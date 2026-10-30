"""Каталог объектов редактора карт.

Записи описаны в коде и синхронизируются с таблицей map_catalog на сервере при старте.
Картинки лежат в assets/map. Деревья берутся из листов анимации (кадры по MAP_TREE_SHEETS
в scenes/world_map_scene.py), декоративные объекты вырезаны из Decorative.psd по одному на файл.
Тайлы земли из MainLev.psd лежат отдельными файлами в assets/map/mainlev/bYY_XX (блоки по
MAINLEV_BLOCK_W × MAINLEV_BLOCK_H тайлов); имя rRR_cCC — строка и столбец на листе.
"""
import functools
import json
import re
from pathlib import Path

MAP_SIZE_MIN = 16
MAP_SIZE_MAX = 512
DEFAULT_MAP_SIZE = 125

MAP_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "map"
MAINLEV_DIR = "mainlev"
MAINLEV_BLOCK_W = 6
MAINLEV_BLOCK_H = 7
MAINLEV_TILE_RE = re.compile(r"r(\d+)_c(\d+)\.png")

MAINLEV_TYPES_FILE = "tile_types.json"
IMPASSABLE_FILE = "impassable.json"
PASSABLE_FILE = "passable.json"
OVERLAY_FILE = "overlay.json"
PALETTE_GROUPS_FILE = "palette_groups.json"
PALETTE_SHEETS_FILE = "palette_sheets.json"
# Соглашение об образцах палитры (одно для любого образца: леса, гор и других). Каждый блок 5×5: кольцо вокруг —
# переходы, внутри 3×3 — тайлы слоя. Раскладка блоков задаётся полем layout образца.
# layout 2 («Лесной ландшафт»): шесть блоков 5×5. Блоки 1–4 в строках 0–9 — декор: слева два блока декора земли
#   (дороги), справа два блока декора травы, внутри каждого по 9 тайлов. Блоки 5 и 6 в строках 10–14 — слой 1
#   (земля, дорога) слева и слой 2 (трава) справа, внутри каждого по 9 базовых тайлов. Базовые тайлы при генерации
#   берутся в случайном порядке, а декор добавляется в основу случайно и не ближе DECOR_MIN_DISTANCE клеток к другому декору.
#   Слева стоят три больших блока дороги в столбик (1, 3, 5), справа три больших блока травы (2, 4, 6). Под ними в
#   строках 15–18 малые тайлы: слева дорожные, справа травяные (угловые вырезы, мелкие фрагменты и плоские варианты тона).
# layout 1 (по умолчанию, горный ландшафт): первая пара блоков сверху — слой 1 (земля) слева и слой 2 (трава) справа,
#   центр каждого из них — главный чистый тайл (MAIN_TILE_SHARE клеток), остальные 8 тайлов внутри — декор;
#   вторая пара под ней — ещё декор: слева декор земли, справа декор травы.
# layout 0: образец без слоёв, просто блок тайлов (например, переход лес — горы).
# Слой 3 — возвышенность (горы), начиная со строки elevation_top образца (по умолчанию ELEVATION_TOP).
# Слой 4 — рельеф: реки со строки river_top образца и горы со строки mountain_top (если они есть). Все блоки шириной 10,
# до следующего слоя или конца образца. Горы непроходимы целиком, как возвышенность.
# Тайлы возвышенности непроходимы (impassable.json), прозрачные тайлы возвышенности и рек идут слоем поверх земли.
# На землю, возвышенность и реки деревья и кусты не ставятся, их можно ставить только на траву.
# Поля образца в palette_groups.json: elevation_top, river_top, mountain_top, layer_names {роль: название}, elevation_passable,
# source_rows и source_cols (откуда взят образец в черновике), landscape и variant (образец — вариант ландшафта: у лесного
# два шаблона, dry — сухой лес и live — живой лес), note (пометка для генератора и ИИ).
# Тайлы гор, листвы, дорог, воды и травы (HIDDEN_CATEGORIES), не вошедшие ни в один образец, палитра не показывает (palette_hidden_keys).
LAYER_BLOCK_SIDE = 5
ELEVATION_TOP = 17
# (роль, название, левая колонка, верхняя строка, ширина, высота, можно ли ставить деревья и кусты)
LAYER_BLOCKS = (
    ("ground", "земля", 0, 0, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, False),
    ("grass", "трава", LAYER_BLOCK_SIDE, 0, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, True),
    ("ground_decor", "декор земли", 0, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, False),
    ("grass_decor", "декор травы", LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, True),
)
DOUBLE = 2 * LAYER_BLOCK_SIDE
LAYER_BLOCKS_V2 = (
    ("ground", "земля", 0, DOUBLE, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, False),
    ("grass", "трава", LAYER_BLOCK_SIDE, DOUBLE, LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, True),
    ("ground_decor", "декор земли", 0, 0, LAYER_BLOCK_SIDE, DOUBLE, False),
    ("grass_decor", "декор травы", LAYER_BLOCK_SIDE, 0, LAYER_BLOCK_SIDE, DOUBLE, True),
    ("ground_small", "малые: дорога", 0, 3 * LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, 4, False),
    ("grass_small", "малые: трава", LAYER_BLOCK_SIDE, 3 * LAYER_BLOCK_SIDE, LAYER_BLOCK_SIDE, 4, True),
)
SMALL_ROLES = ("ground_small", "grass_small")
DECOR_BASE = {"ground_decor": "ground", "grass_decor": "grass"}
TALL_ROLES = ("elevation", "river", "mountain")
UNNUMBERED_ROLES = tuple(DECOR_BASE) + SMALL_ROLES
LAYER_NUMBERS = {"ground": 1, "grass": 2, "elevation": 3, "river": 4, "mountain": 4}
HIDDEN_CATEGORIES = ("rock", "leaves", "road", "water", "grass")
MAIN_TILE_SHARE = 0.9
DECOR_CHANCE = 1 - MAIN_TILE_SHARE
DECOR_MIN_DISTANCE = 3

TREE_ENTRIES = (
    ("tree1", "tree", "trees/tree1.png"),
    ("tree2", "tree", "trees/tree2.png"),
    ("tree3", "tree", "trees/tree3.png"),
    ("old_tree1", "old_tree", "trees/old_tree1.png"),
    ("old_tree2", "old_tree", "trees/old_tree2.png"),
    ("old_tree3", "old_tree", "trees/old_tree3.png"),
    ("big_tree", "old_tree", "trees/big_tree.png"),
)

BLOCKING_CATEGORIES = ("tree", "old_tree", "log", "stump", "rock", "water")
DECOR_COUNT = 100
DEFAULT_DECOR_CATEGORY = "bush"
# Номера объектов соответствуют порядку вырезки из Decorative.psd (слева направо, сверху вниз).
DECOR_CATEGORIES = (
    ("old_tree", (1, 2, 3, 27)),
    ("tree", (4, 5, 6)),
    ("log", (7, 8, 11, 12)),
    ("stump", (9, 10)),
)


def _decor_category(number):
    for category, numbers in DECOR_CATEGORIES:
        if number in numbers:
            return category
    return DEFAULT_DECOR_CATEGORY


def _tree_entries():
    for key, category, asset in TREE_ENTRIES:
        yield key, "object", category, asset


def _decor_entries():
    for number in range(1, DECOR_COUNT + 1):
        key = f"dec_{number:03d}"
        yield key, "object", _decor_category(number), f"objects/{key}.png"


def _mainlev_types():
    """Тип каждого тайла MainLev по блокам: {блок: {rRR_cCC: категория}}."""
    return json.loads((MAP_ASSETS / MAINLEV_DIR / MAINLEV_TYPES_FILE).read_text(encoding="utf-8"))


def _impassable_keys():
    """Ключи тайлов и объектов, которые художник пометил как непроходимые."""
    return frozenset(json.loads((MAP_ASSETS / IMPASSABLE_FILE).read_text(encoding="utf-8")))


def _passable_keys():
    """Ключи, которые художник пометил как проходимые: они не блокируют даже в блокирующей категории."""
    return frozenset(json.loads((MAP_ASSETS / PASSABLE_FILE).read_text(encoding="utf-8")))


@functools.cache
def overlay_keys():
    """Тайлы земли с прозрачными частями: редактор ставит их слоем overlay поверх земли, а не вместо неё."""
    return frozenset(json.loads((MAP_ASSETS / OVERLAY_FILE).read_text(encoding="utf-8")))


@functools.cache
def palette_groups():
    """Образцы художника: разделы палитры, где тайлы лежат в заданной раскладке (x, y) одним блоком."""
    return json.loads((MAP_ASSETS / PALETTE_GROUPS_FILE).read_text(encoding="utf-8"))


@functools.cache
def palette_sheets():
    """Блоки листа MainLev для низа палитры (scripts/slice_mainlev_units.py): [{title, cells: [{key, x, y}]}].

    Это копии тайлов в раскладке листа; основные разделы и образцы от них не меняются.
    """
    path = MAP_ASSETS / PALETTE_SHEETS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _layer_specs(group):
    """Блоки слоёв образца: основные четыре, возвышенность и (если задана river_top) реки; названия из layer_names."""
    layout = group.get("layout", 1)
    if layout == 0:
        return []
    last = max((cell["y"] for cell in group["cells"]), default=0)
    wide = 2 * LAYER_BLOCK_SIDE
    specs = list(LAYER_BLOCKS_V2 if layout == 2 else LAYER_BLOCKS)
    tops = [
        (role, name, group.get(field, default))
        for role, name, field, default in (
            ("elevation", "возвышенность", "elevation_top", ELEVATION_TOP),
            ("river", "реки", "river_top", None),
            ("mountain", "горы", "mountain_top", None),
        )
    ]
    tops = [(role, name, top) for role, name, top in tops if top is not None]
    for index, (role, name, top) in enumerate(tops):
        end = tops[index + 1][2] if index + 1 < len(tops) else last + 1
        specs.append((role, name, 0, top, wide, end - top, False))
    names = group.get("layer_names", {})
    return [(role, names.get(role, name), *rest) for role, name, *rest in specs]


def palette_group_layers(group):
    """Блоки образца по соглашению.

    Список {role, number, name, title, decor, objects_allowed, x, y, w, h, cells, inner}; cells — весь блок
    {(x, y): ключ}, inner — внутренние 3×3 каждого блока 5×5 в нём (у возвышенности, рек, гор и малых тайлов пусто).
    У земли, травы, возвышенности, рек и гор number 1, 2, 3, 4 и 4 (реки и горы — слой 4 «рельеф»), у декора и малых
    тайлов None. Образец с layout 0 слоёв не имеет.
    Попадают только блоки, где есть тайлы: так генератор карт находит землю, траву, их декор, возвышенность, реки и горы.
    """
    cells = {(cell["x"], cell["y"]): cell["key"] for cell in group["cells"]}
    layers = []
    for role, name, left, top, width, height, objects_allowed in _layer_specs(group):
        block = {
            (x, y): key
            for (x, y), key in cells.items()
            if left <= x < left + width and top <= y < top + height
        }
        if not block:
            continue
        decor = role in DECOR_BASE
        number = LAYER_NUMBERS.get(role)
        title = f"Слой {number} · {name}" if number else (f"Декор · {name.split()[-1]}" if decor else name)
        layers.append({
            "role": role, "number": number, "name": name, "decor": decor, "title": title,
            "objects_allowed": objects_allowed,
            "x": left, "y": top, "w": width, "h": height, "cells": block,
            "inner": {} if role in TALL_ROLES or role in SMALL_ROLES else {
                (x, y): key for (x, y), key in block.items()
                if 0 < (x - left) % LAYER_BLOCK_SIDE < LAYER_BLOCK_SIDE - 1
                and 0 < (y - top) % LAYER_BLOCK_SIDE < LAYER_BLOCK_SIDE - 1
            },
        })
    return layers


def _inner_blocks(layer):
    """Внутренние тайлы каждого блока 5×5 слоя по порядку сверху вниз, слева направо: [[ключи], ...] (пустой блок — [])."""
    side = LAYER_BLOCK_SIDE
    cells = {}
    for (x, y), key in layer["inner"].items():
        cells.setdefault(((y - layer["y"]) // side, (x - layer["x"]) // side), {})[(x, y)] = key
    result = []
    for row in range(layer["h"] // side):
        for col in range(layer["w"] // side):
            block, keys = cells.get((row, col), {}), []
            for position in sorted(block, key=lambda cell: (cell[1], cell[0])):
                if block[position] not in keys:
                    keys.append(block[position])
            result.append(keys)
    return result


def _inner_keys(layer):
    keys = []
    for position in sorted(layer["inner"], key=lambda cell: (cell[1], cell[0])):
        if layer["inner"][position] not in keys:
            keys.append(layer["inner"][position])
    return keys


def palette_group_decor(group):
    """Основа и декор образца: {"ground": {"base": [ключи], "decor": [ключи]}, "grass": {...}}.

    base — тайлы основы дороги или травы, берутся в случайном порядке. decor — тайлы декора, их ставят редко (DECOR_CHANCE)
    и не ближе DECOR_MIN_DISTANCE клеток друг к другу.
    layout 2: base — 9 тайлов внутри блока слоя (блоки 5 и 6), decor — тайлы внутри блоков декора (блоки 1–4).
    layout 1: base — один главный тайл, центр блока слоя 1 или 2; decor — остальные 8 тайлов внутри него и 9 тайлов
    внутри блока декора; ключ main равен этому главному тайлу.
    layout 2, если внутри блока слоя (5 или 6) пусто: основой становятся тайлы первого заполненного блока декора,
    остальные блоки декора остаются декором (так работает недоделанный образец).
    Роль без нужных блоков, без тайлов или без центрального тайла (layout 1) в результат не попадает.
    """
    layers = {layer["role"]: layer for layer in palette_group_layers(group)}
    result = {}
    for decor_role, base_role in DECOR_BASE.items():
        if base_role not in layers or decor_role not in layers:
            continue
        block = layers[base_role]
        if group.get("layout", 1) == 2:
            parts = _inner_blocks(layers[decor_role])
            base = _inner_keys(block)
            if not base:
                filled = [part for part in parts if part]
                if not filled:
                    continue
                base, parts = filled[0], filled[1:]
            result[base_role] = {"base": base, "decor": [key for part in parts for key in part if key not in base]}
            continue
        main = block["cells"].get((block["x"] + LAYER_BLOCK_SIDE // 2, block["y"] + LAYER_BLOCK_SIDE // 2))
        if main is None:
            continue
        decor = []
        for key in _inner_keys(block) + _inner_keys(layers[decor_role]):
            if key != main and key not in decor:
                decor.append(key)
        result[base_role] = {"main": main, "base": [main], "decor": decor}
    return result


def decor_fits(x, y, placed):
    """Можно ли поставить декор в (x, y): ближе DECOR_MIN_DISTANCE клеток (по большей из осей) другого декора
    того же слоя быть не должно. placed — {(x, y): ключ} уже стоящий декор."""
    reach = DECOR_MIN_DISTANCE - 1
    return not any(
        (x + dx, y + dy) in placed for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)
    )


def decor_spaced(placed):
    """Соблюдено ли правило расстояния между всем уже стоящим декором слоя."""
    reach = DECOR_MIN_DISTANCE - 1
    return all(
        (x + dx, y + dy) not in placed
        for x, y in placed
        for dx in range(-reach, reach + 1)
        for dy in range(-reach, reach + 1)
        if dx or dy
    )


def pick_decor(decor_keys, x, y, placed, rng, chance=DECOR_CHANCE):
    """Случайный декор для основы в (x, y) или None: с вероятностью chance и если decor_fits.

    Выбранный декор записывается в placed, поэтому обходить клетки нужно в случайном порядке одним словарём
    на каждый слой (землю и траву отдельно). Остальные клетки получают главный тайл.
    """
    if not decor_keys or rng.random() >= chance or not decor_fits(x, y, placed):
        return None
    placed[(x, y)] = rng.choice(list(decor_keys))
    return placed[(x, y)]


def palette_landscape(landscape):
    """Образцы одного ландшафта по вариантам: {"dry": группа, "live": группа} у лесного; образец без поля variant идёт под "main".

    Лесной ландшафт состоит из двух шаблонов: первый (dry) для сухого леса (большие и маленькие пни, сухие деревья),
    второй (live) для живого леса. Поле note образца кратко описывает это для генератора и ИИ.
    """
    result = {}
    for group in palette_groups():
        if group.get("landscape", group["title"]) == landscape:
            result[group.get("variant", "main")] = group
    return result


def palette_hidden_keys(catalog=None):
    """Тайлы гор, листвы, дорог, воды и травы (HIDDEN_CATEGORIES), не вошедшие ни в один образец: палитра их не показывает.

    В каталоге и в базе они остаются, поэтому старые карты и черновики с ними открываются как раньше.
    """
    used = {cell["key"] for group in palette_groups() for cell in group["cells"]}
    return frozenset(
        item["item_key"]
        for item in (catalog_definitions() if catalog is None else catalog)
        if item["kind"] == "ground" and item["category"] in HIDDEN_CATEGORIES and item["item_key"] not in used
    )


@functools.cache
def _object_surfaces():
    allowed, forbidden = set(), set()
    for group in palette_groups():
        for layer in palette_group_layers(group):
            (allowed if layer["objects_allowed"] else forbidden).update(layer["cells"].values())
    return frozenset(allowed), frozenset(forbidden)


def tile_allows_objects(item_key, category):
    """Можно ли ставить деревья и кусты на тайл земли: только на траву, не на землю-дорогу.

    Роль тайла берётся из блоков слоёв образцов (запрет земли сильнее). Для тайлов вне этих блоков
    решает категория: трава подходит, всё остальное нет.
    """
    allowed, forbidden = _object_surfaces()
    if item_key in forbidden:
        return False
    return item_key in allowed or category == "grass"


def _mainlev_entries():
    types = _mainlev_types()
    for path in sorted((MAP_ASSETS / MAINLEV_DIR).glob("b*/r*_c*.png")):
        match = MAINLEV_TILE_RE.fullmatch(path.name)
        if match is None:
            continue
        row, col = int(match.group(1)), int(match.group(2))
        category = types[path.parent.name][path.stem]
        yield f"ml_r{row:02d}_c{col:02d}", "ground", category, f"{MAINLEV_DIR}/{path.parent.name}/{path.name}"


def _entries():
    yield from _tree_entries()
    yield from _decor_entries()
    yield from _mainlev_entries()


def catalog_definitions():
    """Список записей каталога для синхронизации с базой."""
    impassable = _impassable_keys()
    passable = _passable_keys()
    return [
        {
            "item_key": key,
            "kind": kind,
            "category": category,
            "asset": asset,
            "footprint_w": 1,
            "footprint_h": 1,
            "blocks": key in impassable or (category in BLOCKING_CATEGORIES and key not in passable),
            "sort_order": order,
        }
        for order, (key, kind, category, asset) in enumerate(_entries(), start=1)
    ]
