#!/usr/bin/env python3
"""Read GB2 monster special-action thresholds; never modify a ROM.

The Markdown table belongs between the generated markers in
docs/MONSTER_SPECIAL_MOVE_RATES.md. The full JSON/TSV retain evidence addresses.
"""
import argparse
import csv
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import re
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
SOURCE_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
# Addresses here, including bank numbers, are hexadecimal. Ends are exclusive.
SPANS = (
    (0x00, 0x09C6, 0x09E0, "indexed pointer lookup"),
    (0x00, 0x1806, 0x1830, "random byte generator"),
    (0x00, 0x1939, 0x1944, "probability comparison and FF shortcut"),
    (0x01, 0x4312, 0x449E, "monster action selection and dispatch"),
    (0x07, 0x4213, 0x423A, "family-specific probability bypass flag"),
    (0x08, 0x4000, 0x419C, "eligibility and action handler tables"),
    (0x08, 0x42F6, 0x4303, "eligibility dispatcher"),
    (0x08, 0x4405, 0x44EF, "adjacency and projectile exceptions"),
    (0x0A, 0x41CF, 0x41E9, "tier stat record lookup"),
    (0x0A, 0x42CE, 0x42D7, "copy threshold into actor cache"),
    (0x0A, 0x4778, 0x57B2, "stat pointers and all Notebook monster records"),
    (0x0B, 0x7CBD, 0x7E5F, "209-entry Monster Notebook catalog"),
)
BYPASS_FAMILIES = {0x02, 0x07, 0x0B, 0x10, 0x15, 0x3F, 0x43}


def offset(bank, address):
    return bank * 0x4000 + (address - 0x4000 if bank else address)


def word(rom, bank, address):
    start = offset(bank, address)
    return int.from_bytes(rom[start:start + 2], "little")


def exact_percent(threshold):
    return "100%" if threshold == 255 else f"{threshold * 100 / 256:.6f}".rstrip("0").rstrip(".") + "%"


def read_entries(rom):
    with (ROOT / "script/en/glossary.tsv").open(encoding="utf-8", newline="") as handle:
        names = {row["id"]: row["english"] for row in csv.DictReader(handle, delimiter="\t")}
    start = offset(0x0B, 0x7CBD)
    catalog = list(zip(rom[start:start + 418:2], rom[start + 1:start + 418:2]))
    if len(set(catalog)) != 209:
        raise ValueError("expected 209 unique Notebook forms")
    entries = []
    for tier, family in sorted(catalog, key=lambda pair: (pair[1], pair[0])):
        if not (1 <= family <= 73 and 1 <= tier <= 3):
            raise ValueError(f"invalid Notebook form: {family}:{tier}")
        pointer = word(rom, 0x0A, 0x4778 + family * 2)
        tiers = rom[offset(0x0A, pointer)]
        if tier > tiers:
            raise ValueError(f"Notebook form exceeds native tier count: {family}:{tier}")
        address = pointer + 1 + (tier - 1) * 18 + 6
        threshold = rom[offset(0x0A, address)]
        name_table = (0x4AA4, 0x4F88, 0x54F6)[tier - 1]
        name_id = f"192:${word(rom, 0xC0, name_table + family * 2):04X}"
        name = names[name_id]
        if not name:
            raise ValueError(f"missing English name: {name_id}")
        eligibility = word(rom, 0x08, 0x4000 + family * 2)
        rule = "ordinary"
        if family in BYPASS_FAMILIES:
            rule = "bypass"
        elif eligibility == 0x44CC:
            rule = "no ordinary special"
        entries.append(dict(
            name=name, family_id=f"{family:02X}", tier=tier,
            threshold=threshold, threshold_hex=f"${threshold:02X}",
            base_chance=exact_percent(threshold), address=f"0A:{address:04X}",
            eligibility=f"08:{eligibility:04X}",
            action=f"08:{word(rom, 0x08, 0x40CE + family * 2):04X}",
            rule=rule,
        ))
    return entries


def verify_mgbdis(rom, directory):
    banks = {}
    reports = []
    for bank, start, end, purpose in SPANS:
        if bank not in banks:
            path = directory / f"bank_{bank:03x}.asm"
            reconstructed = {}
            for line in path.read_text().splitlines():
                match = re.search(r"; \$([0-9A-F]{4}): (.*)$", line)
                if match:
                    address = int(match[1], 16)
                    values = re.findall(r"\$([0-9A-F]{2})(?![0-9A-F])", match[2])
                    reconstructed.update({address + i: int(value, 16) for i, value in enumerate(values)})
            banks[bank] = reconstructed
        data = bytes(banks[bank][address] for address in range(start, end))
        raw = rom[offset(bank, start):offset(bank, end)]
        if data != raw:
            raise ValueError(f"mgbdis bytes disagree at {bank:02X}:{start:04X}")
        reports.append(dict(bank=bank, start=start, end_exclusive=end,
                            purpose=purpose, sha256=sha256(raw).hexdigest()))
    return reports


def verify_native_gate(rom):
    from pyboy import PyBoy
    with tempfile.TemporaryDirectory(prefix="shiren-monster-rate-") as directory:
        path = Path(directory) / "original.gbc"
        path.write_bytes(rom)
        gb = PyBoy(str(path), window="null", ram_file=io.BytesIO(bytes(0x8000)), sound_emulated=False)
        try:
            gb.set_emulation_speed(0)
            gb.tick(120, False)
            # Control the RNG byte just before the native comparison. The FF
            # shortcut must work without reaching this hook at all.
            def force_roll(_):
                gb.register_file.A = gb.memory[0xC7F1]
            gb.hook_register(0, 0x1940, force_roll, None)
            counts = []
            for threshold in range(256):
                # WRAM harness: preserve B=threshold/C=roll across the native
                # call; store the resulting carry for all 256 byte values.
                code = bytearray.fromhex(
                    "F3 06 00 0E 00 79 EA F1 C7 C5 58 CD 39 19 C1 "
                    "3E 00 CE 00 26 C8 69 77 0C 20 EB 3E 42 EA FF C7 18 FE"
                )
                code[2] = threshold
                gb.memory[0xC700:0xC700 + len(code)] = code
                gb.memory[0xC7FF] = 0
                gb.memory[0xFFFF] = 0
                gb.memory[0xFF0F] = 0
                gb.register_file.SP = 0xC6F0
                gb.register_file.PC = 0xC700
                gb.tick(2, False)
                actual = list(gb.memory[0xC800:0xC900])
                expected = [int(threshold == 255 or roll < threshold) for roll in range(256)]
                if gb.memory[0xC7FF] != 0x42 or actual != expected:
                    raise ValueError(f"native probability helper failed for threshold {threshold}")
                counts.append(sum(actual))
        finally:
            gb.stop(save=False)
    return dict(comparisons=65536, passed=True, success_counts_by_threshold=counts,
                method="original 00:1939 in PyBoy; RNG byte controlled at 00:1940")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument("--mgbdis", type=Path, default=ROOT / "build/mgbdis")
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build/monster-special-rates")
    parser.add_argument("--emulator", action="store_true", help="also exhaust the native probability helper in PyBoy")
    parser.add_argument("--check-doc", action="store_true", help="check the tracked English table against the ROM")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if sha1(rom).hexdigest() != SOURCE_SHA1:
        raise ValueError("unsupported original ROM SHA-1")
    entries = read_entries(rom)
    report = dict(source_sha1=SOURCE_SHA1, address_notation="hexadecimal bank:CPU address",
                  entries=entries, mgbdis_spans=verify_mgbdis(rom, args.mgbdis), comparisons=[])
    for path in args.compare:
        candidate = path.read_bytes()
        for bank, start, end, purpose in SPANS:
            span = slice(offset(bank, start), offset(bank, end))
            if rom[span] != candidate[span]:
                raise ValueError(f"{path}: changed {purpose} at {bank:02X}:{start:04X}")
        report["comparisons"].append(dict(file=str(path), sha256=sha256(candidate).hexdigest(), matched=True))
    if args.emulator:
        report["native_gate"] = verify_native_gate(rom)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    with (args.out_dir / "rates.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(entries[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(entries)
    lines = ["| Monster | Tier | Stored base chance | Byte | ROM address | Rule |",
             "|---|---:|---:|---|---|---|"]
    for entry in entries:
        lines.append("| {name} | {tier} | {base_chance} | `{threshold_hex}` | `{address}` | {rule} |".format(**entry))
    table = "\n".join(lines) + "\n"
    (args.out_dir / "rates.md").write_text(table, encoding="utf-8")
    if args.check_doc:
        document = (ROOT / "docs/MONSTER_SPECIAL_MOVE_RATES.md").read_text(encoding="utf-8")
        match = re.search(
            r"<!-- BEGIN GENERATED MONSTER RATES -->\n(.*?)<!-- END GENERATED MONSTER RATES -->",
            document, re.DOTALL,
        )
        if not match or match[1].strip() != table.strip():
            raise ValueError("document table is missing or differs from the ROM-derived English table")
    print(f"Verified {len(entries)} Notebook forms against {len(SPANS)} mgbdis spans.")
    print(f"Matched {len(args.compare)} comparison ROMs; artifacts: {args.out_dir}")
    if args.emulator:
        print("PASS all 65,536 native threshold/roll combinations.")
    if args.check_doc:
        print("PASS tracked English table matches all 209 ROM entries.")


if __name__ == "__main__":
    main()
