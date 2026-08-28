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

import mesen_state
import surfaces
import extract


class MesenBlankScrollHelperTests(unittest.TestCase):
    def test_helper_matches_the_proven_gb2_inventory_and_write_route(self):
        source = (ROOT / "tools" / "mesen_spawn_blank_scroll.lua").read_text(
            encoding="utf-8"
        )

        def constant(name):
            match = re.search(
                r"^local %s = (0x[0-9A-F]+|[0-9]+)$" % re.escape(name),
                source,
                re.MULTILINE,
            )
            self.assertIsNotNone(match, name)
            return int(match.group(1), 0)

        self.assertEqual(surfaces.ITEM_INVENTORY_WRAM_BANK, constant("INVENTORY_BANK"))
        self.assertEqual(surfaces.ITEM_INVENTORY_BASE, constant("INVENTORY_BASE"))
        self.assertEqual(
            constant("INVENTORY_BANK") * 0x1000
            + constant("INVENTORY_BASE")
            - 0xD000,
            constant("INVENTORY_WRAM"),
        )
        self.assertEqual(surfaces.ITEM_INVENTORY_SLOTS, constant("INVENTORY_SLOTS"))
        self.assertEqual(
            surfaces.ITEM_INVENTORY_SENTINEL, constant("INVENTORY_SENTINEL")
        )
        self.assertEqual(surfaces.ITEM_OBJECT_WRAM_BANK, constant("OBJECT_BANK"))
        self.assertEqual(surfaces.ITEM_OBJECT_BASE, constant("OBJECT_BASE"))
        self.assertEqual(
            constant("OBJECT_BANK") * 0x1000 + constant("OBJECT_BASE") - 0xD000,
            constant("OBJECT_WRAM"),
        )
        self.assertEqual(surfaces.ITEM_OBJECT_SIZE, constant("OBJECT_SIZE"))
        self.assertIn('{ "gbWorkRam", "gameboyWorkRam" }', source)

        record_match = re.search(r"^local ITEM_RECORD = \{ ([^}]+) \}$", source, re.MULTILINE)
        self.assertIsNotNone(record_match)
        record = tuple(
            int(value.strip(), 0) for value in record_match.group(1).split(",")
        )
        route = next(
            row for row in surfaces.ITEM_SPECIAL_ACTION_ROUTES
            if row[0] == "blank_scroll_write"
        )
        seed = surfaces.ITEM_CATEGORY_SEEDS[route[2]]
        self.assertEqual(("scroll", 146, 7), (route[1], route[6], seed.action_class))
        self.assertEqual((146, 7, 0, 0, 0, 0, 0, 0), record)
        self.assertEqual(record[0], constant("ITEM_ID"))

        # Prove the flattened addresses against a real Mesen 2 Work RAM field rather
        # than assuming CPU-visible $Dxxx addresses can switch banks from Lua.
        work_ram = mesen_state.load_fields(ROOT / "SaveStates" / "Mamel.mss")[
            "workRam"
        ]
        inventory_at = constant("INVENTORY_WRAM")
        inventory = work_ram[
            inventory_at:inventory_at + constant("INVENTORY_SLOTS")
        ]
        free_slot = inventory.index(constant("INVENTORY_SENTINEL"))
        occupied = set(inventory[:free_slot])
        object_at = constant("OBJECT_WRAM")
        free_object = next(
            index
            for index in range(constant("OBJECT_COUNT"))
            if index not in occupied
            and work_ram[
                object_at + index * constant("OBJECT_SIZE"):
                object_at + (index + 1) * constant("OBJECT_SIZE")
            ] == bytes(constant("OBJECT_SIZE"))
        )
        self.assertEqual(1, free_slot)
        self.assertEqual(9, free_object)


class MesenBlankScrollLiveTests(unittest.TestCase):
    """Exercise the reported full-name confirmation route in Mesen itself."""

    ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
    FAILURE_STATE_SHA1 = "04d328075584c9e5b41e7686d1067157bccd2b43"
    FAILURE_SRAM_SHA1 = "140931481938c6d9e22d8adc4c4a74d648dc9c75"

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

        cls.source = ROOT / cls.ROM_NAME
        if not cls.source.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

        cls.state = ROOT / "SaveStates" / "Mamel.mss"
        if not cls.state.is_file():
            raise unittest.SkipTest("Mamel Mesen state fixture is unavailable")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "blank-scroll-mesen.gbc"
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
                "could not build Mesen Blank Scroll fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _run_route(self, learned):
        env = os.environ.copy()
        env["GB2_MSS_PATH"] = str(self.state)
        env["GB2_EXPECT_MATCH"] = "1" if learned else "0"
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_blank_scroll_live.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=40,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn("Blank Scroll editor reached", output)
        self.assertIn("Windblade confirmed", output)
        self.assertIn("screen=A99BBFF6", output)
        return output

    def test_learned_full_windblade_converts_and_returns_to_gameplay(self):
        output = self._run_route(learned=True)
        self.assertIn("Blank Scroll converted", output)
        self.assertRegex(output, r"PASS converted=\d+")

    def test_unlearned_full_windblade_is_rejected_without_freezing(self):
        output = self._run_route(learned=False)
        self.assertNotIn("Blank Scroll converted", output)
        self.assertIn("PASS converted=nil", output)

    def test_user_failure_fixture_converts_without_reset_or_inventory_damage(self):
        state = ROOT / "SaveStates" / "blank-scroll.mss"
        sram = ROOT / "SaveStates" / "blank-scroll.srm"
        if not state.is_file():
            self.skipTest("user-supplied Blank Scroll failure fixture is unavailable")
        self.assertEqual(self.FAILURE_STATE_SHA1, sha1(state.read_bytes()).hexdigest())

        env = os.environ.copy()
        env["GB2_MSS_PATH"] = str(state)
        if sram.is_file():
            self.assertEqual(
                self.FAILURE_SRAM_SHA1, sha1(sram.read_bytes()).hexdigest()
            )
            env["GB2_SRM_PATH"] = str(sram)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_blank_scroll_failure_fixture.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=40,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertNotIn("restarted the game", output)
        self.assertIn(
            "PASS fixture match=32 object=18 item=7F reset=false",
            output,
        )
