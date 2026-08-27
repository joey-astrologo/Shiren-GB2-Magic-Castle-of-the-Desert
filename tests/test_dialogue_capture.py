import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import codec


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
CONTROL_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "control_dispatch.json").read_text()
)
SCRIPT_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "script_directory.json").read_text()
)


class DialogueCaptureIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        if hashlib.sha1(cls.path.read_bytes()).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def test_clean_boot_reaches_first_dialogue_fixture(self):
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        try:
            source_events = capture_dialogue.trace_to_dialogue(pyboy)
            self.assertEqual(
                SCRIPT_FIXTURE["opening_runtime_trace"],
                ["%d:$%04X" % event for event in source_events],
            )
            got = bytes(
                pyboy.memory[
                    0xC800:0xC800 + len(capture_dialogue.DIALOGUE_PREFIX)
                ]
            )
            self.assertEqual(capture_dialogue.DIALOGUE_PREFIX, got)

            # The captured box is waiting at FB. On the next dispatch, replace its
            # trailing FC with the fixture payload and let the unmodified renderer
            # consume it. The visited offsets measure arity independently of parse().
            probe = CONTROL_FIXTURE["runtime_probe"]
            payload = bytes.fromhex(probe["payload"])
            events = []
            armed = {"value": True}

            def at_dispatch(_context=None):
                if armed["value"]:
                    armed["value"] = False
                    for index, value in enumerate(payload):
                        pyboy.memory[0xC800 + index] = value
                    pyboy.memory[0xC4E0] = 0x00
                    pyboy.memory[0xC4E1] = 0xC8
                pointer = pyboy.memory[0xC4E0] | (pyboy.memory[0xC4E1] << 8)
                events.append(pointer - 0xC800)

            pyboy.hook_register(0, codec.DISPATCH_ENTRY, at_dispatch, None)
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
            for _ in range(300):
                pyboy.tick()
            expected = probe["dispatch_offsets"]
            self.assertEqual(expected, events[:len(expected)])
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
