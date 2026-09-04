from hashlib import sha1
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cartridge
import capture_dialogue
import extract
import pyboy_route
import service_menus
import stairs_menu


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "service_menus.json").read_text(
        encoding="utf-8"
    )
)

# Confirmed live in an untouched Japanese ROM during ordinary dungeon UI.
# Widened service menus cannot treat this bank-7 memory as persistent storage.
NATIVE_BANK7_UI_LIVE_START = 0xD8B4
NATIVE_BANK7_UI_LIVE_END = 0xD8F8


def _original_rom():
    path = ROOT / ROM_NAME
    if not path.is_file():
        raise unittest.SkipTest("matching original ROM is required")
    rom = path.read_bytes()
    if sha1(rom).hexdigest() != extract.ROM_SHA1:
        raise unittest.SkipTest("ROM hash does not match the fixture")
    return path, rom


class ServiceMenuInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.rom = _original_rom()
        cls.stairs = stairs_menu.install(cls.rom)
        cls.output = service_menus.install(cls.stairs)

    def test_exact_service_sets_widths_and_runtime_are_frozen(self):
        self.assertEqual(FIXTURE["static"], service_menus.summary(self.stairs))
        password = next(
            row for row in FIXTURE["static"]["labels"]
            if row["text"] == "Password"
        )
        self.assertLess(password["native_clearance_pixels"], 0)
        self.assertGreaterEqual(password["english_clearance_pixels"], 0)
        self.assertEqual(service_menus.TEXT_START_X, password["text_start_pixels"])
        self.assertEqual(6, password["english_clearance_pixels"])
        synthesis = next(
            row for row in FIXTURE["static"]["labels"]
            if row["menu"] == "blacksmith_info" and row["text"] == "Synthesis"
        )
        self.assertEqual(45, synthesis["renderer_pixels"])
        self.assertEqual(-13, synthesis["native_clearance_pixels"])
        self.assertEqual(3, synthesis["english_clearance_pixels"])

    def test_service_template_has_six_dynamic_tiles_and_a_stable_spill_tile(self):
        raw = service_menus.service_template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [
            cells[offset:offset + service_menus.ENGLISH_COLUMNS]
            for offset in range(0, len(cells), service_menus.ENGLISH_COLUMNS)
        ]
        self.assertEqual(10, len(rows))
        self.assertEqual((0x7E, 0x8F), rows[0][0])
        self.assertEqual((0x7E, 0xAF), rows[0][-1])
        self.assertEqual(
            [(0x90 + index, 0x87) for index in range(6)]
            + [(service_menus.SERVICE_BLANK_TILE, 0x87)],
            rows[1][1:-1],
        )
        self.assertEqual((0x7E, 0xCF), rows[-1][0])
        self.assertEqual((0x7E, 0xEF), rows[-1][-1])
        self.assertEqual(
            [0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, service_menus.SERVICE_BLANK_TILE],
            [tile for tile, _attribute in rows[6][1:-1]],
        )
        for row in rows[1:-1]:
            self.assertEqual(service_menus.SERVICE_BLANK_TILE, row[-2][0])
        self.assertNotIn(0xC0, [tile for tile, _attribute in rows[6][1:-1]])

    def test_rescue_template_exposes_only_password_overflow_tiles(self):
        raw = service_menus.rescue_template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [
            cells[offset:offset + service_menus.ENGLISH_COLUMNS]
            for offset in range(0, len(cells), service_menus.ENGLISH_COLUMNS)
        ]
        spill_tiles = [row[-2][0] for row in rows[1:-1]]
        self.assertEqual(
            [
                service_menus.SERVICE_BLANK_TILE,
                0xA8,
                0xBA,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
            ],
            spill_tiles,
        )
        self.assertEqual(
            service_menus.service_template_address()
            + len(service_menus.service_template_bytes()),
            service_menus.rescue_template_address(),
        )

    def test_post_rescue_template_stages_password_away_from_cursor_tiles(self):
        raw = service_menus.rescue_delivery_template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [
            cells[offset:offset + service_menus.ENGLISH_COLUMNS]
            for offset in range(0, len(cells), service_menus.ENGLISH_COLUMNS)
        ]
        self.assertEqual(
            [
                service_menus.SERVICE_BLANK_TILE,
                service_menus.RESCUE_DELIVERY_SUFFIX_TILES[0],
                service_menus.RESCUE_DELIVERY_SUFFIX_TILES[1],
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
                service_menus.SERVICE_BLANK_TILE,
            ],
            [row[-2][0] for row in rows[1:-1]],
        )
        self.assertTrue(
            set(service_menus.RESCUE_DELIVERY_SUFFIX_SOURCE_TILES).isdisjoint(
                service_menus.RESCUE_DELIVERY_SUFFIX_TILES
            )
        )
        self.assertEqual(
            service_menus.rescue_template_address()
            + len(service_menus.rescue_template_bytes()),
            service_menus.rescue_delivery_template_address(),
        )
        stage = service_menus._rescue_delivery_tile_support_bytes()
        blank = 0x8000 + service_menus.SERVICE_BLANK_TILE * 16
        for source_tile, destination_tile in zip(
            service_menus.RESCUE_DELIVERY_SUFFIX_SOURCE_TILES,
            service_menus.RESCUE_DELIVERY_SUFFIX_TILES,
        ):
            source = 0x8000 + source_tile * 16
            destination = 0x8000 + destination_tile * 16
            self.assertIn(
                bytes((
                    0x21, source & 0xFF, source >> 8,
                    0x11, destination & 0xFF, destination >> 8,
                    0x01, 0x10, 0x00, 0xCD, 0x6B, 0x0A,
                )),
                stage,
            )
            self.assertIn(
                bytes((
                    0x21, blank & 0xFF, blank >> 8,
                    0x11, source & 0xFF, source >> 8,
                    0x01, 0x10, 0x00, 0xCD, 0x6B, 0x0A,
                )),
                stage,
            )

    def test_blacksmith_template_uses_one_staged_suffix_spill(self):
        raw = service_menus.blacksmith_info_template_bytes()
        cells = [tuple(raw[offset:offset + 2]) for offset in range(0, len(raw), 2)]
        rows = [
            cells[offset:offset + service_menus.ENGLISH_COLUMNS]
            for offset in range(0, len(cells), service_menus.ENGLISH_COLUMNS)
        ]
        self.assertEqual(
            [
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_SUFFIX_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
                service_menus.BLACKSMITH_BLANK_TILE,
            ],
            [row[-2][0] for row in rows[1:-1]],
        )
        self.assertEqual(
            service_menus.rescue_delivery_template_address()
            + len(service_menus.rescue_delivery_template_bytes()),
            service_menus.blacksmith_info_template_address(),
        )

    def test_blacksmith_suffix_tile_is_staged_and_restored(self):
        stage = service_menus._blacksmith_tile_support_bytes()
        source = 0x8000 + service_menus.BLACKSMITH_SUFFIX_SOURCE_TILE * 16
        destination = 0x8000 + service_menus.BLACKSMITH_SUFFIX_TILE * 16
        blank = 0x8000 + service_menus.BLACKSMITH_BLANK_TILE * 16
        self.assertIn(bytes((0x21, source & 0xFF, source >> 8)), stage)
        self.assertIn(bytes((0x11, destination & 0xFF, destination >> 8)), stage)
        self.assertIn(
            bytes((
                0x21, blank & 0xFF, blank >> 8,
                0x11, source & 0xFF, source >> 8,
                0x01, 0x10, 0x00, 0xCD, 0x6B, 0x0A,
            )),
            stage,
        )
        self.assertIn(
            bytes.fromhex(
                "F50707074F2121D811120006077EE6F7B177190520F7"
                "F14FE04F3E05E07079EAD9D9"
            ),
            stage,
        )
        self.assertIn(
            bytes((0x3E, service_menus.BLACKSMITH_TILE_FLAG_VALUE)), stage
        )
        restore = service_menus._restore_support_bytes()
        self.assertIn(bytes((0x21, blank & 0xFF, blank >> 8)), restore)
        self.assertIn(bytes((0x11, destination & 0xFF, destination >> 8)), restore)

    def test_native_load_branch_lands_on_the_native_ld_hl(self):
        raw = service_menus._load_support_bytes()
        self.assertEqual(b"\x20", raw[3:4])
        target = 5 + raw[4]
        native = service_menus.stairs_menu.NATIVE_TEMPLATE_ADDRESS
        self.assertEqual(
            bytes((0x21, native & 0xFF, native >> 8)),
            raw[target:target + 3],
        )

    def test_wide_copy_inherits_the_active_vram_bank_for_its_bottom_row(self):
        raw = service_menus._copy_support_bytes()
        bottom = 0xD800 + 9 * service_menus.ENGLISH_COLUMNS * 2
        first_attribute = bottom + 3
        self.assertIn(
            bytes.fromhex("C5FA03D8E608F6C7")
            + bytes((0x21, first_attribute & 0xFF, first_attribute >> 8))
            + bytes((0x06, service_menus.ENGLISH_INTERIOR_COLUMNS))
            + bytes.fromhex("22230520FBC1"),
            raw,
        )

    def test_wide_copy_saves_the_added_column_before_drawing(self):
        raw = service_menus._copy_support_bytes()
        save = service_menus.service_save_address()
        self.assertIn(bytes((0xCD, save & 0xFF, save >> 8)), raw)
        self.assertLessEqual(
            service_menus.SAVED_COLUMN_ADDRESS
            + 2 * service_menus.MAXIMUM_SERVICE_ROWS,
            service_menus.SAVED_DESTINATION_ADDRESS,
        )
        self.assertLess(
            0xD800 + len(service_menus.service_template_bytes()),
            service_menus.SAVED_COLUMN_ADDRESS,
        )

    def test_service_state_does_not_overlap_live_native_bank7_ui_memory(self):
        self.assertEqual(
            stairs_menu.POPUP_STATE_WRAM_BANK,
            service_menus.POPUP_STATE_WRAM_BANK,
        )
        self.assertNotEqual(7, service_menus.POPUP_STATE_WRAM_BANK)
        service_state = range(
            service_menus.SAVED_COLUMN_ADDRESS,
            service_menus.BLACKSMITH_TILE_FLAG_ADDRESS + 1,
        )
        native_ui = range(
            NATIVE_BANK7_UI_LIVE_START,
            NATIVE_BANK7_UI_LIVE_END,
        )
        self.assertTrue(set(service_state).isdisjoint(native_ui))
        self.assertGreaterEqual(
            service_state.start, stairs_menu.POPUP_STATE_RESERVED_START
        )
        self.assertLessEqual(
            service_state.stop, stairs_menu.POPUP_STATE_RESERVED_END
        )

    def test_saved_column_wraps_from_first_bg_map_back_to_9800(self):
        # Warehouse starts at $9B88. Its added column is $9B90 and rows four
        # onward cross the hardware tile-map boundary $9BFF -> $9800.
        self.assertIn(
            bytes.fromhex("7CFE9C20023E9867"),
            service_menus._save_support_bytes(),
        )
        self.assertIn(
            bytes.fromhex("7AFE9C20023E9857"),
            service_menus._restore_support_bytes(),
        )

    def test_saved_column_wraps_horizontally_inside_one_bg_row(self):
        # The floor-items fixture places the popup at row 14, x=28. Its added
        # column is row 14, x=4 ($99C4), not row 15, x=4 ($99E4).
        self.assertIn(
            bytes.fromhex(
                "7BE6E06F7BC608E61FB5EAD4D96F7AEAD5D967"
            ),
            service_menus._save_support_bytes(),
        )
        restore = service_menus._restore_support_bytes()
        self.assertIn(
            bytes.fromhex(
                "FAD4D96FFAD5D9677DE6E05F7DD608E61FB36F"
            ),
            restore,
        )
        self.assertIn(
            bytes.fromhex("7DE6E05F7DC606E61FB36F"),
            restore,
        )

    def test_controller_exit_chains_both_popup_cleanup_owners(self):
        raw = service_menus._service_exit_helper_bytes()
        floor = stairs_menu.floor_cleanup_address()
        restore = service_menus.service_restore_address()
        self.assertEqual(
            bytes((
                0xCD, floor & 0xFF, floor >> 8,
                0xCD, restore & 0xFF, restore >> 8,
                0xC9,
            )),
            raw,
        )

    def test_town_refresh_runs_guarded_column_cleanup(self):
        hook = extract.file_offset(
            service_menus.SERVICE_LOOP_BANK,
            service_menus.SERVICE_LOOP_CALL_ADDRESS,
        )
        self.assertEqual(
            bytes((
                0xCD,
                service_menus.SERVICE_LOOP_TRAMPOLINE_ADDRESS & 0xFF,
                service_menus.SERVICE_LOOP_TRAMPOLINE_ADDRESS >> 8,
            )),
            self.output[hook:hook + 3],
        )
        trampoline = extract.file_offset(
            service_menus.SERVICE_LOOP_BANK,
            service_menus.SERVICE_LOOP_TRAMPOLINE_ADDRESS,
        )
        self.assertEqual(
            service_menus._service_loop_trampoline(),
            self.output[
                trampoline:
                trampoline + len(service_menus._service_loop_trampoline())
            ],
        )

    def test_installer_changes_only_chained_helpers_reservation_and_checksums(self):
        allowed = {
            offset
            for start, end in service_menus.owned_ranges()
            for offset in range(start, end)
        } | {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        changed = {
            offset
            for offset, pair in enumerate(zip(self.stairs, self.output))
            if pair[0] != pair[1]
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)
        cartridge.verify_checksums(self.output)

    def test_chained_source_and_padding_guards_fail_closed(self):
        for address in (
            service_menus.LOAD_HELPER_ADDRESS,
            service_menus.COPY_HELPER_ADDRESS,
            service_menus.SUPPORT_ADDRESS,
        ):
            damaged = bytearray(self.stairs)
            damaged[extract.file_offset(service_menus.RUNTIME_BANK, address)] ^= 1
            with self.subTest(address=address):
                with self.assertRaises(service_menus.ServiceMenuError):
                    service_menus.install(damaged)

        for address in (
            service_menus.SERVICE_LOOP_CALL_ADDRESS,
            service_menus.SERVICE_LOOP_TRAMPOLINE_ADDRESS,
        ):
            damaged = bytearray(self.stairs)
            damaged[
                extract.file_offset(service_menus.SERVICE_LOOP_BANK, address)
            ] ^= 1
            with self.subTest(address=address):
                with self.assertRaises(service_menus.ServiceMenuError):
                    service_menus.install(damaged)


class PyBoyServiceMenuTests(unittest.TestCase):
    SCRATCH_FLAT_BASE = service_menus.POPUP_STATE_WRAM_BANK * 0x1000
    SCRATCH_COLUMN = (
        SCRATCH_FLAT_BASE + service_menus.SAVED_COLUMN_ADDRESS - 0xD000
    )
    SCRATCH_DESTINATION = (
        SCRATCH_FLAT_BASE + service_menus.SAVED_DESTINATION_ADDRESS - 0xD000
    )
    SCRATCH_ROWS = (
        SCRATCH_FLAT_BASE + service_menus.SAVED_ROWS_ADDRESS - 0xD000
    )
    SCRATCH_FLAG = (
        SCRATCH_FLAT_BASE + service_menus.SAVED_FLAG_ADDRESS - 0xD000
    )
    SCRATCH_FLAG_END = (
        SCRATCH_FLAT_BASE + service_menus.SAVED_FLAG_END_ADDRESS - 0xD000
    )
    BLACKSMITH_FLAG = (
        SCRATCH_FLAT_BASE + service_menus.BLACKSMITH_TILE_FLAG_ADDRESS - 0xD000
    )

    SYNTHESIS_RASTER = (
        ".####............#...#...............#.......",
        "#................#...#.......................",
        "#.....#..#.###..###..###...##...###.##...###.",
        ".###..#..#.#..#..#...#..#.#..#.#.....#..#....",
        "....#.#..#.#..#..#...#..#.####..##...#...##..",
        "....#..###.#..#..#...#..#.#.......#..#.....#.",
        "####.....#.#..#...##.#..#..###.###..###.###..",
        ".......##....................................",
    )
    LOWER_D_RASTER = (
        "...#.", "...#.", ".###.", "#..#.", "#..#.", "#..#.", ".###.", ".....",
    )
    WAREHOUSE_EDGE = (
        "........", "######..", ".....##.",
        *("......#." for _ in range(58)),
        ".....##.", "######..", "........",
    )

    @classmethod
    def setUpClass(cls):
        cls.source, _rom = _original_rom()
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "service-menus.gbc"
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
                "could not build service-menu fixture:\n"
                + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    @staticmethod
    def _ink(pyboy, x, y):
        return pyboy.screen.image.getpixel((x, y))[:3] == (0, 0, 0)

    def _assert_raster(self, pyboy, x, y, raster):
        for row, expected in enumerate(raster):
            for column, pixel in enumerate(expected):
                self.assertEqual(
                    pixel == "#",
                    self._ink(pyboy, x + column, y + row),
                    "pixel mismatch at (%d,%d)" % (x + column, y + row),
                )

    @staticmethod
    def _vram(pyboy, address, bank):
        old_bank = pyboy.memory[0xFF4F]
        try:
            pyboy.memory[0xFF4F] = bank
            return pyboy.memory[address]
        finally:
            pyboy.memory[0xFF4F] = old_bank

    @staticmethod
    def _popup_row(destination, row):
        address = destination + row * 32
        if address >= 0x9C00 and destination < 0x9C00:
            address -= 0x400
        return address

    def _active(self, pyboy):
        return (
            pyboy_route.work_read_byte(pyboy, self.SCRATCH_FLAG) == 0xA5
            and pyboy_route.work_read_byte(pyboy, self.SCRATCH_FLAG_END) == 0x5A
        )

    def _capture_column(self, pyboy, expected_destination=None, expected_rows=None):
        self.assertTrue(self._active(pyboy))
        raw = pyboy_route.work_read(pyboy, self.SCRATCH_DESTINATION, 2)
        destination = int.from_bytes(raw, "little")
        rows = pyboy_route.work_read_byte(pyboy, self.SCRATCH_ROWS)
        if expected_destination is not None:
            self.assertEqual(expected_destination, destination)
        if expected_rows is not None:
            self.assertEqual(expected_rows, rows)
        self.assertGreaterEqual(rows, 2)
        self.assertLessEqual(rows, 10)
        saved = pyboy_route.work_read(pyboy, self.SCRATCH_COLUMN, rows * 2)
        for row in range(rows):
            address = self._popup_row(destination, row)
            expected_tile = 0x7E if row in (0, rows - 1) else 0x7F
            expected_attribute = 0xEF if row == rows - 1 else 0xAF
            self.assertEqual(expected_tile, self._vram(pyboy, address, 0))
            self.assertEqual(expected_attribute, self._vram(pyboy, address, 1))
        return destination, rows, saved

    def _assert_restored(self, pyboy, capture):
        destination, rows, saved = capture
        self.assertFalse(self._active(pyboy))
        for row in range(rows):
            address = self._popup_row(destination, row)
            self.assertEqual(saved[row * 2], self._vram(pyboy, address, 0))
            self.assertEqual(saved[row * 2 + 1], self._vram(pyboy, address, 1))

    def _start(self, row, state_key="state", hash_key="state_sha1"):
        state = ROOT / row[state_key]
        if not state.is_file():
            self.skipTest("service-menu state fixture is unavailable")
        self.assertEqual(row[hash_key], sha1(state.read_bytes()).hexdigest())
        return pyboy_route.start(self.PyBoy, self.localized, state)

    def _exercise_lifecycle(
        self, row, initial_actions, option_count, *, auto_advance=False,
        expected_rows=None, blacksmith=False,
    ):
        pyboy = self._start(row)
        opened = None
        capture = None
        screens = []
        try:
            for frame in range(2401):
                if frame in initial_actions:
                    pyboy_route.press(pyboy, initial_actions[frame])
                if auto_advance and opened is None and frame % 70 == 0:
                    pyboy_route.press(pyboy, "a")
                if opened is not None:
                    relative = frame - opened
                    for index in range(1, option_count):
                        if relative == 100 + (index - 1) * 120:
                            pyboy_route.press(pyboy, "down")
                    if relative == (520 if blacksmith else 500):
                        pyboy_route.press(pyboy, "b")
                pyboy.tick()
                if opened is None and self._active(pyboy):
                    opened = frame
                if opened is not None and frame == opened + 60:
                    capture = self._capture_column(
                        pyboy, expected_rows=expected_rows
                    )
                    if blacksmith:
                        self.assertEqual(
                            0xA6,
                            pyboy_route.work_read_byte(pyboy, self.BLACKSMITH_FLAG),
                        )
                    screens.append(pyboy.screen.image.tobytes())
                elif opened is not None and frame in {
                    opened + 180, opened + 300, opened + 420, opened + 480,
                }:
                    screens.append(pyboy.screen.image.tobytes())
                if (
                    capture is not None and frame > opened + 560
                    and not self._active(pyboy)
                ):
                    self._assert_restored(pyboy, capture)
                    if blacksmith:
                        self.assertEqual(
                            0,
                            pyboy_route.work_read_byte(pyboy, self.BLACKSMITH_FLAG),
                        )
                    self.assertGreaterEqual(len(set(screens)), option_count)
                    return
            self.fail("service menu did not complete its PyBoy lifecycle")
        finally:
            pyboy.stop(save=False)

    def test_blacksmith_info_synthesis_matches_approved_pixels(self):
        row = FIXTURE["blacksmith_info"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Blacksmith Info menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
        try:
            pyboy_route.run_frames(
                pyboy, 481,
                ((60, "a"), (150, "down"), (210, "down"),
                 (270, "down"), (330, "a")),
            )
            self._assert_raster(pyboy, 24, 48, self.SYNTHESIS_RASTER)
            for y in range(72, 80):
                for x in (*range(16, 24), *range(64, 72)):
                    self.assertFalse(self._ink(pyboy, x, y))
        finally:
            pyboy.stop(save=False)

    def test_blacksmith_info_is_widened_traversed_and_dismissed_cleanly(self):
        self._exercise_lifecycle(
            FIXTURE["blacksmith_info"],
            {60: "a", 150: "down", 210: "down", 270: "down", 330: "a"},
            len(FIXTURE["blacksmith_info"]["options"]),
            expected_rows=9,
            blacksmith=True,
        )

    def test_rescue_popup_is_rebuilt_wide_and_dismisses_cleanly(self):
        self._exercise_lifecycle(
            FIXTURE["rescue"],
            {60: "b", 160: "a", 260: "a", 360: "a", 460: "a", 560: "a"},
            len(FIXTURE["rescue"]["options"]),
        )

    def test_rescue_password_selection_restores_the_added_column(self):
        pyboy = self._start(FIXTURE["rescue"])
        capture = None
        actions = {
            60: "b", 160: "a", 260: "a", 360: "a", 460: "a", 560: "a",
            720: "down", 760: "a",
        }
        try:
            for frame in range(1001):
                if frame in actions:
                    pyboy_route.press(pyboy, actions[frame])
                pyboy.tick()
                if frame == 700:
                    capture = self._capture_column(pyboy, expected_destination=0x9950)
            self.assertIsNotNone(capture)
            self._assert_restored(pyboy, capture)
        finally:
            pyboy.stop(save=False)

    def test_rescue_password_final_d_matches_approved_pixels(self):
        pyboy = self._start(FIXTURE["rescue"])
        try:
            pyboy_route.run_frames(
                pyboy, 791,
                ((60, "b"), (160, "a"), (260, "a"), (360, "a"),
                 (460, "a"), (560, "a"), (720, "down")),
            )
            self._assert_raster(pyboy, 61, 37, self.LOWER_D_RASTER)
        finally:
            pyboy.stop(save=False)

    def test_post_rescue_password_is_wide_with_literal_pixels(self):
        state = ROOT / "SaveStates" / "at-rescue.state"
        if not state.is_file():
            self.skipTest("post-rescue menu fixture is unavailable")
        self.assertEqual(
            "ac90aecb1808dc2e27777481faa896bac48d4b0a",
            sha1(state.read_bytes()).hexdigest(),
        )
        pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
        menu_at = None
        try:
            for frame in range(5001):
                if frame == 60:
                    pyboy_route.press(pyboy, "down")
                elif frame == 120:
                    pyboy_route.press(pyboy, "a")
                elif menu_at is None and frame >= 240 and frame % 90 == 0:
                    pyboy_route.press(pyboy, "a")
                if menu_at is not None and frame - menu_at in (130, 160, 190):
                    pyboy_route.press(pyboy, "down")
                pyboy.tick()
                target = bytes(pyboy.memory[0xFFB0:0xFFBA])
                if (
                    menu_at is None and target[0] == 4
                    and target[2:] == bytes.fromhex("80077F0792079E07")
                ):
                    menu_at = frame
                if menu_at is not None and frame - menu_at in (120, 155, 185, 215):
                    self.assertTrue(self._active(pyboy))
                    self._assert_raster(pyboy, 61, 39, self.LOWER_D_RASTER)
                    selected = {120: 1, 155: 2, 185: 3, 215: 4}[frame - menu_at]
                    ranges = ((24, 33), (36, 45), (48, 57), (60, 69))
                    for index, (top, bottom) in enumerate(ranges, 1):
                        ink = sum(
                            self._ink(pyboy, x, y)
                            for x in range(16, 23) for y in range(top, bottom + 1)
                        )
                        self.assertGreaterEqual(ink, 8) if index == selected else self.assertEqual(0, ink)
                    self.assertEqual(
                        0,
                        sum(self._ink(pyboy, x, y)
                            for x in range(66, 72) for y in range(22, 70)),
                    )
                    if frame - menu_at == 215:
                        return
            self.fail("post-rescue delivery menu was not reached")
        finally:
            pyboy.stop(save=False)

    def test_warehouse_popup_is_opened_wide_and_dismisses_cleanly(self):
        self._exercise_lifecycle(
            FIXTURE["warehouse"], {}, len(FIXTURE["warehouse"]["options"]),
            auto_advance=True,
        )

    def test_warehouse_floor_items_keep_the_literal_right_border(self):
        row = FIXTURE["warehouse"]
        cases = (
            (
                row["floor_items_state"],
                row["floor_items_state_sha1"],
                "99C4",
            ),
            (
                row["floor_items_reenter_state"],
                row["floor_items_reenter_state_sha1"],
                "9B90",
            ),
        )
        for relative, expected_sha1, destination in cases:
            with self.subTest(state=relative):
                state = ROOT / relative
                if not state.is_file():
                    self.skipTest("warehouse floor-items fixture is unavailable")
                self.assertEqual(
                    expected_sha1,
                    sha1(state.read_bytes()).hexdigest(),
                )
                pyboy = pyboy_route.start(self.PyBoy, self.localized, state)
                opened = None
                capture = None
                try:
                    for frame in range(1201):
                        if frame == 180:
                            pyboy_route.press(pyboy, "a")
                        if opened is not None:
                            relative_frame = frame - opened
                            if relative_frame in (100, 220, 340):
                                pyboy_route.press(pyboy, "down")
                            elif relative_frame == 500:
                                pyboy_route.press(pyboy, "b")
                        pyboy.tick()
                        if opened is None and self._active(pyboy):
                            opened = frame
                        if opened is not None and frame == opened + 60:
                            capture = self._capture_column(
                                pyboy, int(destination, 16), 8
                            )
                            self._assert_raster(pyboy, 72, 16, self.WAREHOUSE_EDGE)
                        elif opened is not None and frame - opened in (180, 300, 420):
                            self._assert_raster(pyboy, 72, 16, self.WAREHOUSE_EDGE)
                        if capture is not None and frame > opened + 560 and not self._active(pyboy):
                            self._assert_restored(pyboy, capture)
                            break
                    else:
                        self.fail("warehouse floor-items route did not close")
                finally:
                    pyboy.stop(save=False)

    def test_bank_popup_is_widened_traversed_and_dismissed_cleanly(self):
        self._exercise_lifecycle(
            FIXTURE["bank"], {60: "a", 160: "a"},
            len(FIXTURE["bank"]["options"]),
        )


if __name__ == "__main__":
    unittest.main()
