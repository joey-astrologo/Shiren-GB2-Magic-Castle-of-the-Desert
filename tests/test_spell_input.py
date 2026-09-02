from hashlib import sha1
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cartridge
import english
import extract
import name6
import spell_input


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("original ROM not present")
    return path, path.read_bytes()


class SpellInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()

    def test_character_domain_is_exactly_enterable_four_byte_english(self):
        raw = spell_input.character_bytes()
        self.assertEqual(spell_input.CHARACTER_CELLS, len(raw))
        self.assertEqual(
            english.encode(spell_input.CHARACTERS),
            raw[:len(spell_input.CHARACTERS)],
        )
        self.assertEqual(
            bytes((english.ENGLISH_CODES[" "],))
            * (spell_input.CHARACTER_CELLS - len(spell_input.CHARACTERS)),
            raw[len(spell_input.CHARACTERS):],
        )
        self.assertEqual(4, spell_input.MAXIMUM_CHARACTERS)

    def test_keyboard_map_contains_every_character_and_both_controls(self):
        self.assertEqual(
            (
                ((0, "ABCDE"), (7, "UVWXY")),
                ((0, "FGHIJ"), (7, "Z")),
                ((0, "KLMNO"), (7, "01234")),
                ((0, "PQRST"), (7, "56789")),
            ),
            spell_input.DISPLAY_ROWS,
        )
        raw = spell_input.english_keyboard_map(self.rom)
        rows = [raw[offset:offset + 20] for offset in range(0, len(raw), 20)]
        for display_row, blocks in enumerate(spell_input.DISPLAY_ROWS):
            for logical_column, text in blocks:
                at = 1 + logical_column
                self.assertEqual(
                    english.encode(text),
                    rows[6 + display_row * 2][at:at + len(text)],
                )
        self.assertEqual(english.encode("DEL"), rows[4][2:5])
        self.assertEqual(english.encode("OK"), rows[4][15:17])

    def test_control_cursors_sit_below_del_and_ok(self):
        raw = spell_input.english_navigation_table(self.rom)
        records = [
            raw[offset:offset + spell_input.NAVIGATION_RECORD_SIZE]
            for offset in range(0, len(raw), spell_input.NAVIGATION_RECORD_SIZE)
        ]
        self.assertEqual((9, 57, 9), tuple(records[spell_input.BACKSPACE_NODE][4:]))
        self.assertEqual((113, 57, 10), tuple(records[spell_input.CONFIRM_NODE][4:]))

    def test_navigation_graph_reaches_only_displayed_cells_and_controls(self):
        raw = spell_input.english_navigation_table(self.rom)
        records = [
            raw[offset:offset + spell_input.NAVIGATION_RECORD_SIZE]
            for offset in range(0, len(raw), spell_input.NAVIGATION_RECORD_SIZE)
        ]
        active = set(range(len(spell_input.CHARACTERS))) | {
            spell_input.BACKSPACE_NODE,
            spell_input.CONFIRM_NODE,
        }
        reached = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for target in records[node][:4]:
                self.assertIn(target, active)
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        self.assertEqual(active, reached)
        for node in spell_input.UNREACHABLE_NODES:
            self.assertEqual(bytes((node,)) * 4, records[node][:4])

    def test_install_changes_only_owned_regions_and_checksums(self):
        output = spell_input.install(self.rom)
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.rom, output))
            if before != after
        }
        owned = {
            offset
            for start, end in spell_input.owned_ranges()
            for offset in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed <= owned | checksums)
        self.assertEqual(
            cartridge.stored_checksums(output),
            cartridge.verify_checksums(output),
        )

        screen_at = extract.file_offset(
            spell_input.SCREEN_BANK, spell_input.SCREEN_ADDRESS
        )
        self.assertEqual(
            spell_input.SCREEN_PATCH,
            output[screen_at:screen_at + len(spell_input.SCREEN_PATCH)],
        )
        character_at = extract.file_offset(
            spell_input.CHARACTER_BANK, spell_input.CHARACTER_TABLE_ADDRESS
        )
        self.assertEqual(
            spell_input.character_bytes(),
            output[character_at:character_at + spell_input.CHARACTER_CELLS],
        )
        navigation_at = extract.file_offset(
            spell_input.NAVIGATION_BANK, spell_input.NAVIGATION_ADDRESS
        )
        self.assertEqual(
            spell_input.english_navigation_table(self.rom),
            output[navigation_at:navigation_at + spell_input.NAVIGATION_SIZE],
        )
        runtime_at = extract.file_offset(
            spell_input.RUNTIME_BANK, spell_input.RUNTIME_ADDRESS
        )
        payload = spell_input.runtime_payload(self.rom)
        self.assertEqual(payload, output[runtime_at:runtime_at + len(payload)])

    def test_private_gift_code_atlas_contains_the_literal_A_shadow(self):
        output = spell_input.install(self.rom)
        code = english.ENGLISH_CODES["A"]
        glyph_at = extract.file_offset(
            spell_input.RUNTIME_BANK,
            spell_input.GLYPH_LOW_ADDRESS
            + (code - spell_input.GLYPH_LOW_START) * spell_input.GLYPH_STRIDE,
        )
        self.assertEqual(
            bytes.fromhex("707088B888CCF8FC88FC88CC88CC0044"),
            output[glyph_at:glyph_at + spell_input.GLYPH_STRIDE],
        )

    def test_spell_patch_does_not_mutate_player_name_navigation(self):
        output = spell_input.install(self.rom)
        start = extract.file_offset(name6.NAVIGATION_BANK, name6.NAVIGATION_ADDRESS)
        end = start + name6.NAVIGATION_SIZE
        self.assertEqual(self.rom[start:end], output[start:end])

    def test_install_is_idempotent(self):
        once = spell_input.install(self.rom)
        twice = spell_input.install(once)
        self.assertEqual(once, twice)

    def test_source_guards_reject_damage(self):
        cases = (
            (spell_input.SCREEN_BANK, spell_input.SCREEN_ADDRESS),
            (spell_input.CHARACTER_BANK, spell_input.CHARACTER_TABLE_ADDRESS),
            (spell_input.NAVIGATION_BANK, spell_input.NAVIGATION_ADDRESS),
            (spell_input.RUNTIME_BANK, spell_input.RUNTIME_ADDRESS),
        )
        for bank, address in cases:
            damaged = bytearray(self.rom)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(spell_input.SpellInputError):
                    spell_input.install(damaged)

    def test_checked_in_code_matches_rgbds_source_when_available(self):
        if not shutil.which("rgbasm") or not shutil.which("rgblink"):
            self.skipTest("RGBDS is not installed")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            obj = directory / "spell-input.o"
            linked = directory / "spell-input.gb"
            subprocess.run(
                [
                    "rgbasm", "-Wall", "-Wextra", "-o", str(obj),
                    str(ROOT / "tools" / "spell_input.asm"),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["rgblink", "-p", "0", "-o", str(linked), str(obj)],
                check=True,
                capture_output=True,
            )
            raw = linked.read_bytes()
        start = spell_input.RUNTIME_BANK * 0x4000
        self.assertEqual(
            spell_input.ASSEMBLED_CODE,
            raw[start:start + len(spell_input.ASSEMBLED_CODE)],
        )
        self.assertEqual(
            spell_input.CODE_END - spell_input.RUNTIME_ADDRESS,
            len(spell_input.ASSEMBLED_CODE),
        )


if __name__ == "__main__":
    unittest.main()
