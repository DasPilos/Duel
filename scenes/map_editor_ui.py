"""Интерфейс редактора карт: строка меню с выпадающими списками, панель инструментов, миникарта и окно ввода."""
import time

import pygame

from core import mob_modes
from core.game_modes import DEFAULT_MODE, mode_name
from core.tile_mask import BLOCKED, FREE, MASK_CELLS, MASK_SIDE

MENU_H = 26
TOOL_H = 40
SERVER_BTN_W = 230
ITEM_H = 24
SEP_H = 7
TOOL_W = 124
DRAFT_W = 720
DRAFT_DETAILS_X = 280
DRAFT_DELETE_SIZE = 20
DRAFT_DELETE_COLOR = (150, 60, 55)
DRAFT_CONFIRM_BUTTON_W = 150
DRAFT_CONFIRM_BUTTON_H = 36
DRAFT_HEAD_H = 48
DRAFT_ROW_H = 30
DRAFT_ROWS = 10
DRAFT_FOOT_H = 40
SAVE_W = 720
SAVE_LIST_TOP = 112
SAVE_FOOT_H = 40
SAVE_BUTTON_W = 120
CONFIRM_W = 460
CONFIRM_H = 124
CONFIRM_BUTTON_W = 180
SIZE_W = 440
SIZE_HEAD_H = 52
SIZE_ROW_H = 36
SIZE_FOOT_H = 36
SIZE_MODE_H = 44
SIZE_MODE_W = 140
WORLD_W = 460
WORLD_HEAD_H = 52
WORLD_ROW_H = 32
WORLD_FOOT_H = 80
MASK_W = 580
MASK_HEAD_H = 56
MASK_AREA_H = 300
MASK_BUTTON_Y = MASK_HEAD_H + MASK_AREA_H + 24
MASK_BUTTON_W = 130
MASK_BUTTON_H = 34
MASK_BUTTON_GAP = 8
MASK_FOOT_H = 40
MASK_H = MASK_BUTTON_Y + MASK_BUTTON_H + MASK_FOOT_H
MASK_FREE_COLOR = (120, 220, 140)
MASK_BLOCK_COLOR = (240, 110, 100)
MASK_BUTTONS = [("free", "Все свободны"), ("block", "Все стоп"), ("clear", "Убрать маску"), ("save", "Сохранить")]
ACTIVE_TEXT = (120, 220, 140)
MENU_BG = (42, 46, 54)
MENU_ACTIVE = (70, 98, 136)
DROP_BG = (34, 37, 43)
BUTTON_BG = (46, 50, 58)
BUTTON_ON = (70, 98, 136)
BORDER = (70, 74, 82)
TEXT = (235, 235, 235)
TEXT_DIM = (160, 166, 176)
TEXT_OFF = (95, 100, 110)
WARN_TEXT = (240, 190, 90)
VIEW_COLOR = (255, 220, 90)
MINI_EMPTY = (18, 20, 24)
MINI_UNKNOWN = (200, 200, 200)
CATEGORY_COLORS = {
    "ground": (88, 132, 64),
    "floor": (104, 146, 76),
    "berry": (120, 150, 70),
    "road": (150, 118, 78),
    "water": (56, 104, 168),
    "bridge": (142, 98, 58),
    "rock": (122, 122, 128),
    "tree": (28, 76, 40),
    "old_tree": (34, 84, 46),
    "stump": (92, 70, 48),
    "log": (100, 76, 52),
}


class MenuBar:
    def __init__(self, font, small):
        self.font = font
        self.small = small
        self.open_index = None

    def _titles(self, menus):
        rects = []
        x = 6
        for title, _items in menus:
            width = self.font.size(title)[0] + 24
            rects.append(pygame.Rect(x, 0, width, MENU_H))
            x += width
        return rects

    def _dropdown(self, menus, index):
        title = self._titles(menus)[index]
        items = menus[index][1]
        width = 240
        for item in items:
            if not item.get("separator"):
                hotkey_width = self.small.size(item.get("hotkey", ""))[0]
                width = max(width, self.font.size(item["label"])[0] + hotkey_width + 56)
        height = 8 + sum(SEP_H if item.get("separator") else ITEM_H for item in items)
        return pygame.Rect(title.x, MENU_H, width, height)

    def _item_rects(self, menus, index):
        box = self._dropdown(menus, index)
        y = box.y + 4
        rects = []
        for item in menus[index][1]:
            height = SEP_H if item.get("separator") else ITEM_H
            rects.append((item, pygame.Rect(box.x + 2, y, box.w - 4, height)))
            y += height
        return rects

    def is_open(self):
        return self.open_index is not None

    def close(self):
        self.open_index = None

    def covers(self, pos, menus):
        """Истина, если указатель над строкой меню или открытым списком."""
        if pos[1] < MENU_H:
            return True
        return self.open_index is not None and self._dropdown(menus, self.open_index).collidepoint(pos)

    def hover(self, pos, menus):
        """Пока меню открыто, наведение на другой заголовок переключает список."""
        if self.open_index is None:
            return
        for index, rect in enumerate(self._titles(menus)):
            if rect.collidepoint(pos):
                self.open_index = index
                return

    def click(self, pos, menus):
        """Возвращает (нажатие поглощено, id команды или None)."""
        for index, rect in enumerate(self._titles(menus)):
            if rect.collidepoint(pos):
                self.open_index = None if self.open_index == index else index
                return True, None
        if self.open_index is None:
            return False, None
        for item, rect in self._item_rects(menus, self.open_index):
            if rect.collidepoint(pos):
                if item.get("separator") or not item.get("enabled", True):
                    return True, None
                self.open_index = None
                return True, item["id"]
        self.open_index = None
        return True, None

    def draw(self, screen, menus):
        screen.fill(MENU_BG, pygame.Rect(0, 0, screen.get_width(), MENU_H))
        for index, ((title, _items), rect) in enumerate(zip(menus, self._titles(menus))):
            if index == self.open_index:
                pygame.draw.rect(screen, MENU_ACTIVE, rect)
            label = self.font.render(title, True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))
        pygame.draw.line(screen, BORDER, (0, MENU_H - 1), (screen.get_width(), MENU_H - 1))
        if self.open_index is None:
            return
        box = self._dropdown(menus, self.open_index)
        pygame.draw.rect(screen, DROP_BG, box)
        pygame.draw.rect(screen, BORDER, box, 1)
        mouse = pygame.mouse.get_pos()
        for item, rect in self._item_rects(menus, self.open_index):
            if item.get("separator"):
                pygame.draw.line(screen, BORDER, (rect.x + 8, rect.centery), (rect.right - 8, rect.centery))
                continue
            enabled = item.get("enabled", True)
            color = TEXT if enabled else TEXT_OFF
            if enabled and rect.collidepoint(mouse):
                pygame.draw.rect(screen, MENU_ACTIVE, rect)
            if item.get("checked"):
                pygame.draw.rect(screen, color, (rect.x + 8, rect.centery - 4, 8, 8))
            screen.blit(self.font.render(item["label"], True, color), (rect.x + 26, rect.y + 3))
            hotkey = item.get("hotkey", "")
            if hotkey:
                text = self.small.render(hotkey, True, TEXT_DIM)
                screen.blit(text, text.get_rect(midright=(rect.right - 10, rect.centery)))


class ToolBar:
    def __init__(self, font):
        self.font = font

    def rects(self, count):
        return [pygame.Rect(8 + index * TOOL_W, MENU_H + 6, TOOL_W - 8, TOOL_H - 12) for index in range(count)]

    def click(self, pos, buttons):
        for (tool_id, _label, _hotkey), rect in zip(buttons, self.rects(len(buttons))):
            if rect.collidepoint(pos):
                return tool_id
        return None

    def server_rect(self, width):
        return pygame.Rect(width - SERVER_BTN_W - 8, MENU_H + 6, SERVER_BTN_W, TOOL_H - 12)

    def server_clicked(self, pos, width):
        return self.server_rect(width).collidepoint(pos)

    def draw(self, screen, buttons, active, extra, server=None):
        screen.fill(MENU_BG, pygame.Rect(0, MENU_H, screen.get_width(), TOOL_H))
        for (tool_id, label, hotkey), rect in zip(buttons, self.rects(len(buttons))):
            pygame.draw.rect(screen, BUTTON_ON if tool_id == active else BUTTON_BG, rect, border_radius=4)
            text = self.font.render(f"{label} ({hotkey})", True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))
        extra_x = 8 + len(buttons) * TOOL_W + 8
        screen.blit(self.font.render(extra, True, TEXT_DIM), (extra_x, MENU_H + 10))
        if server is not None:
            label, enabled = server
            rect = self.server_rect(screen.get_width())
            pygame.draw.rect(screen, BUTTON_BG if enabled else MENU_BG, rect, border_radius=4)
            pygame.draw.rect(screen, BORDER, rect, 1, border_radius=4)
            text = self.font.render(label, True, TEXT if enabled else TEXT_DIM)
            screen.blit(text, text.get_rect(center=rect.center))
        pygame.draw.line(screen, BORDER, (0, MENU_H + TOOL_H - 1), (screen.get_width(), MENU_H + TOOL_H - 1))


class Minimap:
    def __init__(self):
        self.surface = None
        self.version = None

    def refresh(self, state):
        if self.surface is not None and self.version == state.version:
            return
        self.surface = pygame.Surface((state.map_w, state.map_h))
        self.surface.fill(MINI_EMPTY)
        for layer in (state.ground, state.overlay, state.objects):
            for (x, y), key in layer.items():
                category = state.items[key]["category"]
                self.surface.set_at((x, y), CATEGORY_COLORS.get(category, MINI_UNKNOWN))
        self.version = state.version

    def draw(self, screen, rect, view):
        """view = (x, y, w, h) в клетках карты: видимая часть сетки."""
        screen.blit(self.surface, rect)
        pygame.draw.rect(screen, BORDER, rect, 1)
        x, y, w, h = view
        pygame.draw.rect(screen, VIEW_COLOR, (rect.x + x, rect.y + y, w, h), 1)


class LoginPrompt:
    """Окно входа на сервер внутри редактора: логин и пароль (звёздочки). Tab — другое поле, Enter или «Сохранить» — войти, Esc — отмена."""

    WIDTH = 460
    HEIGHT = 300
    FIELD_H = 34
    MAX_LENGTH = 64
    SUBMIT_W = 160
    SUBMIT_H = 36

    def __init__(self, font, small, username=""):
        self.font = font
        self.small = small
        self.fields = {"username": username, "password": ""}
        self.active = "password" if username else "username"
        self.message = ""

    def box(self):
        rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def submit_rect(self):
        box = self.box()
        return pygame.Rect(box.right - 24 - self.SUBMIT_W, box.y + 218, self.SUBMIT_W, self.SUBMIT_H)

    def _field_rect(self, name):
        box = self.box()
        index = 0 if name == "username" else 1
        return pygame.Rect(box.x + 24, box.y + 64 + index * 62, box.w - 48, self.FIELD_H)

    def handle_event(self, event):
        """None, 'submit' (Enter) или 'cancel' (Esc)."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "submit"
            if event.key == pygame.K_TAB:
                self.active = "password" if self.active == "username" else "username"
            elif event.key == pygame.K_BACKSPACE:
                self.fields[self.active] = self.fields[self.active][:-1]
        elif event.type == pygame.TEXTINPUT:
            if len(self.fields[self.active]) < self.MAX_LENGTH:
                self.fields[self.active] += event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.submit_rect().collidepoint(event.pos):
                return "submit"
            for name in self.fields:
                if self._field_rect(name).collidepoint(event.pos):
                    self.active = name
        return None

    def values(self):
        return self.fields["username"].strip(), self.fields["password"]

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Вход на сервер", True, TEXT), (box.x + 24, box.y + 18))
        for name, label in (("username", "Логин"), ("password", "Пароль")):
            rect = self._field_rect(name)
            screen.blit(self.small.render(label, True, TEXT_DIM), (rect.x, rect.y - 20))
            pygame.draw.rect(screen, BUTTON_ON if name == self.active else BUTTON_BG, rect, border_radius=4)
            shown = self.fields[name] if name == "username" else "*" * len(self.fields[name])
            screen.blit(self.font.render(shown, True, TEXT), (rect.x + 10, rect.y + 6))
        for index, line in enumerate(self.message.split("\n") if self.message else []):
            screen.blit(self.small.render(line, True, WARN_TEXT), (box.x + 24, box.y + 170 + index * 20))
        submit = self.submit_rect()
        pygame.draw.rect(screen, BUTTON_ON, submit, border_radius=4)
        label = self.font.render("Сохранить", True, TEXT)
        screen.blit(label, label.get_rect(center=submit.center))
        hint = self.small.render("Tab — другое поле · Enter — сохранить · Esc — отмена", True, TEXT_DIM)
        screen.blit(hint, (box.x + 24, box.bottom - 30))


class TextPrompt:
    def __init__(self, font, small, title, text, max_length):
        self.font = font
        self.small = small
        self.title = title
        self.text = text
        self.max_length = max_length

    def handle_key(self, event):
        """Возвращает 'ok', 'cancel' или None."""
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "ok"
        if event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
            self.text += event.unicode
        return None

    def draw(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        box = pygame.Rect(0, 0, 460, 132)
        box.center = screen.get_rect().center
        pygame.draw.rect(screen, DROP_BG, box, border_radius=6)
        pygame.draw.rect(screen, BORDER, box, 1, border_radius=6)
        screen.blit(self.font.render(self.title, True, TEXT), (box.x + 18, box.y + 14))
        field = pygame.Rect(box.x + 18, box.y + 50, box.w - 36, 34)
        pygame.draw.rect(screen, BUTTON_BG, field, border_radius=4)
        screen.blit(self.font.render(self.text + "|", True, TEXT), (field.x + 8, field.y + 7))
        hint = self.small.render("Enter — применить · Esc — отмена", True, TEXT_DIM)
        screen.blit(hint, (box.x + 18, box.y + 96))


def _shade(screen):
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 150))
    screen.blit(shade, (0, 0))


def _panel(screen, box):
    pygame.draw.rect(screen, DROP_BG, box, border_radius=6)
    pygame.draw.rect(screen, BORDER, box, 1, border_radius=6)


def _fit(font, text, width):
    while text and font.size(text)[0] > width:
        text = text[:-2] + "…"
    return text


def _scroll_offset(scroll, steps, count):
    return max(0, min(scroll - steps, max(0, count - DRAFT_ROWS)))


def _row_at(pos, box, top, drafts, scroll):
    """Черновик в строке списка под курсором или None. top — отступ списка от верха окна."""
    if not box.collidepoint(pos) or pos[1] < box.y + top:
        return None
    row = (pos[1] - box.y - top) // DRAFT_ROW_H
    if row >= DRAFT_ROWS:
        return None
    index = row + scroll
    return drafts[index] if index < len(drafts) else None


def draft_details(draft):
    """Пояснение к черновику для списка: размер карты и режим игры, например «125×125 · Башня»."""
    parts = []
    if draft.get("map_w") and draft.get("map_h"):
        parts.append(f"{draft['map_w']}×{draft['map_h']}")
    parts.append(mode_name(draft.get("mode", DEFAULT_MODE)))
    return " · ".join(parts)


def _draft_row(box, top, offset):
    return pygame.Rect(box.x + 12, box.y + top + offset * DRAFT_ROW_H, box.w - 24, DRAFT_ROW_H - 4)


def _delete_rect(row):
    """Кнопка «×» в правом краю строки черновика."""
    return pygame.Rect(row.right - DRAFT_DELETE_SIZE - 6, row.centery - DRAFT_DELETE_SIZE // 2, DRAFT_DELETE_SIZE, DRAFT_DELETE_SIZE)


def _draw_rows(screen, font, small, drafts, scroll, box, top, hovered, deletable=False):
    for offset, draft in enumerate(drafts[scroll:scroll + DRAFT_ROWS]):
        row = _draft_row(box, top, offset)
        pygame.draw.rect(screen, MENU_ACTIVE if hovered is draft else BUTTON_BG, row, border_radius=4)
        inset = DRAFT_DELETE_SIZE + 16 if deletable else 10
        stamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(draft["updated_at"]))
        stamp_text = small.render(stamp, True, TEXT_DIM)
        screen.blit(stamp_text, stamp_text.get_rect(midright=(row.right - inset, row.centery)))
        active = draft.get("active_worlds") or []
        if active:
            active_text = small.render(_fit(small, "активна в: " + ", ".join(active), 150), True, ACTIVE_TEXT)
            screen.blit(active_text, active_text.get_rect(midright=(row.right - inset - stamp_text.get_width() - 12, row.centery)))
        if deletable:
            button = _delete_rect(row)
            pygame.draw.rect(screen, DRAFT_DELETE_COLOR, button, border_radius=4)
            cross = small.render("×", True, TEXT)
            screen.blit(cross, cross.get_rect(center=button.center))
        details = small.render(draft_details(draft), True, TEXT_DIM)
        screen.blit(details, details.get_rect(midleft=(row.x + DRAFT_DETAILS_X, row.centery)))
        name = _fit(font, draft["name"], DRAFT_DETAILS_X - 20)
        screen.blit(font.render(name, True, TEXT), (row.x + 10, row.y + 5))


class DraftList:
    """Окно списка черновиков: клик по строке открывает черновик, «×» просит подтверждение удаления, Esc или клик мимо окна закрывает."""

    def __init__(self, font, small, drafts):
        self.font = font
        self.small = small
        self.drafts = drafts
        self.scroll = 0
        self.confirm = None  # черновик, который ждёт подтверждения удаления
        self.message = ""

    def _visible(self):
        return enumerate(self.drafts[self.scroll:self.scroll + DRAFT_ROWS])

    def delete_at(self, pos):
        """Черновик, чью кнопку «×» нажали, или None."""
        box = self.box()
        for offset, draft in self._visible():
            if _delete_rect(_draft_row(box, DRAFT_HEAD_H, offset)).collidepoint(pos):
                return draft
        return None

    def _confirm_buttons(self):
        box = self.box()
        y = box.centery + 10
        yes = pygame.Rect(box.centerx - DRAFT_CONFIRM_BUTTON_W - 10, y, DRAFT_CONFIRM_BUTTON_W, DRAFT_CONFIRM_BUTTON_H)
        no = pygame.Rect(box.centerx + 10, y, DRAFT_CONFIRM_BUTTON_W, DRAFT_CONFIRM_BUTTON_H)
        return yes, no

    def confirm_click(self, pos):
        """«delete», «cancel» или None: что выбрал художник в окне подтверждения."""
        yes, no = self._confirm_buttons()
        if yes.collidepoint(pos):
            return "delete"
        if no.collidepoint(pos):
            return "cancel"
        return None

    def box(self):
        rect = pygame.Rect(0, 0, DRAFT_W, DRAFT_HEAD_H + DRAFT_ROWS * DRAFT_ROW_H + DRAFT_FOOT_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def row_at(self, pos):
        return _row_at(pos, self.box(), DRAFT_HEAD_H, self.drafts, self.scroll)

    def wheel(self, steps):
        self.scroll = _scroll_offset(self.scroll, steps, len(self.drafts))

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Черновики карт", True, TEXT), (box.x + 18, box.y + 14))
        if not self.drafts:
            empty = self.small.render("Черновиков пока нет. Сохраните карту: Ctrl+S", True, TEXT_DIM)
            screen.blit(empty, (box.x + 18, box.y + DRAFT_HEAD_H + 8))
        hovered = self.row_at(pygame.mouse.get_pos())
        _draw_rows(screen, self.font, self.small, self.drafts, self.scroll, box, DRAFT_HEAD_H, hovered, deletable=True)
        if self.confirm is not None:
            self._draw_confirm(screen, box)
        if self.message:
            text = self.small.render(self.message, True, WARN_TEXT)
        else:
            text = self.small.render("Клик — открыть · × — удалить · колесо — прокрутка · Esc — закрыть", True, TEXT_DIM)
        screen.blit(text, (box.x + 18, box.bottom - DRAFT_FOOT_H + 12))

    def _draw_confirm(self, screen, box):
        area = pygame.Rect(box.x + 12, box.y + DRAFT_HEAD_H, box.w - 24, DRAFT_ROWS * DRAFT_ROW_H)
        pygame.draw.rect(screen, BUTTON_BG, area, border_radius=6)
        pygame.draw.rect(screen, WARN_TEXT, area, 1, border_radius=6)
        question = self.font.render(f"Удалить карту «{self.confirm['name']}»?", True, TEXT)
        screen.blit(question, question.get_rect(center=(box.centerx, box.centery - 30)))
        note = self.small.render("Это нельзя отменить. Опубликованные карты удалить нельзя.", True, TEXT_DIM)
        screen.blit(note, note.get_rect(center=(box.centerx, box.centery - 4)))
        yes, no = self._confirm_buttons()
        mouse = pygame.mouse.get_pos()
        for rect, label, color in (
            (yes, "Удалить", DRAFT_DELETE_COLOR),
            (no, "Отмена", BUTTON_ON if no.collidepoint(mouse) else MENU_BG),
        ):
            pygame.draw.rect(screen, color, rect, border_radius=5)
            text = self.font.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))


class SizePicker:
    """Окно выбора размера новой карты: клик по строке создаёт пустую карту выбранного размера, Esc закрывает."""

    def __init__(self, font, small, presets, modes=None, mode=None):
        self.font = font
        self.small = small
        self.presets = presets
        self.modes = list(modes or [])
        self.mode = mode or (self.modes[0]["key"] if self.modes else None)

    def _top(self):
        return SIZE_HEAD_H + (SIZE_MODE_H if self.modes else 0)

    def box(self):
        height = self._top() + len(self.presets) * SIZE_ROW_H + SIZE_FOOT_H
        rect = pygame.Rect(0, 0, SIZE_W, height)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _row(self, index):
        box = self.box()
        return pygame.Rect(box.x + 18, box.y + self._top() + index * SIZE_ROW_H, box.w - 36, SIZE_ROW_H - 6)

    def _mode_rect(self, index):
        box = self.box()
        return pygame.Rect(box.x + 96 + index * (SIZE_MODE_W + 6), box.y + SIZE_HEAD_H + 2, SIZE_MODE_W, 32)

    def handle_event(self, event):
        """Возвращает (ширина, высота) или (ширина, высота, режим), если режимы заданы; 'cancel' или None."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, mode in enumerate(self.modes):
                if self._mode_rect(index).collidepoint(event.pos):
                    self.mode = mode["key"]
                    return None
            for index, (map_w, map_h, _) in enumerate(self.presets):
                if self._row(index).collidepoint(event.pos):
                    return (map_w, map_h, self.mode) if self.modes else (map_w, map_h)
            if not self.box().collidepoint(event.pos):
                return "cancel"
        return None

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Новая карта: режим и размер" if self.modes else "Размер новой карты", True, TEXT), (box.x + 18, box.y + 14))
        mouse = pygame.mouse.get_pos()
        if self.modes:
            screen.blit(self.small.render("Режим:", True, TEXT_DIM), (box.x + 18, box.y + SIZE_HEAD_H + 10))
            for index, mode in enumerate(self.modes):
                chip = self._mode_rect(index)
                chosen = mode["key"] == self.mode
                pygame.draw.rect(screen, BUTTON_ON if chosen else BUTTON_BG, chip, border_radius=4)
                pygame.draw.rect(screen, ACTIVE_TEXT if chosen else BORDER, chip, 2 if chosen else 1, border_radius=4)
                label = self.font.render(mode["name"], True, TEXT)
                screen.blit(label, label.get_rect(center=chip.center))
        for index, (map_w, map_h, label) in enumerate(self.presets):
            row = self._row(index)
            pygame.draw.rect(screen, BUTTON_ON if row.collidepoint(mouse) else BUTTON_BG, row, border_radius=4)
            text = self.font.render(f"{map_w} × {map_h}  ·  {label}", True, TEXT)
            screen.blit(text, text.get_rect(midleft=(row.x + 12, row.centery)))
        foot = self.small.render("Клик по размеру — создать карту · Esc — отмена", True, TEXT_DIM)
        screen.blit(foot, (box.x + 18, box.bottom - SIZE_FOOT_H + 12))


class WorldPicker:
    """Окно выбора мира для размещения черновика: клик выбирает мир, «Применить» размещает карту в нём."""

    def __init__(self, font, small, worlds, active_names, draft_name):
        self.font = font
        self.small = small
        self.worlds = worlds
        self.active = set(active_names)
        self.draft_name = draft_name
        self.selected = None
        self.message = ""

    def box(self):
        height = WORLD_HEAD_H + len(self.worlds) * WORLD_ROW_H + WORLD_FOOT_H
        rect = pygame.Rect(0, 0, WORLD_W, height)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _row(self, index):
        box = self.box()
        return pygame.Rect(box.x + 18, box.y + WORLD_HEAD_H + index * WORLD_ROW_H, box.w - 36, WORLD_ROW_H - 4)

    def apply_button(self):
        box = self.box()
        return pygame.Rect(box.right - 18 - 160, box.bottom - 44, 160, 34)

    def handle_event(self, event):
        """Возвращает ('apply', мир), 'cancel' или None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.selected is not None:
                return ("apply", self.selected)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.selected is not None and self.apply_button().collidepoint(event.pos):
                return ("apply", self.selected)
            for index, world in enumerate(self.worlds):
                if self._row(index).collidepoint(event.pos):
                    self.selected = world
                    self.message = ""
                    return None
            if not self.box().collidepoint(event.pos):
                return "cancel"
        return None

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Разместить карту в мире", True, TEXT), (box.x + 18, box.y + 14))
        caption = self.small.render(_fit(self.small, f"Карта «{self.draft_name}» будет играть в выбранном мире", box.w - 36), True, TEXT_DIM)
        screen.blit(caption, (box.x + 18, box.y + 36))
        mouse = pygame.mouse.get_pos()
        for index, world in enumerate(self.worlds):
            row = self._row(index)
            chosen = self.selected is not None and self.selected["id"] == world["id"]
            pygame.draw.rect(screen, BUTTON_ON if chosen or row.collidepoint(mouse) else BUTTON_BG, row, border_radius=4)
            screen.blit(self.font.render(world["name"], True, TEXT), (row.x + 12, row.y + 5))
            if world["name"] in self.active:
                marker = self.small.render("сейчас активна", True, ACTIVE_TEXT)
                screen.blit(marker, marker.get_rect(midright=(row.right - 10, row.centery)))
        if self.message:
            foot = self.small.render(self.message, True, WARN_TEXT)
        elif self.selected is None:
            foot = self.small.render("Выберите мир в списке", True, TEXT_DIM)
        else:
            foot = self.small.render("Enter — применить · Esc — отмена", True, TEXT_DIM)
        screen.blit(foot, (box.x + 18, box.bottom - WORLD_FOOT_H + 10))
        button = self.apply_button()
        enabled = self.selected is not None
        pygame.draw.rect(screen, (BUTTON_ON if button.collidepoint(mouse) else BUTTON_BG) if enabled else BUTTON_BG,
                         button, border_radius=4)
        label = self.font.render("Применить", True, TEXT if enabled else TEXT_OFF)
        screen.blit(label, label.get_rect(center=button.center))


class MaskDialog:
    """Окно маски проходимости элемента: сетка 4×4 на тайле, клик по клетке переключает проходимо / непроходимо."""

    def __init__(self, font, small, key, image, tile, mask, blocks):
        self.font = font
        self.small = small
        self.key = key
        self.image = image
        self.tile = tile
        self.cells = list(mask) if mask is not None else [BLOCKED if blocks else FREE] * MASK_CELLS

    def box(self):
        rect = pygame.Rect(0, 0, MASK_W, MASK_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _area(self):
        box = self.box()
        return pygame.Rect(box.x + 18, box.y + MASK_HEAD_H, box.w - 36, MASK_AREA_H)

    def _tile_rect(self):
        area = self._area()
        rect = pygame.Rect(0, 0, self.tile, self.tile)
        rect.centerx = area.centerx
        rect.bottom = area.bottom - 4
        return rect

    def _button_rects(self):
        box = self.box()
        total = len(MASK_BUTTONS) * MASK_BUTTON_W + (len(MASK_BUTTONS) - 1) * MASK_BUTTON_GAP
        x = box.centerx - total // 2
        y = box.y + MASK_BUTTON_Y
        return [
            (action, label, pygame.Rect(x + i * (MASK_BUTTON_W + MASK_BUTTON_GAP), y, MASK_BUTTON_W, MASK_BUTTON_H))
            for i, (action, label) in enumerate(MASK_BUTTONS)
        ]

    def _cell_size(self):
        return self.tile // MASK_SIDE

    def _cell_at(self, pos):
        tile = self._tile_rect()
        if not tile.collidepoint(pos):
            return None
        cell = self._cell_size()
        row = min(MASK_SIDE - 1, (pos[1] - tile.y) // cell)
        col = min(MASK_SIDE - 1, (pos[0] - tile.x) // cell)
        return row * MASK_SIDE + col

    def _cell_rect(self, index):
        tile = self._tile_rect()
        cell = self._cell_size()
        row, col = divmod(index, MASK_SIDE)
        return pygame.Rect(tile.x + col * cell, tile.y + row * cell, cell, cell)

    def _apply(self, action):
        if action == "free":
            self.cells = [FREE] * MASK_CELLS
        elif action == "block":
            self.cells = [BLOCKED] * MASK_CELLS
        elif action == "clear":
            return "clear", None
        else:
            return "save", "".join(self.cells)
        return None

    def handle_event(self, event):
        """Возвращает ('save', маска), ('clear', None), 'cancel' или None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "save", "".join(self.cells)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for action, _, rect in self._button_rects():
                if rect.collidepoint(event.pos):
                    return self._apply(action)
            index = self._cell_at(event.pos)
            if index is not None:
                self.cells[index] = BLOCKED if self.cells[index] == FREE else FREE
                return None
            if not self.box().collidepoint(event.pos):
                return "cancel"
        return None

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render(f"Маска проходимости: {self.key}", True, TEXT), (box.x + 18, box.y + 14))
        caption = "Зелёная клетка — проходимо, красная — блокирует · проход: минимум 3 клетки в ширину и 2 в высоту"
        screen.blit(self.small.render(_fit(self.small, caption, box.w - 36), True, TEXT_DIM), (box.x + 18, box.y + 34))
        tile = self._tile_rect()
        clip = screen.get_clip()
        screen.set_clip(self._area())
        screen.blit(self.image, self.image.get_rect(midbottom=tile.midbottom))
        screen.set_clip(clip)
        for index, value in enumerate(self.cells):
            rect = self._cell_rect(index)
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            overlay.fill((*(MASK_FREE_COLOR if value == FREE else MASK_BLOCK_COLOR), 120))
            screen.blit(overlay, rect)
        cell = self._cell_size()
        for i in range(1, MASK_SIDE):
            pygame.draw.line(screen, BORDER, (tile.x + cell * i, tile.y), (tile.x + cell * i, tile.bottom - 1))
            pygame.draw.line(screen, BORDER, (tile.x, tile.y + cell * i), (tile.right - 1, tile.y + cell * i))
        pygame.draw.rect(screen, TEXT, tile, 1)
        mouse = pygame.mouse.get_pos()
        hovered = self._cell_at(mouse)
        if hovered is not None:
            pygame.draw.rect(screen, VIEW_COLOR, self._cell_rect(hovered), 2)
        for _, label, rect in self._button_rects():
            pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(mouse) else BUTTON_BG, rect, border_radius=4)
            text = self.font.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))
        foot = self.small.render("Клик по клетке — переключить · Enter — сохранить · Esc — отмена", True, TEXT_DIM)
        screen.blit(foot, (box.x + 18, box.bottom - MASK_FOOT_H + 12))


class SaveDialog:
    """Окно сохранения черновика: название, кнопка «Сохранить» и список существующих черновиков.
    Если название совпадает с уже сохранённым черновиком, сначала спрашивает подтверждение перезаписи."""

    def __init__(self, font, small, drafts, name, max_length):
        self.font = font
        self.small = small
        self.drafts = drafts
        self.text = name
        self.max_length = max_length
        self.scroll = 0
        self.message = ""
        self.overwrite = None

    def box(self):
        rect = pygame.Rect(0, 0, SAVE_W, SAVE_LIST_TOP + DRAFT_ROWS * DRAFT_ROW_H + SAVE_FOOT_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def field(self):
        box = self.box()
        return pygame.Rect(box.x + 18, box.y + 46, box.w - 36 - SAVE_BUTTON_W - 10, 34)

    def save_button(self):
        field = self.field()
        return pygame.Rect(field.right + 10, field.y, SAVE_BUTTON_W, field.h)

    def row_at(self, pos):
        return _row_at(pos, self.box(), SAVE_LIST_TOP, self.drafts, self.scroll)

    def confirm_box(self):
        rect = pygame.Rect(0, 0, CONFIRM_W, CONFIRM_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def confirm_buttons(self):
        box = self.confirm_box()
        yes = pygame.Rect(box.x + 18, box.bottom - 50, CONFIRM_BUTTON_W, 34)
        no = pygame.Rect(box.right - 18 - CONFIRM_BUTTON_W, box.bottom - 50, CONFIRM_BUTTON_W, 34)
        return yes, no

    def handle_event(self, event):
        """Возвращает ('save', название, id перезаписываемого черновика или None), 'cancel' или None."""
        if self.overwrite is not None:
            return self._confirm_event(event)
        if event.type == pygame.KEYDOWN:
            return self._key(event)
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = _scroll_offset(self.scroll, event.y, len(self.drafts))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._click(event.pos)
        return None

    def submit(self):
        name = self.text.strip()
        if not name:
            self.message = "Введите название черновика"
            return None
        existing = next((draft for draft in self.drafts if draft["name"] == name), None)
        if existing is None:
            return ("save", name, None)
        self.overwrite = existing
        return None

    def _key(self, event):
        if event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self.submit()
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
            self.text += event.unicode
        self.message = ""
        return None

    def _click(self, pos):
        if self.save_button().collidepoint(pos):
            return self.submit()
        draft = self.row_at(pos)
        if draft is not None:
            self.text = draft["name"]
            self.message = ""
            return None
        if not self.box().collidepoint(pos):
            return "cancel"
        return None

    def _confirm_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._confirmed_save()
            if event.key == pygame.K_ESCAPE:
                self.overwrite = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            yes, no = self.confirm_buttons()
            if yes.collidepoint(event.pos):
                return self._confirmed_save()
            if no.collidepoint(event.pos):
                self.overwrite = None
        return None

    def _confirmed_save(self):
        draft = self.overwrite
        self.overwrite = None
        return ("save", draft["name"], draft["id"])

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Сохранить черновик", True, TEXT), (box.x + 18, box.y + 14))
        field = self.field()
        pygame.draw.rect(screen, BUTTON_BG, field, border_radius=4)
        pygame.draw.rect(screen, BORDER, field, 1, border_radius=4)
        shown = self.text
        while shown and self.font.size(shown + "|")[0] > field.w - 16:
            shown = shown[1:]
        screen.blit(self.font.render(shown + "|", True, TEXT), (field.x + 8, field.y + 7))
        button = self.save_button()
        hovered = button.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, BUTTON_ON if hovered else BUTTON_BG, button, border_radius=4)
        label = self.font.render("Сохранить", True, TEXT)
        screen.blit(label, label.get_rect(center=button.center))
        caption = self.small.render("Существующие черновики: клик выбирает название", True, TEXT_DIM)
        screen.blit(caption, (box.x + 18, box.y + SAVE_LIST_TOP - 22))
        if not self.drafts:
            empty = self.small.render("Черновиков пока нет", True, TEXT_DIM)
            screen.blit(empty, (box.x + 18, box.y + SAVE_LIST_TOP + 8))
        hovered_draft = self.row_at(pygame.mouse.get_pos()) if self.overwrite is None else None
        _draw_rows(screen, self.font, self.small, self.drafts, self.scroll, box, SAVE_LIST_TOP, hovered_draft)
        if self.message:
            foot = self.small.render(self.message, True, WARN_TEXT)
        else:
            foot = self.small.render("Enter — сохранить · Esc — отмена · колесо — прокрутка", True, TEXT_DIM)
        screen.blit(foot, (box.x + 18, box.bottom - SAVE_FOOT_H + 12))
        if self.overwrite is not None:
            self._draw_confirm(screen)

    def _draw_confirm(self, screen):
        box = self.confirm_box()
        _panel(screen, box)
        screen.blit(self.font.render("Перезаписать черновик?", True, TEXT), (box.x + 18, box.y + 16))
        question = f"«{self.overwrite['name']}» уже сохранён и будет заменён"
        screen.blit(self.small.render(_fit(self.small, question, box.w - 36), True, TEXT_DIM), (box.x + 18, box.y + 46))
        yes, no = self.confirm_buttons()
        mouse = pygame.mouse.get_pos()
        for button, text, active in ((yes, "Перезаписать (Enter)", yes.collidepoint(mouse)),
                                     (no, "Отмена (Esc)", no.collidepoint(mouse))):
            pygame.draw.rect(screen, BUTTON_ON if active else BUTTON_BG, button, border_radius=4)
            label = self.small.render(text, True, TEXT)
            screen.blit(label, label.get_rect(center=button.center))


MOB_W = 1040
MOB_H = 780
MOB_FIELDS = [
    ("move_speed", "Скорость передвижения", "px/с", 5.0, "{:.0f}"),
    ("windup", "Скорость замаха", "с", 0.05, "{:.2f}"),
    ("backswing", "Скорость отката после удара", "с", 0.05, "{:.2f}"),
    ("aggro_tiles", "Агрессия: радиус", "тайлов", 0.5, "{:.1f}"),
    ("respawn_seconds", "Респаун: время до возрождения", "", 5.0, None),
    ("reward_copper", "Награда: монеты при смерти", "мед.", 5.0, "{:.0f}"),
]
# Кукла экипировки: слот -> (колонка, строка, подпись), как в окне персонажа
EQUIP_SLOT_CELLS = {
    "ears": (0, 0, "Серьги"), "head": (2, 0, "Голова"), "neck": (4, 0, "Шея"),
    "back": (0, 1, "Плащ"), "body": (2, 1, "Доспех"), "ring": (4, 1, "Кольцо"),
    "hands": (0, 2, "Руки"), "weapon": (1, 2, "П рука"), "belt": (2, 2, "Пояс"),
    "shield": (3, 2, "Л рука"), "ring_2": (4, 2, "Кольцо"),
    "legs": (2, 3, "Ноги"), "feet": (2, 4, "Обувь"),
}
EQUIP_W, EQUIP_H = 740, 560
EQUIP_CELL_W, EQUIP_CELL_H, EQUIP_GAP = 124, 54, 12
EQUIP_PICKER_W, EQUIP_ROW_H, EQUIP_PICKER_ROWS = 480, 34, 9
MOB_BTN = 32
XP_STEP = 5
MOB_PATROL_CELL = 24
MOB_PATROL_PRESETS = [("clear", "Очистить"), ("circle3", "Круг 3"), ("circle6", "Круг 6")]
PATROL_FILL = (86, 160, 220)
PATROL_ANCHOR_COLOR = (255, 220, 90)


class EquipmentDialog:
    """Окно экипировки моба: кукла по слотам. Клик по ячейке открывает список предметов, которые подходят виду
    по характеристикам и уровню (requirements предмета в базе). Пустая ячейка значит без предмета.

    equipment: слот -> id предмета, меняется на месте. items: предметы экипировки из базы.
    """

    def __init__(self, font, small, mob_name, stats, level, equipment, items):
        self.font = font
        self.small = small
        self.mob_name = mob_name
        self.stats = stats
        self.level = level
        self.equipment = equipment
        self.items = {int(item["id"]): item for item in items}
        self.by_slot = {slot: [] for slot in mob_modes.MOB_EQUIPMENT_SLOTS}
        for item in items:
            if item.get("equip_slot") in self.by_slot:
                self.by_slot[item["equip_slot"]].append(item)
        self.picker_slot = None
        self.picker_scroll = 0

    def box(self):
        rect = pygame.Rect(0, 0, EQUIP_W, EQUIP_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _cell(self, slot):
        col, row, _label = EQUIP_SLOT_CELLS[slot]
        box = self.box()
        return pygame.Rect(
            box.x + 24 + col * (EQUIP_CELL_W + EQUIP_GAP), box.y + 70 + row * (EQUIP_CELL_H + EQUIP_GAP),
            EQUIP_CELL_W, EQUIP_CELL_H,
        )

    def _done_rect(self):
        box = self.box()
        return pygame.Rect(box.right - 164, box.bottom - 56, 140, 40)

    def _eligible(self, slot):
        """Варианты для слота: None («пусто») и предметы, которые подходят виду."""
        fitting = [item for item in self.by_slot[slot] if mob_modes.item_fits_mob(item, self.stats, self.level)]
        return [None] + fitting

    def _picker_rect(self):
        box = self.box()
        rows = min(EQUIP_PICKER_ROWS, len(self._eligible(self.picker_slot)))
        height = 52 + rows * EQUIP_ROW_H
        return pygame.Rect(box.centerx - EQUIP_PICKER_W // 2, box.y + 70, EQUIP_PICKER_W, height)

    def _picker_row(self, picker, row):
        return pygame.Rect(picker.x + 8, picker.y + 44 + row * EQUIP_ROW_H, picker.w - 16, EQUIP_ROW_H - 4)

    def _requirement_text(self, item):
        requirements = dict((item.get("effects") or {}).get("requirements") or {})
        level = int(requirements.pop("level", 1))
        labels = dict(mob_modes.STAT_LABELS)
        parts = [f"{labels.get(stat, stat)} {value}" for stat, value in requirements.items()]
        parts.append(f"ур. {level}")
        return ", ".join(parts)

    def handle_event(self, event):
        """Возвращает "close", когда окно закрывается; None, если окно остаётся открытым."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.picker_slot is not None:
                self.picker_slot = None
                return None
            return "close"
        if event.type == pygame.MOUSEWHEEL and self.picker_slot is not None:
            total = len(self._eligible(self.picker_slot))
            self.picker_scroll = max(0, min(self.picker_scroll - event.y, max(0, total - EQUIP_PICKER_ROWS)))
            return None
        if event.type != pygame.MOUSEBUTTONDOWN or event.button not in (1, 3):
            return None
        if self.picker_slot is not None:
            if event.button == 3:
                self.picker_slot = None
            else:
                self._pick(event.pos)
            return None
        if event.button == 1:
            for slot in EQUIP_SLOT_CELLS:
                if self._cell(slot).collidepoint(event.pos):
                    self.picker_slot = slot
                    self.picker_scroll = 0
                    return None
            if self._done_rect().collidepoint(event.pos):
                return "close"
        return None

    def _pick(self, pos):
        picker = self._picker_rect()
        if not picker.collidepoint(pos):
            self.picker_slot = None
            return
        options = self._eligible(self.picker_slot)
        for row in range(EQUIP_PICKER_ROWS):
            index = self.picker_scroll + row
            if index >= len(options):
                break
            if self._picker_row(picker, row).collidepoint(pos):
                choice = options[index]
                self.equipment[self.picker_slot] = None if choice is None else int(choice["id"])
                self.picker_slot = None
                return

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render(f"Экипировка: {self.mob_name}", True, TEXT), (box.x + 24, box.y + 18))
        screen.blit(
            self.small.render("Клик по ячейке выбирает предмет. В списке только предметы, которые подходят по характеристикам и уровню", True, TEXT_DIM),
            (box.x + 24, box.y + 44),
        )
        mouse = pygame.mouse.get_pos()
        for slot, (_col, _row, label) in EQUIP_SLOT_CELLS.items():
            cell = self._cell(slot)
            pygame.draw.rect(screen, BUTTON_ON if cell.collidepoint(mouse) else BUTTON_BG, cell, border_radius=6)
            pygame.draw.rect(screen, BORDER, cell, 1, border_radius=6)
            screen.blit(self.small.render(label, True, TEXT_DIM), (cell.x + 8, cell.y + 5))
            item_id = self.equipment.get(slot)
            if item_id is None:
                screen.blit(self.font.render("пусто", True, TEXT_DIM), (cell.x + 8, cell.y + 26))
                continue
            item = self.items.get(item_id)
            name = item["name"] if item else f"предмет #{item_id}"
            fits = item is not None and mob_modes.item_fits_mob(item, self.stats, self.level)
            screen.blit(self.font.render(_fit(self.font, name, cell.w - 16), True, TEXT if fits else WARN_TEXT), (cell.x + 8, cell.y + 26))
        done = self._done_rect()
        pygame.draw.rect(screen, BUTTON_ON if done.collidepoint(mouse) else BUTTON_BG, done, border_radius=5)
        label = self.font.render("Готово", True, TEXT)
        screen.blit(label, label.get_rect(center=done.center))
        if self.picker_slot is not None:
            self._draw_picker(screen, mouse)

    def _draw_picker(self, screen, mouse):
        picker = self._picker_rect()
        pygame.draw.rect(screen, MENU_BG, picker, border_radius=8)
        pygame.draw.rect(screen, ACTIVE_TEXT, picker, 2, border_radius=8)
        slot_label = EQUIP_SLOT_CELLS[self.picker_slot][2]
        screen.blit(self.font.render(f"Слот: {slot_label}", True, TEXT), (picker.x + 12, picker.y + 10))
        options = self._eligible(self.picker_slot)
        hidden = len(self.by_slot[self.picker_slot]) - (len(options) - 1)
        if hidden:
            note = self.small.render(f"скрыто по требованиям: {hidden}", True, TEXT_DIM)
            screen.blit(note, (picker.right - note.get_width() - 12, picker.y + 14))
        if len(options) == 1:
            screen.blit(self.small.render("нет подходящих предметов для этого вида", True, TEXT_DIM), (picker.x + 12, picker.y + 44))
        current = self.equipment.get(self.picker_slot)
        for row in range(EQUIP_PICKER_ROWS):
            index = self.picker_scroll + row
            if index >= len(options):
                break
            item = options[index]
            rect = self._picker_row(picker, row)
            chosen = (None if item is None else int(item["id"])) == current
            pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(mouse) or chosen else BUTTON_BG, rect, border_radius=4)
            if item is None:
                screen.blit(self.font.render("пусто (без предмета)", True, TEXT), (rect.x + 8, rect.y + 6))
                continue
            screen.blit(self.font.render(_fit(self.font, item["name"], rect.w * 0.45), True, TEXT), (rect.x + 8, rect.y + 6))
            requirements = _fit(self.small, self._requirement_text(item), rect.w * 0.5)
            width = self.small.size(requirements)[0]
            screen.blit(self.small.render(requirements, True, TEXT_DIM), (rect.right - width - 8, rect.y + 9))


class MobParamsDialog:
    """Окно параметров вида моба в режиме: скорости, агрессия, состояние, характеристики, награда, экипировка и поле патруля 18×18.

    equipment_items — предметы экипировки из базы (словари с id, name, equip_slot). handle_event возвращает ("save", настройки), "cancel" или None.
    """

    def __init__(self, font, small, mob_name, mode_name, settings, equipment_items=()):
        self.font = font
        self.small = small
        self.mob_name = mob_name
        self.mode_name = mode_name
        self.values = {key: float(settings[key]) for key, *_ in MOB_FIELDS}
        self.state = settings["state"]
        self.stats = dict(settings["stats"])
        self.level = int(settings["level"])
        self.reward_xp = int(settings["reward_xp"])

        # Предмет, которого нет в списке (например, сервер недоступен), остаётся в настройках, а не сбрасывается
        current = settings.get("equipment") or {}
        self.equipment = {slot: current.get(slot) for slot in mob_modes.MOB_EQUIPMENT_SLOTS}
        self.equipment_items = list(equipment_items)
        self.equipment_window = None

        anchor = mob_modes.PATROL_ANCHOR
        self.patrol = {(dx + anchor, dy + anchor) for dx, dy in settings["patrol"]}
        self.painting = None
        self.message = ""

    # --- раскладка ---
    def box(self):
        rect = pygame.Rect(0, 0, MOB_W, MOB_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _field_rects(self, index):
        box = self.box()
        y = box.y + 70 + index * 40
        minus = pygame.Rect(box.x + 24 + 310, y, MOB_BTN, 30)
        value = pygame.Rect(minus.right + 4, y, 84, 30)
        plus = pygame.Rect(value.right + 4, y, MOB_BTN, 30)
        return minus, value, plus, pygame.Rect(box.x + 24, y, plus.right - box.x - 24, 30)

    def _state_rect(self, index):
        box = self.box()
        return pygame.Rect(box.x + 24 + index * 158, box.y + 358, 150, 36)

    def _stat_rects(self, index):
        box = self.box()
        x = box.x + 24 + (index % 2) * 236
        y = box.y + 568 + (index // 2) * 40
        minus = pygame.Rect(x + 118, y, 30, 30)
        value = pygame.Rect(minus.right + 4, y, 40, 30)
        plus = pygame.Rect(value.right + 4, y, 30, 30)
        return minus, value, plus

    def _level_rects(self):
        box = self.box()
        minus = pygame.Rect(box.x + 24 + 118, box.y + 482, 30, 30)
        value = pygame.Rect(minus.right + 4, minus.y, 40, 30)
        plus = pygame.Rect(value.right + 4, minus.y, 30, 30)
        return minus, value, plus

    def _xp_rects(self):
        """Строка «Награда ХР» сразу под уровнем: та же колонка, что у уровня."""
        level_minus, _level_value, _level_plus = self._level_rects()
        minus = pygame.Rect(level_minus.x, level_minus.bottom + 10, 30, 30)
        value = pygame.Rect(minus.right + 4, minus.y, 84, 30)
        plus = pygame.Rect(value.right + 4, minus.y, 30, 30)
        return minus, value, plus

    def _grid_origin(self):
        box = self.box()
        return box.x + 560, box.y + 90

    def _cell_at(self, pos):
        gx, gy = self._grid_origin()
        cx, cy = (pos[0] - gx) // MOB_PATROL_CELL, (pos[1] - gy) // MOB_PATROL_CELL
        if pos[0] >= gx and pos[1] >= gy and 0 <= cx < mob_modes.PATROL_SIZE and 0 <= cy < mob_modes.PATROL_SIZE:
            return cx, cy
        return None

    def _preset_rect(self, index):
        gx, gy = self._grid_origin()
        return pygame.Rect(gx + index * 112, gy + mob_modes.PATROL_SIZE * MOB_PATROL_CELL + 14, 104, 32)

    def _save_rect(self):
        box = self.box()
        return pygame.Rect(box.x + 24, box.bottom - 60, 240, 40)

    def _cancel_rect(self):
        box = self.box()
        return pygame.Rect(box.x + 276, box.bottom - 60, 140, 40)

    def _equipment_button_rect(self):
        box = self.box()
        return pygame.Rect(box.x + 560, box.y + 640, 200, 36)

    # --- значения ---
    def settings(self):
        anchor = mob_modes.PATROL_ANCHOR
        return {
            **{key: self.values[key] for key, *_ in MOB_FIELDS},
            "level": self.level,
            "reward_xp": self.reward_xp,
            "state": self.state,
            "stats": dict(self.stats),
            "equipment": dict(self.equipment),
            "patrol": [[cx - anchor, cy - anchor] for cx, cy in sorted(self.patrol, key=lambda c: (c[1], c[0]))],
        }

    def _step_field(self, index, direction):
        key, _label, _unit, step, _fmt = MOB_FIELDS[index]
        low, high = mob_modes.LIMITS[key]
        self.values[key] = round(max(low, min(high, self.values[key] + direction * step)), 2)

    def _step_stat(self, index, direction):
        """+ тратит свободное очко, − возвращает его; выносливость задаётся уровнем и не меняется."""
        key = mob_modes.STAT_LABELS[index][0]
        if key == "endurance":
            return
        if direction > 0:
            if mob_modes.free_points(self.level, self.stats) > 0:
                self.stats[key] += 1
        elif self.stats[key] > mob_modes.STAT_MIN:
            self.stats[key] -= 1

    def _step_level(self, direction):
        """Смена уровня меняет выносливость и число свободных очков; лишние очки снимаются с последних характеристик."""
        level = max(mob_modes.LEVEL_MIN, min(mob_modes.LEVEL_CAP, self.level + direction))
        if level == self.level:
            return
        self.level = level
        self.stats["endurance"] = mob_modes.endurance_for_level(level)
        for key in reversed(mob_modes.ALLOCATABLE_STATS):
            while mob_modes.free_points(level, self.stats) < 0 and self.stats[key] > mob_modes.STAT_MIN:
                self.stats[key] -= 1

    def _step_xp(self, direction):
        low, high = mob_modes.LIMITS["reward_xp"]
        self.reward_xp = int(max(low, min(high, self.reward_xp + direction * XP_STEP)))

    def _apply_preset(self, preset):
        size, anchor = mob_modes.PATROL_SIZE, mob_modes.PATROL_ANCHOR
        if preset == "clear":
            self.patrol = set()
            return
        radius = 3 if preset == "circle3" else 6
        self.patrol = {
            (cx, cy)
            for cx in range(size) for cy in range(size)
            if (cx - anchor) ** 2 + (cy - anchor) ** 2 <= radius * radius
        }

    # --- события ---
    def handle_event(self, event):
        if self.equipment_window is not None:
            if self.equipment_window.handle_event(event) == "close":
                self.equipment_window = None
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.type == pygame.MOUSEBUTTONUP:
            self.painting = None
        elif event.type == pygame.MOUSEMOTION and self.painting is not None:
            self._paint(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self._wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            return self._press(event)
        return None

    def _wheel(self, steps):
        mouse = pygame.mouse.get_pos()
        for index in range(len(MOB_FIELDS)):
            if self._field_rects(index)[3].collidepoint(mouse):
                self._step_field(index, steps)
                return

    def _paint(self, pos):
        cell = self._cell_at(pos)
        if cell is None:
            return
        if self.painting == 1:
            self.patrol.add(cell)
        else:
            self.patrol.discard(cell)

    def _press(self, event):
        pos = event.pos
        if event.button == 3:
            if self._cell_at(pos) is not None:
                self.painting = 3
                self._paint(pos)
            return None
        if self._save_rect().collidepoint(pos):
            try:
                return "save", mob_modes.validate_settings(self.settings())
            except ValueError as error:
                self.message = str(error)
                return None
        if self._cancel_rect().collidepoint(pos):
            return "cancel"
        if self._equipment_button_rect().collidepoint(pos):
            self.equipment_window = EquipmentDialog(
                self.font, self.small, self.mob_name, self.stats, self.level, self.equipment, self.equipment_items,
            )
            return None
        for index in range(len(MOB_FIELDS)):
            minus, _value, plus, _row = self._field_rects(index)
            if minus.collidepoint(pos):
                self._step_field(index, -1)
                return None
            if plus.collidepoint(pos):
                self._step_field(index, 1)
                return None
        for index, state in enumerate(mob_modes.STATES):
            if self._state_rect(index).collidepoint(pos):
                self.state = state
                return None
        level_minus, _level_value, level_plus = self._level_rects()
        if level_minus.collidepoint(pos):
            self._step_level(-1)
            return None
        if level_plus.collidepoint(pos):
            self._step_level(1)
            return None
        xp_minus, _xp_value, xp_plus = self._xp_rects()
        if xp_minus.collidepoint(pos):
            self._step_xp(-1)
            return None
        if xp_plus.collidepoint(pos):
            self._step_xp(1)
            return None
        for index in range(len(mob_modes.STAT_LABELS)):
            minus, _value, plus = self._stat_rects(index)
            if minus.collidepoint(pos):
                self._step_stat(index, -1)
                return None
            if plus.collidepoint(pos):
                self._step_stat(index, 1)
                return None
        for index, (preset, _label) in enumerate(MOB_PATROL_PRESETS):
            if self._preset_rect(index).collidepoint(pos):
                self._apply_preset(preset)
                return None
        if self._cell_at(pos) is not None:
            self.painting = 1
            self._paint(pos)
        return None

    # --- рисование ---
    def _stepper(self, screen, minus, value, plus, text, enabled=True):
        mouse = pygame.mouse.get_pos()
        for rect, sign in ((minus, "−"), (plus, "+")):
            hovered = enabled and rect.collidepoint(mouse)
            pygame.draw.rect(screen, BUTTON_ON if hovered else BUTTON_BG, rect, border_radius=4)
            label = self.font.render(sign, True, TEXT if enabled else TEXT_OFF)
            screen.blit(label, label.get_rect(center=rect.center))
        pygame.draw.rect(screen, MENU_BG, value, border_radius=4)
        pygame.draw.rect(screen, BORDER, value, 1, border_radius=4)
        label = self.font.render(text, True, TEXT)
        screen.blit(label, label.get_rect(center=value.center))

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        title = f"Параметры: {self.mob_name}  ·  режим «{self.mode_name}»"
        screen.blit(self.font.render(title, True, TEXT), (box.x + 24, box.y + 18))
        screen.blit(self.small.render("Параметры относятся к виду моба: их получают все такие мобы во всех мирах режима", True, TEXT_DIM), (box.x + 24, box.y + 44))

        for index, (key, label, unit, _step, fmt) in enumerate(MOB_FIELDS):
            minus, value, plus, row = self._field_rects(index)
            screen.blit(self.font.render(label, True, TEXT), (row.x, row.y + 5))
            text = mob_modes.format_hms(self.values[key]) if fmt is None else fmt.format(self.values[key])
            self._stepper(screen, minus, value, plus, text)
            screen.blit(self.small.render(unit, True, TEXT_DIM), (plus.right + 8, plus.y + 8))

        screen.blit(self.font.render("Состояние", True, ACTIVE_TEXT), (box.x + 24, box.y + 330))
        for index, state in enumerate(mob_modes.STATES):
            rect = self._state_rect(index)
            chosen = state == self.state
            pygame.draw.rect(screen, BUTTON_ON if chosen else BUTTON_BG, rect, border_radius=4)
            pygame.draw.rect(screen, ACTIVE_TEXT if chosen else BORDER, rect, 2 if chosen else 1, border_radius=4)
            label = self.font.render(mob_modes.STATE_LABELS[state], True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))
        hint_y = box.y + 404
        for line in self._wrap(mob_modes.STATE_HINTS[self.state], 466):
            screen.blit(self.small.render(line, True, TEXT_DIM), (box.x + 24, hint_y))
            hint_y += 18

        screen.blit(self.font.render("Характеристики", True, ACTIVE_TEXT), (box.x + 24, box.y + 454))
        level_minus, level_value, level_plus = self._level_rects()
        screen.blit(self.font.render("Уровень", True, TEXT), (level_minus.x - 118, level_minus.y + 5))
        self._stepper(screen, level_minus, level_value, level_plus, str(self.level))
        xp_minus, xp_value, xp_plus = self._xp_rects()
        screen.blit(self.font.render("Награда ХР", True, TEXT), (xp_minus.x - 118, xp_minus.y + 5))
        self._stepper(screen, xp_minus, xp_value, xp_plus, str(self.reward_xp))
        screen.blit(
            self.small.render("делится по доле урона", True, TEXT_DIM),
            (xp_plus.right + 24, xp_plus.y + 8),
        )
        free = mob_modes.free_points(self.level, self.stats)
        total = mob_modes.free_points_for_level(self.level)
        screen.blit(
            self.font.render(f"Свободных очков: {free} из {total}", True, ACTIVE_TEXT if free > 0 else TEXT_DIM),
            (level_plus.right + 24, level_plus.y + 5),
        )
        for index, (key, label) in enumerate(mob_modes.STAT_LABELS):
            minus, value, plus = self._stat_rects(index)
            screen.blit(self.font.render(label, True, TEXT), (minus.x - 118, minus.y + 5))
            self._stepper(screen, minus, value, plus, str(self.stats[key]), enabled=key != "endurance")
        screen.blit(
            self.small.render(f"Выносливость задаётся уровнем: {mob_modes.endurance_for_level(self.level)}", True, TEXT_DIM),
            (box.x + 24, self._stat_rects(4)[0].bottom + 8),
        )

        self._draw_patrol(screen, box)

        screen.blit(self.font.render("Экипировка", True, ACTIVE_TEXT), (box.x + 560, box.y + 610))
        equip_button = self._equipment_button_rect()
        mouse = pygame.mouse.get_pos()
        pygame.draw.rect(screen, BUTTON_ON if equip_button.collidepoint(mouse) else BUTTON_BG, equip_button, border_radius=5)
        pygame.draw.rect(screen, BORDER, equip_button, 1, border_radius=5)
        label = self.font.render("Открыть экипировку", True, TEXT)
        screen.blit(label, label.get_rect(center=equip_button.center))
        filled = sum(1 for item_id in self.equipment.values() if item_id is not None)
        screen.blit(
            self.small.render(f"надето: {filled} из {len(mob_modes.MOB_EQUIPMENT_SLOTS)}", True, TEXT_DIM),
            (equip_button.right + 14, equip_button.y + 10),
        )
        save, cancel = self._save_rect(), self._cancel_rect()
        mouse = pygame.mouse.get_pos()
        pygame.draw.rect(screen, (70, 130, 80) if save.collidepoint(mouse) else (56, 106, 66), save, border_radius=5)
        pygame.draw.rect(screen, BUTTON_ON if cancel.collidepoint(mouse) else BUTTON_BG, cancel, border_radius=5)
        for rect, text in ((save, "Сохранить изменения"), (cancel, "Отмена")):
            label = self.font.render(text, True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))
        if self.message:
            screen.blit(self.small.render(self.message, True, WARN_TEXT), (cancel.right + 18, cancel.y + 12))
        if self.equipment_window is not None:
            self.equipment_window.draw(screen)

    def _draw_patrol(self, screen, box):
        gx, gy = self._grid_origin()
        size, cell = mob_modes.PATROL_SIZE, MOB_PATROL_CELL
        screen.blit(self.font.render("Патруль", True, ACTIVE_TEXT), (gx, box.y + 62))
        screen.blit(self.small.render(f"клеток: {len(self.patrol)} · ЛКМ — закрасить, ПКМ — стереть", True, TEXT_DIM), (gx + 80, box.y + 66))
        pygame.draw.rect(screen, (16, 18, 22), (gx, gy, size * cell, size * cell))
        for cy in range(size):
            for cx in range(size):
                rect = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
                if (cx, cy) in self.patrol:
                    pygame.draw.rect(screen, PATROL_FILL, rect.inflate(-2, -2))
                pygame.draw.rect(screen, (44, 48, 56), rect, 1)
        anchor = mob_modes.PATROL_ANCHOR
        mark = pygame.Rect(gx + anchor * cell, gy + anchor * cell, cell, cell)
        pygame.draw.rect(screen, PATROL_ANCHOR_COLOR, mark, 2)
        pygame.draw.line(screen, PATROL_ANCHOR_COLOR, mark.topleft, mark.bottomright, 1)
        pygame.draw.line(screen, PATROL_ANCHOR_COLOR, mark.topright, mark.bottomleft, 1)
        mouse = pygame.mouse.get_pos()
        for index, (_preset, label) in enumerate(MOB_PATROL_PRESETS):
            rect = self._preset_rect(index)
            pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(mouse) else BUTTON_BG, rect, border_radius=4)
            text = self.small.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))
        screen.blit(self.small.render("Жёлтый крест — точка появления моба", True, TEXT_DIM), (gx, self._preset_rect(0).bottom + 8))

    def _wrap(self, text, width):
        lines, current = [], ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and self.small.size(candidate)[0] > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        return lines + ([current] if current else [])
