$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using Microsoft.Win32;
public class FixtureKey {
 public Dictionary<string,object> values = new Dictionary<string,object>();
 public Dictionary<string,RegistryValueKind> kinds = new Dictionary<string,RegistryValueKind>();
 public string[] GetValueNames() { var a=new string[values.Count]; values.Keys.CopyTo(a,0); return a; }
 public object GetValue(string n,object fallback,RegistryValueOptions options) { return values.ContainsKey(n)?values[n]:fallback; }
 public RegistryValueKind GetValueKind(string n) { return kinds[n]; }
 public void SetValue(string n,object v,RegistryValueKind k) {
  if(Fixture.Fail==n) { Fixture.Fail=null; throw new Exception("Injected write failure"); }
  values[n]=v; kinds[n]=k;
 }
 public void DeleteValue(string n,bool fail) { values.Remove(n); kinds.Remove(n); }
 public void Close() {}
}
public static class Fixture {
 public static FixtureKey Current;
 public static FixtureKey Schemes;
 public static string Fail=null;
 public static bool FailRefresh=false;
 public static bool Refresh() { if(FailRefresh) { FailRefresh=false; return false; } return true; }
}
'@
$roles=@('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
$parent=Join-Path (Split-Path $PSScriptRoot -Parent) '.build-checks'
$folder=Join-Path $parent ('transaction-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$previousLocalAppData=$env:LOCALAPPDATA
try {
 $states=foreach($r in $roles) {
  'fixture' | Set-Content -LiteralPath (Join-Path $folder ($r+'.ani'))
  @{role=$r;variants=@{'64'=($r+'.ani')}}
 }
 @{name='Fixture';states=@($states)} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $folder 'manifest.json')
 $source=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'install-theme.ps1') -Raw
 $source=$source.Replace("[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors', `$true)",'[Fixture]::Current')
 $source=$source.Replace("[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors\Schemes')",'[Fixture]::Schemes')
 $source=$source.Replace('[PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,0)','[Fixture]::Refresh()')
 if($source.Contains('[Microsoft.Win32.Registry]::CurrentUser')) { throw 'Refusing to run test with real registry access' }
 $installer=Join-Path $folder 'install.ps1'
 $source | Set-Content -LiteralPath $installer -Encoding UTF8
 foreach($mode in @('success','scheme','role','refresh')) {
  $env:LOCALAPPDATA=Join-Path $folder $mode
  [Fixture]::Current=New-Object FixtureKey
  [Fixture]::Schemes=New-Object FixtureKey
  foreach($r in (@('')+$roles)) { [Fixture]::Current.SetValue($r,'original-'+$r,[Microsoft.Win32.RegistryValueKind]::String) }
  [Fixture]::Schemes.SetValue('Fixture 64','previous scheme',[Microsoft.Win32.RegistryValueKind]::ExpandString)
  if($mode -eq 'scheme') { [Fixture]::Fail='Fixture 64' }
  if($mode -eq 'role') { [Fixture]::Fail='Wait' }
  if($mode -eq 'refresh') { [Fixture]::FailRefresh=$true }
  $failed=$false
  try { & $installer -Size 64 | Out-Null } catch { $failed=$true }
  if($failed -ne ($mode -ne 'success')) { throw "Unexpected result: $mode" }
  if($failed) {
   foreach($r in (@('')+$roles)) {
    if([Fixture]::Current.values[$r] -ne ('original-'+$r)) { throw "Cursor not rolled back: $r" }
   }
   if([Fixture]::Schemes.values['Fixture 64'] -ne 'previous scheme' -or [Fixture]::Schemes.kinds['Fixture 64'] -ne [Microsoft.Win32.RegistryValueKind]::ExpandString) { throw 'Scheme not rolled back' }
  } else {
   $paths=([string][Fixture]::Schemes.values['Fixture 64']).Split(',')
   if($paths.Count -ne 17) { throw 'Expected 17 scheme paths' }
   for($i=0;$i -lt 17;$i++) {
    if($paths[$i] -ne [Fixture]::Current.values[$roles[$i]] -or -not (Test-Path -LiteralPath $paths[$i])) { throw 'Saved and active cursor mismatch' }
   }
   if([Fixture]::Schemes.kinds['Fixture 64'] -ne [Microsoft.Win32.RegistryValueKind]::String) { throw 'Incorrect scheme type' }
  }
  Write-Output "Passed: $mode (in-memory registry and simulated refresh)"
 }
} finally {
 $env:LOCALAPPDATA=$previousLocalAppData
 $resolved=[IO.Path]::GetFullPath($folder)
 if(-not $resolved.StartsWith(([IO.Path]::GetFullPath($parent).TrimEnd('\')+'\transaction-'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe cleanup path' }
 Remove-Item -LiteralPath $resolved -Recurse -Force
}
