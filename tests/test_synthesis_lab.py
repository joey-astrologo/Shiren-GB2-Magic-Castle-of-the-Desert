from hashlib import sha1, sha256
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
ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "synthesis_lab.json").read_text(
        encoding="utf-8"
    )
)
SCRIPT = ROOT / "tools" / "mesen_spawn_synthesis_lab.lua"


def lua_bytes(source, name):
    match = re.search(
        rf"local {re.escape(name)}\s*=\s*\{{([^}}]+)\}}", source
    )
    if match is None:
        raise AssertionError(f"missing Lua table {name}")
    return bytes(int(value, 0) for value in re.findall(r"0x[0-9A-Fa-f]+|\d+", match.group(1)))


class SynthesisLabContractTests(unittest.TestCase):
    def test_helper_uses_the_reviewed_native_objects_and_sparse_pot_cells(self):
        source = SCRIPT.read_text(encoding="utf-8")
        objects = FIXTURE["objects"]
        self.assertEqual(bytes.fromhex(objects["base"]["record_hex"]), lua_bytes(source, "CUDGEL"))
        self.assertEqual(bytes.fromhex(objects["donor"]["record_hex"]), lua_bytes(source, "MINOTAUR_AXE"))
        self.assertEqual(bytes.fromhex(objects["pot"]["record_hex"]), lua_bytes(source, "SYNTHESIS_POT"))
        self.assertEqual(objects["pot"]["cell_offsets"], list(lua_bytes(source, "POT_CELL_OFFSETS")))
        self.assertIn("Synthesis Pot > Put In > Club", source)
        self.assertIn("repeat with Axe of the Minotaur", source)
        for key, checksum in FIXTURE["screens"].items():
            constant = {
                "initial_items_fnv1a": "ITEM_LIST_SCREEN",
                "pot_action_fnv1a": "ACTION_SCREEN",
                "put_in_picker_fnv1a": "PUT_PICKER_SCREEN",
                "after_base_fnv1a": "FIRST_PUT_SCREEN",
                "after_donor_fnv1a": "SECOND_PUT_SCREEN",
            }[key]
            self.assertIn(f"local {constant} = 0x{checksum}", source)


class MesenSynthesisLabTests(unittest.TestCase):
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
        cls.state = ROOT / FIXTURE["mesen_state"]["path"]
        if not cls.source.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        if sha1(cls.source.read_bytes()).hexdigest() != FIXTURE["source_rom_sha1"]:
            raise AssertionError("source ROM SHA-1 mismatch")
        raw = cls.state.read_bytes()
        if sha1(raw).hexdigest() != FIXTURE["mesen_state"]["sha1"]:
            raise AssertionError("synthesis-lab Mesen state SHA-1 mismatch")
        if sha256(raw).hexdigest() != FIXTURE["mesen_state"]["sha256"]:
            raise AssertionError("synthesis-lab Mesen state SHA-256 mismatch")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "synthesis-lab.gbc"
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
            raise AssertionError("could not build synthesis-lab fixture:\n" + built.stdout + built.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_native_pot_accepts_the_base_and_consumes_the_donor(self):
        env = os.environ.copy()
        env["GB2_SYNTHESIS_LAB_MSS"] = str(self.state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(SCRIPT),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        screens = FIXTURE["screens"]
        self.assertIn(
            "PASS synthesis-lab item=%s action=%s picker=%s first=%s second=%s break=weapon-bit-10"
            % (
                screens["initial_items_fnv1a"],
                screens["pot_action_fnv1a"],
                screens["put_in_picker_fnv1a"],
                screens["after_base_fnv1a"],
                screens["after_donor_fnv1a"],
            ),
            output,
        )
        self.assertIn("synthesis lab post-break seal=weapon-bit-10", output)


if __name__ == "__main__":
    unittest.main()
