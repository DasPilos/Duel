import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client.network import ServerError
from ui.world_creation_dialog import VISIBLE_ROWS, WorldCreateDialog


class FakeClient:
    def __init__(self):
        self.maps = {"tower": [{"id": 1, "name": "Долина", "map_w": 64, "map_h": 64},
                               {"id": 2, "name": "Лес", "map_w": 125, "map_h": 125}]}
        self.created = []
        self.started = []
        self.fail_create = False

    def list_saved_maps(self, mode=None):
        return list(self.maps.get(mode, []))

    def create_world(self, saved_id, name, test=True):
        if self.fail_create:
            raise ServerError("карта повреждена")
        world = {"world_id": 10, "name": name}
        self.created.append((saved_id, name, test))
        return world

    def start_world(self, world_id):
        self.started.append(world_id)
        return {"world_id": world_id, "started": True}


def click(dialog, pos):
    dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def type_text(dialog, text):
    dialog.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=text))


def type_name(dialog, text):
    click(dialog, dialog.name_rect().center)  # поле названия получает ввод только после клика по нему
    type_text(dialog, text)


class WorldCreateDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))
        cls.font = pygame.font.SysFont("arial", 16)
        cls.small = pygame.font.SysFont("arial", 13)

    def setUp(self):
        self.client = FakeClient()
        self.dialog = WorldCreateDialog(self.client, self.font, self.small, pygame.Rect(0, 0, 1920, 1080))

    def test_lists_the_maps_of_the_default_mode(self):
        self.assertEqual([m["name"] for m in self.dialog.maps], ["Долина", "Лес"])

    def test_choosing_a_map_and_creating_a_test_world(self):
        type_name(self.dialog, "Проба")
        click(self.dialog, self.dialog.row_rect(1).center)
        self.assertEqual(self.dialog.saved_id, 2)
        click(self.dialog, self.dialog.create_rect().center)
        self.assertEqual(self.client.created, [(2, "Проба", True)])
        self.assertIsNotNone(self.dialog.created_world)
        self.assertIn("создан", self.dialog.message)

    def test_test_flag_can_be_turned_off(self):
        click(self.dialog, self.dialog.test_rect().center)
        self.assertFalse(self.dialog.test)
        type_name(self.dialog, "Открытый")
        click(self.dialog, self.dialog.row_rect(0).center)
        click(self.dialog, self.dialog.create_rect().center)
        self.assertEqual(self.client.created, [(1, "Открытый", False)])

    def test_name_and_map_are_required(self):
        click(self.dialog, self.dialog.row_rect(0).center)
        click(self.dialog, self.dialog.create_rect().center)
        self.assertIn("название", self.dialog.message)
        type_name(self.dialog, "Мир")
        self.dialog.saved_id = None
        click(self.dialog, self.dialog.create_rect().center)
        self.assertIn("карту", self.dialog.message)
        self.assertEqual(self.client.created, [])

    def test_start_needs_a_created_world_then_starts_it(self):
        click(self.dialog, self.dialog.start_rect().center)
        self.assertEqual(self.client.started, [])
        type_name(self.dialog, "Мир")
        click(self.dialog, self.dialog.row_rect(0).center)
        click(self.dialog, self.dialog.create_rect().center)
        click(self.dialog, self.dialog.start_rect().center)
        self.assertEqual(self.client.started, [10])
        self.assertIn("запускается", self.dialog.message)

    def test_changing_the_mode_reloads_maps_and_clears_selection(self):
        self.client.maps["forest"] = [{"id": 5, "name": "Чаща", "map_w": 16, "map_h": 16}]
        click(self.dialog, self.dialog.row_rect(0).center)
        self.assertEqual(self.dialog.saved_id, 1)
        self.dialog.mode = "tower"
        self.dialog.mode = "forest"
        self.dialog.refresh_maps()
        self.assertIsNone(self.dialog.saved_id)
        self.assertEqual([m["name"] for m in self.dialog.maps], ["Чаща"])

    def test_server_error_is_shown_not_raised(self):
        self.client.fail_create = True
        type_name(self.dialog, "Мир")
        click(self.dialog, self.dialog.row_rect(0).center)
        click(self.dialog, self.dialog.create_rect().center)
        self.assertIn("карта повреждена", self.dialog.message)

    def test_escape_closes_and_the_dialog_draws(self):
        self.dialog.draw(pygame.display.get_surface())
        self.dialog.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        self.assertTrue(self.dialog.finished)

    def test_long_map_lists_scroll(self):
        self.client.maps["tower"] = [{"id": i, "name": f"Карта {i}", "map_w": 16, "map_h": 16} for i in range(VISIBLE_ROWS + 3)]
        self.dialog.refresh_maps()
        self.dialog.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-2))
        self.assertEqual(self.dialog.scroll, 2)


if __name__ == "__main__":
    unittest.main()
