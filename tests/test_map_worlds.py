import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from client import map_drafts
from core.map_catalog import catalog_definitions
from server import map_worlds
from tests.fixtures import create_test_database, drop_test_database

GROUND = next(item["item_key"] for item in catalog_definitions() if item["kind"] == "ground")


class FakeProcess:
    def poll(self):
        return None  # процесс работает


class FakeSpawn:
    def __init__(self):
        self.calls = []

    def __call__(self, world_id, port):
        self.calls.append((world_id, port))
        return FakeProcess()


class SavedMapTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.moderator = self.database.register("saver-mod", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (self.moderator["id"],))
        self.body = {
            "name": "Горная долина", "mode": "tower", "map_w": 16, "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [{"kind": "imp_sword", "x": 2, "y": 2}],
        }
        map_worlds._processes.clear()

    def tearDown(self):
        map_worlds._processes.clear()
        drop_test_database(self.database)

    def test_saving_stores_the_map_and_creates_no_world_and_starts_no_server(self):
        worlds_before = len(self.database.list_worlds())
        spawn = FakeSpawn()
        with patch.object(map_worlds, "spawn_world_server", spawn):
            result = map_worlds.save_map(self.database, self.moderator["id"], self.body)
        self.assertEqual(result["name"], "Горная долина")
        self.assertEqual(len(self.database.list_worlds()), worlds_before)
        self.assertEqual(spawn.calls, [])
        stored = self.database.get_saved_map(result["saved_id"])
        self.assertEqual(stored["mode"], "tower")
        self.assertEqual(stored["cells"], [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}])
        self.assertEqual(stored["mobs"], [{"kind": "imp_sword", "x": 2, "y": 2}])

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


class StartWorldTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.moderator = self.database.register("starter-mod", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (self.moderator["id"],))
        map_worlds._processes.clear()

    def tearDown(self):
        map_worlds._processes.clear()
        drop_test_database(self.database)

    def test_start_runs_a_server_for_the_world_once(self):
        world = self.database.create_map_world("Долина", "tower", self.moderator["id"])
        spawn = FakeSpawn()
        first = map_worlds.start_world(self.database, self.moderator["id"], world["id"], spawn=spawn, healthy=lambda u: False)
        self.assertTrue(first["started"])
        self.assertEqual(spawn.calls[0][0], world["id"])
        self.assertIn(spawn.calls[0][1], map_worlds.PORT_RANGE)
        self.assertEqual(self.database.world_info(world["id"])["server_url"], first["server_url"])
        second = map_worlds.start_world(self.database, self.moderator["id"], world["id"], spawn=spawn, healthy=lambda u: False)
        self.assertFalse(second["started"])
        self.assertEqual(len(spawn.calls), 1)

    def test_only_moderators_can_start_a_world(self):
        world = self.database.create_map_world("Долина", "tower", self.moderator["id"])
        user = self.database.register("plain-user-2", "password")
        with self.assertRaises(ValueError):
            map_worlds.start_world(self.database, user["id"], world["id"], spawn=FakeSpawn(), healthy=lambda u: False)

    def test_free_port_skips_used_and_busy_ports(self):
        busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        busy.bind(("127.0.0.1", 0))  # порт, который выбрала ОС, занят
        taken = busy.getsockname()[1]
        try:
            with patch.object(map_worlds, "PORT_RANGE", range(taken, taken + 3)):
                self.assertEqual(map_worlds.free_port({taken + 1}), taken + 2)
        finally:
            busy.close()


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
