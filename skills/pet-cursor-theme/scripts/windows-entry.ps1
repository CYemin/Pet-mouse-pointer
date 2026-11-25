# Keep this entire file compatible with Windows PowerShell 2.0 / .NET 3.5.
param(
    [ValidateSet('install-theme.ps1','restore-theme.ps1','resize-current.ps1','install-catalog.ps1','install-collection.ps1')]
    [string]$Script,
    [ValidateSet(32,48,64,96,128)][int]$Size = 48,
    [string]$Collection = 'all', [int]$Index = 0, [string]$BackupPath,
    [switch]$OpenPointerSettings, [switch]$PreserveActiveTheme, [switch]$WhatIf
)
$ErrorActionPreference = 'Stop'
function Test-Windows7Runtime {
    param([version]$OSVersion,[int]$PowerShellMajor)
    return ($OSVersion -lt [version]'6.2' -or $PowerShellMajor -lt 3)
}
$operationResult = @{ ExitCode=0 }
try {
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root $Script
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Missing script: $Script. Extract the complete package first." }
$parameters = @{}
if ($Script -ne 'restore-theme.ps1' -and $Script -ne 'install-collection.ps1') { $parameters.Size = $Size }
if ($Script -eq 'install-catalog.ps1' -or $Script -eq 'install-collection.ps1') { $parameters.Collection = $Collection }
if ($Script -eq 'install-collection.ps1') { $parameters.Index = $Index }
if ($Script -eq 'restore-theme.ps1' -and $BackupPath) { $parameters.BackupPath = $BackupPath }
if ($Script -eq 'install-catalog.ps1' -and $PreserveActiveTheme) { $parameters.PreserveActiveTheme = $true }
if ($OpenPointerSettings -and $Script -ne 'restore-theme.ps1' -and $Script -ne 'resize-current.ps1') { $parameters.OpenPointerSettings = $true }
if ($WhatIf) { $parameters.WhatIf = $true }
if (Test-Windows7Runtime ([Environment]::OSVersion.Version) $PSVersionTable.PSVersion.Major) {
    $parameters.Script = $Script
    $parameters.Root = $root
    $target = Join-Path $root 'windows7-theme.ps1'
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'Missing Windows 7 compatibility files. Extract the complete updated package.' }
}
& $target @parameters
if (-not $?) { throw "Pointer operation failed: $Script" }
} catch {
    # This entry is intentionally NOT an advanced script: PowerShell 2.0
    # ignores explicit exit codes in advanced scripts invoked with -File.
    [Console]::Error.WriteLine($_.ToString())
    $operationResult.ExitCode = 1
}
exit $operationResult.ExitCode
