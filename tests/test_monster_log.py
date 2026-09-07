from pathlib import Path
import re
from hashlib import sha1
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import capture_dialogue
import english
import menu_text
import pyboy_route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
LUA_PATH = ROOT / "tools" / "mesen_unlock_monster_log.lua"
STATE_PATH = ROOT / "SaveStates" / "monster-logs.state"
STATE_SHA1 = "5ec94d5ece186ef9a059fd3e1547cd93dd822506"


class MonsterLogUnlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()

    def test_lua_masks_match_every_native_catalog_entry_only(self):
        entries = menu_text._monster_notebook_master_entries(self.rom)
        expected = [0] * 28
        for tier, monster in entries:
            bit = (tier - 1) * 73 + monster
            expected[bit // 8] |= 1 << (bit % 8)
        source = LUA_PATH.read_text(encoding="utf-8")
        block = re.search(
            r"local REQUIRED_MASKS = \{(?P<body>.*?)\n\}", source, re.DOTALL
        )
        self.assertIsNotNone(block)
        actual = [
            int(value, 16)
            for value in re.findall(r"0x[0-9A-Fa-f]{2}", block.group("body"))
        ]
        self.assertEqual(expected, actual)

        self.assertEqual(209, sum(bin(value).count("1") for value in actual))

    def test_native_catalog_omits_only_the_ten_internal_variants(self):
        entries = set(menu_text._monster_notebook_master_entries(self.rom))
        omitted = {
            tier: [monster for monster in range(1, 74) if (tier, monster) not in entries]
            for tier in range(1, 4)
        }
        self.assertEqual(
            {1: [], 2: [40, 66, 68], 3: [2, 4, 16, 40, 66, 67, 68]},
            omitted,
        )


class PyBoyMonsterLogGlyphCellTests(unittest.TestCase):
    TARGETS = (
        (
            "Death Reaper",
            2,
            3,
            "Death Reaper<br>Attacks without expression.<br>"
            "Its scythe is secondhand.",
        ),
        (
            "Jungarian",
            6,
            1,
            "Jungarian<br>Takes an item and throws it.<br>"
            "Even that cute face hurls it.",
        ),
        (
            "Mamel control",
            0,
            0,
            "Mamel<br>The most popular monster.<br>Its tail is said to be tasty.",
        ),
    )
    MAP_TILES = bytes.fromhex(
        "7E6C6D6E6F707172737475767778797A7B7C7D7E"
    )
    MAP_ATTRIBUTES = bytes.fromhex(
        "C8888888888888888888888888888888888888E8"
    )
    BORDER_PLANES = {
        0: bytes.fromhex("00000000" * 16 + "406040604060406000000000"),
        1: bytes.fromhex("00FFFFFF" * 18 + "DF60DF60"),
    }

    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE_PATH.is_file():
            raise unittest.SkipTest("matching ROM and Monster Log state are required")
        if sha1(STATE_PATH.read_bytes()).hexdigest() != STATE_SHA1:
            raise AssertionError("Monster Log PyBoy state SHA-1 mismatch")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        cls.temporary = tempfile.TemporaryDirectory()
        destination = Path(cls.temporary.name) / "monster-log.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(source),
                str(ROOT / "script" / "en"),
                str(destination),
                "--font-style",
                "both",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=90,
        )
        if built.returncode:
            cls.temporary.cleanup()
            raise AssertionError(
                "could not build Monster Log fixtures:\n" + built.stdout + built.stderr
            )
        cls.localized = {
            style: destination.with_name("monster-log-%s-font.gbc" % style)
            for style in ("classic", "shadowed")
        }

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    @staticmethod
    def _vram(pyboy, address, bank, size=1):
        old_bank = pyboy.memory[0xFF4F]
        try:
            pyboy.memory[0xFF4F] = bank
            return bytes(pyboy.memory[address:address + size])
        finally:
            pyboy.memory[0xFF4F] = old_bank

    @classmethod
    def _border_state(cls, pyboy):
        image = pyboy.screen.image.convert("RGB")
        return {
            "map": tuple(cls._vram(pyboy, 0x9A20, bank, 20) for bank in (0, 1)),
            "planes": tuple(
                b"".join(
                    cls._vram(pyboy, 0x9000 + tile * 16 + 10, bank, 4)
                    for tile in range(0x6C, 0x7F)
                )
                for bank in (0, 1)
            ),
            "pixels": tuple(
                tuple(image.getpixel((x, y)) for x in range(160))
                for y in (141, 142, 143)
            ),
        }

    @staticmethod
    def _open_target(pyboy, page, slot):
        pyboy_route.run_frames(pyboy, 30)
        pyboy_route.press(pyboy, "b")
        pyboy_route.run_frames(pyboy, 90)
        pyboy_route.press(pyboy, "a")
        pyboy_route.run_frames(pyboy, 90)
        for _ in range(page):
            # Put the real controller on the bottom row, then let its Down path
            # advance and rebuild the next 27-entry catalog page.
            pyboy.memory[0xC14F] = 18
            pyboy.memory[0xC150] = 18
            pyboy_route.press(pyboy, "down")
            pyboy_route.run_frames(pyboy, 30)
        if page:
            for _ in range(2):
                pyboy_route.press(pyboy, "up")
                pyboy_route.run_frames(pyboy, 20)
        for _ in range(slot):
            pyboy_route.press(pyboy, "right")
            pyboy_route.run_frames(pyboy, 20)
        if (pyboy.memory[0xC152], pyboy.memory[0xC14F]) != (page, slot):
            raise AssertionError("Monster Log controller did not reach the target entry")
        pyboy_route.press(pyboy, "a")
        pyboy_route.run_frames(pyboy, 150)

    def test_supplied_artifact_is_repaired_for_both_fonts_and_spill_sizes(self):
        background = (192, 160, 144)
        border = (168, 80, 0)
        ink = (0, 0, 8)
        expected_pixels = (
            tuple([background] + [ink] * 2 + [border] * 154 + [ink] * 2 + [background]),
            tuple([background, border] + [ink] * 156 + [border, background]),
            tuple([background] * 160),
        )
        for style, rom in self.localized.items():
            for label, page, slot, text in self.TARGETS:
                with self.subTest(font=style, entry=label):
                    pyboy = pyboy_route.start(self.PyBoy, rom, STATE_PATH)
                    try:
                        pyboy_route.run_frames(pyboy, 30)
                        self.assertEqual(
                            bytes.fromhex("C03FFF3F"),
                            self._vram(pyboy, 0x96C0 + 10, 1, 4),
                            "the supplied two-pixel artifact is no longer reproduced",
                        )
                        self._open_target(pyboy, page, slot)
                        self.assertIsNotNone(
                            pyboy_route.find_work_ram(
                                pyboy, english.encode_source(text)
                            )
                        )
                        settled = self._border_state(pyboy)
                        pyboy.tick()
                        pyboy.tick()
                        self.assertEqual(settled, self._border_state(pyboy))
                        self.assertEqual(
                            (self.MAP_TILES, self.MAP_ATTRIBUTES), settled["map"]
                        )
                        self.assertEqual(
                            (self.BORDER_PLANES[0], self.BORDER_PLANES[1]),
                            settled["planes"],
                        )
                        self.assertEqual(expected_pixels, settled["pixels"])
                    finally:
                        pyboy.stop(save=False)

    def test_unlock_masks_make_all_209_native_entries_available(self):
        entries = menu_text._monster_notebook_master_entries(
            (ROOT / ROM_NAME).read_bytes()
        )
        masks = [0] * 28
        for tier, monster in entries:
            bit = (tier - 1) * 73 + monster
            masks[bit // 8] |= 1 << (bit % 8)

        pyboy = pyboy_route.start(
            self.PyBoy, self.localized["shadowed"], STATE_PATH
        )
        try:
            pyboy_route.run_frames(pyboy, 30)
            pyboy_route.press(pyboy, "b")
            pyboy_route.run_frames(pyboy, 90)
            pyboy_route.press(pyboy, "a")
            pyboy_route.run_frames(pyboy, 90)

            before = pyboy_route.work_read(pyboy, 0x2E48, len(masks))
            unlocked = bytes(old | mask for old, mask in zip(before, masks))
            pyboy_route.work_write(pyboy, 0x2E48, unlocked)
            self.assertEqual(unlocked, pyboy_route.work_read(pyboy, 0x2E48, 28))

            # The current page was cached before the helper ran. Visit the next
            # page and return through the real controller so page zero is rebuilt.
            pyboy.memory[0xC14F] = 18
            pyboy.memory[0xC150] = 18
            pyboy_route.press(pyboy, "down")
            pyboy_route.run_frames(pyboy, 30)
            pyboy.memory[0xC14F] = 0
            pyboy.memory[0xC150] = 0
            pyboy_route.press(pyboy, "up")
            pyboy_route.run_frames(pyboy, 30)
            self.assertEqual(0, pyboy.memory[0xC152])
            self.assertEqual(7, pyboy.memory[0xC153])

            for page in range(8):
                first = page * 27
                expected = entries[first:first + 27]
                cache = bytes(pyboy.memory[0xCF00:0xCF51])
                actual = tuple(
                    (cache[offset], cache[offset + 1], cache[offset + 2])
                    for offset in range(0, len(expected) * 3, 3)
                )
                self.assertEqual(
                    tuple((tier, monster, 1) for tier, monster in expected),
                    actual,
                )
                if page < 7:
                    pyboy.memory[0xC14F] = 18
                    pyboy.memory[0xC150] = 18
                    pyboy_route.press(pyboy, "down")
                    pyboy_route.run_frames(pyboy, 30)
                    self.assertEqual(page + 1, pyboy.memory[0xC152])
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
