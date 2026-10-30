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
    overlay_keys,
    palette_group_decor,
    palette_group_layers,
    palette_groups,
    palette_hidden_keys,
    palette_sheets,
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
HUE_BUCKETS = 12
GRAY_SATURATION = 0.15

GROUND_ORDER = ("grass", "road", "water", "floor", "rock", "leaves")
OBJECT_ORDER = ("tree", "old_tree", "stump", "log", "bush")
TITLES = {
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
}

TEXT = (235, 235, 235)
TEXT_DIM = (160, 166, 176)
HEADER_BG = (40, 44, 52)
CELL_BG = (30, 34, 40)
SELECT_COLOR = (120, 200, 255)
GRID_COLOR = (58, 63, 72)
BLOCK_MARK = (230, 70, 70)
OVERLAY_MARK = (80, 160, 255)
DECOR_MARK = (240, 210, 70)
LAYER_DIGIT_COLOR = (255, 255, 255)
LAYER_DIGIT_BG = (20, 22, 28)
LAYER_COLORS = {
    "ground": (214, 150, 80), "grass": (110, 200, 110),
    "ground_decor": (170, 110, 50), "grass_decor": (70, 150, 80),
    "elevation": (170, 140, 230), "river": (90, 170, 230),
    "ground_small": (140, 100, 55), "grass_small": (80, 140, 90), "mountain": (205, 170, 120),
}

_RGB_CACHE = {}


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


@dataclass
class _Cluster:
    cells: list
    cols: int
    rows: int
    color: tuple
    overlay: bool
    objects: bool = False
    layers: list = field(default_factory=list)


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
    surface: pygame.Surface | None = None


class Palette:
    """Строки палитры: заголовки разделов и ряды групп тайлов и объектов."""

    def __init__(self, catalog, map_dir, font, small, tile=VIEW_TILE, max_panel=640, animations=None):
        """animations: {ключ элемента: {"frame": (ширина, высота), "frames": число кадров, "cols": кадров в строке листа,
        "ms": мс на кадр}}. Такой элемент лежит в файле листом кадров: в палитре виден первый кадр, а под курсором идёт анимация."""
        self.font = font
        self.max_panel = max_panel
        self.small = small
        self.map_dir = Path(map_dir)
        self.animations = dict(animations or {})
        self._images = {}
        self._sheets = {}
        self._overlay = overlay_keys()
        self._decor = frozenset(
            key for group in palette_groups() for part in palette_group_decor(group).values() for key in part["decor"]
        )
        self.tile = tile
        self._sections = self._group(catalog)
        self._layout()

    @property
    def scale(self):
        return self.tile / SOURCE_TILE

    def panel_width(self):
        """Ширина панели каталога: COLUMNS тайлов в ряд, но не уже PANEL_W_MIN и не шире max_panel."""
        return max(PANEL_W_MIN, min(COLUMNS * self.tile + PANEL_MARGIN, self.max_panel))

    def set_tile(self, tile):
        """Меняет размер тайла в палитре и пересобирает строки."""
        if tile == self.tile:
            return
        self.tile = tile
        self._images = {}
        self._layout()

    def _group(self, catalog):
        """Разделы (название, группы) в порядке показа.

        Сначала образцы художника из palette_groups.json, затем остальные тайлы по типу и объекты,
        в самом низу копии блоков листа из palette_sheets.json; группы одного вида идут по цвету.
        """
        tiles = defaultdict(lambda: defaultdict(dict))
        objects = defaultdict(list)
        sections = []
        by_key = {item["item_key"]: item for item in catalog}
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
        for item in catalog:
            if item["item_key"] in grouped:
                continue
            position = _tile_position(item)
            if position is None:
                objects[item["category"]].append(item)
            else:
                block, row, col = position
                tiles[item["category"]][block][(row, col)] = item
        for category in self._ordered(tiles, GROUND_ORDER):
            clusters = []
            for block, cells in sorted(tiles[category].items()):
                for group in _connected(cells):
                    clusters.append(self._tile_cluster(group, cells))
            sections.append((TITLES.get(category, category), clusters))
        for category in self._ordered(objects, OBJECT_ORDER):
            items = sorted(objects[category], key=lambda item: item["item_key"])
            clusters = [self._object_cluster(item) for item in items]
            sections.append((TITLES.get(category, category), clusters))
        for sheet in palette_sheets():
            cells = [((cell["x"], cell["y"]), by_key[cell["key"]]) for cell in sheet["cells"] if cell["key"] in by_key]
            if cells:
                cols = max(dx for (dx, _), _ in cells) + 1
                rows = max(dy for (_, dy), _ in cells) + 1
                sections.append((sheet["title"], [_Cluster(cells, cols, rows, (0, 0.0), False)]))
        return sections

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

    def _object_cluster(self, item):
        color = _color_key([_average_rgb(self.map_dir / item["asset"])])
        return _Cluster([((0, 0), item)], 1, 1, color, False, objects=True)

    def _layout(self):
        self.rows = []
        top = self._add(_Row("legend", 0, LEGEND_H))
        for title, clusters in self._sections:
            solid = [cluster for cluster in clusters if not cluster.overlay]
            over = [cluster for cluster in clusters if cluster.overlay]
            for suffix, part in (("", solid), (" · поверх земли", over)):
                if not part:
                    continue
                part.sort(key=lambda cluster: cluster.color)
                count = sum(len(cluster.cells) for cluster in part)
                top = self._add(_Row("header", top, HEADER_H, title=title + suffix, count=count))
                if part[0].layers:
                    captions = [(pygame.Rect(layer["x"] * self.tile, 0, layer["w"] * self.tile, CAPTION_H), layer)
                        for layer in part[0].layers if layer["y"] == 0]
                    top = self._add(_Row("caption", top, CAPTION_H, cells=captions))
                top = self._pack(part, top)
        self._tops = [row.top for row in self.rows]
        self.height = self.rows[-1].top + self.rows[-1].height if self.rows else 0

    def _pack(self, clusters, top):
        """Раскладывает группы по рядам слева направо: форма каждой группы сохраняется, стыки остаются бесшовными."""
        object_side = max(OBJECT_CELL_MIN, 2 * self.tile + 4)
        limit = min(COLUMNS * self.tile, self.panel_width() - PANEL_MARGIN)
        shelf, frames, x, height = [], [], 0, 0

        def flush(top):
            if not shelf:
                return top
            size = (x - CLUSTER_GAP, height)
            return self._add(_Row("block", top, height + 2 * BLOCK_PAD, size=size, cells=list(shelf), frames=list(frames)))

        for cluster in clusters:
            side = object_side if cluster.objects else self.tile
            width = cluster.cols * side
            if shelf and x + width > limit:
                top = flush(top)
                shelf.clear()
                frames.clear()
                x, height = 0, 0
            for (dx, dy), item in cluster.cells:
                shelf.append((pygame.Rect(x + dx * side, dy * side, side, side), item))
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
        for rect, item in row.cells:
            if rect.collidepoint(local_x, local_y):
                return item["item_key"]
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

    def stamp_entries(self, start, end):
        """Элементы под рамкой из start в end как [(ключ, столбец, строка)].

        Берётся ряд, где рамка началась; положение считается в клетках от левого верхнего угла рамки.
        """
        _, cells = self._marquee_hits(start, end)
        hits = [(round(rect.x / rect.w), round(rect.y / rect.h), item) for rect, item in cells]
        if not hits:
            return []
        first_col = min(col for col, _, _ in hits)
        first_row = min(line for _, line, _ in hits)
        entries, taken = [], set()
        for col, line, item in hits:
            position = (col - first_col, line - first_row)
            if position not in taken:
                taken.add(position)
                entries.append((item["item_key"], *position))
        return entries

    def is_animated(self, key):
        return key in self.animations

    def draw(self, screen, view, scroll, selected, marquee=None, hovered=None, ticks=0):
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
            elif row.kind == "legend":
                self._draw_legend(screen, y)
            elif row.kind == "caption":
                self._draw_caption(screen, row, y)
            else:
                self._draw_block(screen, row, y, selected, hovered, ticks)
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

    def _draw_legend(self, screen, y):
        pygame.draw.polygon(screen, BLOCK_MARK, [(PANEL_TEXT_X, y + 6), (PANEL_TEXT_X + 10, y + 6), (PANEL_TEXT_X, y + 16)])
        screen.blit(self.small.render("непроходимо", True, TEXT_DIM), (PANEL_TEXT_X + 16, y + 5))
        pygame.draw.rect(screen, OVERLAY_MARK, (PANEL_TEXT_X + 112, y + 7, 9, 9))
        screen.blit(self.small.render("поверх земли", True, TEXT_DIM), (PANEL_TEXT_X + 126, y + 5))
        pygame.draw.rect(screen, DECOR_MARK, (PANEL_TEXT_X, y + 27, 9, 9))
        screen.blit(self.small.render("декор: добавляется в основу случайно", True, TEXT_DIM), (PANEL_TEXT_X + 16, y + 25))

    def _draw_caption(self, screen, row, y):
        """Подписи слоёв образца над их блоками: номер, название и полоса цвета рамки."""
        for rect, layer in row.cells:
            color = LAYER_COLORS[layer["role"]]
            text = f"{layer['number']} · {layer['name']}" if layer["number"] else layer["name"]
            screen.blit(self.small.render(text, True, color), (BLOCK_X + rect.x + 2, y + 1))
            pygame.draw.rect(screen, color, (BLOCK_X + rect.x, y + row.height - 3, rect.w, 3))

    def _draw_block(self, screen, row, y, selected, hovered=None, ticks=0):
        if row.surface is None:
            row.surface = self._block_surface(row)
        origin = (BLOCK_X, y + BLOCK_PAD)
        screen.blit(row.surface, origin)
        if hovered in self.animations:
            animation = self.animations[hovered]
            frame = (int(ticks) // animation["ms"]) % animation["frames"]
            for rect, item in row.cells:
                if item["item_key"] == hovered:
                    self._paint_cell(screen, rect.move(origin), item, self._cell_image(item, rect.size, frame))
        for rect, item in row.cells:
            if item["item_key"] == selected:
                pygame.draw.rect(screen, SELECT_COLOR, rect.move(origin), 2)

    def _paint_cell(self, target, rect, item, image):
        """Клетка палитры: фон, картинка, рамка и метки проходимости, слоя и декора."""
        pygame.draw.rect(target, CELL_BG, rect)
        target.blit(image, rect)
        pygame.draw.rect(target, GRID_COLOR, rect, 1)
        mark = max(4, rect.w // 5)
        if item["blocks"]:
            corner = [(rect.left, rect.top), (rect.left + mark, rect.top), (rect.left, rect.top + mark)]
            pygame.draw.polygon(target, BLOCK_MARK, corner)
        if item["item_key"] in self._overlay:
            pygame.draw.rect(target, OVERLAY_MARK, (rect.right - mark, rect.bottom - mark, mark, mark))
        if item["item_key"] in self._decor:
            pygame.draw.rect(target, DECOR_MARK, (rect.right - mark, rect.top, mark, mark))
        layer = layer_of(item)
        if layer is not None:
            digit = self.small.render(str(layer), True, LAYER_DIGIT_COLOR)
            chip = pygame.Rect(rect.x + 2, rect.bottom - digit.get_height() - 3, digit.get_width() + 6, digit.get_height() + 2)
            pygame.draw.rect(target, LAYER_DIGIT_BG, chip, border_radius=3)
            target.blit(digit, (chip.x + 3, chip.y + 1))

    def _block_surface(self, row):
        """Ряд групп: фон клетки, картинка, рамка и метки проходимости и слоя."""
        surface = pygame.Surface(row.size, pygame.SRCALPHA)
        for rect, item in row.cells:
            self._paint_cell(surface, rect, item, self._cell_image(item, rect.size))
        for frame, role, label in row.frames:
            pygame.draw.rect(surface, LAYER_COLORS[role], frame, FRAME_W)
            if label:
                text = self.small.render(label, True, LAYER_COLORS[role])
                chip = pygame.Rect(frame.x + FRAME_W, frame.y + FRAME_W, text.get_width() + 6, text.get_height() + 2)
                pygame.draw.rect(surface, HEADER_BG, chip)
                surface.blit(text, (chip.x + 3, chip.y + 1))
        return surface

    def _native_image(self, item, frame=0):
        """Картинка элемента; у элемента-листа кадров — нужный кадр листа."""
        asset = item["asset"]
        if asset not in self._sheets:
            self._sheets[asset] = pygame.image.load(str(self.map_dir / asset)).convert_alpha()
        sheet = self._sheets[asset]
        animation = self.animations.get(item["item_key"])
        if animation is None:
            return sheet
        frame_w, frame_h = animation["frame"]
        column, line = frame % animation["cols"], frame // animation["cols"]
        return sheet.subsurface(pygame.Rect(column * frame_w, line * frame_h, frame_w, frame_h))

    def _cell_image(self, item, size, frame=0):
        """Картинка элемента по размеру клетки: тайл растягивается, объект вписывается с сохранением пропорций."""
        cache_key = (item["asset"], size, frame if item["item_key"] in self.animations else 0)
        if cache_key not in self._images:
            native = self._native_image(item, frame)
            image = pygame.Surface(size, pygame.SRCALPHA)
            if item["kind"] == "ground":
                image.blit(pygame.transform.smoothscale(native, size), (0, 0))
            else:
                factor = min((size[0] - 4) / native.get_width(), (size[1] - 4) / native.get_height())
                fitted = (max(1, round(native.get_width() * factor)), max(1, round(native.get_height() * factor)))
                scaled = pygame.transform.smoothscale(native, fitted)
                image.blit(scaled, scaled.get_rect(center=(size[0] // 2, size[1] // 2)))
            self._images[cache_key] = image
        return self._images[cache_key]
