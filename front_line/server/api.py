"""HTTP routes specific to Front Line."""

from server.world_map import terrain_payload
from front_line.server.world_api import WorldRequestHandler


class FrontLineRequestHandler(WorldRequestHandler):
    API_ROUTES = {
        **WorldRequestHandler.API_ROUTES,
        "POST": WorldRequestHandler.API_ROUTES["POST"] + (
            "/api/front-line/character-draft",
            "/api/world/item-drop/loot",
        ),
    }

    def _dispatch_mode_api(self, method, path, body=None):
        if method == "GET" and path == "/api/map/terrain":
            self.database.user_id_by_token(self._token())
            self.world.prepare_lobby_terrain()
            terrain = terrain_payload()
            terrain["front_line_map"] = self.world.map_visual_payload()
            self._send(200, {"terrain": terrain})
            return True
        if method == "POST" and path == "/api/front-line/character-draft":
            body = body or {}
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            draft = self.world.submit_character_draft(
                user_id,
                character_id,
                str(body.get("profession_type", "")),
                body.get("stats", {}),
            )
            self._send(200, {"draft": draft})
            return True
        if method == "POST" and path == "/api/world/item-drop/loot":
            body = body or {}
            user_id = self.database.user_id_by_token(self._token())
            character_id = int(body.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
            result = self.world.loot_item_drop(
                user_id,
                character_id,
                str(body.get("drop_id", "")),
            )
            self._send(200, result)
            return True
        return super()._dispatch_mode_api(method, path, body)
