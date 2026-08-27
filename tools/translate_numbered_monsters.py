#!/usr/bin/env python3
"""Fill the nine numbered robot-name tables used by Zoso's upgrades.

Each table contains the unnumbered base model followed by models 2 through 99.
The English overlays deliberately keep that native convention: no synthetic
``No. 1`` is added to the first record.  This tool only fills blank cells and
uses the rich organized catalog solely to recover the group/index references;
the tracked output remains source-free.
"""
import csv
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "script" / "organized" / "glossary.tsv"
OVERLAY = ROOT / "script" / "en" / "glossary.tsv"

SECTION = "numbered_monster_variant_names"
REFERENCE = re.compile(r"g(1(?:1[6-9]|2[0-4]))\[(\d{3})\]")

# The first three are already frozen actor names elsewhere in the translation.
# The remaining names follow the original power-source progression while
# presenting the wordplay as readable English names.
BASE_NAMES = {
    116: "Zenmaiger",
    117: "Royal Wind",
    118: "Hydro Rover",
    119: "Thermal King",
    120: "Steam Max",
    121: "Diesel Ace",
    122: "Mega Solar",
    123: "Linear Shogun",
    124: "Hybrider Z",
}


def variant_name(group, index):
    """Return the English model name for a zero-based native table index."""
    try:
        base = BASE_NAMES[group]
    except KeyError:
        raise ValueError(f"unsupported numbered robot group {group}") from None
    if not 0 <= index < 99:
        raise ValueError(f"numbered robot index out of range: {index}")
    return base if index == 0 else f"{base} No. {index + 1}"


def catalog_variants(path=CATALOG):
    """Return stable ID -> (group, index), rejecting malformed table coverage."""
    variants = {}
    coverage = {group: set() for group in BASE_NAMES}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["sections"] != SECTION:
                continue
            matches = [
                REFERENCE.search(reference)
                for reference in row["references"].split(";")
            ]
            matches = [match for match in matches if match]
            if len(matches) != 1:
                raise ValueError(
                    f"{row['id']} needs exactly one numbered robot reference"
                )
            group, index = map(int, matches[0].groups())
            if group not in BASE_NAMES:
                raise ValueError(f"{row['id']} has unexpected group {group}")
            if index in coverage[group]:
                raise ValueError(f"group {group} duplicates index {index}")
            coverage[group].add(index)
            variants[row["id"]] = (group, index)

    expected = set(range(99))
    for group, indices in coverage.items():
        if indices != expected:
            missing = sorted(expected - indices)
            extra = sorted(indices - expected)
            raise ValueError(
                f"group {group} coverage mismatch; missing={missing}, extra={extra}"
            )
    if len(variants) != 9 * 99:
        raise ValueError(f"expected 891 numbered robot records, found {len(variants)}")
    return variants


def fill_rows(rows, variants):
    """Fill blank numbered-name rows and return the number changed."""
    changed = 0
    seen = set()
    for row in rows:
        if row["sections"] != SECTION:
            continue
        try:
            group, index = variants[row["id"]]
        except KeyError:
            raise ValueError(f"overlay has unknown numbered robot ID {row['id']}") from None
        seen.add(row["id"])
        if not row["english"]:
            row["english"] = variant_name(group, index)
            changed += 1
    missing = sorted(set(variants) - seen)
    if missing:
        raise ValueError(f"overlay is missing numbered robot ID {missing[0]}")
    return changed


def main():
    variants = catalog_variants()
    with OVERLAY.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    changed = fill_rows(rows, variants)
    with OVERLAY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"translated {changed} blank numbered robot records")


if __name__ == "__main__":
    main()
