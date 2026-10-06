import random
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from core import settings
from combat.card_battle import CardBattle, build_battle_deck
from combat.card_database import Card, choose_battle_reward, load_cards
from combat.fighter import Fighter
from combat.character_stats import calculate_max_hp
from combat.mechanics import get_critical_chance, get_dodge_chance
from ui.character_card import CharacterCard
from ui.character_profile import derived_values
from ui.renderers.card_area import CardAreaRenderer
from scenes.duel_scene import DuelScene
from scenes.duel_input import DuelInputHandler


def _reward_card(key, drop_chance):
    return Card(
        key=key,
        name=key,
        group_name="Боец: Тест",
        resource_type="rage",
        resource_cost=0,
        effect_type="damage",
        effect_data={"dice": "1d1"},
        drop_chance=drop_chance,
    )


class TestCardBattle(unittest.TestCase):
    def test_battle_deck_contains_all_available_cards_without_level_limits(self):
        cards = load_cards()

        deck = build_battle_deck(cards, player_level=1, enemy_level=1, rng=random.Random(2))

        self.assertCountEqual(deck, cards)
        self.assertEqual(len(deck), len(cards))

    def test_mage_duel_battle_excludes_warrior_cards(self):
        pygame.init()
        try:
            scene = DuelScene()
            mage_profile = {
                "id": 1,
                "name": "TestMage",
                "level": 1,
                "xp": 0,
                "type": "mage",
                "stats": {"wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 4},
                "stat_points": 0,
                "hp": 90,
                "mp": 55,
            }
            scene.online_session = SimpleNamespace(character=mage_profile, selected_deck=None)
            scene.restart()
            self.assertTrue(scene.battle.cards)
            self.assertTrue(all(card.group_name.startswith("Магия:") for card in scene.battle.cards))
        finally:
            pygame.quit()

    def test_draft_cards_keep_fixed_slots_in_two_rows(self):
        pygame.init()
        try:
            scene = DuelScene()
            renderer = scene.renderer.card_renderer
            scene.battle.table = list(scene.battle.cards[:10])
            slots = list(renderer.draft_slots())
            rects = [renderer.draft_slot_rect(index) for index in range(10)]
            self.assertTrue(all(rect.size == (renderer.CARD_WIDTH, renderer.CARD_HEIGHT) for rect in rects))
            self.assertEqual(len({rect.y for rect in rects[:5]}), 1)
            self.assertGreater(rects[5].y, rects[0].y)
            self.assertTrue(all(scene.layout.card_table.contains(rect) for rect in rects))

            taken = slots[2]
            scene.battle.table.remove(taken)
            after = renderer.draft_slots()
            self.assertIsNone(after[2])
            self.assertEqual(after[3], slots[3])
        finally:
            pygame.quit()

    def test_turn_timer_is_one_minute(self):
        self.assertEqual(settings.TURN_DECISION_SECONDS, 60)

    def test_duel_screen_draws_in_every_card_phase(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            for profession in ("warrior", "archer", "assassin", "battle_mage"):
                scene = DuelScene()
                scene.player.set_profession(profession)
                scene.battle.table = list(scene.battle.cards[:10])
                scene.draft_reveal_started = time.monotonic()
                scene.draft_cleanup_started = time.monotonic()
                scene.turn_deadline = time.monotonic() + 30
                for phase in ("draft_reveal", "draft", "draft_cleanup", "planning", "waiting_enemy", "damage"):
                    with self.subTest(profession=profession, phase=phase):
                        scene.phase = phase
                        scene.renderer.draw(screen)
        finally:
            pygame.quit()

    def test_strength_adds_one_damage_to_card_roll(self):
        self.assertEqual(calculate_max_hp(1, 5), 50)

    def test_agility_debuff_changes_all_agility_derivatives(self):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        attacker.stats["agility"] = 0
        defender.stats["agility"] = 8

        dodge_before = get_dodge_chance(attacker, defender)
        defender.adjust_temporary_stat("agility", -4)
        dodge_after = get_dodge_chance(attacker, defender)

        self.assertEqual(dodge_before - dodge_after, 8)

        attacker.stats["agility"] = 8
        defender.stats["agility"] = 8
        attacker.temporary_stat_modifiers["agility"] = 0
        defender.temporary_stat_modifiers["agility"] = 0
        anti_dodge_before = get_dodge_chance(attacker, defender)
        attacker.adjust_temporary_stat("agility", -4)
        anti_dodge_after = get_dodge_chance(attacker, defender)

        # Ловкость атакующего больше не влияет на уворот защитника.
        self.assertEqual(anti_dodge_after - anti_dodge_before, 0)

        battle = CardBattle(attacker, defender, cards=[], rng=random.Random(1))
        self.assertEqual(battle._stronger_side("agility"), "enemy")

    def test_intuition_debuff_changes_critical_chance_and_priority(self):
        attacker = Fighter("Атакующий")
        defender = Fighter("Защитник")
        attacker.stats["intuition"] = 8
        defender.stats["intuition"] = 6
        battle = CardBattle(attacker, defender, cards=[], rng=random.Random(1))

        critical_before = get_critical_chance(attacker, defender)
        self.assertEqual(battle._stronger_side("intuition"), "player")

        attacker.adjust_temporary_stat("intuition", -4)

        # Интуиция теперь влияет только на урон крита, а не на его шанс — шанс не меняется.
        self.assertEqual(critical_before - get_critical_chance(attacker, defender), 0)
        self.assertEqual(battle._stronger_side("intuition"), "enemy")

    def test_duel_scene_starts_with_full_card_pool(self):
        pygame.init()
        try:
            scene = DuelScene()
            self.assertEqual(settings.GAINED_POINTS_FONT_SIZE, 20)
            self.assertGreaterEqual(scene.gained_points_font.get_height(), 20)
            self.assertTrue(scene.gained_points_font.get_bold())
            self.assertEqual(scene.battle.hands["player"], [])
            self.assertEqual(scene.battle.hands["enemy"], [])
            self.assertEqual(len(scene.battle.table), 10)
        finally:
            pygame.quit()

    def test_active_effect_statuses_show_value_and_duration(self):
        pygame.init()
        try:
            scene = DuelScene()
            battle = scene.battle
            battle._add_buff("player", 1, dodge_percent=-12)
            battle._add_buff("player", 2, crit_chance=12)
            battle._add_buff("player", 3, damage_percent=23)
            battle.bleeds["player"] = [{"damage": 3, "remaining": 2, "source": "enemy"}]
            battle.poisons["player"] = [{"damage": 2, "remaining": 2, "source": "enemy"}] * 2

            statuses = scene.renderer._active_effect_statuses("player")

            self.assertEqual(statuses["Уворот"][0][0], "-12% на 1 ход")
            self.assertEqual(statuses["Крит"][0][0], "+12% на 2 хода")
            self.assertEqual(statuses["Урон"][0][0], "+23% на 3 хода")
            self.assertEqual([text for text, _ in statuses["HP"]], ["Кровотечение -3/ход", "Яд x2"])

            scene.player.stats["agility"] = 4
            scene.player.temporary_stat_modifiers["agility"] = -4
            scene.player.stats["strength"] = 4
            scene.player.temporary_stat_modifiers["strength"] = -4
            scene.player.stats["intuition"] = 4
            scene.player.temporary_stat_modifiers["intuition"] = -4
            scene.enemy.stats["agility"] = 4
            scene.enemy.stats["endurance"] = 0
            player_profile = scene.renderer._effective_profile_for_derived(
                scene.player,
                {"stats": dict(scene.player.stats), "max_hp": scene.player.max_hp},
            )
            enemy_profile = scene.renderer._effective_profile_for_derived(
                scene.enemy,
                {"stats": dict(scene.enemy.stats), "max_hp": scene.enemy.max_hp},
            )
            self.assertEqual(
                derived_values(player_profile)["Уворот"],
                "0%",
            )
            self.assertEqual(
                derived_values(player_profile)["Урон"],
                1,
            )
            # Базовый шанс крита фиксирован и больше не падает вслед за интуицией.
            self.assertTrue(
                derived_values(player_profile)["Крит"].startswith("5% × "),
            )
            scene.player.temporary_dodge_chance_modifier = -100
            scene.player.temporary_critical_chance_modifier = -100
            adjusted = scene.renderer._apply_chance_modifiers(
                {"Уворот": "8%", "Крит": "5% × 170%"},
                scene.player,
            )
            self.assertEqual(adjusted["Уворот"], "0%")
            self.assertEqual(adjusted["Крит"], "0% × 170%")
        finally:
            pygame.quit()

    def test_stats_frames_leave_six_pixels_to_six_card_hand(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.hands["player"] = list(cards[:6])
            scene.battle.hands["enemy"] = list(cards[6:12])

            player_x, player_width = scene.renderer._stats_frame_geometry(
                "player",
                settings.WIDTH,
            )
            enemy_x, enemy_width = scene.renderer._stats_frame_geometry(
                "enemy",
                settings.WIDTH,
            )
            player_first = scene.renderer.card_renderer.card_rect(
                scene.layout.player_hand,
                6,
                0,
            )
            enemy_last = scene.renderer.card_renderer.card_rect(
                scene.layout.enemy_hand,
                6,
                5,
            )

            self.assertEqual(player_first.left - (player_x + player_width), 6)
            self.assertEqual(enemy_x - enemy_last.right, 6)
            self.assertGreater(player_width, 310)
            self.assertGreater(enemy_width, 310)
        finally:
            pygame.quit()

    def test_stats_frames_stay_expanded_with_fewer_cards(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.hands["player"] = list(cards[:3])
            scene.battle.hands["enemy"] = list(cards[3:6])

            player_geometry = scene.renderer._stats_frame_geometry(
                "player",
                settings.WIDTH,
            )
            enemy_geometry = scene.renderer._stats_frame_geometry(
                "enemy",
                settings.WIDTH,
            )

            self.assertEqual(player_geometry, (10, 444))
            self.assertEqual(enemy_geometry, (1466, 444))
        finally:
            pygame.quit()

    def test_card_damage_includes_strength_but_description_does_not(self):
        class FixedRandom:
            @staticmethod
            def random():
                return 0.99

            @staticmethod
            def randint(start, _end):
                return start

            @staticmethod
            def shuffle(_items):
                return None

        card = Card(
            key="test_strike",
            name="Тестовый удар",
            group_name="Боец: Тест",
            resource_type="rage",
            resource_cost=0,
            effect_type="damage",
            effect_data={"dice": "1d4"},
        )
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["strength"] = 20
        enemy.stats["endurance"] = 0
        battle = CardBattle(player, enemy, cards=[], rng=FixedRandom())

        event = battle._resolve_card("player", card)

        self.assertEqual(event["damage"], 21)
        self.assertTrue(CardAreaRenderer._card_description(card).startswith("Урон 1d4 + Сила."))

    def test_empty_battle_keeps_state_consistent(self):
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[], rng=random.Random(4))

        self.assertEqual(battle.deck, [])
        self.assertEqual(battle.table, [])
        self.assertEqual(battle.hands["player"], [])
        self.assertEqual(battle.hands["enemy"], [])
        self.assertEqual(battle.resolve_turn(), [])

    def test_empty_battle_can_start_next_turn_without_cards(self):
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[], rng=random.Random(4))

        battle.start_next_turn()
        self.assertEqual(battle.turn, 1)
        self.assertEqual(battle.hands["player"], [])
        self.assertEqual(battle.hands["enemy"], [])

    def test_discard_stays_out_of_deck_until_deck_is_empty(self):
        cards = load_cards()
        deck_card = cards[0]
        discarded_card = cards[1]
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[])
        battle.draft_mode = None
        battle.deck = [deck_card]
        battle.discard = [discarded_card]

        battle.start_next_turn()

        self.assertIn(deck_card, battle.hands["player"])
        self.assertNotIn(discarded_card, battle.hands["player"])
        self.assertEqual(battle.discard, [discarded_card])
        self.assertEqual(battle.deck, [])

    def test_six_card_hand_skips_draw_without_removing_card_from_deck(self):
        cards = load_cards()
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[])
        battle.draft_mode = None
        battle.hands["player"] = list(cards[:battle.MAX_HAND_SIZE])
        battle.hands["enemy"] = list(cards[6:12])
        battle.deck = list(cards[12:15])

        battle.start_next_turn()

        self.assertEqual(len(battle.hands["player"]), battle.MAX_HAND_SIZE)
        self.assertEqual(len(battle.hands["enemy"]), battle.MAX_HAND_SIZE)
        self.assertEqual(len(battle.deck), 3)

    def test_redraft_never_exceeds_six_cards_in_hand(self):
        cards = load_cards()
        card_pool = cards + [
            replace(card, key=f"{card.key}_copy")
            for card in cards[:5]
        ]
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["intuition"] = 8
        enemy.stats["intuition"] = 4
        player.stats["agility"] = 8
        enemy.stats["agility"] = 4
        battle = CardBattle(player, enemy, cards=[])
        battle.draft_mode = None
        battle.hands["player"] = list(card_pool[:6])
        battle.hands["enemy"] = list(card_pool[6:11])
        battle.discard = list(card_pool[11:18])

        self.assertTrue(battle.prepare_redraft())
        battle.finish_afk_redraft()

        self.assertEqual(len(battle.hands["player"]), 6)
        self.assertEqual(len(battle.hands["enemy"]), 6)
        self.assertLessEqual(
            max(len(hand) for hand in battle.hands.values()),
            battle.MAX_HAND_SIZE,
        )

    def test_redraft_keeps_hands_and_distributes_two_cards_each(self):
        cards = load_cards()
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["intuition"] = 8
        enemy.stats["intuition"] = 4
        player.stats["agility"] = 4
        enemy.stats["agility"] = 8
        battle = CardBattle(player, enemy, cards=[])
        battle.draft_mode = None
        kept_player_card = cards[8]
        kept_enemy_card = cards[9]
        battle.hands = {
            "player": [kept_player_card],
            "enemy": [kept_enemy_card],
        }
        battle.discard = list(cards[:8])

        self.assertTrue(battle.prepare_redraft())
        self.assertEqual(battle.draft_first_side(), "player")
        self.assertEqual(battle.hands["player"], [kept_player_card])
        self.assertEqual(battle.hands["enemy"], [kept_enemy_card])
        self.assertEqual(len(battle.table), 6)

        side = battle.draft_first_side()
        while not battle.current_draft_complete():
            battle.choose_redraft_card(side, battle.table[0].key)
            side = "enemy" if side == "player" else "player"
        # Бонусная карта за более высокую характеристику убрана — обе стороны
        # получают ровно то, что выбрали в повторном драфте.
        self.assertIsNone(battle.take_draft_bonus_card())
        battle.finish_redraft()

        self.assertIn(kept_player_card, battle.hands["player"])
        self.assertIn(kept_enemy_card, battle.hands["enemy"])
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)
        self.assertEqual(len(battle.deck), 4)
        self.assertEqual(battle.discard, [])

        battle.start_next_turn()

        self.assertEqual(len(battle.hands["player"]), 4)
        self.assertEqual(len(battle.hands["enemy"]), 4)
        self.assertEqual(len(battle.deck), 2)

    def test_redraft_starts_only_after_deck_is_empty(self):
        cards = load_cards()
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["intuition"] = 8
        enemy.stats["intuition"] = 4
        player.stats["agility"] = 8
        enemy.stats["agility"] = 4
        battle = CardBattle(player, enemy, cards=[])
        battle.draft_mode = None
        battle.deck = list(cards[:2])
        battle.discard = list(cards[2:7])

        self.assertFalse(battle.prepare_redraft())
        battle.discard.extend(battle.deck)
        battle.deck.clear()

        self.assertTrue(battle.prepare_redraft())
        self.assertEqual(len(battle.table), 6)

        side = battle.draft_first_side()
        while not battle.current_draft_complete():
            battle.choose_redraft_card(side, battle.table[0].key)
            side = "enemy" if side == "player" else "player"
        self.assertIsNone(battle.take_draft_bonus_card())
        battle.finish_redraft()

        self.assertEqual(len(battle.deck), 3)
        battle.start_next_turn()
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)
        self.assertEqual(len(battle.deck), 1)

    def test_duel_scene_waits_until_next_turn_after_last_draw(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.deck = [cards[0]]
            scene.battle.discard = list(cards[1:7])
            scene.battle.table = []
            scene.battle.draft_mode = None
            scene.battle.hands = {"player": [], "enemy": []}
            scene.phase = "card_draw"
            scene.draw_queue = []
            scene.draw_transfer = {
                "side": "player",
                "card": cards[0],
                "started": time.monotonic() - settings.CARD_MOVE_SECONDS,
            }

            with patch("scenes.duel_scene.play_draft_music"):
                scene.update(0)

            self.assertEqual(scene.battle.deck, [])
            self.assertEqual(len(scene.battle.discard), 6)
            self.assertEqual(scene.battle.draft_mode, None)
            self.assertEqual(scene.phase, "planning")
        finally:
            pygame.quit()

    def test_headless_next_turn_completes_redraft_automatically(self):
        cards = load_cards()
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["intuition"] = 8
        enemy.stats["intuition"] = 4
        player.stats["agility"] = 8
        enemy.stats["agility"] = 4
        battle = CardBattle(player, enemy, cards=[])
        battle.draft_mode = None
        battle.hands = {"player": [cards[8]], "enemy": [cards[9]]}
        battle.discard = list(cards[:8])

        battle.start_next_turn()

        self.assertEqual(battle.turn, 1)
        self.assertEqual(battle.draft_mode, None)
        self.assertEqual(battle.table, [])
        self.assertEqual(battle.discard, [])
        self.assertEqual(len(battle.deck), 4)
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)

    def test_headless_redraft_starts_on_turn_after_last_draw(self):
        cards = load_cards()
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[])
        battle.draft_mode = None
        battle.deck = [cards[0]]
        battle.discard = list(cards[1:7])

        battle.start_next_turn()

        self.assertEqual(len(battle.discard), 6)
        self.assertEqual(len(battle.hands["player"]), 1)
        self.assertEqual(len(battle.hands["enemy"]), 0)

        battle.start_next_turn()

        self.assertEqual(battle.draft_mode, None)
        self.assertEqual(battle.discard, [])
        self.assertEqual(battle.table, [])
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 2)

    def test_starting_deal_gives_no_bonus_card_for_higher_stats(self):
        class LastChoiceRandom(random.Random):
            @staticmethod
            def randrange(stop):
                return stop - 1

        cards = load_cards()
        player = Fighter("Игрок")
        enemy = Fighter("Враг")
        player.stats["agility"] = 8
        enemy.stats["agility"] = 4
        battle = CardBattle(
            player,
            enemy,
            cards=cards,
            rng=LastChoiceRandom(3),
        )
        for _ in range(battle.STARTING_PICK_LIMIT):
            battle.choose_starting_card("player", battle.table[0].key)
            battle.choose_starting_card("enemy", battle.table[0].key)

        battle.finish_starting_deal()

        # Более высокая характеристика больше не даёт дополнительную карту.
        self.assertIsNone(battle.starting_bonus_side)
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)

    def test_duel_scene_starts_redraft_when_deck_is_empty(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            kept_hands = {
                "player": [cards[8]],
                "enemy": [cards[9]],
            }
            scene.battle.hands = {
                side: list(hand) for side, hand in kept_hands.items()
            }
            scene.battle.deck = []
            scene.battle.discard = list(cards[:8])
            scene.battle.table = []
            scene.battle.draft_mode = None
            scene.phase = "deck_shuffle"
            scene.deck_shuffle_started = (
                time.monotonic() - settings.DECK_SHUFFLE_SECONDS
            )

            with patch("scenes.duel_scene.play_draft_music"):
                scene.update(0)

            self.assertIn(scene.phase, ("draft", "enemy_transfer"))
            self.assertEqual(scene.battle.draft_mode, "redraft")
            # У каждой стороны свой стол: считаем только сторону игрока
            self.assertEqual(
                len(scene.battle.table) + scene.battle.redraft_picks["player"],
                6,
            )
            for side, kept_hand in kept_hands.items():
                for card in kept_hand:
                    self.assertIn(card, scene.battle.hands[side])
            self.assertEqual(
                scene.draft_next_side,
                scene.battle.draft_first_side(),
            )
        finally:
            pygame.quit()

    def test_card_reward_requires_global_twenty_percent_roll(self):
        class NoRewardRandom:
            @staticmethod
            def random():
                return 0.20

        card = _reward_card("droppable", 50)

        self.assertIsNone(choose_battle_reward([card], NoRewardRandom()))

    def test_card_reward_uses_card_chances_as_selection_weights(self):
        class FixedRandom:
            def __init__(self):
                self.values = iter((0.19, 0.99))

            def random(self):
                return next(self.values)

        never = _reward_card("never", 0)
        guaranteed = _reward_card("guaranteed", 100)

        reward = choose_battle_reward([never, guaranteed], FixedRandom())

        self.assertEqual(reward, guaranteed)

    def test_victory_currency_reward_comes_from_server(self):
        class FakeSession:
            def __init__(self):
                self.reported = None

            @staticmethod
            def award_battle_card(_card_keys):
                return None

            def report_battle_result(self, _fighter, outcome, opponent_level, _opponent_profile=None):
                self.reported = (outcome, opponent_level)
                return {"currency": {"copper": 20, "silver": 1, "gold": 0}, "xp": 20}

            @staticmethod
            def save_fighter(_fighter):
                raise AssertionError("прогресс после боя сохраняет сервер")

        pygame.init()
        try:
            scene = DuelScene()
            session = FakeSession()
            scene.online_session = session
            scene.player.level = 5
            scene.player.hp = 1
            scene.enemy.hp = 0

            with patch("scenes.duel_scene.record_battle"):
                scene.finish_battle()
            scene.save_online_character()

            self.assertEqual(
                scene.currency_reward,
                {"copper": 20, "silver": 1, "gold": 0},
            )
            self.assertEqual(session.reported[0], "win")
        finally:
            pygame.quit()

    def test_result_screen_uses_large_coins_and_green_card_healing(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.currency_reward = {"copper": 20, "silver": 1, "gold": 0}
            scene.battle.stats["player"]["cards"] = ["Глоток Эля"]
            scene.battle.stats["player"]["card_healing"]["Глоток Эля"] = 12
            screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))

            with patch("ui.duel_renderer.draw_text") as draw_text_mock:
                scene.renderer.draw_result(screen)

            self.assertEqual(
                {
                    currency: icon.get_size()
                    for currency, icon in scene.renderer.reward_currency_icons.items()
                },
                {
                    "copper": (70, 70),
                    "silver": (70, 70),
                    "gold": (70, 70),
                },
            )
            healing_calls = [
                call.args
                for call in draw_text_mock.call_args_list
                if len(call.args) >= 6 and call.args[2] == "+12 HP"
            ]
            self.assertEqual(len(healing_calls), 1)
            self.assertEqual(healing_calls[0][5], (90, 230, 120))
        finally:
            pygame.quit()

    def test_result_screen_draws_received_card_face(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.card_reward = {
                "name": "Разрез",
                "group_name": "Боец: Кровавая жатва",
                "image_path": "assets/cards/faces/deaf_defense.png",
                "resource_type": "rage",
                "resource_cost": 11,
            }
            screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))

            with patch.object(
                scene.renderer.card_renderer,
                "_draw_card_front_scaled",
            ) as draw_card_mock:
                scene.renderer.draw_result(screen)

            draw_card_mock.assert_called_once()
            _screen, reward_card, reward_rect = draw_card_mock.call_args.args
            self.assertEqual(
                reward_card.image_path,
                "assets/cards/faces/deaf_defense.png",
            )
            self.assertEqual((reward_card.name, reward_card.resource_type, reward_card.resource_cost), ("Разрез", "rage", 11))
            self.assertEqual(reward_rect.size, (150, 200))
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()