import math
import unittest

from kaloda.combat.card_battle import CardBattle
from kaloda.combat.card_database import Card, cards_for_type
from kaloda.combat.fighter import Fighter
from kaloda.combat.mechanics import get_dodge_chance


class FixedRandom:
    """random() >= любые шансы уворота/крита: всё попадает и без критов."""

    def __init__(self, value=0.99):
        self.value = value

    def random(self):
        return self.value

    @staticmethod
    def randint(start, _end):
        return start

    @staticmethod
    def shuffle(_items):
        return None

    @staticmethod
    def randrange(stop):
        return 0


def _card(profession, key):
    return next(card for card in cards_for_type(profession) if card.key == key)


def _battle(attacker="warrior", defender="warrior", rng=None):
    player = Fighter("A", 5, profession_type=attacker)
    enemy = Fighter("B", 5, profession_type=defender)
    for fighter in (player, enemy):
        fighter.unique_resource_current = 999
        fighter.temporary_dodge_chance_modifier = 0
    battle = CardBattle(player, enemy, cards=[], rng=rng or FixedRandom())
    return battle, player, enemy


class PhysicalEffectTests(unittest.TestCase):
    def test_fire_electric_reaction_damages_status_holder_not_player_caster(self):
        battle, player, enemy = _battle("mage", "warrior")
        battle.mage_mode = True
        player.mp = player.max_mp
        player.stats["harmony"] = 10
        enemy.stats["harmony"] = 0
        player_hp = player.hp

        for key in ("mage_flash", "mage_lightning_strike"):
            card = _card("mage", key)
            hp_before = enemy.hp
            event = battle._resolve_card("player", card)
            battle._apply_pending_mage_effects()
            self.assertEqual(event["damage"], hp_before - enemy.hp)

        self.assertEqual(player.hp, player_hp)
        self.assertIn("blinding", [status["name"] for status in battle.mage_statuses["enemy"]])
        self.assertNotIn("blinding", [status["name"] for status in battle.mage_statuses["player"]])
        self.assertNotIn("огонь", [status["name"] for status in battle.mage_statuses["enemy"]])
        self.assertNotIn("электро", [status["name"] for status in battle.mage_statuses["enemy"]])

    def test_assassin_deck_uses_revised_costs_and_effect_values(self):
        cards = {card.key: card for card in cards_for_type("assassin")}
        expected_costs = {
            "assassin_poison_strike": 5,
            "assassin_poison_blade": 11,
            "assassin_poison_rain": 13,
            "assassin_poison_infusion": 9,
            "assassin_poison_cascade": 14,
            "assassin_poison_extraction": 11,
            "assassin_poison_execution": 39,
            "assassin_numbness": 14,
            "assassin_wormwood": 10,
            "assassin_hemlock": 8,
            "assassin_datura": 7,
            "assassin_poison_vines": 10,
            "assassin_neurotoxins": 24,
            "assassin_overdose": 18,
            "assassin_antidote_dispel": 13,
        }

        self.assertEqual({key: cards[key].resource_cost for key in expected_costs}, expected_costs)
        self.assertEqual(cards["assassin_poison_infusion"].effect_data["crit_chance_percent"], 16)
        self.assertEqual(cards["assassin_wormwood"].effect_data["heal_endurance"], 3)
        self.assertEqual(cards["assassin_overdose"].effect_data["poison"], 2)
        self.assertEqual(cards["assassin_overdose"].effect_data["poison_cap_bonus"], 4)
        self.assertEqual(cards["assassin_overdose"].effect_data["poison_cap_duration"], 4)

    def test_bleed_ticks_next_turns_and_is_not_lethal(self):
        battle, _player, enemy = _battle()
        test_bleed = Card("test_bleed", "Тестовое кровотечение", "Боец: Тест", "rage", 0,
                          "damage", {"dice": 8, "bleed_percent": 8})
        battle._resolve_card("player", test_bleed)
        self.assertEqual(len(battle.bleeds["enemy"]), 1)
        hp = enemy.hp
        battle._tick_physical_effects()
        self.assertLess(enemy.hp, hp)
        enemy.hp = 1
        battle._tick_physical_effects()
        self.assertEqual(enemy.hp, 1)
        self.assertEqual(battle.bleeds["enemy"], [])

    def test_poison_stacks_and_execution_uses_them(self):
        battle, player, enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_poison_cascade"))
        self.assertEqual(len(battle.poisons["enemy"]), 3)
        hp = enemy.hp
        execution = _card("assassin", "assassin_poison_execution")
        event = battle._resolve_card("player", execution)
        multiplier = execution.effect_data["poison_damage_multiplier"]
        self.assertEqual(event["damage"], 3 * multiplier + player.strength)
        self.assertLess(enemy.hp, hp)

    def test_poison_onslaught_applies_one_poison_per_hit(self):
        battle, _player, _enemy = _battle("assassin", "warrior")

        battle._resolve_card("player", _card("assassin", "assassin_poison_rain"))

        self.assertEqual(len(battle.poisons["enemy"]), 3)

    def test_hemlock_applies_poison_before_checking_stun_threshold(self):
        battle, _player, _enemy = _battle("assassin", "warrior")
        battle._add_poison("player", 4)

        event = battle._resolve_card("player", _card("assassin", "assassin_hemlock"))

        self.assertEqual(len(battle.poisons["enemy"]), 5)
        self.assertEqual(battle.mage_stuns["enemy"], 1)
        self.assertIn("ОГЛУШЕНИЕ", event["effect_text"])

    def test_poison_ticks_once_for_two_percent_and_cold_pauses_it(self):
        battle, _player, enemy = _battle("archer", "warrior")
        enemy.max_hp = 500
        enemy.hp = 500
        battle._add_poison("player", 8)

        self.assertEqual(len(battle.poisons["enemy"]), 5)
        battle._tick_poison("enemy")
        self.assertEqual(enemy.hp, 490)
        self.assertEqual(len(battle.poisons["enemy"]), 4)

        battle.mage_statuses["enemy"].append({"name": "холод", "remaining": 2, "stacks": 0})
        battle._add_poison("player", 1)
        battle._tick_poison("enemy")

        self.assertEqual(enemy.hp, 490)
        self.assertEqual(len(battle.poisons["enemy"]), 4)

    def test_poison_ticks_when_poisoned_fighter_finishes_their_turn(self):
        battle, _player, enemy = _battle("assassin", "warrior")
        battle._add_poison("player", 1)
        hp_before = enemy.hp
        battle.turn_order = ("player", "enemy")
        battle.active_side = "player"

        self.assertFalse(battle.complete_side_turn())
        self.assertEqual(enemy.hp, hp_before)

        battle.complete_side_turn()

        self.assertEqual(enemy.hp, hp_before - math.ceil(enemy.max_hp * 0.02))
        self.assertEqual(len(battle.poisons["enemy"]), 0)

    def test_barrage_records_damage_for_each_strike(self):
        battle, player, _enemy = _battle("archer", "warrior")
        barrage = _card("archer", "archer_barrage")

        event = battle._resolve_card("player", barrage)

        self.assertEqual(len(event["hit_results"]), 8)
        self.assertEqual(
            [hit["damage"] for hit in event["hit_results"]],
            [barrage.effect_data["dice"] + player.strength] * 8,
        )
        self.assertEqual(sum(hit["damage"] for hit in event["hit_results"]), event["damage"])

    def test_heather_deals_two_plus_strength_and_applies_two_poison_stacks(self):
        battle, player, enemy = _battle("archer", "warrior")
        hp_before = enemy.hp

        event = battle._resolve_card("player", _card("archer", "archer_heather"))

        self.assertEqual(event["damage"], 2 + player.strength)
        self.assertEqual(enemy.hp, hp_before - event["damage"])
        self.assertEqual(len(battle.poisons["enemy"]), 2)

    def test_entangling_vine_limits_target_to_one_card(self):
        battle, _player, enemy = _battle("archer", "warrior")
        battle._resolve_card("player", _card("archer", "archer_entangling_vine"))
        first = Card("first", "First", "Боец: Test", "rage", 0, "damage", {"dice": 1})
        second = Card("second", "Second", "Боец: Test", "rage", 0, "damage", {"dice": 1})
        battle.hands["enemy"] = [first, second]
        battle.active_side = "enemy"

        self.assertTrue(battle.select_card("enemy", first.key))
        self.assertFalse(battle.select_card("enemy", second.key))

    def test_entangle_stacks_from_distinct_sources_up_to_three(self):
        battle, _player, _enemy = _battle("archer", "warrior")
        cards = [
            Card(
                f"vine_{index}", "Оплетение", "Лучник: Проворный герой",
                "accuracy", 0, "damage_buff", {"entangle": index + 1},
            )
            for index in range(4)
        ]

        for card in cards:
            battle._apply_enemy_debuffs("player", card)

        entangles = [buff for buff in battle.phys_buffs["enemy"] if buff.get("entangled")]
        self.assertEqual(len(entangles), 3)
        self.assertEqual({buff["entangle_source"] for buff in entangles}, {card.key for card in cards[:3]})
        self.assertEqual(battle._buff("enemy", "entangled"), 3)

    def test_agile_hero_healing_contract_and_shield_cards(self):
        battle, player, _enemy = _battle("archer", "warrior")
        player.hp -= 20
        moss = battle._resolve_card("player", _card("archer", "archer_healing_moss"))
        self.assertEqual(moss["healed"], 10 + player.endurance)

        hp_before = player.hp
        mana_before = player.mp
        battle._resolve_card("player", _card("archer", "archer_blood_sacrifice"))
        self.assertEqual(player.hp, hp_before - int(player.max_hp * 0.2))
        self.assertEqual(player.mp, mana_before - math.ceil(player.max_mp * 0.25))
        self.assertEqual(battle._buff("player", "agility_bonus"), 10)

        battle._resolve_card("player", _card("archer", "archer_oak_bulwark"))
        hp_before = player.hp
        self.assertEqual(battle.phys_shields["player"], 10 + player.agility + 10)
        battle._mage_take_damage("player", 10 + player.agility + 10)
        self.assertEqual(player.hp, hp_before)

    def test_healing_fern_cleanses_debuffs_but_keeps_buffs(self):
        battle, _player, _enemy = _battle("archer", "warrior")
        battle._add_buff("player", 2, mana_regen_debuff=50)
        battle._add_buff("player", 2, damage_percent=10)
        battle.bleeds["player"].append({"damage": 2, "remaining": 2, "source": "enemy"})
        battle._add_poison("enemy", 2)
        battle.mage_stuns["player"] = 1
        battle.mage_statuses["player"].extend((
            {"name": "огонь", "remaining": 2, "stacks": 1},
            {"name": "electric_cold_immunity", "remaining": 1},
        ))

        battle._resolve_card("player", _card("archer", "archer_healing_fern"))

        self.assertEqual(battle._buff("player", "mana_regen_debuff"), 0)
        self.assertEqual(battle._buff("player", "damage_percent"), 10)
        self.assertEqual(battle.bleeds["player"], [])
        self.assertEqual(battle.poisons["player"], [])
        self.assertEqual(battle.mage_stuns["player"], 0)
        self.assertEqual([status["name"] for status in battle.mage_statuses["player"]], ["electric_cold_immunity"])

    def test_hidden_step_guarantees_one_dodge(self):
        battle, _player, _enemy = _battle("archer", "warrior", rng=FixedRandom(0))
        battle._resolve_card("player", _card("archer", "archer_hidden_step"))
        attack = Card("attack", "Attack", "Боец: Test", "rage", 0, "damage", {"dice": 10})

        event = battle._resolve_card("enemy", attack)

        self.assertTrue(event["dodged"])
        self.assertEqual(event["damage"], 0)
        self.assertEqual(battle.phys_state["player"]["guaranteed_dodges"], 0)

    def test_forest_spirit_absorbs_damage_and_removes_bonuses_when_killed(self):
        battle, player, _enemy = _battle("archer", "warrior")
        enemy_hp_before = battle.enemy.hp
        summon_event = battle._resolve_card("player", _card("archer", "archer_forest_spirit"))
        hp_before = player.hp
        attack = Card("attack", "Attack", "Боец: Test", "rage", 0, "damage", {"dice": 20})

        self.assertEqual(summon_event["damage"], 0)
        self.assertEqual(battle.enemy.hp, enemy_hp_before)
        self.assertEqual(battle.phys_spirits["player"]["max_hp"], 20 + player.agility)
        self.assertEqual(battle._buff("player", "dodge_percent"), 15)
        self.assertEqual(battle._buff("player", "damage_percent"), 10)
        for _ in range(8):
            battle._tick_physical_effects()
        self.assertIsNotNone(battle.phys_spirits["player"])
        self.assertEqual(battle._buff("player", "dodge_percent"), 15)
        battle._mage_take_damage("player", 10)
        self.assertEqual(battle.phys_spirits["player"]["hp"], 10 + player.agility)
        event = battle._resolve_card("enemy", attack)

        self.assertIsNone(battle.phys_spirits["player"])
        self.assertEqual(battle._buff("player", "dodge_percent"), 0)
        self.assertEqual(player.hp, hp_before - event["damage"])

    def test_poison_extraction_converts_poison_to_crit(self):
        battle, _player, _enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_poison_cascade"))
        battle._resolve_card("player", _card("assassin", "assassin_poison_extraction"))
        self.assertEqual(battle.poisons["enemy"], [])
        self.assertEqual(battle._buff("player", "crit_chance"), 6)

    def test_numbness_blocks_healing_for_three_turns(self):
        battle, _player, enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_numbness"))
        hp_before = enemy.hp

        healed = battle._heal("enemy", 50)

        self.assertEqual(healed, 0)
        self.assertEqual(enemy.hp, hp_before)

    def test_neurotoxins_blocks_only_damage_cards(self):
        battle, _player, _enemy = _battle("assassin", "assassin")
        battle._resolve_card("player", _card("assassin", "assassin_neurotoxins"))
        battle.active_side = "enemy"

        self.assertFalse(battle.can_select("enemy", _card("assassin", "assassin_poison_strike")))
        self.assertTrue(battle.can_select("enemy", _card("assassin", "assassin_poison_cascade")))

    def test_overdose_applies_two_poison_and_temporarily_raises_limit_to_nine(self):
        battle, _player, _enemy = _battle("assassin", "warrior")
        battle._resolve_card("player", _card("assassin", "assassin_overdose"))
        self.assertEqual(len(battle.poisons["enemy"]), 2)

        for _ in range(3):
            battle._add_poison("player", 3)

        self.assertEqual(len(battle.poisons["enemy"]), 9)

    def test_mana_burn_and_bonus_on_empty_mana(self):
        battle, _player, enemy = _battle("archer", "mage")
        enemy.mp = 5
        hp = enemy.hp
        mana_burn = Card(
            "test_mana_burn", "Тестовый выстрел", "Лучник: Проворный герой",
            "accuracy", 0, "damage", {"dice": 8, "burn_mana": 7, "burn_damage_percent": 3},
        )
        event = battle._resolve_card("player", mana_burn)
        self.assertEqual(enemy.mp, 0)
        self.assertIn("МАНЫ", event["effect_text"])
        self.assertLess(enemy.hp, hp - 1)

    def test_buff_cards_do_not_burn_mana_immediately(self):
        battle, _player, enemy = _battle("archer", "mage")
        mana = enemy.mp
        mana_burn_buff = Card(
            "test_mana_burn_buff", "Тестовое усиление", "Лучник: Проворный герой",
            "accuracy", 0, "damage_buff", {"burn_mana_percent": 2, "duration": 2},
        )
        battle._resolve_card("player", mana_burn_buff)
        self.assertEqual(enemy.mp, mana)
        self.assertEqual(battle._buff("player", "burn_bonus_max_percent"), 2)

    def test_heal_percent_heals_missing_hp(self):
        battle, player, _enemy = _battle()
        player.hp = player.max_hp // 2
        event = battle._resolve_card("player", _card("warrior", "warrior_valen_cleave"))
        self.assertGreater(event["healed"], 0)

    def test_valentine_healing_does_not_trigger_against_invulnerability(self):
        battle, player, _enemy = _battle()
        player.hp = 20
        battle.invulnerable["enemy"] = True

        event = battle._resolve_card("player", _card("warrior", "warrior_valen_strike"))

        self.assertEqual(event["damage"], 0)
        self.assertEqual(event["healed"], 0)
        self.assertEqual(player.hp, 20)

    def test_assassin_critical_generates_fifteen_concentration(self):
        battle, assassin, _enemy = _battle("assassin", "warrior", rng=FixedRandom())
        assassin.unique_resource_current = 25
        assassin.temporary_critical_chance_modifier = 100

        event = battle._resolve_card("player", _card("assassin", "assassin_poison_strike"))

        self.assertTrue(event["critical"])
        self.assertEqual(assassin.unique_resource_current, 35)

    def test_multi_hit_card_rolls_evasion_crit_and_heals_per_hit(self):
        class CountingRandom(FixedRandom):
            def __init__(self):
                super().__init__(0.99)
                self.calls = 0

            def random(self):
                self.calls += 1
                return self.value

        rng = CountingRandom()
        battle, player, enemy = _battle(rng=rng)
        player.hp = 20
        player.stats["strength"] = 0
        card = Card(
            "three_hits", "Три удара", "Боец: Тест", "rage", 0, "damage",
            {"dice": 4, "hits": 3, "heal_percent": 50},
        )

        event = battle._resolve_card("player", card)

        self.assertEqual(event["damage"], 12)
        expected_hp = 20
        expected_healing = 0
        for _ in range(3):
            healed = (player.max_hp - expected_hp + 1) // 2
            expected_hp += healed
            expected_healing += healed
        self.assertEqual(event["healed"], expected_healing)
        self.assertEqual(player.hp, expected_hp)
        self.assertEqual(event["hits"], 3)
        self.assertEqual(rng.calls, 6)

    def test_blessing_theft_redirects_enemy_healing(self):
        battle, player, enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_fog_curse"))
        enemy.hp = 10
        player.hp = 10
        healed = battle._heal("enemy", 20)
        self.assertEqual(healed, 12)
        self.assertEqual(player.hp, 18)

    def test_buffs_expire(self):
        battle, _player, _enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_blood_pact"))
        self.assertEqual(battle._buff("player", "damage_percent"), 23)
        for _ in range(3):
            battle._tick_physical_effects()
        self.assertEqual(battle._buff("player", "damage_percent"), 0)

    def test_buff_duration_does_not_tick_on_the_round_it_is_applied(self):
        battle, _player, _enemy = _battle()
        battle._resolve_card("player", _card("warrior", "warrior_blood_pact"))

        battle._tick_physical_effects()
        self.assertEqual(battle._buff("player", "damage_percent"), 23)
        battle._tick_physical_effects()
        self.assertEqual(battle._buff("player", "damage_percent"), 23)
        battle._tick_physical_effects()
        self.assertEqual(battle._buff("player", "damage_percent"), 0)

    def test_stun_blocks_card_selection(self):
        battle, _player, enemy = _battle("archer", "warrior")
        enemy.stats["agility"] = 8
        battle.begin_next_turn()
        battle._stun("enemy")
        card = _card("warrior", "warrior_valen_strike")
        battle.hands["enemy"] = [card]
        self.assertFalse(battle.can_select("enemy", card))

    def test_no_miss_ignores_dodge(self):
        battle, _player, enemy = _battle("archer", "archer", rng=FixedRandom(0.0))
        enemy.temporary_dodge_chance_modifier = 100
        event = battle._resolve_card("player", _card("archer", "archer_hunt_stance"))
        self.assertFalse(event["dodged"])
        self.assertGreater(event["damage"], 0)

    def test_equipped_block_prevents_physical_attack_damage(self):
        battle, _player, enemy = _battle(rng=FixedRandom(0.0))
        enemy.temporary_dodge_chance_modifier = -6
        enemy.equipment_stat_modifiers["block"] = 100
        hp_before = enemy.hp

        event = battle._resolve_card("player", _card("warrior", "warrior_valen_strike"))

        self.assertTrue(event["blocked"])
        self.assertEqual(event["block_count"], 1)
        self.assertEqual(event["damage"], 0)
        self.assertEqual(enemy.hp, hp_before)

    def test_assassin_passive_grants_crit_bonus_from_poison_stacks(self):
        battle, player, _enemy = _battle("assassin", "warrior", rng=FixedRandom(0.10))
        player.temporary_critical_chance_modifier = 0
        battle._resolve_card("player", _card("assassin", "assassin_poison_cascade"))
        event = battle._resolve_card("player", _card("assassin", "assassin_poison_strike"))
        self.assertTrue(event["critical"])

    def test_full_heal_is_taken_back_later(self):
        battle, player, _enemy = _battle()
        player.hp = 10
        battle._resolve_card("player", _card("warrior", "warrior_valentine_transcendence"))
        self.assertEqual(player.hp, player.max_hp)
        for _ in range(3):
            battle._tick_physical_effects()
        self.assertLess(player.hp, player.max_hp)
        self.assertGreaterEqual(player.hp, 1)

    def test_severe_demeanor_reduces_opponents_next_attack(self):
        battle, _player, enemy = _battle(rng=FixedRandom())
        battle._resolve_card("player", _card("warrior", "warrior_severe_demeanor"))
        strike = _card("warrior", "warrior_valen_strike")

        event = battle._resolve_card("enemy", strike)

        self.assertEqual(event["damage"], strike.effect_data["dice"] + enemy.strength - 2)
        self.assertEqual(battle._buff("enemy", "outgoing_damage_flat"), 2)

    def test_grave_frost_heals_for_three_turns(self):
        battle, player, _enemy = _battle()
        player.hp = 10
        battle._resolve_card("player", _card("warrior", "warrior_grave_frost"))

        battle._tick_physical_effects()

        self.assertEqual(player.hp, 10 + 4 + player.stats["endurance"])
        self.assertEqual(len(battle.regenerations["player"]), 1)

    def test_hunter_bonds_heals_after_two_round_ticks(self):
        battle, player, _enemy = _battle()
        player.hp = 20
        battle._resolve_card("player", _card("warrior", "warrior_hunter_bonds"))
        hp_after_cost = player.hp

        battle._tick_physical_effects()
        self.assertEqual(player.hp, hp_after_cost)
        battle._tick_physical_effects()
        delayed_heal = (player.max_hp * 15 + 99) // 100
        self.assertEqual(player.hp, min(player.max_hp, hp_after_cost + delayed_heal))

    def test_severe_demeanor_reduces_enemy_outgoing_damage_by_two(self):
        battle, _player, enemy = _battle(rng=FixedRandom())
        battle._resolve_card("player", _card("warrior", "warrior_severe_demeanor"))
        strike = _card("warrior", "warrior_valen_strike")

        event = battle._resolve_card("enemy", strike)

        self.assertEqual(event["damage"], strike.effect_data["dice"] + enemy.strength - 2)

    def test_scarlet_throne_spends_current_hp_heals_and_buffs(self):
        battle, player, _enemy = _battle()
        player.hp = 40
        expected_hp = 40 - int(40 * 0.4) + (player.max_hp * 10 + 99) // 100

        battle._resolve_card("player", _card("warrior", "warrior_scarlet_throne"))

        self.assertEqual(player.hp, min(player.max_hp, expected_hp))
        self.assertEqual(battle._buff("player", "damage_percent"), 10)
        self.assertEqual(battle._buff("player", "incoming_damage_percent"), 10)

    def test_buried_alive_protects_and_skips_next_own_turn(self):
        battle, _player, _enemy = _battle()
        card = _card("warrior", "warrior_buried_alive")
        battle.hands["player"] = [card]
        battle._resolve_card("player", card)

        self.assertTrue(battle.invulnerable["player"])
        self.assertTrue(battle.skip_next_turn["player"])
        self.assertFalse(battle.can_select("player", card))
        self.assertFalse(battle.can_select("player", _card("warrior", "warrior_valen_strike")))

    def test_team_revive_card_is_not_selectable_in_duel(self):
        battle, _player, _enemy = _battle()
        card = _card("warrior", "warrior_no_losses")
        battle.hands["player"] = [card]

        self.assertFalse(battle.can_select("player", card))

    def test_every_physical_card_resolves(self):
        for profession in ("warrior", "archer", "assassin"):
            for card in cards_for_type(profession):
                with self.subTest(card=card.key):
                    battle, _player, _enemy = _battle(profession, "mage")
                    event = battle._resolve_card("player", card)
                    self.assertTrue(event["effect_text"] or event["damage"] or event["dodged"])

    def test_fire_deals_two_per_stack_once_then_resets_to_one(self):
        battle, _player, enemy = _battle("archer", "warrior")
        battle.mage_mode = True
        enemy.max_hp = 500
        enemy.hp = 500
        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 5, "stacks": 5, "applied_turn": 0}]

        battle._process_status_turn_effects()
        battle._resolve_mage_end_turn_effects()

        self.assertEqual(enemy.hp, 490)
        self.assertEqual([s["stacks"] for s in battle.mage_statuses["enemy"]], [1])

    def test_single_fire_stack_deals_two_and_goes_out(self):
        battle, _player, enemy = _battle("archer", "warrior")
        battle.mage_mode = True
        enemy.max_hp = 500
        enemy.hp = 500
        battle.mage_statuses["enemy"] = [{"name": "огонь", "remaining": 3, "stacks": 1, "applied_turn": 0}]

        battle._process_status_turn_effects()

        self.assertEqual(enemy.hp, 498)
        self.assertEqual(battle.mage_statuses["enemy"], [])

    def test_water_on_holder_lowers_their_dodge_by_fifteen(self):
        battle, player, enemy = _battle("warrior", "warrior")
        enemy.temporary_dodge_chance_modifier = 30
        attack = Card("attack", "Attack", "Боец: Test", "rage", 0, "damage", {"dice": 10})
        base_dodge = get_dodge_chance(player, enemy) + enemy.temporary_dodge_chance_modifier
        roll = (base_dodge - 7) / 100

        battle.rng = FixedRandom(roll)
        self.assertTrue(battle._resolve_card("player", attack)["dodged"])

        battle.rng = FixedRandom(roll)
        battle.mage_statuses["enemy"] = [{"name": "вода", "remaining": 2, "stacks": 0, "applied_turn": 0}]
        self.assertFalse(battle._resolve_card("player", attack)["dodged"])


if __name__ == "__main__":
    unittest.main()
