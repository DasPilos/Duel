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

    def test_saved_world_and_city_checkpoints_restore_exact_position(self):
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
        from main import start_disconnect

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
            scene.player_target = (4400, 2880)
            for _ in range(600):
                scene.update(1 / 30)
            self.assertTrue(is_passable(scene.player_x, scene.player_y))
            self.assertLess(scene.player_x, 3900)
            # С юга по проходу можно подойти к входу в разлом
            scene.player_x, scene.player_y = 4240, 3470
            scene.player_target = (4240, 3328)
            for _ in range(300):
                scene.update(1 / 30)
            self.assertEqual((scene.player_x, scene.player_y), (4240, 3328))
            rift = next(obj for obj in scene.objects if obj["id"] == "mountain_rift")
            self.assertTrue(scene._is_within_one_tile(rift))
            scene.camera_x, scene.camera_y = 4400, 2880
            scene.draw(screen)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
