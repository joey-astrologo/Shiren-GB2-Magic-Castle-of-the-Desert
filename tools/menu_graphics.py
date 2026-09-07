#!/usr/bin/env python3
"""Install the localized Status overlay and item-action tile safeguards.

Bank 17 copies a 4 KiB 2bpp template at 17:$5A2C into WRAM.  The Monster Log
also consumes that bitmap with a different layout, so changing the source
template corrupts the Log.  Instead, this module replaces all three Status
reconstruction calls and draws the English labels over their WRAM canvas.  The
wrapper lives in dedicated empty bank 255, not padding another graphic may consume.
The shared template consequently remains byte-exact for every other consumer.

The item-action window uses the same 18-tile-wide canvas in a different way. Its
eight logical label slots are 48 pixels apart, but the compact window maps only
the first five label tiles after each cursor cell. A shadow pixel entering the
sixth label tile therefore aliases the next column's cursor cell. The upload
wrapper clears both cursor-only canvas columns after rendering and before the
native VRAM copy, so clipped shadow pixels cannot reappear on lower blank rows.
The equipment preview starts one tile after the cleared third-column cursor
cell, leaving 40 pixels for its two unsigned-byte values and native arrow.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
import sys

from cartridge import fix_checksums
import english_font
import extract
import font


TEMPLATE_BANK = 17
TEMPLATE_ADDRESS = 0x5A2C
TEMPLATE_SIZE = 0x1000
TEMPLATE_SHA1 = "b856fd7fdc133762e758f75e0ed4b245e4f3a990"

CANVAS_COLUMNS = 18
CANVAS_ROWS = 14
CANVAS_WIDTH = CANVAS_COLUMNS * 8
CANVAS_HEIGHT = CANVAS_ROWS * 8
CANVAS_TILES = CANVAS_COLUMNS * CANVAS_ROWS
BACKGROUND_COLOR = 0
SHADOW_COLOR = 2
INK_COLOR = 3


class MenuGraphicsError(ValueError):
    """The menu template, label plan, or target ROM violates an invariant."""


@dataclass(frozen=True)
class MenuLabel:
    """One English raster and the rectangle whose Japanese pixels it replaces."""

    name: str
    text: str
    x: int
    y: int
    clear_left: int
    clear_top: int
    clear_right: int
    clear_bottom: int
    visual_right_edge: int


# Coordinates use the native 144x112 canvas copied to WRAM bank 7 at $D000.
# ``visual_right_edge`` is exclusive and freezes collision-free space before a
# dynamic number, panel edge, or suffix.  The compact English percent glyph uses
# the seven remaining pixels at x=137..143 without crossing the canvas edge.
LABELS = (
    MenuLabel("experience", "Exp", 56, 1, 56, 0, 88, 10, 88),
    MenuLabel("location", "Location", 56, 12, 56, 12, 104, 20, 104),
    MenuLabel("map", "Map", 3, 24, 3, 24, 27, 32, 53),
    MenuLabel("hints", "Hints", 3, 36, 3, 36, 27, 44, 53),
    MenuLabel("quit", "Quit", 3, 48, 3, 48, 27, 56, 53),
    MenuLabel("attack", "Atk", 0, 77, 0, 77, 21, 85, 21),
    MenuLabel("strength", "Strength", 40, 77, 40, 77, 91, 85, 91),
    MenuLabel("strength_separator", "/", 108, 77, 107, 77, 114, 85, 120),
    MenuLabel("defense", "Def", 0, 88, 0, 88, 21, 96, 21),
    MenuLabel("fullness", "Fullness", 40, 88, 40, 88, 80, 96, 91),
    MenuLabel("fullness_separator", "/", 108, 88, 107, 88, 114, 96, 120),
    MenuLabel("fullness_suffix", "%", 137, 88, 137, 88, 144, 96, 144),
    MenuLabel("money", "Gitan", 0, 99, 0, 99, 27, 107, 105),
    MenuLabel("money_suffix", "G", 138, 99, 138, 99, 144, 107, 144),
)

# All three callers of 17:$6A2C reconstruct the Status canvas: the normal
# in-dungeon entry, a same-routine refresh path, and the Help-page return path.
# Missing the last of these made the Japanese template reappear after backing
# out of a selected Hint.  Every route must therefore pass through the same
# English WRAM overlay before the native dynamic-value renderer and uploader.
CALL_SITES = (
    ("help_return", 4, 0x4148),
    ("menu_open", 16, 0x464F),
    ("menu_refresh", 16, 0x4689),
)
CALL_SITE_ORIGINAL = bytes.fromhex("3E11212C6ACDAC09")

# This completely empty bank is outside the script allocator's 215..239 range
# and is explicitly owned by this engine patch.
OVERLAY_BANK = 255
OVERLAY_ADDRESS = 0x4000
OVERLAY_LIMIT = 0x8000
OVERLAY_ORIGINAL_BYTE = 0x00
OVERLAY_PAYLOAD_SIZE = 2685

# Bank 17 clears and renders the complete item-action canvas in WRAM bank 7,
# then copies its five visible tile rows from $D240 to VRAM $9240. Replace only
# that final copy tail. The helper lives after the independently frozen Status
# overlay payload in the same dedicated menu-graphics bank.
ITEM_ACTION_UPLOAD_BANK = 17
ITEM_ACTION_UPLOAD_ADDRESS = 0x6F04
ITEM_ACTION_UPLOAD_ORIGINAL = bytes.fromhex(
    "3E07E0702140D211409201A005CD6B0AC1C9"
)
ITEM_ACTION_HELPER_ADDRESS = 0x4B00
ITEM_ACTION_CANVAS_ADDRESS = 0xD000
ITEM_ACTION_CANVAS_COLUMNS = 18
ITEM_ACTION_CURSOR_COLUMNS = (6, 12)
ITEM_ACTION_VISIBLE_TILE_ROWS = tuple(range(2, 7))
ITEM_ACTION_CURSOR_TILE_IDS = tuple(
    row * ITEM_ACTION_CANVAS_COLUMNS + column
    for column in ITEM_ACTION_CURSOR_COLUMNS
    for row in ITEM_ACTION_VISIBLE_TILE_ROWS
)
ITEM_ACTION_TILE_BYTES = 16
ITEM_ACTION_WRAM_BANK = 7
ITEM_ACTION_VRAM_SOURCE = 0xD240
ITEM_ACTION_VRAM_DESTINATION = 0x9240
ITEM_ACTION_VRAM_COPY_BYTES = 0x05A0

# The sword/shield comparison shares canvas tiles $30/$42 with the third
# logical command column's cursor. Cleanup must keep those tiles blank. Its
# native x=96 origin therefore erases leading digits; x=104 leaves five whole
# tiles for the largest English preview, "255" + native arrow + "255" (38px).
# Guard both coordinate stores, but own only the changed X immediate byte.
EQUIPMENT_PREVIEW_BANK = 17
EQUIPMENT_PREVIEW_POSITION_ADDRESS = 0x71A1
EQUIPMENT_PREVIEW_POSITION_ORIGINAL = bytes.fromhex("3E60EAD6C43E14EAD7C4")
EQUIPMENT_PREVIEW_START = (104, 20)
EQUIPMENT_PREVIEW_RIGHT_EDGE = 144


def equipment_preview_position_offset():
    return extract.file_offset(EQUIPMENT_PREVIEW_BANK, EQUIPMENT_PREVIEW_POSITION_ADDRESS)

def template_offset():
    return extract.file_offset(TEMPLATE_BANK, TEMPLATE_ADDRESS)


def template_bytes(rom):
    at = template_offset()
    raw = bytes(rom[at:at + TEMPLATE_SIZE])
    if len(raw) != TEMPLATE_SIZE:
        raise MenuGraphicsError("ROM is too small for the main-menu template")
    return raw


def verify_template(rom):
    actual = sha1(template_bytes(rom)).hexdigest()
    if actual != TEMPLATE_SHA1:
        raise MenuGraphicsError(
            "main-menu template SHA-1 %s, expected %s"
            % (actual, TEMPLATE_SHA1)
        )
    return actual


def decode_canvas(raw):
    """Decode the 18x14 visible tile prefix to mutable color-index rows."""
    raw = bytes(raw)
    if len(raw) != TEMPLATE_SIZE:
        raise MenuGraphicsError("template must contain exactly 4096 bytes")
    pixels = [bytearray(CANVAS_WIDTH) for _ in range(CANVAS_HEIGHT)]
    for tile in range(CANVAS_TILES):
        rows = font.decode_2bpp_slices(raw[tile * 16:(tile + 1) * 16], 8)
        left = (tile % CANVAS_COLUMNS) * 8
        top = (tile // CANVAS_COLUMNS) * 8
        for y, row in enumerate(rows):
            pixels[top + y][left:left + 8] = bytes(row)
    return pixels


def _encode_tile(pixels, left, top):
    out = bytearray()
    for y in range(top, top + 8):
        low = 0
        high = 0
        for x in range(left, left + 8):
            color = pixels[y][x]
            if not 0 <= color <= 3:
                raise MenuGraphicsError("2bpp canvas contains invalid color %r" % color)
            bit = 0x80 >> (x - left)
            if color & 1:
                low |= bit
            if color & 2:
                high |= bit
        out += bytes((low, high))
    return bytes(out)


def encode_canvas(pixels, original):
    """Encode the canvas while retaining the template's unused four-tile tail."""
    if len(pixels) != CANVAS_HEIGHT or any(
        len(row) != CANVAS_WIDTH for row in pixels
    ):
        raise MenuGraphicsError("canvas must be 144x112 pixels")
    original = bytes(original)
    if len(original) != TEMPLATE_SIZE:
        raise MenuGraphicsError("template must contain exactly 4096 bytes")
    out = bytearray()
    for tile in range(CANVAS_TILES):
        out += _encode_tile(
            pixels,
            (tile % CANVAS_COLUMNS) * 8,
            (tile // CANVAS_COLUMNS) * 8,
        )
    out += original[CANVAS_TILES * 16:]
    return bytes(out)


def _clear(pixels, label):
    if not (
        0 <= label.clear_left <= label.clear_right <= CANVAS_WIDTH
        and 0 <= label.clear_top <= label.clear_bottom <= CANVAS_HEIGHT
    ):
        raise MenuGraphicsError("%s has an invalid clear rectangle" % label.name)
    for y in range(label.clear_top, label.clear_bottom):
        pixels[y][label.clear_left:label.clear_right] = bytes(
            (BACKGROUND_COLOR,) * (label.clear_right - label.clear_left)
        )


def _draw(pixels, label, approved):
    pen = label.x
    runs = []
    for character in label.text:
        try:
            glyph = approved.glyphs[character]
            advance = approved.advances[character]
        except KeyError as exc:
            raise MenuGraphicsError(
                "%s uses unsupported glyph %r" % (label.name, exc.args[0])
            ) from exc
        runs.append(
            (pen, font.decode_2bpp_slices(glyph, height=english_font.CELL_SIZE[1]))
        )
        pen += advance

    # These status labels are a bitmap overlay rather than runtime strings.
    # Paint the installed font's complete color-2 shadow plane first, then its
    # color-3 ink plane, matching adjacent-glyph overlap in the approved font.
    for color in (SHADOW_COLOR, INK_COLOR):
        for run_x, raster in runs:
            for glyph_y, row in enumerate(raster):
                y = label.y + glyph_y
                for glyph_x, pixel in enumerate(row):
                    if pixel != color:
                        continue
                    x = run_x + glyph_x
                    if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
                        pixels[y][x] = color
                    elif color == INK_COLOR:
                        raise MenuGraphicsError(
                            "%s ink raster leaves the canvas" % label.name
                        )
    if pen > label.visual_right_edge:
        raise MenuGraphicsError(
            "%s advances to x=%d past exclusive edge x=%d"
            % (label.name, pen, label.visual_right_edge)
        )
    return pen


def localized_template(rom, approved=None, verify_original=True):
    """Return the deterministic English 4 KiB template and label measurements."""
    if verify_original:
        verify_template(rom)
    original = template_bytes(rom)
    pixels = decode_canvas(original)
    approved = approved or english_font.load_approved()
    measurements = []
    for label in LABELS:
        _clear(pixels, label)
        final_x = _draw(pixels, label, approved)
        measurements.append(
            {
                "name": label.name,
                "text": label.text,
                "start": [label.x, label.y],
                "final_x": final_x,
                "visual_right_edge": label.visual_right_edge,
                "clearance_pixels": label.visual_right_edge - final_x,
                "clear_rect": [
                    label.clear_left,
                    label.clear_top,
                    label.clear_right,
                    label.clear_bottom,
                ],
            }
        )
    return encode_canvas(pixels, original), measurements


def _banked_offset(bank, address):
    return extract.file_offset(bank, address)


def call_site_offsets():
    return tuple(
        (name, bank, address, _banked_offset(bank, address))
        for name, bank, address in CALL_SITES
    )


def overlay_offset():
    return _banked_offset(OVERLAY_BANK, OVERLAY_ADDRESS)


def item_action_upload_offset():
    return _banked_offset(ITEM_ACTION_UPLOAD_BANK, ITEM_ACTION_UPLOAD_ADDRESS)


def item_action_helper_offset():
    return _banked_offset(OVERLAY_BANK, ITEM_ACTION_HELPER_ADDRESS)


def item_action_upload_patch():
    """Return the guarded far-call replacement for the native upload tail."""
    call = bytes((
        0x3E, OVERLAY_BANK,
        0x21, ITEM_ACTION_HELPER_ADDRESS & 0xFF,
        ITEM_ACTION_HELPER_ADDRESS >> 8,
        0xCD, 0xAC, 0x09,
        0xC1,  # pop bc retained from the native tail
        0xC9,
    ))
    return call + bytes(len(ITEM_ACTION_UPLOAD_ORIGINAL) - len(call))


def item_action_cleanup_payload():
    """Clear cursor-only canvas columns, then perform the native VRAM copy."""
    code = bytearray((
        0x3E, ITEM_ACTION_WRAM_BANK,
        0xE0, 0x70,
    ))
    for column in ITEM_ACTION_CURSOR_COLUMNS:
        first_tile = (
            ITEM_ACTION_VISIBLE_TILE_ROWS[0] * ITEM_ACTION_CANVAS_COLUMNS + column
        )
        first_address = (
            ITEM_ACTION_CANVAS_ADDRESS + first_tile * ITEM_ACTION_TILE_BYTES
        )
        code += bytes((
            0x21, first_address & 0xFF, first_address >> 8,  # ld hl,first tile
            0x06, len(ITEM_ACTION_VISIBLE_TILE_ROWS),       # ld b,row count
            0xC5,                                           # loop: push bc
            0x01, ITEM_ACTION_TILE_BYTES, 0x00,             # ld bc,$0010
            0xCD, 0xEA, 0x09,                               # call zero-fill
            0xC1,                                           # pop bc
            0x11, 0x10, 0x01,                               # ld de,$0110
            0x19,                                           # add hl,de
            0x05,                                           # dec b
            0x20, 0xF1,                                     # jr nz,loop
        ))
    code += bytes((
        0x21, ITEM_ACTION_VRAM_SOURCE & 0xFF,
        ITEM_ACTION_VRAM_SOURCE >> 8,
        0x11, ITEM_ACTION_VRAM_DESTINATION & 0xFF,
        ITEM_ACTION_VRAM_DESTINATION >> 8,
        0x01, ITEM_ACTION_VRAM_COPY_BYTES & 0xFF,
        ITEM_ACTION_VRAM_COPY_BYTES >> 8,
        0xCD, 0x6B, 0x0A,
        0xC9,
    ))
    if ITEM_ACTION_HELPER_ADDRESS + len(code) > OVERLAY_LIMIT:
        raise MenuGraphicsError("item-action cleanup exceeds the bank-255 code cave")
    return bytes(code)


def overlay_payload(rom, approved=None):
    """Return a wrapper that applies only reviewed label bits to WRAM bank 7."""
    approved = approved or english_font.load_approved()
    original = template_bytes(rom)
    localized, measurements = localized_template(rom, approved=approved)

    # Apply compact (offset, mask, value) records before the native numeric
    # constructor uploads the completed canvas.  The final JP is a deliberate
    # tail dispatch: the nested dispatcher returns through the outer bank-255
    # frame and back to the unique bank-16 caller without resuming remote code.
    code = bytearray(bytes.fromhex(
        "C5D5"            # preserve caller BC and DE
        "F070F53E07E070"  # preserve SVBK and select WRAM bank 7
        "210000"          # ld hl,table (filled below)
        "2A5F2A577AFEFF2811" # load offset; high=$ff terminates
        "2A472A4F"        # B=mask, C=desired masked value
        "E52100D019"      # preserve table; HL=$d000+offset
        "7EA9A0AE77"      # old XOR ((old XOR value) AND mask)
        "E118E6"          # restore table and loop
        "F1E070"          # restore SVBK
        "D1C1"            # restore caller DE and BC
        "3E11212C6AC3AC09"# tail-dispatch original constructor
    ))
    table_address = OVERLAY_ADDRESS + len(code)
    code[10:12] = table_address.to_bytes(2, "little")
    table = bytearray()
    for offset, (source, target) in enumerate(zip(original, localized)):
        if source == target:
            continue
        mask = source ^ target
        table += offset.to_bytes(2, "little") + bytes((mask, target & mask))
    table += b"\x00\xFF"
    payload = bytes(code + table)
    if len(payload) > OVERLAY_PAYLOAD_SIZE:
        raise MenuGraphicsError("status-menu overlay payload size changed")
    payload += bytes(OVERLAY_PAYLOAD_SIZE - len(payload))
    if OVERLAY_ADDRESS + len(payload) > OVERLAY_LIMIT:
        raise MenuGraphicsError("status-menu overlay exceeds its reserved bank")
    rows = []
    for measurement in measurements:
        row = dict(measurement)
        row.pop("clear_rect")
        rows.append(row)
    return payload, rows


def owned_ranges(approved=None):
    overlay = overlay_offset()
    status_ranges = tuple(
        (offset, offset + len(CALL_SITE_ORIGINAL))
        for _name, _bank, _address, offset in call_site_offsets()
    ) + ((overlay, overlay + OVERLAY_PAYLOAD_SIZE),)
    upload = item_action_upload_offset()
    helper = item_action_helper_offset()
    preview = equipment_preview_position_offset()
    return status_ranges + (
        (upload, upload + len(ITEM_ACTION_UPLOAD_ORIGINAL)),
        (helper, helper + len(item_action_cleanup_payload())),
        (preview + 1, preview + 2),
    )


def install(rom, approved=None, verify_original=True, checksums=True):
    """Return a ROM with the Status overlay and action-tile cleanup installed."""
    out = bytearray(rom)
    approved = approved or english_font.load_approved()
    if verify_original:
        verify_template(out)
    for name, bank, address, call_site in call_site_offsets():
        if bytes(out[call_site:call_site + len(CALL_SITE_ORIGINAL)]) != CALL_SITE_ORIGINAL:
            raise MenuGraphicsError(
                "status-menu %s call site %s is not original"
                % (name, extract.location(bank, address))
            )
    payload, _rows = overlay_payload(out, approved)
    if len(payload) != OVERLAY_PAYLOAD_SIZE:
        raise MenuGraphicsError("status-menu overlay payload size changed")
    cave = overlay_offset()
    if any(byte != OVERLAY_ORIGINAL_BYTE for byte in out[cave:cave + len(payload)]):
        raise MenuGraphicsError("status-menu overlay cave is not empty")
    action_call = item_action_upload_offset()
    if (
        bytes(out[action_call:action_call + len(ITEM_ACTION_UPLOAD_ORIGINAL)])
        != ITEM_ACTION_UPLOAD_ORIGINAL
    ):
        raise MenuGraphicsError("item-action upload call site is not original")
    preview = equipment_preview_position_offset()
    if bytes(out[preview:preview + len(EQUIPMENT_PREVIEW_POSITION_ORIGINAL)]) != EQUIPMENT_PREVIEW_POSITION_ORIGINAL:
        raise MenuGraphicsError("equipment preview position is not original")
    action_payload = item_action_cleanup_payload()
    action_cave = item_action_helper_offset()
    if any(
        byte != OVERLAY_ORIGINAL_BYTE
        for byte in out[action_cave:action_cave + len(action_payload)]
    ):
        raise MenuGraphicsError("item-action cleanup cave is not empty")
    call = bytes((
        0x3E, OVERLAY_BANK,
        0x21, OVERLAY_ADDRESS & 0xFF, OVERLAY_ADDRESS >> 8,
        0xCD, 0xAC, 0x09,
    ))
    for _name, _bank, _address, call_site in call_site_offsets():
        out[call_site:call_site + len(call)] = call
    out[cave:cave + len(payload)] = payload
    out[
        action_call:action_call + len(ITEM_ACTION_UPLOAD_ORIGINAL)
    ] = item_action_upload_patch()
    out[action_cave:action_cave + len(action_payload)] = action_payload
    out[preview + 1] = EQUIPMENT_PREVIEW_START[0]
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, approved=None):
    approved = approved or english_font.load_approved()
    verify_template(rom)
    original = template_bytes(rom)
    payload, rows = overlay_payload(rom, approved)
    return {
        "schema": "shiren-gb2-menu-graphics-v6",
        "source": {
            "location": extract.location(TEMPLATE_BANK, TEMPLATE_ADDRESS),
            "size": TEMPLATE_SIZE,
            "sha1": sha1(original).hexdigest(),
            "remains_byte_exact": True,
        },
        "call_sites": [
            {
                "name": name,
                "location": extract.location(bank, address),
                "original_hex": CALL_SITE_ORIGINAL.hex().upper(),
                "patch_hex": bytes((
                    0x3E, OVERLAY_BANK,
                    0x21, OVERLAY_ADDRESS & 0xFF, OVERLAY_ADDRESS >> 8,
                    0xCD, 0xAC, 0x09,
                )).hex().upper(),
            }
            for name, bank, address in CALL_SITES
        ],
        "overlay": {
            "location": extract.location(OVERLAY_BANK, OVERLAY_ADDRESS),
            "limit": extract.location(OVERLAY_BANK, OVERLAY_LIMIT - 1),
            "bytes": len(payload),
            "sha1": sha1(payload).hexdigest(),
            "remaining_bytes": OVERLAY_LIMIT - OVERLAY_ADDRESS - len(payload),
        },
        "labels": rows,
        "item_action_cursor_cleanup": {
            "call_site": {
                "location": extract.location(
                    ITEM_ACTION_UPLOAD_BANK, ITEM_ACTION_UPLOAD_ADDRESS
                ),
                "original_hex": ITEM_ACTION_UPLOAD_ORIGINAL.hex().upper(),
                "patch_hex": item_action_upload_patch().hex().upper(),
            },
            "helper": {
                "location": extract.location(
                    OVERLAY_BANK, ITEM_ACTION_HELPER_ADDRESS
                ),
                "bytes": len(item_action_cleanup_payload()),
                "sha1": sha1(item_action_cleanup_payload()).hexdigest(),
            },
            "canvas": {
                "wram_bank": ITEM_ACTION_WRAM_BANK,
                "address": "$%04X" % ITEM_ACTION_CANVAS_ADDRESS,
                "tile_columns": ITEM_ACTION_CANVAS_COLUMNS,
                "cursor_only_columns": list(ITEM_ACTION_CURSOR_COLUMNS),
                "visible_tile_rows": list(ITEM_ACTION_VISIBLE_TILE_ROWS),
                "cleared_tile_ids": list(ITEM_ACTION_CURSOR_TILE_IDS),
                "vram_copy": "$%04X-$%04X" % (
                    ITEM_ACTION_VRAM_DESTINATION,
                    ITEM_ACTION_VRAM_DESTINATION
                    + ITEM_ACTION_VRAM_COPY_BYTES - 1,
                ),
            },
        },
        "equipment_preview": {
            "position_store": extract.location(EQUIPMENT_PREVIEW_BANK, EQUIPMENT_PREVIEW_POSITION_ADDRESS),
            "original_hex": EQUIPMENT_PREVIEW_POSITION_ORIGINAL.hex().upper(),
            "start_pen": list(EQUIPMENT_PREVIEW_START),
            "right_edge": EQUIPMENT_PREVIEW_RIGHT_EDGE,
            "available_pixels": EQUIPMENT_PREVIEW_RIGHT_EDGE - EQUIPMENT_PREVIEW_START[0],
            "value_domain": [0, 255],
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("output", help="output ROM with the menu template installed")
    args = parser.parse_args(argv)
    source = Path(args.rom).read_bytes()
    try:
        output = install(source)
        report = summary(source)
    except (MenuGraphicsError, english_font.FontError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print("labels     : %d" % len(report["labels"]))
    print("overlay    : %d byte(s)" % report["overlay"]["bytes"])
    print("output     : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
