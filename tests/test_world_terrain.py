import math
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from core import settings
from server.world_map import OBSTACLES, _edge_distance, is_passable, point_in_polygon, terrain_payload
from server.structures import WORLD_OBJECTS, city_structures
from server import presence
from scenes.world_map_scene import MOB_SPRITE_SIZE
from server.world_roads import COUNTRY_BUILDINGS, CITY_GATES, roads_payload
from tests.fixtures import create_test_database, drop_test_database, running_server

# Фиксированный исход удара игрока: попадание на 13 без крита.
PLAYER_HIT_DAMAGE = 13
FIXED_PLAYER_HIT = {"outcome": "hit", "damage": PLAYER_HIT_DAMAGE, "critical": False}


class WorldTerrainTests(unittest.TestCase):
    def test_returning_wagon_hover_shows_cargo_weight_and_reverse_progress(self):
        from types import SimpleNamespace
        from ui.map_travel import _route_progress_percent, draw_mobile_hover_card

        self.assertEqual(_route_progress_percent({
            "direction": "returning", "travel_seconds": 120, "eta_seconds": 120,
        }), 100)
        self.assertEqual(_route_progress_percent({
            "direction": "returning", "travel_seconds": 120, "eta_seconds": 0,
        }), 0)

        pygame.init()
        pygame.display.set_mode((640, 480), pygame.HIDDEN)
        rendered = []
        font = pygame.font.SysFont(None, 18)

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return font.render(text, *args)

            def __getattr__(self, name):
                return getattr(font, name)

        scene = SimpleNamespace(small_font=Recorder())
        entity = {
            "entity_kind": "wagon", "cart_name": "Лёгкая повозка",
            "cart_sprite_key": "light", "movement_text": "Возвращается в город",
            "route_name": "Крестьянское поселение", "direction": "returning",
            "progress_percent": 100, "travel_seconds": 120, "eta_seconds": 120,
            "phase": "returning", "cargo_kg": 300,
            "cargo": [{"resource_id": "wheat", "quantity": 150, "unit_weight_kg": 2}],
        }
        try:
            draw_mobile_hover_card(scene, pygame.Surface((640, 480)), entity)
        finally:
            pygame.quit()

        self.assertIn("Лёгкая повозка", rendered)
        self.assertIn("Груз: Пшеница ×150 · общий вес 300 кг", rendered)
        self.assertIn("Путь в город: 100%", rendered)
        self.assertFalse(any(text.startswith("Экипаж:") or text.startswith("Лошади:") for text in rendered))

    def test_resting_pinned_convoy_hover_shows_rest_not_returning(self):
        from ui.map_travel import traveling_entities

        convoy = {
            "id": 3, "cart_name": "Лёгкая повозка", "cart_sprite_key": "light",
            "destination_building_id": "wheat_farm", "phase": "resting",
            "status": "Отдых экипажа", "movement_text": "Отдых экипажа",
            "direction": "outbound", "progress_percent": 0,
            "seconds_remaining": 600, "travel_seconds": 600,
            "cargo": [], "horses": [{"name": "Лошадь 1"}],
        }
        route = {"building_id": "wheat_farm", "name": "Крестьянское поселение",
                 "tiles": [[10, 10], [11, 10]]}
        scene = SimpleNamespace(
            chat=SimpleNamespace(traveling_convoys=[convoy], travelers=[],
                                 convoys_received_at=time.monotonic()),
            road_routes=[route], tile_size=32,
        )

        entity = traveling_entities(scene)[0]

        self.assertEqual(entity["movement_text"], "Отдых экипажа")
        self.assertLessEqual(entity["eta_seconds"], 600)
        self.assertEqual(entity["position_x"], (10.5 * 32))

    def test_convoy_hover_eta_uses_hours_minutes_seconds_without_daily_wrap(self):
        from ui.map_travel import _format_phase_eta
        from ui.time_format import format_hms

        self.assertEqual(format_hms(89999), "24:59:59")
        self.assertEqual(format_hms(61), "00:01:01")
        self.assertEqual(format_hms(-1), "00:00:00")
        self.assertEqual(
            _format_phase_eta({"phase": "loading", "eta_seconds": 3600}),
            "До конца погрузки: 01:00:00",
        )
        self.assertEqual(
            _format_phase_eta({"phase": "unloading", "eta_seconds": 61}),
            "До конца разгрузки: 00:01:01",
        )
        self.assertEqual(
            _format_phase_eta({"phase": "outbound", "eta_seconds": 60}),
            "До прибытия: 00:01:00",
        )

    def test_convoy_draws_grade_specific_wagon_harness_horse_and_driver(self):
        pygame.init()
        pygame.display.set_mode((640, 640), pygame.HIDDEN)
        from ui.map_travel import draw_traveling_entities

        route = {"building_id": "lumber_camp", "name": "Лесопилка", "tiles": [[10, 10], [11, 10]]}
        convoy = {
            "cart_sprite_key": "peasant", "destination_building_id": "lumber_camp",
            "seconds_remaining": 5, "travel_seconds": 10, "progress_percent": 50,
            "direction": "outbound", "cargo": [], "horses": [{"name": "Рыжий"}],
        }
        scene = SimpleNamespace(
            chat=SimpleNamespace(traveling_convoys=[convoy], travelers=[],
                                 convoys_received_at=time.monotonic()),
            road_routes=[route], tile_size=32, grid_font=pygame.font.SysFont(None, 16),
            world_to_screen=lambda x, y: (x, y),
        )
        screen = pygame.Surface((640, 640))
        draw_traveling_entities(scene, screen)

        self.assertFalse(screen.get_bounding_rect().size == (0, 0))

    def test_nearby_convoys_on_same_route_render_in_separate_lanes(self):
        from ui.map_travel import draw_traveling_entities, traveling_entities

        pygame.init()
        pygame.display.set_mode((640, 640), pygame.HIDDEN)
        route = {
            "building_id": "lumber_camp", "name": "Лесопилка",
            "tiles": [[10, 10], [11, 10]],
        }
        convoys = [
            {
                "id": convoy_id, "cart_sprite_key": "peasant",
                "destination_building_id": "lumber_camp",
                "seconds_remaining": 5, "travel_seconds": 10,
                "progress_percent": 50, "direction": "outbound", "cargo": [],
            }
            for convoy_id in (41, 42)
        ]
        scene = SimpleNamespace(
            chat=SimpleNamespace(traveling_convoys=convoys, travelers=[],
                                 convoys_received_at=time.monotonic()),
            road_routes=[route], tile_size=32,
            grid_font=pygame.font.SysFont(None, 16),
            world_to_screen=lambda x, y: (x, y),
        )
        entities = traveling_entities(scene)
        self.assertEqual(len(entities), 2)
        self.assertEqual(
            {(entity["position_x"], entity["position_y"]) for entity in entities},
            {(entities[0]["position_x"], entities[0]["position_y"])},
        )
        display_positions = {
            (entity["display_position_x"], entity["display_position_y"])
            for entity in entities
        }
        self.assertEqual(len(display_positions), 2)

        rendered_centers = []
        screen = pygame.Surface((640, 640))
        with patch("ui.map_travel.draw_convoy_sprite_group",
                   side_effect=lambda _screen, center, *_args, **_kwargs:
                   rendered_centers.append(center)), \
                patch("ui.map_travel.draw_transport_cart_icon", return_value=None):
            draw_traveling_entities(scene, screen)
        self.assertEqual(len(set(rendered_centers)), 2)

    def test_afk_presence_survives_ttl_and_is_cleared_on_reconnect(self):
        previous_presence = dict(presence.PRESENCE)
        presence.PRESENCE.clear()
        character = {
            "id": 77, "name": "Отключённый", "type": "warrior", "level": 4, "xp": 30,
            "hp": 80, "max_hp": 100, "mp": 20, "max_mp": 40,
            "stats": {"strength": 8}, "stat_points": 0, "zone": "world_map",
            "position_x": 2400, "position_y": 1600, "position_direction": "e",
        }
        try:
            presence.update_presence("old-token", 9, character, "world_map")
            presence.mark_afk("old-token", 9, character)
            presence.PRESENCE["old-token"]["seen_at"] = 0
            presence.cleanup()
            afk_player = presence.occupants(1, "world_map")[0]
            self.assertTrue(afk_player["afk"])
            self.assertEqual((afk_player["position_x"], afk_player["position_y"]), (2400, 1600))

            presence.update_presence("new-token", 9, character, "world_map")
            current_players = presence.occupants(1, "world_map")
            self.assertEqual(len(current_players), 1)
            self.assertFalse(current_players[0]["afk"])
        finally:
            presence.PRESENCE.clear()
            presence.PRESENCE.update(previous_presence)

    def test_one_massif_covers_both_former_ranges(self):
        mountains = [obstacle for obstacle in OBSTACLES if obstacle["type"] == "mountains"]
        self.assertEqual(len(mountains), 1)
        for x, y in ((4412, 2881), (155 * 32, 60 * 32), (150 * 32, 66 * 32), (140 * 32, 80 * 32)):
            with self.subTest(point=(x, y)):
                self.assertFalse(is_passable(x, y))
        for x, y in ((3500, 2400), (5300, 3500), (128 * 32, 50 * 32), (181 * 32, 64 * 32)):
            with self.subTest(point=(x, y)):
                self.assertTrue(is_passable(x, y))

    def test_rift_passage_cuts_through_mountains(self):
        self.assertTrue(is_passable(4240, 3328))
        self.assertTrue(is_passable(4240, 3200))
        self.assertFalse(is_passable(4100, 3200))
        self.assertFalse(is_passable(4380, 3200))

    def test_forest_blocks_its_outline(self):
        self.assertFalse(is_passable(1700, 3000))
        self.assertFalse(is_passable(2600, 3000))
        self.assertTrue(is_passable(400, 3000))
        self.assertTrue(is_passable(1778, 2550))
        self.assertTrue(is_passable(1400, 3600))
        self.assertTrue(is_passable(1488, 2640))
        forest = next(obstacle for obstacle in OBSTACLES if obstacle["id"] == "forest_1")
        self.assertGreater(len(forest["trees"]), 300)
        points = forest["points"]
        for index in range(len(points)):
            (ax, ay), (bx, by), (cx, cy) = points[index - 2], points[index - 1], points[index]
            turn = abs(math.atan2(cy - by, cx - bx) - math.atan2(by - ay, bx - ax))
            turn = min(turn, 2 * math.pi - turn)
            self.assertLess(math.degrees(turn), 45)

    def test_lumber_camp_moves_north_entrance_and_stump_clearcut_follow_forest(self):
        camp = next(obj for obj in WORLD_OBJECTS if obj["id"] == "lumber_camp")
        self.assertEqual((camp["tile_x"], camp["tile_y"], camp["tile_w"], camp["tile_h"]),
                         (41, 83, 10, 10))
        self.assertEqual(camp["rotation"], 180)
        self.assertEqual(camp["entrance_tile"], [46, 83])
        self.assertEqual(camp["approach_pos"], [1488, 2640])
        self.assertTrue(is_passable(*camp["approach_pos"]))

        forest = next(obstacle for obstacle in OBSTACLES if obstacle["id"] == "forest_1")
        stump_tiles = {tuple(tile) for tile in camp["stump_tiles"]}
        self.assertEqual(len(stump_tiles), 10)
        self.assertTrue(all(93 <= y <= 97 for _x, y in stump_tiles))
        self.assertTrue(all(point_in_polygon((x * 32 + 16, y * 32 + 16), forest["points"])
                            for x, y in stump_tiles))

        routes = roads_payload(city_level=4)["routes"]
        route = next(row for row in routes if row["building_id"] == "lumber_camp")
        route_tiles = {tuple(tile) for tile in route["tiles"]}
        self.assertEqual(route["tiles"][-1], [46, 82])
        self.assertFalse(route_tiles & stump_tiles)

    def test_hills_at_edges_huge_mountains_in_center(self):
        massif = next(obstacle for obstacle in OBSTACLES if obstacle["id"] == "mountains_1")
        hills = [peak for peak in massif["peaks"] if peak["kind"] == "hill"]
        peaks = [peak for peak in massif["peaks"] if peak["kind"] == "peak"]
        self.assertGreater(len(hills), 30)
        self.assertGreater(len(peaks), 30)
        self.assertLess(max(hill["h"] for hill in hills), 150)
        self.assertGreater(max(peak["h"] for peak in peaks), 400)

    def test_black_pit_is_on_western_mountain_face_with_city_side_entrance(self):
        pit = next(obj for obj in WORLD_OBJECTS if obj["id"] == "black_pit")
        self.assertEqual((pit["tile_x"], pit["tile_y"]), (133, 54))
        self.assertEqual(pit["entrance_tile"], [133, 60])
        self.assertTrue(is_passable(120 * 32 + 16, 60 * 32 + 16))
        self.assertTrue(is_passable(*pit["approach_pos"]))
        self.assertTrue(is_passable(133 * 32 + 16, 60 * 32 + 16))
        self.assertFalse(is_passable(150 * 32 + 16, 66 * 32 + 16))

    def test_lake_is_smooth_and_blocks_water_and_shore(self):
        lake = next(obstacle for obstacle in OBSTACLES if obstacle["type"] == "lake")
        self.assertEqual(lake["id"], "lake_1")
        self.assertTrue(is_passable(30 * 32, 30 * 32))
        self.assertFalse(is_passable(70 * 32, 28 * 32))
        points = lake["points"]
        for index in range(len(points)):
            (ax, ay), (bx, by), (cx, cy) = points[index - 2], points[index - 1], points[index]
            turn = abs(math.atan2(cy - by, cx - bx) - math.atan2(by - ay, bx - ax))
            turn = min(turn, 2 * math.pi - turn)
            self.assertLess(math.degrees(turn), 45)

    def test_country_roads_connect_each_building_to_nearest_noncentral_gate(self):
        roads = roads_payload(city_level=4)
        routes = {route["building_id"]: route for route in roads["routes"]}
        self.assertEqual(set(routes), set(COUNTRY_BUILDINGS))
        self.assertEqual(set(CITY_GATES), {"north", "west", "south"})
        blocked = __import__("server.world_roads", fromlist=["_blocked_cells"])._blocked_cells()
        objects = {obj["id"]: obj for obj in WORLD_OBJECTS}

        for building_id, route in routes.items():
            with self.subTest(building=building_id):
                tiles = [tuple(tile) for tile in route["tiles"]]
                self.assertEqual(tiles[0], CITY_GATES[route["gate_id"]])
                approach = objects[building_id]["approach_pos"]
                self.assertEqual(tiles[-1], (approach[0] // 32, approach[1] // 32))
                self.assertTrue(all(tile not in blocked for tile in tiles))
                self.assertTrue(all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
                                    for a, b in zip(tiles, tiles[1:])))
                self.assertNotEqual(route["gate_id"], "east")

            self.assertEqual(routes["black_pit"]["gate_id"], "west")
            pit = objects["black_pit"]
            self.assertEqual(routes["black_pit"]["tiles"][-1],
                     [pit["approach_pos"][0] // 32, pit["approach_pos"][1] // 32])
            farm_tiles = routes["wheat_farm"]["tiles"]
            terrain_to_clear = [obstacle for obstacle in OBSTACLES if obstacle["id"] in {"lake_1", "forest_1", "mountains_1"}]
            for x, y in farm_tiles:
                center = (x * 32 + 16, y * 32 + 16)
                for obstacle in terrain_to_clear:
                    with self.subTest(tile=(x, y), obstacle=obstacle["id"]):
                        self.assertFalse(point_in_polygon(center, obstacle["points"]))
                        self.assertGreaterEqual(_edge_distance(center[0], center[1], obstacle["points"]), 2 * 32)

        self.assertEqual({tuple(tile) for tile in roads["tiles"]},
                         {tuple(tile) for route in roads["routes"] for tile in route["tiles"]})

    def test_city_level_filters_country_objects_and_roads(self):
        level_one = terrain_payload(city_level=1)
        self.assertEqual(
            {obj["id"] for obj in level_one["objects"] if obj["id"] in COUNTRY_BUILDINGS},
            {"wheat_farm", "lumber_camp"},
        )
        self.assertEqual(
            {route["building_id"] for route in level_one["roads"]["routes"]},
            {"wheat_farm", "lumber_camp"},
        )
        self.assertEqual(
            {route["building_id"] for route in roads_payload(city_level=2)["routes"]},
            {"wheat_farm", "lumber_camp", "mountain_rift"},
        )
        self.assertEqual(
            {route["building_id"] for route in roads_payload(city_level=3)["routes"]},
            {"wheat_farm", "lumber_camp", "mountain_rift", "barnyard"},
        )

    def test_structures_come_from_server(self):
        database = create_test_database()
        try:
            with running_server(database) as client:
                client.register("builder", "secret1")
                client.login("builder", "secret1")
                terrain = client.get_map_terrain()
                city = client.get_city_structures()
        finally:
            drop_test_database(database)
        world_ids = [obj["id"] for obj in terrain["objects"]]
        for object_id in ("wheat_farm", "lumber_camp", "town_radburg"):
            self.assertIn(object_id, world_ids)
        for object_id in ("mountain_rift", "barnyard", "black_pit"):
            self.assertNotIn(object_id, world_ids)
        self.assertEqual(
            {route["building_id"] for route in terrain["roads"]["routes"]},
            {"wheat_farm", "lumber_camp"},
        )
        self.assertEqual(len(city["objects"]), 13)
        self.assertEqual(city["objects"][3]["id"], "barn_building")
        stable = city["objects"][-1]
        self.assertEqual(stable["id"], "stable_building")
        self.assertEqual((stable["tile_x"], stable["tile_y"], stable["tile_w"], stable["tile_h"]), (77, 6, 17, 6))
        self.assertEqual(stable["entrance_tile"], [85, 11])
        self.assertEqual(len(city["walls"]), 12)
        route = terrain["roads"]["routes"][0]
        self.assertTrue({"building_id", "gate_id", "tiles", "distance_tiles", "distance_pixels", "resources"}.issubset(route))
        self.assertTrue(route["resources"])

    def test_global_city_uses_modular_visual_state(self):
        from unittest.mock import patch
        from scenes.world_map_scene import WorldMapScene

        town = next(obj for obj in WORLD_OBJECTS if obj["id"] == "town_radburg")
        visual_state = {
            "city_level": 1, "population": 8, "active": True, "phase_index": 2,
        }

        class Client:
            def get_map_terrain(self):
                return {
                    "objects": [town], "obstacles": [],
                    "roads": {"routes": [], "tiles": [], "travel_seconds": 0},
                    "city_visual_state": visual_state,
                }

        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            scene = WorldMapScene(SimpleNamespace(
                character={"id": 1, "name": "Test"}, client=Client(),
            ))
            scene.camera_x = town["x"] + town["tile_w"] * scene.tile_size / 2
            scene.camera_y = town["y"] + town["tile_h"] * scene.tile_size / 2
            with patch("scenes.world_map_scene.draw_city_exterior") as draw_city:
                scene._draw_objects(screen)
            draw_city.assert_called_once()
            self.assertEqual(draw_city.call_args.args[2], visual_state)
        finally:
            pygame.quit()

    def test_player_does_not_move_during_windup_and_resumes_after(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            hit_patch = patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=dict(FIXED_PLAYER_HIT))
            hit_patch.start()
            self.addCleanup(hit_patch.stop)

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10, mob["y"]
            scene._set_attack_target(mob)
            scene._update_attack_target(0.0)
            self.assertGreater(scene.attack_windup, 0)
            scene.move_path = [(scene.player_x + 200, scene.player_y)]
            x_before = scene.player_x

            scene.update(0.1)
            self.assertEqual(scene.player_x, x_before)
            self.assertEqual(scene.player_state, "idle")

            scene.attack_target = None
            scene.attack_windup = 0.0
            scene.attack_backswing = 0.0
            scene.move_path = [(scene.player_x + 200, scene.player_y)]
            scene.update(0.1)
            self.assertGreater(scene.player_x, x_before)
        finally:
            pygame.quit()

    def test_scene_without_server_has_no_structures(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            self.assertEqual(scene.objects, [])
            self.assertEqual(scene.obstacles, [])
        finally:
            pygame.quit()

    def test_attack_tile_is_highlighted_green(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y = mob["x"] - 60, mob["y"]
            scene.camera_x, scene.camera_y = scene.player_x, scene.player_y
            scene._set_attack_target(mob)

            mx, my = scene.world_to_screen(mob["x"], mob["y"])
            screen.fill((0, 0, 0))
            scene._draw_attack_tile(screen)
            rect = scene._mob_body_rect(mob)
            left, _ = scene.world_to_screen(rect.left, rect.top)
            r, g, b, _ = screen.get_at((int(left) - 3, int(my)))
            self.assertGreater(g, r)
            self.assertGreater(g, b)
        finally:
            pygame.quit()

    def test_attack_reach_is_30_px_from_mob_body(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_reach
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            reach = get_attack_reach(scene.combat_fighter)
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2

            scene.player_x, scene.player_y = edge - reach + 1, mob["y"]
            self.assertLessEqual(scene._distance_to_mob_body(mob), reach)
            scene.player_x = edge - reach - 5
            self.assertGreater(scene._distance_to_mob_body(mob), reach)
        finally:
            pygame.quit()

    def test_attack_target_strikes_only_within_reach_and_restarts_windup_without_pause(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_backswing, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            hit_patch = patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=dict(FIXED_PLAYER_HIT))
            hit_patch.start()
            self.addCleanup(hit_patch.stop)
            save_patch = patch("scenes.world_map_scene.WorldMapScene._save_player_hp")
            save_patch.start()
            self.addCleanup(save_patch.stop)

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            full_hp = mob["hp"]
            windup = get_attack_windup(scene.combat_fighter)
            backswing = get_attack_backswing(scene.combat_fighter)
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            scene._set_attack_target(mob)
            # Вход в зону удара не наносит урон мгновенно: сначала замах
            scene._update_attack_target(0.0)
            self.assertEqual(mob["hp"], full_hp)
            self.assertGreater(scene.attack_windup, 0)

            scene._update_attack_target(windup)
            self.assertEqual(mob["hp"], full_hp - PLAYER_HIT_DAMAGE)
            # После удара идёт откат: новый замах не начинается, пока он не закончится
            self.assertEqual(scene.attack_windup, 0.0)
            self.assertAlmostEqual(scene.attack_backswing, backswing)
            scene.update(backswing)
            # Откат закончился ровно в этом кадре; остаток dt = 0, замах начат, удара ещё нет
            self.assertEqual(scene.attack_backswing, 0.0)
            self.assertAlmostEqual(scene.attack_windup, windup)
            self.assertEqual(mob["hp"], full_hp - PLAYER_HIT_DAMAGE)

            scene._update_attack_target(windup)
            self.assertEqual(mob["hp"], full_hp - 2 * PLAYER_HIT_DAMAGE)
        finally:
            pygame.quit()

    def test_backswing_leftover_time_goes_to_next_windup_not_double_counted(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_backswing, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            hit_patch = patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=dict(FIXED_PLAYER_HIT))
            hit_patch.start()
            self.addCleanup(hit_patch.stop)
            save_patch = patch("scenes.world_map_scene.WorldMapScene._save_player_hp")
            save_patch.start()
            self.addCleanup(save_patch.stop)

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            full_hp = mob["hp"]
            windup = get_attack_windup(scene.combat_fighter)
            backswing = get_attack_backswing(scene.combat_fighter)
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            scene._set_attack_target(mob)
            scene._update_attack_target(windup)
            self.assertEqual(mob["hp"], full_hp - PLAYER_HIT_DAMAGE)

            # Кадр длиннее отката: 0.1 с уходят на следующий замах, а не списываются дважды
            scene.update(backswing + 0.1)
            self.assertEqual(scene.attack_backswing, 0.0)
            self.assertAlmostEqual(scene.attack_windup, windup - 0.1)
            self.assertEqual(mob["hp"], full_hp - PLAYER_HIT_DAMAGE)
        finally:
            pygame.quit()

    def test_retreating_mob_leaves_reach_mid_windup_swing_completes_as_miss(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_reach, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            full_hp = mob["hp"]
            reach = get_attack_reach(scene.combat_fighter)
            windup = get_attack_windup(scene.combat_fighter)
            # Моб в патруле уходит от игрока со скоростью патруля (40 px/с)
            mob["state"] = "idle"
            mob["patrol_pause"] = 0.0
            mob["patrol_target"] = (mob["x"] + 400, mob["y"])
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            # Стартуем почти на границе дальности: за замах моб уходит за неё
            scene.player_x, scene.player_y = edge - (reach - 5), mob["y"]
            scene._set_attack_target(mob)
            scene.move_path = []

            with patch.object(scene, "_player_in_mob_aggro_area", return_value=False), \
                    patch.object(scene, "_strike_mob") as strike, \
                    patch.object(scene, "_spawn_damage_number") as spawn_number:
                elapsed = 0.0
                while scene.attack_windup > 0 or elapsed == 0.0:
                    scene.update(0.02)
                    elapsed += 0.02
                    self.assertLess(elapsed, windup + 0.5, "замах должен доиграться до конца")
                    if scene.attack_windup > 0:
                        with patch("scenes.world_map_scene.pygame.draw.lines") as draw_lines:
                            scene._draw_attack_swing(pygame.Surface((settings.WIDTH, settings.HEIGHT)))
                        draw_lines.assert_called()

            self.assertGreater(scene._distance_to_mob_body(mob), reach, "моб должен выйти из дальности до конца замаха")
            strike.assert_not_called()
            self.assertEqual(mob["hp"], full_hp)
            spawn_number.assert_called()
            self.assertEqual(spawn_number.call_args.kwargs.get("text"), "Промах")
            self.assertGreater(scene.attack_backswing, 0.0)
        finally:
            pygame.quit()

    def test_player_windup_survives_target_leaving_reach_and_ends_as_miss(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            full_hp = mob["hp"]
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            scene._set_attack_target(mob)
            scene.move_path = [(scene.player_x + 100, scene.player_y)]

            with patch.object(scene, "_spawn_damage_number") as spawn_number:
                # Во время замаха персонаж стоит на месте и не бьёт
                scene.update(get_attack_windup(scene.combat_fighter) / 2)
                self.assertEqual(scene.player_x, edge - 10)
                self.assertEqual(mob["hp"], full_hp)

                # Цель ушла из зоны: замах не сбрасывается и доигрывается до промаха
                scene.player_x = edge - 400
                windup_before = scene.attack_windup
                scene._update_attack_target(0.0)
                self.assertEqual(scene.attack_windup, windup_before)
                scene._update_attack_target(windup_before + 0.01)
                self.assertEqual(scene.attack_windup, 0.0)
                self.assertEqual(mob["hp"], full_hp)
                self.assertEqual(spawn_number.call_args.kwargs.get("text"), "Промах")
                self.assertGreater(scene.attack_backswing, 0.0)
        finally:
            pygame.quit()

    def test_player_run_frames_exist_for_every_direction(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            self.assertEqual(set(scene.player_run_directional_frames), {"n", "ne", "e", "se", "s", "sw", "w", "nw"})
            for direction, frames in scene.player_run_directional_frames.items():
                self.assertTrue(frames, direction)
        finally:
            pygame.quit()

    def test_player_moves_during_backswing(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.player_x, scene.player_y = 500.0, 500.0
            scene.attack_target = None
            scene.attack_backswing = 0.5
            scene.move_path = [(scene.player_x + 100, scene.player_y)]
            scene.update(0.1)
            self.assertGreater(scene.player_x, 500.0)
            self.assertAlmostEqual(scene.attack_backswing, 0.4)
        finally:
            pygame.quit()

    def test_right_click_on_ground_starts_click_effect_that_expires(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import CLICK_EFFECT_DURATION, WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.player_x, scene.player_y = 500.0, 500.0
            scene.mobs = []
            scene._set_move_target = lambda goal: True
            scene.screen_to_world = lambda sx, sy: (700.0, 500.0)
            scene._mob_at_world_point = lambda wx, wy: None
            scene._keyboard_movement_blocked = lambda: False
            scene.active_entity = None
            event = SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0))
            scene.handle_event(event)
            self.assertIsNotNone(scene.click_effect)
            self.assertEqual((scene.click_effect["x"], scene.click_effect["y"]), (700.0, 500.0))
            scene.update(CLICK_EFFECT_DURATION / 2)
            self.assertIsNotNone(scene.click_effect)
            scene.update(CLICK_EFFECT_DURATION)
            self.assertIsNone(scene.click_effect)
        finally:
            pygame.quit()

    def test_player_move_click_cancels_windup(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            full_hp = mob["hp"]
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            scene._set_attack_target(mob)
            scene.update(get_attack_windup(scene.combat_fighter) / 2)
            self.assertGreater(scene.attack_windup, 0.0)

            # Действие игрока (ПКМ по земле) отменяет замах
            scene._set_move_target((scene.player_x - 200, scene.player_y))
            self.assertEqual(scene.attack_windup, 0.0)
            self.assertIsNone(scene.attack_target)
            scene.update(get_attack_windup(scene.combat_fighter))
            self.assertEqual(mob["hp"], full_hp)
        finally:
            pygame.quit()

    def test_mob_windup_blocks_movement_and_resets_only_when_player_leaves_leash(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import MOB_LEASH_RADIUS_TILES, WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob_windup = get_attack_windup(mob["fighter"])
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            mob_x_before = mob["x"]

            with patch.object(scene, "_mob_strike_player") as strike:
                # Удар моба не мгновенный: сначала замах, моб стоит на месте
                scene._update_mob_chase(mob, 0.1)
                strike.assert_not_called()
                self.assertAlmostEqual(mob["attack_windup"], mob_windup - 0.1)
                self.assertEqual(mob["x"], mob_x_before)

                # Игрок ушёл за поводок: замах сбрасывается, моб возвращается в патруль
                scene.player_x = mob["x"] + (MOB_LEASH_RADIUS_TILES + 5) * scene.tile_size
                scene._update_mob_chase(mob, 0.1)
                self.assertEqual(mob["attack_windup"], 0.0)
                self.assertEqual(mob["state"], "idle")
                strike.assert_not_called()
        finally:
            pygame.quit()

    def test_mob_windup_completes_as_miss_when_player_leaves_reach(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob_windup = get_attack_windup(mob["fighter"])
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]

            with patch.object(scene, "_mob_strike_player") as strike, \
                    patch.object(scene, "_spawn_damage_number") as spawn_number:
                scene._update_mob_chase(mob, 0.1)
                # Игрок отошёл внутри поводка, но вне дальности удара
                scene.player_x = edge - 400
                scene._update_mob_chase(mob, mob_windup)
                strike.assert_not_called()
                self.assertEqual(spawn_number.call_args.kwargs.get("text"), "Промах")
                self.assertEqual(mob["attack_windup"], 0.0)
                self.assertGreater(mob["attack_backswing"], 0.0)
        finally:
            pygame.quit()

    def test_mob_windup_draws_red_telegraph_arc_only_while_winding_up(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob_windup = get_attack_windup(mob["fighter"])
            scene.player_x, scene.player_y = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10, mob["y"]
            scene.camera_x, scene.camera_y = mob["x"], mob["y"]
            sx, sy = scene.world_to_screen(mob["x"], mob["y"])
            mob["attack_swing_angle"] = 0.0

            def has_telegraph_pixels():
                screen.fill((0, 0, 0))
                scene._draw_mob_windup(screen, mob, sx, sy)
                return any(screen.get_at((x, y))[:3] != (0, 0, 0)
                           for x in range(settings.WIDTH) for y in range(settings.HEIGHT))

            mob["attack_windup"] = 0.0
            self.assertFalse(has_telegraph_pixels())

            mob["attack_windup"] = mob_windup / 2
            mob["attack_windup_total"] = mob_windup
            self.assertTrue(has_telegraph_pixels())
        finally:
            pygame.quit()

    def test_player_hit_starts_attack_swing_animation(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y, scene.player_direction = mob["x"] - 40, mob["y"], "e"
            scene.camera_x, scene.camera_y = scene.player_x, scene.player_y

            screen.fill((0, 0, 0))
            scene._draw_attack_swing(screen)
            self.assertEqual(screen.get_at((settings.WIDTH // 2, settings.HEIGHT // 2))[:3], (0, 0, 0))

            scene._set_attack_target(mob)
            scene._update_attack_target(0.0)
            self.assertAlmostEqual(scene.attack_windup, get_attack_windup(scene.combat_fighter))

            screen.fill((0, 0, 0))
            scene._draw_attack_swing(screen)
            self.assertTrue(any(screen.get_at((x, y))[:3] != (0, 0, 0)
                                for x in range(settings.WIDTH) for y in range(0, settings.HEIGHT, 4)))

            scene.attack_target = None
            scene.update(0.1)
            self.assertEqual(scene.attack_windup, 0)
            screen.fill((0, 0, 0))
            scene._draw_attack_swing(screen)
            self.assertEqual(screen.get_at((settings.WIDTH // 2, settings.HEIGHT // 2))[:3], (0, 0, 0))
        finally:
            pygame.quit()

    def test_player_backswing_allows_movement_without_new_windup(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_backswing, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            hit_patch = patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=dict(FIXED_PLAYER_HIT))
            hit_patch.start()
            self.addCleanup(hit_patch.stop)
            save_patch = patch("scenes.world_map_scene.WorldMapScene._save_player_hp")
            save_patch.start()
            self.addCleanup(save_patch.stop)

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10, mob["y"]
            scene._set_attack_target(mob)
            scene._update_attack_target(0.0)
            scene._update_attack_target(get_attack_windup(scene.combat_fighter))
            backswing = get_attack_backswing(scene.combat_fighter)
            self.assertGreater(scene.attack_backswing, 0)

            # Во время отката игрок идёт по пути, но не начинает новый замах
            scene.attack_target = None
            scene.move_path = [(scene.player_x + 200, scene.player_y)]
            x_before = scene.player_x
            scene.update(1 / 60)
            self.assertGreater(scene.player_x, x_before)
            self.assertEqual(scene.attack_windup, 0.0)

            scene.update(backswing)
            self.assertEqual(scene.attack_backswing, 0.0)
        finally:
            pygame.quit()

    def test_mob_moves_during_backswing_and_does_not_start_windup(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_backswing, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob["state"] = "chase"
            mob["attack_windup"] = 0.0
            mob["attack_backswing"] = get_attack_backswing(mob["fighter"])
            mob_windup = get_attack_windup(mob["fighter"])
            mob_backswing = get_attack_backswing(mob["fighter"])
            # Игрок далеко за пределами досягаемости, но в поводке
            scene.player_x, scene.player_y = mob["x"] + 150, mob["y"]
            x_before = mob["x"]
            with patch.object(scene, "_mob_strike_player") as strike:
                scene._update_mob_chase(mob, 1 / 60)
                self.assertGreater(mob["x"], x_before)
                self.assertEqual(mob["attack_windup"], 0.0)
                strike.assert_not_called()

            # Игрок в зоне удара, но откат ещё идёт: новый замах не начинается
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]
            with patch.object(scene, "_mob_strike_player") as strike:
                scene._update_mob_chase(mob, 1 / 60)
                self.assertEqual(mob["attack_windup"], 0.0)
                strike.assert_not_called()
            self.assertGreater(mob_windup, 0)
            self.assertGreater(mob_backswing, 0)
        finally:
            pygame.quit()

    def test_mob_backswing_blocks_next_windup_and_decays_outside_chase(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_backswing, get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob_windup = get_attack_windup(mob["fighter"])
            mob_backswing = get_attack_backswing(mob["fighter"])
            edge = mob["x"] - MOB_SPRITE_SIZE[0] / 2
            scene.player_x, scene.player_y = edge - 10, mob["y"]

            with patch.object(scene, "_mob_strike_player") as strike:
                scene._update_mob_chase(mob, mob_windup)
                strike.assert_called_once()
                self.assertGreater(mob["attack_backswing"], 0)

                # Пока откат идёт, моб не начинает новый замах даже в зоне удара
                scene._update_mob_chase(mob, mob_windup / 2)
                self.assertEqual(mob["attack_windup"], 0.0)

                # Откат тикает и вне погони: игрок далеко, моб в патруле
                scene.player_x = edge - 800
                scene._update_mobs(mob_backswing)
                self.assertEqual(mob["attack_backswing"], 0.0)
        finally:
            pygame.quit()

    def test_player_hit_spawns_damage_number_for_five_seconds(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from combat.world_stats import get_attack_windup
            from scenes.world_map_scene import WorldMapScene

            hit_patch = patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=dict(FIXED_PLAYER_HIT))
            hit_patch.start()
            self.addCleanup(hit_patch.stop)

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10, mob["y"]

            scene._set_attack_target(mob)
            scene._update_attack_target(0.0)
            scene._update_attack_target(get_attack_windup(scene.combat_fighter))
            self.assertEqual(len(scene.damage_numbers), 1)
            number = scene.damage_numbers[0]
            self.assertEqual(number["text"], f"-{PLAYER_HIT_DAMAGE}")
            self.assertAlmostEqual(number["timer"], 5.0)

            # Цель сбрасываем и отходим от моба, чтобы проверять только время жизни числа, а не новые удары.
            scene.attack_target = None
            scene.player_x = mob["x"] - 400
            scene.update(4.9)
            self.assertEqual(len(scene.damage_numbers), 1)
            scene.update(0.2)
            self.assertEqual(scene.damage_numbers, [])
        finally:
            pygame.quit()

    def test_skeleton_patrols_inside_its_tile_square(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            import random

            from scenes.world_map_scene import MOB_PATROL_CENTER_TILE, MOB_PATROL_RADIUS_TILES, WorldMapScene

            random.seed(7)
            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            self.assertEqual(
                (int(mob["home_x"] // scene.tile_size), int(mob["home_y"] // scene.tile_size)),
                MOB_PATROL_CENTER_TILE,
            )
            limit = MOB_PATROL_RADIUS_TILES * scene.tile_size + 1e-6
            visited = set()
            for _ in range(3000):
                scene._update_mobs(1 / 30)
                self.assertLessEqual(abs(mob["x"] - mob["home_x"]), limit)
                self.assertLessEqual(abs(mob["y"] - mob["home_y"]), limit)
                self.assertFalse(scene._check_collision(mob["x"], mob["y"]))
                visited.add((round(mob["x"]), round(mob["y"])))
            self.assertGreater(len(visited), 20)
        finally:
            pygame.quit()

    def test_player_cannot_walk_into_mob_body(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            # Ставим персонажа слева от моба, чтобы ноги касались левого края спрайта
            scene.player_x = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10 - 20
            scene.player_y = mob["y"]
            self.assertFalse(scene._player_blocked(scene.player_x, scene.player_y))
            self.assertTrue(scene._player_blocked(mob["x"], mob["y"]))
            self.assertTrue(scene._player_blocked(mob["x"] - MOB_SPRITE_SIZE[0] / 2, mob["y"]))
            # Мёртвый моб не блокирует персонажа
            mob["hp"] = 0
            self.assertFalse(scene._player_blocked(mob["x"], mob["y"]))
        finally:
            pygame.quit()

    def test_attack_labels_and_crit_numbers_use_popup_scheme(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import (
                DAMAGE_COLOR_BLOCK, DAMAGE_COLOR_CRIT, DAMAGE_COLOR_DODGE, DAMAGE_COLOR_NORMAL, WorldMapScene,
            )

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y = mob["x"] - MOB_SPRITE_SIZE[0] / 2 - 10, mob["y"]
            scene.damage_numbers = []

            cases = [
                ({"outcome": "dodge", "damage": 0, "critical": False}, "Уворот", DAMAGE_COLOR_DODGE),
                ({"outcome": "block", "damage": 0, "critical": False}, "Блок", DAMAGE_COLOR_BLOCK),
            ]
            for result, text, color in cases:
                with patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=result), \
                        patch.object(scene, "_spawn_damage_number") as spawn_number:
                    scene._strike_mob(mob)
                spawn_number.assert_called_once()
                self.assertEqual(spawn_number.call_args.kwargs.get("text"), text)
                self.assertEqual(spawn_number.call_args.args[3], color)
                self.assertEqual(mob["hp"], mob["max_hp"])

            normal = {"outcome": "hit", "damage": 3, "critical": False}
            with patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=normal), \
                    patch.object(scene, "_spawn_damage_number") as spawn_number:
                scene._strike_mob(mob)
            self.assertEqual(spawn_number.call_args.args[2], 3)
            self.assertEqual(spawn_number.call_args.args[3], DAMAGE_COLOR_NORMAL)
            self.assertFalse(spawn_number.call_args.kwargs.get("big", False))

            crit = {"outcome": "hit", "damage": 9, "critical": True}
            mob["hp"] = mob["max_hp"]
            with patch("scenes.world_map_scene.resolve_world_melee_attack", return_value=crit), \
                    patch.object(scene, "_spawn_damage_number") as spawn_number:
                scene._strike_mob(mob)
            self.assertEqual(spawn_number.call_args.args[3], DAMAGE_COLOR_CRIT)
            self.assertTrue(spawn_number.call_args.kwargs.get("big"))
        finally:
            pygame.quit()

    def test_mob_facing_follows_movement_direction(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            self.assertIn("facing", mob)
            mob["facing"] = 0.0
            scene.player_x, scene.player_y = mob["x"], mob["y"] - 200
            scene._move_mob_toward_player(mob, 0.1)
            self.assertAlmostEqual(mob["facing"], -math.pi / 2, places=5)
        finally:
            pygame.quit()

    def test_mob_strike_on_player_uses_facing_angle(self):
        pygame.init()
        try:
            from scenes.world_map_scene import WorldMapScene

            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            save_patch = patch("scenes.world_map_scene.WorldMapScene._save_player_hp")
            save_patch.start()
            self.addCleanup(save_patch.stop)
            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_direction = "e"
            scene.player_x, scene.player_y = mob["x"] - 60, mob["y"]
            scene._mob_strike_player(mob)
            self.assertIsInstance(scene._player_facing_angle(), float)
        finally:
            pygame.quit()

    def test_miss_spawns_no_damage_number(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.player_x, scene.player_y, scene.player_direction = mob["x"] - 400, mob["y"], "e"

            scene._update_attack_target(0.0)
            self.assertIsNone(scene.attack_target)
            self.assertEqual(scene.damage_numbers, [])
            self.assertEqual(mob["hp"], mob["max_hp"])
        finally:
            pygame.quit()

    def test_saved_world_and_city_checkpoints_restore_exact_position(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from client.app_flow import checkpoint_for_scene, scene_for_saved_character
            from scenes.city_scene import CityScene
            from scenes.world_map_scene import WorldMapScene

            client = SimpleNamespace(get_map_terrain=terrain_payload,
                                     get_city_structures=city_structures)
            character = {"id": 1, "name": "Позиция", "level": 1, "type": "warrior"}
            world = WorldMapScene(SimpleNamespace(character=dict(character), client=client))
            world.player_x, world.player_y, world.player_direction = 4351.5, 2879.25, "nw"
            world_checkpoint = checkpoint_for_scene(world)
            resumed_world = scene_for_saved_character(
                SimpleNamespace(character=world_checkpoint, client=client))
            self.assertIsInstance(resumed_world, WorldMapScene)
            self.assertEqual((resumed_world.player_x, resumed_world.player_y,
                              resumed_world.player_direction), (4351.5, 2879.25, "nw"))

            city = CityScene(SimpleNamespace(character=dict(character), client=client))
            city.player_x, city.player_y, city.player_direction = 1450.5, 890.25, "e"
            city_checkpoint = checkpoint_for_scene(city)
            resumed_city = scene_for_saved_character(
                SimpleNamespace(character=city_checkpoint, client=client))
            self.assertIsInstance(resumed_city, CityScene)
            self.assertEqual((resumed_city.player_x, resumed_city.player_y,
                              resumed_city.player_direction), (1450.5, 890.25, "e"))
        finally:
            pygame.quit()

    def test_pause_menu_settings_stub_and_quit_action(self):
        from ui.exit_menu import ExitMenu

        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            menu = ExitMenu()
            menu.open()
            rendered_titles = []
            base_font = pygame.font.SysFont(settings.FONT_NAME, 20)
            base_small_font = pygame.font.SysFont(settings.FONT_NAME, 16)

            class RecordingFont:
                def __init__(self, wrapped_font):
                    self.wrapped_font = wrapped_font

                def render(self, text, *args):
                    rendered_titles.append(text)
                    return self.wrapped_font.render(text, *args)

                def __getattr__(self, name):
                    return getattr(self.wrapped_font, name)

            font = RecordingFont(base_font)
            small_font = RecordingFont(base_small_font)
            menu.draw(screen, font, small_font)
            self.assertIn("МЕНЮ", rendered_titles)
            self.assertIn("settings", menu.buttons)
            self.assertIn("quit", menu.buttons)
            menu.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=menu.buttons["settings"].center))
            self.assertEqual(menu.page, "settings")
            menu.draw(screen, font, small_font)
            menu.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=menu.buttons["back"].center))
            menu.draw(screen, font, small_font)
            action = menu.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=menu.buttons["quit"].center))
            self.assertEqual(action, "quit")
            self.assertFalse(menu.is_open)
            menu.begin_quit()
            self.assertFalse(menu.update_quit(2.5))
            self.assertEqual(menu.quit_remaining, 2.5)
            screen.fill((255, 255, 255))
            menu.draw(screen, font, small_font)
            self.assertLess(screen.get_at((0, 0)).r, 255)
            self.assertIn("Выход через 3...", rendered_titles)
            self.assertTrue(menu.update_quit(2.5))
            screen.fill((255, 255, 255))
            menu.draw(screen, font, small_font)
            self.assertIn("Выход через 0...", rendered_titles)
        finally:
            pygame.quit()

    def test_exit_disconnect_is_submitted_without_blocking_countdown(self):
        from client.app_flow import start_disconnect

        class FakeSession:
            character = {"id": 7, "name": "Test", "zone": "tavern"}
            disconnected = False

            def disconnect(self, fighter=None, character=None):
                self.disconnected = True
                self.checkpoint = character

        class FakeChat:
            closed = False

            def close(self):
                self.closed = True

        class FakeExecutor:
            def submit(self, function, **kwargs):
                self.function = function
                self.arguments = kwargs
                return "pending-disconnect"

        session = FakeSession()
        chat = FakeChat()
        executor = FakeExecutor()
        scene = SimpleNamespace(session=session, chat=chat, player=None)

        result = start_disconnect(scene, executor)

        self.assertEqual(result, "pending-disconnect")
        self.assertTrue(chat.closed)
        self.assertFalse(session.disconnected)
        executor.function(**executor.arguments)
        self.assertTrue(session.disconnected)
        self.assertEqual(session.checkpoint["id"], 7)

    def test_profile_key_action_opens_and_closes_player_card(self):
        from client.app_flow import toggle_player_profile

        class Overlay:
            def __init__(self):
                self.is_open = False
                self.profile = None

            def open(self, profile, counterpart=None):
                self.profile = profile
                self.is_open = True

            def close(self):
                self.profile = None
                self.is_open = False

        overlay = Overlay()
        character = {"id": 7, "name": "Тест"}
        scene = SimpleNamespace(
            session=SimpleNamespace(character=character),
            profile_overlay=overlay,
        )
        self.assertTrue(toggle_player_profile(scene))
        self.assertTrue(overlay.is_open)
        self.assertEqual(overlay.profile, character)
        self.assertTrue(toggle_player_profile(scene))
        self.assertFalse(overlay.is_open)

    def test_drag_pans_camera_without_selecting(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.camera_follow_player = True
            start_x, start_y = scene.camera_x, scene.camera_y
            down = (600, 500)
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=down))
            scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(down[0] - 80, down[1]),
                                                  rel=(-80, 0), buttons=(1, 0, 0)))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(down[0] - 80, down[1])))
            self.assertFalse(scene.camera_follow_player)
            self.assertGreater(scene.camera_x, start_x)
            self.assertAlmostEqual(scene.camera_y, start_y)
            self.assertIsNone(scene.active_entity)
        finally:
            pygame.quit()

    def _click(self, scene, pos, times=1):
        for _ in range(times):
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))

    def test_single_click_on_player_opens_nothing(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            screen_pos = scene.world_to_screen(scene.player_x, scene.player_y)
            pos = (int(screen_pos[0]), int(screen_pos[1]) - 28)
            self._click(scene, pos)
            self.assertIsNone(scene.active_entity)
            self.assertFalse(scene.profile_overlay.is_open)
            self.assertIsNone(scene.pinned_mob)
        finally:
            pygame.quit()

    def test_double_click_on_player_opens_left_profile_only(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            screen_pos = scene.world_to_screen(scene.player_x, scene.player_y)
            pos = (int(screen_pos[0]), int(screen_pos[1]) - 28)
            self._click(scene, pos, times=2)
            self.assertTrue(scene.profile_overlay.is_open)
            self.assertIsNone(scene.active_entity)
            self.assertIsNone(scene.pinned_mob)
            scene.draw(screen)
            self.assertTrue(scene.profile_overlay.player_frame.left < settings.WIDTH // 2)
        finally:
            pygame.quit()

    def test_double_click_on_mob_pins_card_and_x_closes_it(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            scene.camera_x, scene.camera_y = mob["x"], mob["y"]
            screen_pos = scene.world_to_screen(mob["x"], mob["y"])
            pos = (int(screen_pos[0]), int(screen_pos[1]))
            self.assertIs(scene._find_entity_at(pos), mob)
            self._click(scene, pos, times=2)
            self.assertIs(scene.pinned_mob, mob)
            self.assertFalse(scene.profile_overlay.is_open)
            scene.draw(screen)

            self._click(scene, scene._mob_card_close_rect().center)
            self.assertIsNone(scene.pinned_mob)
        finally:
            pygame.quit()

    def test_coords_box_is_drawn_under_hover_popups(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            order = []
            scene._draw_coords_box = lambda *args: order.append("coords")
            scene._draw_hover_popup = lambda *args: order.append("hover")
            scene._draw_active_window = lambda *args: order.append("active")
            scene.draw(screen)
            self.assertLess(order.index("coords"), order.index("active"))
            self.assertLess(order.index("coords"), order.index("hover"))
        finally:
            pygame.quit()

    def test_minimap_and_hud_are_drawn_under_cards(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            order = []
            scene._draw_minimap = lambda *args: order.append("minimap")
            scene._draw_hud = lambda *args: order.append("hud")
            scene._draw_active_window = lambda *args: order.append("active")
            scene._draw_hover_popup = lambda *args: order.append("hover")
            scene.draw(screen)
            self.assertLess(order.index("minimap"), order.index("active"))
            self.assertLess(order.index("minimap"), order.index("hover"))
            self.assertLess(order.index("hud"), order.index("hover"))
        finally:
            pygame.quit()

    def test_pinned_mob_card_closes_when_mob_dies(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace(),
                                                  add_currency=lambda **kwargs: None))
            mob = scene.mobs[0]
            mob["hp"] = 0
            scene._on_mob_defeated(mob)
            scene.update(0.016)
            self.assertIsNone(scene.pinned_mob)
        finally:
            pygame.quit()

    def test_mob_hover_card_draws_without_error(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.hovered_mobile_entity = None
            scene.hovered_entity = {"entity_kind": "mob", "name": "Скелет", "state": "idle",
                                    "hp": 7, "max_hp": 10, "fighter": None}
            scene._draw_hover_popup(screen, (0, 0))
        finally:
            pygame.quit()

    def test_mob_hover_card_shows_while_profile_overlay_is_open(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.profile_overlay.open(scene._own_player_card_profile())
            scene.hovered_mobile_entity = None
            scene.hovered_entity = {"entity_kind": "mob", "name": "Скелет", "state": "idle",
                                    "hp": 7, "max_hp": 10, "fighter": scene._build_mob_fighter()}
            calls = []
            scene._draw_mob_hover_card = lambda surf, *a, **k: calls.append(surf)
            scene._draw_hover_popup(screen, (0, 0))
            self.assertEqual(calls, [screen])
        finally:
            pygame.quit()

    def test_skeleton_fighter_has_base_stats_and_level(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import MOB_LEVEL, MOB_STATS, WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            fighter = scene._build_mob_fighter()
            self.assertEqual(fighter.level, MOB_LEVEL)
            for stat_key, value in MOB_STATS.items():
                self.assertEqual(fighter.stats[stat_key], value, stat_key)
            self.assertEqual(fighter.stats["strength"], 3)
        finally:
            pygame.quit()

    def test_hovering_own_player_shows_player_card_not_tooltip(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.hovered_mobile_entity = None
            scene.hovered_entity = scene._find_entity_at(scene.world_to_screen(scene.player_x, scene.player_y))
            self.assertEqual(scene.hovered_entity["id"], "player")
            calls = []
            scene._draw_own_player_hover_card = lambda surf: calls.append(surf)
            scene._draw_hover_popup(screen, (0, 0))
            self.assertEqual(calls, [screen])
        finally:
            pygame.quit()

    def test_own_player_hover_card_draws_without_error(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            from ui.character_card import CharacterCard

            CharacterCard._REGISTRY.pop("1", None)
            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Тестовый"}, client=SimpleNamespace()))
            scene._draw_own_player_hover_card(screen)
            self.assertEqual(CharacterCard._REGISTRY["1"].state["name"], "Тестовый")
        finally:
            pygame.quit()

    def test_own_player_hover_card_is_drawn_on_left_side(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            from ui.character_card import CharacterCard

            CharacterCard._REGISTRY.pop("1", None)
            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Левый"}, client=SimpleNamespace()))
            drawn_rects = []
            original_draw = CharacterCard.draw

            def spy_draw(card, surface, frame, *args, **kwargs):
                drawn_rects.append(pygame.Rect(frame))
                return original_draw(card, surface, frame, *args, **kwargs)

            CharacterCard.draw = spy_draw
            try:
                scene._draw_own_player_hover_card(screen)
            finally:
                CharacterCard.draw = original_draw
            self.assertEqual(drawn_rects, [pygame.Rect(settings.PLAYER_CARD_RECT)])
            self.assertLess(drawn_rects[0].right, settings.WIDTH // 2)
        finally:
            pygame.quit()

    def test_own_player_card_shows_hp_after_mob_hit(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 7, "name": "Удар"}, client=SimpleNamespace()))
            profile = scene._own_player_card_profile()
            scene.combat_fighter.hp = max(0, scene.combat_fighter.hp - 9)
            updated = scene._own_player_card_profile()
            self.assertEqual(updated["hp"], profile["hp"] - 9)
            self.assertEqual(updated["hp"], scene.combat_fighter.hp)
            self.assertEqual(updated["max_hp"], scene.combat_fighter.max_hp)
        finally:
            pygame.quit()

    def test_checkpoint_keeps_fighter_hp_after_combat(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from client.app_flow import checkpoint_for_scene
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 8, "name": "Чек"}, client=SimpleNamespace()))
            scene.combat_fighter.hp = 17
            scene.combat_fighter.mp = 4
            checkpoint = checkpoint_for_scene(scene)
            self.assertEqual(checkpoint["hp"], 17)
            self.assertEqual(checkpoint["mp"], 4)
        finally:
            pygame.quit()

    def test_mob_hit_saves_player_hp_to_server(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            saved = []
            session = SimpleNamespace(
                character={"id": 9, "name": "Сервер"},
                client=SimpleNamespace(),
                save_fighter=lambda fighter: saved.append(fighter.hp),
            )
            scene = WorldMapScene(session)
            mob = scene.mobs[0] if getattr(scene, "mobs", None) else None
            if mob is None:
                self.skipTest("на карте нет мобов")
            scene.combat_fighter.hp = 50
            scene._hp_dirty = True
            with patch("scenes.world_map_scene.resolve_world_melee_attack",
                       return_value={"outcome": "hit", "damage": 7, "critical": False}):
                scene._mob_strike_player(mob)
            self.assertEqual(scene.combat_fighter.hp, 43)
            self.assertEqual(saved, [43])
            self.assertFalse(scene._hp_dirty)
        finally:
            pygame.quit()

    def test_regen_save_is_throttled_and_reaches_server(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import PLAYER_HP_SAVE_INTERVAL, WorldMapScene

            saved = []
            session = SimpleNamespace(
                character={"id": 10, "name": "Реген"},
                client=SimpleNamespace(),
                save_fighter=lambda fighter: saved.append(fighter.hp),
            )
            scene = WorldMapScene(session)
            scene.combat_fighter.hp = 1
            scene.combat_fighter.max_hp = 100
            scene._hp_dirty = True
            scene._hp_save_timer = 0.0
            scene._flush_player_hp(0.1)
            self.assertEqual(saved, [])
            scene._flush_player_hp(PLAYER_HP_SAVE_INTERVAL)
            self.assertEqual(len(saved), 1)
            self.assertFalse(scene._hp_dirty)
        finally:
            pygame.quit()

    def test_server_error_on_hp_save_shows_notice_and_keeps_game_running(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from client.network import ServerError
            from scenes.world_map_scene import WorldMapScene

            def fail(fighter):
                raise ServerError("нет связи")

            session = SimpleNamespace(
                character={"id": 11, "name": "Ошибка"},
                client=SimpleNamespace(),
                save_fighter=fail,
            )
            scene = WorldMapScene(session)
            scene._save_player_hp()
            self.assertEqual(scene.action_notice, "нет связи")
        finally:
            pygame.quit()

    def test_passive_session_regen_does_not_touch_world_map(self):
        from client.app_flow import apply_passive_regen
        from scenes.world_map_scene import WorldMapScene

        calls = []

        class Session:
            def passive_regenerate(self, dt):
                calls.append(dt)

        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            scene = WorldMapScene(SimpleNamespace(character={"id": 12, "name": "Бой"}, client=SimpleNamespace()))
            scene.session = Session()
            apply_passive_regen(scene, 0.5)
            self.assertEqual(calls, [])
        finally:
            pygame.quit()

    def test_movement_keys_work_while_profile_overlay_is_open(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.profile_overlay.open(scene.session.character, None)
            self.assertTrue(scene.profile_overlay.is_open)
            self.assertFalse(scene._keyboard_movement_blocked())
        finally:
            pygame.quit()

    def test_skeleton_carries_thirty_copper(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import MOB_COINS, WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            skeleton = next(m for m in scene.mobs if m.get("entity_kind") == "mob")
            self.assertEqual(skeleton["coins"], {"copper": 30, "silver": 0, "gold": 0})
            self.assertEqual(MOB_COINS, {"copper": 30, "silver": 0, "gold": 0})
        finally:
            pygame.quit()

    def test_mob_kill_rewards_hero_with_twenty_percent_of_coins(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from core.currency import Currency
            from client.network import ServerError
            from scenes.world_map_scene import WorldMapScene

            granted = []

            class FakeSession:
                character = {"id": 1, "name": "Т"}
                client = SimpleNamespace()

                def add_currency(self, copper=0, silver=0, gold=0):
                    granted.append(copper)

            scene = WorldMapScene(FakeSession())
            mob = next(m for m in scene.mobs if m.get("entity_kind") == "mob")
            scene._on_mob_defeated(mob)
            self.assertEqual(granted, [6])
            self.assertEqual(mob["coins"], {"copper": 0, "silver": 0, "gold": 0})

            scene._respawn_mob(mob)
            self.assertEqual(mob["coins"], {"copper": 30, "silver": 0, "gold": 0})

            def failing_add(copper=0, silver=0, gold=0):
                raise ServerError("нет связи")

            FakeSession.add_currency = staticmethod(failing_add)
            scene._on_mob_defeated(mob)
            self.assertEqual(scene.action_notice, "нет связи")
            self.assertEqual(Currency.to_copper(**mob["coins"]), 0)
        finally:
            pygame.quit()

    def test_mob_card_shows_coins(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            drawn_currency = []
            card = scene._mob_card()
            original = card._draw_currency

            def spy(screen_arg, x, y, currency):
                drawn_currency.append(dict(currency))
                return original(screen_arg, x, y, currency)

            card._draw_currency = spy
            mob = {"entity_kind": "mob", "name": "Скелет", "state": "idle", "hp": 68, "max_hp": 68,
                   "fighter": scene._build_mob_fighter(), "coins": {"copper": 30, "silver": 0, "gold": 0}}
            scene._draw_mob_hover_card(screen, mob=mob)
            self.assertEqual(drawn_currency, [{"copper": 30, "silver": 0, "gold": 0}])
        finally:
            pygame.quit()

    def test_mob_card_lists_all_stats(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            drawn = []
            card = scene._mob_card()
            real_font = card.small_font

            class SpyFont:
                def __getattr__(self, name):
                    return getattr(real_font, name)

                def render(self, text, *args, **kwargs):
                    drawn.append(text)
                    return real_font.render(text, *args, **kwargs)

            card.small_font = SpyFont()
            mob = {"entity_kind": "mob", "name": "Скелет", "state": "idle", "hp": 68, "max_hp": 68,
                   "fighter": scene._build_mob_fighter()}
            scene._draw_mob_hover_card(screen, mob=mob)
            self.assertIn("Уровень 1", drawn)
            for stat_name in ("Сила: 3", "Ловкость: 3", "Интуиция: 3", "Мудрость: 3",
                              "Интеллект: 3", "Выносливость: 4"):
                self.assertTrue(any(stat_name in text for text in drawn), stat_name)
        finally:
            pygame.quit()

    def test_mob_overhead_shows_hp_label(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Ратник"}, client=SimpleNamespace()))
            mob = scene.mobs[0]
            mob["hp"] = 17
            mob["max_hp"] = 68
            mob["sprite"] = pygame.Surface((90, 53))
            scene.mobs = [mob]
            scene.world_to_screen = lambda x, y: (settings.WIDTH // 2, settings.HEIGHT // 2)
            drawn = []
            real_render = scene.grid_font.render
            scene.grid_font = SimpleNamespace(render=lambda text, *a: drawn.append(text) or real_render(text, *a))
            scene._draw_mobs(screen)
            self.assertIn("ХП 17/68", drawn)
        finally:
            pygame.quit()

    def test_player_overhead_shows_name_hp_and_mp(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Ратник"}, client=SimpleNamespace()))
            scene.combat_fighter.hp = 40
            scene.combat_fighter.max_hp = 60
            scene.combat_fighter.mp = 5
            scene.combat_fighter.max_mp = 20
            drawn = []
            real_render = scene.grid_font.render
            scene.grid_font = SimpleNamespace(render=lambda text, *a: drawn.append(text) or real_render(text, *a))
            scene.small_font = SimpleNamespace(render=lambda text, *a: drawn.append(text) or pygame.Surface((1, 1)))
            scene._draw_player_character(screen)
            self.assertIn("Ратник", drawn)
            self.assertIn("ХП 40/60", drawn)
            self.assertIn("МП 5/20", drawn)
        finally:
            pygame.quit()

    def test_player_overhead_bars_are_twice_as_tall(self):
        from scenes.world_map_scene import WorldMapScene
        self.assertEqual(WorldMapScene.OVERHEAD_BAR_HEIGHT, 10)

    def test_terrain_comes_from_server(self):
        database = create_test_database()
        try:
            with running_server(database) as client:
                client.register("mapuser", "secret1")
                client.login("mapuser", "secret1")
                terrain = client.get_map_terrain()
        finally:
            drop_test_database(database)
        self.assertEqual(terrain["obstacles"][0]["id"], "mountains_1")
        self.assertTrue(terrain["obstacles"][0]["peaks"])

    def test_player_cannot_walk_into_mountains(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            client = SimpleNamespace(get_map_terrain=lambda: terrain_payload(city_level=2))
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=client))
            self.assertTrue(scene._check_collision(4400, 2880))
            scene.player_x, scene.player_y = 3500, 2880
            # ПКМ по точке за горами: путь обходит препятствия, персонаж не заходит в горы
            scene._set_move_target((3700, 2880))
            for _ in range(600):
                scene.update(1 / 30)
            self.assertTrue(is_passable(scene.player_x, scene.player_y))
            self.assertLess(scene.player_x, 3900)
            # С юга по проходу можно подойти к входу в разлом
            scene.player_x, scene.player_y = 4240, 3470
            scene._set_move_target((4240, 3300))
            for _ in range(300):
                scene.update(1 / 30)
            self.assertLess(scene.player_y, 3470)
            self.assertTrue(is_passable(scene.player_x, scene.player_y))
            rift = next(obj for obj in scene.objects if obj["id"] == "mountain_rift")
            self.assertTrue(scene._is_within_one_tile(rift))
            scene.camera_x, scene.camera_y = 4400, 2880
            scene.draw(screen)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
