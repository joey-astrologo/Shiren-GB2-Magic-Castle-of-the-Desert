from collections import deque
from hashlib import sha1
import io
import json
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
import extract
import name6
import mesen_state
import rescue_password
import rescue_presentation
import spell_input
import unidentified_names


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
REQUESTER_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "rescue_requester.json").read_text(
        encoding="utf-8"
    )
)
ENTRY_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "rescue_entry.json").read_text(
        encoding="utf-8"
    )
)


def _install_prerequisites(rom):
    output = name6.install(rom, checksums=False)
    output = blank_scroll.install(output, checksums=False)
    output = spell_input.install(output, checksums=False)
    return unidentified_names.install(output, checksums=False)


def _records(raw):
    size = name6.NAVIGATION_RECORD_SIZE
    return tuple(raw[index:index + size] for index in range(0, len(raw), size))


def _shortest_buttons(records, start, target):
    buttons = ("down", "up", "left", "right")
    pending = deque(((start, ()),))
    reached = {start}
    while pending:
        node, path = pending.popleft()
        if node == target:
            return path
        for edge, button in enumerate(buttons):
            neighbor = records[node][edge]
            if neighbor not in reached:
                reached.add(neighbor)
                pending.append((neighbor, path + (button,)))
    raise AssertionError("navigation target %d is unreachable" % target)


def _input_sequences(rom, text):
    records = _records(rescue_presentation.english_navigation_table(rom))
    node = 0
    characters = []
    for character in text:
        target = rescue_password.LOCALIZED_ALPHABET.index(character)
        characters.extend(_shortest_buttons(records, node, target))
        characters.append("a")
        node = target
    # The native full-field handler moves the navigation node to OK as soon as
    # the final password cell is filled. Moving from the last character's
    # keyboard node here would instead land on another control (usually DEL)
    # and could make a route appear to submit while actually erasing input.
    return characters, ["a"]


class RescuePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()
        cls.prerequisite = _install_prerequisites(cls.rom)

    def test_embedded_alphabets_match_both_sides_of_the_mapping(self):
        payload = rescue_presentation.runtime_payload(self.prerequisite)
        english_at = (
            rescue_presentation.ALPHABET_ADDRESS
            - rescue_presentation.RUNTIME_ADDRESS
        )
        native_at = (
            rescue_presentation.NATIVE_ALPHABET_ADDRESS
            - rescue_presentation.RUNTIME_ADDRESS
        )
        self.assertEqual(
            rescue_password.LOCALIZED_ALPHABET_CODES,
            payload[english_at:english_at + 64],
        )
        self.assertEqual(
            rescue_password.NATIVE_ALPHABET_CODES,
            payload[native_at:native_at + 64],
        )

    def test_keyboard_is_the_approved_name_layout_plus_question_and_bang(self):
        raw = rescue_presentation.english_keyboard_map(self.prerequisite)
        rows = tuple(raw[index:index + 20] for index in range(0, len(raw), 20))
        blank = name6.english.ENGLISH_CODES[" "]
        self.assertEqual(bytes((blank,) * 5), rows[2][1:6])
        self.assertEqual(
            name6.english.encode("?!"),
            rows[12][17:19],
        )
        self.assertEqual(
            name6.character_positions() + ((3, 16), (3, 17)),
            rescue_presentation.character_positions(),
        )

    def test_navigation_reaches_every_symbol_and_no_removed_control(self):
        records = _records(
            rescue_presentation.english_navigation_table(self.prerequisite)
        )
        reached = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for neighbor in records[node][:4]:
                self.assertNotIn(neighbor, rescue_presentation.BLANK_NODES)
                if neighbor not in reached:
                    reached.add(neighbor)
                    pending.append(neighbor)
        self.assertEqual(rescue_presentation.ACTIVE_NODES, reached)
        self.assertEqual(
            (3, 16),
            rescue_presentation.character_positions()[
                rescue_presentation.QUESTION_NODE
            ],
        )
        self.assertEqual(
            (3, 17),
            rescue_presentation.character_positions()[
                rescue_presentation.EXCLAMATION_NODE
            ],
        )

    def test_every_visible_character_maps_to_its_native_six_bit_symbol(self):
        for node, character in enumerate(rescue_password.LOCALIZED_ALPHABET):
            with self.subTest(node=node, character=character):
                self.assertEqual(
                    rescue_password.NATIVE_ALPHABET_CODES[node:node + 1],
                    rescue_password.delocalize_password(character),
                )

    def test_install_redirects_all_guarded_routes_and_private_graph(self):
        output = rescue_presentation.install(self.prerequisite)
        for bank, address, target in (
            (
                rescue_presentation.PASSWORD_CACHE_BANK,
                rescue_presentation.PASSWORD_CACHE_ADDRESS,
                rescue_presentation.PASSWORD_CACHE_WRAPPER,
            ),
            (
                rescue_presentation.INPUT_HOOK_BANK,
                rescue_presentation.INPUT_HOOK_ADDRESS,
                rescue_presentation.INPUT_ADDRESS,
            ),
            (
                rescue_presentation.SCREEN_HOOK_BANK,
                rescue_presentation.SCREEN_HOOK_ADDRESS,
                rescue_presentation.SCREEN_ADDRESS,
            ),
        ):
            at = extract.file_offset(bank, address)
            self.assertEqual(
                rescue_presentation._far_call(
                    rescue_presentation.RUNTIME_BANK, target
                ),
                output[at:at + 8],
            )
        pointer = extract.file_offset(
            rescue_presentation.NAVIGATION_BANK,
            rescue_presentation.NAVIGATION_POINTER_ADDRESS,
        )
        self.assertEqual(
            rescue_presentation.NAVIGATION_POINTER_PATCH,
            output[pointer:pointer + 2],
        )
        runtime_at = extract.file_offset(
            rescue_presentation.RUNTIME_BANK,
            rescue_presentation.RUNTIME_ADDRESS,
        )
        payload = rescue_presentation.runtime_payload(output)
        self.assertEqual(payload, output[runtime_at:runtime_at + len(payload)])
        loop_call = extract.file_offset(
            rescue_presentation.INPUT_LOOP_BANK,
            rescue_presentation.INPUT_LOOP_CALL_ADDRESS,
        )
        self.assertEqual(
            bytes(
                (
                    0xCD,
                    rescue_presentation.INPUT_LOOP_TRAMPOLINE_ADDRESS & 0xFF,
                    rescue_presentation.INPUT_LOOP_TRAMPOLINE_ADDRESS >> 8,
                )
            ),
            output[loop_call:loop_call + 3],
        )
        trampoline = extract.file_offset(
            rescue_presentation.INPUT_LOOP_BANK,
            rescue_presentation.INPUT_LOOP_TRAMPOLINE_ADDRESS,
        )
        self.assertEqual(
            rescue_presentation.INPUT_LOOP_TRAMPOLINE_PATCH,
            output[
                trampoline:
                trampoline + len(rescue_presentation.INPUT_LOOP_TRAMPOLINE_PATCH)
            ],
        )

    def test_install_is_idempotent(self):
        once = rescue_presentation.install(self.prerequisite)
        twice = rescue_presentation.install(once)
        self.assertEqual(once, twice)

    def test_hooks_pointer_and_reserved_bank_are_fail_closed(self):
        locations = (
            (
                rescue_presentation.PASSWORD_CACHE_BANK,
                rescue_presentation.PASSWORD_CACHE_ADDRESS,
            ),
            (
                rescue_presentation.INPUT_HOOK_BANK,
                rescue_presentation.INPUT_HOOK_ADDRESS,
            ),
            (
                rescue_presentation.SCREEN_HOOK_BANK,
                rescue_presentation.SCREEN_HOOK_ADDRESS,
            ),
            (
                rescue_presentation.INPUT_LOOP_BANK,
                rescue_presentation.INPUT_LOOP_CALL_ADDRESS,
            ),
            (
                rescue_presentation.INPUT_LOOP_BANK,
                rescue_presentation.INPUT_LOOP_TRAMPOLINE_ADDRESS,
            ),
            (
                rescue_presentation.NAVIGATION_BANK,
                rescue_presentation.NAVIGATION_POINTER_ADDRESS,
            ),
            (
                rescue_presentation.RUNTIME_BANK,
                rescue_presentation.RUNTIME_ADDRESS,
            ),
        )
        for bank, address in locations:
            with self.subTest(location=extract.location(bank, address)):
                damaged = bytearray(self.prerequisite)
                damaged[extract.file_offset(bank, address)] ^= 1
                with self.assertRaises(
                    rescue_presentation.RescuePresentationError
                ):
                    rescue_presentation.install(damaged)

    def test_checked_in_code_matches_rgbds_source_when_available(self):
        if not shutil.which("rgbasm") or not shutil.which("rgblink"):
            self.skipTest("RGBDS is not installed")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            obj = directory / "rescue-presentation.o"
            linked = directory / "rescue-presentation.gb"
            subprocess.run(
                [
                    "rgbasm", "-Wall", "-Wextra", "-o", str(obj),
                    str(ROOT / "tools" / "rescue_presentation.asm"),
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
        start = rescue_presentation.RUNTIME_BANK * 0x4000
        self.assertEqual(
            rescue_presentation.ASSEMBLED_CODE,
            raw[start:start + len(rescue_presentation.ASSEMBLED_CODE)],
        )


class LiveRescueEditorRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        state = ROOT / ENTRY_FIXTURE["japanese_editor_state"]["path"]
        if not source.is_file() or not state.is_file():
            raise unittest.SkipTest("matching ROM and live Rescue failure are required")
        if sha1(source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.fields = mesen_state.load_fields(state)
        cls.ram = cls.fields["cartRam"]
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "rescue-repair.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(source),
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
                "could not build Rescue repair fixture:\n"
                + built.stdout + built.stderr
            )
        cls.localized_rom = cls.localized.read_bytes()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _pyboy(self):
        pyboy = self.PyBoy(
            str(self.localized),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        for _frame in range(120):
            pyboy.tick()
        return pyboy

    def _invoke(self, pyboy, bank, address, c=0):
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
        pyboy.memory[0xFFFF] = old_ie | 1
        pyboy.memory[0xFF0F] = 0
        pyboy.register_file.B = 0
        pyboy.register_file.C = c
        pyboy.register_file.SP = 0xC6F0
        pyboy.register_file.PC = 0xC700
        for _frame in range(120):
            pyboy.tick()
            if pyboy.memory[0xC7FF] == 0x42:
                break
        pyboy.memory[0xFFFF] = old_ie
        self.assertEqual(0x42, pyboy.memory[0xC7FF])

    def test_exact_live_japanese_editor_state_repairs_to_full_english_map(self):
        work_ram = self.fields["workRam"]
        self.assertEqual(
            (0x08, 0x00, 0x00, 0x00, 0x0D),
            tuple(work_ram[index] for index in (0x195, 0x14E, 0x14F, 0x152, 0x153)),
        )
        video_ram = self.fields["videoRam"]
        native_map = b"".join(
            video_ram[0x1840 + row * 32:0x1840 + row * 32 + 20]
            for row in range(16)
        )
        self.assertEqual(
            "36a4d9d6488f0ee4be1b67467300db6c3dc9d7fb",
            sha1(native_map).hexdigest(),
        )

        pyboy = self._pyboy()
        try:
            pyboy.memory[0xFF4F] = 0
            for row in range(16):
                for column in range(20):
                    pyboy.memory[0x9840 + row * 32 + column] = native_map[
                        row * 20 + column
                    ]
            for address, value in (
                (0xC195, 0x08),
                (0xC14E, 0x00),
                (0xC14F, 0x00),
                (0xC152, 0x00),
                (0xC153, 0x0D),
            ):
                pyboy.memory[address] = value

            self._invoke(
                pyboy,
                rescue_presentation.RUNTIME_BANK,
                rescue_presentation.REPAIR_ACTIVE_EDITOR_ADDRESS,
                c=self.fields["cpu.c"][0],
            )

            self.assertEqual(0x08, pyboy.memory[0xC195])
            self.assertEqual(rescue_presentation.NAVIGATION_TYPE, pyboy.memory[0xC14E])
            self.assertEqual(0x0D, pyboy.memory[0xC153])
            pyboy.memory[0xFF4F] = 0
            repaired_map = bytes(
                pyboy.memory[0x9840 + row * 32 + column]
                for row in range(16)
                for column in range(20)
            )
            self.assertEqual(
                rescue_presentation.english_keyboard_map(self.localized_rom),
                repaired_map,
            )
        finally:
            pyboy.stop(save=False)


class MesenRescuePresentationRouteTests(unittest.TestCase):
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

        cls.source = ROOT / ROM_NAME
        if not cls.source.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "rescue-presentation.gbc"
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
                "could not build rescue presentation fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _checked_state(self, row):
        state = ROOT / row["path"]
        if not state.is_file():
            self.skipTest("required rescue state is unavailable")
        self.assertEqual(row["sha1"], sha1(state.read_bytes()).hexdigest())
        return state

    def test_rankings_route_renders_english_and_preserves_native_protocol(self):
        row = REQUESTER_FIXTURE["ranking_state"]
        state = self._checked_state(row)
        env = os.environ.copy()
        env["GB2_RESCUE_RANKINGS_MSS"] = str(state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_rescue_requester_route.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS localized SOS screen=7F6D7FB9 "
            "buffer=6F7359324D4E6932506F73716DFF "
            "diary=3EC1C2C48F7F09080201",
            output,
        )

    def test_password_route_enters_english_code_as_native_and_submits_it(self):
        state = self._checked_state(ENTRY_FIXTURE["password_menu_state"])
        editor = ENTRY_FIXTURE["localized_editor"]
        vector = ENTRY_FIXTURE["public_sos_vector"]
        characters, confirm = _input_sequences(
            self.localized.read_bytes(), vector["localized"]
        )
        env = os.environ.copy()
        env.update(
            {
                "GB2_RESCUE_ENTRY_MSS": str(state),
                "GB2_RESCUE_EXPECTED_EDITOR_SCREEN": editor["screen_checksum"],
                "GB2_RESCUE_EXPECTED_NATIVE": vector["native_hex"],
                "GB2_RESCUE_CHARACTER_INPUTS": ",".join(characters),
                "GB2_RESCUE_CONFIRM_INPUTS": ",".join(confirm),
                "GB2_RESCUE_EXPECTED_RESULT_SCREEN": vector[
                    "validation_response_screen_checksum"
                ],
                "GB2_RESCUE_EXPECTED_POST_NATIVE": vector[
                    "post_validation_buffer_hex"
                ],
            }
        )
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_rescue_entry_route.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=40,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "rescue code entered",
            output,
        )
        self.assertIn(
            "buffer=" + vector["native_hex"] + "FF",
            output,
        )
        self.assertIn(
            "PASS rescue input submitted",
            output,
        )

    def test_revival_response_resumes_requester_and_generates_thank_you_code(self):
        state = self._checked_state(REQUESTER_FIXTURE["sos_state"])
        row = REQUESTER_FIXTURE["revival_response_test"]
        revival = row["revival"]
        thank_you = row["thank_you"]
        characters, confirm = _input_sequences(
            self.localized.read_bytes(), revival["localized_password"]
        )
        env = os.environ.copy()
        env.update(
            {
                "GB2_REVIVAL_REQUESTER_MSS": str(state),
                "GB2_REVIVAL_EXPECTED_NATIVE": revival["native_hex"],
                "GB2_REVIVAL_CHARACTER_INPUTS": ",".join(characters),
                "GB2_REVIVAL_CONFIRM_INPUTS": ",".join(confirm),
                "GB2_REVIVAL_EXPECTED_EDITOR_SCREEN": row[
                    "editor_screen_checksum"
                ],
                "GB2_REVIVAL_EXPECTED_ENTERED_SCREEN": revival[
                    "entered_screen_checksum"
                ],
                "GB2_REVIVAL_EXPECTED_SUCCESS_SCREEN": revival[
                    "success_screen_checksum"
                ],
                "GB2_REVIVAL_EXPECTED_THANK_YOU_SCREEN": thank_you[
                    "screen_checksum"
                ],
                "GB2_REVIVAL_EXPECTED_THANK_YOU_NATIVE": thank_you[
                    "native_hex"
                ],
            }
        )
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_rescue_revival_route.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=40,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn("Revival code entered", output)
        self.assertIn(
            "PASS Revival response accepted and Thank-You Password generated",
            output,
        )

    def test_captured_japanese_editor_is_repaired_by_live_input_loop(self):
        state = self._checked_state(ENTRY_FIXTURE["japanese_editor_state"])
        editor = ENTRY_FIXTURE["localized_editor"]
        env = os.environ.copy()
        env.update(
            {
                "GB2_RESCUE_FAILURE_MSS": str(state),
                "GB2_RESCUE_EXPECTED_EDITOR_SCREEN": editor["screen_checksum"],
            }
        )
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_rescue_failure_repair.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn("captured Japanese rescue editor loaded", output)
        self.assertIn("installed rescue loop repaired editor", output)
        self.assertIn(
            "PASS captured rescue editor repaired naturally",
            output,
        )

if __name__ == "__main__":
    unittest.main()
