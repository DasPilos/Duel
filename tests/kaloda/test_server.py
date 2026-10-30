import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from client.network import ServerError
from kaloda.combat.card_database import Card
from kaloda.server import maintenance
from kaloda.server.database import STARTING_COINS, Database
from kaloda.server.main import GameRequestHandler
from tests.kaloda.server_fixtures import (
    create_second_world,
    create_test_database,
    drop_test_database,
    running_server,
)


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def login(self, client, username, character_name=None, profession="warrior"):
        client.register(username, "password")
        client.login(username, "password")
        return None if character_name is None else client.create_character(character_name, profession)


class TestWorldIsolation(ServerTestCase):
    def test_hp_rescaling_preserves_health_percentage(self):
        self.assertEqual(Database._rescale_hp(45, 100, 45), 20)
        self.assertEqual(Database._rescale_hp(100, 100, 45), 45)

    def test_game_tables_live_in_their_own_schema_and_users_stay_shared(self):
        with self.database.connection() as connection:
            tables = {
                row["table_schema"] + "." + row["table_name"]
                for row in connection.execute(
                    "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = ANY(%s)",
                    ([self.database.schema, self.database.shared_schema],),
                )
            }
        game, shared = self.database.schema, self.database.shared_schema
        for table in ("characters", "items_catalog", "character_card_collection", "chat_messages"):
            self.assertIn(f"{game}.{table}", tables)
        for table in ("users", "sessions", "worlds"):
            self.assertIn(f"{shared}.{table}", tables)
            self.assertNotIn(f"{game}.{table}", tables)
        # у Оператора 1 своя таблица персонажей, и мы её не трогаем
        self.assertIn(f"{shared}.characters", tables)
        user = self.database.register("isolated", "password")
        self.database.create_character(user["id"], "Герой")
        with self.database.shared_database.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) AS amount FROM characters").fetchone()["amount"], 0)

    def test_server_refuses_a_world_that_belongs_to_operator_1(self):
        with self.assertRaisesRegex(RuntimeError, "принадлежит не Колоде"):
            Database(
                self.database.dsn, schema=self.database.schema,
                shared_schema=self.database.shared_schema, world_id=1,
            )

    def test_server_needs_an_explicit_world_and_an_existing_shared_schema(self):
        with patch("kaloda.server.config.WORLD_ID", None), self.assertRaisesRegex(RuntimeError, "KALODA_WORLD_ID"):
            Database(self.database.dsn, schema=self.database.schema, shared_schema=self.database.shared_schema)
        with self.assertRaisesRegex(RuntimeError, "Оператора 1"):
            Database(self.database.dsn, schema="kaloda_unused_test", shared_schema="no_such_shared_schema", world_id=9)

    def test_account_has_one_character_per_world(self):
        user = self.database.register("tester", "password")
        first = self.database.create_character(user["id"], "Воин")
        with self.assertRaisesRegex(ValueError, "уже есть персонаж"):
            self.database.create_character(user["id"], "Маг")

        second_world = create_second_world(self.database)
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

        second_world = create_second_world(self.database)
        self.assertEqual(second_world.create_character(second["id"], "Воин")["name"], "Воин")

    def test_session_is_bound_to_its_world(self):
        self.database.register("traveller", "password")
        token = self.database.login("traveller", "password")["token"]
        second_world = create_second_world(self.database)

        with self.assertRaises(ValueError):
            second_world.user_id_by_token(token)

    def test_server_publishes_its_address_for_the_lobby_and_withdraws_it(self):
        self.database.set_server_url("http://127.0.0.1:8766")
        with self.database.shared_database.connection() as connection:
            row = connection.execute("SELECT server_url FROM worlds WHERE id = %s", (self.database.world_id,)).fetchone()
        self.assertEqual(row["server_url"], "http://127.0.0.1:8766")

        self.database.set_server_url(None)
        with self.database.shared_database.connection() as connection:
            row = connection.execute("SELECT server_url FROM worlds WHERE id = %s", (self.database.world_id,)).fetchone()
        self.assertIsNone(row["server_url"])


class TestAccountsAndCharacters(ServerTestCase):
    def test_password_is_not_accepted_in_plain_text(self):
        self.database.register("tester", "password")
        with self.assertRaises(ValueError):
            self.database.login("tester", "wrong-password")

    def test_online_player_count_deduplicates_accounts_and_ignores_stale_sessions(self):
        self.database.register("online-first", "password")
        self.database.login("online-first", "password")
        self.database.login("online-first", "password")
        self.database.register("online-second", "password")
        second_login = self.database.login("online-second", "password")
        now = time.time()
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE sessions SET last_seen_at = %s WHERE token = %s", (now - 20, second_login["token"]),
            )

        self.assertEqual(self.database.online_player_count(now=now), 1)

    def test_character_is_created_with_seven_stats_and_a_starting_wallet(self):
        user = self.database.register("tester", "password")
        user_id = self.database.user_id_by_token(self.database.login("tester", "password")["token"])
        self.assertEqual(user_id, user["id"])

        created = self.database.create_character(user_id, "Воин")
        saved = self.database.save_character(
            user_id, created["id"], {**created, "hp": created["max_hp"] - 10, "xp": 30, "coins": 999_999},
        )
        loaded = self.database.get_character(user_id, created["id"])

        self.assertEqual(saved["hp"], loaded["hp"])
        self.assertEqual((loaded["xp"], loaded["name"], loaded["zone"]), (30, "Воин", "world_map"))
        self.assertEqual(set(created["stats"]), {
            "strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance",
        })
        self.assertEqual(loaded["coins"], STARTING_COINS)

    def test_every_class_can_be_created_and_unknown_class_is_rejected(self):
        for index, profession in enumerate(("warrior", "archer", "assassin", "mage", "necromancer")):
            user = self.database.register(f"class-{index}", "password")
            character = self.database.create_character(user["id"], f"Герой{index}", profession_type=profession)
            self.assertEqual(character["type"], profession)
        user = self.database.register("class-bad", "password")
        with self.assertRaisesRegex(ValueError, "Профессия"):
            self.database.create_character(user["id"], "Тролль", profession_type="troll")

    def test_necromancer_character_is_persisted_with_class_identity(self):
        user = self.database.register("necromancer-player", "password")

        character = self.database.create_character(user["id"], "Некромант", profession_type="necromancer")

        self.assertEqual((character["type"], character["max_hp"], character["max_mp"]), ("necromancer", 40, 35))

    def test_character_name_is_limited_and_filtered(self):
        user = self.database.register("tester", "password")
        with self.assertRaises(ValueError):
            self.database.create_character(user["id"], "Слишком длинное имя")
        with self.assertRaises(ValueError):
            self.database.create_character(user["id"], "идиот")

    def test_login_applies_offline_regen_before_session_starts(self):
        user = self.database.register("offline_login", "password")
        character = self.database.create_character(user["id"], "Вернувшийся")
        self.database.save_character(user["id"], character["id"], {**character, "hp": 1})
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET updated_at = %s WHERE id = %s", (time.time() - 600, character["id"]),
            )

        self.database.login("offline_login", "password")
        loaded = self.database.get_character(user["id"], character["id"])

        self.assertEqual(loaded["hp"], loaded["max_hp"])

    def test_deleting_character_clears_cached_afk_presence(self):
        from kaloda.server import social

        user = self.database.register("presence-delete", "password")
        character = self.database.create_character(user["id"], "AFK персонаж")
        social.mark_afk("deleted-character-token", user["id"], character)
        self.assertIsNotNone(social.get_character_presence(character["id"]))

        self.database.delete_character(user["id"], character["id"])

        self.assertIsNone(social.get_character_presence(character["id"]))

    def test_deleting_a_character_needs_the_password_and_removes_its_data(self):
        user = self.database.register("deleter", "password")
        character = self.database.create_character(user["id"], "Удаляемый")
        self.database.add_card_to_collection(character["id"], "test_card")
        with self.assertRaisesRegex(ValueError, "Неверный пароль"):
            self.database.delete_character_with_password(user["id"], character["id"], "wrong")

        self.database.delete_character_with_password(user["id"], character["id"], "password")

        self.assertEqual(self.database.get_characters(user["id"]), [])
        with self.database.connection() as connection:
            rows = connection.execute("SELECT 1 FROM character_card_collection WHERE character_id = %s", (character["id"],))
            self.assertEqual(rows.fetchall(), [])

    def test_someone_elses_character_cannot_be_deleted_or_loaded(self):
        owner = self.database.register("owner", "password")
        thief = self.database.register("thief", "password")
        character = self.database.create_character(owner["id"], "Чужой")

        with self.assertRaisesRegex(ValueError, "не найден"):
            self.database.delete_character(thief["id"], character["id"])
        self.assertIsNone(self.database.get_character(thief["id"], character["id"]))


class TestCardCollection(ServerTestCase):
    def test_card_collection_persists_and_stacks_duplicate_cards(self):
        user = self.database.register("collector", "password")
        character = self.database.create_character(user["id"], "Коллекционер")

        first = self.database.add_card_to_collection(character["id"], "test_card")
        second = self.database.add_card_to_collection(character["id"], "test_card")
        collection = self.database.get_card_collection(character["id"])

        self.assertEqual(first["slot_index"], 0)
        self.assertEqual(second["quantity"], 2)
        self.assertEqual(len(collection), 1)
        self.assertEqual((collection[0]["card_key"], collection[0]["quantity"]), ("test_card", 2))

    def test_card_collection_has_sixty_unique_slots(self):
        user = self.database.register("fullcollector", "password")
        character = self.database.create_character(user["id"], "Хранитель")
        for index in range(60):
            self.database.add_card_to_collection(character["id"], f"card_{index}")

        with self.assertRaisesRegex(ValueError, "нет свободных"):
            self.database.add_card_to_collection(character["id"], "overflow")

    def test_client_receives_battle_card_in_collection(self):
        card = Card(
            key="reward_card", name="Наградная карта", group_name="Боец: Тест", resource_type="rage",
            resource_cost=1, effect_type="damage", effect_data={"dice": "1d4"}, drop_chance=100,
            image_path="assets/cards/faces/reward_card.png",
        )
        with running_server(self.database) as client:
            character = self.login(client, "rewarduser", "Победитель")
            with (
                patch("kaloda.server.main.load_cards", return_value=[card]),
                patch("kaloda.server.main.choose_battle_reward", return_value=card),
            ):
                reward = client.award_battle_card(character["id"], ["reward_card"])
                collection = client.get_card_collection(character["id"])

        self.assertEqual(reward["key"], "reward_card")
        self.assertEqual(collection[0]["key"], "reward_card")
        self.assertEqual(collection[0]["quantity"], 1)


class TestHttpApi(ServerTestCase):
    def test_client_api_round_trip(self):
        with running_server(self.database) as client:
            character = self.login(client, "apiuser", "Сетевой воин")
            with self.assertRaisesRegex(ServerError, "Опыт начисляется сервером"):
                client.save_character({**character, "xp": 30})
            character["zone"] = "backyard"
            saved = client.save_character(character)
            loaded = client.load_character()
            client.disconnect(loaded)

        self.assertEqual(saved["xp"], 0)
        self.assertEqual((loaded["zone"], loaded["name"]), ("backyard", "Сетевой воин"))

    def test_server_introduces_itself_and_serves_the_map(self):
        with running_server(self.database) as client:
            self.login(client, "info-user")
            info = client.get_game_info()
            terrain = client.get_map_terrain()

        self.assertEqual(info, {"game": "kaloda", "world_id": self.database.world_id})
        self.assertEqual(terrain["objects"][0]["id"], "crystal_of_life")
        self.assertNotIn("city_visual_state", terrain)

    def test_game_calls_require_a_session_and_unknown_routes_are_404(self):
        with running_server(self.database) as client:
            with self.assertRaisesRegex(ServerError, "не авторизован"):
                client.get_card_shop_catalog()
            self.login(client, "routes")
            with self.assertRaisesRegex(ServerError, "Маршрут не найден"):
                client._request("GET", "/api/kaloda/no-such-route", authenticated=True)
            with self.assertRaisesRegex(ServerError, "Маршрут не найден"):
                client._request("GET", "/api/castle/1/population", authenticated=True)

    def test_missing_fields_and_foreign_characters_are_reported_clearly(self):
        with running_server(self.database) as client:
            self.login(client, "bad-request", "Игрок")
            with self.assertRaisesRegex(ServerError, "Не указано поле"):
                client._request("POST", "/api/inventory/move", {"character_id": 1}, authenticated=True)
            with self.assertRaisesRegex(ServerError, "Персонаж не найден"):
                client.get_card_collection(987654)

    def test_server_status_counts_players_and_restart_control_requires_moderator(self):
        maintenance.cancel_restart()
        with running_server(self.database) as client:
            self.login(client, "statususer")
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

    def test_stat_points_can_be_spent_while_respecting_stat_gates(self):
        with running_server(self.database) as client:
            character = self.login(client, "statuser", "Распределитель")
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
                (saved["stats"]["strength"], saved["stats"]["agility"], saved["stats"]["intuition"]), (4, 4, 4),
            )
            self.assertEqual(saved["stat_points"], 0)

            stats = dict(saved["stats"])
            stats["agility"] += 1
            with self.assertRaisesRegex(ServerError, "Характеристики изменяются сервером"):
                client.save_character({**saved, "stats": stats})
            with self.assertRaisesRegex(ServerError, "Характеристики изменяются сервером"):
                client.save_character({**saved, "stat_points": 5})

    def test_client_cannot_raise_its_own_wallet(self):
        with running_server(self.database) as client:
            character = self.login(client, "rich", "Богач")
            with self.assertRaisesRegex(ServerError, "Валюта начисляется сервером"):
                client.save_character({**character, "coins": character["coins"] + 5})
            self.assertEqual(client.load_character()["coins"], character["coins"])

    def test_talent_choice_is_validated_by_the_server(self):
        with running_server(self.database) as client:
            character = self.login(client, "talents", "Талантливый")
            with self.assertRaisesRegex(ServerError, "уровень персонажа недостаточен"):
                client.choose_character_talent(character["id"], 2, "anything")
            with self.assertRaisesRegex(ServerError, "от 1 до 10"):
                client.choose_character_talent(character["id"], 11, "anything")

    def test_buying_a_drink_heals_and_charges_the_wallet(self):
        with running_server(self.database) as client:
            character = self.login(client, "drinker", "Выпивоха")
            self.database.save_character(
                client_user_id(self.database, "drinker"), character["id"], {**character, "hp": 10},
            )
            drink = client.list_drinks()[0]
            self.assertEqual(drink["price_coins"], 20)

            bought = client.buy_drink(character["id"], drink["id"])["character"]

        self.assertEqual(bought["coins"], STARTING_COINS - 20)
        self.assertGreater(bought["hp"], 10)

    def test_drink_is_refused_at_full_health_and_without_money(self):
        with running_server(self.database) as client:
            character = self.login(client, "sober", "Трезвенник")
            drink = client.list_drinks()[0]
            with self.assertRaisesRegex(ServerError, "БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ"):
                client.buy_drink(character["id"], drink["id"])

            user_id = client_user_id(self.database, "sober")
            self.database.save_character(user_id, character["id"], {**character, "hp": 1})
            with self.database.connection() as connection:
                connection.execute(
                    "UPDATE characters SET coins = 0 WHERE id = %s", (character["id"],),
                )
            with self.assertRaisesRegex(ServerError, "Недостаточно денег"):
                client.buy_drink(character["id"], drink["id"])

        history = self.database.get_chat_history(character["id"], "tavern")
        self.assertTrue(any(message["sender"] == "Хозяин трактира" for message in history))


def client_user_id(database, username):
    with database.connection() as connection:
        return connection.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()["id"]


class TestChat(ServerTestCase):
    def test_chat_message_payload_formats_server_time_in_kiev(self):
        created_at = datetime(2025, 1, 1, 22, 59, 59, tzinfo=timezone.utc).timestamp()
        payload = Database._chat_message_payload({
            "id": 1, "location": "tavern", "sender_character_id": 2, "sender_name": "Игрок",
            "recipient_character_id": None, "text": "Привет", "created_at": created_at,
        })

        self.assertEqual(payload["time_text"], "00:59:59")

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
            character = self.login(client, "chatuser", "Собеседник")
            message = client.send_message(character["id"], "tavern", "Привет")
            history = client.list_messages("tavern", character["id"])

        self.assertEqual(message["message"]["text"], "Привет")
        self.assertEqual(history[-1]["text"], "Привет")

    def test_chat_rooms_are_limited_to_the_kaloda_locations(self):
        with running_server(self.database) as client:
            character = self.login(client, "rooms", "Комнатный")
            for location in ("tavern", "world_map", "backyard", "character_room"):
                client.send_message(character["id"], location, f"в {location}")
            for location in ("city", "hub", "somewhere"):
                with self.assertRaisesRegex(ServerError, "Неизвестная локация"):
                    client.send_message(character["id"], location, "нельзя")
            with self.assertRaisesRegex(ServerError, "только сервер"):
                client.send_message(character["id"], "world", "Поддельное объявление")

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

    def test_chat_history_discards_messages_older_than_48_hours(self):
        user = self.database.register("history_ttl", "password")
        character = self.database.create_character(user["id"], "История")
        old_message = self.database.add_chat_message(character["id"], "tavern", "старое")
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE chat_messages SET created_at = %s WHERE id = %s",
                (time.time() - 48 * 60 * 60 - 1, old_message["id"]),
            )
        self.database.add_chat_message(character["id"], "tavern", "новое")

        history = self.database.get_chat_history(character["id"], "tavern")

        self.assertEqual([item["text"] for item in history], ["новое"])

    def test_world_announcements_are_visible_in_every_location_and_server_only(self):
        with running_server(self.database) as client:
            character = self.login(client, "world-announcement-reader", "Читатель")
            narrator_id = self.database.ensure_bot_character("world-narrator-test", "Летописец")
            self.database.add_chat_message(narrator_id, "world", "В Колоде объявлен новый сезон.")

            for location in ("tavern", "backyard", "world_map", "character_room"):
                messages = client.list_messages(location, character["id"])
                self.assertTrue(any(message["text"] == "В Колоде объявлен новый сезон." for message in messages))

    def test_private_messages_are_visible_only_to_the_two_participants(self):
        first = self.database.create_character(self.database.register("pm-first", "password")["id"], "Первый")
        second = self.database.create_character(self.database.register("pm-second", "password")["id"], "Второй")
        third = self.database.create_character(self.database.register("pm-third", "password")["id"], "Третий")
        self.database.add_chat_message(first["id"], "tavern", "тайна", recipient_id=second["id"])

        seen = {
            name: [item["text"] for item in self.database.get_chat_history(character["id"], "tavern")]
            for name, character in (("first", first), ("second", second), ("third", third))
        }

        self.assertEqual(seen, {"first": ["тайна"], "second": ["тайна"], "third": []})

    def test_only_moderators_can_delete_and_mute(self):
        user = self.database.register("muted", "password")
        character = self.database.create_character(user["id"], "Болтун")
        message = self.database.add_chat_message(character["id"], "tavern", "спам")
        with self.assertRaisesRegex(ValueError, "Недостаточно прав"):
            self.database.delete_chat_message(message["id"], user["id"])
        with self.assertRaisesRegex(ValueError, "Недостаточно прав"):
            self.database.mute_character(character["id"], character["id"], user["id"])

        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (user["id"],))
        self.database.mute_character(character["id"], character["id"], user["id"], seconds=60)
        self.database.delete_chat_message(message["id"], user["id"])

        self.assertTrue(self.database.is_muted(character["id"], "tavern"))
        self.assertEqual(self.database.get_chat_history(character["id"], "tavern"), [])


class TestBattleRewards(ServerTestCase):
    def test_battle_result_rewards_are_computed_by_server(self):
        with running_server(self.database) as client:
            character = self.login(client, "fighter", "Победитель боя")
            result = client.report_battle_result(character["id"], "win", 1, 5, 0)
            self.assertEqual(result["xp"], 20)
            self.assertEqual(result["currency"], {"coins": 0})
            self.assertEqual(result["character"]["level"], 2)
            self.assertEqual(result["character"]["xp"], 0)
            self.assertEqual(result["character"]["hp"], 5)
            with self.assertRaisesRegex(ServerError, "уже засчитан"):
                client.report_battle_result(character["id"], "win", 1, 5, 0)

    def test_battle_result_does_not_change_the_wallet(self):
        with running_server(self.database) as client:
            character = self.login(client, "payout", "Победитель")
            result = client.report_battle_result(character["id"], "win", 1, character["hp"], character["mp"])

        self.assertEqual(result["character"]["coins"], character["coins"])

    def test_guild_quest_reward_is_claimed_once_and_idempotent(self):
        with running_server(self.database) as client:
            character = self.login(client, "guild-quest", "Искатель")
            first = client.claim_guild_quest_reward(character["id"], "kill_kobold", "quest-completion-1")
            retry = client.claim_guild_quest_reward(character["id"], "kill_kobold", "quest-completion-1")
            duplicate = client.claim_guild_quest_reward(character["id"], "kill_kobold", "quest-completion-2")

        self.assertEqual(first["reward_coins"], 10)
        self.assertFalse(first["already_claimed"])
        self.assertEqual(retry["character"]["coins"], character["coins"] + 10)
        self.assertFalse(retry["already_claimed"])
        self.assertEqual(duplicate["reward_coins"], 0)
        self.assertTrue(duplicate["already_claimed"])

    def test_guild_quest_rewards_match_the_quest_book(self):
        from kaloda.quests import QUESTS_BY_ID

        with running_server(self.database) as client:
            character = self.login(client, "guild-rewards", "Искатель")
            for quest_id, quest in QUESTS_BY_ID.items():
                result = client.claim_guild_quest_reward(character["id"], quest_id, f"completion-{quest_id}")
                self.assertEqual(result["reward_coins"], quest.reward_coins, quest_id)
            with self.assertRaisesRegex(ServerError, "Неизвестное задание"):
                client.claim_guild_quest_reward(character["id"], "no_such_quest", "x-1")

    def test_world_npc_kill_xp_uses_server_rewards_and_is_idempotent(self):
        with running_server(self.database) as client:
            character = self.login(client, "npc-xp", "Охотник")
            request_id = "dbe82a31-8408-4500-a8a7-7100248da512"
            first = client.claim_npc_kill_xp(
                character["id"], "dungeon_room_3", ["skeleton", "necromancer"], request_id,
            )
            with self.assertRaisesRegex(ServerError, "уже начислен"):
                client.claim_npc_kill_xp(
                    character["id"], "dungeon_room_3", ["skeleton", "necromancer"], request_id,
                )
            with self.assertRaisesRegex(ServerError, "нельзя победить"):
                client.claim_npc_kill_xp(
                    character["id"], "kobold", ["necromancer"], "6a6e2b3c-5b6d-4b43-9f43-5b0d6e3c4f10",
                )

        self.assertEqual(first["xp"], 55)
        self.assertEqual(first["levels_gained"], 1)
        self.assertEqual((first["character"]["level"], first["character"]["xp"]), (2, 35))
        self.assertEqual(first["character"]["stat_points"], 10)

    def test_battle_result_persists_replay_in_server_archive(self):
        replay = {
            "id": "archive-test-battle", "timestamp": 1234.0, "source": "duel_scene", "turns": 2,
            "winner": "Архивный герой",
            "player": {"name": "Архивный герой", "level": 1, "stats": {}, "hp": 5, "max_hp": 10},
            "enemy": {"name": "Соперник", "level": 1, "stats": {}, "hp": 0, "max_hp": 10},
        }
        with running_server(self.database) as client:
            character = self.login(client, "archive-user", "Архивный герой")
            result = client.report_battle_result(character["id"], "win", 1, 5, 0, battle_record=replay)
            repeated = self.database.save_battle_archive(character["id"], None, "win", replay)

        self.assertEqual(repeated, result["battle_archive_id"])
        with self.database.connection() as connection:
            row = connection.execute("SELECT outcome, replay_json FROM battle_archive").fetchone()
        self.assertEqual((row["outcome"], row["replay_json"]), ("win", replay))

    def test_invalid_replay_is_rejected(self):
        user = self.database.register("bad-replay", "password")
        character = self.database.create_character(user["id"], "Фальсификатор")
        with self.assertRaisesRegex(ValueError, "Некорректная запись боя"):
            self.database.save_battle_archive(character["id"], None, "win", {"no": "id"})
        with self.assertRaisesRegex(ValueError, "Некорректный исход боя"):
            self.database.save_battle_archive(character["id"], None, "won", {"id": "x"})


if __name__ == "__main__":
    unittest.main()
