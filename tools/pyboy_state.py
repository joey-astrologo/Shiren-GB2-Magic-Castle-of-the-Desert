"""Read memory from the project's native PyBoy save-state fixtures."""

import io
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM = (
    ROOT
    / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
)


class PyBoyStateError(ValueError):
    """A native state could not be inspected safely."""


def _pyboy_class():
    try:
        from pyboy import PyBoy
    except ImportError as exc:
        raise PyBoyStateError("PyBoy is required to inspect a state fixture") from exc
    return PyBoy


def _load(state_path, rom_path=None):
    state_path = Path(state_path)
    rom_path = Path(rom_path or DEFAULT_ROM)
    if state_path.suffix != ".state":
        raise PyBoyStateError("expected a native .state fixture: %s" % state_path)
    if not state_path.is_file():
        raise PyBoyStateError("state fixture does not exist: %s" % state_path)
    if not rom_path.is_file():
        raise PyBoyStateError("ROM does not exist: %s" % rom_path)

    pyboy = _pyboy_class()(
        str(rom_path),
        window="null",
        sound_emulated=False,
        ram_file=io.BytesIO(bytes(0x8000)),
    )
    pyboy.set_emulation_speed(0)
    try:
        with state_path.open("rb") as handle:
            pyboy.load_state(handle)
    except Exception:
        pyboy.stop(save=False)
        raise
    return pyboy


def cart_ram(state_path, rom_path=None):
    """Return all four 8 KiB cartridge-RAM banks restored by a state."""
    pyboy = _load(state_path, rom_path)
    try:
        pyboy.memory[0x0000] = 0x0A
        banks = []
        for bank in range(4):
            pyboy.memory[0x4000] = bank
            banks.append(bytes(pyboy.memory[0xA000:0xC000]))
        return b"".join(banks)
    finally:
        pyboy.stop(save=False)


def work_ram(state_path, rom_path=None):
    """Return WRAM in the flat 32 KiB bank order used by project tooling."""
    pyboy = _load(state_path, rom_path)
    try:
        banks = [bytes(pyboy.memory[0xC000:0xD000])]
        for bank in range(1, 8):
            pyboy.memory[0xFF70] = bank
            banks.append(bytes(pyboy.memory[0xD000:0xE000]))
        return b"".join(banks)
    finally:
        pyboy.stop(save=False)


def high_ram(state_path, rom_path=None):
    """Return the 127-byte CGB high-RAM window restored by a state."""
    pyboy = _load(state_path, rom_path)
    try:
        return bytes(pyboy.memory[0xFF80:0xFFFF])
    finally:
        pyboy.stop(save=False)


def load_into(pyboy, state_path):
    """Load a fixture into an existing PyBoy instance."""
    state_path = Path(state_path)
    if state_path.suffix != ".state":
        raise PyBoyStateError("expected a native .state fixture: %s" % state_path)
    with state_path.open("rb") as handle:
        pyboy.load_state(handle)
    return pyboy
