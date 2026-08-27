from hashlib import sha1
import csv
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import english_font
import layout
import wrap_items


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
ROM_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"


class ItemDescriptionWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists() or sha1(path.read_bytes()).hexdigest() != ROM_SHA1:
            raise unittest.SkipTest("matching original ROM not present")
        cls.font_rom = english_font.install(path.read_bytes())

    def test_reflow_preserves_every_visible_character(self):
        source = (
            "<26>Synthesis Pot<26><br>"
            "Synthesizes weapons, shields, Staves, or Bracelets. "
            "Categories cannot be mixed."
        )
        wrapped = wrap_items.wrap_description(self.font_rom, source, "test:$0000")
        self.assertEqual(wrap_items.visible_words(source), wrap_items.visible_words(wrapped))
        self.assertNotEqual(source, wrapped)

    def test_production_catalog_is_safe_and_idempotent(self):
        with (ROOT / "script" / "en" / "items.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(216, len(rows))
        for row in rows:
            with self.subTest(record=row["id"]):
                wrapped = wrap_items.wrap_description(
                    self.font_rom, row["english"], row["id"]
                )
                self.assertEqual(row["english"], wrapped)
                measured = layout.source_layout(
                    self.font_rom,
                    english.encode_source(wrapped),
                    mode=0x08,
                    record_id=row["id"],
                )
                self.assertTrue(measured.safe)
                self.assertLessEqual(len(measured.lines), 11)


if __name__ == "__main__":
    unittest.main()
