#!/usr/bin/env python3
"""Synchronize Big Moai's 100 native four-byte promotional gift codes.

Group 23 is the runtime comparison table.  Group 13 indices 127..226 are the
matching developer/debug labels.  The first 93 codes remain deliberately
neutral, while the seven codes taught as "spells" in story dialogue receive
memorable four-letter equivalents that fit the native input buffer.  These
reward codes are independent of Wanderer Rescue passwords.
"""
import csv
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "script" / "organized" / "internal.tsv"
OVERLAY = ROOT / "script" / "en" / "internal.tsv"

REFERENCE = re.compile(r"g(013|023)\[(\d{3})\]")
STORY_CODES = {
    93: "WISH",
    94: "RANU",
    95: "BADE",
    96: "SUGI",
    97: "TSUB",
    98: "MAMA",
    99: "HOYO",
}


def spell_code(index):
    if not 0 <= index < 100:
        raise ValueError(f"spell index out of range: {index}")
    return STORY_CODES.get(index, f"S{index + 1:03d}")


def catalog_targets(path=CATALOG):
    """Return stable ID -> English for the runtime and matching debug tables."""
    targets = {}
    runtime_coverage = set()
    debug_coverage = set()
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            matches = [
                REFERENCE.search(reference)
                for reference in row["references"].split(";")
            ]
            matches = [match for match in matches if match]
            for match in matches:
                group, native_index = int(match.group(1)), int(match.group(2))
                if group == 23:
                    index = native_index
                    runtime_coverage.add(index)
                    targets[row["id"]] = spell_code(index)
                elif 127 <= native_index <= 226:
                    index = native_index - 127
                    debug_coverage.add(index)
                    targets[row["id"]] = f"Spell {index + 1}: {spell_code(index)}"

    expected = set(range(100))
    if runtime_coverage != expected:
        raise ValueError("runtime spell table is not a complete 0..99 sequence")
    if debug_coverage != expected:
        raise ValueError("debug spell table is not a complete 0..99 sequence")
    if len(targets) != 200:
        raise ValueError(f"expected 200 spell records, found {len(targets)}")
    return targets


def fill_rows(rows, targets):
    changed = 0
    seen = set()
    for row in rows:
        if row["id"] not in targets:
            continue
        seen.add(row["id"])
        if not row["english"]:
            row["english"] = targets[row["id"]]
            changed += 1
    missing = sorted(set(targets) - seen)
    if missing:
        raise ValueError(f"internal overlay is missing spell ID {missing[0]}")
    return changed


def main():
    targets = catalog_targets()
    with OVERLAY.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    changed = fill_rows(rows, targets)
    with OVERLAY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"translated {changed} blank spell records")


if __name__ == "__main__":
    main()
