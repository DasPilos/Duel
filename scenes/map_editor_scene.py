"""Редактор карт в духе Heroes 3: строка меню, инструменты, каталог слева, сетка карты справа, сохранение и применение."""
from pathlib import Path

import pygame

from client import map_drafts
from client.map_editor_seed import build_tower_seed_cells
from client.map_editor_state import MapEditorState
from client.network import ServerError
from core import mob_modes, settings
from core.crystal_growth import (
    check_loot_order, crystal_colors, crystal_unlocked, parse_crystal_key, settings_for,
)
from core.game_modes import DEFAULT_MODE, GAME_MODES, is_mode, mode_name
from core.map_catalog import (
    DEFAULT_MAP_SIZE, ROCKY_GROUND_MOSS_GRASS_TILE_IDS, palette_role_keys, rocky_animations, rocky_tile_specs, terrain_layer_for_key,
    desert_animations, desert_tile_specs, undead_animations, undead_tile_specs,
    grassland_animations, grassland_tile_specs,
    water_decor_keys, winter_animated_groups, winter_animations, winter_tile_specs,
)
from core.npc_catalog import NPC_FRAME, NPC_FRAMES_PER_ROW, NPC_ROW_DOWN, npc_catalog, sheet_path
from core.tile_mask import FREE, MASK_SIDE, load_partial_masks, save_partial_masks
from scenes.map_editor_ui import BUTTON_BG, BUTTON_ON, MENU_H, TOOL_H, CrystalSettingsDialog, DraftList, ExitDialog, MaskDialog, Minimap, MenuBar, MobParamsDialog, PaletteConflictDialog, PaletteCredentialDialog, SaveDialog, SizePicker, TextPrompt, ToolBar, WorldPicker
from core.item_form import validate_form
from core.map_animals import ANIMAL_SHEETS, WATERFOWL_SHEETS
from scenes.item_form_dialog import ItemFormDialog
from scenes.map_equipment_palette import EquipmentPalette
from scenes.map_palette import (
    BLOCK_PAD, BLOCK_X,
    SERIES_CATEGORIES,
    Palette, animation_frame_index, maximum_tile_size, rocky_tile_frame, series_base,
)
from scenes.world_map_scene import (
    MAP_PROP_SCALE,
    MAP_TREE_COLUMNS,
    MAP_TREE_FRAME_MS,
    MAP_TREE_FRAMES,
    MAP_TREE_FRAMES_PER_ROW,
    MAP_TREE_SCALE,
    MAP_TREE_SHEETS,
)

MAP_DIR = Path(__file__).resolve().parent.parent / "assets" / "map"
TILE = 32
WHEEL_STEP = 60
THUMB = 40
TOP = MENU_H + TOOL_H
LIST_OFFSET = 90
ADD_ITEM_H = 32  # полоса над списком каталога: кнопка «Добавить предмет»
SCROLL_W = 12
SCROLL_GAP = 18
SCROLL_MIN_THUMB = 30
MINI_PAD = 12
MINIMAP_BUTTON_SIZE = (94, 26)
STATUS_H = 50
LAYER_BAR_H = 34
ZOOM_MIN, ZOOM_MAX = 8, 48
MASK_TILE = 160
MASK_IMAGE_W = 480
MASK_IMAGE_H = 300
MAX_BRUSH = 5
NPC_ROW_H = 76
NPC_LIST_W = 420
NPC_ANIM_FPS = 6
NPC_CARD_W = 340
NPC_CARD_H = 340
SECTION_TABS = [
    ("map", "Биомы", 90),
    ("animals", "Животные", 105),
    ("npc", "NPC", 90),
    ("spawn", "Спаун", 90),
    ("equip", "Экипировка", 120),
]
BIOME_TABS = (
    ("forest", "Лесной"),
    ("rocky", "Скалистый"),
    ("winter", "Зимний"),
    ("undead", "Нежить"),
    ("desert", "Пустыня"),
)
EDITOR_LAYER_LABELS = (
    "Вода",
    "Декор воды",
    "Основа суши",
    "Декор суши",
    "Скалы, горы и водопады",
    "Постройки",
    "Декор местности",
    "Животные",
    "Мобы",
)
EDITOR_LAYER_SHORT_LABELS = (
    "Вода",
    "Вода+",
    "Суша",
    "Декор",
    "Скалы",
    "Строй.",
    "Природа",
    "Живот.",
    "Мобы",
)
EDITOR_LAYER_COUNT = len(EDITOR_LAYER_LABELS)
MOB_LAYER_INDEX = EDITOR_LAYER_COUNT - 1
WATERFALL_KEYS = frozenset(
    key for key, spec in rocky_tile_specs().items()
    if spec.get("sheet") == "Waterfalls"
)
WINTER_ANIMATED_WATER_KEYS = frozenset(
    cell["key"]
    for group in winter_animated_groups()
    for cell in group["cells"]
)
WATER_BASE_KEYS = frozenset(
    key
    for key, spec in {
        **rocky_tile_specs(), **winter_tile_specs(), **desert_tile_specs(),
    }.items()
    if (
        (
            spec.get("sheet") == "Water_detilazation"
            and not key.startswith("desert_")
        )
        or (
            key.startswith("desert_")
            and spec.get("sheet") == "Water_coasts"
            and spec.get("layer") == "ground"
        )
    )
    and spec.get("category") == "water"
    and key not in WINTER_ANIMATED_WATER_KEYS
)
WATER_DECOR_KEYS = water_decor_keys()
LAND_DECOR_KEYS = frozenset().union(*(
    palette_role_keys(role)
    for role in ("ground_decor", "grass_decor", "ground_small", "grass_small")
))
LAYER_70_ALPHA = round(255 * 0.7)
NAME_MAX = 64
DOUBLE_CLICK_MS = 400
CRYSTAL_BTN = 20
TOOLS = [("brush", "Кисть", "B"), ("fill", "Заливка", "F"), ("erase", "Ластик", "E"), ("select", "Выделение", "V"), ("stamp", "Вставка", "Ctrl+V")]
TOOL_SCANCODES = {pygame.KSCAN_B: "brush", pygame.KSCAN_F: "fill", pygame.KSCAN_E: "erase", pygame.KSCAN_V: "select"}
TOOL_LABELS = {tool_id: label for tool_id, label, _hotkey in TOOLS}
ERASE_HOVER_COLOR = (255, 110, 110)
TOOL_CURSOR_HOTSPOTS = {"brush": (3, 20), "fill": (12, 20), "erase": (12, 12), "select": (2, 2), "stamp": (12, 12)}
_TOOL_CURSORS = {}
# Ctrl-сочетания по физической клавише: на русской раскладке event.key даёт кириллицу.
CTRL_KEYS = {
    pygame.KSCAN_S: "save", pygame.KSCAN_N: "new",
    pygame.KSCAN_L: "drafts", pygame.KSCAN_Z: "undo", pygame.KSCAN_Y: "redo", pygame.KSCAN_D: "deselect",
    pygame.KSCAN_C: "copy", pygame.KSCAN_X: "cut", pygame.KSCAN_V: "paste",
}


def _ctrl_command(event):
    scancode = getattr(event, "scancode", None)
    if scancode == pygame.KSCAN_Z and event.mod & pygame.KMOD_SHIFT:
        return "redo"
    return CTRL_KEYS.get(scancode)
# Одиночные клавиши по физической позиции (скан-код), чтобы работали и на русской раскладке.
PLAIN_SCANCODES = {
    pygame.KSCAN_G: "grid", pygame.KSCAN_M: "minimap", pygame.KSCAN_DELETE: "delete", pygame.KSCAN_X: "mask",
    pygame.KSCAN_N: "npc",
}
BRUSH_SIZE_SCANCODES = {pygame.KSCAN_LEFTBRACKET: -1, pygame.KSCAN_RIGHTBRACKET: 1}
PLAIN_KEYS = {pygame.K_F2: "rename"}
PAN_KEYS = {
    pygame.K_LEFT: (-4, 0), pygame.K_a: (-4, 0),
    pygame.K_RIGHT: (4, 0), pygame.K_d: (4, 0),
    pygame.K_UP: (0, -4), pygame.K_w: (0, -4),
    pygame.K_DOWN: (0, 4), pygame.K_s: (0, 4),
}
ZOOM_KEYS = {pygame.K_EQUALS: 4, pygame.K_PLUS: 4, pygame.K_KP_PLUS: 4, pygame.K_MINUS: -4, pygame.K_KP_MINUS: -4}
COMMANDS_WITHOUT_MAP = ("new", "drafts", "tower", "exit")
WELCOME_BUTTONS = (
    ("new", "Новая карта  (Ctrl+N)"),
    ("drafts", "Загрузить черновик  (Ctrl+L)"),
    ("tower", "Карта башни с сервера"),
)

BG = (24, 26, 30)
PANEL_BG = (34, 37, 43)
BORDER = (70, 74, 82)
TEXT = (235, 235, 235)
TEXT_DIM = (160, 166, 176)
BLOCKED_TEXT = (235, 120, 110)
GREEN = (120, 220, 140)
RED = (240, 110, 100)
AMBER = (240, 190, 90)
HOVER_COLOR = (255, 220, 90)
# Клетка без земли: чёрная, чтобы сразу было видно, что её ещё не редактировали.
EMPTY_CELL = (0, 0, 0)
SELECT_COLOR = (120, 200, 255)


# Деревья лежат листами кадров; в палитре под курсором они идут с той же скоростью, что в игре
TREE_ANIMATIONS = {
    name: {
        "frame": frame_size,
        "frames": MAP_TREE_FRAMES,
        "cols": MAP_TREE_COLUMNS.get(name, MAP_TREE_FRAMES_PER_ROW),
        "ms": MAP_TREE_FRAME_MS,
    }
    for name, frame_size in MAP_TREE_SHEETS.items()
}
ANIMAL_ANIMATIONS = {
    f"animal_{name}": {
        "frame": (frame_size, frame_size),
        "frames": frame_count,
        "cols": columns,
        "ms": MAP_TREE_FRAME_MS,
    }
    for name, (frame_size, columns, frame_count) in ANIMAL_SHEETS.items()
}
WATERFOWL_ANIMATIONS = {
    f"animal_{name}_water": {
        "frame": (32, 32),
        "frames": WATERFOWL_SHEETS[f"{name}_water"][2],
        "cols": WATERFOWL_SHEETS[f"{name}_water"][1],
        "ms": MAP_TREE_FRAME_MS,
    }
    for name in ("duck", "drake", "duckling")
}
ROCKY_ANIMATIONS = {
    key: {
        "frame": tuple(animation["frame"]),
        "frames": animation["frames"],
        "cols": animation["cols"],
        "durations": animation["durations"],
        "tile_ids": animation["tile_ids"],
    }
    for key, animation in rocky_animations().items()
}
ROCKY_TILE_SPECS = rocky_tile_specs()
WINTER_TILE_SPECS = winter_tile_specs()
UNDEAD_TILE_SPECS = undead_tile_specs()
DESERT_TILE_SPECS = desert_tile_specs()
GRASSLAND_TILE_SPECS = grassland_tile_specs()
BIOME_TILE_SPECS = {
    **ROCKY_TILE_SPECS, **WINTER_TILE_SPECS, **UNDEAD_TILE_SPECS,
    **DESERT_TILE_SPECS, **GRASSLAND_TILE_SPECS,
}
WINTER_ANIMATIONS = {
    key: {
        "frame": tuple(animation["frame"]),
        "frames": animation["frames"],
        "cols": animation["cols"],
        "durations": animation["durations"],
        "tile_ids": animation["tile_ids"],
    }
    for key, animation in winter_animations().items()
}
UNDEAD_ANIMATIONS = {
    key: {
        "frame": tuple(animation["frame"]),
        "frames": animation["frames"],
        "cols": animation["cols"],
        "durations": animation["durations"],
        **({"tile_ids": animation["tile_ids"]} if "tile_ids" in animation else {}),
    }
    for key, animation in undead_animations().items()
}
DESERT_ANIMATIONS = {
    key: {
        "frame": tuple(animation["frame"]),
        "frames": animation["frames"],
        "cols": animation["cols"],
        "durations": animation["durations"],
        "tile_ids": animation["tile_ids"],
    }
    for key, animation in desert_animations().items()
}
GRASSLAND_ANIMATIONS = {
    key: {
        "frame": tuple(animation["frame"]),
        "frames": animation["frames"],
        "cols": animation["cols"],
        "durations": animation["durations"],
        "tile_ids": animation["tile_ids"],
    }
    for key, animation in grassland_animations().items()
}
PALETTE_ANIMATIONS = {
    **TREE_ANIMATIONS, **ANIMAL_ANIMATIONS, **WATERFOWL_ANIMATIONS,
    **ROCKY_ANIMATIONS, **WINTER_ANIMATIONS, **UNDEAD_ANIMATIONS,
    **DESERT_ANIMATIONS, **GRASSLAND_ANIMATIONS,
}


def _scale_rgba(surface, size):
    """Масштабирует спрайт с альфой без тёмной каймы: цвет умножается на альфу до сглаживания."""
    width, height = surface.get_size()
    raw = bytearray(pygame.image.tobytes(surface, "RGBA"))
    for i in range(0, len(raw), 4):
        a = raw[i + 3]
        if a != 255:
            raw[i] = raw[i] * a // 255
            raw[i + 1] = raw[i + 1] * a // 255
            raw[i + 2] = raw[i + 2] * a // 255
    premul = pygame.image.frombytes(bytes(raw), (width, height), "RGBA")
    scaled = pygame.transform.smoothscale(premul, size)
    raw = bytearray(pygame.image.tobytes(scaled, "RGBA"))
    for i in range(0, len(raw), 4):
        a = raw[i + 3]
        if 0 < a < 255:
            raw[i] = min(255, raw[i] * 255 // a)
            raw[i + 1] = min(255, raw[i + 1] * 255 // a)
            raw[i + 2] = min(255, raw[i + 2] * 255 // a)
    return pygame.image.frombytes(bytes(raw), size, "RGBA")


def _draw_tool_icon(surface, kind):
    outline = (20, 20, 20)
    if kind == "brush":
        pygame.draw.line(surface, outline, (3, 20), (18, 5), 5)
        pygame.draw.line(surface, (240, 190, 60), (3, 20), (18, 5), 3)
    elif kind == "fill":
        pygame.draw.polygon(surface, outline, [(3, 12), (11, 4), (19, 12), (11, 20)])
        pygame.draw.polygon(surface, (120, 170, 255), [(5, 12), (11, 6), (17, 12), (11, 18)])
        pygame.draw.circle(surface, (120, 170, 255), (20, 19), 3)
    elif kind == "erase":
        pygame.draw.rect(surface, outline, (3, 7, 18, 11), border_radius=2)
        pygame.draw.rect(surface, (255, 140, 170), (4, 8, 16, 9), border_radius=2)
        pygame.draw.rect(surface, (120, 170, 255), (4, 8, 6, 9))
    elif kind == "select":
        pygame.draw.rect(surface, outline, (1, 1, 13, 13), 1)
        pygame.draw.rect(surface, outline, (7, 7, 16, 16))
        pygame.draw.rect(surface, (255, 220, 80), (8, 8, 14, 14))
    elif kind == "stamp":
        pygame.draw.rect(surface, outline, (2, 2, 20, 20))
        pygame.draw.rect(surface, (90, 200, 120), (3, 3, 18, 18))
        pygame.draw.line(surface, (255, 255, 255), (12, 6), (12, 18), 2)
        pygame.draw.line(surface, (255, 255, 255), (6, 12), (18, 12), 2)


def _cursor_for(kind):
    if kind == "arrow":
        return pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_ARROW)
    if kind not in _TOOL_CURSORS:
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        _draw_tool_icon(surface, kind)
        _TOOL_CURSORS[kind] = pygame.cursors.Cursor(TOOL_CURSOR_HOTSPOTS[kind], surface)
    return _TOOL_CURSORS[kind]


class MapEditorScene:
    def __init__(self, client, catalog, ensure_login):
        self.client = client
        self.ensure_login = ensure_login
        self.catalog = sorted(catalog, key=lambda item: item["sort_order"])
        self.font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.small = pygame.font.SysFont(settings.FONT_NAME, 13)
        self.title = pygame.font.SysFont(settings.FONT_NAME, 18, bold=True)
        self.menu = MenuBar(self.font, self.small)
        self.toolbar = ToolBar(self.font)
        self.minimap = Minimap()
        self.commands = {
            "new": self.new_map,
            "tower": self.open_tower_map,
            "save": self.save,
            "drafts": self.open_draft_list,
            "publish": self.publish,
            "server_save": self.save_to_server,
            "exit": self._request_close,
            "undo": self.undo,
            "redo": self.redo,
            "delete": self.delete_selection,
            "deselect": self.deselect,
            "copy": self.copy_selection,
            "cut": self.cut_selection,
            "paste": self.paste_stamp,
            "grid": self.toggle_grid,
            "minimap": self.toggle_minimap,
            "rename": self.open_rename,
            "mask": self.open_mask_dialog,
            "harvest": self.toggle_harvest,
            "npc": self.toggle_npc_section,
            "zoom_in": lambda: self._set_zoom(self.zoom + 4),
            "zoom_out": lambda: self._set_zoom(self.zoom - 4),
        }
        self.state = MapEditorState(self.catalog, [], DEFAULT_MAP_SIZE, DEFAULT_MAP_SIZE)
        self._reset_editor_layers()
        self.has_map = False
        self.draft_id = None
        self.selected = self.catalog[0]["item_key"] if self.catalog else None
        self.selected_layer = None
        self.active_map_layer = 0
        self.editor_layer_visible = [True] * EDITOR_LAYER_COUNT
        self.editor_layer_70 = [False] * EDITOR_LAYER_COUNT
        self.tool = "brush"
        self.brush_size = 1
        self.cursor_kind = None
        self.show_grid = True
        self.show_minimap = True
        self.name_dirty = False
        self.zoom = 16
        self.origin_x = 0
        self.origin_y = 0
        self.list_scroll = 0
        self.hover = None
        self.drag = None
        self.stamp = None
        self.ghosts = {}
        self.exit_dialog = None
        self.exit_after_save = False
        self.pending_action = None
        self.prompt = None
        self.draft_list = None
        self.save_dialog = None
        self.size_picker = None
        self.world_picker = None
        self.mask_dialog = None
        self.partial_masks = load_partial_masks()
        self.natives = {}
        self.asset_sheets = {}
        self.scaled = {}
        self.layer_scaled = {}
        self.thumbs = {}
        self.biome_catalogs = {
            "forest": [
                item for item in self.catalog
                if not item["item_key"].startswith(("rocky_", "winter_", "undead_", "desert_"))
                and item["category"] != "animal"
            ],
            "rocky": [
                item for item in self.catalog
                if item["item_key"].startswith("rocky_") and item["category"] != "animal"
            ],
            "winter": [
                item for item in self.catalog
                if item["item_key"].startswith("winter_") and item["category"] != "animal"
            ],
            "undead": [
                item for item in self.catalog
                if item["item_key"].startswith("undead_") and item["category"] != "animal"
            ],
            "desert": [
                item for item in self.catalog
                if item["item_key"].startswith("desert_") and item["category"] != "animal"
            ],
        }
        self.animal_catalog = [item for item in self.catalog if item["category"] == "animal"]
        self.biome = "forest"
        self.palette_editing = False
        self.palette_overrides = {}
        self.palette_original_overrides = {}
        self.palette_version = 0
        self.palette_context = None
        self.palette_selected_keys = set()
        self.palette_credentials = None
        self.palette_conflicts = None
        self.palette_resolutions = {}
        self.palette_submit_credentials = None
        self.biome_palettes = {}
        self.palette = self._build_biome_palette(self.biome)
        self.biome_palettes[self.biome] = self.palette
        self.animal_palette = self._build_animal_palette()
        self.palette_default_groups = {}
        self.palette_default_orders = {}
        self._record_palette_defaults(self.palette)
        self._record_palette_defaults(self.animal_palette)
        self.npc_list = npc_catalog()
        self.equipment_palette = None  # строится при первом открытии вкладки «Экипировка»
        self.equipment_selected = None
        self.section = "map"
        self.selected_npc = None
        self.npc_sheets = {}
        self.npc_scaled = {}
        self.toast = None  # (текст, цвет, момент, когда скрыть) — заметное сообщение посреди редактора
        self.server_map = None  # id мира на сервере, созданного из этой карты
        self.mode = DEFAULT_MODE
        self.npc_card = None
        self.mob_dialog = None
        self.mob_dialog_kind = None
        self.item_dialog = None
        self.crystal_dialog = None
        self.last_catalog_click = None
        self.mob_settings_cache = {}
        self.status = "Создайте новую карту или загрузите черновик"
        self.status_color = TEXT_DIM

    @property
    def panel_w(self):
        return self.palette.panel_width()

    @property
    def scroll_x(self):
        return self.panel_w - SCROLL_GAP

    def grid_rect(self):
        return pygame.Rect(
            self.panel_w, TOP + LAYER_BAR_H, settings.WIDTH - self.panel_w,
            settings.HEIGHT - STATUS_H - TOP - LAYER_BAR_H,
        )

    def layer_bar_rect(self):
        return pygame.Rect(self.panel_w, TOP, settings.WIDTH - self.panel_w, LAYER_BAR_H)

    def _layer_tab_rects(self):
        bar = self.layer_bar_rect()
        control_width = 180
        available = max(0, bar.w - control_width - 12)
        tab_width = available // EDITOR_LAYER_COUNT
        tabs = [
            (index, pygame.Rect(bar.x + 4 + index * tab_width, bar.y + 4, max(1, tab_width - 3), bar.h - 8))
            for index in range(EDITOR_LAYER_COUNT)
        ]
        controls_x = bar.x + 4 + tab_width * EDITOR_LAYER_COUNT
        hide = pygame.Rect(controls_x + 4, bar.y + 4, 82, bar.h - 8)
        opacity = pygame.Rect(hide.right + 4, bar.y + 4, 74, bar.h - 8)
        return tabs, hide, opacity

    def _draw_layer_tabs(self, screen):
        bar = self.layer_bar_rect()
        screen.fill((30, 33, 39), bar)
        mouse = pygame.mouse.get_pos()
        tabs, hide, opacity = self._layer_tab_rects()
        for index, rect in tabs:
            active = index == self.active_map_layer
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(
                screen,
                (70, 98, 136) if active else ((56, 61, 70) if hovered else (43, 47, 54)),
                rect,
                border_radius=4,
            )
            pygame.draw.rect(screen, BORDER, rect, 1, border_radius=4)
            label = f"{index + 1} {EDITOR_LAYER_SHORT_LABELS[index]}"
            while self.small.size(label)[0] > rect.w - 6 and len(label) > 3:
                label = label[:-2] + "."
            text = self.small.render(label, True, TEXT if active else TEXT_DIM)
            screen.blit(text, text.get_rect(center=rect.center))
        for rect, label, active in (
            (hide, "Показать" if not self.editor_layer_visible[self.active_map_layer] else "Скрыть",
             not self.editor_layer_visible[self.active_map_layer]),
            (opacity, "70%" if self.editor_layer_70[self.active_map_layer] else "100%",
             self.editor_layer_70[self.active_map_layer]),
        ):
            pygame.draw.rect(screen, (70, 98, 136) if active else (43, 47, 54), rect, border_radius=4)
            pygame.draw.rect(screen, BORDER, rect, 1, border_radius=4)
            text = self.small.render(label, True, TEXT if active else TEXT_DIM)
            screen.blit(text, text.get_rect(center=rect.center))

    def _layer_tab_click(self, pos):
        tabs, hide, opacity = self._layer_tab_rects()
        for index, rect in tabs:
            if rect.collidepoint(pos):
                self.active_map_layer = index
                message = (
                    f"Активен слой {index + 1} «{EDITOR_LAYER_LABELS[index]}»; "
                    "изменения всех слоёв сохраняются в черновике"
                )
                self._set_status(message, TEXT_DIM)
                return True
        if hide.collidepoint(pos):
            self.editor_layer_visible[self.active_map_layer] = not self.editor_layer_visible[self.active_map_layer]
            state = "скрыт" if not self.editor_layer_visible[self.active_map_layer] else "показан"
            self._set_status(
                f"Слой {self.active_map_layer + 1} «{EDITOR_LAYER_LABELS[self.active_map_layer]}» {state}",
                TEXT_DIM,
            )
            return True
        if opacity.collidepoint(pos):
            self.editor_layer_70[self.active_map_layer] = not self.editor_layer_70[self.active_map_layer]
            percent = 70 if self.editor_layer_70[self.active_map_layer] else 100
            self._set_status(
                f"Непрозрачность слоя {self.active_map_layer + 1} "
                f"«{EDITOR_LAYER_LABELS[self.active_map_layer]}»: {percent}%",
                TEXT_DIM,
            )
            return True
        return False

    def _layer_alpha(self, index):
        if not self.editor_layer_visible[index]:
            return 0
        return LAYER_70_ALPHA if self.editor_layer_70[index] else 255

    def _reset_editor_layers(self):
        self.editor_layers = [self.state] + [
            MapEditorState(self.catalog, [], self.state.map_w, self.state.map_h)
            for _ in range(EDITOR_LAYER_COUNT - 1)
        ]
        self.state.replace_other_layers = True
        for layer in self.editor_layers[1:]:
            layer.allow_cross_layer_placements = True
            layer.replace_other_layers = True
        self.active_map_layer = 0

    def _restore_editor_layers(self, saved_layers, mark_saved=True):
        if not isinstance(saved_layers, list):
            raise ValueError("список слоёв должен быть массивом")
        source_layers = [self.state]
        for index, cells in enumerate(saved_layers, start=1):
            if not isinstance(cells, list):
                raise ValueError(f"Данные дополнительного слоя {index + 1} в черновике повреждены")
            source_layers.append(MapEditorState(self.catalog, cells, self.state.map_w, self.state.map_h))
        restored = [
            MapEditorState(self.catalog, [], self.state.map_w, self.state.map_h)
            for _ in range(EDITOR_LAYER_COUNT)
        ]
        for layer in restored:
            layer.allow_cross_layer_placements = True
            layer.replace_other_layers = True
        for source in source_layers:
            for cell in source.to_cells():
                target_index = self._artist_layer_for_item(cell["key"], cell["layer"])
                storage_layer = self._artist_storage_layer(cell["key"], cell["layer"])
                error = restored[target_index].place(
                    cell["key"], cell["x"], cell["y"], layer=storage_layer,
                )
                if error:
                    raise ValueError(f"Не удалось перенести клетку на слой {target_index + 1}: {error}")
        if mark_saved:
            for layer in restored:
                layer.mark_saved()
        self.state = restored[0]
        self.editor_layers = restored
        self.active_map_layer = 0

    def _artist_layer_for_item(self, key, storage_layer=None, include_overrides=True):
        item = self.state.items.get(key)
        if item is None:
            raise ValueError("Элемента нет в каталоге")
        if include_overrides:
            override = self.palette_overrides.get(key, {}).get("editor_layer")
            if override is not None:
                return override - 1
        if key in WATERFALL_KEYS:
            return 4
        if key in WATER_BASE_KEYS:
            return 0
        if key in WATER_DECOR_KEYS:
            return 1
        if item["category"] == "water" and storage_layer == "overlay":
            return 1
        if item["kind"] == "object":
            if item["category"] == "animal":
                return 7
            if item["category"] in ("building", "bridge", "house", "structure"):
                return 5
            return 6
        if key in LAND_DECOR_KEYS:
            return 3
        if item.get("editor_layer") is not None:
            return int(item["editor_layer"]) - 1
        if storage_layer is None:
            if item["category"] == "road":
                storage_layer = "ground"
            elif key in self.state.infra_keys:
                storage_layer = "infra"
            elif key in self.state.overlay_keys:
                storage_layer = "overlay"
            else:
                storage_layer = terrain_layer_for_key(key) or "ground"
        if storage_layer in ("elevation", "relief"):
            return 4
        if storage_layer == "infra":
            return 5
        if storage_layer == "overlay":
            return 1 if item["category"] == "water" else 3
        if item["category"] == "water":
            return 0
        return 2

    def _artist_storage_layer(self, key, storage_layer):
        item = self.state.items.get(key)
        override = self.palette_overrides.get(key, {}).get("editor_layer")
        if override is not None:
            if item is None:
                raise ValueError("Элемента нет в каталоге")
            if item["kind"] == "object":
                return "object"
            return {
                1: "ground",
                2: "overlay",
                3: "ground",
                4: "overlay",
                5: "elevation",
                6: "infra",
            }.get(override, storage_layer)
        spec = BIOME_TILE_SPECS.get(key)
        if (
            spec is not None
            and spec.get("sheet") == "Ground_moss"
            and spec.get("tile_id") in ROCKY_GROUND_MOSS_GRASS_TILE_IDS
        ):
            return "ground"
        return storage_layer

    def _artist_layer_error(self, key, storage_layer=None):
        try:
            required_index = self._artist_layer_for_item(key, storage_layer)
        except ValueError as error:
            return str(error)
        if required_index == self.active_map_layer:
            return None
        return (
            f"Элемент относится к слою {required_index + 1} "
            f"«{EDITOR_LAYER_LABELS[required_index]}», а сейчас выбран слой "
            f"{self.active_map_layer + 1} «{EDITOR_LAYER_LABELS[self.active_map_layer]}»"
        )

    def _stamp_artist_layer_error(self, stamp):
        for storage_layer in ("ground", "overlay", "elevation", "relief", "infra", "objects"):
            for entry in stamp.get(storage_layer, ()):
                error = self._artist_layer_error(
                    entry[2],
                    None if storage_layer == "objects" else storage_layer,
                )
                if error:
                    return error
        return None

    def _active_editor_state(self):
        self.editor_layers[0] = self.state
        return self.editor_layers[self.active_map_layer]

    def _game_cells(self):
        """Flatten editor-only paint layers into the game's existing map-cell format."""
        self.editor_layers[0] = self.state
        combined = MapEditorState(self.catalog, [], self.state.map_w, self.state.map_h)
        for state in self.editor_layers:
            for cell in state.to_cells():
                error = combined.place(cell["key"], cell["x"], cell["y"], layer=cell["layer"])
                if error:
                    raise ValueError(f"Слой карты содержит несовместимый элемент: {error}")
        return combined.to_cells()

    def panel_rect(self):
        return pygame.Rect(0, TOP, self.panel_w, settings.HEIGHT - STATUS_H - TOP)

    def handle_event(self, event):
        """Возвращает True, когда редактор нужно закрыть."""
        if self.exit_dialog is not None:
            return self._exit_dialog_event(event)
        if event.type == pygame.QUIT:
            return self._request_close()
        if self.palette_credentials is not None:
            self._palette_credentials_event(event)
            return False
        if self.palette_conflicts is not None:
            self._palette_conflicts_event(event)
            return False
        if self.palette_context is not None:
            self._palette_context_event(event)
            return False
        if self.prompt is not None:
            if event.type == pygame.KEYDOWN:
                self._prompt_key(event)
            return False
        if self.save_dialog is not None:
            return self._save_dialog_event(event)
        if self.draft_list is not None:
            self._draft_list_event(event)
            return False
        if self.size_picker is not None:
            self._size_picker_event(event)
            return False
        if self.world_picker is not None:
            self._world_picker_event(event)
            return False
        if self.mob_dialog is not None:
            self._mob_dialog_event(event)
            return False
        if self.crystal_dialog is not None:
            self._crystal_dialog_event(event)
            return False
        if self.item_dialog is not None:
            self._item_dialog_event(event)
            return False
        if self.mask_dialog is not None:
            self._mask_dialog_event(event)
            return False
        if not self.has_map:
            return self._welcome_event(event)
        if event.type == pygame.KEYDOWN:
            return self._key(event)
        if event.type == pygame.MOUSEWHEEL:
            self._wheel(event.y, bool(pygame.key.get_mods() & pygame.KMOD_CTRL))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            return self._mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_up(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_move(event)
        return False

    def draw(self, screen):
        screen.fill(BG)
        self._sync_cursor()
        if self.has_map:
            self._draw_grid(screen)
            self._draw_panel(screen)
        else:
            self._draw_welcome(screen)
        self._draw_status(screen)
        if self.has_map:
            self._draw_layer_tabs(screen)
            self._draw_npc_card(screen)
            self.toolbar.draw(screen, TOOLS, self.tool, self._toolbar_text(), server=self._server_button())
        self.menu.draw(screen, self._menus())
        if self.prompt is not None:
            self.prompt.draw(screen)
        if self.draft_list is not None:
            self.draft_list.draw(screen)
        if self.save_dialog is not None:
            self.save_dialog.draw(screen)
        if self.size_picker is not None:
            self.size_picker.draw(screen)
        if self.world_picker is not None:
            self.world_picker.draw(screen)
        if self.mask_dialog is not None:
            self.mask_dialog.draw(screen)
        if self.mob_dialog is not None:
            self.mob_dialog.draw(screen)
        if self.crystal_dialog is not None:
            self.crystal_dialog.draw(screen)
        if self.item_dialog is not None:
            self.item_dialog.draw(screen)
        if self.palette_context is not None:
            self._draw_palette_context(screen)
        if self.palette_credentials is not None:
            self.palette_credentials.draw(screen)
        if self.palette_conflicts is not None:
            self.palette_conflicts.draw(screen)
        self._draw_toast(screen)
        if self.exit_dialog is not None:
            self.exit_dialog.draw(screen)

    def _welcome_area(self):
        return pygame.Rect(0, TOP, settings.WIDTH, settings.HEIGHT - STATUS_H - TOP)

    def _welcome_buttons(self):
        area = self._welcome_area()
        width, height, gap = 360, 44, 14
        top = area.centery - 40
        return [
            (command, label, pygame.Rect(area.centerx - width // 2, top + index * (height + gap), width, height))
            for index, (command, label) in enumerate(WELCOME_BUTTONS)
        ]

    def _draw_welcome(self, screen):
        area = self._welcome_area()
        screen.fill(PANEL_BG, area)
        title = self.title.render("Карта не открыта", True, TEXT)
        hint = self.font.render("Создайте новую карту или загрузите черновик: рисовать можно только после этого", True, TEXT_DIM)
        screen.blit(title, title.get_rect(center=(area.centerx, area.centery - 110)))
        screen.blit(hint, hint.get_rect(center=(area.centerx, area.centery - 70)))
        mouse = pygame.mouse.get_pos()
        for _command, label, rect in self._welcome_buttons():
            fill = (78, 86, 100) if rect.collidepoint(mouse) else (58, 64, 74)
            pygame.draw.rect(screen, fill, rect, border_radius=6)
            pygame.draw.rect(screen, BORDER, rect, 1, border_radius=6)
            text = self.font.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))

    def _welcome_event(self, event):
        """Пока карта не открыта, работают только меню, кнопки и команды открытия или выхода."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.menu.is_open():
                    self.menu.close()
                    return False
                return self._command("exit")
            if event.mod & pygame.KMOD_CTRL:
                command = _ctrl_command(event)
                if command in COMMANDS_WITHOUT_MAP:
                    return self._command(command)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 or self.menu.is_open():
                consumed, command = self.menu.click(event.pos, self._menus())
                if consumed:
                    return self._command(command) if command else False
            if event.button == 1:
                for command, _label, rect in self._welcome_buttons():
                    if rect.collidepoint(event.pos):
                        return self._command(command)
        return False

    def _dirty(self):
        self.editor_layers[0] = self.state
        return any(layer.dirty for layer in self.editor_layers) or self.name_dirty

    def _notify(self, text, color):
        """Результат действия: строка состояния и заметное сообщение посреди редактора на несколько секунд."""
        self._set_status(text, color)
        self.toast = (text, color, pygame.time.get_ticks() + 4000)

    def _draw_toast(self, screen):
        if self.toast is None:
            return
        text, color, until = self.toast
        if pygame.time.get_ticks() > until:
            self.toast = None
            return
        label = self.font.render(text, True, color)
        grid = self.grid_rect()
        box = pygame.Rect(0, 0, label.get_width() + 40, 44)
        box.midtop = (grid.centerx, grid.y + 12)
        pygame.draw.rect(screen, (28, 32, 42), box, border_radius=8)
        pygame.draw.rect(screen, color, box, 2, border_radius=8)
        screen.blit(label, label.get_rect(center=box.center))

    def _set_status(self, text, color):
        self.status = text
        self.status_color = color

    def _toolbar_text(self):
        name = self.state.name or "без названия"
        return f"Размер кисти: {self.brush_size} ([ ])  ·  Карта: {name}  ·  Режим: {mode_name(self.mode)}"

    def _confirmed(self, action, question):
        """Опасные команды выполняются со второго нажатия."""
        if self.pending_action == action:
            self.pending_action = None
            return True
        self.pending_action = action
        self._set_status(question, AMBER)
        return False

    def _command(self, command):
        """Выполняет команду. Возвращает True только для выхода из редактора."""
        if not self.has_map and command not in COMMANDS_WITHOUT_MAP:
            return False
        if command != self.pending_action:
            self.pending_action = None
        result = self.commands[command]()
        return bool(result) if command == "exit" else False

    def _menus(self):
        menus = self._build_menus()
        if not self.has_map:
            for _title, items in menus:
                for item in items:
                    if not item.get("separator") and item["id"] not in COMMANDS_WITHOUT_MAP:
                        item["enabled"] = False
        return menus

    def _build_menus(self):
        state = self._active_editor_state()
        return [
            ("Файл", [
                {"id": "new", "label": "Новая карта", "hotkey": "Ctrl+N"},
                {"id": "tower", "label": "Открыть карту башни (с сервера)"},
                {"separator": True},
                {"id": "save", "label": "Сохранить черновик", "hotkey": "Ctrl+S"},
                {"id": "drafts", "label": "Загрузить черновик", "hotkey": "Ctrl+L"},
                {
                    "id": "server_save",
                    "label": self._server_label(),
                    "enabled": self.draft_id is not None and not self._dirty(),
                },
                {"separator": True},
                {"id": "exit", "label": "Выход", "hotkey": "Esc"},
            ]),
            ("Правка", [
                {"id": "undo", "label": "Отменить", "hotkey": "Ctrl+Z", "enabled": bool(state.undo_stack)},
                {"id": "redo", "label": "Повторить", "hotkey": "Ctrl+Y", "enabled": bool(state.redo_stack)},
                {"separator": True},
                {"id": "copy", "label": "Копировать", "hotkey": "Ctrl+C", "enabled": state.selection is not None},
                {"id": "cut", "label": "Вырезать", "hotkey": "Ctrl+X", "enabled": state.selection is not None},
                {"id": "paste", "label": "Вставить", "hotkey": "Ctrl+V", "enabled": self.stamp is not None},
                {"separator": True},
                {"id": "delete", "label": "Удалить выделение", "hotkey": "Del", "enabled": state.selection is not None},
                {"id": "deselect", "label": "Снять выделение", "hotkey": "Ctrl+D", "enabled": state.selection is not None},
            ]),
            ("Вид", [
                {"id": "grid", "label": "Сетка", "hotkey": "G", "checked": self.show_grid},
                {"id": "minimap", "label": "Миникарта", "hotkey": "M", "checked": self.show_minimap},
                {"id": "npc", "label": "Раздел NPC", "hotkey": "N", "checked": self.section == "npc"},
                {"separator": True},
                {"id": "zoom_in", "label": "Приблизить", "hotkey": "+"},
                {"id": "zoom_out", "label": "Отдалить", "hotkey": "-"},
            ]),
            ("Карта", [
                {"id": "rename", "label": "Название...", "hotkey": "F2"},
                {"id": "mask", "label": "Маска проходимости...", "hotkey": "X", "enabled": self.selected is not None},
                {"id": "harvest", "label": "Добыча кристаллов", "checked": self.state.harvest_enabled},
                {"id": "size", "label": f"Размер {state.map_w}×{state.map_h} (задаётся при создании карты)", "enabled": False},
            ]),
        ]

    def new_map(self):
        if (
            self.state.ground or self.state.overlay or self.state.elevation or self.state.relief
            or self.state.infra or self.state.objects or self.name_dirty
        ) and not self._confirmed(
            "new", "Очистить карту? Нажмите ещё раз, чтобы стереть всё на карте (сохранённые черновики не меняются)"
        ):
            return
        self.size_picker = SizePicker(self.font, self.small, modes=GAME_MODES, mode=self.mode)
        self._set_status("Выберите режим, ширину и высоту новой карты", TEXT_DIM)

    def _size_picker_event(self, event):
        result = self.size_picker.handle_event(event)
        if result is None:
            return
        self.size_picker = None
        if result == "cancel":
            self._set_status("Создание карты отменено", TEXT_DIM)
            return
        map_w, map_h, self.mode = result
        self.state = MapEditorState(self.catalog, [], map_w, map_h)
        self._reset_editor_layers()
        self.active_map_layer = 0
        self.has_map = True
        self.mob_settings_cache = {}
        self._detach_draft()
        self.minimap = Minimap()
        self.drag = None
        if self.mode == "economy":
            mode_note = "Заглушка: цель режима — прокачка замка."
        elif self.mode == "deck":
            mode_note = "Карту этого режима строит оператор 2."
        else:
            mode_note = ""
        note = f" {mode_note}" if mode_note else ""
        self._set_status(
            f"Новая карта {map_w}×{map_h}, режим «{mode_name(self.mode)}».{note} "
            "Сохраните черновик (Ctrl+S), чтобы задать название",
            TEXT_DIM,
        )

    def open_tower_map(self):
        """Заполняет черновик тайлами башни. Тайлы берутся с сервера, поэтому нужен вход. Сохраняется только по Ctrl+S."""
        if self._dirty() and not self._confirmed(
            "tower", "Несохранённые изменения будут потеряны. Нажмите ещё раз, чтобы заполнить карту картой башни"
        ):
            return
        if not self.ensure_login():
            self._set_status("Для карты башни нужен вход на сервер", RED)
            return
        try:
            terrain = self.client.get_map_terrain()
        except ServerError as error:
            self._set_status(f"Не загружено: {error}", RED)
            return
        if not terrain.get("map", {}).get("uniform_grass"):
            self._set_status("Сервер отдаёт не карту башни: запустите его с WORLD_ID=2", RED)
            return
        cells = build_tower_seed_cells(terrain, self.state.items, self.state.map_w, self.state.map_h)
        if not self.has_map:
            self.state = MapEditorState(self.catalog, [], self.state.map_w, self.state.map_h)
            self._reset_editor_layers()
        self._detach_draft()
        self.mode = DEFAULT_MODE
        self.state.replace_cells(cells)
        self._restore_editor_layers([], mark_saved=False)
        self.has_map = True
        self.minimap = Minimap()
        self.drag = None
        self._set_status(f"Карта башни в черновике, клеток: {len(cells)}. Сохраните черновик (Ctrl+S)", GREEN)

    def _detach_draft(self):
        """Новая карта или карта башни не относятся к сохранённому черновику: следующее сохранение спросит название."""
        self.state.name = ""
        self.name_dirty = False
        self.draft_id = None
        self.server_map = None

    def save(self):
        """Открывает окно сохранения: название, существующие черновики и подтверждение перезаписи."""
        self.save_dialog = SaveDialog(self.font, self.small, map_drafts.list_drafts(), self.state.name, NAME_MAX)
        pygame.key.start_text_input()
        self._set_status("Введите название или выберите черновик из списка", TEXT_DIM)
        return False

    def _save_dialog_event(self, event):
        """Возвращает True, когда после сохранения нужно закрыть редактор (выбрано «Сохранить и выйти»)."""
        result = self.save_dialog.handle_event(event)
        if result is None:
            return False
        if result == "cancel":
            self._close_save_dialog()
            if self.exit_after_save:
                self.exit_after_save = False
                self.exit_dialog = ExitDialog(self.font, self.small)
            else:
                self._set_status("Сохранение отменено", TEXT_DIM)
            return False
        _, name, draft_id = result
        error = self._write_draft(name, draft_id)
        if error is not None:
            self.save_dialog.message = error
            return False
        self._close_save_dialog()
        exit_now = self.exit_after_save
        self.exit_after_save = False
        return exit_now

    def _close_save_dialog(self):
        self.save_dialog = None
        pygame.key.stop_text_input()

    def _write_draft(self, name, draft_id):
        """Сохраняет карту в локальный черновик. Возвращает текст ошибки или None при успехе."""
        self.editor_layers[0] = self.state
        try:
            saved = map_drafts.save_draft(
                name, self.state.to_cells(), self.state.map_w, self.state.map_h, draft_id,
                mode=self.mode, mobs=self.state.to_mobs(), spawns=self.state.to_spawns(),
                crystals=self.state.to_crystals(), harvest_enabled=self.state.harvest_enabled,
                editor_layers=[layer.to_cells() for layer in self.editor_layers[1:]],
            )
        except map_drafts.DraftError as error:
            return str(error)
        self.state.name = saved["name"]
        self.draft_id = saved["id"]
        self.server_map = (saved.get("server_map") or {}).get("saved_id")
        for layer in self.editor_layers:
            layer.mark_saved()
        self.name_dirty = False
        self._set_status(f"Черновик «{saved['name']}» сохранён, клеток: {len(saved['cells'])}", GREEN)
        return None

    def open_draft_list(self):
        if self._dirty() and not self._confirmed(
            "drafts", "Несохранённые изменения будут потеряны. Нажмите ещё раз, чтобы открыть список черновиков"
        ):
            return
        self.draft_list = DraftList(self.font, self.small, map_drafts.list_drafts())
        self._set_status("Выберите черновик из списка", TEXT_DIM)

    def _open_draft(self, draft_id):
        try:
            draft = map_drafts.load_draft(draft_id)
        except map_drafts.DraftError as error:
            self._set_status(f"Не открыто: {error}", RED)
            return
        previous_state = self.state
        previous_layers = self.editor_layers
        previous_active_layer = self.active_map_layer
        self.state = MapEditorState(self.catalog, draft["cells"], draft["map_w"], draft["map_h"])
        try:
            self._restore_editor_layers(draft.get("editor_layers", []))
        except (KeyError, TypeError, ValueError) as error:
            self.state = previous_state
            self.editor_layers = previous_layers
            self.active_map_layer = previous_active_layer
            self._set_status(f"Черновик не открыт: данные слоёв повреждены ({error})", RED)
            return
        self.state.name = draft["name"]
        self.state.load_mobs(draft.get("mobs", []))
        self.state.load_spawns(draft.get("spawns", []))
        self.state.load_crystals(draft.get("crystals", {}), draft.get("harvest_enabled", False))
        self.draft_id = draft["id"]
        self.server_map = (draft.get("server_map") or {}).get("saved_id")
        self.has_map = True
        self.mode = draft.get("mode") if is_mode(draft.get("mode")) else DEFAULT_MODE
        self.mob_settings_cache = {}
        self.minimap = Minimap()
        self.name_dirty = False
        self.drag = None
        self.draft_list = None
        self.pending_action = None
        self._set_status(f"Черновик «{draft['name']}» открыт", GREEN)

    def _draft_list_event(self, event):
        drafts = self.draft_list
        if drafts.confirm is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                drafts.confirm = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                answer = drafts.confirm_click(event.pos)
                if answer == "delete":
                    self._delete_draft(drafts.confirm)
                elif answer == "cancel":
                    drafts.confirm = None
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.draft_list = None
            self._set_status("Список черновиков закрыт", TEXT_DIM)
        elif event.type == pygame.MOUSEWHEEL:
            self.draft_list.wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            doomed = self.draft_list.delete_at(event.pos)
            if doomed is not None:
                self.draft_list.confirm = doomed
                self.draft_list.message = ""
                return
            draft = self.draft_list.row_at(event.pos)
            if draft is not None:
                self._open_draft(draft["id"])
            elif not self.draft_list.box().collidepoint(event.pos):
                self.draft_list = None
                self._set_status("Список черновиков закрыт", TEXT_DIM)

    def _delete_draft(self, draft):
        """Удаляет черновик с диска. Опубликованную карту не удаляем: публикация на сервере не снимается."""
        listed = next((item for item in map_drafts.list_drafts() if item["id"] == draft["id"]), None)
        worlds = listed["active_worlds"] if listed else []
        if worlds:
            self.draft_list.confirm = None
            self.draft_list.message = f"Нельзя удалить: карта играет в мире «{', '.join(worlds)}»"
            return
        try:
            map_drafts.delete_draft(draft["id"])
        except map_drafts.DraftError as error:
            self.draft_list.confirm = None
            self.draft_list.message = str(error)
            return
        if self.draft_id == draft["id"]:
            self.draft_id = None
        self.draft_list = DraftList(self.font, self.small, map_drafts.list_drafts())
        self.draft_list.message = f"Карта «{draft['name']}» удалена"
        self._set_status(f"Черновик «{draft['name']}» удалён", TEXT_DIM)

    def _server_label(self):
        return "Обновить на сервере" if self.server_map else "Сохранить на сервер"

    def _server_button(self):
        return self._server_label(), self.draft_id is not None and not self._dirty()

    def save_to_server(self):
        """Сохраняет карту на сервере как заготовку. Мир не создаётся и сервер не запускается: это делает раздел «Миры»."""
        if self._dirty() or self.draft_id is None:
            self._notify("Сначала сохраните черновик (Ctrl+S), затем сохраните его на сервер", AMBER)
            return False
        if not self.ensure_login():
            self._set_status("Карта не сохранена: вход на сервер не выполнен", RED)
            return False
        try:
            result = self.client.save_saved_map(
                self._game_cells(), self.state.map_w, self.state.map_h, self.state.name,
                self.mode, mobs=self.state.to_mobs(), saved_id=self.server_map, spawns=self.state.to_spawns(),
                crystals=self.state.to_crystals(), harvest_enabled=self.state.harvest_enabled,
            )
        except ServerError as error:
            self._notify(f"Не сохранено на сервере: {error}", RED)
            return False
        except ValueError as error:
            self._notify(f"Не сохранено на сервере: {error}", RED)
            return False
        map_drafts.mark_server_map(self.draft_id, result["saved_id"], result["name"])
        created = self.server_map is None
        self.server_map = result["saved_id"]
        if result.get("world_errors"):
            self._notify(f"Сохранено, но миры не обновлены: {result['world_errors'][0]['error']}", RED)
            return False
        action = "Карта сохранена на сервере" if created else "Карта на сервере обновлена"
        self._notify(f"{action}: «{result['name']}». Миры с этой картой обновятся сами", GREEN)
        return False

    def publish(self):
        """Открывает список миров: выбранный мир начнёт играть сохранённым черновиком."""
        if self._dirty() or self.draft_id is None:
            self._set_status("Сначала сохраните черновик (Ctrl+S), затем разместите его на сервере", AMBER)
            return False
        if not self.ensure_login():
            self._set_status("Для публикации нужен вход на сервер", RED)
            return False
        try:
            worlds = self.client.list_worlds()
        except ServerError as error:
            self._set_status(f"Миры не загружены: {error}", RED)
            return False
        draft = next((item for item in map_drafts.list_drafts() if item["id"] == self.draft_id), None)
        active = draft["active_worlds"] if draft else []
        self.world_picker = WorldPicker(self.font, self.small, worlds, active, self.state.name)
        self._set_status("Выберите мир и нажмите «Применить»", TEXT_DIM)
        return False

    def _world_picker_event(self, event):
        result = self.world_picker.handle_event(event)
        if result is None:
            return
        if result == "cancel":
            self.world_picker = None
            self._set_status("Размещение отменено", TEXT_DIM)
            return
        world = result[1]
        try:
            cells = self._game_cells()
            published = self.client.publish_map(
                cells, self.state.map_w, self.state.map_h, self.state.name, world["id"],
                mobs=self.state.to_mobs(), mode=self.mode, spawns=self.state.to_spawns(), saved_id=self.server_map,
                crystals=self.state.to_crystals(), harvest_enabled=self.state.harvest_enabled,
            )
        except ServerError as error:
            self.world_picker.message = f"Не размещено: {error}"
            return
        except ValueError as error:
            self.world_picker.message = f"Не размещено: {error}"
            return
        map_drafts.mark_published(self.draft_id, world["id"], world["name"])
        self.world_picker = None
        self._set_status(
            f"Карта «{self.state.name}» размещена в мире «{world['name']}», клеток: {published['applied']}, бесов: {published.get('mobs', 0)}", GREEN
        )

    def open_mask_dialog(self):
        if self.selected is None:
            self._set_status("Сначала выберите элемент в каталоге", AMBER)
            return
        key = self.selected
        native = self._native(key)
        width, height = native.get_size()
        tile = min(MASK_TILE, TILE * MASK_IMAGE_W // width, TILE * MASK_IMAGE_H // height)
        tile = max(MASK_SIDE, tile // MASK_SIDE * MASK_SIDE)
        self.mask_dialog = MaskDialog(
            self.font, self.small, key, self._scaled(key, tile), tile,
            self.partial_masks.get(key), self.state.items[key]['blocks'],
        )
        self._set_status(f"Маска «{key}»: ЛКМ по клетке — переключить", TEXT_DIM)

    def _mask_dialog_event(self, event):
        result = self.mask_dialog.handle_event(event)
        if result is None:
            return
        key = self.mask_dialog.key
        self.mask_dialog = None
        if result == "cancel":
            self._set_status("Маска не изменена", TEXT_DIM)
            return
        action, mask = result
        if action == "clear":
            self.partial_masks.pop(key, None)
            kind = "непроходим" if self.state.items[key]["blocks"] else "проходим"
            message = f"Маска «{key}» убрана: элемент целиком {kind}"
        else:
            self.partial_masks[key] = mask
            message = f"Маска «{key}» сохранена: проходимых клеток {mask.count(FREE)} из 16"
        try:
            save_partial_masks(self.partial_masks)
        except OSError as error:
            self._set_status(f"Маска не записана в файл: {error}", RED)
            return
        self._set_status(message, GREEN)

    def undo(self):
        if self._active_editor_state().undo():
            self._set_status("Действие отменено", TEXT_DIM)

    def redo(self):
        if self._active_editor_state().redo():
            self._set_status("Действие повторено", TEXT_DIM)

    def delete_selection(self):
        state = self._active_editor_state()
        if state.selection is None:
            return
        state.begin_action()
        count = state.delete_selection()
        state.end_action()
        self._set_status(f"Удалено элементов: {count}", TEXT_DIM)

    def deselect(self):
        self._active_editor_state().clear_selection()

    def copy_selection(self):
        stamp = self._active_editor_state().copy_selection()
        if stamp is None:
            self._set_status("Нечего копировать: выделите область инструментом «Выделение» (V)", AMBER)
            return False
        self.stamp = stamp
        count = sum(len(stamp.get(layer, ())) for layer in ("ground", "overlay", "elevation", "relief", "infra", "objects"))
        self._set_status(f"Скопировано элементов: {count}. Ctrl+V — вставить куском", GREEN)
        return True

    def cut_selection(self):
        if self.copy_selection():
            self.delete_selection()
            self._set_status("Вырезано. Ctrl+V — вставить куском", GREEN)

    def paste_stamp(self):
        self._set_tool("stamp")

    def _set_tool(self, tool):
        if tool == "stamp":
            if self.stamp is None:
                self._set_status("Буфер пуст: выделите область (V) и нажмите Ctrl+C или обведите тайлы в каталоге", AMBER)
                return
            self._set_status("Клик по карте — вставить кусок, ПКМ или Esc — отмена", GREEN)
        self.tool = tool

    def _place_stamp(self, tile):
        error = self._stamp_artist_layer_error(self.stamp or {})
        if error:
            self._set_status(error, RED)
            return
        state = self._active_editor_state()
        state.begin_action()
        error = state.paste(self.stamp, tile[0], tile[1])
        state.end_action()
        if error:
            self._set_status(error, RED)

    def toggle_npc_section(self):
        self._set_section("map" if self.section == "npc" else "npc")
        return False

    def _set_section(self, section):
        if section == self.section:
            return
        self.section = section
        self.list_scroll = 0
        self.npc_card = None
        if section == "equip":
            self._ensure_equipment_palette()
        messages = {
            "animals": "Животные: выберите животное в палитре и поставьте его на карту",
            "npc": "Раздел NPC: выберите врага в списке. Клик по клетке ставит его на карту",
            "spawn": "Спаун: клик по клетке ставит или убирает точку появления игрока. ПКМ — убрать",
            "equip": "Экипировка: предметы по слотам. Ctrl + колесо — размер иконок",
        }
        self._set_status(messages.get(section, "Выберите элемент слева и рисуйте на карте"), TEXT_DIM)

    def _build_biome_palette(self, biome):
        max_panel = settings.WIDTH // 2
        return Palette(
            self.biome_catalogs[biome],
            MAP_DIR,
            self.font,
            self.small,
            tile=maximum_tile_size(max_panel),
            max_panel=max_panel,
            animations=PALETTE_ANIMATIONS,
            rules=self.palette_overrides,
            arrange_mode=self.palette_editing,
        )

    def _build_animal_palette(self):
        max_panel = settings.WIDTH // 2
        return Palette(
            self.animal_catalog,
            MAP_DIR,
            self.font,
            self.small,
            tile=maximum_tile_size(max_panel),
            max_panel=max_panel,
            animations=PALETTE_ANIMATIONS,
            rules=self.palette_overrides,
            arrange_mode=self.palette_editing,
        )

    def _set_biome(self, biome):
        if biome == self.biome:
            return
        self.biome = biome
        if biome not in self.biome_palettes:
            self.biome_palettes[biome] = self._build_biome_palette(biome)
        self.palette = self.biome_palettes[biome]
        self.list_scroll = 0
        self._set_status(f"Биом: {dict(BIOME_TABS)[biome]}", TEXT_DIM)

    def _catalog_palette(self):
        """Палитра, которую показывает каталог сейчас: биом, животные или экипировка."""
        if self.section == "equip":
            self._ensure_equipment_palette()
            return self.equipment_palette
        if self.section == "animals":
            return self.animal_palette
        return self.palette

    def _refresh_palette_views(self):
        self.biome_palettes = {
            biome: self._build_biome_palette(biome)
            for biome, _label in BIOME_TABS
        }
        self.palette = self.biome_palettes[self.biome]
        self.animal_palette = self._build_animal_palette()
        self.equipment_palette = None

    def _record_palette_defaults(self, palette):
        for title, clusters in palette._sections:
            order = 0
            for cluster in clusters:
                for _position, item in cluster.cells:
                    key = item["item_key"]
                    self.palette_default_groups.setdefault(key, title)
                    self.palette_default_orders.setdefault(key, order)
                    order += 1

    def _enter_palette_editing(self):
        if self.section not in ("map", "animals"):
            self._set_status("Настройка доступна только в палитре тайлов и животных", RED)
            return
        if self.client is None or not self.ensure_login():
            self._set_status("Войдите на сервер, чтобы загрузить общую палитру", RED)
            return
        try:
            state = self.client.get_map_palette()
        except (ServerError, OSError, ValueError) as error:
            self._set_status(f"Не удалось загрузить палитру сервера: {error}", RED)
            return
        for biome, _label in BIOME_TABS:
            if biome not in self.biome_palettes:
                self.biome_palettes[biome] = self._build_biome_palette(biome)
            self._record_palette_defaults(self.biome_palettes[biome])
        self._record_palette_defaults(self.animal_palette)
        self.palette_version = int(state["version"])
        self.palette_overrides = dict(state["overrides"])
        self.palette_original_overrides = dict(state["overrides"])
        self._refresh_palette_views()
        legacy_position_keys = set()
        for palette in (*self.biome_palettes.values(), self.animal_palette):
            legacy_position_keys.update(palette.legacy_position_keys())
        for key in legacy_position_keys:
            rule = dict(self.palette_overrides.get(key, {}))
            rule.pop("palette_position", None)
            if rule:
                self.palette_overrides[key] = rule
            else:
                self.palette_overrides.pop(key, None)
        self.palette_editing = True
        self.palette_context = None
        self.palette_selected_keys.clear()
        self.list_scroll = 0
        self._refresh_palette_views()
        if legacy_position_keys:
            self._set_status(
                "Старая раскладка восстановлена; ЛКМ перетащите тайлы в пустые клетки, "
                "затем примените палитру для сохранения исправления",
                AMBER,
            )
        else:
            self._set_status(
                "ЛКМ перетащите тайл в пустую клетку его раздела; ПКМ — выбрать раздел. Esc отменяет изменения",
                GREEN,
            )

    def _reset_palette_layout(self):
        changed = False
        for key in list(self.palette_overrides):
            rule = dict(self.palette_overrides[key])
            if "palette_position" in rule:
                rule.pop("palette_position")
                changed = True
                if rule:
                    self.palette_overrides[key] = rule
                else:
                    self.palette_overrides.pop(key)
        if not changed:
            self._set_status("Пользовательская раскладка не настроена", TEXT_DIM)
            return
        self._refresh_palette_views()
        self._set_status("Раскладка палитры сброшена к исходной — подтвердите изменения", AMBER)

    def _place_palette_item(self, key, group, position):
        palette = self._catalog_palette()
        positions = palette.arrangement_positions(group)
        occupying_key = next(
            (other_key for other_key, slot in positions.items() if slot == position and other_key != key),
            None,
        )
        if occupying_key is not None:
            self._set_status("Клетка занята — тайл не перемещён", AMBER)
            return
        if key not in positions or positions[key] == position:
            return
        scroll = self.list_scroll
        item = self.state.items[key]
        rule = dict(self.palette_overrides.get(key, {}))
        default_position = next(
            row.default_positions[key]
            for row in palette.rows
            if row.arrange_group == group and key in row.default_positions
        )
        if position == default_position:
            rule.pop("palette_position", None)
        else:
            rule["palette_position"] = {"x": position[0], "y": position[1]}
        if rule:
            self.palette_overrides[key] = rule
        else:
            self.palette_overrides.pop(key, None)
        self._refresh_palette_views()
        self.list_scroll = min(scroll, self._max_scroll())
        self.selected = key
        self.selected_layer = self._artist_storage_layer(key, None)
        self._set_status(
            f"Тайл «{item.get('name', key)}» перемещён в раздел «{group}» — подтвердите раскладку",
            AMBER,
        )

    def _finish_palette_layout_drag(self, pos):
        drag = self.drag
        if drag is None or drag["mode"] != "palette_layout":
            return
        palette = self._catalog_palette()
        content_point = self._catalog_point(pos)
        target = palette.arrangement_position_at(*content_point)
        if target is None or target[0] != drag["group"]:
            return
        current_position = palette.arrangement_positions(drag["group"]).get(
            drag["key"]
        )
        if current_position == target[1:]:
            return
        self._place_palette_item(drag["key"], drag["group"], target[1:])

    def _finish_palette_selection(self):
        drag = self.drag
        if drag is None or drag["mode"] != "palette_select":
            return
        palette = self._catalog_palette()
        self.palette_selected_keys = palette.arrangement_items_in_rect(
            drag["group"],
            drag["start"],
            drag["end"],
        )
        self._set_status(
            f"Выделено тайлов: {len(self.palette_selected_keys)}. ПКМ по выделенному тайлу — общие настройки",
            TEXT_DIM,
        )

    def _cancel_palette_editing(self):
        self.palette_overrides = dict(self.palette_original_overrides)
        self.palette_editing = False
        self.palette_context = None
        self.palette_selected_keys.clear()
        self.palette_resolutions.clear()
        self.palette_submit_credentials = None
        self._refresh_palette_views()
        self._set_status("Настройка общей палитры отменена", TEXT_DIM)

    def _begin_palette_publish(self):
        if self.palette_overrides == self.palette_original_overrides:
            self.palette_editing = False
            self.palette_context = None
            self.palette_selected_keys.clear()
            self._refresh_palette_views()
            self._set_status("Изменений палитры нет", TEXT_DIM)
            return
        if self.client is None or not self.ensure_login():
            self._set_status("Нужен вход на сервер для подтверждения палитры", RED)
            return
        self.palette_credentials = PaletteCredentialDialog(self.font, self.small)
        pygame.key.start_text_input()

    def _palette_credentials_event(self, event):
        dialog = self.palette_credentials
        result = dialog.handle_event(event)
        if result == "cancel":
            self.palette_credentials = None
            self.palette_submit_credentials = None
            pygame.key.stop_text_input()
            return
        if not isinstance(result, tuple) or result[0] != "submit":
            return
        _action, username, password = result
        try:
            preview = self.client.preview_map_palette(username, password, self.palette_overrides)
        except (ServerError, OSError, ValueError) as error:
            dialog.password = ""
            dialog.message = f"Не удалось проверить данные: {error}"
            dialog.message_color = RED
            dialog.active_field = 1
            self._set_status(f"Не удалось проверить палитру: {error}", RED)
            pygame.key.start_text_input()
            return
        self.palette_credentials = None
        pygame.key.stop_text_input()
        self.palette_version = int(preview["version"])
        self.palette_submit_credentials = (username, password)
        self.palette_resolutions = {}
        self._show_palette_conflicts(preview.get("conflicts", []))
        if not preview.get("conflicts"):
            self._apply_palette_changes()

    def _show_palette_conflicts(self, conflicts):
        self.palette_conflicts = (
            PaletteConflictDialog(self.font, self.small, conflicts)
            if conflicts else None
        )

    def _palette_conflicts_event(self, event):
        result = self.palette_conflicts.handle_event(event)
        if result == "cancel":
            self.palette_conflicts = None
            self.palette_submit_credentials = None
            self.palette_resolutions.clear()
            self._set_status("Применение палитры отменено", TEXT_DIM)
            return
        if result is None:
            return
        conflict_id, key = result
        self.palette_resolutions[conflict_id] = key
        if self.palette_conflicts.index + 1 < len(self.palette_conflicts.conflicts):
            self.palette_conflicts.index += 1
            return
        self.palette_conflicts = None
        self._apply_palette_changes()

    def _apply_palette_changes(self):
        if self.palette_submit_credentials is None:
            self._set_status("Нет подтверждения для отправки палитры", RED)
            return
        username, password = self.palette_submit_credentials
        try:
            result = self.client.apply_map_palette(
                username,
                password,
                self.palette_overrides,
                self.palette_version,
                self.palette_resolutions,
            )
        except (ServerError, OSError, ValueError) as error:
            self.palette_submit_credentials = None
            self.palette_resolutions.clear()
            self.palette_credentials = PaletteCredentialDialog(
                self.font,
                self.small,
                username=username,
            )
            self.palette_credentials.active_field = 1
            self.palette_credentials.message = f"Не удалось сохранить: {error}"
            self.palette_credentials.message_color = RED
            pygame.key.start_text_input()
            self._set_status(f"Не удалось применить палитру: {error}", RED)
            return
        if not result.get("applied"):
            self._show_palette_conflicts(result.get("conflicts", []))
            if self.palette_conflicts is None:
                self._set_status("Сервер отклонил изменения палитры", RED)
            return
        self.palette_version = int(result["version"])
        self.palette_original_overrides = dict(self.palette_overrides)
        self.palette_submit_credentials = None
        self.palette_resolutions.clear()
        self.palette_editing = False
        self.palette_selected_keys.clear()
        self._refresh_palette_views()
        if result.get("removed_cells"):
            removed_cells = result["removed_cells"]
            removed_labels = []
            for cell in removed_cells[:3]:
                item = self.state.items.get(cell["key"])
                name = item.get("name", cell["key"]) if item else cell["key"]
                map_name = cell.get("map_name", "карта")
                removed_labels.append(
                    f"«{name}» — «{map_name}», клетка ({cell['x']}, {cell['y']})"
                )
            extra_count = len(removed_cells) - len(removed_labels)
            extra = f"; ещё {extra_count}" if extra_count else ""
            self._notify(
                "Палитра сохранена. Автоматически убраны конфликтующие объекты: "
                + "; ".join(removed_labels)
                + extra,
                AMBER,
            )
        else:
            self._set_status(
                "Палитра сохранена на сервере; режим настройки закрыт, можно продолжать работу художника",
                GREEN,
            )

    def _palette_rule(self, key):
        item = self.state.items[key]
        rule = dict(self.palette_overrides.get(key, {}))
        default_layer = self._artist_layer_for_item(key) + 1
        rule.setdefault("blocks", bool(item["blocks"]))
        rule.setdefault("editor_layer", default_layer)
        rule.setdefault(
            "generator_role",
            "random_decor" if key in self._catalog_palette()._decor else None,
        )
        rule.setdefault("palette_group", self._palette_default_group(key))
        rule.setdefault("palette_order", self._default_palette_order(key))
        return rule

    def _palette_default_group(self, key):
        return self.palette_default_groups.get(
            key,
            self.state.items[key]["category"],
        )

    def _default_palette_order(self, key):
        return self.palette_default_orders.get(key, 0)

    def _open_palette_context(self, key, position):
        if not self.palette_editing:
            return
        selected_keys = (
            set(self.palette_selected_keys)
            if key in self.palette_selected_keys
            else {key}
        )
        selected_keys = {
            item_key for item_key in selected_keys
            if item_key in self.state.items
        }
        if not selected_keys:
            selected_keys = {key}
        width, height = 330, 296
        rect = pygame.Rect(position[0], position[1], width, height)
        rect.clamp_ip(pygame.display.get_surface().get_rect())
        group_options = list(dict.fromkeys(
            title for title, _clusters in self._catalog_palette()._sections
        ))
        group_options = [title for title in group_options if title != "Легенда"]
        rules = {
            item_key: self._palette_rule(item_key)
            for item_key in selected_keys
        }
        for rule in rules.values():
            if rule["palette_group"] not in group_options:
                group_options.append(rule["palette_group"])
        self.palette_context = {
            "key": key,
            "keys": selected_keys,
            "rect": rect,
            "groups": group_options,
            "initial_rules": {key: dict(rule) for key, rule in rules.items()},
            "rules": rules,
            "confirm": None,
        }

    def _palette_context_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.palette_context["confirm"] is not None:
                self.palette_context["confirm"] = None
            elif self._palette_context_dirty():
                self.palette_context["confirm"] = "cancel"
            else:
                self.palette_context = None
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        context = self.palette_context
        rect = context["rect"]
        if not rect.collidepoint(event.pos):
            return
        local_x, local_y = event.pos[0] - rect.x, event.pos[1] - rect.y
        if context["confirm"] is not None:
            if 244 <= local_y < 282:
                if local_x < rect.w // 2:
                    action = context["confirm"]
                    self.palette_context = None
                    if action == "apply":
                        self._commit_palette_context(context)
                    else:
                        self._set_status("Изменения в окне тайла отменены", TEXT_DIM)
                else:
                    context["confirm"] = None
            return
        if 244 <= local_y < 282:
            if not self._palette_context_dirty():
                self.palette_context = None
                return
            context["confirm"] = "apply" if local_x < rect.w // 2 else "cancel"
            return

        key = context["key"]
        keys = sorted(context["keys"])
        representative = context["rules"][key]
        item = self.state.items[key]
        if 38 <= local_y < 72:
            for item_key in keys:
                context["rules"][item_key]["blocks"] = not context["rules"][item_key]["blocks"]
        elif 74 <= local_y < 108:
            step = 1 if local_x >= rect.w // 2 else -1
            common_layers = set(range(1, 9))
            for item_key in keys:
                selected_item = self.state.items[item_key]
                if item_key in WATER_DECOR_KEYS:
                    allowed = {2}
                elif selected_item["kind"] == "object":
                    allowed = {6, 7, 8}
                else:
                    allowed = {1, 2, 3, 4, 5, 6}
                common_layers.intersection_update(allowed)
            common_layers = sorted(common_layers)
            if not common_layers:
                self._set_status("Для выделенных тайлов нет общего слоя", RED)
                return
            current = representative["editor_layer"]
            if len(common_layers) == 1:
                destination = common_layers[0]
            elif current in common_layers:
                index = common_layers.index(current)
                destination = common_layers[(index + step) % len(common_layers)]
            elif step > 0:
                destination = next(
                    (layer for layer in common_layers if layer > current),
                    common_layers[0],
                )
            else:
                destination = next(
                    (layer for layer in reversed(common_layers) if layer < current),
                    common_layers[-1],
                )
            for item_key in keys:
                context["rules"][item_key]["editor_layer"] = destination
        elif 110 <= local_y < 144:
            for item_key in keys:
                rule = context["rules"][item_key]
                rule["generator_role"] = (
                    None if rule["generator_role"] == "random_decor" else "random_decor"
                )
        elif 146 <= local_y < 180:
            groups = context["groups"]
            current = representative["palette_group"]
            step = 1 if local_x >= rect.w // 2 else -1
            index = groups.index(current) if current in groups else 0
            destination = groups[(index + step) % len(groups)]
            group_orders = sorted(
                values.get("palette_order", 0)
                for other_key, values in self.palette_overrides.items()
                if other_key not in context["keys"]
                and values.get("palette_group") == destination
            )
            next_order = max(group_orders, default=-1) + 1
            for offset, item_key in enumerate(keys):
                rule = context["rules"][item_key]
                rule["palette_group"] = destination
                rule["palette_order"] = next_order + offset
        elif 182 <= local_y < 216:
            if representative["palette_group"] == self._palette_default_group(key):
                self._set_status("Сначала перенесите тайл в пользовательскую группу", AMBER)
                return
            step = -1 if local_x < rect.w // 2 else 1
            for item_key in keys:
                context["rules"][item_key]["palette_order"] += step
        else:
            return
        return

    def _palette_context_dirty(self):
        context = self.palette_context
        return any(
            context["rules"][key] != context["initial_rules"][key]
            for key in context["keys"]
        )

    def _commit_palette_context(self, context):
        properties = (
            "blocks",
            "editor_layer",
            "generator_role",
            "palette_group",
            "palette_order",
        )
        for key in context["keys"]:
            item = self.state.items[key]
            base = dict(self.palette_overrides.get(key, {}))
            initial = context["initial_rules"][key]
            edited = context["rules"][key]
            original = self.palette_original_overrides.get(key, {})
            defaults = {
                "blocks": bool(item["blocks"]),
                "editor_layer": self._default_editor_layer(key),
                "generator_role": (
                    "random_decor" if key in self._catalog_palette()._decor else None
                ),
                "palette_group": self._palette_default_group(key),
                "palette_order": self._default_palette_order(key),
            }
            if edited["palette_group"] != initial["palette_group"]:
                base.pop("palette_position", None)
            for property_name in properties:
                value = edited[property_name]
                if value == initial[property_name]:
                    continue
                if property_name in original or value != defaults[property_name]:
                    base[property_name] = value
                else:
                    base.pop(property_name, None)
            if base:
                self.palette_overrides[key] = base
            else:
                self.palette_overrides.pop(key, None)
        self._refresh_palette_views()
        self._set_status(
            f"Настройки применены к {len(context['keys'])} тайлам — подтвердите палитру на сервере",
            AMBER,
        )

    def _default_editor_layer(self, key):
        item = self.state.items[key]
        if key in WATER_DECOR_KEYS:
            return 2
        if item.get("editor_layer") is not None:
            return int(item["editor_layer"])
        return self._artist_layer_for_item(key, include_overrides=False) + 1

    def _ensure_equipment_palette(self):
        if self.equipment_palette is not None:
            return
        items = []
        try:
            if self.client is not None:
                items = self.client.get_equipment_items(list(mob_modes.MOB_EQUIPMENT_SLOTS))
        except (ServerError, OSError):
            self._set_status("Экипировка не загружена: сервер недоступен", RED)
        self.equipment_palette = EquipmentPalette(items, self.font, self.small, self.palette.panel_width(), self.palette.tile)

    def _tab_rects(self):
        """Вкладки раздела в две строки, если в одну не помещаются."""
        panel = self.panel_rect()
        rects = []
        x, row = 8, 0
        for section, label, width in SECTION_TABS:
            if x + width > panel.right - 8:
                x, row = 8, row + 1
            rects.append((section, label, pygame.Rect(x, panel.y + 34 + row * 28, width, 24)))
            x += width + 6
        return rects

    def _npc_row_rect(self, index):
        y = self._list_top() + index * NPC_ROW_H - self.list_scroll
        return pygame.Rect(8, y, min(self.panel_w - 16, NPC_LIST_W), NPC_ROW_H - 6)

    def _spawn_row_rect(self):
        return pygame.Rect(8, self._list_top(), min(self.panel_w - 16, NPC_LIST_W), NPC_ROW_H - 6)

    def _draw_spawn_row(self, screen):
        rect = self._spawn_row_rect()
        pygame.draw.rect(screen, (58, 76, 104), rect, border_radius=6)
        pygame.draw.rect(screen, HOVER_COLOR, rect, 2, border_radius=6)
        radius = NPC_FRAME // 2 - 6
        center = (rect.x + 6 + NPC_FRAME // 2, rect.centery)
        pygame.draw.circle(screen, (80, 220, 120), center, radius)
        pygame.draw.circle(screen, (10, 40, 20), center, radius, 2)
        screen.blit(self.font.render("Точка спауна", True, TEXT), (rect.x + NPC_FRAME + 20, rect.y + 16))
        screen.blit(self.small.render("клик по карте · ПКМ — убрать", True, TEXT_DIM), (rect.x + NPC_FRAME + 20, rect.y + 40))

    def _npc_at(self, pos):
        if not (self._list_top() <= pos[1] < self._list_bottom()):
            return None
        for index, npc in enumerate(self.npc_list):
            if self._npc_row_rect(index).collidepoint(pos):
                return npc
        return None

    def _select_npc(self, npc):
        if npc is None:
            return
        self.selected_npc = npc["key"]
        self._set_status(f"Выбран NPC: {npc['name']}. Расстановка на карте появится на следующем этапе", TEXT_DIM)

    def _npc_frame(self, npc, row, column):
        """Кадр листа ходьбы NPC 64x64 или None, если файла листа нет."""
        key = npc["key"]
        if key not in self.npc_sheets:
            try:
                self.npc_sheets[key] = pygame.image.load(str(sheet_path(npc, "walk"))).convert_alpha()
            except (pygame.error, OSError):
                self.npc_sheets[key] = None
        sheet = self.npc_sheets[key]
        if sheet is None:
            return None
        return sheet.subsurface(pygame.Rect(column * NPC_FRAME, row * NPC_FRAME, NPC_FRAME, NPC_FRAME))

    def _mob_settings(self, kind):
        """Настройки вида моба в режиме карты: из файла режима или по умолчанию, с сообщением об ошибке файла."""
        key = (self.mode, kind)
        if key not in self.mob_settings_cache:
            try:
                self.mob_settings_cache[key] = mob_modes.load_mob_settings(self.mode, kind)
            except mob_modes.ModeFileError as error:
                self._set_status(str(error), RED)
                self.mob_settings_cache[key] = mob_modes.default_settings(kind)
        return self.mob_settings_cache[key]

    def _npc_card_rect(self):
        """Карточка моба справа от панели, на уровне его строки; None, если карточка не показана."""
        if self.npc_card is None or self.section != "npc" or self.mob_dialog is not None:
            return None
        index = next((i for i, npc in enumerate(self.npc_list) if npc["key"] == self.npc_card), None)
        if index is None or not self._npc_row_rect(index).colliderect(pygame.Rect(0, self._list_top(), self.panel_w, self._list_bottom() - self._list_top())):
            return None
        rect = pygame.Rect(self.panel_w + 6, self._npc_row_rect(index).y, NPC_CARD_W, NPC_CARD_H)
        rect.bottom = min(rect.bottom, settings.HEIGHT - STATUS_H - 6)
        return rect

    @staticmethod
    def _npc_card_button(card):
        return pygame.Rect(card.x + 14, card.bottom - 48, card.w - 28, 34)

    def _update_npc_card(self, pos):
        """Карточка появляется при наведении на моба и остаётся, пока мышь на строке, на карточке или между ними."""
        if self.section != "npc" or self.mob_dialog is not None:
            self.npc_card = None
            return
        hovered = self._npc_at(pos)
        if hovered is not None:
            self.npc_card = hovered["key"]
            return
        card = self._npc_card_rect()
        if card is None:
            self.npc_card = None
            return
        index = next(i for i, npc in enumerate(self.npc_list) if npc["key"] == self.npc_card)
        if not self._npc_row_rect(index).union(card).collidepoint(pos):
            self.npc_card = None

    def _draw_npc_card(self, screen):
        card = self._npc_card_rect()
        if card is None:
            return
        npc = next(npc for npc in self.npc_list if npc["key"] == self.npc_card)
        params = self._mob_settings(npc["key"])
        pygame.draw.rect(screen, PANEL_BG, card, border_radius=8)
        pygame.draw.rect(screen, HOVER_COLOR, card, 2, border_radius=8)
        frame = self._npc_frame(npc, NPC_ROW_DOWN, int(pygame.time.get_ticks() / 1000 * NPC_ANIM_FPS) % NPC_FRAMES_PER_ROW)
        if frame is not None:
            screen.blit(pygame.transform.scale(frame, (NPC_FRAME * 2, NPC_FRAME * 2)), (card.x + 14, card.y + 14))
        screen.blit(self.title.render(npc["name"], True, TEXT), (card.x + 156, card.y + 22))
        screen.blit(self.small.render(npc["key"], True, TEXT_DIM), (card.x + 156, card.y + 50))
        screen.blit(self.small.render(f"Режим: {mode_name(self.mode)}", True, TEXT_DIM), (card.x + 156, card.y + 70))
        stats = params["stats"]
        lines = [
            f"Уровень {params['level']} · {mob_modes.STATE_LABELS[params['state']].lower()}",
            f"Скорость: {params['move_speed']:.0f} px/с",
            f"Замах: {params['windup']:.2f} с · откат: {params['backswing']:.2f} с",
            f"Агрессия: {params['aggro_tiles']:.1f} тайла · патруль: {len(params['patrol'])} клеток",
            f"Респаун: {mob_modes.format_hms(params['respawn_seconds'])}",
            " · ".join(f"{mob_modes.STAT_SHORT[key]} {stats[key]}" for key, _label in mob_modes.STAT_LABELS),
        ]
        for number, line in enumerate(lines):
            screen.blit(self.small.render(line, True, TEXT), (card.x + 14, card.y + 152 + number * 20))
        button = self._npc_card_button(card)
        hovered = button.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (70, 130, 80) if hovered else (56, 106, 66), button, border_radius=5)
        label = self.font.render("Задать параметры", True, TEXT)
        screen.blit(label, label.get_rect(center=button.center))

    def _open_mob_dialog(self, kind):
        npc = next(npc for npc in self.npc_list if npc["key"] == kind)
        equipment_items, equipment_note = [], ""
        try:
            if self.client is not None:
                equipment_items = self.client.get_equipment_items(list(mob_modes.MOB_EQUIPMENT_SLOTS))
        except (ServerError, OSError):
            equipment_note = "Экипировка не загружена: сервер недоступен"
        self.mob_dialog = MobParamsDialog(
            self.font, self.small, npc["name"], mode_name(self.mode), self._mob_settings(kind), equipment_items,
        )
        self.mob_dialog.message = equipment_note
        self.mob_dialog_kind = kind
        self.npc_card = None
        self._set_status(f"Параметры «{npc['name']}»: измените значения и нажмите «Сохранить изменения»", TEXT_DIM)

    def _crystal_dialog_event(self, event):
        result = self.crystal_dialog.handle_event(event)
        if result is None:
            return
        if result == "cancel":
            self.crystal_dialog = None
            self._set_status("Настройки кристалла не изменены", TEXT_DIM)
            return
        color = self.crystal_dialog.color
        colors = crystal_colors(self.state.items)
        try:
            check_loot_order(self.state.crystal_settings, colors, color, result[1])
        except ValueError as error:
            self.crystal_dialog.message = str(error)
            return
        self.state.set_crystal_settings(color, result[1])
        self.crystal_dialog = None
        self._set_status(f"Настройки кристалла «{color}» сохранены: применяются ко всем стадиям цвета", GREEN)

    def _open_crystal_dialog(self, key):
        color, _stage = parse_crystal_key(key)
        colors = crystal_colors(self.state.items)
        if not crystal_unlocked(self.state.crystal_settings, colors, color):
            index = colors.index(color)
            self._set_status(f"Сначала настройте кристалл «{colors[index - 1]}»", AMBER)
            return
        settings = settings_for(self.state.crystal_settings, color)
        loot_items, loot_note = [], ""
        try:
            if self.client is not None:
                loot_items = self.client.get_material_items()
        except (ServerError, OSError):
            loot_note = "Материалы не загружены: сервер недоступен"
        self.crystal_dialog = CrystalSettingsDialog(
            self.font, self.small, color, f"Настройки кристалла «{color}»", settings, loot_items,
        )
        self.crystal_dialog.message = loot_note
        self.last_catalog_click = None

    def toggle_harvest(self):
        enabled = self.state.toggle_harvest()
        if enabled:
            self._set_status("Добыча кристаллов включена: игроки смогут добывать кристаллы на этой карте", GREEN)
        else:
            self._set_status("Добыча кристаллов выключена: кристаллы на карте только декорация", TEXT_DIM)

    def _mob_dialog_event(self, event):
        result = self.mob_dialog.handle_event(event)
        if result is None:
            return
        if result == "cancel":
            self.mob_dialog = None
            self._set_status("Параметры моба не изменены", TEXT_DIM)
            return
        kind = self.mob_dialog_kind
        try:
            saved = mob_modes.save_mob_settings(self.mode, kind, result[1])
        except ValueError as error:
            self.mob_dialog.message = str(error)
            return
        self.mob_settings_cache[(self.mode, kind)] = saved
        self.mob_dialog = None
        self._set_status(f"Параметры «{kind}» сохранены в mob_modes/{self.mode}.json", GREEN)

    def _toggle_spawn(self, tile):
        result = self.state.toggle_spawn(tile[0], tile[1])
        if result == "added":
            self._set_status(f"Точка спауна {len(self.state.spawns)} на ({tile[0]}, {tile[1]})", GREEN)
        elif result == "removed":
            self._set_status(f"Точка спауна убрана с ({tile[0]}, {tile[1]})", TEXT_DIM)
        else:
            self._set_status(result, RED)

    def _remove_spawn(self, tile):
        if self.state.erase_spawn(tile[0], tile[1]):
            self._set_status(f"Точка спауна убрана с ({tile[0]}, {tile[1]})", TEXT_DIM)

    def _draw_spawns(self, screen, grid, x0, y0, x1, y1):
        z = self.zoom
        radius = max(4, z // 2)
        for index, (sx, sy) in enumerate(self.state.spawns):
            if not (x0 <= sx < x1 and y0 <= sy < y1):
                continue
            center = (grid.x + (sx - x0) * z + z // 2, grid.y + (sy - y0) * z + z // 2)
            pygame.draw.circle(screen, (80, 220, 120), center, radius)
            pygame.draw.circle(screen, (10, 40, 20), center, radius, 2)
            if z >= 12:
                number = self.small.render(str(index + 1), True, (10, 30, 15))
                screen.blit(number, number.get_rect(center=center))

    def _npc_sprite(self, kind, size):
        """Кадр беса для клетки карты: первый кадр ходьбы вниз, квадрат size×size. None, если листа нет."""
        cache_key = (kind, size)
        if cache_key not in self.npc_scaled:
            npc = next((item for item in self.npc_list if item["key"] == kind), None)
            frame = self._npc_frame(npc, NPC_ROW_DOWN, 0) if npc is not None else None
            self.npc_scaled[cache_key] = None if frame is None else _scale_rgba(frame.copy(), (size, size))
        return self.npc_scaled[cache_key]

    def _place_mob(self, tile):
        if self.active_map_layer != MOB_LAYER_INDEX:
            self._set_status(
                f"Мобы размещаются только на слое {MOB_LAYER_INDEX + 1} "
                f"«{EDITOR_LAYER_LABELS[MOB_LAYER_INDEX]}»",
                RED,
            )
            return
        if self.selected_npc is None:
            self._set_status("Сначала выберите беса в списке слева", AMBER)
            return
        self.state.begin_action()
        error = self.state.place_mob(self.selected_npc, tile[0], tile[1])
        self.state.end_action()
        if error:
            self._set_status(error, RED)
        else:
            self._set_status(f"Бес на ({tile[0]}, {tile[1]}). Всего на карте: {len(self.state.mobs)}", GREEN)

    def _remove_mob(self, tile):
        if self.active_map_layer != MOB_LAYER_INDEX:
            self._set_status(
                f"Мобы удаляются только на слое {MOB_LAYER_INDEX + 1} "
                f"«{EDITOR_LAYER_LABELS[MOB_LAYER_INDEX]}»",
                RED,
            )
            return
        self.state.begin_action()
        removed = self.state.erase_mob(tile[0], tile[1])
        self.state.end_action()
        if removed:
            self._set_status(f"Бес убран с ({tile[0]}, {tile[1]}). Всего на карте: {len(self.state.mobs)}", TEXT_DIM)

    def _draw_mobs(self, screen, grid, x0, y0, x1, y1, alpha=255):
        z = self.zoom
        for (mx, my), kind in self.state.mobs.items():
            if not (x0 <= mx < x1 and y0 <= my < y1):
                continue
            image = self._npc_sprite(kind, z * 2)
            if image is None:
                continue
            if alpha < 255:
                image = image.copy()
                image.set_alpha(alpha)
            tile = pygame.Rect(grid.x + (mx - x0) * z, grid.y + (my - y0) * z, z, z)
            screen.blit(image, image.get_rect(midbottom=(tile.centerx, tile.bottom)))
            pygame.draw.rect(screen, (255, 90, 90), tile, 1)

    def _draw_npc_ghost(self, screen, grid):
        image = self._npc_sprite(self.selected_npc, self.zoom * 2)
        if image is None:
            return
        ghost = image.copy()
        ghost.set_alpha(150)
        hx, hy = self.hover
        tile = pygame.Rect(
            grid.x + (hx - self.origin_x) * self.zoom, grid.y + (hy - self.origin_y) * self.zoom, self.zoom, self.zoom
        )
        screen.blit(ghost, ghost.get_rect(midbottom=(tile.centerx, tile.bottom)))
        pygame.draw.rect(screen, HOVER_COLOR, tile, 2)

    def _draw_npc_list(self, screen):
        frame_index = int(pygame.time.get_ticks() / 1000 * NPC_ANIM_FPS) % NPC_FRAMES_PER_ROW
        mouse = pygame.mouse.get_pos()
        previous_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(0, self._list_top(), self.panel_w, self._list_bottom() - self._list_top()))
        for index, npc in enumerate(self.npc_list):
            rect = self._npc_row_rect(index)
            if rect.bottom <= self._list_top() or rect.top >= self._list_bottom():
                continue
            chosen = npc["key"] == self.selected_npc
            color = (58, 76, 104) if chosen else ((46, 50, 58) if rect.collidepoint(mouse) else (38, 41, 48))
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, HOVER_COLOR if chosen else BORDER, rect, 2 if chosen else 1, border_radius=6)
            frame = self._npc_frame(npc, NPC_ROW_DOWN, frame_index if chosen else 0)
            if frame is not None:
                screen.blit(frame, (rect.x + 6, rect.centery - NPC_FRAME // 2))
            screen.blit(self.font.render(npc["name"], True, TEXT), (rect.x + NPC_FRAME + 20, rect.y + 16))
            screen.blit(self.small.render("ходьба · атака", True, TEXT_DIM), (rect.x + NPC_FRAME + 20, rect.y + 40))
        screen.set_clip(previous_clip)

    def _draw_tabs(self, screen):
        for section, label, rect in self._tab_rects():
            active = section == self.section
            pygame.draw.rect(screen, (70, 98, 136) if active else (46, 50, 58), rect, border_radius=4)
            pygame.draw.rect(screen, BORDER, rect, 1, border_radius=4)
            text = self.small.render(label, True, TEXT if active else TEXT_DIM)
            screen.blit(text, text.get_rect(center=rect.center))
        if self.section == "map":
            for biome, label, rect in self._biome_tab_rects():
                active = biome == self.biome
                pygame.draw.rect(screen, (70, 98, 136) if active else (46, 50, 58), rect, border_radius=4)
                pygame.draw.rect(screen, BORDER, rect, 1, border_radius=4)
                text = self.small.render(label, True, TEXT if active else TEXT_DIM)
                screen.blit(text, text.get_rect(center=rect.center))

    def _biome_tab_rects(self):
        panel = self.panel_rect()
        gap = 6
        width = (panel.w - 16 - gap * (len(BIOME_TABS) - 1)) // len(BIOME_TABS)
        y = panel.y + 90
        return [
            (biome, label, pygame.Rect(8 + index * (width + gap), y, width, 24))
            for index, (biome, label) in enumerate(BIOME_TABS)
        ]

    def toggle_grid(self):
        self.show_grid = not self.show_grid

    def toggle_minimap(self):
        self.show_minimap = not self.show_minimap
        self._clamp_origin()

    def open_rename(self):
        self.prompt = TextPrompt(self.font, self.small, "Название карты", self.state.name, NAME_MAX)
        pygame.key.start_text_input()

    def _prompt_key(self, event):
        result = self.prompt.handle_key(event)
        if result is None:
            return
        text = self.prompt.text.strip()
        self.prompt = None
        pygame.key.stop_text_input()
        if result == "cancel":
            self._set_status("Название не изменено", TEXT_DIM)
            return
        if text != self.state.name:
            self.state.name = text
            self.name_dirty = True
            self._set_status("Название изменено. Сохраните черновик", AMBER)

    def _request_close(self):
        """Без несохранённых изменений редактор закрывается сразу. Иначе открывается окно выбора."""
        if not self._dirty():
            return True
        if self.exit_dialog is None:
            self.exit_dialog = ExitDialog(self.font, self.small)
        self._set_status("Несохранённые изменения. Выберите: сохранить, выйти без сохранения или остаться", AMBER)
        return False

    def _exit_dialog_event(self, event):
        """Возвращает True, когда редактор нужно закрыть."""
        result = self.exit_dialog.handle_event(event)
        if result is None:
            return False
        if result == "cancel":
            self.exit_dialog = None
            self._set_status("Выход отменён", TEXT_DIM)
            return False
        if result == "discard":
            return True
        self.exit_dialog = None
        self.exit_after_save = True
        self.save()
        return False

    def _key(self, event):
        ctrl = event.mod & pygame.KMOD_CTRL
        if event.key == pygame.K_ESCAPE:
            if self.palette_editing:
                self._cancel_palette_editing()
                return False
            if self.menu.is_open():
                self.menu.close()
                return False
            if self.tool == "stamp":
                self.tool = "brush"
                return False
            if self._active_editor_state().selection is not None:
                self.deselect()
                return False
            return self._command("exit")
        if ctrl:
            command = _ctrl_command(event)
            return self._command(command) if command else False
        scancode = getattr(event, "scancode", None)
        if scancode in TOOL_SCANCODES:
            self.tool = TOOL_SCANCODES[scancode]
        elif scancode in BRUSH_SIZE_SCANCODES:
            self.brush_size = max(1, min(MAX_BRUSH, self.brush_size + BRUSH_SIZE_SCANCODES[scancode]))
        elif scancode in PLAIN_SCANCODES:
            return self._command(PLAIN_SCANCODES[scancode])
        elif event.key in PLAIN_KEYS:
            return self._command(PLAIN_KEYS[event.key])
        elif event.key in PAN_KEYS:
            self._pan_by(*PAN_KEYS[event.key])
        elif event.key in ZOOM_KEYS:
            self._set_zoom(self.zoom + ZOOM_KEYS[event.key])
        return False

    def _wheel(self, steps, ctrl=False):
        pos = pygame.mouse.get_pos()
        if self.panel_rect().collidepoint(pos):
            if ctrl:
                self._palette_zoom(self.palette.tile)
            else:
                self.list_scroll = max(0, min(self.list_scroll - steps * WHEEL_STEP, self._max_scroll()))
        elif self.section in ("map", "animals") and not ctrl and self.grid_rect().collidepoint(pos):
            for _ in range(abs(steps)):
                self._cycle_tool(1 if steps > 0 else -1)
        else:
            self._set_zoom(self.zoom + 4 * steps)

    def _cycle_tool(self, step):
        ids = [tool_id for tool_id, _label, _hotkey in TOOLS]
        index = ids.index(self.tool)
        for _ in ids:
            index = (index + step) % len(ids)
            candidate = ids[index]
            if candidate == "stamp" and self.stamp is None:
                continue
            self._set_tool(candidate)
            if candidate != "stamp":
                self._set_status(f"Инструмент: {TOOL_LABELS[candidate]}", TEXT_DIM)
            return

    def _modal_open(self):
        dialogs = (
            self.exit_dialog, self.prompt, self.save_dialog, self.draft_list, self.size_picker,
            self.world_picker, self.mob_dialog, self.crystal_dialog, self.item_dialog, self.mask_dialog,
            self.palette_credentials, self.palette_conflicts, self.palette_context,
        )
        return self.menu.is_open() or any(dialog is not None for dialog in dialogs)

    def _cursor_kind(self):
        if not self.has_map or self.section not in ("map", "animals") or self.hover is None or self._modal_open():
            return "arrow"
        return self.tool

    def _sync_cursor(self):
        kind = self._cursor_kind()
        if kind == self.cursor_kind:
            return
        self.cursor_kind = kind
        try:
            pygame.mouse.set_cursor(_cursor_for(kind))
        except pygame.error:
            # Headless-драйвер SDL не поддерживает курсоры; на работу редактора это не влияет.
            pass

    def _tiles_rect(self, grid, tiles):
        xs = [tile[0] for tile in tiles]
        ys = [tile[1] for tile in tiles]
        return pygame.Rect(
            grid.x + (min(xs) - self.origin_x) * self.zoom,
            grid.y + (min(ys) - self.origin_y) * self.zoom,
            (max(xs) - min(xs) + 1) * self.zoom,
            (max(ys) - min(ys) + 1) * self.zoom,
        )

    def _palette_zoom(self, tile):
        self._set_status("Размер палитры зафиксирован: 10 тайлов в ряд", TEXT_DIM)

    def _mouse_down(self, event):
        pos = event.pos
        if event.button == 1 and self._add_item_rect().collidepoint(pos) and self.mob_dialog is None:
            self.item_dialog = ItemFormDialog(self.font, self.small)
            return False
        menus = self._menus()
        if event.button == 1 or self.menu.is_open():
            consumed, command = self.menu.click(pos, menus)
            if consumed:
                return self._command(command) if command else False
        card = self._npc_card_rect()
        if card is not None and card.collidepoint(pos):
            if event.button == 1 and self._npc_card_button(card).collidepoint(pos):
                self._open_mob_dialog(self.npc_card)
            return False
        if event.button == 1 and MENU_H <= pos[1] < TOP:
            if self.toolbar.server_clicked(pos, settings.WIDTH):
                return self.save_to_server()
            tool = self.toolbar.click(pos, TOOLS)
            if tool:
                self._set_tool(tool)
            return False
        if event.button == 1 and self.has_map and self.layer_bar_rect().collidepoint(pos):
            self._layer_tab_click(pos)
            return False
        if event.button == 1 and self._minimap_button_rect().collidepoint(pos):
            self.toggle_minimap()
            return False
        if self.panel_rect().collidepoint(pos):
            self._panel_down(event)
            return False
        if event.button == 2 and self.grid_rect().collidepoint(pos):
            self.drag = {"mode": "pan", "start": pos, "origin": (self.origin_x, self.origin_y)}
            return False
        tile = self._tile_at(pos)
        if tile is None:
            return False
        if event.button == 1:
            self._grid_primary(tile, shift=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
        elif event.button == 3:
            self._grid_secondary(tile)
        return False

    def _panel_down(self, event):
        if event.button == 3:
            if not self.palette_editing:
                return
            if self.section not in ("map", "animals"):
                return
            if self._list_top() <= event.pos[1] < self._list_bottom() and event.pos[0] < self.scroll_x:
                point = self._catalog_point(event.pos)
                palette = self._catalog_palette()
                key = palette.item_at(*point)
                if key is not None and key in self.state.items:
                    if palette.compound_entries(key):
                        self._set_status("Цельный водный штамп настраивается как единый объект", TEXT_DIM)
                    else:
                        if key not in self.palette_selected_keys:
                            self.palette_selected_keys = {key}
                        self._open_palette_context(key, event.pos)
            return
        if event.button != 1:
            return
        pos = event.pos
        if self._palette_settings_rect().collidepoint(pos):
            if self.palette_editing:
                self._begin_palette_publish()
            else:
                self._enter_palette_editing()
            return
        if self.palette_editing and self._palette_reset_rect().collidepoint(pos):
            self._reset_palette_layout()
            return
        for section, _label, rect in self._tab_rects():
            if rect.collidepoint(pos):
                self._set_section(section)
                return
        if self.section == "map":
            for biome, _label, rect in self._biome_tab_rects():
                if rect.collidepoint(pos):
                    self._set_biome(biome)
                    return
        minimap = self._minimap_rect()
        if minimap is not None and minimap.collidepoint(pos):
            self.drag = {"mode": "minimap"}
            self._center_view_on(self._minimap_tile(pos))
        elif self._max_scroll() and self._scrollbar_track().collidepoint(pos):
            thumb = self._scroll_thumb()
            offset = pos[1] - thumb.y if thumb.collidepoint(pos) else thumb.h // 2
            self.drag = {"mode": "scroll", "offset": offset}
            self._scroll_to_pointer(pos[1], offset)
        elif self.section == "npc":
            self._select_npc(self._npc_at(pos))
        elif self.section == "spawn":
            if self._spawn_row_rect().collidepoint(pos):
                self._set_status("Точка спауна: клик по клетке ставит, повторный клик или ПКМ убирает", GREEN)
        elif self.section == "equip":
            if self._list_top() <= pos[1] < self._list_bottom() and pos[0] < self.scroll_x:
                palette = self._catalog_palette()
                key = palette.item_at(*self._catalog_point(pos))
                if key is not None:
                    self.equipment_selected = key
                    item = palette.item(key)
                    self._set_status(
                        f"Экипировка: {item['name']}. Выбор предмета на карту появится на следующем этапе", TEXT_DIM,
                    )
        elif self._list_top() <= pos[1] < self._list_bottom() and pos[0] < self.scroll_x:
            point = self._catalog_point(pos)
            palette = self._catalog_palette()
            if self.palette_editing:
                layout_target = palette.arrangement_position_at(*point)
                if layout_target is not None:
                    item_key = palette.arrangement_item_at(layout_target)
                    if item_key is None:
                        self.drag = {
                            "mode": "palette_select",
                            "group": layout_target[0],
                            "start": layout_target[1:],
                            "end": layout_target[1:],
                        }
                        return
            crystal = self._crystal_button(pos)
            if crystal is not None:
                self._open_crystal_dialog(crystal[0])
                return
            key = palette.item_at(*point)
            if key is not None:
                now = pygame.time.get_ticks()
                last = self.last_catalog_click
                self.last_catalog_click = (key, now)
                if last is not None and last[0] == key and now - last[1] <= DOUBLE_CLICK_MS and parse_crystal_key(key) is not None:
                    self.last_catalog_click = None
                    self._open_crystal_dialog(key)
                    return
                self.selected = key
                if self.palette_editing:
                    if key not in self.palette_selected_keys:
                        self.palette_selected_keys = {key}
                self.selected_layer = self._artist_storage_layer(
                    key,
                    palette.item_layer_at(*point),
                )
                compound = palette.compound_entries(key)
                if compound:
                    self.stamp = self.state.make_stamp(compound)
                    self.tool = "stamp"
                    self._set_status(
                        f"Выбран цельный водный штамп {self.stamp['w']}×{self.stamp['h']}: "
                        "клик по воде — вставить",
                        GREEN,
                    )
                    return
                self.tool = "brush"
                item = self.state.items[key]
                self._set_status(f"Выбрано: {key} · {item['category']} · обведите несколько тайлов, чтобы взять кусок", TEXT_DIM)
                if self.palette_editing:
                    group = palette.arrangement_group_for_item(key)
                    if group is not None:
                        self.drag = {
                            "mode": "palette_layout",
                            "key": key,
                            "group": group,
                            "end": event.pos,
                        }
                else:
                    self.drag = {"mode": "catalog", "start": point, "end": point}

    def _crystal_button(self, pos):
        """(ключ кристалла, прямоугольник кнопки в координатах содержимого) под точкой или None."""
        if self.section != "map" or self.mob_dialog is not None or self.crystal_dialog is not None:
            return None
        if not (self._list_top() <= pos[1] < self._list_bottom() and pos[0] < self.scroll_x):
            return None
        palette = self._catalog_palette()
        point = self._catalog_point(pos)
        key = palette.item_at(*point)
        if key is None or parse_crystal_key(key) is None:
            return None
        card = palette.item_rect(key)
        if card is None:
            return None
        button = pygame.Rect(card.right - CRYSTAL_BTN - 4, card.top + 4, CRYSTAL_BTN, CRYSTAL_BTN)
        screen_button = button.move(0, self._list_top() - self.list_scroll)
        if not pygame.Rect(0, self._list_top(), self.scroll_x, self._list_bottom() - self._list_top()).contains(screen_button):
            return None
        return key, button

    def _catalog_point(self, pos):
        return pos[0], pos[1] - self._list_top() + self.list_scroll

    def _marquee(self):
        if self.drag and self.drag["mode"] == "catalog" and self.drag["end"] != self.drag["start"]:
            return self.drag["start"], self.drag["end"]
        return None

    def _finish_catalog_drag(self):
        entries = self._catalog_palette().stamp_entries(self.drag["start"], self.drag["end"], with_layers=True)
        if len(entries) < 2:
            return
        stamp = self.state.make_stamp([(dx, dy, key, layer) for key, dx, dy, layer in entries])
        if stamp is None:
            return
        self.stamp = stamp
        self.tool = "stamp"
        self._set_status(f"Взят кусок {stamp['w']}×{stamp['h']}: клик по карте — вставить, ПКМ или Esc — отмена", GREEN)

    def _scrollbar_track(self):
        return pygame.Rect(self.scroll_x, self._list_top(), SCROLL_W, self._list_bottom() - self._list_top())

    def _scroll_thumb(self):
        track = self._scrollbar_track()
        max_scroll = self._max_scroll()
        if max_scroll == 0:
            return pygame.Rect(track.x, track.y, track.w, track.h)
        thumb_h = max(SCROLL_MIN_THUMB, track.h * track.h // self._content_height())
        thumb_y = track.y + (track.h - thumb_h) * self.list_scroll // max_scroll
        return pygame.Rect(track.x, thumb_y, track.w, thumb_h)

    def _scroll_to_pointer(self, y, offset):
        track = self._scrollbar_track()
        travel = track.h - self._scroll_thumb().h
        if travel <= 0:
            return
        ratio = max(0.0, min(1.0, (y - offset - track.y) / travel))
        self.list_scroll = round(ratio * self._max_scroll())

    def _grid_primary(self, tile, shift=False):
        state = self._active_editor_state()
        if self.section == "spawn":
            self._toggle_spawn(tile)
            return
        if self.section == "npc":
            self._place_mob(tile)
            return
        if self.tool == "stamp":
            self._place_stamp(tile)
        elif self.tool == "select":
            if shift and state.in_selection(*tile):
                state.begin_action()
                self.drag = {"mode": "move", "last": tile}
            else:
                state.select(tile[0], tile[1], tile[0], tile[1])
                self.drag = {"mode": "select", "start": tile}
        elif self.tool == "fill":
            self._fill(tile)
        elif self.tool == "erase":
            self._start_erase(tile)
        else:
            state.begin_action()
            self.drag = {"mode": "paint", "last": tile}
            self._paint(tile)

    def _grid_secondary(self, tile):
        if self.section == "spawn":
            self._remove_spawn(tile)
            return
        if self.section == "npc":
            self._remove_mob(tile)
            return
        if self.tool == "stamp":
            self.tool = "brush"
            return
        if self.tool == "select":
            self.deselect()
            return
        self._start_erase(tile)

    def _start_erase(self, tile):
        self._active_editor_state().begin_action()
        self.drag = {"mode": "erase", "last": tile}
        self._erase(tile)

    def _mouse_up(self, pos=None):
        if self.drag and self.drag["mode"] in ("paint", "erase", "move"):
            self._active_editor_state().end_action()
        elif self.drag and self.drag["mode"] == "catalog":
            self._finish_catalog_drag()
        elif self.drag and self.drag["mode"] == "palette_layout":
            self._finish_palette_layout_drag(
                pygame.mouse.get_pos() if pos is None else pos
            )
        elif self.drag and self.drag["mode"] == "palette_select":
            self._finish_palette_selection()
        self.drag = None

    def _mouse_move(self, event):
        pos = event.pos
        menus = self._menus()
        if self.menu.is_open():
            self.menu.hover(pos, menus)
        self.hover = None if self.menu.covers(pos, menus) else self._tile_at(pos)
        self._update_npc_card(pos)
        if not self.drag:
            return
        mode = self.drag["mode"]
        if mode == "pan":
            sx, sy = self.drag["start"]
            ox, oy = self.drag["origin"]
            self.origin_x = ox - (pos[0] - sx) // self.zoom
            self.origin_y = oy - (pos[1] - sy) // self.zoom
            self._clamp_origin()
        elif mode == "minimap":
            tile = self._minimap_tile(pos, clamp=True)
            if tile is not None:
                self._center_view_on(tile)
        elif mode == "scroll":
            self._scroll_to_pointer(pos[1], self.drag["offset"])
        elif mode == "catalog":
            self.drag["end"] = self._catalog_point(pos)
        elif mode == "palette_layout":
            self.drag["end"] = pos
            list_top, list_bottom = self._list_top(), self._list_bottom()
            if pos[1] < list_top + 18 and self.list_scroll > 0:
                self.list_scroll = max(0, self.list_scroll - WHEEL_STEP)
            elif pos[1] > list_bottom - 18:
                self.list_scroll = min(self._max_scroll(), self.list_scroll + WHEEL_STEP)
        elif mode == "palette_select":
            list_top, list_bottom = self._list_top(), self._list_bottom()
            if pos[1] < list_top + 18 and self.list_scroll > 0:
                self.list_scroll = max(0, self.list_scroll - WHEEL_STEP)
            elif pos[1] > list_bottom - 18:
                self.list_scroll = min(self._max_scroll(), self.list_scroll + WHEEL_STEP)
            target = self._catalog_palette().arrangement_position_at(
                *self._catalog_point(pos)
            )
            if target is not None and target[0] == self.drag["group"]:
                self.drag["end"] = target[1:]
        elif self.hover is None:
            return
        elif mode == "select":
            self._active_editor_state().select(*self.drag["start"], *self.hover)
        elif mode == "move":
            last = self.drag["last"]
            error = self._active_editor_state().move_selection(
                self.hover[0] - last[0], self.hover[1] - last[1],
            )
            if error:
                self._set_status(error, RED)
            else:
                self.drag["last"] = self.hover
        elif self.hover != self.drag["last"]:
            self.drag["last"] = self.hover
            if mode == "paint":
                self._paint(self.hover)
            else:
                self._erase(self.hover)

    def _paint(self, tile):
        if self.selected is None:
            return
        error = self._artist_layer_error(self.selected, self.selected_layer)
        if error:
            self._set_status(error, RED)
            return
        error = self._active_editor_state().paint(
            self.selected, tile[0], tile[1], self.brush_size, layer=self.selected_layer,
        )
        if error:
            self._set_status(error, RED)

    def _erase(self, tile):
        state = self._active_editor_state()
        for x, y in self._brush_tiles(tile):
            state.erase(x, y)

    def _fill(self, tile):
        if self.selected is None:
            return
        error = self._artist_layer_error(self.selected, self.selected_layer)
        if error:
            self._set_status(error, RED)
            return
        state = self._active_editor_state()
        if state.items[self.selected]["kind"] != "ground":
            self._set_status("Заливка работает только с землёй", RED)
            return
        state.begin_action()
        result = state.fill(self.selected, tile[0], tile[1], layer=self.selected_layer)
        state.end_action()
        if isinstance(result, str):
            self._set_status(result, RED)
        else:
            self._set_status(
                f"Залито клеток: {result}" if result else "Область уже этого вида",
                TEXT_DIM,
            )

    def _brush_tiles(self, tile):
        start = -(self.brush_size // 2)
        tiles = []
        for dx in range(start, start + self.brush_size):
            for dy in range(start, start + self.brush_size):
                if self.state.inside(tile[0] + dx, tile[1] + dy):
                    tiles.append((tile[0] + dx, tile[1] + dy))
        return tiles

    def _tile_at(self, pos):
        grid = self.grid_rect()
        if not grid.collidepoint(pos):
            return None
        x = self.origin_x + (pos[0] - grid.x) // self.zoom
        y = self.origin_y + (pos[1] - grid.y) // self.zoom
        return (x, y) if self.state.inside(x, y) else None

    def _minimap_rect(self):
        if not self.show_minimap:
            return None
        grid = self.grid_rect()
        size = Minimap.DISPLAY_SIZE
        return pygame.Rect(
            grid.right - size - MINI_PAD,
            grid.bottom - size - MINI_PAD,
            size,
            size,
        )

    def _minimap_button_rect(self):
        minimap = self._minimap_rect()
        if minimap is not None:
            return pygame.Rect(
                minimap.right - MINIMAP_BUTTON_SIZE[0] - 6,
                minimap.y + 6,
                *MINIMAP_BUTTON_SIZE,
            )
        grid = self.grid_rect()
        return pygame.Rect(
            grid.right - MINIMAP_BUTTON_SIZE[0] - MINI_PAD,
            grid.bottom - MINIMAP_BUTTON_SIZE[1] - MINI_PAD,
            *MINIMAP_BUTTON_SIZE,
        )

    def _minimap_tile(self, pos, clamp=False):
        rect = self._minimap_rect()
        if rect is None:
            return None
        x = (pos[0] - rect.x) * self.state.map_w // rect.w
        y = (pos[1] - rect.y) * self.state.map_h // rect.h
        if clamp:
            x = max(0, min(x, self.state.map_w - 1))
            y = max(0, min(y, self.state.map_h - 1))
        elif not rect.collidepoint(pos):
            return None
        return x, y

    def _center_view_on(self, tile):
        grid = self.grid_rect()
        self.origin_x = tile[0] - (grid.w // self.zoom) // 2
        self.origin_y = tile[1] - (grid.h // self.zoom) // 2
        self._clamp_origin()

    def _list_top(self):
        biome_tabs_height = 28 if self.section == "map" else 0
        return TOP + LIST_OFFSET + biome_tabs_height + ADD_ITEM_H

    def _palette_settings_rect(self):
        return pygame.Rect(self.panel_w - 174, TOP + 4, 164, 28)

    def _palette_reset_rect(self):
        return pygame.Rect(self.panel_w - 226, TOP + 4, 48, 28)

    def _add_item_rect(self):
        biome_tabs_height = 28 if self.section == "map" else 0
        return pygame.Rect(8, TOP + LIST_OFFSET + biome_tabs_height + 3, self.panel_w - 16, ADD_ITEM_H - 6)

    def _item_dialog_event(self, event):
        result = self.item_dialog.handle_event(event)
        if result == "cancel":
            self.item_dialog = None
        elif isinstance(result, tuple) and result[0] == "save":
            self._save_new_item(result[1])

    def _save_new_item(self, form):
        """Проверяет форму, отправляет на сервер и добавляет предмет в базу. Ошибку показывает в окне."""
        try:
            validate_form(form)
        except ValueError as error:
            self.item_dialog.message = str(error)
            return
        if self.client is None or not self.ensure_login():
            self.item_dialog.message = "Нет входа на сервер: предмет не сохранён"
            return
        try:
            item = self.client.create_item(form)
        except (ServerError, OSError) as error:
            self.item_dialog.message = f"Не сохранено: {error}"
            return
        self.item_dialog = None
        self.equipment_palette = None  # список экипировки перечитается при следующем открытии
        self._set_status(f"Предмет «{item['name']}» добавлен в базу (id {item['id']})", GREEN)

    def _draw_add_item_button(self, screen):
        rect = self._add_item_rect()
        pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(pygame.mouse.get_pos()) else BUTTON_BG, rect, border_radius=4)
        label = self.small.render("+ Добавить предмет", True, TEXT)
        screen.blit(label, label.get_rect(center=rect.center))

    def _list_bottom(self):
        return self.panel_rect().bottom - MINI_PAD

    def _pan_by(self, dx, dy):
        self.origin_x += dx
        self.origin_y += dy
        self._clamp_origin()

    def _set_zoom(self, zoom):
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        self._clamp_origin()

    def _clamp_origin(self):
        grid = self.grid_rect()
        max_x = max(0, self.state.map_w - grid.w // self.zoom)
        max_y = max(0, self.state.map_h - grid.h // self.zoom)
        self.origin_x = max(0, min(self.origin_x, max_x))
        self.origin_y = max(0, min(self.origin_y, max_y))

    def _content_height(self):
        if self.section == "npc":
            return len(self.npc_list) * NPC_ROW_H
        return self._catalog_palette().height

    def _max_scroll(self):
        if self.section == "spawn":
            return 0
        visible = self._list_bottom() - self._list_top()
        return max(0, self._content_height() - visible)

    def _draw_grid(self, screen):
        self.editor_layers[0] = self.state
        grid = self.grid_rect()
        previous_clip = screen.get_clip()
        screen.set_clip(grid)
        screen.fill(EMPTY_CELL, grid)
        z = self.zoom
        ticks = pygame.time.get_ticks()
        x0, y0 = self.origin_x, self.origin_y
        x1 = min(self.state.map_w, x0 + grid.w // z + 2)
        y1 = min(self.state.map_h, y0 + grid.h // z + 2)
        for index, state in enumerate(self.editor_layers):
            alpha = self._layer_alpha(index)
            if alpha == 0:
                continue
            self._draw_editor_layer(screen, state, grid, x0, y0, x1, y1, z, ticks, alpha)
        if self.show_grid and z >= 12:
            for tx in range(x0, x1):
                for ty in range(y0, y1):
                    rect = pygame.Rect(
                        grid.x + (tx - x0) * z, grid.y + (ty - y0) * z, z, z,
                    )
                    pygame.draw.rect(screen, (40, 44, 50), rect, 1)

        mob_alpha = (
            self._layer_alpha(MOB_LAYER_INDEX)
            if MOB_LAYER_INDEX < len(self.editor_layer_visible)
            else 255
        )
        if mob_alpha:
            self._draw_mobs(screen, grid, x0, y0, x1, y1, mob_alpha)
        self._draw_spawns(screen, grid, x0, y0, x1, y1)
        self._draw_selection(screen, grid)
        self._draw_hover(screen, grid)
        screen.set_clip(previous_clip)
        pygame.draw.rect(screen, BORDER, grid, 1)

    def _draw_editor_layer(self, screen, state, grid, x0, y0, x1, y1, zoom, ticks, alpha):
        for tx in range(x0, x1):
            for ty in range(y0, y1):
                rect = pygame.Rect(
                    grid.x + (tx - x0) * zoom, grid.y + (ty - y0) * zoom, zoom, zoom,
                )
                key = state.ground.get((tx, ty))
                if key:
                    self._blit_map_layer(screen, key, rect, zoom, ticks, alpha)
                over = state.overlay.get((tx, ty))
                if over:
                    self._blit_map_layer(screen, over, rect, zoom, ticks, alpha)
        self._draw_map_objects(screen, state, grid, x0, y0, x1, y1, zoom, ticks, True, alpha)
        for tx in range(x0, x1):
            for ty in range(y0, y1):
                rect = pygame.Rect(grid.x + (tx - x0) * zoom, grid.y + (ty - y0) * zoom, zoom, zoom)
                elevation = state.elevation.get((tx, ty))
                if elevation:
                    self._blit_map_layer(screen, elevation, rect, zoom, ticks, alpha)
                relief = state.relief.get((tx, ty))
                if relief:
                    self._blit_map_layer(screen, relief, rect, zoom, ticks, alpha)
                infra = state.infra.get((tx, ty))
                if infra:
                    self._blit_map_layer(screen, infra, rect, zoom, ticks, alpha)
        self._draw_map_objects(screen, state, grid, x0, y0, x1, y1, zoom, ticks, False, alpha)

    def _draw_map_objects(self, screen, state, grid, x0, y0, x1, y1, zoom, ticks, under_elevation, alpha):
        for (ax, ay), key in sorted(state.objects.items(), key=lambda entry: entry[0][1]):
            if not (x0 - 4 <= ax < x1 + 1 and y0 - 6 <= ay < y1 + 1):
                continue
            spec = BIOME_TILE_SPECS.get(key)
            object_is_under = spec is not None and spec.get("render_order") == "under_elevation"
            if object_is_under != under_elevation:
                continue
            img = self._scaled_map_layer(key, zoom, ticks, alpha)
            footprint = self._footprint_rect(key, ax, ay)
            dest = self._object_rect(key, img, footprint)
            if dest.colliderect(grid):
                screen.blit(img, dest)

    def _scaled_map_layer(self, key, zoom, ticks, alpha):
        image = self._scaled_at_time(key, zoom, ticks)
        if alpha >= 255:
            return image
        animation = PALETTE_ANIMATIONS.get(key)
        frame = animation_frame_index(animation, ticks) if animation else 0
        cache_key = (key, zoom, frame, alpha)
        if cache_key not in self.layer_scaled:
            faded = image.copy()
            faded.set_alpha(alpha)
            self.layer_scaled[cache_key] = faded
        return self.layer_scaled[cache_key]

    def _blit_map_layer(self, screen, key, rect, zoom, ticks, alpha):
        if alpha:
            screen.blit(self._scaled_map_layer(key, zoom, ticks, alpha), rect)

    def _draw_selection(self, screen, grid):
        state = self._active_editor_state()
        if state.selection is None:
            return
        left, top, right, bottom = state.selection
        rect = pygame.Rect(
            grid.x + (left - self.origin_x) * self.zoom,
            grid.y + (top - self.origin_y) * self.zoom,
            (right - left + 1) * self.zoom,
            (bottom - top + 1) * self.zoom,
        )
        pygame.draw.rect(screen, SELECT_COLOR, rect, 2)

    def _footprint_rect(self, key, x, y):
        item = self.state.items[key]
        grid = self.grid_rect()
        z = self.zoom
        return pygame.Rect(
            grid.x + (x - self.origin_x) * z,
            grid.y + (y - self.origin_y) * z,
            item["footprint_w"] * z,
            item["footprint_h"] * z,
        )

    def _object_rect(self, key, image, footprint):
        """Ростовые серии и кристаллы выравниваются по нижнему центру видимой части."""
        item = self.state.items[key]
        if item["category"] in SERIES_CATEGORIES or item.get("growth_series") is not None:
            base_x, base_y = series_base(image)
            return image.get_rect(topleft=(footprint.centerx - base_x, footprint.bottom - base_y))
        render_offset = item.get("render_offset_tiles", {})
        if render_offset:
            cell_width = footprint.w / item["footprint_w"]
            cell_height = footprint.h / item["footprint_h"]
            return image.get_rect(midbottom=(
                footprint.centerx + round(render_offset.get("x", 0) * cell_width),
                footprint.bottom + round(render_offset.get("y", 0) * cell_height),
            ))
        return image.get_rect(midbottom=(footprint.centerx, footprint.bottom))

    def _draw_hover(self, screen, grid):
        if self.section == "spawn" and self.hover is not None and not self.menu.is_open():
            hx, hy = self.hover
            tile = pygame.Rect(grid.x + (hx - self.origin_x) * self.zoom, grid.y + (hy - self.origin_y) * self.zoom, self.zoom, self.zoom)
            pygame.draw.rect(screen, HOVER_COLOR, tile, 2)
            return
        if self.section == "npc" and self.hover is not None and self.selected_npc is not None and not self.menu.is_open():
            self._draw_npc_ghost(screen, grid)
            return
        if self.hover is None or self.menu.is_open() or self.tool == "select":
            return
        if self.tool == "stamp":
            self._draw_stamp_ghost(screen, grid)
            return
        if self.tool == "erase" or (self.brush_size > 1 and self.tool == "brush"):
            color = ERASE_HOVER_COLOR if self.tool == "erase" else HOVER_COLOR
            pygame.draw.rect(screen, color, self._tiles_rect(grid, self._brush_tiles(self.hover)), 1)
        if self.tool != "brush" or self.selected is None:
            return
        hx, hy = self.hover
        rect = self._footprint_rect(self.selected, hx, hy)
        img = self._scaled(self.selected, self.zoom).copy()
        img.set_alpha(150)
        screen.blit(img, self._object_rect(self.selected, img, rect))
        pygame.draw.rect(screen, HOVER_COLOR, rect, 2)

    def _ghost(self, key):
        cache_key = (key, self.zoom)
        if cache_key not in self.ghosts:
            image = self._scaled(key, self.zoom).copy()
            image.set_alpha(150)
            self.ghosts[cache_key] = image
        return self.ghosts[cache_key]

    def _draw_stamp_ghost(self, screen, grid):
        hx, hy = self.hover
        for layer in ("ground", "overlay", "elevation", "relief", "infra", "objects"):
            for dx, dy, key in self.stamp.get(layer, ()):
                rect = self._footprint_rect(key, hx + dx, hy + dy)
                image = self._ghost(key)
                if layer == "objects":
                    screen.blit(image, self._object_rect(key, image, rect))
                else:
                    screen.blit(image, rect)
        z = self.zoom
        frame = pygame.Rect(
            grid.x + (hx - self.origin_x) * z,
            grid.y + (hy - self.origin_y) * z,
            self.stamp["w"] * z,
            self.stamp["h"] * z,
        )
        pygame.draw.rect(screen, HOVER_COLOR, frame, 2)

    def _hovered_catalog_key(self):
        """Ключ элемента каталога под курсором или None."""
        x, y = pygame.mouse.get_pos()
        if self.mob_dialog is not None or self.crystal_dialog is not None or not (self._list_top() <= y < self._list_bottom() and x < self.scroll_x):
            return None
        return self._catalog_palette().item_at(x, y - self._list_top() + self.list_scroll)

    def _draw_crystal_button(self, screen):
        found = self._crystal_button(pygame.mouse.get_pos())
        if found is None:
            return
        _key, button = found
        rect = button.move(0, self._list_top() - self.list_scroll)
        pygame.draw.rect(screen, BUTTON_ON, rect, border_radius=4)
        pygame.draw.rect(screen, HOVER_COLOR, rect, 1, border_radius=4)
        for offset in (5, 10, 15):
            pygame.draw.circle(screen, TEXT, (rect.x + offset, rect.centery), 1)

    def _catalog_hover_rect(self, key, mouse_pos):
        palette = self._catalog_palette()
        local_x, local_y = mouse_pos[0], mouse_pos[1] - self._list_top() + self.list_scroll
        for row in palette.rows:
            if row.kind != "block" or not row.top <= local_y < row.top + row.height:
                continue
            for rect, group in row.previews:
                if rect.collidepoint(local_x - BLOCK_X, local_y - row.top - BLOCK_PAD):
                    if key in (group["key"], group.get("primary_key")):
                        return rect.move(
                            BLOCK_X,
                            self._list_top() + row.top + BLOCK_PAD - self.list_scroll,
                        )
            for rect, item in row.cells:
                if item["item_key"] == key:
                    return rect.move(
                        BLOCK_X,
                        self._list_top() + row.top + BLOCK_PAD - self.list_scroll,
                    )
        return None

    def _tooltip_rect(self, box, anchor, viewport):
        if anchor is None:
            return box.clamp(viewport)
        gap = 8
        candidates = (
            pygame.Rect(anchor.right + gap, anchor.top, box.w, box.h),
            pygame.Rect(anchor.left - box.w - gap, anchor.top, box.w, box.h),
            pygame.Rect(anchor.left, anchor.bottom + gap, box.w, box.h),
            pygame.Rect(anchor.left, anchor.top - box.h - gap, box.w, box.h),
        )
        for candidate in candidates:
            if viewport.contains(candidate) and not candidate.colliderect(anchor):
                return candidate
        for candidate in candidates:
            candidate.clamp_ip(viewport)
            if not candidate.colliderect(anchor):
                return candidate
        return box.clamp(viewport)

    def _draw_item_tooltip(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        key = self._hovered_catalog_key()
        if key is None:
            return
        item_key = key
        item = self.state.items.get(item_key)
        if item is None:
            item_key = next(
                (
                    entry[2]
                    for entry in self._catalog_palette().compound_entries(key)
                    if entry[2] in self.state.items
                ),
                None,
            )
            if item_key is None:
                return
            item = self.state.items[item_key]
        biome_spec = BIOME_TILE_SPECS.get(item_key)
        title = (
            f"Анимация · {key.rsplit('_', 1)[-1]}"
            if item_key != key
            else biome_spec.get("display_name", key) if biome_spec else key
        )
        head = self.font.render(title, True, TEXT)
        if biome_spec is not None:
            placement = "объект · ставить поверх земли" if biome_spec["layer"] == "objects" else f"тайл · слой {biome_spec['layer']}"
            source_layers = biome_spec.get("tiled_layers", [])
            source = f" · Tiled: {source_layers[0]}" if source_layers else ""
            if len(source_layers) > 1:
                source += f" +{len(source_layers) - 1}"
            sub = self.small.render(f"{placement} · {item['category']}{source}", True, TEXT_DIM)
        elif key in self.partial_masks:
            sub = self.small.render(f"{item['kind']} · {item['category']} · частично (маска)", True, AMBER)
        elif item.get("blocks"):
            sub = self.small.render(f"{item['kind']} · {item['category']} · непроходим", True, BLOCKED_TEXT)
        else:
            sub = self.small.render(f"{item['kind']} · {item['category']} · проходим", True, TEXT_DIM)
        box = pygame.Rect(0, 0, max(head.get_width(), sub.get_width()) + 16, head.get_height() + sub.get_height() + 10)
        viewport = pygame.Rect(
            0,
            self._list_top(),
            self.panel_w,
            self._list_bottom() - self._list_top(),
        )
        anchor = self._catalog_hover_rect(key, mouse_pos)
        box = self._tooltip_rect(box, anchor, viewport)
        pygame.draw.rect(screen, PANEL_BG, box, border_radius=4)
        pygame.draw.rect(screen, HOVER_COLOR, box, 1, border_radius=4)
        screen.blit(head, (box.x + 8, box.y + 5))
        screen.blit(sub, (box.x + 8, box.y + 5 + head.get_height()))

    def _draw_palette_context(self, screen):
        context = self.palette_context
        rect = context["rect"]
        item = self.state.items[context["key"]]
        rule = context["rules"][context["key"]]
        pygame.draw.rect(screen, PANEL_BG, rect, border_radius=6)
        pygame.draw.rect(screen, HOVER_COLOR, rect, 2, border_radius=6)
        title = item.get("name", context["key"])[:25]
        screen.blit(
            self.font.render(title, True, TEXT),
            (rect.x + 10, rect.y + 8),
        )
        if len(context["keys"]) > 1:
            count = self.small.render(
                f"Общие настройки · {len(context['keys'])} тайлов",
                True,
                TEXT_DIM,
            )
            screen.blit(count, (rect.x + 10, rect.y + 25))
        layer_values = {
            context["rules"][key]["editor_layer"]
            for key in context["keys"]
        }
        layer_value = (
            str(next(iter(layer_values)))
            if len(layer_values) == 1
            else "Разные"
        )
        values = (
            ("Проходимость", "Непроходим" if rule["blocks"] else "Проходим"),
            ("Слой", layer_value),
            ("Роль генератора", "Декор" if rule["generator_role"] == "random_decor" else "Обычный"),
            ("Группа", rule["palette_group"]),
            ("Порядок в группе", str(rule["palette_order"] + 1)),
        )
        for index, (label, value) in enumerate(values):
            y = rect.y + 38 + index * 36
            row = pygame.Rect(rect.x + 8, y, rect.w - 16, 32)
            pygame.draw.rect(screen, BUTTON_BG, row, border_radius=4)
            pygame.draw.rect(screen, BORDER, row, 1, border_radius=4)
            screen.blit(self.small.render(label, True, TEXT_DIM), (row.x + 8, row.y + 2))
            display_value = value
            while self.small.size(display_value)[0] > row.w // 2 and len(display_value) > 4:
                display_value = display_value[:-2] + "…"
            rendered = self.small.render(display_value, True, TEXT)
            screen.blit(rendered, rendered.get_rect(midright=(row.right - 8, row.centery)))
            if index in (1, 3, 4):
                screen.blit(self.small.render("−      +", True, TEXT_DIM), (row.right - 42, row.y + 2))
        if context["confirm"] is not None:
            message = (
                "Применить изменения?"
                if context["confirm"] == "apply"
                else "Отменить изменения?"
            )
            screen.blit(
                self.small.render(message, True, TEXT),
                (rect.x + 10, rect.y + 219),
            )
            labels = ("Подтвердить", "Назад")
        elif self._palette_context_dirty():
            labels = ("Применить", "Отмена")
        else:
            labels = ("Закрыть", "")
        for index, label in enumerate(labels):
            if not label:
                continue
            button = pygame.Rect(
                rect.x + 8 + index * (rect.w // 2),
                rect.y + 244,
                rect.w // 2 - 12,
                38,
            )
            pygame.draw.rect(screen, BUTTON_BG, button, border_radius=4)
            pygame.draw.rect(screen, BORDER, button, 1, border_radius=4)
            text = self.small.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=button.center))

    def _draw_panel(self, screen):
        panel = self.panel_rect()
        screen.fill(PANEL_BG, panel)
        screen.blit(self.title.render("Каталог", True, TEXT), (12, panel.y + 10))
        settings_rect = self._palette_settings_rect()
        settings_label = "Применить палитру" if self.palette_editing else "Настройка палитры"
        pygame.draw.rect(
            screen,
            BUTTON_ON if self.palette_editing else BUTTON_BG,
            settings_rect,
            border_radius=4,
        )
        pygame.draw.rect(screen, BORDER, settings_rect, 1, border_radius=4)
        settings_text = self.small.render(settings_label, True, TEXT)
        screen.blit(settings_text, settings_text.get_rect(center=settings_rect.center))
        if self.palette_editing:
            reset_rect = self._palette_reset_rect()
            pygame.draw.rect(screen, BUTTON_BG, reset_rect, border_radius=4)
            pygame.draw.rect(screen, BORDER, reset_rect, 1, border_radius=4)
            reset_text = self.small.render("Сброс", True, TEXT)
            screen.blit(reset_text, reset_text.get_rect(center=reset_rect.center))
        self._draw_tabs(screen)
        self._draw_add_item_button(screen)
        if self.section == "npc":
            screen.blit(self.small.render(f"{len(self.npc_list)} NPC", True, TEXT_DIM), (92, panel.y + 14))
            self._draw_npc_list(screen)
        elif self.section == "spawn":
            screen.blit(self.small.render(f"точек: {len(self.state.spawns)}", True, TEXT_DIM), (92, panel.y + 14))
            self._draw_spawn_row(screen)
        else:
            palette = self._catalog_palette()
            if self.section == "equip":
                screen.blit(self.small.render(f"{palette.count} предметов", True, TEXT_DIM), (92, panel.y + 14))
            elif self.section == "animals":
                screen.blit(self.small.render(f"{len(self.animal_catalog)} животных", True, TEXT_DIM), (92, panel.y + 14))
            else:
                screen.blit(self.small.render(f"{len(self.biome_catalogs[self.biome])} элементов", True, TEXT_DIM), (92, panel.y + 14))
            list_rect = pygame.Rect(0, self._list_top(), self.panel_w, self._list_bottom() - self._list_top())
            if self.section == "equip":
                palette.draw(
                    screen, list_rect, self.list_scroll, self.equipment_selected,
                    hovered=self._hovered_catalog_key(), ticks=pygame.time.get_ticks(),
                )
            else:
                arrangement_drag = None
                if self.drag and self.drag["mode"] == "palette_layout":
                    content_point = self._catalog_point(self.drag["end"])
                    arrangement_drag = (
                        self.drag["group"],
                        self.drag["key"],
                        palette.arrangement_position_at(*content_point),
                    )
                elif self.drag and self.drag["mode"] == "palette_select":
                    content_point = self._catalog_point(
                        pygame.mouse.get_pos()
                    )
                    arrangement_drag = (
                        self.drag["group"],
                        None,
                        palette.arrangement_position_at(*content_point),
                    )
                arrangement_marquee = None
                if self.drag and self.drag["mode"] == "palette_select":
                    arrangement_marquee = (
                        self.drag["group"],
                        self.drag["start"],
                        self.drag["end"],
                    )
                palette.draw(
                    screen, list_rect, self.list_scroll, self.selected, self._marquee(),
                    hovered=self._hovered_catalog_key(), ticks=pygame.time.get_ticks(),
                    arrangement_drag=arrangement_drag,
                    arrangement_selection=self.palette_selected_keys,
                    arrangement_marquee=arrangement_marquee,
                )
                self._draw_crystal_button(screen)
                self._draw_item_tooltip(screen)
        if self._max_scroll():
            track = self._scrollbar_track()
            thumb = self._scroll_thumb()
            pygame.draw.rect(screen, (60, 64, 72), track, border_radius=4)
            pygame.draw.rect(screen, (150, 156, 166), thumb, border_radius=4)
        minimap = self._minimap_rect()
        if minimap is not None:
            self.minimap.refresh(
                self.state,
                self.editor_layers,
                self.editor_layer_visible,
                [self._layer_alpha(index) for index in range(len(self.editor_layers))],
            )
            grid = self.grid_rect()
            view_w = min(self.state.map_w - self.origin_x, grid.w // self.zoom)
            view_h = min(self.state.map_h - self.origin_y, grid.h // self.zoom)
            self.minimap.draw(
                screen,
                minimap,
                (self.origin_x, self.origin_y, view_w, view_h),
                (self.state.map_w, self.state.map_h),
            )
        button = self._minimap_button_rect()
        pygame.draw.rect(screen, BUTTON_ON, button, border_radius=4)
        pygame.draw.rect(screen, BORDER, button, 1, border_radius=4)
        label = "Скрыть" if self.show_minimap else "Миникарта"
        text = self.small.render(label, True, TEXT)
        screen.blit(text, text.get_rect(center=button.center))
        pygame.draw.line(screen, BORDER, (self.panel_w - 1, panel.y), (self.panel_w - 1, panel.bottom))

    def _draw_status(self, screen):
        bar = pygame.Rect(0, settings.HEIGHT - STATUS_H, settings.WIDTH, STATUS_H)
        screen.fill(PANEL_BG, bar)
        pygame.draw.line(screen, BORDER, (0, bar.y), (bar.right, bar.y))
        help_text = (
            "ЛКМ — рисовать/выбрать · ПКМ — стереть · B/F/V — инструменты · [ ] — кисть · "
            "G — сетка · M — миникарта · Ctrl+S — сохранить · Esc — выход"
        )
        screen.blit(self.small.render(help_text, True, TEXT_DIM), (14, bar.y + 6))
        screen.blit(self.font.render(self.status, True, self.status_color), (14, bar.y + 24))
        size_text = f"{self.state.map_w}×{self.state.map_h} · {self.zoom}px"
        screen.blit(self.small.render(size_text, True, TEXT_DIM), (bar.right - 170, bar.y + 6))
        if self._dirty():
            screen.blit(self.font.render("● не сохранено", True, AMBER), (bar.right - 170, bar.y + 24))

    def _native(self, key):
        """Изображение элемента в мировых пикселях (32 px на тайл), с теми же масштабами, что в игре."""
        if key not in self.natives:
            item = self.state.items[key]
            image = self._asset_sheet(item["asset"])
            if item["category"] in ("tree", "old_tree") and key in MAP_TREE_SHEETS:
                frame_w, frame_h = MAP_TREE_SHEETS[key]
                frame = image.subsurface(pygame.Rect(0, 0, frame_w, frame_h)).copy()
                image = _scale_rgba(frame, (round(frame_w * MAP_TREE_SCALE), round(frame_h * MAP_TREE_SCALE)))
            elif key in BIOME_TILE_SPECS:
                spec = BIOME_TILE_SPECS[key]
                animation = PALETTE_ANIMATIONS.get(key)
                if spec.get("representation") == "sprite" and animation is not None:
                    frame_w, frame_h = animation["frame"]
                    image = image.subsurface(pygame.Rect(0, 0, frame_w, frame_h)).copy()
                else:
                    image = rocky_tile_frame(key, image).copy()
            elif item["category"] == "animal":
                animation = PALETTE_ANIMATIONS.get(key)
                if animation is not None:
                    frame_w, frame_h = animation["frame"]
                    image = image.subsurface(pygame.Rect(0, 0, frame_w, frame_h)).copy()
            elif item["category"] in ("stump", "log"):
                size = (round(image.get_width() * MAP_PROP_SCALE), round(image.get_height() * MAP_PROP_SCALE))
                image = _scale_rgba(image, size)
            self.natives[key] = image
        return self.natives[key]

    def _asset_sheet(self, asset):
        if not hasattr(self, "asset_sheets"):
            self.asset_sheets = {}
        if asset not in self.asset_sheets:
            self.asset_sheets[asset] = pygame.image.load(str(MAP_DIR / asset)).convert_alpha()
        return self.asset_sheets[asset]

    def _scaled_at_time(self, key, zoom, ticks):
        animation = PALETTE_ANIMATIONS.get(key)
        frame = animation_frame_index(animation, ticks) if animation else 0
        return self._scaled(key, zoom, frame)

    def _scaled(self, key, zoom, frame=0):
        cache_key = (key, zoom, frame)
        if cache_key not in self.scaled:
            if frame and key in BIOME_TILE_SPECS:
                spec = BIOME_TILE_SPECS[key]
                sheet = self._asset_sheet(self.state.items[key]["asset"])
                if spec.get("representation") == "sprite":
                    animation = PALETTE_ANIMATIONS.get(key)
                    if animation is None:
                        native = sheet
                    else:
                        frame_w, frame_h = animation["frame"]
                        column, line = frame % animation["cols"], frame // animation["cols"]
                        native = sheet.subsurface(
                            pygame.Rect(column * frame_w, line * frame_h, frame_w, frame_h)
                        )
                else:
                    native = rocky_tile_frame(key, sheet, frame)
            else:
                native = self._native(key)
            factor = zoom / TILE
            size = (max(1, round(native.get_width() * factor)), max(1, round(native.get_height() * factor)))
            self.scaled[cache_key] = _scale_rgba(native, size)
        return self.scaled[cache_key]

    def _thumb(self, key):
        if key not in self.thumbs:
            native = self._native(key)
            factor = min(THUMB / native.get_width(), THUMB / native.get_height())
            size = (max(1, round(native.get_width() * factor)), max(1, round(native.get_height() * factor)))
            self.thumbs[key] = _scale_rgba(native, size)
        return self.thumbs[key]
