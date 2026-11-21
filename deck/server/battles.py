"""Server-owned Deck combat sessions backed by the shared combat rules."""

import json
import random
import threading
import time
import uuid

from deck.combat.card_battle import CardBattle
from deck.combat.battle_archive import build_battle_record
from deck.combat.card_database import (
    Card,
    DECK_SIZE,
    cards_for_type,
    class_cards_for_type,
    expand_deck_card_keys,
    is_mage_profession,
)
from deck.combat.fighter import Fighter


SESSION_TTL_SECONDS = 60 * 60
DRAFT_TIMEOUT_SECONDS = 90
DRAW_TIMEOUT_SECONDS = 15
TURN_TIMEOUT_SECONDS = 60
TURN_TIMEOUTS_BEFORE_SURRENDER = 3
_LOCK = threading.RLock()
_SESSIONS = {}
_CHARACTER_SESSIONS = {}
_STORAGE = None
_STATE_FORMAT_VERSION = 1


def _encode_state(value):
    if value is random:
        return {"$type": "random_module"}
    if isinstance(value, Card):
        return {"$type": "card", "attributes": _encode_state(value.__dict__)}
    if isinstance(value, Fighter):
        return {"$type": "fighter", "attributes": _encode_state(value.__dict__)}
    if isinstance(value, CardBattle):
        return {"$type": "card_battle", "attributes": _encode_state(value.__dict__)}
    if isinstance(value, dict):
        return {
            "$type": "dict",
            "items": [[_encode_state(key), _encode_state(item)] for key, item in value.items()],
        }
    if isinstance(value, list):
        return {"$type": "list", "items": [_encode_state(item) for item in value]}
    if isinstance(value, tuple):
        return {"$type": "tuple", "items": [_encode_state(item) for item in value]}
    if isinstance(value, set):
        return {"$type": "set", "items": [_encode_state(item) for item in value]}
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError(f"Нельзя сохранить состояние боя типа {type(value).__name__}")


def _decode_state(value):
    if not isinstance(value, dict) or "$type" not in value:
        return value
    value_type = value["$type"]
    if value_type == "random_module":
        return random
    if value_type == "dict":
        return {
            _decode_state(key): _decode_state(item)
            for key, item in value["items"]
        }
    if value_type in ("list", "tuple", "set"):
        items = [_decode_state(item) for item in value["items"]]
        return {"list": list, "tuple": tuple, "set": set}[value_type](items)
    if value_type in ("card", "fighter", "card_battle"):
        attributes = _decode_state(value["attributes"])
        if value_type == "card":
            return Card(**attributes)
        instance_type = Fighter if value_type == "fighter" else CardBattle
        instance = instance_type.__new__(instance_type)
        instance.__dict__.update(attributes)
        return instance
    raise ValueError(f"Неизвестный тип состояния боя: {value_type!r}")


def _serialize_session(session):
    return json.dumps(
        {"version": _STATE_FORMAT_VERSION, "session": _encode_state(session)},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _deserialize_session(state_json):
    payload = json.loads(state_json)
    if payload.get("version") != _STATE_FORMAT_VERSION:
        raise ValueError(
            f"Неподдерживаемая версия сохранённого боя: {payload.get('version')!r}"
        )
    session = _decode_state(payload["session"])
    if not isinstance(session, dict) or not isinstance(session.get("battle"), CardBattle):
        raise ValueError("Повреждено сохранённое состояние боя")
    return session


def _persist_session(session):
    if _STORAGE is not None:
        _STORAGE.save_deck_battle_session(
            session["id"], _serialize_session(session), session["updated_at"],
        )


def configure_storage(storage):
    """Loads this world's persisted sessions and switches the backing store."""
    global _STORAGE
    with _LOCK:
        if storage is _STORAGE:
            return
        sessions = {}
        character_sessions = {}
        if storage is not None:
            rows = storage.load_deck_battle_sessions(
                time.time() - SESSION_TTL_SECONDS,
            )
            for row in rows:
                session = _deserialize_session(row["state_json"])
                session_id = str(row["session_id"])
                if session.get("id") != session_id:
                    raise ValueError("Идентификатор сохранённого боя не совпадает с записью")
                sessions[session_id] = session
                for participant_id in session["participants"]:
                    participant_id = str(participant_id)
                    if participant_id in character_sessions:
                        raise ValueError(
                            f"Персонаж {participant_id} найден в нескольких сохранённых боях"
                        )
                    character_sessions[participant_id] = session_id
        _SESSIONS.clear()
        _SESSIONS.update(sessions)
        _CHARACTER_SESSIONS.clear()
        _CHARACTER_SESSIONS.update(character_sessions)
        _STORAGE = storage


def _fighter(profile):
    profession = str(profile.get("type", "warrior"))
    fighter = Fighter(str(profile.get("name", "Игрок")), int(profile.get("level", 1)), profession)
    fighter.stats = dict(profile.get("stats", {}))
    for stat_name in fighter.STAT_NAMES:
        fighter.stats.setdefault(stat_name, 2)
    fighter.talents = dict(profile.get("talents", {}))
    fighter.recalculate_parameters()
    fighter.hp = min(int(profile.get("hp", fighter.max_hp)), fighter.max_hp)
    fighter.mp = min(int(profile.get("mp", fighter.max_mp)), fighter.max_mp)
    fighter.xp = int(profile.get("xp", 0))
    fighter.stat_points = int(profile.get("stat_points", 0))
    fighter.character_id = profile.get("id", profile.get("character_id"))
    return fighter


def _deck(profile):
    profession = str(profile.get("type", "warrior"))
    cards = cards_for_type(profession)
    by_key = {card.key: card for card in cards}
    keys = expand_deck_card_keys(profile.get("deck") or {})
    selected = [by_key[key] for key in keys if key in by_key]
    if len(selected) < DECK_SIZE:
        selected.extend(
            card for card in class_cards_for_type(profession)
            if card not in selected
        )
    return selected[:DECK_SIZE]


def _card_payload(card):
    return {
        "key": card.key,
        "name": card.name,
        "group_name": card.group_name,
        "effect_type": card.effect_type,
        "effect_data": dict(card.effect_data),
        "resource_type": card.resource_type,
        "resource_cost": card.resource_cost,
        "effect_duration": card.effect_duration,
        "rarity": card.rarity,
    }


def _public_fighter(fighter):
    return {
        "name": fighter.name,
        "level": fighter.level,
        "type": fighter.profession_type,
        "hp": fighter.hp,
        "max_hp": fighter.max_hp,
        "mp": fighter.mp,
        "max_mp": fighter.max_mp,
        "stats": dict(fighter.stats),
        "unique_resource_type": fighter.unique_resource_type,
        "unique_resource": fighter.unique_resource_current,
        "unique_resource_max": fighter.unique_resource_max,
    }


# Презентация бойцов для клиента (порт плашек и призывов из deck/ui/duel_renderer.py). Статус — это id, знак positive
# и, где Python их показывает, turns (ходов осталось), stacks (стаки) и amount (значение). Текст строит клиент.
_BUFF_HIDDEN_KEYS = frozenset({
    "remaining", "fresh", "expire_after_turn", "forest_spirit", "entangle_source", "dodge_stack_limit",
})
# Ключи бафа со знаком «минус» по duel_renderer.py; все остальные ключи, включая неизвестные, позитивны.
_BUFF_NEGATIVE_KEYS = frozenset({
    "mana_regen_debuff", "steal_healing_percent", "outgoing_damage_flat", "outgoing_damage_percent",
    "healing_blocked", "forbid_damage_cards", "entangled", "mark_damage", "poison_cap_bonus", "dodge_stun",
})
_MAGE_STATUS_IDS = {"огонь": "fire", "вода": "water", "холод": "cold", "электро": "electro", "воздух": "air"}
_PHYS_STATE_STATUSES = (
    ("guaranteed_crits", True),
    ("no_crit_attacks", False),
    ("guaranteed_dodges", True),
    ("dodge_stacks", True),
)
_SPIRIT_NAME = "Лесной дух"


def _effects(battle, attribute, side, default):
    # getattr: сессии, сохранённые до появления атрибута, отдают снимок без ошибки.
    return getattr(battle, attribute, {}).get(side, default)


def _status(status_id, positive, turns=None, stacks=None, amount=None):
    return {"id": status_id, "positive": positive, "turns": turns, "stacks": stacks, "amount": amount}


def _numeric_or_none(value):
    # Булевы значения Python выводит без числа, поэтому для них amount пустой.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _buff_statuses(buff):
    turns = 1 if buff.get("expire_after_turn") else max(1, int(buff.get("remaining", 1)))
    return [
        _status(key, key not in _BUFF_NEGATIVE_KEYS, turns=turns, amount=_numeric_or_none(value))
        for key, value in buff.items()
        if key not in _BUFF_HIDDEN_KEYS and value
    ]


# Порядок тот же, что у плашки Python: бафы, яд, кровотечение, лечение, отложенные эффекты, статусы мага, оглушение,
# заморозка, неуязвимость, счётчики, пропуск хода, бонусы и облака мага, благословения.
def _presentation_statuses(battle, side):
    statuses = []
    for buff in _effects(battle, "phys_buffs", side, []):
        statuses.extend(_buff_statuses(buff))
    poisons = _effects(battle, "poisons", side, [])
    if poisons:
        statuses.append(_status("poison", False, stacks=len(poisons)))
    bleeds = _effects(battle, "bleeds", side, [])
    if bleeds:
        statuses.append(_status(
            "bleed",
            False,
            turns=max(int(bleed["remaining"]) for bleed in bleeds),
            amount=sum(int(bleed["damage"]) for bleed in bleeds),
        ))
    for regeneration in _effects(battle, "regenerations", side, []):
        statuses.append(_status(
            "regeneration", True, turns=int(regeneration["remaining"]), amount=int(regeneration["heal_per_turn"]),
        ))
    for heal in _effects(battle, "delayed_heals", side, []):
        statuses.append(_status("delayed_heal", True, turns=int(heal["remaining"])))
    for loss in _effects(battle, "delayed_hp_loss", side, []):
        statuses.append(_status("delayed_hp_loss", False, turns=int(loss["remaining"]), amount=int(loss["amount"])))
    for effect in _effects(battle, "mage_statuses", side, []):
        name = str(effect["name"])
        statuses.append(_status(
            _MAGE_STATUS_IDS.get(name, name),
            name.endswith("_immunity"),
            turns=int(effect.get("remaining", 1)),
            stacks=int(effect.get("stacks", 1)),
        ))
    stun = int(_effects(battle, "mage_stuns", side, 0))
    if stun:
        statuses.append(_status("stun", False, turns=stun))
    freeze = int(_effects(battle, "mage_freeze", side, 0))
    if freeze:
        statuses.append(_status("freeze", False, turns=freeze))
    if _effects(battle, "invulnerable", side, False):
        statuses.append(_status("invulnerable", True))
    state = _effects(battle, "phys_state", side, {})
    for key, positive in _PHYS_STATE_STATUSES:
        count = int(state.get(key, 0))
        if count:
            statuses.append(_status(key, positive, stacks=count))
    if _effects(battle, "skip_next_turn", side, False):
        statuses.append(_status("skip_turn", False))
    for bonus in _effects(battle, "mage_damage_bonuses", side, []):
        statuses.append(_status(
            "mage_damage_bonus", True, turns=int(bonus.get("remaining", 1)), amount=int(bonus.get("percent", 0)),
        ))
    for cloud in _effects(battle, "mage_clouds", side, []):
        statuses.append(_status("storm_cloud", True, turns=int(cloud.get("remaining", 1))))
    for blessing in _effects(battle, "mage_reactive_blessings", side, []):
        statuses.append(_status("reactive_blessing", True, turns=int(blessing.get("remaining", 1))))
    return statuses


# Живые призывы стороны: сначала дух, затем големы (как в _draw_summons_near_discard). turns у духа — остаток ходов,
# если он есть в состоянии; у големов и духа без остатка turns пустой.
def _presentation_summons(battle, side):
    summons = []
    spirit = _effects(battle, "phys_spirits", side, None)
    if spirit and int(spirit.get("hp", 0)) > 0:
        hp = int(spirit["hp"])
        summons.append({
            "kind": "spirit",
            "name": _SPIRIT_NAME,
            "hp": hp,
            "max_hp": int(spirit.get("max_hp", hp)),
            "turns": int(spirit.get("remaining", 0)) or None,
        })
    for golem in _effects(battle, "mage_golems", side, []):
        hp = int(golem.get("hp", 0))
        if hp > 0:
            summons.append({
                "kind": "golem",
                "name": str(golem.get("name", "Голем")),
                "hp": hp,
                "max_hp": int(golem.get("max_hp", hp)),
                "turns": None,
            })
    return summons


# Поля бойца в снимке: shield — щит физический плюс магический; statuses и summons — см. функции выше.
def _presentation_fields(battle, side):
    return {
        "shield": int(_effects(battle, "phys_shields", side, 0)) + int(_effects(battle, "mage_shields", side, 0)),
        "statuses": _presentation_statuses(battle, side),
        "summons": _presentation_summons(battle, side),
    }


def _draft_picks(battle, side):
    """Ключи карт, которые сторона взяла в текущем драфте: Python-клиент показывает их летящими картами."""
    if battle.draft_mode == "starting":
        picked = battle.hands[side]
    elif battle.draft_mode == "redraft":
        # Выборы перераздачи дописываются в конец руки, поэтому это последние redraft_picks карт.
        count = battle.redraft_picks.get(side, 0)
        picked = battle.hands[side][-count:] if count > 0 else []
    else:
        return []
    return [card.key for card in picked]


def _finish_draft(session):
    """Завершает драфт; выборы обеих сторон сохраняются в last_draft_picks до первого розыгрыша хода."""
    battle = session["battle"]
    session["last_draft_picks"] = {side: _draft_picks(battle, side) for side in ("player", "enemy")}
    if battle.draft_mode == "starting":
        battle.finish_starting_deal()
    else:
        battle.finish_redraft()


def _expire_sessions(now=None):
    now = time.time() if now is None else now
    expired = [
        session_id for session_id, session in _SESSIONS.items()
        if now - session["updated_at"] > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        session = _SESSIONS.pop(session_id)
        if _STORAGE is not None:
            _STORAGE.delete_deck_battle_session(session_id)
        for participant_id in session["participants"]:
            if _CHARACTER_SESSIONS.get(participant_id) == session_id:
                _CHARACTER_SESSIONS.pop(participant_id, None)


def start(
    player_profile,
    opponent_profile,
    *,
    opponent_is_bot=False,
    session_id=None,
    group_id=None,
):
    """Create or retrieve a session for the two accepted duel participants."""
    player_id = str(player_profile.get("id", player_profile.get("character_id", "")))
    opponent_id = str(opponent_profile.get("id", opponent_profile.get("character_id", "")))
    if not player_id or not opponent_id or player_id == opponent_id:
        raise ValueError("Некорректные участники боя")
    with _LOCK:
        _expire_sessions()
        existing_id = _CHARACTER_SESSIONS.get(player_id)
        if existing_id is not None:
            existing = _SESSIONS[existing_id]
            if existing["finished"] and player_id in existing["acknowledged"]:
                _CHARACTER_SESSIONS.pop(player_id, None)
            else:
                if opponent_id in existing["participants"]:
                    return existing_id
                raise ValueError("Персонаж уже участвует в другом бою")
        if not opponent_is_bot:
            existing_id = _CHARACTER_SESSIONS.get(opponent_id)
            if existing_id is not None:
                existing = _SESSIONS[existing_id]
                if player_id in existing["participants"]:
                    return existing_id
                raise ValueError("Соперник уже участвует в другом бою")

        player = _fighter(player_profile)
        enemy = _fighter(opponent_profile)
        player_cards = _deck(player_profile)
        enemy_cards = _deck(opponent_profile)
        battle = CardBattle(
            player,
            enemy,
            cards=player_cards,
            enemy_cards=enemy_cards,
            mage_mode=is_mage_profession(player.profession_type)
            or is_mage_profession(enemy.profession_type),
        )
        if len(player_cards) < DECK_SIZE or len(enemy_cards) < DECK_SIZE:
            raise ValueError("Для боя не хватает карт выбранного класса")

        session_id = str(session_id or uuid.uuid4().hex)
        participants = [player_id] if opponent_is_bot else [player_id, opponent_id]
        session = {
            "id": session_id,
            "group_id": str(group_id) if group_id is not None else None,
            "battle": battle,
            "participants": participants,
            "sides": {player_id: "player", opponent_id: "enemy"},
            "profiles": {"player": dict(player_profile), "enemy": dict(opponent_profile)},
            "bot_sides": {"enemy"} if opponent_is_bot else set(),
            "created_at": time.time(),
            "updated_at": time.time(),
            "finished": False,
            "outcome": None,
            "result_recorded": False,
            "acknowledged": set(),
            "phase": "",
            "deadline": 0.0,
            "timeouts": {"player": 0, "enemy": 0},
        }
        _SESSIONS[session_id] = session
        for participant_id in participants:
            _CHARACTER_SESSIONS[participant_id] = session_id
        if opponent_is_bot:
            _ai_draft(battle, "enemy")
        _update_deadline(session)
        _persist_session(session)
        return session_id


def active(character_id):
    with _LOCK:
        _expire_sessions()
        participant_id = str(character_id)
        session_id = _CHARACTER_SESSIONS.get(participant_id)
        if session_id is not None and participant_id in _SESSIONS[session_id]["acknowledged"]:
            return None
        return session_id


def _get_session(character_id, session_id):
    _expire_sessions()
    session = _SESSIONS.get(str(session_id))
    if session is None or str(character_id) not in session["participants"]:
        raise ValueError("Бой не найден или персонаж не участвует в нём")
    session["updated_at"] = time.time()
    return session, session["sides"][str(character_id)]


def _ai_draft(battle, side):
    if battle.draft_mode == "starting":
        while len(battle.hands[side]) < battle.STARTING_PICK_LIMIT:
            table = battle.table_for(side)
            if not table:
                break
            battle.choose_starting_card(side, random.choice(table).key)
    elif battle.draft_mode == "redraft":
        while battle.redraft_picks[side] < battle.redraft_pick_limit(side):
            table = battle.table_for(side)
            if not table:
                break
            battle.choose_redraft_card(side, random.choice(table).key)


def _prepare_next_round(session):
    battle = session["battle"]
    if battle.prepare_redraft():
        for side in session["bot_sides"]:
            _ai_draft(battle, side)
        return
    battle.begin_next_turn()
    for side in ("player", "enemy"):
        battle.draw_next_turn_card(side)
        battle.prepare_draw_choice(side)
    for side in session["bot_sides"]:
        choices = battle.draw_choices[side]
        if choices:
            battle.choose_draw_card(side, choices[0].key)


def _confirm_bot_sides(battle, bot_sides):
    for side in bot_sides:
        if battle.confirmed[side]:
            continue
        battle.selected[side] = []
        for card in list(battle.hands[side]):
            if battle.remaining_card_slots(side) <= 0:
                break
            if battle.can_select(side, card):
                battle.selected[side].append(card)
        battle.confirm_selection(side)


def _session_phase(session):
    battle = session["battle"]
    if session["finished"]:
        return "result"
    if battle.draft_mode:
        return "draft"
    if any(battle.draw_choices.values()):
        return "draw"
    return "planning"


def _update_deadline(session):
    phase = _session_phase(session)
    if phase == session["phase"]:
        return
    session["phase"] = phase
    timeout = {
        "draft": DRAFT_TIMEOUT_SECONDS,
        "draw": DRAW_TIMEOUT_SECONDS,
        "planning": TURN_TIMEOUT_SECONDS,
    }.get(phase, 0)
    session["deadline"] = time.time() + timeout if timeout else 0.0


def _process_timeouts(session):
    _update_deadline(session)
    if session["finished"] or not session["deadline"] or time.time() < session["deadline"]:
        return
    battle = session["battle"]
    phase = session["phase"]
    if phase == "draft":
        for side in ("player", "enemy"):
            _ai_draft(battle, side)
        if battle.draft_mode == "starting" or (
            battle.draft_mode == "redraft" and battle.current_draft_complete()
        ):
            _finish_draft(session)
    elif phase == "draw":
        for side in ("player", "enemy"):
            choices = battle.draw_choices[side]
            if choices:
                battle.choose_draw_card(side, choices[0].key)
    elif phase == "planning":
        for side in ("player", "enemy"):
            if side in session["bot_sides"] or battle.confirmed[side]:
                continue
            session["timeouts"][side] += 1
            if session["timeouts"][side] >= TURN_TIMEOUTS_BEFORE_SURRENDER:
                fighter = battle.player if side == "player" else battle.enemy
                fighter.hp = 0
                session["finished"] = True
                session["outcome"] = battle.outcome()
                break
            battle.selected[side] = []
            battle.confirm_selection(side)
        _confirm_bot_sides(battle, session["bot_sides"])
        _resolve_if_confirmed(session)
    _update_deadline(session)


def _resolve_if_confirmed(session):
    battle = session["battle"]
    if not all(battle.confirmed.values()):
        return
    battle.resolve_turn()
    session.pop("last_draft_picks", None)
    outcome = battle.outcome()
    if outcome is not None:
        session["finished"] = True
        session["outcome"] = outcome
        return
    _prepare_next_round(session)


def act(character_id, session_id, action, card_key=""):
    with _LOCK:
        session, side = _get_session(character_id, session_id)
        previous_phase = _session_phase(session)
        previous_turn = session["battle"].turn
        _process_timeouts(session)
        if session["finished"]:
            return snapshot(character_id, session_id)
        battle = session["battle"]
        if _session_phase(session) != previous_phase or battle.turn != previous_turn:
            return snapshot(character_id, session_id)
        if action == "pick_starting":
            battle.choose_starting_card(side, str(card_key))
            for bot_side in session["bot_sides"]:
                _ai_draft(battle, bot_side)
            if all(len(battle.hands[candidate]) >= battle.STARTING_PICK_LIMIT for candidate in ("player", "enemy")):
                _finish_draft(session)
        elif action == "pick_redraft":
            battle.choose_redraft_card(side, str(card_key))
            for bot_side in session["bot_sides"]:
                _ai_draft(battle, bot_side)
            if battle.current_draft_complete():
                _finish_draft(session)
        elif action == "select":
            if not battle.select_card(side, str(card_key)):
                raise ValueError("Эту карту нельзя выбрать сейчас")
        elif action == "deselect":
            if not battle.deselect_card(side, str(card_key)):
                raise ValueError("Выбранная карта не найдена")
        elif action == "burn":
            if not battle.burn_card(side, str(card_key)):
                raise ValueError("Сейчас нельзя сжечь эту карту")
        elif action == "confirm":
            battle.confirm_selection(side)
            _confirm_bot_sides(battle, session["bot_sides"])
            _resolve_if_confirmed(session)
        elif action == "choose_draw":
            if not battle.choose_draw_card(side, str(card_key)):
                raise ValueError("Карта для добора недоступна")
            for bot_side in session["bot_sides"]:
                choices = battle.draw_choices[bot_side]
                if choices:
                    battle.choose_draw_card(bot_side, choices[0].key)
        else:
            raise ValueError("Неизвестное действие боя")
        session["updated_at"] = time.time()
        _update_deadline(session)
        return snapshot(character_id, session_id)


def snapshot(character_id, session_id):
    with _LOCK:
        session, side = _get_session(character_id, session_id)
        _process_timeouts(session)
        _update_deadline(session)
        battle = session["battle"]
        fighter = battle.player if side == "player" else battle.enemy
        opponent = battle.enemy if side == "player" else battle.player
        opponent_side = "enemy" if side == "player" else "player"
        result = {
            "battle_id": session["id"],
            "group_id": session["group_id"],
            "phase": "result" if session["finished"] else (
                "draft" if battle.draft_mode else (
                    "draw" if battle.draw_choices[side] else "planning"
                )
            ),
            "seconds_left": max(0, int(session["deadline"] - time.time()))
            if session["deadline"] else 0,
            "timeout_count": session["timeouts"][side],
            "draft_mode": battle.draft_mode or "",
            "turn": battle.turn,
            "side": side,
            "fighter": {**_public_fighter(fighter), **_presentation_fields(battle, side)},
            "opponent": {**_public_fighter(opponent), **_presentation_fields(battle, opponent_side)},
            "hand": [_card_payload(card) for card in battle.hands[side]],
            "selected": [card.key for card in battle.selected[side]],
            "table": [_card_payload(card) for card in battle.table_for(side)],
            "draw_choices": [_card_payload(card) for card in battle.draw_choices[side]],
            "can_select": [
                card.key for card in battle.hands[side] if battle.can_select(side, card)
            ],
            "confirmed": battle.confirmed[side],
            "opponent_confirmed": battle.confirmed["enemy" if side == "player" else "player"],
            "opponent_draft_picks": _draft_picks(battle, "enemy" if side == "player" else "player"),
            "opponent_last_draft_picks": list(
                session.get("last_draft_picks", {}).get("enemy" if side == "player" else "player", [])
            ),
            "last_exchange": battle.last_exchange,
            "history": battle.history[-12:],
            "outcome": session["outcome"],
            "reward_card_keys": list(battle.reward_card_keys),
        }
        _persist_session(session)
        return result


def finish(character_id, session_id):
    with _LOCK:
        session, side = _get_session(character_id, session_id)
        if not session["finished"]:
            raise ValueError("Бой ещё не завершён")
        return {
            "battle_id": session["id"],
            "group_id": session["group_id"],
            "outcome": session["outcome"] if side == "player" else {
                "win": "loss", "loss": "win", "draw": "draw",
            }[session["outcome"]],
            "player": _public_fighter(session["battle"].player),
            "opponent": _public_fighter(session["battle"].enemy),
            "player_profile": session["profiles"]["player"],
            "opponent_profile": session["profiles"]["enemy"],
            "participants": list(session["participants"]),
            "reward_card_keys": list(session["battle"].reward_card_keys),
            "history": session["battle"].history,
            "stats": session["battle"].stats,
        }


def claim_results(session_id):
    with _LOCK:
        session = _SESSIONS.get(str(session_id))
        if session is None or not session["finished"]:
            raise ValueError("Завершённый бой не найден")
        already_recorded = session["result_recorded"]
        session["result_recorded"] = True
        result = {
            "already_recorded": already_recorded,
            "group_id": session["group_id"],
            "outcome": session["outcome"],
            "player_profile": session["profiles"]["player"],
            "opponent_profile": session["profiles"]["enemy"],
            "player": _public_fighter(session["battle"].player),
            "opponent": _public_fighter(session["battle"].enemy),
            "participants": list(session["participants"]),
            "reward_card_keys": list(session["battle"].reward_card_keys),
            "history": session["battle"].history,
            "stats": session["battle"].stats,
            "battle_record": build_battle_record(
                session["battle"], source="godot_deck_battle"
            ),
        }
        _persist_session(session)
        return result


def acknowledge(character_id, session_id):
    with _LOCK:
        session = _SESSIONS.get(str(session_id))
        participant_id = str(character_id)
        if session is None or participant_id not in session["participants"]:
            return
        session["acknowledged"].add(participant_id)
        if len(session["acknowledged"]) == len(session["participants"]):
            _SESSIONS.pop(str(session_id), None)
            if _STORAGE is not None:
                _STORAGE.delete_deck_battle_session(session_id)
            for current_id in session["participants"]:
                if _CHARACTER_SESSIONS.get(current_id) == str(session_id):
                    _CHARACTER_SESSIONS.pop(current_id, None)
        else:
            _persist_session(session)
