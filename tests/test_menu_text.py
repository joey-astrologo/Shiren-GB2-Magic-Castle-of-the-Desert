from dataclasses import replace
from hashlib import sha1
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import extract
import menu_text
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "menu_text.json"


class OriginalRomMenuTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.summary = menu_text.analyze(cls.rom, cls.result, cls.translated)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_complete_menu_text_contract_is_frozen(self):
        self.assertEqual(self.fixture, self.summary)
        self.assertEqual(176, self.summary["help_and_secrets_records"])
        self.assertEqual(219, self.summary["monster_notebook_records"])
        self.assertEqual(395, self.summary["total_translated_records"])

    def test_exact_family_counts_and_native_empty_slots_are_preserved(self):
        self.assertEqual(
            {
                "control_help": (28, 27),
                "technique_help": (33, 32),
                "wanderers_guide": (22, 21),
                "wanderer_secret_pages": (100, 96),
                "monster_notebook_descriptions": (219, 219),
            },
            {
                name: (row["logical_references"], row["stable_records"])
                for name, row in self.summary["families"].items()
            },
        )
        self.assertEqual(
            [
                "200:$5984",
                "200:$5985",
                "200:$5986",
                "200:$5987",
                "200:$5988",
                "200:$5989",
                "200:$63E4",
                "200:$63E5",
                "200:$63E6",
                "200:$63E7",
                "200:$63E8",
                "200:$63E9",
                "200:$6DE2",
                "200:$6DE3",
                "200:$6DE4",
                "200:$6DE5",
                "200:$6DE6",
                "200:$6DE7",
            ],
            self.summary["native_empty_notebook_slots"],
        )

    def test_positioned_topics_and_notebook_geometry_are_bounded(self):
        self.assertEqual(
            {"wanderers_guide": 10, "control_help": 9, "technique_help": 16},
            {
                name: row["entries"]
                for name, row in self.summary["positioned_topics"].items()
            },
        )
        for row in self.summary["positioned_topics"].values():
            self.assertLessEqual(
                row["widest"]["composer_pixels"], row["pixel_budget"]
            )
            self.assertLessEqual(
                row["widest"]["renderer_pixels"], row["pixel_budget"]
            )
        notebook = self.summary["families"]["monster_notebook_descriptions"]
        self.assertEqual(2, notebook["max_lines"])
        self.assertEqual(
            {"Controls", "Tech", "Secrets", "Control Guide"},
            {row["text"] for row in self.summary["positioned_headers"].values()},
        )

    def test_missing_required_menu_translation_fails_closed(self):
        broken = dict(self.translated)
        broken.pop((193, 0x54FF))
        with self.assertRaisesRegex(menu_text.MenuTextError, "missing 1 translation"):
            menu_text.analyze(self.rom, self.result, broken)

    def test_oversized_menu_line_fails_closed(self):
        broken = dict(self.translated)
        key = (200, 0x4F9C)
        text = "W" * 40 + "<br>Short"
        broken[key] = replace(
            broken[key], text=text, encoded=english.encode_source(text)
        )
        with self.assertRaisesRegex(menu_text.MenuTextError, "does not fit"):
            menu_text.analyze(self.rom, self.result, broken)

    def test_notebook_third_line_fails_closed(self):
        broken = dict(self.translated)
        key = (200, 0x4F9C)
        text = "First<br>Second<br>Third"
        broken[key] = replace(
            broken[key], text=text, encoded=english.encode_source(text)
        )
        with self.assertRaisesRegex(menu_text.MenuTextError, "must use 2 Notebook"):
            menu_text.analyze(self.rom, self.result, broken)

    def test_secret_canvas_reset_control_fails_closed(self):
        broken = dict(self.translated)
        key = (200, 0x71BE)
        text = broken[key].text.removeprefix("<box>")
        broken[key] = replace(
            broken[key], text=text, encoded=english.encode_source(text)
        )
        with self.assertRaisesRegex(menu_text.MenuTextError, "critical controls"):
            menu_text.analyze(self.rom, self.result, broken)


if __name__ == "__main__":
    unittest.main()
