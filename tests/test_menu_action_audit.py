from hashlib import sha1
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import menu_action_audit


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class MenuActionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the audit fixture")
        cls.audit = menu_action_audit.audit(cls.rom, ROOT / "script" / "en")

    def test_every_native_event_choice_record_is_discovered_and_partitioned(self):
        event = self.audit["event_choices"]
        self.assertEqual(0x1E, event["opcode"])
        self.assertEqual(13, event["record_bytes"])
        self.assertEqual(65, event["occurrences"])
        self.assertEqual(29, event["unique_sets"])
        self.assertEqual(55, event["release"]["occurrences"])
        self.assertEqual(19, event["release"]["unique_sets"])
        self.assertEqual(10, event["developer"]["occurrences"])
        self.assertEqual(10, event["developer"]["unique_sets"])

    def test_release_overflow_sets_and_pixels_are_reported_exactly(self):
        release = self.audit["event_choices"]["release"]
        self.assertEqual(14, release["safe_native_sets"])
        self.assertEqual(5, release["safe_widened_sets"])
        self.assertEqual(0, release["overflow_sets"])
        self.assertEqual(0, release["overflow_occurrences"])
        self.assertEqual(
            [],
            [
                (
                    menu["name"],
                    tuple(
                        (label["text"], label["renderer_pixels"], menu["text_budget"])
                        for label in menu["overflow_labels"]
                    ),
                )
                for menu in release["sets"]
                if menu["status"] == "overflow"
            ],
        )

    def test_approved_training_action_is_train_and_fits_native_popup(self):
        menu = next(
            menu
            for menu in self.audit["event_choices"]["release"]["sets"]
            if menu["references"] == [[7, 152], [7, 15], [7, 135]]
        )
        self.assertEqual("Train / Info / Quit", menu["name"])
        self.assertEqual("safe_native", menu["status"])
        self.assertEqual(25, menu["labels"][0]["renderer_pixels"])
        self.assertEqual(7, menu["labels"][0]["clearance_pixels"])

    def test_review_actions_and_approved_intensive_wording(self):
        release = self.audit["event_choices"]["release"]
        self.assertEqual(
            {},
            {
                menu["name"]: (
                    menu["context"],
                    menu["recommended_action"],
                    tuple(
                        (
                            candidate["text"],
                            candidate["renderer_pixels"],
                            candidate["fits_native"],
                        )
                        for candidate in menu["wording_candidates"]
                    ),
                )
                for menu in release["sets"]
                if menu["status"] == "overflow"
            },
        )
        intensive = next(
            menu
            for menu in release["sets"]
            if menu["references"] == [[7, 153], [7, 15], [7, 135]]
        )
        self.assertEqual("Train+ / Info / Quit", intensive["name"])
        self.assertEqual("safe_native", intensive["status"])
        self.assertEqual(30, intensive["labels"][0]["renderer_pixels"])
        self.assertEqual(2, intensive["labels"][0]["clearance_pixels"])
        self.assertEqual("approved_wording", intensive["recommended_action"])
        delivery = next(
            menu
            for menu in release["sets"]
            if menu["references"] == [[7, 128], [7, 127], [7, 146], [7, 158]]
        )
        self.assertEqual("safe_widened", delivery["status"])
        self.assertEqual("approved_geometry", delivery["recommended_action"])
        self.assertEqual(6, delivery["labels"][1]["clearance_pixels"])

    def test_approved_contextual_short_labels_fit_native_popups(self):
        release = self.audit["event_choices"]["release"]
        expected = {
            ((7, 136), (7, 137), (7, 145), (7, 158)): (
                "Yes / No / Info / Later",
                (("Info", 21, 11),),
            ),
            ((7, 111), (7, 112), (7, 135)): (
                "Send / Get / Quit",
                (("Get", 16, 16),),
            ),
            ((7, 160), (7, 161), (7, 162), (7, 135)): (
                "SOS / Revive / Thanks / Quit",
                (("Revive", 30, 2), ("Thanks", 31, 1)),
            ),
        }
        for references, (name, labels) in expected.items():
            with self.subTest(name=name):
                menu = next(
                    menu
                    for menu in release["sets"]
                    if tuple(map(tuple, menu["references"])) == references
                )
                self.assertEqual(name, menu["name"])
                self.assertEqual("safe_native", menu["status"])
                actual = tuple(
                    (
                        label["text"],
                        label["renderer_pixels"],
                        label["clearance_pixels"],
                    )
                    for label in menu["labels"]
                    if label["text"] in {row[0] for row in labels}
                )
                self.assertEqual(labels, actual)

    def test_existing_widened_and_special_glyph_menus_are_not_false_positives(self):
        release = self.audit["event_choices"]["release"]
        self.assertEqual(
            [
                "Deposit / Withdraw / Balance / Quit",
                "Cable / Password / Quit",
                "Cable / Password / Cancel / Later",
                "Forge / Repair / Synthesis / Remove / Quit",
                "Deposit / Withdraw / Trash / Quit",
            ],
            [menu["name"] for menu in release["sets"]
             if menu["status"] == "safe_widened"],
        )
        password_graphic = next(
            label
            for menu in release["sets"]
            for label in menu["labels"]
            if label["text"] == "<passwordLeft><passwordRight>"
        )
        self.assertEqual(32, password_graphic["renderer_pixels"])

    def test_other_action_paths_are_complete_and_fit(self):
        positioned = self.audit["positioned_text"]
        self.assertTrue(positioned["complete"])
        self.assertEqual(120, positioned["discovered_call_sites"])

        items = self.audit["item_actions"]
        self.assertEqual(24, items["entries"])
        self.assertEqual(48, items["text_budget"])
        self.assertEqual(41, items["widest"]["renderer_pixels"])
        self.assertEqual([], items["overflow_labels"])

        stairs = self.audit["stairs"]
        self.assertEqual(2, stairs["entries"])
        self.assertEqual(56, stairs["text_budget"])
        self.assertEqual(46, stairs["widest"]["renderer_pixels"])
        self.assertEqual([], stairs["overflow_labels"])

    def test_developer_only_choices_are_kept_separate(self):
        developer = self.audit["event_choices"]["developer"]
        self.assertEqual(1, developer["safe_native_sets"])
        self.assertEqual(9, developer["overflow_sets"])


if __name__ == "__main__":
    unittest.main()
