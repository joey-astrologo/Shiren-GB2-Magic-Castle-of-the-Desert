from hashlib import sha1
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import capture_dialogue
import extract
import pyboy_fixtures
import pyboy_route
import pyboy_state
import translate_spells


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "big_moai.json").read_text(encoding="utf-8")
)


class BigMoaiFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state_path = ROOT / FIXTURE["locked_state"]["path"]
        cls.work_ram = pyboy_state.work_ram(cls.state_path)
        cls.cart_ram = pyboy_state.cart_ram(cls.state_path)

    def test_user_fixture_hash_and_locked_state_are_frozen(self):
        self.assertEqual(
            FIXTURE["locked_state"]["sha1"],
            sha1(self.state_path.read_bytes()).hexdigest(),
        )
        work_ram = self.work_ram
        stage, shadow = FIXTURE["unlock"]["work_ram_offsets"]
        self.assertEqual(FIXTURE["locked_state"]["active_stage"], work_ram[stage])
        self.assertEqual(FIXTURE["locked_state"]["stage_shadow"], work_ram[shadow])
        self.assertEqual(bytes((0xFF,)) * 20, work_ram[0x12C1:0x12C1 + 20])

    def test_story_stage_is_present_in_both_native_save_mirrors(self):
        cart_ram = self.cart_ram
        expected = bytes((
            FIXTURE["locked_state"]["active_stage"],
            FIXTURE["locked_state"]["stage_shadow"],
        ))
        for offset in FIXTURE["locked_state"]["mirrored_sram_stage_offsets"]:
            with self.subTest(offset=offset):
                self.assertEqual(expected, cart_ram[offset:offset + 2])
                self.assertEqual(sum(expected) & 0xFF, cart_ram[offset + 2])

    def test_native_event_gate_matches_the_discovered_minimum_stage(self):
        rom = (ROOT / ROM_NAME).read_bytes()
        at = extract.file_offset(0x74, 0x5CEF)
        # opcode $60 branches to $5CF7 when C3EF >= $09; otherwise the next
        # packet is group $6A index $0D, the exact locked response.
        self.assertEqual(
            bytes.fromhex("6009F75C160D6A"),
            rom[at:at + 7],
        )
        self.assertEqual(
            FIXTURE["unlock"]["minimum_stage"],
            rom[at + 1],
        )

    def test_pyboy_unlock_owns_only_the_two_measured_progression_bytes(self):
        self.assertEqual(
            FIXTURE["unlock"]["work_ram_offsets"][0],
            pyboy_fixtures.BIG_MOAI_STAGE_ADDRESS - 0xC000,
        )
        self.assertEqual(
            FIXTURE["unlock"]["work_ram_offsets"][1],
            pyboy_fixtures.BIG_MOAI_STAGE_SHADOW_ADDRESS - 0xC000,
        )
        self.assertEqual(
            FIXTURE["unlock"]["minimum_stage"],
            pyboy_fixtures.BIG_MOAI_MINIMUM_STAGE,
        )

    def test_wish_and_fortune_grass_contracts_are_exact(self):
        route = FIXTURE["wish_route"]
        self.assertEqual(route["code"], translate_spells.spell_code(route["runtime_index"]))
        self.assertEqual(bytes.fromhex(route["encoded_hex"]), english.encode(route["code"]))

        glossary = ROOT / "script" / "organized" / "glossary.tsv"
        row = next(
            line.split("\t")
            for line in glossary.read_text(encoding="utf-8").splitlines()[1:]
            if f"g004[{route['reward_item_id']:03d}]" in line
        )
        self.assertEqual(route["reward_item"], row[-1])


class BigMoaiPyBoyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = ROOT / ROM_NAME
        cls.state = ROOT / FIXTURE["locked_state"]["path"]
        if not cls.rom.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("original ROM and Big Moai state are required")
        if sha1(cls.rom.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "shiren-gb2-big-moai.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(cls.rom),
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
                "could not build Big Moai fixture:\n" + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _pyboy(self):
        return pyboy_route.start(self.PyBoy, self.localized, self.state)

    @staticmethod
    def _work_byte(pyboy, offset):
        if offset < 0x1000:
            return pyboy.memory[0xC000 + offset]
        bank = offset // 0x1000
        old_bank = pyboy.memory[0xFF70]
        try:
            pyboy.memory[0xFF70] = bank
            return pyboy.memory[0xD000 + offset % 0x1000]
        finally:
            pyboy.memory[0xFF70] = old_bank

    def test_user_state_reproduces_the_real_locked_npc_branch(self):
        pyboy = self._pyboy()
        seen = []
        try:
            def at_text(_context=None):
                if pyboy.register_file.A == 0x6A:
                    seen.append(pyboy.register_file.C)

            pyboy.hook_register(0, 0x1F58, at_text, None)
            pyboy_route.run_frames(pyboy, 150, actions=((120, "a"),))
            self.assertEqual(6, pyboy.memory[0xC3EF])
            self.assertEqual(6, pyboy.memory[0xC3F0])
            self.assertIn(FIXTURE["unlock"]["locked_dialogue"]["index"], seen)
            self.assertNotEqual(3, pyboy.memory[0xC195])
        finally:
            pyboy.stop(save=False)

    def test_distributable_helper_changes_exactly_the_minimum_stage_pair(self):
        pyboy = self._pyboy()
        try:
            before = bytes(pyboy.memory[0xC000:0xC800])
            changed, old_stage = pyboy_fixtures.unlock_big_moai(pyboy)
            after = bytes(pyboy.memory[0xC000:0xC800])
            differences = [
                index for index, pair in enumerate(zip(before, after))
                if pair[0] != pair[1]
            ]
            self.assertTrue(changed)
            self.assertEqual(6, old_stage)
            self.assertEqual([0x3EF, 0x3F0], differences)
            self.assertEqual((9, 9), (pyboy.memory[0xC3EF], pyboy.memory[0xC3F0]))
        finally:
            pyboy.stop(save=False)

    def test_wish_runs_through_the_real_npc_editor_and_awards_fortune_grass(self):
        pyboy = self._pyboy()
        events = []
        editor_at = None
        reward_at = None
        sequence = (
            "left", "left", "left", "a",
            "up", "down", "down", "left", "left", "a",
            "down", "down", "a",
            "up", "up", "left", "a", "a",
        )
        try:
            pyboy_fixtures.unlock_big_moai(pyboy)

            def at_text(_context=None):
                nonlocal reward_at
                if pyboy.register_file.A != 0x6A:
                    return
                index = pyboy.register_file.C
                events.append(index)
                if index == FIXTURE["wish_route"]["reward_dialogue"]["index"]:
                    reward_at = frame

            pyboy.hook_register(0, 0x1F58, at_text, None)
            for frame in range(3001):
                if editor_at is None and (
                    pyboy.memory[0xC195] == 3
                    and pyboy.memory[0xC14F] == 0
                    and pyboy.memory[0xC152] == 0
                ):
                    editor_at = frame

                if frame in (120, 420, 720):
                    pyboy_route.press(pyboy, "a")
                if editor_at is not None:
                    dynamic = {
                        editor_at + 75: "up",
                        editor_at + 105: "down",
                    }
                    for index, button in enumerate(sequence):
                        dynamic[editor_at + 135 + index * 15] = button
                    if frame in dynamic:
                        pyboy_route.press(pyboy, dynamic[frame])
                if reward_at is not None:
                    if frame == reward_at + 180 or frame == reward_at + 300:
                        pyboy_route.press(pyboy, "a")
                pyboy.tick()
                if FIXTURE["wish_route"]["post_reward_dialogue"]["index"] in events:
                    break

            self.assertIsNotNone(editor_at)
            self.assertIn(
                FIXTURE["wish_route"]["valid_dialogue"]["index"], events
            )
            self.assertIn(
                FIXTURE["wish_route"]["reward_dialogue"]["index"], events
            )
            self.assertIn(
                FIXTURE["wish_route"]["post_reward_dialogue"]["index"], events
            )
            inventory = [self._work_byte(pyboy, 0x12C1 + slot) for slot in range(20)]
            objects = [object_id for object_id in inventory if object_id != 0xFF]
            self.assertTrue(objects)
            items = [
                self._work_byte(pyboy, 0x2482 + object_id * 8)
                for object_id in objects
            ]
            self.assertIn(FIXTURE["wish_route"]["reward_item_id"], items)
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
