"""Сборка гор и возвышенностей из тайлов образца: форма края, тип клетки и согласование соседей.

Горный массив состоит из плато (травяные тайлы сверху) и каменной стенки в WALL_ROWS строк под южным краем плато.
Для каждой клетки массива берутся тайлы своего типа (плато или стенка), форма которых по прозрачности ближе всего к
нужной (граница массива, как в terrain_autotile), затем соседи согласуются: сравниваются краевые пиксели тайлов
(форма и цвет), а пары, которые художник поставил рядом в образце, получают скидку. Тайлы с особенностями (камешки
на траве, тёмные пещеры) и тайлы другого тона выбираются реже. Результат зависит только от seed.

Pygame подключается внутри функций.
"""
import functools
import math

from core.map_catalog import MAP_ASSETS
from core.terrain_autotile import desired_coverage, tile_shape

SIDE = 32
WALL_ROWS = 2
ADJACENT_BONUS = 0.3
SHAPE_WEIGHT = 2.0
COLOUR_WEIGHT = 6.0
CANDIDATES = 14
SWEEPS = 50
START_TEMPERATURE = 0.2
OPAQUE_FROM = 127
UNKNOWN_EDGE = 0.35
OUTSIDE_MARGIN = 3
ROCK_REWARD = 2.5


def wall_below(plateau, rows=WALL_ROWS):
    """Клетки стенки: rows клеток под каждой южной границей плато."""
    wall = set()
    for x, y in plateau:
        if (x, y + 1) not in plateau:
            wall.update((x, y + step) for step in range(1, rows + 1))
    return wall - plateau


@functools.cache
def _pixels(asset):
    import pygame

    image = pygame.image.load(str(MAP_ASSETS / asset))
    return [[tuple(image.get_at((x, y))) for x in range(SIDE)] for y in range(SIDE)]


def _edges(pixels):
    return {
        "L": [pixels[y][0] for y in range(SIDE)],
        "R": [pixels[y][SIDE - 1] for y in range(SIDE)],
        "T": list(pixels[0]),
        "B": list(pixels[SIDE - 1]),
    }


def _edge_cost(first, second):
    """Различие двух краёв: несовпадение формы (непрозрачных пикселей) и цвета; край без пикселей — неизвестен."""
    mismatch = both = visible = 0
    colour = 0.0
    for a, b in zip(first, second):
        a_opaque, b_opaque = a[3] > OPAQUE_FROM, b[3] > OPAQUE_FROM
        visible += a_opaque or b_opaque
        if a_opaque != b_opaque:
            mismatch += 1
        elif a_opaque:
            both += 1
            colour += sum(abs(a[i] - b[i]) for i in range(3)) / 765
    if visible == 0:
        return UNKNOWN_EDGE
    return 2.0 * mismatch / SIDE + (colour / both if both else 0.0)


def _features(pixels, grass):
    """Доля «особенностей» тайла (камешки на траве, тёмные места) и его средний цвет."""
    opaque = rock = dark = 0
    sums = [0, 0, 0]
    for row in pixels:
        for r, g, b, a in row:
            if a <= OPAQUE_FROM:
                continue
            opaque += 1
            sums[0], sums[1], sums[2] = sums[0] + r, sums[1] + g, sums[2] + b
            rock += r > g + 8 and r > 100
            dark += (r + g + b) / 3 < 55
    opaque = max(opaque, 1)
    penalty = (2.5 * rock / opaque if grass else -ROCK_REWARD * rock / opaque) + 4.0 * dark / opaque
    return penalty, tuple(channel / opaque for channel in sums)


def _median_colour(colours):
    if not colours:
        return (0.0, 0.0, 0.0)
    ordered = sorted(colours, key=sum)
    return ordered[len(ordered) // 2]


class ReliefTiles:
    """Тайлы гор образца и таблицы их совместимости. plateau и wall — списки ключей, cells — {(x, y): ключ} образца."""

    def __init__(self, plateau, wall, assets, cells):
        self.plateau, self.wall = list(plateau), list(wall)
        keys = self.plateau + self.wall
        self.assets = assets
        self.shape = {key: tile_shape(assets[key])[0] for key in keys}
        edges = {key: _edges(_pixels(assets[key])) for key in keys}
        self.penalty, self.colour = {}, {}
        for key in keys:
            self.penalty[key], self.colour[key] = _features(_pixels(assets[key]), key in self.plateau)
        reference = {
            "plateau": _median_colour([self.colour[key] for key in self.plateau if self.penalty[key] < 0.05]),
            "wall": _median_colour([self.colour[key] for key in self.wall if self.penalty[key] < 0.05]),
        }
        self.tone = {
            key: COLOUR_WEIGHT * math.dist(self.colour[key], reference["plateau" if key in self.plateau else "wall"]) / 255
            for key in keys
        }
        self.horizontal = {a: {b: _edge_cost(edges[a]["R"], edges[b]["L"]) for b in keys} for a in keys}
        self.vertical = {a: {b: _edge_cost(edges[a]["B"], edges[b]["T"]) for b in keys} for a in keys}
        self.next_to, self.below = set(), set()
        for (x, y), key in cells.items():
            if key not in self.shape:
                continue
            right, down = cells.get((x + 1, y)), cells.get((x, y + 1))
            if right in self.shape:
                self.next_to.add((key, right))
            if down in self.shape:
                self.below.add((key, down))


def assemble(tiles, plateau, wall, rng, candidates=CANDIDATES, sweeps=SWEEPS):
    """{клетка: ключ тайла} для массива из клеток плато и стенки; клетки вне массива считаются пустыми."""
    footprint = plateau | wall
    if not footprint:
        return {}
    xs, ys = [x for x, _ in footprint], [y for _, y in footprint]
    outside = {
        (x, y)
        for x in range(min(xs) - OUTSIDE_MARGIN, max(xs) + OUTSIDE_MARGIN + 1)
        for y in range(min(ys) - OUTSIDE_MARGIN, max(ys) + OUTSIDE_MARGIN + 1)
    } - footprint
    domain = {}
    for cell in footprint:
        desired = desired_coverage(cell[0], cell[1], outside)
        pool = tiles.plateau if cell in plateau else tiles.wall
        ranked = sorted((sum(abs(a - b) for a, b in zip(tiles.shape[key], desired)), key) for key in pool)
        domain[cell] = [(SHAPE_WEIGHT * error + tiles.penalty[key] + tiles.tone[key], key) for error, key in ranked[:candidates]]
    state = {}

    def cost(cell, key, own):
        x, y = cell
        total = own
        for neighbour, horizontal, before in (
            ((x - 1, y), True, True), ((x + 1, y), True, False), ((x, y - 1), False, True), ((x, y + 1), False, False)
        ):
            other = state.get(neighbour)
            if other is None:
                continue
            first, second = (other, key) if before else (key, other)
            if horizontal:
                total += tiles.horizontal[first][second] - (ADJACENT_BONUS if (first, second) in tiles.next_to else 0.0)
            else:
                total += tiles.vertical[first][second] - (ADJACENT_BONUS if (first, second) in tiles.below else 0.0)
        return total

    order = sorted(footprint, key=lambda cell: (cell[1], cell[0]))
    for cell in order:
        scored = [(cost(cell, key, own), key) for own, key in domain[cell]]
        best = min(value for value, _ in scored)
        state[cell] = rng.choice([key for value, key in scored if value <= best + 0.05])
    for sweep in range(sweeps):
        temperature = START_TEMPERATURE * (1 - sweep / sweeps) + 0.01
        shuffled = order[:]
        rng.shuffle(shuffled)
        for cell in shuffled:
            scored = [(cost(cell, key, own), key) for own, key in domain[cell]]
            best = min(value for value, _ in scored)
            state[cell] = rng.choices([key for _, key in scored], [math.exp(-(value - best) / temperature) for value, _ in scored])[0]
    return state
