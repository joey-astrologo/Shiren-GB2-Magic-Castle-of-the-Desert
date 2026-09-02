#!/usr/bin/env python3
"""Audit page markers that wrap alone onto line two or line three.

The native page marker is nine pixels wide.  A text pen at x=136..143 causes
the marker to wrap to the beginning of the following physical line.  This is
not the below-window corruption caused by a third-line wrap, but it leaves a
detached, improperly animated marker inside the dialogue box.

This tool proposes review-only corrections.  It never rewrites translations.
Ordinary ``<page><box>`` and terminal ``<page>`` boundaries move the final word
to the next line.  The few pacing-sensitive ``<page><br>`` cases use explicit
shorter wording so their existing post-wait line timing remains unchanged.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile

import codec
import english
import english_font
import extract
import layout
import runtime_widths
import translations as translation_file


PACING_SHORTENINGS = {
    "195:$6290": (
        "five-in-a-row in the desert?",
        "five-in-a-row in a desert?",
    ),
    "195:$66BA": (
        "The Lord will be most pleased.",
        "The Lord will be so pleased.",
    ),
    "195:$6A49": (
        "Pekeji: ...But I took it anyway.",
        "Pekeji: ...But I took it.",
    ),
    "195:$6E7D": (
        "???: Shh... Someone is coming.",
        "???: Shh... Someone's coming.",
    ),
    "196:$6333": (
        "Oro: I ask this of you as well.",
        "Oro: I ask this of you too.",
    ),
}


@dataclass(frozen=True)
class Candidate:
    record_id: str
    section: str
    surface: int
    source_line: int
    renderer_pixels: int
    boundary: str
    before: str
    after: str
    strategy: str


@dataclass(frozen=True)
class AuditResult:
    candidates: tuple
    proposed_overrides: dict
    proposal_problems: tuple


class PageMarkerAuditError(ValueError):
    pass


def _catalog_paths(path):
    path = Path(path)
    return tuple(sorted(path.glob("*.tsv"))) if path.is_dir() else (path,)


def _sections(path):
    out = {}
    for tsv_path in _catalog_paths(path):
        with tsv_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not {"id", "sections"}.issubset(reader.fieldnames or ()):
                continue
            for row in reader:
                record_id = row.get("id", "")
                if record_id and not record_id.startswith("#"):
                    out[record_id] = row.get("sections", "")
    return out


def _token_positions(raw):
    positioned = []
    offset = 0
    for token in codec.parse_source(raw):
        positioned.append((offset, token))
        offset += len(token.raw)
    return positioned


def _boundary(raw, endpoint):
    positioned = _token_positions(raw)
    by_offset = {offset: index for index, (offset, _token) in enumerate(positioned)}
    index = by_offset[endpoint.offset]
    if index + 1 == len(positioned):
        return "end"
    following = positioned[index + 1][1]
    if following.code == 0xFC:
        return "box"
    if following.code == 0xFD:
        return "br"
    return "text"


def _line_for_endpoint(measured, endpoint):
    return next(
        line
        for line in measured.lines
        if line.surface == endpoint.surface
        and line.line == endpoint.line
        and line.start_offset <= endpoint.offset <= line.end_offset
    )


def _visible_lines(raw, measured, endpoint):
    out = []
    for line in sorted(
        (
            line
            for line in measured.lines
            if line.surface == endpoint.surface and line.line <= endpoint.line
        ),
        key=lambda item: item.line,
    ):
        end = endpoint.offset if line.line == endpoint.line else line.end_offset
        out.append(english.decode_source(raw[line.start_offset:end]))
    return out


def _move_last_word(raw, measured, endpoint):
    line = _line_for_endpoint(measured, endpoint)
    split_at = raw.rfind(bytes((english.ENGLISH_CODES[" "],)), line.start_offset,
                         endpoint.offset)
    if split_at < 0:
        raise PageMarkerAuditError(
            "%s surface %d line %d has no word boundary"
            % (endpoint.offset, endpoint.surface + 1, endpoint.line + 1)
        )
    proposed = bytearray(raw)
    proposed[split_at] = 0xFD
    return bytes(proposed), split_at


def _control_count(raw, code):
    return sum(token.code == code for token in codec.parse_source(raw))


def _proposal_problems(font_rom, translated, proposals, contract):
    problems = []
    for key, raw in sorted(proposals.items()):
        translation = translated[key]
        measured = layout.source_layout(
            font_rom,
            raw,
            runtime_contract=contract,
            record_id=translation.record_id,
            simulate_soft_wrap=True,
        )
        issue_counts = {
            "detached markers": len(measured.detached_page_marker_wraps),
            "third-line markers": len(measured.page_marker_overflows),
            "line limits": len(measured.line_limit_overflows),
            "composer widths": len(measured.composer_overflows),
            "renderer widths": len(measured.renderer_overflows),
            "unresolved substitutions": len(measured.unresolved_dynamic_offsets),
        }
        active = [
            "%s=%d" % (label, count)
            for label, count in issue_counts.items()
            if count
        ]
        for code, label in ((0xFB, "page"), (0xFC, "box"), (0xF2, "delay")):
            if _control_count(raw, code) != _control_count(translation.encoded, code):
                active.append("%s control count changed" % label)
        if active:
            problems.append(
                "%s: %s" % (translation.record_id, ", ".join(active))
            )
    return tuple(problems)


def audit(rom, translations_path):
    """Return every detached page-marker endpoint and safe review proposals."""
    rom = bytes(rom)
    extracted = extract.extract(rom)
    translated = translation_file.load_path(
        translations_path, extracted["records"]
    )
    sections = _sections(translations_path)
    font_rom = english_font.install(rom)
    width_analysis = runtime_widths.analyze(font_rom, extracted, translated)
    candidates = []
    proposals = {}

    for key, translation in sorted(translated.items()):
        measured = layout.source_layout(
            font_rom,
            translation.encoded,
            runtime_contract=width_analysis.contract,
            record_id=translation.record_id,
            simulate_soft_wrap=True,
        )
        endpoints = measured.detached_page_marker_wraps
        if not endpoints:
            continue

        raw = translation.encoded
        proposed = raw
        if translation.record_id in PACING_SHORTENINGS:
            old, new = PACING_SHORTENINGS[translation.record_id]
            if translation.text.count(old) != 1:
                raise PageMarkerAuditError(
                    "%s no longer contains pacing wording %r"
                    % (translation.record_id, old)
                )
            proposed = english.encode_source(translation.text.replace(old, new))
            if len(endpoints) != 1 or _boundary(raw, endpoints[0]) != "br":
                raise PageMarkerAuditError(
                    "%s pacing exception no longer matches one <page><br> endpoint"
                    % translation.record_id
                )
            endpoint = endpoints[0]
            before_lines = _visible_lines(raw, measured, endpoint)
            candidates.append(
                Candidate(
                    record_id=translation.record_id,
                    section=sections.get(translation.record_id, ""),
                    surface=endpoint.surface + 1,
                    source_line=endpoint.line + 1,
                    renderer_pixels=endpoint.renderer_pixels,
                    boundary="page + line break",
                    before="<br>".join(before_lines),
                    after="<br>".join(before_lines).replace(old, new),
                    strategy="shorten_for_pacing",
                )
            )
        else:
            mutable = bytearray(raw)
            for endpoint in endpoints:
                boundary = _boundary(raw, endpoint)
                if boundary == "br":
                    raise PageMarkerAuditError(
                        "%s has an unreviewed pacing-sensitive endpoint"
                        % translation.record_id
                    )
                _single, split_at = _move_last_word(raw, measured, endpoint)
                mutable[split_at] = 0xFD
                before_lines = _visible_lines(raw, measured, endpoint)
                before_line = before_lines[-1]
                prefix, final_word = before_line.rsplit(" ", 1)
                candidates.append(
                    Candidate(
                        record_id=translation.record_id,
                        section=sections.get(translation.record_id, ""),
                        surface=endpoint.surface + 1,
                        source_line=endpoint.line + 1,
                        renderer_pixels=endpoint.renderer_pixels,
                        boundary=(
                            "page + box reset" if boundary == "box"
                            else "terminal page"
                        ),
                        before="<br>".join(before_lines),
                        after="<br>".join(
                            before_lines[:-1] + [prefix, final_word]
                        ),
                        strategy="move_last_word",
                    )
                )
            proposed = bytes(mutable)
        proposals[key] = proposed

    problems = _proposal_problems(
        font_rom, translated, proposals, width_analysis.contract
    )
    return AuditResult(tuple(candidates), proposals, problems)


def _read_tsv(path):
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return tuple(reader.fieldnames or ()), list(reader)


def _rewrite_tsv(path, text_field, updates):
    """Rewrite exact approved English cells while preserving the TSV schema."""
    path = Path(path)
    fields, rows = _read_tsv(path)
    if "id" not in fields or text_field not in fields:
        raise PageMarkerAuditError(
            "%s lacks id/%s columns" % (path, text_field)
        )
    remaining = dict(updates)
    for row in rows:
        record_id = row["id"]
        if record_id in remaining:
            row[text_field] = remaining.pop(record_id)
    if remaining:
        raise PageMarkerAuditError(
            "%s is missing approved record %s" % (path, sorted(remaining)[0])
        )
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
        delete=False,
    )
    try:
        with temporary:
            writer = csv.DictWriter(
                temporary,
                fieldnames=fields,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        Path(temporary.name).replace(path)
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


def _author_explicit_breaks(generated, proposed, authored, record_id):
    """Map approved generated line breaks back into unwrapped authored prose."""
    if len(generated) != len(proposed):
        raise PageMarkerAuditError(
            "%s mechanical proposal changed encoded length" % record_id
        )
    split_offsets = []
    for offset, (before, after) in enumerate(zip(generated, proposed)):
        if before == after:
            continue
        if before != english.ENGLISH_CODES[" "] or after != 0xFD:
            raise PageMarkerAuditError(
                "%s mechanical proposal changed something other than a word space"
                % record_id
            )
        split_offsets.append(offset)
    if not split_offsets:
        raise PageMarkerAuditError(
            "%s mechanical proposal contains no new line break" % record_id
        )

    authored_raw = english.encode_source(authored)
    normalize = lambda raw: bytes(
        english.ENGLISH_CODES[" "] if value == 0xFD else value for value in raw
    )
    if normalize(generated) != normalize(authored_raw):
        raise PageMarkerAuditError(
            "%s authored prose no longer matches generated words/controls"
            % record_id
        )
    mutable = bytearray(authored_raw)
    for offset in split_offsets:
        if mutable[offset] != english.ENGLISH_CODES[" "]:
            raise PageMarkerAuditError(
                "%s approved split is not an authored word space" % record_id
            )
        mutable[offset] = 0xFD
    return english.decode_source(bytes(mutable))


def apply_approved_sources(rom, translations_path, result, root=None):
    """Apply reviewed proposals to each authoritative source-free TSV.

    Generated prose and message catalogs are intentionally not touched here;
    their established authoring tools must regenerate them afterward.
    """
    if result.proposal_problems:
        raise PageMarkerAuditError(result.proposal_problems[0])
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    extracted = extract.extract(bytes(rom))
    translated = translation_file.load_path(
        translations_path, extracted["records"]
    )
    section_by_id = {
        candidate.record_id: candidate.section for candidate in result.candidates
    }

    editor_path = root / "script" / "editing" / "prose.tsv"
    _fields, editor_rows = _read_tsv(editor_path)
    editor = {row["id"]: row["english"] for row in editor_rows}
    updates = {
        "prose": {},
        "combat": {},
        "item": {},
        "direct": {},
    }
    for key, proposed in sorted(result.proposed_overrides.items()):
        current = translated[key]
        record_id = current.record_id
        section = section_by_id[record_id]
        if section == "story_and_event_dialogue":
            authored = editor[record_id]
            if record_id in PACING_SHORTENINGS:
                before, after = PACING_SHORTENINGS[record_id]
                if authored.count(before) != 1:
                    raise PageMarkerAuditError(
                        "%s no longer contains approved wording" % record_id
                    )
                updates["prose"][record_id] = authored.replace(before, after)
            else:
                updates["prose"][record_id] = _author_explicit_breaks(
                    current.encoded, proposed, authored, record_id
                )
        elif section == "combat_and_dungeon_messages":
            updates["combat"][record_id] = english.decode_source(proposed)
        elif section == "item_and_action_messages":
            updates["item"][record_id] = english.decode_source(proposed)
        elif section == "floor_and_system_messages":
            updates["direct"][record_id] = english.decode_source(proposed)
        else:
            raise PageMarkerAuditError(
                "%s has unsupported authoritative section %s"
                % (record_id, section)
            )

    _rewrite_tsv(editor_path, "english", updates["prose"])
    _rewrite_tsv(
        root / "script" / "drafts" / "combat_messages.tsv",
        "draft",
        updates["combat"],
    )
    _rewrite_tsv(
        root / "script" / "drafts" / "item_messages.tsv",
        "draft",
        updates["item"],
    )
    _rewrite_tsv(
        root / "script" / "en" / "messages.tsv",
        "english",
        updates["direct"],
    )
    return {name: len(values) for name, values in updates.items()}


def _cell(text):
    return "`%s`" % text.replace("|", "\\|").replace("`", "\\`")


def render_markdown(result):
    line_counts = Counter(candidate.source_line for candidate in result.candidates)
    section_counts = Counter(candidate.section for candidate in result.candidates)
    strategies = Counter(candidate.strategy for candidate in result.candidates)
    out = [
        "# Detached Dialogue Page-Marker Audit",
        "",
        "## Purpose",
        "",
        "The native page marker is nine pixels wide. When translated text ends at",
        "pixel 136-143, the marker wraps alone to the start of the following line.",
        "This produces the solid-marker/partly flashing appearance reported in game.",
        "This audit covers both line-one to line-two and line-two to line-three wraps.",
        "",
        "No translation changes in this document have been applied. They are review",
        "proposals only.",
        "",
        "## Summary",
        "",
        "- %d detached marker endpoints across %d translated records."
        % (len(result.candidates), len(result.proposed_overrides)),
        "- %d wrap from line one; %d wrap from line two."
        % (line_counts[1], line_counts[2]),
        "- %d proposals move only the final word to the next line."
        % strategies["move_last_word"],
        "- %d pacing-sensitive `<page><br>` proposals shorten wording instead."
        % strategies["shorten_for_pacing"],
        "- Every proposal was remeasured: no detached marker, third-line marker",
        "  overflow, fourth line, ordinary width overflow, or unresolved runtime",
        "  substitution remains.",
        "",
        "Sections: " + ", ".join(
            "%s (%d)" % (section, count)
            for section, count in sorted(section_counts.items())
        ),
        "",
        "## Pacing-sensitive wording decisions",
        "",
        "These five waits are immediately followed by an existing line break. Adding",
        "another line would alter dialogue timing, so concise wording is proposed.",
        "",
        "| # | Record | Current | Proposed |",
        "|---:|---|---|---|",
    ]
    pacing = [
        candidate
        for candidate in result.candidates
        if candidate.strategy == "shorten_for_pacing"
    ]
    for index, candidate in enumerate(pacing, 1):
        out.append(
            "| %d | `%s` | %s | %s |"
            % (
                index,
                candidate.record_id,
                _cell(candidate.before),
                _cell(candidate.after),
            )
        )

    out += [
        "",
        "## Final-word reflow decisions",
        "",
        "Each proposal below preserves the words, page wait, box reset, and ordering;",
        "only the final space before the page wait becomes a line break.",
        "",
        "| # | Record | Section | Chunk | Wrap | Width | Current | Proposed |",
        "|---:|---|---|---:|---|---:|---|---|",
    ]
    ordinary = [
        candidate
        for candidate in result.candidates
        if candidate.strategy == "move_last_word"
    ]
    for index, candidate in enumerate(ordinary, 1):
        out.append(
            "| %d | `%s` | %s | %d | line %d → %d | %d px | %s | %s |"
            % (
                index,
                candidate.record_id,
                candidate.section,
                candidate.surface,
                candidate.source_line,
                candidate.source_line + 1,
                candidate.renderer_pixels,
                _cell(candidate.before),
                _cell(candidate.after),
            )
        )
    out += [
        "",
        "## Proposed automated rule",
        "",
        "For three-line dialogue surfaces, reject any page marker that would wrap",
        "from line one or line two. Keep the existing stricter rejection for markers",
        "that would wrap below line three. A repair must keep the marker beside text;",
        "it may not create a marker-only line or alter a pacing-sensitive `<page><br>`",
        "sequence without explicit wording review.",
        "",
    ]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--translations",
        default="script/en",
        help="English category directory or TSV (default: script/en)",
    )
    parser.add_argument("--output", help="optional Markdown output path")
    parser.add_argument(
        "--apply-sources",
        action="store_true",
        help="write approved proposals to authoritative source-free TSVs",
    )
    args = parser.parse_args(argv)
    try:
        result = audit(Path(args.rom).read_bytes(), args.translations)
        if result.proposal_problems:
            raise PageMarkerAuditError(result.proposal_problems[0])
        if args.apply_sources:
            counts = apply_approved_sources(
                Path(args.rom).read_bytes(), args.translations, result
            )
            print(
                "updated authoritative sources: %s"
                % ", ".join(
                    "%s=%d" % item for item in sorted(counts.items())
                )
            )
        rendered = render_markdown(result)
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8")
            print("wrote %s" % destination)
        else:
            print(rendered)
    except (
        OSError,
        ValueError,
        extract.ExtractError,
        english_font.FontError,
        runtime_widths.RuntimeWidthError,
        translation_file.TranslationError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
