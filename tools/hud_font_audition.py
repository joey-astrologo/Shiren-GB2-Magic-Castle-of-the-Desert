#!/usr/bin/env python3
"""Render GB2's dedicated top-status-bar font directly from ROM bytes.

The dungeon HUD does not use the localized dialogue font.  Bank 3 stores a compact
8x8-tile atlas at ``$5742-$5841``.  Its first ten tiles pack two four-pixel glyph
slots apiece: decimal/hexadecimal ``0-9A-F`` followed by the literal ``Lv`` and
``Hp`` label letters.  The next tile holds both halves of the slash, two tiles hold
meter artwork, and the final three tiles are reserved blanks.

This tool is an audition/contact-sheet renderer only; it never edits a ROM.  Its
layout proofs use the native four-pixel slot widths and the exact source pixels.

Example::

    python3 tools/hud_font_audition.py \
        "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
"""

import argparse
from hashlib import sha256
from pathlib import Path
import sys

import hud_font

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - only exercised without Pillow
    raise SystemExit(
        "HUD font audition requires Pillow (`python3 -m pip install pillow`)"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
DEFAULT_ROM = ROOT / ROM_NAME
DEFAULT_OUTPUT = ROOT / "build" / "hud_font_audition.png"

BANK_SIZE = 0x4000
HUD_SOURCE_BANK = 0x03
HUD_SOURCE_ADDRESS = 0x5742
HUD_SOURCE_OFFSET = (
    HUD_SOURCE_BANK * BANK_SIZE + HUD_SOURCE_ADDRESS - 0x4000
)
SOURCE_TILE_COUNT = 16
SOURCE_TILE_BYTES = 16
HUD_SOURCE_SIZE = SOURCE_TILE_COUNT * SOURCE_TILE_BYTES
HUD_SOURCE_SHA256 = (
    "3ea78ca67f1364b85de7fe4971886ae3bc76bcd643837504cc22be5e839704a1"
)
HUD_NATIVE_MIDDLE_SHA256 = (
    "e90d17c07e06e0f05d91e793faf93395b108d68d94b5aae884bc341d9300353a"
)
HUD_NATIVE_AFTER_SLASH_SHA256 = (
    "d9a01877e76c8d9752f80f4cb6441354ace005454b4e4b7cde4e82788622cbc7"
)
HUD_SOURCE_LOCATION = "3:$5742-$5841"

SLOT_WIDTH = 4
GLYPH_HEIGHT = 8
ALPHANUMERIC_GLYPHS = "0123456789ABCDEFLvHp"
PRODUCTION_LABELS = ("Lv", "Hp")
SYMBOLS = ("/", "meter-fill", "meter-cap")

SLASH_TILE = 10
METER_FILL_TILE = 11
METER_CAP_TILE = 12
RESERVED_TILES = (13, 14, 15)

SHEET_SIZE = (384, 256)
SHEET_BACKGROUND = (28, 30, 34)
PANEL_BACKGROUND = (248, 248, 248)
HUD_BACKGROUND = (248, 248, 248)
HUD_INK = (0, 0, 0)
CAPTION = (232, 232, 232)
MUTED_CAPTION = (168, 172, 180)
ACCENT = (176, 40, 24)

PROOFS = (
    "1F Lv 2 Hp 19/21",
    "99F Lv 99 Hp 999/999",
)


class HudFontAuditionError(ValueError):
    """The ROM or requested glyph violates the traced HUD-font contract."""


def read_source(rom):
    """Return and hash-verify the complete packed HUD atlas."""
    source = bytes(rom[HUD_SOURCE_OFFSET:HUD_SOURCE_OFFSET + HUD_SOURCE_SIZE])
    if len(source) != HUD_SOURCE_SIZE:
        raise HudFontAuditionError(
            "ROM is too small for HUD font source at %s" % HUD_SOURCE_LOCATION
        )
    actual = sha256(source).hexdigest()
    approved_digits = hud_font.approved_digit_bytes()
    approved_slash = hud_font.approved_slash_bytes()
    slash_at = hud_font.SLASH_TILE * SOURCE_TILE_BYTES
    installed = (
        source[:hud_font.DIGIT_BYTES] == approved_digits
        and sha256(source[hud_font.DIGIT_BYTES:slash_at]).hexdigest()
        == HUD_NATIVE_MIDDLE_SHA256
        and source[slash_at:slash_at + SOURCE_TILE_BYTES] == approved_slash
        and sha256(source[slash_at + SOURCE_TILE_BYTES:]).hexdigest()
        == HUD_NATIVE_AFTER_SLASH_SHA256
    )
    if actual != HUD_SOURCE_SHA256 and not installed:
        raise HudFontAuditionError(
            "HUD font source SHA-256 mismatch: got %s; expected native source "
            "or approved digits/slash with unchanged native spans" % actual
        )
    return source


def _decode_tile(raw):
    if len(raw) != SOURCE_TILE_BYTES:
        raise HudFontAuditionError("one HUD source tile must contain 16 bytes")
    rows = []
    for y in range(GLYPH_HEIGHT):
        low, high = raw[y * 2:y * 2 + 2]
        rows.append(tuple(
            (((high >> bit) & 1) << 1) | ((low >> bit) & 1)
            for bit in range(7, -1, -1)
        ))
    return tuple(rows)


def source_tiles(rom):
    """Decode all 16 source tiles into 8x8 color-index rows."""
    source = read_source(rom)
    return tuple(
        _decode_tile(source[index * SOURCE_TILE_BYTES:(index + 1) * SOURCE_TILE_BYTES])
        for index in range(SOURCE_TILE_COUNT)
    )


def _character_pixels(rom, character):
    tiles = source_tiles(rom)
    if character in ALPHANUMERIC_GLYPHS:
        index = ALPHANUMERIC_GLYPHS.index(character)
        tile = tiles[index // 2]
        left = (index % 2) * SLOT_WIDTH
        return tuple(row[left:left + SLOT_WIDTH] for row in tile)
    if character == "/":
        return tiles[SLASH_TILE]
    if character == "meter-fill":
        return tiles[METER_FILL_TILE]
    if character == "meter-cap":
        return tiles[METER_CAP_TILE]
    raise HudFontAuditionError("unknown HUD glyph %r" % character)


def glyph_raster(rom, character):
    """Return one reviewed glyph as literal ``.``/``#`` pixel rows."""
    return tuple(
        "".join("#" if color >= 2 else "." for color in row)
        for row in _character_pixels(rom, character)
    )


def _glyph_image(rom, character):
    pixels = _character_pixels(rom, character)
    image = Image.new("RGB", (len(pixels[0]), len(pixels)), HUD_BACKGROUND)
    target = image.load()
    for y, row in enumerate(pixels):
        for x, color in enumerate(row):
            if color >= 2:
                target[x, y] = HUD_INK
    return image


def render_hud_text(rom, text):
    """Render text using only the characters supported by the native HUD atlas."""
    pieces = []
    for character in text:
        if character == " ":
            pieces.append(Image.new("RGB", (SLOT_WIDTH, GLYPH_HEIGHT), HUD_BACKGROUND))
        elif character == "/":
            pieces.append(_glyph_image(rom, character))
        elif character in ALPHANUMERIC_GLYPHS:
            pieces.append(_glyph_image(rom, character))
        else:
            raise HudFontAuditionError(
                "text contains unsupported HUD character %r" % character
            )
    if not pieces:
        raise HudFontAuditionError("HUD proof text cannot be empty")
    image = Image.new(
        "RGB", (sum(piece.width for piece in pieces), GLYPH_HEIGHT), HUD_BACKGROUND
    )
    left = 0
    for piece in pieces:
        image.paste(piece, (left, 0))
        left += piece.width
    return image


def _nearest(image, scale):
    if scale == 1:
        return image.copy()
    return image.resize(
        (image.width * scale, image.height * scale), Image.Resampling.NEAREST
    )


def _centered_text(draw, box, text, fill, font):
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    x = box[0] + (box[2] - box[0] - width) // 2
    draw.text((x, box[1]), text, fill=fill, font=font)


def render_sheet(rom):
    """Return the native-size HUD-font contact sheet and a provenance report."""
    source_sha256 = sha256(read_source(rom)).hexdigest()
    image = Image.new("RGB", SHEET_SIZE, SHEET_BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((12, 6), "GB2 HUD FONT AUDITION", fill=CAPTION, font=font)
    draw.text(
        (12, 18),
        "%s - 16 packed 8x8 tiles / 4px glyph slots" % HUD_SOURCE_LOCATION,
        fill=MUTED_CAPTION,
        font=font,
    )
    draw.rectangle((12, 31, 371, 32), fill=ACCENT)
    draw.text((12, 36), "ALL HUD ALPHANUMERIC SLOTS", fill=CAPTION, font=font)

    cell_width = 36
    cell_height = 36
    grid_left = 12
    grid_top = 48
    for index, character in enumerate(ALPHANUMERIC_GLYPHS):
        column = index % 10
        row = index // 10
        left = grid_left + column * cell_width
        top = grid_top + row * cell_height
        draw.rectangle(
            (left, top, left + cell_width - 4, top + cell_height - 3),
            fill=PANEL_BACKGROUND,
        )
        label = character
        _centered_text(
            draw,
            (left, top + 1, left + cell_width - 4, top + 9),
            label,
            HUD_INK,
            font,
        )
        glyph = _nearest(_glyph_image(rom, character), 3)
        image.paste(
            glyph,
            (left + (cell_width - 4 - glyph.width) // 2, top + 10),
        )

    draw.text((12, 124), "HUD SYMBOL TILES", fill=CAPTION, font=font)
    symbol_boxes = (
        (12, 136, 116, 176),
        (128, 136, 244, 176),
        (256, 136, 371, 176),
    )
    for symbol, box in zip(SYMBOLS, symbol_boxes):
        draw.rectangle(box, fill=PANEL_BACKGROUND)
        _centered_text(draw, box, symbol, HUD_INK, font)
        glyph = _nearest(_glyph_image(rom, symbol), 3)
        image.paste(
            glyph,
            (box[2] - glyph.width - 8, box[1] + (box[3] - box[1] - glyph.height) // 2),
        )

    draw.text((12, 184), "HUD LAYOUT PROOFS", fill=CAPTION, font=font)
    for row, proof in enumerate(PROOFS):
        top = 197 + row * 24
        draw.rectangle((12, top, 371, top + 19), fill=PANEL_BACKGROUND)
        rendered = _nearest(render_hud_text(rom, proof), 2)
        image.paste(rendered, (190, top + 2))
        draw.text((18, top + 5), proof, fill=HUD_INK, font=font)

    draw.text(
        (12, 246),
        "SHA-256 " + source_sha256[:24] + "...",
        fill=MUTED_CAPTION,
        font=font,
    )

    report = {
        "source": HUD_SOURCE_LOCATION,
        "source_sha256": source_sha256,
        "source_tiles": SOURCE_TILE_COUNT,
        "alphanumeric_count": len(ALPHANUMERIC_GLYPHS),
        "alphanumeric_glyphs": ALPHANUMERIC_GLYPHS,
        "production_labels": list(PRODUCTION_LABELS),
        "symbols": list(SYMBOLS),
        "reserved_tiles": list(RESERVED_TILES),
        "proofs": list(PROOFS),
    }
    return image, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "rom", nargs="?", type=Path, default=DEFAULT_ROM,
        help="original or compatible Shiren GB2 ROM",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="PNG output path (default: build/hud_font_audition.png)",
    )
    parser.add_argument(
        "--scale", type=int, default=3,
        help="nearest-neighbour output scale (default: 3)",
    )
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale must be positive")
    try:
        rom = args.rom.read_bytes()
        sheet, report = render_sheet(rom)
        output = _nearest(sheet, args.scale)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output.save(args.output)
    except (OSError, HudFontAuditionError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    print("source : %s sha256=%s" % (report["source"], report["source_sha256"]))
    print(
        "glyphs : %s (labels %s; symbols %s)"
        % (
            report["alphanumeric_glyphs"],
            ", ".join(report["production_labels"]),
            ", ".join(report["symbols"]),
        )
    )
    print("output : %s (%dx)" % (args.output, args.scale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
