import random
import unittest

from kaloda.combat.arena_battle import (
    ARENA_SIZE,
    ANCIENT_ENT_DECK,
    ANCIENT_ENT_MAX_HP,
    ANCIENT_ENT_MAX_MP,
    ANCIENT_ENT_NAME,
    BONE_DOG_DECK,
    BONE_DOG_MAX_HP,
    NECROMANCER_DECK,
    NECROMANCER_MAX_HP,
    NECROMANCER_MAX_MP,
    SKELETON_GUARD_DECK,
    SKELETON_GUARD_MAX_HP,
    SKELETON_GUARD_MAX_MP,
    SKELETON_KING_DECK,
    SKELETON_KING_MAX_HP,
    SKELETON_KING_MAX_MP,
    FOREST_SPIRIT_RANGE,
    KOBOLD_DECK,
    KOBOLD_MAX_HP,
    MAX_CARDS_PER_TURN,
    MAX_HAND_SIZE,
    MOVE_RANGE,
    SKELETON_DECK,
    SKELETON_MAX_HP,
    SKELETON_MAX_MP,
    SKULL_EXPLOSION,
    WOLF_DECK,
    WOLF_MAX_HP,
    ArenaBattle,
    CreatureCard,
    arena_center_for_tiles,
    arena_layout,
    card_role,
    create_ally_archer,
    create_ancient_ent,
    create_kobold,
    create_necromancer,
    create_skeleton,
    create_skeleton_guard,
    create_skeleton_king,
    axial_coordinates,
    hex_distance,
    hex_distance_to_center,
    hex_neighbors,
    spread_positions,
)
from kaloda.combat.card_database import Card, cards_for_type, load_cards
from kaloda.combat.fighter import Fighter


def _battle(enemy_deck=KOBOLD_DECK, player_pos=(0, 7), enemy_pos=(ARENA_SIZE - 1, 7), seed=3):
    player = Fighter("Герой", 1, "warrior")
    kobold = create_kobold()
    return ArenaBattle(
        player, kobold, cards_for_type("warrior"), (0, 2, ARENA_SIZE, ARENA_SIZE),
        player_pos, enemy_pos, enemy_deck=enemy_deck, rng=random.Random(seed),
    )


def _necromancer_battle(level=1):
    player = Fighter("Некромант", level, "necromancer")
    return ArenaBattle(
        player,
        create_kobold(),
        cards_for_type("necromancer"),
        (0, 2, ARENA_SIZE, ARENA_SIZE),
        (0, 7),
        (ARENA_SIZE - 1, 7),
        enemy_deck=KOBOLD_DECK,
        rng=random.Random(3),
    )


class ArenaBattleTests(unittest.TestCase):
    def test_attack_can_be_aimed_at_an_empty_hex(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = Card(
            "empty_hex_strike", "Удар", "Боец: атака", "rage", 0,
            "damage", {"dice": "1d1", "range": 3},
        )
        battle.engine.hands["player"] = [card]
        empty_tile = (6, 6)

        self.assertIn(empty_tile, battle.card_aim_tiles(card))
        self.assertEqual(battle.attack_targets_at(card, empty_tile), [])
        self.assertIsNotNone(battle.play_card(card, aim_tile=empty_tile))
        self.assertNotIn(card, battle.engine.hands["player"])

    def test_aoe_attack_uses_selected_hex_even_when_it_is_empty(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(7, 7))
        battle._add_enemy_summon(
            "nearby_skeleton", create_skeleton(), (8, 7), SKELETON_DECK, "skeleton"
        )
        card = Card(
            "empty_hex_blast", "Взрыв", "Магия: огонь", "mana", 0,
            "mage_area_damage", {"damage": 1, "range": 4, "aoe_radius": 1},
        )
        aim_tile = (8, 6)

        self.assertEqual(
            set(battle.attack_targets_at(card, aim_tile)),
            {"enemy", "nearby_skeleton"},
        )

    def test_aoe_hits_enemy_outside_direct_range_when_inside_blast_radius(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(7, 7))
        card = Card(
            "short_range_blast", "Взрыв", "Магия: огонь", "mana", 0,
            "mage_area_damage", {"damage": 1, "range": 1, "aoe_radius": 1},
        )
        battle.engine.hands["player"] = [card]
        aim_tile = (6, 7)
        self.assertEqual(hex_distance(battle.positions["player"], aim_tile), 1)
        self.assertEqual(hex_distance(battle.positions["player"], battle.positions["enemy"]), 2)

        hp_before = battle.enemy.hp
        event = battle.play_card(card, aim_tile=aim_tile)

        self.assertIsNotNone(event)
        self.assertLess(battle.enemy.hp, hp_before)

    def test_stepwise_movement_stops_on_a_roots_trap(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        destination = max(
            battle.reachable_tiles("player"),
            key=lambda tile: (tile[0], tile[1]),
        )
        path = battle.movement_path("player", destination)
        self.assertGreaterEqual(len(path), 2)
        battle.traps.append({
            "tile": path[0], "owner": "enemy", "damage": 0, "root_turns": 2,
        })

        self.assertTrue(battle.move_player(destination))
        self.assertEqual(battle.positions["player"], path[0])
        self.assertEqual(battle.roots["player"], 2)

    def test_ai_walking_triggers_a_trap_on_an_intermediate_hex(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(9, 7))
        destination = (7, 7)
        path = battle.movement_path("enemy", destination)
        self.assertEqual(len(path), 2)
        battle.traps.append({
            "tile": path[0], "owner": "player", "damage": 0, "root_turns": 2,
        })

        self.assertTrue(battle._walk_unit_to("enemy", destination))
        self.assertEqual(battle.positions["enemy"], path[0])
        self.assertEqual(battle.roots["enemy"], 2)

    def test_dash_walks_through_traps_without_using_regular_movement(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = next(card for card in load_cards() if card.key == "universal_dash")
        destination = max(
            battle.card_tiles(card),
            key=lambda tile: hex_distance(battle.positions["player"], tile),
        )
        path = battle.movement_path("player", destination, max_steps=3)
        battle.engine.hands["player"] = [card]
        battle.player.unique_resource_current = 1000
        battle.traps.append({
            "tile": path[0], "owner": "enemy", "damage": 0, "root_turns": 2,
        })

        self.assertIsNotNone(battle.play_card(card, destination))
        self.assertEqual(battle.positions["player"], path[0])
        self.assertFalse(battle.moved)

    def test_teleport_card_jumps_directly_and_only_triggers_landing_trap(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = next(card for card in load_cards() if card.key == "universal_teleport")
        destination = (8, 7)
        path = battle.movement_path("player", destination, max_steps=10)
        self.assertEqual(len(path), 3)
        battle.engine.hands["player"] = [card]
        battle.player.mp = 100
        intermediate_trap = {
            "tile": path[0], "owner": "enemy", "damage": 0, "root_turns": 2,
        }
        landing_trap = {
            "tile": destination, "owner": "enemy", "damage": 0, "root_turns": 2,
        }
        battle.traps.extend((intermediate_trap, landing_trap))

        event = battle.play_card(card, destination)

        self.assertIsNotNone(event)
        self.assertEqual(battle.positions["player"], destination)
        self.assertEqual(battle.roots["player"], 2)
        self.assertIn(intermediate_trap, battle.traps)
        self.assertNotIn(landing_trap, battle.traps)
        self.assertEqual(battle.movement_events, [])
        self.assertEqual(event["resource_spent"], 9)

    def test_unstable_elixir_damage_taken_penalty_expires_after_two_rounds(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        battle.temporary_damage_taken["player"] = [[30, 2]]
        battle._refresh_king_auras()
        self.assertEqual(battle.player.incoming_damage_bonus_percent, 30)

        battle._tick_arena_effects()
        battle._refresh_king_auras()
        self.assertEqual(battle.player.incoming_damage_bonus_percent, 30)
        battle._tick_arena_effects()
        battle._refresh_king_auras()
        self.assertEqual(battle.player.incoming_damage_bonus_percent, 0)

    def test_unstable_elixir_corrosion_deals_exactly_fifteen_over_four_turns(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        initial_hp = battle.player.hp
        battle.arena_corrosion["player"] = [15, 4]

        for _ in range(4):
            battle._tick_arena_effects()

        self.assertEqual(battle.player.hp, initial_hp - 15)
        self.assertNotIn("player", battle.arena_corrosion)

    def test_divine_healing_adds_seven_ticks_of_ten_hp(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = next(card for card in load_cards() if card.key == "universal_divine_healing")
        battle.engine.hands["player"] = [card]
        battle.player.mp = 100

        self.assertIsNotNone(battle.play_card(card, target="player"))
        effect = battle.engine.regenerations["player"][-1]
        self.assertEqual(effect["heal_per_turn"], 10)
        self.assertEqual(effect["remaining"], 7)

    def test_evolution_increases_summon_hp_by_twenty_and_adds_regeneration(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = next(card for card in load_cards() if card.key == "universal_evolution")
        battle.engine.hands["player"] = [card]
        battle.player.unique_resource_current = 1000
        battle.summons["summon_test"] = {
            "kind": "wolf", "name": "Волк", "owner": "player",
            "hp": 20, "max_hp": 20, "damage": 5,
        }
        battle.positions["summon_test"] = (6, 7)
        battle.damage_dealt["summon_test"] = 0

        self.assertIsNotNone(battle.play_card(card, target="summon_test"))
        self.assertEqual(battle.summons["summon_test"]["max_hp"], 40)
        self.assertEqual(battle.summons["summon_test"]["hp"], 40)
        battle.summons["summon_test"]["hp"] = 20
        for _ in range(4):
            battle._tick_summon_regeneration("summon_test")
        self.assertEqual(battle.summons["summon_test"]["hp"], 35)
        self.assertNotIn("regenerations", battle.summons["summon_test"])

    def test_teleport_spends_three_mana_per_hex(self):
        battle = _battle(player_pos=(5, 7), enemy_pos=(12, 7))
        card = next(card for card in load_cards() if card.key == "universal_teleport")
        battle.engine.hands["player"] = [card]
        battle.player.mp = 100
        destination = (10, 7)

        event = battle.play_card(card, destination)

        self.assertEqual(event["resource_spent"], 15)
        self.assertEqual(battle.player.mp, 85)
        self.assertEqual(battle.positions["player"], destination)

    def test_necromancer_arena_battle_starts_with_fifteen_percent_necrotism(self):
        battle = _necromancer_battle()

        self.assertEqual(
            battle.player.unique_resource_current,
            int(battle.player.unique_resource_max * 0.15),
        )
    def test_necromancer_recovers_ten_percent_of_max_necrotism_per_death_once(self):
        player = Fighter("Некромант", 1, "necromancer")
        battle = ArenaBattle(
            player,
            create_kobold(),
            cards_for_type("necromancer"),
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (0, 7),
            (ARENA_SIZE - 1, 7),
            enemy_deck=KOBOLD_DECK,
            rng=random.Random(3),
        )
        player.unique_resource_current = 0

        battle.fighters["enemy"].hp = 0
        battle._check_result()
        battle._check_result()
        battle.summons["fallen_summon"] = {
            "kind": "necromancer_familiar", "name": "Фамильяр",
            "owner": "player", "hp": 0, "max_hp": 8,
        }
        battle._remove_summon("fallen_summon", "погиб")

        self.assertEqual(player.unique_resource_current, 10)

    def test_necromancer_summon_cards_create_creatures_with_specified_hp(self):
        expected_hp = {
            "necromancer_familiar": 8,
            "necromancer_lokrif": 17,
            "necromancer_bone_hero": 45,
            "necromancer_spirit": 10,
            "necromancer_lyrk": 15,
            "necromancer_grave_zink": 30,
            "necromancer_bone_dragon": 80,
        }
        for key, hp in expected_hp.items():
            with self.subTest(card=key):
                battle = _necromancer_battle(level=4)
                battle.player.unique_resource_current = battle.player.unique_resource_max
                card = next(card for card in cards_for_type("necromancer") if card.key == key)
                battle.engine.hands["player"] = [card]
                tile = battle.summon_tiles()[0]

                event = battle.play_card(card, tile)

                self.assertIsNotNone(event)
                summon = battle.summons[event["summon"]]
                expected_summon_hp = hp + battle.player.intellect
                self.assertEqual(summon["hp"], expected_summon_hp)
                self.assertEqual(summon["max_hp"], expected_summon_hp)
                self.assertIsInstance(battle.effects_for(event["summon"]), list)

    def test_necromancer_spirit_can_act_when_player_ends_turn(self):
        battle = _necromancer_battle()
        battle.player.unique_resource_current = battle.player.unique_resource_max
        card = next(card for card in cards_for_type("necromancer") if card.key == "necromancer_spirit")
        battle.engine.hands["player"] = [card]
        event = battle.play_card(card, battle.summon_tiles()[0])
        spirit_id = event["summon"]
        battle.positions[spirit_id] = (6, 7)
        battle.positions["enemy"] = (8, 7)

        self.assertTrue(battle.end_player_turn())
        self.assertIn(spirit_id, battle.summons)

    def test_necromancer_lyrk_applies_poison_when_attacking_during_end_turn(self):
        battle = _necromancer_battle()
        battle.player.unique_resource_current = battle.player.unique_resource_max
        card = next(card for card in cards_for_type("necromancer") if card.key == "necromancer_lyrk")
        battle.engine.hands["player"] = [card]
        event = battle.play_card(card, battle.summon_tiles()[0])
        lyrk_id = event["summon"]
        battle.positions[lyrk_id] = (6, 7)
        battle.positions["enemy"] = (7, 7)
        battle.summons[lyrk_id]["attacks"] = 1
        enemy_hp_before = battle.enemy.hp

        self.assertTrue(battle.end_player_turn())
        self.assertIn("ядовитый укус Лирка", " ".join(battle.log))
        self.assertEqual(battle.enemy.hp, enemy_hp_before - 7)
        poison_events = [
            event
            for entry in battle.engine.history
            for event in entry["events"]
            if event.get("card") == "Яд"
        ]
        self.assertEqual(len(poison_events), 1)

    def test_necromancer_green_flame_ticks_at_start_of_target_turn(self):
        battle = _necromancer_battle()
        battle.positions["enemy"] = (2, 7)
        card = next(
            card for card in cards_for_type("necromancer")
            if card.key == "necromancer_dead_god_curse"
        )
        battle.player.unique_resource_current = battle.player.unique_resource_max
        battle.engine.hands["player"] = [card]
        hp_before = battle.enemy.hp

        battle.play_card(card, "enemy")
        self.assertEqual(battle.enemy.hp, hp_before)
        battle._tick_green_flame("enemy")

        self.assertEqual(battle.enemy.hp, hp_before - 1)

    def test_necromancer_fragility_curse_increases_incoming_damage(self):
        battle = _necromancer_battle()
        battle.positions["enemy"] = (2, 7)
        card = next(
            card for card in cards_for_type("necromancer")
            if card.key == "necromancer_fragility_curse"
        )
        battle.player.unique_resource_current = battle.player.unique_resource_max
        battle.engine.hands["player"] = [card]

        battle.play_card(card, "enemy")
        hp_before = battle.enemy.hp
        battle._apply_environment_damage("enemy", 10, source_side="player")

        self.assertEqual(battle.enemy.hp, hp_before - 13)

    def test_necromancer_slow_trap_triggers_on_enemy_step(self):
        battle = _necromancer_battle()
        card = next(
            card for card in cards_for_type("necromancer")
            if card.key == "necromancer_slow_trap"
        )
        battle.player.unique_resource_current = battle.player.unique_resource_max
        battle.engine.hands["player"] = [card]
        trap_tile = (2, 7)
        event = battle.play_card(card, trap_tile)
        self.assertIsNotNone(event)

        battle.positions["enemy"] = trap_tile
        battle._trigger_trap("enemy", trap_tile)

        self.assertEqual(battle.enemy.hp, KOBOLD_MAX_HP - 15)
        self.assertGreater(battle.slowed_until["enemy"], battle.round)

    def test_recommended_card_ranges_and_requested_cost_changes_are_in_catalog(self):
        cards = {card.key: card for card in load_cards()}
        self.assertEqual(cards["mage_stone_spikes"].resource_cost, 55)
        self.assertEqual(cards["mage_stone_spikes"].effect_data["range"], 4)
        self.assertEqual(cards["warrior_dagger_throw"].effect_data["range"], 3)
        self.assertEqual(cards["warrior_dagger_throw_copy"].effect_data["range"], 3)
        self.assertEqual(cards["warrior_no_losses"].effect_data["range"], 1)
        for key, expected in {
            "mage_water_summon": 5,
            "mage_rising_flow": 4,
            "mage_flow_blessing": 4,
            "mage_water_guard": 4,
            "mage_waterfall": 5,
            "mage_gurgling_flow": 4,
        }.items():
            self.assertEqual(cards[key].effect_data["range"], expected)
        extraction = cards["assassin_poison_extraction"]
        datura = cards["assassin_datura"]
        neurotoxins = cards["assassin_neurotoxins"]
        self.assertEqual(card_role(extraction), "enemy")
        self.assertEqual(card_role(datura), "enemy")
        self.assertEqual(card_role(neurotoxins), "enemy")

    def test_universal_arena_cards_have_the_requested_costs_and_effects(self):
        cards = {card.key: card for card in load_cards()}
        expected = {
            "universal_trap": (10, 2, "arena_trap", 19),
            "universal_barricade": (16, 2, "arena_barrier", None),
            "universal_dash": (5, 3, "arena_dash", None),
            "universal_wolf": (21, 1, "arena_wolf", None),
            "universal_roots_trap": (8, 2, "arena_trap", 8),
            "universal_resource_recovery": (0, 0, "arena_resource_recovery", None),
            "universal_knockback": (16, 1, "arena_knockback", 12),
        }
        for key, (cost, reach, effect, damage) in expected.items():
            card = cards[key]
            with self.subTest(card=key):
                self.assertEqual(card.resource_cost, cost)
                self.assertEqual(card.effect_type, effect)
                self.assertEqual(card.effect_data.get("range", 0), reach)
                if damage is not None:
                    self.assertEqual(card.effect_data["damage"], damage)
        prices = {
            "universal_trap": 300,
            "universal_barricade": 200,
            "universal_dash": 100,
            "universal_wolf": 550,
            "universal_roots_trap": 100,
            "universal_resource_recovery": 320,
            "universal_knockback": 280,
            "universal_bonebreaker": 250,
        }
        for key, price in prices.items():
            card = cards[key]
            self.assertEqual(card.price_coins, price)
        self.assertTrue(cards["universal_trap"].effect_data["cannot_crit"])
        self.assertEqual(cards["universal_roots_trap"].effect_data["root_turns"], 2)
        self.assertEqual(cards["universal_barricade"].effect_data["size"], 3)
        self.assertEqual(cards["universal_resource_recovery"].effect_data["resource_percent"], 15)
        self.assertEqual(cards["universal_knockback"].effect_data["knockback"], 3)
        self.assertEqual(cards["universal_bonebreaker"].resource_cost, 13)
        self.assertEqual(cards["universal_bonebreaker"].effect_data["duration"], 2)
        self.assertEqual(cards["universal_bonebreaker"].rarity, "epic")

    def test_every_universal_card_is_priced_in_coins(self):
        universal = [card for card in load_cards() if card.group_name.startswith("Универсальные:")]

        self.assertGreater(len(universal), 0)
        for card in universal:
            with self.subTest(card=card.key):
                self.assertGreater(card.price_coins, 0)

    def test_bonebreaker_applies_bone_break_and_hits_when_the_target_moves(self):
        cards = {card.key: card for card in load_cards()}
        battle = _battle(player_pos=(4, 7), enemy_pos=(5, 7))
        battle.player.unique_resource_current = 1000
        bonebreaker = cards["universal_bonebreaker"]
        battle.engine.hands["player"] = [bonebreaker]
        self.assertIsNotNone(battle.play_card(bonebreaker, "enemy"))
        enemy_hp = battle.enemy.hp
        battle.positions["enemy"] = (6, 7)
        battle._trigger_trap("enemy", (6, 7))
        self.assertEqual(battle.enemy.hp, enemy_hp - max(1, int(battle.enemy.max_hp * 0.04)))

    def test_skeleton_guard_and_king_stats_and_team_aura(self):
        player = Fighter("Герой", 1, "warrior")
        guard_one, guard_two, king = (
            create_skeleton_guard(),
            create_skeleton_guard(),
            create_skeleton_king(),
        )
        battle = ArenaBattle(
            player,
            [guard_one, guard_two, king],
            cards_for_type("warrior"),
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (4, 7),
            [(6, 7), (7, 8), (8, 7)],
            enemy_deck=SKELETON_GUARD_DECK,
            rng=random.Random(2),
        )
        king_id = battle.enemy_ids[2]
        battle.enemy_decks[king_id] = SKELETON_KING_DECK
        self.assertEqual((guard_one.max_hp, guard_one.max_mp),
                         (SKELETON_GUARD_MAX_HP, SKELETON_GUARD_MAX_MP))
        self.assertEqual((king.max_hp, king.max_mp),
                         (SKELETON_KING_MAX_HP, SKELETON_KING_MAX_MP))
        self.assertEqual(guard_one.incoming_damage_reduction_percent, 30)
        self.assertEqual(guard_one.outgoing_damage_bonus_percent, 10)
        self.assertEqual(king.outgoing_damage_bonus_percent, 10)
        self.assertEqual(SKELETON_KING_DECK[-1].damage, 50)

    def test_king_kneel_prevents_movement_dodging_and_targeting_king(self):
        player = Fighter("Герой", 1, "warrior")
        guard_one, guard_two, king = (
            create_skeleton_guard(),
            create_skeleton_guard(),
            create_skeleton_king(),
        )
        battle = ArenaBattle(
            player,
            [guard_one, guard_two, king],
            cards_for_type("warrior"),
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (6, 7),
            [(7, 7), (7, 8), (8, 7)],
            enemy_deck=SKELETON_GUARD_DECK,
            rng=random.Random(2),
        )
        king_id = battle.enemy_ids[2]
        battle.enemy_decks[king_id] = SKELETON_KING_DECK
        battle.positions["enemy"] = (8, 7)
        battle.positions["enemy_2"] = (8, 8)
        battle.positions[king_id] = (7, 7)
        battle._refresh_king_auras()
        battle._resolve_creature_card(SKELETON_KING_DECK[6], king_id, "player")
        self.assertTrue(battle._is_kneeling("player"))
        self.assertEqual(player.next_damage_taken_bonus_percent, 20)
        self.assertEqual(battle.reachable_tiles("player"), [])
        self.assertFalse(battle._creature_attack_dodged(
            king_id, "player", SKELETON_KING_DECK[0]
        ))
        verdict = next(card for card in load_cards() if card.key == "universal_knockback")
        self.assertNotIn(king_id, battle.card_targets(verdict))

    def test_trap_barrier_dash_and_wolf_resolve_on_arena_tiles(self):
        cards = {card.key: card for card in load_cards()}
        battle = _battle(player_pos=(4, 7), enemy_pos=(5, 7))
        battle.player.unique_resource_current = 1000

        trap = cards["universal_trap"]
        battle.engine.hands["player"] = [trap]
        trap_tile = battle.card_tiles(trap)[0]
        self.assertIsNotNone(battle.play_card(trap, trap_tile))
        self.assertIn(trap_tile, [entry["tile"] for entry in battle.traps])
        enemy_hp = battle.enemy.hp
        battle.positions["enemy"] = trap_tile
        battle._trigger_trap("enemy", trap_tile)
        self.assertEqual(battle.enemy.hp, enemy_hp - 19)
        self.assertFalse(battle.traps)
        roots_trap = cards["universal_roots_trap"]
        battle.engine.hands["player"] = [roots_trap]
        roots_tile = battle.card_tiles(roots_trap)[0]
        self.assertIsNotNone(battle.play_card(roots_trap, roots_tile))
        roots_hp = battle.enemy.hp
        battle.positions["enemy"] = roots_tile
        battle._trigger_trap("enemy", roots_tile)
        self.assertEqual(battle.enemy.hp, max(0, roots_hp - 8))
        self.assertEqual(battle.roots["enemy"], 2)

        barrier_battle = _battle(player_pos=(4, 7), enemy_pos=(5, 7))
        barrier_battle.player.unique_resource_current = 1000
        barrier = cards["universal_barricade"]
        barrier_battle.engine.hands["player"] = [barrier]
        center = barrier_battle.card_tiles(barrier)[0]
        line = barrier_battle._barrier_line(center)
        self.assertEqual(len(line), 3)
        self.assertIsNotNone(barrier_battle.play_card(barrier, center))
        self.assertTrue(all(barrier_battle.barriers[tile] == 8 for tile in line))
        self.assertTrue(barrier_battle._line_blocked(line[0], line[2]))

        dash_battle = _battle(player_pos=(4, 7), enemy_pos=(10, 7))
        dash_battle.player.unique_resource_current = 1000
        dash = cards["universal_dash"]
        dash_battle.engine.hands["player"] = [dash]
        destination = dash_battle.card_tiles(dash)[-1]
        self.assertIsNotNone(dash_battle.play_card(dash, destination))
        self.assertEqual(dash_battle.positions["player"], destination)

        wolf_battle = _battle(player_pos=(4, 7), enemy_pos=(10, 7))
        wolf_battle.player.unique_resource_current = 1000
        wolf = cards["universal_wolf"]
        wolf_battle.engine.hands["player"] = [wolf]
        self.assertIsNotNone(wolf_battle.play_card(wolf, wolf_battle.card_tiles(wolf)[0]))
        self.assertEqual(next(iter(wolf_battle.summons.values()))["max_hp"], WOLF_MAX_HP)

        recovery_battle = _battle(player_pos=(4, 7), enemy_pos=(10, 7))
        recovery = cards["universal_resource_recovery"]
        recovery_battle.player.unique_resource_current = 0
        recovery_battle.engine.hands["player"] = [recovery]
        self.assertIsNotNone(recovery_battle.play_card(recovery))
        self.assertEqual(
            recovery_battle.player.unique_resource_current,
            int(recovery_battle.player.unique_resource_max * 0.15),
        )
        self.assertEqual(recovery_battle.player.next_damage_taken_bonus_percent, 25)

        knockback_battle = _battle(player_pos=(4, 7), enemy_pos=(5, 7))
        knockback_battle.player.unique_resource_current = 1000
        knockback = cards["universal_knockback"]
        knockback_battle.engine.hands["player"] = [knockback]
        original_distance = knockback_battle.distance()
        target_hp = knockback_battle.enemy.hp
        self.assertIsNotNone(knockback_battle.play_card(knockback, "enemy"))
        self.assertEqual(knockback_battle.enemy.hp, target_hp - 12)
        self.assertEqual(knockback_battle.distance(), original_distance + 3)

    def test_necromancer_transfer_uses_selected_destination_and_seven_resource(self):
        battle = _necromancer_battle()
        ally = create_ally_archer()
        battle.fighters["ally"] = ally
        battle.ally_ids.append("ally")
        battle.positions["ally"] = (2, 7)
        battle.damage_dealt["ally"] = 0
        card = next(card for card in load_cards() if card.key == "necromancer_transfer")
        battle.engine.hands["player"] = [card]
        destination = (5, 7)

        self.assertEqual(battle.player.unique_resource_current, 7)
        self.assertIn("ally", battle.card_targets(card))
        self.assertIn(destination, battle.transfer_tiles("ally", card))
        event = battle.play_card(card, "ally", destination=destination)

        self.assertIsNotNone(event)
        self.assertEqual(battle.positions["ally"], destination)
        self.assertEqual(event["destination"], destination)
        self.assertEqual(battle.player.unique_resource_current, 0)

    def test_grave_soil_covers_radius_and_gravestones_reach_arena_edge(self):
        cards = {card.key: card for card in load_cards()}
        soil_battle = _necromancer_battle()
        soil_battle.player.unique_resource_current = 1000
        soil = cards["necromancer_grave_soil"]
        soil_battle.engine.hands["player"] = [soil]
        center = (1, 7)

        self.assertIsNotNone(soil_battle.play_card(soil, center))

        expected = set()
        for y in range(soil_battle.arena_rect[1], soil_battle.arena_rect[1] + soil_battle.arena_rect[3]):
            for x in range(soil_battle.arena_rect[0], soil_battle.arena_rect[0] + soil_battle.arena_rect[2]):
                tile = (x, y)
                if (
                    soil_battle.in_arena(tile)
                    and hex_distance(center, tile) <= soil.effect_data["radius"]
                ):
                    expected.add(tile)
        self.assertEqual(set(soil_battle.grave_soil), expected)

        barrier_battle = _necromancer_battle()
        barrier_battle.player.unique_resource_current = 1000
        barrier_battle.positions["enemy"] = (8, 7)
        barrier = cards["necromancer_gravestones"]
        barrier_battle.engine.hands["player"] = [barrier]
        target = (1, 7)
        line = barrier_battle._grave_barrier_line(target)

        self.assertGreater(len(line), 3)
        self.assertIsNotNone(barrier_battle.play_card(barrier, target))
        self.assertEqual(set(barrier_battle.barriers), set(line))
        self.assertNotIn((8, 7), line)
        self.assertIn((ARENA_SIZE - 1, 7), line)

    def test_necromancer_and_all_its_summons_are_undead_in_grave_soil(self):
        battle = _necromancer_battle()
        player_tile = battle.positions["player"]
        battle.grave_soil[player_tile] = battle.round + 2
        battle.player.hp -= 10
        move_range = battle.movement_budget("player")

        self.assertTrue(battle.is_undead("player"))
        self.assertEqual(battle.movement_budget("player"), move_range)
        battle._tick_grave_soil_fighter("player")
        self.assertEqual(battle.player.hp, battle.player.max_hp - 7)

        summon_tile = next(
            tile for tile in battle.reachable_tiles("player")
            if tile not in battle.positions.values()
        )
        summon_id = "summon_test_undead"
        battle.positions[summon_id] = summon_tile
        battle.summons[summon_id] = {
            "kind": "necromancer_familiar", "owner": "player",
            "hp": 5, "max_hp": 8, "movement": 2,
        }
        battle.grave_soil[summon_tile] = battle.round + 2

        self.assertTrue(battle.is_undead(summon_id))
        self.assertTrue(any(
            hex_distance(summon_tile, tile) == 3
            for tile in battle.reachable_tiles(summon_id, max_steps=3)
        ))
        battle._tick_grave_soil_summon(summon_id)
        self.assertEqual(battle.summons[summon_id]["hp"], 8)

    def test_dash_and_normal_movement_are_independent(self):
        battle = _battle(player_pos=(4, 7), enemy_pos=(12, 7))
        battle.player.unique_resource_current = 1000
        dash = next(card for card in load_cards() if card.key == "universal_dash")
        battle.engine.hands["player"] = [dash]
        ordinary_move = (4, 6)
        self.assertTrue(battle.move_player(ordinary_move))
        destination = battle.card_tiles(dash)[0]

        self.assertIsNotNone(battle.play_card(dash, destination))
        self.assertEqual(battle.positions["player"], destination)
        self.assertTrue(battle.moved)

    def test_knockback_trap_pushes_against_the_victims_movement(self):
        battle = _battle(player_pos=(0, 7), enemy_pos=(5, 7))
        battle.traps.append({
            "tile": (5, 7),
            "owner": "player",
            "damage": 0,
            "knockback": 3,
        })

        battle._trigger_trap("enemy", (5, 7), previous_tile=(4, 7))

        self.assertEqual(battle.positions["enemy"], (2, 7))
        self.assertFalse(battle.traps)

    def test_kobold_deck_matches_design(self):
        cards = {card.name: card for card in KOBOLD_DECK}
        self.assertEqual(len(KOBOLD_DECK), 5)
        self.assertEqual(cards["Удар"].damage, 5)
        self.assertEqual(cards["Сильный удар"].damage, 8)
        self.assertEqual(cards["Ошеломление"].stun_turns, 1)
        self.assertEqual(cards["Острый сук"].damage, 4)
        self.assertEqual(cards["Раскол"].damage, 9)
        self.assertEqual(KOBOLD_MAX_HP, 20)
        self.assertEqual(create_kobold().max_hp, KOBOLD_MAX_HP)
        self.assertEqual(create_kobold().hp, 20)
        self.assertTrue(all(card.range == 1 for card in KOBOLD_DECK))

    def test_static_objects_and_units_block_arena_movement(self):
        battle = _battle()
        battle.blocked_tiles.add((1, 7))
        self.assertNotIn((1, 7), battle.reachable_tiles("player"))

        battle.blocked_tiles.clear()
        blocker = create_ally_archer()
        battle.fighters["ally"] = blocker
        battle.ally_ids.append("ally")
        battle.positions["ally"] = (1, 7)
        self.assertNotIn((1, 7), battle.reachable_tiles("player"))

    def test_enemy_summons_form_an_uncircumventable_front_for_player_movement(self):
        battle = _battle(player_pos=(3, 7), enemy_pos=(8, 7))
        battle._add_enemy_summon(
            "front_skeleton", create_skeleton(), (4, 7), SKELETON_DECK, "skeleton"
        )

        reachable = set(battle.reachable_tiles("player"))

        self.assertNotIn((4, 7), reachable)
        self.assertNotIn((5, 7), reachable)
        self.assertFalse(battle.move_player((5, 7)))
        self.assertIn((3, 6), reachable)
        self.assertIn((3, 8), reachable)
        self.assertIn((2, 7), reachable)

        battle.fighters["front_skeleton"].hp = 0
        self.assertIn((5, 7), battle.reachable_tiles("player"))

    def test_enemy_summon_front_blocks_ranged_cards_and_throwable_items(self):
        battle = _battle(player_pos=(3, 7), enemy_pos=(8, 7))
        battle._add_enemy_summon(
            "front_skeleton", create_skeleton(), (4, 7), SKELETON_DECK, "skeleton"
        )
        ranged_card = Card(
            "barrier_test", "Дальний удар", "Боец: Тест", "rage", 0, "damage",
            {"dice": "1d1", "range": 8},
        )
        battle.engine.hands["player"] = [ranged_card]

        self.assertEqual(battle.card_targets(ranged_card), ["front_skeleton"])
        self.assertFalse(battle.can_play_card(ranged_card, "enemy"))
        self.assertTrue(battle.can_play_card(ranged_card, "front_skeleton"))
        self.assertFalse(battle.can_use_battle_item(6, "enemy")[0])
        self.assertTrue(battle.can_use_battle_item(6, "front_skeleton")[0])

    def test_creature_cards_cannot_hit_from_beyond_one_hex(self):
        battle = _battle(enemy_deck=(CreatureCard("hit", "Удар", damage=5),))
        enemy = battle.positions["enemy"]
        player_hp = battle.player.hp
        battle._resolve_creature_card(battle.enemy_deck[0], "enemy", "player")
        self.assertEqual(battle.player.hp, player_hp)
        self.assertEqual(battle.positions["enemy"], enemy)
        self.assertTrue(any("слишком далеко" in entry for entry in battle.log))

        battle.positions["enemy"] = hex_neighbors(battle.positions["player"])[0]
        battle._resolve_creature_card(battle.enemy_deck[0], "enemy", "player")
        self.assertEqual(battle.player.hp, player_hp - 5)

    def test_creature_attacks_can_be_dodged_and_consume_guaranteed_dodge(self):
        battle = _battle(enemy_deck=(CreatureCard("hit", "Удар", damage=5),),
                         player_pos=(5, 7), enemy_pos=(6, 7))
        battle.player.temporary_dodge_chance_modifier = 100
        battle.rng = type("AlwaysLowRandom", (), {"random": lambda _self: 0.0})()
        hp = battle.player.hp

        battle._resolve_creature_card(battle.enemy_deck[0], "enemy", "player")

        self.assertEqual(battle.player.hp, hp)
        self.assertTrue(any("уклонился" in line for line in battle.log))

        battle.player.temporary_dodge_chance_modifier = -100
        battle.engine.phys_state["player"]["guaranteed_dodges"] = 1
        battle._resolve_creature_card(battle.enemy_deck[0], "enemy", "player")
        self.assertEqual(battle.player.hp, hp)
        self.assertEqual(battle.engine.phys_state["player"]["guaranteed_dodges"], 0)
        battle.engine.phys_state["player"]["guaranteed_dodges"] = 1
        battle._resolve_creature_card(
            CreatureCard("roots", "Корни", root_turns=2),
            "enemy",
            "player",
        )
        self.assertEqual(battle.roots["player"], 0)
        self.assertEqual(battle.engine.phys_state["player"]["guaranteed_dodges"], 0)

    def test_forest_spirit_is_a_summon_with_three_hex_support_abilities(self):
        card = next(card for card in cards_for_type("archer") if card.key == "archer_forest_spirit")
        self.assertEqual(card_role(card), "summon")

        player = Fighter("Герой", profession_type="archer")
        enemy = create_kobold()
        battle = ArenaBattle(
            player, enemy, cards_for_type("archer"), (0, 2, ARENA_SIZE, ARENA_SIZE),
            (0, 7), (10, 7), rng=random.Random(9),
        )
        player.unique_resource_current = player.unique_resource_max
        tile = battle.summon_tiles()[0]
        battle.engine.hands["player"] = [card]
        event = battle.play_card(card, tile)
        sid = event["summon"]
        self.assertEqual(battle.summons[sid]["kind"], "forest_spirit")
        self.assertEqual(battle.summons[sid]["max_hp"], 30)
        self.assertEqual(FOREST_SPIRIT_RANGE, 3)

        battle.positions[sid] = (3, 7)
        player.hp -= 10
        before_heal = player.hp
        battle._summon_act(sid)
        self.assertEqual(player.hp, before_heal + max(1, int(player.max_hp * 0.05)))

        player.hp = player.max_hp
        battle._summon_act(sid)
        self.assertEqual(battle.engine._buff("player", "damage_percent"), 10)
        self.assertAlmostEqual(player.mage_damage_bonus_ratio, 1.10)
        expected_shield = max(1, int(player.hp * 0.08))
        battle._summon_act(sid)
        self.assertEqual(battle.engine.mage_shields["player"], expected_shield)
        self.assertIn(sid, battle._enemy_victims())

    def test_low_health_mob_flees_but_summoned_wolf_does_not(self):
        battle = _battle(
            enemy_deck=(CreatureCard("hit", "Удар", damage=5),),
            player_pos=(5, 7),
            enemy_pos=(6, 7),
        )
        battle.enemy.hp = 4
        initial_distance = battle.distance()
        initial_hp = battle.player.hp
        battle.enemy_turn()
        self.assertGreater(battle.distance(), initial_distance)
        self.assertEqual(battle.player.hp, initial_hp)
        self.assertTrue(any("Кобольд отступает" in line for line in battle.log))

        ent_battle = _battle(enemy_deck=ANCIENT_ENT_DECK, player_pos=(5, 7), enemy_pos=(6, 7))
        ent_battle.fighters["enemy"].hp = 100
        self.assertTrue(ent_battle._spawn_enemy_wolf("enemy"))
        wolf_id = next(iter(ent_battle.enemy_summons))
        ent_battle.fighters[wolf_id].hp = 1
        ent_battle.enemy_decks["enemy"] = (CreatureCard("idle", "Ожидание"),)
        ent_battle.enemy_turn()
        self.assertFalse(any("Волк отступает" in line for line in ent_battle.log))

    def test_ancient_ent_stats_cards_roots_and_area_attack(self):
        ent = create_ancient_ent()
        self.assertEqual((ent.name, ent.hp, ent.max_hp), (ANCIENT_ENT_NAME, 140, ANCIENT_ENT_MAX_HP))
        self.assertEqual((ent.mp, ent.max_mp), (50, ANCIENT_ENT_MAX_MP))
        self.assertEqual(len(ANCIENT_ENT_DECK), 5)
        by_key = {card.key: card for card in ANCIENT_ENT_DECK}
        self.assertEqual((by_key["ent_strike"].damage, by_key["ent_strike"].range), (18, 1))
        self.assertEqual((by_key["ent_aoe"].damage, by_key["ent_aoe"].range,
                          by_key["ent_aoe"].aoe_radius), (12, 1, 2))
        self.assertEqual((by_key["ent_roots"].range, by_key["ent_roots"].root_turns,
                          by_key["ent_roots"].cooldown_turns), (3, 2, 4))
        self.assertTrue(by_key["ent_heal"].heal_percent == 0.10)
        self.assertEqual(by_key["ent_heal"].heal_threshold, 0.25)
        self.assertEqual(by_key["ent_heal"].cooldown_turns, 2)
        self.assertTrue(by_key["ent_wolf"].summon_wolf)

        player = Fighter("Герой", 1, "warrior")
        ally = create_ally_archer()
        battle = ArenaBattle(
            player, ent, [], (0, 2, ARENA_SIZE, ARENA_SIZE), (4, 7), (5, 7),
            enemy_deck=ANCIENT_ENT_DECK, allies=[(ally, (), (5, 8))],
            rng=random.Random(7),
        )
        player.temporary_dodge_chance_modifier = -100
        ally.temporary_dodge_chance_modifier = -100
        self.assertEqual(len(battle.enemy_summons), 1)
        self.assertTrue(any("призывает волка" in line for line in battle.log))
        before = (player.hp, ally.hp)
        battle._resolve_creature_card(by_key["ent_aoe"], "enemy", "player")
        self.assertEqual((player.hp, ally.hp), (before[0] - 12, before[1] - 12))
        battle._resolve_creature_card(by_key["ent_roots"], "enemy", "player")
        self.assertEqual(battle.roots["player"], 2)
        self.assertEqual(battle.reachable_tiles("player"), [])

    def test_ent_heals_below_threshold_on_two_turn_cooldown_and_summons_fast_wolf(self):
        battle = _battle(enemy_deck=ANCIENT_ENT_DECK)
        ent = create_ancient_ent()
        ent.hp = 30
        battle.fighters["enemy"] = ent
        battle.engine.enemy = ent
        battle.enemy_deck = ANCIENT_ENT_DECK
        battle.enemy_decks["enemy"] = ANCIENT_ENT_DECK
        battle.round = 1
        self.assertTrue(battle._enemy_try_heal("enemy"))
        self.assertEqual(ent.hp, 44)
        ent.hp = 30
        battle.round = 2
        self.assertFalse(battle._enemy_try_heal("enemy"))
        battle.round = 3
        self.assertTrue(battle._enemy_try_heal("enemy"))

        battle.positions["enemy"] = (6, 7)
        self.assertTrue(battle._spawn_enemy_wolf("enemy"))
        wolf_id = next(iter(battle.enemy_summons))
        wolf = battle.fighters[wolf_id]
        self.assertEqual((wolf.hp, wolf.max_hp), (WOLF_MAX_HP, WOLF_MAX_HP))
        self.assertEqual(battle.enemy_decks[wolf_id], WOLF_DECK)
        self.assertTrue(all(card.name == "Укус" and card.damage == 5 and card.range == 1
                            for card in WOLF_DECK))
        self.assertTrue(any(hex_distance(battle.positions[wolf_id], tile) == 4
                            for tile in battle.reachable_tiles(wolf_id, max_steps=4)))

    def test_ancient_ent_starts_with_wolf_and_resummons_after_it_dies(self):
        player = Fighter("Герой", 1, "warrior")
        battle = ArenaBattle(
            player,
            create_ancient_ent(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (4, 7),
            (5, 7),
            enemy_deck=ANCIENT_ENT_DECK,
            rng=random.Random(3),
        )
        self.assertEqual(len(battle.enemy_summons), 1)
        wolf_id = next(iter(battle.enemy_summons))

        battle.enemy_decks["enemy"] = (next(card for card in ANCIENT_ENT_DECK if card.summon_wolf),)
        battle.enemy_turn()
        self.assertEqual(len(battle.enemy_summons), 1)
        self.assertEqual(len([uid for uid in battle.enemy_summons if uid in battle.alive_enemies()]), 1)

        battle.fighters[wolf_id].hp = 0

        battle.enemy_turn()

        living_wolves = [uid for uid in battle.enemy_summons if uid in battle.alive_enemies()]
        self.assertEqual(len(living_wolves), 1)
        self.assertNotEqual(living_wolves[0], wolf_id)

    def test_arena_is_centered_near_12x12_and_fighters_start_on_opposite_edges(self):
        rect, player_pos, enemy_pos, center = arena_layout((50, 12), (54, 12), 128, 68)
        left, top, width, height = rect
        self.assertEqual((width, height), (11, 11))
        self.assertEqual(center, arena_center_for_tiles((50, 12), (54, 12)))
        radius = (width - 1) / 2
        tiles = [(x, y) for y in range(top, top + height) for x in range(left, left + width)
                 if hex_distance_to_center((x, y), center) <= radius]
        center_tile = (center[0] + (center[1] - (center[1] & 1)) // 2, center[1])
        self.assertIn(center_tile, tiles)
        boundary_distance = max(hex_distance_to_center(tile, center) for tile in tiles)
        self.assertEqual(hex_distance_to_center(player_pos, center), boundary_distance)
        self.assertEqual(hex_distance_to_center(enemy_pos, center), boundary_distance)
        self.assertNotEqual(player_pos, enemy_pos)
        self.assertTrue(all(left <= tile[0] < left + width and top <= tile[1] < top + height
                            for tile in (player_pos, enemy_pos)))

        edge_rect, edge_player, edge_enemy, edge_center = arena_layout((0, 0), (1, 0), 128, 68)
        self.assertTrue(all(0 <= x < 128 and 0 <= y < 68 for x, y in (edge_player, edge_enemy)))
        self.assertTrue(all(hex_distance_to_center(tile, edge_center) <= radius
                            for tile in (edge_player, edge_enemy)))

    def test_hex_arena_outline_is_symmetric_and_center_does_not_shift_when_it_grows(self):
        source_player, source_enemy = (50, 12), (54, 12)
        expected_center = arena_center_for_tiles(source_player, source_enemy)
        for extras in range(4):
            rect, player_pos, enemy_pos, center = arena_layout(
                source_player, source_enemy, 128, 68, extra_fighters=extras,
                arena_center=expected_center,
            )
            self.assertEqual(center, expected_center)
            left, top, width, height = rect
            radius = (min(width, height) - 1) / 2
            arena_tiles = {
                (x, y) for y in range(top, top + height) for x in range(left, left + width)
                if hex_distance_to_center((x, y), center) <= radius
            }
            self.assertTrue(arena_tiles)
            center_tile = (center[0] + (center[1] - (center[1] & 1)) // 2, center[1])
            self.assertIn(center_tile, arena_tiles)
            for tile in arena_tiles:
                q, r = tile[0] - (tile[1] - (tile[1] & 1)) // 2, tile[1]
                reflected_q, reflected_r = round(2 * center[0] - q), round(2 * center[1] - r)
                reflected = (reflected_q + (reflected_r - (reflected_r & 1)) // 2, reflected_r)
                self.assertIn(reflected, arena_tiles)
            self.assertIn(player_pos, arena_tiles)
            self.assertIn(enemy_pos, arena_tiles)

    def test_move_up_to_three_hexes_once_per_turn(self):
        battle = _battle()
        self.assertEqual(MOVE_RANGE, 3)
        self.assertFalse(battle.can_move_to("player", (4, 7)))
        self.assertFalse(battle.can_move_to("player", (-1, 7)))
        self.assertFalse(battle.can_move_to("player", (3, 10)), "диагональ квадрата не является шагом гекса")
        self.assertTrue(battle.can_move_to("player", (3, 7)))
        self.assertTrue(battle.move_player((3, 7)))
        self.assertEqual(battle.positions["player"], (3, 7))
        self.assertFalse(battle.move_player((4, 7)), "перемещение — одно за ход")

    def test_hex_neighbors_and_ranges_on_both_row_parities(self):
        for center in ((5, 5), (5, 6)):
            with self.subTest(center=center):
                neighbors = hex_neighbors(center)
                self.assertEqual(len(set(neighbors)), 6)
                for tile in neighbors:
                    self.assertEqual(hex_distance(center, tile), 1)
                    self.assertIn(center, hex_neighbors(tile))
                battle = _battle(player_pos=center)
                expected = {
                    (x, y) for y in range(battle.arena_rect[1], battle.arena_rect[1] + battle.arena_rect[3])
                    for x in range(battle.arena_rect[0], battle.arena_rect[0] + battle.arena_rect[2])
                    if 0 < hex_distance(center, (x, y)) <= 3 and battle.in_arena((x, y))
                }
                self.assertEqual(set(battle.reachable_tiles("player")), expected)
                expected_summons = {
                    (x, y) for y in range(battle.arena_rect[1], battle.arena_rect[1] + battle.arena_rect[3])
                    for x in range(battle.arena_rect[0], battle.arena_rect[0] + battle.arena_rect[2])
                    if 0 < hex_distance(center, (x, y)) <= 2 and battle.in_arena((x, y))
                }
                self.assertEqual(set(battle.summon_tiles()), expected_summons)
                self.assertTrue(all(hex_distance(center, tile) <= 2 for tile in battle.summon_tiles()))

    def test_movement_cannot_jump_over_occupied_hexes(self):
        start = (5, 6)
        neighbors = hex_neighbors(start)
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"), [create_kobold() for _ in neighbors],
            [], (0, 0, 17, 17), start, neighbors,
        )
        self.assertEqual(battle.reachable_tiles("player"), [])
        self.assertFalse(battle.move_player((7, 6)))
        battle.fighters["enemy"].hp = 0
        self.assertIn(neighbors[0], battle.reachable_tiles("player"))

    def test_arena_size_grows_per_additional_fighter_and_fits_map_edges(self):
        for extras in (0, 1, 2, 3, 7):
            for origin in ((0, 0), (127, 67)):
                with self.subTest(extras=extras, origin=origin):
                    rect, player, enemy, _ = arena_layout(origin, origin, 128, 68, extra_fighters=extras)
                    left, top, width, height = rect
                    expected_side = ARENA_SIZE + 2 * extras
                    self.assertEqual((width, height), (expected_side, expected_side))
                    self.assertTrue(0 <= left <= 128 - width)
                    self.assertTrue(0 <= top <= 68 - height)
                    self.assertNotEqual(player, enemy)
        with self.assertRaises(ValueError):
            arena_layout((0, 0), (1, 0), 10, 10)

    def test_only_two_cards_per_turn(self):
        battle = _battle()
        battle.player.unique_resource_current = battle.player.unique_resource_max
        played = 0
        for card in list(battle.engine.hands["player"]):
            battle.player.unique_resource_current = battle.player.unique_resource_max
            if battle.play_card(card) is not None:
                played += 1
        self.assertLessEqual(played, MAX_CARDS_PER_TURN)
        self.assertEqual(battle.cards_played, played)
        self.assertFalse(any(battle.can_play_card(card) for card in battle.engine.hands["player"])
                         and battle.cards_played >= MAX_CARDS_PER_TURN)

    def test_kobold_moves_toward_player_and_hits_with_exact_damage(self):
        battle = _battle(
            enemy_deck=(CreatureCard("hit", "Удар", damage=5),
                        CreatureCard("split", "Раскол", damage=9)),
            player_pos=(6, 7),
        )
        hp = battle.player.hp
        battle.end_player_turn()
        self.assertEqual(battle.positions["enemy"], (7, 7))
        damage = hp - battle.player.hp
        self.assertIn(damage, (5, 9), "за ход разыгрывается только одна из двух карт")
        self.assertEqual(battle.damage_dealt["enemy"], damage)
        self.assertEqual(battle.active_side, "player")
        self.assertEqual(battle.round, 2)

    def test_each_kobold_plays_only_one_card_from_full_deck_per_round(self):
        from collections import Counter
        from unittest.mock import patch

        for count in (1, 3):
            with self.subTest(kobolds=count):
                battle = ArenaBattle(
                    Fighter("Герой", 1, "warrior"),
                    [create_kobold() for _ in range(count)],
                    [], (0, 0, 15, 15), (0, 7),
                    [(14, 5 + index * 2) for index in range(count)],
                    rng=random.Random(3),
                )
                with patch.object(battle, "_resolve_creature_card") as resolve:
                    for round_number in (2, 3):
                        resolve.reset_mock()
                        battle.end_player_turn()
                        self.assertEqual(
                            Counter(call.args[1] for call in resolve.call_args_list),
                            Counter({eid: 1 for eid in battle.enemy_ids}),
                        )
                        self.assertEqual(battle.round, round_number)
                        self.assertTrue(battle.player_can_act())

    def test_daze_makes_player_skip_next_turn(self):
        battle = _battle(enemy_deck=(CreatureCard("daze", "Ошеломление", stun_turns=1),))
        battle.positions["enemy"] = hex_neighbors(battle.positions["player"])[0]
        battle.end_player_turn()
        self.assertEqual(battle.round, 2)
        self.assertIn("Оглушение: 1 х.", battle.effects_for("player"))
        self.assertFalse(battle.player_can_act())
        self.assertFalse(battle.move_player((1, 7)))
        battle.end_player_turn()
        # Оглушённый игрок пропустил ход; на следующем ходу кобольда он устойчив к оглушению
        self.assertTrue(any("пропускает ход" in line for line in battle.log))
        self.assertTrue(any("устойчив к оглушению" in line for line in battle.log))
        self.assertEqual(battle.round, 3)
        self.assertTrue(battle.player_can_act())

    def test_player_stun_skips_kobold_turn(self):
        battle = _battle()
        battle.engine._stun("enemy")
        hp = battle.player.hp
        battle.end_player_turn()
        self.assertEqual(battle.player.hp, hp)
        self.assertTrue(any("Кобольд оглушён" in line for line in battle.log))

    def test_teleport_happens_on_next_player_turn(self):
        battle = _battle(enemy_deck=(CreatureCard("hit", "Удар", damage=5),))
        battle.positions["enemy"] = hex_neighbors(battle.positions["player"])[0]
        self.assertTrue(battle.teleport())
        self.assertEqual(battle.result, "teleport")
        self.assertEqual(battle.player.hp, battle.player.max_hp - 5)

    def test_victory_and_defeat(self):
        battle = _battle()
        battle.enemy.take_damage(battle.enemy.hp)
        battle.end_player_turn()
        self.assertEqual(battle.result, "win")

        battle = _battle(enemy_deck=(CreatureCard("split", "Раскол", damage=9),))
        battle.player.hp = 5
        battle.positions["enemy"] = hex_neighbors(battle.positions["player"])[0]
        battle.teleport()
        self.assertEqual(battle.result, "loss", "смерть до телепорта — поражение")

    def test_card_range_hook_limits_play(self):
        battle = _battle()
        card = next(card for card in battle.engine.deck + battle.engine.hands["player"] if card_role(card) == "enemy")
        ranged = card.__class__(**{**card.__dict__, "effect_data": {**card.effect_data, "range": 1}})
        battle.engine.hands["player"].append(ranged)
        battle.player.unique_resource_current = 1000
        self.assertFalse(battle.can_play_card(ranged, target="enemy"))
        self.assertFalse(battle.can_play_card(ranged, aim_tile=(2, 7)))
        self.assertTrue(
            battle.can_play_card(ranged, aim_tile=hex_neighbors(battle.positions["player"])[0])
        )

    def test_hand_is_limited_to_seven_cards_and_overflow_is_burned(self):
        battle = _battle(enemy_deck=(CreatureCard("noop", "Рычание"),))
        self.assertEqual(battle.draw_events[0]["cards"], [card.name for card in battle.engine.hands["player"]])
        for _ in range(2):
            battle.end_player_turn()
            self.assertEqual(len(battle.draw_events[-1]["cards"]), 1)
        self.assertEqual(len(battle.engine.hands["player"]), MAX_HAND_SIZE)
        battle.end_player_turn()
        self.assertEqual(len(battle.engine.hands["player"]), MAX_HAND_SIZE)
        self.assertTrue(battle.draw_events[-1]["hand_full"])
        self.assertEqual(battle.draw_events[-1]["cards"], [])
        self.assertTrue(battle.engine.discard)

    def test_player_arena_draft_picks_two_and_deals_three_random_cards(self):
        player = Fighter("Герой", 1, "warrior")
        battle = ArenaBattle(
            player, create_kobold(), cards_for_type("warrior"),
            (0, 2, ARENA_SIZE, ARENA_SIZE), (0, 7), (10, 7),
            rng=random.Random(4), player_draft=True,
        )
        self.assertTrue(battle.player_draft)
        self.assertEqual(len(battle.engine.table), len(cards_for_type("warrior")))
        self.assertEqual(
            {card.key for card in battle.engine.table},
            {card.key for card in cards_for_type("warrior")},
        )
        self.assertEqual(battle.engine.hands["player"], [])
        for card in list(battle.engine.table[:2]):
            battle.choose_starting_card(card.key)
        self.assertFalse(battle.player_draft)
        self.assertEqual(len(battle.engine.hands["player"]), 5)
        self.assertEqual(battle.round, 1)

    def test_full_arena_hand_burns_selected_draw_and_bottoms_the_other(self):
        battle = _battle()
        cards = load_cards()
        battle.engine.hands["player"] = list(cards[:MAX_HAND_SIZE])
        selected, unselected = cards[MAX_HAND_SIZE:MAX_HAND_SIZE + 2]
        battle.engine.draw_choices["player"] = [selected, unselected]
        battle.engine.deck = [cards[-1]]
        self.assertTrue(battle.choose_draw_card(selected.key))
        self.assertIn(selected, battle.engine.discard)
        self.assertEqual(battle.engine.deck[0], unselected)
        self.assertEqual(len(battle.engine.hands["player"]), MAX_HAND_SIZE)

    def test_camp_battle_against_three_kobolds(self):
        rect, player_pos, enemy_pos, center = arena_layout((58, 18), (62, 18), 128, 68)
        positions = spread_positions(rect, player_pos, enemy_pos, 3, arena_center=center)
        self.assertEqual(len(set(positions)), 3)
        self.assertTrue(all(hex_distance_to_center(pos, center) <= (min(rect[2:]) - 1) / 2
                            for pos in positions))
        kobolds = [create_kobold(name=f"Кобольд {index}") for index in (1, 2, 3)]
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"), kobolds, cards_for_type("warrior"), rect, player_pos, positions,
            enemy_deck=(CreatureCard("hit", "Удар", damage=5),), rng=random.Random(1),
            arena_center=center,
        )
        battle.player.temporary_dodge_chance_modifier = -100
        adjacent = [tile for tile in hex_neighbors(player_pos)
                    if battle.in_arena(tile) and tile != player_pos]
        for eid, tile in zip(battle.enemy_ids, adjacent):
            battle.positions[eid] = tile
        self.assertEqual(battle.enemy_ids, ["enemy", "enemy_2", "enemy_3"])
        hp = battle.player.hp
        battle.end_player_turn()
        self.assertEqual(battle.player.hp, hp - 15, "каждый из трёх кобольдов бьёт по разу")
        self.assertEqual(sum(battle.damage_dealt[eid] for eid in battle.enemy_ids), 15)

        # Оглушение действует только на выбранного кобольда
        battle.select_target("enemy_2")
        battle.engine._stun("enemy")
        self.assertTrue(battle.stunned("enemy_2"))
        self.assertFalse(battle.stunned("enemy"))
        battle.select_target("enemy")
        self.assertTrue(battle.stunned("enemy_2"))
        hp = battle.player.hp
        battle.end_player_turn()
        self.assertEqual(battle.player.hp, hp - 10)
        self.assertFalse(battle.stunned("enemy_2"))

        kobolds[0].take_damage(kobolds[0].hp)
        kobolds[1].take_damage(kobolds[1].hp)
        battle.end_player_turn()
        self.assertIsNone(battle.result)
        self.assertEqual(battle.target, "enemy_3")
        kobolds[2].take_damage(kobolds[2].hp)
        battle.end_player_turn()
        self.assertEqual(battle.result, "win")


def _card(key, profession):
    return next(card for card in cards_for_type(profession) if card.key == key)


def _team_battle(profession="mage", seed=5, enemy_deck=(CreatureCard("noop", "Пусто"),)):
    player = Fighter("Герой", 3, profession)
    player.mp = player.max_mp
    ally = create_ally_archer(3)
    battle = ArenaBattle(
        player, create_kobold(), [], (0, 0, 15, 15), (0, 7), (12, 7),
        enemy_deck=enemy_deck, rng=random.Random(seed), mage_mode=profession == "mage",
        allies=[(ally, cards_for_type("archer"), (0, 9))],
    )
    player.mp = player.max_mp
    return battle, player, ally


class ArenaTargetingTests(unittest.TestCase):
    def test_card_range_uses_hex_neighbors_not_square_diagonals(self):
        battle, _, _ = _team_battle()
        card = _card("mage_paralysis", "mage")
        ranged = card.__class__(**{**card.__dict__, "effect_data": {**card.effect_data, "range": 1}})
        battle.positions["player"] = (5, 6)
        battle.positions["enemy"] = (6, 7)
        self.assertEqual(battle.card_targets(ranged), [])
        battle.positions["enemy"] = (5, 7)
        self.assertEqual(battle.card_targets(ranged), ["enemy"])

    def test_effect_labels_include_values_durations_and_charges(self):
        battle, _, _ = _team_battle()
        engine = battle.engine
        engine._add_buff("player", 3, damage_percent=25)
        engine.mage_damage_bonuses["player"] = [{"percent": -15, "remaining": 2}]
        engine._add_mage_shield("player", 12, 2)
        engine.phys_state["player"]["guaranteed_dodges"] = 2
        labels = battle.effects_for("player")
        self.assertIn("Урон: 25% (3 х.)", labels)
        self.assertIn("Магический урон -15%: 2 х.", labels)
        self.assertIn("Щит +12 HP: 3 х.", labels)
        self.assertIn("Гарантированное уклонение x2", labels)
        colors = dict(battle.effect_entries_for("player"))
        self.assertNotEqual(colors[labels[0]], colors["Магический урон -15%: 2 х."])

    def test_effects_follow_allies_and_inactive_enemy_after_target_switch(self):
        battle, _, _ = _team_battle()
        with battle._as_player("ally"):
            battle.engine._add_buff("player", 2, entangled=True)
        self.assertIn("Оплетение (2 х.)", battle.effects_for("ally"))
        self.assertEqual(battle.effects_for("player"), [])
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"), [create_kobold(), create_kobold()], [],
            (0, 0, 15, 15), (0, 7), [(14, 7), (14, 9)],
        )
        battle.engine.mage_stuns["enemy"] = 2
        battle.select_target("enemy_2")
        self.assertIn("Оглушение: 2 х.", battle.effects_for("enemy"))
        self.assertEqual(battle.effects_for("enemy_2"), [])
        battle.select_target("enemy")
        self.assertIn("Оглушение: 2 х.", battle.effects_for("enemy"))
        battle.engine.mage_stuns["enemy"] = 0
        self.assertEqual(battle.effects_for("enemy"), [])

    def test_card_roles(self):
        self.assertEqual(card_role(_card("mage_golem_summon", "mage")), "summon")
        self.assertEqual(card_role(_card("mage_thundercloud", "mage")), "summon")
        self.assertEqual(card_role(_card("mage_paralysis", "mage")), "enemy")
        self.assertEqual(card_role(_card("mage_flow_blessing", "mage")), "ally")
        self.assertEqual(card_role(_card("archer_healing_moss", "archer")), "ally")

    def test_mage_effects_apply_immediately_and_card_leaves_hand_once(self):
        battle, player, _ = _team_battle()
        battle.positions["enemy"] = (4, 7)
        card = _card("mage_paralysis", "mage")
        battle.engine.hands["player"] = [card]
        self.assertFalse(battle.can_play_card(card, "player"), "дебафф нельзя повесить на себя")
        self.assertTrue(battle.play_card(card, "enemy"))
        self.assertTrue(battle.stunned("enemy"), "отложенный эффект мага применён сразу")
        self.assertNotIn(card, battle.engine.hands["player"])
        self.assertIsNone(battle.play_card(card, "enemy"), "повторный розыгрыш той же карты невозможен")

    def test_heal_goes_to_ally_and_is_paid_by_caster(self):
        battle, player, ally = _team_battle("archer")
        card = _card("archer_healing_moss", "archer")
        battle.engine.hands["player"] = [card]
        player.unique_resource_current = player.unique_resource_max
        ally.unique_resource_current = 0
        ally.hp = ally.max_hp - 20
        self.assertFalse(battle.can_play_card(card, "enemy"), "лечение нельзя применить к врагу")
        player_hp, accuracy = player.hp, player.unique_resource_current
        event = battle.play_card(card, "ally")
        self.assertIsNotNone(event)
        self.assertGreater(ally.hp, ally.max_hp - 20)
        self.assertEqual(player.hp, player_hp)
        self.assertLess(player.unique_resource_current, accuracy)
        self.assertEqual(ally.unique_resource_current, 0)

    def test_golem_is_placed_within_two_tiles_and_fights_in_melee(self):
        battle, player, _ = _team_battle()
        card = _card("mage_golem_summon", "mage")
        battle.engine.hands["player"] = [card]
        self.assertFalse(battle.can_play_card(card, (3, 7)), "дальше 2 тайлов призывать нельзя")
        self.assertFalse(battle.can_play_card(card, (0, 9)), "клетка занята союзником")
        self.assertTrue(battle.play_card(card, (2, 7)))
        (sid, golem), = battle.summons.items()
        self.assertEqual(golem["kind"], "golem")
        self.assertEqual(battle.positions[sid], (2, 7))
        self.assertTrue(battle.occupied((2, 7)))
        self.assertFalse(battle.engine.mage_golems["player"], "голем не уходит в невидимый эффект движка")

        battle.end_player_turn()
        self.assertEqual(battle.positions[sid], (5, 7), "голем идёт к ближайшему врагу на 3 гекса")
        kobold = battle.fighters["enemy"]
        battle.positions["enemy"] = (6, 7)
        hp = kobold.hp
        battle.end_player_turn()
        self.assertEqual(battle.dist(sid, "enemy"), 1)
        self.assertEqual(kobold.hp, hp - golem["damage"])

    def test_cloud_strikes_and_dissipates(self):
        battle, player, _ = _team_battle()
        card = _card("mage_thundercloud", "mage")
        battle.engine.hands["player"] = [card]
        self.assertTrue(battle.play_card(card, (1, 6)))
        (sid, cloud), = battle.summons.items()
        battle.positions["enemy"] = (3, 6)
        hp = battle.fighters["enemy"].hp
        turns = cloud["remaining"]
        battle.end_player_turn()
        self.assertLess(battle.fighters["enemy"].hp, hp)
        self.assertIn("электро", [status["name"] for status in battle.engine.mage_statuses["enemy"]])
        for _ in range(turns):
            battle.end_player_turn()
        self.assertNotIn(sid, battle.summons)

    def test_enemies_attack_nearest_team_member_and_ally_death_is_not_loss(self):
        battle, player, ally = _team_battle(enemy_deck=(CreatureCard("hit", "Удар", damage=5),))
        battle.positions["enemy"] = (1, 10)
        player_hp = player.hp
        ally.hp = 5
        battle.active_side = "enemy"
        battle.enemy_turn()
        self.assertTrue(ally.is_dead())
        self.assertEqual(player.hp, player_hp)
        self.assertIsNone(battle.result)
        self.assertNotIn("ally", battle.alive_allies())

    def test_living_wolf_blocks_the_arena_front_and_death_opens_the_passage(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_ancient_ent(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (4, 7),
            (5, 7),
            enemy_deck=ANCIENT_ENT_DECK,
            rng=random.Random(11),
        )
        wolf_id = next(iter(battle.enemy_summons))
        direction = battle.wolf_barrier["direction"]
        wolf_q, wolf_r = axial_coordinates(battle.positions[wolf_id])
        blocked = [
            (x, y)
            for y in range(2, 2 + ARENA_SIZE)
            for x in range(ARENA_SIZE)
            if battle.in_arena((x, y))
            and (x, y) != battle.positions["player"]
            and not battle.occupied((x, y))
            and (
                (axial_coordinates((x, y))[0] - wolf_q) * direction[0]
                + (axial_coordinates((x, y))[1] - wolf_r) * direction[1]
            ) > 0
            and hex_distance((x, y), battle.positions["player"]) <= MOVE_RANGE
        ]
        self.assertTrue(blocked)
        reachable = set(battle.reachable_tiles("player"))
        self.assertTrue(set(blocked).isdisjoint(reachable))

        battle.fighters[wolf_id].hp = 0
        self.assertIn(blocked[0], battle.reachable_tiles("player"))
        self.assertIsNone(battle.wolf_barrier)

    def test_skeleton_teleports_stuns_and_marks_next_damage(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_skeleton(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (5, 7),
            (7, 7),
            enemy_deck=SKELETON_DECK,
            rng=random.Random(13),
        )
        _, teleport, mark, _ = SKELETON_DECK
        self.assertEqual((battle.enemy.hp, battle.enemy.max_hp), (SKELETON_MAX_HP, SKELETON_MAX_HP))
        self.assertEqual(battle.enemy.mp, SKELETON_MAX_MP)
        self.assertEqual(battle.enemy.temporary_dodge_chance_modifier, 20)

        battle._resolve_creature_card(teleport, "enemy", "player")
        self.assertEqual(battle.dist("enemy", "player"), 1)
        self.assertEqual(battle.engine.mage_stuns["player"], 1)
        self.assertEqual(battle.enemy_card_last_used["enemy"][teleport.key], battle.round)

        battle.engine.mage_stuns["player"] = 0
        battle._resolve_creature_card(mark, "enemy", "player")
        self.assertEqual(battle.player.next_damage_taken_bonus_percent, 50)
        before = battle.player.hp
        battle.engine._mage_take_damage("player", 10, source_side="enemy")
        self.assertEqual(battle.player.hp, before - 15)
        self.assertEqual(battle.player.next_damage_taken_bonus_percent, 0)

    def test_necromancer_summons_nearby_skull_and_skeleton(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_necromancer(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (3, 7),
            (8, 7),
            enemy_deck=NECROMANCER_DECK,
            rng=random.Random(17),
        )
        self.assertEqual((battle.enemy.hp, battle.enemy.max_hp), (NECROMANCER_MAX_HP, NECROMANCER_MAX_HP))
        self.assertEqual((battle.enemy.mp, battle.enemy.max_mp), (55, NECROMANCER_MAX_MP))

        for card, kind, expected_hp in (
            (NECROMANCER_DECK[0], "skull", 10),
            (NECROMANCER_DECK[1], "skeleton", SKELETON_MAX_HP),
        ):
            battle._resolve_creature_card(card, "enemy", "enemy")
            summon_id = next(
                uid for uid in battle.enemy_summons
                if battle.enemy_summon_kinds[uid] == kind
            )
            self.assertEqual(battle.fighters[summon_id].max_hp, expected_hp)
            self.assertLessEqual(hex_distance(battle.positions[summon_id], battle.positions["enemy"]), 1)

    def test_necromancer_summon_cards_have_independent_four_round_cooldowns(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_necromancer(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (3, 7),
            (8, 7),
            enemy_deck=NECROMANCER_DECK,
            rng=random.Random(20),
        )
        summon_cards = NECROMANCER_DECK[:3]
        self.assertEqual([card.cooldown_turns for card in summon_cards], [4, 4, 4])

        battle._resolve_creature_card(summon_cards[0], "enemy", "enemy")
        last_used = battle.enemy_card_last_used["enemy"]
        self.assertEqual(last_used, {summon_cards[0].key: battle.round})
        self.assertNotIn(summon_cards[1].key, last_used)
        self.assertNotIn(summon_cards[2].key, last_used)

        battle.round += 3
        self.assertLess(battle.round - last_used[summon_cards[0].key], 4)
        self.assertGreaterEqual(
            battle.round - last_used.get(summon_cards[1].key, -10**6), 4
        )
        battle.round += 1
        self.assertGreaterEqual(battle.round - last_used[summon_cards[0].key], 4)

    def test_necromancer_moves_to_and_holds_three_to_four_hex_range(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_necromancer(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (3, 7),
            (8, 7),
            enemy_deck=NECROMANCER_DECK,
            rng=random.Random(18),
        )

        battle._enemy_move("enemy")
        self.assertIn(battle.dist("enemy", "player"), (3, 4))

        battle.positions["enemy"] = (4, 7)
        battle._enemy_move("enemy")
        self.assertIn(battle.dist("enemy", "player"), (3, 4))

    def test_skull_explosion_and_bone_dog_sacrifice_heal(self):
        battle = ArenaBattle(
            Fighter("Герой", 1, "warrior"),
            create_necromancer(),
            [],
            (0, 2, ARENA_SIZE, ARENA_SIZE),
            (3, 7),
            (8, 7),
            enemy_deck=NECROMANCER_DECK,
            rng=random.Random(19),
        )
        battle.player.temporary_dodge_chance_modifier = -100
        battle._spawn_enemy_minion("enemy", "skull")
        skull_id = next(uid for uid in battle.enemy_summons
                        if battle.enemy_summon_kinds[uid] == "skull")
        before = battle.player.hp
        battle._skull_turn(skull_id)
        self.assertEqual(battle.player.hp, before - SKULL_EXPLOSION.damage)
        self.assertTrue(battle.fighters[skull_id].is_dead())

        skeleton_id = battle._spawn_enemy_minion("enemy", "skeleton")
        dog_id = battle._spawn_enemy_minion("enemy", "bone_dog")
        skeleton = battle.fighters[skeleton_id]
        dog = battle.fighters[dog_id]
        self.assertEqual((dog.hp, dog.max_hp, dog.max_mp), (BONE_DOG_MAX_HP, BONE_DOG_MAX_HP, 10))
        skeleton.hp = 10
        dog.hp = 3
        battle._resolve_creature_card(BONE_DOG_DECK[1], dog_id, dog_id)
        self.assertEqual(skeleton.hp, 10 + int(BONE_DOG_MAX_HP * 0.5))
        self.assertTrue(dog.is_dead())

    def test_ally_archer_acts_on_its_own(self):
        battle, player, ally = _team_battle("warrior", enemy_deck=(CreatureCard("noop", "Пусто"),))
        battle.positions["enemy"] = (3, 9)
        ally.unique_resource_current = ally.unique_resource_max
        hand = len(battle.ally_cards["ally"]["hand"])
        self.assertEqual(hand, 5)
        battle.end_player_turn()
        played = len(battle.ally_cards["ally"]["discard"])
        self.assertGreater(played, 0, "союзник разыгрывает карты сам")
        self.assertLessEqual(played, MAX_CARDS_PER_TURN)


if __name__ == "__main__":
    unittest.main()
