[CmdletBinding(SupportsShouldProcess)]
param([string]$BackupPath)
$ErrorActionPreference = 'Stop'
$themeRoot = Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Sable-Handdrawn'

function Resolve-RestoreBackup {
    param([string]$Root,[string]$Requested)
    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) { throw "指定的备份文件不存在：$Requested" }
        return $Requested
    }
    $latestFile = Join-Path $Root 'latest-backup.txt'
    if (Test-Path -LiteralPath $latestFile -PathType Leaf) {
        $candidate = (Get-Content -LiteralPath $latestFile -Raw -Encoding UTF8).Trim()
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
        Write-Warning 'latest-backup.txt 指向的备份已不存在（安装目录可能被删除），改用现存最早的备份。'
    }
    # Fallback: the earliest backup records the pre-install state, so it is the
    # right baseline even when latest-backup.txt dangles.
    if (Test-Path -LiteralPath $Root -PathType Container) {
        foreach ($dir in (Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue | Sort-Object Name)) {
            foreach ($name in @('original-baseline-v2.json','restore-backup.json')) {
                $file = Join-Path $dir.FullName $name
                if (Test-Path -LiteralPath $file -PathType Leaf) {
                    Write-Warning "改用备份：$file"
                    return $file
                }
            }
        }
    }
    throw '找不到可用的安装备份，请手动在「鼠标属性 → 指针」里恢复默认指针。'
}

$BackupPath = Resolve-RestoreBackup -Root $themeRoot -Requested $BackupPath
$backup = Get-Content -LiteralPath $BackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($backup.version -notin @(1,2) -or -not $backup.records) { throw 'Invalid backup format' }
$allowed = @('','Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
if ($backup.version -eq 2) { $allowed += @('Scheme Source','CursorBaseSize') }
foreach ($record in $backup.records) { if ($record.name -notin $allowed) { throw "Unexpected backup value: $($record.name)" } }
if (-not $PSCmdlet.ShouldProcess('Current user mouse pointer theme',"Restore cursor values from $BackupPath")) { return }
$syncScript = Join-Path $PSScriptRoot 'cursor-size-sync.ps1'
if (Test-Path -LiteralPath $syncScript) { . $syncScript; Stop-CursorSizeSync }
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors',$true)
if ($null -eq $key) { throw 'Current user cursor registry key is unavailable' }
try {
    foreach ($record in $backup.records) {
        if ($record.exists) {
            $kind = [Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$record.kind)
            $key.SetValue($record.name,$record.value,$kind)
        } else { $key.DeleteValue($record.name,$false) }
    }
    $key.Flush()
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
if (-not [PetCursorRestoreRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,2)) { throw 'Cursor refresh failed after restoration' }
if ($backup.PSObject.Properties['sizeSyncState'] -and (Get-Command Restore-CursorSizeSyncState -ErrorAction SilentlyContinue)) {
    Restore-CursorSizeSyncState -State $backup.sizeSyncState -Restart
}
Write-Output 'Previous cursor settings restored. Installed files and backup were retained.'
