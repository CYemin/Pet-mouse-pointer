# 宠物鼠标指针 · macOS 测试版

当前公开 11 套像素动画主题的 Mousecape `.cape` 导出包。制作环境为 Windows：格式与素材转换检查通过，**Mac 实机导入、系统应用和点击手感尚未验收**。

## 先看这里：macOS 版和 Windows 版不一样

Windows 版有 `一键安装所有喜乐蒂.cmd` 这类双击入口，双击后会立即生效并自动弹出「鼠标属性 → 指针」。**macOS 版没有这些入口，双击也不会自动应用**——两边机制不同：

| | Windows 版 | macOS 版（本包） |
|---|---|---|
| 双击之后发生什么 | 安装并立即生效，自动打开「鼠标属性」 | 只是把主题**导入**到 Mousecape 列表 |
| 什么时候真正生效 | 立刻 | 必须在 Mousecape 里手动点 **Apply** |
| 换另一套风格 | 从「鼠标属性」的方案下拉里选 | 导入另一个 `.cape`，在列表里选中后 Apply |
| 由谁执行安装 | 本项目的安装器脚本 | Mousecape 应用本身 |
| 有没有「指针方案下拉」 | 有（Windows 鼠标属性） | macOS 没有这个概念 |
| 指针大小 | 安装器直接加载原生像素 | 用 `32pt.cape` / `48pt.cape` 两个版本选择 |

**记住一句话：双击 = 导入，Apply = 生效。**

## 安装（4 步）

| 步骤 | 操作 | 你会看到 |
|---|---|---|
| 1 | 从 [Mousecape 官方 Releases](https://github.com/alexzielenski/Mousecape/releases) 下载并打开 Mousecape | Mousecape 窗口能正常打开，列表为空或只有系统主题 |
| 2 | 完整解压本压缩包（**不要**在压缩包内直接双击），进入喜欢的主题文件夹 | 看到 `32pt.cape`、`48pt.cape`、`preview.html` 等文件 |
| 3 | 双击 `32pt.cape` | Mousecape 被唤起，主题**出现在列表里**；此时指针还没变化 |
| 4 | 在 Mousecape 列表里选中该主题 → 点 **Apply** | 指针变成宠物，整个过程完成 |

`32pt.cape` 是常规尺寸（32pt 对应 32/64 像素，含 1×/2×）；`48pt.cape` 是同样主题的大号版本（48pt 对应 48/96 像素）。想换大小就导入并 Apply 另一个。

不需要 Python，也不需要管理员权限。本包不捆绑 Mousecape，也不安装登录 helper、不修改其他系统设置。

## 换成另一套风格

1. 回到解压目录，进入另一个主题文件夹
2. 双击它的 `32pt.cape` → Mousecape 列表里多了这套
3. 在列表里选中它 → 点 **Apply**

想对比多套就先全部导入，再在列表里来回切换 Apply。

## 恢复默认指针

Mousecape 菜单 → `Capes → Restore Defaults`，然后删除列表里导入的宠物主题。

菜单名称依据官方 `MainMenu.xib`，不同分支或语言可能不同。**建议先确认自己这个版本里恢复功能的位置和行为，再应用主题。**

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| 双击 `.cape` 没反应 | 文件没有关联到 Mousecape。右键 → 打开方式 → 选 Mousecape；或先在 Mousecape 里用 File → Import |
| 导入成功但指针没变 | 正常，还差最后一步：在 Mousecape 列表里选中主题点 **Apply** |
| 部分场景还是系统指针 | 某些系统条目未被主题覆盖（见下方「状态对应」）；也可能是该 App 自己绘制了光标 |
| 重启后失效 | 本包不装登录 helper。需要登录后保持效果时，用 Mousecape 自带的 helper 功能，并注意它之后要单独取消 |
| 指针变大后边缘发虚 | 用同目录的 `48pt.cape`（原生 2× 图像），而不是让系统缩放小尺寸版本 |

## 预览

`preview.html` 可离线查看两种大小、深浅背景、转换后的动画、红色点击热点，并支持暂停播放。**浏览器预览不代表系统兼容性。**

## 状态对应

| 宠物动作 | Mousecape 条目 |
|---|---|
| 正常选择 | Arrow |
| 帮助选择 | Help |
| 后台工作 | Busy |
| 忙碌等待 | Wait |
| 精确选择 | Crosshair / Crosshair 2 |
| 文本选择 | IBeam |
| 不可用 | Forbidden |
| 垂直缩放 | Resize N-S / Window N-S |
| 水平缩放 | Resize W-E / Window E-W |
| 左上右下缩放 | Window NW-SE |
| 右上左下缩放 | Window NE-SW |
| 移动 | Move |
| 链接选择 | Link / Pointing |

13 种源动作映射为 17 个 Mac 条目。Windows 的手写、候选、位置和人员选择不导出。Mac 的复制、别名、单向缩放、抓手、放大缩小等额外条目使用系统默认；应用自绘指针可能不受主题影响。条目名称和编号依据 [Mousecape MCDefs.m](https://github.com/alexzielenski/Mousecape/blob/master/Mousecape/mousecloak/MCDefs.m)。

## 动画与 Retina

Mousecape 的[应用代码](https://github.com/alexzielenski/Mousecape/blob/master/Mousecape/mousecloak/apply.m)将每个指针限制为 1–24 帧，帧时长相同；Windows ANI 可以逐帧设置不同停留时间。导出时先尝试用重复帧精确保留节奏；展开后超过 24 帧的动作按时间均匀采样为 24 帧，循环总时长保持一致。短促表情可能被简化，不能声称与 Windows 逐帧一致。每套 `verification.json` 记录原帧数、导出序列、时长、精确/采样标志。

每张图像为垂直堆叠的透明 PNG 帧条，内嵌于 XML plist 的 Representations。Mousecape 使用 NSBitmapImageRep 读取图像。1×、2× 从同一基准帧产生，避免 Windows 不同尺寸热点独立取整造成 Retina 点击点变化。像素画以最近邻放大；手绘图像以 Lanczos 放大。2× 不是额外生成的细节。

## Mac 实测验收

请在实际使用的机器完成以下检查，并记录 Mac 型号、Intel/Apple Silicon、macOS 版本及 Mousecape 版本。当前所有项均待测。

- `.cape` 可以导入，常规和大号主题分别显示，Apply 不报错。
- 点击鼻尖或功能符号时，实际命中点与可见接触点一致。
- 文本、链接、等待、帮助、十字、不可用和不同方向缩放按表切换；实际应用可能不触发所有条目。
- 循环没有黑底、倒放、突然位移或明显跳帧，睡眠和问号动作的采样效果可以接受。
- 内置 Retina 屏幕、外接屏及不同缩放比例间移动后，尺寸和点击点正常。
- 恢复默认功能可用；如果启用了 helper，检查注销和重新登录后的行为。

主题文件与 CPU 架构无关，但实际兼容性取决于 Mousecape 和 macOS；尚未确认任何具体系统或芯片组合。Mousecape 使用私有 CoreGraphics API，因此不能仅凭格式检查承诺未来系统兼容性。本包不捆绑其程序或代码；涉及再分发或商业使用时，需单独核对它的[许可](https://github.com/alexzielenski/Mousecape/blob/master/LICENSE)。

## 重新导出

在仓库中安装 Python 3.10+、Pillow。先下载 Windows 全部 11 套合集，将其中的 11 个主题文件夹放入仓库 `output/` 下，保留各套 `manifest.json` 与 `frames/`，再运行：

```text
python -m unittest discover -s scripts -p test_macos_theme.py
python scripts/build_macos_theme.py
python scripts/verify_macos_theme.py
```

默认导出 `output/` 中已有 `manifest.json` 和 `frames/` 的主题；当前公开合集为 11 套。指定单套可运行 `python scripts/build_macos_theme.py output/golden-cream-pixel --output output/macos-cream-test`。输出包括 `.cape`、离线预览、说明、转换记录、ZIP 和 SHA-256；不会应用指针。

素材授权说明见随包 `ASSETS.md`，代码许可见 `LICENSE`。原始宠物照片不包含在 Mac 包中。
