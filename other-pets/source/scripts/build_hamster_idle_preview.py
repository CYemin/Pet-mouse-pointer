"""Extract the generated idle sheet, align its leading paw and export a preview."""

from pathlib import Path
import json

from PIL import Image, ImageDraw

from build_complete_theme import pixel_convert
from build_samples import ani_file, cur_file


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "hamster-idle"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(ROOT / "assets/hamster-concepts/golden-idle-sheet.png").convert("RGBA")
    cells = []
    points = []
    for index in range(8):
        left = round(index % 4 * sheet.width / 4)
        top = round(index // 4 * sheet.height / 2)
        right = round((index % 4 + 1) * sheet.width / 4)
        bottom = round((index // 4 + 1) * sheet.height / 2)
        cell = sheet.crop((left, top, right, bottom))
        cell.putalpha(cell.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
        bounds = cell.getbbox()
        # Measure the left edge of the pink paw, excluding stray outline pixels.
        paw = [(x, y) for x in range(bounds[0], bounds[0] + 45)
               for y in range(bounds[1] + 100, bounds[1] + 200)
               if (lambda p: p[3] == 255 and p[0] > 160 and p[0] - p[1] > 20
                   and p[1] > 80)(cell.getpixel((x, y)))]
        x = min(point[0] for point in paw)
        rows = [y for px, y in paw if px == x]
        points.append((x, round(sum(rows) / len(rows))))
        cells.append(cell)
    extent = max(max(cell.getbbox()[2] - point[0], point[1] - cell.getbbox()[1],
                     cell.getbbox()[3] - point[1]) for cell, point in zip(cells, points))
    side = round(extent / .79)
    aligned = []
    for cell, point in zip(cells, points):
        canvas = Image.new("RGBA", (side, side))
        canvas.alpha_composite(cell, (round(side * .07) - point[0], round(side * .43) - point[1]))
        aligned.append(canvas.resize((48, 48), Image.Resampling.NEAREST))
    frames = pixel_convert(aligned, {"pixel_alpha_threshold": 128, "pixel_palette_colors": 24})
    hotspot = (3, 21)
    # Find the nearest consistently opaque paw pixel for the exported cursor.
    candidates = [(x, y) for x in range(1, 7) for y in range(18, 25)
                  if all(frame.getpixel((x, y))[3] for frame in frames)]
    hotspot = min(candidates, key=lambda p: (p[0]-hotspot[0])**2 + (p[1]-hotspot[1])**2)
    sequence = [0, 1, 2, 3, 2, 4, 5, 6, 7]
    durations = [1100, 180, 70, 110, 70, 160, 280, 200, 550]
    for index, frame in enumerate(frames):
        frame.save(OUT / f"golden-normal-48-{index}.png")
    data = ani_file([cur_file([(frame, hotspot)]) for frame in frames], sequence,
                    [round(ms * 60 / 1000) for ms in durations])
    (OUT / "golden-normal-48.ani").write_bytes(data)
    views = []
    for index in sequence:
        board = Image.new("RGB", (360, 270), "#f4efe6")
        frame = frames[index]
        board.paste(frame.resize((240, 240), Image.Resampling.NEAREST), (0, 12), frame.resize((240, 240), Image.Resampling.NEAREST))
        board.paste(frame, (285, 108), frame)
        draw = ImageDraw.Draw(board)
        draw.text((280, 170), "48 px", fill="#634b3d")
        views.append(board)
    views[0].save(OUT / "golden-idle-preview.gif", save_all=True, append_images=views[1:],
                  duration=durations, loop=0, optimize=False)
    (OUT / "motion-review.json").write_text(json.dumps({
        "source_landmarks": points, "hotspot": hotspot, "sequence": sequence,
        "durations_ms": durations, "unique_frames": len({f.tobytes() for f in frames}),
        "review_note": "Generated drawings may retain minor fur texture variation."
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
