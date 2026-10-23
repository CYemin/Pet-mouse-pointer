[CmdletBinding(SupportsShouldProcess)]
param([ValidateSet(32,48,64,96,128)][int]$Size = 48, [switch]$OpenPointerSettings)
$ErrorActionPreference = 'Stop'
function Select-CursorRestoreBackupPath {
    param([object[]]$CurrentRecords,[string]$ThemeRoot,[string]$PreviousBackupPath,[string]$CurrentBackupPath)
    $roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
    try {
        $rootPrefix = [IO.Path]::GetFullPath($ThemeRoot).TrimEnd('\')+'\'
        if (@($CurrentRecords | Where-Object { $_.name -in $roles }).Count -ne $roles.Count) { return $CurrentBackupPath }
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
        if ($previous.version -eq 2) { $names += @('Scheme Source','CursorBaseSize') }
        $previousRecords = @($previous.records)
        if ($previous.version -notin @(1,2) -or $previousRecords.Count -ne $names.Count) { return $CurrentBackupPath }
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
$syncScript = Join-Path $PSScriptRoot 'cursor-size-sync.ps1'
$syncSource = Join-Path $PSScriptRoot 'cursor-size-sync.cs'
if (-not (Test-Path -LiteralPath $syncScript) -or -not (Test-Path -LiteralPath $syncSource)) { throw 'Size synchronization files are missing. Extract the complete updated theme package.' }
. $syncScript
$syncState = Get-CursorSizeSyncState
$themeRoot = Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Sable-Handdrawn'
$runId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$installPath = Join-Path $themeRoot $runId
New-Item -ItemType Directory -Path $installPath -Force | Out-Null
$syncExe = Join-Path $installPath 'cursor-size-sync.exe'
Compile-CursorSizeSync -SourcePath $syncSource -OutputPath $syncExe
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors', $true)
if ($null -eq $key) { throw 'Current user cursor registry key is unavailable' }
$records = @()
$names = @('') + @($manifest.states.role) + @('Scheme Source','CursorBaseSize')
foreach ($name in $names) {
    $exists = $key.GetValueNames() -contains $name
    $records += [pscustomobject]@{ name=$name; exists=$exists; kind=$(if($exists){[string]$key.GetValueKind($name)}else{'String'}); value=$(if($exists){$key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}else{$null}) }
}
$backup = [pscustomobject]@{version=2; created=(Get-Date).ToString('o'); records=$records; sizeSyncState=$syncState}
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
if ($restoreBackupPath -ne $backupPath) {
    $baseline = Get-Content -LiteralPath $restoreBackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $upgradeBaseline = $false
    if ($baseline.version -eq 1) {
        # Older installers never changed these two values. Preserve them while
        # upgrading the original baseline, without overwriting the old backup.
        $baseline.version = 2
        $baseline.records = @($baseline.records) + @($records | Where-Object { $_.name -in @('Scheme Source','CursorBaseSize') })
        $upgradeBaseline = $true
    }
    if (-not $baseline.PSObject.Properties['sizeSyncState']) {
        $baseline | Add-Member -NotePropertyName sizeSyncState -NotePropertyValue $syncState
        $upgradeBaseline = $true
    }
    if ($upgradeBaseline) {
        $restoreBackupPath = Join-Path $installPath 'original-baseline-v2.json'
        $baseline | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $restoreBackupPath -Encoding UTF8
    }
}
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
 [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 private static extern IntPtr LoadCursorFromFile(string path);
 [DllImport("user32.dll")]
 private static extern bool DestroyCursor(IntPtr cursor);
 [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 private static extern IntPtr LoadImage(IntPtr instance,string path,uint type,int width,int height,uint flags);
 [DllImport("user32.dll",SetLastError=true)]
 private static extern bool SetSystemCursor(IntPtr cursor,uint id);
 public static void ValidateFile(string path) {
  IntPtr cursor=LoadCursorFromFile(path);
  if(cursor==IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(),"Windows cannot load cursor: "+path);
  DestroyCursor(cursor);
 }
 public static void ApplyFile(string path,uint id,int size) {
  IntPtr cursor=LoadImage(IntPtr.Zero,path,2,size,size,0x10);
  if(cursor==IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(),"Cannot load cursor: "+path);
  if(!SetSystemCursor(cursor,id)) {
   int error=Marshal.GetLastWin32Error();
   DestroyCursor(cursor);
   throw new System.ComponentModel.Win32Exception(error,"Cannot apply system cursor: "+id);
  }
  // SetSystemCursor takes ownership and destroys this non-shared handle.
 }
}
'@
if (-not ('PetCursorRefresh' -as [type])) { Add-Type -TypeDefinition $refreshSource }
$syncMutationAttempted = $false
try {
    foreach ($target in $installedFiles.Values) { [PetCursorRefresh]::ValidateFile($target) }
    $syncMutationAttempted = $true
    Stop-CursorSizeSync
    $schemesKey.SetValue($schemeName,$schemeValue,[Microsoft.Win32.RegistryValueKind]::String)
    foreach ($state in $manifest.states) {
        $source = $sourceFiles[$state.role]
        $target = Join-Path $installPath ([IO.Path]::GetFileName($source))
        $key.SetValue($state.role,$target,[Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    $key.SetValue('',"$($manifest.name) $Size",[Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Scheme Source',1,[Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('CursorBaseSize',$Size,[Microsoft.Win32.RegistryValueKind]::DWord)
    $key.Flush()
    if (-not [PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,2)) { throw "Cursor refresh failed. Backup: $restoreBackupPath" }
    # Reload the saved scheme first, then set every live system cursor explicitly.
    # SPI_SETCURSORS alone can leave an accessibility-generated role in place.
    $cursorIds = @{Arrow=32512;Help=32651;AppStarting=32650;Wait=32514;Crosshair=32515;IBeam=32513;NWPen=32631;No=32648;SizeNS=32645;SizeWE=32644;SizeNWSE=32642;SizeNESW=32643;SizeAll=32646;UpArrow=32516;Hand=32649;Pin=32671;Person=32672}
    foreach ($role in $installedFiles.Keys) { [PetCursorRefresh]::ApplyFile($installedFiles[$role],$cursorIds[$role],$Size) }
    foreach ($role in $installedFiles.Keys) {
        if ($key.GetValue($role) -ne $installedFiles[$role]) { throw "Windows replaced cursor role: $role. Close mouse accessibility settings and retry." }
    }
    Enable-CursorSizeSync -ExePath $syncExe -InstallPath $installPath -SchemeName $schemeName -Paths $installedFiles -Size $Size
} catch {
    $installError = $_
    # A running synchronizer must stop before rollback can restore the old theme.
    if ($syncMutationAttempted) { Stop-CursorSizeSync }
    if ($schemeExists) { $schemesKey.SetValue($schemeName,$oldScheme,$oldSchemeKind) }
    else { $schemesKey.DeleteValue($schemeName,$false) }
    foreach ($record in $records) {
        if ($record.exists) { $kind=[Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$record.kind); $key.SetValue($record.name,$record.value,$kind) }
        else { $key.DeleteValue($record.name,$false) }
    }
    $key.Flush()
    [PetCursorRefresh]::SystemParametersInfo(0x57,0,[IntPtr]::Zero,2) | Out-Null
    if ($syncMutationAttempted) { Restore-CursorSizeSyncState -State $syncState -Restart }
    throw $installError
} finally { $key.Close(); $schemesKey.Close() }
Write-Output "Saved selectable Windows cursor scheme: $schemeName"
Write-Output "Applied $Size px theme. Restore backup: $restoreBackupPath"
Write-Output '安装完成，鼠标主题已生效。'
Write-Output '可在 Windows 设置的“鼠标指针与触控 → 大小”拖动滑块调整宠物指针；恢复原鼠标会停止后台尺寸同步。'
if ($OpenPointerSettings) {
    # Show the Windows pointer page so the saved scheme is visible right away.
    # A failure here must not turn a completed installation into an error.
    try {
        Start-Process -FilePath ([IO.Path]::Combine($env:windir,'System32','rundll32.exe')) `
            -ArgumentList 'shell32.dll,Control_RunDLL main.cpl,@0,1' -ErrorAction Stop
    } catch {
        Write-Output '无法自动打开鼠标属性窗口，请按 Win+R 输入 main.cpl 手动查看方案。'
    }
}
