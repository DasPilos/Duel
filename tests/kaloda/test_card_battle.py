import random
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from kaloda import settings
from kaloda.combat.card_battle import CardBattle, build_battle_deck
from kaloda.combat.card_database import Card, cards_for_type, choose_battle_reward, load_cards
from kaloda.combat.fighter import Fighter
from kaloda.combat.character_stats import BASE_STAT_VALUE
from kaloda.combat.mechanics import get_critical_chance, get_dodge_chance
from kaloda.ui.character_profile import derived_values, normalize_character_profile
from kaloda.ui.duel_renderer import DuelRenderer
from kaloda.ui.renderers.card_area import CardAreaRenderer
from kaloda.scenes.duel_scene import DuelScene
from kaloda.scenes.duel_input import DuelInputHandler


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

    def test_bot_receives_cards_for_its_profession(self):
        pygame.init()
        try:
            scene = DuelScene()
            for profession, group_prefix in (
                ("warrior", "Боец:"),
                ("assassin", "Асасин:"),
                ("archer", "Лучник:"),
            ):
                scene.opponent_profile = {
                    "id": f"bot_{profession}",
                    "name": f"Бот {profession}",
                    "level": 1,
                    "type": profession,
                    "stats": {
                        "strength": 2,
                        "agility": 2,
                        "intuition": 2,
                        "wisdom": 3,
                        "intellect": 3,
                        "harmony": 3,
                        "endurance": 4,
                    },
                    "hp": 50,
                    "mp": 20,
                }
                scene.restart()

                self.assertTrue(scene.battle.enemy_cards)
                self.assertTrue(
                    all(card.group_name.startswith(group_prefix) for card in scene.battle.enemy_cards)
                )
                self.assertTrue(
                    all(card.group_name.startswith(group_prefix) for card in scene.battle.enemy_table)
                )
                expected_player_prefix = "Боец:"
                self.assertTrue(
                    all(card.group_name.startswith(expected_player_prefix) for card in scene.battle.table)
                )
        finally:
            pygame.quit()

    def test_bot_draft_uses_its_own_class_table_after_player_selects_card(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.player.set_profession("archer")
            scene.enemy.set_profession("warrior")
            scene.battle = CardBattle(
                scene.player,
                scene.enemy,
                cards=cards_for_type("archer"),
                enemy_cards=cards_for_type("warrior"),
                rng=random.Random(1),
            )
            scene.phase = "draft"
            scene.draft_next_side = "player"
            renderer = scene.renderer.card_renderer
            selected_player_card = scene.battle.table[0]
            selected_rect = renderer.draft_slot_rect(0)

            scene.input_handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=selected_rect.center,
                )
            )
            self.assertEqual(scene.phase, "draft_transfer")
            self.assertIn(selected_player_card, scene.battle.hands["player"])

            scene.card_transfer["started"] -= settings.PLAYER_DRAFT_PICK_MOVE_SECONDS
            with patch("kaloda.scenes.duel_scene.play_card_move_sound"):
                scene.update(0)

            self.assertEqual(scene.phase, "enemy_transfer")
            self.assertTrue(scene.battle.hands["enemy"])
            self.assertTrue(
                all(card.group_name.startswith(("Боец:", "Универсальные:")) for card in scene.battle.hands["enemy"])
            )
            self.assertTrue(
                all(card.group_name.startswith(("Лучник:", "Универсальные:")) for card in scene.battle.table)
            )
        finally:
            pygame.quit()

    def test_battle_starts_with_full_health_and_displays_final_hp(self):
        pygame.init()
        try:
            scene = DuelScene()
            character_profile = {
                "id": 7,
                "name": "Игрок",
                "level": 1,
                "xp": 0,
                "type": "warrior",
                "stats": {
                    "strength": 3,
                    "agility": 3,
                    "intuition": 3,
                    "wisdom": 3,
                    "intellect": 3,
                    "harmony": 3,
                    "endurance": 5,
                },
                "hp": 1,
                "mp": 15,
            }
            opponent_profile = {
                **character_profile,
                "id": "bot_warrior",
                "name": "Бот",
                "hp": 1,
                "kind": "bot",
            }
            scene.online_session = SimpleNamespace(
                character=character_profile,
                selected_deck=None,
            )
            scene.opponent_profile = opponent_profile

            scene.restart()

            self.assertEqual(scene.player.hp, scene.player.max_hp)
            self.assertEqual(scene.enemy.hp, scene.enemy.max_hp)
            player_display = normalize_character_profile(scene.player)
            enemy_display = normalize_character_profile(scene.enemy)
            self.assertEqual(player_display["hp"], player_display["max_hp"])
            self.assertEqual(enemy_display["hp"], enemy_display["max_hp"])
            labels = []

            def capture_text(_screen, _font, text, *_args, **_kwargs):
                labels.append(text)

            with patch("kaloda.ui.duel_renderer.draw_text", side_effect=capture_text):
                scene.renderer.draw_battle_stats(
                    pygame.Surface((settings.WIDTH, settings.HEIGHT))
                )

            self.assertIn(
                f"HP: {scene.enemy.hp}/{scene.enemy.max_hp}",
                labels,
            )
        finally:
            pygame.quit()

    def test_card_details_open_with_right_click_and_close_with_left_click(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.player.set_profession("assassin")
            scene.enemy.set_profession("warrior")
            scene.battle = CardBattle(
                scene.player,
                scene.enemy,
                cards=cards_for_type("assassin"),
                enemy_cards=cards_for_type("warrior"),
            )
            scene.phase = "planning"
            card = next(card for card in scene.battle.cards if card.effect_data.get("dice"))
            scene.battle.hands["player"] = [card]
            scene.player.unique_resource_current = 0
            renderer = scene.renderer.card_renderer
            card_rect = renderer.card_rect(scene.layout.player_hand, 1, 0)
            handler = DuelInputHandler(scene)

            handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=3,
                    pos=card_rect.center,
                )
            )

            self.assertNotIn(card, scene.battle.selected["player"])
            self.assertIs(renderer.details_card, card)
            self.assertFalse(scene.battle.can_select("player", card))
            self.assertEqual(card.resource_type, "concentration")
            renderer.close_details()

            scene.player.unique_resource_current = card.resource_cost
            handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=card_rect.center,
                )
            )
            self.assertIn(card, scene.battle.selected["player"])
            selected_rect = renderer.card_rect(
                scene.layout.player_selected,
                1,
                0,
            )
            handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=3,
                    pos=selected_rect.center,
                )
            )
            self.assertIs(renderer.details_card, card)
            details = renderer._card_information_lines(card, detailed=True)
            self.assertTrue(any(line.startswith("Стоимость:") for line in details))
            self.assertTrue(any("Итоговый урон сейчас:" in line for line in details))
            self.assertTrue(any("Формула и текущие значения:" in line for line in details))

            surface = pygame.Surface((settings.WIDTH, settings.HEIGHT))
            renderer._draw_card_details(surface)
            self.assertIsNotNone(renderer.details_close_rect)
            handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=(0, 0),
                )
            )
            self.assertIsNone(renderer.details_card)
            handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=scene.layout.play_cards_button.center,
                )
            )
            self.assertEqual(scene.phase, "waiting_enemy")
            scene.enemy_wait_started -= 1
            with patch("kaloda.scenes.duel_scene.duck_battle_music"):
                scene.update(0)
            self.assertEqual(scene.phase, "clash")
        finally:
            pygame.quit()

    def test_b_key_burns_selected_card_for_fifteen_percent_resources(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.phase = "planning"
            card, selected_card = scene.battle.cards[:2]
            scene.battle.hands["player"] = [card, selected_card]
            scene.battle.selected["player"] = [selected_card]
            scene.player.mp = 0
            scene.player.unique_resource_current = 0
            expected_mana = int(scene.player.max_mp * 0.15)
            expected_unique = int(scene.player.unique_resource_max * 0.15)

            scene.input_handler.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b)
            )
            self.assertTrue(scene.burn_mode)
            self.assertEqual(scene.battle.selected["player"], [selected_card])

            card_rect = scene.renderer.card_renderer.card_rect(
                scene.layout.player_hand,
                1,
                0,
            )
            scene.input_handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=card_rect.center,
                )
            )
            self.assertEqual(scene.burn_card_key, card.key)
            self.assertIn(card, scene.battle.hands["player"])

            scene.input_handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=scene.layout.play_cards_button.center,
                )
            )

            self.assertFalse(scene.burn_mode)
            self.assertNotIn(card, scene.battle.hands["player"])
            self.assertNotIn(card, scene.battle.deck)
            self.assertNotIn(card, scene.battle.discard)
            self.assertEqual(scene.battle.selected["player"], [selected_card])
            self.assertEqual(scene.player.mp, expected_mana)
            self.assertEqual(scene.player.unique_resource_current, expected_unique)
        finally:
            pygame.quit()

    def test_hover_card_summary_only_shows_final_effect_outcomes(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.phase = "planning"
            scene.player.set_profession("archer")
            renderer = scene.renderer.card_renderer
            card = Card(
                "test_rooted_strike", "Удар с оплетением", "Проворный герой",
                "accuracy", 2, "damage", {"dice": 4, "entangle": 2},
            )

            lines = renderer._card_hover_information_lines(card)

            self.assertTrue(any(line.startswith("Итоговый урон:") for line in lines))
            self.assertIn("Оплетение: 2 хода.", lines)
            self.assertFalse(any("Стоимость" in line or "Формула" in line or "крит" in line.lower()
                                 for line in lines))
        finally:
            pygame.quit()

    def test_hover_card_summary_shows_magic_status_and_damage_debuff(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.phase = "planning"
            scene.player.set_profession("mage")
            card = Card(
                "test_water_bolt", "Водяной удар", "Магия: Вода",
                "mana", 5, "mage_damage_status",
                {
                    "damage": 12,
                    "status": "вода",
                    "status_duration": 2,
                    "damage_percent": -8,
                    "intellect_percent": 2,
                },
                effect_duration=2,
            )

            lines = scene.renderer.card_renderer._card_hover_information_lines(card)

            self.assertTrue(any(line.startswith("Итоговый урон:") for line in lines))
            self.assertIn("Статус «вода»: 1 ур. на 2 хода.", lines)
            self.assertTrue(any(line.startswith("Снижение урона врага:") for line in lines))
            self.assertFalse(any("Стоимость" in line or "Формула" in line for line in lines))
        finally:
            pygame.quit()

    def test_burning_card_grants_fifteen_percent_and_removes_it_for_battle(self):
        player = Fighter("Асасин", profession_type="assassin")
        enemy = Fighter("Враг")
        battle = CardBattle(
            player,
            enemy,
            cards=[],
        )
        card = cards_for_type("assassin")[0]
        battle.hands["player"] = [card]
        player.mp = 0
        player.unique_resource_current = 0
        expected_mana = int(player.max_mp * 0.15)
        expected_unique = int(player.unique_resource_max * 0.15)

        self.assertTrue(battle.burn_card("player", card.key))

        self.assertNotIn(card, battle.hands["player"])
        self.assertNotIn(card, battle.deck)
        self.assertNotIn(card, battle.discard)
        self.assertEqual(player.mp, expected_mana)
        self.assertEqual(player.unique_resource_current, expected_unique)
        self.assertFalse(battle.burn_card("player", card.key))

    def test_burning_card_restores_necromancers_necrotism(self):
        player = Fighter("Некромант", profession_type="necromancer")
        battle = CardBattle(
            player,
            Fighter("Враг"),
            cards=[],
        )
        card = cards_for_type("necromancer")[0]
        battle.hands["player"] = [card]
        player.unique_resource_current = 0

        self.assertTrue(battle.burn_card("player", card.key))

        self.assertEqual(
            player.unique_resource_current,
            int(player.unique_resource_max * 0.15),
        )

    def test_necromancer_starts_battle_with_fifteen_percent_necrotism(self):
        player = Fighter("Некромант", profession_type="necromancer")
        enemy = Fighter("Противник", profession_type="necromancer")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("necromancer"),
            enemy_cards=cards_for_type("necromancer"),
        )
        player.unique_resource_current = player.unique_resource_max
        enemy.unique_resource_current = enemy.unique_resource_max
        expected = int(player.unique_resource_max * 0.15)

        battle._start_turn(draw_cards=False)

        self.assertEqual(player.unique_resource_current, expected)
        self.assertEqual(enemy.unique_resource_current, expected)

    def test_necromancer_recovers_eight_plus_level_necrotism_each_turn(self):
        player = Fighter("Некромант", level=3, profession_type="necromancer")
        enemy = Fighter("Противник")
        battle = CardBattle(
            player,
            enemy,
            cards=cards_for_type("necromancer"),
            enemy_cards=cards_for_type("warrior"),
        )

        battle._start_turn(draw_cards=False)
        player.unique_resource_current = 0
        battle._start_turn(draw_cards=False)

        self.assertEqual(player.unique_resource_current, 11)

        player.unique_resource_current = player.unique_resource_max - 1
        battle._start_turn(draw_cards=False)

        self.assertEqual(player.unique_resource_current, player.unique_resource_max)

    def test_necromancer_card_cost_label_uses_necrotism_name(self):
        class CaptureFont:
            text = None

            def render(self, text, _antialias, _color):
                self.text = text
                return SimpleNamespace(get_rect=lambda **_kwargs: None)

        class CaptureScreen:
            def blit(self, *_args):
                pass

        renderer = CardAreaRenderer.__new__(CardAreaRenderer)
        renderer.scene = SimpleNamespace(
            player=Fighter("Некромант", profession_type="necromancer")
        )
        renderer.card_cost_font = CaptureFont()
        card = next(card for card in cards_for_type("necromancer") if card.key == "necromancer_spirit")
        rect = SimpleNamespace(centerx=50, bottom=100)

        renderer._draw_card_costs(CaptureScreen(), card, rect)

        self.assertEqual(renderer.card_cost_font.text, "20 НЕКРОТИЗМА")

    def test_mage_opponent_profile_fills_missing_stats_before_recalculation(self):
        fighter = Fighter("Противник")
        profile = {
            "name": "Маг-бот",
            "level": 1,
            "type": "mage",
            "stats": {"strength": 0, "agility": 0, "intuition": 0},
            "hp": 50,
            "mp": 20,
        }

        DuelScene._apply_fighter_profile(fighter, profile)

        self.assertEqual(fighter.profession_type, "mage")
        self.assertEqual(fighter.stats["intellect"], BASE_STAT_VALUE)
        self.assertGreater(fighter.max_hp, 0)
        self.assertGreater(fighter.max_mp, 0)

    def test_chance_modifiers_keep_unavailable_dodge_placeholder(self):
        mage = Fighter("Маг", profession_type="mage")

        adjusted = DuelRenderer._apply_chance_modifiers(
            {"Уворот": "--", "Крит": "5% × 165%"},
            mage,
        )

        self.assertEqual(adjusted["Уворот"], "--")
        self.assertEqual(adjusted["Крит"], "5% × 165%")

    def test_starting_draft_cards_fill_two_centered_rows_of_eleven(self):
        pygame.init()
        try:
            scene = DuelScene()
            renderer = scene.renderer.card_renderer
            scene.battle.table = list(scene.battle.cards[:22])
            rects = [renderer.draft_slot_rect(index) for index in range(22)]
            self.assertEqual(len({rect.y for rect in rects[:11]}), 1)
            self.assertEqual(len({rect.y for rect in rects[11:]}), 1)
            self.assertGreater(rects[11].y, rects[0].y)
            self.assertTrue(all(scene.layout.card_table.contains(rect) for rect in rects))
            self.assertEqual(rects[0].left, scene.layout.card_table.left + 1)
            self.assertEqual(rects[10].right, scene.layout.card_table.right - 1)
            self.assertEqual(rects[0].width, rects[10].width)
            self.assertEqual(rects[0].height, rects[10].height)

            with patch.object(renderer, "_draw_moving_card") as draw_moving_card:
                renderer._draw_reveal_cards(None, scene.battle.table, 10, scene.layout.card_table)
            self.assertEqual(draw_moving_card.call_count, 22)
            self.assertTrue(
                all(call.kwargs["target_size"] == rects[index].size
                    for index, call in enumerate(draw_moving_card.call_args_list))
            )

            slots = list(renderer.draft_slots())
            taken = slots[2]
            scene.battle.table.remove(taken)
            after = renderer.draft_slots()
            self.assertIsNone(after[2])
            self.assertEqual(after[3], slots[3])

            scene.battle.draft_mode = "redraft"
            redraft_rects = [renderer.draft_slot_rect(index) for index in range(6)]
            self.assertEqual(redraft_rects[0].size, (renderer.CARD_WIDTH, renderer.CARD_HEIGHT))
            self.assertEqual(redraft_rects[0].y, redraft_rects[4].y)
            self.assertGreater(redraft_rects[5].y, redraft_rects[0].y)
        finally:
            pygame.quit()

    def test_fighter_panel_uses_profession_type_for_class_colors(self):
        pygame.init()
        try:
            scene = DuelScene()
            expected_dominant_channels = {
                "archer": "green",
                "assassin": "purple",
                "warrior": "red",
            }
            for profession, expected_color in expected_dominant_channels.items():
                scene.player.set_profession(profession)
                surface = pygame.Surface((settings.WIDTH, settings.HEIGHT))
                surface.fill((0, 0, 0))
                profile = {
                    "type": "warrior",
                    "profession_type": profession,
                    "hp": scene.player.hp,
                    "max_hp": scene.player.max_hp,
                    "mp": scene.player.mp,
                    "max_mp": scene.player.max_mp,
                }

                scene.renderer._draw_corner_fighter_card(
                    surface,
                    scene.player,
                    profile,
                    {},
                    10,
                    10,
                    (80, 180, 120),
                    "left",
                )

                red, green, blue, _alpha = surface.get_at((20, 20))
                if expected_color == "green":
                    self.assertGreater(green, red)
                    self.assertGreater(green, blue)
                elif expected_color == "purple":
                    self.assertGreater(red, green)
                    self.assertGreater(blue, green)
                else:
                    self.assertGreater(red, green)
                    self.assertGreater(red, blue)
        finally:
            pygame.quit()

    def test_turn_timer_is_one_minute(self):
        self.assertEqual(settings.TURN_DECISION_SECONDS, 60)

    def test_combat_messages_stay_above_each_fighters_stats_for_ten_seconds(self):
        pygame.init()
        screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
        try:
            scene = DuelScene()
            scene.battle.last_exchange = [
                {
                    "side": "player",
                    "effect_text": "Дурман",
                    "damage": 7,
                    "dodged": False,
                    "critical": False,
                },
                {
                    "side": "enemy",
                    "effect_text": "Яды не найдены",
                    "damage": 3,
                    "dodged": False,
                    "critical": False,
                },
            ]
            scene.resolver.damage_image = None

            with patch("kaloda.scenes.duel_resolver.play_damage_sound"):
                scene.resolver._add_floating_damage()

            messages = scene.active_floating_texts
            self.assertEqual(len(messages), 4)
            player_x = scene.resolver._floating_text_x("player")
            enemy_x = scene.resolver._floating_text_x("enemy")
            panel_top = scene.resolver._floating_text_panel_top()
            self.assertCountEqual([message.x for message in messages], [player_x, enemy_x, enemy_x, player_x])
            self.assertCountEqual(
                [message.y for message in messages],
                [
                    panel_top - scene.resolver.FLOATING_TEXT_PANEL_GAP,
                    panel_top - scene.resolver.FLOATING_TEXT_PANEL_GAP,
                    panel_top - scene.resolver.FLOATING_TEXT_PANEL_GAP - scene.resolver.FLOATING_TEXT_LINE_HEIGHT,
                    panel_top - scene.resolver.FLOATING_TEXT_PANEL_GAP - scene.resolver.FLOATING_TEXT_LINE_HEIGHT,
                ],
            )
            self.assertTrue(all(message.duration == settings.FPS * 10 for message in messages))
            self.assertTrue(all(message.vy == 0 and not message.fade_out for message in messages))

            original_positions = [(message.x, message.y) for message in messages]
            for _ in range(settings.FPS):
                for message in messages:
                    message.update()
            self.assertEqual([(message.x, message.y) for message in messages], original_positions)
            self.assertTrue(all(message.duration == settings.FPS * 9 for message in messages))

            with patch("kaloda.scenes.duel_resolver.play_damage_sound"):
                scene.resolver._add_floating_damage()
            positions_by_side = {
                side: [
                    (message.x, message.y)
                    for message in scene.active_floating_texts
                    if message.x == scene.resolver._floating_text_x(side)
                ]
                for side in ("player", "enemy")
            }
            for positions in positions_by_side.values():
                self.assertEqual(len(positions), 4)
                self.assertEqual(len({y for _x, y in positions}), 4)

            messages = scene.active_floating_texts
            for message in messages:
                message.duration = 1
            from kaloda.ui.hud import update_and_draw_floating_texts

            update_and_draw_floating_texts(screen, messages)
            self.assertEqual(messages, [])
        finally:
            pygame.quit()

    def test_card_phase_input_starts_with_burn_mode_disabled(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.phase = "planning"

            scene.input_handler._handle_card_phase((0, 0), 1)

            self.assertFalse(scene.burn_mode)
            self.assertIsNone(scene.burn_card_key)
        finally:
            pygame.quit()

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
        class FixedRandom:
            @staticmethod
            def random():
                return 0.99

            @staticmethod
            def randint(start, _end):
                return start

        card = Card(
            key="test_strike",
            name="Тестовый удар",
            group_name="Боец: Тест",
            resource_type="rage",
            resource_cost=0,
            effect_type="damage",
            effect_data={"dice": "1d4"},
        )
        damage_by_strength = {}
        for strength in (2, 7):
            player = Fighter("Игрок")
            enemy = Fighter("Враг")
            player.stats["strength"] = strength
            enemy.stats["endurance"] = 0
            battle = CardBattle(player, enemy, cards=[], rng=FixedRandom())
            damage_by_strength[strength] = battle._resolve_card("player", card)["damage"]

        self.assertEqual(damage_by_strength[7] - damage_by_strength[2], 5)

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
            self.assertEqual(scene.battle.hands["player"], [])
            self.assertEqual(scene.battle.hands["enemy"], [])
            self.assertEqual(len(scene.battle.table), 22)
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

    def test_stats_frames_leave_six_pixels_to_full_hand(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            hand_limit = scene.battle.hand_limit_for("player")
            scene.battle.hands["player"] = list(cards[:hand_limit])
            scene.battle.hands["enemy"] = list(cards[hand_limit:hand_limit * 2])

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
                hand_limit,
                0,
            )
            enemy_last = scene.renderer.card_renderer.card_rect(
                scene.layout.enemy_hand,
                hand_limit,
                hand_limit - 1,
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
            hand_limit = scene.battle.hand_limit_for("player")
            scene.battle.hands["player"] = list(cards[:hand_limit])
            scene.battle.hands["enemy"] = list(cards[hand_limit:hand_limit * 2])
            full_hand_geometry = {
                side: scene.renderer._stats_frame_geometry(side, settings.WIDTH)
                for side in ("player", "enemy")
            }

            scene.battle.hands["player"] = list(cards[:3])
            scene.battle.hands["enemy"] = list(cards[3:6])

            for side, expected in full_hand_geometry.items():
                self.assertEqual(
                    scene.renderer._stats_frame_geometry(side, settings.WIDTH),
                    expected,
                )
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

        # Физический урон карты считается от максимума кубика (1d4 -> 4) плюс сила.
        self.assertEqual(event["damage"], 24)
        description = CardAreaRenderer._card_description(card)
        self.assertEqual(description, "Наносит 1d4 урона.")
        self.assertNotIn("Сила", description)

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

    def test_full_hand_burns_drawn_card_instead_of_adding_it(self):
        cards = load_cards()
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[])
        battle.draft_mode = None
        limit = battle.MAX_HAND_SIZE
        battle.hands["player"] = list(cards[:limit])
        battle.hands["enemy"] = list(cards[:limit])
        battle.deck = list(cards[limit:limit + 3])
        battle.enemy_deck = list(cards[limit:limit + 3])

        battle.start_next_turn()

        for side in ("player", "enemy"):
            self.assertEqual(len(battle.hands[side]), limit)
        # Добранная карта при полной руке сгорает: колода уменьшилась, сброс вырос.
        self.assertEqual(len(battle.deck), 2)
        self.assertEqual(len(battle.discard), 1)
        self.assertEqual(len(battle.enemy_deck), 2)
        self.assertEqual(len(battle.enemy_discard), 1)

    def test_redraft_never_exceeds_hand_limit(self):
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
        battle.enemy_discard = list(card_pool[18:24])

        self.assertTrue(battle.prepare_redraft())
        battle.finish_afk_redraft()

        self.assertEqual(len(battle.hands["player"]), battle.MAX_HAND_SIZE)
        self.assertEqual(len(battle.hands["enemy"]), battle.MAX_HAND_SIZE)
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
        battle.enemy_discard = list(cards[10:16])

        self.assertTrue(battle.prepare_redraft())
        self.assertEqual(battle.draft_first_side(), "player")
        self.assertEqual(battle.hands["player"], [kept_player_card])
        self.assertEqual(battle.hands["enemy"], [kept_enemy_card])
        self.assertEqual(len(battle.table), 6)

        side = battle.draft_first_side()
        while not battle.current_draft_complete():
            table = battle.table_for(side)
            battle.choose_redraft_card(side, table[0].key)
            side = "enemy" if side == "player" else "player"
        # Бонусная карта за более высокую характеристику убрана — обе стороны
        # получают ровно то, что выбрали в повторном драфте.
        self.assertIsNone(battle.take_draft_bonus_card())
        battle.finish_redraft()

        self.assertIn(kept_player_card, battle.hands["player"])
        self.assertIn(kept_enemy_card, battle.hands["enemy"])
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)
        self.assertEqual(len(battle.deck), 6)
        self.assertEqual(len(battle.enemy_deck), 4)
        self.assertEqual(battle.discard, [])

        battle.start_next_turn()

        self.assertEqual(len(battle.hands["player"]), 4)
        self.assertEqual(len(battle.hands["enemy"]), 4)
        self.assertEqual(len(battle.deck), 5)
        self.assertEqual(len(battle.enemy_deck), 3)

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
        battle.enemy_deck = list(cards[7:13])
        battle.discard = list(cards[2:7])

        self.assertFalse(battle.prepare_redraft())
        battle.discard.extend(battle.deck)
        battle.deck.clear()

        self.assertTrue(battle.prepare_redraft())
        self.assertEqual(len(battle.table), 6)

        side = battle.draft_first_side()
        while not battle.current_draft_complete():
            table = battle.table_for(side)
            battle.choose_redraft_card(side, table[0].key)
            side = "enemy" if side == "player" else "player"
        self.assertIsNone(battle.take_draft_bonus_card())
        battle.finish_redraft()

        self.assertEqual(len(battle.deck), 5)
        self.assertEqual(len(battle.enemy_deck), 4)
        battle.start_next_turn()
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)
        self.assertEqual(len(battle.deck), 4)
        self.assertEqual(len(battle.enemy_deck), 3)

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

            with patch("kaloda.scenes.duel_scene.play_draft_music"):
                scene.update(0)

            self.assertEqual(scene.phase, "card_draw_choice")
            self.assertEqual(len(scene.battle.draw_choices["player"]), 2)
            self.assertEqual(len(scene.battle.draw_choices["enemy"]), 0)
            self.assertAlmostEqual(
                scene.draw_choice_deadline - time.monotonic(),
                settings.DRAW_CHOICE_SECONDS,
                delta=0.1,
            )
        finally:
            pygame.quit()

    def test_draw_choices_use_each_side_deck_and_put_unselected_card_at_bottom(self):
        cards = load_cards()
        player = Fighter("Игрок")
        enemy = Fighter("Противник")
        battle = CardBattle(player, enemy, cards=[])
        battle.dual_table = True
        battle.deck = list(cards[:4])
        battle.enemy_deck = list(cards[4:8])

        player_choices = battle.prepare_draw_choice("player")
        enemy_choices = battle.prepare_draw_choice("enemy")

        self.assertEqual(player_choices, [cards[3], cards[2]])
        self.assertEqual(enemy_choices, [cards[7], cards[6]])
        self.assertEqual(battle.deck, cards[:2])
        self.assertEqual(battle.enemy_deck, cards[4:6])

        self.assertTrue(battle.choose_draw_card("player", cards[2].key))
        self.assertTrue(battle.choose_draw_card("enemy", cards[7].key))

        self.assertEqual(battle.hands["player"], [cards[2]])
        self.assertEqual(battle.hands["enemy"], [cards[7]])
        self.assertEqual(battle.deck, [cards[3], *cards[:2]])
        self.assertEqual(battle.enemy_deck, [cards[6], *cards[4:6]])

    def test_draw_choice_timeout_defaults_to_top_card_for_both_fighters(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.deck = list(cards[:4])
            scene.battle.enemy_deck = list(cards[4:8])
            scene.battle.draft_mode = None
            scene.battle.hands = {"player": [], "enemy": []}

            scene._start_next_card_draw(time.monotonic())
            player_top = scene.battle.draw_choices["player"][0]
            enemy_top = scene.battle.draw_choices["enemy"][0]
            scene.draw_choice_deadline = time.monotonic() - 1

            scene.update(0)

            self.assertEqual(scene.phase, "planning")
            self.assertEqual(scene.battle.hands["player"], [player_top])
            self.assertEqual(scene.battle.hands["enemy"], [enemy_top])
            self.assertEqual(scene.battle.deck[0], cards[2])
            self.assertEqual(scene.battle.enemy_deck[0], cards[6])
            self.assertIsNone(scene.draw_choice_deadline)
        finally:
            pygame.quit()

    def test_player_can_choose_displayed_card_and_bot_selects_from_own_draw(self):
        pygame.init()
        try:
            scene = DuelScene()
            cards = load_cards()
            scene.battle.deck = list(cards[:4])
            scene.battle.enemy_deck = list(cards[4:8])
            scene.battle.draft_mode = None
            scene.battle.hands = {"player": [], "enemy": []}
            scene._start_next_card_draw(time.monotonic())
            selected = scene.battle.draw_choices["player"][1]
            enemy_selected = scene.battle.draw_choices["enemy"][0]
            card_area = scene.renderer.card_renderer.draw_choice_area("player")
            card_rect = scene.renderer.card_renderer.card_rect(card_area, 2, 1)
            scene.renderer.card_renderer.draw(
                pygame.Surface((settings.WIDTH, settings.HEIGHT))
            )

            scene.input_handler.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=card_rect.center,
                )
            )

            self.assertEqual(scene.phase, "planning")
            self.assertEqual(scene.battle.hands["player"], [selected])
            self.assertEqual(scene.battle.hands["enemy"], [enemy_selected])
            self.assertIn(cards[0], scene.battle.deck)
            self.assertIn(cards[4], scene.battle.enemy_deck)
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
        battle.enemy_discard = list(cards[10:16])

        battle.start_next_turn()

        self.assertEqual(battle.turn, 1)
        self.assertEqual(battle.draft_mode, None)
        self.assertEqual(battle.table, [])
        self.assertEqual(battle.discard, [])
        self.assertEqual(len(battle.deck), 6)
        self.assertEqual(len(battle.enemy_deck), 4)
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)

    def test_headless_redraft_starts_on_turn_after_last_draw(self):
        cards = load_cards()
        battle = CardBattle(Fighter("Игрок"), Fighter("Враг"), cards=[])
        battle.draft_mode = None
        battle.deck = [cards[0]]
        battle.discard = list(cards[1:7])
        battle.enemy_deck = list(cards[7:14])

        battle.start_next_turn()

        self.assertEqual(len(battle.discard), 6)
        self.assertEqual(len(battle.hands["player"]), 1)
        self.assertEqual(len(battle.hands["enemy"]), 1)

        battle.start_next_turn()

        self.assertEqual(battle.draft_mode, None)
        self.assertEqual(battle.discard, [])
        self.assertEqual(battle.table, [])
        self.assertEqual(len(battle.hands["player"]), 3)
        self.assertEqual(len(battle.hands["enemy"]), 3)

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
            battle.choose_starting_card("enemy", battle.table_for("enemy")[0].key)

        battle.finish_starting_deal()

        # Более высокая характеристика больше не даёт дополнительную карту.
        self.assertIsNone(battle.starting_bonus_side)
        starting_hand_size = battle.STARTING_RANDOM_CARDS + battle.STARTING_PICK_LIMIT
        self.assertEqual(len(battle.hands["player"]), starting_hand_size)
        self.assertEqual(len(battle.hands["enemy"]), starting_hand_size)

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
            scene.battle.enemy_deck = []
            scene.battle.enemy_discard = list(cards[8:16])
            scene.battle.table = []
            scene.battle.draft_mode = None
            scene.phase = "deck_shuffle"
            scene.deck_shuffle_started = (
                time.monotonic() - settings.DECK_SHUFFLE_SECONDS
            )

            with patch("kaloda.scenes.duel_scene.play_draft_music"):
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

            def report_battle_result(self, _fighter, outcome, opponent_level,
                                     _opponent_profile=None, battle_record=None):
                self.reported = (outcome, opponent_level, battle_record)
                return {"currency": {"coins": 120}, "xp": 20}

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

            scene.finish_battle()
            scene.save_online_character()

            self.assertEqual(
                scene.currency_reward,
                {"coins": 120},
            )
            self.assertEqual(session.reported[0], "win")
            self.assertEqual(session.reported[2]["player"]["name"], "Игрок")
        finally:
            pygame.quit()

    def test_result_screen_uses_large_coins_and_green_card_healing(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.currency_reward = {"coins": 120}
            scene.battle.stats["player"]["cards"] = ["Глоток Эля"]
            scene.battle.stats["player"]["card_healing"]["Глоток Эля"] = 12
            screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))

            with patch("kaloda.ui.duel_renderer.draw_text") as draw_text_mock:
                scene.renderer.draw_result(screen)

            self.assertEqual(scene.renderer.reward_money_icon.get_size(), (70, 70))
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