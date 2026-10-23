"""Export existing reviewed PNG frames as Mousecape themes; never apply cursors.

Schema/role references: alexzielenski/Mousecape, MCDefs.m and MCCursor.m.
Mousecape's apply.m limits animation to 24 equally timed frames.
"""
import argparse
import base64
from bisect import bisect_right
import hashlib
import html
import io
import json
from math import gcd
from pathlib import Path
import plistlib
import re
import shutil
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ROLE_MAP = {
    'Arrow': ('com.apple.coregraphics.Arrow',),
    'Help': ('com.apple.cursor.40',),
    'AppStarting': ('com.apple.cursor.4',),
    'Wait': ('com.apple.coregraphics.Wait',),
    'Crosshair': ('com.apple.cursor.7', 'com.apple.cursor.8'),
    'IBeam': ('com.apple.coregraphics.IBeam',),
    'No': ('com.apple.cursor.3',),
    'SizeNS': ('com.apple.cursor.23', 'com.apple.cursor.32'),
    'SizeWE': ('com.apple.cursor.19', 'com.apple.cursor.28'),
    'SizeNWSE': ('com.apple.cursor.34',),
    'SizeNESW': ('com.apple.cursor.30',),
    'SizeAll': ('com.apple.coregraphics.Move',),
    'Hand': ('com.apple.cursor.2', 'com.apple.cursor.13'),
}
SIZES = (32, 48)


def uniform_timeline(sequence, ticks):
    """Expand exact holds, or sample at bin centres, keeping the cycle duration."""
    if not sequence or len(sequence) != len(ticks):
        raise ValueError('Sequence and timing must have the same nonzero length')
    if any(type(t) is not int or t <= 0 for t in ticks):
        raise ValueError('ANI ticks must be positive integers')
    if any(type(i) is not int or i < 0 for i in sequence):
        raise ValueError('Frame indices must be nonnegative integers')
    quantum = gcd(*ticks)
    count = sum(ticks) // quantum
    if count <= 24:
        return [i for i, t in zip(sequence, ticks) for _ in range(t // quantum)], quantum / 60, True
    boundaries = []
    elapsed = 0
    for t in ticks:
        elapsed += t
        boundaries.append(elapsed)
    sampled = [sequence[bisect_right(boundaries, (i + 0.5) * elapsed / 24)] for i in range(24)]
    return sampled, elapsed / 60 / 24, False


def make_cursor(source, state, size):
    identifier = state['id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', identifier):
        raise ValueError('Invalid state identifier')
    count = state['frame_count']
    if type(count) is not int or not 1 <= count <= 256:
        raise ValueError('Invalid source frame count')
    sequence, duration, exact = uniform_timeline(state['sequence'], state['ticks'])
    if max(state['sequence']) >= count:
        raise ValueError('Animation refers to a missing frame')
    hotspot = state['hotspots'][str(size)]
    if len(hotspot) != 2 or any(type(v) is not int or not 0 <= v < size for v in hotspot):
        raise ValueError('Hotspot outside cursor bounds')
    frames = []
    for i in range(count):
        with Image.open(source / f'frames/{identifier}-{size}-{i}.png') as image:
            if image.size != (size, size):
                raise ValueError('Frame dimensions do not match the requested size')
            frames.append(image.convert('RGBA'))
    # Derive 2x from the same base geometry: independent rounded hotspots in
    # the Windows size variants can otherwise move the click point on Retina.
    resampling = Image.Resampling.NEAREST if state.get('pixel_art') else Image.Resampling.LANCZOS
    representations = []
    for scale in (1, 2):
        pixels = size * scale
        strip = Image.new('RGBA', (pixels, pixels * len(sequence)))
        for row, index in enumerate(sequence):
            frame = frames[index]
            if scale != 1:
                frame = frame.resize((pixels, pixels), resampling)
            strip.paste(frame, (0, row * pixels))
        data = io.BytesIO()
        strip.save(data, format='PNG')
        representations.append(data.getvalue())
    cursor = dict(FrameCount=len(sequence), FrameDuration=duration,
                  HotSpotX=float(hotspot[0]), HotSpotY=float(hotspot[1]),
                  PointsWide=float(size), PointsHigh=float(size),
                  Representations=representations)
    timing = dict(role=state['role'], id=identifier, label=state.get('label', state['role']),
                  source_frames=count, exported_frames=len(sequence),
                  frame_duration_seconds=duration, cycle_seconds=sum(state['ticks']) / 60,
                  timing_exact=exact, exported_sequence=sequence,
                  mac_identifiers=list(ROLE_MAP[state['role']]))
    return cursor, timing


def preview_page(name, variants):
    cards = []
    for size, entries in variants.items():
        for cursor, timing in entries:
            data = base64.b64encode(cursor['Representations'][1]).decode('ascii')
            frames = cursor['FrameCount']
            cycle = frames * cursor['FrameDuration']
            style = (f'width:{size}px;height:{size}px;background-image:url(data:image/png;base64,{data});'
                     f'background-size:{size}px {size * frames}px;'
                     f'--end:-{size * frames}px;animation:play {cycle}s steps({frames}) infinite;')
            label = html.escape(timing['label'])
            image = f'<span class="cursor" style="{style}"><i style="left:{cursor["HotSpotX"]}px;top:{cursor["HotSpotY"]}px"></i></span>'
            cards.append(f'<article><h3>{label} · {size}pt</h3><div class="stages"><div>{image}</div><div class="dark">{image}</div></div>'
                         f'<p>{frames} 帧 · {cycle:.3f}s · {"原节奏" if timing["timing_exact"] else "等时采样"}</p></article>')
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(name)} · Mac 动画预览</title><style>'
            'body{font:16px system-ui;margin:32px;background:#f5f2ed;color:#342c25}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}'
            'article{border:1px solid #d7cdc1;border-radius:12px;padding:16px;background:white}h3{font-size:16px}p{font-size:13px}'
            '.stages{display:flex}.stages>div{display:grid;place-items:center;background:#faf9f6;width:50%;height:110px}.stages>.dark{background:#252831}'
            '.cursor{display:block;background-repeat:no-repeat;position:relative;image-rendering:pixelated}.cursor i{display:none;position:absolute;width:5px;height:5px;'
            'border:1px solid #ff325d;transform:translate(-50%,-50%);border-radius:50%;background:#fffa}body.hotspots i{display:block}'
            '@keyframes play{to{background-position:0 var(--end)}}@media(prefers-reduced-motion:reduce){.cursor{animation-play-state:paused!important}}'
            '</style>'
            f'<h1>{html.escape(name)} · macOS 测试版</h1><p>预览使用 .cape 中的相同帧条和节奏。1×/2×共用点击坐标，红点为热点；此页不能证明 macOS 系统应用成功。</p>'
            '<button onclick="document.body.classList.toggle(\'hotspots\')">显示 / 隐藏点击点</button> '
            '<button onclick="for(const e of document.querySelectorAll(\'.cursor\'))e.style.animationPlayState=e.style.animationPlayState===\'paused\'?\'running\':\'paused\'">暂停 / 播放</button>'
            '<main>' + ''.join(cards) + '</main></html>')


def build_theme(source, target):
    source, target = Path(source), Path(target)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    states = manifest['states']
    roles = [state['role'] for state in states]
    if len(set(roles)) != len(roles) or not set(ROLE_MAP).issubset(roles):
        raise ValueError('Missing or duplicate cursor roles')
    name = manifest['name']
    slug = source.name
    variants, files = {}, {}
    timings = []
    for size in SIZES:
        cursors, entries = {}, []
        for state in states:
            if state['role'] not in ROLE_MAP:
                continue
            cursor, timing = make_cursor(source, state, size)
            entries.append((cursor, timing))
            for key in ROLE_MAP[state['role']]:
                cursors[key] = cursor
            if size == SIZES[0]:
                timings.append(timing)
        variants[size] = entries
        cape = dict(Author='CYemin', CapeName=f'{name} · Mac {size}pt (Test)',
                    CapeVersion=1.0, Cloud=False, Cursors=cursors, HiDPI=True,
                    Identifier=f'io.github.cyemin.pet-cursors.{slug}.{size}pt',
                    MinimumVersion=2.0, Version=2.0)
        files[f'{slug}-{size}pt.cape'] = plistlib.dumps(cape, fmt=plistlib.FMT_XML)
    report = dict(status='structural-checks-passed', native_macos_tested=False,
                  system_settings_modified=False, name=name, theme=slug,
                  source_asset_revision=manifest.get('asset_revision'),
                  sizes_points=list(SIZES), scales=[1, 2], source_roles_exported=len(ROLE_MAP),
                  mac_cursor_entries=len(cursors),
                  omitted_windows_roles=[r for r in roles if r not in ROLE_MAP],
                  retina_method='2x derived from base frame to preserve hotspot geometry',
                  timing=timings,
                  sha256={n: hashlib.sha256(data).hexdigest() for n, data in files.items()})
    # Finish all input validation before writing a partial theme.
    target.mkdir(parents=True, exist_ok=True)
    for filename, data in files.items():
        (target / filename).write_bytes(data)
    (target / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (target / 'preview.html').write_text(preview_page(name, variants), encoding='utf-8')
    (target / 'README.md').write_text(
        f'# {name} · macOS 测试版\n\n'
        '需要先安装 [Mousecape](https://github.com/alexzielenski/Mousecape/releases)。本包不附带第三方程序。\n\n'
        f'1. 完整解压，双击 `{slug}-32pt.cape` 导入 Mousecape。\n'
        '2. 在 Mousecape 主题列表中选中导入的主题，使用 Apply 应用。大号请选择 `48pt.cape` 结尾的文件。\n'
        '3. 恢复时使用 Mousecape 菜单 `Capes → Restore Defaults`；恢复后再删除本主题。\n'
        '4. 打开 `preview.html` 检查转换后的动画和点击点，无需 Python。\n\n'
        '包含13种对应动作、17个Mac指针条目，常规32pt和大号48pt，每种含1×/2×图像。'
        '32pt在Retina上使用64像素图像，48pt使用96像素图像；图像从同一基准帧缩放以保持热点一致。\n\n'
        'Windows 的手写、候选、位置和人员选择没有直接对应条目，不导出。Mac额外的复制、别名、抓手、缩放等状态保留系统默认。'
        '具体App自绘指针可能不受主题影响。\n\n'
        'Mousecape最多接受24个等时帧：能精确展开的停留保持原节奏，其余按时间采样到24帧，总循环时长保持一致，部分短促动作可能被简化。'
        '每个状态的转换记录见 `verification.json`。\n\n'
        '**验证范围：** 已完成plist、PNG、帧顺序、尺寸、透明度、热点、时长与压缩包检查。'
        '当前制作环境为Windows，尚未在Mac导入或应用，不能承诺特定macOS版本、Intel/Apple Silicon、登录保持、多屏和Retina切换兼容性。'
        'Mac实测步骤见合集的 `macOS.md`。\n', encoding='utf-8')
    return report


def build_collection(sources, output):
    output = Path(output)
    reports = [build_theme(source, output / Path(source).name) for source in sources]
    shutil.copy2(ROOT / 'docs/macOS.md', output / 'macOS.md')
    public_repo = ROOT if (ROOT / 'LICENSE').is_file() else ROOT / '.publish/Pet-mouse-pointer'
    for name in ('LICENSE', 'ASSETS.md'):
        if (public_repo / name).is_file():
            shutil.copy2(public_repo / name, output / name)
    (output / 'catalog.json').write_text(json.dumps(dict(
        theme_count=len(reports), native_macos_tested=False, themes=reports), ensure_ascii=False, indent=2), encoding='utf-8')
    rows = '\n'.join(f'- [{r["name"]}]({r["theme"]}/README.md) · [动画预览]({r["theme"]}/preview.html)' for r in reports)
    (output / 'README.md').write_text(
        f'# 宠物鼠标 · macOS 测试版（{len(reports)}套）\n\n'
        '先阅读 [安装与恢复说明](macOS.md)，然后进入喜欢的主题文件夹。\n\n' + rows +
        '\n\n格式检查通过，Mac导入、系统应用和实际点击体验尚待实测。\n', encoding='utf-8')
    archive_path = output.parent / f'{output.name}.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path, f'{output.name}/{path.relative_to(output).as_posix()}')
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity check failed')
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive_path.name}\n', encoding='ascii')
    return archive_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('themes', nargs='*', type=Path, help='Built Windows theme folders with frames/')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/pet-mouse-pointer-macos-test')
    args = parser.parse_args()
    sources = args.themes or sorted(p.parent for p in (ROOT / 'output').glob('*/manifest.json')
                                   if (p.parent / 'frames').is_dir() and
                                   isinstance(json.loads(p.read_text(encoding='utf-8')).get('states'), list))
    print(build_collection(sources, args.output))
