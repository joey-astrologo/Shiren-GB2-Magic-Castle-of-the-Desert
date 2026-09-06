from hashlib import sha1
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import layout
import pyboy_route
import rescue_password


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "clear-campaign-password.state"
STATE_SHA1 = "ccbb4ac69d31ddc887128b17ac63952b234c785c"
NATIVE_PASSWORD = bytes.fromhex("40454976344E")
LOCALIZED_PASSWORD = "QVZ9Ee"
ROUTE_ACTIONS = ((0, "a"), (100, "a"), (200, "down"), (300, "a"))


class ClearCampaignPasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        if not cls.source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("clear-campaign ROM/state fixture is required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "clear-campaign.gbc"
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
                "could not build clear-campaign fixture:\n"
                + built.stdout
                + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def _capture_certificate(self, inject_expected_display=False):
        pyboy = pyboy_route.start(self.PyBoy, self.localized, STATE)
        localized = rescue_password.localized_display_codes(NATIVE_PASSWORD)
        saw_certificate = [False]

        def at_full_renderer(_context=None):
            staged = bytes(pyboy.memory[0xC800:0xC900])
            native_at = staged.find(NATIVE_PASSWORD)
            localized_at = staged.find(localized)
            if native_at < 0 and localized_at < 0:
                return
            saw_certificate[0] = True
            if inject_expected_display and native_at >= 0:
                for offset, value in enumerate(localized):
                    pyboy.memory[0xC800 + native_at + offset] = value

        try:
            pyboy.hook_register(*layout.FULL_RENDERER_ENTRY, at_full_renderer, None)
            pyboy_route.run_frames(pyboy, 400, ROUTE_ACTIONS)
            self.assertTrue(saw_certificate[0], "clear certificate did not render")
            pixels = tuple(pyboy.screen.image.getdata())
            native_buffer = bytes(pyboy.memory[0xC16D:0xC173])
            return pixels, native_buffer
        finally:
            pyboy.stop(save=False)

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_clear_certificate_pixels_use_localized_password_without_mutating_it(self):
        actual_pixels, actual_native = self._capture_certificate()
        expected_pixels, expected_native = self._capture_certificate(
            inject_expected_display=True
        )

        differences = [
            index
            for index, pair in enumerate(zip(actual_pixels, expected_pixels))
            if pair[0] != pair[1]
        ]
        self.assertFalse(
            differences,
            "clear-campaign password pixels differ from %s at (%d, %d)"
            % (
                LOCALIZED_PASSWORD,
                differences[0] % 160 if differences else -1,
                differences[0] // 160 if differences else -1,
            ),
        )
        self.assertEqual(NATIVE_PASSWORD, actual_native)
        self.assertEqual(NATIVE_PASSWORD, expected_native)


if __name__ == "__main__":
    unittest.main()
