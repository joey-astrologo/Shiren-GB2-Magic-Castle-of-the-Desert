from hashlib import sha1
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import graphics_audit


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class GraphicsAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.summary = graphics_audit.summary(cls.rom)

    def test_credit_card_is_a_stored_tile_and_tilemap_family(self):
        credit = self.summary["clean_boot"]["credit_card"]
        self.assertEqual("stored_tiles_and_tilemap", credit["storage"])
        self.assertEqual(
            [
                {
                    "selector": 58,
                    "table": "05:$6F35",
                    "source": "2D:$4F12-$5583",
                    "destination": "$8800",
                    "vram_banks": [0],
                    "data_bytes": 1648,
                },
                {
                    "selectors": [57, 58],
                    "table": "3F:$4017",
                    "source": "36:$614A-$626B",
                    "destination": "$8000",
                    "vram_banks": [0],
                    "data_bytes": 288,
                },
            ],
            credit["tile_planes"],
        )
        self.assertEqual(
            {
                "selector": 104,
                "descriptor": "00:$3E0B-$3E0D",
                "source": "3B:$7980-$7E81",
                "destination": "$9820",
                "columns": 20,
                "rows": 32,
                "interleaved_attributes": True,
            },
            credit["tilemap"],
        )
        self.assertEqual(
            {
                "attribute_palette_ids": [0, 1, 2, 3, 4, 5, 6],
                "base_source": "17:$58F6-$592D",
                "palette_0_override": "F0:$409F-$40A6",
                "behavior": "native fade animation",
            },
            credit["palette"],
        )

    def test_title_is_a_stored_multi_bank_tile_and_tilemap_family(self):
        title = self.summary["clean_boot"]["title_screen"]
        self.assertEqual("stored_tiles_and_tilemap", title["storage"])
        self.assertEqual(
            [
                {
                    "selector": 0,
                    "table": "05:$6F35",
                    "source": "1C:$4000-$5421",
                    "destination": "$8800",
                    "vram_banks": [1, 0],
                    "bank_bytes": [1056, 4096],
                    "data_bytes": 5152,
                },
                {
                    "selector": 0,
                    "table": "3F:$4017",
                    "source": "31:$4000-$4B01",
                    "destination": "$8000",
                    "vram_banks": [1, 0],
                    "bank_bytes": [768, 2048],
                    "data_bytes": 2816,
                },
            ],
            title["tile_planes"],
        )
        self.assertEqual(
            {
                "selector": 0,
                "descriptor": "00:$3CD3-$3CD5",
                "source": "38:$4000-$42D1",
                "destination": "$9800",
                "columns": 20,
                "rows": 18,
                "interleaved_attributes": True,
            },
            title["tilemap"],
        )
        self.assertEqual(
            {
                "attribute_palette_ids": [0, 1, 2, 3, 4, 5, 6, 7],
                "source": "17:$416F-$41AE",
            },
            title["palette"],
        )

    def test_arrival_cards_are_composed_from_a_shared_glyph_atlas(self):
        cards = self.summary["arrival_cards"]
        self.assertEqual("runtime_composed_glyph_tiles", cards["storage"])
        self.assertEqual("7F:$4000-$41E0", cards["renderer"])
        self.assertEqual(
            {
                "source": "7F:$41E1-$61E0",
                "glyphs": 128,
                "bytes_per_glyph": 64,
                "tile_dimensions": [2, 2],
                "pixel_dimensions": [16, 16],
            },
            cards["glyph_atlas"],
        )
        self.assertEqual("7F:$61E9-$6228", cards["pointer_table"])
        self.assertEqual("7F:$6229-$62EE", cards["sequences"])
        self.assertEqual(32, cards["selector_slots"])
        self.assertEqual(31, cards["unique_sequences"])
        self.assertEqual([30, 31], cards["aliased_selectors"])
        self.assertEqual(9, cards["maximum_location_glyphs"])
        self.assertEqual(
            {
                "background_palette": 7,
                "background_source": "7F:$61E1-$61E8",
                "glyph_palette": 6,
                "glyph_endpoints": ["00:$3AE9-$3AEA", "7F:$61E7-$61E8"],
                "glyph_middle_colors": "inherited from active route",
            },
            cards["palette"],
        )
        self.assertEqual(
            {
                "dungeon_selector": 2,
                "location_glyphs": [11, 12, 13, 14],
                "floor": 2,
                "loaded_glyphs": [11, 12, 13, 14, 0, 2, 10],
            },
            cards["live_mamel_route"],
        )

    def test_audited_scope_keeps_environmental_signs_and_fin_out_of_scope(self):
        policy = self.summary["policy"]
        self.assertEqual("preserve_japanese", policy["environmental_shop_signs"])
        self.assertEqual("preserve_japanese", policy["ending_fin_mark"])
        self.assertEqual("audit_and_localize", policy["functional_graphical_text"])

    def test_ending_credits_are_not_misreported_as_a_completed_trace(self):
        ending = self.summary["routes_requiring_live_capture"]["ending_credits"]
        self.assertEqual("live_route_required", ending["status"])
        self.assertEqual(
            {
                "scenario_selector": 27,
                "scenario_label": "Town 7 staff telop",
                "scenario_label_source": "group 14 index 27 / C2:$7111",
                "music_selector": 38,
                "music_label": "Staff Roll",
                "music_label_source": "group 25 index 38 / C3:$432C",
            },
            ending["native_evidence"],
        )
        self.assertEqual("unknown_until_live_trace", ending["storage"])
        self.assertEqual(
            ["main ending", "true ending"], ending["routes_to_capture"]
        )

    def test_native_pixel_and_map_sources_are_hash_frozen(self):
        self.assertEqual(
            {
                "credit_main_tiles": "125fabd0ef1c4ddff374709a84db18eaac75331e",
                "credit_secondary_tiles": "0b2ff4d0137c4ea4b930cc99fe34165f0b708aa9",
                "credit_tilemap_attributes": "92356fb0b358fe154a5b78e24185b5113dbedde4",
                "credit_base_palettes": "1e764e7dc526657480be9b561c6cd6b0e57115c0",
                "credit_palette_0_override": "caee102534b925867f925b609ed271ca4d579384",
                "title_8800_tiles": "1aa928ad218524bf756a73887bd6f9c767831ff1",
                "title_8000_tiles": "2f9d79349b2c0edf05115e5be7d908f24fe8218d",
                "title_tilemap_attributes": "01352b6485c7769660030e5fdfacbf60b3d9d8a5",
                "title_palettes": "16232d5246e6f25cbf107f8c34799362a3523a5a",
                "arrival_glyph_atlas": "08377199518119f4290b25e0c62f71b6af76f374",
                "arrival_pointer_table": "d2c976aa5c1ffbe99523f6be58b1ead8f11fa64d",
                "arrival_sequences": "ca7f741c24e9bb9870b824ca270b6d865b376a5f",
            },
            self.summary["native_source_sha1"],
        )


if __name__ == "__main__":
    unittest.main()
