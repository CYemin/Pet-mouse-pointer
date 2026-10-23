"""Read exported capes back and compare every embedded frame to source PNGs."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import plistlib
import zipfile

from PIL import Image
from build_macos_theme import ROLE_MAP, SIZES


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_theme(target, source):
    target, source = Path(target), Path(source)
    report = json.loads((target / 'verification.json').read_text(encoding='utf-8'))
    original = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    states = {s['role']: s for s in original['states']}
    timing = {s['role']: s for s in report['timing']}
    require(report['native_macos_tested'] is False, 'Native testing must remain pending')
    require(report['source_asset_revision'] == original.get('asset_revision'), 'Source revision differs')
    require(set(timing) == set(ROLE_MAP), 'Incomplete exported role set')
    totals = dict(cape_files=0, cursor_entries=0, png_strips=0, embedded_frames=0)
    for size in SIZES:
        path = target / f'{source.name}-{size}pt.cape'
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == report['sha256'][path.name], 'File hash mismatch')
        cape = plistlib.loads(data)
        require(cape['Version'] == 2 and cape['MinimumVersion'] == 2 and cape['HiDPI'], 'Invalid cape metadata')
        require(set(cape['Cursors']) == {key for keys in ROLE_MAP.values() for key in keys}, 'Incorrect Mac cursor keys')
        totals['cape_files'] += 1
        for role, keys in ROLE_MAP.items():
            state, record = states[role], timing[role]
            sequence = record['exported_sequence']
            for key in keys:
                cursor = cape['Cursors'][key]
                count = cursor['FrameCount']
                require(type(count) is int and 1 <= count <= 24, 'Frame count outside Mousecape range')
                require(count == len(sequence), 'Sequence length mismatch')
                require(math.isclose(count * cursor['FrameDuration'], sum(state['ticks']) / 60), 'Animation duration differs')
                require((cursor['PointsWide'], cursor['PointsHigh']) == (size, size), 'Logical size differs')
                require([cursor['HotSpotX'], cursor['HotSpotY']] == state['hotspots'][str(size)], 'Hotspot differs')
                require(len(cursor['Representations']) == 2, 'Expected 1x and 2x images')
                totals['cursor_entries'] += 1
                for scale, representation in enumerate(cursor['Representations'], 1):
                    with Image.open(io.BytesIO(representation)) as image:
                        require(image.format == 'PNG', 'Expected embedded PNG')
                        image = image.convert('RGBA')
                    pixels = size * scale
                    require(image.size == (pixels, pixels * count), 'Invalid vertical strip dimensions')
                    require(image.getchannel('A').getextrema()[0] == 0, 'Missing transparent background')
                    for row, frame_index in enumerate(sequence):
                        with Image.open(source / f'frames/{state["id"]}-{size}-{frame_index}.png') as expected:
                            expected = expected.convert('RGBA')
                        if scale == 2:
                            expected = expected.resize((pixels, pixels), Image.Resampling.NEAREST if state.get('pixel_art') else Image.Resampling.LANCZOS)
                        actual = image.crop((0, row * pixels, pixels, (row + 1) * pixels))
                        require(actual.tobytes() == expected.tobytes(), f'Frame pixels differ: {path.name}/{key}/{scale}x/{row}')
                        totals['embedded_frames'] += 1
                    totals['png_strips'] += 1
    return totals


def verify_collection(output, sources_root):
    output, sources_root = Path(output), Path(sources_root)
    catalog = json.loads((output / 'catalog.json').read_text(encoding='utf-8'))
    totals = dict(themes=0, cape_files=0, cursor_entries=0, png_strips=0, embedded_frames=0)
    for theme in catalog['themes']:
        result = verify_theme(output / theme['theme'], sources_root / theme['theme'])
        totals['themes'] += 1
        for key, value in result.items():
            totals[key] += value
    require(totals['themes'] == catalog['theme_count'], 'Catalog count differs')
    path = output.parent / f'{output.name}.zip'
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, 'ZIP integrity failure')
        for file in output.rglob('*'):
            if file.is_file():
                require(archive.read(f'{output.name}/{file.relative_to(output).as_posix()}') == file.read_bytes(), 'ZIP content differs')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == path.with_suffix('.zip.sha256').read_text().split()[0], 'ZIP SHA-256 mismatch')
    return dict(status='passed', native_macos_tested=False, **totals)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, default=root / 'output/pet-mouse-pointer-macos-test')
    parser.add_argument('--sources-root', type=Path, default=root / 'output')
    args = parser.parse_args()
    print(json.dumps(verify_collection(args.output, args.sources_root), ensure_ascii=False))
