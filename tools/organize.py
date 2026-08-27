#!/usr/bin/env python3
"""Partition GB2's extracted script into translator-facing TSV files.

The authoritative extractor owns stable record IDs and source metadata.  This
module adds a second, deterministic layer: every logical group/index reference
is assigned by an evidence-backed semantic rule, then every physical record is
written to exactly one category file.  Unknown rules, overlapping rules, or a
record aliased across categories go to an explicit review bucket rather than
silently inheriting a guessed classification.

Generated files contain extracted game text and belong under the ignored
``script/organized`` directory.  The tracked fixture freezes only counts and
hashes.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import extract


SCHEMA = "shiren-gb2-script-organization-v1"


@dataclass(frozen=True)
class Category:
    name: str
    filename: str
    description: str


@dataclass(frozen=True)
class ReferenceRule:
    category: str
    section: str
    first_group: int
    last_group: int
    first_index: int = 0
    last_index: int = 0xFF

    def matches(self, reference):
        return (
            self.first_group <= reference.group <= self.last_group
            and self.first_index <= reference.index <= self.last_index
        )


@dataclass(frozen=True)
class OrganizedRecord:
    record: extract.Record
    category: str
    sections: tuple
    review_reasons: tuple


CATEGORIES = (
    Category(
        "glossary",
        "glossary.tsv",
        "canonical names, appearances, abilities, traps and locations",
    ),
    Category("items", "items.tsv", "identified item descriptions"),
    Category(
        "monsters",
        "monsters.tsv",
        "Monster Notebook and monster-meat descriptions",
    ),
    Category(
        "ui_system",
        "ui_system.tsv",
        "menus, labels, status, ranking and other positioned system text",
    ),
    Category("help", "help.tsv", "Wanderer's Guide, controls and technique help"),
    Category(
        "messages",
        "messages.tsv",
        "combat, dungeon, item-action and runtime gameplay messages",
    ),
    Category("prose", "prose.tsv", "story, event and character dialogue"),
    Category(
        "internal",
        "internal.tsv",
        "debug, scenario, password, animation and engine-facing labels",
    ),
    Category(
        "review",
        "review.tsv",
        "unclassified, ambiguous or cross-category aliases requiring review",
    ),
)


# Rules describe logical references rather than ROM locations.  Broad group
# ranges are intentional only where the full pointer group has one proven
# semantic role.  Group 24 is split because it mixes locations with positioned
# UI records; group 17 keeps its no-traps status separate from actual names.
REFERENCE_RULES = (
    ReferenceRule("internal", "debug_and_engine_labels", 0, 0),
    ReferenceRule("glossary", "actor_names_tier_1", 1, 1),
    ReferenceRule("glossary", "actor_names_tier_2", 2, 2),
    ReferenceRule("glossary", "actor_names_tier_3", 3, 3),
    ReferenceRule("glossary", "identified_item_names", 4, 4),
    ReferenceRule("glossary", "unidentified_item_appearances", 5, 5),
    ReferenceRule("items", "item_descriptions", 6, 6),
    ReferenceRule("ui_system", "menus_and_system_labels", 7, 7),
    ReferenceRule("messages", "combat_and_dungeon_messages", 8, 8),
    ReferenceRule("prose", "ending_and_credits_text", 9, 9),
    ReferenceRule("messages", "floor_and_system_messages", 10, 10),
    ReferenceRule("messages", "item_and_action_messages", 11, 11),
    ReferenceRule("glossary", "item_ability_roots", 12, 12),
    ReferenceRule("internal", "debug_spell_labels", 13, 13),
    ReferenceRule("internal", "scenario_labels", 14, 14),
    ReferenceRule("glossary", "item_ability_descriptions", 15, 15),
    ReferenceRule("ui_system", "adventure_history_labels", 16, 16),
    ReferenceRule("ui_system", "trap_menu_status", 17, 17, 0, 0),
    ReferenceRule("glossary", "trap_names", 17, 17, 1, 22),
    ReferenceRule("ui_system", "ranking_outcomes_and_labels", 18, 18),
    ReferenceRule("help", "wanderers_guide", 19, 19),
    ReferenceRule("help", "control_help", 20, 20),
    ReferenceRule("help", "technique_help", 21, 21),
    ReferenceRule("ui_system", "ranking_titles_and_grade_labels", 22, 22),
    ReferenceRule("internal", "password_fragments", 23, 23),
    ReferenceRule("ui_system", "adventure_and_miscellaneous_ui", 24, 24, 0, 0),
    ReferenceRule("glossary", "location_names", 24, 24, 1, 14),
    ReferenceRule("ui_system", "dynamic_status_fields", 24, 24, 15, 18),
    ReferenceRule("glossary", "location_names", 24, 24, 19, 48),
    ReferenceRule("ui_system", "adventure_and_miscellaneous_ui", 24, 24, 49, 66),
    ReferenceRule("internal", "animation_and_effect_labels", 25, 27),
    ReferenceRule("ui_system", "condition_labels", 28, 28),
    ReferenceRule("monsters", "monster_notebook_descriptions", 29, 31),
    ReferenceRule("help", "wanderer_secret_pages", 32, 32),
    ReferenceRule("prose", "story_and_event_dialogue", 33, 112),
    ReferenceRule("monsters", "monster_meat_descriptions", 113, 115),
    ReferenceRule("glossary", "numbered_monster_variant_names", 116, 124),
    ReferenceRule("internal", "internal_object_labels", 125, 125),
)


def _rules_sha1():
    payload = [
        {
            "category": rule.category,
            "section": rule.section,
            "group_range": [rule.first_group, rule.last_group],
            "index_range": [rule.first_index, rule.last_index],
        }
        for rule in REFERENCE_RULES
    ]
    return sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _reference_label(reference):
    return "g%03d[%03d]@%s" % (
        reference.group,
        reference.index,
        extract.location(
            reference.table_bank, extract.cpu_address(reference.pointer_offset)
        ),
    )


def classify(result):
    """Return a complete, single-owner partition of extracted records."""
    categories = {category.name for category in CATEGORIES}
    rule_categories = {rule.category for rule in REFERENCE_RULES}
    if "review" in rule_categories or rule_categories - categories:
        raise extract.ExtractError("invalid script organization category rules")

    out = []
    for record in result["records"]:
        assignments = []
        reasons = []
        for reference in record.references:
            matches = [rule for rule in REFERENCE_RULES if rule.matches(reference)]
            if len(matches) != 1:
                kind = "unclassified_reference" if not matches else "ambiguous_reference"
                reasons.append("%s:%d:%d" % (kind, reference.group, reference.index))
                continue
            assignments.append((matches[0].category, matches[0].section))

        record_categories = {category for category, _section in assignments}
        if reasons:
            category = "review"
        elif len(record_categories) != 1:
            category = "review"
            reasons.append(
                "cross_category_alias:%s"
                % ",".join(sorted(record_categories or {"none"}))
            )
        else:
            category = next(iter(record_categories))

        sections = tuple(sorted({section for _category, section in assignments}))
        if category == "review" and not sections:
            sections = ("unclassified",)
        out.append(
            OrganizedRecord(
                record=record,
                category=category,
                sections=sections,
                review_reasons=tuple(sorted(reasons)),
            )
        )

    if len(out) != len(result["records"]):
        raise extract.ExtractError("script organization dropped a record")
    if len({row.record.id for row in out}) != len(out):
        raise extract.ExtractError("script organization duplicated a record")
    return tuple(out)


def summary(result, organized=None):
    """Return the redistributable classification census and fingerprints."""
    organized = classify(result) if organized is None else tuple(organized)
    by_category = {category.name: [] for category in CATEGORIES}
    for row in organized:
        by_category[row.category].append(row)

    reference_states = Counter()
    for record in result["records"]:
        for reference in record.references:
            count = sum(rule.matches(reference) for rule in REFERENCE_RULES)
            if count == 0:
                reference_states["unclassified"] += 1
            elif count == 1:
                reference_states["assigned_once"] += 1
            else:
                reference_states["ambiguous"] += 1

    category_rows = []
    partition_digest = sha1()
    for category in CATEGORIES:
        rows = by_category[category.name]
        digest = sha1()
        sections = Counter()
        review_reasons = Counter()
        for row in rows:
            section_text = ";".join(row.sections)
            digest.update(row.record.id.encode("ascii"))
            digest.update(b"\0")
            digest.update(section_text.encode("ascii"))
            digest.update(b"\0")
            partition_digest.update(category.name.encode("ascii"))
            partition_digest.update(b"\0")
            partition_digest.update(row.record.id.encode("ascii"))
            partition_digest.update(b"\0")
            for section in row.sections:
                sections[section] += 1
            for reason in row.review_reasons:
                review_reasons[reason.split(":", 1)[0]] += 1
        category_rows.append(
            {
                "name": category.name,
                "filename": category.filename,
                "description": category.description,
                "records": len(rows),
                "nonempty_records": sum(bool(row.record.raw) for row in rows),
                "logical_references": sum(
                    len(row.record.references) for row in rows
                ),
                "source_bytes": sum(len(row.record.raw) for row in rows),
                "sections": dict(sorted(sections.items())),
                "review_reasons": dict(sorted(review_reasons.items())),
                "assignment_sha1": digest.hexdigest(),
            }
        )

    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "rules_sha1": _rules_sha1(),
        "records": len(organized),
        "logical_references": len(result["references"]),
        "reference_coverage": {
            "assigned_once": reference_states["assigned_once"],
            "unclassified": reference_states["unclassified"],
            "ambiguous": reference_states["ambiguous"],
        },
        "partition_complete": (
            len(organized) == len(result["records"])
            and len({row.record.id for row in organized}) == len(organized)
        ),
        "review_records": len(by_category["review"]),
        "partition_sha1": partition_digest.hexdigest(),
        "categories": category_rows,
    }


def read_existing_english(output_dir, result):
    """Load existing category cells while rejecting stale or duplicate rows."""
    by_id = {record.id: record for record in result["records"]}
    english = {}
    owners = {}
    for category in CATEGORIES:
        path = output_dir / category.filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fields = set(reader.fieldnames or ())
            missing = {"id", "english"} - fields
            if missing:
                raise extract.ExtractError(
                    "%s is missing required column(s): %s"
                    % (path, ", ".join(sorted(missing)))
                )
            for line_number, row in enumerate(reader, 2):
                if None in row or row.get("id") is None or row.get("english") is None:
                    raise extract.ExtractError(
                        "%s:%d has the wrong number of TSV columns"
                        % (path, line_number)
                    )
                record_id = row["id"]
                if not record_id or record_id.startswith("#"):
                    continue
                if record_id in owners:
                    raise extract.ExtractError(
                        "%s:%d duplicates record ID %s from %s"
                        % (path, line_number, record_id, owners[record_id])
                    )
                try:
                    record = by_id[record_id]
                except KeyError:
                    raise extract.ExtractError(
                        "%s:%d names stale record ID %s"
                        % (path, line_number, record_id)
                    ) from None
                if row.get("length") and int(row["length"]) != len(record.raw):
                    raise extract.ExtractError(
                        "%s:%d source length changed for %s"
                        % (path, line_number, record_id)
                    )
                if row.get("original_hex") and (
                    row["original_hex"].upper() != record.raw.hex().upper()
                ):
                    raise extract.ExtractError(
                        "%s:%d original bytes changed for %s"
                        % (path, line_number, record_id)
                    )
                if row.get("japanese") and row["japanese"] != record.source:
                    raise extract.ExtractError(
                        "%s:%d Japanese source changed for %s"
                        % (path, line_number, record_id)
                    )
                owners[record_id] = path
                english[record_id] = row["english"]
    return english


def _write_tsv(path, rows, english):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            (
                "id",
                "sections",
                "length",
                "original_hex",
                "references",
                "interior_of",
                "review_reasons",
                "japanese",
                "english",
            )
        )
        for row in rows:
            record = row.record
            writer.writerow(
                (
                    record.id,
                    ";".join(row.sections),
                    len(record.raw),
                    record.raw.hex().upper(),
                    ";".join(_reference_label(ref) for ref in record.references),
                    record.interior_of,
                    ";".join(row.review_reasons),
                    record.source,
                    english.get(record.id, ""),
                )
            )


def write_outputs(result, output_dir, english_by_id=None):
    """Write all category TSVs plus a deterministic manifest.

    Without ``english_by_id``, existing English cells are preserved in place.
    A supplied mapping is authoritative and is used by the compact-overlay
    synchronizer after it has resolved both workspaces without conflicts.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = read_existing_english(output_dir, result)
    if english_by_id is None:
        english = existing
    else:
        by_id = {record.id for record in result["records"]}
        unknown = sorted(set(english_by_id) - by_id)
        if unknown:
            raise extract.ExtractError(
                "English mapping names stale record ID %s" % unknown[0]
            )
        english = dict(english_by_id)
    organized = classify(result)
    by_category = {category.name: [] for category in CATEGORIES}
    for row in organized:
        by_category[row.category].append(row)

    paths = []
    for category in CATEGORIES:
        path = output_dir / category.filename
        _write_tsv(path, by_category[category.name], english)
        paths.append(path)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(summary(result, organized=organized), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    paths.append(manifest_path)
    return tuple(paths)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--out",
        default="script/organized",
        help="output directory (default: script/organized)",
    )
    args = parser.parse_args(argv)
    try:
        result = extract.extract(Path(args.rom).read_bytes())
        paths = write_outputs(result, args.out)
        measured = summary(result)
    except (OSError, ValueError, extract.ExtractError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    print(
        "%d records / %d references -> %d categories; %d review"
        % (
            measured["records"],
            measured["logical_references"],
            len(measured["categories"]),
            measured["review_records"],
        )
    )
    for category in measured["categories"]:
        print("%-14s %4d  %s" % (
            category["name"], category["records"], category["filename"]
        ))
    print("manifest      %s" % paths[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
