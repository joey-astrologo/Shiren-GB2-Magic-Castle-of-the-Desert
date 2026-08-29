#!/usr/bin/env python3
"""Install an English four-character editor for Big Moai promotional gift codes.

The native graphical input mode 3 owns a four-byte buffer, 49 kana cells and
three controls.  This patch retains the buffer and controller contracts while
replacing the reachable character domain with A-Z and 0-9.  Mode 4 (player
names), the Blank Scroll editor, and Wanderer Rescue keep their independent
controllers.  The game calls the Big Moai codes "spells."
"""
from hashlib import sha1

from cartridge import fix_checksums
import english
import extract
import name6


RUNTIME_BANK = 252
RUNTIME_ADDRESS = 0x4000
CODE_END = 0x4060
KEYBOARD_MAP_ADDRESS = 0x4100
KEYBOARD_MAP_END = 0x4240
GLYPH_LOW_ADDRESS = 0x4300
GLYPH_LOW_START = 0x00
GLYPH_LOW_END = 0x25
GLYPH_HIGH_ADDRESS = 0x4600
GLYPH_HIGH_START = 0x30
GLYPH_HIGH_END = 0x58
GLYPH_STRIDE = 16
PAYLOAD_END = 0x4890

SCREEN_BANK = 4
SCREEN_ADDRESS = 0x4CF6
ORIGINAL_SCREEN_HEAD = bytes.fromhex("CD3108CD60253E03")
SCREEN_PATCH = bytes.fromhex("3EFC210040C3AC09")

CHARACTER_BANK = 18
CHARACTER_TABLE_ADDRESS = 0x5310
CHARACTER_CELLS = 49
CHARACTER_TABLE_SHA1 = "2fe3d091914b9883799fc65f2d73e40bc37b2bd1"

NAVIGATION_BANK = 16
NAVIGATION_ADDRESS = 0x64B9
NAVIGATION_NODES = 52
NAVIGATION_RECORD_SIZE = 7
NAVIGATION_SIZE = NAVIGATION_NODES * NAVIGATION_RECORD_SIZE
NAVIGATION_SHA1 = "fd11cfa157fbccccb1f7965488d022beade29425"
GENERATED_NAVIGATION_SHA1 = "bbaadc62278f36abe7d59af5a725655fb5ae7523"

KEYBOARD_MAP_BANK = 4
KEYBOARD_MAP_SOURCE_ADDRESS = 0x49C4
KEYBOARD_MAP_SIZE = 20 * 16
KEYBOARD_MAP_SHA1 = name6.KEYBOARD_MAP_SHA1

CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MAXIMUM_CHARACTERS = 4
BACKSPACE_NODE = 50
CONFIRM_NODE = 51
UNREACHABLE_NODES = tuple(range(len(CHARACTERS), BACKSPACE_NODE))

# The left block holds A-M.  The right block continues N-Z and places the
# digits beneath it.  Logical columns are converted to tile/sprite positions
# by the resource builders below.
DISPLAY_ROWS = (
    ((0, "ABCDE"), (7, "NOPQR")),
    ((0, "FGHIJ"), (7, "STUVW")),
    ((0, "KLM"), (7, "XYZ")),
    ((7, "01234"),),
    ((7, "56789"),),
)


class SpellInputError(ValueError):
    """The native editor or generated English spell resources changed."""


# Assembled from tools/spell_input.asm at $FC:$4000.
ASSEMBLED_CODE = bytes.fromhex(
    "CD3108CD60253E0321A75ECDAC093E1221594FCDAC093E0421A449CDAC09"
    "AFE04F210041114098011410CDCC0A210043110090015002CD6B0A210046"
    "110093018002CD6B0A3E0421514DCDAC09AFE04F21F09711FF00010800CD"
    "280ACD5708C9"
)


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _checked_source(rom, bank, address, size, expected_sha1, label):
    at = _offset(bank, address)
    raw = bytes(rom[at:at + size])
    if len(raw) != size:
        raise SpellInputError(f"ROM is too small for {label}")
    actual = sha1(raw).hexdigest()
    if actual != expected_sha1:
        raise SpellInputError(
            f"{label} SHA-1 {actual}, expected {expected_sha1}"
        )
    return raw


def character_bytes():
    raw = english.encode(CHARACTERS)
    if len(raw) != len(CHARACTERS):
        raise SpellInputError("English spell character table changed")
    return raw + bytes((english.ENGLISH_CODES[" "],)) * (
        CHARACTER_CELLS - len(raw)
    )


def character_positions():
    positions = {}
    for row, blocks in enumerate(DISPLAY_ROWS):
        for start, text in blocks:
            for offset, character in enumerate(text):
                if character in positions:
                    raise SpellInputError("spell keyboard repeats a character")
                positions[character] = (row, start + offset)
    if set(positions) != set(CHARACTERS):
        raise SpellInputError("spell keyboard does not cover A-Z and 0-9")
    return tuple(positions[character] for character in CHARACTERS)


def english_keyboard_map(rom):
    raw = _checked_source(
        rom,
        KEYBOARD_MAP_BANK,
        KEYBOARD_MAP_SOURCE_ADDRESS,
        KEYBOARD_MAP_SIZE,
        KEYBOARD_MAP_SHA1,
        "shared graphical-input tilemap",
    )
    rows = [bytearray(row) for row in zip(*[iter(raw)] * 20)]
    blank = english.ENGLISH_CODES[" "]
    for row in range(2, 16):
        rows[row][1:19] = bytes((blank,) * 18)

    def put(row, column, text):
        encoded = english.encode(text)
        rows[row][column:column + len(encoded)] = encoded

    put(4, 2, "DEL")
    put(4, 15, "OK")
    for display_row, blocks in enumerate(DISPLAY_ROWS):
        for logical_column, text in blocks:
            put(6 + display_row * 2, 1 + logical_column, text)
    result = bytes(value for row in rows for value in row)
    if len(result) != KEYBOARD_MAP_SIZE:
        raise SpellInputError("English spell keyboard map is not 20x16 tiles")
    return result


def english_navigation_table(rom):
    at = _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS)
    raw = bytes(rom[at:at + NAVIGATION_SIZE])
    if len(raw) != NAVIGATION_SIZE:
        raise SpellInputError("ROM is too small for mode-3 navigation table")
    # Rebuilding an already patched development ROM must be deterministic.
    # The generated graph keeps the native record size, so accept either the
    # original table or the exact table this function produces below.
    native_sha1 = sha1(raw).hexdigest()
    if native_sha1 == GENERATED_NAVIGATION_SHA1:
        return raw
    if native_sha1 != NAVIGATION_SHA1:
        raise SpellInputError(
            f"mode-3 navigation table SHA-1 {native_sha1}, "
            f"expected {NAVIGATION_SHA1}"
        )
    records = [
        bytearray(record)
        for record in zip(*[iter(raw)] * NAVIGATION_RECORD_SIZE)
    ]
    positions = character_positions()
    node_at = {position: node for node, position in enumerate(positions)}
    rows = {row: [] for row in range(len(DISPLAY_ROWS))}
    columns = {column: [] for column in range(12)}
    for node, (row, column) in enumerate(positions):
        rows[row].append(node)
        columns[column].append(node)
        records[node][4:] = bytes((9 + column * 8, 73 + row * 16, 8))

    # Every displayed row is one horizontal ring across both visual blocks.
    for row_nodes in rows.values():
        ring = sorted(row_nodes, key=lambda node: positions[node][1])
        for ordinal, node in enumerate(ring):
            records[node][2] = ring[ordinal - 1]
            records[node][3] = ring[(ordinal + 1) % len(ring)]

    # Vertical edges lead to the editing controls and return through the same
    # visual block, so all active nodes remain reachable without blank cells.
    for column, column_nodes in columns.items():
        if not column_nodes:
            continue
        stack = sorted(column_nodes, key=lambda node: positions[node][0])
        control = BACKSPACE_NODE if column < 7 else CONFIRM_NODE
        for ordinal, node in enumerate(stack):
            records[node][0] = (
                stack[ordinal + 1] if ordinal + 1 < len(stack) else control
            )
            records[node][1] = stack[ordinal - 1] if ordinal else control

    left_top = node_at[(0, 0)]
    left_bottom = node_at[(2, 0)]
    right_top = node_at[(0, 7)]
    right_bottom = node_at[(4, 7)]
    records[BACKSPACE_NODE][:] = bytes(
        (left_top, left_bottom, CONFIRM_NODE, CONFIRM_NODE, 9, 49, 9)
    )
    records[CONFIRM_NODE][:] = bytes(
        (right_top, right_bottom, BACKSPACE_NODE, BACKSPACE_NODE, 113, 49, 10)
    )

    for node in UNREACHABLE_NODES:
        records[node][:] = bytes((node, node, node, node, 0, 0, 0))

    active = set(range(len(CHARACTERS))) | {BACKSPACE_NODE, CONFIRM_NODE}
    reached = {0}
    pending = [0]
    while pending:
        node = pending.pop()
        for target in records[node][:4]:
            if target in active and target not in reached:
                reached.add(target)
                pending.append(target)
    if reached != active:
        raise SpellInputError(
            f"English spell graph leaves unreachable nodes {sorted(active - reached)}"
        )
    for node in active:
        leaked = set(records[node][:4]) - active
        if leaked:
            raise SpellInputError(
                f"active spell node {node} reaches inactive nodes {sorted(leaked)}"
            )
    result = bytes(value for record in records for value in record)
    if len(result) != NAVIGATION_SIZE:
        raise SpellInputError("English spell navigation table changed size")
    return result


def runtime_payload(rom):
    if len(ASSEMBLED_CODE) != CODE_END - RUNTIME_ADDRESS:
        raise SpellInputError("assembled spell-input code length changed")
    payload = bytearray(PAYLOAD_END - RUNTIME_ADDRESS)

    def place(address, raw):
        start = address - RUNTIME_ADDRESS
        end = start + len(raw)
        if not 0 <= start <= end <= len(payload):
            raise SpellInputError("spell-input payload leaves its reserved range")
        if any(payload[start:end]):
            raise SpellInputError("spell-input payload components overlap")
        payload[start:end] = raw

    place(RUNTIME_ADDRESS, ASSEMBLED_CODE)
    place(KEYBOARD_MAP_ADDRESS, english_keyboard_map(rom))
    place(
        GLYPH_LOW_ADDRESS,
        name6.keyboard_glyph_bytes(GLYPH_LOW_START, GLYPH_LOW_END),
    )
    place(
        GLYPH_HIGH_ADDRESS,
        name6.keyboard_glyph_bytes(GLYPH_HIGH_START, GLYPH_HIGH_END),
    )
    return bytes(payload)


def owned_ranges():
    return (
        (
            _offset(SCREEN_BANK, SCREEN_ADDRESS),
            _offset(SCREEN_BANK, SCREEN_ADDRESS) + len(SCREEN_PATCH),
        ),
        (
            _offset(CHARACTER_BANK, CHARACTER_TABLE_ADDRESS),
            _offset(CHARACTER_BANK, CHARACTER_TABLE_ADDRESS) + CHARACTER_CELLS,
        ),
        (
            _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS),
            _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS) + NAVIGATION_SIZE,
        ),
        (
            _offset(RUNTIME_BANK, RUNTIME_ADDRESS),
            _offset(RUNTIME_BANK, PAYLOAD_END),
        ),
    )


def install(rom, verify_original=True, checksums=True):
    out = bytearray(rom)
    screen_at = _offset(SCREEN_BANK, SCREEN_ADDRESS)
    actual = bytes(out[screen_at:screen_at + len(ORIGINAL_SCREEN_HEAD)])
    if (
        verify_original
        and actual != ORIGINAL_SCREEN_HEAD
        and actual[:len(SCREEN_PATCH)] != SCREEN_PATCH
    ):
        raise SpellInputError("mode-3 screen constructor is not original")
    out[screen_at:screen_at + len(SCREEN_PATCH)] = SCREEN_PATCH

    character_at = _offset(CHARACTER_BANK, CHARACTER_TABLE_ADDRESS)
    if verify_original:
        actual_characters = bytes(
            out[character_at:character_at + CHARACTER_CELLS]
        )
        if (
            sha1(actual_characters).hexdigest() != CHARACTER_TABLE_SHA1
            and actual_characters != character_bytes()
        ):
            raise SpellInputError("mode-3 character table is not original")
    out[character_at:character_at + CHARACTER_CELLS] = character_bytes()

    navigation = english_navigation_table(out)
    navigation_at = _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS)
    out[navigation_at:navigation_at + len(navigation)] = navigation

    payload = runtime_payload(out)
    runtime_at = _offset(RUNTIME_BANK, RUNTIME_ADDRESS)
    existing = bytes(out[runtime_at:runtime_at + len(payload)])
    if verify_original and any(existing) and existing != payload:
        raise SpellInputError(
            "reserved spell-input range is not empty at "
            + extract.location(RUNTIME_BANK, RUNTIME_ADDRESS)
        )
    out[runtime_at:runtime_at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom):
    keyboard = english_keyboard_map(rom)
    navigation = english_navigation_table(rom)
    return {
        "mode": 3,
        "maximum_characters": MAXIMUM_CHARACTERS,
        "characters": CHARACTERS,
        "runtime": {
            "bank": RUNTIME_BANK,
            "start": extract.location(RUNTIME_BANK, RUNTIME_ADDRESS),
            "end_exclusive": extract.location(RUNTIME_BANK, PAYLOAD_END),
            "payload_bytes": PAYLOAD_END - RUNTIME_ADDRESS,
        },
        "keyboard_map_sha1": sha1(keyboard).hexdigest(),
        "navigation_sha1": sha1(navigation).hexdigest(),
        "active_nodes": len(CHARACTERS) + 2,
        "unreachable_nodes": list(UNREACHABLE_NODES),
        "mode4_source_unchanged": True,
    }
