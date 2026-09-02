#!/usr/bin/env python3
"""Install the English Wanderer Rescue password presentation/input layer.

The packet codec, diary records, and Link Cable representation stay native.
Generated passwords are localized only while they are rendered. Modes 5-8
reuse the approved player-name keyboard, add ``?`` and ``!``, and convert each
English selection to the equivalent native six-bit symbol before the original
validator sees the input buffer.
"""

from hashlib import sha1

from cartridge import fix_checksums
import english
import extract
import name6
import rescue_password


RUNTIME_BANK = 249
RUNTIME_ADDRESS = 0x4000
CODE_END = 0x42A2
ALPHABET_ADDRESS = 0x4080
INPUT_ADDRESS = 0x4100
SCREEN_ADDRESS = 0x4160
REFRESH_ADDRESS = 0x41B0
UPLOAD_ADDRESS = 0x41C0
NATIVE_ALPHABET_ADDRESS = 0x4200
HARDWARE_B_ADDRESS = 0x4260
PREMODE_SCREEN_ADDRESS = 0x4280
NAVIGATION_ADDRESS = 0x4300
KEYBOARD_MAP_ADDRESS = 0x4600
PAYLOAD_END = 0x4740

PASSWORD_CACHE_BANK = 0x11
PASSWORD_CACHE_ADDRESS = 0x4747
PASSWORD_CACHE_EXPECTED = bytes.fromhex("3E03211B5BCDAC09")
PASSWORD_CACHE_WRAPPER = RUNTIME_ADDRESS

INPUT_HOOK_BANK = 0x10
INPUT_HOOK_ADDRESS = 0x5B66
INPUT_HOOK_EXPECTED = bytes.fromhex("3EFA210040CDAC09")

SCREEN_HOOK_BANK = 0x10
SCREEN_HOOK_ADDRESS = 0x7A49
SCREEN_HOOK_EXPECTED = bytes.fromhex("3EF4214540CDAC09")
PREMODE_SCREEN_HOOK_ADDRESS = 0x68E4

HARDWARE_B_BANK = 0x10
HARDWARE_B_HOOK_ADDRESS = 0x5B22
HARDWARE_B_HOOK_EXPECTED = bytes.fromhex("3E1221B053CDAC09")
HARDWARE_B_HOOK_PATCH = bytes.fromhex("3EF9216042CDAC09")

NAVIGATION_BANK = name6.NAVIGATION_BANK
NAVIGATION_POINTER_ADDRESS = 0x615E
NAVIGATION_POINTER_EXPECTED = bytes.fromhex("3F0A")
NAVIGATION_POINTER_PATCH = bytes.fromhex("00C8")
MODE0_NAVIGATION_POINTER_ADDRESS = 0x615C
MODE0_NAVIGATION_POINTER_ENGLISH = bytes.fromhex("453B")
MODE0_NAVIGATION_POINTER_PATCH = bytes.fromhex("00C8")
ENGLISH_NAVIGATION_SHA1 = "03f5fa84f58bb28f92d405c6fc1ca6c47caf6ace"

NAVIGATION_TYPE = 0xF5
NAVIGATION_SCRATCH = 0xC800
CHARACTER_COUNT = 64
QUESTION_NODE = 62
EXCLAMATION_NODE = 63
OK_NODE = 77
LEFT_NODE = 78
RIGHT_NODE = 79
DELETE_NODE = 80
ACTIVE_NODES = frozenset(range(CHARACTER_COUNT)) | {
    OK_NODE,
    LEFT_NODE,
    RIGHT_NODE,
    DELETE_NODE,
}
BLANK_NODES = frozenset(range(CHARACTER_COUNT, OK_NODE))


class RescuePresentationError(ValueError):
    """A rescue route, shared keyboard prerequisite, or reservation changed."""


# Assembled from tools/rescue_presentation.asm at $F9:$4000-$42A1. Keeping
# these bytes checked in avoids an RGBDS build dependency; tests reassemble the
# source when RGBDS is installed and demand an exact match.
ASSEMBLED_CODE = bytes.fromhex("""
cd1240016dc13e03211b5bcdac09cd3940c9216dc1060f7efeffc8fed52815fe5e3804d6391802d6305f1600e5218040197ee177230520dfc9216dc1060f7efeffc8fed52823fe0a380cfe24380cfe4a380cd610180ac6341806d60a1802d616c630fe5e3802c60977230520d1c90000000000000000000000000000000000000a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20212223303132333435363738393a3b3c3d3e3f40414243444546474849000102030405060708094e4f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000fa95c1fe05383ffe09303b79fe403013060021004209463e12214c52cdac09cdb041c9fe4d2817fe4e2807fe4f2803fe50c03efa210040cdac09cdb041c93efa210040c3ac093efa210040c3ac0900000000000000000000000000000000000079fe05382afe093026ea95c1c53efd213242cdac09cdc041afe04f210046114098011410cdcc0aafe04fcdb041c1c93ef4214540c3ac0900000000000000000000000000000000000000000000000000cd12403e0421514dcdac09cd3940c9002100431100c80137022a12130b78b120f83ef5ea4ec1c90000000000000000000000000000000000000000000000000000000000000000000000000000000000303132333435363738393a3b3c3d3e3f404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d6768696a6b6c6d6e6f70717273747576777800000000000000000000000000000000000000000000000000000000000000003e1221b053cdac09fa95c1fe05380efe09300afa4ec1fef52003cdb041c9000079fe053815fe093011ea95c1c53efd213242cdac09cdc041c1c93ef4214540c3ac09
""")


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _far_call(bank, address):
    return bytes(
        (0x3E, bank, 0x21, address & 0xFF, address >> 8, 0xCD, 0xAC, 0x09)
    )


def character_positions():
    """Return A-Z, a-z, 0-9, ?, ! positions in the approved layout."""
    positions = name6.character_positions() + ((3, 16), (3, 17))
    if len(positions) != CHARACTER_COUNT or len(set(positions)) != CHARACTER_COUNT:
        raise RescuePresentationError("rescue keyboard positions are not unique")
    return positions


def english_keyboard_map(rom):
    """Return the player-name map with SPACE removed and ``?!`` added."""
    rows = [
        bytearray(row)
        for row in zip(*[iter(name6.english_keyboard_map(rom))] * 20)
    ]
    blank = english.ENGLISH_CODES[" "]
    rows[2][1:6] = bytes((blank,) * 5)
    rows[12][17:19] = english.encode("?!")
    result = bytes(value for row in rows for value in row)
    if len(result) != name6.KEYBOARD_MAP_SIZE:
        raise RescuePresentationError("rescue keyboard map changed size")
    return result


def _shared_english_navigation(rom):
    at = _offset(NAVIGATION_BANK, name6.NAVIGATION_ADDRESS)
    raw = bytearray(rom[at:at + name6.NAVIGATION_SIZE])
    if len(raw) != name6.NAVIGATION_SIZE:
        raise RescuePresentationError("shared navigation table is truncated")

    mode0 = MODE0_NAVIGATION_POINTER_ADDRESS - name6.NAVIGATION_ADDRESS
    rescue = NAVIGATION_POINTER_ADDRESS - name6.NAVIGATION_ADDRESS
    current_mode0 = bytes(raw[mode0:mode0 + 2])
    current_rescue = bytes(raw[rescue:rescue + 2])
    if current_mode0 not in (
        MODE0_NAVIGATION_POINTER_ENGLISH,
        MODE0_NAVIGATION_POINTER_PATCH,
    ):
        raise RescuePresentationError("mode-0 private navigation pointer changed")
    if current_rescue not in (
        NAVIGATION_POINTER_EXPECTED,
        NAVIGATION_POINTER_PATCH,
    ):
        raise RescuePresentationError("rescue private navigation pointer changed")

    # These pointer slots occupy bytes in dead node 64. Normalize them before
    # proving the underlying player-name graph is precisely the reviewed one.
    raw[mode0:mode0 + 2] = MODE0_NAVIGATION_POINTER_ENGLISH
    raw[rescue:rescue + 2] = NAVIGATION_POINTER_EXPECTED
    actual = sha1(raw).hexdigest()
    if actual != ENGLISH_NAVIGATION_SHA1:
        raise RescuePresentationError(
            "shared English navigation SHA-1 %s, expected %s"
            % (actual, ENGLISH_NAVIGATION_SHA1)
        )
    return bytes(raw)


def english_navigation_table(rom):
    """Return a private reachable graph for all 64 rescue symbols."""
    records = [
        bytearray(record)
        for record in zip(
            *[iter(_shared_english_navigation(rom))]
            * name6.NAVIGATION_RECORD_SIZE
        )
    ]
    positions = character_positions()
    node_at = {position: node for node, position in enumerate(positions)}
    rows = {row: [] for row in range(name6.KEYBOARD_GRID_ROWS)}
    columns = {column: [] for column in range(18)}
    for node, (row, column) in enumerate(positions):
        rows[row].append(node)
        columns[column].append(node)
        records[node][4] = 9 + column * 8
        records[node][5] = 73 + row * 16
        records[node][6] = 8

    for row_nodes in rows.values():
        ring = sorted(row_nodes, key=lambda node: positions[node][1])
        for ordinal, node in enumerate(ring):
            records[node][2] = ring[ordinal - 1]
            records[node][3] = ring[(ordinal + 1) % len(ring)]

    top_controls = (LEFT_NODE, RIGHT_NODE, DELETE_NODE)
    for column, column_nodes in columns.items():
        if not column_nodes:
            continue
        block = next(
            block_index
            for block_index, (start, width) in enumerate(
                zip(name6.KEYBOARD_BLOCK_COLUMNS, name6.KEYBOARD_BLOCK_WIDTHS)
            )
            if start <= column < start + width
        )
        stack = sorted(column_nodes, key=lambda node: positions[node][0])
        for ordinal, node in enumerate(stack):
            records[node][0] = (
                stack[ordinal + 1] if ordinal + 1 < len(stack) else OK_NODE
            )
            records[node][1] = stack[ordinal - 1] if ordinal else top_controls[block]

    controls = {
        OK_NODE: (DELETE_NODE, EXCLAMATION_NODE, DELETE_NODE, LEFT_NODE),
        LEFT_NODE: (node_at[(0, 0)], OK_NODE, DELETE_NODE, RIGHT_NODE),
        RIGHT_NODE: (node_at[(0, 6)], OK_NODE, LEFT_NODE, DELETE_NODE),
        DELETE_NODE: (node_at[(0, 12)], OK_NODE, RIGHT_NODE, LEFT_NODE),
    }
    for node, neighbors in controls.items():
        records[node][:4] = bytes(neighbors)

    for node in ACTIVE_NODES:
        leaked = set(records[node][:4]) & BLANK_NODES
        if leaked:
            raise RescuePresentationError(
                "active rescue node %d reaches blank node(s) %s"
                % (node, sorted(leaked))
            )
    reached = {0}
    pending = [0]
    while pending:
        node = pending.pop()
        for target in records[node][:4]:
            if target in ACTIVE_NODES and target not in reached:
                reached.add(target)
                pending.append(target)
    if reached != ACTIVE_NODES:
        raise RescuePresentationError(
            "rescue graph leaves unreachable node(s) %s"
            % sorted(ACTIVE_NODES - reached)
        )

    result = bytes(value for record in records for value in record)
    if len(result) != name6.NAVIGATION_SIZE:
        raise RescuePresentationError("rescue navigation table changed size")
    return result


def runtime_payload(rom):
    if len(ASSEMBLED_CODE) != CODE_END - RUNTIME_ADDRESS:
        raise RescuePresentationError("assembled rescue code length changed")
    payload = bytearray(PAYLOAD_END - RUNTIME_ADDRESS)
    occupied = bytearray(len(payload))

    def place(address, raw):
        start = address - RUNTIME_ADDRESS
        end = start + len(raw)
        if not 0 <= start <= end <= len(payload):
            raise RescuePresentationError("rescue payload leaves its reservation")
        if any(occupied[start:end]):
            raise RescuePresentationError("rescue payload components overlap")
        payload[start:end] = raw
        occupied[start:end] = bytes((1,)) * len(raw)

    place(RUNTIME_ADDRESS, ASSEMBLED_CODE)
    place(NAVIGATION_ADDRESS, english_navigation_table(rom))
    place(KEYBOARD_MAP_ADDRESS, english_keyboard_map(rom))

    english_at = ALPHABET_ADDRESS - RUNTIME_ADDRESS
    if payload[english_at:english_at + CHARACTER_COUNT] != (
        rescue_password.LOCALIZED_ALPHABET_CODES
    ):
        raise RescuePresentationError("assembled English rescue alphabet changed")
    native_at = NATIVE_ALPHABET_ADDRESS - RUNTIME_ADDRESS
    if payload[native_at:native_at + CHARACTER_COUNT] != (
        rescue_password.NATIVE_ALPHABET_CODES
    ):
        raise RescuePresentationError("assembled native rescue alphabet changed")
    return bytes(payload)


def owned_ranges():
    hooks = tuple(
        (_offset(bank, address), _offset(bank, address) + len(expected))
        for bank, address, expected in (
            (PASSWORD_CACHE_BANK, PASSWORD_CACHE_ADDRESS, PASSWORD_CACHE_EXPECTED),
            (INPUT_HOOK_BANK, INPUT_HOOK_ADDRESS, INPUT_HOOK_EXPECTED),
            (SCREEN_HOOK_BANK, SCREEN_HOOK_ADDRESS, SCREEN_HOOK_EXPECTED),
            (
                SCREEN_HOOK_BANK,
                PREMODE_SCREEN_HOOK_ADDRESS,
                SCREEN_HOOK_EXPECTED,
            ),
            (HARDWARE_B_BANK, HARDWARE_B_HOOK_ADDRESS, HARDWARE_B_HOOK_EXPECTED),
        )
    )
    pointer = _offset(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
    return hooks + (
        (pointer, pointer + len(NAVIGATION_POINTER_PATCH)),
        (_offset(RUNTIME_BANK, RUNTIME_ADDRESS), _offset(RUNTIME_BANK, PAYLOAD_END)),
    )


def install(rom, verify_original=True, checksums=True):
    """Return a prerequisite-enabled ROM with English rescue I/O."""
    out = bytearray(rom)
    for bank, address, expected, target in (
        (
            PASSWORD_CACHE_BANK,
            PASSWORD_CACHE_ADDRESS,
            PASSWORD_CACHE_EXPECTED,
            PASSWORD_CACHE_WRAPPER,
        ),
        (INPUT_HOOK_BANK, INPUT_HOOK_ADDRESS, INPUT_HOOK_EXPECTED, INPUT_ADDRESS),
        (
            SCREEN_HOOK_BANK,
            SCREEN_HOOK_ADDRESS,
            SCREEN_HOOK_EXPECTED,
            SCREEN_ADDRESS,
        ),
        (
            SCREEN_HOOK_BANK,
            PREMODE_SCREEN_HOOK_ADDRESS,
            SCREEN_HOOK_EXPECTED,
            PREMODE_SCREEN_ADDRESS,
        ),
    ):
        at = _offset(bank, address)
        replacement = _far_call(RUNTIME_BANK, target)
        current = bytes(out[at:at + len(expected)])
        if verify_original and current not in (expected, replacement):
            raise RescuePresentationError(
                "rescue prerequisite at %s changed"
                % extract.location(bank, address)
            )
        out[at:at + len(replacement)] = replacement

    hardware_b = _offset(HARDWARE_B_BANK, HARDWARE_B_HOOK_ADDRESS)
    current = bytes(
        out[hardware_b:hardware_b + len(HARDWARE_B_HOOK_EXPECTED)]
    )
    if verify_original and current not in (
        HARDWARE_B_HOOK_EXPECTED,
        HARDWARE_B_HOOK_PATCH,
    ):
        raise RescuePresentationError(
            "hardware-B input handler changed at %s"
            % extract.location(HARDWARE_B_BANK, HARDWARE_B_HOOK_ADDRESS)
        )
    out[hardware_b:hardware_b + len(HARDWARE_B_HOOK_PATCH)] = (
        HARDWARE_B_HOOK_PATCH
    )

    pointer = _offset(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
    current = bytes(out[pointer:pointer + len(NAVIGATION_POINTER_PATCH)])
    if verify_original and current not in (
        NAVIGATION_POINTER_EXPECTED,
        NAVIGATION_POINTER_PATCH,
    ):
        raise RescuePresentationError(
            "rescue navigation pointer at %s changed"
            % extract.location(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
        )
    out[pointer:pointer + len(NAVIGATION_POINTER_PATCH)] = (
        NAVIGATION_POINTER_PATCH
    )

    payload = runtime_payload(out)
    runtime_at = _offset(RUNTIME_BANK, RUNTIME_ADDRESS)
    existing = bytes(out[runtime_at:runtime_at + len(payload)])
    if verify_original and any(existing) and existing != payload:
        raise RescuePresentationError(
            "reserved rescue range is not empty at %s"
            % extract.location(RUNTIME_BANK, RUNTIME_ADDRESS)
        )
    out[runtime_at:runtime_at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom):
    return {
        "modes": (5, 6, 7, 8),
        "alphabet": rescue_password.LOCALIZED_ALPHABET,
        "navigation_type": NAVIGATION_TYPE,
        "navigation_scratch": "$%04X" % NAVIGATION_SCRATCH,
        "keyboard_sha1": sha1(english_keyboard_map(rom)).hexdigest(),
        "navigation_sha1": sha1(english_navigation_table(rom)).hexdigest(),
    }
