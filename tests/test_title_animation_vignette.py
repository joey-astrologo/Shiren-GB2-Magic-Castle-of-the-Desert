from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import title_animation_vignette


class TitleAnimationVignetteTests(unittest.TestCase):
    def test_default_schedule_keeps_every_frame_of_one_flash_cycle(self):
        frames = title_animation_vignette.frame_schedule(
            title_animation_vignette.DEFAULT_FIRST_FRAME,
            title_animation_vignette.DEFAULT_LAST_FRAME,
            title_animation_vignette.DEFAULT_FRAME_STEP,
        )
        self.assertEqual(tuple(range(600, 660)), frames)
        self.assertEqual(60, len(frames))

    def test_contact_sheet_preserves_every_supplied_frame_at_native_pixels(self):
        frames = []
        for index in range(10):
            image = Image.new("RGB", title_animation_vignette.SCREEN_SIZE, (index, 0, 0))
            frames.append((600 + index, image))

        sheet = title_animation_vignette.compose_contact_sheet(
            frames,
            columns=4,
            scale=2,
        )
        self.assertEqual((1280, 912), sheet.size)
        for index in range(10):
            column = index % 4
            row = index // 4
            sample = (
                column * 320 + 10,
                row * 304 + title_animation_vignette.LABEL_HEIGHT * 2 + 10,
            )
            self.assertEqual((index, 0, 0), sheet.getpixel(sample))

    def test_default_gif_cadence_preserves_a_one_second_sixty_frame_cycle(self):
        frames = [
            (
                600 + index,
                Image.new(
                    "RGB",
                    title_animation_vignette.SCREEN_SIZE,
                    (index * 4, index * 3, index * 2),
                ),
            )
            for index in range(60)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "title.gif"
            title_animation_vignette.write_gif(frames, output, scale=1)
            with Image.open(output) as animation:
                durations = []
                for index in range(animation.n_frames):
                    animation.seek(index)
                    durations.append(animation.info["duration"])
                self.assertEqual(60, animation.n_frames)
                self.assertEqual(1000, sum(durations))


if __name__ == "__main__":
    unittest.main()
