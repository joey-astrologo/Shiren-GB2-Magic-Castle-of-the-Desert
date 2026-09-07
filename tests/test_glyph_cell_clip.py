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
import far_text
import font
import glyph_cell_clip
import layout
import pyboy_fixtures
import pyboy_route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "Mamel.state"


class GlyphCellClipInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("matching original ROM is required")

    def test_exact_guard_idempotence_and_exclusive_mutations(self):
        patched = glyph_cell_clip.install(self.rom)
        self.assertTrue(glyph_cell_clip.verify(patched))
        self.assertEqual(patched, glyph_cell_clip.install(patched))
        allowed = {0x14D, 0x14E, 0x14F}
        for start, end in glyph_cell_clip.owned_ranges():
            allowed.update(range(start, end))
        changed = {i for i, (a, b) in enumerate(zip(self.rom, patched)) if a != b}
        self.assertTrue(changed <= allowed)
        for address in (0x3971, 0x397D, 0x3986, 0x3FF6):
            with self.subTest(address=hex(address)):
                damaged = bytearray(self.rom)
                damaged[address] ^= 1
                with self.assertRaises(glyph_cell_clip.GlyphCellClipError):
                    glyph_cell_clip.install(damaged)

    def test_fixed_bank_predicate_does_not_overlap_far_selectors(self):
        for start, end in glyph_cell_clip.owned_ranges():
            for other_start, other_end in far_text.owned_ranges():
                self.assertTrue(end <= other_start or other_end <= start)
        both = far_text.install(glyph_cell_clip.install(self.rom))
        self.assertEqual(both, glyph_cell_clip.install(far_text.install(self.rom)))
        self.assertTrue(far_text.verify(both))
        self.assertTrue(glyph_cell_clip.verify(both))


class PyBoyGlyphCellClipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ROM_NAME).is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory()
        destination = Path(cls.temporary.name) / "clip.gbc"
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
            style: destination.with_name("clip-%s-font.gbc" % style)
            for style in ("classic", "shadowed")
        }

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_real_drink_routes_preserve_the_complete_bottom_border(self):
        white, gray, black = (248, 248, 248), (168, 168, 168), (0, 0, 0)
        expected_border = (
            tuple([white] + [black] * 2 + [gray] * 154 + [black] * 2 + [white]),
            tuple([white, gray] + [black] * 156 + [gray, white]),
            tuple([white] * 160),
        )
        for style, path in self.localized.items():
            for item, root, name in ((105, 28, "Otogirisou"), (121, 44, "Leaping Grass")):
                with self.subTest(font=style, item=name):
                    target = pyboy_route.start(self.PyBoy, path, STATE)
                    seen = []
                    edge = []
                    expected = english.encode_source(
                        "Made " + name + " <br><cF3>into medicine <cF3>and consumed it."
                    ) + b"\xff"

                    def at_full(_context=None):
                        if bytes(target.memory[0xC800:0xC800 + len(expected)]) == expected:
                            seen.append((target.frame_count, target.memory[0xC4DA]))

                    def at_glyph(_context=None):
                        if seen and target.memory[0xC4D6] == 139:
                            edge.append((target.memory[0xC4D6], target.memory[0xC4D7]))

                    try:
                        # Disposable native inventory fixture; real menu/controller
                        # and item-use composition execute without injected text.
                        pyboy_fixtures.install_item_gallery(
                            target, [bytes((item, 6, 0, 0, 0, 0, 0, 0))] * 20
                        )
                        pyboy_fixtures.identify_root(target, root)
                        target.hook_register(*layout.FULL_RENDERER_ENTRY, at_full, None)
                        target.hook_register(*layout.GLYPH_RENDERER_ENTRY, at_glyph, None)
                        actions = {120: "b", 220: "a", 320: "a", 420: "a"}
                        for frame in range(600):
                            if frame in actions:
                                target.button(actions[frame], 5)
                            target.tick()
                            if seen and target.frame_count >= seen[0][0] + 15:
                                break
                        self.assertEqual(1, len(seen))
                        self.assertEqual(0x10, seen[0][1])
                        self.assertIn((139, 40), edge)
                        for _ in range(3):
                            image = target.screen.image.convert("RGB")
                            actual = tuple(tuple(image.getpixel((x, y)) for x in range(160))
                                           for y in (141, 142, 143))
                            self.assertEqual(expected_border, actual)
                            target.tick()
                    finally:
                        target.stop(save=False)

    @staticmethod
    def _canvas_offset(x, y):
        return (y // 8 * 18 + x // 8) * 16 + (y % 8) * 2

    def test_compositor_matches_pixel_clipping_at_every_horizontal_origin(self):
        # Independent pixel oracle, with nonblank destination canaries. Cover
        # all alignments, interior tile crossings, both heights/source banks,
        # both font styles, and deferred/immediate upload modes.
        seed = bytes((i * 37 + 91) & 255 for i in range(0x1000))
        for style, path in self.localized.items():
            rom = path.read_bytes()
            target = pyboy_route.start(self.PyBoy, path, STATE)
            try:
                target.memory[0xFFFF] = 0
                target.memory[0xFF0F] = 0
                target.memory[0xFF40] = 0
                target.memory[0xFF70] = 7
                # A direct native compositor call from fixed WRAM, followed by
                # a completion sentinel and spin. No renderer is simulated here.
                target.memory[0xC700:0xC70B] = bytes.fromhex("F3 CD 22 39 3E 42 EA FF C7 18 FE")
                for code in (english.encode("."), bytes.fromhex("F001")):
                    glyph = font.read_glyph(rom, code)
                    location = glyph.location
                    for mode in (0x01, 0x02, 0x04, 0x08, 0x10):
                        y = 40 if mode == 0x10 else 21
                        for x in range(144):
                            with self.subTest(font=style, code=code.hex(), mode=mode, x=x):
                                target.memory[0xD000:0xE000] = seed
                                target.memory[0xC4D0] = location.address & 255
                                target.memory[0xC4D1] = location.address >> 8
                                target.memory[0xC4D2] = location.bank
                                destination = 0xD000 + self._canvas_offset(x, y)
                                target.memory[0xC4D3] = destination & 255
                                target.memory[0xC4D4] = destination >> 8
                                target.memory[0xC4D6] = x
                                target.memory[0xC4D7] = y
                                target.memory[0xC4DA] = mode
                                target.memory[0xFFE0] = location.height
                                target.memory[0xFFF7] = 17
                                target.memory[0x2100] = 17
                                target.memory[0xC7FF] = 0
                                target.register_file.SP = 0xC6F0
                                target.register_file.PC = 0xC700
                                for _ in range(3):
                                    target.tick()
                                    if target.memory[0xC7FF] == 0x42:
                                        break
                                self.assertEqual(0x42, target.memory[0xC7FF])
                                expected = bytearray(seed)
                                for dy, row in enumerate(glyph.pixels):
                                    for dx, color in enumerate(row[:8]):
                                        if x + dx >= 144:
                                            continue
                                        at = self._canvas_offset(x + dx, y + dy)
                                        bit = 1 << (7 - (x + dx) % 8)
                                        if mode & 8:
                                            color = (color & 2) | ((color & 1) & (color >> 1))
                                        for plane in (0, 1):
                                            expected[at + plane] &= ~bit & 255
                                            if color & (1 << plane):
                                                expected[at + plane] |= bit
                                self.assertEqual(bytes(expected), bytes(target.memory[0xD000:0xE000]))
                                self.assertEqual((x, y), tuple(target.memory[0xC4D6:0xC4D8]))
                                self.assertEqual(17, target.memory[0xFFF7])
                                self.assertEqual(rom[17 * 0x4000], target.memory[0x4000])
                                self.assertEqual(0xC6F0, target.register_file.SP)
                                self.assertEqual(location.address + location.height * 2,
                                                 target.memory[0xC4D0] | target.memory[0xC4D1] << 8)
            finally:
                target.stop(save=False)


if __name__ == "__main__":
    unittest.main()
