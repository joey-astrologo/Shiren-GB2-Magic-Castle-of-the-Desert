#!/usr/bin/env python3
"""Build a self-contained canvas audition from supplied title art and native motion.

This captures an unmodified ROM with PyBoy and embeds the supplied PNGs verbatim.
The browser composes the preview. No ROM, save, source artwork, or build installer
is modified. Open build/title-localization-audition/index.html after running.
"""

import argparse
import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/graphics/GB2 Title Graphics"
OUTPUT = ROOT / "build/title-localization-audition"
FIRST_FRAME = 600
FRAME_COUNT = 480
BAT_RAISE = 12
GB_FPS = 4194304 / 70224


def image_uri(path):
    mime = "image/gif" if path.suffix == ".gif" else "image/png"
    return "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode())


def sprite_pixels(vram, sprite):
    """Decode one native 8x16 sprite into opaque screen coordinates."""
    y, x, tile, attributes = sprite
    for row in range(16):
        source_row = 15 - row if attributes & 0x40 else row
        offset = (tile & 0xFE) * 16 + source_row * 2
        low, high = vram[offset:offset + 2]
        for column in range(8):
            bit = column if attributes & 0x20 else 7 - column
            color = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
            if color:
                yield x - 8 + column, y - 16 + row


def background_color(pyboy, x, y, palettes):
    """Read the BG below the small bat; this band is below the sky raster ramp."""
    map_address = 0x9800 + (y // 8) * 32 + x // 8
    tile = pyboy.memory[0, map_address]
    attributes = pyboy.memory[1, map_address]
    tile = (tile ^ 0x80) + 128  # Native title uses signed $8800 tile addressing.
    row = 7 - y % 8 if attributes & 0x40 else y % 8
    bit = x % 8 if attributes & 0x20 else 7 - x % 8
    bank = (attributes >> 3) & 1
    address = 0x8000 + tile * 16 + row * 2
    low, high = pyboy.memory[bank, address:address + 2]
    color = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
    offset = (attributes & 7) * 8 + color * 2
    packed = palettes[offset] | (palettes[offset + 1] << 8)
    return [(packed & 31) * 8, ((packed >> 5) & 31) * 8, ((packed >> 10) & 31) * 8]


def capture_motion(rom):
    from pyboy import PyBoy

    pyboy = PyBoy(str(rom), window="null", sound_emulated=False)
    pyboy.set_emulation_speed(0)
    images, image_ids, frames = [], {}, []
    try:
        for frame in range(1, FIRST_FRAME + FRAME_COUNT):
            if frame < FIRST_FRAME:
                pyboy.tick()
                continue
            if pyboy.memory[0xFF40] != 0xE7 or any(pyboy.memory[a] for a in (0xFF42, 0xFF43)):
                raise ValueError("Unexpected native title display state")
            # The OAM seen after tick belongs to the next rendered frame. Read
            # its sprite and BG first, then capture the frame that uses them.
            oam = list(pyboy.memory[0xFE00:0xFEA0])
            sprites = list(dict.fromkeys(tuple(oam[i:i + 4]) for i in range(0, 160, 4)))
            small = [s for s in sprites if s[0] == 45 and s[3] == 0 and 0x54 <= s[2] <= 0x72]
            if len(small) != 1:
                raise ValueError("Could not identify the native moon-side bat")
            vram = bytes(pyboy.memory[0, 0x8000:0x9800])
            coords = list(sprite_pixels(vram, small[0]))
            # Read the palette index register without changing future execution.
            old_index = pyboy.memory[0xFF68]
            palettes = []
            for index in range(64):
                pyboy.memory[0xFF68] = index
                palettes.append(pyboy.memory[0xFF69])
            pyboy.memory[0xFF68] = old_index
            bat = []
            for x, y in coords:
                bat.append([x, y - 1, background_color(pyboy, x, y, palettes)])
            pyboy.tick()
            capture = pyboy.screen.image.convert("RGB")
            for x, y in coords:
                if capture.getpixel((x, y)) != (8, 8, 8):
                    raise ValueError("Native bat ink no longer matches the traced sprite")
            stream = BytesIO()
            capture.save(stream, format="PNG")
            png = stream.getvalue()
            key = sha256(png).hexdigest()
            if key not in image_ids:
                image_ids[key] = len(images)
                images.append("data:image/png;base64," + base64.b64encode(png).decode())
            frames.append({"image": image_ids[key], "bat": bat})
    finally:
        pyboy.stop(save=False)
    return images, frames


def build(rom, output):
    files = {
        "scene": "2 English title static with mask/2.GB2TitleStaticExample.png",
        "title": "2 English title static with mask/1b.GB2TitleStaticTransparent.png",
        "subtitle": "3 English subtitle animation components/1b.GB2TitleSubtitleTransparent.png",
        "reference": "GB2TitleDraft.gif",
    }
    for index in range(8):
        files["shine%d" % index] = (
            "4 English subtitle precomposed 8 frames/GB2TitleExampleFrame%d.png" % (index + 1)
        )
    for name, relative in files.items():
        with Image.open(ART / relative) as image:
            expected = (480, 429) if name == "reference" else (160, 143)
            if image.size != expected:
                raise ValueError("Unexpected source dimensions: %s" % relative)
    native_images, frames = capture_motion(rom)
    data = {
        "images": {name: image_uri(ART / relative) for name, relative in files.items()},
        "nativeImages": native_images,
        "frames": frames,
        "fps": GB_FPS,
        "batRaise": BAT_RAISE,
        "firstFrame": FIRST_FRAME,
    }
    template = Path(__file__).with_suffix(".html").read_text()
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(template.replace("/* AUDITION_DATA */ null", json.dumps(data)))
    manifest = {
        "status": "visual audition only; insertion awaits approval",
        "rom_sha256": sha256(rom.read_bytes()).hexdigest(),
        "sources": {relative: sha256((ART / relative).read_bytes()).hexdigest() for relative in files.values()},
        "native_frames": [FIRST_FRAME, FIRST_FRAME + FRAME_COUNT - 1],
        "native_fps": GB_FPS,
        "canvas": [160, 144],
        "source_alignment": "Artwork omits native row 0; retain artwork coordinates, extend bottom sand one row",
        "moon_side_bat_offset": [0, -BAT_RAISE],
        "sparkle": {"phase_frames": 10, "phases": 8, "cycle_frames": 240, "initial_hold_frames": 60},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Audition: %s" % (output / "index.html"))
    print("Captured %d native frames; source ROM and artwork unchanged." % len(frames))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.rom.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
