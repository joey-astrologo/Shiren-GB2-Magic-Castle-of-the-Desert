"""Full-sheet integrity, owner routing, test-ROM output and no-write guarantees."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import english
import import_script_sheet as sheet
import insert
import ips
import workbench_web as web

ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


def tsv(rows, fields=sheet.FIELDS, newline="\n"):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator=newline)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


class SheetParserTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(id="192:$4100", loc="216:$5000", bytes="12", jp="Source text",
                          en='An "item" {F182=%}.', edited_en=""),
                     dict(id="192:$4200", loc="216:$5020", bytes="0", jp="", en="<empty>", edited_en="")]
        self.baseline = {r["id"]: dict(r) for r in self.rows}
        self.profiles = {r["id"]: dict(editable=i == 0, reason="Fixed empty slot") for i, r in enumerate(self.rows)}

    def parse(self, rows):
        return sheet.parse_sheet(tsv(rows), self.baseline, self.profiles)

    def test_spreadsheet_quoting_bom_crlf_and_sorting_preserve_exact_edits(self):
        text = 'A "different" item {F182=%}!'
        self.rows[0]["edited_en"] = text
        encoded = "\ufeff" + tsv(list(reversed(self.rows)), tuple(reversed(sheet.FIELDS)), "\r\n")
        self.assertEqual({self.rows[0]["id"]: text}, sheet.parse_sheet(encoded, self.baseline, self.profiles))

    def test_blank_and_copied_baseline_cells_do_not_become_edits(self):
        self.assertEqual({}, self.parse(self.rows))
        for row in self.rows:
            row["edited_en"] = row["en"]
        self.assertEqual({}, self.parse(self.rows))

    def test_metadata_and_all_record_ids_are_required(self):
        cases = [self.rows[:-1], self.rows + [self.rows[0]], []]
        for field in sheet.FIELDS[:-1]:
            rows = deepcopy(self.rows)
            rows[0][field] += " changed"
            cases.append(rows)
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.parse(rows)

    def test_reference_edits_and_multiline_or_oversized_edits_are_rejected(self):
        self.rows[1]["edited_en"] = "New text"
        with self.assertRaisesRegex(ValueError, "reference-only"):
            self.parse(self.rows)
        self.rows[1]["edited_en"] = ""
        for value in ("Line\nbreak", "Line\rbreak", "Tab\ttext", "A" * (sheet.prose_web.MAX_TEXT + 1)):
            self.rows[0]["edited_en"] = value
            with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                self.parse(self.rows)

    def test_malformed_columns_are_rejected(self):
        valid = tsv(self.rows)
        cases = ["", valid.replace("edited_en", "english", 1), valid.replace("edited_en", "en", 1),
                 valid.replace("\tbytes\t", "\tbytes\textra\t", 1), valid + "192:$4100\ttoo few\n",
                 valid + '"unfinished quoted field\n']
        for text in cases:
            with self.subTest(text=text[:100]), self.assertRaises((ValueError, csv.Error)):
                sheet.parse_sheet(text, self.baseline, self.profiles)

    def test_existing_rom_or_patch_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "review.gbc"
            patch_path = destination.with_suffix(".ips")
            patch_path.write_bytes(b"existing patch")
            with self.assertRaises(FileExistsError):
                sheet.output_paths(destination, "shadowed")
            self.assertEqual(b"existing patch", patch_path.read_bytes())
            self.assertFalse(destination.exists())
            with self.assertRaises(ValueError):
                sheet.output_paths(Path(tmp) / "review.tsv", "classic")

    def test_combined_write_failure_restores_project_and_removes_new_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, output = root / "owner.tsv", root / "review.gbc"
            project.write_bytes(b"original owner\n")
            prepared = sheet.PreparedSheet(root / "original.gbc", b"", root / "sheet.tsv", b"", "revision",
                {project: b"original owner\n"}, {"192:$4100": "Edited"}, {project: b"edited owner\n"},
                (), {}, {"exact_references": 1})
            real_replace = web.os.replace
            def fail_patch(src, dest):
                if dest == output.with_suffix(".ips"):
                    raise OSError("injected output write failure")
                return real_replace(src, dest)
            with patch.object(sheet, "ROOT", root), patch.object(sheet, "require_unchanged"), \
                 patch.object(sheet, "build_outputs", return_value={output: b"ROM", output.with_suffix(".ips"): b"IPS"}), \
                 patch.object(web.os, "replace", side_effect=fail_patch), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(OSError, "injected"):
                    sheet.execute(prepared, apply=True, output=output)
            self.assertEqual(b"original owner\n", project.read_bytes())
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".ips").exists())


@unittest.skipUnless(ROM.exists(), "matching local ROM and normal build dependencies required")
class SheetIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import export_script_sheet
        cls.directory = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls.directory.name)
        cls.addClassCleanup(cls.directory.cleanup)
        baseline = cls.tmp / "baseline.tsv"
        # Produce a fresh sheet through the independent exporter. A previously
        # shared review snapshot may intentionally remain on an older baseline.
        with redirect_stdout(io.StringIO()):
            export_script_sheet.export_sheet(ROM, ROOT / "script/en", baseline)
        with baseline.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle, delimiter="\t"))
        cls.changed_ids = ("195:$5593", "194:$55B1", "193:$4192", "202:$41B0")
        cls.changes = {r["id"]: r["en"].replace(".", "!", 1) for r in cls.rows if r["id"] in cls.changed_ids}
        edited = [dict(r, edited_en=cls.changes.get(r["id"], "")) for r in cls.rows]
        cls.incoming = cls.tmp / "returned.tsv"
        cls.incoming.write_text(tsv(edited), encoding="utf-8-sig")
        cls.before = sheet.workspace_snapshot()
        cls.prepared = sheet.prepare_sheet(ROM, cls.incoming)

    def tearDown(self):
        self.assertEqual(self.before, sheet.workspace_snapshot(), "Tests must never edit the actual project")

    def test_prepare_and_check_leave_project_and_sheet_unchanged(self):
        self.assertEqual(6695, len(self.prepared.records))
        self.assertEqual(7163, self.prepared.validation["exact_references"])
        self.assertEqual(self.changes, self.prepared.changes)
        content = self.incoming.read_bytes()
        with redirect_stdout(io.StringIO()), patch.object(web, "apply_transaction") as apply:
            sheet.execute(self.prepared)
            apply.assert_not_called()
        self.assertEqual(content, self.incoming.read_bytes())

    def test_test_rom_and_ips_contain_inserted_edits_and_keep_other_records(self):
        import build
        destination = self.tmp / "test-build.gbc"
        with redirect_stdout(io.StringIO()):
            sheet.execute(self.prepared, output=destination, font_style="both")
        source = ROM.read_bytes()
        for path in build.font_variant_output_paths(destination).values():
            output = path.read_bytes()
            self.assertEqual(output, ips.apply_patch(source, path.with_suffix(".ips").read_bytes()))
            for record in self.prepared.records:
                current = self.prepared.merged[record.id]
                expected = (b"" if current == "<empty>" else english.encode_source(current)) if current else record.raw
                for reference in record.references:
                    self.assertEqual(expected, insert.read_source_record(output, reference.group, reference.index), record.id)

    def test_apply_routes_to_draft_owners_and_writes_only_isolated_files(self):
        captured = {}
        commit = web.apply_transaction
        def isolated_apply(proposed, originals):
            captured.update(proposed)
            mapping = {p: self.tmp / "applied" / p.relative_to(ROOT) for p in proposed}
            for path, dest in mapping.items():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if originals.get(path) is not None:
                    dest.write_bytes(originals[path])
            commit({mapping[p]: value for p, value in proposed.items()},
                   {mapping[p]: originals.get(p) for p in proposed})
            for path, value in proposed.items():
                self.assertEqual(value, mapping[path].read_bytes())
        with redirect_stdout(io.StringIO()), patch.object(web, "apply_transaction", side_effect=isolated_apply):
            sheet.execute(self.prepared, apply=True)
        for path in ("script/editing/prose.tsv", "script/drafts/prose.tsv", "script/drafts/prose.generated.json",
                     "script/drafts/item_messages.tsv", "script/drafts/item_messages.generated.json",
                     "script/drafts/combat_messages.tsv", "script/drafts/combat_messages.generated.json",
                     "script/en/prose.tsv", "script/en/items.tsv", "script/en/messages.tsv"):
            self.assertIn(ROOT / path, captured)
        # Confirm that applying a prose sheet edit does not copy wrapped baselines
        # over unrelated authored scenes.
        original = {r["id"]: r["english"] for r in csv.DictReader(io.StringIO(
            self.before[ROOT / "script/editing/prose.tsv"].decode()), delimiter="\t")}
        updated = {r["id"]: r["english"] for r in csv.DictReader(io.StringIO(
            captured[ROOT / "script/editing/prose.tsv"].decode()), delimiter="\t")}
        for record_id, text in original.items():
            self.assertEqual(self.changes.get(record_id, text), updated[record_id])

    def test_invalid_text_and_changed_runtime_selectors_fail_before_writing(self):
        cases = {"194:$55B1": "Unsupported é", "193:$4192": "Hit <lookup:1A:C5> for <cF3><copy:01:1B:C5> damage."}
        for record_id, edit in cases.items():
            path = self.tmp / "invalid.tsv"
            path.write_text(tsv([dict(r, edited_en=edit if r["id"] == record_id else "") for r in self.rows]), encoding="utf-8")
            with self.subTest(record_id=record_id), patch.object(web, "apply_transaction") as apply, self.assertRaises(ValueError):
                sheet.prepare_sheet(ROM, path)
            apply.assert_not_called()

    def test_shared_name_change_cannot_leave_invalid_consumers(self):
        path = self.tmp / "changed-name.tsv"
        path.write_text(tsv([dict(r, edited_en="Koppi" if r["id"] == "192:$4E2D" else "") for r in self.rows]), encoding="utf-8")
        with patch.object(web, "apply_transaction") as apply, self.assertRaises(ValueError):
            sheet.prepare_sheet(ROM, path)
        apply.assert_not_called()

    def test_sheet_or_project_changes_after_check_prevent_writes(self):
        original = self.incoming.read_bytes()
        try:
            self.incoming.write_bytes(original + b"\n")
            with patch.object(web, "apply_transaction") as apply, self.assertRaisesRegex(ValueError, "sheet changed"):
                sheet.execute(self.prepared, apply=True)
            apply.assert_not_called()
        finally:
            self.incoming.write_bytes(original)
        with patch.object(web, "input_revision", return_value="changed"), patch.object(web, "apply_transaction") as apply:
            with self.assertRaisesRegex(ValueError, "Project files changed"):
                sheet.execute(self.prepared, apply=True)
            apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
