#!/usr/bin/env python3
"""Wrap sentence-level GB2 prose into measured native dialogue lines.

The tracked draft contains stable IDs, semantic sections and natural English,
but no extracted Japanese.  Translators own story pacing controls such as
``<page>`` and ``<box>``.  This tool owns only generated ``<br>`` controls: it
balances ordinary word spaces across the minimum safe number of lines,
measures both of GB2's native width models, and refuses to invent a new
dialogue surface. A source ``<page><br>`` pair is semantic: FB only pauses, so
the FD line advance is preserved unless an inserted FC box reset makes it
unnecessary. Physical line occupancy remains cumulative until that FC reset.

Generated rows are synchronized into both the rich ignored catalogs and the
tracked compact overlays.  A hash-only state file records which cells the tool
owns, so a manual edit to generated output fails before either catalog is
rewritten.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha1
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
import runtime_widths
import translations


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "script" / "drafts" / "prose.tsv"
DEFAULT_STATE = ROOT / "script" / "drafts" / "prose.generated.json"
DEFAULT_CATALOG = ROOT / "script" / "organized"
DEFAULT_OVERLAYS = ROOT / "script" / "en"

SCHEMA = "shiren-gb2-prose-draft-v1"
STATE_SCHEMA = "shiren-gb2-prose-generated-v1"
DRAFT_SECTION = "story_and_event_dialogue"
DIALOGUE_LINE_LIMIT = 3

_BOUNDARY_RE = re.compile(r"(<(?:page|box)>)")
_HEX_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")


class WrapError(ValueError):
    """A prose draft cannot be wrapped or synchronized safely."""


@dataclass(frozen=True)
class DraftRow:
    record_id: str
    sections: tuple
    draft: str


@dataclass(frozen=True)
class WrappedWorkspace:
    english_by_id: dict
    wrapped_by_id: dict
    state: dict
    lint_summary: dict


def _text_sha1(text):
    return sha1(text.encode("utf-8")).hexdigest()


def prose_rows(result):
    """Return the exact sentence-level dialogue family in extractor order."""
    return tuple(
        row
        for row in organize.classify(result)
        if row.category == "prose" and DRAFT_SECTION in row.sections
    )


def eligible_sha1(rows):
    digest = sha1()
    for row in rows:
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


def read_draft(path, eligible, require_complete=True):
    """Load a source-free prose draft against the current semantic partition."""
    path = Path(path)
    wanted = {row.record.id: row for row in eligible}
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or ())
        missing = {"id", "sections", "draft"} - fields
        if missing:
            raise WrapError(
                "%s is missing required column(s): %s"
                % (path, ", ".join(sorted(missing)))
            )
        for line_number, values in enumerate(reader, 2):
            if None in values or any(values.get(name) is None for name in fields):
                raise WrapError(
                    "%s:%d has the wrong number of TSV columns"
                    % (path, line_number)
                )
            record_id = values["id"]
            if not record_id or record_id.startswith("#"):
                continue
            if record_id in out:
                raise WrapError(
                    "%s:%d duplicates record ID %s"
                    % (path, line_number, record_id)
                )
            if record_id not in wanted:
                raise WrapError(
                    "%s:%d names stale or non-dialogue record ID %s"
                    % (path, line_number, record_id)
                )
            sections = tuple(filter(None, values["sections"].split(";")))
            if sections != wanted[record_id].sections:
                raise WrapError(
                    "%s:%d semantic sections changed for %s"
                    % (path, line_number, record_id)
                )
            out[record_id] = DraftRow(record_id, sections, values["draft"])

    if require_complete:
        missing = [row.record.id for row in eligible if row.record.id not in out]
        if missing:
            raise WrapError(
                "%s is missing dialogue record ID %s; run with --init"
                % (path, missing[0])
            )
    return out


def write_draft(path, eligible, existing=None):
    """Create or refresh the complete draft while retaining authored cells."""
    path = Path(path)
    existing = {} if existing is None else dict(existing)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("id", "sections", "draft"))
        for row in eligible:
            old = existing.get(row.record.id)
            writer.writerow(
                (
                    row.record.id,
                    ";".join(row.sections),
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
    """Load and validate the hash-only generated-cell ownership state."""
    path = Path(path)
    if not path.exists():
        if allow_missing:
            return _base_state(result, eligible)
        raise WrapError("%s does not exist; run with --init" % path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != STATE_SCHEMA:
        raise WrapError("%s has unsupported state schema" % path)
    if data.get("rom_sha1") != result["rom_sha1"]:
        raise WrapError("%s belongs to a different ROM" % path)
    if data.get("eligible_sha1") != eligible_sha1(eligible):
        raise WrapError("%s belongs to a different prose partition" % path)
    generated = data.get("generated")
    if not isinstance(generated, dict):
        raise WrapError("%s generated state must be an object" % path)
    known = {row.record.id for row in eligible}
    for record_id, hashes in generated.items():
        if record_id not in known:
            raise WrapError("%s owns stale record ID %s" % (path, record_id))
        if not isinstance(hashes, dict) or set(hashes) != {"draft_sha1", "wrapped_sha1"}:
            raise WrapError("%s has malformed state for %s" % (path, record_id))
        if any(
            not isinstance(value, str) or not _HEX_SHA1_RE.fullmatch(value)
            for value in hashes.values()
        ):
            raise WrapError("%s has malformed hashes for %s" % (path, record_id))
    return data


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tokens(data, codes):
    return tuple(token for token in codec.parse_source(data) if token.code in codes)


def _is_subsequence(wanted, got):
    cursor = iter(got)
    return all(any(candidate == item for candidate in cursor) for item in wanted)


def _boundary_shapes(data):
    """Return page/box order plus each page's immediate continuation shape."""
    tokens = tuple(codec.parse_source(data))
    return tuple(
        (
            token.code,
            token.code == 0xFB
            and index + 1 < len(tokens)
            and tokens[index + 1].code == 0xFD,
            token.code == 0xFB
            and index + 1 < len(tokens)
            and tokens[index + 1].code == 0xFC,
        )
        for index, token in enumerate(tokens)
        if token.code in (0xFB, 0xFC)
    )


def _boundary_contract_survives(source, draft):
    cursor = iter(draft)
    for source_code, source_post_break, _source_post_box in source:
        if not any(
            draft_code == source_code
            and (
                not source_post_break
                or draft_post_break
                or draft_post_box
            )
            for draft_code, draft_post_break, draft_post_box in cursor
        ):
            return False
    return True


def physical_box_line_counts(data):
    """Count physical lines accumulated between native FC box resets."""
    counts = []
    lines = 1
    active = False
    for token in codec.parse_source(data):
        if token.code == 0xFC:
            counts.append(lines)
            lines = 1
            active = False
            continue
        active = True
        if token.code == 0xFD:
            lines += 1
    if active:
        counts.append(lines)
    return tuple(counts)


def validate_physical_box_lines(record, encoded):
    """Reject English-only cumulative overflow across FB page waits.

    A native FB page wait does not reset the line index. No English story
    record may accumulate more than three physical lines before an FC reset.
    """
    target = physical_box_line_counts(encoded)
    for index, line_count in enumerate(target):
        if line_count <= DIALOGUE_LINE_LIMIT:
            continue
        raise WrapError(
            "%s accumulates %d physical lines in dialogue box %d across "
            "<page>; insert <box> to reset the window"
            % (record.id, line_count, index + 1)
        )


def validate_control_contract(record, draft, encoded):
    """Preserve semantic boundaries, effects and runtime substitutions."""
    source_boundaries = _boundary_shapes(record.raw)
    draft_boundaries = _boundary_shapes(encoded)
    if not _boundary_contract_survives(source_boundaries, draft_boundaries):
        raise WrapError(
            "%s draft drops or reorders a source <page>/<box> boundary, "
            "or drops its required post-<page> <br> without replacing it "
            "with a box reset"
            % record.id
        )

    for code, label in ((0xF9, "<cF9>"), (0xFA, "<delay>")):
        source_effects = Counter(token.raw for token in _tokens(record.raw, {code}))
        draft_effects = Counter(token.raw for token in _tokens(encoded, {code}))
        if source_effects != draft_effects:
            raise WrapError(
                "%s draft changes the exact %s effect multiset"
                % (record.id, label)
            )

    speaker_quotes = Counter(
        token.args
        for token in codec.parse_source(encoded)
        if token.code == 0xF2 and token.args in (b"\x24", b"\x26")
    )
    if speaker_quotes[b"\x24"] != speaker_quotes[b"\x26"]:
        raise WrapError(
            "%s uses an unmatched Japanese speaker quote; use an English colon "
            "after the speaker label" % record.id
        )

    translated = translations.load_mapping(
        {record.id: draft}, (record,)
    )
    translation = translated[(record.bank, record.address)]
    issues = lint_en.check_runtime_tokens(record, translation)
    if issues:
        raise WrapError(
            "%s draft changes runtime substitutions: %s"
            % (record.id, issues[0].detail)
        )


def _measure_line(font_rom, text, record_id, runtime_contract):
    encoded = english.encode_source(text)
    measured = layout.source_layout(
        font_rom,
        encoded,
        mode=layout.SURFACE_PROFILES["dialogue"].representative_mode,
        runtime_contract=runtime_contract,
        record_id=record_id,
    )
    if measured.unresolved_dynamic_offsets:
        kinds = sorted(
            {
                expansion.kind
                for expansion in measured.dynamic_expansions
                if not expansion.bounded
            }
        )
        raise WrapError(
            "%s needs translated runtime width maxima for %s before it can be wrapped"
            % (record_id, ", ".join(kinds))
        )
    if len(measured.lines) != 1:
        raise WrapError("%s produced an invalid internal line measurement" % record_id)
    return measured.lines[0]


def _fits(measured):
    return (
        measured.composer_pixels < layout.COMPOSER_WRAP_AT
        and measured.renderer_pixels <= layout.CANVAS_WIDTH_PIXELS
    )


def _validate_paragraph_whitespace(paragraph, record_id):
    if (
        paragraph.startswith(" ")
        or paragraph.endswith(" ")
        or "  " in paragraph
        or any(character in paragraph for character in "\t\r\n")
    ):
        raise WrapError(
            "%s uses leading, trailing, repeated or non-space whitespace"
            % record_id
        )


def _wrap_paragraph_greedy(font_rom, paragraph, record_id, runtime_contract):
    """Retain the established minimum-line, fill-first layout policy."""
    _validate_paragraph_whitespace(paragraph, record_id)
    words = paragraph.split(" ")
    lines = []
    current = ""
    for word in words:
        if not word:
            raise WrapError("%s contains an empty prose word" % record_id)
        candidate = word if not current else current + " " + word
        measured = _measure_line(font_rom, candidate, record_id, runtime_contract)
        if _fits(measured):
            current = candidate
            continue
        if not current:
            raise WrapError(
                "%s has an unbreakable word/control run wider than the dialogue canvas"
                % record_id
            )
        lines.append(current)
        current = word
        measured = _measure_line(font_rom, current, record_id, runtime_contract)
        if not _fits(measured):
            raise WrapError(
                "%s has an unbreakable word/control run wider than the dialogue canvas"
                % record_id
            )
    lines.append(current)
    return tuple(lines)


def _wrap_paragraph_balanced(font_rom, paragraph, record_id, runtime_contract):
    """Use the fewest safe lines, then avoid severely underfilled last lines."""
    _validate_paragraph_whitespace(paragraph, record_id)
    words = paragraph.split(" ")
    if any(not word for word in words):
        raise WrapError("%s contains an empty prose word" % record_id)

    candidates = {}
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            text = " ".join(words[start:end])
            measured = _measure_line(
                font_rom, text, record_id, runtime_contract
            )
            if not _fits(measured):
                break
            candidates[(start, end)] = (
                text,
                max(measured.composer_pixels, measured.renderer_pixels),
            )
        if (start, start + 1) not in candidates:
            raise WrapError(
                "%s has an unbreakable word/control run wider than the dialogue canvas"
                % record_id
            )

    # Prefer the fewest lines, then minimize squared unused width over every
    # line—including the last. Penalizing the last line avoids the tiny
    # orphans produced by greedy wrapping while retaining deterministic ties.
    best = {len(words): ((), ())}
    width_cap = layout.COMPOSER_WRAP_AT - 1
    for start in range(len(words) - 1, -1, -1):
        choices = []
        for end in range(start + 1, len(words) + 1):
            candidate = candidates.get((start, end))
            suffix = best.get(end)
            if candidate is None or suffix is None:
                continue
            text, width = candidate
            suffix_lines, suffix_widths = suffix
            lines = (text,) + suffix_lines
            widths = (width,) + suffix_widths
            score = (
                len(lines),
                sum((width_cap - value) ** 2 for value in widths),
                tuple(-value for value in widths),
                lines,
            )
            choices.append((score, lines, widths))
        if choices:
            _score, lines, widths = min(choices, key=lambda choice: choice[0])
            best[start] = (lines, widths)
    if 0 not in best:
        raise WrapError("%s cannot be wrapped safely" % record_id)
    return best[0][0]


def wrap_record(font_rom, record, draft, runtime_contract=None, balanced=True):
    """Return one generated record after proving all native constraints."""
    runtime_contract = runtime_contract or layout.english_runtime_width_contract()
    if not draft:
        raise WrapError("%s has a blank draft" % record.id)
    try:
        encoded = english.encode_source(draft)
    except ValueError as exc:
        raise WrapError("%s draft cannot be encoded: %s" % (record.id, exc)) from exc
    validate_control_contract(record, draft, encoded)

    output = []
    previous_boundary = None
    for piece in _BOUNDARY_RE.split(draft):
        if not piece:
            continue
        if piece in ("<page>", "<box>"):
            output.append(piece)
            previous_boundary = piece
            continue
        leading_break = previous_boundary == "<page>" and piece.startswith("<br>")
        if leading_break:
            piece = piece[len("<br>"):]
        continuation_space = (
            previous_boundary == "<page>" and piece.startswith(" ")
        )
        if continuation_space:
            # <page> scrolls the existing box; it does not start a new line.
            # Preserve one authored inter-sentence space across the control,
            # while still rejecting ordinary or repeated edge whitespace.
            piece = piece[1:]
        paragraphs = piece.split("<br>")
        if any(paragraph == "" for paragraph in paragraphs):
            raise WrapError(
                "%s has a leading, trailing or repeated <br> on a dialogue surface"
                % record.id
            )
        lines = []
        paragraph_wrapper = (
            _wrap_paragraph_balanced if balanced else _wrap_paragraph_greedy
        )
        for paragraph in paragraphs:
            lines.extend(
                paragraph_wrapper(
                    font_rom, paragraph, record.id, runtime_contract
                )
            )
        if len(lines) > DIALOGUE_LINE_LIMIT:
            raise WrapError(
                "%s needs %d dialogue lines; author an additional <page>/<box> boundary"
                % (record.id, len(lines))
            )
        output.append(
            ("<br>" if leading_break else "")
            + (" " if continuation_space else "")
            + "<br>".join(lines)
        )
        previous_boundary = None

    wrapped = "".join(output)
    wrapped_encoded = english.encode_source(wrapped)
    validate_physical_box_lines(record, wrapped_encoded)
    measured = layout.source_layout(
        font_rom,
        wrapped_encoded,
        mode=layout.SURFACE_PROFILES["dialogue"].representative_mode,
        runtime_contract=runtime_contract,
        record_id=record.id,
    )
    if not measured.safe:
        raise WrapError("%s failed final native layout validation" % record.id)
    return wrapped


def contract_summary(result, eligible, drafts, state):
    """Return a source-free fixture summary for the prose authoring contract."""
    ordered_drafts = tuple(drafts[row.record.id] for row in eligible)
    boundary_counts = Counter()
    effect_counts = Counter({"cF9": 0, "delay": 0})
    runtime_counts = Counter()
    dynamic_records = f6_records = 0
    for row in eligible:
        tokens = codec.parse_source(row.record.raw)
        dynamic = [token for token in tokens if token.kind == "source_control"]
        dynamic_records += bool(dynamic)
        f6_records += any(token.code == 0xF6 for token in dynamic)
        for token in dynamic:
            if token.code == 0xF4:
                runtime_counts["copy"] += 1
            elif token.code == 0xF5:
                runtime_counts["name"] += 1
            elif token.args[0] == 0x01:
                runtime_counts["lookup"] += 1
            elif token.args[0] == 0x03:
                runtime_counts["number"] += 1
            else:
                runtime_counts["sourceF6"] += 1
        for token in tokens:
            if token.code in (0xFB, 0xFC):
                boundary_counts[codec.CONTROLS[token.code]] += 1
            elif token.code in (0xF9, 0xFA):
                effect_counts[codec.CONTROLS[token.code]] += 1
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "source_free": True,
        "section": DRAFT_SECTION,
        "eligible_records": len(eligible),
        "eligible_sha1": eligible_sha1(eligible),
        "draft_records": sum(bool(row.draft) for row in ordered_drafts),
        "draft_sha1": draft_sha1(ordered_drafts),
        "generated_records": len(state["generated"]),
        "dynamic_records": dynamic_records,
        "f6_records": f6_records,
        "runtime_substitutions": dict(sorted(runtime_counts.items())),
        "source_boundaries": dict(sorted(boundary_counts.items())),
        "source_effects": dict(sorted(effect_counts.items())),
        "layout": {
            "composer_max_pixels": layout.COMPOSER_WRAP_AT - 1,
            "renderer_max_pixels": layout.CANVAS_WIDTH_PIXELS,
            "dialogue_lines_per_surface": DIALOGUE_LINE_LIMIT,
        },
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
    """Validate drafts and return a conflict-safe prospective workspace."""
    eligible = prose_rows(result)
    drafts = read_draft(draft_path, eligible)
    state = load_state(state_path, result, eligible)
    current = overlays.merge_english(result, catalog_dir, overlay_dir)
    records = {row.record.id: row.record for row in eligible}

    for record_id, hashes in state["generated"].items():
        row = drafts[record_id]
        if not row.draft:
            raise WrapError(
                "%s is wrapper-owned but its prose draft is now blank" % record_id
            )
        if _text_sha1(current.get(record_id, "")) != hashes["wrapped_sha1"]:
            raise WrapError(
                "%s generated English was edited outside the prose draft"
                % record_id
            )

    font_rom = english_font.install(source_rom)
    current_translated = translations.load_mapping(current, result["records"])
    runtime_analysis = runtime_widths.analyze(
        font_rom, result, current_translated
    )
    wrapped_by_id = {}
    next_generated = {}
    for row in (drafts[item.record.id] for item in eligible):
        if not row.draft:
            continue
        record = records[row.record_id]
        wrapped = wrap_record(
            font_rom, record, row.draft, runtime_contract=runtime_analysis.contract
        )
        old = state["generated"].get(row.record_id)
        existing = current.get(row.record_id, "")
        if old is None and existing and existing != wrapped:
            raise WrapError(
                "%s already has non-wrapper English; move it into the prose draft or clear it"
                % row.record_id
            )
        wrapped_by_id[row.record_id] = wrapped
        next_generated[row.record_id] = {
            "draft_sha1": _text_sha1(row.draft),
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
    return WrappedWorkspace(merged, wrapped_by_id, next_state, lint_summary)


def apply_workspace(result, workspace, catalog_dir, overlay_dir, state_path):
    """Rewrite both translation views from the one validated mapping."""
    organized = organize.classify(result)
    organize.write_outputs(result, catalog_dir, english_by_id=workspace.english_by_id)
    overlays.write_outputs(
        result, overlay_dir, organized, workspace.english_by_id
    )
    write_state(state_path, workspace.state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--translations", default=str(DEFAULT_OVERLAYS))
    parser.add_argument("--exceptions")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--init", action="store_true", help="create or refresh the source-free draft"
    )
    action.add_argument(
        "--apply", action="store_true", help="write validated wrapped rows to both catalogs"
    )
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)

    try:
        source_rom = Path(args.rom).read_bytes()
        result = extract.extract(source_rom)
        eligible = prose_rows(result)
        if args.init:
            drafts = refresh_draft(args.draft, eligible)
            state = load_state(
                args.state, result, eligible, allow_missing=True
            )
            write_state(args.state, state)
            measured = contract_summary(result, eligible, drafts, state)
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
                    result,
                    workspace,
                    args.catalog,
                    args.translations,
                    args.state,
                )
            drafts = read_draft(args.draft, eligible)
            measured = contract_summary(result, eligible, drafts, workspace.state)
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
        WrapError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    if args.json:
        print(json.dumps(measured, indent=2, sort_keys=True))
    else:
        print(
            "prose %s: %d eligible; %d drafted; %d generated; %d F6-bearing source record(s)"
            % (
                verb,
                measured["eligible_records"],
                measured["draft_records"],
                measured["generated_records"],
                measured["f6_records"],
            )
        )
        print("draft       %s" % args.draft)
        print("state       %s" % args.state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
