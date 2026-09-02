#!/usr/bin/env python3
"""Lint GB2 English translations for silent content-consistency failures.

Encoding proves that an English cell can become bytes.  It cannot prove that a
runtime substitution survived or that one Japanese name did not become two
different English names.  This module closes those gaps from the authoritative
ROM extraction and the semantic partition in :mod:`organize`.

The production glossary is derived rather than copied: term definitions are the
records already assigned to name-like glossary sections.  That leaves no second
Japanese glossary file to drift.  Only stable IDs, issue kinds and written
reasons appear in the optional tracked exception file.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
import json
from pathlib import Path
import re
import sys

import codec
import english
import extract
import organize
import translations as translation_file


SCHEMA = "shiren-gb2-translation-lint-v1"
EXCEPTION_SCHEMA = "shiren-gb2-lint-exceptions-v1"
EXCEPTION_FILENAME = "lint_exceptions.json"
MIN_SOURCE_TERM_LENGTH = 3
JAPANESE_QUOTE_GLYPHS = frozenset(
    (bytes.fromhex("F198"), bytes.fromhex("F19A"),
     bytes.fromhex("F224"), bytes.fromhex("F226"))
)

# These sections define reusable terms.  Collision checks are scoped by family:
# an actor and an item may intentionally share a rendering, while two distinct
# actors with one English name would be indistinguishable in runtime messages.
TERM_FAMILIES = {
    "actor_names_tier_1": "actor",
    "actor_names_tier_2": "actor",
    "actor_names_tier_3": "actor",
    "identified_item_names": "item",
    "unidentified_item_appearances": "appearance",
    "item_ability_roots": "ability",
    "location_names": "location",
    "numbered_monster_variant_names": "actor",
    "trap_names": "trap",
}

# Ability roots include ordinary words such as "power" and "explanation"; the
# numbered variants often contain dynamic controls.  They remain definitions for
# split/collision checks but are not blindly imposed on prose.  The remaining
# families are concrete names observed across messages and dialogue.
SEARCHABLE_SECTIONS = frozenset(
    {
        "actor_names_tier_1",
        "actor_names_tier_2",
        "actor_names_tier_3",
        "identified_item_names",
        "unidentified_item_appearances",
        "location_names",
        "trap_names",
    }
)

# Actor slot 140 is the internal speaker label ``せつめい`` (explanation), not
# a proper noun that prose containing the ordinary word must repeat verbatim.
# Keep it in actor collision/split checks while excluding it from prose search.
NON_SEARCHABLE_DEFINITION_IDS = frozenset({"192:$4F4F"})

EXCEPTABLE_KINDS = frozenset(
    {"glossary_collision", "glossary_split", "term_ignored"}
)

_MARKUP = re.compile(r"<[^>]+>|\{[^{}]+\}")


class TranslationLintError(ValueError):
    """The English workspace violates a translation content contract."""


@dataclass(frozen=True, order=True)
class Issue:
    record_id: str
    kind: str
    related_id: str
    detail: str

    @property
    def key(self):
        return self.record_id, self.kind, self.related_id


@dataclass(frozen=True)
class LintException:
    record_id: str
    kind: str
    related_id: str
    reason: str

    @property
    def key(self):
        return self.record_id, self.kind, self.related_id


@dataclass(frozen=True)
class GlossaryDefinition:
    record_id: str
    source: str
    english: str
    sections: tuple
    families: tuple
    searchable: bool


@dataclass(frozen=True)
class SearchTerm:
    source: str
    english: str
    glossary_id: str


def _translations_by_id(translated):
    return {entry.record_id: entry for entry in translated.values()}


def glossary_definitions(result, translated):
    """Return term definitions derived from the proven semantic partition."""
    by_id = _translations_by_id(translated)
    out = []
    for row in organize.classify(result):
        sections = tuple(
            sorted(section for section in row.sections if section in TERM_FAMILIES)
        )
        if not sections:
            continue
        entry = by_id.get(row.record.id)
        english = ""
        if entry is not None and not entry.explicit_empty:
            english = entry.text
        out.append(
            GlossaryDefinition(
                record_id=row.record.id,
                source=row.record.source,
                english=english,
                sections=sections,
                families=tuple(sorted({TERM_FAMILIES[s] for s in sections})),
                searchable=(
                    bool(set(sections) & SEARCHABLE_SECTIONS)
                    and row.record.id not in NON_SEARCHABLE_DEFINITION_IDS
                ),
            )
        )
    return tuple(out)


def _pair_issue(kind, first, second, detail):
    left, right = sorted((first, second))
    return Issue(left, kind, right, detail)


def check_glossary(definitions):
    """Find split Japanese terms and within-family English collisions."""
    issues = {}
    by_source = defaultdict(list)
    for definition in definitions:
        if definition.english:
            by_source[definition.source].append(definition)

    for entries in by_source.values():
        for first, second in combinations(entries, 2):
            if first.english == second.english:
                continue
            issue = _pair_issue(
                "glossary_split",
                first.record_id,
                second.record_id,
                "the same Japanese glossary source is rendered as %r and %r"
                % (first.english, second.english),
            )
            issues[issue.key] = issue

    by_rendering = defaultdict(list)
    for definition in definitions:
        if not definition.english:
            continue
        normalized = " ".join(definition.english.split()).casefold()
        for family in definition.families:
            by_rendering[(family, normalized)].append(definition)
    for (family, _normalized), entries in by_rendering.items():
        for first, second in combinations(entries, 2):
            if first.source == second.source:
                continue
            issue = _pair_issue(
                "glossary_collision",
                first.record_id,
                second.record_id,
                "%s glossary sources both render as %r"
                % (family, first.english),
            )
            issues[issue.key] = issue
    return tuple(sorted(issues.values()))


def significant_tokens(raw):
    """Return exact runtime substitutions that English may not add or remove."""
    out = Counter()
    for token in codec.parse_source(raw):
        if token.kind == "source_control":
            out[codec.source_control_text(token)] += 1
    return out


def check_runtime_tokens(record, translation):
    """Return token parity issues for one translated record."""
    if translation.explicit_empty:
        return ()
    wanted = significant_tokens(record.raw)
    got = significant_tokens(translation.encoded)
    issues = []
    for token in sorted(set(wanted) | set(got)):
        before, after = wanted[token], got[token]
        if before == after:
            continue
        kind = "token_lost" if after < before else "token_added"
        issues.append(
            Issue(
                record.id,
                kind,
                "",
                "%s appears %d time(s) in the Japanese source and %d in English"
                % (token, before, after),
            )
        )
    return tuple(issues)


def _native_template_selectors(raw):
    """Return ordered native 0-9/a-z selector runs introduced by F8.

    F8 itself is a renderer no-op, but the surrounding event/menu template
    code treats the following native Latin bytes as variable selectors before
    ordinary rendering.  Their byte identities therefore belong to the
    runtime contract even though they look like editable Latin text.
    """
    runs = []
    current = None
    for token in codec.parse_source(raw):
        if token.kind == "control" and token.code == 0xF8:
            if current is not None:
                runs.append("".join(current))
            current = []
            continue
        if current is not None and token.kind == "glyph":
            native = codec.decode_source(token.raw)
            if len(native) == 1 and (
                "0" <= native <= "9" or "a" <= native <= "z"
            ):
                current.append(native)
                continue
        if current is not None:
            runs.append("".join(current))
            current = None
    if current is not None:
        runs.append("".join(current))
    return tuple(runs)


def check_native_template_selectors(record, translation):
    """Require F8-prefixed runtime selectors to remain byte-exact."""
    wanted = _native_template_selectors(record.raw)
    if not wanted:
        return ()
    got = (
        ()
        if translation.explicit_empty
        else _native_template_selectors(translation.encoded)
    )
    if got == wanted:
        return ()
    return (
        Issue(
            record.id,
            "template_selector_changed",
            "",
            "native F8 selector run(s) changed from %r to %r"
            % (wanted, got),
        ),
    )


def _control_count(raw, code):
    return sum(
        token.kind == "control" and token.code == code
        for token in codec.parse_source(raw)
    )


def check_native_soft_wrap(record, translation):
    """Require English to retain a native F3 checkpoint from Japanese.

    F3 is a conditional rollback point, not a forced line break. English may
    need more checkpoints after reordering or expanding a sentence, but it may
    not discard the source record's native wrapping behavior altogether.
    """
    wanted = _control_count(record.raw, 0xF3)
    if not wanted:
        return ()
    got = 0 if translation.explicit_empty else _control_count(translation.encoded, 0xF3)
    if got:
        return ()
    return (
        Issue(
            record.id,
            "soft_wrap_lost",
            "",
            "<cF3> appears %d time(s) in the Japanese source but not in English; "
            "retain at least one native conditional wrap checkpoint" % wanted,
        ),
    )


def check_sentence_spacing(record, translation):
    """Find a word joined to ``?`` or ``!`` on the same physical line."""
    if translation.explicit_empty:
        return ()
    tokens = tuple(codec.parse_source(translation.encoded))
    for index, token in enumerate(tokens):
        punctuation = english.CODE_TO_ENGLISH.get(token.code)
        if punctuation not in ("?", "!"):
            continue
        crossed = []
        for following in tokens[index + 1:]:
            if following.kind == "control":
                if following.code in (0xFC, 0xFD):
                    break
                crossed.append(codec.CONTROLS.get(following.code, "control"))
                continue
            character = english.CODE_TO_ENGLISH.get(following.code)
            if character == " ":
                break
            if character and character.isalnum():
                suffix = (
                    " across <%s>" % "><".join(crossed) if crossed else ""
                )
                return (
                    Issue(
                        record.id,
                        "sentence_spacing",
                        "",
                        "%s is joined to the following word%s; insert one space"
                        % (
                            "question mark"
                            if punctuation == "?"
                            else "exclamation mark",
                            suffix,
                        ),
                    ),
                )
            break
    return ()


def check_japanese_quotes(record, translation):
    """Reject native corner/speaker quote glyphs from localized text."""
    if translation.explicit_empty:
        return ()
    found = tuple(
        token.raw
        for token in codec.parse_source(translation.encoded)
        if token.raw in JAPANESE_QUOTE_GLYPHS
    )
    if not found:
        return ()
    names = tuple(codec.decode_source(raw) for raw in found)
    return (
        Issue(
            record.id,
            "japanese_quote_glyph",
            "",
            "%s use(s) native Japanese quote artwork; use straight ASCII \""
            % ", ".join(names),
        ),
    )


def _plain_search_source(source):
    return (
        "<" not in source
        and "{" not in source
        and len("".join(source.split())) >= MIN_SOURCE_TERM_LENGTH
    )


def search_terms(definitions):
    """Return every searchable source term, longest first.

    Untranslated and split definitions remain in the result with blank English.
    They still mask shorter glossary strings nested inside them, preventing a
    partially translated glossary from producing false terminology failures.
    """
    by_source = defaultdict(list)
    for definition in definitions:
        if definition.searchable and _plain_search_source(definition.source):
            by_source[definition.source].append(definition)
    out = []
    for source, entries in by_source.items():
        translations = {entry.english for entry in entries if entry.english}
        english = next(iter(translations)) if len(translations) == 1 else ""
        out.append(
            SearchTerm(
                source=source,
                english=english,
                glossary_id=min(entry.record_id for entry in entries),
            )
        )
    return tuple(sorted(out, key=lambda term: (-len(term.source), term.source)))


def flatten_english(text):
    """Remove renderer markup and normalize spacing for term matching."""
    return " ".join(_MARKUP.sub(" ", text).split()).casefold()


def check_terms(record, translation, terms):
    """Find frozen terms present in source but absent from translated English."""
    if translation.explicit_empty:
        return ()
    source = record.source
    mask = [False] * len(source)
    rendered = flatten_english(translation.text)
    missing = {}
    for term in terms:
        start = 0
        matched = False
        while True:
            at = source.find(term.source, start)
            if at < 0:
                break
            start = at + 1
            stop = at + len(term.source)
            if any(mask[at:stop]):
                continue
            mask[at:stop] = [True] * len(term.source)
            matched = True
        if not matched or not term.english:
            continue
        if flatten_english(term.english) not in rendered:
            issue = Issue(
                record.id,
                "term_ignored",
                term.glossary_id,
                "source contains the glossary term at %s, frozen as %r, but English does not"
                % (term.glossary_id, term.english),
            )
            missing[issue.key] = issue
    return tuple(sorted(missing.values()))


def default_exceptions_path(translations_path):
    path = Path(translations_path)
    return path / EXCEPTION_FILENAME if path.is_dir() else None


def load_exceptions(path, result):
    """Load reviewed, source-free issue exceptions from JSON."""
    if path is None:
        return ()
    path = Path(path)
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != EXCEPTION_SCHEMA:
        raise TranslationLintError("%s has unsupported exception schema" % path)
    rows = data.get("exceptions")
    if not isinstance(rows, list):
        raise TranslationLintError("%s exceptions must be a list" % path)
    known = {record.id for record in result["records"]}
    out = []
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise TranslationLintError("%s exception %d must be an object" % (path, index))
        record_id = row.get("id", "")
        kind = row.get("kind", "")
        related_id = row.get("related_id", "")
        reason = row.get("reason", "").strip()
        if record_id not in known or related_id not in known:
            raise TranslationLintError(
                "%s exception %d names an unknown stable ID" % (path, index)
            )
        if kind not in EXCEPTABLE_KINDS:
            raise TranslationLintError(
                "%s exception %d has unsupported kind %r" % (path, index, kind)
            )
        if not reason:
            raise TranslationLintError(
                "%s exception %d needs a written reason" % (path, index)
            )
        exception = LintException(record_id, kind, related_id, reason)
        if exception.key in seen:
            raise TranslationLintError(
                "%s duplicates exception %s/%s/%s"
                % ((path,) + exception.key)
            )
        seen.add(exception.key)
        out.append(exception)
    return tuple(out)


def apply_exceptions(issues, exceptions):
    """Suppress exact reviewed issues and reject exceptions that went stale."""
    remaining = {issue.key: issue for issue in issues}
    stale = []
    for exception in exceptions:
        if exception.key in remaining:
            del remaining[exception.key]
        else:
            stale.append(
                Issue(
                    exception.record_id,
                    "stale_exception",
                    exception.related_id,
                    "reviewed %s exception no longer matches a lint issue"
                    % exception.kind,
                )
            )
    return tuple(sorted(tuple(remaining.values()) + tuple(stale)))


def check(result, translated, exceptions=()):
    """Return all unsuppressed translation issues in deterministic order."""
    by_record = {(record.bank, record.address): record for record in result["records"]}
    definitions = glossary_definitions(result, translated)
    definition_ids = {definition.record_id for definition in definitions}
    terms = search_terms(definitions)
    issues = list(check_glossary(definitions))
    for key, translation in translated.items():
        record = by_record[key]
        issues.extend(check_runtime_tokens(record, translation))
        issues.extend(check_native_template_selectors(record, translation))
        issues.extend(check_native_soft_wrap(record, translation))
        issues.extend(check_sentence_spacing(record, translation))
        issues.extend(check_japanese_quotes(record, translation))
        if record.id not in definition_ids:
            issues.extend(check_terms(record, translation, terms))
    unique = {issue.key: issue for issue in issues}
    return apply_exceptions(tuple(unique.values()), exceptions)


def _runtime_kind(token):
    if token.code == 0xF4:
        return "copy"
    if token.code == 0xF5:
        return "name"
    if token.args[0] == 0x01:
        return "lookup"
    if token.args[0] == 0x03:
        return "number"
    return "sourceF6"


def summary(result, translated, issues=(), exceptions=()):
    """Return a source-free census of the lint contract and current progress."""
    definitions = glossary_definitions(result, translated)
    source_groups = Counter(definition.source for definition in definitions)
    family_counts = Counter()
    searchable = []
    for definition in definitions:
        family_counts.update(definition.families)
        if definition.searchable:
            searchable.append(definition)
    plain_terms = {
        definition.source
        for definition in searchable
        if _plain_search_source(definition.source)
    }

    runtime_kinds = Counter()
    runtime_records = 0
    for record in result["records"]:
        found = 0
        for token in codec.parse_source(record.raw):
            if token.kind == "source_control":
                runtime_kinds[_runtime_kind(token)] += 1
                found += 1
        runtime_records += bool(found)

    records_by_key = {
        (record.bank, record.address): record for record in result["records"]
    }
    native_soft_wrap_translated_records = 0
    native_soft_wrap_source_markers = 0
    native_soft_wrap_preserved_records = 0
    native_soft_wrap_english_markers = 0
    for key, translation in translated.items():
        record = records_by_key[key]
        source_markers = _control_count(record.raw, 0xF3)
        if not source_markers:
            continue
        english_markers = (
            0
            if translation.explicit_empty
            else _control_count(translation.encoded, 0xF3)
        )
        native_soft_wrap_translated_records += 1
        native_soft_wrap_source_markers += source_markers
        native_soft_wrap_preserved_records += bool(english_markers)
        native_soft_wrap_english_markers += english_markers

    issue_kinds = Counter(issue.kind for issue in issues)
    return {
        "schema": SCHEMA,
        "records": len(result["records"]),
        "translated_records": len(translated),
        "explicit_empty_records": sum(
            entry.explicit_empty for entry in translated.values()
        ),
        "glossary_definition_records": len(definitions),
        "translated_glossary_records": sum(bool(item.english) for item in definitions),
        "glossary_families": dict(sorted(family_counts.items())),
        "duplicate_source_groups": sum(count > 1 for count in source_groups.values()),
        "records_in_duplicate_source_groups": sum(
            count for count in source_groups.values() if count > 1
        ),
        "searchable_definition_records": len(searchable),
        "searchable_plain_source_terms": len(plain_terms),
        "minimum_search_term_length": MIN_SOURCE_TERM_LENGTH,
        "runtime_substitution_records": runtime_records,
        "runtime_substitution_tokens": sum(runtime_kinds.values()),
        "runtime_substitution_kinds": dict(sorted(runtime_kinds.items())),
        "native_soft_wrap_translated_records": native_soft_wrap_translated_records,
        "native_soft_wrap_source_markers": native_soft_wrap_source_markers,
        "native_soft_wrap_preserved_records": native_soft_wrap_preserved_records,
        "native_soft_wrap_english_markers": native_soft_wrap_english_markers,
        "reviewed_exceptions": len(exceptions),
        "problems": len(issues),
        "problem_kinds": dict(sorted(issue_kinds.items())),
    }


def require_clean(result, translated, exceptions=()):
    """Return the clean summary or raise with the first actionable issue."""
    issues = check(result, translated, exceptions)
    if issues:
        first = issues[0]
        related = " / %s" % first.related_id if first.related_id else ""
        raise TranslationLintError(
            "%d translation lint problem(s); first: %s%s %s: %s"
            % (len(issues), first.record_id, related, first.kind, first.detail)
        )
    return summary(result, translated, issues, exceptions)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--translations",
        default="script/en",
        help="English TSV or category directory (default: script/en)",
    )
    parser.add_argument(
        "--exceptions",
        help="reviewed exception JSON (default: lint_exceptions.json beside a directory)",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--tsv", action="store_true", help="machine-readable issue rows")
    output.add_argument("--json", action="store_true", help="JSON summary and issue rows")
    args = parser.parse_args(argv)
    try:
        result = extract.extract(Path(args.rom).read_bytes())
        translated = translation_file.load_path(
            args.translations, result["records"]
        )
        exception_path = (
            Path(args.exceptions)
            if args.exceptions
            else default_exceptions_path(args.translations)
        )
        exceptions = load_exceptions(exception_path, result)
        issues = check(result, translated, exceptions)
        measured = summary(result, translated, issues, exceptions)
    except (
        OSError,
        ValueError,
        extract.ExtractError,
        translation_file.TranslationError,
        TranslationLintError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    if args.json:
        print(
            json.dumps(
                {
                    "summary": measured,
                    "issues": [asdict(issue) for issue in issues],
                },
                indent=2,
            )
        )
    elif args.tsv:
        print("id\tkind\trelated_id\tdetail")
        for issue in issues:
            print(
                "%s\t%s\t%s\t%s"
                % (
                    issue.record_id,
                    issue.kind,
                    issue.related_id,
                    issue.detail.replace("\t", " "),
                )
            )
    else:
        for issue in issues:
            related = " / %s" % issue.related_id if issue.related_id else ""
            print("%-12s%s  %s" % (issue.record_id, related, issue.kind))
            print("    %s" % issue.detail)
        print(
            "lint_en: %d translated; %d glossary definitions; %d exception(s); %d problem(s)"
            % (
                measured["translated_records"],
                measured["glossary_definition_records"],
                measured["reviewed_exceptions"],
                measured["problems"],
            )
        )
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
