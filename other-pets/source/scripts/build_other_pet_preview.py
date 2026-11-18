"""Build the pet cursor color catalog and its shared playground."""

from base64 import b64encode
from io import BytesIO
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from build_complete_theme import ORDER, SIZES, pixel_convert
from build_samples import ani_file, cur_file
from cursor_launchers import write_launchers
from other_pet_colors import recolor
from other_pet_motion import animations


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "other-pet-prototypes"
OUT = ROOT / "output" / "other-pet-prototypes"
DISTRIBUTION = ROOT / "downloads" / "other-pets" / "other-pets-playground.zip"


def png_uri(pixels):
    buffer = BytesIO()
    pixels.save(buffer, "PNG")
    return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")


def scaled_hotspot(source, images, native, size):
    x, y = ((value + .5) * size / 48 - .5 for value in native)
    color = source.getpixel(native)
    frame = images[0]
    candidates = [
        (i, j) for i in range(max(0, round(x) - 2), min(size, round(x) + 3))
        for j in range(max(0, round(y) - 2), min(size, round(y) + 3))
        if frame.getpixel((i, j))[3] == 255 and all(
            other.getpixel((i, j)) == frame.getpixel((i, j)) for other in images
        )
    ]
    if not candidates:
        raise ValueError(f"No fixed visible pixel near {native} at {size}px")
    # Match the center first, then prefer the authored mark color on a tie.
    return min(candidates, key=lambda p: ((p[0]-x)**2 + (p[1]-y)**2, frame.getpixel(p) != color))


def write_theme_package(folder, manifest):
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name in ("install-theme.ps1", "restore-theme.ps1"):
        shutil.copyfile(Path(__file__).with_name(name), folder / name)
    launchers = write_launchers(folder)
    readme = folder / "使用说明.txt"
    readme.write_text(
        f"{manifest['name']} · Windows 动画指针\n\n"
        "完整解压后，双击「应用鼠标主题.cmd」应用 48 px 方案。\n"
        "也可使用同目录中带尺寸的入口。共 17 个 Windows 指针状态。\n"
        "双击「恢复原鼠标.cmd」恢复应用前的指针。\n",
        encoding="utf-8-sig",
    )
    files = [folder / name for name in ("install-theme.ps1", "restore-theme.ps1", "manifest.json")]
    license_path = folder / "operation-marks-LICENSE.txt"
    shutil.copyfile(ROOT / "assets" / "operation-marks-v1" / "LICENSE", license_path)
    files.extend([readme, license_path, *launchers])
    files.extend(folder / state["file"] for state in manifest["states"])
    files.extend(folder / path for state in manifest["states"] for path in state["variants"].values())
    with ZipFile(OUT / f"{folder.name}-windows.zip", "w", compression=ZIP_DEFLATED) as package:
        for path in files:
            package.write(path, Path(folder.name) / path.relative_to(folder))


def load_master(species_id):
    source = Image.open(ASSETS / f"{species_id}.png").convert("RGBA")
    alpha = source.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    source.putalpha(alpha)
    left, top, right, bottom = alpha.getbbox()
    side = round(max(right - left, bottom - top) / 0.88)
    x = (left + right - side) // 2
    y = (top + bottom - side) // 2
    native = source.crop((x, y, x + side, y + side)).resize((48, 48), Image.Resampling.NEAREST)
    return pixel_convert([native], {"pixel_alpha_threshold": 128, "pixel_palette_colors": 18})[0]


def build_pet(pet, master, variant, motion=None):
    native = recolor(master, variant)
    motion = list(animations(pet["speciesId"], native, master)) if motion is None else motion
    folder = OUT / pet["id"]
    (folder / "frames").mkdir(parents=True, exist_ok=True)
    sizes = {size: {"roles": {}} for size in SIZES}
    for size in SIZES:
        pixels = native.resize((size, size), Image.Resampling.NEAREST)
        saved = pet["hotspots"].get(str(size))
        hotspot = tuple(saved) if saved else scaled_hotspot(native, [pixels], tuple(pet["hotspots"]["48"]), size)
        path = OUT / f"{pet['id']}-{size}.cur"
        path.write_bytes(cur_file([(pixels, hotspot)]))
        sizes[size].update(hotspot=hotspot, cursor=path.name)
        (folder / str(size)).mkdir(exist_ok=True)

    states = []
    for role, system_role, label, frames, anchor, sequence, ticks, showcase_tick in motion:
        state = {
            "id": role, "role": system_role, "label": label,
            "file": f"{role}.ani", "variants": {}, "hotspots": {},
            "animated": True, "frame_count": len(frames), "sequence": sequence, "ticks": ticks,
        }
        for size in SIZES:
            resized = [frame.resize((size, size), Image.Resampling.NEAREST) for frame in frames]
            hotspot = sizes[size]["hotspot"] if anchor is None else scaled_hotspot(frames[0], resized, anchor, size)
            pixel = resized[0].getpixel(hotspot)
            if pixel[3] != 255 or any(frame.getpixel(hotspot) != pixel for frame in resized):
                raise ValueError(f"{pet['id']} {role} {size}px changed its hotspot pixel")
            if resized[0].tobytes() == resized[2].tobytes():
                raise ValueError(f"{pet['id']} {role} {size}px lost the closed-eye frame")
            path = folder / str(size) / state["file"]
            path.write_bytes(ani_file([cur_file([(frame, hotspot)]) for frame in resized], sequence, ticks))
            for index, frame in enumerate(resized):
                frame.save(folder / "frames" / f"{role}-{size}-{index}.png")
            state["variants"][str(size)] = path.relative_to(folder).as_posix()
            state["hotspots"][str(size)] = hotspot
            sizes[size]["roles"][role] = {
                "label": label,
                "frames": [png_uri(frame) for frame in resized],
                "sequence": sequence,
                "ticks": ticks,
                "showcaseTick": showcase_tick,
                "hotspot": hotspot,
                "cursor": path.relative_to(OUT).as_posix(),
            }
        shutil.copyfile(folder / state["variants"]["48"], folder / state["file"])
        states.append(state)
    if [state["role"] for state in states] != ORDER:
        raise ValueError("Theme must include all 17 roles in Windows scheme order")
    write_theme_package(folder, {
        "name": f"{pet['species']} · {pet['color']}", "states": states,
        "sizes": SIZES, "scheme_order": ORDER,
    })
    return {**pet, "sizes": sizes, "package": f"{pet['id']}-windows.zip"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ASSETS / "pets.json").read_text(encoding="utf-8"))
    colors = json.loads((ASSETS / "colors.json").read_text(encoding="utf-8"))
    data = []
    for pet in config:
        species_id = pet["id"]
        group = colors[species_id]
        master = load_master(species_id)
        shared = {**pet, "speciesId": species_id, "species": group["species"]}
        data.append(build_pet({**shared, "color": group["original"]}, master, None))
        for variant in group["variants"]:
            data.append(build_pet({**shared, "id": variant["id"], "color": variant["color"]}, master, variant))
    template = Path(__file__).with_name("other-pet-preview.html").read_text(encoding="utf-8")
    page = OUT / "其他宠物点击测试.html"
    page.write_text(
        template.replace("__PETS__", json.dumps(data, ensure_ascii=False)), encoding="utf-8"
    )
    DISTRIBUTION.parent.mkdir(parents=True, exist_ok=True)
    paths = {page.name}
    for pet in data:
        paths.add(pet["package"])
        for size in pet["sizes"].values():
            paths.add(size["cursor"])
            paths.update(action["cursor"] for action in size["roles"].values())
    with ZipFile(DISTRIBUTION, "w", compression=ZIP_DEFLATED) as package:
        for path in sorted(paths):
            package.write(OUT / path, path)
        package.writestr(
            "从这里开始.txt",
            "完整解压本包后，用浏览器打开「其他宠物点击测试.html」。\n"
            "测试页可离线使用，也能下载选中的 Windows 主题。\n",
        )


if __name__ == "__main__":
    main()
