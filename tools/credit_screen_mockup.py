#!/usr/bin/env python3
"""Render a review-only Inter candidate over GB2's native credit card.

The clean ROM supplies the stable credit frame, including both native ``© 2001``
rows.  Only the two Japanese name bands are cleared and repainted.  This tool
does not patch or write a ROM.
"""

import argparse
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


NATIVE_SIZE = (160, 144)
CREDIT_FRAME = 320
SUPERSAMPLE = 8
BLACK = (0, 0, 0)
DARK = (64, 64, 64)
MID = (120, 120, 120)
WHITE = (248, 248, 248)
PALETTE = (BLACK, DARK, MID, WHITE)
PIXEL_SYMBOLS = {
    BLACK: ".",
    DARK: "d",
    MID: "m",
    WHITE: "#",
}

# Coverage is quantized into GB2's three native ink levels.  These are not the
# green GB1 ending-credit treatment and do not add a separate offset shadow.
LOW_COVERAGE = 48
MID_COVERAGE = 128
HIGH_COVERAGE = 208


@dataclass(frozen=True)
class CreditLine:
    text: str
    left: int
    top: int
    bottom: int
    cap_height: int


LINES = (
    CreditLine("CHUNSOFT", left=36, top=57, bottom=71, cap_height=10),
    CreditLine("Koichi Sugiyama", left=32, top=89, bottom=103, cap_height=10),
)

STRIPS = (
    ("chunsoft", "A0", (16, 56, 144, 72), "F3:$5F00-$60FF"),
    ("koichi_sugiyama", "E0", (16, 88, 144, 104), "F3:$6300-$64FF"),
)


def capture_native_credit(rom_path, pyboy_class):
    """Capture the fully bright clean-boot credit frame at native resolution."""
    pyboy = pyboy_class(str(rom_path), window="null", sound_emulated=False)
    try:
        for _frame in range(CREDIT_FRAME + 1):
            pyboy.tick()
        image = pyboy.screen.image.convert("RGB").copy()
    finally:
        pyboy.stop(save=False)

    if image.size != NATIVE_SIZE:
        raise ValueError("native credit frame is %r, expected %r" % (image.size, NATIVE_SIZE))
    colors = set(image.getdata())
    if colors != set(PALETTE):
        raise ValueError("native credit frame palette changed: %r" % sorted(colors))
    return image


@lru_cache(maxsize=None)
def _font_size(font_path, cap_height):
    target = cap_height * SUPERSAMPLE
    best = None
    distance = 1 << 30
    for size in range(6, 300):
        font = ImageFont.truetype(font_path, size)
        box = font.getbbox("H")
        error = abs((box[3] - box[1]) - target)
        if error < distance:
            best = size
            distance = error
    return best


def _coverage(font_path, text, cap_height):
    """Return phase-selected grayscale coverage at native pixel resolution."""
    font_path = str(font_path)
    font = ImageFont.truetype(font_path, _font_size(font_path, cap_height))
    best = None
    for dy in range(SUPERSAMPLE):
        for dx in range(SUPERSAMPLE):
            high = Image.new("L", (4000, 700), 0)
            draw = ImageDraw.Draw(high)
            x = float(200 + dx)
            for character in text:
                draw.text((x, 200 + dy), character, 255, font=font)
                x += font.getlength(character)
            box = high.getbbox()
            high = high.crop(
                (
                    box[0] - 4 * SUPERSAMPLE,
                    box[1] - 4 * SUPERSAMPLE,
                    box[2] + 4 * SUPERSAMPLE,
                    box[3] + 4 * SUPERSAMPLE,
                )
            )
            box = high.getbbox()
            left = box[0] // SUPERSAMPLE * SUPERSAMPLE
            top = box[1] // SUPERSAMPLE * SUPERSAMPLE
            right = (box[2] + SUPERSAMPLE - 1) // SUPERSAMPLE * SUPERSAMPLE
            bottom = (box[3] + SUPERSAMPLE - 1) // SUPERSAMPLE * SUPERSAMPLE
            high = high.crop((left, top, right, bottom))
            low = high.resize(
                (high.width // SUPERSAMPLE, high.height // SUPERSAMPLE),
                Image.Resampling.BOX,
            )
            score = sum(min(value, 255 - value) for value in low.getdata())
            if best is None or score < best[0]:
                best = score, low
    return best[1]


def _level_masks(font_path, line):
    coverage = _coverage(font_path, line.text, line.cap_height)
    crop_box = coverage.point(
        lambda value: 255 if value >= LOW_COVERAGE else 0,
        mode="1",
    ).getbbox()
    if crop_box is None:
        raise ValueError("cannot render an empty credit line")
    coverage = coverage.crop(crop_box)
    masks = (
        coverage.point(
            lambda value: 255 if LOW_COVERAGE <= value < MID_COVERAGE else 0,
            mode="1",
        ),
        coverage.point(
            lambda value: 255 if MID_COVERAGE <= value < HIGH_COVERAGE else 0,
            mode="1",
        ),
        coverage.point(
            lambda value: 255 if value >= HIGH_COVERAGE else 0,
            mode="1",
        ),
    )
    return masks


def render_candidate(native, font_path):
    """Replace only the two native Japanese-name bands with English artwork."""
    if native.size != NATIVE_SIZE:
        raise ValueError("native reference must be 160x144")
    candidate = native.convert("RGB").copy()
    draw = ImageDraw.Draw(candidate)

    for line in LINES:
        draw.rectangle((0, line.top, 159, line.bottom - 1), fill=BLACK)
        masks = _level_masks(font_path, line)
        width, height = masks[0].size
        if line.left + width > 152:
            raise ValueError("%r exceeds the safe credit width" % line.text)
        if height > line.bottom - line.top:
            raise ValueError("%r exceeds its native line band" % line.text)
        for mask, color in zip(masks, (DARK, MID, WHITE)):
            ink = Image.new("RGB", mask.size, color)
            candidate.paste(ink, (line.left, line.top), mask)

    if not set(candidate.getdata()).issubset(PALETTE):
        raise AssertionError("candidate introduced a non-native color")
    return candidate


def ink_bounds(image, line):
    points = [
        (x, y)
        for y in range(line.top, line.bottom)
        for x in range(image.width)
        if image.getpixel((x, y)) != BLACK
    ]
    if not points:
        raise ValueError("credit line has no ink")
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def ink_colors(image, line):
    return {
        image.getpixel((x, y))
        for y in range(line.top, line.bottom)
        for x in range(image.width)
        if image.getpixel((x, y)) != BLACK
    }


def comparison(native, candidate, scale=6):
    nearest = Image.Resampling.NEAREST
    native_large = native.resize((160 * scale, 144 * scale), nearest)
    candidate_large = candidate.resize((160 * scale, 144 * scale), nearest)
    sheet = Image.new("RGB", (320 * scale, 144 * scale), BLACK)
    sheet.paste(native_large, (0, 0))
    sheet.paste(candidate_large, (160 * scale, 0))
    return sheet


def frozen_asset(candidate, font_path):
    """Return the reviewed name strips as editable four-level pixel rows."""
    line_by_name = {
        "chunsoft": LINES[0],
        "koichi_sugiyama": LINES[1],
    }
    strips = []
    for name, first_tile, rect, rom_source in STRIPS:
        crop = candidate.crop(rect)
        rows = [
            "".join(PIXEL_SYMBOLS[crop.getpixel((x, y))] for x in range(crop.width))
            for y in range(crop.height)
        ]
        strips.append(
            {
                "name": name,
                "text": line_by_name[name].text,
                "first_tile": first_tile,
                "tile_count": 32,
                "screen_rect": list(rect),
                "rom_source": rom_source,
                "rows": rows,
            }
        )
    return {
        "format": "shiren-gb2-credit-screen-v1",
        "status": "visually approved mockup; production insertion source",
        "content": ["© 2001", "CHUNSOFT", "© 2001", "Koichi Sugiyama"],
        "font": {
            "family": "Inter",
            "style": "SemiBold",
            "version": "4.1",
            "file": "assets/fonts/candidates/Inter-SemiBold-4.1.ttf",
            "sha256": sha256(Path(font_path).read_bytes()).hexdigest(),
            "license": "SIL Open Font License 1.1",
            "license_file": "licenses/OFL-1.1-Inter.txt",
        },
        "render": {
            "generator": "tools/credit_screen_mockup.py",
            "native_frame": CREDIT_FRAME,
            "palette": [list(color) for color in PALETTE],
            "pixel_symbols": {
                ".": "background",
                "d": "dark gray",
                "m": "mid gray",
                "#": "white",
            },
            "coverage_thresholds": [
                LOW_COVERAGE,
                MID_COVERAGE,
                HIGH_COVERAGE,
            ],
            "gb1_credit_layout_reused": False,
        },
        "strips": strips,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--comparison-output", type=Path)
    parser.add_argument("--asset-output", type=Path)
    parser.add_argument("--scale", type=int, default=6)
    args = parser.parse_args(argv)

    from capture_dialogue import _pyboy_class

    native = capture_native_credit(args.rom, _pyboy_class())
    candidate = render_candidate(native, args.font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidate.resize(
        (candidate.width * args.scale, candidate.height * args.scale),
        Image.Resampling.NEAREST,
    ).save(args.output)
    if args.comparison_output:
        args.comparison_output.parent.mkdir(parents=True, exist_ok=True)
        comparison(native, candidate, args.scale).save(args.comparison_output)
    if args.asset_output:
        args.asset_output.parent.mkdir(parents=True, exist_ok=True)
        args.asset_output.write_text(
            json.dumps(frozen_asset(candidate, args.font), indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
