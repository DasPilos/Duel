"""HTTP-сервер мира Колоды.

Один процесс — один мир. Номер мира берётся из KALODA_WORLD_ID, а код этого мира в общей таблице `worlds`
должен начинаться с «kaloda». Запуск: `python -m kaloda.server.main`.
"""

import json
import os
import re
import threading
import time
import traceback
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from kaloda.combat.card_database import (
    card_allowed_for,
    card_to_dict,
    choose_battle_reward,
    class_cards_for_type,
    deck_validation_error,
    load_cards,
)
from kaloda.combat.character_stats import STAT_DEPENDENTS, stat_supports_met
from kaloda.server import bots, config, maintenance, social
from kaloda.server.database import Database
from kaloda.server.items_database import ItemsDatabase
from kaloda.world_map import terrain_payload

API = "/api/kaloda"
CHAT_LOCATIONS = ("tavern", "world_map", "backyard", "character_room")
DIRECTIONS = {"n", "ne", "e", "se", "s", "sw", "w", "nw"}
PROFESSIONS = ("warrior", "archer", "assassin", "mage", "necromancer")

# (метод, путь, обработчик). Группы в пути передаются обработчику аргументами после тела запроса.
ROUTES = (
    ("GET", "/health", "_health"),
    ("GET", "/api/server/status", "_server_status"),
    ("POST", "/api/server/restart-notice", "_restart_notice"),
    ("POST", "/api/register", "_register"),
    ("POST", "/api/login", "_login"),
    ("POST", "/api/sessions/disconnect", "_disconnect"),
    # персонажи
    ("GET", "/api/characters", "_list_characters"),
    ("GET", "/api/characters/me", "_my_character"),
    ("POST", "/api/characters", "_create_character"),
    ("GET", r"/api/characters/(\d+)", "_get_character"),
    ("PUT", r"/api/characters/(\d+)", "_save_character"),
    ("POST", r"/api/characters/(\d+)/delete", "_delete_character"),
    # рюкзак, экипировка, хранилище
    ("GET", r"/api/inventory/(\d+)", "_get_inventory"),
    ("GET", r"/api/equipment/(\d+)", "_get_equipment"),
    ("GET", r"/api/storage/(\d+)/(\w+)", "_get_storage"),
    ("POST", r"/api/((?:inventory/(?:move|use|drop|remove))|(?:equipment/(?:equip|unequip)))", "_inventory_action"),
    ("GET", "/api/items/catalog", "_catalog_items"),
    # таверна
    ("GET", "/api/drinks", "_drinks"),
    ("POST", "/api/character/buy_drink", "_buy_drink"),
    # присутствие и чат
    ("POST", "/api/social/presence", "_presence"),
    ("GET", "/api/social/occupants", "_occupants"),
    ("GET", "/api/chat/history", "_chat_history"),
    ("GET", "/api/chat/unread", "_chat_unread"),
    ("POST", "/api/chat/messages", "_chat_message"),
    ("POST", "/api/chat/read", "_chat_read"),
    ("POST", "/api/chat/report", "_chat_report"),
    ("POST", "/api/chat/delete", "_chat_delete"),
    ("POST", "/api/chat/mute", "_chat_mute"),
    # игра Колоды
    ("GET", f"{API}/info", "_info"),
    ("GET", f"{API}/map/terrain", "_map_terrain"),
    ("GET", f"{API}/items", "_item_catalog"),
    ("GET", f"{API}/supplies-shop", "_supplies_shop"),
    ("POST", f"{API}/supplies-shop/buy", "_buy_supplies"),
    ("GET", f"{API}/card-shop", "_card_shop"),
    ("POST", f"{API}/card-shop/buy", "_buy_card"),
    ("GET", f"{API}/dungeon/card-shop", "_dungeon_card_shop"),
    ("POST", f"{API}/dungeon/card-shop/buy", "_buy_dungeon_card"),
    ("POST", f"{API}/dungeon/treasure", "_dungeon_treasure"),
    ("POST", f"{API}/npc-kills", "_npc_kills"),
    ("POST", f"{API}/guild/quest-reward", "_guild_quest_reward"),
    ("POST", f"{API}/talents/choose", "_choose_talent"),
    ("GET", rf"{API}/card-collection/(\d+)", "_card_collection_route"),
    ("GET", rf"{API}/decks/(\d+)", "_get_decks"),
    ("POST", f"{API}/decks", "_create_deck"),
    ("DELETE", rf"{API}/decks/(\d+)", "_delete_deck"),
    ("POST", f"{API}/battle/result", "_battle_result"),
    ("POST", f"{API}/battle/card-reward", "_battle_card_reward"),
    ("GET", f"{API}/opponents", "_opponents"),
    ("PUT", rf"{API}/opponents/(.+)", "_save_opponent"),
    # игроки рядом: заявки на бой
    ("GET", f"{API}/social/snapshot", "_social_snapshot"),
    ("GET", f"{API}/social/offers", "_social_offers"),
    ("POST", f"{API}/social/duel-offers", "_duel_offer"),
    ("POST", f"{API}/social/duel-offers/respond", "_duel_offer_respond"),
    ("POST", f"{API}/social/duel-applications", "_duel_application"),
    ("POST", f"{API}/social/duel-applications/cancel", "_duel_application_cancel"),
    ("GET", f"{API}/social/group-battles", "_group_battles"),
    ("POST", f"{API}/social/group-battles", "_group_battle_create"),
    ("POST", rf"{API}/social/group-battles/([\w-]+)/join", "_group_battle_join"),
    ("POST", rf"{API}/social/group-battles/([\w-]+)/leave", "_group_battle_leave"),
)
_COMPILED_ROUTES = tuple((method, re.compile(f"^{path}$"), name) for method, path, name in ROUTES)


class GameRequestHandler(BaseHTTPRequestHandler):
    database = None
    items_database = None
    chat_send_times = {}

    # ------------------------------------------------------------------ общие помощники

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 64 * 1024:
            raise ValueError("Слишком большой запрос")
        raw = self.rfile.read(length)
        body = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(body, dict):
            raise ValueError("Тело запроса должно быть объектом")
        return body

    def _token(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise ValueError("Требуется авторизация")
        return value[7:].strip()

    def _query(self):
        return parse_qs(urlparse(self.path).query)

    def _query_value(self, name, default=None):
        return self._query().get(name, [default])[0]

    def _user_id(self):
        return self.database.user_id_by_token(self._token())

    def _own_character(self, character_id):
        """Персонаж текущего игрока; чужой или несуществующий персонаж — ошибка."""
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(character_id))
        if character is None:
            raise ValueError("Персонаж не найден")
        return user_id, character

    @staticmethod
    def _location(value):
        location = str(value)
        if location not in CHAT_LOCATIONS:
            raise ValueError("Неизвестная локация")
        return location

    def _handle_error(self, error):
        status = 401 if "авторизац" in str(error) or "сессия" in str(error) else 400
        self._send(status, {"error": str(error)})

    def _handle_server_error(self, error):
        traceback.print_exc()
        self._send(500, {"error": "Внутренняя ошибка сервера"})

    def _dispatch(self, method):
        try:
            path = urlparse(self.path).path.rstrip("/")
            for route_method, pattern, name in _COMPILED_ROUTES:
                match = pattern.match(path)
                if route_method == method and match is not None:
                    body = {} if method == "GET" else self._body()
                    getattr(self, name)(body, *match.groups())
                    return
            self._send(404, {"error": "Маршрут не найден"})
        except KeyError as error:
            self._send(400, {"error": f"Не указано поле {error.args[0]}"})
        except (ValueError, json.JSONDecodeError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def log_message(self, format_string, *args):
        print(f"[kaloda] {self.address_string()} - {format_string % args}")

    # ------------------------------------------------------------------ служебное и аккаунты

    def _health(self, body):
        self._send(200, {"status": "ok"})

    def _info(self, body):
        self._user_id()
        self._send(200, {"game": "kaloda", "world_id": self.database.world_id})

    def _server_status(self, body):
        self._user_id()
        self._send(200, {
            "online_players": self.database.online_player_count(),
            "restart_notice": maintenance.public_notice(),
            "server_time": time.time(),
            "server_timezone": config.SERVER_TIMEZONE,
        })

    def _restart_notice(self, body):
        if not self.database.is_moderator(self._user_id()):
            raise ValueError("Недостаточно прав для управления сервером")
        if body.get("action") == "cancel":
            maintenance.cancel_restart()
            self._send(200, {"restart_notice": None})
            return
        minutes = int(body.get("minutes", 3))
        if not 1 <= minutes <= 30:
            raise ValueError("Время до перезапуска: от 1 до 30 минут")
        notice = maintenance.schedule_restart(delay_seconds=minutes * 60, message="Сервер получил обновление.")
        self._send(200, {"restart_notice": notice})

    def _register(self, body):
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        if not 3 <= len(username) <= 32 or not 6 <= len(password) <= 128:
            raise ValueError("Имя: 3-32 символа, пароль: 6-128 символов")
        self._send(201, {"user": self.database.register(username, password)})

    def _login(self, body):
        self._send(200, self.database.login(str(body.get("username", "")), str(body.get("password", ""))))

    def _disconnect(self, body):
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        character_id = body.get("character_id")
        character_id = int(character_id) if character_id is not None else None
        result = self.database.disconnect(token, character_id, body.get("character"))
        if character_id is not None and body.get("character") is not None:
            saved_character = self.database.get_character(user_id, character_id)
            if saved_character is not None:
                try:
                    social.cancel_public_duel_offer(character_id, "backyard")
                except ValueError:
                    pass
                # Вышедший игрок остаётся в локации афк-персонажем: его можно вызвать на бой
                social.mark_afk(token, user_id, self._presence_character(saved_character))
                self._announce_player_status(saved_character, "покинул сервер")
        self._send(200, result)

    # ------------------------------------------------------------------ персонажи

    @staticmethod
    def _validate_client_character_update(current, payload):
        """Клиент не может повышать то, чем ведает сервер: уровень, опыт, характеристики сверх очков, деньги."""
        if "level" in payload and int(payload["level"]) > int(current["level"]):
            raise ValueError("Уровень изменяется сервером")
        if "xp" in payload and int(payload["xp"]) > int(current["xp"]):
            raise ValueError("Опыт начисляется сервером")

        current_stats = current.get("stats", {})
        requested_stats = payload.get("stats", {})
        current_points = int(current.get("stat_points", 0))
        requested_points = int(payload.get("stat_points", current_points))
        if not isinstance(requested_stats, dict):
            requested_stats = {}
        # Повышать характеристики можно только за свободные очки: сумма статов + очков не растёт
        increase = sum(
            max(0, int(value) - int(current_stats.get(stat, 0)))
            for stat, value in requested_stats.items()
        )
        decrease = sum(
            max(0, int(current_stats.get(stat, 0)) - int(requested_stats[stat]))
            for stat in current_stats
            if stat in requested_stats
        )
        if increase + requested_points > current_points + decrease:
            raise ValueError("Характеристики изменяются сервером")
        for stat, value in requested_stats.items():
            if int(value) > int(current_stats.get(stat, 0)) and not stat_supports_met(requested_stats, stat):
                raise ValueError("Для повышения характеристики недостаточно очков связанных характеристик")
        for stat in current_stats:
            if stat not in requested_stats or int(requested_stats[stat]) >= int(current_stats[stat]):
                continue
            if any(
                dependent in requested_stats
                and not stat_supports_met(requested_stats, dependent)
                for dependent in STAT_DEPENDENTS.get(stat, ())
            ):
                raise ValueError("Нельзя снизить связанную характеристику ниже нужного порога")

        if int(payload.get("coins", 0)) > int(current.get("coins", 0)):
            raise ValueError("Валюта начисляется сервером")

    def _list_characters(self, body):
        self._send(200, {"characters": self.database.get_characters(self._user_id())})

    def _my_character(self, body):
        self._send(200, {"character": self.database.get_character(self._user_id())})

    def _get_character(self, body, character_id):
        _, character = self._own_character(character_id)
        self._send(200, {"character": character})

    def _create_character(self, body):
        user_id = self._user_id()
        name = str(body.get("name", "")).strip()
        profession_type = str(body.get("profession_type", "warrior")).strip().lower()
        self.database.validate_character_name(name)
        if profession_type not in PROFESSIONS:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(PROFESSIONS)}")
        character = self.database.create_character(user_id, name, profession_type)
        self.items_database.grant_base_equipment(character["id"])
        self._send(201, {"character": self.database.get_character(user_id, character["id"])})

    def _save_character(self, body, character_id):
        user_id = self._user_id()
        character_id = int(character_id)
        if "profession_type" in body and len(body) == 1:
            character = self.database.update_character_profession(user_id, character_id, body["profession_type"])
        else:
            current = self.database.get_character(user_id, character_id)
            if current is None:
                raise ValueError("Персонаж не найден")
            self._validate_client_character_update(current, body)
            character = self.database.save_character(user_id, character_id, body)
        self._send(200, {"character": character})

    def _delete_character(self, body, character_id):
        user_id = self._user_id()
        if "password" in body:
            self.database.delete_character_with_password(user_id, int(character_id), str(body["password"]))
        else:
            self.database.delete_character(user_id, int(character_id))
        self._send(200, {"deleted": True})

    def _choose_talent(self, body):
        user_id = self._user_id()
        character = self.database.choose_character_talent(
            user_id, int(body.get("character_id", 0)), body.get("level", 0), body.get("choice_id", ""),
        )
        self._send(200, {"character": character})

    def _card_collection(self, character):
        """Коллекция карт с описанием; при первом обращении выдаются стартовые карты класса."""
        character_id = character["id"]
        self.database.ensure_starter_cards(
            character_id, [card.key for card in class_cards_for_type(character.get("type"))],
        )
        cards_by_key = {card.key: card for card in load_cards()}
        collection = []
        for entry in self.database.get_card_collection(character_id):
            card = cards_by_key.get(entry["card_key"])
            if card is not None:
                collection.append({**entry, **card_to_dict(card)})
        return collection

    def _card_collection_route(self, body, character_id):
        _, character = self._own_character(character_id)
        self._send(200, {"collection": self._card_collection(character)})

    # ------------------------------------------------------------------ рюкзак, экипировка, предметы

    def _get_inventory(self, body, character_id):
        self._own_character(character_id)
        self._send(200, self.items_database.get_inventory_state(int(character_id)))

    def _get_equipment(self, body, character_id):
        self._own_character(character_id)
        self._send(200, {"equipment": self.items_database.get_equipment(int(character_id))})

    def _get_storage(self, body, character_id, storage_type):
        self._own_character(int(character_id))
        self._send(200, {"storage": self.items_database.get_storage(int(character_id), storage_type)})

    def _inventory_action(self, body, action):
        user_id, _ = self._own_character(body.get("character_id", 0))
        character_id = int(body["character_id"])
        response = {}
        items = self.items_database
        if action == "inventory/move":
            items.move_item(character_id, body["from_slot"], body["to_slot"])
        elif action == "inventory/use":
            response["character"] = items.use_item(user_id, character_id, body["slot_index"])
        elif action == "inventory/drop":
            items.drop_from_slot(character_id, body["slot_index"])
        elif action == "inventory/remove":
            quantity = int(body.get("quantity", 0))
            if quantity <= 0:
                raise ValueError("Некорректное количество предметов")
            if not items.remove_from_inventory(character_id, int(body["item_id"]), quantity):
                raise ValueError("В рюкзаке недостаточно предметов")
        elif action == "equipment/equip":
            items.equip_item(character_id, body["slot_index"], body.get("slot"))
        else:
            items.unequip_item(character_id, str(body["slot"]), body.get("target_slot"))
        response.update(items.get_inventory_state(character_id))
        self._send(200, response)

    def _catalog_items(self, body):
        self._user_id()
        raw_ids = self._query_value("ids", "")
        try:
            item_ids = [int(part) for part in raw_ids.split(",") if part.strip()]
        except ValueError:
            raise ValueError("Некорректные id предметов") from None
        self._send(200, {"items": self.items_database.get_catalog_items(item_ids)})

    def _item_catalog(self, body):
        self._user_id()
        self._send(200, {"items": self.items_database.list_catalog_items()})

    def _map_terrain(self, body):
        self._user_id()
        self._send(200, {"terrain": terrain_payload()})

    # ------------------------------------------------------------------ таверна и магазины

    def _drinks(self, body):
        self._user_id()
        self._send(200, {"drinks": self.database.get_drinks_list()})

    def _buy_drink(self, body):
        user_id = self._user_id()
        character = self.database.buy_drink(user_id, int(body.get("character_id", 0)), int(body.get("drink_id", 0)))
        self._send(200, {"character": character})

    def _supplies_shop(self, body):
        self._user_id()
        self._send(200, {"items": self.items_database.get_supplies_shop_catalog()})

    def _buy_supplies(self, body):
        user_id = self._user_id()
        self._send(200, self.items_database.buy_supplies_item(
            user_id, int(body.get("character_id", 0)), body.get("item_id", 0),
        ))

    def _card_shop(self, body):
        self._user_id()
        self._send(200, {"cards": self.items_database.get_card_shop_catalog()})

    def _buy_card(self, body):
        user_id = self._user_id()
        self._send(200, self.items_database.buy_card(
            user_id, int(body.get("character_id", 0)), str(body.get("card_key", "")),
        ))

    def _dungeon_card_shop(self, body):
        self._user_id()
        self._send(200, {"cards": self.items_database.get_dungeon_card_shop_catalog()})

    def _buy_dungeon_card(self, body):
        user_id = self._user_id()
        self._send(200, self.items_database.buy_dungeon_card(
            user_id, int(body.get("character_id", 0)), str(body.get("card_key", "")),
        ))

    def _dungeon_treasure(self, body):
        user_id = self._user_id()
        self._send(200, self.items_database.claim_dungeon_treasure(
            user_id, int(body.get("character_id", 0)), body.get("request_id"),
        ))

    # ------------------------------------------------------------------ колоды и награды

    def _get_decks(self, body, character_id):
        self._own_character(character_id)
        self._send(200, {"decks": self.items_database.get_decks(int(character_id))})

    def _create_deck(self, body):
        user_id, character = self._own_character(body.get("character_id", 0))
        name = str(body.get("name", "")).strip()
        if not 1 <= len(name) <= 32:
            raise ValueError("Название колоды: от 1 до 32 символов")
        cards = body.get("cards", {})
        if isinstance(cards, list):
            cards = dict(Counter(str(key) for key in cards))
        elif isinstance(cards, dict):
            normalized_cards = {}
            for key, quantity in cards.items():
                if isinstance(quantity, bool) or not isinstance(quantity, int):
                    raise ValueError("Количество карт должно быть целым числом")
                normalized_cards[str(key)] = quantity
            cards = normalized_cards
        else:
            raise ValueError("Некорректный состав колоды")
        owned_quantities = {
            entry["card_key"]: int(entry["quantity"]) for entry in self._card_collection(character)
        }
        error = deck_validation_error(cards, character.get("type"), owned_quantities)
        if error:
            raise ValueError(error)
        deck_id = self.items_database.create_deck(character["id"], name, cards)
        self._send(201, {"deck": self.items_database.get_deck(deck_id)})

    def _delete_deck(self, body, deck_id):
        _, character = self._own_character(body.get("character_id", 0))
        if not self.items_database.delete_deck(character["id"], int(deck_id)):
            raise ValueError("Колода не найдена")
        self._send(200, {"deleted": True})

    def _guild_quest_reward(self, body):
        user_id = self._user_id()
        character, reward_coins, already_claimed = self.database.claim_guild_quest_reward(
            user_id, int(body.get("character_id", 0)), body.get("quest_id"), body.get("request_id"),
        )
        self._send(200, {
            "character": character,
            "reward_coins": reward_coins,
            "already_claimed": already_claimed,
        })

    def _npc_kills(self, body):
        user_id = self._user_id()
        defeated_types = body.get("defeated_types", [])
        if not isinstance(defeated_types, list) or len(defeated_types) > 5:
            raise ValueError("Некорректный список побеждённых существ")
        self._send(200, self.database.report_npc_kill_xp(
            user_id, int(body.get("character_id", 0)), body.get("encounter_id", ""),
            defeated_types, body.get("request_id"),
        ))

    # ------------------------------------------------------------------ бои

    def _battle_result(self, body):
        user_id = self._user_id()
        self._send(200, self._apply_battle_result(user_id, int(body.get("character_id", 0)), body))

    def _apply_battle_result(self, user_id, character_id, body):
        character = self.database.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        outcome = str(body.get("outcome", ""))
        if outcome not in ("win", "draw", "loss"):
            raise ValueError("Некорректный исход боя")
        opponent_level = max(1, min(1000, int(body.get("opponent_level", character["level"]))))
        result = self.database.report_battle_result(
            user_id, character_id, outcome, opponent_level,
            int(body.get("hp", character["hp"])), int(body.get("mp", character["mp"])),
            body.get("battle_id"),
        )
        afk_result = self._apply_afk_defender_result(character_id, body)
        battle_archive_id = None
        replay = body.get("battle_record")
        if replay is not None:
            battle_archive_id = self.database.save_battle_archive(
                character_id, body.get("opponent_id"), outcome, replay,
            )
        return {**result, "afk_opponent": afk_result, "battle_archive_id": battle_archive_id}

    def _apply_afk_defender_result(self, attacker_id, body):
        """После боя с афк-игроком сохраняет его здоровье и ману; побеждённый возвращается к кристаллу с 1 HP."""
        opponent_id = body.get("opponent_id")
        if opponent_id is None or body.get("opponent_hp") is None or body.get("opponent_mp") is None:
            return None
        opponent_id = int(opponent_id)
        battle = self.database.get_active_battle(int(attacker_id), opponent_id)
        if (battle is None or not battle.get("opponent_afk")
                or battle.get("battle_data", {}).get("mode") != "afk_defense"):
            return None

        presence = social.get_character_presence(opponent_id)
        if presence is None or not presence.get("afk"):
            self.database.delete_active_battle(int(attacker_id), opponent_id)
            return None
        target = self.database.get_character_for_battle(opponent_id)
        if target is None:
            self.database.delete_active_battle(int(attacker_id), opponent_id)
            return None

        character = target["character"]
        hp = max(0, min(int(body["opponent_hp"]), character["max_hp"]))
        mp = max(0, min(int(body["opponent_mp"]), character["max_mp"]))
        defeated = hp <= 0
        checkpoint = {**character, "hp": hp, "mp": mp}
        if defeated:
            checkpoint.update({"hp": 1, "mp": 1, "zone": "world_map", "position_x": None, "position_y": None})
        saved = self.database.save_character(target["user_id"], opponent_id, checkpoint)
        social.update_afk_character(saved)
        self.database.delete_active_battle(int(attacker_id), opponent_id)
        return {"character_id": opponent_id, "hp": saved["hp"], "mp": saved["mp"], "defeated": defeated}

    def _battle_card_reward(self, body):
        user_id, character = self._own_character(body.get("character_id", 0))
        eligible_keys = body.get("card_keys", [])
        if not isinstance(eligible_keys, list) or len(eligible_keys) > 100:
            raise ValueError("Некорректный список карт боя")
        eligible_key_set = {str(key) for key in eligible_keys}
        eligible_cards = [
            card for card in load_cards()
            if card.key in eligible_key_set and card_allowed_for(card, character.get("type"))
        ]
        reward = choose_battle_reward(eligible_cards)
        if reward is None:
            self._send(200, {"reward": None})
            return
        collection_entry = self.database.add_card_to_collection(character["id"], reward.key)
        self._send(200, {"reward": {**collection_entry, **card_to_dict(reward)}})

    def _opponents(self, body):
        self._send(200, {"opponents": self.database.get_opponents(self._user_id())})

    def _save_opponent(self, body, opponent_id):
        user_id = self._user_id()
        self._send(200, {"opponent": self.database.update_bot(user_id, opponent_id, body)})

    # ------------------------------------------------------------------ присутствие и чат

    def _presence_character(self, character):
        """Профиль для присутствия: вместе с персонажем идёт активная колода, чтобы соперник-игрок играл ею."""
        active = self.items_database.get_active_deck(int(character["id"]))
        return {**character, "deck": active["cards"] if active else None}

    def _announce_player_status(self, character, status):
        self.database.add_chat_message(character["id"], "world", f"[ИГРОК] {character['name']} {status}")

    def _chat_actor(self, character_id):
        return self._own_character(character_id)

    def _check_chat_rate(self, character_id):
        now = time.time()
        timestamps = self.chat_send_times.setdefault(character_id, [])
        timestamps[:] = [stamp for stamp in timestamps if stamp > now - config.CHAT_RATE_LIMIT_WINDOW]
        if len(timestamps) >= config.CHAT_RATE_LIMIT_COUNT:
            raise ValueError("Слишком много сообщений. Подождите немного")
        timestamps.append(now)

    def _presence(self, body):
        token = self._token()
        user_id, character = self._own_character(int(body["character_id"]))
        location = self._location(body.get("location", "world_map"))
        if social.update_presence(token, user_id, self._presence_character(character), location):
            self._announce_player_status(character, "присоединился к игре")
        self._send(200, {"ok": True})

    def _occupants(self, body):
        user_id = self._user_id()
        location = self._location(self._query_value("location", "world_map"))
        self._send(200, {"occupants": social.occupants(user_id, location)})

    def _chat_history(self, body):
        character_id = int(self._query_value("character_id", 0))
        self._chat_actor(character_id)
        self._send(200, {
            "messages": self.database.get_chat_history(
                character_id,
                self._location(self._query_value("location", "world_map")),
                self._query_value("before_id"),
                self._query_value("limit", 50),
            )
        })

    def _chat_unread(self, body):
        character_id = int(self._query_value("character_id", 0))
        self._chat_actor(character_id)
        location = self._location(self._query_value("location", "world_map"))
        self._send(200, {"unread": self.database.chat_unread_count(character_id, location)})

    def _chat_message(self, body):
        _, character = self._chat_actor(int(body.get("character_id", 0)))
        text = str(body.get("text", "")).strip()
        if not 1 <= len(text) <= config.CHAT_MAX_LENGTH:
            raise ValueError(f"Сообщение должно содержать от 1 до {config.CHAT_MAX_LENGTH} символов")
        location = str(body.get("location", "world_map"))
        if location == "world":
            raise ValueError("В мировой канал может писать только сервер")
        location = self._location(location)
        self._check_chat_rate(character["id"])
        if self.database.is_muted(character["id"], location):
            raise ValueError("Вы временно не можете отправлять сообщения")
        message = self.database.add_chat_message(character["id"], location, text, body.get("recipient_id"))
        self._send(201, {"message": message})

    def _chat_read(self, body):
        character_id = int(body.get("character_id", 0))
        self._chat_actor(character_id)
        self.database.mark_chat_read(
            character_id, self._location(body.get("location", "world_map")), body.get("message_id", 0),
        )
        self._send(200, {"ok": True})

    def _chat_report(self, body):
        character_id = int(body.get("character_id", 0))
        self._chat_actor(character_id)
        reason = str(body.get("reason", "")).strip()
        if not 1 <= len(reason) <= 200:
            raise ValueError("Некорректная причина жалобы")
        self.database.report_chat_message(body.get("message_id"), character_id, reason)
        self._send(201, {"ok": True})

    def _chat_delete(self, body):
        self.database.delete_chat_message(body.get("message_id"), self._user_id())
        self._send(200, {"ok": True})

    def _chat_mute(self, body):
        self.database.mute_character(
            body.get("character_id"), body.get("muted_character_id"), self._user_id(), body.get("seconds", 600),
        )
        self._send(200, {"ok": True})

    # ------------------------------------------------------------------ игроки рядом и заявки на бой

    def _social_snapshot(self, body):
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        location = self._location(self._query_value("location", "world_map"))
        character_id = int(self._query_value("character_id", 0))
        _, character = self._chat_actor(character_id)
        position_x = self._query_value("position_x")
        position_y = self._query_value("position_y")
        if location == "world_map" and position_x is not None and position_y is not None:
            try:
                position_x, position_y = float(position_x), float(position_y)
            except (TypeError, ValueError):
                raise ValueError("Некорректная позиция персонажа") from None
            direction = self._query_value("position_direction", "s")
            character = {
                **character,
                "position_x": position_x,
                "position_y": position_y,
                "position_direction": direction if direction in DIRECTIONS else "s",
            }
        if social.update_presence(token, user_id, self._presence_character(character), location):
            self._announce_player_status(character, "присоединился к игре")
        offers = social.offers_for(character_id)
        if location == "backyard":
            offers += social.public_offers(location, character_id)
        self._send(200, {
            "occupants": social.occupants(user_id, location),
            "messages": self.database.get_chat_history(character_id, location),
            "offers": offers,
            "my_application": social.own_public_offer(character_id, location),
            "group_offers": social.group_battle_offers() if location == "backyard" else [],
        })

    def _social_offers(self, body):
        user_id = self._user_id()
        character = self.database.get_character(user_id)
        location = self._location(self._query_value("location", "world_map"))
        offers = social.offers_for(character["id"])
        if location == "backyard":
            offers += social.public_offers(location, character["id"])
        self._send(200, {
            "offers": offers,
            "my_application": social.own_public_offer(character["id"], location),
        })

    def _duel_offer(self, body):
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        character = self.database.get_character(user_id, int(body["character_id"]))
        target_id = body.get("target_id")
        location = body.get("location", "backyard")
        if character is None or not target_id or location != "backyard":
            raise ValueError("Предложение поединка недоступно")
        if social.pending_public_offer(character["id"], location) is not None:
            raise ValueError("Пока активна ваша заявка, вы не можете бросать вызов")
        target = next(
            (item for item in social.occupants(user_id, location) if str(item["character_id"]) == str(target_id)),
            None,
        )
        if target is None:
            raise ValueError("Персонаж не найден в локации")
        if target.get("type", "warrior") != character.get("type", "warrior"):
            raise ValueError("Нельзя вызвать персонажа другого класса")
        if character["hp"] < character["max_hp"]:
            raise ValueError("Нельзя вступить в бой: здоровье должно быть полностью восстановлено")
        if target.get("hp", target.get("max_hp")) < target.get("max_hp", 0):
            raise ValueError("Нельзя вступить в бой: здоровье соперника должно быть полностью восстановлено")
        challenger = {"character_id": character["id"], "name": character["name"]}
        if target.get("kind") == "bot":
            error = social.backyard_duel_error(character, target)
            if error:
                raise ValueError(error)
            offer = social.add_duel_offer(challenger, target_id, location)
            offer["status"] = "accepted"
            offer["accepted_by"] = target["character_id"]
            self._send(201, {"accepted": True, "offer": offer})
            return
        if target.get("afk"):
            target_id = int(target["character_id"])
            if (self.database.get_active_battle(character["id"], target_id)
                    or self.database.get_active_battle(target_id, character["id"])):
                raise ValueError("Один из персонажей уже участвует в бою")
            offer = social.add_duel_offer(challenger, target_id, location)
            offer["status"] = "accepted"
            offer["accepted_by"] = target_id
            self.database.save_active_battle(
                character["id"], target_id, {"mode": "afk_defense", "location": location},
            )
            self.database.mark_opponent_afk(character["id"], target_id, True)
            self._send(201, {"accepted": True, "offer": offer})
            return
        offer = social.add_duel_offer(challenger, target_id, location)
        self._send(201, {"accepted": False, "offer": offer})

    def _duel_offer_respond(self, body):
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(body["character_id"]))
        if character is None:
            raise ValueError("Персонаж не найден")
        accepted = bool(body.get("accepted"))
        if accepted and character["hp"] < character["max_hp"]:
            raise ValueError("Нельзя вступить в бой: здоровье должно быть полностью восстановлено")
        if accepted and social.has_active_application(character["id"]):
            raise ValueError("Сначала отмените свою заявку, чтобы вступить в бой")
        offer = next((item for item in social.DUEL_OFFERS if item["id"] == body["offer_id"]), None)
        afk_defender_id = None
        if offer is not None and str(offer["sender_id"]).lstrip("-").isdigit():
            sender_id = int(offer["sender_id"])
            sender = self.database.get_character_for_battle(sender_id)
            sender_character = sender["character"] if sender is not None else None
            if sender_character is not None and sender_character.get("type", "warrior") != character.get("type", "warrior"):
                raise ValueError("Нельзя принять вызов персонажа другого класса")
            sender_presence = social.get_character_presence(sender_id)
            if accepted and offer.get("target_id") is None and sender_presence and sender_presence.get("afk"):
                if sender_character is None:
                    raise ValueError("Персонаж уже недоступен")
                if sender_character["hp"] < sender_character["max_hp"]:
                    raise ValueError("Нельзя вступить в бой: здоровье соперника должно быть полностью восстановлено")
                if (self.database.get_active_battle(character["id"], sender_id)
                        or self.database.get_active_battle(sender_id, character["id"])):
                    raise ValueError("Этот персонаж уже участвует в бою")
                afk_defender_id = sender_id
        offer = social.respond_duel_offer(character["id"], body["offer_id"], accepted)
        if afk_defender_id is not None:
            self.database.save_active_battle(
                character["id"], afk_defender_id, {"mode": "afk_defense", "location": "backyard"},
            )
            self.database.mark_opponent_afk(character["id"], afk_defender_id, True)
        self._send(200, {"offer": offer})

    def _duel_application(self, body):
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(body["character_id"]))
        if character is None or body.get("location") != "backyard":
            raise ValueError("Заявка недоступна")
        if character["hp"] < character["max_hp"]:
            raise ValueError("Нельзя подать заявку: здоровье должно быть полностью восстановлено")
        if social.has_active_application(character["id"]):
            raise ValueError("Нельзя одновременно участвовать в нескольких заявках")
        offer = social.add_public_duel_offer(
            {"character_id": character["id"], "name": character["name"]},
            "backyard",
            max(120, min(int(body.get("ttl", 120)), 1800)),
        )
        self._send(201, {"application": offer})

    def _duel_application_cancel(self, body):
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(body["character_id"]))
        if character is None or body.get("location") != "backyard":
            raise ValueError("Отмена заявки недоступна")
        self._send(200, {"application": social.cancel_public_duel_offer(character["id"], "backyard")})

    def _group_battles(self, body):
        self._user_id()
        self._send(200, {"offers": social.group_battle_offers()})

    def _group_battle_character(self, body, message):
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(body["character_id"]))
        if character is None or body.get("location") != "backyard":
            raise ValueError(message)
        if character["hp"] < character["max_hp"]:
            raise ValueError("Для группового боя здоровье должно быть полностью восстановлено")
        if social.has_active_application(character["id"]):
            raise ValueError("Нельзя одновременно участвовать в нескольких заявках")
        return character

    def _group_battle_create(self, body):
        character = self._group_battle_character(body, "Заявка группового боя недоступна")
        ttl = max(120, min(int(body.get("ttl", 120)), 1800))
        max_participants = int(body.get("max_participants", 10))
        if max_participants not in (6, 8, 10):
            raise ValueError("Размер команды может быть только 6, 8 или 10")
        self._send(201, {"offer": social.create_group_battle_offer(character, ttl, max_participants)})

    def _group_battle_join(self, body, offer_id):
        character = self._group_battle_character(body, "Присоединение к групповому бою недоступно")
        self._send(200, {"offer": social.join_group_battle_offer(offer_id, character)})

    def _group_battle_leave(self, body, offer_id):
        user_id = self._user_id()
        character = self.database.get_character(user_id, int(body["character_id"]))
        if character is None:
            raise ValueError("Персонаж не найден")
        self._send(200, {"offer": social.leave_group_battle_offer(offer_id, character["id"])})


class GameHTTPServer(ThreadingHTTPServer):
    # В Windows SO_REUSEADDR позволяет второму серверу молча занять тот же порт
    allow_reuse_address = os.name != "nt"


def bind_database(database, items_database=None):
    """Подключает обработчик к базе и возвращает прежнюю пару (для тестов, которые подменяют базу)."""
    previous = (GameRequestHandler.database, GameRequestHandler.items_database)
    # Ограничение частоты привязано к персонажам конкретной базы и с её заменой начинается заново
    GameRequestHandler.chat_send_times.clear()
    if database is None:
        GameRequestHandler.database = GameRequestHandler.items_database = None
    else:
        GameRequestHandler.database = database
        GameRequestHandler.items_database = items_database or ItemsDatabase(database)
    return previous


def run():
    database = Database()
    bind_database(database)
    server = GameHTTPServer((config.HOST, config.PORT), GameRequestHandler)
    stop_event = threading.Event()
    restart_requested = threading.Event()
    threads = [
        threading.Thread(target=_run_bot_battles, args=(stop_event,), name="bot-battle-scheduler", daemon=True),
        threading.Thread(
            target=_run_scheduled_restart, args=(server, stop_event, restart_requested),
            name="scheduled-server-restart", daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    # Лобби предлагает мир, только пока у него есть адрес сервера
    database.set_server_url(config.PUBLIC_URL)
    print(f"Kaloda server (мир {database.world_id}): http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKaloda server stopped")
    finally:
        database.set_server_url(None)
        stop_event.set()
        for thread in threads:
            thread.join(timeout=2)
        server.server_close()
    if restart_requested.is_set():
        raise SystemExit(1)


def _run_bot_battles(stop_event):
    while not stop_event.is_set():
        try:
            bots.run_bot_battle_tick()
        except Exception:
            traceback.print_exc()
        if stop_event.wait(1):
            break


def _run_scheduled_restart(server, stop_event, restart_requested):
    while not stop_event.wait(0.5):
        if maintenance.restart_due():
            restart_requested.set()
            server.shutdown()
            return


if __name__ == "__main__":
    run()
