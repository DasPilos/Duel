"""Палитра редактора карт: тайлы MainLev и объекты, сгруппированные по типу и цвету."""
import colorsys
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from core.map_layers import layer_of
from core.map_catalog import (
    MAINLEV_DIR,
    MAINLEV_TILE_RE,
    ROCKY_GROUND_MOSS_GRASS_TILE_IDS,
    WATER_ANIMAL_KEYS,
    desert_animated_groups,
    grassland_animations,
    grassland_tile_specs,
    desert_tile_specs,
    overlay_keys,
    palette_group_decor,
    palette_group_layers,
    palette_groups,
    palette_hidden_keys,
    palette_sheets,
    rocky_animated_groups,
    rocky_animations,
    rocky_tile_specs,
    rocky_water_object_groups,
    storage_layer_for_palette_role,
    undead_animated_groups,
    undead_tile_specs,
    winter_animated_groups,
    winter_animations,
    winter_tile_specs,
)

SOURCE_TILE = 32
VIEW_TILE = 20
PALETTE_TILE_MIN = 16
PALETTE_TILE_MAX = 96
PALETTE_TILE_STEP = 4
COLUMNS = 10
PANEL_W_MIN = 240
BLOCK_X = 12
BLOCK_PAD = 4
CLUSTER_GAP = 8
HEADER_H = 30
LEGEND_H = 44
CAPTION_H = 20
FRAME_W = 2
PANEL_TEXT_X = 12
SCROLL_ROOM = 30
PANEL_MARGIN = BLOCK_X + SCROLL_ROOM
OBJECT_CELL_MIN = 44
ANIMATED_PREVIEW_SCALE = 0.5
HUE_BUCKETS = 12
GRAY_SATURATION = 0.15
ROCKY_TILE_SPECS = rocky_tile_specs()
ROCKY_ANIMATIONS = rocky_animations()
WINTER_TILE_SPECS = winter_tile_specs()
WINTER_ANIMATIONS = winter_animations()
UNDEAD_TILE_SPECS = undead_tile_specs()
DESERT_TILE_SPECS = desert_tile_specs()
GRASSLAND_TILE_SPECS = grassland_tile_specs()
BIOME_TILE_SPECS = {
    **ROCKY_TILE_SPECS, **WINTER_TILE_SPECS, **UNDEAD_TILE_SPECS,
    **DESERT_TILE_SPECS, **GRASSLAND_TILE_SPECS,
}
GRASSLAND_ANIMATIONS = grassland_animations()

GROUND_ORDER = ("grass", "road", "water", "floor", "rock", "leaves")
OBJECT_ORDER = ("building", "tree", "old_tree", "stump", "log", "bush", "animal", "crystal")
# Категории, где объекты одного вида (ключ `<вид>_<стадия>`) выводятся рядом по возрастанию стадии.
SERIES_CATEGORIES = ("crystal",)
ROCKY_GROWTH_TITLE = "Скалистый биом · Растущие объекты"
# Отступ опоры стадий от низа клетки палитры (пикс.).
SERIES_BASE_GAP = 2
TITLES = {
    "building": "Постройки",
    "grass": "Трава",
    "road": "Дороги",
    "water": "Вода",
    "floor": "Пол и мосты",
    "rock": "Скалы и камни",
    "leaves": "Листва",
    "tree": "Деревья",
    "old_tree": "Старые деревья",
    "stump": "Пни",
    "log": "Брёвна",
    "bush": "Кусты и растения",
    "animal": "Животные",
    "crystal": "Кристаллы",
}

TEXT = (235, 235, 235)
TEXT_DIM = (160, 166, 176)
HEADER_BG = (40, 44, 52)
CELL_BG = (30, 34, 40)
SELECT_COLOR = (120, 200, 255)
GRID_COLOR = (58, 63, 72)
BLOCK_MARK = (230, 70, 70)
PASSABLE_MARK = (90, 200, 120)
OVERLAY_MARK = (80, 160, 255)
DECOR_MARK = (240, 210, 70)
LAYER_DIGIT_COLOR = (255, 255, 255)
LAYER_DIGIT_BG = (20, 22, 28)
LAYER_COLORS = {
    "ground": (214, 150, 80), "grass": (110, 200, 110),
    "ground_decor": (170, 110, 50), "grass_decor": (70, 150, 80),
    "elevation": (170, 140, 230), "river": (90, 170, 230),
    "ground_small": (140, 100, 55), "grass_small": (80, 140, 90), "mountain": (205, 170, 120),
    "overlay": (80, 160, 255), "infra": (230, 190, 90),
}

_RGB_CACHE = {}


def animation_frame_index(animation, ticks):
    """Resolve a frame using Tiled per-frame durations or the legacy fixed interval."""
    durations = animation.get("durations")
    if durations:
        elapsed = int(ticks) % sum(durations)
        for index, duration in enumerate(durations):
            if elapsed < duration:
                return index
            elapsed -= duration
        return len(durations) - 1
    return (int(ticks) // animation["ms"]) % animation["frames"]


def rocky_tile_frame(key, sheet, frame=0):
    """Crop one imported biome tile from its scaled source atlas."""
    spec = BIOME_TILE_SPECS.get(key)
    if spec is None or spec.get("representation") == "sprite":
        return sheet
    frames = spec.get("frame_tile_ids") or [spec["tile_id"]]
    tile_id = frames[frame % len(frames)]
    column, row = tile_id % spec["columns"], tile_id // spec["columns"]
    tile_size = sheet.get_width() // spec["columns"]
    image = sheet.subsurface(pygame.Rect(column * tile_size, row * tile_size, tile_size, tile_size))
    return pygame.transform.flip(image, True, False) if spec.get("flip_x", False) else image


def _average_rgb(path):
    """Средний цвет непрозрачной части картинки; кэшируется, чтобы палитра не читала файлы повторно."""
    path = str(path)
    if path not in _RGB_CACHE:
        image = pygame.image.load(path).convert_alpha()
        covered = pygame.mask.from_surface(image, 16).count()
        if covered == 0:
            _RGB_CACHE[path] = (0, 0, 0)
        else:
            backdrop = pygame.Surface(image.get_size())
            backdrop.blit(image, (0, 0))
            area = image.get_width() * image.get_height()
            share = covered / area
            red, green, blue, _ = pygame.transform.average_color(backdrop)
            _RGB_CACHE[path] = tuple(min(255, round(channel / share)) for channel in (red, green, blue))
    return _RGB_CACHE[path]


def _color_key(colors):
    """Ключ сортировки по цвету: серые первыми, затем по оттенку и яркости."""
    red, green, blue = (sum(channel) / len(colors) / 255 for channel in zip(*colors))
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    bucket = -1 if saturation < GRAY_SATURATION else int(hue * HUE_BUCKETS) % HUE_BUCKETS
    return bucket, value


def maximum_tile_size(max_panel):
    """Largest palette cell that keeps ten columns inside the available panel width."""
    return min(PALETTE_TILE_MAX, max(PALETTE_TILE_MIN, (max_panel - PANEL_MARGIN) // COLUMNS))


def _tile_position(item):
    """Блок, строка и столбец тайла MainLev на исходном листе или None, если это не такой тайл."""
    if item["kind"] != "ground":
        return None
    folder, _, name = item["asset"].rpartition("/")
    match = MAINLEV_TILE_RE.fullmatch(name)
    if folder.split("/")[0] != MAINLEV_DIR or match is None:
        return None
    return folder, int(match.group(1)), int(match.group(2))


def _connected(cells):
    """Связные по сторонам группы клеток {(строка, столбец): элемент}."""
    seen = set()
    groups = []
    for start in sorted(cells):
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], []
        while stack:
            row, col = stack.pop()
            group.append((row, col))
            for neighbour in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
                if neighbour in cells and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    return groups


def _series(items):
    """Group growth stages by visible size and other numbered series by stage."""
    by_kind = defaultdict(list)
    for item in items:
        if item.get("growth_series") is not None:
            stage = int(item["growth_stage"])
            size = int(item.get("growth_size", stage))
            by_kind[item["growth_series"]].append((size, stage, item))
            continue
        kind, stage = item["item_key"].rsplit("_", 1)
        stage = int(stage)
        by_kind[kind].append((stage, stage, item))
    return [
        [item for _, _, item in sorted(stages, key=lambda entry: (entry[0], entry[1]))]
        for _, stages in sorted(by_kind.items())
    ]


def _is_series_item(item):
    if item.get("growth_series") is not None:
        return True
    if item["category"] in SERIES_CATEGORIES:
        return True
    if item["category"] != "bush":
        return False
    prefix, separator, stage = item["item_key"].rpartition("_")
    return bool(separator and prefix.startswith("bush_") and stage in {"1", "2", "3"})


def series_base(image):
    """Опора стадии: середина нижнего края видимой части картинки. Все стадии кладутся на неё, и рост идёт от одного места."""
    rect = image.get_bounding_rect()
    return rect.centerx, rect.bottom


@dataclass
class _Cluster:
    cells: list
    cols: int
    rows: int
    color: tuple
    overlay: bool
    objects: bool = False
    layers: list = field(default_factory=list)
    compound: bool = False
    series: bool = False
    preview_group: dict | None = None
    subsection: str | None = None
    artist_context: bool = False


@dataclass
class _Row:
    kind: str
    top: int
    height: int
    title: str = ""
    count: int = 0
    size: tuple = (0, 0)
    cells: list = field(default_factory=list)
    frames: list = field(default_factory=list)
    previews: list = field(default_factory=list)
    surface: pygame.Surface | None = None
    arrange_group: str | None = None
    default_positions: dict = field(default_factory=dict)


class Palette:
    """Строки палитры: заголовки разделов и ряды групп тайлов и объектов."""

    def __init__(
        self,
        catalog,
        map_dir,
        font,
        small,
        tile=VIEW_TILE,
        max_panel=640,
        animations=None,
        rules=None,
        arrange_mode=False,
    ):
        """animations: {ключ элемента: {"frame": (ширина, высота), "frames": число кадров, "cols": кадров в строке листа,
        "ms": мс на кадр}}. Такой элемент лежит в файле листом кадров: в палитре виден первый кадр, а под курсором идёт анимация."""
        self.font = font
        self.max_panel = max_panel
        self.small = small
        self.map_dir = Path(map_dir)
        self.animations = dict(animations or {})
        self.rules = dict(rules or {})
        self.arrange_mode = arrange_mode
        self._images = {}
        self._sheets = {}
        self._fit_ref = {}
        self._overlay = overlay_keys()
        self._decor = frozenset(
            key for group in palette_groups() for part in palette_group_decor(group).values() for key in part["decor"]
        )
        self._compound_stamps = {}
        self._catalog_items = {}
        self._water_preview_cache = {}
        self.tile = min(tile, max(PALETTE_TILE_MIN, (max_panel - PANEL_MARGIN) // COLUMNS))
        self._sections = self._group(catalog)
        self._layout()

    @property
    def scale(self):
        return self.tile / SOURCE_TILE

    def panel_width(self):
        """Ширина панели каталога: COLUMNS тайлов в ряд, но не уже PANEL_W_MIN и не шире max_panel."""
        width = max(PANEL_W_MIN, min(COLUMNS * self.tile + PANEL_MARGIN, self.max_panel))
        context_columns = max(
            (
                cluster.cols
                for _title, clusters in getattr(self, "_sections", ())
                for cluster in clusters
                if cluster.artist_context
            ),
            default=0,
        )
        if context_columns:
            context_side = min(
                self.tile,
                max(1, (self.max_panel - PANEL_MARGIN) // context_columns),
            )
            width = max(width, context_columns * context_side + PANEL_MARGIN)
        return width

    def set_tile(self, tile):
        """Меняет размер тайла в палитре и пересобирает строки."""
        if tile == self.tile:
            return
        self.tile = tile
        self._images = {}
        self._layout()

    def _group(self, catalog):
        """Разделы (название, группы) в порядке показа.

        Сначала образцы художника, затем остальные тайлы по типу и объекты;
        ростовые серии находятся в начале раздела кустов, копии блоков листа — в самом низу.
        """
        tiles = defaultdict(lambda: defaultdict(dict))
        objects = defaultdict(list)
        rocky_growth = []
        rocky_detail_objects = []
        rocky_sheets = defaultdict(lambda: defaultdict(dict))
        rocky_objects = []
        rocky_compounds = defaultdict(list)
        winter_growth = []
        winter_objects = []
        winter_detail_objects = []
        winter_spot_objects = []
        winter_water_detail_objects = []
        winter_sheets = defaultdict(lambda: defaultdict(dict))
        winter_compounds = defaultdict(list)
        undead_sprite_families = defaultdict(list)
        undead_atlas_objects = []
        undead_detail_objects = []
        undead_animated_objects = []
        undead_sheets = defaultdict(lambda: defaultdict(dict))
        undead_compounds = defaultdict(list)
        desert_sprite_families = defaultdict(list)
        desert_atlas_objects = []
        desert_detail_objects = []
        desert_sheets = defaultdict(lambda: defaultdict(dict))
        desert_compounds = defaultdict(list)
        winter_animation_groups = winter_animated_groups()
        winter_animation_keys = {
            cell["key"]
            for group in winter_animation_groups
            for cell in group["cells"]
        }
        undead_animation_groups = undead_animated_groups()
        undead_animation_keys = {
            cell["key"]
            for group in undead_animation_groups
            for cell in group["cells"]
        }
        desert_animation_groups = desert_animated_groups()
        desert_animation_keys = {
            cell["key"]
            for group in desert_animation_groups
            for cell in group["cells"]
        }
        water_object_clusters = []
        sections = []
        by_key = {item["item_key"]: item for item in catalog}
        self._catalog_items = by_key
        grouped = set(palette_hidden_keys(catalog))
        for group in palette_groups():
            cells = [((cell["x"], cell["y"]), by_key[cell["key"]]) for cell in group["cells"] if cell["key"] in by_key]
            if not cells:
                continue
            grouped.update(item["item_key"] for _, item in cells)
            cols = max(dx for (dx, _), _ in cells) + 1
            rows = max(dy for (_, dy), _ in cells) + 1
            cluster = _Cluster(cells, cols, rows, (0, 0.0), False, layers=palette_group_layers(group))
            sections.append((group["title"], [cluster]))
        for group in rocky_water_object_groups():
            cells = [
                ((cell["x"], cell["y"]), by_key[cell["key"]])
                for cell in group["cells"]
                if cell["key"] in by_key
            ]
            if len(cells) != len(group["cells"]):
                continue
            entries = [
                (cell["x"], cell["y"], cell["key"], cell["layer"])
                for cell in group["cells"]
            ]
            water_object_clusters.append(_Cluster(
                cells,
                group["width"],
                group["height"],
                (0, 0.0),
                False,
                compound=True,
                preview_group=group,
                subsection=(
                    f"Руины {group['key'].rsplit('_', 1)[1]}"
                    if group["key"].startswith("rocky_water_object_ruins_")
                    else None
                ),
            ))
            self._compound_stamps[group["primary_key"]] = entries
            self._compound_stamps[group["key"]] = entries
            grouped.update(cell["key"] for cell in group["cells"])
        for item in catalog:
            if item["item_key"] in grouped:
                continue
            rocky_spec = ROCKY_TILE_SPECS.get(item["item_key"])
            if rocky_spec is not None:
                if rocky_spec.get("palette_hidden", False):
                    grouped.add(item["item_key"])
                    continue
                if item.get("growth_series") is not None:
                    if rocky_spec.get("sheet") == "details":
                        rocky_detail_objects.append(item)
                    else:
                        rocky_growth.append(item)
                    grouped.add(item["item_key"])
                    continue
                if rocky_spec.get("representation") == "sprite":
                    if rocky_spec.get("sheet") == "details":
                        rocky_detail_objects.append(item)
                    else:
                        rocky_objects.append(item)
                else:
                    row = rocky_spec["tile_id"] // rocky_spec["columns"]
                    column = rocky_spec["tile_id"] % rocky_spec["columns"]
                    rocky_sheets[rocky_spec["sheet"]][rocky_spec["layer"]][row, column] = item
                grouped.add(item["item_key"])
                continue
            winter_spec = WINTER_TILE_SPECS.get(item["item_key"])
            if winter_spec is not None:
                if item["item_key"] in winter_animation_keys:
                    grouped.add(item["item_key"])
                    continue
                if winter_spec.get("palette_hidden", False):
                    grouped.add(item["item_key"])
                    continue
                if item.get("growth_series") is not None:
                    winter_growth.append(item)
                elif winter_spec.get("representation") == "sprite":
                    if winter_spec.get("sheet") == "details":
                        winter_detail_objects.append(item)
                    elif winter_spec.get("sheet") == "spots":
                        winter_spot_objects.append(item)
                    elif winter_spec.get("sheet") == "water_detilazation_v2":
                        winter_water_detail_objects.append(item)
                    else:
                        winter_objects.append(item)
                else:
                    row = winter_spec["tile_id"] // winter_spec["columns"]
                    column = winter_spec["tile_id"] % winter_spec["columns"]
                    winter_sheets[winter_spec["sheet"]][winter_spec["layer"]][row, column] = item
                grouped.add(item["item_key"])
                continue
            undead_spec = UNDEAD_TILE_SPECS.get(item["item_key"])
            if undead_spec is not None:
                if item["item_key"] in undead_animation_keys:
                    grouped.add(item["item_key"])
                    continue
                if undead_spec.get("palette_hidden", False):
                    grouped.add(item["item_key"])
                    continue
                if undead_spec.get("representation") == "sprite":
                    sheet = undead_spec.get("sheet", "").casefold()
                    if sheet == "objects_separately":
                        undead_sprite_families[undead_spec["object_type"]].append(item)
                    elif sheet == "details":
                        undead_detail_objects.append(item)
                    elif sheet.startswith("animation"):
                        undead_animated_objects.append(item)
                    else:
                        undead_atlas_objects.append(item)
                else:
                    row = undead_spec["tile_id"] // undead_spec["columns"]
                    column = undead_spec["tile_id"] % undead_spec["columns"]
                    undead_sheets[undead_spec["sheet"]][undead_spec["layer"]][row, column] = item
                grouped.add(item["item_key"])
                continue
            desert_spec = DESERT_TILE_SPECS.get(item["item_key"])
            if desert_spec is not None:
                if item["item_key"] in desert_animation_keys:
                    grouped.add(item["item_key"])
                    continue
                if desert_spec.get("palette_hidden", False):
                    grouped.add(item["item_key"])
                    continue
                if desert_spec.get("representation") == "sprite":
                    sheet = desert_spec.get("sheet", "").casefold()
                    if sheet == "objects_separately":
                        desert_sprite_families[desert_spec["object_type"]].append(item)
                    elif sheet == "details":
                        desert_detail_objects.append(item)
                    else:
                        desert_atlas_objects.append(item)
                else:
                    row = desert_spec["tile_id"] // desert_spec["columns"]
                    column = desert_spec["tile_id"] % desert_spec["columns"]
                    desert_sheets[desert_spec["sheet"]][desert_spec["layer"]][row, column] = item
                grouped.add(item["item_key"])
                continue
            position = _tile_position(item)
            if position is None:
                objects[item["category"]].append(item)
            else:
                block, row, col = position
                tiles[item["category"]][block][(row, col)] = item
        water_object_effect_keys = {
            cell["key"]
            for group in rocky_water_object_groups()
            for cell in group["cells"]
            if cell["layer"] == "overlay"
        }
        for group in rocky_animated_groups():
            group_cells = {}
            for cell in group["cells"]:
                if cell["key"] in water_object_effect_keys:
                    continue
                item = by_key.get(cell["key"])
                if item is not None:
                    group_cells[(cell["y"], cell["x"])] = item
            if not group_cells:
                continue
            cluster = self._tile_cluster(list(group_cells), group_cells)
            cluster.overlay = True
            cluster.objects = True
            cluster.compound = True
            cluster.layers = [{
                "x": 0,
                "y": 0,
                "w": cluster.cols,
                "h": cluster.rows,
                "role": "overlay",
                "name": "",
                "number": None,
            }]
            top = min(y for y, _x in group_cells)
            left = min(x for _y, x in group_cells)
            entries = [
                (x - left, y - top, item["item_key"], "overlay")
                for (y, x), item in sorted(group_cells.items())
            ]
            for _x, _y, key, _layer in entries:
                self._compound_stamps[key] = entries
            rocky_compounds["Water_detilazation2"].append(cluster)
        for group in winter_animation_groups:
            group_cells = {}
            for cell in group["cells"]:
                item = by_key.get(cell["key"])
                if item is not None:
                    group_cells[(cell["y"], cell["x"])] = item
            if not group_cells:
                continue
            cluster = self._tile_cluster(list(group_cells), group_cells)
            cluster.overlay = True
            cluster.objects = True
            cluster.compound = True
            cluster.preview_group = group
            entries = [
                (cell["x"], cell["y"], cell["key"], cell["layer"])
                for cell in group["cells"]
                if cell["key"] in by_key
            ]
            self._compound_stamps[group["key"]] = entries
            for _x, _y, key, _layer in entries:
                self._compound_stamps[key] = entries
            winter_compounds[group["sheet"]].append(cluster)
        for group in undead_animation_groups:
            group_cells = {}
            for cell in group["cells"]:
                item = by_key.get(cell["key"])
                if item is not None:
                    group_cells[(cell["y"], cell["x"])] = item
            if not group_cells:
                continue
            cluster = self._tile_cluster(list(group_cells), group_cells)
            cluster.overlay = all(
                cell["layer"] == "overlay" for cell in group["cells"]
            )
            cluster.compound = True
            cluster.preview_group = group
            entries = [
                (cell["x"], cell["y"], cell["key"], cell["layer"])
                for cell in group["cells"]
                if cell["key"] in by_key
            ]
            self._compound_stamps[group["key"]] = entries
            for _x, _y, key, _layer in entries:
                self._compound_stamps[key] = entries
            undead_compounds[group["sheet"]].append((group["cells"][0]["layer"], cluster))
        for group in desert_animation_groups:
            group_cells = {}
            for cell in group["cells"]:
                item = by_key.get(cell["key"])
                if item is not None:
                    group_cells[(cell["y"], cell["x"])] = item
            if not group_cells:
                continue
            cluster = self._tile_cluster(list(group_cells), group_cells)
            cluster.overlay = all(
                cell["layer"] == "overlay" for cell in group["cells"]
            )
            cluster.compound = True
            cluster.preview_group = group
            entries = [
                (cell["x"], cell["y"], cell["key"], cell["layer"])
                for cell in group["cells"]
                if cell["key"] in by_key
            ]
            self._compound_stamps[group["key"]] = entries
            for _x, _y, key, _layer in entries:
                self._compound_stamps[key] = entries
            desert_compounds[group["sheet"]].append(
                (group["cells"][0]["layer"], cluster)
            )
        for group in rocky_water_object_groups():
            entries = [
                (cell["x"], cell["y"], cell["key"], cell["layer"])
                for cell in group["cells"]
            ]
            self._compound_stamps[group["key"]] = entries
            self._compound_stamps[group["primary_key"]] = entries
        for category in self._ordered(tiles, GROUND_ORDER):
            clusters = []
            for block, cells in sorted(tiles[category].items()):
                for group in _connected(cells):
                    clusters.append(self._tile_cluster(group, cells))
            sections.append((TITLES.get(category, category), clusters))
        for category in self._ordered(objects, OBJECT_ORDER):
            if category in SERIES_CATEGORIES:
                clusters = [self._series_cluster(series) for series in _series(objects[category])]
            elif category == "bush":
                growth_items = [item for item in objects[category] if _is_series_item(item)]
                decorations = [item for item in objects[category] if not _is_series_item(item)]
                clusters = [self._series_cluster(series) for series in _series(growth_items)]
                clusters.extend(self._object_cluster(item) for item in sorted(decorations, key=lambda item: item["item_key"]))
            else:
                items = sorted(objects[category], key=lambda item: item["item_key"])
                clusters = [self._object_cluster(item) for item in items]
            sections.append((TITLES.get(category, category), clusters))
        rocky_artist_items = [
            item
            for item in catalog
            if (
                (spec := ROCKY_TILE_SPECS.get(item["item_key"])) is not None
                and spec.get("sheet") == "Ground_moss"
                and not spec.get("palette_hidden", False)
            )
        ]
        rocky_artist_cluster = self._artist_sheet_cluster(
            rocky_artist_items,
            ROCKY_TILE_SPECS,
            "Ground_moss",
        )
        if rocky_artist_cluster is not None:
            sections.append((
                "Скалистый биом · Ландшафт с листа художника",
                [rocky_artist_cluster],
            ))
        rocky_chunk_width = max(1, min(COLUMNS, (self.panel_width() - PANEL_MARGIN) // self.tile))
        sheet_order = dict.fromkeys(
            spec["sheet"] for spec in ROCKY_TILE_SPECS.values()
        )
        for sheet in (name for name in sheet_order if name in rocky_compounds or name in rocky_sheets):
            roles = set(rocky_sheets.get(sheet, {}))
            if rocky_compounds.get(sheet):
                roles.add("overlay")
            for role in sorted(roles, key=lambda value: {"ground": 0, "elevation": 1, "infra": 2, "overlay": 3}.get(value, 4)):
                role_cells = rocky_sheets.get(sheet, {}).get(role, {})
                clusters = (
                    list(rocky_compounds.get(sheet, ()))
                    if role == "overlay"
                    else []
                )
                base_title = next(
                    spec["title"] for spec in ROCKY_TILE_SPECS.values()
                    if spec["sheet"] == sheet
                )
                cell_groups = [(role_cells, None)]
                if sheet == "Ground_moss" and role == "elevation":
                    grass_cells = {
                        position: item for position, item in role_cells.items()
                        if ROCKY_TILE_SPECS[item["item_key"]]["tile_id"]
                        in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
                    }
                    rock_cells = {
                        position: item for position, item in role_cells.items()
                        if ROCKY_TILE_SPECS[item["item_key"]]["tile_id"]
                        not in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
                    }
                    cell_groups = [
                        (grass_cells, "Скалистый биом · Трава"),
                        (rock_cells, "Скалистый биом · Скалы и возвышенности"),
                    ]
                for group_cells, group_title in cell_groups:
                    group_clusters = list(clusters) if group_title is None else []
                    if group_cells:
                        max_column = max(column for _row, column in group_cells)
                        for start_column in range(0, max_column + 1, rocky_chunk_width):
                            chunk = {
                                (row, column - start_column): item
                                for (row, column), item in group_cells.items()
                                if start_column <= column < start_column + rocky_chunk_width
                            }
                            for group in _connected(chunk):
                                cluster = self._tile_cluster(group, chunk)
                                cluster.overlay = role == "overlay"
                                cluster_role = (
                                    "ground"
                                    if group_title == "Скалистый биом · Трава"
                                    else role
                                )
                                cluster.layers = [
                                    {
                                        "x": x,
                                        "y": y,
                                        "w": 1,
                                        "h": 1,
                                        "role": cluster_role,
                                        "name": "",
                                        "number": None,
                                    }
                                    for (x, y), _item in cluster.cells
                                ]
                                group_clusters.append(cluster)
                    group_clusters.sort(
                        key=lambda cluster: min(
                            ROCKY_TILE_SPECS[item["item_key"]]["tile_id"]
                            for _position, item in cluster.cells
                        )
                    )
                    title = group_title or self._rocky_section_title(sheet, role, base_title)
                    sections.append((title, group_clusters))
        winter_chunk_width = max(1, min(COLUMNS, (self.panel_width() - PANEL_MARGIN) // self.tile))
        winter_sheet_order = dict.fromkeys(spec["sheet"] for spec in WINTER_TILE_SPECS.values())
        winter_sheet_sections = []
        winter_ice_crack_clusters = []
        for sheet in (
            name for name in dict.fromkeys((
                "ground_ice",
                "Ice",
                "cracks",
                "Snow",
                "Water_detilazation",
                "water_detilazation_v2",
                *winter_sheet_order,
            ))
            if name in winter_sheets or name in winter_compounds
        ):
            sheet_specs = [
                spec for spec in WINTER_TILE_SPECS.values()
                if spec["sheet"] == sheet
            ]
            for role in sorted(
                set(winter_sheets.get(sheet, {})) | ({"overlay"} if winter_compounds.get(sheet) else set()),
                key=lambda value: {"ground": 0, "elevation": 1, "infra": 2, "overlay": 3}.get(value, 4),
            ):
                role_cells = winter_sheets.get(sheet, {}).get(role, {})
                clusters = list(winter_compounds.get(sheet, ())) if role == "overlay" else []
                if role_cells:
                    max_column = max(column for _row, column in role_cells)
                    for start_column in range(0, max_column + 1, winter_chunk_width):
                        chunk = {
                            (row, column - start_column): item
                            for (row, column), item in role_cells.items()
                            if start_column <= column < start_column + winter_chunk_width
                        }
                        for group in _connected(chunk):
                            clusters.append(self._tile_cluster(group, chunk))
                    clusters.sort(
                        key=lambda cluster: min(
                            WINTER_TILE_SPECS[item["item_key"]]["tile_id"]
                            for _position, item in cluster.cells
                        )
                    )
                base_title = sheet_specs[0]["title"]
                if winter_compounds.get(sheet) and role == "overlay":
                    title = "Водные блики"
                else:
                    title = base_title.removeprefix("Зимний биом · ")
                    if role != sheet_specs[0]["layer"]:
                        title = f"{title} · поверх земли"
                if sheet.casefold() in ("ice", "cracks"):
                    winter_ice_crack_clusters.extend(clusters)
                    continue
                winter_sheet_sections.append((title, clusters))
        if winter_ice_crack_clusters:
            sections.append(("Лёд и трещины", winter_ice_crack_clusters))
        sections.extend(winter_sheet_sections)
        undead_chunk_width = max(1, min(COLUMNS, (self.panel_width() - PANEL_MARGIN) // self.tile))
        mountain_artist_items = [
            item
            for item in catalog
            if (
                (spec := UNDEAD_TILE_SPECS.get(item["item_key"])) is not None
                and spec.get("sheet") == "Ground_rocks"
                and not spec.get("palette_hidden", False)
            )
        ]
        mountain_artist_cluster = self._undead_artist_cluster(
            mountain_artist_items,
        )
        if mountain_artist_cluster is not None:
            sections.append((
                "Биом нежити · Горы — ландшафт с листа художника",
                [mountain_artist_cluster],
            ))
        undead_sheet_order = dict.fromkeys(spec["sheet"] for spec in UNDEAD_TILE_SPECS.values())
        for sheet in (
            name for name in undead_sheet_order
            if name in undead_sheets or name in undead_compounds
        ):
            sheet_specs = [
                spec for spec in UNDEAD_TILE_SPECS.values()
                if spec["sheet"] == sheet
            ]
            roles = set(undead_sheets.get(sheet, {})) | {
                role for role, _cluster in undead_compounds.get(sheet, ())
            }
            for role in sorted(
                roles,
                key=lambda value: {
                    "ground": 0,
                    "overlay": 1,
                    "elevation": 2,
                    "infra": 3,
                    "objects": 4,
                }.get(value, 5),
            ):
                role_cells = undead_sheets.get(sheet, {}).get(role, {})
                clusters = [
                    cluster
                    for group_role, cluster in undead_compounds.get(sheet, ())
                    if group_role == role
                ]
                base_title = sheet_specs[0]["title"]
                title = base_title.removeprefix("Биом нежити · ")
                if role != sheet_specs[0]["layer"]:
                    role_title = {
                        "ground": "основа",
                        "overlay": "декор",
                        "elevation": "возвышенность",
                        "infra": "инфраструктура",
                        "objects": "объекты",
                    }.get(role, role)
                    title = f"{title} · {role_title}"
                cell_groups = [(role_cells, title)]
                if sheet == "Ground_rocks" and role == "elevation":
                    cell_groups = []
                    for mountain_type in ("dark", "stone"):
                        group_cells = {
                            position: item
                            for position, item in role_cells.items()
                            if UNDEAD_TILE_SPECS[item["item_key"]].get("mountain_type")
                            == mountain_type
                        }
                        if group_cells:
                            group_title = UNDEAD_TILE_SPECS[
                                next(iter(group_cells.values()))["item_key"]
                            ]["mountain_type_title"]
                            cell_groups.append((group_cells, group_title))
                for group_cells, group_title in cell_groups:
                    group_clusters = list(clusters) if group_title == title else []
                    if group_cells:
                        if sheet == "Ground_rocks" and role == "elevation":
                            mountain_type = UNDEAD_TILE_SPECS[
                                next(iter(group_cells.values()))["item_key"]
                            ]["mountain_type"]
                            cluster = self._undead_artist_cluster(
                                group_cells.values(),
                                mountain_type,
                            )
                            if cluster is not None:
                                group_clusters = [cluster]
                            represented_keys = {
                                item["item_key"]
                                for _position, item in group_clusters[0].cells
                            } if group_clusters else set()
                            extra_items = [
                                item
                                for item in group_cells.values()
                                if item["item_key"] not in represented_keys
                            ]
                            for start in range(0, len(extra_items), COLUMNS):
                                extra_chunk = extra_items[start:start + COLUMNS]
                                extra_cells = {
                                    (0, index): item
                                    for index, item in enumerate(extra_chunk)
                                }
                                group_clusters.append(
                                    self._tile_cluster(
                                        list(extra_cells),
                                        extra_cells,
                                    )
                                )
                        else:
                            max_column = max(column for _row, column in group_cells)
                            for start_column in range(0, max_column + 1, undead_chunk_width):
                                chunk = {
                                    (row, column - start_column): item
                                    for (row, column), item in group_cells.items()
                                    if start_column <= column < start_column + undead_chunk_width
                                }
                                for group in _connected(chunk):
                                    cluster = self._tile_cluster(group, chunk)
                                    if role in {"ground", "overlay", "elevation", "infra"}:
                                        cluster.layers = [
                                            {
                                                "x": x,
                                                "y": y,
                                                "w": 1,
                                                "h": 1,
                                                "role": role,
                                                "name": "",
                                                "number": None,
                                            }
                                            for (x, y), _item in cluster.cells
                                        ]
                                    group_clusters.append(cluster)
                    if sheet == "Ground_rocks" and role == "elevation":
                        group_clusters.sort(
                            key=lambda cluster: (
                                -(cluster.cols * cluster.rows),
                                -len(cluster.cells),
                                -max(cluster.cols, cluster.rows),
                                min(
                                    UNDEAD_TILE_SPECS[item["item_key"]]["tile_id"]
                                    for _position, item in cluster.cells
                                ),
                            )
                        )
                    else:
                        group_clusters.sort(
                            key=lambda cluster: min(
                                UNDEAD_TILE_SPECS[item["item_key"]]["tile_id"]
                                for _position, item in cluster.cells
                            )
                        )
                    sections.append((group_title, group_clusters))
        desert_chunk_width = max(1, min(COLUMNS, (self.panel_width() - PANEL_MARGIN) // self.tile))
        desert_sheet_order = dict.fromkeys(
            spec["sheet"] for spec in DESERT_TILE_SPECS.values()
        )
        for sheet in (
            name for name in desert_sheet_order
            if name in desert_sheets or name in desert_compounds
        ):
            sheet_specs = [
                spec for spec in DESERT_TILE_SPECS.values()
                if spec["sheet"] == sheet
            ]
            roles = set(desert_sheets.get(sheet, {})) | {
                role for role, _cluster in desert_compounds.get(sheet, ())
            }
            for role in sorted(
                roles,
                key=lambda value: {
                    "ground": 0,
                    "overlay": 1,
                    "elevation": 2,
                    "infra": 3,
                    "objects": 4,
                }.get(value, 5),
            ):
                role_cells = desert_sheets.get(sheet, {}).get(role, {})
                clusters = [
                    cluster
                    for group_role, cluster in desert_compounds.get(sheet, ())
                    if group_role == role
                ]
                if role_cells:
                    max_column = max(column for _row, column in role_cells)
                    for start_column in range(0, max_column + 1, desert_chunk_width):
                        chunk = {
                            (row, column - start_column): item
                            for (row, column), item in role_cells.items()
                            if start_column <= column < start_column + desert_chunk_width
                        }
                        for group in _connected(chunk):
                            cluster = self._tile_cluster(group, chunk)
                            if role in {"ground", "overlay", "elevation", "infra"}:
                                cluster.layers = [
                                    {
                                        "x": x,
                                        "y": y,
                                        "w": 1,
                                        "h": 1,
                                        "role": role,
                                        "name": "",
                                        "number": None,
                                    }
                                    for (x, y), _item in cluster.cells
                                ]
                            clusters.append(cluster)
                clusters.sort(
                    key=lambda cluster: min(
                        DESERT_TILE_SPECS[item["item_key"]]["tile_id"]
                        for _position, item in cluster.cells
                    )
                )
                base_title = sheet_specs[0]["title"].removeprefix("Пустыня · ")
                if role != sheet_specs[0]["layer"]:
                    role_title = {
                        "ground": "основа",
                        "overlay": "декор",
                        "elevation": "возвышенности",
                        "infra": "инфраструктура",
                        "objects": "объекты",
                    }.get(role, role)
                    base_title = f"{base_title} · {role_title}"
                sections.append((f"Пустыня · {base_title}", clusters))
        for object_type, family_items in sorted(
            undead_sprite_families.items(),
            key=lambda entry: min(
                UNDEAD_TILE_SPECS[item["item_key"]]["object_type_order"]
                for item in entry[1]
            ),
        ):
            spec = UNDEAD_TILE_SPECS[family_items[0]["item_key"]]
            sections.append((
                f"Нежить · {spec['object_type_name']}",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        family_items,
                        key=lambda item: (
                            -(
                                UNDEAD_TILE_SPECS[item["item_key"]]["source_size"][0]
                                * UNDEAD_TILE_SPECS[item["item_key"]]["source_size"][1]
                            ),
                            -max(UNDEAD_TILE_SPECS[item["item_key"]]["source_size"]),
                            item["item_key"],
                        ),
                    )
                ],
            ))
        def sprite_size_order(item):
            width, height = UNDEAD_TILE_SPECS[item["item_key"]]["source_size"]
            return -(width * height), -max(width, height), item["item_key"]

        if undead_atlas_objects:
            sections.append((
                "Нежить · Спрайты из атласа",
                [self._object_cluster(item) for item in sorted(undead_atlas_objects, key=sprite_size_order)],
            ))
        if undead_detail_objects:
            sections.append((
                "Нежить · Цельные детали",
                [self._object_cluster(item) for item in sorted(undead_detail_objects, key=sprite_size_order)],
            ))
        if undead_animated_objects:
            sections.append((
                "Нежить · Анимированные цельные объекты",
                [self._object_cluster(item) for item in sorted(undead_animated_objects, key=sprite_size_order)],
            ))
        for object_type, family_items in sorted(
            desert_sprite_families.items(),
            key=lambda entry: min(
                DESERT_TILE_SPECS[item["item_key"]]["object_type_order"]
                for item in entry[1]
            ),
        ):
            spec = DESERT_TILE_SPECS[family_items[0]["item_key"]]
            sections.append((
                f"Пустыня · {spec['object_type_name']}",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        family_items,
                        key=lambda item: (
                            -(
                                DESERT_TILE_SPECS[item["item_key"]]["source_size"][0]
                                * DESERT_TILE_SPECS[item["item_key"]]["source_size"][1]
                            ),
                            -max(DESERT_TILE_SPECS[item["item_key"]]["source_size"]),
                            item["item_key"],
                        ),
                    )
                ],
            ))
        def desert_sprite_size_order(item):
            width, height = DESERT_TILE_SPECS[item["item_key"]]["source_size"]
            return -(width * height), -max(width, height), item["item_key"]

        if desert_atlas_objects:
            sections.append((
                "Пустыня · Объекты из атласа",
                [
                    self._object_cluster(item)
                    for item in sorted(desert_atlas_objects, key=desert_sprite_size_order)
                ],
            ))
        if desert_detail_objects:
            sections.append((
                "Пустыня · Цельные детали",
                [
                    self._object_cluster(item)
                    for item in sorted(desert_detail_objects, key=desert_sprite_size_order)
                ],
            ))
        if winter_growth:
            sections.append((
                "Растущие объекты",
                [self._series_cluster(series) for series in _series(winter_growth)],
            ))
        if winter_objects:
            sections.append((
                "Цельные объекты",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        winter_objects,
                        key=lambda item: (int(item.get("growth_size", 0)), item["item_key"]),
                    )
                ],
            ))
        if winter_detail_objects:
            sections.append((
                "Цельные детали",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        winter_detail_objects,
                        key=lambda item: (int(item.get("growth_size", 0)), item["item_key"]),
                    )
                ],
            ))
        if winter_spot_objects:
            sections.append((
                "Следы и пятна",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        winter_spot_objects,
                        key=lambda item: (int(item.get("growth_size", 0)), item["item_key"]),
                    )
                ],
            ))
        if winter_water_detail_objects:
            sections.append((
                "Цельные водные детали",
                [
                    self._object_cluster(item)
                    for item in sorted(
                        winter_water_detail_objects,
                        key=lambda item: (int(item.get("growth_size", 0)), item["item_key"]),
                    )
                ],
            ))
        if water_object_clusters:
            sections.append(("Скалистый биом · Объекты в воде", water_object_clusters))
        if rocky_growth:
            clusters = [
                self._series_cluster(series)
                for series in _series(rocky_growth)
            ]
            sections.append((ROCKY_GROWTH_TITLE, clusters))
        if rocky_detail_objects:
            series_items = [
                item for item in rocky_detail_objects
                if item.get("growth_series") is not None
            ]
            clusters = [
                self._series_cluster(series)
                for series in _series(series_items)
            ]
            clusters.extend(
                self._object_cluster(item)
                for item in sorted(
                    rocky_detail_objects,
                    key=lambda item: (
                        int(item.get("growth_size", 0)),
                        item["item_key"],
                    ),
                )
                if item.get("growth_series") is None
            )
            sections.append(("Скалистый биом · Цельные детали и растения", clusters))
        if rocky_objects:
            clusters = [
                self._object_cluster(item)
                for item in sorted(rocky_objects, key=lambda item: item["item_key"])
            ]
            title = ROCKY_TILE_SPECS[rocky_objects[0]["item_key"]]["title"]
            sections.append((title, clusters))
        for sheet in palette_sheets():
            cells = [((cell["x"], cell["y"]), by_key[cell["key"]]) for cell in sheet["cells"] if cell["key"] in by_key]
            if cells:
                cols = max(dx for (dx, _), _ in cells) + 1
                rows = max(dy for (_, dy), _ in cells) + 1
                sections.append((sheet["title"], [_Cluster(cells, cols, rows, (0, 0.0), False)]))
        custom_groups = defaultdict(list)
        custom_keys = {
            key: rule["palette_group"]
            for key, rule in self.rules.items()
            if rule.get("palette_group") and key in by_key
        }
        if custom_keys:
            retained_sections = []
            for title, clusters in sections:
                retained_clusters = []
                for cluster in clusters:
                    if cluster.preview_group is not None or cluster.compound:
                        retained_clusters.append(cluster)
                        continue
                    retained = []
                    for position, item in cluster.cells:
                        group_title = custom_keys.get(item["item_key"])
                        if group_title is None:
                            retained.append((position, item))
                        else:
                            custom_groups[group_title].append(item)
                    if retained:
                        cluster.cells = retained
                        retained_clusters.append(cluster)
                retained_sections.append((title, retained_clusters))
            sections = retained_sections
            for title, items in custom_groups.items():
                clusters = [
                    self._tile_cluster([(0, 0)], {(0, 0): item})
                    if item["kind"] == "ground"
                    else self._object_cluster(item)
                    for item in sorted(
                        items,
                        key=lambda value: (
                            self.rules.get(value["item_key"], {}).get(
                                "palette_order", value.get("sort_order", 0)
                            ),
                            value["item_key"],
                        ),
                    )
                ]
                existing_index = next(
                    (index for index, (section_title, _section_clusters) in enumerate(sections)
                     if section_title == title),
                    None,
                )
                if existing_index is None:
                    sections.append((title, clusters))
                else:
                    section_title, existing_clusters = sections[existing_index]
                    sections[existing_index] = (
                        section_title,
                        existing_clusters + clusters,
                    )
        return sections

    @staticmethod
    def _rocky_section_title(sheet, role, base_title):
        role_titles = {
            "ground": "Земля и основа",
            "elevation": "Скалы и возвышенности",
            "infra": "Мосты и инфраструктура",
            "overlay": "Детали поверх земли",
        }
        base_roles = {
            "Ground_moss": "ground",
            "Water_coasts": "ground",
            "Waterfalls": "overlay",
            "Water_detilazation2": "overlay",
            "Water_detilazation": "overlay",
            "details": "overlay",
            "Water_under_objects": "overlay",
        }
        if role == "infra":
            return "Скалистый биом · Мосты и инфраструктура"
        if sheet == "Ground_moss" and role == "elevation":
            return "Скалистый биом · Скалы и возвышенности"
        if sheet == "Water_coasts" and role == "elevation":
            return "Скалистый биом · Берега и скальные края"
        if sheet == "Waterfalls" and role == "elevation":
            return "Скалистый биом · Скалы у водопадов"
        if role == base_roles.get(sheet):
            return base_title
        return f"{base_title} · {role_titles.get(role, role)}"

    @staticmethod
    def _ordered(source, order):
        return [category for category in order if category in source] + sorted(set(source) - set(order))

    def _tile_cluster(self, group, cells):
        top = min(row for row, _ in group)
        left = min(col for _, col in group)
        items = [((col - left, row - top), cells[row, col]) for row, col in sorted(group)]
        colors = [_average_rgb(self.map_dir / item["asset"]) for _, item in items]
        overlay = sum(item["item_key"] in self._overlay for _, item in items) * 2 > len(items)
        cols = max(dx for (dx, _), _ in items) + 1
        rows = max(dy for (_, dy), _ in items) + 1
        return _Cluster(items, cols, rows, _color_key(colors), overlay)

    def _artist_sheet_cluster(
        self,
        items,
        specs,
        sheet,
        spec_filter=None,
    ):
        source_cells = {}
        columns = rows = 0
        for item in sorted(
            items,
            key=lambda value: specs[value["item_key"]]["tile_id"],
        ):
            spec = specs[item["item_key"]]
            if spec.get("sheet") != sheet or (
                spec_filter is not None and not spec_filter(spec)
            ):
                continue
            size = spec.get("artist_sheet_size")
            positions = spec.get("artist_sheet_positions")
            if not size or not positions:
                continue
            columns = max(columns, size[0])
            rows = max(rows, size[1])
            for column, row in positions:
                position = (column, row)
                previous = source_cells.get(position)
                if previous is not None and previous["item_key"] != item["item_key"]:
                    raise ValueError(
                        f"Duplicate {sheet} artist-sheet position {position}"
                    )
                source_cells[position] = item
        if not source_cells:
            return None
        unique_items = {
            item["item_key"]: item for item in source_cells.values()
        }
        colors = [
            _average_rgb(self.map_dir / item["asset"])
            for item in list(unique_items.values())[:20]
        ]
        cells = [
            ((column, row), {**item, "palette_artist_copy": True})
            for (column, row), item in sorted(
                source_cells.items(),
                key=lambda entry: (entry[0][1], entry[0][0]),
            )
        ]
        return _Cluster(
            cells,
            columns,
            rows,
            _color_key(colors),
            False,
            objects=True,
            compound=True,
            artist_context=True,
        )

    def _undead_artist_cluster(self, items, mountain_type=None):
        return self._artist_sheet_cluster(
            items,
            UNDEAD_TILE_SPECS,
            "Ground_rocks",
            lambda spec: (
                mountain_type is None
                or spec.get("mountain_type") == mountain_type
            ),
        )

    def _object_cluster(self, item):
        color = _color_key([_average_rgb(self.map_dir / item["asset"])])
        return _Cluster([((0, 0), item)], 1, 1, color, False, objects=True)

    def _series_cluster(self, series):
        """Ряд стадий одного вида: клетки слева направо от самой маленькой стадии к созревшей."""
        cells = [((index, 0), item) for index, item in enumerate(series)]
        colors = [_average_rgb(self.map_dir / item["asset"]) for item in series]
        sizes = [pygame.image.load(str(self.map_dir / item["asset"])).get_size() for item in series]
        reference = (
            max(SOURCE_TILE, max(width for width, _ in sizes)),
            max(SOURCE_TILE, max(height for _, height in sizes)),
        )
        for item in series:
            self._fit_ref[item["item_key"]] = reference
        return _Cluster(cells, len(series), 1, _color_key(colors), False, objects=True, series=True)

    def _layout(self):
        self.rows = []
        top = self._add(_Row("legend", 0, LEGEND_H))
        for title, clusters in self._sections:
            arrangement_clusters = [
                cluster for cluster in clusters
                if cluster.preview_group is None and not cluster.compound
            ]
            compound_clusters = [
                cluster for cluster in clusters
                if cluster.preview_group is not None or cluster.compound
            ]
            has_saved_layout = any(
                "palette_position" in self.rules.get(item["item_key"], {})
                for cluster in arrangement_clusters
                for _position, item in cluster.cells
            )
            legacy_layout = self._legacy_position_keys(arrangement_clusters)
            if arrangement_clusters and (
                self.arrange_mode or (has_saved_layout and not legacy_layout)
            ):
                top = self._add(_Row(
                    "header",
                    top,
                    HEADER_H,
                    title=title,
                    count=sum(
                        1 if cluster.compound else len(cluster.cells)
                        for cluster in clusters
                    ),
                ))
                ordered_clusters = self._arrangement_order(title, arrangement_clusters)
                top = self._pack_arrangement(title, ordered_clusters, top)
                top = self._pack(compound_clusters, top)
                continue
            if title == "Лёд и трещины":
                count = sum(
                    1 if cluster.compound else len(cluster.cells)
                    for cluster in clusters
                )
                top = self._add(_Row("header", top, HEADER_H, title=title, count=count))
                top = self._pack(clusters, top)
                continue
            solid = [cluster for cluster in clusters if not cluster.overlay]
            over = [cluster for cluster in clusters if cluster.overlay]
            for suffix, part in (("", solid), (" · поверх земли", over)):
                if not part:
                    continue
                if title == TITLES["animal"] and suffix == "":
                    land = [
                        cluster for cluster in part
                        if all(item["item_key"] not in WATER_ANIMAL_KEYS for _, item in cluster.cells)
                    ]
                    water = [
                        cluster for cluster in part
                        if any(item["item_key"] in WATER_ANIMAL_KEYS for _, item in cluster.cells)
                    ]
                    top = self._add(_Row("header", top, HEADER_H, title=title, count=len(part)))
                    top = self._pack(land, top)
                    if water:
                        top = self._add(_Row("subheader", top, HEADER_H - 6, title="Водные", count=len(water)))
                        top = self._pack(water, top)
                    continue
                if (
                    title != TITLES["bush"]
                    and not title.startswith(("Скалистый биом", "Растущие объекты"))
                ):
                    part.sort(key=lambda cluster: cluster.color)
                count = sum(
                    1 if cluster.compound else len(cluster.cells)
                    for cluster in part
                )
                top = self._add(_Row("header", top, HEADER_H, title=title + suffix, count=count))
                if title == "Скалистый биом · Объекты в воде" and suffix == "":
                    other_clusters = [cluster for cluster in part if cluster.subsection is None]
                    ruin_clusters = sorted(
                        (cluster for cluster in part if cluster.subsection is not None),
                        key=lambda cluster: int(cluster.subsection.rsplit(" ", 1)[1]),
                    )
                    top = self._pack(other_clusters, top)
                    for cluster in ruin_clusters:
                        top = self._add(_Row(
                            "subheader",
                            top,
                            HEADER_H - 6,
                            title=cluster.subsection,
                            count=len(cluster.cells),
                        ))
                        top = self._pack([cluster], top)
                    continue
                if part[0].layers:
                    captions = [(pygame.Rect(layer["x"] * self.tile, 0, layer["w"] * self.tile, CAPTION_H), layer)
                        for layer in part[0].layers
                        if layer["y"] == 0 and (layer.get("name") or layer.get("number"))]
                    if captions:
                        top = self._add(_Row("caption", top, CAPTION_H, cells=captions))
                if title == TITLES["bush"] and suffix == "":
                    growing = [cluster for cluster in part if cluster.series]
                    decorations = [cluster for cluster in part if not cluster.series]
                    top = self._pack(growing, top)
                    top = self._pack(decorations, top)
                elif title == ROCKY_GROWTH_TITLE and suffix == "":
                    for cluster in part:
                        first_item = cluster.cells[0][1]
                        label = first_item["display_name"].split(" · стадия", 1)[0]
                        top = self._add(_Row(
                            "subheader",
                            top,
                            HEADER_H - 6,
                            title=label,
                            count=len(cluster.cells),
                        ))
                        top = self._pack([cluster], top)
                elif title == "Растущие объекты" and suffix == "":
                    for cluster in part:
                        first_item = cluster.cells[0][1]
                        label = first_item["display_name"].split(" · стадия", 1)[0]
                        top = self._add(_Row(
                            "subheader",
                            top,
                            HEADER_H - 6,
                            title=label,
                            count=len(cluster.cells),
                        ))
                        top = self._pack([cluster], top)
                elif title == "Скалистый биом · Цельные детали и растения" and suffix == "":
                    for cluster in part:
                        first_item = cluster.cells[0][1]
                        label = first_item.get("display_name", cluster.cells[0][1]["item_key"])
                        if first_item.get("growth_series") is not None:
                            label = label.split(" · стадия", 1)[0]
                        top = self._add(_Row(
                            "subheader",
                            top,
                            HEADER_H - 6,
                            title=label,
                            count=len(cluster.cells),
                        ))
                        top = self._pack([cluster], top)
                else:
                    top = self._pack(part, top)
        self._tops = [row.top for row in self.rows]
        self.height = self.rows[-1].top + self.rows[-1].height if self.rows else 0

    @staticmethod
    def _arrangement_order(title, clusters):
        if title == "Лёд и трещины":
            return list(clusters)
        if title == TITLES["animal"]:
            land = [
                cluster for cluster in clusters
                if all(item["item_key"] not in WATER_ANIMAL_KEYS for _, item in cluster.cells)
            ]
            water = [
                cluster for cluster in clusters
                if any(item["item_key"] in WATER_ANIMAL_KEYS for _, item in cluster.cells)
            ]
            return land + water
        solid = [cluster for cluster in clusters if not cluster.overlay]
        over = [cluster for cluster in clusters if cluster.overlay]
        if title != TITLES["bush"] and not title.startswith(
            ("Скалистый биом", "Растущие объекты")
        ):
            solid.sort(key=lambda cluster: cluster.color)
            over.sort(key=lambda cluster: cluster.color)
        return solid + over

    def _legacy_position_keys(self, clusters):
        items = {
            item["item_key"]
            for cluster in clusters
            for _position, item in cluster.cells
            if not cluster.compound and cluster.preview_group is None
        }
        if items and all(
            "palette_position" in self.rules.get(key, {})
            for key in items
        ):
            return items
        return set()

    def legacy_position_keys(self):
        """Return keys from old layouts that stored a position for every cell in a section."""
        keys = set()
        for _title, clusters in self._sections:
            eligible = [
                cluster for cluster in clusters
                if cluster.preview_group is None and not cluster.compound
            ]
            keys.update(self._legacy_position_keys(eligible))
        return keys

    def _pack_arrangement(self, group, clusters, top):
        items = []
        seen = set()
        default_positions = {}
        column = line = row_height = 0
        legacy_positions = self._legacy_position_keys(clusters)
        keep_artwork_groups = any(
            UNDEAD_TILE_SPECS.get(item["item_key"], {}).get("mountain_group")
            for cluster in clusters
            for _position, item in cluster.cells
        )
        for cluster in clusters:
            if cluster.preview_group is not None or cluster.compound:
                continue
            if column and column + cluster.cols > COLUMNS:
                line += row_height
                column = row_height = 0
            for position, item in cluster.cells:
                key = item["item_key"]
                if key in seen or key in self._compound_stamps:
                    continue
                seen.add(key)
                items.append(item)
                default_positions[key] = (
                    column + position[0],
                    line + position[1],
                )
            column += cluster.cols
            row_height = max(row_height, cluster.rows)
        positions = {
            key: position
            for key, position in default_positions.items()
            if keep_artwork_groups
            or key in legacy_positions
            or "palette_position" not in self.rules.get(key, {})
        }
        occupied = {position: key for key, position in positions.items()}
        for item in items:
            key = item["item_key"]
            rule = self.rules.get(key, {})
            position = rule.get("palette_position")
            if (
                keep_artwork_groups
                or key in legacy_positions
                or not isinstance(position, dict)
            ):
                continue
            slot = (position.get("x"), position.get("y"))
            if (
                isinstance(slot[0], int)
                and not isinstance(slot[0], bool)
                and isinstance(slot[1], int)
                and not isinstance(slot[1], bool)
                and 0 <= slot[0] < COLUMNS
                and 0 <= slot[1] < 256
                and slot not in occupied
            ):
                occupied[slot] = item
                positions[key] = slot
            else:
                default_slot = default_positions[key]
                if default_slot not in occupied:
                    occupied[default_slot] = key
                    positions[key] = default_slot

        if not items:
            return top
        rows = max(
            max((line for _column, line in default_positions.values()), default=0),
            max((line for _column, line in positions.values()), default=0),
        ) + 1
        if self.arrange_mode:
            rows = min(256, rows + 1)
        cells = [
            (
                pygame.Rect(
                    column * self.tile,
                    line * self.tile,
                    self.tile,
                    self.tile,
                ),
                item,
            )
            for item in items
            for column, line in (positions[item["item_key"]],)
        ]
        return self._add(_Row(
            "block",
            top,
            rows * self.tile + 2 * BLOCK_PAD,
            size=(COLUMNS * self.tile, rows * self.tile),
            cells=cells,
            arrange_group=group,
            default_positions=default_positions,
        ))

    def _pack(self, clusters, top):
        """Раскладывает группы по рядам слева направо: форма каждой группы сохраняется, стыки остаются бесшовными."""
        object_side = max(OBJECT_CELL_MIN, 2 * self.tile + 4)
        limit = min(COLUMNS * self.tile, self.panel_width() - PANEL_MARGIN)
        shelf, frames, previews, x, height = [], [], [], 0, 0

        def flush(top):
            if not shelf:
                return top
            size = (x - CLUSTER_GAP, height)
            return self._add(_Row(
                "block",
                top,
                height + 2 * BLOCK_PAD,
                size=size,
                cells=list(shelf),
                frames=list(frames),
                previews=list(previews),
            ))

        for cluster in clusters:
            side = object_side if cluster.objects else self.tile
            if cluster.artist_context:
                side = min(
                    self.tile,
                    max(1, (self.max_panel - PANEL_MARGIN) // cluster.cols),
                )
            elif cluster.objects:
                side = min(side, limit // cluster.cols)
            elif cluster.preview_group is not None:
                side = min(side, max(1, limit // cluster.cols))
            width = cluster.cols * side
            if shelf and x + width > limit:
                top = flush(top)
                shelf.clear()
                frames.clear()
                previews.clear()
                x, height = 0, 0
            for (dx, dy), item in cluster.cells:
                shelf.append((pygame.Rect(x + dx * side, dy * side, side, side), item))
            if cluster.preview_group is not None:
                previews.append((
                    pygame.Rect(x, 0, width, cluster.rows * side),
                    cluster.preview_group,
                ))
            for layer in cluster.layers:
                frame = pygame.Rect(x + layer["x"] * side, layer["y"] * side, layer["w"] * side, layer["h"] * side)
                label = None if layer["y"] == 0 else (f"{layer['number']} · " if layer["number"] else "") + layer["name"]
                frames.append((frame, layer["role"], label))
            x += width + CLUSTER_GAP
            height = max(height, cluster.rows * side)
        return flush(top)

    def _add(self, row):
        self.rows.append(row)
        return row.top + row.height

    def item_at(self, x, y):
        """Ключ элемента под точкой (x, y) в координатах содержимого палитры (без прокрутки)."""
        index = bisect_right(self._tops, y) - 1
        if index < 0:
            return None
        row = self.rows[index]
        if row.kind != "block" or y >= row.top + row.height:
            return None
        local_x, local_y = x - BLOCK_X, y - row.top - BLOCK_PAD
        for rect, group in row.previews:
            if rect.collidepoint(local_x, local_y):
                return group.get("primary_key", group["key"])
        for rect, item in row.cells:
            if rect.collidepoint(local_x, local_y):
                return item["item_key"]
        return None

    def item_layer_at(self, x, y):
        """Слой карты для конкретного тайла образца палитры или None вне блока с назначенной ролью."""
        index = bisect_right(self._tops, y) - 1
        if index < 0:
            return None
        row = self.rows[index]
        if row.kind != "block" or y >= row.top + row.height:
            return None
        local_x, local_y = x - BLOCK_X, y - row.top - BLOCK_PAD
        if any(rect.collidepoint(local_x, local_y) for rect, _group in row.previews):
            return None
        if not any(rect.collidepoint(local_x, local_y) for rect, _ in row.cells):
            return None
        for frame, role, _ in row.frames:
            if frame.collidepoint(local_x, local_y):
                return storage_layer_for_palette_role(role)
        for rect, item in row.cells:
            if not rect.collidepoint(local_x, local_y):
                continue
            spec = ROCKY_TILE_SPECS.get(item["item_key"])
            if spec is not None and spec.get("sheet") == "Ground_moss":
                return storage_layer_for_palette_role(spec["layer"])
            spec = UNDEAD_TILE_SPECS.get(item["item_key"])
            if spec is not None and spec.get("sheet") == "Ground_rocks":
                return storage_layer_for_palette_role(spec["layer"])
        return None

    def item_rect(self, key):
        """Прямоугольник клетки элемента в координатах содержимого палитры (без прокрутки) или None."""
        for row in self.rows:
            if row.kind != "block":
                continue
            for rect, item in row.cells:
                if item["item_key"] == key:
                    return rect.move(BLOCK_X, row.top + BLOCK_PAD)
        return None

    def _marquee_hits(self, start, end):
        """Ряд, где началась рамка из start в end (координаты содержимого палитры), и клетки ряда под рамкой."""
        index = bisect_right(self._tops, start[1]) - 1
        if index < 0 or self.rows[index].kind != "block":
            return None, []
        row = self.rows[index]
        left, right = sorted((start[0], end[0]))
        top, bottom = sorted((start[1], end[1]))
        area = pygame.Rect(left - BLOCK_X, top - row.top - BLOCK_PAD, right - left + 1, bottom - top + 1)
        return row, [(rect, item) for rect, item in row.cells if rect.colliderect(area)]

    def stamp_entries(self, start, end, with_layers=False):
        """Элементы под рамкой из start в end как [(ключ, столбец, строка)].

        Берётся ряд, где рамка началась; положение считается в клетках от левого верхнего угла рамки.
        """
        row, cells = self._marquee_hits(start, end)
        hits = [(round(rect.x / rect.w), round(rect.y / rect.h), item, rect) for rect, item in cells]
        if not hits:
            return []
        first_col = min(col for col, _, _, _ in hits)
        first_row = min(line for _, line, _, _ in hits)
        entries, taken = [], set()
        for col, line, item, rect in hits:
            position = (col - first_col, line - first_row)
            if position not in taken:
                taken.add(position)
                layer = next(
                    (storage_layer_for_palette_role(role) for frame, role, _ in row.frames
                     if frame.collidepoint(rect.center)),
                    None,
                )
                entry = (item["item_key"], *position)
                entries.append(entry + (layer,) if with_layers else entry)
        return entries

    def is_animated(self, key):
        return key in self.animations

    def compound_entries(self, key):
        """Return a complete animated composition as (dx, dy, key, layer) entries."""
        return list(self._compound_stamps.get(key, ()))

    def draw(
        self,
        screen,
        view,
        scroll,
        selected,
        marquee=None,
        hovered=None,
        ticks=0,
        arrangement_drag=None,
        arrangement_selection=None,
        arrangement_marquee=None,
    ):
        """hovered — ключ элемента под курсором: если он анимированный, его клетка проигрывает кадры по времени ticks (мс)."""
        previous_clip = screen.get_clip()
        screen.set_clip(view)
        first = max(0, bisect_right(self._tops, scroll) - 1)
        for row in self.rows[first:]:
            y = view.top + row.top - scroll
            if y >= view.bottom:
                break
            if y + row.height <= view.top:
                continue
            if row.kind == "header":
                self._draw_header(screen, row, view, y)
            elif row.kind == "subheader":
                self._draw_subheader(screen, row, view, y)
            elif row.kind == "legend":
                self._draw_legend(screen, y)
            elif row.kind == "caption":
                self._draw_caption(screen, row, y)
            else:
                self._draw_block(
                    screen,
                    row,
                    y,
                    selected,
                    hovered,
                    ticks,
                    arrangement_drag,
                    arrangement_selection,
                    arrangement_marquee,
                )
        if marquee is not None:
            row, cells = self._marquee_hits(*marquee)
            for rect, _ in cells:
                pygame.draw.rect(screen, SELECT_COLOR, rect.move(BLOCK_X, view.top + row.top + BLOCK_PAD - scroll), 2)
        screen.set_clip(previous_clip)

    def _draw_header(self, screen, row, view, y):
        pygame.draw.rect(screen, HEADER_BG, (view.x, y + 2, view.w, row.height - 4))
        screen.blit(self.font.render(row.title, True, TEXT), (PANEL_TEXT_X, y + 6))
        count = self.small.render(str(row.count), True, TEXT_DIM)
        screen.blit(count, (view.right - count.get_width() - 22, y + 9))

    def _draw_subheader(self, screen, row, view, y):
        pygame.draw.rect(screen, (32, 37, 45), (view.x + 8, y + 2, view.w - 8, row.height - 4))
        screen.blit(self.small.render(row.title, True, TEXT_DIM), (PANEL_TEXT_X + 8, y + 4))
        count = self.small.render(str(row.count), True, TEXT_DIM)
        screen.blit(count, (view.right - count.get_width() - 22, y + 5))

    def _draw_legend(self, screen, y):
        pygame.draw.polygon(screen, BLOCK_MARK, [(PANEL_TEXT_X, y + 6), (PANEL_TEXT_X + 10, y + 6), (PANEL_TEXT_X, y + 16)])
        screen.blit(self.small.render("непроходимо", True, TEXT_DIM), (PANEL_TEXT_X + 16, y + 5))
        pygame.draw.polygon(screen, PASSABLE_MARK, [(PANEL_TEXT_X + 112, y + 6), (PANEL_TEXT_X + 122, y + 6), (PANEL_TEXT_X + 122, y + 16)])
        screen.blit(self.small.render("проходимо", True, TEXT_DIM), (PANEL_TEXT_X + 128, y + 5))
        screen.blit(self.small.render("цифра внизу — рабочий слой", True, TEXT_DIM), (PANEL_TEXT_X, y + 25))

    def _draw_caption(self, screen, row, y):
        """Подписи слоёв образца над их блоками: номер, название и полоса цвета рамки."""
        for rect, layer in row.cells:
            color = LAYER_COLORS[layer["role"]]
            text = f"{layer['number']} · {layer['name']}" if layer["number"] else layer["name"]
            screen.blit(self.small.render(text, True, color), (BLOCK_X + rect.x + 2, y + 1))
            pygame.draw.rect(screen, color, (BLOCK_X + rect.x, y + row.height - 3, rect.w, 3))

    def _draw_block(
        self,
        screen,
        row,
        y,
        selected,
        hovered=None,
        ticks=0,
        arrangement_drag=None,
        arrangement_selection=None,
        arrangement_marquee=None,
    ):
        if row.surface is None:
            row.surface = self._block_surface(row)
        origin = (BLOCK_X, y + BLOCK_PAD)
        screen.blit(row.surface, origin)
        animated_keys = set()
        if hovered in self._compound_stamps:
            animated_keys.update(entry[2] for entry in self._compound_stamps[hovered])
        elif hovered in self.animations:
            animated_keys.add(hovered)
        preview_keys = set()
        for rect, group in row.previews:
            group_keys = {cell["key"] for cell in group["cells"]}
            if hovered == group["key"] or hovered in group_keys:
                preview_keys.update(group_keys)
                preview = self._water_preview(group, ticks, animated=True)
                screen.blit(
                    pygame.transform.scale(preview, self._preview_size(rect, group)),
                    self._preview_rect(rect, group).move(origin),
                )
        animated_keys.difference_update(preview_keys)
        for key in animated_keys:
            animation = self.animations.get(key)
            if animation is None:
                continue
            frame = animation_frame_index(animation, ticks)
            for rect, item in row.cells:
                if item["item_key"] == key:
                    self._paint_cell(screen, rect.move(origin), item, self._cell_image(item, rect.size, frame))
        if row.arrange_group is not None and arrangement_drag:
            drag_group, _drag_key, target = arrangement_drag
            if drag_group != row.arrange_group:
                target = None
            else:
                target = target[1:] if target and target[0] == drag_group else None
            if drag_group == row.arrange_group:
                for line in range(row.size[1] // self.tile):
                    for column in range(COLUMNS):
                        rect = pygame.Rect(
                            column * self.tile,
                            line * self.tile,
                            self.tile,
                            self.tile,
                        ).move(origin)
                        color = (
                            SELECT_COLOR
                            if target == (column, line)
                            else (92, 112, 132)
                        )
                        pygame.draw.rect(screen, color, rect, 2 if target == (column, line) else 1)
        if row.arrange_group is not None and arrangement_selection:
            for rect, item in row.cells:
                if item["item_key"] in arrangement_selection:
                    pygame.draw.rect(
                        screen,
                        SELECT_COLOR,
                        rect.move(origin),
                        2,
                    )
        if (
            row.arrange_group is not None
            and arrangement_marquee is not None
            and arrangement_marquee[0] == row.arrange_group
        ):
            _group, start, end = arrangement_marquee
            left, right = sorted((start[0], end[0]))
            top, bottom = sorted((start[1], end[1]))
            marquee_rect = pygame.Rect(
                left * self.tile,
                top * self.tile,
                (right - left + 1) * self.tile,
                (bottom - top + 1) * self.tile,
            ).move(origin)
            pygame.draw.rect(screen, SELECT_COLOR, marquee_rect, 2)
        selected_entries = self._compound_stamps.get(selected)
        if selected_entries:
            selected_preview = next(
                (
                    (rect, group) for rect, group in row.previews
                    if selected == group["key"]
                    or selected in {cell["key"] for cell in group["cells"]}
                ),
                None,
            )
            if selected_preview is not None:
                rect, group = selected_preview
                pygame.draw.rect(
                    screen,
                    SELECT_COLOR,
                    self._preview_rect(rect, group).move(origin),
                    2,
                )
                return
            selected_keys = {entry[2] for entry in selected_entries}
            selected_rects = [
                rect for rect, item in row.cells if item["item_key"] in selected_keys
            ]
            if selected_rects:
                selected_rect = selected_rects[0].copy()
                for rect in selected_rects[1:]:
                    selected_rect.union_ip(rect)
                pygame.draw.rect(screen, SELECT_COLOR, selected_rect.move(origin), 2)
            return
        for rect, item in row.cells:
            if item["item_key"] == selected:
                pygame.draw.rect(screen, SELECT_COLOR, rect.move(origin), 2)

    def _paint_cell(self, target, rect, item, image):
        """Клетка палитры: фон, картинка, рамка и метки проходимости, слоя и декора."""
        pygame.draw.rect(target, CELL_BG, rect)
        target.blit(image, rect)
        if item["item_key"] in self._compound_stamps:
            return
        if item.get("palette_artist_copy"):
            return
        pygame.draw.rect(target, GRID_COLOR, rect, 1)
        mark = max(4, rect.w // 5)
        rule = self.rules.get(item["item_key"], {})
        if rule.get("blocks", item["blocks"]):
            corner = [(rect.left, rect.top), (rect.left + mark, rect.top), (rect.left, rect.top + mark)]
            pygame.draw.polygon(target, BLOCK_MARK, corner)
        else:
            corner = [
                (rect.left, rect.top),
                (rect.left + mark, rect.top),
                (rect.left, rect.top + mark),
            ]
            pygame.draw.polygon(target, PASSABLE_MARK, corner)
        layer = rule.get("editor_layer", item.get("editor_layer", layer_of(item)))
        if layer is not None:
            digit = self.small.render(str(layer), True, LAYER_DIGIT_COLOR)
            chip = pygame.Rect(rect.x + 2, rect.bottom - digit.get_height() - 3, digit.get_width() + 6, digit.get_height() + 2)
            pygame.draw.rect(target, LAYER_DIGIT_BG, chip, border_radius=3)
            target.blit(digit, (chip.x + 3, chip.y + 1))

    def _block_surface(self, row):
        """Ряд групп: фон клетки, картинка, рамка и метки проходимости и слоя."""
        surface = pygame.Surface(row.size, pygame.SRCALPHA)
        animated_preview_keys = {
            cell["key"]
            for _rect, group in row.previews
            if self._preview_is_animated(group)
            for cell in group["cells"]
        }
        for rect, item in row.cells:
            if item["item_key"] in animated_preview_keys:
                continue
            self._paint_cell(surface, rect, item, self._cell_image(item, rect.size))
        for rect, group in row.previews:
            preview = self._water_preview(group)
            surface.blit(
                pygame.transform.scale(preview, self._preview_size(rect, group)),
                self._preview_rect(rect, group),
            )
        for frame, role, label in row.frames:
            pygame.draw.rect(surface, LAYER_COLORS[role], frame, FRAME_W)
            if label:
                text = self.small.render(label, True, LAYER_COLORS[role])
                chip = pygame.Rect(frame.x + FRAME_W, frame.y + FRAME_W, text.get_width() + 6, text.get_height() + 2)
                pygame.draw.rect(surface, HEADER_BG, chip)
                surface.blit(text, (chip.x + 3, chip.y + 1))
        return surface

    def arrangement_position_at(self, x, y):
        for row in self.rows:
            if row.arrange_group is None or not row.top <= y < row.top + row.height:
                continue
            local_x = x - BLOCK_X
            local_y = y - row.top - BLOCK_PAD
            column, line = local_x // self.tile, local_y // self.tile
            if 0 <= column < COLUMNS and 0 <= line < min(256, row.size[1] // self.tile):
                return row.arrange_group, column, line
        return None

    def arrangement_group_for_item(self, key):
        for row in self.rows:
            if row.arrange_group is not None and any(
                item["item_key"] == key for _rect, item in row.cells
            ):
                return row.arrange_group
        return None

    def arrangement_positions(self, group):
        for row in self.rows:
            if row.arrange_group == group:
                return {
                    item["item_key"]: (rect.x // self.tile, rect.y // self.tile)
                    for rect, item in row.cells
                }
        return {}

    def arrangement_items_in_rect(self, group, start, end):
        left, right = sorted((start[0], end[0]))
        top, bottom = sorted((start[1], end[1]))
        for row in self.rows:
            if row.arrange_group != group:
                continue
            return {
                item["item_key"]
                for rect, item in row.cells
                if left <= rect.x // self.tile <= right
                and top <= rect.y // self.tile <= bottom
            }
        return set()

    def arrangement_item_at(self, position, group=None):
        if position is None:
            return None
        if len(position) == 3:
            group, column, line = position
        else:
            column, line = position
        for row in self.rows:
            if row.arrange_group is None or row.arrange_group != group:
                continue
            return next(
                (
                    item["item_key"]
                    for rect, item in row.cells
                    if rect.topleft == (
                        column * self.tile,
                        line * self.tile,
                    )
                ),
                None,
            )
        return None

    def _preview_is_animated(self, group):
        return any(cell["key"] in self.animations for cell in group["cells"])

    def _preview_size(self, rect, group):
        if not self._preview_is_animated(group):
            return rect.size
        return (
            max(1, round(rect.w * ANIMATED_PREVIEW_SCALE)),
            max(1, round(rect.h * ANIMATED_PREVIEW_SCALE)),
        )

    def _preview_rect(self, rect, group):
        size = self._preview_size(rect, group)
        return pygame.Rect(
            rect.centerx - size[0] // 2,
            rect.centery - size[1] // 2,
            *size,
        )

    def _water_preview(self, group, ticks=0, animated=False):
        frame_indices = tuple(
            (
                cell["key"],
                animation_frame_index(self.animations[cell["key"]], ticks),
            )
            for cell in group["cells"]
            if animated and cell["key"] in self.animations
        )
        cache_key = None if animated else group["key"]
        if cache_key is not None and cache_key in self._water_preview_cache:
            return self._water_preview_cache[cache_key]

        surface = pygame.Surface(
            (group["width"] * SOURCE_TILE, group["height"] * SOURCE_TILE),
            pygame.SRCALPHA,
        )
        surface.fill(CELL_BG)
        frame_by_key = dict(frame_indices)
        for cell in group["cells"]:
            item = self._catalog_items[cell["key"]]
            if item["kind"] != "ground":
                continue
            native = self._native_image(item, frame_by_key.get(cell["key"], 0))
            image = pygame.transform.scale(native, (SOURCE_TILE, SOURCE_TILE))
            surface.blit(image, (cell["x"] * SOURCE_TILE, cell["y"] * SOURCE_TILE))
        for cell in group["cells"]:
            item = self._catalog_items[cell["key"]]
            if item["kind"] == "ground":
                continue
            native = self._native_image(item)
            render_offset = item.get("render_offset_tiles", {})
            anchor = (
                round((cell["x"] + 0.5 + render_offset.get("x", 0)) * SOURCE_TILE),
                round((cell["y"] + 1 + render_offset.get("y", 0)) * SOURCE_TILE),
            )
            surface.blit(native, native.get_rect(midbottom=anchor))
        if cache_key is not None:
            self._water_preview_cache[cache_key] = surface
        return surface

    def _native_image(self, item, frame=0):
        """Картинка элемента; у элемента-листа кадров — нужный кадр листа."""
        asset = item["asset"]
        if asset not in self._sheets:
            self._sheets[asset] = pygame.image.load(str(self.map_dir / asset)).convert_alpha()
        sheet = self._sheets[asset]
        animation = self.animations.get(item["item_key"])
        biome_spec = BIOME_TILE_SPECS.get(item["item_key"])
        if biome_spec is not None and biome_spec.get("representation") != "sprite":
            return rocky_tile_frame(item["item_key"], sheet, frame)
        if animation is None:
            return sheet
        frame_w, frame_h = animation["frame"]
        tile_ids = animation.get("tile_ids")
        if tile_ids:
            tile_id = tile_ids[frame % len(tile_ids)]
            columns = sheet.get_width() // frame_w
            column, line = tile_id % columns, tile_id // columns
        else:
            column, line = frame % animation["cols"], frame // animation["cols"]
        return sheet.subsurface(pygame.Rect(column * frame_w, line * frame_h, frame_w, frame_h))

    def _cell_image(self, item, size, frame=0):
        """Картинка элемента по размеру клетки: тайл растягивается, объект вписывается с сохранением пропорций."""
        cache_key = (
            item["item_key"],
            item["asset"],
            size,
            frame if item["item_key"] in self.animations else 0,
        )
        if cache_key not in self._images:
            native = self._native_image(item, frame)
            image = pygame.Surface(size, pygame.SRCALPHA)
            if item["kind"] == "ground":
                image.blit(pygame.transform.smoothscale(native, size), (0, 0))
            else:
                ref_w, ref_h = self._fit_ref.get(
                    item["item_key"],
                    (max(SOURCE_TILE, native.get_width()), max(SOURCE_TILE, native.get_height())),
                )
                factor = min((size[0] - 4) / ref_w, (size[1] - 4) / ref_h)
                fitted = (max(1, round(native.get_width() * factor)), max(1, round(native.get_height() * factor)))
                scaled = pygame.transform.smoothscale(native, fitted)
                if _is_series_item(item):
                    base_x, base_y = series_base(scaled)
                    image.blit(scaled, (size[0] // 2 - base_x, size[1] - SERIES_BASE_GAP - base_y))
                else:
                    image.blit(scaled, scaled.get_rect(center=(size[0] // 2, size[1] // 2)))
            self._images[cache_key] = image
        return self._images[cache_key]
