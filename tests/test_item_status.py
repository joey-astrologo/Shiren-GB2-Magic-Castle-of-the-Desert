from hashlib import sha1, sha256
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
import codec
import english_font
import extract
import font
import item_status
import layout
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "item_status.json").read_text(encoding="utf-8")
)


class ItemStatusMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_asset_source_bitmap_and_renderer_contract_are_frozen(self):
        summary = item_status.summary(self.rom)
        expected = dict(FIXTURE)
        expected.pop("schema")
        expected.pop("item_row")
        expected.pop("mesen_state")
        self.assertEqual(expected, summary)
        self.assertEqual(item_status.CRACKED_CODE, codec.encode("<cracked>"))
        self.assertEqual("<cracked>", codec.decode(item_status.CRACKED_CODE))

    def test_installer_changes_only_the_owned_bitmap_and_checksums(self):
        output = item_status.install(self.rom)
        allowed = {
            offset
            for start, end in item_status.owned_ranges()
            for offset in range(start, end)
        } | {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        changed = {
            offset
            for offset, pair in enumerate(zip(self.rom, output))
            if pair[0] != pair[1]
        }
        self.assertTrue(changed <= allowed)
        self.assertTrue(changed & set(range(*item_status.owned_ranges()[0])))
        cartridge.verify_checksums(output)

        glyph = font.read_glyph(output, item_status.CRACKED_CODE)
        self.assertEqual(FIXTURE["width"], glyph.width)
        self.assertEqual(
            FIXTURE["renderer_advance"],
            layout.renderer_advance(output, item_status.CRACKED_CODE),
        )
        rendered = [
            "".join("#" if pixel == item_status.INK_COLOR else "." for pixel in row)
            for row in glyph.pixels
        ]
        self.assertEqual(FIXTURE["rows"], rendered)
        self.assertFalse(any(pixel == 2 for row in glyph.pixels for pixel in row))

    def test_unexpected_bitmap_or_width_metadata_is_rejected(self):
        bitmap = bytearray(self.rom)
        bitmap[item_status.owned_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(item_status.ItemStatusError, "source bitmap"):
            item_status.install(bitmap)

        widths = bytearray(self.rom)
        location = font.glyph_location(item_status.CRACKED_CODE)
        width_at = (
            font.banked_offset(font.WIDTH_BANK, font.WIDTH_ADDRESS)
            + location.width_index
        )
        widths[width_at] ^= 1
        with self.assertRaisesRegex(item_status.ItemStatusError, "width metadata"):
            item_status.install(widths)

    def test_every_translated_item_name_shape_fits_with_the_marker(self):
        extracted = extract.extract(self.rom)
        translated = translations.load_path(ROOT / "script" / "en", extracted["records"])
        patched_font = item_status.install(english_font.install(self.rom))
        analysis = runtime_widths.analyze(patched_font, extracted, translated)
        maximum = analysis.domains["item_name"].maximum.renderer_pixels
        marker = layout.renderer_advance(patched_font, item_status.CRACKED_CODE)
        contract = FIXTURE["item_row"]
        self.assertEqual(contract["maximum_translated_name_pixels"], maximum)
        self.assertEqual(contract["marker_pixels"], marker)
        rightmost = contract["start_x"] + maximum + marker
        self.assertEqual(contract["rightmost_pixel"], rightmost)
        self.assertEqual(contract["remaining_pixels"], contract["right_edge"] - rightmost)
        self.assertLessEqual(rightmost, contract["right_edge"])


class MesenBrokenBraceletRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = [
            os.environ.get("MESEN_BIN"),
            shutil.which("Mesen"),
            shutil.which("mesen"),
            "/Applications/Mesen.app/Contents/MacOS/Mesen",
        ]
        cls.mesen = next(
            (Path(path) for path in candidates if path and Path(path).is_file()),
            None,
        )
        if cls.mesen is None:
            raise unittest.SkipTest("Mesen test-runner executable is unavailable")

        cls.source = ROOT / ROM_NAME
        cls.state = ROOT / FIXTURE["mesen_state"]["path"]
        if not cls.source.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("matching ROM and broken-Bracelet state are required")
        raw = cls.state.read_bytes()
        if sha1(raw).hexdigest() != FIXTURE["mesen_state"]["sha1"]:
            raise AssertionError("broken-Bracelet Mesen state SHA-1 mismatch")
        if sha256(raw).hexdigest() != FIXTURE["mesen_state"]["sha256"]:
            raise AssertionError("broken-Bracelet Mesen state SHA-256 mismatch")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "broken-bracelet.gbc"
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
            raise AssertionError("could not build cracked-marker fixture:\n" + built.stdout + built.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_supplied_state_redraws_the_localized_marker(self):
        env = os.environ.copy()
        env["GB2_MSS_PATH"] = str(self.state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(ROOT / "tests" / "mesen_broken_bracelet_live.lua"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn(
            "PASS cracked marker screen="
            + FIXTURE["mesen_state"]["localized_redraw_screen_fnv1a"],
            output,
        )


if __name__ == "__main__":
    unittest.main()
