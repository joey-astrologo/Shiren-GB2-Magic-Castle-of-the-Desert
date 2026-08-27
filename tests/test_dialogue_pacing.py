from hashlib import sha1
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import dialogue_pacing
import extract


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class DialoguePacingUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_patch_is_exact_idempotent_and_fail_closed(self):
        start, end = dialogue_pacing.owned_range()
        self.assertEqual(dialogue_pacing.ORIGINAL_BYPASS, self.rom[start:end])
        patched = dialogue_pacing.install(self.rom)
        self.assertTrue(dialogue_pacing.verify(patched))
        self.assertEqual(patched, dialogue_pacing.install(patched))

        damaged = bytearray(self.rom)
        damaged[start] ^= 1
        with self.assertRaisesRegex(
            dialogue_pacing.DialoguePacingError, "page auto-bypass"
        ):
            dialogue_pacing.install(damaged)

    def test_only_audited_branch_and_checksums_change(self):
        patched = dialogue_pacing.install(self.rom)
        changed = {
            index
            for index, (before, after) in enumerate(zip(self.rom, patched))
            if before != after
        }
        start, end = dialogue_pacing.owned_range()
        allowed = set(range(start, end)) | {
            0x014D,
            0x014E,
            0x014F,
        }
        self.assertTrue(changed <= allowed)


class DialoguePacingPyBoyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        if sha1(cls.path.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def test_auto_mode_cannot_discard_an_explicit_page(self):
        patched = dialogue_pacing.install(self.path.read_bytes())
        page_hits = []
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "dialogue-pacing.gbc"
            path.write_bytes(patched)
            pyboy = self.PyBoy(str(path), window="null", sound_emulated=False)
            pyboy.set_emulation_speed(0)

            def at_page(_context=None):
                # Reproduce the affected story-mode condition at a real FB in
                # group 35. The patched handler must ignore this bypass flag.
                source_bank = pyboy.memory[0xC4DB]
                source_pointer = (
                    pyboy.memory[0xC4DC] | (pyboy.memory[0xC4DD] << 8)
                )
                if source_bank == 195 and 0x562F <= source_pointer < 0x56DA:
                    pyboy.memory[0xC4D9] = 1
                    page_hits.append(pyboy.frame_count)

            pyboy.hook_register(0, 0x3751, at_page, None)
            try:
                capture_dialogue.run_to_dialogue(pyboy)
                self.assertEqual(1, len(page_hits))
                for _ in range(300):
                    pyboy.tick()
                self.assertEqual([page_hits[0]], page_hits)
                self.assertEqual(0, pyboy.memory[0xC4D9])

                # The handler still requires the normal release-then-fresh-A
                # transition; one deliberate press advances it.
                pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                for _ in range(300):
                    pyboy.tick()
                self.assertGreater(len(page_hits), 1)
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
