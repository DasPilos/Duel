"""Пошаговый бой на гексагональной арене посреди глобальной карты.

Ход стороны: одно перемещение (до MOVE_RANGE клеток по соседним клеткам) и до
MAX_CARDS_PER_TURN карт. Эффекты карт игрока считает обычный CardBattle; карты
кобольдов наносят фиксированный урон и не требуют ресурсов.

CardBattle рассчитан на бой один на один, поэтому в движке «enemy» — это текущая
цель, а «player» — тот член команды игрока, который сейчас действует или получает
эффект. Состояние эффектов остальных бойцов хранится отдельно и подставляется в
движок при смене цели (select_target) или действующего союзника (_as_player).

Призванные существа (голем, громовая туча) — отдельные фигуры на арене со своим
ходом после хода игрока и союзников.
"""

import math
import random
from collections import deque
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import dataclass

from kaloda.combat.card_battle import CardBattle, card_deals_damage
from kaloda.combat.fighter import Fighter
from kaloda.combat.mechanics import get_dodge_chance


ARENA_SIZE = 11
MOVE_RANGE = 3
MAX_CARDS_PER_TURN = 2
ENEMY_CARDS_PER_TURN = 1
BATTLE_ITEM_COOLDOWN_ROUNDS = 3
STARTING_HAND_SIZE = 5
MAX_HAND_SIZE = 7
KOBOLD_MAX_HP = 20
ANCIENT_ENT_NAME = "ДРЕВНИЙ ЕНТ"
ANCIENT_ENT_MAX_HP = 140
ANCIENT_ENT_MAX_MP = 50
WOLF_MAX_HP = 12
SKELETON_MAX_HP = 45
SKELETON_MAX_MP = 25
NECROMANCER_MAX_HP = 35
NECROMANCER_MAX_MP = 55
SKELETON_GUARD_MAX_HP = 60
SKELETON_GUARD_MAX_MP = 20
SKELETON_KING_MAX_HP = 340
SKELETON_KING_MAX_MP = 130
NECROMANCER_MIN_RANGE = 3
NECROMANCER_MAX_RANGE = 4
BONE_DOG_MAX_HP = 22
BONE_DOG_MAX_MP = 10
SKULL_MAX_HP = 10
SUMMON_RANGE = 2
FOREST_SPIRIT_RANGE = 3
FOREST_SPIRIT_HP = 30
GOLEM_ATTACK_RANGE = 1
CLOUD_STRIKE_RANGE = 1
ALLY_ARCHER_NAME = "Ельпачино Фред"

# Состояние эффектов одной стороны CardBattle, которое у каждого бойца своё
SWAPPED_STATE = (
    "bleeds", "delayed_heals", "delayed_hp_loss", "invulnerability_targets", "invulnerable",
    "mage_clouds", "mage_damage_bonuses", "mage_delayed_statuses", "mage_freeze", "mage_golems",
    "mage_pending_effects", "mage_reactive_blessings", "mage_shield_effects", "mage_shields",
    "mage_statuses", "mage_stuns", "phys_buffs", "phys_shields", "phys_spirits", "phys_state",
    "poisons", "regenerations", "skip_next_turn", "skip_turn_armed",
)

SUMMON_EFFECTS = {"mage_golem", "mage_cloud", "necromancer_summon"}
HOSTILE_EFFECTS = {
    "damage_debuff", "mage_damage_debuff", "mage_stun_status",
    "arena_knockback", "arena_bonebreaker",
    "arena_dreadful_corruption",
    "necromancer_defense_curse", "necromancer_green_flame",
}
TILE_EFFECTS = {
    "arena_trap", "arena_barrier", "arena_dash", "arena_teleport",
    "necromancer_trap", "necromancer_barrier", "necromancer_grave_soil",
}
SELF_EFFECTS = {
    "mage_restore_mana", "mage_hp_for_mana", "mage_mana_regen_buff", "mage_draw",
    "damage_recoil", "guard", "team_revive", "arena_resource_recovery",
    "arena_unstable_elixir", "necromancer_summon_search",
    "necromancer_resource_sacrifice", "necromancer_bargain",
}
# Карты, которые оплачиваются здоровьем заклинателя, действуют только на него самого
SELF_COST_KEYS = ("hp_percent", "hp_current_percent", "sacrifice_max_hp_percent")
HEAL_EFFECTS = {"heal", "heal_over_time", "mage_heal_missing_hp"}


def card_role(card):
    """Цель карты: enemy — враг, ally — игрок или союзник, self — только сам, summon — свободный тайл."""
    data = card.effect_data or {}
    if card.effect_type in TILE_EFFECTS:
        return "tile"
    if card.effect_type == "arena_wolf":
        return "summon"
    if card.effect_type in SUMMON_EFFECTS or data.get("summon_spirit"):
        return "summon"
    if card.effect_type in SELF_EFFECTS:
        return "self"
    if (card_deals_damage(card) or card.effect_type in HOSTILE_EFFECTS
            or card.effect_type == "damage" or data.get("poison") or data.get("entangle")
            or data.get("poison_extraction") or data.get("poison_outgoing_damage_percent")):
        return "enemy"
    if any(key in data for key in SELF_COST_KEYS):
        return "self"
    return "ally"


@dataclass(frozen=True)
class CreatureCard:
    key: str
    name: str
    damage: int = 0
    stun_turns: int = 0
    description: str = ""
    range: int = 1
    aoe_radius: int = 0
    heal_percent: float = 0.0
    heal_threshold: float = 0.0
    cooldown_turns: int = 0
    root_turns: int = 0
    summon_wolf: bool = False
    summon_kind: str = ""
    aoe_center_self: bool = False
    teleport_behind: bool = False
    damage_taken_bonus_percent: int = 0
    heal_allies_percent_of_caster_hp: float = 0.0
    sacrifice_heal_percent: float = 0.0
    sacrifice_threshold: float = 0.0
    protect_king: bool = False
    shield_next_damage_percent: int = 0
    teleport_to_king_below_hp_percent: int = 0
    heal_allies_percent_of_target_max_hp: float = 0.0
    trap_damage: int = 0
    trap_aoe_radius: int = 0
    trap_damage_taken_bonus_percent: int = 0
    teleport_farthest_below_hp_percent: int = 0
    banner_duration: int = 0
    banner_aura_radius: int = 0
    kneel_radius: int = 0
    execute_below_hp_percent: int = 0


ANCIENT_ENT_DECK = (
    CreatureCard("ent_strike", "Удар", damage=18, range=1),
    CreatureCard("ent_aoe", "Удар корнями", damage=12, range=1, aoe_radius=2),
    CreatureCard("ent_heal", "Лечение", heal_percent=0.10, heal_threshold=0.25, cooldown_turns=2),
    CreatureCard("ent_roots", "Корни", range=3, cooldown_turns=4, root_turns=2),
    CreatureCard("ent_wolf", "Призыв волка", range=1, summon_wolf=True),
)
WOLF_DECK = (CreatureCard("wolf_bite", "Укус", damage=5, range=1),)
SKELETON_DECK = (
    CreatureCard("skeleton_strike", "Удар", damage=9, range=1),
    CreatureCard("skeleton_teleport", "Прыжок за спину", range=4, stun_turns=1,
                 cooldown_turns=4, teleport_behind=True),
    CreatureCard("skeleton_mark", "Уязвимость", range=3, damage_taken_bonus_percent=50),
    CreatureCard("skeleton_sweep", "Костяной вихрь", damage=12, range=1, aoe_radius=1,
                 aoe_center_self=True),
)
NECROMANCER_DECK = (
    CreatureCard("necromancer_skull", "Призыв черепа", range=1, cooldown_turns=4,
                 summon_kind="skull"),
    CreatureCard("necromancer_skeleton", "Призыв скелета", range=1, cooldown_turns=4,
                 summon_kind="skeleton"),
    CreatureCard("necromancer_bone_dog", "Призыв костяного пса", range=1,
                 cooldown_turns=4, summon_kind="bone_dog"),
    CreatureCard("necromancer_roots", "Корни", range=5, root_turns=2),
    CreatureCard("necromancer_heal", "Лечение союзников",
                 heal_allies_percent_of_caster_hp=0.25),
)
SKELETON_GUARD_DECK = (
    CreatureCard("guard_spear", "Удар копьём", damage=9, range=2),
    CreatureCard("guard_for_king", "За короля!", range=4, protect_king=True),
    CreatureCard("guard_shield_bash", "Удар щитом", damage=10, range=1, stun_turns=1),
    CreatureCard("guard_protect", "Защитить любой ценой", range=None,
                 teleport_to_king_below_hp_percent=30, cooldown_turns=10**6),
)
SKELETON_KING_DECK = (
    CreatureCard("king_crushing", "Сокрушение", damage=18, range=1, aoe_radius=1),
    CreatureCard("king_guard", "Стража!", range=2, summon_kind="skeleton_guard", cooldown_turns=12),
    CreatureCard("king_morale", "Поднять боевой дух", range=None,
                 heal_allies_percent_of_target_max_hp=0.20,
                 shield_next_damage_percent=15),
    CreatureCard("king_grave", "Могила странника", range=2, trap_damage=20,
                 trap_aoe_radius=1, trap_damage_taken_bonus_percent=35),
    CreatureCard("king_trick", "Королевская хитрость", damage=30, range=None,
                 teleport_farthest_below_hp_percent=40, cooldown_turns=10**6),
    CreatureCard("king_banner", "Королевское знамя", range=2, banner_duration=6,
                 banner_aura_radius=2, cooldown_turns=7),
    CreatureCard("king_kneel", "На колени перед королём", range=None,
                 kneel_radius=2, stun_turns=2, cooldown_turns=8),
    CreatureCard("king_verdict", "Королевский вердикт", damage=50, range=1,
                 execute_below_hp_percent=10, cooldown_turns=10**6),
)
BONE_DOG_DECK = (
    CreatureCard("bone_dog_bite", "Удар", damage=7, range=1),
    CreatureCard("bone_dog_sacrifice", "Жертвенное лечение",
                 sacrifice_heal_percent=0.5, sacrifice_threshold=0.15),
)
SKULL_EXPLOSION = CreatureCard(
    "skull_explosion", "Взрыв черепа", damage=14, range=2, aoe_radius=2,
    aoe_center_self=True,
)


KOBOLD_DECK = (
    CreatureCard("kobold_strike", "Удар", damage=5, description="5 урона"),
    CreatureCard("kobold_heavy_strike", "Сильный удар", damage=8, description="8 урона"),
    CreatureCard("kobold_daze", "Ошеломление", stun_turns=1, description="Оглушает противника на 1 ход"),
    CreatureCard("kobold_sharp_branch", "Острый сук", damage=4, description="4 урона"),
    CreatureCard("kobold_split", "Раскол", damage=9, description="9 урона"),
)


def create_kobold(level=1, name="Кобольд"):
    kobold = Fighter(name, level, "warrior")
    kobold.max_hp = KOBOLD_MAX_HP
    kobold.hp = KOBOLD_MAX_HP
    return kobold


def create_ancient_ent():
    ent = Fighter(ANCIENT_ENT_NAME, 1, "mage")
    ent.max_hp = ANCIENT_ENT_MAX_HP
    ent.hp = ANCIENT_ENT_MAX_HP
    ent.max_mp = ANCIENT_ENT_MAX_MP
    ent.mp = ANCIENT_ENT_MAX_MP
    return ent


def create_skeleton(name="Скелет"):
    skeleton = Fighter(name, 1, "mage")
    skeleton.max_hp = skeleton.hp = SKELETON_MAX_HP
    skeleton.max_mp = skeleton.mp = SKELETON_MAX_MP
    skeleton.temporary_dodge_chance_modifier = 20
    return skeleton


def create_necromancer():
    necromancer = Fighter("Некромансер", 1, "mage")
    necromancer.max_hp = necromancer.hp = NECROMANCER_MAX_HP
    necromancer.max_mp = necromancer.mp = NECROMANCER_MAX_MP
    return necromancer


def create_skeleton_guard():
    guard = Fighter("Скелет-страж", 1, "mage")
    guard.max_hp = guard.hp = SKELETON_GUARD_MAX_HP
    guard.max_mp = guard.mp = SKELETON_GUARD_MAX_MP
    guard.incoming_damage_reduction_percent = 20
    return guard


def create_skeleton_king():
    king = Fighter("Король скелетов", 1, "mage")
    king.max_hp = king.hp = SKELETON_KING_MAX_HP
    king.max_mp = king.mp = SKELETON_KING_MAX_MP
    return king


def create_bone_dog():
    dog = Fighter("Костяной пёс", 1, "warrior")
    dog.max_hp = dog.hp = BONE_DOG_MAX_HP
    dog.max_mp = dog.mp = BONE_DOG_MAX_MP
    dog.arena_move_range = 4
    return dog


def create_skull():
    skull = Fighter("Череп", 1, "mage")
    skull.max_hp = skull.hp = SKULL_MAX_HP
    skull.max_mp = skull.mp = 0
    return skull


def create_ally_archer(level=1, name=ALLY_ARCHER_NAME):
    return Fighter(name, max(1, int(level)), "archer")


def hex_distance(a, b):
    """Расстояние на сетке odd-r: нечётные строки сдвинуты вправо."""
    aq = a[0] - (a[1] - (a[1] & 1)) // 2
    bq = b[0] - (b[1] - (b[1] & 1)) // 2
    dq, dr = aq - bq, a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def hex_neighbors(tile):
    """Соседи по рёбрам гекса: СВ, В, ЮВ, ЮЗ, З, СЗ."""
    x, y = tile
    shift = y & 1
    return ((x + shift, y - 1), (x + 1, y), (x + shift, y + 1),
            (x + shift - 1, y + 1), (x - 1, y), (x + shift - 1, y - 1))


def axial_coordinates(tile):
    x, y = tile
    return x - (y - (y & 1)) // 2, y


def arena_center_for_tiles(player_tile, enemy_tile):
    """Return the nearest actual hex cell to the midpoint between the combatants."""
    player_q, player_r = axial_coordinates(player_tile)
    enemy_q, enemy_r = axial_coordinates(enemy_tile)
    midpoint_q, midpoint_r = (player_q + enemy_q) / 2, (player_r + enemy_r) / 2
    q_values = {math.floor(midpoint_q), math.ceil(midpoint_q)}
    r_values = {math.floor(midpoint_r), math.ceil(midpoint_r)}
    return min(
        ((q, r) for q in q_values for r in r_values),
        key=lambda center: (
            (center[0] - midpoint_q) ** 2
            + (center[0] - midpoint_q) * (center[1] - midpoint_r)
            + (center[1] - midpoint_r) ** 2,
            center,
        ),
    )


def hex_distance_to_center(tile, center):
    q, r = axial_coordinates(tile)
    dq, dr = q - center[0], r - center[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def _hex_tiles(center, radius):
    cq, cr = center
    for r in range(math.floor(cr - radius) - 1, math.ceil(cr + radius) + 2):
        for q in range(math.floor(cq - radius) - 1, math.ceil(cq + radius) + 2):
            if max(abs(q - cq), abs(r - cr), abs(q + r - cq - cr)) <= radius + 1e-9:
                yield q + (r - (r & 1)) // 2, r


def _fit_hex_center(center, radius, map_w, map_h):
    """Move a battlefield center inward only as much as needed to keep its hex on-map."""
    limit = 2 * math.ceil(radius + 1)
    offsets = range(-limit, limit + 1)
    candidates = sorted(
        ((center[0] + dq, center[1] + dr) for dq in offsets for dr in offsets),
        key=lambda candidate: (
            (candidate[0] - center[0]) ** 2
            + (candidate[0] - center[0]) * (candidate[1] - center[1])
            + (candidate[1] - center[1]) ** 2
        ),
    )
    for candidate in candidates:
        tiles = tuple(_hex_tiles(candidate, radius))
        if tiles and all(0 <= x < map_w and 0 <= y < map_h for x, y in tiles):
            return candidate
    raise ValueError("Арена не помещается на карте")


def _rect_for_hex(center, tiles, map_w, map_h, size):
    xs, ys = zip(*tiles)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x - min_x + 1 > size or max_y - min_y + 1 > size:
        raise ValueError("Гексагональная арена превышает заданный размер")
    center_x = center[0] + center[1] / 2
    left = math.floor(center_x - (size - 1) / 2)
    top = math.floor(center[1] - (size - 1) / 2)
    left = max(0, min(map_w - size, max(min_x, min(left, max_x - size + 1))))
    top = max(0, min(map_h - size, max(min_y, min(top, max_y - size + 1))))
    return left, top, size, size


def _edge_positions(rect, tiles, center, player_tile, enemy_tile):
    boundary = [tile for tile in tiles
                if hex_distance_to_center(tile, center) == max(hex_distance_to_center(t, center) for t in tiles)]

    def vector(tile):
        q, r = axial_coordinates(tile)
        return q + r / 2 - center[0] - center[1] / 2, (r - center[1]) * math.sqrt(3) / 2

    player_vector = vector(player_tile)
    enemy_vector = vector(enemy_tile)
    direction = (enemy_vector[0] - player_vector[0], enemy_vector[1] - player_vector[1])
    if direction == (0, 0):
        direction = (1, 0)
    player_vector, enemy_vector = (-direction[0], -direction[1]), direction

    def farthest(direction, exclude=None):
        return max((tile for tile in boundary if tile != exclude),
                   key=lambda tile: vector(tile)[0] * direction[0] + vector(tile)[1] * direction[1])

    enemy_pos = farthest(enemy_vector)
    player_pos = farthest(player_vector, exclude=enemy_pos)
    return player_pos, enemy_pos


def arena_layout(player_tile, enemy_tile, map_w, map_h, size=ARENA_SIZE, *, extra_fighters=0,
                 arena_center=None):
    """Build a centered hex arena; each extra combatant adds one ring of hexes."""
    radius = (size - 1) // 2 + extra_fighters
    size = radius * 2 + 1
    if size > min(map_w, map_h):
        raise ValueError("Арена не помещается на карте")
    center = arena_center or arena_center_for_tiles(player_tile, enemy_tile)
    center = _fit_hex_center(center, radius, map_w, map_h)
    tiles = tuple(_hex_tiles(center, radius))
    rect = _rect_for_hex(center, tiles, map_w, map_h, size)
    player_pos, enemy_pos = _edge_positions(rect, tiles, center, player_tile, enemy_tile)
    return rect, player_pos, enemy_pos, center


def spread_positions(rect, player_pos, enemy_pos, count, gap=2, arena_center=None):
    """Расставить врагов у края гексагональной арены."""
    left, top, width, height = rect
    vertical_edge = player_pos[1] == enemy_pos[1]
    offsets = [0]
    for step in range(1, count):
        offsets.append(((step + 1) // 2) * gap * (1 if step % 2 else -1))
    candidates = [
        (x, y) for y in range(top, top + height) for x in range(left, left + width)
        if arena_center is None
        or hex_distance_to_center((x, y), arena_center) <= (min(width, height) - 1) / 2 + 1e-9
    ]
    used = set()
    positions = []
    for offset in offsets[:count]:
        if vertical_edge:
            suggested = (enemy_pos[0], max(top, min(top + height - 1, enemy_pos[1] + offset)))
        else:
            suggested = (max(left, min(left + width - 1, enemy_pos[0] + offset)), enemy_pos[1])
        available = [tile for tile in candidates if tile not in used]
        if arena_center is not None:
            edge_distance = max(hex_distance_to_center(tile, arena_center) for tile in candidates)
            boundary = [tile for tile in available if hex_distance_to_center(tile, arena_center) == edge_distance]
            available = boundary or available
        position = min(available, key=lambda tile: hex_distance(suggested, tile))
        positions.append(position)
        used.add(position)
    return positions


class ArenaBattle:
    def __init__(self, player, enemy, player_cards, arena_rect, player_pos, enemy_pos,
                 enemy_deck=KOBOLD_DECK, rng=None, mage_mode=False, hand_limit=MAX_HAND_SIZE, allies=None,
                 arena_center=None, blocked_tiles=(), player_draft=False):
        """allies — список (боец, колода, стартовая клетка) союзников под управлением ИИ."""
        self.rng = random if rng is None else rng
        enemies = list(enemy) if isinstance(enemy, (list, tuple)) else [enemy]
        enemy_positions = ([tuple(pos) for pos in enemy_pos]
                           if enemy_pos and isinstance(enemy_pos[0], (list, tuple)) else [tuple(enemy_pos)])
        if len(enemies) != len(enemy_positions):
            raise ValueError("Каждому врагу нужна своя стартовая клетка")
        self.enemy_ids = ["enemy"] + [f"enemy_{index}" for index in range(2, len(enemies) + 1)]
        self.player = player
        self.fighters = {"player": player, **dict(zip(self.enemy_ids, enemies))}
        self.target = "enemy"
        self.engine = CardBattle(player, enemies[0], cards=[], rng=self.rng, enemy_cards=[], mage_mode=mage_mode)
        hand_limit = min(int(hand_limit), MAX_HAND_SIZE)
        if hand_limit < 0:
            raise ValueError("Лимит руки не может быть отрицательным")
        self.engine.MAX_HAND_SIZE = hand_limit
        self.hand_limit = self.engine.hand_limit_for("player")
        self._swapped = [attr for attr in SWAPPED_STATE
                         if isinstance(getattr(self.engine, attr, None), dict) and "enemy" in getattr(self.engine, attr)]
        self._fresh = {attr: deepcopy(getattr(self.engine, attr)["enemy"]) for attr in self._swapped}
        self._fresh_player = {attr: deepcopy(getattr(self.engine, attr)["player"]) for attr in self._swapped}
        self._stash = {eid: deepcopy(self._fresh) for eid in self.enemy_ids[1:]}
        self.engine.deck = list(player_cards)
        self.rng.shuffle(self.engine.deck)
        self.player_draft = bool(player_draft)
        self.player_draw_choice = bool(player_draft)
        if self.player_draft:
            self.engine.STARTING_TABLE_SIZE = len(self.engine.deck)
            self.engine._prepare_starting_table()
        else:
            self.engine.hands["player"] = [card for _ in range(STARTING_HAND_SIZE)
                                           if (card := self.engine._draw_card("player")) is not None]
        self.enemy_deck = tuple(enemy_deck)
        self.enemy_decks = {eid: self.enemy_deck for eid in self.enemy_ids}
        self.enemy_card_last_used = {eid: {} for eid in self.enemy_ids}
        self.enemy_summons = set()
        self.enemy_summon_kinds = {}
        self.wolf_barrier = None
        self.arena_rect = tuple(arena_rect)
        self.arena_center = (tuple(arena_center) if arena_center is not None else
                             arena_center_for_tiles(player_pos, enemy_positions[0]))
        self.arena_radius = (min(self.arena_rect[2:]) - 1) / 2
        self.positions = {"player": tuple(player_pos), **dict(zip(self.enemy_ids, enemy_positions))}
        self.movement_events = []
        player_q, player_r = axial_coordinates(self.positions["player"])
        enemy_q, enemy_r = axial_coordinates(self.positions[self.enemy_ids[0]])
        self._summon_front_axis = (
            player_q, player_r, enemy_q - player_q, enemy_r - player_r,
        )
        self.blocked_tiles = {tuple(tile) for tile in blocked_tiles}
        self.traps = []
        self.barriers = {}
        self.grave_soil = {}
        self.slowed_until = {}
        self.green_flame = {}
        self.defense_curses = {}
        self.necrotism_gain_bonus = {}
        self.protection_effects = {}
        self.temporary_damage_taken = {}
        self.arena_corrosion = {}
        self.next_summon_bonus = None
        self.king_flags = []
        self.broken_bones = {}
        self.kneeling = {}
        self.roots = {uid: 0 for uid in self.positions}
        self.damage_dealt = {"player": 0, **{eid: 0 for eid in self.enemy_ids}}
        self.log = []
        # Сообщения о добранных картах: {"round", "cards", "hand_full", "start"}
        self.draw_events = [{"round": 1, "cards": [card.name for card in self.engine.hands["player"]],
                             "hand_full": False, "start": True}]
        self.result = None
        self.teleport_pending = False
        self.last_battle_item_round = None
        self.stun_immune = {"player": False}
        self.summons = {}
        self._summon_counter = 0
        self._death_rewards_applied = set()
        self.ally_ids = []
        self.ally_cards = {}
        self._ally_stash = {}
        for index, (fighter, cards, pos) in enumerate(allies or [], start=1):
            self._add_ally("ally" if index == 1 else f"ally_{index}", fighter, cards, pos)
        self.round = 0
        self.active_side = "draft" if self.player_draft else "player"
        self.moved = False
        self.cards_played = 0
        self.player_movement_path = []
        self._player_movement_steps = 0
        self.last_move_interrupted = False
        if self.player_draft:
            self._initialize_boss_state()
        else:
            self._start_round()
            self._initialize_boss_state()
        self._refresh_king_auras()

    def _initialize_boss_state(self):
        self._set_boss_mana()
        if self.enemy.name == ANCIENT_ENT_NAME:
            self._spawn_enemy_wolf("enemy")

    def _set_boss_mana(self):
        if self.enemy.name == ANCIENT_ENT_NAME:
            self.enemy.mp = ANCIENT_ENT_MAX_MP
        elif self.enemy.name in ("Скелет", "Некромансер"):
            self.enemy.mp = self.enemy.max_mp

    def choose_starting_card(self, card_key):
        if not self.player_draft:
            return False
        self.engine.choose_starting_card("player", card_key)
        if len(self.engine.hands["player"]) < self.engine.STARTING_PICK_LIMIT:
            return True
        table = self.engine.table_for("player")
        self.rng.shuffle(table)
        self.engine.hands["player"].extend(table[:self.engine.STARTING_RANDOM_CARDS])
        del table[:self.engine.STARTING_RANDOM_CARDS]
        self.engine._deck_for("player").extend(table)
        table.clear()
        self.engine.draft_mode = None
        self.engine._start_turn(draw_cards=False)
        self.player_draft = False
        self.round = 1
        self.active_side = "player"
        self._set_boss_mana()
        self.draw_events[0]["cards"] = [card.name for card in self.engine.hands["player"]]
        return True

    def _add_ally(self, aid, fighter, cards, pos):
        self.ally_ids.append(aid)
        self.fighters[aid] = fighter
        self.positions[aid] = tuple(pos)
        deck = list(cards)
        self.rng.shuffle(deck)
        self.ally_cards[aid] = {"deck": deck, "hand": [], "discard": []}
        for _ in range(STARTING_HAND_SIZE):
            self._ally_draw(aid)
        self._ally_stash[aid] = deepcopy(self._fresh_player)
        self.roots[aid] = 0
        self.damage_dealt[aid] = 0
        self.stun_immune[aid] = False
        if getattr(fighter, "unique_resource_type", None) not in (None, "mana"):
            fighter.unique_resource_current = int(fighter.unique_resource_max * 0.15)

    def _king_id(self):
        return next(
            (eid for eid in self.alive_enemies()
             if self.fighters[eid].name == "Король скелетов"),
            None,
        )

    def _refresh_king_auras(self):
        for uid, fighter in self.fighters.items():
            fighter.arena_move_range_bonus = int(
                getattr(fighter, "_talent_effects", {}).get("move_range", 0)
            )
            fighter.outgoing_damage_bonus_percent = 0
            fighter.incoming_damage_reduction_percent = (
                20 if fighter.name == "Скелет-страж" else 0
            )
            fighter.incoming_damage_bonus_percent = (
                30 if self.defense_curses.get(uid, 0) > self.round else 0
            ) + sum(
                bonus for bonus, remaining in self.temporary_damage_taken.get(uid, ())
                if remaining > 0
            )
            protection = self.protection_effects.get(uid)
            if protection and protection["expires_round"] > self.round:
                fighter.incoming_damage_reduction_percent += protection["percent"]
            if self.defense_curses.get(uid, 0) > self.round:
                fighter.incoming_damage_reduction_percent -= 30
        king_id = self._king_id() if hasattr(self, "enemy_ids") else None
        for sid, summon in self.summons.items():
            if summon.get("kind") != "necromancer_familiar":
                continue
            owner = summon.get("owner", "player")
            allies = [owner, *self.alive_allies()] if owner == "player" else [owner]
            for uid in allies:
                if uid in self.fighters and self.dist(sid, uid) <= 2:
                    self.fighters[uid].outgoing_damage_bonus_percent += 20
        if king_id is not None:
            king_tile = self.positions[king_id]
            for eid in self.alive_enemies():
                if hex_distance(self.positions[eid], king_tile) <= 2:
                    fighter = self.fighters[eid]
                    fighter.arena_move_range_bonus = 1
                    fighter.outgoing_damage_bonus_percent += 10
                    fighter.incoming_damage_reduction_percent += 10
        active_flags = [
            flag for flag in self.king_flags
            if flag["expires_round"] > self.round
        ]
        self.king_flags = active_flags
        for flag in active_flags:
            for uid, fighter in self.fighters.items():
                if hex_distance(self.positions[uid], flag["tile"]) > flag["radius"]:
                    continue
                if uid in self.enemy_ids:
                    fighter.outgoing_damage_bonus_percent += 15
                else:
                    fighter.outgoing_damage_bonus_percent -= 10

    def _is_kneeling(self, uid):
        return self.kneeling.get(uid, 0) > self.round

    # ------------------------------------------------------------------ бойцы и цель

    @property
    def enemy(self):
        return self.fighters[self.target]

    @property
    def enemies(self):
        return [self.fighters[eid] for eid in self.enemy_ids]

    def alive_enemies(self):
        return [eid for eid in self.enemy_ids if not self.fighters[eid].is_dead()]

    def alive_allies(self):
        return [aid for aid in self.ally_ids if not self.fighters[aid].is_dead()]

    def summon_ids(self, kind=None):
        return [sid for sid, summon in self.summons.items() if kind is None or summon["kind"] == kind]

    def unit_name(self, uid):
        if uid in self.summons:
            return self.summons[uid]["name"]
        return self.fighters[uid].name

    def select_target(self, eid):
        """Сделать врага eid стороной «enemy» движка CardBattle."""
        if eid == self.target or eid not in self.enemy_ids:
            return
        engine = self.engine
        self._stash[self.target] = {attr: getattr(engine, attr)["enemy"] for attr in self._swapped}
        loaded = self._stash.pop(eid)
        for attr in self._swapped:
            getattr(engine, attr)["enemy"] = loaded[attr]
        engine.enemy = self.fighters[eid]
        self.target = eid

    @contextmanager
    def _as_player(self, uid):
        """Временно сделать союзника uid стороной «player» движка (его ресурсы, эффекты и здоровье)."""
        if uid == "player":
            yield
            return
        engine = self.engine
        stash = self._ally_stash[uid]
        saved = {attr: getattr(engine, attr)["player"] for attr in self._swapped}
        for attr in self._swapped:
            getattr(engine, attr)["player"] = stash[attr]
        real_player, engine.player = engine.player, self.fighters[uid]
        try:
            yield
        finally:
            for attr in self._swapped:
                stash[attr] = getattr(engine, attr)["player"]
                getattr(engine, attr)["player"] = saved[attr]
            engine.player = real_player

    @contextmanager
    def _free_cast(self):
        """Карта уже оплачена заклинателем — получатель эффекта ничего не тратит."""
        engine = self.engine
        engine._can_pay = lambda side, card: True
        engine._spend_points = lambda side, card: None
        try:
            yield
        finally:
            del engine._can_pay
            del engine._spend_points

    def _state(self, side, attr):
        if side == "player":
            return getattr(self.engine, attr)["player"]
        if side in self._ally_stash:
            return self._ally_stash[side][attr]
        if side == self.target:
            return getattr(self.engine, attr)["enemy"]
        return self._stash.get(side, self._fresh)[attr]

    def _retarget_if_dead(self):
        if self.fighters[self.target].is_dead():
            alive = self.alive_enemies()
            if alive:
                self.select_target(alive[0])

    # ------------------------------------------------------------------ состояние

    def is_over(self):
        return self.result is not None

    def stunned(self, side):
        if side in self.summons:
            return False
        return int(self._state(side, "mage_stuns") or 0) > 0

    def in_arena(self, tile):
        left, top, width, height = self.arena_rect
        return (left <= tile[0] < left + width and top <= tile[1] < top + height
                and hex_distance_to_center(tile, self.arena_center) <= self.arena_radius + 1e-9)

    @property
    def center_tile(self):
        q, r = self.arena_center
        return q + (r - (r & 1)) // 2, r

    def occupied(self, tile, ignore=None):
        tile = tuple(tile)
        units = ["player", *self.alive_allies(), *self.alive_enemies(), *self.summons]
        return tile in self.blocked_tiles or tile in self.barriers or any(
            unit != ignore and self.positions[unit] == tile for unit in units
        )

    def _is_behind_enemy_summon_front(self, tile):
        origin_q, origin_r, direction_q, direction_r = self._summon_front_axis
        if direction_q == direction_r == 0:
            return False
        living_summons = self.enemy_summons.intersection(self.alive_enemies())
        projections = []
        for summon_id in living_summons:
            q, r = axial_coordinates(self.positions[summon_id])
            projection = ((q - origin_q) * direction_q
                          + (r - origin_r) * direction_r)
            if projection > 0:
                projections.append(projection)
        if not projections:
            return False
        q, r = axial_coordinates(tile)
        projection = ((q - origin_q) * direction_q
                      + (r - origin_r) * direction_r)
        return projection > max(projections)

    def dist(self, a, b):
        return hex_distance(self.positions[a], self.positions[b])

    def distance(self, eid=None):
        return self.dist("player", eid or self.target)

    def can_move_to(self, side, tile):
        return tuple(tile) in self.reachable_tiles(side)

    def movement_budget(self, side="player"):
        if side in self.fighters:
            fighter = self.fighters[side]
            steps = (
                int(getattr(fighter, "arena_move_range", MOVE_RANGE))
                + int(getattr(fighter, "arena_move_range_bonus", 0))
            )
            if not self.is_undead(side) and (
                self.slowed_until.get(side, 0) > self.round
                or self.positions[side] in self.grave_soil
            ):
                steps = max(0, steps - 1)
            return steps
        return int(self.summons.get(side, {}).get("movement", MOVE_RANGE))

    def is_undead(self, uid):
        fighter = self.fighters.get(uid)
        if fighter is not None and (
            fighter.profession_type == "necromancer"
            or any(word in fighter.name.casefold() for word in ("скелет", "нежить"))
        ):
            return True
        summon = self.summons.get(uid)
        if summon is None:
            return False
        if str(summon.get("kind", "")).startswith("necromancer_"):
            return True
        owner = self.fighters.get(summon.get("owner"))
        return bool(
            owner is not None
            and (
                owner.profession_type == "necromancer"
                or any(word in owner.name.casefold() for word in ("скелет", "нежить"))
            )
        )

    def movement_path(self, side, destination, max_steps=None):
        destination = tuple(destination)
        start = self.positions[side]
        if max_steps is None:
            max_steps = (
                int(getattr(self.fighters[side], "arena_move_range", MOVE_RANGE))
                + int(getattr(self.fighters[side], "arena_move_range_bonus", 0))
                if side in self.fighters else self.movement_budget(side)
            )
        reachable = set(self.reachable_tiles(side, max_steps=max_steps))
        if destination not in reachable:
            return []
        parents = {start: None}
        queue = deque([start])
        while queue:
            tile = queue.popleft()
            if tile == destination:
                break
            for neighbor in hex_neighbors(tile):
                if neighbor in reachable and neighbor not in parents:
                    parents[neighbor] = tile
                    queue.append(neighbor)
        if destination not in parents:
            return []
        path = []
        tile = destination
        while tile != start:
            path.append(tile)
            tile = parents[tile]
        return list(reversed(path))

    def _walk_unit_to(self, side, destination, max_steps=None, movement_action=True):
        path = self.movement_path(side, destination, max_steps=max_steps)
        if not path:
            return False
        start = self.positions[side]
        walked_path = []
        for tile in path:
            if (
                side not in self.positions
                or hex_distance(self.positions[side], tile) != 1
                or not self.in_arena(tile)
                or self.occupied(tile, ignore=side)
                or self.roots.get(side, 0)
                or self._is_kneeling(side)
                or self.stunned(side)
            ):
                break
            previous_tile = self.positions[side]
            self.positions[side] = tile
            walked_path.append(tuple(tile))
            if side == "player" and movement_action:
                self.moved = True
            self._trigger_trap(side, tile, previous_tile=previous_tile)
            if (
                self.positions.get(side) != tile
                or self.roots.get(side, 0)
                or self.stunned(side)
            ):
                break
        if walked_path and (side != "player" or not movement_action):
            self.movement_events.append({
                "unit": side,
                "start": tuple(start),
                "path": walked_path,
            })
        self._refresh_king_auras()
        return self.positions.get(side) != start

    def begin_player_movement(self, destination):
        if (
            not self.player_can_act() or self.kneeling.get("player", 0)
            or self.moved
        ):
            return []
        self.player_movement_path = self.movement_path("player", destination)
        self._player_movement_steps = 0
        self.last_move_interrupted = False
        return list(self.player_movement_path)

    def reachable_tiles(self, side, max_steps=MOVE_RANGE):
        if self.roots.get(side, 0) or self._is_kneeling(side):
            return []
        if side in self.fighters:
            if not self.is_undead(side) and (
                self.slowed_until.get(side, 0) > self.round
                or self.positions[side] in self.grave_soil
            ):
                max_steps = max(0, int(max_steps) - 1)
        elif side in self.summons:
            if (
                not self.is_undead(side)
                and self.positions[side] in self.grave_soil
            ):
                max_steps = max(0, int(max_steps) - 1)
            if self.summons[side].get("kind") == "necromancer_spirit":
                start = self.positions[side]
                visited = {start}
                queue = deque([(start, 0)])
                reachable = []
                while queue:
                    tile, steps = queue.popleft()
                    if steps >= max_steps:
                        continue
                    for neighbor in hex_neighbors(tile):
                        if neighbor in visited or not self.in_arena(neighbor):
                            continue
                        visited.add(neighbor)
                        if not self.occupied(neighbor, ignore=side):
                            reachable.append(neighbor)
                        queue.append((neighbor, steps + 1))
                return reachable
        barrier = self.wolf_barrier
        if barrier and barrier["wolf_id"] not in self.alive_enemies():
            self.wolf_barrier = None
            barrier = None
        start = self.positions[side]
        visited = {start}
        queue = deque([(start, 0)])
        reachable = []
        while queue:
            tile, steps = queue.popleft()
            if steps >= max_steps:
                continue
            for neighbor in hex_neighbors(tile):
                if neighbor in visited or not self.in_arena(neighbor) or self.occupied(neighbor, ignore=side):
                    continue
                if side == "player" and self._is_behind_enemy_summon_front(neighbor):
                    continue
                if side == "player" and barrier and self._crosses_wolf_barrier(neighbor, barrier):
                    continue
                visited.add(neighbor)
                reachable.append(neighbor)
                queue.append((neighbor, steps + 1))
        return reachable

    def _crosses_wolf_barrier(self, tile, barrier):
        wolf_id = barrier["wolf_id"]
        if wolf_id not in self.positions:
            return False
        direction = barrier["direction"]
        wolf_q, wolf_r = axial_coordinates(self.positions[wolf_id])
        tile_q, tile_r = axial_coordinates(tile)
        return ((tile_q - wolf_q) * direction[0]
                + (tile_r - wolf_r) * direction[1]) > 0

    def summon_tiles(self):
        """Свободные тайлы в радиусе SUMMON_RANGE от игрока, куда можно поставить существо."""
        px, py = self.positions["player"]
        return [
            (px + dx, py + dy)
            for dy in range(-SUMMON_RANGE, SUMMON_RANGE + 1)
            for dx in range(-SUMMON_RANGE, SUMMON_RANGE + 1)
            if 0 < hex_distance((px, py), (px + dx, py + dy)) <= SUMMON_RANGE
            and self.in_arena((px + dx, py + dy)) and not self.occupied((px + dx, py + dy))
            and not any(trap["tile"] == (px + dx, py + dy) for trap in self.traps)
        ]

    def player_can_act(self):
        return (
            not self.player_draft
            and not self.engine.draw_choices["player"]
            and self.active_side == "player"
            and not self.is_over()
            and not self.stunned("player")
        )

    def choose_draw_card(self, card_key):
        if self.player_draft or not self.engine.draw_choices["player"]:
            return False
        return self.engine.choose_draw_card("player", card_key)

    def card_targets(self, card, caster="player"):
        """Бойцы, на которых можно разыграть карту (для призыва — пусто, он ставится на тайл)."""
        role = card_role(card)
        card_range = (card.effect_data or {}).get("range")
        if role == "enemy" and card_range is not None and int(card_range) >= 2:
            fighter = self.fighters[caster]
            if fighter.profession_type == "archer":
                accuracy = int(getattr(fighter, "unique_resource_current", 0))
                per_ten = int(
                    getattr(fighter, "_talent_effects", {}).get(
                        "attack_range_per_10_accuracy", 0
                    )
                )
                card_range = int(card_range) + accuracy // 10 * per_ten
        in_range = lambda uid: card_range is None or uid == caster or self.dist(caster, uid) <= int(card_range)
        if card.effect_type == "necromancer_sacrifice":
            return [
                sid for sid, summon in self.summons.items()
                if summon.get("owner") == caster
            ]
        if card.effect_type == "necromancer_summon_heal":
            return [caster]
        if card.effect_type == "necromancer_transfer":
            return [
                uid for uid in ("player", *self.alive_allies())
                if uid != caster and in_range(uid)
                and not self._line_blocked(self.positions[caster], self.positions[uid])
                and bool(self.reachable_tiles(uid, max_steps=int((card.effect_data or {}).get("distance", 3))))
            ]
        if card.effect_type == "arena_evolution":
            reach = int((card.effect_data or {}).get("range", 5))
            return [
                uid for uid in (*self.alive_allies(), *self.summons)
                if (
                    uid in self.summons
                    and self.summons[uid].get("owner") == caster
                    or uid in self.ally_ids
                )
                and hex_distance(self.positions[caster], self.positions[uid]) <= reach
                and not self._line_blocked(self.positions[caster], self.positions[uid])
            ]
        if role == "enemy":
            return [
                eid for eid in self.alive_enemies()
                if not (
                    self._is_kneeling(caster)
                    and self.fighters[eid].name == "Король скелетов"
                )
                if in_range(eid)
                and not self._line_blocked(self.positions[caster], self.positions[eid])
                and not (
                    caster == "player"
                    and self._is_behind_enemy_summon_front(self.positions[eid])
                )
            ]
        if role == "ally":
            return [
                uid for uid in ("player", *self.alive_allies())
                if in_range(uid)
                and not self._line_blocked(self.positions[caster], self.positions[uid])
            ]
        if role == "self":
            return [caster]
        return []

    def card_tiles(self, card):
        data = card.effect_data or {}
        effect = card.effect_type
        if effect == "arena_dash":
            return self.reachable_tiles("player", max_steps=int(data.get("distance", 3)))
        if effect == "arena_teleport":
            origin = self.positions["player"]
            left, top, width, height = self.arena_rect
            return [
                (x, y)
                for y in range(top, top + height)
                for x in range(left, left + width)
                if self.in_arena((x, y))
                and (x, y) != origin
                and not self.occupied((x, y), ignore="player")
            ]
        if effect in {
            "arena_wolf", "arena_trap", "arena_barrier",
            "necromancer_trap", "necromancer_barrier", "necromancer_grave_soil",
        }:
            distance = int(data.get("range", 1 if effect == "arena_wolf" else 2))
            origin = self.positions["player"]
            tiles = (
                (x, y) for y in range(origin[1] - distance, origin[1] + distance + 1)
                for x in range(origin[0] - distance, origin[0] + distance + 1)
                if hex_distance(origin, (x, y)) <= distance
                and self.in_arena((x, y)) and not self.occupied((x, y))
            )
            if effect == "necromancer_barrier":
                return [tile for tile in tiles if self._grave_barrier_line(tile) is not None]
            if effect == "arena_barrier":
                return [tile for tile in tiles if self._barrier_line(tile) is not None]
            if effect == "necromancer_grave_soil":
                return [tile for tile in tiles if tile not in self.barriers]
            if effect in {"arena_trap", "necromancer_trap"}:
                return [
                    tile for tile in tiles
                    if not any(trap["tile"] == tile for trap in self.traps)
                ]
            return [tile for tile in tiles if tile != origin]
        return []

    def transfer_tiles(self, target, card):
        if target not in ("player", *self.alive_allies()):
            return []
        return self.reachable_tiles(
            target,
            max_steps=int((card.effect_data or {}).get("distance", 3)),
        )

    def card_aim_tiles(self, card, caster="player"):
        """Return in-range arena hexes that can be chosen as an attack's aim point."""
        if card_role(card) != "enemy":
            return []
        data = card.effect_data or {}
        max_range = data.get("range")
        if max_range is not None and int(max_range) >= 2:
            fighter = self.fighters[caster]
            if fighter.profession_type == "archer":
                accuracy = int(getattr(fighter, "unique_resource_current", 0))
                per_ten = int(
                    getattr(fighter, "_talent_effects", {}).get(
                        "attack_range_per_10_accuracy", 0
                    )
                )
                max_range = int(max_range) + accuracy // 10 * per_ten
        origin = self.positions[caster]
        tiles = []
        for y in range(self.arena_rect[1], self.arena_rect[1] + self.arena_rect[3]):
            for x in range(self.arena_rect[0], self.arena_rect[0] + self.arena_rect[2]):
                tile = (x, y)
                distance = hex_distance(origin, tile)
                if (
                    self.in_arena(tile)
                    and (max_range is None or distance <= int(max_range))
                    and tile not in self.barriers
                    and not self._line_blocked(origin, tile)
                    and not (
                        caster == "player"
                        and self._is_behind_enemy_summon_front(tile)
                    )
                ):
                    tiles.append(tile)
        return tiles

    def attack_targets_at(self, card, aim_tile, caster="player"):
        if tuple(aim_tile) not in self.card_aim_tiles(card, caster):
            return []
        radius = max(0, int((card.effect_data or {}).get("aoe_radius", 0)))
        return [
            uid for uid in self.alive_enemies()
            if hex_distance(self.positions[uid], tuple(aim_tile)) <= radius
        ]

    def aoe_aim_tile_for_target(self, card, target_tile, caster="player"):
        radius = int((card.effect_data or {}).get("aoe_radius", 0))
        if radius <= 0:
            return None
        candidates = [
            tile for tile in self.card_aim_tiles(card, caster)
            if hex_distance(tile, tuple(target_tile)) <= radius
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda tile: (
                hex_distance(tile, tuple(target_tile)),
                hex_distance(self.positions[caster], tile),
                tile[1],
                tile[0],
            ),
        )

    def _barrier_line(self, center):
        q, r = axial_coordinates(center)
        for dq, dr in ((0, 1), (1, 0), (1, -1)):
            line = []
            for offset in (-1, 0, 1):
                row, col = r + dr * offset, q + dq * offset
                line.append((col + (row - (row & 1)) // 2, row))
            if all(
                self.in_arena(tile) and not self.occupied(tile)
                and not any(trap["tile"] == tile for trap in self.traps)
                for tile in line
            ):
                return tuple(line)
        return None

    def _grave_barrier_line(self, start):
        source_q, source_r = axial_coordinates(self.positions["player"])
        start_q, start_r = axial_coordinates(start)
        vector = (start_q - source_q, start_r - source_r)
        if vector == (0, 0):
            return None
        axial_directions = ((0, -1), (1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0))
        direction = max(
            axial_directions,
            key=lambda offset: (
                2 * vector[0] * offset[0]
                + vector[0] * offset[1]
                + vector[1] * offset[0]
                + 2 * vector[1] * offset[1]
            ),
        )
        line = []
        q, r = start_q, start_r
        while True:
            tile = (q + (r - (r & 1)) // 2, r)
            if not self.in_arena(tile):
                break
            if (
                not self.occupied(tile)
                and not any(trap["tile"] == tile for trap in self.traps)
            ):
                line.append(tile)
            q += direction[0]
            r += direction[1]
        return tuple(line) or None

    def _line_blocked(self, start, end):
        start_q, start_r = axial_coordinates(start)
        end_q, end_r = axial_coordinates(end)
        distance = hex_distance(start, end)
        for step in range(1, distance):
            ratio = step / distance
            x = start_q + (end_q - start_q) * ratio
            z = start_r + (end_r - start_r) * ratio
            y = -x - z
            q, rounded_y, r = round(x), round(y), round(z)
            x_diff, y_diff, z_diff = abs(q - x), abs(rounded_y - y), abs(r - z)
            if x_diff > y_diff and x_diff > z_diff:
                q = -rounded_y - r
            elif y_diff > z_diff:
                rounded_y = -q - r
            else:
                r = -q - rounded_y
            tile = (q + (r - (r & 1)) // 2, r)
            if tile in self.barriers:
                return True
        return False

    def can_play_card(self, card, target=None, aim_tile=None):
        self._refresh_king_auras()
        if not self.player_can_act() or self.cards_played >= MAX_CARDS_PER_TURN:
            return False
        if self.kneeling.get("player", 0) and self.cards_played >= 1:
            return False
        if card not in self.engine.hands["player"] or not self.engine.can_select("player", card):
            return False
        if card.effect_type == "necromancer_resource_sacrifice":
            hp_cost = max(
                1,
                int(self.player.max_hp * int((card.effect_data or {}).get("hp_percent", 25)) / 100),
            )
            if self.player.hp <= hp_cost:
                return False
        role = card_role(card)
        if role == "enemy":
            if aim_tile is not None:
                return tuple(aim_tile) in self.card_aim_tiles(card)
            if target is not None:
                return target in self.card_targets(card)
            return bool(self.card_aim_tiles(card))
        if role in {"summon", "tile"}:
            tiles = self.card_tiles(card) if card.effect_type == "arena_wolf" or role == "tile" else self.summon_tiles()
            if target is None:
                return bool(tiles)
            if tuple(target) not in tiles:
                return False
            if card.effect_type == "arena_teleport":
                cost = hex_distance(self.positions["player"], tuple(target)) * int(
                    (card.effect_data or {}).get("mana_per_hex", 3)
                )
                return self.player.mp >= cost
            return True
        targets = self.card_targets(card)
        return bool(targets) if target is None else target in targets

    def _default_target(self, card):
        role = card_role(card)
        if role == "summon":
            tiles = self.card_tiles(card) if card.effect_type == "arena_wolf" else self.summon_tiles()
            goal = self.positions[self.target]
            return min(tiles, key=lambda tile: hex_distance(tile, goal)) if tiles else None
        targets = self.card_targets(card)
        if role == "enemy" and self.target in targets:
            return self.target
        return targets[0] if targets else None

    # ------------------------------------------------------------------ действия игрока

    def move_player(self, tile):
        if (
            not self.player_can_act() or self.kneeling.get("player", 0)
            or self.moved
        ):
            return False
        path = self.begin_player_movement(tile)
        if not path:
            return False
        moved = False
        for step in path:
            if not self.move_player_step(step):
                break
            moved = True
            if self.last_move_interrupted:
                break
        self.player_movement_path = []
        return moved

    def move_player_step(self, tile):
        tile = tuple(tile)
        self.last_move_interrupted = False
        if (
            not self.player_can_act()
            or self.kneeling.get("player", 0)
            or self.roots.get("player", 0)
            or self._player_movement_steps >= self.movement_budget("player")
            or not self.player_movement_path
            or tile != self.player_movement_path[0]
            or tile not in hex_neighbors(self.positions["player"])
            or not self.in_arena(tile)
            or self.occupied(tile, ignore="player")
            or self._is_behind_enemy_summon_front(tile)
            or (
                self.wolf_barrier
                and self._crosses_wolf_barrier(tile, self.wolf_barrier)
            )
        ):
            return False
        previous_tile = self.positions["player"]
        self.positions["player"] = tuple(tile)
        self.moved = True
        self._player_movement_steps += 1
        self.player_movement_path.pop(0)
        self._refresh_king_auras()
        self._trigger_trap("player", tuple(tile), previous_tile=previous_tile)
        self.last_move_interrupted = (
            self.positions["player"] != tuple(tile)
            or bool(self.roots.get("player", 0))
            or self.stunned("player")
        )
        return True

    def play_card(self, card, target=None, destination=None, aim_tile=None):
        """Разыграть карту на бойца target (или на тайл target для призыва)."""
        if aim_tile is not None:
            if not self.can_play_card(card, aim_tile=aim_tile):
                return None
            event = self._play_attack_at_tile(card, tuple(aim_tile))
            return self._complete_card_play(card, event)
        if target is None:
            target = self._default_target(card)
        if target is None or not self.can_play_card(card, target):
            return None
        if (
            card.effect_type == "necromancer_transfer"
            and tuple(destination or ()) not in self.transfer_tiles(target, card)
        ):
            return None
        if card.effect_type in {
            "arena_trap", "arena_barrier", "arena_dash", "arena_wolf",
            "arena_resource_recovery", "arena_knockback",
            "arena_bonebreaker", "arena_divine_healing",
            "arena_unstable_elixir", "arena_evolution", "arena_teleport",
            "arena_dreadful_corruption",
            "necromancer_trap", "necromancer_barrier", "necromancer_grave_soil",
        }:
            event = self._play_arena_card(card, target)
        elif (
            card.effect_type.startswith("necromancer_")
            and card.effect_type != "necromancer_summon"
        ):
            event = self._play_necromancer_card(card, target, destination)
        elif card_role(card) == "summon":
            event = self._summon("player", card, tuple(target))
        else:
            event = self._cast("player", card, target)
        return self._complete_card_play(card, event)

    def _complete_card_play(self, card, event):
        if event is None:
            return None
        self.engine.hands["player"].remove(card)
        self.engine.discard.append(card)
        self.cards_played += 1
        self._log_cast(self.player.name, card, event)
        self._check_result()
        self._retarget_if_dead()
        return event

    def _play_attack_at_tile(self, card, aim_tile):
        targets = self.attack_targets_at(card, aim_tile)
        data = card.effect_data or {}
        event = {
            "target_tile": aim_tile,
            "targets": list(targets),
            "hit_results": [],
            "damage": 0,
            "healed": 0,
            "effect_text": "АТАКА ПО ГЕКСУ",
            "attack": True,
        }
        if card.effect_type == "arena_dreadful_corruption":
            with self._as_player("player"):
                if not self.engine._can_pay("player", card):
                    return None
                self.engine._spend_points("player", card)
            for uid in targets:
                self._apply_dreadful_corruption(uid, data)
            event["effect_text"] = f"СТРАШНАЯ ПОРЧА: ПОРАЖЕНО ЦЕЛЕЙ {len(targets)}"
            return event
        if not targets:
            with self._as_player("player"):
                if not self.engine._can_pay("player", card):
                    return None
                self.engine._spend_points("player", card)
            event["effect_text"] = "АТАКА ПО ПУСТОМУ ГЕКСУ"
            return event
        for index, uid in enumerate(targets):
            context = self._free_cast() if index else nullcontext()
            with context:
                hit = self._cast("player", card, uid)
            if hit is None:
                continue
            event["hit_results"].append(hit)
            event["damage"] += int(hit.get("damage", 0))
            event["healed"] += int(hit.get("healed", 0))
        if event["hit_results"]:
            event["effect_text"] = f"ПОРАЖЕНО ЦЕЛЕЙ: {len(event['hit_results'])}"
        else:
            event["effect_text"] = "АТАКА ПО ПУСТОМУ ГЕКСУ"
        return event

    def _apply_dreadful_corruption(self, uid, data):
        fighter = self.fighters[uid]
        with self._as_player(uid):
            self.engine._add_mage_status(
                "player", "огонь", 3, stacks=int(data.get("fire_stacks", 4))
            )
            for _ in range(int(data.get("poison_stacks", 4))):
                self.engine._add_poison("player", 1)
            self.engine._add_buff(
                "player", 2,
                outgoing_damage_percent=int(data.get("outgoing_damage_reduction", 20)),
            )
            self.engine.mage_stuns["player"] = max(
                self.engine.mage_stuns.get("player", 0),
                int(data.get("stun_turns", 1)),
            )
        self._add_green_flame(uid, 2)
        incoming_bonus = int(data.get("incoming_damage_bonus", 20))
        self.temporary_damage_taken.setdefault(uid, []).append([incoming_bonus, 2])
        self._refresh_king_auras()
        resource_loss = int(fighter.unique_resource_max * int(data.get("resource_loss_percent", 10)) / 100)
        if fighter.unique_resource_type == "mana":
            resource_loss = int(fighter.max_mp * int(data.get("resource_loss_percent", 10)) / 100)
            fighter.mp = max(0, fighter.mp - resource_loss)
        else:
            fighter.unique_resource_current = max(0, fighter.unique_resource_current - resource_loss)
        self._log(f"{fighter.name}: Страшная порча — потеряно {resource_loss} ресурса")

    def _play_arena_card(self, card, target):
        data = card.effect_data or {}
        if card.effect_type == "arena_teleport":
            destination = tuple(target)
            cost = hex_distance(self.positions["player"], destination) * int(
                data.get("mana_per_hex", 3)
            )
            if self.player.mp < cost:
                return None
            self.player.mp -= cost
            previous_tile = self.positions["player"]
            self.positions["player"] = destination
            self._trigger_trap("player", destination, previous_tile=previous_tile)
            return {
                "target_tile": destination,
                "resource_spent": cost,
                "effect_text": f"ТЕЛЕПОРТ: ПОТРАЧЕНО {cost} МАНЫ",
            }
        with self._as_player("player"):
            if not self.engine._can_pay("player", card):
                return None
            self.engine._spend_points("player", card)
        event = {"effect_text": card.name.upper()}
        if card.effect_type == "arena_trap":
            self.traps.append({
                "tile": tuple(target), "owner": "player",
                "damage": int(data.get("damage", 0)),
                "root_turns": int(data.get("root_turns", 0)),
            })
            event["effect_text"] = "ЛОВУШКА УСТАНОВЛЕНА"
        elif card.effect_type == "necromancer_trap":
            self.traps.append({
                "tile": tuple(target),
                "owner": "player",
                "damage": int(data.get("damage", 0)),
                "root_turns": int(data.get("root_turns", 0)),
                "slow_turns": int(data.get("slow_turns", 0)),
                "knockback": int(data.get("knockback", 0)),
            })
            event["effect_text"] = "ЛОВУШКА УСТАНОВЛЕНА"
        elif card.effect_type == "arena_barrier":
            for tile in self._barrier_line(tuple(target)):
                self.barriers[tile] = int(card.effect_duration or 8)
            event["effect_text"] = "БАРРИКАДА УСТАНОВЛЕНА"
        elif card.effect_type == "necromancer_barrier":
            for tile in self._grave_barrier_line(tuple(target)) or ():
                self.barriers[tile] = int(data.get("duration", card.effect_duration or 6))
            event["effect_text"] = "МОГИЛЬНЫЕ ПЛИТЫ УСТАНОВЛЕНЫ"
        elif card.effect_type == "necromancer_grave_soil":
            duration = int(data.get("duration", 15))
            radius = int(data.get("radius", 3))
            for y in range(self.arena_rect[1], self.arena_rect[1] + self.arena_rect[3]):
                for x in range(self.arena_rect[0], self.arena_rect[0] + self.arena_rect[2]):
                    tile = (x, y)
                    if (
                        self.in_arena(tile)
                        and hex_distance(tuple(target), tile) <= radius
                        and tile not in self.barriers
                    ):
                        self.grave_soil[tile] = max(
                            self.grave_soil.get(tile, 0), self.round + duration
                        )
            event["effect_text"] = "МОГИЛЬНАЯ ПОЧВА РАСПРОСТРАНЯЕТСЯ"
        elif card.effect_type == "arena_dash":
            self._walk_unit_to(
                "player",
                tuple(target),
                max_steps=int(data.get("distance", 3)),
                movement_action=False,
            )
            event["effect_text"] = "РЫВОК"
        elif card.effect_type == "arena_wolf":
            self._summon_counter += 1
            sid = f"summon_{self._summon_counter}"
            wolf_hp = WOLF_MAX_HP
            wolf_damage = 5
            if self.player.profession_type == "necromancer":
                talent_effects = self.player._talent_effects
                wolf_hp += (
                    int(talent_effects.get("summon_hp_per_intellect", 0))
                    * int(self.player.intellect)
                )
                wolf_damage += (
                    int(talent_effects.get("summon_damage_per_4_wisdom", 0))
                    * int(self.player.wisdom) // 4
                )
            self.summons[sid] = {
                "kind": "wolf", "name": "Волк", "owner": "player",
                "hp": wolf_hp, "max_hp": wolf_hp, "damage": wolf_damage,
            }
            self.positions[sid] = tuple(target)
            self.damage_dealt[sid] = 0
            event["effect_text"] = "ПРИЗВАН ВОЛК"
        elif card.effect_type == "arena_resource_recovery":
            fighter = self.player
            resource_type = getattr(fighter, "unique_resource_type", None)
            if resource_type == "mana":
                amount = int(fighter.max_mp * int(data.get("resource_percent", 15)) / 100)
                fighter.mp = min(fighter.max_mp, fighter.mp + amount)
            else:
                amount = int(fighter.unique_resource_max * int(data.get("resource_percent", 15)) / 100)
                fighter.gain_unique_resource(amount)
            fighter.next_damage_taken_bonus_percent = int(
                data.get("next_damage_taken_bonus_percent", 25)
            )
            event["resource_restored"] = amount
            event["effect_text"] = f"+{amount} РЕСУРСА, СЛЕДУЮЩИЙ УРОН +25%"
        elif card.effect_type == "arena_knockback":
            self.select_target(target)
            victim = self.fighters[target]
            hp_before = victim.hp
            with self._as_player("player"):
                self.engine._mage_take_damage(
                    "enemy", int(data.get("damage", 12)), source_side="player"
                )
            self.damage_dealt["player"] += max(0, int(hp_before - victim.hp))
            self._knockback(target, int(data.get("knockback", 3)))
            event["target"] = target
            event["damage"] = max(0, int(hp_before - victim.hp))
            event["effect_text"] = f"{event['damage']} УРОНА, ОТБРАСЫВАНИЕ"
        elif card.effect_type == "arena_bonebreaker":
            duration = int(data.get("duration", 2))
            self.broken_bones[target] = max(self.broken_bones.get(target, 0), self.round + duration)
            event["target"] = target
            event["effect_text"] = "СЛОМАННЫЕ КОСТИ: ПЕРЕМЕЩЕНИЕ ОТНИМАЕТ 4% МАКС. HP"
        elif card.effect_type == "arena_divine_healing":
            with self._as_player(target):
                self.engine.regenerations["player"].append({
                    "heal_per_turn": int(data.get("heal_per_turn", 10)),
                    "endurance_heal": 0,
                    "remaining": int(data.get("duration", 7)),
                    "card": card.name,
                    "fresh": True,
                })
            event["target"] = target
            event["effect_text"] = "БОЖЕСТВЕННОЕ ИСЦЕЛЕНИЕ: РЕГЕНЕРАЦИЯ"
        elif card.effect_type == "arena_unstable_elixir":
            self._apply_unstable_elixir(data)
            event["target"] = "player"
            event["effect_text"] = "НЕСТАБИЛЬНОЕ ЗЕЛЬЕ: 3 ХОРОШИХ И 3 ПЛОХИХ ЭФФЕКТА"
        elif card.effect_type == "arena_evolution":
            if target in self.summons:
                summon = self.summons[target]
                bonus = int(data.get("summon_max_hp", 20))
                summon["max_hp"] += bonus
                summon["hp"] += bonus
                summon.setdefault("regenerations", []).append({
                    "heal_per_turn": int(data.get("heal_per_turn", 5)),
                    "remaining": int(data.get("duration", 3)),
                    "fresh": True,
                    "card": card.name,
                })
            else:
                fighter = self.fighters[target]
                bonus = int(data.get("fighter_max_hp", 35))
                fighter.max_hp += bonus
                fighter.hp += bonus
                with self._as_player(target):
                    self.engine.regenerations["player"].append({
                        "heal_per_turn": int(data.get("heal_per_turn", 5)),
                        "endurance_heal": 0,
                        "remaining": int(data.get("duration", 3)),
                        "card": card.name,
                        "fresh": True,
                    })
            event.update(target=target, healed=bonus)
            event["effect_text"] = f"ЭВОЛЮЦИЯ: МАКС. HP +{bonus}, РЕГЕНЕРАЦИЯ"
        return event

    def _apply_unstable_elixir(self, data):
        fighter = self.player
        positive = (
            (30, "heal"), (30, "teleport"), (15, "shield"),
            (10, "resource"), (5, "regeneration"),
        )
        negative = (
            (30, "damage"), (30, "teleport"), (15, "defense"),
            (10, "resource"), (5, "corrosion"),
        )
        for effects, good in ((positive, True), (negative, False)):
            for _ in range(int(data.get("rolls", 3))):
                roll = self.rng.randrange(100)
                cumulative = 0
                selected = None
                for chance, effect in effects:
                    cumulative += chance
                    if roll < cumulative:
                        selected = effect
                        break
                if selected is None:
                    continue
                if selected == "heal":
                    fighter.hp = min(fighter.max_hp, fighter.hp + 10)
                elif selected == "teleport":
                    self._random_short_teleport()
                elif selected == "shield":
                    with self._as_player("player"):
                        self.engine.mage_shields["player"] += 12
                elif selected == "resource":
                    amount = int(fighter.unique_resource_max * 0.1)
                    if fighter.unique_resource_type == "mana":
                        fighter.mp = min(fighter.max_mp, fighter.mp + amount) if good else max(0, fighter.mp - amount)
                    elif good:
                        fighter.gain_unique_resource(amount)
                    else:
                        fighter.unique_resource_current = max(0, fighter.unique_resource_current - amount)
                elif selected == "regeneration":
                    with self._as_player("player"):
                        self.engine.regenerations["player"].append({
                            "heal_per_turn": 5, "endurance_heal": 0, "remaining": 4,
                            "card": "Нестабильное зелье", "fresh": True,
                        })
                elif selected == "damage":
                    self._apply_environment_damage("player", 10, source_side="enemy")
                elif selected == "defense":
                    self.temporary_damage_taken.setdefault("player", []).append([30, 2])
                    self._refresh_king_auras()
                elif selected == "corrosion":
                    self.arena_corrosion["player"] = [15, 4]

    def _random_short_teleport(self):
        current = self.positions["player"]
        tiles = self.reachable_tiles("player", max_steps=2)
        if not tiles:
            return
        destination = self.rng.choice(tiles)
        self._walk_unit_to(
            "player", destination, max_steps=2, movement_action=False
        )

    def _play_necromancer_card(self, card, target, destination=None):
        data = card.effect_data or {}
        caster = self.fighters["player"]
        with self._as_player("player"):
            if not self.engine._can_pay("player", card):
                return None
            self.engine._spend_points("player", card)

        event = {"target": target, "effect_text": card.name.upper(), "damage": 0}
        effect = card.effect_type
        if effect == "necromancer_transfer":
            path = self.movement_path(
                target, destination,
                max_steps=int(data.get("distance", 3)),
            )
            if not path:
                return None
            self._walk_unit_to(
                target, destination, max_steps=len(path), movement_action=False
            )
            event["destination"] = self.positions[target]
            event["effect_text"] = "СУЩЕСТВО ПЕРЕМЕЩЕНО"
        elif effect == "necromancer_summon_heal":
            healed = 0
            for sid, summon in self.summons.items():
                if summon.get("owner") != "player" or self.dist("player", sid) > int(data.get("range", 2)):
                    continue
                amount = max(1, int(summon["max_hp"] * int(data.get("heal_percent", 35)) / 100))
                restored = min(amount, summon["max_hp"] - summon["hp"])
                summon["hp"] += restored
                healed += restored
            event["healed"] = healed
            event["effect_text"] = f"ПРИЗЫВЫ ИСЦЕЛЕНЫ НА {healed} HP"
        elif effect == "necromancer_sacrifice":
            summon = self.summons[target]
            refund = int(int(summon.get("resource_cost", 0)) * int(data.get("refund_percent", 35)) / 100)
            self._remove_summon(target, "поглощён во имя владыки")
            healed = min(
                caster.max_hp - caster.hp,
                int(caster.max_hp * int(data.get("heal_percent", 20)) / 100),
            )
            caster.hp += healed
            resource_gain = int(caster.unique_resource_max * int(data.get("resource_percent", 10)) / 100)
            caster.gain_unique_resource(resource_gain + refund)
            drawn = self.engine.draw_next_turn_card("player")
            event.update(healed=healed, resource_restored=resource_gain + refund)
            event["effect_text"] = "ЖЕРТВА ПРИНЯТА" + ("; КАРТА ВЗЯТА" if drawn else "")
        elif effect == "necromancer_summon_search":
            self.next_summon_bonus = {
                "hp_percent": int(data.get("hp_percent", 20)),
                "damage_percent": int(data.get("damage_percent", 10)),
                "damage_reduction_percent": int(data.get("damage_reduction_percent", 10)),
            }
            deck = self.engine._deck_for("player")
            summon_card = next(
                (card for card in reversed(deck) if card.effect_type == "necromancer_summon"),
                None,
            )
            if summon_card is not None and len(self.engine.hands["player"]) < self.hand_limit:
                deck.remove(summon_card)
                self.engine.hands["player"].append(summon_card)
                event["effect_text"] = "КАРТА ПРИЗЫВА ДОБАВЛЕНА; СЛЕДУЮЩИЙ ПРИЗЫВ УСИЛЕН"
            else:
                event["effect_text"] = "СЛЕДУЮЩИЙ ПРИЗЫВ УСИЛЕН"
        elif effect == "necromancer_resource_sacrifice":
            health_cost = max(1, int(caster.max_hp * int(data.get("hp_percent", 25)) / 100))
            if caster.hp <= health_cost:
                return None
            caster.take_damage(health_cost)
            restored = int(caster.unique_resource_max * int(data.get("resource_percent", 25)) / 100)
            caster.gain_unique_resource(restored)
            event.update(damage=health_cost, resource_restored=restored)
            event["effect_text"] = f"ПОТРАЧЕНО {health_cost} HP, +{restored} НЕКРОТИЗМА"
        elif effect == "necromancer_bargain":
            self._add_green_flame("player", int(data.get("green_flame_damage_percent", 1)))
            self.necrotism_gain_bonus["player"] = max(
                self.necrotism_gain_bonus.get("player", 0),
                int(data.get("gain_percent", 20)),
            )
            event["effect_text"] = "ЗЕЛЁНЫЙ ОГОНЬ; ПОЛУЧЕНИЕ НЕКРОТИЗМА +20%"
        elif effect == "necromancer_screamer":
            affected = [
                uid for uid in self.alive_enemies()
                if self.dist(target, uid) <= int(data.get("aoe_radius", 1))
            ]
            for uid in affected:
                dealt = self._apply_environment_damage(
                    uid, int(data.get("damage", 5)), source_side="player"
                )
                event["damage"] += dealt
                if not self.fighters[uid].is_dead():
                    self.select_target(uid)
                    self.engine.mage_stuns["enemy"] = max(
                        self.engine.mage_stuns.get("enemy", 0),
                        int(data.get("stun_turns", 1)),
                    )
            event["effect_text"] = f"СКРИМЕР: {len(affected)} ЦЕЛЕЙ ОГЛУШЕНЫ"
        elif effect in {
            "necromancer_damage",
            "necromancer_damage_roots",
            "necromancer_defense_curse",
            "necromancer_green_flame",
        }:
            target_fighter = self.fighters[target]
            damage = int(data.get("damage", 0))
            if damage:
                dealt = self._apply_environment_damage(target, damage, source_side="player")
                event["damage"] = dealt
            if effect == "necromancer_damage_roots":
                self.roots[target] = max(self.roots.get(target, 0), int(data.get("root_turns", 2)))
            elif effect == "necromancer_defense_curse":
                self.defense_curses[target] = max(
                    self.defense_curses.get(target, 0),
                    self.round + int(data.get("duration", 3)),
                )
                target_fighter.incoming_damage_bonus_percent = int(
                    data.get("reduction_percent", 30)
                )
            elif effect == "necromancer_green_flame":
                self._add_green_flame(target, int(data.get("damage_percent", 2)))
            event["effect_text"] = (
                f"{event['damage']} УРОНА" if event["damage"]
                else "ЗЕЛЁНЫЙ ОГОНЬ НАЛОЖЕН" if effect == "necromancer_green_flame"
                else "ЭФФЕКТ НАЛОЖЕН"
            )
        return event

    def _add_green_flame(self, target, damage_percent):
        self.green_flame.setdefault(target, []).append(max(1, int(damage_percent)))

    def _allied_summon_ids(self):
        return [
            sid for sid, summon in self.summons.items()
            if summon.get("owner") in ("player", *self.ally_ids)
        ]

    def _knockback(self, side, distance, origin=None, reverse=False):
        origin = self.positions["player"] if origin is None else tuple(origin)
        current = self.positions[side]
        q0, r0 = axial_coordinates(origin)
        q1, r1 = axial_coordinates(current)
        direction = (q1 - q0, r1 - r0)
        if reverse:
            direction = (-direction[0], -direction[1])
        if direction == (0, 0):
            return
        axial_directions = ((0, -1), (1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0))

        def hex_dot(first, second):
            return (
                2 * first[0] * second[0]
                + first[0] * second[1]
                + first[1] * second[0]
                + 2 * first[1] * second[1]
            )

        direction = max(axial_directions, key=lambda step: hex_dot(direction, step))
        for _ in range(distance):
            q, r = axial_coordinates(current)
            candidates = []
            for neighbor in hex_neighbors(current):
                nq, nr = axial_coordinates(neighbor)
                step = (nq - q, nr - r)
                score = hex_dot(step, direction)
                if (
                    score > 0 and self.in_arena(neighbor)
                    and not self.occupied(neighbor, ignore=side)
                ):
                    candidates.append((neighbor, score, hex_distance(origin, neighbor)))
            if not candidates:
                break
            previous_tile = current
            current = max(candidates, key=lambda option: (option[1], option[2]))[0]
            self.positions[side] = current
            self._refresh_king_auras()
            self._trigger_trap(side, current, previous_tile=previous_tile)
            if (
                self.positions.get(side) != current
                or self.roots.get(side, 0)
                or self.stunned(side)
            ):
                break

    def _trigger_trap(self, side, tile, previous_tile=None):
        if side not in self.fighters:
            return
        if self.broken_bones.get(side, 0) > self.round and not self.fighters[side].is_dead():
            amount = max(1, int(self.fighters[side].max_hp * 0.04))
            dealt = self._apply_environment_damage(side, amount)
            self._log(f"{self.fighters[side].name}: сломанные кости — {dealt} урона за перемещение")
            self._check_result()
        trap = next((item for item in self.traps if item["tile"] == tile), None)
        if trap is None or not self._trap_is_hostile_to(trap, side):
            return
        victims = self._trap_victims(trap)
        affected = [
            uid for uid in victims
            if uid in self.positions and hex_distance(tile, self.positions[uid]) <= trap.get("aoe_radius", 0)
        ]
        self.traps.remove(trap)
        for uid in affected:
            source_side = "enemy" if trap.get("owner") == "enemy" else "player"
            dealt = self._apply_environment_damage(uid, trap["damage"], source_side)
            if trap.get("root_turns") and uid in self.roots:
                self.roots[uid] = max(self.roots.get(uid, 0), trap["root_turns"])
            if trap.get("slow_turns") and uid in self.fighters:
                self.slowed_until[uid] = max(
                    self.slowed_until.get(uid, 0), self.round + trap["slow_turns"]
                )
            if trap.get("knockback"):
                self._knockback(
                    uid,
                    trap["knockback"],
                    origin=previous_tile if previous_tile is not None else tile,
                    reverse=True,
                )
            if trap.get("damage_taken_bonus_percent") and uid in self.fighters:
                self.fighters[uid].next_damage_taken_bonus_percent = max(
                    self.fighters[uid].next_damage_taken_bonus_percent,
                    trap["damage_taken_bonus_percent"],
                )
            self._log(f"{self.fighters[uid].name} попадает в ловушку и получает {dealt} урона")
        self._check_result()

    def _trap_is_hostile_to(self, trap, side):
        if trap.get("owner") == "enemy":
            return side == "player" or side in self.ally_ids
        return side in self.enemy_ids

    def _trap_victims(self, trap):
        if trap.get("owner") == "enemy":
            return ["player", *self.alive_allies()]
        return self.alive_enemies()

    def _apply_environment_damage(self, uid, amount, source_side=None):
        fighter = self.fighters[uid]
        hp_before = fighter.hp
        if uid in self.enemy_ids:
            self.select_target(uid)
            self.engine._mage_take_damage("enemy", amount, source_side=source_side)
        else:
            if source_side == "enemy" and (king_id := self._king_id()) is not None:
                self.select_target(king_id)
            with self._as_player(uid):
                self.engine._mage_take_damage("player", amount, source_side=source_side)
        return max(0, int(hp_before - fighter.hp))

    def _cast(self, caster, card, target):
        """Применить карту бойца caster к бойцу target с учётом подмены сторон движка."""
        engine = self.engine
        receiver = self.fighters[target]
        hp_before = receiver.hp
        if card_role(card) == "enemy":
            self.select_target(target)
            with self._as_player(caster):
                event = engine._resolve_card("player", card)
                engine._apply_pending_mage_effects()
            self.damage_dealt[caster] += max(0, int(hp_before - receiver.hp))
        elif target == caster:
            with self._as_player(caster):
                event = engine._resolve_card("player", card)
                engine._apply_pending_mage_effects()
        else:
            with self._as_player(caster):
                if not engine._can_pay("player", card):
                    return None
                engine._spend_points("player", card)
            with self._as_player(target), self._free_cast():
                event = engine._resolve_card("player", card)
                engine._apply_pending_mage_effects()
        event["target"] = target
        event["hp_change"] = int(receiver.hp - hp_before)
        return event

    def _summon(self, owner, card, tile):
        engine = self.engine
        caster = self.fighters[owner]
        with self._as_player(owner):
            if not engine._can_pay("player", card):
                return None
            engine._spend_points("player", card)
        wisdom = engine._mage_stat(caster, "wisdom")
        harmony = engine._mage_stat(caster, "harmony")
        data = card.effect_data or {}
        self._summon_counter += 1
        sid = f"summon_{self._summon_counter}"
        if card.effect_type == "necromancer_summon":
            summon_kind = str(data.get("summon_kind", ""))
            profiles = {
                "familiar": ("necromancer_familiar", "Фамильяр", 8, 2, 2, 0),
                "lokrif": ("necromancer_lokrif", "Локриф", 17, 4, 3, 8),
                "bone_hero": ("necromancer_bone_hero", "Костяной герой", 45, 20, 3, 10),
                "spirit": ("necromancer_spirit", "Дух", 10, 10, 3, 5),
                "lyrk": ("necromancer_lyrk", "Лирк", 15, 10, 2, 3),
                "grave_zink": ("necromancer_grave_zink", "Могильный зинк", 30, 5, 3, 12),
                "bone_dragon": ("necromancer_bone_dragon", "Костяной дракон", 80, 40, 3, 20),
            }
            if summon_kind not in profiles:
                raise ValueError(f"Неизвестный вид призыва Некроманта: {summon_kind}")
            kind, name, hp, mana, movement, damage = profiles[summon_kind]
            bonus = self.next_summon_bonus or {}
            hp = max(1, int(hp * (100 + int(bonus.get("hp_percent", 0))) / 100))
            damage = int(damage * (100 + int(bonus.get("damage_percent", 0))) / 100)
            summon = {
                "kind": kind, "name": name, "owner": owner,
                "hp": hp, "max_hp": hp, "mana": mana, "max_mana": mana,
                "movement": movement, "damage": damage, "resource_cost": card.resource_cost,
                "damage_reduction_percent": max(
                    int(bonus.get("damage_reduction_percent", 0)),
                    50 if summon_kind == "spirit" else 0,
                ),
                "persistent_damage_reduction": (
                    summon_kind == "spirit"
                    or int(bonus.get("damage_reduction_percent", 0)) > 0
                ),
                "first_damage_reduction": 65 if summon_kind == "lokrif" else 0,
                "cooldowns": {}, "attacks": 0,
            }
            self.next_summon_bonus = None
            text = f"ПРИЗВАН {name.upper()}"
        elif card.effect_type == "mage_golem":
            hp = int(data.get("hp", 16)) + wisdom
            summon = {
                "kind": "golem", "name": "Голем земли", "owner": owner, "hp": hp, "max_hp": hp,
                "damage": int(data.get("damage", 2)) + wisdom,
                "stun_damage": int(data.get("stun_damage", 8)) + wisdom,
                "stun_every": max(1, int(data.get("stun_every", 3))), "attacks": 0,
            }
            text = "ПРИЗВАН ГОЛЕМ"
        elif data.get("summon_spirit"):
            hp = max(1, int(data.get("spirit_hp", FOREST_SPIRIT_HP)))
            summon = {
                "kind": "forest_spirit",
                "name": "Лесной дух",
                "owner": owner,
                "hp": hp,
                "max_hp": hp,
            }
            text = "ПРИЗВАН ЛЕСНОЙ ДУХ"
        else:
            duration = int(data.get("duration", 2)) + harmony // max(1, int(data.get("harmony_duration", 6)))
            summon = {"kind": "cloud", "name": "Громовая туча", "owner": owner,
                      "remaining": max(1, duration), "damage": int(data.get("damage", 3))}
            text = "ПРИЗВАНА ГРОМОВАЯ ТУЧА"
        if caster.profession_type == "necromancer" and "hp" in summon:
            talent_effects = caster._talent_effects
            hp_bonus = (
                int(talent_effects.get("summon_hp_per_intellect", 0))
                * int(caster.intellect)
            )
            damage_bonus = (
                int(talent_effects.get("summon_damage_per_4_wisdom", 0))
                * int(caster.wisdom) // 4
            )
            summon["max_hp"] = int(summon.get("max_hp", summon["hp"])) + hp_bonus
            summon["hp"] = int(summon["hp"]) + hp_bonus
            if "damage" in summon:
                summon["damage"] = int(summon["damage"]) + damage_bonus
        self.summons[sid] = summon
        self.positions[sid] = tuple(tile)
        self.damage_dealt[sid] = 0
        self._refresh_king_auras()
        return {"effect_text": text, "summon": sid, "target": None, "hp_change": 0, "damage": 0}

    def _log_cast(self, name, card, event):
        target = event.get("target")
        suffix = ""
        if target is not None and target in self.fighters and self.fighters[target].name != name:
            suffix = f" → {self.fighters[target].name}"
        text = f"{name}: {card.name}{suffix}"
        if event.get("effect_text"):
            text += f" — {event['effect_text']}"
        self._log(text)
        if target in self.enemy_ids and self.fighters[target].is_dead():
            self._log(f"{self.fighters[target].name} повержен")

    def teleport(self):
        """Телепорт к кристаллу срабатывает в начале следующего хода игрока, если он выживет."""
        if not self.player_can_act():
            return False
        self.teleport_pending = True
        self._log(f"{self.player.name} начинает телепорт к кристаллу возрождения")
        self.end_player_turn()
        return True

    def use_battle_item(self, item_id, target=None):
        """Применить один из предметов магазина припасов к текущему участнику боя."""
        available, message = self.can_use_battle_item(item_id, target)
        if not available:
            return False, message
        if item_id == 4:
            healed = min(20, self.player.max_hp - self.player.hp)
            self.player.hp += healed
            self._log(f"{self.player.name} восстановил {healed} HP")
        elif item_id == 5:
            restored = min(12, self.player.max_mp - self.player.mp)
            self.player.mp += restored
            self._log(f"{self.player.name} восстановил {restored} маны")
        elif item_id == 6:
            enemy = self.fighters[target]
            enemy.take_damage(9)
            self._log(f"Метательный кинжал наносит {enemy.name} 9 урона")
            self._check_result()
            self._retarget_if_dead()
        elif item_id == 52:
            if not self._remove_one_negative_effect("player"):
                return False, "Отрицательный эффект уже отсутствует"
            self.player.mp -= 20
            self._log(f"{self.player.name} снял отрицательный эффект свитком")
        self.last_battle_item_round = self.round
        return True, "Предмет использован"

    def can_use_battle_item(self, item_id, target=None):
        if not self.player_can_act():
            return False, "Сейчас нельзя использовать предмет"
        if (
            self.last_battle_item_round is not None
            and self.round - self.last_battle_item_round < BATTLE_ITEM_COOLDOWN_ROUNDS
        ):
            return False, "Предмет можно использовать только раз в три хода"
        if item_id == 4 and self.player.hp >= self.player.max_hp:
            return False, "Здоровье уже полностью восстановлено"
        if item_id == 5 and self.player.mp >= self.player.max_mp:
            return False, "Мана уже полностью восстановлена"
        if item_id == 6:
            if target not in self.alive_enemies():
                return False, "Выберите живого врага"
            if self._is_behind_enemy_summon_front(self.positions[target]):
                return False, "Нельзя атаковать цель за линией вражеских призывов"
        if item_id == 52:
            if self.player.mp < 20:
                return False, "Для свитка нужно 20 маны"
            if not self._has_negative_effect("player"):
                return False, "На игроке нет отрицательных эффектов"
        if item_id not in (4, 5, 6, 52):
            return False, "Этот предмет нельзя использовать в бою"
        return True, "Предмет готов к использованию"

    def _has_negative_effect(self, side):
        negative_keys = {
            "steal_healing_percent", "mana_regen_debuff", "outgoing_damage_flat",
            "outgoing_damage_percent", "entangled", "mark_damage", "healing_blocked",
            "forbid_damage_cards", "poison_cap_bonus", "dodge_stun",
        }
        return (
            any(any(key in buff for key in negative_keys) for buff in self._state(side, "phys_buffs"))
            or any(self._state(side, attr) for attr in ("bleeds", "poisons", "delayed_hp_loss"))
            or any(not status.get("name", "").endswith("_immunity")
                   for status in self._state(side, "mage_statuses"))
            or bool(self._state(side, "mage_stuns"))
            or bool(self._state(side, "mage_freeze"))
            or bool(self._state(side, "skip_next_turn"))
            or bool(self._state(side, "skip_turn_armed"))
        )

    def _remove_one_negative_effect(self, side):
        negative_keys = {
            "steal_healing_percent", "mana_regen_debuff", "outgoing_damage_flat",
            "outgoing_damage_percent", "entangled", "mark_damage", "healing_blocked",
            "forbid_damage_cards", "poison_cap_bonus", "dodge_stun",
        }
        buffs = self._state(side, "phys_buffs")
        for index, buff in enumerate(buffs):
            key = next((key for key in negative_keys if key in buff), None)
            if key is not None:
                buff.pop(key)
                if not any(name not in {"remaining", "fresh", "expire_after_turn"} for name in buff):
                    buffs.pop(index)
                return True
        for attr in ("bleeds", "poisons", "delayed_hp_loss"):
            effects = self._state(side, attr)
            if effects:
                effects.pop(0)
                return True
        statuses = self._state(side, "mage_statuses")
        for index, status in enumerate(statuses):
            if not status.get("name", "").endswith("_immunity"):
                statuses.pop(index)
                return True
        for attr in ("mage_stuns", "mage_freeze"):
            remaining = int(self._state(side, attr) or 0)
            if remaining:
                state = getattr(self.engine, attr)
                state["player"] = remaining - 1
                return True
        for attr in ("skip_next_turn", "skip_turn_armed"):
            if self._state(side, attr):
                getattr(self.engine, attr)["player"] = False
                return True
        return False

    def end_player_turn(self):
        """Завершить ход игрока; затем ходят союзники, призванные существа и враги."""
        if (
            self.player_draft or self.engine.draw_choices["player"]
            or self.active_side != "player" or self.is_over()
        ):
            return False
        if self.stunned("player"):
            # Следующий ход противников уже не может оглушить снова — без бесконечного стан-лока
            self.engine.mage_stuns["player"] -= 1
            self.stun_immune["player"] = True
            self._log(f"{self.player.name} оглушён и пропускает ход")
        self._finish_side("player")
        if self.is_over():
            return True
        self.active_side = "allies"
        self.allies_turn()
        if self.is_over():
            return True
        self.active_side = "enemy"
        self.enemy_turn()
        return True

    # ------------------------------------------------------------------ союзники и призванные существа

    def allies_turn(self):
        chosen = self.target
        for aid in self.alive_allies():
            self._ally_act(aid)
            if self.is_over():
                return
        for sid in list(self.summons):
            if sid in self.summons and self.alive_enemies():
                self._summon_act(sid)
                self._tick_grave_soil_summon(sid)
            if self.is_over():
                return
        if not self.fighters[chosen].is_dead():
            self.select_target(chosen)
        self._retarget_if_dead()

    def _ally_draw(self, aid):
        pile = self.ally_cards[aid]
        if len(pile["hand"]) >= self.hand_limit:
            return None
        if not pile["deck"] and pile["discard"]:
            pile["deck"], pile["discard"] = pile["discard"], []
            self.rng.shuffle(pile["deck"])
        if not pile["deck"]:
            return None
        card = pile["deck"].pop()
        pile["hand"].append(card)
        return card

    def _ally_regen(self, aid):
        fighter = self.fighters[aid]
        wisdom = int(fighter.stats.get("wisdom", 0))
        fighter.mp = min(fighter.max_mp, fighter.mp + 8 + wisdom // 2)
        if getattr(fighter, "unique_resource_type", None) not in (None, "mana") and hasattr(fighter, "recover_unique_resource"):
            fighter.recover_unique_resource(fighter.level)

    def _ally_act(self, aid):
        fighter = self.fighters[aid]
        self._tick_green_flame(aid)
        if self.is_over():
            return
        if self.stunned(aid):
            self._ally_stash[aid]["mage_stuns"] -= 1
            self.stun_immune[aid] = True
            self._log(f"{fighter.name} оглушён и пропускает ход")
        else:
            self._ally_reposition(aid)
            pile = self.ally_cards[aid]
            hand = list(pile["hand"])
            self.rng.shuffle(hand)
            played = 0
            for card in hand:
                if played >= MAX_CARDS_PER_TURN or self.is_over():
                    break
                target = self._ally_choose_target(aid, card)
                if target is None:
                    continue
                event = self._cast(aid, card, target)
                if event is None:
                    continue
                pile["hand"].remove(card)
                pile["discard"].append(card)
                played += 1
                self._log_cast(fighter.name, card, event)
                self._check_result()
        with self._as_player(aid):
            self.engine.active_side = "player"
            self.engine.complete_side_turn()
            self._tick_root(aid)
        self._check_result()

    def _ally_choose_target(self, aid, card):
        role = card_role(card)
        if role == "summon":
            return None
        with self._as_player(aid):
            if not self.engine.can_select("player", card):
                return None
        targets = self.card_targets(card, caster=aid)
        if not targets:
            return None
        if role == "enemy":
            return self._nearest(aid, targets)
        if role == "self":
            return aid
        ratio = lambda uid: self.fighters[uid].hp / max(1, self.fighters[uid].max_hp)
        wounded = min(targets, key=ratio)
        if card.effect_type in HEAL_EFFECTS and ratio(wounded) >= 1:
            return None
        return wounded if card.effect_type in HEAL_EFFECTS else aid

    def _ally_reposition(self, aid):
        """Лучник держит дистанцию: если враг вплотную, отходит как можно дальше."""
        enemies = self.alive_enemies()
        if not enemies or min(self.dist(aid, eid) for eid in enemies) > 1:
            return
        options = self.reachable_tiles(aid)
        if not options:
            return
        start = self.positions[aid]
        best = max(options, key=lambda tile: (
            min(hex_distance(tile, self.positions[eid]) for eid in enemies),
            -hex_distance(tile, start),
        ))
        self._walk_unit_to(aid, best)

    def _nearest(self, uid, candidates):
        if not candidates:
            return None
        return min(candidates, key=lambda other: (self.dist(uid, other), candidates.index(other)))

    def _approach(self, uid, goal, stop=1, movement_range=MOVE_RANGE):
        """Подойти к goal на расстояние stop, сделав одно перемещение до MOVE_RANGE тайлов."""
        target = self.positions[goal]
        start = self.positions[uid]
        if hex_distance(start, target) <= stop:
            return
        options = self.reachable_tiles(uid, max_steps=movement_range)
        if not options:
            return
        safe_options = [
            tile for tile in options
            if hex_distance(tile, target) >= stop
        ]
        if safe_options:
            best = min(safe_options, key=lambda tile: (
                hex_distance(tile, target),
                (tile[0] - target[0]) ** 2 + (tile[1] - target[1]) ** 2,
                hex_distance(tile, start),
            ))
        else:
            best = max(options, key=lambda tile: (
                hex_distance(tile, target),
                -hex_distance(tile, start),
            ))
        if hex_distance(best, target) < hex_distance(start, target):
            self._walk_unit_to(uid, best, max_steps=movement_range)

    def _tick_summon_regeneration(self, sid):
        summon = self.summons[sid]
        remaining_effects = []
        for effect in summon.get("regenerations", ()):
            if effect.get("fresh"):
                effect["fresh"] = False
                remaining_effects.append(effect)
                continue
            healed = min(
                int(effect["heal_per_turn"]),
                int(summon["max_hp"]) - int(summon["hp"]),
            )
            summon["hp"] += healed
            effect["remaining"] -= 1
            if healed:
                self._log(
                    f"{summon['name']}: {effect.get('card', 'Регенерация')} +{healed} HP"
                )
            if effect["remaining"] > 0:
                remaining_effects.append(effect)
        if remaining_effects:
            summon["regenerations"] = remaining_effects
        else:
            summon.pop("regenerations", None)

    def _summon_act(self, sid):
        summon = self.summons[sid]
        self._tick_summon_regeneration(sid)
        if sid not in self.summons or self.is_over():
            return
        summon = self.summons[sid]
        self._tick_green_flame(sid)
        if sid not in self.summons or self.is_over():
            return
        if summon["kind"] == "necromancer_familiar":
            self._familiar_act(sid)
            return
        if summon["kind"].startswith("necromancer_"):
            self._necromancer_summon_act(sid)
            return
        if summon["kind"] == "forest_spirit":
            self._forest_spirit_act(sid)
            return
        victim = self._nearest(sid, self.alive_enemies())
        if victim is None:
            return
        reach = GOLEM_ATTACK_RANGE if summon["kind"] == "golem" else CLOUD_STRIKE_RANGE
        if summon["kind"] == "wolf":
            reach = 1
            self._approach(sid, victim, stop=reach, movement_range=4)
        else:
            self._approach(sid, victim, stop=reach)
        if self.dist(sid, victim) <= reach:
            if summon["kind"] == "golem":
                summon["attacks"] += 1
                self._summon_hit(sid, victim, summon["damage"])
                if summon["attacks"] % summon["stun_every"] == 0 and not self.fighters[victim].is_dead():
                    self._summon_hit(sid, victim, summon["stun_damage"], label="мощный удар")
            elif summon["kind"] == "wolf":
                self._summon_hit(sid, victim, summon["damage"])
            else:
                self._summon_hit(sid, victim, summon["damage"], electro=True)
        else:
            self._log(f"{summon['name']} идёт к цели {self.fighters[victim].name}")
        if summon["kind"] == "cloud":
            summon["remaining"] -= 1
            if summon["remaining"] <= 0:
                self._remove_summon(sid, "рассеялась")

    def _forest_spirit_act(self, sid):
        allies = ["player", *self.alive_allies()]
        in_range = [uid for uid in allies if self.dist(sid, uid) <= FOREST_SPIRIT_RANGE]
        if not in_range:
            target = min(allies, key=lambda uid: self.dist(sid, uid))
            self._approach(sid, target, stop=FOREST_SPIRIT_RANGE)
            in_range = [uid for uid in allies if self.dist(sid, uid) <= FOREST_SPIRIT_RANGE]
        if not in_range:
            return

        wounded = [uid for uid in in_range if self.fighters[uid].hp < self.fighters[uid].max_hp]
        if wounded:
            target_id = min(wounded, key=lambda uid: (
                self.fighters[uid].hp / max(1, self.fighters[uid].max_hp),
                self.fighters[uid].hp,
            ))
            target = self.fighters[target_id]
            amount = max(1, int(target.max_hp * 0.05))
            with self._as_player(target_id):
                healed = self.engine._heal("player", amount)
            self._log(f"Лесной дух лечит {target.name} на {healed} HP")
            return

        target_id = next((
            uid for uid in in_range
            if not any(
                buff.get("damage_percent", 0) >= 10 and buff.get("remaining", 0) > 0
                for buff in self._state(uid, "phys_buffs")
            )
        ), None)
        if target_id is not None:
            with self._as_player(target_id):
                self.engine._add_buff("player", 2, damage_percent=10)
                fighter = self.fighters[target_id]
                fighter.mage_damage_bonus_ratio = max(
                    0,
                    getattr(fighter, "mage_damage_bonus_ratio", 1) + 0.10,
                )
                self.engine._queue_mage_effect("player", "damage_bonus", percent=10, duration=2)
                self.engine._apply_pending_mage_effects()
            self._log(f"Лесной дух усиливает урон {self.fighters[target_id].name} на 10% на 2 хода")
            return

        target_id = next((
            uid for uid in in_range
            if not self._state(uid, "mage_shields") and not self._state(uid, "phys_shields")
        ), None)
        if target_id is not None:
            amount = max(1, int(self.fighters[target_id].hp * 0.08))
            with self._as_player(target_id):
                self.engine._add_mage_shield("player", amount, 2)
            self._log(f"Лесной дух даёт {self.fighters[target_id].name} щит {amount} HP")

    def _summon_hit(self, sid, eid, amount, electro=False, label="удар"):
        engine = self.engine
        summon = self.summons[sid]
        self.select_target(eid)
        victim = self.fighters[eid]
        hp_before = victim.hp
        engine._mage_take_damage("enemy", amount, source_side="player")
        if electro:
            # Summons hit before two status-expiration passes at the round boundary.
            engine._add_mage_status("enemy", "электро", 3)
            engine._apply_mage_status_reaction("enemy", "электро", {"damage": amount, "effect_text": ""})
        dealt = max(0, int(hp_before - victim.hp))
        self.damage_dealt[sid] += dealt
        self._log(f"{summon['name']}: {label} по {victim.name} — {dealt} урона")
        if victim.is_dead():
            self._log(f"{victim.name} повержен")
        self._check_result()

    def _familiar_act(self, sid):
        summon = self.summons[sid]
        owner = summon.get("owner", "player")
        allies = [uid for uid in (owner, *self.alive_allies()) if uid in self.fighters]
        if not allies:
            return
        if min(self.dist(sid, uid) for uid in allies) > 2:
            target = min(allies, key=lambda uid: self.dist(sid, uid))
            self._approach(sid, target, stop=2, movement_range=summon.get("movement", 2))
        self._refresh_king_auras()

    def _necromancer_summon_act(self, sid):
        summon = self.summons[sid]
        kind = summon["kind"]
        owner = summon.get("owner", "player")
        owner_fighter = self.fighters.get(owner)
        if kind == "necromancer_bone_hero" and owner_fighter is not None:
            if owner_fighter.max_hp - owner_fighter.hp >= int(summon["max_hp"] * 0.5):
                healed = min(
                    owner_fighter.max_hp - owner_fighter.hp,
                    int(summon["max_hp"] * 0.5),
                )
                owner_fighter.hp += healed
                self.protection_effects[owner] = {
                    "percent": 10, "expires_round": self.round + 2,
                }
                summon["hp"] = 0
                self._remove_summon(sid, "пожертвовал собой ради призывателя")
                self._refresh_king_auras()
                self._log(f"Костяной герой лечит призывателя на {healed} HP")
                return
        if kind == "necromancer_lokrif" and owner_fighter is not None:
            cooldowns = summon.setdefault("cooldowns", {})
            if (
                owner_fighter.hp / max(1, owner_fighter.max_hp) <= 0.25
                and self.round >= cooldowns.get("support", 0)
            ):
                use_heal = self.rng.choice((True, False))
                if use_heal and owner_fighter.hp < owner_fighter.max_hp:
                    healed = min(
                        owner_fighter.max_hp - owner_fighter.hp,
                        int(summon["max_hp"] * 0.5),
                    )
                    owner_fighter.hp += healed
                    self._log(f"Локриф лечит призывателя на {healed} HP")
                else:
                    self.protection_effects[owner] = {
                        "percent": 30, "expires_round": self.round + 2,
                    }
                    self._refresh_king_auras()
                    self._log("Локриф защищает призывателя на 30%")
                cooldowns["support"] = self.round + 2
                return
        if kind == "necromancer_grave_zink" and summon["hp"] <= 10:
            summon["hp"] = min(summon["max_hp"], summon["hp"] + 10)
            self._log("Могильный зинк восстанавливает 10 HP")
            return
        if (
            kind == "necromancer_bone_dragon"
            and summon["hp"] / max(1, summon["max_hp"]) < 0.2
        ):
            summon["hp"] = min(
                summon["max_hp"], summon["hp"] + int(summon["max_hp"] * 0.15)
            )
            return
        victim = self._nearest(sid, self.alive_enemies())
        if victim is None:
            return
        if kind == "necromancer_bone_hero" and self.dist(sid, victim) == 2:
            destination = min(
                self.reachable_tiles(sid, max_steps=2),
                key=lambda tile: hex_distance(tile, self.positions[victim]),
                default=None,
            )
            if destination is not None:
                self._walk_unit_to(sid, destination, max_steps=2)
                if self.positions[sid] != destination:
                    return
                for enemy_id in self.alive_enemies():
                    if self.dist(victim, enemy_id) <= 1:
                        self._summon_hit(sid, enemy_id, 8, label="рывок костяного героя")
                return
        if (
            kind == "necromancer_spirit"
            and self.dist(sid, victim) <= 3
            and self.round % 3 == 0
        ):
            self._spirit_draw()
            return
        if self.is_over() or victim not in self.fighters:
            return
        movement = int(summon.get("movement", 2))
        attack_range = 1
        if kind == "necromancer_spirit":
            attack_range = 2
        if kind == "necromancer_lyrk" and self.dist(sid, victim) == 3:
            self.roots[victim] = max(self.roots.get(victim, 0), 1)
            self._log("Лирк накладывает корни")
            return
        if kind == "necromancer_bone_dragon":
            attack_range = 3
        self._approach(sid, victim, stop=attack_range, movement_range=movement)
        if self.dist(sid, victim) > attack_range:
            self._log(f"{summon['name']} приближается к {self.fighters[victim].name}")
            return

        cooldowns = summon.setdefault("cooldowns", {})
        if kind == "necromancer_spirit":
            use_stun = self.round >= cooldowns.get("stun", 0)
            if use_stun:
                self._summon_hit(sid, victim, 5, label="удар духа")
                if not self.fighters[victim].is_dead():
                    self.engine.mage_stuns["enemy"] = max(
                        self.engine.mage_stuns.get("enemy", 0), 1
                    )
                cooldowns["stun"] = self.round + 4
            elif self.round >= cooldowns.get("knockback", 0):
                self._summon_hit(sid, victim, 8, label="удар духа")
                self._knockback(victim, 1, origin=self.positions[sid])
                cooldowns["knockback"] = self.round + 2
            else:
                self._spirit_draw()
            return
        if kind == "necromancer_lyrk":
            summon["attacks"] += 1
            if summon["attacks"] % 2:
                self._summon_hit(sid, victim, 3, label="укус Лирка")
                self._add_green_flame(victim, 1)
            else:
                self._summon_hit(sid, victim, 6, label="ядовитый укус Лирка")
                self.select_target(victim)
                self.engine._add_poison("player", 1)
            return
        if kind == "necromancer_grave_zink":
            target = self.fighters[victim]
            self._summon_hit(sid, victim, summon["damage"], label="удар Зинка")
            drained = min(target.mp, 15)
            target.mp -= drained
            if drained == 0 and not target.is_dead():
                self._summon_hit(sid, victim, 8, label="выжигание маны")
            return
        if kind == "necromancer_bone_dragon":
            attack_count = summon.get("attacks", 0) + 1
            summon["attacks"] = attack_count
            if attack_count % 4 == 0:
                for enemy_id in self.alive_enemies():
                    if self.dist(sid, enemy_id) <= 1:
                        self._summon_hit(sid, enemy_id, 6, label="драконий рёв")
                        if not self.fighters[enemy_id].is_dead():
                            self.engine.mage_stuns["enemy"] = max(
                                self.engine.mage_stuns.get("enemy", 0), 1
                            )
                return
            if attack_count % 2 == 0:
                for enemy_id in self._cone_targets(sid, victim, 3):
                    self._summon_hit(sid, enemy_id, 5, label="зелёное пламя")
                    self._add_green_flame(enemy_id, 1)
                return
        if kind == "necromancer_bone_hero":
            summon["attacks"] += 1
            if summon["attacks"] % 2:
                self._summon_hit(sid, victim, 10, label="удар костяного героя")
            else:
                self._summon_hit(sid, victim, 7, label="удар костяного героя")
                summon["hp"] = min(summon["max_hp"], summon["hp"] + 5)
            return
        self._summon_hit(sid, victim, summon["damage"], label="атака")
        if kind == "necromancer_lokrif":
            self.select_target(victim)
            self.engine._add_poison("player", 2)

    def _cone_targets(self, source, direction_target, radius):
        source_q, source_r = axial_coordinates(self.positions[source])
        target_q, target_r = axial_coordinates(self.positions[direction_target])
        target_q -= source_q
        target_r -= source_r
        target_x = math.sqrt(3) * (target_q + target_r / 2)
        target_y = 1.5 * target_r
        target_length = math.hypot(target_x, target_y)
        if target_length == 0:
            return [direction_target]
        result = []
        for enemy_id in self.alive_enemies():
            q, r = axial_coordinates(self.positions[enemy_id])
            x = math.sqrt(3) * (q - source_q + (r - source_r) / 2)
            y = 1.5 * (r - source_r)
            distance = self.dist(source, enemy_id)
            length = math.hypot(x, y)
            if (
                0 < distance <= radius
                and length > 0
                and (x * target_x + y * target_y) / (length * target_length) >= 0.5
            ):
                result.append(enemy_id)
        return result or [direction_target]

    def _tick_green_flame(self, uid):
        stacks = self.green_flame.get(uid)
        if not stacks:
            return
        current_hp = (
            self.summons[uid]["hp"] if uid in self.summons
            else self.fighters[uid].hp if uid in self.fighters
            else 0
        )
        if current_hp <= 0:
            return
        amount = max(1, int(current_hp * sum(stacks) / 100))
        if uid in self.summons:
            self.summons[uid]["hp"] = max(0, current_hp - amount)
            if self.summons[uid]["hp"] <= 0:
                self._remove_summon(uid, "сгорел в зелёном огне")
        elif uid in self.fighters:
            self._apply_environment_damage(uid, amount)
            self._check_result()
        self._log(f"{self.unit_name(uid) if uid in self.summons or uid in self.fighters else uid}: зелёный огонь — {amount} урона")

    def _spirit_draw(self):
        if len(self.engine.hands["player"]) >= self.hand_limit:
            restored = int(self.player.unique_resource_max * 0.05)
            self.player.gain_unique_resource(restored)
            self._log(f"Дух: рука заполнена, +{restored} некротизма")
        elif self.engine.draw_next_turn_card("player") is not None:
            self._log("Дух вытягивает карту призывателю")

    def _remove_summon(self, sid, reason):
        summon = self.summons.pop(sid)
        self.positions.pop(sid, None)
        if summon.get("hp", 1) <= 0 or "поглощён" in reason:
            self._grant_necrotism_for_death(sid)
        if summon.get("kind") == "necromancer_familiar" and summon.get("last_attacker") in self.fighters:
            self._add_green_flame(summon["last_attacker"], 1)
        self._log(f"{summon['name']} {reason}")

    # ------------------------------------------------------------------ ход противников

    def _enemy_victims(self):
        """Враги атакуют бойцов и приземлённые призывы; туча парит над ареной."""
        grounded_summons = [
            sid for sid, summon in self.summons.items()
            if summon.get("kind") != "cloud"
        ]
        return ["player", *self.alive_allies(), *grounded_summons]

    def _creature_card_targets(self, eid, card):
        if card.protect_king:
            king_id = self._king_id()
            return [king_id] if king_id is not None else []
        if card.heal_allies_percent_of_target_max_hp:
            return self.alive_enemies()
        if (card.teleport_behind or card.root_turns or card.stun_turns
                or card.damage_taken_bonus_percent or card.execute_below_hp_percent
                or card.teleport_farthest_below_hp_percent or card.trap_damage
                or card.banner_duration or card.kneel_radius):
            return ["player", *self.alive_allies()]
        return self._enemy_victims()

    def enemy_turn(self):
        if self.is_over():
            return
        self._refresh_king_auras()
        chosen = self.target
        for eid in list(self.alive_enemies()):
            self.select_target(eid)
            fighter = self.fighters[eid]
            self._tick_green_flame(eid)
            if self.is_over():
                return
            if self.stunned(eid):
                self.engine.mage_stuns["enemy"] -= 1
                self._log(f"{fighter.name} оглушён и пропускает ход")
            else:
                below_retreat_threshold = (
                    eid not in self.enemy_summons
                    and fighter.hp / max(1, fighter.max_hp) < 0.25
                )
                if below_retreat_threshold and self._enemy_try_heal(eid):
                    pass
                elif below_retreat_threshold:
                    self._retreat(eid)
                    self._log(f"{fighter.name} отступает, чтобы спастись")
                elif self.enemy_summon_kinds.get(eid) == "skull":
                    self._skull_turn(eid)
                else:
                    victim = self._nearest(eid, self._enemy_victims())
                    if victim is not None:
                        self._enemy_move(eid)
                    deck = self.enemy_decks[eid]
                    available_cards = [
                        card for card in deck
                        if self.round - self.enemy_card_last_used[eid].get(card.key, -10**6)
                        >= max(1, card.cooldown_turns)
                        and (
                            not card.heal_percent
                            or (fighter.hp < fighter.max_hp
                                and fighter.hp / max(1, fighter.max_hp) <= card.heal_threshold)
                        )
                        and (
                            not card.heal_allies_percent_of_caster_hp
                            and not card.heal_allies_percent_of_target_max_hp
                            or any(
                                self.fighters[ally].hp < self.fighters[ally].max_hp
                                for ally in self.alive_enemies()
                            )
                        )
                        and (
                            not card.sacrifice_heal_percent
                            or (
                                fighter.hp / max(1, fighter.max_hp) <= card.sacrifice_threshold
                                and self._sacrifice_heal_target(eid) is not None
                            )
                        )
                        and (
                            not card.summon_wolf
                            or not any(
                                self.enemy_summon_kinds.get(wolf) == "wolf"
                                and wolf in self.alive_enemies()
                                for wolf in self.enemy_summons
                            )
                        )
                        and (
                            not card.summon_kind
                            or any(
                                self.in_arena(tile) and not self.occupied(tile)
                                for tile in hex_neighbors(self.positions[eid])
                            )
                        )
                        and (
                            not card.protect_king
                            or (
                                (king_id := self._king_id()) is not None
                                and self.fighters[king_id].next_damage_reduction_percent < 20
                            )
                        )
                        and (
                            not card.teleport_to_king_below_hp_percent
                            or (
                                (king_id := self._king_id()) is not None
                                and fighter.hp / max(1, fighter.max_hp)
                                    <= card.teleport_to_king_below_hp_percent / 100
                            )
                        )
                        and (
                            not card.teleport_farthest_below_hp_percent
                            or fighter.hp / max(1, fighter.max_hp)
                                <= card.teleport_farthest_below_hp_percent / 100
                        )
                        and (
                            not card.execute_below_hp_percent
                            or any(
                                self.fighters[target].hp / max(1, self.fighters[target].max_hp)
                                    <= card.execute_below_hp_percent / 100
                                and self.dist(eid, target) <= int(card.range or 999999)
                                for target in ["player", *self.alive_allies()]
                            )
                        )
                        and (
                            not card.kneel_radius
                            or (
                                (king_id := self._king_id()) is not None
                                and any(self.dist(king_id, target) <= card.kneel_radius
                                        for target in ["player", *self.alive_allies()])
                            )
                        )
                        and (
                            not card.trap_damage
                            or any(
                                self.in_arena(tile) and not self.occupied(tile)
                                for tile in hex_neighbors(self.positions["player"])
                            )
                        )
                        and (
                            fighter.name.startswith("Кобольд")
                            or not (
                                card.damage or card.stun_turns or card.root_turns
                                or card.damage_taken_bonus_percent or card.execute_below_hp_percent
                            )
                            or any(
                                card.range is None or self.dist(eid, target) <= card.range
                                for target in self._creature_card_targets(eid, card)
                            )
                        )
                    ]
                    if available_cards:
                        card = self.rng.sample(
                            available_cards, min(ENEMY_CARDS_PER_TURN, len(available_cards))
                        )[0]
                        victim = (eid if (
                            card.heal_percent or card.summon_wolf or card.summon_kind
                            or card.heal_allies_percent_of_caster_hp
                            or card.heal_allies_percent_of_target_max_hp
                            or card.sacrifice_heal_percent
                        )
                                  else self._nearest(eid, self._creature_card_targets(eid, card)))
                        if victim is not None:
                            self._resolve_creature_card(card, eid, victim)
                        if self.is_over():
                            return
            self._finish_side("enemy")
            if self.is_over():
                return
        self.select_target(chosen)
        self._retarget_if_dead()
        self.stun_immune = {uid: False for uid in self.stun_immune}
        if not self.is_over():
            self._start_round()

    def _enemy_move(self, eid):
        self._refresh_king_auras()
        victim = self._nearest(eid, self._enemy_victims())
        if victim is not None:
            if self.fighters[eid].name.startswith("Некромансер"):
                distance = self.dist(eid, victim)
                if NECROMANCER_MIN_RANGE <= distance <= NECROMANCER_MAX_RANGE:
                    return
                if distance < NECROMANCER_MIN_RANGE:
                    options = self.reachable_tiles(eid)
                    preferred = [
                        tile for tile in options
                        if NECROMANCER_MIN_RANGE <= hex_distance(tile, self.positions[victim])
                        <= NECROMANCER_MAX_RANGE
                    ]
                    if preferred:
                        destination = min(
                            preferred,
                            key=lambda tile: (
                                abs(hex_distance(tile, self.positions[victim]) - 3.5),
                                hex_distance(tile, self.positions[eid]),
                            ),
                        )
                        self._walk_unit_to(eid, destination)
                    return
                self._approach(eid, victim, stop=NECROMANCER_MAX_RANGE)
                return
            movement_range = (
                int(getattr(self.fighters[eid], "arena_move_range", MOVE_RANGE))
                + int(getattr(self.fighters[eid], "arena_move_range_bonus", 0))
            )
            self._approach(eid, victim, movement_range=movement_range)

    def _enemy_try_heal(self, eid):
        fighter = self.fighters[eid]
        for card in self.enemy_decks[eid]:
            can_self_heal = (
                card.heal_percent and fighter.hp < fighter.max_hp
                and fighter.hp / max(1, fighter.max_hp) <= card.heal_threshold
            )
            can_team_heal = (
                card.heal_allies_percent_of_caster_hp
                and any(
                    self.fighters[ally].hp < self.fighters[ally].max_hp
                    for ally in self.alive_enemies()
                )
            )
            can_team_heal = can_team_heal or (
                card.heal_allies_percent_of_target_max_hp
                and any(
                    self.fighters[ally].hp < self.fighters[ally].max_hp
                    for ally in self.alive_enemies()
                )
            )
            if not (can_self_heal or can_team_heal):
                continue
            last_used = self.enemy_card_last_used[eid].get(card.key, -10**6)
            if self.round - last_used < max(1, card.cooldown_turns):
                continue
            self._resolve_creature_card(card, eid, eid)
            return True
        return False

    def _sacrifice_heal_target(self, eid):
        eligible = [
            uid for uid in self.alive_enemies()
            if uid != eid and (
                self.enemy_summon_kinds.get(uid) == "skeleton"
                or self.fighters[uid].name.startswith("Некромансер")
            )
        ]
        injured = [uid for uid in eligible if self.fighters[uid].hp < self.fighters[uid].max_hp]
        return min(
            injured,
            key=lambda uid: self.fighters[uid].hp / max(1, self.fighters[uid].max_hp),
            default=None,
        )

    def _skull_turn(self, eid):
        victim = self._nearest(eid, self._enemy_victims())
        if victim is None:
            return
        self._enemy_move(eid)
        victim = self._nearest(eid, self._enemy_victims())
        if victim is not None and self.dist(eid, victim) <= SKULL_EXPLOSION.range:
            self._resolve_creature_card(SKULL_EXPLOSION, eid, victim)
            self.fighters[eid].hp = 0
            self._log(f"{self.fighters[eid].name} взрывается")

    def _retreat(self, eid):
        victims = self._enemy_victims()
        options = self.reachable_tiles(
            eid, max_steps=4 if eid in self.enemy_summons else MOVE_RANGE
        )
        if not victims or not options:
            return
        start = self.positions[eid]
        destination = max(
            options,
            key=lambda tile: (
                min(hex_distance(tile, self.positions[victim]) for victim in victims),
                -hex_distance(tile, start),
            ),
        )
        self._walk_unit_to(
            eid, destination, max_steps=4 if eid in self.enemy_summons else MOVE_RANGE
        )

    def _spawn_enemy_wolf(self, eid):
        available = [
            tile for tile in hex_neighbors(self.positions[eid])
            if self.in_arena(tile) and not self.occupied(tile)
        ]
        if not available:
            self._log(f"{self.fighters[eid].name}: нет места для волка")
            return False
        wolf_id = f"wolf_{len(self.enemy_summons) + 1}"
        wolf = Fighter("Волк", 1, "warrior")
        wolf.max_hp = WOLF_MAX_HP
        wolf.hp = WOLF_MAX_HP
        wolf.arena_move_range = 4
        wolf_tile = min(available, key=lambda tile: hex_distance(tile, self.positions["player"]))
        self._add_enemy_summon(wolf_id, wolf, wolf_tile, WOLF_DECK, "wolf")
        player_q, player_r = axial_coordinates(self.positions["player"])
        wolf_q, wolf_r = axial_coordinates(wolf_tile)
        direction = (wolf_q - player_q, wolf_r - player_r)
        if direction != (0, 0):
            self.wolf_barrier = {"wolf_id": wolf_id, "direction": direction}
        self._log(f"{self.fighters[eid].name} призывает волка")
        return True

    def _add_enemy_summon(self, summon_id, fighter, tile, deck, kind):
        self.enemy_ids.append(summon_id)
        self.enemy_summons.add(summon_id)
        self.enemy_summon_kinds[summon_id] = kind
        self.fighters[summon_id] = fighter
        self.positions[summon_id] = tuple(tile)
        self.damage_dealt[summon_id] = 0
        self.enemy_decks[summon_id] = deck
        self.enemy_card_last_used[summon_id] = {}
        self._stash[summon_id] = deepcopy(self._fresh)
        self.stun_immune[summon_id] = False
        self.roots[summon_id] = 0

    def _spawn_enemy_minion(self, eid, kind):
        available = [
            tile for tile in hex_neighbors(self.positions[eid])
            if self.in_arena(tile) and not self.occupied(tile)
        ]
        if not available:
            self._log(f"{self.fighters[eid].name}: нет места для призыва")
            return False

        summon_id = f"{kind}_{len(self.enemy_summons) + 1}"
        if kind == "skeleton":
            fighter, deck = create_skeleton(f"Скелет-призыв {len(self.enemy_summons) + 1}"), SKELETON_DECK
        elif kind == "skeleton_guard":
            fighter, deck = create_skeleton_guard(), SKELETON_GUARD_DECK
        elif kind == "bone_dog":
            fighter, deck = create_bone_dog(), BONE_DOG_DECK
        elif kind == "skull":
            fighter, deck = create_skull(), ()
        else:
            raise ValueError(f"Неизвестный вид призыва: {kind}")
        fighter.arena_move_range = 4
        tile = min(available, key=lambda candidate: hex_distance(candidate, self.positions["player"]))
        self._add_enemy_summon(summon_id, fighter, tile, deck, kind)
        self._log(f"{self.fighters[eid].name} призывает {fighter.name.lower()}")
        return summon_id

    def _resolve_creature_card(self, card, eid="enemy", victim="player"):
        name = self.fighters[eid].name
        if card.protect_king:
            king_id = self._king_id()
            if king_id is None:
                return
            self.fighters[king_id].next_damage_reduction_percent = 20
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name}: {card.name} — следующий урон по королю снижен на 20%")
            return
        if card.teleport_to_king_below_hp_percent:
            king_id = self._king_id()
            if king_id is None:
                return
            king_tile = self.positions[king_id]
            destinations = [
                tile for tile in hex_neighbors(king_tile)
                if self.in_arena(tile) and not self.occupied(tile, ignore=eid)
            ]
            if destinations:
                destination = min(
                    destinations,
                    key=lambda tile: hex_distance(tile, self.positions["player"]),
                )
                _, _, width, height = self.arena_rect
                if self._walk_unit_to(
                    eid, destination, max_steps=width * height,
                    movement_action=False,
                ):
                    self.enemy_card_last_used[eid][card.key] = self.round
                    self._log(f"{name}: {card.name} — перемещение к королю")
            return
        if card.heal_allies_percent_of_target_max_hp:
            allies = [
                ally_id for ally_id in self.alive_enemies()
                if self.dist(eid, ally_id) <= 3
            ]
            for ally_id in allies:
                ally = self.fighters[ally_id]
                ally.hp = min(
                    ally.max_hp,
                    ally.hp + int(ally.max_hp * card.heal_allies_percent_of_target_max_hp),
                )
                ally.next_damage_reduction_percent = max(
                    ally.next_damage_reduction_percent,
                    card.shield_next_damage_percent,
                )
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name}: {card.name} — лечение союзников и защита от следующего урона")
            return
        if card.trap_damage:
            candidates = [
                tile
                for y in range(self.positions["player"][1] - 2, self.positions["player"][1] + 3)
                for x in range(self.positions["player"][0] - 2, self.positions["player"][0] + 3)
                for tile in [(x, y)]
                if hex_distance(tile, self.positions[eid]) <= int(card.range or 2)
                and hex_distance(tile, self.positions["player"]) <= 2
                and self.in_arena(tile) and not self.occupied(tile)
                and not any(trap["tile"] == tile for trap in self.traps)
            ]
            if candidates:
                tile = min(candidates, key=lambda pos: hex_distance(pos, self.positions["player"]))
                self.traps.append({
                    "tile": tile, "owner": "enemy", "damage": card.trap_damage,
                    "aoe_radius": card.trap_aoe_radius,
                    "damage_taken_bonus_percent": card.trap_damage_taken_bonus_percent,
                    "root_turns": 0,
                })
                self.enemy_card_last_used[eid][card.key] = self.round
                self._log(f"{name}: {card.name} — ловушка установлена")
            return
        if card.banner_duration:
            candidates = [
                tile
                for y in range(self.positions[eid][1] - int(card.range or 2),
                               self.positions[eid][1] + int(card.range or 2) + 1)
                for x in range(self.positions[eid][0] - int(card.range or 2),
                               self.positions[eid][0] + int(card.range or 2) + 1)
                for tile in [(x, y)]
                if hex_distance(tile, self.positions[eid]) <= int(card.range or 2)
                and self.in_arena(tile) and not self.occupied(tile)
                and tile not in self.barriers
            ]
            if candidates:
                tile = min(candidates, key=lambda pos: hex_distance(pos, self.positions["player"]))
                self.barriers[tile] = card.banner_duration
                self.king_flags.append({
                    "tile": tile, "radius": card.banner_aura_radius,
                    "expires_round": self.round + card.banner_duration,
                })
                self._refresh_king_auras()
                self.enemy_card_last_used[eid][card.key] = self.round
                self._log(f"{name}: {card.name} — знамя поднято")
            return
        if card.kneel_radius:
            king_id = self._king_id()
            if king_id is None:
                return
            targets = ["player", *self.alive_allies()]
            affected = [
                uid for uid in targets
                if self.dist(king_id, uid) <= card.kneel_radius
            ]
            for uid in affected:
                self.kneeling[uid] = self.round + int(card.stun_turns) + 1
                self.fighters[uid].next_damage_taken_bonus_percent = max(
                    self.fighters[uid].next_damage_taken_bonus_percent, 20
                )
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name}: {card.name} — {len(affected)} бойцов повержены ниц")
            return
        if card.teleport_farthest_below_hp_percent:
            targets = ["player", *self.alive_allies()]
            target_id = max(targets, key=lambda uid: self.dist(eid, uid), default=None)
            if target_id is None:
                return
            destinations = [
                tile for tile in hex_neighbors(self.positions[target_id])
                if self.in_arena(tile) and not self.occupied(tile, ignore=eid)
            ]
            if not destinations:
                return
            destination = min(
                destinations,
                key=lambda tile: hex_distance(tile, self.positions[target_id]),
            )
            _, _, width, height = self.arena_rect
            if not self._walk_unit_to(
                eid, destination, max_steps=width * height,
                movement_action=False,
            ):
                return
            dealt = self._apply_environment_damage(target_id, card.damage, source_side="enemy")
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name}: {card.name} — {dealt} урона {self.fighters[target_id].name}")
            self._check_result()
            return
        card_range = getattr(card, "range", None)
        if victim is not None and card_range is not None and self.dist(eid, victim) > card_range:
            self._log(f"{name}: {card.name} — слишком далеко")
            return
        if card.heal_percent:
            fighter = self.fighters[eid]
            healed = min(
                fighter.max_hp - fighter.hp,
                max(1, int(fighter.max_hp * card.heal_percent)),
            )
            if healed <= 0:
                return
            fighter.hp += healed
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name}: лечение — восстановлено {healed} HP")
            return
        if card.heal_allies_percent_of_caster_hp:
            healing = max(1, int(self.fighters[eid].hp * card.heal_allies_percent_of_caster_hp))
            healed_allies = []
            for ally_id in self.alive_enemies():
                ally = self.fighters[ally_id]
                healed = min(ally.max_hp - ally.hp, healing)
                if healed > 0:
                    ally.hp += healed
                    healed_allies.append(f"{ally.name}: +{healed} HP")
            if healed_allies:
                self.enemy_card_last_used[eid][card.key] = self.round
                self._log(f"{name}: лечение — {'; '.join(healed_allies)}")
            return
        if card.sacrifice_heal_percent:
            target_id = self._sacrifice_heal_target(eid)
            if target_id is None:
                return
            target = self.fighters[target_id]
            healed = min(
                target.max_hp - target.hp,
                max(1, int(self.fighters[eid].max_hp * card.sacrifice_heal_percent)),
            )
            target.hp += healed
            self.fighters[eid].hp = 0
            self.enemy_card_last_used[eid][card.key] = self.round
            self._log(f"{name} жертвует собой и лечит {target.name} на {healed} HP")
            return
        if card.summon_wolf:
            if self._spawn_enemy_wolf(eid):
                self.enemy_card_last_used[eid][card.key] = self.round
            return
        if card.summon_kind:
            if self._spawn_enemy_minion(eid, card.summon_kind):
                self.enemy_card_last_used[eid][card.key] = self.round
            return
        if victim is None:
            return
        if card.teleport_behind:
            target_tile = self.positions[victim]
            old_tile = self.positions[eid]
            behind_tiles = [
                tile for tile in hex_neighbors(target_tile)
                if self.in_arena(tile) and not self.occupied(tile, ignore=eid)
            ]
            left, top, width, height = self.arena_rect
            available = behind_tiles or [
                (x, y)
                for y in range(top, top + height)
                for x in range(left, left + width)
                if self.in_arena((x, y)) and not self.occupied((x, y), ignore=eid)
            ]
            if not available:
                self._log(f"{name}: нет свободной клетки для прыжка")
                return
            destination = min(
                available,
                key=lambda tile: (
                    hex_distance(tile, target_tile),
                    -hex_distance(tile, old_tile) if behind_tiles else hex_distance(tile, old_tile),
                ),
            )
            _, _, width, height = self.arena_rect
            if not self._walk_unit_to(
                eid, destination, max_steps=width * height,
                movement_action=False,
            ):
                return
        if victim in self.summons and not card.aoe_radius:
            summon = self.summons[victim]
            if card.damage:
                if (
                    summon.get("kind") == "necromancer_lyrk"
                    and self.rng.random() < 0.20
                ):
                    self._log(f"{summon['name']} уклоняется от атаки")
                    return
                damage = int(card.damage)
                reduction = int(
                    summon.get("first_damage_reduction", 0)
                    or summon.get("damage_reduction_percent", 0)
                )
                if reduction:
                    damage = max(1, int(damage * (100 - reduction) / 100))
                    if summon.get("first_damage_reduction"):
                        summon["first_damage_reduction"] = 0
                    elif not summon.get("persistent_damage_reduction"):
                        summon["damage_reduction_percent"] = 0
                dealt = min(int(summon["hp"]), damage)
                summon["hp"] -= damage
                summon["last_attacker"] = eid
                self.damage_dealt[eid] += dealt
                self._log(f"{name}: {card.name} — {dealt} урона ({summon['name']})")
                if summon["hp"] <= 0:
                    self._remove_summon(victim, "разрушен")
            if card.stun_turns:
                self._log(f"{name}: {card.name} — {summon['name']} не поддаётся оглушению")
            return
        affected = [victim]
        if card.aoe_radius:
            center = self.positions[eid] if card.aoe_center_self else self.positions[victim]
            affected = [
                uid for uid in self._enemy_victims()
                if hex_distance(center, self.positions[uid]) <= card.aoe_radius
            ]
        for target_id in affected:
            if target_id in self.summons:
                summon = self.summons[target_id]
                if card.damage:
                    if (
                        summon.get("kind") == "necromancer_lyrk"
                        and self.rng.random() < 0.20
                    ):
                        self._log(f"{summon['name']} уклоняется от атаки")
                        continue
                    damage = int(card.damage)
                    reduction = int(
                        summon.get("first_damage_reduction", 0)
                        or summon.get("damage_reduction_percent", 0)
                    )
                    if reduction:
                        damage = max(1, int(damage * (100 - reduction) / 100))
                        if summon.get("first_damage_reduction"):
                            summon["first_damage_reduction"] = 0
                        elif not summon.get("persistent_damage_reduction"):
                            summon["damage_reduction_percent"] = 0
                    dealt = min(int(summon["hp"]), damage)
                    summon["hp"] -= damage
                    summon["last_attacker"] = eid
                    self.damage_dealt[eid] += dealt
                    self._log(f"{name}: {card.name} — {dealt} урона ({summon['name']})")
                    if summon["hp"] <= 0:
                        self._remove_summon(target_id, "разрушен")
                continue
            target = self.fighters[target_id]
            suffix = "" if target_id == "player" else f" по {target.name}"
            if (card.damage or card.stun_turns or card.root_turns or card.damage_taken_bonus_percent) and self._creature_attack_dodged(
                eid, target_id, card
            ):
                continue
            if card.damage:
                hp_before = target.hp
                with self._as_player(target_id):
                    self.engine._mage_take_damage("player", card.damage, source_side="enemy")
                if (card.execute_below_hp_percent and not target.is_dead()
                        and target.hp / max(1, target.max_hp) <= card.execute_below_hp_percent / 100):
                    target.hp = 0
                dealt = max(0, int(hp_before - target.hp))
                self.damage_dealt[eid] += dealt
                self._log(f"{name}: {card.name} — {dealt} урона{suffix}")
                if target_id != "player" and target.is_dead():
                    self._log(f"{target.name} повержен")
            if target_id == victim and card.stun_turns and not target.is_dead():
                if self.stun_immune.get(target_id):
                    self._log(f"{name}: {card.name} — {target.name} устойчив к оглушению")
                else:
                    with self._as_player(target_id):
                        self.engine.mage_stuns["player"] = max(self.engine.mage_stuns["player"], card.stun_turns)
                    self._log(f"{name}: {card.name} — {target.name} оглушён на {card.stun_turns} ход")
            if target_id == victim and card.root_turns and not target.is_dead():
                self.roots[target_id] = max(self.roots.get(target_id, 0), card.root_turns)
                self._log(f"{name}: {card.name} — {target.name} опутан корнями на {card.root_turns} хода")
            if target_id == victim and card.damage_taken_bonus_percent and not target.is_dead():
                target.next_damage_taken_bonus_percent = max(
                    target.next_damage_taken_bonus_percent,
                    card.damage_taken_bonus_percent,
                )
                self._log(
                    f"{name}: {card.name} — следующий полученный урон увеличен на "
                    f"{card.damage_taken_bonus_percent}%"
                )
        if card.cooldown_turns:
            self.enemy_card_last_used[eid][card.key] = self.round
        self._check_result()

    def _creature_attack_dodged(self, eid, target_id, card):
        """Resolve a creature attack against the target's normal and guaranteed dodge."""
        if self._is_kneeling(target_id):
            return False
        target = self.fighters[target_id]
        with self._as_player(target_id):
            dodge = get_dodge_chance(self.fighters[eid], target)
            dodge += target.temporary_dodge_chance_modifier
            dodge += self.engine._buff("player", "dodge_percent")
            dodge += self.engine._buff("player", "agility_bonus") * 2
            dodge += sum(
                int(status.get("miss_chance", 0))
                for status in self.engine.mage_statuses.get("enemy", [])
                if status["name"] == "blinding"
            )
            if any(
                status["name"] == "вода"
                for status in self.engine.mage_statuses.get("player", [])
            ):
                dodge -= 15
            guaranteed = self.engine.phys_state["player"]["guaranteed_dodges"] > 0
            if guaranteed:
                self.engine.phys_state["player"]["guaranteed_dodges"] -= 1
            if not guaranteed and self.rng.random() * 100 >= max(0, dodge):
                return False
            self.engine._fighter_dodged("player")
            self.engine._on_dodge("player", "enemy", {})
        self._log(f"{self.fighters[eid].name}: {card.name} — {target.name} уклонился")
        return True

    # ------------------------------------------------------------------ раунды

    def _tick_enemy_only(self, eid):
        """Эффекты на враге, который сейчас не цель: тикают без повторного тика эффектов игрока."""
        self.select_target(eid)
        engine = self.engine
        saved_player = {attr: getattr(engine, attr)["player"] for attr in self._swapped}
        stun = engine.mage_stuns["enemy"]
        for attr in self._swapped:
            getattr(engine, attr)["player"] = deepcopy(self._fresh_player[attr])
        try:
            self._tick_engine_effects("enemy")
        finally:
            engine.mage_stuns["enemy"] = stun
            for attr in self._swapped:
                getattr(engine, attr)["player"] = saved_player[attr]

    def _tick_ally(self, aid):
        """Эффекты союзника тикают без повторного тика эффектов текущей цели."""
        engine = self.engine
        with self._as_player(aid):
            saved_enemy = {attr: getattr(engine, attr)["enemy"] for attr in self._swapped}
            stun = engine.mage_stuns["player"]
            for attr in self._swapped:
                getattr(engine, attr)["enemy"] = deepcopy(self._fresh[attr])
            try:
                self._tick_engine_effects("player")
            finally:
                engine.mage_stuns["player"] = stun
                for attr in self._swapped:
                    getattr(engine, attr)["enemy"] = saved_enemy[attr]

    def _tick_engine_effects(self, side):
        engine = self.engine
        engine._tick_physical_effects()
        engine._process_status_turn_effects()
        engine._remove_expired_statuses()
        engine._resolve_mage_end_turn_effects()
        engine.mage_freeze[side] = max(0, int(engine.mage_freeze[side]) - 1)

    def _start_round(self):
        chosen = self.target
        if self.round > 0:
            self.barriers = {
                tile: remaining - 1 for tile, remaining in self.barriers.items()
                if remaining > 1
            }
            for eid in self.alive_enemies():
                if eid != chosen:
                    self._tick_enemy_only(eid)
            self.select_target(chosen)
            for aid in self.alive_allies():
                self._tick_ally(aid)
                self._ally_regen(aid)
                self._ally_draw(aid)
        # Оглушение снимается, когда сторона пропускает свой ход, а не в начале раунда
        stuns = dict(self.engine.mage_stuns)
        hand = self.engine.hands["player"]
        if self.round > 0 and not self.engine._deck_for("player") and self.engine.discard:
            self.engine._shuffle_discard_into_deck("player")
        hand_size = len(hand)
        self.engine._start_turn(
            draw_cards=self.round > 0 and not self.player_draw_choice
        )
        draw_choices = (
            self.engine.prepare_draw_choice("player")
            if self.round > 0 and self.player_draw_choice else []
        )
        self.engine.mage_stuns = stuns
        self.round += 1
        self._tick_arena_effects()
        self.grave_soil = {
            tile: expires for tile, expires in self.grave_soil.items()
            if expires > self.round
        }
        self._tick_green_flame("player")
        self._refresh_king_auras()
        if self.round > 1:
            drawn = [card.name for card in draw_choices]
            if not self.player_draw_choice:
                drawn = [card.name for card in self.engine.hands["player"][hand_size:]]
            self.draw_events.append({
                "round": self.round, "cards": drawn, "start": False,
                "hand_full": hand_size >= self.hand_limit,
                "choice": bool(draw_choices),
            })
            del self.draw_events[:-6]
        self.active_side = "player"
        self.moved = False
        self.cards_played = 0
        self._check_result()
        self._retarget_if_dead()
        if self.is_over():
            return
        if self.teleport_pending:
            self.result = "teleport"
            self._log(f"{self.player.name} телепортируется к кристаллу возрождения")

    def _tick_arena_effects(self):
        for side, effects in tuple(self.temporary_damage_taken.items()):
            active = []
            for bonus, remaining in effects:
                if remaining > 1:
                    active.append([bonus, remaining - 1])
            if active:
                self.temporary_damage_taken[side] = active
            else:
                self.temporary_damage_taken.pop(side, None)

        corrosion = self.arena_corrosion.get("player")
        if corrosion:
            total_damage, turns_left = corrosion
            amount = (total_damage + turns_left - 1) // turns_left
            dealt = self._apply_environment_damage(
                "player", amount
            )
            self._log(f"{self.player.name}: коррозия наносит {dealt} урона")
            total_damage -= amount
            turns_left -= 1
            if total_damage > 0 and turns_left > 0:
                self.arena_corrosion["player"] = [total_damage, turns_left]
            else:
                self.arena_corrosion.pop("player", None)
            self._check_result()

    def _finish_side(self, side):
        self.engine.active_side = side
        self.engine.complete_side_turn()
        self._tick_root(side)
        self._tick_grave_soil_fighter(side)
        self._check_result()

    def _tick_grave_soil_fighter(self, side):
        if (
            side not in self.fighters
            or not self.is_undead(side)
            or self.positions[side] not in self.grave_soil
        ):
            return
        fighter = self.fighters[side]
        healed = min(3, fighter.max_hp - fighter.hp)
        fighter.hp += healed
        if healed:
            self._log(f"{fighter.name}: могильная почва +{healed} HP")

    def _tick_grave_soil_summon(self, sid):
        if (
            sid not in self.summons
            or not self.is_undead(sid)
            or self.positions[sid] not in self.grave_soil
        ):
            return
        summon = self.summons[sid]
        healed = min(3, summon["max_hp"] - summon["hp"])
        summon["hp"] += healed

    def _tick_root(self, side):
        if self.roots.get(side, 0):
            self.roots[side] -= 1

    def _check_result(self):
        if self.result is not None:
            return
        for uid, fighter in self.fighters.items():
            if fighter.is_dead():
                self._grant_necrotism_for_death(uid)
        if self.player.is_dead():
            self.result = "loss"
        elif not self.alive_enemies():
            self.result = "win"

    def _grant_necrotism_for_death(self, dead_id):
        if dead_id in self._death_rewards_applied:
            return
        self._death_rewards_applied.add(dead_id)
        for uid, fighter in self.fighters.items():
            if getattr(fighter, "unique_resource_type", None) != "necrotism":
                continue
            multiplier = 100 + int(self.necrotism_gain_bonus.get(uid, 0))
            reward = int(fighter.unique_resource_max * 0.10 * multiplier / 100)
            fighter.gain_unique_resource(reward)

    def _log(self, text):
        self.log.append(text)
        del self.log[:-8]

    # ------------------------------------------------------------------ описание эффектов

    def effects_for(self, side):
        return [text for text, _ in self.effect_entries_for(side)]

    def effect_entries_for(self, side):
        """Текст и цвет действующих эффектов для плашек и подробной подсказки."""
        positive = (125, 225, 145)
        negative = (245, 135, 125)
        neutral = (220, 185, 245)
        if side in self.summons:
            summon = self.summons[side]
            if summon["kind"] == "cloud":
                return [(f"Рассеется через: {summon['remaining']} х.", neutral)]
            if summon["kind"] == "forest_spirit":
                return [(f"Поддержка союзников: {FOREST_SPIRIT_RANGE} гекса", positive)]
            if summon["kind"].startswith("necromancer_"):
                descriptions = {
                    "necromancer_familiar": "Аура: +20% урона союзникам в радиусе 2 гексов",
                    "necromancer_lokrif": "Яд; первый входящий урон снижен на 65%",
                    "necromancer_bone_hero": "Атаки, рывок и жертва ради призывателя",
                    "necromancer_spirit": "Бесплотность: 50% сопротивления физическому урону",
                    "necromancer_lyrk": "20% уклонения; атаки накладывают эффекты",
                    "necromancer_grave_zink": "Удар и выжигание маны",
                    "necromancer_bone_dragon": "Удар, зелёное пламя и оглушение по области",
                }
                description = descriptions.get(summon["kind"])
                return [(description, positive)] if description else []
            left = summon["stun_every"] - summon["attacks"] % summon["stun_every"]
            return [(f"Мощный удар через: {left} атак.", positive)]
        state = lambda attr: self._state(side, attr)
        entries = []
        fighter = self.player if side == "player" else self.fighters.get(side)
        vulnerability = int(getattr(fighter, "next_damage_taken_bonus_percent", 0))
        if vulnerability:
            entries.append((f"Следующий урон +{vulnerability}%", negative))
        for bonus, remaining in self.temporary_damage_taken.get(side, ()):
            if remaining > 0:
                entries.append((f"Уязвимость +{bonus}%: {remaining} х.", negative))
        green_flame = self.green_flame.get(side, ())
        if green_flame:
            entries.append((
                f"Зелёное пламя +{sum(green_flame)}% урона/ход",
                negative,
            ))
        corrosion = self.arena_corrosion.get(side)
        if corrosion:
            damage, remaining = corrosion
            entries.append((f"Коррозия: {damage} урона за {remaining} х.", negative))
        if self.defense_curses.get(side, 0) > self.round:
            remaining = self.defense_curses[side] - self.round
            entries.append((f"Проклятие защиты: {remaining} х.", negative))
        if self.slowed_until.get(side, 0) > self.round:
            remaining = self.slowed_until[side] - self.round
            entries.append((f"Замедление: {remaining} х.", negative))
        protection = self.protection_effects.get(side)
        if protection and protection.get("expires_round", 0) > self.round:
            remaining = protection["expires_round"] - self.round
            entries.append((
                f"Защита от урона: -{protection['percent']}% ({remaining} х.)",
                positive,
            ))
        if self.broken_bones.get(side, 0) > self.round:
            remaining = self.broken_bones[side] - self.round
            entries.append((f"Сломанные кости: {remaining} х.", negative))
        if self._is_kneeling(side):
            remaining = self.kneeling[side] - self.round
            entries.append((f"Повержен ниц: {remaining} х.", negative))
        labels = {
            "damage_percent": ("Урон", "%", positive),
            "dodge_percent": ("Уворот", "%", positive),
            "crit_chance": ("Шанс крита", "%", positive),
            "crit_damage": ("Крит. урон", "%", positive),
            "agility_bonus": ("Ловкость", "", positive),
            "hit_bonus": ("Меткость", "%", positive),
            "incoming_damage_percent": ("Сопротивление урону", "%", positive),
            "extra_hits": ("Доп. удары", "", positive),
            "regen_per_hit_percent": ("Лечение за удар", "%", positive),
            "missing_hp_damage": ("Урон за потерю HP", "", positive),
            "bleed_heal_percent": ("Лечение от кровотечения", "%", positive),
            "crit_conversion": ("Конверсия крита", "", positive),
            "accuracy_gain": ("Меткость за уклонение", "", positive),
            "burn_bonus_max_percent": ("Выжигание максимальной маны", "%", positive),
            "burn_bonus_current_percent": ("Выжигание текущей маны", "%", positive),
            "dodge_damage_bonus": ("Урон после уклонения", "%", positive),
            "mana_regen_bonus": ("Восст. маны", "", positive),
            "mana_regen_debuff": ("Снижение восст. маны", "%", negative),
            "steal_healing_percent": ("Кража лечения", "%", negative),
            "outgoing_damage_flat": ("Исходящий урон", "", negative),
            "outgoing_damage_percent": ("Исходящий урон", "%", negative),
            "healing_blocked": ("Запрет лечения", "", negative),
            "forbid_damage_cards": ("Запрет атакующих карт", "", negative),
            "entangled": ("Оплетение", "", negative),
            "mark_damage": ("Метка уязвимости", " урона", negative),
            "poison_cap_bonus": ("Лимит яда увеличен", "", negative),
            "dodge_stun": ("Оглушение при уклонении", "", negative),
        }
        for buff in state("phys_buffs"):
            turns = 1 if buff.get("expire_after_turn") else max(1, int(buff.get("remaining", 1)))
            for key, value in buff.items():
                if not value or key in {
                    "remaining", "fresh", "expire_after_turn", "forest_spirit",
                    "entangle_source", "dodge_stack_limit",
                }:
                    continue
                label, suffix, color = labels.get(key, (key.replace("_", " ").capitalize(), "", neutral))
                if not isinstance(value, bool):
                    label += f": {value}{suffix}"
                    if color == positive and value < 0:
                        color = negative
                entries.append((f"{label} ({turns} х.)", color))
        for effect in state("bleeds"):
            entries.append((f"Кровотечение -{effect['damage']}/ход: {effect['remaining']} х.", negative))
        if state("poisons"):
            entries.append((f"Яд x{len(state('poisons'))} (2% HP за заряд)", negative))
        for effect in state("regenerations"):
            fighter = self.fighters[side]
            heal = effect["heal_per_turn"] + int(fighter.stats.get("endurance", 0)) * effect.get("endurance_heal", 0)
            entries.append((f"Лечение {heal} HP/ход: {effect['remaining']} х.", positive))
        for effect in state("delayed_heals"):
            entries.append((f"Лечение +{effect['amount']} HP через {effect['remaining']} х.", positive))
        for effect in state("delayed_hp_loss"):
            entries.append((f"Потеря {effect['amount']} HP через {effect['remaining']} х.", negative))
        for status in state("mage_statuses") or []:
            stacks = f" x{status['stacks']}" if status.get("stacks", 1) > 1 else ""
            entries.append((f"{str(status['name']).capitalize()}{stacks}: {status.get('remaining', 1)} х.", neutral))
        if self.roots.get(side, 0):
            entries.append((f"Корни: {self.roots[side]} х.", negative))
        if state("mage_stuns"):
            entries.append((f"Оглушение: {state('mage_stuns')} х.", negative))
        if state("mage_freeze"):
            entries.append((f"Заморозка: {state('mage_freeze')} х.", negative))
        if state("skip_next_turn"):
            entries.append(("Пропуск следующего хода: 1 х.", negative))
        if state("phys_shields"):
            entries.append((f"Щит +{int(state('phys_shields'))} HP", positive))
        for shield in state("mage_shield_effects"):
            entries.append((f"Щит +{shield['amount']} HP: {shield['remaining']} х.", positive))
        for bonus in state("mage_damage_bonuses"):
            percent = bonus["percent"]
            entries.append((f"Магический урон {percent:+}%: {bonus['remaining']} х.",
                            positive if percent >= 0 else negative))
        for blessing in state("mage_reactive_blessings"):
            entries.append((f"Ответное благословение: {blessing['remaining']} х.", positive))
        if state("invulnerable"):
            entries.append(("Неуязвимость", positive))
        spirit = state("phys_spirits")
        if spirit:
            entries.append((f"Лесной дух: {spirit['hp']}/{spirit['max_hp']} HP", positive))
        for key, label, color in (
            ("guaranteed_crits", "Гарантированный крит", positive),
            ("no_crit_attacks", "Атаки без крита", negative),
            ("guaranteed_dodges", "Гарантированное уклонение", positive),
            ("dodge_stacks", "Заряды после уклонения", positive),
        ):
            count = state("phys_state").get(key, 0)
            if count:
                entries.append((f"{label} x{count}", color))
        return entries
