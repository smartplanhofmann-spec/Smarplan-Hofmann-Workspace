"""Render the original Smartplan floor-plan mark into native app-icon formats.

Geometry matches PlanMark in app/lib/design.dart. Requires pinned Pillow from
backend/requirements.lock; no third-party logos or downloaded images are used.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
INK = (29, 29, 31)


def mark(size, rounded):
    factor = 4
    side = size * factor
    image = Image.new("RGBA" if rounded else "RGB", (side, side), (0, 0, 0, 0) if rounded else INK)
    draw = ImageDraw.Draw(image)
    if rounded:
        draw.rounded_rectangle((0, 0, side - 1, side - 1), radius=side * .28, fill=INK)
    points = [(side * x, side * y) for x, y in ((.30, .68), (.30, .32), (.70, .32), (.70, .50), (.46, .50), (.46, .68))]
    width = max(1, round(side * .065))
    draw.line(points, fill="white", width=width, joint="curve")
    radius = width / 2
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    icon = ROOT / "app/windows/runner/resources/app_icon.ico"
    mark(256, True).save(icon, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    catalog = ROOT / "app/ios/Runner/Assets.xcassets/AppIcon.appiconset"
    for entry in json.loads((catalog / "Contents.json").read_text())["images"]:
        if "filename" in entry:
            size = round(float(entry["size"].split("x")[0]) * float(entry["scale"].removesuffix("x")))
            mark(size, False).save(catalog / entry["filename"])
    print("Original Smartplan mark rendered for Windows and iOS")


if __name__ == "__main__":
    main()
