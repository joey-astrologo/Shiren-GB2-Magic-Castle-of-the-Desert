"""Native-oracle coverage, metadata guards and transactional importer tests."""
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
import workbench_web as web
import prose_web

ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = ROOT / "tests/fixtures/workbench_web_cases.json"


def tsv(data, changes):
    rows = {r["loc"]: r for r in data["records"]}
    return "\n".join(["# format\t" + web.FORMAT, "# revision\t" + data["revision"], "# rules\t" + data["rulesRevision"]]
        + ["# base\t%s\t%s" % (key, rows[key]["base"]) for key in changes]
        + ["# id\tenglish"] + [key + "\t" + value for key, value in changes.items()]) + "\n"


def oracle_cases():
    data = json.loads(web.CATALOG.read_text())
    result, _, _, _, font_rom, contract, _, _ = prose_web.load_workspace(ROM.read_bytes())
    native = {r.id: r for r in result["records"]}
    cases = []
    groups = set()
    for row in data["records"]:
        if not row["editable"] or row["profile"]["kind"] == "prose": continue
        variants = {"append": row["draft"] + " Next."}
        # Exercise every template, plus the first row of every remaining family.
        if row["profile"]["kind"] in ("combat", "item_message") or row["event"] not in groups:
            groups.add(row["event"])
            for token in re.findall(r"<[^>]+>|\{[^{}]+\}", row["draft"]):
                variants["remove " + token] = row["draft"].replace(token, "", 1)
            variants.update({"newline": row["draft"] + "\n", "overflow": "W" * 30,
                "unsupported glyph": row["draft"] + "é", "extra line": row["draft"] + "<br>Next.",
                "bad token": row["draft"] + "<unknown>", "space": " " + row["draft"]})
            for width in (132, 135, 136, 137, 143, 144, 145):
                variants["hspace %d" % width] = "<hspace:%02X>.<page>" % width
        for label, text in variants.items():
            cases.append({"id": row["loc"], "label": label, "text": text,
                "expected": web.python_check(native[row["loc"]], row, text, font_rom, contract)})
    return cases


class WorkbenchWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data = json.loads(web.CATALOG.read_text())

    def test_complete_coverage_and_fresh_assets(self):
        self.assertEqual(self.data, web.check_assets())
        self.assertEqual(6695, len(self.data["records"]))
        self.assertEqual(7163, self.data["logicalReferences"])
        self.assertEqual(12, len(self.data["subjects"]))
        self.assertTrue(all("japanese" in r and (r["editable"] or r["reason"]) for r in self.data["records"]))
        self.assertTrue(all(r["expected"]["valid"] for r in self.data["records"] if r["editable"]))

    def test_metadata_and_readonly_guards(self):
        row = next(r for r in self.data["records"] if r["editable"])
        text = tsv(self.data, {row["loc"]: row["draft"]})
        self.assertEqual({row["loc"]: row["draft"]}, web.parse_edits(text, self.data))
        fixed = next(r for r in self.data["records"] if not r["editable"])
        for bad in (text.replace(row["base"], "0" * 64), text.replace(self.data["rulesRevision"], "0" * 64),
                    text.replace(web.FORMAT, prose_web.FORMAT), text + row["loc"] + "\tduplicate\n",
                    tsv(self.data, {fixed["loc"]: "Changed"})):
            with self.assertRaises(ValueError): web.parse_edits(bad, self.data)

    def test_atomic_writes_and_concurrent_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.write_bytes(b"old a"); b.write_bytes(b"old b")
            before = {a: a.read_bytes(), b: b.read_bytes()}; after = {a: b"new a", b: b"new b"}
            real_replace = web.os.replace
            def fail_second(src, dest):
                if dest == b: raise OSError("injected write failure")
                return real_replace(src, dest)
            with patch.object(web.os, "replace", side_effect=fail_second), self.assertRaises(OSError):
                web.apply_transaction(after, before)
            self.assertEqual(before, {a: a.read_bytes(), b: b.read_bytes()})
            b.write_bytes(b"other editor")
            with self.assertRaises(ValueError): web.apply_transaction(after, before)
            self.assertEqual(b"old a", a.read_bytes())
            b.write_bytes(before[b]); web.apply_transaction(after, before)
            self.assertEqual(after, {a: a.read_bytes(), b: b.read_bytes()})

    @unittest.skipUnless(ROM.exists(), "matching local ROM required")
    def test_python_mutation_oracle(self):
        self.assertEqual(json.loads(FIXTURE.read_text()), oracle_cases())

    @unittest.skipUnless(ROM.exists(), "matching local ROM required")
    def test_complete_regeneration(self):
        self.assertEqual(self.data, web.make_catalog(ROM.read_bytes()))

    @unittest.skipUnless(ROM.exists(), "matching local ROM and build dependencies required")
    def test_import_routes_all_draft_owners_and_applies_only_to_isolated_files(self):
        ids = ("195:$5593", "194:$55B1", "193:$4192", "202:$41B0")
        changes = {r["loc"]: r["draft"].replace(".", "!", 1) for r in self.data["records"] if r["loc"] in ids}
        before = {p: p.read_bytes() for folder in ("script/en", "script/organized", "script/drafts", "script/editing")
                  for p in (ROOT / folder).glob("*") if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            incoming = Path(tmp) / "edits.tsv"; incoming.write_text(tsv(self.data, changes))
            captured = {}
            commit = web.apply_transaction
            def isolated_apply(proposed, originals):
                captured.update(proposed)
                mapping = {p: Path(tmp) / "isolated" / p.relative_to(ROOT) for p in proposed}
                for p, dest in mapping.items():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if originals.get(p) is not None: dest.write_bytes(originals[p])
                commit({mapping[p]: value for p, value in proposed.items()},
                    {mapping[p]: originals.get(p) for p in proposed})
                for p, value in proposed.items(): self.assertEqual(value, mapping[p].read_bytes())
            with redirect_stdout(io.StringIO()), patch.object(web, "apply_transaction", side_effect=isolated_apply):
                self.assertEqual(changes, web.import_file(ROM, incoming, apply=True))
            paths = {str(p.relative_to(ROOT)) for p in captured}
            for required in ("script/editing/prose.tsv", "script/drafts/prose.tsv", "script/drafts/prose.generated.json",
                "script/drafts/item_messages.tsv", "script/drafts/item_messages.generated.json", "script/drafts/combat_messages.tsv",
                "script/drafts/combat_messages.generated.json", "script/en/prose.tsv", "script/en/items.tsv", "script/en/messages.tsv"):
                self.assertIn(required, paths)
            incoming.write_text(tsv(self.data, {"194:$55B1": "Curly “quotes”"}))
            with self.assertRaises(ValueError): web.import_file(ROM, incoming, apply=True)
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == "__main__":
    if "--write-fixtures" in sys.argv:
        FIXTURE.write_text(json.dumps(oracle_cases(), ensure_ascii=False, separators=(",", ":")) + "\n")
        print("Wrote Python workbench mutation oracles")
    else: unittest.main()
