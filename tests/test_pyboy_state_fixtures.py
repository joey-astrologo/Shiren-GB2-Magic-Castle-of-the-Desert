import io
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue


ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class PyBoyStateFixtureMigrationTests(unittest.TestCase):
    def test_every_archived_source_state_has_a_native_pyboy_fixture(self):
        sources = sorted((ROOT / "SaveStates").glob("*." + "mss"))
        self.assertTrue(sources, "the checked-in reproduction states are missing")
        missing = [source.with_suffix(".state") for source in sources
                   if not source.with_suffix(".state").is_file()]
        self.assertEqual([], missing)

    def test_python_tests_and_fixture_manifests_use_only_pyboy_states(self):
        forbidden = {
            "." + "mss": "legacy save-state path",
            "mesen" + "_state": "legacy state parser",
            "--test" + "runner": "legacy emulator runner",
            "which(\"" + "Mesen" + "\")": "legacy emulator discovery",
        }
        offenders = []
        paths = sorted((ROOT / "tests").glob("*.py"))
        paths += sorted((ROOT / "tests" / "fixtures").glob("*.json"))
        for path in paths:
            if path == Path(__file__):
                continue
            text = path.read_text(encoding="utf-8")
            for needle, description in forbidden.items():
                if needle in text:
                    offenders.append(
                        f"{path.relative_to(ROOT)}: {description} ({needle})"
                    )
        self.assertEqual([], offenders)

    def test_no_mesen_only_route_scripts_remain_in_the_test_suite(self):
        legacy = sorted((ROOT / "tests").glob("mesen_*.lua"))
        self.assertEqual([], legacy)

    def test_every_native_fixture_loads_and_advances_in_pyboy(self):
        if not ROM.is_file():
            raise unittest.SkipTest("matching source ROM is required")
        try:
            PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        states = sorted((ROOT / "SaveStates").glob("*.state"))
        self.assertTrue(states, "no native PyBoy state fixtures were found")
        for state in states:
            with self.subTest(state=state.name):
                pyboy = PyBoy(
                    str(ROM),
                    window="null",
                    sound_emulated=False,
                    ram_file=io.BytesIO(bytes(0x8000)),
                )
                pyboy.set_emulation_speed(0)
                try:
                    with state.open("rb") as handle:
                        pyboy.load_state(handle)
                    initial_frame = pyboy.frame_count
                    for _ in range(3):
                        pyboy.tick()
                    self.assertEqual(initial_frame + 3, pyboy.frame_count)
                    self.assertNotEqual(0, pyboy.register_file.PC)
                finally:
                    pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
