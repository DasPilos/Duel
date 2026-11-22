"""Server-authoritative matchmaking and lane defense for Front Line."""

import heapq
from collections import deque
import math
import time
from types import SimpleNamespace

from combat.fighter import Fighter
from combat.character_stats import (
    CREATION_ALLOCATABLE_STATS,
    BASE_STAT_VALUE,
    calculate_max_hp,
    calculate_max_mana,
    creation_stats,
    minimum_endurance,
)
from combat import world_stats
from combat.progression import apply_xp, xp_to_next
from core import mob_modes
from core.spawn_squads import planned_squad_ticks, squad_size
from core.map_catalog import grassland_tiles
from core.tile_mask import load_partial_masks
from server import map_editor, presence, world_map
from server.perf_probe import timed
from server.world_map import TILE
from front_line.server import combat as front_line_combat

# Главное здание: 5×5 клеток. Клетка спауна — левый верхний угол footprint.
BUILDING_FOOTPRINT_TILES = 5
from front_line.server.world_mobs import (
    _distance_to_rect,
    MOB_LABEL_OFFSET,
    MOB_PROFILES,
    MOB_MISS_LOG_TEXT,
    PLAYER_HEAD_OFFSET,
    PLAYER_MISS_LOG_TEXT,
    WorldService,
    _Mob,
    FEET_H,
    FEET_W,
    MOB_BODY_OFFSET_Y,
    _feet_rect,
    _fighter_from_character,
    _read_point,
    _apply_world_resource_formulas,
    _quantize_facing,
    _rects_collide,
)

START_WAIT_SECONDS = 120
CHARACTER_DRAFT_SECONDS = 10
WAVE_DRAFT_SECONDS = 10
FRONT_LINE_PROFESSIONS = ("warrior", "archer", "mage")
# Уровень, с которого каждая сессия мира начинает героя (опыт сессии в базу не пишется).
FRONT_LINE_START_LEVEL = 1
# Правило режима Front Line, не связано с созданием персонажа (1000 меди — правило экономического сервера).
# Кошелёк героя в начале каждой игры: 100 меди = 1 серебро.
FRONT_LINE_START_WALLET = {"copper": 0, "silver": 1, "gold": 0}
DEFAULT_DRAFT_ALLOCATION = {stat: BASE_STAT_VALUE for stat in CREATION_ALLOCATABLE_STATS}
MAX_ACTIVE_MOBS = map_editor.MAX_MOB_SPAWN_COUNT
ATTACK_FIELD_REFRESH_TICKS = 2
# Стоимость клетки, занятой другим мобом, в поле движения к герою: очередь дороже обхода.
CHASE_OCCUPIED_COST = 3


MOB_CORPSE_SECONDS = 3.0
ITEM_DROP_PICKUP_RANGE = TILE * 3.0
OBJECTIVE_ATTACK_RANGE = TILE * 3.0
# Атакующий моб продолжает бить, пока толпа не вытолкнет его дальше этого порога.
OBJECTIVE_ATTACK_KEEP_RANGE = OBJECTIVE_ATTACK_RANGE + TILE  # полтайла по старой сетке 32 px
OBJECTIVE_ATTACK_KEEP_CELLS = 3.0  # полтора клетки по 32 px
OBJECTIVE_FLOW_LOOKAHEAD_CELLS = 8  # четыре клетки по 32 px
FLOW_NEIGHBOURS = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)),
    (-1, 1, math.sqrt(2.0)), (-1, -1, math.sqrt(2.0)),
)
MOB_SEPARATION_RADIUS = TILE  # полтайла по старой сетке 32 px: радиус тела моба 16 px
# Клетка сетки мобов: не меньше самой широкой пары тел (два босса), иначе соседи пропустятся.
MOB_BUCKET_PX = 2.0 * MOB_SEPARATION_RADIUS * 4.0
BOSS_SEPARATION_SCALE = 4.0
MOB_SEPARATION_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
# Отклонения от направления к цели, которыми моб обходит героя: сначала в выбранную сторону.
MOB_DETOUR_ANGLES = tuple(math.radians(angle) for angle in (30, 60, 90, 120))
# Если моб не может обойти героя дольше этого времени, он пробует углы шире (до 150°).
MOB_STUCK_SECONDS = 0.3
# Соседние клетки погони: поле расстояний считается по 4 направлениям.
CHASE_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _angle_gap(a, b):
    d = (a - b + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)
# Кольца вокруг героя: первое — в зоне удара, второе — ожидание за первым рядом. Радиусы в px от центра героя.
RING_RADII_PX = (34.0, 66.0)
RING_SLOTS = (8, 14)
RING_RELEASE_RADIANS = math.radians(60)
# Поле мест удара у героя: занятое другой крысой место дорого, а клетка с крысой — немного дороже.
ATTACK_SPOT_TAKEN_COST = 60
CELL_OCCUPIED_COST = 2
# Тело героя для проверки, не загораживает ли он путь к месту кольца.
HERO_PATH_RADIUS_PX = 12.0
MOB_STUCK_DETOUR_ANGLES = tuple(math.radians(angle) for angle in (30, 60, 90, 120, 150))
BOSS_WAVE_DELAY_SECONDS = 30
GRASSLAND_WATER_COAST_CATEGORIES = {
    int(item["tile_id"]): item["category"]
    for item in grassland_tiles()
    if item.get("sheet", "").lower() == "water_coasts"
}
# Земля пустой карты ожидания: тайл листа травы художника (base_tails), каталога больше нет.
WAITING_GROUND_KEY = (
    "atlas|res://assets/base_tails/Biome/craftpix-net-189510-grassland-top-down-tileset-pixel-art/"
    "Tiled_files/ground_grasss.png|0|0"
)


class FrontLineWorldService(WorldService):
    def __init__(
        self, database, items_database, *, start_wait_seconds=START_WAIT_SECONDS,
        character_draft_seconds=CHARACTER_DRAFT_SECONDS,
        wave_draft_seconds=WAVE_DRAFT_SECONDS, **kwargs,
    ):
        self._start_wait_seconds = max(1.0, float(start_wait_seconds))
        self._character_draft_seconds = max(1.0, float(character_draft_seconds))
        self._wave_draft_seconds = max(1.0, float(wave_draft_seconds))
        self._start_deadline = 0.0
        self._game_started = False
        self._character_draft_active = False
        self._character_draft_deadline = 0.0
        self._wave_draft_deadline = 0.0
        self._character_draft_choices = {}
        self._character_draft_results = {}
        self._waves_unlocked = False
        self._waves_unlocked_at = 0.0
        self._round_countdown_zero_until = 0.0
        self._match_result = ""
        # Счётчики героев за текущий раунд и итоги матча для экрана результатов.
        self._round_stats = {}
        self._round_mobs_killed = 0
        self._match_summary = None
        # Кошельки персонажей на момент входа в игру: монеты игры к ним не возвращаются.
        self._session_wallets = {}
        self._map_started_at = 0.0
        self._map_name = ""
        self._map_id = 0
        self._map_width = 16
        self._map_height = 16
        self._map_editor_layers = []
        self._hero_spawns = []
        self._pending_spawns = []
        self._mob_spawners = []
        self._spawn_sequence = 0
        self._mob_profile_cache = {}
        self._mob_profile_mtime = None
        self._item_drops = {}
        self._item_drop_sequence = 0
        self._game_started_at = 0.0
        self._building_states = []
        self._objective_flow_cache = None
        super().__init__(database, items_database, **kwargs)
        self._start_deadline = self._clock() + self._start_wait_seconds
        self._refresh_waiting_map()

    def _build_mobs(self):
        return {}

    def _build_wildlife(self):
        return {}

    @staticmethod
    def _mob_settings_mtime():
        try:
            return mob_modes.mode_file("front_line").stat().st_mtime_ns
        except OSError:
            return None

    def _mob_profile(self, kind):
        # Настройки правят в редакторе карт: если файл изменился, перечитываем. Новые мобы получат новые значения.
        mtime = self._mob_settings_mtime()
        if mtime != self._mob_profile_mtime:
            self._mob_profile_cache.clear()
            self._mob_profile_mtime = mtime
        if kind not in self._mob_profile_cache:
            try:
                self._mob_profile_cache[kind] = mob_modes.load_mob_settings("front_line", kind)
            except mob_modes.ModeFileError as error:
                print(f"[front_line] Не удалось загрузить настройки моба {kind}: {error}")
                self._mob_profile_cache[kind] = mob_modes.default_settings(kind)
        return self._mob_profile_cache[kind]

    @staticmethod
    def _mob_payload(mob):
        payload = WorldService._mob_payload(mob)
        payload.update({
            "mp": mob.fighter.mp,
            "max_mp": mob.fighter.max_mp,
            "backswing": mob.backswing,
            "backswing_total": mob.backswing_time,
            "is_boss": bool(getattr(mob, "is_boss", False)),
            "attack_style": str(getattr(mob, "attack_style", "warrior")),
            "attack_range_px": front_line_combat.range_units_to_px(
                getattr(mob, "attack_range_units", None) or front_line_combat.MOB_ATTACK_RANGE_UNITS),
            "front_line": True,
        })
        return payload

    def _player_payload(self, player):
        payload = super()._player_payload(player)
        fighter = player.fighter
        payload["backswing_total"] = self._player_backswing_time(player)
        payload["level"] = int(fighter.level)
        payload["xp"] = int(fighter.xp)
        payload["xp_to_next"] = xp_to_next(fighter.level)
        payload["reach"] = self._player_attack_range_px(player)
        payload["attack_range"] = int(front_line_combat.hero_attack_range_units(fighter))
        payload["projectile"] = front_line_combat.projectile_kind(fighter.profession_type)
        payload["projectile_speed"] = front_line_combat.projectile_speed_px(fighter.profession_type)
        payload["projectiles"] = [
            {
                "id": projectile["id"],
                "kind": projectile["kind"],
                "from": [projectile["from"][0], projectile["from"][1]],
                "target": projectile["target"].id,
                "radius": front_line_combat.MAGE_AREA_RADIUS_UNITS if projectile["kind"] == "orb" else 0,
                "pos": [round(projectile["pos"][0], 2), round(projectile["pos"][1], 2)],
                "speed": round(projectile["speed"], 2),
            }
            for projectile in self._projectile_list()
            if projectile["owner"] is player
        ]
        return payload

    def _spawn_pixels(self):
        if self._hero_spawns:
            return list(self._hero_spawns)
        return [tuple(world_map.MAP_SPAWN_PX)]

    def _entry_position(self, saved_x, saved_y):
        spawns = self._spawn_pixels()
        index = len(self._players) % len(spawns)
        return spawns[index]

    def _load_player(self, user_id, character_id, x, y):
        player = super()._load_player(user_id, character_id, x, y)
        if self._map_id > 0 and not self._game_started and not self._character_draft_active:
            self._start_first_map()
        return player

    MOB_DYNAMIC_KEYS = (
        "id", "x", "y", "hp", "mp", "state", "respawn_timer", "facing", "windup", "windup_total",
        "backswing", "backswing_total", "swing_id", "hurt_id", "coins",
    )

    def _apply_orders(self, player, payload):
        """Синхронизация несёт только добычу и рывок: приказы (цель, стоп, удержание) приходят командами."""
        self._set_harvest_target(player, payload.get("harvest_target"))
        dash_target = payload.get("dash_target")
        if dash_target is not None:
            if not isinstance(dash_target, dict):
                raise ValueError("Некорректная цель рывка")
            self._request_dash(player, _read_point(dash_target.get("x"), dash_target.get("y")))

    def command(self, user_id, character_id, payload):
        """Приказ игрока (атака, стоп, удержание, очко характеристики): применяется сразу, отдельно от синхронизации."""
        with self._lock:
            player = self._players.get(int(character_id))
            if player is None or player.user_id != user_id:
                raise ValueError("Персонаж не находится в этом мире")
            self._apply_command(player, payload)
        return {"ok": True}

    def _apply_command(self, player, payload):
        order_id = payload.get("order_id")
        if isinstance(order_id, int) and not isinstance(order_id, bool) and order_id != player.order_seq:
            player.order_seq = order_id
            self._cancel_attack(player)
        if "attack_target" in payload:
            target_id = payload.get("attack_target")
            target = self._mobs.get(target_id) if isinstance(target_id, str) else None
            player.attack_target = target if target is not None and target.alive else None
        if "hold" in payload:
            player.hold = payload.get("hold") is True
        if payload.get("stop") is True:
            player.attack_target = None
        stats = payload.get("allocate_stats")
        if isinstance(stats, list):
            for stat in stats:
                self._allocate_stat(player, stat)

    def _compact_mobs(self, player, mobs):
        """Постоянные поля моба (имя, описание, характеристики, экипировка) уходят один раз; дальше только меняющиеся."""
        known = getattr(player, "known_mobs", None)
        if known is None:
            known = player.known_mobs = set()
        known.intersection_update({entry["id"] for entry in mobs})
        result = []
        for entry in mobs:
            if entry["id"] in known:
                compact = {key: entry[key] for key in self.MOB_DYNAMIC_KEYS if key in entry}
                compact["compact"] = True
                result.append(compact)
            else:
                known.add(entry["id"])
                result.append(entry)
        return result

    def _allocate_stat(self, player, stat):
        fighter = player.fighter
        if not isinstance(stat, str) or stat == "endurance" or stat not in fighter.stats or fighter.stat_points <= 0:
            return
        fighter.stats[stat] = int(fighter.stats[stat]) + 1
        fighter.stat_points -= 1
        fighter.recalculate_parameters()
        _apply_world_resource_formulas(fighter)
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

    @timed("синхронизация с клиентом (включая ожидание замка тика)")
    def sync(self, user_id, character_id, payload):
        if payload.get("resync") is True:
            with self._lock:
                player = self._players.get(int(character_id))
                if player is not None:
                    player.known_mobs = set()
        return super().sync(user_id, character_id, payload)

    @timed("сборка снимка")
    def _snapshot(self, player, since, accepted):
        snapshot = super()._snapshot(player, since, accepted)
        snapshot["item_drops"] = [dict(drop) for drop in self._item_drops.values()]
        now = self._clock()
        snapshot["front_line"] = {
            "buildings": [
                {"x": b["x"], "y": b["y"], "sprite": b["sprite"], "hp": round(b["hp"], 1), "max_hp": b["max_hp"]}
                for b in getattr(self, "_building_states", [])
            ],
            "state": (
                "map_unavailable" if not self._game_started and self._map_id <= 0
                else "lost" if self._match_result == "lost" or (self._building_states and not self._any_building_alive())
                else "victory" if self._match_result == "victory"
                else "character_draft" if self._character_draft_active
                else "running" if self._waves_unlocked
                else "awaiting_wave_draft" if self._game_started
                else "waiting"
            ),
            "players_waiting": len(self._players),
            "starts_in_seconds": 0 if self._game_started else max(
                0, math.ceil(self._start_deadline - now),
            ),
            "draft_seconds_remaining": max(
                0, math.ceil(self._character_draft_deadline - now),
            ) if self._character_draft_active else 0,
            "wave_draft_seconds_remaining": max(
                0, math.ceil(self._wave_draft_deadline - now),
            ) if self._game_started and not self._waves_unlocked else 0,
            "round_countdown_active": self._game_started and (
                not self._waves_unlocked or now < self._round_countdown_zero_until
            ),
            "round_countdown_seconds": max(
                0, math.ceil(self._wave_draft_deadline - now),
            ) if self._game_started and not self._waves_unlocked else 0,
            "draft_players_ready": len(self._character_draft_choices),
            "draft_players_total": len(self._players) if self._character_draft_active else 0,
            "draft_selected": player.character_id in self._character_draft_choices,
            "draft_character": self._character_draft_results.get(player.character_id, {}),
            "map_id": self._map_id,
            "map_name": self._map_name,
            "map_width": self._map_width,
            "map_height": self._map_height,
            "match_started": self._game_started,
            "match_result": self._match_result,
            "match_summary": self._match_summary or {},
            "hero_visible": self._game_started and not self._character_draft_active,
            "elapsed_seconds": max(0, int(now - self._game_started_at))
            if self._game_started and not self._character_draft_active else 0,
            "objective": {
                "alive": sum(1 for b in self._building_states if b["hp"] > 0),
                "total": len(self._building_states),
            },
            "wave": self._wave_progress(now),
        }
        snapshot["mobs"] = self._compact_mobs(player, snapshot["mobs"])
        return snapshot

    @timed("тик мира")
    def advance(self, dt):
        super().advance(dt)
        with self._lock:
            self._update_projectiles(dt)
            now = self._clock()
            if self._game_started and not self._players:
                self._reset_matchmaking_round(now)
            if not self._game_started:
                if not self._players:
                    self._character_draft_active = False
                    self._character_draft_deadline = 0.0
                    self._character_draft_choices.clear()
                    self._start_deadline = now + self._start_wait_seconds
                elif not self._character_draft_active and now >= self._start_deadline:
                    self._start_first_map()
            if self._character_draft_active and now >= self._character_draft_deadline:
                self._complete_character_draft()
            if (
                self._game_started
                and not self._character_draft_active
                and not self._waves_unlocked
                and now >= self._wave_draft_deadline
            ):
                self._waves_unlocked = True
                self._waves_unlocked_at = now
                self._round_countdown_zero_until = now + 1.0
            if (
                self._game_started
                and self._waves_unlocked
                and (not self._building_states or self._any_building_alive())
                and not self._match_result
            ):
                self._advance_spawners(dt)
                self._check_match_victory()

    def _reset_matchmaking_round(self, now):
        self._reset_session_wallets()
        self._game_started = False
        self._character_draft_active = False
        self._character_draft_deadline = 0.0
        self._wave_draft_deadline = 0.0
        self._character_draft_choices.clear()
        self._character_draft_results.clear()
        self._waves_unlocked = False
        self._waves_unlocked_at = 0.0
        self._round_countdown_zero_until = 0.0
        self._map_started_at = 0.0
        self._game_started_at = 0.0
        self._hero_spawns = []
        self._pending_spawns = []
        self._mob_spawners = []
        self._spawn_sequence = 0
        self._mobs.clear()
        self._projectiles = []
        self._item_drops.clear()
        self._item_drop_sequence = 0
        self._match_result = ""
        self._round_stats = {}
        self._round_mobs_killed = 0
        self._match_summary = None
        self._building_states = []
        self._start_deadline = now + self._start_wait_seconds
        self._refresh_waiting_map()

    def map_visual_payload(self):
        with self._lock:
            return {
                "id": self._map_id,
                "name": self._map_name,
                "map_w": self._map_width,
                "map_h": self._map_height,
                "layers": [
                    {
                        "type": str(layer.get("type", "")),
                        "visible": bool(layer.get("visible", True)),
                        "cells": layer.get("cells", []),
                    }
                    for layer in self._visible_editor_layers(self._map_editor_layers)
                    if layer.get("type") in ("tile", "decorative")
                ],
            }

    def prepare_lobby_terrain(self):
        """Publish a Front Line map (or a neutral placeholder), never another mode's terrain."""
        with self._lock:
            if not self._game_started:
                self._refresh_waiting_map()

    def _refresh_waiting_map(self):
        saved = self._published_saved_map()
        catalog = self._database.map_catalog()
        if saved is None:
            ground_key = next(
                (item["item_key"] for item in catalog if item["kind"] == "ground"),
                WAITING_GROUND_KEY,
            )
            cells = [{"layer": "ground", "x": 0, "y": 0, "key": ground_key}]
            map_w = map_h = 16
            self._map_id = 0
            self._map_name = ""
            self._map_width = map_w
            self._map_height = map_h
            self._map_editor_layers = []
            self._hero_spawns = []
            crystals = {}
            harvest_enabled = False
        else:
            cells = saved["cells"]
            map_w = int(saved["map_w"])
            map_h = int(saved["map_h"])
            self._map_id = int(saved["id"])
            self._map_name = str(saved["name"])
            self._map_width = map_w
            self._map_height = map_h
            self._map_editor_layers = saved.get("editor_layers", [])
            self._hero_spawns = [
                (int(spawn["x"]) * TILE + TILE / 2, int(spawn["y"]) * TILE + TILE / 2)
                for spawn in saved["spawns"]
                if spawn.get("type", "hero") == "hero"
            ]
            crystals = saved["crystals"]
            harvest_enabled = bool(saved["harvest_enabled"])
        terrain_catalog = self._database.map_catalog()
        terrain_cells = self._editor_terrain_cells(
            cells, self._map_editor_layers, terrain_catalog,
        )
        terrain = map_editor.terrain_from_cells(
            terrain_cells, terrain_catalog, load_partial_masks(),
        )
        if terrain is None:
            ground = next(item for item in catalog if item["kind"] == "ground")
            terrain = map_editor.terrain_from_cells(
                [{"layer": "ground", "x": 0, "y": 0, "key": ground["item_key"]}],
                terrain_catalog,
                load_partial_masks(),
            )
        # Флаги проходимости слоёв редактора: мост и берег проходимы, вода и объекты — нет.
        terrain = map_editor.apply_layer_passability(terrain, self._map_editor_layers, map_w, map_h)
        self._apply_atlas_collision(terrain, self._map_editor_layers, map_w, map_h)
        self._building_states = self._buildings_from_saved(saved)
        terrain["impassable"] = set(terrain.get("impassable", ())) | self._building_tiles(self._building_states)
        published = {
            "map_w": map_w,
            "map_h": map_h,
            "published_at": time.time(),
            "crystals": crystals,
            "harvest_enabled": harvest_enabled,
        }
        world_map.apply_live_terrain(terrain, published)
        return saved

    @staticmethod
    def _visible_editor_layers(layers):
        layers_by_id = {
            int(layer.get("id", index + 1)): layer
            for index, layer in enumerate(layers)
        }
        visible_layers = []
        for index, layer in enumerate(layers):
            current = layer
            seen = set()
            visible = True
            while current:
                current_id = int(current.get("id", index + 1))
                if current_id in seen or not bool(current.get("visible", True)):
                    visible = False
                    break
                seen.add(current_id)
                parent_id = int(current.get("parent_id", 0))
                current = layers_by_id.get(parent_id, {})
            if visible:
                visible_layers.append(layer)
        return visible_layers

    @classmethod
    def _top_surface_cells(cls, layers):
        """Select the uppermost occupied non-decorative tile at each position."""
        top_cells = {}
        for layer in cls._visible_editor_layers(layers):
            if layer.get("type") != "tile":
                continue
            for cell in layer.get("cells", []):
                position = (int(cell.get("x", -1)), int(cell.get("y", -1)))
                if position[0] >= 0 and position[1] >= 0:
                    top_cells[position] = cell
        return top_cells

    @classmethod
    def _editor_terrain_cells(cls, cells, layers, catalog):
        """Use resolved surfaces, excluding flattened decorative and hidden tiles."""
        visible_layers = cls._visible_editor_layers(layers)
        tile_layers = [
            layer for layer in layers
            if layer.get("type") in ("tile", "decorative")
        ]
        if not tile_layers:
            return cells

        editor_layer_positions = {
            (int(cell.get("x", -1)), int(cell.get("y", -1)))
            for layer in tile_layers
            for cell in layer.get("cells", [])
            if int(cell.get("x", -1)) >= 0 and int(cell.get("y", -1)) >= 0
        }
        by_key = {item["item_key"]: item for item in catalog}
        object_layer_cells = set()
        visual_only_object_cells = set()
        for layer in visible_layers:
            layer_type = layer.get("type")
            for cell in layer.get("cells", []):
                key = cell.get("key")
                item = by_key.get(key)
                if item is None or item.get("kind") != "object":
                    continue
                signature = (
                    int(cell.get("x", -1)),
                    int(cell.get("y", -1)),
                    key,
                )
                if layer_type == "object":
                    object_layer_cells.add(signature)
        for layer in layers:
            if layer.get("type") != "decorative":
                continue
            for cell in layer.get("cells", []):
                key = cell.get("key")
                item = by_key.get(key)
                if item is None or item.get("kind") != "object":
                    continue
                signature = (
                    int(cell.get("x", -1)),
                    int(cell.get("y", -1)),
                    key,
                )
                if signature not in object_layer_cells:
                    visual_only_object_cells.add(signature)
        resolved = [
            cell for cell in cells
            if not (
                cell.get("layer") in (
                    "ground", "overlay", "elevation", "relief", "infra",
                )
                and (int(cell.get("x", -1)), int(cell.get("y", -1)))
                in editor_layer_positions
            )
            and not (
                cell.get("layer") == "object"
                and (
                    int(cell.get("x", -1)),
                    int(cell.get("y", -1)),
                    cell.get("key"),
                ) in visual_only_object_cells
            )
        ]
        for cell in cls._top_surface_cells(layers).values():
            key = cell.get("key")
            item = by_key.get(key)
            if item is None and str(key).startswith(map_editor.ATLAS_KEY_PREFIX):
                item = map_editor.atlas_item(key, cell.get("layer", "ground"))
            if item is None:
                continue
            terrain_cell = dict(cell)
            terrain_cell.setdefault(
                "layer",
                "object" if item.get("kind") == "object" else "ground",
            )
            resolved.append(terrain_cell)
        return resolved

    @staticmethod
    def _apply_atlas_collision(terrain, layers, map_w, map_h):
        """Apply the top visible atlas tile's walkability at each map position."""
        water_tiles = set()
        solid_tiles = set()
        bridge_tiles = set()
        top_cells = FrontLineWorldService._top_surface_cells(layers)
        for (x, y), cell in top_cells.items():
            if x >= map_w or y >= map_h:
                continue
            key = str(cell.get("key", ""))
            if not key.startswith("atlas|"):
                continue
            parts = key[len("atlas|"):].split("|")
            if len(parts) not in (3, 5, 6):
                continue
            try:
                sheet = parts[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
                if sheet == "water_coasts.png" and "grassland" in parts[0].lower():
                    tile_id = int(parts[2]) * 39 + int(parts[1])
                    category = GRASSLAND_WATER_COAST_CATEGORIES.get(tile_id)
                    if category == "water":
                        water_tiles.add((x, y))
                    elif category == "bridge":
                        bridge_tiles.add((x, y))
                    continue
                if "bridge" in sheet:
                    bridge_tiles.add((x, y))
                elif any(token in sheet for token in ("water", "coast", "waterfall", "lava")):
                    water_tiles.add((x, y))
                elif any(token in sheet for token in (
                    "object", "tree", "flower", "statue", "rock", "building", "house",
                    "castle", "tavern", "hut", "structure", "tower", "exterior",
                )):
                    solid_tiles.add((x, y))
            except (IndexError, ValueError):
                continue
        bridge_tiles -= solid_tiles
        for key in ("water", "impassable", "mountain", "forest", "dry"):
            terrain[key] = set(terrain[key])
        terrain["partial"] = dict(terrain.get("partial", {}))
        terrain["water"].difference_update(bridge_tiles)
        terrain["impassable"].difference_update(bridge_tiles)
        terrain["mountain"].difference_update(bridge_tiles)
        terrain["forest"].difference_update(bridge_tiles)
        terrain["dry"].difference_update(bridge_tiles)
        for tile in bridge_tiles:
            terrain.get("partial", {}).pop(tile, None)
        terrain["water"].update(water_tiles - bridge_tiles)
        terrain["impassable"].update(solid_tiles)
        if bridge_tiles:
            terrain["bridges"] = list(terrain.get("bridges", []))
            terrain["bridges"].append({"tiles": [list(tile) for tile in sorted(bridge_tiles)]})

    def _published_saved_map(self):
        """Заготовка, опубликованная в этот мир: её рельеф, здания и флаги слоёв.
        Без публикации (или если заготовка удалена) — первая заготовка режима, как раньше.
        """
        published = self._database.published_map()
        saved_id = published.get("saved_id") if published else None
        if saved_id:
            try:
                return self._database.get_saved_map(saved_id)
            except ValueError:
                pass
        return self._database.first_saved_map("front_line")

    def reload_terrain(self, terrain, published):
        """Подменяет рельеф и заодно здания опубликованной карты: здания в публикации не хранятся отдельно."""
        if terrain is not None:
            buildings = self._buildings_from_saved(self._published_saved_map())
            terrain["impassable"] = set(terrain.get("impassable", ())) | self._building_tiles(buildings)
            with self._lock:
                self._building_states = buildings
        super().reload_terrain(terrain, published)

    @staticmethod
    def _buildings_from_saved(saved):
        """Главные здания карты: состояние для тика (здоровье, регенерация, слоты обороны с перезарядкой)."""
        buildings = []
        for spawn in (saved or {}).get("spawns", []):
            if spawn.get("type") != "building":
                continue
            settings = spawn.get("settings", {})
            max_hp = int(settings.get("hp", 500))
            slots = []
            for slot in settings.get("defense_slots", []):
                slots.append({
                    "attack": str(slot.get("attack", "arrow")),
                    "damage_min": int(slot.get("damage_min", 1)),
                    "damage_max": int(slot.get("damage_max", 1)),
                    "radius_px": front_line_combat.range_units_to_px(float(slot.get("radius_units", 300.0))),
                    "interval_seconds": float(slot.get("interval_seconds", 2.0)),
                    "cooldown": 0.0,
                })
            buildings.append({
                "x": int(spawn["x"]),
                "y": int(spawn["y"]),
                "sprite": str(spawn.get("sprite", "castle_8")),
                "hp": float(max_hp),
                "max_hp": float(max_hp),
                "regen_per_minute": float(settings.get("hp_regen_per_minute", 0)),
                "slots": slots,
            })
        return buildings

    @staticmethod
    def _building_tiles(buildings):
        """Клетки footprint зданий: непроходимы для героев и мобов."""
        return {
            (building["x"] + dx, building["y"] + dy)
            for building in buildings
            for dx in range(BUILDING_FOOTPRINT_TILES)
            for dy in range(BUILDING_FOOTPRINT_TILES)
        }

    def _update_buildings(self, dt):
        """Регенерация здоровья и выстрелы слотов обороны по ближайшему живому мобу в радиусе."""
        for building in getattr(self, "_building_states", []):
            building["hp"] = min(
                building["max_hp"],
                building["hp"] + building["regen_per_minute"] * dt / 60.0,
            )
            center = (
                (building["x"] + BUILDING_FOOTPRINT_TILES / 2) * TILE,
                (building["y"] + BUILDING_FOOTPRINT_TILES / 2) * TILE,
            )
            for slot in building["slots"]:
                slot["cooldown"] = max(0.0, slot["cooldown"] - dt)
                if slot["cooldown"] > 0.0:
                    continue
                target = self._nearest_living_mob(center, slot["radius_px"])
                if target is None:
                    continue
                slot["cooldown"] = slot["interval_seconds"]
                damage = self._rng.randint(slot["damage_min"], slot["damage_max"])
                self._damage_mob(target, damage, None)
                if target.fighter.hp <= 0 and getattr(target, "state", "") != "dead":
                    self._defeat_mob(target, None)

    def _nearest_living_mob(self, center, radius_px):
        best, best_distance = None, radius_px
        for mob in getattr(self, "_mobs", {}).values():
            if not getattr(mob, "alive", True) or mob.fighter.hp <= 0:
                continue
            distance = math.hypot(mob.x - center[0], mob.y - center[1])
            if distance <= best_distance:
                best, best_distance = mob, distance
        return best

    def submit_character_draft(self, user_id, character_id, profession_type, allocation):
        if profession_type not in FRONT_LINE_PROFESSIONS:
            raise ValueError(f"Профессия должна быть одной из: {', '.join(FRONT_LINE_PROFESSIONS)}")
        if not isinstance(allocation, dict):
            raise ValueError("Настройки характеристик должны быть объектом")
        creation_stats(allocation)
        with self._lock:
            if not self._character_draft_active:
                raise ValueError("Выбор персонажа сейчас закрыт")
            if self._clock() >= self._character_draft_deadline:
                self._complete_character_draft()
                raise ValueError("Время выбора персонажа закончилось")
            player = self._players.get(int(character_id))
            if player is None or player.user_id != int(user_id):
                raise ValueError("Персонаж не находится в этом мире")
            self._character_draft_choices[int(character_id)] = {
                "profession_type": profession_type,
                "allocation": dict(allocation),
            }
            return self._character_draft_status(int(character_id))

    def _character_draft_status(self, character_id):
        now = self._clock()
        return {
            "active": self._character_draft_active,
            "seconds_remaining": max(0, math.ceil(self._character_draft_deadline - now))
            if self._character_draft_active else 0,
            "players_ready": len(self._character_draft_choices),
            "players_total": len(self._players) if self._character_draft_active else 0,
            "selected": int(character_id) in self._character_draft_choices,
        }

    def _find_auto_target(self, player):
        if not front_line_combat.AUTO_ATTACK_ENABLED:
            return None
        # Герой идёт по приказу: автоатака не начинается, пока он не стоит.
        if self._clock() - getattr(player, "last_move_time", float("-inf")) < front_line_combat.AUTO_ATTACK_IDLE_SECONDS:
            return None
        reach = self._player_attack_range_px(player)
        best = None
        best_distance = None
        for mob in self._mobs.values():
            if not mob.alive:
                continue
            distance = self._player_attack_distance(player, mob)
            if distance <= reach and (best_distance is None or distance < best_distance):
                best = mob
                best_distance = distance
        return best

    def _begin_swing_facing(self, player, mob, dt):
        # Герой поворачивается к цели с ограниченной скоростью; замах начинается, когда он смотрит на цель.
        desired = math.atan2(mob.y - player.y, mob.x - player.x)
        current = getattr(player, "turn_angle", player.facing)
        difference = (desired - current + math.pi) % (2 * math.pi) - math.pi
        step = front_line_combat.HERO_TURN_RATE * dt
        aligned = abs(difference) <= step
        current = desired if aligned else current + math.copysign(step, difference)
        player.turn_angle = current
        player.facing = _quantize_facing(current)
        return aligned

    def _player_move_speed(self, player):
        return super()._player_move_speed(player) * front_line_combat.HERO_MOVE_SPEED_SCALE

    def _strike_range_px(self, player):
        return super()._strike_range_px(player) + front_line_combat.ATTACK_RANGE_BUFFER_PX

    def _on_strike_out_of_range(self, player, target):
        # Как в Dota 2: цель ушла из дальности — удар не проходит, промаха и отката нет; герой догоняет.
        return

    def _player_windup_time(self, player):
        # Базовый замах по классу: лучник 0,7 с, маг 1,2 с; интуиция сокращает его, как и раньше.
        class_base = front_line_combat.FRONT_LINE_BASE_WINDUP.get(
            player.fighter.profession_type, world_stats.BASE_ATTACK_WINDUP,
        )
        offset = class_base - world_stats.BASE_ATTACK_WINDUP
        windup = super()._player_windup_time(player) + offset
        return max(front_line_combat.MIN_ATTACK_WINDUP, windup * front_line_combat.FRONT_LINE_WINDUP_SCALE)

    def _player_backswing_time(self, player):
        backswing = super()._player_backswing_time(player)
        return max(front_line_combat.MIN_ATTACK_BACKSWING, backswing * front_line_combat.FRONT_LINE_BACKSWING_SCALE)

    def _accept_move(self, player, x, y, elapsed):
        if self._character_draft_active:
            return False
        return super()._accept_move(player, x, y, elapsed)

    def _start_first_map(self):
        if self._character_draft_active or self._game_started:
            return
        saved = self._refresh_waiting_map()
        if saved is None:
            self._start_deadline = self._clock() + self._start_wait_seconds
            return
        self._match_result = ""
        self._character_draft_active = True
        self._character_draft_deadline = self._clock() + self._character_draft_seconds
        self._pending_spawns = saved["spawns"]
        self._hero_spawns = [
            (int(spawn["x"]) * TILE + TILE / 2, int(spawn["y"]) * TILE + TILE / 2)
            for spawn in self._pending_spawns
            if spawn.get("type", "hero") == "hero"
        ]
        self._mob_spawners = []
        self._item_drops.clear()
        self._start_deadline = self._character_draft_deadline

    def _configure_mob_spawners(self):
        for spawn in self._pending_spawns:
            if spawn.get("type") != "mob":
                continue
            settings = dict(spawn["settings"])
            raw_waves = settings.get("waves")
            if not isinstance(raw_waves, list):
                raw_waves = [settings]
            spawner = {
                "x": int(spawn["x"]),
                "y": int(spawn["y"]),
                "waves": [],
            }
            for wave_index, wave_settings in enumerate(raw_waves, 1):
                settings = dict(wave_settings)
                boss = settings.get("boss", {})
                start_at = self._map_started_at + max(
                    0, int(settings.get("start_after_seconds", 0)),
                )
                count = max(1, int(settings["count"]))
                squad_min = max(1, int(settings.get("squad_min", 1)))
                squad_max = max(squad_min, int(settings.get("squad_max", squad_min)))
                wave_state = {
                    "index": wave_index,
                    "settings": settings,
                    "remaining": count,
                    "spawned": 0,
                    "boss_pending": bool(boss.get("enabled", False)),
                    "boss_spawn_at": None,
                    "starts_at": start_at,
                    "next_spawn_at": start_at,
                    "squad_min": squad_min,
                    "squad_max": squad_max,
                    "planned_ticks": planned_squad_ticks(count, squad_min, squad_max),
                    "tick": 0,
                    "squad_pending": 0,
                }
                spawner["waves"].append(wave_state)
            self._mob_spawners.append(spawner)
        self._pending_spawns = []

    def _grant_mob_xp(self, user_id, character_id, amount):
        """Опыт за моба живёт только в текущей сессии мира и в базу не пишется.

        Новый запуск Front Line (после победы или поражения) начинает героя с первого уровня и 0 опыта.
        """
        player = self._online_player(user_id, character_id)
        if player is None:
            return 0, 0
        fighter = player.fighter
        self._round_entry(character_id)["xp"] += amount
        levels_gained = apply_xp(fighter, amount)
        _apply_world_resource_formulas(fighter)
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

    def _complete_character_draft(self):
        # Новый раунд начинается со свежих счётчиков: итоги прошлой игры уже показаны.
        self._round_stats = {}
        self._round_mobs_killed = 0
        self._match_summary = None
        if not self._players:
            self._character_draft_active = False
            self._character_draft_deadline = 0.0
            self._character_draft_choices.clear()
            self._start_deadline = self._clock() + self._start_wait_seconds
            return
        for index, (character_id, player) in enumerate(list(self._players.items())):
            choice = self._character_draft_choices.get(character_id)
            if choice is None:
                choice = {
                    "profession_type": self._rng.choice(FRONT_LINE_PROFESSIONS),
                    "allocation": dict(DEFAULT_DRAFT_ALLOCATION),
                }
            character = self._database.get_character(player.user_id, character_id)
            if character is None:
                raise ValueError("Персонаж не найден")
            self._reset_character_progress(player.user_id, character_id)
            self._begin_session_wallet(player.user_id, character_id)
            self._round_entry(character_id, character.get("name", ""))
            stats, free_points = creation_stats(choice["allocation"])
            # Прогресс сессии: каждый запуск мира начинается с первого уровня и 0 опыта.
            level = FRONT_LINE_START_LEVEL
            stats["endurance"] = max(stats["endurance"], minimum_endurance(level))
            max_hp = calculate_max_hp(level, stats["endurance"])
            max_mp = calculate_max_mana(stats["intellect"])
            character = dict(character)
            character.update({
                "type": choice["profession_type"],
                "level": level,
                "xp": 0,
                "stats": stats,
                "stat_points": free_points,
                "hp": max_hp,
                "max_hp": max_hp,
                "mp": max_mp,
                "max_mp": max_mp,
            })
            player.fighter = _fighter_from_character(character)
            player.dirty = False
            self._refresh_carry(player)
            self._character_draft_results[character_id] = character
            target = (
                self._hero_spawns[index % len(self._hero_spawns)]
                if self._hero_spawns else tuple(world_map.MAP_SPAWN_PX)
            )
            player.x, player.y = self._nearest_free(*target)
            player.move_path = []
            player.attack_target = None
            player.harvest_target = None
        self._character_draft_active = False
        self._character_draft_choices.clear()
        self._game_started = True
        self._map_started_at = self._clock()
        self._game_started_at = self._clock()
        self._wave_draft_deadline = self._game_started_at + self._wave_draft_seconds
        self._round_countdown_zero_until = 0.0
        self._configure_mob_spawners()
        world_map.TERRAIN_VERSION += 1
        self._objective_flow()

    @timed("волны и спавн")
    def _advance_spawners(self, dt):
        now = self._clock()
        for spawner in self._mob_spawners:
            for wave in spawner["waves"]:
                if wave["remaining"] <= 0 and not wave["boss_pending"]:
                    continue
                scheduled_start = max(wave["starts_at"], self._waves_unlocked_at)
                if now < scheduled_start:
                    continue
                wave["next_spawn_at"] = max(wave["next_spawn_at"], scheduled_start)
                if wave["remaining"] > 0:
                    if now < wave["next_spawn_at"]:
                        continue
                    if wave["squad_pending"] <= 0:
                        wave["squad_pending"] = squad_size(
                            wave["tick"], wave["planned_ticks"],
                            wave["squad_min"], wave["squad_max"], wave["remaining"],
                        )
                    room = MAX_ACTIVE_MOBS - len(self._mobs)
                    if room <= 0:
                        continue
                    batch = min(wave["squad_pending"], room)
                    for _ in range(batch):
                        self._spawn_mob(
                            spawner,
                            wave["settings"],
                            wave_index=wave["index"],
                        )
                    wave["remaining"] -= batch
                    wave["spawned"] += batch
                    wave["squad_pending"] -= batch
                    if wave["squad_pending"] == 0:
                        wave["tick"] += 1
                        wave["next_spawn_at"] = now + max(
                            1, int(wave["settings"]["interval_seconds"]),
                        )
                    if wave["remaining"] == 0 and wave["boss_pending"]:
                        wave["boss_spawn_at"] = now + BOSS_WAVE_DELAY_SECONDS
                    continue
                if (
                    wave["boss_pending"]
                    and wave["boss_spawn_at"] is not None
                    and now >= wave["boss_spawn_at"]
                    and len(self._mobs) < MAX_ACTIVE_MOBS
                ):
                    self._spawn_mob(
                        spawner,
                        wave["settings"],
                        boss_settings=wave["settings"]["boss"],
                        wave_index=wave["index"],
                    )
                    wave["boss_pending"] = False

    def _wave_progress(self, now):
        waves_by_index = {}
        for spawner in self._mob_spawners:
            for wave in spawner["waves"]:
                index = int(wave["index"])
                progress = waves_by_index.setdefault(index, {
                    "total": 0,
                    "spawned": 0,
                    "remaining": 0,
                    "boss_pending": False,
                    "boss_spawn_at": None,
                    "starts_at": float("inf"),
                })
                boss_enabled = bool(wave["settings"].get("boss", {}).get("enabled", False))
                progress["total"] += int(wave["settings"]["count"]) + int(boss_enabled)
                progress["spawned"] += int(wave["spawned"])
                progress["remaining"] += int(wave["remaining"])
                progress["boss_pending"] = progress["boss_pending"] or wave["boss_pending"]
                if wave["boss_spawn_at"] is not None:
                    current_deadline = progress["boss_spawn_at"]
                    progress["boss_spawn_at"] = (
                        wave["boss_spawn_at"] if current_deadline is None
                        else min(current_deadline, wave["boss_spawn_at"])
                    )
                progress["starts_at"] = min(progress["starts_at"], wave["starts_at"])
        if not waves_by_index:
            return {}
        for index, progress in waves_by_index.items():
            progress["alive"] = sum(
                1
                for mob in self._mobs.values()
                if mob.alive and int(getattr(mob, "front_line_wave_index", 0)) == index
            )
        current_index = next(
            (
                index
                for index in sorted(waves_by_index, reverse=True)
                if (
                    now >= max(waves_by_index[index]["starts_at"], self._waves_unlocked_at)
                    and (
                        waves_by_index[index]["remaining"] > 0
                        or waves_by_index[index]["boss_pending"]
                        or waves_by_index[index]["alive"] > 0
                    )
                )
            ),
            None,
        )
        if current_index is None:
            return {}
        progress = waves_by_index[current_index]
        boss_deadline = progress["boss_spawn_at"]
        return {
            "number": current_index,
            "mobs_alive": progress["alive"],
            "mobs_total": progress["total"],
            "mobs_spawned": progress["spawned"],
            "boss_pending": progress["boss_pending"],
            "boss_in_seconds": max(0, math.ceil(boss_deadline - now))
            if boss_deadline is not None and progress["boss_pending"] else 0,
        }

    # Место появления моба: ближайшая точка у точки спауна, где тело моба не задевает другого моба,
    # героя и рельеф. Отряд выстраивается кольцами: сначала один ряд, потом следующий.
    SPAWN_SPOT_STEP_PX = 32
    SPAWN_SPOT_RINGS = 12

    def _free_mob_spot(self, x, y):
        if self._mob_spot_free(x, y):
            return float(x), float(y)
        step = self.SPAWN_SPOT_STEP_PX
        for ring in range(1, self.SPAWN_SPOT_RINGS + 1):
            offsets = sorted(
                ((dx * step, dy * step) for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)
                 if max(abs(dx), abs(dy)) == ring),
                key=lambda offset: math.hypot(*offset),
            )
            for dx, dy in offsets:
                if self._mob_spot_free(x + dx, y + dy):
                    return float(x + dx), float(y + dy)
        return float(x), float(y)

    def _mob_spot_free(self, x, y):
        if self._terrain_blocked(x, y) or self._mob_blocked_by_players(x, y):
            return False
        body = self._mob_body_rect(None, x, y)
        return not any(
            mob.alive and _rects_collide(body, self._mob_body_rect(mob, mob.x, mob.y))
            for mob in self._mobs.values()
        )

    def _spawn_mob(self, spawner, settings, boss_settings=None, wave_index=0):
        requested_kind = str(settings["mob_key"])
        if requested_kind not in MOB_PROFILES:
            raise ValueError(f"Моб «{requested_kind}» отсутствует в боевом каталоге")
        kind = requested_kind
        profile = MOB_PROFILES[kind]
        level = int(settings["level"])
        cfg = self._mob_profile(kind)
        fighter = Fighter(profile["name"], level=level)
        fighter.stats.update(cfg["stats"])
        fighter.recalculate_parameters()
        _apply_world_resource_formulas(fighter)
        fighter.max_hp = int(cfg["max_hp"])
        fighter.max_mp = int(cfg["max_mp"])
        fighter.hp = fighter.max_hp
        fighter.mp = fighter.max_mp
        fighter.innate_damage_range = (int(cfg.get("damage_min", 0)), int(cfg.get("damage_max", 0)))
        home = (
            int(spawner["x"]) * TILE + TILE / 2,
            int(spawner["y"]) * TILE + TILE / 2,
        )
        home = self._free_mob_spot(*home)
        mob_id = f"front_line_{self._spawn_sequence}"
        self._spawn_sequence += 1
        mob = _Mob(mob_id, kind, home, fighter, {})
        mob.apply_config(cfg)
        mob.attack_range_units = int(cfg.get("attack_range", front_line_combat.MOB_ATTACK_RANGE_UNITS))
        mob.attack_style = str(cfg.get("attack_style", "warrior"))
        mob.area_radius_units = int(cfg.get("area_radius", front_line_combat.MAGE_AREA_RADIUS_UNITS))
        mob.id = mob_id
        mob.kind = kind
        mob.name = profile["name"]
        mob.log_names = {"nom": mob.name, "dat": mob.name, "gen": mob.name}
        mob.coins_copper = mob.reward_copper
        mob.attitude = "neutral"
        mob.target = None
        mob.front_line_target = str(settings.get("target", "objective"))
        mob.front_line_wave_index = int(wave_index)
        mob.front_line_spawn_point = (int(spawner["x"]), int(spawner["y"]))
        mob.is_boss = boss_settings is not None
        if boss_settings is not None:
            fighter.max_hp = int(boss_settings["max_hp"])
            fighter.hp = fighter.max_hp
            fighter.max_mp = int(boss_settings["max_mp"])
            fighter.mp = fighter.max_mp
            mob.reward_xp = int(boss_settings["reward_xp"])
            mob.boss_drop_slots = list(boss_settings.get("drop_slots", []))
        self._mobs[mob_id] = mob

    @timed("мобы: движение и расталкивание")
    def _update_mobs(self, dt):
        self._mob_grid = self._mob_buckets()
        self._move_mobs(dt)
        self._update_buildings(dt)

    def _move_mobs(self, dt):
        self._ring_epoch = getattr(self, "_ring_epoch", 0) + 1
        if not self._game_started or not self._waves_unlocked:
            return
        for mob_id, mob in list(self._mobs.items()):
            if not mob.alive:
                mob.respawn_timer = max(0.0, mob.respawn_timer - dt)
                if mob.respawn_timer <= 0:
                    self._mobs.pop(mob_id, None)
                continue
            if self._building_states and not self._any_building_alive():
                mob.state = "idle"
                mob.target = None
                continue
            target_mode = getattr(mob, "front_line_target", "objective")
            _target_building, objective_distance = self._nearest_alive_building(mob.x, mob.y)
            player_target = self._nearest_front_line_player(mob)
            if player_target is not None and (
                target_mode == "characters"
                or (
                    target_mode == "both"
                    and math.hypot(player_target.x - mob.x, player_target.y - mob.y) < objective_distance
                )
            ):
                mob.state = "chase"
                mob.target = player_target
                self._update_mob_chase(mob, dt)
                continue
            mob.target = None
            if mob.state == "chase":
                mob.state = "idle"
                mob.chase_route = []
                mob.windup = 0.0
            if target_mode != "characters":
                flow = self._objective_flow()
                cell = (math.floor(mob.x / TILE), math.floor(mob.y / TILE))
                flow_distance = flow["distance"].get(cell)
                attacking = mob.state == "attack"
                if flow_distance is None:
                    in_range = objective_distance <= (
                        OBJECTIVE_ATTACK_KEEP_RANGE if attacking else OBJECTIVE_ATTACK_RANGE
                    )
                else:
                    in_range = flow_distance <= (OBJECTIVE_ATTACK_KEEP_CELLS if attacking else 0.0)
                if in_range:
                    self._attack_objective(mob, dt, self._objective_attack_facing(flow, cell))
                else:
                    if attacking:
                        mob.state = "idle"
                        mob.windup = 0.0
                    self._move_mob_to_objective(mob, dt, flow, cell)
        self._separate_mobs(dt)

    # Сетка мобов на тик: кандидаты для проверки тел. Клетка не меньше самой широкой пары тел.
    def _mob_buckets(self):
        buckets = {}
        for mob in self._mobs.values():
            if mob.alive:
                buckets.setdefault((math.floor(mob.x / MOB_BUCKET_PX), math.floor(mob.y / MOB_BUCKET_PX)), []).append(mob)
        return buckets

    def _mob_blocked_by_mobs(self, x, y, mob):
        buckets = getattr(self, "_mob_grid", None)
        if buckets is None:
            candidates = list(getattr(self, "_mobs", {}).values())
        else:
            bucket_x, bucket_y = math.floor(x / MOB_BUCKET_PX), math.floor(y / MOB_BUCKET_PX)
            candidates = [
                other
                for offset_x in (-1, 0, 1)
                for offset_y in (-1, 0, 1)
                for other in buckets.get((bucket_x + offset_x, bucket_y + offset_y), ())
            ]
        radius = self._mob_separation_radius(mob)
        for other in candidates:
            if other is mob or not other.alive:
                continue
            distance = math.hypot(x - other.x, y - other.y)
            if distance < radius + self._mob_separation_radius(other) and distance < math.hypot(
                mob.x - other.x, mob.y - other.y,
            ):
                return True
        return False

    @timed("поле погони (пересчёт)")
    def _chase_flow(self, player):
        """Поле расстояний по проходимым клеткам от клетки героя (BFS по 4 соседям), кэш на клетку и версию рельефа.

        Моб идёт по убывающему расстоянию, поэтому обходит любую преграду, даже если путь сначала уводит от героя.
        """
        hero_cell = (math.floor(player.x / TILE), math.floor(player.y / TILE))
        width = int(getattr(self, "_map_width", 64))
        height = int(getattr(self, "_map_height", 64))
        epoch = getattr(self, "_ring_epoch", 0)
        key = (epoch // ATTACK_FIELD_REFRESH_TICKS, world_map.TERRAIN_VERSION, width, height, hero_cell)
        cached = getattr(self, "_chase_flow_cache", None)
        if cached is not None and cached["key"] == key:
            return cached
        walkable = self._walkable_cells()
        # Стоимость клеток: 1 за шаг, плюс штраф за клетку, занятую другим мобом. Мобы в очереди видят обход,
        # если он короче очереди, и не все идут по одному кратчайшему пути.
        occupied = {
            (math.floor(mob.x / TILE), math.floor(mob.y / TILE))
            for mob in self._mobs.values() if mob.alive
        }
        distance = {hero_cell: 0}
        heap = [(0, hero_cell)]
        while heap:
            cost, cell = heapq.heappop(heap)
            if cost > distance.get(cell, math.inf):
                continue
            for dx, dy in CHASE_STEPS:
                nxt = (cell[0] + dx, cell[1] + dy)
                if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                    continue
                if nxt not in walkable:
                    continue
                new_cost = cost + 1 + (CHASE_OCCUPIED_COST if nxt in occupied else 0)
                if new_cost < distance.get(nxt, math.inf):
                    distance[nxt] = new_cost
                    heapq.heappush(heap, (new_cost, nxt))
        self._chase_flow_cache = {"key": key, "distance": distance}
        return self._chase_flow_cache

    def _plan_chase_route(self, mob, player):
        """Путь в обход рельефа до клетки рядом с героем по полю расстояний. Пусто, если пути нет."""
        distance = self._chase_flow(player)["distance"]
        cell = (math.floor(mob.x / TILE), math.floor(mob.y / TILE))
        path = []
        if cell not in distance:
            # Моб стоит на клетке, центр которой занят преградой (например, прижат к краю стены):
            # выходим через ближайшую проходимую соседнюю клетку.
            neighbours = [
                (cell[0] + dx, cell[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)
            ]
            reachable = [item for item in neighbours if item in distance]
            if not reachable:
                return []
            cell = min(reachable, key=lambda item: math.hypot((item[0] + 0.5) * TILE - mob.x, (item[1] + 0.5) * TILE - mob.y))
            path.append(((cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE))
        # Спуск по убывающей стоимости до клетки рядом с героем (нулевая клетка — сам герой).
        while True:
            best = None
            for dx, dy in CHASE_STEPS:
                nxt = (cell[0] + dx, cell[1] + dy)
                value = distance.get(nxt)
                if value is not None and (best is None or value < best[0]):
                    best = (value, nxt)
            if best is None or best[0] >= distance[cell] or best[0] == 0:
                break
            cell = best[1]
            path.append(((cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE))
        if not path and distance.get(cell, 0) > 1:
            return []
        return path

    def _walkable_cells(self):
        """Проходимые клетки карты. Считаются один раз на версию рельефа и набор построек.

        Поле погони и поле таверны берут этот набор, а не проверяют рельеф на каждой клетке:
        проверка рельефа дорогая, а поле погони пересчитывается каждые несколько тиков.
        """
        key = (world_map.TERRAIN_VERSION, self._map_width, self._map_height)
        cached = getattr(self, "_walkable_cache", None)
        if cached is not None and cached[0] == key and cached[1] is self._solid_rects:
            return cached[2]
        walkable = frozenset(
            (cell_x, cell_y)
            for cell_y in range(max(1, int(self._map_height)))
            for cell_x in range(max(1, int(self._map_width)))
            if not self._terrain_blocked((cell_x + 0.5) * TILE, (cell_y + 0.5) * TILE)
        )
        self._walkable_cache = (key, self._solid_rects, walkable)
        return walkable

    @timed("поле таверны (пересчёт)")
    def _objective_flow(self):
        """Поле потока к стенам таверны, общее для всех мобов карты.

        Направление берётся из клетки, где моб стоит сейчас, поэтому толчки
        толпы не сбивают маршрут, а мобы не уходят в тупики у цели.
        """
        key = (
            world_map.TERRAIN_VERSION, self._map_width, self._map_height,
            tuple((b["x"], b["y"], b["hp"] > 0) for b in self._building_states),
        )
        cached = self._objective_flow_cache
        if cached is not None and cached["key"] == key:
            return cached
        walkable = self._walkable_cells()
        walls = self._objective_wall_cells(walkable)
        facing = {}
        for wall_x, wall_y in sorted(walls):
            for offset_x, offset_y, _cost in FLOW_NEIGHBOURS:
                cell = (wall_x - offset_x, wall_y - offset_y)
                if cell in walkable and (cell not in facing or abs(offset_x) + abs(offset_y) == 1):
                    facing[cell] = math.atan2(offset_y, offset_x)
        for building in self._alive_buildings():
            point = self._objective_point(building)
            objective_cell = (math.floor(point.x / TILE), math.floor(point.y / TILE))
            if objective_cell in walkable:
                facing.setdefault(objective_cell, None)
        links = {}

        def linked(first, second):
            pair = (first, second) if first <= second else (second, first)
            if pair not in links:
                links[pair] = self._terrain_segment_clear(
                    (first[0] + 0.5) * TILE, (first[1] + 0.5) * TILE,
                    (second[0] + 0.5) * TILE, (second[1] + 0.5) * TILE,
                )
            return links[pair]

        distance = {cell: 0.0 for cell in facing}
        parent = {}
        queue = [(0.0, cell) for cell in facing]
        heapq.heapify(queue)
        while queue:
            current_distance, cell = heapq.heappop(queue)
            if current_distance > distance[cell]:
                continue
            for offset_x, offset_y, cost in FLOW_NEIGHBOURS:
                neighbour = (cell[0] + offset_x, cell[1] + offset_y)
                if neighbour not in walkable:
                    continue
                next_distance = current_distance + cost
                if next_distance >= distance.get(neighbour, math.inf):
                    continue
                if offset_x and offset_y:
                    sides = ((cell[0] + offset_x, cell[1]), (cell[0], cell[1] + offset_y))
                    if not all(
                        side in walkable and linked(cell, side) and linked(side, neighbour)
                        for side in sides
                    ):
                        continue
                elif not linked(cell, neighbour):
                    continue
                distance[neighbour] = next_distance
                parent[neighbour] = cell
                heapq.heappush(queue, (next_distance, neighbour))
        self._objective_flow_cache = {
            "key": key,
            "distance": distance,
            "parent": parent,
            "facing": facing,
            "lookahead": {},
        }
        return self._objective_flow_cache

    def _objective_wall_cells(self, walkable):
        """Непроходимые клетки зданий-целей: крупнейшая связная группа в footprint каждого живого здания."""
        walls = set()
        for building in self._alive_buildings():
            remaining = {
                (cell_x, cell_y)
                for cell_y in range(building["y"], building["y"] + BUILDING_FOOTPRINT_TILES)
                for cell_x in range(building["x"], building["x"] + BUILDING_FOOTPRINT_TILES)
                if 0 <= cell_x < self._map_width and 0 <= cell_y < self._map_height
                and (cell_x, cell_y) not in walkable
            }
            largest = set()
            while remaining:
                component = {remaining.pop()}
                frontier = list(component)
                while frontier:
                    cx, cy = frontier.pop()
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if (nx, ny) in remaining:
                            remaining.discard((nx, ny))
                            component.add((nx, ny))
                            frontier.append((nx, ny))
                if len(component) > len(largest):
                    largest = component
            walls |= largest
        return walls

    def _alive_buildings(self):
        return [building for building in self._building_states if building["hp"] > 0]

    def _any_building_alive(self):
        return bool(self._alive_buildings())

    @staticmethod
    def _building_rect_px(building):
        size = BUILDING_FOOTPRINT_TILES * TILE
        return (building["x"] * TILE, building["y"] * TILE, size, size)

    def _nearest_alive_building(self, x, y):
        """Ближайшее живое здание к точке и расстояние до его footprint (0 — внутри)."""
        best, best_distance = None, math.inf
        for building in self._alive_buildings():
            distance = _distance_to_rect(x, y, self._building_rect_px(building))
            if distance < best_distance:
                best, best_distance = building, distance
        return best, best_distance

    @staticmethod
    def _objective_point(building):
        """Точка подхода мобов к зданию: слева от его стены, по центру высоты."""
        return SimpleNamespace(
            x=building["x"] * TILE - TILE,
            y=(building["y"] + BUILDING_FOOTPRINT_TILES / 2) * TILE,
        )

    @staticmethod
    def _objective_attack_facing(flow, cell):
        for _ in range(3):
            if cell is None:
                return None
            if cell in flow["facing"]:
                return flow["facing"][cell]
            cell = flow["parent"].get(cell)
        return None

    def _flow_lookahead(self, flow, cell):
        """Самая дальняя клетка по потоку, к которой из центра клетки ведёт прямой путь."""
        cached = flow["lookahead"].get(cell)
        if cached is not None:
            return cached
        chain = []
        step = flow["parent"].get(cell)
        while step is not None and len(chain) < OBJECTIVE_FLOW_LOOKAHEAD_CELLS:
            chain.append(step)
            step = flow["parent"].get(step)
        target = cell
        for candidate in reversed(chain):
            if candidate == chain[0] or self._terrain_segment_clear(
                (cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE,
                (candidate[0] + 0.5) * TILE, (candidate[1] + 0.5) * TILE,
            ):
                target = candidate
                break
        flow["lookahead"][cell] = target
        return target

    def _move_mob_to_objective(self, mob, dt, flow, cell):
        building, _distance = self._nearest_alive_building(mob.x, mob.y)
        if building is None:
            return
        if cell not in flow["distance"]:
            self._move_mob_toward(mob, self._objective_point(building), dt)
            return
        step = mob.move_speed * dt
        for target in (self._flow_lookahead(flow, cell), flow["parent"].get(cell), cell):
            if target is None:
                continue
            gap_x = (target[0] + 0.5) * TILE - mob.x
            gap_y = (target[1] + 0.5) * TILE - mob.y
            gap = math.hypot(gap_x, gap_y)
            if gap < 1e-6:
                continue
            travel = min(step, gap)
            next_x = mob.x + gap_x / gap * travel
            next_y = mob.y + gap_y / gap * travel
            if not self._terrain_segment_clear(mob.x, mob.y, next_x, next_y):
                continue
            if self._step_mob_around_players(mob, math.atan2(gap_y, gap_x), travel):
                return

    def _sidestep_blocked_mob(self, mob, heading, distance):
        """Погоня: герой загородил точку маршрута — моб обходит его тем же способом, что и путь к таверне."""
        return self._step_mob_around_players(mob, heading, distance)

    def _step_mob_around_players(self, mob, heading, distance):
        """Шаг к цели; если путь загородил герой, моб обходит его сбоку.

        Сторона обхода запоминается, пока прямой путь закрыт, чтобы моб не метался
        у героя то влево, то вправо. Если обход не удаётся дольше MOB_STUCK_SECONDS,
        моб пробует углы шире.
        """
        if self._try_mob_step(mob, heading, distance):
            mob.front_line_detour_side = 0
            mob.front_line_stuck_time = 0.0
            return True
        stuck = getattr(mob, "front_line_stuck_time", 0.0) >= MOB_STUCK_SECONDS
        angles = MOB_STUCK_DETOUR_ANGLES if stuck else MOB_DETOUR_ANGLES
        side = getattr(mob, "front_line_detour_side", 0) or self._detour_side(mob, heading)
        for detour_side in (side, -side):
            for angle in angles:
                if self._try_mob_step(mob, heading + detour_side * angle, distance):
                    mob.front_line_detour_side = detour_side
                    mob.front_line_stuck_time = 0.0
                    return True
        mob.front_line_stuck_time = getattr(mob, "front_line_stuck_time", 0.0) + distance / mob.move_speed
        mob.facing = heading
        return False

    def _try_mob_step(self, mob, heading, distance):
        next_x = mob.x + math.cos(heading) * distance
        next_y = mob.y + math.sin(heading) * distance
        if not self._terrain_segment_clear(mob.x, mob.y, next_x, next_y):
            return False
        if self._mob_blocked_by_players(next_x, next_y, mob):
            return False
        mob.facing = heading
        mob.x, mob.y = next_x, next_y
        return True

    def _detour_side(self, mob, heading):
        """Сторона поворота от ближайшего героя: +1 — по часовой стрелке на экране, −1 — против."""
        player = min(
            self._players.values(),
            key=lambda item: math.hypot(item.x - mob.x, item.y - mob.y),
            default=None,
        )
        if player is None:
            return 1
        cross = math.cos(heading) * (player.y - mob.y) - math.sin(heading) * (player.x - mob.x)
        return -1 if cross > 0 else 1

    @classmethod
    def _mob_body_rect(cls, mob, x, y):
        """Тело моба для столкновений с героем: квадрат со стороной в два радиуса расталкивания."""
        # Тело моба для блокировки героя — размер ног героя (FEET_W × FEET_H), а не круг расталкивания:
        # иначе моб на мосту в два тайла полностью перекрывает проход.
        # Низ тела моба — на 7 px ниже точки (x, y): там начинаются ноги спрайта.
        return (int(x - FEET_W / 2), int(y + MOB_BODY_OFFSET_Y - FEET_H), FEET_W, FEET_H)

    def _player_blocked(self, x, y, start=None):
        """Герой не проходит сквозь рельеф и компактные тела живых мобов.

        start — точка, откуда идёт герой. Если он уже касается моба, выйти от него можно: блокируется только
        новое касание или движение к центру моба. Иначе герой застревал бы в касании и не мог уйти.
        """
        if self._terrain_blocked(x, y):
            return True
        feet = _feet_rect(x, y)
        start_feet = _feet_rect(*start) if start is not None else None
        for mob in self._mobs.values():
            if not mob.alive:
                continue
            body = self._mob_body_rect(mob, mob.x, mob.y)
            if not _rects_collide(feet, body):
                continue
            if start_feet is None or not _rects_collide(start_feet, body):
                return True
            if math.hypot(x - mob.x, y - mob.y) < math.hypot(start[0] - mob.x, start[1] - mob.y):
                return True
        return False

    def _mob_blocked_by_players(self, x, y, mob=None):
        """Тело моба в (x, y) задевает героя.

        Моб, который уже касается героя, может отойти от него, но не придвинуться ближе.
        """
        body = self._mob_body_rect(mob, x, y)
        current = None if mob is None else self._mob_body_rect(mob, mob.x, mob.y)
        for player in self._players.values():
            # Преследующий моб не упирается в тело своей цели: иначе он не доходит до радиуса атаки и замирает.
            if mob is not None and mob.state == "chase" and getattr(mob, "target", None) is player:
                continue
            feet = _feet_rect(player.x, player.y)
            if not _rects_collide(body, feet):
                continue
            if current is None or not _rects_collide(current, feet):
                return True
            if math.hypot(x - player.x, y - player.y) < math.hypot(mob.x - player.x, mob.y - player.y):
                return True
        # Моб не шагает в тело другого моба: вплотную и ближе, чем сейчас. Отойти и разойтись можно.
        return mob is not None and self._mob_blocked_by_mobs(x, y, mob)

    def _attack_objective(self, mob, dt, facing=None):
        """Удар по ближайшему живому зданию идёт как удар по герою: замах, урон, откат."""
        mob.state = "attack"
        building, _distance = self._nearest_alive_building(mob.x, mob.y)
        if building is None:
            return
        if facing is None:
            target_x = building["x"] * TILE + BUILDING_FOOTPRINT_TILES * TILE / 2
            target_y = building["y"] * TILE + BUILDING_FOOTPRINT_TILES * TILE / 2
            if math.hypot(target_x - mob.x, target_y - mob.y) > 0:
                facing = math.atan2(target_y - mob.y, target_x - mob.x)
        if facing is not None:
            mob.facing = facing
        if mob.backswing > 0.0:
            mob.backswing = max(0.0, mob.backswing - dt)
            if mob.backswing > 0.0:
                return
        if mob.windup <= 0.0:
            mob.windup = mob.windup_time
            mob.windup_total = mob.windup
            mob.swing_id = getattr(mob, "swing_id", 0) + 1
        mob.windup = max(0.0, mob.windup - dt)
        if mob.windup > 0.0:
            return
        damage = max(1, int(world_stats.get_world_base_damage(mob.fighter, self._rng)))
        building["hp"] = max(0.0, building["hp"] - damage)
        if not self._any_building_alive():
            self._finish_match("lost")
        mob.backswing = mob.backswing_time

    @staticmethod
    def _mob_separation_radius(mob):
        scale = BOSS_SEPARATION_SCALE if bool(getattr(mob, "is_boss", False)) else 1.0
        return MOB_SEPARATION_RADIUS * scale

    @timed("расталкивание мобов")
    def _separate_mobs(self, dt):
        """Мягко расталкивает живых мобов, чтобы толпа не сливалась в одну точку.

        Толчок за тик не длиннее шага моба и не заходит в рельеф или под героя,
        поэтому на узких переправах мобы не застревают друг в друге навсегда.
        """
        mobs = [mob for mob in self._mobs.values() if mob.alive]
        if len(mobs) < 2:
            return
        radii = [self._mob_separation_radius(mob) for mob in mobs]
        cell_size = 2.0 * max(radii)
        buckets = {}
        for index, mob in enumerate(mobs):
            key = (math.floor(mob.x / cell_size), math.floor(mob.y / cell_size))
            buckets.setdefault(key, []).append(index)
        pushes = [[0.0, 0.0] for _ in mobs]
        for (bucket_x, bucket_y), members in buckets.items():
            for offset_x in (-1, 0, 1):
                for offset_y in (-1, 0, 1):
                    neighbours = buckets.get((bucket_x + offset_x, bucket_y + offset_y))
                    if not neighbours:
                        continue
                    for first in members:
                        for second in neighbours:
                            if second <= first:
                                continue
                            self._add_separation_push(
                                mobs, radii, pushes, first, second,
                            )
        for mob, (push_x, push_y) in zip(mobs, pushes):
            length = math.hypot(push_x, push_y)
            if length <= 0.01:
                continue
            limit = max(1.0, mob.move_speed * dt)
            if length > limit:
                push_x, push_y = push_x / length * limit, push_y / length * limit
            self._push_mob(mob, push_x, push_y)

    @staticmethod
    def _add_separation_push(mobs, radii, pushes, first, second):
        a, b = mobs[first], mobs[second]
        gap_x, gap_y = b.x - a.x, b.y - a.y
        distance = math.hypot(gap_x, gap_y)
        min_distance = radii[first] + radii[second]
        if distance >= min_distance:
            return
        if distance < 1e-6:
            # Мобы в одной точке: направление зависит от пары, чтобы стопка раскрывалась веером.
            angle = (first + second) * MOB_SEPARATION_GOLDEN_ANGLE
            unit_x, unit_y = math.cos(angle), math.sin(angle)
        else:
            unit_x, unit_y = gap_x / distance, gap_y / distance
        overlap = min_distance - distance
        first_share = radii[second] / min_distance
        second_share = radii[first] / min_distance
        pushes[first][0] -= unit_x * overlap * first_share
        pushes[first][1] -= unit_y * overlap * first_share
        pushes[second][0] += unit_x * overlap * second_share
        pushes[second][1] += unit_y * overlap * second_share

    def _push_mob(self, mob, push_x, push_y):
        for step_x, step_y in ((push_x, push_y), (push_x, 0.0), (0.0, push_y)):
            if abs(step_x) < 1e-6 and abs(step_y) < 1e-6:
                continue
            next_x, next_y = mob.x + step_x, mob.y + step_y
            if not self._terrain_segment_clear(mob.x, mob.y, next_x, next_y):
                continue
            if self._mob_blocked_by_players(next_x, next_y, mob):
                continue
            mob.x, mob.y = next_x, next_y
            return

    def _begin_session_wallet(self, user_id, character_id):
        """Монеты в начале игры стартовые, как при создании персонажа: монеты прошлых игр не учитываются."""
        self._session_wallets[character_id] = user_id
        self._set_session_wallet(user_id, character_id)

    def _reset_session_wallets(self):
        """Конец игры: кошельки участников возвращаются к стартовым, как и герой."""
        for character_id, user_id in self._session_wallets.items():
            self._set_session_wallet(user_id, character_id)
        self._session_wallets = {}

    def _set_session_wallet(self, user_id, character_id):
        wallet = FRONT_LINE_START_WALLET
        self._database.set_world_currency(user_id, character_id, wallet["copper"], wallet["silver"], wallet["gold"])
        player = self._players.get(character_id)
        if player is not None and player.user_id == user_id:
            self._emit(player, {
                "type": "currency",
                "currency": dict(wallet),
            })

    def _round_entry(self, character_id, name=""):
        """Счётчики героя за раунд: создаются при первом событии и живут до выхода всех игроков."""
        entry = self._round_stats.get(character_id)
        if entry is None:
            entry = {
                "character_id": character_id,
                "name": name,
                "damage_dealt": 0,
                "damage_taken": 0,
                "kills": 0,
                "xp": 0,
                "deaths": 0,
            }
            self._round_stats[character_id] = entry
        return entry

    def _damage_mob(self, mob, damage, attacker=None):
        dealt = super()._damage_mob(mob, damage, attacker)
        if attacker is not None and dealt > 0:
            self._round_entry(attacker.character_id)["damage_dealt"] += dealt
        return dealt

    def _player_died(self, player):
        self._round_entry(player.character_id)["deaths"] += 1
        super()._player_died(player)

    def _build_match_summary(self, result):
        """Итоги раунда для экрана результатов. Фиксируются в момент конца матча."""
        entries = [dict(entry) for entry in self._round_stats.values()]
        total_damage = sum(entry["damage_dealt"] for entry in entries)
        for entry in entries:
            entry["damage_share"] = (
                round(100.0 * entry["damage_dealt"] / total_damage, 1) if total_damage else 0.0
            )
        entries.sort(key=lambda entry: entry["damage_dealt"], reverse=True)
        return {
            "result": result,
            "duration_seconds": max(0, int(self._clock() - self._game_started_at)),
            "mobs_killed": self._round_mobs_killed,
            "total_damage": total_damage,
            "objective_alive": sum(1 for b in self._building_states if b["hp"] > 0),
            "objective_total": len(self._building_states),
            "players": entries,
        }

    def _finish_match(self, result):
        """Конец игры (победа или поражение): уровень и навыки персонажей возвращаются к стартовым."""
        if self._match_result == result:
            return
        self._match_result = result
        self._match_summary = self._build_match_summary(result)
        self._reset_session_wallets()
        for character_id, player in self._players.items():
            self._reset_character_progress(player.user_id, character_id)

    def _reset_character_progress(self, user_id, character_id):
        """Стартовые уровень, опыт и характеристики персонажа, как при создании."""
        stats, free_points = creation_stats()
        max_hp = calculate_max_hp(FRONT_LINE_START_LEVEL, stats["endurance"])
        self._database.save_world_progression(
            user_id, character_id, FRONT_LINE_START_LEVEL, 0, stats, free_points, max_hp)

    def _check_match_victory(self):
        waves = [
            wave
            for spawner in self._mob_spawners
            for wave in spawner["waves"]
        ]
        if any(
            wave["remaining"] > 0 or wave["boss_pending"]
            for wave in waves
        ):
            return
        if any(mob.alive for mob in self._mobs.values()):
            return
        self._finish_match("victory")

    def _nearest_front_line_player(self, mob):
        return min(
            self._players.values(),
            key=lambda player: math.hypot(player.x - mob.x, player.y - mob.y),
            default=None,
        )

    def _defeat_mob(self, mob, killer):
        super()._defeat_mob(mob, killer)
        self._round_mobs_killed += 1
        if getattr(killer, "character_id", None) is not None:
            self._round_entry(killer.character_id)["kills"] += 1
        if bool(getattr(mob, "is_boss", False)):
            self._create_boss_item_drop(mob)
        mob.respawn_timer = MOB_CORPSE_SECONDS

    def _mob_strike(self, mob, player):
        if getattr(mob, "attack_style", "warrior") != "warrior":
            self._launch_mob_projectile(mob, player)
            return
        self._apply_mob_hit(mob, player)

    def _apply_mob_hit(self, mob, player):
        result = front_line_combat.resolve_melee_attack(
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
        taken = min(result["damage"], player.fighter.hp)
        player.fighter.hp = max(0, player.fighter.hp - result["damage"])
        self._round_entry(player.character_id)["damage_taken"] += taken
        player.dirty = True
        lifesteal_percent = front_line_combat.lifesteal_percent(mob.fighter)
        lifesteal_percent += sum(
            front_line_combat.aura_lifesteal_percent(
                owner.fighter,
                "enemies",
                math.hypot(owner.x - mob.x, owner.y - mob.y),
            )
            for owner in self._players.values()
        )
        healed = front_line_combat.apply_lifesteal(mob.fighter, result["damage"], lifesteal_percent)
        self._emit_number(player, result["damage"], result["critical"], player.x, top_y)
        crit_text = " (критический)" if result["critical"] else ""
        self._emit_log(player, f"{names['nom']} нанес вам {result['damage']} урона{crit_text}", "enemy")
        if healed:
            self._emit_log(player, f"{names['nom']} восстановил {healed} HP", "enemy")
        if player.fighter.hp <= 0:
            self._player_died(player)

    def _chase_goal(self, mob, player):
        """Куда идёт моб в погоне.

        Сначала место в кольце вокруг героя, если до него прямой путь чистый. Иначе — по полю стоимости
        мест удара: моб идёт к ближайшему свободному месту, обходя героя и занятые места. Если путь
        не нужен (моб уже в зоне удара или пути нет), — к самому герою.
        """
        field = self._attack_field(player)
        slot = self._ring_slots(player).get(id(mob))
        if slot is not None:
            x, y = slot
            slot_cell = (math.floor(x / TILE), math.floor(y / TILE))
            # Место кольца годится, только если оно свободно по полю: на узком проходе оно за занятой крысой.
            if (slot_cell in field and field[slot_cell] < ATTACK_SPOT_TAKEN_COST
                    and not self._terrain_blocked(x, y) and self._terrain_segment_clear(mob.x, mob.y, x, y)
                    and not self._segment_passes_near(mob.x, mob.y, x, y, player.x, player.y, HERO_PATH_RADIUS_PX)):
                return SimpleNamespace(x=x, y=y)
        cell = (math.floor(mob.x / TILE), math.floor(mob.y / TILE))
        if cell not in field:
            return player
        best = cell
        for dx, dy in CHASE_STEPS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if field.get(nxt, math.inf) < field.get(best, math.inf):
                best = nxt
        if best == cell or field[cell] <= 0:
            return player
        return SimpleNamespace(x=(best[0] + 0.5) * TILE, y=(best[1] + 0.5) * TILE)

    @timed("поле атаки (пересчёт)")
    def _attack_field(self, player):
        """Стоимость выхода к месту удара для каждой клетки. Места удара — 4 клетки рядом с героем.

        Клетка героя не проходима. Место, занятое другой живой крысой, стоит ATTACK_SPOT_TAKEN_COST, поэтому
        очередь предпочитает свободный проход. Считается раз за тик на героя.
        """
        epoch = getattr(self, "_ring_epoch", 0)
        hero_cell = (math.floor(player.x / TILE), math.floor(player.y / TILE))
        width = int(getattr(self, "_map_width", 64))
        height = int(getattr(self, "_map_height", 64))
        # Поле стоимостей меняется медленно (крысы смещаются за доли секунды): пересчёт раз в несколько тактов.
        key = (epoch // ATTACK_FIELD_REFRESH_TICKS, hero_cell, world_map.TERRAIN_VERSION, width, height)
        cached = getattr(self, "_attack_field_cache", None)
        if cached is not None and cached["key"] == key:
            return cached["field"]
        occupied = {
            (math.floor(mob.x / TILE), math.floor(mob.y / TILE))
            for mob in self._mobs.values() if mob.alive
        }

        def walkable(cell):
            return (0 <= cell[0] < width and 0 <= cell[1] < height
                    and not self._terrain_blocked((cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE))

        field = {}
        heap = []
        for dx, dy in CHASE_STEPS:
            seed = (hero_cell[0] + dx, hero_cell[1] + dy)
            if not walkable(seed):
                continue
            cost = ATTACK_SPOT_TAKEN_COST if seed in occupied else 0
            field[seed] = cost
            heapq.heappush(heap, (cost, seed))
        while heap:
            cost, cell = heapq.heappop(heap)
            if cost > field.get(cell, math.inf):
                continue
            for dx, dy in CHASE_STEPS:
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt == hero_cell or not walkable(nxt):
                    continue
                new_cost = cost + 1 + (CELL_OCCUPIED_COST if nxt in occupied else 0)
                if new_cost < field.get(nxt, math.inf):
                    field[nxt] = new_cost
                    heapq.heappush(heap, (new_cost, nxt))
        self._attack_field_cache = {"key": key, "field": field}
        return field

    @staticmethod
    def _ring_position(player, slot):
        ring, index = slot
        angle = 2.0 * math.pi * index / RING_SLOTS[ring]
        radius = RING_RADII_PX[ring]
        return player.x + radius * math.cos(angle), player.y + radius * math.sin(angle)

    @staticmethod
    def _segment_passes_near(ax, ay, bx, by, px, py, radius):
        """Отрезок (ax, ay)–(bx, by) проходит ближе radius к точке (px, py)."""
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        t = 0.0 if length_sq <= 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        return math.hypot(ax + dx * t - px, ay + dy * t - py) < radius

    def _ring_free(self, mob, player, slot):
        """Место кольца достижимо для этого моба: не в препятствии, без стены и без героя на пути."""
        x, y = self._ring_position(player, slot)
        if self._terrain_blocked(x, y) or not self._terrain_segment_clear(mob.x, mob.y, x, y):
            return False
        return not self._segment_passes_near(mob.x, mob.y, x, y, player.x, player.y, HERO_PATH_RADIUS_PX)

    def _ring_slots(self, player):
        """Места вокруг героя для преследующих его мобов на этом тике: {id(моб): (x, y)}.

        Ближайшие мобы занимают первое кольцо, остальные — второе. Место держится, пока моб не ушёл от него
        больше чем на RING_RELEASE_RADIANS.
        """
        epoch = getattr(self, "_ring_epoch", 0)
        cache = getattr(self, "_ring_cache", None)
        if cache is None or cache["epoch"] != epoch:
            cache = {"epoch": epoch, "heroes": {}}
            self._ring_cache = cache
        key = getattr(player, "character_id", id(player))
        if key in cache["heroes"]:
            return cache["heroes"][key]
        chasers = [
            mob for mob in self._mobs.values()
            if mob.alive and mob.state == "chase" and getattr(mob, "target", None) is player
        ]
        chasers.sort(key=lambda mob: (math.hypot(mob.x - player.x, mob.y - player.y), str(mob.id)))
        used = set()
        slots = {}
        waiting = []
        for mob in chasers:
            angle = math.atan2(mob.y - player.y, mob.x - player.x)
            held = getattr(mob, "front_line_ring", None)
            if held is not None and held[0] == key and held[1] not in used and self._ring_free(mob, player, held[1]):
                slot_angle = 2.0 * math.pi * held[1][1] / RING_SLOTS[held[1][0]]
                if _angle_gap(angle, slot_angle) <= RING_RELEASE_RADIANS:
                    used.add(held[1])
                    slots[id(mob)] = self._ring_position(player, held[1])
                    continue
            mob.front_line_ring = None
            waiting.append((mob, angle))
        for mob, angle in waiting:
            choice = None
            for ring in range(len(RING_SLOTS)):
                free = [
                    (_angle_gap(angle, 2.0 * math.pi * index / RING_SLOTS[ring]), index)
                    for index in range(RING_SLOTS[ring])
                    if (ring, index) not in used and self._ring_free(mob, player, (ring, index))
                ]
                if free:
                    choice = (ring, min(free)[1])
                    break
            if choice is None:
                continue
            used.add(choice)
            mob.front_line_ring = (key, choice)
            slots[id(mob)] = self._ring_position(player, choice)
        cache["heroes"][key] = slots
        return slots

    def _player_attack_range_px(self, player):
        return front_line_combat.range_units_to_px(front_line_combat.hero_attack_range_units(player.fighter))

    def _player_attack_distance(self, player, mob):
        return front_line_combat.attack_distance_px(
            player.x, player.y, mob.x, mob.y,
            front_line_combat.mob_range_hull_px(bool(getattr(mob, "is_boss", False))),
        )

    def _mob_attack_range_px(self, mob):
        units = getattr(mob, "attack_range_units", None)
        if units is None:
            units = front_line_combat.MOB_ATTACK_RANGE_UNITS
        return front_line_combat.range_units_to_px(units)

    def _mob_attack_distance(self, mob, player):
        return front_line_combat.attack_distance_px(
            mob.x, mob.y, player.x, player.y, front_line_combat.HERO_BODY_RADIUS_PX,
        )

    def _projectile_list(self):
        if not hasattr(self, "_projectiles"):
            self._projectiles = []
        return self._projectiles

    def _deliver_player_strike(self, player, target):
        """Ближний бой бьёт сразу; лучник и маг выпускают снаряд, который летит за целью и бьёт при попадании."""
        kind = front_line_combat.projectile_kind(player.fighter.profession_type)
        if not kind:
            self._strike_mob(player, target)
            return
        self._projectile_sequence = getattr(self, "_projectile_sequence", 0) + 1
        speed = front_line_combat.projectile_speed_px(player.fighter.profession_type)
        origin = (player.x, player.y)
        self._projectile_list().append({
            "id": self._projectile_sequence,
            "owner": player,
            "target": target,
            "kind": kind,
            "from": origin,
            "pos": origin,
            "last": (target.x, target.y),
            "speed": speed,
            "age": 0.0,
        })
        # Событие нужно клиенту в момент выстрела: снаряд летит от героя, а не появляется у цели.
        self._emit(player, {
            "type": "projectile",
            "id": self._projectile_sequence,
            "kind": kind,
            "from": [player.x, player.y],
            "target": target.id,
            "speed": speed,
        })

    def _explode_orb(self, owner, center):
        """Взрыв мага: урон всем живым мобам в радиусе от точки попадания, даже если цель уже погибла."""
        radius = front_line_combat.area_radius_px()
        for mob in list(self._mobs.values()):
            if not mob.alive:
                continue
            distance = front_line_combat.attack_distance_px(
                center.x, center.y, mob.x, mob.y, self._mob_separation_radius(mob),
            )
            if distance <= radius:
                self._strike_mob(owner, mob)

    def _launch_mob_projectile(self, mob, player):
        """Стрелок и маг бьют снарядом: стрела или сфера летит к герою и бьёт при попадании."""
        profession = mob.attack_style
        kind = front_line_combat.projectile_kind(profession)
        self._projectile_sequence = getattr(self, "_projectile_sequence", 0) + 1
        speed = front_line_combat.projectile_speed_px(profession)
        origin = (mob.x, mob.y)
        self._projectile_list().append({
            "id": self._projectile_sequence,
            "source": "mob",
            "owner": mob,
            "target": player,
            "kind": kind,
            "pos": origin,
            "speed": speed,
            "age": 0.0,
        })
        # Снаряд видят все герои в мире: каждому нужно событие выстрела.
        for other in list(self._players.values()):
            self._emit(other, {
                "type": "projectile",
                "id": self._projectile_sequence,
                "kind": kind,
                "from": [mob.x, mob.y],
                "target": player.character_id,
                "speed": speed,
            })

    def _update_mob_projectiles(self, dt):
        """Двигает снаряды мобов и возвращает те, что ещё летят."""
        flying = []
        for shot in self._projectile_list():
            if shot.get("source") != "mob":
                continue
            target = shot["target"]
            if not any(player is target for player in self._players.values()):
                continue  # герой вышел из мира: снаряд пропадает
            shot["age"] += dt
            px, py = shot["pos"]
            tx, ty = target.x, target.y
            step = shot["speed"] * dt
            distance = math.hypot(tx - px, ty - py)
            edge = front_line_combat.attack_distance_px(px, py, tx, ty, front_line_combat.HERO_BODY_RADIUS_PX)
            if edge <= step:
                self._land_mob_projectile(shot, tx, ty, target)
                continue
            if shot["age"] >= front_line_combat.PROJECTILE_MAX_SECONDS:
                if shot["kind"] == "orb":
                    self._land_mob_projectile(shot, px, py, target)
                continue
            fraction = min(1.0, step / distance) if distance > 0 else 1.0
            shot["pos"] = (px + (tx - px) * fraction, py + (ty - py) * fraction)
            flying.append(shot)
        return flying

    def _land_mob_projectile(self, shot, x, y, target):
        for other in list(self._players.values()):
            self._emit(other, {"type": "projectile_hit", "id": shot["id"], "x": x, "y": y, "kind": shot["kind"]})
        mob = shot["owner"]
        if shot["kind"] == "orb":
            radius = front_line_combat.range_units_to_px(getattr(
                mob, "area_radius_units", front_line_combat.MAGE_AREA_RADIUS_UNITS))
            for player in list(self._players.values()):
                if front_line_combat.attack_distance_px(x, y, player.x, player.y, front_line_combat.HERO_BODY_RADIUS_PX) <= radius:
                    self._apply_mob_hit(mob, player)
        elif target.fighter.hp > 0:
            self._apply_mob_hit(mob, target)

    @timed("снаряды")
    def _update_projectiles(self, dt):
        mob_shots = self._update_mob_projectiles(dt)
        projectiles = [shot for shot in self._projectile_list() if shot.get("source") != "mob"]
        if not projectiles:
            self._projectiles = mob_shots
            return
        still_flying = []
        for projectile in projectiles:
            owner = projectile["owner"]
            target = projectile["target"]
            if not any(player is owner for player in self._players.values()):
                continue
            projectile["age"] += dt
            if target.alive:
                projectile["last"] = (target.x, target.y)
            tx, ty = projectile["last"]
            px, py = projectile["pos"]
            step = projectile["speed"] * dt
            distance = math.hypot(tx - px, ty - py)
            if projectile["age"] >= front_line_combat.PROJECTILE_MAX_SECONDS:
                if projectile["kind"] == "orb":
                    self._land_projectile(projectile, px, py, owner, target)
                continue
            if target.alive:
                edge = front_line_combat.attack_distance_px(px, py, tx, ty, self._mob_separation_radius(target))
                if edge <= step:
                    self._land_projectile(projectile, px, py, owner, target)
                    continue
            elif distance <= step:
                # Цель погибла в полёте: сгусток взрывается там, где её видели, стрела пропадает.
                if projectile["kind"] == "orb":
                    self._land_projectile(projectile, tx, ty, owner, target)
                continue
            fraction = min(1.0, step / distance) if distance > 0 else 1.0
            projectile["pos"] = (px + (tx - px) * fraction, py + (ty - py) * fraction)
            still_flying.append(projectile)
        self._projectiles = still_flying + mob_shots

    def _land_projectile(self, projectile, x, y, owner, target):
        self._emit(owner, {"type": "projectile_hit", "id": projectile["id"], "x": x, "y": y, "kind": projectile["kind"]})
        if projectile["kind"] == "orb":
            self._explode_orb(owner, SimpleNamespace(x=x, y=y))
        elif target.alive:
            self._strike_mob(owner, target)

    def _strike_mob(self, player, mob):
        mob.provoker = player
        result = front_line_combat.resolve_melee_attack(
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
        lifesteal_percent = front_line_combat.lifesteal_percent(player.fighter)
        lifesteal_percent += self._player_aura_lifesteal_percent(player)
        healed = front_line_combat.apply_lifesteal(player.fighter, dealt, lifesteal_percent)
        if healed:
            player.dirty = True
            self._emit_log(player, f"Вы восстановили {healed} HP благодаря вампиризму", "player")
        self._emit_number(player, dealt, result["critical"], wx, wy)
        crit_text = " (критический)" if result["critical"] else ""
        self._emit_log(player, f"Вы нанесли {names['dat']} {dealt} урона{crit_text}", "player")
        if not mob.alive:
            self._defeat_mob(mob, player)

    def _player_aura_lifesteal_percent(self, target):
        percent = 0
        for owner in self._players.values():
            percent += front_line_combat.aura_lifesteal_percent(
                owner.fighter,
                "allies",
                math.hypot(owner.x - target.x, owner.y - target.y),
            )
        return min(100, percent)

    def _create_boss_item_drop(self, mob):
        slots = getattr(mob, "boss_drop_slots", [])
        roll = self._rng.randint(1, 100)
        threshold = 0
        for slot in slots:
            item_id = int(slot.get("item_id", 0))
            chance = int(slot.get("chance_percent", 0))
            previous_threshold = threshold
            threshold += chance
            if item_id <= 0 or chance <= 0 or not previous_threshold < roll <= threshold:
                continue
            catalog_item = self._items.get_catalog_items([item_id]).get(str(item_id))
            if catalog_item is None:
                return
            self._item_drop_sequence += 1
            drop_id = f"front_line_item_{self._item_drop_sequence}"
            self._item_drops[drop_id] = {
                "id": drop_id,
                "item_id": item_id,
                "name": str(catalog_item["name"]),
                "icon": str(catalog_item.get("icon", "")),
                "x": mob.x,
                "y": mob.y,
            }
            return

    def loot_item_drop(self, user_id, character_id, drop_id):
        with self._lock:
            player = self._players.get(int(character_id))
            if player is None or player.user_id != int(user_id):
                raise ValueError("Персонаж не находится в этом мире")
            drop = self._item_drops.get(str(drop_id))
            if drop is None:
                raise ValueError("Предмет уже подобран или не найден")
            if math.hypot(drop["x"] - player.x, drop["y"] - player.y) > ITEM_DROP_PICKUP_RANGE:
                raise ValueError("Подойдите ближе к предмету")
            added = self.run_inventory_action(
                int(user_id),
                int(character_id),
                lambda: self._items.add_to_inventory(
                    int(character_id), int(drop["item_id"]), 1,
                ),
            )
            if not added:
                raise ValueError("В рюкзаке не хватает места для предмета")
            self._item_drops.pop(str(drop_id), None)
            self._emit_notice(player, f"Подобран предмет: {drop['name']}")
            return {"drop_id": str(drop_id), "item": drop}


# Замеры стадий удара: печатают только медленные вызовы (см. server/perf_probe.py).
for _method, _label in (
    ("_tick_player", "шаг героя в тике"),
    ("_update_player_attack", "замах и удар героя"),
    ("_deliver_player_strike", "выпуск удара или снаряда"),
    ("_strike_mob", "удар по мобу"),
    ("_defeat_mob", "гибель моба (награда и монеты)"),
    ("_flush", "сохранение HP и MP в базу"),
    ("_regenerate", "регенерация героя"),
    ("_refresh_carry", "пересчёт груза"),
    ("_refresh_structures", "обновление построек"),
    ("_update_wildlife", "дикие животные"),
):
    setattr(FrontLineWorldService, _method, timed(_label)(getattr(FrontLineWorldService, _method)))
