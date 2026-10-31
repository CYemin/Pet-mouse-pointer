"""Current-only selection with missing other themes; no live registry writes."""
from pathlib import Path
import json,os,shutil,subprocess,unittest,uuid
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name=='nt','Windows PowerShell integration')
class ResizeCurrentTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'.build-checks'/('current-only 空格 '+uuid.uuid4().hex);self.root.mkdir(parents=True)
        self.trace=self.root/'trace.txt'
        for slug in ['active','other']:
            d=self.root/slug;d.mkdir();(d/'manifest.json').write_text(json.dumps({'name':slug}),encoding='utf8')
            (d/'install-theme.ps1').write_text("[CmdletBinding(SupportsShouldProcess)]param($Size)\nif($PSCmdlet.ShouldProcess('fixture','resize')){Add-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'trace.txt') -Value ((Split-Path -Leaf $PSScriptRoot)+':'+$Size)}\n",encoding='ascii')
        # Replace only the registry-reading function with a fixture provider.
        script=ROOT/'scripts/resize-current.ps1';target=self.root/'resize-current.ps1'
        code="$t=$null;$e=$null;$a=[System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$t,[ref]$e);$f=$a.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-CurrentPetScheme'},$true);$s=[IO.File]::ReadAllText($args[0]);$s=$s.Remove($f.Extent.StartOffset,$f.Extent.EndOffset-$f.Extent.StartOffset).Insert($f.Extent.StartOffset,'function Get-CurrentPetScheme { return $env:PET_TEST_ACTIVE }');[IO.File]::WriteAllText($args[1],$s)"
        p=self.root/'setup.ps1';p.write_text(code,encoding='ascii')
        subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(p),str(script),str(target)],check=True,capture_output=True)
    def tearDown(self):
        assert self.root.resolve().is_relative_to((ROOT/'.build-checks').resolve());shutil.rmtree(self.root)
    def run_resize(self,name='active',*args):
        env=os.environ.copy();env['PET_TEST_ACTIVE']=name
        return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.root/'resize-current.ps1'),'-Size','32',*args],env=env,capture_output=True,timeout=30)
    def test_resizes_one_style_and_ignores_other_missing_installer(self):
        (self.root/'other/install-theme.ps1').unlink();r=self.run_resize();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.trace.read_text().splitlines(),['active:32'])
    def test_unknown_active_stops_without_installing_any_style(self):
        self.assertNotEqual(self.run_resize('unknown').returncode,0);self.assertFalse(self.trace.exists())
    def test_missing_current_source_stops_without_fallback(self):
        (self.root/'active/manifest.json').unlink();self.assertNotEqual(self.run_resize().returncode,0);self.assertFalse(self.trace.exists())
    def test_dry_run_does_not_apply(self):
        self.assertEqual(self.run_resize('active','-WhatIf').returncode,0);self.assertFalse(self.trace.exists())
if __name__=='__main__':unittest.main()
