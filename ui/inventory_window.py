"""
Окно инвентаря: кукла персонажа со слотами экипировки и рюкзак 10x5.

ЛКМ — выбрать / перетащить, ПКМ — быстрое действие (использовать, надеть, снять).
Открывается глобально клавишей I (см. main.py) и кнопкой «РЮКЗАК» в профиле.
"""

import time
from pathlib import Path

import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button


PLACEHOLDERS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fighters" / "equipment" / "placeholders"

BACKPACK_COLS = 10
BACKPACK_ROWS = 5
CELL = 62
GAP = 4
SLOT = 64

# Колонки слотов вокруг куклы: (ключ, подпись)
LEFT_SLOTS = (("head", "Голова"), ("neck", "Шея"), ("back", "Плащ"), ("body", "Доспех"), ("belt", "Пояс"), ("legs", "Ноги"))
RIGHT_SLOTS = (("ears", "Серьги"), ("hands", "Руки"), ("ring", "Кольцо"), ("weapon", "Оружие"), ("shield", "Щит"), ("feet", "Обувь"))
SLOT_LABELS = dict(LEFT_SLOTS + RIGHT_SLOTS)

# Порядок наложения слоёв на куклу (снизу вверх)
LAYER_ORDER = ("back", "legs", "feet", "body", "belt", "neck", "hands", "ring", "head", "ears", "shield", "weapon")
# Область холста 1024x1024, где стоит фигура
DOLL_CROP = pygame.Rect(200, 70, 630, 790)

RARITY_COLORS = {
    "common": (205, 205, 205),
    "rare": (80, 150, 255),
    "epic": (180, 100, 240),
    "legendary": (255, 170, 40),
}
RARITY_LABELS = {"common": "Обычный", "rare": "Редкий", "epic": "Эпический", "legendary": "Легендарный"}
TYPE_LABELS = {"potion": "Зелье", "material": "Материал", "equipment": "Экипировка", "scroll": "Свиток"}
STAT_LABELS = {
    "strength": "Сила",
    "agility": "Ловкость",
    "intuition": "Интуиция",
    "endurance": "Выносливость",
    "wisdom": "Мудрость",
    "intellect": "Интеллект",
    "harmony": "Гармония",
}

PANEL_BG = (32, 28, 30)
PANEL_BORDER = (150, 120, 70)
CELL_BG = (48, 44, 48)
CELL_HOVER = (70, 64, 70)
CELL_BORDER = (85, 78, 80)
TEXT = (230, 222, 205)
TEXT_DIM = (150, 142, 130)
GOLD = (255, 215, 120)
GREEN = (120, 220, 120)
RED = (235, 110, 100)


class IconCache:
    """Иконки предметов: обрезанные слои экипировки или процедурные рисунки"""

    def __init__(self):
        self._layers = {}
        self._icons = {}

    def layer(self, key):
        """Полноразмерный слой экипировки 1024x1024 (или None)"""
        if key not in self._layers:
            path = PLACEHOLDERS_DIR / f"{key}.png"
            try:
                self._layers[key] = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, OSError, FileNotFoundError):
                self._layers[key] = None
        return self._layers[key]

    def get(self, key, size):
        cache_key = (key, size)
        if cache_key not in self._icons:
            self._icons[cache_key] = self._build(key, size)
        return self._icons[cache_key]

    def _build(self, key, size):
        layer = self.layer(key) if key else None
        if layer is not None:
            cropped = layer.subsurface(layer.get_bounding_rect())
            scale = (size * 0.84) / max(cropped.get_width(), cropped.get_height())
            scaled = pygame.transform.smoothscale(
                cropped,
                (max(1, int(cropped.get_width() * scale)), max(1, int(cropped.get_height() * scale))),
            )
            icon = pygame.Surface((size, size), pygame.SRCALPHA)
            icon.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
            return icon
        return self._draw_procedural(key or "", size)

    @staticmethod
    def _draw_procedural(key, size):
        icon = pygame.Surface((size, size), pygame.SRCALPHA)
        s = size / 64.0

        def p(x, y):
            return int(x * s), int(y * s)

        def r(x, y, w, h):
            return pygame.Rect(int(x * s), int(y * s), int(w * s), int(h * s))

        outline = (40, 30, 25)
        if key.startswith("potion"):
            liquid = {"potion_red": (210, 50, 60), "potion_blue": (60, 110, 230), "potion_orange": (235, 140, 40)}.get(key, (150, 80, 200))
            pygame.draw.circle(icon, (200, 220, 230), p(32, 40), int(17 * s))
            pygame.draw.circle(icon, liquid, p(32, 41), int(14 * s))
            pygame.draw.rect(icon, (200, 220, 230), r(26, 12, 12, 16))
            pygame.draw.rect(icon, (140, 90, 50), r(25, 8, 14, 7), border_radius=2)
            pygame.draw.circle(icon, (255, 255, 255), p(26, 35), int(4 * s))
            pygame.draw.circle(icon, outline, p(32, 40), int(17 * s), max(1, int(2 * s)))
        elif key == "ore":
            pygame.draw.polygon(icon, (110, 100, 95), [p(12, 44), p(20, 22), p(38, 14), p(54, 28), p(50, 50), p(26, 54)])
            for x, y in ((24, 30), (38, 26), (34, 42), (44, 38)):
                pygame.draw.circle(icon, (190, 120, 80), p(x, y), int(4 * s))
            pygame.draw.polygon(icon, outline, [p(12, 44), p(20, 22), p(38, 14), p(54, 28), p(50, 50), p(26, 54)], max(1, int(2 * s)))
        elif key == "herb":
            pygame.draw.line(icon, (70, 120, 50), p(32, 56), p(32, 18), max(1, int(3 * s)))
            for cx, cy, w in ((22, 30, 18), (42, 26, 18), (24, 44, 16), (40, 42, 16)):
                pygame.draw.ellipse(icon, (90, 180, 70), r(cx - w / 2, cy - 5, w, 10))
        elif key == "bone":
            pygame.draw.line(icon, (235, 225, 200), p(18, 46), p(46, 18), max(2, int(8 * s)))
            for x, y in ((14, 44), (20, 50), (44, 14), (50, 20)):
                pygame.draw.circle(icon, (235, 225, 200), p(x, y), int(6 * s))
        elif key == "crystal":
            points = [p(32, 8), p(48, 26), p(40, 56), p(24, 56), p(16, 26)]
            pygame.draw.polygon(icon, (90, 200, 240), points)
            pygame.draw.polygon(icon, (190, 240, 255), [p(32, 8), p(40, 26), p(32, 56), p(24, 26)])
            pygame.draw.polygon(icon, outline, points, max(1, int(2 * s)))
        elif key == "scroll":
            pygame.draw.rect(icon, (225, 205, 160), r(16, 14, 32, 36))
            pygame.draw.rect(icon, (170, 130, 80), r(12, 10, 40, 8), border_radius=4)
            pygame.draw.rect(icon, (170, 130, 80), r(12, 46, 40, 8), border_radius=4)
            for y in (24, 30, 36):
                pygame.draw.line(icon, (130, 100, 70), p(22, y), p(42, y), max(1, int(2 * s)))
        else:
            pygame.draw.rect(icon, (90, 80, 90), r(14, 14, 36, 36), border_radius=6)
            font = pygame.font.SysFont(settings.FONT_NAME, int(28 * s), bold=True)
            mark = font.render("?", True, TEXT)
            icon.blit(mark, mark.get_rect(center=(size // 2, size // 2)))
        return icon


class InventoryWindow:
    """Модальное окно инвентаря для текущей онлайн-сессии"""

    def __init__(self):
        self.session = None
        self.icons = IconCache()
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 30, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.qty_font = pygame.font.SysFont(settings.FONT_NAME, 15, bold=True)

        self.rect = pygame.Rect(0, 0, 1240, 760)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.close_button = pygame.Rect(self.rect.right - 56, self.rect.y + 14, 40, 40)

        # Кукла и слоты
        doll_left = self.rect.x + 24
        self.doll_area = pygame.Rect(doll_left + SLOT + 16, self.rect.y + 80, 330, 414)
        self.slot_rects = {}
        for column, slots in ((doll_left, LEFT_SLOTS), (self.doll_area.right + 16, RIGHT_SLOTS)):
            for row, (key, _label) in enumerate(slots):
                self.slot_rects[key] = pygame.Rect(column, self.doll_area.y + row * (SLOT + 6), SLOT, SLOT)
        self.stats_rect = pygame.Rect(doll_left, self.doll_area.bottom + 24, self.doll_area.right + 16 + SLOT - doll_left, 190)

        # Рюкзак
        grid_left = self.rect.x + 560
        grid_top = self.rect.y + 110
        self.cell_rects = [
            pygame.Rect(grid_left + col * (CELL + GAP), grid_top + row * (CELL + GAP), CELL, CELL)
            for row in range(BACKPACK_ROWS)
            for col in range(BACKPACK_COLS)
        ]
        grid_width = BACKPACK_COLS * (CELL + GAP) - GAP
        self.details_rect = pygame.Rect(grid_left, self.cell_rects[-1].bottom + 24, grid_width, 250)
        button_y = self.details_rect.bottom - 56
        self.action_button = pygame.Rect(self.details_rect.x + 20, button_y, 190, 40)
        self.drop_button = pygame.Rect(self.details_rect.right - 210, button_y, 190, 40)

        self._reset_state()

    def _reset_state(self):
        self.inventory = {}   # slot_index -> предмет
        self.equipment = {}   # slot -> предмет
        self.bonuses = {}
        self.capacity = BACKPACK_COLS * BACKPACK_ROWS
        self.selected = None  # ("bag", index) | ("equip", slot)
        self.pressed = None
        self.press_pos = (0, 0)
        self.dragging = False
        self.drop_confirm_until = 0.0
        self.message = None
        self.message_color = TEXT
        self.message_until = 0.0
        self._doll_key = None
        self._doll_surface = None

    # ==================== ОТКРЫТИЕ / ЗАКРЫТИЕ ====================

    @property
    def is_open(self):
        return self.session is not None

    def open(self, session):
        self._reset_state()
        self.session = session
        self._request(session.client.get_inventory, session.character["id"])

    def close(self):
        self.session = None
        self._reset_state()

    def toggle(self, session):
        if self.is_open:
            self.close()
        else:
            self.open(session)

    # ==================== СЕРВЕР ====================

    def _request(self, method, *args):
        """Вызывает метод клиента и применяет полученное состояние. True при успехе."""
        try:
            state = method(*args)
        except ServerError as error:
            self._say(str(error), RED)
            return False
        self._apply_state(state)
        return True

    def _apply_state(self, state):
        self.inventory = {item["slot_index"]: item for item in state.get("inventory", [])}
        self.equipment = dict(state.get("equipment", {}))
        self.bonuses = dict(state.get("bonuses", {}))
        self.capacity = int(state.get("capacity", self.capacity))
        character = self.session.character
        character["equipment_bonuses"] = dict(self.bonuses)
        updated = state.get("character")
        if updated:
            for key in ("hp", "max_hp", "mp", "max_mp"):
                if key in updated:
                    character[key] = updated[key]
        if self.selected and self._item_at(self.selected) is None:
            self.selected = None

    def _character_id(self):
        return self.session.character["id"]

    def _say(self, text, color=TEXT, seconds=3.0):
        self.message = text
        self.message_color = color
        self.message_until = time.time() + seconds

    # ==================== ДЕЙСТВИЯ ====================

    def _item_at(self, target):
        if target is None:
            return None
        kind, key = target
        return self.inventory.get(key) if kind == "bag" else self.equipment.get(key)

    def _quick_action(self, target):
        """Основное действие для предмета: использовать / надеть / снять"""
        item = self._item_at(target)
        if item is None:
            return
        kind, key = target
        client = self.session.client
        if kind == "equip":
            if self._request(client.unequip_item, self._character_id(), key):
                self._say(f"Снято: {item['name']}")
        elif item.get("equip_slot"):
            if self._request(client.equip_item, self._character_id(), key):
                self.selected = ("equip", item["equip_slot"])
                self._say(f"Надето: {item['name']}", GREEN)
        elif item.get("can_use"):
            if self._request(client.use_item, self._character_id(), key):
                self._say(f"Использовано: {item['name']}", GREEN)
        else:
            self._say("Этот предмет нельзя использовать", TEXT_DIM)

    def _drop(self, target):
        item = self._item_at(target)
        if item is None or target[0] != "bag":
            return
        if time.time() > self.drop_confirm_until:
            self.drop_confirm_until = time.time() + 3.0
            return
        self.drop_confirm_until = 0.0
        if self._request(self.session.client.drop_item, self._character_id(), target[1]):
            self._say(f"Выброшено: {item['name']}", TEXT_DIM)

    def _drop_onto(self, source, target):
        """Завершение перетаскивания предмета source на target"""
        if target is None or source == target:
            return
        item = self._item_at(source)
        client = self.session.client
        character_id = self._character_id()
        if source[0] == "bag" and target[0] == "bag":
            self._request(client.move_item, character_id, source[1], target[1])
            self.selected = target
        elif source[0] == "bag" and target[0] == "equip":
            if item.get("equip_slot") != target[1]:
                self._say(f"Сюда нельзя: слот «{SLOT_LABELS[target[1]]}»", RED)
                return
            if self._request(client.equip_item, character_id, source[1], target[1]):
                self.selected = target
                self._say(f"Надето: {item['name']}", GREEN)
        elif source[0] == "equip" and target[0] == "bag":
            if self._request(client.unequip_item, character_id, source[1], target[1]):
                self.selected = None
                self._say(f"Снято: {item['name']}")

    # ==================== СОБЫТИЯ ====================

    def _target_at(self, position):
        for index, rect in enumerate(self.cell_rects):
            if rect.collidepoint(position):
                return ("bag", index)
        for slot, rect in self.slot_rects.items():
            if rect.collidepoint(position):
                return ("equip", slot)
        return None

    def handle_event(self, event):
        """Окно модальное: пока оно открыто, поглощает все события ввода"""
        if not self.is_open:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_i):
                self.close()
            elif event.key == pygame.K_DELETE and self.selected:
                self._drop(self.selected)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = event.pos
            if self.close_button.collidepoint(position):
                self.close()
                return True
            item = self._item_at(self.selected)
            if item is not None and self.action_button.collidepoint(position):
                self._quick_action(self.selected)
                return True
            if item is not None and self.selected[0] == "bag" and self.drop_button.collidepoint(position):
                self._drop(self.selected)
                return True
            target = self._target_at(position)
            if target is not None and self._item_at(target) is not None:
                self.pressed = target
                self.press_pos = position
                self.dragging = False
                if target != self.selected:
                    self.drop_confirm_until = 0.0
                self.selected = target
            elif target is not None or not self.rect.collidepoint(position):
                self.selected = None
            return True

        if event.type == pygame.MOUSEMOTION and self.pressed is not None and not self.dragging:
            dx = event.pos[0] - self.press_pos[0]
            dy = event.pos[1] - self.press_pos[1]
            self.dragging = dx * dx + dy * dy > 36
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pressed is not None and self.dragging:
                self._drop_onto(self.pressed, self._target_at(event.pos))
            self.pressed = None
            self.dragging = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            target = self._target_at(event.pos)
            if target is not None and self._item_at(target) is not None:
                self.selected = target
                self._quick_action(target)
            return True

        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION,
                              pygame.MOUSEWHEEL, pygame.KEYUP, pygame.TEXTINPUT)

    # ==================== РИСОВАНИЕ ====================

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))

        pygame.draw.rect(screen, PANEL_BG, self.rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, self.rect, 3, border_radius=14)
        title = self.title_font.render("ИНВЕНТАРЬ", True, GOLD)
        screen.blit(title, (self.rect.x + 28, self.rect.y + 22))
        draw_button(screen, self.close_button, "×", self.title_font, color=(90, 60, 55), hover_color=(150, 70, 60))

        mouse = pygame.mouse.get_pos()
        dragged = self._item_at(self.pressed) if self.dragging else None

        self._draw_doll(screen)
        self._draw_slots(screen, mouse, dragged)
        self._draw_stats(screen)
        self._draw_backpack(screen, mouse)
        self._draw_details(screen)

        hint = self.small_font.render(
            "ЛКМ — выбрать или перетащить   ·   ПКМ — надеть / снять / использовать   ·   Del — выбросить   ·   I / Esc — закрыть",
            True,
            TEXT_DIM,
        )
        screen.blit(hint, hint.get_rect(midbottom=(self.rect.centerx, self.rect.bottom - 12)))

        if self.message and time.time() < self.message_until:
            text = self.font.render(self.message, True, self.message_color)
            screen.blit(text, text.get_rect(midright=(self.close_button.x - 20, self.close_button.centery)))

        if dragged is not None:
            icon = self.icons.get(dragged.get("icon"), CELL)
            icon = icon.copy()
            icon.set_alpha(210)
            screen.blit(icon, icon.get_rect(center=mouse))
        else:
            hovered = self._item_at(self._target_at(mouse))
            if hovered is not None:
                self._draw_tooltip(screen, hovered, mouse)

    def _draw_doll(self, screen):
        pygame.draw.rect(screen, (40, 36, 40), self.doll_area, border_radius=10)
        key = tuple(self.equipment[slot]["icon"] for slot in LAYER_ORDER if slot in self.equipment)
        if key != self._doll_key:
            self._doll_key = key
            self._doll_surface = self._render_doll(key)
        screen.blit(self._doll_surface, self._doll_surface.get_rect(center=self.doll_area.center))

    def _render_doll(self, layer_keys):
        canvas = pygame.Surface((1024, 1024), pygame.SRCALPHA)
        body = (78, 68, 64)
        edge = (105, 94, 86)
        # Манекен, совпадающий с раскладкой слоёв экипировки
        for shape in (
            ("rect", pygame.Rect(360, 262, 60, 250), 28),
            ("rect", pygame.Rect(604, 262, 60, 250), 28),
            ("rect", pygame.Rect(412, 450, 92, 260), 20),
            ("rect", pygame.Rect(520, 450, 92, 260), 20),
            ("rect", pygame.Rect(400, 690, 104, 150), 20),
            ("rect", pygame.Rect(520, 690, 104, 150), 20),
            ("poly", [(425, 250), (599, 250), (622, 470), (402, 470)], 0),
            ("rect", pygame.Rect(488, 220, 48, 40), 8),
        ):
            kind, geometry, radius = shape
            if kind == "rect":
                pygame.draw.rect(canvas, body, geometry, border_radius=radius)
                pygame.draw.rect(canvas, edge, geometry, 5, border_radius=radius)
            else:
                pygame.draw.polygon(canvas, body, geometry)
                pygame.draw.polygon(canvas, edge, geometry, 5)
        pygame.draw.circle(canvas, body, (512, 165), 72)
        pygame.draw.circle(canvas, edge, (512, 165), 72, 5)

        for layer_key in layer_keys:
            layer = self.icons.layer(layer_key)
            if layer is not None:
                canvas.blit(layer, (0, 0))

        figure = canvas.subsurface(DOLL_CROP)
        scale = min(self.doll_area.width / DOLL_CROP.width, self.doll_area.height / DOLL_CROP.height)
        return pygame.transform.smoothscale(
            figure,
            (int(DOLL_CROP.width * scale), int(DOLL_CROP.height * scale)),
        )

    def _draw_cell(self, screen, rect, item, *, hovered, selected, highlight=None):
        pygame.draw.rect(screen, CELL_HOVER if hovered else CELL_BG, rect, border_radius=6)
        border = RARITY_COLORS.get(item.get("rarity"), CELL_BORDER) if item else CELL_BORDER
        if highlight is not None:
            border = highlight
        pygame.draw.rect(screen, border, rect, 3 if selected or highlight else 2, border_radius=6)
        if selected:
            pygame.draw.rect(screen, GOLD, rect.inflate(6, 6), 2, border_radius=8)
        if item is None:
            return
        being_dragged = self.dragging and self._item_at(self.pressed) is item
        icon = self.icons.get(item.get("icon"), rect.width)
        if being_dragged:
            icon = icon.copy()
            icon.set_alpha(70)
        screen.blit(icon, rect.topleft)
        if item.get("quantity", 1) > 1:
            qty = self.qty_font.render(str(item["quantity"]), True, (255, 255, 255))
            shadow = self.qty_font.render(str(item["quantity"]), True, (0, 0, 0))
            spot = qty.get_rect(bottomright=(rect.right - 5, rect.bottom - 3))
            screen.blit(shadow, spot.move(1, 1))
            screen.blit(qty, spot)

    def _draw_slots(self, screen, mouse, dragged):
        for slot, rect in self.slot_rects.items():
            item = self.equipment.get(slot)
            highlight = None
            if dragged is not None and dragged.get("equip_slot") == slot:
                highlight = GREEN
            self._draw_cell(
                screen, rect, item,
                hovered=rect.collidepoint(mouse),
                selected=self.selected == ("equip", slot),
                highlight=highlight,
            )
            if item is None:
                label = self.small_font.render(SLOT_LABELS[slot], True, TEXT_DIM)
                if label.get_width() > rect.width - 4:
                    label = pygame.transform.smoothscale(label, (rect.width - 4, label.get_height()))
                screen.blit(label, label.get_rect(center=rect.center))

    def _draw_stats(self, screen):
        pygame.draw.rect(screen, (40, 36, 40), self.stats_rect, border_radius=10)
        character = self.session.character
        x = self.stats_rect.x + 18
        y = self.stats_rect.y + 14
        header = self.font.render(f"{character.get('name', '')}  ·  уровень {character.get('level', 1)}", True, GOLD)
        screen.blit(header, (x, y))
        y += 34

        stats = character.get("stats", {})
        column_width = (self.stats_rect.width - 36) // 2
        for index, (stat, value) in enumerate(stats.items()):
            cx = x + (index % 2) * column_width
            cy = y + (index // 2) * 30
            name = self.font.render(f"{STAT_LABELS.get(stat, stat)}: {value}", True, TEXT)
            screen.blit(name, (cx, cy))
            bonus = int(self.bonuses.get(stat, 0))
            if bonus:
                extra = self.font.render(f"+{bonus}" if bonus > 0 else str(bonus), True, GREEN if bonus > 0 else RED)
                screen.blit(extra, (cx + name.get_width() + 8, cy))
        y += ((len(stats) + 1) // 2) * 30 + 10

        hp_line = self.font.render(
            f"Здоровье: {character.get('hp', 0)} / {character.get('max_hp', 0)}"
            f"      Мана: {character.get('mp', 0)} / {character.get('max_mp', 0)}",
            True,
            TEXT,
        )
        screen.blit(hp_line, (x, y))
        y += 30
        weight = sum(item.get("weight", 0) * item.get("quantity", 1) for item in self.inventory.values())
        weight += sum(item.get("weight", 0) for item in self.equipment.values())
        weight_line = self.small_font.render(f"Общий вес снаряжения: {weight:.1f} кг", True, TEXT_DIM)
        screen.blit(weight_line, (x, y))

    def _draw_backpack(self, screen, mouse):
        header = self.font.render(f"РЮКЗАК   {len(self.inventory)} / {self.capacity}", True, GOLD)
        screen.blit(header, (self.cell_rects[0].x, self.cell_rects[0].y - 34))
        for index, rect in enumerate(self.cell_rects):
            self._draw_cell(
                screen, rect, self.inventory.get(index),
                hovered=rect.collidepoint(mouse),
                selected=self.selected == ("bag", index),
            )

    def _draw_details(self, screen):
        pygame.draw.rect(screen, (40, 36, 40), self.details_rect, border_radius=10)
        item = self._item_at(self.selected)
        x = self.details_rect.x + 20
        if item is None:
            text = self.font.render("Выберите предмет, чтобы увидеть подробности", True, TEXT_DIM)
            screen.blit(text, text.get_rect(center=self.details_rect.center))
            return

        screen.blit(self.icons.get(item.get("icon"), 96), (x, self.details_rect.y + 18))
        self._draw_item_text(screen, item, x + 116, self.details_rect.y + 18, self.details_rect.right - x - 136)

        kind = self.selected[0]
        if kind == "equip":
            label = "СНЯТЬ"
        elif item.get("equip_slot"):
            label = "НАДЕТЬ"
        elif item.get("can_use"):
            label = "ИСПОЛЬЗОВАТЬ"
        else:
            label = None
        if label:
            draw_button(screen, self.action_button, label, self.font, color=(70, 120, 80), hover_color=(90, 160, 100))
        if kind == "bag":
            confirming = time.time() < self.drop_confirm_until
            draw_button(
                screen, self.drop_button, "ТОЧНО ВЫБРОСИТЬ?" if confirming else "ВЫБРОСИТЬ", self.font,
                color=(150, 60, 55) if confirming else (95, 60, 58), hover_color=(170, 70, 60),
            )

    def _item_lines(self, item):
        """Строки описания предмета: (текст, цвет, шрифт)"""
        rarity = item.get("rarity", "common")
        kind = TYPE_LABELS.get(item.get("item_type"), item.get("item_type", ""))
        if item.get("equip_slot"):
            kind = f"{kind} · {SLOT_LABELS.get(item['equip_slot'], item['equip_slot'])}"
        lines = [
            (item.get("name", "?"), RARITY_COLORS.get(rarity, TEXT), self.font),
            (f"{RARITY_LABELS.get(rarity, rarity)} · {kind}", TEXT_DIM, self.small_font),
        ]
        if item.get("description"):
            lines.append((item["description"], TEXT, self.small_font))
        for stat, value in item.get("bonuses", {}).items():
            sign = "+" if value > 0 else ""
            lines.append((f"{sign}{value} {STAT_LABELS.get(stat, stat)}", GREEN if value > 0 else RED, self.small_font))
        effects = item.get("effects", {})
        if item.get("can_use") and effects.get("type") in ("hp", "mp"):
            lines.append((f"Восстанавливает {effects.get('value', 0)} {'здоровья' if effects['type'] == 'hp' else 'маны'}", GREEN, self.small_font))
        lines.append((f"Вес: {item.get('weight', 0):g} кг   ·   Цена: {item.get('price', 0)} зол.", TEXT_DIM, self.small_font))
        return lines

    def _draw_item_text(self, screen, item, x, y, width):
        for text, color, font in self._item_lines(item):
            for line in self._wrap(text, font, width):
                surface = font.render(line, True, color)
                screen.blit(surface, (x, y))
                y += surface.get_height() + 4
        return y

    @staticmethod
    def _wrap(text, font, width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def _draw_tooltip(self, screen, item, mouse):
        width = 300
        lines = [
            (line, color, font)
            for text, color, font in self._item_lines(item)
            for line in self._wrap(text, font, width - 24)
        ]
        height = sum(font.get_linesize() + 4 for _, _, font in lines) + 20
        tooltip = pygame.Rect(mouse[0] + 18, mouse[1] + 18, width, height)
        tooltip.clamp_ip(screen.get_rect())
        if tooltip.collidepoint(mouse):
            tooltip.right = mouse[0] - 12
            tooltip.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, (22, 20, 24), tooltip, border_radius=8)
        pygame.draw.rect(screen, RARITY_COLORS.get(item.get("rarity"), PANEL_BORDER), tooltip, 2, border_radius=8)
        y = tooltip.y + 10
        for line, color, font in lines:
            surface = font.render(line, True, color)
            screen.blit(surface, (tooltip.x + 12, y))
            y += font.get_linesize() + 4
