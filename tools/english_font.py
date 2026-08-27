#!/usr/bin/env python3
"""Bake Thin Pixel-7 GB Compact into GB2's native proportional font tables.

GB2 already has the renderer we need.  Its one-byte font stores 8x8 2bpp cells at
3:$4842 and reads the horizontal advance from the first page of the table at 3:$4442.
This installer changes only the 78 slots owned by ``english.ENGLISH_CODES``, then fixes
the cartridge checksums.  No renderer code is replaced.
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
INK_COLOR = 3


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


def encode_2bpp(rows):
    """Convert eight ``.#`` rows to GB2's background-1/foreground-3 tile format."""
    if (
        not isinstance(rows, list)
        or len(rows) != 8
        or any(
            not isinstance(row, str) or len(row) != 8 or set(row) - {".", "#"}
            for row in rows
        )
    ):
        raise FontError("glyph must contain eight 8-column .# rows")
    out = bytearray()
    for row in rows:
        ink = sum(0x80 >> x for x, pixel in enumerate(row) if pixel == "#")
        # Color 1 is low=1/high=0 and color 3 is low=1/high=1.  Therefore the
        # low plane is solid and the reviewed one-bit raster is the high plane.
        out += bytes((0xFF, ink))
    return bytes(out)


class ApprovedFont:
    def __init__(self, spec_path, source_path, name, rows, advances):
        self.spec_path = spec_path
        self.source_path = source_path
        self.name = name
        self.rows = rows
        self.advances = advances
        self.glyphs = {character: encode_2bpp(rows[character]) for character in rows}

    def text_width(self, text):
        return english.text_width(text, self.advances)


def load_approved(spec_path=DEFAULT_SPEC):
    """Verify and load the frozen GB1-approved font assets."""
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
        encode_2bpp(rows[character])
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
        spec_path, source_path, spec["name"], dict(rows), advances
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
    args = parser.parse_args(argv)
    source = Path(args.rom).read_bytes()
    try:
        approved = load_approved(args.font_spec)
        output = install(source, approved)
    except FontError as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    changed = sum(before != after for before, after in zip(source, output))
    print("font       : %s" % approved.name)
    print("glyphs     : %d" % len(english.ENGLISH_CODES))
    print("changed    : %d byte(s), including global checksum" % changed)
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
