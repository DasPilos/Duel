"""Черновик редактора из опубликованной карты мира: клетки повторяют тайлы, которые видит игрок на сервере.

Сервер отдаёт рельеф наборами тайлов по категориям каталога (kaloda/server/map_editor.py, terrain_from_cells),
поэтому клетки обратно берутся из каталога по тем же категориям. Ключей Оператора 1 здесь нет: их в каталоге Колоды нет.
Мостов в каталоге Колоды тоже нет, поэтому мосты сервера в черновик не попадают.
"""

# Категории наборов тайлов рельефа сервера: вода, дорога, пол, горы — земля; лес и сухой лес — деревья
GROUND_TILE_SETS = (("water", "water"), ("paths", "road"), ("floor", "floor"), ("mountain", "rock"))
GRASS_CATEGORY = "grass"
TREE_CATEGORY = "tree"
DRY_CATEGORY = "old_tree"
PROP_CATEGORIES = ("stump", "log")


def decode_tiles(rows):
    """Строки [y, x_начало, x_конец] с сервера превращаются в множество тайлов (x, y)."""
    return {(x, y) for y, x_start, x_end in rows for x in range(x_start, x_end + 1)}


def _pick(keys, x, y):
    """Вариант тайла по координате: одна и та же карта получается при каждом сиде."""
    return keys[(x * 73856093 ^ y * 19349663) % len(keys)]


def _pools(items):
    """Ключи каталога по виду и категории, по порядку item_key: {вид: {категория: [ключи]}}.

    Для травы берутся тайлы без блокировки, чтобы земля под травой не стояла стеной.
    """
    pools = {"ground": {}, "object": {}}
    for item in sorted(items.values(), key=lambda entry: entry["item_key"]):
        if item["kind"] == "ground" and item["category"] == GRASS_CATEGORY and item.get("blocks"):
            continue
        pools[item["kind"]].setdefault(item["category"], []).append(item["item_key"])
    return pools


def build_world_seed_cells(terrain, items, map_w, map_h):
    """Клетки черновика из ответа /api/kaloda/map/terrain (опубликованная карта мира).

    items — каталог редактора по item_key. Если в ответе нет наборов тайлов, карта мира не опубликована.
    """
    tiles = terrain["tiles"]
    tile_sets = {name: decode_tiles(tiles.get(name, [])) for name in ("water", "paths", "floor", "mountain", "forest", "dry")}
    pools = _pools(items)

    ground = []
    for y in range(map_h):
        for x in range(map_w):
            category = GRASS_CATEGORY
            for tile_set, ground_category in GROUND_TILE_SETS:
                if (x, y) in tile_sets[tile_set]:
                    category = ground_category
                    break
            key = _pick(pools["ground"][category], x, y)
            ground.append({"layer": "ground", "x": x, "y": y, "key": key})

    covered = set()
    objects = []

    def put(category, x, y):
        keys = pools["object"].get(category)
        if not keys:
            return
        item = items[_pick(keys, x, y)]
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        for tile_x, tile_y in footprint:
            if not (0 <= tile_x < map_w and 0 <= tile_y < map_h) or (tile_x, tile_y) in covered:
                return
        covered.update(footprint)
        objects.append({"layer": "object", "x": x, "y": y, "key": item["item_key"]})

    for prop in terrain.get("props", []):
        if prop["type"] in PROP_CATEGORIES:
            x, y = min(tuple(tile) for tile in prop["tiles"])
            put(prop["type"], x, y)

    for tile in sorted(tile_sets["forest"]):
        put(TREE_CATEGORY, *tile)
    # Сухой лес заблокирован на сервере, поэтому в редакторе это сухие деревья, а не пустая земля.
    for tile in sorted(tile_sets["dry"]):
        put(DRY_CATEGORY, *tile)

    return ground + objects
