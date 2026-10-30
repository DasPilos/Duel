"""Генератор карты «Три дороги»: три дороги сходятся в центре среди трёх возвышенностей и уходят к краям карты.

Правила карты:
  - дороги шириной 2–3 тайла сходятся в центре и выходят на карте с трёх разных сторон (север, запад, восток);
  - вокруг центра стоят три возвышенности слоя 3 (плато из блоков возвышенности образца), дороги идут между ними;
  - дороги идут через густой старый лес (огромные деревья в шахматном порядке, малые деревья, сухие участки
    с пнями) и между горными массивами слоя 4, которые стоят по обе стороны дороги;
  - через три реки дороги переходят по мостам из раздела «Инфраструктура» (на мосту дорога сужается до 2 тайлов);
  - земля и трава берутся из шаблонов «Лесного ландшафта» (сухой и живой), декор не ближе 3 клеток друг к другу.

Пример: python -m scripts.generate_crossroads_map --name "Три дороги 96"
"""
import argparse
import math
import os
import random
from collections import Counter, deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from client import map_drafts
from core.map_catalog import (
    catalog_definitions,
    decor_spaced,
    overlay_keys,
    palette_group_layers,
    palette_groups,
    palette_landscape,
    pick_decor,
    tile_allows_objects,
)
from core.relief_tiling import ReliefTiles, assemble, wall_below
from core.terrain_autotile import desired_coverage, is_full, pick_border_tile, tile_shape
from scripts.generate_forest_map import (
    BIG_STUMPS,
    GIANT_ALIVE,
    GIANT_DEAD,
    HILL_SIDE,
    LANDMARK,
    SMALL_ALIVE,
    SMALL_DEAD,
    SMALL_STUMPS,
    TONE_THRESHOLD,
    _bush_groups,
    _clamp,
    _distances,
    _hash,
    _hill_stamps,
    _Noise,
    _Template,
)
from server.map_editor import terrain_from_cells, validate_cells

SIZE = 96
SIZE_MIN = 80
SEED = 3
DEFAULT_NAME = "Три дороги 96"
FOREST = "Лесной ландшафт"
MOUNTAINS = "Горный ландшафт"
INFRASTRUCTURE = "Инфраструктура"
ROAD_RADIUS = 1.3
PLAZA_RADIUS = 2.0
RIVER_WIDTH = 1  # Правило: река всегда 1 клетка; шире только на горной вершине ml_r33_c35.
ROAD_MARGIN = 2
CENTRE_CLEAR = 14
HILL_ANGLES = (-22.5, 90.0, 202.5)
MASSIFS_PER_ANCHOR = 2
MASSIF_WIDTH = (6, 10)
MASSIF_HEIGHT = (3, 4)
MASSIF_ATTEMPTS = 600
MASSIF_ROAD_RANGE = (3, 8)
DRY_THRESHOLD = 0.62
GIANT_DENSITY = 0.38
SMALL_DENSITY = 0.18
WATER_TEAL = 40
GIANT_DEAD_SHARE = 0.3


def _is_teal(colour):
    """Чистая вода: зелёный и синий каналы заметно выше красного (без камней и берега)."""
    red, green, blue = colour
    return green - red > WATER_TEAL and blue - red > WATER_TEAL


def _smooth(t):
    t = _clamp(t)
    return t * t * (3 - 2 * t)


def _rect_distance(x, y, rect):
    left, top, right, bottom = rect
    return math.hypot(max(left - x, 0, x - right), max(top - y, 0, y - bottom))


def _layout(size):
    """Положение рек, мостов и дорог в клетках для карты size×size."""
    centre = size // 2
    ry = round(size * 0.22)
    rw = round(size * 0.17)
    wy = round(size * 0.60)
    return {
        "centre": centre,
        "river_north": ry,
        "river_west": rw,
        "river_east": size - 1 - rw - (RIVER_WIDTH - 1),
        "side_road": wy,
        "north_rect": (centre - 6, ry - 3, centre + 6, ry + RIVER_WIDTH + 2),
        "west_rect": (rw - 5, wy - 3, rw + RIVER_WIDTH + 4, wy + 4),
        "east_rect": (size - 1 - rw - RIVER_WIDTH - 4, wy - 3, size - rw + 4, wy + 4),
    }


def _centreline(waypoints, rects, noise, salt, amplitude, step=0.4):
    """Точки неровной оси дороги: вдоль ломаной, смещение поперёк по шуму; у rects и у центра дорога ровная."""
    points = []
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        count = max(1, int(length / step))
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        points += [(x0 + (x1 - x0) * i / count, y0 + (y1 - y0) * i / count, nx, ny) for i in range(count)]
    points.append((*waypoints[-1], 0.0, 0.0))
    result = []
    for index, (x, y, nx, ny) in enumerate(points):
        travelled = index * step
        envelope = min(_smooth(travelled / 10), _smooth((len(points) - 1 - index) * step / 6))
        for rect in rects:
            envelope = min(envelope, _smooth(_rect_distance(x, y, rect) / 6))
        wobble = (noise(travelled, salt * 17.0, 9, 40 + salt) - 0.5) * 2 * amplitude * envelope
        result.append((x + nx * wobble, y + ny * wobble))
    return result


def _road_cells(line, size, radius=ROAD_RADIUS):
    """Клетки, центры которых ближе radius к оси дороги: ширина 2–3 клетки."""
    cells = set()
    for px, py in line:
        for cx in range(math.floor(px) - 2, math.floor(px) + 3):
            for cy in range(math.floor(py) - 2, math.floor(py) + 3):
                if 0 <= cx < size and 0 <= cy < size and math.hypot(cx + 0.5 - px, cy + 0.5 - py) <= radius + 1e-9:
                    cells.add((cx, cy))
    return cells


def _river_offsets(size, straight, noise, salt, amplitude):
    """Смещение русла по длине: плавное по шуму (не больше 1 клетки за шаг), у моста нулевое."""
    target = []
    for index in range(size):
        envelope = _smooth((min(abs(index - straight[0]), abs(index - straight[1])) if not straight[0] <= index <= straight[1] else 0) / 9)
        target.append(round((noise(index, salt * 13.0, 14, 60 + salt) - 0.5) * 2 * amplitude * envelope))
    for index in range(1, size):
        target[index] = max(target[index - 1] - 1, min(target[index - 1] + 1, target[index]))
    for index in range(size - 2, -1, -1):
        target[index] = max(target[index + 1] - 1, min(target[index + 1] + 1, target[index]))
    return target


def _river_line(size, base, offsets, start, horizontal):
    """Русло шириной RIVER_WIDTH клеток: смещение за шаг не больше 1, поэтому добавляем стыковую клетку, чтобы клетки касались сторонами."""
    cells = set()
    for u in range(start, size):
        shifts = {offsets[u], offsets[u + 1]} if u + 1 < size else {offsets[u]}
        for shift in shifts:
            for k in range(RIVER_WIDTH):
                v = base + shift + k
                if 0 <= v < size:
                    cells.add((u, v) if horizontal else (v, u))
    return cells


def _horizontal_river(size, top, straight, noise):
    offsets = _river_offsets(size, straight, noise, 1, 5)
    return _river_line(size, top, offsets, 0, True)


def _vertical_river(size, left, start, straight, noise, salt):
    offsets = _river_offsets(size, straight, noise, salt, 5)
    return _river_line(size, left, offsets, start, False)


def _bridge_stamps(group):
    """Вертикальный (настил 2 клетки по x, 4×7) и горизонтальный (настил 2 клетки по y, 5×4) мосты из раздела «Инфраструктура»."""
    grid = {(cell["x"], cell["y"]): cell["key"] for cell in group["cells"]}
    vertical = {(x, y): grid[(x, y)] for x in range(4) for y in range(7) if (x, y) in grid}
    horizontal = {(x - 2, y - 7): grid[(x, y)] for x in range(2, 7) for y in range(7, 11) if (x, y) in grid}
    horizontal.setdefault((4, 1), horizontal[(3, 1)])
    return vertical, horizontal


def _place_hills(size, centre, stamp, road_distance, water_distance, taken):
    """Три возвышенности вокруг центра между дорогами: [(x, y)] левого верхнего угла каждой."""
    placed = []
    for angle in HILL_ANGLES:
        for radius in range(7, 18):
            x = round(centre + radius * math.cos(math.radians(angle)) - HILL_SIDE / 2)
            y = round(centre + radius * math.sin(math.radians(angle)) - HILL_SIDE / 2)
            body = [(x + dx, y + dy) for dx in range(HILL_SIDE) for dy in range(HILL_SIDE)]
            margin = [(x + dx, y + dy) for dx in range(-1, HILL_SIDE + 1) for dy in range(-1, HILL_SIDE + 1)]
            if any(cell in taken or not 0 <= cell[0] < size or not 0 <= cell[1] < size for cell in margin):
                continue
            if any(road_distance.get(cell, 9) < ROAD_MARGIN or water_distance.get(cell, 9) < ROAD_MARGIN for cell in body):
                continue
            taken.update(margin)
            placed.append((x, y))
            break
    return placed


def _place_massifs(rng, size, tiles, anchors, road_distance, water_distance, taken, centre):
    """Горные массивы по обе стороны дорог: рядом с осью (в MASSIF_ROAD_RANGE), но не на дороге и не у воды."""
    placed = []
    for ax, ay in anchors:
        for _ in range(MASSIFS_PER_ANCHOR):
            for _ in range(MASSIF_ATTEMPTS):
                width, height = rng.randint(*MASSIF_WIDTH), rng.randint(*MASSIF_HEIGHT)
                x0 = round(ax + rng.uniform(-12, 12) - width / 2)
                y0 = round(ay + rng.uniform(-12, 12) - height / 2)
                plateau = {(x0 + x, y0 + y) for x in range(width) for y in range(height)}
                for corner in ((x0, y0), (x0 + width - 1, y0)):
                    if rng.random() < 0.7:
                        plateau.discard(corner)
                wall = wall_below(plateau)
                cells = plateau | wall
                if any(not 1 <= x < size - 1 or not 1 <= y < size - 1 for x, y in cells):
                    continue
                if math.hypot(x0 + width / 2 - centre, y0 + height / 2 - centre) < CENTRE_CLEAR:
                    continue
                margin = {(x + dx, y + dy) for x, y in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
                if margin & taken:
                    continue
                if any(road_distance.get(c, 9) < MASSIF_ROAD_RANGE[0] or water_distance.get(c, 9) < 2 for c in cells):
                    continue
                if min(road_distance.get(c, 9) for c in cells) > MASSIF_ROAD_RANGE[1]:
                    continue
                taken |= margin
                placed.append(assemble(tiles, plateau, wall, rng))
                break
    return placed


def generate(size=SIZE, seed=SEED):
    """Клетки карты «Три дороги» и сведения о ней: (cells, stats)."""
    if size < SIZE_MIN:
        raise SystemExit(f"Размер карты не меньше {SIZE_MIN}")
    pygame.init()
    rng = random.Random(seed)
    noise = _Noise(seed)
    catalog = catalog_definitions()
    items = {item["item_key"]: item for item in catalog}
    assets = {key: item["asset"] for key, item in items.items()}
    forest = palette_landscape(FOREST)
    dry_template, live_template = _Template(forest["dry"], assets), _Template(forest["live"], assets)
    mountain_group = palette_landscape(MOUNTAINS)["main"]
    mountain_layers = {layer["role"]: layer for layer in palette_group_layers(mountain_group)}
    infrastructure = next(group for group in palette_groups() if group["title"] == INFRASTRUCTURE)
    vertical_bridge, horizontal_bridge = _bridge_stamps(infrastructure)
    plateau_stamp = _hill_stamps(live_template.layers)[0]
    green, berry, dry_bushes = _bush_groups(items)
    water_tiles = sorted({
        key for key in mountain_layers["river"]["cells"].values()
        if items[key]["category"] == "water" and is_full(tile_shape(assets[key])[0]) and _is_teal(tile_shape(assets[key])[1])
    })

    spec = _layout(size)
    centre = spec["centre"]
    north_x = centre
    side = spec["side_road"] + 1
    west_cross, east_cross = spec["river_west"], spec["river_east"]

    # Дороги: оси идут от центра к краям; у мостов оси ровные и точно по границе клеток (настил 2 клетки).
    lines = {
        "north": _centreline([(north_x, centre), (north_x, 0)], [spec["north_rect"]], noise, 1, 4.5),
        "west": _centreline(
            [(centre, centre), (centre - 10, centre + 8), (west_cross + RIVER_WIDTH + 12, side), (0, side)],
            [spec["west_rect"]], noise, 2, 4.0,
        ),
        "east": _centreline(
            [(centre, centre), (centre + 10, centre + 8), (east_cross - 12, side), (size, side)],
            [spec["east_rect"]], noise, 3, 4.0,
        ),
    }
    roads = {name: _road_cells(line, size) for name, line in lines.items()}
    plaza = _road_cells([(centre, centre)], size, PLAZA_RADIUS)
    road = set().union(*roads.values()) | plaza

    # Реки: северная поперёк карты, западная и восточная уходят от неё на юг; у мостов русло ровное.
    ry = spec["river_north"]
    river = _horizontal_river(size, ry, (spec["north_rect"][0], spec["north_rect"][2]), noise)
    river |= _vertical_river(size, west_cross, ry, (spec["west_rect"][1], spec["west_rect"][3]), noise, 2)
    river |= _vertical_river(size, east_cross, ry, (spec["east_rect"][1], spec["east_rect"][3]), noise, 3)

    bridges = []
    bridges.append({(north_x - 2 + dx, ry - 1 + dy): key for (dx, dy), key in vertical_bridge.items()})
    for cross, rect in ((west_cross, spec["west_rect"]), (east_cross, spec["east_rect"])):
        bridges.append({(cross + dx, side - 2 + dy): key for (dx, dy), key in horizontal_bridge.items()})
    bridge_cells = {cell for stamp in bridges for cell in stamp}
    if road & river - bridge_cells:
        raise SystemExit("Дорога пересекает реку вне моста")
    hole = road | river | bridge_cells

    road_distance = _distances(size, road)
    water_distance = _distances(size, river)
    bridge_distance = _distances(size, bridge_cells)
    taken = set()
    hills = _place_hills(size, centre, plateau_stamp, road_distance, water_distance, taken)
    anchors = []
    for line in lines.values():
        anchors += [line[int(len(line) * share)] for share in (0.33, 0.8)]
    mountain = mountain_layers["mountain"]
    keys = sorted(set(mountain["cells"].values()))
    plateau_keys = [key for key in keys if items[key]["category"] == "grass"]
    relief = ReliefTiles(plateau_keys, [key for key in keys if key not in plateau_keys], assets, dict(mountain["cells"]))
    massifs = _place_massifs(rng, size, relief, anchors, road_distance, water_distance, taken, centre)

    dry_cells = {(x, y) for x in range(size) for y in range(size) if noise(x, y, 11, 77) > DRY_THRESHOLD}

    def template_at(x, y):
        return dry_template if (x, y) in dry_cells else live_template

    # Лес: чем выше плотность, тем гуще огромные деревья; дороги, реки, мосты, возвышенности и горы остаются свободными.
    keep_out = set()
    for x, y in hills:
        keep_out |= {(x + dx, y + dy) for dx in range(-1, HILL_SIDE + 1) for dy in range(-1, HILL_SIDE + 1)}
    for state in massifs:
        keep_out |= {(x + dx, y + dy) for x, y in state for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    objects = {}
    trees = set(GIANT_ALIVE + GIANT_DEAD + (LANDMARK,) + SMALL_ALIVE + SMALL_DEAD)

    def near_tree(x, y, reach):
        return any(objects.get((x + dx, y + dy)) in trees for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1))

    def density(x, y):
        return _clamp(0.7 * noise(x, y, 18, 31) + 0.3 * noise(x, y, 7, 32))

    def free(x, y, margin=ROAD_MARGIN):
        cell = (x, y)
        return (
            road_distance[cell] >= margin and water_distance[cell] >= margin and bridge_distance[cell] >= margin
            and cell not in keep_out and cell not in objects
        )

    order = [(x, y) for x in range(size) for y in range(size)]
    rng.shuffle(order)
    for x, y in order:
        if math.hypot(x - centre, y - centre) < CENTRE_CLEAR or not free(x, y, ROAD_MARGIN + 1) or (x + y) % 2:
            continue
        if density(x, y) > GIANT_DENSITY:
            objects[(x, y)] = rng.choice(GIANT_DEAD if rng.random() < GIANT_DEAD_SHARE else GIANT_ALIVE)
    for x, y in order:
        if not free(x, y) or math.hypot(x - centre, y - centre) < CENTRE_CLEAR - 3:
            continue
        value = density(x, y)
        if value <= SMALL_DENSITY or rng.random() > 0.6 + 0.4 * value or near_tree(x, y, 1):
            continue
        alive = rng.random() < (0.35 if (x, y) in dry_cells else 0.85)
        objects[(x, y)] = rng.choice(SMALL_ALIVE if alive else SMALL_DEAD)
    for x, y in order:
        if not free(x, y):
            continue
        roll = rng.random()
        if (x, y) in dry_cells:
            if roll < 0.04:
                objects[(x, y)] = rng.choice(BIG_STUMPS)
            elif roll < 0.09:
                objects[(x, y)] = rng.choice(SMALL_STUMPS)
            elif roll < 0.14:
                objects[(x, y)] = rng.choice(dry_bushes)
        elif roll < 0.08:
            objects[(x, y)] = rng.choice(berry if rng.random() < 0.35 else green)

    # Тайлы: земля везде (вода под руслом), трава поверх земли везде кроме дорог и рек, у берега трава по форме.
    ground_decor, grass_decor = {}, {}
    ground_choice, grass_choice = {}, {}
    for x, y in order:
        template = template_at(x, y)
        if (x, y) in road:
            ground_choice[(x, y)] = pick_decor(template.decor_ground, x, y, ground_decor, rng)
        elif (x, y) not in hole and road_distance[(x, y)] >= ROAD_MARGIN:
            grass_choice[(x, y)] = pick_decor(template.decor_grass, x, y, grass_decor, rng)

    def tone(x, y, base, flat, salt):
        if flat and noise(x, y, 7, 61 + salt) > TONE_THRESHOLD:
            return flat[_hash(x, y, salt) % len(flat)]
        return base[_hash(x, y, salt + 1) % len(base)]

    def water(x, y):
        return water_tiles[_hash(x, y, 3) % len(water_tiles)]

    def ground_tile(x, y):
        cell = (x, y)
        if cell in river:
            return water(x, y)
        if cell not in road and water_distance[cell] <= 1 and road_distance[cell] > 1:
            return water(x, y)
        template = template_at(x, y)
        return ground_choice.get(cell) or tone(x, y, template.base_ground, template.flat_ground, 1)

    def grass_tile(x, y):
        template = template_at(x, y)
        desired = desired_coverage(x, y, hole)
        if is_full(desired):
            return grass_choice.get((x, y)) or tone(x, y, template.base_grass, template.flat_grass, 5)
        return pick_border_tile(template.border, desired, rng)

    ground_map = {(x, y): ground_tile(x, y) for y in range(size) for x in range(size)}
    overlay_map = {(x, y): grass_tile(x, y) for y in range(size) for x in range(size) if (x, y) not in hole}
    transparent = overlay_keys()
    solid = set()

    def stamp_cells(cells):
        for cell, key in cells.items():
            base = template_at(*cell).base_grass
            ground_map[cell] = base[_hash(*cell, 7) % len(base)]
            if key in transparent:
                overlay_map[cell] = key
            else:
                ground_map[cell] = key
                overlay_map.pop(cell, None)
            if items[key]["blocks"]:
                solid.add(cell)

    for x, y in hills:
        stamp_cells({(x + dx, y + dy): key for (dx, dy), key in plateau_stamp.items()})
    for state in massifs:
        stamp_cells(state)
    for stamp in bridges:
        for cell, key in stamp.items():
            overlay_map[cell] = key
            if items[key]["blocks"]:
                solid.add(cell)
            else:
                solid.discard(cell)

    cells = [{"layer": "ground", "x": x, "y": y, "key": key} for (x, y), key in sorted(ground_map.items(), key=lambda e: (e[0][1], e[0][0]))]
    cells += [{"layer": "overlay", "x": x, "y": y, "key": key} for (x, y), key in sorted(overlay_map.items(), key=lambda e: (e[0][1], e[0][0]))]
    top = {(c["x"], c["y"]): c["key"] for c in cells if c["layer"] != "object"}
    for cell in [cell for cell, key in objects.items() if not tile_allows_objects(top[cell], items[top[cell]]["category"])]:
        del objects[cell]
    for (x, y), key in sorted(objects.items(), key=lambda entry: (entry[0][1], entry[0][0])):
        cells.append({"layer": "object", "x": x, "y": y, "key": key})

    stats = _check(cells, catalog, items, objects, road, river, bridge_cells, centre, size, ground_decor, grass_decor)
    stats.update(
        hills=len(hills), massifs=len(massifs), mountain_cells=sum(len(state) for state in massifs),
        dry_cells=len(dry_cells), road_cells=len(road), river_cells=len(river), bridges=len(bridges),
        max_road_thickness=_thickness(road, centre),
    )
    return cells, stats


def _thickness(road, centre, plaza=5):
    """Ширина дороги вне перекрёстка: сторона наибольшего квадрата из клеток дороги."""
    best = 0
    for x, y in road:
        if max(abs(x - centre), abs(y - centre)) < plaza:
            continue
        side = 1
        while all((x + dx, y + dy) in road for dx in range(side + 1) for dy in range(side + 1)):
            side += 1
        best = max(best, side)
    return best


def _check(cells, catalog, items, objects, road, river, bridge_cells, centre, size, ground_decor, grass_decor):
    validate_cells(cells, catalog, size, size)
    terrain = terrain_from_cells(cells, catalog)
    assert decor_spaced(ground_decor) and decor_spaced(grass_decor)
    blocked = set(terrain["impassable"]) | set(terrain["water"]) | set(terrain["dry"])
    seen, queue = {(centre, centre)}, deque([(centre, centre)])
    while queue:
        cx, cy = queue.popleft()
        for nxt in ((cx, cy - 1), (cx, cy + 1), (cx - 1, cy), (cx + 1, cy)):
            if 0 <= nxt[0] < size and 0 <= nxt[1] < size and nxt not in seen and nxt not in blocked:
                seen.add(nxt)
                queue.append(nxt)
    exits = {
        "north": [c for c in road if c[1] == 0],
        "west": [c for c in road if c[0] == 0],
        "east": [c for c in road if c[0] == size - 1],
    }
    reachable = {name: any(cell in seen for cell in cells_) for name, cells_ in exits.items()}
    on_road = [cell for cell in objects if cell in road]
    return {
        "objects": Counter(items[key]["category"] for key in objects.values()),
        "road_exits_reachable_from_centre": reachable,
        "objects_on_road": len(on_road),
        "ground_decor": len(ground_decor),
        "grass_decor": len(grass_decor),
        "bridge_cells_walkable": sum(1 for cell in bridge_cells if cell in seen),
    }


def save(cells, name, size=SIZE):
    existing = next((draft for draft in map_drafts.list_drafts() if draft["name"] == name), None)
    return map_drafts.save_draft(name, cells, size, size, draft_id=existing["id"] if existing else None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default=DEFAULT_NAME, help="название черновика")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--size", type=int, default=SIZE)
    arguments = parser.parse_args()
    generated, info = generate(arguments.size, arguments.seed)
    draft = save(generated, arguments.name, arguments.size)
    print(f"Черновик «{draft['name']}»: {len(draft['cells'])} клеток")
    for field, value in info.items():
        print(f"  {field}: {value}")
