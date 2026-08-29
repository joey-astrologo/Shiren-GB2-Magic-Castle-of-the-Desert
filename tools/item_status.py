#!/usr/bin/env python3
"""Localize GB2's composite cracked-Bracelet status marker.

The item formatter appends prefixed glyph ``F2 1E`` to cracked Bracelets.  The
stock 16x10 bitmap spells Japanese ``(hibi)``/``(crack)`` rather than drawing a
language-neutral icon, so retaining it beside an English item name produces the
mixed-language mark reported by playtesting.  This installer replaces only that
bitmap with a compact ``(Cr)`` marker and preserves its native 15-pixel width
metadata and two-slice renderer contract.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from cartridge import fix_checksums
import font


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET = ROOT / "assets" / "graphics" / "item_status_symbols.json"

CRACKED_CODE = bytes.fromhex("F21E")
CRACKED_WIDTHS = bytes.fromhex("0F06")
ORIGINAL_BITMAP = bytes.fromhex(
    "5FE0BFC1FFA2FFA2FFBBFFA2EEB3DDBBBFC05FE0"
    "D7384FF8FFA8FF08FF88FF08FF08FF88EF18D738"
)
BACKGROUND_COLOR = 1
INK_COLOR = 3


class ItemStatusError(ValueError):
    """The status-symbol asset or target ROM violates a build invariant."""


def _bitmap_offset():
    location = font.glyph_location(CRACKED_CODE)
    return font.banked_offset(location.bank, location.address)


def _width_offset():
    location = font.glyph_location(CRACKED_CODE)
    return font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS) + location.width_index


def encode_2bpp(rows):
    """Encode ten 16-pixel rows as the renderer's two sequential 8x10 slices."""
    if (
        not isinstance(rows, list)
        or len(rows) != font.KANJI_HEIGHT
        or any(
            not isinstance(row, str)
            or len(row) != 16
            or set(row) - {".", "#"}
            for row in rows
        )
    ):
        raise ItemStatusError("status glyph must contain ten 16-column .# rows")
    out = bytearray()
    for piece in range(2):
        for row in rows:
            cells = row[piece * 8:(piece + 1) * 8]
            ink = sum(0x80 >> x for x, pixel in enumerate(cells) if pixel == "#")
            out += bytes((0xFF, ink))
    return bytes(out)


def load_asset(path=DEFAULT_ASSET):
    """Load and validate the reviewed cracked-marker raster."""
    path = Path(path).resolve()
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ItemStatusError("cannot load status-symbol asset %s: %s" % (path, exc)) from exc
    if source.get("format") != "shiren-gb2-prefixed-status-symbols-v1":
        raise ItemStatusError("unsupported status-symbol format %r" % source.get("format"))
    if set(source.get("symbols", {})) != {"cracked"}:
        raise ItemStatusError("status-symbol asset must define only cracked")
    symbol = source["symbols"]["cracked"]
    if symbol.get("code", "").upper() != CRACKED_CODE.hex().upper():
        raise ItemStatusError("cracked marker must own F21E")
    if symbol.get("label") != "(Cr)":
        raise ItemStatusError("cracked marker label must be (Cr)")
    rows = symbol.get("rows")
    bitmap = encode_2bpp(rows)
    return path, tuple(rows), bitmap


def owned_ranges():
    """Return the exclusive ROM byte range owned by this installer."""
    start = _bitmap_offset()
    return ((start, start + len(ORIGINAL_BITMAP)),)


def install(rom, asset_path=DEFAULT_ASSET, checksums=True):
    """Return ``rom`` with the English cracked-Bracelet marker installed."""
    _path, _rows, bitmap = load_asset(asset_path)
    out = bytearray(rom)
    at = _bitmap_offset()
    current = bytes(out[at:at + len(ORIGINAL_BITMAP)])
    if current not in (ORIGINAL_BITMAP, bitmap):
        raise ItemStatusError("unexpected F21E source bitmap")
    width_at = _width_offset()
    if bytes(out[width_at:width_at + 2]) != CRACKED_WIDTHS:
        raise ItemStatusError("unexpected F21E/F21F width metadata")
    out[at:at + len(bitmap)] = bitmap
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, asset_path=DEFAULT_ASSET):
    """Return the source/asset contract used by fixtures and documentation."""
    path, rows, bitmap = load_asset(asset_path)
    localized = install(rom, asset_path=path, checksums=False)
    glyph = font.read_glyph(localized, CRACKED_CODE)
    return {
        "asset": str(path.relative_to(ROOT)),
        "asset_sha256": sha256(path.read_bytes()).hexdigest(),
        "code": CRACKED_CODE.hex().upper(),
        "label": "(Cr)",
        "width": glyph.width,
        "renderer_advance": sum(
            8 if value >= 10 else value
            for value in CRACKED_WIDTHS
        ),
        "rows": list(rows),
        "original_bitmap": ORIGINAL_BITMAP.hex().upper(),
        "localized_bitmap": bitmap.hex().upper(),
        "localized_bitmap_sha256": sha256(bitmap).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="input Shiren GB2 ROM")
    parser.add_argument("output", help="output ROM")
    parser.add_argument("--asset", default=str(DEFAULT_ASSET))
    args = parser.parse_args(argv)
    try:
        source = Path(args.rom).read_bytes()
        output = install(source, args.asset)
    except (OSError, ItemStatusError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print("marker     : (Cr) at F21E")
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
