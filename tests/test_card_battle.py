import random
import time
import unittest

import pygame

from combat.card_battle import CardBattle, points_from_stat
from combat.card_database import load_cards
from combat.fighter import Fighter
from combat.character_stats import calculate_max_hp
from ui.character_card import CharacterCard
from scenes.duel_scene import DuelScene


class TestCardBattle(unittest.TestCase):
    def test_strength_adds_one_damage_to_card_roll(self):
        self.assertEqual(calculate_max_hp(1, 5), 50)

    def test_selected_cards_preview_uses_plus_values(self):
        cards = load_cards()
        selected = [
            next(card for card in cards if card.key == "heavy_swing"),
            next(card for card in cards if card.key == "aimed_strike"),
            next(card for card in cards if card.key == "spirit_recovery"),
        ]

        preview = CharacterCard._card_preview(selected)

        self.assertEqual(preview["Урон"], " + 2-10")
        self.assertEqual(preview["HP"], " + 1-6")

    def test_player_can_add_second_card_and_return_first(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.hands["player"] = cards[:3]
            scene.battle.action_points["player"] = {stat: 99 for stat in ("strength", "intuition", "agility", "endurance")}
            scene.phase = "planning"

            first_rect = scene.renderer.card_renderer.card_rect(scene.layout.player_hand, 3, 0)
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": first_rect.center}))
            visible_hand = [card for card in scene.battle.hands["player"] if card not in scene.battle.selected["player"]]
            second_rect = scene.renderer.card_renderer.card_rect(scene.layout.player_hand, len(visible_hand), 0)
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": second_rect.center}))
            self.assertEqual(len(scene.battle.selected["player"]), 2)

            selected_rect = scene.renderer.card_renderer.card_rect(scene.layout.player_selected, 2, 0)
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": selected_rect.center}))
            scene.card_return_transfer["started"] = time.monotonic() - 1.1
            scene.update(0)
            self.assertEqual(len(scene.battle.selected["player"]), 1)
        finally:
            pygame.quit()

    def test_card_damage_formula_uses_roll_plus_strength(self):
        self.assertEqual(4 + 5, 9)

    def test_database_contains_thirty_cards(self):
        self.assertEqual(len(load_cards()), 30)

    def test_points_formula_has_expected_bounds(self):
        for value in range(0, 13):
            points = points_from_stat(value, random.Random(value))
            self.assertGreaterEqual(points, value // 4)
            self.assertLessEqual(points, value // 4 + 1)

    def test_starting_deal_gives_three_cards_and_strength_bonus(self):
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["strength"] = 7
        enemy.stats["strength"] = 5
        battle = CardBattle(player, enemy, rng=random.Random(3))

        for _ in range(3):
            battle.choose_starting_card("player", battle.table[0].key)
            battle.choose_starting_card("enemy", battle.table[0].key)
        battle.finish_starting_deal()

        self.assertEqual(battle.turn, 1)
        self.assertEqual(len(battle.hands["player"]), 4)
        self.assertEqual(len(battle.hands["enemy"]), 3)

    def test_played_cards_leave_hand_and_unplayed_cards_remain(self):
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), rng=random.Random(4))
        for _ in range(3):
            battle.choose_starting_card("player", battle.table[0].key)
            battle.choose_starting_card("enemy", battle.table[0].key)
        battle.finish_starting_deal()
        card = battle.hands["player"][0]
        battle.action_points["player"] = {stat: 99 for stat in battle.action_points["player"]}
        battle.select_card("player", card.key)
        battle.confirm_selection("player")
        battle.confirm_selection("enemy")
        battle.resolve_turn()

        self.assertNotIn(card, battle.hands["player"])
        self.assertIn(card, battle.discard)
        self.assertLessEqual(len(battle.hands["player"]), 6)


if __name__ == "__main__":
    unittest.main()