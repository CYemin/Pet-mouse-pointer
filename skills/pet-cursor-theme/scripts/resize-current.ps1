[CmdletBinding(SupportsShouldProcess)]
param([ValidateSet(32,48,64,96,128)][int]$Size = 48)
$ErrorActionPreference = 'Stop'
function Find-CurrentThemeDirectory {
    param([string]$SearchRoot,[string]$ActiveScheme)
    if ([string]::IsNullOrWhiteSpace($ActiveScheme)) { throw 'No active named pet scheme. Select a pet scheme first.' }
    $candidates = @()
    if (Test-Path -LiteralPath (Join-Path $SearchRoot 'manifest.json') -PathType Leaf) { $candidates += $SearchRoot }
    $candidates += @(Get-ChildItem -LiteralPath $SearchRoot -Directory | Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } | ForEach-Object { $_.FullName })
    $matches = @()
    foreach ($dir in $candidates) {
        $path = Join-Path $dir 'manifest.json'
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try { $m = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { continue }
        if ($m.name -ceq $ActiveScheme) { $matches += $dir }
    }
    if ($matches.Count -ne 1) { throw 'Current theme source was not uniquely found. Keep its theme folder beside this tool. No other theme was installed.' }
    return $matches[0]
}
function Get-CurrentPetScheme {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors')
    if ($null -eq $key) { throw 'Windows cursor settings are unavailable.' }
    try {
        $root = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Sable-Handdrawn')).TrimEnd('\')+'\'
        foreach ($role in @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')) {
            $value = [Environment]::ExpandEnvironmentVariables([string]$key.GetValue($role))
            if ([string]::IsNullOrWhiteSpace($value) -or -not [IO.Path]::GetFullPath($value).StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
                throw 'Current pointer is not a complete installed pet theme. Select a pet scheme first. Nothing was changed.'
            }
        }
        return [string]$key.GetValue('')
    } finally { $key.Close() }
}
$active = Get-CurrentPetScheme
$directory = Find-CurrentThemeDirectory -SearchRoot $PSScriptRoot -ActiveScheme $active
$installer = Join-Path $directory 'install-theme.ps1'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Current theme installer is missing.' }
# The existing installer preflights all 17 paths and retains the restore baseline.
if ($WhatIfPreference) { & $installer -Size $Size -WhatIf; return }
if ($PSCmdlet.ShouldProcess($active,"Resize only the current pet to $Size px")) {
    & $installer -Size $Size
    if (-not $?) { throw 'Current theme resize failed.' }
}
