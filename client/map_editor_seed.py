"""Черновик редактора из карты башни: клетки повторяют тайлы, которые видит игрок на сервере."""

GRASS_KEYS = tuple(f"grass_{number}" for number in range(1, 6))
WATER_KEYS = tuple(f"water_{number}" for number in range(1, 4))
ROAD_KEYS = tuple(f"road_core_{number}" for number in range(1, 5))
TREE_KEYS = ("tree1", "tree2", "tree3")
DEAD_TREE_KEYS = ("old_tree1", "old_tree2", "old_tree3")
STUMP_KEYS = ("stump_1", "stump_2")
LOG_KEYS = ("log_1", "log_2")
BRIDGE_KEY = "bridge_horizontal"


def decode_tiles(rows):
    """Строки [y, x_начало, x_конец] с сервера превращаются в множество тайлов (x, y)."""
    return {(x, y) for y, x_start, x_end in rows for x in range(x_start, x_end + 1)}


def _pick(keys, x, y):
    """Вариант тайла по координате: одна и та же карта получается при каждом сиде."""
    return keys[(x * 73856093 ^ y * 19349663) % len(keys)]


def build_tower_seed_cells(terrain, items, map_w, map_h, mountain_roles):
    """Клетки черновика из ответа /api/map/terrain.

    items — каталог редактора по item_key, mountain_roles — {(x, y): имя_скалы} из build_mountain_roles.
    """
    tiles = terrain["tiles"]
    water = decode_tiles(tiles.get("water", []))
    paths = decode_tiles(tiles.get("paths", []))
    forest = decode_tiles(tiles.get("forest", []))
    dry = decode_tiles(tiles.get("dry", []))
    mountain = decode_tiles(tiles.get("mountain", []))
    covered = set()
    objects = []

    def put(key, x, y):
        item = items[key]
        footprint = [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]
        for tile_x, tile_y in footprint:
            if not (0 <= tile_x < map_w and 0 <= tile_y < map_h) or (tile_x, tile_y) in covered:
                return
        covered.update(footprint)
        objects.append({"layer": "object", "x": x, "y": y, "key": key})

    ground = []
    for y in range(map_h):
        for x in range(map_w):
            if (x, y) in water:
                key = _pick(WATER_KEYS, x, y)
            elif (x, y) in paths:
                key = _pick(ROAD_KEYS, x, y)
            else:
                key = _pick(GRASS_KEYS, x, y)
            ground.append({"layer": "ground", "x": x, "y": y, "key": key})

    # Мосты и пни идут первыми: они важнее деревьев, которые им мешают.
    for bridge in terrain.get("bridges", []):
        run = [tuple(tile) for tile in bridge["tiles"]]
        width = items[BRIDGE_KEY]["footprint_w"]
        height = items[BRIDGE_KEY]["footprint_h"]
        # Сервер рисует мост по центру пролёта, поэтому якорь — центр пролёта минус половина спрайта.
        x = (min(tile_x for tile_x, _ in run) + max(tile_x for tile_x, _ in run) + 1 - width) // 2
        y = (min(tile_y for _, tile_y in run) + max(tile_y for _, tile_y in run) + 1 - height) // 2
        put(BRIDGE_KEY, min(max(x, 0), map_w - width), min(max(y, 0), map_h - height))

    for prop in terrain.get("props", []):
        x, y = min(tuple(tile) for tile in prop["tiles"])
        if prop["type"] == "stump":
            put(_pick(STUMP_KEYS, x, y), x, y)
        elif prop["type"] == "log":
            put(_pick(LOG_KEYS, x, y), x, y)

    for tile in sorted(mountain):
        put(mountain_roles[tile], *tile)

    for tile in sorted(forest):
        put(_pick(TREE_KEYS, *tile), *tile)
    # Сухой лес заблокирован на сервере, поэтому в редакторе это мёртвые деревья, а не пустая земля.
    for tile in sorted(dry):
        put(_pick(DEAD_TREE_KEYS, *tile), *tile)

    return ground + objects
