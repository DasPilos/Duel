import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

from client.network import GameClient, ServerError
from server.central_main import CentralRequestHandler
from tests.fixtures import create_test_database, drop_test_database


class CentralServerTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database(central=True)
        self.http_server = ThreadingHTTPServer(("127.0.0.1", 0), CentralRequestHandler)
        self.previous_database = CentralRequestHandler.database
        CentralRequestHandler.database = self.database
        self.thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.thread.start()
        self.client = GameClient(f"http://127.0.0.1:{self.http_server.server_port}")

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.thread.join(timeout=2)
        CentralRequestHandler.database = self.previous_database
        drop_test_database(self.database)

    def test_central_login_and_lobby_do_not_require_a_game_world(self):
        user = self.client.register("central-player", "password123")["user"]
        self.assertEqual(user["username"], "central-player")

        self.client.login("central-player", "password123")

        with self.database.connection() as connection:
            session = connection.execute(
                "SELECT world_id FROM sessions WHERE token = %s", (self.client.token,)
            ).fetchone()
        self.assertIsNone(session["world_id"])
        self.assertNotIn("lobby", [world["code"] for world in self.client.list_worlds()])
        self.assertIn("central-player", [player["username"] for player in self.client.list_lobby()])
        self.assertEqual(self.client.get_me()["username"], "central-player")

    def test_central_login_includes_account_role(self):
        user = self.client.register("central-admin", "password123")["user"]
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user["id"],))

        logged_in_user = self.client.login("central-admin", "password123")

        self.assertEqual(logged_in_user["role"], "admin")

    def test_central_routes_require_a_valid_account_session(self):
        with self.assertRaises(ServerError):
            self.client.list_worlds()

    def test_central_item_update_uses_selected_mode_and_requires_moderator(self):
        self.database.register("item-viewer", "password123")
        self.client.login("item-viewer", "password123")
        with self.assertRaisesRegex(ServerError, "модератора"):
            self.client._request(
                "PUT",
                "/api/items/catalog/1000",
                {"mode": "front_line", "form": {"name": "Клинок"}},
                authenticated=True,
            )

        user = self.database.register("item-editor", "password123")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user["id"],))
        self.client.login("item-editor", "password123")
        item_database = MagicMock()
        item_database.update_item.return_value = {
            "id": 1000,
            "name": "Клинок",
            "item_type": "equipment",
        }

        with patch("server.central_main.map_worlds.mode_item_database", return_value=item_database):
            item = self.client._request(
                "PUT",
                "/api/items/catalog/1000",
                {"mode": "front_line", "form": {"name": "Клинок"}},
                authenticated=True,
            )["item"]

        self.assertEqual(item["name"], "Клинок")
        item_database.update_item.assert_called_once_with(user["id"], 1000, {"name": "Клинок"})

    def test_public_version_endpoint_reports_server_and_application_compatibility(self):
        client_info = self.client._request(
            "GET", "/api/version?app=client&version=1.0.0&protocol=1"
        )
        old_editor_info = self.client._request(
            "GET", "/api/version?app=editor&version=0.9.0&protocol=1"
        )
        protocol_mismatch = self.client._request(
            "GET", "/api/version?app=client&version=1.0.0&protocol=2"
        )

        self.assertEqual(client_info["server_version"], "1.0.0")
        self.assertEqual(client_info["protocol_version"], 1)
        self.assertTrue(client_info["compatibility"]["compatible"])
        self.assertTrue(old_editor_info["compatibility"]["requires_update"])
        self.assertIn("1.0.0", old_editor_info["compatibility"]["reason"])
        self.assertFalse(protocol_mismatch["compatibility"]["compatible"])
        self.assertIn("протокола", protocol_mismatch["compatibility"]["reason"])

    def test_map_editor_can_save_and_reopen_a_draft_from_the_central_lobby(self):
        user = self.client.register("central-map-editor", "password123")["user"]
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user["id"],))
        self.client.login("central-map-editor", "password123")

        catalog = self.client._request("GET", "/api/map/catalog", authenticated=True)["items"]
        self.assertTrue(catalog)
        saved = self.client.save_saved_map([], 64, 64, "Lobby draft", "tower")
        drafts = self.client.list_saved_maps("tower")
        loaded = self.client._request(
            "GET", f"/api/map/editor/saved/{saved['saved_id']}", authenticated=True,
        )["map"]

        self.assertIn(saved["saved_id"], [draft["id"] for draft in drafts])
        self.assertEqual(loaded["name"], "Lobby draft")
        self.assertEqual(loaded["mode"], "tower")

    def test_lobby_chat_requires_auth_and_returns_shared_messages(self):
        self.client.register("chat-player", "password123")
        self.client.login("chat-player", "password123")
        anonymous = GameClient(self.client.base_url)

        with self.assertRaises(ServerError):
            anonymous.list_lobby_chat()

        message = self.client.send_lobby_chat_message("  Всем привет!  ")
        history = self.client.list_lobby_chat()

        self.assertEqual(message["username"], "chat-player")
        self.assertEqual(message["text"], "Всем привет!")
        self.assertEqual(history[-1]["id"], message["id"])

    def test_lobby_chat_validates_messages_and_rate_limits_senders(self):
        self.client.register("chat-limits", "password123")
        self.client.login("chat-limits", "password123")

        with self.assertRaises(ServerError):
            self.client.send_lobby_chat_message("  ")
        with self.assertRaises(ServerError):
            self.client.send_lobby_chat_message("x" * 301)

        for index in range(5):
            self.client.send_lobby_chat_message(f"message {index}")
        with self.assertRaises(ServerError):
            self.client.send_lobby_chat_message("too many")

    def test_account_password_change_keeps_current_session_and_revokes_others(self):
        self.client.register("account-player", "password123")
        self.client.login("account-player", "password123")
        other_session = GameClient(self.client.base_url)
        other_session.login("account-player", "password123")

        updated_user = self.client.change_password("password123", "newpassword123")

        self.assertEqual(updated_user["username"], "account-player")
        self.assertEqual(self.client.get_me()["username"], "account-player")
        with self.assertRaises(ServerError):
            other_session.get_me()
        with self.assertRaises(ServerError):
            GameClient(self.client.base_url).login("account-player", "password123")
        self.assertEqual(
            GameClient(self.client.base_url).login("account-player", "newpassword123")["username"],
            "account-player",
        )

    def test_account_password_change_rejects_wrong_current_password(self):
        self.client.register("account-check", "password123")
        self.client.login("account-check", "password123")

        with self.assertRaises(ServerError):
            self.client.change_password("incorrect", "newpassword123")

    def test_central_lists_available_mode_runtimes(self):
        self.client.register("mode-player", "password123")
        self.client.login("mode-player", "password123")

        modes = self.client.list_modes()

        self.assertEqual(
            [mode["key"] for mode in modes],
            ["tower", "economy", "deck", "front_line"],
        )
        self.assertEqual(
            [mode["name"] for mode in modes],
            ["Tower", "Economy", "Deck", "Front Line"],
        )
        self.assertEqual(modes[0]["entrypoint"], "tower.server.main")
        self.assertEqual(modes[1]["entrypoint"], "economy.server.main")
        self.assertEqual(modes[2]["entrypoint"], "deck.server.main")
        self.assertEqual(modes[3]["entrypoint"], "front_line.server.main")
        self.assertEqual(modes[3]["schema"], "tower")
        self.assertTrue(modes[3]["runtime_ready"])

    def test_central_auth_creates_a_world_scoped_session(self):
        user = self.client.register("world-player", "password123")["user"]
        self.client.login("world-player", "password123")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role='admin' WHERE id=%s", (user["id"],))
        world = self.database.create_map_world("Economy test", "economy", user["id"])
        self.database.set_world_server(world["id"], "http://127.0.0.1:8805")

        session = self.client.connect_world(world["id"])

        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT world_id FROM sessions WHERE token=%s", (session["token"],)
            ).fetchone()
        self.assertEqual(row["world_id"], world["id"])
        self.assertEqual(session["user"]["id"], user["id"])

    def test_map_editor_can_read_shared_palette_from_central_server(self):
        self.client.register("map-editor", "password123")
        self.client.login("map-editor", "password123")

        self.assertEqual(self.client.get_map_palette(), self.database.map_palette_state())

    def test_central_map_publish_enforces_mode_boundaries(self):
        user = self.client.register("map-admin", "password123")["user"]
        self.client.login("map-admin", "password123")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role='admin' WHERE id=%s", (user["id"],))
        economy_world = self.database.create_map_world("Economy editor test", "economy", user["id"])
        deck_world = self.database.create_map_world("Deck editor test", "deck", user["id"])

        with self.assertRaises(ServerError):
            self.client.publish_map([], 125, 125, "Wrong mode", economy_world["id"], mode="tower")

        with self.assertRaises(ServerError):
            self.client.publish_map([], 125, 125, "Deck map", deck_world["id"], mode="deck")

        with patch.object(
            self.database, "publish_map",
            return_value={"world_id": economy_world["id"], "applied": 1},
        ) as publish:
            result = self.client.publish_map(
                [], 125, 125, "Economy map", economy_world["id"], mode="economy",
            )

        self.assertEqual(result["world_id"], economy_world["id"])
        self.assertEqual(publish.call_args.args[7], "economy")

    def test_central_map_material_validation_uses_mode_catalog(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [{"id": 17}]
        context = MagicMock()
        context.__enter__.return_value = connection

        with patch.object(self.database, "connection", return_value=context):
            self.assertEqual(self.database.material_item_ids("economy"), {17})

        query = connection.execute.call_args.args[0]
        self.assertIn('"economy".items_catalog', query)
        with self.assertRaises(ValueError):
            self.database.material_item_ids("deck")

    def test_central_map_material_validation_uses_tower_schema_for_front_line(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [{"id": 17}]
        context = MagicMock()
        context.__enter__.return_value = connection

        with patch.object(self.database, "connection", return_value=context):
            self.assertEqual(self.database.material_item_ids("front_line"), {17})

        query = connection.execute.call_args.args[0]
        self.assertIn('"tower".items_catalog', query)


if __name__ == "__main__":
    unittest.main()
