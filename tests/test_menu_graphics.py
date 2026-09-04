from hashlib import sha1
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import build as translation_build
import english
import english_font
import extract
import hud_font
import menu_graphics
import pyboy_state
import runtime_widths
import surfaces
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "main_menu_graphics.json").read_text(
        encoding="utf-8"
    )
)


class OriginalRomMainMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.approved = english_font.load_approved()
        cls.output = menu_graphics.install(cls.rom, cls.approved)

    def test_source_canvas_labels_and_output_are_frozen(self):
        static_fixture = dict(FIXTURE)
        static_fixture.pop("live_mamel_menu")
        static_fixture.pop("live_clean_boot_diary_menu")
        static_fixture.pop("live_mamel_hints_popup")
        static_fixture.pop("live_mamel_hints_return")
        self.assertEqual(
            static_fixture, menu_graphics.summary(self.rom, self.approved)
        )
        self.assertEqual(14, len(static_fixture["labels"]))
        self.assertTrue(static_fixture["source"]["remains_byte_exact"])

    def test_shared_template_is_entirely_byte_exact(self):
        self.assertEqual(
            menu_graphics.template_bytes(self.rom),
            menu_graphics.template_bytes(self.output),
        )

    def test_status_bitmap_labels_use_the_approved_literal_shadow_pixels(self):
        localized, measurements = menu_graphics.localized_template(
            self.rom, self.approved
        )
        pixels = menu_graphics.decode_canvas(localized)
        actual = tuple(
            "".join(str(color) for color in row[3:20])
            for row in pixels[24:32]
        )
        self.assertEqual(
            (
                "30003000000000000",
                "32003200000000000",
                "33033203300333000",
                "32303200230322300",
                "32323203332320320",
                "32023230232333020",
                "32003203332322200",
                "02000200222320000",
            ),
            actual,
        )

        expected_color_counts = {
            "experience": (33, 40),
            "location": (66, 81),
            "map": (32, 41),
            "hints": (47, 57),
            "quit": (36, 46),
            "attack": (31, 40),
            "strength": (72, 92),
            "strength_separator": (6, 6),
            "defense": (33, 40),
            "fullness": (73, 87),
            "fullness_separator": (6, 6),
            "fullness_suffix": (9, 14),
            "money": (44, 56),
            "money_suffix": (12, 15),
        }
        final_x = {row["name"]: row["final_x"] for row in measurements}
        for label in menu_graphics.LABELS:
            right = min(menu_graphics.CANVAS_WIDTH, final_x[label.name] + 1)
            colors = [
                color
                for row in pixels[label.y:label.y + 8]
                for color in row[label.x:right]
            ]
            with self.subTest(label=label.name):
                self.assertEqual(
                    expected_color_counts[label.name],
                    (
                        colors.count(menu_graphics.SHADOW_COLOR),
                        colors.count(menu_graphics.INK_COLOR),
                    ),
                )

    def test_installer_changes_only_status_call_overlay_and_checksums(self):
        allowed = {
            offset
            for start, end in menu_graphics.owned_ranges(self.approved)
            for offset in range(start, end)
        } | {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        changed = {
            offset
            for offset, pair in enumerate(zip(self.rom, self.output))
            if pair[0] != pair[1]
        }
        self.assertTrue(changed <= allowed)
        for name, _bank, _address, at in menu_graphics.call_site_offsets():
            with self.subTest(call_site=name):
                self.assertEqual(
                    bytes.fromhex("3EFF210040CDAC09"), self.output[at:at + 8]
                )
        payload, _rows = menu_graphics.overlay_payload(self.rom, self.approved)
        cave = menu_graphics.overlay_offset()
        self.assertEqual(payload, self.output[cave:cave + len(payload)])
        cartridge.verify_checksums(self.output)

    def test_wrong_template_is_rejected_before_mutation(self):
        damaged = bytearray(self.rom)
        damaged[menu_graphics.template_offset()] ^= 1
        with self.assertRaisesRegex(
            menu_graphics.MenuGraphicsError, "template SHA-1"
        ):
            menu_graphics.install(damaged)

    def test_wrong_call_site_or_occupied_bank_is_rejected(self):
        for name, _bank, _address, at in menu_graphics.call_site_offsets():
            with self.subTest(call_site=name):
                call_site = bytearray(self.rom)
                call_site[at] ^= 1
                with self.assertRaisesRegex(
                    menu_graphics.MenuGraphicsError, "call site"
                ):
                    menu_graphics.install(call_site)

        cave = bytearray(self.rom)
        cave[menu_graphics.overlay_offset()] = 1
        with self.assertRaisesRegex(menu_graphics.MenuGraphicsError, "cave"):
            menu_graphics.install(cave)


class LiveLocalizedMainMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rom_path = ROOT / ROM_NAME
        state_path = ROOT / "SaveStates" / "Mamel.state"
        if not rom_path.exists() or not state_path.exists():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        cls.rom = rom_path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        extracted = extract.extract(cls.rom)
        translated = translations.load_path(ROOT / "script" / "en", extracted["records"])
        runtime = runtime_widths.analyze(
            english_font.install(cls.rom), extracted, translated
        )
        output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "localized.gbc"
        cls.localized_path.write_bytes(output)
        native_hud = bytearray(output)
        digit_start, digit_end = hud_font.digit_range()
        label_start, label_end = hud_font.label_range()
        slash_start, slash_end = hud_font.slash_range()
        native_hud[digit_start:digit_end] = hud_font.ORIGINAL_DIGIT_BYTES
        native_hud[label_start:label_end] = hud_font.ORIGINAL_LABEL_BYTES
        native_hud[slash_start:slash_end] = hud_font.ORIGINAL_SLASH_BYTES
        cartridge.fix_checksums(native_hud)
        cls.native_hud_path = Path(cls.temporary.name) / "native-hud-control.gbc"
        cls.native_hud_path.write_bytes(native_hud)
        cls.ram = pyboy_state.cart_ram(state_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _assert_live_map_shadow(self, image):
        expected = (
            "30003000000000000",
            "32003200000000000",
            "33033203300333000",
            "32303200230322300",
            "32323203332320320",
            "32023230232333020",
            "32003203332322200",
            "02000200222320000",
        )
        palette = {
            "0": (248, 248, 248),
            "2": (168, 168, 168),
            "3": (0, 0, 0),
        }
        actual = tuple(
            tuple(image.getpixel((11 + x, 40 + y)) for x in range(17))
            for y in range(8)
        )
        wanted = tuple(
            tuple(palette[color] for color in row)
            for row in expected
        )
        self.assertEqual(wanted, actual)

    def _assert_only_hud_changed(self, localized, expected_sha1, events, settled_frame):
        """Keep the old full-frame hash and isolate the approved HUD delta."""
        pyboy = self.PyBoy(
            str(self.native_hud_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        try:
            for frame in range(settled_frame + 1):
                button = events.get(frame)
                if button is not None:
                    pyboy.button(button, capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
            native = pyboy.screen.image.convert("RGB")
        finally:
            pyboy.stop(save=False)

        self.assertEqual(expected_sha1, sha1(native.tobytes()).hexdigest())
        differences = {
            (x, y)
            for y in range(localized.height)
            for x in range(localized.width)
            if localized.getpixel((x, y)) != native.getpixel((x, y))
        }
        self.assertTrue(differences)
        self.assertTrue(all(y < 8 for _x, y in differences))

    def test_mamel_save_opens_complete_english_main_menu(self):
        expected = FIXTURE["live_mamel_menu"]
        events = {
            120: "a", 180: "start", 240: "a", 360: "start",
            420: "a", 600: "a", 780: "a", 1000: "b",
        }
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        draws = []

        def at_direct_draw(_context=None):
            if pyboy.frame_count < 1000:
                return
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            draws.append(bytes(raw))

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for frame in range(expected["settled_frame"] + 1):
                if frame in (120, 240, 420, 600, 780):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if frame == 1000:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            for label in expected["dynamic_labels"]:
                with self.subTest(label=label):
                    self.assertIn(english.encode(label) + b"\xFF", draws)
            image = pyboy.screen.image.convert("RGB")
            self._assert_live_map_shadow(image)
            self._assert_only_hud_changed(
                image,
                expected["screen_rgb_sha1"],
                events,
                expected["settled_frame"],
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

    def test_clean_boot_diary_menu_is_english_and_unclipped(self):
        expected = FIXTURE["live_clean_boot_diary_menu"]
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(b"\xFF" * 0x8000),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        draws = []

        def at_direct_draw(_context=None):
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            draws.append(bytes(raw))

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for frame in range(expected["settled_frame"] + 1):
                if frame == 360:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if frame == 540:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            for label in expected["dynamic_labels"]:
                with self.subTest(label=label):
                    self.assertIn(english.encode(label) + b"\xFF", draws)
            screen = pyboy.screen.image.convert("RGB").tobytes()
            self.assertEqual(expected["screen_rgb_sha1"], sha1(screen).hexdigest())
        finally:
            pyboy.stop(save=False)

    def test_mamel_hints_popup_titles_are_english_and_bounded(self):
        expected = FIXTURE["live_mamel_hints_popup"]
        events = {
            120: "a", 180: "start", 240: "a", 360: "start",
            420: "a", 600: "a", 780: "a", 1000: "b",
            1060: "down", 1090: "down", 1120: "down", 1160: "a",
        }
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        draws = []

        def at_direct_draw(_context=None):
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            draws.append(bytes(raw))

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for frame in range(expected["settled_frame"] + 1):
                if frame in (120, 240, 420, 600, 780):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if frame == 1000:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                if frame in (1060, 1090, 1120):
                    pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                if frame == 1160:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            for label in expected["labels"]:
                with self.subTest(label=label):
                    self.assertIn(english.encode(label) + b"\xFF", draws)
            image = pyboy.screen.image.convert("RGB")
            self._assert_only_hud_changed(
                image,
                expected["screen_rgb_sha1"],
                events,
                expected["settled_frame"],
            )
        finally:
            pyboy.stop(save=False)

    def test_selected_hint_returns_to_complete_english_status_menu(self):
        """Reproduce the reported Hint -> Controls -> Back redraw regression."""
        expected = FIXTURE["live_mamel_hints_return"]
        events = {
            120: "a", 180: "start", 240: "a", 360: "start",
            420: "a", 600: "a", 780: "a", 1000: "b",
            1060: "down", 1090: "down", 1120: "down", 1160: "a",
            1280: "a", 1400: "b",
        }
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        draws = []

        def at_direct_draw(_context=None):
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            draws.append(bytes(raw))

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for frame in range(expected["settled_frame"] + 1):
                if frame in (120, 240, 420, 600, 780):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if frame == 1000:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                if frame in (1060, 1090, 1120):
                    pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                if frame in (1160, 1280):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame == 1400:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            for label in expected["dynamic_labels"]:
                with self.subTest(label=label):
                    self.assertIn(english.encode(label) + b"\xFF", draws)
            image = pyboy.screen.image.convert("RGB")
            self._assert_live_map_shadow(image)
            self._assert_only_hud_changed(
                image,
                expected["screen_rgb_sha1"],
                events,
                expected["settled_frame"],
            )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
