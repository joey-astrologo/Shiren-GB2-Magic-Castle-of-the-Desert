from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pyboy_state


class PyBoyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = ROOT / "SaveStates" / "Mamel.state"
        cls.rom = (
            ROOT
            / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
        )
        if not cls.state.is_file() or not cls.rom.is_file():
            raise unittest.SkipTest("native state and matching ROM are required")

    def test_supplied_mamel_state_contains_four_sram_banks(self):
        ram = pyboy_state.cart_ram(self.state, self.rom)
        self.assertEqual(0x8000, len(ram))
        self.assertEqual(b"FGB20", ram[11:16])

    def test_supplied_mamel_state_contains_all_wram_banks(self):
        ram = pyboy_state.work_ram(self.state, self.rom)
        self.assertEqual(0x8000, len(ram))
        self.assertEqual(bytes.fromhex("4d 53 30 01"), ram[:4])

    def test_non_native_extension_is_rejected(self):
        with self.assertRaisesRegex(pyboy_state.PyBoyStateError, "native"):
            pyboy_state.cart_ram(self.state.with_suffix(".legacy"), self.rom)


if __name__ == "__main__":
    unittest.main()
