from hashlib import md5, sha1, sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import allocate
import arrival_cards
import build as translated_build
import capture_dialogue
import cartridge
import dialogue_pacing
import english
import english_font
import english_smoke
import extract
import far_text
import font
import hud_font
import insert
import item_formatting
import item_status
import layout
import menu_graphics
import name6
import blank_scroll
import credit_screen
import rescue_presentation
import shop_sale_count
import spell_input
import stairs_menu
import service_menus
import translations
import unidentified_names
import wait_screen


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "translation_build.json").read_text(
        encoding="utf-8"
    )
)


def _load_original():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("original ROM not present")
    original = path.read_bytes()
    if sha1(original).hexdigest() != FIXTURE["source_rom_sha1"]:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, original


def _build_fixture(original):
    extracted = extract.extract(original)
    loaded = translations.load_tsv(
        ROOT / FIXTURE["translation_fixture"], extracted["records"]
    )
    overrides = translations.encoded_overrides(loaded)
    output, allocation, validation = translated_build.build_rom(original, overrides)
    return extracted, loaded, overrides, output, allocation, validation


class TranslationBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.original = _load_original()
        (
            cls.extracted,
            cls.translations,
            cls.overrides,
            cls.output,
            cls.allocation,
            cls.validation,
        ) = _build_fixture(cls.original)

    def test_override_is_resized_repacked_and_resolves_from_actual_rom(self):
        fixture = FIXTURE["override"]
        key = next(iter(self.overrides))
        record = next(
            record
            for record in self.extracted["records"]
            if (record.bank, record.address) == key
        )
        placement = self.allocation.record_placements[key]
        self.assertEqual(fixture["id"], record.id)
        self.assertEqual(fixture["text"], self.translations[key].text)
        self.assertEqual(fixture["encoded"], self.overrides[key].hex().upper())
        self.assertEqual(fixture["original_bytes"], len(record.raw))
        self.assertEqual(fixture["encoded_bytes"], placement.raw_size)
        self.assertEqual(fixture["size_delta"], len(self.overrides[key]) - len(record.raw))
        self.assertEqual(
            fixture["output"],
            extract.location(placement.output_bank, placement.output_address),
        )
        self.assertTrue(placement.overridden)
        for reference in record.references:
            self.assertEqual(
                self.overrides[key],
                insert.read_source_record(self.output, reference.group, reference.index),
            )

    def test_allocation_validation_output_and_manifest_are_frozen(self):
        self.assertEqual(FIXTURE["allocation_summary"], self.allocation.summary)
        self.assertEqual(FIXTURE["validation"], self.validation)

        output = FIXTURE["output"]
        self.assertEqual(output["size"], len(self.output))
        self.assertEqual(output["sha1"], sha1(self.output).hexdigest())
        self.assertEqual(output["sha256"], sha256(self.output).hexdigest())
        self.assertEqual(output["md5"], md5(self.output).hexdigest())
        self.assertEqual(
            (int(output["header_checksum"], 16), int(output["global_checksum"], 16)),
            cartridge.verify_checksums(self.output),
        )

        manifest = allocate.manifest_bytes(self.allocation)
        self.assertEqual(FIXTURE["allocation_manifest"]["bytes"], len(manifest))
        self.assertEqual(
            FIXTURE["allocation_manifest"]["sha1"], sha1(manifest).hexdigest()
        )

    def test_mutations_are_confined_to_script_font_directory_and_checksums(self):
        fixture = FIXTURE["output"]
        self.assertTrue(dialogue_pacing.verify(self.output))
        changed = insert.mutation_offsets(self.original, self.output)
        packed = b"".join(offset.to_bytes(4, "little") for offset in changed)
        self.assertEqual(fixture["changed_bytes"], len(changed))
        self.assertEqual(
            fixture["mutation_offsets_sha256"], sha256(packed).hexdigest()
        )

        directory_start = extract.file_offset(
            extract.DIRECTORY_BANK, extract.DIRECTORY_ADDRESS
        )
        directory_offsets = set(
            range(
                directory_start,
                directory_start
                + extract.DIRECTORY_COUNT * extract.DIRECTORY_RECORD_SIZE,
            )
        )
        script_offsets = {
            offset
            for bank in self.allocation.bank_images
            for offset in range(
                bank * allocate.BANK_SIZE, (bank + 1) * allocate.BANK_SIZE
            )
        }
        width_base = font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
        glyph_base = font.banked_offset(font.SINGLE_BANK, font.SINGLE_ADDRESS)
        font_offsets = {
            width_base + code for code in english.ENGLISH_CODES.values()
        } | {
            glyph_base + code * font.SINGLE_STRIDE + byte
            for code in english.ENGLISH_CODES.values()
            for byte in range(font.SINGLE_STRIDE)
        }
        item_status_offsets = {
            offset
            for start, end in item_status.owned_ranges()
            for offset in range(start, end)
        }
        item_formatting_offsets = {
            offset
            for start, end in item_formatting.owned_ranges()
            for offset in range(start, end)
        }
        hud_font_offsets = {
            offset
            for start, end in hud_font.owned_ranges()
            for offset in range(start, end)
        }
        sale_count_start, sale_count_end = shop_sale_count.owned_range()
        sale_count_offsets = set(range(sale_count_start, sale_count_end))
        credit_screen_offsets = {
            offset
            for start, end in credit_screen.owned_ranges()
            for offset in range(start, end)
        }
        wait_screen_offsets = {
            offset
            for start, end in wait_screen.owned_ranges()
            for offset in range(start, end)
        }
        arrival_card_offsets = {
            offset
            for start, end in arrival_cards.owned_ranges()
            for offset in range(start, end)
        }
        checksum_offsets = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        selector_offsets = {
            offset
            for start, end in far_text.owned_ranges()
            for offset in range(start, end)
        }
        menu_offsets = {
            offset
            for start, end in menu_graphics.owned_ranges()
            for offset in range(start, end)
        }
        stairs_offsets = {
            offset
            for start, end in stairs_menu.owned_ranges()
            for offset in range(start, end)
        }
        service_menu_offsets = {
            offset
            for start, end in service_menus.owned_ranges()
            for offset in range(start, end)
        }
        name6_offsets = {
            offset
            for start, end in name6.owned_ranges()
            for offset in range(start, end)
        }
        blank_scroll_offsets = {
            offset
            for start, end in blank_scroll.owned_ranges()
            for offset in range(start, end)
        }
        spell_input_offsets = {
            offset
            for start, end in spell_input.owned_ranges()
            for offset in range(start, end)
        }
        unidentified_name_offsets = {
            offset
            for start, end in unidentified_names.owned_ranges()
            for offset in range(start, end)
        }
        rescue_presentation_offsets = {
            offset
            for start, end in rescue_presentation.owned_ranges()
            for offset in range(start, end)
        }
        pacing_start, pacing_end = dialogue_pacing.owned_range()
        pacing_offsets = set(range(pacing_start, pacing_end))
        allowed = (
            directory_offsets
            | script_offsets
            | font_offsets
            | item_formatting_offsets
            | hud_font_offsets
            | sale_count_offsets
            | item_status_offsets
            | credit_screen_offsets
            | wait_screen_offsets
            | arrival_card_offsets
            | selector_offsets
            | menu_offsets
            | stairs_offsets
            | service_menu_offsets
            | name6_offsets
            | blank_scroll_offsets
            | spell_input_offsets
            | unidentified_name_offsets
            | rescue_presentation_offsets
            | pacing_offsets
            | checksum_offsets
        )
        self.assertTrue(set(changed) <= allowed)

        directory = self.output[
            directory_start:
            directory_start + extract.DIRECTORY_COUNT * extract.DIRECTORY_RECORD_SIZE
        ]
        self.assertEqual(fixture["directory_sha1"], sha1(directory).hexdigest())
        written = b"".join(
            self.output[
                bank * allocate.BANK_SIZE:(bank + 1) * allocate.BANK_SIZE
            ]
            for bank in self.allocation.bank_images
        )
        self.assertEqual(fixture["written_banks_sha1"], sha1(written).hexdigest())

    def test_installed_font_regions_and_table_anchors_are_frozen(self):
        self.assertEqual(
            FIXTURE["font_regions"],
            {
                name: sha1(data).hexdigest()
                for name, data in font.font_regions(self.output).items()
            },
        )
        for anchor in FIXTURE["table_anchors"]:
            table = self.allocation.group_tables[anchor["group"]]
            with self.subTest(group=anchor["group"]):
                self.assertEqual(anchor["output"], extract.location(*table.output_key))
                self.assertEqual(anchor["size"], table.size)
                self.assertEqual(anchor["text_bytes"], table.text_bytes)
                self.assertEqual(anchor["payload_sha1"], table.payload_sha1)

    def test_smoke_wrapper_is_the_same_production_build(self):
        output, payload = english_smoke.build(self.original)
        self.assertEqual(next(iter(self.overrides.values())), payload)
        self.assertEqual(self.output, output)

    def test_relocated_validation_detects_translated_payload_corruption(self):
        key = next(iter(self.overrides))
        placement = self.allocation.record_placements[key]
        damaged = bytearray(self.output)
        at = extract.file_offset(placement.output_bank, placement.output_address)
        damaged[at] ^= 1
        with self.assertRaisesRegex(insert.InsertError, "mismatch"):
            insert.validate_relocated(
                self.original, damaged, self.allocation, self.overrides
            )

    def test_allocator_rejects_bad_override_contracts(self):
        key = next(iter(self.overrides))
        cases = (
            (
                "unknown source record",
                {(999, 0x4000): b"\x0A"},
            ),
            (
                "not bytes",
                {key: "A"},
            ),
            (
                "not valid source text",
                {key: b"\xFF"},
            ),
            (
                "cannot fit in one bank",
                {key: b"\x0A" * allocate.BANK_SIZE},
            ),
        )
        for message, overrides in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(allocate.AllocationError, message):
                    allocate.allocate(self.original, record_overrides=overrides)

    def test_overriding_an_aliased_empty_record_preserves_all_15_pointers(self):
        key = (192, 0x43C4)
        payload = english.encode_source("A")
        allocation = allocate.allocate(self.original, record_overrides={key: payload})
        output, _used = insert.write_relocated(self.original, allocation)
        validation = insert.validate_relocated(
            self.original, output, allocation, {key: payload}
        )
        record = next(
            record
            for record in self.extracted["records"]
            if (record.bank, record.address) == key
        )
        self.assertEqual(b"", record.raw)
        self.assertEqual(15, len(record.references))
        self.assertEqual(15, validation["overridden_references"])

        table = allocation.group_tables[0]
        image = allocation.bank_images[table.output_bank]
        targets = set()
        for reference in record.references:
            pointer_at = table.output_address - 0x4000 + 2 + reference.index * 3
            targets.add(
                (
                    image[pointer_at + 2],
                    image[pointer_at] | (image[pointer_at + 1] << 8),
                )
            )
            self.assertEqual(
                payload,
                insert.read_source_record(output, reference.group, reference.index),
            )
        self.assertEqual(1, len(targets))

    def test_build_rejects_a_rune_description_that_exceeds_its_direct_row(self):
        key = (194, 0x7263)
        payload = english.encode_source("<EC>May make Meat, but can break")
        font_rom = english_font.install(self.original)
        generic = layout.validate_overrides(font_rom, {key: payload})
        self.assertEqual(142, generic["max_renderer_pixels"])
        with self.assertRaisesRegex(
            layout.LayoutError, r"194:\$7263: positioned text"
        ):
            translated_build.build_rom(self.original, {key: payload})

        line_break = english.encode_source("<EC>One<br>Two")
        with self.assertRaisesRegex(
            layout.LayoutError, r"194:\$7263: positioned text contains source control FD"
        ):
            translated_build.build_rom(self.original, {key: line_break})

    def test_build_rejects_main_menu_labels_outside_live_pixel_budgets(self):
        left_key = (192, 0x6AED)
        with self.assertRaisesRegex(
            layout.LayoutError, r"192:\$6AED: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {left_key: english.encode_source("Items Too Long")},
            )

        location_key = (193, 0x6FC7)
        with self.assertRaisesRegex(
            layout.LayoutError, r"193:\$6FC7: right-aligned text"
        ):
            translated_build.build_rom(
                self.original,
                {location_key: english.encode_source("Overlong Location")},
            )

    def test_build_rejects_item_action_labels_outside_fixed_columns(self):
        action_key = (192, 0x69F8)
        with self.assertRaisesRegex(
            layout.LayoutError, r"192:\$69F8: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {action_key: english.encode_source("Action Too Long")},
            )

    def test_build_rejects_status_heading_outside_its_live_row(self):
        heading_key = (192, 0x6A52)
        with self.assertRaisesRegex(
            layout.LayoutError, r"192:\$6A52: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {heading_key: english.encode_source("W" * 23)},
            )

    def test_build_rejects_front_end_labels_outside_live_pixel_budgets(self):
        hub_key = (192, 0x6B8D)
        with self.assertRaisesRegex(
            layout.LayoutError, r"192:\$6B8D: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {hub_key: english.encode_source("Adventure History")},
            )

        adventure_key = (193, 0x70EF)
        with self.assertRaisesRegex(
            layout.LayoutError, r"193:\$70EF: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {adventure_key: english.encode_source("Thank-You Password")},
            )

    def test_build_rejects_service_labels_that_cross_the_indented_edge(self):
        password_key = (192, 0x70BC)
        with self.assertRaisesRegex(
            layout.LayoutError, r"192:\$70BC: positioned text"
        ):
            translated_build.build_rom(
                self.original,
                {password_key: english.encode_source("Password Too Long")},
            )


class TranslationBuildPyBoyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.original = _load_original()
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        (
            _extracted,
            _translations,
            cls.overrides,
            cls.output,
            _allocation,
            _validation,
        ) = _build_fixture(cls.original)

    def test_translated_relocated_rom_boots_and_renders_pixel_exact_vwf(self):
        opening = FIXTURE["opening"]
        payload = next(iter(self.overrides.values()))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "translation-smoke.gbc"
            path.write_bytes(self.output)
            pyboy = self.PyBoy(str(path), window="null")
            pyboy.set_emulation_speed(0)
            try:
                events = capture_dialogue.trace_to_dialogue(pyboy, expected=payload)
                staged = bytes(pyboy.memory[0xC800:0xC800 + len(payload)])
                screen = pyboy.screen.image.convert("RGBA").tobytes()
                final_pen = pyboy.memory[0xC4D6]
            finally:
                pyboy.stop(save=False)

        self.assertEqual(opening["source_trace"], ["%d:$%04X" % event for event in events])
        self.assertEqual(payload, staged)
        self.assertEqual(opening["staged_bytes"], len(staged))
        self.assertEqual(opening["staged_sha1"], sha1(staged).hexdigest())
        self.assertEqual(opening["screen_rgba_sha1"], sha1(screen).hexdigest())
        self.assertEqual(opening["final_pen"], final_pen)


if __name__ == "__main__":
    unittest.main()
