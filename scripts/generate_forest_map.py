"""Генератор лесной карты по шаблону зон. Результат сохраняется черновиком редактора карт.

Шаблон (расстояния считаются от центра карты по неровной линии, а не по кругу; границы зон меняются
по направлению в пределах диапазона):
  1. Поляна        — до 10–20 тайлов: открытая трава, здесь встречаются четыре дороги, редкие кусты и ягоды.
  2. Огромный лес  — до 15–30 тайлов: огромные деревья стоят в шахматном порядке, лес непроходим.
                     Дороги прорезают его насквозь.
  3. Малый лес     — до 20–40 тайлов: проходимый лес из небольших деревьев, чаще зелёных; опушки,
                     поляны, кусты и ягоды.
  Дальше           — редкие одинокие сухие деревья, пни и сухие кусты.

Земля и трава берутся из образца ландшафта по соглашению слоёв: основа из 9 базовых тайлов блоков 5 и 6
в случайном порядке, а декор из блоков 1–4 случайно (около 10% клеток) и не ближе 3 клеток друг к другу.
У «Лесного ландшафта» два шаблона: первый (dry) — сухой лес с большими и маленькими пнями, второй (live) — живой лес.
Сухой шаблон ложится за зонами и пятнами в малом лесу (с пнями, сухими деревьями и кустами), живой — на остальную карту.

Пример: python -m scripts.generate_forest_map --name "Лес по шаблону 64"
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
    MAP_ASSETS,
    catalog_definitions,
    decor_spaced,
    overlay_keys,
    TALL_ROLES,
    palette_group_decor,
    palette_group_layers,
    palette_landscape,
    pick_decor,
    tile_allows_objects,
)
from core.relief_tiling import WALL_ROWS, ReliefTiles, assemble, wall_below
from core.terrain_autotile import border_candidates, desired_coverage, is_full, pick_border_tile, small_tiles
from server.map_editor import terrain_from_cells, validate_cells

SIZE = 64
SEED = 64
DEFAULT_NAME = "Лес по шаблону 64"
LANDSCAPE = "Лесной ландшафт"
# Внешние границы зон: диапазон расстояния от центра в тайлах.
GLADE_RANGE = (10, 20)
GIANT_RANGE = (15, 30)
GROVE_RANGE = (20, 40)
ZONE_GAP = 3
ROAD_MARGIN = 2
BERRY_SHARE = 0.05
GIANT_ALIVE = ("dec_004", "dec_005", "dec_006", "big_tree")
GIANT_DEAD = ("dec_001", "dec_002", "dec_003")
LANDMARK = "dec_027"
BIG_STUMPS = ("dec_009", "dec_010")
SMALL_STUMPS = ("dec_093", "dec_098")
# Пятна сухого леса внутри малого леса: шум выше порога.
DRY_PATCH_THRESHOLD = 0.68
LANDMARKS = 2
SMALL_ALIVE = ("tree1", "tree2", "tree3")
SMALL_DEAD = ("old_tree1", "old_tree2", "old_tree3")
# Холмы слоя 3 из блоков возвышенности образца: плато (левый блок 5×5) и впадина (правый).
HILL_PLATEAUS = 5
HILL_PITS = 3
HILL_SIDE = 5
HILL_ROAD_MARGIN = 3
HILL_ZONES = ("grove", "outer")
# Горные массивы слоя 4: плато и каменная стенка под ним, собираются по форме и совместимости краёв.
MASSIFS = 3
MASSIF_WIDTH = (6, 10)
MASSIF_HEIGHT = (3, 4)
MASSIF_ROAD_MARGIN = 3
MASSIF_ATTEMPTS = 800
MASSIF_ZONES = ("grove", "outer")
# Пятна голой земли на траве: кайма по форме из малых тайлов, плоские варианты тона из блоков малых тайлов.
EARTH_PATCHES = 16
EARTH_PATCH_MIN = 3
EARTH_PATCH_MAX = 9
EARTH_PATCH_MARGIN = 3
TONE_THRESHOLD = 0.64


def _hash(x, y, salt=0):
    return ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0x7FFFFFFF


def _smooth(t):
    return t * t * (3 - 2 * t)


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


class _Noise:
    def __init__(self, seed):
        self.seed = seed
        self.lattice = {}

    def _point(self, ix, iy, octave):
        key = (ix, iy, octave)
        if key not in self.lattice:
            self.lattice[key] = random.Random(_hash(ix, iy, octave + self.seed)).random()
        return self.lattice[key]

    def __call__(self, x, y, scale, octave):
        fx, fy = x / scale, y / scale
        ix, iy = math.floor(fx), math.floor(fy)
        tx, ty = _smooth(fx - ix), _smooth(fy - iy)
        a, b = self._point(ix, iy, octave), self._point(ix + 1, iy, octave)
        c, d = self._point(ix, iy + 1, octave), self._point(ix + 1, iy + 1, octave)
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def _berry_share(asset):
    image = pygame.image.load(str(MAP_ASSETS / asset))
    covered = berries = 0
    red = green = 0
    for x in range(image.get_width()):
        for y in range(image.get_height()):
            r, g, b, a = image.get_at((x, y))
            if a < 128:
                continue
            covered += 1
            red, green = red + r, green + g
            if (r > g + 45 and r > 110 and b < r - 20) or (r > 150 and g > 130 and b < 100 and abs(r - g) < 90):
                berries += 1
    covered = max(covered, 1)
    return berries / covered, red / covered, green / covered


def _bush_groups(items):
    """Кусты по виду: зелёные, ягодные (много красных и жёлтых пикселей) и сухие."""
    green, berry, dry = [], [], []
    for key in sorted(k for k, item in items.items() if item["category"] == "bush"):
        share, red, grn = _berry_share(items[key]["asset"])
        if grn < red * 1.05:
            dry.append(key)
        elif share >= BERRY_SHARE:
            berry.append(key)
        else:
            green.append(key)
    return green, berry, dry


class _ZoneShape:
    """Неровные внешние границы зон: радиус зависит от направления и лежит в заданном диапазоне."""

    def __init__(self, rng):
        self.waves = []
        for low, high in (GLADE_RANGE, GIANT_RANGE, GROVE_RANGE):
            phases = [rng.uniform(0, math.tau) for _ in range(3)]
            self.waves.append((low, high, phases))

    def radii(self, angle):
        radii = []
        for low, high, (p1, p2, p3) in self.waves:
            shape = 0.55 * math.sin(2 * angle + p1) + 0.30 * math.sin(3 * angle + p2) + 0.15 * math.sin(5 * angle + p3)
            radii.append(low + (high - low) * (0.5 + 0.5 * shape))
        glade = radii[0]
        giant = max(radii[1], glade + ZONE_GAP)
        grove = max(radii[2], giant + ZONE_GAP)
        return glade, giant, grove


def _carve_roads(size, rng, noise, centre, plaza):
    road = set()

    def disc(cx, cy, radius):
        for x in range(max(0, int(cx - radius) - 1), min(size, int(cx + radius) + 2)):
            for y in range(max(0, int(cy - radius) - 1), min(size, int(cy + radius) + 2)):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= radius * radius:
                    road.add((x, y))

    corners = [(1.5, 1.5), (size - 1.5, 1.5), (1.5, size - 1.5), (size - 1.5, size - 1.5)]
    for index, (sx, sy) in enumerate(corners):
        dx, dy = centre[0] - sx, centre[1] - sy
        length = math.hypot(dx, dy)
        px, py = -dy / length, dx / length
        amplitude = rng.uniform(5.5, 8.5)
        waves = rng.choice((1.5, 2.0, 2.5))
        phase = rng.uniform(0, math.tau)
        second, phase2 = rng.uniform(1.0, 2.2), rng.uniform(0, math.tau)
        steps = int(length * 6)
        for i in range(steps + 1):
            s = i / steps
            bend = math.sin(math.pi * s) ** 0.8
            offset = bend * (amplitude * math.sin(math.tau * waves * s + phase) + second * math.sin(math.tau * 4 * s + phase2))
            x = _clamp(sx + dx * s + px * offset, 1.0, size - 1.0)
            y = _clamp(sy + dy * s + py * offset, 1.0, size - 1.0)
            disc(x, y, 1.05 + 0.30 * noise(x, y, 7, 3 + index))
    disc(centre[0], centre[1], plaza)
    for _ in range(8):
        changed = False
        for x in range(size):
            for y in range(size):
                around = [(x, y - 1) in road, (x, y + 1) in road, (x - 1, y) in road, (x + 1, y) in road]
                if (x, y) not in road and ((around[0] and around[1]) or (around[2] and around[3]) or sum(around) >= 3):
                    road.add((x, y))
                    changed = True
        if not changed:
            break
    return road


def _earth_patches(rng, size, zones, road):
    """Пятна голой земли: небольшие группы клеток вдали от дорог, друг от друга и от огромного леса."""
    patches = set()
    margin = range(-EARTH_PATCH_MARGIN, EARTH_PATCH_MARGIN + 1)

    def fits(blob):
        for x, y in blob:
            if not (2 <= x < size - 2 and 2 <= y < size - 2):
                return False
            if any(
                zones.get((x + dx, y + dy)) == "giant" or (x + dx, y + dy) in road or (x + dx, y + dy) in patches
                for dx in margin for dy in margin
            ):
                return False
        return True

    for _ in range(EARTH_PATCHES):
        for _ in range(80):
            blob = {(rng.randrange(3, size - 3), rng.randrange(3, size - 3))}
            for _ in range(rng.randint(EARTH_PATCH_MIN, EARTH_PATCH_MAX) * 3):
                if len(blob) >= EARTH_PATCH_MAX or len(blob) >= EARTH_PATCH_MIN and rng.random() < 0.15:
                    break
                x, y = rng.choice(sorted(blob))
                blob.add(rng.choice(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))))
            if len(blob) >= EARTH_PATCH_MIN and fits(blob):
                patches |= blob
                break
    return patches


class _Template:
    """Тайлы одного образца-шаблона: основа и декор земли и травы, кайма, плоские тона, слои возвышенности и гор."""

    def __init__(self, group, assets):
        self.layers = {layer["role"]: layer for layer in palette_group_layers(group)}
        decor = palette_group_decor(group)
        self.base_ground, self.base_grass = (decor.get(name, {}).get("base", []) for name in ("ground", "grass"))
        self.decor_ground, self.decor_grass = (decor.get(name, {}).get("decor", []) for name in ("ground", "grass"))
        if not self.base_ground or not self.base_grass:
            raise SystemExit(f"В образце «{group['title']}» нет базовых тайлов земли или травы")
        tall = {key for role in TALL_ROLES if role in self.layers for key in self.layers[role]["cells"].values()}
        keys = sorted({cell["key"] for cell in group["cells"]} - tall)
        self.border = border_candidates(keys, assets, self.base_grass[0])
        small = small_tiles(group, assets)
        self.flat_ground, self.flat_grass = small.get("ground", {}).get("flat", []), small.get("grass", {}).get("flat", [])


def _hill_stamps(layers):
    """Штампы холмов {(dx, dy): ключ}: плато и впадина из блоков возвышенности образца (пусто, если слоя нет)."""
    elevation = layers.get("elevation")
    if elevation is None:
        return []
    top = elevation["y"]

    def block(left):
        return {
            (x - left, y - top): key
            for (x, y), key in elevation["cells"].items()
            if left <= x < left + HILL_SIDE and top <= y < top + HILL_SIDE
        }

    return [block(elevation["x"]), block(elevation["x"] + HILL_SIDE)]


def _place_massifs(rng, size, tiles, zones, road_distance, taken):
    """Горные массивы [{клетка: ключ}]: плато с неровными верхними углами и стенка под ним, вдали от дорог и друг от друга."""
    placed = []
    for _ in range(MASSIFS):
        for _ in range(MASSIF_ATTEMPTS):
            width, height = rng.randint(*MASSIF_WIDTH), rng.randint(*MASSIF_HEIGHT)
            plateau = {(x, y) for x in range(width) for y in range(height)}
            for corner in ((0, 0), (width - 1, 0)):
                if rng.random() < 0.7:
                    plateau.discard(corner)
            x0 = rng.randrange(1, size - width - 1)
            y0 = rng.randrange(1, size - height - WALL_ROWS - 1)
            plateau = {(x0 + x, y0 + y) for x, y in plateau}
            wall = wall_below(plateau)
            cells = plateau | wall
            margin = {(x + dx, y + dy) for x, y in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            if margin & taken:
                continue
            if any(zones.get(cell) not in MASSIF_ZONES or road_distance.get(cell, 0) < MASSIF_ROAD_MARGIN for cell in cells):
                continue
            taken |= margin
            placed.append(assemble(tiles, plateau, wall, rng))
            break
    return placed


def _place_hills(rng, size, stamps_at, zones, road_distance, taken):
    """Места холмов [(x, y, штамп)]: вдали от дорог и друг от друга, только в малом лесу и за ним.

    stamps_at(x, y) возвращает пару штампов (плато, впадина) шаблона в этом месте.
    """
    placed = []
    for index, count in enumerate((HILL_PLATEAUS, HILL_PITS)):
        for _ in range(400):
            if count == 0:
                break
            x, y = rng.randrange(1, size - HILL_SIDE - 1), rng.randrange(1, size - HILL_SIDE - 1)
            body = [(x + dx, y + dy) for dx in range(HILL_SIDE) for dy in range(HILL_SIDE)]
            margin = [(x + dx, y + dy) for dx in range(-1, HILL_SIDE + 1) for dy in range(-1, HILL_SIDE + 1)]
            if any(cell in taken for cell in margin):
                continue
            if any(zones[cell] not in HILL_ZONES or road_distance[cell] < HILL_ROAD_MARGIN for cell in body):
                continue
            taken.update(margin)
            placed.append((x, y, stamps_at(x, y)[index]))
            count -= 1
    return placed


def _distances(size, road):
    distance = {cell: 0 for cell in road}
    queue = deque(road)
    while queue:
        cx, cy = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (cx + dx, cy + dy)
                if 0 <= cell[0] < size and 0 <= cell[1] < size and cell not in distance:
                    distance[cell] = distance[(cx, cy)] + 1
                    queue.append(cell)
    return distance


def generate(size=SIZE, seed=SEED, landscape=LANDSCAPE):
    """Клетки карты по шаблону и сведения о ней: (cells, stats). landscape — название образца в палитре."""
    pygame.init()
    rng = random.Random(seed)
    noise = _Noise(seed)
    catalog = catalog_definitions()
    items = {item["item_key"]: item for item in catalog}
    for key in GIANT_ALIVE + GIANT_DEAD + (LANDMARK,) + SMALL_ALIVE + SMALL_DEAD:
        assert items[key]["blocks"], key

    groups = palette_landscape(landscape)
    if not groups or any(group.get("layout") != 2 for group in groups.values()):
        raise SystemExit(f"Образца «{landscape}» с раскладкой 2 нет в палитре")
    assets = {key: item["asset"] for key, item in items.items()}
    # Кайма травы берётся по форме из всех подходящих тайлов образца, кроме высоких слоёв (возвышенность, реки, горы).
    templates = {name: _Template(group, assets) for name, group in groups.items()}
    dry_template = templates.get("dry")
    live_template = templates.get("live") or templates.get("main") or next(iter(templates.values()))
    elevation_stamps = {name: _hill_stamps(template.layers) for name, template in templates.items()}
    stamp_pairs = [pair for pair in elevation_stamps.values() if pair]
    green, berry, dry = _bush_groups(items)
    centre = (size / 2, size / 2)
    shape = _ZoneShape(rng)
    road = _carve_roads(size, rng, noise, centre, plaza=3.0)
    road_distance = _distances(size, road)

    def place(x, y):
        dx, dy = x + 0.5 - centre[0], y + 0.5 - centre[1]
        glade, giant, grove = shape.radii(math.atan2(dy, dx))
        return math.hypot(dx, dy), glade, giant, grove

    def zone(x, y):
        distance, glade, giant, grove = place(x, y)
        return "glade" if distance < glade else "giant" if distance < giant else "grove" if distance < grove else "outer"

    objects = {}
    trees = set(GIANT_ALIVE + GIANT_DEAD + (LANDMARK,) + SMALL_ALIVE + SMALL_DEAD)

    def near_tree(x, y, reach):
        return any(objects.get((x + dx, y + dy)) in trees for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1))

    cells_order = [(x, y) for x in range(size) for y in range(size)]
    rng.shuffle(cells_order)
    zones = {cell: zone(*cell) for cell in cells_order}
    dry_cells = {
        (x, y) for (x, y), name in zones.items()
        if dry_template and (name == "outer" or (name == "grove" and noise(x, y, 9, 71) > DRY_PATCH_THRESHOLD))
    }

    def template_at(x, y):
        return dry_template if (x, y) in dry_cells else live_template

    def stamps_at(x, y):
        template_name = "dry" if (x + 2, y + 2) in dry_cells else "live" if "live" in templates else "main"
        return elevation_stamps.get(template_name) or stamp_pairs[0]
    patches = _earth_patches(rng, size, zones, road)
    road |= patches
    road_distance = _distances(size, road)

    # Зона 2: огромные деревья в шахматном порядке перекрывают проход, дороги остаются просеками.
    giants = [cell for cell in cells_order if zones[cell] == "giant" and road_distance[cell] >= ROAD_MARGIN and sum(cell) % 2 == 0]
    for x, y in giants:
        objects[(x, y)] = rng.choice(GIANT_DEAD if rng.random() < 0.28 else GIANT_ALIVE)
    deep = [cell for cell in giants if road_distance[cell] >= 6]
    for cell in rng.sample(deep, min(LANDMARKS, len(deep))):
        objects[cell] = LANDMARK

    # Зона 3: проходимый малый лес с опушками.
    for x, y in cells_order:
        cell = (x, y)
        if zones[cell] != "grove" or road_distance[cell] < ROAD_MARGIN:
            continue
        distance, _, giant, grove = place(x, y)
        depth = (distance - giant) / (grove - giant)
        glade_patch = noise(x, y, 6, 51) > 0.62
        on_edge = min(depth, 1 - depth) < 0.18
        density = _clamp(0.30 + 0.60 * noise(x, y, 11, 31)) * (0.5 if on_edge else 1.0)
        if glade_patch or rng.random() > density:
            continue
        if near_tree(x, y, 2 if density > 0.45 else 3):
            continue
        alive = rng.random() < 0.9 - 0.4 * depth and cell not in dry_cells
        objects[cell] = rng.choice(SMALL_ALIVE if alive else SMALL_DEAD)

    # Сухой лес (первый шаблон): сухие деревья, большие и маленькие пни, сухие кусты.
    for x, y in cells_order:
        cell = (x, y)
        if cell not in dry_cells or road_distance[cell] < ROAD_MARGIN or cell in objects:
            continue
        roll = rng.random()
        if roll < 0.025 and not near_tree(x, y, 3):
            objects[cell] = rng.choice(SMALL_DEAD)
        elif roll < 0.05:
            objects[cell] = rng.choice(BIG_STUMPS)
        elif roll < 0.09:
            objects[cell] = rng.choice(SMALL_STUMPS)
        elif roll < 0.14:
            objects[cell] = rng.choice(dry)

    # Растения: кусты и ягоды на опушках, полянах и поляне в центре.
    for x, y in cells_order:
        cell = (x, y)
        if cell in objects or zones[cell] not in ("glade", "grove") or road_distance[cell] < ROAD_MARGIN:
            continue
        distance, _, giant, grove = place(x, y)
        near_edge = zones[cell] == "grove" and min(distance - giant, grove - distance) < 3
        clearing = zones[cell] == "grove" and noise(x, y, 6, 51) > 0.62
        chance = 0.025 if zones[cell] == "glade" else 0.22 if clearing or near_edge else 0.07
        if rng.random() < chance:
            objects[cell] = rng.choice(berry if rng.random() < 0.4 else green)

    # Горные массивы слоя 4 и холмы слоя 3 (если в образце есть такие слои): деревья и кусты убираются с запасом в клетку.
    mountain = next((t.layers["mountain"] for t in templates.values() if "mountain" in t.layers), None)
    relief = None
    if mountain is not None:
        keys = sorted(set(mountain["cells"].values()))
        plateau_keys = [key for key in keys if items[key]["category"] == "grass"]
        relief = ReliefTiles(
            plateau_keys, [key for key in keys if key not in plateau_keys], assets, dict(mountain["cells"])
        )
    taken = set()
    massifs = _place_massifs(rng, size, relief, zones, road_distance, taken) if relief else []
    hills = _place_hills(rng, size, stamps_at, zones, road_distance, taken) if stamp_pairs else []
    for x, y, _ in hills:
        for dx in range(-1, HILL_SIDE + 1):
            for dy in range(-1, HILL_SIDE + 1):
                objects.pop((x + dx, y + dy), None)
    for state in massifs:
        for x, y in state:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    objects.pop((x + dx, y + dy), None)

    # Тайлы: земля везде, трава поверх земли везде кроме дорог; декор добавляется случайно по формуле.
    ground_decor, grass_decor = {}, {}
    ground_choice, grass_choice = {}, {}
    for x, y in cells_order:
        template = template_at(x, y)
        if (x, y) in road:
            ground_choice[(x, y)] = pick_decor(template.decor_ground, x, y, ground_decor, rng)
        elif road_distance[(x, y)] >= ROAD_MARGIN:
            grass_choice[(x, y)] = pick_decor(template.decor_grass, x, y, grass_decor, rng)

    def tone(x, y, base, flat, salt):
        """Основной тайл клетки: пятнами по шуму вместо него берётся плоский вариант тона из малых тайлов."""
        if flat and noise(x, y, 7, 61 + salt) > TONE_THRESHOLD:
            return flat[_hash(x, y, salt) % len(flat)]
        return base[_hash(x, y, salt + 1) % len(base)]

    def grass_tile(x, y):
        template = template_at(x, y)
        desired = desired_coverage(x, y, road)
        if is_full(desired):
            return grass_choice.get((x, y)) or tone(x, y, template.base_grass, template.flat_grass, 5)
        return pick_border_tile(template.border, desired, rng)

    ground_map = {
        (x, y): ground_choice.get((x, y)) or tone(x, y, template_at(x, y).base_ground, template_at(x, y).flat_ground, 1)
        for y in range(size) for x in range(size)
    }
    overlay_map = {(x, y): grass_tile(x, y) for y in range(size) for x in range(size) if (x, y) not in road}
    transparent = overlay_keys()
    solid = set()
    for x, y, stamp in hills:
        for dx in range(HILL_SIDE):
            for dy in range(HILL_SIDE):
                cell = (x + dx, y + dy)
                base_grass = template_at(*cell).base_grass
                ground_map[cell] = base_grass[_hash(*cell, 7) % len(base_grass)]
                key = stamp.get((dx, dy))
                if key is None:
                    continue
                if key in transparent:
                    overlay_map[cell] = key
                else:
                    ground_map[cell] = key
                    overlay_map.pop(cell, None)
                if items[key]["blocks"]:
                    solid.add(cell)

    for state in massifs:
        for cell, key in state.items():
            base_grass = template_at(*cell).base_grass
            ground_map[cell] = base_grass[_hash(*cell, 7) % len(base_grass)]
            if key in transparent:
                overlay_map[cell] = key
            else:
                ground_map[cell] = key
                overlay_map.pop(cell, None)
            if items[key]["blocks"]:
                solid.add(cell)

    cells = [{"layer": "ground", "x": x, "y": y, "key": key} for (x, y), key in sorted(ground_map.items(), key=lambda e: (e[0][1], e[0][0]))]
    cells += [{"layer": "overlay", "x": x, "y": y, "key": key} for (x, y), key in sorted(overlay_map.items(), key=lambda e: (e[0][1], e[0][0]))]
    for (x, y), key in sorted(objects.items(), key=lambda entry: (entry[0][1], entry[0][0])):
        cells.append({"layer": "object", "x": x, "y": y, "key": key})

    stats = _check(
        cells, catalog, items, objects, road, road_distance, zones, centre, size, ground_decor, grass_decor, solid, len(hills)
    )
    stats["earth_patch_cells"] = len(patches)
    stats["mountain_massifs"] = len(massifs)
    stats["mountain_cells"] = sum(len(state) for state in massifs)
    flat_ground = {key for template in templates.values() for key in template.flat_ground}
    flat_grass = {key for template in templates.values() for key in template.flat_grass}
    stats["dry_forest_cells"] = len(dry_cells)
    stats["tone_variant_cells"] = sum(key in flat_ground for key in ground_map.values()) + sum(
        key in flat_grass for key in overlay_map.values()
    )
    return cells, stats


def _check(cells, catalog, items, objects, road, road_distance, zones, centre, size, ground_decor, grass_decor, solid, hills):
    top = {(c["x"], c["y"]): c["key"] for c in cells if c["layer"] != "object"}
    bad = [cell for cell in objects if not tile_allows_objects(top[cell], items[top[cell]]["category"])]
    assert not bad, bad[:5]
    validate_cells(cells, catalog, size, size)
    terrain_from_cells(cells, catalog)
    assert decor_spaced(ground_decor) and decor_spaced(grass_decor)
    grass_cells = size * size - len(road)
    assert len(ground_decor) <= 0.1 * len(road) and len(grass_decor) <= 0.1 * grass_cells

    blocked = {cell for cell, key in objects.items() if items[key]["blocks"]} | solid
    start = (int(centre[0]), int(centre[1]))
    seen, queue = {start}, deque([start])
    while queue:
        cx, cy = queue.popleft()
        for nxt in ((cx, cy - 1), (cx, cy + 1), (cx - 1, cy), (cx + 1, cy)):
            if 0 <= nxt[0] < size and 0 <= nxt[1] < size and nxt not in seen and nxt not in blocked:
                seen.add(nxt)
                queue.append(nxt)
    # Проход сквозь огромный лес в обход дорог: из поляны к малому лесу только по клеткам вне просек.
    off_road = [cell for cell in zones if road_distance[cell] > ROAD_MARGIN and cell not in blocked]
    free = set(off_road)
    crossing = deque(cell for cell in off_road if zones[cell] == "glade")
    reached = set(crossing)
    while crossing:
        cx, cy = crossing.popleft()
        for nxt in ((cx, cy - 1), (cx, cy + 1), (cx - 1, cy), (cx + 1, cy)):
            if nxt in free and nxt not in reached:
                reached.add(nxt)
                crossing.append(nxt)
    giant_crossings = sum(1 for cell in reached if zones[cell] in ("grove", "outer"))
    giant_total = sum(1 for cell in zones if zones[cell] == "giant")
    corners = [(1, 1), (size - 2, 1), (1, size - 2), (size - 2, size - 2)]
    return {
        "zones": Counter(zones.values()),
        "objects": Counter(items[key]["category"] for key in objects.values()),
        "road": len(road),
        "giant_total": giant_total,
        "reachable_from_glade_bypassing_roads_to_outer_zones": giant_crossings,
        "corners_reach_centre": [any(abs(c[0] - cx) + abs(c[1] - cy) <= 3 for c in seen) for cx, cy in corners],
        "hills": hills,
        "ground_decor": len(ground_decor),
        "grass_decor": len(grass_decor),
        "base_tile_share": (round(1 - len(ground_decor) / len(road), 3), round(1 - len(grass_decor) / grass_cells, 3)),
    }


def save(cells, name, size=SIZE):
    existing = next((draft for draft in map_drafts.list_drafts() if draft["name"] == name), None)
    return map_drafts.save_draft(name, cells, size, size, draft_id=existing["id"] if existing else None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default=DEFAULT_NAME, help="название черновика")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--size", type=int, default=SIZE)
    parser.add_argument("--landscape", default=LANDSCAPE, help="образец палитры: Лесной ландшафт или Горный ландшафт")
    arguments = parser.parse_args()
    generated, info = generate(arguments.size, arguments.seed, arguments.landscape)
    draft = save(generated, arguments.name, arguments.size)
    print(f"Черновик «{draft['name']}»: {len(draft['cells'])} клеток")
    for field, value in info.items():
        print(f"  {field}: {value}")
