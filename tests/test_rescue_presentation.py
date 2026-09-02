from collections import deque
from hashlib import sha1
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
import extract
import name6
import rescue_password
import rescue_presentation
import capture_dialogue
import pyboy_route
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
            (
                rescue_presentation.SCREEN_HOOK_BANK,
                rescue_presentation.PREMODE_SCREEN_HOOK_ADDRESS,
                rescue_presentation.PREMODE_SCREEN_ADDRESS,
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
        hardware_b = extract.file_offset(
            rescue_presentation.HARDWARE_B_BANK,
            rescue_presentation.HARDWARE_B_HOOK_ADDRESS,
        )
        self.assertEqual(
            rescue_presentation.HARDWARE_B_HOOK_PATCH,
            output[
                hardware_b:
                hardware_b + len(rescue_presentation.HARDWARE_B_HOOK_PATCH)
            ],
        )

    def test_primary_screen_wrapper_uses_incoming_mode_not_stale_wram(self):
        start = (
            rescue_presentation.SCREEN_ADDRESS
            - rescue_presentation.RUNTIME_ADDRESS
        )
        wrapper = rescue_presentation.ASSEMBLED_CODE[start:start + 16]
        self.assertEqual(0x79, wrapper[0])  # ld a,c
        self.assertIn(bytes.fromhex("EA95C1C5"), wrapper)  # publish mode; push bc

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
                rescue_presentation.SCREEN_HOOK_BANK,
                rescue_presentation.PREMODE_SCREEN_HOOK_ADDRESS,
            ),
            (
                rescue_presentation.HARDWARE_B_BANK,
                rescue_presentation.HARDWARE_B_HOOK_ADDRESS,
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


class PyBoyRescuePresentationRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        if not cls.source.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

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
        pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
        try:
            pyboy_route.run_frames(
                pyboy,
                720,
                actions=((100, "select"), (240, "a"), (400, "left"), (460, "a")),
            )
            self.assertEqual(
                bytes.fromhex("6F7359324D4E6932506F73716DFF"),
                bytes(pyboy.memory[0xC16D:0xC17B]),
            )
            self.assertEqual(
                bytes.fromhex("3EC1C2C48F7F09080201"),
                bytes(pyboy.memory[0xC27D:0xC287]),
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

    def test_password_route_enters_english_code_as_native_and_submits_it(self):
        state = self._checked_state(ENTRY_FIXTURE["password_menu_state"])
        editor = ENTRY_FIXTURE["localized_editor"]
        vector = ENTRY_FIXTURE["public_sos_vector"]
        characters, confirm = _input_sequences(
            self.localized.read_bytes(), vector["localized"]
        )
        pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
        pyboy.memory[0xC195] = 0
        editor_at = None
        input_at = None
        confirm_at = None
        try:
            for frame in range(5201):
                if editor_at is None and (
                    pyboy.memory[0xC195] == 8
                    and pyboy.memory[0xC14E] == 0xF5
                ):
                    editor_at = frame
                    input_at = frame + 400

                fixed = {90: "a", 390: "a", 720: "a", 1120: "a", 3200: "a"}
                if frame in fixed:
                    pyboy_route.press(pyboy, fixed[frame])
                if input_at is not None:
                    for index, button in enumerate(characters):
                        if frame == input_at + index * 15:
                            pyboy_route.press(pyboy, button)
                    done = input_at + len(characters) * 15 + 30
                    if confirm_at is None and frame >= done:
                        expected = bytes.fromhex(vector["native_hex"] + "FF")
                        if bytes(pyboy.memory[0xC16D:0xC17B]) == expected:
                            self.assertEqual(0x0C, pyboy.memory[0xC152])
                            confirm_at = frame + 60
                if confirm_at is not None:
                    for index, button in enumerate(confirm):
                        if frame == confirm_at + index * 15:
                            pyboy_route.press(pyboy, button)
                    if frame >= confirm_at + len(confirm) * 15 + 420:
                        break
                pyboy.tick()

            self.assertIsNotNone(editor_at)
            self.assertIsNotNone(confirm_at)
            self.assertEqual(
                bytes.fromhex(vector["post_validation_buffer_hex"]),
                bytes(pyboy.memory[0xC16D:0xC17B]),
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

    def test_revival_response_resumes_requester_and_generates_thank_you_code(self):
        state = self._checked_state(REQUESTER_FIXTURE["sos_state"])
        row = REQUESTER_FIXTURE["revival_response_test"]
        revival = row["revival"]
        thank_you = row["thank_you"]
        characters, confirm = _input_sequences(
            self.localized.read_bytes(), revival["localized_password"]
        )
        pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
        editor_at = None
        confirm_at = None
        try:
            for frame in range(8201):
                if editor_at is None and (
                    pyboy.memory[0xC195] == 7
                    and pyboy.memory[0xC14E] == 0xF5
                    and pyboy.memory[0xC152] == 0
                ):
                    editor_at = frame
                fixed = {
                    120: "a", 360: "a", 600: "down",
                    660: "a", 780: "a", 1140: "a",
                }
                if frame in fixed:
                    pyboy_route.press(pyboy, fixed[frame], 2)
                if editor_at is not None:
                    start_at = editor_at + 180
                    for index, button in enumerate(characters):
                        if frame == start_at + index * 15:
                            pyboy_route.press(pyboy, button, 2)
                    done = start_at + len(characters) * 15 + 30
                    if confirm_at is None and frame >= done:
                        expected = bytes.fromhex(revival["native_hex"] + "FF")
                        if bytes(pyboy.memory[0xC16D:0xC17D]) == expected:
                            self.assertEqual(0x0E, pyboy.memory[0xC152])
                            self.assertEqual(0x4D, pyboy.memory[0xC14F])
                            confirm_at = frame + 60
                if confirm_at is not None:
                    for index, button in enumerate(confirm):
                        if frame == confirm_at + index * 15:
                            pyboy_route.press(pyboy, button, 2)
                    advance = confirm_at + len(confirm) * 15 + 480
                    if frame == advance:
                        pyboy_route.press(pyboy, "a", 2)
                    if frame >= confirm_at + len(confirm) * 15 + 780:
                        break
                pyboy.tick()

            self.assertIsNotNone(editor_at)
            self.assertIsNotNone(confirm_at)
            self.assertEqual(
                bytes.fromhex(thank_you["native_hex"] + "FF"),
                bytes(pyboy.memory[0xC16D:0xC17A]),
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

if __name__ == "__main__":
    unittest.main()
