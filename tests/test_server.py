import time
import threading
import unittest
from unittest.mock import patch

from client.network import ServerError
from combat.card_database import Card
from server.database import Database
from server.main import GameRequestHandler
from server import social, world
from server import maintenance
from client.state import ChatState
from ui.chat.widgets import MessageList
from tests.fixtures import create_test_database, drop_test_database, running_server
from scenes.duel_scene import DuelScene
import pygame


class ServerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def test_restart_notice_counts_down_and_can_be_cancelled(self):
        maintenance.cancel_restart()
        try:
            notice = maintenance.schedule_restart(delay_seconds=180, now=1000)
            self.assertEqual(notice["seconds_remaining"], 180)
            self.assertFalse(maintenance.restart_due(now=1179))
            self.assertTrue(maintenance.restart_due(now=1180))
            maintenance.cancel_restart()
            self.assertIsNone(maintenance.public_notice(now=1180))
        finally:
            maintenance.cancel_restart()

    def test_restart_scheduler_stops_server_when_countdown_expires(self):
        from server.main import _run_scheduled_restart

        class FakeServer:
            def __init__(self):
                self.shutdown_called = False

            def shutdown(self):
                self.shutdown_called = True

        maintenance.cancel_restart()
        stop = threading.Event()
        restart_requested = threading.Event()
        server = FakeServer()
        try:
            maintenance.schedule_restart(delay_seconds=1, now=time.time() - 1)
            _run_scheduled_restart(server, stop, restart_requested)
            self.assertTrue(server.shutdown_called)
            self.assertTrue(restart_requested.is_set())
        finally:
            maintenance.cancel_restart()

    def test_scheduled_restart_stops_http_server_at_deadline(self):
        from server.main import _run_scheduled_restart

        class FakeServer:
            def __init__(self):
                self.stopped = threading.Event()

            def shutdown(self):
                self.stopped.set()

        maintenance.cancel_restart()
        stop = threading.Event()
        requested = threading.Event()
        server = FakeServer()
        try:
            maintenance.schedule_restart(delay_seconds=1, now=time.time() - 1)
            _run_scheduled_restart(server, stop, requested)
            self.assertTrue(requested.is_set())
            self.assertTrue(server.stopped.is_set())
        finally:
            maintenance.cancel_restart()

    def test_server_status_counts_players_and_restart_control_requires_moderator(self):
        maintenance.cancel_restart()
        with running_server(self.database) as client:
            client.register("statususer", "password")
            client.login("statususer", "password")
            character = client.create_character("StatusUser")
            client.social_snapshot("tavern", character["id"])

            self.assertEqual(client.get_server_status(), {
                "online_players": 1,
                "restart_notice": None,
            })
            with self.assertRaisesRegex(ServerError, "Недостаточно прав"):
                client.schedule_server_restart()

            with self.database.connection() as connection:
                connection.execute("UPDATE users SET role = 'moderator' WHERE username = %s", ("statususer",))

            notice = client.schedule_server_restart()
            self.assertEqual(notice["seconds_remaining"], 180)
            self.assertIn("обновление", notice["message"])
            self.assertIsNone(client.cancel_server_restart())
        self.assertIsNone(maintenance.public_notice())

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

    def test_card_collection_persists_and_stacks_duplicate_cards(self):
        user = self.database.register("collector", "password")
        character = self.database.create_character(user["id"], "Коллекционер")

        first = self.database.add_card_to_collection(character["id"], "test_card")
        second = self.database.add_card_to_collection(character["id"], "test_card")
        collection = self.database.get_card_collection(character["id"])

        self.assertEqual(first["slot_index"], 0)
        self.assertEqual(second["quantity"], 2)
        self.assertEqual(len(collection), 1)
        self.assertEqual(collection[0]["card_key"], "test_card")
        self.assertEqual(collection[0]["quantity"], 2)

    def test_card_collection_has_sixty_unique_slots(self):
        user = self.database.register("fullcollector", "password")
        character = self.database.create_character(user["id"], "Хранитель")
        for index in range(60):
            self.database.add_card_to_collection(
                character["id"],
                f"card_{index}",
            )

        with self.assertRaisesRegex(ValueError, "нет свободных"):
            self.database.add_card_to_collection(character["id"], "overflow")

    def test_client_receives_battle_card_in_collection(self):
        card = Card(
            key="reward_card",
            name="Наградная карта",
            group_name="Боец: Тест",
            resource_type="rage",
            resource_cost=1,
            effect_type="damage",
            effect_data={"dice": "1d4"},
            drop_chance=100,
            image_path="assets/cards/faces/reward_card.png",
        )
        with running_server(self.database) as client:
            client.register("rewarduser", "password")
            client.login("rewarduser", "password")
            character = client.create_character("Победитель")
            with (
                patch("server.main.load_cards", return_value=[card]),
                patch("server.main.choose_battle_reward", return_value=card),
            ):
                reward = client.award_battle_card(
                    character["id"],
                    ["reward_card"],
                )
                collection = client.get_card_collection(character["id"])

        self.assertEqual(reward["key"], "reward_card")
        self.assertEqual(collection[0]["key"], "reward_card")
        self.assertEqual(collection[0]["quantity"], 1)

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
                "UPDATE characters SET updated_at = %s WHERE id = %s",
                (time.time() - 600, character["id"]),
            )

        self.database.login("offline_login", "password")
        loaded = self.database.get_character(user["id"], character["id"])

        self.assertEqual(loaded["hp"], loaded["max_hp"])

    def test_account_has_one_character_per_world(self):
        user = self.database.register("tester", "password")
        first = self.database.create_character(user["id"], "Воин")
        with self.assertRaisesRegex(ValueError, "уже есть персонаж"):
            self.database.create_character(user["id"], "Маг")

        second_world = Database(self.database.dsn, schema=self.database.schema, world_id=2)
        second = second_world.create_character(user["id"], "Маг")

        self.assertEqual([first["id"]], [item["id"] for item in self.database.get_characters(user["id"])])
        self.assertEqual([second["id"]], [item["id"] for item in second_world.get_characters(user["id"])])
        self.assertIsNone(self.database.get_character(user["id"], second["id"]))

    def test_character_name_is_unique_within_world_only(self):
        first = self.database.register("first", "password")
        second = self.database.register("second", "password")
        self.database.create_character(first["id"], "Воин")
        with self.assertRaisesRegex(ValueError, "имя уже занято"):
            self.database.create_character(second["id"], "воин")

        second_world = Database(self.database.dsn, schema=self.database.schema, world_id=2)
        self.assertEqual(second_world.create_character(second["id"], "Воин")["name"], "Воин")

    def test_session_is_bound_to_its_world(self):
        self.database.register("traveller", "password")
        token = self.database.login("traveller", "password")["token"]
        second_world = Database(self.database.dsn, schema=self.database.schema, world_id=2)

        with self.assertRaises(ValueError):
            second_world.user_id_by_token(token)

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
                "strength": 6,
                "agility": 3,
                "intuition": 3,
                "endurance": 4,
            },
        )

    def test_backyard_contains_all_bot_profiles(self):
        user = self.database.register("tester", "password")
        opponents = self.database.get_opponents(user["id"])
        bots = {item["name"]: item for item in opponents if item["kind"] == "bot"}

        expected_names = {item["name"] for item in world.BOT_OPPONENTS}
        self.assertEqual(set(bots), expected_names)

        self.assertEqual(bots["Безпроводной Душ"]["stats"], {
            "strength": 3,
            "agility": 3,
            "intuition": 6,
            "endurance": 4,
        })
        self.assertEqual(bots["Комфу Падла"]["stats"], {
            "strength": 3,
            "agility": 6,
            "intuition": 3,
            "endurance": 4,
        })
        self.assertEqual(bots["Пахарь"]["stats"], {
            "strength": 3,
            "agility": 3,
            "intuition": 3,
            "endurance": 7,
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
        with running_server(self.database) as client:
            client.register("chatuser", "password")
            client.login("chatuser", "password")
            character = client.create_character("Собеседник")
            message = client.send_message(character["id"], "tavern", "Привет")
            history = client.list_messages("tavern", character["id"])

        self.assertEqual(message["message"]["text"], "Привет")
        self.assertEqual(history[-1]["text"], "Привет")

    def test_legacy_social_message_route_remains_compatible(self):
        with running_server(self.database) as client:
            client.register("legacychat", "password")
            client.login("legacychat", "password")
            character = client.create_character("Старый чат")
            result = client._request(
                "POST",
                "/api/social/messages",
                {"character_id": character["id"], "location": "tavern", "text": "Совместимо"},
                authenticated=True,
            )

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
                "UPDATE chat_messages SET created_at = %s WHERE id = %s",
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
        world.update_bot("bot_brawler", 40)
        social.DUEL_OFFERS.clear()
        with running_server(self.database) as client:
            user_id = client.register("botuser", "password")["user"]["id"]
            client.login("botuser", "password")
            character = client.create_character("Равный боец")
            # Level is server-owned, so the test changes it on the server side.
            character.update({"level": 2})
            character["stats"]["endurance"] = 4
            character["max_hp"] = 40
            character["hp"] = 40
            character = self.database.save_character(user_id, character["id"], character)
            with self.assertRaises(ServerError):
                client.offer_duel(character["id"], "backyard", "bot_brawler")

            character.update({"level": 1})
            character["stats"]["endurance"] = 3
            character["max_hp"] = 30
            character["hp"] = 30
            character = self.database.save_character(user_id, character["id"], character)
            result = client.offer_duel(character["id"], "backyard", "bot_brawler")

        self.assertTrue(result["accepted"])
        self.assertEqual(result["offer"]["status"], "accepted")
        self.assertEqual(result["offer"]["accepted_by"], "bot_brawler")

    def test_client_api_round_trip(self):
        with running_server(self.database) as client:
            client.register("apiuser", "password")
            client.login("apiuser", "password")
            character = client.create_character("Сетевой воин")
            with self.assertRaisesRegex(ServerError, "Опыт начисляется сервером"):
                client.save_character({**character, "xp": 30})
            character["zone"] = "backyard"
            saved = client.save_character(character)
            loaded = client.load_character()
            client.disconnect(loaded)

        self.assertEqual(saved["xp"], 0)
        self.assertEqual(loaded["zone"], "backyard")
        self.assertEqual(loaded["name"], "Сетевой воин")

    def test_battle_result_rewards_are_computed_by_server(self):
        with running_server(self.database) as client:
            client.register("fighter", "password")
            client.login("fighter", "password")
            character = client.create_character("Победитель боя")
            result = client.report_battle_result(character["id"], "win", 1, 5, 0)
            self.assertEqual(result["xp"], 20)
            self.assertEqual(result["currency"], {"copper": 10, "silver": 0, "gold": 0})
            self.assertEqual(result["character"]["xp"], character["xp"] + 20)
            self.assertEqual(result["character"]["hp"], 5)
            with self.assertRaisesRegex(ServerError, "уже засчитан"):
                client.report_battle_result(character["id"], "win", 1, 5, 0)

    def test_stat_points_can_be_spent_but_not_created(self):
        with running_server(self.database) as client:
            client.register("statuser", "password")
            client.login("statuser", "password")
            character = client.create_character("Распределитель")
            points = character["stat_points"]
            stats = dict(character["stats"])
            stats["strength"] += points
            saved = client.save_character({**character, "stats": stats, "stat_points": 0})
            self.assertEqual(saved["stats"]["strength"], character["stats"]["strength"] + points)
            self.assertEqual(saved["stat_points"], 0)

            stats = dict(saved["stats"])
            stats["agility"] += 1
            with self.assertRaisesRegex(ServerError, "Характеристики изменяются сервером"):
                client.save_character({**saved, "stats": stats})
            with self.assertRaisesRegex(ServerError, "Характеристики изменяются сервером"):
                client.save_character({**saved, "stat_points": 5})

    def test_client_can_create_duel_application(self):
        with running_server(self.database) as client:
            client.register("appuser", "password")
            client.login("appuser", "password")
            character = client.create_character("Заявитель")
            application = client.create_duel_application(character["id"], "backyard")

        self.assertEqual(application["application"]["sender_id"], character["id"])


if __name__ == "__main__":
    unittest.main()
