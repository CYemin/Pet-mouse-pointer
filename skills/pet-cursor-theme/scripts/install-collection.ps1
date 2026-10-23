[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][ValidateSet('sheltie','golden')][string]$Collection,
    # 0 = install every style in the collection; N = install only style N (the switcher).
    [int]$Index = 0,
    [switch]$OpenPointerSettings
)
$ErrorActionPreference = 'Stop'

# Order here is the order shown in the switcher launcher.
$Collections = @{
    sheltie = @(
        @{ slug='pet-pixel-complete';       name='雕色喜乐蒂' },
        @{ slug='sheltie-tricolor-pixel';   name='黑白三色喜乐蒂' },
        @{ slug='sheltie-blue-merle-pixel'; name='三色陨石喜乐蒂' },
        @{ slug='sheltie-dark-sable-pixel'; name='深雕色喜乐蒂' },
        @{ slug='sheltie-bi-black-pixel';   name='黑白两色喜乐蒂' },
        @{ slug='sheltie-bi-blue-pixel';    name='蓝陨石色喜乐蒂' },
        @{ slug='sheltie-red-merle-pixel';  name='红陨石喜乐蒂' }
    )
    golden = @(
        @{ slug='golden-standard-pixel'; name='标准金毛' },
        @{ slug='golden-light-pixel';    name='浅金毛' },
        @{ slug='golden-cream-pixel';    name='奶油白金毛' },
        @{ slug='golden-dark-pixel';     name='深金毛' }
    )
}
$themes = $Collections[$Collection]
$label = if ($Collection -eq 'sheltie') { '喜乐蒂' } else { '金毛' }

# The launcher may sit in the collection root or inside a theme folder.
$searchRoots = @($PSScriptRoot)
$parent = Split-Path -Parent $PSScriptRoot
if ($parent) { $searchRoots += $parent }
function Resolve-ThemeDirectory([string]$slug) {
    foreach ($root in $searchRoots) {
        $candidate = Join-Path $root $slug
        if (Test-Path -LiteralPath (Join-Path $candidate 'install-theme.ps1')) { return $candidate }
    }
    throw "找不到主题目录 $slug，请先完整解压合集压缩包。"
}

# Verify every theme before touching the system, so a partial install cannot happen.
foreach ($theme in $themes) { [void](Resolve-ThemeDirectory $theme.slug) }

if ($Index -gt 0) {
    if ($Index -gt $themes.Count) { throw "编号超出范围：$Index（本合集共 $($themes.Count) 套）" }
    $targets = @($themes[$Index - 1])
} else {
    $targets = $themes
}

# Dry-run gate: --check reaches this point only after every theme folder was verified.
if (-not $PSCmdlet.ShouldProcess("$label（$($targets.Count) 套）", '安装并注册到鼠标方案')) { return }

if ($targets.Count -eq 1) {
    Write-Output "切换到：$($targets[0].name)"
} else {
    Write-Output "将依次安装 $($targets.Count) 套$label 主题；最后安装的一套为当前生效方案。"
}

$done = 0
foreach ($theme in $targets) {
    $directory = Resolve-ThemeDirectory $theme.slug
    Write-Output ''
    Write-Output "—— 安装 $($theme.name) ——"
    $installer = Join-Path $directory 'install-theme.ps1'
    & $installer -Size 48
    if (-not $?) { throw "$($theme.name) 安装失败，已停止。已安装的 $done 套保留不变。" }
    $done++
}

Write-Output ''
Write-Output "已完成 $done 套$label 主题。"
Write-Output '全部风格都已注册到「鼠标属性 → 指针 → 方案」，可直接在方案列表里查看缩略图。'
Write-Output '注意：在方案下拉里直接选其它风格会退回32px；要真正切换，请使用同目录的「切换风格」入口。'

if ($OpenPointerSettings) {
    try {
        Start-Process -FilePath ([IO.Path]::Combine($env:windir,'System32','rundll32.exe')) `
            -ArgumentList 'shell32.dll,Control_RunDLL main.cpl,@0,1' -ErrorAction Stop
    } catch {
        Write-Output '无法自动打开鼠标属性窗口，请按 Win+R 输入 main.cpl 手动查看方案。'
    }
}
