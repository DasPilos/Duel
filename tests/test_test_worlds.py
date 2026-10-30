import unittest

from core.map_catalog import catalog_definitions
from server import map_worlds
from tests.fixtures import create_test_database, drop_test_database

GROUND = next(item["item_key"] for item in catalog_definitions() if item["kind"] == "ground")


class TestWorldTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.admin = self.database.register("test-admin", "password")
        self.mod = self.database.register("test-mod", "password")
        self.player = self.database.register("test-player", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (self.admin["id"],))
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (self.mod["id"],))
        self.saved = map_worlds.save_map(self.database, self.admin["id"], {
            "name": "Тестовая долина", "mode": "tower", "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [{"kind": "imp_sword", "x": 2, "y": 2}],
        })

    def tearDown(self):
        drop_test_database(self.database)

    def world_ids(self, viewer_id):
        return {world["id"] for world in self.database.list_worlds(viewer_id=viewer_id)}

    def test_admin_creates_a_test_world_from_a_saved_map(self):
        result = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": self.saved["saved_id"], "name": "Проба"})
        self.assertTrue(result["test"])
        self.assertEqual(result["mode"], "tower")
        info = self.database.world_info(result["world_id"])
        self.assertTrue(info["test_only"])
        self.assertEqual(info["name"], "Проба")
        with self.database.connection() as connection:
            published = connection.execute(
                "SELECT mode FROM map_world_publish WHERE world_id = %s", (result["world_id"],)).fetchone()
            mobs = connection.execute(
                "SELECT kind FROM map_live_mobs WHERE world_id = %s", (result["world_id"],)).fetchall()
        self.assertEqual(published["mode"], "tower")
        self.assertEqual([m["kind"] for m in mobs], ["imp_sword"])

    def test_test_world_name_defaults_to_the_saved_map_name(self):
        result = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": self.saved["saved_id"]})
        self.assertEqual(self.database.world_info(result["world_id"])["name"], "Тестовая долина")

    def test_moderator_cannot_create_or_start_test_worlds(self):
        with self.assertRaises(ValueError):
            map_worlds.create_test_world(self.database, self.mod["id"], {"saved_id": self.saved["saved_id"]})
        world = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": self.saved["saved_id"]})
        with self.assertRaises(ValueError):
            map_worlds.start_world(self.database, self.mod["id"], world["world_id"], spawn=lambda *a: None, healthy=lambda u: False)

    def test_test_world_is_hidden_from_players_and_visible_to_moderators_and_admins(self):
        world = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": self.saved["saved_id"]})
        self.assertNotIn(world["world_id"], self.world_ids(self.player["id"]))
        self.assertNotIn(world["world_id"], self.world_ids(None))
        self.assertIn(world["world_id"], self.world_ids(self.mod["id"]))
        self.assertIn(world["world_id"], self.world_ids(self.admin["id"]))

    def test_players_cannot_enter_a_test_world_server(self):
        world = map_worlds.create_test_world(self.database, self.admin["id"], {"saved_id": self.saved["saved_id"]})
        self.database.world_id = world["world_id"]
        self.assertFalse(self.database.can_enter_current_world(self.player["id"]))
        self.assertTrue(self.database.can_enter_current_world(self.mod["id"]))
        self.assertTrue(self.database.can_enter_current_world(self.admin["id"]))

    def test_open_worlds_are_open_to_everyone(self):
        self.assertTrue(self.database.can_enter_current_world(self.player["id"]))
        self.assertIn(1, self.world_ids(self.player["id"]))

    def test_saved_maps_are_listed_for_moderators(self):
        names = [item["name"] for item in self.database.list_saved_maps()]
        self.assertIn("Тестовая долина", names)


if __name__ == "__main__":
    unittest.main()
