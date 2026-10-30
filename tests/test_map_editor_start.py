import unittest

import pygame

from core.map_catalog import catalog_definitions
from scenes.map_editor_scene import MapEditorScene, TOP

ALWAYS_ENABLED = ("new", "drafts", "tower", "exit")


class MapEditorStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.screen = pygame.display.get_surface()

    def click(self, pos):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_editor_starts_without_map(self):
        self.assertFalse(self.scene.has_map)
        self.assertEqual(self.scene.status, "Создайте новую карту или загрузите черновик")

    def test_welcome_screen_draws_without_grid(self):
        self.scene.draw(self.screen)
        self.assertFalse(self.scene.has_map)

    def test_clicks_on_grid_do_not_edit_without_map(self):
        self.click((self.screen.get_width() // 2, TOP + 200))
        self.assertEqual(self.scene.state.ground, {})
        self.assertEqual(self.scene.state.overlay, {})
        self.assertEqual(self.scene.state.objects, {})

    def test_menu_editing_items_are_disabled_without_map(self):
        for _title, items in self.scene._menus():
            for item in items:
                if item.get("separator"):
                    continue
                if item["id"] in ALWAYS_ENABLED:
                    continue
                self.assertFalse(item.get("enabled", True), item["id"])

    def test_new_map_button_opens_size_picker(self):
        command, _label, rect = self.scene._welcome_buttons()[0]
        self.assertEqual(command, "new")
        self.click(rect.center)
        self.assertIsNotNone(self.scene.size_picker)

    def test_server_button_disabled_without_saved_draft(self):
        _label, enabled = self.scene._server_button()
        self.assertFalse(enabled)

    def test_server_button_enabled_for_saved_clean_draft(self):
        self.scene.draft_id = "draft-1"
        self.scene._dirty = lambda: False
        _label, enabled = self.scene._server_button()
        self.assertTrue(enabled)

    def test_cancelled_login_reports_map_not_saved(self):
        self.scene.draft_id = "draft-1"
        self.scene._dirty = lambda: False
        self.scene.save_to_server()
        self.assertIn("Карта не сохранена", self.scene.status)

    def test_server_button_click_saves_to_server(self):
        self.scene.has_map = True
        calls = []
        self.scene.save_to_server = lambda: calls.append(True)
        self.click(self.scene.toolbar.server_rect(self.screen.get_width()).center)
        self.assertEqual(calls, [True])


if __name__ == "__main__":
    unittest.main()
