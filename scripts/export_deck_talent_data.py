"""Генерирует данные древа талантов Deck для клиента Godot из Python-источников.

Запуск из корня репозитория:  python scripts/export_deck_talent_data.py

Пишет:
  godot_client/scripts/deck_talent_data.gd    — деревья классов и таблица устаревших типов;
  godot_client/tests/deck_talent_samples.json — эталон для проверки клиента.
Эффекты улучшений в клиент не выгружаются: производные значения считает сервер.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GODOT_DIR = os.path.join(ROOT, "godot_client")
DATA_PATH = os.path.join(GODOT_DIR, "scripts", "deck_talent_data.gd")
SAMPLES_PATH = os.path.join(GODOT_DIR, "tests", "deck_talent_samples.json")

sys.path.insert(0, ROOT)

from deck.combat.character_stats import LEGACY_PROFESSION_TYPES  # noqa: E402
from deck.combat.talents import TALENT_TREES  # noqa: E402


def tree_entries(tree):
    entries = []
    for entry in tree:
        if entry.get("passive"):
            entries.append({
                "level": entry["level"],
                "passive": True,
                "name": entry["name"],
                "description": entry["description"],
            })
        else:
            entries.append({
                "level": entry["level"],
                "passive": False,
                "options": [
                    {"id": option["id"], "name": option["name"], "description": option["description"]}
                    for option in entry["options"]
                ],
            })
    return entries


def literal(value):
    # JSON-литералы совпадают с синтаксисом словарей и массивов GDScript.
    return json.dumps(value, ensure_ascii=False, indent="\t")


def write_data_file(legacy, trees):
    lines = [
        "extends RefCounted",
        "",
        "# Сгенерировано scripts/export_deck_talent_data.py из deck/combat/talents.py. Не править вручную.",
        "",
        f"const LEGACY_PROFESSION_TYPES := {literal(legacy)}",
        "",
        f"const TREES := {literal(trees)}",
        "",
    ]
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def write_samples(legacy, trees):
    samples = {"legacy_profession_types": legacy, "trees": trees}
    with open(SAMPLES_PATH, "w", encoding="utf-8") as handle:
        json.dump(samples, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def main():
    legacy = dict(LEGACY_PROFESSION_TYPES)
    trees = {profession: tree_entries(tree) for profession, tree in TALENT_TREES.items()}
    write_data_file(legacy, trees)
    write_samples(legacy, trees)
    print("trees: " + ", ".join(f"{name}={len(tree)}" for name, tree in trees.items()))


if __name__ == "__main__":
    main()
