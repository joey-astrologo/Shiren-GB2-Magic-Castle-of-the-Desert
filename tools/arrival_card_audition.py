#!/usr/bin/env python3
"""Render all GB2 arrival-card selectors with a candidate TTF/OTF.

This is a ROM-independent artwork audition, not a production installer.  It reproduces
the measured 160x144 GB2 composition: a centered 16-pixel location band, a red underline
snapped to the native 16-pixel block grid, and the native Latin 0-9/F floor blocks.  The
audition raises F by one pixel to correct its visibly low bright cap; the production ROM
is not changed by this tool.  A magnified floor proof at the bottom makes that adjustment
easy to inspect.  The default ``native-aa`` treatment quantizes a supersampled location
font to the three live Mamel-route ink shades.  ``solid`` is available when judging a
strictly one-bit location candidate.

Selectors 30 and 31 share the native ``Mystery Dungeon`` sequence.  The wording was
resolved directly from its nine atlas blocks after the first audition sheet was reviewed.

Example::

    python3 tools/arrival_card_audition.py --font Candidate.ttf \
        --output build/arrival_cards_candidate.png
"""

import argparse
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - exercised only without optional Pillow
    raise SystemExit(
        "arrival-card audition requires Pillow (`python3 -m pip install pillow`)"
    ) from exc

import graphics_audit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"
DEFAULT_OUTPUT = ROOT / "build" / "arrival_cards_audition.png"
DEFAULT_ASSET_OUTPUT = ROOT / "assets" / "graphics" / "arrival_cards_inter.json"
DEFAULT_FLOOR_ASSET = ROOT / "assets" / "graphics" / "arrival_floor_native.json"

CARDS = graphics_audit.ARRIVAL_LABELS
UNRESOLVED_SELECTORS = ()

SCREEN_SIZE = (160, 144)
LOCATION_BAND = (40, 56)
UNDERLINE_Y = 57
FLOOR_BAND = (73, 89)
MAXIMUM_LABEL_PIXELS = 144
BLOCK_PIXELS = 16
DEFAULT_AUDITION_F_Y_OFFSET = -1

# Exact stable colors captured from the Ancient Ruins 2F Mamel route.  The two middle
# glyph colors are inherited on other routes, so this is a useful audition palette rather
# than a claim that every dungeon uses these exact RGB values.
BACKGROUND = (0, 0, 0)
DARK_INK = (40, 40, 40)
MIDDLE_INK = (96, 96, 96)
BRIGHT_INK = (248, 248, 248)
UNDERLINE = (136, 24, 0)
PALETTE = (BACKGROUND, DARK_INK, MIDDLE_INK, BRIGHT_INK, UNDERLINE)
PIXEL_SYMBOLS = {
    BACKGROUND: ".",
    DARK_INK: "d",
    MIDDLE_INK: "m",
    BRIGHT_INK: "#",
}
SYMBOL_PIXELS = {symbol: color for color, symbol in PIXEL_SYMBOLS.items()}

NATIVE_FLOOR_SOURCE = "7F:$41E1-$44A0"
NATIVE_FLOOR_SOURCE_SHA256 = (
    "9bd2e5e4e9623a041353376842b0ea4a63d99acdf87d914bfc2a205d522bad15"
)
NATIVE_FLOOR_BANK = 0x7F
NATIVE_FLOOR_ADDRESS = 0x41E1
NATIVE_FLOOR_GLYPHS = "0123456789F"
NATIVE_FLOOR_BLOCK_BYTES = 64

SUPERSAMPLE = 8
DEFAULT_CAP_HEIGHT = 11
DEFAULT_AA_LOW = 48
DEFAULT_AA_HIGH = 160
STYLES = ("native-aa", "solid")

CELL_WIDTH = 176
CELL_HEIGHT = 168
HEADER_HEIGHT = 24
FLOOR_PROOF_HEIGHT = 104
FLOOR_PROOF_SAMPLES = (
    "1F", "2F", "3F", "4F", "5F", "6F",
    "7F", "8F", "9F", "10F", "11F", "99F",
)


class ArrivalCardAuditionError(ValueError):
    """A candidate font or requested sheet cannot satisfy the audition contract."""


@dataclass
class CandidateFace:
    path: Path
    font: object
    cap_height: int
    font_sha256: str
    _cache: dict = field(default_factory=dict)

    @property
    def name(self):
        return self.path.stem

    def mask(self, text):
        if text not in self._cache:
            self._cache[text] = _render_mask(self.font, text)
        return self._cache[text].copy()


def _font_size(font_path, cap_height):
    target = cap_height * SUPERSAMPLE
    best = None
    for size in range(6, 301):
        font = ImageFont.truetype(str(font_path), size)
        box = font.getbbox("H")
        height = box[3] - box[1]
        candidate = (abs(height - target), size)
        if best is None or candidate < best[:2]:
            best = (candidate[0], candidate[1], font)
    return best[2]


def load_font(path, cap_height=DEFAULT_CAP_HEIGHT):
    """Load a candidate outline font at the requested native-pixel cap height."""
    path = Path(path).resolve()
    if cap_height < 6 or cap_height > 15:
        raise ArrivalCardAuditionError("cap height must be between 6 and 15 pixels")
    if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
        raise ArrivalCardAuditionError("candidate must be a TTF, OTF, or TTC font")
    try:
        raw = path.read_bytes()
        font = _font_size(path, cap_height)
    except OSError as exc:
        raise ArrivalCardAuditionError("cannot load candidate font %s: %s" % (path, exc)) from exc
    return CandidateFace(
        path=path,
        font=font,
        cap_height=cap_height,
        font_sha256=sha256(raw).hexdigest(),
    )


def _render_phase(font, text, dx, dy):
    box = font.getbbox(text)
    width = max(SUPERSAMPLE, box[2] - box[0] + SUPERSAMPLE * 4)
    height = max(SUPERSAMPLE, box[3] - box[1] + SUPERSAMPLE * 4)
    high = Image.new("L", (width, height), 0)
    origin = (
        SUPERSAMPLE * 2 - box[0] + dx,
        SUPERSAMPLE * 2 - box[1] + dy,
    )
    ImageDraw.Draw(high).text(origin, text, font=font, fill=255)
    ink = high.getbbox()
    if ink is None:
        raise ArrivalCardAuditionError("candidate rendered %r as an empty mask" % text)
    left = ink[0] // SUPERSAMPLE * SUPERSAMPLE
    top = ink[1] // SUPERSAMPLE * SUPERSAMPLE
    right = math.ceil(ink[2] / SUPERSAMPLE) * SUPERSAMPLE
    bottom = math.ceil(ink[3] / SUPERSAMPLE) * SUPERSAMPLE
    high = high.crop((left, top, right, bottom))
    low = high.resize(
        (high.width // SUPERSAMPLE, high.height // SUPERSAMPLE),
        Image.Resampling.BOX,
    )
    ink = low.getbbox()
    if ink is None:
        raise ArrivalCardAuditionError("candidate rendered %r as an empty mask" % text)
    return low.crop(ink)


def _render_mask(font, text):
    """Choose the least-ambiguous 8x subpixel phase and return native coverage."""
    if not text:
        raise ArrivalCardAuditionError("arrival-card text cannot be empty")
    best = None
    for dy in range(SUPERSAMPLE):
        for dx in range(SUPERSAMPLE):
            mask = _render_phase(font, text, dx, dy)
            ambiguity = sum(min(value, 255 - value) for value in mask.getdata())
            candidate = (ambiguity, mask.width * mask.height, dy, dx, mask)
            if best is None or candidate[:4] < best[:4]:
                best = candidate
    return best[4]


def sample_floor(selector):
    """Return a representative floor string while exercising every digit shape."""
    if selector == 0:
        return None
    floors = ("1F", "2F", "9F", "10F", "19F", "50F", "99F")
    return floors[(selector - 1) % len(floors)]


def _paint_mask(screen, mask, left, top, style, aa_low, aa_high):
    if style not in STYLES:
        raise ArrivalCardAuditionError(
            "unknown style %r; expected %s" % (style, ", ".join(STYLES))
        )
    if not 0 <= aa_low < aa_high <= 255:
        raise ArrivalCardAuditionError("AA thresholds must satisfy 0 <= low < high <= 255")
    source = mask.load()
    target = screen.load()
    for y in range(mask.height):
        for x in range(mask.width):
            coverage = source[x, y]
            if not coverage:
                continue
            if style == "solid":
                if coverage >= 128:
                    target[left + x, top + y] = BRIGHT_INK
            elif coverage < aa_low:
                target[left + x, top + y] = DARK_INK
            elif coverage < aa_high:
                target[left + x, top + y] = MIDDLE_INK
            else:
                target[left + x, top + y] = BRIGHT_INK


def _centered_position(mask, band):
    top, bottom = band
    if mask.height > bottom - top:
        raise ArrivalCardAuditionError(
            "candidate raster is %d pixels high, exceeds the %d-pixel arrival-card band"
            % (mask.height, bottom - top)
        )
    return (SCREEN_SIZE[0] - mask.width) // 2, top + (bottom - top - mask.height) // 2


def _decode_native_block(raw):
    if len(raw) != NATIVE_FLOOR_BLOCK_BYTES:
        raise ArrivalCardAuditionError("native floor block must contain 64 bytes")
    image = Image.new("RGB", (BLOCK_PIXELS, BLOCK_PIXELS), BACKGROUND)
    target = image.load()
    colors = {
        0: BRIGHT_INK,
        1: MIDDLE_INK,
        2: DARK_INK,
        3: BACKGROUND,
    }
    for tile_x in range(2):
        for tile_y in range(2):
            tile = raw[(tile_x * 2 + tile_y) * 16:]
            for y in range(8):
                low, high = tile[y * 2:y * 2 + 2]
                for x in range(8):
                    bit = 7 - x
                    value = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
                    target[tile_x * 8 + x, tile_y * 8 + y] = colors[value]
    return image


def native_floor_asset(rom):
    """Decode and freeze the readable native 0-9/F blocks from a clean ROM."""
    start = NATIVE_FLOOR_BANK * 0x4000 + NATIVE_FLOOR_ADDRESS - 0x4000
    raw = bytes(rom[start:start + len(NATIVE_FLOOR_GLYPHS) * NATIVE_FLOOR_BLOCK_BYTES])
    if sha256(raw).hexdigest() != NATIVE_FLOOR_SOURCE_SHA256:
        raise ArrivalCardAuditionError("native arrival-floor source changed unexpectedly")
    return {
        "format": "shiren-gb2-native-arrival-floor-v1",
        "source": NATIVE_FLOOR_SOURCE,
        "source_sha256": NATIVE_FLOOR_SOURCE_SHA256,
        "policy": "preserve readable native Latin digits and F",
        "blocks": [
            {
                "glyph": glyph,
                "rows": _symbol_rows(
                    _decode_native_block(
                        raw[index * NATIVE_FLOOR_BLOCK_BYTES:
                            (index + 1) * NATIVE_FLOOR_BLOCK_BYTES]
                    )
                ),
            }
            for index, glyph in enumerate(NATIVE_FLOOR_GLYPHS)
        ],
    }


def load_floor_blocks(path=DEFAULT_FLOOR_ASSET):
    path = Path(path).resolve()
    try:
        asset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArrivalCardAuditionError(
            "cannot load native floor asset %s: %s" % (path, exc)
        ) from exc
    expected = {
        "format": "shiren-gb2-native-arrival-floor-v1",
        "source": NATIVE_FLOOR_SOURCE,
        "source_sha256": NATIVE_FLOOR_SOURCE_SHA256,
        "policy": "preserve readable native Latin digits and F",
    }
    if {key: asset.get(key) for key in expected} != expected:
        raise ArrivalCardAuditionError("native floor asset contract changed")
    records = asset.get("blocks")
    if not isinstance(records, list) or len(records) != len(NATIVE_FLOOR_GLYPHS):
        raise ArrivalCardAuditionError("native floor asset must define eleven blocks")
    blocks = []
    for record, glyph in zip(records, NATIVE_FLOOR_GLYPHS):
        if record.get("glyph") != glyph:
            raise ArrivalCardAuditionError("native floor block order changed")
        rows = record.get("rows")
        if (
            not isinstance(rows, list)
            or len(rows) != 16
            or any(
                not isinstance(row, str)
                or len(row) != 16
                or set(row) - set(SYMBOL_PIXELS)
                for row in rows
            )
        ):
            raise ArrivalCardAuditionError(
                "native floor block %s must contain sixteen 16-column .dm# rows"
                % glyph
            )
        block = Image.new("RGB", (16, 16), BACKGROUND)
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                block.putpixel((x, y), SYMBOL_PIXELS[symbol])
        blocks.append(block)
    return path, asset, tuple(blocks)


@lru_cache(maxsize=1)
def _default_floor_blocks():
    return load_floor_blocks()[2]


def floor_block(glyph, floor_blocks=None, f_y_offset=0):
    """Return one preserved, context-independent native digit/F block."""
    if glyph not in NATIVE_FLOOR_GLYPHS or len(glyph) != 1:
        raise ArrivalCardAuditionError("floor glyph must be one of 0-9 or F")
    if not isinstance(f_y_offset, int) or not -4 <= f_y_offset <= 4:
        raise ArrivalCardAuditionError("F y offset must be an integer from -4 through 4")
    blocks = _default_floor_blocks() if floor_blocks is None else floor_blocks
    block = blocks[NATIVE_FLOOR_GLYPHS.index(glyph)].copy()
    if glyph != "F" or f_y_offset == 0:
        return block
    shifted = Image.new("RGB", block.size, BACKGROUND)
    shifted.paste(block, (0, f_y_offset))
    return shifted


def _paint_floor(screen, floor, floor_blocks, f_y_offset=0):
    if (
        not isinstance(floor, str)
        or not floor.endswith("F")
        or not floor[:-1].isdigit()
        or not 1 <= len(floor[:-1]) <= 2
        or not 1 <= int(floor[:-1]) <= 99
    ):
        raise ArrivalCardAuditionError(
            "floor must be a decimal value from 1F through 99F"
        )
    glyphs = floor
    left = 64 if len(glyphs) == 2 else 56
    for index, glyph in enumerate(glyphs):
        screen.paste(
            floor_block(
                glyph,
                floor_blocks=floor_blocks,
                f_y_offset=f_y_offset,
            ),
            (left + index * BLOCK_PIXELS, 72),
        )
    ink = [
        x
        for x in range(left, left + len(glyphs) * BLOCK_PIXELS)
        for y in range(72, 88)
        if screen.getpixel((x, y)) != BACKGROUND
    ]
    return 0 if not ink else max(ink) - min(ink) + 1


def render_card(
    face,
    label,
    floor="1F",
    style="native-aa",
    aa_low=DEFAULT_AA_LOW,
    aa_high=DEFAULT_AA_HIGH,
    floor_blocks=None,
    floor_f_y_offset=0,
):
    """Render one native-sized candidate screen and return ``(image, metrics)``."""
    label_mask = face.mask(label)
    if label_mask.width > MAXIMUM_LABEL_PIXELS:
        raise ArrivalCardAuditionError(
            "%r is %d pixels wide and exceeds the 144-pixel arrival-card budget"
            % (label, label_mask.width)
        )
    label_left, label_top = _centered_position(label_mask, LOCATION_BAND)
    underline_width = math.ceil(label_mask.width / BLOCK_PIXELS) * BLOCK_PIXELS
    if underline_width > MAXIMUM_LABEL_PIXELS:
        raise ArrivalCardAuditionError(
            "%r needs a %d-pixel underline and exceeds the 144-pixel arrival-card budget"
            % (label, underline_width)
        )
    underline_left = (SCREEN_SIZE[0] - underline_width) // 2

    screen = Image.new("RGB", SCREEN_SIZE, BACKGROUND)
    _paint_mask(screen, label_mask, label_left, label_top, style, aa_low, aa_high)
    ImageDraw.Draw(screen).line(
        (underline_left, UNDERLINE_Y, underline_left + underline_width - 1, UNDERLINE_Y),
        fill=UNDERLINE,
    )

    floor_width = 0
    if floor is not None:
        floor_width = _paint_floor(
            screen,
            floor,
            _default_floor_blocks() if floor_blocks is None else floor_blocks,
            f_y_offset=floor_f_y_offset,
        )

    return screen, {
        "label": label,
        "label_width": label_mask.width,
        "label_height": label_mask.height,
        "label_left": label_left,
        "label_top": label_top,
        "underline_width": underline_width,
        "underline_left": underline_left,
        "underline_y": UNDERLINE_Y,
        "floor": floor,
        "floor_width": floor_width,
        "floor_f_y_offset": floor_f_y_offset,
    }


def _failure_card(message):
    screen = Image.new("RGB", SCREEN_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(screen)
    draw.rectangle((7, 39, 152, 89), outline=UNDERLINE)
    draw.text((12, 48), "OVERFLOW", fill=BRIGHT_INK)
    draw.text((12, 66), message[:23], fill=MIDDLE_INK)
    return screen


def render_floor_alignment_proof(
    floor_blocks=None,
    f_y_offset=DEFAULT_AUDITION_F_Y_OFFSET,
):
    """Render a magnified proof of representative one- and two-digit floors."""
    blocks = _default_floor_blocks() if floor_blocks is None else floor_blocks
    proof = Image.new("RGB", (CELL_WIDTH * 4, FLOOR_PROOF_HEIGHT), (24, 24, 24))
    draw = ImageDraw.Draw(proof)
    draw.text(
        (8, 5),
        "FLOOR ALIGNMENT PROOF | audition F y=%+d | ROM unchanged" % f_y_offset,
        fill=BRIGHT_INK,
    )
    panel_width = proof.width // 6
    for index, floor in enumerate(FLOOR_PROOF_SAMPLES):
        native = Image.new("RGB", SCREEN_SIZE, BACKGROUND)
        _paint_floor(native, floor, blocks, f_y_offset=f_y_offset)
        closeup = native.crop((56, 72, 104, 88)).resize(
            (96, 32),
            Image.Resampling.NEAREST,
        )
        column = index % 6
        row = index // 6
        left = column * panel_width
        top = 24 + row * 38
        draw.text((left + 3, top + 12), floor, fill=MIDDLE_INK)
        proof.paste(closeup, (left + 19, top))
    return proof


def render_sheet(
    face,
    columns=4,
    style="native-aa",
    aa_low=DEFAULT_AA_LOW,
    aa_high=DEFAULT_AA_HIGH,
    floor_blocks=None,
    floor_f_y_offset=DEFAULT_AUDITION_F_Y_OFFSET,
):
    """Render all 32 selector cells and return ``(contact_sheet, report)``."""
    if columns < 1:
        raise ArrivalCardAuditionError("columns must be positive")
    rows = math.ceil(len(CARDS) / columns)
    sheet = Image.new(
        "RGB",
        (
            CELL_WIDTH * columns,
            HEADER_HEIGHT + CELL_HEIGHT * rows + FLOOR_PROOF_HEIGHT,
        ),
        (24, 24, 24),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (8, 7),
        "%s | cap %d | %s | audition F y=%+d"
        % (face.name, face.cap_height, style, floor_f_y_offset),
        fill=BRIGHT_INK,
    )

    metrics = []
    overflowing = []
    for selector, proven_label in enumerate(CARDS):
        unresolved = selector in UNRESOLVED_SELECTORS
        audition_label = "UNRESOLVED %d" % selector if unresolved else proven_label
        floor = sample_floor(selector)
        try:
            screen, card_metrics = render_card(
                face,
                audition_label,
                floor=floor,
                style=style,
                aa_low=aa_low,
                aa_high=aa_high,
                floor_blocks=floor_blocks,
                floor_f_y_offset=floor_f_y_offset,
            )
        except ArrivalCardAuditionError as exc:
            screen = _failure_card(str(exc))
            overflowing.append(selector)
            card_metrics = {
                "label": audition_label,
                "label_width": None,
                "floor": floor,
                "error": str(exc),
            }
        card_metrics["selector"] = selector
        card_metrics["proven_label"] = None if unresolved else proven_label
        card_metrics["unresolved"] = unresolved
        metrics.append(card_metrics)

        column = selector % columns
        row = selector // columns
        cell_left = column * CELL_WIDTH
        cell_top = HEADER_HEIGHT + row * CELL_HEIGHT
        sheet.paste(screen, (cell_left + 8, cell_top))
        footer = "%02d  %s" % (selector, proven_label)
        draw.text((cell_left + 8, cell_top + 148), footer[:27], fill=MIDDLE_INK)

    proof_top = HEADER_HEIGHT + CELL_HEIGHT * rows
    sheet.paste(
        render_floor_alignment_proof(
            floor_blocks=floor_blocks,
            f_y_offset=floor_f_y_offset,
        ),
        (0, proof_top),
    )

    known_metrics = [
        item
        for item in metrics
        if not item["unresolved"] and item.get("label_width") is not None
    ]
    widest = max(known_metrics, key=lambda item: item["label_width"])
    return sheet, {
        "font": str(face.path),
        "font_sha256": face.font_sha256,
        "cap_height": face.cap_height,
        "style": style,
        "floor_f_y_offset": floor_f_y_offset,
        "cards": len(CARDS),
        "resolved_cards": len(CARDS) - len(UNRESOLVED_SELECTORS),
        "unresolved_selectors": list(UNRESOLVED_SELECTORS),
        "overflowing_selectors": overflowing,
        "widest_resolved": {
            "selector": widest["selector"],
            "label": widest["label"],
            "pixels": widest["label_width"],
        },
        "metrics": metrics,
    }


def _symbol_rows(image):
    try:
        return [
            "".join(PIXEL_SYMBOLS[image.getpixel((x, y))] for x in range(image.width))
            for y in range(image.height)
        ]
    except KeyError as exc:
        raise ArrivalCardAuditionError(
            "production raster contains a color outside the four-level glyph palette"
        ) from exc


def production_asset(face, style="native-aa", aa_low=DEFAULT_AA_LOW,
                     aa_high=DEFAULT_AA_HIGH):
    """Return the editable, block-aligned production asset for the approved face."""
    records = []
    by_label = {}
    for selector, label in enumerate(CARDS):
        if label in by_label:
            records[by_label[label]]["selectors"].append(selector)
            continue
        card, metrics = render_card(
            face,
            label,
            floor=None,
            style=style,
            aa_low=aa_low,
            aa_high=aa_high,
        )
        left = metrics["underline_left"]
        width = metrics["underline_width"]
        record = {
            "text": label,
            "selectors": [selector],
            "blocks": width // BLOCK_PIXELS,
            "rows": _symbol_rows(card.crop((left, 40, left + width, 56))),
        }
        by_label[label] = len(records)
        records.append(record)

    return {
        "format": "shiren-gb2-arrival-cards-v1",
        "content": list(CARDS),
        "font": {
            "family": "Inter",
            "style": "SemiBold",
            "version": "4.1",
            "cap_height": face.cap_height,
            "sha256": face.font_sha256,
            "license": "SIL Open Font License 1.1",
        },
        "rendering": {
            "style": style,
            "aa_low": aa_low,
            "aa_high": aa_high,
            "palette_symbols": {
                ".": list(BACKGROUND),
                "d": list(DARK_INK),
                "m": list(MIDDLE_INK),
                "#": list(BRIGHT_INK),
            },
        },
        "layout": {
            "screen_size": list(SCREEN_SIZE),
            "location_band": list(LOCATION_BAND),
            "underline_y": UNDERLINE_Y,
            "floor_band": list(FLOOR_BAND),
            "maximum_label_pixels": MAXIMUM_LABEL_PIXELS,
            "block_pixels": BLOCK_PIXELS,
        },
        "floor_art": {
            "asset": "assets/graphics/arrival_floor_native.json",
            "source": NATIVE_FLOOR_SOURCE,
            "source_sha256": NATIVE_FLOOR_SOURCE_SHA256,
            "policy": "preserve native Latin digits; raise F one pixel for optical alignment",
            "f_y_offset": DEFAULT_AUDITION_F_Y_OFFSET,
        },
        "labels": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--asset-output",
        type=Path,
        help="also freeze the approved block-aligned production JSON asset",
    )
    parser.add_argument(
        "--native-floor-rom",
        type=Path,
        help="freeze the clean ROM's native 0-9/F blocks before rendering",
    )
    parser.add_argument(
        "--floor-asset",
        type=Path,
        default=DEFAULT_FLOOR_ASSET,
    )
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cap-height", type=int, default=DEFAULT_CAP_HEIGHT)
    parser.add_argument("--style", choices=STYLES, default="native-aa")
    parser.add_argument("--aa-low", type=int, default=DEFAULT_AA_LOW)
    parser.add_argument("--aa-high", type=int, default=DEFAULT_AA_HIGH)
    args = parser.parse_args(argv)
    try:
        if args.scale < 1:
            raise ArrivalCardAuditionError("scale must be positive")
        face = load_font(args.font, args.cap_height)
        if args.native_floor_rom:
            floor_asset = native_floor_asset(args.native_floor_rom.read_bytes())
            args.floor_asset.parent.mkdir(parents=True, exist_ok=True)
            args.floor_asset.write_text(
                json.dumps(floor_asset, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        _floor_path, _floor_asset, floor_blocks = load_floor_blocks(args.floor_asset)
        sheet, report = render_sheet(
            face,
            columns=args.columns,
            style=args.style,
            aa_low=args.aa_low,
            aa_high=args.aa_high,
            floor_blocks=floor_blocks,
        )
    except (OSError, ArrivalCardAuditionError) as exc:
        parser.error(str(exc))

    if args.scale != 1:
        sheet = sheet.resize(
            (sheet.width * args.scale, sheet.height * args.scale),
            Image.Resampling.NEAREST,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    if args.asset_output:
        args.asset_output.parent.mkdir(parents=True, exist_ok=True)
        args.asset_output.write_text(
            json.dumps(
                production_asset(
                    face,
                    style=args.style,
                    aa_low=args.aa_low,
                    aa_high=args.aa_high,
                ),
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
    widest = report["widest_resolved"]
    print(
        "arrival-card audition: wrote %s (%d cards, %dx)"
        % (args.output, report["cards"], args.scale)
    )
    print(
        "font: %s cap=%d style=%s sha256=%s"
        % (face.name, face.cap_height, args.style, face.font_sha256)
    )
    print(
        "widest: selector %d %r = %d/%d pixels"
        % (
            widest["selector"],
            widest["label"],
            widest["pixels"],
            MAXIMUM_LABEL_PIXELS,
        )
    )
    print("unresolved selectors: none")
    if report["overflowing_selectors"]:
        print(
            "overflows: %s"
            % ", ".join(map(str, report["overflowing_selectors"]))
        )
    else:
        print("overflows: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
