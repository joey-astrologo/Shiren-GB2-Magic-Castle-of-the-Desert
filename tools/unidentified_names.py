#!/usr/bin/env python3
"""Install the English mode-0 unidentified-item naming screen.

Mode 0 shares native input machinery with player names and Blank Scrolls, but
its screen has one additional semantic action: node $4C cycles through the
history-filtered Fill In recalls. The player-name graph deliberately made that
old Japanese conversion node unreachable, so mode 0 receives a dedicated graph
in WRAM rather than changing the other graphical-input modes again.
"""
from hashlib import sha1

import blank_scroll
from cartridge import fix_checksums
import english
import extract
import name6


RUNTIME_BANK = 250
RUNTIME_ADDRESS = 0x4000
INPUT_ADDRESS = 0x4000
SCREEN_ADDRESS = 0x40C0
CONFIRM_ADDRESS = 0x4100
RESTORE_ADDRESS = 0x4160
RESOLVE_ADDRESS = 0x4180
CODE_END = 0x4240
NAVIGATION_ADDRESS = 0x4240
KEYBOARD_MAP_ADDRESS = 0x4480
PAYLOAD_END = 0x45C0

MODE = 0
FREE_NAME_MAXIMUM = 7
FILL_IN_MAXIMUM = 14
MAXIMUM_CHARACTERS = FREE_NAME_MAXIMUM
FILL_IN_NODE = 0x4C
NAVIGATION_TYPE = 0xF4
NAVIGATION_SCRATCH = 0xC800
CANONICAL_PREFIX = 0xFE
CANONICAL_MARKER = 0xFF
LEGACY_CANONICAL_PREFIX = 0xFF
LEGACY_CANONICAL_MARKER = 0xFE
INPUT_POSITION_ADDRESS = 0xC152
INPUT_MAXIMUM_ADDRESS = 0xC153
INPUT_BUFFER_ADDRESS = 0xC16D
NATIVE_TAIL_ADDRESS = INPUT_BUFFER_ADDRESS + FREE_NAME_MAXIMUM
ROOT_GROUP = 12
ROOT_ENTRIES = 123
ROOT_DISABLED = (69, 79, 114, 121)

NAVIGATION_BANK = name6.NAVIGATION_BANK
# The generic resolver indexes its pointer table at 16:$5F74 with an unsigned
# eight-bit type. Type $F4 therefore reads 16:$615C. Those two bytes are the
# Down/Up neighbors of node 64, which is unreachable in both English name
# graphs (nodes 62..74 remain blank). This gives mode 0 a private pointer slot
# without stealing native type $13, whose 16:$5F9A pointer drives ordinary
# nine-row lists including Adventure -> Continue/Secrets/Reset/Recap.
NAVIGATION_POINTER_ADDRESS = 0x615C
NAVIGATION_POINTER_ORIGINAL = bytes.fromhex("453B")
NAVIGATION_POINTER_PATCH = bytes(
    (NAVIGATION_SCRATCH & 0xFF, NAVIGATION_SCRATCH >> 8)
)
NAVIGATION_NODES = name6.NAVIGATION_NODES
NAVIGATION_RECORD_SIZE = name6.NAVIGATION_RECORD_SIZE
NAVIGATION_SIZE = name6.NAVIGATION_SIZE
ENGLISH_NAVIGATION_SHA1 = "03f5fa84f58bb28f92d405c6fc1ca6c47caf6ace"

INPUT_PATCH = (
    16,
    0x5B66,
    bytes((0x3E, blank_scroll.RUNTIME_BANK, 0x21,
           blank_scroll.INPUT_ADDRESS & 0xFF,
           blank_scroll.INPUT_ADDRESS >> 8, 0xCD, 0xAC, 0x09)),
    INPUT_ADDRESS,
)
SCREEN_PATCHES = (
    (16, 0x681B, bytes.fromhex("3EF4214540CDAC09"), SCREEN_ADDRESS),
    (16, 0x6A33, bytes.fromhex("3EF4214540CDAC09"), SCREEN_ADDRESS),
    (16, 0x6B98, bytes.fromhex("3EF4214540CDAC09"), SCREEN_ADDRESS),
)
CALL_PATCHES = (INPUT_PATCH,) + SCREEN_PATCHES
CONFIRM_PATCH = (
    16,
    0x5B84,
    bytes((0x3E, blank_scroll.RUNTIME_BANK, 0x21,
           blank_scroll.CONFIRM_ADDRESS & 0xFF,
           blank_scroll.CONFIRM_ADDRESS >> 8, 0xCD, 0xAC, 0x09)),
    CONFIRM_ADDRESS,
)
CALL_PATCHES += (CONFIRM_PATCH,)

DISPLAY_TRAMPOLINE_BANK = 0x78
DISPLAY_CALL_ADDRESS = 0x480B
DISPLAY_TRAMPOLINE_ADDRESS = 0x7E90
DISPLAY_CALL_ORIGINAL = bytes.fromhex("CD094C")
DISPLAY_CALL_PATCH = bytes(
    (
        0xCD,
        DISPLAY_TRAMPOLINE_ADDRESS & 0xFF,
        DISPLAY_TRAMPOLINE_ADDRESS >> 8,
    )
)
DISPLAY_TRAMPOLINE_ORIGINAL = bytes(16)
DISPLAY_TRAMPOLINE_PATCH = bytes(
    (
        0x3E,
        RUNTIME_BANK,
        0x21,
        RESOLVE_ADDRESS & 0xFF,
        RESOLVE_ADDRESS >> 8,
        0xC3,
        0xAC,
        0x09,
        # Preserve the slot ordinal in C across FarDispatch, then restore it
        # to A before entering the native 78:$4C09 pointer calculation.
        0x79,
        0xCD,
        0x09,
        0x4C,
        0xC9,
        0x00,
        0x00,
        0x00,
    )
)
RAW_PATCHES = (
    (
        DISPLAY_TRAMPOLINE_BANK,
        DISPLAY_CALL_ADDRESS,
        DISPLAY_CALL_ORIGINAL,
        DISPLAY_CALL_PATCH,
    ),
    (
        DISPLAY_TRAMPOLINE_BANK,
        DISPLAY_TRAMPOLINE_ADDRESS,
        DISPLAY_TRAMPOLINE_ORIGINAL,
        DISPLAY_TRAMPOLINE_PATCH,
    ),
)


class UnidentifiedNameError(ValueError):
    """The shared keyboard prerequisite or mode-0 reservation changed."""


# Assembled from tools/unidentified_names.asm at $FA:$4000-$423F.
ASSEMBLED_CODE = bytes.fromhex("""
fa95c1a7c28b4079fe4c282bfe50ca7a40fe4dd28b40fa96c13c2805c5cdbe41c13e07ea53c13efb212040cdac093e07ea53c1cd6041c93e07ea53c13e12211552cdac09fa96c13c283a3d4f216dc13e0ccda01f793dea52c1216dc10600093e
0e914728063e24220520fc3eff773e0eea53c1cdf041cdde40c9fa96c13c280bcdbe41c93e07ea53c118eb3efb212040c3ac09000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
3efd213242cdac09cdde40afe04f218044114098011410cdcc0aafe04fc92140421100c80137022a12130b78b120f83ef4ea4ec1c90000000000000000000000fa95c1a728083efb218040c3ac09cd60413e1221f750cdac0979fef8c0fa96c1
3cc83dc547626b11f8ff19f070f53e02e0703efe223eff2278223eff0605220520fcf1e070c1c9000000000000000000000000000000000000000000000000003effea74c13ed52175c10606220520fcc9000000000000000000000000000000
3e7821987ecdac097efefe280bfeffc0237efefe280a2bc9237efeff28022bc9234e79fe7b38032b2bc923e5d5626b3e0ccda01fe109545d3e02e070e1c9afea52c13effea96c1216dc106073ed5220520fc06073e24220520fc3eff77ea74c1
79fe50c0cdf0413e07ea53c1cd6041c911b0ff216dc1060e3e04cd5b0a3eff123e07ea53c13e04216f4dcdac093e0eea53c13e1121c246c3ac090000000000000000000000000000000000000000000000000000000000000000000000000000
""")


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _runtime_offset(address):
    return _offset(RUNTIME_BANK, address)


def _far_call(address):
    return bytes(
        (0x3E, RUNTIME_BANK, 0x21, address & 0xFF, address >> 8,
         0xCD, 0xAC, 0x09)
    )


def english_keyboard_map(rom):
    """Return the 20x16 English mode-0 map with its Fill In control."""
    raw = name6.english_keyboard_map(rom)
    rows = [bytearray(row) for row in zip(*[iter(raw)] * 20)]
    rows[2][7:14] = english.encode("FILL IN")
    result = bytes(value for row in rows for value in row)
    if len(result) != name6.KEYBOARD_MAP_SIZE:
        raise UnidentifiedNameError("mode-0 keyboard map changed size")
    return result


def english_navigation_table(rom):
    """Restore node $4C only in mode 0's copy of the English graph."""
    at = _offset(NAVIGATION_BANK, name6.NAVIGATION_ADDRESS)
    raw = bytearray(rom[at:at + NAVIGATION_SIZE])
    redirect = NAVIGATION_POINTER_ADDRESS - name6.NAVIGATION_ADDRESS
    current = bytes(raw[redirect:redirect + len(NAVIGATION_POINTER_PATCH)])
    if current not in (NAVIGATION_POINTER_ORIGINAL, NAVIGATION_POINTER_PATCH):
        raise UnidentifiedNameError(
            "private navigation pointer source at %s changed"
            % extract.location(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
        )
    # Idempotent installs see the private $C800 pointer in unreachable node 64.
    # Normalize that dead pair before hashing and cloning the shared graph.
    raw[redirect:redirect + len(NAVIGATION_POINTER_ORIGINAL)] = (
        NAVIGATION_POINTER_ORIGINAL
    )
    raw = bytes(raw)
    actual = sha1(raw).hexdigest()
    if actual != ENGLISH_NAVIGATION_SHA1:
        raise UnidentifiedNameError(
            "shared English navigation SHA-1 %s, expected %s"
            % (actual, ENGLISH_NAVIGATION_SHA1)
        )
    records = [
        bytearray(record)
        for record in zip(*[iter(raw)] * NAVIGATION_RECORD_SIZE)
    ]

    positions = name6.character_positions()
    node_at = {position: node for node, position in enumerate(positions)}
    columns = {column: [] for column in range(18)}
    for node, (row, column) in enumerate(positions):
        columns[column].append(node)

    bottom_controls = (75, 76, 77)
    for column, nodes in columns.items():
        if not nodes:
            continue
        block = next(
            block_index
            for block_index, (start, width) in enumerate(
                zip(name6.KEYBOARD_BLOCK_COLUMNS, name6.KEYBOARD_BLOCK_WIDTHS)
            )
            if start <= column < start + width
        )
        bottom = max(nodes, key=lambda node: positions[node][0])
        records[bottom][0] = bottom_controls[block]

    controls = {
        75: (78, node_at[(4, 0)], 77, 76),
        76: (79, node_at[(4, 6)], 75, 77),
        77: (80, node_at[(3, 15)], 76, 75),
        78: (node_at[(0, 0)], 75, 80, 79),
        79: (node_at[(0, 6)], 76, 78, 80),
        80: (node_at[(0, 12)], 77, 79, 78),
    }
    for node, neighbors in controls.items():
        records[node][:4] = bytes(neighbors)

    active = set(range(len(name6.KEYBOARD_CHARACTERS))) | set(controls)
    blanks = set(range(len(name6.KEYBOARD_CHARACTERS), 75))
    for node in active:
        leaked = set(records[node][:4]) & blanks
        if leaked:
            raise UnidentifiedNameError(
                "active mode-0 node %d reaches blank node(s) %s"
                % (node, sorted(leaked))
            )
    reached = {0}
    pending = [0]
    while pending:
        node = pending.pop()
        for target in records[node][:4]:
            if target in active and target not in reached:
                reached.add(target)
                pending.append(target)
    if reached != active:
        raise UnidentifiedNameError(
            "mode-0 graph leaves unreachable node(s) %s"
            % sorted(active - reached)
        )
    result = bytes(value for record in records for value in record)
    if len(result) != NAVIGATION_SIZE:
        raise UnidentifiedNameError("mode-0 navigation table changed size")
    return result


def runtime_payload(rom):
    if len(ASSEMBLED_CODE) != CODE_END - RUNTIME_ADDRESS:
        raise UnidentifiedNameError("assembled mode-0 code length changed")
    payload = bytearray(PAYLOAD_END - RUNTIME_ADDRESS)

    def place(address, raw):
        start = address - RUNTIME_ADDRESS
        end = start + len(raw)
        if not 0 <= start <= end <= len(payload):
            raise UnidentifiedNameError("mode-0 payload leaves its reservation")
        if any(payload[start:end]):
            raise UnidentifiedNameError("mode-0 payload components overlap")
        payload[start:end] = raw

    place(RUNTIME_ADDRESS, ASSEMBLED_CODE)
    place(NAVIGATION_ADDRESS, english_navigation_table(rom))
    place(KEYBOARD_MAP_ADDRESS, english_keyboard_map(rom))
    return bytes(payload)


def validate_root_catalog(roots):
    """Prove every recallable translated root fits the presentation field."""
    required = set(range(ROOT_ENTRIES))
    missing = required - set(roots)
    if missing:
        raise UnidentifiedNameError(
            "translated item roots are missing indices: %s"
            % ", ".join(map(str, sorted(missing)))
        )

    rows = []
    disabled = set(ROOT_DISABLED)
    for index in range(ROOT_ENTRIES):
        name = roots[index]
        try:
            raw = english.encode(name)
        except (KeyError, ValueError) as exc:
            raise UnidentifiedNameError(
                "item root %d cannot be recalled: %s" % (index, exc)
            ) from exc
        is_sentinel = bool(raw) and raw[0] == 0x21
        if index in disabled:
            if not is_sentinel:
                raise UnidentifiedNameError(
                    "disabled item root %d must retain the $21 sentinel" % index
                )
            continue
        if is_sentinel:
            raise UnidentifiedNameError(
                "enabled item root %d begins with the $21 sentinel" % index
            )
        if len(raw) > FILL_IN_MAXIMUM:
            raise UnidentifiedNameError(
                "item root %d needs %d recall cells, maximum is %d"
                % (index, len(raw), FILL_IN_MAXIMUM)
            )
        rows.append((index, name, len(raw)))

    maximum = max(length for _index, _name, length in rows)
    return {
        "free_name_maximum": FREE_NAME_MAXIMUM,
        "fill_in_maximum": FILL_IN_MAXIMUM,
        "longest": [
            {"root_index": index, "name": name, "characters": length}
            for index, name, length in rows
            if length == maximum
        ],
    }


def owned_ranges():
    patches = tuple(
        (_offset(bank, address), _offset(bank, address) + len(expected))
        for bank, address, expected, _target in CALL_PATCHES
    )
    raw_patches = tuple(
        (_offset(bank, address), _offset(bank, address) + len(expected))
        for bank, address, expected, _replacement in RAW_PATCHES
    )
    pointer = _offset(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
    return patches + raw_patches + (
        (pointer, pointer + len(NAVIGATION_POINTER_PATCH)),
        (_runtime_offset(RUNTIME_ADDRESS), _runtime_offset(PAYLOAD_END)),
    )


def install(rom, verify_original=True, checksums=True):
    """Return a name6/Blank-Scroll-enabled ROM with localized mode 0."""
    out = bytearray(rom)
    for bank, address, expected, target in CALL_PATCHES:
        at = _offset(bank, address)
        current = bytes(out[at:at + len(expected)])
        replacement = _far_call(target)
        if verify_original and current not in (expected, replacement):
            raise UnidentifiedNameError(
                "mode-0 prerequisite at %s is not installed"
                % extract.location(bank, address)
            )
        out[at:at + len(replacement)] = replacement

    for bank, address, expected, replacement in RAW_PATCHES:
        at = _offset(bank, address)
        current = bytes(out[at:at + len(expected)])
        if verify_original and current not in (expected, replacement):
            raise UnidentifiedNameError(
                "mode-0 display prerequisite at %s changed"
                % extract.location(bank, address)
            )
        out[at:at + len(replacement)] = replacement

    pointer = _offset(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
    current = bytes(out[pointer:pointer + 2])
    if verify_original and current not in (
        NAVIGATION_POINTER_ORIGINAL, NAVIGATION_POINTER_PATCH
    ):
        raise UnidentifiedNameError(
            "navigation pointer at %s changed"
            % extract.location(NAVIGATION_BANK, NAVIGATION_POINTER_ADDRESS)
        )
    out[pointer:pointer + 2] = NAVIGATION_POINTER_PATCH

    payload = runtime_payload(out)
    at = _runtime_offset(RUNTIME_ADDRESS)
    existing = bytes(out[at:at + len(payload)])
    if verify_original and any(existing) and existing != payload:
        raise UnidentifiedNameError(
            "reserved mode-0 bank is not empty at %s"
            % extract.location(RUNTIME_BANK, RUNTIME_ADDRESS)
        )
    out[at:at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom):
    navigation = english_navigation_table(rom)
    keyboard = english_keyboard_map(rom)
    return {
        "mode": MODE,
        "free_name_maximum": FREE_NAME_MAXIMUM,
        "fill_in_maximum": FILL_IN_MAXIMUM,
        "fill_in_node": FILL_IN_NODE,
        "navigation_type": NAVIGATION_TYPE,
        "navigation_scratch": "$%04X" % NAVIGATION_SCRATCH,
        "canonical_signature": "$%02X $%02X <root>"
        % (CANONICAL_PREFIX, CANONICAL_MARKER),
        "legacy_canonical_signature": "$%02X $%02X <root>"
        % (LEGACY_CANONICAL_PREFIX, LEGACY_CANONICAL_MARKER),
        "navigation_sha1": sha1(navigation).hexdigest(),
        "keyboard_sha1": sha1(keyboard).hexdigest(),
        "path_from_A_to_fill_in": ["up", "right", "up"],
    }
