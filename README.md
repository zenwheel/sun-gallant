# Sun Gallant

Independent, open-source outline revivals of the 12×22 console font seen on Sun workstations.

- **Sun Gallant Regular** preserves the original 12×22 design exactly.
- **Sun Gallant Vector** is a smooth redraw for contemporary terminal and editor sizes. It follows the bitmap's letterforms closely: slab serifs, heavy stems with hairline joins and thin diagonals, ball terminals, and the original's bold punctuation.

Both are ordinary outline-only TrueType fonts. There are no embedded bitmap strikes.

This project is not affiliated with or endorsed by Sun Microsystems or Oracle.

## Build

You need Python 3.10 or newer and `make`. The first build creates an isolated virtual environment and installs a pinned FontTools release:

```sh
make
```

Outputs:

```text
dist/SunGallant-Regular.ttf
dist/SunGallant-Regular.woff2
dist/sunGallantVector.ttf
dist/sunGallantVector.woff2
```

Run the complete validation suite with:

```sh
make test
```

Builds are deterministic: identical source and dependencies produce identical font binaries.

## Install

Install the TTF for your current macOS or Linux user:

```sh
make install
```

Remove it again with:

```sh
make uninstall
```

On Windows, build the fonts and install both TTF files in `dist/` from Explorer.

Applications that were already running may need to be restarted before the font appears.

## Web

```css
@font-face {
  font-family: 'Sun Gallant';
  src: url('SunGallant-Regular.woff2') format('woff2');
  font-style: normal;
  font-weight: 400;
}

@font-face {
  font-family: 'Sun Gallant Vector';
  src: url('sunGallantVector.woff2') format('woff2');
  font-style: normal;
  font-weight: 400;
}
```

The original face is pixel-perfect at a CSS font size of 22px and integer multiples such as 44px. The Vector face is resolution-independent and intended to scale cleanly at arbitrary sizes.

## How it works

The canonical original source is `sources/glyphs.txt`. Each glyph is a 12×22
ASCII grid, where `#` is filled and `.` is empty. The original Gallant
character range matches the pinned NetBSD bitmap exactly; characters added by
this project follow the same grid.

The builder:

1. validates every glyph and the declared character coverage;
2. builds the original face from compact pixel-boundary contours;
3. builds the vector face from the pinned SVG paths in `sources/vector_paths.json`;
4. converts cubic construction curves to native TrueType quadratic curves;
5. preserves each face's real left side bearings together with the original 17-pixel ascent, 5-pixel descent, and 12-pixel monospace advance;
6. writes outline-only TTF files and derives WOFF2 from them.

The editable centerline construction lives in `scripts/trace_vector_source.py`. Regenerating the pinned path source is optional and requires librsvg (`rsvg-convert`), ImageMagick, and Potrace 1.16:

```sh
python3 scripts/trace_vector_source.py
```

Normal builds do not require any of these tools.

## Coverage

Both faces contain Basic Latin, Latin-1, complete decimal superscript and subscript sets, the Unicode fraction slash, and every precomposed vulgar fraction: 226 encoded glyphs plus `.notdef`.

## License and provenance

Sun Gallant is distributed under the BSD 3-Clause License. The bitmap seed is
derived from NetBSD's `gallant12x22.h`, whose University of California license
is preserved verbatim in the vendored source.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the pinned upstream
revision and checksum.
