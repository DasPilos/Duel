import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_max_hp
from combat.fighter import Fighter
from core import settings
from scenes.tavern_scene import TavernScene
from ui.chat.panel import ChatPanel
from ui.character_card import CharacterCard
from ui.character_profile import derived_values, normalize_character_profile, profile_from_fighter
from ui.character_profile_overlay import CharacterProfileOverlay


class CharacterStatTests(unittest.TestCase):
    def test_max_hp_formula_matches_level_and_endurance(self):
        self.assertEqual(calculate_max_hp(1, 5), 50)
        self.assertEqual(calculate_max_hp(3, 7), 70)

    def test_profile_model_normalizes_fighter_and_derived_values(self):
        fighter = Fighter("Тест")
        profile = normalize_character_profile(profile_from_fighter(fighter))

        self.assertEqual(profile["stats"], fighter.stats)
        self.assertEqual(derived_values(profile, fighter), {
            "Урон": 4,
            "Уворот": "6%",
            "Крит": "6%",
            "HP": 40,
        })

    def test_endurance_increase_preserves_gained_health(self):
        state = adjust_stats(
            {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            20,
            25,
            1,
            "endurance",
            1,
        )

        self.assertEqual(state["max_hp"], 60)
        self.assertEqual(state["hp"], 55)
        self.assertEqual(state["stat_points"], 5)

    def test_stat_decrease_cannot_go_below_minimum(self):
        state = adjust_stats(
            {"strength": 4, "agility": 5, "intuition": 5, "endurance": 5},
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

            self.assertTrue(fighter.add_stat("endurance"))
            self.assertTrue(card.adjust_stat("endurance", 1))
            self.assertEqual(card.data["stats"], fighter.stats)
            self.assertEqual(card.data["stat_points"], fighter.stat_points)
            self.assertEqual(card.data["hp"], fighter.hp)
            self.assertEqual(card.data["max_hp"], fighter.max_hp)
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
                overlay.player_frame.bottom - 92,
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
            self.assertEqual(panel.panel_rect.left, 526)
            self.assertEqual(panel.panel_rect.right, 1394)

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
                scene.profile_overlay.player_frame.bottom - 92,
            )

            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))
            scene.draw(pygame.Surface((1920, 1080)))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))

            self.assertEqual(len(session.saved_profiles), 2)
            self.assertEqual(session.saved_profiles[0]["stats"]["strength"], 6)
            self.assertEqual(session.saved_profiles[1]["stats"]["strength"], 7)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()