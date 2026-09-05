#!/usr/bin/env python3
"""Audit the player-facing boundary of GB2's internal text directory.

Big Moai's runtime four-byte promotional gift-code table (called "spells" by
the game), its matching diagnostic labels, and group 125's twelve runtime room
labels need English bytes. The room labels are composed into the visible
``It's <room>!`` dungeon alert. This system is independent of Wanderer Rescue.
The remaining records are developer selectors or engine dispatch names;
relocating them would add no player-facing coverage and would weaken the native
identity contracts used while reverse engineering.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import extract
import organize
import translations


SCHEMA = "shiren-gb2-internal-text-audit-v1"
POLICIES = (
    ("runtime_spell_codes", 23, 0, 99, True),
    ("debug_spell_codes", 13, 127, 226, True),
    ("developer_event_selectors", 13, 0, 126, False),
    ("debug_and_engine_labels", 0, 0, 255, False),
    ("scenario_debug_labels", 14, 0, 255, False),
    ("animation_effect_dispatch", (25, 26, 27), 0, 255, False),
    ("internal_object_null", 125, 0, 0, False),
    ("runtime_house_labels", 125, 1, 12, True),
    ("internal_object_ids", 125, 13, 255, False),
)


class InternalAuditError(ValueError):
    """The internal directory no longer matches its reviewed policy."""


def _policy_for(record):
    matches = set()
    for reference in record.references:
        for name, groups, first, last, translate in POLICIES:
            groups = (groups,) if isinstance(groups, int) else groups
            if reference.group in groups and first <= reference.index <= last:
                matches.add((name, translate))
    if len(matches) != 1:
        raise InternalAuditError(
            "%s matches %d internal policies" % (record.id, len(matches))
        )
    return next(iter(matches))


def analyze(result, translated):
    organized = organize.classify(result)
    records = [row.record for row in organized if row.category == "internal"]
    buckets = Counter()
    translated_buckets = Counter()
    required_ids = set()
    native_ids = set()
    for record in records:
        name, should_translate = _policy_for(record)
        buckets[name] += 1
        entry = translated.get((record.bank, record.address))
        authored = entry is not None and bool(entry.text)
        if authored:
            translated_buckets[name] += 1
        if should_translate:
            required_ids.add(record.id)
            if not authored:
                raise InternalAuditError(
                    "required internal runtime record %s is untranslated"
                    % record.id
                )
        else:
            native_ids.add(record.id)
            if entry is not None:
                raise InternalAuditError(
                    "engine-only record %s unexpectedly has an override"
                    % record.id
                )

    if len(records) != len(required_ids) + len(native_ids):
        raise InternalAuditError("internal audit does not partition every record")
    rows = []
    for name, _groups, _first, _last, should_translate in POLICIES:
        rows.append(
            {
                "name": name,
                "records": buckets[name],
                "translated_records": translated_buckets[name],
                "policy": "translate" if should_translate else "retain_native",
            }
        )
    return {
        "schema": SCHEMA,
        "internal_records": len(records),
        "translated_runtime_records": len(required_ids),
        "retained_engine_records": len(native_ids),
        "partition_complete": len(records) == len(required_ids) + len(native_ids),
        "runtime_translation_complete": all(
            row["translated_records"] == row["records"]
            for row in rows
            if row["policy"] == "translate"
        ),
        "policies": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--translations", default="script/en")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rom = Path(args.rom).read_bytes()
        result = extract.extract(rom)
        translated = translations.load_path(args.translations, result["records"])
        measured = analyze(result, translated)
    except (
        OSError,
        ValueError,
        extract.ExtractError,
        translations.TranslationError,
        InternalAuditError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)
    if args.json:
        print(json.dumps(measured, indent=2, sort_keys=True))
    else:
        print(
            "%d internal records: %d runtime-translated, %d engine-native"
            % (
                measured["internal_records"],
                measured["translated_runtime_records"],
                measured["retained_engine_records"],
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
