import json
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote


class ServerError(RuntimeError):
    pass


class GameClient:
    def __init__(self, base_url="http://127.0.0.1:8765", timeout=3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = None

    def _request(self, method, path, payload=None, authenticated=False):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            if not self.token:
                raise ServerError("Клиент не авторизован")
            headers["Authorization"] = f"Bearer {self.token}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RemoteDisconnected, ConnectionResetError, OSError) as error:
            if isinstance(error, HTTPError):
                try:
                    details = json.loads(error.read().decode("utf-8"))
                    message = details.get("error", str(error))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message = str(error)
            else:
                message = str(error)
            raise ServerError(message) from error

    def health(self):
        return self._request("GET", "/health")

    def register(self, username, password):
        return self._request("POST", "/api/register", {"username": username, "password": password})

    def login(self, username, password):
        result = self._request("POST", "/api/login", {"username": username, "password": password})
        self.token = result["token"]
        return result["user"]

    def create_character(self, name, profession_type="warrior"):
        return self._request("POST", "/api/characters", {"name": name, "profession_type": profession_type}, authenticated=True)["character"]

    def list_characters(self):
        return self._request("GET", "/api/characters", authenticated=True)["characters"]

    def list_opponents(self):
        return self._request("GET", "/api/opponents", authenticated=True)["opponents"]

    def save_opponent(self, opponent):
        return self._request(
            "PUT",
            f"/api/opponents/{opponent['id']}",
            opponent,
            authenticated=True,
        )["opponent"]

    def update_presence(self, character_id, location):
        return self._request("POST", "/api/social/presence", {"character_id": character_id, "location": location}, authenticated=True)

    def list_occupants(self, location):
        return self._request("GET", f"/api/social/occupants?location={quote(location)}", authenticated=True)["occupants"]

    def list_messages(self, location, character_id, before_id=None, limit=50):
        path = f"/api/chat/history?location={quote(location)}&character_id={character_id}&limit={limit}"
        if before_id is not None:
            path += f"&before_id={before_id}"
        return self._request("GET", path, authenticated=True)["messages"]

    def social_snapshot(self, location, character_id):
        path = f"/api/social/snapshot?location={quote(location)}&character_id={character_id}"
        return self._request("GET", path, authenticated=True)

    def send_message(self, character_id, location, text, recipient_id=None):
        return self._request("POST", "/api/chat/messages", {"character_id": character_id, "location": location, "text": text, "recipient_id": recipient_id}, authenticated=True)

    def mark_chat_read(self, character_id, location, message_id):
        return self._request("POST", "/api/chat/read", {"character_id": character_id, "location": location, "message_id": message_id}, authenticated=True)

    def unread_count(self, character_id, location):
        return self._request("GET", f"/api/chat/unread?location={quote(location)}&character_id={character_id}", authenticated=True)["unread"]

    def report_message(self, character_id, message_id, reason):
        return self._request("POST", "/api/chat/report", {"character_id": character_id, "message_id": message_id, "reason": reason}, authenticated=True)

    def delete_message(self, message_id):
        return self._request("POST", "/api/chat/delete", {"message_id": message_id}, authenticated=True)

    def mute_character(self, character_id, muted_character_id, seconds=600):
        return self._request("POST", "/api/chat/mute", {"character_id": character_id, "muted_character_id": muted_character_id, "seconds": seconds}, authenticated=True)

    def offer_duel(self, character_id, location, target_id):
        return self._request("POST", "/api/social/duel-offers", {"character_id": character_id, "location": location, "target_id": target_id}, authenticated=True)

    def create_duel_application(self, character_id, location, ttl=120):
        return self._request("POST", "/api/social/duel-applications", {"character_id": character_id, "location": location, "ttl": ttl}, authenticated=True)

    def cancel_duel_application(self, character_id, location):
        return self._request("POST", "/api/social/duel-applications/cancel", {"character_id": character_id, "location": location}, authenticated=True)

    def duel_board(self, location="tavern"):
        return self._request("GET", f"/api/social/offers?location={quote(location)}", authenticated=True)

    def list_duel_offers(self, location="tavern"):
        return self.duel_board(location)["offers"]

    def respond_duel_offer(self, character_id, offer_id, accepted):
        return self._request("POST", "/api/social/duel-offers/respond", {"character_id": character_id, "offer_id": offer_id, "accepted": accepted}, authenticated=True)

    def load_character(self, character_id=None):
        path = "/api/characters/me" if character_id is None else f"/api/characters/{character_id}"
        return self._request("GET", path, authenticated=True)["character"]

    def save_character(self, character):
        return self._request("PUT", f"/api/characters/{character['id']}", character, authenticated=True)["character"]

    def audit_match(self, audit):
        return self._request("POST", "/api/matches/audit", audit, authenticated=True)

    def list_group_battles(self):
        return self._request("GET", "/api/social/group-battles", authenticated=True)["offers"]

    def create_group_battle(self, character_id, location="backyard", ttl=120, max_participants=10):
        return self._request("POST", "/api/social/group-battles", {"character_id": character_id, "location": location, "ttl": ttl, "max_participants": max_participants}, authenticated=True)

    def join_group_battle(self, offer_id, character_id, location="backyard"):
        return self._request(
            "POST",
            f"/api/social/group-battles/{offer_id}/join",
            {"character_id": character_id, "location": location},
            authenticated=True,
        )

    def leave_group_battle(self, offer_id, character_id):
        return self._request("POST", f"/api/social/group-battles/{offer_id}/leave", {"character_id": character_id}, authenticated=True)

    def disconnect(self, character=None):
        payload = None
        if character is not None:
            payload = {"character_id": character["id"], "character": character}
        result = self._request("POST", "/api/sessions/disconnect", payload, authenticated=True)
        self.token = None
        return result

    def check_active_battle(self, player_id, opponent_id):
        """Проверяет наличие активного боя"""
        return self._request(
            "GET",
            f"/api/duel/active-battles/{player_id}/{opponent_id}",
            authenticated=True
        )

    def restore_battle_state(self, player_id, opponent_id):
        """Восстанавливает состояние боя при переподключении"""
        return self._request(
            "GET",
            f"/api/duel/restore/{player_id}/{opponent_id}",
            authenticated=True
        )

    # ================== ИНВЕНТАРЬ И ЭКИПИРОВКА ==================
    
    def get_inventory(self, character_id):
        """Получить инвентарь персонажа"""
        return self._request("GET", f"/api/inventory/{character_id}", authenticated=True)["inventory"]
    
    def get_equipment(self, character_id):
        """Получить экипировку персонажа"""
        return self._request("GET", f"/api/equipment/{character_id}", authenticated=True)["equipment"]
    
    def get_storage(self, character_id, storage_type="chest1"):
        """Получить хранилище персонажа"""
        return self._request("GET", f"/api/storage/{character_id}/{storage_type}", authenticated=True)["storage"]
    
    def get_decks(self, character_id):
        """Получить боевые колоды персонажа"""
        return self._request("GET", f"/api/decks/{character_id}", authenticated=True)["decks"]
    
    def use_item(self, character_id, item_id):
        """Использовать предмет"""
        return self._request("POST", "/api/inventory/use", {"character_id": character_id, "item_id": item_id}, authenticated=True)
    
    def drop_item(self, character_id, item_id):
        """Выбросить предмет"""
        return self._request("POST", "/api/inventory/drop", {"character_id": character_id, "item_id": item_id}, authenticated=True)
    
    def equip_item(self, character_id, item_id, slot):
        """Надеть предмет экипировки"""
        return self._request("POST", "/api/equipment/equip", {"character_id": character_id, "item_id": item_id, "slot": slot}, authenticated=True)
    
    def unequip_item(self, character_id, slot):
        """Снять предмет экипировки"""
        return self._request("POST", "/api/equipment/unequip", {"character_id": character_id, "slot": slot}, authenticated=True)

