"""Редактор карт в духе Heroes 3: строка меню, инструменты, каталог слева, сетка карты справа, сохранение и применение."""
from pathlib import Path

import pygame

from client import map_drafts
from client.map_editor_seed import build_tower_seed_cells, decode_tiles
from client.map_editor_state import MapEditorState
from client.network import ServerError
from core import mob_modes, settings
from core.game_modes import DEFAULT_MODE, GAME_MODES, is_mode, mode_name
from core.map_catalog import DEFAULT_MAP_SIZE
from core.npc_catalog import NPC_FRAME, NPC_FRAMES_PER_ROW, NPC_ROW_DOWN, npc_catalog, sheet_path
from core.tile_mask import FREE, MASK_SIDE, load_partial_masks, save_partial_masks
from scenes.map_editor_ui import BUTTON_BG, BUTTON_ON, MENU_H, TOOL_H, DraftList, MaskDialog, Minimap, MenuBar, MobParamsDialog, SaveDialog, SizePicker, TextPrompt, ToolBar, WorldPicker
from core.item_form import validate_form
from scenes.item_form_dialog import ItemFormDialog
from scenes.map_equipment_palette import EquipmentPalette
from scenes.map_palette import PALETTE_TILE_MAX, PALETTE_TILE_MIN, PALETTE_TILE_STEP, Palette
from scenes.world_map_scene import (
    MAP_PROP_SCALE,
    MAP_TREE_COLUMNS,
    MAP_TREE_FRAME_MS,
    MAP_TREE_FRAMES,
    MAP_TREE_FRAMES_PER_ROW,
    MAP_TREE_SCALE,
    MAP_TREE_SHEETS,
    build_mountain_roles,
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
STATUS_H = 50
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
SECTION_TABS = [("map", "Земля и объекты", 130), ("npc", "NPC", 90), ("spawn", "Спаун", 90), ("equip", "Экипировка", 120)]
NAME_MAX = 64
MAP_SIZE_PRESETS = [
    (64, 64, "небольшая"),
    (125, 125, "как башня"),
    (256, 256, "средняя"),
    (512, 256, "как мир 1"),
]
TOOLS = [("brush", "Кисть", "B"), ("fill", "Заливка", "F"), ("select", "Выделение", "V"), ("stamp", "Вставка", "Ctrl+V")]
TOOL_KEYS = {pygame.K_b: "brush", pygame.K_f: "fill", pygame.K_v: "select"}
CTRL_KEYS = {
    pygame.K_s: "save", pygame.K_n: "new",
    pygame.K_l: "drafts", pygame.K_z: "undo", pygame.K_y: "redo", pygame.K_d: "deselect",
    pygame.K_c: "copy", pygame.K_x: "cut", pygame.K_v: "paste",
}
PLAIN_KEYS = {
    pygame.K_g: "grid", pygame.K_m: "minimap", pygame.K_F2: "rename", pygame.K_DELETE: "delete", pygame.K_x: "mask",
    pygame.K_n: "npc",
}
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
            "npc": self.toggle_npc_section,
            "zoom_in": lambda: self._set_zoom(self.zoom + 4),
            "zoom_out": lambda: self._set_zoom(self.zoom - 4),
        }
        self.state = MapEditorState(self.catalog, [], DEFAULT_MAP_SIZE, DEFAULT_MAP_SIZE)
        self.has_map = False
        self.draft_id = None
        self.selected = self.catalog[0]["item_key"] if self.catalog else None
        self.tool = "brush"
        self.brush_size = 1
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
        self.close_warned = False
        self.pending_action = None
        self.prompt = None
        self.draft_list = None
        self.save_dialog = None
        self.size_picker = None
        self.world_picker = None
        self.mask_dialog = None
        self.partial_masks = load_partial_masks()
        self.natives = {}
        self.scaled = {}
        self.thumbs = {}
        self.palette = Palette(
            self.catalog, MAP_DIR, self.font, self.small, max_panel=settings.WIDTH // 2, animations=TREE_ANIMATIONS
        )
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
        return pygame.Rect(self.panel_w, TOP, settings.WIDTH - self.panel_w, settings.HEIGHT - STATUS_H - TOP)

    def panel_rect(self):
        return pygame.Rect(0, TOP, self.panel_w, settings.HEIGHT - STATUS_H - TOP)

    def handle_event(self, event):
        """Возвращает True, когда редактор нужно закрыть."""
        if event.type == pygame.QUIT:
            return self._request_close()
        if self.prompt is not None:
            if event.type == pygame.KEYDOWN:
                self._prompt_key(event)
            return False
        if self.save_dialog is not None:
            self._save_dialog_event(event)
            return False
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
            self._wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            return self._mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_up()
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_move(event)
        return False

    def draw(self, screen):
        screen.fill(BG)
        if self.has_map:
            self._draw_grid(screen)
            self._draw_panel(screen)
        else:
            self._draw_welcome(screen)
        self._draw_status(screen)
        if self.has_map:
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
        if self.item_dialog is not None:
            self.item_dialog.draw(screen)
        self._draw_toast(screen)

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
                command = CTRL_KEYS.get(event.key)
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
        return self.state.dirty or self.name_dirty

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
        state = self.state
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
                {"id": "size", "label": f"Размер {state.map_w}×{state.map_h} (задаётся при создании карты)", "enabled": False},
            ]),
        ]

    def new_map(self):
        if (self.state.ground or self.state.overlay or self.state.objects or self.name_dirty) and not self._confirmed(
            "new", "Очистить карту? Нажмите ещё раз, чтобы стереть всё на карте (сохранённые черновики не меняются)"
        ):
            return
        self.size_picker = SizePicker(self.font, self.small, MAP_SIZE_PRESETS, GAME_MODES, self.mode)
        self._set_status("Выберите режим и размер новой карты", TEXT_DIM)

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
        self.has_map = True
        self.mob_settings_cache = {}
        self._detach_draft()
        self.minimap = Minimap()
        self.drag = None
        self._set_status(f"Новая карта {map_w}×{map_h}, режим «{mode_name(self.mode)}». Сохраните черновик (Ctrl+S), чтобы задать название", TEXT_DIM)

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
        mountains = decode_tiles(terrain["tiles"].get("mountain", []))
        cells = build_tower_seed_cells(
            terrain, self.state.items, self.state.map_w, self.state.map_h, build_mountain_roles(mountains)
        )
        if not self.has_map:
            self.state = MapEditorState(self.catalog, [], self.state.map_w, self.state.map_h)
        self._detach_draft()
        self.mode = DEFAULT_MODE
        self.state.replace_cells(cells)
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
        result = self.save_dialog.handle_event(event)
        if result is None:
            return
        if result == "cancel":
            self._close_save_dialog()
            self._set_status("Сохранение отменено", TEXT_DIM)
            return
        _, name, draft_id = result
        error = self._write_draft(name, draft_id)
        if error is None:
            self._close_save_dialog()
        else:
            self.save_dialog.message = error

    def _close_save_dialog(self):
        self.save_dialog = None
        pygame.key.stop_text_input()

    def _write_draft(self, name, draft_id):
        """Сохраняет карту в локальный черновик. Возвращает текст ошибки или None при успехе."""
        try:
            saved = map_drafts.save_draft(
                name, self.state.to_cells(), self.state.map_w, self.state.map_h, draft_id,
                mode=self.mode, mobs=self.state.to_mobs(), spawns=self.state.to_spawns(),
            )
        except map_drafts.DraftError as error:
            return str(error)
        self.state.name = saved["name"]
        self.draft_id = saved["id"]
        self.server_map = (saved.get("server_map") or {}).get("saved_id")
        self.state.mark_saved()
        self.name_dirty = False
        self.close_warned = False
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
        self.state = MapEditorState(self.catalog, draft["cells"], draft["map_w"], draft["map_h"])
        self.state.name = draft["name"]
        self.state.load_mobs(draft.get("mobs", []))
        self.state.load_spawns(draft.get("spawns", []))
        self.draft_id = draft["id"]
        self.server_map = (draft.get("server_map") or {}).get("saved_id")
        self.has_map = True
        self.mode = draft.get("mode") if is_mode(draft.get("mode")) else DEFAULT_MODE
        self.mob_settings_cache = {}
        self.minimap = Minimap()
        self.name_dirty = False
        self.close_warned = False
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
                self.state.to_cells(), self.state.map_w, self.state.map_h, self.state.name,
                self.mode, mobs=self.state.to_mobs(), saved_id=self.server_map, spawns=self.state.to_spawns(),
            )
        except ServerError as error:
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
            published = self.client.publish_map(
                self.state.to_cells(), self.state.map_w, self.state.map_h, self.state.name, world["id"],
                mobs=self.state.to_mobs(), mode=self.mode, spawns=self.state.to_spawns(), saved_id=self.server_map,
            )
        except ServerError as error:
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
        if self.state.undo():
            self._set_status("Действие отменено", TEXT_DIM)

    def redo(self):
        if self.state.redo():
            self._set_status("Действие повторено", TEXT_DIM)

    def delete_selection(self):
        if self.state.selection is None:
            return
        self.state.begin_action()
        count = self.state.delete_selection()
        self.state.end_action()
        self._set_status(f"Удалено элементов: {count}", TEXT_DIM)

    def deselect(self):
        self.state.clear_selection()

    def copy_selection(self):
        stamp = self.state.copy_selection()
        if stamp is None:
            self._set_status("Нечего копировать: выделите область инструментом «Выделение» (V)", AMBER)
            return False
        self.stamp = stamp
        count = len(stamp["ground"]) + len(stamp["overlay"]) + len(stamp["objects"])
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
        self.state.begin_action()
        error = self.state.paste(self.stamp, tile[0], tile[1])
        self.state.end_action()
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
            "npc": "Раздел NPC: выберите врага в списке. Клик по клетке ставит его на карту",
            "spawn": "Спаун: клик по клетке ставит или убирает точку появления игрока. ПКМ — убрать",
            "equip": "Экипировка: предметы по слотам. Ctrl + колесо — размер иконок",
        }
        self._set_status(messages.get(section, "Выберите элемент слева и рисуйте на карте"), TEXT_DIM)

    def _catalog_palette(self):
        """Палитра, которую показывает каталог сейчас: объекты карты или экипировка."""
        if self.section == "equip":
            self._ensure_equipment_palette()
            return self.equipment_palette
        return self.palette

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
        self.state.begin_action()
        removed = self.state.erase_mob(tile[0], tile[1])
        self.state.end_action()
        if removed:
            self._set_status(f"Бес убран с ({tile[0]}, {tile[1]}). Всего на карте: {len(self.state.mobs)}", TEXT_DIM)

    def _draw_mobs(self, screen, grid, x0, y0, x1, y1):
        z = self.zoom
        for (mx, my), kind in self.state.mobs.items():
            if not (x0 <= mx < x1 and y0 <= my < y1):
                continue
            image = self._npc_sprite(kind, z * 2)
            if image is None:
                continue
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
        if self._dirty() and not self.close_warned:
            self.close_warned = True
            self._set_status("Есть несохранённые изменения. Ctrl+S — сохранить, ещё раз Esc — выйти без сохранения", AMBER)
            return False
        return True

    def _key(self, event):
        ctrl = event.mod & pygame.KMOD_CTRL
        shift = event.mod & pygame.KMOD_SHIFT
        if event.key == pygame.K_ESCAPE:
            if self.menu.is_open():
                self.menu.close()
                return False
            if self.tool == "stamp":
                self.tool = "brush"
                return False
            if self.state.selection is not None:
                self.deselect()
                return False
            return self._command("exit")
        if ctrl:
            command = "redo" if event.key == pygame.K_z and shift else CTRL_KEYS.get(event.key)
            return self._command(command) if command else False
        if event.key in TOOL_KEYS:
            self.tool = TOOL_KEYS[event.key]
        elif event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            step = -1 if event.key == pygame.K_LEFTBRACKET else 1
            self.brush_size = max(1, min(MAX_BRUSH, self.brush_size + step))
        elif event.key in PLAIN_KEYS:
            return self._command(PLAIN_KEYS[event.key])
        elif event.key in PAN_KEYS:
            self._pan_by(*PAN_KEYS[event.key])
        elif event.key in ZOOM_KEYS:
            self._set_zoom(self.zoom + ZOOM_KEYS[event.key])
        return False

    def _wheel(self, steps):
        if self.panel_rect().collidepoint(pygame.mouse.get_pos()):
            if pygame.key.get_mods() & pygame.KMOD_CTRL:
                self._palette_zoom(self._catalog_palette().tile + PALETTE_TILE_STEP * steps)
            else:
                self.list_scroll = max(0, min(self.list_scroll - steps * WHEEL_STEP, self._max_scroll()))
        else:
            self._set_zoom(self.zoom + 4 * steps)

    def _palette_zoom(self, tile):
        palette = self._catalog_palette()
        tile = max(PALETTE_TILE_MIN, min(PALETTE_TILE_MAX, tile))
        if tile == palette.tile:
            return
        old_max = self._max_scroll()
        ratio = self.list_scroll / old_max if old_max else 0
        palette.set_tile(tile)
        self._clamp_origin()
        self.list_scroll = min(self._max_scroll(), round(ratio * self._max_scroll()))
        self._set_status(f"Каталог: тайлы {tile} px (Ctrl + колесо)", TEXT_DIM)

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
            self._grid_primary(tile)
        elif event.button == 3:
            self._grid_secondary(tile)
        return False

    def _panel_down(self, event):
        if event.button != 1:
            return
        pos = event.pos
        for section, _label, rect in self._tab_rects():
            if rect.collidepoint(pos):
                self._set_section(section)
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
            key = self._catalog_palette().item_at(*point)
            if key is not None:
                self.selected = key
                self.tool = "brush"
                item = self.state.items[key]
                self._set_status(f"Выбрано: {key} · {item['category']} · обведите несколько тайлов, чтобы взять кусок", TEXT_DIM)
                self.drag = {"mode": "catalog", "start": point, "end": point}

    def _catalog_point(self, pos):
        return pos[0], pos[1] - self._list_top() + self.list_scroll

    def _marquee(self):
        if self.drag and self.drag["mode"] == "catalog" and self.drag["end"] != self.drag["start"]:
            return self.drag["start"], self.drag["end"]
        return None

    def _finish_catalog_drag(self):
        entries = self.palette.stamp_entries(self.drag["start"], self.drag["end"])
        if len(entries) < 2:
            return
        stamp = self.state.make_stamp([(dx, dy, key) for key, dx, dy in entries])
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

    def _grid_primary(self, tile):
        if self.section == "spawn":
            self._toggle_spawn(tile)
            return
        if self.section == "npc":
            self._place_mob(tile)
            return
        if self.tool == "stamp":
            self._place_stamp(tile)
        elif self.tool == "select":
            if self.state.in_selection(*tile):
                self.state.begin_action()
                self.drag = {"mode": "move", "last": tile}
            else:
                self.state.select(tile[0], tile[1], tile[0], tile[1])
                self.drag = {"mode": "select", "start": tile}
        elif self.tool == "fill":
            self._fill(tile)
        else:
            self.state.begin_action()
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
        self.state.begin_action()
        self.drag = {"mode": "erase", "last": tile}
        self._erase(tile)

    def _mouse_up(self):
        if self.drag and self.drag["mode"] in ("paint", "erase", "move"):
            self.state.end_action()
        elif self.drag and self.drag["mode"] == "catalog":
            self._finish_catalog_drag()
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
        elif self.hover is None:
            return
        elif mode == "select":
            self.state.select(*self.drag["start"], *self.hover)
        elif mode == "move":
            last = self.drag["last"]
            error = self.state.move_selection(self.hover[0] - last[0], self.hover[1] - last[1])
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
        error = self.state.paint(self.selected, tile[0], tile[1], self.brush_size)
        if error:
            self._set_status(error, RED)

    def _erase(self, tile):
        for x, y in self._brush_tiles(tile):
            self.state.erase(x, y)

    def _fill(self, tile):
        if self.selected is None:
            return
        if self.state.items[self.selected]["kind"] != "ground":
            self._set_status("Заливка работает только с землёй", RED)
            return
        self.state.begin_action()
        count = self.state.fill(self.selected, tile[0], tile[1])
        self.state.end_action()
        self._set_status(f"Залито клеток: {count}" if count else "Область уже этого вида", TEXT_DIM)

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
        panel = self.panel_rect()
        return pygame.Rect(
            (self.panel_w - self.state.map_w) // 2,
            panel.bottom - self.state.map_h - MINI_PAD,
            self.state.map_w,
            self.state.map_h,
        )

    def _minimap_tile(self, pos, clamp=False):
        rect = self._minimap_rect()
        if rect is None:
            return None
        x, y = pos[0] - rect.x, pos[1] - rect.y
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
        return TOP + LIST_OFFSET + ADD_ITEM_H

    def _add_item_rect(self):
        return pygame.Rect(8, TOP + LIST_OFFSET + 3, self.panel_w - 16, ADD_ITEM_H - 6)

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
        minimap = self._minimap_rect()
        return minimap.y - MINI_PAD if minimap is not None else self.panel_rect().bottom - MINI_PAD

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
        grid = self.grid_rect()
        previous_clip = screen.get_clip()
        screen.set_clip(grid)
        z = self.zoom
        x0, y0 = self.origin_x, self.origin_y
        x1 = min(self.state.map_w, x0 + grid.w // z + 2)
        y1 = min(self.state.map_h, y0 + grid.h // z + 2)
        for tx in range(x0, x1):
            for ty in range(y0, y1):
                rect = pygame.Rect(grid.x + (tx - x0) * z, grid.y + (ty - y0) * z, z, z)
                key = self.state.ground.get((tx, ty))
                if key:
                    screen.blit(self._scaled(key, z), rect)
                else:
                    screen.fill(EMPTY_CELL, rect)
                over = self.state.overlay.get((tx, ty))
                if over:
                    screen.blit(self._scaled(over, z), rect)
                if self.show_grid and z >= 12:
                    pygame.draw.rect(screen, (40, 44, 50), rect, 1)
        for (ax, ay), key in sorted(self.state.objects.items(), key=lambda entry: entry[0][1]):
            if not (x0 - 4 <= ax < x1 + 1 and y0 - 6 <= ay < y1 + 1):
                continue
            img = self._scaled(key, z)
            footprint = self._footprint_rect(key, ax, ay)
            dest = img.get_rect(midbottom=(footprint.centerx, footprint.bottom))
            if dest.colliderect(grid):
                screen.blit(img, dest)
        self._draw_mobs(screen, grid, x0, y0, x1, y1)
        self._draw_spawns(screen, grid, x0, y0, x1, y1)
        self._draw_selection(screen, grid)
        self._draw_hover(screen, grid)
        screen.set_clip(previous_clip)
        pygame.draw.rect(screen, BORDER, grid, 1)

    def _draw_selection(self, screen, grid):
        if self.state.selection is None:
            return
        left, top, right, bottom = self.state.selection
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
        if self.brush_size > 1 and self.tool == "brush":
            tiles = self._brush_tiles(self.hover)
            xs = [tile[0] for tile in tiles]
            ys = [tile[1] for tile in tiles]
            rect = pygame.Rect(
                grid.x + (min(xs) - self.origin_x) * self.zoom,
                grid.y + (min(ys) - self.origin_y) * self.zoom,
                (max(xs) - min(xs) + 1) * self.zoom,
                (max(ys) - min(ys) + 1) * self.zoom,
            )
            pygame.draw.rect(screen, HOVER_COLOR, rect, 1)
        if self.tool != "brush" or self.selected is None:
            return
        hx, hy = self.hover
        rect = self._footprint_rect(self.selected, hx, hy)
        img = self._scaled(self.selected, self.zoom).copy()
        img.set_alpha(150)
        screen.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom)))
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
        for layer in ("ground", "overlay", "objects"):
            for dx, dy, key in self.stamp[layer]:
                rect = self._footprint_rect(key, hx + dx, hy + dy)
                image = self._ghost(key)
                if layer == "objects":
                    screen.blit(image, image.get_rect(midbottom=(rect.centerx, rect.bottom)))
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
        if self.mob_dialog is not None or not (self._list_top() <= y < self._list_bottom() and x < self.scroll_x):
            return None
        return self._catalog_palette().item_at(x, y - self._list_top() + self.list_scroll)

    def _draw_item_tooltip(self, screen):
        x, y = pygame.mouse.get_pos()
        key = self._hovered_catalog_key()
        if key is None:
            return
        item = self.state.items[key]
        head = self.font.render(key, True, TEXT)
        if key in self.partial_masks:
            sub = self.small.render(f"{item['kind']} · {item['category']} · частично (маска)", True, AMBER)
        elif item.get("blocks"):
            sub = self.small.render(f"{item['kind']} · {item['category']} · непроходим", True, BLOCKED_TEXT)
        else:
            sub = self.small.render(f"{item['kind']} · {item['category']} · проходим", True, TEXT_DIM)
        box = pygame.Rect(0, 0, max(head.get_width(), sub.get_width()) + 16, head.get_height() + sub.get_height() + 10)
        box.topleft = (x + 16, y + 16)
        box.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, PANEL_BG, box, border_radius=4)
        pygame.draw.rect(screen, HOVER_COLOR, box, 1, border_radius=4)
        screen.blit(head, (box.x + 8, box.y + 5))
        screen.blit(sub, (box.x + 8, box.y + 5 + head.get_height()))

    def _draw_panel(self, screen):
        panel = self.panel_rect()
        screen.fill(PANEL_BG, panel)
        screen.blit(self.title.render("Каталог", True, TEXT), (12, panel.y + 10))
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
            else:
                screen.blit(self.small.render(f"{len(self.catalog)} элементов", True, TEXT_DIM), (92, panel.y + 14))
            list_rect = pygame.Rect(0, self._list_top(), self.panel_w, self._list_bottom() - self._list_top())
            if self.section == "equip":
                palette.draw(
                    screen, list_rect, self.list_scroll, self.equipment_selected,
                    hovered=self._hovered_catalog_key(), ticks=pygame.time.get_ticks(),
                )
            else:
                palette.draw(
                    screen, list_rect, self.list_scroll, self.selected, self._marquee(),
                    hovered=self._hovered_catalog_key(), ticks=pygame.time.get_ticks(),
                )
                self._draw_item_tooltip(screen)
        if self._max_scroll():
            track = self._scrollbar_track()
            thumb = self._scroll_thumb()
            pygame.draw.rect(screen, (60, 64, 72), track, border_radius=4)
            pygame.draw.rect(screen, (150, 156, 166), thumb, border_radius=4)
        minimap = self._minimap_rect()
        if minimap is not None:
            self.minimap.refresh(self.state)
            grid = self.grid_rect()
            view_w = min(self.state.map_w - self.origin_x, grid.w // self.zoom)
            view_h = min(self.state.map_h - self.origin_y, grid.h // self.zoom)
            self.minimap.draw(screen, minimap, (self.origin_x, self.origin_y, view_w, view_h))
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
            image = pygame.image.load(str(MAP_DIR / item["asset"])).convert_alpha()
            if item["category"] in ("tree", "old_tree") and key in MAP_TREE_SHEETS:
                frame_w, frame_h = MAP_TREE_SHEETS[key]
                frame = image.subsurface(pygame.Rect(0, 0, frame_w, frame_h)).copy()
                image = _scale_rgba(frame, (round(frame_w * MAP_TREE_SCALE), round(frame_h * MAP_TREE_SCALE)))
            elif item["category"] in ("stump", "log"):
                size = (round(image.get_width() * MAP_PROP_SCALE), round(image.get_height() * MAP_PROP_SCALE))
                image = _scale_rgba(image, size)
            self.natives[key] = image
        return self.natives[key]

    def _scaled(self, key, zoom):
        cache_key = (key, zoom)
        if cache_key not in self.scaled:
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
