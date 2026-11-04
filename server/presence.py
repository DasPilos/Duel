import copy
import time

from server.world import get_bot_opponents


PRESENCE_TTL = 15
PRESENCE = {}


def cleanup():
    cutoff = time.time() - PRESENCE_TTL
    for token in list(PRESENCE):
        if not PRESENCE[token].get("afk") and PRESENCE[token]["seen_at"] < cutoff:
            del PRESENCE[token]


def _profile_fields(character):
    fields = (
        "character_id", "name", "type", "level", "xp", "hp", "max_hp", "mp",
        "max_mp", "stats", "stat_points", "zone", "position_x", "position_y",
        "position_direction",
    )
    payload = {field: copy.deepcopy(character.get(field)) for field in fields if field in character}
    if "character_id" not in payload and "id" in character:
        payload["character_id"] = character["id"]
    return payload


def update_presence(token, user_id, character, location):
    cleanup()
    character_id = character["id"]
    for existing_token, entry in list(PRESENCE.items()):
        if existing_token != token and entry.get("character_id") == character_id and entry.get("afk"):
            del PRESENCE[existing_token]
    PRESENCE[token] = {
        "token": token,
        "user_id": user_id,
        **_profile_fields(character),
        "location": location,
        "afk": False,
        "seen_at": time.time(),
    }


def mark_afk(token, user_id, character):
    location = PRESENCE.get(token, {}).get("location", character.get("zone", "tavern"))
    update_presence(token, user_id, character, location)
    PRESENCE[token]["afk"] = True


def get_character_presence(character_id):
    cleanup()
    return next(
        (copy.deepcopy(entry) for entry in PRESENCE.values() if entry.get("character_id") == character_id),
        None,
    )


def character_level(character_id, location):
    """Возвращает уровень персонажа, если он сейчас присутствует в локации."""
    cleanup()
    for item in PRESENCE.values():
        if item["character_id"] == character_id and item["location"] == location:
            return item["level"]
    return None


def occupants(user_id, location):
    cleanup()
    result = [
        {key: value for key, value in item.items() if key != "token"}
        for item in PRESENCE.values()
        if item["location"] == location
    ]
    if location in {"backyard", "tavern"}:
        result.extend(
            {
                **bot,
                "character_id": bot["id"],
                "kind": "bot",
                "location": location,
            }
            for bot in get_bot_opponents()
            if bot.get("zone") == location
        )
    return result


def remove_character_presence(character_id):
    character_id = int(character_id)
    removed = False
    for token in list(PRESENCE):
        if int(PRESENCE[token]["character_id"]) == character_id:
            del PRESENCE[token]
            removed = True
    return removed


def update_afk_character(character_id, character=None):
    if character is None:
        character = character_id
        character_id = character.get("id", character.get("character_id"))
    if character_id is None:
        return None
    cleanup()
    for item in PRESENCE.values():
        if int(item["character_id"]) != int(character_id) or not item.get("afk"):
            continue
        for field in ("name", "type", "level", "xp", "hp", "max_hp", "mp", "max_mp",
                      "stats", "stat_points", "zone", "position_x", "position_y", "position_direction"):
            if field in character:
                item[field] = copy.deepcopy(character[field])
        item["location"] = character.get("zone", item["location"])
        item["seen_at"] = time.time()
        return copy.deepcopy(item)
    return None
