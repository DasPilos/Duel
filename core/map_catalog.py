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
MAP_SIZE_MAX = 1600
DEFAULT_MAP_SIZE = 125

MAP_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "map"
MAINLEV_DIR = "mainlev"
CRYSTAL_DIR = "crystals"
CRYSTAL_CATEGORY = "crystal"
ROCKY_GROUND_MOSS_GRASS_TILE_IDS = frozenset({
    47, 49, 51, 52, 54, 55,
    77, 78, 79, 81, 82, 84, 85,
    107, 108, 109, 113, 116, 254,
})
ROCKY_DIR = "rocky"
ROCKY_CATALOG_FILE = "catalog.json"
WINTER_DIR = "winter"
WINTER_CATALOG_FILE = "catalog.json"
UNDEAD_DIR = "undead"
UNDEAD_CATALOG_FILE = "catalog.json"
DESERT_DIR = "desert"
DESERT_CATALOG_FILE = "catalog.json"
GRASSLAND_DIR = "grassland"
GRASSLAND_CATALOG_FILE = "catalog.json"
CITY_BUILDINGS_DIR = "city_buildings"
CITY_BUILDINGS_CATALOG_FILE = "catalog.json"
BUSH_DIR = "bushes"
ANIMAL_DIR = "animals"
WATER_ANIMAL_KEYS = frozenset({
    "animal_duck_water",
    "animal_drake_water",
    "animal_duckling_water",
})
MAINLEV_BLOCK_W = 6
MAINLEV_BLOCK_H = 7
MAINLEV_TILE_RE = re.compile(r"r(\d+)_c(\d+)\.png")

MAINLEV_TYPES_FILE = "tile_types.json"
IMPASSABLE_FILE = "impassable.json"
PASSABLE_FILE = "passable.json"
OVERLAY_FILE = "overlay.json"
PALETTE_GROUPS_FILE = "palette_groups.json"
PALETTE_SHEETS_FILE = "palette_sheets.json"
INFRASTRUCTURE_GROUP = "Инфраструктура"
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

BLOCKING_CATEGORIES = ("tree", "old_tree", "log", "stump", "rock", "water", "animal", CRYSTAL_CATEGORY)
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


def _crystal_entries():
    # Файлы <цвет>_<стадия>.png: стадия 1 — самый маленький кристалл, стадия 4 — созревший (для роста).
    for path in sorted((MAP_ASSETS / CRYSTAL_DIR).glob("*.png")):
        yield f"crystal_{path.stem.lower()}", "object", CRYSTAL_CATEGORY, f"{CRYSTAL_DIR}/{path.name}"


def _bush_entries():
    for path in sorted((MAP_ASSETS / BUSH_DIR).glob("*.png")):
        yield f"bush_{path.stem}", "object", "bush", f"{BUSH_DIR}/{path.name}"


def _animal_entries():
    for path in sorted((MAP_ASSETS / ANIMAL_DIR).glob("*.png")):
        yield f"animal_{path.stem}", "object", "animal", f"{ANIMAL_DIR}/{path.name}"


@functools.cache
def rocky_tiles():
    """Tiles imported from Rocky_area.tmx, including their source-sheet placement and layer role."""
    path = MAP_ASSETS / ROCKY_DIR / ROCKY_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def rocky_tile_specs():
    return {item["key"]: item for item in rocky_tiles()}


@functools.cache
def rocky_animated_groups():
    """Whole-cell compositions for adjacent animated Rocky water tiles."""
    path = MAP_ASSETS / ROCKY_DIR / ROCKY_CATALOG_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("animated_groups", [])


@functools.cache
def rocky_water_object_groups():
    """Whole Rocky object-and-wave compositions sampled from the author's Tiled map."""
    path = MAP_ASSETS / ROCKY_DIR / ROCKY_CATALOG_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("water_object_groups", [])


@functools.cache
def rocky_animations():
    path = MAP_ASSETS / ROCKY_DIR / "animations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _rocky_entries():
    for item in rocky_tiles():
        yield item["key"], item["kind"], item["category"], item["asset"]


@functools.cache
def winter_tiles():
    path = MAP_ASSETS / WINTER_DIR / WINTER_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def winter_tile_specs():
    return {item["key"]: item for item in winter_tiles()}


@functools.cache
def undead_tiles():
    path = MAP_ASSETS / UNDEAD_DIR / UNDEAD_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def undead_tile_specs():
    return {item["key"]: item for item in undead_tiles()}


@functools.cache
def undead_animations():
    path = MAP_ASSETS / UNDEAD_DIR / "animations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@functools.cache
def undead_animated_groups():
    path = MAP_ASSETS / UNDEAD_DIR / UNDEAD_CATALOG_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("animated_groups", [])


@functools.cache
def desert_tiles():
    path = MAP_ASSETS / DESERT_DIR / DESERT_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def desert_tile_specs():
    return {item["key"]: item for item in desert_tiles()}


@functools.cache
def desert_animations():
    path = MAP_ASSETS / DESERT_DIR / "animations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@functools.cache
def desert_animated_groups():
    path = MAP_ASSETS / DESERT_DIR / DESERT_CATALOG_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("animated_groups", [])


@functools.cache
def grassland_tiles():
    path = MAP_ASSETS / GRASSLAND_DIR / GRASSLAND_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def grassland_tile_specs():
    return {item["key"]: item for item in grassland_tiles()}


@functools.cache
def grassland_animations():
    path = MAP_ASSETS / GRASSLAND_DIR / "animations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@functools.cache
def city_buildings():
    path = MAP_ASSETS / CITY_BUILDINGS_DIR / CITY_BUILDINGS_CATALOG_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []


@functools.cache
def city_building_specs():
    return {item["key"]: item for item in city_buildings()}


@functools.cache
def water_decor_keys():
    """Keys for animated water details, including sheets whose category is not marked as water."""
    water_sheets = {
        "Water_detilazation", "Water_detilazation2", "Water_under_objects",
        "water_detilazation_v2",
    }
    return frozenset(
        key
        for key, spec in {
            **rocky_tile_specs(), **winter_tile_specs(), **undead_tile_specs(),
            **desert_tile_specs(), **grassland_tile_specs(),
        }.items()
        if (
            spec.get("sheet") in water_sheets
            and (
                spec.get("layer") == "overlay"
                or spec.get("sheet") == "water_detilazation_v2"
            )
        ) or spec.get("water_decor", False)
    )


@functools.cache
def water_decor_requires_water_keys():
    """Overlay animation keys that require a water base; standalone water tiles are excluded."""
    water_sheets = {"Water_detilazation2", "Water_under_objects", "water_detilazation_v2"}
    return frozenset(
        key
        for key, spec in {
            **rocky_tile_specs(), **winter_tile_specs(), **undead_tile_specs(),
            **desert_tile_specs(), **grassland_tile_specs(),
        }.items()
        if (
            spec.get("layer") == "overlay" and spec.get("sheet") in water_sheets
        ) or spec.get("requires_water", False)
    )


@functools.cache
def winter_animations():
    path = MAP_ASSETS / WINTER_DIR / "animations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@functools.cache
def winter_animated_groups():
    """Whole-cell compositions for adjacent animated winter water tiles."""
    path = MAP_ASSETS / WINTER_DIR / WINTER_CATALOG_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("animated_groups", [])


def _winter_entries():
    for item in winter_tiles():
        yield item["key"], item["kind"], item["category"], item["asset"]


def _undead_entries():
    for item in undead_tiles():
        yield item["key"], item["kind"], item["category"], item["asset"]


def _desert_entries():
    for item in desert_tiles():
        yield item["key"], item["kind"], item["category"], item["asset"]


def _grassland_entries():
    for item in grassland_tiles():
        yield item["key"], item["kind"], item["category"], item["asset"]


def _city_building_entries():
    for item in city_buildings():
        yield item["key"], item["kind"], item["category"], item["asset"]


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
def road_keys():
    """Дорожные тайлы земли: редактор ставит их слоем overlay, чтобы дорога не стирала траву под собой."""
    return frozenset(
        item["item_key"]
        for item in catalog_definitions()
        if item["kind"] == "ground" and item["category"] == "road"
    )


@functools.cache
def overlay_keys():
    """Тайлы overlay поверх земли: прозрачные тайлы из файла, дороги и импортированные биомы."""
    rocky_overlay = {
        item["key"] for item in rocky_tiles()
        if item["layer"] == "overlay"
    }
    winter_overlay = {
        item["key"] for item in winter_tiles()
        if item["layer"] == "overlay"
    }
    undead_overlay = {
        item["key"] for item in undead_tiles()
        if item["layer"] == "overlay"
    }
    desert_overlay = {
        item["key"] for item in desert_tiles()
        if item["layer"] == "overlay"
    }
    grassland_overlay = {
        item["key"] for item in grassland_tiles()
        if item["layer"] == "overlay"
    }
    return (
        frozenset(json.loads((MAP_ASSETS / OVERLAY_FILE).read_text(encoding="utf-8")))
        | road_keys() | rocky_overlay | winter_overlay | undead_overlay | desert_overlay
        | grassland_overlay
    )



@functools.cache
def palette_groups():
    """Образцы художника: разделы палитры, где тайлы лежат в заданной раскладке (x, y) одним блоком."""
    return json.loads((MAP_ASSETS / PALETTE_GROUPS_FILE).read_text(encoding="utf-8"))


@functools.cache
def infrastructure_keys():
    """Тайлы раздела «Инфраструктура»: редактор ставит их слоем infra поверх земли и прозрачных тайлов, не стирая их."""
    return frozenset(
        cell["key"]
        for group in palette_groups()
        if group["title"] == INFRASTRUCTURE_GROUP
        for cell in group["cells"]
    )


@functools.cache
def terrain_layer_keys():
    """Ключи возвышенностей и рельефа из образцов палитры, отдельно от подложки земли."""
    result = {"elevation": set(), "relief": set()}
    for group in palette_groups():
        for layer in palette_group_layers(group):
            if layer["role"] == "elevation":
                result["elevation"].update(layer["cells"].values())
            elif layer["role"] in ("river", "mountain"):
                result["relief"].update(layer["cells"].values())
    return {layer: frozenset(keys) for layer, keys in result.items()}


@functools.cache
def palette_role_keys(role):
    """Ключи тайлов, расположенные в роли образца палитры."""
    return frozenset(
        key
        for group in palette_groups()
        for layer in palette_group_layers(group)
        if layer["role"] == role
        for key in layer["cells"].values()
    )


@functools.cache
def palette_storage_layer_keys(storage_layer):
    """Ключи палитры, у которых заданная роль хранится в указанном слое карты."""
    return frozenset(
        key
        for group in palette_groups()
        for layer in palette_group_layers(group)
        if storage_layer_for_palette_role(layer["role"]) == storage_layer
        for key in layer["cells"].values()
    )


@functools.cache
def terrain_layer_for_key(key):
    """Слой возвышенности или рельефа для тайла из соответствующего блока палитры."""
    for layer, keys in terrain_layer_keys().items():
        if key in keys:
            return layer
    return None


def storage_layer_for_palette_role(role):
    """Слой карты для роли тайла в образце палитры."""
    if role in ("elevation",):
        return "elevation"
    if role in ("overlay", "infra"):
        return role
    if role in ("river", "mountain"):
        return "relief"
    if role in ("ground", "grass", "ground_decor", "grass_decor", "ground_small", "grass_small"):
        return "ground"
    return None


@functools.cache
def bridge_stamps():
    """Шаблоны мостов из раздела «Инфраструктура» как {(dx, dy): ключ}: вертикальный (настил 2 клетки по x, 4×7) и горизонтальный (настил 2 клетки по y, 5×4)."""
    group = next(group for group in palette_groups() if group["title"] == INFRASTRUCTURE_GROUP)
    grid = {(cell["x"], cell["y"]): cell["key"] for cell in group["cells"]}
    vertical = {(x, y): grid[(x, y)] for x in range(4) for y in range(7) if (x, y) in grid}
    horizontal = {(x - 2, y - 7): grid[(x, y)] for x in range(2, 7) for y in range(7, 11) if (x, y) in grid}
    horizontal.setdefault((4, 1), horizontal[(3, 1)])
    return vertical, horizontal


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
    """Ключи повторных и не выбранных для палитры тайлов: палитра их не показывает.

    В каталоге и в базе они остаются, поэтому старые карты и черновики с ними открываются как раньше.
    """
    used = {cell["key"] for group in palette_groups() for cell in group["cells"]}
    used.update(rocky_tile_specs())
    used.update(winter_tile_specs())
    used.update(undead_tile_specs())
    used.update(desert_tile_specs())
    hidden_rocky = {
        item["key"]
        for item in rocky_tiles()
        if item.get("palette_hidden", False)
    }
    hidden_winter = {
        item["key"]
        for item in winter_tiles()
        if item.get("palette_hidden", False)
    }
    hidden_undead = {
        item["key"]
        for item in undead_tiles()
        if item.get("palette_hidden", False)
    }
    hidden_desert = {
        item["key"]
        for item in desert_tiles()
        if item.get("palette_hidden", False)
    }
    return frozenset(
        item["item_key"]
        for item in (catalog_definitions() if catalog is None else catalog)
        if (
            item["item_key"] in hidden_rocky
            or item["item_key"] in hidden_winter
            or item["item_key"] in hidden_undead
            or item["item_key"] in hidden_desert
            or (
                item["kind"] == "ground"
                and item["category"] in HIDDEN_CATEGORIES
                and item["item_key"] not in used
            )
        )
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
    yield from _bush_entries()
    yield from _animal_entries()
    yield from _rocky_entries()
    yield from _winter_entries()
    yield from _undead_entries()
    yield from _desert_entries()
    yield from _grassland_entries()
    yield from _city_building_entries()
    yield from _mainlev_entries()
    yield from _crystal_entries()


def catalog_definitions():
    """Список записей каталога для синхронизации с базой."""
    impassable = _impassable_keys()
    passable = _passable_keys()
    biome_specs = {
        **rocky_tile_specs(), **winter_tile_specs(), **undead_tile_specs(),
        **desert_tile_specs(), **grassland_tile_specs(), **city_building_specs(),
    }
    result = []
    for order, (key, kind, category, asset) in enumerate(_entries(), start=1):
        spec = biome_specs.get(key)
        rocky_elevation = (
            key.startswith("rocky_")
            and spec is not None
            and spec.get("layer") == "elevation"
            and category != "bush"
            and not (
                spec.get("sheet") == "Ground_moss"
                and spec.get("tile_id") in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
            )
        )
        desert_elevation = (
            key.startswith("desert_")
            and spec is not None
            and spec.get("layer") == "elevation"
            and category != "bush"
        )
        item = {
            "item_key": key,
            "kind": kind,
            "category": category,
            "asset": asset,
            "footprint_w": int(spec.get("footprint_w", 1)) if spec is not None else 1,
            "footprint_h": int(spec.get("footprint_h", 1)) if spec is not None else 1,
            "blocks": key in impassable
            or bool(spec and spec.get("blocks"))
            or (
                key not in passable
                and (category in BLOCKING_CATEGORIES or rocky_elevation or desert_elevation)
            ),
            "sort_order": order,
        }
        item["editor_layer"] = (
            int(spec["editor_layer"])
            if spec is not None and spec.get("editor_layer") is not None
            else _default_editor_layer(key, kind, category, spec or {})
        )
        if spec is not None:
            for name in (
                "display_name",
                "representation",
                "growth_series",
                "growth_stage",
                "growth_size",
                "render_offset_tiles",
            ):
                if name in spec:
                    item[name] = spec[name]
        result.append(item)
    return result


def _default_editor_layer(key, kind, category, spec):
    """Artist-facing layer number; separate from the map's internal storage layer."""
    sheet = spec.get("sheet")
    if category == "animal":
        return 8
    if key in water_decor_keys():
        return 2
    if kind == "object":
        return 6 if category in ("building", "bridge", "house", "structure") else 7
    if sheet == "Waterfalls":
        return 5
    if (
        sheet == "Ground_moss"
        and spec.get("tile_id") in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
    ):
        return 3
    if key in infrastructure_keys():
        return 6
    layer = spec.get("layer") or terrain_layer_for_key(key)
    if layer == "overlay":
        return 2 if category == "water" else 4
    if category == "water":
        return 1
    if category == "grass":
        return 3
    if layer in ("elevation", "relief"):
        return 5
    if layer == "infra":
        return 6
    if category == "road":
        return 3
    return 3
