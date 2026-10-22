"""Exercise real CMD launchers against trusted scripts in dry-run mode."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import unittest
import uuid
from cursor_launchers import LAUNCHERS,write_launchers

ROOT=Path(__file__).resolve().parents[1]

def snapshot():
    import winreg
    result={}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Control Panel\Cursors') as key:
        index=0
        while True:
            try:name,value,kind=winreg.EnumValue(key,index)
            except OSError:break
            result[name]=(value,kind);index+=1
    return result

@unittest.skipUnless(os.name=='nt','Windows CMD integration')
class CursorLauncherTests(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'.build-checks'/('双击入口 空格 '+uuid.uuid4().hex)
        self.folder.mkdir(parents=True)
        self.scripts=self.folder/'主题 & 包!';self.scripts.mkdir()
        for name in ('install-theme.ps1','restore-theme.ps1'):
            shutil.copy2(ROOT/'scripts'/name,self.scripts/name)
        # A minimal theme is enough for -WhatIf to check all role source paths.
        roles=['Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No',
               'SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person']
        states=[]
        for size in (48,96):
            (self.scripts/str(size)).mkdir()
            (self.scripts/str(size)/'fixture.ani').write_bytes(b'dry-run path fixture')
        for role in roles:states.append({'role':role,'variants':{str(n):f'{n}/fixture.ani' for n in (48,96)}})
        (self.scripts/'manifest.json').write_text(json.dumps({'states':states}),encoding='utf-8')
        self.launchers=write_launchers(self.scripts)
        self.env=os.environ.copy();self.env['LOCALAPPDATA']=str(self.folder/'appdata')
        backup_folder=self.folder/'appdata/PetCursorThemes/Sable-Handdrawn'
        backup_folder.mkdir(parents=True)
        backup=backup_folder/'fixture-backup.json'
        backup.write_text(json.dumps({'version':1,'records':[{'name':'Arrow','exists':True,'kind':'String','value':'test'}]}),encoding='utf-8')
        (backup_folder/'latest-backup.txt').write_text(str(backup),encoding='utf-8')
        self.before=snapshot()

    def tearDown(self):
        self.assertEqual(snapshot(),self.before,'Launcher dry run changed cursor registry values')
        self.assertTrue(self.folder.resolve().is_relative_to((ROOT/'.build-checks').resolve()))
        shutil.rmtree(self.folder)

    def run_launcher(self,path,check=True,input_text=None):
        # /c call handles quoted Chinese paths and --check explicitly; no
        # arbitrary arguments reach PowerShell. Launch outside its own folder.
        return subprocess.run([os.environ.get('COMSPEC','cmd.exe'),'/d','/c',
                               'call',str(path),*(['--check'] if check else [])],cwd=ROOT,env=self.env,
                              capture_output=True,encoding='utf-8',errors='replace',
                              input=input_text,
                              creationflags=subprocess.CREATE_NO_WINDOW,timeout=30)

    def test_all_three_real_cmd_paths_and_powershell_dry_runs(self):
        for path in self.launchers:
            with self.subTest(name=path.name):
                result=self.run_launcher(path)
                self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
                self.assertIn('没有修改系统鼠标设置',result.stdout)
                self.assertNotIn('成功。',result.stdout)
                data=path.read_bytes()
                self.assertFalse(data.startswith(b'\xef\xbb\xbf'))
                self.assertNotIn(b'\n',data.replace(b'\r\n',b''))
        # Install -WhatIf must return before creating an installation directory.
        children=list((self.folder/'appdata/PetCursorThemes/Sable-Handdrawn').iterdir())
        self.assertEqual({p.name for p in children},{'fixture-backup.json','latest-backup.txt'})

    def test_missing_script_reports_failure_without_success_message(self):
        (self.scripts/'install-theme.ps1').unlink()
        result=self.run_launcher(self.launchers[0])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('先完整解压',result.stdout)
        self.assertNotIn('成功。',result.stdout)

    def test_powershell_failure_is_propagated_without_false_success(self):
        (self.scripts/'manifest.json').unlink()
        result=self.run_launcher(self.launchers[0])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('操作未完成',result.stdout)
        self.assertNotIn('成功。',result.stdout)

    def test_normal_success_window_message_using_safe_stub_only(self):
        # Exercise the non-check branch without ever applying system settings.
        (self.scripts/'install-theme.ps1').write_text("Write-Output 'Safe launcher fixture'; exit 0\n",encoding='ascii')
        result=self.run_launcher(self.launchers[0],check=False,input_text='\n')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('应用鼠标主题（48px）成功。',result.stdout)
        self.assertNotIn('预演检查完成',result.stdout)

    def test_restore_without_backup_reports_failure(self):
        (self.folder/'appdata/PetCursorThemes/Sable-Handdrawn/latest-backup.txt').unlink()
        result=self.run_launcher(self.launchers[2])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('操作未完成',result.stdout)
        self.assertNotIn('成功。',result.stdout)

if __name__=='__main__':unittest.main()
