import copy
import json
import random
import threading
import time
from pathlib import Path

from combat.battle import Battle
from combat.battle_archive import record_battle
from combat.fighter import Fighter

# Вне таверны (задний двор) боты лечатся 10 минут до полного хп, в таверне — вдвое быстрее.
BOT_FULL_REGEN_SECONDS = 600
BOT_TAVERN_FULL_REGEN_SECONDS = 300
BOT_BATTLE_INTERVAL_SECONDS = 60
BOT_BATTLE_COOLDOWN_SECONDS = 600
BOT_APPLICATION_WAIT_SECONDS = 30
BOT_STAT_WEIGHTS = {
    "critical": ("intuition", "strength", "agility", "endurance"),
    "agile": ("agility", "intuition", "strength", "endurance"),
    "tank": ("endurance", "strength", "agility", "intuition"),
    "boss": ("strength", "endurance", "intuition", "agility"),
}


def _bot(identifier, name, stats, role):
    max_hp = 100 + stats["endurance"] * 14
    return {
        "id": identifier,
        "name": name,
        "level": 1,
        "xp": 0,
        "hp": max_hp,
        "max_hp": max_hp,
        "mp": 50,
        "max_mp": 50,
        "stats": stats,
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
        "role": role,
    }

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
    _bot("bot_void_lightning", "Молния Пустоты", {"strength": 6, "agility": 5, "intuition": 11, "endurance": 4}, "critical"),
    _bot("bot_fist_blade", "Клинок в Кулаке", {"strength": 8, "agility": 4, "intuition": 10, "endurance": 4}, "critical"),
    _bot("bot_wasteland_fury", "Ярость Пустошей", {"strength": 9, "agility": 4, "intuition": 8, "endurance": 5}, "critical"),
    _bot("bot_fist_destroyer", "Кулак-Разрушитель", {"strength": 10, "agility": 5, "intuition": 7, "endurance": 4}, "critical"),
    _bot("bot_pit_demon", "Демон Ямы", {"strength": 8, "agility": 4, "intuition": 9, "endurance": 5}, "critical"),
    _bot("bot_oathbreaker", "Разрушитель Клятв", {"strength": 7, "agility": 5, "intuition": 9, "endurance": 5}, "critical"),
    _bot("bot_bloody_arena_shadow", "Тень Кровавой Арены", {"strength": 4, "agility": 11, "intuition": 7, "endurance": 4}, "agile"),
    _bot("bot_wolf_grin", "Волчий Оскал", {"strength": 5, "agility": 10, "intuition": 7, "endurance": 4}, "agile"),
    _bot("bot_raven_broken_jaw", "Ворон Разбитая Челюсть", {"strength": 6, "agility": 9, "intuition": 6, "endurance": 5}, "agile"),
    _bot("bot_ash_fist", "Пепельный Кулак", {"strength": 7, "agility": 8, "intuition": 7, "endurance": 4}, "agile"),
    _bot("bot_bonebreaker", "Костолом", {"strength": 8, "agility": 8, "intuition": 5, "endurance": 5}, "agile"),
    _bot("bot_bear_grip", "Хват Медведя", {"strength": 7, "agility": 9, "intuition": 5, "endurance": 5}, "agile"),
    _bot("bot_ironhand_thunder", "Гром Железнорук", {"strength": 7, "agility": 4, "intuition": 4, "endurance": 11}, "tank"),
    _bot("bot_steel_fang", "Стальной Клык", {"strength": 8, "agility": 4, "intuition": 5, "endurance": 9}, "tank"),
    _bot("bot_living_mountain", "Живая Гора", {"strength": 6, "agility": 4, "intuition": 4, "endurance": 12}, "tank"),
    _bot("bot_northern_butcher", "Мясник Севера", {"strength": 9, "agility": 4, "intuition": 4, "endurance": 9}, "tank"),
    _bot("bot_skullcrusher", "Дробитель Черепов", {"strength": 9, "agility": 5, "intuition": 4, "endurance": 8}, "tank"),
    _bot("bot_giant_slayer", "Убийца Гигантов", {"strength": 8, "agility": 4, "intuition": 5, "endurance": 9}, "tank"),
    _bot("bot_bloody_sand_king", "Король Кровавого Песка", {"strength": 7, "agility": 6, "intuition": 6, "endurance": 7}, "boss"),
)

BOT_STATE_PATH = Path(__file__).resolve().parent.parent / "bot_state.json"
BOT_STATE = {opponent["id"]: copy.deepcopy(opponent) for opponent in BOT_OPPONENTS}
BOT_UPDATED_AT = {opponent_id: time.time() for opponent_id in BOT_STATE}
BOT_LAST_BATTLE_AT = {opponent_id: 0.0 for opponent_id in BOT_STATE}
BOT_LAST_ATTACK_AT = {opponent_id: 0.0 for opponent_id in BOT_STATE}
BOT_SCHEDULER_STARTED_AT = 0.0
BOT_LAST_SIMULATED_BATTLE_AT = 0.0
BOT_STATE_LOCK = threading.RLock()


def _load_bot_state():
    if not BOT_STATE_PATH.exists():
        return
    try:
        payload = json.loads(BOT_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for opponent_id, opponent in payload.items():
        if opponent_id not in BOT_STATE or not isinstance(opponent, dict) or "id" not in opponent:
            continue
        BOT_STATE[opponent_id] = copy.deepcopy(opponent)
        BOT_UPDATED_AT[opponent_id] = float(opponent.get("updated_at", time.time()))
        BOT_LAST_BATTLE_AT[opponent_id] = float(opponent.get("last_battle_at", 0.0))
        BOT_LAST_ATTACK_AT[opponent_id] = float(opponent.get("last_attack_at", 0.0))


def _save_bot_state():
    payload = {}
    for opponent_id, opponent in BOT_STATE.items():
        snapshot = copy.deepcopy(opponent)
        snapshot["updated_at"] = BOT_UPDATED_AT.get(opponent_id, time.time())
        snapshot["last_battle_at"] = BOT_LAST_BATTLE_AT.get(opponent_id, 0.0)
        snapshot["last_attack_at"] = BOT_LAST_ATTACK_AT.get(opponent_id, 0.0)
        payload[opponent_id] = snapshot
    BOT_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_load_bot_state()
_save_bot_state()


def get_bot_opponents():
    with BOT_STATE_LOCK:
        _regenerate_bots(time.time())
        return copy.deepcopy(list(BOT_STATE.values()))


def update_bot(opponent_id, profile):
    with BOT_STATE_LOCK:
        if opponent_id not in BOT_STATE:
            raise ValueError("Бот не найден")
        opponent = BOT_STATE[opponent_id]
        if not isinstance(profile, dict):
            profile = {"hp": profile}
        for key in ("level", "xp", "hp", "mp", "max_mp", "stats", "stat_points"):
            if key in profile:
                opponent[key] = copy.deepcopy(profile[key])
        _allocate_bot_stat_points(opponent)
        opponent["max_hp"] = 100 + 20 * (opponent["level"] - 1) + opponent["stats"]["endurance"] * 14
        opponent["hp"] = max(0, min(opponent["max_hp"], int(opponent["hp"])))
        opponent["mp"] = max(0, min(opponent["max_mp"], int(opponent["mp"])))
        BOT_UPDATED_AT[opponent_id] = time.time()
    _save_bot_state()


def run_bot_battle_tick(now=None):
    """Drive bot applications on the board and resolve accepted bot battles."""
    global BOT_SCHEDULER_STARTED_AT, BOT_LAST_SIMULATED_BATTLE_AT
    now = time.time() if now is None else float(now)
    with BOT_STATE_LOCK:
        if BOT_SCHEDULER_STARTED_AT == 0.0:
            BOT_SCHEDULER_STARTED_AT = now
            return None
        _regenerate_bots(now)
        from server import social

        pending = social.pending_bot_public_offers("backyard")
        stale = next(
            (
                offer for offer in pending
                if now - float(offer["created_at"]) >= BOT_APPLICATION_WAIT_SECONDS
                and _can_accept_application(offer["sender_id"], now)
            ),
            None,
        )
        if stale is not None and now - BOT_LAST_SIMULATED_BATTLE_AT >= BOT_BATTLE_INTERVAL_SECONDS:
            social.close_public_offer(stale["id"], "cancelled", now)
            target_offer = next(
                (offer for offer in pending if offer["id"] != stale["id"]),
                None,
            )
            if target_offer is None:
                target = _pick_attacker(now, exclude_ids={stale["sender_id"]})
                if target is None:
                    return None
                target_offer = _post_bot_application(target, now)
            social.accept_public_offer(target_offer["id"], stale["sender_id"], now)
            result = _resolve_bot_battle(target_offer["sender_id"], stale["sender_id"], now)
            BOT_LAST_SIMULATED_BATTLE_AT = now
            _post_next_bot_application(now, {target_offer["sender_id"], stale["sender_id"]})
            return result

        if not pending and now - BOT_SCHEDULER_STARTED_AT >= BOT_BATTLE_INTERVAL_SECONDS:
            attacker = _pick_attacker(now)
            if attacker is not None:
                offer = _post_bot_application(attacker, now)
                return {"status": "posted", "offer_id": offer["id"], "attacker_id": attacker["id"]}
        return None


def _can_accept_application(opponent_id, now):
    opponent = BOT_STATE.get(opponent_id)
    return opponent is not None and opponent["zone"] == "backyard" and opponent["hp"] == opponent["max_hp"] and (
        now - BOT_LAST_BATTLE_AT[opponent_id] >= BOT_BATTLE_COOLDOWN_SECONDS
    )


def _pick_attacker(now, exclude_ids=frozenset()):
    eligible = [
        opponent for opponent in BOT_STATE.values()
        if opponent["id"] not in exclude_ids
        and opponent["zone"] == "backyard"
        and opponent["hp"] == opponent["max_hp"]
        and now - BOT_LAST_ATTACK_AT[opponent["id"]] >= BOT_BATTLE_COOLDOWN_SECONDS
        and now - BOT_LAST_BATTLE_AT[opponent["id"]] >= BOT_BATTLE_COOLDOWN_SECONDS
    ]
    return random.choice(eligible) if eligible else None


def _post_bot_application(opponent, now):
    from server import social

    offer = social.add_public_duel_offer(
        {"character_id": opponent["id"], "name": opponent["name"]},
        "backyard",
        created_at=now,
    )
    BOT_LAST_ATTACK_AT[opponent["id"]] = now
    _save_bot_state()
    return offer


def _post_next_bot_application(now, excluded_ids):
    attacker = _pick_attacker(now, excluded_ids)
    if attacker is not None:
        _post_bot_application(attacker, now)


def _resolve_bot_battle(attacker_id, defender_id, now):
    attacker = BOT_STATE[attacker_id]
    defender = BOT_STATE[defender_id]
    attacker_fighter = _fighter_from_profile(attacker)
    defender_fighter = _fighter_from_profile(defender)
    battle = Battle(attacker_fighter, defender_fighter)
    while not battle.is_over():
        attack_zone, defense_zones = _random_turn_choice()
        battle.choose_player_zones(attack_zone, defense_zones)
        battle.resolve_turn()
    record_battle(battle, source="bot_vs_bot", extra={"attacker_id": attacker_id, "defender_id": defender_id})
    _store_fighter(attacker_id, attacker_fighter, now)
    _store_fighter(defender_id, defender_fighter, now)
    BOT_STATE[attacker_id]["zone"] = "tavern"
    BOT_STATE[defender_id]["zone"] = "tavern"
    BOT_LAST_BATTLE_AT[attacker_id] = now
    BOT_LAST_BATTLE_AT[defender_id] = now
    from server import social
    social.record_bot_tavern_reply(attacker_id, attacker["name"], battle.outcome(), location="tavern")
    social.record_bot_tavern_reply(defender_id, defender["name"], battle.outcome(), location="tavern")
    _save_bot_state()
    return {
        "status": "accepted",
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "winner": battle.winner_name(),
        "turns": battle.turn,
    }


def _regenerate_bots(now):
    changed = False
    for opponent_id, opponent in BOT_STATE.items():
        if opponent["hp"] >= opponent["max_hp"]:
            BOT_UPDATED_AT[opponent_id] = now
            if opponent["zone"] == "tavern":
                opponent["zone"] = "backyard"
                changed = True
            continue
        elapsed = max(0, now - BOT_UPDATED_AT[opponent_id])
        full_regen_seconds = BOT_TAVERN_FULL_REGEN_SECONDS if opponent["zone"] == "tavern" else BOT_FULL_REGEN_SECONDS
        regen_per_second = opponent["max_hp"] / full_regen_seconds
        healed = int(elapsed * regen_per_second)
        # Не сбрасываем таймер, пока не накопилось хотя бы 1 хп — иначе при
        # частых вызовах (например, раз в секунду) дробный прогресс терялся
        # каждый раз и боты переставали лечиться вовсе.
        if healed <= 0:
            continue
        opponent["hp"] = min(opponent["max_hp"], opponent["hp"] + healed)
        BOT_UPDATED_AT[opponent_id] = now
        if opponent["zone"] == "tavern" and opponent["hp"] >= opponent["max_hp"]:
            opponent["zone"] = "backyard"
        changed = True
    if changed:
        _save_bot_state()


def _fighter_from_profile(profile):
    fighter = Fighter(profile["name"], profile["level"])
    fighter.xp = profile["xp"]
    fighter.stats = copy.deepcopy(profile["stats"])
    fighter.stat_points = profile["stat_points"]
    fighter.recalculate_parameters()
    fighter.hp = profile["hp"]
    fighter.mp = profile["mp"]
    fighter.max_mp = profile["max_mp"]
    return fighter


def _store_fighter(opponent_id, fighter, now):
    update_bot(opponent_id, {
        "level": fighter.level,
        "xp": fighter.xp,
        "hp": fighter.hp,
        "mp": fighter.mp,
        "max_mp": fighter.max_mp,
        "stats": fighter.stats,
        "stat_points": fighter.stat_points,
    })
    BOT_UPDATED_AT[opponent_id] = now


def _random_turn_choice():
    zones = ("head", "body", "waist", "thigh", "shin")
    return random.choice(zones), random.sample(zones, 2)


def _allocate_bot_stat_points(opponent):
    weights = BOT_STAT_WEIGHTS.get(opponent.get("role"), BOT_STAT_WEIGHTS["boss"])
    while opponent["stat_points"] > 0:
        stat_name = weights[(opponent["stat_points"] - 1) % len(weights)]
        opponent["stats"][stat_name] += 1
        opponent["stat_points"] -= 1
