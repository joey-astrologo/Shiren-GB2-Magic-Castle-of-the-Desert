#!/usr/bin/env python3
"""Read-only audit of GB2 equipment abilities and rescue reward eligibility.

This checks definitions and reward tables, not every ability's combat behavior.
Generated evidence stays under build/. No ROM or save is modified.
"""
import argparse
import csv
from hashlib import sha1, sha256
import json
from pathlib import Path
import re

import extract

ROOT = Path(__file__).resolve().parents[1]
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
# Hexadecimal banks and CPU addresses; ends are exclusive.
SPANS = (
    (0x04, 0x53B5, 0x5567, "rescue generation, capacity guard, and weighted selection"),
    (0x04, 0x5567, 0x5E37, "all rescue tier, count, and status/ability tables"),
    (0x11, 0x4C2F, 0x4CAA, "ability display and family mapping"),
    (0x77, 0x552E, 0x55AC, "item definition pointers 0 through 62"),
    (0x77, 0x56BE, 0x5A9E, "all 62 sword/shield definitions"),
    (0x77, 0x6113, 0x6124, "item definition lookup"),
    (0x78, 0x467B, 0x469E, "object ability bitset getter"),
    (0x78, 0x46D2, 0x4740, "inherent ability getter and exclusion from added abilities"),
    (0x7A, 0x42C9, 0x42D6, "set doubled capacity flag"),
    (0x7A, 0x47FF, 0x4823, "constructor copies inherent abilities"),
    (0x7A, 0x4954, 0x4991, "capacity lookup and doubling"),
    (0x7A, 0x4A04, 0x4A97, "synthesis ability merge and random overflow removal"),
    (0x7A, 0x4AF7, 0x4B31, "ability counting and selected-bit lookup"),
)
DUNGEONS = {
    1: ("Castle Dungeon", 6), 2: ("Ancient Ruins", 8),
    3: ("Castle Tower", 15), 4: ("Castle Keep", 20),
    5: ("Jahannam's Gate", 25), 6: ("Abyssal Depths", 98),
    7: ("Tonfan's Hole", 98), 8: ("Wanado", 98),
    9: ("Smith's Forge", 98), 10: ("Pot Cave", 99),
}


def raw(rom, bank, address, count):
    at = extract.file_offset(bank, address)
    return rom[at:at + count]


def pointer(rom, bank, address):
    return int.from_bytes(raw(rom, bank, address, 2), "little")


def verify_spans(rom, directory, comparisons):
    decoded = {}
    evidence = []
    for bank, start, end, purpose in SPANS:
        if bank not in decoded:
            decoded[bank] = {}
            for line in (directory / f"bank_{bank:03x}.asm").read_text().splitlines():
                match = re.search(r"; \$([0-9A-F]{4}): (.*)$", line)
                if match:
                    values = re.findall(r"\$([0-9A-F]{2})(?![0-9A-F])", match[2])
                    decoded[bank].update({int(match[1], 16) + i: int(v, 16)
                                          for i, v in enumerate(values)})
        data = raw(rom, bank, start, end - start)
        if bytes(decoded[bank][a] for a in range(start, end)) != data:
            raise ValueError(f"mgbdis bytes differ at {bank:02X}:{start:04X}")
        evidence.append(dict(address=f"{bank:02X}:{start:04X}",
                             end_exclusive=f"{end:04X}", purpose=purpose,
                             sha256=sha256(data).hexdigest()))
    compared = []
    for path in comparisons:
        candidate = path.read_bytes()
        for bank, start, end, purpose in SPANS:
            if raw(candidate, bank, start, end - start) != raw(rom, bank, start, end - start):
                raise ValueError(f"{path}: changed {purpose}")
        compared.append(dict(path=str(path), sha256=sha256(candidate).hexdigest()))
    return evidence, compared


def ranges(values):
    result = []
    for value in values:
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def audit(rom):
    with (ROOT / "script/en/glossary.tsv").open() as stream:
        english = {row["id"]: row["english"] for row in csv.DictReader(stream, delimiter="\t")}
    directory = extract.read_directory(rom)

    def group(number):
        return {ref.index: english[extract.location(ref.target_bank, ref.target_address)]
                for ref in extract.read_table(rom, directory[number])}

    names, descriptions = group(4), group(15)
    items = []
    for item_id in range(1, 63):
        address = pointer(rom, 0x77, 0x552E + 2 * item_id)
        data = raw(rom, 0x77, address, 16)
        mask = int.from_bytes(data[8:11], "little")
        items.append(dict(item_id=item_id, name=names[item_id],
                          family="weapon" if item_id <= 33 else "shield",
                          address=f"77:{address:04X}", mask=f"{mask:06X}",
                          bits=[b for b in range(24) if mask & (1 << b)],
                          capacity=data[11]))
    tiers = []
    for tier in range(20):
        address = pointer(rom, 4, 0x55A1 + tier * 2)
        counts = pointer(rom, 4, 0x5579 + tier * 2)
        tiers.append(dict(tier=tier, address=f"04:{address:04X}",
                          weights=[list(raw(rom, 4, address + family * 32, 32))
                                   for family in range(3)],
                          attempts=[list(raw(rom, 4, counts + family * 2, 2))
                                    for family in range(3)]))
    floor_tiers = {}
    for dungeon, (name, last) in DUNGEONS.items():
        address = pointer(rom, 4, 0x5567 + 2 * max(0, dungeon - 2))
        floor_tiers[name] = {floor: raw(rom, 4, address + floor // 5, 1)[0]
                             for floor in range(1, last + 1)}
    rows = []
    for family_id, (family, first, count) in enumerate((("weapon", 0, 22), ("shield", 22, 23))):
        for bit in range(count):
            eligible = {}
            for name, floors in floor_tiers.items():
                eligible[name] = ranges([floor for floor, tier in floors.items()
                                         if tiers[tier]["weights"][family_id][bit + 8]
                                         and tiers[tier]["attempts"][family_id][1]])
            donors = [item["name"] for item in items
                      if item["family"] == family and bit in item["bits"]]
            rows.append(dict(key=f"{'W' if family_id == 0 else 'S'}{bit:02d}",
                             family=family, bit=bit,
                             description=descriptions[first + bit].removeprefix("<EC>"),
                             donors=donors, rescue_floor_ranges=eligible))
    unused = [row["key"] for row in rows
              if not row["donors"] and not any(row["rescue_floor_ranges"].values())]
    if unused != ["W06", "S05", "S06", "S07", "S22"]:
        raise ValueError(f"unexpected unassigned abilities: {unused}")
    return dict(items=items, abilities=rows, rescue_tiers=tiers,
                floor_tiers=floor_tiers, unassigned=unused)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / ROM_NAME)
    parser.add_argument("--mgbdis", type=Path, default=ROOT / "build/mgbdis")
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--check-doc", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/equipment-seals/audit.json")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise ValueError("unexpected source ROM SHA-1")
    evidence, comparisons = verify_spans(rom, args.mgbdis, args.compare)
    report = audit(rom)
    if args.check_doc:
        doc = (ROOT / "docs/EQUIPMENT_SEALS.md").read_text()
        keys = re.findall(r"^\| ([WS]\d{2}) \|", doc, re.M)
        if sorted(keys) != sorted(row["key"] for row in report["abilities"]):
            raise ValueError("document must list every ability exactly once")
        for row in report["abilities"]:
            line = next(line for line in doc.splitlines() if line.startswith(f'| {row["key"]} |'))
            if not all(name in line for name in row["donors"]):
                raise ValueError(f'{row["key"]}: document donor mismatch')
            if row["key"] not in report["unassigned"]:
                routes = line.split("|")[4].strip().split("; ")
                for route in routes:
                    match = re.fullmatch(r"(.+) (\d+)–(\d+)", route)
                    if not match:
                        raise ValueError(f'{row["key"]}: unrecognized rescue route: {route}')
                    dungeon_text, first, last = match.groups()
                    for dungeon in dungeon_text.split(" or "):
                        dungeon = "Abyssal Depths" if dungeon == "AD" else dungeon
                        eligible = row["rescue_floor_ranges"][dungeon]
                        if not any(low <= int(first) <= int(last) <= high for low, high in eligible):
                            raise ValueError(f'{row["key"]}: ineligible rescue route: {route}')
    report.update(source_rom_sha1=extract.ROM_SHA1, spans=evidence, comparisons=comparisons,
                  scope="Static definitions and reward tables; not a combat or full-playthrough test.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {len(evidence)} mgbdis spans; {len(comparisons)} comparison ROMs match.")
    print("PASS 62 definitions, 45 descriptions, 20 rescue tiers; 5 unassigned entries.")
    print(f"Evidence: {args.output}")


if __name__ == "__main__":
    main()
