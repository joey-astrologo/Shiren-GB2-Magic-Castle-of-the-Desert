from hashlib import sha1
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import english
import font
import layout
import menu_graphics
import pyboy_route as route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "strength-defense-rendering-issue.state"
STATE_SHA1 = "982d5b88204eec8dc4359de95543e326189e9e1a"
INVENTORY = 0x12C1
OBJECTS = 0x2482
ARROW = b"\x2e"


class EquipmentPreviewInstallerTests(unittest.TestCase):
    def test_position_patch_is_guarded_and_keeps_the_native_vertical_origin(self):
        source = ROOT / ROM_NAME
        if not source.is_file():
            self.skipTest("matching original ROM is required")
        original = source.read_bytes()
        output = menu_graphics.install(original)
        at = 17 * 0x4000 + 0x71A1 - 0x4000
        self.assertEqual(bytes.fromhex("3E60EAD6C43E14EAD7C4"), original[at:at + 10])
        self.assertEqual(bytes.fromhex("3E68EAD6C43E14EAD7C4"), output[at:at + 10])
        for offset in (0, 1, 5, 6, 9):
            with self.subTest(offset=offset):
                damaged = bytearray(original)
                damaged[at + offset] ^= 1
                with self.assertRaisesRegex(menu_graphics.MenuGraphicsError, "equipment preview"):
                    menu_graphics.install(damaged)


class PyBoyEquipmentPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ROM_NAME).is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and equipment preview state are required")
        if sha1(STATE.read_bytes()).hexdigest() != STATE_SHA1:
            raise AssertionError("equipment preview state SHA-1 changed")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory()
        destination = Path(cls.temporary.name) / "equipment.gbc"
        built = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build.py"),
             str(ROOT / ROM_NAME), str(ROOT / "script" / "en"),
             str(destination), "--font-style", "both"],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
        )
        if built.returncode:
            cls.temporary.cleanup()
            raise AssertionError(built.stdout + built.stderr)
        cls.localized = {
            style: destination.with_name("equipment-%s-font.gbc" % style)
            for style in ("classic", "shadowed")
        }

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    @staticmethod
    def _items(target):
        inventory = route.work_read(target, INVENTORY, 20)
        return inventory, tuple((item, route.work_read(target, OBJECTS + item * 8, 8))
                                for item in inventory if item != 255)

    @staticmethod
    def _read_stream(target):
        return bytes(target.memory[0xC800:0xC820]).split(b"\xff", 1)[0]

    @staticmethod
    def _expected_pixels(rom, current, proposed):
        white, gray, black = (248, 248, 248), (168, 168, 168), (0, 0, 0)
        pixels = [[white] * 48 for _ in range(16)]
        x = 8  # The first interior tile remains reserved for cursor cleanup.
        raw = english.encode(str(current)) + ARROW + english.encode(str(proposed))
        for code in raw:
            glyph = font.read_glyph(rom, bytes((code,)))
            for y, row in enumerate(glyph.pixels):
                for dx, color in enumerate(row):
                    if x + dx < 48:
                        # Mode $08 maps the font's color-1 white to canvas 0.
                        pixels[y + 4][x + dx] = (white, white, gray, black)[color]
            x += glyph.width
        return tuple(tuple(row) for row in pixels)

    def _assert_preview(self, target, rom, current, proposed):
        stream = self._read_stream(target)
        self.assertEqual(english.encode(str(current)) + ARROW + english.encode(str(proposed)),
                         stream.replace(b"\xfe", b""))
        expected = self._expected_pixels(rom, current, proposed)
        for _ in range(3):
            image = target.screen.image.convert("RGB")
            actual = tuple(tuple(image.getpixel((x, y)) for x in range(104, 152))
                           for y in range(120, 136))
            self.assertEqual(expected, actual)
            target.tick()
        # The complete cursor-alias cells must remain cleared, including the
        # blank part below the preview where Exchange's shadow used to leak.
        old_vbk = target.memory[0xFF4F]
        try:
            target.memory[0xFF4F] = 1
            for tile in menu_graphics.ITEM_ACTION_CURSOR_TILE_IDS:
                at = 0x9000 + tile * 16
                self.assertEqual(bytes(16), bytes(target.memory[at:at + 16]))
        finally:
            target.memory[0xFF4F] = old_vbk

    def test_supplied_bronze_shield_displays_129_to_5_without_inventory_changes(self):
        for style, path in self.localized.items():
            with self.subTest(font=style):
                target = route.start(self.PyBoy, path, STATE)
                calls = []
                try:
                    route.run_frames(target, 30)
                    before = self._items(target)
                    self.assertEqual(9, before[0][2])
                    self.assertEqual(bytes.fromhex("2302050320000000"), dict(before[1])[9])
                    target.hook_register(17, 0x7116,
                        lambda _: calls.append((target.register_file.A, target.register_file.E)), None)
                    route.press(target, "a")
                    route.run_frames(target, 60)
                    self.assertEqual([(2, 9)], calls)
                    self._assert_preview(target, path.read_bytes(), 129, 5)
                    self.assertEqual(before, self._items(target))
                finally:
                    target.stop(save=False)

    def test_sword_and_shield_previews_cover_both_digit_counts_and_redraw(self):
        values = (0, 9, 10, 99, 100, 255)
        for style, path in self.localized.items():
            rom = path.read_bytes()
            for kind, item_index, equipped in ((1, 2, 10), (2, 35, 11)):
                for current in values:
                    for proposed in values:
                        with self.subTest(font=style, kind=kind, current=current, proposed=proposed):
                            target = route.start(self.PyBoy, path, STATE)
                            calls = []
                            try:
                                route.run_frames(target, 30)
                                # Only disposable item records are varied. The real
                                # equipment getter, decimal formatter, menu drawing,
                                # upload and physical A/B controller paths all run.
                                record = bytearray(route.work_read(target, OBJECTS + equipped * 8, 8))
                                record[2:4] = bytes((current, 0))
                                route.work_write(target, OBJECTS + equipped * 8, record)
                                route.work_write(target, OBJECTS + 9 * 8,
                                                 bytes((item_index, kind, proposed, 0, 0, 0, 0, 0)))
                                before = self._items(target)
                                target.hook_register(17, 0x7116,
                                    lambda _: calls.append((target.register_file.A, target.register_file.E)), None)
                                route.press(target, "a")
                                route.run_frames(target, 30)
                                self._assert_preview(target, rom, current, proposed)
                                route.press(target, "b")
                                route.run_frames(target, 30)
                                route.press(target, "a")
                                route.run_frames(target, 30)
                                self._assert_preview(target, rom, current, proposed)
                                self.assertEqual([(kind, 9), (kind, 9)], calls)
                                self.assertEqual(before, self._items(target))
                            finally:
                                target.stop(save=False)

    def test_every_unsigned_byte_fits_with_a_three_digit_value_on_either_side(self):
        for style, path in self.localized.items():
            rom = path.read_bytes()
            for value in range(256):
                for current, proposed in ((value, 255), (255, value)):
                    with self.subTest(font=style, current=current, proposed=proposed):
                        raw = english.encode(str(current)) + ARROW + english.encode(str(proposed))
                        measured = layout.validate_direct_surface(
                            rom, raw, start_x=104, start_y=20, right_edge=144
                        )
                        self.assertLessEqual(measured.final_x, 142)
                        self.assertEqual(20, measured.final_y)
                        # Visible ink/shadow also fits; the compositor may clip
                        # only unused trailing cell pixels at the right edge.
                        x = 104
                        for code in raw:
                            glyph = font.read_glyph(rom, bytes((code,)))
                            for row in glyph.pixels:
                                self.assertTrue(all(x + dx < 144 for dx, color in enumerate(row)
                                                    if color in (2, 3)))
                            x += glyph.width


if __name__ == "__main__":
    unittest.main()
