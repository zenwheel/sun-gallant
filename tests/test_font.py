from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
TTF = ROOT / "dist" / "SunGallant-Regular.ttf"
WOFF2 = ROOT / "dist" / "SunGallant-Regular.woff2"
VECTOR_TTF = ROOT / "dist" / "sunGallantVector.ttf"
VECTOR_WOFF2 = ROOT / "dist" / "sunGallantVector.woff2"
GLYPH_SOURCE = ROOT / "sources" / "glyphs.txt"
VECTOR_SOURCE = ROOT / "sources" / "vector_paths.json"


def source_rows(codepoint: str) -> list[str]:
    block = GLYPH_SOURCE.read_text(encoding="utf-8").split(f"U+{codepoint} ", 1)[1]
    return block.splitlines()[1:23]


class FontTests(unittest.TestCase):
    def test_expected_outputs_exist(self) -> None:
        self.assertTrue(TTF.is_file())
        self.assertTrue(WOFF2.is_file())
        self.assertTrue(VECTOR_TTF.is_file())
        self.assertTrue(VECTOR_WOFF2.is_file())

    def test_vendored_source_is_pinned(self) -> None:
        source = ROOT / "sources" / "netbsd-gallant12x22.h"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual(digest, "8fd73eda8a698c9157f7e56da461c9cb0e74db3554fc58562dff28c322ccbb46")

    def test_vector_source_is_pinned(self) -> None:
        digest = hashlib.sha256(VECTOR_SOURCE.read_bytes()).hexdigest()
        self.assertEqual(digest, "8a7027fca1e59678ef23cd92ccec6463b4643ba714c226103d1b877cc06d3a12")

    def test_every_visible_glyph_has_a_designed_vector_outline(self) -> None:
        from scripts.trace_vector_source import modern_elements, parse_source

        for codepoint, rows in parse_source().items():
            if not any("#" in row for row in rows):
                continue
            with self.subTest(codepoint=f"U+{codepoint:04X}"):
                elements = modern_elements(codepoint)
                self.assertIsNotNone(
                    elements,
                    f"U+{codepoint:04X} would fall back to an undesigned outline",
                )
                self.assertTrue(all(path.strip() for path, *_ in elements))

    def test_font_is_outline_only(self) -> None:
        for path in (TTF, VECTOR_TTF):
            with self.subTest(path=path.name):
                font = TTFont(path)
                self.assertIn("glyf", font)
                for bitmap_table in ("EBDT", "EBLC", "EBSC", "CBDT", "CBLC", "sbix"):
                    self.assertNotIn(bitmap_table, font)

    def test_metrics_preserve_the_12_by_22_grid(self) -> None:
        font = TTFont(TTF)
        self.assertEqual(font["head"].unitsPerEm, 1408)
        self.assertEqual(font["hhea"].ascent, 1088)
        self.assertEqual(font["hhea"].descent, -320)
        self.assertEqual({advance for advance, _ in font["hmtx"].metrics.values()}, {768})
        self.assertEqual(font["post"].isFixedPitch, 1)

    def test_version_metadata(self) -> None:
        font = TTFont(TTF)
        version = font["name"].getName(5, 3, 1)
        self.assertIsNotNone(version)
        self.assertEqual(version.toUnicode(), "Version 0.1.5")
        self.assertAlmostEqual(font["head"].fontRevision, 0.105, places=3)

    def test_vector_metadata(self) -> None:
        font = TTFont(VECTOR_TTF)
        self.assertEqual(font["name"].getName(1, 3, 1).toUnicode(), "Sun Gallant Vector")
        self.assertEqual(font["name"].getName(4, 3, 1).toUnicode(), "Sun Gallant Vector Regular")
        self.assertEqual(font["name"].getName(5, 3, 1).toUnicode(), "Version 0.1.5")
        self.assertAlmostEqual(font["head"].fontRevision, 0.105, places=3)

    def test_character_coverage(self) -> None:
        font = TTFont(TTF)
        cmap = font.getBestCmap()
        expected = {
            *range(0x20, 0x7F),
            *range(0xA0, 0x100),
            0x2044,
            0x2070,
            *range(0x2074, 0x207A),
            *range(0x2080, 0x208A),
            *range(0x2150, 0x2160),
            0x2189,
        }
        self.assertEqual(set(cmap), expected)

    def test_extended_numbers_remain_monospaced(self) -> None:
        font = TTFont(TTF)
        cmap = font.getBestCmap()
        codepoints = {
            0x2044,
            0x2070,
            *range(0x2074, 0x207A),
            *range(0x2080, 0x208A),
            *range(0x2150, 0x2160),
            0x2189,
        }
        for codepoint in codepoints:
            with self.subTest(codepoint=f"U+{codepoint:04X}"):
                name = cmap[codepoint]
                glyph = font["glyf"][name]
                self.assertGreater(glyph.numberOfContours, 0)
                self.assertGreaterEqual(glyph.xMin, 0)
                self.assertLessEqual(glyph.xMax, 12 * 64)
                self.assertEqual(font["hmtx"][name][0], 12 * 64)

    def test_visible_glyphs_have_real_contours(self) -> None:
        font = TTFont(TTF)
        glyphs = font["glyf"]
        self.assertGreater(glyphs["A"].numberOfContours, 0)
        self.assertEqual(glyphs["space"].numberOfContours, 0)

    def test_left_side_bearings_match_bitmap_insets(self) -> None:
        font = TTFont(TTF)
        glyphs = font["glyf"]
        for name in font.getGlyphOrder():
            glyph = glyphs[name]
            if glyph.numberOfContours:
                with self.subTest(glyph=name):
                    self.assertEqual(font["hmtx"][name][1], glyph.xMin)
        self.assertEqual(font["hmtx"]["i"][1], 3 * 64)
        self.assertEqual(font["hmtx"]["l"][1], 3 * 64)

    def test_original_glyphs_match_vendored_source(self) -> None:
        from scripts.import_netbsd import parse_header

        vendored = parse_header(ROOT / "sources" / "netbsd-gallant12x22.h")
        codepoints = {0, *range(0x20, 0x7F), *range(0xA0, 0x100)}
        for codepoint in codepoints:
            expected = [
                "".join(
                    "#" if (packed_row >> 4) & (1 << (12 - column - 1)) else "."
                    for column in range(12)
                )
                for packed_row in vendored[codepoint]
            ]
            with self.subTest(codepoint=f"U+{codepoint:04X}"):
                self.assertEqual(source_rows(f"{codepoint:04X}"), expected)

    def test_font_remains_strictly_monospaced(self) -> None:
        font = TTFont(TTF)
        self.assertEqual(
            {advance for advance, _ in font["hmtx"].metrics.values()},
            {12 * 64},
        )
        self.assertNotIn("kern", font)
        self.assertNotIn("GPOS", font)

    def test_vector_is_a_native_curved_monospace(self) -> None:
        font = TTFont(VECTOR_TTF)
        glyphs = font["glyf"]
        self.assertTrue(any((flag & 1) == 0 for flag in glyphs["O"].flags))
        self.assertEqual(
            {advance for advance, _ in font["hmtx"].metrics.values()},
            {12 * 64},
        )
        self.assertEqual(font["post"].isFixedPitch, 1)
        for name in font.getGlyphOrder():
            glyph = glyphs[name]
            if glyph.numberOfContours:
                with self.subTest(glyph=name):
                    self.assertEqual(font["hmtx"][name][1], glyph.xMin)
                    self.assertGreaterEqual(glyph.xMin, 0)
                    self.assertLessEqual(glyph.xMax, 12 * 64)
                    self.assertGreaterEqual(glyph.yMin, -5 * 64)
                    self.assertLessEqual(glyph.yMax, 17 * 64)

    def test_faces_have_identical_coverage_and_metrics(self) -> None:
        original = TTFont(TTF)
        vector = TTFont(VECTOR_TTF)
        self.assertEqual(original.getBestCmap(), vector.getBestCmap())
        for table, field in (
            ("head", "unitsPerEm"),
            ("hhea", "ascent"),
            ("hhea", "descent"),
        ):
            self.assertEqual(
                getattr(original[table], field),
                getattr(vector[table], field),
            )

    def test_original_narrow_serifs_are_preserved(self) -> None:
        capital_i = source_rows("0049")
        lowercase_i = source_rows("0069")
        lowercase_l = source_rows("006C")
        self.assertEqual(capital_i[3], "...######...")
        self.assertEqual(lowercase_i[7], "...####.....")
        self.assertEqual(lowercase_l[2], "...####.....")
        self.assertEqual(lowercase_i[16], "...######...")
        self.assertEqual(lowercase_l[16], "...######...")

    def test_structural_capital_edges_are_preserved(self) -> None:
        capital_g = source_rows("0047")
        capital_q = source_rows("0051")
        self.assertEqual(capital_g[11], ".##....#####")
        self.assertEqual(capital_q[18], "..#...###..#")

    def test_woff2_decodes_as_the_same_font(self) -> None:
        for ttf_path, woff2_path in ((TTF, WOFF2), (VECTOR_TTF, VECTOR_WOFF2)):
            with self.subTest(path=ttf_path.name):
                ttf = TTFont(ttf_path)
                woff2 = TTFont(woff2_path)
                self.assertEqual(woff2.flavor, "woff2")
                self.assertEqual(woff2.getBestCmap(), ttf.getBestCmap())
                self.assertEqual(woff2.getGlyphOrder(), ttf.getGlyphOrder())

    def test_build_is_reproducible(self) -> None:
        paths = (TTF, WOFF2, VECTOR_TTF, VECTOR_WOFF2)
        originals = {path: path.read_bytes() for path in paths}
        subprocess.run([sys.executable, ROOT / "scripts" / "build_font.py"], check=True)
        for path in paths:
            self.assertEqual(path.read_bytes(), originals[path])

    def test_user_install_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "SUN_GALLANT_FONT_DIR": directory}
            command = [sys.executable, ROOT / "scripts" / "install_font.py"]
            subprocess.run(command, check=True, env=environment)
            installed = [Path(directory) / path.name for path in (TTF, VECTOR_TTF)]
            for installed_path, source in zip(installed, (TTF, VECTOR_TTF), strict=True):
                self.assertEqual(installed_path.read_bytes(), source.read_bytes())
            subprocess.run([*command, "--remove"], check=True, env=environment)
            self.assertFalse(any(path.exists() for path in installed))


if __name__ == "__main__":
    unittest.main()
