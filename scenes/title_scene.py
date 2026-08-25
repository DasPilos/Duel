import pygame

from client.session import OnlineSession
from client.network import ServerError
from client.credentials import (
    clear_credentials,
    load_credentials,
    save_credentials,
)
from core import settings
from ui.hud import draw_button, draw_text


class TitleScene:
    FIELDS = ("username", "password")

    def __init__(self, server_url, username="", password=""):
        self.server_url = server_url
        saved = load_credentials()
        self.values = {
            "username": username or saved["username"],
            "password": password or saved["password"],
        }
        self.mode = "login"
        self.remember = bool(saved["username"] and saved["password"])
        self.active_field = "username"
        self.error = ""
        self.finished = False
        self.cancelled = False
        self.online_session = None
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 42)
        self.field_rects = {
            "username": pygame.Rect(760, 380, 400, 46),
            "password": pygame.Rect(760, 460, 400, 46),
        }
        self.login_mode_button = pygame.Rect(700, 260, 250, 48)
        self.register_mode_button = pygame.Rect(970, 260, 250, 48)
        self.connect_button = pygame.Rect(760, 650, 400, 55)
        self.remember_rect = pygame.Rect(760, 550, 24, 24)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self._activate_next_field()
            elif event.key == pygame.K_BACKSPACE:
                field = self.values[self.active_field]
                self.values[self.active_field] = field[:-1]
            elif event.key == pygame.K_RETURN:
                self.authenticate()
            elif event.key == pygame.K_ESCAPE:
                self.finished = True
                self.cancelled = True
        elif event.type == pygame.TEXTINPUT:
            if self.active_field == "password" or len(self.values[self.active_field]) < 32:
                self.values[self.active_field] += event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for field, rect in self.field_rects.items():
                if rect.collidepoint(event.pos):
                    self.active_field = field
                    return
            if self.login_mode_button.collidepoint(event.pos):
                self.mode = "login"
                self.error = ""
                return
            if self.register_mode_button.collidepoint(event.pos):
                self.mode = "register"
                self.error = ""
                return
            if self.remember_rect.collidepoint(event.pos):
                self.remember = not self.remember
                return
            if self.connect_button.collidepoint(event.pos):
                self.authenticate()

    def _activate_next_field(self):
        index = self.FIELDS.index(self.active_field)
        self.active_field = self.FIELDS[(index + 1) % len(self.FIELDS)]

    def authenticate(self):
        username = self.values["username"].strip()
        password = self.values["password"]
        if not 3 <= len(username) <= 32:
            self.error = "Имя пользователя: от 3 до 32 символов"
            return
        if not 6 <= len(password) <= 128:
            self.error = "Пароль: от 6 до 128 символов"
            return
        session = OnlineSession(username, password, "", self.server_url)
        try:
            if self.mode == "register":
                session.register_account()
            else:
                session.user = session.client.login(username, password)
        except ServerError as error:
            self.error = str(error)
            return
        if self.remember:
            save_credentials(username, password)
        else:
            clear_credentials()
        self.online_session = session
        self.finished = True

    def update(self, dt):
        pass

    def close(self):
        if self.online_session is not None:
            self.online_session.disconnect()

    def draw(self, screen):
        screen.fill((16, 18, 28))
        panel = pygame.Rect(620, 70, 680, 700)
        pygame.draw.rect(screen, (22, 24, 36), panel, border_radius=12)
        pygame.draw.rect(screen, (62, 68, 86), panel, width=2, border_radius=12)
        title = self.title_font.render("МИНИ-ДУЭЛЬ", True, (240, 240, 255))
        screen.blit(title, title.get_rect(center=(960, 120)))
        draw_text(screen, self.font, "ПОДКЛЮЧЕНИЕ К ИГРОВОМУ МИРУ", 760, 195, (255, 220, 120))
        draw_button(screen, self.login_mode_button, "ВОЙТИ В АККАУНТ", self.font, color=(70, 140, 220) if self.mode == "login" else (70, 70, 85))
        draw_button(screen, self.register_mode_button, "РЕГИСТРАЦИЯ", self.font, color=(70, 140, 220) if self.mode == "register" else (70, 70, 85))
        draw_text(screen, self.small_font, "Введите логин и пароль, затем нажмите Enter", 760, 325, (170, 170, 170))

        labels = {
            "username": "ПОЛЬЗОВАТЕЛЬ",
            "password": "ПАРОЛЬ",
        }
        for field, rect in self.field_rects.items():
            color = (70, 140, 220) if field == self.active_field else (70, 70, 85)
            pygame.draw.rect(screen, (28, 30, 43), rect, border_radius=6)
            pygame.draw.rect(screen, color, rect, width=2, border_radius=6)
            draw_text(screen, self.small_font, labels[field], rect.x, rect.y - 24, (205, 205, 215))
            value = self.values[field]
            if field == "password":
                value = "*" * len(value)
            draw_text(screen, self.font, value, rect.x + 12, rect.y + 10, (240, 240, 245))

        pygame.draw.rect(screen, (70, 140, 220) if self.remember else (70, 70, 85), self.remember_rect, border_radius=4)
        if self.remember:
            pygame.draw.line(screen, (255, 255, 255), (764, 562), (769, 568), 3)
            pygame.draw.line(screen, (255, 255, 255), (769, 568), (779, 556), 3)
        draw_text(screen, self.small_font, "Запомнить логин и пароль", 795, 550, (205, 205, 215))
        button_text = "ВОЙТИ В АККАУНТ" if self.mode == "login" else "СОЗДАТЬ АККАУНТ"
        draw_button(screen, self.connect_button, button_text, self.font, color=(70, 140, 220))
        if self.error:
            draw_text(screen, self.small_font, self.error, 760, 680, (255, 100, 100))
