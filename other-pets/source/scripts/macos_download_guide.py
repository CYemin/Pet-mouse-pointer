"""Add the shared Chinese quick-start guide to single-theme Mousecape archives."""

from copy import copy
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

DOWNLOADS = Path(__file__).resolve().parents[1] / 'downloads' / 'macOS'
GUIDE_NAME = '安装说明.txt'


def read_guide():
    return (DOWNLOADS / GUIDE_NAME).read_text(encoding='utf-8-sig').encode('utf-8-sig')


def add_guide(archive_path, guide):
    with tempfile.TemporaryDirectory(dir=archive_path.parent) as folder:
        staged = Path(folder) / archive_path.name
        with ZipFile(archive_path) as source:
            roots = {name.split('/', 1)[0] for name in source.namelist()}
            if len(roots) != 1 or not any(name.endswith('.cape') for name in source.namelist()):
                raise ValueError(f'{archive_path}: expected a single Mousecape theme')
            guide_path = f'{roots.pop()}/{GUIDE_NAME}'
            if guide_path in source.namelist() and source.read(guide_path) == guide:
                return False
            with ZipFile(staged, 'w', ZIP_DEFLATED, compresslevel=6) as target:
                for info in source.infolist():
                    if info.filename == guide_path:
                        continue
                    with source.open(info) as src, target.open(copy(info), 'w') as dest:
                        shutil.copyfileobj(src, dest)
                target.writestr(guide_path, guide)
        with ZipFile(staged) as result:
            if result.testzip() or result.read(guide_path) != guide:
                raise ValueError(f'{archive_path}: staged ZIP failed validation')
        staged.replace(archive_path)
    return True


if __name__ == '__main__':
    guide = read_guide()
    count = sum(add_guide(path, guide) for path in sorted(DOWNLOADS.rglob('*-macOS.zip')))
    print(f'Updated {count} macOS theme archives.')
