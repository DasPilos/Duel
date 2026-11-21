"""Always-on account, lobby, mode and world registry server."""

import json
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.map_catalog import DEFAULT_MAP_SIZE
from server import avatars, build_info, config, map_editor, map_worlds
from core import spawn_squads
from server.database import Database
from server.mode_registry import get_mode, list_modes


class CentralRequestHandler(BaseHTTPRequestHandler):
    database = None

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        path = urlparse(self.path).path
        if path.startswith("/api/map/"):
            limit = 16 * 1024 * 1024
        elif path == "/api/account/avatar":
            limit = 256 * 1024
        else:
            limit = 64 * 1024
        if length > limit:
            raise ValueError("Слишком большой запрос")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _token(self):
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise ValueError("Требуется авторизация")
        return authorization[7:].strip()

    def _user_id(self):
        return self.database.user_id_by_token(self._token())

    def _dispatch_error(self, error):
        if isinstance(error, (ValueError, json.JSONDecodeError)):
            self._send(400, {"error": str(error)})
            return
        traceback.print_exc()
        self._send(500, {"error": "Внутренняя ошибка центрального сервера"})

    def do_GET(self):
        try:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/health":
                self._send(200, {"status": "ok", "service": "central"})
                return
            if path == "/api/version":
                query = parse_qs(urlparse(self.path).query)
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
            if path == "/api/modes":
                self._user_id()
                self._send(200, {"modes": list_modes()})
                return
            if path == "/api/worlds":
                user_id = self._user_id()
                worlds = self.database.list_worlds(viewer_id=user_id)
                self._send(200, {"worlds": [world for world in worlds if world["code"] != "lobby"]})
                return
            if path == "/api/lobby":
                self._user_id()
                self._send(200, {"players": self.database.lobby_members()})
                return
            if path == "/api/lobby/chat":
                user_id = self._user_id()
                self._send(200, {"messages": self.database.lobby_chat_history(viewer_id=user_id)})
                return
            if path == "/api/account/avatar":
                png = self.database.get_avatar(self._user_id())
                self._send(200, {"png_base64": avatars.encode_avatar(png) if png else None})
                return
            if path == "/api/me":
                self._send(200, {"user": self.database.user_role(self._user_id())})
                return
            if path == "/api/map/catalog":
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                self._send(200, {
                    "items": self.database.map_catalog(),
                    "tile_groups": self.database.custom_tile_groups(),
                })
                return
            if path == "/api/items/catalog":
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                mode = parse_qs(urlparse(self.path).query).get("mode", ["tower"])[0]
                items = map_worlds.mode_item_database(self.database, mode)
                self._send(200, {
                    "items": items.get_all_catalog_items(),
                })
                return
            if path == "/api/map/mob-settings":
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                query = parse_qs(urlparse(self.path).query)
                settings = map_worlds.load_mob_settings(
                    query.get("mode", [""])[0],
                    query.get("kind", [""])[0],
                )
                self._send(200, {"settings": settings})
                return
            asset_prefix = "/api/map/assets/"
            if path.startswith(asset_prefix):
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                item_key = path[len(asset_prefix):]
                if not item_key or "/" in item_key:
                    raise ValueError("Некорректный ключ ресурса карты")
                data = self.database.map_asset(item_key)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            saved_map_prefix = "/api/map/editor/saved/"
            if path.startswith(saved_map_prefix):
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                saved_id = path[len(saved_map_prefix):]
                if not saved_id.isdigit():
                    raise ValueError("Некорректный id карты")
                self._send(200, {"map": self.database.get_saved_map(int(saved_id))})
                return
            if path == "/api/map/saved":
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                mode = parse_qs(urlparse(self.path).query).get("mode", [None])[0]
                self._send(200, {"saved_maps": self.database.list_saved_maps(mode)})
                return
            if path == "/api/map/palette":
                self._user_id()
                self._send(200, self.database.map_palette_state())
                return
            if path == "/api/map/saved":
                user_id = self._user_id()
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                mode = parse_qs(urlparse(self.path).query).get("mode", [None])[0]
                self._send(200, {"saved_maps": self.database.list_saved_maps(mode)})
                return
            self._send(404, {"error": "Маршрут центрального сервера не найден"})
        except Exception as error:
            self._dispatch_error(error)

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
            if path == "/api/login":
                self._send(200, self.database.login(
                    str(body.get("username", "")), str(body.get("password", ""))
                ))
                return
            if path == "/api/sessions/disconnect":
                self._send(200, self.database.disconnect(self._token()))
                return
            world_connect = re.fullmatch(r"/api/worlds/(\d+)/connect", path)
            if world_connect:
                session = self.database.connect_to_world(
                    self._token(), int(world_connect.group(1))
                )
                self._send(200, session)
                return
            user_id = self._user_id()
            if path == "/api/items/catalog":
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                items = map_worlds.mode_item_database(self.database, body.get("mode", "tower"))
                self._send(201, {"item": items.create_item(user_id, body.get("form") or {})})
                return
            if path == "/api/map/mob-settings":
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
            if path == "/api/map/spawn-preview":
                if not self.database.is_moderator(user_id):
                    raise ValueError("Недостаточно прав модератора")
                self._send(200, spawn_squads.preview(body, map_editor.MAX_MOB_SPAWN_COUNT))
                return
            if path == "/api/map/tile-groups":
                self._send(201, self.database.save_custom_tile_group(user_id, body))
                return
            if path == "/api/lobby/chat":
                message = self.database.add_lobby_chat_message(
                    user_id, body.get("text", ""), body.get("recipient_user_id")
                )
                self._send(201, {"message": message})
                return
            if path == "/api/account/avatar":
                avatar = avatars.decode_avatar(body.get("png_base64"))
                self.database.save_avatar(user_id, avatar)
                self._send(200, {"avatar": {"size": avatars.AVATAR_SIZE}})
                return
            if path == "/api/account/password":
                user = self.database.change_password(
                    user_id,
                    self._token(),
                    str(body.get("current_password", "")),
                    str(body.get("new_password", "")),
                )
                self._send(200, {"user": user})
                return
            if path == "/api/account/game-nickname":
                user = self.database.change_game_nickname(
                    user_id,
                    self._token(),
                    str(body.get("game_nickname", "")),
                )
                self._send(200, {"user": user})
                return
            if path in ("/api/worlds/create", "/api/map/editor/test-world"):
                self._send(200, map_worlds.create_test_world(self.database, user_id, body))
                return
            if path == "/api/worlds/start":
                world_id = int(body.get("world_id") or 0)
                self._send(200, map_worlds.start_world(self.database, user_id, world_id))
                return
            if path == "/api/map/editor/saved":
                mode_key = str(body.get("mode", "tower"))
                if get_mode(mode_key)["key"] == "deck":
                    raise ValueError("Карты Deck сохраняются через отдельный API режима")
                self._send(200, map_worlds.save_map(self.database, user_id, body))
                return
            if path == "/api/map/palette/preview":
                self._send(200, self.database.preview_map_palette(
                    user_id, body.get("username", ""), body.get("password", ""),
                    body.get("overrides", {}),
                ))
                return
            if path == "/api/map/palette/apply":
                self._send(200, self.database.apply_map_palette(
                    user_id, body.get("username", ""), body.get("password", ""),
                    body.get("overrides", {}), body.get("expected_version", 0),
                    body.get("resolutions", {}),
                ))
                return
            if path == "/api/map/editor/publish":
                target_world_id = int(body.get("world_id") or 0)
                target_world = self.database.world_info(target_world_id)
                requested_mode = str(body.get("mode", "tower"))
                mode = get_mode(requested_mode)
                if mode["key"] == "deck":
                    raise ValueError("Карты Deck публикуются через отдельный API режима")
                if not mode.get("runtime_ready", True):
                    raise ValueError(f"Игровой сервер режима «{mode['name']}» ещё не подключён")
                target_mode = get_mode(target_world["mode"])
                if target_world["code"] == "lobby":
                    raise ValueError("Нельзя публиковать карту в лобби")
                if mode["key"] != target_mode["key"]:
                    raise ValueError("Режим карты должен совпадать с режимом мира")
                published = self.database.publish_map(
                    body.get("cells", []), target_world_id, body.get("name", ""),
                    body.get("map_w", DEFAULT_MAP_SIZE), body.get("map_h", DEFAULT_MAP_SIZE), user_id,
                    body.get("mobs", []), mode["key"], spawns=body.get("spawns", []),
                    saved_id=int(body.get("saved_id") or 0) or None,
                    crystals=body.get("crystals", {}),
                    harvest_enabled=bool(body.get("harvest_enabled", False)),
                )
                self._send(200, published)
                return
            self._send(404, {"error": "Маршрут центрального сервера не найден"})
        except Exception as error:
            self._dispatch_error(error)

    def do_PUT(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            match = re.fullmatch(r"/api/items/catalog/(\d+)", path)
            if not match:
                self._send(404, {"error": "Маршрут центрального сервера не найден"})
                return
            body = self._body()
            if not isinstance(body, dict):
                raise ValueError("Тело запроса должно быть объектом")
            user_id = self._user_id()
            if not self.database.is_moderator(user_id):
                raise ValueError("Недостаточно прав модератора")
            items = map_worlds.mode_item_database(self.database, body.get("mode", "tower"))
            item = items.update_item(user_id, int(match.group(1)), body.get("form") or {})
            self._send(200, {"item": item})
        except Exception as error:
            self._dispatch_error(error)

    def log_message(self, format_string, *args):
        print(f"[central] {self.address_string()} - {format_string % args}")


def run():
    CentralRequestHandler.database = Database(central=True)
    stop_event = threading.Event()
    front_line_thread = threading.Thread(
        target=_maintain_front_line_world,
        args=(CentralRequestHandler.database, stop_event),
        name="front-line-matchmaking-server",
        daemon=True,
    )
    front_line_thread.start()
    server = ThreadingHTTPServer((config.HOST, config.PORT), CentralRequestHandler)
    print(f"Central server: http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCentral server stopped")
    finally:
        stop_event.set()
        front_line_thread.join(timeout=3)
        server.server_close()


def _maintain_front_line_world(database, stop_event):
    while not stop_event.is_set():
        try:
            result = map_worlds.ensure_front_line_world(database)
            if result["started"]:
                print(f"[front_line] Автоматический сервер запущен: {result['server_url']}")
        except Exception:
            traceback.print_exc()
        stop_event.wait(5)


if __name__ == "__main__":
    run()
