#!/usr/bin/env python3
"""Capture one dense, frame-complete pass of the animated title-screen flash.

The default schedule captures every emulated frame from 600 through 659.  It writes both
a labeled contact sheet for pixel-art reference and a nearest-neighbor animated GIF.  This
is a read-only capture utility: it never modifies the source ROM.

Example::

    python3 tools/title_animation_vignette.py
"""

import argparse
import math
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - only exercised without Pillow
    raise SystemExit(
        "title-animation vignette requires Pillow (`python3 -m pip install pillow`)"
    ) from exc

import capture_dialogue


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM = ROOT / "build" / "shiren-gb2-english.gbc"
DEFAULT_SHEET_OUTPUT = ROOT / "build" / "title-screen-text-flash-frames.png"
DEFAULT_GIF_OUTPUT = ROOT / "build" / "title-screen-text-flash.gif"

DEFAULT_FIRST_FRAME = 600
DEFAULT_LAST_FRAME = 659
DEFAULT_FRAME_STEP = 1
DEFAULT_COLUMNS = 8
DEFAULT_SHEET_SCALE = 2
DEFAULT_GIF_SCALE = 4
DEFAULT_GIF_FPS = 60

SCREEN_SIZE = (160, 144)
LABEL_HEIGHT = 8
SHEET_BACKGROUND = (0, 0, 0)
LABEL_INK = (240, 240, 240)


class TitleAnimationVignetteError(ValueError):
    """The requested title-animation capture cannot be produced safely."""


def frame_schedule(first_frame, last_frame, frame_step=DEFAULT_FRAME_STEP):
    """Return the inclusive emulator-frame schedule for one capture."""
    if not all(isinstance(value, int) for value in (first_frame, last_frame, frame_step)):
        raise TitleAnimationVignetteError("frame values must be integers")
    if first_frame < 1:
        raise TitleAnimationVignetteError("first frame must be positive")
    if last_frame < first_frame:
        raise TitleAnimationVignetteError("last frame cannot precede first frame")
    if frame_step < 1:
        raise TitleAnimationVignetteError("frame step must be positive")
    return tuple(range(first_frame, last_frame + 1, frame_step))


def capture_frames(rom_path, schedule, pyboy_class=None):
    """Boot ``rom_path`` and capture each requested native 160x144 frame."""
    rom_path = Path(rom_path).resolve()
    if not rom_path.is_file():
        raise TitleAnimationVignetteError("ROM does not exist: %s" % rom_path)
    schedule = tuple(schedule)
    if not schedule:
        raise TitleAnimationVignetteError("capture schedule cannot be empty")
    if tuple(sorted(set(schedule))) != schedule:
        raise TitleAnimationVignetteError("capture schedule must be strictly increasing")

    PyBoy = capture_dialogue._pyboy_class() if pyboy_class is None else pyboy_class
    pyboy = PyBoy(str(rom_path), window="null", sound_emulated=False)
    captured = []
    wanted = set(schedule)
    try:
        for frame_number in range(1, schedule[-1] + 1):
            pyboy.tick()
            if frame_number in wanted:
                image = pyboy.screen.image.convert("RGB").copy()
                if image.size != SCREEN_SIZE:
                    raise TitleAnimationVignetteError(
                        "emulator returned %r instead of a 160x144 frame" % (image.size,)
                    )
                captured.append((frame_number, image))
    finally:
        pyboy.stop()
    if tuple(number for number, _image in captured) != schedule:
        raise TitleAnimationVignetteError("emulator did not produce the full schedule")
    return captured


def compose_contact_sheet(frames, columns=DEFAULT_COLUMNS, scale=DEFAULT_SHEET_SCALE):
    """Compose labeled frames without dropping or resampling source pixels."""
    frames = list(frames)
    if not frames:
        raise TitleAnimationVignetteError("contact sheet needs at least one frame")
    if not isinstance(columns, int) or columns < 1:
        raise TitleAnimationVignetteError("columns must be a positive integer")
    if not isinstance(scale, int) or scale < 1:
        raise TitleAnimationVignetteError("sheet scale must be a positive integer")
    for _number, image in frames:
        if image.mode != "RGB" or image.size != SCREEN_SIZE:
            raise TitleAnimationVignetteError(
                "contact-sheet frames must be 160x144 RGB images"
            )

    rows = math.ceil(len(frames) / columns)
    native = Image.new(
        "RGB",
        (SCREEN_SIZE[0] * columns, (LABEL_HEIGHT + SCREEN_SIZE[1]) * rows),
        SHEET_BACKGROUND,
    )
    draw = ImageDraw.Draw(native)
    for index, (frame_number, image) in enumerate(frames):
        column = index % columns
        row = index // columns
        left = column * SCREEN_SIZE[0]
        top = row * (LABEL_HEIGHT + SCREEN_SIZE[1])
        draw.text((left + 2, top), "frame %d" % frame_number, fill=LABEL_INK)
        native.paste(image, (left, top + LABEL_HEIGHT))
    if scale == 1:
        return native
    return native.resize(
        (native.width * scale, native.height * scale),
        Image.Resampling.NEAREST,
    )


def write_gif(
    frames,
    output_path,
    scale=DEFAULT_GIF_SCALE,
    fps=DEFAULT_GIF_FPS,
):
    """Write an animated nearest-neighbor GIF from all captured frames."""
    frames = list(frames)
    if not frames:
        raise TitleAnimationVignetteError("animated GIF needs at least one frame")
    if not isinstance(scale, int) or scale < 1:
        raise TitleAnimationVignetteError("GIF scale must be a positive integer")
    if not isinstance(fps, int) or not 1 <= fps <= 100:
        raise TitleAnimationVignetteError("GIF fps must be an integer from 1 through 100")
    images = []
    for _number, image in frames:
        if image.mode != "RGB" or image.size != SCREEN_SIZE:
            raise TitleAnimationVignetteError("GIF frames must be 160x144 RGB images")
        images.append(
            image.resize(
                (SCREEN_SIZE[0] * scale, SCREEN_SIZE[1] * scale),
                Image.Resampling.NEAREST,
            )
        )
    # GIF delays are whole centiseconds.  Quantize cumulative time rather than
    # rounding each 60 Hz frame to 10 ms, which would shorten a one-second cycle
    # to 0.6 seconds.  At 60 fps this produces a repeating 20/10/20 ms cadence.
    durations = []
    previous_centiseconds = 0
    for frame_index in range(1, len(images) + 1):
        elapsed_centiseconds = round(frame_index * 100 / fps)
        durations.append((elapsed_centiseconds - previous_centiseconds) * 10)
        previous_centiseconds = elapsed_centiseconds
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--sheet-output", type=Path, default=DEFAULT_SHEET_OUTPUT)
    parser.add_argument("--gif-output", type=Path, default=DEFAULT_GIF_OUTPUT)
    parser.add_argument("--first-frame", type=int, default=DEFAULT_FIRST_FRAME)
    parser.add_argument("--last-frame", type=int, default=DEFAULT_LAST_FRAME)
    parser.add_argument("--frame-step", type=int, default=DEFAULT_FRAME_STEP)
    parser.add_argument("--columns", type=int, default=DEFAULT_COLUMNS)
    parser.add_argument("--sheet-scale", type=int, default=DEFAULT_SHEET_SCALE)
    parser.add_argument("--gif-scale", type=int, default=DEFAULT_GIF_SCALE)
    parser.add_argument("--gif-fps", type=int, default=DEFAULT_GIF_FPS)
    args = parser.parse_args(argv)

    try:
        schedule = frame_schedule(args.first_frame, args.last_frame, args.frame_step)
        frames = capture_frames(args.rom, schedule)
        sheet = compose_contact_sheet(
            frames,
            columns=args.columns,
            scale=args.sheet_scale,
        )
        args.sheet_output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.sheet_output)
        write_gif(
            frames,
            args.gif_output,
            scale=args.gif_scale,
            fps=args.gif_fps,
        )
    except (OSError, TitleAnimationVignetteError) as exc:
        parser.error(str(exc))

    print(
        "title-animation vignette: captured %d/%d emulator frames (%d-%d, step %d)"
        % (
            len(frames),
            args.last_frame - args.first_frame + 1,
            args.first_frame,
            args.last_frame,
            args.frame_step,
        )
    )
    print("contact sheet: %s" % args.sheet_output)
    print("animated GIF: %s" % args.gif_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
