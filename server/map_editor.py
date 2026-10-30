"""Проверка карт редактора перед публикацией и рельеф опубликованной карты мира."""
from core.map_catalog import DEFAULT_MAP_SIZE, MAP_SIZE_MAX, MAP_SIZE_MIN, catalog_definitions
from core.npc_catalog import NPC_CATALOG
from core.tile_mask import load_partial_masks

LAYERS = ("ground", "overlay", "object")


def check_map_size(map_w, map_h):
    """Размер карты в тайлах: целые числа от MAP_SIZE_MIN до MAP_SIZE_MAX."""
    for side in (map_w, map_h):
        if not isinstance(side, int) or isinstance(side, bool) or not MAP_SIZE_MIN <= side <= MAP_SIZE_MAX:
            raise ValueError(f"Размер карты: от {MAP_SIZE_MIN} до {MAP_SIZE_MAX} тайлов по каждой стороне")
    return map_w, map_h


def validate_cells(cells, catalog, map_w, map_h):
    """Проверяет клетки карты и возвращает их в виде кортежей для записи в базу.

    Слои ground и overlay: по одной клетке на тайл, в обоих лежат тайлы земли;
    overlay рисуется поверх ground. Слой object: занятые клетки объектов
    не должны пересекаться и не выходить за край карты.
    """
    if not isinstance(cells, list):
        raise ValueError("Карта должна быть списком клеток")
    by_key = {item["item_key"]: item for item in catalog}
    anchors = set()
    occupied = set()
    result = []
    for cell in cells:
        layer = str(cell.get("layer", ""))
        key = str(cell.get("key", ""))
        x, y = int(cell.get("x", -1)), int(cell.get("y", -1))
        item = by_key.get(key)
        if item is None:
            raise ValueError(f"Элемента «{key}» нет в каталоге")
        if layer not in LAYERS or item["kind"] != ("ground" if layer == "overlay" else layer):
            raise ValueError(f"Элемент «{key}» нельзя ставить на слой «{layer}»")
        if (layer, x, y) in anchors:
            raise ValueError(f"Клетка ({x}, {y}) уже занята на слое «{layer}»")
        anchors.add((layer, x, y))
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        for fx, fy in footprint:
            if not (0 <= fx < map_w and 0 <= fy < map_h):
                raise ValueError(f"Элемент «{key}» выходит за край карты")
        if layer == "object":
            if any(tile in occupied for tile in footprint):
                raise ValueError(f"Элемент «{key}» в ({x}, {y}) пересекается с другим объектом")
            occupied.update(footprint)
        result.append((layer, x, y, key))
    return result


def validate_mobs(mobs, map_w, map_h):
    """Расстановка NPC: список (вид, x, y) для записи в базу. Вид — из каталога NPC, один NPC на клетку, клетка внутри карты."""
    if mobs is None:
        return []
    if not isinstance(mobs, list):
        raise ValueError("NPC должны быть списком")
    kinds = {npc["key"] for npc in NPC_CATALOG}
    result, taken = [], set()
    for mob in mobs:
        if not isinstance(mob, dict):
            raise ValueError("Каждый NPC — объект с полями kind, x, y")
        kind = str(mob.get("kind", ""))
        x, y = int(mob.get("x", -1)), int(mob.get("y", -1))
        if kind not in kinds:
            raise ValueError(f"NPC «{kind}» нет в каталоге")
        if not (0 <= x < map_w and 0 <= y < map_h):
            raise ValueError(f"NPC «{kind}» стоит за краем карты")
        if (x, y) in taken:
            raise ValueError(f"На клетке ({x}, {y}) уже стоит NPC")
        taken.add((x, y))
        result.append((kind, x, y))
    return result


def validate_spawns(spawns, map_w, map_h):
    """Точки спауна игроков: список (x, y). Клетка внутри карты, точки не повторяются."""
    if spawns is None:
        return []
    if not isinstance(spawns, list):
        raise ValueError("Точки спауна должны быть списком")
    result, taken = [], set()
    for spawn in spawns:
        if not isinstance(spawn, dict):
            raise ValueError("Каждая точка спауна — объект с полями x, y")
        x, y = int(spawn.get("x", -1)), int(spawn.get("y", -1))
        if not (0 <= x < map_w and 0 <= y < map_h):
            raise ValueError(f"Точка спауна ({x}, {y}) за краем карты")
        if (x, y) in taken:
            raise ValueError(f"Точка спауна ({x}, {y}) задана дважды")
        taken.add((x, y))
        result.append((x, y))
    return result


def terrain_from_cells(cells, catalog, masks=None):
    """Переводит клетки карты в наборы тайлов для рельефа; None, если клеток нет.

    Ягоды и пол не ставятся на воду, дорогу и мост.
    Сухой лес (old_tree) попадает в dry и блокирует ход.
    Пни, брёвна и мосты передаются списками объектов.
    Блокирующие тайлы каталога (blocks) попадают в impassable, кроме мостов.
    Элемент с маской (masks: ключ → маска 4×4) не блокирует тайл целиком: его проходимость задаёт маска.
    Тайл с блокирующим объектом без маски остаётся непроходимым целиком.
    """
    masks = masks or {}
    if not cells:
        return None
    # Тайл overlay (например, мост) заменяет проходимость земли под собой.
    overlay_tiles = {(cell["x"], cell["y"]) for cell in cells if cell["layer"] == "overlay"}
    by_key = {item["item_key"]: item for item in catalog}
    water, paths, forest, dry, mountain = set(), set(), set(), set(), set()
    berry, floor = set(), set()
    props, bridges, bridge_tiles = [], [], set()
    impassable, solid, partial = set(), set(), {}
    for cell in cells:
        item = by_key.get(cell["key"])
        if item is None:
            continue
        x, y = cell["x"], cell["y"]
        if cell["layer"] == "ground" and (x, y) in overlay_tiles:
            continue
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        category = item["category"]
        mask = masks.get(cell["key"])
        if mask is not None:
            partial.update(dict.fromkeys(footprint, mask))
        elif item["blocks"]:
            impassable.update(footprint)
            solid.update(footprint)
        if cell["layer"] in ("ground", "overlay"):
            if category == "water":
                water.add((x, y))
            elif category == "road":
                paths.add((x, y))
            elif category == "berry":
                berry.add((x, y))
            elif category == "floor":
                floor.add((x, y))
            elif category == "rock":
                mountain.add((x, y))
        elif category == "tree":
            forest.add((x, y))
        elif category == "old_tree":
            dry.add((x, y))
        elif category == "rock":
            mountain.add((x, y))
        elif category in ("stump", "log"):
            props.append({"type": category, "tiles": [list(tile) for tile in footprint]})
        elif category == "bridge":
            bridges.append({"tiles": [list(tile) for tile in footprint]})
            bridge_tiles.update(footprint)
    ground_free = bridge_tiles | paths | water
    partial_tiles = {tile: mask for tile, mask in partial.items() if tile not in solid}
    return {
        "water": frozenset(water - bridge_tiles),
        "paths": frozenset(paths),
        "forest": frozenset(forest),
        "dry": frozenset(dry),
        "mountain": frozenset(mountain),
        "berry": frozenset(berry - ground_free),
        "floor": frozenset(floor - ground_free),
        "props": props,
        "bridges": bridges,
        "impassable": frozenset(impassable - bridge_tiles),
        "partial": partial_tiles,
    }


def load_published_map(database, published=None):
    """Опубликованная карта текущего мира: (рельеф, сведения о публикации) или (None, None), если карты нет."""
    if published is None:
        published = database.published_map()
    if published is None:
        return None, None
    return terrain_from_cells(database.map_live_cells(), database.map_catalog(), load_partial_masks()), published
