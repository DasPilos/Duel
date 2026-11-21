"""Mode-scoped HTTP dispatch shared by the independent mode API modules."""

from fnmatch import fnmatchcase
from urllib.parse import urlparse

from server.main import GameRequestHandler

COMMON_API_ROUTES = {
    "GET": (
        "/health",
        "/api/version",
        "/api/server/status",
        "/download/client",
        "/api/characters",
        "/api/characters/me",
        "/api/characters/*",
        "/api/map/terrain",
        "/api/map/palette",
        "/api/map/saved",
        "/api/map/mob-settings",
        "/api/items/catalog",
        "/api/items/equipment",
        "/api/items/materials",
        "/api/social/occupants",
        "/api/social/messages",
        "/api/social/snapshot",
        "/api/chat/history",
        "/api/chat/unread",
        "/api/inventory/*",
        "/api/equipment/*",
        "/api/storage/*",
    ),
    "POST": (
        "/api/sessions/disconnect",
        "/api/characters",
        "/api/characters/*/delete",
        "/api/map/palette/preview",
        "/api/map/palette/apply",
        "/api/map/mob-settings",
        "/api/items/catalog",
        "/api/social/presence",
        "/api/social/messages",
        "/api/chat/messages",
        "/api/chat/read",
        "/api/chat/report",
        "/api/chat/delete",
        "/api/chat/mute",
        "/api/inventory/move",
        "/api/inventory/use",
        "/api/inventory/drop",
        "/api/inventory/remove",
        "/api/storage/transfer",
        "/api/equipment/equip",
        "/api/equipment/unequip",
    ),
    "PUT": ("/api/characters/*", "/api/items/catalog/*"),
    "DELETE": (),
}


class ModeRequestHandler(GameRequestHandler):
    API_ROUTES = COMMON_API_ROUTES

    def _dispatch_mode_api(self, method, path, body=None):
        return False

    def _mode_route_allowed(self, method):
        path = urlparse(self.path).path.rstrip("/") or "/"
        return any(fnmatchcase(path, route) for route in self.API_ROUTES.get(method, ()))

    def _reject_mode_route(self):
        self._send(404, {"error": "Маршрут не найден в API этого режима"})

    def do_GET(self):
        if self._mode_route_allowed("GET"):
            return super().do_GET()
        self._reject_mode_route()

    def do_POST(self):
        if self._mode_route_allowed("POST"):
            return super().do_POST()
        self._reject_mode_route()

    def do_PUT(self):
        if self._mode_route_allowed("PUT"):
            return super().do_PUT()
        self._reject_mode_route()

    def do_DELETE(self):
        if self._mode_route_allowed("DELETE"):
            return super().do_DELETE()
        self._reject_mode_route()
