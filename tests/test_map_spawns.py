import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from client.map_editor_state import MapEditorState
from core.map_catalog import catalog_definitions
from server import map_editor, map_worlds
from tests.fixtures import create_test_database, drop_test_database

CATALOG = catalog_definitions()
GROUND = next(item["item_key"] for item in CATALOG if item["kind"] == "ground")


class SpawnStateTests(unittest.TestCase):
    def test_click_adds_then_removes_a_spawn(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        self.assertEqual(state.toggle_spawn(3, 4), "added")
        self.assertEqual(state.toggle_spawn(3, 4), "removed")
        self.assertEqual(state.spawns, [])

    def test_several_spawns_keep_their_order(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.toggle_spawn(1, 1)
        state.toggle_spawn(5, 2)
        self.assertEqual(state.to_spawns(), [{"x": 1, "y": 1}, {"x": 5, "y": 2}])

    def test_spawn_outside_the_map_is_refused(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        self.assertEqual(state.toggle_spawn(16, 0), "Клетка вне карты")

    def test_spawns_are_undoable_and_mark_the_map_dirty(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.mark_saved()
        state.begin_action()
        state.toggle_spawn(2, 2)
        self.assertTrue(state.end_action())
        self.assertTrue(state.dirty)
        state.undo()
        self.assertEqual(state.spawns, [])
        state.redo()
        self.assertEqual(state.spawns, [(2, 2)])

    def test_loading_skips_duplicates_and_points_outside_the_map(self):
        state = MapEditorState(CATALOG, [], 16, 16)
        state.load_spawns([{"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 40, "y": 0}])
        self.assertEqual(state.spawns, [(1, 1)])

    def test_draft_keeps_spawns(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            spawns = [{"x": 3, "y": 4}]
            saved = map_drafts.save_draft("Спаун", [], 16, 16, folder=folder, spawns=spawns)
            self.assertEqual(map_drafts.load_draft(saved["id"], folder)["spawns"], spawns)


class SpawnValidationTests(unittest.TestCase):
    def test_valid_spawns_come_back_as_pairs(self):
        self.assertEqual(map_editor.validate_spawns([{"x": 0, "y": 0}, {"x": 15, "y": 3}], 16, 16), [(0, 0), (15, 3)])
        self.assertEqual(map_editor.validate_spawns(None, 16, 16), [])

    def test_bad_spawns_are_rejected(self):
        for spawns in ([{"x": 16, "y": 0}], [{"x": 1, "y": 1}, {"x": 1, "y": 1}], ["не объект"]):
            with self.assertRaises(ValueError, msg=repr(spawns)):
                map_editor.validate_spawns(spawns, 16, 16)


class SpawnServerTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.admin = self.database.register("spawn-admin", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (self.admin["id"],))
        self.body = {
            "name": "Спаун-карта", "mode": "tower", "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [], "spawns": [{"x": 2, "y": 3}, {"x": 9, "y": 9}],
        }

    def tearDown(self):
        drop_test_database(self.database)

    def test_saved_map_keeps_its_spawns(self):
        saved = map_worlds.save_map(self.database, self.admin["id"], self.body)
        self.assertEqual(self.database.get_saved_map(saved["saved_id"])["spawns"], [{"x": 2, "y": 3}, {"x": 9, "y": 9}])

    def test_test_world_gets_the_spawns_of_its_map(self):
        saved = map_worlds.save_map(self.database, self.admin["id"], self.body)
        world = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": saved["saved_id"]})
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT x, y FROM map_live_spawns WHERE world_id = %s ORDER BY x", (world["world_id"],)).fetchall()
        self.assertEqual([(row["x"], row["y"]) for row in rows], [(2, 3), (9, 9)])

    def test_out_of_map_spawn_is_rejected_and_nothing_is_saved(self):
        with self.assertRaises(ValueError):
            map_worlds.save_map(self.database, self.admin["id"], {**self.body, "spawns": [{"x": 99, "y": 0}]})


class SpawnTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        from scenes.map_editor_scene import MapEditorScene
        self.scene = MapEditorScene(None, CATALOG, lambda: True)
        self.scene.has_map = True

    def test_spawn_tab_is_inside_the_palette_panel(self):
        panel = self.scene.panel_rect()
        spawn_tabs = [rect for section, _label, rect in self.scene._tab_rects() if section == "spawn"]
        self.assertEqual(len(spawn_tabs), 1)
        self.assertTrue(panel.contains(spawn_tabs[0]), (panel, spawn_tabs[0]))

    def test_all_three_tabs_fit_without_overlap(self):
        rects = [rect for _section, _label, rect in self.scene._tab_rects()]
        for index, rect in enumerate(rects):
            self.assertTrue(self.scene.panel_rect().contains(rect), rect)
            for other in rects[index + 1:]:
                self.assertFalse(rect.colliderect(other), (rect, other))

    def test_clicking_a_tile_in_the_spawn_tab_places_a_spawn(self):
        self.scene._set_section("spawn")
        self.scene._grid_primary((4, 5))
        self.assertEqual(self.scene.state.spawns, [(4, 5)])
        self.scene._grid_secondary((4, 5))
        self.assertEqual(self.scene.state.spawns, [])

    def test_the_grid_draws_spawns(self):
        screen = pygame.display.get_surface()
        self.scene._set_section("spawn")
        self.scene._grid_primary((2, 2))
        self.scene.hover = (3, 3)
        self.scene.draw(screen)


if __name__ == "__main__":
    unittest.main()
