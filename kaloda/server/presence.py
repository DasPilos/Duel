import copy
import threading
import time

from kaloda.server.bots import get_bot_opponents


PRESENCE_TTL = 15
PRESENCE = {}
# Токены и id аккаунтов не покидают сервер: клиентам отдаётся только профиль персонажа.
PRIVATE_FIELDS = frozenset({"token", "user_id"})
PROFILE_FIELDS = (
    "name", "type", "level", "xp", "hp", "max_hp", "mp", "max_mp", "stats", "talents",
    "unique_resource_max", "stat_points", "zone", "position_x", "position_y", "position_direction",
    "deck",
)
# HTTP-потоки читают и меняют присутствие одновременно, поэтому все обращения идут под одним замком.
_LOCK = threading.RLock()


def cleanup():
    cutoff = time.time() - PRESENCE_TTL
    with _LOCK:
        for token in list(PRESENCE):
            if not PRESENCE[token].get("afk") and PRESENCE[token]["seen_at"] < cutoff:
                del PRESENCE[token]


def _profile_fields(character):
    payload = {field: copy.deepcopy(character[field]) for field in PROFILE_FIELDS if field in character}
    payload["character_id"] = character["id"]
    return payload


def update_presence(token, user_id, character, location):
    """Отмечает персонажа в локации. True, если он только что появился в игре (раньше его не было в сети)."""
    with _LOCK:
        cleanup()
        character_id = character["id"]
        already_online = any(
            entry.get("character_id") == character_id and not entry.get("afk")
            for entry in PRESENCE.values()
        )
        # Один персонаж — одна запись: афк-копия и запись от прежнего токена заменяются новой
        for existing_token, entry in list(PRESENCE.items()):
            if existing_token != token and entry.get("character_id") == character_id:
                del PRESENCE[existing_token]
        PRESENCE[token] = {
            "token": token,
            "user_id": user_id,
            "kind": "player",
            **_profile_fields(character),
            "location": location,
            "afk": False,
            "seen_at": time.time(),
        }
        return not already_online


def mark_afk(token, user_id, character):
    """Оставляет вышедшего игрока в его локации афк-персонажем: его можно вызвать на бой."""
    with _LOCK:
        location = PRESENCE.get(token, {}).get("location", character.get("zone", "world_map"))
        update_presence(token, user_id, character, location)
        PRESENCE[token]["afk"] = True


def get_character_presence(character_id):
    with _LOCK:
        cleanup()
        return next(
            (copy.deepcopy(entry) for entry in PRESENCE.values() if int(entry["character_id"]) == int(character_id)),
            None,
        )


def occupants(user_id, location):
    """Игроки локации (в том числе афк) и, для заднего двора и таверны, боты, которые сейчас в ней."""
    bots = get_bot_opponents() if location in {"backyard", "tavern"} else []
    with _LOCK:
        cleanup()
        result = [
            {key: copy.deepcopy(value) for key, value in item.items() if key not in PRIVATE_FIELDS}
            for item in PRESENCE.values()
            if item["location"] == location
        ]
    result.extend(
        {
            **bot,
            "character_id": bot["id"],
            "kind": "bot",
            "location": location,
        }
        for bot in bots
        if bot.get("zone") == location
    )
    return result


def remove_character_presence(character_id):
    character_id = int(character_id)
    with _LOCK:
        removed = False
        for token in list(PRESENCE):
            if int(PRESENCE[token]["character_id"]) == character_id:
                del PRESENCE[token]
                removed = True
        return removed


def update_afk_character(character_id, character=None):
    """Обновляет афк-копию персонажа после боя с ним. Можно вызвать как (character) или (character_id, character)."""
    if character is None:
        character = character_id
        character_id = character.get("id", character.get("character_id"))
    if character_id is None:
        return None
    with _LOCK:
        cleanup()
        for item in PRESENCE.values():
            if int(item["character_id"]) != int(character_id) or not item.get("afk"):
                continue
            for field in PROFILE_FIELDS:
                if field in character:
                    item[field] = copy.deepcopy(character[field])
            item["location"] = character.get("zone", item["location"])
            item["seen_at"] = time.time()
            return copy.deepcopy(item)
        return None
