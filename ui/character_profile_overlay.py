import pygame

from core import settings
from ui.character_card import CharacterCard
from ui.hud import draw_button


class CharacterProfileOverlay:
    """Reusable right-side profile card opened by any UI surface."""

    def __init__(self, action_font):
        self.action_font = action_font
        self.card = CharacterCard()
        self.frame = pygame.Rect(settings.ENEMY_CARD_RECT)
        self.close_button = pygame.Rect(
            self.frame.right - 100,
            self.frame.y + 15,
            85,
            34,
        )
        self.profile = None

    @property
    def is_open(self):
        return self.profile is not None

    def open(self, profile):
        self.profile = dict(profile)

    def close(self):
        self.profile = None

    def handle_click(self, position):
        if self.is_open and self.close_button.collidepoint(position):
            self.close()
            return True
        return False

    def draw(self, screen):
        if not self.is_open:
            return
        self.card.sync(self.profile, title="ПРОФИЛЬ ПЕРСОНАЖА", kind=self.profile.get("kind", "player"))
        self.card.draw(screen, self.frame, border_color=(210, 100, 90))
        draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.action_font, color=(70, 75, 90))
