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

import blank_scroll
import build as build_tool
import capture_dialogue
import cartridge
import english
import english_font
import extract
import name6
import runtime_widths
import surfaces
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "blank_scroll.json").read_text(
        encoding="utf-8"
    )
)


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("matching original ROM is required")
    rom = path.read_bytes()
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, rom


def _translated_roots(rom):
    result = extract.extract(rom)
    translated = translations.load_path(ROOT / "script" / "en", result["records"])
    by_reference = {
        (reference.group, reference.index): record
        for record in result["records"]
        for reference in record.references
    }
    return result, translated, by_reference


class BlankScrollInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        cls.name6_rom = bytes(name6.install(cls.rom))
        cls.output = blank_scroll.install(cls.name6_rom)
        cls.result, cls.translated, cls.by_reference = _translated_roots(cls.rom)

    def test_fixture_freezes_every_accepted_name_and_full_input(self):
        roots = {}
        for index in range(blank_scroll.ROOT_FIRST, blank_scroll.ROOT_LAST + 1):
            record = self.by_reference[(blank_scroll.ROOT_GROUP, index)]
            roots[index] = self.translated[(record.bank, record.address)].text
        names = [roots[index] for index in blank_scroll.accepted_root_indices()]
        self.assertEqual(FIXTURE, blank_scroll.validate_root_catalog(roots))
        self.assertEqual(32, len(names))
        self.assertEqual(
            {"Eradication", "Trap-eraser", "Squid Sushi"},
            {name for name in names if len(name) == blank_scroll.MAXIMUM_CHARACTERS},
        )
        self.assertEqual(11, max(map(len, names)))

        damaged = dict(roots)
        damaged[69] = "xBlank"
        with self.assertRaises(blank_scroll.BlankScrollError):
            blank_scroll.validate_root_catalog(damaged)

    def test_disabled_markers_retain_the_native_byte_contract(self):
        # $21 is both the native disable sentinel and English uppercase X.
        # Lowercase x would encode to $47 and silently re-enable the entries.
        for index in (69, 79, 114, 121):
            record = self.by_reference[(blank_scroll.ROOT_GROUP, index)]
            text = self.translated[(record.bank, record.address)].text
            self.assertTrue(text.startswith("X"))
            self.assertEqual(0x21, english.encode(text)[0])

    def test_every_enabled_root_still_leads_its_full_item_name(self):
        partitions = (
            (47, 80, 124),
        )
        disabled = set(blank_scroll.ROOT_DISABLED)
        for first, last, first_item in partitions:
            for index in range(first, last + 1):
                root_record = self.by_reference[(12, index)]
                item_record = self.by_reference[(4, first_item + index - first)]
                root = self.translated[(root_record.bank, root_record.address)].text
                item = self.translated[(item_record.bank, item_record.address)].text
                if index in disabled:
                    root = root[1:]
                self.assertTrue(item.casefold().startswith(root.casefold()))

    def test_install_changes_only_owned_ranges_and_is_idempotent(self):
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.name6_rom, self.output))
            if before != after
        }
        owned = {
            offset
            for start, end in blank_scroll.owned_ranges()
            for offset in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed <= owned | checksums)
        self.assertEqual(
            cartridge.stored_checksums(self.output),
            cartridge.verify_checksums(self.output),
        )
        self.assertEqual(self.output, blank_scroll.install(self.output))

    def test_name6_is_an_explicit_prerequisite_and_damage_is_rejected(self):
        with self.assertRaises(blank_scroll.BlankScrollError):
            blank_scroll.install(self.rom)

        for bank, address, _expected, _target in blank_scroll.PATCHES:
            damaged = bytearray(self.name6_rom)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(blank_scroll.BlankScrollError):
                    blank_scroll.install(damaged)

        damaged = bytearray(self.name6_rom)
        damaged[
            extract.file_offset(
                blank_scroll.RUNTIME_BANK, blank_scroll.RUNTIME_ADDRESS
            )
        ] = 1
        with self.assertRaises(blank_scroll.BlankScrollError):
            blank_scroll.install(damaged)

    def test_checked_in_code_matches_rgbds_source_when_available(self):
        if not shutil.which("rgbasm") or not shutil.which("rgblink"):
            self.skipTest("RGBDS is not installed")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            obj = directory / "blank-scroll.o"
            linked = directory / "blank-scroll.gb"
            subprocess.run(
                [
                    "rgbasm", "-Wall", "-Wextra", "-o", str(obj),
                    str(ROOT / "tools" / "blank_scroll.asm"),
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
        start = blank_scroll.RUNTIME_BANK * 0x4000
        self.assertEqual(
            blank_scroll.ASSEMBLED_CODE,
            raw[start:start + len(blank_scroll.ASSEMBLED_CODE)],
        )


class LiveBlankScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path, cls.rom = _original_rom()
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.result, cls.translated, cls.by_reference = _translated_roots(cls.rom)
        overrides = translations.encoded_overrides(cls.translated)
        width_analysis = runtime_widths.analyze(
            english_font.install(cls.rom), cls.result, cls.translated
        )
        output, _allocation, _validation = build_tool.build_rom(
            cls.rom,
            overrides,
            runtime_contract=width_analysis.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "blank-scroll.gbc"
        cls.localized_path.write_bytes(output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _pyboy(self):
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
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
        trampoline = bytes(
            (
                0x3E, bank, 0x21, address & 0xFF, address >> 8,
                0xCD, 0xAC, 0x09,
                0x3E, 0x42, 0xEA, 0xFF, 0xC7,
                0x18, 0xFE,
            )
        )
        for offset, value in enumerate(trampoline):
            pyboy.memory[0xC700 + offset] = value
        pyboy.memory[0xC7FF] = 0
        old_ie = pyboy.memory[0xFFFF]
        pyboy.memory[0xFFFF] = (old_ie | 1) if allow_interrupts else 0
        pyboy.memory[0xFF0F] = 0
        pyboy.register_file.SP = 0xC6F0
        pyboy.register_file.PC = 0xC700
        for _frame in range(120 if allow_interrupts else 4):
            pyboy.tick()
            if pyboy.memory[0xC7FF] == 0x42:
                break
        pyboy.memory[0xFFFF] = old_ie
        self.assertEqual(0x42, pyboy.memory[0xC7FF])

    def _root_text(self, index):
        record = self.by_reference[(blank_scroll.ROOT_GROUP, index)]
        return self.translated[(record.bank, record.address)].text

    def _prepare_matcher(self, pyboy, learned_indices=()):
        pyboy.memory[0xFF70] = 2
        object_record = bytes((146, 7, 0, 0, 0, 0, 0, 0))
        for offset, value in enumerate(object_record):
            pyboy.memory[0xD482 + offset] = value
        for offset in range(32):
            pyboy.memory[blank_scroll.ROOT_HISTORY_ADDRESS + offset] = 0
        for index in learned_indices:
            address = blank_scroll.ROOT_HISTORY_ADDRESS + index // 8
            pyboy.memory[address] |= 1 << (index & 7)

    def _match(self, pyboy, text):
        raw = english.encode(text) + b"\xFF"
        for offset, value in enumerate(raw):
            pyboy.memory[0xC600 + offset] = value
        self._set_bc(pyboy, 0xC600)
        self._set_de(pyboy, 0xFF00)
        self._invoke(
            pyboy,
            blank_scroll.ROOT_MATCHER_BANK,
            blank_scroll.ROOT_MATCHER_ADDRESS,
        )
        return (
            (pyboy.register_file.B << 8) | pyboy.register_file.C,
            pyboy.register_file.D,
        )

    def _localized_match(self, pyboy, text, learned_indices=()):
        self._prepare_matcher(pyboy, learned_indices=learned_indices)
        raw = english.encode(text)
        self.assertLessEqual(len(raw), blank_scroll.MAXIMUM_CHARACTERS)
        for offset in range(blank_scroll.MAXIMUM_CHARACTERS + 1):
            pyboy.memory[blank_scroll.INPUT_BUFFER_ADDRESS + offset] = 0xD5
        for offset, value in enumerate(raw):
            pyboy.memory[blank_scroll.INPUT_BUFFER_ADDRESS + offset] = value
        pyboy.memory[blank_scroll.INPUT_BUFFER_ADDRESS + len(raw)] = 0xFF

        # The old failure copied a ninth character into $C195 (wInputMode).
        # Preserve a canary across the native seven-character scratch field
        # and prove that the custom matcher never writes there.
        scratch = bytes(range(0xA0, 0xA8))
        for offset, value in enumerate(scratch):
            pyboy.memory[blank_scroll.INPUT_SCRATCH_ADDRESS + offset] = value
        pyboy.memory[blank_scroll.INPUT_MODE_ADDRESS] = blank_scroll.MODE
        pyboy.memory[blank_scroll.MATCH_CACHE_ADDRESS] = 0xFF
        self._invoke(
            pyboy,
            blank_scroll.RUNTIME_BANK,
            blank_scroll.MATCHER_ADDRESS,
        )
        self.assertEqual(
            scratch,
            bytes(
                pyboy.memory[
                    blank_scroll.INPUT_SCRATCH_ADDRESS:
                    blank_scroll.INPUT_MODE_ADDRESS
                ]
            ),
        )
        self.assertEqual(
            blank_scroll.MODE,
            pyboy.memory[blank_scroll.INPUT_MODE_ADDRESS],
        )
        return pyboy.memory[blank_scroll.MATCH_CACHE_ADDRESS]

    def test_localized_matcher_resolves_every_name_without_touching_input_mode(self):
        pyboy = self._pyboy()
        try:
            for index in blank_scroll.accepted_root_indices():
                name = self._root_text(index)
                with self.subTest(index=index, name=name):
                    self.assertEqual(
                        index,
                        self._localized_match(
                            pyboy, name, learned_indices=(index,)
                        ),
                    )
        finally:
            pyboy.stop(save=False)

    def test_localized_matcher_rejects_unlearned_and_inexact_names_safely(self):
        pyboy = self._pyboy()
        try:
            self.assertEqual(0xFF, self._localized_match(pyboy, "Windblade"))
            self.assertEqual(
                0xFF,
                self._localized_match(
                    pyboy, "Windblad", learned_indices=(50,)
                ),
            )
            self.assertEqual(
                0xFF,
                self._localized_match(
                    pyboy, "windblade", learned_indices=(50,)
                ),
            )
        finally:
            pyboy.stop(save=False)

    def test_real_matcher_accepts_every_full_learned_scroll_name(self):
        pyboy = self._pyboy()
        try:
            names = [
                self._root_text(index)
                for index in blank_scroll.accepted_root_indices()
            ]
            self.assertEqual(tuple(names), blank_scroll.selectable_inputs(names))
            for index, name in zip(blank_scroll.accepted_root_indices(), names):
                self._prepare_matcher(pyboy, learned_indices=(index,))
                with self.subTest(index=index, name=name):
                    pointer, matched = self._match(pyboy, name)
                    self.assertEqual((0xC374, index), (pointer, matched))
        finally:
            pyboy.stop(save=False)

    def test_real_matcher_rejects_disabled_and_unread_roots(self):
        pyboy = self._pyboy()
        try:
            self._prepare_matcher(
                pyboy, learned_indices=blank_scroll.accepted_root_indices()
            )
            for index in blank_scroll.ROOT_DISABLED:
                with self.subTest(disabled=index):
                    pointer, _matched = self._match(pyboy, self._root_text(index))
                    self.assertEqual(0, pointer)

            pointer, _matched = self._match(pyboy, self._root_text(47).lower())
            self.assertEqual(0, pointer)

            self._prepare_matcher(pyboy)
            pointer, _matched = self._match(pyboy, self._root_text(47))
            self.assertEqual(0, pointer)
        finally:
            pyboy.stop(save=False)

    def test_mode1_screen_has_11_cells_english_map_and_working_hyphen(self):
        pyboy = self._pyboy()
        try:
            self._set_bc(pyboy, blank_scroll.MODE)
            self._invoke(
                pyboy,
                blank_scroll.RUNTIME_BANK,
                blank_scroll.SCREEN_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(blank_scroll.MODE, pyboy.memory[0xC195])
            self.assertEqual(
                blank_scroll.MAXIMUM_CHARACTERS, pyboy.memory[0xC153]
            )
            self.assertEqual(
                b"\xD5" * blank_scroll.MAXIMUM_CHARACTERS + b"\xFF",
                bytes(
                    pyboy.memory[
                        blank_scroll.INPUT_BUFFER_ADDRESS:
                        blank_scroll.INPUT_BUFFER_ADDRESS
                        + blank_scroll.MAXIMUM_CHARACTERS + 1
                    ]
                ),
            )

            expected = bytearray(name6.english_keyboard_map(self.rom))
            expected[10 * 20 + 13] = english.ENGLISH_CODES["-"]
            old_vbk = pyboy.memory[0xFF4F]
            pyboy.memory[0xFF4F] = 0
            observed = bytes(
                pyboy.memory[0x9840 + row * 32 + column]
                for row in range(16)
                for column in range(20)
            )
            pyboy.memory[0xFF4F] = old_vbk & 1
            self.assertEqual(bytes(expected), observed)

            self._set_bc(pyboy, blank_scroll.HYPHEN_NODE)
            self._invoke(
                pyboy,
                blank_scroll.RUNTIME_BANK,
                blank_scroll.INPUT_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(
                english.ENGLISH_CODES["-"],
                pyboy.memory[blank_scroll.INPUT_BUFFER_ADDRESS],
            )
            self.assertEqual(1, pyboy.memory[0xC152])
        finally:
            pyboy.stop(save=False)

    def test_mode1_editor_accepts_longest_roots_with_hyphen_and_space(self):
        pyboy = self._pyboy()
        try:
            for name in ("Trap-eraser", "Squid Sushi"):
                with self.subTest(name=name):
                    self._set_bc(pyboy, blank_scroll.MODE)
                    self._invoke(
                        pyboy,
                        blank_scroll.RUNTIME_BANK,
                        blank_scroll.SCREEN_ADDRESS,
                        allow_interrupts=True,
                    )
                    self.assertEqual(blank_scroll.MAXIMUM_CHARACTERS, len(name))
                    for character in name:
                        node = (
                            0x4B
                            if character == " "
                            else (
                                blank_scroll.HYPHEN_NODE
                                if character == "-"
                                else name6.KEYBOARD_CHARACTERS.index(character)
                            )
                        )
                        self._set_bc(pyboy, node)
                        self._invoke(
                            pyboy,
                            blank_scroll.RUNTIME_BANK,
                            blank_scroll.INPUT_ADDRESS,
                            allow_interrupts=True,
                        )
                    self.assertEqual(
                        english.encode(name) + b"\xFF",
                        bytes(
                            pyboy.memory[
                                blank_scroll.INPUT_BUFFER_ADDRESS:
                                blank_scroll.INPUT_BUFFER_ADDRESS
                                + blank_scroll.MAXIMUM_CHARACTERS + 1
                            ]
                        ),
                    )
        finally:
            pyboy.stop(save=False)

    def test_live_write_route_converts_blank_scroll_from_full_windblade_name(self):
        state_owner = self.PyBoy(str(self.source_path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        pyboy = self._pyboy()
        try:
            pyboy.load_state(io.BytesIO(state_bytes))
            old_svbk = pyboy.memory[0xFF70]
            pyboy.memory[0xFF70] = surfaces.ITEM_INVENTORY_WRAM_BANK
            for slot, seed in enumerate(surfaces.ITEM_CATEGORY_SEEDS):
                pyboy.memory[surfaces.ITEM_INVENTORY_BASE + slot] = seed.object_index
            pyboy.memory[
                surfaces.ITEM_INVENTORY_BASE + len(surfaces.ITEM_CATEGORY_SEEDS)
            ] = surfaces.ITEM_INVENTORY_SENTINEL
            pyboy.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
            for seed in surfaces.ITEM_CATEGORY_SEEDS:
                object_at = (
                    surfaces.ITEM_OBJECT_BASE
                    + seed.object_index * surfaces.ITEM_OBJECT_SIZE
                )
                for offset, value in enumerate(seed.object_record):
                    pyboy.memory[object_at + offset] = value
            blank_seed = next(
                seed for seed in surfaces.ITEM_CATEGORY_SEEDS
                if seed.category == "scroll"
            )
            blank_at = (
                surfaces.ITEM_OBJECT_BASE
                + blank_seed.object_index * surfaces.ITEM_OBJECT_SIZE
            )
            for offset, value in enumerate((146, 7, 0, 0, 0, 0, 0, 0)):
                pyboy.memory[blank_at + offset] = value
            for offset in range(32):
                pyboy.memory[blank_scroll.ROOT_HISTORY_ADDRESS + offset] = 0
            windblade_root = 50
            history_at = (
                blank_scroll.ROOT_HISTORY_ADDRESS + windblade_root // 8
            )
            pyboy.memory[history_at] = 1 << (windblade_root & 7)
            pyboy.memory[0xFF70] = old_svbk & 7
            pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS] &= (
                ~surfaces.ITEM_ACTION_GLOBAL_GATE_MASK & 0xFF
            )

            inputs = {
                0: "b", 100: "a", 150: "down", 200: "down",
                250: "down", 300: "down", 350: "down", 400: "down",
                500: "a", 600: "down", 650: "a",
            }
            for current in range(1151):
                if current in inputs:
                    pyboy.button(inputs[current], capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            self.assertEqual(
                blank_scroll.MAXIMUM_CHARACTERS,
                pyboy.memory[blank_scroll.INPUT_MAXIMUM_ADDRESS],
            )

            navigation = name6.english_navigation_table(self.rom)
            records = [
                navigation[offset:offset + name6.NAVIGATION_RECORD_SIZE]
                for offset in range(0, len(navigation), name6.NAVIGATION_RECORD_SIZE)
            ]
            directions = ("down", "up", "left", "right")

            def press(button):
                pyboy.button(button, capture_dialogue.PRESS_FRAMES)
                for _frame in range(20):
                    pyboy.tick()

            def move_to(target):
                start = pyboy.memory[0xC14F]
                pending = [(start, ())]
                visited = {start}
                path = None
                while pending:
                    node, candidate = pending.pop(0)
                    if node == target:
                        path = candidate
                        break
                    for direction, neighbor in zip(directions, records[node][:4]):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            pending.append((neighbor, candidate + (direction,)))
                self.assertIsNotNone(path)
                for direction in path:
                    press(direction)
                self.assertEqual(target, pyboy.memory[0xC14F])

            for character in "Windblade":
                move_to(name6.KEYBOARD_CHARACTERS.index(character))
                press("a")
            move_to(77)
            press("a")
            reset_frames = []
            for post_confirm_frame in range(600):
                pyboy.tick()
                if pyboy.register_file.PC in (0, 0xFFFF):
                    reset_frames.append(post_confirm_frame)

            old_svbk = pyboy.memory[0xFF70]
            pyboy.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
            self.assertEqual(127, pyboy.memory[blank_at])
            pyboy.memory[0xFF70] = old_svbk & 7
            self.assertEqual([], reset_frames)
        finally:
            pyboy.stop(save=False)

    def test_blank_maximum_wrapper_preserves_name_and_spell_limits(self):
        pyboy = self._pyboy()
        try:
            for mode, expected in ((1, 11), (3, 4), (4, 6)):
                pyboy.memory[blank_scroll.INPUT_MODE_ADDRESS] = mode
                pyboy.memory[blank_scroll.INPUT_MAXIMUM_ADDRESS] = 0
                self._invoke(
                    pyboy,
                    blank_scroll.RUNTIME_BANK,
                    blank_scroll.MAXIMUM_ADDRESS,
                )
                self.assertEqual(
                    expected,
                    pyboy.memory[blank_scroll.INPUT_MAXIMUM_ADDRESS],
                )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
