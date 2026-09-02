from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english_font
import font
import font_shadow_audition


class FontShadowAuditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved = english_font.load_approved()

    def test_proposal_uses_the_approved_font_and_native_palette_roles(self):
        self.assertEqual("Thin Pixel-7 GB Compact", self.approved.name)
        self.assertEqual((1, 1), font_shadow_audition.SHADOW_OFFSET)
        self.assertEqual((-1, 0), font_shadow_audition.BOTTOM_ORPHAN_SHIFT)
        self.assertEqual(1, font_shadow_audition.BACKGROUND_COLOR)
        self.assertEqual(2, font_shadow_audition.SHADOW_COLOR)
        self.assertEqual(3, font_shadow_audition.INK_COLOR)
        self.assertEqual((172, 172, 172), font_shadow_audition.PREVIEW_SHADOW)
        self.assertIn("+", font_shadow_audition.EDGE_CASES)
        self.assertEqual(78, len(font_shadow_audition.ORDERED_CHARACTERS))
        self.assertEqual(
            set(self.approved.rows), set(font_shadow_audition.ORDERED_CHARACTERS)
        )

    def test_shadow_is_offset_then_the_original_black_raster_is_drawn_on_top(self):
        self.assertEqual(
            (
                ".###....",
                "#.gg#...",
                "#g..#g..",
                "#####g..",
                "#ggg#g..",
                "#g..#g..",
                "#g..#g..",
                ".g...g..",
            ),
            font_shadow_audition.shadow_raster(self.approved.rows["A"]),
        )

        current_ink = {
            (x, y)
            for y, row in enumerate(self.approved.rows["A"])
            for x, pixel in enumerate(row)
            if pixel == "#"
        }
        proposed = font_shadow_audition.shadow_pixels(self.approved.rows["A"])
        self.assertEqual(
            current_ink,
            {
                (x, y)
                for y, row in enumerate(proposed)
                for x, color in enumerate(row)
                if color == font_shadow_audition.INK_COLOR
            },
        )
        self.assertTrue(any(
            color == font_shadow_audition.SHADOW_COLOR
            for row in proposed
            for color in row
        ))

    def test_every_cutoff_glyph_gets_the_same_connected_bottom_cleanup(self):
        expected_bottom_rows = {
            ",": "#g......",
            "Q": "..gg#...",
            "g": ".##g....",
            "j": "##g.....",
            "p": "#g......",
            "q": "...#g...",
            "y": ".##g....",
        }
        for character, expected in expected_bottom_rows.items():
            with self.subTest(character=character):
                self.assertEqual(
                    expected,
                    font_shadow_audition.shadow_raster(
                        self.approved.rows[character]
                    )[-1],
                )

        report = font_shadow_audition.analyze(self.approved)
        self.assertEqual(
            [",", "g", "j", "y"], report["bottom_orphan_adjusted_glyphs"]
        )
        self.assertEqual(4, report["bottom_orphan_pixels_moved_left"])

    def test_plus_shadow_uses_native_color_two_and_round_trips_as_2bpp(self):
        proposed = font_shadow_audition.shadow_pixels(self.approved.rows["+"])
        self.assertTrue(any(
            color == font_shadow_audition.SHADOW_COLOR
            for row in proposed
            for color in row
        ))
        encoded = font_shadow_audition.encode_shadow_2bpp(
            self.approved.rows["+"]
        )
        self.assertEqual(16, len(encoded))
        self.assertEqual(
            proposed,
            font.decode_2bpp_slices(encoded, height=font.SINGLE_HEIGHT),
        )

    def test_production_encoder_matches_every_reviewed_audition_glyph(self):
        for character in font_shadow_audition.ORDERED_CHARACTERS:
            with self.subTest(character=character):
                rows = self.approved.rows[character]
                self.assertEqual(
                    font_shadow_audition.shadow_pixels(rows),
                    english_font.shadow_pixels(rows),
                )
                self.assertEqual(
                    font_shadow_audition.encode_shadow_2bpp(rows),
                    self.approved.glyphs[character],
                )

    def test_text_comparison_preserves_black_pixels_and_adds_only_gray(self):
        text = "Shadow proof: Agjpqy, 99%!"
        current, advance = font_shadow_audition.render_text(
            self.approved, text, shadow=False
        )
        proposed, proposed_advance = font_shadow_audition.render_text(
            self.approved, text, shadow=True
        )
        self.assertEqual(advance, proposed_advance)
        self.assertEqual(8, current.height)
        self.assertEqual(8, proposed.height)
        self.assertEqual(advance, current.width)
        self.assertEqual(advance + 1, proposed.width)
        self.assertEqual(
            {font_shadow_audition.PREVIEW_BACKGROUND, font_shadow_audition.PREVIEW_INK},
            set(current.getdata()),
        )
        self.assertEqual(
            {
                font_shadow_audition.PREVIEW_BACKGROUND,
                font_shadow_audition.PREVIEW_SHADOW,
                font_shadow_audition.PREVIEW_INK,
            },
            set(proposed.getdata()),
        )

        current_black = {
            (x, y)
            for y in range(current.height)
            for x in range(current.width)
            if current.getpixel((x, y)) == font_shadow_audition.PREVIEW_INK
        }
        proposed_black = {
            (x, y)
            for y in range(proposed.height)
            for x in range(proposed.width)
            if proposed.getpixel((x, y)) == font_shadow_audition.PREVIEW_INK
        }
        self.assertEqual(current_black, proposed_black)

    def test_report_exposes_cell_clipping_and_metric_overhangs(self):
        report = font_shadow_audition.analyze(self.approved)
        self.assertEqual([1, 1], report["shadow_offset"])
        self.assertEqual(78, report["glyph_count"])
        self.assertEqual(
            [",", "Q", "g", "j", "p", "q", "y"],
            report["bottom_clipped_glyphs"],
        )
        self.assertEqual(["%"], report["advance_overhang_glyphs"])
        self.assertEqual(10, report["bottom_clipped_shadow_pixels"])
        self.assertEqual(3, report["advance_overhang_shadow_pixels"])
        self.assertFalse(report["rom_modified"])

    def test_sheet_and_cli_show_current_and_proposed_full_inventory(self):
        sheet, report = font_shadow_audition.render_sheet(self.approved)
        self.assertEqual((720, 560), sheet.size)
        self.assertEqual(
            [
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "abcdefghijklmnopqrstuvwxyz",
                "0123456789",
                ".,'-?!():/[]+~%",
            ],
            report["inventory_rows"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "font-shadow-audition.png"
            result = font_shadow_audition.main(
                ["--output", str(output), "--scale", "1"]
            )
            self.assertEqual(0, result)
            with Image.open(output) as written:
                self.assertEqual((720, 560), written.size)


if __name__ == "__main__":
    unittest.main()
