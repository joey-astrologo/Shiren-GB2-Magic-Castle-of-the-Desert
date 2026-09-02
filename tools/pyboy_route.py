"""Shared controller and memory helpers for native PyBoy route tests."""

import io
from pathlib import Path


def start(PyBoy, rom_path, state_path):
    pyboy = PyBoy(
        str(rom_path),
        window="null",
        sound_emulated=False,
        ram_file=io.BytesIO(bytes(0x8000)),
    )
    pyboy.set_emulation_speed(0)
    with Path(state_path).open("rb") as handle:
        pyboy.load_state(handle)
    return pyboy


def press(pyboy, button, frames=5):
    pyboy.button(button, frames)


def run_frames(pyboy, count, actions=()):
    schedule = {}
    for frame, button in actions:
        schedule.setdefault(frame, []).append(button)
    for frame in range(count):
        for button in schedule.get(frame, ()):
            press(pyboy, button)
        pyboy.tick()


def find_cpu(pyboy, pattern, start_at=0xC000, end_at=0xE000):
    pattern = bytes(pattern)
    memory = bytes(pyboy.memory[start_at:end_at])
    offset = memory.find(pattern)
    return None if offset < 0 else start_at + offset


def flat_work_ram(pyboy):
    old_bank = pyboy.memory[0xFF70]
    try:
        banks = [bytes(pyboy.memory[0xC000:0xD000])]
        for bank in range(1, 8):
            pyboy.memory[0xFF70] = bank
            banks.append(bytes(pyboy.memory[0xD000:0xE000]))
        return b"".join(banks)
    finally:
        pyboy.memory[0xFF70] = old_bank


def work_read(pyboy, offset, size=1):
    """Read bytes from the project's flat 32 KiB WRAM address space."""
    if not 0 <= offset < 0x8000 or not 0 <= size <= 0x8000 - offset:
        raise ValueError("WRAM read is outside the 32 KiB flat address space")
    return bytes(work_read_byte(pyboy, offset + index) for index in range(size))


def work_read_byte(pyboy, offset):
    if not 0 <= offset < 0x8000:
        raise ValueError("WRAM offset is outside the 32 KiB flat address space")
    if offset < 0x1000:
        return pyboy.memory[0xC000 + offset]
    old_bank = pyboy.memory[0xFF70]
    try:
        pyboy.memory[0xFF70] = offset // 0x1000
        return pyboy.memory[0xD000 + offset % 0x1000]
    finally:
        pyboy.memory[0xFF70] = old_bank


def work_write(pyboy, offset, values):
    """Write bytes to flat WRAM and verify every write immediately."""
    values = bytes(values)
    if not 0 <= offset < 0x8000 or len(values) > 0x8000 - offset:
        raise ValueError("WRAM write is outside the 32 KiB flat address space")
    for index, value in enumerate(values):
        work_write_byte(pyboy, offset + index, value)


def work_write_byte(pyboy, offset, value):
    if not 0 <= offset < 0x8000:
        raise ValueError("WRAM offset is outside the 32 KiB flat address space")
    if not 0 <= value <= 0xFF:
        raise ValueError("WRAM value is outside the byte range")
    if offset < 0x1000:
        address = 0xC000 + offset
        pyboy.memory[address] = value
        actual = pyboy.memory[address]
    else:
        old_bank = pyboy.memory[0xFF70]
        try:
            pyboy.memory[0xFF70] = offset // 0x1000
            address = 0xD000 + offset % 0x1000
            pyboy.memory[address] = value
            actual = pyboy.memory[address]
        finally:
            pyboy.memory[0xFF70] = old_bank
    if actual != value:
        raise AssertionError("WRAM write failed at flat offset $%04X" % offset)


def find_work_ram(pyboy, pattern):
    offset = flat_work_ram(pyboy).find(bytes(pattern))
    return None if offset < 0 else offset


def screen_ink(pyboy, x, y):
    return pyboy.screen.image.getpixel((x, y))[:3] == (0, 0, 0)


def wait_until(pyboy, predicate, maximum_frames, actions=None):
    """Tick until predicate succeeds, optionally selecting input per frame."""
    for frame in range(maximum_frames + 1):
        value = predicate()
        if value:
            return frame, value
        if frame == maximum_frames:
            break
        if actions is not None:
            button = actions(frame)
            if button:
                press(pyboy, button)
        pyboy.tick()
    raise AssertionError("route condition not reached within %d frames" % maximum_frames)
