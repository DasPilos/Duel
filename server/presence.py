import copy
import time

from server.world import get_bot_opponents


PRESENCE_TTL = 15
PRESENCE = {}


def cleanup():
    cutoff = time.time() - PRESENCE_TTL
    for token in list(PRESENCE):
        if not PRESENCE[token].get("afk", False) and PRESENCE[token]["seen_at"] < cutoff:
            del PRESENCE[token]


def online_player_count():
    """Count distinct connected human accounts; AFK entries and bots are excluded."""
    cleanup()
    return len({
        item["user_id"]
        for item in PRESENCE.values()
        if not item.get("afk", False)
    })


def update_presence(token, user_id, character, location):
    cleanup()
    character_id = character["id"]
    already_present = any(
        item["character_id"] == character_id and item["token"] == token and not item.get("afk", False)
        for item in PRESENCE.values()
    )
    for previous_token in list(PRESENCE):
        if PRESENCE[previous_token]["character_id"] == character_id:
            del PRESENCE[previous_token]
    PRESENCE[token] = {
        "token": token,
        "user_id": user_id,
        "character_id": character["id"],
        "name": character["name"],
        "type": character.get("type", "warrior"),
        "level": character["level"],
        "xp": character["xp"],
        "hp": character["hp"],
        "max_hp": character["max_hp"],
        "mp": character["mp"],
        "max_mp": character["max_mp"],
        "stats": copy.deepcopy(character["stats"]),
        "stat_points": character["stat_points"],
        "location": location,
        "position_x": character.get("position_x"),
        "position_y": character.get("position_y"),
        "position_direction": character.get("position_direction"),
        "afk": False,
        "seen_at": time.time(),
    }
    return not already_present


def mark_afk(token, user_id, character):
    """Retain the last known location as an offline, attackable presence entry."""
    cleanup()
    character_id = int(character["id"])
    entry = PRESENCE.get(token, {})
    entry.update({
        "token": token,
        "user_id": user_id,
        "character_id": character_id,
        "name": character["name"],
        "type": character.get("type", "warrior"),
        "level": character["level"],
        "xp": character["xp"],
        "hp": character["hp"],
        "max_hp": character["max_hp"],
        "mp": character["mp"],
        "max_mp": character["max_mp"],
        "stats": copy.deepcopy(character["stats"]),
        "stat_points": character["stat_points"],
        "location": character.get("zone", entry.get("location", "tavern")),
        "position_x": character.get("position_x"),
        "position_y": character.get("position_y"),
        "position_direction": character.get("position_direction"),
        "afk": True,
        "seen_at": time.time(),
    })
    PRESENCE[token] = entry


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


def get_character_presence(character_id):
    cleanup()
    return next((dict(item) for item in PRESENCE.values()
                 if int(item["character_id"]) == int(character_id)), None)


def update_afk_character(character):
    cleanup()
    for item in PRESENCE.values():
        if int(item["character_id"]) != int(character["id"]) or not item.get("afk"):
            continue
        for field in ("name", "type", "level", "xp", "hp", "max_hp", "mp", "max_mp",
                      "stats", "stat_points", "zone", "position_x", "position_y", "position_direction"):
            if field in character:
                item[field] = copy.deepcopy(character[field])
        item["location"] = character.get("zone", item["location"])
        item["seen_at"] = time.time()
        return dict(item)
    return None