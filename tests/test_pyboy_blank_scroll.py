from hashlib import sha1
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import pyboy_route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "blank-scroll.state"
STATE_SHA1 = "c36ee8c975fc6dc59f965a184461940c50473e45"


class PyBoyBlankScrollFailureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        if not cls.source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and native Blank Scroll state are required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "blank-scroll.gbc"
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
                "could not build Blank Scroll fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    @staticmethod
    def _work_byte(pyboy, offset):
        if offset < 0x1000:
            return pyboy.memory[0xC000 + offset]
        old_bank = pyboy.memory[0xFF70]
        try:
            pyboy.memory[0xFF70] = offset // 0x1000
            return pyboy.memory[0xD000 + offset % 0x1000]
        finally:
            pyboy.memory[0xFF70] = old_bank

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_full_windblade_confirmation_converts_without_reset_or_damage(self):
        pyboy = pyboy_route.start(self.PyBoy, self.localized, STATE)
        windblade = bytes.fromhex("20 38 3d 33 31 3b 30 33 34")
        reset_observed = False
        try:
            def at_reset(_context=None):
                nonlocal reset_observed
                reset_observed = True

            pyboy.hook_register(0, 0x01C1, at_reset, None)
            self.assertEqual(1, pyboy.memory[0xC195])
            self.assertEqual(len(windblade), pyboy.memory[0xC152])
            self.assertEqual(11, pyboy.memory[0xC153])
            self.assertEqual(windblade, bytes(pyboy.memory[0xC16D:0xC176]))

            selected = pyboy.memory[0xC156]
            inventory_before = bytes(
                self._work_byte(pyboy, 0x12C1 + slot) for slot in range(20)
            )
            object_id = inventory_before[selected]
            self.assertNotEqual(0xFF, object_id)
            object_before = bytes(
                self._work_byte(pyboy, 0x2482 + object_id * 8 + offset)
                for offset in range(8)
            )
            self.assertEqual(0x92, object_before[0])

            pyboy_route.run_frames(pyboy, 100, actions=((60, "a"),))
            self.assertFalse(reset_observed)
            self.assertEqual(0x32, pyboy.memory[0xC196])
            self.assertEqual(1, pyboy.memory[0xC195])
            self.assertEqual(windblade[:7] + b"\xFF", bytes(pyboy.memory[0xC16D:0xC175]))
            inventory_after = bytes(
                self._work_byte(pyboy, 0x12C1 + slot) for slot in range(20)
            )
            object_after = bytes(
                self._work_byte(pyboy, 0x2482 + object_id * 8 + offset)
                for offset in range(8)
            )
            self.assertEqual(inventory_before, inventory_after)
            self.assertEqual(0x7F, object_after[0])
            self.assertEqual(object_before[1:], object_after[1:])
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
