"""Окно «Новый предмет» в редакторе карт: название, слот, требования, характеристики и бои предмета."""
import copy

import pygame

from core import item_form, item_icons, mob_modes
from scenes.map_editor_ui import ACTIVE_TEXT, BORDER, BUTTON_BG, BUTTON_ON, MENU_BG, TEXT, TEXT_DIM, WARN_TEXT, _fit, _panel, _shade

ITEM_W, ITEM_H = 1140, 690
ICON_CELL = 84
ICON_COLS = 6
ICON_ROWS = 5
ICON_IMG = 52
ROW_H = 34
LABEL_W = 170
CTRL_X = 170
SLOT_LABELS = dict(
    (slot, label) for slot, label in (
        ("head", "Голова"), ("ears", "Серьги"), ("neck", "Шея"), ("back", "Плащ"), ("body", "Доспех"),
        ("hands", "Руки"), ("weapon", "Правая рука"), ("shield", "Левая рука"), ("belt", "Пояс"),
        ("ring", "Кольцо 1"), ("ring_2", "Кольцо 2"), ("legs", "Ноги"), ("feet", "Обувь"),
    )
)

# (ключ, подпись, вид, шаг, от, до). Ключи req:<стат> и bon:<стат> — требования и характеристики предмета
COLUMNS = (
    [
        ("name", "Название", "text", 0, 0, 0),
        ("slot", "Слот", "slot", 0, 0, 0),
        ("icon", "Иконка", "icon", 0, 0, 0),
        ("two_handed", "Обе руки (двуручный)", "flag", 0, 0, 0),
        ("windup_percent", "Скорость замаха, %", "int", 5, -90, 200),
        ("recovery_percent", "Восстановление, %", "int", 5, -90, 200),
        ("move_speed_percent", "Скорость передвижения, %", "int", 5, -90, 200),
        ("damage_min", "Урон от", "int", 1, 0, 999),
        ("damage_max", "Урон до", "int", 1, 0, 999),
        ("price", "Цена, мед.", "int", 100, 0, item_form.MAX_PRICE),
    ],
    [("header", "Требование", "", 0, 0, 0), ("level", "Уровень", "int", 1, 1, item_form.MAX_LEVEL)]
    + [(f"req:{stat}", label, "int", 1, 0, item_form.MAX_STAT) for stat, label in mob_modes.STAT_LABELS]
    + [("header", "Характеристики предмета", "", 0, 0, 0)]
    + [(f"bon:{stat}", label, "int", 1, 0, item_form.MAX_STAT) for stat, label in mob_modes.STAT_LABELS],
    [
        ("header", "Бой", "", 0, 0, 0),
        ("dodge", "Уворот, %", "int", 1, 0, 100),
        ("anti_dodge", "Анти уворот, %", "int", 1, 0, 100),
        ("crit", "Крит, %", "int", 1, 0, 100),
        ("anti_crit", "Крит антикрит, %", "int", 1, 0, 100),
        ("crit_power", "Сила крита, %", "int", 5, 0, 500),
        ("block", "Блок, %", "int", 1, 0, 100),
        ("hp", "ХП", "int", 10, 0, item_form.MAX_HP),
        ("mp", "МП", "int", 10, 0, item_form.MAX_HP),
        ("magic_damage", "Маг урон", "int", 1, 0, item_form.MAX_DAMAGE),
    ],
)
COLUMN_X = (24, 380, 736)


class ItemFormDialog:
    """handle_event возвращает ("save", форма), "cancel" или None. Проверку и отправку делает редактор карт."""

    def __init__(self, font, small):
        self.font = font
        self.small = small
        self.form = item_form.default_form()
        self.focus = None
        self.message = ""
        self.icon_options = None  # открытый выбор иконки: [None, ключ, ...]
        self.icon_scroll = 0  # прокрутка выбора в строках сетки
        self._thumbs = {}

    def box(self):
        rect = pygame.Rect(0, 0, ITEM_W, ITEM_H)
        rect.center = pygame.display.get_surface().get_rect().center
        return rect

    def _entries(self):
        """Строки формы с их положением: (спецификация, x, y)."""
        box = self.box()
        entries = []
        for column, specs in enumerate(COLUMNS):
            for row, spec in enumerate(specs):
                entries.append((spec, box.x + COLUMN_X[column], box.y + 80 + row * ROW_H))
        return entries

    def _controls(self, spec, x, y):
        key, _label, kind, *_ = spec
        if kind == "text":
            return {"field": pygame.Rect(x + CTRL_X, y, 160, 28)}
        if kind == "slot":
            return {
                "prev": pygame.Rect(x + CTRL_X, y, 28, 28),
                "value": pygame.Rect(x + CTRL_X + 32, y, 120, 28),
                "next": pygame.Rect(x + CTRL_X + 156, y, 28, 28),
            }
        if kind == "flag":
            return {"box": pygame.Rect(x + CTRL_X, y + 3, 22, 22)}
        if kind == "icon":
            return {"button": pygame.Rect(x + CTRL_X, y, 160, 28)}
        return {
            "minus": pygame.Rect(x + CTRL_X, y, 28, 28),
            "value": pygame.Rect(x + CTRL_X + 32, y, 72, 28),
            "plus": pygame.Rect(x + CTRL_X + 108, y, 28, 28),
        }

    def _save_rect(self):
        box = self.box()
        return pygame.Rect(box.x + 24, box.bottom - 56, 240, 40)

    def _cancel_rect(self):
        box = self.box()
        return pygame.Rect(box.x + 276, box.bottom - 56, 140, 40)

    def _get(self, key):
        if key.startswith("req:"):
            return self.form["requirements"][key[4:]]
        if key.startswith("bon:"):
            return self.form["bonuses"][key[4:]]
        return self.form[key]

    def _set(self, key, value):
        if key.startswith("req:"):
            self.form["requirements"][key[4:]] = value
        elif key.startswith("bon:"):
            self.form["bonuses"][key[4:]] = value
        else:
            self.form[key] = value

    def _step(self, spec, direction):
        key, _label, _kind, step, low, high = spec
        self._set(key, max(low, min(high, self._get(key) + direction * step)))

    def _step_slot(self, direction):
        slots = mob_modes.MOB_EQUIPMENT_SLOTS
        index = slots.index(self.form["slot"])
        self.form["slot"] = slots[(index + direction) % len(slots)]

    def _icon_rect(self):
        """Окно выбора иконки по центру формы."""
        box = self.box()
        width = ICON_COLS * ICON_CELL + 24
        height = ICON_ROWS * ICON_CELL + 60
        return pygame.Rect(box.centerx - width // 2, box.y + 100, width, height)

    def _icon_cell(self, index):
        picker = self._icon_rect()
        col, row = index % ICON_COLS, index // ICON_COLS
        return pygame.Rect(picker.x + 12 + col * ICON_CELL, picker.y + 44 + row * ICON_CELL, ICON_CELL - 4, ICON_CELL - 4)

    def _open_icon_picker(self):
        self.icon_options = [None] + item_icons.icons_for_slot(self.form["slot"])
        self.icon_scroll = 0
        self.focus = None

    def _icon_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.icon_options = None
        elif event.type == pygame.MOUSEWHEEL:
            rows = (len(self.icon_options) + ICON_COLS - 1) // ICON_COLS
            self.icon_scroll = max(0, min(self.icon_scroll - event.y, max(0, rows - ICON_ROWS)))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._icon_rect().collidepoint(event.pos):
                self.icon_options = None
                return None
            for index in range(ICON_COLS * ICON_ROWS):
                option = self.icon_scroll * ICON_COLS + index
                if option >= len(self.icon_options):
                    break
                if self._icon_cell(index).collidepoint(event.pos):
                    self.form["icon"] = self.icon_options[option]
                    self.icon_options = None
                    break
        return None

    def _thumb(self, key):
        if key not in self._thumbs:
            try:
                image = pygame.image.load(str(item_icons.icon_path(key))).convert_alpha()
                self._thumbs[key] = pygame.transform.smoothscale(image, (ICON_IMG, ICON_IMG))
            except (pygame.error, OSError):
                self._thumbs[key] = None
        return self._thumbs[key]

    def _draw_icon_picker(self, screen, mouse):
        picker = self._icon_rect()
        pygame.draw.rect(screen, MENU_BG, picker, border_radius=8)
        pygame.draw.rect(screen, ACTIVE_TEXT, picker, 2, border_radius=8)
        slot_label = SLOT_LABELS[self.form["slot"]]
        screen.blit(self.font.render(f"Иконка: {slot_label}", True, TEXT), (picker.x + 12, picker.y + 12))
        if len(self.icon_options) == 1:
            screen.blit(self.small.render("В базе иконок пока нет файлов для этого слота. Положите PNG в assets/item_icons", True, WARN_TEXT), (picker.x + 12, picker.y + 44))
        for index in range(ICON_COLS * ICON_ROWS):
            option = self.icon_scroll * ICON_COLS + index
            if option >= len(self.icon_options):
                break
            key = self.icon_options[option]
            cell = self._icon_cell(index)
            chosen = key == self.form["icon"]
            pygame.draw.rect(screen, BUTTON_ON if cell.collidepoint(mouse) or chosen else BUTTON_BG, cell, border_radius=4)
            if key is None:
                label = self.small.render("нет", True, TEXT)
                screen.blit(label, label.get_rect(center=cell.center))
                continue
            thumb = self._thumb(key)
            if thumb is not None:
                screen.blit(thumb, thumb.get_rect(center=(cell.centerx, cell.y + 30)))
            name = self.small.render(_fit(self.small, key, cell.w - 6), True, TEXT_DIM)
            screen.blit(name, name.get_rect(center=(cell.centerx, cell.bottom - 10)))

    def handle_event(self, event):
        if self.icon_options is not None:
            return self._icon_event(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if self.focus == "name":
                if event.key == pygame.K_BACKSPACE:
                    self.form["name"] = self.form["name"][:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.focus = None
                elif event.unicode and event.unicode.isprintable() and len(self.form["name"]) < item_form.MAX_NAME:
                    self.form["name"] += event.unicode
            return None
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        pos = event.pos
        if self._save_rect().collidepoint(pos):
            return "save", copy.deepcopy(self.form)
        if self._cancel_rect().collidepoint(pos):
            return "cancel"
        for spec, x, y in self._entries():
            if spec[0] == "header":
                continue
            controls = self._controls(spec, x, y)
            key = spec[0]
            if key == "name" and controls["field"].collidepoint(pos):
                self.focus = "name"
                return None
            if key == "slot":
                if controls["prev"].collidepoint(pos):
                    self._step_slot(-1)
                elif controls["next"].collidepoint(pos):
                    self._step_slot(1)
                self.focus = None
                return None
            if spec[2] == "flag" and controls["box"].collidepoint(pos):
                self.form["two_handed"] = not self.form["two_handed"]
                self.focus = None
                return None
            if spec[2] == "icon" and controls["button"].collidepoint(pos):
                self._open_icon_picker()
                return None
            if spec[2] == "int":
                if controls["minus"].collidepoint(pos):
                    self._step(spec, -1)
                elif controls["plus"].collidepoint(pos):
                    self._step(spec, 1)
                self.focus = None
                return None
        self.focus = None
        return None

    def draw(self, screen):
        _shade(screen)
        box = self.box()
        _panel(screen, box)
        screen.blit(self.font.render("Новый предмет", True, TEXT), (box.x + 24, box.y + 18))
        screen.blit(
            self.small.render("Предмет сохранится в базу. Уворот, скорости, криты и магический урон пока не участвуют в бою: значения сохраняются", True, TEXT_DIM),
            (box.x + 24, box.y + 46),
        )
        mouse = pygame.mouse.get_pos()
        for spec, x, y in self._entries():
            key, label, kind, *_ = spec
            if key == "header":
                screen.blit(self.font.render(label, True, ACTIVE_TEXT), (x, y + 4))
                continue
            screen.blit(self.small.render(label, True, TEXT), (x, y + 8))
            controls = self._controls(spec, x, y)
            if kind == "text":
                field = controls["field"]
                pygame.draw.rect(screen, BUTTON_ON if self.focus == "name" else MENU_BG, field, border_radius=4)
                pygame.draw.rect(screen, BORDER, field, 1, border_radius=4)
                caret = "|" if self.focus == "name" else ""
                screen.blit(self.font.render(_fit(self.font, self.form["name"] + caret, field.w - 12), True, TEXT), (field.x + 6, field.y + 5))
            elif kind == "slot":
                for rect, sign in ((controls["prev"], "<"), (controls["next"], ">")):
                    pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(mouse) else BUTTON_BG, rect, border_radius=4)
                    text = self.font.render(sign, True, TEXT)
                    screen.blit(text, text.get_rect(center=rect.center))
                value = controls["value"]
                pygame.draw.rect(screen, MENU_BG, value, border_radius=4)
                text = self.font.render(SLOT_LABELS[self.form["slot"]], True, TEXT)
                screen.blit(text, text.get_rect(center=value.center))
            elif kind == "icon":
                button = controls["button"]
                pygame.draw.rect(screen, BUTTON_ON if button.collidepoint(mouse) else MENU_BG, button, border_radius=4)
                pygame.draw.rect(screen, BORDER, button, 1, border_radius=4)
                text = self.small.render(_fit(self.small, self.form["icon"] or "нет", button.w - 12), True, TEXT)
                screen.blit(text, text.get_rect(center=button.center))
            elif kind == "flag":
                box_rect = controls["box"]
                pygame.draw.rect(screen, MENU_BG, box_rect, border_radius=3)
                pygame.draw.rect(screen, BORDER, box_rect, 1, border_radius=3)
                if self.form["two_handed"]:
                    pygame.draw.line(screen, ACTIVE_TEXT, box_rect.topleft, box_rect.bottomright, 3)
                    pygame.draw.line(screen, ACTIVE_TEXT, box_rect.topright, box_rect.bottomleft, 3)
            else:
                for rect, sign in ((controls["minus"], "−"), (controls["plus"], "+")):
                    pygame.draw.rect(screen, BUTTON_ON if rect.collidepoint(mouse) else BUTTON_BG, rect, border_radius=4)
                    text = self.font.render(sign, True, TEXT)
                    screen.blit(text, text.get_rect(center=rect.center))
                value = controls["value"]
                pygame.draw.rect(screen, MENU_BG, value, border_radius=4)
                text = self.font.render(str(self._get(key)), True, TEXT)
                screen.blit(text, text.get_rect(center=value.center))
        save, cancel = self._save_rect(), self._cancel_rect()
        pygame.draw.rect(screen, (70, 130, 80) if save.collidepoint(mouse) else (56, 106, 66), save, border_radius=5)
        pygame.draw.rect(screen, BUTTON_ON if cancel.collidepoint(mouse) else BUTTON_BG, cancel, border_radius=5)
        for rect, text in ((save, "Сохранить в базу"), (cancel, "Отмена")):
            label = self.font.render(text, True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))
        if self.message:
            screen.blit(self.small.render(self.message, True, WARN_TEXT), (cancel.right + 18, cancel.y + 13))
        if self.icon_options is not None:
            self._draw_icon_picker(screen, mouse)
