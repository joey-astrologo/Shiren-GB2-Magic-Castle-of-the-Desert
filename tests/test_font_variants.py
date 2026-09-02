from hashlib import sha1
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translated_build
import cartridge
import english
import english_font
import extract
import font
import ips
import menu_graphics
import name6
import spell_input


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class FontVariantAssetTests(unittest.TestCase):
    def test_classic_font_is_the_literal_source_ink_without_gray_pixels(self):
        classic = english_font.load_approved(style="classic")
        shadowed = english_font.load_approved(style="shadowed")

        self.assertEqual(classic.rows, shadowed.rows)
        self.assertEqual(classic.advances, shadowed.advances)
        self.assertEqual(
            bytes.fromhex("FF70FF88FF88FFF8FF88FF88FF88FF00"),
            classic.glyphs["A"],
        )
        self.assertEqual(
            bytes.fromhex("FF70CFB8BBCCFBFC8BFCBBCCBBCCBB44"),
            shadowed.glyphs["A"],
        )
        for character, glyph in classic.glyphs.items():
            raster = font.decode_2bpp_slices(glyph, height=8)
            expected = tuple(
                tuple(3 if pixel == "#" else 1 for pixel in row)
                for row in classic.rows[character]
            )
            with self.subTest(character=character):
                self.assertEqual(expected, raster)

    def test_both_output_mode_writes_two_unambiguous_rom_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "shiren-gb2-english.gbc"
            paths = translated_build.write_font_variant_outputs(
                base,
                {"classic": b"classic-rom", "shadowed": b"shadowed-rom"},
            )
            self.assertEqual(
                {
                    "classic": base.with_name(
                        "shiren-gb2-english-classic-font.gbc"
                    ),
                    "shadowed": base.with_name(
                        "shiren-gb2-english-shadowed-font.gbc"
                    ),
                },
                paths,
            )
            self.assertEqual(b"classic-rom", paths["classic"].read_bytes())
            self.assertEqual(b"shadowed-rom", paths["shadowed"].read_bytes())
            self.assertFalse(base.exists())

    def test_both_output_mode_validates_both_roms_before_writing_either(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "shiren-gb2-english.gbc"
            with self.assertRaisesRegex(TypeError, "shadowed font output"):
                translated_build.write_font_variant_outputs(
                    base,
                    {"classic": b"classic-rom", "shadowed": "not bytes"},
                )
            self.assertTrue(
                all(not path.exists() for path in
                    translated_build.font_variant_output_paths(base).values())
            )

    def test_both_output_mode_writes_round_trip_release_patches(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = bytes(32)
            classic = bytearray(source)
            classic[3:5] = b"CL"
            shadowed = bytearray(source)
            shadowed[12:14] = b"SH"
            outputs = {
                "classic": bytes(classic),
                "shadowed": bytes(shadowed),
            }
            base = Path(temporary) / "shiren-gb2-english.gbc"

            paths = translated_build.write_font_variant_patches(
                base, source, outputs
            )

            self.assertEqual(
                {
                    "classic": base.with_name(
                        "shiren-gb2-english-classic-font.ips"
                    ),
                    "shadowed": base.with_name(
                        "shiren-gb2-english-shadowed-font.ips"
                    ),
                },
                paths,
            )
            for style, path in paths.items():
                with self.subTest(style=style):
                    self.assertEqual(
                        outputs[style],
                        ips.apply_patch(source, path.read_bytes()),
                    )


class ProductionFontVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("original ROM is required")
        cls.original = path.read_bytes()
        if sha1(cls.original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        override = english.encode_source(
            "Hello, Shiren!<br>Native VWF works.<page><box>"
        )
        cls.overrides = {(195, 0x562F): override}
        cls.classic, cls.allocation, _validation = translated_build.build_rom(
            cls.original, cls.overrides, font_style="classic"
        )
        cls.shadowed, shadowed_allocation, _validation = (
            translated_build.build_rom(
                cls.original, cls.overrides, font_style="shadowed"
            )
        )
        if cls.allocation.summary != shadowed_allocation.summary:
            raise AssertionError("font style changed script allocation")

    def test_runtime_and_both_keyboard_atlases_follow_the_selected_style(self):
        code = english.ENGLISH_CODES["A"]
        runtime_at = font.banked_offset(
            font.SINGLE_BANK,
            font.SINGLE_ADDRESS + code * font.SINGLE_STRIDE,
        )
        name_at = extract.file_offset(
            name6.RUNTIME_BANK,
            name6.GLYPH_LOW_ADDRESS
            + (code - name6.GLYPH_LOW_START) * name6.GLYPH_STRIDE,
        )
        spell_at = extract.file_offset(
            spell_input.RUNTIME_BANK,
            spell_input.GLYPH_LOW_ADDRESS
            + (code - spell_input.GLYPH_LOW_START) * spell_input.GLYPH_STRIDE,
        )

        self.assertEqual(
            bytes.fromhex("FF70FF88FF88FFF8FF88FF88FF88FF00"),
            self.classic[runtime_at:runtime_at + 16],
        )
        self.assertEqual(
            bytes.fromhex("FF70CFB8BBCCFBFC8BFCBBCCBBCCBB44"),
            self.shadowed[runtime_at:runtime_at + 16],
        )
        for at in (name_at, spell_at):
            self.assertEqual(
                bytes.fromhex("707088888888F8F88888888888880000"),
                self.classic[at:at + 16],
            )
            self.assertEqual(
                bytes.fromhex("707088B888CCF8FC88FC88CC88CC0044"),
                self.shadowed[at:at + 16],
            )

        atlas_ranges = (
            (
                name6.RUNTIME_BANK,
                name6.GLYPH_LOW_ADDRESS,
                name6.GLYPH_LOW_END - name6.GLYPH_LOW_START,
            ),
            (
                name6.RUNTIME_BANK,
                name6.GLYPH_HIGH_ADDRESS,
                name6.GLYPH_HIGH_END - name6.GLYPH_HIGH_START,
            ),
            (
                spell_input.RUNTIME_BANK,
                spell_input.GLYPH_LOW_ADDRESS,
                spell_input.GLYPH_LOW_END - spell_input.GLYPH_LOW_START,
            ),
            (
                spell_input.RUNTIME_BANK,
                spell_input.GLYPH_HIGH_ADDRESS,
                spell_input.GLYPH_HIGH_END - spell_input.GLYPH_HIGH_START,
            ),
        )
        for bank, address, glyphs in atlas_ranges:
            at = extract.file_offset(bank, address)
            raw = self.classic[at:at + glyphs * 16]
            with self.subTest(bank=bank, address=address):
                self.assertTrue(
                    all(raw[index] == raw[index + 1]
                        for index in range(0, len(raw), 2))
                )

        classic_font = english_font.load_approved(style="classic")
        classic_menu, _measurements = menu_graphics.localized_template(
            self.original, approved=classic_font
        )
        pixels = menu_graphics.decode_canvas(classic_menu)
        for label in menu_graphics.LABELS:
            colors = {
                pixels[y][x]
                for y in range(label.clear_top, label.clear_bottom)
                for x in range(label.clear_left, label.clear_right)
            }
            with self.subTest(status_label=label.name):
                self.assertTrue(colors <= {0, 3})

    def test_classic_equipment_plus_uses_the_black_only_english_glyph(self):
        # Bank 120:$4843 is the positive equipment-modifier producer:
        # ``ld a, sign`` followed by ``ldi [hl], a``.  Follow the byte it
        # actually emits and compare that glyph's decoded pixels, so this
        # catches a formatter that still selects the native Japanese plus
        # even when the approved English font asset itself is correct.
        producer = font.banked_offset(120, 0x4843)
        self.assertEqual(0x3E, self.classic[producer])
        emitted_code = self.classic[producer + 1]
        emitted = font.read_glyph(self.classic, bytes((emitted_code,)))
        approved = english_font.load_approved(style="classic")
        expected = font.decode_2bpp_slices(
            approved.glyphs["+"], height=font.SINGLE_HEIGHT
        )

        self.assertEqual(expected, emitted.pixels)
        self.assertNotIn(2, (pixel for row in emitted.pixels for pixel in row))

    def test_variants_differ_only_in_visual_font_owners_and_checksums(self):
        changed = {
            offset
            for offset, (classic, shadowed) in enumerate(
                zip(self.classic, self.shadowed)
            )
            if classic != shadowed
        }
        runtime_font = {
            font.banked_offset(
                font.SINGLE_BANK,
                font.SINGLE_ADDRESS + code * font.SINGLE_STRIDE,
            ) + byte
            for code in english.ENGLISH_CODES.values()
            for byte in range(font.SINGLE_STRIDE)
        }
        status_overlay = {
            offset
            for start, end in menu_graphics.owned_ranges()
            for offset in range(start, end)
        }
        shared_keyboard = {
            extract.file_offset(name6.RUNTIME_BANK, address) + byte
            for address, size in (
                (
                    name6.GLYPH_LOW_ADDRESS,
                    (name6.GLYPH_LOW_END - name6.GLYPH_LOW_START) * 16,
                ),
                (
                    name6.GLYPH_HIGH_ADDRESS,
                    (name6.GLYPH_HIGH_END - name6.GLYPH_HIGH_START) * 16,
                ),
            )
            for byte in range(size)
        }
        moai_keyboard = {
            extract.file_offset(spell_input.RUNTIME_BANK, address) + byte
            for address, size in (
                (
                    spell_input.GLYPH_LOW_ADDRESS,
                    (spell_input.GLYPH_LOW_END - spell_input.GLYPH_LOW_START) * 16,
                ),
                (
                    spell_input.GLYPH_HIGH_ADDRESS,
                    (spell_input.GLYPH_HIGH_END - spell_input.GLYPH_HIGH_START) * 16,
                ),
            )
            for byte in range(size)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed)
        self.assertTrue(
            changed
            <= runtime_font
            | status_overlay
            | shared_keyboard
            | moai_keyboard
            | checksums
        )


if __name__ == "__main__":
    unittest.main()
