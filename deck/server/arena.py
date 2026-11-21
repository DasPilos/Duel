"""Бой на арене с NPC на сервере Колоды.

Сервер собирает ArenaBattle так же, как ArenaController.start в deck/ui/arena_overlay.py,
и выполняет команды игрока в том же порядке вызовов движка. Задержки интерфейса
(ENEMY_DELAY, STUN_DELAY, WALK_STEP_SECONDS) здесь не нужны: они меняют только показ.
Модуль не импортирует pygame и работает без базы данных.
"""

import random
import threading
import time
import uuid
from dataclasses import dataclass, field

from deck.combat.arena_battle import (
    ANCIENT_ENT_DECK,
    KOBOLD_DECK,
    MAX_CARDS_PER_TURN,
    MOVE_RANGE,
    NECROMANCER_DECK,
    SKELETON_DECK,
    SKELETON_GUARD_DECK,
    SKELETON_KING_DECK,
    SUMMON_RANGE,
    ArenaBattle,
    arena_center_for_tiles,
    arena_layout,
    card_role,
    create_ally_archer,
    create_ancient_ent,
    create_kobold,
    create_necromancer,
    create_skeleton,
    create_skeleton_guard,
    create_skeleton_king,
    hex_distance,
    hex_distance_to_center,
    spread_positions,
)
from deck.combat.card_database import (
    DECK_SIZE,
    cards_for_type,
    class_cards_for_type,
    expand_deck_card_keys,
    is_mage_profession,
)
from deck.combat.character_stats import BASE_STAT_VALUE
from deck.combat.fighter import Fighter
from deck.map_config import (
    ANCIENT_ENT_TILE,
    DUNGEON_ENTRANCE_BOUNDS,
    DUNGEON_ROOM_ORIGIN,
    DUNGEON_ROOM_SIZE,
    KOBOLD_CAMP2_TILE,
    KOBOLD_CAMP_SIZE,
    KOBOLD_CAMP_TILE,
    KOBOLD_SPAWN_TILE,
    MAP_HEIGHT_TILES,
    MAP_WIDTH_TILES,
    TILE_SIZE,
    tile_center,
)

SESSION_TTL_SECONDS = 60 * 60
BATTLE_ITEM_IDS = (4, 5, 6, 52)
COMMAND_TYPES = ("draft", "draw_choice", "select_target", "move", "play", "burn", "item", "teleport", "end_turn")
# Клетки могил, как GRAVEYARD_MOBS в deck/scenes/world_map_scene.py.
GRAVEYARD_TILES = {"skeleton": (34, 55), "necromancer": (48, 58)}
# Встречи арены, как _start_arena и start_*_battle в deck/scenes/world_map_scene.py.
# radius — расстояние в клетках, с которого Python запускает бой (_check_kobold_encounter).
ENCOUNTERS = {
    "kobold": {"tile": KOBOLD_SPAWN_TILE, "count": 1, "radius": 1},
    "kobold_camp": {"tile": KOBOLD_CAMP_TILE, "count": KOBOLD_CAMP_SIZE, "radius": 2},
    "kobold_camp_2": {"tile": KOBOLD_CAMP2_TILE, "count": KOBOLD_CAMP_SIZE, "radius": 2, "ally": True},
    "ancient_ent": {"tile": ANCIENT_ENT_TILE, "count": 1, "radius": 1, "boss": "ancient_ent"},
    "skeleton": {"tile": GRAVEYARD_TILES["skeleton"], "count": 1, "radius": 1, "boss": "skeleton"},
    "necromancer": {"tile": GRAVEYARD_TILES["necromancer"], "count": 1, "radius": 1, "boss": "necromancer"},
}


class ArenaError(ValueError):
    """Ошибка команды, которую можно показать игроку."""


# Комнаты подземелья с боем, как ArenaController.start(dungeon_room) в deck/ui/arena_overlay.py.
# Противник стоит на DUNGEON_ROOM_ORIGIN + DUNGEON_ACTOR_OFFSET. Комнаты 2 и 4 интерактивны и ведёт клиент.
DUNGEON_ACTOR_OFFSET = (8, 5)
DUNGEON_ROOM_BATTLES = {
    "dungeon_room_1": {"kind": "skeletons", "previous": None},
    "dungeon_room_3": {"kind": "skeletons_necromancer", "previous": "dungeon_room_1"},
    "dungeon_room_5": {"kind": "guards_king", "previous": "dungeon_room_3"},
}
DUNGEON_BATTLE_SIZES = {"skeletons": 2, "skeletons_necromancer": 3, "guards_king": 3}
# Ко входу: клетка перед порталом, как checkpoint_position и exit_dungeon в Python.
DUNGEON_APPROACH_TILE = (DUNGEON_ENTRANCE_BOUNDS[0] - 1, DUNGEON_ENTRANCE_BOUNDS[1] + DUNGEON_ENTRANCE_BOUNDS[3] // 2)
DUNGEON_APPROACH_POSITION = tuple(float(value) for value in tile_center(*DUNGEON_APPROACH_TILE))


@dataclass
class ArenaSession:
    session_id: str
    character_id: int
    source: str
    battle: ArenaBattle
    rng: random.Random
    reward_request_id: str
    created_at: float
    updated_at: float
    journal: list = field(default_factory=list)


def side_deck(card_keys, character_type):
    """Колода стороны как _side_deck в deck/scenes/duel_scene.py."""
    class_cards = class_cards_for_type(character_type)
    if not card_keys:
        return class_cards
    cards_by_key = {card.key: card for card in cards_for_type(character_type)}
    deck = [cards_by_key[key] for key in expand_deck_card_keys(card_keys) if key in cards_by_key]
    if len(deck) < DECK_SIZE:
        deck.extend([card for card in class_cards if card not in deck][:DECK_SIZE - len(deck)])
    return deck


def apply_profile(fighter, profile):
    """Профиль персонажа на бойца как DuelScene._apply_fighter_profile; боты здесь не участвуют."""
    fighter.set_profession(profile.get("type", "warrior"))
    fighter.name = profile["name"]
    fighter.level = profile["level"]
    fighter.xp = profile.get("xp", 0)
    fighter.stats = dict(profile["stats"])
    for stat_name in fighter.STAT_NAMES:
        default = 0 if stat_name in ("strength", "agility", "intuition") else BASE_STAT_VALUE
        fighter.stats.setdefault(stat_name, default)
    fighter.stat_points = profile.get("stat_points", 0)
    fighter.character_id = profile.get("id", profile.get("character_id"))
    fighter.set_talents(profile.get("talents", {}))
    fighter.hp = min(profile.get("hp", fighter.max_hp), fighter.max_hp)
    fighter.mp = min(profile.get("mp", fighter.max_mp), fighter.max_mp)


def build_player_fighter(profile, equipment=None, deck_keys=None):
    """Боец и колода игрока как build_player_fighter в deck/ui/arena_overlay.py."""
    fighter = Fighter(profile.get("name", "Герой"), int(profile.get("level", 1) or 1), profile.get("type", "warrior"))
    if "stats" in profile:
        try:
            apply_profile(fighter, profile)
        except (KeyError, TypeError, ValueError):
            pass
    fighter.hp = max(1, min(int(profile.get("hp", fighter.max_hp) or fighter.max_hp), fighter.max_hp))
    if profile.get("mp") is not None:
        fighter.mp = max(0, min(int(profile["mp"]), fighter.max_mp))
    fighter.equipment = dict(equipment or {})
    return fighter, side_deck(deck_keys, fighter.profession_type)


def _ally_start(rect, player_pos, taken, arena_center):
    """Свободная клетка рядом с игроком внутри арены, как ArenaController._ally_start."""
    left, top, width, height = rect
    px, py = player_pos
    radius = (min(width, height) - 1) / 2
    for dx, dy in ((0, 2), (0, -2), (2, 0), (-2, 0), (1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (0, -1), (1, 0), (-1, 0)):
        tile = (px + dx, py + dy)
        if (left <= tile[0] < left + width and top <= tile[1] < top + height
                and tile not in taken and hex_distance(player_pos, tile) <= SUMMON_RANGE
                and hex_distance_to_center(tile, arena_center) <= radius + 1e-9):
            return tile
    raise ArenaError("Нет свободной клетки рядом с игроком для союзника")


def _spawn_enemies(encounter, count, rect, player_pos, enemy_pos, center):
    """Враги встречи и их колода; порядок веток совпадает с ArenaController.start."""
    boss = encounter.get("boss")
    if boss == "ancient_ent":
        return create_ancient_ent(), ANCIENT_ENT_DECK, enemy_pos
    if boss == "skeleton":
        return create_skeleton(), SKELETON_DECK, enemy_pos
    if boss == "necromancer":
        return create_necromancer(), NECROMANCER_DECK, enemy_pos
    if count > 1:
        enemies = [create_kobold(name=f"Кобольд {index}") for index in range(1, count + 1)]
        return enemies, KOBOLD_DECK, spread_positions(rect, player_pos, enemy_pos, count, arena_center=center)
    return create_kobold(), KOBOLD_DECK, enemy_pos


def _dungeon_enemies(kind, rect, player_pos, enemy_pos, center):
    """Бойцы комнаты подземелья, их колода и колоды отдельных бойцов, как в ArenaController.start(dungeon_room)."""
    if kind == "skeletons":
        enemies = [create_skeleton("Скелет"), create_skeleton("Скелет")]
        decks = {}
        deck = SKELETON_DECK
    elif kind == "skeletons_necromancer":
        enemies = [create_skeleton("Скелет"), create_skeleton("Скелет"), create_necromancer()]
        decks = {2: NECROMANCER_DECK}
        deck = SKELETON_DECK
    else:
        enemies = [create_skeleton_guard(), create_skeleton_guard(), create_skeleton_king()]
        decks = {2: SKELETON_KING_DECK}
        deck = SKELETON_GUARD_DECK
    positions = spread_positions(rect, player_pos, enemy_pos, len(enemies), arena_center=center)
    return enemies, deck, positions, decks


def dungeon_actor_tile():
    left, top = DUNGEON_ROOM_ORIGIN
    return left + DUNGEON_ACTOR_OFFSET[0], top + DUNGEON_ACTOR_OFFSET[1]


def dungeon_room_contains(tile):
    left, top = DUNGEON_ROOM_ORIGIN
    width, height = DUNGEON_ROOM_SIZE
    return left <= tile[0] < left + width and top <= tile[1] < top + height


def _attach_journal(battle, journal):
    """ArenaBattle хранит только последние 8 строк журнала, полный журнал боя ведём отдельно."""
    original_log = battle._log

    def record(text):
        journal.append(text)
        original_log(text)

    battle._log = record


def start_session(profile, *, source, position_x, position_y, equipment=None, deck_keys=None, seed=None, now=None):
    """Новый бой против встречи source; игрок начинает с выбора стартовых карт."""
    dungeon = DUNGEON_ROOM_BATTLES.get(source)
    encounter = None if dungeon is not None else ENCOUNTERS.get(source)
    if dungeon is None and encounter is None:
        raise ArenaError("Этот противник не участвует в бою на арене")
    if dungeon is not None:
        count, ally, enemy_tile = DUNGEON_BATTLE_SIZES[dungeon["kind"]], False, dungeon_actor_tile()
    else:
        count, ally, enemy_tile = encounter["count"], encounter.get("ally", False), tuple(encounter["tile"])
    player_tile = (int(position_x // TILE_SIZE), int(position_y // TILE_SIZE))
    fighter, cards = build_player_fighter(profile, equipment, deck_keys)
    center = arena_center_for_tiles(player_tile, enemy_tile)
    decks = {}
    try:
        rect, player_pos, enemy_pos, center = arena_layout(
            player_tile, enemy_tile, MAP_WIDTH_TILES, MAP_HEIGHT_TILES,
            extra_fighters=count - 1 + int(ally), arena_center=center,
        )
        if dungeon is not None:
            enemies, enemy_deck, enemy_pos, decks = _dungeon_enemies(dungeon["kind"], rect, player_pos, enemy_pos, center)
        else:
            enemies, enemy_deck, enemy_pos = _spawn_enemies(encounter, count, rect, player_pos, enemy_pos, center)
        allies = []
        if ally:
            archer = create_ally_archer(fighter.level)
            taken = {tuple(player_pos), *(tuple(pos) for pos in (enemy_pos if count > 1 else [enemy_pos]))}
            allies.append((archer, side_deck(None, "archer"), _ally_start(rect, player_pos, taken, center)))
    except ValueError as error:
        raise ArenaError(str(error)) from error
    rng = random.Random(uuid.uuid4().int if seed is None else seed)
    battle = ArenaBattle(
        fighter, enemies, cards, rect, player_pos, enemy_pos,
        enemy_deck=enemy_deck, rng=rng, mage_mode=is_mage_profession(fighter.profession_type),
        allies=allies, arena_center=center, blocked_tiles=(), player_draft=True,
    )
    for index, deck in decks.items():
        battle.enemy_decks[battle.enemy_ids[index]] = deck
    current = time.time() if now is None else now
    journal = []
    _attach_journal(battle, journal)
    return ArenaSession(
        session_id=uuid.uuid4().hex,
        character_id=int(profile.get("id", 0) or 0),
        source=source,
        battle=battle,
        rng=rng,
        reward_request_id=uuid.uuid4().hex,
        created_at=current,
        updated_at=current,
        journal=journal,
    )


def _card_key(command):
    card_key = command.get("card_key")
    if not isinstance(card_key, str) or not card_key:
        raise ArenaError("Не указана карта")
    return card_key


def _hand_card(battle, command):
    index = command.get("card_index")
    hand = battle.engine.hands["player"]
    if not isinstance(index, int) or not 0 <= index < len(hand):
        raise ArenaError("Такой карты нет в руке")
    return hand[index]


def _tile(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ArenaError("Клетка должна быть парой координат")
    return int(value[0]), int(value[1])


def _optional_tile(value):
    return None if value is None else _tile(value)


def _optional_str(value):
    return None if value in (None, "") else str(value)


def _require_player_turn(battle):
    if battle.player_draft:
        raise ArenaError("Сначала выберите стартовые карты")
    if battle.engine.draw_choices["player"]:
        raise ArenaError("Сначала выберите карту из добора")
    if battle.is_over() or battle.active_side != "player" or not battle.player_can_act():
        raise ArenaError("Сейчас ход противника")


def cannot_play_reason(battle, card):
    """Причина отказа розыгрыша как _cannot_play_reason в deck/ui/arena_overlay.py."""
    if battle.cards_played >= MAX_CARDS_PER_TURN:
        return f"За ход можно разыграть не больше {MAX_CARDS_PER_TURN} карт"
    role = card_role(card)
    if role == "summon" and not battle.summon_tiles():
        return f"Нет свободных тайлов в радиусе {SUMMON_RANGE} для призыва"
    card_range = (card.effect_data or {}).get("range")
    if role == "enemy" and card_range is not None and not battle.card_targets(card):
        return f"Все враги слишком далеко (дальность {card_range})"
    return "Не хватает ресурса для этой карты"


def _do_draft(session, command, remove_item):
    battle = session.battle
    if not battle.player_draft:
        raise ArenaError("Стартовые карты уже выбраны")
    card_key = _card_key(command)
    if card_key not in {card.key for card in battle.engine.table_for("player")}:
        raise ArenaError("Этой карты нет среди стартовых")
    battle.choose_starting_card(card_key)
    return None


def _do_draw_choice(session, command, remove_item):
    battle = session.battle
    card_key = _card_key(command)
    if card_key not in {card.key for card in battle.engine.draw_choices["player"]}:
        raise ArenaError("Эту карту нельзя выбрать из добора")
    battle.choose_draw_card(card_key)
    return None


def _do_select_target(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    eid = str(command.get("target", ""))
    if eid not in battle.enemy_ids:
        raise ArenaError("Цель должна быть врагом арены")
    if battle.target != eid:
        battle.select_target(eid)
    return None


def _do_move(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    if battle.moved:
        raise ArenaError("За ход можно пойти только один раз")
    tile = _tile(command.get("tile"))
    path = battle.begin_player_movement(tile)
    if not path:
        if tile == battle.positions["player"]:
            return None
        raise ArenaError(f"Сюда не дойти: до {MOVE_RANGE} клеток по свободным клеткам арены")
    notice = None
    try:
        for step in path:
            if not battle.move_player_step(step):
                notice = "Перемещение остановлено"
                break
            if battle.last_move_interrupted:
                notice = "Перемещение прервано эффектом ловушки"
                break
    finally:
        battle.player_movement_path.clear()
    return notice


TILE_ROLES = ("summon", "tile")


def _enemy_attack(battle, card, enemy_id):
    """Щелчок по врагу без выбранного гекса: прицел по центру области, а для одиночного удара — сам враг."""
    if enemy_id not in battle.alive_enemies():
        raise ArenaError("Цель должна быть врагом арены")
    aim_tile = battle.aoe_aim_tile_for_target(card, battle.positions[enemy_id])
    if aim_tile is None:
        return enemy_id, None
    return None, aim_tile


def _do_play(session, command, remove_item):
    """Розыгрыш карты. Клетка призыва и тайловых карт идёт в tile (или destination), как в оверлее — в target."""
    battle = session.battle
    _require_player_turn(battle)
    card = _hand_card(battle, command)
    role = card_role(card)
    aim_tile = _optional_tile(command.get("aim_tile"))
    destination = _optional_tile(command.get("destination"))
    if role in TILE_ROLES:
        target = _optional_tile(command.get("tile"))
        if target is None:
            target = destination
        destination = None
    else:
        target = _optional_str(command.get("target"))
    if role == "enemy" and aim_tile is None and target is not None:
        target, aim_tile = _enemy_attack(battle, card, target)
    event = battle.play_card(card, target, destination=destination, aim_tile=aim_tile)
    if event is None:
        raise ArenaError(cannot_play_reason(battle, card))
    return None


def _do_burn(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    card = _hand_card(battle, command)
    if battle.engine.burned_this_turn["player"]:
        raise ArenaError("За ход можно сжечь только одну карту")
    if not battle.engine.burn_card("player", card.key):
        raise ArenaError("Не удалось сжечь карту")
    battle._log(f"{battle.player.name} сжигает карту «{card.name}»")
    return "Карта сожжена: восстановлено 15% максимального ресурса"


def _do_item(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    item_id = command.get("item_id")
    if not isinstance(item_id, int) or item_id not in BATTLE_ITEM_IDS:
        raise ArenaError("Этот предмет нельзя использовать в бою")
    target = _optional_str(command.get("target"))
    available, message = battle.can_use_battle_item(item_id, target)
    if not available:
        raise ArenaError(message)
    if remove_item is None:
        raise ArenaError("Инвентарь недоступен")
    remove_item(session.character_id, item_id, 1)
    success, message = battle.use_battle_item(item_id, target)
    if not success:
        raise ArenaError(message)
    return message


def _do_teleport(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    if not battle.teleport():
        raise ArenaError("Сейчас нельзя призвать телепорт")
    return None


def _do_end_turn(session, command, remove_item):
    battle = session.battle
    _require_player_turn(battle)
    if not battle.end_player_turn():
        raise ArenaError("Сейчас нельзя завершить ход")
    return None


_HANDLERS = {
    "draft": _do_draft,
    "draw_choice": _do_draw_choice,
    "select_target": _do_select_target,
    "move": _do_move,
    "play": _do_play,
    "burn": _do_burn,
    "item": _do_item,
    "teleport": _do_teleport,
    "end_turn": _do_end_turn,
}


def _pass_stunned_turns(battle):
    """Оглушённый игрок пропускает ход сам, как update() в интерфейсе (STUN_DELAY)."""
    while (not battle.is_over() and battle.active_side == "player"
           and battle.stunned("player") and battle.end_player_turn()):
        pass


def apply_command(session, command, *, remove_item=None, now=None):
    """Выполняет команду игрока и автоматические шаги. Возвращает заметку и новые строки журнала."""
    battle = session.battle
    if battle.is_over():
        raise ArenaError("Бой уже завершён")
    kind = str(command.get("type", ""))
    if kind not in COMMAND_TYPES:
        raise ArenaError("Неизвестная команда арены")
    log_start = len(session.journal)
    notice = _HANDLERS[kind](session, command, remove_item)
    _pass_stunned_turns(battle)
    session.updated_at = time.time() if now is None else now
    return {"notice": notice, "log": list(session.journal[log_start:])}


def _card_view(card, battle=None, index=None):
    data = card.effect_data or {}
    view = {
        "key": card.key,
        "name": card.name,
        "group": card.group_name,
        "effect": card.effect_type,
        "resource_type": card.resource_type,
        "resource_cost": card.resource_cost,
        "role": card_role(card),
        "range": data.get("range"),
        "aoe_radius": int(data.get("aoe_radius", 0)),
    }
    if index is not None:
        view["index"] = index
        view["playable"] = bool(battle.can_play_card(card))
        if view["playable"]:
            view["preview"] = _card_preview(battle, card)
        elif battle.player_can_act():
            view["reason"] = cannot_play_reason(battle, card)
    return view


def _tiles(tiles):
    return [[int(tile[0]), int(tile[1])] for tile in tiles]


def _card_preview(battle, card):
    """Куда можно выбрать цель разыгрываемой карты: то же, что valid_targets и valid_tiles в оверлее."""
    role = card_role(card)
    preview = {"targets": [], "aim_tiles": [], "tiles": [], "transfer_tiles": {}}
    if card.effect_type == "necromancer_transfer":
        targets = list(battle.card_targets(card))
        preview["targets"] = targets
        preview["transfer_tiles"] = {uid: _tiles(battle.transfer_tiles(uid, card)) for uid in targets}
    elif role == "enemy":
        preview["aim_tiles"] = _tiles(battle.card_aim_tiles(card))
    elif role in TILE_ROLES:
        if card.effect_type == "arena_wolf" or role == "tile":
            preview["tiles"] = _tiles(battle.card_tiles(card))
        else:
            preview["tiles"] = _tiles(battle.summon_tiles())
    else:
        preview["targets"] = list(battle.card_targets(card))
    return preview


def _side_of(battle, uid):
    if uid == "player":
        return "player"
    if uid in battle.ally_ids:
        return "ally"
    if uid in battle.enemy_ids:
        return "enemy"
    return "summon"


def _unit_view(battle, uid):
    fighter = battle.fighters[uid]
    return {
        "id": uid,
        "name": fighter.name,
        "side": _side_of(battle, uid),
        "hp": int(fighter.hp),
        "max_hp": int(fighter.max_hp),
        "mp": int(fighter.mp),
        "max_mp": int(fighter.max_mp),
        "position": list(battle.positions[uid]),
        "effects": [str(text) for text in battle.effects_for(uid)],
        "damage_dealt": int(battle.damage_dealt.get(uid, 0)),
    }


def _summon_view(battle, sid):
    summon = battle.summons[sid]
    hp = int(summon.get("hp", 0))
    return {
        "id": sid,
        "name": str(summon.get("name", "Призыв")),
        "side": "summon",
        "owner": summon.get("owner"),
        "kind": summon.get("kind"),
        "hp": hp,
        "max_hp": int(summon.get("max_hp", hp)),
        "mp": int(summon.get("mana", 0)),
        "max_mp": int(summon.get("max_mana", 0)),
        "position": list(battle.positions[sid]),
        "effects": [str(text) for text in battle.effects_for(sid)],
        "damage_dealt": int(battle.damage_dealt.get(sid, 0)),
    }


def _board_view(battle):
    left, top, width, height = battle.arena_rect
    return {
        "tiles": [[x, y] for y in range(top, top + height) for x in range(left, left + width)
                  if battle.in_arena((x, y))],
        "obstacles": _tiles(sorted(battle.blocked_tiles)),
        "barriers": _tiles(battle.barriers),
        "traps": _tiles(trap["tile"] for trap in battle.traps),
        "grave_soil": _tiles(battle.grave_soil),
    }


def _movement_view(battle):
    movable = battle.player_can_act() and not battle.moved and not battle.kneeling.get("player", 0)
    return {
        "can_move": bool(movable),
        "reachable": _tiles(battle.reachable_tiles("player")) if movable else [],
    }


def _phase(battle):
    if battle.player_draft:
        return "draft"
    if battle.is_over():
        return "result"
    if battle.engine.draw_choices["player"]:
        return "draw_choice"
    return "battle"


def session_view(session):
    """Состояние боя для клиента: всё, что нужно для отрисовки и выбора действий."""
    battle = session.battle
    engine = battle.engine
    units = [_unit_view(battle, "player")]
    units += [_unit_view(battle, uid) for uid in battle.alive_allies()]
    units += [_unit_view(battle, uid) for uid in battle.alive_enemies()]
    units += [_summon_view(battle, sid) for sid, summon in battle.summons.items() if summon.get("hp", 0) > 0]
    target = battle.target if battle.target in battle.fighters else None
    return {
        "session_id": session.session_id,
        "source": session.source,
        "phase": _phase(battle),
        "round": battle.round,
        "active_side": battle.active_side,
        "result": battle.result,
        "arena": {
            "rect": list(battle.arena_rect),
            "center": list(battle.arena_center),
            "radius": battle.arena_radius,
        },
        **_board_view(battle),
        "units": units,
        "hand": [_card_view(card, battle, index) for index, card in enumerate(engine.hands["player"])],
        "hand_limit": battle.hand_limit,
        "draft_cards": [_card_view(card) for card in engine.table_for("player")] if battle.player_draft else [],
        "draw_choices": [_card_view(card) for card in engine.draw_choices["player"]],
        "deck_left": len(engine.deck),
        "cards_played": battle.cards_played,
        "max_cards": MAX_CARDS_PER_TURN,
        "move_range": MOVE_RANGE,
        "summon_range": SUMMON_RANGE,
        "enemies_total": len(battle.enemy_ids),
        "moved": battle.moved,
        **_movement_view(battle),
        "burned_this_turn": bool(engine.burned_this_turn["player"]),
        "target": target,
        "target_distance": battle.distance() if target else None,
        "teleport_pending": battle.teleport_pending,
        "log": list(session.journal[-60:]),
    }


def npc_xp_type(name):
    """Тип противника для опыта, как _npc_xp_type в deck/scenes/world_map_scene.py."""
    normalized = str(name).casefold()
    if "кобольд" in normalized:
        return "kobold"
    if "древний ент" in normalized:
        return "ancient_ent"
    if "король скелетов" in normalized:
        return "skeleton_king"
    if "страж" in normalized:
        return "skeleton_guard"
    if "некромансер" in normalized:
        return "necromancer"
    if "скелет" in normalized:
        return "skeleton"
    return None


def finish_report(session):
    """Итог боя для наград: результат, убитые противники с типом опыта и остаток здоровья игрока."""
    battle = session.battle
    defeated = []
    for enemy_id in battle.enemy_ids:
        fighter = battle.fighters[enemy_id]
        npc_type = npc_xp_type(fighter.name)
        if fighter.hp <= 0 and npc_type is not None:
            defeated.append(npc_type)
    return {
        "result": battle.result,
        "encounter_id": session.source,
        "defeated_npc_types": defeated,
        "enemy_count": len(battle.enemy_ids),
        "player_hp": max(0, int(battle.player.hp)),
        "player_mp": max(0, int(battle.player.mp)),
        "reward_request_id": session.reward_request_id,
    }


class ArenaRegistry:
    """Бои арены в памяти процесса: один бой на персонажа, неактивные сессии удаляются через час."""

    def __init__(self, ttl_seconds=SESSION_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._sessions = {}
        self._by_character = {}

    def start(self, profile, *, source, position_x, position_y, equipment=None, deck_keys=None, seed=None, now=None):
        with self._lock:
            current = time.time() if now is None else now
            self._drop_expired(current)
            character_id = int(profile.get("id", 0) or 0)
            if character_id in self._by_character:
                raise ArenaError("У персонажа уже идёт бой на арене")
            session = start_session(
                profile, source=source, position_x=position_x, position_y=position_y,
                equipment=equipment, deck_keys=deck_keys, seed=seed, now=current,
            )
            self._sessions[session.session_id] = session
            self._by_character[character_id] = session.session_id
            return session

    def active(self, character_id, now=None):
        with self._lock:
            self._drop_expired(time.time() if now is None else now)
            session_id = self._by_character.get(int(character_id))
            return self._sessions.get(session_id) if session_id else None

    def command(self, character_id, session_id, command, *, remove_item=None, now=None):
        """Выполняет команду и возвращает состояние, а при конце боя — итог и освобождает персонажа."""
        with self._lock:
            current = time.time() if now is None else now
            self._drop_expired(current)
            session = self._sessions.get(session_id)
            if session is None or session.character_id != int(character_id):
                raise ArenaError("Бой на арене не найден или уже завершён")
            try:
                result = apply_command(session, command, remove_item=remove_item, now=current)
            except ArenaError:
                raise
            except Exception as error:
                self._remove(session)
                raise ArenaError("Бой на арене прерван из-за ошибки сервера") from error
            finished = finish_report(session) if session.battle.is_over() else None
            state = session_view(session)
            if finished is not None:
                self._remove(session)
            return {"result": result, "state": state, "finished": finished}

    def _remove(self, session):
        self._sessions.pop(session.session_id, None)
        if self._by_character.get(session.character_id) == session.session_id:
            del self._by_character[session.character_id]

    def _drop_expired(self, now):
        for session in list(self._sessions.values()):
            if session.updated_at + self._ttl <= now:
                self._remove(session)
