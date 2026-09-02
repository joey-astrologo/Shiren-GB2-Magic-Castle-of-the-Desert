from hashlib import sha1
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build
import extract
import runtime_widths
import shop_sale_count
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "selling-multiple-item.mss"
STATE_SHA1 = "f95f9ff9e3475bc740975a5608c9349949bf0df4"


class MultipleItemSaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mesen = Path("/Applications/Mesen.app/Contents/MacOS/Mesen")
        if not mesen.is_file():
            raise unittest.SkipTest("Mesen is unavailable")
        source = ROOT / ROM_NAME
        if not source.is_file() or not STATE.is_file():
            raise unittest.SkipTest("source ROM and multiple-sale state are required")
        original = source.read_bytes()
        if sha1(original).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.mesen = mesen
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
            env = os.environ.copy()
            env["GB2_MULTIPLE_SALE_MSS"] = str(STATE)
            result = subprocess.run(
                [
                    str(self.mesen),
                    "--testrunner",
                    "--enablestdout",
                    "--novideo",
                    "--noaudio",
                    str(rom),
                    str(ROOT / "tests" / "mesen_shop_sale_count.lua"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-8000:])
        self.assertIn("PASS multiple sale renders 4 items, right?", output)


if __name__ == "__main__":
    unittest.main()
