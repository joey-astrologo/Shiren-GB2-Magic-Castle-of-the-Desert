from hashlib import sha1
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import credit_screen_mockup
import ending_credits_audition


ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "ending-one.state"
FONT = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"
STATE_SHA1 = "3ef2a74e1e926d1fd79df0c45d51b683b5793004"


class EndingCreditsAuditionTests(unittest.TestCase):
    def test_complete_main_ending_contract_uses_the_opening_credit_treatment(self):
        self.assertEqual(20, len(ending_credits_audition.CREDITS))
        self.assertEqual(
            (500, 830, 1140, 1460, 1780, 2100, 2400, 2750, 3100, 3440,
             3780, 4120, 4440, 4760, 5070, 5380, 5700, 6020, 6350, 6750),
            ending_credits_audition.STABLE_CARD_FRAMES,
        )
        self.assertEqual(7150, ending_credits_audition.END_MARK_FRAME)
        self.assertEqual("preserve Japanese", ending_credits_audition.END_MARK_POLICY)
        self.assertEqual(FONT, ending_credits_audition.DEFAULT_FONT)
        self.assertEqual(credit_screen_mockup.PALETTE, ending_credits_audition.PALETTE)
        self.assertEqual(
            (credit_screen_mockup.LOW_COVERAGE,
             credit_screen_mockup.MID_COVERAGE,
             credit_screen_mockup.HIGH_COVERAGE),
            ending_credits_audition.COVERAGE_THRESHOLDS,
        )
        self.assertEqual("Executive Producer", ending_credits_audition.CREDITS[0].role)
        self.assertEqual(("Koichi Nakamura",), ending_credits_audition.CREDITS[0].names)
        self.assertEqual("Production & Copyright", ending_credits_audition.CREDITS[-1].role)
        self.assertEqual(("CHUNSOFT",), ending_credits_audition.CREDITS[-1].names)

    def test_every_candidate_card_fits_and_uses_only_the_native_credit_palette(self):
        face = ending_credits_audition.load_font(FONT)
        for index, credit in enumerate(ending_credits_audition.CREDITS):
            with self.subTest(index=index, role=credit.role):
                card, metrics = ending_credits_audition.render_card(face, credit)
                self.assertEqual((160, 144), card.size)
                self.assertTrue(set(card.getdata()) <= set(credit_screen_mockup.PALETTE))
                self.assertEqual([], metrics["overflows"])
                self.assertLessEqual(metrics["ink_bounds"][2], 151)
                self.assertGreaterEqual(metrics["ink_bounds"][0], 8)

    def test_sheet_and_cli_write_review_art_without_mutating_inputs(self):
        face = ending_credits_audition.load_font(FONT)
        sheet, report = ending_credits_audition.render_sheet(face, columns=2)
        self.assertEqual((672, 1704), sheet.size)
        self.assertEqual(20, report["cards"])
        self.assertEqual([], report["overflowing_cards"])
        self.assertEqual("Inter SemiBold", report["font_name"])

        before_state = STATE.read_bytes()
        before_rom = ROM.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "ending-credits.png"
            result = ending_credits_audition.main(
                ["--candidate-only", "--scale", "1", "--output", str(output)]
            )
            self.assertEqual(0, result)
            with Image.open(output) as written:
                self.assertEqual(sheet.size, written.size)
        self.assertEqual(before_state, STATE.read_bytes())
        self.assertEqual(before_rom, ROM.read_bytes())

    def test_live_fixture_captures_all_cards_and_the_preserved_end_mark(self):
        if not ROM.is_file() or not STATE.is_file():
            raise unittest.SkipTest("ending ROM/state fixture is required")
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())
        try:
            PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        native, end_mark = ending_credits_audition.capture_native_roll(
            ROM, STATE, PyBoy
        )
        self.assertEqual(20, len(native))
        for card in native:
            self.assertEqual((160, 144), card.size)
            self.assertEqual(set(credit_screen_mockup.PALETTE), set(card.getdata()))
        self.assertEqual((160, 144), end_mark.size)
        self.assertNotEqual({credit_screen_mockup.BLACK}, set(end_mark.getdata()))


if __name__ == "__main__":
    unittest.main()
