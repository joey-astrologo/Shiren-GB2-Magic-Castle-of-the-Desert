from hashlib import sha1
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cartridge
import extract
import service_menus
import stairs_menu


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "service_menus.json").read_text(
        encoding="utf-8"
    )
)


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
            bytes.fromhex("FAD9D80707074F2121D811120006077EE6F7B177190520F7"),
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
                "7BE6E06F7BC608E61FB5EAD4D86F7AEAD5D867"
            ),
            service_menus._save_support_bytes(),
        )
        restore = service_menus._restore_support_bytes()
        self.assertIn(
            bytes.fromhex(
                "FAD4D86FFAD5D8677DE6E05F7DD608E61FB36F"
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


class MesenServiceMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = (
            os.environ.get("MESEN_BIN"),
            shutil.which("Mesen"),
            shutil.which("mesen"),
            "/Applications/Mesen.app/Contents/MacOS/Mesen",
        )
        cls.mesen = next(
            (Path(path) for path in candidates if path and Path(path).is_file()),
            None,
        )
        if cls.mesen is None:
            raise unittest.SkipTest("Mesen test-runner executable is unavailable")
        cls.source, _rom = _original_rom()
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

    def test_blacksmith_info_synthesis_matches_approved_pixels(self):
        row = FIXTURE["blacksmith_info"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Blacksmith Info menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_BLACKSMITH_INFO_MSS"] = str(state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(
                    ROOT
                    / "tests"
                    / "mesen_service_menu_blacksmith_info_pixels.lua"
                ),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS Blacksmith Info Synthesis and clean Quit row match approved pixels",
            output,
        )

    def test_blacksmith_info_is_widened_traversed_and_dismissed_cleanly(self):
        row = FIXTURE["blacksmith_info"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Blacksmith Info menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_BLACKSMITH_INFO_MSS"] = str(state)
        for label in ("forge", "repair", "synthesis", "remove", "quit", "closed"):
            env["GB2_BLACKSMITH_EXPECTED_" + label.upper() + "_SCREEN"] = row[
                label + "_screen"
            ]
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_blacksmith_info.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        for label in ("Forge", "Repair", "Synthesis", "Remove", "Quit", "closed"):
            self.assertIn(
                "service-menu Blacksmith %s screen=%s"
                % (label, row[label.lower() + "_screen"]),
                output,
            )
        self.assertIn(
            "PASS Blacksmith Info widened, traversed, and dismissed", output
        )

    def test_rescue_popup_is_rebuilt_wide_and_dismisses_cleanly(self):
        row = FIXTURE["rescue"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Rescue Team menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_RESCUE_ENTRY_MSS"] = str(state)
        env["GB2_RESCUE_EXPECTED_CONFIRM_SCREEN"] = row[
            "confirmation_screen"
        ]
        env["GB2_RESCUE_EXPECTED_WIDE_SCREEN"] = row["wide_screen"]
        env["GB2_RESCUE_EXPECTED_CLOSED_SCREEN"] = row["closed_screen"]
        env["GB2_RESCUE_EXPECTED_PASSWORD_SCREEN"] = row["password_screen"]
        env["GB2_RESCUE_EXPECTED_QUIT_SCREEN"] = row["quit_screen"]
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_rescue.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "service-menu Rescue confirmation screen="
            + row["confirmation_screen"],
            output,
        )
        self.assertIn(
            "service-menu Rescue wide screen=" + row["wide_screen"], output
        )
        self.assertIn(
            "service-menu Rescue Password screen=" + row["password_screen"],
            output,
        )
        self.assertIn(
            "service-menu Rescue Quit screen=" + row["quit_screen"], output
        )
        self.assertIn(
            "service-menu Rescue closed screen=" + row["closed_screen"], output
        )
        self.assertIn(
            "PASS Rescue confirmation and service popup rebuilt and dismissed",
            output,
        )

    def test_rescue_password_selection_restores_the_added_column(self):
        row = FIXTURE["rescue"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Rescue Team menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_RESCUE_ENTRY_MSS"] = str(state)
        env["GB2_RESCUE_EXPECTED_TRANSITION_SCREEN"] = row["selected_screen"]
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_rescue_select.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "service-menu Rescue selected screen="
            + row["selected_screen"]
            + " saved=9950 flag=00",
            output,
        )
        self.assertIn(
            "PASS Rescue Password selection restores widened popup column",
            output,
        )

    def test_rescue_password_final_d_matches_approved_pixels(self):
        row = FIXTURE["rescue"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Rescue Team menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_RESCUE_ENTRY_MSS"] = str(state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(
                    ROOT
                    / "tests"
                    / "mesen_service_menu_rescue_password_pixels.lua"
                ),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS Rescue Password final d matches the approved raster",
            output,
        )

    def test_post_rescue_password_is_wide_with_literal_pixels(self):
        state = ROOT / "SaveStates" / "at-rescue.mss"
        if not state.is_file():
            self.skipTest("post-rescue menu fixture is unavailable")
        self.assertEqual(
            "9adf777f9f86a18ba025d32edf1c5fcae02ec326",
            sha1(state.read_bytes()).hexdigest(),
        )
        env = os.environ.copy()
        env["GB2_AT_RESCUE_MSS"] = str(state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_post_rescue.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=90,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS post-rescue popup survives every live cursor position",
            output,
        )

    def test_warehouse_popup_is_opened_wide_and_dismisses_cleanly(self):
        row = FIXTURE["warehouse"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("warehouse menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_WAREHOUSE_MENU_MSS"] = str(state)
        env["GB2_WAREHOUSE_EXPECTED_WIDE_SCREEN"] = row["wide_screen"]
        env["GB2_WAREHOUSE_EXPECTED_CLOSED_SCREEN"] = row["closed_screen"]
        env["GB2_WAREHOUSE_EXPECTED_WITHDRAW_SCREEN"] = row["withdraw_screen"]
        env["GB2_WAREHOUSE_EXPECTED_TRASH_SCREEN"] = row["trash_screen"]
        env["GB2_WAREHOUSE_EXPECTED_QUIT_SCREEN"] = row["quit_screen"]
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_warehouse.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "service-menu Warehouse wide screen=" + row["wide_screen"], output
        )
        for label in ("Withdraw", "Trash", "Quit"):
            self.assertIn(
                "service-menu Warehouse %s screen=%s"
                % (label, row[label.lower() + "_screen"]),
                output,
            )
        self.assertIn(
            "service-menu Warehouse closed screen=" + row["closed_screen"], output
        )
        self.assertIn(
            "PASS Warehouse service popup widened and dismissed", output
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
                env = os.environ.copy()
                env["GB2_WAREHOUSE_ITEMS_MSS"] = str(state)
                env["GB2_WAREHOUSE_EXPECTED_DESTINATION"] = destination
                result = subprocess.run(
                    [
                        str(self.mesen),
                        "--testrunner",
                        "--enablestdout",
                        "--novideo",
                        "--noaudio",
                        str(self.localized),
                        str(
                            ROOT
                            / "tests"
                            / "mesen_service_menu_warehouse_floor_items.lua"
                        ),
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=60,
                )
                output = result.stdout + result.stderr
                self.assertEqual(0, result.returncode, output[-8000:])
                self.assertIn(
                    "PASS Warehouse floor-items popup keeps and restores "
                    "its literal right edge",
                    output,
                )

    def test_bank_popup_is_widened_traversed_and_dismissed_cleanly(self):
        row = FIXTURE["bank"]
        state = ROOT / row["state"]
        if not state.is_file():
            self.skipTest("Bank Teller menu fixture is unavailable")
        self.assertEqual(row["state_sha1"], sha1(state.read_bytes()).hexdigest())
        env = os.environ.copy()
        env["GB2_BANK_TELLER_MSS"] = str(state)
        for label in ("deposit", "withdraw", "balance", "quit", "closed"):
            env["GB2_BANK_EXPECTED_" + label.upper() + "_SCREEN"] = row[
                label + "_screen"
            ]
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_service_menu_bank.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        for label in ("Deposit", "Withdraw", "Balance", "Quit", "closed"):
            self.assertIn(
                "service-menu Bank %s screen=%s"
                % (label, row[label.lower() + "_screen"]),
                output,
            )
        self.assertIn(
            "PASS Bank service popup widened, traversed, and dismissed",
            output,
        )


if __name__ == "__main__":
    unittest.main()
