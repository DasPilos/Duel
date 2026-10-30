"""База иконок предметов: PNG из папки assets/item_icons. Имя файла без .png — ключ иконки в базе предметов.

В названии файла указывается слот, например weapon_iron_sword.png или shield_oak.png. Выбор иконки в форме
предмета показывает файлы, которые подходят слоту по префиксу, а если таких нет — все.
"""
import re
from pathlib import Path

ITEM_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "item_icons"
ICON_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")

# Префиксы имён файлов по слотам (правая рука — оружие, левая — щит, как в палитре экипировки)
SLOT_ICON_PREFIXES = {
    "head": ("head_",), "ears": ("ears_",), "neck": ("neck_",), "back": ("back_",), "body": ("body_",),
    "hands": ("hands_",), "weapon": ("weapon_", "right_hand_"), "shield": ("shield_", "left_hand_"),
    "belt": ("belt_",), "ring": ("ring_", "rings_"), "ring_2": ("ring_", "rings_"), "legs": ("legs_",),
    "feet": ("feet_",),
}


def icon_keys():
    """Все ключи иконок из папки, по алфавиту."""
    if not ITEM_ICON_DIR.is_dir():
        return []
    return sorted(path.stem for path in ITEM_ICON_DIR.glob("*.png") if ICON_KEY_RE.match(path.stem))


def icon_path(key):
    return ITEM_ICON_DIR / f"{key}.png"


def icons_for_slot(slot):
    """Иконки, подходящие слоту по префиксу имени; если подходящих нет — все иконки папки."""
    keys = icon_keys()
    prefixes = SLOT_ICON_PREFIXES.get(slot, (f"{slot}_",))
    matching = [key for key in keys if key.startswith(prefixes)]
    return matching or keys


def is_known_icon(key):
    return bool(key) and bool(ICON_KEY_RE.match(key)) and icon_path(key).is_file()
