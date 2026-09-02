from hashlib import sha1
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import capture_dialogue
import extract
import pyboy_route
import runtime_widths
import shop_sale_count
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "selling-multiple-item.state"
STATE_SHA1 = "420d2945ded0a0f7ad147f44710ba12c35be6912"


class MultipleItemSaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("source ROM and multiple-sale state are required")
        original = source.read_bytes()
        if sha1(original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.original = original
        cls.result = extract.extract(original)
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        widths = runtime_widths.analyze(
            build.english_font.install(original), cls.result, cls.translated
        )
        cls.localized = build.build_rom(
            original,
            translations.encoded_overrides(cls.translated),
            runtime_contract=widths.contract,
        )[0]

    def test_user_fixture_is_frozen(self):
        self.assertEqual(STATE_SHA1, sha1(STATE.read_bytes()).hexdigest())

    def test_count_selector_has_one_audited_script_consumer(self):
        consumers = [
            (
                record.id,
                [(reference.group, reference.index) for reference in record.references],
            )
            for record in self.result["records"]
            if bytes.fromhex("F805") in record.raw
        ]
        self.assertEqual([("199:$49C0", [(106, 41)])], consumers)
        self.assertEqual(
            (
                "Shopkeeper: All right!<br><cF8>5 items, right?"
                "<page><box>Shopkeeper: I'll pay<br>"
                "<cF8>7 Gitan for them.<page><box>Shopkeeper: Deal?"
            ),
            self.translated[(199, 0x49C0)].text,
        )

    def test_installer_is_anchored_idempotent_and_confined(self):
        output = shop_sale_count.install(self.original)
        start, end = shop_sale_count.owned_range()
        changed = {
            offset
            for offset, pair in enumerate(zip(self.original, output))
            if pair[0] != pair[1]
        }
        checksum_bytes = {
            0x014D,
            0x014E,
            0x014F,
        }
        self.assertTrue(changed <= set(range(start, end)) | checksum_bytes)
        self.assertTrue(changed - checksum_bytes)
        self.assertEqual(
            shop_sale_count.ENGLISH_TERMINATOR,
            output[start:end],
        )
        self.assertEqual(output, shop_sale_count.install(output))
        self.assertTrue(shop_sale_count.verify(output))

        damaged = bytearray(self.original)
        damaged[start] ^= 1
        with self.assertRaisesRegex(
            shop_sale_count.ShopSaleCountError,
            "sale-count suffix",
        ):
            shop_sale_count.install(damaged)

    def test_multiple_item_count_has_no_japanese_counter_glyph(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "multiple-sale.gbc"
            rom.write_bytes(self.localized)
            pyboy = pyboy_route.start(self.PyBoy, rom, STATE)
            try:
                english = bytes.fromhex(
                    "04 24 38 43 34 3c 42 4b 24 41 38 36 37 43 4e"
                )
                leaked = bytes.fromhex("04 39 4f")
                pyboy_route.run_frames(pyboy, 60)
                pyboy_route.press(pyboy, "a")
                _frame, address = pyboy_route.wait_until(
                    pyboy,
                    lambda: pyboy_route.find_work_ram(pyboy, english),
                    840,
                )
                self.assertIsNotNone(address)
                self.assertIsNone(pyboy_route.find_work_ram(pyboy, leaked))
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
