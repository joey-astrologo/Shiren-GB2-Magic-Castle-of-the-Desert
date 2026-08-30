from hashlib import sha1
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import extract
import mesen_state
import translate_spells


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "big_moai.json").read_text(encoding="utf-8")
)


class BigMoaiFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state_path = ROOT / FIXTURE["locked_state"]["path"]
        cls.fields = mesen_state.load_fields(cls.state_path)
        cls.helper = (ROOT / "tools" / "mesen_unlock_big_moai.lua").read_text(
            encoding="utf-8"
        )

    def helper_constant(self, name):
        match = re.search(
            r"^local %s = (0x[0-9A-F]+|[0-9]+)$" % re.escape(name),
            self.helper,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, name)
        return int(match.group(1), 0)

    def test_user_fixture_hash_and_locked_state_are_frozen(self):
        self.assertEqual(
            FIXTURE["locked_state"]["sha1"],
            sha1(self.state_path.read_bytes()).hexdigest(),
        )
        work_ram = self.fields["workRam"]
        stage, shadow = FIXTURE["unlock"]["work_ram_offsets"]
        self.assertEqual(FIXTURE["locked_state"]["active_stage"], work_ram[stage])
        self.assertEqual(FIXTURE["locked_state"]["stage_shadow"], work_ram[shadow])
        self.assertEqual(bytes((0xFF,)) * 20, work_ram[0x12C1:0x12C1 + 20])

    def test_story_stage_is_present_in_both_native_save_mirrors(self):
        cart_ram = self.fields["cartRam"]
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

    def test_helper_owns_only_the_two_measured_progression_bytes(self):
        self.assertEqual(
            FIXTURE["unlock"]["work_ram_offsets"][0],
            self.helper_constant("STAGE_OFFSET"),
        )
        self.assertEqual(
            FIXTURE["unlock"]["work_ram_offsets"][1],
            self.helper_constant("STAGE_SHADOW_OFFSET"),
        )
        self.assertEqual(
            FIXTURE["unlock"]["minimum_stage"],
            self.helper_constant("MINIMUM_STAGE"),
        )
        self.assertNotIn("cartRam", self.helper)
        self.assertNotIn("gameboyMemory", self.helper)
        self.assertEqual(1, self.helper.count("emu.write"))
        self.assertIn("if stage ~= shadow then", self.helper)

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


class BigMoaiLiveTests(unittest.TestCase):
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
        cls.rom = ROOT / ROM_NAME
        cls.state = ROOT / FIXTURE["locked_state"]["path"]
        if not cls.rom.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("original ROM and Big Moai state are required")
        if sha1(cls.rom.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

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

    def run_mesen(self, script, extra_env=None, timeout=30):
        env = os.environ.copy()
        env["GB2_BIG_MOAI_MSS"] = str(self.state)
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / script),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        return output

    def test_user_state_reproduces_the_real_locked_npc_branch(self):
        output = self.run_mesen(
            "tests/mesen_big_moai_locked.lua",
            {"GB2_BIG_MOAI_PROMPT_SCREEN": FIXTURE["unlock"]["prompt_screen_fnv1a"]},
        )
        self.assertIn(
            "PASS big-moai-locked stage=06/06 dialogue=6A:0D",
            output,
        )

    def test_distributable_helper_changes_exactly_the_minimum_stage_pair(self):
        output = self.run_mesen("tools/mesen_unlock_big_moai.lua")
        self.assertIn(
            "PASS big-moai-unlock stage=09/09 changed=03EF,03F0",
            output,
        )

    def test_wish_runs_through_the_real_npc_editor_and_awards_fortune_grass(self):
        output = self.run_mesen(
            "tests/mesen_big_moai_live.lua",
            {
                "GB2_BIG_MOAI_LIBRARY": "1",
                "GB2_BIG_MOAI_HELPER": str(ROOT / "tools" / "mesen_unlock_big_moai.lua"),
                "GB2_BIG_MOAI_PROMPT_SCREEN": FIXTURE["unlock"]["prompt_screen_fnv1a"],
                "GB2_BIG_MOAI_EDITOR_SCREEN": FIXTURE["wish_route"]["editor_screen_fnv1a"],
                "GB2_BIG_MOAI_DELETE_SCREEN": FIXTURE["wish_route"]["delete_screen_fnv1a"],
                "GB2_BIG_MOAI_OK_SCREEN": FIXTURE["wish_route"]["ok_screen_fnv1a"],
                "GB2_BIG_MOAI_REWARD_SCREEN": FIXTURE["wish_route"]["reward_screen_fnv1a"],
            },
        )
        self.assertIn(
            "PASS big-moai-live code=WISH item=70 object=03 post=1A",
            output,
        )


if __name__ == "__main__":
    unittest.main()
