"""Синхронизирует образец палитры редактора карт с черновиком художника.

Обновляет assets/map/palette_groups.json (раскладка образца), assets/map/overlay.json (тайлы поверх земли)
и списки проходимости: тайлы возвышенности (слой 3) непроходимы, кроме перечисленных в elevation_passable.
Тайлы образца идут слоем земли, кроме возвышенности и рек (слои 3 и 4): их прозрачные тайлы остаются поверх земли.
Поля образца (layout, source_rows, elevation_top, river_top, layer_names, elevation_passable) сохраняются между
запусками. Из одного черновика можно взять несколько образцов: --rows берёт только эти строки, y считается от первой.

Примеры:
  python -m scripts.sync_palette_group "Лесной ланшафт" --title "Лесной ландшафт · сухой лес" --cols 0-9 --rows 0-31 \\
      --landscape "Лесной ландшафт" --variant dry --layout 2
  python -m scripts.sync_palette_group "Лесной ланшафт" --title "Переход лес горы" --layout 0 --rows 118-124 --after "Лесной ландшафт"
  python -m scripts.sync_palette_group "Горный ланшафт" --title "Горный ландшафт" --elevation-top 20 --river-top 33
"""
import argparse
import json

import pygame

from client.map_drafts import list_drafts, load_draft
from core.map_catalog import (
    IMPASSABLE_FILE,
    MAP_ASSETS,
    OVERLAY_FILE,
    PALETTE_GROUPS_FILE,
    PASSABLE_FILE,
    TALL_ROLES,
    catalog_definitions,
    palette_group_layers,
)

TRANSPARENT_SHARE = 0.005
ALPHA_OPAQUE_FROM = 127


def _find_draft(name):
    matches = [draft for draft in list_drafts() if draft["name"].casefold() == name.casefold()]
    if not matches:
        raise SystemExit(f"Черновик «{name}» не найден")
    return load_draft(matches[0]["id"])


def _transparent_keys(catalog):
    keys = []
    for item in catalog:
        if item["kind"] != "ground":
            continue
        image = pygame.image.load(str(MAP_ASSETS / item["asset"]))
        area = image.get_width() * image.get_height()
        opaque = pygame.mask.from_surface(image, ALPHA_OPAQUE_FROM).count()
        if (area - opaque) / area > TRANSPARENT_SHARE:
            keys.append(item["item_key"])
    return keys


def _write(name, text):
    (MAP_ASSETS / name).write_text(text, encoding="utf-8", newline="\n")


def _rewrite_list(name, change):
    """Меняет список ключей в json, сохраняя сортировку, отступы и окончания строк файла."""
    path = MAP_ASSETS / name
    raw = path.read_bytes().decode("utf-8")
    keys = change(set(json.loads(raw)))
    text = json.dumps(sorted(keys), ensure_ascii=False, indent=1)
    path.write_bytes((text.replace("\n", "\r\n") if "\r\n" in raw else text).encode("utf-8"))
    return len(keys)


def _tall_keys(group, roles):
    """Тайлы слоёв образца с заданными ролями."""
    return {key for layer in palette_group_layers(group) if layer["role"] in roles for key in layer["cells"].values()}


def _find_group(groups, *titles):
    for title in titles:
        for item in groups:
            if title and item["title"].casefold() == title.casefold():
                return item
    return None


def sync(
    draft_name, title=None, passable=None, elevation_top=None, river_top=None, layer_names=None,
    rows=None, layout=None, after=None, replaces=None, mountain_top=None,
    cols=None, landscape=None, variant=None, note=None,
):
    draft = _find_draft(draft_name)
    title = title or draft["name"][:1].upper() + draft["name"][1:]
    catalog = catalog_definitions()
    known = {item["item_key"] for item in catalog}

    path = MAP_ASSETS / PALETTE_GROUPS_FILE
    groups = json.loads(path.read_text(encoding="utf-8"))
    previous = _find_group(groups, title, replaces)
    extras = {k: v for k, v in (previous or {}).items() if k not in ("title", "cells")}
    source_rows = list(rows) if rows else extras.get("source_rows")
    source_cols = list(cols) if cols else extras.get("source_cols")
    taken = [
        c for c in draft["cells"]
        if (not source_rows or source_rows[0] <= c["y"] <= source_rows[1])
        and (not source_cols or source_cols[0] <= c["x"] <= source_cols[1])
    ]
    if not taken:
        raise SystemExit("В выбранных строках и столбцах черновика нет тайлов")
    first = min(c["y"] for c in taken) if source_rows else 0
    left = source_cols[0] if source_cols else 0
    cells = sorted(
        ({"key": c["key"], "x": c["x"] - left, "y": c["y"] - first} for c in taken), key=lambda c: (c["y"], c["x"])
    )
    unknown = sorted({cell["key"] for cell in cells} - known)
    if unknown:
        raise SystemExit(f"Нет в каталоге: {', '.join(unknown[:5])}")

    group = {"title": title, "cells": cells, **extras}
    if source_rows:
        group["source_rows"] = source_rows
    if source_cols:
        group["source_cols"] = source_cols
    for field, value in (("landscape", landscape), ("variant", variant), ("note", note)):
        if value is not None:
            group[field] = value
    if layout is not None:
        group["layout"] = layout
    if elevation_top is not None:
        group["elevation_top"] = elevation_top
    if river_top is not None:
        group["river_top"] = river_top
    if mountain_top is not None:
        group["mountain_top"] = mountain_top
    if layer_names:
        group["layer_names"] = {**group.get("layer_names", {}), **layer_names}
    if passable is not None:
        group["elevation_passable"] = sorted(passable)
    stray = sorted(set(group.get("elevation_passable", [])) - _tall_keys(group, ("elevation",)))
    if stray:
        raise SystemExit(f"Нет среди тайлов возвышенности образца: {', '.join(stray)}")
    if not group.get("elevation_passable"):
        group.pop("elevation_passable", None)
    if previous is not None:
        groups[next(i for i, item in enumerate(groups) if item is previous)] = group
    else:
        anchor = next((i for i, item in enumerate(groups) if after and item["title"].casefold() == after.casefold()), None)
        groups.insert(len(groups) if anchor is None else anchor + 1, group)
    _write(PALETTE_GROUPS_FILE, json.dumps(groups, ensure_ascii=False, indent=1) + "\n")

    elevation = set().union(*(_tall_keys(item, ("elevation", "mountain")) for item in groups))
    tall = set().union(*(_tall_keys(item, TALL_ROLES) for item in groups))
    walkable_elevation = {key for item in groups for key in item.get("elevation_passable", [])}
    blocked_elevation = elevation - walkable_elevation
    # Дорога, трава, декор и малые тайлы образцов всегда проходимы, даже если раньше попали в непроходимые по ошибке.
    flat = set().union(*(
        {key for layer in palette_group_layers(item) if layer["role"] not in TALL_ROLES for key in layer["cells"].values()}
        for item in groups
    )) - tall
    grouped = {cell["key"] for item in groups for cell in item["cells"]} - tall
    overlay = sorted(key for key in _transparent_keys(catalog) if key not in grouped)
    _write(OVERLAY_FILE, json.dumps(overlay, ensure_ascii=False))
    unblocked = set()

    def unblock(keys):
        unblocked.update(keys & flat)
        return (keys | blocked_elevation) - walkable_elevation - flat

    blocked = _rewrite_list(IMPASSABLE_FILE, unblock)
    walkable = _rewrite_list(PASSABLE_FILE, lambda keys: (keys - blocked_elevation) | walkable_elevation | unblocked)
    print(
        f"Образец «{title}»: {len(cells)} клеток; тайлов поверх земли: {len(overlay)}; "
        f"возвышенность во всех образцах: {len(elevation)} (проходимых {len(walkable_elevation)}); "
        f"всего непроходимых {blocked}, проходимых {walkable}"
    )


def _rows(text):
    first, separator, last = text.partition("-")
    if not (separator and first.isdigit() and last.isdigit() and int(first) <= int(last)):
        raise argparse.ArgumentTypeError("нужен вид ПЕРВАЯ-ПОСЛЕДНЯЯ, например 0-31")
    return int(first), int(last)


def _layer_name(text):
    role, separator, name = text.partition("=")
    if not separator or not name:
        raise argparse.ArgumentTypeError("нужен вид РОЛЬ=название, например elevation=горная возвышенность")
    return role, name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("draft", help="название черновика с образцом")
    parser.add_argument("--title", help="название раздела в каталоге (по умолчанию название черновика)")
    parser.add_argument(
        "--passable", nargs="*", metavar="КЛЮЧ",
        help="тайлы возвышенности, по которым можно ходить (без аргумента список сохраняется из прошлой синхронизации)",
    )
    parser.add_argument("--elevation-top", type=int, help="строка образца, с которой начинается слой 3")
    parser.add_argument("--river-top", type=int, help="строка образца, с которой начинается слой 4 (реки)")
    parser.add_argument("--mountain-top", type=int, help="строка образца, с которой начинаются горы (слой 4)")
    parser.add_argument("--rows", type=_rows, help="взять из черновика только эти строки, например 0-31")
    parser.add_argument("--cols", type=_rows, help="взять из черновика только эти столбцы, например 15-24; x считается от первого")
    parser.add_argument("--landscape", help="общее название ландшафта, если образец — его вариант (Лесной ландшафт)")
    parser.add_argument("--variant", choices=("dry", "live"), help="вариант ландшафта: dry — сухой лес, live — живой лес")
    parser.add_argument("--note", help="пометка образца для генератора и ИИ")
    parser.add_argument("--layout", type=int, choices=(0, 1, 2), help="раскладка блоков образца (см. core/map_catalog.py)")
    parser.add_argument("--after", help="поставить новый образец в палитре после образца с этим названием")
    parser.add_argument("--replaces", help="заменить образец с этим названием (переименование)")
    parser.add_argument(
        "--layer-name", action="append", type=_layer_name, default=[], metavar="РОЛЬ=название",
        help="название слоя в палитре: ground, grass, ground_decor, grass_decor, elevation, river",
    )
    arguments = parser.parse_args()
    sync(
        arguments.draft, arguments.title, arguments.passable, arguments.elevation_top, arguments.river_top,
        dict(arguments.layer_name), arguments.rows, arguments.layout, arguments.after, arguments.replaces,
        arguments.mountain_top, arguments.cols, arguments.landscape, arguments.variant, arguments.note,
    )
