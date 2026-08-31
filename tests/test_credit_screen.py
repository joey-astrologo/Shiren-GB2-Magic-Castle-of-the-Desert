from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import credit_screen
import credit_screen_mockup
import english_smoke


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FONT_PATH = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"


class CreditScreenInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        cls.original = cls.source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_asset_and_native_plane_contract_are_frozen(self):
        self.assertEqual(
            {
                "asset": "assets/graphics/credit_screen_inter.json",
                "asset_sha256": (
                    "e73eb9c426fced709e12e6799ced8caca3f84c5b218bbaa1cc12d21d6825234a"
                ),
                "font_sha256": (
                    "78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3"
                ),
                "plane": {
                    "source": "F3:$5D00-$64FF",
                    "bytes": 2048,
                    "native_sha256": (
                        "1166addacdee2b6aa38f609f3dcc21ea9d92fd24fa7d6b5ed067ba0c3652e3e4"
                    ),
                    "destination": "VRAM bank 1 $8800-$8FFF",
                },
                "strips": [
                    {
                        "name": "chunsoft",
                        "text": "CHUNSOFT",
                        "source": "F3:$5F00-$60FF",
                        "screen_rect": [16, 56, 144, 72],
                        "original_sha256": (
                            "152ba82ee7a2b467f63335a42428161c4d40d88a00b47276724b5b7fac8a3527"
                        ),
                        "localized_sha256": (
                            "9738a71b4ffb37997fdede58473aac709b12bd613252febf37d8130b2f9b9eac"
                        ),
                        "bytes": 512,
                    },
                    {
                        "name": "koichi_sugiyama",
                        "text": "Koichi Sugiyama",
                        "source": "F3:$6300-$64FF",
                        "screen_rect": [16, 88, 144, 104],
                        "original_sha256": (
                            "25181d51ffc79fe7afe9acc33cc98776fbccd4b9c9ddd7022423ec495c1965e0"
                        ),
                        "localized_sha256": (
                            "386b18d4e013cbfafba5f44b26f82d3f7d97f85ea77c663e75ec9e7c9f27a1ab"
                        ),
                        "bytes": 512,
                    },
                ],
            },
            credit_screen.summary(self.original),
        )

    def test_installer_is_guarded_idempotent_and_confined(self):
        output = credit_screen.install(self.original)
        self.assertEqual(output, credit_screen.install(output))
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.original, output))
            if before != after
        }
        owned = {
            offset
            for start, end in credit_screen.owned_ranges()
            for offset in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed <= owned | checksums)
        self.assertTrue(changed & set(range(*credit_screen.owned_ranges()[0])))
        self.assertTrue(changed & set(range(*credit_screen.owned_ranges()[1])))

        damaged = bytearray(self.original)
        damaged[credit_screen.owned_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(
            credit_screen.CreditScreenError,
            "native strip changed unexpectedly",
        ):
            credit_screen.install(damaged)


class ProductionCreditScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        cls.original = cls.source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.production, _payload = english_smoke.build(cls.original)

    @classmethod
    def capture_frames(cls, rom_path, frame_numbers):
        wanted = set(frame_numbers)
        frames = {}
        pyboy = cls.PyBoy(str(rom_path), window="null", sound_emulated=False)
        try:
            for frame in range(max(wanted) + 1):
                pyboy.tick()
                if frame in wanted:
                    frames[frame] = pyboy.screen.image.convert("RGB").copy()
        finally:
            pyboy.stop(save=False)
        return frames

    def test_production_build_renders_the_approved_credit_name_pixels(self):
        native = credit_screen_mockup.capture_native_credit(
            self.source_path, self.PyBoy
        )
        expected = credit_screen_mockup.render_candidate(native, FONT_PATH)
        frozen = json.loads(credit_screen.DEFAULT_ASSET.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen,
            credit_screen_mockup.frozen_asset(expected, FONT_PATH),
        )
        with tempfile.TemporaryDirectory() as temporary:
            production_path = Path(temporary) / "credit-production.gbc"
            production_path.write_bytes(self.production)
            actual = credit_screen_mockup.capture_native_credit(
                production_path, self.PyBoy
            )

        replacement_rows = {
            y
            for line in credit_screen_mockup.LINES
            for y in range(line.top, line.bottom)
        }
        mismatches = [
            (x, y)
            for y in replacement_rows
            for x in range(160)
            if actual.getpixel((x, y)) != expected.getpixel((x, y))
        ]
        self.assertEqual(
            0,
            len(mismatches),
            "production credit differs from approved art at %d name-band pixels"
            % len(mismatches),
        )

        for y in range(144):
            if y in replacement_rows:
                continue
            for x in range(160):
                self.assertEqual(native.getpixel((x, y)), actual.getpixel((x, y)))

    def test_production_credit_uses_native_fade_and_title_handoff(self):
        credit_frames = (280, 300, 320, 440, 480)
        all_frames = credit_frames + (240, 520)
        with tempfile.TemporaryDirectory() as temporary:
            production_path = Path(temporary) / "credit-production.gbc"
            production_path.write_bytes(self.production)
            native = self.capture_frames(self.source_path, all_frames)
            actual = self.capture_frames(production_path, all_frames)

        stable_candidate = credit_screen_mockup.render_candidate(
            native[320], FONT_PATH
        )
        stable_palette = credit_screen_mockup.PALETTE
        replacement_rows = {
            y
            for line in credit_screen_mockup.LINES
            for y in range(line.top, line.bottom)
        }

        # Before the card appears and after it hands off to the title, production
        # must remain pixel-identical to the clean ROM.
        self.assertEqual(list(native[240].getdata()), list(actual[240].getdata()))
        self.assertEqual(list(native[520].getdata()), list(actual[520].getdata()))

        for frame in credit_frames:
            frame_palette = tuple(sorted(set(native[frame].getdata())))
            self.assertEqual(4, len(frame_palette))
            shade = dict(zip(stable_palette, frame_palette))
            expected = native[frame].copy()
            for y in replacement_rows:
                for x in range(160):
                    expected.putpixel((x, y), shade[stable_candidate.getpixel((x, y))])
            self.assertEqual(
                list(expected.getdata()),
                list(actual[frame].getdata()),
                "credit transition differs at frame %d" % frame,
            )


if __name__ == "__main__":
    unittest.main()
