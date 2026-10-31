[CmdletBinding(SupportsShouldProcess)]
param([string]$Collection = 'all', [ValidateSet(32,48,64,96,128)][int]$Size = 32,
      [switch]$OpenPointerSettings)
$ErrorActionPreference = 'Stop'
$catalog = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$targets = @($catalog | Where-Object { $Collection -eq 'all' -or $_.family -eq $Collection })
if ($targets.Count -eq 0) { throw "Unknown or empty collection: $Collection" }
# Validate the complete selection before any installer can change settings.
$roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
foreach ($theme in $targets) {
    if ($theme.id -notmatch '^[a-z0-9-]+$') { throw 'Invalid theme identifier' }
    $dir = Join-Path $PSScriptRoot $theme.id
    if (-not (Test-Path -LiteralPath (Join-Path $dir 'install-theme.ps1') -PathType Leaf)) { throw "Missing installer: $($theme.id)" }
    $m = Get-Content -LiteralPath (Join-Path $dir 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if (@($m.states).Count -ne 17 -or @($m.states.role | Sort-Object -Unique).Count -ne 17) { throw 'Incomplete roles' }
    foreach ($r in $roles) {
        $s = @($m.states | Where-Object { $_.role -eq $r })
        if ($s.Count -ne 1) { throw "Missing role $r" }
        $relative = [string]$s[0].variants.PSObject.Properties[[string]$Size].Value
        $path = [IO.Path]::GetFullPath((Join-Path $dir $relative))
        $prefix = [IO.Path]::GetFullPath($dir).TrimEnd('\') + '\'
        if (-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing or unsafe cursor: $relative" }
    }
}
if (-not $PSCmdlet.ShouldProcess("$Collection : $($targets.Count) themes", "Install saved schemes at $Size px; last theme becomes active")) { return }
$done = 0
foreach ($theme in $targets) {
    & (Join-Path (Join-Path $PSScriptRoot $theme.id) 'install-theme.ps1') -Size $Size
    if (-not $?) { throw "Stopped after $done themes; failed: $($theme.id)" }
    $done++
}
Write-Output "Installed $done schemes. Active: $($targets[-1].name). Restore launcher returns to the original baseline."
if ($OpenPointerSettings) {
    Start-Process -FilePath (Join-Path $env:windir 'System32/rundll32.exe') -ArgumentList 'shell32.dll,Control_RunDLL main.cpl,@0,1'
}
