"""Рельеф глобальной карты: хранится на сервере, клиент только рисует и учитывает непроходимость."""

import math
import random


TILE = 32
# Горный разлом: тайлы X 130..134, Y 95..102; проход к нему прорублен через южное подножие
RIFT_TILES = (130, 95, 5, 8)
RIFT_PASSAGE = (RIFT_TILES[0] * TILE, RIFT_TILES[1] * TILE, RIFT_TILES[2] * TILE, 3800 - RIFT_TILES[1] * TILE)
# Чёрная копь: тайлы X 133..141, Y 54..66; западный вход обращён к городу
BLACK_PIT_TILES = (133, 54, 9, 13)
BLACK_PIT_PASSAGES = (
    tuple(value * TILE for value in BLACK_PIT_TILES),
    (113 * TILE, 59 * TILE, 21 * TILE, 3 * TILE),
)


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


# Единый горный массив (тайлы): объединяет южный хребет у разлома и северные высокие горы
MASSIF_OUTLINE = (
    (140, 46), (159, 42), (171, 51), (175, 64), (166, 79), (161, 92), (154, 102), (143, 107),
    (134, 108), (124, 105), (116, 98), (113, 88), (117, 79), (125, 74), (130, 66), (134, 55),
)

OBSTACLES = (
    _massif("mountains_1", "Горы", MASSIF_OUTLINE, seed=3694, passages=(RIFT_PASSAGE, *BLACK_PIT_PASSAGES)),
    _forest("forest_1", "Лес", ((2063, 3464), (741, 3506), (498, 2964), (1778, 2611), (3087, 2883)), seed=2063),
    _lake("lake_1", "Озеро", ((40, 26), (62, 38), (98, 33), (102, 17), (83, 19), (74, 24), (61, 27)), seed=402638),
)


def is_passable(x, y):
    return not any(
        point_in_polygon((x, y), obstacle["points"])
        and not any(_in_rect(x, y, passage) for passage in obstacle["passages"])
        for obstacle in OBSTACLES
    )


def terrain_payload(city_level=1):
    from server.structures import world_structures
    from server.world_roads import roads_payload

    return {"obstacles": [dict(obstacle) for obstacle in OBSTACLES],
            **world_structures(city_level), "roads": roads_payload(city_level)}
