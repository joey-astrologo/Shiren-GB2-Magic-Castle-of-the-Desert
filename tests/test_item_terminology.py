import json
from hashlib import sha1
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "item_terminology.json").read_text(
        encoding="ascii"
    )
)
TITLE = re.compile(r"^<26>(.*?)<26>(?:<br>|$)")


class ItemTerminologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != FIXTURE["source_rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.by_reference = {
            (reference.group, reference.index): record
            for record in cls.result["records"]
            for reference in record.references
        }
        cls.by_id = {record.id: record for record in cls.result["records"]}

    @classmethod
    def record_text(cls, record):
        return cls.translated[(record.bank, record.address)].text

    @classmethod
    def reference_text(cls, group, index):
        return cls.record_text(cls.by_reference[(group, index)])

    def test_approved_series_names_are_frozen_in_names_and_descriptions(self):
        self.assertEqual(50, len(FIXTURE["approved"]))
        for row in FIXTURE["approved"]:
            with self.subTest(item_id=row["item_id"], english=row["english"]):
                name = self.reference_text(4, row["item_id"])
                description = self.reference_text(6, row["item_id"])
                title = TITLE.match(description)
                self.assertEqual(row["english"], name)
                self.assertIsNotNone(title)
                self.assertEqual(name, title.group(1))
                self.assertNotEqual(row["previous"], name)

    def test_every_identified_description_title_tracks_its_item_name(self):
        for item_id in range(1, 216):
            with self.subTest(item_id=item_id):
                name = self.reference_text(4, item_id)
                description = self.reference_text(6, item_id)
                title = TITLE.match(description)
                self.assertIsNotNone(title)
                self.assertEqual(name, title.group(1))

    def test_precedent_free_names_remain_explicitly_provisional(self):
        self.assertEqual(3, len(FIXTURE["provisional"]))
        for row in FIXTURE["provisional"]:
            with self.subTest(item_id=row["item_id"]):
                self.assertEqual(
                    row["english"], self.reference_text(4, row["item_id"])
                )

    def test_unidentified_item_roots_track_the_approved_names(self):
        self.assertEqual(26, len(FIXTURE["roots"]))
        for row in FIXTURE["roots"]:
            with self.subTest(root_index=row["root_index"]):
                self.assertEqual(
                    row["english"], self.reference_text(12, row["root_index"])
                )

    def test_critical_bracelet_description_names_the_actual_effect(self):
        description = self.reference_text(6, 84)
        self.assertIn(FIXTURE["critical_description_fragment"], description)

    def test_literal_item_references_keep_reviewed_wraps_and_page_controls(self):
        for row in FIXTURE["surface_records"]:
            with self.subTest(record_id=row["id"]):
                self.assertEqual(
                    row["english"], self.record_text(self.by_id[row["id"]])
                )


if __name__ == "__main__":
    unittest.main()
