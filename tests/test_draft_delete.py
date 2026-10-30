import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from core.map_catalog import catalog_definitions
from scenes.map_editor_scene import MapEditorScene
from scenes.map_editor_ui import DRAFT_HEAD_H, DRAFT_ROW_H, DraftList, _delete_rect, _draft_row


def draft(draft_id, name, active=()):
    return {"id": draft_id, "name": name, "map_w": 64, "map_h": 64, "mode": "tower",
            "updated_at": 1.0, "active_worlds": list(active)}


class DeleteDraftFileTests(unittest.TestCase):
    def test_delete_removes_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            saved = map_drafts.save_draft("Лес", [], 16, 16, folder=folder)
            map_drafts.delete_draft(saved["id"], folder)
            self.assertFalse((folder / f"{saved['id']}.json").exists())
            with self.assertRaises(map_drafts.DraftError):
                map_drafts.load_draft(saved["id"], folder)

    def test_deleting_twice_says_it_is_gone(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(map_drafts.DraftError):
                map_drafts.delete_draft("missing", Path(folder))


class DraftListButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))
        cls.font = pygame.font.SysFont("arial", 16)
        cls.small = pygame.font.SysFont("arial", 13)

    def test_cross_button_belongs_to_its_row_only(self):
        drafts = [draft("a", "Первая"), draft("b", "Вторая")]
        drafts_list = DraftList(self.font, self.small, drafts)
        box = drafts_list.box()
        second_row = _draft_row(box, DRAFT_HEAD_H, 1)
        self.assertIs(drafts_list.delete_at(_delete_rect(second_row).center), drafts[1])
        self.assertIsNone(drafts_list.delete_at(box.center))
        self.assertIsNone(drafts_list.delete_at((second_row.x + 5, second_row.centery)))

    def test_confirm_buttons_answer_delete_or_cancel(self):
        drafts_list = DraftList(self.font, self.small, [draft("a", "Первая")])
        yes, no = drafts_list._confirm_buttons()
        self.assertEqual(drafts_list.confirm_click(yes.center), "delete")
        self.assertEqual(drafts_list.confirm_click(no.center), "cancel")
        self.assertIsNone(drafts_list.confirm_click((0, 0)))

    def test_list_draws_with_confirmation_and_message(self):
        screen = pygame.display.get_surface()
        drafts_list = DraftList(self.font, self.small, [draft("a", "Первая")])
        drafts_list.confirm = drafts_list.drafts[0]
        drafts_list.message = "Карта удалена"
        drafts_list.draw(screen)


class DraftDeleteSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.drafts = [draft("a", "Первая"), draft("b", "Вторая", active=["Башня"])]
        self.scene.draft_list = DraftList(self.scene.font, self.scene.small, self.drafts)

    def click(self, pos):
        self.scene._draft_list_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def cross_of(self, index):
        box = self.scene.draft_list.box()
        return _delete_rect(_draft_row(box, DRAFT_HEAD_H, index)).center

    def test_cross_asks_for_confirmation_first(self):
        with patch.object(map_drafts, "delete_draft") as delete:
            self.click(self.cross_of(0))
            delete.assert_not_called()
        self.assertEqual(self.scene.draft_list.confirm["id"], "a")

    def test_escape_cancels_the_confirmation_but_keeps_the_list(self):
        self.click(self.cross_of(0))
        self.scene._draft_list_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        self.assertIsNone(self.scene.draft_list.confirm)
        self.assertIsNotNone(self.scene.draft_list)

    def test_confirming_deletes_and_refreshes_the_list(self):
        self.click(self.cross_of(0))
        yes, _no = self.scene.draft_list._confirm_buttons()
        remaining = [self.drafts[1]]
        with patch.object(map_drafts, "list_drafts", side_effect=[self.drafts, remaining]), \
                patch.object(map_drafts, "delete_draft") as delete:
            self.click(yes.center)
        delete.assert_called_once_with("a")
        self.assertEqual([item["id"] for item in self.scene.draft_list.drafts], ["b"])
        self.assertIn("удалена", self.scene.draft_list.message)

    def test_published_draft_is_never_deleted(self):
        self.click(self.cross_of(1))
        yes, _no = self.scene.draft_list._confirm_buttons()
        with patch.object(map_drafts, "list_drafts", return_value=self.drafts), \
                patch.object(map_drafts, "delete_draft") as delete:
            self.click(yes.center)
        delete.assert_not_called()
        self.assertIsNone(self.scene.draft_list.confirm)
        self.assertIn("Башня", self.scene.draft_list.message)

    def test_deleting_the_open_draft_detaches_it(self):
        self.scene.draft_id = "a"
        self.click(self.cross_of(0))
        yes, _no = self.scene.draft_list._confirm_buttons()
        with patch.object(map_drafts, "list_drafts", return_value=[self.drafts[1]]), \
                patch.object(map_drafts, "delete_draft"):
            self.click(yes.center)
        self.assertIsNone(self.scene.draft_id)


if __name__ == "__main__":
    unittest.main()
