#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sources" / "glyphs.txt"
OUTPUT = ROOT / "sources" / "vector_paths.json"
WIDTH = 12
HEIGHT = 22

# Stem weight in cell units; Gallant's stems are two pixels of a 12-pixel cell.
STEM = 1.8

PATH_COMMANDS = {"M", "L", "H", "V", "C", "S", "Q", "T", "Z"}
NUMBER_PATTERN = re.compile(r"[A-Za-z]|[-+]?(?:\d+\.?\d*|\.\d+)")


def number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def transform_path(
    path: str,
    scale_x: float,
    scale_y: float,
    offset_x: float,
    offset_y: float,
) -> str:
    tokens: list[str] = []
    command = ""
    x_axis = True
    for token in NUMBER_PATTERN.findall(path):
        if token.isalpha():
            command = token.upper()
            if command not in PATH_COMMANDS or command != token:
                raise ValueError(f"unsupported path command {token!r}")
            x_axis = True
            tokens.append(token)
            continue
        value = float(token)
        if command == "V" or (command not in "HV" and not x_axis):
            tokens.append(number(value * scale_y + offset_y))
        else:
            tokens.append(number(value * scale_x + offset_x))
        if command not in "HV":
            x_axis = not x_axis
    return " ".join(tokens)


def dot(cx: float, cy: float, r: float) -> str:
    """A closed circle, for ball terminals and punctuation drawn with the fill pen."""
    k = 0.5523 * r
    n = number
    return (
        f"M{n(cx)} {n(cy - r)} "
        f"C{n(cx + k)} {n(cy - r)} {n(cx + r)} {n(cy - k)} {n(cx + r)} {n(cy)} "
        f"C{n(cx + r)} {n(cy + k)} {n(cx + k)} {n(cy + r)} {n(cx)} {n(cy + r)} "
        f"C{n(cx - k)} {n(cy + r)} {n(cx - r)} {n(cy + k)} {n(cx - r)} {n(cy)} "
        f"C{n(cx - r)} {n(cy - k)} {n(cx - k)} {n(cy - r)} {n(cx)} {n(cy - r)} Z"
    )


def bar(left: float, top: float, right: float, bottom: float) -> str:
    """A filled rectangle, for the original's two-pixel horizontal bars."""
    n = number
    return f"M{n(left)} {n(top)} H{n(right)} V{n(bottom)} H{n(left)} Z"


def turned(drawing: str) -> str:
    """Rotate a drawing 180 degrees about the cell, for inverted punctuation."""
    return "|".join(
        transform_path(part, -1, -1, 12, 20.2) if part.strip() else ""
        for part in drawing.split("|")
    )


# Serifed centerlines on Gallant's 12 by 22 pixel grid. Ink follows the
# bitmap's pixel edges: capitals span y=3-17, digits and ascenders rise to
# y=2, the x-height is y=7, and descenders reach y=22. Centerlines therefore
# sit half a hairline inside those edges (3.4, 16.6, 7.4, 2.4, 21.6), and a
# two-pixel stem in columns c and c+1 is centered on x=c+1.
#
# A drawing is "broad | hair | fill": broad strokes use the horizontal nib,
# so verticals come out as heavy as Gallant's stems while horizontals and
# shallow curves thin to its one-pixel joins; hairlines carry the slab
# serifs and the thin diagonals; fills are ball terminals, dots, and the
# two-pixel bars of digits and operators. A list of (path, weight[, pen])
# pairs is used where a glyph needs a lighter or heavier stroke.
MODERN_PATHS = {
    0: "M2 3.4 H10 V16.6 H2 Z",
    # Punctuation and operators.
    ord("!"): f"M6 2 V12.4 | | {dot(6, 15.8, 1.05)}",
    ord('"'): "M4 2 V7.8 M8 2 V7.8",
    ord("#"): f"M6.9 2 L3.1 17 M10.3 2 L6.5 17 | | {bar(3.4, 6, 11.4, 7.8)} {bar(0.8, 12, 8.8, 13.8)}",
    ord("$"): "M9.6 5.4 C9 4 7.8 3.4 6 3.4 C3.6 3.4 2.2 4.4 2.2 6.2 C2.2 8 3.6 8.8 6 9.6 C8.6 10.4 9.8 11.4 9.8 13 C9.8 14.6 8.4 15.6 6 15.6 C4 15.6 2.6 14.8 2 13.2 M6 1.8 V17.2",
    ord("%"): [
        ("M2.6 17 L10 2", 1.0),
        ("M3.4 2.6 C2.3 2.6 1.6 3.4 1.6 4.7 C1.6 6 2.3 6.8 3.4 6.8 C4.5 6.8 5.2 6 5.2 4.7 C5.2 3.4 4.5 2.6 3.4 2.6", 0.75),
        ("M8.6 12.2 C7.5 12.2 6.8 13 6.8 14.3 C6.8 15.6 7.5 16.4 8.6 16.4 C9.7 16.4 10.4 15.6 10.4 14.3 C10.4 13 9.7 12.2 8.6 12.2", 0.75),
    ],
    ord("&"): "M10.4 16.6 L4.4 9.4 C3.4 8.2 3 7.2 3 6 C3 4 4.2 2.6 6 2.6 C7.6 2.6 8.6 3.6 8.6 5 C8.6 6.4 7.6 7.6 5.2 9.2 C3 10.6 2 11.8 2 13.4 C2 15.4 3.4 16.6 5.6 16.6 C7.6 16.6 9 15.6 10 12.4 | M8.6 12.4 H11",
    ord("'"): f"M6.5 3.4 C6.6 5.6 5.8 7.6 3.9 9.2 | | {dot(5.6, 3.6, 1.3)}",
    ord("("): "M9 2 C6.6 4.6 5.8 7.2 5.8 9.5 C5.8 11.8 6.6 14.4 9 17",
    ord(")"): "M3 2 C5.4 4.6 6.2 7.2 6.2 9.5 C6.2 11.8 5.4 14.4 3 17",
    ord("*"): "M6 6.4 V16.6 M2.4 8.4 L9.6 14.4 M9.6 8.4 L2.4 14.4 | M4.4 6.4 H7.6 M4.4 16.6 H7.6",
    ord("+"): f"M6 7 V17 | | {bar(1.4, 11.1, 10.6, 12.9)}",
    ord(","): f"M6.3 15.8 C6.5 18 5.8 19.8 4 21.4 | | {dot(5.2, 15.4, 1.3)}",
    ord("-"): f"| | {bar(1.4, 11.1, 10.6, 12.9)}",
    ord("."): f"| | {dot(5.2, 15.4, 1.4)}",
    ord("/"): "M2 17 L10 2",
    ord(":"): f"| | {dot(5.2, 8.9, 1.3)} {dot(5.2, 15.4, 1.3)}",
    ord(";"): f"M6.3 16.6 C6.5 18.6 5.8 20 4 21.4 | | {dot(5.2, 9.9, 1.3)} {dot(5.2, 16, 1.3)}",
    ord("<"): "M10 7.4 L2.4 12 L10 16.6",
    ord("="): f"| | {bar(1.4, 9, 10.6, 10.8)} {bar(1.4, 13.2, 10.6, 15)}",
    ord(">"): "M2 7.4 L9.6 12 L2 16.6",
    ord("?"): f"M2.6 5.4 C2.8 3.4 4.2 2.4 6 2.4 C8 2.4 9.2 3.6 9.2 5.4 C9.2 7.4 8.2 8.4 7 9.6 C5.6 11 5 11.6 5 12.6 | | {dot(5, 15.8, 1.05)}",
    ord("@"): [
        ("M10 13.6 V9 C10 6.6 8.6 5.4 6.4 5.4 C3.6 5.4 2 7.4 2 11 C2 14.6 3.6 16.6 6.6 16.6 H10.4", 0.85),
        ("M8 9.6 C7.6 9.1 7.1 8.8 6.5 8.8 C5.2 8.8 4.4 9.8 4.4 11.2 C4.4 12.6 5.2 13.4 6.4 13.4 C7.2 13.4 7.8 13 8 12.2 M8 8.8 V13.6 H10", 0.7),
    ],
    ord("["): f"M6 2.4 V16.6 | | {bar(5.1, 2, 10, 3.8)} {bar(5.1, 15.2, 10, 17)}",
    ord("\\"): "M2 2 L10 17",
    ord("]"): f"M5 2.4 V16.6 | | {bar(1.4, 2, 5.9, 3.8)} {bar(1.4, 15.2, 5.9, 17)}",
    ord("^"): "M2 6.6 L6 2.4 L10 6.6",
    ord("_"): f"| | {bar(0.3, 18, 11.7, 19.8)}",
    ord("`"): f"M5.8 7 C5.8 5.2 6.4 3.6 7.6 2.4 | | {dot(6.6, 7.2, 1.25)}",
    ord("{"): "M9.4 2.4 H8.6 C7.2 2.4 6.6 3.2 6.6 4.6 V6.8 C6.6 8.4 6 9.3 4.4 9.6 C6 9.9 6.6 10.8 6.6 12.4 V14.4 C6.6 15.8 7.2 16.6 8.6 16.6 H9.4",
    ord("|"): "M6 2 V22",
    ord("}"): "M2.6 2.4 H3.4 C4.8 2.4 5.4 3.2 5.4 4.6 V6.8 C5.4 8.4 6 9.3 7.6 9.6 C6 9.9 5.4 10.8 5.4 12.4 V14.4 C5.4 15.8 4.8 16.6 3.4 16.6 H2.6",
    ord("~"): "M1.8 14 C2.2 11.6 3.2 10.4 4.6 10.4 C6.2 10.4 6.4 13.6 7.8 13.6 C9 13.6 9.8 12.4 10.4 10.2",
    # Digits rise a pixel above the capitals, as in the original.
    ord("0"): "M6 2.4 C4 2.4 2.6 4.6 2.6 9.5 C2.6 14.4 4 16.6 6 16.6 C8 16.6 9.4 14.4 9.4 9.5 C9.4 4.6 8 2.4 6 2.4",
    ord("1"): "M6 2.4 V16.6 | M6 2.4 L2.6 6.4 M2.6 16.6 H9.4",
    ord("2"): f"M2 5.4 C2.4 3.4 4 2.4 5.8 2.4 C8 2.4 9.2 3.6 9.2 5.6 C9.2 7.6 8.2 9 6.4 10.8 L2.2 15.4 | M10.2 14 V16.2 | {bar(1.4, 15.2, 10.6, 17)}",
    ord("3"): "M2.2 5 C2.8 3.3 4.2 2.4 6 2.4 C8.2 2.4 9.4 3.6 9.4 5.4 C9.4 7.6 8 8.8 5.6 8.8 H4.6 M5.6 8.8 C8.6 8.8 10 10.2 10 12.6 C10 15.2 8.4 16.6 6 16.6 C4.2 16.6 2.7 15.8 2 14.2",
    ord("4"): f"M8 2 V17 | M7.6 2.4 L2 11.4 | {bar(1.6, 11, 10.8, 12.8)}",
    ord("5"): f"M2.6 9.4 C3.4 8 4.6 7.4 6 7.4 C8.6 7.4 10 9 10 11.8 C10 14.8 8.4 16.6 5.8 16.6 C4 16.6 2.6 15.8 2 14.4 | M3.8 3 L2.8 9 | {bar(3.4, 2, 9.8, 3.8)}",
    ord("6"): "M8.6 2.4 C5 3 2 6 2 11.2 C2 14.8 3.6 16.6 6 16.6 C8.6 16.6 10 15 10 12.4 C10 9.8 8.6 8.4 6.2 8.4 C4.4 8.4 2.9 9.4 2.2 10.8",
    ord("7"): f"M9.8 3.4 C8 7.6 6.4 11.6 5.5 17 | M1.8 2.6 V5 | {bar(1.8, 2, 10.6, 3.8)}",
    ord("8"): "M6 2.4 C4 2.4 2.8 3.4 2.8 5.2 C2.8 7 4 8.2 6 8.8 C8.2 9.4 9.2 10.6 9.2 12.6 C9.2 15 8 16.6 6 16.6 C4 16.6 2.8 15 2.8 12.6 C2.8 10.6 3.8 9.4 6 8.8 C8 8.2 9.2 7 9.2 5.2 C9.2 3.4 8 2.4 6 2.4",
    ord("9"): "M6 2.4 C3.4 2.4 2 4 2 6.6 C2 9 3.4 10.4 5.8 10.4 C7.8 10.4 9.2 9.4 9.8 8 M6 2.4 C8.6 2.4 10 4.4 10 8.4 C10 13.2 7.2 16.2 2.6 16.6",
    # Capitals.
    ord("A"): "M6 3.4 L10.1 16.6 | M5.6 3.4 L1.9 16.6 M5.2 3.4 H6.4 M3.2 11.5 H8.8 M0.7 16.6 H3 M8.6 16.6 H11.3",
    ord("B"): "M2 3.4 V16.6 M2 3.4 H6.4 C8.4 3.4 9.4 4.4 9.4 6.3 C9.4 8.3 8.2 9.5 6.4 9.5 H2 M6.4 9.5 C8.8 9.5 10 10.6 10 12.8 C10 15.3 8.7 16.6 6.4 16.6 H2 | M0.7 3.4 H2 M0.7 16.6 H2",
    ord("C"): "M9.8 4.4 C9 3.7 7.9 3.4 6.4 3.4 C3.4 3.4 2 5.6 2 10 C2 14.4 3.4 16.6 6.2 16.6 C8 16.6 9.2 15.9 10.2 14.6 | M10.2 3.6 V6.2",
    ord("D"): "M2 3.4 V16.6 M2 3.4 H5.4 C8.6 3.4 10 5.6 10 10 C10 14.4 8.6 16.6 5.4 16.6 H2 | M0.7 3.4 H2 M0.7 16.6 H2",
    ord("E"): "M3 3.4 V16.6 | M1.4 3.4 H9.6 V5.8 M3 9.5 H8.6 M8.6 8.3 V10.7 M1.4 16.6 H10.6 V14.2",
    ord("F"): "M3 3.4 V16.6 | M1.4 3.4 H9.6 V5.8 M3 9.5 H8.6 M8.6 8.3 V10.7 M1.4 16.6 H4.6",
    ord("G"): "M9.8 4.4 C9 3.7 7.9 3.4 6.4 3.4 C3.4 3.4 2 5.6 2 10 C2 14.4 3.4 16.6 6.4 16.6 C8 16.6 9.2 16.2 10 15.6 V11.5 | M10.2 3.6 V6.2 M7.2 11.5 H11.3",
    ord("H"): "M2 3.4 V16.6 M10 3.4 V16.6 | M0.7 3.4 H3.3 M8.7 3.4 H11.3 M0.7 16.6 H3.3 M8.7 16.6 H11.3 M2 9.5 H10",
    ord("I"): "M6 3.4 V16.6 | M3.4 3.4 H8.6 M3.4 16.6 H8.6",
    ord("J"): f"M6 3.4 V18.4 C6 20.4 5.2 21.4 3.8 21.4 | M3.4 3.4 H8.6 | {dot(3.2, 20.6, 1)}",
    ord("K"): "M2 3.4 V16.6 M4.2 9.6 L10.2 16.6 | M9 3.4 L2.6 10.6 M0.7 3.4 H3.3 M7.6 3.4 H10.6 M0.7 16.6 H3.3 M8.4 16.6 H11.3",
    ord("L"): "M3 3.4 V16.6 | M1.4 3.4 H4.6 M1.4 16.6 H10.6 V14.2",
    ord("M"): "M2.2 3.4 L5.8 16.4 M10 3.4 V16.6 | M1.5 3.4 V16.6 M9.8 3.4 L5.8 16.4 M0.6 3.4 H2.4 M9.6 3.4 H11.3 M0.6 16.6 H2.6 M8.7 16.6 H11.3",
    ord("N"): "M1.9 3.4 L10.2 16.6 | M1.4 3.4 V16.6 M10.6 3.4 V16.6 M0.5 3.4 H2 M9.4 3.4 H11.5 M0.5 16.6 H2.6",
    ord("O"): "M6 3.4 C3.4 3.4 2 5.6 2 10 C2 14.4 3.4 16.6 6 16.6 C8.6 16.6 10 14.4 10 10 C10 5.6 8.6 3.4 6 3.4",
    ord("P"): "M3 3.4 V16.6 M3 3.4 H6.6 C8.8 3.4 10 4.6 10 6.6 C10 8.5 8.8 9.6 6.6 9.6 H3 | M1.4 3.4 H3 M1.4 16.6 H4.6",
    ord("Q"): "M6 3.4 C3.4 3.4 2 5.6 2 10 C2 14.4 3.4 16.6 6 16.6 C8.6 16.6 10 14.4 10 10 C10 5.6 8.6 3.4 6 3.4 M5.4 16.8 C4.2 17.1 3.2 17.7 2.8 18.4 C2.55 18.95 3 19.1 3.7 18.75 C4.7 18.25 5.7 18.35 6.7 19.1 C7.9 20 9.3 19.8 10.6 18.4",
    ord("R"): "M2 3.4 V16.6 M2 3.4 H6.4 C8.6 3.4 9.8 4.5 9.8 6.4 C9.8 8.3 8.6 9.5 6.4 9.5 H2 M5 9.8 L10.2 16.6 | M0.7 3.4 H2 M0.7 16.6 H3.3 M9.2 16.6 H11.3",
    ord("S"): "M9.9 4.4 C9 3.7 7.8 3.4 6.3 3.4 C3.6 3.4 2.2 4.5 2.2 6.4 C2.2 8.4 3.6 9.2 6 9.9 C8.6 10.6 10 11.6 10 13.6 C10 15.6 8.6 16.6 5.8 16.6 C4.2 16.6 2.9 16.3 1.8 15.6 | M10.2 3.6 V6.2 M1.6 13.6 V16.2",
    ord("T"): "M6 3.4 V16.6 | M1.4 3.4 H10.6 M1.4 3.4 V5.4 M10.6 3.4 V5.4 M3.4 16.6 H8.6",
    ord("U"): "M2 3.4 V12.4 C2 15.2 3.4 16.6 6 16.6 | M6 16.6 C8.6 16.6 10.4 15.2 10.4 12.4 V3.4 M0.7 3.4 H3.3 M8.8 3.4 H11.3",
    ord("V"): "M2 3.4 L6 16.6 | M10.2 3.4 L6 16.6 M0.7 3.4 H3.4 M8.6 3.4 H11.3",
    ord("W"): "M1.8 3.4 L4 16.6 M5.6 3.4 L8 16.6 | M4 16.6 L5.8 8 M8 16.6 L10.5 3.4 M0.5 3.4 H6.6 M8.6 3.4 H11.5",
    ord("X"): "M2.2 3.4 L9.8 16.6 | M9.8 3.4 L2.2 16.6 M0.7 3.4 H3.6 M8.6 3.4 H11.3 M0.7 16.6 H3.4 M8.4 16.6 H11.3",
    ord("Y"): "M2.2 3.4 L6 10 V16.6 | M9.8 3.4 L6 10 M0.7 3.4 H3.6 M8.6 3.4 H11.3 M3.6 16.6 H8.4",
    ord("Z"): "M9.4 3.4 L2.6 16.6 | M2.4 3.4 H9.8 M2.4 3.4 V5.2 M2.2 16.6 H9.8 V14.6",
    # Lowercase.
    ord("a"): "M3.4 9.4 C3.6 8 4.6 7.4 6.2 7.4 C8 7.4 9 8.2 9 10 V15.4 C9 16.2 9.6 16.6 10.6 16.6 M9 10.8 H6.4 C4 10.8 2.6 11.8 2.6 13.7 C2.6 15.6 3.6 16.6 5.2 16.6 C6.8 16.6 8.2 15.8 9 14.4",
    ord("b"): "M2 2.4 V16.6 M2.2 10 C2.8 8.2 4.2 7.4 6 7.4 C8.6 7.4 10 9 10 12 C10 15 8.6 16.6 6 16.6 C4.2 16.6 2.8 15.8 2.2 14.6 | M0.6 3.8 L2 2.4",
    ord("c"): "M9 8.2 V9.8 M9.4 8.4 C8.6 7.7 7.6 7.4 6.2 7.4 C3.6 7.4 2 9 2 12 C2 15 3.6 16.6 6.2 16.6 C7.6 16.6 8.7 16 9.6 14.8",
    ord("d"): "M10 2.4 V16.6 M9.8 10 C9.2 8.2 7.8 7.4 6 7.4 C3.4 7.4 2 9 2 12 C2 15 3.4 16.6 6 16.6 C7.8 16.6 9.2 15.8 9.8 14.6 | M8.4 3.8 L10 2.4 M10 16.6 H11.4",
    ord("e"): "M2 11.6 H10 C10 9 8.6 7.4 6 7.4 C3.4 7.4 2 9 2 12 C2 15 3.6 16.6 6.4 16.6 C7.9 16.6 9 16 9.9 14.9",
    ord("f"): f"M5 16.6 V5.6 C5 3.4 6 2.4 7.6 2.4 C8.4 2.4 9 2.6 9.4 3 | M2.8 9.4 H8.6 M2.8 16.6 H7.2 | {dot(9, 3.9, 0.95)}",
    ord("g"): [
        ("M5.5 7.4 C3.4 7.4 2 8.4 2 10 C2 11.6 3.4 12.6 5.5 12.6 C7.6 12.6 9 11.6 9 10 C9 8.4 7.6 7.4 5.5 7.4", 1.0),
        ("M8.4 8.2 C9 7.8 9.8 7.5 10.6 7.4", 1.0, "hair"),
        ("M3.4 12.2 C2.4 12.8 2 13.4 2 14.2 C2 15.2 2.8 15.8 4.2 15.8 H7.6 C9.4 15.8 10.4 16.6 10.4 18.2 C10.4 20.2 8.6 21.6 6 21.6 C3.4 21.6 1.6 20.6 1.6 19.2 C1.6 18 2.4 17.4 3.6 17.2", 1.0),
    ],
    ord("h"): "M3 2.4 V16.6 M3.2 9.8 C3.8 8.2 5 7.4 6.6 7.4 C8.2 7.4 9 8.4 9 10.2 V16.6 | M1.6 3.8 L3 2.4 M1.4 16.6 H4.6 M7.4 16.6 H10.6",
    ord("i"): f"M6 7.4 V16.6 | M3.6 7.4 H6 M3.6 16.6 H8.4 | {dot(6, 4, 1.05)}",
    ord("j"): f"M9 7.4 V18.6 C9 20.6 7.8 21.6 5.6 21.6 C4.4 21.6 3.4 21 2.9 19.6 | M6.6 7.4 H9 | {dot(9, 4, 1.05)} {dot(3, 19, 1)}",
    ord("k"): "M2 2.4 V16.6 M4.4 10.8 L9 16.6 | M0.6 3.8 L2 2.4 M8.6 7.4 L2.6 12.6 M7 7.4 H10 M0.6 16.6 H3.4 M7.4 16.6 H10.6",
    ord("l"): "M6 2.4 V16.6 | M3.6 2.4 H6 M3.6 16.6 H8.4",
    ord("m"): "M2 7.4 V16.6 M2.2 9.4 C2.6 8 3.4 7.4 4.4 7.4 C5.6 7.4 6 8.2 6 9.6 V16.6 M6.2 9.4 C6.6 8 7.4 7.4 8.4 7.4 C9.6 7.4 10 8.2 10 9.6 V16.6 | M0.6 7.4 H2 M0.5 16.6 H3 M4.8 16.6 H7.2 M9 16.6 H11.5",
    ord("n"): "M3 7.4 V16.6 M3.2 9.6 C3.8 8.1 5 7.4 6.6 7.4 C8.3 7.4 9 8.4 9 10.2 V16.6 | M1.6 8.6 L3 7.4 M1.4 16.6 H4.6 M7.4 16.6 H10.6",
    ord("o"): "M6 7.4 C3.4 7.4 2 9 2 12 C2 15 3.4 16.6 6 16.6 C8.6 16.6 10 15 10 12 C10 9 8.6 7.4 6 7.4",
    ord("p"): "M2 7.4 V21.6 M2.2 10 C2.8 8.2 4.2 7.4 6 7.4 C8.6 7.4 10 9 10 12 C10 15 8.6 16.6 6 16.6 C4.2 16.6 2.8 15.8 2.2 14.6 | M0.6 7.4 H2 M0.6 21.6 H3.4",
    ord("q"): "M10 7.4 V21.6 M9.8 10 C9.2 8.2 7.8 7.4 6 7.4 C3.4 7.4 2 9 2 12 C2 15 3.4 16.6 6 16.6 C7.8 16.6 9.2 15.8 9.8 14.6 | M8.6 21.6 H11.4",
    ord("r"): f"M3 7.4 V16.6 M3.2 9.8 C3.8 8.2 5 7.4 6.6 7.4 C7.6 7.4 8.4 7.7 9 8.2 | M1.4 7.4 H3 M1.4 16.6 H5 | {dot(8.6, 9, 1)}",
    ord("s"): "M9.4 8.2 C8.6 7.7 7.6 7.4 6.2 7.4 C4 7.4 2.8 8.3 2.8 9.6 C2.8 11 4 11.5 6.2 12 C8.4 12.5 9.6 13.2 9.6 14.6 C9.6 15.9 8.4 16.6 6 16.6 C4.6 16.6 3.4 16.3 2.4 15.7 | M9.4 7.6 V9.6 M2.4 14 V16.2",
    ord("t"): "M5 4 V14.4 C5 15.9 5.8 16.6 7.2 16.6 C8.4 16.6 9.4 16 10 15 | M1.6 7.4 H9.6",
    ord("u"): "M3 7.4 V13.8 C3 15.6 4 16.6 5.6 16.6 C7.2 16.6 8.4 15.8 8.8 14.4 M9 7.4 V16.6 | M1.4 7.4 H3 M7.4 7.4 H9 M9 16.6 H10.6",
    ord("v"): "M2 7.4 L6 16.6 | M10.2 7.4 L6 16.6 M0.6 7.4 H3.4 M8.6 7.4 H11.4",
    ord("w"): "M2 7.4 L4 16.6 M5.6 7.4 L8 16.6 | M4 16.6 L5.8 10.8 M8 16.6 L10.4 7.4 M0.5 7.4 H7 M8.8 7.4 H11.5",
    ord("x"): "M2.4 7.4 L9.6 16.6 | M9.4 7.4 L2.6 16.6 M0.6 7.4 H4 M8.2 7.4 H11.4 M0.6 16.6 H3.6 M8 16.6 H11.4",
    ord("y"): f"M2 7.4 L6.1 17.2 | M10.2 7.4 L6 17.4 C5.4 19 4.6 20.4 3.2 21 M0.6 7.4 H3.4 M8.6 7.4 H11.4 | {dot(2.6, 20.8, 0.95)}",
    ord("z"): "M9.2 7.4 L2.8 16.6 | M1.6 7.4 H9.8 M1.6 7.4 V9.4 M2 16.6 H10.2 V14.4",
    # Latin-1 punctuation and symbols.
    0xA1: turned(f"M6 2.4 V12.2 | | {dot(6, 15.8, 1.05)}"),
    0xA2: "M9.4 9 C8.6 8 7.6 7.4 6.2 7.4 C3.6 7.4 2.2 9 2.2 11.8 C2.2 14.6 3.6 16.2 6.2 16.2 C7.6 16.2 8.6 15.6 9.4 14.6 M7.6 3.4 L3.4 18.8",
    0xA3: f"M9.4 4.6 C9 3.2 8 2.4 6.6 2.4 C4.8 2.4 3.8 3.6 3.8 5.6 V13.6 C3.8 15 3.2 16 2 16.6 H10.4 V14.6 | M2 9.4 H7.4 | {bar(2, 15.4, 10.4, 17)}",
    0xA4: "M6 7.6 C4 7.6 2.8 8.8 2.8 10.6 C2.8 12.4 4 13.6 6 13.6 C8 13.6 9.2 12.4 9.2 10.6 C9.2 8.8 8 7.6 6 7.6 | M3.6 8.2 L1.8 6.4 M8.4 8.2 L10.2 6.4 M3.6 13 L1.8 14.8 M8.4 13 L10.2 14.8",
    0xA5: "M2.2 3.4 L6 10 V16.6 | M9.8 3.4 L6 10 M0.7 3.4 H3.6 M8.6 3.4 H11.3 M3.6 16.6 H8.4 M2.8 10.5 H9.2 M2.8 12.6 H9.2",
    0xA6: "M6 2 V9.6 M6 13.4 V22",
    0xA7: "M9.4 4 C8.6 3 7.6 2.4 6.2 2.4 C4.2 2.4 3 3.4 3 4.8 C3 6.2 4.2 7 6.4 7.8 C8.6 8.6 9.6 9.6 9.6 11 C9.6 12.2 8.8 13 7.4 13.4 M2.6 16 C3.4 17 4.4 17.6 5.8 17.6 C7.8 17.6 9 16.6 9 15.2 C9 13.8 7.8 13 5.6 12.2 C3.4 11.4 2.4 10.4 2.4 9 C2.4 7.8 3.2 7 4.6 6.6",
    0xA8: f"| | {dot(4, 1.2, 0.95)} {dot(8, 1.2, 0.95)}",
    0xA9: [
        ("M6 3.4 C8.8 3.4 10.8 5.6 10.8 10 C10.8 14.4 8.8 16.6 6 16.6 C3.2 16.6 1.2 14.4 1.2 10 C1.2 5.6 3.2 3.4 6 3.4", 0.55),
        ("M8.2 8 C7.8 7.2 7 6.8 6.2 6.8 C4.8 6.8 3.9 8 3.9 10 C3.9 12 4.8 13.2 6.2 13.2 C7 13.2 7.8 12.8 8.2 12", 0.75),
    ],
    0xAB: "M5.8 8 L2.6 12 L5.8 16 M9.6 8 L6.4 12 L9.6 16",
    0xAC: f"M9.8 10.4 V13.4 | | {bar(1.4, 9, 10.6, 10.8)}",
    0xAD: f"| | {bar(1.4, 11.1, 10.6, 12.9)}",
    0xAE: [
        ("M6 3.4 C8.8 3.4 10.8 5.6 10.8 10 C10.8 14.4 8.8 16.6 6 16.6 C3.2 16.6 1.2 14.4 1.2 10 C1.2 5.6 3.2 3.4 6 3.4", 0.55),
        ("M4.6 13.2 V6.8 H6.6 C7.8 6.8 8.4 7.6 8.4 8.6 C8.4 9.6 7.8 10.4 6.6 10.4 H4.6 M6.6 10.4 L8.6 13.2", 0.75),
    ],
    0xAF: f"| | {bar(1.4, 0.4, 10.6, 2)}",
    0xB0: [(transform_path("M6 2.4 C4.6 2.4 3.6 3.4 3.6 4.8 C3.6 6.2 4.6 7.2 6 7.2 C7.4 7.2 8.4 6.2 8.4 4.8 C8.4 3.4 7.4 2.4 6 2.4", 1, 1, -1.4, 0.6), 0.75)],
    0xB1: f"M6 6 V13.8 | | {bar(1.4, 9, 10.6, 10.8)} {bar(1.4, 15.2, 10.6, 17)}",
    0xB4: "M5.2 2.8 L7.4 0.9",
    0xB5: "M3 7.4 V22 M3 13.8 C3 15.6 4 16.6 5.6 16.6 C7.2 16.6 8.4 15.8 8.8 14.4 M9 7.4 V16.6 | M1.4 7.4 H3 M7.4 7.4 H9 M9 16.6 H10.6",
    0xB6: "M6.6 3.4 V17 M9 3.4 V17 | M3.6 3.4 H9.8 | M6.6 3 H4 C2.4 3 1.4 4.4 1.4 6.2 C1.4 8 2.4 9.4 4 9.4 H6.6 Z",
    0xB7: f"| | {dot(6, 11.6, 1.2)}",
    0xB8: "M6.2 16.8 V17.6 C7.6 17.8 8.2 18.4 8.2 19.4 C8.2 20.4 7.2 21.2 5.2 21",
    0xBB: "M2.4 8 L5.6 12 L2.4 16 M6.2 8 L9.4 12 L6.2 16",
    0xBF: turned(f"M2.6 5.4 C2.8 3.4 4.2 2.4 6 2.4 C8 2.4 9.2 3.6 9.2 5.4 C9.2 7.4 8.2 8.4 7 9.6 C5.6 11 5 11.6 5 12.6 | | {dot(5, 15.8, 1.05)}"),
    0xC6: "M6 3.4 V16.6 | M4.4 3.4 H10.6 V5.6 M5.6 3.4 L1.8 16.6 M0.6 16.6 H3.2 M6 9.6 H9.2 M9.2 8.4 V10.8 M4.6 16.6 H11.4 V14.4 M3 11.6 H6",
    0xD0: f"M2 3.4 V16.6 M2 3.4 H5.4 C8.6 3.4 10 5.6 10 10 C10 14.4 8.6 16.6 5.4 16.6 H2 | M0.7 3.4 H2 M0.7 16.6 H2 | {bar(0.4, 9.1, 4.6, 10.9)}",
    0xD7: "M2.8 8.2 L9.2 15 M9.2 8.2 L2.8 15",
    0xD8: "M6 3.4 C3.4 3.4 2 5.6 2 10 C2 14.4 3.4 16.6 6 16.6 C8.6 16.6 10 14.4 10 10 C10 5.6 8.6 3.4 6 3.4 | M2 17 L10 2.6",
    0xDE: "M3 3.4 V16.6 M3 6.4 H6.4 C8.8 6.4 10 7.6 10 9.8 C10 12 8.8 13.2 6.4 13.2 H3 | M1.4 3.4 H4.6 M1.4 16.6 H4.6",
    0xDF: "M3 16.6 V5.6 C3 3.6 4.2 2.4 5.8 2.4 C7.4 2.4 8.4 3.4 8.4 5 C8.4 6.6 7.4 7.4 6 8.2 V9.4 C6 10.4 7 11 8.2 11.8 C9.4 12.6 10 13.4 10 14.4 C10 15.8 9 16.6 7.4 16.6 C6.6 16.6 6 16.4 5.4 16 | M1.4 16.6 H3",
    0xE6: [
        ("M1.8 8.6 C2.4 7.8 3.2 7.4 4.2 7.4 C5.4 7.4 6 8.2 6 9.6 V14 C6 15.8 5.2 16.6 3.8 16.6 C2.4 16.6 1.4 15.8 1.4 14.4 C1.4 12.8 2.6 11.8 6 11.8 H10.6 C10.6 8.8 9.6 7.4 8.2 7.4 C6.8 7.4 6 8.6 6 10.8 V13 C6 15.4 7 16.6 8.4 16.6 C9.4 16.6 10.2 16.2 10.8 15.4", 0.8),
    ],
    0xF0: "M6 8.4 C3.4 8.4 2 10 2 12.6 C2 15.2 3.4 16.6 6 16.6 C8.6 16.6 10 15.2 10 12.4 C10 8.4 8.4 5 5 2.4 | M3.2 6.4 L8.8 3",
    0xF7: f"| | {bar(1.4, 11.1, 10.6, 12.9)} {dot(6, 8, 1.1)} {dot(6, 16, 1.1)}",
    0xF8: "M6 7.4 C3.4 7.4 2 9 2 12 C2 15 3.4 16.6 6 16.6 C8.6 16.6 10 15 10 12 C10 9 8.6 7.4 6 7.4 | M1.8 17 L10.2 7",
    0xFE: "M2 2.4 V21.6 M2.2 10 C2.8 8.2 4.2 7.4 6 7.4 C8.6 7.4 10 9 10 12 C10 15 8.6 16.6 6 16.6 C4.2 16.6 2.8 15.8 2.2 14.6 | M0.6 2.4 H2 M0.6 21.6 H3.4",
}

# Bases for marked i and j, which drop their dots.
DOTLESS = {
    "i": "M6 7.4 V16.6 | M3.6 7.4 H6 M3.6 16.6 H8.4",
    "j": f"M9 7.4 V18.6 C9 20.6 7.8 21.6 5.6 21.6 C4.4 21.6 3.4 21 2.9 19.6 | M6.6 7.4 H9 | {dot(3, 19, 1)}",
}

# Combining marks as (template, cap top, cap bottom, lowercase top,
# lowercase bottom), where a template is a drawing to format or a function
# of the mark's top and bottom. Cap marks live in the 0.7-2.0 band above the y=3 cap
# line; lowercase marks live in the 4.6-5.9 band above the y=7 x-height line.
COMBINING_MARKS = {
    "\u0300": ("M4.6 {top} L7.4 {bottom}", 0.8, 2.0, 4.4, 5.8),
    "\u0301": ("M4.6 {bottom} L7.4 {top}", 0.8, 2.0, 4.4, 5.8),
    "\u0302": ("M3.4 {bottom} L6 {top} L8.6 {bottom}", 0.8, 2.0, 4.4, 5.8),
    "\u0303": ("M3.2 {bottom} C3.6 {top} 4.4 {top} 6 {mid} C7.6 {low} 8.4 {low} 8.8 {top}", 0.8, 2.0, 4.4, 5.8),
    "\u0308": (lambda top, bottom: f"| | {dot(4, (top + bottom) / 2, 0.95)} {dot(8, (top + bottom) / 2, 0.95)}", 0.8, 2.0, 4.4, 5.8),
    "\u030a": ("| M6 {top} C4.6 {top} 4.6 {bottom} 6 {bottom} C7.4 {bottom} 7.4 {top} 6 {top}", 0.2, 2.2, 3.8, 5.8),
    "\u0327": ("M6.2 16.8 V17.6 C7.6 17.8 8.2 18.4 8.2 19.4 C8.2 20.4 7.2 21.2 5.2 21", 0, 0, 0, 0),
}

# A drawn element is (path, weight, pen). Weight scales the pen; the pen is
# "broad" (a flat nib held horizontally, so verticals are heavy and
# horizontals are hairlines, like the original's 2px stems and 1px joins,
# with flat ends cut square across the stroke),
# "hair" (a plain monoline hairline), or "fill" (the closed path is filled).
Element = tuple[str, float, str]
PENS = {"broad", "hair", "fill"}

# Fraction of the stem weight carried by the round hairline core of the
# broad nib; the rest is the nib's horizontal sweep.
HAIRLINE = 0.47
NIB_STEPS = 17

def normalize_elements(value) -> list[Element]:
    """Expand a glyph drawing into elements.

    A string is "broad strokes | hairlines | fills", where the later parts
    are optional. A list holds (path, weight) or (path, weight, pen) items.
    """
    if isinstance(value, str):
        return [
            (part.strip(), 1.0, pen)
            for part, pen in zip(value.split("|"), ("broad", "hair", "fill"))
            if part.strip()
        ]
    elements = []
    for item in value:
        path, weight, pen = (*item, "broad") if len(item) == 2 else item
        if pen not in PENS:
            raise ValueError(f"unknown pen {pen!r}")
        elements.append((path, weight, pen))
    return elements


# The regular digits sit on the y=17 baseline, span y=3-17, and center on
# x=6. Small forms are the same drawings scaled about the baseline, with a
# lighter absolute stroke that still reads optically heavier at their size.
def small_form_source(name: str) -> list[Element]:
    return normalize_elements(MODERN_PATHS[ord(name)])


SMALL_SCALE = 0.52
SMALL_STROKE = 0.72
SUPERSCRIPT_BASELINE = 10.2
SUBSCRIPT_BASELINE = 20.4

FRACTION_SCALE = 0.42
FRACTION_STROKE = 0.68
FRACTION_SLASH = ("M3.1 17.4 L8.9 2.6", 0.85, "hair")
NUMERATOR_BASELINE = 8.9
NUMERATOR_CENTER = 3.3
DENOMINATOR_CENTER = 8.7
TENTH_SCALE = 0.34
BASELINE = 17

SUPERSCRIPT_DIGITS = {
    0xB9: "1",
    0xB2: "2",
    0xB3: "3",
    0x2070: "0",
    **{0x2074 + index: str(4 + index) for index in range(6)},
}
SUBSCRIPT_DIGITS = {0x2080 + digit: str(digit) for digit in range(10)}
VULGAR_FRACTIONS = {
    0xBC: ("1", "4"),
    0xBD: ("1", "2"),
    0xBE: ("3", "4"),
    0x2150: ("1", "7"),
    0x2151: ("1", "9"),
    0x2152: ("1", "10"),
    0x2153: ("1", "3"),
    0x2154: ("2", "3"),
    0x2155: ("1", "5"),
    0x2156: ("2", "5"),
    0x2157: ("3", "5"),
    0x2158: ("4", "5"),
    0x2159: ("1", "6"),
    0x215A: ("5", "6"),
    0x215B: ("1", "8"),
    0x215C: ("3", "8"),
    0x215D: ("5", "8"),
    0x215E: ("7", "8"),
    0x2189: ("0", "3"),
}


def small_form(
    source: str,
    scale: float,
    center_x: float,
    baseline: float,
    weight: float,
) -> list[Element]:
    return [
        (
            transform_path(
                path,
                scale,
                scale,
                center_x - 6 * scale,
                baseline - BASELINE * scale,
            ),
            element_weight * weight,
            pen,
        )
        for path, element_weight, pen in small_form_source(source)
    ]


def fraction_elements(numerator: str, denominator: str | None) -> list[Element]:
    elements = [
        element
        for digit in numerator
        for element in small_form(
            digit, FRACTION_SCALE, NUMERATOR_CENTER, NUMERATOR_BASELINE, FRACTION_STROKE
        )
    ]
    elements.append(FRACTION_SLASH)
    if denominator is None:
        return elements
    if len(denominator) == 1:
        centers = [DENOMINATOR_CENTER]
        scale = FRACTION_SCALE
    else:
        centers = [7.0, 9.7]
        scale = TENTH_SCALE
    for digit, center in zip(denominator, centers, strict=True):
        elements.extend(small_form(digit, scale, center, BASELINE, FRACTION_STROKE))
    return elements


def derived_paths() -> dict[int, list[Element]]:
    derived: dict[int, list[Element]] = {}
    for codepoint, digit in SUPERSCRIPT_DIGITS.items():
        derived[codepoint] = small_form(
            digit, SMALL_SCALE, 6, SUPERSCRIPT_BASELINE, SMALL_STROKE
        )
    for codepoint, digit in SUBSCRIPT_DIGITS.items():
        derived[codepoint] = small_form(
            digit, SMALL_SCALE, 6, SUBSCRIPT_BASELINE, SMALL_STROKE
        )
    for codepoint, (numerator, denominator) in VULGAR_FRACTIONS.items():
        derived[codepoint] = fraction_elements(numerator, denominator)
    derived[0x215F] = fraction_elements("1", None)
    derived[0x2044] = [("M2.4 18.2 L9.6 1.8", 1.0, "hair")]
    # Ordinal indicators are the lowercase letters scaled to superscript size,
    # underlined as in the original.
    for codepoint, letter in ((0xAA, "a"), (0xBA, "o")):
        derived[codepoint] = [
            *small_form(letter, 0.62, 6, 10.8, SMALL_STROKE),
            (bar(2.4, 12.6, 9.6, 14.2), 1.0, "fill"),
        ]
    return derived


DERIVED_PATHS = derived_paths()


def modern_elements(codepoint: int) -> list[Element] | None:
    direct = MODERN_PATHS.get(codepoint)
    if direct is not None:
        return normalize_elements(direct)
    derived = DERIVED_PATHS.get(codepoint)
    if derived is not None:
        return derived
    decomposition = unicodedata.normalize("NFD", chr(codepoint))
    if len(decomposition) < 2 or ord(decomposition[0]) not in MODERN_PATHS:
        return None
    if any(mark not in COMBINING_MARKS for mark in decomposition[1:]):
        return None

    base = MODERN_PATHS[ord(decomposition[0])]
    if decomposition[0] in "ij" and any(mark != "\u0327" for mark in decomposition[1:]):
        base = DOTLESS[decomposition[0]]
    uppercase = decomposition[0].isupper()
    elements = normalize_elements(base)
    for mark in decomposition[1:]:
        template, cap_top, cap_bottom, lower_top, lower_bottom = COMBINING_MARKS[mark]
        top = cap_top if uppercase else lower_top
        bottom = cap_bottom if uppercase else lower_bottom
        if callable(template):
            drawing = template(top, bottom)
        else:
            drawing = template.format(
                top=number(top),
                bottom=number(bottom),
                low=number(bottom + 0.45),
                mid=number((top + bottom) / 2),
            )
        elements.extend(normalize_elements(drawing))
    return elements


def parse_source() -> dict[int, tuple[str, ...]]:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    glyphs: dict[int, tuple[str, ...]] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"U\+([0-9A-F]{4,6})(?: .*)?", line)
        if not match:
            raise ValueError(f"{SOURCE}:{index}: invalid glyph header")
        codepoint = int(match.group(1), 16)
        glyphs[codepoint] = tuple(lines[index : index + HEIGHT])
        index += HEIGHT
    return glyphs


def design_svg(elements: list[Element], stroke_width: float, color: str = "black") -> str:
    """Draw elements as SVG markup in the 12 by 22 cell."""
    hair = stroke_width * HAIRLINE
    nib = stroke_width - hair
    parts = []
    for path, weight, pen in elements:
        if pen == "fill":
            parts.append(f'<path d="{path}" fill="{color}" stroke="none"/>')
            continue
        width = number(hair * weight)
        if pen == "hair":
            parts.append(f'<path d="{path}" stroke-width="{width}"/>')
            continue
        # The broad nib is swept as a row of hairline copies spanning it.
        for step in range(NIB_STEPS):
            offset = (step / (NIB_STEPS - 1) - 0.5) * nib * weight
            parts.append(
                f'<path d="{path}" stroke-width="{width}" stroke-linecap="butt" '
                f'transform="translate({number(offset)} 0)"/>'
            )
    return (
        f'<g stroke="{color}" stroke-linecap="square" stroke-linejoin="round" '
        f'fill="none">{"".join(parts)}</g>'
    )


def render_design(
    rsvg: str,
    magick: str,
    elements: list[Element],
    stroke_width: float,
) -> bytes:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="192" height="352" '
        'viewBox="0 0 12 22">'
        '<rect width="12" height="22" fill="white"/>'
        f"{design_svg(elements, stroke_width)}</svg>"
    )
    png = subprocess.run(
        [rsvg, "--format", "png"],
        input=svg.encode(),
        capture_output=True,
        check=True,
    ).stdout
    return subprocess.run(
        [magick, "png:-", "-threshold", "50%", "pbm:-"],
        input=png,
        capture_output=True,
        check=True,
    ).stdout


def trace(
    potrace: str,
    rsvg: str,
    magick: str,
    codepoint: int,
    rows: tuple[str, ...],
    stroke_width: float,
) -> str:
    if not any("#" in row for row in rows):
        return ""

    elements = modern_elements(codepoint)
    if elements is None:
        raise ValueError(
            f"U+{codepoint:04X} is visible but has no designed vector outline"
        )

    result = subprocess.run(
        [
            potrace,
            "--backend",
            "svg",
            "--output",
            "-",
            "--tight",
            "--unit",
            "4",
            "--turdsize",
            "0",
            "--alphamax",
            "0.8",
            "--opttolerance",
            "0.15",
            "--turnpolicy",
            "minority",
        ],
        input=render_design(rsvg, magick, elements, stroke_width),
        capture_output=True,
        check=True,
    )
    paths = re.findall(r'<path d="([\s\S]*?)"/>', result.stdout.decode())
    if not paths:
        raise ValueError("Potrace produced no SVG path for a visible glyph")
    return " ".join(
        re.sub(r"\s+", " ", path).strip()
        for path in paths
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--potrace", default="potrace", help="path to Potrace 1.16")
    parser.add_argument("--rsvg", default="rsvg-convert", help="path to librsvg's rsvg-convert")
    parser.add_argument("--magick", default="magick", help="path to ImageMagick")
    parser.add_argument("--stroke-width", type=float, default=STEM)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output

    version = subprocess.run(
        [args.potrace, "--version"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()[0]
    paths = {
        f"{codepoint:04X}": trace(
            args.potrace,
            args.rsvg,
            args.magick,
            codepoint,
            rows,
            args.stroke_width,
        )
        for codepoint, rows in parse_source().items()
    }
    payload = {
        "format": 1,
        "tracer": version,
        "settings": {
            "construction": "serifed centerlines drawn with a horizontal broad nib",
            "supersample": 16,
            "stroke_width": args.stroke_width,
            "hairline": HAIRLINE,
            "unit": 4,
            "alphamax": 0.8,
            "opttolerance": 0.15,
            "turnpolicy": "minority",
        },
        "paths": paths,
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    label = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
    print(f"Wrote {label} ({len(paths)} glyphs)")


if __name__ == "__main__":
    main()
