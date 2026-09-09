#!/usr/bin/env python3
"""Verify GB2's ordinary physical damage math against the original ROM/mgbdis.

Run with --emulator to compare the arithmetic model with native routines in PyBoy.
This is a read-only audit; it never patches a ROM or saves gameplay progress.
"""
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
COEFFICIENTS = (240, 225, 198, 153, 91, 32, 4)
# Hexadecimal bank/CPU addresses, exclusive ends.
SPANS = (
    (0x00, 0x0309, 0x0320, "actor status lookup"),
    (0x00, 0x09AC, 0x09C6, "banked call"),
    (0x00, 0x0C45, 0x0C59, "8-bit multiplication"),
    (0x00, 0x1806, 0x186C, "random byte and bounded random draw"),
    (0x07, 0x4956, 0x4968, "Power Up stack cap"),
    (0x07, 0x5463, 0x547F, "level lookup"),
    (0x07, 0x5E63, 0x5E7C, "equipped item slots"),
    (0x07, 0x6A3A, 0x6A54, "level-based attack lookup"),
    (0x07, 0x6C64, 0x6D28, "attack, buffs, and defense getters"),
    (0x07, 0x7237, 0x729B, "level attack table"),
    (0x77, 0x6401, 0x6459, "attack/defense inputs and damage caller"),
    (0x77, 0x68E1, 0x6B23, "damage, modifiers, coefficients, variance, rounding"),
    (0x78, 0x4740, 0x478B, "effective weapon/shield strength"),
    (0x7A, 0x48A0, 0x48AE, "equipment base strength plus modifier"),
    (0x7E, 0x5169, 0x5193, "current strength plus bonus"),
)


def offset(bank, address):
    return bank * 0x4000 + (address - 0x4000 if bank else address)


def level_attack(level):
    if not 0 <= level <= 99:
        raise ValueError("level must be 0..99 (0 is the unused table entry)")
    if level < 2:
        return 5 * level
    return 2 * level + 2 if level <= 26 else level + 28


def player_attack(level, strength, sword, power_ups=0, enraged=False):
    # Strength above 247 would wrap the native byte-sized +8 before the next
    # addition. That corrupt/out-of-range input is outside this player model.
    if not (0 <= strength <= 247 and 0 <= sword <= 255 and 0 <= power_ups <= 4):
        raise ValueError("unsupported strength, sword strength, or Power Up count")
    weight = min(255, 8 + strength + sword // 2)
    attack = min(255, level_attack(level) * weight // 16)
    for _ in range(power_ups):
        attack = min(255, attack + attack // 2)
    return min(255, attack * 2) if enraged else attack


def defense_fixed(attack, defense):
    """Return the native pre-variance damage numerator (denominator 256)."""
    if not (0 <= attack <= 255 and 0 <= defense <= 255):
        raise ValueError("attack and defense must be bytes")
    value = attack * 256
    for bit, coefficient in enumerate(COEFFICIENTS, start=1):
        if defense & (1 << bit):
            value = (value // 256) * coefficient
    if attack and defense >= 2 and value < 256:
        value += 1
    return value


def ordinary_damage(attack, defense, roll):
    """No critical hit, slayer, blessing, resistance, or fixed-damage effects."""
    if not 0 <= roll < 64:
        raise ValueError("roll must be 0..63")
    value = defense_fixed(attack, defense)
    change = (value // 256) * (roll // 2)
    value += change if roll & 1 else -change
    return min(255, max(int(value != 0), (value + 128) // 256))


def distribution(attack, defense):
    return dict(sorted(Counter(ordinary_damage(attack, defense, r) for r in range(64)).items()))


def verify_bytes(rom, directory, comparisons):
    decoded = {}
    spans = []
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
        spans.append(dict(address=f"{bank:02X}:{start:04X}", end_exclusive=f"{end:04X}",
                          purpose=purpose, sha256=sha256(raw).hexdigest()))
    compared = []
    for path in comparisons:
        candidate = path.read_bytes()
        for bank, start, end, purpose in SPANS:
            region = slice(offset(bank, start), offset(bank, end))
            if candidate[region] != rom[region]:
                raise ValueError(f"{path}: changed {purpose} at {bank:02X}:{start:04X}")
        compared.append(dict(path=str(path), sha256=sha256(candidate).hexdigest(), matched=True))
    return spans, compared


def verify_native(rom):
    from pyboy import PyBoy

    counts = Counter()
    with tempfile.TemporaryDirectory(prefix="shiren-damage-") as directory:
        path = Path(directory) / "original.gbc"
        path.write_bytes(rom)
        gb = PyBoy(str(path), window="null", ram_file=io.BytesIO(bytes(0x8000)), sound_emulated=False)
        try:
            gb.set_emulation_speed(0)
            gb.tick(120, False)
            # The real bounded RNG executes. Replace its result just after the
            # call, keeping combat arithmetic, carry, and rounding native.
            gb.hook_register(0x77, 0x6B04,
                             lambda _: setattr(gb.register_file, "A", gb.memory[0xC200]), None)

            def run_batch(bank, cases, label, word_result=False):
                # Each case supplies setup instructions, entry point, and an
                # expected C or BC result. The harness stays in fixed WRAM, outside
                # RNG/bank-switch scratch. Results occupy WRAM bank 1.
                code = bytearray([0xF3])
                for i, (setup, entry, _) in enumerate(cases):
                    target = 0xD800 + i * (2 if word_result else 1)
                    code.extend(setup)
                    code.extend([0xCD, entry & 255, entry >> 8, 0x79,
                                 0xEA, target & 255, target >> 8])
                    if word_result:
                        code.extend([0x78, 0xEA, (target + 1) & 255, (target + 1) >> 8])
                code.extend(bytes.fromhex("3E A5 EA 01 C2 18 FE"))
                if len(code) > 0xBB0:
                    raise ValueError("WRAM harness would overlap its stack")
                gb.memory[0xFF70] = 1
                gb.memory[0xFFFF] = 0
                gb.memory[0xFF0F] = 0
                gb.memory[0x2100] = bank
                gb.memory[0xFFF7] = bank
                gb.memory[0xC201] = 0
                gb.memory[0xC400:0xC400 + len(code)] = code
                gb.register_file.SP = 0xCFF0
                gb.register_file.PC = 0xC400
                for _ in range(32):
                    gb.tick(4, False)
                    if gb.memory[0xC201] == 0xA5:
                        break
                width = 2 if word_result else 1
                raw = bytes(gb.memory[0xD800:0xD800 + len(cases) * width])
                actual = [int.from_bytes(raw[i:i + width], "little") for i in range(0, len(raw), width)]
                expected = [case[2] for case in cases]
                if gb.memory[0xC201] != 0xA5 or actual != expected:
                    mismatch = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), None)
                    raise ValueError(f"{label}: native mismatch at case {mismatch}; "
                                     f"PC={gb.register_file.PC:04X}, actual={actual[mismatch] if mismatch is not None else None}, "
                                     f"expected={expected[mismatch] if mismatch is not None else None}")
                counts[label] += len(cases)

            gb.memory[0xFFB0:0xFFB8] = bytes(8)
            gb.memory[0xC200] = 0
            for defense in range(256):
                for start in (0, 128):
                    run_batch(0x77, [(bytes([0x01, attack, defense]), 0x6ACB,
                                       defense_fixed(attack, defense)) for attack in range(start, start + 128)],
                              "fixed_defense_numerator", word_result=True)
                run_batch(0x77, [(bytes([0x01, attack, defense]), 0x68E1,
                                   ordinary_damage(attack, defense, 0)) for attack in range(256)],
                          "all_attack_defense_pairs")
            for roll in range(64):
                gb.memory[0xC200] = roll
                for defense in (0, 2, 10, 20, 100, 254):
                    run_batch(0x77, [(bytes([0x01, attack, defense]), 0x68E1,
                                       ordinary_damage(attack, defense, roll)) for attack in range(256)],
                              "variance_and_rounding")
            for base in range(128):
                run_batch(7, [(bytes([0x0E, base, 0x3E, weight]), 0x6CE4,
                               min(255, base * weight // 16)) for weight in range(256)],
                          "attack_multiply_divide_cap")

            # Exercise the complete player attack getter. Unequipped item slots
            # plus the native equipment-bonus field supply effective W, avoiding
            # any fabricated item parser or hook on the math itself.
            gb.memory[0xFF70] = 1
            gb.memory[0xD000] = 0
            gb.memory[0xD2B1:0xD2B5] = bytes([255] * 4)
            gb.memory[0xD2A7] = 0
            gb.memory[0xD2BF] = 0
            gb.memory[0xFFFC] = 0
            gb.memory[0xFF96:0xFF99] = bytes(3)
            for sword in (0, 1, 2, 3, 10, 11, 99, 254, 255):
                gb.memory[0xFF70] = 2
                gb.memory[0xDE19] = sword
                gb.memory[0xDE1A] = 0
                gb.memory[0xFF70] = 1
                for strength in (0, 1, 7, 8, 9, 20, 50, 99, 104):
                    gb.memory[0xD2A6] = strength
                    run_batch(7, [(bytes([0x3E, level, 0xE0, 0x9A]), 0x6CC2,
                                   player_attack(level, strength, sword)) for level in range(1, 100)],
                              "full_player_attack_getter")
            gb.memory[0xFF70] = 2
            gb.memory[0xDE19] = 0
            gb.memory[0xFF70] = 1
            gb.memory[0xD2A6] = 8
            for stacks in range(5):
                gb.memory[0xD2BF] = stacks
                for enraged in (False, True):
                    gb.memory[0xFF97] = 0x80 if enraged else 0
                    run_batch(7, [(bytes([0x1E, 0, 0x3E, level, 0xE0, 0x9A]), 0x6C64,
                                   player_attack(level, 8, 0, stacks, enraged)) for level in range(1, 100)],
                              "power_up_and_enraged")
        finally:
            gb.stop(save=False)
    return dict(passed=True, cases=dict(counts), total=sum(counts.values()),
                method="original routines in PyBoy; isolated WRAM inputs and controlled 6-bit RNG result")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument("--mgbdis", type=Path, default=ROOT / "build/mgbdis")
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build/player-damage")
    parser.add_argument("--emulator", action="store_true")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if sha1(rom).hexdigest() != SOURCE_SHA1:
        raise ValueError("unsupported source ROM SHA-1")
    if list(rom[offset(7, 0x7237):offset(7, 0x729B)]) != [level_attack(i) for i in range(100)]:
        raise ValueError("level attack table mismatch")
    if tuple(rom[offset(0x77, 0x6AF5):offset(0x77, 0x6AFC)]) != COEFFICIENTS:
        raise ValueError("defense coefficient table mismatch")
    spans, compared = verify_bytes(rom, args.mgbdis, args.compare)
    report = dict(source_sha1=SOURCE_SHA1, spans=spans, comparisons=compared,
                  level_attack=[level_attack(i) for i in range(100)],
                  coefficients=COEFFICIENTS, examples=[])
    for level, strength, sword, defense in ((1, 8, 0, 5), (10, 8, 10, 10), (10, 9, 10, 10), (99, 99, 255, 0)):
        attack = player_attack(level, strength, sword)
        report["examples"].append(dict(level=level, strength=strength, sword=sword, defense=defense,
                                       attack=attack, fixed=defense_fixed(attack, defense),
                                       damage_counts_out_of_64=distribution(attack, defense)))
    if args.emulator:
        report["native"] = verify_native(rom)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS level/defense tables and {len(SPANS)} mgbdis spans; {len(compared)} comparison ROMs match.")
    if args.emulator:
        print(f"PASS {report['native']['total']:,} native cases: {report['native']['cases']}")
    print(f"Evidence: {args.out_dir / 'audit.json'}")


if __name__ == "__main__":
    main()
