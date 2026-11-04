import time
import threading
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from client.network import ServerError
from combat.card_database import Card, DECK_SIZE, cards_for_type
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

    def test_hp_rescaling_preserves_health_percentage(self):
        self.assertEqual(Database._rescale_hp(45, 100, 45), 20)
        self.assertEqual(Database._rescale_hp(100, 100, 45), 45)

    def test_removed_city_progression_tables_are_absent(self):
        retired_tables = {
            "city_population_state", "city_citizens", "building_states",
            "building_resources", "building_worker_slots", "building_upgrade_materials",
            "building_player_resources", "stable_horses", "stable_cart_progress",
            "transport_convoys", "forge_orders",
        }
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = ANY(%s)",
                (self.database.schema, list(retired_tables)),
            ).fetchall()
        self.assertEqual({row["table_name"] for row in rows}, set())

    def test_retired_city_api_is_closed_but_map_terrain_is_available(self):
        with running_server(self.database) as client:
            client.register("retiredcity", "password")
            client.login("retiredcity", "password")
            with self.assertRaises(ServerError):
                client._request(
                    "GET", "/api/castle/1/population", authenticated=True
                )
            terrain = client.get_map_terrain()
            self.assertNotIn("city_visual_state", terrain)
            self.assertEqual(terrain["objects"][0]["id"], "crystal_of_life")

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
            status = client.get_server_status()
            self.assertEqual(status["online_players"], 1)
            self.assertIsNone(status["restart_notice"])
            self.assertEqual(status["server_timezone"], "Europe/Kyiv")
            self.assertAlmostEqual(status["server_time"], time.time(), delta=2)
            with self.assertRaisesRegex(ServerError, "Недостаточно прав"):
                client.schedule_server_restart()

            with self.database.connection() as connection:
                connection.execute("UPDATE users SET role = 'moderator' WHERE username = %s", ("statususer",))

            notice = client.schedule_server_restart()
            self.assertEqual(notice["seconds_remaining"], 180)
            self.assertIn("обновление", notice["message"])
            self.assertIsNone(client.cancel_server_restart())
        self.assertIsNone(maintenance.public_notice())

    def test_online_player_count_deduplicates_accounts_and_ignores_stale_sessions(self):
        self.database.register("online-first", "password")
        self.database.login("online-first", "password")
        self.database.login("online-first", "password")
        second = self.database.register("online-second", "password")
        second_login = self.database.login("online-second", "password")
        now = time.time()
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE sessions SET last_seen_at = %s WHERE token = %s",
                (now - 20, second_login["token"]),
            )

        self.assertEqual(self.database.online_player_count(now=now), 1)

    def test_character_is_created_and_loaded(self):
        user = self.database.register("tester", "password")
        login = self.database.login("tester", "password")
        user_id = self.database.user_id_by_token(login["token"])
        self.assertEqual(user_id, user["id"])

        created = self.database.create_character(user_id, "Воин")
        saved = self.database.save_character(
            user_id,
            created["id"],
            {**created, "hp": created["max_hp"] - 10, "xp": 30, "coins": 999},
        )
        loaded = self.database.get_character(user_id, created["id"])

        self.assertEqual(saved["hp"], loaded["hp"])
        self.assertEqual(loaded["xp"], 30)
        self.assertEqual(loaded["name"], "Воин")
        self.assertEqual(created["coins"], 100)
        self.assertEqual(loaded["coins"], 100)

    def test_necromancer_character_is_persisted_with_class_identity(self):
        user = self.database.register("necromancer-player", "password")

        character = self.database.create_character(
            user["id"], "Некромант", profession_type="necromancer"
        )

        self.assertEqual(character["type"], "necromancer")
        self.assertEqual(character["max_hp"], 40)
        self.assertEqual(character["max_mp"], 35)

    def test_deleting_character_clears_cached_afk_presence(self):
        user = self.database.register("presence-delete", "password")
        character = self.database.create_character(user["id"], "AFK персонаж")
        social.mark_afk("deleted-character-token", user["id"], character)
        self.assertIsNotNone(social.get_character_presence(character["id"]))

        self.database.delete_character(user["id"], character["id"])

        self.assertIsNone(social.get_character_presence(character["id"]))

    def test_legacy_mage_types_are_migrated_to_the_single_mage_class(self):
        user = self.database.register("legacy-mage", "password")
        character = self.database.create_character(
            user["id"], "Старый маг", profession_type="support_mage"
        )
        self.assertEqual(character["type"], "mage")

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET type = %s WHERE id = %s",
                ("harmonist", character["id"]),
            )
            self.database._normalize_character_stats(connection)
            stored_type = connection.execute(
                "SELECT type FROM characters WHERE id = %s",
                (character["id"],),
            ).fetchone()["type"]
        self.assertEqual(stored_type, "mage")
        self.assertEqual(stored_type, "mage")

    def test_chat_message_payload_formats_server_time_in_kiev(self):
        created_at = datetime(2025, 1, 1, 22, 59, 59, tzinfo=timezone.utc).timestamp()
        payload = Database._chat_message_payload({
            "id": 1,
            "location": "tavern",
            "sender_character_id": 2,
            "sender_name": "Игрок",
            "recipient_character_id": None,
            "text": "Привет",
            "created_at": created_at,
        })

        self.assertEqual(payload["time_text"], "00:59:59")

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
            with self.database.connection() as connection:
                starter_items = connection.execute(
                    "SELECT item_id FROM character_items WHERE character_id = %s ORDER BY item_id",
                    (character["id"],),
                ).fetchall()
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
        self.assertEqual(starter_items, [])
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
        warrior_ids = {
            bot["id"] for bot in world.BOT_OPPONENTS
            if bot.get("type", "warrior") == "warrior"
        }
        self.assertTrue(all(
            item.get("type", "warrior") == "warrior"
            for item in world.get_bot_opponents()
            if item["id"] in warrior_ids
        ))
        warrior_cards = cards_for_type("warrior")
        self.assertEqual(len(warrior_cards), DECK_SIZE)
        self.assertTrue(all(card.group_name == "Боец: Стиль Валентайна" for card in warrior_cards))
        archer = bots["Ельпачино Фред"]
        self.assertEqual(archer["type"], "archer")
        self.assertEqual(archer["max_hp"], 65)
        archer_cards = cards_for_type(archer["type"])
        self.assertEqual(len(archer_cards), DECK_SIZE)
        self.assertTrue(all(card.group_name == "Лучник: Проворный герой" for card in archer_cards))
        self.assertEqual(set(archer["deck"]), {card.key for card in archer_cards})
        archer_fighter = world._fighter_from_profile(archer)
        self.assertEqual(archer_fighter.unique_resource_type, "accuracy")
        self.assertEqual(archer_fighter.max_hp, 65)

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

    def test_plowman_hp_uses_warrior_base_health(self):
        user = self.database.register("hpcheck", "password")
        plowman = next(
            opponent
            for opponent in self.database.get_opponents(user["id"])
            if opponent["id"] == "bot_plowman"
        )

        self.assertEqual((plowman["hp"], plowman["max_hp"]), (140, 140))

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
            character["max_hp"] = 110
            character["hp"] = 110
            character = self.database.save_character(user_id, character["id"], character)
            with self.assertRaises(ServerError):
                client.offer_duel(character["id"], "backyard", "bot_brawler")

            character.update({"level": 1})
            character["stats"]["endurance"] = 3
            character["max_hp"] = 100
            character["hp"] = 100
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
            self.assertEqual(result["currency"], {"coins": 0})
            self.assertEqual(result["character"]["level"], 2)
            self.assertEqual(result["character"]["xp"], 0)
            self.assertEqual(result["character"]["hp"], 5)
            with self.assertRaisesRegex(ServerError, "уже засчитан"):
                client.report_battle_result(character["id"], "win", 1, 5, 0)

    def test_guild_quest_reward_is_claimed_once_and_idempotent(self):
        with running_server(self.database) as client:
            client.register("guild-quest", "password")
            client.login("guild-quest", "password")
            character = client.create_character("Искатель")
            initial_coins = character["coins"]
            first = client.claim_guild_quest_reward(
                character["id"], "kill_kobold", "quest-completion-1"
            )
            retry = client.claim_guild_quest_reward(
                character["id"], "kill_kobold", "quest-completion-1"
            )
            duplicate = client.claim_guild_quest_reward(
                character["id"], "kill_kobold", "quest-completion-2"
            )

        self.assertEqual(first["reward_coins"], 10)
        self.assertFalse(first["already_claimed"])
        self.assertEqual(retry["character"]["coins"], initial_coins + 10)
        self.assertFalse(retry["already_claimed"])
        self.assertEqual(duplicate["reward_coins"], 0)
        self.assertTrue(duplicate["already_claimed"])

    def test_guild_ent_and_dungeon_rewards_use_new_coin_values(self):
        with running_server(self.database) as client:
            client.register("guild-rewards", "password")
            client.login("guild-rewards", "password")
            character = client.create_character("Искатель")
            for quest_id, request_id, expected in (
                ("kill_ancient_ent", "ent-quest-completion", 160),
                ("clear_dungeon", "dungeon-quest-completion", 780),
            ):
                result = client.claim_guild_quest_reward(
                    character["id"], quest_id, request_id
                )
                self.assertEqual(result["reward_coins"], expected)

    def test_new_card_shop_uses_coins_and_sells_cards_for_rarity_price(self):
        with running_server(self.database) as client:
            client.register("coin-card-shop", "password")
            client.login("coin-card-shop", "password")
            character = client.create_character("Коллекционер")
            catalog = {card["key"]: card for card in client.get_card_shop_catalog()}

            self.assertEqual(catalog["universal_divine_healing"]["price_coins"], 75)
            self.assertTrue(catalog["universal_divine_healing"]["available"])
            self.assertEqual(catalog["universal_trap"]["price_coins"], 50)
            self.assertEqual(catalog["universal_trap"]["rarity"], "common")
            self.assertTrue(catalog["universal_trap"]["available"])

            result = client.buy_card(character["id"], "universal_divine_healing")
            self.assertEqual(result["character"]["coins"], 25)
            sold = client.sell_card(character["id"], "universal_divine_healing")
            self.assertEqual(sold["sale_price_coins"], 50)
            self.assertEqual(sold["character"]["coins"], 75)
            collection = client.get_card_collection(character["id"])
            self.assertNotIn(
                "universal_divine_healing",
                {entry["card_key"] for entry in collection},
            )
            bought_common = client.buy_card(character["id"], "universal_trap")
            self.assertEqual(bought_common["character"]["coins"], 25)
            sold_common = client.sell_card(character["id"], "universal_trap")
            self.assertEqual(sold_common["sale_price_coins"], 15)
            self.assertEqual(sold_common["character"]["coins"], 40)

    def test_supplies_shop_prices_and_coin_purchase(self):
        with running_server(self.database) as client:
            client.register("coin-supplies-shop", "password")
            client.login("coin-supplies-shop", "password")
            character = client.create_character("Покупатель")
            catalog = client.get_supplies_shop_catalog()

            self.assertEqual(
                {item["item_id"]: item["price_coins"] for item in catalog},
                {4: 15, 5: 15, 6: 5, 7: 45, 52: 60},
            )
            result = client.buy_supplies_item(character["id"], 4)

        self.assertEqual(result["character"]["coins"], character["coins"] - 15)
        self.assertIn(4, {item["item_id"] for item in result["inventory"]["inventory"]})

    def test_dungeon_treasure_is_server_owned_and_idempotent(self):
        rewards = {
            "coins": 830,
            "items": [
                {"item_id": 901, "name": "Карта скелета-стража", "quantity": 1},
                {"item_id": 902, "name": "Статуя короля скелетов", "quantity": 1},
                {"item_id": 901, "name": "Карта скелета-стража", "quantity": 2},
                {"item_id": 903, "name": "Копьё скелета-стража", "quantity": 1},
                {"item_id": 904, "name": "Карта короля скелетов", "quantity": 1},
                {"item_id": 905, "name": "Корона короля скелетов", "quantity": 1},
                {"item_id": 906, "name": "Наследие павшего короля", "quantity": 1},
            ],
        }
        with running_server(self.database) as client:
            client.register("dungeon-treasure", "password")
            client.login("dungeon-treasure", "password")
            character = client.create_character("Искатель")
            initial_coins = character["coins"]
            request_id = "bc2fdcb1-5ac5-4630-a1e8-26e3906a57e1"
            with patch("server.items_database.roll_dungeon_treasure", return_value=rewards):
                first = client.claim_dungeon_treasure(character["id"], request_id)
                retry = client.claim_dungeon_treasure(character["id"], request_id)

        self.assertEqual(first["character"]["coins"], initial_coins + 830)
        self.assertEqual(retry["character"]["coins"], initial_coins + 830)
        self.assertEqual(first["rewards"], retry["rewards"])
        quantities = {
            item["item_id"]: item["quantity"] for item in first["inventory"]["inventory"]
        }
        self.assertEqual(quantities[901], 3)
        self.assertEqual(quantities[902], 1)
        self.assertEqual(quantities[906], 1)

    def test_world_npc_kill_xp_uses_server_rewards_and_is_idempotent(self):
        with running_server(self.database) as client:
            client.register("npc-xp", "password")
            client.login("npc-xp", "password")
            character = client.create_character("Охотник")
            request_id = "dbe82a31-8408-4500-a8a7-7100248da512"
            first = client.claim_npc_kill_xp(
                character["id"],
                "dungeon_room_3",
                ["skeleton", "necromancer"],
                request_id,
            )
            with self.assertRaisesRegex(ServerError, "уже начислен"):
                client.claim_npc_kill_xp(
                    character["id"],
                    "dungeon_room_3",
                    ["skeleton", "necromancer"],
                    request_id,
                )

        self.assertEqual(first["xp"], 55)
        self.assertEqual(first["levels_gained"], 1)
        self.assertEqual(first["character"]["level"], 2)
        self.assertEqual(first["character"]["xp"], 35)
        self.assertEqual(first["character"]["stat_points"], 10)

    def test_battle_result_persists_replay_in_server_archive(self):
        replay = {
            "id": "hall-of-fame-test-battle",
            "timestamp": 1234.0,
            "source": "duel_scene",
            "turns": 2,
            "winner": "Архивный герой",
            "player": {"name": "Архивный герой", "level": 1, "stats": {}, "hp": 5, "max_hp": 10},
            "enemy": {"name": "Соперник", "level": 1, "stats": {}, "hp": 0, "max_hp": 10},
            "stats": {"player": {}, "enemy": {}},
            "hands": {"player": ["first_card"], "enemy": ["second_card"]},
            "history": [{"turn": 1, "events": [{"side": "player", "card": "first_card"}]}],
        }
        with running_server(self.database) as client:
            client.register("hall-archive-user", "password")
            client.login("hall-archive-user", "password")
            character = client.create_character("Архивный герой")
            result = client.report_battle_result(
                character["id"], "win", 1, 5, 0, battle_record=replay,
            )
            page = client.list_battle_archive(limit=10, offset=0)
            detail = client.get_battle_archive_record(result["battle_archive_id"])

        self.assertEqual(page["total"], 1)
        self.assertEqual(page["battles"][0]["player_name"], "Архивный герой")
        self.assertEqual(detail["replay_json"], replay)
        self.assertEqual(detail["outcome"], "win")

    def test_legacy_backyard_currency_rewards_are_disabled(self):
        cases = (
            ("payout-equal", 1, 1),
            ("payout-higher", 2, 1),
            ("payout-lower", 1, 2),
        )
        with running_server(self.database) as template_client:
            for index, (username, player_level, opponent_level) in enumerate(cases):
                client = type(template_client)(template_client.base_url)
                client.register(username, "password")
                client.login(username, "password")
                character = client.create_character(f"Hero{index}")
                if player_level != character["level"]:
                    with self.database.connection() as connection:
                        connection.execute(
                            "UPDATE characters SET level=%s WHERE id=%s",
                            (player_level, character["id"]),
                        )
                result = client.report_battle_result(
                    character["id"], "win", opponent_level, character["hp"], character["mp"],
                )
                self.assertEqual(result["currency"], {"coins": 0})
                self.assertEqual(result["character"]["coins"], 100)

    def test_human_battle_result_queues_local_chat_commentary(self):
        with running_server(self.database) as attacker_client:
            attacker_client.register("commentator-attacker", "password")
            attacker_client.login("commentator-attacker", "password")
            attacker = attacker_client.create_character("Лучник")

            defender_client = type(attacker_client)(attacker_client.base_url)
            defender_client.register("commentator-defender", "password")
            defender_client.login("commentator-defender", "password")
            defender = defender_client.create_character("Страж")

            with patch("server.main.enqueue_battle_comment") as enqueue:
                attacker_client.report_battle_result(
                    attacker["id"], "win", defender["level"], attacker["hp"], attacker["mp"],
                    opponent_id=defender["id"], opponent_hp=defender["hp"],
                    opponent_mp=defender["mp"],
                )

        enqueue.assert_called_once_with(
            self.database, attacker["id"], defender["id"], "win",
        )

    def test_world_announcements_are_visible_in_every_location_and_server_only(self):
        with running_server(self.database) as client:
            client.register("world-announcement-reader", "password")
            client.login("world-announcement-reader", "password")
            character = client.create_character("Читатель")
            narrator_id = self.database.ensure_bot_character("world-narrator-test", "Летописец")
            self.database.add_chat_message(
                narrator_id,
                "world",
                "Запасы зерна в городе подходят к концу.",
            )

            for location in ("tavern", "city", "backyard", "world_map", "character_room"):
                messages = client.list_messages(location, character["id"])
                self.assertTrue(any(message["text"] == "Запасы зерна в городе подходят к концу." for message in messages))

            with self.assertRaisesRegex(ServerError, "только сервер"):
                client.send_message(character["id"], "world", "Поддельное объявление")

    def test_stat_points_can_be_spent_while_respecting_stat_gates(self):
        with running_server(self.database) as client:
            client.register("statuser", "password")
            client.login("statuser", "password")
            character = client.create_character("Распределитель")
            stats = dict(character["stats"])
            stats["strength"] += 2
            saved = client.save_character({**character, "stats": stats, "stat_points": 4})
            stats = dict(saved["stats"])
            stats["agility"] += 2
            saved = client.save_character({**saved, "stats": stats, "stat_points": 2})
            stats = dict(saved["stats"])
            stats["intuition"] += 2
            saved = client.save_character({**saved, "stats": stats, "stat_points": 0})

            self.assertEqual(
                (saved["stats"]["strength"], saved["stats"]["agility"], saved["stats"]["intuition"]),
                (4, 4, 4),
            )
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
