"""Synthetic regressions for cursor body motion, not the cursor artwork."""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import unittest
import uuid

from PIL import Image, ImageDraw

import verify_cursor_motion as motion


@contextmanager
def pack_folder():
    # mkdtemp's mode=0700 strips inherited Windows sandbox permissions. A
    # unique normal directory keeps fixtures writable without changing ACLs.
    workspace = Path(__file__).resolve().parents[1]
    folder = (workspace / ('.motion-test-' + uuid.uuid4().hex)).resolve()
    folder.mkdir()
    try:
        yield folder
    finally:
        # Verify the exact resolved target before recursive cleanup.
        if folder.resolve().parent != workspace or not folder.name.startswith('.motion-test-'):
            raise RuntimeError('Temporary fixture escaped the workspace')
        shutil.rmtree(folder)


def sprite(dx=0, blink=False, paw=False, annotation=0, scale=1.0):
    """The small fixed badge/hotpoint must not conceal a moving main body."""
    body = Image.new('RGBA', (48, 48))
    draw = ImageDraw.Draw(body)
    draw.rectangle((14, 14, 36, 40), fill='#533629')
    draw.rectangle((16, 16, 34, 38), fill='#ead5a5')
    draw.rectangle((31, 17, 40, 30), fill='#a47742')
    draw.rectangle((12 if paw else 13, 33, 17, 36), fill='#ead5a5')
    draw.rectangle((21, 21, 25, 24), fill='#ead5a5' if blink else '#201b19')
    if blink:
        draw.line((21, 23, 25, 23), fill='#201b19')
    else:
        draw.point((22, 22), fill='white')
    if scale != 1.0:
        bounds = body.getbbox()
        crop = body.crop(bounds)
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)),
                           Image.Resampling.NEAREST)
        body = Image.new('RGBA', (48, 48))
        body.paste(crop, (round(26.5 - crop.width / 2),
                         round(27.0 - crop.height / 2)), crop)
    result = Image.new('RGBA', (48, 48))
    result.paste(body, (dx, 0), body)
    draw = ImageDraw.Draw(result)
    draw.rectangle((3, 3, 5, 5), fill='#533629')
    if annotation:
        draw.rectangle((41, 3, 41 + annotation - 1, 3 + annotation - 1),
                       fill='#a47742')
    return result


def write_pack(folder, frames):
    (folder / 'frames').mkdir()
    state = {'id': 'synthetic', 'role': 'Arrow', 'frame_count': len(frames),
             'sequence': list(range(len(frames))), 'hotspots': {'48': [4, 4], '96': [8, 8]}}
    (folder / 'manifest.json').write_text(json.dumps({'asset_revision': 'test-revision',
        'sizes': [48, 96], 'states': [state]}), encoding='utf-8')
    for size in (48, 96):
        for index, frame in enumerate(frames):
            frame.resize((size, size), Image.Resampling.NEAREST).save(
                folder / 'frames' / f'synthetic-{size}-{index}.png')


class CursorMotionTests(unittest.TestCase):
    def test_fixed_body_blink_and_tiny_paw_motion_do_not_flag(self):
        result = motion.analyze_frames([sprite(), sprite(blink=True, paw=True), sprite()])
        self.assertEqual(len(result['transitions']), 3)
        self.assertFalse(any(p['heuristic_status'] == 'review_candidate'
                             for p in result['transitions']))

    def test_four_pixel_body_jump_is_found_with_opaque_fixed_hotpoint(self):
        frames = [sprite(), sprite(), sprite(dx=4)]
        self.assertTrue(all(frame.getpixel((4, 4))[3] == 255 for frame in frames))
        result = motion.analyze_frames(frames)
        jump = result['transitions'][1]
        self.assertEqual(jump['heuristic_status'], 'review_candidate')
        self.assertIn('translation_jump', jump['reasons'])
        self.assertGreaterEqual(jump['metrics']['translation_pixels_48'], 3.5)

    def test_two_pixel_body_jump_is_found_despite_fixed_hotpoint(self):
        frames = [sprite(), sprite(dx=2)]
        self.assertTrue(all(frame.getpixel((4, 4))[3] == 255 for frame in frames))
        result = motion.analyze_frames(frames)
        self.assertIn('translation_jump', result['transitions'][0]['reasons'])
        self.assertGreaterEqual(result['transitions'][0]['metrics']['translation_pixels_48'], 2)

    def test_last_to_first_jump_is_audited_even_after_smooth_forward_motion(self):
        result = motion.analyze_frames([sprite(dx=i) for i in range(5)])
        self.assertFalse(any(p['heuristic_status'] == 'review_candidate'
                             for p in result['transitions'][:-1]))
        seam = result['transitions'][-1]
        self.assertEqual((seam['from_frame'], seam['to_frame']), (4, 0))
        self.assertTrue(seam['loop_closure'])
        self.assertIn('translation_jump', seam['reasons'])

    def test_large_detached_annotation_does_not_move_body_registration(self):
        result = motion.analyze_frames([sprite(annotation=0), sprite(annotation=6),
                                        sprite(annotation=2), sprite(annotation=0)])
        self.assertFalse(any(p['heuristic_status'] == 'review_candidate'
                             for p in result['transitions']))

    def test_uniform_body_scale_jump_is_a_review_candidate(self):
        result = motion.analyze_frames([sprite(), sprite(scale=1.25), sprite()])
        self.assertIn('scale_change', result['transitions'][0]['reasons'])
        self.assertGreater(result['transitions'][0]['metrics']['radius_ratio'], 1.15)

    def test_explicit_sequence_and_repeated_frames_are_preserved(self):
        result = motion.analyze_frames([sprite(), sprite(blink=True)], [0, 1, 1, 0])
        self.assertEqual([(p['from_frame'], p['to_frame']) for p in result['transitions']],
                         [(0, 1), (1, 1), (1, 0), (0, 0)])

    def test_96px_measurement_uses_48px_equivalent_thresholds(self):
        frames = [sprite(), sprite(dx=4)]
        small = motion.analyze_frames(frames)
        large = motion.analyze_frames([f.resize((96, 96), Image.Resampling.NEAREST)
                                       for f in frames])
        self.assertEqual([p['reasons'] for p in small['transitions']],
                         [p['reasons'] for p in large['transitions']])
        self.assertAlmostEqual(small['transitions'][0]['score'],
                               large['transitions'][0]['score'])

    def test_cli_writes_evidence_and_never_claims_automatic_visual_pass(self):
        with pack_folder() as folder:
            write_pack(folder, [sprite(), sprite(), sprite(dx=4)])
            self.assertEqual(motion.main([str(folder)]), 0)
            report_path = folder / 'motion-review' / 'automatic-report.json'
            report = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'needs_visual_review')
            self.assertTrue(report['visual_review_required'])
            self.assertFalse(report['automatic_pass'])
            self.assertEqual(report['asset_revision'], 'test-revision')
            self.assertEqual(report['sizes_checked'], [48, 96])
            pairs = report['states'][0]['variants']['48']['transitions']
            flagged = [p for p in pairs if p['heuristic_status'] == 'review_candidate']
            self.assertTrue(flagged)
            for pair in flagged:
                self.assertIn('baseline', pair)
                self.assertIn('score', pair)
                for name in ('overlay', 'difference', 'contact_sheet'):
                    self.assertTrue((folder / pair['artifacts'][name]).is_file())

    def test_zero_candidates_still_requires_visual_review(self):
        with pack_folder() as folder:
            write_pack(folder, [sprite(), sprite(blink=True), sprite()])
            report = motion.audit_theme(folder)
            self.assertEqual(report['candidate_count'], 0)
            self.assertEqual(report['status'], 'needs_visual_review')
            self.assertFalse(report['automatic_pass'])
            artifacts = report['states'][0]['variants']['48']['all_frame_artifacts']
            self.assertTrue((folder/artifacts['full_sequence_contact_sheet']).is_file())
            self.assertTrue((folder/artifacts['slow_playback']).is_file())

    def test_missing_export_is_reported_with_frame_path(self):
        with pack_folder() as folder:
            write_pack(folder, [sprite(), sprite()])
            missing = folder / 'frames' / 'synthetic-96-1.png'
            missing.unlink()
            with self.assertRaisesRegex(ValueError, 'synthetic-96-1.png'):
                motion.audit_theme(folder)


if __name__ == '__main__':
    unittest.main()
