import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import time

from server import config
from server.database import Database
from server.items_database import ItemsDatabase
from server import social
from server.world import run_bot_battle_tick
from combat.anticheat import score_match


class GameRequestHandler(BaseHTTPRequestHandler):
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
        social.update_presence(token, user_id, character, location)
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
                   inventory = self.items_database.get_inventory(character_id)
                   self._send(200, {"inventory": inventory})
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
            if path == "/api/login":
                self._send(200, self.database.login(str(body.get("username", "")), str(body.get("password", ""))))
                return
            if path == "/api/characters":
                user_id = self.database.user_id_by_token(self._token())
                name = str(body.get("name", "")).strip()
                profession_type = str(body.get("profession_type", "warrior")).strip().lower()
                self.database.validate_character_name(name)
                if profession_type not in ["warrior", "mage"]:
                    raise ValueError("Профессия должна быть 'warrior' или 'mage'")
                self._send(201, {"character": self.database.create_character(user_id, name, profession_type)})
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
                offer = social.respond_duel_offer(character["id"], body["offer_id"], bool(body.get("accepted")))
                self._send(200, {"offer": offer})
                return
            
            # ============= API ИНВЕНТАРЯ =============
            if path == "/api/inventory":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               inventory = self.items_database.get_inventory(character_id)
               self._send(200, {"inventory": inventory})
               return
            
            if path == "/api/equipment":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               equipment = self.items_database.get_equipment(character_id)
               self._send(200, {"equipment": equipment})
               return
            
            if path == "/api/storage":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               storage_type = str(body.get("storage_type", "chest1"))
               storage = self.items_database.get_storage(character_id, storage_type)
               self._send(200, {"storage": storage})
               return
            
            if path == "/api/decks":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               decks = self.items_database.get_decks(character_id)
               self._send(200, {"decks": decks})
               return
            
            if path == "/api/inventory/use":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               item_id = int(body.get("item_id", 0))
               result = self.items_database.use_item(character_id, item_id)
               self._send(200, {"used": result})
               return
            
            if path == "/api/inventory/drop":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               item_id = int(body.get("item_id", 0))
               self.items_database.remove_from_inventory(character_id, item_id)
               self._send(200, {"dropped": True})
               return
            
            if path == "/api/equipment/equip":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               item_id = int(body.get("item_id", 0))
               slot = str(body.get("slot", "")).strip()
               self.items_database.equip_item(character_id, item_id, slot)
               self._send(200, {"equipped": True})
               return
            
            if path == "/api/equipment/unequip":
               token = self._token()
               user_id = self.database.user_id_by_token(token)
               character_id = int(body.get("character_id", 0))
               character = self.database.get_character(user_id, character_id)
               if character is None:
                   raise ValueError("Персонаж не найден")
               slot = str(body.get("slot", "")).strip()
               self.items_database.unequip_item(character_id, slot)
               self._send(200, {"unequipped": True})
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


def run():
    server = ThreadingHTTPServer((config.HOST, config.PORT), GameRequestHandler)
    stop_bot_battles = threading.Event()
    bot_battle_thread = threading.Thread(
        target=_run_bot_battles,
        args=(stop_bot_battles,),
        name="bot-battle-scheduler",
        daemon=True,
    )
    bot_battle_thread.start()
    print(f"Game server: http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped")
    finally:
        stop_bot_battles.set()
        bot_battle_thread.join(timeout=2)
        server.server_close()


def _run_bot_battles(stop_event):
    while not stop_event.is_set():
        try:
            run_bot_battle_tick()
        except Exception:
            traceback.print_exc()
        if stop_event.wait(1):
            break


if __name__ == "__main__":
    run()
