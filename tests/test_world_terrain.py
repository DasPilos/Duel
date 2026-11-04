import math
import time
import unittest
from types import SimpleNamespace

import pygame

from core import settings
from core.map_config import KOBOLD_SPAWN_TILE, MAP_VERSION, TILE_SIZE as T
from server.world_map import OBSTACLES, _edge_distance, is_passable, point_in_polygon, terrain_payload
from server.structures import WORLD_OBJECTS, city_structures
from server import presence
from server.world_roads import COUNTRY_BUILDINGS, CITY_GATES, roads_payload
from tests.fixtures import create_test_database, drop_test_database, running_server


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
        from ui.map_travel import _format_eta, _format_phase_eta

        self.assertEqual(_format_eta(89999), "24:59:59")
        self.assertEqual(_format_eta(61), "00:01:01")
        self.assertEqual(_format_eta(-1), "00:00:00")
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

    def test_new_world_map_has_only_the_respawn_crystal(self):
        terrain = terrain_payload()
        self.assertEqual(terrain["map_version"], MAP_VERSION)
        self.assertEqual(terrain["tile_size"], 48)
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (256, 128))
        self.assertEqual(terrain["city_area"]["bounds"][0], 0)
        self.assertNotIn("forest_area", terrain)
        self.assertNotIn("graveyard_area", terrain)
        self.assertEqual(len(terrain["objects"]), 1)
        crystal = terrain["objects"][0]
        self.assertEqual(crystal["id"], "crystal_of_life")
        self.assertEqual((crystal["tile_x"], crystal["tile_y"]), (11, 33))
        self.assertEqual((crystal["tile_w"], crystal["tile_h"]), (3, 3))
        self.assertEqual(crystal["solid_rects"], [[11 * T, 33 * T, 3 * T, 3 * T]])
        self.assertEqual(terrain["obstacles"], [])
        self.assertEqual(terrain["roads"], {"routes": [], "tiles": [], "travel_seconds": 0})

    def test_structures_come_from_server(self):
        from client.network import ServerError

        database = create_test_database()
        try:
            with running_server(database) as client:
                client.register("builder", "secret1")
                client.login("builder", "secret1")
                terrain = client.get_map_terrain()
                with self.assertRaises(ServerError):
                    client.get_city_structures()
        finally:
            drop_test_database(database)
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (256, 128))
        self.assertEqual([obj["id"] for obj in terrain["objects"]], ["crystal_of_life"])
        crystal = terrain["objects"][0]
        self.assertEqual((crystal["tile_x"], crystal["tile_y"], crystal["tile_w"], crystal["tile_h"]),
                         (11, 33, 3, 3))
        self.assertEqual(terrain["obstacles"], [])
        self.assertEqual(terrain["roads"]["routes"], [])
        self.assertEqual(terrain["roads"]["tiles"], [])
        self.assertIn("city_area", terrain)
        self.assertNotIn("city_visual_state", terrain)

    def test_legacy_server_map_is_replaced_with_current_layout(self):
        from scenes.world_map_scene import WorldMapScene

        town = next(obj for obj in WORLD_OBJECTS if obj["id"] == "town_radburg")

        class Client:
            def get_map_terrain(self):
                return {
                    "objects": [town],
                    "obstacles": [{"id": "old_lake"}],
                    "roads": {"routes": [{"building_id": "old_farm"}],
                              "tiles": [[20, 20]], "travel_seconds": 60},
                }

        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            scene = WorldMapScene(SimpleNamespace(
                character={"id": 1, "name": "Test"}, client=Client(),
            ))
            self.assertEqual((scene.grid_w, scene.grid_h), (256, 128))
            self.assertEqual([obj["id"] for obj in scene.objects], [
                "crystal_of_life", "library", "talent_tree",
            ])
            self.assertEqual(scene.city_bounds[0], 0)
            self.assertFalse(scene.show_outside_city_locations)
            self.assertEqual(scene.graveyard_bounds, (0, 0, 0, 0))
            scene.player_x = KOBOLD_SPAWN_TILE[0] * T + T // 2
            scene.player_y = KOBOLD_SPAWN_TILE[1] * T + T // 2
            scene._check_kobold_encounter()
            scene._update_dungeon_gate(5.0)
            self.assertIsNone(scene.arena)
            self.assertIsNone(scene.dungeon_entry_elapsed)
            self.assertEqual(
                (scene.objects[0]["tile_x"], scene.objects[0]["tile_y"],
                 scene.objects[0]["tile_w"], scene.objects[0]["tile_h"]),
                (11, 33, 3, 3),
            )
            self.assertEqual(scene.obstacles, [])
            self.assertEqual(scene.road_tiles, set())
            self.assertEqual(scene.road_routes, [])
            self.assertEqual(scene.road_travel_seconds, 0)
        finally:
            pygame.quit()

    def test_scene_without_server_has_no_structures(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            self.assertEqual([obj["id"] for obj in scene.objects], ["library", "talent_tree"])
            self.assertEqual(scene.obstacles, [])
        finally:
            pygame.quit()

    def test_world_map_player_draw_handles_missing_character(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            client = SimpleNamespace(
                get_player_work=lambda _character_id: self.fail(
                    "Player work must not be loaded without a selected character"
                ),
            )
            scene = WorldMapScene(SimpleNamespace(character=None, client=client))

            scene._draw_player_character(screen)
        finally:
            pygame.quit()

    def test_clicking_player_opens_profile_and_backpack(self):
        pygame.init()
        try:
            screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            session = SimpleNamespace(
                character={"id": 1, "name": "Тестовый герой", "level": 1, "type": "warrior"},
                client=SimpleNamespace(),
                social_snapshot=lambda location: {
                    "occupants": [], "messages": [], "offers": [],
                    "my_application": None, "group_offers": [],
                },
            )
            scene = WorldMapScene(session)
            self.assertEqual(scene.chat.location, "world_map")
            player_screen = scene.world_to_screen(scene.player_x, scene.player_y)
            scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=(player_screen[0], player_screen[1] - 28)))
            self.assertEqual(scene.active_entity["id"], "player")
            scene.draw(screen)

            rendered = []
            original_font = scene.small_font

            class Recorder:
                def render(self, text, *args):
                    rendered.append(text)
                    return original_font.render(text, *args)

                def __getattr__(self, name):
                    return getattr(original_font, name)

            scene.small_font = Recorder()
            try:
                scene.draw(screen)
            finally:
                scene.small_font = original_font
            self.assertIn("ИНФОРМАЦИЯ", rendered)

            scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=scene.active_action_button.center))
            self.assertTrue(scene.profile_overlay.is_open)
            scene.draw(screen)
            self.assertTrue(scene.profile_overlay.player_frame.left < settings.WIDTH // 2)

            scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=scene.profile_overlay.backpack_button.center))
            self.assertTrue(scene.profile_overlay.inventory_requested)
        finally:
            if "scene" in locals() and scene.chat is not None:
                scene.chat.close()
            pygame.quit()

    def test_world_checkpoints_restore_position_and_legacy_city_checkpoint_migrates(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from main import checkpoint_for_scene, scene_for_saved_character
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
            self.assertIsInstance(resumed_city, WorldMapScene)
            self.assertEqual(
                (int(resumed_city.player_x // T), int(resumed_city.player_y // T)),
                (12, 36),
            )
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
            self.assertFalse(hasattr(menu, "begin_quit"))
        finally:
            pygame.quit()

    def test_profile_key_action_opens_and_closes_player_card(self):
        from main import toggle_player_profile

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

    def test_server_returns_new_map_with_respawn_crystal_only(self):
        database = create_test_database()
        try:
            with running_server(database) as client:
                client.register("mapuser", "secret1")
                client.login("mapuser", "secret1")
                terrain = client.get_map_terrain()
        finally:
            drop_test_database(database)
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (256, 128))
        self.assertEqual([obj["id"] for obj in terrain["objects"]], ["crystal_of_life"])
        self.assertEqual(
            (terrain["objects"][0]["tile_x"], terrain["objects"][0]["tile_y"],
             terrain["objects"][0]["tile_w"], terrain["objects"][0]["tile_h"]),
            (11, 33, 3, 3),
        )
        self.assertEqual(terrain["obstacles"], [])
        self.assertEqual(terrain["roads"]["routes"], [])

    def test_new_map_has_only_crystal_and_respects_its_boundaries(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            client = SimpleNamespace(get_map_terrain=terrain_payload)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=client))
            self.assertEqual((scene.grid_w, scene.grid_h), (256, 128))
            self.assertEqual(
                (int(scene.player_x // T), int(scene.player_y // T)),
                (12, 36),
            )
            self.assertEqual([obj["id"] for obj in scene.objects], [
                "crystal_of_life", "library", "talent_tree",
            ])
            crystal = scene.objects[0]
            self.assertEqual(
                (crystal["tile_x"], crystal["tile_y"], crystal["tile_w"], crystal["tile_h"]),
                (11, 33, 3, 3),
            )
            self.assertEqual(crystal["solid_rects"], [pygame.Rect(11 * T, 33 * T, 3 * T, 3 * T)])
            self.assertEqual(scene.obstacles, [])
            self.assertFalse(scene._check_collision(scene.world_w / 2, scene.world_h / 2))
            self.assertTrue(scene._check_collision(12 * T + T // 2, 34 * T + T // 2))
            self.assertTrue(scene._check_collision(scene.world_w + 1, scene.world_h / 2))
        finally:
            pygame.quit()

    def test_legacy_city_save_resumes_on_the_new_world_map(self):
        from main import scene_for_saved_character
        from scenes.world_map_scene import WorldMapScene

        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            session = SimpleNamespace(
                character={
                    "id": 1, "name": "Перенесённый герой", "zone": "city",
                    "position_x": 1600, "position_y": 1600,
                },
                client=SimpleNamespace(get_map_terrain=lambda: terrain_payload()),
            )
            scene = scene_for_saved_character(session)
            self.assertIsInstance(scene, WorldMapScene)
            self.assertEqual(
                (int(scene.player_x // T), int(scene.player_y // T)),
                (12, 36),
            )
            new_character = SimpleNamespace(
                character={"id": 2, "name": "Новый герой"},
                client=SimpleNamespace(get_map_terrain=lambda: terrain_payload()),
            )
            new_scene = scene_for_saved_character(new_character)
            self.assertIsInstance(new_scene, WorldMapScene)
            self.assertEqual(
                (int(new_scene.player_x // T), int(new_scene.player_y // T)),
                (12, 36),
            )
        finally:
            pygame.quit()

    def test_city_walls_surround_crystal_with_east_gate(self):
        from core.map_config import is_city_tile

        area = terrain_payload()["city_area"]
        self.assertEqual(area["bounds"], [0, 25, 25, 19])
        self.assertEqual(area["gate_tiles"], [[24, 33], [24, 34], [24, 35]])
        walls = {tuple(tile) for tile in area["wall_tiles"]}
        ring = walls | {tuple(tile) for tile in area["gate_tiles"]}
        expected_ring = {
            (x, y) for x in range(25) for y in range(25, 44)
            if x in (0, 24) or y in (25, 43)
        }
        self.assertEqual(ring, expected_ring)
        self.assertEqual(walls, expected_ring - {(24, 33), (24, 34), (24, 35)})
        self.assertTrue(is_city_tile(11, 33))
        crystal = terrain_payload()["objects"][0]
        left, top, width, height = area["bounds"]
        self.assertEqual(crystal["tile_x"] * 2 + crystal["tile_w"], left * 2 + width)
        self.assertEqual(crystal["tile_y"] * 2 + crystal["tile_h"], top * 2 + height)
        self.assertTrue(is_city_tile(24, 33))
        self.assertTrue(is_city_tile(1, 42))
        self.assertFalse(is_city_tile(25, 33))
        self.assertFalse(is_city_tile(-1, 33))
        self.assertFalse(is_city_tile(12, 24))
        self.assertFalse(is_city_tile(12, 44))

        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(
                character={"id": 1, "name": "Т"},
                client=SimpleNamespace(get_map_terrain=terrain_payload),
            ))
            for x, y in walls:
                self.assertTrue(scene._check_collision(x * T + T // 2, y * T + T // 2))
            for x, y in area["gate_tiles"]:
                self.assertFalse(scene._check_collision(x * T + T // 2, y * T + T // 2))
            self.assertFalse(scene._check_collision(20 * T + T // 2, 30 * T + T // 2))
            scene.player_x, scene.player_y = 1 * T + T // 2, 42 * T + T // 2
            self.assertTrue(scene.player_in_city())
            self.assertFalse(scene.player_in_forest())
            self.assertNotIn("forest_area", terrain_payload())
            self.assertNotIn("graveyard_area", terrain_payload())
            scene.player_x, scene.player_y = 15 * T + T // 2, 33 * T + T // 2
            self.assertTrue(scene.player_in_city())
            scene.player_x = 25 * T
            self.assertFalse(scene.player_in_city())
        finally:
            pygame.quit()

    def test_respawn_crystal_restores_health_when_player_is_nearby(self):
        from scenes.world_map_scene import WorldMapScene

        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            saved = []

            class Client:
                def get_map_terrain(self):
                    return terrain_payload()

                def save_character(self, character):
                    saved.append(dict(character))

            character = {"id": 1, "name": "Т", "hp": 5, "max_hp": 120}
            scene = WorldMapScene(SimpleNamespace(character=character, client=Client()))
            scene.active_entity = scene.objects[0]
            scene.player_x, scene.player_y = scene.objects[0]["approach_pos"]

            scene._trigger_active_action()

            self.assertEqual(character["hp"], 120)
            self.assertEqual(saved[0]["hp"], 120)
            self.assertEqual(scene.action_notice, "Здоровье полностью восстановлено!")
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
