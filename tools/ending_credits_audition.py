#!/usr/bin/env python3
"""Render a review-only English audition of GB2's main-ending credit roll.

The native cards are captured from ``SaveStates/ending-one.state`` with PyBoy and
shown beside English candidates.  Candidate text uses the exact Inter SemiBold
font, grayscale palette, and three-level coverage treatment approved for the
opening copyright/composer card.  The Japanese ``終`` mark is captured as route
evidence but deliberately excluded from replacement artwork.

This tool writes a PNG only.  It never modifies a ROM or save state.
"""

import argparse
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import io
import math
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - optional dependency failure
    raise SystemExit(
        "ending-credit audition requires Pillow (`python3 -m pip install pillow`)"
    ) from exc

import credit_screen_mockup


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM = (
    ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
)
DEFAULT_STATE = ROOT / "SaveStates" / "ending-one.state"
DEFAULT_FONT = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"
DEFAULT_OUTPUT = ROOT / "build" / "ending_credits_audition.png"

SCREEN_SIZE = (160, 144)
BLACK = credit_screen_mockup.BLACK
DARK = credit_screen_mockup.DARK
MID = credit_screen_mockup.MID
WHITE = credit_screen_mockup.WHITE
PALETTE = credit_screen_mockup.PALETTE
COVERAGE_THRESHOLDS = (
    credit_screen_mockup.LOW_COVERAGE,
    credit_screen_mockup.MID_COVERAGE,
    credit_screen_mockup.HIGH_COVERAGE,
)

ROLE_CAP_HEIGHT = 7
NAME_CAP_HEIGHT = 10
MINIMUM_CAP_HEIGHT = 5
MAXIMUM_TEXT_WIDTH = 144
LINE_BAND_HEIGHT = 16

# Midpoints of the 20 fully bright, stable cards measured from ending-one.state.
# The title card before these is intentionally not part of the staff-credit asset.
STABLE_CARD_FRAMES = (
    500,
    830,
    1140,
    1460,
    1780,
    2100,
    2400,
    2750,
    3100,
    3440,
    3780,
    4120,
    4440,
    4760,
    5070,
    5380,
    5700,
    6020,
    6350,
    6750,
)
END_MARK_FRAME = 7150
END_MARK_POLICY = "preserve Japanese"

CELL_WIDTH = 336
CELL_HEIGHT = 168
HEADER_HEIGHT = 24


class EndingCreditsAuditionError(ValueError):
    """The captured roll or requested candidate cannot satisfy its layout."""


@dataclass(frozen=True)
class Credit:
    role: str
    names: tuple
    native_role: str
    native_names: tuple
    frame: int


_CREDIT_TEXT = (
    ("Executive Producer", ("Koichi Nakamura",), "制作総指揮", ("中村 光一",)),
    ("Director", ("Seiichiro Nagahata",), "監督", ("長畑 成一郎",)),
    ("Script", ("Shin-ichiro Tomie",), "脚本", ("冨江 慎一郎",)),
    ("Original Art", ("Kaoru Hasegawa",), "原画", ("長谷川 薫",)),
    ("Music", ("Koichi Sugiyama", "Hayato Matsuo"), "音楽",
     ("すぎやま こういち", "松尾 早人")),
    ("Planning", ("Koji Maruta",), "企画", ("丸田 康司",)),
    ("Chief Programmer", ("Hidefumi Itano",), "プログラム チーフ", ("板野 英史",)),
    ("Programming",
     ("Hironori Ishigami", "Shoji Aomatsu", "Katsumi Ono", "Kenji Nemoto",
      "Eiji Kobayashi"),
     "プログラム", ("石神 宏紀", "青松 正二", "大野 克己", "根本 賢二", "小林 永司")),
    ("Programming",
     ("Nobuo Morioka", "Takanori Nakamura", "Hideaki Miyamoto",
      "Masahiro Yanagisawa"),
     "プログラム", ("森岡 伸夫", "中村 隆徳", "宮本 英明", "柳沢 昌宏")),
    ("Art Chief", ("Fuyuhiko Koizumi",), "美術 チーフ", ("小泉 冬彦",)),
    ("Art", ("Shinji Sasaki", "Migaku Matsui", "Yuko Nakagawa", "Naoki Kunimoto"),
     "美術", ("佐々木 真治", "松井 磨", "中川 祐子", "国本 直樹")),
    ("Music Production Chief", ("Kojiro Nakashima",), "音楽制作チーフ", ("中嶋 康二郎",)),
    ("Music Production", ("Chiyoko Mitsumata",), "音楽制作", ("三俣 千代子",)),
    ("Script Assistance", ("Hirotaka Inaba", "Emiko Tanaka"), "脚本協力",
     ("稲葉 洋敬", "田中 絵美子")),
    ("Development Support", ("Shinya Yamada",), "開発推進", ("山田 信哉",)),
    ("Public Relations", ("Peace Entertainment", "Keisuke Yamamoto",
                           "Hidetoshi Miyashita"),
     "広報", ("(有)ピースエンターテインメント", "山本 啓介", "宮下 秀俊")),
    ("Special Thanks", ("Yasuhiro Nagata",), "協力", ("永田 泰大",)),
    ("Special Thanks", ("Stingray Co., Ltd.",), "協力", ("(株)スティングレイ",)),
    ("Special Thanks", ("Kazuhiko Nakanishi", "Yukio Nishihata", "Kosuke Awata"),
     "協力", ("中西 一彦", "西畑 幸雄", "粟田 浩介")),
    ("Production & Copyright", ("CHUNSOFT",), "制作・著作", ("(株)チュンソフト",)),
)

CREDITS = tuple(
    Credit(role, names, native_role, native_names, frame)
    for (role, names, native_role, native_names), frame
    in zip(_CREDIT_TEXT, STABLE_CARD_FRAMES)
)


@dataclass(frozen=True)
class CandidateFace:
    path: Path
    name: str
    sha256: str


def load_font(path=DEFAULT_FONT):
    """Validate a candidate outline font and retain its reproducible identity."""
    path = Path(path).resolve()
    if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
        raise EndingCreditsAuditionError("candidate must be a TTF, OTF, or TTC font")
    try:
        raw = path.read_bytes()
        family, style = ImageFont.truetype(str(path), 24).getname()
    except OSError as exc:
        raise EndingCreditsAuditionError("cannot load candidate font %s: %s" % (path, exc)) from exc
    return CandidateFace(path, ("%s %s" % (family, style)).strip(), sha256(raw).hexdigest())


@lru_cache(maxsize=None)
def _level_masks(face, text, cap_height):
    coverage = _coverage(face, text, cap_height)
    low, middle, high = COVERAGE_THRESHOLDS
    crop_box = coverage.point(
        lambda value: 255 if value >= low else 0,
        mode="1",
    ).getbbox()
    if crop_box is None:
        raise EndingCreditsAuditionError("cannot render an empty ending-credit line")
    coverage = coverage.crop(crop_box)
    return (
        coverage.point(lambda value: 255 if low <= value < middle else 0, mode="1"),
        coverage.point(lambda value: 255 if middle <= value < high else 0, mode="1"),
        coverage.point(lambda value: 255 if value >= high else 0, mode="1"),
    )


@lru_cache(maxsize=None)
def _coverage(face, text, cap_height):
    """Apply the opening-card phase selection on a tightly bounded canvas."""
    supersample = credit_screen_mockup.SUPERSAMPLE
    font = ImageFont.truetype(
        str(face.path),
        credit_screen_mockup._font_size(str(face.path), cap_height),
    )
    advance = sum(font.getlength(character) for character in text)
    padding = 8 * supersample
    width = max(supersample, math.ceil(advance) + padding * 2 + font.size)
    height = max(supersample, font.size * 3 + padding * 2)
    best = None
    for dy in range(supersample):
        for dx in range(supersample):
            high = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(high)
            x = float(padding + dx)
            for character in text:
                draw.text((x, padding + dy), character, 255, font=font)
                x += font.getlength(character)
            box = high.getbbox()
            if box is None:
                raise EndingCreditsAuditionError("cannot render an empty ending-credit line")
            high = high.crop(
                (
                    box[0] - 4 * supersample,
                    box[1] - 4 * supersample,
                    box[2] + 4 * supersample,
                    box[3] + 4 * supersample,
                )
            )
            box = high.getbbox()
            left = box[0] // supersample * supersample
            top = box[1] // supersample * supersample
            right = math.ceil(box[2] / supersample) * supersample
            bottom = math.ceil(box[3] / supersample) * supersample
            high = high.crop((left, top, right, bottom))
            low = high.resize(
                (high.width // supersample, high.height // supersample),
                Image.Resampling.BOX,
            )
            score = sum(min(value, 255 - value) for value in low.getdata())
            if best is None or score < best[0]:
                best = score, low
    return best[1]


def _fitting_masks(face, text, preferred_cap_height):
    for cap_height in range(preferred_cap_height, MINIMUM_CAP_HEIGHT - 1, -1):
        masks = _level_masks(face, text, cap_height)
        if masks[0].width <= MAXIMUM_TEXT_WIDTH and masks[0].height <= LINE_BAND_HEIGHT:
            return masks, cap_height
    raise EndingCreditsAuditionError(
        "%r cannot fit the %d-pixel ending-credit width" % (text, MAXIMUM_TEXT_WIDTH)
    )


def _row_tops(count):
    """Return native-derived 16-pixel row bands for a card's line count."""
    layouts = {
        2: (42, 63),
        3: (34, 55, 75),
        4: (22, 43, 63, 83),
        5: (11, 31, 51, 71, 92),
        6: (11, 31, 51, 71, 91, 111),
    }
    try:
        return layouts[count]
    except KeyError as exc:
        raise EndingCreditsAuditionError(
            "ending-credit cards support two through six lines, got %d" % count
        ) from exc


def _paste_mask(screen, mask, xy, color):
    ink = Image.new("RGB", mask.size, color)
    screen.paste(ink, xy, mask)


def render_card(face, credit):
    """Render one native-sized English card and return its fit metrics."""
    lines = (credit.role,) + tuple(credit.names)
    tops = _row_tops(len(lines))
    screen = Image.new("RGB", SCREEN_SIZE, BLACK)
    metrics = []
    overflows = []
    for index, (text, band_top) in enumerate(zip(lines, tops)):
        preferred = ROLE_CAP_HEIGHT if index == 0 else NAME_CAP_HEIGHT
        masks, cap_height = _fitting_masks(face, text, preferred)
        width, height = masks[0].size
        left = (SCREEN_SIZE[0] - width) // 2
        top = band_top + (LINE_BAND_HEIGHT - height) // 2
        if left < 8 or left + width > 152:
            overflows.append(index)
        for mask, color in zip(masks, (DARK, MID, WHITE)):
            _paste_mask(screen, mask, (left, top), color)
        metrics.append(
            {
                "text": text,
                "width": width,
                "height": height,
                "left": left,
                "top": top,
                "cap_height": cap_height,
            }
        )

    points = [
        (x, y)
        for y in range(SCREEN_SIZE[1])
        for x in range(SCREEN_SIZE[0])
        if screen.getpixel((x, y)) != BLACK
    ]
    xs, ys = zip(*points)
    return screen, {
        "role": credit.role,
        "frame": credit.frame,
        "lines": metrics,
        "overflows": overflows,
        "ink_bounds": (min(xs), min(ys), max(xs), max(ys)),
    }


def capture_native_roll(rom_path, state_path, pyboy_class):
    """Capture every stable Japanese card and the accepted native end mark."""
    rom_path = Path(rom_path)
    state_path = Path(state_path)
    if not rom_path.is_file():
        raise EndingCreditsAuditionError("missing ending-credit ROM: %s" % rom_path)
    if not state_path.is_file():
        raise EndingCreditsAuditionError("missing ending-credit state: %s" % state_path)

    wanted = set(STABLE_CARD_FRAMES) | {END_MARK_FRAME}
    frames = {}
    pyboy = pyboy_class(
        str(rom_path),
        window="null",
        sound_emulated=False,
        ram_file=io.BytesIO(bytes(0x8000)),
    )
    pyboy.set_emulation_speed(0)
    try:
        with state_path.open("rb") as handle:
            pyboy.load_state(handle)
        for frame in range(max(wanted) + 1):
            pyboy.tick()
            if frame in wanted:
                image = pyboy.screen.image.convert("RGB").copy()
                if image.size != SCREEN_SIZE:
                    raise EndingCreditsAuditionError(
                        "ending frame is %r, expected %r" % (image.size, SCREEN_SIZE)
                    )
                frames[frame] = image
    finally:
        pyboy.stop(save=False)

    missing = sorted(wanted - set(frames))
    if missing:
        raise EndingCreditsAuditionError("failed to capture ending frames: %s" % missing)
    return tuple(frames[frame] for frame in STABLE_CARD_FRAMES), frames[END_MARK_FRAME]


def _failure_card(message):
    screen = Image.new("RGB", SCREEN_SIZE, BLACK)
    draw = ImageDraw.Draw(screen)
    draw.rectangle((7, 7, 152, 136), outline=MID)
    draw.text((12, 52), "OVERFLOW", fill=WHITE)
    draw.text((12, 70), message[:23], fill=MID)
    return screen


def render_sheet(face, native_cards=None, columns=2):
    """Render all cards, optionally paired with their captured Japanese originals."""
    if columns < 1:
        raise EndingCreditsAuditionError("columns must be positive")
    if native_cards is not None and len(native_cards) != len(CREDITS):
        raise EndingCreditsAuditionError(
            "native reference has %d cards, expected %d" % (len(native_cards), len(CREDITS))
        )

    rows = math.ceil(len(CREDITS) / columns)
    sheet = Image.new(
        "RGB",
        (CELL_WIDTH * columns, HEADER_HEIGHT + CELL_HEIGHT * rows),
        (24, 24, 24),
    )
    draw = ImageDraw.Draw(sheet)
    heading = "%s | opening copyright treatment | %s" % (
        face.name,
        "Japanese / English" if native_cards is not None else "English candidates",
    )
    draw.text((8, 6), heading, fill=WHITE)

    metrics = []
    overflowing = []
    for index, credit in enumerate(CREDITS):
        try:
            candidate, card_metrics = render_card(face, credit)
        except EndingCreditsAuditionError as exc:
            candidate = _failure_card(str(exc))
            card_metrics = {"role": credit.role, "frame": credit.frame,
                            "error": str(exc), "overflows": [0]}
            overflowing.append(index)
        if card_metrics.get("overflows"):
            overflowing.append(index)
        card_metrics["index"] = index
        metrics.append(card_metrics)

        column = index % columns
        row = index // columns
        left = column * CELL_WIDTH
        top = HEADER_HEIGHT + row * CELL_HEIGHT
        if native_cards is None:
            sheet.paste(candidate, (left + 88, top))
        else:
            sheet.paste(native_cards[index], (left + 4, top))
            sheet.paste(candidate, (left + 172, top))
        footer = "%02d  %s" % (index + 1, credit.role)
        draw.text((left + 8, top + 148), footer[:48], fill=MID)

    return sheet, {
        "cards": len(CREDITS),
        "font": str(face.path),
        "font_name": face.name,
        "font_sha256": face.sha256,
        "palette": [list(color) for color in PALETTE],
        "coverage_thresholds": list(COVERAGE_THRESHOLDS),
        "native_reference": native_cards is not None,
        "ending_mark": END_MARK_POLICY,
        "overflowing_cards": sorted(set(overflowing)),
        "metrics": metrics,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument(
        "--candidate-only",
        action="store_true",
        help="skip PyBoy capture and render English candidates without Japanese references",
    )
    args = parser.parse_args(argv)

    try:
        if args.scale < 1:
            raise EndingCreditsAuditionError("scale must be positive")
        face = load_font(args.font)
        native = None
        if not args.candidate_only:
            from capture_dialogue import _pyboy_class

            native, _end_mark = capture_native_roll(args.rom, args.state, _pyboy_class())
        sheet, report = render_sheet(face, native_cards=native, columns=args.columns)
        if report["overflowing_cards"]:
            raise EndingCreditsAuditionError(
                "ending-credit cards overflow: %s"
                % ", ".join(str(index + 1) for index in report["overflowing_cards"])
            )
    except (OSError, EndingCreditsAuditionError, RuntimeError) as exc:
        parser.error(str(exc))

    if args.scale != 1:
        sheet = sheet.resize(
            (sheet.width * args.scale, sheet.height * args.scale),
            Image.Resampling.NEAREST,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(
        "ending-credit audition: wrote %s (%d cards, %dx, %s)"
        % (
            args.output,
            report["cards"],
            args.scale,
            "candidate only" if args.candidate_only else "native comparison",
        )
    )
    print(
        "font: %s sha256=%s | palette/coverage: opening copyright card"
        % (face.name, face.sha256)
    )
    print("overflows: none | end mark: %s" % END_MARK_POLICY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
