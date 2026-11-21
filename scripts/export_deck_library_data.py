"""Генерирует справочник Deck для клиента Godot из Python-источников.

Запуск из корня репозитория:  python scripts/export_deck_library_data.py

Пишет:
  godot_client/scripts/deck_library_data.gd  — тексты существ, карт, классов и эффектов;
  godot_client/tests/deck_library_samples.json — полный эталон для проверки клиента,
  включая записи предметов, которые Python строит из каталога сервера.
"""

import ast
import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GODOT_DIR = os.path.join(ROOT, "godot_client")
DATA_PATH = os.path.join(GODOT_DIR, "scripts", "deck_library_data.gd")
SAMPLES_PATH = os.path.join(GODOT_DIR, "tests", "deck_library_samples.json")
ITEMS_PATH = os.path.join(ROOT, "deck", "server", "items_database.py")

sys.path.insert(0, ROOT)

import pygame  # noqa: E402

pygame.init()

from deck.ui.library_window import LibraryWindow, _item_entry  # noqa: E402

GDSCRIPT_CONSTS = (
    ("Существа", "CREATURES"),
    ("Карты", "CARDS"),
    ("Классы", "CLASSES"),
    ("Эффекты", "EFFECTS"),
)
SAMPLE_ITEM_IDS = (4, 5, 6, 20, 30, 52, 92)


def gd_string(text):
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_data_file(catalogue):
    lines = [
        "extends RefCounted",
        "",
        "# Сгенерировано scripts/export_deck_library_data.py из deck/ui/library_window.py. Не править вручную.",
        "",
    ]
    for category, const_name in GDSCRIPT_CONSTS:
        lines.append(f"const {const_name} := [")
        for entry in catalogue[category]:
            lines.append(
                f'\t{{"name": {gd_string(entry["name"])}, '
                f'"description": {gd_string(entry["description"])}}},'
            )
        lines.append("]")
        lines.append("")
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def seed_items():
    with open(ITEMS_PATH, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CATALOG" for target in node.targets
        ):
            return {row[0]: row for row in ast.literal_eval(node.value)}
    raise RuntimeError("CATALOG не найден в items_database.py")


def server_item(row):
    """Предмет в формате ответа GET /api/deck/items (см. _item_payload в items_database.py)."""
    (item_id, name, item_type, rarity, weight, price, description,
     can_use, effects, bonuses, icon, equip_slot) = row
    return {
        "id": item_id,
        "name": name,
        "item_type": item_type,
        "rarity": rarity,
        "weight": weight,
        "price": price,
        "description": description,
        "can_use": bool(can_use),
        "effects": effects or {},
        "bonuses": bonuses or {},
        "icon": icon,
        "equip_slot": equip_slot,
    }


def write_samples(catalogue):
    rows = seed_items()
    items = []
    for item_id in SAMPLE_ITEM_IDS:
        item = server_item(rows[item_id])
        items.append({"item": item, "entry": _item_entry(item)})
    samples = {
        "categories": {category: catalogue[category] for category, _ in GDSCRIPT_CONSTS},
        "items": items,
    }
    with open(SAMPLES_PATH, "w", encoding="utf-8") as handle:
        json.dump(samples, handle, ensure_ascii=False, indent=1)


def main():
    window = LibraryWindow(SimpleNamespace(session=None))
    catalogue = window.data
    write_data_file(catalogue)
    write_samples(catalogue)
    for category, _ in GDSCRIPT_CONSTS:
        print(category, len(catalogue[category]))


if __name__ == "__main__":
    main()
