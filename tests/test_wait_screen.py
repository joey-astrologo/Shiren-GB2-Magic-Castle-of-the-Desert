from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import english_smoke
import wait_screen


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
ASSET_PATH = ROOT / "assets" / "graphics" / "wait_screen.json"
ASSET_SHA256 = "d38cf756b5a9742575a1e281d261e7bd83164455289d1b6f5e13c23c82ea165b"
SYMBOLS = ".lg#"
BANK = 0x56
TOP_ADDRESS = 0x7A80
BOTTOM_ADDRESS = 0x7C80
BIRD_ADDRESSES = (0x7B80, 0x7D80)
BLOCK_BYTES = 0x100


def offset(bank, address):
    return bank * 0x4000 + address - 0x4000


def read_block(rom, address):
    start = offset(BANK, address)
    return bytes(rom[start:start + BLOCK_BYTES])


def decode_block(data):
    """Decode sixteen column-major tiles to one 64x16 symbol raster."""
    if len(data) != BLOCK_BYTES:
        raise ValueError("wait-screen block must be 256 bytes")
    rows = [["."] * 64 for _ in range(16)]
    for column in range(8):
        for tile_row in range(2):
            tile = data[(column * 2 + tile_row) * 16:][:16]
            for y in range(8):
                low, high = tile[y * 2:y * 2 + 2]
                for x in range(8):
                    bit = 7 - x
                    value = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
                    rows[tile_row * 8 + y][column * 8 + x] = SYMBOLS[value]
    return ["".join(row) for row in rows]


def decode_sign(rom):
    return (
        decode_block(read_block(rom, TOP_ADDRESS))
        + decode_block(read_block(rom, BOTTOM_ADDRESS))
    )


class WaitScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        cls.original = cls.source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.asset = json.loads(ASSET_PATH.read_text(encoding="utf-8"))

    def test_approved_source_preserves_the_native_sign_outside_text(self):
        self.assertEqual(ASSET_SHA256, sha256(ASSET_PATH.read_bytes()).hexdigest())
        self.assertEqual(["Please", "wait..."], self.asset["content"])
        self.assertEqual([33, 74, 97, 106], self.asset["layout"]["screen_rect"])
        self.assertEqual(32, len(self.asset["rows"]))
        self.assertTrue(all(len(row) == 64 for row in self.asset["rows"]))
        self.assertTrue(all(set(row) <= set(SYMBOLS) for row in self.asset["rows"]))

        native = decode_sign(self.original)
        changed = {
            (x, y)
            for y, (before, after) in enumerate(zip(native, self.asset["rows"]))
            for x, (old, new) in enumerate(zip(before, after))
            if old != new
        }
        allowed = {
            (x, y)
            for y in range(8, 18)
            for x in range(6, 41)
        } | {
            (x, y)
            for y in range(18, 28)
            for x in range(6, 59)
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)

        font = self.asset["font"]
        for key in ("spec", "glyph_source", "license"):
            path = ROOT / font[key]
            self.assertEqual(font[key + "_sha256"], sha256(path.read_bytes()).hexdigest())

    def test_native_blocks_and_interleaved_bird_art_are_frozen(self):
        blocks = self.asset["native_blocks"]
        self.assertEqual(
            blocks[0]["original_sha256"],
            sha256(read_block(self.original, TOP_ADDRESS)).hexdigest(),
        )
        self.assertEqual(
            blocks[1]["original_sha256"],
            sha256(read_block(self.original, BOTTOM_ADDRESS)).hexdigest(),
        )
        for address, record in zip(
            BIRD_ADDRESSES,
            self.asset["preserved_interleaved_bird_blocks"],
        ):
            self.assertEqual(
                record["sha256"],
                sha256(read_block(self.original, address)).hexdigest(),
            )

    def test_asset_and_rom_ownership_summary_are_frozen(self):
        self.assertEqual(
            {
                "asset": "assets/graphics/wait_screen.json",
                "asset_sha256": ASSET_SHA256,
                "content": ["Please", "wait..."],
                "screen_rect": [33, 74, 97, 106],
                "blocks": [
                    {
                        "name": "top",
                        "source": "56:$7A80-$7B7F",
                        "bytes": 256,
                        "original_sha256": (
                            "4c8b018b97475bb18ac952aaa0951006d2d749628733a590bedeec97c3af4192"
                        ),
                        "localized_sha256": (
                            "8af82c6faeebc91d6cdbdc089b0af18b89da9e5597790d2d57826f8bf1491b38"
                        ),
                    },
                    {
                        "name": "bottom",
                        "source": "56:$7C80-$7D7F",
                        "bytes": 256,
                        "original_sha256": (
                            "65d74b28ce217f454be340e6939dc323c0cff463cb18e58126b4dfd86867ff11"
                        ),
                        "localized_sha256": (
                            "5f0e0691637e51f767c069f0e8b0b69ac322e89c4e08f86c8cdcdb6b0e8ab047"
                        ),
                    },
                ],
                "preserved_bird_blocks": [
                    {
                        "source": "56:$7B80-$7C7F",
                        "sha256": (
                            "d90084aa3116e657c49af91810adb0db5227551ee9ba92365027a335a8448383"
                        ),
                    },
                    {
                        "source": "56:$7D80-$7E7F",
                        "sha256": (
                            "a47de45b2ca8abdea344d3afa08661b4c1e90119e25619a798ba261f4db59d24"
                        ),
                    },
                ],
            },
            wait_screen.summary(self.original),
        )

    def test_installer_is_guarded_idempotent_and_confined(self):
        output = wait_screen.install(self.original)
        self.assertEqual(output, wait_screen.install(output))
        changed = {
            at
            for at, (before, after) in enumerate(zip(self.original, output))
            if before != after
        }
        owned = {
            at
            for start, end in wait_screen.owned_ranges()
            for at in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed <= owned | checksums)
        for owned_range in wait_screen.owned_ranges():
            self.assertTrue(changed & set(range(*owned_range)))

        for address in BIRD_ADDRESSES:
            self.assertEqual(read_block(self.original, address), read_block(output, address))

        damaged_sign = bytearray(self.original)
        damaged_sign[wait_screen.owned_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(
            wait_screen.WaitScreenError,
            "native sign block changed unexpectedly",
        ):
            wait_screen.install(damaged_sign)

        damaged_bird = bytearray(self.original)
        damaged_bird[offset(BANK, BIRD_ADDRESSES[0])] ^= 1
        with self.assertRaisesRegex(
            wait_screen.WaitScreenError,
            "preserved bird block changed unexpectedly",
        ):
            wait_screen.install(damaged_bird)

    def test_production_rom_contains_the_approved_wait_sign_pixels(self):
        production, _payload = english_smoke.build(self.original)
        actual = decode_sign(production)
        expected = self.asset["rows"]
        mismatches = [
            (x, y)
            for y, (wanted, got) in enumerate(zip(expected, actual))
            for x, (wanted_pixel, got_pixel) in enumerate(zip(wanted, got))
            if wanted_pixel != got_pixel
        ]
        self.assertEqual(
            0,
            len(mismatches),
            "production wait sign differs from approved art at %d pixels"
            % len(mismatches),
        )

        for address in BIRD_ADDRESSES:
            self.assertEqual(
                read_block(self.original, address),
                read_block(production, address),
            )


if __name__ == "__main__":
    unittest.main()
