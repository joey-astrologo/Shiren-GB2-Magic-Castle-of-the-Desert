from hashlib import sha1
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import english
import english_font
import extract
import name6
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "ranking-screen-on-death.mss"
STATE_SHA1 = "ac76a1b2f5f5c5207308e39e8438ab4dc37bdd5c"


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
        cls.mesen = Path("/Applications/Mesen.app/Contents/MacOS/Mesen")
        source = ROOT / ROM_NAME
        if not cls.mesen.is_file():
            raise unittest.SkipTest("Mesen is unavailable")
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
            screenshot = temporary / "ranking-note.png"
            rom.write_bytes(self.localized)
            env = os.environ.copy()
            env["GB2_DEATH_RANKINGS_MSS"] = str(STATE)
            env["GB2_RANKING_NOTE_SCREENSHOT"] = str(screenshot)
            result = subprocess.run(
                [
                    str(self.mesen),
                    "--testrunner",
                    "--enablestdout",
                    "--novideo",
                    "--noaudio",
                    str(rom),
                    str(ROOT / "tests" / "mesen_ranking_note_input.lua"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, output[-8000:])
            self.assertIn(
                "ranking-note input mode 2 found at frame 476 "
                "with 13-character maximum",
                output,
            )
            self.assertTrue(screenshot.is_file(), output[-8000:])
            image = Image.open(screenshot).convert("RGB")
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

    def test_message_space_cells_and_right_arrow_work_through_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "ranking-note.gbc"
            rom.write_bytes(self.localized)
            for scenario in ("right", "space"):
                with self.subTest(scenario=scenario):
                    env = os.environ.copy()
                    env["GB2_DEATH_RANKINGS_MSS"] = str(STATE)
                    env["GB2_RANKING_NOTE_SCENARIO"] = scenario
                    result = subprocess.run(
                        [
                            str(self.mesen),
                            "--testrunner",
                            "--enablestdout",
                            "--novideo",
                            "--noaudio",
                            str(rom),
                            str(
                                ROOT
                                / "tests"
                                / "mesen_ranking_note_editing.lua"
                            ),
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=60,
                    )
                    output = result.stdout + result.stderr
                    self.assertEqual(0, result.returncode, output[-8000:])
                    self.assertIn("PASS mode-2", output)


if __name__ == "__main__":
    unittest.main()
