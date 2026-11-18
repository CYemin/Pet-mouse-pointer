"""Palette changes on the native sprite, before eye and body animation."""

from PIL import ImageColor


def calico_patch(x, y):
    if ((x - 36) / 5) ** 2 + ((y - 9) / 9) ** 2 < 1:
        return "black"
    if ((x - 35) / 7) ** 2 + ((y - 38) / 5.5) ** 2 < 1:
        return "black"
    if ((x - 38) / 7) ** 2 + ((y - 30) / 5.5) ** 2 < 1:
        return "orange"
    if ((x - 23) / 6) ** 2 + ((y - 10) / 9) ** 2 < 1:
        return "orange"
    return None


def recolor(image, spec):
    if not spec:
        return image
    source = sorted({pixel for pixel in image.get_flattened_data() if pixel[3]}, key=lambda pixel: sum(pixel[:3]))
    target = [(*ImageColor.getrgb(f"#{color}"), 255) for color in spec["palette"].split()]
    mapping = dict(zip(source, target, strict=True))
    changed = image.copy()
    pattern = spec.get("pattern")
    for y in range(image.height):
        for x in range(image.width):
            pixel = image.getpixel((x, y))
            if not pixel[3]:
                continue
            color = mapping[pixel]
            r, g, b, _ = pixel
            if pattern == "calico" and r > 170 and r - g > 43 and r - b > 75:
                patch = calico_patch(x, y)
                if patch == "orange":
                    color = pixel
                elif patch == "black":
                    shade = round((g - 75) * .17)
                    color = (47 + shade, 41 + shade, 44 + shade, 255)
            elif pattern == "lutino" and pixel == source[0] and 16 <= x < 21 and 16 <= y < 21:
                color = (109, 43, 45, 255)
            elif pattern == "lavender" and r > 220 and 120 < g < 215 and 35 < b < 116:
                band = 20 <= y + (x - 20) // 3 <= 26 or 35 <= y + (x - 30) // 4 <= 38
                if band:
                    tone = round((g - 130) * .46)
                    color = (151 + tone, 132 + tone, 155 + tone, 255)
            elif pattern == "pearl" and y >= 27 and x >= 22 and abs(r - g) < 32:
                if (y - 27) % 5 < 2 and (x + ((y - 27) // 5) * 2) % 6 < 2:
                    color = (229, 209, 167, 255)
            changed.putpixel((x, y), color)
    if changed.getchannel("A").tobytes() != image.getchannel("A").tobytes():
        raise ValueError("Recolor changed the pet silhouette")
    return changed
