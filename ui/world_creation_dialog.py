"""Окно «Создать мир» в разделе «Миры»: название, режим, галочка «тест», карта из сохранённых и запуск.

Видно только админу. Карты списка — сохранённые в редакторе карты выбранного режима.
"""
import pygame

from client.network import ServerError
from client.server_maps import list_server_maps, upload_server_map
from core.game_modes import GAME_MODES

NAME_MAX = 40
ROW_H = 34
VISIBLE_ROWS = 5
TEXT = (235, 235, 240)
TEXT_DIM = (160, 166, 180)
PANEL = (30, 33, 46)
FIELD = (46, 50, 66)
ACCENT = (110, 150, 230)
GREEN = (120, 220, 130)
RED = (240, 110, 100)


class WorldCreateDialog:
    def __init__(self, client, font, small, screen_rect):
        self.client = client
        self.font = font
        self.small = small
        self.name = ""
        self.focus_name = True
        self.mode = GAME_MODES[0]["key"]
        self.test = True
        self.maps = []
        self.saved_id = None
        self.created_world = None
        self.picking = None  # список карт из maps_for_server, когда открыт выбор для загрузки
        self.server_maps = list_server_maps
        self.message = ""
        self.message_color = TEXT_DIM
        self.finished = False
        self.box = pygame.Rect(0, 0, 760, 560)
        self.box.center = screen_rect.center
        self.refresh_maps()

    # ----- раскладка -----
    def _rect(self, x, y, w, h):
        return pygame.Rect(self.box.x + x, self.box.y + y, w, h)

    def name_rect(self):
        return self._rect(24, 70, 712, 40)

    def mode_rect(self, index):
        return self._rect(24 + index * 170, 150, 160, 36)

    def test_rect(self):
        return self._rect(24, 206, 26, 26)

    def upload_rect(self):
        return self._rect(self.box.w - 24 - 190, 228, 190, 30)

    def picker_row_rect(self, index):
        return self._rect(24, 258 + index * ROW_H, 712, ROW_H - 4)

    def picker_back_rect(self):
        return self._rect(24, self.box.h - 64, 220, 40)

    def row_rect(self, offset):
        return self._rect(24, 258 + offset * ROW_H, 712, ROW_H - 4)

    def create_rect(self):
        return self._rect(24, self.box.h - 64, 220, 40)

    def start_rect(self):
        return self._rect(260, self.box.h - 64, 220, 40)

    def close_rect(self):
        return self._rect(self.box.w - 150, self.box.h - 64, 126, 40)

    # ----- данные -----
    def refresh_maps(self):
        try:
            self.maps = self.client.list_saved_maps(self.mode)
        except ServerError as error:
            self.maps = []
            self._say(str(error), RED)
            return
        if self.saved_id not in {item["id"] for item in self.maps}:
            self.saved_id = None

    def open_picker(self):
        try:
            self.picking = self.server_maps()
        except OSError as error:
            self._say(f"Папка с картами не открыта: {error}", RED)
            return
        if not self.picking:
            self._say("Папка maps_for_server пуста: положите туда карты из папки map_drafts", RED)

    def upload(self, entry):
        """Загружает выбранную карту на сервер и выбирает её в списке; режим окна становится режимом карты."""
        try:
            saved_id = upload_server_map(self.client, entry)["saved_id"]
        except ServerError as error:
            self._say(f"Не загружено: {error}", RED)
            return
        self.picking = None
        self.mode = entry["mode"]
        self.refresh_maps()
        self.saved_id = saved_id
        self._say(f"Карта «{entry['name']}» загружена на сервер и выбрана", GREEN)

    def _click_picker(self, pos):
        for index, entry in enumerate(self.picking):
            if self.picker_row_rect(index).collidepoint(pos):
                self.upload(entry)
                return
        if self.picker_back_rect().collidepoint(pos):
            self.picking = None

    def _draw_picker(self, screen):
        area = self._rect(12, 226, self.box.w - 24, self.box.h - 290)
        pygame.draw.rect(screen, PANEL, area, border_radius=6)
        screen.blit(self.small.render("Выберите карту для загрузки на сервер", True, TEXT), (area.x + 12, area.y + 6))
        for index, entry in enumerate(self.picking[:VISIBLE_ROWS]):
            row = self.picker_row_rect(index)
            pygame.draw.rect(screen, FIELD, row, border_radius=4)
            screen.blit(self.small.render(f"{entry['name']}  ({entry['mode']})", True, TEXT), (row.x + 10, row.y + 8))
            size = self.small.render(f"{entry['map_w']}×{entry['map_h']}", True, TEXT_DIM)
            screen.blit(size, size.get_rect(midright=(row.right - 10, row.centery)))
        back = self.picker_back_rect()
        pygame.draw.rect(screen, (90, 95, 110), back, border_radius=5)
        text = self.font.render("Назад", True, TEXT)
        screen.blit(text, text.get_rect(center=back.center))

    def _say(self, text, color=TEXT_DIM):
        self.message = text
        self.message_color = color

    def create(self):
        if not self.name.strip():
            self._say("Введите название мира", RED)
            return
        if self.saved_id is None:
            self._say("Выберите карту этого режима", RED)
            return
        try:
            self.created_world = self.client.create_world(self.saved_id, self.name.strip(), self.test)
        except ServerError as error:
            self._say(f"Мир не создан: {error}", RED)
            return
        kind = "тестовый" if self.test else "обычный"
        self._say(f"Мир «{self.created_world['name']}» создан ({kind}). Запустите его кнопкой «Запустить».", GREEN)

    def start(self):
        if self.created_world is None:
            self._say("Сначала создайте мир", RED)
            return
        try:
            result = self.client.start_world(self.created_world["world_id"])
        except ServerError as error:
            self._say(f"Не запущен: {error}", RED)
            return
        if result["started"]:
            self._say("Сервер мира запускается. Через несколько секунд мир появится в списке.", GREEN)
        else:
            self._say("Сервер мира уже работает.", GREEN)

    # ----- события -----
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.picking is not None:
                    self.picking = None
                else:
                    self.finished = True
            elif event.key == pygame.K_BACKSPACE and self.focus_name:
                self.name = self.name[:-1]
        elif event.type == pygame.TEXTINPUT and self.focus_name:
            if len(self.name) < NAME_MAX:
                self.name += event.text
        elif event.type == pygame.MOUSEWHEEL:
            max_offset = max(0, len(self.maps) - VISIBLE_ROWS)
            self.scroll = max(0, min(max_offset, getattr(self, "scroll", 0) - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def _click(self, pos):
        if self.picking is not None:
            self._click_picker(pos)
            return
        if self.name_rect().collidepoint(pos):
            self.focus_name = True
            return
        self.focus_name = False
        if self.upload_rect().collidepoint(pos):
            self.open_picker()
            return
        for index, mode in enumerate(GAME_MODES):
            if self.mode_rect(index).collidepoint(pos) and mode["key"] != self.mode:
                self.mode = mode["key"]
                self.saved_id = None
                self.scroll = 0
                self.refresh_maps()
                return
        if self.test_rect().collidepoint(pos) or self._rect(56, 200, 300, 36).collidepoint(pos):
            self.test = not self.test
            return
        offset = 0
        scroll = getattr(self, "scroll", 0)
        for item in self.maps[scroll:scroll + VISIBLE_ROWS]:
            if self.row_rect(offset).collidepoint(pos):
                self.saved_id = item["id"]
                return
            offset += 1
        if self.create_rect().collidepoint(pos):
            self.create()
        elif self.start_rect().collidepoint(pos):
            self.start()
        elif self.close_rect().collidepoint(pos):
            self.finished = True

    # ----- рисование -----
    def draw(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, PANEL, self.box, border_radius=8)
        pygame.draw.rect(screen, ACCENT, self.box, 1, border_radius=8)
        screen.blit(self.font.render("Создать мир", True, TEXT), (self.box.x + 24, self.box.y + 18))
        screen.blit(self.small.render("Название", True, TEXT_DIM), (self.box.x + 24, self.box.y + 50))
        name_rect = self.name_rect()
        pygame.draw.rect(screen, FIELD, name_rect, border_radius=4)
        if self.focus_name:
            pygame.draw.rect(screen, ACCENT, name_rect, 1, border_radius=4)
        screen.blit(self.font.render(self.name, True, TEXT), (name_rect.x + 10, name_rect.y + 8))
        screen.blit(self.small.render("Режим", True, TEXT_DIM), (self.box.x + 24, self.box.y + 130))
        for index, mode in enumerate(GAME_MODES):
            rect = self.mode_rect(index)
            chosen = mode["key"] == self.mode
            pygame.draw.rect(screen, ACCENT if chosen else FIELD, rect, border_radius=4)
            label = self.font.render(mode["name"], True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))
        test_rect = self.test_rect()
        pygame.draw.rect(screen, FIELD, test_rect, border_radius=3)
        if self.test:
            pygame.draw.line(screen, GREEN, (test_rect.x + 5, test_rect.centery), (test_rect.x + 10, test_rect.bottom - 6), 3)
            pygame.draw.line(screen, GREEN, (test_rect.x + 10, test_rect.bottom - 6), (test_rect.right - 4, test_rect.y + 5), 3)
        screen.blit(self.font.render("тест (видят только админ и модераторы)", True, TEXT), (test_rect.right + 10, test_rect.y + 2))
        screen.blit(self.small.render("Карта этого режима", True, TEXT_DIM), (self.box.x + 24, self.box.y + 236))
        upload = self.upload_rect()
        pygame.draw.rect(screen, ACCENT, upload, border_radius=4)
        label = self.small.render("Загрузить карту", True, TEXT)
        screen.blit(label, label.get_rect(center=upload.center))
        if not self.maps:
            screen.blit(self.small.render("В этом режиме пока нет сохранённых карт. Нажмите «Загрузить карту»", True, TEXT_DIM), (self.box.x + 24, self.box.y + 262))
        scroll = getattr(self, "scroll", 0)
        for offset, item in enumerate(self.maps[scroll:scroll + VISIBLE_ROWS]):
            row = self.row_rect(offset)
            chosen = item["id"] == self.saved_id
            pygame.draw.rect(screen, ACCENT if chosen else FIELD, row, border_radius=4)
            screen.blit(self.small.render(item["name"], True, TEXT), (row.x + 10, row.y + 8))
            size = self.small.render(f"{item['map_w']}×{item['map_h']}", True, TEXT_DIM)
            screen.blit(size, size.get_rect(midright=(row.right - 10, row.centery)))
        for rect, label, color in (
            (self.create_rect(), "Создать", (70, 130, 80)),
            (self.start_rect(), "Запустить", (70, 110, 170)),
            (self.close_rect(), "Закрыть", (90, 95, 110)),
        ):
            pygame.draw.rect(screen, color, rect, border_radius=5)
            text = self.font.render(label, True, TEXT)
            screen.blit(text, text.get_rect(center=rect.center))
        if self.message:
            text = self.small.render(self.message, True, self.message_color)
            screen.blit(text, (self.box.x + 24, self.box.bottom - 88))
        if self.picking is not None:
            self._draw_picker(screen)
