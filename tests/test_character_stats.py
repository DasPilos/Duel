import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_max_hp
from combat.fighter import Fighter
from ui.character_card import CharacterCard
from ui.character_profile_overlay import CharacterProfileOverlay


class CharacterStatTests(unittest.TestCase):
    def test_max_hp_formula_matches_level_and_endurance(self):
        self.assertEqual(calculate_max_hp(1, 5), 170)
        self.assertEqual(calculate_max_hp(3, 7), 238)

    def test_endurance_increase_preserves_gained_health(self):
        state = adjust_stats(
            {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            120,
            170,
            1,
            "endurance",
            1,
        )

        self.assertEqual(state["max_hp"], 184)
        self.assertEqual(state["hp"], 134)
        self.assertEqual(state["stat_points"], 5)

    def test_stat_decrease_cannot_go_below_minimum(self):
        state = adjust_stats(
            {"strength": 4, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            170,
            170,
            1,
            "strength",
            -1,
        )

        self.assertIsNone(state)

    def test_card_and_fighter_produce_matching_stat_state(self):
        pygame.init()
        try:
            fighter = Fighter("Тест")
            card = CharacterCard()
            card.sync({
                "name": "Тест",
                "level": fighter.level,
                "hp": fighter.hp,
                "max_hp": fighter.max_hp,
                "stats": fighter.stats,
                "stat_points": fighter.stat_points,
            })

            self.assertTrue(fighter.add_stat("endurance"))
            self.assertTrue(card.adjust_stat("endurance", 1))
            self.assertEqual(card.data["stats"], fighter.stats)
            self.assertEqual(card.data["stat_points"], fighter.stat_points)
            self.assertEqual(card.data["hp"], fighter.hp)
            self.assertEqual(card.data["max_hp"], fighter.max_hp)
        finally:
            pygame.quit()

    def test_profile_overlay_applies_player_card_stat_click(self):
        pygame.init()
        try:
            overlay = CharacterProfileOverlay(pygame.font.Font(None, 18))
            overlay.open({"name": "Соперник", "stats": {}})
            overlay.player_card.sync({
                "name": "Игрок",
                "level": 1,
                "hp": 170,
                "max_hp": 170,
                "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
                "stat_points": 6,
            })
            _, plus = overlay.player_card._stat_control_rects(
                overlay.player_frame,
                overlay.player_frame.bottom - 92,
            )

            action, profile = overlay.handle_click(plus.center)

            self.assertEqual(action, "stat_change")
            self.assertEqual(profile["stats"]["strength"], 6)
            self.assertEqual(profile["stat_points"], 5)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()