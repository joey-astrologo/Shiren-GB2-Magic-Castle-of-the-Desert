from hashlib import sha1, sha256
import json
from pathlib import Path
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
import capture_dialogue
import pyboy_fixtures
import pyboy_route
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "item_formatting.json").read_text(
        encoding="utf-8"
    )
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

    def test_gallery_contains_twenty_reviewed_native_records(self):
        rows = FIXTURE["gallery"]["rows"]
        self.assertEqual(20, len(rows))
        self.assertEqual(list(range(1, 11)) * 2, [row["slot"] for row in rows])
        self.assertEqual([1] * 10 + [2] * 10, [row["page"] for row in rows])
        self.assertTrue(
            all(len(bytes.fromhex(row["object_hex"])) == 8 for row in rows)
        )
        self.assertEqual("Club", rows[0]["expected"])
        self.assertEqual("Preservation Pot[5]", rows[-1]["expected"])


class PyBoyItemFormattingGalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        state = FIXTURE["gallery"]["pyboy_state"]
        cls.state = ROOT / state["path"]
        if not cls.source.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        raw = cls.state.read_bytes()
        if sha1(raw).hexdigest() != state["sha1"]:
            raise AssertionError("item-gallery PyBoy state SHA-1 mismatch")
        if sha256(raw).hexdigest() != state["sha256"]:
            raise AssertionError("item-gallery PyBoy state SHA-256 mismatch")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

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

    def test_two_gallery_pages_render_through_the_native_item_menu(self):
        pyboy = pyboy_route.start(self.PyBoy, self.localized, self.state)
        records = [
            bytes.fromhex(row["object_hex"])
            for row in FIXTURE["gallery"]["rows"]
        ]
        try:
            targets = pyboy_fixtures.install_item_gallery(pyboy, records)
            self.assertEqual(
                bytes(targets),
                pyboy_route.work_read(
                    pyboy, pyboy_fixtures.INVENTORY,
                    pyboy_fixtures.INVENTORY_SLOTS,
                ),
            )
            for frame in range(701):
                if frame == 120:
                    pyboy_route.press(pyboy, "b")
                elif frame == 220:
                    pyboy_route.press(pyboy, "a")
                elif frame == 480:
                    pyboy_route.press(pyboy, "right")
                pyboy.tick()
                if frame == 400:
                    page_one = pyboy.screen.image.copy()
            page_two = pyboy.screen.image.copy()
            self.assertNotEqual(page_one.tobytes(), page_two.tobytes())
            for page in (page_one, page_two):
                # Both native pages contain item-name ink throughout the list,
                # while the static width test above guards the right boundary.
                ink = sum(
                    page.getpixel((x, y))[:3] == (0, 0, 0)
                    for x in range(6, 145) for y in range(16, 128)
                )
                self.assertGreater(ink, 500)
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
