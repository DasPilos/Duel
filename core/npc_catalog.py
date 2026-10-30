"""Каталог NPC (мобов) для редактора карт.

Спрайты лежат в assets/NPC/<папка>: листы 256x256 в стиле LPC, сетка 4x4 клеток по 64 px.
Строки листа: 0 — вниз, 1 — вверх, 2 — вправо, 3 — влево; в строке 4 кадра анимации.
Характеристики, экипировка и появление в мире добавятся отдельным этапом.
"""
from pathlib import Path

NPC_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "NPC"
NPC_FRAME = 64
NPC_FRAMES_PER_ROW = 4
NPC_ROW_DOWN, NPC_ROW_UP, NPC_ROW_RIGHT, NPC_ROW_LEFT = 0, 1, 2, 3

# (вариант, название, суффикс файла листа)
_IMP_VARIANTS = (
    ("vanilla", "Бес", "vanilla"),
    ("sword", "Бес с мечом", "sword"),
    ("pitchfork", "Бес с вилами", "pitchfork"),
    ("sword_shield", "Бес с мечом и щитом", "sword shield"),
    ("pitchfork_shield", "Бес с вилами и щитом", "pitchfork shield"),
)
# (префикс ключа, префикс названия): у каждого вида своя папка assets/NPC/<ключ>
# (цвет, префикс названия): ключ вида — imp_<вид>, а у цветных imp_<цвет>_<вид>; папка и файлы — по цвету
_IMP_COLORS = (
    ("red", ""),
    ("green", "Зелёный "),
    ("blue", "Синий "),
)


def _imp_name(prefix, name):
    return prefix + name[0].lower() + name[1:] if prefix else name


def _imp_key(color, variant):
    return f"imp_{variant}" if color == "red" else f"imp_{color}_{variant}"


NPC_CATALOG = tuple(
    {
        "key": _imp_key(color, variant),
        "name": _imp_name(color_name, name),
        "variant": variant,
        "folder": f"imp_{color}_{variant}",
        "walk": f"imp_{color}_{variant} walk.png",
        "attack": f"imp_{color}_{variant} attack.png",
        "death": f"imp_{color}_{variant} death.png",
    }
    for color, color_name in _IMP_COLORS
    for variant, name, _suffix in _IMP_VARIANTS
)


def npc_catalog():
    """Копия каталога: список описаний NPC в порядке показа в редакторе."""
    return [dict(npc) for npc in NPC_CATALOG]


def sheet_path(npc, action):
    """Путь к листу анимации NPC: action — walk или attack."""
    return NPC_ASSETS / npc["folder"] / npc[action]


def facing_row(angle):
    """Строка листа по углу взгляда в радианах (atan2(dy, dx), ось y вниз): вниз, вверх, вправо или влево."""
    import math
    dx, dy = math.cos(angle), math.sin(angle)
    if abs(dx) >= abs(dy):
        return NPC_ROW_RIGHT if dx >= 0 else NPC_ROW_LEFT
    return NPC_ROW_DOWN if dy >= 0 else NPC_ROW_UP
