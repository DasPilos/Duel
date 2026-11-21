import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from server import config
from server.database import Database
from server.items_database import ItemsDatabase, hidden_items_for_mode
from server import build_info, maintenance, social, world_map
from server import map_worlds
from server.map_editor import DEFAULT_MAP_SIZE, load_published_map


MAP_BODY_LIMIT = 16 * 1024 * 1024


class GameRequestHandler(BaseHTTPRequestHandler):
    # Постоянное соединение (keep-alive): клиент мира шлёт снимки частыми запросами, новый TCP на каждый — лишняя задержка.
    protocol_version = "HTTP/1.1"
    # Простаивающее соединение закрывается, иначе поток обработчика висит бесконечно.
    timeout = 30
    CHAT_LOCATIONS = ("tavern", "city", "world_map", "character_room")
    database = None
    items_database = None
    world = None
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

    def _send_map_asset(self, item_key):
        user_id = self.database.user_id_by_token(self._token())
        if not self.database.is_moderator(user_id):
            raise ValueError("Недостаточно прав модератора")
        data = self.database.map_asset(item_key)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        # Карта 64×64 с тайлами весит сотни килобайт, поэтому маршруты карт получают больший лимит
        limit = MAP_BODY_LIMIT if urlparse(self.path).path.startswith("/api/map/") else 64 * 1024
        if length > limit:
            # Тело не прочитано: соединение нельзя переиспользовать, закрываем его после ответа.
            self.close_connection = True
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

    def _dispatch_mode_api(self, method, path, body=None):
        return False

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
        occupants = social.occupants(user_id, location)
        if config.GAME_SCHEMA == "front_line":
            nicknames = self.database.game_nicknames(
                occupant.get("user_id", 0) for occupant in occupants
            )
            for occupant in occupants:
                nickname = nicknames.get(int(occupant.get("user_id", 0)), "")
                if nickname:
                    occupant["name"] = nickname
        self._send(200, {
            "occupants": occupants,
            "messages": self.database.get_chat_history(character_id, location),
        })

    def _handle_server_status(self):
        self.database.user_id_by_token(self._token())
        server_time = time.time()
        server_offset = datetime.fromtimestamp(server_time, ZoneInfo(config.SERVER_TIMEZONE)).utcoffset()
        self._send(200, {
            "online_players": self.database.online_player_count(),
            "build_id": build_info.SERVER_BUILD_ID,
            "restart_notice": maintenance.public_notice(),
            "client_reload": maintenance.public_client_reload(),
            "server_time": server_time,
            "server_timezone": config.SERVER_TIMEZONE,
            "server_utc_offset_seconds": int(server_offset.total_seconds()),
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
            if self._dispatch_mode_api("GET", path):
                return
            if path == "/health":
                self._send(200, {"status": "ok"})
                return
            if path == "/api/version":
                query = self._query()
                try:
                    protocol_version = int(query["protocol"][0]) if "protocol" in query else None
                except ValueError as error:
                    raise ValueError("Некорректная версия API-протокола") from error
                self._send(200, build_info.public_version_info(
                    query.get("app", [""])[0],
                    query.get("version", [""])[0],
                    protocol_version,
                ))
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
            if path == "/api/worlds":
                viewer_id = self.database.user_id_by_token(self._token())
                self._send(200, {"worlds": self.database.list_worlds(viewer_id=viewer_id)})
                return
            if path == "/api/map/palette":
                self.database.user_id_by_token(self._token())
                self._send(200, self.database.map_palette_state())
                return
            if path == "/api/map/catalog":
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                self._send(200, {
                    "items": self.database.map_catalog(),
                    "tile_groups": self.database.custom_tile_groups(),
                })
                return
            if path == "/api/map/mob-settings":
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                query = self._query()
                settings = map_worlds.load_mob_settings(
                    query.get("mode", [""])[0],
                    query.get("kind", [""])[0],
                )
                self._send(200, {"settings": settings})
                return
            asset_prefix = "/api/map/assets/"
            if path.startswith(asset_prefix):
                item_key = path[len(asset_prefix):]
                if not item_key or "/" in item_key:
                    raise ValueError("Некорректный ключ ресурса карты")
                self._send_map_asset(item_key)
                return
            saved_map_prefix = "/api/map/editor/saved/"
            if path.startswith(saved_map_prefix):
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                saved_id = path[len(saved_map_prefix):]
                if not saved_id.isdigit():
                    raise ValueError("Некорректный id карты")
                self._send(200, {"map": self.database.get_saved_map(int(saved_id))})
                return
            if path == "/api/map/saved":
                viewer_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(viewer_id):
                    raise ValueError("Недостаточно прав модератора")
                mode = self._query().get("mode", [None])[0]
                self._send(200, {"saved_maps": self.database.list_saved_maps(mode)})
                return
            if path == "/api/me":
                user = self.database.user_role(self.database.user_id_by_token(self._token()))
                self._send(200, {"user": user})
                return
            if path == "/api/lobby":
                self.database.user_id_by_token(self._token())
                self._send(200, {"players": self.database.lobby_members()})
                return
            if path == "/api/items/catalog":
                self.database.user_id_by_token(self._token())
                raw_ids = self._query().get("ids", [""])[0]
                try:
                    item_ids = [int(part) for part in raw_ids.split(",") if part.strip()]
                except ValueError:
                    self._send(400, {"error": "Некорректные id предметов"})
                    return
                items = (
                    self.items_database.get_all_catalog_items()
                    if not raw_ids.strip()
                    else self.items_database.get_catalog_items(item_ids)
                )
                self._send(200, {"items": items})
                return
            if path == "/api/items/equipment":
                self.database.user_id_by_token(self._token())
                raw_slots = self._query().get("slots", [""])[0]
                slots = [part.strip() for part in raw_slots.split(",") if part.strip()]
                self._send(200, {"items": self.items_database.get_equipment_items(slots)})
                return
            if path == "/api/items/materials":
                self.database.user_id_by_token(self._token())
                self._send(200, {"items": self.items_database.get_material_items()})
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
            if self._dispatch_mode_api("POST", path, body):
                return
            if path == "/api/map/mob-settings":
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                if not isinstance(body, dict):
                    raise ValueError("Настройки моба должны быть объектом")
                settings = map_worlds.save_mob_settings(
                    body.get("mode", ""),
                    body.get("kind", ""),
                    body.get("settings", {}),
                )
                self._send(200, {"settings": settings})
                return
            if path == "/api/map/tile-groups":
                user_id = self.database.user_id_by_token(self._token())
                self._send(201, self.database.save_custom_tile_group(user_id, body))
                return
            if path == "/api/register":
                username = str(body.get("username", "")).strip()
                password = str(body.get("password", ""))
                if not 3 <= len(username) <= 32 or not 6 <= len(password) <= 128:
                    raise ValueError("Имя: 3-32 символа, пароль: 6-128 символов")
                self._send(201, {"user": self.database.register(username, password)})
                return
            if path in ("/api/map/editor/test-world", "/api/worlds/create"):
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, map_worlds.create_test_world(self.database, user_id, body))
                return
            if path == "/api/worlds/start":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, map_worlds.start_world(self.database, user_id, int(body.get("world_id") or 0)))
                return
            if path == "/api/items/catalog":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, {"item": self.items_database.create_item(user_id, body.get("form") or {})})
                return
            if path == "/api/map/editor/saved":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, map_worlds.save_map(self.database, user_id, body))
                return
            if path == "/api/map/palette/preview":
                user_id = self.database.user_id_by_token(self._token())
                result = self.database.preview_map_palette(
                    user_id, body.get("username", ""), body.get("password", ""),
                    body.get("overrides", {}),
                )
                self._send(200, result)
                return
            if path == "/api/map/palette/apply":
                user_id = self.database.user_id_by_token(self._token())
                result = self.database.apply_map_palette(
                    user_id, body.get("username", ""), body.get("password", ""),
                    body.get("overrides", {}), body.get("expected_version", 0),
                    body.get("resolutions", {}),
                )
                self._send(200, result)
                return
            if path == "/api/map/editor/publish":
                user_id = self.database.user_id_by_token(self._token())
                target_world_id = int(body.get("world_id") or 0)
                target_world = self.database.world_info(target_world_id)
                requested_mode = str(body.get("mode", "tower"))
                if requested_mode != config.GAME_SCHEMA or target_world["mode"] != config.GAME_SCHEMA:
                    raise ValueError("Карту можно публиковать только в мир текущего режима")
                published = self.database.publish_map(
                    body.get("cells", []), target_world_id, body.get("name", ""),
                    body.get("map_w", DEFAULT_MAP_SIZE), body.get("map_h", DEFAULT_MAP_SIZE), user_id,
                    body.get("mobs", []), requested_mode, spawns=body.get("spawns", []),
                    saved_id=int(body.get("saved_id") or 0) or None,
                    crystals=body.get("crystals", {}), harvest_enabled=bool(body.get("harvest_enabled", False)),
                )
                if published["world_id"] == self.database.world_id:
                    apply_published_map(self.database, GameRequestHandler.world)
                self._send(200, published)
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
            if path == "/api/server/client-reload":
                user_id = self.database.user_id_by_token(self._token())
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав для управления сервером")
                if body.get("action") == "cancel":
                    maintenance.cancel_client_reload()
                    self._send(200, {"client_reload": None})
                    return
                message = str(body.get("message", "")).strip() or None
                if message and len(message) > 300:
                    raise ValueError("Текст уведомления: не больше 300 символов")
                notice = maintenance.request_client_reload(message=message)
                self._send(200, {"client_reload": notice})
                return
            if path == "/api/login":
                session = self.database.login(str(body.get("username", "")), str(body.get("password", "")))
                if not self.database.can_enter_current_world(self.database.user_id_by_token(session["token"])):
                    self.database.disconnect(session["token"])
                    raise ValueError("Этот мир пока тестовый: вход открыт модераторам и админам")
                self._send(200, session)
                return
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                name = str(body.get("name", "")).strip()
                profession_type = str(body.get("profession_type", "warrior")).strip().lower()
                self.database.validate_character_name(name)
                valid_professions = ["warrior", "archer", "assassin", "mage"]
                if profession_type not in valid_professions:
                    raise ValueError(f"Профессия должна быть одной из: {', '.join(valid_professions)}")
                character = self.database.create_character(user_id, name, profession_type, body.get("stats"))
                self.items_database.grant_base_equipment(character["id"])
                self._send(201, {"character": character})
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
                if character_id is not None and self.world is not None:
                    # Выход из мира сохраняет HP и MP до записи чекпоинта
                    self.world.leave(user_id, character_id)
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
               if not self.database.character_belongs_to_user(user_id, character_id):
                   raise ValueError("Персонаж не найден")
               def perform_inventory_action():
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
                   return response

               if self.world is None:
                   response = perform_inventory_action()
               else:
                   response = self.world.run_inventory_action(user_id, character_id, perform_inventory_action)
               self._send(200, response)
               return

            if path == "/api/storage/transfer":
               user_id = self.database.user_id_by_token(self._token())
               character_id = int(body.get("character_id", 0))
               if not self.database.character_belongs_to_user(user_id, character_id):
                   raise ValueError("Персонаж не найден")
               def perform_storage_transfer():
                   self.items_database.transfer_storage(
                       character_id,
                       body.get("storage_type", ""),
                       body.get("direction", ""),
                       body.get("quantity", 0),
                       slot_index=body.get("slot_index"),
                       storage_item_id=body.get("storage_item_id"),
                   )
                   return {
                       **self.items_database.get_inventory_state(character_id),
                       "storage": self.items_database.get_storage(
                           character_id, str(body.get("storage_type", ""))
                       ),
                   }

               if self.world is None:
                   response = perform_storage_transfer()
               else:
                   response = self.world.run_inventory_action(
                       user_id, character_id, perform_storage_transfer
                   )
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

            item_match = re.fullmatch(r"/api/items/catalog/(\d+)", path)
            if item_match:
                body = self._body()
                if not isinstance(body, dict):
                    raise ValueError("Тело запроса должно быть объектом")
                user_id = self.database.user_id_by_token(self._token())
                item = self.items_database.update_item(
                    user_id,
                    int(item_match.group(1)),
                    body.get("form") or {},
                )
                self._send(200, {"item": item})
                return

            if path.startswith("/api/characters/"):
                character_id = int(path.rsplit("/", 1)[1])
                user_id = self.database.user_id_by_token(self._token())
                body = self._body()
                # HP и MP ведёт сервер (регенерация, бой, отдых), клиентская запись их не меняет
                body.pop("hp", None)
                body.pop("mp", None)
                # Check if this is a profession update
                if "profession_type" in body and len(body) == 1:
                    character = self.database.update_character_profession(user_id, character_id, body["profession_type"])
                    self._send(200, {"character": character})
                else:
                    current = self.database.get_character(user_id, character_id)
                    if current is None:
                        raise ValueError("Персонаж не найден")
                    self._validate_client_character_update(current, body)
                    # Опыт пишет только сервер (награда за моба): устаревший снимок клиента его не откатывает
                    body["xp"] = current["xp"]
                    character = self.database.save_character(user_id, character_id, body)
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
            self._send(404, {"error": "Маршрут не найден"})
        except Exception as error:
            self._handle_server_error(error)

    def log_message(self, format_string, *args):
        print(f"[server] {self.address_string()} - {format_string % args}")


class GameHTTPServer(ThreadingHTTPServer):
    # В Windows SO_REUSEADDR позволяет второму серверу молча занять тот же порт
    allow_reuse_address = os.name != "nt"


def apply_published_map(database, world=None):
    """Рельеф и размер мира берутся из опубликованной карты редактора; запущенный мир перечитывает их без перезапуска."""
    terrain, published = load_published_map(database)
    if world is not None:
        world.reload_terrain(terrain, published)
    else:
        world_map.apply_live_terrain(terrain, published)


def run_mode_server(mode, request_handler, *, world_factory=None, startup=None, background_workers=()):
    from server.mode_registry import get_mode

    mode_config = get_mode(mode)
    if not mode_config.get("runtime_ready", True) or not mode_config.get("entrypoint"):
        raise ValueError(f"No runtime is registered for game mode {mode!r}")
    if config.GAME_SCHEMA != mode_config["schema"]:
        raise RuntimeError(
            f"Set GAME_SCHEMA={mode_config['schema']!r} before starting this mode's world process"
        )
    database = Database()
    world = database.world_info(config.WORLD_ID)
    if world["code"] == "lobby":
        raise RuntimeError("The lobby has no gameplay runtime; use python -m server.central_main")
    if world["mode"] != mode:
        raise RuntimeError(
            f"World mode {world['mode']!r} cannot start in the {mode!r} runtime"
        )
    GameRequestHandler.database = database
    GameRequestHandler.items_database = ItemsDatabase(database)
    GameRequestHandler.items_database.hidden_item_ids = hidden_items_for_mode(mode)
    GameRequestHandler.world = None
    request_handler.database = database
    request_handler.items_database = GameRequestHandler.items_database
    apply_published_map(database)
    if startup is not None:
        startup(database)
    server = GameHTTPServer((config.HOST, config.PORT), request_handler)
    if world_factory is not None:
        GameRequestHandler.world = world_factory(database, GameRequestHandler.items_database)
        GameRequestHandler.world.start()
    stop_event = threading.Event()
    restart_requested = threading.Event()
    restart_thread = threading.Thread(
        target=_run_scheduled_restart,
        args=(server, stop_event, restart_requested),
        name="scheduled-server-restart",
        daemon=True,
    )
    restart_thread.start()
    worker_threads = []
    for name, worker in background_workers:
        thread = threading.Thread(
            target=worker,
            args=(database, stop_event),
            name=name,
            daemon=True,
        )
        thread.start()
        worker_threads.append(thread)
    print(f"Game server: http://{config.HOST}:{config.PORT}")
    try:
        database.set_world_server(config.WORLD_ID, config.PUBLIC_URL.rstrip("/"))
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped")
    finally:
        stop_event.set()
        restart_thread.join(timeout=2)
        for thread in worker_threads:
            thread.join(timeout=2)
        if GameRequestHandler.world is not None:
            GameRequestHandler.world.stop()
        try:
            database.set_world_server(config.WORLD_ID, None)
        finally:
            server.server_close()
    if restart_requested.is_set():
        raise SystemExit(1)


def _run_scheduled_restart(server, stop_event, restart_requested):
    while not stop_event.wait(0.5):
        if maintenance.restart_due():
            restart_requested.set()
            server.shutdown()
            return


def run():
    mode = config.GAME_SCHEMA
    if mode == "tower":
        from tower.server.main import run as run_tower
        return run_tower()
    if mode == "economy":
        from economy.server.main import run as run_economy
        return run_economy()
    raise RuntimeError("Set GAME_SCHEMA to 'tower' or 'economy' before starting a world process")


if __name__ == "__main__":
    run()
