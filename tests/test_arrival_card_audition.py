from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arrival_card_audition
import graphics_audit


FONT = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"


class ArrivalCardAuditionTests(unittest.TestCase):
    def test_complete_selector_and_native_layout_contract_is_frozen(self):
        self.assertEqual(32, len(arrival_card_audition.CARDS))
        self.assertEqual(graphics_audit.ARRIVAL_LABELS, arrival_card_audition.CARDS)
        self.assertEqual((), arrival_card_audition.UNRESOLVED_SELECTORS)
        self.assertEqual((160, 144), arrival_card_audition.SCREEN_SIZE)
        self.assertEqual((40, 56), arrival_card_audition.LOCATION_BAND)
        self.assertEqual(57, arrival_card_audition.UNDERLINE_Y)
        self.assertEqual((73, 89), arrival_card_audition.FLOOR_BAND)
        self.assertEqual(144, arrival_card_audition.MAXIMUM_LABEL_PIXELS)
        self.assertEqual(11, arrival_card_audition.DEFAULT_CAP_HEIGHT)
        self.assertEqual(-1, arrival_card_audition.DEFAULT_AUDITION_F_Y_OFFSET)
        self.assertEqual(104, arrival_card_audition.FLOOR_PROOF_HEIGHT)

    def test_candidate_cards_are_centered_block_bounded_and_use_native_palette(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        widths = []
        for selector, label in enumerate(arrival_card_audition.CARDS[:30]):
            floor = arrival_card_audition.sample_floor(selector)
            card, metrics = arrival_card_audition.render_card(
                face,
                label,
                floor=floor,
                style="native-aa",
            )
            self.assertEqual(arrival_card_audition.SCREEN_SIZE, card.size)
            self.assertTrue(set(card.getdata()) <= set(arrival_card_audition.PALETTE))
            self.assertLessEqual(metrics["label_width"], 144)
            self.assertEqual(0, metrics["underline_width"] % 16)
            self.assertLessEqual(metrics["underline_width"], 144)
            self.assertEqual(
                (160 - metrics["underline_width"]) // 2,
                metrics["underline_left"],
            )
            self.assertEqual(arrival_card_audition.UNDERLINE_Y, metrics["underline_y"])
            self.assertEqual(floor, metrics["floor"])
            widths.append(metrics["label_width"])
        self.assertTrue(widths)

    def test_contact_sheet_contains_all_selectors_and_cli_writes_it(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        sheet, report = arrival_card_audition.render_sheet(
            face,
            columns=4,
            style="native-aa",
        )
        self.assertEqual((704, 1472), sheet.size)
        self.assertEqual(32, report["cards"])
        self.assertEqual(32, report["resolved_cards"])
        self.assertEqual([], report["unresolved_selectors"])
        self.assertEqual([], report["overflowing_selectors"])
        self.assertEqual(-1, report["floor_f_y_offset"])

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "arrival-audition.png"
            result = arrival_card_audition.main(
                [
                    "--font",
                    str(FONT),
                    "--output",
                    str(output),
                    "--scale",
                    "1",
                    "--columns",
                    "4",
                ]
            )
            self.assertEqual(0, result)
            with Image.open(output) as written:
                self.assertEqual(sheet.size, written.size)

    def test_audition_sheet_optically_aligns_the_one_and_f_bright_caps(self):
        """The default sheet must expose a corrected, not visibly dropped, 1F."""
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        sheet, _report = arrival_card_audition.render_sheet(
            face,
            columns=4,
            style="native-aa",
        )

        # Selector 1 is the second card and deliberately exercises 1F.  Inspect
        # the two 16x16 runtime blocks independently so surrounding artwork
        # cannot hide a one-pixel vertical error.
        card_left = arrival_card_audition.CELL_WIDTH + 8
        card_top = arrival_card_audition.HEADER_HEIGHT
        floor_top = card_top + 72
        digit_left = card_left + 64
        f_left = digit_left + arrival_card_audition.BLOCK_PIXELS

        def bright_top(left):
            return min(
                y
                for y in range(floor_top, floor_top + 16)
                for x in range(left, left + 16)
                if sheet.getpixel((x, y)) == arrival_card_audition.BRIGHT_INK
            )

        self.assertEqual(
            bright_top(digit_left),
            bright_top(f_left),
            "the F's bright cap is one pixel lower than the 1",
        )

    def test_overflowing_candidate_fails_instead_of_clipping(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        with self.assertRaisesRegex(
            arrival_card_audition.ArrivalCardAuditionError,
            "exceeds the 144-pixel arrival-card budget",
        ):
            arrival_card_audition.render_card(
                face,
                "This label is deliberately far too long for one arrival card",
                floor="99F",
            )


if __name__ == "__main__":
    unittest.main()
