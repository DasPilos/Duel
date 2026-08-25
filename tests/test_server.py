import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from client.network import GameClient, ServerError
from server.database import Database
from server.main import GameRequestHandler
from server import social, world
from client.state import ChatState


class ServerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_character_is_created_and_loaded(self):
        user = self.database.register("tester", "password")
        login = self.database.login("tester", "password")
        user_id = self.database.user_id_by_token(login["token"])
        self.assertEqual(user_id, user["id"])

        created = self.database.create_character(user_id, "Воин")
        saved = self.database.save_character(
            user_id,
            created["id"],
            {**created, "hp": created["max_hp"] - 10, "xp": 30},
        )
        loaded = self.database.get_character(user_id, created["id"])

        self.assertEqual(saved["hp"], loaded["hp"])
        self.assertEqual(loaded["xp"], 30)
        self.assertEqual(loaded["name"], "Воин")

    def test_account_can_have_multiple_characters(self):
        user = self.database.register("tester", "password")
        first = self.database.create_character(user["id"], "Воин")
        second = self.database.create_character(user["id"], "Маг")

        characters = self.database.get_characters(user["id"])

        self.assertEqual([first["id"], second["id"]], [item["id"] for item in characters])

    def test_character_name_is_limited_and_filtered(self):
        user = self.database.register("tester", "password")
        with self.assertRaises(ValueError):
            self.database.create_character(user["id"], "Слишком длинное имя")
        with self.assertRaises(ValueError):
            self.database.create_character(user["id"], "идиот")

    def test_backyard_contains_brawler_bot(self):
        user = self.database.register("tester", "password")
        opponents = self.database.get_opponents(user["id"])
        brawler = next(item for item in opponents if item["name"] == "Забияка")

        self.assertEqual(brawler["level"], 1)
        self.assertEqual(
            brawler["stats"],
            {
                "strength": 9,
                "agility": 4,
                "intuition": 5,
                "endurance": 8,
            },
        )

    def test_backyard_contains_all_bot_profiles(self):
        user = self.database.register("tester", "password")
        opponents = self.database.get_opponents(user["id"])
        bots = {item["name"]: item for item in opponents if item["kind"] == "bot"}

        self.assertEqual(
            set(bots),
            {"Забияка", "Безпроводной Душ", "Комфу Падла", "Пахарь"},
        )
        self.assertEqual(bots["Безпроводной Душ"]["stats"], {
            "strength": 6,
            "agility": 4,
            "intuition": 10,
            "endurance": 6,
        })
        self.assertEqual(bots["Комфу Падла"]["stats"], {
            "strength": 6,
            "agility": 10,
            "intuition": 4,
            "endurance": 6,
        })
        self.assertEqual(bots["Пахарь"]["stats"], {
            "strength": 12,
            "agility": 4,
            "intuition": 4,
            "endurance": 6,
        })

    def test_password_is_not_accepted_in_plain_text(self):
        self.database.register("tester", "password")
        with self.assertRaises(ValueError):
            self.database.login("tester", "wrong-password")

    def test_chat_history_is_persistent_and_ordered(self):
        user = self.database.register("tester", "password")
        character = self.database.create_character(user["id"], "Чатер")
        first = self.database.add_chat_message(character["id"], "tavern", "<b>текст</b>")
        second = self.database.add_chat_message(character["id"], "tavern", "Второе")

        history = self.database.get_chat_history(character["id"], "tavern")

        self.assertEqual([item["id"] for item in history], [first["id"], second["id"]])
        self.assertEqual(history[0]["text"], "<b>текст</b>")

    def test_chat_unread_and_read_marker(self):
        user = self.database.register("tester", "password")
        character = self.database.create_character(user["id"], "Чатер")
        message = self.database.add_chat_message(character["id"], "tavern", "Привет")

        self.assertEqual(self.database.chat_unread_count(character["id"], "tavern"), 1)
        self.database.mark_chat_read(character["id"], "tavern", message["id"])
        self.assertEqual(self.database.chat_unread_count(character["id"], "tavern"), 0)

    def test_chat_message_rate_limit_is_enforced_by_handler(self):
        GameRequestHandler.chat_send_times.clear()
        GameRequestHandler.chat_send_times[7] = [time.time()] * 5
        handler = GameRequestHandler.__new__(GameRequestHandler)
        with self.assertRaises(ValueError):
            handler._check_chat_rate(7)

    def test_chat_state_deduplicates_messages(self):
        state = ChatState()
        message = {"id": 1, "created_at": 2, "text": "hello"}
        state.replace_messages("tavern", [message, message])
        state.add_message("tavern", message)
        self.assertEqual(len(state.messages_by_channel["tavern"]), 1)

    def test_duel_application_is_public_and_expires(self):
        user = self.database.register("tester", "password")
        character = self.database.create_character(user["id"], "Воин")
        social.DUEL_OFFERS.clear()
        application = social.add_public_duel_offer(
            {"character_id": character["id"], "name": character["name"]},
            "backyard",
        )

        self.assertIn(application["id"], {offer["id"] for offer in social.public_offers("backyard")})
        user_offer = next(
            offer for offer in social.DUEL_OFFERS
            if offer["id"] == application["id"]
        )
        user_offer["created_at"] -= 121
        active_ids = {offer["id"] for offer in social.public_offers("backyard")}
        self.assertNotIn(application["id"], active_ids)

    def test_bot_accepts_only_equal_backyard_duel(self):
        GameRequestHandler.database = self.database
        world.update_bot("bot_brawler", 212)
        social.DUEL_OFFERS.clear()
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")

        try:
            client.register("botuser", "password")
            client.login("botuser", "password")
            character = client.create_character("Равный боец")
            with self.assertRaises(ServerError):
                client.offer_duel(character["id"], "backyard", "bot_brawler")

            character.update({
                "stats": {
                    "strength": 5,
                    "agility": 5,
                    "intuition": 5,
                    "endurance": 11,
                },
                "max_hp": 254,
                "hp": 254,
            })
            character = client.save_character(character)
            result = client.offer_duel(character["id"], "backyard", "bot_brawler")
        finally:
            http_server.shutdown()
            http_server.server_close()

        self.assertTrue(result["accepted"])
        self.assertEqual(result["offer"]["status"], "accepted")
        self.assertEqual(result["offer"]["accepted_by"], "bot_brawler")

    def test_client_api_round_trip(self):
        GameRequestHandler.database = self.database
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")

        try:
            client.register("apiuser", "password")
            client.login("apiuser", "password")
            character = client.create_character("Сетевой воин")
            character["xp"] = 30
            saved = client.save_character(character)
            loaded = client.load_character()
            client.disconnect(loaded)
        finally:
            http_server.shutdown()
            http_server.server_close()

        self.assertEqual(saved["xp"], 30)
        self.assertEqual(loaded["name"], "Сетевой воин")

    def test_client_can_create_duel_application(self):
        GameRequestHandler.database = self.database
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")

        try:
            client.register("appuser", "password")
            client.login("appuser", "password")
            character = client.create_character("Заявитель")
            application = client.create_duel_application(character["id"], "backyard")
        finally:
            http_server.shutdown()
            http_server.server_close()

        self.assertEqual(application["application"]["sender_id"], character["id"])


if __name__ == "__main__":
    unittest.main()
