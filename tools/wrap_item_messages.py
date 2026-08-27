#!/usr/bin/env python3
"""Measure and synchronize the group-11 dungeon item-message draft.

The tracked draft is source-free and owns group 11 indices 20 through 169: the
item/action result block after the 20 item-name formatter fragments.  Ordinary
word spaces are wrapped with :func:`wrap_en.wrap_record`; semantic controls and
runtime substitutions remain translator-owned.  A hash-only state file rejects
manual edits to generated English before either catalog is rewritten.
"""
import argparse
import csv
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import re
import sys

import english
import english_font
import extract
import layout
import lint_en
import organize
import overlays
import runtime_widths
import translations
import wrap_en


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "script" / "drafts" / "item_messages.tsv"
DEFAULT_STATE = ROOT / "script" / "drafts" / "item_messages.generated.json"
DEFAULT_CATALOG = ROOT / "script" / "organized"
DEFAULT_OVERLAYS = ROOT / "script" / "en"

SCHEMA = "shiren-gb2-item-message-draft-v1"
STATE_SCHEMA = "shiren-gb2-item-message-generated-v1"
SECTION = "item_and_action_messages"
GROUP = 11
FIRST_INDEX = 20
LAST_INDEX = 169
_HEX_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")


class ItemMessageWrapError(ValueError):
    """The item-message draft cannot be wrapped or synchronized safely."""


@dataclass(frozen=True)
class MessageRow:
    index: int
    record: object
    sections: tuple


@dataclass(frozen=True)
class DraftRow:
    record_id: str
    sections: tuple
    draft: str


def wrap_message(font_rom, record, draft, runtime_contract):
    """Wrap one item message, retaining authored native F3 checkpoints.

    A dynamic item name can make one fixed English ``<br>`` look badly
    unbalanced for short names. When a translator deliberately supplies F3,
    validate the game compositor's real rollback path and leave those
    conditional checkpoints intact. Ordinary item rows retain the established
    greedy fixed-line policy.
    """
    if "<cF3>" not in draft:
        return wrap_en.wrap_record(
            font_rom,
            record,
            draft,
            runtime_contract=runtime_contract,
            balanced=False,
        )
    try:
        encoded = english.encode_source(draft)
    except ValueError as exc:
        raise wrap_en.WrapError(
            "%s draft cannot be encoded: %s" % (record.id, exc)
        ) from exc
    wrap_en.validate_control_contract(record, draft, encoded)
    measured = layout.source_layout(
        font_rom,
        encoded,
        mode=layout.SURFACE_PROFILES["dialogue"].representative_mode,
        runtime_contract=runtime_contract,
        record_id=record.id,
        simulate_soft_wrap=True,
    )
    if measured.unresolved_dynamic_offsets:
        raise wrap_en.WrapError(
            "%s has unresolved runtime widths on its native soft-wrap path"
            % record.id
        )
    by_surface = {}
    for line in measured.lines:
        by_surface[line.surface] = max(
            by_surface.get(line.surface, 0), line.line + 1
        )
    if not measured.safe or max(by_surface.values(), default=1) > wrap_en.DIALOGUE_LINE_LIMIT:
        raise wrap_en.WrapError(
            "%s has an unsafe native soft-wrap layout" % record.id
        )
    return draft


def _text_sha1(text):
    return sha1(text.encode("utf-8")).hexdigest()


def message_rows(result):
    """Return the exact group-11 item/action block in selector order."""
    classified = {row.record.id: row for row in organize.classify(result)}
    by_index = {}
    for record in result["records"]:
        for reference in record.references:
            if reference.group != GROUP:
                continue
            if not FIRST_INDEX <= reference.index <= LAST_INDEX:
                continue
            if reference.index in by_index:
                raise ItemMessageWrapError(
                    "group %d index %d has multiple records"
                    % (GROUP, reference.index)
                )
            row = classified[record.id]
            if row.category != "messages" or row.sections != (SECTION,):
                raise ItemMessageWrapError(
                    "%s left the item-message semantic partition" % record.id
                )
            by_index[reference.index] = MessageRow(
                reference.index, record, row.sections
            )
    wanted = set(range(FIRST_INDEX, LAST_INDEX + 1))
    if set(by_index) != wanted:
        missing = min(wanted - set(by_index))
        raise ItemMessageWrapError(
            "group %d item-message block is missing index %d" % (GROUP, missing)
        )
    return tuple(by_index[index] for index in sorted(by_index))


def eligible_sha1(rows):
    digest = sha1()
    for row in rows:
        digest.update(str(row.index).encode("ascii"))
        digest.update(b"\0")
        digest.update(row.record.id.encode("ascii"))
        digest.update(b"\0")
        digest.update(";".join(row.sections).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def draft_sha1(rows):
    digest = sha1()
    for row in rows:
        digest.update(row.record_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(";".join(row.sections).encode("ascii"))
        digest.update(b"\0")
        digest.update(row.draft.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def read_draft(path, eligible):
    path = Path(path)
    wanted = {row.record.id: row for row in eligible}
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or ())
        missing = {"id", "sections", "draft"} - fields
        if missing:
            raise ItemMessageWrapError(
                "%s is missing required column(s): %s"
                % (path, ", ".join(sorted(missing)))
            )
        for line_number, values in enumerate(reader, 2):
            if None in values or any(values.get(name) is None for name in fields):
                raise ItemMessageWrapError(
                    "%s:%d has the wrong number of TSV columns"
                    % (path, line_number)
                )
            record_id = values["id"]
            if not record_id or record_id.startswith("#"):
                continue
            if record_id in out:
                raise ItemMessageWrapError(
                    "%s:%d duplicates record ID %s"
                    % (path, line_number, record_id)
                )
            if record_id not in wanted:
                raise ItemMessageWrapError(
                    "%s:%d names stale or non-item record ID %s"
                    % (path, line_number, record_id)
                )
            sections = tuple(filter(None, values["sections"].split(";")))
            if sections != wanted[record_id].sections:
                raise ItemMessageWrapError(
                    "%s:%d semantic sections changed for %s"
                    % (path, line_number, record_id)
                )
            out[record_id] = DraftRow(record_id, sections, values["draft"])
    missing_ids = [row.record.id for row in eligible if row.record.id not in out]
    if missing_ids:
        raise ItemMessageWrapError(
            "%s is missing item-message record ID %s" % (path, missing_ids[0])
        )
    return out


def _base_state(result, eligible):
    return {
        "schema": STATE_SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "eligible_sha1": eligible_sha1(eligible),
        "generated": {},
    }


def load_state(path, result, eligible, allow_missing=False):
    path = Path(path)
    if not path.exists():
        if allow_missing:
            return _base_state(result, eligible)
        raise ItemMessageWrapError("%s does not exist" % path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != STATE_SCHEMA:
        raise ItemMessageWrapError("%s has unsupported state schema" % path)
    if data.get("rom_sha1") != result["rom_sha1"]:
        raise ItemMessageWrapError("%s belongs to a different ROM" % path)
    if data.get("eligible_sha1") != eligible_sha1(eligible):
        raise ItemMessageWrapError(
            "%s belongs to a different item-message partition" % path
        )
    generated = data.get("generated")
    if not isinstance(generated, dict):
        raise ItemMessageWrapError("%s generated state must be an object" % path)
    known = {row.record.id for row in eligible}
    for record_id, hashes in generated.items():
        if record_id not in known:
            raise ItemMessageWrapError(
                "%s owns stale record ID %s" % (path, record_id)
            )
        if not isinstance(hashes, dict) or set(hashes) != {
            "draft_sha1",
            "wrapped_sha1",
        }:
            raise ItemMessageWrapError(
                "%s has malformed state for %s" % (path, record_id)
            )
        if any(
            not isinstance(value, str) or not _HEX_SHA1_RE.fullmatch(value)
            for value in hashes.values()
        ):
            raise ItemMessageWrapError(
                "%s has malformed hashes for %s" % (path, record_id)
            )
    return data


def _write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_workspace(
    source_rom,
    result,
    draft_path=DEFAULT_DRAFT,
    state_path=DEFAULT_STATE,
    catalog_dir=DEFAULT_CATALOG,
    overlay_dir=DEFAULT_OVERLAYS,
    exceptions_path=None,
):
    eligible = message_rows(result)
    drafts = read_draft(draft_path, eligible)
    state = load_state(state_path, result, eligible, allow_missing=True)
    current = overlays.merge_english(result, catalog_dir, overlay_dir)

    for record_id, hashes in state["generated"].items():
        if not drafts[record_id].draft:
            raise ItemMessageWrapError(
                "%s is wrapper-owned but its item-message draft is now blank"
                % record_id
            )
        if _text_sha1(current.get(record_id, "")) != hashes["wrapped_sha1"]:
            raise ItemMessageWrapError(
                "%s generated English was edited outside the item-message draft"
                % record_id
            )

    font_rom = english_font.install(source_rom)
    current_translated = translations.load_mapping(current, result["records"])
    runtime_analysis = runtime_widths.analyze(
        font_rom, result, current_translated
    )
    wrapped_by_id = {}
    next_generated = {}
    for item in eligible:
        draft = drafts[item.record.id]
        if not draft.draft:
            continue
        wrapped = wrap_message(
            font_rom,
            item.record,
            draft.draft,
            runtime_analysis.contract,
        )
        old = state["generated"].get(item.record.id)
        existing = current.get(item.record.id, "")
        if old is None and existing and existing != wrapped:
            raise ItemMessageWrapError(
                "%s already has non-wrapper English; move it into the item-message "
                "draft or clear it" % item.record.id
            )
        wrapped_by_id[item.record.id] = wrapped
        next_generated[item.record.id] = {
            "draft_sha1": _text_sha1(draft.draft),
            "wrapped_sha1": _text_sha1(wrapped),
        }

    merged = dict(current)
    merged.update(wrapped_by_id)
    translated = translations.load_mapping(merged, result["records"])
    if exceptions_path is None:
        exceptions_path = lint_en.default_exceptions_path(overlay_dir)
    exceptions = lint_en.load_exceptions(exceptions_path, result)
    lint_summary = lint_en.require_clean(result, translated, exceptions)
    next_state = _base_state(result, eligible)
    next_state["generated"] = next_generated
    return eligible, drafts, merged, wrapped_by_id, next_state, lint_summary


def contract_summary(result, eligible, drafts, wrapped_by_id, state):
    ordered = tuple(drafts[row.record.id] for row in eligible)
    deferred = [
        row.index for row in eligible if not drafts[row.record.id].draft
    ]
    line_counts = {}
    for record_id, wrapped in wrapped_by_id.items():
        surfaces = wrapped.replace("<box>", "<page>").split("<page>")
        line_counts[record_id] = max(
            (part.count("<br>") + 1 for part in surfaces if part),
            default=0,
        )
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "source_free": True,
        "group": GROUP,
        "index_range": [FIRST_INDEX, LAST_INDEX],
        "eligible_records": len(eligible),
        "eligible_sha1": eligible_sha1(eligible),
        "draft_records": sum(bool(row.draft) for row in ordered),
        "draft_sha1": draft_sha1(ordered),
        "generated_records": len(state["generated"]),
        "deferred_indices": deferred,
        "max_lines_per_surface": max(line_counts.values(), default=0),
        "layout": {
            "composer_max_pixels": wrap_en.layout.COMPOSER_WRAP_AT - 1,
            "renderer_max_pixels": wrap_en.layout.CANVAS_WIDTH_PIXELS,
            "dialogue_lines_per_surface": wrap_en.DIALOGUE_LINE_LIMIT,
        },
    }


def apply_workspace(result, merged, state, catalog_dir, overlay_dir, state_path):
    organized = organize.classify(result)
    organize.write_outputs(result, catalog_dir, english_by_id=merged)
    overlays.write_outputs(result, overlay_dir, organized, merged)
    _write_state(state_path, state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--translations", default=str(DEFAULT_OVERLAYS))
    parser.add_argument("--exceptions")
    parser.add_argument(
        "--apply", action="store_true", help="write validated wrapped rows"
    )
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)
    try:
        source_rom = Path(args.rom).read_bytes()
        result = extract.extract(source_rom)
        (
            eligible,
            drafts,
            merged,
            wrapped_by_id,
            state,
            lint_summary,
        ) = prepare_workspace(
            source_rom,
            result,
            draft_path=args.draft,
            state_path=args.state,
            catalog_dir=args.catalog,
            overlay_dir=args.translations,
            exceptions_path=args.exceptions,
        )
        measured = contract_summary(
            result, eligible, drafts, wrapped_by_id, state
        )
        if args.apply:
            apply_workspace(
                result,
                merged,
                state,
                args.catalog,
                args.translations,
                args.state,
            )
    except (
        OSError,
        ValueError,
        extract.ExtractError,
        ItemMessageWrapError,
        wrap_en.WrapError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    if args.json:
        print(json.dumps(measured, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(
            "item messages: %d / %d drafted; %d deferred; lint issues %d"
            % (
                measured["draft_records"],
                measured["eligible_records"],
                len(measured["deferred_indices"]),
                lint_summary["problems"],
            )
        )
        print("mode         : %s" % ("applied" if args.apply else "check only"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
