"""Check the Mousecape export contract without requiring macOS."""
import io
import hashlib
import json
from pathlib import Path
import plistlib
from contextlib import contextmanager
import shutil
import unittest
import uuid

from PIL import Image
from build_macos_theme import ROLE_MAP, build_theme, uniform_timeline
from verify_macos_theme import verify_theme

CHECKS = (Path(__file__).resolve().parents[1] / '.build-checks').resolve()
CHECKS.mkdir(exist_ok=True)


@contextmanager
def temporary_folder():
    folder = CHECKS / ('mac-test-' + uuid.uuid4().hex)
    folder.mkdir()
    try:
        yield folder
    finally:
        assert folder.resolve().is_relative_to(CHECKS)
        shutil.rmtree(folder)

class MacThemeTests(unittest.TestCase):
    def test_equal_duration_keeps_every_frame(self):
        sequence, duration, exact = uniform_timeline([2, 0, 1], [3, 3, 3])
        self.assertEqual(sequence, [2, 0, 1])
        self.assertEqual(duration, 0.05)
        self.assertTrue(exact)

    def test_variable_holds_are_preserved_when_within_frame_limit(self):
        sequence, duration, exact = uniform_timeline([0, 1, 2], [3, 9, 6])
        self.assertEqual(sequence, [0, 1, 1, 1, 2, 2])
        self.assertAlmostEqual(len(sequence) * duration, 18 / 60)
        self.assertTrue(exact)

    def test_long_animation_is_sampled_with_original_cycle_duration(self):
        sequence, duration, exact = uniform_timeline(list(range(30)), [3] * 30)
        self.assertEqual(len(sequence), 24)
        self.assertEqual(sequence[0], 0)
        self.assertEqual(sequence[-1], 29)
        self.assertAlmostEqual(len(sequence) * duration, 1.5)
        self.assertFalse(exact)

    def test_invalid_timing_is_rejected(self):
        for sequence, ticks in [([], []), ([0], [0]), ([0], [-1]),
                                ([0], [True]), ([0, 1], [3])]:
            with self.subTest(sequence=sequence, ticks=ticks):
                with self.assertRaises(ValueError):
                    uniform_timeline(sequence, ticks)

    def fixture(self, folder):
        assert folder.resolve().is_relative_to(CHECKS)
        source = folder / '主题 with spaces'
        (source / 'frames').mkdir(parents=True)
        states = []
        for role in list(ROLE_MAP) + ['NWPen', 'UpArrow', 'Pin', 'Person']:
            identifier = role.lower()
            states.append(dict(id=identifier, role=role, frame_count=2,
                               sequence=[0, 1], ticks=[3, 6], pixel_art=True,
                               hotspots={'32': [3, 7], '48': [5, 11]}))
            for size in (32, 48):
                for index in range(2):
                    frame = Image.new('RGBA', (size, size))
                    frame.putpixel((3, 7), (240, index * 200, 30, 255))
                    frame.save(source / f'frames/{identifier}-{size}-{index}.png')
        (source / 'manifest.json').write_text(json.dumps(dict(
            name='测试宠物', asset_revision='fixture', states=states)), encoding='utf-8')
        return source

    def test_cape_has_valid_schema_hotspots_retina_and_vertical_frame_order(self):
        with temporary_folder() as temp:
            source = self.fixture(Path(temp))
            target = Path(temp) / 'export'
            report = build_theme(source, target)
            cape = plistlib.loads((target / f'{source.name}-32pt.cape').read_bytes())
            self.assertEqual(cape['Version'], 2.0)
            self.assertTrue(cape['HiDPI'])
            self.assertEqual(set(cape['Cursors']), {key for keys in ROLE_MAP.values() for key in keys})
            cursor = cape['Cursors']['com.apple.coregraphics.Arrow']
            self.assertEqual((cursor['HotSpotX'], cursor['HotSpotY']), (3, 7))
            self.assertEqual(cursor['FrameCount'], 3)
            self.assertAlmostEqual(cursor['FrameDuration'] * 3, 0.15)
            for scale, data in enumerate(cursor['Representations'], 1):
                image = Image.open(io.BytesIO(data)).convert('RGBA')
                self.assertEqual(image.size, (32 * scale, 96 * scale))
                self.assertEqual(image.getpixel((3 * scale, 7 * scale)), (240, 0, 30, 255))
                self.assertEqual(image.getpixel((3 * scale, 39 * scale)), (240, 200, 30, 255))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(report['omitted_windows_roles'], ['NWPen', 'UpArrow', 'Pin', 'Person'])
            self.assertFalse(report['native_macos_tested'])
            self.assertTrue((target / 'preview.html').is_file())

    def test_missing_frame_fails_before_writing_package(self):
        with temporary_folder() as temp:
            source = self.fixture(Path(temp))
            (source / 'frames/arrow-48-1.png').unlink()
            target = Path(temp) / 'export'
            with self.assertRaises(FileNotFoundError):
                build_theme(source, target)
            self.assertFalse(target.exists())

    def test_unsafe_identifier_is_rejected(self):
        with temporary_folder() as temp:
            source = self.fixture(Path(temp))
            path = source / 'manifest.json'
            manifest = json.loads(path.read_text(encoding='utf-8'))
            manifest['states'][0]['id'] = '../outside'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(ValueError):
                build_theme(source, Path(temp) / 'export')

    def test_verifier_detects_wrong_pixels_even_with_matching_file_hash(self):
        with temporary_folder() as temp:
            source = self.fixture(Path(temp))
            target = Path(temp) / 'export'
            build_theme(source, target)
            self.assertEqual(verify_theme(target, source)['cape_files'], 2)
            path = target / f'{source.name}-32pt.cape'
            cape = plistlib.loads(path.read_bytes())
            cursor = cape['Cursors']['com.apple.coregraphics.Arrow']
            image = Image.open(io.BytesIO(cursor['Representations'][0])).convert('RGBA')
            image.putpixel((3, 7), (0, 0, 0, 255))
            data = io.BytesIO()
            image.save(data, format='PNG')
            cursor['Representations'][0] = data.getvalue()
            path.write_bytes(plistlib.dumps(cape))
            report_path = target / 'verification.json'
            report = json.loads(report_path.read_text(encoding='utf-8'))
            report['sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            report_path.write_text(json.dumps(report), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Frame pixels differ'):
                verify_theme(target, source)


if __name__ == '__main__':
    unittest.main()
