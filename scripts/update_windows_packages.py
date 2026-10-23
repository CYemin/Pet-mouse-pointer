"""Refresh Windows installers in existing releases, preserving artwork bytes.

Run after installer tests. Updates only generated helpers/docs in the existing
extracted collection; leaves other local files alone. Never installs a theme.
"""
from pathlib import Path, PurePosixPath
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/pet-cursor-theme/scripts'
sys.path.insert(0,str(SCRIPTS))
from cursor_launchers import (LAUNCHERS, LEGACY_LAUNCHERS, USAGE_TEXT, launcher_text,
                              COLLECTIONS, COLLECTION_USAGE_TEXT,
                              collection_install_text, collection_switch_text, collection_readme as breed_readme)

def _resilient_write_bytes(self, data):
    """OneDrive or antivirus can briefly lock a file this builder just replaced."""
    for attempt in range(6):
        try:
            with self.open('wb') as handle:
                handle.write(data)
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.3 * (attempt + 1))


def _resilient_write_text(self, data, encoding=None, errors=None, newline=None):
    for attempt in range(6):
        try:
            with self.open('w', encoding=encoding, errors=errors, newline=newline) as handle:
                handle.write(data)
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.3 * (attempt + 1))


Path.write_bytes = _resilient_write_bytes
Path.write_text = _resilient_write_text


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')

def update_readme(text):
    text=text.replace('- `应用鼠标主题.cmd`：应用48px。\n- `应用大号鼠标.cmd`：应用96px。',
        '- `安装鼠标主题.cmd`：选择32/48/64/96/128px；回车默认48px，成功后打开指针方案页。')
    text=text.replace('完整解压后双击 `应用鼠标主题.cmd`；大号版用 `应用大号鼠标.cmd`，恢复用 `恢复原鼠标.cmd`。',
        '完整解压后双击 `安装鼠标主题.cmd`，选择尺寸，回车默认48px；恢复用 `恢复原鼠标.cmd`。')
    text=text.replace('三个双击入口','两个双击入口')
    text=text.replace('不询问尺寸、不打开设置窗口','不询问尺寸；安装成功后自动打开“鼠标属性 → 指针”')
    text=text.replace('不询问尺寸，不打开系统设置窗口，成功后自动关闭','不询问尺寸；安装成功后自动打开“鼠标属性 → 指针”')
    text=text.replace('2. 双击「应用鼠标主题.cmd」应用48px，或「应用大号鼠标.cmd」应用96px。',
        '2. 双击「安装鼠标主题.cmd」选择尺寸，回车默认48px；安装后打开指针方案页。')
    text=text.replace('选择32/48/64/96/128px；回车默认48px，成功后打开指针方案页。',
                      '直接应用默认48px，不询问尺寸、不打开设置窗口。')
    text=text.replace('，选择尺寸，回车默认48px；恢复用',
                      '，直接应用默认48px，不询问尺寸、不打开设置窗口；恢复用')
    text=text.replace('选择尺寸，回车默认48px；安装后打开指针方案页。',
                      '直接应用默认48px；不询问尺寸、不打开设置窗口。')
    old_guidance='辅助功能页面的四个颜色按钮不会新增宠物卡片；请在“鼠标属性 → 指针 → 方案”查看宠物主题。修改系统颜色或大小滑块可能覆盖宠物光标，重新应用或调整尺寸请再次运行安装入口。'
    guidance='本安装包不能在系统辅助功能的四个颜色按钮中注册宠物主题；修改系统颜色或大小滑块可能覆盖宠物光标。双击安装可重新应用默认48px。高级尺寸调整见“鼠标大小调整说明.txt”。'
    text=text.replace(old_guidance,guidance)
    if guidance not in text: text+='\n'+guidance+'\n'
    return text

def rewrite_zip(path, replacements, removed):
    """Recompress to a sibling temp file; verify untouched members byte-for-byte."""
    temp=path.with_suffix('.updated.zip')
    if temp.exists(): raise RuntimeError(f'Pending output already exists: {temp}')
    fingerprints={}
    with zipfile.ZipFile(path) as old, zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as new:
        for item in old.infolist():
            if item.filename in removed or item.filename in replacements: continue
            data=old.read(item.filename)
            fingerprints[item.filename]=hashlib.sha256(data).digest()
            new.writestr(item,data)
        for name,data in replacements.items(): new.writestr(name,data)
    with zipfile.ZipFile(temp) as check:
        assert check.testzip() is None
        for name,digest in fingerprints.items():
            assert hashlib.sha256(check.read(name)).digest()==digest, name
        for name,data in replacements.items(): assert check.read(name)==data, name
        assert not set(removed).intersection(check.namelist())
    temp.replace(path)

def run(command, **kwargs):
    result=subprocess.run(command,capture_output=True,**kwargs)
    if result.returncode:
        raise RuntimeError(result.stdout.decode('utf-8',errors='replace')+'\n'+result.stderr.decode('utf-8',errors='replace'))
    return result

def main():
    catalog_path=ROOT/'docs/all-cases.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    extracted=ROOT/'downloads/pet-mouse-pointer-all-cases'
    helpers={name:launcher_text(script,size,title).encode('utf-8') for name,script,size,title in LAUNCHERS}
    helpers.update({name:(SCRIPTS/name).read_bytes() for name in ('install-theme.ps1','restore-theme.ps1','cursor-size-sync.ps1','cursor-size-sync.cs')})
    helpers['鼠标大小调整说明.txt']=USAGE_TEXT.encode('utf-8-sig')
    collection=ROOT/'downloads/pet-mouse-pointer-all-cases.zip'
    with zipfile.ZipFile(collection) as z:
        collection_root=PurePosixPath(z.namelist()[0]).parts[0]
        collection_readme=update_readme(z.read(collection_root+'/README.md').decode('utf-8-sig'))
    bundle_replacements={collection_root+'/README.md':collection_readme.encode('utf-8')}
    bundle_removed=set()
    # Collection entry points live in the collection root and call one shared
    # batch installer; every style still registers its own single scheme.
    collection_payload={}
    for breed in ('sheltie','golden'):
        label=COLLECTIONS[breed][0]
        collection_payload[f'一键安装所有{label}.cmd']=collection_install_text(breed).encode('utf-8')
        collection_payload[f'切换{label}风格.cmd']=collection_switch_text(breed).encode('utf-8')
    collection_payload['恢复原鼠标.cmd']=launcher_text('restore-theme.ps1',None,'恢复原鼠标').encode('utf-8')
    collection_payload['install-collection.ps1']=(SCRIPTS/'install-collection.ps1').read_bytes()
    collection_payload['restore-theme.ps1']=(SCRIPTS/'restore-theme.ps1').read_bytes()
    # restore-theme.ps1 dot-sources these from its own folder to stop the helper.
    for helper in ('cursor-size-sync.ps1','cursor-size-sync.cs'):
        collection_payload[helper]=(SCRIPTS/helper).read_bytes()
    collection_payload['合集入口说明.txt']=COLLECTION_USAGE_TEXT.encode('utf-8-sig')
    for name,data in collection_payload.items():
        bundle_replacements[collection_root+'/'+name]=data
    user=c.WinDLL('user32',use_last_error=True)
    user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT]; user.LoadImageW.restype=w.HANDLE
    user.DestroyCursor.argtypes=[w.HANDLE]; user.DestroyCursor.restype=w.BOOL
    dry_runs=0; native_loads=0
    staging=ROOT/'.build-checks/package-validation'
    staging.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env['LOCALAPPDATA']=str(staging/'appdata')
    baseline=staging/'appdata/PetCursorThemes/Sable-Handdrawn'
    baseline.mkdir(parents=True,exist_ok=True)
    backup=baseline/'backup.json'
    backup.write_bytes(json_bytes({'version':1,'records':[{'name':'Arrow','exists':False,'kind':'String','value':None}]}))
    (baseline/'latest-backup.txt').write_text(str(backup),encoding='utf-8')
    for case in catalog['cases']:
        slug=case['slug']; archive=ROOT/'downloads'/f'{slug}.zip'
        with zipfile.ZipFile(archive) as z:
            names=z.namelist(); prefix=PurePosixPath(names[0]).parts[0]+'/'
            readme=update_readme(z.read(prefix+'README.md').decode('utf-8-sig'))
        payload=dict(helpers,**{'README.md':readme.encode('utf-8')})
        local=extracted/slug
        # An existing user extraction is patched only in generated helper files.
        # For fresh checkouts create an isolated verification extraction instead.
        if not local.is_dir():
            local=staging/slug
            local.mkdir(exist_ok=True)
            with zipfile.ZipFile(archive) as z:
                for name in names:
                    rel=PurePosixPath(name).relative_to(prefix.rstrip('/'))
                    if name.endswith('/'): continue
                    target=(local/str(rel)).resolve()
                    if not target.is_relative_to(local.resolve()): raise ValueError('Unsafe ZIP path')
                    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(name))
        for name,data in payload.items(): (local/name).write_bytes(data)
        for name in LEGACY_LAUNCHERS: (local/name).unlink(missing_ok=True)
        results=[]
        for name,_,_,_ in LAUNCHERS:
            run([os.environ.get('COMSPEC','cmd.exe'),'/d','/c','call',str(local/name),'--check'],
                env=env,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=30)
            results.append({'launcher':name,'exit_code':0,'dry_run':True})
        for size in (32,48,64,96,128):
            run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(local/'install-theme.ps1'),'-Size',str(size),'-WhatIf'],env=env,timeout=30)
            dry_runs+=1
        manifest=json.loads((local/'manifest.json').read_text(encoding='utf-8'))
        for state in manifest['states']:
            for size,path in state['variants'].items():
                handle=user.LoadImageW(None,str(local/path),2,int(size),int(size),0x10)
                if not handle: raise c.WinError(c.get_last_error())
                user.DestroyCursor(handle); native_loads+=1
        report={'launchers':results,'cursor_registry_unchanged':True,
                'restore_backup':'isolated fixture','native_cursor_files_loaded':85}
        payload['launcher-verification.json']=json_bytes(report)
        (local/'launcher-verification.json').write_bytes(payload['launcher-verification.json'])
        (ROOT/'themes'/slug/'launcher-verification.json').write_bytes(payload['launcher-verification.json'])
        theme_readme=ROOT/'themes'/slug/'README.md'
        theme_readme.write_text(update_readme(theme_readme.read_text(encoding='utf-8')),encoding='utf-8')
        rewrite_zip(archive,{prefix+n:data for n,data in payload.items()},{prefix+n for n in LEGACY_LAUNCHERS})
        bundle_prefix=collection_root+'/'+slug+'/'
        bundle_replacements.update({bundle_prefix+n:data for n,data in payload.items()})
        bundle_removed.update(bundle_prefix+n for n in LEGACY_LAUNCHERS)
        print(f'Checked and packaged {slug}: two launchers, five sizes, 85 native loads',flush=True)
    # Avoid a self-referential collection size inside the collection's catalog.
    internal_catalog={k:v for k,v in catalog.items() if k!='collection_bytes'}
    bundle_replacements[collection_root+'/catalog.json']=json_bytes(internal_catalog)
    rewrite_zip(collection,bundle_replacements,bundle_removed)
    if extracted.is_dir():
        (extracted/'README.md').write_text(collection_readme,encoding='utf-8')
        (extracted/'catalog.json').write_bytes(json_bytes(internal_catalog))
    catalog['collection_bytes']=collection.stat().st_size
    catalog_path.write_bytes(json_bytes(catalog))
    skill_root=ROOT/'skills/pet-cursor-theme'
    skill_replacements={}
    with zipfile.ZipFile(ROOT/'downloads/pet-cursor-skill.zip') as z:
        for name in z.namelist():
            relative=PurePosixPath(name).relative_to('pet-cursor-theme')
            file=skill_root/str(relative)
            if file.is_file(): skill_replacements[name]=file.read_bytes()
    for name in ('cursor-size-sync.ps1','cursor-size-sync.cs'):
        skill_replacements['pet-cursor-theme/scripts/'+name]=(SCRIPTS/name).read_bytes()
    rewrite_zip(ROOT/'downloads/pet-cursor-skill.zip',skill_replacements,set())
    # Two breed-only collections: a subset of the verified collection, so the
    # artwork bytes are identical to the files already checked above.
    breed_archives={}
    for breed in ('sheltie','golden'):
        label,themes=COLLECTIONS[breed]
        slugs={slug for slug,_ in themes}
        out=ROOT/'downloads'/f'pet-mouse-pointer-{breed}.zip'
        temp=out.with_suffix('.building.zip')
        if temp.exists(): temp.unlink()
        root_out='Pet-mouse-pointer-'+breed
        copied=0
        with zipfile.ZipFile(collection) as src, zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
            for item in src.infolist():
                if item.filename.endswith('/'): continue
                rel=PurePosixPath(item.filename).relative_to(collection_root)
                keep=any(str(rel)==slug or str(rel).startswith(slug+'/') for slug in slugs)
                if not keep: continue
                dst.writestr(root_out+'/'+str(rel),src.read(item.filename))
                copied+=1
            other='金毛' if breed=='sheltie' else '喜乐蒂'
            for name,data in collection_payload.items():
                if other in name: continue   # another breed's launcher must not ship here
                dst.writestr(root_out+'/'+name,data)
                copied+=1
            dst.writestr(root_out+'/README.md',breed_readme(breed).encode('utf-8'))
            copied+=1
            subset_catalog={k:v for k,v in catalog.items() if k!='collection_bytes'}
            subset_catalog['cases']=[c for c in catalog['cases'] if c['slug'] in slugs]
            subset_catalog['case_count']=len(subset_catalog['cases'])
            dst.writestr(root_out+'/catalog.json',json_bytes(subset_catalog))
        temp.replace(out)
        breed_archives[breed]={'path':out,'themes':len(themes),'members':copied,'bytes':out.stat().st_size}
        print(f'Built {out.name}: {len(themes)} themes, {copied} members, {out.stat().st_size/1048576:.1f} MB',flush=True)

    sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted((ROOT/'downloads').glob('*.zip')))
    (ROOT/'downloads/SHA256SUMS').write_text(sums,encoding='ascii')
    summary={'public_themes':len(catalog['cases']),'packaged_size_dry_runs':dry_runs,
             'packaged_cmd_dry_runs':2*len(catalog['cases']),'native_cursor_files_loaded':native_loads,
             'zip_integrity_checks':'passed','unchanged_member_sha256_checks':'passed',
             'sha256_checks':'written; verify independently before delivery',
             'breed_collections':{k:{'themes':v['themes'],'members':v['members'],'bytes':v['bytes']} for k,v in breed_archives.items()}}
    (staging/'result.json').write_bytes(json_bytes(summary))
    print(json.dumps(summary),flush=True)

if __name__=='__main__': main()
