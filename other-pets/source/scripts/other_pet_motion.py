"""Local pixel animation for the 48 px pet cursor masters."""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from operation_marks import MARKER_SIZES, PET_BOXES


ROLES = {
    "normal": ("Arrow", "正常选择"),
    "help": ("Help", "帮助选择"),
    "working": ("AppStarting", "后台运行"),
    "wait": ("Wait", "忙碌等待"),
    "cross": ("Crosshair", "精确定位"),
    "text": ("IBeam", "文本选择"),
    "pen": ("NWPen", "手写"),
    "unavailable": ("No", "不可用"),
    "size-ns": ("SizeNS", "垂直调整"),
    "size-we": ("SizeWE", "水平调整"),
    "size-nwse": ("SizeNWSE", "西北—东南调整"),
    "size-nesw": ("SizeNESW", "东北—西南调整"),
    "move": ("SizeAll", "移动"),
    "alternate": ("UpArrow", "候选选择"),
    "link": ("Hand", "链接选择"),
    "pin": ("Pin", "位置选择"),
    "person": ("Person", "人员选择"),
}
OPERATIONS = {*MARKER_SIZES, "cross", "text", "pen"}
BADGES = {"help", "working", "wait", "unavailable", "pin", "person"}
INK = "#553424"
CREAM = "#fff0ce"


PET_MOTION = {
    "cat": {
        "eye": (21, 17, 27, 23),
        "head": (17, 2, 43, 16),
        "link_delta": (0, -2),
        "body": (14, 27, 46, 46),
    },
    "cockatiel": {
        "eye": (16, 16, 21, 21),
        "head": (19, 2, 40, 16),
        "link_delta": (-1, -2),
        "body": (12, 24, 44, 46),
    },
    "gecko": {
        "eye": (17, 11, 22, 16),
        "head": (13, 7, 31, 17),
        "link_box": (25, 29, 44, 41),
        "link_delta": (1, -2),
        "body": (13, 17, 46, 37),
    },
}


def blink(image, box, closed, reference):
    """Compress the eye around its lower lid, using adjacent face pixels above it."""
    x0, y0, x1, y1 = box
    frame = image.copy()
    height = y1 - y0
    lid = y1 - 1
    kept = max(1, height // 2) if not closed else 1
    for x in range(x0, x1):
        # Restrict the edit to columns occupied by the dark eye.
        eye = [y for y in range(y0, y1) if sum(reference.getpixel((x, y))[:3]) < 180]
        if not eye:
            continue
        last = min(lid, max(eye) + 1)
        first = min(eye)
        face = image.getpixel((x, first - 1))
        for y in range(first, last + 1):
            frame.putpixel((x, y), face)
        for y in range(max(first, last - kept + 1), last + 1):
            source_y = eye[len(eye) * (y - (last - kept + 1)) // kept]
            frame.putpixel((x, y), image.getpixel((x, source_y)))
    return frame


def flex(image, box, dx, dy):
    """Resample a feature with a tapered displacement at its attachment edges."""
    x0, y0, x1, y1 = box
    frame = image.copy()
    for y in range(max(0, y0 - 2), min(image.height, y1 + 2)):
        for x in range(max(0, x0 - 2), min(image.width, x1 + 2)):
            across = min(1, (x - x0 + 3) / 5, (x1 + 2 - x) / 5)
            # The area near the head/body attachment stretches less.
            along = min(1, (y - y0 + 3) / 5, (y1 + 2 - y) / 6)
            weight = max(0, min(across, along))
            source = (x - round(dx * weight), y - round(dy * weight))
            if 0 <= source[0] < image.width and 0 <= source[1] < image.height:
                frame.putpixel((x, y), image.getpixel(source))
    return frame


def peck(image, level):
    frame = flex(image, (8, 4, 36, 24), -level, level)
    draw = ImageDraw.Draw(frame)
    # The underside of the bill opens around the anchored upper tip.
    draw.polygon([(8, 21), (11, 21), (13, 22), (11, 23 + level), (9, 23 + level)],
                 fill=INK)
    draw.line([(9, 22 + level), (11, 22 + level), (12, 22)], fill="#b3947c")
    if level == 1:
        draw.rectangle((4, 23, 6, 24), fill=INK)
        draw.point((5, 23), fill="#dcad51")
    else:
        draw.rectangle((6, 21, 8, 22), fill=INK)
        draw.point((7, 21), fill="#dcad51")
    return frame


def eat(image, phase):
    frame = image.copy()
    draw = ImageDraw.Draw(frame)
    if phase == 0:
        draw.rectangle((2, 20, 4, 22), fill=INK)
        draw.point((3, 21), fill="#9eac54")
        return frame
    draw.line([(10, 15), (12, 16), (16, 16)], fill=INK, width=2)
    tip = {1: (7, 18), 2: (3, 21), 3: (7, 18), 4: (10, 16)}[phase]
    draw.line([(12, 16), (9, 17), tip], fill="#8d3c55", width=4)
    draw.line([(12, 16), (9, 17), tip], fill="#f48da0", width=2)
    if phase < 4:
        food = (3, 21) if phase == 1 else tip
        x, y = food
        draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill="#6c542b")
        draw.point(food, fill="#c5be67")
    return frame


def pose(pet_id, image, role, strength):
    design = PET_MOTION[pet_id]
    head, body = design["head"], design["body"]
    if role == "link":
        box, delta = design.get("link_box", head), design["link_delta"]
    elif role in {"help", "unavailable", "pin", "person", "alternate"}:
        box, delta = head, {
            "help": (1, 2), "unavailable": (2, 1), "pin": (-2, 1),
            "person": (1, -2), "alternate": (0, -2),
        }[role]
    else:
        box, delta = body, {
            "normal": (0, -2), "working": (-1, -2), "wait": (0, 2),
            "cross": (-1, -2), "text": (-2, 0), "pen": (-2, -1),
            "size-ns": (0, -2), "size-we": (-2, 0), "size-nwse": (-2, -2),
            "size-nesw": (2, -2), "move": (-2, 1),
        }[role]
    return flex(image, box, *(int(value * strength) for value in delta))


@lru_cache
def operation_mark(role):
    if role in MARKER_SIZES:
        path = Path(__file__).resolve().parents[1] / "assets" / "operation-marks-v1" / f"{role}.png"
        mark = Image.open(path).convert("RGBA").resize(MARKER_SIZES[role], Image.Resampling.NEAREST)
        return mark, (mark.width // 2, 0 if role == "alternate" else mark.height // 2)
    mark = Image.new("RGBA", (17, 19))
    draw = ImageDraw.Draw(mark)
    if role == "cross":
        lines = [[(8, 1), (8, 17)], [(0, 9), (16, 9)]]
        anchor = (8, 9)
    elif role == "text":
        lines = [[(8, 1), (8, 17)], [(4, 1), (12, 1)], [(4, 17), (12, 17)]]
        anchor = (8, 9)
    else:
        draw.polygon([(1, 17), (3, 10), (12, 1), (16, 5), (7, 14)], fill=INK)
        draw.polygon([(4, 11), (12, 3), (14, 5), (6, 13)], fill="#dfab64")
        draw.line([(5, 11), (12, 4)], fill=CREAM, width=2)
        draw.line([(1, 17), (3, 15)], fill=INK, width=2)
        return mark, (1, 17)
    for line in lines:
        draw.line(line, fill=INK, width=5)
    for line in lines:
        draw.line(line, fill=CREAM, width=2)
    return mark, anchor


def badge(frame, role, phase, pet_id):
    icon = Image.new("RGBA", (16, 18))
    d = ImageDraw.Draw(icon)
    if role == "help":
        y = 3 + phase
        d.line([(5, y+2), (6, y), (10, y), (11, y+2), (11, y+4), (8, y+6), (8, y+7)],
               fill=INK, width=3)
        d.line([(5, y+2), (6, y), (10, y), (11, y+2), (11, y+4), (8, y+6), (8, y+7)],
               fill=CREAM, width=1)
        d.rectangle((7, y+9, 9, y+11), fill=INK)
        d.point((8, y+10), fill=CREAM)
    elif role == "working":
        dots = [(8, 4), (12, 8), (8, 12), (4, 8)]
        for i, (x, y) in enumerate(dots):
            d.rectangle((x-1, y-1, x+1, y+1), fill=INK)
            d.point((x, y), fill=CREAM if i == phase else "#bd9772")
    elif role == "wait":
        y = 6 - phase
        path = [(4, y), (10, y), (4, y+6), (10, y+6)]
        d.line(path, fill=INK, width=3)
        d.line(path, fill=CREAM, width=1)
    elif role == "unavailable":
        d.ellipse((2, 3, 13, 14), fill="#ffe5d2", outline=INK, width=2)
        d.line([(4, 12), (11, 5)], fill="#a44440", width=3)
    elif role == "pin":
        d.polygon([(3, 7), (5, 4), (11, 4), (13, 7), (12, 10), (8, 15), (4, 10)],
                  fill="#9b5041", outline=INK)
        d.rectangle((7, 6, 9, 8), fill=CREAM)
    else:
        d.ellipse((5, 3, 11, 9), fill=CREAM, outline=INK)
        d.polygon([(3, 14), (3, 12), (6, 9), (10, 9), (13, 12), (13, 14)],
                  fill="#bd9772", outline=INK)
    frame.alpha_composite(icon, (32, 0) if pet_id == "gecko" else (0, 0))


def compose(frames, role):
    if role not in OPERATIONS:
        return frames, None
    bounds = [frame.getbbox() for frame in frames]
    union = (min(b[0] for b in bounds), min(b[1] for b in bounds),
             max(b[2] for b in bounds), max(b[3] for b in bounds))
    x0, y0, x1, y1 = PET_BOXES.get(role, (16, 17, 47, 47))
    width, height = union[2] - union[0], union[3] - union[1]
    ratio = min((x1-x0) / width, (y1-y0) / height)
    size = (round(width * ratio), round(height * ratio))
    mark, (x, y) = operation_mark(role)
    position = (2, 2)
    result = []
    for frame in frames:
        canvas = Image.new("RGBA", (48, 48))
        art = frame.crop(union).resize(size, Image.Resampling.NEAREST)
        canvas.alpha_composite(art, (x1 - size[0], y1 - size[1]))
        canvas.alpha_composite(mark, position)
        result.append(canvas)
    return result, (position[0] + x, position[1] + y)


def animations(pet_id, image, reference=None):
    eye = PET_MOTION[pet_id]["eye"]
    reference = image if reference is None else reference
    half, closed = blink(image, eye, False, reference), blink(image, eye, True, reference)
    for role, (system_role, label) in ROLES.items():
        frames = [image.copy(), half.copy(), closed.copy()]
        sequence = [0, 1, 2, 1, 0]
        ticks = [83, 4, 6, 4, 15]
        showcase_tick = None
        if role != "normal" or pet_id != "cat":
            frames.extend(pose(pet_id, image, role, strength) for strength in (.5, 1))
            sequence.extend((3, 4, 3, 0))
            ticks.extend((5, 11, 5, 16))
        if role in {"normal", "link", "wait"} and pet_id == "cockatiel":
            showcase_tick = sum(ticks)
            start = len(frames)
            frames.extend(peck(image, level) for level in (1, 2))
            sequence.extend((start, start + 1, start, 0))
            ticks.extend((6, 7, 5, 19))
        if role in {"normal", "link", "wait"} and pet_id == "gecko":
            showcase_tick = sum(ticks)
            start = len(frames)
            frames.extend(eat(image, phase) for phase in range(5))
            sequence.extend(range(start, start + 5))
            sequence.append(0)
            ticks.extend((15, 4, 8, 5, 6, 19))
        if role in BADGES:
            for i, frame in enumerate(frames):
                badge(frame, role, [0, 0, 0, 1, 2][min(i, 4)], pet_id)
        frames, anchor = compose(frames, role)
        yield role, system_role, label, frames, anchor, sequence, ticks, showcase_tick
