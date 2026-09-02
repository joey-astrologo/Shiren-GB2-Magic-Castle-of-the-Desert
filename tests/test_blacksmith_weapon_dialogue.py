from hashlib import sha1
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import english_font
import extract
import layout
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
BLACKSMITH_RECORD_ID = "199:$4D50"
WEAPON_GROUP = 4
WEAPON_INDICES = range(1, 34)
APPROVED_FIRST_PAGE = (
    "Blacksmith:<br><cF8>8...<br>"
    "Understood. Leave it to me.<page>"
)


class BlacksmithWeaponDialogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.by_id = {record.id: record for record in cls.result["records"]}
        cls.by_reference = {
            (reference.group, reference.index): record
            for record in cls.result["records"]
            for reference in record.references
        }
        cls.font_rom = english_font.install(
            cls.rom, approved=english_font.load_approved(style="shadowed")
        )

    @classmethod
    def text_for_record(cls, record):
        return cls.translated[(record.bank, record.address)].text

    def test_every_weapon_name_and_page_cursor_fit_the_approved_three_lines(self):
        template = self.text_for_record(self.by_id[BLACKSMITH_RECORD_ID])
        self.assertEqual(APPROVED_FIRST_PAGE, template.split("<box>", 1)[0])

        names = tuple(
            self.text_for_record(
                self.by_reference[(WEAPON_GROUP, weapon_index)]
            )
            for weapon_index in WEAPON_INDICES
        )
        self.assertEqual(33, len(names))
        self.assertEqual(33, len(set(names)))

        for name in names:
            concrete = template.replace("<cF8>8", name)
            measured = layout.source_layout(
                self.font_rom,
                english.encode_source(concrete),
                mode=0x02,
            )
            first_page = tuple(
                line for line in measured.lines if line.surface == 0
            )
            endpoints = tuple(
                endpoint
                for endpoint in measured.page_endpoints
                if endpoint.surface == 0
            )
            with self.subTest(weapon=name):
                self.assertTrue(measured.safe)
                self.assertEqual(3, len(first_page))
                self.assertEqual(1, len(endpoints))
                self.assertEqual(2, endpoints[0].line)
                self.assertFalse(endpoints[0].wraps)


if __name__ == "__main__":
    unittest.main()
