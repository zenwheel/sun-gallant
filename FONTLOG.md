# Fontlog

## 0.1.5

- Redrew `Sun Gallant Vector` to follow the original bitmap instead of a sans-serif skeleton: slab serifs on capitals and lowercase stems, angled head serifs on ascenders, and beaked terminals on `C G S E F L T Z`.
- Strokes are now drawn with a horizontal broad nib, so stems stay as heavy as the original's two-pixel verticals while horizontals, bowls' tops and bottoms, and selected diagonals (`A K M N V W X Y`) thin to its one-pixel hairlines.
- Restored the original's ball terminals (`a c f j r y J`), round dots, teardrop comma and quotes, two-pixel bars on digits and operators, taller digits, descending `J`, and underlined ordinal indicators.
- Broad strokes now end flat across the stroke, so diagonal legs no longer poke past their serifs.

## 0.1.4

- Restored the original's swash-tailed `Q` and double-storey `g` as geometric redrawings.
- Rebuilt `y` so its descender flows continuously out of the right diagonal instead of overlapping it.

## 0.1.3

- Added `Sun Gallant Vector`, a from-scratch geometric monospace redraw with smooth quadratic curves, flat terminals, and the same 12-unit advance and character coverage as the original face.
- Drew every visible Latin-1 letter and symbol in the same geometric system, including `Æ æ Ø ø Ð ð Þ þ ß`, inverted punctuation, and the currency, legal, and mathematical signs; the build now refuses to fall back to bitmap-derived skeleton outlines.
- Derived superscripts, subscripts, ordinal indicators, and every vulgar fraction geometrically from the redrawn digits, with normalized scale, weight, alignment, and a consistent fraction slash.
- Normalized diacritic placement and weight across capitals and lowercase, with intentional square diaeresis dots.
- Narrowed `0` against `O` following the original bitmap's slashless distinction, and evened out the dense joins of `M` and `m`.
- Added editable centerline construction and a pinned vector-path source so ordinary builds remain deterministic and require only FontTools.

## 0.1.2

- Corrected every glyph's TrueType left side bearing to match its actual horizontal inset while preserving the 12-pixel monospace advance.
- Restored the pinned original Gallant glyph shapes and retired the separate `Sun Gallant Classic` family.

## 0.1.1

- Added a separate `Sun Gallant Classic` family that preserves the pinned Gallant bitmap while retaining the same outline-only TTF and WOFF2 formats.
- Inset the outer serif tips of boundary-reaching capitals by one pixel to prevent adjacent capitals from joining, without adding kerning or changing the 12-pixel advance.

## 0.1.0

- Seeded Basic Latin and Latin-1 from the independently licensed NetBSD Gallant console bitmap.
- Added deterministic bitmap-to-outline generation.
- Added desktop TTF and web WOFF2 outputs.
- Added current-user installation, uninstallation, tests, specimen, and CI.
- Optically widened the serifs of `I`, `i`, `l`, and `f` while preserving the original 12-pixel monospace advance.
- Added complete superscript and subscript decimal digits, the fraction slash, and the full Unicode set of precomposed vulgar fractions.
