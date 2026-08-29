from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cartridge
import english
import english_font
import extract
import item_formatting
import item_status
import layout
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "item_formatting.json").read_text(
        encoding="utf-8"
    )
)
GALLERY_SCRIPT = ROOT / "tools" / "mesen_item_formatting_gallery.lua"
GALLERY_ROW = re.compile(
    r'^\s*\{\s*"([^"]+)",\s*"([^"]+)",\s*\{([^}]+)\}\s*\},\s*$',
    re.MULTILINE,
)


class ItemFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != FIXTURE["source_rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.extracted = extract.extract(cls.rom)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.extracted["records"]
        )
        cls.by_reference = {
            (reference.group, reference.index): record
            for record in cls.extracted["records"]
            for reference in record.references
        }
        cls.font_rom = item_status.install(
            item_formatting.install(english_font.install(cls.rom))
        )

    @classmethod
    def item_name(cls, item_id):
        record = cls.by_reference[(4, item_id)]
        return cls.translated[(record.bank, record.address)].text

    def test_formatter_producer_contract_is_frozen(self):
        self.assertEqual(FIXTURE["formatter"], item_formatting.summary())

    def test_installer_is_anchored_idempotent_and_confined(self):
        output = item_formatting.install(self.rom)
        allowed = {
            offset
            for start, end in item_formatting.owned_ranges()
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
        self.assertTrue(changed - {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        })
        cartridge.verify_checksums(output)
        self.assertEqual(output, item_formatting.install(output))
        for patch in item_formatting.PATCHES:
            self.assertEqual(
                patch.localized,
                output[patch.offset:patch.offset + len(patch.localized)],
            )

        damaged = bytearray(self.rom)
        damaged[item_formatting.PATCHES[0].offset] ^= 1
        with self.assertRaisesRegex(
            item_formatting.ItemFormattingError, "equipment_negative_sign"
        ):
            item_formatting.install(damaged)

    def test_every_localized_dynamic_item_shape_fits_the_inventory_row(self):
        contract = FIXTURE["item_row"]
        start_x = contract["start_x"]
        right_edge = contract["right_edge"]
        families = {
            "weapon_plus_99": (range(1, 34), lambda name: name + "+99"),
            "shield_plus_99": (range(34, 63), lambda name: name + "+99"),
            "arrow_99": (range(90, 97), lambda name: "99 " + name),
            "staff_99": (range(158, 184), lambda name: name + "[99]"),
            "pot_9": (range(184, 200), lambda name: name + "[9]"),
        }
        for family, (item_ids, compose) in families.items():
            measured = []
            for item_id in item_ids:
                text = compose(self.item_name(item_id))
                rendered = layout.renderer_layout(
                    self.font_rom,
                    english.encode_source(text),
                    mode=0x08,
                    start_x=start_x,
                )
                self.assertFalse(rendered.auto_wraps, (family, item_id, text))
                self.assertLessEqual(rendered.rightmost_pen, right_edge)
                measured.append(
                    {
                        "item_id": item_id,
                        "text": text,
                        "pixels": rendered.rightmost_pen - start_x,
                        "rightmost_pixel": rendered.rightmost_pen,
                    }
                )
            maximum = max(measured, key=lambda row: (row["pixels"], row["item_id"]))
            self.assertEqual(contract["families"][family], maximum)

        status = contract["maximum_status_combination"]
        encoded = (
            bytes((0xEA,))
            + english.encode_source(self.item_name(11) + "+99")
            + bytes((0xEB, 0xED))
        )
        rendered = layout.renderer_layout(
            self.font_rom, encoded, mode=0x08, start_x=start_x
        )
        actual = {
            "text": "<equip>" + self.item_name(11) + "+99<skull><plate>",
            "pixels": rendered.rightmost_pen - start_x,
            "rightmost_pixel": rendered.rightmost_pen,
            "remaining_pixels": right_edge - rendered.rightmost_pen,
        }
        self.assertEqual(status, actual)
        self.assertFalse(rendered.auto_wraps)
        self.assertLessEqual(rendered.rightmost_pen, right_edge)

    def test_manual_gallery_table_matches_the_reviewed_fixture(self):
        source = GALLERY_SCRIPT.read_text(encoding="utf-8")
        rows = []
        for index, match in enumerate(GALLERY_ROW.finditer(source)):
            values = bytes(
                int(token.strip(), 16) for token in match.group(3).split(",")
            )
            rows.append(
                {
                    "page": index // 10 + 1,
                    "slot": index % 10 + 1,
                    "label": match.group(1),
                    "expected": match.group(2),
                    "object_hex": values.hex().upper(),
                }
            )
        self.assertEqual(FIXTURE["gallery"]["rows"], rows)
        self.assertEqual(20, len(rows))
        self.assertTrue(all(len(bytes.fromhex(row["object_hex"])) == 8 for row in rows))
        self.assertIn(
            "local PAGE_1_SCREEN = 0x" + FIXTURE["gallery"]["page_1_screen_fnv1a"],
            source,
        )
        self.assertIn(
            "local PAGE_2_SCREEN = 0x" + FIXTURE["gallery"]["page_2_screen_fnv1a"],
            source,
        )


class MesenItemFormattingGalleryTests(unittest.TestCase):
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
        state = FIXTURE["gallery"]["mesen_state"]
        cls.state = ROOT / state["path"]
        if not cls.source.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        raw = cls.state.read_bytes()
        if sha1(raw).hexdigest() != state["sha1"]:
            raise AssertionError("item-gallery Mesen state SHA-1 mismatch")
        if sha256(raw).hexdigest() != state["sha256"]:
            raise AssertionError("item-gallery Mesen state SHA-256 mismatch")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "item-formatting-gallery.gbc"
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
                "could not build item-formatting gallery:\n" + built.stdout + built.stderr
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_two_gallery_pages_match_the_reviewed_framebuffers(self):
        env = os.environ.copy()
        env["GB2_ITEM_GALLERY_MSS"] = str(self.state)
        result = subprocess.run(
            [
                str(self.mesen),
                "--testrunner",
                "--enablestdout",
                "--novideo",
                "--noaudio",
                str(self.localized),
                str(GALLERY_SCRIPT),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        gallery = FIXTURE["gallery"]
        self.assertIn(
            "PASS item-formatting-gallery page1=%s page2=%s"
            % (gallery["page_1_screen_fnv1a"], gallery["page_2_screen_fnv1a"]),
            output,
        )


if __name__ == "__main__":
    unittest.main()
