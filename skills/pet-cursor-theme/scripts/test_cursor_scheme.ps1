param([string]$InstallerPath = (Join-Path $PSScriptRoot 'install-theme.ps1'))
$ErrorActionPreference = 'Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($InstallerPath,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$f=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-CursorSchemeValue'},$true)
if (-not $f) { throw 'Missing Get-CursorSchemeValue: installed theme cannot be selected again in Windows' }
. ([scriptblock]::Create($f.Extent.Text))
$roles=@('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
$paths=@{}; foreach($role in $roles) { $paths[$role]='C:\Pets\'+$role+'.ani' }
$actual=Get-CursorSchemeValue $paths
if ($actual -ne (($roles | ForEach-Object {$paths[$_]}) -join ',')) { throw 'Incorrect Windows scheme order' }
$paths.Remove('Person'); $failed=$false
try { Get-CursorSchemeValue $paths | Out-Null } catch { $failed=$true }
if (-not $failed) { throw 'Missing role was accepted' }
$paths['Person']='C:\bad,path.ani'; $failed=$false
try { Get-CursorSchemeValue $paths | Out-Null } catch { $failed=$true }
if (-not $failed) { throw 'Comma path was accepted' }
Write-Output 'Passed: scheme order, missing role, comma path; no system settings changed.'
