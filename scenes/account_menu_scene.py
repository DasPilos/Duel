from datetime import datetime

import pygame

from client.background_polling import BackgroundPoller
from client.network import ServerError
from client.session import OnlineSession
from core import settings
from ui.hud import draw_button, draw_text
from ui.world_creation_dialog import WorldCreateDialog

POLL_INTERVAL = 5.0
WORLD_ROW_HEIGHT = 84
LOBBY_COLUMNS = 4
LOBBY_ROW_HEIGHT = 26


def format_time(timestamp):
    if timestamp is None:
        return "не задано"
    return datetime.fromtimestamp(timestamp).strftime("%d.%m.%Y %H:%M")


class AccountMenuScene:
    def __init__(self, session):
        self.session = session
        self.world_session = None
        self.worlds = []
        self.lobby = []
        self.error = ""
        self.load_error = ""
        self.finished = False
        self.cancelled = False
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)

        self.logout_button = pygame.Rect(60, 150, 320, 50)
        self.worlds_rect = pygame.Rect(1480, 120, 400, 600)
        self.worlds_rows_top = self.worlds_rect.y + 56
        self.visible_world_rows = (self.worlds_rect.bottom - self.worlds_rows_top) // WORLD_ROW_HEIGHT
        self.world_scroll = 0
        self.lobby_rect = pygame.Rect(40, 780, 1840, 260)

        self.is_admin = self._check_admin()
        self.create_world_button = pygame.Rect(self.worlds_rect.x, self.worlds_rect.bottom + 8, self.worlds_rect.w, 40)
        self.world_dialog = None

        self.poller = BackgroundPoller(self._fetch, interval=POLL_INTERVAL)
        self.poller.start()

    def _check_admin(self):
        """Кнопку «Создать мир» видит только админ."""
        try:
            return self.session.client.get_me().get("role") == "admin"
        except (ServerError, OSError):
            return False

    def _fetch(self):
        return self.session.client.list_worlds(), self.session.client.list_lobby()

    def handle_event(self, event):
        if self.world_dialog is not None:
            self.world_dialog.handle_event(event)
            if self.world_dialog.finished:
                self.world_dialog = None
            return
        if self.is_admin and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.create_world_button.collidepoint(event.pos):
                self.world_dialog = WorldCreateDialog(
                    self.session.client, self.small_font, self.small_font, pygame.display.get_surface().get_rect(),
                )
                return
        if event.type == pygame.MOUSEWHEEL:
            if self.worlds_rect.collidepoint(pygame.mouse.get_pos()):
                max_scroll = max(0, len(self.worlds) - self.visible_world_rows)
                self.world_scroll = max(0, min(max_scroll, self.world_scroll - event.y))
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.logout_button.collidepoint(event.pos):
            self._logout()
            return
        if self.worlds_rect.collidepoint(event.pos) and event.pos[1] >= self.worlds_rows_top:
            slot = (event.pos[1] - self.worlds_rows_top) // WORLD_ROW_HEIGHT
            index = slot + self.world_scroll
            if slot < self.visible_world_rows and index < len(self.worlds):
                self._enter_world(self.worlds[index])

    def _enter_world(self, world):
        if not world["is_open"]:
            self.error = "Мир закрыт"
            return
        if not world["server_url"]:
            if not self.is_admin:
                self.error = "Мир ещё не запущен: администратор запускает его в разделе «Миры»"
                return
            try:
                started = self.session.client.start_world(world["id"])
            except ServerError as error:
                self.error = f"Мир не запущен: {error}"
                return
            self.error = ("Сервер мира запускается, войдите через несколько секунд" if started["started"]
                          else "Сервер мира уже запускается, войдите через несколько секунд")
            return
        world_session = OnlineSession(self.session.username, self.session.password, "", world["server_url"])
        try:
            world_session.user = world_session.client.login(self.session.username, self.session.password)
        except ServerError as error:
            self.error = str(error)
            return
        try:
            self.session.disconnect()
        except ServerError:
            # Лобби учитывает только свежие сессии, поэтому старая сессия аккаунтного сервера истечёт сама.
            pass
        # Миры карт (код map…) открываются сразу на карте: в таверне их нет
        world_session.map_world = str(world.get("code", "")).startswith("map")
        self.world_session = world_session
        self._finish()

    def _logout(self):
        try:
            self.session.disconnect()
        except ServerError as error:
            self.error = str(error)
            return
        self.cancelled = True
        self._finish()

    def _finish(self):
        self.finished = True
        self.poller.stop()

    def update(self, dt):
        result, error = self.poller.poll()
        if error is not None:
            self.load_error = str(error) if isinstance(error, ServerError) else "Нет связи с сервером"
        elif result is not None:
            self.worlds, self.lobby = result
            self.load_error = ""
            max_scroll = max(0, len(self.worlds) - self.visible_world_rows)
            self.world_scroll = min(self.world_scroll, max_scroll)

    def close(self):
        self.poller.stop()

    def draw(self, screen):
        screen.fill((16, 18, 28))
        draw_text(screen, self.title_font, f"Аккаунт: {self.session.username}", 60, 60, color=(240, 220, 150))
        draw_text(screen, self.small_font, "Выберите мир, в котором хотите продолжить игру", 60, 110, color=(170, 170, 185))
        draw_button(
            screen,
            self.logout_button,
            "Выйти из аккаунта",
            self.font,
            color=(150, 70, 70),
            hover_color=(190, 90, 90),
        )
        y = 230
        for message, color in ((self.error, (255, 120, 120)), (self.load_error, (255, 180, 90))):
            if message:
                draw_text(screen, self.small_font, message, 60, y, color=color)
                y += 28
        self._draw_worlds(screen)
        self._draw_lobby(screen)
        if self.is_admin:
            draw_button(screen, self.create_world_button, "Создать мир", self.font, color=(70, 110, 170), hover_color=(90, 135, 200))
        if self.world_dialog is not None:
            self.world_dialog.draw(screen)

    def _draw_worlds(self, screen):
        rect = self.worlds_rect
        pygame.draw.rect(screen, (28, 32, 48), rect, border_radius=12)
        pygame.draw.rect(screen, (90, 100, 140), rect, width=2, border_radius=12)
        draw_text(screen, self.font, "Миры", rect.x + 16, rect.y + 14, color=(240, 220, 150))
        if not self.worlds:
            draw_text(screen, self.small_font, "Миров пока нет", rect.x + 16, self.worlds_rows_top, color=(170, 170, 185))
            return
        mouse_pos = pygame.mouse.get_pos()
        visible = self.worlds[self.world_scroll:self.world_scroll + self.visible_world_rows]
        for offset, world in enumerate(visible):
            row = pygame.Rect(
                rect.x + 10,
                self.worlds_rows_top + offset * WORLD_ROW_HEIGHT,
                rect.width - 20,
                WORLD_ROW_HEIGHT - 6,
            )
            hovered = row.collidepoint(mouse_pos) and world["is_open"]
            pygame.draw.rect(screen, (46, 54, 80) if hovered else (36, 40, 60), row, border_radius=8)
            status = "открыт" if world["is_open"] else "закрыт"
            status_color = (120, 220, 130) if world["is_open"] else (230, 110, 110)
            status_x = row.right - 10 - self.small_font.size(status)[0]
            draw_text(screen, self.small_font, world["name"], row.x + 10, row.y + 6)
            draw_text(screen, self.small_font, status, status_x, row.y + 6, color=status_color)
            draw_text(screen, self.small_font, f"Начало: {format_time(world['opens_at'])}", row.x + 10, row.y + 30, color=(190, 195, 210))
            draw_text(screen, self.small_font, f"Окончание: {format_time(world['closes_at'])}", row.x + 10, row.y + 52, color=(190, 195, 210))

    def _draw_lobby(self, screen):
        rect = self.lobby_rect
        pygame.draw.rect(screen, (28, 32, 48), rect, border_radius=12)
        pygame.draw.rect(screen, (90, 100, 140), rect, width=2, border_radius=12)
        draw_text(screen, self.font, f"Лобби: онлайн {len(self.lobby)}", rect.x + 16, rect.y + 12, color=(240, 220, 150))
        if not self.lobby:
            draw_text(screen, self.small_font, "Никого нет", rect.x + 16, rect.y + 52, color=(170, 170, 185))
            return
        column_width = rect.width // LOBBY_COLUMNS
        rows_per_column = (rect.height - 60) // LOBBY_ROW_HEIGHT
        capacity = rows_per_column * LOBBY_COLUMNS
        for index, player in enumerate(self.lobby[:capacity]):
            column, row = divmod(index, rows_per_column)
            x = rect.x + 16 + column * column_width
            y = rect.y + 52 + row * LOBBY_ROW_HEIGHT
            draw_text(screen, self.small_font, player["username"], x, y, color=(220, 225, 235))
        hidden = len(self.lobby) - capacity
        if hidden > 0:
            draw_text(screen, self.small_font, f"и ещё {hidden}", rect.right - 150, rect.bottom - 28, color=(170, 170, 185))
