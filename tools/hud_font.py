#!/usr/bin/env python3
"""Install the approved decimal digits and slash in GB2's dungeon HUD atlas.

The top status bar packs two four-pixel glyphs into each 8x8 2bpp tile. Decimal
digits 0-9 occupy the first five tiles at bank 3:$5742, while the slash occupies
tile ten. This patch replaces only those discontiguous cells; hexadecimal A-F,
Lv/Hp, meter artwork, and reserved tiles remain native.
"""
import argparse
import json
from pathlib import Path
import sys

from cartridge import fix_checksums


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "assets" / "fonts" / "hud_digits.json"

BANK_SIZE = 0x4000
HUD_BANK = 3
HUD_ADDRESS = 0x5742
HUD_OFFSET = HUD_BANK * BANK_SIZE + HUD_ADDRESS - 0x4000
TILE_BYTES = 16
DIGIT_TILES = 5
DIGIT_BYTES = DIGIT_TILES * TILE_BYTES
DIGITS = "0123456789"
SLASH_TILE = 10
SLASH_OFFSET = HUD_OFFSET + SLASH_TILE * TILE_BYTES
BACKGROUND_COLOR = 1
INK_COLOR = 3
APPROVED_SOURCE_SHA256 = (
    "cd93f5115d23fae3d5bef80ce74e2f2544d08473498e5bcb41c91cec9253e00d"
)
ORIGINAL_DIGIT_BYTES = bytes.fromhex(
    "ff00ffe4ffa4ffa4ffa4ffa4ffe4ff00"
    "ff00ffeeffa2ff26ff42ff82ffeeff00"
    "ff00ffaeffa8ffaeffe2ff22ff2eff00"
    "ff00ffeeff82ffe2ffa2ffa2ffe2ff00"
    "ff00ffeeffaaffeaffaeffa2ffeeff00"
)
ORIGINAL_SLASH_BYTES = bytes.fromhex("ff00ff00ff06ff0cff18ff30ff60ff00")


class HudFontError(ValueError):
    """The approved HUD digits or their guarded ROM target are invalid."""


def load_approved(path=DEFAULT_SPEC):
    """Load and validate the reviewed 4x8 digit rasters."""
    path = Path(path)
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HudFontError("cannot load HUD digit spec %s: %s" % (path, exc)) from exc
    if spec.get("schema") != "shiren-gb2-hud-digits-v1":
        raise HudFontError("unsupported HUD digit schema %r" % spec.get("schema"))
    if spec.get("source", {}).get("sha256") != APPROVED_SOURCE_SHA256:
        raise HudFontError("HUD digit source identity does not match the approved image")
    glyphs = spec.get("glyphs", {})
    if set(glyphs) != set(DIGITS):
        raise HudFontError("HUD digit spec must define exactly 0-9")
    for character in DIGITS:
        rows = glyphs[character]
        if (
            not isinstance(rows, list)
            or len(rows) != 8
            or any(
                not isinstance(row, str)
                or len(row) != 4
                or set(row) - {".", "#"}
                for row in rows
            )
        ):
            raise HudFontError("HUD digit %s must contain eight 4-column .# rows" % character)
    slash = spec.get("slash")
    if (
        not isinstance(slash, list)
        or len(slash) != 8
        or any(
            not isinstance(row, str)
            or len(row) != 8
            or set(row) - {".", "#"}
            for row in slash
        )
    ):
        raise HudFontError("HUD slash must contain eight 8-column .# rows")
    return spec


def approved_digit_bytes(spec=None):
    """Pack the ten approved 4x8 glyphs into five native 8x8 2bpp tiles."""
    glyphs = (spec or load_approved())["glyphs"]
    out = bytearray()
    for left, right in zip(DIGITS[::2], DIGITS[1::2]):
        for y in range(8):
            pixels = glyphs[left][y] + glyphs[right][y]
            low = high = 0
            for x, pixel in enumerate(pixels):
                color = INK_COLOR if pixel == "#" else BACKGROUND_COLOR
                bit = 7 - x
                low |= (color & 1) << bit
                high |= ((color >> 1) & 1) << bit
            out += bytes((low, high))
    return bytes(out)


def approved_slash_bytes(spec=None):
    """Encode the approved 8x8 slash in the native background/ink palette."""
    rows = (spec or load_approved())["slash"]
    out = bytearray()
    for row in rows:
        low = high = 0
        for x, pixel in enumerate(row):
            color = INK_COLOR if pixel == "#" else BACKGROUND_COLOR
            bit = 7 - x
            low |= (color & 1) << bit
            high |= ((color >> 1) & 1) << bit
        out += bytes((low, high))
    return bytes(out)


def digit_range():
    """Return the exclusive ROM range occupied by decimal digit tiles."""
    return HUD_OFFSET, HUD_OFFSET + DIGIT_BYTES


def slash_range():
    """Return the exclusive ROM range occupied by the slash tile."""
    return SLASH_OFFSET, SLASH_OFFSET + TILE_BYTES


def owned_ranges():
    """Return the two discontiguous HUD ranges owned by this installer."""
    return digit_range(), slash_range()


def install(rom, spec=None, checksums=True):
    """Return ``rom`` with only the approved HUD digits and slash changed."""
    spec = spec or load_approved()
    out = bytearray(rom)
    targets = (
        ("digit", digit_range(), ORIGINAL_DIGIT_BYTES, approved_digit_bytes(spec)),
        ("slash", slash_range(), ORIGINAL_SLASH_BYTES, approved_slash_bytes(spec)),
    )
    for name, (start, end), original, replacement in targets:
        current = bytes(out[start:end])
        if current not in (original, replacement):
            raise HudFontError("unexpected HUD %s bytes" % name)
        out[start:end] = replacement
    if checksums:
        fix_checksums(out)
    return bytes(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="input Shiren GB2 ROM")
    parser.add_argument("output", help="output ROM")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="approved digit JSON")
    args = parser.parse_args(argv)
    try:
        source = Path(args.rom).read_bytes()
        output = install(source, load_approved(args.spec))
    except (OSError, HudFontError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print("HUD glyphs : 0-9 and slash (%d packed digit tiles)" % DIGIT_TILES)
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
