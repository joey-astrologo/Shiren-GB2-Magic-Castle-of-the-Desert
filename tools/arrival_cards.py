#!/usr/bin/env python3
"""Install the approved English town/dungeon arrival-card artwork.

The native bank-$7F renderer is retained byte-for-byte in dedicated bank $F8,
with only its same-bank data operands redirected to a private English block
atlas.  Its readable Latin 0-9 blocks remain byte-exact and F is raised by one
pixel for approved optical alignment.  A nine-byte guarded wrapper at the native
entry far-calls that clone. Centering, floor formatting, underline drawing,
palettes, fade, and transition control therefore remain native.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from cartridge import fix_checksums
import graphics_audit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET = ROOT / "assets" / "graphics" / "arrival_cards_inter.json"
DEFAULT_FLOOR_ASSET = ROOT / "assets" / "graphics" / "arrival_floor_native.json"

BANK_SIZE = 0x4000
NATIVE_BANK = 0x7F
NATIVE_RENDERER_ADDRESS = 0x4000
NATIVE_RENDERER_BYTES = 0x01E1
NATIVE_ATLAS_ADDRESS = 0x41E1
NATIVE_PALETTE_ADDRESS = 0x61E1
NATIVE_ENTRY = bytes.fromhex("3E0B219345CDAC090D")
NATIVE_RENDERER_SHA256 = (
    "5498c237d4b4c3b40ea3dc8516973ad58bddf8450704c444f6e90b235a8cac2c"
)

RUNTIME_BANK = 0xF8
RUNTIME_ADDRESS = 0x4000
PALETTE_ADDRESS = 0x41E1
POINTER_TABLE_ADDRESS = 0x41E9
SEQUENCE_ADDRESS = 0x4229
ATLAS_ADDRESS = 0x4340
RUNTIME_END = 0x8000

ENTRY_WRAPPER = bytes((
    0x3E, RUNTIME_BANK,             # ld a,$F8
    0x21, 0x00, 0x40,               # ld hl,$4000
    0xCD, 0xAC, 0x09,               # call native far-call helper
    0xC9,                           # ret
))

# Arrival palette 6 is ordered bright-to-dark: native pixel value 0 is the
# bright endpoint and value 3 is the black card background.
PIXEL_VALUES = {".": 3, "d": 2, "m": 1, "#": 0}
EXPECTED_FONT_SHA256 = (
    "78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3"
)
EXPECTED_NATIVE_FLOOR_SHA256 = (
    "9bd2e5e4e9623a041353376842b0ea4a63d99acdf87d914bfc2a205d522bad15"
)
EXPECTED_PRODUCTION_FLOOR_SHA256 = (
    "27c4ef844b232fbf9fa87f539030b9730adb2ac1ee21636cafecd32842bfab3e"
)
APPROVED_F_Y_OFFSET = -1


class ArrivalCardError(ValueError):
    """The approved asset or an exact ROM ownership contract changed."""


def _offset(bank, address):
    if not 0x4000 <= address < 0x8000:
        raise ArrivalCardError("switchable-bank address is outside ROMX")
    return bank * BANK_SIZE + address - 0x4000


def _digest(data):
    return sha256(data).hexdigest()


def _validate_rows(rows, width, owner):
    if (
        not isinstance(rows, (list, tuple))
        or len(rows) != 16
        or any(
            not isinstance(row, str)
            or len(row) != width
            or set(row) - set(PIXEL_VALUES)
            for row in rows
        )
    ):
        raise ArrivalCardError(
            "%s must contain sixteen %d-column .dm# rows" % (owner, width)
        )
    return tuple(rows)


def encode_block(rows):
    """Encode one 16x16 raster in the native column-major four-tile order."""
    rows = _validate_rows(rows, 16, "arrival block")
    encoded = bytearray()
    for tile_x in range(2):
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


def _shift_rows(rows, y_offset):
    """Translate a 16x16 symbolic raster vertically with background clipping."""
    rows = _validate_rows(rows, 16, "arrival block")
    if not isinstance(y_offset, int) or not -15 <= y_offset <= 15:
        raise ArrivalCardError("arrival block y offset must be from -15 through 15")
    blank = "." * 16
    if y_offset < 0:
        return rows[-y_offset:] + (blank,) * -y_offset
    if y_offset > 0:
        return (blank,) * y_offset + rows[:-y_offset]
    return rows


def load_asset(path=DEFAULT_ASSET):
    path = Path(path).resolve()
    try:
        asset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArrivalCardError("cannot load arrival-card asset %s: %s" % (path, exc)) from exc

    if asset.get("format") != "shiren-gb2-arrival-cards-v1":
        raise ArrivalCardError("unsupported arrival-card asset format")
    if tuple(asset.get("content", ())) != graphics_audit.ARRIVAL_LABELS:
        raise ArrivalCardError("arrival-card wording or selector order changed")
    if asset.get("font") != {
        "family": "Inter",
        "style": "SemiBold",
        "version": "4.1",
        "cap_height": 11,
        "sha256": EXPECTED_FONT_SHA256,
        "license": "SIL Open Font License 1.1",
    }:
        raise ArrivalCardError("arrival-card font provenance changed")
    if asset.get("rendering") != {
        "style": "native-aa",
        "aa_low": 48,
        "aa_high": 160,
        "palette_symbols": {
            ".": [0, 0, 0],
            "d": [40, 40, 40],
            "m": [96, 96, 96],
            "#": [248, 248, 248],
        },
    }:
        raise ArrivalCardError("arrival-card rendering contract changed")
    if asset.get("layout") != {
        "screen_size": [160, 144],
        "location_band": [40, 56],
        "underline_y": 57,
        "floor_band": [73, 89],
        "maximum_label_pixels": 144,
        "block_pixels": 16,
    }:
        raise ArrivalCardError("arrival-card layout changed")
    expected_floor_art = {
        "asset": "assets/graphics/arrival_floor_native.json",
        "source": "7F:$41E1-$44A0",
        "source_sha256": EXPECTED_NATIVE_FLOOR_SHA256,
        "policy": "preserve native Latin digits; raise F one pixel for optical alignment",
        "f_y_offset": APPROVED_F_Y_OFFSET,
    }
    if asset.get("floor_art") != expected_floor_art:
        raise ArrivalCardError("arrival-card floor-art policy changed")

    labels = asset.get("labels")
    if not isinstance(labels, list) or len(labels) != 30:
        raise ArrivalCardError("arrival-card asset must define 30 unique labels")
    selector_rows = [None] * 32
    encoded_labels = []
    for record in labels:
        text = record.get("text")
        selectors = record.get("selectors")
        blocks = record.get("blocks")
        if (
            not isinstance(text, str)
            or not isinstance(selectors, list)
            or not selectors
            or not isinstance(blocks, int)
            or not 1 <= blocks <= 9
        ):
            raise ArrivalCardError("invalid arrival-card label record")
        rows = _validate_rows(record.get("rows"), blocks * 16, repr(text))
        glyphs = []
        for block in range(blocks):
            glyphs.append(
                encode_block(tuple(row[block * 16:(block + 1) * 16] for row in rows))
            )
        encoded_labels.append((text, tuple(selectors), tuple(glyphs)))
        for selector in selectors:
            if (
                not isinstance(selector, int)
                or not 0 <= selector < 32
                or selector_rows[selector] is not None
                or graphics_audit.ARRIVAL_LABELS[selector] != text
            ):
                raise ArrivalCardError("invalid or duplicate selector for %r" % text)
            selector_rows[selector] = len(encoded_labels) - 1
    if any(value is None for value in selector_rows):
        raise ArrivalCardError("arrival-card selectors do not cover all 32 slots")

    floor_path = ROOT / expected_floor_art["asset"]
    try:
        floor_asset = json.loads(floor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArrivalCardError(
            "cannot load arrival-floor asset %s: %s" % (floor_path, exc)
        ) from exc
    if {
        "format": floor_asset.get("format"),
        "source": floor_asset.get("source"),
        "source_sha256": floor_asset.get("source_sha256"),
        "policy": floor_asset.get("policy"),
    } != {
        "format": "shiren-gb2-native-arrival-floor-v1",
        "source": expected_floor_art["source"],
        "source_sha256": EXPECTED_NATIVE_FLOOR_SHA256,
        "policy": "preserve readable native Latin digits and F",
    }:
        raise ArrivalCardError("native arrival-floor asset contract changed")
    floors = floor_asset.get("blocks")
    if not isinstance(floors, list) or len(floors) != 11:
        raise ArrivalCardError("native floor asset must define digits 0-9 and F")
    encoded_native_floors = []
    encoded_floors = []
    for record, glyph in zip(floors, "0123456789F"):
        if record.get("glyph") != glyph:
            raise ArrivalCardError("arrival floor-block order changed")
        rows = _validate_rows(record.get("rows"), 16, "arrival floor %s" % glyph)
        encoded_native_floors.append(encode_block(rows))
        if glyph == "F":
            rows = _shift_rows(rows, APPROVED_F_Y_OFFSET)
        encoded_floors.append(encode_block(rows))
    if _digest(b"".join(encoded_native_floors)) != EXPECTED_NATIVE_FLOOR_SHA256:
        raise ArrivalCardError("native arrival-floor pixels changed")
    if _digest(b"".join(encoded_floors)) != EXPECTED_PRODUCTION_FLOOR_SHA256:
        raise ArrivalCardError("approved arrival-floor alignment changed")
    return path, asset, tuple(encoded_labels), tuple(selector_rows), tuple(encoded_floors)


def _patch_word(code, instruction_address, opcode, value):
    offset = instruction_address - RUNTIME_ADDRESS
    if code[offset] != opcode:
        raise ArrivalCardError(
            "arrival renderer opcode changed at $%04X" % instruction_address
        )
    code[offset + 1:offset + 3] = value.to_bytes(2, "little")


def _original_renderer(rom):
    start = _offset(NATIVE_BANK, NATIVE_RENDERER_ADDRESS)
    current = bytes(rom[start:start + NATIVE_RENDERER_BYTES])
    if current[:len(NATIVE_ENTRY)] == ENTRY_WRAPPER:
        current = NATIVE_ENTRY + current[len(NATIVE_ENTRY):]
    if _digest(current) != NATIVE_RENDERER_SHA256:
        raise ArrivalCardError("native arrival-card renderer changed unexpectedly")
    return current


def runtime_bank(rom, asset_path=DEFAULT_ASSET):
    """Build the exact bank-$F8 renderer/data image without mutating ``rom``."""
    _path, _asset, labels, selector_rows, floors = load_asset(asset_path)
    native_floor_start = _offset(NATIVE_BANK, NATIVE_ATLAS_ADDRESS)
    native_floor = bytes(
        rom[native_floor_start:native_floor_start + len(floors) * 64]
    )
    if _digest(native_floor) != EXPECTED_NATIVE_FLOOR_SHA256:
        raise ArrivalCardError("native arrival-floor source changed unexpectedly")
    renderer = bytearray(_original_renderer(rom))
    _patch_word(renderer, 0x4074, 0x21, POINTER_TABLE_ADDRESS)
    for address in (0x4094, 0x4128, 0x413D, 0x4152):
        _patch_word(renderer, address, 0x11, ATLAS_ADDRESS)
    _patch_word(renderer, 0x419B, 0x21, PALETTE_ADDRESS)
    _patch_word(renderer, 0x41B1, 0x21, PALETTE_ADDRESS + 6)

    atlas = bytearray().join(floors)
    sequences = bytearray()
    label_ids = []
    next_id = len(floors)
    for _text, _selectors, blocks in labels:
        ids = tuple(range(next_id, next_id + len(blocks)))
        next_id += len(blocks)
        if next_id > 256:
            raise ArrivalCardError("arrival-card atlas exceeds 256 addressable blocks")
        label_ids.append(ids)
        atlas.extend(bytearray().join(blocks))

    pointers_by_record = []
    for ids in label_ids:
        pointer = SEQUENCE_ADDRESS + len(sequences)
        pointers_by_record.append(pointer)
        sequences.extend((len(ids), *ids))
    pointers = bytearray()
    for record_index in selector_rows:
        pointers.extend(pointers_by_record[record_index].to_bytes(2, "little"))

    bank = bytearray(BANK_SIZE)
    def place(address, payload, owner):
        start = address - RUNTIME_ADDRESS
        end = start + len(payload)
        if start < 0 or end > len(bank):
            raise ArrivalCardError("%s exceeds dedicated bank $F8" % owner)
        bank[start:end] = payload

    place(RUNTIME_ADDRESS, renderer, "renderer")
    native_palette = bytes(
        rom[
            _offset(NATIVE_BANK, NATIVE_PALETTE_ADDRESS):
            _offset(NATIVE_BANK, NATIVE_PALETTE_ADDRESS) + 8
        ]
    )
    place(PALETTE_ADDRESS, native_palette, "palette")
    place(POINTER_TABLE_ADDRESS, pointers, "pointer table")
    place(SEQUENCE_ADDRESS, sequences, "sequences")
    place(ATLAS_ADDRESS, atlas, "atlas")
    if ATLAS_ADDRESS + len(atlas) > RUNTIME_END:
        raise ArrivalCardError("arrival-card atlas exceeds dedicated bank $F8")
    return bytes(bank), {
        "unique_labels": len(labels),
        "selector_slots": len(selector_rows),
        "atlas_blocks": len(atlas) // 64,
        "atlas_bytes": len(atlas),
        "sequence_bytes": len(sequences),
        "used_end": ATLAS_ADDRESS + len(atlas),
    }


def owned_ranges():
    return (
        (
            _offset(NATIVE_BANK, NATIVE_RENDERER_ADDRESS),
            _offset(NATIVE_BANK, NATIVE_RENDERER_ADDRESS) + len(ENTRY_WRAPPER),
        ),
        (
            _offset(RUNTIME_BANK, RUNTIME_ADDRESS),
            _offset(RUNTIME_BANK, RUNTIME_END - 1) + 1,
        ),
    )


def install(rom, asset_path=DEFAULT_ASSET, checksums=True):
    """Return ``rom`` with the guarded English arrival-card bank installed."""
    out = bytearray(rom)
    expected_bank, _report = runtime_bank(out, asset_path)
    entry_start, entry_end = owned_ranges()[0]
    bank_start, bank_end = owned_ranges()[1]
    current_entry = bytes(out[entry_start:entry_end])
    current_bank = bytes(out[bank_start:bank_end])

    if current_entry == ENTRY_WRAPPER:
        if current_bank != expected_bank:
            raise ArrivalCardError("installed arrival-card bank changed unexpectedly")
    elif current_entry == NATIVE_ENTRY:
        if any(current_bank):
            raise ArrivalCardError("dedicated arrival-card bank $F8 is not empty")
        out[entry_start:entry_end] = ENTRY_WRAPPER
        out[bank_start:bank_end] = expected_bank
    else:
        raise ArrivalCardError("native arrival-card entry changed unexpectedly")

    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, asset_path=DEFAULT_ASSET):
    path, asset, _labels, _selector_rows, _floors = load_asset(asset_path)
    bank, report = runtime_bank(rom, asset_path)
    return {
        "asset": str(path.relative_to(ROOT)),
        "asset_sha256": _digest(path.read_bytes()),
        "font_sha256": asset["font"]["sha256"],
        "floor_asset": str(DEFAULT_FLOOR_ASSET.relative_to(ROOT)),
        "floor_asset_sha256": _digest(DEFAULT_FLOOR_ASSET.read_bytes()),
        "native_entry": "7F:$4000-$4008",
        "runtime_bank": "F8:$4000-$7FFF",
        "runtime_sha256": _digest(bank),
        **report,
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
    except (OSError, ArrivalCardError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print("asset      : %s" % report["asset"])
    print("selectors  : %d" % report["selector_slots"])
    print("atlas      : %d blocks" % report["atlas_blocks"])
    print("output     : %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
