#!/usr/bin/env python3
"""Compare Thin Pixel-7 source rasters with the installed drop-shadow bake.

This is a read-only production audit.  It loads the approved English raster and
advances, paints palette-color-2 gray one pixel right/down from every foreground
pixel, then redraws the unchanged palette-color-3 black glyph on top.  On a
bottom-clipped glyph, a disconnected bottom-right gray pixel moves one pixel left
to join the visible stroke.  The output compares the source raster with the
installed treatment for all 79 supported characters.

No font asset or ROM is modified.
"""

import argparse
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - only exercised without Pillow
    raise SystemExit(
        "font-shadow audition requires Pillow (`python3 -m pip install pillow`)"
    ) from exc

import english
import english_font


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "font_shadow_audition.png"

SHADOW_OFFSET = (1, 1)
BOTTOM_ORPHAN_SHIFT = (-1, 0)
BACKGROUND_COLOR = 1
SHADOW_COLOR = 2
INK_COLOR = 3
CELL_SIZE = (8, 8)

# Stable menu palette 7 captured in the Mamel, Bank Teller, Blacksmith, and
# completed-rescue states.  Production's real contract is palette index 2;
# these values also make the PNG match that route's exact gray.
MENU_PALETTE = (
    (255, 255, 255),
    (255, 255, 255),
    (172, 172, 172),
    (0, 0, 0),
)
PREVIEW_BACKGROUND = MENU_PALETTE[BACKGROUND_COLOR]
PREVIEW_SHADOW = MENU_PALETTE[SHADOW_COLOR]
PREVIEW_INK = MENU_PALETTE[INK_COLOR]
SHEET_BACKGROUND = (28, 30, 34)
SHEET_CAPTION = (236, 236, 236)
SHEET_MUTED = (168, 172, 180)
SHEET_ACCENT = (176, 40, 24)

SHEET_SIZE = (720, 560)
ORDERED_CHARACTERS = tuple(
    character
    for character, _code in sorted(
        english.ENGLISH_CODES.items(), key=lambda pair: pair[1]
    )
)
INVENTORY_ROWS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    ".,'-?!():/[]+~%\"",
)
EDGE_CASES = ("g", "j", "p", "q", "y", "Q", ",", "+", "%")
SAMPLE_LINES = (
    "Shiren found a +99 Sword!",
    "Hp 127/127  Floor 99F",
    "The quick brown fox jumps.",
)


class FontShadowAuditionError(ValueError):
    """The approved raster or audition request violates the comparison contract."""


def _validate_rows(rows):
    if (
        not isinstance(rows, (list, tuple))
        or len(rows) != CELL_SIZE[1]
        or any(
            not isinstance(row, str)
            or len(row) != CELL_SIZE[0]
            or set(row) - {".", "#"}
            for row in rows
        )
    ):
        raise FontShadowAuditionError("glyph must contain eight 8-column .# rows")


def _raw_shadow_pixels(rows):
    """Return the literal +1,+1 treatment before the orphan cleanup."""
    _validate_rows(rows)
    width, height = CELL_SIZE
    dx, dy = SHADOW_OFFSET
    pixels = [[BACKGROUND_COLOR] * width for _ in range(height)]
    ink = {
        (x, y)
        for y, row in enumerate(rows)
        for x, pixel in enumerate(row)
        if pixel == "#"
    }

    # Paint the offset layer first.  Native-cell overflow is deliberately
    # clipped here because this is the production-size 8x8 proposal.
    for x, y in ink:
        shadow_x, shadow_y = x + dx, y + dy
        if 0 <= shadow_x < width and 0 <= shadow_y < height:
            pixels[shadow_y][shadow_x] = SHADOW_COLOR

    # Redraw the source black on top exactly as proposed.  This also turns any
    # gray/foreground overlap back into the unchanged foreground shape.
    for x, y in ink:
        pixels[y][x] = INK_COLOR
    return pixels


def _move_bottom_orphan_left(pixels, ink):
    """Join one disconnected bottom-right gray pixel on a clipped glyph."""
    _width, height = CELL_SIZE
    if not any(y + SHADOW_OFFSET[1] >= height for _x, y in ink):
        return False

    bottom = pixels[height - 1]
    gray = [x for x, color in enumerate(bottom) if color == SHADOW_COLOR]
    if not gray:
        return False
    rightmost = max(gray)
    if (
        rightmost < 2
        or bottom[rightmost - 1] != BACKGROUND_COLOR
        or bottom[rightmost - 2] not in (SHADOW_COLOR, INK_COLOR)
    ):
        return False

    bottom[rightmost] = BACKGROUND_COLOR
    bottom[rightmost + BOTTOM_ORPHAN_SHIFT[0]] = SHADOW_COLOR
    return True


def shadow_pixels(rows):
    """Return the cleaned installed 8x8 color indexes for one glyph."""
    _validate_rows(rows)
    ink = _ink_points(rows)
    pixels = _raw_shadow_pixels(rows)
    _move_bottom_orphan_left(pixels, ink)
    return tuple(tuple(row) for row in pixels)


def shadow_raster(rows):
    """Return the installed cell as literal background/gray/black symbols."""
    symbols = {
        BACKGROUND_COLOR: ".",
        SHADOW_COLOR: "g",
        INK_COLOR: "#",
    }
    return tuple(
        "".join(symbols[color] for color in row)
        for row in shadow_pixels(rows)
    )


def encode_shadow_2bpp(rows):
    """Encode background=1, shadow=2, and ink=3 for the native renderer."""
    encoded = bytearray()
    for row in shadow_pixels(rows):
        low = high = 0
        for x, color in enumerate(row):
            bit = 7 - x
            low |= (color & 1) << bit
            high |= ((color >> 1) & 1) << bit
        encoded.extend((low, high))
    return bytes(encoded)


def _ink_points(rows):
    _validate_rows(rows)
    return {
        (x, y)
        for y, row in enumerate(rows)
        for x, pixel in enumerate(row)
        if pixel == "#"
    }


def analyze(font_asset):
    """Report all cell clipping and advance overhang introduced by the shadow."""
    if set(font_asset.rows) != set(ORDERED_CHARACTERS):
        raise FontShadowAuditionError("approved English glyph inventory changed")

    width, height = CELL_SIZE
    dx, dy = SHADOW_OFFSET
    clipped = {}
    overhang = {}
    adjusted = {}
    for character in ORDERED_CHARACTERS:
        ink = _ink_points(font_asset.rows[character])
        bottom = {
            (x + dx, y + dy)
            for x, y in ink
            if y + dy >= height
        }
        if bottom:
            clipped[character] = len(bottom)

        gray = {
            (x + dx, y + dy)
            for x, y in ink
            if 0 <= x + dx < width and 0 <= y + dy < height
        } - ink
        beyond = {
            point for point in gray if point[0] >= font_asset.advances[character]
        }
        if beyond:
            overhang[character] = len(beyond)

        raw = _raw_shadow_pixels(font_asset.rows[character])
        cleaned = [row[:] for row in raw]
        if _move_bottom_orphan_left(cleaned, ink):
            adjusted[character] = 1

    return {
        "font": font_asset.name,
        "glyph_count": len(ORDERED_CHARACTERS),
        "shadow_offset": list(SHADOW_OFFSET),
        "palette_roles": {
            "background": BACKGROUND_COLOR,
            "shadow": SHADOW_COLOR,
            "ink": INK_COLOR,
        },
        "bottom_clipped_glyphs": sorted(clipped),
        "bottom_clipped_shadow_pixels": sum(clipped.values()),
        "bottom_orphan_shift": list(BOTTOM_ORPHAN_SHIFT),
        "bottom_orphan_adjusted_glyphs": sorted(adjusted),
        "bottom_orphan_pixels_moved_left": sum(adjusted.values()),
        "advance_overhang_glyphs": sorted(overhang),
        "advance_overhang_shadow_pixels": sum(overhang.values()),
        "inventory_rows": list(INVENTORY_ROWS),
        "rom_modified": False,
    }


def render_text(font_asset, text, shadow):
    """Render one line at its real proportional advances and return ``(image, width)``."""
    if not text:
        raise FontShadowAuditionError("audition text cannot be empty")
    unsupported = sorted(set(text) - set(ORDERED_CHARACTERS))
    if unsupported:
        raise FontShadowAuditionError(
            "unsupported audition character(s): %s" % repr("".join(unsupported))
        )

    advance = sum(font_asset.advances[character] for character in text)
    image_width = advance + (SHADOW_OFFSET[0] if shadow else 0)
    image = Image.new("RGB", (image_width, CELL_SIZE[1]), PREVIEW_BACKGROUND)
    target = image.load()
    runs = []
    pen = 0
    for character in text:
        ink = _ink_points(font_asset.rows[character])
        gray = {
            (x, y)
            for y, row in enumerate(shadow_pixels(font_asset.rows[character]))
            for x, color in enumerate(row)
            if color == SHADOW_COLOR
        }
        runs.append((pen, ink, gray))
        pen += font_asset.advances[character]

    if shadow:
        for pen, _ink, gray in runs:
            for x, y in gray:
                draw_x, draw_y = pen + x, y
                if 0 <= draw_x < image.width and 0 <= draw_y < image.height:
                    target[draw_x, draw_y] = PREVIEW_SHADOW

    # Paint all line foregrounds after all line shadows, preserving black where
    # a following glyph intersects the previous glyph's one-pixel overhang.
    for pen, ink, _gray in runs:
        for x, y in ink:
            target[pen + x, y] = PREVIEW_INK
    return image, advance


def _render_cell(font_asset, character, shadow):
    rows = font_asset.rows[character]
    if shadow:
        colors = shadow_pixels(rows)
    else:
        colors = tuple(
            tuple(INK_COLOR if pixel == "#" else BACKGROUND_COLOR for pixel in row)
            for row in rows
        )
    palette = {
        BACKGROUND_COLOR: PREVIEW_BACKGROUND,
        SHADOW_COLOR: PREVIEW_SHADOW,
        INK_COLOR: PREVIEW_INK,
    }
    image = Image.new("RGB", CELL_SIZE, PREVIEW_BACKGROUND)
    target = image.load()
    for y, row in enumerate(colors):
        for x, color in enumerate(row):
            target[x, y] = palette[color]
    return image


def _nearest(image, scale):
    if scale == 1:
        return image.copy()
    return image.resize(
        (image.width * scale, image.height * scale), Image.Resampling.NEAREST
    )


def _paste_line(sheet, font_asset, text, shadow, position, scale=2):
    line, _advance = render_text(font_asset, text, shadow)
    sheet.paste(_nearest(line, scale), position)


def render_sheet(font_asset):
    """Render the complete current/proposed comparison sheet and return its report."""
    report = analyze(font_asset)
    sheet = Image.new("RGB", SHEET_SIZE, SHEET_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    caption_font = ImageFont.load_default()

    draw.text((16, 8), "THIN PIXEL-7 DROP-SHADOW AUDIT", fill=SHEET_CAPTION, font=caption_font)
    draw.text(
        (16, 21),
        "color-2 gray +1,+1; black on top; disconnected cutoff pixels shifted left",
        fill=SHEET_MUTED,
        font=caption_font,
    )
    draw.rectangle((16, 36, 703, 37), fill=SHEET_ACCENT)
    draw.text((16, 45), "SOURCE / NO SHADOW", fill=SHEET_CAPTION, font=caption_font)
    draw.text((370, 45), "INSTALLED +1,+1 SHADOW", fill=SHEET_CAPTION, font=caption_font)

    inventory_top = 63
    for index, text in enumerate(INVENTORY_ROWS):
        top = inventory_top + index * 39
        label = ("uppercase", "lowercase", "digits", "punctuation")[index]
        draw.text((16, top), label, fill=SHEET_MUTED, font=caption_font)
        draw.text((370, top), label, fill=SHEET_MUTED, font=caption_font)
        _paste_line(sheet, font_asset, text, False, (16, top + 11), scale=2)
        _paste_line(sheet, font_asset, text, True, (370, top + 11), scale=2)

    draw.rectangle((16, 220, 703, 221), fill=SHEET_ACCENT)
    draw.text(
        (16, 228),
        "8x8 EDGE CELLS — cutoff orphans joined left; % retains its advance overhang",
        fill=SHEET_CAPTION,
        font=caption_font,
    )
    for shadow, top, label in (
        (False, 252, "source"),
        (True, 326, "installed"),
    ):
        draw.text((16, top + 18), label, fill=SHEET_MUTED, font=caption_font)
        for index, character in enumerate(EDGE_CASES):
            left = 72 + index * 68
            draw.rectangle((left - 1, top - 1, left + 48, top + 48), outline=SHEET_MUTED)
            sheet.paste(_nearest(_render_cell(font_asset, character, shadow), 6), (left, top))
            bounds = draw.textbbox((0, 0), character, font=caption_font)
            label_width = bounds[2] - bounds[0]
            draw.text(
                (left + (48 - label_width) // 2, top + 52),
                character,
                fill=SHEET_CAPTION,
                font=caption_font,
            )

    draw.rectangle((16, 401, 703, 402), fill=SHEET_ACCENT)
    draw.text((16, 409), "IN-GAME COPY PROOFS", fill=SHEET_CAPTION, font=caption_font)
    for row, text in enumerate(SAMPLE_LINES):
        top = 426 + row * 30
        draw.rectangle((16, top, 349, top + 21), fill=PREVIEW_BACKGROUND)
        draw.rectangle((370, top, 703, top + 21), fill=PREVIEW_BACKGROUND)
        _paste_line(sheet, font_asset, text, False, (22, top + 3), scale=2)
        _paste_line(sheet, font_asset, text, True, (376, top + 3), scale=2)

    draw.text(
        (16, 522),
        "8x8: 10 shadows clip; 4 visible orphans move left on , g, j, y; % overhang stays 3 pixels.",
        fill=SHEET_MUTED,
        font=caption_font,
    )
    draw.text(
        (16, 536),
        "READ-ONLY AUDIT — this command does not alter assets, advances, or a ROM.",
        fill=SHEET_CAPTION,
        font=caption_font,
    )
    return sheet, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="PNG output path (default: build/font_shadow_audition.png)",
    )
    parser.add_argument(
        "--scale", type=int, default=2,
        help="nearest-neighbour output scale (default: 2)",
    )
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale must be positive")
    try:
        font_asset = english_font.load_approved()
        sheet, report = render_sheet(font_asset)
        output = _nearest(sheet, args.scale)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output.save(args.output)
    except (OSError, english_font.FontError, FontShadowAuditionError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    print("font    : %s (%d glyphs)" % (report["font"], report["glyph_count"]))
    print("shadow  : +%d,+%d gray-under / black-over" % SHADOW_OFFSET)
    print(
        "8x8     : %d clipped gray pixel(s) on %s"
        % (
            report["bottom_clipped_shadow_pixels"],
            "".join(report["bottom_clipped_glyphs"]),
        )
    )
    print(
        "cleanup : %d bottom orphan pixel(s) moved left on %s"
        % (
            report["bottom_orphan_pixels_moved_left"],
            "".join(report["bottom_orphan_adjusted_glyphs"]),
        )
    )
    print(
        "advance : %d overhang gray pixel(s) on %s"
        % (
            report["advance_overhang_shadow_pixels"],
            "".join(report["advance_overhang_glyphs"]),
        )
    )
    print("output  : %s (%dx)" % (args.output, args.scale))
    print("ROM     : unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
