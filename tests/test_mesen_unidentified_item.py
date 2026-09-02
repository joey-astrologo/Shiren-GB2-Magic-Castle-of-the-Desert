from hashlib import sha1
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import mesen_state
import runtime_widths
import surfaces


class MesenUnidentifiedItemHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT / "tools" / "mesen_spawn_unidentified_item.lua"
        ).read_text(encoding="utf-8")

    def constant(self, name):
        match = re.search(
            r"^local %s = (0x[0-9A-F]+|[0-9]+)$" % re.escape(name),
            self.source,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, name)
        return int(match.group(1), 0)

    def test_helper_addresses_match_the_measured_wram_contracts(self):
        self.assertEqual(surfaces.ITEM_INVENTORY_WRAM_BANK, self.constant("INVENTORY_BANK"))
        self.assertEqual(surfaces.ITEM_INVENTORY_BASE, self.constant("INVENTORY_BASE"))
        self.assertEqual(
            self.constant("INVENTORY_BANK") * 0x1000
            + self.constant("INVENTORY_BASE") - 0xD000,
            self.constant("INVENTORY_WRAM"),
        )
        self.assertEqual(surfaces.ITEM_INVENTORY_SLOTS, self.constant("INVENTORY_SLOTS"))
        self.assertEqual(surfaces.ITEM_OBJECT_WRAM_BANK, self.constant("OBJECT_BANK"))
        self.assertEqual(surfaces.ITEM_OBJECT_BASE, self.constant("OBJECT_BASE"))
        self.assertEqual(
            self.constant("OBJECT_BANK") * 0x1000
            + self.constant("OBJECT_BASE") - 0xD000,
            self.constant("OBJECT_WRAM"),
        )
        self.assertEqual(surfaces.ITEM_OBJECT_SIZE, self.constant("OBJECT_SIZE"))
        self.assertEqual(0xFF, self.constant("UNIDENTIFIED_OBJECT_MARKER"))
        self.assertEqual(2, self.constant("IDENTIFICATION_BANK"))
        self.assertEqual(0xDC82, self.constant("IDENTIFICATION_BASE"))
        self.assertEqual(0x2C82, self.constant("IDENTIFICATION_WRAM"))
        self.assertEqual(0xDE1C, self.constant("HISTORY_BASE"))
        self.assertEqual(0x2E1C, self.constant("HISTORY_WRAM"))
        self.assertEqual(0xDD78, self.constant("CUSTOM_NAME_BASE"))
        self.assertEqual(0x2D78, self.constant("CUSTOM_NAME_WRAM"))
        self.assertEqual(runtime_widths.CUSTOM_ITEM_NAME_SLOTS, self.constant("CUSTOM_NAME_SLOTS"))
        self.assertEqual(runtime_widths.CUSTOM_ITEM_NAME_SLOT_BYTES, self.constant("CUSTOM_NAME_SLOT_BYTES"))
        self.assertEqual(0xC12B, self.constant("ACTION_INHIBIT_ADDRESS"))
        self.assertEqual(0x02, self.constant("ACTION_INHIBIT_MASK"))
        self.assertIn('{ "gbWorkRam", "gameboyWorkRam" }', self.source)
        self.assertIn(
            'foundRecord[7] == UNIDENTIFIED_OBJECT_MARKER',
            self.source,
        )
        self.assertIn(
            'emu.read(ACTION_INHIBIT_ADDRESS, cpuMemT) & ACTION_INHIBIT_MASK == 0',
            self.source,
        )

    def test_all_representative_targets_follow_native_category_partitions(self):
        rows = re.findall(
            r'^\s*(\w+) = target\("([^"]+)", '
            r"(0x[0-9A-F]+), (0x[0-9A-F]+), "
            r"(0x[0-9A-F]+), (0x[0-9A-F]+)\),$",
            self.source,
            re.MULTILINE,
        )
        self.assertEqual(5, len(rows))
        expected = {
            "passage_bracelet": ("Waterwalk Bracelet", "bracelet"),
            "herb": ("Herb", "grass"),
            "windblade_scroll": ("Windblade Scroll", "scroll"),
            "knockback_staff": ("Knockback Staff", "staff"),
            "preservation_pot": ("Preservation Pot", "jar"),
        }
        seeds = {seed.category: seed for seed in surfaces.ITEM_CATEGORY_SEEDS}
        partitions = {row[0]: row[1:] for row in surfaces.ITEM_NAME_ROOT_PARTITIONS}
        for key, label, item, action, root, appearance in rows:
            item, action, root, appearance = map(
                lambda value: int(value, 0), (item, action, root, appearance)
            )
            self.assertEqual(expected[key][0], label)
            category = expected[key][1]
            first, last, first_item = partitions[category]
            self.assertTrue(first <= root <= last)
            self.assertTrue(first <= appearance <= last)
            self.assertEqual(first_item + root - first, item)
            self.assertEqual(seeds[category].action_class, action)

    def test_mamel_fixture_is_clean_and_has_safe_injection_capacity(self):
        work_ram = mesen_state.load_fields(ROOT / "SaveStates" / "Mamel.mss")[
            "workRam"
        ]
        root = 0x32
        mapping = self.constant("IDENTIFICATION_WRAM") + root * 2
        self.assertEqual(b"\xFF\xFF", work_ram[mapping:mapping + 2])
        history = self.constant("HISTORY_WRAM") + root // 8
        self.assertFalse(work_ram[history] & (1 << (root % 8)))
        custom = self.constant("CUSTOM_NAME_WRAM")
        custom_bytes = self.constant("CUSTOM_NAME_SLOTS") * self.constant(
            "CUSTOM_NAME_SLOT_BYTES"
        )
        self.assertEqual(bytes([0xFF]) * custom_bytes, work_ram[custom:custom + custom_bytes])

        inventory = work_ram[
            self.constant("INVENTORY_WRAM"):
            self.constant("INVENTORY_WRAM") + self.constant("INVENTORY_SLOTS")
        ]
        self.assertIn(self.constant("INVENTORY_SENTINEL"), inventory)
        occupied = set(
            value for value in inventory
            if value != self.constant("INVENTORY_SENTINEL")
        )
        objects = self.constant("OBJECT_WRAM")
        self.assertTrue(any(
            index not in occupied
            and work_ram[
                objects + index * self.constant("OBJECT_SIZE"):
                objects + (index + 1) * self.constant("OBJECT_SIZE")
            ] == bytes(self.constant("OBJECT_SIZE"))
            for index in range(self.constant("OBJECT_COUNT"))
        ))


class MesenUnidentifiedItemHelperLiveTests(unittest.TestCase):
    """Run the distributable helper itself against the supplied Mesen fixture."""

    @classmethod
    def setUpClass(cls):
        candidates = [
            os.environ.get("MESEN_BIN"),
            shutil.which("Mesen"),
            shutil.which("mesen"),
            "/Applications/Mesen.app/Contents/MacOS/Mesen",
        ]
        cls.mesen = next(
            (Path(path) for path in candidates if path and Path(path).is_file()),
            None,
        )
        if cls.mesen is None:
            raise unittest.SkipTest("Mesen test-runner executable is unavailable")

        cls.source = ROOT / (
            "Fushigi no Dungeon - Fuurai no Shiren GB2 - "
            "Sabaku no Majou (Japan).gbc"
        )
        if not cls.source.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

        cls.state = ROOT / "SaveStates" / "Mamel.mss"
        if not cls.state.is_file():
            raise unittest.SkipTest("Mamel Mesen state fixture is unavailable")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "unidentified-item-mesen.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(cls.source),
                str(ROOT / "script" / "en"),
                str(cls.localized),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if built.returncode:
            cls.temporary.cleanup()
            raise AssertionError(
                "could not build unidentified-item fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_distributable_helper_prepares_the_mamel_fixture_in_mesen(self):
        env = os.environ.copy()
        env["GB2_UNIDENTIFIED_HELPER_FIXTURE"] = str(self.state)
        env["GB2_UNIDENTIFIED_TARGET"] = "windblade_scroll"
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tools" / "mesen_spawn_unidentified_item.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS unidentified-helper target=windblade_scroll "
            "slot=1 object=9 root=50 appearance=50",
            output,
        )


if __name__ == "__main__":
    unittest.main()
