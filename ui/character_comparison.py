import pygame

from combat.card_database import is_mage_profession
from core import settings
from ui.character_card import CharacterCard
from ui.mage_card import MageCard
from ui.hud import draw_button


class CharacterComparison:
    """Reusable two-character card view with no dependency on a scene."""

    def __init__(self, action_font):
        self.action_font = action_font
        self.player_card = CharacterCard()
        self.opponent_card = CharacterCard()
        self.player_frame = pygame.Rect(settings.PLAYER_CARD_RECT)
        self.opponent_frame = pygame.Rect(settings.ENEMY_CARD_RECT)
        self.close_button = pygame.Rect(
            self.opponent_frame.right - 100,
            self.opponent_frame.y + 15,
            85,
            34,
        )
        self.challenge_button = pygame.Rect(settings.PROFILE_CHALLENGE_BUTTON_RECT)

    @staticmethod
    def _is_mage(profile):
        if not isinstance(profile, dict):
            return False
        # Все классы имеют одинаковые 7 статов — класс определяется только по type
        return is_mage_profession(profile.get("type"))

    @classmethod
    def _card_for_profile(cls, profile, current_card):
        card_type = MageCard if cls._is_mage(profile) else CharacterCard
        # Точный тип: MageCard — наследник CharacterCard
        return current_card if type(current_card) is card_type else card_type()

    def _draw_card(self, card, screen, frame, *, border_color, editable=False):
        card.draw(
            screen,
            frame,
            border_color=border_color,
            editable=editable,
        )

    def draw(self, screen, player_profile, opponent_profile, *, editable_player=True):
        self.player_card = self._card_for_profile(player_profile, self.player_card)
        self.opponent_card = self._card_for_profile(opponent_profile, self.opponent_card)
        self.player_card.sync(player_profile, title="ИГРОК", kind="player")
        self._draw_card(
            self.player_card,
            screen,
            self.player_frame,
            border_color=(80, 180, 120),
            editable=editable_player,
        )
        self.opponent_card.sync(opponent_profile, title="ПРОТИВНИК", kind="enemy")
        self._draw_card(
            self.opponent_card,
            screen,
            self.opponent_frame,
            border_color=(210, 100, 90),
        )
        draw_button(screen, self.challenge_button, "БРОСИТЬ ВЫЗОВ", self.action_font, color=(150, 75, 65))
        draw_button(screen, self.close_button, "ЗАКРЫТЬ", self.action_font, color=(70, 75, 90))

    def handle_click(self, position, player_profile):
        """Return an action and, for stat changes, the canonical card data."""
        self.player_card = self._card_for_profile(player_profile, self.player_card)
        self.player_card.sync(player_profile, title="ИГРОК", kind="player")
        change = self.player_card.stat_control_at(self.player_frame, position)
        if change is not None:
            stat_name, delta = change
            if self.player_card.adjust_stat(stat_name, delta):
                return "stat_change", self.player_card.data
            return "handled", None
        if self.close_button.collidepoint(position):
            return "close", None
        if self.challenge_button.collidepoint(position):
            return "challenge", None
        return None, None
