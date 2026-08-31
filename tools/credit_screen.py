#!/usr/bin/env python3
"""Install the approved English clean-boot copyright/composer card.

The native boot driver loads ``F3:$5D00-$64FF`` verbatim into VRAM bank 1 at
``$8800``.  Its generated tilemap assigns two private 16x2-tile strips to each
Japanese name.  This installer replaces only those strips; the two native
``© 2001`` rows, map, palettes, fade, scroll, and title transition remain intact.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from cartridge import fix_checksums


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET = ROOT / "assets" / "graphics" / "credit_screen_inter.json"

BANK_SIZE = 0x4000
SOURCE_BANK = 0xF3
PLANE_ADDRESS = 0x5D00
PLANE_BYTES = 0x0800

PIXEL_VALUES = {".": 0, "d": 1, "m": 2, "#": 3}
EXPECTED_FONT_SHA256 = \
    "78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3"

STRIP_CONTRACTS = (
    {
        "name": "chunsoft",
        "text": "CHUNSOFT",
        "first_tile": "A0",
        "screen_rect": [16, 56, 144, 72],
        "rom_source": "F3:$5F00-$60FF",
        "address": 0x5F00,
        "original_sha256": (
            "152ba82ee7a2b467f63335a42428161c4d40d88a00b47276724b5b7fac8a3527"
        ),
    },
    {
        "name": "koichi_sugiyama",
        "text": "Koichi Sugiyama",
        "first_tile": "E0",
        "screen_rect": [16, 88, 144, 104],
        "rom_source": "F3:$6300-$64FF",
        "address": 0x6300,
        "original_sha256": (
            "25181d51ffc79fe7afe9acc33cc98776fbccd4b9c9ddd7022423ec495c1965e0"
        ),
    },
)


class CreditScreenError(ValueError):
    """The approved asset or native credit-plane ownership changed."""


def _offset(bank, address):
    if not 0x4000 <= address < 0x8000:
        raise CreditScreenError("switchable-bank address is outside ROMX")
    return bank * BANK_SIZE + address - 0x4000


def encode_rows(rows):
    """Encode one 128x16 four-level strip as 32 row-major 2bpp tiles."""
    if (
        not isinstance(rows, list)
        or len(rows) != 16
        or any(
            not isinstance(row, str)
            or len(row) != 128
            or set(row) - set(PIXEL_VALUES)
            for row in rows
        )
    ):
        raise CreditScreenError(
            "credit strip must contain sixteen 128-column .dm# rows"
        )

    encoded = bytearray()
    for tile_y in range(2):
        for tile_x in range(16):
            for row in range(8):
                low = high = 0
                cells = rows[tile_y * 8 + row][tile_x * 8:(tile_x + 1) * 8]
                for column, symbol in enumerate(cells):
                    value = PIXEL_VALUES[symbol]
                    bit = 7 - column
                    low |= (value & 1) << bit
                    high |= ((value >> 1) & 1) << bit
                encoded.extend((low, high))
    return bytes(encoded)


def load_asset(path=DEFAULT_ASSET):
    path = Path(path).resolve()
    try:
        asset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CreditScreenError("cannot load credit asset %s: %s" % (path, exc)) from exc
    if asset.get("format") != "shiren-gb2-credit-screen-v1":
        raise CreditScreenError("unsupported credit-screen asset format")
    if asset.get("content") != [
        "© 2001",
        "CHUNSOFT",
        "© 2001",
        "Koichi Sugiyama",
    ]:
        raise CreditScreenError("credit-screen content changed without approval")
    font = asset.get("font", {})
    if (
        font.get("family") != "Inter"
        or font.get("style") != "SemiBold"
        or font.get("version") != "4.1"
        or font.get("sha256") != EXPECTED_FONT_SHA256
        or font.get("license") != "SIL Open Font License 1.1"
    ):
        raise CreditScreenError("credit-screen font provenance changed")

    records = asset.get("strips")
    if not isinstance(records, list) or len(records) != len(STRIP_CONTRACTS):
        raise CreditScreenError("credit-screen asset must define exactly two strips")
    encoded = []
    for record, contract in zip(records, STRIP_CONTRACTS):
        for key in (
            "name",
            "text",
            "first_tile",
            "screen_rect",
            "rom_source",
        ):
            if record.get(key) != contract[key]:
                raise CreditScreenError(
                    "%s strip %s changed" % (contract["name"], key)
                )
        if record.get("tile_count") != 32:
            raise CreditScreenError("%s strip must contain 32 tiles" % contract["name"])
        pixels = encode_rows(record.get("rows"))
        if len(pixels) != 0x200:
            raise AssertionError(len(pixels))
        encoded.append(pixels)
    return path, asset, tuple(encoded)


def owned_ranges():
    """Return the two exclusive native-art ranges owned by this installer."""
    return tuple(
        (_offset(SOURCE_BANK, contract["address"]),
         _offset(SOURCE_BANK, contract["address"]) + 0x200)
        for contract in STRIP_CONTRACTS
    )


def install(rom, asset_path=DEFAULT_ASSET, checksums=True):
    """Return ``rom`` with only the approved English name strips installed."""
    _path, _asset, strips = load_asset(asset_path)
    out = bytearray(rom)
    for contract, pixels, (start, end) in zip(
        STRIP_CONTRACTS, strips, owned_ranges()
    ):
        current = bytes(out[start:end])
        current_sha = sha256(current).hexdigest()
        localized_sha = sha256(pixels).hexdigest()
        if current_sha not in (contract["original_sha256"], localized_sha):
            raise CreditScreenError(
                "%s native strip changed unexpectedly: %s"
                % (contract["name"], current_sha)
            )
        out[start:end] = pixels
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, asset_path=DEFAULT_ASSET):
    path, asset, strips = load_asset(asset_path)
    plane_start = _offset(SOURCE_BANK, PLANE_ADDRESS)
    plane = bytes(rom[plane_start:plane_start + PLANE_BYTES])
    return {
        "asset": str(path.relative_to(ROOT)),
        "asset_sha256": sha256(path.read_bytes()).hexdigest(),
        "font_sha256": asset["font"]["sha256"],
        "plane": {
            "source": "F3:$5D00-$64FF",
            "bytes": PLANE_BYTES,
            "native_sha256": sha256(plane).hexdigest(),
            "destination": "VRAM bank 1 $8800-$8FFF",
        },
        "strips": [
            {
                "name": contract["name"],
                "text": contract["text"],
                "source": contract["rom_source"],
                "screen_rect": contract["screen_rect"],
                "original_sha256": contract["original_sha256"],
                "localized_sha256": sha256(pixels).hexdigest(),
                "bytes": len(pixels),
            }
            for contract, pixels in zip(STRIP_CONTRACTS, strips)
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    args = parser.parse_args(argv)
    try:
        source = args.rom.read_bytes()
        output = install(source, args.asset)
        report = summary(source, args.asset)
    except (OSError, CreditScreenError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print("asset      : %s" % report["asset"])
    print("strips     : %d" % len(report["strips"]))
    print("output     : %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
