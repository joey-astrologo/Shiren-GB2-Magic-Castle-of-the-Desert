#!/usr/bin/env python3
"""Export the GB2 browser prose catalogue and check/import downloaded edits.

The public catalogue intentionally includes Japanese prose, as well as English,
font pixels, source contracts, and the Python wrapper's expected output. No ROM or
raw extraction file is published. The existing scene editor remains authoritative.
"""
import argparse
from collections import Counter
import difflib
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile

import codec
import allocate
import english
import english_font
import extract
import font as game_font
import layout
import lint_en
import overlays
import prose_editor
import prose_scenes
import runtime_widths
import translations
import translate_spells
import wrap_en

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs/translation-tool/prose"
CATALOG = SITE / "catalog.json"
FORMAT = "shiren-gb2-prose-edits-v1"
MAX_TEXT = 40000
RULE_FILES = (
    "tools/prose_web.py", "tools/prose_editor.py", "tools/prose_scenes.py",
    "tools/wrap_en.py", "tools/layout.py", "tools/english.py", "tools/codec.py",
    "tools/lint_en.py", "tools/runtime_widths.py", "tools/runtime_terms.py",
    "tools/translations.py", "tools/english_font.py", "data/kanji.tsv",
    "tools/translate_spells.py",
    "tools/allocate.py",
    "tools/font.py",
    "assets/fonts/thin_pixel_7_compact.json",
    "assets/fonts/thin_pixel_7_compact_glyphs.json",
    "docs/translation-tool/prose/rules.js",
    "script/en/lint_exceptions.json",
)


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def serialized(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_exceptions(issues, exceptions):
    keys = {issue.key for issue in issues}
    return lint_en.apply_exceptions(issues, [item for item in exceptions if item.key in keys])


def input_revision():
    paths = sorted(set(RULE_FILES) | {
        str(path.relative_to(ROOT)) for path in (ROOT / "script/en").glob("*.tsv")
    } | {"script/editing/prose.tsv", "script/drafts/prose_scenes.tsv"})
    return digest(serialized({name: sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in paths}))


def load_workspace(rom):
    result = extract.extract(rom)
    eligible = wrap_en.prose_rows(result)
    scenes = prose_scenes.build_scenes(result, prose_scenes.read_map())
    drafts = wrap_en.read_draft(wrap_en.DEFAULT_DRAFT, eligible)
    rows = prose_editor.read_editor(prose_editor.DEFAULT_EDITOR,
        prose_editor.expected_rows(result, scenes, drafts))
    current = overlays.merge_english(result, wrap_en.DEFAULT_CATALOG, wrap_en.DEFAULT_OVERLAYS)
    translated = translations.load_mapping(current, result["records"])
    font_rom = english_font.install(rom)
    contract = runtime_widths.analyze(font_rom, result, translated).contract
    exceptions = lint_en.load_exceptions(ROOT / "script/en/lint_exceptions.json", result)
    terms = lint_en.search_terms(lint_en.glossary_definitions(result, translated))
    return result, scenes, rows, current, font_rom, contract, exceptions, terms


def policy_contract(record, baseline):
    boundaries = wrap_en._boundary_shapes(record.raw)
    return {
        "unwaitedBoxes": sum(code == 0xFC and (i == 0 or boundaries[i - 1][0] != 0xFB)
                             for i, (code, _, _) in enumerate(boundaries)),
        "storyCodes": {code: len(re.findall(r"\b%s\b" % code, baseline))
                       for code in translate_spells.STORY_CODES.values()
                       if re.search(r"\b%s\b" % code, baseline)},
    }


def python_check(record, draft, font_rom, contract, terms, exceptions, baseline=None):
    if draft == prose_editor.EMPTY and not record.raw:
        return {"valid": True, "wrapped": "", "lines": [], "encodedBytes": 0}
    try:
        policy = policy_contract(record, draft if baseline is None else baseline)
        boundaries = re.findall(r"<(?:page|box)>", draft)
        unwaited = sum(token == "<box>" and (i == 0 or boundaries[i - 1] != "<page>")
                       for i, token in enumerate(boundaries))
        if unwaited > policy["unwaitedBoxes"]:
            raise ValueError("New dialogue boxes need <page><box> to preserve reading time")
        for code, count in policy["storyCodes"].items():
            if len(re.findall(r"\b%s\b" % code, draft)) != count:
                raise ValueError("Keep the exact Big Moai story code %s" % code)
        wrapped = wrap_en.wrap_record(font_rom, record, draft, runtime_contract=contract)
        translation = translations.load_mapping({record.id: wrapped}, (record,))[
            (record.bank, record.address)]
        issues = []
        for check in (lint_en.check_runtime_tokens, lint_en.check_native_template_selectors,
                      lint_en.check_native_soft_wrap, lint_en.check_sentence_spacing,
                      lint_en.check_japanese_quotes):
            issues.extend(check(record, translation))
        issues.extend(lint_en.check_terms(record, translation, terms))
        issues = lint_en.apply_exceptions(issues, [item for item in exceptions if item.record_id == record.id])
        if issues:
            raise ValueError(issues[0].detail)
        measured = layout.source_layout(font_rom, english.encode_source(wrapped),
            runtime_contract=contract, record_id=record.id)
        encoded_bytes = len(english.encode_source(wrapped))
        if encoded_bytes + 1 > allocate.BANK_SIZE:
            raise ValueError("This record exceeds a ROM bank; the project allocator needs an engineering change")
        return {"valid": True, "wrapped": wrapped, "encodedBytes": encoded_bytes, "lines": [
            [line.surface, line.line, line.composer_pixels, line.renderer_pixels]
            for line in measured.lines]}
    except ValueError as exc:
        return {"valid": False, "error": str(exc)}


def make_catalog(rom):
    result, scenes, rows, current, font_rom, contract, exceptions, terms = load_workspace(rom)
    approved = english_font.load_approved()
    by_id = {record.id: record for record in result["records"]}
    # Per-row term obligations are derived with the same longest-match masking
    # and reviewed exceptions as lint_en, rather than a second glossary policy.
    term_by_id = {term.glossary_id: term.english for term in terms}
    entries = []
    glyph_tokens = {}
    for row in rows:
        record = by_id[row["id"]]
        tokens = tuple(codec.parse_source(record.raw))
        runtime = {}
        for token in tokens:
            if token.kind == "source_control":
                bound = layout.dynamic_expansion(font_rom, token, 0, contract, record_id=record.id)
                runtime[codec.source_control_text(token)] = {
                    "composer": bound.composer_pixels, "renderer": bound.renderer_pixels,
                    "kind": bound.kind}
        dummy = translations.load_mapping({record.id: "placeholder"}, (record,))[
            (record.bank, record.address)]
        missing_terms = row_exceptions(lint_en.check_terms(record, dummy, terms), exceptions)
        boundaries = [[codec.CONTROLS[code], post_break, post_box]
                      for code, post_break, post_box in wrap_en._boundary_shapes(record.raw)]
        effects = Counter(codec.decode_source(token.raw) for token in tokens if token.code in (0xF9, 0xFA))
        native_runs = lint_en._native_template_selectors(record.raw)
        controls = {
            "boundaries": boundaries,
            "effects": dict(effects),
            "runtime": dict(lint_en.significant_tokens(record.raw)),
            "selectors": list(native_runs),
            "softWrap": any(token.code == 0xF3 for token in tokens),
        }
        expected = python_check(record, row["english"], font_rom, contract, terms, exceptions)
        if not expected["valid"]:
            raise ValueError("%s: baseline failed: %s" % (record.id, expected["error"]))
        draft = row["english"]
        if draft != prose_editor.EMPTY:
            for token in codec.parse_source(english.encode_source(draft)):
                if token.kind in ("glyph", "kanji"):
                    spelling = english.decode_source(token.raw)
                    if len(spelling) > 1:
                        glyph_tokens[spelling] = {
                            "bytes": len(token.raw),
                            "pixels": [list(line) for line in game_font.read_glyph(font_rom, token.raw).pixels],
                            "composer": layout.composer_advance(font_rom, token.raw),
                            "slices": list(layout.renderer_slice_advances(font_rom, token.raw))}
        sequence = ["<%s>%s" % (name, "<br> or <box>" if post else "")
                    for name, post, _ in boundaries]
        sequence += list(effects) + list(controls["runtime"])
        sequence += ["<cF8>" + run for run in native_runs]
        if controls["softWrap"]:
            sequence.append("<cF3>")
        entry = {
            "loc": record.id, "event": row["scene_id"], "draft": draft,
            "current": current.get(record.id, ""), "japanese": record.source,
            "editable": bool(record.raw), "speaker": "",
            "controls": controls, "runtime": runtime,
            "policy": policy_contract(record, draft),
            "terms": sorted({term_by_id[issue.related_id] for issue in missing_terms}),
            "reviewedOmissions": sorted({term_by_id[item.related_id] for item in exceptions
                if item.record_id == record.id and item.kind == "term_ignored"}),
            "sequence": sequence, "expected": expected,
        }
        speaker = re.match(r"((?:<name>|[A-Za-z][A-Za-z '?.-]*)):", draft)
        if speaker:
            entry["speaker"] = speaker.group(1)
        entry["base"] = digest(serialized(entry))
        entries.append(entry)
    font = {"name": approved.name, "glyphs": {
        char: {"advance": approved.advances[char],
               "rows": [int(row.replace(".", "0").replace("#", "1"), 2) for row in pixels],
               "pixels": [list(line) for line in english_font.glyph_pixels(pixels)]}
        for char, pixels in approved.rows.items()}}
    native = {}
    for char in "0123456789abcdefghijklmnopqrstuvwxyz":
        encoded = codec.encode_source(char)
        native[char] = {"composer": layout.composer_advance(font_rom, encoded),
                        "slices": list(layout.renderer_slice_advances(font_rom, encoded)),
                        "char": english.CODE_TO_ENGLISH.get(encoded[0])}
    units = allocate.build_units(result, translations.encoded_overrides(
        translations.load_mapping(current, result["records"])))
    allocation = {
        "bankSize": allocate.BANK_SIZE, "banks": len(allocate.FREE_BANKS),
        "tables": [unit.pointer_bytes for unit in units],
        "records": [[record.id, len(raw) + 1] for unit in units
                    for record, raw in zip(unit.records, unit.record_data)],
    }
    data = {
        "format": FORMAT, "inputRevision": input_revision(),
        "font": font, "nativeSelectors": native, "glyphTokens": glyph_tokens,
        "allocation": allocation,
        "rules": {"composerLimit": 143, "pixelLimit": 144, "lineLimit": 3,
                  "cellWidth": 8, "lineAdvance": 11,
                  "pageMarker": layout.renderer_advance(font_rom, bytes((layout.DIALOGUE_PAGE_MARKER_CODE,)))},
        "events": [{"id": scene.spec.scene_id, "name": scene.spec.title,
                    "phase": scene.spec.phase, "locs": list(scene.record_ids)} for scene in scenes],
        "records": entries,
    }
    # Includes derived runtime bounds and glossary terms as well as source code.
    data["rulesRevision"] = digest(serialized({
        "files": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in RULE_FILES},
        "font": font, "native": native, "glyphs": glyph_tokens, "allocation": allocation,
        "contracts": [[r["loc"], r["controls"], r["runtime"], r["policy"], r["terms"], r["reviewedOmissions"]] for r in entries]}))
    data["revision"] = digest(serialized(data))
    return data


def parse_edits(text, data):
    if len(text.encode("utf-8")) > 2_000_000:
        raise ValueError("Changes TSV is larger than 2 MB")
    metadata, bases, changes = {}, {}, {}
    for index, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if not line:
            continue
        if line.startswith("# "):
            fields = line[2:].split("\t")
            if len(fields) == 3 and fields[0] == "base":
                if fields[1] in bases:
                    raise ValueError("Duplicate baseline ID")
                bases[fields[1]] = fields[2]
            elif len(fields) == 2 and fields[0] in ("format", "revision", "rules"):
                if fields[0] in metadata:
                    raise ValueError("Duplicate metadata")
                metadata[fields[0]] = fields[1]
            elif fields != ["id", "english"]:
                raise ValueError("Unknown changes metadata on line %d" % index)
            continue
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] in changes:
            raise ValueError("Malformed or duplicate changes row on line %d" % index)
        changes[fields[0]] = fields[1]
    if (metadata.get("format") != FORMAT or metadata.get("rules") != data["rulesRevision"]
            or not re.fullmatch(r"[a-f0-9]{64}", metadata.get("revision", ""))
            or not changes or set(bases) != set(changes)):
        raise ValueError("Use a changes TSV from the GB2 editor with matching rules and baselines")
    records = {row["loc"]: row for row in data["records"]}
    for record_id, value in changes.items():
        row = records.get(record_id)
        if not row or not row["editable"] or row["base"] != bases[record_id]:
            raise ValueError("%s: unknown, read-only, or changed project baseline" % record_id)
        if len(value) > MAX_TEXT or not value:
            raise ValueError("%s: blank or oversized draft" % record_id)
    return changes


def import_file(rom_path, path, apply=False):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if data["inputRevision"] != input_revision():
        raise ValueError("Catalogue is stale; export the current project before importing")
    changes = parse_edits(Path(path).read_text(encoding="utf-8"), data)
    original_editor = prose_editor.DEFAULT_EDITOR.read_bytes()
    rom = Path(rom_path).read_bytes()
    result, scenes, rows, current, font_rom, contract, exceptions, terms = load_workspace(rom)
    by_id = {record.id: record for record in result["records"]}
    baselines = {row["id"]: row["english"] for row in rows}
    proposed_english = dict(current)
    for record_id, value in changes.items():
        checked = python_check(by_id[record_id], value, font_rom, contract, terms, exceptions, baselines[record_id])
        if not checked["valid"]:
            raise ValueError("%s: %s" % (record_id, checked["error"]))
        proposed_english[record_id] = checked["wrapped"]
    allocate.allocate(rom, record_overrides=translations.encoded_overrides(
        translations.load_mapping(proposed_english, result["records"])))
    proposed = [dict(row, english=changes.get(row["id"], row["english"])) for row in rows]
    with tempfile.TemporaryDirectory(prefix="gb2-web-import-") as directory:
        candidate = Path(directory) / "prose.tsv"
        prose_editor.write_editor(candidate, proposed)
        # Run the full owner: conflict state, all drafts, complete project lint.
        prose_editor.main([str(rom_path), "--editor", str(candidate)])
        before = prose_editor.DEFAULT_EDITOR.read_text(encoding="ascii")
        after = candidate.read_text(encoding="ascii")
        print("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
            fromfile="script/editing/prose.tsv", tofile="proposed prose.tsv")), end="")
        if apply:
            if prose_editor.DEFAULT_EDITOR.read_bytes() != original_editor:
                raise ValueError("The prose editor changed during import; rerun the check before applying")
            prose_editor.write_editor(prose_editor.DEFAULT_EDITOR, proposed)
            print("Updated the authoritative prose editor. Run prose_editor.py ROM --apply to synchronize and then build.")
        else:
            print("Checked; no project files changed. Use --apply to update the authoritative prose editor.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export")
    export.add_argument("rom")
    export.add_argument("--check", action="store_true")
    sub.add_parser("check-assets")
    importer = sub.add_parser("import")
    importer.add_argument("rom")
    importer.add_argument("tsv")
    importer.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "export":
            data = make_catalog(Path(args.rom).read_bytes())
            output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if args.check:
                if CATALOG.read_text(encoding="utf-8") != output:
                    raise ValueError("Catalogue is stale; run export again")
            else:
                CATALOG.parent.mkdir(parents=True, exist_ok=True)
                CATALOG.write_text(output, encoding="utf-8")
            print("%d prose records in %d scenes" % (len(data["records"]), len(data["events"])))
        elif args.action == "check-assets":
            data = json.loads(CATALOG.read_text(encoding="utf-8"))
            if data["inputRevision"] != input_revision():
                raise ValueError("Prose catalogue inputs changed; regenerate with the local ROM")
            print("Catalogue matches tracked project inputs")
        else:
            import_file(args.rom, args.tsv, args.apply)
    except (OSError, ValueError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
