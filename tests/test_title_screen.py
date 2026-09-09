from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import title_graphics
import title_screen
import title_screen_runtime
from title_localization_audition import sprite_pixels


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads((ROOT / "tests/fixtures/title_screen.json").read_text())


def original_rom():
    path = ROOT / ROM_NAME
    if (
        not path.exists()
        or sha1(path.read_bytes()).hexdigest() != capture_dialogue.ROM_SHA1
    ):
        raise unittest.SkipTest("matching original ROM is required")
    return path.read_bytes()


class TitleInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_rom()
        cls.output = title_screen.install(cls.original)

    def test_approved_composition_is_frozen_before_the_renderer(self):
        for phase, expected in enumerate(FIXTURE["rgba_sha256"]):
            image = title_graphics.compose(self.original, phase, gradient=True)
            self.assertEqual(
                expected, sha256(image.convert("RGBA").tobytes()).hexdigest()
            )

    def test_idempotence_checksums_and_exclusive_mutation_ranges(self):
        self.assertEqual(self.output, title_screen.install(self.output))
        cartridge.verify_checksums(self.output)
        owned = {
            i for start, end in title_screen.owned_ranges() for i in range(start, end)
        }
        owned.update((0x14D, 0x14E, 0x14F))
        unexpected = [
            i
            for i, (a, b) in enumerate(zip(self.original, self.output))
            if a != b and i not in owned
        ]
        self.assertEqual([], unexpected)

    def test_rejects_hook_resource_and_reserved_bank_collisions(self):
        for address in (
            0x44,
            0x215,
            title_graphics.offset(28, 0x4100),
            title_graphics.offset(245, 0x4000),
            title_graphics.offset(247, 0x7FFF),
        ):
            with self.subTest(address=hex(address)):
                altered = bytearray(self.original)
                altered[address] ^= 0x55
                with self.assertRaises(title_screen.TitleScreenError):
                    title_screen.install(altered)

    def test_palette_tile_and_scanline_object_budgets(self):
        graphics = title_graphics.compile_graphics(self.original)
        _, metrics = title_screen_runtime.build(self.original, graphics)
        self.assertEqual(326, metrics["background_tiles"])
        self.assertEqual(43, metrics["body_sprites"])
        self.assertEqual(150, metrics["object_tiles"])
        self.assertEqual(61, metrics["stat_events"])
        for key, capacity in (
            ("bg_palettes", 4),
            ("lower_palettes", 4),
            ("obj_palettes", 3),
        ):
            self.assertEqual(8, len(graphics[key]))
            self.assertTrue(all(len(palette) <= capacity for palette in graphics[key]))
        for y in range(144):
            count = sum(r["y"] <= y < r["y"] + 16 for r in graphics["rects"])
            if 14 <= y <= 32:
                count += 3
            if 115 <= y < 135:
                count += 2
            self.assertLessEqual(count, 10, "OAM limit at scanline %d" % y)


class TitleLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pyboy import PyBoy
        except ImportError as error:
            raise unittest.SkipTest(str(error))
        cls.PyBoy = PyBoy
        cls.original = original_rom()
        cls.directory = tempfile.TemporaryDirectory(prefix="shiren-title-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.native_path = Path(cls.directory.name) / "native.gbc"
        cls.output_path = Path(cls.directory.name) / "localized.gbc"
        cls.native_path.write_bytes(cls.original)
        cls.output_path.write_bytes(title_screen.install(cls.original))

    def emulator(self, path):
        owner = self.PyBoy(str(path), window="null", sound_emulated=False)
        owner.set_emulation_speed(0)
        self.addCleanup(owner.stop, save=False)
        return owner

    def test_live_pixels_two_sparkle_cycles_and_original_bat_motion(self):
        # Capture the native bat cycle independently of the inserted clock/table.
        native = self.emulator(self.native_path)
        native.tick(599)
        native_bats = []
        for _ in range(FIXTURE["bat_cycle_frames"]):
            oam = list(native.memory[0xFE00:0xFEA0])
            records = list(
                dict.fromkeys(tuple(oam[i : i + 4]) for i in range(0, 160, 4))
            )
            bats = [r for r in records if 0x54 <= r[2] < 0x74 and r[3] == 0]
            native_bats.append(
                tuple(
                    (y - (13 if y == 45 else 1), x, tile, attr)
                    for y, x, tile, attr in bats
                )
            )
            native.tick()
        native.stop(save=False)

        source = title_graphics.offset(49, 0x4000) + 2 + 0x300
        native_vram = self.original[source : source + 0x800]
        expected = {
            (moon, shine): title_graphics.compose(
                self.original, moon, shine, gradient=True
            )
            for moon in range(4)
            for shine in range(-1, 8)
        }
        owner = self.emulator(self.output_path)
        owner.tick(600)
        actual_bats, phases, clocks = [], [], []
        for frame in range(480):
            clock = owner.memory[0xC880]
            moon = owner.memory[0xC881]
            shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
            oam = [
                tuple(owner.memory[0xFE00 + i * 4 : 0xFE04 + i * 4]) for i in range(3)
            ]
            bats = tuple(r for r in oam if r[0])
            actual_bats.append(bats)
            phases.append((moon, shine))
            clocks.append(clock)
            image = expected[moon, shine].copy()
            for bat in bats:
                self.assertEqual(0, bat[3])
                for x, y in sprite_pixels(native_vram, bat):
                    self.assertTrue(0 <= x < 160 and 0 <= y < 144)
                    image.putpixel((x, y), (8, 8, 8))
            owner.tick()
            actual = owner.screen.image.convert("RGB")
            if actual.tobytes() != image.tobytes():
                bad = [
                    (x, y)
                    for y in range(144)
                    for x in range(160)
                    if actual.getpixel((x, y)) != image.getpixel((x, y))
                ]
                self.fail(
                    "title frame %d differs at %d pixels: %s"
                    % (frame, len(bad), bad[:8])
                )
        self.assertTrue(
            any(
                all(
                    bats == native_bats[(index + shift) % 96]
                    for index, bats in enumerate(actual_bats)
                )
                for shift in range(96)
            ),
            "inserted bat motion differs from the native 96-frame cycle",
        )
        self.assertTrue(all(b == (a + 1) % 240 for a, b in zip(clocks, clocks[1:])))
        changes = [i for i in range(1, 480) if phases[i][0] != phases[i - 1][0]]
        self.assertTrue(all(b - a == 6 for a, b in zip(changes, changes[1:])))
        for shine in range(8):
            self.assertEqual(20, sum(s == shine for _, s in phases))
        self.assertEqual(320, sum(s == -1 for _, s in phases))

    def test_start_handoff_preserves_the_native_menu(self):
        images = []
        for path in (self.native_path, self.output_path):
            owner = self.emulator(path)
            owner.tick(650)
            owner.button("start", 5)
            owner.tick(120)
            self.assertEqual(7, owner.memory[0xC0E5])
            image = owner.screen.image.convert("RGB")
            # The selected-row arrow flashes on its own clock. Loading the
            # larger title shifts that harmless blink phase by a few frames.
            image.paste((0, 0, 0), (4, 14, 14, 25))
            images.append(image.tobytes())
            owner.button("b", 5)
            owner.tick(120)
            self.assertEqual(7, owner.memory[0xC0E5])
        self.assertEqual(images[0], images[1])

    def test_every_start_transition_frame_fades_the_complete_composition(self):
        # Observe the original cartridge's interpolation commits independently
        # of the localized palette tables and private fade state.
        native = self.emulator(self.native_path)
        native.tick(650)
        commits = []

        def at_native_commit(_):
            commits.append(
                (native.frame_count, native.memory[0xDEF1], native.memory[0xDEE1])
            )

        native.hook_register(6, 0x423D, at_native_commit, None)
        native.button("start", 5)
        native.tick(60)
        native_steps = [progress * 32 // total for _, progress, total in commits]
        native_intervals = [b[0] - a[0] for a, b in zip(commits, commits[1:])]
        self.assertEqual([2, 10, 18, 26, 32], native_steps)
        self.assertEqual([4] * 4, native_intervals)
        native.stop(save=False)

        expected = {
            (m, s): title_graphics.compose(self.original, m, s, gradient=True)
            for m in range(4)
            for s in range(-1, 8)
        }
        start = title_graphics.offset(49, 0x4000) + 2 + 0x300
        tiles = self.original[start : start + 0x800]
        saw_sparkle = False
        for press_frame in (600, 650, 730):
            with self.subTest(press_frame=press_frame):
                owner = self.emulator(self.output_path)
                owner.tick(press_frame)
                owner.button("start", 5)
                levels = []
                for frame in range(60):
                    clock, moon, step = (
                        owner.memory[a] for a in (0xC880, 0xC881, 0xC887)
                    )
                    shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
                    active = owner.memory[0xC3B4] == 0x9D and owner.memory[0xC0E5] == 9
                    image = expected[moon, shine].copy()
                    for i in range(3):
                        bat = tuple(owner.memory[0xFE00 + i * 4 : 0xFE04 + i * 4])
                        if active and bat[0]:
                            for x, y in sprite_pixels(tiles, bat):
                                image.putpixel((x, y), (8, 8, 8))
                    owner.tick()
                    if not active or not owner.memory[0xFF40] & 0x80:
                        continue
                    if step:
                        saw_sparkle |= shine >= 0
                        if not levels or levels[-1][1] != step:
                            levels.append((frame, step))
                    # The native fade interpolates each five-bit channel toward
                    # white, rounding down. It must hold for every pixel, even
                    # when one palette is reused for sky, sand, and sparkle.
                    image = image.point(
                        [
                            min(248, v + ((31 - v // 8) * step // 32) * 8)
                            for v in range(256)
                        ]
                        * 3
                    )
                    actual = owner.screen.image.convert("RGB")
                    mismatches = sum(
                        a != b for a, b in zip(image.getdata(), actual.getdata())
                    )
                    self.assertEqual(
                        0, mismatches, "Start frame %d, fade %d" % (frame, step)
                    )
                self.assertEqual(native_steps, [step for _, step in levels])
                self.assertEqual(
                    native_intervals, [b[0] - a[0] for a, b in zip(levels, levels[1:])]
                )
                self.assertEqual(7, owner.memory[0xC0E5])
                owner.stop(save=False)
        self.assertTrue(
            saw_sparkle, "transition coverage must include an active sparkle"
        )

    def test_attract_replay_releases_scratch_and_reloads_the_title(self):
        owner = self.emulator(self.output_path)
        owner.tick(600)
        staged_code = bytes(owner.memory[0xC900:0xC9E0])
        departed = False
        played = False
        returned = False
        # The native RNG chooses among recordings of different lengths.
        for _ in range(14000):
            owner.tick()
            scene, mode = owner.memory[0xC3B4], owner.memory[0xC0E5]
            self.assertNotEqual(255, mode)
            departed |= scene != 0x9D
            played |= departed and mode == 6
            if played and scene == 0x9D and mode == 9:
                returned = True
                break
        self.assertTrue(returned, "attract replay did not return to the title")
        owner.tick(120)
        self.assertEqual(staged_code, bytes(owner.memory[0xC900:0xC9E0]))
        clock, moon = owner.memory[0xC880], owner.memory[0xC881]
        shine = (clock - 60) // 10 if 60 <= clock < 140 else -1
        image = title_graphics.compose(self.original, moon, shine, gradient=True)
        source = title_graphics.offset(49, 0x4000) + 2 + 0x300
        vram = self.original[source : source + 0x800]
        for i in range(3):
            bat = tuple(owner.memory[0xFE00 + i * 4 : 0xFE04 + i * 4])
            if bat[0]:
                for x, y in sprite_pixels(vram, bat):
                    image.putpixel((x, y), (8, 8, 8))
        owner.tick()
        self.assertEqual(image.tobytes(), owner.screen.image.convert("RGB").tobytes())


if __name__ == "__main__":
    unittest.main()
