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
from core.production_buildings import BUILDINGS
from server.production_buildings import DEFAULT_FACTION, ProductionBuildings
from server.city_population import CityPopulation
from server.city_upgrade import city_upgrade_payload
from server.world_events import run_world_event_watcher
from server.transport import TransportService
from server.world_map import terrain_payload
from server.structures import city_structures
from server.world_roads import roads_payload


class GameRequestHandler(BaseHTTPRequestHandler):
    CHAT_LOCATIONS = ("tavern", "city", "world_map", "character_room")
    database = Database()
    items_database = ItemsDatabase(database)
    chat_send_times = {}

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
        self.database.add_chat_message(character["id"], "world", text)

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
        position_x = query.get("position_x", [None])[0]
        position_y = query.get("position_y", [None])[0]
        if location == "world_map" and position_x is not None and position_y is not None:
            try:
                position_x, position_y = float(position_x), float(position_y)
            except (TypeError, ValueError):
                raise ValueError("Некорректная позиция персонажа")
            character = dict(character)
            character["position_x"] = position_x
            character["position_y"] = position_y
            direction = query.get("position_direction", ["s"])[0]
            character["position_direction"] = direction if direction in {
                "n", "ne", "e", "se", "s", "sw", "w", "nw"
            } else "s"
        if social.update_presence(token, user_id, character, location):
            self._announce_player_status(character, "присоединился к игре")
        self._send(200, {
            "occupants": social.occupants(user_id, location),
            "messages": self.database.get_chat_history(character_id, location),
        })

    def _handle_server_status(self):
        self.database.user_id_by_token(self._token())
        server_time = time.time()
        self._send(200, {
            "online_players": self.database.online_player_count(),
            "restart_notice": maintenance.public_notice(),
            "server_time": server_time,
            "server_timezone": config.SERVER_TIMEZONE,
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
        if location == "world":
            raise ValueError("В мировой канал может писать только сервер")
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
                with self.database.connection() as connection:
                    state = connection.execute(
                        "SELECT city_level FROM city_population_state WHERE world_id=%s AND faction=%s",
                        (self.database.world_id, DEFAULT_FACTION),
                    ).fetchone()
                city_level = 1 if state is None else int(state["city_level"])
                with self.database.connection() as connection:
                    city_visual_state = city_upgrade_payload(
                        connection, (self.database.world_id, DEFAULT_FACTION), time.time()
                    )
                terrain = terrain_payload(city_level)
                terrain["city_visual_state"] = city_visual_state
                self._send(200, {"terrain": terrain})
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
            if path.startswith("/api/castle/"):
                parts = path.split("/")
                if len(parts) != 5 or parts[4] != "population":
                    self._send(404, {"error": "Путь замка не найден"})
                    return
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(parts[3])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                state = CityPopulation(self.database).get_state(character_id)
                self._send(200, {"population": state})
                return
            if path == "/api/world/traveling-citizens":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(self._query().get("character_id", [0])[0])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                travelers = CityPopulation(self.database).get_traveling_citizens(character_id)
                self._send(200, {"citizens": travelers})
                return
            if path == "/api/world/traveling-convoys":
                user_id = self.database.user_id_by_token(self._token())
                character_id = int(self._query().get("character_id", [0])[0])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                convoys = TransportService(self.database).get_world_convoys(character_id)
                self._send(200, {"convoys": convoys})
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
            
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError) as error:
            self._handle_error(error)
        except Exception as error:
            self._handle_server_error(error)

    def do_POST(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            body = self._body()
            if path.startswith("/api/castle/"):
                parts = path.split("/")
                if len(parts) == 5 and parts[4] == "treasury":
                    user_id = self.database.user_id_by_token(self._token())
                    character_id = int(parts[3])
                    if self.database.get_character(user_id, character_id) is None:
                        raise ValueError("Персонаж не найден")
                    state = CityPopulation(self.database).transfer_treasury(
                        character_id, body.get("direction"), body.get("amount_copper")
                    )
                    self._send(200, {"population": state})
                    return
                if len(parts) == 5 and parts[4] == "treasury-edict":
                    user_id = self.database.user_id_by_token(self._token())
                    character_id = int(parts[3])
                    if self.database.get_character(user_id, character_id) is None:
                        raise ValueError("Персонаж не найден")
                    state = CityPopulation(self.database).start_treasury_edict(character_id)
                    self._send(200, {"population": state})
                    return
                if len(parts) == 6 and parts[4] == "upgrades":
                    user_id = self.database.user_id_by_token(self._token())
                    character_id = int(parts[3])
                    if self.database.get_character(user_id, character_id) is None:
                        raise ValueError("Персонаж не найден")
                    state = CityPopulation(self.database).start_castle_upgrade(
                        character_id, parts[5]
                    )
                    self._send(200, {"population": state})
                    return

                    self._send(404, {"error": "Путь замка не найден"})
                    return
                user_id = self.database.user_id_by_token(self._token())
                character_id, citizen_id = int(parts[3]), int(parts[5])
                if self.database.get_character(user_id, character_id) is None:
                    raise ValueError("Персонаж не найден")
                population = CityPopulation(self.database)
                if parts[6] == "assign":
                    state = population.assign_citizen(
                        character_id, citizen_id, body.get("building"), body.get("slot_index")
                    )
                else:
                    state = population.recall_citizen(character_id, citizen_id)
                self._send(200, {"population": state})
                return
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
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                name = str(body.get("name", "")).strip()
                profession_type = str(body.get("profession_type", "warrior")).strip().lower()
                self.database.validate_character_name(name)
                valid_professions = ["warrior", "archer", "assassin", "mage"]
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
                elif action == "storage/deposit":
                    state = buildings.deposit_to_storage(
                        character_id, building, body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "storage/withdraw":
                    state = buildings.withdraw_from_storage(
                        character_id, building, body.get("resource"), body.get("quantity", 0)
                    )
                elif action == "upgrade/deposit":
                    state = buildings.deposit_material(
                        character_id, building, body.get("item_id", 0),
                        body.get("quantity", 0), source=body.get("source", "warehouse"),
                    )
                elif action == "upgrade/start":
                    state = buildings.start_upgrade(character_id, building)
                elif action == "farm/upgrade" and building == "farm":
                    state = buildings.purchase_farm_upgrade(
                        character_id, body.get("upgrade_id"),
                    )
                elif action == "lumber-camp/upgrade" and building == "lumber_camp":
                    state = buildings.purchase_lumber_camp_upgrade(
                        character_id, body.get("upgrade_id"),
                    )
                elif action == "stall-upgrade/contribute" and building == "stable":
                    state = buildings.contribute_stall_upgrade(
                        character_id, body.get("upgrade_id"), body.get("resource"),
                        body.get("quantity", 0), source=body.get("source"),
                    )
                elif action == "stall-upgrade/purchase" and building == "stable":
                    state = buildings.purchase_stall_upgrade(character_id, body.get("upgrade_id"))
                elif action == "cart/contribute" and building == "stable":
                    state = buildings.contribute_cart(
                        character_id, body.get("resource"), body.get("quantity", 0),
                        source=body.get("source"),
                    )
                elif action == "cart/purchase" and building == "stable":
                    state = buildings.purchase_cart(character_id, body.get("grade", 1))
                elif action == "cart/repair" and building == "stable":
                    state = buildings.repair_cart(character_id, body.get("cart_id", ""))
                elif action == "cart/rename" and building == "stable":
                    state = buildings.rename_cart(
                        character_id, body.get("cart_id", ""), body.get("name", "")
                    )
                elif action == "cart/auto_repair" and building == "stable":
                    state = buildings.set_cart_auto_repair(
                        character_id, body.get("cart_id", ""), body.get("mode")
                    )
                elif action == "transport/dispatch" and building == "stable":
                    convoy = TransportService(self.database).dispatch(character_id, body)
                    state = ProductionBuildings(self.database).get_state(character_id, "stable")
                    self._send(201, {"building": state, "convoy": convoy})
                    return
                elif action == "transport/pin" and building == "stable":
                    TransportService(self.database).set_pinned(
                        character_id, body.get("convoy_id"), body.get("pinned", False),
                    )
                    state = ProductionBuildings(self.database).get_state(character_id, "stable")
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

    def do_PUT(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
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
    stop_event = threading.Event()
    restart_requested = threading.Event()
    restart_thread = threading.Thread(
        target=_run_scheduled_restart,
        args=(server, stop_event, restart_requested),
        name="scheduled-server-restart",
        daemon=True,
    )
    restart_thread.start()
    population_thread = threading.Thread(
        target=_run_city_population,
        args=(stop_event,),
        name="city-population-ticks",
        daemon=True,
    )
    population_thread.start()
    world_event_thread = threading.Thread(
        target=run_world_event_watcher,
        args=(GameRequestHandler.database, stop_event),
        name="world-event-watcher",
        daemon=True,
    )
    world_event_thread.start()
    print(f"Game server: http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped")
    finally:
        stop_event.set()
        restart_thread.join(timeout=2)
        population_thread.join(timeout=2)
        world_event_thread.join(timeout=2)
        server.server_close()
    if restart_requested.is_set():
        raise SystemExit(1)


def _run_scheduled_restart(server, stop_event, restart_requested):
    while not stop_event.wait(0.5):
        if maintenance.restart_due():
            restart_requested.set()
            server.shutdown()
            return


def _run_city_population(stop_event):
    population = CityPopulation(GameRequestHandler.database)
    while not stop_event.is_set():
        try:
            population.tick_all()
        except Exception:
            traceback.print_exc()
        if stop_event.wait(1):
            break


if __name__ == "__main__":
    run()
