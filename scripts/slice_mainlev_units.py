"""Нарезает лист MainLev на блоки в раскладке листа и записывает их в assets/map/palette_sheets.json.

Палитра показывает эти блоки в самом низу, после объектов. Это копии обычных разделов, но тайлов, которые уже
стоят в образцах (palette_groups.json), здесь нет: они показаны только в образцах. Блок — окно листа в клетках
(строки r0–r1, столбцы c0–c1), раскладка тайлов в нём та же, что на листе, поэтому блок удобно брать рамкой и
вставлять куском.

Окна шире 10 тайлов не делаются: каталог показывает по 10 тайлов в ряд.
Чтобы нарезать другую область, добавьте окно в WINDOWS и запустите: python -m scripts.slice_mainlev_units
"""
import json
import re
from collections import Counter

from core.map_catalog import MAP_ASSETS, catalog_definitions, palette_groups, palette_hidden_keys

SHEETS_FILE = "palette_sheets.json"
MIN_TILES = 6
MAX_WIDTH = 10
KEY_RE = re.compile(r"ml_r(\d+)_c(\d+)")
WORDS = {
    "grass": "трава", "road": "дорога", "water": "вода", "rock": "скалы", "leaves": "листва", "floor": "пол и мосты",
}

# (первая строка, последняя строка, первый столбец, последний столбец) в клетках листа.
UNIT_COLS = ((0, 9), (10, 19), (20, 29))
WINDOWS = (
    # Юниты 10×7 (круглый декор сверху, блок-кольцо и блок-заливка) разных цветов.
    [(21, 27, c0, c1) for c0, c1 in UNIT_COLS + ((30, 39), (40, 49))]
    + [(r0, r1, c0, c1) for r0, r1 in ((28, 34), (35, 41), (42, 47)) for c0, c1 in UNIT_COLS]
    # Юниты с водой: делятся на половины не шире 10 тайлов.
    + [(r0, r1, c0, c1) for r0, r1 in ((28, 35), (36, 42), (43, 47)) for c0, c1 in ((30, 35), (36, 41), (42, 47), (48, 52))]
    # Блоки листвы и мосты справа вверху.
    + [(0, 20, 36, 42), (0, 20, 43, 52)]
)


def _tile_positions():
    positions = {}
    for item in catalog_definitions():
        match = KEY_RE.fullmatch(item["item_key"])
        if match and item["kind"] == "ground":
            positions[(int(match.group(1)), int(match.group(2)))] = item
    return positions


def slice_sheet():
    """Блоки листа: [{title, cells: [{key, x, y}], window, tiles}] и число клеток вне окон."""
    positions = _tile_positions()
    used = {cell["key"] for group in palette_groups() for cell in group["cells"]} | palette_hidden_keys()
    taken = set()
    blocks = []
    for r0, r1, c0, c1 in WINDOWS:
        assert c1 - c0 + 1 <= MAX_WIDTH, (r0, r1, c0, c1)
        window = {
            cell: item for cell, item in positions.items()
            if r0 <= cell[0] <= r1 and c0 <= cell[1] <= c1 and cell not in taken
        }
        taken.update(window)
        window = {cell: item for cell, item in window.items() if item["item_key"] not in used}
        if len(window) < MIN_TILES:
            continue
        top = min(row for row, _ in window)
        left = min(col for _, col in window)
        bottom = max(row for row, _ in window)
        right = max(col for _, col in window)
        main = Counter(item["category"] for item in window.values()).most_common(1)[0][0]
        blocks.append({
            "title": f"Лист · {WORDS.get(main, main)} · r{top}-{bottom} c{left:02d}-{right:02d}",
            "cells": [
                {"key": item["item_key"], "x": col - left, "y": row - top}
                for (row, col), item in sorted(window.items())
            ],
        })
    return blocks, taken


if __name__ == "__main__":
    blocks, _ = slice_sheet()
    (MAP_ASSETS / SHEETS_FILE).write_text(json.dumps(blocks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Блоков: {len(blocks)}, тайлов в блоках: {sum(len(block['cells']) for block in blocks)}")
    for block in blocks:
        width = max(cell["x"] for cell in block["cells"]) + 1
        height = max(cell["y"] for cell in block["cells"]) + 1
        print(f"  {block['title']}: {len(block['cells'])} тайлов, {width}x{height}")
