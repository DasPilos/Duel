"""Рельеф глобальной карты: хранится на сервере, клиент только рисует и учитывает непроходимость."""

import math
import random

from core.tile_mask import mask_blocks_rect, mask_free_point
from server import config


TILE = 32
# Мир «Башня» (WORLD_ID=2): карта 125x125 тайлов, башня в центре и дороги к ней
TOWER_WORLD_ID = 2
IS_TOWER_WORLD = config.WORLD_ID == TOWER_WORLD_ID
TOWER_TILES = 125
TOWER_CENTER_TILE = TOWER_TILES // 2
TOWER_HP = 1000
# Горный разлом: тайлы X 130..134, Y 95..102; проход к нему прорублен через южное подножие
RIFT_TILES = (130, 95, 5, 8)
RIFT_PASSAGE = (RIFT_TILES[0] * TILE, RIFT_TILES[1] * TILE, RIFT_TILES[2] * TILE, 3800 - RIFT_TILES[1] * TILE)
# Чёрная копь: тайлы X 133..141, Y 54..66; западный вход обращён к городу
BLACK_PIT_TILES = (133, 54, 9, 13)
BLACK_PIT_PASSAGES = (
    tuple(value * TILE for value in BLACK_PIT_TILES),
    (113 * TILE, 59 * TILE, 21 * TILE, 3 * TILE),
)


def tower_obstacle():
    """Башня 3x3 тайла в центре карты с прочностью."""
    left = (TOWER_CENTER_TILE - 1) * TILE
    right = (TOWER_CENTER_TILE + 2) * TILE
    return {
        "id": "tower_1", "type": "tower", "name": "Башня",
        "points": [(left, left), (right, left), (right, right), (left, right)],
        "passages": [], "hp": TOWER_HP, "max_hp": TOWER_HP,
    }


# Двор башни 57x57 тайлов и горный венец в квадрате 67x67 вокруг него: толщина неровная, от 0 до 5 тайлов,
# в каждой стороне ущелье 5 тайлов по центру
TOWER_YARD_HALF = 28
TOWER_RING_HALF = 33
TOWER_GORGE_HALF = 2
TOWER_RING_DEPTH = TOWER_RING_HALF - TOWER_YARD_HALF
# Внешняя дорога идёт за венцом, отступая на один тайл травы
TOWER_OUTER_ROAD_DISTANCE = TOWER_RING_HALF + 2
TOWER_MOUNTAIN_SEED = 131


def _ring_side_profiles(rng):
    """Для каждой стороны венца толщина по смещению от центра стороны: от 0 до 5 тайлов, с просветами 4–10 тайлов."""
    profiles = []
    for _ in range(4):
        thickness = rng.randint(2, 4)
        profile = {}
        for offset in range(-TOWER_RING_HALF, TOWER_RING_HALF + 1):
            if rng.random() < 0.3:
                step = 1 if thickness < 3 else -1 if thickness > 3 else rng.choice((-1, 1))
                if rng.random() < 0.25:
                    step = -step
                thickness = min(TOWER_RING_DEPTH, max(1, thickness + step))
            profile[offset] = thickness
        for _ in range(rng.randint(2, 3)):
            gap = rng.randint(4, 10)
            for _attempt in range(20):
                start = rng.randint(TOWER_GORGE_HALF + 2, TOWER_RING_HALF - gap)
                sign = rng.choice((-1, 1))
                # просветы не сливаются: между ними остаётся хотя бы один тайл венца
                if any(profile.get(sign * offset) == 0 for offset in range(start - 1, start + gap + 1)):
                    continue
                for offset in range(start, start + gap):
                    profile[sign * offset] = 0
                break
        profiles.append(profile)
    return profiles


def tower_mountain_tiles():
    """Горный венец: полоса неровной толщины вокруг двора, просветы и четыре открытых ущелья по центру сторон."""
    profiles = _ring_side_profiles(random.Random(TOWER_MOUNTAIN_SEED))
    tiles = set()
    for dx in range(-TOWER_RING_HALF, TOWER_RING_HALF + 1):
        for dy in range(-TOWER_RING_HALF, TOWER_RING_HALF + 1):
            reach = max(abs(dx), abs(dy))
            if reach <= TOWER_YARD_HALF:
                continue
            if abs(dy) >= abs(dx):
                side, along = (0 if dy < 0 else 1), dx
            else:
                side, along = (2 if dx < 0 else 3), dy
            if abs(along) <= TOWER_GORGE_HALF:
                continue
            # depth: 0 у внешнего края венца, растёт к двору
            if TOWER_RING_HALF - reach < profiles[side][along]:
                tiles.add((TOWER_CENTER_TILE + dx, TOWER_CENTER_TILE + dy))
    return frozenset(tiles)


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


def tower_road_tiles():
    """Дороги мира «Башня»: кольцо во дворе, кольцо за горным венцом и четыре оси от башни до края карты через ущелья."""
    centre = TOWER_CENTER_TILE
    ring_min, ring_max = centre - 3, centre + 3
    tiles = set()
    # Внутреннее кольцо во дворе: вокруг башни с зазором в один тайл
    for index in range(ring_min - 2, ring_max + 3):
        for depth in range(3):
            tiles.update({(index, ring_min - depth), (index, ring_max + depth),
                          (ring_min - depth, index), (ring_max + depth, index)})
    # Внешнее кольцо: три тайла дороги за венцом, по квадрату от центра карты
    for depth in range(TOWER_OUTER_ROAD_DISTANCE, TOWER_OUTER_ROAD_DISTANCE + 3):
        for index in range(centre - depth, centre + depth + 1):
            tiles.update({(index, centre - depth), (index, centre + depth),
                          (centre - depth, index), (centre + depth, index)})
    # Оси от башни до края карты; ядро с самой башней не занимаем
    core = range(centre - 1, centre + 2)
    for index in range(TOWER_TILES):
        if index in core:
            continue
        for offset in (-1, 0, 1):
            tiles.update({(centre + offset, index), (index, centre + offset)})
    return tuple(sorted(tiles, key=lambda tile: (tile[1], tile[0])))


# Лес и озёра мира «Башня»: пятна-эллипсы в тайлах (центр X, центр Y, полуось X, полуось Y), края неровные
TOWER_TERRAIN_SEED = 125
TOWER_PROP_SEED = 126
# Доля тайлов края леса, где стоит пень или лежит бревно
TOWER_STUMP_CHANCE = 0.2
TOWER_LOG_CHANCE = 0.06
TOWER_FOREST_BLOBS = ((8, 14, 6, 7), (7, 45, 5, 9), (9, 82, 6, 8), (40, 110, 10, 6),
                      (80, 111, 8, 6), (112, 40, 6, 9), (113, 84, 5, 8), (40, 14, 9, 6), (84, 14, 8, 6))
TOWER_LAKE_BLOBS = ((98, 20, 7, 5), (14, 104, 6, 5), (104, 104, 5, 4))
# Вокруг дорог и двора башни лес и вода не растут, чтобы путь к башне оставался открытым
TOWER_ROAD_CLEARANCE = 2
# Реки: исток на северном краю, устья в юго-западном и юго-восточном озёрах; начало, конец и ширина
TOWER_RIVER_SEED = 127
TOWER_RIVER_ROUTES = (((14, 0), (14, 104), 3), ((118, 0), (104, 104), 3))
# Пролёт моста: русло на дороге не шире 2 * TOWER_BRIDGE_HALF_SPAN + 1 тайлов, как спрайт моста художника
TOWER_BRIDGE_HALF_SPAN = 2
# Сухой лес по краю карты: глубина полосы и участки, которые чередуются с полянками
TOWER_DRY_SEED = 128
# Глубина сухой полосы меняется вдоль каждого края от минимума до максимума, поэтому край неровный
TOWER_DRY_MIN_DEPTH = 1
TOWER_DRY_MAX_DEPTH = 4
# Вдоль края лес идёт участками 10..40 тайлов, между участками полянки 10..40 тайлов
TOWER_DRY_SPAN_MIN = 10
TOWER_DRY_SPAN_MAX = 40
TOWER_GLADE_MIN = 10
TOWER_GLADE_MAX = 40
# Пни и брёвна на опушке сухого леса встречаются редко
TOWER_DRY_STUMP_CHANCE = 0.04
TOWER_DRY_LOG_CHANCE = 0.015
# Густой зелёный лес не подходит к воде ближе этого расстояния в тайлах (у гор будет так же)
TOWER_WATER_MARGIN = 3
# Полянки: одна в каждом лесном пятне и несколько на полях; от них тропинки к дорогам
TOWER_CLEARING_SEED = 129
TOWER_CLEARING_RADIUS = 3
TOWER_FIELD_CLEARINGS = 6
TOWER_FIELD_CLEARING_RADIUS = 2
TOWER_PATH_SEED = 130
TOWER_PATH_WOBBLE = 3
# Ширина тропинки в тайлах: художник рисует дороги не уже трёх тайлов
TOWER_PATH_WIDTHS = (3, 4, 5)


def _blob_tiles(rng, centre_x, centre_y, radius_x, radius_y):
    """Пятно тайлов с неровным краем: радиус меняется по углу, поэтому форма похожа на природную опушку или берег."""
    phase_a, phase_b = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
    tiles = set()
    for tile_y in range(max(0, centre_y - radius_y - 2), min(TOWER_TILES, centre_y + radius_y + 3)):
        for tile_x in range(max(0, centre_x - radius_x - 2), min(TOWER_TILES, centre_x + radius_x + 3)):
            dx = (tile_x - centre_x) / radius_x
            dy = (tile_y - centre_y) / radius_y
            angle = math.atan2(dy, dx)
            limit = 1 + 0.16 * math.sin(3 * angle + phase_a) + 0.1 * math.sin(5 * angle + phase_b)
            if math.hypot(dx, dy) <= limit:
                tiles.add((tile_x, tile_y))
    return tiles


def _tower_reserved_tiles():
    """Тайлы, где лес, вода и пни не растут: дороги с запасом, весь двор башни и сам горный венец."""
    reserved = set(TOWER_MOUNTAIN_TILES)
    for road_x, road_y in tower_road_tiles():
        for dx in range(-TOWER_ROAD_CLEARANCE, TOWER_ROAD_CLEARANCE + 1):
            for dy in range(-TOWER_ROAD_CLEARANCE, TOWER_ROAD_CLEARANCE + 1):
                reserved.add((road_x + dx, road_y + dy))
    for dx in range(-TOWER_YARD_HALF, TOWER_YARD_HALF + 1):
        for dy in range(-TOWER_YARD_HALF, TOWER_YARD_HALF + 1):
            reserved.add((TOWER_CENTER_TILE + dx, TOWER_CENTER_TILE + dy))
    return reserved


def _clearing_tiles(centre_x, centre_y, radius):
    """Полянка с неровным краем: пятно той же формы, что и опушки леса, а не круг."""
    rng = random.Random(TOWER_CLEARING_SEED * 1009 + centre_x * 131 + centre_y)
    return _blob_tiles(rng, centre_x, centre_y, radius, radius)


def _near_tiles(tiles, margin):
    """Тайлы в квадрате радиуса margin вокруг каждого из tiles."""
    near = set()
    for tile_x, tile_y in tiles:
        for dx in range(-margin, margin + 1):
            for dy in range(-margin, margin + 1):
                near.add((tile_x + dx, tile_y + dy))
    return near


def build_tower_clearings():
    """Полянки (центр X, центр Y, радиус): одна у каждого лесного пятна и несколько на полях вокруг башни."""
    rng = random.Random(TOWER_CLEARING_SEED)
    clearings = []
    for centre_x, centre_y, radius_x, radius_y in TOWER_FOREST_BLOBS:
        clearings.append((
            centre_x + rng.randint(-radius_x // 2, radius_x // 2),
            centre_y + rng.randint(-radius_y // 2, radius_y // 2),
            TOWER_CLEARING_RADIUS,
        ))
    for _ in range(TOWER_FIELD_CLEARINGS):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(14, 44)
        clearings.append((
            round(TOWER_CENTER_TILE + distance * math.cos(angle)),
            round(TOWER_CENTER_TILE + distance * math.sin(angle)),
            TOWER_FIELD_CLEARING_RADIUS,
        ))
    return tuple(clearings)


def _wobbly_line(rng, start, end):
    """Извилистая тропинка из тайлов: прямая от start к end, которая немного прогибается, и шаги только по сторонам тайла."""
    (start_x, start_y), (end_x, end_y) = start, end
    steps = max(abs(end_x - start_x), abs(end_y - start_y))
    if steps == 0:
        return {start}
    length = math.hypot(end_x - start_x, end_y - start_y)
    normal_x, normal_y = -(end_y - start_y) / length, (end_x - start_x) / length
    phase = rng.uniform(0, math.tau)
    points = []
    for step in range(steps + 1):
        t = step / steps
        bend = TOWER_PATH_WOBBLE * math.sin(math.pi * t) * math.sin(4 * math.pi * t + phase)
        points.append((
            round(start_x + (end_x - start_x) * t + normal_x * bend),
            round(start_y + (end_y - start_y) * t + normal_y * bend),
        ))
    tiles = set()
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        x, y = x1, y1
        tiles.add((x, y))
        while x != x2:
            x += 1 if x2 > x else -1
            tiles.add((x, y))
        while y != y2:
            y += 1 if y2 > y else -1
            tiles.add((x, y))
    return tiles


def build_tower_paths(clearings, water):
    """Тропинки от каждой полянки к ближайшей дороге; тропинка, упёршаяся в воду или горный венец, не строится."""
    rng = random.Random(TOWER_PATH_SEED)
    roads = tower_road_tiles()
    paths = set()
    for centre_x, centre_y, _ in clearings:
        target = min(roads, key=lambda tile: abs(tile[0] - centre_x) + abs(tile[1] - centre_y))
        line = _wobbly_line(rng, (centre_x, centre_y), target)
        # Тропинка от 3 до 5 тайлов шириной, ширина своя у каждой
        width = rng.choice(TOWER_PATH_WIDTHS)
        offsets = range(-(width // 2), width - width // 2)
        path = {(x + dx, y + dy) for x, y in line for dx in offsets for dy in offsets}
        if not path & (water | TOWER_MOUNTAIN_TILES):
            paths |= path
    return frozenset(paths)


def build_tower_terrain_tiles(rivers=frozenset(), bridges=(), clearings=()):
    """Тайлы леса и воды мира «Башня»: вода важнее леса, дороги, башня и их окрестности свободны."""
    reserved = _tower_reserved_tiles()
    rng = random.Random(TOWER_TERRAIN_SEED)
    water = set()
    for blob in TOWER_LAKE_BLOBS:
        water |= _blob_tiles(rng, *blob)
    forest = set()
    for blob in TOWER_FOREST_BLOBS:
        forest |= _blob_tiles(rng, *blob)
    water = (water - reserved) | rivers
    bridge_tiles = {tuple(tile) for bridge in bridges for tile in bridge["tiles"]}
    water -= bridge_tiles
    forest -= water
    forest -= _near_tiles(water, TOWER_WATER_MARGIN)
    for centre_x, centre_y, radius in clearings:
        forest -= _clearing_tiles(centre_x, centre_y, radius)
    return frozenset(forest - reserved), frozenset(water)


def _river_tiles(rng, start, end, width):
    """Русло реки от истока к устью: центр извивается синусами, ширина и сдвиг строк неравномерны, поэтому берега не ровные."""
    (start_x, start_y), (end_x, end_y) = start, end
    phase_a, phase_b, phase_c = (rng.uniform(0, math.tau) for _ in range(3))
    tiles = set()
    previous = start_x
    for tile_y in range(start_y, end_y + 1):
        t = (tile_y - start_y) / (end_y - start_y)
        centre = (start_x + (end_x - start_x) * t
                  + 5 * math.sin(3 * math.pi * t + phase_a) * math.sin(math.pi * t)
                  + 1.5 * math.sin(11 * t + phase_b))
        half = width / 2 + 0.6 * math.sin(7 * t + phase_c)
        for tile_x in range(math.floor(min(previous, centre) - half), math.ceil(max(previous, centre) + half)):
            tiles.add((tile_x, tile_y))
        previous = centre
    return tiles


def _road_river_groups(rivers):
    """Участки русла, лежащие на дороге: связные группы тайлов, каждая группа — одно пересечение и один мост."""
    crossing = rivers & frozenset(tower_road_tiles())
    groups, seen = [], set()
    for start in sorted(crossing, key=lambda tile: (tile[1], tile[0])):
        if start in seen:
            continue
        seen.add(start)
        group, stack = [], [start]
        while stack:
            tile_x, tile_y = stack.pop()
            group.append((tile_x, tile_y))
            for neighbour in ((tile_x + 1, tile_y), (tile_x - 1, tile_y), (tile_x, tile_y + 1), (tile_x, tile_y - 1)):
                if neighbour in crossing and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    return groups


def build_tower_rivers():
    """Реки от северного края к юго-западному озеру. На дороге русло сужается до пролёта моста: переход — это устье с одним мостом."""
    rng = random.Random(TOWER_RIVER_SEED)
    tiles = set()
    for start, end, width in TOWER_RIVER_ROUTES:
        tiles |= _river_tiles(rng, start, end, width)
    tiles -= TOWER_MOUNTAIN_TILES
    for group in _road_river_groups(frozenset(tiles)):
        centre = (min(tile_x for tile_x, _ in group) + max(tile_x for tile_x, _ in group)) // 2
        for tile in group:
            if abs(tile[0] - centre) > TOWER_BRIDGE_HALF_SPAN:
                tiles.discard(tile)
    return frozenset(tiles)


def build_tower_bridges(rivers):
    """Один мост на каждое пересечение реки с дорогой: пролёт занимает всё русло на дороге, сухие тайлы дороги остаются проходимыми."""
    return tuple(
        {"tiles": [list(tile) for tile in sorted(group, key=lambda tile: (tile[1], tile[0]))]}
        for group in _road_river_groups(rivers)
    )


def _dry_spans(rng):
    """Вдоль одного края чередуются участки сухого леса (10..40 тайлов) и полянки (10..40 тайлов). True — лес."""
    has_forest = [False] * TOWER_TILES
    position = rng.randint(0, TOWER_GLADE_MAX)
    while position < TOWER_TILES:
        length = rng.randint(TOWER_DRY_SPAN_MIN, TOWER_DRY_SPAN_MAX)
        for along in range(position, min(TOWER_TILES, position + length)):
            has_forest[along] = True
        position += length + rng.randint(TOWER_GLADE_MIN, TOWER_GLADE_MAX)
    return has_forest


def _dry_depths(rng):
    """Глубина сухой полосы вдоль одной стороны: случайное блуждание внутри участков леса, на полянках полосы нет."""
    has_forest = _dry_spans(rng)
    depths = []
    depth = (TOWER_DRY_MIN_DEPTH + TOWER_DRY_MAX_DEPTH) // 2
    for forest_here in has_forest:
        depth = min(TOWER_DRY_MAX_DEPTH, max(TOWER_DRY_MIN_DEPTH, depth + rng.choice((-1, 0, 0, 1))))
        depths.append(depth if forest_here else 0)
    return depths


def build_tower_dry_forest(forest, water, paths):
    """Сухой лес участками по краю карты, между участками полянки. Дороги и реки уже открыты."""
    reserved = _tower_reserved_tiles()
    rng = random.Random(TOWER_DRY_SEED)
    last = TOWER_TILES - 1
    top, bottom, left, right = (_dry_depths(rng) for _ in range(4))
    dry = {
        (tile_x, tile_y) for tile_x in range(TOWER_TILES) for tile_y in range(TOWER_TILES)
        if (tile_y < top[tile_x] or last - tile_y < bottom[tile_x]
            or tile_x < left[tile_y] or last - tile_x < right[tile_y])
    }
    return frozenset(dry - reserved - forest - water - paths)


def build_tower_props(forest, water, occupied=frozenset(), stump_chance=TOWER_STUMP_CHANCE, log_chance=TOWER_LOG_CHANCE):
    """Пни и брёвна у края леса: непроходимы, как деревья. Бревно занимает два тайла по горизонтали."""
    reserved = _tower_reserved_tiles()
    edge = set()
    for tile_x, tile_y in forest:
        for tile in ((tile_x, tile_y - 1), (tile_x, tile_y + 1), (tile_x + 1, tile_y), (tile_x - 1, tile_y)):
            if (tile not in forest and tile not in water and tile not in occupied and tile not in reserved
                    and 0 <= tile[0] < TOWER_TILES and 0 <= tile[1] < TOWER_TILES):
                edge.add(tile)
    rng = random.Random(TOWER_PROP_SEED)
    props, used = [], set()
    for tile in sorted(edge, key=lambda item: (item[1], item[0])):
        if tile in used:
            continue
        right = (tile[0] + 1, tile[1])
        if right in edge and right not in used and rng.random() < log_chance:
            props.append({"type": "log", "tiles": [list(tile), list(right)]})
            used.update({tile, right})
        elif rng.random() < stump_chance:
            props.append({"type": "stump", "tiles": [list(tile)]})
            used.add(tile)
    return tuple(props)


if IS_TOWER_WORLD:
    TOWER_MOUNTAIN_TILES = tower_mountain_tiles()
    TOWER_RIVERS = build_tower_rivers()
    TOWER_BRIDGES = build_tower_bridges(TOWER_RIVERS)
    TOWER_CLEARINGS = build_tower_clearings()
    TOWER_FOREST_TILES, TOWER_WATER_TILES = build_tower_terrain_tiles(TOWER_RIVERS, TOWER_BRIDGES, TOWER_CLEARINGS)
    TOWER_PATH_TILES = build_tower_paths(TOWER_CLEARINGS, TOWER_WATER_TILES)
    TOWER_FOREST_TILES = frozenset(TOWER_FOREST_TILES - TOWER_PATH_TILES)
    TOWER_DRY_TILES = build_tower_dry_forest(TOWER_FOREST_TILES, TOWER_WATER_TILES, TOWER_PATH_TILES)
    forest_props = build_tower_props(TOWER_FOREST_TILES, TOWER_WATER_TILES, TOWER_DRY_TILES | TOWER_PATH_TILES)
    forest_prop_tiles = frozenset(tuple(tile) for prop in forest_props for tile in prop["tiles"])
    dry_props = build_tower_props(
        TOWER_DRY_TILES, TOWER_WATER_TILES, TOWER_FOREST_TILES | TOWER_PATH_TILES | forest_prop_tiles,
        TOWER_DRY_STUMP_CHANCE, TOWER_DRY_LOG_CHANCE,
    )
    TOWER_PROPS = forest_props + dry_props
else:
    TOWER_MOUNTAIN_TILES = frozenset()
    TOWER_RIVERS = frozenset()
    TOWER_BRIDGES = ()
    TOWER_CLEARINGS = ()
    TOWER_FOREST_TILES = frozenset()
    TOWER_WATER_TILES = frozenset()
    TOWER_PATH_TILES = frozenset()
    TOWER_DRY_TILES = frozenset()
    TOWER_PROPS = ()
TOWER_BERRY_TILES = frozenset()
TOWER_FLOOR_TILES = frozenset()
TOWER_IMPASSABLE_TILES = frozenset()
TOWER_PARTIAL_MASKS = {}
TOWER_PROP_TILES = frozenset(tuple(tile) for prop in TOWER_PROPS for tile in prop["tiles"])
TOWER_BLOCKED_TILES = TOWER_FOREST_TILES | TOWER_WATER_TILES | TOWER_DRY_TILES | TOWER_PROP_TILES | TOWER_MOUNTAIN_TILES


def rect_touches_blocked_tile(rect):
    """Пересекает ли прямоугольник (x, y, ширина, высота) тайл леса, воды или пня и бревна; правый и нижний край не считаются."""
    if not TOWER_BLOCKED_TILES and not TOWER_PARTIAL_MASKS:
        return False
    x, y, width, height = rect
    for tile_y in range(y // TILE, (y + height - 1) // TILE + 1):
        for tile_x in range(x // TILE, (x + width - 1) // TILE + 1):
            mask = TOWER_PARTIAL_MASKS.get((tile_x, tile_y))
            if mask is not None:
                if mask_blocks_rect(mask, tile_x, tile_y, TILE, x, y, x + width, y + height):
                    return True
            elif (tile_x, tile_y) in TOWER_BLOCKED_TILES:
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


MAP_TILES_W = TOWER_TILES if IS_TOWER_WORLD else 512
MAP_TILES_H = TOWER_TILES if IS_TOWER_WORLD else 256
# Точка появления игрока: в мире «Башня» на южной дороге, а не в центре, где стоит башня
MAP_SPAWN_PX = (
    (TOWER_CENTER_TILE * TILE + TILE // 2, (TOWER_CENTER_TILE + 28) * TILE + TILE // 2)
    if IS_TOWER_WORLD else (MAP_TILES_W * TILE // 2, MAP_TILES_H * TILE // 2)
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

_WORLD_OBSTACLES = (
    _massif("mountains_1", "Горы", MASSIF_OUTLINE, seed=3694, passages=(RIFT_PASSAGE, *BLACK_PIT_PASSAGES)),
    _forest("forest_1", "Лес", ((2063, 3464), (741, 3506), (498, 2964), (1778, 2611), (3087, 2883)), seed=2063),
    _lake("lake_1", "Озеро", ((40, 26), (62, 38), (98, 33), (102, 17), (83, 19), (74, 24), (61, 27)), seed=402638),
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


TOWER_MOUNTAIN_OBSTACLES = (
    tuple(_mountain_obstacle(index, rect) for index, rect in enumerate(_tile_rects(TOWER_MOUNTAIN_TILES)))
    if IS_TOWER_WORLD else ()
)
OBSTACLES = (tower_obstacle(), *TOWER_MOUNTAIN_OBSTACLES) if IS_TOWER_WORLD else _WORLD_OBSTACLES
# Публикация из редактора: размер карты, точка появления и метка публикации (для опроса БД)
LIVE_MAP = False
PUBLISHED_AT = None
# Рельеф и размер, которые подменяет карта из редактора; процедурные значения сохраняем для возврата
_TERRAIN_NAMES = (
    "TOWER_FOREST_TILES", "TOWER_WATER_TILES", "TOWER_DRY_TILES", "TOWER_PATH_TILES", "TOWER_MOUNTAIN_TILES",
    "TOWER_BERRY_TILES", "TOWER_FLOOR_TILES", "TOWER_PROPS", "TOWER_BRIDGES", "TOWER_PROP_TILES", "TOWER_BLOCKED_TILES", "TOWER_IMPASSABLE_TILES", "TOWER_PARTIAL_MASKS", "TOWER_MOUNTAIN_OBSTACLES", "OBSTACLES",
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
    partial_tiles = frozenset(partial_masks)
    props = tuple(terrain["props"])
    bridges = tuple(terrain["bridges"])
    prop_tiles = frozenset(tuple(tile) for prop in props for tile in prop["tiles"])
    mountain_obstacles = tuple(
        _mountain_obstacle(index, rect) for index, rect in enumerate(_tile_rects(mountain - partial_tiles))
    )
    # Здание башни остаётся на её карте; на остальных опубликованных картах препятствия только горы из клеток
    obstacles = (tower_obstacle(), *mountain_obstacles) if IS_TOWER_WORLD else mountain_obstacles
    blocked = (forest | dry | water | prop_tiles | mountain | impassable) - partial_tiles
    map_w, map_h = published["map_w"], published["map_h"]
    return {
        "TOWER_FOREST_TILES": forest,
        "TOWER_WATER_TILES": water,
        "TOWER_DRY_TILES": dry,
        "TOWER_PATH_TILES": paths,
        "TOWER_MOUNTAIN_TILES": mountain,
        "TOWER_IMPASSABLE_TILES": impassable,
        "TOWER_PARTIAL_MASKS": partial_masks,
        "TOWER_BERRY_TILES": berry,
        "TOWER_FLOOR_TILES": floor,
        "TOWER_PROPS": props,
        "TOWER_BRIDGES": bridges,
        "TOWER_PROP_TILES": prop_tiles,
        "TOWER_BLOCKED_TILES": blocked,
        "TOWER_MOUNTAIN_OBSTACLES": mountain_obstacles,
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
    return _passable_at(x, y, TOWER_BLOCKED_TILES, OBSTACLES, TOWER_PARTIAL_MASKS)


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
    from server.structures import world_structures
    from server.world_roads import roads_payload

    return {"map": {"tiles_w": MAP_TILES_W, "tiles_h": MAP_TILES_H, "uniform_grass": IS_TOWER_WORLD or LIVE_MAP,
                    "spawn": list(MAP_SPAWN_PX), "version": TERRAIN_VERSION},
            "tiles": {"forest": _tile_rows(TOWER_FOREST_TILES), "water": _tile_rows(TOWER_WATER_TILES),
                      "dry": _tile_rows(TOWER_DRY_TILES), "paths": _tile_rows(TOWER_PATH_TILES),
                      "mountain": _tile_rows(TOWER_MOUNTAIN_TILES), "impassable": _tile_rows(TOWER_IMPASSABLE_TILES),
                      "berry": _tile_rows(TOWER_BERRY_TILES), "floor": _tile_rows(TOWER_FLOOR_TILES),
                      "partial": [[x, y, mask] for (x, y), mask in sorted(TOWER_PARTIAL_MASKS.items())]},
            "props": [dict(prop) for prop in TOWER_PROPS],
            "bridges": [dict(bridge) for bridge in TOWER_BRIDGES],
            "obstacles": [dict(obstacle) for obstacle in OBSTACLES],
            **world_structures(city_level), "roads": roads_payload(city_level)}
