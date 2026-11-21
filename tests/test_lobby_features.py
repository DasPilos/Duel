import base64
import struct
import threading
import time
import unittest
import zlib
from http.server import ThreadingHTTPServer

from client.network import GameClient, ServerError
from server import avatars
from server.central_main import CentralRequestHandler
from tests.fixtures import create_test_database, drop_test_database


def make_png(width=avatars.AVATAR_SIZE, height=avatars.AVATAR_SIZE, bit_depth=8, color_type=6):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    channels = {0: 1, 2: 3, 6: 4}[color_type]
    header = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    scanlines = b"".join(b"\x00" + bytes(width * channels) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class AvatarValidationTests(unittest.TestCase):
    def test_accepts_150_pixel_png_in_rgb_or_rgba(self):
        for color_type in (2, 6):
            png = make_png(color_type=color_type)
            self.assertEqual(avatars.validate_avatar_png(png), png)

    def test_rejects_other_sizes_formats_and_bit_depths(self):
        for png in (make_png(151, 150), make_png(150, 150, bit_depth=16), make_png(color_type=0)):
            with self.assertRaises(ValueError):
                avatars.validate_avatar_png(png)
        with self.assertRaises(ValueError):
            avatars.validate_avatar_png(b"GIF89a" + bytes(40))

    def test_rejects_broken_and_oversized_payloads(self):
        with self.assertRaises(ValueError):
            avatars.decode_avatar("")
        with self.assertRaises(ValueError):
            avatars.decode_avatar("%%% не base64 %%%")
        with self.assertRaises(ValueError):
            avatars.validate_avatar_png(b"\x89PNG\r\n\x1a\n" + bytes(avatars.MAX_AVATAR_BYTES))


class LobbyFeatureTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database(central=True)
        self.http_server = ThreadingHTTPServer(("127.0.0.1", 0), CentralRequestHandler)
        self.previous_database = CentralRequestHandler.database
        CentralRequestHandler.database = self.database
        self.thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.http_server.server_port}"

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.thread.join(timeout=2)
        CentralRequestHandler.database = self.previous_database
        drop_test_database(self.database)

    def logged_in_client(self, username, role="user"):
        user = self.database.register(username, "password123")
        if role != "user":
            with self.database.connection() as connection:
                connection.execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
        client = GameClient(self.base_url)
        client.login(username, "password123")
        return client, user

    def test_account_avatar_is_stored_as_a_150_pixel_png(self):
        client, _ = self.logged_in_client("avatar-player")
        self.assertIsNone(client._request("GET", "/api/account/avatar", authenticated=True)["png_base64"])

        png = make_png()
        saved = client._request(
            "POST", "/api/account/avatar", {"png_base64": base64.b64encode(png).decode("ascii")}, authenticated=True
        )
        self.assertEqual(saved["avatar"]["size"], avatars.AVATAR_SIZE)
        stored = client._request("GET", "/api/account/avatar", authenticated=True)["png_base64"]
        self.assertEqual(base64.b64decode(stored), png)

        wrong_size = base64.b64encode(make_png(151, 150)).decode("ascii")
        with self.assertRaises(ServerError):
            client._request("POST", "/api/account/avatar", {"png_base64": wrong_size}, authenticated=True)
        stored_again = client._request("GET", "/api/account/avatar", authenticated=True)["png_base64"]
        self.assertEqual(base64.b64decode(stored_again), png)

        with self.assertRaises(ServerError):
            GameClient(self.base_url)._request("GET", "/api/account/avatar")

    def test_account_game_nickname_is_saved_and_returned_for_front_line(self):
        client, user = self.logged_in_client("nickname-player")

        updated = client.change_game_nickname("  Звёздный Страж  ")

        self.assertEqual(updated["game_nickname"], "Звёздный Страж")
        self.assertEqual(client._request("GET", "/api/me", authenticated=True)["user"]["game_nickname"], "Звёздный Страж")
        self.assertEqual(self.database.game_nicknames([user["id"]]), {user["id"]: "Звёздный Страж"})
        with self.database.connection() as connection:
            connection.execute("UPDATE worlds SET server_url = %s WHERE id = %s", ("http://127.0.0.1:8800", 2))
        world_session = client.connect_world(2)
        self.assertEqual(world_session["user"]["game_nickname"], "Звёздный Страж")

    def test_account_game_nickname_requires_two_to_24_non_control_characters(self):
        client, _ = self.logged_in_client("nickname-invalid")

        for nickname in ("", "x", "x" * 25, "hero\nname"):
            with self.subTest(nickname=nickname), self.assertRaises(ServerError):
                client.change_game_nickname(nickname)
        self.assertEqual(client.get_me()["game_nickname"], "")

    def test_lobby_whispers_reach_only_their_sender_and_recipient(self):
        alice, alice_user = self.logged_in_client("whisper-alice")
        bob, bob_user = self.logged_in_client("whisper-bob")
        carol, _ = self.logged_in_client("whisper-carol")
        alice._request("POST", "/api/lobby/chat", {"text": "всем привет"}, authenticated=True)
        whisper = alice._request(
            "POST", "/api/lobby/chat",
            {"text": "тебе одному", "recipient_user_id": bob_user["id"]},
            authenticated=True,
        )["message"]
        self.assertEqual(whisper["recipient_user_id"], bob_user["id"])
        self.assertEqual(whisper["recipient_username"], "whisper-bob")

        alice_texts = [message["text"] for message in alice.list_lobby_chat()]
        bob_texts = [message["text"] for message in bob.list_lobby_chat()]
        carol_texts = [message["text"] for message in carol.list_lobby_chat()]
        self.assertIn("тебе одному", alice_texts)
        self.assertIn("тебе одному", bob_texts)
        self.assertNotIn("тебе одному", carol_texts)
        self.assertIn("всем привет", carol_texts)

        with self.assertRaises(ServerError):
            alice._request(
                "POST", "/api/lobby/chat", {"text": "себе", "recipient_user_id": alice_user["id"]}, authenticated=True
            )
        with self.assertRaises(ServerError):
            alice._request(
                "POST", "/api/lobby/chat", {"text": "никому", "recipient_user_id": 999999}, authenticated=True
            )

    def test_world_list_reports_online_players_start_time_and_privacy(self):
        admin = self.database.register("world-admin", "password123")
        moderator = self.database.register("world-mod", "password123")
        player = self.database.register("world-player", "password123")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (admin["id"],))
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (moderator["id"],))
        public_world = self.database.create_map_world("Открытая долина", "tower", admin["id"], test_only=False)
        test_world = self.database.create_map_world("Тестовая долина", "tower", moderator["id"], test_only=True)
        self.database.set_world_server(public_world["id"], "http://127.0.0.1:8801")

        now = time.time()
        with self.database.connection() as connection:
            for index, user_id in enumerate((player["id"], moderator["id"], player["id"])):
                connection.execute(
                    """INSERT INTO sessions (token, user_id, world_id, created_at, last_seen_at)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (f"online-token-{index}", user_id, public_world["id"], now, now),
                )
            connection.execute(
                """INSERT INTO sessions (token, user_id, world_id, created_at, last_seen_at)
                   VALUES ('stale-token', %s, %s, %s, %s)""",
                (admin["id"], public_world["id"], now - 3600, now - 3600),
            )

        visible_to_players = {world["id"]: world for world in self.database.list_worlds(viewer_id=None)}
        self.assertNotIn(test_world["id"], visible_to_players)
        worlds = {world["id"]: world for world in self.database.list_worlds(viewer_id=moderator["id"])}
        self.assertEqual(worlds[public_world["id"]]["online_players"], 2)
        self.assertIsNotNone(worlds[public_world["id"]]["started_at"])
        self.assertTrue(worlds[test_world["id"]]["test_only"])
        self.assertIsNone(worlds[test_world["id"]]["started_at"])
        self.assertEqual(worlds[test_world["id"]]["online_players"], 0)

        self.database.set_world_server(public_world["id"], None)
        stopped = {world["id"]: world for world in self.database.list_worlds(viewer_id=None)}
        self.assertIsNone(stopped[public_world["id"]]["started_at"])


if __name__ == "__main__":
    unittest.main()
