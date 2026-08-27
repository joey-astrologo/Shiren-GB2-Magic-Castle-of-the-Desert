#!/usr/bin/env python3
"""Reproduce the first full dialogue screen and save a PyBoy state/screenshot.

The path is entirely deterministic: boot, create the first adventure log, accept
the default name, then let the opening cutscene reach the first three-line box.
No battery save is read or written.
"""
import argparse
from hashlib import sha1
from pathlib import Path
import sys


ROM_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
PRESS_FRAMES = 5

# The renderer initializer at 0:$312B reads a banked ROM source location from
# $C4DB:$C4DC/$C4DD and expands/copies that record into the $C800 working buffer.
# Hooking this routine is therefore a direct ROM-reference trace, upstream of the
# WRAM fixture asserted below.
SOURCE_INIT = (0, 0x312B)
SOURCE_BANK_AT = 0xC4DB
SOURCE_POINTER_AT = 0xC4DC

# This exact prefix is staged at $C800 for the captured box. It is better than a
# screenshot hash as an assertion: it proves that the intended script record, not
# merely a visually similar scene, is active.
DIALOGUE_PREFIX = bytes.fromhex(
    "f0 3e f0 40 f1 5a f2 22 f2 24 f0 44 f0 46 74 24 "
    "31 36 71 34 59 45 fd 24 44 63 3f 52 48 5c 24 43 "
    "56 33 3f 43 48 fd 24 4d 32 39 37 67 24 30 63 3f "
    "67 2c fb fc"
)


def _pyboy_class():
    try:
        from pyboy import PyBoy
    except ImportError as exc:
        raise RuntimeError("PyBoy is required to capture the dialogue fixture") from exc
    return PyBoy


def _ticks(pyboy, count):
    for _ in range(count):
        pyboy.tick()


def run_to_dialogue(pyboy):
    """Drive a fresh boot to the first complete dialogue screen."""
    for frame in range(721):
        if frame == 360:
            pyboy.button("start", PRESS_FRAMES)
        if frame == 540:
            pyboy.button("a", PRESS_FRAMES)
        pyboy.tick()

    pyboy.button("a", PRESS_FRAMES)       # create an adventure log
    _ticks(pyboy, 240)
    pyboy.button("start", PRESS_FRAMES)   # select "done" on name entry
    _ticks(pyboy, 30)
    pyboy.button("a", PRESS_FRAMES)       # accept the default name

    # Name confirmation/cutscene/tower scene, measured from a clean boot.
    _ticks(pyboy, 600 + 3601 + 2851)


def validate_dialogue(pyboy, expected=DIALOGUE_PREFIX):
    """Assert the expected renderer payload at the opening dialogue buffer."""
    expected = bytes(expected)
    got = bytes(pyboy.memory[0xC800:0xC800 + len(expected)])
    if got != expected:
        raise RuntimeError(
            "capture missed the dialogue fixture: $C800 starts %s, expected %s"
            % (got[:16].hex(" "), expected[:16].hex(" "))
        )


def wait_for_dialogue(pyboy, expected, max_frames):
    """Tick until an exact staged dialogue prefix appears, or fail closed."""
    expected = bytes(expected)
    for frame in range(max_frames + 1):
        got = bytes(pyboy.memory[0xC800:0xC800 + len(expected)])
        if got == expected:
            return frame
        if frame < max_frames:
            pyboy.tick()
    raise RuntimeError(
        "dialogue prefix did not appear within %d frames; $C800 starts %s"
        % (max_frames, got[:16].hex(" "))
    )


def source_location(pyboy):
    """Return the bank/address currently selected for the ROM text reader."""
    bank = pyboy.memory[SOURCE_BANK_AT]
    pointer = pyboy.memory[SOURCE_POINTER_AT] | (pyboy.memory[SOURCE_POINTER_AT + 1] << 8)
    return bank, pointer


def trace_to_dialogue(pyboy, expected=DIALOGUE_PREFIX):
    """Drive the fixture route and return every ROM source seen by 0:$312B."""
    events = []

    def at_source_init(_context=None):
        event = source_location(pyboy)
        if not events or events[-1] != event:
            events.append(event)

    pyboy.hook_register(*SOURCE_INIT, at_source_init, None)
    run_to_dialogue(pyboy)
    validate_dialogue(pyboy, expected)
    return events


def capture(rom_path, state_path, screenshot_path):
    rom_path = Path(rom_path)
    digest = sha1(rom_path.read_bytes()).hexdigest()
    if digest != ROM_SHA1:
        raise ValueError("ROM SHA1 is %s; expected %s" % (digest, ROM_SHA1))

    PyBoy = _pyboy_class()
    pyboy = PyBoy(str(rom_path), window="null")
    pyboy.set_emulation_speed(0)
    try:
        run_to_dialogue(pyboy)
        validate_dialogue(pyboy)
        state_path = Path(state_path)
        screenshot_path = Path(screenshot_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("wb") as handle:
            pyboy.save_state(handle)
        pyboy.screen.image.save(screenshot_path)
    finally:
        pyboy.stop(save=False)
    return state_path, screenshot_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--state", default="build/first-dialogue.state")
    parser.add_argument("--png", default="build/first-dialogue.png")
    args = parser.parse_args(argv)
    try:
        state, png = capture(args.rom, args.state, args.png)
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(state)
    print(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
