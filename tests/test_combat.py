import unittest
from unittest.mock import patch

from combat.battle import Battle
from combat.fighter import Fighter
from combat.resolver import resolve_attack


class TestFighter(unittest.TestCase):
    def test_initial_values(self):
        fighter = Fighter("Тест")

        self.assertEqual(fighter.stats, {
            "strength": 5,
            "agility": 5,
            "intuition": 5,
            "endurance": 5,
        })
        self.assertEqual(fighter.stat_points, 6)
        self.assertEqual(fighter.max_hp, 170)
        self.assertEqual(fighter.hp, fighter.max_hp)

    def test_endurance_updates_max_and_current_hp(self):
        fighter = Fighter("Тест")

        self.assertTrue(fighter.add_stat("endurance"))

        self.assertEqual(fighter.max_hp, 184)
        self.assertEqual(fighter.hp, 184)
        self.assertEqual(fighter.stat_points, 5)

    def test_stat_limits(self):
        fighter = Fighter("Тест")

        self.assertTrue(fighter.remove_stat("strength"))

        self.assertEqual(fighter.strength, 4)
        self.assertFalse(fighter.remove_stat("strength"))
        self.assertEqual(fighter.stat_points, 7)


class TestAttackResolver(unittest.TestCase):
    @patch("combat.resolver.random.random", return_value=99.0 / 100)
    @patch("combat.resolver.roll_2d6", return_value=(1, 1))
    def test_first_hit_has_no_combo_bonus(self, _roll, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")

        result = resolve_attack(attacker, defender, False, 0)

        self.assertEqual(result["combo_level"], 1)
        self.assertEqual(result["damage"], 12)
        self.assertFalse(result["critical"])

    @patch("combat.resolver.random.random", return_value=99.0 / 100)
    @patch("combat.resolver.roll_2d6", return_value=(1, 1))
    def test_second_hit_gets_combo_bonus(self, _roll, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")

        result = resolve_attack(attacker, defender, False, 1)

        self.assertEqual(result["combo_level"], 2)
        self.assertEqual(result["damage"], 14)


class TestBattleStatistics(unittest.TestCase):
    @staticmethod
    def _result(damage=0, blocked=False, dodged=False, critical=False, combo=0):
        return {
            "damage": damage,
            "dice": (1, 1),
            "critical": critical,
            "critical_dice": None,
            "critical_multiplier": 1,
            "blocked": blocked,
            "dodged": dodged,
            "combo_level": combo,
        }

    def test_zero_damage_resets_combo(self):
        battle = Battle(Fighter("Игрок"), Fighter("Враг"))
        battle.stats["player"]["current_combo"] = 3

        battle._record_attack("player", self._result(blocked=True))

        self.assertEqual(battle.stats["player"]["current_combo"], 0)

    @patch("combat.battle.resolve_attack")
    def test_defensive_stats_belong_to_defender(self, resolve):
        battle = Battle(Fighter("Игрок"), Fighter("Враг"))
        battle.choose_player_zones("head", ["body", "waist"])
        resolve.side_effect = [
            self._result(blocked=True),
            self._result(damage=10, combo=1),
        ]

        battle.enemy_choose_zones = lambda: ("head", ["body", "waist"])
        battle.resolve_turn()

        self.assertEqual(battle.stats["enemy"]["blocks"], 1)
        self.assertEqual(battle.stats["player"]["blocks"], 0)
        self.assertEqual(battle.stats["enemy"]["hits"], 1)
        self.assertEqual(battle.stats["enemy"]["damage"], 10)
        self.assertEqual(battle.player.hp, 160)

    def test_fifth_hit_resets_current_combo(self):
        battle = Battle(Fighter("Игрок"), Fighter("Враг"))

        battle._record_attack("player", self._result(damage=20, combo=5, critical=True))

        self.assertEqual(battle.stats["player"]["current_combo"], 0)
        self.assertEqual(battle.stats["player"]["max_combo"], 5)
        self.assertEqual(battle.stats["player"]["critical"], 1)


if __name__ == "__main__":
    unittest.main()
