[CmdletBinding(SupportsShouldProcess)]
param([string]$BackupPath)
$ErrorActionPreference = 'Stop'
if (-not $BackupPath) {
    $latest = Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Sable-Handdrawn\latest-backup.txt'
    if (-not (Test-Path -LiteralPath $latest)) { throw 'No installation backup found. Supply -BackupPath explicitly.' }
    $BackupPath = (Get-Content -LiteralPath $latest -Raw -Encoding UTF8).Trim()
}
$backup = Get-Content -LiteralPath $BackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($backup.version -ne 1 -or -not $backup.records) { throw 'Invalid backup format' }
$allowed = @('','Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
foreach ($record in $backup.records) { if ($record.name -notin $allowed) { throw "Unexpected backup value: $($record.name)" } }
if (-not $PSCmdlet.ShouldProcess('Current user mouse pointer theme',"Restore cursor values from $BackupPath")) { return }
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors',$true)
if ($null -eq $key) { throw 'Current user cursor registry key is unavailable' }
try {
    foreach ($record in $backup.records) {
        if ($record.exists) {
            $kind = [Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$record.kind)
            $key.SetValue($record.name,$record.value,$kind)
        } else { $key.DeleteValue($record.name,$false) }
    }
} finally { $key.Close() }
$refreshSource = @'
using System;
using System.Runtime.InteropServices;
public static class PetCursorRestoreRefresh {
 [DllImport("user32.dll",SetLastError=true)]
 public static extern bool SystemParametersInfo(uint action,uint parameter,IntPtr data,uint flags);
}
'@
if (-not ('PetCursorRestoreRefresh' -as [type])) { Add-Type -TypeDefinition $refreshSource }
if (-not [PetCursorRestoreRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,0)) { throw 'Cursor refresh failed after restoration' }
Write-Output 'Previous cursor settings restored. Installed files and backup were retained.'
