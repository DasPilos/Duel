"""Черновик редактора из карты башни: клетки повторяют тайлы, которые видит игрок на сервере.

Земля и трава — слой 1, дороги — слой 2, мосты — слой инфраструктуры, деревья и пни — объекты. Тайлы берутся из каталога
по категориям и только полные (без прозрачного края), чтобы дорога не стирала то, что под ней.
"""
from core.map_catalog import bridge_stamps, overlay_keys, palette_role_keys
from core.terrain_autotile import is_full, is_teal, tile_shape


def decode_tiles(rows):
    """Строки [y, x_начало, x_конец] с сервера превращаются в множество тайлов (x, y)."""
    return {(x, y) for y, x_start, x_end in rows for x in range(x_start, x_end + 1)}


def _pick(keys, x, y):
    """Вариант тайла по координате: одна и та же карта получается при каждом сиде."""
    return keys[(x * 73856093 ^ y * 19349663) % len(keys)]


def _pool(items, kind, category, keep=None, exclude=()):
    """Ключи категории в порядке сортировки: одинаковый каталог даёт одинаковую карту."""
    return sorted(
        key for key, item in items.items()
        if (
            item["kind"] == kind and item["category"] == category
            and key not in exclude and (keep is None or keep(item["asset"]))
        )
    )


def _full(asset):
    return is_full(tile_shape(asset)[0])


def _clean_water(asset):
    coverage, colour = tile_shape(asset)
    return is_full(coverage) and is_teal(colour)


def _pools(items):
    mountain_keys = palette_role_keys("mountain") | overlay_keys()
    return {
        "grass": _pool(items, "ground", "grass", _full, mountain_keys),
        "water": _pool(items, "ground", "water", _clean_water, mountain_keys),
        "road": _pool(items, "ground", "road", _full),
        "rock": _pool(items, "ground", "rock", _full),
        "tree": _pool(items, "object", "tree"),
        "old_tree": _pool(items, "object", "old_tree"),
        "stump": _pool(items, "object", "stump"),
        "log": _pool(items, "object", "log"),
    }


def build_tower_seed_cells(terrain, items, map_w, map_h):
    """Клетки черновика из ответа /api/map/terrain. items — каталог редактора по item_key."""

    def inside(tile):
        return 0 <= tile[0] < map_w and 0 <= tile[1] < map_h

    def read(name):
        return {tile for tile in decode_tiles(terrain["tiles"].get(name, [])) if inside(tile)}

    water, paths, forest, dry, mountain = read("water"), read("paths"), read("forest"), read("dry"), read("mountain")
    pools = _pools(items)
    vertical, horizontal = bridge_stamps()
    ground, overlay, relief, infra, objects = {}, {}, {}, {}, {}

    for y in range(map_h):
        for x in range(map_w):
            pool = pools["water"] if (x, y) in water else pools["grass"]
            ground[(x, y)] = _pick(pool, x, y)
    for x, y in mountain:
        relief[(x, y)] = _pick(pools["rock"], x, y)
    for x, y in paths:
        overlay[(x, y)] = _pick(pools["road"], x, y)

    # Мосты первыми: деревья и пни на них не ставятся. Шаблон выбирается по форме пролёта, центрируется на нём.
    bridge_tiles = set()
    for bridge in terrain.get("bridges", []):
        run = [tuple(tile) for tile in bridge["tiles"]]
        min_x = min(x for x, _ in run)
        min_y = min(y for _, y in run)
        width = max(x for x, _ in run) - min_x + 1
        height = max(y for _, y in run) - min_y + 1
        stamp = vertical if height >= width else horizontal
        stamp_w = max(dx for dx, _ in stamp) + 1
        stamp_h = max(dy for _, dy in stamp) + 1
        left = min_x + (width - stamp_w) // 2
        top = min_y + (height - stamp_h) // 2
        for (dx, dy), key in stamp.items():
            tile = (left + dx, top + dy)
            if inside(tile):
                infra[tile] = key
                bridge_tiles.add(tile)

    blocked = water | mountain | paths | bridge_tiles

    def place(pool, x, y):
        if (x, y) not in blocked and (x, y) not in objects:
            objects[(x, y)] = _pick(pool, x, y)

    for prop in terrain.get("props", []):
        x, y = min(tuple(tile) for tile in prop["tiles"])
        if prop["type"] == "stump":
            place(pools["stump"], x, y)
        elif prop["type"] == "log":
            place(pools["log"], x, y)

    for x, y in sorted(forest):
        place(pools["tree"], x, y)
    # Сухой лес заблокирован на сервере, поэтому в редакторе это мёртвые деревья, а не пустая земля.
    for x, y in sorted(dry):
        place(pools["old_tree"], x, y)

    cells = []
    for layer, layer_cells in (
        ("ground", ground), ("overlay", overlay), ("relief", relief), ("infra", infra), ("object", objects),
    ):
        cells.extend({"layer": layer, "x": x, "y": y, "key": key} for (x, y), key in sorted(layer_cells.items()))
    return cells
