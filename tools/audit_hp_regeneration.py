#!/usr/bin/env python3
"""Audit Shiren's natural HP regeneration without patching a ROM or saving a game."""
import argparse
from collections import Counter
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
SOURCE_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
# Hexadecimal bank/CPU addresses; exclusive ends.
SPANS = (
    (0x00, 0x0309, 0x0320, "actor status gate"),
    (0x00, 0x038D, 0x0398, "equipment effect flag lookup"),
    (0x00, 0x0C20, 0x0C3B, "maximum HP times five"),
    (0x00, 0x0EFA, 0x0F06, "bit lookup"),
    (0x00, 0x2F4B, 0x2F51, "HP display refresh flag"),
    (0x01, 0x59C1, 0x59D5, "player action completion caller"),
    (0x01, 0x674A, 0x6765, "status-dependent regeneration dispatch"),
    (0x07, 0x4BCF, 0x4CC4, "HP getters, capped addition, regeneration"),
    (0x07, 0x5641, 0x564E, "current Fullness getter"),
    (0x7E, 0x5825, 0x5859, "initial zero counter and 15 maximum HP"),
)


def offset(bank, address):
    return bank * 0x4000 + (address - 0x4000 if bank else address)


def regen_step(hp, maximum, counter, *, fullness=100, healing=False, blocked=False):
    """One call to the ordinary player regeneration routine; no companion branch.

    Returns (new_hp, new_counter). Caller-level status/action diversions are
    outside this function. The counter is a real unsigned 16-bit accumulator.
    """
    if not (1 <= maximum <= 250 and 0 <= hp <= maximum and 0 <= counter <= 65535):
        raise ValueError("invalid HP or counter")
    if not 0 <= fullness <= 200:
        raise ValueError("invalid Fullness")
    if blocked:
        return hp, counter
    counter = (counter + 5 * maximum) % 65536
    due = counter >= 1000
    if due:
        counter -= 1000  # Exactly once, even when another 1000 remains.
    if fullness == 0 or hp == 0 or hp == maximum or not (due or healing):
        return hp, counter
    return min(maximum, hp + (5 if healing else 1)), counter


def verify_bytes(rom, directory, comparisons):
    decoded = {}
    reports = []
    for bank, start, end, purpose in SPANS:
        if bank not in decoded:
            decoded[bank] = {}
            for line in (directory / f"bank_{bank:03x}.asm").read_text().splitlines():
                match = re.search(r"; \$([0-9A-F]{4}): (.*)$", line)
                if match:
                    address = int(match[1], 16)
                    values = re.findall(r"\$([0-9A-F]{2})(?![0-9A-F])", match[2])
                    decoded[bank].update({address + i: int(v, 16) for i, v in enumerate(values)})
        raw = rom[offset(bank, start):offset(bank, end)]
        if bytes(decoded[bank][a] for a in range(start, end)) != raw:
            raise ValueError(f"mgbdis mismatch at {bank:02X}:{start:04X}")
        reports.append(dict(address=f"{bank:02X}:{start:04X}", end_exclusive=f"{end:04X}",
                            purpose=purpose, sha256=sha256(raw).hexdigest()))
    compared = []
    for path in comparisons:
        candidate = path.read_bytes()
        for bank, start, end, purpose in SPANS:
            region = slice(offset(bank, start), offset(bank, end))
            if candidate[region] != rom[region]:
                raise ValueError(f"{path}: changed {purpose} at {bank:02X}:{start:04X}")
        compared.append(dict(path=str(path), sha256=sha256(candidate).hexdigest(), matched=True))
    return reports, compared


def verify_native(rom):
    from pyboy import PyBoy

    counts = Counter()
    with tempfile.TemporaryDirectory(prefix="shiren-regen-") as directory:
        path = Path(directory) / "original.gbc"
        path.write_bytes(rom)
        gb = PyBoy(str(path), window="null", ram_file=io.BytesIO(bytes(0x8000)), sound_emulated=False)
        try:
            gb.set_emulation_speed(0)
            gb.tick(120, False)
            gb.memory[0xFFFC] = 0
            gb.memory[0xC0B6] = 255  # No companion side effect.

            def run_batch(maximum, cases, label, *, fullness=100, healing=False, blocked=False):
                code = bytearray([0xF3])
                for i, (hp, counter) in enumerate(cases):
                    code.extend([0x21, 0xA3, 0xD2, 0x36, counter & 255, 0x23, 0x36, counter >> 8,
                                 0x3E, hp, 0xE0, 0x9B, 0xCD, 0x27, 0x4C])
                    for j, address in enumerate((0xFF9B, 0xD2A3, 0xD2A4)):
                        result = 0xD800 + 3 * i + j
                        code.extend([0xFA, address & 255, address >> 8,
                                     0xEA, result & 255, result >> 8])
                code.extend(bytes.fromhex("3E A5 EA 00 C2 18 FE"))
                # C4C1 is the native HUD-refresh flag set when HP changes.
                # Keep executable scratch above that flag as well as the RNG.
                if len(code) > 0x9B0:
                    raise ValueError("WRAM harness overlaps stack")
                gb.memory[0xFF70] = 1
                gb.memory[0xFF9C] = maximum
                gb.memory[0xD2AD] = fullness
                gb.memory[0xD2BB] = 0x20 if healing else 0
                gb.memory[0xC12B] = 4 if blocked else 0
                gb.memory[0xFFFF] = 0
                gb.memory[0xFF0F] = 0
                gb.memory[0x2100] = 7
                gb.memory[0xFFF7] = 7
                gb.memory[0xC200] = 0
                gb.memory[0xC600:0xC600 + len(code)] = code
                gb.register_file.SP = 0xCFF0
                gb.register_file.PC = 0xC600
                for _ in range(16):
                    gb.tick(4, False)
                    if gb.memory[0xC200] == 0xA5:
                        break
                if gb.memory[0xC200] != 0xA5:
                    raise ValueError(f"native {label} did not return: maximum={maximum}, "
                                     f"PC={gb.register_file.PC:04X}, SP={gb.register_file.SP:04X}")
                raw = bytes(gb.memory[0xD800:0xD800 + 3 * len(cases)])
                for i, (hp, counter) in enumerate(cases):
                    actual = raw[3*i], int.from_bytes(raw[3*i+1:3*i+3], "little")
                    expected = regen_step(hp, maximum, counter, fullness=fullness,
                                          healing=healing, blocked=blocked)
                    if actual != expected:
                        raise ValueError(f"{label}: maximum={maximum}, hp={hp}, counter={counter}: "
                                         f"native={actual}, expected={expected}")
                counts[label] += len(cases)

            for maximum in range(1, 251):
                for start in range(0, 1000, 64):
                    run_batch(maximum, [(1, p) for p in range(start, min(start + 64, 1000))],
                              "normal_counter_range")
            for maximum in (201, 250):
                for start in range(0, 65536, 64):
                    run_batch(maximum, [(1, p) for p in range(start, start + 64)], "full_16_bit_counter")
            for maximum in (15, 40, 100, 200, 250):
                cases = [(hp, p) for hp in (0, 1, maximum - 1, maximum) for p in (0, 999, 1000, 65000)]
                for fullness in (0, 100):
                    for healing in (False, True):
                        for blocked in (False, True):
                            run_batch(maximum, cases, "healing_and_suppression",
                                      fullness=fullness, healing=healing, blocked=blocked)
        finally:
            gb.stop(save=False)
    return dict(passed=True, cases=dict(counts), total=sum(counts.values()),
                method="original 07:4C27 in PyBoy, including HP/counter writes; no routine hooks")


def verify_live(rom, state):
    from pyboy import PyBoy
    from tools import pyboy_state

    before, after = [], []
    with tempfile.TemporaryDirectory(prefix="shiren-regen-live-") as directory:
        path = Path(directory) / "original.gbc"
        path.write_bytes(rom)
        gb = PyBoy(str(path), window="null", ram_file=io.BytesIO(pyboy_state.cart_ram(state)), sound_emulated=False)
        try:
            gb.set_emulation_speed(0)
            with state.open("rb") as handle:
                gb.load_state(handle)
            gb.memory[0xFF70] = 1
            gb.memory[0xD00B:0xD00D] = bytes([39, 40])
            gb.memory[0xFF9B:0xFF9D] = bytes([39, 40])
            gb.memory[0xD2A3:0xD2A5] = bytes(2)
            gb.memory[0xD2AD] = 100
            gb.memory[0xD2BB:0xD2BD] = bytes(2)

            def snapshot(destination):
                def capture(_):
                    old_bank = gb.memory[0xFF70]
                    gb.memory[0xFF70] = 1
                    destination.append(dict(frame=gb.frame_count, hp=gb.memory[0xFF9B],
                                            maximum=gb.memory[0xFF9C],
                                            counter=gb.memory[0xD2A3] + 256 * gb.memory[0xD2A4]))
                    gb.memory[0xFF70] = old_bank
                return capture
            gb.hook_register(7, 0x4C27, snapshot(before), None)
            gb.hook_register(1, 0x59D2, snapshot(after), None)
            gb.tick(120, False)
            if before:
                raise ValueError("fixture was not idle before input")
            gb.button_press("b")
            gb.button_press("a")
            gb.tick(240, False)
            gb.button_release("a")
            gb.button_release("b")
            gb.tick(30, False)
            if len(before) < 6 or len(before) != len(after):
                raise ValueError("live wait route did not produce at least six matched updates")
            for a, b in zip(before, after):
                expected = regen_step(a["hp"], a["maximum"], a["counter"])
                if (b["hp"], b["counter"]) != expected:
                    raise ValueError(f"live wait regeneration mismatch: {a}, {b}, {expected}")
        finally:
            gb.stop(save=False)
    return dict(passed=True, state=str(state), state_sha256=sha256(state.read_bytes()).hexdigest(),
                idle_frames=120, updates=len(before), before=before, after=after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument("--mgbdis", type=Path, default=ROOT / "build/mgbdis")
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build/hp-regeneration")
    parser.add_argument("--emulator", action="store_true")
    parser.add_argument("--live-state", type=Path, help="also check idle and B+A waiting in the Mamel fixture")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if sha1(rom).hexdigest() != SOURCE_SHA1:
        raise ValueError("unsupported original ROM")
    spans, comparisons = verify_bytes(rom, args.mgbdis, args.compare)
    report = dict(source_sha1=SOURCE_SHA1, spans=spans, comparisons=comparisons)
    if args.emulator:
        report["native"] = verify_native(rom)
    if args.live_state:
        report["live"] = verify_live(rom, args.live_state)
    counter = 0
    skipped = []
    for update in range(1, 1001):
        hp, counter = regen_step(1, 250, counter)
        if hp == 1:
            skipped.append(update)
    report["maximum_250_sequence"] = dict(updates=1000, starting_counter=0, skipped_updates=skipped,
                                           ending_counter=counter)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS {len(spans)} mgbdis spans; {len(comparisons)} comparison ROMs match.")
    if args.emulator:
        print(f"PASS {report['native']['total']:,} native cases: {report['native']['cases']}")
    if args.live_state:
        print(f"PASS live idle/wait route: {report['live']['updates']} regeneration updates.")
    print(f"Evidence: {args.out_dir / 'audit.json'}")


if __name__ == "__main__":
    # Keep direct-script and python -m invocation equivalent for fixture helpers.
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    main()
