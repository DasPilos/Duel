import pygame
from pathlib import Path

from core import settings
from ui.hud import draw_button, draw_text
from ui.chat import ChatPanel


class TavernScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.regen_elapsed = 0.0
        self.chat = ChatPanel(session, "tavern")
        self.navigate = None
        self.background = None
        self.tavern_hotspots = (
            ("Выход на улицу", -400, -390, 130, 300, None),
            ("Главный зал", 384, -417, 126, 141, None),
            ("комната отдыха", 600, -347, 69, 85, None),
            ("Задний двор", 1000, -400, 55, 153, "backyard"),
            ("Хозяин трактира", 1000, -200, 85, 108, None),
            ("Искатели приключений", -300, -11, 167, 121, None),
        )
        background_path = Path(__file__).resolve().parent.parent / "assets" / "tavern" / "background_original.png"
        try:
            self.background = pygame.image.load(str(background_path)).convert()
        except (pygame.error, OSError):
            self.background = None

    def handle_event(self, event):
        if self.chat.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for _, hotspot, action in self._get_tavern_hotspots():
                if hotspot.collidepoint(event.pos) and action == "backyard":
                    self.navigate = "backyard"
                    self.finished = True
                    return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_b):
                self.finished = True
            elif event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True
    def update(self, dt):
        self.regen_elapsed += dt
        if self.regen_elapsed >= 1.0:
            steps = int(self.regen_elapsed)
            self.regen_elapsed -= steps
            self.session.regenerate_character(steps * 5)
        self.chat.update(dt)

    def draw(self, screen):
        if self.background is None:
            screen.fill((38, 27, 24))
        else:
            screen_width, screen_height = screen.get_size()
            background = pygame.transform.smoothscale(
                self.background,
                (screen_width, screen_height),
            )
            screen.blit(background, (0, 0))
        self._draw_hotspot_highlights(screen)
        self.chat.draw(screen)

    def _get_tavern_hotspots(self):
        chat_rect = self.chat.panel_rect
        return [
            (name, pygame.Rect(chat_rect.x + x, chat_rect.y + y, width, height), action)
            for name, x, y, width, height, action in self.tavern_hotspots
        ]

    def _draw_hotspot_highlights(self, screen):
        if self.background is None:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        for name, rect, _ in self._get_tavern_hotspots():
            if not rect.collidepoint(mouse_x, mouse_y):
                continue
            highlight = pygame.Surface(rect.size, pygame.SRCALPHA)
            highlight.fill((255, 205, 100, 24))
            screen.blit(highlight, rect.topleft)
            pygame.draw.rect(screen, (255, 215, 120, 180), rect, width=3, border_radius=8)
            label = self.small_font.render(name, True, (255, 230, 160))
            label_rect = label.get_rect(midbottom=(rect.centerx, rect.top - 6))
            screen.blit(label, label_rect)

    def close(self):
        pass
