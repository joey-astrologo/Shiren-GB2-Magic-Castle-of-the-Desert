from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import shop_price_font_audition


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class ShopPriceFontAuditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()

    def test_complete_native_shop_digit_source_is_frozen(self):
        source = shop_price_font_audition.read_source(self.rom)
        self.assertEqual(160, len(source))
        self.assertEqual(
            "4df296fd16d1142cf821259614eadb07df7be4747a69fdab58db3182b725fb46",
            sha256(source).hexdigest(),
        )
        self.assertEqual("3:$5642-$56E1", shop_price_font_audition.SOURCE_LOCATION)
        self.assertEqual("0123456789", shop_price_font_audition.DIGITS)
        self.assertEqual(5, shop_price_font_audition.GLYPH_WIDTH)
        self.assertEqual(8, shop_price_font_audition.GLYPH_HEIGHT)

    def test_literal_rasters_preserve_white_gray_and_black_source_indexes(self):
        expected = {
            "0": (
                "33333", "33333", "32123", "31313",
                "31313", "31313", "32123", "33333",
            ),
            "3": (
                "33333", "33333", "31123", "33313",
                "33123", "33313", "31123", "33333",
            ),
            "6": (
                "33333", "33333", "32123", "31333",
                "31123", "31313", "32123", "33333",
            ),
            "9": (
                "33333", "33333", "32123", "31313",
                "32113", "33313", "32123", "33333",
            ),
        }
        for digit, raster in expected.items():
            with self.subTest(digit=digit):
                self.assertEqual(
                    raster,
                    shop_price_font_audition.glyph_raster(self.rom, digit),
                )

        self.assertEqual(3, shop_price_font_audition.BACKGROUND_COLOR)
        self.assertEqual(1, shop_price_font_audition.INK_COLOR)
        self.assertEqual(2, shop_price_font_audition.SHADE_COLOR)
        self.assertEqual((0, 0, 0), shop_price_font_audition.PREVIEW_BACKGROUND)
        self.assertEqual((240, 240, 240), shop_price_font_audition.PREVIEW_INK)
        self.assertEqual((168, 168, 168), shop_price_font_audition.PREVIEW_SHADE)

    def test_every_digit_is_distinct_and_uses_the_five_pixel_shop_advance(self):
        rasters = {
            digit: shop_price_font_audition.glyph_raster(self.rom, digit)
            for digit in shop_price_font_audition.DIGITS
        }
        self.assertEqual(10, len(set(rasters.values())))
        for digit, rows in rasters.items():
            with self.subTest(digit=digit):
                self.assertEqual(8, len(rows))
                self.assertTrue(all(len(row) == 5 for row in rows))
                self.assertIn("1", "".join(rows))

        proof = shop_price_font_audition.render_price(self.rom, "0123456789")
        self.assertEqual((50, 8), proof.size)
        self.assertEqual(
            {
                shop_price_font_audition.PREVIEW_BACKGROUND,
                shop_price_font_audition.PREVIEW_INK,
                shop_price_font_audition.PREVIEW_SHADE,
            },
            set(proof.getdata()),
        )

    def test_screenshot_price_examples_and_maximum_width_are_in_the_sheet(self):
        self.assertEqual(
            ("50", "100", "200", "650", "800", "1200", "1500", "99999"),
            shop_price_font_audition.PRICE_PROOFS,
        )
        self.assertEqual((25, 8), shop_price_font_audition.render_price(self.rom, "99999").size)
        with self.assertRaisesRegex(
            shop_price_font_audition.ShopPriceFontAuditionError,
            "digits only",
        ):
            shop_price_font_audition.render_price(self.rom, "50G")

    def test_contact_sheet_and_cli_are_read_only(self):
        sheet, report = shop_price_font_audition.render_sheet(self.rom)
        self.assertEqual((480, 360), sheet.size)
        self.assertEqual(10, report["digit_count"])
        self.assertEqual(list(shop_price_font_audition.PRICE_PROOFS), report["proofs"])
        self.assertEqual(
            shop_price_font_audition.SOURCE_SHA256,
            report["source_sha256"],
        )
        self.assertFalse(report["rom_modified"])

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "shop-price-font.png"
            result = shop_price_font_audition.main(
                [ROM_NAME, "--output", str(output), "--scale", "2"]
            )
            self.assertEqual(0, result)
            with Image.open(output) as written:
                self.assertEqual((960, 720), written.size)

    def test_modified_source_fails_closed(self):
        damaged = bytearray(self.rom)
        damaged[shop_price_font_audition.SOURCE_OFFSET + 0x52] ^= 1
        with self.assertRaisesRegex(
            shop_price_font_audition.ShopPriceFontAuditionError,
            "source SHA-256 mismatch",
        ):
            shop_price_font_audition.read_source(damaged)


if __name__ == "__main__":
    unittest.main()
