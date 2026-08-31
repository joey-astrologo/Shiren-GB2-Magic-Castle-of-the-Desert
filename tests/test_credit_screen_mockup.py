from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import credit_screen_mockup


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FONT_PATH = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"
FONT_SPEC_PATH = ROOT / "assets" / "fonts" / "candidates" / "inter_semibold_4_1.json"
LICENSE_PATH = ROOT / "licenses" / "OFL-1.1-Inter.txt"
EXPECTED_FONT_SHA256 = \
    "78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3"
EXPECTED_LICENSE_SHA256 = \
    "262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a"


class CreditScreenMockupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom_path = ROOT / ROM_NAME
        if not cls.rom_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        if sha1(cls.rom_path.read_bytes()).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def test_candidate_font_has_frozen_identity_and_ofl_provenance(self):
        self.assertTrue(FONT_PATH.exists())
        self.assertEqual(EXPECTED_FONT_SHA256, sha256(FONT_PATH.read_bytes()).hexdigest())
        spec = json.loads(FONT_SPEC_PATH.read_text(encoding="utf-8"))
        self.assertEqual("Inter", spec["family"])
        self.assertEqual("SemiBold", spec["style"])
        self.assertEqual("4.1", spec["version"])
        self.assertEqual("SIL Open Font License 1.1", spec["license"])
        self.assertEqual(EXPECTED_FONT_SHA256, spec["sha256"])
        self.assertEqual("licenses/OFL-1.1-Inter.txt", spec["license_file"])
        self.assertEqual(
            EXPECTED_LICENSE_SHA256,
            sha256(LICENSE_PATH.read_bytes()).hexdigest(),
        )

    def test_mockup_replaces_only_the_two_native_name_bands(self):
        native = credit_screen_mockup.capture_native_credit(
            self.rom_path, self.PyBoy
        )
        candidate = credit_screen_mockup.render_candidate(native, FONT_PATH)
        self.assertEqual((160, 144), candidate.size)

        replacement_rows = {
            y
            for line in credit_screen_mockup.LINES
            for y in range(line.top, line.bottom)
        }
        native_pixels = native.load()
        candidate_pixels = candidate.load()
        for y in range(144):
            if y in replacement_rows:
                continue
            for x in range(160):
                self.assertEqual(native_pixels[x, y], candidate_pixels[x, y])

    def test_mockup_uses_gb2_palette_and_native_line_regions(self):
        native = credit_screen_mockup.capture_native_credit(
            self.rom_path, self.PyBoy
        )
        candidate = credit_screen_mockup.render_candidate(native, FONT_PATH)
        self.assertEqual(
            {
                (0, 0, 0),
                (64, 64, 64),
                (120, 120, 120),
                (248, 248, 248),
            },
            set(candidate.getdata()),
        )

        for line in credit_screen_mockup.LINES:
            bounds = credit_screen_mockup.ink_bounds(candidate, line)
            self.assertEqual(line.left, bounds[0])
            self.assertGreaterEqual(bounds[1], line.top)
            self.assertLessEqual(bounds[2], 151)
            self.assertLess(bounds[3], line.bottom)
            colors = credit_screen_mockup.ink_colors(candidate, line)
            self.assertEqual(
                {(64, 64, 64), (120, 120, 120), (248, 248, 248)},
                colors,
            )

    def test_mockup_wording_does_not_add_an_untranslated_role(self):
        self.assertEqual(
            ["CHUNSOFT", "Koichi Sugiyama"],
            [line.text for line in credit_screen_mockup.LINES],
        )


if __name__ == "__main__":
    unittest.main()
