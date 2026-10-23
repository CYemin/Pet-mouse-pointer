"""Write double-click Windows launchers for a compiled cursor theme."""
from pathlib import Path

LAUNCHERS=(
    ('应用鼠标主题.cmd','install-theme.ps1',48,'应用鼠标主题（48px）'),
    ('应用大号鼠标.cmd','install-theme.ps1',96,'应用大号鼠标（96px）'),
    ('恢复原鼠标.cmd','restore-theme.ps1',None,'恢复原鼠标'),
    ('应用小号鼠标32px.cmd','install-theme.ps1',32,'应用小号鼠标（32px）'),
    ('应用鼠标64px.cmd','install-theme.ps1',64,'应用鼠标（64px）'),
    ('应用特大鼠标128px.cmd','install-theme.ps1',128,'应用特大鼠标（128px）'),
)

def launcher_text(script,size,title):
    argument='' if size is None else f' -Size {size}'
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
        'if not defined PET_CURSOR_DRY_RUN pause',
        'exit /b %PET_CURSOR_EXIT%',
    ]
    return '\r\n'.join(lines)+'\r\n'

def write_launchers(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,script,size,title in LAUNCHERS:
        # CMD needs the first lines to be ASCII, then reads Chinese after chcp.
        # Do not add a UTF-8 BOM; use CRLF for Windows command processing.
        (output/name).write_bytes(launcher_text(script,size,title).encode('utf-8'))
    return [output/name for name,_,_,_ in LAUNCHERS]
