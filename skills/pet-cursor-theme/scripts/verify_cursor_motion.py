"""Find cursor animation motion candidates; never certify a visual pass.

Usage: python scripts/verify_cursor_motion.py OUTPUT_DIRECTORY
Writes OUTPUT_DIRECTORY/motion-review/automatic-report.json, all-frame
light/dark sequence sheets and normal/slow GIFs, plus unaligned adjacent
overlays, differences and contact sheets for candidates.

Pillow is the only external dependency. Measurements use 48px-equivalent
images, including 96px exports. The largest connected alpha component is an
approximation to the head/body, excluding detached badges, question marks and
ZZZ. A manifest state may override this with motion_audit.roi_normalized:
[left, top, right, bottom]. Coordinates are fractions of the complete canvas.

Translation registration combines alpha mismatch and overlapping luminance
error. Alpha centroid/RMS radius estimate size changes without confusing a
blink with global translation. These are heuristics: attached symbols, large
limb/ear changes, rotation, intentional travel, clipping, component selection,
and low-detail art can cause false positives or missed motion. Registration
search is bounded; sub-48px details are lost. Timing is recorded by sequence
order, not perceptual playback. Hotspot opacity is deliberately NOT a pass
criterion. Every sequence edge, including last -> first, needs visual review,
even when no automatic candidate is found. Do not infer "all passed" here.
"""
import argparse
import copy
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat


MEASUREMENT_SIZE = 48
THRESHOLDS = {'translation_pixels_48': 2.0, 'registration_improvement': 0.12,
              'scale_ratio_change': 1.14, 'scale_axis_log_disagreement': 0.18,
              'unexplained_cost_floor': 0.18, 'search_radius_pixels_48': 6,
              'minimum_body_pixels_48': 32}
LIMITATIONS = [
    'The largest alpha component approximates the body; it is not semantic segmentation.',
    'Detached annotations are excluded; attached symbols or substantial limb/ear motion may bias metrics.',
    'Registration is limited to +/-6 pixels at 48px equivalent; large moves may exceed the search.',
    'RMS-radius/bounding-box scale estimates may confuse rotation or changing pose with scaling.',
    '48px-equivalent sampling can miss subpixel or fine-detail changes in larger exports.',
    'Repeated sequence entries are checked, but timing/easing and intentional movement need playback review.',
    'No candidates means only that these heuristics found none, not that the animation is visually stable.',
    'Hotspot opacity/location is not used to approve motion; fixed opaque hotpoints cannot conceal body jumps.',
]


def _normalize(frames):
    if not frames:
        raise ValueError('At least one exported frame is required')
    size = frames[0].size
    if size[0] != size[1] or not size[0]:
        raise ValueError('Cursor frames must be nonempty square images')
    if any(frame.size != size for frame in frames):
        raise ValueError('All frames in a variant must have the same dimensions')
    return [frame.convert('RGBA').resize((48, 48), Image.Resampling.NEAREST)
            for frame in frames]


def _body_feature(image, roi):
    """Use one connected body, preserving its original canvas coordinates."""
    alpha = image.getchannel('A')
    bounds = (0, 0, 48, 48)
    if roi is not None:
        if (len(roi) != 4 or not 0 <= roi[0] < roi[2] <= 1
                or not 0 <= roi[1] < roi[3] <= 1):
            raise ValueError('motion_audit.roi_normalized must be [0..1] left,top,right,bottom')
        bounds = (math.floor(roi[0]*48), math.floor(roi[1]*48),
                  math.ceil(roi[2]*48), math.ceil(roi[3]*48))
    pixels = alpha.load()
    remaining = {(x, y) for y in range(bounds[1], bounds[3])
                 for x in range(bounds[0], bounds[2]) if pixels[x, y] >= 128}
    largest = []
    while remaining:
        seed = remaining.pop()
        queue = deque([seed])
        component = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                           (1, 0), (-1, 1), (0, 1), (1, 1)):
                neighbor = (x+dx, y+dy)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        if len(component) > len(largest):
            largest = component
    mask = Image.new('L', (48, 48))
    for point in largest:
        mask.putpixel(point, 255)
    area = len(largest)
    cx = sum(p[0] for p in largest)/area if area else 0
    cy = sum(p[1] for p in largest)/area if area else 0
    radius = math.sqrt(sum((x-cx)**2+(y-cy)**2 for x, y in largest)/area) if area else 0
    return {'mask': mask, 'luma': ImageChops.multiply(image.convert('L'), mask),
            'area': area, 'centroid': [cx, cy], 'radius': radius,
            'bbox': mask.getbbox()}


def _shift(image, dx, dy):
    shifted = Image.new('L', image.size)
    shifted.paste(image, (dx, dy))  # no wrapping at the canvas edge
    return shifted


def _registration_cost(first, second, dx=0, dy=0):
    mask = _shift(second['mask'], dx, dy)
    intersection = ImageChops.darker(first['mask'], mask)
    overlap = intersection.histogram()[255]
    union = first['area'] + second['area'] - overlap
    if not union:
        return 1.0
    # Original areas penalize any pixels shifted outside the canvas.
    alpha_error = (first['area'] + second['area'] - 2*overlap)/union
    luma_error = 1.0
    if overlap:
        difference = ImageChops.difference(first['luma'], _shift(second['luma'], dx, dy))
        luma_error = ImageStat.Stat(difference, intersection).sum[0]/(255*overlap)
    return 0.7*alpha_error + 0.3*luma_error


def _measure_pair(first, second):
    before = _registration_cost(first, second)
    best, best_shift = before, (0, 0)
    if before > 1e-10:
        radius = THRESHOLDS['search_radius_pixels_48']
        shifts = sorted(((x, y) for y in range(-radius, radius+1)
                         for x in range(-radius, radius+1)),
                        key=lambda p: (p[0]**2+p[1]**2, p))
        for dx, dy in shifts:
            if (dx, dy) == (0, 0):
                continue
            cost = _registration_cost(first, second, dx, dy)
            if cost < best - 1e-10:
                best, best_shift = cost, (dx, dy)
                if best < 1e-10:
                    break
    dx, dy = (-best_shift[0], -best_shift[1])
    radius_ratio = second['radius']/first['radius'] if first['radius'] else 1.0
    a, b = first['bbox'], second['bbox']
    width_ratio = (b[2]-b[0])/(a[2]-a[0]) if a and b else 1.0
    height_ratio = (b[3]-b[1])/(a[3]-a[1]) if a and b else 1.0
    return {'translation_dx_48': dx, 'translation_dy_48': dy,
            'translation_pixels_48': math.hypot(dx, dy),
            'centroid_displacement_48': math.dist(first['centroid'], second['centroid']),
            'radius_ratio': radius_ratio, 'width_ratio': width_ratio, 'height_ratio': height_ratio,
            'registration_cost_before': before, 'registration_cost_after': best,
            'registration_improvement': (before-best)/before if before else 0.0,
            'minimum_body_area_48': min(first['area'], second['area'])}


def analyze_frames(frames, sequence=None, roi=None):
    """Return candidates for all ordered sequence edges, including loop closure.

    Frames may be any equal square size. Metrics/thresholds use 48px equivalent.
    roi, when supplied, is a fixed normalized body rectangle for every frame.
    No I/O, hotspot tests, or automatic visual-pass decision is performed here.
    """
    normalized = _normalize(frames)
    sequence = list(range(len(frames))) if sequence is None else list(sequence)
    if not sequence or any(type(i) is not int or not 0 <= i < len(frames) for i in sequence):
        raise ValueError('sequence must contain valid exported frame indices')
    features = [_body_feature(frame, roi) for frame in normalized]
    hashes = [hashlib.sha256(frame.tobytes()).digest() for frame in normalized]
    pairs, cache = [], {}
    for step, before in enumerate(sequence):
        after = sequence[(step+1) % len(sequence)]
        key = (hashes[before], hashes[after])
        if key not in cache:
            cache[key] = _measure_pair(features[before], features[after])
        pairs.append({'sequence_step': step, 'from_frame': before, 'to_frame': after,
                      'loop_closure': step == len(sequence)-1, 'metrics': dict(cache[key])})
    costs = [p['metrics']['registration_cost_before'] for p in pairs]
    median_cost = statistics.median(costs)
    baseline = {'median_registration_cost': median_cost,
                'mad_registration_cost': statistics.median(abs(v-median_cost) for v in costs),
                'median_translation_pixels_48': statistics.median(
                    p['metrics']['translation_pixels_48'] for p in pairs)}
    residual_threshold = max(THRESHOLDS['unexplained_cost_floor'],
                             median_cost + 6*baseline['mad_registration_cost'] + 0.04)
    for pair in pairs:
        metric, reasons, scores = pair['metrics'], [], [0.0]
        if metric['registration_improvement'] >= THRESHOLDS['registration_improvement']:
            score = metric['translation_pixels_48']/THRESHOLDS['translation_pixels_48']
            scores.append(score)
            if score >= 1:
                reasons.append('translation_jump')
        scale_log = abs(math.log(max(metric['radius_ratio'], 1e-6)))
        axis_disagreement = abs(math.log(metric['width_ratio']/metric['height_ratio']))
        if axis_disagreement <= THRESHOLDS['scale_axis_log_disagreement']:
            score = scale_log/math.log(THRESHOLDS['scale_ratio_change'])
            scores.append(score)
            if score >= 1:
                reasons.append('scale_change')
        if (metric['registration_cost_before'] > residual_threshold
                and metric['registration_cost_after'] > 0.10):
            reasons.append('unexplained_shape_change')
            scores.append(metric['registration_cost_before']/residual_threshold)
        if metric['minimum_body_area_48'] < THRESHOLDS['minimum_body_pixels_48']:
            reasons.append('body_not_reliably_isolated')
            scores.append(1.0)
        pair.update(score=round(max(scores), 6), baseline=dict(baseline), reasons=reasons,
                    heuristic_status='review_candidate' if reasons else 'no_candidate_detected')
        pair['metrics'] = {k: round(v, 6) if isinstance(v, float) else v
                           for k, v in metric.items()}
    boxes = [f['bbox'] for f in features if f['bbox']]
    body_roi = ([min(b[0] for b in boxes), min(b[1] for b in boxes),
                 max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None)
    return {'measurement_size': 48, 'body_selection': 'largest_alpha_component',
            'roi_normalized_override': roi, 'body_union_bbox_48': body_roi,
            'baseline': baseline, 'unused_frames': sorted(set(range(len(frames)))-set(sequence)),
            'transitions': pairs}


def _composite(image, color):
    background = Image.new('RGBA', image.size, color)
    return Image.alpha_composite(background, image.convert('RGBA')).convert('RGB')


def _save_evidence(output, state, size, pair, first, second):
    folder = output/'motion-review'
    stem = f'{state}-{size}-step{pair["sequence_step"]:03d}-{pair["from_frame"]}-to-{pair["to_frame"]}'
    display_size = 192
    before, after = _composite(first, '#22262c'), _composite(second, '#22262c')
    overlay = Image.blend(before, after, 0.5)
    difference = ImageChops.difference(before, after).point(lambda value: min(255, value*3))
    paths = {}
    for name, image in (('overlay', overlay), ('difference', difference)):
        path = folder/f'{stem}-{name}.png'
        image.resize((display_size, display_size), Image.Resampling.NEAREST).save(path)
        paths[name] = path.relative_to(output).as_posix()
    sheet = Image.new('RGB', (4*display_size, display_size+52), '#444950')
    draw = ImageDraw.Draw(sheet)
    text = (f'{state} {size}px step {pair["sequence_step"]}: {pair["from_frame"]} -> '
            f'{pair["to_frame"]}' + (' LOOP CLOSURE' if pair['loop_closure'] else ''))
    draw.text((5, 3), text, fill='white')
    draw.text((5, 18), f'shift48={pair["metrics"]["translation_pixels_48"]:.2f}px '
              f'radius ratio={pair["metrics"]["radius_ratio"]:.3f}; unaligned originals', fill='white')
    for column, (image, color, label) in enumerate(((first, '#f5f2eb', 'before / light'),
            (second, '#f5f2eb', 'after / light'), (first, '#22262c', 'before / dark'),
            (second, '#22262c', 'after / dark'))):
        thumb = _composite(image, color).resize((display_size, display_size), Image.Resampling.NEAREST)
        sheet.paste(thumb, (column*display_size, 52))
        draw.text((column*display_size+5, 36), label, fill='white')
    path = folder/f'{stem}-contact.png'
    sheet.save(path)
    paths['contact_sheet'] = path.relative_to(output).as_posix()
    return paths


def _save_sequence_evidence(output, state, size, frames, sequence, ticks):
    """Every displayed frame, both backgrounds, closure and slowed playback."""
    folder = output/'motion-review'
    columns = min(4, len(sequence)+1)
    cell_width, cell_height = size*2+18, size+25
    steps = sequence+[sequence[0]]
    sheet = Image.new('RGB', (columns*cell_width,
        math.ceil(len(steps)/columns)*cell_height+30), '#e9e4da')
    draw = ImageDraw.Draw(sheet)
    draw.text((5, 6), f'{state} {size}px | every sequence step + loop return', fill='#34281f')
    for step, index in enumerate(steps):
        x,y = step%columns*cell_width, step//columns*cell_height+30
        for offset,color in ((0,'#fffaf2'),(size+6,'#22262c')):
            sheet.paste(_composite(frames[index],color),(x+4+offset,y))
        label = f'step {step}: frame {index}' if step<len(sequence) else f'LOOP -> frame {index}'
        draw.text((x+4,y+size+3),label,fill='#34281f')
    path = folder/f'{state}-{size}-full-sequence.png'
    sheet.save(path)
    playback = []
    for index in sequence:
        panel = Image.new('RGB',(size*2+6,size),'#e9e4da')
        panel.paste(_composite(frames[index],'#fffaf2'),(0,0))
        panel.paste(_composite(frames[index],'#22262c'),(size+6,0))
        playback.append(panel)
    artifacts = {'full_sequence_contact_sheet':path.relative_to(output).as_posix()}
    for speed,multiplier in (('normal',1),('slow',4)):
        path = folder/f'{state}-{size}-{speed}.gif'
        durations = [max(10,round(tick*1000/60*multiplier/10)*10) for tick in ticks]
        playback[0].save(path,save_all=True,append_images=playback[1:],
                         duration=durations,loop=0)
        artifacts[speed+'_playback'] = path.relative_to(output).as_posix()
    return artifacts


def audit_theme(output, sizes=(48, 96)):
    """Audit an exported theme and write evidence; report always needs review."""
    output = Path(output).resolve()
    manifest_path = output/'manifest.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot read {manifest_path}: {error}') from error
    folder = output/'motion-review'
    folder.mkdir(exist_ok=True)
    records, candidate_count, checked_frames, checked_edges = [], 0, 0, 0
    for state in manifest['states']:
        identifier = state['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
            raise ValueError(f'Invalid state id: {identifier!r}')
        count = state['frame_count']
        if type(count) is not int or count < 1:
            raise ValueError(f'{identifier}: frame_count must be a positive integer')
        sequence = state.get('sequence', list(range(count)))
        ticks = state.get('ticks', [3]*len(sequence))
        if len(ticks)!=len(sequence) or any(type(t) is not int or t<=0 for t in ticks):
            raise ValueError(f'{identifier}: one positive integer duration per sequence step is required')
        roi = state.get('motion_audit', {}).get('roi_normalized')
        record = {'id': identifier, 'frame_count': count, 'sequence': sequence, 'variants': {}}
        analysis_cache = {}
        for size in sizes:
            frames = []
            for index in range(count):
                path = output/'frames'/f'{identifier}-{size}-{index}.png'
                try:
                    with Image.open(path) as image:
                        if image.size != (size, size):
                            raise ValueError(f'Expected {size}x{size}, found {image.size}')
                        frames.append(image.convert('RGBA'))
                except (OSError, ValueError) as error:
                    raise ValueError(f'Cannot audit frame {path}: {error}') from error
            normalized = _normalize(frames)
            key = tuple(hashlib.sha256(frame.tobytes()).digest() for frame in normalized)
            if key in analysis_cache:
                result = copy.deepcopy(analysis_cache[key][1])
                result['metrics_reused_from_size'] = analysis_cache[key][0]
            else:
                result = analyze_frames(normalized, sequence, roi)
                analysis_cache[key] = (size, copy.deepcopy(result))
            for pair in result['transitions']:
                pair.update(state=identifier, size=size)
                checked_edges += 1
                if pair['heuristic_status'] == 'review_candidate':
                    candidate_count += 1
                    pair['artifacts'] = _save_evidence(output, identifier, size, pair,
                        frames[pair['from_frame']], frames[pair['to_frame']])
            checked_frames += count
            result['all_frame_artifacts'] = _save_sequence_evidence(
                output,identifier,size,frames,sequence,ticks)
            record['variants'][str(size)] = result
        records.append(record)
    report = {'status': 'needs_visual_review', 'automatic_pass': False,
              'visual_review_required': True, 'asset_revision': manifest.get('asset_revision'),
              'source_manifest': 'manifest.json', 'sizes_checked': list(sizes),
              'measurement_size': 48, 'states_checked': len(records),
              'exported_frames_checked': checked_frames, 'sequence_edges_checked': checked_edges,
              'candidate_count': candidate_count, 'thresholds': THRESHOLDS,
              'score_definition': 'Maximum normalized translation/scale/residual heuristic; >=1 is a review candidate, not proof of jitter.',
              'baseline_definition': 'Per-state sequence median and MAD are context; absolute translation/scale limits remain active even when every edge moves.',
              'limitations': LIMITATIONS,
              'review_instructions': [
                  'Review every state/frame and last-to-first transition at actual 48px and 96px on light and dark backgrounds.',
                  'For candidates inspect unaligned overlays, differences and contact sheets; distinguish intended expression from whole-body jumps.',
                  'Review unflagged transitions too; neither zero candidates nor opaque hotspots certify stability.',
                  'Record an explicit visual-review.json bound to this asset_revision before claiming all motion checks passed.',
              ], 'states': records}
    (folder/'automatic-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                               encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('output', type=Path, help='Built theme directory containing manifest.json and frames/')
    args = parser.parse_args(argv)
    try:
        report = audit_theme(args.output)
    except (ValueError, KeyError) as error:
        print(f'Motion audit failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps({key: report[key] for key in ('status', 'states_checked',
        'exported_frames_checked', 'sequence_edges_checked', 'candidate_count')}, indent=2))
    print(f'Evidence: {args.output / "motion-review" / "automatic-report.json"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
