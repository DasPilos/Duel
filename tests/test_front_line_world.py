import math
import os
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from combat.fighter import Fighter
from core import mob_modes
from core.map_catalog import catalog_definitions
from front_line.server import combat as front_line_combat
from combat.character_stats import calculate_max_hp, creation_stats
from front_line.server.world import MOB_SEPARATION_RADIUS, FrontLineWorldService
from server import map_editor, map_worlds, world_map
from server.items_database import ItemsDatabase
from tests.fixtures import create_test_database, drop_test_database


GROUND = next(item["item_key"] for item in catalog_definitions() if item["kind"] == "ground")
WATER = next(item["item_key"] for item in catalog_definitions() if item["category"] == "water")


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FixedRoll:
    def __init__(self, value):
        self.value = value

    def randint(self, _minimum, _maximum):
        return self.value


class AtlasWalkabilityTests(unittest.TestCase):
    def test_stone_crossing_passes_heroes_and_mobs_but_keeps_adjacent_water(self):
        catalog = catalog_definitions()
        water = [
            {"layer": "ground", "x": x, "y": y, "key": WATER}
            for x in range(4, 10) for y in range(4, 8)
        ]
        stones = [
            {
                "layer": "ground", "x": 6 + column, "y": 4 + row,
                "key": (
                    "atlas|res://assets/base_tails/Biome/"
                    "craftpix-net-189510-grassland-top-down-tileset-pixel-art/"
                    f"Tiled_files/Water_coasts.png|{33 + column}|{1 + row}"
                ),
            }
            for column in range(2) for row in range(4)
        ]
        layers = [
            {"id": 1, "type": "tile", "cells": water},
            {"id": 2, "type": "tile", "cells": stones},
        ]
        cells = FrontLineWorldService._editor_terrain_cells(water, layers, catalog)
        terrain = map_editor.terrain_from_cells(cells, catalog)
        FrontLineWorldService._apply_atlas_collision(terrain, layers, 16, 16)
        self.addCleanup(world_map.apply_live_terrain)
        world_map.apply_live_terrain(
            terrain, {"map_w": 16, "map_h": 16, "published_at": 1},
        )
        service = FrontLineWorldService.__new__(FrontLineWorldService)
        service._wildlife = {}
        service._solid_rects = []
        service._players = {}
        for cell in stones:
            x, y = (cell["x"] + 0.5) * world_map.TILE, (cell["y"] + 0.5) * world_map.TILE
            self.assertTrue(world_map.is_passable(x, y))
            self.assertFalse(service._terrain_blocked(x, y))
        self.assertFalse(world_map.is_passable(5.5 * world_map.TILE, 5.5 * world_map.TILE))
        bridge_tiles = {tuple(tile) for bridge in terrain["bridges"] for tile in bridge["tiles"]}
        self.assertEqual(bridge_tiles, {(cell["x"], cell["y"]) for cell in stones})
        for start_y, target_y in ((3.5, 8.5), (8.5, 3.5)):
            with self.subTest(start_y=start_y):
                mob = SimpleNamespace(
                    x=6.5 * world_map.TILE, y=start_y * world_map.TILE,
                    move_speed=96, chase_route=[], chase_replan_timer=0, facing=0,
                )
                target = SimpleNamespace(x=mob.x, y=target_y * world_map.TILE)
                for _ in range(100):
                    service._move_mob_toward(mob, target, 1 / 30)
                self.assertAlmostEqual(mob.y, target.y)

    def test_uncovered_water_background_blocks_but_top_land_and_objects_replace_it(self):
        terrain = {
            "water": set(),
            "impassable": set(),
            "mountain": set(),
            "forest": set(),
            "dry": set(),
            "partial": {},
        }
        cells = [
            {"x": x, "y": y, "key": "atlas|res://water_detilazation.png|0|0"}
            for y in range(64)
            for x in range(64)
        ]
        cells.extend(
            [
                {
                    "x": 27,
                    "y": 56,
                    "key": (
                        "atlas|res://assets/base_tails/Biome/"
                        "craftpix-net-189510-grassland/Tiled_files/"
                        "Water_coasts.png|3|2|3|2|core"
                    ),
                },
                {
                    "x": 10,
                    "y": 10,
                    "key": (
                        "atlas|res://assets/base_tails/Biome/"
                        "craftpix-net-189510-grassland/Tiled_files/"
                        "Water_coasts.png|2|1"
                    ),
                },
                {"x": 40, "y": 40, "key": "atlas|res://Exterior.png|0|0"},
            ]
        )

        FrontLineWorldService._apply_atlas_collision(
            terrain,
            [{"type": "tile", "visible": True, "cells": cells}],
            64,
            64,
        )

        expected_water = {(x, y) for y in range(64) for x in range(64)}
        expected_water -= {(27, 56), (40, 40)}
        self.assertEqual(terrain["water"], expected_water)
        self.assertEqual(terrain["impassable"], {(40, 40)})

    def test_top_decorative_layer_preserves_lower_atlas_collision(self):
        terrain = {
            "water": set(),
            "impassable": set(),
            "mountain": set(),
            "forest": set(),
            "dry": set(),
            "partial": {},
        }
        layers = [
            {
                "type": "tile",
                "visible": True,
                "cells": [{
                    "x": 2,
                    "y": 3,
                    "key": "atlas|res://water.png|0|0",
                }],
            },
            {
                "type": "decorative",
                "visible": True,
                "cells": [{
                    "x": 2,
                    "y": 3,
                    "key": "atlas|res://Exterior.png|0|0",
                }],
            },
        ]

        FrontLineWorldService._apply_atlas_collision(terrain, layers, 16, 16)

        self.assertIn((2, 3), terrain["water"])
        self.assertNotIn((2, 3), terrain["impassable"])

    def test_top_normal_atlas_layer_replaces_lower_water_collision(self):
        terrain = {
            "water": set(),
            "impassable": set(),
            "mountain": set(),
            "forest": set(),
            "dry": set(),
            "partial": {},
        }
        layers = [
            {
                "type": "tile",
                "visible": True,
                "cells": [{
                    "x": 2,
                    "y": 3,
                    "key": "atlas|res://water.png|0|0",
                }],
            },
            {
                "type": "tile",
                "visible": True,
                "cells": [{
                    "x": 2,
                    "y": 3,
                    "key": "atlas|res://Exterior.png|0|0",
                }],
            },
        ]

        FrontLineWorldService._apply_atlas_collision(terrain, layers, 16, 16)

        self.assertNotIn((2, 3), terrain["water"])
        self.assertIn((2, 3), terrain["impassable"])

    def test_decorative_catalog_layer_preserves_lower_water_terrain(self):
        catalog = catalog_definitions()
        water_cell = {"layer": "ground", "x": 2, "y": 3, "key": WATER}
        layers = [
            {
                "id": 1,
                "type": "tile",
                "visible": True,
                "cells": [water_cell],
            },
            {
                "id": 2,
                "type": "decorative",
                "visible": True,
                "cells": [{
                    "layer": "ground",
                    "x": 2,
                    "y": 3,
                    "key": GROUND,
                }],
            },
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [water_cell], layers, catalog,
        )

        self.assertEqual(resolved, [water_cell])

    def test_surface_resolution_matches_movement_and_payload(self):
        catalog = catalog_definitions()
        grass = "grassland_water_coasts_0081"
        road = next(
            item["item_key"] for item in catalog
            if item["category"] == "road" and not item["blocks"]
        )
        mountain = next(
            item["item_key"] for item in catalog
            if item["category"] == "rock" and item["kind"] == "ground"
        )
        atlas_water = "atlas|res://water.png|0|0"
        cases = [
            (WATER, grass, "tile", True, None),
            (atlas_water, grass, "tile", True, None),
            (WATER, "atlas|res://grass.png|0|0", "tile", True, None),
            (grass, road, "tile", True, "paths"),
            (WATER, "atlas|res://bridge.png|0|0", "tile", True, None),
            (grass, mountain, "tile", False, "mountain"),
            (WATER, grass, "decorative", False, "water"),
            (atlas_water, "atlas|res://bridge.png|0|0", "decorative", False, "water"),
            (grass, WATER, "decorative", True, None),
            (grass, "atlas|res://Exterior.png|0|0", "decorative", True, None),
        ]
        self.addCleanup(world_map.apply_live_terrain)
        service = FrontLineWorldService.__new__(FrontLineWorldService)
        service._wildlife = {}
        service._solid_rects = []
        for lower, upper, layer_type, passable, property_name in cases:
            with self.subTest(lower=lower, upper=upper, layer_type=layer_type):
                lower_cell = {"layer": "ground", "x": 6, "y": 6, "key": lower}
                upper_cell = {"layer": "ground", "x": 6, "y": 6, "key": upper}
                uncovered = {"layer": "ground", "x": 7, "y": 6, "key": WATER}
                layers = [
                    {"id": 1, "type": "tile", "cells": [lower_cell, uncovered]},
                    {"id": 2, "type": layer_type, "cells": [upper_cell]},
                ]
                cells = FrontLineWorldService._editor_terrain_cells(
                    [lower_cell, upper_cell, uncovered], layers, catalog,
                )
                terrain = map_editor.terrain_from_cells(cells, catalog)
                FrontLineWorldService._apply_atlas_collision(terrain, layers, 16, 16)
                world_map.apply_live_terrain(
                    terrain, {"map_w": 16, "map_h": 16, "published_at": 1},
                )
                x = y = 6.5 * world_map.TILE
                self.assertEqual(world_map.is_passable(x, y), passable)
                self.assertEqual(service._terrain_blocked(x, y), not passable)
                self.assertEqual(
                    service._terrain_segment_clear(x - 2, y, x + 2, y), passable,
                )
                self.assertFalse(world_map.is_passable(7.5 * world_map.TILE, y))
                with patch.object(world_map, "IS_TOWER_WORLD", True):
                    tiles = world_map.terrain_payload()["tiles"]
                self.assertEqual(
                    tiles["water"], [[6, 6 if property_name == "water" else 7, 7]],
                )
                for name in ("paths", "mountain"):
                    self.assertEqual(tiles[name], [[6, 6, 6]] if name == property_name else [])

    def test_hidden_group_does_not_override_lower_surface(self):
        catalog = catalog_definitions()
        water_cell = {"layer": "ground", "x": 2, "y": 3, "key": WATER}
        for upper_key in (GROUND, "atlas|res://bridge.png|0|0"):
            with self.subTest(upper_key=upper_key):
                layers = [
                    {"id": 1, "type": "tile", "cells": [water_cell]},
                    {"id": 2, "type": "group", "visible": False},
                    {
                        "id": 3, "type": "tile", "parent_id": 2,
                        "cells": [{"layer": "ground", "x": 2, "y": 3, "key": upper_key}],
                    },
                ]
                cells = FrontLineWorldService._editor_terrain_cells(
                    [water_cell], layers, catalog,
                )
                terrain = map_editor.terrain_from_cells(cells, catalog)
                FrontLineWorldService._apply_atlas_collision(terrain, layers, 16, 16)
                self.assertEqual(cells, [water_cell])
                self.assertIn((2, 3), terrain["water"])

    def test_hidden_tile_layer_does_not_contribute_terrain(self):
        catalog = catalog_definitions()
        water_cell = {"layer": "ground", "x": 2, "y": 3, "key": WATER}
        layers = [
            {
                "id": 1,
                "type": "tile",
                "visible": False,
                "cells": [water_cell],
            },
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [water_cell], layers, catalog,
        )

        self.assertEqual(resolved, [])

    def test_decorative_catalog_object_does_not_block_movement(self):
        catalog = catalog_definitions()
        tavern = next(
            item for item in catalog
            if item["item_key"] == "city_building_tavern"
        )
        tavern_cell = {
            "layer": "object",
            "x": 2,
            "y": 3,
            "key": tavern["item_key"],
        }
        layers = [
            {"id": 1, "type": "tile", "visible": True, "cells": []},
            {
                "id": 2,
                "type": "decorative",
                "visible": True,
                "cells": [{
                    "layer": "object",
                    "x": 2,
                    "y": 3,
                    "key": tavern["item_key"],
                }],
            },
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [tavern_cell], layers, catalog,
        )

        self.assertNotIn(tavern_cell, resolved)

    def test_hidden_decorative_catalog_object_does_not_block_movement(self):
        catalog = catalog_definitions()
        tavern = next(
            item for item in catalog
            if item["item_key"] == "city_building_tavern"
        )
        tavern_cell = {
            "layer": "object",
            "x": 2,
            "y": 3,
            "key": tavern["item_key"],
        }
        layers = [
            {"id": 1, "type": "tile", "visible": True, "cells": []},
            {
                "id": 2,
                "type": "decorative",
                "visible": False,
                "cells": [{
                    "layer": "object",
                    "x": 2,
                    "y": 3,
                    "key": tavern["item_key"],
                }],
            },
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [tavern_cell], layers, catalog,
        )

        self.assertNotIn(tavern_cell, resolved)

    def test_higher_catalog_road_replaces_lower_water_terrain(self):
        catalog = catalog_definitions()
        road = next(
            item for item in catalog
            if item.get("category") == "road" and not item.get("blocks")
        )
        water_cell = {"layer": "ground", "x": 2, "y": 3, "key": WATER}
        road_cell = {"layer": "overlay", "x": 2, "y": 3, "key": road["item_key"]}
        untouched_ground = {"layer": "ground", "x": 5, "y": 6, "key": GROUND}
        layers = [
            {"id": 1, "type": "tile", "visible": True, "cells": [water_cell]},
            {"id": 2, "type": "tile", "visible": True, "cells": [road_cell]},
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [water_cell, untouched_ground], layers, catalog,
        )
        terrain = map_editor.terrain_from_cells(resolved, catalog)

        self.assertNotIn((2, 3), terrain["water"])
        self.assertIn((2, 3), terrain["paths"])
        self.assertEqual(
            {(cell["x"], cell["y"], cell["key"]) for cell in resolved},
            {
                (2, 3, road["item_key"]),
                (5, 6, GROUND),
            },
        )

    def test_higher_catalog_mountain_blocks_lower_water_terrain(self):
        catalog = catalog_definitions()
        mountain = next(
            item for item in catalog
            if item.get("category") == "rock" and item.get("kind") == "ground"
        )
        water_cell = {"layer": "ground", "x": 2, "y": 3, "key": WATER}
        mountain_cell = {
            "layer": "ground",
            "x": 2,
            "y": 3,
            "key": mountain["item_key"],
        }
        layers = [
            {"id": 1, "type": "tile", "visible": True, "cells": [water_cell]},
            {"id": 2, "type": "tile", "visible": True, "cells": [mountain_cell]},
        ]

        resolved = FrontLineWorldService._editor_terrain_cells(
            [water_cell], layers, catalog,
        )
        terrain = map_editor.terrain_from_cells(resolved, catalog)

        self.assertNotIn((2, 3), terrain["water"])
        self.assertIn((2, 3), terrain["mountain"])


class FrontLineMobCrowdTests(unittest.TestCase):
    def _service(self):
        service = FrontLineWorldService.__new__(FrontLineWorldService)
        service._wildlife = {}
        service._solid_rects = []
        service._players = {}
        service._mobs = {}
        service._rng = random.Random(1)
        service._tavern = SimpleNamespace(x=10 * world_map.TILE, y=0.0)
        service._tavern_hp = 100
        service._match_result = ""
        service._tavern_flow_cache = None
        return service

    def _apply_water(self, cells, size):
        catalog = catalog_definitions()
        water = [{"layer": "ground", "x": x, "y": y, "key": WATER} for x, y in cells]
        layers = [{"id": 1, "type": "tile", "cells": water}]
        terrain = map_editor.terrain_from_cells(
            FrontLineWorldService._editor_terrain_cells(water, layers, catalog), catalog,
        )
        self.addCleanup(world_map.apply_live_terrain)
        world_map.apply_live_terrain(terrain, {"map_w": size, "map_h": size, "published_at": 1})

    def test_tavern_attack_winds_up_strikes_then_recovers(self):
        service = self._service()
        mob = SimpleNamespace(
            x=5 * world_map.TILE, y=6.5 * world_map.TILE, facing=math.pi, fighter=SimpleNamespace(),
            windup=0.0, windup_total=0.0, backswing=0.0, windup_time=0.5, backswing_time=0.25,
            state="idle",
        )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=17):
            service._attack_tavern(mob, 0.25)
            self.assertEqual((service._tavern_hp, mob.windup_total, mob.windup), (100, 0.5, 0.25))
            self.assertLess(abs(mob.facing), math.pi / 4)
            service._attack_tavern(mob, 0.25)
            self.assertEqual((service._tavern_hp, mob.windup, mob.backswing), (83, 0.0, 0.25))
            service._attack_tavern(mob, 0.125)
            self.assertEqual((service._tavern_hp, mob.windup, mob.backswing), (83, 0.0, 0.125))

    def test_stacked_mobs_spread_apart_without_entering_water(self):
        self._apply_water([(8, y) for y in range(16)], 16)
        service = self._service()
        start = (7.6 * world_map.TILE, 8 * world_map.TILE)
        for index in range(6):
            service._mobs[str(index)] = SimpleNamespace(
                x=start[0], y=start[1] + (index - 2.5) * 34.0, alive=True, move_speed=100.0, is_boss=index == 0,
            )
        for _ in range(200):
            service._separate_mobs(0.05)
        mobs = list(service._mobs.values())
        for mob in mobs:
            self.assertFalse(service._terrain_blocked(mob.x, mob.y))
        for first_index, first in enumerate(mobs):
            for second in mobs[first_index + 1:]:
                expected = (
                    service._mob_separation_radius(first) + service._mob_separation_radius(second)
                )
                self.assertGreaterEqual(
                    math.hypot(first.x - second.x, first.y - second.y), expected - 1.0,
                )

    def test_stacked_crowd_spreads_along_tavern_walls_and_attacks(self):
        self._apply_water([(x, y) for x in range(10, 16) for y in range(10, 16)], 24)
        service = self._service()
        service._tavern = SimpleNamespace(x=10 * world_map.TILE, y=10 * world_map.TILE)
        service._objective = SimpleNamespace(x=9.5 * world_map.TILE, y=12.5 * world_map.TILE)
        service._map_width = service._map_height = 24
        service._game_started = service._waves_unlocked = True
        service._tavern_hp = 10 ** 6
        for index in range(10):
            service._mobs[str(index)] = SimpleNamespace(
                id=str(index), alive=True, state="idle", target=None, front_line_target="objective",
                x=20.5 * world_map.TILE, y=(2.5 + index * 1.1) * world_map.TILE, facing=0.0, move_speed=100.0,
                windup=0.0, windup_total=0.0, backswing=0.0, windup_time=0.5, backswing_time=0.5,
                chase_route=[], chase_replan_timer=0.0, fighter=SimpleNamespace(), is_boss=False,
            )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=1):
            for _ in range(600):
                service._update_mobs(1 / 30)
        mobs = list(service._mobs.values())
        # Тела не накладываются: у стены таверны бьют только те, кто помещается; остальные стоят в очереди.
        self.assertGreaterEqual(sum(mob.state == "attack" for mob in mobs), 3)
        self.assertLess(service._tavern_hp, 10 ** 6)
        for first_index, first in enumerate(mobs):
            self.assertFalse(service._terrain_blocked(first.x, first.y))
            for second in mobs[first_index + 1:]:
                self.assertGreaterEqual(
                    math.hypot(first.x - second.x, first.y - second.y),
                    2 * MOB_SEPARATION_RADIUS - 1.0,
                )

    def test_mobs_walk_around_hero_blocking_the_path_to_tavern(self):
        self._apply_water([(x, y) for x in range(10, 16) for y in range(10, 16)], 24)
        service = self._service()
        service._tavern = SimpleNamespace(x=10 * world_map.TILE, y=10 * world_map.TILE)
        service._objective = SimpleNamespace(x=9.5 * world_map.TILE, y=12.5 * world_map.TILE)
        service._map_width = service._map_height = 24
        service._game_started = service._waves_unlocked = True
        service._tavern_hp = 10 ** 6
        hero = SimpleNamespace(x=18.5 * world_map.TILE, y=12.5 * world_map.TILE)
        service._players = {1: hero}
        for index in range(3):
            service._mobs[str(index)] = SimpleNamespace(
                id=str(index), alive=True, state="idle", target=None, front_line_target="objective",
                x=(21.5 + index) * world_map.TILE, y=12.5 * world_map.TILE, facing=0.0, move_speed=100.0,
                windup=0.0, windup_total=0.0, backswing=0.0, windup_time=0.5, backswing_time=0.5,
                chase_route=[], chase_replan_timer=0.0, fighter=SimpleNamespace(), is_boss=False,
            )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=1):
            for _ in range(600):
                service._update_mobs(1 / 30)
                self.assertFalse(service._player_blocked(hero.x, hero.y), "моб не наползает на героя")
        self.assertEqual([mob.state for mob in service._mobs.values()], ["attack"] * 3)

    def test_chase_mob_steps_around_hero_blocking_its_waypoint(self):
        service = self._service()
        service._terrain_blocked = lambda x, y: False
        hero = SimpleNamespace(x=100.0, y=100.0)
        service._players = {1: hero}
        mob = SimpleNamespace(
            x=74.0, y=100.0, facing=0.0, move_speed=100.0, chase_route=[], chase_replan_timer=0.0,
            is_boss=False,
        )
        waypoint = SimpleNamespace(x=130.0, y=100.0)  # точка маршрута за героем

        for _ in range(30):
            service._move_mob_toward(mob, waypoint, 1 / 30)

        self.assertGreater(math.hypot(mob.x - 74.0, mob.y - 100.0), 10.0, "моб стоит перед героем")
        self.assertFalse(service._mob_blocked_by_players(mob.x, mob.y, mob))

    def test_swing_and_hurt_counters_advance_with_windup_and_damage(self):
        service = self._service()
        service._terrain_blocked = lambda x, y: False
        hero = SimpleNamespace(x=100.0, y=100.0)
        service._players = {1: hero}
        service._mob_strike = lambda mob, player: None
        mob = SimpleNamespace(
            x=110.0, y=100.0, home_x=110.0, home_y=100.0, facing=0.0, move_speed=100.0, chase_route=[],
            chase_replan_timer=0.0, windup=0.0, windup_total=0.0, backswing=0.0, windup_time=0.5,
            backswing_time=0.5, target=hero, fighter=Fighter("Крыса", level=1), is_boss=False,
        )

        service._update_mob_chase(mob, 1 / 30)
        self.assertEqual(getattr(mob, "swing_id", 0), 1, "новый замах увеличивает swing_id")
        service._update_mob_chase(mob, 1 / 30)
        self.assertEqual(getattr(mob, "swing_id", 0), 1, "продолжающийся замах не меняет swing_id")

        service._damage_mob(mob, 0)
        self.assertEqual(getattr(mob, "hurt_id", 0), 0, "нулевой урон не запускает анимацию урона")
        service._damage_mob(mob, 3)
        service._damage_mob(mob, 2)
        self.assertEqual(getattr(mob, "hurt_id", 0), 2, "каждый удар по мобу увеличивает hurt_id")

    def test_chase_mob_pressed_against_a_wall_walks_around_it(self):
        # Стена по x = 10 тайлов на всю высоту, проход только у низа карты (y = 20 тайлов).
        service = self._service()
        service._map_width = service._map_height = 24
        service._terrain_blocked = lambda x, y: int(x // world_map.TILE) == 10 and int(y // world_map.TILE) < 20
        hero = SimpleNamespace(x=8.5 * world_map.TILE, y=10.5 * world_map.TILE)
        service._players = {1: hero}
        mob = SimpleNamespace(
            x=12.5 * world_map.TILE, y=10.5 * world_map.TILE, facing=0.0, move_speed=100.0, chase_route=[],
            chase_replan_timer=0.0, is_boss=False,
        )
        for _ in range(1200):
            service._move_mob_toward(mob, hero, 1 / 30)
            if math.hypot(mob.x - hero.x, mob.y - hero.y) <= 40.0:
                break
        self.assertLessEqual(math.hypot(mob.x - hero.x, mob.y - hero.y), 40.0, "моб упёрся в стену и не обходит её")

    def test_chase_mobs_keep_striking_hero_standing_in_a_one_tile_gap(self):
        ty = 500.0

        def wall(x, y):
            return 400 <= x < 464 and not (ty - 16 <= y < ty + 16)

        service = self._service()
        service._game_started = service._waves_unlocked = True
        service._tavern_hp = 10 ** 6
        service._map_width = service._map_height = 24
        service._tavern = SimpleNamespace(x=0.0, y=0.0)
        service._objective = SimpleNamespace(x=0.0, y=0.0)
        service._terrain_blocked = wall
        hero = SimpleNamespace(x=432.0, y=ty)
        service._players = {1: hero}
        strikes = []
        service._mob_strike = lambda mob, player: strikes.append((service._tick, mob.id))
        service._tick = 0
        service._seq = 0
        hero.events = []
        hero.dirty = False
        for index, y in enumerate((ty, ty - 20, ty + 20)):
            service._mobs[str(index)] = SimpleNamespace(
                id=str(index), alive=True, state="idle", target=None, front_line_target="both",
                x=250.0, y=y, home_x=250.0, home_y=y, facing=0.0, move_speed=100.0, windup=0.0,
                windup_total=0.0, backswing=0.0, windup_time=0.5, backswing_time=0.5, chase_route=[],
                chase_replan_timer=0.0, fighter=Fighter("Крыса", level=1), is_boss=False,
            )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=1):
            for tick in range(900):
                service._tick = tick
                service._update_mobs(1 / 30)
        late = {str(index) for tick, index in strikes if tick >= 600}
        # Герой в проходе в один тайл: к нему подходит одна крыса за раз, остальные ждут в очереди за стеной
        # (места кольца, достижимые только через проход). Проверяем, что удары продолжаются.
        self.assertGreaterEqual(len(late), 1)

    def test_mob_touching_hero_may_step_away_but_not_closer(self):
        service = self._service()
        hero = SimpleNamespace(x=100.0, y=100.0)
        service._players = {1: hero}
        mob = SimpleNamespace(x=110.0, y=100.0, is_boss=False)

        self.assertFalse(service._mob_blocked_by_players(114.0, 100.0, mob))
        self.assertTrue(service._mob_blocked_by_players(106.0, 100.0, mob))
        self.assertTrue(service._mob_blocked_by_players(114.0, 100.0))


class FrontLinePlayerPayloadTests(unittest.TestCase):
    def test_payload_reports_level_and_xp_to_next_level(self):
        service = FrontLineWorldService.__new__(FrontLineWorldService)
        fighter = Fighter("Герой", level=2)
        fighter.xp = 35
        player = SimpleNamespace(
            character_id=1, x=0.0, y=0.0, fighter=fighter, facing=0.0, windup=0.0,
            windup_total=0.0, swing_id=0, backswing=0.0, attack_target=None, windup_target=None,
            dash=None, dash_cooldown=0.0, move_speed=120.0, carry_multiplier=1.0, harvest_target=None,
        )

        payload = service._player_payload(player)

        self.assertEqual((payload["level"], payload["xp"], payload["xp_to_next"]), (2, 35, 240))


class FrontLineBridgeDetourTests(unittest.TestCase):
    """Герой стоит на узком проходе: крысы обходят его по свободному коридору, а не толпятся перед ним."""

    def test_rats_go_around_a_hero_blocking_a_bridge_and_both_sides_attack(self):
        walkable = set()
        for x in range(24):
            walkable.add((x, 10))
        for x in range(21):
            walkable.add((x, 14))
        for y in range(10, 15):
            walkable.add((0, y))
            walkable.add((20, y))
        service = FrontLineMobCrowdTests()._service()
        service._game_started = service._waves_unlocked = True
        service._tavern_hp = 10 ** 6
        service._map_width = service._map_height = 24
        service._tavern = SimpleNamespace(x=0.0, y=0.0)
        service._objective = SimpleNamespace(x=0.0, y=0.0)
        service._terrain_blocked = lambda x, y: (int(x // world_map.TILE), int(y // world_map.TILE)) not in walkable
        service._emit_label = lambda *a, **k: None
        service._seq = 0
        strikes = []
        service._mob_strike = lambda mob, player: strikes.append((service._tick, mob.id))
        service._tick = 0
        hero = SimpleNamespace(
            x=10.5 * world_map.TILE, y=10.5 * world_map.TILE, alive=True, character_id=1, user_id=1,
            fighter=Fighter("Герой", level=1), facing=0.0, windup=0.0, windup_total=0.0, swing_id=0, backswing=0.0,
            attack_target=None, windup_target=None, dash=None, dash_cooldown=0.0, move_speed=120.0,
            carry_multiplier=1.0, harvest_target=None, events=[], dirty=False, flush_timer=0.0,
        )
        service._players = {1: hero}
        for index, cell_x in enumerate((5, 4, 3)):
            x, y = (cell_x + 0.5) * world_map.TILE, 10.5 * world_map.TILE
            service._mobs[str(index)] = SimpleNamespace(
                id=str(index), alive=True, state="idle", target=None, front_line_target="characters",
                x=x, y=y, home_x=x, home_y=y, facing=0.0, move_speed=100.0, windup=0.0, windup_total=0.0,
                backswing=0.0, windup_time=0.5, backswing_time=0.5, chase_route=[], chase_replan_timer=0.0,
                fighter=Fighter("Крыса", level=1), is_boss=False, respawn_timer=0,
            )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=1):
            for tick in range(1200):
                service._tick = tick
                service._update_mobs(1 / 30)
        late = {mob_id for tick, mob_id in strikes if tick >= 900}
        self.assertGreaterEqual(len(late), 2, "вторая крыса обходит героя и бьёт с другой стороны")


class FrontLineRingTests(unittest.TestCase):
    """Крысы окружают героя кольцом, а не стоят одной кучей с одной стороны."""

    def test_chasing_rats_surround_a_standing_hero_in_a_ring(self):
        service = FrontLineMobCrowdTests()._service()
        service._game_started = service._waves_unlocked = True
        service._tavern_hp = 10 ** 6
        service._map_width = service._map_height = 64
        service._tavern = SimpleNamespace(x=0.0, y=0.0)
        service._objective = SimpleNamespace(x=0.0, y=0.0)
        service._terrain_blocked = lambda x, y: False
        service._emit_label = lambda *a, **k: None
        service._mob_strike = lambda mob, player: None
        service._seq = 0
        hero = SimpleNamespace(
            x=600.0, y=600.0, alive=True, character_id=1, user_id=1, fighter=Fighter("Герой", level=1), facing=0.0,
            windup=0.0, windup_total=0.0, swing_id=0, backswing=0.0, attack_target=None, windup_target=None,
            dash=None, dash_cooldown=0.0, move_speed=120.0, carry_multiplier=1.0, harvest_target=None,
            events=[], dirty=False, flush_timer=0.0,
        )
        service._players = {1: hero}
        for index in range(12):
            angle = index * 0.5  # крысы идут с одной стороны, но в разных точках
            x, y = 600.0 + 260.0 * math.cos(angle), 600.0 + 260.0 * math.sin(angle)
            service._mobs[str(index)] = SimpleNamespace(
                id=str(index), alive=True, state="idle", target=None, front_line_target="characters",
                x=x, y=y, home_x=x, home_y=y, facing=0.0, move_speed=100.0, windup=0.0, windup_total=0.0,
                backswing=0.0, windup_time=0.5, backswing_time=0.5, chase_route=[], chase_replan_timer=0.0,
                fighter=Fighter("Крыса", level=1), is_boss=False, respawn_timer=0, is_boss_flag=False,
            )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=1):
            for _ in range(900):
                service._update_mobs(1 / 30)
        close = sorted(
            math.atan2(mob.y - hero.y, mob.x - hero.x)
            for mob in service._mobs.values()
            if math.hypot(mob.x - hero.x, mob.y - hero.y) - 10.0 <= 32.0
        )
        # Тела не накладываются: вокруг героя помещается примерно пять-шесть крыс.
        self.assertGreaterEqual(len(close), 5, "в зоне удара стоят хотя бы пять крыс")
        gaps = [b - a for a, b in zip(close, close[1:])] + [close[0] + 2 * math.pi - close[-1]]
        self.assertLessEqual(max(gaps), math.radians(90) + 0.05, "крысы окружают героя, а не стоят с одной стороны")


class FrontLineRangeTests(unittest.TestCase):
    """Дальность в единицах (1 тайл = 100 ед.), расстояние до края тела и снаряды лучника."""

    def _service(self):
        service = FrontLineMobCrowdTests()._service()
        service._terrain_blocked = lambda x, y: False
        service._clock = lambda: 0.0
        service._seq = 0
        service._projectiles = []
        return service

    def _hero(self, profession, x=0.0, y=0.0):
        fighter = Fighter("Герой", level=2, profession_type=profession)
        return SimpleNamespace(
            x=x, y=y, facing=0.0, fighter=fighter, windup=0.0, windup_total=0.0, windup_target=None,
            swing_id=0, backswing=0.0, attack_target=None, dash=None, dash_cooldown=0.0, events=[],
            dirty=False, character_id=1, user_id=1,
        )

    def _mob(self, x, y):
        return SimpleNamespace(
            id="m1", alive=True, x=x, y=y, is_boss=False, fighter=Fighter("Крыса", level=1), state="idle",
        )

    def test_hero_range_units_by_class(self):
        self.assertEqual(front_line_combat.hero_attack_range_units(self._hero("warrior").fighter), 100)
        self.assertEqual(front_line_combat.hero_attack_range_units(self._hero("archer").fighter), 500)
        self.assertEqual(front_line_combat.hero_attack_range_units(self._hero("mage").fighter), 500)
        self.assertAlmostEqual(front_line_combat.range_units_to_px(500), 160.0)

    def test_projectile_speed_and_blast_radius_by_class(self):
        self.assertAlmostEqual(front_line_combat.projectile_speed_px("archer"), 192.0)
        self.assertAlmostEqual(front_line_combat.projectile_speed_px("mage"), 160.0)
        self.assertAlmostEqual(front_line_combat.area_radius_px(), 16.0)

    def test_class_base_windup_for_archer_and_mage_is_longer_than_for_warrior(self):
        service = self._service()
        warrior = self._hero("warrior", x=0.0, y=0.0)
        archer = self._hero("archer", x=0.0, y=0.0)
        mage = self._hero("mage", x=0.0, y=0.0)
        # Разница базовых замахов классов уменьшена вдвое вместе с замахом (FRONT_LINE_WINDUP_SCALE = 0.5).
        self.assertAlmostEqual(service._player_windup_time(archer) - service._player_windup_time(warrior), 0.2, places=6)
        self.assertAlmostEqual(service._player_windup_time(mage) - service._player_windup_time(warrior), 0.7, places=6)

    def test_shots_follow_the_attack_cycle_without_spam(self):
        service = self._service()
        archer = self._hero("archer", x=100.0, y=100.0)
        archer.fighter.stats["intuition"] = 60
        archer.fighter.stats["agility"] = 60
        mob = self._mob(200.0, 100.0)
        archer.attack_target = mob
        service._player_attack_range_px = lambda player: 10000.0
        service._player_attack_distance = lambda player, target: 100.0
        shots = []
        service._deliver_player_strike = lambda player, target: shots.append(target)
        for _ in range(120):  # две секунды при 60 кадрах
            service._update_player_attack(archer, 1 / 60)
        cycle = service._player_windup_time(archer) + service._player_backswing_time(archer)
        # Допуск в один выстрел; 1e-9 — погрешность float при делении на цикл.
        self.assertLessEqual(abs(len(shots) - 2.0 / cycle), 1.0 + 1e-9)

    def test_archer_shot_sends_projectile_event_at_the_moment_of_the_shot(self):
        service = self._service()
        archer = self._hero("archer", x=100.0, y=100.0)
        mob = self._mob(300.0, 100.0)
        service._deliver_player_strike(archer, mob)
        event = archer.events[-1]
        self.assertEqual(event["type"], "projectile")
        self.assertEqual(event["id"], service._projectile_sequence)
        self.assertEqual(event["kind"], "arrow")
        self.assertEqual(event["target"], "m1")
        self.assertEqual(event["from"], [100.0, 100.0])
        self.assertGreater(event["speed"], 0.0)

    def test_projectile_chases_a_target_that_moved_away(self):
        service = self._service()
        archer = self._hero("archer", x=0.0, y=0.0)
        archer.events = []
        mob = self._mob(150.0, 0.0)
        service._players = {1: archer}
        strikes = []
        service._strike_mob = lambda owner, target: strikes.append(target.id)
        service._deliver_player_strike(archer, mob)
        mob.x = 240.0
        for _ in range(60):
            service._update_projectiles(0.05)
        self.assertEqual(strikes, ["m1"], "стрела догоняет цель, которая ушла из её первоначальной точки")
        self.assertEqual(service._projectile_list(), [])

    def test_hero_turns_toward_the_target_before_the_swing_starts(self):
        service = self._service()
        warrior = self._hero("warrior", x=0.0, y=0.0)
        mob = self._mob(0.0, -100.0)  # 90° от взгляда героя
        self.assertFalse(service._begin_swing_facing(warrior, mob, 0.05))
        turned = 0
        while not service._begin_swing_facing(warrior, mob, 0.05) and turned < 100:
            turned += 1
        self.assertLess(turned, 100)
        self.assertLess(abs(warrior.turn_angle - (-math.pi / 2)), 1e-6)

    def test_armor_reduces_damage_by_percent_and_never_below_one(self):
        self.assertEqual(front_line_combat.damage_after_armor(0, 32), 0)
        self.assertEqual(front_line_combat.damage_after_armor(10, 32), 3)
        self.assertEqual(front_line_combat.damage_after_armor(1, 1000), 1)

    def test_hero_move_speed_is_scaled_for_front_line(self):
        service = self._service()
        archer = self._hero("archer", x=0.0, y=0.0)
        archer.carry_multiplier = 1.0
        base = front_line_combat.HERO_MOVE_SPEED_SCALE
        from combat import world_stats as stats
        self.assertAlmostEqual(service._player_move_speed(archer), stats.get_move_speed(archer.fighter, 1.0) * base)

    def test_order_cancels_windup_without_backswing_or_miss(self):
        service = self._service()
        archer = self._hero("archer", x=100.0, y=100.0)
        archer.events = []
        archer.windup = 0.3
        archer.windup_total = 0.5
        archer.windup_target = self._mob(300.0, 100.0)
        service._cancel_attack(archer)
        self.assertEqual((archer.windup, archer.windup_total, archer.backswing), (0.0, 0.0, 0.0))
        self.assertIsNone(archer.windup_target)

    def test_front_line_target_leaving_range_keeps_target_without_miss_or_backswing(self):
        service = self._service()
        warrior = self._hero("warrior", x=100.0, y=100.0)
        warrior.events = []
        mob = self._mob(300.0, 100.0)
        warrior.attack_target = mob
        warrior.windup = 0.01
        warrior.windup_total = 0.5
        warrior.windup_target = mob
        service._player_attack_range_px = lambda player: 32.0
        service._player_attack_distance = lambda player, target: 200.0
        service._update_player_attack(warrior, 0.05)
        self.assertIs(warrior.attack_target, mob)
        self.assertEqual(warrior.backswing, 0.0)
        self.assertFalse(any(event.get("type") == "label" for event in warrior.events))

    def test_hold_position_refuses_steps_but_not_the_attack_range_check(self):
        service = self._service()
        service._character_draft_active = False
        player = SimpleNamespace(
            x=200.0, y=200.0, move_speed=160.0, windup=0.0, backswing=0.0, dash=None, facing=0.0, hold=True,
        )
        self.assertFalse(service._accept_move(player, 210.0, 200.0, 1.0))
        player.hold = False
        self.assertTrue(service._accept_move(player, 210.0, 200.0, 1.0))

    def test_new_order_id_cancels_windup_but_repeating_the_order_keeps_it(self):
        service = self._service()
        archer = self._hero("archer", x=100.0, y=100.0)
        archer.harvest_target = None
        archer.harvest_progress = 0.0
        archer.order_seq = 1
        mob = self._mob(300.0, 100.0)
        service._mobs = {"m1": mob}
        service._crystals = {}
        archer.windup = 0.3
        archer.windup_total = 0.5
        archer.windup_target = mob
        service._apply_command(archer, {"attack_target": "m1", "order_id": 1})
        self.assertEqual(archer.windup, 0.3)
        service._apply_command(archer, {"attack_target": None, "order_id": 2})
        self.assertEqual(archer.windup, 0.0)
        self.assertIsNone(archer.windup_target)

    def test_idle_hero_does_not_attack_without_an_order(self):
        # Автоатака выключена: моб в дальности без приказа герой не бьёт.
        service = self._service()
        warrior = self._hero("warrior", x=100.0, y=100.0)
        mob = self._mob(120.0, 100.0)
        service._mobs = {"m1": mob}
        service._player_attack_distance = lambda player, target: 20.0
        service._player_attack_range_px = lambda player: 32.0
        warrior.attack_target = None
        warrior.hold = False
        service._update_player_attack(warrior, 0.01)
        self.assertIsNone(warrior.windup_target)

    def test_hero_attacks_the_ordered_target(self):
        service = self._service()
        warrior = self._hero("warrior", x=100.0, y=100.0)
        mob = self._mob(120.0, 100.0)
        service._mobs = {"m1": mob}
        service._player_attack_distance = lambda player, target: 20.0
        service._player_attack_range_px = lambda player: 32.0
        warrior.attack_target = mob
        warrior.hold = False
        service._update_player_attack(warrior, 0.01)
        self.assertIs(warrior.windup_target, mob)

    def test_player_stands_still_while_winding_up(self):
        service = self._service()
        service._character_draft_active = False
        player = SimpleNamespace(
            x=200.0, y=200.0, move_speed=160.0, windup=0.4, backswing=0.0, dash=None, facing=0.0,
        )
        self.assertFalse(service._accept_move(player, 210.0, 200.0, 1.0))
        self.assertEqual((player.x, player.y), (200.0, 200.0))
        player.windup = 0.0
        self.assertTrue(service._accept_move(player, 210.0, 200.0, 1.0))
        self.assertEqual((player.x, player.y), (210.0, 200.0))

    def test_mob_base_damage_adds_to_strength_bonus(self):
        from combat import world_stats
        mob = self._mob(0.0, 0.0)
        mob.fighter.stats["strength"] = 1
        mob.fighter.innate_damage_range = (3, 5)
        # Без броска — максимум: 2 за силу плюс максимум базового урона
        self.assertEqual(world_stats.get_world_base_damage(mob.fighter), 2 + 5)

    def test_mob_range_comes_from_its_kind_settings_or_default_to_one_tile(self):
        service = self._service()
        mob = self._mob(0.0, 0.0)
        self.assertAlmostEqual(service._mob_attack_range_px(mob), 32.0)
        mob.attack_range_units = 200.0
        self.assertAlmostEqual(service._mob_attack_range_px(mob), 64.0)

    def test_edited_mob_file_applies_to_next_spawn_without_restart(self):
        service = self._service()
        service._nearest_free = lambda x, y: (x, y)
        service._mob_profile_cache = {}
        service._mob_profile_mtime = None
        service._spawn_sequence = 0
        service._mobs = {}
        kind = "imp_vanilla"
        with tempfile.TemporaryDirectory() as folder:
            path = mob_modes.mode_file("front_line", folder)
            with patch.object(mob_modes, "MODES_DIR", Path(folder)):
                settings = mob_modes.default_settings(kind)
                settings["move_speed"] = 100.0
                mob_modes.save_mob_settings("front_line", kind, settings, folder)
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
                service._spawn_mob({"x": 3, "y": 3}, {"mob_key": kind, "level": 1})

                settings["move_speed"] = 150.0
                mob_modes.save_mob_settings("front_line", kind, settings, folder)
                os.utime(path, ns=(2_000_000_000, 2_000_000_000))
                service._spawn_mob({"x": 4, "y": 4}, {"mob_key": kind, "level": 1})

        first, second = list(service._mobs.values())
        self.assertEqual(first.move_speed, 100.0)
        self.assertEqual(second.move_speed, 150.0)

    def test_warrior_cannot_strike_from_156px_but_archer_can(self):
        service = self._service()
        mob = self._mob(176.0, 0.0)  # центр в 176 px, край тела в 156 px
        warrior, archer = self._hero("warrior"), self._hero("archer")
        self.assertAlmostEqual(service._player_attack_distance(warrior, mob), 156.0)
        self.assertGreater(service._player_attack_distance(warrior, mob), service._player_attack_range_px(warrior))
        self.assertLessEqual(service._player_attack_distance(archer, mob), service._player_attack_range_px(archer))

    def test_archer_shot_deals_damage_only_after_flight_time(self):
        service = self._service()
        archer = self._hero("archer")
        mob = self._mob(150.0, 0.0)
        service._players = {1: archer}
        strikes = []
        service._strike_mob = lambda owner, target: strikes.append(target.id)
        archer.attack_target = mob
        for _ in range(40):
            service._update_player_attack(archer, 0.1)
            if service._projectile_list():
                break
        self.assertEqual(len(service._projectile_list()), 1, "выстрел лучника создаёт снаряд")
        self.assertEqual(strikes, [], "урон не приходит в момент выстрела")
        for _ in range(20):  # стрела лучника 192 px/с: до цели 130 px, около 0,7 с
            service._update_projectiles(0.05)
        self.assertEqual(strikes, ["m1"], "урон приходит, когда стрела долетела")
        self.assertEqual(service._projectile_list(), [])

    def test_projectile_disappears_when_target_dies_in_flight(self):
        service = self._service()
        archer = self._hero("archer")
        mob = self._mob(150.0, 0.0)
        service._players = {1: archer}
        strikes = []
        service._strike_mob = lambda owner, target: strikes.append(target.id)
        service._projectile_list().append({
            "id": 1, "owner": archer, "target": mob, "kind": "arrow", "from": (0.0, 0.0),
            "pos": (0.0, 0.0), "last": (150.0, 0.0), "speed": 384.0, "age": 0.0,
        })
        mob.alive = False
        service._update_projectiles(0.5)
        self.assertEqual(strikes, [])
        self.assertEqual(service._projectile_list(), [])

    def test_mage_orb_hits_every_mob_inside_the_area_only(self):
        service = self._service()
        mage = self._hero("mage")
        centre = self._mob(150.0, 0.0)
        near = self._mob(150.0 + 20.0, 0.0)  # край тела в 4 px от центра взрыва, внутри радиуса 32 px
        far = self._mob(150.0 + 80.0, 0.0)   # край тела в 64 px, снаружи
        near.id, far.id = "m2", "m3"
        service._mobs = {"m1": centre, "m2": near, "m3": far}
        service._players = {1: mage}
        strikes = []
        service._strike_mob = lambda owner, target: strikes.append(target.id)
        service._projectile_list().append({
            "id": 1, "owner": mage, "target": centre, "kind": "orb", "from": (0.0, 0.0),
            "pos": (140.0, 0.0), "last": (150.0, 0.0), "speed": 384.0, "age": 0.0,
        })
        service._update_projectiles(0.05)
        self.assertEqual(sorted(strikes), ["m1", "m2"])

    def test_mage_orb_still_explodes_when_its_target_died_in_flight(self):
        service = self._service()
        mage = self._hero("mage")
        centre = self._mob(150.0, 0.0)
        centre.alive = False
        neighbour = self._mob(160.0, 0.0)
        neighbour.id = "m2"
        service._mobs = {"m1": centre, "m2": neighbour}
        service._players = {1: mage}
        strikes = []
        service._strike_mob = lambda owner, target: strikes.append(target.id)
        service._projectile_list().append({
            "id": 1, "owner": mage, "target": centre, "kind": "orb", "from": (0.0, 0.0),
            "pos": (140.0, 0.0), "last": (150.0, 0.0), "speed": 384.0, "age": 0.0,
        })
        service._update_projectiles(0.05)
        self.assertEqual(strikes, ["m2"])

    def test_damage_numbers_are_whole_values(self):
        service = self._service()
        service._seq = 0
        hero = SimpleNamespace(events=[])
        service._emit_number(hero, 2.0, False, 0.0, 0.0)
        service._emit_number(hero, 4.6, True, 0.0, 0.0)
        self.assertEqual([event["value"] for event in hero.events], [2, 5])
        self.assertTrue(all(isinstance(event["value"], int) for event in hero.events))

    def test_archer_payload_reports_range_units_and_projectiles(self):
        service = FrontLineWorldService.__new__(FrontLineWorldService)
        service._seq = 0
        service._projectiles = []
        archer = self._hero("archer", 10.0, 20.0)
        archer.fighter.level = 2
        archer.fighter.xp = 35
        archer.facing = 0.0
        archer.move_speed = 120.0
        archer.carry_multiplier = 1.0
        archer.harvest_target = None
        archer.attack_target = None
        archer.windup = 0.0
        archer.windup_total = 0.0
        archer.backswing = 0.0
        archer.trails = []
        service._projectiles.append({
            "id": 1, "owner": archer, "target": self._mob(150.0, 20.0), "kind": "arrow", "from": (10.0, 20.0),
            "pos": (40.0, 20.0), "last": (150.0, 20.0), "speed": 384.0, "age": 0.0,
        })
        payload = service._player_payload(archer)
        self.assertEqual(payload["attack_range"], 500)
        self.assertEqual(payload["projectile"], "arrow")
        self.assertAlmostEqual(payload["reach"], 160.0)
        self.assertEqual(payload["projectiles"][0]["target"], "m1")


class FrontLineSessionProgressTests(unittest.TestCase):
    class _Database:
        def __init__(self, character=None):
            self.character = character
            self.saved = []
            self.currency_sets = []

        def get_character(self, user_id, character_id):
            return self.character

        def save_world_progression(self, *args):
            self.saved.append(args)

        def set_world_currency(self, *args):
            self.currency_sets.append(args)

    def _service(self, database):
        service = object.__new__(FrontLineWorldService)
        service._database = database
        service._players = {}
        service._seq = 0
        service._round_stats = {}
        service._round_mobs_killed = 0
        service._match_summary = None
        service._match_result = ""
        service._session_wallets = {}
        service._tavern_hp = 0
        service._tavern_max_hp = 0
        service._game_started_at = 0.0
        service._clock = lambda: 0.0
        return service

    def test_mob_xp_stays_in_session_and_is_not_saved(self):
        database = self._Database()
        service = self._service(database)
        player = SimpleNamespace(user_id=1, fighter=Fighter("Игрок", level=1), events=[])
        service._players = {7: player}
        with patch("front_line.server.world.presence"):
            service._grant_mob_xp(1, 7, 10)
        self.assertEqual(player.fighter.xp, 10)
        self.assertEqual(database.saved, [])
        self.assertEqual(player.events[-1]["character"]["xp"], 10)

    def test_session_wallet_is_restored_when_match_ends(self):
        database = self._Database()
        service = self._service(database)
        service._session_wallets = {7: 1}
        player = SimpleNamespace(user_id=1, fighter=Fighter("Игрок", level=1), events=[])
        service._players = {7: player}
        service._finish_match("victory")
        self.assertEqual(database.currency_sets, [(1, 7, 0, 1, 0)])
        self.assertEqual(service._session_wallets, {})
        self.assertEqual(player.events[-1]["type"], "currency")

    def test_draft_starts_each_session_at_first_level_with_no_xp(self):
        stored = {"id": 7, "name": "Top", "level": 11, "xp": 985, "stats": {}, "stat_points": 0}
        database = self._Database(character=stored)
        service = self._service(database)
        player = SimpleNamespace(
            user_id=1, fighter=None, events=[], x=0, y=0, move_path=[], attack_target=None,
            harvest_target=None, dirty=True,
        )
        service._players = {7: player}
        service._character_draft_choices = {}
        service._character_draft_results = {}
        service._character_draft_active = True
        service._hero_spawns = []
        service._rng = random.Random(1)
        service._clock = lambda: 0.0
        service._wave_draft_seconds = 30
        service._nearest_free = lambda x, y: (x, y)
        with patch.object(service, "_refresh_carry"), patch.object(service, "_configure_mob_spawners"), patch.object(service, "_tavern_flow"):
            service._complete_character_draft()
        self.assertEqual((player.fighter.level, player.fighter.xp), (1, 0))
        self.assertEqual(service._character_draft_results[7]["xp"], 0)
        self.assertEqual([saved[2:4] for saved in database.saved], [(1, 0)])
        self.assertEqual(database.currency_sets, [(1, 7, 0, 1, 0)])

    def test_match_end_resets_level_and_stats_to_creation_values(self):
        database = self._Database()
        service = self._service(database)
        service._players = {7: SimpleNamespace(user_id=1, fighter=None, events=[])}
        service._match_result = ""
        service._finish_match("victory")
        service._finish_match("victory")
        self.assertEqual(len(database.saved), 1)
        user_id, character_id, level, xp, stats, stat_points, max_hp = database.saved[0]
        self.assertEqual((user_id, character_id, level, xp), (1, 7, 1, 0))
        self.assertEqual(stats, creation_stats()[0])
        self.assertEqual(stat_points, creation_stats()[1])
        self.assertEqual(max_hp, calculate_max_hp(1, stats["endurance"]))


class FrontLineRoundStatsTests(unittest.TestCase):
    def _service(self):
        service = object.__new__(FrontLineWorldService)
        service._players = {}
        service._round_stats = {}
        service._round_mobs_killed = 0
        service._match_summary = None
        service._match_result = ""
        service._tavern_hp = 80
        service._tavern_max_hp = 100
        service._game_started_at = 10.0
        service._clock = lambda: 70.0
        service._session_wallets = {}
        return service

    def test_summary_counts_damage_shares_and_round_duration(self):
        service = self._service()
        service._round_entry(1, "Лучник")
        service._round_entry(2, "Маг")
        archer = SimpleNamespace(character_id=1, user_id=1)
        mage = SimpleNamespace(character_id=2, user_id=2)
        mob = SimpleNamespace(fighter=Fighter("Крыса", level=1), damage_by={})
        mob.fighter.hp = 100
        service._damage_mob(mob, 30, archer)
        service._damage_mob(mob, 10, mage)
        service._finish_match("lost")
        summary = service._match_summary
        self.assertEqual(summary["result"], "lost")
        self.assertEqual(summary["duration_seconds"], 60)
        self.assertEqual(summary["total_damage"], 40)
        self.assertEqual((summary["tavern_hp"], summary["tavern_max_hp"]), (80, 100))
        first, second = summary["players"]
        self.assertEqual((first["name"], first["damage_dealt"], first["damage_share"]), ("Лучник", 30, 75.0))
        self.assertEqual((second["name"], second["damage_dealt"], second["damage_share"]), ("Маг", 10, 25.0))

    def test_damage_taken_and_deaths_are_counted_per_hero(self):
        service = self._service()
        service._round_entry(1, "Воин")["damage_taken"] += 12
        service._round_entry(1)["deaths"] += 1
        entry = service._round_entry(1)
        self.assertEqual((entry["name"], entry["damage_taken"], entry["deaths"]), ("Воин", 12, 1))


class FrontLineMobBodyTests(unittest.TestCase):
    def _service(self):
        service = object.__new__(FrontLineWorldService)
        service._mobs = {}
        service._players = {}
        return service

    def _mob(self, x, y):
        return SimpleNamespace(alive=True, x=float(x), y=float(y), is_boss=False)

    def test_mob_cannot_step_into_another_mob_body(self):
        service = self._service()
        stays = self._mob(0, 0)
        stepping = self._mob(60, 0)
        service._mobs = {1: stays, 2: stepping}
        self.assertTrue(service._mob_blocked_by_players(25.0, 0.0, stepping))

    def test_mob_already_touching_another_may_move_apart(self):
        service = self._service()
        left = self._mob(0, 0)
        right = self._mob(20, 0)
        service._mobs = {1: left, 2: right}
        self.assertFalse(service._mob_blocked_by_players(22.0, 0.0, right))

    def test_mob_cannot_step_onto_hero_body(self):
        service = self._service()
        service._players = {7: SimpleNamespace(x=100.0, y=100.0)}
        mob = self._mob(60, 100)
        service._mobs = {1: mob}
        self.assertTrue(service._mob_blocked_by_players(100.0, 100.0, mob))


class FrontLineMobStyleTests(unittest.TestCase):
    """Характер боя моба: стрелок бьёт стрелой, маг — сферой с уроном по области от точки попадания."""

    def _service(self):
        service = FrontLineRangeTests()._service()
        service._rng = random.Random(1)
        service._round_stats = {}
        service._round_mobs_killed = 0
        return service

    def _hero(self, character_id, x, y):
        return SimpleNamespace(
            x=float(x), y=float(y), alive=True, character_id=character_id, user_id=character_id,
            fighter=Fighter("Герой", level=1), facing=0.0, dirty=False, events=[],
        )

    def _mob(self, style, x, y):
        return SimpleNamespace(
            id="m", x=float(x), y=float(y), alive=True, fighter=Fighter("Лук", level=1),
            log_names={"nom": "Лук", "dat": "Лука", "gen": "Лука"}, attack_style=style,
            area_radius_units=50, facing=0.0, is_boss=False,
        )

    def test_archer_mob_shoots_arrow_and_damage_lands_on_arrival(self):
        service = self._service()
        mob = self._mob("archer", 300, 0)
        hero = self._hero(1, 0, 0)
        service._players = {1: hero}
        service._mobs = {"m": mob}
        with patch("front_line.server.world.front_line_combat.resolve_melee_attack",
                   return_value={"outcome": "hit", "damage": 10, "critical": False}):
            service._mob_strike(mob, hero)
            self.assertEqual(len(service._projectiles), 1)
            self.assertEqual(hero.fighter.hp, hero.fighter.max_hp, "стрела ещё летит, урона нет")
            for _ in range(30):
                service._update_projectiles(0.1)
        self.assertEqual(service._projectiles, [])
        self.assertLess(hero.fighter.hp, hero.fighter.max_hp)

    def test_mage_mob_sphere_damages_heroes_near_the_impact_only(self):
        service = self._service()
        mob = self._mob("mage", 300, 0)
        target = self._hero(1, 0, 0)
        near = self._hero(2, 0, 10)
        far = self._hero(3, 200, 0)
        service._players = {1: target, 2: near, 3: far}
        service._mobs = {"m": mob}
        with patch("front_line.server.world.front_line_combat.resolve_melee_attack",
                   return_value={"outcome": "hit", "damage": 10, "critical": False}):
            service._mob_strike(mob, target)
            for _ in range(40):
                service._update_projectiles(0.1)
        self.assertLess(target.fighter.hp, target.fighter.max_hp)
        self.assertLess(near.fighter.hp, near.fighter.max_hp, "рядом с точкой попадания — тоже урон")
        self.assertEqual(far.fighter.hp, far.fighter.max_hp, "далеко от взрыва — урона нет")

    def test_mob_style_and_area_radius_are_validated_for_front_line(self):
        base = mob_modes.default_settings("imp_vanilla")
        settings = mob_modes.validate_settings(
            {**base, "attack_style": "mage", "area_radius": 80, "damage_min": 1, "damage_max": 6, "level": 1},
            mode="front_line",
        )
        self.assertEqual((settings["attack_style"], settings["area_radius"]), ("mage", 80))
        with self.assertRaisesRegex(ValueError, "Характер боя"):
            mob_modes.validate_settings(
                {**base, "attack_style": "knight", "damage_min": 1, "damage_max": 6, "level": 1},
                mode="front_line",
            )


class FrontLineStatAllocationTests(unittest.TestCase):
    def test_allocate_stat_spends_a_session_point_inside_the_world(self):
        service = FrontLineRangeTests()._service()
        hero = SimpleNamespace(
            x=0.0, y=0.0, alive=True, character_id=1, user_id=1, fighter=Fighter("Герой", level=2),
            events=[], attack_target=None, hold=False, order_seq=0, harvest_target=None, harvest_progress=0.0,
            dash=None, dirty=False,
        )
        hero.fighter.stat_points = 2
        before = hero.fighter.stats["strength"]
        service._apply_command(hero, {"allocate_stats": ["strength", "endurance", "bogus"]})
        self.assertEqual(hero.fighter.stats["strength"], before + 1)
        self.assertEqual(hero.fighter.stat_points, 1, "выносливость и неизвестная характеристика очков не тратят")
        self.assertEqual(hero.events[-1]["character"]["stat_points"], 1)


class FrontLineSnapshotCompactionTests(unittest.TestCase):
    def test_static_mob_fields_are_sent_once_then_only_dynamic_fields(self):
        service = FrontLineRangeTests()._service()
        player = SimpleNamespace(known_mobs=set())
        entry = {"id": "m1", "x": 1.0, "y": 2.0, "hp": 5, "name": "Крыса", "stats": {"strength": 3}}
        first = service._compact_mobs(player, [dict(entry)])
        self.assertEqual(first[0]["name"], "Крыса")
        second = service._compact_mobs(player, [{**entry, "x": 9.0}])
        self.assertTrue(second[0]["compact"])
        self.assertNotIn("name", second[0])
        self.assertEqual(second[0]["x"], 9.0)


class FrontLineSquadTests(unittest.TestCase):
    """Отряды волны: от минимума к максимуму, последнее отправление забирает остаток."""

    def _run(self, count, squad_min, squad_max):
        from front_line.server.world import planned_squad_ticks, squad_size
        planned = planned_squad_ticks(count, squad_min, squad_max)
        remaining, tick, sizes = count, 0, []
        while remaining > 0:
            size = squad_size(tick, planned, squad_min, squad_max, remaining)
            sizes.append(size)
            remaining -= size
            tick += 1
        return sizes

    def test_squads_ramp_from_min_to_max_and_last_tick_takes_the_rest(self):
        sizes = self._run(100, 2, 8)
        self.assertEqual(sum(sizes), 100)
        self.assertEqual(sizes[0], 2)
        self.assertEqual(sizes[-1], 9)  # 8 плюс остаток 1: всё оставшееся уходит в последнем отправлении
        self.assertTrue(all(a <= b for a, b in zip(sizes[:19], sizes[1:20])))
        self.assertTrue(20 <= len(sizes) <= 22)

    def test_fixed_squad_sends_remainder_in_the_last_tick(self):
        sizes = self._run(100, 6, 6)
        self.assertEqual(sizes[:-1], [6] * 15)
        self.assertEqual(sizes[-1], 10)  # после 15 отрядов осталось 10: 6 плюс 4

    def test_single_mob_squads_keep_the_old_one_by_one_spawn(self):
        self.assertEqual(self._run(5, 1, 1), [1] * 5)


class FrontLineWorldTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.admin = self.database.register("front-line-admin", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'admin' WHERE id = %s", (self.admin["id"],))
        self.character = self.database.create_character(self.admin["id"], "Драфт")
        self.clock = Clock()
        self.map_body = {
            "name": "Маршрут 1",
            "mode": "front_line",
            "map_w": 16,
            "map_h": 16,
            "cells": [{"layer": "ground", "x": 0, "y": 0, "key": GROUND}],
            "mobs": [],
            "spawns": [
                {"x": 1, "y": 1, "type": "hero"},
                {"x": 2, "y": 1, "type": "hero"},
                {
                    "x": 3,
                    "y": 3,
                    "type": "mob",
                    "settings": {
                        "waves": [{
                            "mob_key": "imp_vanilla",
                            "level": 4,
                            "count": 2,
                            "interval_seconds": 1,
                            "reward_xp": 75,
                            "reward_copper": 38,
                        }],
                    },
                },
            ],
        }

    def tearDown(self):
        world_map.apply_live_terrain(None, None)
        drop_test_database(self.database)

    def _service(self, start_wait_seconds=1):
        # Сценарии этого класса рассчитаны на 60-секундные драфт и подготовку к волне (в игре теперь по 10 с).
        service = FrontLineWorldService(
            self.database,
            ItemsDatabase(self.database),
            start_wait_seconds=start_wait_seconds,
            character_draft_seconds=60,
            wave_draft_seconds=60,
            clock=self.clock,
            rng=random.Random(3),
        )
        service._tick_player = lambda _player, _dt: None
        return service

    def _waiting_player(self, service):
        return service._load_player(self.admin["id"], self.character["id"], 0, 0)

    def test_spawn_uses_saved_front_line_mob_stats_and_hp_mp(self):
        service = self._service()
        service._nearest_free = lambda x, y: (x, y)
        settings = mob_modes.default_settings("imp_vanilla")
        settings["stats"] = {
            "strength": 101,
            "agility": 202,
            "intuition": 303,
            "wisdom": 404,
            "intellect": 505,
            "endurance": 606,
        }
        settings["max_hp"] = 707
        settings["max_mp"] = 808

        with patch(
            "front_line.server.world.mob_modes.load_mob_settings",
            return_value=settings,
        ) as load_settings:
            service._spawn_mob(
                {"x": 3, "y": 3},
                {"mob_key": "imp_vanilla", "level": 4},
            )

        load_settings.assert_called_once_with("front_line", "imp_vanilla")
        mob = next(iter(service._mobs.values()))
        self.assertEqual(mob.fighter.stats, settings["stats"])
        self.assertEqual(
            (mob.fighter.hp, mob.fighter.max_hp, mob.fighter.mp, mob.fighter.max_mp),
            (707, 707, 808, 808),
        )

    def test_spawn_uses_palette_mob_key_and_profile(self):
        service = self._service()
        service._nearest_free = lambda x, y: (x, y)
        kind = "mob|goblin sprite-pack|g1"
        settings = mob_modes.default_settings(kind)

        with patch(
            "front_line.server.world.mob_modes.load_mob_settings",
            return_value=settings,
        ) as load_settings:
            service._spawn_mob({"x": 3, "y": 3}, {"mob_key": kind, "level": 1})

        load_settings.assert_called_once_with("front_line", kind)
        mob = next(iter(service._mobs.values()))
        self.assertEqual((mob.kind, mob.name), (kind, "Гоблин 1"))

    def test_spawn_rejects_unknown_key_instead_of_substituting_an_imp(self):
        service = self._service()

        with self.assertRaisesRegex(ValueError, "отсутствует в боевом каталоге"):
            service._spawn_mob(
                {"x": 3, "y": 3},
                {"mob_key": "mob|not-a-pack|rat1", "level": 1},
            )

    def test_boss_drop_roll_selects_only_the_matching_item_slot(self):
        service = self._service()
        player = self._waiting_player(service)
        service._rng = FixedRoll(75)
        boss = SimpleNamespace(
            boss_drop_slots=[
                {"item_id": 1, "chance_percent": 50},
                {"item_id": 2, "chance_percent": 50},
            ],
            x=player.x,
            y=player.y,
        )

        service._create_boss_item_drop(boss)

        drops = service._snapshot(player, 0, True)["item_drops"]
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0]["item_id"], 2)

    def test_boss_drop_roll_can_leave_all_slots_empty(self):
        service = self._service()
        player = self._waiting_player(service)
        service._rng = FixedRoll(100)
        boss = SimpleNamespace(
            boss_drop_slots=[{"item_id": 1, "chance_percent": 50}],
            x=player.x,
            y=player.y,
        )

        service._create_boss_item_drop(boss)

        self.assertEqual(service._snapshot(player, 0, True)["item_drops"], [])

    def test_boss_item_drop_requires_proximity_and_is_picked_up_once(self):
        service = self._service()
        player = self._waiting_player(service)
        service._rng = FixedRoll(1)
        boss = SimpleNamespace(
            boss_drop_slots=[{"item_id": 1, "chance_percent": 100}],
            x=player.x + 100,
            y=player.y,
        )
        service._create_boss_item_drop(boss)
        drop_id = next(iter(service._item_drops))

        with self.assertRaisesRegex(ValueError, "Подойдите ближе"):
            service.loot_item_drop(self.admin["id"], self.character["id"], drop_id)

        player.x, player.y = boss.x, boss.y
        result = service.loot_item_drop(self.admin["id"], self.character["id"], drop_id)
        self.assertEqual(result["item"]["item_id"], 1)
        self.assertNotIn(drop_id, service._item_drops)
        with self.assertRaisesRegex(ValueError, "уже подобран"):
            service.loot_item_drop(self.admin["id"], self.character["id"], drop_id)
        with self.database.connection() as connection:
            inventory_item = connection.execute(
                "SELECT quantity FROM character_items WHERE character_id = %s AND item_id = %s",
                (self.character["id"], 1),
            ).fetchone()
        self.assertIsNotNone(inventory_item)
        self.assertEqual(int(inventory_item["quantity"]), 1)

    def test_wait_timer_resets_when_the_queue_is_empty(self):
        service = self._service(start_wait_seconds=120)
        self.assertEqual(service._start_deadline, 220.0)
        self.clock.advance(30)
        service.advance(1)
        self.assertEqual(service._start_deadline, 250.0)
        self.assertFalse(service._game_started)

    def test_waiting_front_line_uses_only_its_own_map(self):
        map_worlds.save_map(
            self.database,
            self.admin["id"],
            {
                "name": "Экономическая карта",
                "mode": "economy",
                "map_w": 40,
                "map_h": 24,
                "cells": self.map_body["cells"],
                "mobs": [],
                "spawns": [],
            },
        )
        service = self._service()
        player = self._waiting_player(service)

        self.assertEqual(service._map_id, 0)
        self.assertEqual((world_map.MAP_TILES_W, world_map.MAP_TILES_H), (16, 16))
        self.assertEqual(
            service._snapshot(player, 0, True)["front_line"]["state"],
            "map_unavailable",
        )

    def test_front_line_map_visual_payload_includes_saved_tile_layers(self):
        body = {
            **self.map_body,
            "editor_layers": [
                {
                    "id": 1,
                    "name": "Берег",
                    "type": "tile",
                    "visible": True,
                    "cells": [{
                        "x": 4,
                        "y": 5,
                        "key": "atlas|res://assets/test_atlas.png|2|3",
                    }],
                },
                {
                    "id": 2,
                    "name": "Скрытый слой",
                    "type": "tile",
                    "visible": False,
                    "cells": [{"x": 6, "y": 7, "key": "atlas|res://assets/hidden.png|0|0"}],
                },
                {
                    "id": 3,
                    "name": "Декор",
                    "type": "decorative",
                    "visible": True,
                    "cells": [{"x": 8, "y": 9, "key": "atlas|res://assets/decor.png|0|0"}],
                },
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()

        visual = service.map_visual_payload()

        self.assertEqual((visual["map_w"], visual["map_h"]), (16, 16))
        self.assertEqual(len(visual["layers"]), 2)
        self.assertEqual(visual["layers"][0]["cells"][0]["x"], 4)
        self.assertEqual(
            visual["layers"][0]["cells"][0]["key"],
            "atlas|res://assets/test_atlas.png|2|3",
        )
        self.assertEqual(visual["layers"][1]["type"], "decorative")

    def test_front_line_atlas_water_and_objects_block_movement(self):
        body = {
            **self.map_body,
            "cells": [
                *self.map_body["cells"],
                {"layer": "ground", "x": 6, "y": 5, "key": WATER},
            ],
            "editor_layers": [
                {
                    "id": 1,
                    "type": "tile",
                    "visible": True,
                    "cells": [
                        {"x": 2, "y": 5, "key": "atlas|res://assets/Ground.png|0|0"},
                        {"x": 4, "y": 5, "key": "atlas|res://assets/Water_coasts.png|0|0"},
                        {"x": 5, "y": 5, "key": "atlas|res://assets/Objects.png|0|0"},
                        {"x": 6, "y": 5, "key": "atlas|res://assets/Bridge.png|0|0"},
                    ],
                },
                {
                    "id": 2,
                    "type": "tile",
                    "visible": False,
                    "cells": [{"x": 7, "y": 5, "key": "atlas|res://assets/Objects.png|0|0"}],
                },
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()
        service.prepare_lobby_terrain()

        self.assertTrue(world_map.is_passable(2 * 32 + 16, 5 * 32 + 16))
        self.assertFalse(world_map.is_passable(4 * 32 + 16, 5 * 32 + 16))
        self.assertFalse(world_map.is_passable(5 * 32 + 16, 5 * 32 + 16))
        self.assertTrue(world_map.is_passable(6 * 32 + 16, 5 * 32 + 16))
        self.assertTrue(world_map.is_passable(7 * 32 + 16, 5 * 32 + 16))

    def test_match_ends_in_victory_after_all_waves_and_bosses_are_defeated(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        service._waves_unlocked = True
        wave = service._mob_spawners[0]["waves"][0]
        wave["remaining"] = 0
        wave["boss_pending"] = True

        service.advance(0.1)
        self.assertEqual(service._snapshot(player, 0, True)["front_line"]["state"], "running")

        wave["boss_pending"] = False
        service._mobs["still_alive"] = SimpleNamespace(alive=True)
        service._check_match_victory()
        self.assertEqual(service._match_result, "")
        service._mobs.clear()
        service.advance(0.1)
        self.assertEqual(service._match_result, "victory")
        self.assertEqual(service._snapshot(player, 0, True)["front_line"]["state"], "victory")

        service._players.clear()
        service.advance(0.1)
        self.assertFalse(service._game_started)
        self.assertEqual(service._match_result, "")
        self.assertEqual(service._tavern_hp, map_editor.DEFAULT_TAVERN_HP)

    def test_empty_running_match_resets_and_next_player_gets_a_draft(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        service = self._service()
        player = self._waiting_player(service)
        service._complete_character_draft()
        self.assertTrue(service._game_started)

        service._players.clear()
        service.advance(0.1)
        self.assertFalse(service._game_started)

        player = self._waiting_player(service)
        self.assertTrue(service._character_draft_active)
        self.assertEqual(
            service._snapshot(player, 0, True)["front_line"]["state"],
            "character_draft",
        )
        self.assertEqual(len(service._mobs), 0)

    def test_first_saved_map_starts_players_and_per_spawn_mob_cycles(self):
        first = map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        map_worlds.save_map(
            self.database,
            self.admin["id"],
            {**self.map_body, "name": "Маршрут 2"},
        )
        service = self._service()
        player = self._waiting_player(service)

        self.assertEqual(len(service._mobs), 0)
        self.assertEqual((player.x, player.y), (48, 48))
        waiting_snapshot = service._snapshot(player, 0, True)["front_line"]
        self.assertEqual(waiting_snapshot["map_id"], first["saved_id"])
        self.assertFalse(waiting_snapshot["match_started"])
        self.assertTrue(service._character_draft_active)
        self.assertFalse(waiting_snapshot["hero_visible"])
        self.assertEqual(waiting_snapshot["draft_seconds_remaining"], 60)
        self.assertEqual(
            (int(player.x // world_map.TILE), int(player.y // world_map.TILE)),
            (1, 1),
        )
        self.clock.advance(1)
        service.advance(0.1)
        self.assertFalse(service._game_started)
        self.assertEqual(service._map_id, first["saved_id"])
        self.assertEqual(service._map_name, "Маршрут 1")
        self.assertTrue(service._character_draft_active)
        self.assertEqual(service._character_draft_status(player.character_id)["seconds_remaining"], 59)
        self.assertFalse(service._snapshot(player, 0, True)["front_line"]["hero_visible"])
        self.assertEqual(
            (int(player.x // world_map.TILE), int(player.y // world_map.TILE)),
            (1, 1),
        )
        self.assertFalse(service._accept_move(player, player.x + 10, player.y, 1))

        service.submit_character_draft(
            self.admin["id"],
            player.character_id,
            "archer",
            {"strength": 4, "agility": 4},
        )
        self.assertTrue(service._character_draft_status(player.character_id)["selected"])
        self.assertEqual(service._character_draft_choices[player.character_id]["profession_type"], "archer")
        original_character = self.database.get_character(self.admin["id"], player.character_id)

        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        self.assertEqual(len(service._mobs), 0)
        self.assertFalse(service._character_draft_active)
        self.assertIn(player.character_id, service._character_draft_results)
        self.assertEqual(service._character_draft_results[player.character_id]["type"], "archer")
        drafted = self.database.get_character(self.admin["id"], player.character_id)
        self.assertEqual(drafted["type"], original_character["type"])
        self.assertEqual(drafted["stats"], original_character["stats"])
        self.assertEqual(player.fighter.profession_type, "archer")
        self.assertEqual(
            (int(player.x // world_map.TILE), int(player.y // world_map.TILE)),
            (1, 1),
        )
        self.assertEqual(service._character_draft_results[player.character_id]["stats"]["strength"], 4)
        self.assertEqual(service._character_draft_results[player.character_id]["stats"]["agility"], 4)
        self.assertEqual(service._character_draft_status(player.character_id)["active"], False)
        snapshot = service._snapshot(player, 0, True)["front_line"]
        self.assertEqual(snapshot["state"], "awaiting_wave_draft")
        self.assertEqual(snapshot["wave_draft_seconds_remaining"], 60)
        self.assertEqual(snapshot["round_countdown_seconds"], 60)
        self.assertTrue(snapshot["round_countdown_active"])
        self.assertTrue(service._accept_move(player, player.x + 10, player.y, 1))
        self.assertEqual(len(service._mobs), 0)

        self.clock.advance(59)
        player.last_seen = self.clock()
        service.advance(59)
        self.assertFalse(service._waves_unlocked)
        self.assertEqual(len(service._mobs), 0)

        self.clock.advance(1)
        player.last_seen = self.clock()
        service.advance(1)
        self.assertTrue(service._waves_unlocked)
        self.assertEqual(service._snapshot(player, 0, True)["front_line"]["state"], "running")
        countdown_zero = service._snapshot(player, 0, True)["front_line"]
        self.assertEqual(countdown_zero["round_countdown_seconds"], 0)
        self.assertTrue(countdown_zero["round_countdown_active"])
        self.assertEqual(len(service._mobs), 1)
        mob = next(iter(service._mobs.values()))
        self.assertEqual((mob.x, mob.y), (112, 112))
        starting_objective_distance = math.hypot(
            service._objective.x - mob.x, service._objective.y - mob.y,
        )
        self.clock.advance(1)
        service.advance(1)
        self.assertEqual(len(service._mobs), 2)
        wave_progress = service._snapshot(player, 0, True)["front_line"]["wave"]
        self.assertEqual(
            (wave_progress["number"], wave_progress["mobs_alive"], wave_progress["mobs_total"]),
            (1, 2, 2),
        )
        mob = next(iter(service._mobs.values()))
        self.assertEqual(mob.kind, "imp_vanilla")
        self.assertEqual(mob.name, "Бес")
        self.assertEqual(mob.fighter.level, 4)
        self.assertEqual(mob.reward_xp, 75)
        self.assertEqual(mob.reward_copper, 38)

        self.assertEqual(len(service._mobs), 2)
        wave_progress = service._snapshot(player, 0, True)["front_line"]["wave"]
        self.assertEqual((wave_progress["mobs_alive"], wave_progress["mobs_total"]), (2, 2))
        objective_distance = math.hypot(
            service._objective.x - mob.x, service._objective.y - mob.y,
        )
        self.assertLess(objective_distance, starting_objective_distance)

    def test_wave_start_delay_is_relative_to_map_start_and_waves_are_independent(self):
        body = {
            **self.map_body,
            "spawns": [
                {"x": 1, "y": 1, "type": "hero"},
                {
                    "x": 3,
                    "y": 3,
                    "type": "mob",
                    "settings": {
                        "waves": [
                            {
                                "mob_key": "imp_vanilla", "level": 2, "count": 1,
                                "interval_seconds": 1, "start_after_seconds": 0,
                                "reward_xp": 11, "reward_copper": 5,
                            },
                            {
                                "mob_key": "imp_vanilla", "level": 8, "count": 1,
                                "interval_seconds": 1, "start_after_seconds": 150,
                                "reward_xp": 99, "reward_copper": 50,
                                "boss": {
                                    "enabled": True,
                                    "max_hp": 4321,
                                    "max_mp": 765,
                                    "reward_xp": 987,
                                    "spell_slots": [{
                                        "spell_key": "",
                                        "range": 8,
                                        "damage": 120,
                                        "cooldown_seconds": 7,
                                        "area_radius": 4,
                                        "mana_cost": 25,
                                    }],
                                },
                            },
                        ],
                    },
                },
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()
        player = self._waiting_player(service)

        self.clock.advance(1)
        service.advance(0.1)
        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        self.assertTrue(service._waves_unlocked)
        self.assertEqual(len(service._mobs), 1)
        first_mob = next(iter(service._mobs.values()))
        self.assertEqual(first_mob.fighter.level, 2)
        self.assertEqual(first_mob.reward_xp, 11)

        self.clock.advance(89)
        player.last_seen = self.clock()
        service.advance(89)
        self.assertEqual(len(service._mobs), 1)
        self.clock.advance(1)
        player.last_seen = self.clock()
        service.advance(1)
        self.assertEqual(len(service._mobs), 2)
        second_wave_mobs = [mob for mob in service._mobs.values() if mob is not first_mob]
        regular_mob = next(mob for mob in second_wave_mobs if not mob.is_boss)
        self.assertEqual(regular_mob.fighter.level, 8)
        self.assertEqual(regular_mob.reward_xp, 99)
        wave_progress = service._snapshot(player, 0, True)["front_line"]["wave"]
        self.assertEqual(
            (
                wave_progress["number"],
                wave_progress["mobs_alive"],
                wave_progress["mobs_total"],
                wave_progress["boss_pending"],
                wave_progress["boss_in_seconds"],
            ),
            (2, 1, 2, True, 30),
        )
        self.clock.advance(29)
        player.last_seen = self.clock()
        service.advance(29)
        self.assertEqual(len(service._mobs), 2)
        self.clock.advance(1)
        player.last_seen = self.clock()
        service.advance(1)
        self.assertEqual(len(service._mobs), 3)
        boss = next(mob for mob in service._mobs.values() if mob.is_boss)
        wave_progress = service._snapshot(player, 0, True)["front_line"]["wave"]
        self.assertEqual(
            (wave_progress["number"], wave_progress["mobs_alive"], wave_progress["boss_pending"]),
            (2, 2, False),
        )
        self.assertEqual((boss.fighter.hp, boss.fighter.max_hp), (4321, 4321))
        self.assertEqual((boss.fighter.mp, boss.fighter.max_mp), (765, 765))
        self.assertEqual(boss.reward_xp, 987)
        boss_payload = next(
            item for item in service._snapshot(player, 0, True)["mobs"]
            if item["id"] == boss.id
        )
        self.assertTrue(boss_payload["is_boss"])
        self.assertEqual((boss_payload["max_hp"], boss_payload["max_mp"]), (4321, 765))

    def test_unselected_player_gets_a_random_class_at_draft_timeout(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(1)
        service.advance(0.1)
        self.assertTrue(service._character_draft_active)

        self.clock.advance(60)
        player.last_seen = self.clock()
        with self.assertRaisesRegex(ValueError, "Время выбора персонажа закончилось"):
            service.submit_character_draft(
                self.admin["id"],
                player.character_id,
                "mage",
                {"intellect": 6},
            )

        drafted = self.database.get_character(self.admin["id"], player.character_id)
        self.assertIn(drafted["type"], ("warrior", "archer", "mage"))
        self.assertEqual(
            drafted["stats"],
            {
                "strength": 3,
                "agility": 3,
                "intuition": 3,
                "wisdom": 3,
                "intellect": 3,
                "endurance": 4,
            },
        )

    def test_players_are_assigned_different_map_spawns_after_draft(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        second_user = self.database.register("front-line-player-two", "password")
        second_character = self.database.create_character(second_user["id"], "Другой")
        service = self._service()
        first_player = self._waiting_player(service)
        second_player = service._load_player(second_user["id"], second_character["id"], 0, 0)
        self.clock.advance(1)
        service.advance(0.1)
        self.assertTrue(service._character_draft_active)

        self.clock.advance(60)
        first_player.last_seen = self.clock()
        second_player.last_seen = self.clock()
        service.advance(60)

        self.assertEqual(
            {
                (int(player.x // world_map.TILE), int(player.y // world_map.TILE))
                for player in (first_player, second_player)
            },
            {(1, 1), (2, 1)},
        )

    def test_assassin_is_rejected_as_a_front_line_draft_choice(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(1)
        service.advance(0.1)

        with self.assertRaisesRegex(ValueError, "Профессия должна быть одной из"):
            service.submit_character_draft(
                self.admin["id"],
                player.character_id,
                "assassin",
                {},
            )

    def test_spawn_target_can_be_players_or_nearest_of_players_and_objective(self):
        body = {
            **self.map_body,
            "spawns": [
                {"x": 1, "y": 1, "type": "hero"},
                {
                    **self.map_body["spawns"][2],
                    "settings": {
                        "waves": [{
                            **self.map_body["spawns"][2]["settings"]["waves"][0],
                            "target": "characters",
                        }],
                    },
                },
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(1)
        service.advance(0.1)
        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        self.clock.advance(59)
        player.last_seen = self.clock()
        service.advance(59)
        self.clock.advance(1)
        player.last_seen = self.clock()
        service.advance(1)

        mob = next(iter(service._mobs.values()))
        player.x, player.y = 48, 288
        service._update_mobs(1)
        self.assertIs(mob.target, player)
        self.assertEqual(mob.state, "chase")

        mob.front_line_target = "both"
        mob.target = None
        mob.state = "idle"
        player.x, player.y = service._objective.x, service._objective.y
        service._update_mobs(1)
        self.assertIsNone(mob.target)
        player.x, player.y = mob.x - 120, mob.y
        service._update_mobs(1)
        self.assertIs(mob.target, player)


    def test_tavern_objective_loads_health_takes_damage_and_can_be_destroyed(self):
        body = {
            **self.map_body,
            "cells": [
                *self.map_body["cells"],
                {"layer": "object", "x": 3, "y": 1, "key": "city_building_tavern"},
            ],
            "spawns": [
                {"x": 1, "y": 1, "type": "hero"},
                {"type": "objective", "settings": {"max_hp": 2000}},
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(1)
        service.advance(0.1)

        snapshot = service._snapshot(player, 0, True)["front_line"]
        self.assertEqual((snapshot["map_width"], snapshot["map_height"]), (16, 16))
        self.assertEqual(snapshot["tavern"]["max_hp"], 2000)
        self.assertEqual(snapshot["tavern"]["hp"], 2000)
        self.assertEqual((snapshot["tavern"]["x"], snapshot["tavern"]["y"]), (96, 32))
        mob = SimpleNamespace(
            fighter=SimpleNamespace(),
            x=service._objective.x,
            y=service._objective.y,
            facing=0.0,
            windup=0.0,
            windup_total=0.0,
            backswing=0.0,
            windup_time=0.5,
            backswing_time=0.5,
            state="idle",
        )
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=17):
            service._attack_tavern(mob, 0.5)
            self.assertEqual(service._tavern_hp, 1983)
            service._attack_tavern(mob, 0.1)
            self.assertEqual(service._tavern_hp, 1983)
            service._tavern_hp = 1
            service._attack_tavern(mob, 1.0)

        self.assertEqual(service._tavern_hp, 0)
        lost_snapshot = service._snapshot(player, 0, True)["front_line"]
        self.assertEqual(lost_snapshot["state"], "lost")
        self.assertTrue(lost_snapshot["tavern"]["destroyed"])

    def test_tavern_attacker_is_included_in_front_line_snapshot(self):
        body = {
            **self.map_body,
            "cells": [
                *self.map_body["cells"],
                {"layer": "object", "x": 3, "y": 1, "key": "city_building_tavern"},
            ],
            "spawns": [
                {"x": 1, "y": 1, "type": "hero"},
                {
                    "x": 3,
                    "y": 1,
                    "type": "mob",
                    "settings": {
                        "waves": [{
                            "mob_key": "imp_vanilla",
                            "level": 1,
                            "count": 1,
                            "interval_seconds": 1,
                        }],
                    },
                },
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)
        service = self._service()
        player = self._waiting_player(service)
        self.clock.advance(60)
        player.last_seen = self.clock()
        service.advance(60)
        service._waves_unlocked = True
        service._waves_unlocked_at = self.clock()
        service._advance_spawners(0.1)

        mob = next(iter(service._mobs.values()))
        mob.x, mob.y = service._objective.x, service._objective.y
        initial_hp = service._tavern_hp
        service._update_mobs(mob.windup_time)
        snapshot = service._snapshot(player, 0, True)

        self.assertLess(service._tavern_hp, initial_hp)
        self.assertEqual(len(snapshot["mobs"]), 1)
        self.assertEqual(snapshot["mobs"][0]["id"], mob.id)
        self.assertTrue(snapshot["mobs"][0]["front_line"])
        self.assertEqual(snapshot["mobs"][0]["state"], "attack")
        self.assertEqual(snapshot["mobs"][0]["backswing"], mob.backswing_time)
        self.assertEqual(snapshot["mobs"][0]["backswing_total"], mob.backswing_time)

    def test_tavern_atlas_art_overrides_editor_generated_default_tavern(self):
        atlas_path = (
            "res://assets/base_tails/pack/"
            "craftpix-net-666104-tavern-top-down-pixel-rpg-asset-pack/"
            "Tiled_files/Exterior.png"
        )
        atlas_cells = [
            {
                "x": x,
                "y": y,
                "key": f"atlas|{atlas_path}|{x % 8}|{y % 8}",
            }
            for y in range(49, 59)
            for x in range(12, 24)
        ]
        body = {
            **self.map_body,
            "map_w": 64,
            "map_h": 64,
            "cells": [
                *self.map_body["cells"],
                {"layer": "object", "x": 51, "y": 25, "key": "city_building_tavern"},
            ],
            "editor_layers": [
                {"id": 1, "type": "tile", "visible": True, "cells": atlas_cells},
                {
                    "id": 2,
                    "type": "object",
                    "visible": True,
                    "cells": [{
                        "x": 51,
                        "y": 25,
                        "key": "city_building_tavern",
                    }],
                },
            ],
            "spawns": [
                {"x": 27, "y": 56, "type": "hero"},
                {"type": "objective", "settings": {"max_hp": 1000}},
            ],
        }
        map_worlds.save_map(self.database, self.admin["id"], body)

        with patch(
            "front_line.server.world.map_editor.terrain_from_cells",
            wraps=map_editor.terrain_from_cells,
        ) as terrain_from_cells:
            service = self._service()

        self.assertEqual((service._tavern.x, service._tavern.y), (12 * 32, 49 * 32))
        terrain_cells = terrain_from_cells.call_args.args[0]
        self.assertFalse(any(cell.get("key") == "city_building_tavern" for cell in terrain_cells))

    def test_character_draft_starts_when_player_confirms_world_and_match_starts_after_60_seconds(self):
        map_worlds.save_map(self.database, self.admin["id"], self.map_body)
        service = self._service(start_wait_seconds=120)
        player = self._waiting_player(service)
        self.assertTrue(service._character_draft_active)
        self.assertFalse(service._game_started)

        for _ in range(59):
            self.clock.advance(1)
            service.sync(
                self.admin["id"],
                self.character["id"],
                {"x": player.x, "y": player.y},
            )
            service.advance(0.1)
            self.assertFalse(service._game_started)

        self.assertEqual(service._character_draft_status(player.character_id)["seconds_remaining"], 1)
        self.clock.advance(1)
        player.last_seen = self.clock()
        service.advance(1)
        self.assertTrue(service._game_started)
        self.assertFalse(service._character_draft_active)
        self.assertTrue(service._snapshot(player, 0, True)["front_line"]["hero_visible"])


if __name__ == "__main__":
    unittest.main()
