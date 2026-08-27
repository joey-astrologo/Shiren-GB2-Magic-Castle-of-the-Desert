import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import font


FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "font_trace.json").read_text())
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class FontAddressTests(unittest.TestCase):
    def test_trace_fixture_locations(self):
        for sample in FIXTURE["samples"]:
            with self.subTest(encoded=sample["encoded"], text=sample["text"]):
                loc = font.glyph_location(bytes.fromhex(sample["encoded"]))
                self.assertEqual(sample["bank"], loc.bank)
                self.assertEqual(sample["address"], loc.address)

    def test_width_pages_are_contiguous(self):
        self.assertEqual(0x24, font.glyph_location(b"\x24").width_index)
        self.assertEqual(0x13E, font.glyph_location(bytes.fromhex("F03E")).width_index)
        self.assertEqual(0x25A, font.glyph_location(bytes.fromhex("F15A")).width_index)
        self.assertEqual(0x322, font.glyph_location(bytes.fromhex("F222")).width_index)

    def test_banked_offsets(self):
        self.assertEqual(0xC442, font.banked_offset(3, 0x4442))
        self.assertEqual(0xC842, font.banked_offset(3, 0x4842))
        self.assertEqual(0x338000, font.banked_offset(206, 0x4000))
        with self.assertRaises(ValueError):
            font.banked_offset(3, 0x2000)

    def test_2bpp_slice_decoder(self):
        # low=10100000, high=01100000 -> color indexes 1,2,3,0,0,0,0,0
        pixels = font.decode_2bpp_slices(bytes((0xA0, 0x60)), height=1)
        self.assertEqual(((1, 2, 3, 0, 0, 0, 0, 0),), pixels)
        with self.assertRaises(ValueError):
            font.decode_2bpp_slices(b"\x00", height=1)

    def test_rejects_non_glyph_sequences(self):
        for raw in (b"", b"\xF3\x10", b"abc"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                font.glyph_location(raw)


class OriginalRomIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        digest = hashlib.sha1(cls.rom).hexdigest()
        if digest != FIXTURE["rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_font_region_hashes(self):
        self.assertEqual(font.REGION_SHA1, font.verify_regions(self.rom))

    def test_trace_fixture_widths(self):
        for sample in FIXTURE["samples"]:
            with self.subTest(encoded=sample["encoded"], text=sample["text"]):
                glyph = font.read_glyph(self.rom, bytes.fromhex(sample["encoded"]))
                self.assertEqual(sample["width"], glyph.width)
                self.assertEqual(16 if sample["width"] >= 10 else 8,
                                 glyph.source_width)

    def test_all_latin_slots_are_drawable(self):
        for code in range(0x0A, 0x24):
            with self.subTest(code=code):
                glyph = font.read_glyph(self.rom, bytes((code,)))
                foreground = sum(pixel >= 2 for row in glyph.pixels for pixel in row)
                self.assertGreater(foreground, 0)
                self.assertGreater(glyph.width, 0)


if __name__ == "__main__":
    unittest.main()
