import copy
import json
import os
import random
import threading
import time

from kaloda.combat.card_battle import CardBattle
from kaloda.combat.card_database import (
    DECK_SIZE,
    cards_for_type,
    class_cards_for_type,
    expand_deck_card_keys,
    is_mage_profession,
)
from kaloda.combat.character_stats import (
    BASE_STAT_VALUE,
    STAT_NAMES,
    calculate_max_hp,
    calculate_max_mana,
    minimum_endurance,
    total_stat_points,
)
from kaloda.combat.fighter import Fighter
from kaloda.server import config

# Вне таверны (задний двор) боты лечатся 10 минут до полного хп, в таверне — вдвое быстрее.
BOT_FULL_REGEN_SECONDS = 600
BOT_TAVERN_FULL_REGEN_SECONDS = 300
BOT_BATTLE_INTERVAL_SECONDS = 30
BOT_BATTLE_COOLDOWN_SECONDS = 600
BOT_APPLICATION_WAIT_SECONDS = 30
# Если реальный игрок подал заявку на бой и никто из игроков не откликнулся
# за это время, её подхватывает бот подходящего уровня.
PLAYER_APPLICATION_WAIT_SECONDS = 60
MAX_BOT_BATTLE_TURNS = 60
# Заблокированные (без набора опыта) боты держат самую длинную возможную заявку
# и ждут только вызова игрока — в автоматические бои бот-против-бота их не берём.
LOCKED_BOT_APPLICATION_TTL_SECONDS = 1800
BOT_STAT_WEIGHTS = {
    "critical": ("intuition", "strength", "agility", "endurance"),
    "agile": ("agility", "intuition", "strength", "endurance"),
    "tank": ("endurance", "strength", "agility", "intuition"),
    "boss": ("strength", "endurance", "intuition", "agility"),
}


def _bot(identifier, name, bot_type, stats, deck=None):
    """Описание бота. Колода None означает базовую колоду класса: её читают из базы карт при первом обращении."""
    full_stats = {stat_name: BASE_STAT_VALUE for stat_name in STAT_NAMES}
    full_stats.update(stats)
    max_hp = calculate_max_hp(1, full_stats["endurance"], bot_type)
    max_mp = calculate_max_mana(full_stats["intellect"], bot_type)
    return {
        "id": identifier,
        "name": name,
        "type": bot_type,
        "level": 1,
        "xp": 0,
        "hp": max_hp,
        "max_hp": max_hp,
        "mp": max_mp,
        "max_mp": max_mp,
        "stats": full_stats,
        "stat_points": 0,
        "zone": "backyard",
        "kind": "bot",
        "role": bot_type,
        "locked_level": True,
        "deck": None if deck is None else list(deck),
    }


# Зафиксированные боты 1 уровня: без набора опыта, каждый играет базовой колодой своего класса.
BOT_OPPONENTS = (
    _bot("bot_elpachino_fred", "Ельпачино Фред", "archer", {"strength": 3, "agility": 5, "intuition": 4, "endurance": 4}),
    _bot("bot_stealth_joe", "Скрытный Джо", "assassin", {"agility": 6, "intuition": 5, "endurance": 3}),
    _bot("bot_fierce_karlo", "Сверепый Карло", "warrior", {"strength": 5, "endurance": 7}),
    _bot(
        "bot_wise_victor",
        "Мудрый Виктор",
        "mage",
        {"wisdom": 6, "intellect": 5, "endurance": 3},
        deck=[
            "mage_flash",
            "mage_fireball",
            "mage_crimson_blood",
            "mage_burning_support",
            "mage_fervent_service",
            "mage_pyromania",
            "mage_water_summon",
            "mage_rising_flow",
            "mage_flow_blessing",
            "mage_water_guard",
            "mage_waterfall",
            "mage_gurgling_flow",
            "mage_boulder_summon",
            "mage_earth_spikes",
            "mage_stone_barrages",
            "mage_golem_summon",
            "mage_mineral_armor",
            "mage_stone_spikes",
            "mage_lightning_strike",
            "mage_thundercloud",
            "mage_paralysis",
            "mage_lightning_punishment",
        ],
    ),
)


BOT_STATE_PATH = config.DATA_DIR / "bot_state.json"
BOT_ZONES = ("backyard", "tavern")
# Состояние наполняется при первом обращении (_ensure_state_loaded): импорт модуля не читает и не пишет файлы.
BOT_STATE = {}
BOT_UPDATED_AT = {}
BOT_LAST_BATTLE_AT = {}
BOT_LAST_ATTACK_AT = {}
BOT_SCHEDULER_STARTED_AT = 0.0
BOT_LAST_SIMULATED_BATTLE_AT = 0.0
BOT_STATE_LOCK = threading.RLock()
_state_loaded = False
_database = None


def _normalize_bot_stats(opponent):
    old_max_hp = int(opponent.get("max_hp", 0))
    old_hp = int(opponent.get("hp", old_max_hp))
    level = max(1, int(opponent.get("level", 1)))
    opponent["level"] = level
    if opponent.get("locked_level"):
        # Зафиксированные боты не качают очки и не меняют статы — только пересчёт HP по актуальной формуле.
        opponent["stat_points"] = 0
        opponent["max_hp"] = calculate_max_hp(
            level,
            opponent["stats"]["endurance"],
            opponent.get("type", "warrior"),
        )
        opponent["hp"] = opponent["max_hp"] if old_hp >= old_max_hp else max(0, min(old_hp, opponent["max_hp"]))
        return
    stats = {stat_name: BASE_STAT_VALUE for stat_name in STAT_NAMES}
    stats["endurance"] = minimum_endurance(level)
    free_points = total_stat_points(level)
    weights = BOT_STAT_WEIGHTS.get(opponent.get("role"), BOT_STAT_WEIGHTS["boss"])
    for index in range(free_points):
        stats[weights[index % len(weights)]] += 1
    opponent["stats"] = stats
    opponent["stat_points"] = 0
    opponent["max_hp"] = calculate_max_hp(
        level,
        stats["endurance"],
        opponent.get("type", "warrior"),
    )
    opponent["hp"] = opponent["max_hp"] if old_hp >= old_max_hp else max(0, min(old_hp, opponent["max_hp"]))


def _init_memory_state():
    """Боты в начальном состоянии: полное здоровье, таймеры заявок и боёв сброшены."""
    global BOT_SCHEDULER_STARTED_AT, BOT_LAST_SIMULATED_BATTLE_AT
    now = time.time()
    BOT_STATE.clear()
    for opponent in BOT_OPPONENTS:
        state = copy.deepcopy(opponent)
        if state["deck"] is None:
            state["deck"] = [card.key for card in cards_for_type(state["type"])]
        _normalize_bot_stats(state)
        BOT_STATE[state["id"]] = state
    for timers, value in ((BOT_UPDATED_AT, now), (BOT_LAST_BATTLE_AT, 0.0), (BOT_LAST_ATTACK_AT, 0.0)):
        timers.clear()
        timers.update(dict.fromkeys(BOT_STATE, value))
    BOT_SCHEDULER_STARTED_AT = 0.0
    BOT_LAST_SIMULATED_BATTLE_AT = 0.0


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
        try:
            _restore_bot(opponent_id, opponent)
        except (TypeError, ValueError, KeyError):
            # Повреждённая запись одного бота не должна ломать остальных: он остаётся в начальном состоянии.
            continue


def _restore_bot(opponent_id, saved):
    home = BOT_STATE[opponent_id]
    if home.get("locked_level"):
        # Сброс накопившегося уровня/опыта из старых боёв — берём из файла только HP/зону.
        saved_max_hp = int(saved.get("max_hp", home["max_hp"]))
        saved_hp = int(saved.get("hp", saved_max_hp))
        home["hp"] = (
            home["max_hp"]
            if saved_hp >= saved_max_hp
            else max(0, min(saved_hp, home["max_hp"]))
        )
        if saved.get("zone") in BOT_ZONES:
            home["zone"] = saved["zone"]
    else:
        restored = copy.deepcopy(saved)
        _normalize_bot_stats(restored)
        BOT_STATE[opponent_id] = restored
    now = time.time()
    BOT_UPDATED_AT[opponent_id] = min(float(saved.get("updated_at", now)), now)
    BOT_LAST_BATTLE_AT[opponent_id] = min(float(saved.get("last_battle_at", 0.0)), now)
    BOT_LAST_ATTACK_AT[opponent_id] = min(float(saved.get("last_attack_at", 0.0)), now)


def _save_bot_state():
    payload = {}
    for opponent_id, opponent in BOT_STATE.items():
        snapshot = copy.deepcopy(opponent)
        snapshot["updated_at"] = BOT_UPDATED_AT.get(opponent_id, time.time())
        snapshot["last_battle_at"] = BOT_LAST_BATTLE_AT.get(opponent_id, 0.0)
        snapshot["last_attack_at"] = BOT_LAST_ATTACK_AT.get(opponent_id, 0.0)
        payload[opponent_id] = snapshot
    # Сначала временный файл, потом замена: обрыв записи не оставляет битый JSON
    temp_path = BOT_STATE_PATH.with_name(BOT_STATE_PATH.name + ".tmp")
    try:
        BOT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, BOT_STATE_PATH)
    except OSError as error:
        print(f"Состояние ботов не сохранено: {error}")


def _ensure_state_loaded():
    """Один раз за процесс собирает боты из описаний и накладывает сохранённое состояние из файла."""
    global _state_loaded
    with BOT_STATE_LOCK:
        if _state_loaded:
            return
        _init_memory_state()
        _load_bot_state()
        _state_loaded = True


def reset_bot_state():
    """Сбрасывает память к начальному состоянию; сохранённый файл будет прочитан заново при следующем обращении."""
    global _state_loaded
    with BOT_STATE_LOCK:
        BOT_STATE.clear()
        _state_loaded = False


def bind_database(database):
    """Подключает базу, через которую боты читают профили игроков и пишут реплики в чат. Возвращает прежнюю."""
    global _database
    with BOT_STATE_LOCK:
        previous, _database = _database, database
    return previous


def get_database():
    global _database
    with BOT_STATE_LOCK:
        if _database is None:
            from kaloda.server.database import Database

            _database = Database()
        return _database


def get_bot_opponents():
    with BOT_STATE_LOCK:
        _ensure_state_loaded()
        _regenerate_bots(time.time())
        return copy.deepcopy(list(BOT_STATE.values()))


def update_bot(opponent_id, profile):
    """Применяет профиль к боту и возвращает его обновлённую копию."""
    with BOT_STATE_LOCK:
        _ensure_state_loaded()
        if opponent_id not in BOT_STATE:
            raise ValueError("Бот не найден")
        opponent = BOT_STATE[opponent_id]
        if not isinstance(profile, dict):
            profile = {"hp": profile}
        # Зафиксированные боты не растут: меняются только их HP и MP
        keys = ("hp", "mp", "max_mp") if opponent.get("locked_level") else (
            "level", "xp", "hp", "mp", "max_mp", "stats", "stat_points",
        )
        for key in keys:
            if key in profile:
                opponent[key] = copy.deepcopy(profile[key])
        _allocate_bot_stat_points(opponent)
        opponent["max_hp"] = calculate_max_hp(
            opponent["level"],
            opponent["stats"]["endurance"],
            opponent.get("type", "warrior"),
        )
        opponent["hp"] = max(0, min(opponent["max_hp"], int(opponent["hp"])))
        opponent["mp"] = max(0, min(opponent["max_mp"], int(opponent["mp"])))
        BOT_UPDATED_AT[opponent_id] = time.time()
        _save_bot_state()
        return copy.deepcopy(opponent)


def run_bot_battle_tick(now=None):
    """Управляет заявками ботов на доске и разрешает принятые бои ботов."""
    global BOT_SCHEDULER_STARTED_AT, BOT_LAST_SIMULATED_BATTLE_AT
    now = time.time() if now is None else float(now)
    with BOT_STATE_LOCK:
        _ensure_state_loaded()
        if BOT_SCHEDULER_STARTED_AT == 0.0:
            BOT_SCHEDULER_STARTED_AT = now
            return None
        _regenerate_bots(now)
        from kaloda.server import social

        _maintain_locked_bot_applications(now)
        pending = social.pending_bot_public_offers("backyard")
        player_offer = next(
            (
                offer for offer in social.pending_player_public_offers("backyard")
                if now - float(offer["created_at"]) >= PLAYER_APPLICATION_WAIT_SECONDS
            ),
            None,
        )
        if player_offer is not None and now - BOT_LAST_SIMULATED_BATTLE_AT >= BOT_BATTLE_INTERVAL_SECONDS:
            result = _accept_player_offer_with_bot(player_offer, now)
            if result is not None:
                BOT_LAST_SIMULATED_BATTLE_AT = now
                return result
        stale = next(
            (
                offer for offer in pending
                if now - float(offer["created_at"]) >= BOT_APPLICATION_WAIT_SECONDS
                and _can_accept_application(offer["sender_id"], now)
                and not BOT_STATE.get(offer["sender_id"], {}).get("locked_level")
            ),
            None,
        )
        if stale is not None and now - BOT_LAST_SIMULATED_BATTLE_AT >= BOT_BATTLE_INTERVAL_SECONDS:
            social.close_public_offer(stale["id"], "cancelled", now)
            stale_type = BOT_STATE.get(stale["sender_id"], {}).get("type", "warrior")
            target_offer = next(
                (
                    offer for offer in pending
                    if offer["id"] != stale["id"]
                    and BOT_STATE.get(offer["sender_id"], {}).get("type", "warrior") == stale_type
                ),
                None,
            )
            if target_offer is None:
                target = _pick_attacker(now, exclude_ids={stale["sender_id"]}, character_type=stale_type)
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


def _accept_player_offer_with_bot(player_offer, now):
    from kaloda.server import social

    player_record = get_database().get_character_for_battle(player_offer["sender_id"])
    if player_record is None:
        social.close_public_offer(player_offer["id"], "cancelled", now)
        return None
    player_profile = player_record["character"]
    player_type = player_profile.get("type", "warrior")
    candidates = [
        bot for bot in BOT_STATE.values()
        if bot["zone"] == "backyard"
        and bot.get("type", "warrior") == player_type
        and bot["hp"] == bot["max_hp"]
        and social.backyard_duel_error(player_profile, bot) is None
    ]
    bot = random.choice(candidates) if candidates else None
    if bot is None:
        return None

    # Бот только помечает заявку принятой — сам бой игрок проходит интерактивно в DuelScene,
    # как и при обычном вызове бота. Бот остаётся в заднем дворе, пока бой не завершится.
    social.accept_public_offer(player_offer["id"], bot["id"], now)
    return {
        "status": "accepted_by_bot",
        "player_id": player_profile["id"],
        "bot_id": bot["id"],
    }


def _can_accept_application(opponent_id, now):
    opponent = BOT_STATE.get(opponent_id)
    return opponent is not None and opponent["zone"] == "backyard" and opponent["hp"] == opponent["max_hp"] and (
        now - BOT_LAST_BATTLE_AT[opponent_id] >= BOT_BATTLE_COOLDOWN_SECONDS
    )


def _pick_attacker(now, exclude_ids=frozenset(), character_type=None):
    eligible = [
        opponent for opponent in BOT_STATE.values()
        if opponent["id"] not in exclude_ids
        and not opponent.get("locked_level")
        and opponent["zone"] == "backyard"
        and (character_type is None or opponent.get("type", "warrior") == character_type)
        and opponent["hp"] == opponent["max_hp"]
        and now - BOT_LAST_ATTACK_AT[opponent["id"]] >= BOT_BATTLE_COOLDOWN_SECONDS
        and now - BOT_LAST_BATTLE_AT[opponent["id"]] >= BOT_BATTLE_COOLDOWN_SECONDS
    ]
    return random.choice(eligible) if eligible else None


def _post_bot_application(opponent, now, ttl=None):
    from kaloda.server import social

    kwargs = {} if ttl is None else {"ttl": ttl}
    offer = social.add_public_duel_offer(
        {"character_id": opponent["id"], "name": opponent["name"]},
        "backyard",
        created_at=now,
        **kwargs,
    )
    BOT_LAST_ATTACK_AT[opponent["id"]] = now
    _save_bot_state()
    return offer


def _maintain_locked_bot_applications(now):
    """Зафиксированные боты всегда держат активной самую долгую заявку,
    пока ждут вызова игрока; истёкшая без ответа заявка переставляется автоматически."""
    from kaloda.server import social

    for opponent in BOT_STATE.values():
        if (
            opponent.get("locked_level")
            and opponent["zone"] == "backyard"
            and opponent["hp"] == opponent["max_hp"]
            and social.pending_public_offer(opponent["id"], "backyard") is None
        ):
            _post_bot_application(opponent, now, ttl=LOCKED_BOT_APPLICATION_TTL_SECONDS)


def _post_next_bot_application(now, excluded_ids):
    attacker = _pick_attacker(now, excluded_ids)
    if attacker is not None:
        _post_bot_application(attacker, now)


def _resolve_bot_battle(attacker_id, defender_id, now):
    _ensure_state_loaded()
    attacker = BOT_STATE[attacker_id]
    defender = BOT_STATE[defender_id]
    attacker_fighter = _fighter_from_profile(attacker)
    defender_fighter = _fighter_from_profile(defender)
    battle = CardBattle(
        attacker_fighter,
        defender_fighter,
        cards=_battle_deck(attacker),
        enemy_cards=_battle_deck(defender),
        mage_mode=is_mage_profession(attacker.get("type")) or is_mage_profession(defender.get("type")),
    )
    # У каждой стороны свой стол и своя колода: карты берутся из стола своей стороны.
    first_side = battle.draft_first_side()
    second_side = "enemy" if first_side == "player" else "player"
    for _ in range(battle.STARTING_PICK_LIMIT):
        for side in (first_side, second_side):
            table = battle.table_for(side)
            battle.choose_starting_card(side, table[random.randrange(len(table))].key)
    battle.finish_starting_deal()
    # На каждый ход нужно давать бойцам новые карты и очки действий, иначе,
    # когда у обеих сторон заканчиваются доступные по цене карты, ни одна из
    # них не наносит урона и цикл проверки battle.is_over() зависает навсегда,
    # блокируя фоновый поток планировщика ботов (бои на заднем дворе замирали).
    while not battle.is_over() and battle.turn < MAX_BOT_BATTLE_TURNS:
        for side in ("player", "enemy"):
            for card in list(battle.hands[side]):
                battle.select_card(side, card.key)
            battle.confirm_selection(side)
        battle.resolve_turn()
        if not battle.is_over():
            battle.start_next_turn()
    if not battle.is_over():
        # Подстраховка: если за отведённое число ходов никто не умер, бой
        # решается по остатку хп, чтобы гарантированно завершиться.
        if attacker_fighter.hp == defender_fighter.hp:
            attacker_fighter.hp = 0
            defender_fighter.hp = 0
        elif attacker_fighter.hp < defender_fighter.hp:
            attacker_fighter.hp = 0
        else:
            defender_fighter.hp = 0
    _store_fighter(attacker_id, attacker_fighter, now)
    _store_fighter(defender_id, defender_fighter, now)
    BOT_STATE[attacker_id]["zone"] = "tavern"
    BOT_STATE[defender_id]["zone"] = "tavern"
    BOT_LAST_BATTLE_AT[attacker_id] = now
    BOT_LAST_BATTLE_AT[defender_id] = now
    from kaloda.server import social

    # Исход считается с точки зрения атакующего, защитник хвастается или жалуется наоборот
    outcome = battle.outcome()
    defender_outcome = {"win": "loss", "loss": "win", "draw": "draw"}[outcome]
    social.record_bot_tavern_reply(attacker_id, attacker["name"], outcome, location="tavern")
    social.record_bot_tavern_reply(defender_id, defender["name"], defender_outcome, location="tavern")
    _save_bot_state()
    return {
        "status": "accepted",
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "winner": battle.winner_name(),
        "turns": battle.turn,
    }


def _regenerate_bots(now):
    """Лечит ботов по времени. Не пишет файл: исход восстанавливается при загрузке из HP и метки времени последнего сохранения."""
    for opponent_id, opponent in BOT_STATE.items():
        if opponent["hp"] >= opponent["max_hp"]:
            BOT_UPDATED_AT[opponent_id] = now
            if opponent["zone"] == "tavern":
                opponent["zone"] = "backyard"
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


def _fighter_from_profile(profile):
    fighter = Fighter(profile["name"], profile["level"], profession_type=profile.get("type", "warrior"))
    fighter.xp = profile["xp"]
    fighter.stats = copy.deepcopy(profile["stats"])
    fighter.stat_points = profile["stat_points"]
    fighter.recalculate_parameters()
    fighter.hp = min(int(profile["hp"]), fighter.max_hp)
    fighter.mp = profile["mp"]
    fighter.max_mp = profile["max_mp"]
    return fighter


def _battle_deck(profile):
    """Колода бота для боя: только карты его класса, недостающее добирается картами того же класса (как у клиента)."""
    character_type = profile.get("type", "warrior")
    class_cards = class_cards_for_type(character_type)
    if not profile.get("deck"):
        return class_cards
    cards_by_key = {card.key: card for card in cards_for_type(character_type)}
    deck = [cards_by_key[key] for key in expand_deck_card_keys(profile["deck"]) if key in cards_by_key]
    if len(deck) < DECK_SIZE:
        deck.extend([card for card in class_cards if card not in deck][:DECK_SIZE - len(deck)])
    return deck


def _store_fighter(opponent_id, fighter, now):
    bot = BOT_STATE[opponent_id]
    if bot.get("locked_level"):
        # Заблокированные боты не набирают опыт и не растут — сохраняем только HP/MP боя.
        update_bot(opponent_id, {
            "hp": min(int(fighter.hp), int(bot["max_hp"])),
            "mp": fighter.mp,
            "max_mp": fighter.max_mp,
        })
    else:
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


def _allocate_bot_stat_points(opponent):
    weights = BOT_STAT_WEIGHTS.get(opponent.get("role"), BOT_STAT_WEIGHTS["boss"])
    while opponent["stat_points"] > 0:
        stat_name = weights[(opponent["stat_points"] - 1) % len(weights)]
        opponent["stats"][stat_name] += 1
        opponent["stat_points"] -= 1
