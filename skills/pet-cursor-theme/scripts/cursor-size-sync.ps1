# Shared installer lifecycle. Dot-sourcing this file does not change settings.
function Get-CursorSizeSyncConfigPath {
    Join-Path $env:LOCALAPPDATA 'PetCursorThemes\SizeSync\active.xml'
}
function Read-CursorSizeSyncXml {
    param([string]$Text)
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $inputText = New-Object IO.StringReader($Text)
    $reader = [Xml.XmlReader]::Create($inputText,$settings)
    try {
        $document = New-Object Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
        if ($document.DocumentElement.Name -ne 'cursorSizeSync') { throw 'Invalid pointer size sync configuration.' }
        return ,$document
    } finally { $reader.Dispose(); $inputText.Dispose() }
}
function Write-CursorSizeSyncConfig {
    param([string]$Text)
    $path = Get-CursorSizeSyncConfigPath
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
    $temporary = $path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary,$Text,(New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary,$path,[NullString]::Value,$true) }
        else { [IO.File]::Move($temporary,$path) }
    } finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }
}
function Get-CursorSizeSyncRegistryValue {
    param([string]$SubKey,[string]$Name)
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($SubKey)
    try {
        $exists = $null -ne $key -and $key.GetValueNames() -contains $Name
        [pscustomobject]@{ exists=$exists; kind=$(if($exists){[string]$key.GetValueKind($Name)}else{'String'});
            value=$(if($exists){$key.GetValue($Name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}else{$null}) }
    } finally { if ($null -ne $key) { $key.Dispose() } }
}
function Set-CursorSizeSyncRegistryValue {
    param([string]$SubKey,[string]$Name,$Record)
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($SubKey)
    try {
        if ($Record.exists) {
            $kind = [Enum]::Parse([Microsoft.Win32.RegistryValueKind],[string]$Record.kind)
            $value = $Record.value
            switch ([string]$kind) {
                'Binary' { $value = [byte[]]$value }
                'MultiString' { $value = [string[]]$value }
                'DWord' { $value = [int]$value }
                'QWord' { $value = [long]$value }
            }
            $key.SetValue($Name,$value,$kind)
        } else { $key.DeleteValue($Name,$false) }
        $key.Flush()
    } finally { $key.Dispose() }
}
function Get-CursorSizeSyncState {
    $path = Get-CursorSizeSyncConfigPath
    [pscustomobject]@{
        configText = $(if ([IO.File]::Exists($path)) { [IO.File]::ReadAllText($path) } else { $null })
        run = Get-CursorSizeSyncRegistryValue 'Software\Microsoft\Windows\CurrentVersion\Run' 'PetCursorSizeSync'
        accessibility = Get-CursorSizeSyncRegistryValue 'Software\Microsoft\Accessibility' 'CursorSize'
    }
}
function Resolve-CursorSizeSyncHelper {
    param([string]$Path)
    $root = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'PetCursorThemes')).TrimEnd('\') + '\'
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [IO.Path]::IsPathRooted($Path) -or $Path -match '["\r\n]') { throw 'Invalid pointer size helper path.' }
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($root,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($fullPath) -ne '.exe' -or -not [IO.File]::Exists($fullPath)) {
        throw 'Pointer size helper is missing or outside the installed theme directory.'
    }
    return $fullPath
}
function Compile-CursorSizeSync {
    param([string]$SourcePath,[string]$OutputPath)
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
    if (-not [IO.File]::Exists($SourcePath)) { throw 'Missing cursor-size-sync.cs; extract the complete theme archive first.' }
    if (-not [IO.File]::Exists($compiler)) { throw 'The Windows .NET Framework C# compiler is unavailable.' }
    if ([IO.File]::Exists($OutputPath)) { throw 'The size helper output must be a new installation path.' }
    $compilerOutput = & $compiler /nologo /target:winexe /r:System.Xml.Linq.dll "/out:$OutputPath" $SourcePath 2>&1
    if ($LASTEXITCODE -ne 0 -or -not [IO.File]::Exists($OutputPath)) {
        throw ('Could not compile the pointer size helper: ' + ($compilerOutput -join [Environment]::NewLine))
    }
}
function Stop-CursorSizeSync {
    $path = Get-CursorSizeSyncConfigPath
    $helper = $null
    if ([IO.File]::Exists($path)) {
        $document = Read-CursorSizeSyncXml ([IO.File]::ReadAllText($path))
        $helper = Resolve-CursorSizeSyncHelper ([string]$document.cursorSizeSync.helperPath)
        # Prevent a delayed startup from reactivating after the stop handshake.
        $document.DocumentElement.SetAttribute('enabled','false')
        Write-CursorSizeSyncConfig $document.OuterXml
    }
    Set-CursorSizeSyncRegistryValue 'Software\Microsoft\Windows\CurrentVersion\Run' 'PetCursorSizeSync' ([pscustomobject]@{exists=$false})
    if ($helper) {
        $process = Start-Process -FilePath $helper -ArgumentList @('--stop',('"' + $path + '"')) -WindowStyle Hidden -PassThru
        try {
            if (-not $process.WaitForExit(6000)) { throw 'Pointer size helper stop timed out; settings have not been restored.' }
            if ($process.ExitCode -ne 0) { throw 'Pointer size helper did not acknowledge stopping; settings have not been restored.' }
        } finally { $process.Dispose() }
    }
}
function Start-CursorSizeSyncHelper {
    param([string]$ExePath)
    $helper = Resolve-CursorSizeSyncHelper $ExePath
    $path = Get-CursorSizeSyncConfigPath
    $process = Start-Process -FilePath $helper -ArgumentList ('"' + $path + '"') -WindowStyle Hidden -PassThru
    try {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        do {
            if ([IO.File]::Exists($path + '.status.xml')) {
                try { [xml]$status = [IO.File]::ReadAllText($path + '.status.xml') } catch { $status = $null }
                if ($null -ne $status -and [string]$status.cursorSizeSyncStatus.pid -eq [string]$process.Id -and
                    [string]$status.cursorSizeSyncStatus.state -in @('ready','resized')) { return }
            }
            if ($process.HasExited) { throw 'Pointer size helper exited before becoming ready.' }
            Start-Sleep -Milliseconds 50
        } while ($timer.ElapsedMilliseconds -lt 5000)
        throw 'Pointer size helper did not become ready within 5 seconds.'
    } finally { $process.Dispose() }
}
function Enable-CursorSizeSync {
    param([string]$ExePath,[string]$InstallPath,[string]$SchemeName,[hashtable]$Paths,[int]$Size)
    $helper = Resolve-CursorSizeSyncHelper $ExePath
    $prefix = [IO.Path]::GetFullPath($InstallPath).TrimEnd('\') + '\'
    $roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
    $ids = @(32512,32651,32650,32514,32515,32513,32631,32648,32645,32644,32642,32643,32646,32516,32649,32671,32672)
    $slider = [Math]::Max(1,[Math]::Min(15,[int][Math]::Round(($Size - 32) / 16.0) + 1))
    $document = Read-CursorSizeSyncXml '<cursorSizeSync enabled="true"/>'
    foreach ($entry in @(@('schemeName',$SchemeName),@('installedDirectory',$InstallPath),@('helperPath',$helper),
        @('initialSliderSize',[string]$slider),@('initialPixelSize',[string]$Size))) {
        $node = $document.CreateElement($entry[0]); $node.InnerText = $entry[1]
        $document.DocumentElement.AppendChild($node) | Out-Null
    }
    $cursors = $document.CreateElement('cursors')
    for ($index = 0; $index -lt $roles.Count; $index++) {
        $role = $roles[$index]
        if (-not $Paths.ContainsKey($role)) { throw "Missing cursor size sync role: $role" }
        $file = [IO.Path]::GetFullPath($Paths[$role])
        if (-not $file.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)) { throw "Cursor size sync file is unavailable: $role" }
        $cursor = $document.CreateElement('cursor')
        $cursor.SetAttribute('role',$role); $cursor.SetAttribute('id',[string]$ids[$index]); $cursor.SetAttribute('file',$file.Substring($prefix.Length))
        $cursors.AppendChild($cursor) | Out-Null
    }
    $document.DocumentElement.AppendChild($cursors) | Out-Null
    Write-CursorSizeSyncConfig $document.OuterXml
    Set-CursorSizeSyncRegistryValue 'Software\Microsoft\Accessibility' 'CursorSize' ([pscustomobject]@{exists=$true;kind='DWord';value=$slider})
    $path = Get-CursorSizeSyncConfigPath
    $command = '"' + $helper + '" "' + $path + '"'
    Set-CursorSizeSyncRegistryValue 'Software\Microsoft\Windows\CurrentVersion\Run' 'PetCursorSizeSync' ([pscustomobject]@{exists=$true;kind='String';value=$command})
    Start-CursorSizeSyncHelper $helper
}
function Restore-CursorSizeSyncState {
    param($State,[switch]$Restart)
    Stop-CursorSizeSync
    $path = Get-CursorSizeSyncConfigPath
    if ($null -eq $State.configText) {
        if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) }
        if ([IO.File]::Exists($path + '.status.xml')) { [IO.File]::Delete($path + '.status.xml') }
    } else { Write-CursorSizeSyncConfig ([string]$State.configText) }
    Set-CursorSizeSyncRegistryValue 'Software\Microsoft\Windows\CurrentVersion\Run' 'PetCursorSizeSync' $State.run
    Set-CursorSizeSyncRegistryValue 'Software\Microsoft\Accessibility' 'CursorSize' $State.accessibility
    if ($Restart -and $null -ne $State.configText) {
        $document = Read-CursorSizeSyncXml ([string]$State.configText)
        if ($document.DocumentElement.GetAttribute('enabled') -eq 'true') { Start-CursorSizeSyncHelper ([string]$document.cursorSizeSync.helperPath) }
    }
}
