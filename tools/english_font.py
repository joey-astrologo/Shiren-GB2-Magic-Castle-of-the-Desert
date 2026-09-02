#!/usr/bin/env python3
"""Bake a selected Thin Pixel-7 GB Compact style into GB2's font tables.

GB2 already has the renderer we need.  Its one-byte font stores 8x8 2bpp cells at
3:$4842 and reads the horizontal advance from the first page of the table at 3:$4442.
This installer changes only the 79 slots owned by ``english.ENGLISH_CODES``, then fixes
the cartridge checksums. The classic style retains the original black-only adapted
raster. The shadowed style adds the approved color-2 shadow at ``+1,+1`` before its
unchanged color-3 ink is redrawn on top. A disconnected visible bottom shadow pixel moves
left for ``, `g`, `j`, and `y`. No renderer code is replaced.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from cartridge import fix_checksums
import english
import font


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "assets" / "fonts" / "thin_pixel_7_compact.json"

BACKGROUND_COLOR = 1
SHADOW_COLOR = 2
INK_COLOR = 3
CLASSIC_STYLE = "classic"
SHADOWED_STYLE = "shadowed"
FONT_STYLES = (CLASSIC_STYLE, SHADOWED_STYLE)
SHADOW_OFFSET = (1, 1)
BOTTOM_ORPHAN_SHIFT = (-1, 0)
CELL_SIZE = (8, 8)


class FontError(ValueError):
    """The approved font assets or target ROM violate a build invariant."""


def _digest(path):
    return sha256(path.read_bytes()).hexdigest()


def _source_path(spec, spec_path):
    declared = Path(spec["source"]["file"])
    return declared if declared.is_absolute() else ROOT / declared


def ink_span(rows):
    columns = [
        x
        for x in range(8)
        if any(row[x] == "#" for row in rows)
    ]
    return (min(columns), max(columns)) if columns else None


def _validate_rows(rows):
    if (
        not isinstance(rows, (list, tuple))
        or len(rows) != CELL_SIZE[1]
        or any(
            not isinstance(row, str)
            or len(row) != CELL_SIZE[0]
            or set(row) - {".", "#"}
            for row in rows
        )
    ):
        raise FontError("glyph must contain eight 8-column .# rows")


def _move_bottom_orphan_left(pixels, ink):
    """Join one disconnected visible shadow pixel on a bottom-clipped glyph."""
    _width, height = CELL_SIZE
    if not any(y + SHADOW_OFFSET[1] >= height for _x, y in ink):
        return False

    bottom = pixels[height - 1]
    shadow = [x for x, color in enumerate(bottom) if color == SHADOW_COLOR]
    if not shadow:
        return False
    rightmost = max(shadow)
    if (
        rightmost < 2
        or bottom[rightmost - 1] != BACKGROUND_COLOR
        or bottom[rightmost - 2] not in (SHADOW_COLOR, INK_COLOR)
    ):
        return False

    bottom[rightmost] = BACKGROUND_COLOR
    bottom[rightmost + BOTTOM_ORPHAN_SHIFT[0]] = SHADOW_COLOR
    return True


def shadow_pixels(rows):
    """Return the approved background/shadow/ink color indexes for one glyph."""
    _validate_rows(rows)
    width, height = CELL_SIZE
    dx, dy = SHADOW_OFFSET
    pixels = [[BACKGROUND_COLOR] * width for _ in range(height)]
    ink = {
        (x, y)
        for y, row in enumerate(rows)
        for x, pixel in enumerate(row)
        if pixel == "#"
    }

    for x, y in ink:
        shadow_x, shadow_y = x + dx, y + dy
        if 0 <= shadow_x < width and 0 <= shadow_y < height:
            pixels[shadow_y][shadow_x] = SHADOW_COLOR
    for x, y in ink:
        pixels[y][x] = INK_COLOR

    _move_bottom_orphan_left(pixels, ink)
    return tuple(tuple(row) for row in pixels)


def glyph_pixels(rows, style=SHADOWED_STYLE):
    """Return one approved glyph in the selected visual font style."""
    if style == SHADOWED_STYLE:
        return shadow_pixels(rows)
    if style != CLASSIC_STYLE:
        raise FontError("unknown English font style %r" % style)
    _validate_rows(rows)
    return tuple(
        tuple(INK_COLOR if pixel == "#" else BACKGROUND_COLOR for pixel in row)
        for row in rows
    )


def encode_2bpp(rows, style=SHADOWED_STYLE):
    """Encode an approved background=1 English tile for one visual style."""
    out = bytearray()
    for row in glyph_pixels(rows, style=style):
        low = high = 0
        for x, color in enumerate(row):
            bit = 7 - x
            low |= (color & 1) << bit
            high |= ((color >> 1) & 1) << bit
        out += bytes((low, high))
    return bytes(out)


class ApprovedFont:
    def __init__(self, spec_path, source_path, name, rows, advances, style):
        self.spec_path = spec_path
        self.source_path = source_path
        self.name = name
        self.style = style
        self.rows = rows
        self.advances = advances
        self.glyphs = {
            character: encode_2bpp(rows[character], style=style)
            for character in rows
        }

    def text_width(self, text):
        return english.text_width(text, self.advances)


def load_approved(spec_path=DEFAULT_SPEC, style=SHADOWED_STYLE):
    """Verify and load the frozen GB1-approved font assets."""
    if style not in FONT_STYLES:
        raise FontError("unknown English font style %r" % style)
    spec_path = Path(spec_path).resolve()
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FontError("cannot load font spec %s: %s" % (spec_path, exc)) from exc
    source_path = _source_path(spec, spec_path).resolve()
    actual_hash = _digest(source_path)
    expected_hash = spec["source"]["sha256"]
    if actual_hash != expected_hash:
        raise FontError(
            "font source SHA-256 %s, approved spec requires %s"
            % (actual_hash, expected_hash)
        )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("format") != "shiren-gb-8x8-rows-v1":
        raise FontError("unsupported font source format %r" % source.get("format"))

    rows = source.get("glyphs", {})
    advances = {character: int(value) for character, value in spec["advances"].items()}
    wanted = set(english.ENGLISH_CODES)
    if set(rows) != wanted or set(advances) != wanted:
        raise FontError(
            "English glyph set mismatch; rows missing=%r extra=%r, widths missing=%r extra=%r"
            % (
                sorted(wanted - set(rows)),
                sorted(set(rows) - wanted),
                sorted(wanted - set(advances)),
                sorted(set(advances) - wanted),
            )
        )

    for character in sorted(wanted):
        encode_2bpp(rows[character], style=style)
        advance = advances[character]
        if not 1 <= advance <= 8:
            raise FontError("%r has invalid %dpx advance" % (character, advance))
        span = ink_span(rows[character])
        if span and span[1] >= advance:
            raise FontError(
                "%r inks through column %d but advances %dpx"
                % (character, span[1], advance)
            )
    return ApprovedFont(
        spec_path, source_path, spec["name"], dict(rows), advances, style
    )


def install(rom, approved=None, verify_original=True, checksums=True):
    """Return a ROM containing the approved English glyphs and native advances."""
    approved = approved or load_approved()
    if verify_original:
        try:
            font.verify_regions(rom)
        except ValueError as exc:
            raise FontError(str(exc)) from exc
    out = bytearray(rom)
    width_base = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
    glyph_base = font.banked_offset(font.SINGLE_BANK, font.SINGLE_ADDRESS)
    for character, code in english.ENGLISH_CODES.items():
        out[width_base + code] = approved.advances[character]
        start = glyph_base + code * font.SINGLE_STRIDE
        out[start:start + font.SINGLE_STRIDE] = approved.glyphs[character]
    if checksums:
        fix_checksums(out)
    return bytes(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("output", help="output ROM with the English font installed")
    parser.add_argument(
        "--font-spec", default=str(DEFAULT_SPEC), help="approved font spec JSON"
    )
    parser.add_argument(
        "--style",
        choices=FONT_STYLES,
        default=SHADOWED_STYLE,
        help="classic black-only or shadowed gray drop-shadow glyphs",
    )
    args = parser.parse_args(argv)
    source = Path(args.rom).read_bytes()
    try:
        approved = load_approved(args.font_spec, style=args.style)
        output = install(source, approved)
    except FontError as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    changed = sum(before != after for before, after in zip(source, output))
    print("font       : %s" % approved.name)
    print("style      : %s" % approved.style)
    print("glyphs     : %d" % len(english.ENGLISH_CODES))
    print("changed    : %d byte(s), including global checksum" % changed)
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
