"""Generate a 256×256 base-mode map with broad grassland, rocky, and winter regions."""
import argparse
import math
import random
from collections import Counter, deque
from functools import lru_cache

from PIL import Image, ImageStat

from client import map_drafts
from core.map_catalog import (
    MAP_ASSETS,
    bridge_stamps,
    catalog_definitions,
    grassland_tile_specs,
    rocky_tile_specs,
    winter_tile_specs,
)
from core.tiled_bridge import DEFAULT_MODE
from server.map_editor import terrain_from_cells, validate_cells

SIZE = 256
SEED = 23
DEFAULT_NAME = "Тестовая база 256"
TILE_SIZE = 32
CITY_CENTRE = (SIZE // 2, SIZE // 2)
BIOME_ANCHORS = {
    "grassland": (42, 190),
    "rocky": (232, 188),
    "winter": (114, -42),
}
BIOME_COLOURS = {
    "grassland": (160, 170, 85),
    "rocky": (174, 164, 136),
    "winter": (176, 198, 208),
}


def _hash(ix, iy, seed, salt):
    value = (ix * 374761393 + iy * 668265263 + seed * 1442695041 + salt * 1013904223) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF


def _fade(value):
    return value * value * (3 - 2 * value)


def _noise(x, y, scale, seed, salt):
    gx, gy = x / scale, y / scale
    ix, iy = math.floor(gx), math.floor(gy)
    fx, fy = _fade(gx - ix), _fade(gy - iy)
    top = _hash(ix, iy, seed, salt) * (1 - fx) + _hash(ix + 1, iy, seed, salt) * fx
    bottom = _hash(ix, iy + 1, seed, salt) * (1 - fx) + _hash(ix + 1, iy + 1, seed, salt) * fx
    return top * (1 - fy) + bottom * fy


@lru_cache(maxsize=4096)
def _tile_profile(asset, tile_id, columns):
    path = MAP_ASSETS / asset
    with Image.open(path) as source:
        image = source.convert("RGBA")
        tile_size = image.width // columns
        x, y = tile_id % columns * tile_size, tile_id // columns * tile_size
        tile = image.crop((x, y, x + tile_size, y + tile_size))
    alpha_counts = tile.getchannel("A").histogram()
    opaque_pixels = sum(alpha_counts[128:])
    if not tile.width or not tile.height or opaque_pixels < tile.width * tile.height * 0.96:
        return None
    return tuple(round(channel) for channel in ImageStat.Stat(
        tile.convert("RGB"),
        tile.getchannel("A"),
    ).mean)


def _terrain_candidates(catalog, specs, category=None):
    items = {item["item_key"]: item for item in catalog}
    profiles = {}
    for key, spec in specs.items():
        if spec.get("layer") != "ground" or key not in items or items[key]["kind"] != "ground":
            continue
        if category and items[key]["category"] != category:
            continue
        tile_id, columns = spec.get("tile_id"), spec.get("columns")
        if tile_id is None or columns is None:
            continue
        colour = _tile_profile(spec["asset"], int(tile_id), int(columns))
        if colour is not None:
            profiles[key] = colour
    return profiles


def _closest_keys(profiles, target, count=18):
    if not profiles:
        raise ValueError(f"No opaque terrain tiles found near colour {target}")
    return [
        key
        for key, _colour in sorted(
            profiles.items(),
            key=lambda entry: (math.dist(entry[1], target), entry[0]),
        )[:count]
    ]


def _biome_at(x, y, seed):
    scores = {}
    for index, (name, (anchor_x, anchor_y)) in enumerate(BIOME_ANCHORS.items()):
        distance = math.hypot(x - anchor_x, y - anchor_y)
        broad_shape = (_noise(x, y, 34, seed, 20 + index) - 0.5) * 32
        scores[name] = distance + broad_shape
    nearest = min(scores.values())
    weights = {
        name: math.exp(-(score - nearest) / 28)
        for name, score in scores.items()
    }
    total = sum(weights.values())
    selector = _noise(x, y, 11, seed, 37) * total
    for name in BIOME_ANCHORS:
        selector -= weights[name]
        if selector <= 0:
            return name, sorted(weights.values(), reverse=True)[1] / total
    return "winter", sorted(weights.values(), reverse=True)[1] / total


def _path_between(start, end):
    x0, y0 = start
    x1, y1 = end
    if x0 == x1:
        return {(x0, y) for y in range(min(y0, y1), max(y0, y1) + 1)}
    if y0 == y1:
        return {(x, y0) for x in range(min(x0, x1), max(x0, x1) + 1)}
    raise ValueError("City access paths must be axis-aligned")


def _zone_map(seed):
    zones = {}
    transition_cells = 0
    for y in range(SIZE):
        for x in range(SIZE):
            name, second_weight = _biome_at(x, y, seed)
            if math.hypot(x - CITY_CENTRE[0], y - CITY_CENTRE[1]) <= 36:
                name = "grassland"
            zones[x, y] = name
            transition_cells += second_weight > 0.25
    return zones, transition_cells


def _river_cells():
    river = set()
    for x in range(SIZE):
        centre_y = round(76 + 4 * math.sin(x / 28) + 2 * math.sin(x / 11))
        river.update((x, centre_y + dy) for dy in (-1, 0, 1))
    for y in range(76, 216):
        centre_x = round(194 + 4 * math.sin(y / 31) + 2 * math.sin(y / 13))
        river.update((centre_x + dx, y) for dx in (-1, 0, 1))
    return river


def _roads_and_bridges(seed):
    centre_x, centre_y = CITY_CENTRE

    def road_offset(position, centre, salt):
        distance = abs(position - centre)
        envelope = _fade(max(0, min(1, (distance - 22) / 80)))
        return round((4 * math.sin(position / 39) + 2 * math.sin(position / 17 + salt)) * envelope)

    def vertical_centre(y):
        return centre_x + road_offset(y, centre_y, 0)

    def horizontal_centre(x):
        return centre_y + road_offset(x, centre_x, 1)

    roads = set()
    for y in range(SIZE):
        path_x = vertical_centre(y)
        roads.update((path_x + dx, y) for dx in (-1, 0, 1))
    for x in range(SIZE):
        path_y = horizontal_centre(x)
        roads.update((x, path_y + dy) for dy in (-1, 0, 1))
    roads.update(
        (x, y)
        for x in range(centre_x - 7, centre_x + 8)
        for y in range(centre_y - 7, centre_y + 8)
    )

    access_paths = (
        ((104, 114), (104, 127)),
        ((148, 108), (148, 127)),
        ((157, 123), (157, 127)),
        ((157, 129), (157, 135)),
        ((148, 129), (148, 150)),
        ((120, 129), (120, 151)),
        ((103, 129), (103, 135)),
        ((97, 120), (127, 120)),
    )
    for start, end in access_paths:
        roads.update(_path_between(start, end))

    vertical, horizontal = bridge_stamps()
    bridge_x = vertical_centre(76)
    bridge_y = round(76 + 4 * math.sin(bridge_x / 28) + 2 * math.sin(bridge_x / 11))
    vertical_bridge = {
        (bridge_x - 2 + dx, bridge_y - 1 + dy): key
        for (dx, dy), key in vertical.items()
    }
    river_x = round(194 + 4 * math.sin(centre_y / 31) + 2 * math.sin(centre_y / 13))
    bridge_y = horizontal_centre(river_x)
    horizontal_bridge = {
        (river_x + dx, bridge_y - 2 + dy): key
        for (dx, dy), key in horizontal.items()
    }
    bridges = {**vertical_bridge, **horizontal_bridge}
    return roads, bridges


def _city_buildings(catalog):
    specs = {
        item["item_key"]: item
        for item in catalog
        if item["item_key"].startswith("city_building_")
    }
    positions = {
        "city_building_market": (93, 98),
        "city_building_tavern": (142, 96),
        "city_building_smithy": (158, 110),
        "city_building_glassblower": (158, 136),
        "city_building_herbalist": (142, 151),
        "city_building_library": (117, 152),
        "city_building_mage_tower": (96, 136),
        "city_building_guild": (87, 116),
    }
    if set(positions) - specs.keys():
        raise ValueError("City building assets are missing from the map catalog")
    return {
        (x, y): key
        for key, (x, y) in positions.items()
    }


def _object_candidates(catalog):
    trees = [
        item["item_key"]
        for item in catalog
        if item["kind"] == "object"
        and item["category"] in {"tree", "old_tree"}
        and item["footprint_w"] == item["footprint_h"] == 1
    ]
    bushes = {
        "grassland": [],
        "rocky": [],
        "winter": [],
    }
    for item in catalog:
        if item["kind"] != "object" or item["category"] != "bush":
            continue
        key = item["item_key"]
        for biome in bushes:
            if key.startswith(f"{biome}_") and item["footprint_w"] == item["footprint_h"] == 1:
                bushes[biome].append(key)
    if not trees:
        raise ValueError("No one-cell tree sprites are available in the map catalog")
    return trees, bushes


def generate(size=SIZE, seed=SEED):
    if size != SIZE:
        raise ValueError(f"This base-map layout is designed for {SIZE}×{SIZE} cells")
    randomizer = random.Random(seed)
    catalog = catalog_definitions()
    grassland = _terrain_candidates(catalog, grassland_tile_specs())
    rocky = _terrain_candidates(catalog, rocky_tile_specs())
    winter = _terrain_candidates(catalog, winter_tile_specs())
    ground_keys = {
        "grassland": _closest_keys(grassland, BIOME_COLOURS["grassland"]),
        "rocky": _closest_keys(rocky, BIOME_COLOURS["rocky"]),
        "winter": _closest_keys(winter, BIOME_COLOURS["winter"]),
    }
    roads_keys = _closest_keys(grassland, (145, 98, 64), 12)

    all_biome_specs = {
        **grassland_tile_specs(),
        **rocky_tile_specs(),
        **winter_tile_specs(),
    }
    water_specs = {
        key: colour
        for key, colour in _terrain_candidates(catalog, all_biome_specs, category="water").items()
        if colour[1] - colour[0] > 35 and colour[2] - colour[0] > 35
    }
    if not water_specs:
        raise ValueError("No opaque water tiles are available for the river")
    water_keys = _closest_keys(water_specs, (70, 145, 160), 12)

    zones, transition_cells = _zone_map(seed)
    river = _river_cells()
    roads, bridges = _roads_and_bridges(seed)
    city = _city_buildings(catalog)
    city_cells = set()
    catalog_by_key = {item["item_key"]: item for item in catalog}
    for (x, y), key in city.items():
        item = catalog_by_key[key]
        city_cells.update(
            (x + dx, y + dy)
            for dx in range(item["footprint_w"])
            for dy in range(item["footprint_h"])
        )
    safe_city = {
        (x, y)
        for x in range(82, 176)
        for y in range(90, 166)
    }
    all_paths = roads
    ground = {}
    for y in range(SIZE):
        for x in range(SIZE):
            cell = (x, y)
            if cell in river:
                ground[cell] = randomizer.choice(water_keys)
            elif cell in all_paths:
                ground[cell] = randomizer.choice(roads_keys)
            else:
                biome = zones[cell]
                ground[cell] = randomizer.choice(ground_keys[biome])

    objects = dict(city)
    reserved = set(city_cells)
    tree_keys, bush_keys = _object_candidates(catalog)
    for y in range(SIZE):
        for x in range(SIZE):
            cell = (x, y)
            if (
                cell in all_paths
                or cell in river
                or cell in bridges
                or cell in safe_city
                or any((x + dx, y + dy) in reserved for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            ):
                continue
            biome = zones[cell]
            local_density = 0.006 + 0.035 * _noise(x, y, 34, seed, 53)
            if randomizer.random() >= local_density:
                continue
            nearby = bush_keys[biome]
            if biome == "winter" and nearby:
                key = randomizer.choice(nearby)
            elif nearby and randomizer.random() < 0.45:
                key = randomizer.choice(nearby)
            else:
                key = randomizer.choice(tree_keys)
            objects[cell] = key
            reserved.add(cell)

    cells = [
        {"layer": "ground", "x": x, "y": y, "key": key}
        for (x, y), key in sorted(ground.items(), key=lambda entry: (entry[0][1], entry[0][0]))
    ]
    cells.extend(
        {"layer": "infra", "x": x, "y": y, "key": key}
        for (x, y), key in sorted(bridges.items(), key=lambda entry: (entry[0][1], entry[0][0]))
    )
    cells.extend(
        {"layer": "object", "x": x, "y": y, "key": key}
        for (x, y), key in sorted(objects.items(), key=lambda entry: (entry[0][1], entry[0][0]))
    )

    validate_cells(cells, catalog, size, size)
    terrain = terrain_from_cells(cells, catalog)
    blocked = set(terrain["impassable"]) | set(terrain["water"]) | set(terrain["dry"])
    start = CITY_CENTRE
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for next_cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            nx, ny = next_cell
            if 0 <= nx < size and 0 <= ny < size and next_cell not in blocked and next_cell not in seen:
                seen.add(next_cell)
                queue.append(next_cell)
    exits = {
        "north": (size // 2, 0),
        "south": (size // 2, size - 1),
        "west": (0, size // 2),
        "east": (size - 1, size // 2),
    }
    reachable = {
        name: any(
            (x + dx, y + dy) in seen
            for dx in range(-2, 3)
            for dy in range(-2, 3)
        )
        for name, (x, y) in exits.items()
    }
    if not all(reachable.values()):
        raise ValueError(f"City roads are not reachable from all map edges: {reachable}")
    stats = {
        "biome_cells": dict(Counter(zones.values())),
        "transition_cells": transition_cells,
        "road_cells": len(roads),
        "river_cells": len(river),
        "bridge_cells": len(bridges),
        "city_buildings": len(city),
        "decor_objects": len(objects) - len(city),
        "road_exits_reachable_from_city": reachable,
        "reachable_cells": len(seen),
    }
    return cells, stats


def save(cells, name=DEFAULT_NAME, size=SIZE):
    existing = next(
        (draft for draft in map_drafts.list_drafts() if draft["name"] == name),
        None,
    )
    return map_drafts.save_draft(
        name,
        cells,
        size,
        size,
        draft_id=existing["id"] if existing else None,
        mode=DEFAULT_MODE,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    cells, stats = generate(seed=args.seed)
    draft = save(cells, args.name)
    print(f"Draft: {draft['name']} ({draft['map_w']}x{draft['map_h']}, {len(cells)} cells)")
    for name, value in stats.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
