from hashlib import sha1
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import blank_scroll
import capture_dialogue
import cartridge
import english
import english_font
import extract
import mesen_state
import name6
import spell_input
import surfaces
import translations
import unidentified_names


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE_NAME = "unidentified-item-naming.mss"
STATE_SHA1 = "2db915b2283fb9e0d831df2a0fe0d3e5beaf3c76"


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("matching original ROM is required")
    rom = path.read_bytes()
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, rom


def _prerequisites(rom):
    output = name6.install(rom)
    output = blank_scroll.install(output)
    return spell_input.install(output)


def _records(raw):
    return [
        raw[offset:offset + name6.NAVIGATION_RECORD_SIZE]
        for offset in range(0, len(raw), name6.NAVIGATION_RECORD_SIZE)
    ]


def _translated_roots(rom):
    result = extract.extract(rom)
    translated = translations.load_path(ROOT / "script" / "en", result["records"])
    by_reference = {
        (reference.group, reference.index): record
        for record in result["records"]
        for reference in record.references
    }
    return {
        index: translated[
            (
                by_reference[(unidentified_names.ROOT_GROUP, index)].bank,
                by_reference[(unidentified_names.ROOT_GROUP, index)].address,
            )
        ].text
        for index in range(unidentified_names.ROOT_ENTRIES)
    }


class UnidentifiedNameInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        cls.prerequisites = _prerequisites(cls.rom)
        cls.output = unidentified_names.install(cls.prerequisites)
        cls.roots = _translated_roots(cls.rom)

    def test_user_fixture_is_frozen(self):
        state = ROOT / "SaveStates" / STATE_NAME
        self.assertTrue(state.is_file())
        self.assertEqual(STATE_SHA1, sha1(state.read_bytes()).hexdigest())

    def test_canonical_signature_cannot_alias_a_native_free_label(self):
        # Native allocation treats byte-zero FF as an unused slot. New tokens
        # therefore start with non-enterable FE and retain the old reversed
        # pair only as a backward-compatible read signature.
        self.assertEqual(0xFE, unidentified_names.CANONICAL_PREFIX)
        self.assertEqual(0xFF, unidentified_names.CANONICAL_MARKER)
        self.assertEqual(0xFF, unidentified_names.LEGACY_CANONICAL_PREFIX)
        self.assertEqual(0xFE, unidentified_names.LEGACY_CANONICAL_MARKER)
        self.assertNotEqual(0xFF, unidentified_names.CANONICAL_PREFIX)
        self.assertNotIn(
            unidentified_names.CANONICAL_PREFIX,
            name6.character_bytes(),
        )
        self.assertTrue(all(
            last < unidentified_names.CANONICAL_MARKER
            for _category, _first, last, _first_item
            in surfaces.ITEM_NAME_ROOT_PARTITIONS
        ))

    def test_every_recalled_root_fits_the_fourteen_cell_presentation_field(self):
        self.assertEqual(
            {
                "free_name_maximum": 7,
                "fill_in_maximum": 14,
                "longest": [
                    {
                        "root_index": 88,
                        "name": "Narrow-escape",
                        "characters": 13,
                    },
                    {
                        "root_index": 112,
                        "name": "Transmutation",
                        "characters": 13,
                    },
                ],
            },
            unidentified_names.validate_root_catalog(self.roots),
        )
        damaged = dict(self.roots)
        damaged[88] += "!!"
        with self.assertRaises(unidentified_names.UnidentifiedNameError):
            unidentified_names.validate_root_catalog(damaged)

    def test_mode0_map_has_fill_in_and_preserves_the_approved_keyboard(self):
        raw = unidentified_names.english_keyboard_map(self.prerequisites)
        rows = [raw[offset:offset + 20] for offset in range(0, len(raw), 20)]
        blank = english.ENGLISH_CODES[" "]
        self.assertEqual(english.encode("SPACE"), rows[2][1:6])
        self.assertEqual(blank, rows[2][6])
        self.assertEqual(english.encode("FILL IN"), rows[2][7:14])
        self.assertEqual(blank, rows[2][14])
        self.assertEqual(english.encode("OK"), rows[2][15:17])
        self.assertEqual(
            english.ENGLISH_CODES[name6.LEFT_CURSOR_CHARACTER], rows[4][1]
        )
        self.assertEqual(
            english.ENGLISH_CODES[name6.RIGHT_CURSOR_CHARACTER], rows[4][8]
        )
        self.assertEqual(english.encode("DEL"), rows[4][15:18])

        shared = name6.english_keyboard_map(self.prerequisites)
        for row in range(16):
            before = shared[row * 20:(row + 1) * 20]
            after = rows[row]
            if row == 2:
                self.assertEqual(before[:7], after[:7])
                self.assertEqual(before[14:], after[14:])
            else:
                self.assertEqual(before, after)

    def test_mode0_graph_restores_only_fill_in_and_is_fully_connected(self):
        navigation = unidentified_names.english_navigation_table(
            self.prerequisites
        )
        records = _records(navigation)
        positions = name6.character_positions()
        node_at = {position: node for node, position in enumerate(positions)}
        controls = {
            75: (78, node_at[(4, 0)], 77, 76),
            76: (79, node_at[(4, 6)], 75, 77),
            77: (80, node_at[(3, 15)], 76, 75),
            78: (node_at[(0, 0)], 75, 80, 79),
            79: (node_at[(0, 6)], 76, 78, 80),
            80: (node_at[(0, 12)], 77, 79, 78),
        }
        active = set(range(len(name6.KEYBOARD_CHARACTERS))) | set(controls)
        blanks = set(range(len(name6.KEYBOARD_CHARACTERS), 75))
        for node, neighbors in controls.items():
            self.assertEqual(bytes(neighbors), records[node][:4])
        for node in active:
            self.assertFalse(set(records[node][:4]) & blanks)

        reached = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for target in records[node][:4]:
                if target in active and target not in reached:
                    reached.add(target)
                    pending.append(target)
        self.assertEqual(active, reached)

        # From the initial A cell: Up -> buffer-left, Right -> buffer-right,
        # Up -> Fill In. This route is also frozen in the manual test docs.
        node = 0
        for direction in (1, 3, 1):
            node = records[node][direction]
        self.assertEqual(unidentified_names.FILL_IN_NODE, node)

    def test_private_graph_pointer_does_not_steal_native_list_type_13(self):
        native_pointer = extract.file_offset(
            unidentified_names.NAVIGATION_BANK, 0x5F9A
        )
        self.assertEqual(
            bytes.fromhex("2566"),
            self.output[native_pointer:native_pointer + 2],
        )

        private_pointer = extract.file_offset(
            unidentified_names.NAVIGATION_BANK,
            unidentified_names.NAVIGATION_POINTER_ADDRESS,
        )
        self.assertEqual(
            unidentified_names.NAVIGATION_POINTER_PATCH,
            self.output[private_pointer:private_pointer + 2],
        )
        self.assertEqual(
            unidentified_names.NAVIGATION_POINTER_ADDRESS,
            0x5F74 + unidentified_names.NAVIGATION_TYPE * 2,
        )
        self.assertEqual(
            64,
            (
                unidentified_names.NAVIGATION_POINTER_ADDRESS
                - name6.NAVIGATION_ADDRESS
            ) // name6.NAVIGATION_RECORD_SIZE,
        )

    def test_installer_changes_only_owned_ranges_and_is_idempotent(self):
        changed = {
            offset
            for offset, (before, after) in enumerate(
                zip(self.prerequisites, self.output)
            )
            if before != after
        }
        owned = {
            offset
            for start, end in unidentified_names.owned_ranges()
            for offset in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= owned | checksums)
        cartridge.verify_checksums(self.output)
        self.assertEqual(
            self.output, unidentified_names.install(self.output)
        )

    def test_prerequisite_and_reserved_space_damage_fail_closed(self):
        for bank, address, _expected, _target in unidentified_names.CALL_PATCHES:
            damaged = bytearray(self.prerequisites)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(unidentified_names.UnidentifiedNameError):
                    unidentified_names.install(damaged)

        for bank, address, _expected, _replacement in unidentified_names.RAW_PATCHES:
            damaged = bytearray(self.prerequisites)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(unidentified_names.UnidentifiedNameError):
                    unidentified_names.install(damaged)

        damaged = bytearray(self.prerequisites)
        damaged[
            extract.file_offset(
                unidentified_names.NAVIGATION_BANK,
                unidentified_names.NAVIGATION_POINTER_ADDRESS,
            )
        ] ^= 1
        with self.assertRaises(unidentified_names.UnidentifiedNameError):
            unidentified_names.install(damaged)

        damaged = bytearray(self.prerequisites)
        damaged[
            extract.file_offset(
                unidentified_names.RUNTIME_BANK,
                unidentified_names.RUNTIME_ADDRESS,
            )
        ] = 1
        with self.assertRaises(unidentified_names.UnidentifiedNameError):
            unidentified_names.install(damaged)

    def test_checked_in_code_matches_rgbds_source_when_available(self):
        if not shutil.which("rgbasm") or not shutil.which("rgblink"):
            self.skipTest("RGBDS is not installed")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            obj = directory / "unidentified-names.o"
            linked = directory / "unidentified-names.gb"
            subprocess.run(
                [
                    "rgbasm", "-Wall", "-Wextra", "-o", str(obj),
                    str(ROOT / "tools" / "unidentified_names.asm"),
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
        start = unidentified_names.RUNTIME_BANK * 0x4000
        self.assertEqual(
            unidentified_names.ASSEMBLED_CODE,
            raw[start:start + len(unidentified_names.ASSEMBLED_CODE)],
        )


class LiveUnidentifiedNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _path, cls.rom = _original_rom()
        state = ROOT / "SaveStates" / STATE_NAME
        if not state.is_file():
            raise unittest.SkipTest("user unidentified-name state is required")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.ram = mesen_state.cart_ram(state)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "unidentified-names.gbc"
        cls.localized_path.write_bytes(
            unidentified_names.install(
                _prerequisites(english_font.install(cls.rom))
            )
        )

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
        for _frame in range(120):
            pyboy.tick()
        return pyboy

    def _invoke(self, pyboy, bank, address, allow_interrupts=False, c=0, de=0):
        trampoline = bytes(
            (
                0x3E, bank, 0x21, address & 0xFF, address >> 8,
                0xCD, 0xAC, 0x09,
                0x3E, 0x42, 0xEA, 0xFF, 0xC7, 0x18, 0xFE,
            )
        )
        for offset, value in enumerate(trampoline):
            pyboy.memory[0xC700 + offset] = value
        pyboy.memory[0xC7FF] = 0
        old_ie = pyboy.memory[0xFFFF]
        pyboy.memory[0xFFFF] = (old_ie | 1) if allow_interrupts else 0
        pyboy.memory[0xFF0F] = 0
        pyboy.register_file.B = 0
        pyboy.register_file.C = c
        pyboy.register_file.D = de >> 8
        pyboy.register_file.E = de & 0xFF
        pyboy.register_file.SP = 0xC6F0
        pyboy.register_file.PC = 0xC700
        for _frame in range(120 if allow_interrupts else 2):
            pyboy.tick()
            if pyboy.memory[0xC7FF] == 0x42:
                break
        pyboy.memory[0xFFFF] = old_ie
        self.assertEqual(0x42, pyboy.memory[0xC7FF])

    def _seed_canonical_preview(self, pyboy):
        pyboy.memory[0xC195] = unidentified_names.MODE
        pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS] = (
            unidentified_names.FILL_IN_MAXIMUM
        )
        pyboy.memory[unidentified_names.INPUT_POSITION_ADDRESS] = 8
        pyboy.memory[0xC196] = 50
        raw = (
            english.encode("Windblade")
            + english.encode(" ") * 5
            + b"\xFF"
        )
        for offset, value in enumerate(raw):
            pyboy.memory[unidentified_names.INPUT_BUFFER_ADDRESS + offset] = value

    def test_mode0_constructor_has_seven_cells_fill_in_and_own_graph(self):
        pyboy = self._pyboy()
        try:
            self._invoke(
                pyboy,
                unidentified_names.RUNTIME_BANK,
                unidentified_names.SCREEN_ADDRESS,
                allow_interrupts=True,
            )
            self.assertEqual(0, pyboy.memory[0xC195])
            self.assertEqual(7, pyboy.memory[0xC153])
            self.assertEqual(
                unidentified_names.NAVIGATION_TYPE,
                pyboy.memory[0xC14E],
            )
            expected_navigation = unidentified_names.english_navigation_table(
                _prerequisites(self.rom)
            )
            self.assertEqual(
                expected_navigation,
                bytes(
                    pyboy.memory[
                        unidentified_names.NAVIGATION_SCRATCH:
                        unidentified_names.NAVIGATION_SCRATCH
                        + unidentified_names.NAVIGATION_SIZE
                    ]
                ),
            )

            old_vbk = pyboy.memory[0xFF4F]
            pyboy.memory[0xFF4F] = 0
            observed = bytes(
                pyboy.memory[0x9840 + row * 32 + column]
                for row in range(16)
                for column in range(20)
            )
            pyboy.memory[0xFF4F] = old_vbk & 1
            self.assertEqual(
                unidentified_names.english_keyboard_map(
                    _prerequisites(self.rom)
                ),
                observed,
            )
        finally:
            pyboy.stop(save=False)

    def test_current_and_legacy_canonical_tokens_both_resolve(self):
        pyboy = self._pyboy()
        try:
            destination = 0xC600
            resolved = []
            for signature in (
                (
                    unidentified_names.CANONICAL_PREFIX,
                    unidentified_names.CANONICAL_MARKER,
                ),
                (
                    unidentified_names.LEGACY_CANONICAL_PREFIX,
                    unidentified_names.LEGACY_CANONICAL_MARKER,
                ),
            ):
                with self.subTest(signature=signature):
                    pyboy.memory[0xFF70] = 2
                    raw = bytes(signature) + bytes((50,)) + b"\xFF" * 5
                    for offset, value in enumerate(raw):
                        pyboy.memory[0xDD78 + offset] = value
                    for offset in range(16):
                        pyboy.memory[destination + offset] = 0xD5
                    self._invoke(
                        pyboy,
                        unidentified_names.RUNTIME_BANK,
                        unidentified_names.RESOLVE_ADDRESS,
                        c=0,
                        de=destination,
                    )
                    observed = bytes(
                        pyboy.memory[destination:destination + 16]
                    )
                    self.assertNotEqual(b"\xD5" * 16, observed)
                    resolved.append(observed)
            self.assertEqual(resolved[0], resolved[1])
        finally:
            pyboy.stop(save=False)

    def test_free_typing_stays_at_seven_even_with_an_expanded_recall_field(self):
        pyboy = self._pyboy()
        try:
            pyboy.memory[0xC195] = unidentified_names.MODE
            pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS] = (
                unidentified_names.FILL_IN_MAXIMUM
            )
            pyboy.memory[unidentified_names.INPUT_POSITION_ADDRESS] = 6
            pyboy.memory[0xC196] = 0xFF
            raw = english.encode("ABCDEFG") + b"\xFF" + b"\xD5" * 7
            for offset, value in enumerate(raw):
                pyboy.memory[unidentified_names.INPUT_BUFFER_ADDRESS + offset] = value

            self._invoke(
                pyboy,
                unidentified_names.RUNTIME_BANK,
                unidentified_names.INPUT_ADDRESS,
                c=name6.KEYBOARD_CHARACTERS.index("H"),
            )
            self.assertEqual(
                6, pyboy.memory[unidentified_names.INPUT_POSITION_ADDRESS]
            )
            # At the final native cell, another character edits that cell; it
            # must not extend into the presentation-only recall tail.
            self.assertEqual(
                english.encode("ABCDEFH") + b"\xFF",
                bytes(
                    pyboy.memory[
                        unidentified_names.INPUT_BUFFER_ADDRESS:
                        unidentified_names.INPUT_BUFFER_ADDRESS + 8
                    ]
                ),
            )
            self.assertEqual(
                unidentified_names.FREE_NAME_MAXIMUM,
                pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS],
            )
        finally:
            pyboy.stop(save=False)

    def test_typing_after_fill_in_starts_a_fresh_free_name(self):
        pyboy = self._pyboy()
        try:
            self._seed_canonical_preview(pyboy)
            self._invoke(
                pyboy,
                unidentified_names.RUNTIME_BANK,
                unidentified_names.INPUT_ADDRESS,
                allow_interrupts=True,
                c=name6.KEYBOARD_CHARACTERS.index("A"),
            )
            self.assertEqual(0xFF, pyboy.memory[0xC196])
            self.assertEqual(
                unidentified_names.FREE_NAME_MAXIMUM,
                pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS],
            )
            self.assertEqual(
                english.encode("A") + b"\xD5" * 6 + b"\xFF",
                bytes(
                    pyboy.memory[
                        unidentified_names.INPUT_BUFFER_ADDRESS:
                        unidentified_names.INPUT_BUFFER_ADDRESS + 8
                    ]
                ),
            )
            self.assertLessEqual(
                pyboy.memory[unidentified_names.INPUT_POSITION_ADDRESS], 6
            )
            self.assertEqual(
                b"\xD5" * 6,
                bytes(
                    pyboy.memory[
                        unidentified_names.INPUT_BUFFER_ADDRESS + 8:
                        unidentified_names.INPUT_BUFFER_ADDRESS + 14
                    ]
                ),
            )
        finally:
            pyboy.stop(save=False)

    def test_delete_after_fill_in_restores_the_empty_free_name_field(self):
        pyboy = self._pyboy()
        try:
            self._seed_canonical_preview(pyboy)
            self._invoke(
                pyboy,
                unidentified_names.RUNTIME_BANK,
                unidentified_names.INPUT_ADDRESS,
                allow_interrupts=True,
                c=0x50,
            )
            self.assertEqual(0xFF, pyboy.memory[0xC196])
            self.assertEqual(0, pyboy.memory[0xC152])
            self.assertEqual(
                unidentified_names.FREE_NAME_MAXIMUM,
                pyboy.memory[unidentified_names.INPUT_MAXIMUM_ADDRESS],
            )
            self.assertEqual(
                b"\xD5" * 7 + b"\xFF",
                bytes(
                    pyboy.memory[
                        unidentified_names.INPUT_BUFFER_ADDRESS:
                        unidentified_names.INPUT_BUFFER_ADDRESS + 8
                    ]
                ),
            )
            self.assertEqual(
                b"\xD5" * 6,
                bytes(
                    pyboy.memory[
                        unidentified_names.INPUT_BUFFER_ADDRESS + 8:
                        unidentified_names.INPUT_BUFFER_ADDRESS + 14
                    ]
                ),
            )
        finally:
            pyboy.stop(save=False)


class MesenUnidentifiedNameRouteTests(unittest.TestCase):
    """Exercise Name -> Fill In -> full canonical display in the real menus."""

    @classmethod
    def setUpClass(cls):
        candidates = [
            os.environ.get("MESEN_BIN"),
            shutil.which("Mesen"),
            shutil.which("mesen"),
            "/Applications/Mesen.app/Contents/MacOS/Mesen",
        ]
        cls.mesen = next(
            (Path(path) for path in candidates if path and Path(path).is_file()),
            None,
        )
        if cls.mesen is None:
            raise unittest.SkipTest("Mesen test-runner executable is unavailable")
        cls.source, rom = _original_rom()
        cls.state = ROOT / "SaveStates" / "Mamel.mss"
        if not cls.state.is_file():
            raise unittest.SkipTest("Mamel Mesen state fixture is unavailable")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "unidentified-names-mesen.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(cls.source),
                str(ROOT / "script" / "en"),
                str(cls.localized),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if built.returncode:
            cls.temporary.cleanup()
            raise AssertionError(
                "could not build unidentified-name fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _run_route(self, route):
        env = os.environ.copy()
        env["GB2_MSS_PATH"] = str(self.state)
        env["GB2_UNIDENTIFIED_ROUTE"] = route
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_unidentified_names_live.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        return output

    def test_fill_in_stores_a_token_and_renders_full_windblade(self):
        output = self._run_route("confirm")
        self.assertIn("localized mode-0 constructor reached", output)
        self.assertIn("native Fill In cycle reached", output)
        self.assertIn(
            "full Windblade Fill In preview retained in fourteen-cell field",
            output,
        )
        self.assertIn(
            "canonical preview aligned to native seven-cell origin", output
        )
        self.assertIn("canonical token stored", output)
        self.assertIn("canonical token resolver returned", output)
        self.assertIn(
            "PASS mode=00 node=01 nav=01 maximum=00", output
        )
        self.assertIn("screen=AC438159", output)

    def test_typing_after_fill_in_resets_then_confirms_a_free_name(self):
        output = self._run_route("type")
        self.assertIn(
            "type-after-fill reset frame=1136 pos=01 max=07 "
            "screen=1D46725B",
            output,
        )
        self.assertIn("PASS route=type", output)
        self.assertIn("node=01 nav=01", output)

    def test_delete_after_fill_in_resets_then_accepts_a_free_name(self):
        output = self._run_route("delete")
        self.assertIn(
            "delete-after-fill reset frame=1136 pos=00 max=07 "
            "screen=52CC5419",
            output,
        )
        self.assertIn(
            "empty free field aligned to native seven-cell origin", output
        )
        self.assertIn("PASS route=delete", output)
        self.assertIn("node=01 nav=01", output)


if __name__ == "__main__":
    unittest.main()
