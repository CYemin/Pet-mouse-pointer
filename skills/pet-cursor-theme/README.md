# Pet Cursor Theme

将自己的宠物照片制作成有表情、有动作、能安装和恢复的 Windows 鼠标指针主题。

本 Skill 随 [Pet-mouse-pointer](https://github.com/CYemin/Pet-mouse-pointer) 项目发布。现有十套完整像素动画主题：金貂、深貂、黑白、三色、蓝陨、双色蓝喜乐蒂，以及奶油白、浅金、标准金、深金毛。每套覆盖17状态并使用清楚的大号操作箭头。支持根据照片设计新角色，也支持在批准角色上扩展毛色；更多宠物的形象生成效果仍需案例验证。

## 使用

1. 将本文件夹作为 Skill 放到支持 `SKILL.md` 的客户端技能目录，保留 `scripts/`、`references/`、`assets/` 与 `requirements.txt`，按客户端方式启用。
2. 提供自己的宠物照片，描述想要的风格。生成服务由客户端提供，本仓库不包含图像模型或密钥。
3. 按 Skill 制作素材并标注热点；配置格式见 `references/configuration.md`。
4. 使用 Python 3.10+、Pillow 编译；逐帧检查全部动画和首尾衔接，再通过 Windows 原生验证后交付完整主题包。

所有脚本位于 `scripts/`。图片生成需要宿主可用的图像生成工具；Python/Pillow 只负责素材分帧、缩放和 CUR/ANI 编码。Windows API 用于验证与用户主动应用主题。

毛色扩展流程见 [coat-variants.md](references/coat-variants.md)。功能箭头模板放在 `assets/operation-marks-v1/`，用于清楚呈现缩放、移动和候选选择；与宠物分开放置，保持点击点固定。

每次制作或修改后，运行 `python scripts/verify_cursor_motion.py OUTPUT`，结合正常速度、慢放及相邻帧叠图检查严重抖动、热点漂移和突然缩放。自动检测只提供复查线索，交付前须完成[逐帧视觉检查](references/motion-review.md)并保存报告。

编译后的主题包只提供 `安装鼠标主题.cmd` 和 `恢复原鼠标.cmd`。完整解压后双击安装直接应用48px，不询问尺寸、安装成功后自动打开“鼠标属性 → 指针”，出错时保留错误信息。无需输入命令或管理员权限。本安装包不能在系统辅助功能的四个颜色按钮中注册宠物主题；高级尺寸调整使用 `install-theme.ps1 -Size 32/48/64/96/128`（任选一个尺寸）。

## 许可与隐私

代码采用 MIT。用户照片、参考图及生成素材不自动继承代码许可证；使用者须分别确认素材来源及生成服务条款。本代码包不包含开发用户的原始照片或宠物图像。

自动化验证不能替代真实桌面应用、不同 DPI、多屏和操作手感测试。请保留备份，再应用主题。
