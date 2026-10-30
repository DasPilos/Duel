"""Подбор тайлов-переходов по форме: где тайл прозрачен, там должна быть видна дорога.

Тайл траву на дороге описывается покрытием 4×4 подклеток (доля непрозрачных пикселей). Нужное покрытие клетки
считается по соседним клеткам дороги: прозрачна та часть клетки, что ближе HOLE_RADIUS (по умолчанию полклетки)
к дороге, поэтому граница проходит по середине пограничной клетки травы, как в рамках блоков образца.
Из всех тайлов-кандидатов выбирается тот, чья форма меньше всего отличается от нужной, так что работают и боковые
тайлы, и угловые, и мелкие фрагменты, а не только кольцо одного блока.

Pygame подключается внутри функций, чтобы модуль можно было импортировать там, где его нет.
"""
import functools
import math

from core.map_catalog import MAP_ASSETS

SUBDIV = 4
HOLE_RADIUS = 0.5
EDGE_SOFTNESS = 1 / SUBDIV
OPAQUE_FROM = 127
FULL_COVERAGE = 0.97
COLOR_DISTANCE_MAX = 14
TIE_MARGIN = 0.3


@functools.cache
def tile_shape(asset):
    """(покрытие SUBDIV×SUBDIV подклеток по строкам сверху вниз, средний цвет непрозрачной части) тайла."""
    import pygame

    image = pygame.image.load(str(MAP_ASSETS / asset))
    width, height = image.get_size()
    step_x, step_y = width // SUBDIV, height // SUBDIV
    coverage, sums, opaque = [], [0, 0, 0], 0
    for by in range(SUBDIV):
        for bx in range(SUBDIV):
            count = 0
            for y in range(by * step_y, (by + 1) * step_y):
                for x in range(bx * step_x, (bx + 1) * step_x):
                    red, green, blue, alpha = image.get_at((x, y))
                    if alpha > OPAQUE_FROM:
                        count += 1
                        sums[0], sums[1], sums[2] = sums[0] + red, sums[1] + green, sums[2] + blue
            opaque += count
            coverage.append(count / (step_x * step_y))
    colour = tuple(channel // max(opaque, 1) for channel in sums)
    return tuple(coverage), colour


def _distance_to_cell(px, py, cx, cy):
    dx = max(cx - px, 0, px - (cx + 1))
    dy = max(cy - py, 0, py - (cy + 1))
    return math.hypot(dx, dy)


def desired_coverage(x, y, road, radius=HOLE_RADIUS):
    """Нужное покрытие клетки (x, y) травой: 1 — трава, 0 — должна быть видна дорога (road — множество клеток дороги)."""
    nearby = [(cx, cy) for cx in (x - 1, x, x + 1) for cy in (y - 1, y, y + 1) if (cx, cy) in road]
    result = []
    for by in range(SUBDIV):
        for bx in range(SUBDIV):
            px, py = x + (bx + 0.5) / SUBDIV, y + (by + 0.5) / SUBDIV
            distance = min((_distance_to_cell(px, py, cx, cy) for cx, cy in nearby), default=9.0)
            result.append(min(1.0, max(0.0, 0.5 + (distance - radius) / EDGE_SOFTNESS)))
    return result


def is_full(coverage):
    return all(value >= FULL_COVERAGE for value in coverage)


def small_tiles(group, assets):
    """Малые тайлы образца по поверхностям: {"ground": {"pieces": [ключи], "flat": [ключи]}, "grass": {...}}.

    pieces — тайлы с прозрачными частями (угловые вырезы, мелкие фрагменты): ими рисуются границы.
    flat — полностью непрозрачные варианты тона: ими разнообразят основу. Поверхность без малых тайлов не попадает в результат.
    """
    from core.map_catalog import palette_group_layers

    result = {}
    for layer in palette_group_layers(group):
        if layer["role"] not in ("ground_small", "grass_small"):
            continue
        surface = "ground" if layer["role"] == "ground_small" else "grass"
        pieces, flat = [], []
        for _, key in sorted(layer["cells"].items(), key=lambda entry: (entry[0][1], entry[0][0])):
            target = flat if is_full(tile_shape(assets[key])[0]) else pieces
            if key not in target:
                target.append(key)
        result[surface] = {"pieces": pieces, "flat": flat}
    return result


def border_candidates(keys, assets, base_key):
    """Тайлы из keys с неполным покрытием и цветом, близким к base_key (трава): годятся как тайлы каймы.

    assets — {ключ: путь картинки относительно assets/map}.
    """
    base_colour = tile_shape(assets[base_key])[1]
    result = []
    for key in keys:
        coverage, colour = tile_shape(assets[key])
        distance = math.dist(colour, base_colour)
        if not is_full(coverage) and sum(coverage) > 0 and distance <= COLOR_DISTANCE_MAX:
            result.append((key, coverage))
    return result


def pick_border_tile(candidates, desired, rng, margin=TIE_MARGIN):
    """Ключ тайла, форма которого ближе всего к desired; среди почти равных по ошибке выбирается случайный."""
    errors = [(sum(abs(a - b) for a, b in zip(coverage, desired)), key) for key, coverage in candidates]
    best = min(error for error, _ in errors)
    return rng.choice([key for error, key in errors if error <= best + margin])
