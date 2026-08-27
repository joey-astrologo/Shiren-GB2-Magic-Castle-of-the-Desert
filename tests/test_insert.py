from hashlib import md5, sha1, sha256
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import allocate
import capture_dialogue
import cartridge
import extract
import far_text
import font
import insert
import mesen_state


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "identity_insert.json").read_text(
        encoding="utf-8"
    )
)


class OriginalRomIdentityInsertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.original = cls.path.read_bytes()
        if sha1(cls.original).hexdigest() != FIXTURE["source_rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.allocation = allocate.allocate(cls.original)
        cls.output, used = insert.write_identity(cls.original, cls.allocation)
        if used is not cls.allocation:
            raise AssertionError("writer did not retain the supplied allocation")
        cls.validation = insert.validate_identity(
            cls.original, cls.output, cls.allocation
        )

    def test_output_hash_size_and_checksums_are_frozen(self):
        fixture = FIXTURE["output"]
        self.assertEqual(fixture["size"], len(self.output))
        self.assertEqual(fixture["sha1"], sha1(self.output).hexdigest())
        self.assertEqual(fixture["sha256"], sha256(self.output).hexdigest())
        self.assertEqual(fixture["md5"], md5(self.output).hexdigest())
        self.assertEqual(
            (int(fixture["header_checksum"], 16), int(fixture["global_checksum"], 16)),
            cartridge.verify_checksums(self.output),
        )
        self.assertEqual(FIXTURE["validation"], self.validation)

    def test_mutations_are_confined_to_planned_regions(self):
        mutations = FIXTURE["mutations"]
        changed = insert.mutation_offsets(self.original, self.output)
        packed = b"".join(offset.to_bytes(4, "little") for offset in changed)
        self.assertEqual(mutations["changed_bytes"], len(changed))
        self.assertEqual(mutations["offsets_sha256"], sha256(packed).hexdigest())

        directory = FIXTURE["directory"]
        directory_offsets = set(
            range(directory["file_offset"], directory["file_offset"] + directory["size"])
        )
        bank_offsets = set()
        for bank in self.allocation.bank_images:
            bank_offsets.update(
                range(bank * allocate.BANK_SIZE, (bank + 1) * allocate.BANK_SIZE)
            )
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
        allowed = directory_offsets | bank_offsets | selector_offsets | checksum_offsets
        self.assertEqual(
            mutations["directory_changed_bytes"],
            sum(offset in directory_offsets for offset in changed),
        )
        self.assertEqual(
            mutations["allocated_bank_changed_bytes"],
            sum(offset in bank_offsets for offset in changed),
        )
        self.assertEqual(
            mutations["checksum_changed_bytes"],
            sum(offset in checksum_offsets for offset in changed),
        )
        self.assertEqual(
            mutations["selector_changed_bytes"],
            sum(offset in selector_offsets for offset in changed),
        )
        self.assertEqual(
            mutations["outside_allowed_regions"],
            sum(offset not in allowed for offset in changed),
        )

    def test_directory_and_written_bank_hashes_are_frozen(self):
        directory = FIXTURE["directory"]
        start = directory["file_offset"]
        end = start + directory["size"]
        self.assertEqual(extract.DIRECTORY_BANK, directory["bank"])
        self.assertEqual(extract.DIRECTORY_ADDRESS, int(directory["address"], 16))
        self.assertEqual(directory["source_sha1"], sha1(self.original[start:end]).hexdigest())
        self.assertEqual(directory["output_sha1"], sha1(self.output[start:end]).hexdigest())

        written = FIXTURE["written_banks"]
        self.assertEqual(
            tuple(range(written["first"], written["last"] + 1)),
            tuple(self.allocation.bank_images),
        )
        payload = b"".join(
            self.output[bank * allocate.BANK_SIZE:(bank + 1) * allocate.BANK_SIZE]
            for bank in self.allocation.bank_images
        )
        self.assertEqual(written["count"], len(self.allocation.bank_images))
        self.assertEqual(written["bytes"], len(payload))
        self.assertEqual(written["sha1"], sha1(payload).hexdigest())
        for bank, image in self.allocation.bank_images.items():
            with self.subTest(bank=bank):
                offset = bank * allocate.BANK_SIZE
                self.assertEqual(image, self.output[offset:offset + allocate.BANK_SIZE])

    def test_directory_rows_match_every_planned_group(self):
        for group, table in self.allocation.group_tables.items():
            with self.subTest(group=group):
                self.assertEqual(
                    (table.output_bank, table.output_address),
                    insert.read_directory_entry(self.output, group),
                )
        for anchor in FIXTURE["directory_anchors"]:
            at = insert.directory_entry_offset(anchor["group"])
            self.assertEqual(anchor["bytes"], self.output[at:at + 3].hex().upper())
            self.assertEqual(
                anchor["table"],
                "%d:$%04X" % insert.read_directory_entry(self.output, anchor["group"]),
            )

    def test_old_script_and_font_regions_are_unchanged(self):
        preserved = FIXTURE["preserved"]
        start = min(extract.TEXT_BANKS) * allocate.BANK_SIZE
        end = (max(extract.TEXT_BANKS) + 1) * allocate.BANK_SIZE
        self.assertEqual(self.original[start:end], self.output[start:end])
        self.assertEqual(
            preserved["original_script_banks_sha1"], sha1(self.output[start:end]).hexdigest()
        )
        self.assertEqual(
            preserved["font_regions"],
            {name: sha1(data).hexdigest() for name, data in font.font_regions(self.output).items()},
        )
        for bank in range(FIXTURE["written_banks"]["last"] + 1, 240):
            offset = bank * allocate.BANK_SIZE
            with self.subTest(unused_reserved_bank=bank):
                self.assertEqual(
                    self.original[offset:offset + allocate.BANK_SIZE],
                    self.output[offset:offset + allocate.BANK_SIZE],
                )

    def test_actual_output_lookup_rejects_out_of_range_index(self):
        table = self.allocation.group_tables[95]
        self.assertEqual(1, table.entries)
        with self.assertRaisesRegex(insert.InsertError, "group 95 has no entry 1"):
            insert.read_source_record(self.output, 95, 1)

    def test_far_selector_calls_and_routine_are_installed(self):
        self.assertTrue(far_text.verify(self.output))

    def test_post_write_validation_detects_directory_corruption(self):
        damaged = bytearray(self.output)
        damaged[insert.directory_entry_offset(35) + 2] ^= 1
        with self.assertRaisesRegex(insert.InsertError, "group 35 directory"):
            insert.validate_identity(self.original, damaged, self.allocation)

    def test_checksum_verifier_detects_payload_corruption(self):
        damaged = bytearray(self.output)
        damaged[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "cartridge checksum mismatch"):
            cartridge.verify_checksums(damaged)


class IdentityInsertPyBoyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.original = cls.path.read_bytes()
        if sha1(cls.original).hexdigest() != FIXTURE["source_rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.output, cls._allocation = insert.write_identity(cls.original)

    def _run(self, path):
        pyboy = self.PyBoy(str(path), window="null")
        pyboy.set_emulation_speed(0)
        try:
            events = capture_dialogue.trace_to_dialogue(pyboy)
            staged = bytes(
                pyboy.memory[0xC800:0xC800 + len(capture_dialogue.DIALOGUE_PREFIX)]
            )
            screen = pyboy.screen.image.convert("RGBA").tobytes()
            return events, staged, screen
        finally:
            pyboy.stop(save=False)

    def _run_mamel_attack(self, path, ram):
        pyboy = self.PyBoy(
            str(path),
            window="null",
            ram_file=io.BytesIO(ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        rendered = []
        f6_return_banks = []

        def at_full_renderer(_context):
            if pyboy.frame_count < 900:
                return
            staged = bytes(pyboy.memory[0xC800:0xC900])
            try:
                end = staged.index(0xFF) + 1
            except ValueError:
                return
            rendered.append(staged[:end])

        def after_f6_lookup(_context):
            if pyboy.frame_count >= 900:
                f6_return_banks.append(pyboy.memory[0xC4DB])

        pyboy.hook_register(0, 0x35ED, at_full_renderer, None)
        pyboy.hook_register(0, 0x33B9, after_f6_lookup, None)
        try:
            # The battery save extracted from Mamel.mss resumes at the file
            # menu.  This fixed input route selects Continue, reaches the
            # adjacent Mamel and attacks it at frame 960.
            for frame in range(1001):
                if frame in (120, 240, 420, 600, 780, 960):
                    pyboy.button("a", 5)
                if frame in (180, 360):
                    pyboy.button("start", 5)
                pyboy.tick()
            return {
                "rendered": rendered,
                "f6_return_banks": f6_return_banks,
                "screen": pyboy.screen.image.convert("RGBA").tobytes(),
                "pc": pyboy.register_file.PC,
            }
        finally:
            pyboy.stop(save=False)

    def test_identity_rom_clean_boots_with_pixel_exact_opening(self):
        opening = FIXTURE["opening"]
        with tempfile.TemporaryDirectory() as temporary:
            output_path = Path(temporary) / "identity.gbc"
            output_path.write_bytes(self.output)
            original_events, original_staged, original_screen = self._run(self.path)
            output_events, output_staged, output_screen = self._run(output_path)

        self.assertEqual(
            opening["source_trace"], ["%d:$%04X" % event for event in output_events]
        )
        self.assertNotEqual(original_events, output_events)
        self.assertEqual(capture_dialogue.DIALOGUE_PREFIX, output_staged)
        self.assertEqual(original_staged, output_staged)
        self.assertEqual(opening["dialogue_prefix_bytes"], len(output_staged))
        self.assertEqual(opening["dialogue_prefix_sha1"], sha1(output_staged).hexdigest())
        self.assertEqual(original_screen, output_screen)
        self.assertEqual(opening["screen_rgba_sha1"], sha1(output_screen).hexdigest())

    def test_nested_mamel_lookup_preserves_outer_combat_record_bank(self):
        state_path = ROOT / "SaveStates" / "Mamel.mss"
        if not state_path.exists():
            raise unittest.SkipTest("Mamel Mesen state is not present")
        ram = mesen_state.cart_ram(state_path)
        outer = self._allocation.record_placements[(193, 0x4192)].output_bank
        actor = self._allocation.record_placements[(192, 0x4BD7)].output_bank
        self.assertNotEqual(outer, actor)

        with tempfile.TemporaryDirectory() as temporary:
            output_path = Path(temporary) / "identity.gbc"
            output_path.write_bytes(self.output)
            original = self._run_mamel_attack(self.path, ram)
            output = self._run_mamel_attack(output_path, ram)

        self.assertTrue(original["rendered"])
        self.assertEqual(original["rendered"], output["rendered"])
        self.assertEqual(original["screen"], output["screen"])
        self.assertTrue(original["f6_return_banks"])
        self.assertEqual(193, original["f6_return_banks"][0])
        self.assertTrue(output["f6_return_banks"])
        self.assertEqual(outer, output["f6_return_banks"][0])
        self.assertNotEqual(0, output["pc"])


if __name__ == "__main__":
    unittest.main()
