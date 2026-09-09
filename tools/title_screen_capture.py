#!/usr/bin/env python3
"""Capture and verify the installed title directly from a production ROM."""

import argparse
import base64
from hashlib import sha1, sha256
import json
from pathlib import Path
import tempfile

from PIL import Image

import capture_dialogue
import cartridge
import title_graphics
from title_localization_audition import sprite_pixels


ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FPS = 4194304 / 70224


def capture(rom_path, reference_path, output):
    from pyboy import PyBoy

    source = reference_path.read_bytes()
    if sha1(source).hexdigest() != capture_dialogue.ROM_SHA1:
        raise ValueError("reference must be the matching original Japanese ROM")
    rom = rom_path.read_bytes()
    cartridge.verify_checksums(rom)
    expected = {
        (moon, shine): title_graphics.compose(source, moon, shine, gradient=True)
        for moon in range(4)
        for shine in range(-1, 8)
    }
    start = title_graphics.offset(49, 0x4000) + 2 + 0x300
    bat_tiles = source[start : start + 0x800]
    frames, clocks, phases, bats = [], [], [], []
    transition = []
    with tempfile.TemporaryDirectory(prefix="shiren-title-capture-") as directory:
        temporary = Path(directory) / "capture.gbc"
        temporary.write_bytes(rom)
        owner = PyBoy(str(temporary), window="null", sound_emulated=False)
        owner.set_emulation_speed(0)
        try:
            owner.tick(600)
            for frame in range(480):
                clock, moon = owner.memory[0xC880], owner.memory[0xC881]
                shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
                records = tuple(
                    tuple(owner.memory[0xFE00 + i * 4 : 0xFE04 + i * 4])
                    for i in range(3)
                )
                image = expected[moon, shine].copy()
                for record in records:
                    if record[0]:
                        for x, y in sprite_pixels(bat_tiles, record):
                            if not (0 <= x < 160 and 0 <= y < 144):
                                raise ValueError("bat pixel is outside the screen")
                            image.putpixel((x, y), (8, 8, 8))
                owner.tick()
                actual = owner.screen.image.convert("RGB")
                if actual.tobytes() != image.tobytes():
                    raise ValueError("production title differs at frame %d" % frame)
                frames.append(actual.copy())
                clocks.append(clock)
                phases.append((moon, shine))
                bats.append(records)
            if any(b != (a + 1) % 240 for a, b in zip(clocks, clocks[1:])):
                raise ValueError("sparkle clock skipped a native frame")
            if any(phases[i] != phases[i % 240] for i in range(480)):
                raise ValueError("moon and sparkle did not repeat after 240 frames")
            if any(bats[i] != bats[i % 96] for i in range(480)):
                raise ValueError("bat cycle is not 96 native frames")
            changes = [i for i in range(1, 480) if phases[i][0] != phases[i - 1][0]]
            if any(b - a != 6 for a, b in zip(changes, changes[1:])):
                raise ValueError("moon phase is not six native frames")
            if any(sum(s == phase for _, s in phases) != 20 for phase in range(8)):
                raise ValueError("sparkle phases did not each last ten native frames")
            owner.button("start", 5)
            for frame in range(120):
                active = owner.memory[0xC3B4] == 0x9D and owner.memory[0xC0E5] == 9
                if active:
                    clock, moon, step = (
                        owner.memory[a] for a in (0xC880, 0xC881, 0xC887)
                    )
                    shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
                    image = expected[moon, shine].copy()
                    for i in range(3):
                        record = tuple(owner.memory[0xFE00 + i * 4 : 0xFE04 + i * 4])
                        if record[0]:
                            for x, y in sprite_pixels(bat_tiles, record):
                                image.putpixel((x, y), (8, 8, 8))
                    image = image.point(
                        [
                            min(248, v + ((31 - v // 8) * step // 32) * 8)
                            for v in range(256)
                        ]
                        * 3
                    )
                owner.tick()
                if active and owner.memory[0xFF40] & 0x80:
                    actual = owner.screen.image.convert("RGB")
                    if actual.tobytes() != image.tobytes():
                        raise ValueError(
                            "production Start transition differs at frame %d" % frame
                        )
                    transition.append((frame, step, actual.copy()))
            if {step for _, step, _ in transition} != {0, 2, 10, 18, 26, 32}:
                raise ValueError("production transition did not show every fade level")
            if owner.memory[0xC0E5] != 7:
                raise ValueError("Start did not reach the native menu")
            menu = owner.screen.image.convert("RGB").copy()
        finally:
            owner.stop(save=False)

    output.mkdir(parents=True, exist_ok=True)
    frames[0].save(output / "title-screen.png")
    menu.save(output / "start-menu.png")
    for frame, step, actual in transition:
        actual.save(output / ("transition-%03d.png" % frame))
    colors = sorted({color for frame in frames for color in frame.getdata()})
    if len(colors) > 256:
        raise ValueError("GIF cannot preserve all title colors")
    palette = Image.new("P", (1, 1))
    palette.putpalette(
        [channel for color in colors for channel in color]
        + [0] * (768 - len(colors) * 3)
    )
    indexed = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames
    ]
    if any(a.tobytes() != b.convert("RGB").tobytes() for a, b in zip(frames, indexed)):
        raise ValueError("GIF palette changed title pixels")
    durations = [
        10 * (round((i + 1) * 100 / FPS) - round(i * 100 / FPS)) for i in range(480)
    ]
    indexed[0].save(
        output / "title-screen.gif",
        save_all=True,
        append_images=indexed[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=1,
    )
    # Pillow can combine identical adjacent frames. Check the encoded timeline.
    with Image.open(output / "title-screen.gif") as encoded:
        reference_index = 0
        for i in range(encoded.n_frames):
            encoded.seek(i)
            pixels = encoded.convert("RGB").tobytes()
            remaining = encoded.info["duration"]
            while remaining:
                if pixels != frames[reference_index].tobytes():
                    raise ValueError("encoded GIF changed frame pixels")
                remaining -= durations[reference_index]
                reference_index += 1
                if remaining < 0:
                    raise ValueError("encoded GIF changed frame timing")
        if reference_index != 480:
            raise ValueError("encoded GIF dropped frames")
    manifest = {
        "rom": rom_path.name,
        "rom_sha256": sha256(rom).hexdigest(),
        "reference_sha1": sha1(source).hexdigest(),
        "verified_frames": 480,
        "native_fps": FPS,
        "moon_phase_frames": 6,
        "bat_cycle_frames": 96,
        "sparkle_phase_frames": 10,
        "sparkle_cycle_frames": 240,
        "gif_duration_ms": sum(durations),
        "start_menu_handoff": "passed",
        "verified_transition_frames": len(transition),
        "fade_levels": sorted({step for _, step, _ in transition}),
        "pixel_comparison": "exact after native RGB555 normalization",
        "capture": "PyBoy cold boot; temporary ROM; saving disabled",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    gif = base64.b64encode((output / "title-screen.gif").read_bytes()).decode("ascii")
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Shiren GB2 — installed title</title><style>"
        "body{margin:40px auto;padding:0 20px;max-width:760px;background:#10131b;"
        "color:#e5e7ed;font:17px/1.6 system-ui}h1{font-size:26px}"
        "img{display:block;width:480px;max-width:100%;image-rendering:pixelated;"
        "border:1px solid #454b5c}code{overflow-wrap:anywhere;font-size:12px}"
        "</style><h1>Shiren GB2 — installed title</h1>"
        "<p>Captured directly from the English ROM. The full loop includes two "
        "subtitle sparkle sweeps, with the original moon and bat animation.</p>"
        '<img alt="Localized title running in the game" src="data:image/gif;base64,'
        + gif
        + '"><p>480 frames matched the approved composition pixel for pixel. '
        "Start reaches the game menu.</p><p>ROM SHA-256<br><code>"
        + manifest["rom_sha256"]
        + "</code></p></html>\n"
    )
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument("--output", type=Path, default=ROOT / "build/title-screen")
    args = parser.parse_args(argv)
    print(json.dumps(capture(args.rom, args.reference, args.output), indent=2))


if __name__ == "__main__":
    main()
