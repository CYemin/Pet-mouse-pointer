[CmdletBinding(SupportsShouldProcess)]
param([ValidateSet(32,48,64,96,128)][int]$Size = 48)
$ErrorActionPreference = 'Stop'
function Select-CursorRestoreBackupPath {
    param([object[]]$CurrentRecords,[string]$ThemeRoot,[string]$PreviousBackupPath,[string]$CurrentBackupPath)
    $roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
    try {
        $rootPrefix = [IO.Path]::GetFullPath($ThemeRoot).TrimEnd('\')+'\'
        if (@($CurrentRecords | Where-Object { $_.name -ne '' }).Count -ne $roles.Count) { return $CurrentBackupPath }
        foreach ($role in $roles) {
            $matching = @($CurrentRecords | Where-Object { $_.name -eq $role })
            if ($matching.Count -ne 1 -or -not $matching[0].exists -or $matching[0].value -isnot [string]) { return $CurrentBackupPath }
            $path = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($matching[0].value))
            if (-not $path.StartsWith($rootPrefix,[StringComparison]::OrdinalIgnoreCase)) { return $CurrentBackupPath }
        }
        # Keep the original baseline only while every cursor still belongs to us.
        # A missing/malformed older backup must not prevent creating a fresh one.
        if (-not $PreviousBackupPath -or -not (Test-Path -LiteralPath $PreviousBackupPath -PathType Leaf)) { return $CurrentBackupPath }
        $previous = Get-Content -LiteralPath $PreviousBackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $names = @('') + $roles
        $previousRecords = @($previous.records)
        if ($previous.version -ne 1 -or $previousRecords.Count -ne $names.Count) { return $CurrentBackupPath }
        foreach ($name in $names) {
            $matching = @($previousRecords | Where-Object { $_.name -is [string] -and $_.name -eq $name })
            if ($matching.Count -ne 1 -or $matching[0].exists -isnot [bool]) { return $CurrentBackupPath }
            if ($matching[0].exists -and ($null -eq $matching[0].value -or
                -not [Enum]::IsDefined([Microsoft.Win32.RegistryValueKind],[string]$matching[0].kind))) { return $CurrentBackupPath }
        }
        return $PreviousBackupPath
    } catch { return $CurrentBackupPath }
}
function Get-CursorSchemeValue {
    param([hashtable]$Paths)
    # Windows Pointers UI uses this fixed order, independent of manifest order.
    $roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
    $values = foreach ($role in $roles) {
        if (-not $Paths.ContainsKey($role) -or [string]::IsNullOrWhiteSpace($Paths[$role])) { throw "Missing cursor role: $role" }
        if ($Paths[$role].Contains(',')) { throw "Cursor scheme paths cannot contain commas: $($Paths[$role])" }
        $Paths[$role]
    }
    return ($values -join ',')
}
$manifestPath = Join-Path $PSScriptRoot 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$sourceFiles = @{}
foreach ($state in $manifest.states) {
    $relative = $state.variants.PSObject.Properties[[string]$Size].Value
    $source = Join-Path $PSScriptRoot $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing cursor: $source" }
    $sourceFiles[$state.role] = $source
}
if (-not $PSCmdlet.ShouldProcess('Current user mouse pointer theme', "Install all 17 cursors at $Size px, with a restore backup")) { return }
$themeRoot = Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Sable-Handdrawn'
$runId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$installPath = Join-Path $themeRoot $runId
New-Item -ItemType Directory -Path $installPath -Force | Out-Null
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors', $true)
if ($null -eq $key) { throw 'Current user cursor registry key is unavailable' }
$records = @()
$names = @('') + @($manifest.states.role)
foreach ($name in $names) {
    $exists = $key.GetValueNames() -contains $name
    $records += [pscustomobject]@{ name=$name; exists=$exists; kind=$(if($exists){[string]$key.GetValueKind($name)}else{'String'}); value=$(if($exists){$key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}else{$null}) }
}
$backup = [pscustomobject]@{version=1; created=(Get-Date).ToString('o'); records=$records}
$backupPath = Join-Path $installPath 'restore-backup.json'
$backup | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $backupPath -Encoding UTF8
$latestBackupPath = Join-Path $themeRoot 'latest-backup.txt'
$previousBackupPath = $null
if (Test-Path -LiteralPath $latestBackupPath -PathType Leaf) {
    try { $previousBackupPath = (Get-Content -LiteralPath $latestBackupPath -Raw -Encoding UTF8).Trim() }
    catch { $previousBackupPath = $null }
}
$restoreBackupPath = Select-CursorRestoreBackupPath -CurrentRecords $records -ThemeRoot $themeRoot `
    -PreviousBackupPath $previousBackupPath -CurrentBackupPath $backupPath
# Make recovery discoverable before any cursor value changes, including when
# copying a file or refreshing the Windows cursor cache subsequently fails.
$restoreBackupPath | Set-Content -LiteralPath $latestBackupPath -Encoding UTF8
# Prepare every file before changing any active cursor or saved scheme.
$installedFiles = @{}
foreach ($state in $manifest.states) {
    $target = Join-Path $installPath ([IO.Path]::GetFileName($sourceFiles[$state.role]))
    Copy-Item -LiteralPath $sourceFiles[$state.role] -Destination $target -Force
    $installedFiles[$state.role] = $target
}
$schemeValue = Get-CursorSchemeValue $installedFiles
$schemeName = "$($manifest.name) $Size"
$schemesKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors\Schemes')
if ($null -eq $schemesKey) { $key.Close(); throw 'Unable to open saved cursor schemes' }
$schemeExists = $schemesKey.GetValueNames() -contains $schemeName
$oldScheme = $schemesKey.GetValue($schemeName,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$oldSchemeKind = if ($schemeExists) { $schemesKey.GetValueKind($schemeName) } else { [Microsoft.Win32.RegistryValueKind]::String }
$refreshSource = @'
using System;
using System.Runtime.InteropServices;
public static class PetCursorRefresh {
 [DllImport("user32.dll",SetLastError=true)]
 public static extern bool SystemParametersInfo(uint action,uint parameter,IntPtr data,uint flags);
}
'@
if (-not ('PetCursorRefresh' -as [type])) { Add-Type -TypeDefinition $refreshSource }
try {
    $schemesKey.SetValue($schemeName,$schemeValue,[Microsoft.Win32.RegistryValueKind]::String)
    foreach ($state in $manifest.states) {
        $source = $sourceFiles[$state.role]
        $target = Join-Path $installPath ([IO.Path]::GetFileName($source))
        $key.SetValue($state.role,$target,[Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    $key.SetValue('',"$($manifest.name) $Size",[Microsoft.Win32.RegistryValueKind]::String)
    if (-not [PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,0)) { throw "Cursor refresh failed. Backup: $restoreBackupPath" }
} catch {
    if ($schemeExists) { $schemesKey.SetValue($schemeName,$oldScheme,$oldSchemeKind) }
    else { $schemesKey.DeleteValue($schemeName,$false) }
    foreach ($record in $records) {
        if ($record.exists) { $kind=[Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$record.kind); $key.SetValue($record.name,$record.value,$kind) }
        else { $key.DeleteValue($record.name,$false) }
    }
    [PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,0) | Out-Null
    throw
} finally { $key.Close(); $schemesKey.Close() }
Write-Output "Saved selectable Windows cursor scheme: $schemeName"
Write-Output "Applied $Size px theme. Restore backup: $restoreBackupPath"
