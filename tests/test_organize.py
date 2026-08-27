from hashlib import sha1
import json
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import organize
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "script_organization.json").read_text(
        encoding="utf-8"
    )
)


class OriginalRomScriptOrganizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.organized = organize.classify(cls.result)

    def test_complete_single_owner_partition_is_frozen(self):
        measured = organize.summary(self.result, organized=self.organized)
        self.assertEqual(FIXTURE["manifest"], measured)
        self.assertTrue(measured["partition_complete"])
        self.assertEqual(6695, measured["records"])
        self.assertEqual(7163, measured["logical_references"])
        self.assertEqual(
            {"assigned_once": 7163, "unclassified": 0, "ambiguous": 0},
            measured["reference_coverage"],
        )
        self.assertEqual(0, measured["review_records"])
        ids = [row.record.id for row in self.organized]
        self.assertEqual(len(ids), len(set(ids)))

    def test_proven_mixed_group_boundaries_route_to_the_right_files(self):
        by_reference = {}
        for row in self.organized:
            for reference in row.record.references:
                by_reference[(reference.group, reference.index)] = row

        expectations = {
            (4, 1): ("glossary", "identified_item_names"),
            (6, 1): ("items", "item_descriptions"),
            (17, 0): ("ui_system", "trap_menu_status"),
            (17, 1): ("glossary", "trap_names"),
            (24, 0): ("ui_system", "adventure_and_miscellaneous_ui"),
            (24, 1): ("glossary", "location_names"),
            (24, 48): ("glossary", "location_names"),
            (24, 49): ("ui_system", "adventure_and_miscellaneous_ui"),
            (24, 50): ("ui_system", "adventure_and_miscellaneous_ui"),
            (29, 0): ("monsters", "monster_notebook_descriptions"),
            (116, 0): ("glossary", "numbered_monster_variant_names"),
        }
        for reference, (category, section) in expectations.items():
            with self.subTest(reference=reference):
                row = by_reference[reference]
                self.assertEqual(category, row.category)
                self.assertIn(section, row.sections)

    def test_generated_category_files_are_deterministic_and_loadable(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = organize.write_outputs(self.result, temporary)
            actual = {
                path.name: sha1(path.read_bytes()).hexdigest() for path in paths
            }
            self.assertEqual(FIXTURE["output_sha1"], actual)
            self.assertEqual({}, translations.load_path(temporary, self.result["records"]))

    def test_regeneration_preserves_existing_english_cells(self):
        with tempfile.TemporaryDirectory() as temporary:
            organize.write_outputs(self.result, temporary)
            path = Path(temporary) / "glossary.tsv"
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines[1].endswith("\t"))
            record_id = lines[1].split("\t", 1)[0]
            lines[1] += "One"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            organize.write_outputs(self.result, temporary)
            loaded = translations.load_path(temporary, self.result["records"])
            record = next(record for record in self.result["records"] if record.id == record_id)
            self.assertEqual("One", loaded[(record.bank, record.address)].text)

    def test_unknown_reference_is_preserved_in_the_review_bucket(self):
        record = self.result["records"][0]
        unknown = replace(record.references[0], group=24, index=67)
        synthetic_record = replace(record, references=(unknown,))
        synthetic = {
            "rom_sha1": self.result["rom_sha1"],
            "records": (synthetic_record,),
            "references": (unknown,),
        }
        row = organize.classify(synthetic)[0]
        self.assertEqual("review", row.category)
        self.assertEqual(("unclassified_reference:24:67",), row.review_reasons)
        measured = organize.summary(synthetic, organized=(row,))
        self.assertEqual(1, measured["review_records"])
        self.assertEqual(1, measured["reference_coverage"]["unclassified"])


if __name__ == "__main__":
    unittest.main()
