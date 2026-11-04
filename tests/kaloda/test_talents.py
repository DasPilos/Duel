import random
import unittest

from kaloda.combat.card_battle import CardBattle
from kaloda.combat.card_database import Card, cards_for_type
from kaloda.combat.character_stats import calculate_max_hp, calculate_max_mana
from kaloda.combat.fighter import Fighter
from kaloda.combat.talents import TALENT_TREES, talent_effects
from kaloda.combat.arena_battle import ARENA_SIZE, KOBOLD_DECK, ArenaBattle, create_kobold


class TalentEffectsTests(unittest.TestCase):
    def test_each_profession_has_ten_levels_and_automatic_level_three_passive(self):
        self.assertEqual(set(TALENT_TREES), {
            "necromancer", "warrior", "archer", "assassin", "mage",
        })
        for profession, tree in TALENT_TREES.items():
            with self.subTest(profession=profession):
                self.assertEqual([entry["level"] for entry in tree], list(range(1, 11)))
                self.assertTrue(tree[2]["passive"])
                self.assertNotIn("options", tree[2])

    def test_level_three_passives_change_derived_class_stats(self):
        warrior = Fighter("Воин", 3, "warrior")
        warrior.stats["strength"] = 4
        warrior.recalculate_parameters()
        self.assertEqual(
            warrior.max_hp,
            calculate_max_hp(3, warrior.endurance, "warrior") + 8,
        )

        mage = Fighter("Маг", 3, "mage")
        mage.recalculate_parameters()
        self.assertEqual(
            mage.max_mp,
            calculate_max_mana(mage.intellect, "mage") + mage.wisdom * 2,
        )

    def test_talent_effects_apply_resource_regeneration_and_draft_bonuses(self):
        effects = talent_effects(
            "necromancer", {"2": "regen_2", "6": "draft_1"}, 6
        )
        self.assertEqual(effects["resource_regen"], 2)
        self.assertEqual(effects["starting_draft_cards"], 1)

        player = Fighter("Некромант", 6, "necromancer")
        player.set_talents({"6": "draft_1"})
        enemy = Fighter("Противник", 1, "warrior")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("necromancer"),
            enemy_cards=cards_for_type("warrior"),
            rng=random.Random(3),
        )
        self.assertEqual(battle.starting_random_limits["player"], 4)
        self.assertEqual(battle.hand_limit_for("player"), 7)
        self.assertEqual(battle.hand_limit_for("enemy"), 7)
        for side in ("player", "enemy"):
            for _ in range(2):
                battle.choose_starting_card(side, battle.table_for(side)[0].key)
        battle.finish_starting_deal()
        self.assertEqual(len(battle.hands["player"]), 6)

        hand_bonus = Fighter("Воин", 6, "warrior")
        hand_bonus.set_talents({"6": "hand_1"})
        hand_battle = CardBattle(
            hand_bonus,
            Fighter("Противник", 1, "warrior"),
            cards=cards_for_type("warrior"),
            enemy_cards=cards_for_type("warrior"),
            rng=random.Random(3),
        )
        self.assertEqual(hand_battle.hand_limit_for("player"), 8)
        self.assertEqual(hand_battle.hand_limit_for("enemy"), 7)

        regenerating = Fighter("Некромант", 6, "necromancer")
        regenerating.set_talents({"2": "regen_2"})
        regenerating.unique_resource_current = 0
        regenerating.recover_unique_resource(6)
        self.assertEqual(regenerating.unique_resource_current, 16)

    def test_burning_card_includes_selected_resource_recovery_talents(self):
        player = Fighter("Некромант", 8, "necromancer")
        player.set_talents({"2": "burn_20", "8": "burn_25"})
        player.unique_resource_max = 100
        player.unique_resource_current = 0
        enemy = Fighter("Противник", 1, "warrior")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("necromancer"),
            enemy_cards=cards_for_type("warrior"),
            rng=random.Random(3),
        )
        card = cards_for_type("necromancer")[0]
        battle.hands["player"] = [card]

        self.assertTrue(battle.burn_card("player", card.key))
        self.assertEqual(player.unique_resource_current, 60)

    def test_archer_passive_extends_non_melee_arena_card_range(self):
        player = Fighter("Лучник", 5, "archer")
        player.set_talents({"5": "move_1"})
        player.unique_resource_current = 20
        battle = ArenaBattle(
            player,
            create_kobold(),
            cards_for_type("archer"),
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (0, 7),
            (3, 7),
            enemy_deck=KOBOLD_DECK,
            rng=random.Random(3),
        )
        ranged_attack = Card(
            key="talent_test_ranged",
            name="Выстрел",
            group_name="Лучник: Тест",
            resource_type="accuracy",
            resource_cost=0,
            effect_type="damage",
            effect_data={"dice": "1d1", "range": 2},
            drop_chance=1,
        )
        self.assertGreater(battle.dist("player", "enemy"), 2)
        self.assertEqual(player.arena_move_range_bonus, 1)
        player.unique_resource_current = 0
        self.assertNotIn("enemy", battle.card_targets(ranged_attack))
        player.unique_resource_current = 20
        self.assertIn("enemy", battle.card_targets(ranged_attack))

    def test_assassin_critical_passive_heals_for_quarter_of_damage(self):
        player = Fighter("Ассасин", 3, "assassin")
        player.max_hp = 100
        player.hp = 50
        enemy = Fighter("Противник", 1, "warrior")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("assassin"),
            enemy_cards=cards_for_type("warrior"),
            rng=random.Random(3),
        )
        battle.phys_state["player"]["guaranteed_crits"] = 1
        attack = Card(
            key="talent_test_critical",
            name="Критический удар",
            group_name="Ассасин: Тест",
            resource_type="concentration",
            resource_cost=0,
            effect_type="damage",
            effect_data={"dice": "1d1"},
            drop_chance=1,
        )

        event = battle._resolve_card("player", attack)

        self.assertTrue(event["critical"])
        self.assertEqual(event["healed"], event["damage"] // 4)
        self.assertEqual(player.hp, 50 + event["healed"])

    def test_mage_passive_adds_magic_damage_per_three_intellect(self):
        player = Fighter("Маг", 3, "mage")
        player.stats["intellect"] = 6
        player.recalculate_parameters()
        enemy = Fighter("Противник", 1, "warrior")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("mage"),
            enemy_cards=cards_for_type("warrior"),
            rng=random.Random(3),
        )
        attack = Card(
            key="talent_test_spell",
            name="Искра",
            group_name="Магия: Тест",
            resource_type="mana",
            resource_cost=0,
            effect_type="mage_damage",
            effect_data={"damage": 5},
            drop_chance=1,
        )

        event = battle._resolve_card("player", attack)

        self.assertEqual(event["damage"], 5 + player.wisdom + 2)


if __name__ == "__main__":
    unittest.main()
