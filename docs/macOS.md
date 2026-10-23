# 宠物鼠标指针 · macOS 测试版

当前公开11套像素动画主题的 Mousecape `.cape` 导出包。制作环境为 Windows，格式和素材转换检查通过，Mac 导入、应用和实际体验尚未验收。

## 安装和使用

1. 从 [Mousecape 官方 GitHub](https://github.com/alexzielenski/Mousecape/releases) 选择适合自己 Mac 的版本，先确认程序可以正常打开。主题包没有捆绑 Mousecape，也不需要 Python。
2. 完整解压合集，进入喜欢的宠物文件夹。
3. 双击 `32pt.cape` 结尾的文件，将常规尺寸主题导入 Mousecape。导入后在列表中选中主题，使用 Apply 应用。导入不等于已应用。
4. 需要更大的宠物时，导入并应用同目录的 `48pt.cape`。每个文件均含1×、2×图像：32pt对应32/64像素，48pt对应48/96像素。
5. `preview.html` 可离线查看两种大小、深浅背景、转换后的动画、红色点击热点，并暂停播放。浏览器预览不代表系统兼容性。

先在不重要的窗口中试用点击、文本插入、窗口边缘缩放、链接和忙碌指针。确认基础应用稳定后，再考虑通过 Mousecape 自带的 helper 功能保持登录后生效。当前合集不安装 helper，不改系统设置。

## 恢复

使用 Mousecape 菜单 `Capes → Restore Defaults` 恢复默认指针，再删除导入的宠物主题；若安装了登录 helper，也请通过 Mousecape 取消。菜单名称依据官方 MainMenu.xib；不同分支或语言可能不同。为方便退出测试，先确认自己使用的版本中恢复功能的位置和行为，再应用主题。

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

13种源动作映射为17个 Mac 条目。Windows 的手写、候选、位置和人员选择不导出。Mac 的复制、别名、单向缩放、抓手、放大缩小等额外条目使用系统默认；应用自绘指针可能不受主题影响。条目名称和编号依据 [Mousecape MCDefs.m](https://github.com/alexzielenski/Mousecape/blob/master/Mousecape/mousecloak/MCDefs.m)。

## 动画与 Retina

Mousecape 的[应用代码](https://github.com/alexzielenski/Mousecape/blob/master/Mousecape/mousecloak/apply.m)将每个指针限制为1–24帧，帧时长相同。Windows ANI 可以逐帧设置不同停留时间。导出时先尝试重复帧精确保留节奏；展开后超过24帧的动作按时间均匀采样为24帧，循环总时长保持一致。短促表情可能简化，不能声称与 Windows 逐帧一致。每套 `verification.json` 记录原帧数、导出序列、时长、精确/采样标志。

每张图像为垂直堆叠的透明 PNG 帧条，内嵌于 XML plist 的 Representations。Mousecape 使用 NSBitmapImageRep 读取图像。1×、2×从同一基准帧产生，避免 Windows 不同尺寸热点独立取整造成 Retina 点击点变化。像素画以最近邻放大；手绘图像以 Lanczos 放大。2×不是额外生成的细节。

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

在仓库中安装 Python 3.10+、Pillow。先下载 Windows 全部11套合集，将其中的11个主题文件夹放入仓库 `output/` 下，保留各套 `manifest.json` 与 `frames/`，再运行：

```text
python -m unittest discover -s scripts -p test_macos_theme.py
python scripts/build_macos_theme.py
python scripts/verify_macos_theme.py
```

默认导出 `output/` 中已有 `manifest.json` 和 `frames/` 的主题；当前公开合集为11套。指定单套可运行 `python scripts/build_macos_theme.py output/golden-cream-pixel --output output/macos-cream-test`。输出包括 `.cape`、离线预览、说明、转换记录、ZIP 和 SHA-256；不会应用指针。

素材授权说明见随包 `ASSETS.md`，代码许可见 `LICENSE`。原始宠物照片不包含在 Mac 包中。
