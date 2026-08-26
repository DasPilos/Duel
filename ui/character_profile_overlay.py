import pygame

from core import settings
from ui.character_card import CharacterCard
from ui.hud import draw_button


class CharacterProfileOverlay:
    """Reusable right-side profile card opened by any UI surface."""

    def __init__(self, action_font):
        self.action_font = action_font
        self.player_card = CharacterCard()
        self.card = CharacterCard()
        self.player_frame = pygame.Rect(settings.PLAYER_CARD_RECT)
        self.frame = pygame.Rect(settings.ENEMY_CARD_RECT)
        self.close_button = pygame.Rect(
            self.frame.right - 100,
            self.frame.y + 15,
            85,
            34,
        )
        self.profile = None
        self.counterpart = None

    @property
    def is_open(self):
        return self.profile is not None

    def open(self, profile, counterpart=None):
        self.profile = dict(profile)
        self.counterpart = dict(counterpart) if isinstance(counterpart, dict) else counterpart

    def close(self):
        self.profile = None
        self.counterpart = None

    def handle_click(self, position):
        if self.is_open and self.close_button.collidepoint(position):
            self.close()
            return True
        return False

    def draw(self, screen, opponent=None, show_counterpart=True):
        if not self.is_open:
            return
        opponent = self.counterpart if self.counterpart is not None else opponent
        if show_counterpart and opponent is not None:
            self.player_card.sync(opponent, title="ТЕКУЩИЙ ИГРОК", kind="player")
            self.player_card.draw(
                screen,
                self.player_frame,
                border_color=(80, 180, 120),
                opponent=self.profile,
            )
        self.card.sync(self.profile, title="ПРОФИЛЬ ПЕРСОНАЖА", kind=self.profile.get("kind", "player"))
        self.card.draw(screen, self.frame, border_color=(210, 100, 90), opponent=opponent)
        draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.action_font, color=(70, 75, 90))
