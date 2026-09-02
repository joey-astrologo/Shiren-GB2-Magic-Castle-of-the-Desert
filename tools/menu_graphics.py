#!/usr/bin/env python3
"""Localize GB2's in-dungeon status menu without mutating shared graphics.

Bank 17 copies a 4 KiB 2bpp template at 17:$5A2C into WRAM.  The Monster Log
also consumes that bitmap with a different layout, so changing the source
template corrupts the Log.  Instead, this module replaces all three Status
reconstruction calls and draws the English labels over their WRAM canvas.  The
wrapper lives in dedicated empty bank 255, not padding another graphic may consume.
The shared template consequently remains byte-exact for every other consumer.
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
    return tuple(
        (offset, offset + len(CALL_SITE_ORIGINAL))
        for _name, _bank, _address, offset in call_site_offsets()
    ) + ((overlay, overlay + OVERLAY_PAYLOAD_SIZE),)


def install(rom, approved=None, verify_original=True, checksums=True):
    """Return a ROM with the status-menu-only English overlay installed."""
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
    call = bytes((
        0x3E, OVERLAY_BANK,
        0x21, OVERLAY_ADDRESS & 0xFF, OVERLAY_ADDRESS >> 8,
        0xCD, 0xAC, 0x09,
    ))
    for _name, _bank, _address, call_site in call_site_offsets():
        out[call_site:call_site + len(call)] = call
    out[cave:cave + len(payload)] = payload
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, approved=None):
    approved = approved or english_font.load_approved()
    verify_template(rom)
    original = template_bytes(rom)
    payload, rows = overlay_payload(rom, approved)
    return {
        "schema": "shiren-gb2-status-menu-overlay-v5",
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
