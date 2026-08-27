import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_max_hp
from combat.fighter import Fighter
from ui.character_card import CharacterCard


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


if __name__ == "__main__":
    unittest.main()