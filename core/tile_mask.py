"""Частичная проходимость тайла: маска 4×4 клетки, где 1 — проходимо, 0 — блокирует.

Маска хранится строкой из 16 символов по строкам сверху вниз. Сервер и клиент используют одни и те же функции,
поэтому числа и правила пересечения держим здесь.
"""
import json
from pathlib import Path

MASK_SIDE = 4
MASK_CELLS = MASK_SIDE * MASK_SIDE
FREE = "1"
BLOCKED = "0"
PARTIAL_FILE = Path(__file__).resolve().parent.parent / "assets" / "map" / "partial.json"


def is_valid_mask(mask):
    return isinstance(mask, str) and len(mask) == MASK_CELLS and set(mask) <= {FREE, BLOCKED}


def load_partial_masks(path=PARTIAL_FILE):
    """Маски по ключам элементов каталога; без файла или с ошибочными масками пусто."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): mask for key, mask in data.items() if is_valid_mask(mask)}


def save_partial_masks(masks, path=PARTIAL_FILE):
    clean = {key: mask for key, mask in sorted(masks.items()) if is_valid_mask(mask)}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def mask_free_point(mask, tile_size, tile_x, tile_y, x, y):
    """Проходима ли клетка маски, в которую попадает точка мира (x, y)."""
    cell = tile_size // MASK_SIDE
    col = min(MASK_SIDE - 1, max(0, int(x - tile_x * tile_size) // cell))
    row = min(MASK_SIDE - 1, max(0, int(y - tile_y * tile_size) // cell))
    return mask[row * MASK_SIDE + col] == FREE


def mask_blocks_rect(mask, tile_x, tile_y, tile_size, left, top, right, bottom):
    """Перекрывает ли заблокированная клетка маски прямоугольник [left, right) × [top, bottom) в мире."""
    cell = tile_size // MASK_SIDE
    origin_x = tile_x * tile_size
    origin_y = tile_y * tile_size
    for row in range(MASK_SIDE):
        cell_top = origin_y + row * cell
        if cell_top >= bottom or cell_top + cell <= top:
            continue
        for col in range(MASK_SIDE):
            if mask[row * MASK_SIDE + col] != BLOCKED:
                continue
            cell_left = origin_x + col * cell
            if cell_left < right and cell_left + cell > left:
                return True
    return False
