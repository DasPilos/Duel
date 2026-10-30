import time
import unittest

from client.network import ServerError
from tests.fixtures import create_test_database, drop_test_database, running_server


class WorldsAndLobbyTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        with self.database.connection() as connection:
            self.world_ids = [row["id"] for row in connection.execute("SELECT id FROM worlds ORDER BY id").fetchall()]

    def tearDown(self):
        drop_test_database(self.database)

    def _set_world(self, world_id, status="open", opens_at=None, closes_at=None, server_url=None):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE worlds SET status = %s, opens_at = %s, closes_at = %s, server_url = %s WHERE id = %s",
                (status, opens_at, closes_at, server_url, world_id),
            )

    def test_list_worlds_marks_open_and_closed_worlds(self):
        now = time.time()
        first, second, third = self.world_ids[:3]
        self._set_world(first, opens_at=now - 60, closes_at=now + 3600, server_url="http://127.0.0.1:9001")
        self._set_world(second, status="closed")
        self._set_world(third, closes_at=now - 1)

        worlds = {world["id"]: world for world in self.database.list_worlds(now=now)}

        self.assertTrue(worlds[first]["is_open"])
        self.assertEqual(worlds[first]["server_url"], "http://127.0.0.1:9001")
        self.assertFalse(worlds[second]["is_open"])
        self.assertFalse(worlds[third]["is_open"])

    def test_list_worlds_closes_world_before_opening_time(self):
        now = time.time()
        world_id = self.world_ids[0]
        self._set_world(world_id, opens_at=now + 600)

        worlds = {world["id"]: world for world in self.database.list_worlds(now=now)}

        self.assertFalse(worlds[world_id]["is_open"])
        self.assertIsNone(worlds[world_id]["server_url"])

    def test_lobby_lists_recent_accounts_across_worlds_once(self):
        now = time.time()
        self.database.register("lobby-b", "password")
        self.database.register("lobby-a", "password")
        self.database.register("lobby-stale", "password")
        self.database.login("lobby-a", "password")
        self.database.login("lobby-a", "password")
        self.database.login("lobby-b", "password")
        stale_login = self.database.login("lobby-stale", "password")
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE sessions SET last_seen_at = %s WHERE token = %s",
                (now - 120, stale_login["token"]),
            )

        players = self.database.lobby_members(now=now)

        self.assertEqual([player["username"] for player in players], ["lobby-a", "lobby-b"])

    def test_worlds_and_lobby_routes_require_authorization(self):
        with running_server(self.database) as client:
            with self.assertRaises(ServerError):
                client.list_worlds()
            with self.assertRaises(ServerError):
                client.list_lobby()

    def test_worlds_and_lobby_routes_return_data_for_logged_in_player(self):
        now = time.time()
        first = self.world_ids[0]
        self._set_world(first, opens_at=now - 60, closes_at=now + 3600, server_url="http://127.0.0.1:9002")
        with running_server(self.database) as client:
            client.register("route-player", "password")
            client.login("route-player", "password")

            worlds = client.list_worlds()
            lobby = client.list_lobby()

        world = next(item for item in worlds if item["id"] == first)
        self.assertTrue(world["is_open"])
        self.assertEqual(world["server_url"], "http://127.0.0.1:9002")
        self.assertIn("route-player", [player["username"] for player in lobby])


if __name__ == "__main__":
    unittest.main()
