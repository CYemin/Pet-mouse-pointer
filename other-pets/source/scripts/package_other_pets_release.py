"""Create the system/species/color delivery and public release files."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import re
import shutil
from zipfile import ZipFile
from build_macos_theme import build_theme
from build_kylin_theme import build as build_linux

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "output/其他宠物开源指针交付"

def read_pets(folder):
    page, = folder.glob("*.html")
    return json.loads(re.search(r"const pets\s*=\s*(.+);", page.read_text(encoding="utf-8"))[1])

def export_pet(item):
    pet, source_root = item
    species, color = pet["species"], pet["color"]
    theme = source_root / pet["id"]
    windows = DELIVERY / "Windows" / species / color
    windows.mkdir(parents=True, exist_ok=True)
    with ZipFile(source_root / pet["package"]) as package:
        for entry in package.infolist():
            parts = Path(entry.filename).parts[1:]
            if not parts:
                continue
            target = windows.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.read(entry))
    manifest = json.loads((theme / "manifest.json").read_text(encoding="utf-8"))
    for state in manifest["states"]:
        state["pixel_art"] = True
    (theme / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    mac = DELIVERY / "macOS" / species / color
    build_theme(theme, mac)
    linux = DELIVERY / "Linux（麒麟-UOS）" / species / color
    linux.mkdir(parents=True, exist_ok=True)
    archive = ROOT / ".build-checks" / f"{pet['id']}-linux.zip"
    archive.parent.mkdir(exist_ok=True)
    build_linux(source_root / pet["package"], archive)
    with ZipFile(archive) as package:
        package.extractall(linux)
    for destination in (windows, mac, linux):
        shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")
    return {"id":pet["id"], "species":species, "color":color}

def main():
    DELIVERY.mkdir(parents=True, exist_ok=True)
    groups = [ROOT / "output/other-pet-prototypes", ROOT / "output/hamster-states"]
    items = [(pet, folder) for folder in groups for pet in read_pets(folder)]
    assert len(items) == 16
    with ThreadPoolExecutor(max_workers=4) as pool:
        catalog = list(pool.map(export_pet, items))
    for group, name in zip(groups, ("猫咪-玄凤-守宫", "仓鼠")):
        target = DELIVERY / "测试页面" / name
        target.mkdir(parents=True, exist_ok=True)
        page, = group.glob("*.html")
        shutil.copy2(page, target / page.name)
        for pet in read_pets(group):
            shutil.copy2(group / pet["package"], target / pet["package"])
            for size in pet["sizes"].values():
                if "cursor" in size:
                    shutil.copy2(group / size["cursor"], target / size["cursor"])
                for action in size["roles"].values():
                    dest = target / action["cursor"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(group / action["cursor"], dest)
    (DELIVERY / "款式清单.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", DELIVERY / "LICENSE")
    (DELIVERY / "使用说明.md").write_text(
        "# 其他宠物鼠标指针\n\n猫咪 5 款、玄凤鹦鹉 4 款、豹纹守宫 4 款、仓鼠 3 款，共 16 款。\n"
        "目录按系统／种类／颜色组织，先选择系统，再选择喜欢的宠物和配色。\n\n"
        "- Windows 提供 17 个动画状态，32／48／64／96／128 px。双击应用入口，恢复时使用恢复入口。\n"
        "- macOS 使用 Mousecape 导入 .cape，提供 32 pt 和 48 pt。导出 13 组对应状态，含 1×／2×图像。\n"
        "- Linux 为 Xcursor 主题，麒麟和 UOS 的安装方法见颜色目录内说明。\n"
        "- 测试页面可离线打开，仓鼠按实际尺寸 1∶1 展示。\n\n"
        "Windows 已完成原生加载与逐帧绘制检查。macOS 和 Linux 已检查文件结构，实机应用待验证。\n"
        "MIT 许可，免费使用、修改及再分发时保留许可。\n", encoding="utf-8")
    source = DELIVERY / "源码"
    source.mkdir(exist_ok=True)
    scripts = (
        "build_other_pet_preview.py", "other-pet-preview.html", "other_pet_colors.py", "other_pet_motion.py",
        "build_hamster_idle_preview.py", "build_hamster_theme.py", "hamster_actions.py", "hamster-states.html",
        "build_complete_theme.py", "build_samples.py", "operation_marks.py", "cursor_launchers.py",
        "install-theme.ps1", "restore-theme.ps1", "build_macos_theme.py", "macos_download_guide.py",
        "build_kylin_theme.py", "package_other_pets_release.py", "verify_complete_theme.py")
    for name in scripts:
        dest = source / "scripts" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts" / name, dest)
    for name in ("other-pet-prototypes", "hamster-concepts", "operation-marks-v1"):
        shutil.copytree(ROOT / "assets" / name, source / "assets" / name, dirs_exist_ok=True)
    shutil.copytree(ROOT / "output/hamster-idle", source / "output/hamster-idle", dirs_exist_ok=True)
    guide = source / "downloads/macOS/安装说明.txt"
    guide.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "downloads/macOS/安装说明.txt", guide)
    for name in ("requirements.txt", "LICENSE"):
        shutil.copy2(ROOT / name, source / name)
    (source / "README.md").write_text(
        "# 构建\n\n安装 Python 3.11+ 后依次运行。\n\n"
        "    python -m pip install -r requirements.txt\n"
        "    python scripts/build_other_pet_preview.py\n"
        "    python scripts/build_hamster_theme.py\n"
        "    python scripts/package_other_pets_release.py\n", encoding="utf-8")
    print(DELIVERY)

if __name__ == "__main__":
    main()
