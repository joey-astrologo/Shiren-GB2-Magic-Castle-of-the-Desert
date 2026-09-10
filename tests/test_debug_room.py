"""Native debug-event reproduction; no production renderer changes are installed."""

from hashlib import sha1
import io
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import pyboy_route


ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "debug-room.state"
STATE_SHA1 = "a2edb2034941b16fcc40b2b98a2e8b3a322d3099"
CHEAT = "019F2FC1"

# Paths are zero-based physical choices from the main debug menu. Indices are
# group-7 labels in visible top-to-bottom order, independent of English wording.
MENUS = (
    ("main", (), (197, 228, 144)),
    ("items", (0,), (198, 199, 200, 201, 202)),
    ("equipment", (0, 0), (203, 204, 205, 206)),
    ("bracelets_grass", (0, 1), (207, 208, 209)),
    ("scrolls_staves", (0, 2), (210, 211, 212, 213)),
    ("pots_arrows", (0, 3), (214, 215)),
    ("meat_1", (0, 4), (159, 216, 217, 218, 219)),
    ("meat_2", (0, 4, 0), (159, 220, 221, 222, 223)),
    ("meat_3", (0, 4, 0, 0), (159, 224, 225, 226, 227)),
    ("flags", (1,), (229, 230, 231, 232)),
)


class NativeDebugRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ROM.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and debug-room fixture are required")
        if sha1(ROM.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def setUp(self):
        self.pyboy = pyboy_route.start(self.PyBoy, ROM, STATE)
        self.addCleanup(self.pyboy.stop, save=False)
        self.references = []
        self.events = []
        self.pyboy.hook_register(0, 0x1FA0, self._selector, None)
        self.pyboy.hook_register(4, 0x6F79, self._event, None)

    def _selector(self, _context):
        registers = self.pyboy.register_file
        self.references.append((registers.A, registers.C))

    def _event(self, _context):
        self.events.append(self.pyboy.register_file.A)

    def _press(self, button):
        self.pyboy.button(button, 5)
        self.pyboy.tick(90)

    def _enter(self, path):
        for choice in path:
            for _ in range(choice):
                self._press("down")
            self._press("a")

    def _assert_menu(self, indices):
        # The native constructor draws rows from bottom to top.
        self.assertEqual(
            [(7, index) for index in reversed(indices)],
            self.references[-len(indices):],
        )

    def _open_debug(self):
        self.pyboy.gameshark.add(CHEAT)
        self._press("a")
        self.pyboy.tick(400)
        self.pyboy.gameshark.remove(CHEAT)
        self.assertEqual([0x9F], self.events)
        self.assertEqual(4, self.pyboy.memory[0xC130])
        self._assert_menu(MENUS[0][2])
        state = io.BytesIO()
        self.pyboy.save_state(state)
        return state.getvalue()

    def _inventory(self):
        work = pyboy_route.flat_work_ram(self.pyboy)
        return [
            work[0x2482 + index * 8:0x248A + index * 8]
            for index in work[0x12C1:0x12D5] if index < 128
        ]

    def test_supplied_fixture_is_frozen_before_the_staircase_transition(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())
        self.assertEqual(3, self.pyboy.memory[0xC130])
        self.assertEqual(0x9F, self.pyboy.memory[0xC12F])
        self.assertEqual(20, len(self._inventory()))

    def test_saved_event_byte_alone_does_not_survive_the_transition(self):
        self._press("a")
        self.pyboy.tick(400)
        self.assertEqual([], self.events)
        self.assertEqual(4, self.pyboy.memory[0xC130])
        self.assertEqual(0xFF, self.pyboy.memory[0xC12F])

    def test_cheat_enters_all_ten_menus_and_back_works_after_removing_it(self):
        base = self._open_debug()
        by_path = {path: indices for _name, path, indices in MENUS}
        for name, path, indices in MENUS[1:]:
            with self.subTest(menu=name):
                self.pyboy.load_state(io.BytesIO(base))
                self.references.clear()
                self._enter(path)
                self._assert_menu(indices)
                self.references.clear()
                self._press("b")
                self._assert_menu(by_path[path[:-1]])

    def test_full_inventory_trash_and_weapon_preset_have_distinct_effects(self):
        base = self._open_debug()
        original = self._inventory()
        self._enter((0, 0, 0))
        self.assertEqual(original, self._inventory())

        self.pyboy.load_state(io.BytesIO(base))
        self._enter((2,))
        self.assertEqual([], self._inventory())
        self._assert_menu(MENUS[0][2])

        self._enter((0, 0, 0))
        self.assertEqual(list(range(1, 21)), [record[0] for record in self._inventory()])
        self.assertTrue(all(record[1] == 1 for record in self._inventory()))


if __name__ == "__main__":
    unittest.main()
