import pygame

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