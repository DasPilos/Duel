import tempfile
import unittest
from pathlib import Path

from kaloda.editor import drafts as map_drafts
from kaloda.editor.catalog import catalog_definitions
from kaloda.server import map_worlds
from tests.kaloda.server_fixtures import create_test_database, drop_test_database

GROUND = next(item["item_key"] for item in catalog_definitions() if item["kind"] == "ground")


class SavedMapTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.moderator = self.database.register("saver-mod", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (self.moderator["id"],))
        self.body = {
            "name": "Горная долина", "mode": "kaloda", "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [{"kind": "kobold", "x": 2, "y": 2}],
        }

    def tearDown(self):
        drop_test_database(self.database)

    def test_saving_stores_the_map_and_creates_no_world(self):
        worlds_before = len(self.database.list_worlds())
        result = map_worlds.save_map(self.database, self.moderator["id"], self.body)
        self.assertEqual(result["name"], "Горная долина")
        self.assertEqual(len(self.database.list_worlds()), worlds_before)
        stored = self.database.get_saved_map(result["saved_id"])
        self.assertEqual(stored["mode"], "kaloda")
        self.assertEqual(stored["cells"], [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}])
        self.assertEqual(stored["mobs"], [{"kind": "kobold", "x": 2, "y": 2}])

    def test_saving_again_updates_the_same_saved_map(self):
        first = map_worlds.save_map(self.database, self.moderator["id"], self.body)
        again = map_worlds.save_map(self.database, self.moderator["id"],
                                    {**self.body, "saved_id": first["saved_id"], "name": "Долина 2"})
        self.assertEqual(again["saved_id"], first["saved_id"])
        self.assertEqual(self.database.get_saved_map(first["saved_id"])["name"], "Долина 2")

    def test_bad_map_is_rejected_and_nothing_is_stored(self):
        bad = {**self.body, "cells": [{"layer": "ground", "x": 999, "y": 0, "key": GROUND}]}
        with self.assertRaises(ValueError):
            map_worlds.save_map(self.database, self.moderator["id"], bad)
        with self.database.connection() as connection:
            count = connection.execute("SELECT COUNT(*) AS n FROM map_saved").fetchone()["n"]
        self.assertEqual(count, 0)

    def test_unknown_mode_and_no_rights_are_rejected(self):
        with self.assertRaises(ValueError):
            map_worlds.save_map(self.database, self.moderator["id"], {**self.body, "mode": "arena"})
        user = self.database.register("plain-user", "password")
        with self.assertRaises(ValueError):
            map_worlds.save_map(self.database, user["id"], self.body)


class DraftServerMapTests(unittest.TestCase):
    def test_the_draft_remembers_its_saved_map_and_keeps_it_on_resave(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            saved = map_drafts.save_draft("Долина", [], 16, 16, folder=folder)
            map_drafts.mark_server_map(saved["id"], 7, "Долина", folder)
            again = map_drafts.save_draft("Долина", [], 16, 16, saved["id"], folder)
            self.assertEqual(again["server_map"], {"saved_id": 7, "saved_name": "Долина"})


if __name__ == "__main__":
    unittest.main()
