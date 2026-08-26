import pygame
from pathlib import Path

from core import settings
from ui.chat import ChatPanel
from ui.character_profile_overlay import CharacterProfileOverlay


class TavernScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.battle_button = pygame.Rect(780, 850, 360, 55)
        self.profile_overlay = CharacterProfileOverlay(self.small_font)
        self.chat = ChatPanel(session, "tavern", profile_overlay=self.profile_overlay)
        self.navigate = None
        # Эталонная ручная разметка (см память проекта): координаты заданы относительно chat.panel_rect и не пересчитываются автоматически.
        self.tavern_hotspots = (
            ("Выход на улицу", -400, -390, 130, 300, None),
            ("Главный зал", 384, -417, 126, 141, None),
            ("Комната отдыха", 600, -347, 69, 85, None),
            ("Задний двор", 1000, -400, 55, 153, "backyard"),
            ("Хозяин трактира", 1000, -200, 85, 108, None),
            ("Искатели приключений", -300, -11, 167, 121, None),
        )
        self.background = None
        background_path = Path(__file__).resolve().parent.parent / "assets" / "tavern" / "background_original.png"
        try:
            self.background = pygame.image.load(str(background_path)).convert()
        except (pygame.error, OSError):
            self.background = None

    def _hotspot_rect(self, x, y, width, height):
        chat_rect = self.chat.panel_rect
        return pygame.Rect(chat_rect.x + x, chat_rect.y + y, width, height)

    def handle_event(self, event):
        if self.chat.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for _, x, y, width, height, action in self.tavern_hotspots:
                if action is not None and self._hotspot_rect(x, y, width, height).collidepoint(event.pos):
                    self.navigate = action
                    self.finished = True
                    return
            if self.battle_button.collidepoint(event.pos):
                self.finished = True
                return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_b):
                self.finished = True
            elif event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True

    def update(self, dt):
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

        # Скрываем встроенную в картинку декоративную область чата.
        # Настоящий ChatPanel рисуется поверх и остается полностью функциональным.
        chat_cover = self.chat.panel_rect.inflate(6, 6)
        pygame.draw.rect(screen, (22, 24, 34), chat_cover, border_radius=10)

        mouse_pos = pygame.mouse.get_pos()
        for label, x, y, width, height, action in self.tavern_hotspots:
            rect = self._hotspot_rect(x, y, width, height)
            if not rect.collidepoint(mouse_pos):
                continue
            pygame.draw.rect(screen, (255, 220, 120), rect, width=2, border_radius=6)
            label_surface = self.small_font.render(label, True, (255, 230, 160))
            label_rect = label_surface.get_rect(midbottom=(rect.centerx, rect.top - 6))
            pygame.draw.rect(screen, (20, 18, 15), label_rect.inflate(12, 8))
            screen.blit(label_surface, label_rect)

        self.chat.draw(screen)
        self.profile_overlay.draw(screen)

    def close(self):
        pass
