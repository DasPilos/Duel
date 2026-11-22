"""Рельеф глобальной карты: хранится на сервере, клиент только рисует и учитывает непроходимость.

Процедурный мир без опубликованной карты — 1024x512 клеток по 16 px (физический размер тот же, что был
512x256 по 32 px). Опубликованная карта редактора подменяет рельеф целиком через apply_live_terrain.
"""

import math
import random

from core import crystal_growth
from core.tile_mask import mask_blocks_rect, mask_free_point
from core.tile import TILE


# Горный разлом: тайлы X 260..269, Y 190..205 (16 px); проход к нему прорублен через южное подножие
RIFT_TILES = (260, 190, 10, 16)
RIFT_PASSAGE = (RIFT_TILES[0] * TILE, RIFT_TILES[1] * TILE, RIFT_TILES[2] * TILE, 3800 - RIFT_TILES[1] * TILE)
# Чёрная копь: тайлы X 266..283, Y 108..133 (16 px); западный вход обращён к городу
BLACK_PIT_TILES = (266, 108, 18, 26)
BLACK_PIT_PASSAGES = (
    tuple(value * TILE for value in BLACK_PIT_TILES),
    (226 * TILE, 118 * TILE, 42 * TILE, 6 * TILE),
)


def _tile_rects(tiles):
    """Прямоугольники (x0, y0, x1, y1, включительно), покрывающие клетки: строки склеиваются, одинаковые отрезки по вертикали тоже."""
    rows = {}
    for tile_x, tile_y in tiles:
        rows.setdefault(tile_y, []).append(tile_x)
    rects = []
    open_runs = {}
    for tile_y in range(min(rows, default=0), max(rows, default=-1) + 2):
        runs = set()
        start = previous = None
        for tile_x in sorted(rows.get(tile_y, [])):
            if start is None or tile_x != previous + 1:
                if start is not None:
                    runs.add((start, previous))
                start = tile_x
            previous = tile_x
        if start is not None:
            runs.add((start, previous))
        for run in [run for run in open_runs if run not in runs]:
            left, right = run
            rects.append((left, open_runs.pop(run), right, tile_y - 1))
        for run in runs:
            open_runs.setdefault(run, tile_y)
    return rects


# Процедурный мир без опубликованной карты не имеет клеточного рельефа: поля ниже остаются пустыми,
# их заполняет карта редактора через apply_live_terrain. Имена сохранены для совместимости с картой редактора.
MAP_MOUNTAIN_TILES = frozenset()
MAP_FOREST_TILES = frozenset()
MAP_WATER_TILES = frozenset()
MAP_DRY_TILES = frozenset()
MAP_PATH_TILES = frozenset()
MAP_PROPS = ()
MAP_BRIDGES = ()
MAP_PROP_TILES = frozenset()
MAP_BERRY_TILES = frozenset()
MAP_FLOOR_TILES = frozenset()
MAP_IMPASSABLE_TILES = frozenset()
MAP_PARTIAL_MASKS = {}
MAP_WILDLIFE_BLOCKED_TILES = frozenset()
MAP_ANIMALS = ()
MAP_MOUNTAIN_OBSTACLES = ()
# Кристаллы карты: {(x, y): {"color", "stage"}}; настройки роста и добычи по цвету; добыча включена сценарием карты
MAP_CRYSTALS = {}
CRYSTAL_SETTINGS = {}
HARVEST_ENABLED = False

MAP_BLOCKED_TILES = MAP_FOREST_TILES | MAP_WATER_TILES | MAP_DRY_TILES | MAP_PROP_TILES | MAP_MOUNTAIN_TILES


def rect_touches_blocked_tile(rect):
    """Пересекает ли прямоугольник (x, y, ширина, высота) тайл леса, воды или пня и бревна; правый и нижний край не считаются."""
    if not MAP_BLOCKED_TILES and not MAP_PARTIAL_MASKS:
        return False
    x, y, width, height = rect
    for tile_y in range(y // TILE, (y + height - 1) // TILE + 1):
        for tile_x in range(x // TILE, (x + width - 1) // TILE + 1):
            mask = MAP_PARTIAL_MASKS.get((tile_x, tile_y))
            if mask is not None:
                if mask_blocks_rect(mask, tile_x, tile_y, TILE, x, y, x + width, y + height):
                    return True
            elif (tile_x, tile_y) in MAP_BLOCKED_TILES:
                return True
    return False


def _tile_rows(tiles):
    """Тайлы по строкам отрезками [y, x_начало, x_конец]: компактный формат для клиента."""
    by_row = {}
    for tile_x, tile_y in tiles:
        by_row.setdefault(tile_y, []).append(tile_x)
    rows = []
    for tile_y in sorted(by_row):
        xs = sorted(by_row[tile_y])
        start = previous = xs[0]
        for tile_x in xs[1:]:
            if tile_x != previous + 1:
                rows.append([tile_y, start, previous])
                start = tile_x
            previous = tile_x
        rows.append([tile_y, start, previous])
    return rows


MAP_TILES_W = 1024
MAP_TILES_H = 512
MAP_SPAWN_PX = (MAP_TILES_W * TILE // 2, MAP_TILES_H * TILE // 2)


def _in_rect(x, y, rect):
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def _segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - ax - dx * t, py - ay - dy * t)


def _edge_distance(x, y, outline):
    return min(
        _segment_distance(x, y, ax, ay, bx, by)
        for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1])
    )


def _massif(obstacle_id, name, tiles, seed, passages=(), count=260):
    """Горный массив по плавному контуру: у краёв низкие холмы, к центру всё выше, в середине огромные горы."""
    rng = random.Random(seed)
    points = _smooth_outline([(x * TILE, y * TILE) for x, y in tiles], rng, wobble=110)
    coarse = points[::3]
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    max_depth = max(
        _edge_distance(x, y, coarse)
        for x in range(min(xs), max(xs), 64)
        for y in range(min(ys), max(ys), 64)
        if point_in_polygon((x, y), points)
    )
    peaks = []
    attempts = 0
    while len(peaks) < count and attempts < count * 40:
        attempts += 1
        x = rng.uniform(min(xs), max(xs))
        y = rng.uniform(min(ys), max(ys))
        if not point_in_polygon((x, y), points):
            continue
        depth = min(1.0, _edge_distance(x, y, coarse) / max_depth) ** 0.8
        width = (70 + 300 * depth) * rng.uniform(0.85, 1.15)
        height = width * (0.35 + 1.25 * depth) * rng.uniform(0.85, 1.15)
        # Основание целиком внутри подножия, проход к разлому свободен
        if not all(point_in_polygon((x + dx, y), points) for dx in (-width / 2, width / 2)):
            continue
        box = (x - width / 2, y - height, width, height)
        if any(_rects_overlap(box, passage) for passage in passages):
            continue
        peaks.append({
            "x": round(x), "y": round(y), "w": round(width), "h": round(height),
            "kind": "hill" if depth < 0.3 else "peak",
        })
    peaks.sort(key=lambda peak: peak["y"])
    return {
        "id": obstacle_id, "type": "mountains", "name": name, "points": points, "peaks": peaks,
        "passages": [list(passage) for passage in passages],
    }


def _rects_overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for i in range(len(polygon)):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _chaikin(points, iterations):
    for _ in range(iterations):
        smoothed = []
        for (px, py), (qx, qy) in zip(points, points[1:] + points[:1]):
            smoothed.append((0.75 * px + 0.25 * qx, 0.75 * py + 0.25 * qy))
            smoothed.append((0.25 * px + 0.75 * qx, 0.25 * py + 0.75 * qy))
        points = smoothed
    return points


def _smooth_outline(corners, rng, wobble=150, iterations=4):
    """Плавный неровный контур без острых углов: основа скругляется, рёбра изгибаются случайно, затем снова сглаживаются."""
    base = _chaikin(corners, 2)
    points = []
    for (x1, y1), (x2, y2) in zip(base, base[1:] + base[:1]):
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
        steps = max(1, int(length // 110))
        for step in range(steps):
            t = (step + rng.uniform(0, 0.5)) / steps
            # Крупные выступы/заливы плюс мелкая неровность
            bend = rng.uniform(-wobble, wobble) * math.sin(math.pi * t) + rng.uniform(-35, 35)
            points.append((x1 + (x2 - x1) * t + nx * bend, y1 + (y2 - y1) * t + ny * bend))
    points = _chaikin(points, iterations)
    outline = []
    for x, y in points:
        point = (round(x), round(y))
        if not outline or math.hypot(point[0] - outline[-1][0], point[1] - outline[-1][1]) >= 8:
            outline.append(point)
    return outline


def _forest(obstacle_id, name, corners, seed, spacing=40):
    """Непроходимый лес по плавному контуру (мировые пиксели): деревья сеткой со смещением внутри контура."""
    rng = random.Random(seed)
    points = _smooth_outline(list(corners), rng)
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    trees = []
    for y in range(min(ys), max(ys) + 1, spacing):
        for x in range(min(xs), max(xs) + 1, spacing):
            tx, ty = x + rng.randint(-14, 14), y + rng.randint(-14, 14)
            if point_in_polygon((tx, ty), points):
                trees.append({"x": tx, "y": ty, "r": rng.randint(16, 27)})
    trees.sort(key=lambda tree: tree["y"])
    return {"id": obstacle_id, "type": "forest", "name": name, "points": list(points), "trees": trees, "passages": []}


def _lake(obstacle_id, name, tile_corners, seed):
    """Озеро с округлой береговой линией; points включает берег для поиска непроходимых тайлов."""
    rng = random.Random(seed)
    points = _smooth_outline([(x * TILE, y * TILE) for x, y in tile_corners], rng, wobble=72, iterations=4)
    center_x = sum(x for x, _ in points) / len(points)
    center_y = sum(y for _, y in points) / len(points)
    water_points = []
    for x, y in points:
        inset = rng.uniform(0.86, 0.91)
        water_points.append((round(center_x + (x - center_x) * inset),
                             round(center_y + (y - center_y) * inset)))
    return {
        "id": obstacle_id,
        "type": "lake",
        "name": name,
        "points": points,
        "water_points": water_points,
        "sandy_shore_sections": [[0.06, 0.2], [0.43, 0.57], [0.78, 0.91]],
        "passages": [],
    }


# Единый горный массив (тайлы 16 px): объединяет южный хребет у разлома и северные высокие горы
MASSIF_OUTLINE = (
    (280, 92), (318, 84), (342, 102), (350, 128), (332, 158), (322, 184), (308, 204), (286, 214),
    (268, 216), (248, 210), (232, 196), (226, 176), (234, 158), (250, 148), (260, 132), (268, 110),
)

_WORLD_OBSTACLES = (
    _massif("mountains_1", "Горы", MASSIF_OUTLINE, seed=3694, passages=(RIFT_PASSAGE, *BLACK_PIT_PASSAGES)),
    _forest("forest_1", "Лес", ((2063, 3464), (741, 3506), (498, 2964), (1778, 2611), (3087, 2883)), seed=2063),
    _lake("lake_1", "Озеро", ((80, 52), (124, 76), (196, 66), (204, 34), (166, 38), (148, 48), (122, 54)), seed=402638),
)


def _mountain_obstacle(index, rect):
    """Кусок горного венца по клеткам: препятствие для мобов и дорог; рисуется клиентом по клеткам."""
    left, top = rect[0] * TILE, rect[1] * TILE
    right, bottom = (rect[2] + 1) * TILE, (rect[3] + 1) * TILE
    return {
        "id": f"mountains_ring_{index}", "type": "mountains", "name": "Горный венец",
        "points": [(left, top), (right, top), (right, bottom), (left, bottom)],
        "peaks": [], "passages": [],
    }


OBSTACLES = _WORLD_OBSTACLES
# Публикация из редактора: размер карты, точка появления и метка публикации (для опроса БД)
LIVE_MAP = False
PUBLISHED_AT = None
# Рельеф и размер, которые подменяет карта из редактора; процедурные значения сохраняем для возврата
_TERRAIN_NAMES = (
    "MAP_FOREST_TILES", "MAP_WATER_TILES", "MAP_DRY_TILES", "MAP_PATH_TILES", "MAP_MOUNTAIN_TILES",
    "MAP_BERRY_TILES", "MAP_FLOOR_TILES", "MAP_PROPS", "MAP_BRIDGES", "MAP_PROP_TILES", "MAP_BLOCKED_TILES",
    "MAP_IMPASSABLE_TILES", "MAP_PARTIAL_MASKS", "MAP_MOUNTAIN_OBSTACLES", "OBSTACLES",
    "MAP_WILDLIFE_BLOCKED_TILES", "MAP_ANIMALS",
    "MAP_CRYSTALS", "CRYSTAL_SETTINGS", "HARVEST_ENABLED",
    "MAP_TILES_W", "MAP_TILES_H", "MAP_SPAWN_PX", "LIVE_MAP", "PUBLISHED_AT",
)
_PROCEDURAL_TERRAIN = {name: globals()[name] for name in _TERRAIN_NAMES}
# Растёт при каждой подмене рельефа: по нему клиент понимает, что карта изменилась
TERRAIN_VERSION = 0


def _live_terrain_values(terrain, published):
    forest = frozenset(terrain["forest"])
    dry = frozenset(terrain["dry"])
    berry = frozenset(terrain["berry"])
    floor = frozenset(terrain["floor"])
    water = frozenset(terrain["water"])
    paths = frozenset(terrain["paths"])
    mountain = frozenset(terrain["mountain"])
    impassable = frozenset(terrain["impassable"])
    partial_masks = dict(terrain.get("partial", {}))
    crystals = dict(terrain.get("crystals", {}))
    partial_tiles = frozenset(partial_masks)
    props = tuple(terrain["props"])
    bridges = tuple(terrain["bridges"])
    animals = tuple(dict(animal) for animal in terrain.get("animals", ()))
    animal_tiles = frozenset((animal["x"], animal["y"]) for animal in animals)
    prop_tiles = frozenset(tuple(tile) for prop in props for tile in prop["tiles"])
    mountain_obstacles = tuple(
        _mountain_obstacle(index, rect) for index, rect in enumerate(_tile_rects(mountain - partial_tiles))
    )
    obstacles = mountain_obstacles
    wildlife_blocked = frozenset(terrain.get(
        "wildlife_blocked",
        (forest | dry | prop_tiles | mountain | impassable) - water - animal_tiles,
    )) | ((forest | dry | prop_tiles | mountain | impassable) - water - animal_tiles - partial_tiles)
    mobile_animal_tiles = animal_tiles - wildlife_blocked - water - partial_tiles
    impassable -= mobile_animal_tiles
    blocked = (forest | dry | water | prop_tiles | mountain | impassable) - partial_tiles - mobile_animal_tiles
    map_w, map_h = published["map_w"], published["map_h"]
    return {
        "MAP_FOREST_TILES": forest,
        "MAP_WATER_TILES": water,
        "MAP_DRY_TILES": dry,
        "MAP_PATH_TILES": paths,
        "MAP_MOUNTAIN_TILES": mountain,
        "MAP_IMPASSABLE_TILES": impassable,
        "MAP_PARTIAL_MASKS": partial_masks,
        "MAP_WILDLIFE_BLOCKED_TILES": wildlife_blocked,
        "MAP_ANIMALS": animals,
        "MAP_CRYSTALS": crystals,
        "CRYSTAL_SETTINGS": crystal_growth.validate_settings(
            published.get("crystals"),
            sorted(set(published.get("crystals") or {}) | {value["color"] for value in crystals.values()})),
        "HARVEST_ENABLED": bool(published.get("harvest_enabled")),
        "MAP_BERRY_TILES": berry,
        "MAP_FLOOR_TILES": floor,
        "MAP_PROPS": props,
        "MAP_BRIDGES": bridges,
        "MAP_PROP_TILES": prop_tiles,
        "MAP_BLOCKED_TILES": blocked,
        "MAP_MOUNTAIN_OBSTACLES": mountain_obstacles,
        "OBSTACLES": obstacles,
        "MAP_TILES_W": map_w,
        "MAP_TILES_H": map_h,
        "MAP_SPAWN_PX": _live_spawn_px(map_w, map_h, blocked, obstacles, partial_masks),
        "LIVE_MAP": True,
        "PUBLISHED_AT": published["published_at"],
    }


def apply_live_terrain(terrain=None, published=None):
    """Подменяет рельеф и размер мира картой редактора; без карты (None) возвращает процедурный мир."""
    global TERRAIN_VERSION
    if terrain is None or published is None:
        values = _PROCEDURAL_TERRAIN
    else:
        values = _live_terrain_values(terrain, published)
    globals().update(values)
    TERRAIN_VERSION += 1


def remove_live_crystal(tile):
    """Убирает добытый кристалл: тайл становится свободным, клиент получает новую версию рельефа."""
    global MAP_CRYSTALS, MAP_IMPASSABLE_TILES, MAP_BLOCKED_TILES, TERRAIN_VERSION
    MAP_CRYSTALS = {key: value for key, value in MAP_CRYSTALS.items() if key != tile}
    MAP_IMPASSABLE_TILES = MAP_IMPASSABLE_TILES - {tile}
    MAP_BLOCKED_TILES = MAP_BLOCKED_TILES - {tile}
    TERRAIN_VERSION += 1


def _passable_at(x, y, blocked, obstacles, partial_masks=None):
    tile = (int(x) // TILE, int(y) // TILE)
    if tile in blocked:
        return False
    if partial_masks and tile in partial_masks and not mask_free_point(partial_masks[tile], TILE, tile[0], tile[1], x, y):
        return False
    return not any(
        point_in_polygon((x, y), obstacle["points"])
        and not any(_in_rect(x, y, passage) for passage in obstacle["passages"])
        for obstacle in obstacles
    )


def is_passable(x, y):
    return _passable_at(x, y, MAP_BLOCKED_TILES, OBSTACLES, MAP_PARTIAL_MASKS)


def _live_spawn_px(map_w, map_h, blocked, obstacles, partial_masks=None):
    """Точка появления опубликованной карты: свободный тайл ближе всего к центру карты."""
    cx, cy = map_w / 2, map_h / 2
    for _, tile_x, tile_y in sorted(
        ((tile_x - cx) ** 2 + (tile_y - cy) ** 2, tile_x, tile_y)
        for tile_x in range(map_w) for tile_y in range(map_h)
    ):
        x, y = tile_x * TILE + TILE // 2, tile_y * TILE + TILE // 2
        if _passable_at(x, y, blocked, obstacles, partial_masks):
            return (x, y)
    return (map_w * TILE // 2, map_h * TILE // 2)


def terrain_payload(city_level=1):
    from economy.server.world_roads import roads_payload
    from server.structures import world_structures

    structures = world_structures(city_level)
    roads = roads_payload(city_level)

    return {"map": {"tiles_w": MAP_TILES_W, "tiles_h": MAP_TILES_H, "uniform_grass": LIVE_MAP,
                    "spawn": list(MAP_SPAWN_PX), "version": TERRAIN_VERSION},
            "tiles": {"forest": _tile_rows(MAP_FOREST_TILES), "water": _tile_rows(MAP_WATER_TILES),
                      "dry": _tile_rows(MAP_DRY_TILES), "paths": _tile_rows(MAP_PATH_TILES),
                      "mountain": _tile_rows(MAP_MOUNTAIN_TILES), "impassable": _tile_rows(MAP_IMPASSABLE_TILES),
                      "berry": _tile_rows(MAP_BERRY_TILES), "floor": _tile_rows(MAP_FLOOR_TILES),
                      "partial": [[x, y, mask] for (x, y), mask in sorted(MAP_PARTIAL_MASKS.items())]},
            "animals": [dict(animal) for animal in MAP_ANIMALS],
            "props": [dict(prop) for prop in MAP_PROPS],
            "bridges": [dict(bridge) for bridge in MAP_BRIDGES],
            "obstacles": [dict(obstacle) for obstacle in OBSTACLES],
            "crystals": [[x, y, crystal["color"], crystal["stage"]]
                         for (x, y), crystal in sorted(MAP_CRYSTALS.items())],
            **structures, "roads": roads}
