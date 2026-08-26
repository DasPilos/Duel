import unittest
from unittest.mock import patch
from types import SimpleNamespace

from combat.battle import Battle
from combat.fighter import Fighter
from combat.progression import apply_xp, battle_xp, xp_to_next
from combat.group_battle import is_afk_draw, split_balanced_teams, visible_group_targets
from combat.resolver import resolve_attack
from scenes.duel_commentator import DuelCommentator


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

    def test_progression_thresholds_and_rewards(self):
        self.assertEqual(xp_to_next(1), 185)
        self.assertEqual(xp_to_next(20), 2940)
        self.assertEqual(xp_to_next(30), 0)
        self.assertEqual(battle_xp(1, 1, "win"), 20)
        self.assertEqual(battle_xp(1, 4, "win"), 27)
        self.assertEqual(battle_xp(7, 1, "win"), 0)
        self.assertEqual(battle_xp(1, 1, "draw"), 8)
        self.assertEqual(battle_xp(1, 1, "loss"), 5)

    def test_progression_level_up_keeps_hp_during_battle(self):
        fighter = Fighter("Тест")
        fighter.hp = 15
        fighter.xp = xp_to_next(fighter.level)

        self.assertEqual(apply_xp(fighter, 0), 1)
        self.assertEqual(fighter.hp, 15)
        self.assertEqual(fighter.level, 2)

    def test_group_battle_splits_participants_into_balanced_teams(self):
        participants = [
            {"id": index, "level": 1, "stats": {"strength": 5 + index, "agility": 5, "intuition": 5, "endurance": 5}}
            for index in range(10)
        ]

        teams = split_balanced_teams(participants, seed=7)

        self.assertEqual(sum(len(team) for team in teams), 10)
        self.assertTrue(all(team for team in teams))
        self.assertLessEqual(abs(sum(fighter["stats"]["strength"] + 15 for fighter in teams[0]) - sum(fighter["stats"]["strength"] + 15 for fighter in teams[1])), 10)

    def test_group_battle_hides_other_exchanges_but_marks_targets(self):
        teams = [
            [{"id": "a1", "hp": 100}, {"id": "a2", "hp": 100}, {"id": "a3", "hp": 100}],
            [{"id": "b1", "hp": 100}, {"id": "b2", "hp": 100}, {"id": "b3", "hp": 100}],
        ]
        exchanges = [{"attacker_id": "a1", "defender_id": "b1", "status": "waiting_response"}]

        targets = visible_group_targets("a1", teams, exchanges)

        self.assertEqual([target["target_available"] for target in targets], [False, True, True])
        self.assertNotIn("attacker_id", targets[0])

    def test_group_battle_afk_draw_requires_living_afk_fighter_on_both_teams(self):
        teams = [
            [{"id": "a1", "hp": 100}],
            [{"id": "b1", "hp": 100}],
        ]

        self.assertTrue(is_afk_draw(teams, {"a1", "b1"}))
        self.assertFalse(is_afk_draw(teams, {"a1"}))


class TestAttackResolver(unittest.TestCase):
    @patch("combat.resolver.random.random", return_value=99.0 / 100)
    def test_first_hit_uses_strength_against_half_endurance(self, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")

        result = resolve_attack(attacker, defender, False, 0)

        self.assertEqual(result["combo_level"], 1)
        self.assertEqual(result["damage"], 12)
        self.assertEqual(result["dice"], (0, 0))
        self.assertFalse(result["critical"])

    @patch("combat.resolver.random.random", return_value=99.0 / 100)
    def test_second_hit_gets_combo_bonus(self, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")

        result = resolve_attack(attacker, defender, False, 1)

        self.assertEqual(result["combo_level"], 2)
        self.assertEqual(result["damage"], 15)

    @patch("combat.resolver.random.random", return_value=99.0 / 100)
    def test_damage_has_minimum_one_after_endurance_reduction(self, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        attacker.stats["strength"] = 1
        defender.stats["endurance"] = 10

        result = resolve_attack(attacker, defender, False, 0)

        self.assertEqual(result["damage"], 1)

    @patch("combat.resolver.random.random", return_value=0.0)
    def test_dodge_cancels_the_attack(self, _random):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        defender.stats["agility"] = 20

        result = resolve_attack(attacker, defender, False, 0)

        self.assertTrue(result["dodged"])
        self.assertEqual(result["damage"], 0)

    @patch("combat.resolver.roll_critical_d8", return_value=2)
    @patch("combat.resolver.random.random", side_effect=(0.99, 0.0))
    def test_critical_hit_deals_half_damage_through_block(self, _random, _critical_dice):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        attacker.stats["intuition"] = 20

        result = resolve_attack(attacker, defender, True, 0)

        self.assertTrue(result["critical"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["damage"], 12)



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

    def test_draw_outcome_awards_xp_to_both_sides(self):
        player = Fighter("Игрок", 1)
        enemy = Fighter("Враг", 1)
        player.hp = 0
        enemy.hp = 0

        battle = Battle(player, enemy)

        self.assertEqual(battle.outcome(), "draw")
        self.assertEqual(battle.winner_name(), "Ничья")
        self.assertEqual(battle.xp_awarded, battle_xp(player.level, enemy.level, "draw"))
        self.assertEqual(battle.enemy_xp_awarded, battle_xp(enemy.level, player.level, "draw"))

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

    def test_commentator_writes_named_exchange(self):
        battle = SimpleNamespace(
            last_player_attack="head",
            last_player_hit=True,
            last_player_damage=21,
            last_player_dodged=False,
            last_player_critical=True,
            last_player_combo=1,
            last_enemy_attack="waist",
            last_enemy_hit=False,
            last_enemy_damage=0,
            last_enemy_dodged=False,
            last_enemy_critical=False,
            last_enemy_combo=0,
        )
        player = SimpleNamespace(name="Забияка", is_dead=lambda: False)
        enemy = SimpleNamespace(name="Безпроводной Душ", is_dead=lambda: False)
        scene = SimpleNamespace(player=player, enemy=enemy, battle=battle, comments=[])

        DuelCommentator(scene).add_combat_comments()

        segments = scene.comments[0]["segments"]
        text = "".join(segment["text"] for segment in segments)
        self.assertIn("Забияка", text)
        self.assertIn("Безпроводной Душ", text)
        self.assertIn("(-21 хп)", text)
        self.assertIn("(-0 хп)", text)
        self.assertGreaterEqual(len(segments), 5)


if __name__ == "__main__":
    unittest.main()
