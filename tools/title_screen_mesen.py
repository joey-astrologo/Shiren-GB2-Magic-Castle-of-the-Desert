#!/usr/bin/env python3
"""Verify title pixels and natural menu/attract transitions in an isolated Mesen."""

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image

import capture_dialogue
import cartridge
import title_graphics
from title_localization_audition import sprite_pixels


ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


def verify(executable, rom_path, reference_path, output):
    original = reference_path.read_bytes()
    if sha1(original).hexdigest() != capture_dialogue.ROM_SHA1:
        raise ValueError("reference must be the matching original Japanese ROM")
    rom = rom_path.read_bytes()
    cartridge.verify_checksums(rom)
    expected = {
        (moon, shine): title_graphics.compose(original, moon, shine, gradient=True)
        for moon in range(4)
        for shine in range(-1, 8)
    }
    start = title_graphics.offset(49, 0x4000) + 2 + 0x300
    bat_tiles = original[start : start + 0x800]
    frames, returned, menu = 0, None, None
    clocks = []
    first = None
    # Portable settings and all incidental emulator files stay in this directory.
    with tempfile.TemporaryDirectory(prefix="shiren-title-mesen-") as temporary:
        directory = Path(temporary)
        local_exe = directory / executable.name
        shutil.copy2(executable, local_exe)
        for sibling in executable.parent.iterdir():
            if sibling.is_file() and (
                sibling.suffix in (".dylib", ".dll", ".so") or ".so." in sibling.name
            ):
                shutil.copy2(sibling, directory / sibling.name)
        (directory / "settings.json").write_text("{}\n")
        local_rom = directory / "title-check.gbc"
        local_rom.write_bytes(rom)
        script = directory / "title-check.lua"
        shutil.copy2(ROOT / "tools/mesen_title_screen_capture.lua", script)
        log_path = directory / "capture.log"
        with log_path.open("w") as log:
            result = subprocess.run(
                [
                    str(local_exe),
                    "--testRunner",
                    "--timeout=60",
                    "--gameBoy.gbcAdjustColors=false",
                    "--gameBoy.blendFrames=false",
                    str(script),
                    str(local_rom),
                ],
                cwd=directory,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=70,
            )
        if result.returncode:
            raise ValueError(
                "Mesen title route exited with code %d" % result.returncode
            )
        for line in log_path.open():
            if not line.startswith(("TITLE_FRAME ", "TITLE_RETURN ", "TITLE_MENU ")):
                continue
            kind, frame, clock, moon, bat, pixels = line.split()
            actual = Image.frombytes("RGB", (160, 144), bytes.fromhex(pixels))
            if kind == "TITLE_MENU":
                menu = actual
                continue
            clock, moon, bat = int(clock), int(moon), int(bat)
            shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
            image = expected[moon, shine].copy()
            # The native main loop clears its OAM shadow between VBlanks.
            # The private phase table describes the bats actually displayed.
            start = title_graphics.offset(245, 0x5C00) + bat * 16
            records = rom[start : start + 12]
            for i in range(0, 12, 4):
                record = tuple(records[i : i + 4])
                if record[0]:
                    for x, y in sprite_pixels(bat_tiles, record):
                        image.putpixel((x, y), (8, 8, 8))
            if actual.tobytes() != image.tobytes():
                output.mkdir(parents=True, exist_ok=True)
                actual.save(output / "mismatch.png")
                image.save(output / "expected.png")
                raise ValueError(
                    "Mesen title differs from approved pixels at frame " + frame
                )
            if kind == "TITLE_RETURN":
                returned = (int(frame), actual)
            else:
                frames += 1
                clocks.append(clock)
                if first is None:
                    first = actual
    if frames != 480 or returned is None or menu is None:
        raise ValueError("Mesen did not complete every title checkpoint")
    if any(b != (a + 1) % 240 for a, b in zip(clocks, clocks[1:])):
        raise ValueError("Mesen title animation skipped a native frame")
    output.mkdir(parents=True, exist_ok=True)
    first.save(output / "title-screen.png")
    returned[1].save(output / "attract-return.png")
    menu.save(output / "start-menu.png")
    manifest = {
        "rom": rom_path.name,
        "rom_sha256": sha256(rom).hexdigest(),
        "emulator": str(executable),
        "emulator_sha256": sha256(executable.read_bytes()).hexdigest(),
        "verified_frames": frames,
        "attract_return_checkpoint": returned[0],
        "start_after_attract": "passed",
        "pixel_comparison": "exact RGB555, including the returned title",
        "profile": "temporary portable profile and temporary ROM",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--mesen", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/title-screen/mesen"
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            verify(args.mesen.resolve(), args.rom, args.reference, args.output),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
