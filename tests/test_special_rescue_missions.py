from hashlib import sha1
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_special_rescues
import capture_dialogue
import extract
import pyboy_route as route
import rescue_converter
import rescue_password as protocol
from tests.test_rescue_presentation import _input_sequences


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates/rescue-entry-menu.state"
STATE_SHA1 = "8c79794a9ae28857dd51ebe343191e1796007164"


class SpecialRescueAuditTests(unittest.TestCase):
    def test_verified_rom_uses_external_packets_and_native_progression_checks(self):
        source = ROOT / ROM_NAME
        if not source.exists():
            self.skipTest("original ROM is required for the native audit")
        rom = source.read_bytes()
        result = audit_special_rescues.analyze(rom)
        for mission in result["missions"]:
            self.assertTrue(all(not matches for matches in mission["matches"].values()))
        at = extract.file_offset(5, 0x6478)
        table = rom[at:at + 18]
        access = dict(zip(table[::2], table[1::2]))
        self.assertEqual({8: 0x1F, 7: 0x1C, 6: 0x24}, {key: access[key] for key in (8, 7, 6)})
        with self.assertRaisesRegex(ValueError, "original Japanese ROM"):
            audit_special_rescues.analyze(bytes(len(rom)))


class PyBoySpecialRescueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and rescue-entry state are required")
        if sha1(source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise AssertionError("original ROM changed")
        if sha1(STATE.read_bytes()).hexdigest() != STATE_SHA1:
            raise AssertionError("rescue-entry state changed")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as error:
            raise unittest.SkipTest(str(error)) from error
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        destination = Path(cls.temporary.name) / "special-rescue.gbc"
        built = subprocess.run(
            [sys.executable, str(ROOT / "tools/build.py"), str(source),
             str(ROOT / "script/en"), str(destination), "--font-style", "both"],
            cwd=ROOT, capture_output=True, text=True, timeout=90,
        )
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        cls.roms = {style: destination.with_name("special-rescue-%s-font.gbc" % style)
                    for style in ("classic", "shadowed")}
        cls.editors = {}
        for style, rom in cls.roms.items():
            target = route.start(cls.PyBoy, rom, STATE)
            try:
                target.memory[0xC195] = 0
                for frame in range(5201):
                    if frame in (90, 390, 720, 1120, 3200):
                        route.press(target, "a")
                    target.tick()
                    if target.memory[0xC195] == 8 and target.memory[0xC14E] == 0xF5:
                        target.tick(400)
                        break
                else:
                    raise AssertionError("native SOS constructor did not open the English editor")
                buffer = io.BytesIO()
                target.save_state(buffer)
                cls.editors[style] = buffer.getvalue()
            finally:
                target.stop(save=False)

    def _submit(self, style, mission, unlocked):
        rom = self.roms[style]
        target = route.start(self.PyBoy, rom, STATE)
        try:
            target.load_state(io.BytesIO(self.editors[style]))
            self.assertEqual(6, target.memory[0xC3EF])
            if unlocked:
                # The captured diary is early-game. This disposable copy advances
                # only the progress byte read by 05:$60B6 / 05:$6443 to meet the
                # three published destinations' original access requirements.
                target.memory[0xC3EF] = 0x24
            entered, validated = [], []

            def before_decode(_):
                entered.append(bytes(target.memory[0xC16D:0xC17B]))

            def after_validation(_):
                validated.append((target.register_file.C,
                                  bytes(target.memory[0xC27D:0xC287])))

            target.hook_register(0x11, 0x76CA, before_decode, None)
            target.hook_register(0x11, 0x76E4, after_validation, None)
            buttons, confirm = _input_sequences(rom.read_bytes(), mission["english"])
            for button in buttons:
                route.press(target, button)
                target.tick(15)
            target.tick(30)
            native = protocol.delocalize_password(mission["english"]) + b"\xff"
            self.assertEqual(native, bytes(target.memory[0xC16D:0xC17B]))
            self.assertEqual(0x4D, target.memory[0xC14F])
            self.assertEqual(13, target.memory[0xC153])
            for button in confirm:
                route.press(target, button)
                target.tick(15)
            target.tick(600)
            self.assertEqual([native], entered)
            fields = protocol.decode_sos(native[:-1])
            self.assertEqual([(0 if unlocked else 2, fields.to_diary_record())], validated)
            self.assertEqual((mission["dungeon_id"], mission["floor"]),
                             (fields.dungeon_id, fields.internal_floor))
            self.assertNotEqual(0, target.register_file.PC)
        finally:
            target.stop(save=False)

    def test_all_three_missions_are_accepted_through_both_english_keyboards(self):
        for style in self.roms:
            for mission in rescue_converter.mission_data()["missions"]:
                with self.subTest(style=style, mission=mission["id"]):
                    self._submit(style, mission, unlocked=True)

    def test_valid_passwords_still_respect_the_captured_diarys_dungeon_locks(self):
        for mission in rescue_converter.mission_data()["missions"]:
            with self.subTest(mission=mission["id"]):
                self._submit("shadowed", mission, unlocked=False)


if __name__ == "__main__":
    unittest.main()
