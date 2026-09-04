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

    def test_grass_consumption_uses_eat_and_consume_language(self):
        self.assertEqual("Eat", self.reference_text(7, 6))

        consumable_description_ids = (
            "202:$6072", "202:$60A0", "202:$60D3", "202:$60F7",
            "202:$6176", "202:$6193", "202:$61B7", "202:$61DC",
            "202:$61F6", "202:$6212", "202:$6233", "202:$6259",
            "202:$6297", "202:$62C6", "202:$62E1", "202:$6326",
            "202:$6341",
        )
        for record_id in consumable_description_ids:
            with self.subTest(description=record_id):
                self.assertIn(
                    "Consume it",
                    self.record_text(self.by_id[record_id]).replace("<br>", " "),
                )

        tutorial_ids = (
            "195:$724F", "205:$6B40", "205:$6B92", "205:$6BE4",
            "205:$6C40", "205:$6D02", "205:$6D54", "205:$6DAD",
            "205:$6E10", "205:$6EB4", "205:$6F04",
        )
        for record_id in tutorial_ids:
            with self.subTest(tutorial=record_id):
                self.assertIn("Consume", self.record_text(self.by_id[record_id]))

        medicine = self.record_text(self.by_id["194:$5679"])
        self.assertIn("and consumed it.", medicine)

        muzzle = self.record_text(self.by_id["202:$646E"]).replace("<br>", " ")
        self.assertIn("You cannot eat or read.", muzzle)

        drinking = re.compile(r"\b(?:drink|drinks|drinking|drank|drunk)\b", re.I)
        remaining = {
            record.id
            for record in self.result["records"]
            if (record.bank, record.address) in self.translated
            and drinking.search(self.record_text(record))
        }
        self.assertEqual({"197:$470E", "200:$5DBC", "200:$67CB"}, remaining)

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
