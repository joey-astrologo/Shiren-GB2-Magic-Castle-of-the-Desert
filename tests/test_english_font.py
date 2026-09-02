from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import english
import english_font
import english_smoke
import font


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "english_font.json").read_text(encoding="utf-8")
)


def _ordered_characters():
    return [
        character
        for character, _code in sorted(
            english.ENGLISH_CODES.items(), key=lambda pair: pair[1]
        )
    ]


def _mask(font_asset, text):
    pixels = set()
    pen = 0
    for character in text:
        for y, row in enumerate(font_asset.rows[character]):
            for x, pixel in enumerate(row):
                if pixel == "#":
                    pixels.add((pen + x, y))
        pen += font_asset.advances[character]
    return pixels, pen


def _mask_hash(pixels):
    packed = ";".join("%d,%d" % point for point in sorted(pixels)).encode("ascii")
    return sha256(packed).hexdigest()


class EnglishCodecTests(unittest.TestCase):
    def test_code_page_ranges_are_frozen(self):
        page = FIXTURE["code_page"]
        self.assertEqual(list(range(page["digits"][0], page["digits"][1] + 1)),
                         [english.ENGLISH_CODES[str(index)] for index in range(10)])
        self.assertEqual(list(range(page["capitals"][0], page["capitals"][1] + 1)),
                         [english.ENGLISH_CODES[chr(ord("A") + index)] for index in range(26)])
        self.assertEqual(page["space"], english.ENGLISH_CODES[" "])
        self.assertEqual(list(range(page["lowercase"][0], page["lowercase"][1] + 1)),
                         [english.ENGLISH_CODES[chr(ord("a") + index)] for index in range(26)])
        punctuation = ".,'-?!():/[]+~%\""
        self.assertEqual(list(range(page["punctuation"][0], page["punctuation"][1] + 1)),
                         [english.ENGLISH_CODES[ch] for ch in punctuation])

        pairs = sorted(english.ENGLISH_CODES.items(), key=lambda pair: pair[1])
        packed = "\n".join("%04X:%02X" % (ord(ch), code) for ch, code in pairs)
        self.assertEqual(page["mapping_sha256"], sha256(packed.encode("ascii")).hexdigest())
        self.assertEqual(FIXTURE["glyph_count"], len(pairs))
        self.assertEqual(len(pairs), len(english.CODE_TO_ENGLISH))

    def test_renderer_and_source_controls_round_trip(self):
        renderer = "Hello!<br>Wait.<delay:03><page><box>"
        self.assertEqual(renderer, english.decode(english.encode(renderer)))
        source = "Hi, <name>!<br>Floor <number:34:12>.<page><box>"
        self.assertEqual(source, english.decode_source(english.encode_source(source)))

    def test_ascii_double_quote_has_a_dedicated_english_slot(self):
        self.assertEqual(0x59, english.ENGLISH_CODES['"'])
        quoted = 'Select "Adventure".<page><box>'
        self.assertEqual(quoted, english.decode_source(english.encode_source(quoted)))

    def test_f8_template_selectors_keep_the_native_byte_domain(self):
        # Ordinary English lowercase uses the localized code page, while the
        # same letters after F8 are native runtime-template selectors.
        self.assertEqual(b"\x36", english.encode_source("g"))
        self.assertEqual(
            bytes.fromhex("F810"),
            english.encode_source("<cF8>g"),
        )
        self.assertEqual(
            bytes.fromhex("F80A0FF19A"),
            english.encode_source("<cF8>af<quoteClose>"),
        )
        for source in ("<cF8>g", "<cF8>af<quoteClose>", "<cF8>9 Gitan"):
            with self.subTest(source=source):
                self.assertEqual(
                    source,
                    english.decode_source(english.encode_source(source)),
                )

    def test_smoke_encoding_is_frozen(self):
        smoke = FIXTURE["smoke"]
        self.assertEqual(smoke["source"], english_smoke.SOURCE)
        self.assertEqual(smoke["record"], "%d:$%04X" % (
            english_smoke.RECORD_BANK, english_smoke.RECORD_ADDRESS
        ))
        encoded = english.encode_source(smoke["source"])
        self.assertEqual(smoke["encoded"], encoded.hex().upper())
        self.assertEqual(smoke["source"], english.decode_source(encoded))

    def test_japanese_character_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "cannot encode English character"):
            english.encode_source("あ")


class EnglishFontAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved = english_font.load_approved()

    def test_approved_asset_and_license_hashes(self):
        assets = FIXTURE["assets"]
        self.assertEqual(
            assets["spec_sha256"],
            sha256(self.approved.spec_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            assets["glyph_source_sha256"],
            sha256(self.approved.source_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            assets["license_sha256"],
            sha256((ROOT / "licenses" / "Thin-Pixel-7.txt").read_bytes()).hexdigest(),
        )
        self.assertEqual(FIXTURE["font"], self.approved.name)

    def test_every_glyph_and_advance_is_frozen(self):
        characters = _ordered_characters()
        self.assertEqual(
            FIXTURE["bake"]["advances_sha256"],
            sha256(bytes(self.approved.advances[ch] for ch in characters)).hexdigest(),
        )
        self.assertEqual(
            FIXTURE["bake"]["glyphs_2bpp_sha256"],
            sha256(b"".join(self.approved.glyphs[ch] for ch in characters)).hexdigest(),
        )
        for anchor in FIXTURE["anchors"]:
            character = anchor["character"]
            with self.subTest(character=character):
                self.assertEqual(anchor["code"], english.ENGLISH_CODES[character])
                self.assertEqual(anchor["advance"], self.approved.advances[character])
                self.assertEqual(anchor["glyph"], self.approved.glyphs[character].hex().upper())

    def test_approved_shadow_contract_is_frozen(self):
        bake = FIXTURE["bake"]
        self.assertEqual(bake["background_color"], english_font.BACKGROUND_COLOR)
        self.assertEqual(bake["shadow_color"], english_font.SHADOW_COLOR)
        self.assertEqual(bake["ink_color"], english_font.INK_COLOR)
        self.assertEqual(tuple(bake["shadow_offset"]), english_font.SHADOW_OFFSET)
        self.assertEqual((1, 1), english_font.SHADOW_OFFSET)
        self.assertEqual((-1, 0), english_font.BOTTOM_ORPHAN_SHIFT)
        self.assertEqual(
            [",", "g", "j", "y"],
            bake["bottom_orphan_adjusted_glyphs"],
        )

    def test_2bpp_conversion_uses_native_background_shadow_and_ink_colors(self):
        for character in _ordered_characters():
            with self.subTest(character=character):
                decoded = font.decode_2bpp_slices(
                    self.approved.glyphs[character], height=font.SINGLE_HEIGHT
                )
                expected = english_font.shadow_pixels(
                    self.approved.rows[character]
                )
                self.assertEqual(expected, decoded)

    def test_smoke_line_geometry_is_frozen(self):
        for line in FIXTURE["smoke"]["lines"]:
            with self.subTest(text=line["text"]):
                pixels, advance = _mask(self.approved, line["text"])
                self.assertEqual(line["advance"], advance)
                self.assertEqual(line["ink_pixels"], len(pixels))
                self.assertEqual(line["mask_sha256"], _mask_hash(pixels))


class OriginalRomEnglishFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.approved = english_font.load_approved()
        cls.patched = english_font.install(cls.rom, cls.approved)

    def test_install_changes_only_owned_slots_and_global_checksum(self):
        width_base = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
        glyph_base = font.banked_offset(font.SINGLE_BANK, font.SINGLE_ADDRESS)
        owned_widths = {width_base + code for code in english.ENGLISH_CODES.values()}
        owned_glyphs = {
            glyph_base + code * font.SINGLE_STRIDE + byte
            for code in english.ENGLISH_CODES.values()
            for byte in range(font.SINGLE_STRIDE)
        }
        allowed = owned_widths | owned_glyphs | {0x14D, 0x14E, 0x14F}
        changed = {
            offset
            for offset, pair in enumerate(zip(self.rom, self.patched))
            if pair[0] != pair[1]
        }
        self.assertTrue(changed <= allowed)
        self.assertEqual(FIXTURE["bake"]["changed_bytes_including_checksum"], len(changed))
        self.assertEqual(len(self.rom), len(self.patched))

        header = 0
        for offset in range(0x134, 0x14D):
            header = (header - self.patched[offset] - 1) & 0xFF
        self.assertEqual(header, self.patched[0x14D])
        global_checksum = sum(self.patched[:0x14E]) + sum(self.patched[0x150:])
        self.assertEqual(global_checksum & 0xFFFF,
                         int.from_bytes(self.patched[0x14E:0x150], "big"))

    def test_installed_regions_and_all_glyphs_match_assets(self):
        regions = font.font_regions(self.patched)
        self.assertEqual(
            FIXTURE["bake"]["installed_width_region_sha1"],
            sha1(regions["widths"]).hexdigest(),
        )
        self.assertEqual(
            FIXTURE["bake"]["installed_single_font_region_sha1"],
            sha1(regions["single"]).hexdigest(),
        )
        for character, code in english.ENGLISH_CODES.items():
            with self.subTest(character=character, code=code):
                glyph = font.read_glyph(self.patched, bytes((code,)))
                self.assertEqual(self.approved.advances[character], glyph.width)
                expected = english_font.shadow_pixels(
                    self.approved.rows[character]
                )
                self.assertEqual(expected, glyph.pixels)

    def test_installed_tiles_contain_the_approved_two_tone_shadow_pixels(self):
        expected_a = (
            (1, 3, 3, 3, 1, 1, 1, 1),
            (3, 1, 2, 2, 3, 1, 1, 1),
            (3, 2, 1, 1, 3, 2, 1, 1),
            (3, 3, 3, 3, 3, 2, 1, 1),
            (3, 2, 2, 2, 3, 2, 1, 1),
            (3, 2, 1, 1, 3, 2, 1, 1),
            (3, 2, 1, 1, 3, 2, 1, 1),
            (1, 2, 1, 1, 1, 2, 1, 1),
        )
        expected_plus = (
            (1, 1, 1, 1, 1, 1, 1, 1),
            (1, 1, 1, 1, 1, 1, 1, 1),
            (1, 1, 3, 1, 1, 1, 1, 1),
            (1, 3, 3, 3, 1, 1, 1, 1),
            (1, 1, 3, 2, 2, 1, 1, 1),
            (1, 1, 1, 2, 1, 1, 1, 1),
            (1, 1, 1, 1, 1, 1, 1, 1),
            (1, 1, 1, 1, 1, 1, 1, 1),
        )
        for character, expected in (("A", expected_a), ("+", expected_plus)):
            with self.subTest(character=character):
                glyph = font.read_glyph(
                    self.patched, bytes((english.ENGLISH_CODES[character],))
                )
                self.assertEqual(expected, glyph.pixels)

        expected_bottom_rows = {
            ",": (3, 2, 1, 1, 1, 1, 1, 1),
            "g": (1, 3, 3, 2, 1, 1, 1, 1),
            "j": (3, 3, 2, 1, 1, 1, 1, 1),
            "y": (1, 3, 3, 2, 1, 1, 1, 1),
        }
        for character, expected in expected_bottom_rows.items():
            with self.subTest(character=character):
                glyph = font.read_glyph(
                    self.patched, bytes((english.ENGLISH_CODES[character],))
                )
                self.assertEqual(expected, glyph.pixels[-1])

    def test_unowned_ui_symbol_block_is_byte_exact(self):
        width_base = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
        glyph_base = font.banked_offset(font.SINGLE_BANK, font.SINGLE_ADDRESS)
        self.assertEqual(
            self.rom[width_base + 0xD0:width_base + 0xF0],
            self.patched[width_base + 0xD0:width_base + 0xF0],
        )
        self.assertEqual(
            self.rom[glyph_base + 0xD0 * 16:glyph_base + 0xF0 * 16],
            self.patched[glyph_base + 0xD0 * 16:glyph_base + 0xF0 * 16],
        )

    def test_rejects_a_rom_whose_original_font_regions_do_not_match(self):
        damaged = bytearray(self.rom)
        damaged[font.banked_offset(font.SINGLE_BANK, font.SINGLE_ADDRESS)] ^= 1
        with self.assertRaisesRegex(english_font.FontError, "font region hash mismatch"):
            english_font.install(damaged, self.approved)


class NativeRendererEnglishSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.approved = english_font.load_approved()

    def test_lowercase_english_renders_pixel_exact_through_native_vwf(self):
        smoke = FIXTURE["smoke"]
        patched, payload = english_smoke.build(self.rom)
        # The opening dialogue palette maps native font color 1 to black,
        # color 2 to gray, and color 3 to white.  Keep these literal so this
        # remains an independent live-renderer proof rather than a screenshot
        # hash regenerated from whatever the current ROM happens to draw.
        live_palette = {
            english_font.BACKGROUND_COLOR: (0, 0, 0),
            english_font.SHADOW_COLOR: (64, 64, 64),
            english_font.INK_COLOR: (248, 248, 248),
        }

        with tempfile.TemporaryDirectory() as temporary:
            rom_path = Path(temporary) / "english-font-smoke.gbc"
            rom_path.write_bytes(patched)
            pyboy = self.PyBoy(str(rom_path), window="null")
            pyboy.set_emulation_speed(0)
            try:
                capture_dialogue.run_to_dialogue(pyboy)
                self.assertEqual(payload, bytes(pyboy.memory[0xC800:0xC800 + len(payload)]))
                image = pyboy.screen.image.convert("RGB")
                for line in smoke["lines"]:
                    expected, advance = _mask(self.approved, line["text"])
                    actual = set()
                    for y in range(8):
                        for x in range(advance):
                            if sum(image.getpixel((line["x"] + x, line["y"] + y))) > 600:
                                actual.add((x, y))
                    with self.subTest(text=line["text"]):
                        self.assertEqual(expected, actual)

                    expected_colors = [
                        [english_font.BACKGROUND_COLOR] * advance
                        for _ in range(font.SINGLE_HEIGHT)
                    ]
                    pen = 0
                    for character in line["text"]:
                        glyph = english_font.shadow_pixels(
                            self.approved.rows[character]
                        )
                        for y, row in enumerate(glyph):
                            for x, color in enumerate(row):
                                # Native VWF cells use color 1 transparently;
                                # later glyphs may overlap an earlier shadow.
                                if (
                                    color != english_font.BACKGROUND_COLOR
                                    and pen + x < advance
                                ):
                                    expected_colors[y][pen + x] = color
                        pen += self.approved.advances[character]
                    for y, row in enumerate(expected_colors):
                        for x, color in enumerate(row):
                            with self.subTest(text=line["text"], x=x, y=y):
                                self.assertEqual(
                                    live_palette[color],
                                    image.getpixel((line["x"] + x, line["y"] + y)),
                                )
                self.assertEqual(smoke["lines"][-1]["advance"], pyboy.memory[0xC4D6])
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
