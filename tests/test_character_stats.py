import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_carry_capacity, calculate_max_hp
from combat.fighter import Fighter
from core import settings
from core.carry_weight import GREEN, NEUTRAL, RED, YELLOW, carried_weight_kg, load_color, movement_speed_multiplier
from scenes.tavern_scene import TavernScene
from ui.chat.panel import ChatPanel
from ui.character_card import CharacterCard
from ui.character_profile import (
    derived_values,
    displayed_hp_values,
    normalize_character_profile,
    profile_from_fighter,
)
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.tavern_shop import TavernShop


class CharacterStatTests(unittest.TestCase):
    def test_carry_capacity_uses_strength_and_endurance(self):
        self.assertEqual(calculate_carry_capacity(6, 4), 42)
        self.assertEqual(calculate_carry_capacity(3, 3), 24)

    def test_carry_load_colors_and_movement_thresholds(self):
        self.assertEqual(load_color(30, 100), GREEN)
        self.assertEqual(movement_speed_multiplier(45, 100), 0.7)
        self.assertEqual(movement_speed_multiplier(60, 100), 0.7)
        self.assertEqual(load_color(61, 100), YELLOW)
        self.assertEqual(movement_speed_multiplier(61, 100), 0.5)
        self.assertEqual(load_color(80, 100), YELLOW)
        self.assertEqual(movement_speed_multiplier(80, 100), 0.5)
        self.assertEqual(load_color(81, 100), RED)
        self.assertEqual(movement_speed_multiplier(81, 100), 0.3)
        self.assertEqual(load_color(45, 100), NEUTRAL)

    def test_carried_weight_sums_bag_and_equipment_once(self):
        inventory = [{"weight": 2.5, "quantity": 2}, {"weight": 1, "quantity": 3}]
        equipment = {
            "weapon": {"weight": 4},
            "shield": {"weight": 4, "_two_handed_shadow": True},
            "body": {"weight": 5},
        }
        self.assertEqual(carried_weight_kg(inventory, equipment), 17)

    def test_max_hp_formula_matches_level_and_endurance(self):
        self.assertEqual(calculate_max_hp(1, 5), 50)
        self.assertEqual(calculate_max_hp(3, 7), 70)

    def test_profile_model_normalizes_fighter_and_derived_values(self):
        fighter = Fighter("Тест")
        profile = normalize_character_profile(profile_from_fighter(fighter))

        self.assertEqual(profile["stats"], fighter.stats)
        self.assertEqual(derived_values(profile), {
            "Урон": 3,
            "Уворот": "6%",
            "Крит": "5% × 165%",
            "Маг Урон": 3,
            "HP": 30,
        })

    def test_endurance_cannot_increase_manually(self):
        state = adjust_stats(
            {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            20,
            25,
            1,
            "endurance",
            1,
        )

        self.assertIsNone(state)

    def test_stat_decrease_cannot_go_below_minimum(self):
        state = adjust_stats(
            {"strength": 3, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            25,
            25,
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

            self.assertTrue(fighter.add_stat("strength"))
            self.assertTrue(card.adjust_stat("strength", 1))
            self.assertEqual(card.data["stats"], fighter.stats)
            self.assertEqual(card.data["stat_points"], fighter.stat_points)
            self.assertEqual(card.data["hp"], fighter.hp)
            self.assertEqual(card.data["max_hp"], fighter.max_hp)
        finally:
            pygame.quit()

    def test_character_card_currency_icons_are_30_pixels(self):
        pygame.init()
        try:
            card = CharacterCard()

            self.assertEqual(card.CURRENCY_ICON_SIZE, 30)
            self.assertEqual(
                {name: icon.get_size() for name, icon in card.currency_icons.items()},
                {
                    "copper": (30, 30),
                    "silver": (30, 30),
                    "gold": (30, 30),
                },
            )
        finally:
            pygame.quit()

    def test_tavern_ale_image_is_100_pixels(self):
        pygame.init()
        try:
            font = pygame.font.Font(None, 18)
            shop = TavernShop(font, font)

            self.assertEqual(shop.DRINK_ICON_SIZE, 100)
            self.assertEqual(shop.ale_image.get_size(), (100, 100))
            self.assertEqual(shop._drink_rect(0).height, 110)
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
                "hp": 25,
                "max_hp": 25,
                "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
                "stat_points": 6,
            })
            _, plus = overlay.player_card._stat_control_rects(
                overlay.player_frame,
                CharacterCard._stat_row_y(overlay.player_frame, 0),
            )

            action, profile = overlay.handle_click(plus.center)

            self.assertEqual(action, "stat_change")
            self.assertEqual(profile["stats"]["strength"], 6)
            self.assertEqual(profile["stat_points"], 5)
        finally:
            pygame.quit()

    def test_stat_buttons_grow_without_moving(self):
        pygame.init()
        try:
            frame = pygame.Rect(20, 120, 500, 955)
            minus, plus = CharacterCard._stat_control_rects(frame, frame.bottom - 92)

            self.assertEqual(minus.topleft, (176, 988))
            self.assertEqual(plus.topleft, (195, 988))
            self.assertEqual(minus.size, (13, 13))
            self.assertEqual(plus.size, (13, 13))
        finally:
            pygame.quit()

    def test_chat_right_click_opens_profile_overlay(self):
        pygame.init()
        try:
            class Session:
                character = {"id": 1, "name": "Игрок"}

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def duel_board(self, location):
                    return {"offers": []}

            overlay = CharacterProfileOverlay(pygame.font.Font(None, 18))
            panel = ChatPanel(Session(), "tavern", profile_overlay=overlay)
            panel.occupants = [{"character_id": 2, "name": "Соперник"}]
            occupant_position = (panel.people_rect.x + 10, panel.people_rect.y + 10)
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 3, "pos": occupant_position},
            )

            self.assertTrue(panel.handle_event(event))
            self.assertTrue(overlay.is_open)
            self.assertEqual(overlay.profile["name"], "Соперник")
        finally:
            pygame.quit()

    def test_chat_divider_resizes_both_content_areas(self):
        pygame.init()
        try:
            class Session:
                character = {"id": 1, "name": "Игрок"}

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def duel_board(self, location):
                    return {"offers": []}

            panel = ChatPanel(Session(), "tavern")
            message_width = panel.message_list.rect.width
            people_width = panel.people_rect.width
            self.assertEqual(panel.panel_rect.left, settings.CHAT_PANEL_X)
            self.assertEqual(panel.panel_rect.right, settings.CHAT_PANEL_X + settings.CHAT_PANEL_WIDTH)

            panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": panel.divider_rect.center}))
            panel.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (panel.divider_rect.centerx - 80, panel.divider_rect.centery)}))
            panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": panel.divider_rect.center}))

            self.assertLess(panel.message_list.rect.width, message_width)
            self.assertGreater(panel.people_rect.width, people_width)
            self.assertEqual(panel.message_input.rect.right, panel.divider_rect.left - settings.CHAT_DIVIDER_GAP)
            self.assertEqual(panel.people_rect.left, panel.divider_rect.right + settings.CHAT_DIVIDER_GAP)
        finally:
            pygame.quit()

    def test_chat_rewraps_messages_after_divider_moves(self):
        pygame.init()
        try:
            class Session:
                character = {"id": 1, "name": "Игрок"}

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def duel_board(self, location):
                    return {"offers": []}

            panel = ChatPanel(Session(), "tavern")
            panel.messages = [{"id": 1, "sender_id": 2, "sender": "Игрок", "text": "длинное сообщение " * 40}]
            panel.message_list.set_messages(panel.messages)
            screen = pygame.Surface((1920, 1080))
            panel.draw(screen)
            wide_line_count = len(panel.message_list._layout[0][0])

            panel._move_divider(panel.divider_rect.centerx - 120)
            panel.draw(screen)
            narrow_line_count = len(panel.message_list._layout[0][0])

            self.assertGreater(narrow_line_count, wide_line_count)
            self.assertEqual(panel.message_list._layout_width, panel.message_list.rect.width)
        finally:
            pygame.quit()

    def test_tavern_backyard_hotspot_remains_clickable(self):
        pygame.init()
        try:
            class Session:
                character = {"id": 1, "name": "Игрок"}

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def duel_board(self, location):
                    return {"offers": []}

            scene = TavernScene(Session())
            _, x, y, width, height, _ = next(
                hotspot for hotspot in scene.tavern_hotspots if hotspot[0] == "Задний двор"
            )
            rect = scene._hotspot_rect(x, y, width, height)
            self.assertEqual(rect, pygame.Rect(1560, 390, 55, 153))
            scene.chat.panel_rect.x += 100
            self.assertEqual(scene._hotspot_rect(x, y, width, height), rect)
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": rect.center},
            )

            scene.handle_event(event)

            self.assertTrue(scene.finished)
            self.assertEqual(scene.navigate, "backyard")
        finally:
            pygame.quit()

    def test_tavern_stat_click_saves_updated_profile(self):
        pygame.init()
        try:
            class Session:
                character = {
                    "id": 1,
                    "name": "Игрок",
                    "level": 1,
                    "xp": 0,
                    "hp": 25,
                    "max_hp": 25,
                    "mp": 50,
                    "max_mp": 50,
                    "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
                    "stat_points": 6,
                }

                def __init__(self):
                    self.saved_profiles = []

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def duel_board(self, location):
                    return {"offers": []}

                def save_character_profile(self, profile):
                    self.saved_profiles.append(profile)
                    self.character = dict(profile)
                    return self.character

            session = Session()
            scene = TavernScene(session)
            scene.profile_overlay.open({"id": 2, "name": "Соперник", "stats": {}}, counterpart=session.character)
            scene.draw(pygame.Surface((1920, 1080)))
            _, plus = scene.profile_overlay.player_card._stat_control_rects(
                scene.profile_overlay.player_frame,
                CharacterCard._stat_row_y(scene.profile_overlay.player_frame, 0),
            )

            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))
            scene.draw(pygame.Surface((1920, 1080)))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))

            self.assertEqual(len(session.saved_profiles), 2)
            self.assertEqual(session.saved_profiles[0]["stats"]["strength"], 6)
            self.assertEqual(session.saved_profiles[1]["stats"]["strength"], 7)
        finally:
            pygame.quit()

    def test_derived_values_are_own_and_include_weapon_damage(self):
        warrior = {
            "name": "Воин",
            "type": "warrior",
            "level": 1,
            "max_hp": 40,
            "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            "equipment_bonuses": {"strength": 1},
            "equipment": {"weapon": {"equip_slot": "weapon", "effects": {"damage": [5, 7]}}},
        }
        mage = {
            "name": "Маг",
            "type": "mage",
            "level": 1,
            "max_hp": 90,
            "stats": {"wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 4, "agility": 3},
        }

        # Урон = сила 5 + 1 от предмета + меч 5–7
        self.assertEqual(derived_values(warrior), {
            "Урон": "11-13", "Уворот": "10%", "Крит": "5% × 175%",
            "Маг Урон": "6-8", "HP": 40,
        })
        # Показатели одинаковы для всех классов: маг урон идёт от мудрости
        self.assertEqual(derived_values(mage), {
            "Урон": 1, "Уворот": "6%", "Крит": "5% × 150%",
            "Маг Урон": 3, "HP": 90,
        })

    def test_equipped_shield_block_is_displayed_in_derived_values(self):
        profile = normalize_character_profile({
            "stats": {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                      "intellect": 3, "harmony": 3, "endurance": 3},
            "equipment_bonuses": {"hp": 20, "block": 5},
        })

        self.assertEqual(derived_values(profile)["Блок"], "5%")

    def test_equipment_hp_bonus_updates_card_max_without_double_counting_fighter(self):
        server_profile = normalize_character_profile({
            "hp": 30, "max_hp": 30,
            "stats": {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                      "intellect": 3, "harmony": 3, "endurance": 3},
            "equipment_bonuses": {"hp": 20},
        })
        self.assertEqual(displayed_hp_values(server_profile), (50, 50))
        self.assertEqual(derived_values(server_profile)["HP"], 50)

        fighter = Fighter("Щитоносец")
        fighter.equipment_stat_modifiers = {"hp": 20}
        fighter.recalculate_parameters()
        self.assertEqual(displayed_hp_values(normalize_character_profile(profile_from_fighter(fighter))),
                         (fighter.hp, fighter.max_hp))

    def test_equipped_item_tooltip_contains_description_and_bonuses(self):
        lines = CharacterCard.equipment_tooltip_lines({
            "name": "Деревянный щит",
            "description": "Щит для защиты",
            "weight": 3,
            "bonuses": {"hp": 20, "block": 5},
            "effects": {"block": 5},
        })
        text = " ".join(line for line, _color in lines)
        self.assertIn("Щит для защиты", text)
        self.assertIn("+20 HP", text)
        self.assertIn("+5 % Блок", text)

    def test_hovering_equipped_shield_draws_tooltip(self):
        from unittest.mock import patch
        from ui.equipment_slots import slot_rects

        pygame.init()
        try:
            card = CharacterCard()
            screen = pygame.Surface((900, 1000))
            frame = pygame.Rect(20, 20, 440, 900)
            shield = {
                "name": "Деревянный щит",
                "description": "Щит для защиты",
                "weight": 3,
                "bonuses": {"hp": 20, "block": 5},
                "effects": {"block": 5},
            }
            with patch("pygame.mouse.get_pos", return_value=slot_rects(frame)["shield"].center):
                self.assertTrue(card._draw_equipment_tooltip(screen, frame, {"shield": shield}))
        finally:
            pygame.quit()

    def test_character_comparison_draw_cross_class_does_not_crash(self):
        from ui.character_comparison import CharacterComparison
        pygame.init()
        try:
            comparison = CharacterComparison(pygame.font.Font(None, 18))
            screen = pygame.Surface((1920, 1080))
            mage_player = {
                "id": 1,
                "name": "МагИгрок",
                "type": "mage",
                "level": 1,
                "hp": 90,
                "max_hp": 90,
                "mp": 55,
                "max_mp": 55,
                "stats": {"wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 4},
                "stat_points": 0,
            }
            warrior_opponent = {
                "id": 2,
                "name": "ВоинБот",
                "type": "warrior",
                "level": 1,
                "hp": 40,
                "max_hp": 40,
                "mp": 50,
                "max_mp": 50,
                "stats": {"strength": 6, "agility": 3, "intuition": 3, "endurance": 4},
                "stat_points": 0,
            }
            comparison.draw(screen, mage_player, warrior_opponent)
            comparison.draw(screen, warrior_opponent, mage_player)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()