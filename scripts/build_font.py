#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from fontTools.agl import UV2AGL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sources" / "glyphs.txt"
VECTOR_SOURCE = ROOT / "sources" / "vector_paths.json"
DIST = ROOT / "dist"

FAMILY = "Sun Gallant"
VECTOR_FAMILY = "Sun Gallant Vector"
STYLE = "Regular"
VERSION = "0.1.5"
FONT_REVISION = 0.105

WIDTH = 12
HEIGHT = 22
ASCENT = 17
DESCENT = 5
UNITS_PER_PIXEL = 64
UNITS_PER_EM = HEIGHT * UNITS_PER_PIXEL
ADVANCE_WIDTH = WIDTH * UNITS_PER_PIXEL
MAC_EPOCH_AT_UNIX_EPOCH = 2_082_844_800
SUPERSCRIPT_DIGITS = {0x2070, *range(0x2074, 0x207A)}
SUBSCRIPT_DIGITS = set(range(0x2080, 0x208A))
FRACTIONS = {0x2044, *range(0x2150, 0x2160), 0x2189}
VENDORED_CODEPOINTS = {0, *range(0x20, 0x7F), *range(0xA0, 0x100)}

EXPECTED_CODEPOINTS = {
    *VENDORED_CODEPOINTS,
    *SUPERSCRIPT_DIGITS,
    *SUBSCRIPT_DIGITS,
    *FRACTIONS,
}

Point = tuple[int, int]
Edge = tuple[Point, Point]


def parse_source(path: Path) -> dict[int, tuple[str, ...]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    glyphs: dict[int, tuple[str, ...]] = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        index += 1
        if not line or line.startswith("#"):
            continue

        match = re.fullmatch(r"U\+([0-9A-F]{4,6})(?: .*)?", line)
        if not match:
            raise ValueError(f"{path}:{index}: invalid glyph header: {line!r}")
        codepoint = int(match.group(1), 16)

        rows = tuple(lines[index : index + HEIGHT])
        if len(rows) != HEIGHT:
            raise ValueError(f"{path}:{index}: truncated U+{codepoint:04X}")
        index += HEIGHT
        for row_number, row in enumerate(rows, start=1):
            if len(row) != WIDTH or set(row) - {"#", "."}:
                raise ValueError(
                    f"{path}:{index - HEIGHT + row_number}: expected {WIDTH} characters of # or ."
                )
        if codepoint in glyphs:
            raise ValueError(f"{path}:{index}: duplicate U+{codepoint:04X}")
        glyphs[codepoint] = rows

    if glyphs.keys() != EXPECTED_CODEPOINTS:
        missing = sorted(EXPECTED_CODEPOINTS - glyphs.keys())
        extra = sorted(glyphs.keys() - EXPECTED_CODEPOINTS)
        raise ValueError(f"unexpected coverage; missing={missing}, extra={extra}")
    return glyphs


def boundary_edges(rows: tuple[str, ...]) -> set[Edge]:
    edges: set[Edge] = set()
    for row, pixels in enumerate(rows):
        for column, pixel in enumerate(pixels):
            if pixel != "#":
                continue

            left = column
            right = column + 1
            top = ASCENT - row
            bottom = top - 1

            if column == 0 or pixels[column - 1] == ".":
                edges.add(((left, bottom), (left, top)))
            if row == 0 or rows[row - 1][column] == ".":
                edges.add(((left, top), (right, top)))
            if column == WIDTH - 1 or pixels[column + 1] == ".":
                edges.add(((right, top), (right, bottom)))
            if row == HEIGHT - 1 or rows[row + 1][column] == ".":
                edges.add(((right, bottom), (left, bottom)))
    return edges


def direction(edge: Edge) -> Point:
    (x1, y1), (x2, y2) = edge
    return x2 - x1, y2 - y1


def choose_next(current: Edge, candidates: list[Edge]) -> Edge:
    dx, dy = direction(current)
    preferred = ((dy, -dx), (dx, dy), (-dy, dx), (-dx, -dy))
    by_direction = {direction(candidate): candidate for candidate in candidates}
    for next_direction in preferred:
        if next_direction in by_direction:
            return by_direction[next_direction]
    raise ValueError("outline contains a disconnected edge")


def simplify(points: list[Point]) -> list[Point]:
    changed = True
    while changed and len(points) > 3:
        changed = False
        simplified: list[Point] = []
        for index, point in enumerate(points):
            previous = points[index - 1]
            following = points[(index + 1) % len(points)]
            if (previous[0] == point[0] == following[0]) or (
                previous[1] == point[1] == following[1]
            ):
                changed = True
            else:
                simplified.append(point)
        points = simplified
    return points


def contours(rows: tuple[str, ...]) -> list[list[Point]]:
    remaining = boundary_edges(rows)
    outgoing: dict[Point, set[Edge]] = defaultdict(set)
    for edge in remaining:
        outgoing[edge[0]].add(edge)

    result: list[list[Point]] = []
    while remaining:
        first = min(remaining)
        current = first
        points = [first[0]]

        while True:
            remaining.remove(current)
            outgoing[current[0]].remove(current)
            end = current[1]
            if end == first[0]:
                break

            candidates = [edge for edge in outgoing[end] if edge in remaining]
            if not candidates:
                raise ValueError(f"open outline at {end}")
            current = choose_next(current, candidates)
            points.append(end)

        result.append(simplify(points))
    return result


def make_glyph(rows: tuple[str, ...]):
    pen = TTGlyphPen(None)
    for outline in contours(rows):
        scaled = [(x * UNITS_PER_PIXEL, y * UNITS_PER_PIXEL) for x, y in outline]
        pen.moveTo(scaled[0])
        for point in scaled[1:]:
            pen.lineTo(point)
        pen.closePath()
    return pen.glyph()


def parse_vector_source(path: Path) -> dict[int, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != 1:
        raise ValueError(f"{path}: unsupported vector source format")
    paths = {
        int(codepoint, 16): outline
        for codepoint, outline in payload.get("paths", {}).items()
    }
    if paths.keys() != EXPECTED_CODEPOINTS:
        missing = sorted(EXPECTED_CODEPOINTS - paths.keys())
        extra = sorted(paths.keys() - EXPECTED_CODEPOINTS)
        raise ValueError(f"unexpected vector coverage; missing={missing}, extra={extra}")
    if any(not isinstance(outline, str) for outline in paths.values()):
        raise ValueError(f"{path}: every vector outline must be an SVG path string")
    return paths


def make_vector_glyph(path: str):
    quadratic_pen = TTGlyphPen(None)
    curve_pen = Cu2QuPen(quadratic_pen, max_err=1, reverse_direction=False)
    pen = TransformPen(
        curve_pen,
        (1, 0, 0, 1, 0, -DESCENT * UNITS_PER_PIXEL),
    )
    parse_path(path, pen)
    return quadratic_pen.glyph()


def glyph_left_side_bearing(glyph) -> int:
    return min((point[0] for point in glyph.coordinates), default=0)


def glyph_name(codepoint: int) -> str:
    if codepoint == 0:
        return ".notdef"
    return UV2AGL.get(codepoint, f"uni{codepoint:04X}")


def left_side_bearing(rows: tuple[str, ...]) -> int:
    filled_columns = [
        column for row in rows for column, pixel in enumerate(row) if pixel == "#"
    ]
    return min(filled_columns, default=0) * UNITS_PER_PIXEL


def build_regular() -> tuple[Path, Path]:
    source = parse_source(SOURCE)
    codepoints = list(source)
    glyph_order = [glyph_name(codepoint) for codepoint in codepoints]
    glyphs = {glyph_name(codepoint): make_glyph(source[codepoint]) for codepoint in codepoints}
    metrics = {
        glyph_name(codepoint): (ADVANCE_WIDTH, left_side_bearing(source[codepoint]))
        for codepoint in codepoints
    }
    cmap = {codepoint: glyph_name(codepoint) for codepoint in codepoints if codepoint != 0}

    font_builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    font_builder.setupGlyphOrder(glyph_order)
    font_builder.setupCharacterMap(cmap)
    font_builder.setupGlyf(glyphs)
    font_builder.setupHorizontalMetrics(metrics)
    font_builder.setupHorizontalHeader(
        ascent=ASCENT * UNITS_PER_PIXEL,
        descent=-DESCENT * UNITS_PER_PIXEL,
        lineGap=0,
    )
    font_builder.setupNameTable(
        {
            "familyName": FAMILY,
            "styleName": STYLE,
            "uniqueFontIdentifier": f"{FAMILY} {VERSION}",
            "fullName": f"{FAMILY} {STYLE}",
            "psName": "SunGallant-Regular",
            "version": f"Version {VERSION}",
            "copyright": (
                "Copyright 2026 theMackabu, sf.tools; "
                "Glyph data copyright 1992, 1993 The Regents of the University of California."
            ),
            "licenseDescription": "BSD 3-Clause License",
            "licenseInfoURL": "https://opensource.org/license/bsd-3-clause",
            "description": "An independent outline revival of the Sun workstation console font.",
        }
    )
    font_builder.setupOS2(
        sTypoAscender=ASCENT * UNITS_PER_PIXEL,
        sTypoDescender=-DESCENT * UNITS_PER_PIXEL,
        sTypoLineGap=0,
        usWinAscent=ASCENT * UNITS_PER_PIXEL,
        usWinDescent=DESCENT * UNITS_PER_PIXEL,
        usWeightClass=400,
        usWidthClass=5,
        fsSelection=0x40,
        achVendID="SGAL",
        sxHeight=7 * UNITS_PER_PIXEL,
        sCapHeight=12 * UNITS_PER_PIXEL,
    )
    font_builder.setupPost(keepGlyphNames=True, isFixedPitch=1)
    font_builder.setupMaxp()

    font = font_builder.font
    font["head"].created = MAC_EPOCH_AT_UNIX_EPOCH
    font["head"].modified = MAC_EPOCH_AT_UNIX_EPOCH
    font["head"].fontRevision = FONT_REVISION
    font["head"].lowestRecPPEM = 11
    font["OS/2"].fsType = 0

    DIST.mkdir(exist_ok=True)
    ttf_path = DIST / "SunGallant-Regular.ttf"
    woff2_path = DIST / "SunGallant-Regular.woff2"
    font.save(ttf_path, reorderTables=False)

    web_font = TTFont(ttf_path, recalcTimestamp=False)
    web_font.flavor = "woff2"
    web_font.save(woff2_path, reorderTables=False)
    return ttf_path, woff2_path


def build_vector() -> tuple[Path, Path]:
    source = parse_source(SOURCE)
    vector_source = parse_vector_source(VECTOR_SOURCE)
    codepoints = list(source)
    glyph_order = [glyph_name(codepoint) for codepoint in codepoints]
    glyphs = {
        glyph_name(codepoint): make_vector_glyph(vector_source[codepoint])
        for codepoint in codepoints
    }
    metrics = {
        glyph_name(codepoint): (
            ADVANCE_WIDTH,
            glyph_left_side_bearing(glyphs[glyph_name(codepoint)]),
        )
        for codepoint in codepoints
    }
    cmap = {codepoint: glyph_name(codepoint) for codepoint in codepoints if codepoint != 0}

    font_builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    font_builder.setupGlyphOrder(glyph_order)
    font_builder.setupCharacterMap(cmap)
    font_builder.setupGlyf(glyphs)
    font_builder.setupHorizontalMetrics(metrics)
    font_builder.setupHorizontalHeader(
        ascent=ASCENT * UNITS_PER_PIXEL,
        descent=-DESCENT * UNITS_PER_PIXEL,
        lineGap=0,
    )
    font_builder.setupNameTable(
        {
            "familyName": VECTOR_FAMILY,
            "styleName": STYLE,
            "uniqueFontIdentifier": f"{VECTOR_FAMILY} {VERSION}",
            "fullName": f"{VECTOR_FAMILY} {STYLE}",
            "psName": "SunGallantVector-Regular",
            "version": f"Version {VERSION}",
            "copyright": (
                "Copyright 2026 theMackabu, sf.tools; "
                "Glyph data copyright 1992, 1993 The Regents of the University of California."
            ),
            "licenseDescription": "BSD 3-Clause License",
            "licenseInfoURL": "https://opensource.org/license/bsd-3-clause",
            "description": (
                "A serifed vector redraw of Sun Gallant that keeps the original "
                "bitmap's slab serifs and stroke contrast."
            ),
        }
    )
    font_builder.setupOS2(
        sTypoAscender=ASCENT * UNITS_PER_PIXEL,
        sTypoDescender=-DESCENT * UNITS_PER_PIXEL,
        sTypoLineGap=0,
        usWinAscent=ASCENT * UNITS_PER_PIXEL,
        usWinDescent=DESCENT * UNITS_PER_PIXEL,
        usWeightClass=400,
        usWidthClass=5,
        fsSelection=0x40,
        achVendID="SGAL",
        sxHeight=9 * UNITS_PER_PIXEL,
        sCapHeight=13 * UNITS_PER_PIXEL,
    )
    font_builder.setupPost(keepGlyphNames=True, isFixedPitch=1)
    font_builder.setupMaxp()

    font = font_builder.font
    font["head"].created = MAC_EPOCH_AT_UNIX_EPOCH
    font["head"].modified = MAC_EPOCH_AT_UNIX_EPOCH
    font["head"].fontRevision = FONT_REVISION
    font["head"].lowestRecPPEM = 8
    font["OS/2"].fsType = 0

    DIST.mkdir(exist_ok=True)
    ttf_path = DIST / "sunGallantVector.ttf"
    woff2_path = DIST / "sunGallantVector.woff2"
    font.save(ttf_path, reorderTables=False)

    web_font = TTFont(ttf_path, recalcTimestamp=False)
    web_font.flavor = "woff2"
    web_font.save(woff2_path, reorderTables=False)
    return ttf_path, woff2_path


def build() -> tuple[Path, ...]:
    return (*build_regular(), *build_vector())


if __name__ == "__main__":
    for output in build():
        print(f"Built {output.relative_to(ROOT)}")
