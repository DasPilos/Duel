import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_max_hp
from combat.character_stats import stat_support_requirement
from combat.fighter import Fighter
from core import settings
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
    def test_max_hp_formula_matches_level_and_endurance(self):
        self.assertEqual(calculate_max_hp(1, 5), 120)
        self.assertEqual(calculate_max_hp(3, 7), 140)

    def test_assassin_stale_profile_uses_base_hp_plus_endurance(self):
        profile = normalize_character_profile({
            "type": "assassin",
            "level": 1,
            "hp": 67,
            "max_hp": 100,
            "stats": {"endurance": 3},
        })

        self.assertEqual(displayed_hp_values(profile), (30, 45))

    def test_assassin_own_character_stats_show_damage_dodge_and_both_crit_values(self):
        fighter = Fighter("Асасин", profession_type="assassin")

        values = derived_values(profile_from_fighter(fighter))

        self.assertEqual(values["Урон"], 2)
        self.assertEqual(values["Уворот"], "4%")
        self.assertEqual(values["Крит"], "13% × 190%")

    def test_profile_model_normalizes_fighter_and_derived_values(self):
        fighter = Fighter("Тест")
        profile = normalize_character_profile(profile_from_fighter(fighter))

        self.assertEqual(profile["stats"], fighter.stats)
        self.assertEqual(derived_values(profile, fighter), {
            "Урон": 3,
            "Уворот": "4%",
            "Крит": "5% × 160%",
            "HP": fighter.max_hp,
        })

    def test_profile_recovers_weight_when_server_snapshot_has_zero(self):
        profile = normalize_character_profile({
            "id": 1,
            "name": "Носильщик",
            "carried_weight_kg": 0,
            "inventory": {"0": {"weight": 2.5, "quantity": 2}},
            "equipment": {
                "weapon": {"weight": 4},
                "shield": {"weight": 4, "_two_handed_shadow": True},
            },
        })

        self.assertEqual(profile["carried_weight_kg"], 9.0)

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
            {"strength": 2, "agility": 2, "intuition": 2, "endurance": 2},
            6,
            25,
            25,
            1,
            "strength",
            -1,
        )

        self.assertIsNone(state)

    def test_stat_advancement_requires_half_value_in_both_linked_stats(self):
        state = {
            "strength": 9,
            "agility": 4,
            "intuition": 4,
            "wisdom": 2,
            "intellect": 2,
            "harmony": 2,
            "endurance": 2,
        }
        self.assertEqual(stat_support_requirement(10), 5)
        self.assertEqual(stat_support_requirement(20), 10)
        self.assertIsNone(adjust_stats(state, 1, 50, 100, 1, "strength", 1))

        state["agility"] = 5
        state["intuition"] = 5
        updated = adjust_stats(state, 1, 50, 100, 1, "strength", 1)
        self.assertEqual(updated["stats"]["strength"], 10)

        state = {**updated["stats"], "agility": 9, "intuition": 9, "strength": 19}
        self.assertIsNone(adjust_stats(state, 1, 50, 100, 1, "strength", 1))
        state["agility"] = 10
        state["intuition"] = 10
        self.assertEqual(
            adjust_stats(state, 1, 50, 100, 1, "strength", 1)["stats"]["strength"],
            20,
        )

    def test_endurance_minimum_increases_with_character_level(self):
        fighter = Fighter("Тест", level=5)

        self.assertEqual(fighter.stats["endurance"], 6)
        self.assertFalse(fighter.add_stat("endurance"))

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
            strength_row = CharacterCard._stat_row_y(overlay.player_frame, 0)
            _, plus = overlay.player_card._stat_control_rects(overlay.player_frame, strength_row)

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

            self.assertEqual(minus.topleft, (203, 988))
            self.assertEqual(plus.topleft, (222, 988))
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
            panel.messages = [{"id": 1, "sender_id": 2, "sender": "Игрок", "text": "длинное сообщение " * 20}]
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

    def test_tavern_street_exit_navigates_to_city(self):
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
            _, x, y, width, height, action = next(
                hotspot for hotspot in scene.tavern_hotspots if hotspot[0] == "Выход на улицу"
            )
            rect = scene._hotspot_rect(x, y, width, height)
            self.assertEqual(action, "city")
            self.assertEqual(rect, pygame.Rect(160, 400, 130, 300))
            scene.chat.collapsed = True

            scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": rect.center},
            ))

            self.assertTrue(scene.finished)
            self.assertEqual(scene.navigate, "city")
        finally:
            pygame.quit()

    def test_tavern_has_no_map_button_or_map_button_navigation(self):
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
            scene.chat.collapsed = True

            self.assertFalse(hasattr(scene, "map_button"))
            scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": (settings.WIDTH - 135, 35)},
            ))

            self.assertFalse(scene.finished)
            self.assertIsNone(scene.navigate)
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
            strength_row = CharacterCard._stat_row_y(scene.profile_overlay.player_frame, 0)
            _, plus = scene.profile_overlay.player_card._stat_control_rects(
                scene.profile_overlay.player_frame,
                strength_row,
            )

            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))
            scene.draw(pygame.Surface((1920, 1080)))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))

            self.assertEqual(len(session.saved_profiles), 2)
            self.assertEqual(session.saved_profiles[0]["stats"]["strength"], 6)
            self.assertEqual(session.saved_profiles[1]["stats"]["strength"], 7)
        finally:
            pygame.quit()

    def test_derived_values_cross_class_does_not_crash(self):
        warrior = {
            "name": "Воин",
            "type": "warrior",
            "level": 1,
            "max_hp": 40,
            "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
        }
        mage = {
            "name": "Маг",
            "type": "mage",
            "level": 1,
            "max_hp": 90,
            "stats": {"wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 4},
        }

        warrior_values = derived_values(warrior, mage)
        mage_values = derived_values(mage, warrior)
        for values in (warrior_values, mage_values):
            self.assertNotEqual(values["Урон"], "--")
            self.assertNotEqual(values["Уворот"], "--")
            self.assertIn("×", values["Крит"])
        self.assertEqual(warrior_values["HP"], 40)
        self.assertEqual(mage_values["HP"], 90)

    def test_mage_derived_values_include_wisdom_and_weapon_damage(self):
        mage = {
            "name": "Маг",
            "type": "mage",
            "level": 1,
            "max_hp": 90,
            "stats": {
                "strength": 3,
                "agility": 3,
                "intuition": 3,
                "wisdom": 7,
                "endurance": 4,
            },
            "equipment": {
                "weapon": {"effects": {"damage": [2, 4]}},
            },
        }
        warrior = {
            "name": "Воин",
            "type": "warrior",
            "level": 1,
            "max_hp": 40,
            "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
        }

        self.assertEqual(derived_values(mage)["Маг Урон"], "9-11")
        self.assertEqual(derived_values(mage, warrior)["Маг Урон"], "9-11")
        self.assertNotIn("Маг Урон", derived_values(warrior))

    def test_necromancer_derived_values_include_wisdom_damage(self):
        necromancer = {
            "name": "Некромант",
            "type": "necromancer",
            "level": 1,
            "stats": {"wisdom": 7, "endurance": 2},
        }

        self.assertEqual(derived_values(necromancer)["Маг Урон"], 7)

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