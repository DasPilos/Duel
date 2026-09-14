import unittest
from types import SimpleNamespace

from combat.fighter import Fighter
from combat.progression import apply_xp, battle_xp, xp_to_next
from combat.group_battle import is_afk_draw, split_balanced_teams, visible_group_targets
from combat.mechanics import get_critical_chance
from scenes.duel_commentator import DuelCommentator


class TestFighter(unittest.TestCase):
    def test_initial_values(self):
        fighter = Fighter("Тест")

        self.assertEqual(fighter.stats, {
            "strength": 3,
            "agility": 3,
            "intuition": 3,
            "endurance": 4,
        })
        self.assertEqual(fighter.stat_points, 3)
        self.assertEqual(fighter.max_hp, 40)
        self.assertEqual(fighter.hp, fighter.max_hp)

    def test_endurance_updates_max_and_current_hp(self):
        fighter = Fighter("Тест")

        self.assertFalse(fighter.add_stat("endurance"))
        self.assertTrue(fighter.add_stat("strength"))
        self.assertEqual(fighter.strength, 4)
        self.assertEqual(fighter.stat_points, 2)

    def test_stat_limits(self):
        fighter = Fighter("Тест")

        self.assertFalse(fighter.remove_stat("strength"))
        self.assertTrue(fighter.add_stat("strength"))
        self.assertEqual(fighter.strength, 4)
        self.assertTrue(fighter.remove_stat("strength"))
        self.assertEqual(fighter.strength, 3)
        self.assertFalse(fighter.remove_stat("strength"))
        self.assertEqual(fighter.stat_points, 3)

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

    def test_intuition_gives_five_crit_and_three_anti_crit(self):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        attacker.stats["intuition"] = 6
        defender.stats["intuition"] = 5

        self.assertEqual(get_critical_chance(attacker, defender), 15)

        attacker.stats["intuition"] += 1
        self.assertEqual(get_critical_chance(attacker, defender), 20)

        defender.stats["intuition"] += 1
        self.assertEqual(get_critical_chance(attacker, defender), 17)

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


class TestCommentator(unittest.TestCase):
    def test_commentator_writes_named_exchange(self):
        battle = SimpleNamespace(
            last_exchange=[
                {
                    "side": "player",
                    "card": "Прямой удар",
                    "damage": 21,
                    "dodged": False,
                    "critical": True,
                    "healed": 0,
                },
                {
                    "side": "enemy",
                    "card": "Блок",
                    "damage": 0,
                    "dodged": False,
                    "critical": False,
                    "healed": 0,
                },
            ]
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
        self.assertGreaterEqual(len(segments), 3)


if __name__ == "__main__":
    unittest.main()
