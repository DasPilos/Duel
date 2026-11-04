import unittest
from unittest.mock import patch

from client.network import ServerError
from core.map_catalog import catalog_definitions
from kaloda.map_config import MAP_VERSION, MAP_WIDTH_TILES
from kaloda.server import map_worlds
from kaloda.server.database import Database
from tests.kaloda.server_fixtures import create_second_world, create_test_database, drop_test_database, running_server

CATALOG = catalog_definitions()
GRASS = next(i["item_key"] for i in CATALOG if i["kind"] == "ground" and i["category"] == "grass" and not i["blocks"])
WATER = next(i["item_key"] for i in CATALOG if i["kind"] == "ground" and i["category"] == "water")
TREE = next(i["item_key"] for i in CATALOG if i["kind"] == "object" and i["category"] == "tree")
# Мир Оператора 1 из миграций общей схемы: в нём Колода не публикует карт
OPERATOR_1_WORLD_ID = 1


def map_body(**changes):
    body = {
        "name": "Долина", "mode": "kaloda", "map_w": 16, "map_h": 16,
        "cells": [
            {"layer": "ground", "x": 0, "y": 0, "key": GRASS},
            {"layer": "ground", "x": 2, "y": 2, "key": WATER},
            {"layer": "object", "x": 5, "y": 5, "key": TREE},
        ],
        "mobs": [{"kind": "imp_sword", "x": 3, "y": 3}],
        "spawns": [{"x": 1, "y": 1}],
    }
    body.update(changes)
    return body


def publish_body(world_id, **changes):
    return {**map_body(), "world_id": world_id, **changes}


class MapServerTestCase(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.register_with_role("map-moderator", "moderator")
        self.database.register("map-player", "password")

    def tearDown(self):
        drop_test_database(self.database)

    def register_with_role(self, username, role):
        user = self.database.register(username, "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
        return user

    def test_only_moderators_save_and_publish_maps(self):
        with running_server(self.database) as client:
            client.login("map-player", "password")
            with self.assertRaisesRegex(ServerError, "Недостаточно прав модератора"):
                client._kaloda("POST", "/map/editor/saved", map_body())
            with self.assertRaisesRegex(ServerError, "Недостаточно прав модератора"):
                client._kaloda("GET", "/map/saved?mode=kaloda")
            with self.assertRaisesRegex(ServerError, "Недостаточно прав модератора"):
                client._kaloda("POST", "/map/editor/publish", publish_body(self.database.world_id))

            client.login("map-moderator", "password")
            saved = client._kaloda("POST", "/map/editor/saved", map_body())
            published = client._kaloda("POST", "/map/editor/publish", publish_body(self.database.world_id))

        self.assertEqual(saved["name"], "Долина")
        self.assertEqual(saved["mode"], "kaloda")
        self.assertEqual(published["world_id"], self.database.world_id)
        self.assertEqual((published["applied"], published["mobs"]), (3, 1))

    def test_saved_maps_are_listed_per_mode_and_resaving_keeps_the_entry(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            saved = client._kaloda("POST", "/map/editor/saved", map_body())
            again = client._kaloda("POST", "/map/editor/saved", map_body(saved_id=saved["saved_id"], name="Долина 2"))
            with self.assertRaisesRegex(ServerError, "Неизвестный режим игры"):
                client._kaloda("POST", "/map/editor/saved", map_body(mode="tower"))
            listed = client._kaloda("GET", "/map/saved?mode=kaloda")["saved_maps"]
            other_mode = client._kaloda("GET", "/map/saved?mode=tower")["saved_maps"]

        self.assertEqual(again["saved_id"], saved["saved_id"])
        self.assertEqual([(item["id"], item["name"]) for item in listed], [(saved["saved_id"], "Долина 2")])
        self.assertEqual(other_mode, [])

    def test_bad_map_is_rejected_and_nothing_is_stored(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            with self.assertRaisesRegex(ServerError, "выходит за край карты"):
                client._kaloda("POST", "/map/editor/saved", map_body(cells=[{"layer": "ground", "x": 99, "y": 0, "key": GRASS}]))
            self.assertEqual(client._kaloda("GET", "/map/saved?mode=kaloda")["saved_maps"], [])

    def test_published_map_becomes_the_terrain_of_its_world(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            client._kaloda("POST", "/map/editor/publish", publish_body(self.database.world_id))
            terrain = client.get_map_terrain()

        self.assertEqual(terrain["map_version"], MAP_VERSION)
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (16, 16))
        self.assertEqual(terrain["published"]["name"], "Долина")
        self.assertEqual(terrain["published"]["mode"], "kaloda")
        self.assertIn([2, 2], terrain["tiles"]["water"])
        self.assertIn([5, 5], terrain["tiles"]["forest"])
        self.assertEqual(terrain["objects"], [])
        self.assertEqual(terrain["tiles"]["paths"], [])

    def test_world_without_a_published_map_keeps_the_code_terrain(self):
        other = create_second_world(self.database)
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            client._kaloda("POST", "/map/editor/publish", publish_body(self.database.world_id))
        with running_server(other) as client:
            client.login("map-player", "password")
            terrain = client.get_map_terrain()

        self.assertNotIn("published", terrain)
        self.assertEqual(terrain["width_tiles"], MAP_WIDTH_TILES)
        self.assertEqual(terrain["objects"][0]["id"], "crystal_of_life")

    def test_maps_are_published_only_into_kaloda_worlds(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            with self.assertRaisesRegex(ServerError, "не принадлежит Колоде"):
                client._kaloda("POST", "/map/editor/publish", publish_body(OPERATOR_1_WORLD_ID))
            with self.assertRaisesRegex(ServerError, "Мир не найден"):
                client._kaloda("POST", "/map/editor/publish", publish_body(987654))

    def test_resaving_a_published_saved_map_republishes_its_worlds(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            saved = client._kaloda("POST", "/map/editor/saved", map_body())
            client._kaloda(
                "POST", "/map/editor/publish", publish_body(self.database.world_id, saved_id=saved["saved_id"]),
            )
            moved = map_body(cells=[{"layer": "ground", "x": 7, "y": 7, "key": WATER}], saved_id=saved["saved_id"])
            result = client._kaloda("POST", "/map/editor/saved", moved)
            terrain = client.get_map_terrain()

        self.assertEqual(result["world_errors"], [])
        self.assertIn([7, 7], terrain["tiles"]["water"])
        self.assertNotIn([2, 2], terrain["tiles"]["water"])

    def test_only_an_admin_creates_test_worlds_and_only_staff_see_or_enter_them(self):
        self.register_with_role("map-admin", "admin")
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            saved = client._kaloda("POST", "/map/editor/saved", map_body())
            with self.assertRaisesRegex(ServerError, "Создавать миры может только админ"):
                client._kaloda("POST", "/map/editor/test-world", {"saved_id": saved["saved_id"]})

            client.login("map-admin", "password")
            created = client._kaloda(
                "POST", "/map/editor/test-world", {"saved_id": saved["saved_id"], "name": "Тестовая долина"},
            )
            admin_ids = [item["id"] for item in client._kaloda("GET", "/worlds")["worlds"]]

            client.login("map-player", "password")
            with self.assertRaisesRegex(ServerError, "Создавать миры может только админ"):
                client._kaloda("POST", "/map/editor/test-world", {"saved_id": saved["saved_id"]})
            player_ids = [item["id"] for item in client._kaloda("GET", "/worlds")["worlds"]]

        world_id = created["world_id"]
        info = self.database.world_info(world_id)
        self.assertTrue(info["code"].startswith("kaloda"))
        self.assertEqual((info["mode"], info["test_only"]), ("kaloda", True))
        self.assertEqual((created["name"], created["mode"], created["test"]), ("Тестовая долина", "kaloda", True))
        self.assertEqual(created["status"], {"world_id": world_id, "server_url": None, "served_here": False})
        self.assertEqual(admin_ids, [self.database.world_id, world_id])
        self.assertEqual(player_ids, [self.database.world_id])

        test_world = Database(
            self.database.dsn, schema=self.database.schema,
            shared_schema=self.database.shared_schema, world_id=world_id,
        )
        with running_server(test_world) as client:
            with self.assertRaisesRegex(ServerError, "тестовый"):
                client.login("map-player", "password")
            client.login("map-moderator", "password")
            self.assertEqual(client._kaloda("GET", "/info")["world_id"], world_id)

    def test_a_test_world_that_fails_to_publish_is_removed(self):
        admin = self.register_with_role("map-admin", "admin")
        saved_id = self.database.save_saved_map(
            0, "Долина", "kaloda", 16, 16, [{"layer": "ground", "x": 0, "y": 0, "key": GRASS}], [], admin["id"],
        )
        worlds_before = [item["id"] for item in self.database.list_worlds(viewer_id=admin["id"])]
        with patch.object(Database, "publish_map", side_effect=ValueError("Карта не прошла проверку")):
            with self.assertRaisesRegex(ValueError, "не прошла проверку"):
                map_worlds.create_test_world(self.database, admin["id"], {"saved_id": saved_id})
        self.assertEqual([item["id"] for item in self.database.list_worlds(viewer_id=admin["id"])], worlds_before)

    def test_map_tables_and_catalog_live_in_the_game_schema(self):
        with self.database.connection() as connection:
            tables = {
                row["table_name"]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (self.database.schema,),
                )
            }
            catalog_size = connection.execute(
                f'SELECT COUNT(*) AS amount FROM "{self.database.schema}".map_catalog'
            ).fetchone()["amount"]
        for table in ("map_catalog", "map_live_cells", "map_live_mobs", "map_live_spawns", "map_saved", "map_world_publish"):
            self.assertIn(table, tables)
        self.assertEqual(catalog_size, len(CATALOG))

    def test_map_routes_accept_bodies_above_the_game_limit(self):
        with running_server(self.database) as client:
            client.login("map-moderator", "password")
            saved = client._kaloda("POST", "/map/editor/saved", {**map_body(), "padding": "x" * (100 * 1024)})
        self.assertIn("saved_id", saved)


if __name__ == "__main__":
    unittest.main()
