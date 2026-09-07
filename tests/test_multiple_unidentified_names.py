from hashlib import sha1
import io
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import capture_dialogue
import english
import english_font
import extract
import pyboy_route
import runtime_widths
import translations
import unidentified_names


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

    def test_start_shortcut_finishes_with_the_full_canonical_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "start-recall.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            draws = []
            wrapper_hits = []

            def at_start_wrapper(_context=None):
                wrapper_hits.append(pyboy.frame_count)

            def at_input_draw(_context=None):
                if pyboy.memory[0xC196] == 107:
                    draws.append(
                        (
                            pyboy.memory[0xC153],
                            bytes(pyboy.memory[0xC16D:0xC17C]),
                        )
                    )

            pyboy.hook_register(
                unidentified_names.RUNTIME_BANK,
                unidentified_names.START_RECALL_ADDRESS,
                at_start_wrapper,
                None,
            )
            pyboy.hook_register(0x11, 0x46C2, at_input_draw, None)
            editor_at = None
            try:
                for frame in range(701):
                    presses = {
                        60: "a",
                        120: "down",
                        180: "down",
                        240: "down",
                        300: "down",
                        400: "a",
                    }
                    if frame in presses:
                        pyboy_route.press(pyboy, presses[frame])
                    if (
                        editor_at is None
                        and pyboy.memory[0xC195] == 0
                        and pyboy.memory[0xC14E]
                        == unidentified_names.NAVIGATION_TYPE
                    ):
                        editor_at = frame
                    if editor_at is not None and frame == editor_at + 80:
                        pyboy_route.press(pyboy, "start")
                    pyboy.tick()
                    if (
                        wrapper_hits
                        and pyboy.memory[0xC153]
                        == unidentified_names.FILL_IN_MAXIMUM
                        and pyboy.memory[0xC196] == 107
                    ):
                        break

                expected = english.encode("Preservation")
                expected_field = (
                    expected
                    + english.encode(" ")
                    * (unidentified_names.FILL_IN_MAXIMUM - len(expected))
                    + b"\xFF"
                )
                self.assertIsNotNone(editor_at)
                self.assertEqual(1, len(wrapper_hits))
                self.assertEqual(
                    len(expected) - 1,
                    pyboy.memory[unidentified_names.INPUT_POSITION_ADDRESS],
                )
                self.assertEqual(
                    unidentified_names.FILL_IN_MAXIMUM,
                    pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS],
                )
                self.assertEqual(
                    expected_field,
                    bytes(
                        pyboy.memory[
                            unidentified_names.INPUT_BUFFER_ADDRESS:
                            unidentified_names.INPUT_BUFFER_ADDRESS
                            + unidentified_names.FILL_IN_MAXIMUM
                            + 1
                        ]
                    ),
                )
                # The native shortcut first performs its seven-cell draw.
                # Our wrapper must leave the final draw on the shared 14-cell
                # presentation used by the visible FILL IN action.
                self.assertTrue(any(maximum == 7 for maximum, _raw in draws))
                self.assertEqual(
                    (unidentified_names.FILL_IN_MAXIMUM, expected_field),
                    draws[-1],
                )
            finally:
                pyboy.stop(save=False)

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

    def test_long_canonical_name_survives_suspend_and_reload(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "canonical-reload.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            pot_root = 107
            identification = 0x2C82
            custom_names = 0x2D78
            editor_at = None
            fill_at = None
            token_at = None
            saved_ram = None
            try:
                for frame in range(1401):
                    presses = {
                        60: "a",
                        120: "down",
                        180: "down",
                        240: "down",
                        300: "down",
                        400: "a",
                    }
                    if editor_at is not None and fill_at is None:
                        presses.update({
                            editor_at + 60: "up",
                            editor_at + 90: "right",
                            editor_at + 120: "up",
                            editor_at + 160: "a",
                        })
                    elif fill_at is not None and token_at is None:
                        presses.update({
                            fill_at + 50: "a",
                            fill_at + 110: "right",
                            fill_at + 170: "a",
                        })
                    elif token_at is not None:
                        presses.update({
                            token_at + 100: "b",
                            token_at + 180: "down",
                            token_at + 240: "down",
                            token_at + 300: "down",
                            token_at + 360: "down",
                            token_at + 430: "a",
                        })
                    if frame in presses:
                        pyboy_route.press(pyboy, presses[frame])
                    pyboy.tick()

                    if (
                        editor_at is None
                        and pyboy.memory[0xC195] == 0
                        and pyboy.memory[0xC14E]
                        == unidentified_names.NAVIGATION_TYPE
                    ):
                        editor_at = frame
                    if (
                        editor_at is not None
                        and fill_at is None
                        and pyboy.memory[0xC153]
                        == unidentified_names.FILL_IN_MAXIMUM
                        and pyboy.memory[0xC196] == pot_root
                    ):
                        fill_at = frame
                    if token_at is None:
                        slot = pyboy_route.work_read_byte(
                            pyboy, identification + pot_root * 2 + 1
                        )
                        if slot != 0xFF:
                            token_at = frame
                    if token_at is not None and frame >= token_at + 520:
                        pyboy.memory[0x0000] = 0x0A
                        banks = []
                        for bank in range(4):
                            pyboy.memory[0x4000] = bank
                            banks.append(bytes(pyboy.memory[0xA000:0xC000]))
                        saved_ram = b"".join(banks)
                        break

                self.assertIsNotNone(editor_at)
                self.assertIsNotNone(fill_at)
                self.assertIsNotNone(token_at)
                self.assertIsNotNone(saved_ram)
                slot = pyboy_route.work_read_byte(
                    pyboy, identification + pot_root * 2 + 1
                )
                expected = bytes((
                    unidentified_names.CANONICAL_PREFIX,
                    unidentified_names.CANONICAL_MARKER,
                    pot_root,
                )) + b"\xFF" * 5
                self.assertEqual(
                    expected,
                    pyboy_route.work_read(
                        pyboy, custom_names + slot * 8, len(expected)
                    ),
                )
                self.assertIn(expected[:4], saved_ram)
                self.assertNotIn(english.encode("Preserv") + b"\xFF", saved_ram)
            finally:
                pyboy.stop(save=False)

            reloaded = self.PyBoy(
                str(rom),
                window="null",
                sound_emulated=False,
                ram_file=io.BytesIO(saved_ram),
            )
            reloaded.set_emulation_speed(0)
            try:
                for frame in range(1001):
                    if frame in (120, 240, 420, 600, 780):
                        pyboy_route.press(reloaded, "a")
                    if frame in (180, 360):
                        pyboy_route.press(reloaded, "start")
                    reloaded.tick()
                slot = pyboy_route.work_read_byte(
                    reloaded, identification + pot_root * 2 + 1
                )
                self.assertNotEqual(0xFF, slot)
                self.assertEqual(
                    expected,
                    pyboy_route.work_read(
                        reloaded, custom_names + slot * 8, len(expected)
                    ),
                )
                self.assertNotEqual(0, reloaded.register_file.PC)
            finally:
                reloaded.stop(save=False)


if __name__ == "__main__":
    unittest.main()
