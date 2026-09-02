#!/usr/bin/env python3
"""Render GB2's dedicated shop-price digit font directly from ROM bytes.

Shop price tags do not use either the localized dialogue font or the dungeon
HUD atlas.  Bank 3 stores ten independent 8x8 2bpp digit tiles at
``$5642-$56E1``.  The live price painter packs the left five pixels of each
tile at a fixed five-pixel advance.  In the user-captured shop view, source
color 3 is black, color 1 is white, and color 2 is the darker edge shade.

This tool is a read-only audition/contact-sheet renderer.  It verifies the
complete ten-tile source and never edits a font asset or ROM.

Example::

    python3 tools/shop_price_font_audition.py
"""

import argparse
from hashlib import sha256
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - exercised only without Pillow
    raise SystemExit(
        "shop-price font audition requires Pillow (`python3 -m pip install pillow`)"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
DEFAULT_ROM = ROOT / ROM_NAME
DEFAULT_OUTPUT = ROOT / "build" / "shop_price_font_audition.png"

BANK_SIZE = 0x4000
SOURCE_BANK = 0x03
SOURCE_ADDRESS = 0x5642
SOURCE_OFFSET = SOURCE_BANK * BANK_SIZE + SOURCE_ADDRESS - 0x4000
SOURCE_LOCATION = "3:$5642-$56E1"
SOURCE_TILE_BYTES = 16
SOURCE_TILE_COUNT = 10
SOURCE_SIZE = SOURCE_TILE_BYTES * SOURCE_TILE_COUNT
SOURCE_SHA256 = (
    "4df296fd16d1142cf821259614eadb07df7be4747a69fdab58db3182b725fb46"
)

DIGITS = "0123456789"
GLYPH_WIDTH = 5
GLYPH_HEIGHT = 8

BACKGROUND_COLOR = 3
INK_COLOR = 1
SHADE_COLOR = 2
PREVIEW_BACKGROUND = (0, 0, 0)
PREVIEW_INK = (240, 240, 240)
PREVIEW_SHADE = (168, 168, 168)
PREVIEW_COLORS = {
    BACKGROUND_COLOR: PREVIEW_BACKGROUND,
    INK_COLOR: PREVIEW_INK,
    SHADE_COLOR: PREVIEW_SHADE,
}

PRICE_PROOFS = ("50", "100", "200", "650", "800", "1200", "1500", "99999")

SHEET_SIZE = (480, 360)
SHEET_BACKGROUND = (28, 30, 34)
PANEL_BACKGROUND = (44, 47, 52)
CAPTION = (232, 232, 232)
MUTED_CAPTION = (168, 172, 180)
ACCENT = (176, 40, 24)


class ShopPriceFontAuditionError(ValueError):
    """The ROM or requested proof violates the native shop-font contract."""


def read_source(rom):
    """Return and hash-verify all ten native shop digit tiles."""
    source = bytes(rom[SOURCE_OFFSET:SOURCE_OFFSET + SOURCE_SIZE])
    if len(source) != SOURCE_SIZE:
        raise ShopPriceFontAuditionError(
            "ROM is too small for shop-price font source at %s" % SOURCE_LOCATION
        )
    actual = sha256(source).hexdigest()
    if actual != SOURCE_SHA256:
        raise ShopPriceFontAuditionError(
            "shop-price source SHA-256 mismatch: got %s, expected %s"
            % (actual, SOURCE_SHA256)
        )
    return source


def _decode_tile(raw):
    """Decode one Game Boy 2bpp tile to eight rows of color indexes."""
    if len(raw) != SOURCE_TILE_BYTES:
        raise ShopPriceFontAuditionError(
            "one shop-price source tile must contain 16 bytes"
        )
    rows = []
    for y in range(GLYPH_HEIGHT):
        low, high = raw[y * 2:y * 2 + 2]
        rows.append(tuple(
            (((high >> bit) & 1) << 1) | ((low >> bit) & 1)
            for bit in range(7, -1, -1)
        ))
    return tuple(rows)


def source_tiles(rom):
    """Decode the complete ten-tile native digit source."""
    source = read_source(rom)
    return tuple(
        _decode_tile(
            source[index * SOURCE_TILE_BYTES:(index + 1) * SOURCE_TILE_BYTES]
        )
        for index in range(SOURCE_TILE_COUNT)
    )


def _digit_pixels(rom, digit):
    if digit not in DIGITS or len(digit) != 1:
        raise ShopPriceFontAuditionError("shop price glyphs are digits only")
    tile = source_tiles(rom)[DIGITS.index(digit)]
    pixels = tuple(row[:GLYPH_WIDTH] for row in tile)
    unexpected = {
        color for row in pixels for color in row
        if color not in PREVIEW_COLORS
    }
    if unexpected:
        raise ShopPriceFontAuditionError(
            "shop digit %s uses unexpected color indexes %s"
            % (digit, sorted(unexpected))
        )
    return pixels


def glyph_raster(rom, digit):
    """Return one exact five-pixel shop glyph as color-index strings."""
    return tuple("".join(str(color) for color in row) for row in _digit_pixels(rom, digit))


def render_price(rom, text):
    """Pack a digits-only price at the native five-pixel advance."""
    if not text or any(character not in DIGITS for character in text):
        raise ShopPriceFontAuditionError("shop price proofs accept digits only")
    image = Image.new(
        "RGB",
        (len(text) * GLYPH_WIDTH, GLYPH_HEIGHT),
        PREVIEW_BACKGROUND,
    )
    target = image.load()
    for index, character in enumerate(text):
        for y, row in enumerate(_digit_pixels(rom, character)):
            for x, color in enumerate(row):
                target[index * GLYPH_WIDTH + x, y] = PREVIEW_COLORS[color]
    return image


def _nearest(image, scale):
    if scale == 1:
        return image.copy()
    return image.resize(
        (image.width * scale, image.height * scale),
        Image.Resampling.NEAREST,
    )


def _centered_text(draw, box, text, fill, font):
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    x = box[0] + (box[2] - box[0] - width) // 2
    draw.text((x, box[1]), text, fill=fill, font=font)


def render_sheet(rom):
    """Return the native-size contact sheet and its provenance report."""
    read_source(rom)
    image = Image.new("RGB", SHEET_SIZE, SHEET_BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((12, 6), "GB2 SHOP-PRICE FONT AUDITION", fill=CAPTION, font=font)
    draw.text(
        (12, 18),
        "%s - ten native 2bpp tiles / five-pixel packed digits" % SOURCE_LOCATION,
        fill=MUTED_CAPTION,
        font=font,
    )
    draw.rectangle((12, 31, 467, 32), fill=ACCENT)

    draw.text((12, 38), "CAPTURED SHOP PALETTE", fill=CAPTION, font=font)
    palette = (
        ("3 BLACK", PREVIEW_BACKGROUND),
        ("1 WHITE", PREVIEW_INK),
        ("2 SHADE", PREVIEW_SHADE),
    )
    for index, (label, color) in enumerate(palette):
        left = 152 + index * 100
        draw.rectangle((left, 37, left + 14, 51), fill=color, outline=CAPTION)
        draw.text((left + 20, 39), label, fill=MUTED_CAPTION, font=font)

    draw.text((12, 58), "ALL NATIVE DIGITS", fill=CAPTION, font=font)
    grid_top = 72
    cell_width = 45
    for index, digit in enumerate(DIGITS):
        left = 12 + index * cell_width
        right = left + 41
        draw.rectangle((left, grid_top, right, grid_top + 63), fill=PANEL_BACKGROUND)
        _centered_text(
            draw, (left, grid_top + 2, right, grid_top + 11), digit, CAPTION, font
        )
        glyph = _nearest(render_price(rom, digit), 6)
        image.paste(
            glyph,
            (left + (right - left + 1 - glyph.width) // 2, grid_top + 14),
        )

    draw.rectangle((12, 144, 467, 145), fill=ACCENT)
    draw.text((12, 152), "PACKED PRICE PROOFS", fill=CAPTION, font=font)
    for index, proof in enumerate(PRICE_PROOFS):
        column = index % 2
        row = index // 2
        left = 12 + column * 234
        top = 168 + row * 42
        right = left + 221
        draw.rectangle((left, top, right, top + 35), fill=PANEL_BACKGROUND)
        draw.text((left + 7, top + 12), proof, fill=CAPTION, font=font)
        rendered = _nearest(render_price(rom, proof), 4)
        image.paste(rendered, (right - rendered.width - 7, top + 2))

    draw.text(
        (12, 344),
        "READ-ONLY: exact source pixels; no font install and no ROM changes",
        fill=MUTED_CAPTION,
        font=font,
    )

    report = {
        "source": SOURCE_LOCATION,
        "source_sha256": SOURCE_SHA256,
        "source_tiles": SOURCE_TILE_COUNT,
        "digit_count": len(DIGITS),
        "digits": DIGITS,
        "glyph_size": [GLYPH_WIDTH, GLYPH_HEIGHT],
        "advance": GLYPH_WIDTH,
        "palette_indexes": {
            "background": BACKGROUND_COLOR,
            "ink": INK_COLOR,
            "shade": SHADE_COLOR,
        },
        "palette_rgb": {
            "background": list(PREVIEW_BACKGROUND),
            "ink": list(PREVIEW_INK),
            "shade": list(PREVIEW_SHADE),
        },
        "proofs": list(PRICE_PROOFS),
        "rom_modified": False,
    }
    return image, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "rom", nargs="?", type=Path, default=DEFAULT_ROM,
        help="matching original Shiren GB2 ROM",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="PNG output path (default: build/shop_price_font_audition.png)",
    )
    parser.add_argument(
        "--scale", type=int, default=2,
        help="nearest-neighbour output scale (default: 2)",
    )
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale must be positive")
    try:
        sheet, report = render_sheet(args.rom.read_bytes())
        output = _nearest(sheet, args.scale)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output.save(args.output)
    except (OSError, ShopPriceFontAuditionError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    print("source : %s sha256=%s" % (report["source"], report["source_sha256"]))
    print("digits : %s (%d x %d; %dpx advance)" % (
        report["digits"], GLYPH_WIDTH, GLYPH_HEIGHT, GLYPH_WIDTH
    ))
    print("palette: 3=black 1=white 2=shade (#A8A8A8)")
    print("output : %s (%dx)" % (args.output, args.scale))
    print("ROM    : unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
