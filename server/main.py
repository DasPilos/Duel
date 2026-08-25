import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import time

from server import config
from server.database import Database
from server import social


class GameRequestHandler(BaseHTTPRequestHandler):
    database = Database()
    chat_send_times = {}

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
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _token(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise ValueError("Требуется авторизация")
        return value[7:].strip()

    def _handle_error(self, error):
        status = 401 if "авторизац" in str(error) or "сессия" in str(error) else 400
        self._send(status, {"error": str(error)})

    def _query(self):
        return parse_qs(urlparse(self.path).query)

    def _chat_actor(self, token, character_id):
        user_id = self.database.user_id_by_token(token)
        character = self.database.get_character(user_id, int(character_id))
        if character is None:
            raise ValueError("Персонаж не найден")
        return user_id, character

    def _check_chat_rate(self, character_id):
        now = time.time()
        timestamps = self.chat_send_times.setdefault(character_id, [])
        timestamps[:] = [stamp for stamp in timestamps if stamp > now - config.CHAT_RATE_LIMIT_WINDOW]
        if len(timestamps) >= config.CHAT_RATE_LIMIT_COUNT:
            raise ValueError("Слишком много сообщений. Подождите немного")
        timestamps.append(now)

    def do_GET(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            if path == "/health":
                self._send(200, {"status": "ok"})
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
            if path == "/api/opponents":
                user_id = self.database.user_id_by_token(self._token())
                self._send(200, {"opponents": self.database.get_opponents(user_id)})
                return
            if path == "/api/social/occupants":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                location = self.path.split("location=", 1)[1] if "location=" in self.path else "tavern"
                self._send(200, {"occupants": social.occupants(user_id, location)})
                return
            if path == "/api/social/messages":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                query = self._query()
                location = query.get("location", ["tavern"])[0]
                character_id = int(query.get("character_id", [self.database.get_character(user_id)["id"]])[0])
                self._chat_actor(token, character_id)
                before_id = query.get("before_id", [None])[0]
                limit = query.get("limit", [50])[0]
                self._send(200, {"messages": self.database.get_chat_history(character_id, location, before_id, limit)})
                return
            if path == "/api/chat/history":
                query = self._query()
                token = self._token()
                character_id = int(query.get("character_id", [0])[0])
                self._chat_actor(token, character_id)
                self._send(200, {"messages": self.database.get_chat_history(character_id, query.get("location", ["tavern"])[0], query.get("before_id", [None])[0], query.get("limit", [50])[0])})
                return
            if path == "/api/chat/unread":
                query = self._query()
                token = self._token()
                character_id = int(query.get("character_id", [0])[0])
                self._chat_actor(token, character_id)
                location = query.get("location", ["tavern"])[0]
                self._send(200, {"unread": self.database.chat_unread_count(character_id, location)})
                return
            if path == "/api/social/offers":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id)
                location = self.path.split("location=", 1)[1] if "location=" in self.path else "tavern"
                offers = social.offers_for(character["id"])
                if location == "backyard":
                    offers += social.public_offers(location, character["id"])
                self._send(200, {
                    "offers": offers,
                    "my_application": social.pending_public_offer(character["id"], location),
                })
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
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError) as error:
            self._handle_error(error)

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
                self._send(200, self.database.login(str(body.get("username", "")), str(body.get("password", ""))))
                return
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                name = str(body.get("name", "")).strip()
                self.database.validate_character_name(name)
                self._send(201, {"character": self.database.create_character(user_id, name)})
                return
            if path == "/api/sessions/disconnect":
                character_id = body.get("character_id")
                self._send(200, self.database.disconnect(self._token(), int(character_id) if character_id is not None else None, body.get("character")))
                return
            if path == "/api/social/presence":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None:
                    raise ValueError("Персонаж не найден")
                social.update_presence(token, user_id, character, str(body.get("location", "tavern")))
                self._send(200, {"ok": True})
                return
            if path == "/api/social/messages":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                text = str(body.get("text", "")).strip()
                self._check_chat_rate(character["id"])
                if self.database.is_muted(character["id"], body.get("location", "tavern")):
                    raise ValueError("Вы временно не можете отправлять сообщения")
                if character is None or not 1 <= len(text) <= config.CHAT_MAX_LENGTH:
                    raise ValueError("Некорректное сообщение")
                location = str(body.get("location", "tavern"))
                recipient_id = body.get("recipient_id")
                if recipient_id is not None and str(recipient_id) == str(character["id"]):
                    raise ValueError("Нельзя отправить сообщение самому себе")
                message = self.database.add_chat_message(character["id"], location, text, recipient_id)
                self._send(201, {"message": message})
                return
            if path == "/api/chat/messages":
                token = self._token()
                character_id = int(body.get("character_id", 0))
                _, character = self._chat_actor(token, character_id)
                text = str(body.get("text", "")).strip()
                if not text or len(text) > config.CHAT_MAX_LENGTH:
                    raise ValueError("Сообщение должно содержать от 1 до 300 символов")
                self._check_chat_rate(character["id"])
                if self.database.is_muted(character["id"], body.get("location", "tavern")):
                    raise ValueError("Вы временно не можете отправлять сообщения")
                self._send(201, {"message": self.database.add_chat_message(character["id"], str(body.get("location", "tavern")), text, body.get("recipient_id"))})
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
                offer = social.add_duel_offer(
                    {"character_id": character["id"], "name": character["name"]},
                    target_id,
                    location,
                )
                self._send(201, {"accepted": False, "offer": offer})
                return
            if path == "/api/social/duel-applications":
                token = self._token()
                user_id = self.database.user_id_by_token(token)
                character = self.database.get_character(user_id, int(body["character_id"]))
                if character is None or body.get("location") != "backyard":
                    raise ValueError("Заявка недоступна")
                if character["hp"] < character["max_hp"]:
                    raise ValueError("Нельзя подать заявку: здоровье должно быть полностью восстановлено")
                offer = social.add_public_duel_offer(
                    {
                        "character_id": character["id"],
                        "name": character["name"],
                    },
                    "backyard",
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
                offer = social.respond_duel_offer(character["id"], body["offer_id"], bool(body.get("accepted")))
                self._send(200, {"offer": offer})
                return
            self._send(404, {"error": "Маршрут не найден"})
        except (ValueError, json.JSONDecodeError, KeyError) as error:
            self._handle_error(error)

    def do_PUT(self):
        try:
            path = urlparse(self.path).path.rstrip("/")
            if path.startswith("/api/opponents/"):
                opponent_id = path.rsplit("/", 1)[1]
                user_id = self.database.user_id_by_token(self._token())
                opponent = self.database.update_bot(user_id, opponent_id, self._body())
                self._send(200, {"opponent": opponent})
                return
            if not path.startswith("/api/characters/"):
                self._send(404, {"error": "Маршрут не найден"})
                return
            character_id = int(path.rsplit("/", 1)[1])
            user_id = self.database.user_id_by_token(self._token())
            character = self.database.save_character(user_id, character_id, self._body())
            self._send(200, {"character": character})
        except (ValueError, json.JSONDecodeError, KeyError) as error:
            self._handle_error(error)

    def log_message(self, format_string, *args):
        print(f"[server] {self.address_string()} - {format_string % args}")


def run():
    server = ThreadingHTTPServer((config.HOST, config.PORT), GameRequestHandler)
    print(f"Game server: http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
