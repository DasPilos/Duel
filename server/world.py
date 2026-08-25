import copy
import time

BOT_FULL_REGEN_SECONDS = 300

BOT_OPPONENTS = (
    {
        "id": "bot_brawler",
        "name": "Забияка",
        "level": 1,
        "xp": 0,
        "hp": 212,
        "max_hp": 212,
        "mp": 50,
        "max_mp": 50,
        "stats": {
            "strength": 9,
            "agility": 4,
            "intuition": 5,
            "endurance": 8,
        },
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
    },
    {
        "id": "bot_wireless_soul",
        "name": "Безпроводной Душ",
        "level": 1,
        "xp": 0,
        "hp": 184,
        "max_hp": 184,
        "mp": 50,
        "max_mp": 50,
        "stats": {
            "strength": 6,
            "agility": 4,
            "intuition": 10,
            "endurance": 6,
        },
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
    },
    {
        "id": "bot_konfu_padla",
        "name": "Комфу Падла",
        "level": 1,
        "xp": 0,
        "hp": 184,
        "max_hp": 184,
        "mp": 50,
        "max_mp": 50,
        "stats": {
            "strength": 6,
            "agility": 10,
            "intuition": 4,
            "endurance": 6,
        },
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
    },
    {
        "id": "bot_plowman",
        "name": "Пахарь",
        "level": 1,
        "xp": 0,
        "hp": 184,
        "max_hp": 184,
        "mp": 50,
        "max_mp": 50,
        "stats": {
            "strength": 12,
            "agility": 4,
            "intuition": 4,
            "endurance": 6,
        },
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
    },
)

BOT_STATE = {opponent["id"]: copy.deepcopy(opponent) for opponent in BOT_OPPONENTS}
BOT_UPDATED_AT = {opponent_id: time.time() for opponent_id in BOT_STATE}


def get_bot_opponents():
    now = time.time()
    for opponent_id, opponent in BOT_STATE.items():
        elapsed = max(0, now - BOT_UPDATED_AT[opponent_id])
        regen_per_second = opponent["max_hp"] / BOT_FULL_REGEN_SECONDS
        opponent["hp"] = min(
            opponent["max_hp"],
            opponent["hp"] + int(elapsed * regen_per_second),
        )
        BOT_UPDATED_AT[opponent_id] = now
    return copy.deepcopy(list(BOT_STATE.values()))


def update_bot(opponent_id, hp):
    if opponent_id not in BOT_STATE:
        raise ValueError("Бот не найден")
    opponent = BOT_STATE[opponent_id]
    opponent["hp"] = max(0, min(opponent["max_hp"], int(hp)))
    BOT_UPDATED_AT[opponent_id] = time.time()
    return copy.deepcopy(opponent)
