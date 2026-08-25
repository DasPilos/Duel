import pygame

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
        self.battle_button = pygame.Rect(780, 850, 360, 55)
        self.regen_elapsed = 0.0
        self.chat = ChatPanel(session, "tavern")
        self.navigate = None
        self.backyard_button = pygame.Rect(1640, 35, 220, 45)

    def handle_event(self, event):
        if self.chat.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.backyard_button.collidepoint(event.pos):
            self.navigate = "backyard"
            self.finished = True
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_b):
                self.finished = True
            elif event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.battle_button.collidepoint(event.pos):
                self.finished = True

    def update(self, dt):
        self.regen_elapsed += dt
        if self.regen_elapsed >= 1.0:
            steps = int(self.regen_elapsed)
            self.regen_elapsed -= steps
            self.session.regenerate_character(steps * 5)
        self.chat.update(dt)

    def draw(self, screen):
        screen.fill((38, 27, 24))
        title = self.title_font.render("ТРАКТИР", True, (255, 220, 150))
        screen.blit(title, title.get_rect(center=(960, 100)))
        draw_text(screen, self.font, "Локация: Трактир", 120, 100, (220, 210, 190))
        draw_button(screen, self.backyard_button, "ЗАДНИЙ ДВОР", self.small_font, color=(110, 75, 50))

        self._draw_barkeeper(screen)
        draw_text(screen, self.font, "Бармен Картинка", 805, 535, (255, 220, 150))
        draw_text(screen, self.small_font, "NPC · хозяин трактира", 840, 565, (190, 175, 160))
        draw_text(screen, self.small_font, "Характеристики NPC", 1200, 300, (255, 220, 150))
        npc_stats = (
            "Сила: 12",
            "Ловкость: 8",
            "Интуиция: 10",
            "Выносливость: 14",
            "Роль: наставник",
        )
        for index, stat in enumerate(npc_stats):
            draw_text(screen, self.small_font, stat, 1200, 340 + index * 28, (215, 205, 190))

        self.chat.draw(screen)

    def _draw_barkeeper(self, screen):
        center_x = 960
        pygame.draw.circle(screen, (180, 125, 90), (center_x, 300), 58)
        pygame.draw.rect(screen, (110, 65, 38), (center_x - 78, 355, 156, 180), border_radius=24)
        pygame.draw.rect(screen, (210, 175, 120), (center_x - 78, 355, 156, 180), width=4, border_radius=24)
        pygame.draw.line(screen, (210, 175, 120), (center_x - 60, 400), (center_x - 140, 500), 18)
        pygame.draw.line(screen, (210, 175, 120), (center_x + 60, 400), (center_x + 140, 500), 18)
        pygame.draw.rect(screen, (95, 50, 30), (center_x - 120, 500, 240, 35), border_radius=5)

    def close(self):
        pass
