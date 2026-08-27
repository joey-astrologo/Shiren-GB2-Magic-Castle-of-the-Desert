#!/usr/bin/env python3
"""Validate and synchronize GB2's source-free group-8 message draft.

Group 8 is one pointer table, but it is not one rendering/translation family.
Indices 0-109 are reusable streamed combat-log messages.  The remainder mixes
shop dialogue, companion condition chatter, behavior labels, and scripted boss
scenes.  This tool freezes those semantic partitions and lets all 201 records
share one conflict-safe source-free authoring sheet without pretending that
they share one layout policy.

Combat-log drafts own their F3 soft-wrap checkpoints.  GB2's source composer
keeps an F3 checkpoint invisible when the expanded sentence fits and rewinds
it to FD only when a later glyph reaches 144 pixels.  Validation therefore
uses the proved mode-$10 renderer and simulates that rollback.  A separate
combination audit substitutes every distinct translated runtime-name geometry
so warnings describe actual names rather than only a global longest-name bound.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha1
import itertools
import json
from pathlib import Path
import re
import sys

import codec
import english
import english_font
import extract
import layout
import lint_en
import organize
import overlays
import runtime_terms
import runtime_widths
import translations
import wrap_en


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "script" / "drafts" / "combat_messages.tsv"
DEFAULT_STATE = ROOT / "script" / "drafts" / "combat_messages.generated.json"
DEFAULT_CATALOG = ROOT / "script" / "organized"
DEFAULT_OVERLAYS = ROOT / "script" / "en"

SCHEMA = "shiren-gb2-combat-message-draft-v1"
STATE_SCHEMA = "shiren-gb2-combat-message-generated-v1"
SECTION = "combat_and_dungeon_messages"
GROUP = 8
FIRST_INDEX = 0
LAST_INDEX = 200
COMBAT_LOG_LAST_INDEX = 109
COMBAT_MODE = 0x10
_HEX_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")


# These ranges are semantic, not merely convenient batches.  Keep the names
# stable: they are copied into the draft and frozen by the fixture.
PARTITIONS = (
    ("damage", 0, 5),
    ("attack_outcomes", 6, 17),
    ("experience_and_levels", 18, 31),
    ("resources_and_traps", 32, 41),
    ("monster_abilities_and_theft", 42, 64),
    ("actor_stat_changes", 65, 80),
    ("statuses", 81, 109),
    ("shop_and_alarm", 110, 118),
    ("nfuu_abilities_and_training", 119, 126),
    ("nfuu_condition_chatter", 127, 133),
    ("mamo_condition_chatter", 134, 142),
    ("oryu_condition_chatter", 143, 151),
    ("pekeji_condition_chatter", 152, 160),
    ("robot_condition_chatter", 161, 170),
    ("actor_behavior_and_labels", 171, 176),
    ("scripted_boss_and_story", 177, 200),
)


class CombatMessageError(ValueError):
    """The group-8 draft or its runtime layout contract is unsafe."""


@dataclass(frozen=True)
class MessageRow:
    index: int
    record: object
    sections: tuple
    family: str


@dataclass(frozen=True)
class DraftRow:
    record_id: str
    sections: tuple
    family: str
    draft: str


@dataclass(frozen=True)
class WidthCandidate:
    label: str
    composer_pixels: int
    renderer_pixels: int
    values: int = 1


def _text_sha1(text):
    return sha1(text.encode("utf-8")).hexdigest()


def family_for_index(index):
    for name, first, last in PARTITIONS:
        if first <= index <= last:
            return name
    raise CombatMessageError("group %d index %d has no semantic family" % (GROUP, index))


def message_rows(result):
    """Return the exact 201-entry group-8 table in selector order."""
    classified = {row.record.id: row for row in organize.classify(result)}
    by_index = {}
    for record in result["records"]:
        for reference in record.references:
            if reference.group != GROUP:
                continue
            if not FIRST_INDEX <= reference.index <= LAST_INDEX:
                raise CombatMessageError(
                    "unexpected group %d index %d" % (GROUP, reference.index)
                )
            if reference.index in by_index:
                raise CombatMessageError(
                    "group %d index %d has multiple records"
                    % (GROUP, reference.index)
                )
            row = classified[record.id]
            if row.category != "messages" or row.sections != (SECTION,):
                raise CombatMessageError(
                    "%s left the group-8 semantic partition" % record.id
                )
            by_index[reference.index] = MessageRow(
                reference.index,
                record,
                row.sections,
                family_for_index(reference.index),
            )
    wanted = set(range(FIRST_INDEX, LAST_INDEX + 1))
    if set(by_index) != wanted:
        missing = min(wanted - set(by_index))
        raise CombatMessageError(
            "group %d message table is missing index %d" % (GROUP, missing)
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
        digest.update(row.family.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def draft_sha1(rows):
    digest = sha1()
    for row in rows:
        digest.update(row.record_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(";".join(row.sections).encode("ascii"))
        digest.update(b"\0")
        digest.update(row.family.encode("ascii"))
        digest.update(b"\0")
        digest.update(row.draft.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def read_draft(path, eligible, require_complete=True):
    path = Path(path)
    wanted = {row.record.id: row for row in eligible}
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or ())
        missing = {"id", "sections", "family", "draft"} - fields
        if missing:
            raise CombatMessageError(
                "%s is missing required column(s): %s"
                % (path, ", ".join(sorted(missing)))
            )
        for line_number, values in enumerate(reader, 2):
            if None in values or any(values.get(name) is None for name in fields):
                raise CombatMessageError(
                    "%s:%d has the wrong number of TSV columns"
                    % (path, line_number)
                )
            record_id = values["id"]
            if not record_id or record_id.startswith("#"):
                continue
            if record_id in out:
                raise CombatMessageError(
                    "%s:%d duplicates record ID %s"
                    % (path, line_number, record_id)
                )
            if record_id not in wanted:
                raise CombatMessageError(
                    "%s:%d names stale or non-group-8 record ID %s"
                    % (path, line_number, record_id)
                )
            expected = wanted[record_id]
            sections = tuple(filter(None, values["sections"].split(";")))
            if sections != expected.sections:
                raise CombatMessageError(
                    "%s:%d semantic sections changed for %s"
                    % (path, line_number, record_id)
                )
            if values["family"] != expected.family:
                raise CombatMessageError(
                    "%s:%d semantic family changed for %s"
                    % (path, line_number, record_id)
                )
            out[record_id] = DraftRow(
                record_id, sections, values["family"], values["draft"]
            )
    if require_complete:
        missing_ids = [row.record.id for row in eligible if row.record.id not in out]
        if missing_ids:
            raise CombatMessageError(
                "%s is missing group-8 record ID %s; run with --init"
                % (path, missing_ids[0])
            )
    return out


def write_draft(path, eligible, existing=None):
    """Create or refresh all rows while retaining authored English cells."""
    path = Path(path)
    existing = {} if existing is None else dict(existing)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("id", "sections", "family", "draft"))
        for row in eligible:
            old = existing.get(row.record.id)
            writer.writerow(
                (
                    row.record.id,
                    ";".join(row.sections),
                    row.family,
                    "" if old is None else old.draft,
                )
            )


def refresh_draft(path, eligible):
    path = Path(path)
    existing = read_draft(path, eligible, require_complete=False) if path.exists() else {}
    write_draft(path, eligible, existing)
    return read_draft(path, eligible)


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
        raise CombatMessageError("%s does not exist; run with --init" % path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != STATE_SCHEMA:
        raise CombatMessageError("%s has unsupported state schema" % path)
    if data.get("rom_sha1") != result["rom_sha1"]:
        raise CombatMessageError("%s belongs to a different ROM" % path)
    if data.get("eligible_sha1") != eligible_sha1(eligible):
        raise CombatMessageError("%s belongs to a different group-8 partition" % path)
    generated = data.get("generated")
    if not isinstance(generated, dict):
        raise CombatMessageError("%s generated state must be an object" % path)
    known = {row.record.id for row in eligible}
    for record_id, hashes in generated.items():
        if record_id not in known:
            raise CombatMessageError("%s owns stale record ID %s" % (path, record_id))
        if not isinstance(hashes, dict) or set(hashes) != {
            "draft_sha1",
            "generated_sha1",
        }:
            raise CombatMessageError("%s has malformed state for %s" % (path, record_id))
        if any(
            not isinstance(value, str) or not _HEX_SHA1_RE.fullmatch(value)
            for value in hashes.values()
        ):
            raise CombatMessageError("%s has malformed hashes for %s" % (path, record_id))
    return data


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mode(row):
    return COMBAT_MODE if row.index <= COMBAT_LOG_LAST_INDEX else 0x02


def validate_draft(font_rom, row, draft, runtime_contract):
    """Return encoded English after proving controls and native layout."""
    if not draft:
        raise CombatMessageError("%s has a blank draft" % row.record.id)
    if any(character in draft for character in "\t\r\n"):
        raise CombatMessageError(
            "%s uses non-space whitespace" % row.record.id
        )
    try:
        encoded = english.encode_source(draft)
    except ValueError as exc:
        raise CombatMessageError(
            "%s draft cannot be encoded: %s" % (row.record.id, exc)
        ) from exc
    try:
        wrap_en.validate_control_contract(row.record, draft, encoded)
    except wrap_en.WrapError as exc:
        raise CombatMessageError(str(exc)) from exc
    measured = layout.source_layout(
        font_rom,
        encoded,
        mode=_mode(row),
        runtime_contract=runtime_contract,
        record_id=row.record.id,
        simulate_soft_wrap=True,
    )
    if measured.unresolved_dynamic_offsets:
        raise CombatMessageError(
            "%s has runtime substitutions without translated width bounds"
            % row.record.id
        )
    if not measured.safe:
        problems = []
        if measured.composer_overflows:
            problems.append("composer overflow")
        if measured.renderer_overflows:
            problems.append("renderer overflow")
        if measured.line_limit_overflows:
            problems.append("dialogue line-limit overflow")
        raise CombatMessageError(
            "%s fails native layout: %s" % (row.record.id, ", ".join(problems))
        )
    return draft, encoded, measured


def _record_map(result):
    records = {(record.bank, record.address): record for record in result["records"]}
    return {
        (reference.group, reference.index): records[
            (reference.target_bank, reference.target_address)
        ]
        for reference in result["references"]
    }


def _plain_width(font_rom, encoded):
    tokens = tuple(codec.parse_source(encoded))
    if any(token.kind not in ("glyph", "kanji") for token in tokens):
        raise CombatMessageError("runtime-name candidate contains a non-glyph token")
    measured = layout.source_layout(font_rom, encoded)
    if len(measured.lines) != 1 or measured.dynamic_offsets:
        raise CombatMessageError("runtime-name candidate is not one static line")
    line = measured.lines[0]
    return line.composer_pixels, line.renderer_pixels


def _translation_candidates(font_rom, result, translated, family_names):
    definitions = {family.name: family for family in runtime_terms.TERM_FAMILIES}
    records = _record_map(result)
    candidates = []
    seen_records = set()
    for family_name in family_names:
        family = definitions[family_name]
        for index in range(family.start_index, family.end_index + 1):
            record = records[(family.group, index)]
            if record.id in seen_records:
                continue
            seen_records.add(record.id)
            try:
                translation = translated[(record.bank, record.address)]
            except KeyError as exc:
                raise CombatMessageError(
                    "%s is missing English needed by the %s warning domain"
                    % (record.id, family_name)
                ) from exc
            composer, renderer = _plain_width(font_rom, translation.encoded)
            candidates.append(
                WidthCandidate(
                    translation.text or "<empty>", composer, renderer
                )
            )
    return candidates


def _dedupe_candidates(candidates):
    """Keep one example and a value count for each equivalent width pair."""
    by_label = {}
    for candidate in candidates:
        by_label.setdefault(candidate.label, candidate)
    by_width = {}
    for candidate in by_label.values():
        key = (candidate.composer_pixels, candidate.renderer_pixels)
        old = by_width.get(key)
        if old is None:
            by_width[key] = candidate
        else:
            by_width[key] = WidthCandidate(
                old.label,
                old.composer_pixels,
                old.renderer_pixels,
                old.values + candidate.values,
            )
    return (
        tuple(by_width[key] for key in sorted(by_width)),
        len(by_label),
    )


def runtime_candidate_domains(font_rom, result, translated):
    """Return actual translated candidates for every group-8 F6 domain."""
    actor = _translation_candidates(
        font_rom,
        result,
        translated,
        ("actor_name_tier_1", "actor_name_tier_2", "actor_name_tier_3"),
    )
    player_encoded = english.encode_source("WWWWWWW")
    composer, renderer = _plain_width(font_rom, player_encoded)
    actor.append(WidthCandidate("<widest 7-byte player name>", composer, renderer))

    traps = _translation_candidates(
        font_rom, result, translated, ("trap_names",)
    )
    items = _translation_candidates(
        font_rom,
        result,
        translated,
        ("identified_item_names", "unidentified_item_appearances"),
    )
    fragments = _translation_candidates(
        font_rom, result, translated, ("item_name_format_fragments",)
    )
    for fragment in fragments:
        items.append(
            WidthCandidate(
                "%s<widest custom name>" % fragment.label,
                fragment.composer_pixels + composer,
                fragment.renderer_pixels + renderer,
            )
        )

    domains = {}
    counts = {}
    for name, values in (
        ("actor_name", actor),
        ("trap_name", traps),
        ("item_name", items),
    ):
        domains[name], counts[name] = _dedupe_candidates(values)
    return domains, counts


def _f6_domain(analysis, record_id, raw):
    bound = analysis.f6_bounds.get((record_id, raw))
    if bound is None:
        raise CombatMessageError(
            "%s has an unbounded F6 token %s"
            % (record_id, codec.decode_source(raw))
        )
    if not bound.kind.startswith("f6_"):
        raise CombatMessageError(
            "%s has an unexpected F6 bound kind %s" % (record_id, bound.kind)
        )
    return bound.kind[len("f6_"):]


def combination_report(font_rom, row, draft, analysis, domains, domain_counts):
    """Exhaust every layout-distinct F6 substitution combination."""
    encoded = english.encode_source(draft)
    raws = []
    for token in codec.parse_source(encoded):
        if token.kind == "source_control" and token.code == 0xF6 and token.raw not in raws:
            raws.append(token.raw)

    choices = []
    domain_names = []
    value_combinations = 1
    for raw in raws:
        domain_name = _f6_domain(analysis, row.record.id, raw)
        try:
            candidates = domains[domain_name]
            value_count = domain_counts[domain_name]
        except KeyError as exc:
            raise CombatMessageError(
                "%s warning audit does not enumerate %s"
                % (row.record.id, domain_name)
            ) from exc
        choices.append(candidates)
        domain_names.append(domain_name)
        value_combinations *= value_count

    geometry_combinations = 1
    for candidates in choices:
        geometry_combinations *= len(candidates)
    products = itertools.product(*choices) if choices else ((),)
    geometry_counts = Counter()
    value_counts = Counter()
    examples = {}
    max_composer = max_renderer = 0
    for combination in products:
        bounds = {}
        labels = []
        for raw, domain_name, candidate in zip(raws, domain_names, combination):
            bounds[(row.record.id, raw)] = layout.RuntimeF6Bound(
                "f6_%s" % domain_name,
                candidate.composer_pixels,
                candidate.renderer_pixels,
            )
            labels.append(candidate.label)
        contract = layout.english_runtime_width_contract(bounds)
        measured = layout.source_layout(
            font_rom,
            encoded,
            mode=_mode(row),
            runtime_contract=contract,
            record_id=row.record.id,
            simulate_soft_wrap=True,
        )
        max_composer = max(
            max_composer,
            max((line.composer_pixels for line in measured.lines), default=0),
        )
        max_renderer = max(
            max_renderer,
            max((line.renderer_pixels for line in measured.lines), default=0),
        )
        if not measured.safe:
            outcome = "unsafe"
        elif measured.soft_wraps:
            outcome = "soft_wrap"
        else:
            outcome = "one_line"
        geometry_counts[outcome] += 1
        weight = 1
        for candidate in combination:
            weight *= candidate.values
        value_counts[outcome] += weight
        examples.setdefault(outcome, labels)

    return {
        "index": row.index,
        "id": row.record.id,
        "family": row.family,
        "f6_domains": domain_names,
        "runtime_value_combinations": value_combinations,
        "layout_distinct_combinations": geometry_combinations,
        "one_line": value_counts["one_line"],
        "soft_wrap": value_counts["soft_wrap"],
        "unsafe": value_counts["unsafe"],
        "layout_one_line": geometry_counts["one_line"],
        "layout_soft_wrap": geometry_counts["soft_wrap"],
        "layout_unsafe": geometry_counts["unsafe"],
        "max_composer_pixels": max_composer,
        "max_renderer_pixels": max_renderer,
        "example_one_line": examples.get("one_line"),
        "example_soft_wrap": examples.get("soft_wrap"),
        "example_unsafe": examples.get("unsafe"),
    }


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
    state = load_state(state_path, result, eligible)
    current = overlays.merge_english(result, catalog_dir, overlay_dir)

    for record_id, hashes in state["generated"].items():
        if not drafts[record_id].draft:
            raise CombatMessageError(
                "%s is tool-owned but its group-8 draft is now blank" % record_id
            )
        if _text_sha1(current.get(record_id, "")) != hashes["generated_sha1"]:
            raise CombatMessageError(
                "%s generated English was edited outside the combat draft"
                % record_id
            )

    font_rom = english_font.install(source_rom)
    current_translated = translations.load_mapping(current, result["records"])
    analysis = runtime_widths.analyze(font_rom, result, current_translated)
    domains, domain_counts = runtime_candidate_domains(
        font_rom, result, current_translated
    )

    generated = {}
    next_generated = {}
    warnings = []
    for row in eligible:
        draft = drafts[row.record.id].draft
        if not draft:
            continue
        text, _encoded, _measured = validate_draft(
            font_rom, row, draft, analysis.contract
        )
        old = state["generated"].get(row.record.id)
        existing = current.get(row.record.id, "")
        if old is None and existing and existing != text:
            raise CombatMessageError(
                "%s already has non-tool English; move it into the combat draft or clear it"
                % row.record.id
            )
        warning = combination_report(
            font_rom, row, text, analysis, domains, domain_counts
        )
        if warning["unsafe"]:
            raise CombatMessageError(
                "%s has %d unsafe runtime-name geometry combination(s)"
                % (row.record.id, warning["unsafe"])
            )
        generated[row.record.id] = text
        warnings.append(warning)
        next_generated[row.record.id] = {
            "draft_sha1": _text_sha1(draft),
            "generated_sha1": _text_sha1(text),
        }

    merged = dict(current)
    merged.update(generated)
    translated = translations.load_mapping(merged, result["records"])
    if exceptions_path is None:
        exceptions_path = lint_en.default_exceptions_path(overlay_dir)
    exceptions = lint_en.load_exceptions(exceptions_path, result)
    lint_summary = lint_en.require_clean(result, translated, exceptions)
    next_state = _base_state(result, eligible)
    next_state["generated"] = next_generated
    return {
        "eligible": eligible,
        "drafts": drafts,
        "merged": merged,
        "generated": generated,
        "state": next_state,
        "warnings": warnings,
        "domain_counts": domain_counts,
        "lint_summary": lint_summary,
    }


def contract_summary(result, eligible, drafts, state, warnings=None, domain_counts=None):
    ordered = tuple(drafts[row.record.id] for row in eligible)
    partition_counts = Counter(row.family for row in eligible)
    controls = Counter()
    substitutions = Counter()
    for row in eligible:
        for token in codec.parse_source(row.record.raw):
            if token.kind == "source_control":
                if token.code == 0xF4:
                    substitutions["copy"] += 1
                elif token.code == 0xF5:
                    substitutions["name"] += 1
                elif token.args[0] == 0x01:
                    substitutions["lookup"] += 1
                elif token.args[0] == 0x03:
                    substitutions["number"] += 1
                else:
                    substitutions["sourceF6"] += 1
            elif token.code in (0xF2, 0xF3, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD):
                label = "speaker" if token.code == 0xF2 else codec.CONTROLS[token.code]
                controls[label] += 1
    warnings = [] if warnings is None else list(warnings)
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "source_free": True,
        "group": GROUP,
        "index_range": [FIRST_INDEX, LAST_INDEX],
        "combat_log_index_range": [FIRST_INDEX, COMBAT_LOG_LAST_INDEX],
        "eligible_records": len(eligible),
        "eligible_sha1": eligible_sha1(eligible),
        "partitions": [
            {
                "name": name,
                "index_range": [first, last],
                "records": partition_counts[name],
            }
            for name, first, last in PARTITIONS
        ],
        "draft_records": sum(bool(row.draft) for row in ordered),
        "draft_sha1": draft_sha1(ordered),
        "generated_records": len(state["generated"]),
        "source_controls": dict(sorted(controls.items())),
        "runtime_substitutions": dict(sorted(substitutions.items())),
        "runtime_candidate_values": dict(sorted((domain_counts or {}).items())),
        "warning_records": len(warnings),
        "warning_totals": {
            key: sum(row[key] for row in warnings)
            for key in (
                "runtime_value_combinations",
                "layout_distinct_combinations",
                "one_line",
                "soft_wrap",
                "unsafe",
                "layout_one_line",
                "layout_soft_wrap",
                "layout_unsafe",
            )
        },
        "layout": {
            "combat_mode": COMBAT_MODE,
            "initial_y": layout.initial_y(COMBAT_MODE),
            "explicit_line_advance": layout.explicit_line_advance(COMBAT_MODE),
            "composer_wrap_at": layout.COMPOSER_WRAP_AT,
            "renderer_max_pixels": layout.CANVAS_WIDTH_PIXELS,
            "soft_wrap_control": "cF3",
        },
    }


def apply_workspace(result, workspace, catalog_dir, overlay_dir, state_path):
    organized = organize.classify(result)
    organize.write_outputs(result, catalog_dir, english_by_id=workspace["merged"])
    overlays.write_outputs(result, overlay_dir, organized, workspace["merged"])
    write_state(state_path, workspace["state"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--translations", default=str(DEFAULT_OVERLAYS))
    parser.add_argument("--exceptions")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--init", action="store_true", help="create or refresh the draft")
    action.add_argument("--apply", action="store_true", help="write validated English")
    parser.add_argument("--json", action="store_true", help="print the contract summary")
    parser.add_argument(
        "--warnings-json",
        action="store_true",
        help="print the per-record runtime-name combination audit",
    )
    args = parser.parse_args(argv)
    try:
        source_rom = Path(args.rom).read_bytes()
        result = extract.extract(source_rom)
        eligible = message_rows(result)
        if args.init:
            drafts = refresh_draft(args.draft, eligible)
            state = load_state(args.state, result, eligible, allow_missing=True)
            write_state(args.state, state)
            measured = contract_summary(result, eligible, drafts, state)
            warnings = []
            verb = "initialized"
        else:
            workspace = prepare_workspace(
                source_rom,
                result,
                draft_path=args.draft,
                state_path=args.state,
                catalog_dir=args.catalog,
                overlay_dir=args.translations,
                exceptions_path=args.exceptions,
            )
            if args.apply:
                apply_workspace(
                    result, workspace, args.catalog, args.translations, args.state
                )
            drafts = workspace["drafts"]
            warnings = workspace["warnings"]
            measured = contract_summary(
                result,
                eligible,
                drafts,
                workspace["state"],
                warnings=warnings,
                domain_counts=workspace["domain_counts"],
            )
            verb = "applied" if args.apply else "checked"
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        codec.ParseError,
        extract.ExtractError,
        overlays.OverlayError,
        translations.TranslationError,
        lint_en.TranslationLintError,
        runtime_widths.RuntimeWidthError,
        CombatMessageError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    if args.warnings_json:
        print(json.dumps(warnings, ensure_ascii=True, indent=2, sort_keys=True))
    elif args.json:
        print(json.dumps(measured, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(
            "group-8 %s: %d eligible; %d drafted; %d generated; %d audited"
            % (
                verb,
                measured["eligible_records"],
                measured["draft_records"],
                measured["generated_records"],
                measured["warning_records"],
            )
        )
        print(
            "runtime layouts: %d one-line; %d soft-wrap; %d unsafe"
            % (
                measured["warning_totals"]["one_line"],
                measured["warning_totals"]["soft_wrap"],
                measured["warning_totals"]["unsafe"],
            )
        )
        print("mode          : %s" % ("applied" if args.apply else "check only"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
