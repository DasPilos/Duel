"""HTTP surface shared by Front Line world servers: sync, command, stream, leave, corpse and rest routes."""

from server import websocket
from server.world_map import terrain_payload
from server.world_stream import WorldStream
from server.mode_api import COMMON_API_ROUTES, ModeRequestHandler


class WorldRequestHandler(ModeRequestHandler):
    API_ROUTES = {
        **COMMON_API_ROUTES,
        "GET": COMMON_API_ROUTES["GET"] + (
            "/api/world/stream",
            "/api/items/catalog",
            "/api/items/equipment",
            "/api/items/materials",
        ),
        "POST": COMMON_API_ROUTES["POST"] + (
            "/api/world/sync",
            "/api/world/command",
            "/api/world/leave",
            "/api/world/corpse/loot",
            "/api/server/restart-notice",
            "/api/server/client-reload",
            "/api/characters/*/rest",
        ),
        "PUT": COMMON_API_ROUTES["PUT"],
    }

    def _serve_world_stream(self):
        """Рукопожатие WebSocket (RFC 6455); дальше соединение ведёт WorldStream, HTTP-запросы на нём не идут."""
        key = self.headers.get("Sec-WebSocket-Key", "")
        if self.headers.get("Upgrade", "").lower() != "websocket" or not key:
            raise ValueError("Ожидается WebSocket-соединение")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", websocket.accept_key(key))
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        WorldStream(self, self.world, self.database).run()

    def _dispatch_mode_api(self, method, path, body=None):
        if method == "GET" and path == "/api/world/stream":
            self._serve_world_stream()
            return True
        if method == "GET" and path == "/api/map/terrain":
            self.database.user_id_by_token(self._token())
            self._send(200, {"terrain": terrain_payload()})
            return True
        if method != "POST":
            return False
        body = body or {}
        if path == "/api/world/sync":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, self.world.sync(user_id, character_id, body))
            return True
        if path == "/api/world/command":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, self.world.command(user_id, character_id, body))
            return True
        if path == "/api/world/leave":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self.world.leave(user_id, character_id)
            self._send(200, {"ok": True})
            return True
        if path == "/api/world/corpse/loot":
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, self.world.loot_corpse(user_id, character_id, int(body.get("corpse_id", 0))))
            return True
        if path.startswith("/api/characters/") and path.endswith("/rest"):
            character_id = int(path.split("/")[3])
            user_id = self.database.user_id_by_token(self._token())
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            self._send(200, {"vitals": self.world.rest(user_id, character_id)})
            return True
        return False
