#!/usr/bin/env python3
"""Publish the complete GB2 text census and import subject-workbench edits.

All geometry, ownership, terminology and runtime domains come from the project
owners. Unconfirmed/composite surfaces stay visible with a reason, not an
invented editable contract. The public snapshot contains text and font data,
never a ROM, save, machine code or the raw extraction.
"""
import argparse
import csv
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import difflib
import os
from pathlib import Path
import re
import sys
import tempfile
from dataclasses import replace
from html import escape

import allocate
import blank_scroll
import codec
import combat_messages
import english
import english_font
import extract
import font as game_font
import layout
import lint_en
import menu_text
import organize
import overlays
import prose_editor
import prose_web
import runtime_widths
import translations
import unidentified_names
import wrap_en
import wrap_item_messages

ROOT = prose_web.ROOT
SITE = ROOT / "docs/translation-tool/workbench"
CATALOG = SITE / "catalog.json"
FORMAT = "shiren-gb2-workbench-edits-v1"
SUBJECTS = (
    ("prose", "Prose", "Story and event dialogue in the project's 72 scenes."),
    ("items", "Item names and appearances", "Identified names, unidentified appearances and canonical recall roots."),
    ("names", "Monsters and characters", "Actor names, monster tiers and numbered variants."),
    ("descriptions", "Item descriptions", "Item details with their title and stat headers."),
    ("abilities", "Equipment abilities", "Ability descriptions and their positioned text limits."),
    ("places", "Locations and traps", "Location names, dungeon names and traps."),
    ("monsters", "Monster descriptions", "Monster Notebook entries and meat descriptions."),
    ("menus", "Menus and system text", "Commands, status, history, rankings and positioned labels."),
    ("help", "Help and guides", "Wanderer's Guide, controls, techniques and Secrets."),
    ("messages", "Gameplay messages", "Combat, items, shops and other dungeon messages."),
    ("ending", "Ending and credits", "Extracted ending dialogue and credit text."),
    ("reference", "Internal and fixed text", "Engine labels, password data, unused slots and extraction references."),
)
RULE_FILES = tuple(sorted(set(prose_web.RULE_FILES) | {
    "tools/workbench_web.py", "tools/organize.py", "tools/overlays.py", "tools/extract.py",
    "tools/build.py", "tools/menu_text.py", "tools/surfaces.py", "tools/combat_messages.py",
    "tools/wrap_item_messages.py", "tools/wrap_items.py", "tools/blank_scroll.py",
    "tools/unidentified_names.py", "tools/stairs_menu.py", "tools/service_menus.py",
    "tools/item_formatting.py", "tools/ending_credits.py", "tools/credit_screen.py",
    "docs/translation-tool/workbench/rules.js",
}))


def input_revision():
    paths = set(RULE_FILES) | {str(p.relative_to(ROOT)) for folder in
        ("script/en", "script/editing", "script/drafts") for p in (ROOT / folder).glob("*")
        if p.suffix in (".tsv", ".json")}
    return prose_web.digest(prose_web.serialized({name: sha256((ROOT / name).read_bytes()).hexdigest()
                                                for name in sorted(paths)}))


def subject_for(row):
    section = row.sections[0]
    if row.category == "glossary":
        if section in ("identified_item_names", "unidentified_item_appearances", "item_ability_roots"):
            return "items"
        if section == "item_ability_descriptions": return "abilities"
        if section in ("location_names", "trap_names"): return "places"
        return "names"
    return {"items": "descriptions", "ui_system": "menus", "internal": "reference",
            "review": "reference", "prose": "ending" if section == "ending_and_credits_text" else "prose"}.get(row.category, row.category)


def positioned_contracts(rom):
    import build as rom_build
    contracts = {}
    for owner in (rom_build._item_ability_positioned_contracts, rom_build._item_action_positioned_contracts,
                  rom_build._status_condition_positioned_contracts, rom_build._front_end_positioned_contracts,
                  rom_build._stairs_menu_positioned_contracts, rom_build._service_menu_positioned_contracts):
        for key, value in owner(rom).items(): contracts.setdefault(key, []).append(list(value))
    left, right = rom_build._main_menu_positioned_contracts(rom)
    for key, value in left.items(): contracts.setdefault(key, []).append(list(value))
    return contracts, right


def make_catalog(rom):
    import build as rom_build
    result, scenes, editor, current, font_rom, contract, exceptions, terms = prose_web.load_workspace(rom)
    prose = json.loads(prose_web.CATALOG.read_text())
    if prose["inputRevision"] != prose_web.input_revision():
        raise ValueError("Regenerate the prose catalogue first")
    prose_rows = {r["loc"]: r for r in prose["records"]}
    translated = translations.load_mapping(current, result["records"])
    analysis = runtime_widths.analyze(font_rom, result, translated)
    by_ref = {(ref.group, ref.index): r for r in result["records"] for ref in r.references}
    modes = rom_build._full_renderer_surface_modes(rom)
    positioned, right = positioned_contracts(rom)
    combat = {row.record.id: row for row in combat_messages.message_rows(result)}
    combat_drafts = combat_messages.read_draft(combat_messages.DEFAULT_DRAFT, tuple(combat.values()))
    item_rows = wrap_item_messages.message_rows(result)
    item_drafts = wrap_item_messages.read_draft(wrap_item_messages.DEFAULT_DRAFT, item_rows)
    width_ids = {key for f in analysis.families.values() for key in f.record_ids}
    definitions = lint_en.glossary_definitions(result, translated)
    # Term IDs survive coordinated renames. Source matching/masking is independent of English.
    dummy_terms = tuple(lint_en.SearchTerm(t.source, "WORKBENCH_MISSING_TERM", t.glossary_id) for t in terms)
    entries, events = [], []
    glyphs = dict(prose["glyphTokens"])
    for organized in organize.classify(result):
        record = organized.record
        key = record.bank, record.address
        refs = {(r.group, r.index) for r in record.references}
        subject = subject_for(organized)
        reason = ""
        draft = current[record.id]
        profile = {"kind": "explicit", "mode": modes.get(key), "lines": None,
                   "pixels": 144, "direct": positioned.get(key, []), "right": right.get(key),
                   "static": record.id in width_ids, "exactControls": None, "fixedSpaces": None}
        if record.id in prose_rows:
            entry = dict(prose_rows[record.id])
            profile.update(kind="prose", mode=2, lines=3)
            draft = entry["draft"]
            event = entry["event"]
        else:
            event = organized.sections[0]
            entry = {"speaker": "", "terms": [], "reviewedOmissions": [], "sequence": []}
            if record.id in combat:
                row = combat[record.id]
                draft = combat_drafts[record.id].draft
                profile.update(kind="combat", lines=2 if 125 <= row.index <= 170 else None)
                event = "combat_" + row.family
            elif record.id in item_drafts:
                draft = item_drafts[record.id].draft
                profile.update(kind="item_message", lines=3)
            elif organized.category == "items":
                profile.update(kind="description", lines=11)
                profile["statHeaders"] = [[i, line] for i, line in enumerate(draft.split("<br>"))
                    if line.startswith(("Atk ", "Def ", "Slots "))]
            if organized.category == "help" or "monster_notebook_descriptions" in organized.sections:
                profile["exactControls"] = list(menu_text._critical_controls(record.raw))
                profile["exactControlTokens"] = [codec.decode_source(t.raw) for t in codec.parse_source(record.raw)
                    if t.kind == "source_control" or t.code in (0xF3, 0xFB, 0xFC)]
                profile["lines"] = record.raw.count(b"\xfd") + 1
                if organized.category == "monsters":
                    profile.update(kind="notebook", lines=1 if record.source == "みていぎ（バグ）" else 2)
                for _, group, first, last in menu_text.POSITIONED_TOPICS:
                    if any((group, i) in refs for i in range(first, last + 1)):
                        profile["pixels"] = min(profile["pixels"], menu_text.POSITIONED_PIXELS)
            for _, group, index, pixels in menu_text.POSITIONED_HEADERS:
                if (group, index) in refs: profile["pixels"] = min(profile["pixels"], pixels)
            if any(g == 7 and 1 <= i <= 24 for g, i in refs): profile["inkEdge"] = 40
            for group, index in refs:
                if group == 12:
                    profile["rootIndex"] = index
                    profile["maxChars"] = unidentified_names.FILL_IN_MAXIMUM
                    profile["sentinel"] = english.CODE_TO_ENGLISH[0x21]
                    if index in unidentified_names.ROOT_DISABLED:
                        reason = "Disabled canonical-name slot. Its sentinel is used by the input code."
                    elif blank_scroll.ROOT_FIRST <= index <= blank_scroll.ROOT_LAST:
                        reason = "The Blank Scroll matcher embeds this exact root in machine code. Change blank_scroll.py and the script together."
            if organized.category in ("internal", "review"):
                reason = ("Engine/debug data or fixed password fragments. This has no approved TSV-only display contract."
                          if organized.category == "internal" else "; ".join(organized.review_reasons))
            if not record.raw or draft == "<empty>": reason = "Native or intentionally empty slot. Keep its empty value."
            if not draft and not reason: reason = "No approved English or measured editable surface yet. Source retained for coverage."
            if organized.category == "ui_system" and not (profile["direct"] or profile["right"] or profile["pixels"] < 144):
                reason = "This positioned or composite UI entry has no standalone editable contract in the build. Its source and current translation are retained here."
            if profile["static"] or profile["direct"] or profile["right"]:
                profile["lines"] = 1
            if subject in ("names", "items", "places"):
                profile["lines"] = 1
                profile["fixedBreaks"] = draft.count("<br>")
            if profile["kind"] not in ("prose", "combat", "item_message") and profile["mode"] != 2:
                profile["fixedBoundaries"] = re.findall(r"<(?:page|box)>", draft)
            if record.id in analysis.families["item_name_format_fragments"].record_ids and draft != "<empty>":
                plain = english.decode_source(english.encode_source(draft))
                profile["fixedSpaces"] = [re.match(r"^ *", plain)[0], re.search(r" *$", plain)[0]]
            tokens = tuple(codec.parse_source(record.raw))
            runtime = {}
            for t in tokens:
                if t.kind == "source_control":
                    b = layout.dynamic_expansion(font_rom, t, 0, contract, record_id=record.id)
                    runtime[codec.source_control_text(t)] = {"composer": b.composer_pixels, "renderer": b.renderer_pixels, "kind": b.kind}
            boundaries = [[codec.CONTROLS[c], br, box] for c, br, box in wrap_en._boundary_shapes(record.raw)]
            entry.update(controls={"boundaries": boundaries,
                "effects": dict(Counter(codec.decode_source(t.raw) for t in tokens if t.code in (0xF9, 0xFA))),
                "runtime": dict(lint_en.significant_tokens(record.raw)),
                "selectors": list(lint_en._native_template_selectors(record.raw)),
                "softWrap": any(t.code == 0xF3 for t in tokens)}, runtime=runtime,
                policy=prose_web.policy_contract(record, draft))
            entry["sequence"] = [codec.decode_source(t.raw) for t in tokens if t.kind not in ("glyph", "kanji")]
            if draft and draft != "<empty>":
                for t in codec.parse_source(english.encode_source(draft)):
                    spelling = english.decode_source(t.raw)
                    if t.kind in ("glyph", "kanji") and len(spelling) > 1:
                        glyphs[spelling] = {"bytes": len(t.raw), "composer": layout.composer_advance(font_rom, t.raw),
                            "slices": list(layout.renderer_slice_advances(font_rom, t.raw)),
                            "pixels": [list(line) for line in game_font.read_glyph(font_rom, t.raw).pixels]}
        if record.id in prose_rows and not entry["editable"]: reason = "Native empty story slot."
        dummy = translations.load_mapping({record.id: "placeholder"}, (record,))[key]
        uses = [i.related_id for i in lint_en.check_terms(record, dummy, dummy_terms)]
        entry.update(loc=record.id, subject=subject, event=event, draft=draft, current=current[record.id],
                     japanese=record.source, editable=not bool(reason), reason=reason, profile=profile,
                     refs=[list(r) for r in sorted(refs)], category=organized.category,
                     termIds=uses, sections=list(organized.sections))
        if entry["editable"]:
            entry["expected"] = python_check(record, entry, draft, font_rom, contract)
            if not entry["expected"]["valid"]:
                raise ValueError("%s baseline: %s" % (record.id, entry["expected"]["error"]))
        entry["base"] = prose_web.digest(prose_web.serialized(entry))
        entries.append(entry)
        # Keep supported authoring aliases as well as their canonical spelling.
        # For example <24> is the English space and {F182=%} encodes English %.
        for spelling in re.findall(r"<[^>]+>|\{[^{}]+\}", draft):
            if spelling == "<empty>": continue
            raw = english.encode_source(spelling)
            parsed = tuple(codec.parse_source(raw))
            if len(parsed) == 1 and parsed[0].kind in ("glyph", "kanji"):
                glyphs[spelling] = {"bytes": len(raw), "composer": layout.composer_advance(font_rom, raw),
                    "slices": list(layout.renderer_slice_advances(font_rom, raw)),
                    "char": english.CODE_TO_ENGLISH.get(raw[0]) if len(raw) == 1 else None,
                    "pixels": [list(line) for line in game_font.read_glyph(font_rom, raw).pixels]}
    for event in prose["events"]: events.append(dict(event, subject="prose"))
    seen = {e["id"] for e in events}
    for row in entries:
        if row["event"] not in seen:
            seen.add(row["event"])
            events.append({"id": row["event"], "name": row["event"].replace("_", " ").capitalize(),
                           "phase": row["subject"], "subject": row["subject"],
                           "locs": [r["loc"] for r in entries if r["event"] == row["event"]]})
    # Every term width is an expression over editable IDs, including category prefixes.
    families = {name: list(f.record_ids) for name, f in analysis.families.items()}
    domains = {}
    for name, required in runtime_widths.DOMAIN_FAMILIES.items():
        values = [[key] for f in required for key in families[f]]
        if name in ("actor_name", "sender_string"): values.append([49])
        if name == "item_name":
            values = [[key] for f in ("identified_item_names", "unidentified_item_appearances") for key in families[f]]
            values += [[key, 49] for key in families["item_name_format_fragments"]]
            values += [[by_ref[(11, prefix)].id, by_ref[(12, i)].id]
                for first, last, prefix in runtime_widths.CANONICAL_NAME_PARTITIONS
                for i in range(first, last + 1) if i not in unidentified_names.ROOT_DISABLED]
        domains[name] = values if name not in runtime_widths.PERMANENTLY_UNRESOLVED else []
    notebook = [[by_ref[(tier, monster)].id, by_ref[(tier + 28, monster - 1)].id]
                for tier, monster in menu_text._monster_notebook_master_entries(rom)]
    data = {key: prose[key] for key in ("font", "nativeSelectors", "allocation", "rules")}
    data.update(format=FORMAT, records=entries, events=events, glyphTokens=glyphs,
                definitions=[asdict(d) for d in definitions], exceptions=[asdict(e) for e in exceptions],
                domains=domains, notebook=notebook, extractedCount=len(result["records"]),
                logicalReferences=len(result["references"]), inputRevision=input_revision(),
                subjects=[{"id": s, "name": n, "description": d,
                    "count": sum(r["subject"] == s for r in entries),
                    "editable": sum(r["subject"] == s and r["editable"] for r in entries)} for s, n, d in SUBJECTS])
    data["rulesRevision"] = prose_web.digest(prose_web.serialized({"inputs": data["inputRevision"],
        "profiles": [[r["loc"], r["profile"]] for r in entries], "domains": domains}))
    data["revision"] = prose_web.digest(prose_web.serialized(data))
    # Keep the public API JSON-shaped as well as its on-disk representation.
    return json.loads(prose_web.serialized(data))


def python_check(record, row, text, font_rom, contract):
    """Independent Python encoding/layout oracle using the existing owners."""
    try:
        p = row["profile"]
        if not row["editable"]:
            if text != row["draft"]: raise ValueError(row["reason"])
            return {"valid": True, "wrapped": row["current"], "lines": [], "encodedBytes": 0}
        if not text or len(text) > prose_web.MAX_TEXT or any(c in text for c in "\t\r\n"):
            raise ValueError("Blank, oversized or non-space whitespace in draft")
        encoded = english.encode_source(text)
        wrap_en.validate_control_contract(record, text, encoded)
        t = translations.load_mapping({record.id: text}, (record,))[(record.bank, record.address)]
        for check in (lint_en.check_native_template_selectors, lint_en.check_native_soft_wrap,
                      lint_en.check_sentence_spacing, lint_en.check_japanese_quotes):
            issues = check(record, t)
            if issues: raise ValueError(issues[0].detail)
        for code, count in row["policy"]["storyCodes"].items():
            if len(re.findall(r"\b%s\b" % code, text)) != count: raise ValueError("Keep the exact story code " + code)
        if p["kind"] == "prose":
            policy = prose_web.policy_contract(record, row["draft"])
            bs = re.findall(r"<(?:page|box)>", text)
            if sum(x == "<box>" and (i == 0 or bs[i - 1] != "<page>") for i, x in enumerate(bs)) > policy["unwaitedBoxes"]:
                raise ValueError("New dialogue boxes need <page><box>")
            text = wrap_en.wrap_record(font_rom, record, text, runtime_contract=contract)
        elif p["kind"] == "item_message":
            text = wrap_item_messages.wrap_message(font_rom, record, text, contract)
        encoded = english.encode_source(text)
        tokens = tuple(codec.parse_source(encoded))
        if p["static"] or p["direct"] or p["right"]:
            if any(t.kind not in ("glyph", "kanji") for t in tokens): raise ValueError("Static text must have no controls")
        if p.get("maxChars"):
            raw = english.encode(text)
            if len(raw) > p["maxChars"] or raw[:1] == b"\x21": raise ValueError("Invalid canonical recall root")
        if p["fixedSpaces"] is not None:
            plain = english.decode_source(encoded)
            if [re.match(r"^ *", plain)[0], re.search(r" *$", plain)[0]] != p["fixedSpaces"]:
                raise ValueError("Keep the shared name fragment's leading/trailing separator spaces")
        for i, header in p.get("statHeaders", []):
            parts = text.split("<br>")
            if len(parts) <= i or parts[i] != header: raise ValueError("Keep the item stat header unchanged")
        if p["exactControls"] is not None and list(menu_text._critical_controls(encoded)) != p["exactControls"]:
            raise ValueError("Keep critical help/Notebook controls")
        if "fixedBoundaries" in p and re.findall(r"<(?:page|box)>", text) != p["fixedBoundaries"]:
            raise ValueError("This fixed surface must retain its page/box structure")
        if "fixedBreaks" in p and text.count("<br>") != p["fixedBreaks"]:
            raise ValueError("Names must retain their single-line structure")
        if p["exactControls"] is not None and p["kind"] != "notebook" and encoded.count(b"\xfd") + 1 > p["lines"]:
            raise ValueError("Help exceeds its total source line budget")
        if p["kind"] == "notebook" and encoded.count(b"\xfd") + 1 != p["lines"]:
            raise ValueError("Keep the exact Notebook line count")
        measured = layout.source_layout(font_rom, encoded, mode=p["mode"] or 2,
            record_id=record.id, runtime_contract=contract, simulate_soft_wrap=p["kind"] != "prose")
        if measured.unresolved_dynamic_offsets or measured.composer_overflows or measured.renderer_overflows:
            raise ValueError("Text exceeds the measured canvas or has unresolved runtime widths")
        if measured.page_marker_overflows or measured.detached_page_marker_wraps:
            raise ValueError("Page marker crosses the right edge")
        if p["mode"] is not None and (measured.bottom_line_glyph_cell_overflows or measured.line_limit_overflows):
            raise ValueError("Text crosses the surface's line or compositor-cell limit")
        if p["kind"] == "notebook" and any(c.line >= 1 for c in measured.glyph_cell_overflows):
            raise ValueError("Notebook bottom row crosses its compositor cell")
        if p["lines"] and any(line.line >= p["lines"] for line in measured.lines):
            raise ValueError("Text exceeds this family's line count")
        if any(max(line.composer_pixels, line.renderer_pixels) > p["pixels"] for line in measured.lines):
            raise ValueError("Text exceeds the positioned topic budget")
        for x, y, edge in p["direct"]: layout.validate_direct_surface(font_rom, encoded, x, y, edge)
        if p["right"]: layout.validate_direct_right_aligned_surface(font_rom, encoded, *p["right"])
        if p.get("inkEdge"):
            approved = english_font.load_approved()
            pen = edge = 0
            for char in english.decode_source(encoded):
                pixels = approved.rows[char]
                edge = max(edge, max((pen + i + 1 for line in pixels for i, c in enumerate(line) if c == "#"), default=pen))
                pen += approved.advances[char]
            if edge > p["inkEdge"]: raise ValueError("Item-action ink enters a cursor-only tile")
        if len(encoded) + 1 > allocate.BANK_SIZE: raise ValueError("Record exceeds a ROM bank")
        return {"valid": True, "wrapped": text, "encodedBytes": len(encoded), "lines": [
            [l.surface, l.line, l.composer_pixels, l.renderer_pixels] for l in measured.lines]}
    except (ValueError, KeyError) as exc:
        return {"valid": False, "error": str(exc)}


def check_assets():
    data = json.loads(CATALOG.read_text())
    if data["inputRevision"] != input_revision(): raise ValueError("Workbench catalogue inputs changed; regenerate with the local ROM")
    ids = [r["loc"] for r in data["records"]]
    if len(ids) != data["extractedCount"] or len(set(ids)) != len(ids): raise ValueError("Incomplete or duplicate text coverage")
    source_ids = []
    for path in (ROOT / "script/en").glob("*.tsv"):
        with path.open() as handle: source_ids.extend(r["id"] for r in csv.DictReader(handle, delimiter="\t"))
    if set(source_ids) != set(ids) or len(source_ids) != len(ids): raise ValueError("Coverage differs from the project catalogues")
    if sum(s["count"] for s in data["subjects"]) != len(ids): raise ValueError("Subject counts do not cover the extraction")
    for subject in data["subjects"]:
        members = [r for r in data["records"] if r["subject"] == subject["id"]]
        if len(members) != subject["count"] or sum(r["editable"] for r in members) != subject["editable"]:
            raise ValueError("Stale subject census")
    pages(data, check=True)
    return data


def pages(data, check=False):
    home = ROOT / "docs/translation-tool/index.html"
    content = home.read_text()
    start, end = "<!-- workbenches:start -->", "<!-- workbenches:end -->"
    cards = [start, '<div class="subject-grid">']
    for s in data["subjects"]:
        href = "workbench/?subject=" + s["id"]
        cards.append('<article class="subject-card"><small>%s entries · %s editable</small><h3><a href="%s">%s</a></h3><p>%s</p><a href="%s">Open workbench →</a></article>' %
                     (format(s["count"], ","), format(s["editable"], ","), href, escape(s["name"]), escape(s["description"]), href))
    cards += ["</div>", end]
    if start in content: updated = content[:content.index(start)] + "\n".join(cards) + content[content.index(end) + len(end):]
    else:
        a = content.index('      <article class="studio-card">'); b = content.index('    </section>', a)
        updated = content[:a] + "\n".join(cards) + '\n      <p class="future-note">All 6,695 extracted entries are accounted for. Fixed and unconfirmed surfaces include a reason. <a href="coverage.html">View script coverage →</a></p>\n' + content[b:]
    updated = updated.replace('<span class="poc-badge">Proof of concept</span>', '<a href="coverage.html">Script coverage →</a>')
    updated = updated.replace('Select a scene', 'Select a workbench').replace('Open the prose editor and select a scene.', 'Choose a subject and a group.')
    table = []
    for s in data["subjects"]:
        table.append('<tr><th scope="row"><a href="workbench/?subject=%s">%s</a></th><td>%s</td><td>%s</td><td>%s</td></tr>' %
                     (s["id"], escape(s["name"]), format(s["count"], ","), format(s["editable"], ","), format(s["count"] - s["editable"], ",")))
    repo = "https://github.com/joey-astrologo/Shiren-GB2-Magic-Castle-of-the-Desert/blob/main/"
    owners = (("Menus, input keyboards and HUD labels", "tools/menu_graphics.py"),
              ("Status and item stat graphics", "tools/item_status.py"),
              ("Dungeon arrival cards", "tools/arrival_cards.py"), ("Wait screen", "tools/wait_screen.py"),
              ("Opening credit screen", "tools/credit_screen.py"), ("Ending credits", "tools/ending_credits.py"),
              ("Rescue presentation", "tools/rescue_presentation.py"),
              ("Blank Scroll name matcher", "tools/blank_scroll.py"),
              ("Big Moai gift-code input", "tools/spell_input.py"),
              ("Numbers, item suffixes and formatting", "tools/item_formatting.py"))
    coverage = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Script coverage · Shiren GB2</title><link rel="stylesheet" href="style.css"></head>
<body><header class="masthead"><div class="header-inner"><a class="brand" href="./">SHIREN GB2 <small>Translation tools</small></a><a href="./">All workbenches</a></div></header>
<main class="coverage"><h1>Script coverage</h1><p>All 6,695 extracted records have exactly one primary subject. Their 7,163 logical references include aliases, which are counted once. Japanese source and current English are bundled.</p>
<div class="coverage-table"><table><thead><tr><th>Subject</th><th>Entries</th><th>Editable</th><th>Reference</th></tr></thead><tbody>''' + "".join(table) + '''</tbody></table></div>
<h2>Reference entries</h2><p>Internal labels, password data, empty slots, embedded matcher names and unconfirmed or composite UI surfaces remain visible in their subjects. Each entry states why a TSV-only edit is unavailable. A reference count does not mean those strings are missing from the catalogue.</p>
<p>The workbenches share one draft, including all 72 prose scenes. The earlier prose editor remains available with its separate saved drafts and import format.</p>
<h2>Text outside the extracted script</h2><p>Some visible text is rendered from graphics, generated values or code-owned tables. The 6,695-record count covers the extracted script; it does not count these assets as editable TSV strings. Their project owners are:</p><ul>''' + "".join('<li><a href="%s%s">%s</a></li>' % (repo, path, title) for title, path in owners) + '''</ul>
<h2>Validation</h2><p>The browser checks encoding, controls, measured surface limits, shared terminology, runtime widths, Notebook composition, combat-name combinations and ROM text allocation. Download is blocked if any edited entry or affected dependency fails. The importer independently runs the Python owners, complete lint and an in-memory ROM build before applying changes.</p><p>Coverage, Japanese source, rules and font snapshots are regenerated from the project. Changed inputs prevent packaging until the catalogue is refreshed. Translation meaning, event behavior and visual acceptance still require review in game.</p></main></body></html>
'''
    for path, value in ((home, updated), (ROOT / "docs/translation-tool/coverage.html", coverage)):
        if check:
            if not path.exists() or path.read_text() != value: raise ValueError("Stale generated workbench navigation/coverage page")
        else: path.write_text(value)


def parse_edits(text, data):
    # The metadata grammar and baseline safeguards are shared with prose. Only
    # the format tag differs; reject it before handing the remaining grammar over.
    tag = "# format\t" + FORMAT
    if text.lstrip("\ufeff").splitlines().count(tag) != 1:
        raise ValueError("Use a GB2 workbench changes TSV")
    return prose_web.parse_edits(text.replace(tag, "# format\t" + prose_web.FORMAT, 1), data)


def check_ownership(result, scenes, editor, current):
    """Prove current generated cells still belong to their original owners."""
    eligible = wrap_en.prose_rows(result)
    drafts = wrap_en.read_draft(wrap_en.DEFAULT_DRAFT, eligible)
    state = prose_editor.read_state(prose_editor.DEFAULT_STATE, result, scenes)
    prose_editor._check_ownership(state, prose_editor.editor_sha1(editor), prose_editor._draft_sha1(eligible, drafts))
    for owner in (wrap_en, wrap_item_messages, combat_messages):
        rows = owner.prose_rows(result) if owner is wrap_en else owner.message_rows(result)
        state = owner.load_state(owner.DEFAULT_STATE, result, rows)
        for record_id, hashes in state["generated"].items():
            expected = hashes.get("wrapped_sha1", hashes.get("generated_sha1"))
            if owner._text_sha1(current.get(record_id, "")) != expected:
                raise ValueError("%s generated text was edited outside its owner" % record_id)


def check_project(rom, result, merged, exceptions):
    """Run the actual complete build, menu/input and combat-domain validators."""
    import build as rom_build
    translated = translations.load_mapping(merged, result["records"])
    lint_en.require_clean(result, translated, exceptions)
    font_rom = english_font.install(rom)
    analysis = runtime_widths.analyze(font_rom, result, translated)
    domains, counts = combat_messages.runtime_candidate_domains(font_rom, result, translated)
    for row in combat_messages.message_rows(result):
        draft = merged[row.record.id]
        if draft and draft != "<empty>":
            combat_messages.validate_draft(font_rom, row, draft, analysis.contract)
            report = combat_messages.combination_report(font_rom, row, draft, analysis, domains, counts)
            if report["unsafe"]: raise ValueError("%s has unsafe runtime-name combinations" % row.record.id)
    menu_text.analyze(rom, result, translated)
    rom_build._validate_blank_scroll_catalog(result, translated)
    rom_build._validate_unidentified_name_catalog(result, translated)
    _, allocation, validation = rom_build.build_rom(rom, translations.encoded_overrides(translated), runtime_contract=analysis.contract)
    return allocation, validation


def staged_files(rom, result, scenes, editor, merged, changes, directory):
    """Construct the complete proposed workspace, then run all three owners."""
    stage = Path(directory)
    catalog, overlay = stage / "script/organized", stage / "script/en"
    organize.write_outputs(result, catalog, english_by_id=merged)
    overlays.write_outputs(result, overlay, organize.classify(result), merged)
    (overlay / lint_en.EXCEPTION_FILENAME).write_bytes((ROOT / "script/en" / lint_en.EXCEPTION_FILENAME).read_bytes())
    proposed_editor = [dict(r, english=changes.get(r["id"], r["english"])) for r in editor]
    prose_editor.write_editor(stage / "script/editing/prose.tsv", proposed_editor)
    for owner in (wrap_en, wrap_item_messages, combat_messages):
        eligible = owner.prose_rows(result) if owner is wrap_en else owner.message_rows(result)
        drafts = owner.read_draft(owner.DEFAULT_DRAFT, eligible)
        if owner is wrap_en:
            drafts = prose_editor.draft_rows_from_editor(result, eligible, proposed_editor)
        else:
            drafts = {key: replace(row, draft=changes.get(key, row.draft)) for key, row in drafts.items()}
        destination = stage / owner.DEFAULT_DRAFT.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if owner is wrap_item_messages:
            # This owner only has a reader; preserve its exact authoring schema.
            with destination.open("w", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
                writer.writerow(("id", "sections", "draft"))
                for row in eligible: writer.writerow((row.record.id, ";".join(row.sections), drafts[row.record.id].draft))
        else: owner.write_draft(destination, eligible, drafts)
        state = owner._base_state(result, eligible)
        state["generated"] = {key: {"draft_sha1": owner._text_sha1(row.draft),
            "generated_sha1" if owner is combat_messages else "wrapped_sha1": owner._text_sha1(merged[key])}
            for key, row in drafts.items() if row.draft}
        state_path = stage / owner.DEFAULT_STATE.relative_to(ROOT)
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        if owner is wrap_en:
            prose_editor.write_state(stage / "script/editing/prose.generated.json", prose_editor._base_state(
                result, scenes, prose_editor.editor_sha1(proposed_editor), prose_editor._draft_sha1(eligible, drafts)))
        # Re-enter the real owner with the prospective files. No local project file
        # is changed during validation, and generated text cannot bypass wrapping.
        workspace = owner.prepare_workspace(rom, result, draft_path=destination, state_path=state_path,
            catalog_dir=catalog, overlay_dir=overlay)
        generated = workspace.english_by_id if owner is wrap_en else workspace[2] if owner is wrap_item_messages else workspace["merged"]
        if generated != merged: raise ValueError("%s disagrees with the proposed generated text" % owner.__name__)
    return {ROOT / p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}


def apply_transaction(proposed, originals):
    for path in proposed:
        if (path.read_bytes() if path.exists() else None) != originals.get(path):
            raise ValueError("%s changed during import; rerun the check" % path)
    written = []
    try:
        for path, contents in proposed.items():
            if contents == originals.get(path): continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".workbench-", delete=False) as handle:
                temporary = Path(handle.name); handle.write(contents)
            try: os.replace(temporary, path)
            finally: temporary.unlink(missing_ok=True)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            if originals.get(path) is None: path.unlink(missing_ok=True)
            else: path.write_bytes(originals[path])
        raise


def import_file(rom_path, tsv_path, apply=False):
    data = check_assets()
    changes = parse_edits(Path(tsv_path).read_text(), data)
    originals = {p: p.read_bytes() for folder in ("script/en", "script/organized", "script/drafts", "script/editing")
                 for p in (ROOT / folder).glob("*") if p.is_file()}
    rom = Path(rom_path).read_bytes()
    result, scenes, editor, current, font_rom, _, exceptions, _ = prose_web.load_workspace(rom)
    check_ownership(result, scenes, editor, current)
    by_id = {r.id: r for r in result["records"]}
    # Static definitions change first, so every unchanged consumer is remeasured.
    merged = dict(current); merged.update(changes)
    contract = runtime_widths.analyze(font_rom, result, translations.load_mapping(merged, result["records"])).contract
    for row in data["records"]:
        if not row["editable"]: continue
        checked = python_check(by_id[row["loc"]], row, changes.get(row["loc"], row["draft"]), font_rom, contract)
        if not checked["valid"]: raise ValueError("%s: %s" % (row["loc"], checked["error"]))
        merged[row["loc"]] = checked["wrapped"]
    allocation, validation = check_project(rom, result, merged, exceptions)
    with tempfile.TemporaryDirectory(prefix="gb2-workbench-") as directory:
        proposed = staged_files(rom, result, scenes, editor, merged, changes, directory)
        changed_files = {p: value for p, value in proposed.items() if value != originals.get(p)}
        for path, contents in changed_files.items():
            if path.suffix != ".tsv" or "organized" in path.parts: continue
            relative = str(path.relative_to(ROOT))
            print("".join(difflib.unified_diff((originals.get(path) or b"").decode().splitlines(True),
                contents.decode().splitlines(True), fromfile=relative, tofile="proposed/" + relative)), end="")
        print("Validated %d edits, complete terminology/runtime domains, all draft owners and %d relocated references." % (len(changes), validation["exact_references"]))
        if input_revision() != data["inputRevision"]: raise ValueError("Project inputs changed during import; rerun the check")
        # Also protect ignored rich catalogues and detect changes to files which
        # did not need rewriting in the proposed result.
        for path, before in originals.items():
            if not path.exists() or path.read_bytes() != before: raise ValueError("%s changed during import" % path)
        if apply:
            apply_transaction(changed_files, originals)
            print("Applied %d files. Regenerate both web catalogues, then run the project's game acceptance checks." % len(changed_files))
        else: print("Checked; no project files changed. Add --apply to write the reviewed edits.")
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export"); export.add_argument("rom"); export.add_argument("--check", action="store_true")
    sub.add_parser("check-assets")
    importer = sub.add_parser("import"); importer.add_argument("rom"); importer.add_argument("tsv"); importer.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "import":
            import_file(args.rom, args.tsv, args.apply); return
        if args.action == "check-assets": data = check_assets()
        else:
            data = make_catalog(Path(args.rom).read_bytes())
            output = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
            if args.check:
                if CATALOG.read_text() != output: raise ValueError("Stale catalogue")
            else:
                SITE.mkdir(parents=True, exist_ok=True); CATALOG.write_text(output)
                pages(data)
        print("%d entries; %d editable; %d subjects" % (len(data["records"]), sum(r["editable"] for r in data["records"]), len(data["subjects"])))
    except (OSError, ValueError) as exc: parser.exit(1, "error: %s\n" % exc)


if __name__ == "__main__": main()
