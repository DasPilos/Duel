import unittest
import uuid

import psycopg
from psycopg import sql

from kaloda.client import KalodaClient
from kaloda.server.database import Database as KalodaDatabase
from kaloda.server.main import bind_database as bind_kaloda_database
from tests.fixtures import TEST_DATABASE_URL, create_test_database, drop_test_database, running_server


class WorldLobbyApiTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def test_worlds_lobby_and_account_routes(self):
        with running_server(self.database) as client:
            client.register("lobbyuser", "password")
            client.login("lobbyuser", "password")

            self.assertEqual(client.get_me()["username"], "lobbyuser")
            self.assertEqual(client.list_lobby()[0]["username"], "lobbyuser")

            self.database.set_world_server(1, "http://127.0.0.1:8765")
            world = next(world for world in client.list_worlds() if world["id"] == 1)
            self.assertTrue(world["is_open"])
            self.assertEqual(world["server_url"], "http://127.0.0.1:8765")
            kaloda = next(world for world in client.list_worlds() if world["id"] == 5)
            self.assertEqual(kaloda["code"], "kaloda1")

    def test_kaloda_login_creates_a_world_scoped_session(self):
        schema = f"kaloda_test_{uuid.uuid4().hex[:12]}"
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

        cards = None
        previous_binding = None
        try:
            cards = KalodaDatabase(
                dsn=self.database.dsn,
                schema=schema,
                shared_schema=self.database.schema,
                world_id=5,
            )
            previous_binding = bind_kaloda_database(cards)
            with running_server(self.database) as lobby_client:
                lobby_client.register("kalodalogin", "password")
                lobby_client.login("kalodalogin", "password")
                card_client = KalodaClient(f"{lobby_client.base_url}/kaloda")
                card_client.login("kalodalogin", "password")

                self.assertEqual(card_client.get_game_info()["world_id"], 5)
                self.assertEqual(cards.user_id_by_token(card_client.token), 1)
                with self.assertRaises(ValueError):
                    self.database.user_id_by_token(card_client.token)
        finally:
            if previous_binding is not None:
                bind_kaloda_database(*previous_binding)
            if cards is not None:
                cards.close()
            with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
                connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

    def test_kaloda_routes_are_mounted_under_the_central_server(self):
        with running_server(self.database) as client:
            self.assertEqual(client._request("GET", "/kaloda/health"), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
