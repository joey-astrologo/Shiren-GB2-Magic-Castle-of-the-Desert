#!/usr/bin/env python3
"""Audit every translated action-menu label against its actual pixel budget.

GB2 has three distinct action-menu paths: fixed item commands, the dedicated
stairs overlay, and event-script choice popups.  The last path was previously
covered only by individually discovered save states.  Native event opcode $1E
has a fixed 13-byte record, so every choice set can instead be found directly
in the ROM and measured without reaching its story state in play.
"""
import argparse
from collections import OrderedDict
from hashlib import sha1
import json
from pathlib import Path
import sys

import english
import english_font
import extract
import layout
import service_menus
import stairs_menu
import surfaces
import translations


SCHEMA = "shiren-gb2-menu-action-audit-v1"
EVENT_CHOICE_OPCODE = 0x1E
EVENT_CHOICE_BYTES = 13
EVENT_CHOICE_SLOTS = 5
EVENT_CHOICE_GROUP = 7
RELEASE_EVENT_BANKS = frozenset((116, 117))
DEVELOPER_EVENT_BANKS = frozenset((180,))

ITEM_ACTION_INDICES = tuple(range(1, 25))
ITEM_ACTION_TEXT_BUDGET = 48
EVENT_NATIVE_INTERIOR_COLUMNS = service_menus.NATIVE_INTERIOR_COLUMNS
EVENT_WIDE_INTERIOR_COLUMNS = service_menus.ENGLISH_INTERIOR_COLUMNS
EVENT_TEXT_START_PIXELS = service_menus.TEXT_START_X
EVENT_NATIVE_TEXT_BUDGET = (
    EVENT_NATIVE_INTERIOR_COLUMNS * service_menus.TILE_PIXELS
    - EVENT_TEXT_START_PIXELS
)
EVENT_WIDE_TEXT_BUDGET = (
    EVENT_WIDE_INTERIOR_COLUMNS * service_menus.TILE_PIXELS
    - EVENT_TEXT_START_PIXELS
)

# These are review decisions, not automatic rewrites.  Candidate wording is
# measured by the same renderer as the installed translations below so the
# report can separate concise-label decisions from genuine geometry work.
RELEASE_MENU_REVIEWS = {
    ((7, 128), (7, 127), (7, 146), (7, 158)): {
        "context": "Rescue Team completed-rescue delivery",
        "recommended_action": "approved_geometry",
    },
    ((7, 136), (7, 137), (7, 145), (7, 158)): {
        "context": "Rescue Team rescued-player item prompt",
        "recommended_action": "approved_wording",
    },
    ((7, 153), (7, 15), (7, 135)): {
        "context": "Training House training menu",
        "recommended_action": "approved_wording",
    },
    ((7, 111), (7, 112), (7, 135)): {
        "context": "Training House dungeon-data exchange",
        "recommended_action": "approved_wording",
    },
    ((7, 160), (7, 161), (7, 162), (7, 135)): {
        "context": "Pigeon Handler password explanations",
        "recommended_action": "approved_wording",
    },
}


class MenuActionAuditError(ValueError):
    """The event-choice encoding or audited menu scope changed."""


def _record_map(result):
    return {
        (reference.group, reference.index): record
        for record in result["records"]
        for reference in record.references
    }


def _translated_label(reference, records, translated, font_rom):
    record = records[reference]
    translation = translated.get((record.bank, record.address))
    raw = translation.encoded if translation is not None else record.raw
    text = translation.text if translation is not None else record.source
    measured = layout.direct_layout(
        font_rom, raw, start_x=EVENT_TEXT_START_PIXELS, start_y=1
    )
    if measured.auto_wraps or measured.final_y != 1:
        raise MenuActionAuditError(
            "%s wraps the direct menu renderer" % record.id
        )
    return {
        "group": reference[0],
        "index": reference[1],
        "reference": list(reference),
        "record": record.id,
        "text": text,
        "translated": translation is not None,
        "renderer_pixels": measured.rightmost_pen - measured.start_x,
    }


def _event_choice_candidates(rom, records):
    """Return every literal group-7 event-choice record in file order."""
    rom = bytes(rom)
    out = []
    for offset in range(len(rom) - EVENT_CHOICE_BYTES + 1):
        if rom[offset] != EVENT_CHOICE_OPCODE:
            continue
        count = rom[offset + 1]
        selected = rom[offset + 2]
        if not 1 <= count <= EVENT_CHOICE_SLOTS or selected >= count:
            continue
        references = tuple(
            (rom[offset + 4 + slot * 2], rom[offset + 3 + slot * 2])
            for slot in range(count)
        )
        padding = rom[
            offset + 3 + count * 2:offset + EVENT_CHOICE_BYTES
        ]
        if any(padding):
            continue
        if not all(
            reference[0] == EVENT_CHOICE_GROUP and reference in records
            for reference in references
        ):
            continue
        bank = offset // extract.BANK_SIZE
        out.append({
            "offset": offset,
            "bank": bank,
            "location": extract.location(bank, extract.cpu_address(offset)),
            "selected": selected,
            "references": references,
            "raw": rom[offset:offset + EVENT_CHOICE_BYTES],
        })
    return tuple(out)


def _widened_event_sets():
    return frozenset(
        tuple((group, index) for index, group in records)
        for records in service_menus.SERVICE_RECORD_SETS
    )


def _menu_set_rows(candidates, records, translated, font_rom):
    grouped = OrderedDict()
    for candidate in candidates:
        grouped.setdefault(candidate["references"], []).append(candidate)

    widened = _widened_event_sets()
    rows = []
    for references, occurrences in grouped.items():
        labels = [
            _translated_label(reference, records, translated, font_rom)
            for reference in references
        ]
        is_widened = references in widened
        budget = (
            EVENT_WIDE_TEXT_BUDGET if is_widened
            else EVENT_NATIVE_TEXT_BUDGET
        )
        for label in labels:
            label["clearance_pixels"] = budget - label["renderer_pixels"]
        overflow = [
            label for label in labels if label["renderer_pixels"] > budget
        ]
        widest = max(labels, key=lambda label: label["renderer_pixels"])
        required_interior = (
            EVENT_TEXT_START_PIXELS + widest["renderer_pixels"]
            + service_menus.TILE_PIXELS - 1
        ) // service_menus.TILE_PIXELS
        review = RELEASE_MENU_REVIEWS.get(references, {})
        wording_candidates = []
        for text in review.get("candidate_text", ()):
            encoded = english.encode_source(text)
            measured = layout.direct_layout(
                font_rom,
                encoded,
                start_x=EVENT_TEXT_START_PIXELS,
                start_y=1,
            )
            pixels = measured.rightmost_pen - measured.start_x
            wording_candidates.append({
                "text": text,
                "renderer_pixels": pixels,
                "fits_native": pixels <= EVENT_NATIVE_TEXT_BUDGET,
            })
        rows.append({
            "name": " / ".join(label["text"] for label in labels),
            "references": [list(reference) for reference in references],
            "locations": [item["location"] for item in occurrences],
            "occurrences": len(occurrences),
            "geometry": "widened" if is_widened else "native",
            "interior_columns": (
                EVENT_WIDE_INTERIOR_COLUMNS if is_widened
                else EVENT_NATIVE_INTERIOR_COLUMNS
            ),
            "text_start_pixels": EVENT_TEXT_START_PIXELS,
            "text_budget": budget,
            "required_interior_columns": required_interior,
            "required_frame_columns": required_interior + 2,
            "status": (
                "overflow" if overflow else
                ("safe_widened" if is_widened else "safe_native")
            ),
            "recommended_action": review.get(
                "recommended_action",
                "unreviewed" if overflow else "none",
            ),
            "context": review.get("context", ""),
            "wording_candidates": wording_candidates,
            "widest": dict(widest),
            "overflow_labels": [dict(label) for label in overflow],
            "labels": labels,
        })
    return rows


def _scope_summary(rows):
    return {
        "occurrences": sum(row["occurrences"] for row in rows),
        "unique_sets": len(rows),
        "safe_native_sets": sum(
            row["status"] == "safe_native" for row in rows
        ),
        "safe_widened_sets": sum(
            row["status"] == "safe_widened" for row in rows
        ),
        "overflow_sets": sum(row["status"] == "overflow" for row in rows),
        "overflow_occurrences": sum(
            row["occurrences"] for row in rows if row["status"] == "overflow"
        ),
        "sets": rows,
    }


def _fixed_action_summary(indices, budget, records, translated, font_rom):
    labels = [
        _translated_label((EVENT_CHOICE_GROUP, index), records, translated, font_rom)
        for index in indices
    ]
    for label in labels:
        label["clearance_pixels"] = budget - label["renderer_pixels"]
    widest = max(labels, key=lambda label: label["renderer_pixels"])
    return {
        "entries": len(labels),
        "text_budget": budget,
        "widest": dict(widest),
        "overflow_labels": [
            dict(label) for label in labels if label["renderer_pixels"] > budget
        ],
        "labels": labels,
    }


def audit(rom, translation_path):
    """Return the complete translated action-menu audit for ``rom``."""
    rom = bytes(rom)
    result = extract.extract(rom)
    records = _record_map(result)
    translated = translations.load_path(translation_path, result["records"])
    font_rom = english_font.install(rom, checksums=False)

    candidates = _event_choice_candidates(rom, records)
    unexpected_banks = sorted(
        {item["bank"] for item in candidates}
        - RELEASE_EVENT_BANKS
        - DEVELOPER_EVENT_BANKS
    )
    if unexpected_banks:
        raise MenuActionAuditError(
            "event choices appeared in unclassified bank(s): %s"
            % ", ".join(str(bank) for bank in unexpected_banks)
        )

    release_candidates = tuple(
        item for item in candidates if item["bank"] in RELEASE_EVENT_BANKS
    )
    developer_candidates = tuple(
        item for item in candidates if item["bank"] in DEVELOPER_EVENT_BANKS
    )
    release_rows = _menu_set_rows(
        release_candidates, records, translated, font_rom
    )
    developer_rows = _menu_set_rows(
        developer_candidates, records, translated, font_rom
    )
    coverage = surfaces.call_graph_coverage(rom)

    return {
        "schema": SCHEMA,
        "source_rom_sha1": sha1(rom).hexdigest(),
        "positioned_text": {
            "apis": coverage["api_count"],
            "discovered_call_sites": coverage["discovered_count"],
            "assigned_call_sites": coverage["assigned_count"],
            "complete": coverage["complete"],
        },
        "item_actions": _fixed_action_summary(
            ITEM_ACTION_INDICES,
            ITEM_ACTION_TEXT_BUDGET,
            records,
            translated,
            font_rom,
        ),
        "stairs": _fixed_action_summary(
            stairs_menu.STAIRS_INDICES,
            stairs_menu.TEXT_RIGHT_EDGE - stairs_menu.TEXT_START_X,
            records,
            translated,
            font_rom,
        ),
        "event_choices": {
            "opcode": EVENT_CHOICE_OPCODE,
            "record_bytes": EVENT_CHOICE_BYTES,
            "occurrences": len(candidates),
            "unique_sets": len({item["references"] for item in candidates}),
            "locations_sha1": sha1(
                "\n".join(item["location"] for item in candidates).encode("ascii")
            ).hexdigest(),
            "records_sha1": sha1(
                b"".join(item["raw"] for item in candidates)
            ).hexdigest(),
            "release_banks": sorted(RELEASE_EVENT_BANKS),
            "developer_banks": sorted(DEVELOPER_EVENT_BANKS),
            "release": _scope_summary(release_rows),
            "developer": _scope_summary(developer_rows),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--translations", default="script/en")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        measured = audit(Path(args.rom).read_bytes(), args.translations)
    except (OSError, ValueError, MenuActionAuditError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    if args.json:
        print(json.dumps(measured, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        event = measured["event_choices"]
        release = event["release"]
        print(
            "%d event choices / %d unique sets; %d release overflow sets"
            % (event["occurrences"], event["unique_sets"], release["overflow_sets"])
        )
        for menu in release["sets"]:
            if menu["status"] != "overflow":
                continue
            details = ", ".join(
                "%s %d>%dpx" % (
                    label["text"], label["renderer_pixels"], menu["text_budget"]
                )
                for label in menu["overflow_labels"]
            )
            print("OVERFLOW %s: %s" % (menu["name"], details))
            if menu["context"]:
                print("  CONTEXT %s" % menu["context"])
            print("  REVIEW %s" % menu["recommended_action"])
            for candidate in menu["wording_candidates"]:
                fit = "fits native" if candidate["fits_native"] else "needs geometry"
                print(
                    "  WORDING %s: %dpx, %s"
                    % (candidate["text"], candidate["renderer_pixels"], fit)
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
