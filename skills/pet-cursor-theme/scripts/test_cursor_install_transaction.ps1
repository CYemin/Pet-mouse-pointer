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
 public object GetValue(string n) { return values.ContainsKey(n)?values[n]:null; }
 public RegistryValueKind GetValueKind(string n) { return kinds[n]; }
 public void SetValue(string n,object v,RegistryValueKind k) {
  if(Fixture.Fail==n) { Fixture.Fail=null; throw new Exception("Injected write failure"); }
  values[n]=v; kinds[n]=k;
 }
 public void DeleteValue(string n,bool fail) { values.Remove(n); kinds.Remove(n); }
 public void Close() {}
 public void Flush() {}
}
public static class Fixture {
 public static FixtureKey Current;
 public static FixtureKey Schemes;
 public static string Fail=null;
 public static bool FailRefresh=false;
 public static bool FailApply=false;
 public static bool FailSync=false;
 public static bool SyncEnabled=false;
 public static void Apply() { if(FailApply) { FailApply=false; throw new Exception("Injected native apply failure"); } }
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
 'fixture' | Set-Content -LiteralPath (Join-Path $folder 'cursor-size-sync.cs')
 @'
function Get-CursorSizeSyncState { [pscustomobject]@{configText=$null;run=@{exists=$false;kind='String';value=$null};accessibility=@{exists=$true;kind='DWord';value=1}} }
function Compile-CursorSizeSync { param($SourcePath,$OutputPath) 'fixture' | Set-Content -LiteralPath $OutputPath }
function Stop-CursorSizeSync { [Fixture]::SyncEnabled=$false }
function Enable-CursorSizeSync { param($ExePath,$InstallPath,$SchemeName,$Paths,$Size) if([Fixture]::FailSync){throw 'Injected sync startup failure'}; [Fixture]::SyncEnabled=$true }
function Restore-CursorSizeSyncState { param($State,[switch]$Restart) [Fixture]::SyncEnabled=$false }
'@ | Set-Content -LiteralPath (Join-Path $folder 'cursor-size-sync.ps1')
 $source=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'install-theme.ps1') -Raw
 $source=$source.Replace("[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors', `$true)",'[Fixture]::Current')
 $source=$source.Replace("[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors\Schemes')",'[Fixture]::Schemes')
 $source=$source.Replace('[PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,2)','[Fixture]::Refresh()')
 $source=$source.Replace('[PetCursorRefresh]::ValidateFile($target)','$null')
 $source=$source.Replace('[PetCursorRefresh]::ApplyFile($installedFiles[$role],$cursorIds[$role],$Size)','[Fixture]::Apply()')
 if($source.Contains('[Microsoft.Win32.Registry]::CurrentUser')) { throw 'Refusing to run test with real registry access' }
 $installer=Join-Path $folder 'install.ps1'
 $source | Set-Content -LiteralPath $installer -Encoding UTF8
 foreach($mode in @('success','scheme','role','metadata','refresh','native','sync_start')) {
  [Fixture]::FailSync=$false; [Fixture]::SyncEnabled=$false
  $env:LOCALAPPDATA=Join-Path $folder $mode
  [Fixture]::Current=New-Object FixtureKey
  [Fixture]::Schemes=New-Object FixtureKey
  foreach($r in (@('')+$roles)) { [Fixture]::Current.SetValue($r,'original-'+$r,[Microsoft.Win32.RegistryValueKind]::String) }
  [Fixture]::Current.SetValue('Scheme Source',2,[Microsoft.Win32.RegistryValueKind]::DWord)
  [Fixture]::Current.SetValue('CursorBaseSize',32,[Microsoft.Win32.RegistryValueKind]::DWord)
  [Fixture]::Schemes.SetValue('Fixture 64','previous scheme',[Microsoft.Win32.RegistryValueKind]::ExpandString)
  if($mode -eq 'scheme') { [Fixture]::Fail='Fixture 64' }
  if($mode -eq 'role') { [Fixture]::Fail='Wait' }
  if($mode -eq 'metadata') { [Fixture]::Fail='CursorBaseSize' }
  if($mode -eq 'refresh') { [Fixture]::FailRefresh=$true }
  if($mode -eq 'native') { [Fixture]::FailApply=$true }
  if($mode -eq 'sync_start') { [Fixture]::FailSync=$true }
  $failed=$false
  try { & $installer -Size 64 | Out-Null } catch { $failed=$true }
  if($failed -ne ($mode -ne 'success')) { throw "Unexpected result: $mode" }
  if($failed) {
   if([Fixture]::SyncEnabled) { throw 'Sync not rolled back' }
   foreach($r in (@('')+$roles)) {
    if([Fixture]::Current.values[$r] -ne ('original-'+$r)) { throw "Cursor not rolled back: $r" }
   }
   if([Fixture]::Schemes.values['Fixture 64'] -ne 'previous scheme' -or [Fixture]::Schemes.kinds['Fixture 64'] -ne [Microsoft.Win32.RegistryValueKind]::ExpandString) { throw 'Scheme not rolled back' }
   if([Fixture]::Current.values['Scheme Source'] -ne 2 -or [Fixture]::Current.values['CursorBaseSize'] -ne 32) { throw 'Metadata not rolled back' }
  } else {
   if(-not [Fixture]::SyncEnabled) { throw 'Sync not enabled' }
   $paths=([string][Fixture]::Schemes.values['Fixture 64']).Split(',')
   if($paths.Count -ne 17) { throw 'Expected 17 scheme paths' }
   for($i=0;$i -lt 17;$i++) {
    if($paths[$i] -ne [Fixture]::Current.values[$roles[$i]] -or -not (Test-Path -LiteralPath $paths[$i])) { throw 'Saved and active cursor mismatch' }
   }
   if([Fixture]::Schemes.kinds['Fixture 64'] -ne [Microsoft.Win32.RegistryValueKind]::String) { throw 'Incorrect scheme type' }
   if([Fixture]::Current.values['Scheme Source'] -ne 1 -or [Fixture]::Current.values['CursorBaseSize'] -ne 64) { throw 'Incorrect active scheme metadata' }
   $backup=Get-Content -LiteralPath ((Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'PetCursorThemes/Sable-Handdrawn/latest-backup.txt') -Raw).Trim()) -Raw | ConvertFrom-Json
   if($backup.version -ne 2 -or @($backup.records).Count -ne 20) { throw 'Missing metadata backup' }
   if(-not $backup.PSObject.Properties['sizeSyncState']) { throw 'Missing startup/slider backup' }
  }
  Write-Output "Passed: $mode (in-memory registry and simulated refresh)"
 }
} finally {
 $env:LOCALAPPDATA=$previousLocalAppData
 $resolved=[IO.Path]::GetFullPath($folder)
 if(-not $resolved.StartsWith(([IO.Path]::GetFullPath($parent).TrimEnd('\')+'\transaction-'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe cleanup path' }
 Remove-Item -LiteralPath $resolved -Recurse -Force
}
