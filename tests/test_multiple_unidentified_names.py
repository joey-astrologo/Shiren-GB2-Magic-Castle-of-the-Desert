from hashlib import sha1
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import capture_dialogue
import english_font
import extract
import pyboy_route
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "multiple-unidentified-items.state"
STATE_SHA1 = "66d4f794008e2941f70d8c3ceb2bc7c2fdce4c63"


class MultipleUnidentifiedNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("source ROM and multi-item state are required")
        original = source.read_bytes()
        if sha1(original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        result = extract.extract(original)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        widths = runtime_widths.analyze(
            english_font.install(original), result, translated
        )
        cls.localized = build.build_rom(
            original,
            translations.encoded_overrides(translated),
            runtime_contract=widths.contract,
        )[0]
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_two_canonical_names_receive_distinct_persistent_slots(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "multiple-unidentified.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            pot_root = 107
            scroll_item_root = 50
            scroll_name_root = 67
            identification = 0x2C82
            custom_names = 0x2D78

            def work_read(offset):
                old_bank = pyboy.memory[0xFF70]
                try:
                    if offset < 0x1000:
                        return pyboy.memory[0xC000 + offset]
                    pyboy.memory[0xFF70] = offset // 0x1000
                    return pyboy.memory[0xD000 + offset % 0x1000]
                finally:
                    pyboy.memory[0xFF70] = old_bank

            def custom_slot(root):
                return work_read(identification + root * 2 + 1)

            editor_count = 0
            editor_at = None
            fill_at = None
            pot_token_at = None
            second_menu_at = None
            second_token_at = None
            left_first_editor = False
            escape_seen = False
            try:
                for frame in range(2201):
                    presses = {}
                    if editor_count == 0:
                        presses = {
                            60: "a", 120: "down", 180: "down",
                            240: "down", 300: "down", 400: "a",
                        }
                    elif editor_count == 1 and pot_token_at is None and fill_at is None:
                        presses = {
                            editor_at + 60: "up",
                            editor_at + 90: "right",
                            editor_at + 120: "up",
                            editor_at + 160: "a",
                        }
                    elif editor_count == 1 and pot_token_at is None:
                        presses = {
                            fill_at + 50: "a",
                            fill_at + 110: "right",
                            fill_at + 170: "a",
                        }
                    elif pot_token_at is not None and editor_count == 1:
                        presses = {
                            second_menu_at: "up",
                            second_menu_at + 60: "a",
                            second_menu_at + 120: "down",
                            second_menu_at + 180: "down",
                            second_menu_at + 240: "down",
                            second_menu_at + 340: "a",
                        }
                    elif editor_count == 2 and fill_at is None:
                        presses = {
                            editor_at + 60: "up",
                            editor_at + 90: "right",
                            editor_at + 120: "up",
                            editor_at + 160: "a",
                        }
                    elif editor_count == 2 and second_token_at is None:
                        presses = {
                            fill_at + 50: "a",
                            fill_at + 110: "right",
                            fill_at + 170: "a",
                        }
                    if frame in presses:
                        pyboy_route.press(pyboy, presses[frame])
                    pyboy.tick()

                    mode = pyboy.memory[0xC195]
                    navigation = pyboy.memory[0xC14E]
                    if pot_token_at is not None and navigation != 0xF4:
                        left_first_editor = True
                    if (
                        navigation == 0xF4 and mode == 0 and editor_at is None
                        and (editor_count == 0 or left_first_editor)
                    ):
                        editor_count += 1
                        editor_at = frame
                        fill_at = None
                    if (
                        editor_at is not None and fill_at is None
                        and pyboy.memory[0xC153] == 14
                        and pyboy.memory[0xC196] != 0xFF
                    ):
                        expected = pot_root if editor_count == 1 else scroll_item_root
                        self.assertEqual(expected, pyboy.memory[0xC196])
                        fill_at = frame
                    if (
                        editor_count == 2 and fill_at is not None
                        and pyboy.memory[0xC196] == scroll_name_root
                    ):
                        escape_seen = True
                    if editor_count == 1 and pot_token_at is None and custom_slot(pot_root) != 0xFF:
                        pot_token_at = frame
                        second_menu_at = frame + 150
                        editor_at = None
                        fill_at = None
                    elif (
                        editor_count == 2 and second_token_at is None
                        and custom_slot(scroll_item_root) != 0xFF
                    ):
                        second_token_at = frame
                    elif second_token_at is not None and frame >= second_token_at + 30:
                        break

                self.assertEqual(2, editor_count)
                self.assertTrue(escape_seen)
                pot_slot = custom_slot(pot_root)
                scroll_slot = custom_slot(scroll_item_root)
                self.assertNotEqual(pot_slot, scroll_slot)
                self.assertEqual(pot_root, work_read(custom_names + pot_slot * 8 + 2))
                self.assertEqual(
                    scroll_name_root,
                    work_read(custom_names + scroll_slot * 8 + 2),
                )
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
