"""Check batch preflight with harmless stub installers, never system settings."""
import json, os, shutil, subprocess, unittest, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name=='nt','Windows PowerShell integration')
class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'.build-checks'/('合集 空格 '+uuid.uuid4().hex);self.root.mkdir(parents=True)
        shutil.copy2(ROOT/'scripts/install-catalog.ps1',self.root/'install-catalog.ps1')
        self.trace=self.root/'trace.txt'
        roles=['Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person']
        items=[]
        for slug,family in [('one','a'),('two','a'),('three','b')]:
            items.append(dict(id=slug,name=slug,family=family));p=self.root/slug;p.mkdir()
            (p/'cursor.ani').write_bytes(b'fixture')
            (p/'manifest.json').write_text(json.dumps(dict(states=[dict(role=r,variants={'32':'cursor.ani'}) for r in roles])),encoding='utf8')
            (p/'install-theme.ps1').write_text("param($Size)\nAdd-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'trace.txt') -Value (Split-Path -Leaf $PSScriptRoot)\n",encoding='utf8')
        (self.root/'catalog.json').write_text(json.dumps(items),encoding='utf8')
    def tearDown(self):
        assert self.root.resolve().is_relative_to((ROOT/'.build-checks').resolve());shutil.rmtree(self.root)
    def run_batch(self,*args):
        return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.root/'install-catalog.ps1'),*args],capture_output=True,timeout=30)
    def test_all_and_filtered_keep_order(self):
        result=self.run_batch();self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'));self.assertEqual(self.trace.read_text().splitlines(),['one','two','three'])
        self.trace.unlink();self.assertEqual(self.run_batch('-Collection','b').returncode,0);self.assertEqual(self.trace.read_text().splitlines(),['three'])
    def test_preflight_missing_later_asset_stops_all(self):
        (self.root/'three/cursor.ani').unlink();self.assertNotEqual(self.run_batch().returncode,0);self.assertFalse(self.trace.exists())
    def test_invalid_selection_and_whatif_never_install(self):
        self.assertNotEqual(self.run_batch('-Collection','unknown').returncode,0)
        result=self.run_batch('-WhatIf');self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'));self.assertFalse(self.trace.exists())
    def test_resize_keeps_known_active_style_last_without_guessing_unknown(self):
        # Load just the pure ordering function; never read or write the registry.
        code = "$t=$null;$e=$null;$a=[System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$t,[ref]$e);$f=$a.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-CatalogInstallOrder'},$true);. ([scriptblock]::Create($f.Extent.Text));$themes=@(@{id='one';name='one'},@{id='two';name='two'},@{id='three';name='three'});$x=@(Get-CatalogInstallOrder $themes 'two');if(($x.id -join ',') -ne 'one,three,two'){throw 'Lost current style'};$x=@(Get-CatalogInstallOrder $themes 'unknown');if(($x.id -join ',') -ne 'one,two,three'){throw 'Guessed unknown style'};$x=@(Get-CatalogInstallOrder @($themes[0]) 'one');if($x.Count -ne 1){throw 'Single-theme case failed'}"
        p=self.root/'order-test.ps1';p.write_text(code,encoding='utf8')
        r=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(p),str(self.root/'install-catalog.ps1')],capture_output=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
if __name__=='__main__':unittest.main()
