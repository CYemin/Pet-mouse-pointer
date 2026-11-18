"""Compile three hamster colors, 17 animated states and a native-size playground."""

from pathlib import Path
import json

from PIL import Image

import build_other_pet_preview as compiler
from hamster_actions import DESCRIPTIONS, actions


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/hamster-states"


def colorize(image, color):
    result = image.copy()
    for y in range(48):
        for x in range(48):
            r, g, b, a = image.getpixel((x, y))
            if a and r > 135 and r - g > 8 and g - b > 12:
                if color == "silver":
                    value = round(.3*r + .5*g + .2*b)
                    result.putpixel((x, y), (value, value - 1, value + 2, a))
                elif color == "ivory":
                    result.putpixel((x, y), (min(255, r+17), min(250, g+27), min(241, b+35), a))
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    compiler.OUT = OUT
    source = ROOT / "output/hamster-idle"
    review = json.loads((source / "motion-review.json").read_text())
    originals = [Image.open(source / f"golden-normal-48-{i}.png").convert("RGBA") for i in range(8)]
    paw_box = (0, 16, 10, 26)
    paw = originals[0].crop(paw_box)
    for frame in originals:
        frame.paste(paw, paw_box[:2])
    data = []
    for color, label in (("golden","金黄"),("silver","银灰"),("ivory","奶白")):
        frames = [colorize(frame, color) for frame in originals]
        pet = {"id":f"hamster-{color}", "speciesId":"hamster", "species":"仓鼠",
               "name":"仓鼠", "color":label, "contact":"前爪趾尖",
               "hotspots":{"48":review["hotspot"]}}
        result = compiler.build_pet(pet, frames[0], None, list(actions(frames)))
        for variant in result["sizes"].values():
            for role, action in variant["roles"].items():
                action["gesture"] = DESCRIPTIONS[role]
        data.append(result)
    template = Path(__file__).with_name("hamster-states.html").read_text(encoding="utf-8")
    (OUT / "仓鼠17种状态测试.html").write_text(
        template.replace("__PETS__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    print("Three colors, 51 animated states, five sizes compiled.")


if __name__ == "__main__":
    main()
