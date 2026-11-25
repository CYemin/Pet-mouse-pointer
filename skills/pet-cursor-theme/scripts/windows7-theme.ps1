# Windows 7 / PowerShell 2.0. No modern script is parsed or helper installed.
[CmdletBinding(SupportsShouldProcess=$true)]
param([string]$Script = 'install-theme.ps1', [string]$Root,
      [ValidateSet(32,48,64,96,128)][int]$Size = 48,
      [string]$Collection = 'all', [int]$Index = 0, [string]$BackupPath,
      [switch]$OpenPointerSettings, [switch]$PreserveActiveTheme,
      [switch]$LibraryOnly)
$ErrorActionPreference = 'Stop'

function Get-Windows7Roles {
    @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand')
}
function Read-Windows7Json {
    param([string]$Path)
    # Use the .NET 3.5 JSON reader, not ConvertFrom-Json or script evaluation.
    [void][Reflection.Assembly]::LoadWithPartialName('System.Runtime.Serialization')
    [void][Reflection.Assembly]::LoadWithPartialName('System.ServiceModel.Web')
    if (-not ('System.Runtime.Serialization.Json.JsonReaderWriterFactory' -as [type])) {
        throw 'Windows .NET Framework 3.5 is disabled. Enable it in Windows Features and retry.'
    }
    $text = [IO.File]::ReadAllText($Path,[Text.Encoding]::UTF8)
    if ($text.Length -gt 16777216) { throw 'Theme JSON exceeds the size limit.' }
    $bytes = [Text.Encoding]::UTF8.GetBytes($text)
    $reader = [System.Runtime.Serialization.Json.JsonReaderWriterFactory]::CreateJsonReader($bytes,[System.Xml.XmlDictionaryReaderQuotas]::Max)
    try {
        $document = New-Object Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
        return ,(Convert-Windows7JsonNode $document.DocumentElement)
    } finally { $reader.Close() }
}
function Convert-Windows7JsonNode {
    param([Xml.XmlElement]$Node)
    switch ($Node.GetAttribute('type')) {
        'object' {
            $result = @{}
            foreach ($child in $Node.ChildNodes) {
                $name = $child.LocalName
                if ($child.NamespaceURI -eq 'item') { $name = $child.GetAttribute('item') }
                if ($result.ContainsKey($name)) { throw "Duplicate JSON property: $name" }
                $result[$name] = Convert-Windows7JsonNode $child
            }
            return ,$result
        }
        'array' {
            $result = @()
            foreach ($child in $Node.ChildNodes) { $result += ,(Convert-Windows7JsonNode $child) }
            return ,$result
        }
        'null' { return $null }
        'boolean' { return [bool]::Parse($Node.InnerText) }
        'number' { return [double]::Parse($Node.InnerText,[Globalization.CultureInfo]::InvariantCulture) }
        default { return [string]$Node.InnerText }
    }
}
function Get-Windows7CursorPlan {
    param([string]$Directory,[int]$Pixels)
    $directoryPath = [IO.Path]::GetFullPath($Directory).TrimEnd('\')
    $prefix = $directoryPath + '\'
    if ($directoryPath.Contains(',')) { throw 'Cursor scheme paths cannot contain commas.' }
    $manifest = Read-Windows7Json (Join-Path $directoryPath 'manifest.json')
    $name = [string]$manifest['name']
    if (-not $name -or -not $name.Trim()) { throw 'Theme name is missing.' }
    $roles = @(Get-Windows7Roles)
    $paths = @{}
    foreach ($role in $roles) {
        $states = @($manifest['states'] | Where-Object { $_['role'] -ceq $role })
        if ($states.Count -ne 1) { throw "Missing or duplicate cursor role: $role" }
        $relative = [string]$states[0]['variants'][[string]$Pixels]
        if (-not $relative -or [IO.Path]::IsPathRooted($relative)) { throw "Invalid cursor path: $role" }
        $path = [IO.Path]::GetFullPath((Join-Path $directoryPath $relative))
        if (-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing or unsafe cursor: $relative" }
        # Refuse junctions/symlinks that could escape the extracted theme root.
        $file = Get-Item -LiteralPath $path -Force
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point in cursor path: $relative" }
        $item = $file.Directory
        while ($item -and $item.FullName.Length -ge $directoryPath.Length) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point in cursor path: $relative" }
            $item = $item.Parent
        }
        $paths[$role] = [IO.Path]::GetFullPath((Join-Path $directoryPath $relative))
    }
    New-Object PSObject -Property @{ Name=$name; Directory=$directoryPath; Roles=$roles; Paths=$paths; Pixels=$Pixels }
}
function Initialize-Windows7Native {
    if ('PetWindows7Native' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class PetWindows7Native {
 [DllImport("user32.dll",SetLastError=true)]
 private static extern bool SystemParametersInfo(uint a,uint p,IntPtr d,uint f);
 [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 private static extern IntPtr LoadImage(IntPtr i,string p,uint t,int w,int h,uint f);
 [DllImport("user32.dll",SetLastError=true)]
 private static extern bool SetSystemCursor(IntPtr c,uint id);
 [DllImport("user32.dll")]
 private static extern bool DestroyCursor(IntPtr c);
 public static void Refresh() {
  if(!SystemParametersInfo(0x57,0,IntPtr.Zero,2)) throw new Win32Exception(Marshal.GetLastWin32Error(),"Cannot refresh cursors");
 }
 public static void Cursor(string path,uint id,int pixels,bool apply) {
  IntPtr c=LoadImage(IntPtr.Zero,path,2,pixels,pixels,0x10);
  if(c==IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(),"Cannot load cursor: "+path);
  if(!apply) { DestroyCursor(c); return; }
  if(!SetSystemCursor(c,id)) {
   int e=Marshal.GetLastWin32Error(); DestroyCursor(c);
   throw new Win32Exception(e,"Cannot apply cursor: "+id);
  }
 }
}
'@
}
function Get-Windows7Records {
    param($Key)
    foreach ($name in (@('') + @(Get-Windows7Roles) + @('Scheme Source'))) {
        $exists = $Key.GetValueNames() -contains $name
        $kind = 'String'; $value = $null
        if ($exists) {
            $kind = [string]$Key.GetValueKind($name)
            $value = $Key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        }
        New-Object PSObject -Property @{ name=$name; exists=$exists; kind=$kind; value=$value }
    }
}
function Assert-Windows7Backup {
    param($Backup)
    $names = @('') + @(Get-Windows7Roles) + @('Scheme Source')
    if ($Backup.version -ne 1 -or @($Backup.records).Count -ne $names.Count) { throw 'Invalid Windows 7 backup.' }
    foreach ($name in $names) {
        $matching = @($Backup.records | Where-Object { $_.name -ceq $name })
        if ($matching.Count -ne 1 -or $matching[0].exists -isnot [bool]) { throw 'Invalid backup records.' }
        $record = $matching[0]
        if ($record.exists -and ($null -eq $record.value -or
            -not [Enum]::IsDefined([Microsoft.Win32.RegistryValueKind],[string]$record.kind))) { throw 'Invalid backup value kind.' }
    }
}
function Write-Windows7Backup {
    param([string]$Path,$Backup)
    Assert-Windows7Backup $Backup
    $document = New-Object Xml.XmlDocument
    $root = $document.CreateElement('petWindows7Backup')
    $root.SetAttribute('version','1'); [void]$document.AppendChild($root)
    foreach ($record in $Backup.records) {
        $node = $document.CreateElement('record')
        $node.SetAttribute('name',[string]$record.name)
        $node.SetAttribute('exists',[string]$record.exists)
        $node.SetAttribute('kind',[string]$record.kind)
        if ($record.exists) {
            switch ([string]$record.kind) {
                'Binary' { $node.InnerText = [Convert]::ToBase64String([byte[]]$record.value) }
                'MultiString' {
                    foreach ($value in @($record.value)) {
                        $item = $document.CreateElement('item'); $item.InnerText = [string]$value; [void]$node.AppendChild($item)
                    }
                }
                default { $node.InnerText = [string]$record.value }
            }
        }
        [void]$root.AppendChild($node)
    }
    $document.Save($Path)
}
function Read-Windows7Backup {
    param([string]$Path)
    $file = Get-Item -LiteralPath $Path
    if ($file.Length -gt 4194304) { throw 'Backup exceeds the size limit.' }
    $settings = New-Object Xml.XmlReaderSettings
    $settings.ProhibitDtd = $true
    $settings.XmlResolver = $null
    $input = [IO.File]::OpenRead($Path)
    $reader = [Xml.XmlReader]::Create($input,$settings)
    try {
        $document = New-Object Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
        $root = $document.DocumentElement
        if ($root.Name -cne 'petWindows7Backup' -or $root.GetAttribute('version') -cne '1') { throw 'Invalid Windows 7 backup format.' }
        $records = @()
        foreach ($node in $root.ChildNodes) {
            if ($node.get_Name() -cne 'record') { throw 'Unexpected backup entry.' }
            $exists = [bool]::Parse($node.GetAttribute('exists'))
            $kind = $node.GetAttribute('kind'); $value = $null
            if ($exists) {
                switch ($kind) {
                    'Binary' { $value = [Convert]::FromBase64String($node.InnerText) }
                    'MultiString' { $value = [string[]]@($node.SelectNodes('item') | ForEach-Object { $_.InnerText }) }
                    'DWord' { $value = [int]::Parse($node.InnerText,[Globalization.CultureInfo]::InvariantCulture) }
                    'QWord' { $value = [long]::Parse($node.InnerText,[Globalization.CultureInfo]::InvariantCulture) }
                    default { $value = $node.InnerText }
                }
            }
            $records += New-Object PSObject -Property @{name=$node.GetAttribute('name');exists=$exists;kind=$kind;value=$value}
        }
        $backup = New-Object PSObject -Property @{version=1;records=$records}
        Assert-Windows7Backup $backup
        return $backup
    } finally { $reader.Close(); $input.Close() }
}
function Set-Windows7Records {
    param($Key,[object[]]$Records)
    foreach ($record in $Records) {
        if ($record.exists) {
            $kind = [Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$record.kind)
            $value = $record.value
            switch ([string]$kind) {
                'Binary' { $value = [byte[]]$value }
                'MultiString' { $value = [string[]]$value }
                'DWord' { $value = [int]$value }
                'QWord' { $value = [long]$value }
            }
            $Key.SetValue([string]$record.name,$value,$kind)
        } else { $Key.DeleteValue([string]$record.name,$false) }
    }
    $Key.Flush()
}
function Get-Windows7ThemeRoot {
    Join-Path $env:LOCALAPPDATA 'PetCursorThemes\Windows7'
}
function Test-Windows7Owned {
    param([object[]]$Records,[string]$ThemeRoot)
    $prefix = [IO.Path]::GetFullPath($ThemeRoot).TrimEnd('\') + '\'
    foreach ($role in @(Get-Windows7Roles)) {
        $matches = @($Records | Where-Object { $_.name -ceq $role })
        if ($matches.Count -ne 1 -or -not $matches[0].exists -or $matches[0].value -isnot [string]) { return $false }
        $path = [Environment]::ExpandEnvironmentVariables([string]$matches[0].value)
        if (-not $path -or -not [IO.Path]::IsPathRooted($path) -or
            -not [IO.Path]::GetFullPath($path).StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { return $false }
    }
    return $true
}
function Resolve-Windows7Backup {
    param([string]$Requested)
    if ($Requested) {
        $backup = Read-Windows7Backup $Requested
        Assert-Windows7Backup $backup
        return $Requested
    }
    $themeRoot = Get-Windows7ThemeRoot
    $latest = Join-Path $themeRoot 'latest-backup.txt'
    if (Test-Path -LiteralPath $latest -PathType Leaf) {
        $candidate = [IO.File]::ReadAllText($latest).Trim()
        try {
            $backup = Read-Windows7Backup $candidate
            Assert-Windows7Backup $backup
            return $candidate
        } catch { Write-Warning 'Latest backup is unavailable; looking for the earliest valid backup.' }
    }
    if (Test-Path -LiteralPath $themeRoot -PathType Container) {
        foreach ($dir in (Get-ChildItem -LiteralPath $themeRoot | Where-Object { $_.PSIsContainer } | Sort-Object Name)) {
            $candidate = Join-Path $dir.FullName 'restore-backup.xml'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                try { $backup = Read-Windows7Backup $candidate; Assert-Windows7Backup $backup; return $candidate } catch { }
            }
        }
    }
    throw 'No valid Windows 7 installation backup found. Use Mouse Properties to select the Windows default scheme.'
}
function Install-Windows7Cursor {
    [CmdletBinding(SupportsShouldProcess=$true)]
    param([string]$Directory,[int]$Pixels = 48)
    $plan = Get-Windows7CursorPlan $Directory $Pixels
    if (-not $PSCmdlet.ShouldProcess($plan.Name,"Install 15 Windows 7 cursor roles at $Pixels px with backup")) { return }
    Initialize-Windows7Native
    $ids = @{Arrow=32512;Help=32651;AppStarting=32650;Wait=32514;Crosshair=32515;IBeam=32513;NWPen=32631;No=32648;SizeNS=32645;SizeWE=32644;SizeNWSE=32642;SizeNESW=32643;SizeAll=32646;UpArrow=32516;Hand=32649}
    foreach ($role in $plan.Roles) { [PetWindows7Native]::Cursor($plan.Paths[$role],$ids[$role],$Pixels,$false) }
    $themeRoot = Get-Windows7ThemeRoot
    $run = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N')
    $installPath = Join-Path $themeRoot $run
    [void][IO.Directory]::CreateDirectory($installPath)
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors',$true)
    if ($null -eq $key) { throw 'Current user cursor registry key is unavailable.' }
    $schemes = $null
    try {
        $records = @(Get-Windows7Records $key)
        $backup = New-Object PSObject -Property @{ version=1; records=$records }
        $backupPath = Join-Path $installPath 'restore-backup.xml'
        Write-Windows7Backup $backupPath $backup
        $restorePath = $backupPath
        if (Test-Windows7Owned $records $themeRoot) {
            try { $restorePath = Resolve-Windows7Backup } catch { $restorePath = $backupPath }
        }
        $installed = @{}
        foreach ($role in $plan.Roles) {
            $destination = Join-Path $installPath ($role + [IO.Path]::GetExtension($plan.Paths[$role]))
            Copy-Item -LiteralPath $plan.Paths[$role] -Destination $destination -Force
            $installed[$role] = $destination
        }
        $schemes = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors\Schemes')
        if ($null -eq $schemes) { throw 'Cannot open saved cursor schemes.' }
        $schemeExists = $schemes.GetValueNames() -contains $plan.Name
        $oldScheme = $schemes.GetValue($plan.Name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $oldKind = [Microsoft.Win32.RegistryValueKind]::String
        if ($schemeExists) { $oldKind = $schemes.GetValueKind($plan.Name) }
        # Recovery remains discoverable even if refreshing live cursors fails.
        [IO.File]::WriteAllText((Join-Path $themeRoot 'latest-backup.txt'),$restorePath,[Text.Encoding]::UTF8)
        try {
            $schemePaths = @($plan.Roles | ForEach-Object { $installed[$_] })
            $schemes.SetValue($plan.Name,($schemePaths -join ','),[Microsoft.Win32.RegistryValueKind]::String)
            foreach ($role in $plan.Roles) { $key.SetValue($role,$installed[$role],[Microsoft.Win32.RegistryValueKind]::ExpandString) }
            $key.SetValue('',$plan.Name,[Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('Scheme Source',1,[Microsoft.Win32.RegistryValueKind]::DWord)
            $key.Flush(); $schemes.Flush()
            [PetWindows7Native]::Refresh()
            foreach ($role in $plan.Roles) { [PetWindows7Native]::Cursor($installed[$role],$ids[$role],$Pixels,$true) }
        } catch {
            $failure = $_
            Set-Windows7Records $key $records
            if ($schemeExists) { $schemes.SetValue($plan.Name,$oldScheme,$oldKind) }
            else { $schemes.DeleteValue($plan.Name,$false) }
            $schemes.Flush()
            [PetWindows7Native]::Refresh()
            throw $failure
        }
        Write-Output "Applied Windows 7 theme: $($plan.Name), $Pixels px, 15 roles. Backup: $restorePath"
        Write-Output 'Use the supplied size shortcuts to resize this pet. No background size-sync helper is installed on Windows 7.'
    } finally { if ($schemes) { $schemes.Close() }; $key.Close() }
}
function Restore-Windows7Cursor {
    [CmdletBinding(SupportsShouldProcess=$true)]
    param([string]$Requested)
    $path = Resolve-Windows7Backup $Requested
    $backup = Read-Windows7Backup $path
    Assert-Windows7Backup $backup
    if (-not $PSCmdlet.ShouldProcess('Current user pointers',"Restore Windows 7 backup: $path")) { return }
    Initialize-Windows7Native
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors',$true)
    if ($null -eq $key) { throw 'Current user cursor registry key is unavailable.' }
    try {
        $current = @(Get-Windows7Records $key)
        try { Set-Windows7Records $key @($backup.records); [PetWindows7Native]::Refresh() }
        catch { $failure = $_; Set-Windows7Records $key $current; [PetWindows7Native]::Refresh(); throw $failure }
    } finally { $key.Close() }
    Write-Output 'Previous Windows 7 cursor settings restored. Installed files and saved schemes were retained.'
}
function Find-Windows7CurrentTheme {
    param([string]$SearchRoot,[string]$ActiveScheme)
    if (-not $ActiveScheme) { throw 'No active named pet scheme.' }
    $candidates = @($SearchRoot)
    $candidates += @(Get-ChildItem -LiteralPath $SearchRoot | Where-Object { $_.PSIsContainer -and -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } | ForEach-Object { $_.FullName })
    $matches = @()
    foreach ($dir in $candidates) {
        $path = Join-Path $dir 'manifest.json'
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try { $manifest = Read-Windows7Json $path; if ($manifest['name'] -ceq $ActiveScheme) { $matches += $dir } } catch { }
    }
    if ($matches.Count -ne 1) { throw 'Current pet source is missing or ambiguous. Keep its theme folder beside this tool. Nothing was installed.' }
    return $matches[0]
}
function Get-Windows7CatalogPlans {
    param([string]$SearchRoot,[string]$Family,[int]$Pixels)
    $catalog = Read-Windows7Json (Join-Path $SearchRoot 'catalog.json')
    $themes = @($catalog | Where-Object { $Family -eq 'all' -or $_['family'] -ceq $Family })
    if ($themes.Count -eq 0) { throw "Unknown or empty collection: $Family" }
    $seen = @{}
    $plans = @()
    foreach ($theme in $themes) {
        $id = [string]$theme['id']
        if ($id -notmatch '^[a-z0-9-]+$' -or $seen.ContainsKey($id)) { throw 'Invalid or duplicate theme identifier.' }
        $seen[$id] = $true
        $plans += Get-Windows7CursorPlan (Join-Path $SearchRoot $id) $Pixels
    }
    # No partial output: validate every target before returning the selection.
    return $plans
}

if ($LibraryOnly) { return }
if (-not $Root) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
$plans = @()
switch ($Script) {
    'restore-theme.ps1' { Restore-Windows7Cursor $BackupPath -WhatIf:$WhatIfPreference; return }
    'install-theme.ps1' { $plans = @(Get-Windows7CursorPlan $Root $Size) }
    'resize-current.ps1' {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors')
        if ($null -eq $key) { throw 'Windows cursor settings are unavailable.' }
        try {
            $records = @(Get-Windows7Records $key)
            if (-not (Test-Windows7Owned $records (Get-Windows7ThemeRoot))) { throw 'The current pointer is not a complete installed Windows 7 pet theme. Nothing was changed.' }
            $name = [string]$key.GetValue('')
        } finally { $key.Close() }
        $directory = Find-Windows7CurrentTheme $Root $name
        $plans = @(Get-Windows7CursorPlan $directory $Size)
    }
    'install-catalog.ps1' {
        $plans = @(Get-Windows7CatalogPlans $Root $Collection $Size)
        if ($PreserveActiveTheme) {
            $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors')
            $active = ''
            if ($key) { try { $active = [string]$key.GetValue('') } finally { $key.Close() } }
            $selected = @($plans | Where-Object { $_.Name -ceq $active })
            if ($selected.Count -eq 1) { $plans = @($plans | Where-Object { $_.Name -cne $active }) + $selected }
        }
    }
    'install-collection.ps1' {
        $groups = @{
            sheltie=@('pet-pixel-complete','sheltie-tricolor-pixel','sheltie-blue-merle-pixel','sheltie-dark-sable-pixel','sheltie-bi-black-pixel','sheltie-bi-blue-pixel','sheltie-red-merle-pixel')
            golden=@('golden-standard-pixel','golden-light-pixel','golden-cream-pixel','golden-dark-pixel')
        }
        if (-not $groups.ContainsKey($Collection)) { throw 'Unknown legacy collection.' }
        $ids = @($groups[$Collection])
        if ($Index -lt 0 -or $Index -gt $ids.Count) { throw 'Theme index is out of range.' }
        if ($Index -gt 0) { $ids = @($ids[$Index - 1]) }
        foreach ($id in $ids) {
            $found = $null
            foreach ($search in @($Root,(Split-Path -Parent $Root))) {
                $dir = Join-Path $search $id
                if (Test-Path -LiteralPath (Join-Path $dir 'manifest.json') -PathType Leaf) { $found = $dir; break }
            }
            if (-not $found) { throw "Missing theme directory: $id" }
            $plans += Get-Windows7CursorPlan $found 48
        }
    }
    default { throw "Unknown pointer operation: $Script" }
}
foreach ($plan in $plans) { Install-Windows7Cursor $plan.Directory $plan.Pixels -WhatIf:$WhatIfPreference }
if ($OpenPointerSettings -and -not $WhatIfPreference) {
    try { Start-Process -FilePath (Join-Path $env:windir 'System32\rundll32.exe') -ArgumentList 'shell32.dll,Control_RunDLL main.cpl,@0,1' }
    catch { Write-Warning 'Open Mouse Properties manually with Win+R, main.cpl.' }
}
