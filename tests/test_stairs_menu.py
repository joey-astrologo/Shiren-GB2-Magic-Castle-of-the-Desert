from hashlib import sha1
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translation_build
import capture_dialogue
import cartridge
import english
import english_font
import extract
import mesen_state
import runtime_widths
import service_menus
import stairs_menu
import surfaces
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "stairs_menu.json").read_text(
        encoding="utf-8"
    )
)


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.exists():
        raise unittest.SkipTest("matching original ROM is required")
    rom = path.read_bytes()
    if sha1(rom).hexdigest() != capture_dialogue.ROM_SHA1:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, rom


class StairsMenuInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        cls.output = stairs_menu.install(cls.rom)

    def test_source_code_frame_and_pixel_budget_are_frozen(self):
        self.assertEqual(FIXTURE, stairs_menu.summary(self.rom))
        self.assertLess(FIXTURE["labels"][1]["native_clearance_pixels"], 0)
        self.assertGreaterEqual(FIXTURE["labels"][1]["english_clearance_pixels"], 0)

    def test_wide_template_has_seven_interior_tiles_and_reviewed_edges(self):
        raw = stairs_menu.template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [cells[offset:offset + 9] for offset in range(0, len(cells), 9)]
        self.assertEqual(5, len(rows))
        self.assertEqual((0x7E, 0x8F), rows[0][0])
        self.assertEqual((0x7E, 0xAF), rows[0][-1])
        self.assertEqual([(0x90 + index, 0x87) for index in range(7)], rows[1][1:-1])
        self.assertEqual((0x7E, 0xCF), rows[-1][0])
        self.assertEqual((0x7E, 0xEF), rows[-1][-1])

    def test_status_template_has_seven_interior_tiles_and_reviewed_edges(self):
        raw = stairs_menu.status_template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [cells[offset:offset + 9] for offset in range(0, len(cells), 9)]
        self.assertEqual(5, len(rows))
        self.assertEqual((0x7C, 0x00), rows[0][0])
        self.assertEqual((0x7C, 0x20), rows[0][-1])
        self.assertEqual([(0x25 + index, 0x08) for index in range(7)], rows[1][1:-1])
        self.assertEqual((0x7C, 0x40), rows[-1][0])
        self.assertEqual((0x7C, 0x60), rows[-1][-1])

    def test_floor_scratch_does_not_alias_any_popup_staging_cell(self):
        """A non-stairs popup must not be able to arm stairs cleanup.

        Test the installed machine code rather than implementation constants:
        every staged popup byte is live from D800 through the largest localized
        template, so none of those addresses may occur as a floor-runtime
        memory operand.
        """
        floor_runtime = stairs_menu.floor_runtime_bytes()
        popup_staging = range(
            0xD800,
            0xD800 + len(service_menus.service_template_bytes()),
        )
        aliased = [
            address
            for address in popup_staging
            if address.to_bytes(2, "little") in floor_runtime
        ]
        self.assertEqual([], aliased)
        self.assertLess(
            service_menus.BLACKSMITH_TILE_FLAG_ADDRESS,
            stairs_menu.FLOOR_SAVED_CELLS_ADDRESS,
        )
        self.assertEqual(
            0xFF,
            stairs_menu.FLOOR_SAVED_FLAG_VALUE
            ^ stairs_menu.FLOOR_SAVED_FLAG_END_VALUE,
        )

    def test_installer_changes_only_reviewed_code_padding_and_checksums(self):
        allowed = {
            offset
            for start, end in stairs_menu.owned_ranges()
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
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)
        cartridge.verify_checksums(self.output)

    def test_source_code_and_padding_guards_fail_closed(self):
        cases = (
            (stairs_menu.BANK, stairs_menu.LOAD_PATCH_ADDRESS),
            (stairs_menu.BANK, stairs_menu.COPY_PATCH_ADDRESS),
            (stairs_menu.RUNTIME_BANK, stairs_menu.HELPER_ADDRESS),
            (stairs_menu.STATUS_BANK, stairs_menu.STATUS_PATCH_ADDRESS),
            (
                stairs_menu.CONTROLLER_BANK,
                stairs_menu.CONTROLLER_EXIT_PATCH_ADDRESS,
            ),
        )
        for bank, address in cases:
            damaged = bytearray(self.rom)
            damaged[extract.file_offset(bank, address)] ^= 1
            with self.subTest(address=extract.location(bank, address)):
                with self.assertRaises(stairs_menu.StairsMenuError):
                    stairs_menu.install(damaged)


class LiveLocalizedStairsMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        state_path = ROOT / "SaveStates" / "Mamel.mss"
        if not state_path.exists():
            raise unittest.SkipTest("Mamel Mesen state is required")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        result = extract.extract(cls.rom)
        translated = translations.load_path(ROOT / "script" / "en", result["records"])
        runtime = runtime_widths.analyze(
            english_font.install(cls.rom), result, translated
        )
        output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "localized.gbc"
        cls.localized_path.write_bytes(output)
        cls.ram = mesen_state.cart_ram(state_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_live_stairs_routes_draw_and_tear_down_both_wide_frames(self):
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        selectors = []
        draws = []
        copies = []

        def at_selector(_context=None):
            if pyboy.register_file.A == stairs_menu.STAIRS_GROUP:
                selectors.append(pyboy.register_file.C)

        def at_direct_draw(_context=None):
            staged = bytes(pyboy.memory[0xC800:0xC900])
            try:
                end = staged.index(0xFF) + 1
            except ValueError:
                return
            draws.append(staged[:end])

        def at_bg_copy(_context=None):
            copies.append(
                (
                    pyboy.register_file.B,
                    pyboy.register_file.C,
                    pyboy.register_file.HL,
                )
            )

        def tilemap_cells(top_left, rows, columns):
            old_vbk = pyboy.memory[0xFF4F]
            result = []
            for row in range(rows):
                values = []
                for column in range(columns):
                    address = top_left + row * 32 + column
                    pyboy.memory[0xFF4F] = 0
                    tile = pyboy.memory[address]
                    pyboy.memory[0xFF4F] = 1
                    attribute = pyboy.memory[address]
                    values.append((tile, attribute))
                result.append(values)
            pyboy.memory[0xFF4F] = old_vbk & 1
            return result

        try:
            # Enter the supplied dungeon state, clear the nearby Mamel and all
            # modal combat text, then retain the live generated floor.
            for frame in range(1001):
                if frame in (120, 240, 420, 600, 780, 960):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
            for _attack in range(14):
                pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                for _frame in range(120):
                    pyboy.tick()
            for _frame in range(240):
                pyboy.tick()

            # Place the special player coordinates and occupancy marker beside
            # the already-generated stairs. Moving down now uses the game's
            # natural tile-entry and popup path.
            old_svbk = pyboy.memory[0xFF70]
            pyboy.memory[0xFF70] = 3
            for offset in range(0x400):
                if pyboy.memory[0xD400 + offset] == 0:
                    pyboy.memory[0xD400 + offset] = 0xFF
            pyboy.memory[0xD400 + 17 * 32 + 5] = 0
            pyboy.memory[0xFF70] = old_svbk & 7
            pyboy.memory[0xFF93] = 5
            pyboy.memory[0xFF94] = 17

            pyboy.hook_register(0, 0x1FA0, at_selector, None)
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            pyboy.hook_register(0, 0x0AEA, at_bg_copy, None)
            floor_underlay = tilemap_cells(0x9988, 5, 9)
            pyboy.button("down", capture_dialogue.PRESS_FRAMES)
            for _frame in range(180):
                pyboy.tick()

            self.assertEqual([60, 59], selectors)
            self.assertIn(english.encode("Proceed") + b"\xFF", draws)
            self.assertIn(english.encode("Stay Here") + b"\xFF", draws)
            self.assertIn((4, 9, 0xD800), copies)
            self.assertIn((1, 9, 0xD848), copies)

            # Stay Here closes through the native seven-column redraw.  The
            # English-only two columns must be restored from the saved BG
            # cells rather than remaining as a vertical frame fragment.
            pyboy.button("down", capture_dialogue.PRESS_FRAMES)
            for _frame in range(100):
                pyboy.tick()
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
            for _frame in range(240):
                pyboy.tick()
            self.assertEqual(floor_underlay, tilemap_cells(0x9988, 5, 9))

            # The status-menu Stairs command uses a separate bank-11
            # constructor.  Open it naturally, prove its nine-column copy,
            # then prove the ordinary main-menu redraw removes the full frame.
            pyboy.button("b", capture_dialogue.PRESS_FRAMES)
            for _frame in range(240):
                pyboy.tick()
            pyboy.button("down", capture_dialogue.PRESS_FRAMES)
            for _frame in range(120):
                pyboy.tick()
            status_underlay = tilemap_cells(0x9883, 5, 9)
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
            for _frame in range(180):
                pyboy.tick()
            self.assertIn(
                (5, 9, stairs_menu.status_template_address()), copies
            )
            status_frame = tilemap_cells(0x9883, 5, 9)
            self.assertEqual([0x7C, 0x7D, 0x7D, 0x7D, 0x7C], [row[-1][0] for row in status_frame])
            pyboy.button("down", capture_dialogue.PRESS_FRAMES)
            for _frame in range(120):
                pyboy.tick()
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
            for _frame in range(240):
                pyboy.tick()
            self.assertEqual(status_underlay, tilemap_cells(0x9883, 5, 9))
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)

    def test_stairs_runtime_does_not_corrupt_monster_notebook_graphics(self):
        # Build a deterministic initialized state, then redirect the next
        # banked dispatch through the real Monster Notebook handler.  The old
        # bank-3 padding implementation rendered its helper bytes as garbage
        # across this otherwise blank top strip.
        owner = self.PyBoy(str(self.path), window="null", sound_emulated=False)
        owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(owner)
            for frame in range(15000):
                if frame % 180 == 0:
                    owner.button("a", capture_dialogue.PRESS_FRAMES)
                owner.tick()
            state = io.BytesIO()
            owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            owner.stop(save=False)

        pyboy = self.PyBoy(
            str(self.localized_path), window="null", sound_emulated=False
        )
        pyboy.set_emulation_speed(0)
        redirected = [False]
        details = [0]

        def at_dispatch(_context=None):
            if redirected[0]:
                return
            redirected[0] = True
            pyboy.register_file.A = surfaces.MONSTER_NOTEBOOK_HANDLER[0]
            pyboy.register_file.HL = surfaces.MONSTER_NOTEBOOK_HANDLER[1]

        def force_catalog(_context=None):
            pyboy.register_file.A = 1

        def seed_cursor(_context=None):
            pyboy.memory[0xC14F] = 0
            pyboy.memory[0xC150] = 0

        def at_detail(_context=None):
            details[0] += 1

        try:
            pyboy.load_state(io.BytesIO(state_bytes))
            pyboy.hook_register(0, 0x09AC, at_dispatch, None)
            pyboy.hook_register(11, 0x7A5A, force_catalog, None)
            pyboy.hook_register(11, 0x7ADC, force_catalog, None)
            pyboy.hook_register(16, 0x7EA5, seed_cursor, None)
            pyboy.hook_register(*surfaces.MONSTER_NOTEBOOK_DETAIL, at_detail, None)
            for frame in range(150):
                if frame == 25:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            self.assertTrue(redirected[0])
            self.assertEqual(1, details[0])
            clean_top = pyboy.screen.image.convert("RGB").crop((0, 0, 120, 32))
            self.assertEqual(
                "1c2bdfcaa17973afe04181cc0e3e0a3f6e8246c7",
                sha1(clean_top.tobytes()).hexdigest(),
            )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
