from hashlib import sha1
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import blank_scroll
import english
import extract
import name6
import pyboy_route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "blank-scroll.state"
STATE_SHA1 = "c36ee8c975fc6dc59f965a184461940c50473e45"
START_STATE = ROOT / "SaveStates" / "blank-scroll-press-start-bug.state"
START_STATE_SHA1 = "065586c449a56c59d093e4ec2bb62d8e15c1d6fe"
SCROLLS = json.loads((ROOT / "tests/fixtures/blank_scroll.json").read_text())["accepted"]


class PyBoyBlankScrollFailureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        if not cls.source.is_file() or not STATE.is_file() or not START_STATE.is_file():
            raise unittest.SkipTest("matching ROM and native Blank Scroll state are required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory()
        output = Path(cls.temporary.name) / "blank-scroll.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(cls.source),
                str(ROOT / "script" / "en"),
                str(output), "--font-style", "both",
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
        cls.fonts = [output.with_name("blank-scroll-" + style + "-font.gbc")
                     for style in ("classic", "shadowed")]
        cls.localized = cls.fonts[1]
        raw = name6.english_navigation_table(cls.source.read_bytes())
        cls.navigation = [raw[i:i + name6.NAVIGATION_RECORD_SIZE]
                          for i in range(0, len(raw), name6.NAVIGATION_RECORD_SIZE)]

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
        self.assertEqual(START_STATE_SHA1, sha1(START_STATE.read_bytes()).hexdigest())

    @staticmethod
    def _press(pyboy, button):
        pyboy_route.run_frames(pyboy, 20, actions=((0, button),))

    def _move(self, pyboy, target):
        pending = [(pyboy.memory[0xC14F], ())]
        visited = set()
        while pending:
            node, path = pending.pop(0)
            if node == target:
                for button in path:
                    self._press(pyboy, button)
                self.assertEqual(target, pyboy.memory[0xC14F])
                return
            if node not in visited:
                visited.add(node)
                for button, neighbor in zip(("down", "up", "left", "right"), self.navigation[node][:4]):
                    pending.append((neighbor, path + (button,)))
        self.fail("keyboard target is unreachable")

    def _type(self, pyboy, text):
        for character in text:
            node = (0x4B if character == " " else blank_scroll.HYPHEN_NODE
                    if character == "-" else name6.KEYBOARD_CHARACTERS.index(character))
            self._move(pyboy, node)
            self._press(pyboy, "a")

    def _open_write(self, rom, learned=None):
        pyboy = pyboy_route.start(self.PyBoy, rom, START_STATE)
        self.addCleanup(pyboy.stop, save=False)
        pyboy.tick(30, True)
        if learned is not None:
            history = bytearray(32)
            for index in learned:
                history[index // 8] |= 1 << (index & 7)
            pyboy_route.work_write(pyboy, 0x2E1C, history)
        for _ in range(8):
            self._press(pyboy, "down")
        for button in ("a", "down", "a"):
            self._press(pyboy, button)
        self.assertEqual(1, pyboy.memory[0xC195])
        self.assertEqual(11, pyboy.memory[0xC153])
        return pyboy

    def _recall(self, pyboy, expected):
        scratch = bytes(pyboy.memory[0xC185:0xC195])
        neighbors = bytes(pyboy.memory[0xC197:0xC199])
        self._press(pyboy, "start")
        self.assertEqual(1, pyboy.memory[0xC195], "Start overwrote the Blank Scroll mode")
        self.assertEqual(11, pyboy.memory[0xC153])
        self.assertEqual(scratch, bytes(pyboy.memory[0xC185:0xC195]))
        self.assertEqual(neighbors, bytes(pyboy.memory[0xC197:0xC199]))
        raw = english.encode(expected["name"])
        self.assertEqual(raw + b"\xD5" * (11 - len(raw)) + b"\xFF",
                         bytes(pyboy.memory[0xC16D:0xC179]))
        self.assertEqual(expected["root_index"], pyboy.memory[0xC196])

    def _confirm_conversion(self, pyboy, root):
        inventory = pyboy_route.work_read(pyboy, 0x12C1, 20)
        object_id = inventory[pyboy.memory[0xC156]]
        object_at = 0x2482 + 8 * object_id
        before = pyboy_route.work_read(pyboy, object_at, 8)
        self.assertEqual(0x92, before[0])
        resets = []
        pyboy.hook_register(0, 0x01C1, lambda _: resets.append(True), None)
        self._move(pyboy, 77)  # actual OK node
        self._press(pyboy, "a")
        pyboy.tick(100, True)
        self.assertEqual([], resets)
        self.assertEqual(inventory, pyboy_route.work_read(pyboy, 0x12C1, 20))
        self.assertEqual(bytes((124 + root - 47,)) + before[1:],
                         pyboy_route.work_read(pyboy, object_at, 8))

    def test_user_start_then_ok_converts_mapping_in_both_fonts(self):
        for rom in self.fonts:
            with self.subTest(font=rom.name):
                pyboy = self._open_write(rom)
                self._recall(pyboy, SCROLLS[1])
                self._confirm_conversion(pyboy, 48)
                self.doCleanups()

    def test_start_then_ok_converts_every_learned_scroll_in_both_fonts(self):
        for rom in self.fonts:
            for scroll in SCROLLS:
                with self.subTest(font=rom.name, name=scroll["name"]):
                    pyboy = self._open_write(rom, (scroll["root_index"],))
                    self._recall(pyboy, scroll)
                    self._confirm_conversion(pyboy, scroll["root_index"])
                    self.doCleanups()

    def test_start_cycles_history_and_preserves_long_prefixes(self):
        for rom in self.fonts:
            with self.subTest(font=rom.name, route="cycle"):
                pyboy = self._open_write(rom, [s["root_index"] for s in SCROLLS])
                for scroll in SCROLLS + SCROLLS[:1]:
                    self._recall(pyboy, scroll)
                self.doCleanups()
            for text, prefix in (("Exorcism", "Exorcis"), ("Trap-eraser", "Trap-erase"),
                                 ("Squid Sushi", "Squid Sush"), ("Trap-eraser", "Trap-eraser")):
                scroll = next(s for s in SCROLLS if s["name"] == text)
                with self.subTest(font=rom.name, prefix=prefix):
                    pyboy = self._open_write(rom, [s["root_index"] for s in SCROLLS])
                    self._type(pyboy, prefix)
                    self._recall(pyboy, scroll)
                    self._recall(pyboy, scroll)
                    self._confirm_conversion(pyboy, scroll["root_index"])
                    self.doCleanups()

    def test_editing_after_start_replaces_the_previous_prefix(self):
        for rom in self.fonts:
            with self.subTest(font=rom.name):
                pyboy = self._open_write(rom, [s["root_index"] for s in SCROLLS])
                self._recall(pyboy, SCROLLS[0])
                for _ in range(len(SCROLLS[0]["name"])):
                    self._press(pyboy, "b")
                self.assertEqual(b"\xD5" * 11 + b"\xFF", bytes(pyboy.memory[0xC16D:0xC179]))
                self._type(pyboy, "Mapp")
                self._recall(pyboy, SCROLLS[1])
                self._confirm_conversion(pyboy, 48)
                self.doCleanups()

    def test_start_with_no_candidate_preserves_mode_and_typed_input(self):
        for rom in self.fonts:
            for text, learned in (("", ()), ("Mapping", ()), ("Trap-erasex", (72,))):
                with self.subTest(font=rom.name, text=text):
                    pyboy = self._open_write(rom, learned)
                    self._type(pyboy, text)
                    field = bytes(pyboy.memory[0xC16D:0xC179])
                    self._press(pyboy, "start")
                    self.assertEqual(1, pyboy.memory[0xC195])
                    self.assertEqual(0xFF, pyboy.memory[0xC196])
                    self.assertEqual(field, bytes(pyboy.memory[0xC16D:0xC179]))
                    self.doCleanups()

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
