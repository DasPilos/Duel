import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import time

from server import config
from server.database import Database
from server.items_database import ItemsDatabase
from server.forge import Forge
from server import maintenance, social
from server.world import run_bot_battle_tick
from core.production_buildings import BUILDINGS
from server.production_buildings import ProductionBuildings
from server.world_map import terrain_payload
from server.structures import city_structures
from server.world_roads import roads_payload
from core.currency import Currency
from combat.anticheat import score_match
from combat.fighter import Fighter
from combat.progression import apply_xp, battle_currency_reward, battle_xp
from combat.card_database import (
    card_allowed_for,
    card_to_dict,
    cards_for_type,
    choose_battle_reward,
    deck_validation_error,
    load_cards,
)


class GameRequestHandler(BaseHTTPRequestHandler):
    CHAT_LOCATIONS = ("tavern", "backyard", "city", "world_map", "character_room")
    database = Database()
    items_database = ItemsDatabase(database)
    chat_send_times = {}
    battle_result_times = {}
    # Результат боя шлёт клиент: не чаще одного боя за это время
    BATTLE_RESULT_MIN_INTERVAL = 20

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_client_download(self):
        package_path = Path(__file__).resolve().parent.parent / "client_package.zip"
        if not package_path.is_file():
            self._send(404, {"error": "Архив клиента не найден"})
            return
        data = package_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", 'attachment; filename="client_package.zip"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 64 * 1024:
            raise ValueError("Слишком большой запрос")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _token(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise ValueError("Требуется авторизация")
        return value[7:].strip()

    def _handle_error(self, error):
        status = 401 if "авторизац" in str(error) or "сессия" in str(error) else 400
        self._send(status, {"error": str(error)})

    def _handle_server_error(self, error):
        traceback.print_exc()
        self._send(500, {"error": "Внутренняя ошибка сервера"})

    def _query(self):
        return parse_qs(urlparse(self.path).query)

    def _chat_actor(self, token, character_id):
        user_id = self.database.user_id_by_token(token)
        character = self.database.get_character(user_id, int(character_id))
        if character is None:
            raise ValueError("Персонаж не найден")
        return user_id, character

    def _announce_player_status(self, character, status):
        text = f"[ИГРОК] {character['name']} {status}"
        for location in self.CHAT_LOCATIONS:
            self.database.add_chat_message(character["id"], location, text)

    @staticmethod
    def _validate_client_character_update(current, payload):
        """Reject client attempts to increase server-owned progression fields."""
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

        current_currency = Currency.from_dict(current)
        requested_currency = Currency.from_dict(payload)
        if requested_currency.total_copper() > current_currency.total_copper():
            raise ValueError("Валюта начисляется сервером")

    def _apply_battle_result(self, user_id, character_id, body):
        character = self.database.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        outcome = str(body.get("outcome", ""))
        if outcome not in ("win", "draw", "loss"):
            raise ValueError("Некорректный исход боя")
        now = time.time()
        last = self.battle_result_times.get(character_id, 0)
        if now - last < self.BATTLE_RESULT_MIN_INTERVAL:
            raise ValueError("Результат боя уже засчитан")
        self.battle_result_times[character_id] = now
        opponent_level = max(1, min(1000, int(body.get("opponent_level", character["level"]))))

        fighter = Fighter(character["name"], character["level"], profession_type=character.get("type", "warrior"))
        fighter.stats = dict(character["stats"])
        fighter.stat_points = character["stat_points"]
        fighter.xp = character["xp"]
        fighter.recalculate_parameters()
        fighter.hp = max(0, min(int(body.get("hp", character["hp"])), fighter.max_hp))
        xp = battle_xp(character["level"], opponent_level, outcome)
        apply_xp(fighter, xp, restore_hp=False)

        copper, silver = battle_currency_reward(character["level"]) if outcome == "win" else (0, 0)
        currency = Currency.from_dict(character)
        currency.add(copper, silver, 0)
        saved = self.database.save_character(user_id, character_id, {
            **character,
            **currency.to_dict(),
            "level": fighter.level,
            "xp": fighter.xp,
            "stats": fighter.stats,
            "stat_points": fighter.stat_points,
            "hp": fighter.hp,
            "mp": max(0, min(int(body.get("mp", character["mp"])), character["max_mp"])),
        })
        afk_result = self._apply_afk_defender_result(character_id, body)
        return {
            "character": saved,
            "xp": xp,
            "currency": {"copper": copper, "silver": silver, "gold": 0},
            "afk_opponent": afk_result,
        }

    def _apply_afk_defender_result(self, attacker_id, body):
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
            checkpoint.update({
                "hp": 1,
                "mp": 1,
                "zone": "city",
                "position_x": 50 * 32 + 16,
                "position_y": 53 * 32 + 16,
                "position_direction": "n",
            })
        saved = self.database.save_character(target["user_id"], opponent_id, checkpoint)
        social.update_afk_character(saved)
        self.database.delete_active_battle(int(attacker_id), opponent_id)
        return {"character_id": opponent_id, "hp": saved["hp"], "mp": saved["mp"], "defeated": defeated}

    def _card_collection(self, character):
        character_id = character["id"]
        self.database.ensure_starter_cards(
            character_id,
            [card.key for card in cards_for_type(character.get("type"))],
        )
        cards_by_key = {card.key: card for card in load_cards()}
        collection = []
        for entry in self.database.get_card_collection(character_id):
            card = cards_by_key.get(entry["card_key"])
            if card is not None:
                collection.append({**entry, **card_to_dict(card)})
        return collection

    def _check_chat_rate(self, character_id):
        now = time.time()
        timestamps = self.chat_send_times.setdefault(character_id, [])
        timestamps[:] = [stamp for stamp in timestamps if stamp > now - config.CHAT_RATE_LIMIT_WINDOW]
        if len(timestamps) >= config.CHAT_RATE_LIMIT_COUNT:
            raise ValueError("Слишком много сообщений. Подождите немного")
        timestamps.append(now)

    def _handle_social_occupants(self):
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        location = self._query().get("location", ["tavern"])[0]
        self._send(200, {"occupants": social.occupants(user_id, location)})

    def _handle_chat_history(self, *, default_to_first_character=False):
        query = self._query()
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        default_character_id = self.database.get_character(user_id)["id"] if default_to_first_character else 0
        character_id = int(query.get("character_id", [default_character_id])[0])
        self._chat_actor(token, character_id)
        self._send(200, {
            "messages": self.database.get_chat_history(
                character_id,
                query.get("location", ["tavern"])[0],
                query.get("before_id", [None])[0],
                query.get("limit", [50])[0],
            )
        })

    def _handle_chat_unread(self):
        query = self._query()
        token = self._token()
        character_id = int(query.get("character_id", [0])[0])
        self._chat_actor(token, character_id)
        location = query.get("location", ["tavern"])[0]
        self._send(200, {"unread": self.database.chat_unread_count(character_id, location)})

    def _handle_social_snapshot(self):
        query = self._query()
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        location = query.get("location", ["tavern"])[0]
        character_id = int(query.get("character_id", [0])[0])
        _, character = self._chat_actor(token, character_id)
        if social.update_presence(token, user_id, character, location):
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

    def _handle_server_status(self):
        self.database.user_id_by_token(self._token())
        self._send(200, {
            "online_players": self.database.online_player_count(),
            "restart_notice": maintenance.public_notice(),
        })

    def _handle_social_offers(self):
        token = self._token()
        user_id = self.database.user_id_by_token(token)
        character = self.database.get_character(user_id)
        location = self._query().get("location", ["tavern"])[0]
        offers = social.offers_for(character["id"])
        if location == "backyard":
            offers += social.public_offers(location, character["id"])
        self._send(200, {
            "offers": offers,
            "my_application": social.own_public_offer(character["id"], location),
        })

    def _handle_chat_message(self, body, *, validation_error, prevent_self_message=False):
        token = self._token()
        character_id = int(body.get("character_id", 0))
        _, character = self._chat_actor(token, character_id)
        text = str(body.get("text", "")).strip()
        if not 1 <= len(text) <= config.CHAT_MAX_LENGTH:
            raise ValueError(validation_error)
        self._check_chat_rate(character["id"])
        location = str(body.get("location", "tavern"))
        if self.database.is_muted(character["id"], location):
            raise ValueError("Вы временно не можете отправлять сообщения")
        recipient_id = body.get("recipient_id")
        if prevent_self_message and recipient_id is not None and str(recipient_id) == str(character["id"]):
            raise ValueError("Нельзя отправить сообщение самому себе")
        message = self.database.add_chat_message(character["id"], location, text, recipient_id)
        self._send(201, {"message": message})

    def do_GET(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            if path == "/health":
                self._send(200, {"status": "ok"})
                return
            if path == "/api/server/status":
                self._handle_server_status()
                return
            if path == "/download/client":
                self._send_client_download()
                return
            if path == "/api/characters/me":
                user_id = self.database.user_id_by_token(self._token())
                character = self.database.get_character(user_id)
                self._send(200, {"character": character})
                return
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, {"characters": self.database.get_characters(user_id)})
                return
            if path == "/api/map/terrain":
                self.database.user_id_by_token(self._token())
                self._send(200, {"terrain": terrain_payload()})
                return
            if path == "/api/city/structures":
                self.database.user_id_by_token(self._token())
                self._send(200, {"city": city_structures()})
                return
            if path.startswith("/api/buildings/player-work/"):
                parts = path.split("/")
                if len(parts) != 5:
                    raise ValueError("Некорректный путь производственной работы")
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[4])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                work = ProductionBuildings(self.database).active_player_work(character_id)
                self._send(200, {"work": work})
                return
            if path.startswith("/api/forge/"):
                parts = path.split("/")
                if len(parts) != 4 or parts[3] == "orders":
                    raise ValueError("Некорректный путь кузницы")
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[3])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                forge = Forge(self.database, self.items_database)
                self._send(200, forge.get_state(character_id))
                return
            if path.startswith("/api/buildings/"):
                parts = path.split("/")
                if len(parts) != 5 or parts[3] not in BUILDINGS:
                    self._send(404, {"error": "Здание не найдено"})
                    return
                building, character_id = parts[3], int(parts[4])
                user_id = self.database.user_id_by_token(self._token())
                if self.database.get_character(user_id, character_id) is None:
                    self._send(404, {"error": "Персонаж не найден"})
                else:
                    state = ProductionBuildings(self.database).get_state(character_id, building)
                    self._send(200, {"building": state})
                return
            if path == "/api/opponents":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, {"opponents": self.database.get_opponents(user_id)})
                return
            if path == "/api/social/occupants":
                self._handle_social_occupants()
                return
            if path == "/api/social/messages":
                self._handle_chat_history(default_to_first_character=True)
                return
            if path == "/api/chat/history":
                self._handle_chat_history()
                return
            if path == "/api/chat/unread":
                self._handle_chat_unread()
                return
            if path == "/api/social/snapshot":
                self._handle_social_snapshot()
                return
            if path == "/api/social/offers":
                self._handle_social_offers()
                return
            if path == "/api/social/group-battles":
                self._token()
                self._send(200, {"offers": social.group_battle_offers()})
                return
            if path.startswith("/api/social/group-battles/"):
                self._token()
                offer_id = path.rsplit("/", 1)[1]
                offer = social.group_battle_offer(offer_id)
                if offer is None:
                    self._send(404, {"error": "Заявка группового боя не найдена"})
                else:
                    self._send(200, {"offer": offer})
                return
            if path.startswith("/api/characters/"):
                character_id = int(path.rsplit("/", 1)[1])
                user_id = self.database.user_id_by_token(self._token())
                character = self.database.get_character(user_id, character_id)
                if character is None:
                    self._send(404, {"error": "Персонаж не найден"})
                else:
                    self._send(200, {"character": character})
                return
            
            if path == "/api/drinks":
                self._token()
                drinks = self.database.get_drinks_list()
                self._send(200, {"drinks": drinks})
                return
            
            # ============= GET API ИНВЕНТАРЯ =============
            if path.startswith("/api/inventory/"):
               character_id = int(path.rsplit("/", 1)[1])
               user_id = self.database.user_id_by_token(self._token())
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   self._send(404, {"error": "Персонаж не найден"})
               else:
                   self._send(200, self.items_database.get_inventory_state(character_id))
               return
            
            if path.startswith("/api/equipment/"):
               character_id = int(path.rsplit("/", 1)[1])
               user_id = self.database.user_id_by_token(self._token())
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   self._send(404, {"error": "Персонаж не найден"})
               else:
                   equipment = self.items_database.get_equipment(character_id)
                   self._send(200, {"equipment": equipment})
               return
            
            if path.startswith("/api/storage/"):
               parts = path.split("/")
               character_id = int(parts[-2])
               storage_type = str(parts[-1])
               user_id = self.database.user_id_by_token(self._token())
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   self._send(404, {"error": "Персонаж не найден"})
               else:
                   storage = self.items_database.get_storage(character_id, storage_type)
                   self._send(200, {"storage": storage})
               return
            
            if path.startswith("/api/decks/"):
               character_id = int(path.rsplit("/", 1)[1])
               user_id = self.database.user_id_by_token(self._token())
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   self._send(404, {"error": "Персонаж не найден"})
               else:
                   decks = self.items_database.get_decks(character_id)
                   self._send(200, {"decks": decks})
               return

            if path.startswith("/api/card-collection/"):
               character_id = int(path.rsplit("/", 1)[1])
               user_id = self.database.user_id_by_token(self._token())
               character = self.database.get_character(user_id, character_id)
               if character is None:
                  self._send(404, {"error": "Персонаж не найден"})
               else:
                  self._send(200, {"collection": self._card_collection(character)})
               return
            
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def do_POST(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            body = self._body()
            if path == "/api/register":
                username = str(body.get("username", "")).strip()
                password = str(body.get("password", ""))
                if not 3 <= len(username) <= 32 or not 6 <= len(password) <= 128:
                    raise ValueError("Имя: 3-32 символа, пароль: 6-128 символов")
                self._send(201, {"user": self.database.register(username, password)})
                return
            if path == "/api/server/restart-notice":
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав для управления сервером")
                if body.get("action") == "cancel":
                    maintenance.cancel_restart()
                    self._send(200, {"restart_notice": None})
                    return
                minutes = int(body.get("minutes", 3))
                if not 1 <= minutes <= 30:
                    raise ValueError("Время до перезапуска: от 1 до 30 минут")
                notice = maintenance.schedule_restart(
                    delay_seconds=minutes * 60,
                    message="Сервер получил обновление.",
                )
                self._send(200, {"restart_notice": notice})
                return
            if path == "/api/login":
                self._send(200, self.database.login(str(body.get("username", "")), str(body.get("password", ""))))
                return
            if path == "/api/decks":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(body.get("character_id", 0))
                character = self.database.get_character(user_id, character_id)
                if character is None:
                    raise ValueError("Персонаж не найден")
                name = str(body.get("name", "")).strip()
                if not 1 <= len(name) <= 32:
                    raise ValueError("Название колоды: от 1 до 32 символов")
                cards = body.get("cards", {})
                if isinstance(cards, list):
                    if len(cards) != len(set(map(str, cards))):
                        raise ValueError("Карты в колоде не должны повторяться")
                    cards = {str(key): 1 for key in cards}
                if not isinstance(cards, dict):
                    raise ValueError("Некорректный состав колоды")
                cards = {str(key): 1 for key in cards}
                owned_keys = {entry["card_key"] for entry in self._card_collection(character)}
                error = deck_validation_error(list(cards), character.get("type"), owned_keys)
                if error:
                    raise ValueError(error)
                deck_id = self.items_database.create_deck(character_id, name, cards)
                self._send(201, {"deck": self.items_database.get_deck(deck_id)})
                return
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                name = str(body.get("name", "")).strip()
                profession_type = str(body.get("profession_type", "warrior")).strip().lower()
                self.database.validate_character_name(name)
                valid_professions = ["warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"]
                if profession_type not in valid_professions:
                    raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")
                character = self.database.create_character(user_id, name, profession_type)
                self.items_database.grant_base_equipment(character["id"])
                self._send(201, {"character": character})
                return
            if path.startswith("/api/forge/"):
                parts = path.split("/")
                if not ((len(parts) == 5 and parts[4] == "orders")
                        or (len(parts) == 7 and parts[4] == "orders" and parts[6] == "collect")):
                    raise ValueError("Некорректный путь кузницы")
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[3])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                forge = Forge(self.database, self.items_database)
                if len(parts) == 5:
                    order_id = forge.create_order(character_id, body.get("item_id"))
                    self._send(201, {"order_id": order_id, **forge.get_state(character_id)})
                    return
                forge.collect_order(character_id, int(parts[5]))
                self._send(200, forge.get_state(character_id))
                return
            if path.startswith("/api/buildings/"):
                parts = path.split("/")
                if len(parts) < 6 or parts[3] not in BUILDINGS:
                    raise ValueError("Некорректный путь здания")
                building, character_id = parts[3], int(parts[4])
                user_id = self.database.user_id_by_token(self._token())
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                buildings = ProductionBuildings(self.database)
                action = "/".join(parts[5:])
                if action == "workers/hire":
                    state = buildings.hire_worker(character_id, building, body.get("slot_index"), body.get("worker_id"))
                elif action == "workers/fire":
                    state = buildings.fire_worker(character_id, building, body.get("slot_index"))
                elif action == "workers/player/toggle":
                    state = buildings.toggle_player_worker(character_id, building, body.get("slot_index"))
                elif action == "player-harvest/claim":
                    state = buildings.claim_player_harvest(
                        character_id, building, body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "storage/deposit":
                    state = buildings.deposit_to_storage(
                        character_id, building, body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "upgrade/deposit":
                    state = buildings.deposit_material(character_id, building, body.get("item_id", 0), body.get("quantity", 0))
                elif action == "upgrade/start":
                    state = buildings.start_upgrade(character_id, building)
                elif action == "stall-upgrade/contribute" and building == "stable":
                    state = buildings.contribute_stall_upgrade(
                        character_id, body.get("upgrade_id"), body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "stall-upgrade/purchase" and building == "stable":
                    state = buildings.purchase_stall_upgrade(character_id, body.get("upgrade_id"))
                elif action == "cart/contribute" and building == "stable":
                    state = buildings.contribute_cart(
                        character_id, body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "cart/purchase" and building == "stable":
                    state = buildings.purchase_cart(character_id, body.get("grade", 1))
                elif action == "horse/purchase" and building == "stable":
                    state = buildings.purchase_horse(character_id, body.get("slot_index"))
                else:
                    raise ValueError("Неизвестное действие здания")
                self._send(200, {"building": state})
                return
            if path.startswith("/api/characters/") and path.endswith("/delete"):
                character_id = int(path.rsplit("/", 2)[1])
                user_id = self.database.user_id_by_token(self._token())
                
                # If password is provided, verify it before deletion
                if "password" in body:
                    password = str(body.get("password", ""))
                    self.database.delete_character_with_password(user_id, character_id, password)
                else:
                    self.database.delete_character(user_id, character_id)
                
                self._send(200, {"deleted": True})
                return
            if path == "/api/sessions/disconnect":
                token = self._token()
                character_id = body.get("character_id")
                user_id = self.database.user_id_by_token(token)
                character_id = int(character_id) if character_id is not None else None
                result = self.database.disconnect(token, character_id, body.get("character"))
                if character_id is not None and body.get("character") is not None:
                    saved_character = self.database.get_character(user_id, character_id)
                    if saved_character is not None:
                        try:
                            social.cancel_public_duel_offer(character_id, "backyard")
                        except ValueError:
                            pass
                        social.mark_afk(token, user_id, saved_character)
                        self._announce_player_status(saved_character, "покинул сервер")
                self._send(200, result)
                return
            if path == "/api/social/presence":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None:
                    raise ValueError("Персонаж не найден")
                if social.update_presence(token, user_id, character, str(body.get("location", "tavern"))):
                    self._announce_player_status(character, "присоединился к игре")
                self._send(200, {"ok": True})
                return
            if path == "/api/social/messages":
                self._handle_chat_message(
                    body,
                    validation_error="Некорректное сообщение",
                    prevent_self_message=True,
                )
                return
            if path == "/api/chat/messages":
                self._handle_chat_message(
                    body,
                    validation_error="Сообщение должно содержать от 1 до 300 символов",
                )
                return
            if path == "/api/chat/read":
                token = self._token()
                character_id = int(body.get("character_id", 0))
                self._chat_actor(token, character_id)
                self.database.mark_chat_read(character_id, str(body.get("location", "tavern")), body.get("message_id", 0))
                self._send(200, {"ok": True})
                return
            if path == "/api/chat/report":
                token = self._token()
                character_id = int(body.get("character_id", 0))
                self._chat_actor(token, character_id)
                reason = str(body.get("reason", "")).strip()
                if not 1 <= len(reason) <= 200:
                    raise ValueError("Некорректная причина жалобы")
                self.database.report_chat_message(body.get("message_id"), character_id, reason)
                self._send(201, {"ok": True})
                return
            if path == "/api/chat/delete":
                token = self._token()
                moderator_id = self.database.user_id_by_token(token)
                self.database.delete_chat_message(body.get("message_id"), moderator_id)
                self._send(200, {"ok": True})
                return
            if path == "/api/chat/mute":
                token = self._token()
                moderator_id = self.database.user_id_by_token(token)
                self.database.mute_character(
                    body.get("character_id"),
                    body.get("muted_character_id"),
                    moderator_id,
                    body.get("seconds", 600),
                )
                self._send(200, {"ok": True})
                return
            if path == "/api/matches/audit":
                self._token()
                audit = dict(body)
                audit.pop("xp", None)
                audit.pop("xp_awarded_a", None)
                audit.pop("xp_awarded_b", None)
                audit.update(score_match(
                    pair_matches_24h=int(audit.get("pair_matches_24h", 0)),
                    pair_wins_24h=int(audit.get("pair_wins_24h", 0)),
                    turns=int(audit.get("turns", 0)),
                    median_turns=int(audit.get("median_turns", 0)),
                    surrender=bool(audit.get("surrender", False)),
                    afk_turns=int(audit.get("afk_turns", 0)),
                    level_difference=int(audit.get("level_b", 1)) - int(audit.get("level_a", 1)),
                    same_device=bool(audit.get("same_device", False)),
                    new_account_farming=bool(audit.get("new_account_farming", False)),
                    client_xp_submitted=bool(body.get("xp") is not None),
                ))
                result = self.database.record_match_audit(audit)
                self._send(201, {**result, "xp": 0, "flags": audit["signals"], "denied": audit["action"] == "xp_denied"})
                return
            if path == "/api/battle/result":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(body.get("character_id", 0))
                self._send(200, self._apply_battle_result(user_id, character_id, body))
                return
            if path == "/api/battle/card-reward":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(body.get("character_id", 0))
                character = self.database.get_character(user_id, character_id)
                if character is None:
                    raise ValueError("Персонаж не найден")
                eligible_keys = body.get("card_keys", [])
                if not isinstance(eligible_keys, list) or len(eligible_keys) > 100:
                    raise ValueError("Некорректный список карт боя")
                eligible_key_set = {str(key) for key in eligible_keys}
                eligible_cards = [
                    card for card in load_cards()
                    if card.key in eligible_key_set
                    and card_allowed_for(card, character.get("type"))
                ]
                reward = choose_battle_reward(eligible_cards)
                if reward is None:
                    self._send(200, {"reward": None})
                    return
                collection_entry = self.database.add_card_to_collection(
                    character_id,
                    reward.key,
                )
                self._send(200, {
                    "reward": {
                        **collection_entry,
                        **card_to_dict(reward),
                    },
                })
                return
            if path == "/api/social/duel-offers":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                target_id = body.get("target_id")
                location = body.get("location", "backyard")
                if character is None or not target_id or location != "backyard":
                    raise ValueError("Предложение поединка недоступно")
                if social.pending_public_offer(character["id"], location) is not None:
                    raise ValueError("Пока активна ваша заявка, вы не можете бросать вызов")
                target = next((item for item in social.occupants(user_id, location) if str(item["character_id"]) == str(target_id)), None)
                if target is None:
                    raise ValueError("Персонаж не найден в локации")
                if target.get("type", "warrior") != character.get("type", "warrior"):
                    raise ValueError("Нельзя вызвать персонажа другого класса")
                if character["hp"] < character["max_hp"]:
                    raise ValueError("Нельзя вступить в бой: здоровье должно быть полностью восстановлено")
                if target.get("hp", target.get("max_hp")) < target.get("max_hp", 0):
                    raise ValueError("Нельзя вступить в бой: здоровье соперника должно быть полностью восстановлено")
                if target.get("kind") == "bot":
                    error = social.backyard_duel_error(character, target)
                    if error:
                        raise ValueError(error)
                    offer = social.add_duel_offer(
                        {"character_id": character["id"], "name": character["name"]},
                        target_id,
                        location,
                    )
                    offer["status"] = "accepted"
                    offer["accepted_by"] = target["character_id"]
                    self._send(201, {"accepted": True, "offer": offer})
                    return
                if target.get("afk"):
                    target_id = int(target["character_id"])
                    if (self.database.get_active_battle(character["id"], target_id)
                            or self.database.get_active_battle(target_id, character["id"])):
                        raise ValueError("Один из персонажей уже участвует в бою")
                    offer = social.add_duel_offer(
                        {"character_id": character["id"], "name": character["name"]},
                        target_id,
                        location,
                    )
                    offer["status"] = "accepted"
                    offer["accepted_by"] = target_id
                    self.database.save_active_battle(
                        character["id"], target_id,
                        {"mode": "afk_defense", "location": location},
                    )
                    self.database.mark_opponent_afk(character["id"], target_id, True)
                    self._send(201, {"accepted": True, "offer": offer})
                    return
                offer = social.add_duel_offer(
                    {"character_id": character["id"], "name": character["name"]},
                    target_id,
                    location,
                )
                self._send(201, {"accepted": False, "offer": offer})
                return
            if path == "/api/social/group-battles":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None or body.get("location") != "backyard":
                    raise ValueError("Заявка группового боя недоступна")
                if character["hp"] < character["max_hp"]:
                    raise ValueError("Для группового боя здоровье должно быть полностью восстановлено")
                if social.has_active_application(character["id"]):
                    raise ValueError("Нельзя одновременно участвовать в нескольких заявках")
                ttl = max(120, min(int(body.get("ttl", 120)), 1800))
                max_participants = int(body.get("max_participants", 10))
                if max_participants not in (6, 8, 10):
                    raise ValueError("Размер команды может быть только 6, 8 или 10")
                offer = social.create_group_battle_offer(character, ttl, max_participants)
                self._send(201, {"offer": offer})
                return
            if path.startswith("/api/social/group-battles/") and path.endswith("/join"):
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None or body.get("location") != "backyard":
                    raise ValueError("Присоединение к групповому бою недоступно")
                if character["hp"] < character["max_hp"]:
                    raise ValueError("Для группового боя здоровье должно быть полностью восстановлено")
                if social.has_active_application(character["id"]):
                    raise ValueError("Нельзя одновременно участвовать в нескольких заявках")
                offer_id = path.split("/api/social/group-battles/", 1)[1].rsplit("/join", 1)[0]
                offer = social.join_group_battle_offer(offer_id, character)
                self._send(200, {"offer": offer})
                return
            if path.startswith("/api/social/group-battles/") and path.endswith("/leave"):
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None:
                    raise ValueError("Персонаж не найден")
                offer_id = path.split("/api/social/group-battles/", 1)[1].rsplit("/leave", 1)[0]
                offer = social.leave_group_battle_offer(offer_id, character["id"])
                self._send(200, {"offer": offer})
                return
            if path == "/api/social/duel-applications":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None or body.get("location") != "backyard":
                    raise ValueError("Заявка недоступна")
                if character["hp"] < character["max_hp"]:
                    raise ValueError("Нельзя подать заявку: здоровье должно быть полностью восстановлено")
                if social.has_active_application(character["id"]):
                    raise ValueError("Нельзя одновременно участвовать в нескольких заявках")
                offer = social.add_public_duel_offer(
                    {
                        "character_id": character["id"],
                        "name": character["name"],
                    },
                    "backyard",
                    max(120, min(int(body.get("ttl", 120)), 1800)),
                )
                self._send(201, {"application": offer})
                return
            if path == "/api/social/duel-applications/cancel":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None or body.get("location") != "backyard":
                    raise ValueError("Отмена заявки недоступна")
                self._send(200, {"application": social.cancel_public_duel_offer(character["id"], "backyard")})
                return
            if path == "/api/social/duel-offers/respond":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None:
                    raise ValueError("Персонаж не найден")
                if body.get("accepted") and character["hp"] < character["max_hp"]:
                    raise ValueError("Нельзя вступить в бой: здоровье должно быть полностью восстановлено")
                if body.get("accepted") and social.has_active_application(character["id"]):
                    raise ValueError("Сначала отмените свою заявку, чтобы вступить в бой")
                offer = next(
                    (item for item in social.DUEL_OFFERS if item["id"] == body["offer_id"]),
                    None,
                )
                afk_defender_id = None
                if offer is not None and str(offer["sender_id"]).lstrip("-").isdigit():
                    sender_id = int(offer["sender_id"])
                    sender = self.database.get_character_for_battle(sender_id)
                    sender_character = sender["character"] if sender is not None else None
                    if sender_character is not None and sender_character.get("type", "warrior") != character.get("type", "warrior"):
                        raise ValueError("Нельзя принять вызов персонажа другого класса")
                    sender_presence = social.get_character_presence(sender_id)
                    if (body.get("accepted") and offer.get("target_id") is None
                            and sender_presence and sender_presence.get("afk")):
                        if sender_character is None:
                            raise ValueError("Персонаж уже недоступен")
                        if sender_character["hp"] < sender_character["max_hp"]:
                            raise ValueError("Нельзя вступить в бой: здоровье соперника должно быть полностью восстановлено")
                        if (self.database.get_active_battle(character["id"], sender_id)
                                or self.database.get_active_battle(sender_id, character["id"])):
                            raise ValueError("Этот персонаж уже участвует в бою")
                        afk_defender_id = sender_id
                offer = social.respond_duel_offer(character["id"], body["offer_id"], bool(body.get("accepted")))
                if afk_defender_id is not None:
                    self.database.save_active_battle(
                        character["id"], afk_defender_id,
                        {"mode": "afk_defense", "location": "backyard"},
                    )
                    self.database.mark_opponent_afk(character["id"], afk_defender_id, True)
                self._send(200, {"offer": offer})
                return
            
            # ============= API ИНВЕНТАРЯ (действия) =============
            # Каждое действие отвечает новым состоянием рюкзака и экипировки
            if path in ("/api/inventory/move", "/api/inventory/use", "/api/inventory/drop",
                        "/api/inventory/remove",
                        "/api/equipment/equip", "/api/equipment/unequip"):
               user_id = self.database.user_id_by_token(self._token())
               character_id = int(body.get("character_id", 0))
               if self.database.get_character(user_id, character_id) is None:
                   raise ValueError("Персонаж не найден")
               response = {}
               if path == "/api/inventory/move":
                   self.items_database.move_item(character_id, body["from_slot"], body["to_slot"])
               elif path == "/api/inventory/use":
                   response["character"] = self.items_database.use_item(user_id, character_id, body["slot_index"])
               elif path == "/api/inventory/drop":
                   self.items_database.drop_from_slot(character_id, body["slot_index"])
               elif path == "/api/inventory/remove":
                   quantity = int(body.get("quantity", 0))
                   if quantity <= 0:
                       raise ValueError("Некорректное количество предметов")
                   if not self.items_database.remove_from_inventory(
                       character_id, int(body["item_id"]), quantity
                   ):
                       raise ValueError("В рюкзаке недостаточно предметов")
               elif path == "/api/equipment/equip":
                   self.items_database.equip_item(character_id, body["slot_index"], body.get("slot"))
               else:
                   self.items_database.unequip_item(character_id, str(body["slot"]), body.get("target_slot"))
               response.update(self.items_database.get_inventory_state(character_id))
               self._send(200, response)
               return
            
            if path == "/api/character/buy_drink":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               drink_id = int(body.get("drink_id", 0))
               character = self.database.buy_drink(user_id, character_id, drink_id)
               self._send(200, {"character": character})
               return
              
            if path == "/api/character/use_drink":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               inventory_item_id = int(body.get("inventory_item_id", 0))
               character = self.database.use_drink(user_id, character_id, inventory_item_id)
               self._send(200, {"character": character})
               return
              
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError, KeyError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def do_DELETE(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            if path.startswith("/api/decks/"):
                deck_id = int(path.rsplit("/", 1)[1])
                body = self._body()
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(body.get("character_id", 0))
                character = self.database.get_character(user_id, character_id)
                if character is None:
                    raise ValueError("Персонаж не найден")
                if not self.items_database.delete_deck(character_id, deck_id):
                    raise ValueError("Колода не найдена")
                self._send(200, {"deleted": True})
                return
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def do_PUT(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            if path.startswith("/api/opponents/"):
                opponent_id = path.rsplit("/", 1)[1]
                user_id = self.database.user_id_by_token(self._token())
                opponent = self.database.update_bot(user_id, opponent_id, self._body())
                self._send(200, {"opponent": opponent})
                return
            if path.startswith("/api/characters/"):
                character_id = int(path.rsplit("/", 1)[1])
                user_id = self.database.user_id_by_token(self._token())
                body = self._body()
                # Check if this is a profession update
                if "profession_type" in body and len(body) == 1:
                    character = self.database.update_character_profession(user_id, character_id, body["profession_type"])
                    self._send(200, {"character": character})
                else:
                    current = self.database.get_character(user_id, character_id)
                    if current is None:
                        raise ValueError("Персонаж не найден")
                    self._validate_client_character_update(current, body)
                    character = self.database.save_character(user_id, character_id, body)
                    self._send(200, {"character": character})
                return
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError, KeyError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def log_message(self, format_string, *args):
        print(f"[server] {self.address_string()} - {format_string % args}")


class GameHTTPServer(ThreadingHTTPServer):
    # В Windows SO_REUSEADDR позволяет второму серверу молча занять тот же порт
    allow_reuse_address = os.name != "nt"


def run():
    print("Подготавливаю дороги к загородным постройкам...")
    roads_payload()
    server = GameHTTPServer((config.HOST, config.PORT), GameRequestHandler)
    stop_bot_battles = threading.Event()
    restart_requested = threading.Event()
    bot_battle_thread = threading.Thread(
        target=_run_bot_battles,
        args=(stop_bot_battles,),
        name="bot-battle-scheduler",
        daemon=True,
    )
    bot_battle_thread.start()
    restart_thread = threading.Thread(
        target=_run_scheduled_restart,
        args=(server, stop_bot_battles, restart_requested),
        name="scheduled-server-restart",
        daemon=True,
    )
    restart_thread.start()
    print(f"Game server: http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped")
    finally:
        stop_bot_battles.set()
        bot_battle_thread.join(timeout=2)
        restart_thread.join(timeout=2)
        server.server_close()
    if restart_requested.is_set():
        raise SystemExit(1)


def _run_bot_battles(stop_event):
    while not stop_event.is_set():
        try:
            run_bot_battle_tick()
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
