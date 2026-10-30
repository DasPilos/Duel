import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from combat.character_stats import BASE_STAT_VALUE, CREATION_FREE_POINTS, creation_stats
from core import settings
from scenes.create_character_scene import CreateCharacterScene
from ui.character_card import CharacterCard
from ui.character_profile import STAT_ROWS


class _FakeSession:
    def __init__(self):
        self.calls = []

    def create_character(self, name, profession_type="warrior", stats=None):
        self.calls.append({"name": name, "profession_type": profession_type, "stats": stats})
        return {"id": 1, "name": name}


def _stat_button_center(scene, profession, stat, delta):
    frame = scene.card_rects[profession]
    index = [row[0] for row in STAT_ROWS].index(stat)
    minus, plus = CharacterCard._stat_control_rects(frame, CharacterCard._stat_row_y(frame, index))
    return (plus if delta > 0 else minus).center


class CreationStatsTests(unittest.TestCase):
    def test_default_creation_gives_base_stats_and_full_free_points(self):
        stats, free = creation_stats()

        self.assertEqual(stats, {
            "strength": 3, "agility": 3, "intuition": 3, "wisdom": 3, "intellect": 3, "endurance": 4,
        })
        self.assertEqual(free, CREATION_FREE_POINTS)

    def test_spent_points_reduce_free_points(self):
        stats, free = creation_stats({"strength": 5, "agility": 4})

        self.assertEqual(stats["strength"], 5)
        self.assertEqual(stats["agility"], 4)
        self.assertEqual(stats["endurance"], 4)
        self.assertEqual(free, 0)

    def test_stat_below_base_is_rejected(self):
        with self.assertRaises(ValueError):
            creation_stats({"strength": BASE_STAT_VALUE - 1})

    def test_more_than_free_points_is_rejected(self):
        with self.assertRaises(ValueError):
            creation_stats({"strength": 7})

    def test_endurance_and_unknown_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            creation_stats({"endurance": 5})


class CreateCharacterSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)

    def setUp(self):
        self.session = _FakeSession()
        self.scene = CreateCharacterScene(self.session)

    def test_cards_fit_the_screen_side_by_side(self):
        rects = list(self.scene.card_rects.values())

        self.assertEqual(len(rects), 4)
        for rect in rects:
            self.assertEqual((rect.width, rect.height), (450, 1000))
            self.assertLessEqual(rect.bottom, settings.HEIGHT)
        self.assertGreaterEqual(rects[0].left, 0)
        self.assertLessEqual(rects[-1].right, settings.WIDTH)
        for left, right in zip(rects, rects[1:]):
            self.assertLess(left.right, right.left)

    def test_free_points_are_capped_per_class(self):
        for _ in range(CREATION_FREE_POINTS + 2):
            self.scene.adjust_stat("warrior", "strength", 1)

        self.assertEqual(self.scene.allocation("warrior")["strength"], BASE_STAT_VALUE + CREATION_FREE_POINTS)
        self.assertEqual(self.scene.free_points("warrior"), 0)
        self.assertEqual(self.scene.free_points("archer"), CREATION_FREE_POINTS)

    def test_stat_cannot_drop_below_base(self):
        self.scene.adjust_stat("mage", "wisdom", -1)

        self.assertEqual(self.scene.allocation("mage")["wisdom"], BASE_STAT_VALUE)

    def test_clicking_plus_selects_class_and_spends_point(self):
        position = _stat_button_center(self.scene, "assassin", "agility", 1)

        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position))

        self.assertEqual(self.scene.profession, "assassin")
        self.assertEqual(self.scene.allocation("assassin")["agility"], BASE_STAT_VALUE + 1)

    def test_endurance_has_no_controls(self):
        frame = self.scene.card_rects["warrior"]
        endurance_index = [row[0] for row in STAT_ROWS].index("endurance")
        row_y = CharacterCard._stat_row_y(frame, endurance_index)

        self.assertIsNone(self.scene.stat_control_at("warrior", CharacterCard._stat_control_rects(frame, row_y)[1].center))

    def test_create_sends_selected_class_allocation(self):
        self.scene.name = "Тест"
        self.scene.profession = "archer"
        self.scene.adjust_stat("archer", "intuition", 1)
        self.scene.adjust_stat("archer", "intuition", 1)

        self.scene.create()

        self.assertTrue(self.scene.finished)
        self.assertEqual(self.session.calls[0]["profession_type"], "archer")
        self.assertEqual(self.session.calls[0]["stats"]["intuition"], BASE_STAT_VALUE + 2)
        self.assertEqual(self.session.calls[0]["stats"], self.scene.allocation("archer"))

    def test_create_requires_name(self):
        self.scene.create()

        self.assertFalse(self.scene.finished)
        self.assertEqual(self.scene.error, "Введите имя персонажа")
        self.assertEqual(self.session.calls, [])

    def test_name_field_is_focused_by_default_and_takes_text(self):
        self.scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="А"))

        self.assertTrue(self.scene.name_focused)
        self.assertEqual(self.scene.name, "А")

    def test_clicking_name_field_focuses_it(self):
        self.scene.name_focused = False

        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=self.scene.name_rect.center))

        self.assertTrue(self.scene.name_focused)

    def test_clicking_outside_name_field_drops_focus_and_ignores_typing(self):
        frame = self.scene.card_rects["mage"]

        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(frame.centerx, frame.y + 300)))
        self.scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Х"))
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE))

        self.assertFalse(self.scene.name_focused)
        self.assertEqual(self.scene.name, "")

    def test_draw_renders_focused_and_unfocused_name_field(self):
        self.scene.draw(self.screen)
        self.scene.name_focused = False
        self.scene.draw(self.screen)

    def test_draw_renders_all_cards(self):
        self.scene.draw(self.screen)


if __name__ == "__main__":
    unittest.main()
