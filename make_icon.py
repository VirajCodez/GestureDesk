from pathlib import Path
import subprocess

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
ICONSET = ROOT / "build" / "GestureDesk.iconset"
ICONSET.mkdir(parents=True, exist_ok=True)

canvas_size = 1024
image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((32, 32, 992, 992), radius=220, fill="#172326")
draw.rounded_rectangle((74, 74, 950, 950), radius=190, outline="#35494a", width=14)

mint = "#8be4b7"
draw.rounded_rectangle((360, 310, 475, 710), radius=56, fill=mint)
draw.rounded_rectangle((493, 245, 608, 710), radius=56, fill=mint)
draw.rounded_rectangle((626, 315, 741, 710), radius=56, fill=mint)
draw.rounded_rectangle((230, 425, 345, 710), radius=56, fill=mint)
draw.rounded_rectangle((260, 610, 745, 795), radius=88, fill=mint)
draw.rounded_rectangle((434, 750, 640, 865), radius=52, fill="#d9ebdf")
draw.ellipse((760, 190, 836, 266), fill="#dfd47d")

sizes = (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
)

for filename, size in sizes:
    image.resize((size, size), Image.Resampling.LANCZOS).save(ICONSET / filename)

subprocess.run(
    ["iconutil", "-c", "icns", str(ICONSET), "-o", str(ROOT / "GestureDesk.icns")],
    check=True,
)