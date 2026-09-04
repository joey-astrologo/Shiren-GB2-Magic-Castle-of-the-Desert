from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import hud_font_audition
import build as translated_build
import cartridge
import hud_font


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"

APPROVED_DIGIT_RASTERS = {
    "0": ("....", "###.", "#.#.", "#.#.", "#.#.", "#.#.", "###.", "...."),
    "1": ("....", ".#..", "##..", ".#..", ".#..", ".#..", "###.", "...."),
    "2": ("....", "##..", "..#.", "..#.", ".#..", "#...", "###.", "...."),
    "3": ("....", "###.", "..#.", ".##.", "..#.", "..#.", "###.", "...."),
    "4": ("....", "#.#.", "#.#.", "#.#.", "###.", "..#.", "..#.", "...."),
    "5": ("....", "###.", "#...", "##..", "..#.", "..#.", "##..", "...."),
    "6": ("....", ".##.", "#...", "###.", "#.#.", "#.#.", "###.", "...."),
    "7": ("....", "###.", "..#.", "..#.", ".#..", ".#..", ".#..", "...."),
    "8": ("....", "###.", "#.#.", "###.", "#.#.", "#.#.", "###.", "...."),
    "9": ("....", "###.", "#.#.", "#.#.", "###.", "..#.", "##..", "...."),
}
APPROVED_SLASH_RASTER = (
    "........",
    "......#.",
    ".....#..",
    "....#...",
    "...#....",
    "..#.....",
    ".#......",
    "........",
)
APPROVED_LABEL_RASTERS = {
    "F": ("....", "###.", "#...", "##..", "#...", "#...", "#...", "...."),
    "L": ("....", "#...", "#...", "#...", "#...", "#...", "###.", "...."),
    "v": ("....", "....", "....", "#..#", "#..#", ".#.#", "..#.", "...."),
    "H": ("....", "#.#.", "#.#.", "###.", "#.#.", "#.#.", "#.#.", "...."),
    "p": ("....", "....", "....", "##..", "#.#.", "##..", "#...", "...."),
}


class HudFontAuditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()

    def test_complete_packed_hud_source_and_character_inventory_are_frozen(self):
        source = hud_font_audition.read_source(self.rom)
        self.assertEqual(0x100, len(source))
        self.assertEqual(
            "3ea78ca67f1364b85de7fe4971886ae3bc76bcd643837504cc22be5e839704a1",
            sha256(source).hexdigest(),
        )
        self.assertEqual("0123456789ABCDEFLvHp", hud_font_audition.ALPHANUMERIC_GLYPHS)
        self.assertEqual(("Lv", "Hp"), hud_font_audition.PRODUCTION_LABELS)
        self.assertEqual(("/", "meter-fill", "meter-cap"), hud_font_audition.SYMBOLS)
        self.assertEqual(16, hud_font_audition.SOURCE_TILE_COUNT)
        self.assertEqual(4, hud_font_audition.SLOT_WIDTH)
        self.assertEqual(8, hud_font_audition.GLYPH_HEIGHT)

    def test_literal_native_rasters_include_the_reported_hud_letters(self):
        expected = {
            "F": (
                "....", "###.", "#...", "###.",
                "#...", "#...", "#...", "....",
            ),
            "L": (
                "....", "#...", "#...", "#...",
                "#...", "#...", "###.", "....",
            ),
            "v": (
                "....", "....", "....", "#.#.",
                "#.#.", "###.", ".#..", "....",
            ),
            "H": (
                "....", "#.#.", "#.#.", "#.#.",
                "###.", "#.#.", "#.#.", "....",
            ),
            "p": (
                "....", "....", "....", "###.",
                "#.#.", "###.", "#...", "....",
            ),
        }
        for character, raster in expected.items():
            with self.subTest(character=character):
                self.assertEqual(raster, hud_font_audition.glyph_raster(self.rom, character))

    def test_all_alphanumerics_are_distinct_nonempty_four_pixel_slots(self):
        rasters = {
            character: hud_font_audition.glyph_raster(self.rom, character)
            for character in hud_font_audition.ALPHANUMERIC_GLYPHS
        }
        self.assertEqual(len(rasters), len(set(rasters.values())))
        for character, rows in rasters.items():
            with self.subTest(character=character):
                self.assertEqual(8, len(rows))
                self.assertTrue(all(len(row) == 4 for row in rows))
                self.assertTrue(any("#" in row for row in rows))

    def test_slash_and_maximum_layout_proof_use_the_native_slot_widths(self):
        slash = hud_font_audition.glyph_raster(self.rom, "/")
        self.assertEqual(8, len(slash))
        self.assertTrue(all(len(row) == 8 for row in slash))
        self.assertEqual(".....##.", slash[2])
        self.assertEqual(".##.....", slash[6])

        proof = hud_font_audition.render_hud_text(
            self.rom, "99F Lv 99 Hp 999/999"
        )
        self.assertEqual((84, 8), proof.size)
        self.assertEqual(
            {hud_font_audition.HUD_BACKGROUND, hud_font_audition.HUD_INK},
            set(proof.getdata()),
        )

    def test_contact_sheet_and_cli_render_every_source_group(self):
        sheet, report = hud_font_audition.render_sheet(self.rom)
        self.assertEqual((384, 256), sheet.size)
        self.assertEqual(20, report["alphanumeric_count"])
        self.assertEqual(list(hud_font_audition.PRODUCTION_LABELS), report["production_labels"])
        self.assertEqual(list(hud_font_audition.SYMBOLS), report["symbols"])
        self.assertEqual(hud_font_audition.HUD_SOURCE_SHA256, report["source_sha256"])

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "hud-font.png"
            result = hud_font_audition.main(
                [ROM_NAME, "--output", str(output), "--scale", "2"]
            )
            self.assertEqual(0, result)
            with Image.open(output) as written:
                self.assertEqual((768, 512), written.size)

    def test_modified_source_fails_closed(self):
        damaged = bytearray(self.rom)
        damaged[hud_font_audition.HUD_SOURCE_OFFSET + 0x80] ^= 1
        with self.assertRaisesRegex(
            hud_font_audition.HudFontAuditionError,
            "HUD font source SHA-256 mismatch",
        ):
            hud_font_audition.read_source(damaged)

    def test_production_build_installs_all_approved_hud_glyphs(self):
        output, _allocation, _validation = translated_build.build_rom(self.rom, {})
        for character, expected in APPROVED_DIGIT_RASTERS.items():
            with self.subTest(character=character):
                self.assertEqual(
                    expected,
                    hud_font_audition.glyph_raster(output, character),
                )
        self.assertEqual(
            APPROVED_SLASH_RASTER,
            hud_font_audition.glyph_raster(output, "/"),
        )
        for character, expected in APPROVED_LABEL_RASTERS.items():
            with self.subTest(character=character):
                self.assertEqual(
                    expected,
                    hud_font_audition.glyph_raster(output, character),
                )
        for character in "ABCDE":
            with self.subTest(preserved_character=character):
                self.assertEqual(
                    hud_font_audition.glyph_raster(self.rom, character),
                    hud_font_audition.glyph_raster(output, character),
                )

        digit_start, digit_end = hud_font.digit_range()
        label_start, label_end = hud_font.label_range()
        slash_start, slash_end = hud_font.slash_range()
        atlas_end = (
            hud_font_audition.HUD_SOURCE_OFFSET
            + hud_font_audition.HUD_SOURCE_SIZE
        )
        self.assertEqual(label_end, slash_start)
        self.assertEqual(self.rom[digit_end:label_start], output[digit_end:label_start])
        self.assertEqual(self.rom[slash_end:atlas_end], output[slash_end:atlas_end])

    def test_hud_installer_is_asset_backed_guarded_and_confined(self):
        spec = hud_font.load_approved()
        label_spec = hud_font.load_approved_labels()
        self.assertEqual(
            hud_font.APPROVED_SOURCE_SHA256,
            spec["source"]["sha256"],
        )
        self.assertEqual(
            APPROVED_DIGIT_RASTERS,
            {character: tuple(rows) for character, rows in spec["glyphs"].items()},
        )
        self.assertEqual(APPROVED_SLASH_RASTER, tuple(spec["slash"]))
        self.assertEqual(
            hud_font.APPROVED_LABEL_SOURCE_SHA256,
            label_spec["source"]["sha256"],
        )
        self.assertEqual(
            APPROVED_LABEL_RASTERS,
            {character: tuple(rows) for character, rows in label_spec["glyphs"].items()},
        )
        packed = hud_font.approved_digit_bytes(spec)
        labels = hud_font.approved_label_bytes(label_spec)
        slash = hud_font.approved_slash_bytes(spec)
        self.assertEqual(5 * 16, len(packed))
        self.assertEqual(3 * 16, len(labels))
        self.assertEqual(16, len(slash))

        output = hud_font.install(self.rom)
        digit_start, digit_end = hud_font.digit_range()
        label_start, label_end = hud_font.label_range()
        slash_start, slash_end = hud_font.slash_range()
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.rom, output))
            if before != after
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed - checksums)
        owned = {
            offset
            for start, end in hud_font.owned_ranges()
            for offset in range(start, end)
        }
        self.assertTrue(changed <= owned | checksums)
        self.assertEqual(packed, output[digit_start:digit_end])
        self.assertEqual(labels, output[label_start:label_end])
        self.assertEqual(slash, output[slash_start:slash_end])
        self.assertEqual(output, hud_font.install(output))
        cartridge.verify_checksums(output)

        damaged = bytearray(self.rom)
        damaged[digit_start] ^= 1
        with self.assertRaisesRegex(hud_font.HudFontError, "unexpected HUD digit"):
            hud_font.install(damaged)

        damaged = bytearray(self.rom)
        damaged[label_start] ^= 1
        with self.assertRaisesRegex(hud_font.HudFontError, "unexpected HUD label"):
            hud_font.install(damaged)

        damaged = bytearray(self.rom)
        damaged[slash_start] ^= 1
        with self.assertRaisesRegex(hud_font.HudFontError, "unexpected HUD slash"):
            hud_font.install(damaged)


if __name__ == "__main__":
    unittest.main()
