import pygame

from core import settings
from scenes.duel_scene import DuelScene
from combat.card_battle import CardBattle
from combat.card_database import load_cards


class MageBattleScene(DuelScene):
    """Mage card battlefield using the existing card-battle mechanics."""

    def __init__(self, online_session=None, opponent=None):
        self.mage_battle = True
        self.player_status = "СТАРТОВЫЙ ДРАФТ"
        self.enemy_status = "СТАРТОВЫЙ ДРАФТ"
        super().__init__(online_session, opponent)
        self._configure_mage_layout()
        mage_cards = [card for card in load_cards() if card.group_name.startswith("Магия:")]
        if mage_cards:
            by_key = {card.key: card for card in mage_cards}
            selected = getattr(online_session, "selected_deck", None) if online_session else None
            player_keys = selected.get("cards", {}) if selected else {}
            if isinstance(player_keys, dict):
                player_keys = player_keys.keys()
            player_deck = [by_key[key] for key in player_keys if key in by_key]
            player_deck.extend(card for card in mage_cards if card not in player_deck)
            player_deck = player_deck[:22]

            enemy_keys = (opponent or {}).get("deck", [])
            enemy_deck = [by_key[key] for key in enemy_keys if key in by_key]
            enemy_deck.extend(card for card in mage_cards if card not in enemy_deck)
            enemy_deck = enemy_deck[:22]
            self.battle = CardBattle(
                self.player,
                self.enemy,
                cards=player_deck,
                enemy_cards=enemy_deck,
            )
            self.battle.mage_mode = True
            self.draft_next_side = "player"

    def _configure_mage_layout(self):
        """Arrange the mage duel like the shared battle-board design."""
        self.layout.card_table = pygame.Rect(20, 170, settings.WIDTH - 40, 520)
        self.layout.enemy_hand = pygame.Rect(410, 20, 1100, 130)
        self.layout.enemy_selected = pygame.Rect(390, 245, 1140, 120)
        self.layout.player_selected = pygame.Rect(390, 520, 1140, 120)
        self.layout.player_hand = pygame.Rect(300, 850, 1320, 180)
        self.layout.discard_rect = pygame.Rect(75, 285, 170, 300)
        self.layout.deck_rect = pygame.Rect(settings.WIDTH - 245, 285, 170, 300)
        self.layout.turn_bar = pygame.Rect(settings.WIDTH // 2 - 150, 715, 300, 18)
        self.layout.play_cards_button = pygame.Rect(settings.WIDTH // 2 + 185, 705, 250, 38)

    def draw(self, screen):
        super().draw(screen)
        if self.phase not in ("result", "result_transition"):
            font = pygame.font.SysFont("arial", 20)
            label = font.render("МАГИЧЕСКАЯ ДУЭЛЬ", True, (190, 140, 240))
            screen.blit(label, (screen.get_width() // 2 - label.get_width() // 2, 12))

    def update(self, dt):
        super().update(dt)
        if self.phase == "draft":
            self.player_status = "ВЫБОР 2 СТАРТОВЫХ КАРТ"
            self.enemy_status = "БОТ ВЫБИРАЕТ СВОИ 2 КАРТЫ"
        elif self.phase in ("planning", "waiting_enemy"):
            self.player_status = "ВАШ ХОД: ДО 2 КАРТ"
            self.enemy_status = "ОЖИДАНИЕ ХОДА БОТА"
        elif self.phase in ("clash", "damage"):
            self.player_status = "РАЗРЕШЕНИЕ КАРТ"
            self.enemy_status = "РАЗРЕШЕНИЕ КАРТ"