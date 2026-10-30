import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client.network import ServerError
from client.server_maps import list_server_maps, upload_server_map
from ui.world_creation_dialog import WorldCreateDialog


def write_map(folder, name, mode="tower", **extra):
    data = {"name": name, "mode": mode, "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": "k"}], "mobs": [], "spawns": [], **extra}
    (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class ServerMapFolderTests(unittest.TestCase):
    def test_lists_valid_maps_and_skips_broken_files(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            write_map(folder, "Долина", mode="forest")
            (folder / "сломан.json").write_text("{не json", encoding="utf-8")
            (folder / "чужой.json").write_text('{"name": "x"}', encoding="utf-8")
            maps = list_server_maps(folder)
            self.assertEqual([(m["name"], m["mode"]) for m in maps], [("Долина", "forest")])

    def test_missing_folder_gives_an_empty_list(self):
        self.assertEqual(list_server_maps(Path("no-such-folder-xyz")), [])


class FakeClient:
    def __init__(self):
        self.saved = []
        self.maps = {"tower": [], "forest": [{"id": 9, "name": "Чаща", "map_w": 16, "map_h": 16}]}
        self.fail = False

    def save_saved_map(self, cells, map_w, map_h, name, mode, mobs=(), saved_id=None, spawns=()):
        if self.fail:
            raise ServerError("карта повреждена")
        self.saved.append((name, mode, mobs, spawns))
        self.maps.setdefault(mode, []).append({"id": 42, "name": name, "map_w": map_w, "map_h": map_h})
        return {"saved_id": 42, "name": name, "mode": mode}

    def list_saved_maps(self, mode=None):
        return list(self.maps.get(mode, []))


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.client = FakeClient()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        write_map(Path(self.folder.name), "Лесная карта", mode="forest", mobs=[{"kind": "imp_sword", "x": 1, "y": 1}])
        self.entries = list_server_maps(Path(self.folder.name))
        self.dialog = WorldCreateDialog(self.client, pygame.font.SysFont("arial", 16), pygame.font.SysFont("arial", 13),
                                        pygame.display.get_surface().get_rect())
        self.dialog.server_maps = lambda: self.entries

    def test_upload_sends_the_map_with_its_mobs_and_mode(self):
        upload_server_map(self.client, self.entries[0])
        name, mode, mobs, spawns = self.client.saved[0]
        self.assertEqual((name, mode), ("Лесная карта", "forest"))
        self.assertEqual(mobs, [{"kind": "imp_sword", "x": 1, "y": 1}])

    def test_upload_button_opens_the_picker_and_a_row_uploads_the_map(self):
        self.dialog._click(self.dialog.upload_rect().center)
        self.assertEqual(len(self.dialog.picking), 1)
        self.dialog._click(self.dialog.picker_row_rect(0).center)
        self.assertIsNone(self.dialog.picking)
        self.assertEqual(self.dialog.mode, "forest")  # режим окна стал режимом карты
        self.assertEqual(self.dialog.saved_id, 42)
        self.assertIn("загружена", self.dialog.message)

    def test_escape_leaves_the_picker_before_closing_the_dialog(self):
        self.dialog._click(self.dialog.upload_rect().center)
        self.dialog.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        self.assertIsNone(self.dialog.picking)
        self.assertFalse(self.dialog.finished)

    def test_back_button_closes_the_picker(self):
        self.dialog._click(self.dialog.upload_rect().center)
        self.dialog._click(self.dialog.picker_back_rect().center)
        self.assertIsNone(self.dialog.picking)

    def test_server_error_is_shown_and_nothing_is_selected(self):
        self.client.fail = True
        self.dialog._click(self.dialog.upload_rect().center)
        self.dialog._click(self.dialog.picker_row_rect(0).center)
        self.assertIn("карта повреждена", self.dialog.message)
        self.assertIsNone(self.dialog.saved_id)

    def test_empty_folder_says_what_to_do(self):
        self.entries[:] = []
        self.dialog._click(self.dialog.upload_rect().center)
        self.assertIn("maps_for_server", self.dialog.message)

    def test_picker_draws(self):
        self.dialog._click(self.dialog.upload_rect().center)
        self.dialog.draw(pygame.display.get_surface())


if __name__ == "__main__":
    unittest.main()
