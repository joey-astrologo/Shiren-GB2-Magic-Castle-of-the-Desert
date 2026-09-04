from hashlib import sha1
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import extract
import name6
import rescue_presentation
import spell_input
import unidentified_names


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
EXPECTED_BOTTOM_BORDER = bytes((0x28,)) + bytes((0x2A,)) * 18 + bytes((0x28,))


class GraphicalInputBorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file():
            raise unittest.SkipTest("source ROM is required")
        cls.rom = source.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def _keyboard_map_for_mode(self, mode):
        if mode == 0:
            return unidentified_names.english_keyboard_map(self.rom)
        if mode == 1:
            raw = bytearray(name6.english_keyboard_map(self.rom))
            raw[10 * 20 + 13] = english.ENGLISH_CODES["-"]
            return bytes(raw)
        if mode in (2, 4):
            return name6.english_keyboard_map(self.rom)
        if mode == 3:
            return spell_input.english_keyboard_map(self.rom)
        if mode in (5, 6, 7, 8):
            return rescue_presentation.english_keyboard_map(self.rom)
        self.fail("unowned graphical-input mode %d" % mode)

    def test_every_graphical_input_mode_preserves_the_complete_bottom_border(self):
        for mode in range(9):
            with self.subTest(mode=mode):
                raw = self._keyboard_map_for_mode(mode)
                self.assertEqual(20 * 16, len(raw))
                self.assertEqual(EXPECTED_BOTTOM_BORDER, raw[-20:])


if __name__ == "__main__":
    unittest.main()
