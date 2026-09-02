from hashlib import sha1
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import english_font
import extract
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "multiple-unidentified-items.mss"
STATE_SHA1 = "f49e8004ca46af37d57d0ebf5c1ce10a7e8e5fcf"


class MultipleUnidentifiedNameTests(unittest.TestCase):
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
        source = ROOT / ROM_NAME
        if cls.mesen is None:
            raise unittest.SkipTest("Mesen test-runner executable is unavailable")
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("source ROM and multi-item state are required")
        original = source.read_bytes()
        if sha1(original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        result = extract.extract(original)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        widths = runtime_widths.analyze(
            english_font.install(original), result, translated
        )
        cls.localized = build.build_rom(
            original,
            translations.encoded_overrides(translated),
            runtime_contract=widths.contract,
        )[0]

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_two_canonical_names_receive_distinct_persistent_slots(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "multiple-unidentified.gbc"
            rom.write_bytes(self.localized)
            env = os.environ.copy()
            env["GB2_MULTIPLE_UNIDENTIFIED_MSS"] = str(STATE)
            result = subprocess.run(
                [
                    str(self.mesen),
                    "--testrunner",
                    "--enablestdout",
                    "--novideo",
                    "--noaudio",
                    str(rom),
                    str(ROOT / "tests" / "mesen_multiple_unidentified_names.lua"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, output[-12000:])
            self.assertIn("PASS canonical names own distinct slots", output)


if __name__ == "__main__":
    unittest.main()
