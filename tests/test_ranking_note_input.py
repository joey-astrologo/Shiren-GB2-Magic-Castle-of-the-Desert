from hashlib import sha1
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import capture_dialogue
import english
import english_font
import extract
import name6
import pyboy_route
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "ranking-screen-on-death.state"
STATE_SHA1 = "f928661f76c975625beddbc70aad223d4ec3cbd0"


def expected_keyboard_ink(original):
    """Return exact approved ink for the localized mode-2 keyboard cells."""
    approved = english_font.load_approved()
    rows = tuple(zip(*[iter(name6.english_keyboard_map(original))] * 20))
    expected = set()
    # The 20x16 source is copied to BG-map row 2, so source row 2 appears at
    # screen y=32. Compare every interior cell the localized map owns while
    # excluding borders and the cursor sprite between character rows.
    for map_row in range(2, 15):
        for column in range(1, 19):
            character = english.CODE_TO_ENGLISH[rows[map_row][column]]
            glyph_rows = name6.CURSOR_GLYPH_ROWS.get(
                character, approved.rows[character]
            )
            screen_x = column * 8
            screen_y = (map_row + 2) * 8
            for glyph_y, glyph_row in enumerate(glyph_rows):
                for glyph_x, pixel in enumerate(glyph_row):
                    if pixel == "#":
                        expected.add((screen_x + glyph_x, screen_y + glyph_y))
    return expected


class RankingNoteInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("source ROM and death-Rankings state are required")
        cls.original = source.read_bytes()
        if sha1(cls.original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.original)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        widths = runtime_widths.analyze(
            english_font.install(cls.original), cls.result, cls.translated
        )
        cls.localized = build.build_rom(
            cls.original,
            translations.encoded_overrides(cls.translated),
            runtime_contract=widths.contract,
        )[0]
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def _open_editor(self, pyboy):
        footer = bytes.fromhex("0a 24 0b 44 43 43 3e 3d")
        ranking_at = None
        for frame in range(1201):
            if ranking_at is None:
                if pyboy_route.find_work_ram(pyboy, footer) is not None:
                    ranking_at = frame
            elif (
                pyboy.memory[0xC195] == 2
                and pyboy.memory[0xC153] == 13
            ):
                return frame

            if frame == 60:
                pyboy_route.press(pyboy, "a")
            elif ranking_at is None and frame >= 180 and frame % 120 == 0:
                pyboy_route.press(pyboy, "a")
            elif ranking_at is not None and frame >= ranking_at + 30:
                if (frame - ranking_at - 30) % 120 == 0:
                    pyboy_route.press(pyboy, "start")
            pyboy.tick()
        self.fail("ranking-note editor did not open")

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_mode2_owns_a_dedicated_screen_call(self):
        at = extract.file_offset(16, 0x7BD4)
        self.assertEqual(bytes.fromhex("0E02"), self.original[at - 2:at])
        self.assertEqual(
            bytes.fromhex("3EF4214540CDAC09"), self.original[at:at + 8]
        )
        self.assertEqual(
            bytes.fromhex("3EFD213242CDAC09"), self.localized[at:at + 8]
        )

    def test_death_ranking_start_opens_english_note_keyboard_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            rom = temporary / "ranking-note.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            try:
                self._open_editor(pyboy)
                pyboy_route.run_frames(pyboy, 120)
                image = pyboy.screen.image.convert("RGB")
            finally:
                pyboy.stop(save=False)
            self.assertEqual((160, 144), image.size)

            expected = expected_keyboard_ink(self.original)
            actual = {
                (x, y)
                for y in range(32, 136)
                for x in range(8, 152)
                if image.getpixel((x, y)) == (0, 0, 0)
                and (y // 8 - 2) in range(2, 15)
            }
            difference = sorted(actual ^ expected)
            self.assertFalse(
                bool(difference),
                "mode-2 keyboard first differs at %s; %d live ink pixels, want %d"
                % (
                    difference[0] if difference else None,
                    len(actual),
                    len(expected),
                ),
            )

    def test_entry_screen_has_a_complete_outer_bottom_border(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "ranking-note.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            try:
                self._open_editor(pyboy)
                pyboy_route.run_frames(pyboy, 120)
                image = pyboy.screen.image.convert("RGB")
            finally:
                pyboy.stop(save=False)

        # The final 18 interior tiles must join the two surviving corner
        # tiles. These literal raster rows detect the reported missing edge
        # without accepting a replacement whole-frame hash.
        for y, expected in ((141, (168, 168, 168)), (142, (0, 0, 0))):
            actual = tuple(image.getpixel((x, y)) for x in range(8, 152))
            mismatch = next(
                (
                    (x, color)
                    for x, color in zip(range(8, 152), actual)
                    if color != expected
                ),
                None,
            )
            self.assertIsNone(
                mismatch,
                "bottom border row %d first differs at x=%s: %s, expected %s"
                % (
                    y,
                    mismatch[0] if mismatch else None,
                    mismatch[1] if mismatch else None,
                    expected,
                ),
            )

    def test_message_space_cells_and_right_arrow_work_through_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "ranking-note.gbc"
            rom.write_bytes(self.localized)
            for scenario in ("right", "space"):
                with self.subTest(scenario=scenario):
                    pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
                    try:
                        self._open_editor(pyboy)
                        sequence = (
                            ("up", "right", "a")
                            if scenario == "right"
                            else ("up", "right", "down", "right", "a")
                        )
                        pyboy_route.run_frames(pyboy, 60)
                        for button in sequence:
                            pyboy_route.press(pyboy, button)
                            pyboy_route.run_frames(pyboy, 30)
                        self.assertEqual(1, pyboy.memory[0xC152])
                        self.assertEqual(0x24, pyboy.memory[0xC16D])
                        self.assertEqual(2, pyboy.memory[0xC195])
                    finally:
                        pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
