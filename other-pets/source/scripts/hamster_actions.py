"""Role-specific hamster gestures on a fixed pixel grid."""

from math import cos, pi, sin

from PIL import Image, ImageDraw

from other_pet_motion import BADGES, ROLES, badge, compose


DESCRIPTIONS = {
    "normal": "眨眼呼吸",
    "help": "歪头、单耳抬起听动静",
    "working": "双手捧籽、咬一口再咀嚼",
    "wait": "闭眼打哈欠、慢慢伏低",
    "cross": "眯眼前倾、稳住肩膀瞄准",
    "text": "低头、收爪，视线逐行移动",
    "pen": "右爪伸出，来回写画",
    "unavailable": "缩头后仰、右爪挡在身前",
    "size-ns": "踮起再蹲下，上下拉伸",
    "size-we": "身体左右使劲、前臂拉扯",
    "size-nwse": "肩膀向左上使劲、臀部向右下压",
    "size-nesw": "肩膀向右上使劲、臀部向左下压",
    "move": "左右抬脚、摇摆搬运",
    "alternate": "抬头嗅上方、耳朵立起",
    "link": "鼻尖轻嗅、脸颊随呼吸鼓动",
    "pin": "俯身探路、左右嗅闻",
    "person": "右爪抬起挥手、身体开心轻弹",
}
INK = (81, 48, 33, 255)
PINK = (237, 164, 151, 255)


def displacement(role, x, y, wave):
    head = max(0, min(1, (28-y)/12)) * max(0, min(1, (x-9)/8))
    body = max(0, min(1, (y-22)/10))
    top = max(0, min(1, (41-y)/24))
    movement = {
        "help": ((y-17)*.13*head, (x-22)*.14*head),
        "working": (sin(y*.6)*.6*body, -1.2*body),
        "wait": (1.2*head, 2.4*top),
        "cross": (-1.7*head, .8*head),
        "text": (head, 1.8*head),
        "pen": (-.8*body, .8*body),
        "unavailable": (2.6*head, -head),
        "size-ns": (0, -3.6*top),
        "size-we": ((x-22)*.13*body, 0),
        "size-nwse": (-2.2*head+1.2*body, -2*head+body),
        "size-nesw": (2.2*head-1.2*body, -2*head+body),
        "move": (1.8*body, 1.3*cos(x*.3)*body),
        "alternate": (head, -2.6*head),
        "link": (-1.8*head, -.5*head),
        "pin": (-1.2*head, 2.2*head),
        "person": (.7*body, -2.4*top),
    }[role]
    return tuple(value*wave for value in movement)


def sculpt(master, role, wave):
    frame = Image.new("RGBA", master.size)
    for y in range(48):
        for x in range(48):
            dx, dy = displacement(role, x, y, wave)
            source = (round(x-dx), round(y-dy))
            if 0 <= source[0] < 48 and 0 <= source[1] < 48:
                frame.putpixel((x,y), master.getpixel(source))
    # The pointing hand remains registered even during a head/body gesture.
    frame.paste(master.crop((0,16,10,26)), (0,16))
    return frame


def feature_position(role, point, wave):
    dx, dy = displacement(role, *point, wave)
    return (round(point[0]+dx), round(point[1]+dy))


def eyelid(frame, role, wave, closed):
    if not closed:
        return
    x, y = feature_position(role, (20,14), wave)
    d = ImageDraw.Draw(frame)
    coat = frame.getpixel((x+3,y-2))
    d.rectangle((x-1,y-1,x+2,y+2), fill=coat)
    d.line((x-1,y+1,x+2,y+1), fill=INK)


def forepaw(frame, center, raised=False):
    d = ImageDraw.Draw(frame)
    # Clear the tucked hand with surrounding belly fur before drawing its new pose.
    d.rectangle((17,28,23,32), fill=frame.getpixel((25,32)))
    x,y = center
    d.line([(21,31),(x+1,y+1)], fill=INK, width=4)
    d.line([(21,30),(x,y)], fill=frame.getpixel((24,29)), width=3)
    d.ellipse((x-2,y-1,x+2,y+2), fill=PINK, outline=INK)
    d.line((x-1,y,x-1,y+1), fill=(255,207,183,255))
    if raised:
        d.point((x+1,y-2), fill=PINK)


def express(frame, role, wave, phase):
    d = ImageDraw.Draw(frame)
    mouth = feature_position(role, (12,21), wave)
    x,y = mouth
    if role == "wait" and wave > .2:
        height = 2 + round(wave*3)
        d.ellipse((x-1,y,x+2,y+height), fill=INK)
        d.point((x,y+height-1), fill=PINK)
    elif role == "working":
        forepaw(frame, (17,26))
        d = ImageDraw.Draw(frame)
        d.ellipse((13,23,17,28), fill=(124,73,35,255), outline=INK)
        d.line((15,24,15,27), fill=(246,211,146,255))
        if phase > 5:
            d.rectangle((13,23,14,24), fill=frame.getpixel((12,24)))
        if phase % 3 == 1:
            d.line((x,y+1,x+2,y+2), fill=INK)
    elif role == "pen":
        forepaw(frame, (14+round(2*sin(phase*pi/3)),29+round(wave)))
    elif role == "unavailable":
        forepaw(frame, (13,25-round(wave*2)), True)
    elif role == "person":
        forepaw(frame, (26+round(sin(phase*pi/3)*2),22-round(wave)), True)
    elif role == "text":
        forepaw(frame, (20,32))
    elif role in {"size-we","size-nwse","size-nesw","move"}:
        forepaw(frame, (13-round(wave*2),29-round(wave)))
    elif role in {"link","pin","alternate"}:
        # Nose and whisker gestures make sniffing readable at native size.
        nx,ny = feature_position(role,(11,16),wave)
        d.line((nx,ny,nx+1,ny), fill=PINK)
        if phase % 4 in (1,2):
            d.line((nx+1,ny+3,nx-2,ny+2), fill=(159,117,91,255))


def actions(originals):
    master = originals[0]
    for role, (system_role,label) in ROLES.items():
        if role == "normal":
            frames = [frame.copy() for frame in originals]
            sequence = [0,1,2,3,2,4,5,6,7]
            ticks = [66,11,4,7,4,10,17,12,33]
        else:
            frames=[]
            for phase in range(12):
                wave = (1-cos(phase*2*pi/11))/2
                if role in {"move","size-we","pin"}:
                    wave = sin(phase*2*pi/11)
                frame = sculpt(master, role, wave)
                closed = phase in (2,3) or (role=="wait" and 4<=phase<=8)
                eyelid(frame, role, wave, closed)
                express(frame, role, wave, phase)
                if role in BADGES:
                    badge(frame, role, phase//4%3, "cat")
                frames.append(frame)
            sequence=list(range(12))
            ticks=[48,7,5,5,7,9,11,9,7,7,8,30]
        frames,anchor=compose(frames,role)
        yield role,system_role,label,frames,anchor,sequence,ticks,None
