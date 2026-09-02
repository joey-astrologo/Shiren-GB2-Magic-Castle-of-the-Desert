from hashlib import sha1
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import english_font
import extract
import font
import layout
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "ranking-screen-on-death.state"
STATE_SHA1 = "f928661f76c975625beddbc70aad223d4ec3cbd0"
EXPECTED = {
    "194:$4EFC": (
        "A Button: Return to Town<br>"
        "Select: Await Rescue<br>"
        "Start: Leave Ranking Note"
    ),
    "194:$4F2D": "A Button: Return to Town<br>Select: Await Rescue",
    "194:$4F4A": "A Button: Return to Town<br>Start: Leave Ranking Note",
    "194:$4F6C": "A Button: Return to Town",
}


def rendered_ink(rom, text):
    """Rasterize the exact color-3 pixels placed by the game's VWF model."""
    staged = english.encode_source(text)
    measured = layout.renderer_layout(
        rom, staged, mode=0x08, start_x=0, start_y=0
    )
    pixels = set()
    for placement in measured.placements:
        glyph = font.read_glyph(rom, placement.encoded)
        slice_start = placement.slice_index * 8
        for glyph_y, row in enumerate(glyph.pixels):
            for glyph_x, color in enumerate(row[slice_start:slice_start + 8]):
                if color == english_font.INK_COLOR:
                    pixels.add((placement.x + glyph_x, placement.y + glyph_y))
    return pixels, measured.line_widths


class RankingFooterSpacingTests(unittest.TestCase):
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
        cls.font_rom = english_font.install(cls.original)

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_all_death_ranking_footers_match_colon_space_pixel_rasters(self):
        by_id = {
            translation.record_id: translation
            for translation in self.translated.values()
        }
        for record_id, wanted in EXPECTED.items():
            with self.subTest(record=record_id):
                actual_pixels, actual_widths = rendered_ink(
                    self.font_rom, by_id[record_id].text
                )
                wanted_pixels, wanted_widths = rendered_ink(self.font_rom, wanted)
                difference = sorted(actual_pixels ^ wanted_pixels)
                self.assertFalse(
                    bool(difference),
                    "%s footer raster first differs at %s; line widths %s, want %s"
                    % (
                        record_id,
                        difference[0] if difference else None,
                        actual_widths,
                        wanted_widths,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
