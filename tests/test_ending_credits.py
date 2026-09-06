from hashlib import sha1
import io
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import cartridge
import ending_credits
import ending_credits_audition
import english_smoke


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
STATE = ROOT / "SaveStates" / "ending-one.state"
STATE_SHA1 = "3ef2a74e1e926d1fd79df0c45d51b683b5793004"

STAFF_TITLE_LINES = (
    "Shiren the Wanderer GB2",
    "Magic Castle of the Desert",
    "- Development Staff -",
)
STAFF_TITLE_BANDS = (38, 58, 78)
STAFF_TITLE_CAP_HEIGHT = 8


def approved_staff_title_pixels():
    """Independently compose the approved English staff-roll title card."""
    face = ending_credits_audition.load_font(
        ending_credits_audition.DEFAULT_FONT
    )
    screen = Image.new(
        "RGB",
        ending_credits_audition.SCREEN_SIZE,
        ending_credits_audition.BLACK,
    )
    for text, band_top in zip(STAFF_TITLE_LINES, STAFF_TITLE_BANDS):
        masks = ending_credits_audition._level_masks(
            face, text, STAFF_TITLE_CAP_HEIGHT
        )
        if masks[0].width > ending_credits.PLANE_WIDTH:
            masks = tuple(
                mask.resize(
                    (ending_credits.PLANE_WIDTH, mask.height),
                    Image.Resampling.NEAREST,
                )
                for mask in masks
            )
        width, height = masks[0].size
        left = (screen.width - width) // 2
        top = band_top + (ending_credits_audition.LINE_BAND_HEIGHT - height) // 2
        for mask, color in zip(
            masks,
            (
                ending_credits_audition.DARK,
                ending_credits_audition.MID,
                ending_credits_audition.WHITE,
            ),
        ):
            ink = Image.new("RGB", mask.size, color)
            screen.paste(ink, (left, top), mask)
    return screen


class EndingCreditsInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.is_file():
            raise unittest.SkipTest("matching original ROM is required")
        cls.original = cls.source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_native_card_plane_contract_covers_all_twenty_approved_cards(self):
        title_start, title_end = ending_credits.title_range()
        self.assertEqual(0x0800, title_end - title_start)
        self.assertEqual(
            ending_credits.TITLE_PLANE.original_sha256,
            __import__("hashlib").sha256(
                self.original[title_start:title_end]
            ).hexdigest(),
        )
        self.assertEqual(20, len(ending_credits.CARD_PLANES))
        self.assertEqual(
            len(ending_credits_audition.CREDITS),
            len(ending_credits.CARD_PLANES),
        )
        for plane, (start, end) in zip(
            ending_credits.CARD_PLANES, ending_credits.card_ranges()
        ):
            with self.subTest(source=plane.source):
                self.assertEqual(plane.byte_count, end - start)
                self.assertEqual(
                    plane.original_sha256,
                    __import__("hashlib").sha256(
                        self.original[start:end]
                    ).hexdigest(),
                )
                self.assertEqual(0, plane.byte_count % 0x100)
                self.assertLessEqual(
                    plane.screen_top + plane.pixel_height,
                    ending_credits_audition.SCREEN_SIZE[1],
                )

    def test_approved_planes_encode_the_audition_and_reserve_a_blank_map_tile(self):
        face = ending_credits_audition.load_font(
            ending_credits_audition.DEFAULT_FONT
        )
        localized = ending_credits.localized_planes()
        localized_title = ending_credits.localized_title_plane()
        approved_title = approved_staff_title_pixels()
        self.assertEqual(
            localized_title,
            ending_credits.encode_card(
                approved_title, ending_credits.TITLE_PLANE
            ),
        )
        self.assertEqual(20, len(localized))
        for credit, plane, pixels in zip(
            ending_credits_audition.CREDITS,
            ending_credits.CARD_PLANES,
            localized,
        ):
            approved, _metrics = ending_credits_audition.render_card(face, credit)
            with self.subTest(role=credit.role):
                self.assertEqual(plane.byte_count, len(pixels))
                self.assertEqual(pixels, ending_credits.encode_card(approved, plane))
                blank_offset = (ending_credits.MAP_BLANK_TILE - 0x80) * 16
                self.assertEqual(
                    bytes(16), pixels[blank_offset:blank_offset + 16]
                )

    def test_installer_is_guarded_idempotent_and_confined(self):
        output = ending_credits.install(self.original)
        self.assertEqual(output, ending_credits.install(output))
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.original, output))
            if before != after
        }
        owned = {
            offset
            for start, end in ending_credits.owned_ranges()
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

        damaged_map = bytearray(self.original)
        damaged_map[ending_credits.owned_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(
            ending_credits.EndingCreditsError,
            "blank-map instruction changed",
        ):
            ending_credits.install(damaged_map)

        damaged_card = bytearray(self.original)
        damaged_card[ending_credits.card_ranges()[0][0]] ^= 1
        with self.assertRaisesRegex(
            ending_credits.EndingCreditsError,
            "plane .* changed unexpectedly",
        ):
            ending_credits.install(damaged_card)


class ProductionEndingCreditsPixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.is_file() or not STATE.is_file():
            raise unittest.SkipTest("matching ending ROM/state fixture is required")
        cls.original = cls.source_path.read_bytes()
        if sha1(cls.original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        if sha1(STATE.read_bytes()).hexdigest() != STATE_SHA1:
            raise unittest.SkipTest("ending state hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.production, _payload = english_smoke.build(cls.original)

    @classmethod
    def capture_frames(cls, rom_bytes, frames):
        wanted = set(frames)
        captured = {}
        with tempfile.TemporaryDirectory() as temporary:
            rom_path = Path(temporary) / "ending-credits-production.gbc"
            rom_path.write_bytes(rom_bytes)
            pyboy = cls.PyBoy(
                str(rom_path),
                window="null",
                sound_emulated=False,
                ram_file=io.BytesIO(bytes(0x8000)),
            )
            pyboy.set_emulation_speed(0)
            try:
                with STATE.open("rb") as handle:
                    pyboy.load_state(handle)
                for frame in range(max(wanted) + 1):
                    pyboy.tick()
                    if frame in wanted:
                        captured[frame] = pyboy.screen.image.convert("RGB").copy()
            finally:
                pyboy.stop(save=False)
        return captured

    def test_first_live_staff_card_matches_the_approved_english_pixels(self):
        face = ending_credits_audition.load_font(
            ending_credits_audition.DEFAULT_FONT
        )
        expected, _metrics = ending_credits_audition.render_card(
            face, ending_credits_audition.CREDITS[0]
        )

        actual = self.capture_frames(
            self.production,
            (ending_credits_audition.STABLE_CARD_FRAMES[0],),
        )[ending_credits_audition.STABLE_CARD_FRAMES[0]]

        mismatches = [
            (x, y)
            for y in range(expected.height)
            for x in range(expected.width)
            if actual.getpixel((x, y)) != expected.getpixel((x, y))
        ]
        self.assertEqual(
            [],
            mismatches,
            "first live staff card differs from the approved English raster "
            "at %d pixels" % len(mismatches),
        )

    def test_all_live_staff_cards_match_the_approved_english_pixels(self):
        face = ending_credits_audition.load_font(
            ending_credits_audition.DEFAULT_FONT
        )
        actual = self.capture_frames(
            self.production, ending_credits_audition.STABLE_CARD_FRAMES
        )
        for credit in ending_credits_audition.CREDITS:
            expected, _metrics = ending_credits_audition.render_card(face, credit)
            mismatch_count = sum(
                expected_pixel != actual_pixel
                for expected_pixel, actual_pixel in zip(
                    expected.getdata(), actual[credit.frame].getdata()
                )
            )
            with self.subTest(frame=credit.frame, role=credit.role):
                self.assertEqual(
                    0,
                    mismatch_count,
                    "live staff card differs from approved English art at "
                    "%d pixels" % mismatch_count,
                )

    def test_staff_roll_title_matches_the_approved_english_pixels(self):
        expected = approved_staff_title_pixels()
        actual = self.capture_frames(self.production, (200,))[200]
        mismatch_count = sum(
            expected_pixel != actual_pixel
            for expected_pixel, actual_pixel in zip(
                expected.getdata(), actual.getdata()
            )
        )
        self.assertEqual(
            0,
            mismatch_count,
            "live staff-roll title differs from approved English art at "
            "%d pixels" % mismatch_count,
        )

    def test_japanese_end_mark_remains_pixel_identical_to_native(self):
        frame = ending_credits_audition.END_MARK_FRAME
        native = self.capture_frames(self.original, (frame,))[frame]
        actual = self.capture_frames(self.production, (frame,))[frame]
        mismatch_count = sum(
            native_pixel != actual_pixel
            for native_pixel, actual_pixel in zip(
                native.getdata(), actual.getdata()
            )
        )
        self.assertEqual(
            0,
            mismatch_count,
            "preserved Japanese end mark changed at %d pixels"
            % mismatch_count,
        )


if __name__ == "__main__":
    unittest.main()
