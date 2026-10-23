param([string]$InstallerPath = (Join-Path $PSScriptRoot 'install-theme.ps1'))
$ErrorActionPreference = 'Stop'
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($InstallerPath,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$selection = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Select-CursorRestoreBackupPath'
},$true)
if (-not $selection) { throw 'Installer is missing its independently testable backup selection function' }
# Load only this function definition. Never execute the installer or open a registry key.
. ([scriptblock]::Create($selection.Extent.Text))

$roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
function New-FixtureRecords([string]$Folder) {
    @([pscustomobject]@{name='';exists=$true;kind='String';value='Fixture scheme'}) +
    @($roles | ForEach-Object {
        [pscustomobject]@{name=$_;exists=$true;kind='ExpandString';value=(Join-Path $Folder ($_.ToLower()+'.cur'))}
    })
}
function Write-FixtureBackup([string]$Path,[object[]]$Records,[int]$Version=1) {
    [pscustomobject]@{version=$Version;records=$Records} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $Path -Encoding UTF8
}
$script:checks = 0
function Assert-Selected([string]$Name,[object[]]$Records,[string]$Prior,[string]$Expected) {
    $actual = Select-CursorRestoreBackupPath -CurrentRecords $Records -ThemeRoot $themeRoot `
        -PreviousBackupPath $Prior -CurrentBackupPath $currentBackup
    if ($actual -ne $Expected) { throw "$Name selected '$actual'; expected '$Expected'" }
    $script:checks++
}

$workspace = Split-Path $PSScriptRoot -Parent
$testParent = Join-Path $workspace '.build-checks'
New-Item -ItemType Directory -Path $testParent -Force | Out-Null
$testRoot = Join-Path $testParent ('cursor-backup-tests-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    # Exercise spaces, Unicode, exclamation marks and brackets without relying on PS1 encoding.
    $themeRoot = Join-Path $testRoot ('Theme '+[char]0x6D4B+[char]0x8BD5+' ! [pixel]')
    $currentBackup = Join-Path $testRoot 'current-run-backup.json'
    $prior = Join-Path $testRoot ('original baseline '+[char]0x6062+[char]0x590D+' ! [scheme].json')
    $external = New-FixtureRecords (Join-Path $testRoot 'External Windows scheme')
    $own48 = New-FixtureRecords (Join-Path $themeRoot 'run-48')
    $own96 = New-FixtureRecords (Join-Path $themeRoot 'run-96')
    Write-FixtureBackup $currentBackup $own48
    Write-FixtureBackup $prior $external

    Assert-Selected 'first apply' $external '' $currentBackup
    Assert-Selected 'repeated apply at 48' $own48 $prior $prior
    Assert-Selected 'repeated apply at 96' $own96 $prior $prior
    $originallyAbsent = @($external | ForEach-Object { $_ | Select-Object * })
    $originallyAbsent[17].exists = $false
    $originallyAbsent[17].value = $null
    $absentBackup = Join-Path $testRoot 'originally-absent-role.json'
    Write-FixtureBackup $absentBackup $originallyAbsent
    Assert-Selected 'valid baseline with originally absent role' $own48 $absentBackup $absentBackup
    Assert-Selected 'external theme after previous apply' $external $prior $currentBackup
    $mixed = @($own48 | ForEach-Object { $_ | Select-Object * })
    $mixed[1].value = $external[1].value
    Assert-Selected 'one external cursor role' $mixed $prior $currentBackup
    Assert-Selected 'similar directory prefix is external' (New-FixtureRecords ($themeRoot+'-other')) $prior $currentBackup
    Assert-Selected 'missing current role' $own48[0..16] $prior $currentBackup
    Assert-Selected 'missing prior file' $own48 (Join-Path $testRoot 'missing.json') $currentBackup

    $invalid = Join-Path $testRoot 'invalid.json'
    'not json' | Set-Content -LiteralPath $invalid -Encoding UTF8
    Assert-Selected 'malformed prior JSON' $own48 $invalid $currentBackup
    Write-FixtureBackup $invalid $external 3
    Assert-Selected 'unsupported prior version' $own48 $invalid $currentBackup
    Write-FixtureBackup $invalid $external[0..16]
    Assert-Selected 'incomplete prior records' $own48 $invalid $currentBackup
    $duplicate = @($external | ForEach-Object { $_ | Select-Object * })
    $duplicate[17].name = 'Arrow'
    Write-FixtureBackup $invalid $duplicate
    Assert-Selected 'duplicate prior role' $own48 $invalid $currentBackup
    $badKind = @($external | ForEach-Object { $_ | Select-Object * })
    $badKind[1].kind = 'InvalidKind'
    Write-FixtureBackup $invalid $badKind
    Assert-Selected 'invalid prior registry kind' $own48 $invalid $currentBackup
    $badFlag = @($external | ForEach-Object { $_ | Select-Object * })
    $badFlag[1].exists = 'true'
    Write-FixtureBackup $invalid $badFlag
    Assert-Selected 'invalid prior existence flag' $own48 $invalid $currentBackup

    $metadata=@([pscustomobject]@{name='Scheme Source';exists=$true;kind='DWord';value=2},
                [pscustomobject]@{name='CursorBaseSize';exists=$true;kind='DWord';value=32})
    Write-FixtureBackup $invalid ($external+$metadata) 2
    Assert-Selected 'version 2 baseline with metadata' ($own48+$metadata) $invalid $invalid
    Write-FixtureBackup $invalid ($external+$metadata[0]) 2
    Assert-Selected 'incomplete version 2 metadata' ($own48+$metadata) $invalid $currentBackup

    $pointerWrites = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.CommandAst] -and
        $node.GetCommandName() -eq 'Set-Content' -and $node.Extent.Text -match '\$latestBackupPath'
    },$true))
    $registryWrites = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] -and
        $node.Member.Value -eq 'SetValue'
    },$true))
    if ($pointerWrites.Count -ne 1 -or -not $registryWrites.Count -or
        $pointerWrites[0].Extent.StartOffset -ge ($registryWrites | ForEach-Object { $_.Extent.StartOffset } | Measure-Object -Minimum).Minimum) {
        throw 'The chosen recovery pointer must be written once, before every registry value mutation'
    }
    $script:checks++
    [pscustomobject]@{status='passed';checks=$script:checks;registry_accessed=$false;installer_executed=$false} | ConvertTo-Json
} finally {
    $resolvedTest = [IO.Path]::GetFullPath($testRoot)
    $allowedPrefix = [IO.Path]::GetFullPath($testParent).TrimEnd('\')+'\cursor-backup-tests-'
    if (-not $resolvedTest.StartsWith($allowedPrefix,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing cleanup outside the workspace backup-test directory'
    }
    Remove-Item -LiteralPath $resolvedTest -Recurse -Force
}
