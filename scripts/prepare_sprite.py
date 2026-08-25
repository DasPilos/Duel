from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE = BASE_DIR / "assets" / "fighters" / "base" / "fighter_source.png"
TARGET = BASE_DIR / "assets" / "fighters" / "base" / "fighter.png"
CANVAS_SIZE = 1024


image = cv2.imread(str(SOURCE), cv2.IMREAD_UNCHANGED)
if image is None:
    raise SystemExit(f"Cannot read {SOURCE}")

height, width = image.shape[:2]
if image.shape[2] == 3:
    rgba = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
else:
    rgba = image.copy()

# Удаляем только черные фоновые области, которые связаны с краями изображения.
dark = np.all(rgba[:, :, :3] < 24, axis=2).astype(np.uint8)
background = np.zeros((height, width), np.uint8)
flood_mask = np.zeros((height + 2, width + 2), np.uint8)
for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
    if dark[y, x]:
        cv2.floodFill(dark, flood_mask, (x, y), 2, loDiff=0, upDiff=0, flags=4)
background[dark == 2] = 255
rgba[background == 255, 3] = 0
remaining_black = np.all(rgba[:, :, :3] < 30, axis=2)
rgba[remaining_black, 3] = 0

canvas = rgba
if (width, height) != (CANVAS_SIZE, CANVAS_SIZE):
    scale = min((CANVAS_SIZE - 48) / width, (CANVAS_SIZE - 48) / height)
    scaled_width = int(width * scale)
    scaled_height = int(height * scale)
    rgba = cv2.resize(rgba, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((CANVAS_SIZE, CANVAS_SIZE, 4), dtype=np.uint8)
    offset_x = (CANVAS_SIZE - scaled_width) // 2
    offset_y = CANVAS_SIZE - scaled_height - 24
    canvas[offset_y:offset_y + scaled_height, offset_x:offset_x + scaled_width] = rgba

if not cv2.imwrite(str(TARGET), canvas):
    raise SystemExit(f"Cannot write {TARGET}")

print(f"saved {TARGET} {CANVAS_SIZE}x{CANVAS_SIZE} RGBA from {SOURCE.name}")