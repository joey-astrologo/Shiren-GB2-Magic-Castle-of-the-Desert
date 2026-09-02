from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pyboy_state
import runtime_widths
import surfaces


STATE = ROOT / "SaveStates" / "unidentified-item-naming.state"


class PyBoyUnidentifiedItemFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STATE.is_file():
            raise unittest.SkipTest("native unidentified-item state is required")
        cls.work_ram = pyboy_state.work_ram(STATE)

    def test_fixture_contains_an_unidentified_item_and_safe_name_capacity(self):
        inventory_at = (
            surfaces.ITEM_INVENTORY_WRAM_BANK * 0x1000
            + surfaces.ITEM_INVENTORY_BASE - 0xD000
        )
        object_at = (
            surfaces.ITEM_OBJECT_WRAM_BANK * 0x1000
            + surfaces.ITEM_OBJECT_BASE - 0xD000
        )
        inventory = self.work_ram[
            inventory_at:inventory_at + surfaces.ITEM_INVENTORY_SLOTS
        ]
        objects = [value for value in inventory if value != 0xFF]
        self.assertTrue(objects)
        records = [
            self.work_ram[
                object_at + value * surfaces.ITEM_OBJECT_SIZE:
                object_at + (value + 1) * surfaces.ITEM_OBJECT_SIZE
            ]
            for value in objects
        ]
        self.assertTrue(any(record[6] == 0xFF for record in records))

        custom_at = 2 * 0x1000 + 0xDD78 - 0xD000
        custom_size = (
            runtime_widths.CUSTOM_ITEM_NAME_SLOTS
            * runtime_widths.CUSTOM_ITEM_NAME_SLOT_BYTES
        )
        self.assertEqual(
            custom_size,
            len(self.work_ram[custom_at:custom_at + custom_size]),
        )


if __name__ == "__main__":
    unittest.main()
