from hashlib import sha1
import io
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translation_build
import capture_dialogue
import english
import english_font
import extract
import layout
import pyboy_route
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "Mamel.state"
STATE_SHA1 = "f03f9ed6e5a9562789903e1360892caff68382be"
HOUSE_LABELS = (
    (0x7189, "a Monster House"),
    (0x7192, "a Ghost House"),
    (0x719A, "a Drain House"),
    (0x71A2, "a Power House"),
    (0x71A9, "a Dragon House"),
    (0x71B1, "a Bomb House"),
    (0x71B9, "a Magic House"),
    (0x71C1, "a One-Eyed House"),
    (0x71C9, "a Hermit House"),
    (0x71D1, "an Animal House"),
    (0x71D9, "a Thief House"),
    (0x71E1, "a Police Station"),
)


class MonsterHouseLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        cls.source = cls.source_path.read_bytes()
        if sha1(cls.source).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        if sha1(STATE.read_bytes()).hexdigest() != STATE_SHA1:
            raise unittest.SkipTest("Mamel state hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.result = extract.extract(cls.source)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )

    def test_every_runtime_house_label_has_an_english_override(self):
        actual = tuple(
            (
                address,
                None if self.translated.get((205, address)) is None
                else self.translated[(205, address)].text,
            )
            for address, _text in HOUSE_LABELS
        )
        self.assertEqual(HOUSE_LABELS, actual)

    def test_monstercall_scroll_renders_an_english_monster_house_alert(self):
        overrides = translations.encoded_overrides(self.translated)
        runtime = runtime_widths.analyze(
            english_font.install(self.source), self.result, self.translated
        )
        output, _allocation, _validation = translation_build.build_rom(
            self.source, overrides, runtime_contract=runtime.contract
        )
        with tempfile.TemporaryDirectory() as temporary:
            localized = Path(temporary) / "monster-house.gbc"
            localized.write_bytes(output)
            pyboy = pyboy_route.start(self.PyBoy, localized, STATE)
            pyboy.set_emulation_speed(0)
            draws = []

            def at_full_renderer(_context=None):
                staged = bytearray()
                for offset in range(0x100):
                    value = pyboy.memory[0xC800 + offset]
                    staged.append(value)
                    if value == 0xFF:
                        break
                draws.append(bytes(staged))

            try:
                # Exhaust the opening Mamel tutorial and retain the generated floor.
                for frame in range(1001):
                    if frame in (120, 240, 420, 600, 780, 960):
                        pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                    if frame in (180, 360):
                        pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                    pyboy.tick()

                # Replace this disposable run's inventory with one identified
                # Monstercall Scroll (item $86, scroll category $07).
                occupied = {
                    value
                    for value in pyboy_route.work_read(pyboy, 0x12C1, 20)
                    if value != 0xFF
                }
                object_id = next(
                    index
                    for index in range(128)
                    if index not in occupied
                    and pyboy_route.work_read(pyboy, 0x2482 + index * 8, 8)
                    == bytes(8)
                )
                pyboy_route.work_write(
                    pyboy,
                    0x2482 + object_id * 8,
                    bytes.fromhex("86 07 00 00 00 00 00 00"),
                )
                pyboy_route.work_write(
                    pyboy,
                    0x12C1,
                    bytes((object_id,)) + bytes((0xFF,)) * 19,
                )

                # Status -> Items -> item -> Read.
                for button in ("b", "a", "a"):
                    pyboy.button(button, capture_dialogue.PRESS_FRAMES)
                    for _frame in range(120):
                        pyboy.tick()
                pyboy.hook_register(
                    *layout.FULL_RENDERER_ENTRY, at_full_renderer, None
                )
                pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                for _frame in range(260):
                    pyboy.tick()

                expected = english.encode("It's a Monster House!") + b"\xFF"
                self.assertIn(expected, draws)
                self.assertNotIn(
                    bytes.fromhex("12 43 4C 42 24 A2 AD 8C 8F D9 99 82 8C 4F FF"),
                    draws,
                )
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
