import unittest
from types import SimpleNamespace

import pygame

from kaloda import settings
from kaloda.map_config import (
    KOBOLD_SPAWN_TILE,
    MAP_VERSION,
    RESPAWN_CRYSTAL,
    TAVERN_BOUNDS,
    TAVERN_EXIT_POS,
    TILE_SIZE as T,
    is_city_tile,
    is_tavern_tile,
)
from kaloda.scenes.world_map_scene import WorldMapScene
from kaloda.world_map import point_in_polygon, terrain_payload


class TestTerrainPayload(unittest.TestCase):
    def test_payload_has_only_the_crystal_city_and_library(self):
        terrain = terrain_payload()

        self.assertEqual(terrain["map_version"], MAP_VERSION)
        self.assertEqual((terrain["width_tiles"], terrain["height_tiles"]), (128, 256))
        self.assertEqual([obj["id"] for obj in terrain["objects"]], ["crystal_of_life"])
        crystal = terrain["objects"][0]
        self.assertEqual((crystal["tile_x"], crystal["tile_y"], crystal["tile_w"], crystal["tile_h"]),
                         (11, 33, 3, 3))
        self.assertEqual(terrain["obstacles"], [])
        self.assertEqual(terrain["roads"], {"routes": [], "tiles": [], "travel_seconds": 0})
        self.assertNotIn("forest_area", terrain)
        self.assertNotIn("graveyard_area", terrain)

    def test_city_walls_surround_the_crystal_with_an_east_gate(self):
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
        self.assertTrue(is_city_tile(24, 33))
        self.assertFalse(is_city_tile(25, 33))
        self.assertFalse(is_city_tile(12, 44))

    def test_point_in_polygon(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]

        self.assertTrue(point_in_polygon((5, 5), square))
        self.assertFalse(point_in_polygon((15, 5), square))


class TestWorldMapScene(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        self.addCleanup(pygame.quit)
        self.scenes = []

    def tearDown(self):
        for scene in self.scenes:
            if scene.chat is not None:
                scene.chat.close()

    def _scene(self, character=None, client=None, **session_fields):
        session = SimpleNamespace(
            character={"id": 1, "name": "Т"} if character is None else character,
            client=SimpleNamespace(get_map_terrain=terrain_payload) if client is None else client,
            **session_fields,
        )
        scene = WorldMapScene(session)
        self.scenes.append(scene)
        return scene

    def test_new_map_has_only_crystal_and_respects_its_boundaries(self):
        scene = self._scene()

        self.assertEqual((scene.grid_w, scene.grid_h), (128, 256))
        self.assertEqual((int(scene.player_x // T), int(scene.player_y // T)), (12, 36))
        self.assertEqual([obj["id"] for obj in scene.objects], ["crystal_of_life", "library", "talent_tree"])
        crystal = scene.objects[0]
        self.assertEqual(crystal["solid_rects"], [pygame.Rect(11 * T, 33 * T, 3 * T, 3 * T)])
        self.assertEqual(scene.obstacles, [])
        self.assertFalse(scene._check_collision(scene.world_w / 2, scene.world_h / 2))
        self.assertTrue(scene._check_collision(12 * T + T // 2, 34 * T + T // 2))
        self.assertTrue(scene._check_collision(scene.world_w + 1, scene.world_h / 2))

    def test_legacy_server_data_is_replaced_with_the_current_layout(self):
        legacy_town = {"id": "town_radburg", "name": "Радбург", "tile_x": 5, "tile_y": 5, "tile_w": 15, "tile_h": 15}

        class Client:
            def get_map_terrain(self):
                return {
                    "objects": [legacy_town],
                    "obstacles": [{"id": "old_lake"}],
                    "roads": {"routes": [{"building_id": "old_farm"}], "tiles": [[20, 20]], "travel_seconds": 60},
                }

        scene = self._scene(client=Client())

        self.assertEqual([obj["id"] for obj in scene.objects], ["crystal_of_life", "library", "talent_tree"])
        self.assertEqual(scene.obstacles, [])
        self.assertEqual(scene.road_tiles, set())
        self.assertFalse(scene.show_outside_city_locations)
        self.assertEqual(scene.graveyard_bounds, (0, 0, 0, 0))
        scene.player_x = KOBOLD_SPAWN_TILE[0] * T + T // 2
        scene.player_y = KOBOLD_SPAWN_TILE[1] * T + T // 2
        scene._check_kobold_encounter()
        self.assertIsNone(scene.arena)

    def test_scene_without_terrain_from_the_server_still_has_its_buildings(self):
        scene = self._scene(client=SimpleNamespace())

        self.assertEqual([obj["id"] for obj in scene.objects], ["library", "talent_tree"])
        self.assertEqual(scene.obstacles, [])

    def test_city_walls_block_movement_but_the_gate_is_open(self):
        scene = self._scene()
        area = terrain_payload()["city_area"]

        for x, y in area["wall_tiles"]:
            self.assertTrue(scene._check_collision(x * T + T // 2, y * T + T // 2))
        for x, y in area["gate_tiles"]:
            self.assertFalse(scene._check_collision(x * T + T // 2, y * T + T // 2))
        self.assertFalse(scene._check_collision(20 * T + T // 2, 30 * T + T // 2))
        scene.player_x, scene.player_y = 1 * T + T // 2, 42 * T + T // 2
        self.assertTrue(scene.player_in_city())
        self.assertFalse(scene.player_in_forest())
        scene.player_x = 25 * T
        self.assertFalse(scene.player_in_city())

    def test_entering_the_tavern_door_leaves_the_map_for_the_tavern(self):
        scene = self._scene()
        left, top, width, _ = TAVERN_BOUNDS
        self.assertTrue(is_tavern_tile(left, top))
        self.assertFalse(is_tavern_tile(left + width, top))
        self.assertTrue(is_city_tile(left, top))

        scene.player_x, scene.player_y = (left + width + 0.5) * T, (top + 0.5) * T
        scene._check_kobold_encounter()
        self.assertFalse(scene.finished)

        scene.player_x = (left + width - 0.5) * T
        scene._check_kobold_encounter()
        self.assertTrue(scene.finished)
        self.assertEqual(scene.navigate, "tavern")
        self.assertIsNone(scene.player_target)

    def test_street_in_front_of_the_tavern_is_free_and_does_not_reenter_it(self):
        x, y = TAVERN_EXIT_POS
        scene = self._scene()
        scene.player_x, scene.player_y = x, y

        self.assertFalse(is_tavern_tile(int(x // T), int(y // T)))
        self.assertFalse(scene._check_collision(x, y))
        scene.draw(self.screen)

        returned = WorldMapScene(scene.session, spawn_pos=(x, y, "s"))
        self.scenes.append(returned)
        returned._check_kobold_encounter()
        self.assertFalse(returned.finished)

    def test_drawing_without_a_selected_character_does_not_crash(self):
        scene = self._scene(character=None)
        scene.session.character = None

        scene._draw_player_character(self.screen)
        scene.draw(self.screen)

    def test_respawn_crystal_restores_health_when_player_is_nearby(self):
        saved = []

        class Client:
            def get_map_terrain(self):
                return terrain_payload()

            def save_character(self, character):
                saved.append(dict(character))

        character = {"id": 1, "name": "Т", "hp": 5, "max_hp": 120}
        scene = self._scene(character=character, client=Client())
        scene.active_entity = scene.objects[0]
        scene.player_x, scene.player_y = RESPAWN_CRYSTAL["approach_pos"]

        scene._trigger_active_action()

        self.assertEqual(character["hp"], 120)
        self.assertEqual(saved[0]["hp"], 120)
        self.assertEqual(scene.action_notice, "Здоровье полностью восстановлено!")

    def test_clicking_the_player_opens_the_profile_and_backpack_request(self):
        scene = self._scene(
            character={"id": 1, "name": "Тестовый герой", "level": 1, "type": "warrior"},
            client=SimpleNamespace(get_map_terrain=terrain_payload),
            social_snapshot=lambda location, position=None: {
                "occupants": [], "messages": [], "offers": [],
                "my_application": None, "group_offers": [],
            },
        )
        self.assertEqual(scene.chat.location, "world_map")
        player_screen = scene.world_to_screen(scene.player_x, scene.player_y)

        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(player_screen[0], player_screen[1] - 28)))
        self.assertEqual(scene.active_entity["id"], "player")
        scene.draw(self.screen)

        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=scene.active_action_button.center))
        self.assertTrue(scene.profile_overlay.is_open)
        scene.draw(self.screen)
        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=scene.profile_overlay.backpack_button.center))
        self.assertTrue(scene.profile_overlay.inventory_requested)


if __name__ == "__main__":
    unittest.main()
