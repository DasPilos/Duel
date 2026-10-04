import math
import unittest
from types import SimpleNamespace

import pygame

from core import settings
from server.world_map import OBSTACLES, _edge_distance, is_passable, point_in_polygon, terrain_payload
from server.structures import WORLD_OBJECTS, city_structures
from server import presence
from server.world_roads import COUNTRY_BUILDINGS, CITY_GATES, roads_payload
from tests.fixtures import create_test_database, drop_test_database, running_server


class WorldTerrainTests(unittest.TestCase):
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
        # Вход в лагерь лесорубов остаётся снаружи леса
        self.assertTrue(is_passable(1232, 3664))
        forest = next(obstacle for obstacle in OBSTACLES if obstacle["id"] == "forest_1")
        self.assertGreater(len(forest["trees"]), 300)
        points = forest["points"]
        for index in range(len(points)):
            (ax, ay), (bx, by), (cx, cy) = points[index - 2], points[index - 1], points[index]
            turn = abs(math.atan2(cy - by, cx - bx) - math.atan2(by - ay, bx - ax))
            turn = min(turn, 2 * math.pi - turn)
            self.assertLess(math.degrees(turn), 45)

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
        roads = roads_payload()
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
        for object_id in ("wheat_farm", "lumber_camp", "mountain_rift", "barnyard", "black_pit", "town_radburg"):
            self.assertIn(object_id, world_ids)
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
            client = SimpleNamespace(get_map_terrain=terrain_payload)
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
