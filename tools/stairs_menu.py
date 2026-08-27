#!/usr/bin/env python3
"""Widen and safely tear down both Proceed/Stay Here stairs popups.

The stairs prompt is not built by GB2's ordinary menu-window constructor.  Its
bank-3 overlay copies a fixed seven-column tilemap whose five interior columns
provide only 40 pixels.  The English ``Stay Here`` raster needs 46 pixels.

This installer adds stairs-only tilemaps in a dedicated empty ROM bank and routes both
constructors through small helpers only when the staged records are group 7
indices 59 and 60.  The floor overlay also saves the newly covered background
cells and restores them after the native seven-column cleanup.  Every other
overlay and ordinary two-choice popup retains its original path byte-for-byte.
"""
from hashlib import sha1

from cartridge import fix_checksums
import english_font
import extract


BANK = 3
STATUS_BANK = 11
CONTROLLER_BANK = 18
LOAD_PATCH_ADDRESS = 0x6A49
COPY_PATCH_ADDRESS = 0x6A8F
STATUS_PATCH_ADDRESS = 0x68DE
CONTROLLER_EXIT_PATCH_ADDRESS = 0x4130

RUNTIME_BANK = 254
HELPER_ADDRESS = 0x4000
FLOOR_SAVE_ADDRESS = 0x405E
TEMPLATE_ADDRESS = 0x40F5
NATIVE_TEMPLATE_ADDRESS = 0x414F
STATUS_HELPER_ADDRESS = 0x41DB
STATUS_TEMPLATE_ADDRESS = 0x4205
STATUS_EXIT_HELPER_ADDRESS = 0x425F
RUNTIME_END = 0x426B

ORIGINAL_LOAD = bytes.fromhex("21B36A1100D8068CCD5B0A")
ORIGINAL_COPY = bytes.fromhex("0E072100D8CDEA0A217ED8010701CDEA0A")
ORIGINAL_STATUS_BRANCH = bytes.fromhex(
    "21F768118398010804CDEA0A216769110399010801CDEA0AC9"
)
ORIGINAL_CONTROLLER_EXIT_CALL = bytes.fromhex("3E11219C43CDAC09")
ORIGINAL_NATIVE_TEMPLATE = bytes.fromhex(
    "7E8FC087C087C087C087C0877EAF7F8F908791879287938794877FAF"
    "7F8FA287A387A487A587A6877FAF7F8FB487B587B687B787B8877FAF"
    "7F8F96879787988799879A877FAF7F8FA887A987AA87AB87AC877FAF"
    "7F8FBA87BB87BC87BD87BE877FAF7F8F9C879D879E879F87A0877FAF"
    "7F8FAE87AF87B087B187B2877FAF7ECFC0C7C0C7C0C7C0C7C0C77EEF"
)
ORIGINAL_INTERIOR_COLUMNS = 5
ENGLISH_INTERIOR_COLUMNS = 7
STATUS_ORIGINAL_INTERIOR_COLUMNS = 6
STATUS_ENGLISH_INTERIOR_COLUMNS = 7
TILE_PIXELS = 8
TEXT_START_X = 8
TEXT_RIGHT_EDGE = TEXT_START_X + ENGLISH_INTERIOR_COLUMNS * TILE_PIXELS
STAIRS_GROUP = 7
STAIRS_INDICES = (59, 60)
STAIRS_LABELS = ("Proceed", "Stay Here")


class StairsMenuError(ValueError):
    """The stairs-popup code, padding, or generated tilemap is not as expected."""


def _offset(address, bank=BANK):
    return extract.file_offset(bank, address)


def _far_call(address, replaced_size, tail_return=False):
    payload = bytes((
        0x3E, RUNTIME_BANK,
        0x21, address & 0xFF, address >> 8,
        0xCD, 0xAC, 0x09,
    ))
    if tail_return:
        payload += b"\xC9"
    if len(payload) > replaced_size:
        raise StairsMenuError("far call does not fit its source patch")
    return payload + bytes(replaced_size - len(payload))


def _is_stairs_helper():
    # Preserve Z only when FFB0=2 and FFB2..FFB5 contain
    # (index 59, group 7), (index 60, group 7).
    return bytes.fromhex(
        "F0B0FE02C0"
        "F0B2FE3BC0"
        "F0B3FE07C0"
        "F0B4FE3CC0"
        "F0B5FE07C9"
    )


def _load_helper():
    # Select and copy either the stairs-only 90-byte tilemap or the native
    # 140-byte generic overlay template into WRAM at D800.
    return bytes.fromhex(
        "CD0040200B"
        "21F5401100D8065AC35B0A"
        "214F411100D8068CC35B0A"
    )


def _copy_helper():
    # The caller supplies B (the number of top rows) and DE (BG destination).
    # A stairs prompt copies nine columns and takes its bottom row from D848;
    # the generic route remains seven columns with its bottom row at D87E.
    return bytes.fromhex(
        "CD00402014"
        "CD5E400E092100D8CDEA0A2148D8010901C3EA0A"
        "0E072100D8CDEA0A217ED8010701C3EA0A"
    )


def helper_bytes():
    result = _is_stairs_helper() + _load_helper() + _copy_helper()
    if len(result) != 94:
        raise StairsMenuError("generated helper layout changed unexpectedly")
    return result


def _floor_save_bytes():
    """Save the ten BG cells covered only by the English floor frame."""
    return bytes.fromhex(
        "C5D5E5"
        "7BEA6FD87AEA70D8"
        "626B01070009"
        "115AD80E05"
        "C5E5AFE04F010200CD6B0A"
        "E13E01E04F010200CD6B0A"
        "7DC61E6F300124C10D20DF"
        "3E01E04FEA71D8E1D1C1C9"
    )


def _floor_restore_bytes():
    """Restore the saved two columns after the native dungeon redraw."""
    return bytes.fromhex(
        "C5D5E5"
        "FA6FD8C6075FFA70D8CE0057"
        "215AD80E05"
        "C5D5AFE04F010200CD6B0A"
        "D13E01E04F010200CD6B0A"
        "7BC61E5F300114C10D20DF"
        "3E01E04FE1D1C1C9"
    )


def _floor_cleanup_bytes():
    restore = FLOOR_SAVE_ADDRESS + len(_floor_save_bytes())
    return bytes.fromhex(
        "F070F53E07E070"
        "FA71D8A72807"
        "AFEA71D8"
    ) + bytes(
        (0xCD, restore & 0xFF, restore >> 8)
    ) + bytes.fromhex("F1E070C9")


def floor_runtime_bytes():
    result = (
        _floor_save_bytes()
        + _floor_restore_bytes()
        + _floor_cleanup_bytes()
    )
    if len(result) != 151:
        raise StairsMenuError("generated floor cleanup layout changed unexpectedly")
    return result


def floor_cleanup_address():
    return (
        FLOOR_SAVE_ADDRESS
        + len(_floor_save_bytes())
        + len(_floor_restore_bytes())
    )


def _status_helper_bytes():
    body = bytes.fromhex(
        "CD0040200D"
    ) + bytes((0x21, STATUS_TEMPLATE_ADDRESS & 0xFF, STATUS_TEMPLATE_ADDRESS >> 8)) + bytes.fromhex(
        "118398010905CDEA0AC9"
        "21F768118398010804CDEA0A"
        "216769110399010801C3EA0A"
    )
    if len(body) != 42:
        raise StairsMenuError("generated status helper layout changed unexpectedly")
    return body


def status_helper_address():
    return STATUS_HELPER_ADDRESS


def status_template_address():
    return STATUS_TEMPLATE_ADDRESS


def status_exit_helper_address():
    return STATUS_EXIT_HELPER_ADDRESS


def _status_exit_helper_bytes():
    cleanup = floor_cleanup_address()
    return bytes.fromhex("3E0B219C43CDAC09") + bytes(
        (0xCD, cleanup & 0xFF, cleanup >> 8, 0xC9)
    )


def _cells_to_bytes(cells):
    return bytes(value for tile, attribute in cells for value in (tile, attribute))


def template_bytes():
    """Return the five-row, nine-column stairs tilemap/attribute template."""
    top = [(0x7E, 0x8F)] + [(0xC0, 0x87)] * 7 + [(0x7E, 0xAF)]

    def content(base):
        return (
            [(0x7F, 0x8F)]
            + [(base + column, 0x87) for column in range(7)]
            + [(0x7F, 0xAF)]
        )

    bottom = [(0x7E, 0xCF)] + [(0xC0, 0xC7)] * 7 + [(0x7E, 0xEF)]
    cells = top + content(0x90) + content(0xA2) + content(0xB4) + bottom
    result = _cells_to_bytes(cells)
    if len(result) != 5 * 9 * 2:
        raise StairsMenuError("generated stairs template has the wrong size")
    return result


def status_template_bytes():
    """Return the five-row, nine-column main-menu stairs tilemap."""
    top = [(0x7C, 0x00)] + [(0x7E, 0x00)] * 7 + [(0x7C, 0x20)]

    def content(base):
        return (
            [(0x7D, 0x00)]
            + [(base + column, 0x08) for column in range(7)]
            + [(0x7D, 0x20)]
        )

    bottom = [(0x7C, 0x40)] + [(0x7E, 0x40)] * 7 + [(0x7C, 0x60)]
    result = _cells_to_bytes(
        top + content(0x25) + content(0x37) + content(0x49) + bottom
    )
    if len(result) != 5 * 9 * 2:
        raise StairsMenuError("generated status stairs template has the wrong size")
    return result


def runtime_payload():
    """Return the complete bank-254 code and tilemap payload."""
    payload = (
        helper_bytes()
        + floor_runtime_bytes()
        + template_bytes()
        + ORIGINAL_NATIVE_TEMPLATE
        + _status_helper_bytes()
        + status_template_bytes()
        + _status_exit_helper_bytes()
    )
    if HELPER_ADDRESS + len(payload) != RUNTIME_END:
        raise StairsMenuError("reserved stairs runtime layout changed unexpectedly")
    return payload


def owned_ranges():
    return (
        (_offset(LOAD_PATCH_ADDRESS), _offset(LOAD_PATCH_ADDRESS) + len(ORIGINAL_LOAD)),
        (_offset(COPY_PATCH_ADDRESS), _offset(COPY_PATCH_ADDRESS) + len(ORIGINAL_COPY)),
        (
            _offset(STATUS_PATCH_ADDRESS, STATUS_BANK),
            _offset(STATUS_PATCH_ADDRESS, STATUS_BANK) + len(ORIGINAL_STATUS_BRANCH),
        ),
        (
            _offset(CONTROLLER_EXIT_PATCH_ADDRESS, CONTROLLER_BANK),
            _offset(CONTROLLER_EXIT_PATCH_ADDRESS, CONTROLLER_BANK)
            + len(ORIGINAL_CONTROLLER_EXIT_CALL),
        ),
        (
            _offset(HELPER_ADDRESS, RUNTIME_BANK),
            _offset(HELPER_ADDRESS, RUNTIME_BANK) + len(runtime_payload()),
        ),
    )


def verify_source(rom):
    rom = bytes(rom)
    expected = (
        (BANK, LOAD_PATCH_ADDRESS, ORIGINAL_LOAD, "overlay template load"),
        (BANK, COPY_PATCH_ADDRESS, ORIGINAL_COPY, "overlay BG copy"),
        (
            STATUS_BANK,
            STATUS_PATCH_ADDRESS,
            ORIGINAL_STATUS_BRANCH,
            "main-menu stairs frame",
        ),
        (
            CONTROLLER_BANK,
            CONTROLLER_EXIT_PATCH_ADDRESS,
            ORIGINAL_CONTROLLER_EXIT_CALL,
            "floor-popup exit dispatch",
        ),
    )
    for bank, address, raw, label in expected:
        actual = rom[_offset(address, bank):_offset(address, bank) + len(raw)]
        if actual != raw:
            raise StairsMenuError(
                "%s bytes changed at %s" % (label, extract.location(bank, address))
            )
    native_at = _offset(0x6AB3, BANK)
    if rom[native_at:native_at + len(ORIGINAL_NATIVE_TEMPLATE)] != ORIGINAL_NATIVE_TEMPLATE:
        raise StairsMenuError(
            "native overlay template changed at %s" % extract.location(BANK, 0x6AB3)
        )
    runtime_at = _offset(HELPER_ADDRESS, RUNTIME_BANK)
    runtime = rom[runtime_at:runtime_at + len(runtime_payload())]
    if len(runtime) != len(runtime_payload()) or any(runtime):
        raise StairsMenuError(
            "reserved stairs runtime is not zero-filled at %s"
            % extract.location(RUNTIME_BANK, HELPER_ADDRESS)
        )


def install(rom, checksums=True):
    """Return a ROM with a widened popup only for the exact stairs records."""
    verify_source(rom)
    out = bytearray(rom)
    load_at = _offset(LOAD_PATCH_ADDRESS)
    copy_at = _offset(COPY_PATCH_ADDRESS)
    out[load_at:load_at + len(ORIGINAL_LOAD)] = _far_call(
        HELPER_ADDRESS + len(_is_stairs_helper()), len(ORIGINAL_LOAD)
    )
    out[copy_at:copy_at + len(ORIGINAL_COPY)] = _far_call(
        HELPER_ADDRESS + len(_is_stairs_helper()) + len(_load_helper()),
        len(ORIGINAL_COPY),
    )

    status_patch_at = _offset(STATUS_PATCH_ADDRESS, STATUS_BANK)
    status_patch = _far_call(
        status_helper_address(), len(ORIGINAL_STATUS_BRANCH), tail_return=True
    )
    out[status_patch_at:status_patch_at + len(status_patch)] = status_patch

    controller_at = _offset(CONTROLLER_EXIT_PATCH_ADDRESS, CONTROLLER_BANK)
    out[
        controller_at:controller_at + len(ORIGINAL_CONTROLLER_EXIT_CALL)
    ] = _far_call(
        status_exit_helper_address(), len(ORIGINAL_CONTROLLER_EXIT_CALL)
    )
    runtime_at = _offset(HELPER_ADDRESS, RUNTIME_BANK)
    payload = runtime_payload()
    out[runtime_at:runtime_at + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, approved=None):
    """Return the frozen source, code, frame, and English pixel contracts."""
    verify_source(rom)
    approved = approved or english_font.load_approved()
    labels = []
    for index, text in zip(STAIRS_INDICES, STAIRS_LABELS):
        width = sum(approved.advances[character] for character in text)
        labels.append(
            {
                "group": STAIRS_GROUP,
                "index": index,
                "text": text,
                "renderer_pixels": width,
                "native_clearance_pixels": (
                    ORIGINAL_INTERIOR_COLUMNS * TILE_PIXELS - width
                ),
                "english_clearance_pixels": (
                    ENGLISH_INTERIOR_COLUMNS * TILE_PIXELS - width
                ),
            }
        )
    return {
        "schema": "shiren-gb2-stairs-menu-v3",
        "bank": BANK,
        "runtime_bank": RUNTIME_BANK,
        "load_patch": extract.location(BANK, LOAD_PATCH_ADDRESS),
        "copy_patch": extract.location(BANK, COPY_PATCH_ADDRESS),
        "helper": extract.location(RUNTIME_BANK, HELPER_ADDRESS),
        "template": extract.location(RUNTIME_BANK, TEMPLATE_ADDRESS),
        "native_template_copy": extract.location(
            RUNTIME_BANK, NATIVE_TEMPLATE_ADDRESS
        ),
        "floor_cleanup": extract.location(RUNTIME_BANK, floor_cleanup_address()),
        "status_patch": extract.location(STATUS_BANK, STATUS_PATCH_ADDRESS),
        "status_detector": extract.location(RUNTIME_BANK, HELPER_ADDRESS),
        "status_helper": extract.location(RUNTIME_BANK, status_helper_address()),
        "status_template": extract.location(
            RUNTIME_BANK, status_template_address()
        ),
        "status_exit_helper": extract.location(
            RUNTIME_BANK, status_exit_helper_address()
        ),
        "controller_exit_patch": extract.location(
            CONTROLLER_BANK, CONTROLLER_EXIT_PATCH_ADDRESS
        ),
        "source_load_sha1": sha1(ORIGINAL_LOAD).hexdigest(),
        "source_copy_sha1": sha1(ORIGINAL_COPY).hexdigest(),
        "helper_sha1": sha1(helper_bytes()).hexdigest(),
        "template_sha1": sha1(template_bytes()).hexdigest(),
        "floor_runtime_sha1": sha1(floor_runtime_bytes()).hexdigest(),
        "status_source_sha1": sha1(ORIGINAL_STATUS_BRANCH).hexdigest(),
        "status_helper_sha1": sha1(_status_helper_bytes()).hexdigest(),
        "status_template_sha1": sha1(status_template_bytes()).hexdigest(),
        "status_exit_helper_sha1": sha1(
            _status_exit_helper_bytes()
        ).hexdigest(),
        "runtime_payload_sha1": sha1(runtime_payload()).hexdigest(),
        "runtime_payload_bytes": len(runtime_payload()),
        "controller_exit_source_sha1": sha1(
            ORIGINAL_CONTROLLER_EXIT_CALL
        ).hexdigest(),
        "native_columns": 7,
        "english_columns": 9,
        "status_native_columns": 8,
        "status_english_columns": 9,
        "native_interior_pixels": ORIGINAL_INTERIOR_COLUMNS * TILE_PIXELS,
        "english_interior_pixels": ENGLISH_INTERIOR_COLUMNS * TILE_PIXELS,
        "text_start_x": TEXT_START_X,
        "text_right_edge": TEXT_RIGHT_EDGE,
        "labels": labels,
    }
