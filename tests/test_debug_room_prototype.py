"""Production debug menus compared with the frozen pre-integration baseline."""
from hashlib import sha1
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import cartridge
import debug_menus
import capture_dialogue
import debug_room_prototype as prototype
import english_font
import font
import pyboy_route as route
import service_menus
import stairs_menu

ROM = ROOT / "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates/debug-room.state"
LABELS = ("Weapons/Shields", "Bracelets/Grass", "Scrolls/Staves", "Pots/Arrows", "Meat")
MAIN_LABELS = ("Give Item", "Set Flag", "Trash")
WEAPONS_LABELS = ("Weapon 1", "Weapon 2", "Shield 1", "Shield 2")
BRACELETS_LABELS = ("Bracelet 1", "Bracelet 2", "Grass")
SCROLLS_LABELS = ("Scroll 1", "Scroll 2", "Staff 1", "Staff 2")
POTS_LABELS = ("Pot", "Arrow")
MEAT1_LABELS = ("Next Page", "Batch 1 (20)", "Batch 2 (18)", "Batch 3 (18)", "Batch 4 (18)")
MEAT2_LABELS = ("Next Page", "Batch 5 (18)", "Batch 6 (20)", "Batch 7 (18)", "Batch 8 (18)")
MEAT3_LABELS = ("Next Page", "Batch 9 (18)", "Batch 10 (19)", "Batch 11 (18)", "Batch 12 (6)")
FLAGS_LABELS = ("Enable Mamo", "Enable Zenmaiger", "Open Furnace", "Moai Leaves")
# Independent layout contract, not imported from the installer or its artwork.
MENUS = {"category": (13, 11, LABELS, 0), "main": (9, 7, MAIN_LABELS, 1),
         "weapons": (8, 9, WEAPONS_LABELS, 2), "bracelets": (10, 7, BRACELETS_LABELS, 3),
         "scrolls": (8, 9, SCROLLS_LABELS, 4), "pots": (7, 5, POTS_LABELS, 5),
         "meat1": (11, 11, MEAT1_LABELS, 6), "meat2": (11, 11, MEAT2_LABELS, 7), "meat3": (11, 11, MEAT3_LABELS, 8), "flags": (13, 9, FLAGS_LABELS, 9)}
SCRIPT_POSITIONS = {"main": b"\xA5\x4A", "category": b"\xBF\x4A",
                    "weapons": b"\xE4\x4A", "bracelets": b"\x05\x4B", "scrolls": b"\x22\x4B",
                    "pots": b"\x43\x4B", "meat1": b"\x5C\x4B", "meat2": b"\x81\x4B", "meat3": b"\xA6\x4B", "flags": b"\xCB\x4B"}


def press(p, button):
    p.button(button, 5)
    p.tick(90)


def open_debug(p):
    p.gameshark.add("019F2FC1")
    press(p, "a")
    p.tick(400)
    p.gameshark.remove("019F2FC1")


def open_menu(p, menu):
    open_debug(p)
    for button in {"main": (), "flags": ("down", "a"), "category": ("a",), "weapons": ("a", "a"),
                   "bracelets": ("a", "down", "a"), "scrolls": ("a", "down", "down", "a"),
                   "pots": ("a", "down", "down", "down", "a"), "meat1": ("a", "up", "a"), "meat2": ("a", "up", "a", "a"), "meat3": ("a", "up", "a", "a", "a")}[menu]:
        press(p, button)


def vram(p):
    old = p.memory[0xFF4F]
    try:
        result = []
        for bank in (0, 1):
            p.memory[0xFF4F] = bank
            result.append(bytes(p.memory[0x8000:0xA000]))
        return result
    finally:
        p.memory[0xFF4F] = old


def inventory(p):
    work = route.flat_work_ram(p)
    return {slot: work[0x2482 + slot * 8:0x248A + slot * 8]
            for slot in work[0x12C1:0x12D5] if slot < 128}


def popup_returns(p):
    """Observe teardown before the event interpreter can draw another menu."""
    records = []

    def returned(_):
        records.append((bytes(p.memory[0xC3BE:0xC3C0]), bytes(p.memory[0xC14E:0xC155]),
                        p.register_file.SP, p.memory[0xFF70], p.memory[0xFF4F], p.memory[0xC4DA],
                        sha1(route.work_read(p, 0x7900, 0x310)).hexdigest(),
                        tuple(sha1(plane).hexdigest() for plane in vram(p))))

    p.hook_register(5, 0x58EE, returned, None)
    return records


def rectangle(p, origin, columns=13, rows=11):
    planes = vram(p)
    pixels = [[None] * (columns * 8) for _ in range(rows * 8)]
    base = origin & ~0x3FF
    for row in range(rows):
        for col in range(columns):
            address = base + (((origin + row * 32) & 0x3E0) | ((origin + col) & 31))
            tile, attr = (plane[address - 0x8000] for plane in planes)
            signed = tile if tile < 128 else tile - 256
            start = 0x1000 + signed * 16
            raster = font.decode_2bpp_slices(planes[(attr >> 3) & 1][start:start + 16], 8)
            for y in range(8):
                for x in range(8):
                    pixels[row * 8 + y][col * 8 + x] = raster[7-y if attr & 64 else y][7-x if attr & 32 else x]
    return pixels


def expected(style, selection, menu="category"):
    # Independent full pixel oracle: literal native border and cursor, approved
    # font source, no generated tile map or tile IDs from the implementation.
    columns, rows, labels, _ = MENUS[menu]
    width, height = columns * 8, rows * 8
    pixels = [[1] * width for _ in range(height)]
    corner = ("11111111", "12333333", "13322222", *(["13211111"] * 5))
    for y in range(8):
        for x in range(8):
            value = int(corner[y][x])
            pixels[y][x] = pixels[y][width-1-x] = value
            pixels[height-1-y][x] = pixels[height-1-y][width-1-x] = value
    for x in range(8, width - 8):
        pixels[1][x] = pixels[height-2][x] = 3
        pixels[2][x] = pixels[height-3][x] = 2
    for y in range(8, height - 8):
        pixels[y][1] = pixels[y][width-2] = 3
        pixels[y][2] = pixels[y][width-3] = 2
    approved = english_font.load_approved(style=style)
    for index, text in enumerate(labels):
        left, top = 16, 8 + index * 16
        for char in text:
            for y, row in enumerate(english_font.glyph_pixels(approved.rows[char], style)):
                for x, color in enumerate(row):
                    if color != 1:
                        pixels[top + y][left + x] = color
            left += approved.advances[char]
    # The arrow occupies rows 0..6, with a one-pixel tip at each end.
    cursor = ("13111111", "13311111", "13331111", "13333111",
              "13331111", "13311111", "13111111", "11111111")
    for y, row in enumerate(cursor):
        pixels[8 + selection * 16 + y][8:16] = map(int, row)
    return pixels


class DebugRoomPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ROM.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching source ROM and debug-room fixture required")
        cls.PyBoy = capture_dialogue._pyboy_class()
        cls.tmp = tempfile.TemporaryDirectory(prefix="gb2-debug-test-")
        cls.directory = Path(cls.tmp.name)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/build.py"), str(ROM), str(ROOT / "script/en"),
             str(cls.directory / "baseline.gbc"), "--font-style", "both"],
            cwd=ROOT, capture_output=True, text=True, timeout=90,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.baseline, cls.experimental, cls.reports = {}, {}, {}
        for style in ("classic", "shadowed"):
            cls.baseline[style] = cls.directory / ("baseline-%s-font.gbc" % style)
            cls.experimental[style] = cls.directory / ("experiment-%s-font.gbc" % style)
            # The CLI now installs debug menus. Save that actual production
            # output, then reconstruct the earlier comparison ROM only inside
            # this test by restoring the two explicitly owned spans.
            integrated = cls.baseline[style].read_bytes()
            baseline = bytearray(integrated)
            first, last = prototype.offset(254, 0x5000), prototype.offset(254, 0x7F00)
            baseline[first:last] = bytes(last - first)
            hook = prototype.offset(5, 0x58E6)
            baseline[hook:hook + 8] = bytes.fromhex("3E12211D40CDAC09")
            cartridge.fix_checksums(baseline)
            if sha1(baseline).hexdigest() != prototype.BASELINE_SHA1[style]:
                raise AssertionError("pre-integration comparison ROM changed; review its new baseline")
            patched, cls.reports[style] = prototype.install(baseline)
            if patched != integrated:
                raise AssertionError("normal build differs from the accepted debug-menu runtime")
            cls.baseline[style].write_bytes(baseline)
            cls.experimental[style].write_bytes(integrated)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def start(self, path, state=STATE):
        p = route.start(self.PyBoy, path, state)
        self.addCleanup(p.stop, save=False)
        return p

    def assert_active_menu(self, baseline, experiment, style, menu, reference=None):
        columns, rows, _, kind = MENUS[menu]
        origin = int.from_bytes(route.work_read(experiment, 0x5A00, 2), "little")
        self.assertEqual(kind, route.work_read(experiment, 0x5A03)[0])
        self.assertEqual(expected(style, experiment.memory[0xC14F], menu),
                         rectangle(experiment, origin, columns, rows))
        # Different artwork is intentional only while a private popup is live.
        # Check every other byte in both VRAM banks, including all map cells
        # vacated when the larger category frame closes into the smaller main.
        outside = []
        for snapshot in (vram(baseline) if reference is None else reference, vram(experiment)):
            planes = [bytearray(plane) for plane in snapshot]
            planes[0][0x900:0xC10] = bytes(0x310)
            for row in range(rows):
                for col in range(columns):
                    address = 0x9800 + (((origin + row * 32) & 0x3E0) | ((origin + col) & 31))
                    for plane in planes:
                        plane[address - 0x8000] = 0
            outside.append(planes)
        self.assertEqual(outside[0], outside[1])

    def test_production_installer_is_guarded_and_disjoint_from_other_owners(self):
        for style in self.baseline:
            baseline, patched = self.baseline[style].read_bytes(), self.experimental[style].read_bytes()
            self.assertEqual(prototype.BASELINE_SHA1[style], sha1(baseline).hexdigest())
            owned = ((prototype.offset(5, 0x58E6), prototype.offset(5, 0x58EE)),
                     (prototype.offset(254, 0x5000), prototype.offset(254, 0x7F00)))
            allowed = {0x14D, 0x14E, 0x14F}
            for start, end in owned:
                allowed.update(range(start, end))
                for other_start, other_end in (*stairs_menu.owned_ranges(), *service_menus.owned_ranges()):
                    self.assertTrue(end <= other_start or other_end <= start)
            self.assertTrue(all(i in allowed for i, (a,b) in enumerate(zip(baseline, patched)) if a != b))
            for address in (prototype.offset(5, 0x58E6), prototype.offset(18, 0x406A),
                            prototype.offset(254, 0x5800), prototype.offset(254, 0x6300),
                            prototype.offset(254, 0x6700), prototype.offset(254, 0x6B00),
                            prototype.offset(254, 0x5140), prototype.offset(254, 0x6F00),
                            prototype.offset(254, 0x7E00),
                            prototype.offset(3, 0x4AE2),
                            prototype.offset(3, 0x69E9),
                            prototype.offset(16, 0x5D1A),
                            prototype.offset(16, 0x5E38),
                            prototype.offset(16, 0x5F86),
                            *(debug_menus.offset(bank, address)
                              for bank, first, last, _, _ in debug_menus.NATIVE_DEPENDENCIES
                              for address in (first, last - 1))):
                bad = bytearray(baseline)
                bad[address] ^= 1
                with self.assertRaises(debug_menus.DebugMenuError):
                    debug_menus.install(bad)
            for bad in (baseline[:-1], baseline + b"\0", patched):
                with self.assertRaises(debug_menus.DebugMenuError):
                    debug_menus.install(bad)

    def test_supplied_open_staircase_restores_its_real_saved_column(self):
        fixture = json.loads((ROOT / "tests/fixtures/debug_room.json").read_text())
        for capture in (fixture, fixture["inventory_room"]):
            with self.subTest(state=capture["state"]):
                self._check_open_staircase(capture)

    def _check_open_staircase(self, fixture):
        state = ROOT / fixture["state"]
        self.assertEqual(fixture["state_sha1"], sha1(state.read_bytes()).hexdigest())
        saved = fixture["open_stairs"]
        cells = bytes.fromhex(saved["saved_cells_hex"])
        destination = saved["saved_destination"]
        for builds in (self.baseline, self.experimental):
            for style, path in builds.items():
                with self.subTest(rom=path.name):
                    p = self.start(path, state)
                    self.assertEqual(bytes.fromhex(saved["marker_hex"]), route.work_read(p, 0x59F6, 2))
                    self.assertEqual(cells, route.work_read(p, 0x59E0, 10))
                    before = vram(p)
                    for bank, key in ((0, "visible_column_tiles_hex"), (1, "visible_column_attributes_hex")):
                        self.assertEqual(bytes.fromhex(saved[key]), bytes(before[bank][destination + row * 32 - 0x8000] for row in range(5)))
                    press(p, "b")
                    self.assertEqual(b"\0\0", route.work_read(p, 0x59F6, 2))
                    after = vram(p)
                    for bank in (0, 1):
                        self.assertEqual(cells[bank::2], bytes(after[bank][destination + row * 32 - 0x8000] for row in range(5)))

    def test_every_cursor_has_complete_labels_borders_and_blank_gaps_in_both_fonts(self):
        for style, path in self.experimental.items():
            with self.subTest(style=style):
                p = self.start(path)
                open_debug(p)
                route.work_write(p, 0x5B22, b"\xA5" * 16)
                press(p, "a")
                origin = int.from_bytes(route.work_read(p, 0x5A00, 2), "little")
                self.assertEqual(0x9948, origin)
                for selection in range(5):
                    self.assertEqual(selection, p.memory[0xC14F])
                    self.assertEqual(expected(style, selection), rectangle(p, origin))
                    press(p, "down")
                self.assertEqual(0, p.memory[0xC14F])
                press(p, "up")
                self.assertEqual(4, p.memory[0xC14F])
                self.assertEqual(expected(style, 4), rectangle(p, origin))
                press(p, "b")
                self.assertEqual(expected(style, 0, "main"), rectangle(p, origin, 9, 7))
                press(p, "b")
                self.assertEqual(bytes(0x122), route.work_read(p, 0x5A00, 0x122))
                self.assertEqual(b"\xA5" * 16, route.work_read(p, 0x5B22, 16))

    def test_every_navigation_frame_keeps_one_cursor_and_unchanged_text(self):
        for style, path in self.experimental.items():
            for menu in MENUS:
                with self.subTest(style=style, menu=menu):
                    self._check_navigation_frames(path, style, menu)

    def _check_navigation_frames(self, path, style, menu):
        p = self.start(path)
        open_menu(p, menu)
        columns, rows, labels, _ = MENUS[menu]
        box = (8, 16, 8 + columns * 8, 16 + rows * 8)
        count = len(labels)
        initial = p.screen.image.convert("RGB").crop(box)
        palette = {1: initial.getpixel((0, 0)),
                   2: initial.getpixel((1, 1)), 3: initial.getpixel((2, 1))}
        valid = {bytes(component for row in expected(style, selected, menu)
                       for pixel in row for component in palette[pixel])
                 for selected in range(count)}
        immutable_tiles = vram(p)[0][0x900:0xC10]
        # Check every displayed frame, including the first two frames
        # after each press. Settled screenshots hid the original bug.
        for button, duration, frames in (
            *(("down", 5, 16),) * count,
            *(("up", 5, 16),) * count,
            ("down", 150, 160), ("up", 150, 160),
            *(("down", 2, 4), ("up", 2, 4)) * 5,
        ):
            p.button(button, duration)
            selections = set()
            for frame in range(frames):
                p.tick()
                selections.add(p.memory[0xC14F])
                actual = p.screen.image.convert("RGB").crop(box).tobytes()
                self.assertTrue(actual in valid,
                              "%s %s frame %d contains an incomplete cursor or flashing text"
                              % (style, button, frame))
                self.assertEqual(immutable_tiles, vram(p)[0][0x900:0xC10],
                                 "navigation rewrote the shared label/cursor tiles")
            if duration == 150:
                self.assertEqual(set(range(count)), selections, "held direction must repeat and wrap")

    def test_all_five_submenus_and_repeated_cleanup_match_the_baseline(self):
        for style in self.baseline:
            base = self.start(self.baseline[style])
            experiment = self.start(self.experimental[style])
            for p in (base, experiment):
                open_debug(p)
            returned = [popup_returns(p) for p in (base, experiment)]
            for cycle in range(3):
                for choice in range(5):
                    for p in (base, experiment):
                        press(p, "a")
                        for _ in range(choice):
                            press(p, "down")
                        press(p, "a")
                    with self.subTest(style=style, cycle=cycle, choice=choice):
                        self.assert_active_menu(base, experiment, style,
                                                ("weapons", "bracelets", "scrolls", "pots", "meat1")[choice])
                    for p in (base, experiment):
                        press(p, "b")
                        press(p, "b")
                    self.assertEqual(returned[0], returned[1])
                    self.assert_active_menu(base, experiment, style, "main")
            for p in (base, experiment):
                press(p, "b")
            # The extra main-menu drawing can advance Shiren's idle OBJ pose.
            # Preserve the exact comparison of every BG tile/map/attribute and
            # the pre-interpreter return snapshots; no UI storage is excluded.
            self.assertEqual(vram(base), vram(experiment))
            self.assertEqual(returned[0], returned[1])
            # Ordinary Items and Status, including repeated closure, after use.
            for button, mode in zip(
                ("b", "a", "a", "b", "b", "down", "a", "b", "b"),
                (4, 1, 2, 1, 4, 4, 4, 4, 4),
            ):
                for p in (base, experiment):
                    press(p, button)
                    self.assertEqual(mode, p.memory[0xC14E])
                # Extra drawing time can shift the idle actor's OBJ animation.
                # Compare every BG tile, glyph and attribute in both VRAM banks,
                # including off-screen cells, instead of masking an arbitrary
                # part of the screenshot. No UI pixel/storage is excluded.
                self.assertEqual(vram(base), vram(experiment))
                self.assertEqual(route.work_read(base, 0x2480, 0x400),
                                 route.work_read(experiment, 0x2480, 0x400))

    def test_wrapped_background_and_attribute_cells_restore_on_both_edges(self):
        for style in self.baseline:
            for menu in MENUS:
                with self.subTest(style=style, menu=menu):
                    self._check_wrapped_menu(style, menu)

    def _check_wrapped_menu(self, style, menu):
        base, experiment = (self.start(paths[style]) for paths in (self.baseline, self.experimental))
        returned = [popup_returns(p) for p in (base, experiment)]
        underlays = []
        for p in (base, experiment):
            def move_origin(_, p=p):
                if bytes(p.memory[0xC3BE:0xC3C0]) == SCRIPT_POSITIONS[menu]:
                    # Inject at construction, after the gate's scratch scan:
                    # the camera IRQ can undo a scroll forced at gate entry.
                    p.memory[0xFF42] = 0xE0
                    p.memory[0xFF43] = 0xE0
                if p is experiment:
                    underlays.append(vram(p))

            bank, address = ((254, self.reports[style]["symbols"]["Constructor"])
                             if p is experiment else (3, 0x69E9))
            p.hook_register(bank, address, move_origin, None)
            open_menu(p, menu)
        self.assertEqual(0x9BDE, int.from_bytes(route.work_read(experiment, 0x5A00, 2), "little"))
        for _ in MENUS[menu][2]:
            # The forced-scroll probe is sampled before construction. Native
            # construction rereads scroll after drawing and can leave its map
            # at the camera's restored origin; the private constructor must
            # preserve the actual underlay outside the wrapped rectangle. Keep
            # the baseline oracle for native glyph preparation; only the maps
            # use the pre-construction underlay as their independent reference.
            reference = [bytearray(plane) for plane in vram(base)]
            for bank in (0, 1):
                reference[bank][0x1800:] = underlays[-1][bank][0x1800:]
            self.assert_active_menu(base, experiment, style, menu, reference=reference)
            for p in (base, experiment):
                press(p, "down")
        for p in (base, experiment):
            for _ in range({"main": 1, "category": 2, "weapons": 3, "bracelets": 3, "scrolls": 3, "pots": 3, "meat1": 3, "meat2": 4, "meat3": 5, "flags": 2}[menu]):
                press(p, "b")
        self.assertEqual(vram(base), vram(experiment))
        self.assertEqual(returned[0], returned[1])

    def test_main_actions_and_repeated_size_changes_restore_all_owned_storage(self):
        fixture = json.loads((ROOT / "tests/fixtures/debug_room.json").read_text())
        for style in self.baseline:
            for state in (STATE, ROOT / fixture["inventory_room"]["state"]):
                with self.subTest(style=style, state=state.name):
                    base, experiment = (self.start(paths[style], state) for paths in (self.baseline, self.experimental))
                    returned = [popup_returns(p) for p in (base, experiment)]
                    for p in (base, experiment):
                        open_debug(p)
                    self.assert_active_menu(base, experiment, style, "main")
                    for _ in range(5):
                        for p in (base, experiment):
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "weapons")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            press(p, "down")
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "bracelets")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            press(p, "down")
                            press(p, "down")
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "scrolls")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            for _ in range(3):
                                press(p, "down")
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "pots")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            press(p, "up")
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "meat1")
                        for p in (base, experiment):
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "meat2")
                        for p in (base, experiment):
                            press(p, "a")
                        self.assert_active_menu(base, experiment, style, "meat3")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "meat2")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "meat1")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "category")
                        for p in (base, experiment):
                            press(p, "b")
                        self.assert_active_menu(base, experiment, style, "main")
                        self.assertEqual(returned[0], returned[1])
                    for p in (base, experiment):
                        press(p, "down")
                        press(p, "a")  # Set Flag: four private action labels.
                    self.assert_active_menu(base, experiment, style, "flags")
                    for p in (base, experiment):
                        press(p, "b")
                    self.assert_active_menu(base, experiment, style, "main")
                    for p in (base, experiment):
                        press(p, "down")
                        press(p, "down")
                        press(p, "a")  # Trash returns to a fresh main menu.
                        self.assertEqual({}, inventory(p))
                    self.assert_active_menu(base, experiment, style, "main")
                    for p in (base, experiment):
                        press(p, "b")
                    self.assertEqual(vram(base), vram(experiment))
                    self.assertEqual(returned[0], returned[1])
                    self.assertEqual(bytes(0x122), route.work_read(experiment, 0x5A00, 0x122))

    def test_transitions_never_upload_glyphs_under_a_visible_private_map(self):
        for style, path in self.experimental.items():
            with self.subTest(style=style):
                p = self.start(path)
                visible, checks = [], []

                def underlay_is_visible():
                    origin = int.from_bytes(route.work_read(p, 0x5A00, 2), "little")
                    kind = route.work_read(p, 0x5A03)[0]
                    columns, rows = {0: (13, 11), 1: (9, 7), 2: (8, 9), 3: (10, 7), 4: (8, 9), 5: (7, 5), 6: (11, 11), 7: (11, 11), 8: (11, 11), 9: (13, 9)}[kind]
                    planes = vram(p)
                    actual = bytes(plane[(0x9800 + (((origin + row * 32) & 0x3E0)
                                          | ((origin + col) & 31))) - 0x8000]
                                   for row in range(rows) for col in range(columns) for plane in planes)
                    return actual == route.work_read(p, 0x5A04, columns * rows * 2)

                def painting(_):
                    # The native cramped map must never be exposed before the
                    # private glyph pool and complete frame are ready.
                    checks.append(("open", underlay_is_visible()))

                def painted(_):
                    visible.append(True)

                def uploading(_):
                    destination = (p.register_file.D << 8) | p.register_file.E
                    if visible and 0x8900 <= destination < 0x8C10:
                        # Otherwise the native cached cursor glyphs alias every
                        # label cell that still references the private artwork.
                        checks.append(("retire", underlay_is_visible()))
                        visible.clear()

                p.hook_register(254, self.reports[style]["symbols"]["Paint"], painting, None)
                p.hook_register(254, 0x507B, painted, None)  # Return from CursorInit.
                p.hook_register(0, 0x0A6B, uploading, None)
                open_debug(p)
                for _ in range(3):
                    press(p, "a")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "b")
                    press(p, "down")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "b")
                    press(p, "down")
                    press(p, "down")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "b")
                    for _ in range(3):
                        press(p, "down")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "b")
                    press(p, "up")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "a")  # First -> second Meat page.
                    press(p, "down")
                    press(p, "up")
                    press(p, "a")  # Second -> third Meat page.
                    press(p, "down")
                    press(p, "up")
                    press(p, "a")  # Third -> first, then revisit third.
                    press(p, "a")
                    press(p, "a")
                    press(p, "b")  # Third -> second.
                    press(p, "b")  # Second -> first Meat page.
                    press(p, "b")
                    press(p, "b")
                    press(p, "down")
                    press(p, "a")
                    press(p, "down")
                    press(p, "up")
                    press(p, "b")
                press(p, "b")
                self.assertEqual([], visible)
                self.assertEqual([("open", True), ("retire", True)] * 64, checks)

    def test_partial_inventory_presets_preserve_items_and_match_baseline_cleanup(self):
        fixture = json.loads((ROOT / "tests/fixtures/debug_room.json").read_text())["inventory_room"]
        state = ROOT / fixture["state"]
        self.assertEqual(fixture["state_sha1"], sha1(state.read_bytes()).hexdigest())
        # Native preset sizes, independently measured with empty inventory.
        presets = [("category-%d-preset-%d" % (category, leaf), (0, category, leaf), count)
                   for category, counts in enumerate(((20, 13, 20, 9), (20, 7, 20), (20, 14, 20, 6), (16, 7)))
                   for leaf, count in enumerate(counts)]
        presets += [("meat-page-%d-preset-%d" % (page + 1, leaf), (0, 4) + (0,) * page + (leaf,), count)
                    for page, counts in enumerate(((20, 18, 18, 18), (18, 20, 18, 18), (18, 19, 18, 6)))
                    for leaf, count in enumerate(counts, 1)]
        self.assertEqual(25, len(presets))
        for style in self.baseline:
            players = [self.start(paths[style], state) for paths in (self.baseline, self.experimental)]
            roots, entered = [], []
            players[1].hook_register(254, 0x501D, lambda _: entered.append(route.work_read(players[1], 0x5A03)[0]), None)
            for p in players:
                self.assertEqual(bytes.fromhex(fixture["inventory_slots_hex"]), route.work_read(p, 0x12C1, 20))
                self.assertEqual(fixture["inventory_records_hex"], [record.hex() for record in inventory(p).values()])
                self.assertEqual(10, len(inventory(p)))
                open_debug(p)
                self.assertEqual(4, p.memory[0xC130])
                saved = io.BytesIO()
                p.save_state(saved)
                roots.append(saved.getvalue())
            for name, choices, count in presets:
                with self.subTest(style=style, preset=name):
                    entered.clear()
                    granted = []
                    for p, saved in zip(players, roots):
                        p.load_state(io.BytesIO(saved))
                        original = inventory(p)
                        for choice in choices:
                            for _ in range(choice):
                                press(p, "down")
                            press(p, "a")
                        items = inventory(p)
                        self.assertEqual(10 + min(10, count), len(items))
                        self.assertEqual(original, {slot: items[slot] for slot in original})
                        self.assertEqual(bytes(0x122), route.work_read(p, 0x5A00, 0x122))
                        granted.append(tuple(items.items()))
                    self.assertEqual({0: [0, 2], 1: [0, 3], 2: [0, 4], 3: [0, 5], 4: [0, 6] + ([7] if len(choices) > 3 else []) + ([8] if len(choices) > 4 else [])}[choices[1]], entered,
                                     "exactly the expected private menus must activate")
                    self.assertEqual(granted[0], granted[1])
                    self.assertEqual(vram(players[0]), vram(players[1]))
                    # Successful creation exits debug. Reopen ordinary menus
                    # with the newly granted items, then close every layer.
                    for button, mode in (("b", 4), ("a", 1), ("a", 2), ("b", 1), ("b", 4), ("b", 4)):
                        for p in players:
                            press(p, button)
                            self.assertEqual(mode, p.memory[0xC14E])
                            self.assertEqual(granted[0], tuple(inventory(p).items()))
                        self.assertEqual(vram(players[0]), vram(players[1]))

    def test_weapons_presets_with_empty_and_full_inventory_match_native_results(self):
        self._check_presets_with_empty_and_full_inventory(0, (20, 13, 20, 9))

    def test_flag_actions_preserve_native_progression_messages_and_cleanup(self):
        import extract
        import translations
        fixture = json.loads((ROOT / "tests/fixtures/debug_flags.json").read_text())
        source = ROM.read_bytes()
        self.assertEqual(fixture["source_rom_sha1"], sha1(source).hexdigest())
        records = extract.extract(source)["records"]
        translated = translations.load_path(ROOT / "script/en", records)
        messages = {(ref.group, ref.index): translated[(record.bank, record.address)].text
                    for record in records for ref in record.references if ref.group == 112}
        for action in fixture["actions"]:
            self.assertEqual(FLAGS_LABELS[action["choice"]], action["label"])
            self.assertEqual(action["message"], messages[112, action["message_index"]])
            payload = (bytes((0x83, action["state_c3ee"])) if action["state_c3ee"] is not None else b"")
            payload += b"".join(bytes((0x20, bit)) for bit in action["clear_bits"])
            payload += b"".join(bytes((0x1F, bit)) for bit in action["set_bits"])
            payload += bytes((0x16, action["message_index"], 112, 0xFC))
            address = prototype.offset(180, action["native_action_address"])
            self.assertEqual(payload, source[address:address + len(payload)])
        states = (STATE, ROOT / "SaveStates/debug-room.state.state")
        for style in self.baseline:
            for state in states:
                players = [self.start(paths[style], state) for paths in (self.baseline, self.experimental)]
                roots, entries, selectors, pages = [], [[], []], [[], []], [[], []]
                returned = [popup_returns(p) for p in players]
                for i, p in enumerate(players):
                    p.hook_register(5, 0x58E6, lambda _, p=p, i=i: entries[i].append(
                        (bytes(p.memory[0xC3BE:0xC3C0]), bytes(p.memory[0xFFB0:0xFFBC]))), None)
                    p.hook_register(0, 0x1F58, lambda _, p=p, i=i: selectors[i].append(
                        (p.register_file.A, p.register_file.C)), None)
                    p.hook_register(0, 0x3751, lambda _, p=p, i=i: pages[i].append(vram(p)), None)
                    open_menu(p, "flags")
                    self.assertEqual(bytes.fromhex(fixture["fixture_before_hex"]), bytes(p.memory[0xC3CE:0xC3F1]))
                    self.assertEqual((bytes.fromhex(fixture["next_script_position_hex"]),
                                      bytes.fromhex(fixture["choice_record_hex"])), entries[i][-1])
                    saved = io.BytesIO()
                    p.save_state(saved)
                    roots.append(saved.getvalue())
                # The real fixtures already have some bits set. Empty/full
                # synthetic flag banks separately prove both set and clear
                # effects, including Zenmaiger's otherwise redundant preset.
                for seed in (None, 0, 255):
                    for action in fixture["actions"]:
                        with self.subTest(style=style, state=state.name, seed=seed, action=action["label"]):
                            for i, p in enumerate(players):
                                p.load_state(io.BytesIO(roots[i]))
                                returned[i].clear()
                                selectors[i].clear()
                                pages[i].clear()
                                original_items = inventory(p)
                                if seed is not None:
                                    p.memory[0xC3CE:0xC3EE] = [seed] * 32
                                expected_state = bytearray(p.memory[0xC3CE:0xC3F1])
                                for bit in action["clear_bits"]:
                                    expected_state[bit // 8] &= ~(1 << (bit % 8))
                                for bit in action["set_bits"]:
                                    expected_state[bit // 8] |= 1 << (bit % 8)
                                if action["state_c3ee"] is not None:
                                    expected_state[32] = action["state_c3ee"]
                                if seed is None:
                                    self.assertEqual(bytes.fromhex(action["fixture_after_hex"]), expected_state)
                                for _ in range(action["choice"]):
                                    press(p, "down")
                                press(p, "a")
                                self.assertEqual([(112, action["message_index"])], selectors[i])
                                self.assertEqual(expected_state, bytes(p.memory[0xC3CE:0xC3F1]))
                                self.assertEqual(original_items, inventory(p))
                                self.assertEqual(bytes(0x122), route.work_read(p, 0x5A00, 0x122))
                            self.assertEqual(1, len(returned[0]))
                            self.assertEqual(returned[0], returned[1])
                            # Compare all VRAM at the native page-wait entry.
                            # A fixed delay samples different blink phases of
                            # Moai's prompt after the wider menu closes.
                            self.assertEqual(1, len(pages[0]))
                            self.assertEqual(pages[0], pages[1])
                            for p in players:
                                press(p, "a")  # Fresh press dismisses the result page and exits debug.
                                self.assertEqual(b"\0\0", bytes(p.memory[0xC3BE:0xC3C0]))
                            self.assertEqual(vram(players[0]), vram(players[1]))
                            # Ordinary menus after an action, including their
                            # full off-screen map and glyph storage on return.
                            for button, mode in (("b", 4), ("a", 1), ("a", 2), ("b", 1), ("b", 4), ("b", 4)):
                                for p in players:
                                    press(p, button)
                                    self.assertEqual(mode, p.memory[0xC14E])
                                    self.assertEqual(expected_state, bytes(p.memory[0xC3CE:0xC3F1]))
                                    self.assertEqual(original_items, inventory(p))
                                self.assertEqual(vram(players[0]), vram(players[1]))

    def test_bracelets_presets_with_empty_and_full_inventory_match_native_results(self):
        self._check_presets_with_empty_and_full_inventory(1, (20, 7, 20))

    def test_scrolls_presets_with_empty_and_full_inventory_match_native_results(self):
        self._check_presets_with_empty_and_full_inventory(2, (20, 14, 20, 6))

    def test_pots_presets_with_empty_and_full_inventory_match_native_results(self):
        self._check_presets_with_empty_and_full_inventory(3, (16, 7))

    def test_meat_first_page_batches_match_frozen_native_ids_names_and_counts(self):
        self._check_meat_batches(1, MEAT1_LABELS, (20, 18, 18, 18))

    def test_meat_second_page_batches_match_frozen_native_ids_names_and_counts(self):
        self._check_meat_batches(2, MEAT2_LABELS, (18, 20, 18, 18))

    def test_meat_third_page_batches_match_frozen_native_ids_names_and_counts(self):
        self._check_meat_batches(3, MEAT3_LABELS, (18, 19, 18, 6))

    def _check_meat_batches(self, page, labels, counts):
        import extract
        import translations
        fixture = json.loads((ROOT / ("tests/fixtures/debug_meat_page_%d.json" % page)).read_text())
        source = ROM.read_bytes()
        self.assertEqual(fixture["source_rom_sha1"], sha1(source).hexdigest())
        records = extract.extract(source)["records"]
        translated = translations.load_path(ROOT / "script/en", records)
        names = {(ref.group, ref.index): translated[(record.bank, record.address)].text
                 for record in records for ref in record.references if ref.group in (1, 2, 3)}
        expected_records = []
        for batch in fixture["batches"]:
            self.assertEqual(labels[batch["choice"]], batch["label"])
            self.assertEqual(batch["count"], len(batch["items"]))
            payload = b"".join(bytes((0x1D, item["monster"], item["tier"])) for item in batch["items"])
            payload += bytes.fromhex("055B00FC")
            address = prototype.offset(180, batch["native_action_address"])
            self.assertEqual(payload, source[address:address + len(payload)])
            for item in batch["items"]:
                self.assertEqual(item["name"], names[item["tier"], item["monster"]])
            expected_records.append([bytes((0xC9, 11, item["monster"], item["tier"], 0, 0, 0, 0))
                                     for item in batch["items"]])
        self._check_presets_with_empty_and_full_inventory(4, counts, first_choice=1,
                                                         expected_records=expected_records, meat_page=page)

    def test_meat_pagination_cycles_all_three_pages_with_native_returns_and_complete_cleanup(self):
        fixture = json.loads((ROOT / "tests/fixtures/debug_room.json").read_text())
        for style in self.baseline:
            for state in (STATE, ROOT / fixture["inventory_room"]["state"]):
                with self.subTest(style=style, state=state.name):
                    base, experiment = (self.start(paths[style], state) for paths in (self.baseline, self.experimental))
                    returned = [popup_returns(p) for p in (base, experiment)]
                    entered = []
                    experiment.hook_register(254, 0x501D, lambda _: entered.append(route.work_read(experiment, 0x5A03)[0]), None)
                    for p in (base, experiment):
                        open_menu(p, "meat1")
                    self.assertEqual([1, 0, 6], entered)
                    self.assert_active_menu(base, experiment, style, "meat1")
                    entered.clear()
                    for _ in range(3):
                        for button, page in (("a", 2), ("a", 3), ("a", 1),
                                             ("a", 2), ("b", 1),
                                             ("a", 2), ("a", 3), ("b", 2), ("b", 1)):
                            for p in (base, experiment):
                                press(p, button)
                            self.assertEqual(returned[0], returned[1])
                            self.assert_active_menu(base, experiment, style, "meat%d" % page)
                    self.assertEqual([7, 8, 6, 7, 6, 7, 8, 7, 6] * 3, entered)
                    for p in (base, experiment):
                        for _ in range(3):
                            press(p, "b")
                    self.assertEqual(returned[0], returned[1])
                    self.assertEqual(vram(base), vram(experiment))

    def _check_presets_with_empty_and_full_inventory(self, category, counts, first_choice=0, expected_records=None, meat_page=1):
        for style in self.baseline:
            for empty in (False, True):
                players = [self.start(paths[style]) for paths in (self.baseline, self.experimental)]
                roots = []
                returned = [popup_returns(p) for p in players]
                for p in players:
                    open_debug(p)
                    if empty:
                        press(p, "up")
                        press(p, "a")  # Native Trash empties a disposable state.
                    self.assertEqual(0 if empty else 20, len(inventory(p)))
                    saved = io.BytesIO()
                    p.save_state(saved)
                    roots.append(saved.getvalue())
                for choice, count in enumerate(counts, first_choice):
                    with self.subTest(style=style, empty=empty, choice=choice):
                        for p, saved, exits in zip(players, roots, returned):
                            p.load_state(io.BytesIO(saved))
                            exits.clear()
                            original = inventory(p)
                            press(p, "a")
                            for _ in range(category):
                                press(p, "down")
                            press(p, "a")
                            for _ in range(meat_page - 1):
                                press(p, "a")
                            for _ in range(choice):
                                press(p, "down")
                            press(p, "a")
                            items = inventory(p)
                            self.assertEqual(count if empty else 20, len(items))
                            if not empty:
                                self.assertEqual(original, items)
                            elif expected_records is not None:
                                self.assertEqual(expected_records[choice - first_choice], list(items.values()))
                            self.assertEqual(bytes(0x122), route.work_read(p, 0x5A00, 0x122))
                        self.assertEqual(tuple(inventory(players[0]).items()), tuple(inventory(players[1]).items()))
                        self.assertEqual(2 + meat_page, len(returned[0]))
                        self.assertEqual(returned[0], returned[1])
                        self.assertEqual(vram(players[0]), vram(players[1]))

    def test_ordinary_service_routes_keep_their_native_controller_and_pixels(self):
        fixture = json.loads((ROOT / "tests/fixtures/service_menus.json").read_text())
        schedules = {
            "warehouse": {i: "a" for i in range(0, 1400, 70)},
            "bank": {60: "a", 160: "a"},
            "blacksmith_info": {60: "a", 150: "down", 210: "down", 270: "down", 330: "a"},
            "rescue": {60: "b", 160: "a", 260: "a", 360: "a", 460: "a", 560: "a"},
            "training": dict(fixture["training"]["reopen_actions"]),
        }
        for style in self.baseline:
            for name, schedule in schedules.items():
                with self.subTest(style=style, menu=name):
                    state = ROOT / fixture[name]["state"]
                    base, experiment = (self.start(paths[style], state) for paths in (self.baseline, self.experimental))
                    entered = []
                    experiment.hook_register(254, 0x501D, lambda _: entered.append(True), None)
                    opened = None
                    for frame in range(2400):
                        # Use the existing reviewed service underlay marker to
                        # prove the requested menu actually opened.
                        if opened is None and route.work_read(experiment, 0x59D7, 2) == b"\xA5\x5A":
                            opened = frame
                        button = schedule.get(frame) if opened is None else None
                        if opened is not None:
                            relative = frame - opened
                            if relative in (100, 200, 300, 400):
                                button = "down"
                            if relative == 500:
                                button = "b"
                        for p in (base, experiment):
                            if button:
                                p.button(button, 5)
                            p.tick()
                        if opened is not None and frame - opened in (60, 160, 260, 360, 460, 620):
                            self.assertEqual(base.screen.image.tobytes(), experiment.screen.image.tobytes())
                            self.assertEqual(vram(base), vram(experiment))
                        if opened is not None and frame - opened == 620:
                            break
                    self.assertIsNotNone(opened)
                    self.assertEqual([], entered)

    def test_gate_rejects_every_mismatched_identity_byte_and_occupied_scratch(self):
        for menu in MENUS:
            with self.subTest(menu=menu):
                self._check_gate_rejections(menu)

    def _check_gate_rejections(self, menu):
        path = self.experimental["shadowed"]
        p = self.start(path)
        if menu == "flags":
            open_menu(p, "main")
            press(p, "down")
        elif menu == "meat3":
            open_menu(p, "meat2")
        elif menu == "meat2":
            open_menu(p, "meat1")
        elif menu != "main":
            open_menu(p, "main" if menu == "category" else "category")
        for _ in range({"bracelets": 1, "scrolls": 2, "pots": 3, "meat1": 4}.get(menu, 0)):
            press(p, "down")
        saved = io.BytesIO()
        p.save_state(saved)
        addresses = (0xC12B, *range(0xC3B4, 0xC3B8), 0xC3BE, 0xC3BF, *range(0xFFB0, 0xFFBC))
        for address in (*addresses, None):
            with self.subTest(address=address):
                p.load_state(io.BytesIO(saved.getvalue()))
                calls, changed = [], []

                def mutate(_):
                    if address is None:
                        route.work_write(p, 0x5A80, b"\xA5")
                    else:
                        changed.append(p.memory[address])
                        p.memory[address] ^= 1

                def native(_):
                    calls.append("native")
                    if changed:
                        p.memory[address] = changed[0]

                def private(_):
                    calls.append("private")

                p.hook_register(5, 0x58E6, mutate, None)
                p.hook_register(18, 0x401D, native, None)
                p.hook_register(254, 0x501D, private, None)
                try:
                    if menu == "main":
                        open_debug(p)
                    else:
                        press(p, "a")
                    self.assertEqual(["native"], calls)
                    if address is None:
                        self.assertEqual(b"\xA5", route.work_read(p, 0x5A80))
                finally:
                    p.hook_deregister(5, 0x58E6)
                    p.hook_deregister(18, 0x401D)
                    p.hook_deregister(254, 0x501D)


if __name__ == "__main__":
    unittest.main()
