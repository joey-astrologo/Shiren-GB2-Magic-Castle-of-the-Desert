#!/usr/bin/env python3
"""Build and optionally capture the first GB2 native-VWF English smoke ROM.

The smoke is a one-record input to the production translation-aware allocator and writer.
It resizes and relocates the complete script corpus, repoints the real directory, installs
the approved font, and validates every logical lookup from the resulting ROM.
"""
import argparse
from pathlib import Path
import sys

import build as translated_build
import capture_dialogue
import english


RECORD_BANK = 195
RECORD_ADDRESS = 0x562F
SOURCE = "Hello, Shiren!<br>Native VWF works.<page><box>"


def build(rom):
    """Return ``(patched_rom, encoded_smoke_payload)`` with fixed checksums."""
    payload = english.encode_source(SOURCE)
    output, _allocation, _validation = translated_build.build_rom(
        rom, {(RECORD_BANK, RECORD_ADDRESS): payload}
    )
    return output, payload


def capture(rom_path, png_path, payload):
    """Boot the smoke ROM to its first English dialogue and save the screen."""
    PyBoy = capture_dialogue._pyboy_class()
    pyboy = PyBoy(str(rom_path), window="null")
    pyboy.set_emulation_speed(0)
    try:
        capture_dialogue.run_to_dialogue(pyboy)
        staged = bytes(pyboy.memory[0xC800:0xC800 + len(payload)])
        if staged != payload:
            raise RuntimeError("smoke route did not stage the English payload")
        png_path = Path(png_path)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        pyboy.screen.image.save(png_path)
    finally:
        pyboy.stop(save=False)
    return png_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("output", help="output English smoke ROM")
    parser.add_argument("--png", help="also boot the ROM and save its dialogue screenshot")
    args = parser.parse_args(argv)
    try:
        output, payload = build(Path(args.rom).read_bytes())
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output)
        screenshot = capture(destination, args.png, payload) if args.png else None
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print("record      : %d:$%04X" % (RECORD_BANK, RECORD_ADDRESS))
    print("source      : %s" % SOURCE)
    print("encoded     : %s" % payload.hex().upper())
    print("output      : %s" % destination)
    if screenshot:
        print("screenshot  : %s" % screenshot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
