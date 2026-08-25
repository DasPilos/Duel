from pathlib import Path

from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parent.parent
TARGET = BASE_DIR / "assets" / "combat" / "hit_placeholder.png"
SIZE = 256

image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
center = SIZE // 2

draw.ellipse((72, 72, 184, 184), fill=(255, 185, 70, 235), outline=(255, 240, 170, 255), width=6)
draw.ellipse((94, 94, 162, 162), fill=(210, 70, 55, 255), outline=(255, 225, 150, 255), width=5)

for start, end in (
    ((center, 18), (center, 62)),
    ((center, 194), (center, 238)),
    ((18, center), (62, center)),
    ((194, center), (238, center)),
    ((48, 48), (78, 78)),
    ((208, 48), (178, 78)),
    ((48, 208), (78, 178)),
    ((208, 208), (178, 178)),
):
    draw.line((start, end), fill=(255, 215, 95, 235), width=8)

TARGET.parent.mkdir(parents=True, exist_ok=True)
image.save(TARGET, "PNG", optimize=True)
print(f"created {TARGET} {SIZE}x{SIZE} RGBA")