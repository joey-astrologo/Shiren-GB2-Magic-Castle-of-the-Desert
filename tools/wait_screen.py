#!/usr/bin/env python3
"""Install the approved English save/load wait-screen sign.

Bank $56 stores the sign as two 64x16 column-major tile blocks.  Two bird-art
blocks are interleaved between and after them; those blocks are deliberately
outside this installer's ownership and are hash-guarded byte-for-byte.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from cartridge import fix_checksums


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET = ROOT / "assets" / "graphics" / "wait_screen.json"

BANK_SIZE = 0x4000
SOURCE_BANK = 0x56
BLOCK_BYTES = 0x100
PIXEL_VALUES = {".": 0, "l": 1, "g": 2, "#": 3}

BLOCK_CONTRACTS = (
    {
        "name": "top",
        "address": 0x7A80,
        "source": "56:$7A80-$7B7F",
        "row_start": 0,
        "original_sha256": (
            "4c8b018b97475bb18ac952aaa0951006d2d749628733a590bedeec97c3af4192"
        ),
        "localized_sha256": (
            "8af82c6faeebc91d6cdbdc089b0af18b89da9e5597790d2d57826f8bf1491b38"
        ),
    },
    {
        "name": "bottom",
        "address": 0x7C80,
        "source": "56:$7C80-$7D7F",
        "row_start": 16,
        "original_sha256": (
            "65d74b28ce217f454be340e6939dc323c0cff463cb18e58126b4dfd86867ff11"
        ),
        "localized_sha256": (
            "5f0e0691637e51f767c069f0e8b0b69ac322e89c4e08f86c8cdcdb6b0e8ab047"
        ),
    },
)

BIRD_CONTRACTS = (
    {
        "address": 0x7B80,
        "source": "56:$7B80-$7C7F",
        "sha256": (
            "d90084aa3116e657c49af91810adb0db5227551ee9ba92365027a335a8448383"
        ),
    },
    {
        "address": 0x7D80,
        "source": "56:$7D80-$7E7F",
        "sha256": (
            "a47de45b2ca8abdea344d3afa08661b4c1e90119e25619a798ba261f4db59d24"
        ),
    },
)


class WaitScreenError(ValueError):
    """The approved asset or its exact native ROM ownership changed."""


def _offset(bank, address):
    if not 0x4000 <= address < 0x8000:
        raise WaitScreenError("switchable-bank address is outside ROMX")
    return bank * BANK_SIZE + address - 0x4000


def _digest(data):
    return sha256(data).hexdigest()


def encode_block(rows):
    """Encode one 64x16 raster as sixteen column-major 2bpp tiles."""
    if (
        not isinstance(rows, list)
        or len(rows) != 16
        or any(
            not isinstance(row, str)
            or len(row) != 64
            or set(row) - set(PIXEL_VALUES)
            for row in rows
        )
    ):
        raise WaitScreenError("wait-screen block must contain sixteen 64-column .lg# rows")

    encoded = bytearray()
    for tile_x in range(8):
        for tile_y in range(2):
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
        raise WaitScreenError("cannot load wait-screen asset %s: %s" % (path, exc)) from exc

    if asset.get("format") != "shiren-gb2-wait-screen-v1":
        raise WaitScreenError("unsupported wait-screen asset format")
    if asset.get("content") != ["Please", "wait..."]:
        raise WaitScreenError("wait-screen wording changed without approval")
    layout = asset.get("layout", {})
    if layout.get("screen_rect") != [33, 74, 97, 106]:
        raise WaitScreenError("wait-screen rectangle changed")
    expected_lines = (
        {"text": "Please", "origin": [8, 8], "advance": 30},
        {"text": "wait...", "origin": [8, 18], "advance": 26},
    )
    if tuple(layout.get("lines", ())) != expected_lines:
        raise WaitScreenError("wait-screen line layout changed")
    if layout.get("gray_drop_shadow") != [1, 1]:
        raise WaitScreenError("wait-screen shadow changed")

    font = asset.get("font", {})
    expected_font = {
        "name": "Thin Pixel-7 GB Compact",
        "spec": "assets/fonts/thin_pixel_7_compact.json",
        "spec_sha256": (
            "6a0a2bcf6ca497a4f226389302b481ebaa66095c781a98cd4244d3763a093eff"
        ),
        "glyph_source": "assets/fonts/thin_pixel_7_compact_glyphs.json",
        "glyph_source_sha256": (
            "e4d7154264cee0cd26680ae39c606916dbee7aee3db8c984d0e4659407d60aa7"
        ),
        "license": "licenses/Thin-Pixel-7.txt",
        "license_sha256": (
            "4ce79ee1180477fb93bdd91596ac00e972a99341604ec53b745b392b4e87ca6c"
        ),
    }
    if font != expected_font:
        raise WaitScreenError("wait-screen font provenance changed")
    for file_key, hash_key in (
        ("spec", "spec_sha256"),
        ("glyph_source", "glyph_source_sha256"),
        ("license", "license_sha256"),
    ):
        source = ROOT / font[file_key]
        try:
            actual = _digest(source.read_bytes())
        except OSError as exc:
            raise WaitScreenError("cannot read wait-screen font source %s" % source) from exc
        if actual != font[hash_key]:
            raise WaitScreenError("wait-screen font source changed: %s" % font[file_key])

    rows = asset.get("rows")
    if not isinstance(rows, list) or len(rows) != 32:
        raise WaitScreenError("wait-screen asset must contain 32 rows")
    blocks = asset.get("native_blocks")
    if not isinstance(blocks, list) or len(blocks) != len(BLOCK_CONTRACTS):
        raise WaitScreenError("wait-screen asset must define exactly two sign blocks")

    encoded = []
    for record, contract in zip(blocks, BLOCK_CONTRACTS):
        expected = {
            "name": contract["name"],
            "source": contract["source"],
            "bytes": BLOCK_BYTES,
            "original_sha256": contract["original_sha256"],
            "localized_sha256": contract["localized_sha256"],
        }
        if record != expected:
            raise WaitScreenError("%s sign-block contract changed" % contract["name"])
        start = contract["row_start"]
        pixels = encode_block(rows[start:start + 16])
        if _digest(pixels) != contract["localized_sha256"]:
            raise WaitScreenError("%s approved sign pixels changed" % contract["name"])
        encoded.append(pixels)

    birds = asset.get("preserved_interleaved_bird_blocks")
    if not isinstance(birds, list) or len(birds) != len(BIRD_CONTRACTS):
        raise WaitScreenError("wait-screen asset must define two preserved bird blocks")
    for record, contract in zip(birds, BIRD_CONTRACTS):
        if record != {"source": contract["source"], "sha256": contract["sha256"]}:
            raise WaitScreenError("preserved bird-block contract changed")
    return path, asset, tuple(encoded)


def owned_ranges():
    """Return the two exclusive native sign-art ranges owned here."""
    return tuple(
        (
            _offset(SOURCE_BANK, contract["address"]),
            _offset(SOURCE_BANK, contract["address"]) + BLOCK_BYTES,
        )
        for contract in BLOCK_CONTRACTS
    )


def install(rom, asset_path=DEFAULT_ASSET, checksums=True):
    """Return ``rom`` with only the approved English sign blocks installed."""
    _path, _asset, blocks = load_asset(asset_path)
    out = bytearray(rom)

    for contract in BIRD_CONTRACTS:
        start = _offset(SOURCE_BANK, contract["address"])
        current = bytes(out[start:start + BLOCK_BYTES])
        if _digest(current) != contract["sha256"]:
            raise WaitScreenError(
                "preserved bird block changed unexpectedly: %s" % contract["source"]
            )

    for contract, pixels, (start, end) in zip(
        BLOCK_CONTRACTS, blocks, owned_ranges()
    ):
        current_sha = _digest(bytes(out[start:end]))
        if current_sha not in (
            contract["original_sha256"],
            contract["localized_sha256"],
        ):
            raise WaitScreenError(
                "%s native sign block changed unexpectedly: %s"
                % (contract["name"], current_sha)
            )
        out[start:end] = pixels

    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, asset_path=DEFAULT_ASSET):
    path, asset, blocks = load_asset(asset_path)
    return {
        "asset": str(path.relative_to(ROOT)),
        "asset_sha256": _digest(path.read_bytes()),
        "content": asset["content"],
        "screen_rect": asset["layout"]["screen_rect"],
        "blocks": [
            {
                "name": contract["name"],
                "source": contract["source"],
                "bytes": BLOCK_BYTES,
                "original_sha256": contract["original_sha256"],
                "localized_sha256": _digest(pixels),
            }
            for contract, pixels in zip(BLOCK_CONTRACTS, blocks)
        ],
        "preserved_bird_blocks": [
            {
                "source": contract["source"],
                "sha256": _digest(
                    rom[
                        _offset(SOURCE_BANK, contract["address"]):
                        _offset(SOURCE_BANK, contract["address"]) + BLOCK_BYTES
                    ]
                ),
            }
            for contract in BIRD_CONTRACTS
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
    except (OSError, WaitScreenError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print("asset      : %s" % report["asset"])
    print("sign blocks: %d" % len(report["blocks"]))
    print("output     : %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
