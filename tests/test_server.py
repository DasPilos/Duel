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
from ui.chat.widgets import MessageList
from scenes.duel_scene import DuelScene
import pygame


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

    def test_login_applies_offline_regen_before_session_starts(self):
        user = self.database.register("offline_login", "password")
        character = self.database.create_character(user["id"], "Вернувшийся")
        self.database.save_character(
            user["id"],
            character["id"],
            {**character, "hp": 1},
        )
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET updated_at = ? WHERE id = ?",
                (time.time() - 600, character["id"]),
            )

        self.database.login("offline_login", "password")
        loaded = self.database.get_character(user["id"], character["id"])

        self.assertEqual(loaded["hp"], loaded["max_hp"])

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

        expected_names = {item["name"] for item in world.BOT_OPPONENTS}
        self.assertEqual(set(bots), expected_names)

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

    def test_client_can_send_and_read_chat_message(self):
        GameRequestHandler.database = self.database
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")

        try:
            client.register("chatuser", "password")
            client.login("chatuser", "password")
            character = client.create_character("Собеседник")
            message = client.send_message(character["id"], "tavern", "Привет")
            history = client.list_messages("tavern", character["id"])
        finally:
            http_server.shutdown()
            http_server.server_close()

        self.assertEqual(message["message"]["text"], "Привет")
        self.assertEqual(history[-1]["text"], "Привет")

    def test_legacy_social_message_route_remains_compatible(self):
        GameRequestHandler.database = self.database
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")

        try:
            client.register("legacychat", "password")
            client.login("legacychat", "password")
            character = client.create_character("Старый чат")
            result = client._request(
                "POST",
                "/api/social/messages",
                {"character_id": character["id"], "location": "tavern", "text": "Совместимо"},
                authenticated=True,
            )
        finally:
            http_server.shutdown()
            http_server.server_close()

        self.assertEqual(result["message"]["text"], "Совместимо")

    def test_bot_tavern_reply_is_persisted_in_database(self):
        user = self.database.register("botchat", "password")
        character = self.database.create_character(user["id"], "Зритель")

        social.record_bot_tavern_reply("bot_test", "Тестовый бот", "win", location="tavern", db=self.database)

        history = self.database.get_chat_history(character["id"], "tavern")

        self.assertTrue(any(item["sender"] == "Тестовый бот" for item in history))

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

    def test_chat_history_discards_messages_older_than_48_hours(self):
        user = self.database.register("history_ttl", "password")
        character = self.database.create_character(user["id"], "История")
        old_message = self.database.add_chat_message(character["id"], "tavern", "старое")
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE chat_messages SET created_at = ? WHERE id = ?",
                (time.time() - 48 * 60 * 60 - 1, old_message["id"]),
            )
        new_message = self.database.add_chat_message(character["id"], "tavern", "новое")

        history = self.database.get_chat_history(character["id"], "tavern")

        self.assertEqual([message["id"] for message in history], [new_message["id"]])

    def test_message_list_scroll_preserves_manual_position(self):
        message_list = MessageList(pygame.Rect(0, 0, 200, 50), None)
        message_list.set_messages([{"id": index, "text": str(index)} for index in range(10)])
        message_list.wheel(-1)
        scroll_position = message_list.scroll

        message_list.set_messages(message_list.messages)

        self.assertEqual(message_list.scroll, scroll_position)

    def test_duel_scene_switches_chat_to_battle_log_when_fight_starts(self):
        pygame.init()
        scene = DuelScene()

        class DummyChat:
            def __init__(self):
                self.channel = "Общий"
                self.message_list = type("List", (), {"set_messages": lambda self, messages: None})()

            def _visible_messages(self):
                return []

        scene.chat = DummyChat()
        scene.start_battle_comments()

        self.assertEqual(scene.chat.channel, "Лог боя")
        pygame.quit()

    def test_duel_profile_close_click_is_consumed_before_battle_input(self):
        pygame.init()
        try:
            scene = DuelScene()
            scene.profile_overlay.open({"name": "Соперник", "stats": {}})
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": scene.profile_overlay.close_button.center},
            )

            scene.handle_event(event)

            self.assertFalse(scene.profile_overlay.is_open)
            self.assertIsNone(scene.attack_zone)
        finally:
            pygame.quit()

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
