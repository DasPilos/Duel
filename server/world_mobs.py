"""Серверная логика боя на карте мира: мобы, позиция и HP игрока, рывок, награды, регенерация.

Сервер владеет состоянием мира. Клиент присылает намерения (позиция, цель удара, рывок),
сервер проверяет их, считает бой и отвечает снимком мира и событиями. Модуль не импортирует
pygame: все правила дублируют клиентскую логику scenes/world_map_scene.py, а формулы берутся
из combat/*.
"""
import math
import random
import sys
import threading
import time

from combat.dash import (
    DASH_COOLDOWN,
    DASH_HIT_RADIUS,
    DASH_MIN_LENGTH,
    DASH_SPEED,
    DASH_TRAIL_DURATION,
    WHIRL_STRIKE_RADIUS,
    dash_damage_roll,
    dash_end_point,
    point_segment_distance,
    whirl_strike_damage_roll,
)
from combat.fighter import Fighter
from combat.progression import apply_xp
from core import mob_modes
from core.mob_profiles import npc_profiles
from combat.fighter_profile import apply_fighter_profile
from combat.world_stats import (
    BASE_MOVE_SPEED,
    get_attack_backswing,
    get_attack_reach,
    get_attack_windup,
    get_hp_regen_per_second,
    get_mana_regen_per_second,
    get_move_speed,
    get_world_max_hp,
    get_world_max_mana,
    resolve_world_melee_attack,
)
from core.carry_weight import movement_speed_multiplier
from core.currency import Currency
from server import map_editor, presence, world_map
from server.structures import world_structures
from server.world_map import IS_TOWER_WORLD, TILE, point_in_polygon, rect_touches_blocked_tile

# Размер карты и точка появления читаются при каждом вызове: их меняет публикация карты из редактора.
def _world_w():
    return world_map.MAP_TILES_W * TILE


def _world_h():
    return world_map.MAP_TILES_H * TILE


# Ноги персонажа и тело моба в пикселях (совпадают с клиентом).
FEET_W = 20
FEET_H = 10
MOB_SPRITE_W = 90
MOB_SPRITE_H = 53
PLAYER_HEAD_OFFSET = 40  # подпись над персонажем
MOB_LABEL_OFFSET = MOB_SPRITE_H / 2 + 10  # подпись над мобом

MOB_LEVEL = 1
MOB_LEASH_DISTANCE = 40 * TILE  # дальше 40 тайлов от точки респауна моб не уходит
MOB_RESPAWN_DELAY = 30.0
MOB_PATROL_RADIUS_TILES = 3
MOB_AGGRO_RADIUS = MOB_PATROL_RADIUS_TILES * TILE + TILE // 2
MOB_PATROL_SPEED = 40.0
MOB_PATROL_PAUSE = 1.5
PLAYER_CORPSE_COIN_PERCENT = 20  # при гибели игрок теряет эту долю монет, они лежат в трупе
CORPSE_LOOT_RANGE = 2 * TILE  # забрать труп можно, стоя не дальше 2 тайлов от него, px

MOB_PROFILES = dict(npc_profiles())
NPC_KEYS = frozenset(MOB_PROFILES)


PLAYER_MISS_LOG_TEXT = {"dodge": "{nom} увернулся", "block": "{nom} блокировал", "miss": "Вы промахнулись"}
MOB_MISS_LOG_TEXT = {"dodge": "Вы увернулись от {gen}", "block": "Вы заблокировали удар {gen}", "miss": "{nom} промахнулся"}

# Допуск движения: скорость × прошедшее время × множитель + запас на задержку сети.
DASH_STEP = 4.0  # шаг проверки коллизии и урона во время рывка, px
DASH_RETREAT_STEP = 2.0  # шаг поиска свободной точки после рывка, px
DASH_EXIT_MAX = 200.0  # дальше этого персонаж не проскакивает сквозь моба, px
DASH_TRAIL_STEP = 10.0  # расстояние между точками следа вихря, px

MOVE_TIME_CAP = 2.0
MOVE_SPEED_FACTOR = 1.5
MOVE_SLACK = 40.0
MOVE_SAMPLE_STEP = 8.0
PLAYER_IDLE_TIMEOUT = 20.0
FLUSH_INTERVAL = 2.0
CARRY_REFRESH_INTERVAL = 10.0
STRUCTURES_REFRESH_INTERVAL = 30.0
TICK_INTERVAL = 0.1
# Как часто мир проверяет, не опубликована ли новая карта (в том числе с другого сервера мира)
PUBLISH_CHECK_INTERVAL = 5.0
MAX_TICK_DT = 0.25
EVENT_LIMIT = 200
FACING_STEP = math.pi / 4  # 8 направлений взгляда персонажа


def _build_obstacle_shapes(obstacles):
    """Препятствия карты в виде (точки, рамка, проходы) для быстрой проверки коллизий."""
    shapes = []
    for obstacle in obstacles:
        points = [tuple(point) for point in obstacle["points"]]
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        bounds = (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
        passages = tuple(tuple(passage) for passage in obstacle.get("passages", []))
        shapes.append((points, bounds, passages))
    return tuple(shapes)


_obstacle_shapes_cache = (None, ())


def _obstacle_shapes():
    """Препятствия для проверки коллизий; пересобираются, когда карта редактора меняет рельеф."""
    global _obstacle_shapes_cache
    version, shapes = _obstacle_shapes_cache
    if version != world_map.TERRAIN_VERSION:
        shapes = _build_obstacle_shapes(world_map.OBSTACLES)
        _obstacle_shapes_cache = (world_map.TERRAIN_VERSION, shapes)
    return shapes


def _in_rect(x, y, rect):
    """Как pygame.Rect.collidepoint: левый и верхний край внутри, правый и нижний — снаружи."""
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def _rects_collide(a, b):
    """Пересечение прямоугольников (x, y, w, h) с строгими границами, как pygame.Rect.colliderect."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _feet_rect(x, y):
    return (int(x - FEET_W / 2), int(y - FEET_H / 2 + 1), FEET_W, FEET_H)


def _mob_block_rect(x, y):
    """Тело моба для блокировки движения: центр в (x, y)."""
    return (int(x) - MOB_SPRITE_W // 2, int(y) - MOB_SPRITE_H // 2, MOB_SPRITE_W, MOB_SPRITE_H)


def _mob_reach_rect(x, y):
    """Тело моба для дальности удара: сдвиг, как в клиенте (_mob_body_rect)."""
    return (int(x - MOB_SPRITE_W / 2), int(y - MOB_SPRITE_H / 2), MOB_SPRITE_W, MOB_SPRITE_H)


def _distance_to_rect(x, y, rect):
    """Расстояние от точки до ближайшей точки прямоугольника (0 внутри)."""
    left, top, width, height = rect
    nearest_x = min(max(x, left), left + width)
    nearest_y = min(max(y, top), top + height)
    return math.hypot(x - nearest_x, y - nearest_y)


def _quantize_facing(angle):
    return round(angle / FACING_STEP) * FACING_STEP


def _read_point(x, y):
    for value in (x, y):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Некорректная позиция")
    return float(x), float(y)


def _apply_world_resource_formulas(fighter):
    """Мировые HP и ману считаем по выносливости и интеллекту; текущие значения не выше максимума."""
    equipment_hp = int(fighter.equipment_stat_modifiers.get("hp", 0))
    equipment_mp = int(fighter.equipment_stat_modifiers.get("mp", 0))
    fighter.max_hp = get_world_max_hp(fighter, equipment_hp)
    fighter.max_mp = get_world_max_mana(fighter, equipment_mp)
    fighter.hp = min(fighter.hp, fighter.max_hp)
    fighter.mp = min(fighter.mp, fighter.max_mp)


def _fighter_from_character(character):
    fighter = Fighter("Игрок", level=1)
    apply_fighter_profile(fighter, character)
    _apply_world_resource_formulas(fighter)
    return fighter


class _Mob:
    def apply_config(self, cfg):
        """Параметры вида из файла режима. cfg None — процедурный моб, остаются мировые значения."""
        if cfg is None:
            return
        self.move_speed = float(cfg["move_speed"])
        self.windup_time = float(cfg["windup"])
        self.backswing_time = float(cfg["backswing"])
        self.aggro_px = float(cfg["aggro_tiles"]) * TILE + TILE // 2
        self.respawn_delay = float(cfg["respawn_seconds"])
        self.patrol_cells = tuple(tuple(cell) for cell in cfg["patrol"])
        self.attitude = cfg["state"]
        self.reward_copper = int(cfg["reward_copper"])
        self.reward_xp = int(cfg["reward_xp"])
        self.coins_copper = self.reward_copper

    def __init__(self, mob_id, kind, home, fighter, equipment):
        profile = MOB_PROFILES[kind]
        self.id = mob_id
        self.kind = kind
        self.name = profile["name"]
        self.desc = profile["desc"]
        self.log_names = profile["log_names"]
        self.home_x, self.home_y = home
        self.x, self.y = home
        self.fighter = fighter
        self.equipment = equipment
        self.state = "idle"
        self.respawn_timer = 0.0
        self.patrol_target = None
        self.patrol_pause = 0.0
        self.windup = 0.0
        self.windup_total = 0.0
        self.backswing = 0.0
        # Для мобов взгляд стартует с 0 (как в клиенте), иначе первый удар по игроку был бы «в спину»
        self.facing = 0.0
        self.coins_copper = mob_modes.DEFAULT_REWARD_COPPER
        self.target = None
        # Параметры вида из файла режима; по умолчанию — прежние мировые значения (процедурные мобы)
        self.move_speed = BASE_MOVE_SPEED
        self.windup_time = get_attack_windup(fighter)
        self.backswing_time = get_attack_backswing(fighter)
        self.aggro_px = MOB_AGGRO_RADIUS
        self.respawn_delay = MOB_RESPAWN_DELAY
        self.reward_copper = mob_modes.DEFAULT_REWARD_COPPER
        self.reward_xp = mob_modes.DEFAULT_REWARD_XP
        # Вклад игроков в урон: {character_id: (user_id, нанесено урона)}, делит награду при гибели
        self.damage_by = {}
        self.patrol_cells = ()
        self.attitude = "aggressive"
        self.provoker = None

    @property
    def alive(self):
        return self.fighter.hp > 0


class _Player:
    def __init__(self, user_id, character_id, fighter, x, y, now):
        self.user_id = user_id
        self.character_id = character_id
        self.fighter = fighter
        self.x = x
        self.y = y
        self.facing = 0.0
        self.last_sync = now
        self.last_seen = now
        self.move_speed = get_move_speed(fighter)
        self.carry_multiplier = 1.0
        self.carry_timer = 0.0
        self.attack_target = None
        self.windup = 0.0
        self.windup_total = 0.0
        self.windup_target = None
        self.backswing = 0.0
        self.swing_id = 0
        self.dash = None
        self.dash_cooldown = 0.0
        self.trails = []
        self.hp_accumulator = 0.0
        self.mp_accumulator = 0.0
        self.dirty = False
        self.flush_timer = 0.0
        self.events = []
        self.corpses = []


class WorldService:
    def __init__(self, database, items_database, city_level_provider=None, clock=None, rng=None):
        self._database = database
        self._items = items_database
        self._city_level = city_level_provider or (lambda: 1)
        self._clock = clock or time.monotonic
        self._rng = rng or random.Random()
        self._lock = threading.RLock()
        self._players = {}
        self._seq = 0
        self._solid_rects = ()
        self._structures_timer = 0.0
        self._refresh_structures()
        self._mobs = self._build_mobs()
        self._relocate_blocked()
        self._thread = None
        self._stop_event = threading.Event()

    # ----- сборка состояния -----

    def _spawn_list(self):
        """Мобы мира: расставленные на опубликованной карте, процедурные (обычный мир) или ни одного (Башня)."""
        if IS_TOWER_WORLD or not world_map.LIVE_MAP:
            return ()
        return tuple(
            (f"mob_{index}_{row['kind']}", row["kind"], (row["x"], row["y"]))
            for index, row in enumerate(self._database.map_live_mobs())
        )

    def _mob_config(self, kind):
        """Настройки вида моба в режиме этого мира (файл mob_modes/<режим>.json); без файла — по умолчанию."""
        mode = self._database.world_mode()
        try:
            return mob_modes.load_mob_settings(mode, kind)
        except mob_modes.ModeFileError:
            return mob_modes.default_settings(kind)

    def _build_mobs(self):
        spawns = list(self._spawn_list())
        configs = {kind: self._mob_config(kind) for _, kind, _ in spawns if kind in NPC_KEYS}
        item_ids = sorted({item_id for cfg in configs.values()
                           for item_id in cfg["equipment"].values() if item_id})
        catalog = self._items.get_catalog_items(item_ids)
        mobs = {}
        for mob_id, kind, (tile_x, tile_y) in spawns:
            profile = MOB_PROFILES[kind]
            cfg = configs.get(kind)
            fighter = Fighter(profile["name"], level=cfg["level"] if cfg else MOB_LEVEL)
            fighter.stats.update(cfg["stats"] if cfg else profile["stats"])
            # Предмет вне каталога или не того слота не выдаётся: слот остаётся пустым
            equipment = {}
            for slot, item_id in (cfg["equipment"] if cfg else {}).items():
                item = catalog.get(str(item_id)) if item_id else None
                if item and item["equip_slot"] == slot:
                    equipment[slot] = item
            fighter.equipment = equipment
            modifiers = {}
            for item in equipment.values():
                for stat_key, bonus in item["bonuses"].items():
                    modifiers[stat_key] = modifiers.get(stat_key, 0) + bonus
            fighter.equipment_stat_modifiers = modifiers
            fighter.recalculate_parameters()
            _apply_world_resource_formulas(fighter)
            fighter.hp = fighter.max_hp
            home = (tile_x * TILE + TILE // 2, tile_y * TILE + TILE // 2)
            mob = _Mob(mob_id, kind, home, fighter, dict(equipment))
            mob.apply_config(cfg)
            mobs[mob_id] = mob
        return mobs

    def _refresh_structures(self):
        payload = world_structures(self._city_level())
        self._solid_rects = tuple(
            tuple(rect)
            for obj in payload.get("objects", [])
            for rect in obj.get("solid_rects", [])
        )

    def _load_player(self, user_id, character_id, x, y):
        character = self._database.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        fighter = _fighter_from_character(character)
        now = self._clock()
        if self._spawn_pixels():
            start_x, start_y = self._entry_position(character.get("position_x"), character.get("position_y"))
        else:
            start_x, start_y = self._initial_position(
                [(x, y), (character.get("position_x"), character.get("position_y")), world_map.MAP_SPAWN_PX])
        player = _Player(user_id, character_id, fighter, start_x, start_y, now)
        player.corpses = self._database.list_player_corpses(character_id)
        self._refresh_carry(player)
        self._players[character_id] = player
        return player

    def _spawn_pixels(self):
        """Точки спауна карты в пикселях (центры клеток). Пусто — карта без точек спауна."""
        return [(x * TILE + TILE // 2, y * TILE + TILE // 2) for x, y in self._database.map_live_spawns()]

    def _entry_position(self, saved_x, saved_y):
        """Вход в мир: ближайшая точка спауна к сохранённой позиции; без позиции — случайная точка."""
        spawns = self._spawn_pixels()
        if not spawns:
            return float(world_map.MAP_SPAWN_PX[0]), float(world_map.MAP_SPAWN_PX[1])
        if isinstance(saved_x, (int, float)) and isinstance(saved_y, (int, float)):
            return min(spawns, key=lambda point: math.hypot(point[0] - saved_x, point[1] - saved_y))
        return self._rng.choice(spawns)

    def _respawn_player(self, player, death_x, death_y, lost_copper=0):
        """Гибель: игрок возрождается у ближайшей к месту гибели точки спауна с полным здоровьем."""
        x, y = self._entry_position(death_x, death_y)
        player.x, player.y = x, y
        player.move_path = []
        player.attack_target = None
        player.fighter.hp = player.fighter.max_hp
        player.dirty = True
        text = "Вы погибли и возрождены у точки спауна"
        if lost_copper:
            text += f". Потеряно {Currency.format_amount(lost_copper)}, они в трупе на месте гибели"
        self._emit_notice(player, text)

    def _player_died(self, player):
        corpse = self._database.create_player_corpse(
            player.user_id, player.character_id, player.x, player.y, PLAYER_CORPSE_COIN_PERCENT)
        lost = 0
        if corpse is not None:
            corpse_payload, currency = corpse
            player.corpses.append(corpse_payload)
            lost = corpse_payload["copper"]
            self._emit(player, {"type": "currency", "currency": currency})
        self._respawn_player(player, player.x, player.y, lost)

    def loot_corpse(self, user_id, character_id, corpse_id):
        """Игрок забирает свой труп: монеты уходят в кошелёк. Труп должен быть рядом с персонажем."""
        with self._lock:
            player = self._players.get(character_id)
            if player is None or player.user_id != user_id:
                raise ValueError("Персонаж не в мире")
            corpse = next((item for item in player.corpses if item["id"] == corpse_id), None)
            if corpse is None:
                raise ValueError("Труп не найден")
            if math.hypot(corpse["x"] - player.x, corpse["y"] - player.y) > CORPSE_LOOT_RANGE:
                raise ValueError("Подойдите ближе к трупу")
            currency, looted = self._database.loot_player_corpse(user_id, character_id, corpse_id)
            player.corpses = [item for item in player.corpses if item["id"] != corpse_id]
            self._emit(player, {"type": "currency", "currency": currency})
            self._emit_notice(player, f"Забрано из трупа: {Currency.format_amount(looted)}")
            return {"currency": currency, "corpses": [dict(item) for item in player.corpses]}

    def _initial_position(self, candidates):
        """Первая подходящая точка: позиция клиента при входе, затем позиция из БД, затем центр карты."""
        for x, y in candidates:
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue
            if not (0 <= x <= _world_w() and 0 <= y <= _world_h()) or self._terrain_blocked(x, y):
                continue
            return float(x), float(y)
        return float(world_map.MAP_SPAWN_PX[0]), float(world_map.MAP_SPAWN_PX[1])

    def _refresh_carry(self, player):
        with self._database.connection() as connection:
            state = self._items.carry_weight_state(connection, player.character_id)
        player.carry_multiplier = movement_speed_multiplier(
            state["carried_weight_kg"], state["carry_capacity_kg"])
        player.move_speed = get_move_speed(player.fighter, player.carry_multiplier)
        player.carry_timer = CARRY_REFRESH_INTERVAL

    # ----- коллизии -----

    def _terrain_blocked(self, x, y):
        if x - FEET_W / 2 < 0 or x + FEET_W / 2 > _world_w() or y - FEET_H / 2 < 0 or y + FEET_H / 2 > _world_h():
            return True
        feet = _feet_rect(x, y)
        for rect in self._solid_rects:
            if _rects_collide(feet, rect):
                return True
        if rect_touches_blocked_tile(feet):
            return True
        ix, iy = int(x), int(y)
        for points, bounds, passages in _obstacle_shapes():
            if not _in_rect(ix, iy, bounds):
                continue
            if point_in_polygon((x, y), points) and not any(_in_rect(ix, iy, passage) for passage in passages):
                return True
        return False

    def _player_blocked(self, x, y):
        """Персонаж не проходит сквозь рельеф и живых мобов."""
        if self._terrain_blocked(x, y):
            return True
        feet = _feet_rect(x, y)
        return any(mob.alive and _rects_collide(feet, _mob_block_rect(mob.x, mob.y))
                   for mob in self._mobs.values())

    def _mob_blocked_by_players(self, x, y):
        body = _mob_block_rect(x, y)
        return any(_rects_collide(body, _feet_rect(player.x, player.y)) for player in self._players.values())

    def _segment_clear(self, x0, y0, x1, y1):
        """Отрезок пути свободен: проверяем точки каждые MOVE_SAMPLE_STEP пикселей."""
        length = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, math.ceil(length / MOVE_SAMPLE_STEP))
        for index in range(1, steps + 1):
            t = index / steps
            if self._player_blocked(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
                return False
        return True

    def _accept_move(self, player, x, y, elapsed):
        """Принимает позицию клиента, если она в пределах скорости и не проходит через стены и мобов."""
        if not (0 <= x <= _world_w() and 0 <= y <= _world_h()):
            return False
        allowed = player.move_speed * min(elapsed, MOVE_TIME_CAP) * MOVE_SPEED_FACTOR + MOVE_SLACK
        dx, dy = x - player.x, y - player.y
        distance = math.hypot(dx, dy)
        if distance > allowed:
            return False
        if not self._segment_clear(player.x, player.y, x, y):
            return False
        if distance > 0.5:
            player.facing = _quantize_facing(math.atan2(dy, dx))
        player.x, player.y = x, y
        return True

    # ----- события и снимок -----

    def _emit(self, player, event):
        self._seq += 1
        event["seq"] = self._seq
        player.events.append(event)
        if len(player.events) > EVENT_LIMIT:
            del player.events[:len(player.events) - EVENT_LIMIT]

    def _emit_number(self, player, value, critical, x, y):
        self._emit(player, {"type": "number", "x": x, "y": y, "value": value, "critical": critical})

    def _emit_label(self, player, outcome, x, y):
        self._emit(player, {"type": "label", "x": x, "y": y, "outcome": outcome})

    def _emit_log(self, player, text, color):
        self._emit(player, {"type": "log", "text": text, "color": color})

    def _emit_notice(self, player, text):
        self._emit(player, {"type": "notice", "text": text})

    def _emit_message(self, player, x, y, text):
        self._emit(player, {"type": "message", "x": x, "y": y, "text": text})

    def _player_payload(self, player):
        fighter = player.fighter
        return {
            "character_id": player.character_id,
            "x": player.x,
            "y": player.y,
            "hp": fighter.hp,
            "max_hp": fighter.max_hp,
            "mp": fighter.mp,
            "max_mp": fighter.max_mp,
            "facing": player.facing,
            "windup": player.windup,
            "windup_total": player.windup_total,
            "swing_id": player.swing_id,
            "backswing": player.backswing,
            "attack_target": player.attack_target.id if player.attack_target else None,
            "windup_target": player.windup_target.id if player.windup_target else None,
            "dash_active": player.dash is not None,
            "dash_cooldown": player.dash_cooldown,
            "reach": get_attack_reach(fighter),
            "move_speed": player.move_speed,
            "carry_multiplier": player.carry_multiplier,
        }

    @staticmethod
    def _mob_payload(mob):
        fighter = mob.fighter
        return {
            "id": mob.id,
            "kind": mob.kind,
            "name": mob.name,
            "desc": mob.desc,
            "x": mob.x,
            "y": mob.y,
            "home_x": mob.home_x,
            "home_y": mob.home_y,
            "hp": fighter.hp,
            "max_hp": fighter.max_hp,
            "level": fighter.level,
            "state": mob.state if mob.alive else "dead",
            "respawn_timer": mob.respawn_timer,
            "facing": mob.facing,
            "windup": mob.windup,
            "windup_total": mob.windup_total,
            "coins": {"copper": mob.coins_copper, "silver": 0, "gold": 0},
            "equipment": {slot: dict(item) for slot, item in mob.equipment.items()},
            "stats": dict(fighter.stats),
        }

    def _snapshot(self, player, since, accepted):
        return {
            "accepted": accepted,
            "seq": self._seq,
            "terrain_version": world_map.TERRAIN_VERSION,
            "player": self._player_payload(player),
            "mobs": [self._mob_payload(mob) for mob in self._mobs.values()],
            "trails": [dict(trail) for trail in player.trails],
            "corpses": [dict(corpse) for corpse in player.corpses],
            "events": [dict(event) for event in player.events if event["seq"] > since],
        }

    def reload_terrain(self, terrain, published):
        """Подменяет рельеф и размер мира без перезапуска сервера: мобы пересоздаются, игроки в препятствиях переставляются."""
        with self._lock:
            world_map.apply_live_terrain(terrain, published)
            self._mobs = self._build_mobs()
            self._refresh_structures()
            self._relocate_blocked()

    def sync_published_map(self):
        """Подхватывает публикацию, сделанную с другого сервера мира через общую БД; True, если рельеф обновлён."""
        published = self._database.published_map()
        if published is None or published["published_at"] == world_map.PUBLISHED_AT:
            return False
        terrain, published = map_editor.load_published_map(self._database, published)
        if terrain is None:
            return False
        self.reload_terrain(terrain, published)
        return True

    def _relocate_blocked(self):
        for player in self._players.values():
            if self._terrain_blocked(player.x, player.y):
                player.x, player.y = self._nearest_free(player.x, player.y)
        for mob in self._mobs.values():
            if self._terrain_blocked(mob.home_x, mob.home_y):
                mob.home_x, mob.home_y = self._nearest_free(mob.home_x, mob.home_y)
            if self._terrain_blocked(mob.x, mob.y):
                mob.x, mob.y = mob.home_x, mob.home_y

    def _nearest_free(self, x, y):
        """Ближайшая свободная точка: кольца вокруг (x, y) с шагом в четверть тайла, не дальше 20 тайлов."""
        step = TILE // 4
        for ring in range(1, 20 * 4 + 1):
            offsets = sorted(
                ((dx * step, dy * step) for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)
                 if max(abs(dx), abs(dy)) == ring),
                key=lambda offset: math.hypot(*offset),
            )
            for dx, dy in offsets:
                if not self._terrain_blocked(x + dx, y + dy):
                    return float(x + dx), float(y + dy)
        return float(world_map.MAP_SPAWN_PX[0]), float(world_map.MAP_SPAWN_PX[1])

    # ----- публичный API -----

    def sync(self, user_id, character_id, payload):
        """Намерения игрока: позиция, цель удара, рывок. Возвращает снимок мира для игрока."""
        now = self._clock()
        x, y = _read_point(payload.get("x"), payload.get("y"))
        since = payload.get("since") or 0
        if not isinstance(since, int) or isinstance(since, bool):
            since = 0
        with self._lock:
            player = self._players.get(character_id)
            if player is None:
                player = self._load_player(user_id, character_id, x, y)
                accepted = True
            elif player.user_id != user_id:
                raise ValueError("Персонаж не найден")
            else:
                elapsed = now - player.last_sync
                if player.dash is not None:
                    accepted = False
                else:
                    accepted = self._accept_move(player, x, y, elapsed)
            player.last_sync = now
            player.last_seen = now

            target_id = payload.get("attack_target")
            target = self._mobs.get(target_id) if isinstance(target_id, str) else None
            player.attack_target = target if target is not None and target.alive else None

            dash_target = payload.get("dash_target")
            if dash_target is not None:
                if not isinstance(dash_target, dict):
                    raise ValueError("Некорректная цель рывка")
                self._request_dash(player, _read_point(dash_target.get("x"), dash_target.get("y")))

            return self._snapshot(player, since, accepted)

    def leave(self, user_id, character_id):
        with self._lock:
            player = self._players.get(character_id)
            if player is None or player.user_id != user_id:
                return
            self._drop_player(player)

    def rest(self, user_id, character_id):
        """Полное восстановление HP и MP в городе или у кристалла: сервер сам сохраняет значения."""
        with self._lock:
            player = self._players.get(character_id)
            if player is not None and player.user_id == user_id:
                player.fighter.hp = player.fighter.max_hp
                player.fighter.mp = player.fighter.max_mp
                player.dirty = True
                return self._flush(player)
            vitals = self._database.rest_character(user_id, character_id)
            presence.update_character_vitals(
                character_id, vitals["hp"], vitals["mp"], vitals["max_hp"], vitals["max_mp"])
            return vitals

    def start(self):
        with self._lock:
            if self._thread is not None:
                return
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run, name="world-service", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
        self._thread = None
        with self._lock:
            for player in list(self._players.values()):
                self._drop_player(player)

    def _run(self):
        last = self._clock()
        next_publish_check = last
        while not self._stop_event.wait(TICK_INTERVAL):
            now = self._clock()
            dt = min(now - last, MAX_TICK_DT)
            last = now
            if now >= next_publish_check:
                next_publish_check = now + PUBLISH_CHECK_INTERVAL
                try:
                    self.sync_published_map()
                except Exception as error:
                    print(f"[world] ошибка проверки публикации карты: {error}", file=sys.stderr)
            try:
                self.advance(dt)
            except Exception as error:  # один сбой тика не должен останавливать мир
                print(f"[world] ошибка тика: {error}", file=sys.stderr)

    def advance(self, dt):
        """Шаг мира на dt секунд. Вызывается фоновым потоком и тестами."""
        with self._lock:
            self._structures_timer -= dt
            if self._structures_timer <= 0:
                self._structures_timer = STRUCTURES_REFRESH_INTERVAL
                self._refresh_structures()
            self._update_mobs(dt)
            now = self._clock()
            for player in list(self._players.values()):
                if now - player.last_seen > PLAYER_IDLE_TIMEOUT:
                    self._drop_player(player)
                    continue
                try:
                    self._tick_player(player, dt)
                except Exception as error:
                    print(f"[world] ошибка игрока {player.character_id}: {error}", file=sys.stderr)

    def _tick_player(self, player, dt):
        self._update_player_attack(player, dt)
        self._update_dash(player, dt)
        player.trails = [{**trail, "ttl": trail["ttl"] - dt} for trail in player.trails if trail["ttl"] - dt > 0]
        player.dash_cooldown = max(0.0, player.dash_cooldown - dt)
        player.carry_timer -= dt
        if player.carry_timer <= 0:
            self._refresh_carry(player)
        self._regenerate(player, dt)
        if player.dirty:
            player.flush_timer += dt
            full = player.fighter.hp >= player.fighter.max_hp and player.fighter.mp >= player.fighter.max_mp
            if full or player.flush_timer >= FLUSH_INTERVAL:
                self._flush(player)

    def _drop_player(self, player):
        self._flush(player)
        self._players.pop(player.character_id, None)
        for mob in self._mobs.values():
            if mob.target is player:
                mob.target = None
                mob.patrol_target = None
                mob.windup = 0.0
                mob.state = "idle"

    def _flush(self, player):
        fighter = player.fighter
        vitals = self._database.save_world_vitals(player.user_id, player.character_id, fighter.hp, fighter.mp)
        player.dirty = False
        player.flush_timer = 0.0
        presence.update_character_vitals(
            player.character_id, vitals["hp"], vitals["mp"], vitals["max_hp"], vitals["max_mp"])
        return vitals

    def _regenerate(self, player, dt):
        fighter = player.fighter
        hp_before, mp_before = fighter.hp, fighter.mp
        if fighter.hp < fighter.max_hp:
            player.hp_accumulator += get_hp_regen_per_second(fighter) * dt
            gained = int(player.hp_accumulator)
            if gained:
                fighter.hp = min(fighter.max_hp, fighter.hp + gained)
                player.hp_accumulator -= gained
        else:
            player.hp_accumulator = 0.0
        if fighter.mp < fighter.max_mp:
            player.mp_accumulator += get_mana_regen_per_second(fighter) * dt
            gained = int(player.mp_accumulator)
            if gained:
                fighter.mp = min(fighter.max_mp, fighter.mp + gained)
                player.mp_accumulator -= gained
        else:
            player.mp_accumulator = 0.0
        if fighter.hp != hp_before or fighter.mp != mp_before:
            player.dirty = True

    # ----- мобы -----

    def _update_mobs(self, dt):
        for mob in self._mobs.values():
            if not mob.alive:
                mob.respawn_timer = max(0.0, mob.respawn_timer - dt)
                if mob.respawn_timer <= 0:
                    self._respawn_mob(mob)
                continue
            if mob.attitude == "friendly":
                helping = self._helping_target(mob)
                if helping is not None:
                    self._help_fight(mob, helping, dt)
                    continue
            if mob.state != "chase":
                target = self._aggro_target(mob)
                if target is not None:
                    mob.state = "chase"
                    mob.target = target
                    mob.patrol_target = None
            if mob.state == "chase":
                self._update_mob_chase(mob, dt)
            else:
                self._update_mob_patrol(mob, dt)
                if mob.backswing > 0:
                    mob.backswing = max(0.0, mob.backswing - dt)

    def _aggro_target(self, mob):
        """Игрок, на которого нападает моб: агрессивный — ближайший в зоне агрессии; нейтральный — только обидчик;
        дружественный не нападает на игроков."""
        if mob.attitude == "friendly":
            return None
        if mob.attitude == "neutral":
            provoker = mob.provoker
            return provoker if provoker is not None and self._players.get(provoker.character_id) is provoker else None
        best = None
        best_distance = math.inf
        for player in self._players.values():
            if abs(player.x - mob.home_x) > mob.aggro_px or abs(player.y - mob.home_y) > mob.aggro_px:
                continue
            distance = math.hypot(player.x - mob.home_x, player.y - mob.home_y)
            if distance < best_distance:
                best, best_distance = player, distance
        return best

    def _helping_target(self, mob):
        """Дружественный моб помогает, если бой с игроком идёт в зоне его патруля: ближайший нападающий моб."""
        best = None
        best_distance = math.inf
        for other in self._mobs.values():
            if other is mob or not other.alive or other.attitude == "friendly" or other.state != "chase":
                continue
            if abs(other.x - mob.home_x) > mob.aggro_px or abs(other.y - mob.home_y) > mob.aggro_px:
                continue
            distance = math.hypot(other.x - mob.x, other.y - mob.y)
            if distance < best_distance:
                best, best_distance = other, distance
        return best

    def _help_fight(self, mob, enemy, dt):
        """Удар дружественного моба по нападающему мобу: идёт к нему и бьёт с откатом."""
        if mob.backswing > 0:
            mob.backswing = max(0.0, mob.backswing - dt)
        dx, dy = enemy.x - mob.x, enemy.y - mob.y
        distance = math.hypot(dx, dy)
        if distance > TILE:
            if distance <= 0:
                return
            step = mob.move_speed * dt
            nx, ny = mob.x + dx / distance * step, mob.y + dy / distance * step
            if not self._terrain_blocked(nx, ny):
                mob.x, mob.y = nx, ny
            return
        if mob.backswing > 0:
            return
        result = resolve_world_melee_attack(
            mob.fighter, enemy.fighter, self._rng,
            defender_facing=enemy.facing,
            attack_vector=(mob.x - enemy.x, mob.y - enemy.y),
        )
        if result["outcome"] == "hit":
            self._damage_mob(enemy, result["damage"])
        mob.backswing = mob.backswing_time

    def _respawn_mob(self, mob):
        mob.x, mob.y = mob.home_x, mob.home_y
        mob.fighter.hp = mob.fighter.max_hp
        mob.coins_copper = mob.reward_copper
        mob.damage_by = {}
        mob.state = "idle"
        mob.respawn_timer = 0.0
        mob.patrol_target = None
        mob.patrol_pause = 0.0
        mob.windup = 0.0
        mob.windup_total = 0.0
        mob.backswing = 0.0
        mob.target = None

    def _pick_patrol_point(self, mob):
        if mob.patrol_cells:
            for _ in range(20):
                dx, dy = self._rng.choice(mob.patrol_cells)
                px, py = mob.home_x + dx * TILE, mob.home_y + dy * TILE
                if not self._terrain_blocked(px, py):
                    return (px, py)
            return None
        radius = MOB_PATROL_RADIUS_TILES
        for _ in range(20):
            px = mob.home_x + self._rng.randint(-radius, radius) * TILE
            py = mob.home_y + self._rng.randint(-radius, radius) * TILE
            if not self._terrain_blocked(px, py):
                return (px, py)
        return None

    def _update_mob_patrol(self, mob, dt):
        if mob.patrol_pause > 0:
            mob.patrol_pause = max(0.0, mob.patrol_pause - dt)
            return
        if mob.patrol_target is None:
            mob.patrol_target = self._pick_patrol_point(mob)
            if mob.patrol_target is None:
                return
        tx, ty = mob.patrol_target
        dx, dy = tx - mob.x, ty - mob.y
        distance = math.hypot(dx, dy)
        step = mob.move_speed * MOB_PATROL_SPEED / BASE_MOVE_SPEED * dt
        if distance <= step:
            mob.x, mob.y = tx, ty
            mob.patrol_target = None
            mob.patrol_pause = MOB_PATROL_PAUSE
            return
        nx = mob.x + dx / distance * step
        ny = mob.y + dy / distance * step
        if self._terrain_blocked(nx, ny) or self._mob_blocked_by_players(nx, ny):
            mob.patrol_target = None
        else:
            mob.facing = math.atan2(dy, dx)  # во время патруля взгляд по ходу движения
            mob.x, mob.y = nx, ny

    def _update_mob_chase(self, mob, dt):
        if mob.backswing > 0:
            mob.backswing = max(0.0, mob.backswing - dt)
        player = mob.target
        leash_distance = math.hypot(player.x - mob.home_x, player.y - mob.home_y) if player else math.inf
        if player is None or leash_distance > MOB_LEASH_DISTANCE:
            mob.state = "idle"
            mob.target = None
            mob.patrol_target = None
            mob.windup = 0.0
            return
        reach = get_attack_reach(mob.fighter)
        if mob.windup <= 0:
            if self._distance_to_player(mob, player) > reach:
                self._move_mob_toward(mob, player, dt)
                return
            if mob.backswing > 0:
                self._move_mob_toward(mob, player, dt)
                return
            mob.windup = mob.windup_time
            mob.windup_total = mob.windup
            mob.facing = math.atan2(player.y - mob.y, player.x - mob.x)
        mob.windup = max(0.0, mob.windup - dt)
        if mob.windup <= 0:
            if self._distance_to_player(mob, player) <= reach:
                self._mob_strike(mob, player)
            else:
                self._emit_label(player, "miss", mob.x, mob.y - MOB_LABEL_OFFSET)
            mob.backswing = mob.backswing_time

    def _distance_to_player(self, mob, player):
        return _distance_to_rect(player.x, player.y, _mob_reach_rect(mob.x, mob.y))

    def _move_mob_toward(self, mob, player, dt):
        dx, dy = player.x - mob.x, player.y - mob.y
        distance = math.hypot(dx, dy)
        if distance <= 0:
            return
        mob.facing = math.atan2(dy, dx)
        step = mob.move_speed * dt
        nx = mob.x + dx / distance * step
        ny = mob.y + dy / distance * step
        if not self._terrain_blocked(nx, ny) and not self._mob_blocked_by_players(nx, ny):
            mob.x, mob.y = nx, ny

    def _mob_strike(self, mob, player):
        result = resolve_world_melee_attack(
            mob.fighter, player.fighter, self._rng,
            defender_facing=player.facing,
            attack_vector=(mob.x - player.x, mob.y - player.y),
        )
        top_y = player.y - PLAYER_HEAD_OFFSET
        names = mob.log_names
        if result["outcome"] != "hit":
            self._emit_label(player, result["outcome"], player.x, top_y)
            self._emit_log(player, MOB_MISS_LOG_TEXT[result["outcome"]].format(**names), "miss")
            return
        player.fighter.hp = max(0, player.fighter.hp - result["damage"])
        player.dirty = True
        self._emit_number(player, result["damage"], result["critical"], player.x, top_y)
        crit_text = " (критический)" if result["critical"] else ""
        self._emit_log(player, f"{names['nom']} нанес вам {result['damage']} урона{crit_text}", "enemy")
        if player.fighter.hp <= 0:
            self._player_died(player)

    # ----- бой игрока -----

    def _update_player_attack(self, player, dt):
        if player.backswing > 0:
            player.backswing = max(0.0, player.backswing - dt)
            return
        if player.windup <= 0:
            mob = player.attack_target
            if mob is None or not mob.alive or player.dash is not None:
                return
            if _distance_to_rect(player.x, player.y, _mob_reach_rect(mob.x, mob.y)) > get_attack_reach(player.fighter):
                return  # до цели идёт клиент, сервер замах не начинает вне зоны удара
            player.windup_target = mob
            player.windup = get_attack_windup(player.fighter)
            player.windup_total = player.windup
            player.swing_id += 1
            player.facing = _quantize_facing(math.atan2(mob.y - player.y, mob.x - player.x))
        player.windup = max(0.0, player.windup - dt)
        if player.windup > 0:
            return
        target = player.windup_target
        player.windup_target = None
        if target is None or not target.alive:
            return  # цель пропала во время замаха: удара и отката нет
        reach = get_attack_reach(player.fighter)
        if _distance_to_rect(player.x, player.y, _mob_reach_rect(target.x, target.y)) <= reach:
            self._strike_mob(player, target)
        else:
            self._emit_label(player, "miss", target.x, target.y - MOB_LABEL_OFFSET)
        player.backswing = get_attack_backswing(player.fighter)

    def _strike_mob(self, player, mob):
        mob.provoker = player
        result = resolve_world_melee_attack(
            player.fighter, mob.fighter, self._rng,
            defender_facing=mob.facing,
            attack_vector=(player.x - mob.x, player.y - mob.y),
        )
        wx, wy = mob.x, mob.y - MOB_LABEL_OFFSET
        names = mob.log_names
        if result["outcome"] != "hit":
            self._emit_label(player, result["outcome"], wx, wy)
            self._emit_log(player, PLAYER_MISS_LOG_TEXT[result["outcome"]].format(**names), "miss")
            return
        dealt = self._damage_mob(mob, result["damage"], player)
        self._emit_number(player, dealt, result["critical"], wx, wy)
        crit_text = " (критический)" if result["critical"] else ""
        self._emit_log(player, f"Вы нанесли {names['dat']} {dealt} урона{crit_text}", "player")
        if not mob.alive:
            self._defeat_mob(mob, player)

    def _damage_mob(self, mob, damage, attacker=None):
        hp_before = mob.fighter.hp
        mob.fighter.hp = max(0, hp_before - damage)
        dealt = hp_before - mob.fighter.hp
        if attacker is not None and dealt > 0:
            user_id, total = mob.damage_by.get(attacker.character_id, (attacker.user_id, 0))
            mob.damage_by[attacker.character_id] = (user_id, total + dealt)
        return dealt

    def _defeat_mob(self, mob, killer):
        mob.state = "dead"
        mob.respawn_timer = mob.respawn_delay
        mob.windup = 0.0
        mob.windup_total = 0.0
        mob.backswing = 0.0
        mob.patrol_target = None
        mob.target = None
        for player in self._players.values():
            if player.windup_target is mob:
                player.windup_target = None
                player.windup = 0.0
            if player.attack_target is mob:
                player.attack_target = None
        name = mob.log_names["nom"]
        self._emit_log(killer, f"{name} повержен", "player")
        self._reward_mob(mob, killer)

    def _reward_mob(self, mob, killer):
        """Добыча и опыт делятся по доле урона: награда × нанесённый урон / максимальное HP моба.

        Сумма долей не больше награды: урон каждого игрока ограничен остатком HP моба.
        Оставшиеся монеты после округления не выдаются. Монеты моба обнуляются до респауна.
        """
        name = mob.log_names["nom"]
        max_hp = mob.fighter.max_hp
        copper_pool = mob.coins_copper
        contributions = [
            (character_id, user_id, dealt)
            for character_id, (user_id, dealt) in mob.damage_by.items()
            if dealt > 0
        ]
        mob.damage_by = {}
        mob.coins_copper = 0
        parts_by_character = {killer.character_id: []}
        for character_id, user_id, dealt in contributions:
            parts = parts_by_character.setdefault(character_id, [])
            copper = copper_pool * dealt // max_hp
            if copper > 0:
                currency = self._database.add_world_currency(user_id, character_id, copper)
                player = self._online_player(user_id, character_id)
                if player is not None:
                    self._emit(player, {"type": "currency", "currency": currency})
                parts.append(f"Добыча: {Currency.format_amount(copper)}")
            xp = mob.reward_xp * dealt // max_hp
            if xp > 0:
                levels_gained, level = self._grant_mob_xp(user_id, character_id, xp)
                parts.append(f"Опыт: +{xp}")
                if levels_gained:
                    parts.append(f"Новый уровень: {level}")
        for character_id, parts in parts_by_character.items():
            player = self._players.get(character_id)
            if player is None:
                continue
            notice = f"{name} повержен"
            if parts:
                notice = f"{notice}. {'. '.join(parts)}"
            self._emit_notice(player, notice)

    def _online_player(self, user_id, character_id):
        player = self._players.get(character_id)
        if player is None or player.user_id != user_id:
            return None
        return player

    def _grant_mob_xp(self, user_id, character_id, amount):
        """Опыт за моба. Онлайн-персонаж получает его в памяти и сразу видит в клиенте, офлайн — пишется в базу.

        Возвращает (сколько уровней получено, итоговый уровень).
        """
        player = self._online_player(user_id, character_id)
        if player is not None:
            fighter = player.fighter
        else:
            character = self._database.get_character(user_id, character_id)
            if character is None:
                return 0, 0
            fighter = _fighter_from_character(character)
        levels_gained = apply_xp(fighter, amount)
        _apply_world_resource_formulas(fighter)
        self._database.save_world_progression(
            user_id, character_id, fighter.level, fighter.xp, dict(fighter.stats),
            fighter.stat_points, fighter.max_hp)
        if player is not None:
            presence.update_character_vitals(
                character_id, fighter.hp, fighter.mp, fighter.max_hp, fighter.max_mp)
            self._emit(player, {
                "type": "progress",
                "character": {
                    "level": fighter.level,
                    "xp": fighter.xp,
                    "stat_points": fighter.stat_points,
                    "stats": dict(fighter.stats),
                    "max_hp": fighter.max_hp,
                },
            })
        return levels_gained, fighter.level

    # ----- рывок -----

    def _request_dash(self, player, target):
        if player.windup > 0 or player.dash is not None or player.dash_cooldown > 0:
            return
        start = (player.x, player.y)
        if math.hypot(target[0] - start[0], target[1] - start[1]) < DASH_MIN_LENGTH:
            self._emit_message(player, player.x, player.y - PLAYER_HEAD_OFFSET, "Слишком близко")
            return
        end = dash_end_point(start, target)
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        player.attack_target = None
        player.dash = {
            "dir": ((end[0] - start[0]) / length, (end[1] - start[1]) / length),
            "start": start,
            "length": length,
            "travelled": 0.0,
            "trail_gap": 0.0,
            "hit": set(),
        }
        player.dash_cooldown = DASH_COOLDOWN
        player.facing = _quantize_facing(math.atan2(end[1] - start[1], end[0] - start[0]))

    def _update_dash(self, player, dt):
        dash = player.dash
        if dash is None:
            return
        dx, dy = dash["dir"]
        budget = DASH_SPEED * dt
        while budget > 0 and dash["travelled"] < dash["length"]:
            step = min(DASH_STEP, budget, dash["length"] - dash["travelled"])
            budget -= step
            nx = player.x + dx * step
            ny = player.y + dy * step
            if self._terrain_blocked(nx, ny):
                self._finish_dash(player)
                return
            player.x, player.y = nx, ny
            dash["travelled"] += step
            dash["trail_gap"] += step
            if dash["trail_gap"] >= DASH_TRAIL_STEP:
                dash["trail_gap"] = 0.0
                player.trails.append({"x": nx, "y": ny, "ttl": DASH_TRAIL_DURATION})
            self._dash_hit_mobs(player)
        if player.dash is not None and dash["travelled"] >= dash["length"] - 1e-6:
            self._finish_dash(player)

    def _dash_hit_mobs(self, player):
        dash = player.dash
        here = (player.x, player.y)
        for mob in self._mobs.values():
            if not mob.alive or mob.id in dash["hit"]:
                continue
            if point_segment_distance((mob.x, mob.y), dash["start"], here) <= DASH_HIT_RADIUS:
                dash["hit"].add(mob.id)
                self._dash_damage_mob(player, mob, dash_damage_roll(self._rng), "Рывок")

    def _dash_damage_mob(self, player, mob, damage, label):
        """Урон рывка и кругового удара: без уворота и блока."""
        dealt = self._damage_mob(mob, damage, player)
        self._emit_number(player, dealt, False, mob.x, mob.y - MOB_LABEL_OFFSET)
        self._emit_log(player, f"{label}: вы нанесли {mob.log_names['dat']} {dealt} урона", "player")
        if not mob.alive:
            self._defeat_mob(mob, player)

    def _finish_dash(self, player):
        dash = player.dash
        player.dash = None
        sx, sy = dash["start"]
        dx, dy = dash["dir"]
        end = dash["travelled"]
        exit_point = self._exit_mob_forward(sx + dx * end, sy + dy * end, dx, dy)
        if exit_point is not None:
            player.x, player.y = exit_point
        else:
            back = end
            while back > 0 and self._player_blocked(sx + dx * back, sy + dy * back):
                back = max(0.0, back - DASH_RETREAT_STEP)
            player.x, player.y = sx + dx * back, sy + dy * back
        self._whirl_strike(player)

    def _exit_mob_forward(self, x, y, dx, dy):
        """Точка выхода из тела моба по линии рывка; None, если впереди стена."""
        travelled = 0.0
        while self._player_blocked(x, y):
            if travelled >= DASH_EXIT_MAX or self._terrain_blocked(x + dx * DASH_RETREAT_STEP, y + dy * DASH_RETREAT_STEP):
                return None
            x += dx * DASH_RETREAT_STEP
            y += dy * DASH_RETREAT_STEP
            travelled += DASH_RETREAT_STEP
        return (x, y)

    def _whirl_strike(self, player):
        self._emit(player, {"type": "whirl"})
        for mob in list(self._mobs.values()):
            if not mob.alive:
                continue
            if math.hypot(mob.x - player.x, mob.y - player.y) <= WHIRL_STRIKE_RADIUS:
                self._dash_damage_mob(player, mob, whirl_strike_damage_roll(self._rng), "Круговой удар")
