"""Write double-click Windows launchers for a compiled cursor theme."""
from pathlib import Path

LAUNCHERS=(
    ('安装鼠标主题.cmd','install-theme.ps1',32,'安装鼠标主题'),
    ('恢复原鼠标.cmd','restore-theme.ps1',None,'恢复原鼠标'),
)
LEGACY_LAUNCHERS=('应用鼠标主题.cmd','应用大号鼠标.cmd','应用小号鼠标32px.cmd',
                  '应用鼠标64px.cmd','应用特大鼠标128px.cmd')
USAGE_TEXT=r'''安装与恢复

1. 完整解压后，双击“安装鼠标主题.cmd”。
2. 自动应用默认32px，不询问尺寸；安装成功后自动打开“鼠标属性 → 指针”，可直接看到已保存的方案。
3. 双击“恢复原鼠标.cmd”恢复安装前设置。

辅助功能里的四个颜色按钮是系统内置样式，不会新增宠物卡片。
修改那些按钮或系统大小滑块可能覆盖宠物光标；本安装包不能在该页面注册主题。
再次双击安装入口可重新应用默认32px。无需管理员权限或Python。
高级用法：powershell -NoProfile -ExecutionPolicy Bypass -File .\install-theme.ps1 -Size 96
支持的尺寸为32、48、64、96、128。该命令需在主题文件夹运行。

安装会备份原设置、保存方案，并加载全部17种系统光标。失败会回滚。
恢复时保留已安装文件和方案。查看动作可打开同目录preview.html。
'''

def launcher_text(script,size,title):
    argument='' if size is None else f' -Size {size}'
    # The installer opens the Windows pointer page so the saved scheme is visible.
    if script=='install-theme.ps1': argument+=' -OpenPointerSettings'
    lines=[
        '@echo off',
        'setlocal DisableDelayedExpansion',
        'chcp 65001 >nul',
        f'title {title}',
        'set "PET_CURSOR_DRY_RUN="',
        'if /i "%~1"=="--check" set "PET_CURSOR_DRY_RUN=-WhatIf"',
        f'if not exist "%~dp0{script}" (',
        '  echo 找不到所需文件，请先完整解压主题包，再运行此入口。',
        '  if not defined PET_CURSOR_DRY_RUN pause',
        '  exit /b 1',
        ')',
        rf'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0{script}"{argument} %PET_CURSOR_DRY_RUN%',
        'set "PET_CURSOR_EXIT=%ERRORLEVEL%"',
        'echo.',
        'if "%PET_CURSOR_EXIT%"=="0" (',
        '  if defined PET_CURSOR_DRY_RUN (',
        '    echo 预演检查完成，没有修改系统鼠标设置。',
        '  ) else (',
        f'    echo {title}成功。',
        '  )',
        ') else (',
        '  echo 操作未完成。请保留上方的错误信息，以便排查。',
        ')',
        'echo.',
        'if not defined PET_CURSOR_DRY_RUN if not "%PET_CURSOR_EXIT%"=="0" pause',
        'exit /b %PET_CURSOR_EXIT%',
    ]
    return '\r\n'.join(lines)+'\r\n'

def write_launchers(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    # Only retire our known generated shortcuts; never remove arbitrary CMD files.
    for name in LEGACY_LAUNCHERS:
        (output/name).unlink(missing_ok=True)
    for name,script,size,title in LAUNCHERS:
        # CMD needs the first lines to be ASCII, then reads Chinese after chcp.
        # Do not add a UTF-8 BOM; use CRLF for Windows command processing.
        (output/name).write_bytes(launcher_text(script,size,title).encode('utf-8'))
    (output/'鼠标大小调整说明.txt').write_text(USAGE_TEXT,encoding='utf-8-sig')
    return [output/name for name,_,_,_ in LAUNCHERS]

# ---------------------------------------------------------------------------
# Collection launchers: install every style of one breed, and switch between
# them by number. Windows applies a saved scheme at 32px, so switching must
# re-install the chosen theme rather than pick it from the scheme list.
# ---------------------------------------------------------------------------
COLLECTIONS = {
    'sheltie': ('喜乐蒂', (
        ('pet-pixel-complete', '雕色喜乐蒂'),
        ('sheltie-tricolor-pixel', '黑白三色喜乐蒂'),
        ('sheltie-blue-merle-pixel', '三色陨石喜乐蒂'),
        ('sheltie-dark-sable-pixel', '深雕色喜乐蒂'),
        ('sheltie-bi-black-pixel', '黑白两色喜乐蒂'),
        ('sheltie-bi-blue-pixel', '蓝陨石色喜乐蒂'),
        ('sheltie-red-merle-pixel', '红陨石喜乐蒂'),
    )),
    'golden': ('金毛', (
        ('golden-standard-pixel', '标准金毛'),
        ('golden-light-pixel', '浅金毛'),
        ('golden-cream-pixel', '奶油白金毛'),
        ('golden-dark-pixel', '深金毛'),
    )),
}

COLLECTION_USAGE_TEXT = r"""合集入口说明

1. 「一键安装所有X.cmd」：依次安装该品种的全部风格，最后一套为当前生效。
   全部风格都会注册到「鼠标属性 → 指针 → 方案」，可在下拉列表里查看缩略图。
2. 「恢复原鼠标.cmd」：恢复到首次安装前的指针设置。

切换风格：打开「鼠标属性 → 指针 → 方案」，选另一套后点「应用」；
也可以双击那一套主题目录里的「安装鼠标主题.cmd」重新安装。

调整大小：
  1) 双击「一键安装所有X.cmd」，自动弹出的「鼠标属性」窗口先别关；
  2) 打开「设置 → 辅助功能 → 鼠标指针和触控」，拖动「大小」滑块；
  3) 回到该窗口，「方案」先选「Windows 默认」点「应用」；
  4) 再选回宠物方案点「应用」，此时按新大小生效。

无需管理员权限或Python。安装器会备份原设置，失败时回滚。
"""

_PWSH = r'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File'


def collection_install_text(collection):
    """CMD body for 'install every style of this collection'."""
    label = COLLECTIONS[collection][0]
    return '\r\n'.join([
        '@echo off',
        'setlocal DisableDelayedExpansion',
        'chcp 65001 >nul',
        f'title 一键安装所有{label}',
        'set "PET_CURSOR_DRY_RUN="',
        'if /i "%~1"=="--check" set "PET_CURSOR_DRY_RUN=-WhatIf"',
        'if not exist "%~dp0install-collection.ps1" (',
        '  echo 找不到所需文件，请先完整解压合集包，再运行此入口。',
        '  if not defined PET_CURSOR_DRY_RUN pause',
        '  exit /b 1',
        ')',
        f'{_PWSH} "%~dp0install-collection.ps1" -Collection {collection} -OpenPointerSettings %PET_CURSOR_DRY_RUN%',
        'set "PET_CURSOR_EXIT=%ERRORLEVEL%"',
        'echo.',
        'if "%PET_CURSOR_EXIT%"=="0" (',
        '  if defined PET_CURSOR_DRY_RUN (',
        '    echo 预演检查完成，没有修改系统鼠标设置。',
        '  ) else (',
        f'    echo 全部{label}风格安装成功。',
        '  )',
        ') else (',
        '  echo 操作未完成。请保留上方的错误信息，以便排查。',
        ')',
        'echo.',
        'if not defined PET_CURSOR_DRY_RUN if not "%PET_CURSOR_EXIT%"=="0" pause',
        'exit /b %PET_CURSOR_EXIT%',
    ]) + '\r\n'




def write_collection_launchers(output, collection):
    """Write the collection install entry point plus its usage note."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    label = COLLECTIONS[collection][0]
    files = {
        f'一键安装所有{label}.cmd': collection_install_text(collection),
    }
    written = []
    for name, text in files.items():
        target = output / name
        target.write_bytes(text.encode('utf-8'))
        written.append(target)
    note = output / '合集入口说明.txt'
    note.write_text(COLLECTION_USAGE_TEXT, encoding='utf-8-sig')
    written.append(note)
    return written

COLLECTION_README = """# {label}鼠标指针合集（{count} 套）

本包含 {count} 种{label}风格，每套 17 种动画状态、32/48/64/96/128px 五种尺寸，默认 32px。

## 一键安装全部

双击 `一键安装所有{label}.cmd`：依次安装全部 {count} 套，最后安装的一套为当前生效方案。
全部风格都会注册到「鼠标属性 → 指针 → 方案」，可在下拉列表里查看缩略图。

安装成功后会自动打开「鼠标属性 → 指针」，可直接看到已注册的方案。

## 切换风格

打开「鼠标属性 → 指针 → 方案」，选另一套后点「应用」即可。
也可以在那一套的主题目录里双击 `安装鼠标主题.cmd` 重新安装。

## 调整大小

| 步骤 | 操作 |
|---|---|
| 1 | 双击 `一键安装所有{label}.cmd`，**自动弹出的「鼠标属性」窗口先别关** |
| 2 | 打开「设置 → 辅助功能 → 鼠标指针和触控」，拖动「大小」滑块 |
| 3 | 回到该窗口，「方案」先选「Windows 默认」，点「应用」 |
| 4 | 再选回宠物方案，点「应用」 |

Windows 记下新大小后不会主动重画当前光标，所以需要切走再切回一次才会生效。

## 恢复

双击 `恢复原鼠标.cmd`，恢复到首次安装前的指针设置。

## 风格清单

{table}

详见 `合集入口说明.txt`。图片预览可打开各主题目录内的 `preview.html`（需保留旁边的 `frames/`）。
"""


def collection_readme(collection):
    label, themes = COLLECTIONS[collection]
    menu = '\n'.join(f'{i}. {name}' for i, (_, name) in enumerate(themes, start=1))
    table = '\n'.join(f'| {i} | {name} | `{slug}/` |'
                      for i, (slug, name) in enumerate(themes, start=1))
    return COLLECTION_README.format(label=label, count=len(themes), table=table)
