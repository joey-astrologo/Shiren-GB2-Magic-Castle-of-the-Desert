#!/usr/bin/env python3
"""Report static ROM contracts for graphical Japanese text families.

This is an inventory tool, not an installer.  It deliberately reads only the
original ROM structures proved by live traces or exact screenshot-to-ROM matches:
the clean-boot credit card, title screen, shared dungeon/town arrival-card renderer,
and save/load wait sign.

    graphics_audit.py ROM
"""

import argparse
from collections import defaultdict
from hashlib import sha1
import json
from pathlib import Path
import sys


class GraphicsAuditError(ValueError):
    pass


GFX_8800_TABLE = (0x05, 0x6F35)
GFX_8000_TABLE = (0x3F, 0x4017)
TILEMAP_TABLE = (0x00, 0x3CD3)

ARRIVAL_BANK = 0x7F
ARRIVAL_RENDERER = (0x4000, 0x41E1)
ARRIVAL_GLYPH_BASE = 0x41E1
ARRIVAL_GLYPH_COUNT = 128
ARRIVAL_GLYPH_BYTES = 0x40
ARRIVAL_POINTER_TABLE = 0x61E9
ARRIVAL_SELECTOR_SLOTS = 32


# C12C selector labels are aligned with the native history-location family.
# Selectors 30 and 31 share one native sequence but have no corresponding
# extracted location-name record, so the audit leaves their semantics open.
ARRIVAL_LABELS = (
    "Town of Ilpa",
    "Castle Dungeon",
    "Ancient Ruins",
    "Closed Room",
    "Inner Ramparts",
    "Tono Gate Shrine",
    "Second Bailey",
    "Dark Chamber",
    "Castle Tower",
    "Castle Walls",
    "Main Bailey",
    "Murky Tower",
    "Hall of Carnage",
    "Silver Chamber",
    "Gold Chamber",
    "Top Chamber",
    "Castle Keep",
    "Jahannam's Gate",
    "Dark Depths",
    "Final Gate",
    "Evil God's Lair",
    "Abyssal Depths",
    "Tonfan's Hole",
    "Wanado",
    "Smith's Forge",
    "Pot Cave",
    "Training Dungeon",
    "Road to Rescue",
    "Castle Prison",
    "Pot Cave",
    "unresolved native selector 30",
    "unresolved native selector 31",
)


def _offset(bank, address):
    if bank == 0:
        if not 0 <= address < 0x4000:
            raise GraphicsAuditError("fixed-bank address is outside ROM0")
        return address
    if not 0x4000 <= address < 0x8000:
        raise GraphicsAuditError("switchable-bank address is outside ROMX")
    return bank * 0x4000 + address - 0x4000


def _read(rom, bank, address, size):
    start = _offset(bank, address)
    data = rom[start:start + size]
    if len(data) != size:
        raise GraphicsAuditError(
            "short ROM read at %02X:$%04X" % (bank, address)
        )
    return data


def _source_sha1(rom, bank, address, size):
    return sha1(_read(rom, bank, address, size)).hexdigest()


def _location(bank, address):
    return "%02X:$%04X" % (bank, address)


def _range(bank, start, end_exclusive):
    return "%02X:$%04X-$%04X" % (bank, start, end_exclusive - 1)


def _table_entry(rom, table, selector):
    table_bank, table_address = table
    raw = _read(rom, table_bank, table_address + selector * 3, 3)
    address = raw[0] | raw[1] << 8
    return raw[2], address


def _assert_entry(rom, table, selector, expected):
    actual = _table_entry(rom, table, selector)
    if actual != expected:
        raise GraphicsAuditError(
            "selector %d at %s resolves to %s, expected %s"
            % (
                selector,
                _location(*table),
                _location(*actual),
                _location(*expected),
            )
        )


def _plane(
    rom,
    table,
    selectors,
    source,
    destination,
    split_limit,
):
    if isinstance(selectors, int):
        selector_list = [selectors]
    else:
        selector_list = list(selectors)
    for selector in selector_list:
        _assert_entry(rom, table, selector, source)

    bank, address = source
    size = int.from_bytes(_read(rom, bank, address, 2), "little")
    if size > split_limit:
        vram_banks = [1, 0]
        bank_bytes = [size - split_limit, split_limit]
    else:
        vram_banks = [0]
        bank_bytes = None

    result = {
        "table": _location(*table),
        "source": _range(bank, address, address + 2 + size),
        "destination": "$%04X" % destination,
        "vram_banks": vram_banks,
        "data_bytes": size,
    }
    if len(selector_list) == 1:
        result["selector"] = selector_list[0]
    else:
        result["selectors"] = selector_list
    if bank_bytes is not None:
        result["bank_bytes"] = bank_bytes

    # Keep the stable presentation order used in the test and JSON output.
    selector_key = "selector" if "selector" in result else "selectors"
    ordered = {selector_key: result[selector_key], "table": result["table"]}
    ordered.update(
        source=result["source"],
        destination=result["destination"],
        vram_banks=result["vram_banks"],
    )
    if bank_bytes is not None:
        ordered["bank_bytes"] = result["bank_bytes"]
    ordered["data_bytes"] = result["data_bytes"]
    return ordered


def _tilemap(rom, selector):
    bank, address = _table_entry(rom, TILEMAP_TABLE, selector)
    columns, rows = _read(rom, bank, address, 2)
    data_size = columns * rows * 2
    data = _read(rom, bank, address + 2, data_size)
    destination = 0x9800 if selector == 0 else 0x9820
    return {
        "selector": selector,
        "descriptor": _range(
            TILEMAP_TABLE[0],
            TILEMAP_TABLE[1] + selector * 3,
            TILEMAP_TABLE[1] + selector * 3 + 3,
        ),
        "source": _range(bank, address, address + 2 + data_size),
        "destination": "$%04X" % destination,
        "columns": columns,
        "rows": rows,
        "interleaved_attributes": True,
        "_palette_ids": sorted({attribute & 7 for attribute in data[1::2]}),
    }


def _public_tilemap(tilemap):
    return {key: value for key, value in tilemap.items() if not key.startswith("_")}


def _arrival_summary(rom):
    pointers = []
    sequences = []
    for selector in range(ARRIVAL_SELECTOR_SLOTS):
        raw = _read(
            rom,
            ARRIVAL_BANK,
            ARRIVAL_POINTER_TABLE + selector * 2,
            2,
        )
        pointer = int.from_bytes(raw, "little")
        count = _read(rom, ARRIVAL_BANK, pointer, 1)[0]
        glyphs = list(_read(rom, ARRIVAL_BANK, pointer + 1, count))
        pointers.append(pointer)
        sequences.append(glyphs)

    aliases = defaultdict(list)
    for selector, sequence in enumerate(sequences):
        aliases[tuple(sequence)].append(selector)
    aliased_selectors = sorted(
        selector
        for group in aliases.values()
        if len(group) > 1
        for selector in group
    )
    unique_sequences = len(aliases)
    sequence_end = max(
        pointer + 1 + len(sequence)
        for pointer, sequence in zip(pointers, sequences)
    )

    return {
        "storage": "runtime_composed_glyph_tiles",
        "renderer": _range(ARRIVAL_BANK, *ARRIVAL_RENDERER),
        "glyph_atlas": {
            "source": _range(
                ARRIVAL_BANK,
                ARRIVAL_GLYPH_BASE,
                ARRIVAL_GLYPH_BASE
                + ARRIVAL_GLYPH_COUNT * ARRIVAL_GLYPH_BYTES,
            ),
            "glyphs": ARRIVAL_GLYPH_COUNT,
            "bytes_per_glyph": ARRIVAL_GLYPH_BYTES,
            "tile_dimensions": [2, 2],
            "pixel_dimensions": [16, 16],
        },
        "pointer_table": _range(
            ARRIVAL_BANK,
            ARRIVAL_POINTER_TABLE,
            ARRIVAL_POINTER_TABLE + ARRIVAL_SELECTOR_SLOTS * 2,
        ),
        "sequences": _range(
            ARRIVAL_BANK,
            min(pointers),
            sequence_end,
        ),
        "selector_slots": ARRIVAL_SELECTOR_SLOTS,
        "unique_sequences": unique_sequences,
        "aliased_selectors": aliased_selectors,
        "maximum_location_glyphs": max(map(len, sequences)),
        "map": {
            "storage": "generated at runtime",
            "background_rows": 18,
            "background_columns": 32,
            "visible_columns": 20,
            "location_alignment": "centered from sequence length",
            "floor_format": "zero-suppressed two digits plus native F glyph",
        },
        "palette": {
            "background_palette": 7,
            "background_source": "7F:$61E1-$61E8",
            "glyph_palette": 6,
            "glyph_endpoints": ["00:$3AE9-$3AEA", "7F:$61E7-$61E8"],
            "glyph_middle_colors": "inherited from active route",
        },
        "selectors": [
            {
                "selector": selector,
                "label": ARRIVAL_LABELS[selector],
                "pointer": "7F:$%04X" % pointers[selector],
                "glyphs": sequences[selector],
            }
            for selector in range(ARRIVAL_SELECTOR_SLOTS)
        ],
        "live_mamel_route": {
            "dungeon_selector": 2,
            "location_glyphs": [11, 12, 13, 14],
            "floor": 2,
            "loaded_glyphs": [11, 12, 13, 14, 0, 2, 10],
        },
    }


def summary(rom):
    """Return the reviewed graphical-text inventory from an original ROM."""
    credit_map = _tilemap(rom, 104)
    title_map = _tilemap(rom, 0)

    credit = {
        "storage": "stored_tiles_and_tilemap",
        "route": "clean boot after the Chunsoft splash",
        "content": [
            "© 2001 CHUNSOFT",
            "© 2001 Koichi Sugiyama credit",
        ],
        "visible_foreground_plane": {
            "selector": 24,
            "pointer": "F0:$40EF-$40F1",
            "length": "F0:$410A",
            "source": "F3:$5D00-$64FF",
            "destination": "$8800-$8FFF",
            "vram_bank": 1,
            "data_bytes": 2048,
            "localized_strips": [
                "F3:$5F00-$60FF",
                "F3:$6300-$64FF",
            ],
        },
        "visible_tilemap": {
            "producer": "F0:$4057-$409E",
            "destination": "$9800",
            "tile_ids": "$80-$FF",
            "attribute_fill": "$08 (VRAM bank 1)",
            "stable_scroll": {"scx": "$F0", "scy": "$D8"},
        },
        "tile_planes": [
            _plane(rom, GFX_8800_TABLE, 58, (0x2D, 0x4F12), 0x8800, 0x1000),
            _plane(
                rom,
                GFX_8000_TABLE,
                [57, 58],
                (0x36, 0x614A),
                0x8000,
                0x0800,
            ),
        ],
        "tilemap": _public_tilemap(credit_map),
        "palette": {
            "attribute_palette_ids": credit_map["_palette_ids"],
            "base_source": "17:$58F6-$592D",
            "palette_0_override": "F0:$409F-$40A6",
            "behavior": "native fade animation",
        },
        "sharing": "the $8000 plane is aliased by selectors 57 and 58",
        "status": "localization_required",
    }
    title = {
        "storage": "stored_tiles_and_tilemap",
        "route": "clean boot after the copyright card",
        "content": [
            "Mystery Dungeon",
            "Shiren the Wanderer GB2",
            "Magic Castle of the Desert",
        ],
        "tile_planes": [
            _plane(rom, GFX_8800_TABLE, 0, (0x1C, 0x4000), 0x8800, 0x1000),
            _plane(rom, GFX_8000_TABLE, 0, (0x31, 0x4000), 0x8000, 0x0800),
        ],
        "tilemap": _public_tilemap(title_map),
        "palette": {
            "attribute_palette_ids": title_map["_palette_ids"],
            "source": "17:$416F-$41AE",
        },
        "sharing": "all three resource selectors are title-family selector 0",
        "status": "localization_required",
    }
    return {
        "policy": {
            "functional_graphical_text": "audit_and_localize",
            "environmental_shop_signs": "preserve_japanese",
            "ending_fin_mark": "preserve_japanese",
        },
        "native_source_sha1": {
            "credit_main_tiles": _source_sha1(rom, 0x2D, 0x4F14, 0x0670),
            "credit_secondary_tiles": _source_sha1(
                rom, 0x36, 0x614C, 0x0120
            ),
            "credit_tilemap_attributes": _source_sha1(
                rom, 0x3B, 0x7982, 0x0500
            ),
            "credit_base_palettes": _source_sha1(
                rom, 0x17, 0x58F6, 0x0038
            ),
            "credit_palette_0_override": _source_sha1(
                rom, 0xF0, 0x409F, 0x0008
            ),
            "credit_visible_foreground": _source_sha1(
                rom, 0xF3, 0x5D00, 0x0800
            ),
            "title_8800_tiles": _source_sha1(rom, 0x1C, 0x4002, 0x1420),
            "title_8000_tiles": _source_sha1(rom, 0x31, 0x4002, 0x0B00),
            "title_tilemap_attributes": _source_sha1(
                rom, 0x38, 0x4002, 0x02D0
            ),
            "title_palettes": _source_sha1(rom, 0x17, 0x416F, 0x0040),
            "arrival_glyph_atlas": _source_sha1(
                rom, 0x7F, 0x41E1, 0x2000
            ),
            "arrival_pointer_table": _source_sha1(
                rom, 0x7F, 0x61E9, 0x0040
            ),
            "arrival_sequences": _source_sha1(rom, 0x7F, 0x6229, 0x00C6),
            "wait_sign_top": _source_sha1(rom, 0x56, 0x7A80, 0x0100),
            "wait_bird_top": _source_sha1(rom, 0x56, 0x7B80, 0x0100),
            "wait_sign_bottom": _source_sha1(rom, 0x56, 0x7C80, 0x0100),
            "wait_bird_bottom": _source_sha1(rom, 0x56, 0x7D80, 0x0100),
        },
        "clean_boot": {
            "credit_card": credit,
            "title_screen": title,
        },
        "arrival_cards": _arrival_summary(rom),
        "save_load_wait_screen": {
            "storage": "stored_column_major_2bpp_tiles",
            "route": (
                "user-observed after Quit suspends an in-game save and that save "
                "is loaded; automated live reproduction remains pending"
            ),
            "native_content": "しばらく おまちください",
            "localized_content": ["Please", "wait..."],
            "screen_rect": [33, 74, 97, 106],
            "localized_sign_blocks": [
                "56:$7A80-$7B7F",
                "56:$7C80-$7D7F",
            ],
            "preserved_interleaved_bird_blocks": [
                "56:$7B80-$7C7F",
                "56:$7D80-$7E7F",
            ],
            "status": (
                "english_art_installed_static_pixel_tested_live_route_pending"
            ),
        },
        "routes_requiring_live_capture": {
            "ending_credits": {
                "status": "live_route_required",
                "storage": "unknown_until_live_trace",
                "native_evidence": {
                    "scenario_selector": 27,
                    "scenario_label": "Town 7 staff telop",
                    "scenario_label_source": "group 14 index 27 / C2:$7111",
                    "music_selector": 38,
                    "music_label": "Staff Roll",
                    "music_label_source": "group 25 index 38 / C3:$432C",
                },
                "routes_to_capture": ["main ending", "true ending"],
                "needed_fixture": (
                    "a disposable save state immediately before each ending"
                ),
                "reason": (
                    "native labels prove the staff-roll route exists, but do not "
                    "prove whether its visible names are stored art, a generated "
                    "tilemap, or ordinary text"
                ),
            }
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(summary(args.rom.read_bytes()), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
