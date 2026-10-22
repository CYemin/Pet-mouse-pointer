"""Check functional-arrow isolation, anchoring and preserved animation content."""
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from operation_marks import apply_operation_marks, _remove_old

ROOT = Path(__file__).resolve().parents[1]


class OperationMarkTests(unittest.TestCase):
    def fixture(self):
        frames = []
        for color in ('#d69a52', '#edbb74'):
            frame = Image.new('RGBA', (48, 48))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((23, 22, 41, 43), fill='#79502f')
            draw.rectangle((27, 26, 29, 28), fill=color)
            marker = Image.open(ROOT/'assets/operation-marks-v1/size-we.png').convert('RGBA').resize((14, 7), Image.Resampling.NEAREST)
            frame.alpha_composite(marker, (6, 3))
            frames.append(frame)
        return frames

    def test_disabled_state_is_exact_noop(self):
        frames = self.fixture()
        result, anchor = apply_operation_marks(frames, (13, 7), {'id': 'normal'}, {}, ROOT)
        self.assertIs(result, frames)
        self.assertEqual(anchor, (13, 7))

    def test_mark_is_fixed_and_animation_difference_survives(self):
        frames = self.fixture()
        result, anchor = apply_operation_marks(frames, (13, 7),
            {'id': 'size-we', 'operation_mark': {'family': 'sheltie'}}, {}, ROOT)
        self.assertEqual(anchor, (16, 9))
        self.assertEqual(result[0].crop((3, 3, 29, 16)).tobytes(), result[1].crop((3, 3, 29, 16)).tobytes())
        self.assertNotEqual(result[0].tobytes(), result[1].tobytes())
        for image in result:
            self.assertEqual(image.getpixel(anchor)[3], 255)
            self.assertLessEqual(set(image.getchannel('A').get_flattened_data()), {0, 255})

    def test_touching_mark_removal_protects_reviewed_pet_region(self):
        frame = Image.new('RGBA', (48, 48))
        draw = ImageDraw.Draw(frame)
        draw.rectangle((3, 3, 8, 15), fill='#3f2618')
        draw.rectangle((8, 10, 25, 30), fill='#f0c986')
        result = _remove_old(frame, (3, 3, 9, 16), [(8, 10, 9, 16)], 100)
        self.assertEqual(result.getpixel((8, 12)), frame.getpixel((8, 12)))
        self.assertEqual(result.getpixel((6, 10))[3], 0)
        self.assertEqual(result.getpixel((20, 20)), frame.getpixel((20, 20)))

    def test_clipping_geometry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'clips'):
            apply_operation_marks(self.fixture(), (13, 7),
                {'id': 'size-we', 'operation_mark': {'family': 'sheltie', 'marker_pos': [40, 40]}}, {}, ROOT)


if __name__ == '__main__':
    unittest.main()
