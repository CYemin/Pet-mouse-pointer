"""Pixel conversion must preserve hard edges, native grids and ANI timing."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

from PIL import Image
import build_complete_theme as compiler


class PixelThemeTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / '.build-checks'
        test_root.mkdir(exist_ok=True)
        self.folder = test_root / ('pixel-test-' + uuid.uuid4().hex)
        self.folder.mkdir()
        self.source = self.folder / 'fixture.png'
        # Test data, not theme artwork: two opaque colours and transparent space.
        self.sheet = Image.new('RGBA', (16, 8))
        for x in range(1, 7):
            for y in range(1, 7):
                self.sheet.putpixel((x, y), (230, 60, 25, 255))
                self.sheet.putpixel((x + 8, y), (25, 80, 230, 255))
        self.sheet.save(self.source)
        self.spec = {'id': 'fixture', 'role': 'Arrow', 'label': 'Fixture',
                     'idea': 'Synthetic test fixture', 'source': str(self.source),
                     'grid': [2, 1], 'landmark_units': 'pixels',
                     'landmarks': [[2, 2], [2, 2]],
                     'sequence': [0, 1], 'ticks': [3, 3]}

    def tearDown(self):
        self.assertEqual(self.folder.resolve().parent,
                         (Path(__file__).resolve().parents[1] / '.build-checks').resolve())
        shutil.rmtree(self.folder)

    def build_fixture(self, **options):
        config = {'states': [dict(self.spec, role=role, id=role.lower())
                             for role in compiler.ORDER], **options}
        path = self.folder / 'config.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        out = self.folder / 'output'
        with patch.object(compiler, 'CONFIG', path), patch.object(compiler, 'OUT', out):
            with contextlib.redirect_stdout(io.StringIO()):
                compiler.build()
        return out, json.loads((out / 'manifest.json').read_text(encoding='utf-8'))

    def test_pixel_prepare_uses_one_native_grid_and_shared_anchor(self):
        frames, anchor, side = compiler.prepare(self.spec,
                                                {'pixel_art': True, 'native_pixel_size': 48})
        self.assertEqual(side, 48)
        self.assertEqual([frame.size for frame in frames], [(48, 48)] * 2)
        self.assertEqual(frames[0].getpixel(anchor), (230, 60, 25, 255))
        self.assertEqual(frames[1].getpixel(anchor), (25, 80, 230, 255))

    def test_all_roles_export_without_new_colours_or_alpha_levels(self):
        out, manifest = self.build_fixture(pixel_art=True, native_pixel_size=48)
        self.assertEqual({state['role'] for state in manifest['states']}, set(compiler.ORDER))
        palette = set(self.sheet.get_flattened_data())
        for state in manifest['states']:
            self.assertTrue(state['pixel_art'])
            self.assertEqual(state['native_pixel_size'], 48)
            self.assertEqual(state['unique_frame_count'], 2)
            self.assertEqual(state['animation_fps'], 20)
            self.assertEqual(state['visual_fps'], 20)
            for size in compiler.SIZES:
                hot = state['hotspots'][str(size)]
                self.assertTrue(all(0 <= v < size for v in hot))
                for index in range(2):
                    with Image.open(out / f'frames/{state["id"]}-{size}-{index}.png') as image:
                        self.assertEqual(image.size, (size, size))
                        self.assertLessEqual(set(image.get_flattened_data()), palette)
                data = (out / state['variants'][str(size)]).read_bytes()
                self.assertEqual(data[:4], b'RIFF')
                self.assertEqual(data[8:12], b'ACON')
                rate = data.index(b'rate')
                self.assertEqual(struct.unpack_from('<2I', data, rate + 8), (3, 3))
            with Image.open(out / f'frames/{state["id"]}-large.png') as large:
                self.assertLessEqual(set(large.get_flattened_data()), palette)
        preview = (out / 'preview.html').read_text(encoding='utf-8')
        self.assertNotIn('__MANIFEST__', preview)
        self.assertIn('image-rendering:pixelated', preview)
        self.assertIn('requestAnimationFrame', preview)
        self.assertNotIn('setTimeout(step', preview)

    def test_build_cli_uses_bundled_templates_with_a_separate_asset_root(self):
        project = self.folder / 'new pet project'
        assets = project / 'assets'
        assets.mkdir(parents=True)
        shutil.copy2(self.source, assets / 'fixture.png')
        config = {'pixel_art': True,
                  'states': [dict(self.spec, role=role, id=role.lower(),
                                  source='assets/fixture.png')
                             for role in compiler.ORDER]}
        config_path = project / 'config.json'
        config_path.write_text(json.dumps(config), encoding='utf-8')
        out = project / 'output'
        self.assertFalse((project / 'scripts').exists())
        result = subprocess.run(
            [sys.executable, str(Path(compiler.__file__).resolve()),
             '--config', str(config_path), '--root', str(project), '--output', str(out)],
            cwd=self.folder, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['states']), 17)
        self.assertTrue((out / 'preview.html').is_file())
        bundled_scripts = Path(compiler.__file__).resolve().parent
        for name in ('install-theme.ps1', 'restore-theme.ps1'):
            self.assertEqual((out / name).read_bytes(), (bundled_scripts / name).read_bytes())
        self.assertFalse((project / 'scripts').exists())

    def test_duplicate_state_ids_are_rejected_before_creating_output(self):
        states = [dict(self.spec, role=role, id=role.lower())
                  for role in compiler.ORDER]
        states[1]['id'] = states[0]['id']
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.build_fixture(states=states, pixel_art=True)
        self.assertFalse((self.folder / 'output').exists(),
                         'Invalid ids must be rejected before any output is written')

    def test_motion_audit_region_survives_compilation(self):
        region = {'roi_normalized': [0.15, 0.2, 0.85, 0.95]}
        self.spec['motion_audit'] = region
        _, manifest = self.build_fixture(pixel_art=True)
        for state in manifest['states']:
            self.assertEqual(state.get('motion_audit'), region,
                             'Motion review must receive the configured body region')

    def test_animation_rebuild_removes_superseded_static_cursors(self):
        animated=dict(self.spec)
        self.spec={**self.spec,'source_frames':[0],'landmarks':[[2,2]],
                   'sequence':[0],'ticks':[3]}
        out,_=self.build_fixture(pixel_art=True)
        self.assertEqual(len(list(out.rglob('*.cur'))),17*6)
        self.spec=animated
        self.build_fixture(pixel_art=True)
        self.assertEqual(list(out.rglob('*.cur')),[],
                         'Old static files must not ship beside their animated replacements')
        self.assertEqual(len(list(out.rglob('*.ani'))),17*6)

    def test_reviewed_small_size_hotspot_override(self):
        self.spec['hotspot_overrides']={'32':[4,5]}
        out,manifest=self.build_fixture(pixel_art=True)
        for state in manifest['states']:
            self.assertEqual(state['hotspots']['32'],[4,5])
            self.assertNotEqual(state['hotspots']['48'],[4,5])

    def test_hotspot_override_rejects_unknown_sizes_and_outside_points(self):
        for override in ({'99':[1,1]},{'32':[32,0]},{'32':[1.5,2]}):
            self.spec['hotspot_overrides']=override
            with self.assertRaises(ValueError):self.build_fixture(pixel_art=True)

    def test_handdrawn_default_keeps_existing_lanczos_conversion(self):
        raw, anchor, side = compiler.prepare(self.spec)
        out, manifest = self.build_fixture()
        self.assertFalse(manifest['states'][0]['pixel_art'])
        for size in compiler.SIZES:
            with Image.open(out / f'frames/arrow-{size}-0.png') as actual:
                expected = raw[0].resize((size, size), Image.Resampling.LANCZOS)
                self.assertEqual(actual.tobytes(), expected.tobytes())
            hot = tuple(max(0, min(size - 1, round(v * size / side))) for v in anchor)
            cursors = [compiler.cur_file([(f.resize((size, size), Image.Resampling.LANCZOS), hot)])
                       for f in raw]
            self.assertEqual((out / f'{size}/arrow.ani').read_bytes(),
                             compiler.ani_file(cursors, self.spec['sequence'], self.spec['ticks']))

    def test_timing_counts_visible_changes_instead_of_duplicate_slots(self):
        red = Image.new('RGBA', (2, 2), 'red')
        blue = Image.new('RGBA', (2, 2), 'blue')
        stats = compiler.animation_stats([red, red.copy(), blue], [0, 1, 2, 2], [3] * 4)
        self.assertEqual(stats['unique_frame_count'], 2)
        self.assertEqual(stats['animation_fps'], 20)
        self.assertEqual(stats['visual_fps'], 10)
        self.assertEqual(stats['peak_fps'], 10)
        self.assertEqual(stats['cycle_ms'], 200)

    def test_idle_hold_does_not_claim_twenty_fps_for_the_whole_loop(self):
        red = Image.new('RGBA', (2, 2), 'red')
        blue = Image.new('RGBA', (2, 2), 'blue')
        stats = compiler.animation_stats([red, blue], [0, 1, 0, 1], [180, 3, 3, 3])
        self.assertEqual(stats['peak_fps'], 20)
        self.assertAlmostEqual(stats['visual_fps'], 240 / 189, places=6)
        self.assertEqual(stats['cycle_ms'], 3150)

    def test_shared_palette_and_binary_alpha_are_deterministic(self):
        frame = Image.new('RGBA', (8, 8))
        frame.putdata([(x * 31, y * 31, (x + y) * 15, (0, 64, 127, 128, 180, 255)[x % 6])
                       for y in range(8) for x in range(8)])
        options = compiler.pixel_options({'pixel_art': True, 'pixel_palette_colors': 4}, {})
        frames = compiler.pixel_convert([frame, frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)], options)
        again = compiler.pixel_convert([frame, frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)], options)
        self.assertEqual([f.tobytes() for f in frames], [f.tobytes() for f in again])
        palette = {p[:3] for f in frames for p in f.get_flattened_data() if p[3]}
        self.assertLessEqual(len(palette), 4)
        self.assertEqual(set(frames[0].getchannel('A').get_flattened_data()), {0, 255})
        self.assertEqual(frames[0].getpixel((2, 0)), (0, 0, 0, 0))
        self.assertEqual(frames[0].getpixel((3, 0))[3], 255)

    def test_state_can_override_pixel_mode(self):
        options = compiler.pixel_options({'pixel_art': True, 'native_pixel_size': 48},
                                         {'pixel_art': False})
        self.assertFalse(options['pixel_art'])
        frames, _, side = compiler.prepare(dict(self.spec, pixel_art=False), {'pixel_art': True})
        self.assertNotEqual(side, 48)
        self.assertEqual(frames[0].width, side)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for preview timeline checks')
    def test_preview_javascript_syntax_and_absolute_ani_timeline(self):
        preview = (compiler.TOOL_DIR / 'theme-preview.html').read_text(encoding='utf-8')
        script = preview.split('<script>', 1)[1].split('</script>', 1)[0]
        check = subprocess.run(['node', '--check'], input=script.replace('__MANIFEST__', '{}'),
                               text=True, capture_output=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        frame_at = script.split('function frameAt(', 1)[1].split('\n', 1)[0]
        cases = '''
const s={sequence:[0,1,2],ticks:[3,3,6]};
const actual=[0,49,50,99,100,199,200,250,12350].map(t=>frameAt(s,t));
if(JSON.stringify(actual)!==JSON.stringify([0,0,1,1,2,2,0,1,2]))throw Error(JSON.stringify(actual));
'''
        check = subprocess.run(['node'], input='function frameAt(' + frame_at + '\n' + cases,
                               text=True, capture_output=True)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_invalid_pixel_grid_and_timing_are_rejected(self):
        for native_size in (0, -1, 48.5, True, 257):
            with self.subTest(native_size=native_size), self.assertRaises(ValueError):
                compiler.prepare(self.spec, {'pixel_art': True, 'native_pixel_size': native_size})
        for key, values in (('pixel_alpha_threshold', [0, 256, 128.5]),
                            ('pixel_palette_colors', [0, 1, 257, 4.5])):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    compiler.pixel_options({'pixel_art': True, key: value}, {})
        for sequence, ticks in (([], []), ([2], [3]), ([0], [0]), ([0], [1.5])):
            with self.subTest(sequence=sequence, ticks=ticks), self.assertRaises(ValueError):
                compiler.animation_stats([Image.new('RGBA', (2, 2))] * 2, sequence, ticks)

    def test_duplicate_roles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '17 roles'):
            self.build_fixture(states=[dict(self.spec, role=role, id=role.lower())
                                       for role in compiler.ORDER] + [self.spec])


if __name__ == '__main__':
    unittest.main()
