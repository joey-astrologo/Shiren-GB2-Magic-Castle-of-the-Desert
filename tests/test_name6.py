from hashlib import sha1
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import english
import english_font
import extract
import pyboy_state
import name6


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
NAME6_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "name6.json").read_text(encoding="utf-8")
)


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("matching original ROM is required")
    rom = path.read_bytes()
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, rom


class Name6InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        cls.output = name6.install(cls.rom)

    def test_contract_freezes_default_limits_storage_and_keyboard(self):
        measured = name6.summary(self.rom)
        self.assertEqual(NAME6_FIXTURE, measured)
        self.assertEqual(6, measured["maximum_visible_characters"])
        self.assertEqual("Shiren", measured["default_name"])
        self.assertEqual([0x66, 0x67], measured["diary"]["suffix_offsets"])
        self.assertEqual([0x68, 0x69], measured["diary"]["marker_offsets"])
        self.assertEqual(32, measured["rankings"]["native_record_bytes"])
        self.assertEqual("$BED0", measured["rankings"]["end_exclusive"])
        self.assertEqual("$BFF8", measured["rankings"]["signature"])
        self.assertEqual(62, measured["keyboard"]["grid_character_nodes"])
        self.assertEqual(63, measured["keyboard"]["insertable_nodes"])
        self.assertEqual(
            list(range(62, 75)) + [76],
            measured["keyboard"]["blank_unreachable_nodes"],
        )
        self.assertTrue(measured["keyboard"]["shared_mode3_source_unchanged"])

    def test_all_embedded_demo_and_secrets_diaries_use_full_english_name(self):
        measured = name6.summary(self.rom)["embedded_replays"]
        self.assertEqual(14, measured["events"])
        self.assertEqual([0, 3], measured["non_secrets_event_range"])
        self.assertEqual([0, 1], measured["title_observed_event_range"])
        self.assertEqual([4, 13], measured["secrets_event_range"])
        self.assertEqual("5:$40E6", measured["title_selector"])
        self.assertEqual("16:$796B", measured["secrets_selector"])

        native, tail = name6.localized_replay_name_parts()
        self.assertEqual(english.encode("Shir") + b"\xFF", native)
        self.assertEqual(english.encode("en") + name6.DIARY_MARKER, tail)
        for record in name6.replay_records(self.rom):
            at = record["offset"]
            with self.subTest(event_id=record["event_id"]):
                self.assertEqual(
                    native,
                    self.output[
                        at + name6.REPLAY_NAME_OFFSET:
                        at
                        + name6.REPLAY_NAME_OFFSET
                        + name6.REPLAY_NAME_FIELD_SIZE
                    ],
                )
                self.assertEqual(
                    tail,
                    self.output[
                        at + name6.DIARY_SUFFIX_OFFSETS[0]:
                        at + name6.DIARY_MARKER_OFFSETS[-1] + 1
                    ],
                )
                owned = set(
                    range(
                        name6.REPLAY_NAME_OFFSET,
                        name6.REPLAY_NAME_OFFSET
                        + name6.REPLAY_NAME_FIELD_SIZE,
                    )
                ) | set(
                    range(
                        name6.DIARY_SUFFIX_OFFSETS[0],
                        name6.DIARY_MARKER_OFFSETS[-1] + 1,
                    )
                )
                self.assertEqual(
                    bytes(
                        value
                        for offset, value in enumerate(
                            self.rom[at:at + name6.DIARY_SIZE]
                        )
                        if offset not in owned
                    ),
                    bytes(
                        value
                        for offset, value in enumerate(
                            self.output[at:at + name6.DIARY_SIZE]
                        )
                        if offset not in owned
                    ),
                )

    def test_character_plan_matches_approved_spaced_mockup(self):
        self.assertEqual(26, len(name6.UPPERCASE_CHARACTERS))
        self.assertEqual(26, len(name6.LOWERCASE_CHARACTERS))
        self.assertEqual("0123456789", name6.UTILITY_CHARACTERS)
        self.assertEqual(".,'-?!():/[]+~%", name6.REMOVED_CHARACTERS)
        self.assertEqual(62, len(name6.character_bytes()))
        self.assertEqual(
            english.encode("Shiren") + b"\xFF", name6.default_name_bytes()
        )

        raw = name6.english_keyboard_map(self.rom)
        rows = [raw[offset:offset + 20] for offset in range(0, len(raw), 20)]
        blank_tile = english.ENGLISH_CODES[" "]
        for block_index, block in enumerate(name6.KEYBOARD_BLOCKS):
            start = 1 + name6.KEYBOARD_BLOCK_COLUMNS[block_index]
            width = name6.KEYBOARD_BLOCK_WIDTHS[block_index]
            for display_row, text in enumerate(block):
                row = 6 + display_row * 2
                self.assertEqual(
                    english.encode(text),
                    rows[row][start:start + width],
                )
        for row in (6, 8, 10, 12, 14):
            self.assertEqual(blank_tile, rows[row][6])
            self.assertEqual(blank_tile, rows[row][12])
        for row in range(3, 15, 2):
            self.assertEqual(bytes((blank_tile,) * 18), rows[row][1:19])
        self.assertEqual(english.encode("SPACE"), rows[2][1:6])
        self.assertEqual(bytes((blank_tile,) * 8), rows[2][7:15])
        self.assertEqual(english.encode("OK"), rows[2][15:17])
        self.assertEqual(
            english.ENGLISH_CODES[name6.LEFT_CURSOR_CHARACTER], rows[4][1]
        )
        self.assertEqual(
            english.ENGLISH_CODES[name6.RIGHT_CURSOR_CHARACTER], rows[4][8]
        )
        self.assertEqual(english.encode("DEL"), rows[4][15:18])

        glyphs = name6.keyboard_glyph_bytes(
            name6.GLYPH_HIGH_START, name6.GLYPH_HIGH_END
        )
        cursor_glyphs = {
            name6.LEFT_CURSOR_CHARACTER: (
                "101030387078F0F87078303810180008"
            ),
            name6.RIGHT_CURSOR_CHARACTER: (
                "8080C0C0E0E0F0F0E0F8C0F080E00040"
            ),
        }
        for character, encoded in cursor_glyphs.items():
            code = english.ENGLISH_CODES[character]
            start = (code - name6.GLYPH_HIGH_START) * name6.GLYPH_STRIDE
            self.assertEqual(
                bytes.fromhex(encoded),
                glyphs[start:start + name6.GLYPH_STRIDE],
            )

        navigation = name6.english_navigation_table(self.rom)
        graph = [
            navigation[offset:offset + name6.NAVIGATION_RECORD_SIZE]
            for offset in range(0, len(navigation), name6.NAVIGATION_RECORD_SIZE)
        ]
        active = set(range(62)) | {75, 77, 78, 79, 80}
        blanks = set(range(62, 75)) | {76}
        for node in active:
            self.assertFalse(set(graph[node][:4]) & blanks)
        reached = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for target in graph[node][:4]:
                if target in active and target not in reached:
                    reached.add(target)
                    pending.append(target)
        self.assertEqual(active, reached)
        for node, (row, column) in enumerate(name6.character_positions()):
            self.assertEqual(
                bytes((9 + column * 8, 73 + row * 16, 8)), graph[node][4:]
            )
        self.assertEqual(bytes((5, 78, 50, 1)), graph[0][:4])
        self.assertEqual(bytes((75, 19, 23, 41)), graph[24][:4])
        self.assertEqual(bytes((26, 79, 4, 46)), graph[25][:4])
        self.assertEqual(bytes((42, 32, 36, 38)), graph[37][:4])
        self.assertEqual(bytes((44, 34, 38, 40)), graph[39][:4])
        self.assertEqual(bytes((51, 80, 25, 47)), graph[46][:4])
        self.assertEqual(bytes((77, 55, 60, 15)), graph[61][:4])
        self.assertEqual(bytes((78, 20, 77, 77)), graph[75][:4])
        self.assertEqual(bytes((80, 61, 75, 75)), graph[77][:4])
        self.assertEqual(bytes((0, 75, 80, 79)), graph[78][:4])
        self.assertEqual(bytes((25, 77, 78, 80)), graph[79][:4])
        self.assertEqual(bytes((46, 77, 79, 78)), graph[80][:4])

        navigation_at = extract.file_offset(
            name6.NAVIGATION_BANK, name6.NAVIGATION_ADDRESS
        )
        self.assertEqual(
            navigation,
            self.output[navigation_at:navigation_at + name6.NAVIGATION_SIZE],
        )

    def test_ranking_note_uses_every_available_blank_node_as_space(self):
        positions = name6.ranking_note_space_positions()
        self.assertEqual(14, len(positions))
        self.assertEqual(14, len(set(positions)))
        rows = tuple(zip(*[iter(name6.english_keyboard_map(self.rom))] * 20))
        blank = english.ENGLISH_CODES[" "]
        graph = name6.ranking_note_navigation_table(self.rom)
        records = tuple(
            graph[offset:offset + name6.NAVIGATION_RECORD_SIZE]
            for offset in range(0, len(graph), name6.NAVIGATION_RECORD_SIZE)
        )
        for node, (row, column) in zip(
            name6.RANKING_NOTE_SPACE_NODES, positions
        ):
            with self.subTest(node=node):
                self.assertEqual(blank, rows[6 + row * 2][1 + column])
                self.assertEqual(
                    bytes((9 + column * 8, 73 + row * 16, 8)),
                    records[node][4:],
                )
        self.assertEqual(name6.RANKING_NOTE_SPACE_NODES[0], records[25][3])
        reached = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for target in records[node][:4]:
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        self.assertEqual(set(range(name6.NAVIGATION_NODES)), reached)
        pointer = extract.file_offset(
            name6.NAVIGATION_BANK,
            name6.RANKING_NOTE_NAVIGATION_POINTER_ADDRESS,
        )
        self.assertEqual(bytes.fromhex("00C8"), self.output[pointer:pointer + 2])
        runtime = extract.file_offset(
            name6.RUNTIME_BANK, name6.RANKING_NOTE_NAVIGATION_ADDRESS
        )
        self.assertEqual(graph, self.output[runtime:runtime + len(graph)])

    def test_keyboard_atlas_contains_approved_literal_two_tone_glyphs(self):
        expected = {
            "A": "707088B888CCF8FC88FC88CC88CC0044",
            "g": "00000000707090B890D8707810386070",
            "0": "606090B090D890D890D890D860680030",
            "[": "101030387078F0F87078303810180008",
            "]": "8080C0C0E0E0F0F0E0F8C0F080E00040",
        }
        for character, encoded in expected.items():
            code = english.ENGLISH_CODES[character]
            if name6.GLYPH_LOW_START <= code < name6.GLYPH_LOW_END:
                address = (
                    name6.GLYPH_LOW_ADDRESS
                    + (code - name6.GLYPH_LOW_START) * name6.GLYPH_STRIDE
                )
            else:
                address = (
                    name6.GLYPH_HIGH_ADDRESS
                    + (code - name6.GLYPH_HIGH_START) * name6.GLYPH_STRIDE
                )
            glyph_at = extract.file_offset(name6.RUNTIME_BANK, address)
            with self.subTest(character=character):
                self.assertEqual(
                    bytes.fromhex(encoded),
                    self.output[glyph_at:glyph_at + name6.GLYPH_STRIDE],
                )

    def test_diary_tail_and_ranking_tail_have_no_native_direct_consumer(self):
        # Immediate direct loads/stores/address loads are absent for all four
        # diary-tail bytes.  The patched getter/setter are their first users.
        direct_address_opcodes = (0x01, 0x08, 0x11, 0x21, 0x31, 0xEA, 0xFA)
        for address in range(name6.DIARY_SUFFIX_ADDRESS, name6.DIARY_MARKER_ADDRESS + 2):
            little = address.to_bytes(2, "little")
            with self.subTest(address=hex(address)):
                self.assertFalse(
                    any(bytes((opcode,)) + little in self.rom for opcode in direct_address_opcodes)
                )

        # Bank 11 is the only banked SRAM owner.  Its last native structure ends
        # at $BCD8; no direct address in the new range exists before patching.
        bank11 = self.rom[11 * 0x4000:12 * 0x4000]
        direct = []
        for offset in range(len(bank11) - 2):
            if bank11[offset] not in direct_address_opcodes:
                continue
            value = bank11[offset + 1] | (bank11[offset + 2] << 8)
            if name6.RANKING_SRAM_HEADER <= value < name6.SRAM_SIGNATURE_ADDRESS:
                direct.append((offset, value))
        self.assertEqual([], direct)
        self.assertEqual(name6.RANKING_NATIVE_END, name6.RANKING_SRAM_HEADER)
        self.assertLess(name6.RANKING_SRAM_END, name6.SRAM_SIGNATURE_ADDRESS)

    def test_mode3_shared_sources_are_byte_exact(self):
        character_at = extract.file_offset(18, 0x5310)
        character_size = 73
        map_at = extract.file_offset(
            name6.KEYBOARD_MAP_BANK, name6.KEYBOARD_MAP_SOURCE_ADDRESS
        )
        self.assertEqual(
            self.rom[character_at:character_at + character_size],
            self.output[character_at:character_at + character_size],
        )
        self.assertEqual(
            self.rom[map_at:map_at + name6.KEYBOARD_MAP_SIZE],
            self.output[map_at:map_at + name6.KEYBOARD_MAP_SIZE],
        )

    def test_installer_changes_only_owned_ranges_and_checksums(self):
        allowed = {
            offset
            for start, end in name6.owned_ranges()
            for offset in range(start, end)
        } | {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.rom, self.output))
            if before != after
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)
        cartridge.verify_checksums(self.output)

    def test_source_code_and_runtime_guards_fail_closed(self):
        cases = [
            (bank, address)
            for _name, bank, address, _original, _target in (
                name6.ROUTINE_PATCHES + name6.CALL_PATCHES
            )
        ] + [
            (name6.NAVIGATION_BANK, name6.NAVIGATION_ADDRESS),
            (name6.RUNTIME_BANK, name6.RUNTIME_ADDRESS),
            (name6.REPLAY_POINTER_BANK, name6.REPLAY_POINTER_ADDRESS),
            name6.REPLAY_TITLE_SELECTOR,
            name6.REPLAY_SECRETS_SELECTOR,
        ] + [
            (record["bank"], record["address"])
            for record in name6.replay_records(self.rom)
        ]
        for bank, address in cases:
            damaged = bytearray(self.rom)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(name6.Name6Error):
                    name6.install(damaged)

    def test_checked_in_code_matches_rgbds_source_when_available(self):
        if not shutil.which("rgbasm") or not shutil.which("rgblink"):
            self.skipTest("RGBDS is not installed")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            obj = directory / "name6.o"
            linked = directory / "name6.gb"
            subprocess.run(
                ["rgbasm", "-Wall", "-Wextra", "-o", str(obj), str(ROOT / "tools" / "name6.asm")],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["rgblink", "-p", "0", "-o", str(linked), str(obj)],
                check=True,
                capture_output=True,
            )
            raw = linked.read_bytes()
        start = name6.RUNTIME_BANK * 0x4000
        self.assertEqual(
            name6.ASSEMBLED_CODE,
            raw[start:start + len(name6.ASSEMBLED_CODE)],
        )


class LiveName6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _path, cls.rom = _original_rom()
        state_path = ROOT / "SaveStates" / "Mamel.state"
        if not state_path.exists():
            raise unittest.SkipTest("Mamel native PyBoy state is required")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.ram = pyboy_state.cart_ram(state_path)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "name6.gbc"
        cls.localized_rom = name6.install(english_font.install(cls.rom))
        cls.localized_path.write_bytes(cls.localized_rom)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _pyboy(self):
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        # Let the boot ROM and the game's hardware init finish before replacing
        # PC with the isolated WRAM trampoline below.
        for _frame in range(120):
            pyboy.tick()
        return pyboy

    @staticmethod
    def _set_bc(pyboy, value):
        pyboy.register_file.B = (value >> 8) & 0xFF
        pyboy.register_file.C = value & 0xFF

    @staticmethod
    def _set_de(pyboy, value):
        pyboy.register_file.D = (value >> 8) & 0xFF
        pyboy.register_file.E = value & 0xFF

    def _invoke(self, pyboy, bank, address, allow_interrupts=False):
        # Run a real far call from fixed WRAM, mark completion, then spin.  This
        # isolates one engine routine without replacing an unrelated game call.
        trampoline = bytes(
            (
                0x3E,
                bank,
                0x21,
                address & 0xFF,
                address >> 8,
                0xCD,
                0xAC,
                0x09,
                0x3E,
                0x42,
                0xEA,
                0xFF,
                0xC7,
                0x18,
                0xFE,
            )
        )
        for offset, value in enumerate(trampoline):
            pyboy.memory[0xC700 + offset] = value
        pyboy.memory[0xC7FF] = 0
        old_ie = pyboy.memory[0xFFFF]
        pyboy.memory[0xFFFF] = (old_ie | 1) if allow_interrupts else 0
        pyboy.memory[0xFF0F] = 0
        # The graphical constructor switches SVBK.  Its call stack must stay in
        # fixed WRAM, just like the game's native $C6xx stack.
        pyboy.register_file.SP = 0xC6F0
        pyboy.register_file.PC = 0xC700
        for _frame in range(120 if allow_interrupts else 2):
            pyboy.tick()
            if pyboy.memory[0xC7FF] == 0x42:
                break
        pyboy.memory[0xFFFF] = old_ie
        self.assertEqual(0x42, pyboy.memory[0xC7FF])

    def test_old_save_fallback_six_character_roundtrip_and_native_save_reload(self):
        pyboy = self._pyboy()
        try:
            # An old diary may contain any values in the formerly unused tail.
            stock = bytes.fromhex("8BA9ADFF")
            for offset, value in enumerate(stock):
                pyboy.memory[name6.DIARY_PREFIX_ADDRESS + offset] = value
            pyboy.memory[name6.DIARY_SUFFIX_ADDRESS] = 0x12
            pyboy.memory[name6.DIARY_SUFFIX_ADDRESS + 1] = 0x34
            pyboy.memory[name6.DIARY_MARKER_ADDRESS] = 0
            pyboy.memory[name6.DIARY_MARKER_ADDRESS + 1] = 0
            self._set_de(pyboy, 0xC620)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.GET_ADDRESS)
            self.assertEqual(stock, bytes(pyboy.memory[0xC620:0xC624]))
            self.assertEqual(0, pyboy.register_file.B)
            self.assertEqual(3, pyboy.register_file.C)
            self.assertEqual(0xC256, pyboy.register_file.HL)
            self.assertEqual(
                0xC256,
                (pyboy.register_file.D << 8) | pyboy.register_file.E,
            )

            pepper = english.encode("Pepper") + b"\xFF"
            for offset, value in enumerate(pepper):
                pyboy.memory[0xC600 + offset] = value
            self._set_de(pyboy, 0xC600)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.SET_ADDRESS)
            self.assertEqual(pepper[:4], bytes(pyboy.memory[0xC252:0xC256]))
            self.assertEqual(0xFF, pyboy.memory[0xC256])
            self.assertEqual(pepper[4:6], bytes(pyboy.memory[0xC2A2:0xC2A4]))
            self.assertEqual(name6.DIARY_MARKER, bytes(pyboy.memory[0xC2A4:0xC2A6]))

            # The unmodified native 0x6A-byte save/load routes include all four
            # extension bytes, so no SRAM format or checksum field moved.
            self._invoke(pyboy, 11, 0x45F1)
            for offset in range(name6.DIARY_SIZE):
                pyboy.memory[0xC23C + offset] = 0
            self._invoke(pyboy, 11, 0x45C8)
            self._set_de(pyboy, 0xC620)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.GET_ADDRESS)
            self.assertEqual(pepper, bytes(pyboy.memory[0xC620:0xC627]))
            self.assertEqual(0, pyboy.register_file.B)
            self.assertEqual(6, pyboy.register_file.C)
            self.assertEqual(0xC257, pyboy.register_file.HL)
            self.assertEqual(
                0xC257,
                (pyboy.register_file.D << 8) | pyboy.register_file.E,
            )

            self._invoke(pyboy, name6.RUNTIME_BANK, name6.DEFAULT_ADDRESS)
            self._set_de(pyboy, 0xC620)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.GET_ADDRESS)
            self.assertEqual(
                english.encode("Shiren") + b"\xFF",
                bytes(pyboy.memory[0xC620:0xC627]),
            )
        finally:
            pyboy.stop(save=False)

    def test_title_family_and_first_last_secrets_snapshots_render_shiren(self):
        pyboy = self._pyboy()
        try:
            records = name6.replay_records(self.rom)
            for event_id in (0, 4, 13):
                record = records[event_id]
                at = record["offset"]
                for offset, value in enumerate(
                    self.localized_rom[at:at + name6.DIARY_SIZE]
                ):
                    pyboy.memory[0xC23C + offset] = value
                self._set_de(pyboy, 0xC620)
                self._invoke(pyboy, name6.RUNTIME_BANK, name6.GET_ADDRESS)
                with self.subTest(event_id=event_id):
                    self.assertEqual(
                        english.encode("Shiren") + b"\xFF",
                        bytes(pyboy.memory[0xC620:0xC627]),
                    )
                    self.assertEqual(6, pyboy.register_file.C)
        finally:
            pyboy.stop(save=False)

    def test_mode4_screen_prefills_shiren_uses_six_cells_and_english_map(self):
        pyboy = self._pyboy()
        try:
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.DEFAULT_ADDRESS)
            pyboy.memory[0xC174] = 0xA7
            self._set_bc(pyboy, 4)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.SCREEN_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(4, pyboy.memory[0xC195])
            self.assertEqual(6, pyboy.memory[0xC153])
            self.assertEqual(
                english.encode("Shiren") + b"\xFF",
                bytes(pyboy.memory[0xC16D:0xC174]),
            )
            self.assertEqual(0xA7, pyboy.memory[0xC174])

            old_vbk = pyboy.memory[0xFF4F]
            pyboy.memory[0xFF4F] = 0
            observed = bytes(
                pyboy.memory[0x9840 + row * 32 + column]
                for row in range(16)
                for column in range(20)
            )
            pyboy.memory[0xFF4F] = old_vbk & 1
            self.assertEqual(name6.english_keyboard_map(self.rom), observed)

            pyboy.memory[0xFF4F] = 0
            self.assertEqual(
                name6.keyboard_glyph_bytes(
                    name6.GLYPH_LOW_START, name6.GLYPH_LOW_END
                ),
                bytes(pyboy.memory[0x9000:0x9250]),
            )
            self.assertEqual(
                name6.keyboard_glyph_bytes(
                    name6.GLYPH_HIGH_START, name6.GLYPH_HIGH_END
                ),
                bytes(
                    pyboy.memory[
                        0x9300:
                        0x9300
                        + (name6.GLYPH_HIGH_END - name6.GLYPH_HIGH_START)
                        * name6.GLYPH_STRIDE
                    ]
                ),
            )
            pyboy.memory[0xFF4F] = old_vbk & 1

            expected_a = (
                "03330000",
                "30223000",
                "32003200",
                "33333200",
                "32223200",
                "32003200",
                "32003200",
                "02000200",
            )
            palette = {
                "0": (248, 248, 248),
                "2": (168, 168, 168),
                "3": (0, 0, 0),
            }
            image = pyboy.screen.image.convert("RGB")
            self.assertEqual(
                tuple(
                    tuple(palette[color] for color in row)
                    for row in expected_a
                ),
                tuple(
                    tuple(image.getpixel((8 + x, 64 + y)) for x in range(8))
                    for y in range(8)
                ),
            )
        finally:
            pyboy.stop(save=False)

    def test_six_inputs_controls_and_skipped_nodes_use_the_clean_layout(self):
        pyboy = self._pyboy()
        try:
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.DEFAULT_ADDRESS)
            self._set_bc(pyboy, 4)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.SCREEN_ADDRESS,
                allow_interrupts=True,
            )
            for offset in range(6):
                pyboy.memory[0xC16D + offset] = 0xD5
            pyboy.memory[0xC173] = 0xFF
            pyboy.memory[0xC152] = 0
            pyboy.memory[0xC153] = 6
            pyboy.memory[0xC14F] = 0
            pyboy.memory[0xC150] = 0

            for node in range(6):
                self._set_bc(pyboy, node)
                self._invoke(
                    pyboy,
                    name6.RUNTIME_BANK,
                    name6.INPUT_ADDRESS,
                    allow_interrupts=True,
                )
            self.assertEqual(english.encode("ABCDEF"), bytes(pyboy.memory[0xC16D:0xC173]))
            self.assertEqual(0xFF, pyboy.memory[0xC173])
            self.assertEqual(5, pyboy.memory[0xC152])
            self.assertEqual(0x4D, pyboy.memory[0xC14F])
            self.assertEqual(0x4D, pyboy.memory[0xC150])

            self._set_bc(pyboy, 0x50)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(
                english.encode("ABCDE") + b"\xD5\xFF",
                bytes(pyboy.memory[0xC16D:0xC174]),
            )

            # The removed CLEAR node is a no-op even if called directly.
            self._set_bc(pyboy, 0x4C)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            before_reset = english.encode("ABCDE") + b"\xD5\xFF"
            self.assertEqual(before_reset, bytes(pyboy.memory[0xC16D:0xC174]))

            for offset in range(6):
                pyboy.memory[0xC16D + offset] = 0xD5
            pyboy.memory[0xC173] = 0xFF
            pyboy.memory[0xC152] = 0
            blank = b"\xD5" * 6 + b"\xFF"
            self.assertEqual(blank, bytes(pyboy.memory[0xC16D:0xC174]))

            # Unreachable blank nodes are harmless even if invoked directly.
            self._set_bc(pyboy, 62)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.INPUT_ADDRESS)
            self.assertEqual(blank, bytes(pyboy.memory[0xC16D:0xC174]))

            # SPACE inserts normally.  The visual cursor-symbol nodes deliberately
            # reverse the two native kana-era action ordinals.
            self._set_bc(pyboy, 0x4B)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(english.encode(" "), bytes(pyboy.memory[0xC16D:0xC16E]))
            self.assertEqual(1, pyboy.memory[0xC152])

            self._set_bc(pyboy, 0x4E)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.INPUT_ADDRESS)
            self.assertEqual(0, pyboy.memory[0xC152])
            self._set_bc(pyboy, 0x4F)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.INPUT_ADDRESS)
            self.assertEqual(1, pyboy.memory[0xC152])

            self._set_bc(pyboy, 0x50)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(blank, bytes(pyboy.memory[0xC16D:0xC174]))
            self.assertEqual(0, pyboy.memory[0xC152])
        finally:
            pyboy.stop(save=False)

    def test_mode2_blank_cells_and_right_at_end_insert_spaces(self):
        pyboy = self._pyboy()
        try:
            pyboy.memory[0xC195] = 2
            pyboy.memory[0xC153] = 13

            def reset():
                for offset in range(13):
                    pyboy.memory[0xC16D + offset] = 0xD5
                pyboy.memory[0xC17A] = 0xFF
                pyboy.memory[0xC152] = 0

            for node in name6.RANKING_NOTE_SPACE_NODES:
                reset()
                self._set_bc(pyboy, node)
                self._invoke(
                    pyboy,
                    name6.RUNTIME_BANK,
                    name6.INPUT_ADDRESS,
                    allow_interrupts=True,
                )
                with self.subTest(node=node):
                    self.assertEqual(english.encode(" "), bytes(
                        pyboy.memory[0xC16D:0xC16E]
                    ))
                    self.assertEqual(1, pyboy.memory[0xC152])

            reset()
            self._set_bc(pyboy, 0x4F)
            self._invoke(
                pyboy,
                name6.RUNTIME_BANK,
                name6.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(
                english.encode(" "), bytes(pyboy.memory[0xC16D:0xC16E])
            )
            self.assertEqual(1, pyboy.memory[0xC152])

            # The player-name editor retains its existing empty-right no-op.
            reset()
            pyboy.memory[0xC195] = 4
            self._set_bc(pyboy, 0x4F)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.INPUT_ADDRESS)
            self.assertEqual(0xD5, pyboy.memory[0xC16D])
            self.assertEqual(0, pyboy.memory[0xC152])
        finally:
            pyboy.stop(save=False)

    def test_ranking_suffix_follows_native_physical_slot_and_renders_six(self):
        pyboy = self._pyboy()
        try:
            pepper = english.encode("Pepper") + b"\xFF"
            for offset, value in enumerate(pepper):
                pyboy.memory[0xC600 + offset] = value
            self._set_de(pyboy, 0xC600)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.SET_ADDRESS)

            category = 2
            slot = 7
            rank = 0
            record = bytearray((index * 7 + 3) & 0xFF for index in range(32))
            record[0x0F:0x13] = pepper[:4]
            pyboy.memory[0xFF70] = 4
            for offset, value in enumerate(record):
                pyboy.memory[0xDD00 + offset] = value

            pyboy.memory[0x0000] = 0x0A
            pyboy.memory[0x4100] = 3
            for offset in range(4):
                pyboy.memory[name6.RANKING_SRAM_HEADER + offset] = 0
            self._set_bc(pyboy, category << 8)
            self._set_de(pyboy, slot)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.RANK_WRITE_ADDRESS)

            pyboy.memory[0x4100] = 0
            native = 0xA013 + category * 0x640 + slot * 0x20
            self.assertEqual(bytes(record), bytes(pyboy.memory[native:native + 32]))
            pyboy.memory[0x4100] = 3
            self.assertEqual(
                name6.RANKING_SRAM_HEADER_BYTES,
                bytes(pyboy.memory[name6.RANKING_SRAM_HEADER:name6.RANKING_SRAM_HEADER + 4]),
            )
            suffix = name6.RANKING_SRAM_SUFFIXES + category * 100 + slot * 2
            self.assertEqual(pepper[4:6], bytes(pyboy.memory[suffix:suffix + 2]))

            # The native index is physical-slot -> displayed rank.  Loading rank
            # zero must find slot seven and therefore the same suffix.
            index_address = 0xA000 + category * name6.RANKING_SLOTS + slot
            for earlier_slot in range(slot):
                pyboy.memory[index_address - slot + earlier_slot] = earlier_slot + 1
            pyboy.memory[index_address] = rank
            for offset in range(32):
                pyboy.memory[0xCF00 + offset] = 0
            pyboy.memory[0xCFA5] = 0
            pyboy.memory[0xCFA6] = 0
            self._set_bc(pyboy, (category << 8) | rank)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.RANK_LOAD_ADDRESS)
            self.assertEqual(bytes(record), bytes(pyboy.memory[0xCF00:0xCF20]))
            self.assertEqual(pepper[4:6], bytes(pyboy.memory[0xCFA5:0xCFA7]))

            self._set_de(pyboy, 0xC620)
            self._invoke(pyboy, name6.RUNTIME_BANK, name6.RANK_RENDER_ADDRESS)
            self.assertEqual(pepper, bytes(pyboy.memory[0xC620:0xC627]))
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
