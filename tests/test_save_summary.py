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
import mesen_state
import runtime_widths
import surfaces
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
SUMMARY_PREFIX_ID = "192:$6C1C"
RESCUE_STATUS_ID = "193:$70E6"
APPEND_BANK = 17
APPEND_ADDRESS = 0x56B6
NATIVE_APPEND = bytes.fromhex("545D1B3E0B212F4BCDAC09")
STOCK_NAME = bytes.fromhex("8BA9ADFF")
RESCUE_SRAM_SHA1 = "5e906c5f1356ef97633cd79f428c01b44e8b5a6c"
RESCUE_SUMMARY_FRAME_SHA1 = "26978c63a763609ffc13dba0f058cc198b93da6b"


class SaveSummaryNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.extracted = extract.extract(cls.rom)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.extracted["records"]
        )

    def test_prefix_owns_only_the_label_and_separator(self):
        record = next(
            record for record in self.extracted["records"]
            if record.id == SUMMARY_PREFIX_ID
        )
        entry = self.translated[(record.bank, record.address)]
        self.assertEqual("Name:<24>", entry.text)
        self.assertEqual(english.encode_source("Name: "), entry.encoded)

    def test_native_saved_name_append_is_untouched(self):
        start = extract.file_offset(APPEND_BANK, APPEND_ADDRESS)
        self.assertEqual(NATIVE_APPEND, self.rom[start:start + len(NATIVE_APPEND)])

    def test_rescue_status_is_the_short_save_summary_record(self):
        record = next(
            record for record in self.extracted["records"]
            if record.id == RESCUE_STATUS_ID
        )
        entry = self.translated[(record.bank, record.address)]
        self.assertEqual("Awaiting Rescue", entry.text)
        self.assertEqual(
            english.encode_source("Awaiting Rescue"),
            entry.encoded,
        )


class LiveSaveSummaryNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rom_path = ROOT / ROM_NAME
        state_path = ROOT / "SaveStates" / "Mamel.mss"
        if not rom_path.exists() or not state_path.exists():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        cls.rom = rom_path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        extracted = extract.extract(cls.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", extracted["records"]
        )
        runtime = runtime_widths.analyze(
            english_font.install(cls.rom), extracted, translated
        )
        output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime.contract,
        )
        append_at = extract.file_offset(APPEND_BANK, APPEND_ADDRESS)
        if output[append_at:append_at + len(NATIVE_APPEND)] != NATIVE_APPEND:
            raise AssertionError("translated build patched the native name append")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "localized.gbc"
        cls.localized_path.write_bytes(output)
        cls.ram = mesen_state.cart_ram(state_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_summary_draws_the_saved_name_bytes_unchanged(self):
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
            for offset in range(0x49):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            draws.append(bytes(raw))

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for frame in range(281):
                if frame in (120, 240):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame == 180:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            self.assertIn(english.encode_source("Name: ") + STOCK_NAME, draws)
            self.assertNotIn(
                english.encode_source("Name: Shiren") + b"\xFF", draws
            )
            self.assertEqual(
                STOCK_NAME,
                bytes(pyboy.memory[0xC252 + offset] for offset in range(4)),
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

    def test_continue_submenu_keeps_its_native_cursor_graph(self):
        """Reproduce Adventure -> save file and exercise all four rows.

        The mode-0 unidentified-name patch once redirected native navigation
        type $13 to its private WRAM graph. This exact route then read $FF
        cursor coordinates: the cursor vanished, Down stopped advancing, and
        repeated movement corrupted the menu. Freeze both navigation state and
        the cursor-masked framebuffer so that ownership cannot regress again.
        """
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        captures = []
        try:
            for frame in range(641):
                if frame in (120, 240, 420):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if frame in (500, 560, 620):
                    pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
                if frame in (450, 520, 580, 640):
                    image = pyboy.screen.image.convert("RGB")
                    # Mask only the four possible 8x8 cursor positions. The
                    # complete menu below the sprite must remain byte-stable.
                    image.paste((248, 248, 248), (52, 12, 64, 62))
                    captures.append(
                        {
                            "navigation_type": pyboy.memory[0xC14E],
                            "cursor": pyboy.memory[0xC14F],
                            "previous": pyboy.memory[0xC150],
                            "maximum": pyboy.memory[0xC151],
                            "cursor_x": pyboy.memory[0xFFB2],
                            "cursor_y": pyboy.memory[0xFFB3],
                            "oam": bytes(pyboy.memory[0xFE00:0xFE04]),
                            "masked_sha1": sha1(image.tobytes()).hexdigest(),
                        }
                    )

            self.assertEqual([0, 1, 2, 3], [row["cursor"] for row in captures])
            self.assertEqual([0, 1, 2, 3], [row["previous"] for row in captures])
            self.assertEqual({0x13}, {row["navigation_type"] for row in captures})
            self.assertEqual({3}, {row["maximum"] for row in captures})
            self.assertEqual({0x36}, {row["cursor_x"] for row in captures})
            self.assertEqual(
                [0x17, 0x22, 0x2D, 0x38],
                [row["cursor_y"] for row in captures],
            )
            self.assertEqual(
                [(0x1F, 0x3E), (0x2A, 0x3E), (0x35, 0x3E), (0x40, 0x3E)],
                [(row["oam"][0], row["oam"][1]) for row in captures],
            )
            self.assertEqual(
                {"8f630df230639195d270536063432ce74c439e08"},
                {row["masked_sha1"] for row in captures},
            )
        finally:
            pyboy.stop(save=False)

    def test_awaiting_rescue_and_run_count_fit_as_separate_fields(self):
        """Render the real SOS save summary and freeze its collision-free UI."""
        sram_path = ROOT / "SaveStates" / "rescue-requester-sos.srm"
        if not sram_path.is_file():
            self.skipTest("requester SOS SRAM fixture is unavailable")
        sram = sram_path.read_bytes()
        self.assertEqual(RESCUE_SRAM_SHA1, sha1(sram).hexdigest())
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(sram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        try:
            for frame in range(271):
                if frame in (120, 240):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame == 180:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
            image = pyboy.screen.image.convert("RGB")
            self.assertEqual(
                RESCUE_SUMMARY_FRAME_SHA1,
                sha1(image.tobytes()).hexdigest(),
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)
