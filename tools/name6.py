#!/usr/bin/env python3
"""Install six-character English player names without changing native records.

The original diary stores four visible name bytes plus a terminator at offsets
``$16..$1A``.  Its final four bytes (offsets ``$66..$69``) have no native
consumer, so this patch stores characters five and six there with a two-byte
marker.  Old saves have no marker and therefore keep their original names.

Ranking records must remain exactly 32 bytes.  A versioned two-byte suffix
table is instead stored in otherwise unused SRAM bank-3 space and indexed by
the same category/physical-slot pair as the native record.  The native ranking
sort order is untouched.
"""
from hashlib import sha1

from cartridge import fix_checksums
import english
import english_font
import extract


RUNTIME_BANK = 253
RUNTIME_ADDRESS = 0x4000
RUNTIME_LIMIT = 0x8000

GET_ADDRESS = 0x41C2
SET_ADDRESS = 0x4030
DEFAULT_ADDRESS = 0x4075
MAXIMUM_ADDRESS = 0x407B
SCREEN_ADDRESS = 0x4232
INPUT_ADDRESS = 0x41D9
RANK_WRITE_ADDRESS = 0x4110
RANK_LOAD_ADDRESS = 0x4155
RANK_RENDER_ADDRESS = 0x41A0
CODE_END = 0x4250

CHARACTER_TABLE_ADDRESS = 0x4300
DEFAULT_NAME_ADDRESS = 0x4350
RANK_HEADER_ADDRESS = 0x4360
KEYBOARD_MAP_ADDRESS = 0x4400
KEYBOARD_MAP_END = 0x4540
GLYPH_LOW_ADDRESS = 0x4600
GLYPH_LOW_START = 0x00
GLYPH_LOW_END = 0x25
GLYPH_HIGH_ADDRESS = 0x4850
GLYPH_HIGH_START = 0x30
GLYPH_HIGH_END = 0x58
GLYPH_STRIDE = 16
PAYLOAD_END = 0x4AD0

DIARY_PREFIX_ADDRESS = 0xC252
DIARY_SUFFIX_ADDRESS = 0xC2A2
DIARY_MARKER_ADDRESS = 0xC2A4
DIARY_MARKER = bytes((0xA5, 0x5A))
DIARY_SIZE = 0x6A
DIARY_SUFFIX_OFFSETS = (0x66, 0x67)
DIARY_MARKER_OFFSETS = (0x68, 0x69)

# Demo playback does not create a new diary from the localized default-name
# routine.  Instead, the engine copies one of fourteen complete, embedded
# 0x6A-byte diary snapshots into the ordinary $C23C record.  Localize those
# snapshots using the same prefix/suffix/marker contract as live saves.
REPLAY_POINTER_BANK = 11
REPLAY_POINTER_ADDRESS = 0x5FB3
REPLAY_POINTER_COUNT = 14
REPLAY_POINTER_ENTRY_SIZE = 3
REPLAY_POINTER_BYTES = bytes.fromhex(
    "0040D20060D20040D30060D30040D00060D00040D10060D1"
    "0040D40060D40040D50060D50040D60060D6"
)
REPLAY_NAME_OFFSET = 0x16
REPLAY_NAME_FIELD_SIZE = 5
REPLAY_ORIGINAL_NAME_FIELD = bytes.fromhex("8BA9ADFF00")  # シレン + tail
REPLAY_ORIGINAL_TAIL = bytes(4)
REPLAY_RECORD_SHA1S = (
    "aec0b59d8635f35c498e3418b448b0631d1e723a",
    "6d0abc13936f603fd5cd5cadd9f517c573a27b0f",
    "6d0abc13936f603fd5cd5cadd9f517c573a27b0f",
    "be079aed2c0aa07013cbbaff73459e8ca91cddf9",
    "b231366f41208c8cf613bdbd66d4473a0fe7593c",
    "fd655da66d814ddbcc3c2f55251c18808aef3980",
    "76341660e3a21a0968a3bc92de154c5a892a5693",
    "1fa575f20972f754924d202a677a888117d63420",
    "971eed66b04f58726009ba4c3aed8743d9843203",
    "68090e81179017d1abe05a76c4d206fc4d86b7f6",
    "3ef50edae033300af0933b396607f2142790527c",
    "ec8e27a4b4138328b701445853f25fe9eb2b2cc3",
    "f5320bd18050a3c50acbdfc5516d76a70b4d2ec1",
    "fc9d6da415f86b1cf43deb8860a070addf51c05c",
)
REPLAY_NON_SECRETS_EVENTS = (0, 3)
REPLAY_TITLE_OBSERVED_EVENTS = (0, 1)
REPLAY_SECRETS_EVENTS = (4, 13)
REPLAY_TITLE_SELECTOR = (5, 0x40E6)
REPLAY_TITLE_SELECTOR_BYTES = bytes.fromhex("21E9C02AE60147CD2F1D")
REPLAY_SECRETS_SELECTOR = (16, 0x796B)
REPLAY_SECRETS_SELECTOR_BYTES = bytes.fromhex(
    "47C5CD2546C13E048047CD2F1D"
)

RANKING_SRAM_BANK = 3
RANKING_SRAM_HEADER = 0xBCD8
RANKING_SRAM_SUFFIXES = 0xBCDC
RANKING_SRAM_HEADER_BYTES = b"N6R1"
RANKING_CATEGORIES = 5
RANKING_SLOTS = 50
RANKING_SUFFIX_SIZE = 2
RANKING_SRAM_SUFFIX_BYTES = (
    RANKING_CATEGORIES * RANKING_SLOTS * RANKING_SUFFIX_SIZE
)
RANKING_SRAM_END = RANKING_SRAM_SUFFIXES + RANKING_SRAM_SUFFIX_BYTES
RANKING_NATIVE_END = 0xBCD8
SRAM_SIGNATURE_ADDRESS = 0xBFF8

KEYBOARD_MAP_BANK = 4
KEYBOARD_MAP_SOURCE_ADDRESS = 0x49C4
KEYBOARD_MAP_SIZE = 20 * 16
KEYBOARD_MAP_SHA1 = "cb1943e9be1cd7d9ad18b678557a48bf561c46a5"

NAVIGATION_BANK = 16
NAVIGATION_ADDRESS = 0x5F9C
NAVIGATION_NODES = 81
NAVIGATION_RECORD_SIZE = 7
NAVIGATION_SIZE = NAVIGATION_NODES * NAVIGATION_RECORD_SIZE
NAVIGATION_SHA1 = "7ba13e1ec4eababe201fc8fa178ba55144fd84dc"

MAX_VISIBLE_CHARACTERS = 6
DEFAULT_NAME = "Shiren"
UPPERCASE_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE_CHARACTERS = "abcdefghijklmnopqrstuvwxyz"
UTILITY_CHARACTERS = "0123456789"
KEYBOARD_CHARACTERS = (
    UPPERCASE_CHARACTERS + LOWERCASE_CHARACTERS + UTILITY_CHARACTERS
)
KEYBOARD_BLOCKS = (
    ("ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVWXY"),
    ("Z    ", "abcde", "fghij", "klmno", "pqrst"),
    ("uvwxy ", "z     ", "012345", "6789  ", "      "),
)
KEYBOARD_BLOCK_COLUMNS = (0, 6, 12)
KEYBOARD_BLOCK_WIDTHS = (5, 5, 6)
KEYBOARD_GRID_ROWS = 5
REMOVED_CHARACTERS = ".,'-?!():/[]+~%"
LEFT_CURSOR_CHARACTER = "["
RIGHT_CURSOR_CHARACTER = "]"
CURSOR_GLYPH_ROWS = {
    LEFT_CURSOR_CHARACTER: (
        "...#....",
        "..##....",
        ".###....",
        "####....",
        ".###....",
        "..##....",
        "...#....",
        "........",
    ),
    RIGHT_CURSOR_CHARACTER: (
        "#.......",
        "##......",
        "###.....",
        "####....",
        "###.....",
        "##......",
        "#.......",
        "........",
    ),
}


class Name6Error(ValueError):
    """A source routine, save-space contract, or generated payload changed."""


# Assembled from tools/name6.asm at $FD:$4000.  Keeping the bytes here avoids
# adding RGBDS as a build-time dependency; the test suite reassembles the source
# when RGBDS is available and requires an exact match.
ASSEMBLED_CODE = bytes.fromhex(
    "2152C206042AFEFF282212130520F6FAA4C2FEA52016FAA5C2FE5A200F"
    "21A2C206022AFEFF280512130520F63EFF12C93EFF2152C20605220520FC"
    "21A2C20602220520FC3EA5EAA4C23E5AEAA5C22152C206041AFEFF281C"
    "FED5281822130520F221A2C206021AFEFF2809FED5280522130520F2C9"
    "115043C330403E12212D50CDAC09FA95C1FE04C03E06EA53C1C93EF4"
    "214540CDAC09AFE04F210044114098011410CDCC0AAFE04FC979FE4D30"
    "0F060021004309463E12214C52C3AC093E12211552C3AC0921D8BC1160"
    "4306041ABEC013230520F8AFC9CDC640C821DCBC01F40116FF7A220B78"
    "B120F921D8BC11604306041A22130520FAAFC921DCBC78A72807016400"
    "093D20FC7B875F160019C9C5D53E0B21575FCDAC09AFEA0041545D2100"
    "DD0620CD5B0AD1C13E03EA0041C5D5CDD840D1C1CDFB40FAA4C2FEA5"
    "2010FAA5C2FE5A2009FAA2C222FAA3C277C93EFF2277C93EFFEAA5CF"
    "EAA6CFC53E0B212555CDAC09C17BFEFFC8C5D53E0B21575FCDAC09AF"
    "EA00411100CF0620CD5B0AD1C13E03EA0041C5D5CDC640D1C1C0C5D5"
    "CDFB402AEAA5CF7EEAA6CFD1C1C9210FCF06042AFEFF281412130520F6"
    "21A5CF06022AFEFF280512130520F63EFF12C9D5CD0040E101FFFF2A03"
    "3C20FB2152C22A3C20FC545DC979FE3EDAAA40FE4BD82819FE4DD8FE4E"
    "2808FE4F20060E4E18020E4F3E12211552C3AC0906243E12214C52C3AC"
    "09"
) + bytes(43) + bytes.fromhex(
    "CD8F40AFE04F21"
    "0046110090015002CD6B0A215048110093018002C36B0A"
)


ROUTINE_PATCHES = (
    (
        "default_name",
        11,
        0x42EB,
        bytes.fromhex("AF066ACD450C1E16160019113CC2190E1D3E07CDA01FC9"),
        DEFAULT_ADDRESS,
    ),
    (
        "name_getter",
        11,
        0x4B2F,
        bytes.fromhex("D5AF066ACD450C1E16160019113CC219D1CD500A545DC9"),
        GET_ADDRESS,
    ),
    (
        "name_setter",
        11,
        0x4B46,
        bytes.fromhex("D5AF066ACD450C1E16160019113CC219545DE1CD500AC9"),
        SET_ADDRESS,
    ),
    (
        "ranking_load",
        11,
        0x5639,
        bytes.fromhex("C5CD2555C17BFEFFC8D5CD575F3E00EA00411100CF0620CD5B0AD1C9"),
        RANK_LOAD_ADDRESS,
    ),
    (
        "ranking_name_renderer",
        11,
        0x56E2,
        bytes.fromhex("D5AF0620CD450C1E0F1600191100CF19D10604CD5B0A3EFF12C9"),
        RANK_RENDER_ADDRESS,
    ),
    (
        "ranking_write",
        11,
        0x5F1C,
        bytes.fromhex("CD575F3E00EA0041545D2100DD0620CD5B0AC9"),
        RANK_WRITE_ADDRESS,
    ),
)

CALL_PATCHES = (
    (
        "mode4_maximum",
        0xF4,
        0x4066,
        bytes.fromhex("3E12212D50CDAC09"),
        MAXIMUM_ADDRESS,
    ),
    (
        "mode4_input",
        16,
        0x5B66,
        bytes.fromhex("3E12211552CDAC09"),
        INPUT_ADDRESS,
    ),
    (
        "create_screen",
        16,
        0x7859,
        bytes.fromhex("3EF4214540CDAC09"),
        SCREEN_ADDRESS,
    ),
    (
        "rename_screen",
        16,
        0x78C9,
        bytes.fromhex("3EF4214540CDAC09"),
        SCREEN_ADDRESS,
    ),
)


def _offset(bank, address):
    return extract.file_offset(bank, address)


def _runtime_offset(address):
    return _offset(RUNTIME_BANK, address)


def _far_transfer(address, size, tail):
    opcode = 0xC3 if tail else 0xCD
    raw = bytes(
        (
            0x3E,
            RUNTIME_BANK,
            0x21,
            address & 0xFF,
            address >> 8,
            opcode,
            0xAC,
            0x09,
        )
    )
    if len(raw) > size:
        raise Name6Error("name6 far transfer does not fit its patch site")
    return raw + bytes(size - len(raw))


def character_bytes():
    raw = english.encode(KEYBOARD_CHARACTERS)
    if (
        len(UPPERCASE_CHARACTERS) != 26
        or len(LOWERCASE_CHARACTERS) != 26
        or len(UTILITY_CHARACTERS) != 10
        or len(raw) != 62
    ):
        raise Name6Error("English name-entry character plan changed")
    return raw


def character_positions():
    """Return each character node's exact (row, column) in the 18-cell grid."""
    positions = {}
    for block_index, block in enumerate(KEYBOARD_BLOCKS):
        if len(block) != KEYBOARD_GRID_ROWS:
            raise Name6Error("English name-entry block has the wrong row count")
        width = KEYBOARD_BLOCK_WIDTHS[block_index]
        for row, text in enumerate(block):
            if len(text) != width:
                raise Name6Error("English name-entry row has the wrong width")
            for column, character in enumerate(text):
                if character == " ":
                    continue
                if character in positions:
                    raise Name6Error("English name-entry layout repeats a character")
                positions[character] = (
                    row,
                    KEYBOARD_BLOCK_COLUMNS[block_index] + column,
                )
    if set(positions) != set(KEYBOARD_CHARACTERS):
        raise Name6Error("English name-entry layout does not match its character table")
    return tuple(positions[character] for character in KEYBOARD_CHARACTERS)


def default_name_bytes():
    raw = english.encode(DEFAULT_NAME) + b"\xFF"
    if len(DEFAULT_NAME) != MAX_VISIBLE_CHARACTERS or len(raw) != 7:
        raise Name6Error("default name must contain exactly six characters")
    return raw


def replay_records(rom, verify_original=True):
    """Return the fourteen event-ID-indexed embedded diary snapshots.

    The native replay dispatcher indexes a three-byte ``address, bank`` table
    directly with the event ID.  Guard both that ordering and every complete
    diary record so a ROM revision cannot silently redirect this patch.
    """
    table_at = _offset(REPLAY_POINTER_BANK, REPLAY_POINTER_ADDRESS)
    raw = bytes(
        rom[
            table_at:
            table_at + REPLAY_POINTER_COUNT * REPLAY_POINTER_ENTRY_SIZE
        ]
    )
    if raw != REPLAY_POINTER_BYTES:
        raise Name6Error(
            "replay diary pointer table at %s changed"
            % extract.location(REPLAY_POINTER_BANK, REPLAY_POINTER_ADDRESS)
        )

    if verify_original:
        for label, (bank, address), expected in (
            (
                "title replay selector",
                REPLAY_TITLE_SELECTOR,
                REPLAY_TITLE_SELECTOR_BYTES,
            ),
            (
                "Secrets replay selector",
                REPLAY_SECRETS_SELECTOR,
                REPLAY_SECRETS_SELECTOR_BYTES,
            ),
        ):
            at = _offset(bank, address)
            actual = bytes(rom[at:at + len(expected)])
            if actual != expected:
                raise Name6Error(
                    "%s at %s changed"
                    % (label, extract.location(bank, address))
                )

    records = []
    for event_id in range(REPLAY_POINTER_COUNT):
        entry = raw[
            event_id * REPLAY_POINTER_ENTRY_SIZE:
            (event_id + 1) * REPLAY_POINTER_ENTRY_SIZE
        ]
        address = entry[0] | (entry[1] << 8)
        bank = entry[2]
        at = _offset(bank, address)
        record = bytes(rom[at:at + DIARY_SIZE])
        if len(record) != DIARY_SIZE:
            raise Name6Error(
                "replay event %d record at %s is truncated"
                % (event_id, extract.location(bank, address))
            )
        if verify_original:
            actual = sha1(record).hexdigest()
            expected = REPLAY_RECORD_SHA1S[event_id]
            if actual != expected:
                raise Name6Error(
                    "replay event %d record at %s SHA-1 %s, expected %s"
                    % (
                        event_id,
                        extract.location(bank, address),
                        actual,
                        expected,
                    )
                )
            if (
                record[
                    REPLAY_NAME_OFFSET:
                    REPLAY_NAME_OFFSET + REPLAY_NAME_FIELD_SIZE
                ]
                != REPLAY_ORIGINAL_NAME_FIELD
                or record[DIARY_SUFFIX_OFFSETS[0]:DIARY_SIZE]
                != REPLAY_ORIGINAL_TAIL
            ):
                raise Name6Error(
                    "replay event %d name storage at %s changed"
                    % (event_id, extract.location(bank, address))
                )
        records.append(
            {
                "event_id": event_id,
                "bank": bank,
                "address": address,
                "offset": at,
                "sha1": REPLAY_RECORD_SHA1S[event_id],
            }
        )
    return tuple(records)


def localized_replay_name_parts():
    """Return the native field and diary extension for embedded replays."""
    raw = default_name_bytes()
    return raw[:4] + b"\xFF", raw[4:6] + DIARY_MARKER


def install_replay_names(rom, verify_original=True):
    """Install ``Shiren`` in every embedded demo/Secrets diary snapshot."""
    out = bytearray(rom)
    native, tail = localized_replay_name_parts()
    for record in replay_records(out, verify_original=verify_original):
        at = record["offset"]
        out[
            at + REPLAY_NAME_OFFSET:
            at + REPLAY_NAME_OFFSET + REPLAY_NAME_FIELD_SIZE
        ] = native
        out[
            at + DIARY_SUFFIX_OFFSETS[0]:
            at + DIARY_MARKER_OFFSETS[-1] + 1
        ] = tail
    return bytes(out)


def keyboard_glyph_bytes(start, end, approved=None):
    """Return approved glyphs in the keyboard's color-0/2/3 2bpp format."""
    approved = approved or english_font.load_approved()
    characters = {code: character for character, code in english.ENGLISH_CODES.items()}
    try:
        raw = bytearray()
        for code in range(start, end):
            character = characters[code]
            rows = CURSOR_GLYPH_ROWS.get(character, approved.rows[character])
            for row in english_font.glyph_pixels(rows, style=approved.style):
                ink = sum(
                    0x80 >> column
                    for column, color in enumerate(row)
                    if color == english_font.INK_COLOR
                )
                ink_and_shadow = sum(
                    0x80 >> column
                    for column, color in enumerate(row)
                    if color in (
                        english_font.SHADOW_COLOR,
                        english_font.INK_COLOR,
                    )
                )
                raw += bytes((ink, ink_and_shadow))
    except KeyError as exc:
        raise Name6Error("keyboard glyph span contains an unowned code") from exc
    if len(raw) != (end - start) * GLYPH_STRIDE:
        raise Name6Error("keyboard glyph span has the wrong size")
    return raw


def _source_keyboard_map(rom):
    at = _offset(KEYBOARD_MAP_BANK, KEYBOARD_MAP_SOURCE_ADDRESS)
    raw = bytes(rom[at:at + KEYBOARD_MAP_SIZE])
    if len(raw) != KEYBOARD_MAP_SIZE:
        raise Name6Error("ROM is too small for the mode-4 keyboard map")
    actual = sha1(raw).hexdigest()
    if actual != KEYBOARD_MAP_SHA1:
        raise Name6Error(
            "mode-4 keyboard map SHA-1 %s, expected %s"
            % (actual, KEYBOARD_MAP_SHA1)
        )
    return raw


def english_keyboard_map(rom):
    """Return the mode-4-only 20x16 English tile-ID map."""
    rows = [
        bytearray(row)
        for row in zip(*[iter(_source_keyboard_map(rom))] * 20)
    ]
    blank = english.ENGLISH_CODES[" "]
    # Native labels and raw keyboard glyphs use alternating continuation rows.
    # Clear the complete interior before placing the one-cell English glyphs.
    for row in range(2, 16):
        rows[row][1:19] = bytes((blank,) * 18)

    # Exact five/five/six-cell columns with real blank separator tiles.  Z
    # begins the middle block, lowercase continues into the right, and the
    # six-wide right block holds 012345 without sacrificing either separator.
    for block_index, block in enumerate(KEYBOARD_BLOCKS):
        start_column = 1 + KEYBOARD_BLOCK_COLUMNS[block_index]
        width = KEYBOARD_BLOCK_WIDTHS[block_index]
        for display_row, text in enumerate(block):
            row = 6 + display_row * 2
            rows[row][
                start_column:start_column + width
            ] = english.encode(text)

    def put(row, column, text):
        raw = english.encode(text)
        rows[row][column:column + len(raw)] = raw

    put(2, 1, "SPACE")
    put(2, 15, "OK")
    rows[4][1] = english.ENGLISH_CODES[LEFT_CURSOR_CHARACTER]
    rows[4][8] = english.ENGLISH_CODES[RIGHT_CURSOR_CHARACTER]
    put(4, 15, "DEL")

    result = bytes(value for row in rows for value in row)
    if len(result) != KEYBOARD_MAP_SIZE:
        raise Name6Error("English keyboard map is not 20x16 tiles")
    return result


def _source_navigation_table(rom):
    at = _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS)
    raw = bytes(rom[at:at + NAVIGATION_SIZE])
    if len(raw) != NAVIGATION_SIZE:
        raise Name6Error("ROM is too small for the mode-4 navigation table")
    actual = sha1(raw).hexdigest()
    if actual != NAVIGATION_SHA1:
        raise Name6Error(
            "mode-4 navigation SHA-1 %s, expected %s"
            % (actual, NAVIGATION_SHA1)
        )
    return raw


def english_navigation_table(rom):
    """Return mode 4's navigation graph with all blank controls skipped."""
    records = [
        bytearray(raw)
        for raw in zip(
            *[iter(_source_navigation_table(rom))] * NAVIGATION_RECORD_SIZE
        )
    ]

    # The first four bytes are Down, Up, Left and Right.  Rebuild those edges
    # and cursor coordinates from the exact five/five/six-column mockup.
    positions = character_positions()
    node_at = {position: node for node, position in enumerate(positions)}
    rows = {row: [] for row in range(KEYBOARD_GRID_ROWS)}
    columns = {column: [] for column in range(18)}
    for node, (row, column) in enumerate(positions):
        rows[row].append(node)
        columns[column].append(node)
        records[node][4] = 9 + column * 8
        records[node][5] = 73 + row * 16
        records[node][6] = 8

    # Horizontal movement follows each displayed row, skipping its intentional
    # holes and wrapping from the final visible cell to the first.
    for row in range(KEYBOARD_GRID_ROWS):
        ring = sorted(rows[row], key=lambda node: positions[node][1])
        for ordinal, node in enumerate(ring):
            records[node][2] = ring[ordinal - 1]
            records[node][3] = ring[(ordinal + 1) % len(ring)]

    # Vertical movement stays in the displayed column and skips holes.  The
    # top/bottom edges lead into the matching control region.
    top_controls = (78, 79, 80)
    bottom_controls = (75, 77, 77)
    for column in range(18):
        stack = sorted(columns[column], key=lambda node: positions[node][0])
        if not stack:
            continue
        block = next(
            block_index
            for block_index, (start, width) in enumerate(
                zip(KEYBOARD_BLOCK_COLUMNS, KEYBOARD_BLOCK_WIDTHS)
            )
            if start <= column < start + width
        )
        for ordinal, node in enumerate(stack):
            records[node][0] = (
                stack[ordinal + 1]
                if ordinal + 1 < len(stack)
                else bottom_controls[block]
            )
            records[node][1] = (
                stack[ordinal - 1] if ordinal else top_controls[block]
            )

    controls = {
        75: (78, node_at[(4, 0)], 77, 77),
        77: (80, node_at[(3, 15)], 75, 75),
        78: (node_at[(0, 0)], 75, 80, 79),
        79: (node_at[(0, 6)], 77, 78, 80),
        80: (node_at[(0, 12)], 77, 79, 78),
    }
    for node, neighbors in controls.items():
        records[node][:4] = bytes(neighbors)

    active = set(range(len(KEYBOARD_CHARACTERS))) | {75, 77, 78, 79, 80}
    blanks = set(range(len(KEYBOARD_CHARACTERS), 75)) | {76}
    for node in active:
        leaked = set(records[node][:4]) & blanks
        if leaked:
            raise Name6Error(
                "active name-entry node %d still reaches blank node(s) %s"
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
        raise Name6Error(
            "English name-entry graph leaves unreachable node(s) %s"
            % sorted(active - reached)
        )
    result = bytes(value for record in records for value in record)
    if len(result) != NAVIGATION_SIZE:
        raise Name6Error("English navigation table changed size")
    return result


def runtime_payload(rom, approved=None):
    if len(ASSEMBLED_CODE) != CODE_END - RUNTIME_ADDRESS:
        raise Name6Error("assembled name6 code length changed")
    payload = bytearray(PAYLOAD_END - RUNTIME_ADDRESS)

    def place(address, raw):
        start = address - RUNTIME_ADDRESS
        end = start + len(raw)
        if not 0 <= start <= end <= len(payload):
            raise Name6Error("name6 payload component leaves its reserved range")
        if any(payload[start:end]):
            raise Name6Error("name6 payload components overlap")
        payload[start:end] = raw

    place(RUNTIME_ADDRESS, ASSEMBLED_CODE)
    place(CHARACTER_TABLE_ADDRESS, character_bytes())
    place(DEFAULT_NAME_ADDRESS, default_name_bytes())
    place(RANK_HEADER_ADDRESS, RANKING_SRAM_HEADER_BYTES)
    place(KEYBOARD_MAP_ADDRESS, english_keyboard_map(rom))
    place(
        GLYPH_LOW_ADDRESS,
        keyboard_glyph_bytes(
            GLYPH_LOW_START, GLYPH_LOW_END, approved=approved
        ),
    )
    place(
        GLYPH_HIGH_ADDRESS,
        keyboard_glyph_bytes(
            GLYPH_HIGH_START, GLYPH_HIGH_END, approved=approved
        ),
    )
    return bytes(payload)


def owned_ranges():
    patches = tuple(
        (
            _offset(bank, address),
            _offset(bank, address) + len(original),
        )
        for _name, bank, address, original, _target in (
            ROUTINE_PATCHES + CALL_PATCHES
        )
    )
    navigation_at = _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS)
    replay_ranges = []
    for event_id in range(REPLAY_POINTER_COUNT):
        entry = REPLAY_POINTER_BYTES[
            event_id * REPLAY_POINTER_ENTRY_SIZE:
            (event_id + 1) * REPLAY_POINTER_ENTRY_SIZE
        ]
        address = entry[0] | (entry[1] << 8)
        at = _offset(entry[2], address)
        replay_ranges.extend(
            (
                (
                    at + REPLAY_NAME_OFFSET,
                    at + REPLAY_NAME_OFFSET + REPLAY_NAME_FIELD_SIZE,
                ),
                (
                    at + DIARY_SUFFIX_OFFSETS[0],
                    at + DIARY_MARKER_OFFSETS[-1] + 1,
                ),
            )
        )
    return patches + tuple(replay_ranges) + (
        (navigation_at, navigation_at + NAVIGATION_SIZE),
        (
            _runtime_offset(RUNTIME_ADDRESS),
            _runtime_offset(PAYLOAD_END),
        ),
    )


def install(rom, approved=None, verify_original=True, checksums=True):
    """Return ``rom`` with six-character names and ranking suffixes installed."""
    out = bytearray(install_replay_names(rom, verify_original=verify_original))
    for name, bank, address, original, target in ROUTINE_PATCHES:
        at = _offset(bank, address)
        if verify_original and bytes(out[at:at + len(original)]) != original:
            raise Name6Error(
                "%s routine at %s is not original"
                % (name, extract.location(bank, address))
            )
        out[at:at + len(original)] = _far_transfer(
            target, len(original), tail=True
        )

    for name, bank, address, original, target in CALL_PATCHES:
        at = _offset(bank, address)
        if verify_original and bytes(out[at:at + len(original)]) != original:
            raise Name6Error(
                "%s call at %s is not original"
                % (name, extract.location(bank, address))
            )
        out[at:at + len(original)] = _far_transfer(
            target, len(original), tail=False
        )

    navigation = english_navigation_table(out)
    navigation_at = _offset(NAVIGATION_BANK, NAVIGATION_ADDRESS)
    out[navigation_at:navigation_at + len(navigation)] = navigation

    approved = approved or english_font.load_approved()
    payload = runtime_payload(out, approved=approved)
    runtime_at = _runtime_offset(RUNTIME_ADDRESS)
    existing = bytes(out[runtime_at:runtime_at + len(payload)])
    if verify_original and any(existing):
        raise Name6Error(
            "reserved runtime range %s is not empty"
            % extract.location(RUNTIME_BANK, RUNTIME_ADDRESS)
        )
    out[runtime_at:runtime_at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return out


def summary(rom, approved=None):
    approved = approved or english_font.load_approved()
    keyboard = english_keyboard_map(rom)
    navigation = english_navigation_table(rom)
    glyphs = (
        keyboard_glyph_bytes(
            GLYPH_LOW_START, GLYPH_LOW_END, approved=approved
        )
        + keyboard_glyph_bytes(
            GLYPH_HIGH_START, GLYPH_HIGH_END, approved=approved
        )
    )
    replays = replay_records(rom)
    return {
        "maximum_visible_characters": MAX_VISIBLE_CHARACTERS,
        "default_name": DEFAULT_NAME,
        "runtime": {
            "bank": RUNTIME_BANK,
            "start": extract.location(RUNTIME_BANK, RUNTIME_ADDRESS),
            "end_exclusive": extract.location(RUNTIME_BANK, PAYLOAD_END),
            "payload_bytes": PAYLOAD_END - RUNTIME_ADDRESS,
        },
        "diary": {
            "native_size": DIARY_SIZE,
            "legacy_prefix_address": "$%04X" % DIARY_PREFIX_ADDRESS,
            "suffix_address": "$%04X" % DIARY_SUFFIX_ADDRESS,
            "marker_address": "$%04X" % DIARY_MARKER_ADDRESS,
            "suffix_offsets": list(DIARY_SUFFIX_OFFSETS),
            "marker_offsets": list(DIARY_MARKER_OFFSETS),
            "old_save_fallback": "marker absent: render legacy prefix only",
        },
        "embedded_replays": {
            "pointer_table": extract.location(
                REPLAY_POINTER_BANK, REPLAY_POINTER_ADDRESS
            ),
            "events": REPLAY_POINTER_COUNT,
            "snapshot_bytes": DIARY_SIZE,
            "name_field_offset": REPLAY_NAME_OFFSET,
            "name_field_bytes": REPLAY_NAME_FIELD_SIZE,
            "non_secrets_event_range": list(REPLAY_NON_SECRETS_EVENTS),
            "title_observed_event_range": list(REPLAY_TITLE_OBSERVED_EVENTS),
            "secrets_event_range": list(REPLAY_SECRETS_EVENTS),
            "localized_name": DEFAULT_NAME,
            "title_selector": extract.location(*REPLAY_TITLE_SELECTOR),
            "secrets_selector": extract.location(*REPLAY_SECRETS_SELECTOR),
            "records": [
                {
                    "event_id": record["event_id"],
                    "location": extract.location(
                        record["bank"], record["address"]
                    ),
                    "sha1": record["sha1"],
                }
                for record in replays
            ],
        },
        "rankings": {
            "native_record_bytes": 32,
            "categories": RANKING_CATEGORIES,
            "physical_slots_per_category": RANKING_SLOTS,
            "sram_bank": RANKING_SRAM_BANK,
            "native_structures_end_exclusive": "$%04X" % RANKING_NATIVE_END,
            "header": "$%04X" % RANKING_SRAM_HEADER,
            "suffixes": "$%04X" % RANKING_SRAM_SUFFIXES,
            "end_exclusive": "$%04X" % RANKING_SRAM_END,
            "signature": "$%04X" % SRAM_SIGNATURE_ADDRESS,
            "old_save_fallback": "header absent: suffix is FF,FF",
        },
        "keyboard": {
            "mode": 4,
            "characters": KEYBOARD_CHARACTERS,
            "grid_character_nodes": len(KEYBOARD_CHARACTERS),
            "space_control_node": 75,
            "removed_clear_control_node": 76,
            "left_cursor_control_node": 78,
            "right_cursor_control_node": 79,
            "insertable_nodes": len(KEYBOARD_CHARACTERS) + 1,
            "blank_unreachable_nodes": list(
                range(len(KEYBOARD_CHARACTERS), 75)
            ) + [76],
            "removed_characters": REMOVED_CHARACTERS,
            "map_bytes": len(keyboard),
            "map_sha1": sha1(keyboard).hexdigest(),
            "navigation_bytes": len(navigation),
            "navigation_sha1": sha1(navigation).hexdigest(),
            "glyph_bytes": len(glyphs),
            "glyph_sha1": sha1(glyphs).hexdigest(),
            "shared_mode3_source_unchanged": True,
        },
    }
