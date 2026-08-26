import copy
import time

from server.world import get_bot_opponents


PRESENCE_TTL = 15
PRESENCE = {}


def cleanup():
    cutoff = time.time() - PRESENCE_TTL
    for token in list(PRESENCE):
        if PRESENCE[token]["seen_at"] < cutoff:
            del PRESENCE[token]


def update_presence(token, user_id, character, location):
    cleanup()
    PRESENCE[token] = {
        "token": token,
        "user_id": user_id,
        "character_id": character["id"],
        "name": character["name"],
        "level": character["level"],
        "xp": character["xp"],
        "hp": character["hp"],
        "max_hp": character["max_hp"],
        "mp": character["mp"],
        "max_mp": character["max_mp"],
        "stats": copy.deepcopy(character["stats"]),
        "stat_points": character["stat_points"],
        "location": location,
        "seen_at": time.time(),
    }


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