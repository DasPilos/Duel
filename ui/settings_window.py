import pygame

from core import settings
from ui.hud import draw_button


class SettingsWindow:
    WIDTH = 650
    HEIGHT = 780

    KEY_LABELS = {
        "profile": "Профиль и инвентарь",
        "interact": "Взаимодействие",
        "grid": "Показать сетку",
        "center": "Центрировать камеру",
        "move_left": "Движение влево",
        "move_right": "Движение вправо",
        "move_up": "Движение вверх",
        "move_down": "Движение вниз",
    }

    def __init__(self, preferences):
        self.preferences = preferences
        self.is_open = False
        self.awaiting_key = None
        self.dragging_slider = None
        self.message = None
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self.rect.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 28, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 15)
        self.close_rect = pygame.Rect(self.rect.right - 48, self.rect.top + 14, 34, 34)
        self.tab_mode_rect = pygame.Rect(self.rect.left + 24, self.rect.top + 70, self.rect.width - 48, 44)
        self.key_rows = {
            key: pygame.Rect(
                self.rect.left + 24,
                self.rect.top + 132 + index * 48,
                self.rect.width - 48,
                40,
            )
            for index, key in enumerate(self.KEY_LABELS)
        }
        self.music_track = pygame.Rect(self.rect.left + 230, self.rect.top + 590, 350, 12)
        self.sfx_track = pygame.Rect(self.rect.left + 230, self.rect.top + 650, 350, 12)

    def open(self):
        self.is_open = True
        self.awaiting_key = None
        self.dragging_slider = None
        self.message = self.preferences.load_error

    def close(self):
        self.is_open = False
        self.awaiting_key = None
        self.dragging_slider = None

    def _save(self):
        try:
            self.preferences.save()
        except OSError as error:
            self.message = f"Не удалось сохранить настройки: {error}"
            return False
        self.message = "Настройки сохранены"
        return True

    def _set_volume(self, name, track, position):
        value = max(0.0, min(1.0, (position[0] - track.left) / track.width))
        self.preferences.values[name] = value
        from ui.music import set_music_volume, set_sfx_volume

        if name == "music_volume":
            set_music_volume(value)
        else:
            set_sfx_volume(value)

    def handle_event(self, event):
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN:
            if self.awaiting_key is not None:
                if event.key == pygame.K_ESCAPE:
                    self.awaiting_key = None
                    self.message = "Изменение клавиши отменено"
                else:
                    self.preferences.key_bindings[self.awaiting_key] = event.key
                    self.awaiting_key = None
                    self._save()
                return True
            if event.key == pygame.K_ESCAPE:
                self.close()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.close()
                return True
            if self.tab_mode_rect.collidepoint(event.pos):
                self.preferences.values["tab_toggle"] = not self.preferences.get("tab_toggle", False)
                self._save()
                return True
            for key, rect in self.key_rows.items():
                if rect.collidepoint(event.pos):
                    self.awaiting_key = key
                    self.message = f"Нажмите новую клавишу: {self.KEY_LABELS[key]}"
                    return True
            for name, track in (
                ("music_volume", self.music_track),
                ("sfx_volume", self.sfx_track),
            ):
                if track.inflate(0, 24).collidepoint(event.pos):
                    self.dragging_slider = name
                    self._set_volume(name, track, event.pos)
                    return True
            return True

        if event.type == pygame.MOUSEMOTION and self.dragging_slider is not None:
            track = self.music_track if self.dragging_slider == "music_volume" else self.sfx_track
            self._set_volume(self.dragging_slider, track, event.pos)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_slider is not None:
                self.dragging_slider = None
                self._save()
            return True

        return event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEWHEEL,
            pygame.KEYUP,
            pygame.TEXTINPUT,
        )

    def draw(self, screen):
        if not self.is_open:
            return
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (24, 29, 38), self.rect, border_radius=12)
        pygame.draw.rect(screen, (155, 175, 205), self.rect, 2, border_radius=12)
        title = self.title_font.render("Настройки", True, (235, 225, 190))
        screen.blit(title, (self.rect.left + 24, self.rect.top + 16))
        draw_button(screen, self.close_rect, "×", self.font, color=(90, 60, 55))

        mode = "Переключать одним нажатием" if self.preferences.get("tab_toggle") else "Показывать, пока Tab зажат"
        pygame.draw.rect(screen, (43, 55, 70), self.tab_mode_rect, border_radius=6)
        pygame.draw.rect(screen, (95, 125, 155), self.tab_mode_rect, 1, border_radius=6)
        screen.blit(
            self.font.render(f"Режим Tab: {mode}", True, (225, 230, 240)),
            (self.tab_mode_rect.left + 12, self.tab_mode_rect.top + 11),
        )

        screen.blit(
            self.font.render("Клавиши управления", True, (190, 210, 235)),
            (self.rect.left + 24, self.rect.top + 118),
        )
        for key, rect in self.key_rows.items():
            pygame.draw.rect(screen, (34, 42, 54), rect, border_radius=5)
            label = self.small_font.render(self.KEY_LABELS[key], True, (220, 225, 235))
            screen.blit(label, (rect.left + 10, rect.top + 11))
            key_name = (
                "Нажмите клавишу..."
                if self.awaiting_key == key
                else pygame.key.name(self.preferences.key_bindings[key]).upper()
            )
            key_rect = pygame.Rect(rect.right - 150, rect.top + 4, 140, rect.height - 8)
            draw_button(screen, key_rect, key_name, self.small_font, color=(60, 85, 115))

        screen.blit(
            self.font.render("Громкость музыки", True, (220, 225, 235)),
            (self.rect.left + 24, self.music_track.top - 8),
        )
        screen.blit(
            self.font.render("Громкость эффектов", True, (220, 225, 235)),
            (self.rect.left + 24, self.sfx_track.top - 8),
        )
        for key, track in (
            ("music_volume", self.music_track),
            ("sfx_volume", self.sfx_track),
        ):
            pygame.draw.rect(screen, (55, 61, 72), track, border_radius=6)
            fill = track.copy()
            fill.width = int(track.width * self.preferences.get(key, 0.0))
            pygame.draw.rect(screen, (95, 165, 220), fill, border_radius=6)
            knob_x = track.left + int(track.width * self.preferences.get(key, 0.0))
            pygame.draw.circle(screen, (235, 240, 250), (knob_x, track.centery), 9)

        if self.message:
            color = (245, 200, 125) if self.message.startswith("Не удалось") else (170, 205, 180)
            screen.blit(
                self.small_font.render(self.message, True, color),
                (self.rect.left + 24, self.rect.bottom - 34),
            )
