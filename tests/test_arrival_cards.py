from hashlib import sha1
import io
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arrival_card_audition
import arrival_cards
import capture_dialogue
import cartridge
import english_smoke
import pyboy_state


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FONT = ROOT / "assets" / "fonts" / "candidates" / "Inter-SemiBold-4.1.ttf"
STATE = ROOT / "SaveStates" / "Mamel.state"


class ArrivalCardInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_path = ROOT / ROM_NAME
        if not source_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        cls.original = source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_asset_is_the_approved_audition_raster(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        _path, asset, _labels, selectors, _floors = arrival_cards.load_asset()
        self.assertEqual(
            arrival_card_audition.production_asset(face),
            asset,
        )
        self.assertEqual(32, len(selectors))
        self.assertEqual("Mystery Dungeon", asset["content"][30])
        self.assertEqual("Mystery Dungeon", asset["content"][31])
        floor_path, floor_asset, _blocks = arrival_card_audition.load_floor_blocks()
        self.assertEqual(
            arrival_card_audition.native_floor_asset(self.original),
            floor_asset,
        )
        self.assertEqual(arrival_card_audition.DEFAULT_FLOOR_ASSET, floor_path)

    def test_installer_is_guarded_idempotent_and_confined(self):
        output = arrival_cards.install(self.original)
        self.assertEqual(output, arrival_cards.install(output))
        changed = {
            offset
            for offset, pair in enumerate(zip(self.original, output))
            if pair[0] != pair[1]
        }
        owned = {
            offset
            for start, end in arrival_cards.owned_ranges()
            for offset in range(start, end)
        }
        checksums = {
            cartridge.HEADER_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM,
            cartridge.GLOBAL_CHECKSUM + 1,
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= owned | checksums)
        cartridge.verify_checksums(output)

        damaged = bytearray(self.original)
        damaged[arrival_cards.owned_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(
            arrival_cards.ArrivalCardError,
            "renderer changed|entry changed",
        ):
            arrival_cards.install(damaged)

        occupied = bytearray(self.original)
        occupied[arrival_cards.owned_ranges()[1][0] + 0x1000] = 1
        with self.assertRaisesRegex(
            arrival_cards.ArrivalCardError,
            "bank \\$F8 is not empty",
        ):
            arrival_cards.install(occupied)

    def test_runtime_bank_contains_every_selector_and_fits(self):
        bank, report = arrival_cards.runtime_bank(self.original)
        self.assertEqual(0x4000, len(bank))
        self.assertEqual(30, report["unique_labels"])
        self.assertEqual(32, report["selector_slots"])
        self.assertEqual(217, report["atlas_blocks"])
        self.assertLessEqual(report["used_end"], 0x8000)
        pointers_at = arrival_cards.POINTER_TABLE_ADDRESS - 0x4000
        pointers = [
            int.from_bytes(bank[pointers_at + index * 2:pointers_at + index * 2 + 2], "little")
            for index in range(32)
        ]
        self.assertEqual(pointers[25], pointers[29])
        self.assertEqual(pointers[30], pointers[31])
        self.assertNotEqual(pointers[29], pointers[30])

    def test_every_runtime_selector_decodes_to_the_approved_pixels(self):
        bank, _report = arrival_cards.runtime_bank(self.original)
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        inverse_palette = {
            0: arrival_card_audition.BRIGHT_INK,
            1: arrival_card_audition.MIDDLE_INK,
            2: arrival_card_audition.DARK_INK,
            3: arrival_card_audition.BACKGROUND,
        }

        def decode_block(block_id):
            start = (
                arrival_cards.ATLAS_ADDRESS - 0x4000
                + block_id * 64
            )
            raw = bank[start:start + 64]
            pixels = [[None] * 16 for _row in range(16)]
            for tile_x in range(2):
                for tile_y in range(2):
                    tile = raw[(tile_x * 2 + tile_y) * 16:]
                    for y in range(8):
                        low, high = tile[y * 2:y * 2 + 2]
                        for x in range(8):
                            bit = 7 - x
                            value = (
                                ((low >> bit) & 1)
                                | (((high >> bit) & 1) << 1)
                            )
                            pixels[tile_y * 8 + y][tile_x * 8 + x] = (
                                inverse_palette[value]
                            )
            return pixels

        pointer_base = arrival_cards.POINTER_TABLE_ADDRESS - 0x4000
        for selector, label in enumerate(arrival_card_audition.CARDS):
            pointer = int.from_bytes(
                bank[
                    pointer_base + selector * 2:
                    pointer_base + selector * 2 + 2
                ],
                "little",
            )
            sequence_at = pointer - 0x4000
            count = bank[sequence_at]
            block_ids = bank[sequence_at + 1:sequence_at + 1 + count]
            decoded = [[] for _row in range(16)]
            for block_id in block_ids:
                block = decode_block(block_id)
                for y in range(16):
                    decoded[y].extend(block[y])

            approved, metrics = arrival_card_audition.render_card(
                face,
                label,
                floor=None,
                style="native-aa",
            )
            left = metrics["underline_left"]
            expected = [
                [
                    approved.getpixel((x, y))
                    for x in range(left, left + count * 16)
                ]
                for y in range(40, 56)
            ]
            with self.subTest(selector=selector, label=label):
                self.assertEqual(expected, decoded)

        # Decode all 11 reusable blocks independently, then compose every
        # supported floor. This prevents a digit fragment from hiding in the
        # shared F block (the production bug first observed on 1F).
        decoded_floor_blocks = [decode_block(block_id) for block_id in range(11)]
        for glyph, decoded in zip("0123456789F", decoded_floor_blocks):
            approved_block = arrival_card_audition.floor_block(
                glyph,
                f_y_offset=arrival_card_audition.DEFAULT_AUDITION_F_Y_OFFSET,
            )
            expected_block = [
                [approved_block.getpixel((x, y)) for x in range(16)]
                for y in range(16)
            ]
            with self.subTest(floor_glyph=glyph):
                self.assertEqual(expected_block, decoded)

        for floor_number in range(1, 100):
            floor = "%dF" % floor_number
            block_ids = [int(digit) for digit in str(floor_number)] + [10]
            decoded = [[] for _row in range(16)]
            for block_id in block_ids:
                for y, row in enumerate(decoded_floor_blocks[block_id]):
                    decoded[y].extend(row)
            approved, _metrics = arrival_card_audition.render_card(
                face,
                "Ancient Ruins",
                floor=floor,
                style="native-aa",
                floor_f_y_offset=arrival_card_audition.DEFAULT_AUDITION_F_Y_OFFSET,
            )
            left = 64 if floor_number < 10 else 56
            expected = [
                [
                    approved.getpixel((x, y))
                    for x in range(left, left + len(block_ids) * 16)
                ]
                for y in range(72, 88)
            ]
            with self.subTest(floor=floor):
                self.assertEqual(expected, decoded)


class ProductionArrivalCardPixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_path = ROOT / ROM_NAME
        if not source_path.exists():
            raise unittest.SkipTest("matching original ROM is required")
        original = source_path.read_bytes()
        if sha1(original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        if not STATE.exists():
            raise unittest.SkipTest("Mamel native PyBoy state is required")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        production, _payload = english_smoke.build(original)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.production_path = Path(cls.temporary.name) / "arrival-production.gbc"
        cls.production_path.write_bytes(production)
        cls.ram = pyboy_state.cart_ram(STATE)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def capture_ancient_ruins_card(self, floor_override=None):
        pyboy = self.PyBoy(
            str(self.production_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        entered_arrival_renderer = [False]

        def at_arrival_renderer(_context=None):
            entered_arrival_renderer[0] = True
            if floor_override is not None:
                pyboy.memory[0xC130] = floor_override

        try:
            # Enter the supplied dungeon save, clear its nearby Mamel and all
            # modal text, then preserve the live generated Ancient Ruins floor.
            for frame in range(1001):
                if frame in (120, 240, 420, 600, 780, 960):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
            for _attack in range(14):
                pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                for _frame in range(120):
                    pyboy.tick()
            for _frame in range(240):
                pyboy.tick()

            # Put Shiren beside the already-generated stairs and enter them
            # through the natural Proceed route.
            old_svbk = pyboy.memory[0xFF70]
            pyboy.memory[0xFF70] = 3
            for offset in range(0x400):
                if pyboy.memory[0xD400 + offset] == 0:
                    pyboy.memory[0xD400 + offset] = 0xFF
            pyboy.memory[0xD400 + 17 * 32 + 5] = 0
            pyboy.memory[0xFF70] = old_svbk & 7
            pyboy.memory[0xFF93] = 5
            pyboy.memory[0xFF94] = 17

            pyboy.hook_register(0x7F, 0x4000, at_arrival_renderer, None)
            pyboy.button("down", capture_dialogue.PRESS_FRAMES)
            for _frame in range(180):
                pyboy.tick()
            pyboy.button("a", capture_dialogue.PRESS_FRAMES)

            candidates = []
            for _frame in range(240):
                pyboy.tick()
                if entered_arrival_renderer[0]:
                    image = pyboy.screen.image.convert("RGB").copy()
                    # The stable card has the complete native red underline.
                    if sum(
                        image.getpixel((x, arrival_card_audition.UNDERLINE_Y))
                        == arrival_card_audition.UNDERLINE
                        for x in range(160)
                    ) >= 64:
                        candidates.append(image)
            self.assertTrue(entered_arrival_renderer[0])
            self.assertTrue(candidates, "arrival card never reached its stable palette")
            return candidates[-1]
        finally:
            pyboy.stop(save=False)

    def test_ancient_ruins_card_matches_the_approved_pixels(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        expected, _metrics = arrival_card_audition.render_card(
            face,
            "Ancient Ruins",
            floor="2F",
            style="native-aa",
            floor_f_y_offset=arrival_card_audition.DEFAULT_AUDITION_F_Y_OFFSET,
        )
        actual = self.capture_ancient_ruins_card()

        rectangle = (0, 38, 160, 90)
        expected_pixels = list(expected.crop(rectangle).getdata())
        actual_pixels = list(actual.crop(rectangle).getdata())
        mismatches = sum(
            before != after
            for before, after in zip(expected_pixels, actual_pixels)
        )
        self.assertEqual(
            0,
            mismatches,
            "live Ancient Ruins 2F card differs from the approved art at %d pixels"
            % mismatches,
        )

    def test_one_floor_uses_a_clean_context_independent_f(self):
        face = arrival_card_audition.load_font(FONT, cap_height=11)
        expected, _metrics = arrival_card_audition.render_card(
            face,
            "Ancient Ruins",
            floor="1F",
            style="native-aa",
            floor_f_y_offset=arrival_card_audition.DEFAULT_AUDITION_F_Y_OFFSET,
        )
        actual = self.capture_ancient_ruins_card(floor_override=1)

        rectangle = (56, 72, 104, 89)
        expected_pixels = list(expected.crop(rectangle).getdata())
        actual_pixels = list(actual.crop(rectangle).getdata())
        mismatches = sum(
            before != after
            for before, after in zip(expected_pixels, actual_pixels)
        )
        self.assertEqual(
            0,
            mismatches,
            "live 1F card contains %d pixels outside the approved floor art"
            % mismatches,
        )

    def test_live_one_floor_optically_aligns_the_one_and_f_bright_caps(self):
        actual = self.capture_ancient_ruins_card(floor_override=1)

        # Inspect the two live runtime blocks independently.  This asserts the
        # visible relationship itself and does not rely on a framebuffer hash
        # or on the production encoder's expected output.
        def bright_top(left):
            return min(
                y
                for y in range(72, 88)
                for x in range(left, left + 16)
                if actual.getpixel((x, y)) == arrival_card_audition.BRIGHT_INK
            )

        self.assertEqual(
            bright_top(64),
            bright_top(80),
            "the live F's bright cap is one pixel lower than the 1",
        )


if __name__ == "__main__":
    unittest.main()
