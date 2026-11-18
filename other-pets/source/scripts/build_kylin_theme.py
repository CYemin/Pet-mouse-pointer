"""Export a packaged Windows theme's original frames as a UKUI/Xcursor pilot."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from struct import pack, unpack_from
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

IMAGE_TYPE = 0xfffd0002
FILE_VERSION = 0x10000

# Use both traditional X11 names and the corresponding modern cursor names.
CURSOR_NAMES = {
    'Arrow': ('left_ptr', 'default', 'arrow'),
    'Help': ('question_arrow', 'help'),
    'AppStarting': ('left_ptr_watch', 'progress', 'half-busy'),
    'Wait': ('watch', 'wait'),
    'Crosshair': ('crosshair', 'cross', 'tcross'),
    'IBeam': ('xterm', 'text', 'ibeam'),
    'NWPen': ('pencil',),
    'No': ('not-allowed', 'forbidden', 'crossed_circle', 'no-drop'),
    'SizeNS': ('sb_v_double_arrow', 'ns-resize', 'row-resize', 'size_ver', 'n-resize', 's-resize'),
    'SizeWE': ('sb_h_double_arrow', 'ew-resize', 'col-resize', 'size_hor', 'e-resize', 'w-resize'),
    'SizeNWSE': ('nwse-resize', 'size_fdiag', 'nw-resize', 'se-resize', 'top_left_corner', 'bottom_right_corner'),
    'SizeNESW': ('nesw-resize', 'size_bdiag', 'ne-resize', 'sw-resize', 'top_right_corner', 'bottom_left_corner'),
    'SizeAll': ('fleur', 'move', 'all-scroll', 'size_all'),
    'UpArrow': ('center_ptr', 'up-arrow'),
    'Hand': ('hand2', 'pointer', 'hand1', 'pointing_hand'),
    'Pin': ('pet-pin',),
    'Person': ('pet-person',),
}


def riff_chunks(data, start):
    while start < len(data):
        tag, length = unpack_from('<4sI', data, start)
        first = start + 8
        stop = first + length
        if stop > len(data):
            raise ValueError('Truncated Windows RIFF chunk')
        yield tag, data[first:stop]
        start = stop + length % 2
    if start != len(data):
        raise ValueError('Invalid Windows RIFF padding')


def windows_cursor_frames(data, size, hotspot, state):
    """Read the 32-bit CUR frames embedded in this project's legacy ANI files."""
    if data[:4] != b'RIFF' or data[8:12] != b'ACON' or unpack_from('<I', data, 4)[0] + 8 != len(data):
        raise ValueError('Expected a RIFF animated cursor')
    chunks = list(riff_chunks(data, 12))
    frames, = (chunk for tag, chunk in chunks if tag == b'LIST' and chunk[:4] == b'fram')
    blocks = dict(chunks)
    for tag, key in ((b'seq ', 'sequence'), (b'rate', 'ticks')):
        expected = state[key]
        if unpack_from(f'<{len(expected)}I', blocks[tag]) != tuple(expected):
            raise ValueError(f'Published ANI {key} differs from the manifest')
    cursor_frames = [chunk for tag, chunk in riff_chunks(frames, 4) if tag == b'icon']
    if len(cursor_frames) != state['frame_count']:
        raise ValueError('Published ANI frame count differs from the manifest')
    for cursor in cursor_frames:
        if unpack_from('<HHH', cursor) != (0, 2, 1):
            raise ValueError('Expected one CUR image per animation frame')
        width, height, _, _, xhot, yhot, length, offset = unpack_from('<BBBBHHII', cursor, 6)
        if (width, height) != (size, size) or (xhot, yhot) != hotspot:
            raise ValueError('CUR dimensions or hotspot differ from the manifest')
        dib = unpack_from('<IiiHHI', cursor, offset)
        start = offset + 40
        stop = start + size * size * 4
        if dib != (40, size, 2 * size, 1, 32, 0) or not stop <= offset + length <= len(cursor):
            raise ValueError('Expected a complete 32-bit BGRA cursor bitmap')
        bgra = np.frombuffer(cursor[start:stop], dtype=np.uint8).reshape(size, size, 4)
        yield bgra[::-1, :, [2, 1, 0, 3]]


def source_frames(archive, directory, state, sizes):
    elapsed = 0
    delays = []
    for ticks in state['ticks']:
        end = elapsed + ticks
        delay = round(Fraction(end * 1000, 60)) - round(Fraction(elapsed * 1000, 60))
        if delay <= 0:
            raise ValueError('Expected a positive frame delay')
        delays.append(delay)
        elapsed = end
    for size in sizes:
        hotspot = tuple(state['hotspots'][str(size)])
        paths = {frame: (directory / 'frames' / f'{state["id"]}-{size}-{frame}.png').as_posix()
                 for frame in set(state['sequence'])}
        ani_frames = None
        if not all(path in archive.NameToInfo for path in paths.values()):
            path = directory / state['variants'][str(size)]
            ani_frames = list(windows_cursor_frames(archive.read(path.as_posix()), size, hotspot, state))
        pixels_by_frame = {}
        for frame, delay in zip(state['sequence'], delays, strict=True):
            if frame not in pixels_by_frame:
                if ani_frames is None:
                    with Image.open(BytesIO(archive.read(paths[frame]))) as png:
                        rgba = np.asarray(png.convert('RGBA'), dtype=np.uint16)
                else:
                    rgba = ani_frames[frame].astype(np.uint16)
                x, y = hotspot
                if rgba.shape != (size, size, 4) or not (0 <= x < size and 0 <= y < size):
                    raise ValueError(f'{state["id"]}/{size}: invalid image size or hotspot')
                if rgba[y, x, 3] == 0:
                    raise ValueError(f'{state["id"]}/{size}/{frame}: transparent hotspot')
                alpha = rgba[:, :, 3:4]
                rgb = (rgba[:, :, :3] * alpha + 127) // 255
                pixels_by_frame[frame] = np.concatenate(
                    (rgb[:, :, ::-1], alpha), axis=-1).astype(np.uint8).tobytes()
            yield size, hotspot, delay, pixels_by_frame[frame]


def encode_cursor(frames):
    header = bytearray(pack('<4sIII', b'Xcur', 16, FILE_VERSION, len(frames)))
    offset = 16 + len(frames) * 12
    chunks = bytearray()
    for size, (xhot, yhot), delay, pixels in frames:
        header += pack('<III', IMAGE_TYPE, size, offset)
        chunks += pack('<9I', 36, IMAGE_TYPE, size, 1, size, size, xhot, yhot, delay)
        chunks += pixels
        offset += 36 + len(pixels)
    return bytes(header + chunks)


def verify_cursor(data, frames):
    magic, header, version, count = unpack_from('<4sIII', data)
    if (magic, header, version, count) != (b'Xcur', 16, FILE_VERSION, len(frames)):
        raise ValueError('Invalid cursor header')
    next_chunk = header + count * 12
    for index, (size, (xhot, yhot), delay, pixels) in enumerate(frames):
        toc = unpack_from('<III', data, header + index * 12)
        if toc != (IMAGE_TYPE, size, next_chunk):
            raise ValueError('Invalid cursor table of contents')
        chunk = unpack_from('<9I', data, next_chunk)
        if chunk != (36, IMAGE_TYPE, size, 1, size, size, xhot, yhot, delay):
            raise ValueError('Cursor frame metadata does not match the source')
        start = next_chunk + 36
        next_chunk = start + size * size * 4
        if data[start:next_chunk] != pixels:
            raise ValueError('Cursor pixels do not match the source')
    if len(data) != next_chunk:
        raise ValueError('Unexpected bytes in cursor file')


def build(source, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as original, tempfile.TemporaryDirectory(dir=output.parent) as temp:
        manifest_path, = (PurePosixPath(n) for n in original.namelist() if n.endswith('/manifest.json'))
        manifest = json.loads(original.read(manifest_path.as_posix()))
        sizes = manifest['sizes']
        if set(CURSOR_NAMES) != {state['role'] for state in manifest['states']}:
            raise ValueError('Expected all 17 source roles')
        slug = manifest_path.parts[0]
        name = manifest['name']
        folder = f'pet-cursor-{slug}'
        staged = Path(temp) / output.name
        with ZipFile(staged, 'w', ZIP_DEFLATED) as archive:
            archive.writestr(f'{folder}/index.theme', f'[Icon Theme]\nName={name}\n')
            for state in manifest['states']:
                frames = list(source_frames(original, manifest_path.parent, state, sizes))
                data = encode_cursor(frames)
                verify_cursor(data, frames)
                for cursor in CURSOR_NAMES[state['role']]:
                    archive.writestr(f'{folder}/cursors/{cursor}', data)
            archive.writestr('安装说明.txt', (
                f'{name} · 麒麟桌面试装包\n\n'
                '01 安装：完整解压 ZIP，在解压目录打开终端，执行以下两行命令：\n'
                'mkdir -p "$HOME/.icons"\n'
                f'cp -R "{folder}" "$HOME/.icons/"\n\n'
                '02 应用：打开「设置 → 个性化 → 主题」中的光标主题设置，'
                f'选择「{name}」。若列表未刷新，可重开设置窗口或注销后重新登录。\n'
                '03 调整大小：若系统提供光标大小选项，可在系统里调整。'
                f'主题内含 {"/".join(str(s) for s in sizes)} px 五种原始尺寸。\n'
                '04 恢复：回到光标主题设置，选回原主题。\n\n'
                '保留原有 17 组素材。桌面和应用会按各自支持的光标名称调用，'
                '位置和人员两个状态使用自定义名称。\n'
                '制作时已核对 Xcursor 文件结构、帧、热点与播放延时。银河麒麟桌面实装待验证。\n'
            ).encode('utf-8-sig'))
        with ZipFile(staged) as archive:
            if archive.testzip() or len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError('Invalid archive')
        staged.replace(output)
    print(f'{name}: {len(manifest["states"])} source states, {len(sizes)} sizes')


def build_catalog(root, jobs):
    queue = root / 'output/expansion-20261112/production-queue.json'
    items = json.loads(queue.read_text(encoding='utf-8'))['items']
    tasks = []
    for item in items:
        source, = (root / path for path in item['packages'] if path.endswith('-Windows.zip'))
        breed, color = item['breed'], item['color']
        group = f'{breed}-{color}'
        output = root / 'downloads' / '麒麟' / breed / group / f'{group}-麒麟.zip'
        tasks.append((source, output))
    errors = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        pending = [(output, pool.submit(build, source, output)) for source, output in tasks]
        for output, task in pending:
            try:
                task.result()
            except (ValueError, KeyError, IndexError, OSError) as exc:
                errors.append(f'{output.name}: {exc}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Exported {len(tasks)} themes across {len({item["breed"] for item in items})} breeds.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?')
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--catalog', action='store_true')
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    if args.catalog and args.source is None and args.output is None:
        build_catalog(Path(__file__).resolve().parents[1], args.jobs)
    elif not args.catalog and args.source is not None and args.output is not None:
        build(args.source, args.output)
    else:
        parser.error('Specify source and output paths, or --catalog.')
