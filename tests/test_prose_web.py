"""Project-derived browser oracles, importer guards and public artifact checks."""
from dataclasses import replace
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_pages
import allocate
import codec
import prose_web

FIXTURE = ROOT / "tests/fixtures/prose_web_cases.json"
ALLOCATION_FIXTURE = ROOT / "tests/fixtures/prose_web_allocation.json"
ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


def changes_tsv(data, changes):
    records = {row["loc"]: row for row in data["records"]}
    lines = ["# format\t" + prose_web.FORMAT, "# revision\t" + data["revision"],
             "# rules\t" + data["rulesRevision"]]
    lines += ["# base\t%s\t%s" % (record_id, records[record_id]["base"]) for record_id in changes]
    lines += ["# id\tenglish"]
    lines += ["%s\t%s" % pair for pair in changes.items()]
    return "\n".join(lines) + "\n"


def oracle_cases():
    data = json.loads(prose_web.CATALOG.read_text(encoding="utf-8"))
    result, _, _, _, font_rom, contract, exceptions, terms = prose_web.load_workspace(ROM.read_bytes())
    native = {record.id: record for record in result["records"]}
    cases = []
    for row in data["records"]:
        if not row["editable"]:
            continue
        variants = {"append sentence": row["draft"] + " Next."}
        for token in re.findall(r"<[^>]+>", row["draft"]):
            variants.setdefault("remove " + token, row["draft"].replace(token, "", 1))
        for term in row["terms"]:
            if term in row["draft"]:
                variants["remove term " + term] = row["draft"].replace(term, "thing", 1)
        for term in row["reviewedOmissions"]:
            variants["stale exception"] = row["draft"] + "<page><box>" + term + "."
        for code in row["policy"]["storyCodes"]:
            variants["change story code"] = row["draft"].replace(code, "ABCD")
        if row["controls"]["selectors"]:
            variants["change native selector"] = row["draft"].replace("<cF8>", "<cF8>z", 1)
        for label, text in variants.items():
            expected = prose_web.python_check(native[row["loc"]], text, font_rom, contract,
                                               terms, exceptions, row["draft"])
            cases.append({"id": row["loc"], "label": label, "text": text, "expected": expected})
    # Isolate geometry and whitespace from a story record's semantic boundaries.
    record = replace(result["records"][0], raw=codec.encode_source("a"), source="a", references=(), controls=())
    synthetic = {"loc": record.id, "editable": True, "draft": "Text.", "terms": [],
        "reviewedOmissions": [], "runtime": {}, "policy": prose_web.policy_contract(record, "Text."),
        "controls": {"boundaries": [], "effects": {}, "runtime": {}, "selectors": [], "softWrap": False}}
    drafts = ["", " text", "text ", "two  spaces", "line\nbreak", "tab\there", "Curly \u201cquotes\u201d",
        "<empty>", "<speaker>Text", "<bad>", "<page", "<name>", "Yes!<page>Next", "Yes!<page> Next",
        "Text.<br>", "<br>Text.", "A<br><br>B", "A<br>B<br>C<page><br>D", "A<br>B<br>C<page><box>D",
        "A<box>B", "A<page><box>B", "Text.<page><box>", "Text.<page><box><delay:01>",
        "<hspace:03>Small space."]
    for width in range(120, 151):
        drafts += ["<hspace:%02X>." % width, "A<br>B<br><hspace:%02X>." % width,
                   "<hspace:%02X>.<page>" % width]
    for count in range(20, 32):
        drafts += ["A" * count, " ".join(["Word"] * count)]
    for text in drafts:
        cases.append({"row": synthetic, "label": "boundary", "text": text,
            "expected": prose_web.python_check(record, text, font_rom, contract, (), (), "Text.")})
    return cases


def allocation_cases():
    result, _, rows, current, _, _, _, _ = prose_web.load_workspace(ROM.read_bytes())
    units = allocate.build_units(result, prose_web.translations.encoded_overrides(
        prose_web.translations.load_mapping(current, result["records"])))
    ids = [row["id"] for row in rows[:40]]
    variants = [{}, {ids[0]: 0}, {ids[0]: 16383}, {ids[0]: 16384},
                {ids[0]: 16382, ids[1]: 1}]
    variants += [{record_id: 10000 for record_id in ids[:count]} for count in (5, 10, 15, 20, 30, 40)]
    cases = []
    for sizes in variants:
        changed = [replace(unit, record_data=tuple(
            bytes(sizes[record.id]) if record.id in sizes else raw
            for record, raw in zip(unit.records, unit.record_data))) for unit in units]
        try:
            _, placements = allocate._pack(changed, allocate.FREE_BANKS)
            last = changed[-1].records[-1]
            bank, address = placements[(last.bank, last.address)]
            expected = {"valid": True, "banksUsed": bank - allocate.FREE_BANKS[0] + 1,
                        "endOffset": address - 0x4000 + len(changed[-1].record_data[-1]) + 1}
        except allocate.AllocationError:
            expected = {"valid": False}
        cases.append({"sizes": sizes, "expected": expected})
    return cases


class ProseWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(prose_web.CATALOG.read_text(encoding="utf-8"))

    def test_catalogue_matches_project_inputs(self):
        self.assertEqual(prose_web.input_revision(), self.data["inputRevision"])
        self.assertEqual(1768, len(self.data["records"]))
        self.assertEqual(72, len(self.data["events"]))
        self.assertEqual(1, sum(not row["editable"] for row in self.data["records"]))
        self.assertTrue(all("japanese" in row for row in self.data["records"]))
        self.assertTrue(all(row["expected"]["valid"] for row in self.data["records"]))

    def test_changes_format_and_rejections(self):
        row = next(row for row in self.data["records"] if row["editable"])
        text = changes_tsv(self.data, {row["loc"]: row["draft"]})
        self.assertEqual({row["loc"]: row["draft"]}, prose_web.parse_edits("\ufeff" + text.replace("\n", "\r\n"), self.data))
        invalid = [text.replace(row["base"], "0" * 64), text.replace(self.data["rulesRevision"], "0" * 64),
                   text + row["loc"] + "\tduplicate\n", text.replace(row["loc"], "999:$FFFF"),
                   text.replace(prose_web.FORMAT, "shiren-prose-edits-v1"), text + "bad\trow\textra\n",
                   text.replace("# id\tenglish", "# unknown\tvalue")]
        empty = next(row for row in self.data["records"] if not row["editable"])
        invalid.append(changes_tsv(self.data, {empty["loc"]: "Text."}))
        for value in invalid:
            with self.subTest(value=value[:100]), self.assertRaises(ValueError):
                prose_web.parse_edits(value, self.data)

    def test_public_artifact_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = build_pages.build(Path(directory) / "pages")
            actual = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
            expected = set(build_pages.RESCUE_FILES) | {"translation-tool/" + name for name in build_pages.TRANSLATION_FILES}
            self.assertEqual(expected, actual)
            self.assertIn('href="translation-tool/index.html"', (output / "index.html").read_text())
            self.assertIn('href="prose/"', (output / "translation-tool/index.html").read_text())
            self.assertFalse(any(name.endswith((".gbc", ".gb", ".sav")) for name in actual))

    @unittest.skipUnless(ROM.exists(), "matching local ROM required for independent Python oracles")
    def test_all_mutation_oracles_match_python(self):
        self.assertEqual(json.loads(FIXTURE.read_text(encoding="utf-8")), oracle_cases())
        self.assertEqual(json.loads(ALLOCATION_FIXTURE.read_text(encoding="utf-8")), allocation_cases())

    @unittest.skipUnless(ROM.exists(), "matching local ROM required for regeneration")
    def test_entire_catalogue_matches_rom_and_python_owners(self):
        self.assertEqual(self.data, prose_web.make_catalog(ROM.read_bytes()))

    @unittest.skipUnless(ROM.exists(), "matching local ROM required for project imports")
    def test_project_import_is_validated_and_changes_only_authoritative_rows(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        valid = next(case for case in cases if case.get("id") and case["expected"]["valid"])
        original = prose_web.prose_editor.DEFAULT_EDITOR.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            editor = Path(directory) / "prose.tsv"
            editor.write_bytes(original)
            changes = Path(directory) / "changes.tsv"
            changes.write_text(changes_tsv(self.data, {valid["id"]: valid["text"]}), encoding="utf-8")
            with patch.object(prose_web.prose_editor, "DEFAULT_EDITOR", editor), redirect_stdout(io.StringIO()):
                prose_web.import_file(ROM, changes)
                self.assertEqual(original, editor.read_bytes())
                prose_web.import_file(ROM, changes, apply=True)
                changed_lines = [(a, b) for a, b in zip(original.splitlines(), editor.read_bytes().splitlines()) if a != b]
                self.assertEqual(1, len(changed_lines))
                self.assertIn(valid["text"].encode("ascii"), changed_lines[0][1])
                editor.write_bytes(original)
                changes.write_text(changes_tsv(self.data, {valid["id"]: "Invalid <name>"}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    prose_web.import_file(ROM, changes, apply=True)
                self.assertEqual(original, editor.read_bytes())


if __name__ == "__main__":
    if "--write-fixtures" in sys.argv:
        cases = oracle_cases()
        FIXTURE.write_text(json.dumps(cases, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        ALLOCATION_FIXTURE.write_text(json.dumps(allocation_cases(), indent=2) + "\n", encoding="utf-8")
        print("Wrote %d Python mutation oracles" % len(cases))
    else:
        unittest.main()
