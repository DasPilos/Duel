import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from client.map_editor_state import MapEditorState
from core.map_catalog import catalog_definitions
from server import map_editor
from tests.fixtures import create_test_database, drop_test_database

KIND = "imp_sword"
OTHER = "imp_pitchfork"


def fresh_state(w=16, h=16):
    return MapEditorState(catalog_definitions(), [], w, h)


class MobStateTests(unittest.TestCase):
    def test_one_mob_per_tile_and_new_one_replaces_the_old(self):
        state = fresh_state()
        self.assertIsNone(state.place_mob(KIND, 2, 3))
        self.assertIsNone(state.place_mob(OTHER, 2, 3))
        self.assertEqual(state.mobs, {(2, 3): OTHER})

    def test_erase_and_bounds_and_unknown_kind(self):
        state = fresh_state()
        state.place_mob(KIND, 1, 1)
        self.assertTrue(state.erase_mob(1, 1))
        self.assertFalse(state.erase_mob(1, 1))
        self.assertIsNotNone(state.place_mob(KIND, 16, 0))
        self.assertIsNotNone(state.place_mob("skeleton", 0, 0))
        self.assertEqual(state.mobs, {})

    def test_placing_is_undoable_and_marks_the_map_dirty(self):
        state = fresh_state()
        state.mark_saved()
        state.begin_action()
        state.place_mob(KIND, 4, 4)
        self.assertTrue(state.end_action())
        self.assertTrue(state.dirty)
        state.undo()
        self.assertEqual(state.mobs, {})
        state.redo()
        self.assertEqual(state.mobs, {(4, 4): KIND})

    def test_to_mobs_is_sorted_row_by_row_and_round_trips(self):
        state = fresh_state()
        state.place_mob(KIND, 5, 2)
        state.place_mob(OTHER, 1, 2)
        state.place_mob(KIND, 0, 0)
        mobs = state.to_mobs()
        self.assertEqual(mobs, [
            {"kind": KIND, "x": 0, "y": 0},
            {"kind": OTHER, "x": 1, "y": 2},
            {"kind": KIND, "x": 5, "y": 2},
        ])
        loaded = fresh_state()
        loaded.load_mobs(mobs + [{"kind": "ghost", "x": 1, "y": 1}, {"kind": KIND, "x": 99, "y": 0}])
        self.assertEqual(loaded.to_mobs(), mobs)

    def test_replacing_the_map_clears_mobs(self):
        state = fresh_state()
        state.place_mob(KIND, 1, 1)
        state.replace_cells([])
        self.assertEqual(state.mobs, {})


class MobDraftTests(unittest.TestCase):
    def test_draft_keeps_mobs_and_older_drafts_have_none(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            mobs = [{"kind": KIND, "x": 3, "y": 4}]
            saved = map_drafts.save_draft("Лес", [], 16, 16, folder=folder, mode="tower", mobs=mobs)
            self.assertEqual(map_drafts.load_draft(saved["id"], folder)["mobs"], mobs)
            old = folder / "old.json"
            old.write_text('{"id": "old", "name": "Старая", "map_w": 16, "map_h": 16, "updated_at": 1, '
                           '"cells": [], "published": []}', encoding="utf-8")
            self.assertEqual(map_drafts.load_draft("old", folder).get("mobs", []), [])


class MapEditorValidationTests(unittest.TestCase):
    def test_valid_mobs_come_back_as_tuples(self):
        mobs = [{"kind": KIND, "x": 0, "y": 0}, {"kind": OTHER, "x": 15, "y": 15}]
        self.assertEqual(map_editor.validate_mobs(mobs, 16, 16), [(KIND, 0, 0), (OTHER, 15, 15)])
        self.assertEqual(map_editor.validate_mobs(None, 16, 16), [])

    def test_bad_mobs_are_rejected(self):
        bad_cases = [
            [{"kind": "skeleton", "x": 0, "y": 0}],  # нет в каталоге NPC
            [{"kind": KIND, "x": 16, "y": 0}],  # за краем карты
            [{"kind": KIND, "x": 1, "y": 1}, {"kind": OTHER, "x": 1, "y": 1}],  # два беса на клетке
            ["не объект"],
            {"kind": KIND},
        ]
        for mobs in bad_cases:
            with self.assertRaises(ValueError, msg=repr(mobs)):
                map_editor.validate_mobs(mobs, 16, 16)


class MapEditorMobSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        from scenes.map_editor_scene import MapEditorScene
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene._set_section("npc")
        self.scene.selected_npc = KIND

    def test_click_places_the_selected_mob_and_right_click_removes_it(self):
        self.scene._grid_primary((3, 4))
        self.assertEqual(self.scene.state.mobs, {(3, 4): KIND})
        self.scene._grid_secondary((3, 4))
        self.assertEqual(self.scene.state.mobs, {})

    def test_click_without_a_selected_mob_only_warns(self):
        self.scene.selected_npc = None
        self.scene._grid_primary((1, 1))
        self.assertEqual(self.scene.state.mobs, {})
        self.assertIn("Сначала выберите беса", self.scene.status)

    def test_ctrl_z_takes_the_mob_back(self):
        self.scene._grid_primary((2, 2))
        self.scene.undo()
        self.assertEqual(self.scene.state.mobs, {})

    def test_the_grid_draws_mobs_and_the_hover_ghost(self):
        screen = pygame.display.get_surface()
        self.scene._grid_primary((2, 2))
        self.scene.hover = (2, 2)
        self.scene.draw(screen)
        self.scene.section = "map"
        self.scene.draw(screen)


class MapMobPublishTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.moderator = self.database.register("mob-mod", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (self.moderator["id"],))
        ground = next(item["item_key"] for item in catalog_definitions() if item["kind"] == "ground")
        self.grass = [{"layer": "ground", "x": 0, "y": 0, "key": ground}]

    def tearDown(self):
        drop_test_database(self.database)

    def publish(self, mobs, **extra):
        return self.database.publish_map(
            self.grass, self.database.world_id, "Карта", 16, 16, self.moderator["id"], mobs=mobs, **extra
        )

    def test_publish_stores_mobs_and_mode(self):
        mobs = [{"kind": KIND, "x": 1, "y": 2}, {"kind": OTHER, "x": 3, "y": 4}]
        result = self.publish(mobs)
        self.assertEqual(result["mobs"], 2)
        self.assertEqual(result["mode"], "tower")
        self.assertEqual(self.database.map_live_mobs(), [
            {"kind": KIND, "x": 1, "y": 2}, {"kind": OTHER, "x": 3, "y": 4},
        ])
        self.assertEqual(self.database.published_map()["mode"], "tower")

    def test_publish_replaces_previous_mobs(self):
        self.publish([{"kind": KIND, "x": 1, "y": 2}])
        self.publish([{"kind": OTHER, "x": 7, "y": 7}])
        self.assertEqual(self.database.map_live_mobs(), [{"kind": OTHER, "x": 7, "y": 7}])

    def test_invalid_mobs_keep_the_previous_publication(self):
        self.publish([{"kind": KIND, "x": 1, "y": 2}])
        with self.assertRaises(ValueError):
            self.publish([{"kind": "skeleton", "x": 0, "y": 0}])
        self.assertEqual(self.database.map_live_mobs(), [{"kind": KIND, "x": 1, "y": 2}])

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.publish([], mode="arena")

    def test_publish_without_mobs_clears_them(self):
        self.publish([{"kind": KIND, "x": 1, "y": 2}])
        self.publish(None)
        self.assertEqual(self.database.map_live_mobs(), [])


if __name__ == "__main__":
    unittest.main()
