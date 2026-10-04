import pygame
import math

from ui.hud import draw_button


class ExitMenu:
    QUIT_DURATION = 5.0

    def __init__(self):
        self.is_open = False
        self.page = "main"
        self.error = ""
        self.rect = pygame.Rect(0, 0, 500, 390)
        self.buttons = {}
        self.quit_remaining = None

    def open(self, error=None):
        self.is_open = True
        self.page = "main"
        self.error = error or ""
        self.quit_remaining = None

    @property
    def quitting(self):
        return self.quit_remaining is not None

    def begin_quit(self):
        self.is_open = False
        self.quit_remaining = self.QUIT_DURATION

    def update_quit(self, dt):
        if not self.quitting:
            return False
        self.quit_remaining = max(0.0, self.quit_remaining - max(0.0, dt))
        return self.quit_remaining <= 0.0

    def handle_event(self, event):
        if not self.is_open:
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.page == "settings":
                self.page = "main"
            else:
                self.is_open = False
                return "resume"
            return None
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        for action, button in self.buttons.items():
            if not button.collidepoint(event.pos):
                continue
            if action == "settings":
                self.page = "settings"
                return None
            if action == "back":
                self.page = "main"
                return None
            self.is_open = False
            return action
        return None

    def draw(self, screen, font, small_font):
        if self.quitting:
            progress = 1.0 - self.quit_remaining / self.QUIT_DURATION
            shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            shade.fill((0, 0, 0, min(240, int(progress * 240))))
            screen.blit(shade, (0, 0))
            countdown = max(1, math.ceil(self.quit_remaining))
            label = small_font.render(f"Выход через {countdown}...", True, (235, 225, 205))
            screen.blit(label, label.get_rect(center=screen.get_rect().center))
            return
        if not self.is_open:
            return
        self.rect.center = screen.get_rect().center
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (24, 29, 34), self.rect, border_radius=6)
        pygame.draw.rect(screen, (194, 161, 94), self.rect, 2, border_radius=6)
        title = font.render("НАСТРОЙКИ" if self.page == "settings" else "МЕНЮ", True,
                            (238, 220, 178))
        screen.blit(title, title.get_rect(midtop=(self.rect.centerx, self.rect.top + 24)))
        if self.error:
            error_surface = small_font.render(self.error, True, (232, 135, 120))
            screen.blit(error_surface, error_surface.get_rect(center=(self.rect.centerx, self.rect.top + 72)))
        self.buttons = {}
        if self.page == "settings":
            stub = small_font.render("Настройки появятся позже", True, (174, 175, 172))
            screen.blit(stub, stub.get_rect(center=(self.rect.centerx, self.rect.centery - 12)))
            actions = [("back", "НАЗАД")]
        else:
            actions = [
                ("settings", "НАСТРОЙКИ"),
                ("quit", "ПОКИНУТЬ ИГРУ"),
                ("resume", "ПРОДОЛЖИТЬ"),
            ]
        height = 42
        gap = 14
        total = len(actions) * height + (len(actions) - 1) * gap
        first_y = self.rect.centery - total // 2 + 20
        for index, (action, label) in enumerate(actions):
            button = pygame.Rect(self.rect.left + 60, first_y + index * (height + gap),
                                 self.rect.width - 120, height)
            color = (105, 69, 49) if action == "quit" else (54, 69, 78)
            draw_button(screen, button, label, small_font, color=color,
                        text_color=(236, 226, 203))
            self.buttons[action] = button