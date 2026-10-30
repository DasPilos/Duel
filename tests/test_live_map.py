import random
import unittest
from unittest import mock

from server import structures, world_map, world_mobs, world_roads
from server.map_editor import terrain_from_cells
from server.world_mobs import WorldService
from tests.test_world_mobs import FakeClock, FakeDatabase, FakeItems


CATALOG = [
    {"item_key": "ground:water_1", "kind": "ground", "category": "water", "asset": "", "footprint_w": 1, "footprint_h": 1, "blocks": True},
    {"item_key": "ground:road_core_1", "kind": "ground", "category": "road", "asset": "", "footprint_w": 1, "footprint_h": 1, "blocks": False},
    {"item_key": "ground:grass_1", "kind": "ground", "category": "grass", "asset": "", "footprint_w": 1, "footprint_h": 1, "blocks": False},
    {"item_key": "object:tree1", "kind": "object", "category": "tree", "asset": "", "footprint_w": 1, "footprint_h": 1, "blocks": True},
    {"item_key": "object:rock_01", "kind": "object", "category": "rock", "asset": "", "footprint_w": 1, "footprint_h": 1, "blocks": True},
    {"item_key": "object:log_1", "kind": "object", "category": "log", "asset": "", "footprint_w": 2, "footprint_h": 1, "blocks": True},
    {"item_key": "object:bridge_horizontal", "kind": "object", "category": "bridge", "asset": "", "footprint_w": 6, "footprint_h": 4, "blocks": False},
]


PUBLISHED = {"map_w": 125, "map_h": 125, "published_at": 1.0}


def cell(layer, x, y, key):
    return {"layer": layer, "x": x, "y": y, "key": key}


def sample_terrain():
    cells = [
        cell("ground", 2, 2, "ground:water_1"),
        cell("ground", 3, 2, "ground:road_core_1"),
        cell("ground", 4, 2, "ground:grass_1"),
        cell("object", 5, 5, "object:tree1"),
        cell("object", 6, 6, "object:rock_01"),
        cell("object", 8, 8, "object:log_1"),
        cell("ground", 13, 13, "ground:water_1"),
        cell("object", 12, 12, "object:bridge_horizontal"),
    ]
    return terrain_from_cells(cells, CATALOG)


class TerrainFromCellsTest(unittest.TestCase):
    def test_empty_map_means_procedural_terrain(self):
        self.assertIsNone(terrain_from_cells([], CATALOG), PUBLISHED)

    def test_categories_map_to_terrain_layers(self):
        terrain = sample_terrain()
        self.assertEqual(terrain["water"], frozenset({(2, 2)}))
        self.assertEqual(terrain["paths"], frozenset({(3, 2)}))
        self.assertEqual(terrain["forest"], frozenset({(5, 5)}))
        self.assertEqual(terrain["mountain"], frozenset({(6, 6)}))
        self.assertEqual(terrain["props"], [{"type": "log", "tiles": [[8, 8], [9, 8]]}])

    def test_bridge_removes_water_under_it(self):
        terrain = sample_terrain()
        self.assertNotIn((13, 13), terrain["water"])
        self.assertIn([13, 13], terrain["bridges"][0]["tiles"])
        self.assertEqual(len(terrain["bridges"][0]["tiles"]), 24)

    def test_unknown_keys_are_ignored(self):
        terrain = terrain_from_cells([cell("object", 1, 1, "object:missing")], CATALOG)
        self.assertEqual(terrain["forest"], frozenset())
        self.assertEqual(terrain["mountain"], frozenset())


class LiveTerrainTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(world_map, "IS_TOWER_WORLD", True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(world_map.apply_live_terrain)

    def test_live_map_replaces_procedural_passability(self):
        world_map.apply_live_terrain(sample_terrain(), PUBLISHED)
        self.assertFalse(world_map.is_passable(5 * 32 + 16, 5 * 32 + 16))
        self.assertFalse(world_map.is_passable(6 * 32 + 16, 6 * 32 + 16))
        self.assertFalse(world_map.is_passable(2 * 32 + 16, 2 * 32 + 16))
        self.assertTrue(world_map.is_passable(20 * 32 + 16, 20 * 32 + 16))
        self.assertTrue(world_map.is_passable(13 * 32 + 16, 13 * 32 + 16))

    def test_apply_bumps_version_and_payload_reports_it(self):
        before = world_map.TERRAIN_VERSION
        world_map.apply_live_terrain(sample_terrain(), PUBLISHED)
        self.assertEqual(world_map.TERRAIN_VERSION, before + 1)
        payload = world_map.terrain_payload()
        self.assertEqual(payload["map"]["version"], before + 1)
        self.assertEqual(payload["tiles"]["water"], [[2, 2, 2]])

    def test_empty_map_restores_procedural_terrain(self):
        original_water = world_map.TOWER_WATER_TILES
        world_map.apply_live_terrain(sample_terrain(), PUBLISHED)
        self.assertIsNot(world_map.TOWER_WATER_TILES, original_water)
        world_map.apply_live_terrain(None)
        self.assertIs(world_map.TOWER_WATER_TILES, original_water)

    def test_mob_collision_shapes_follow_live_rocks(self):
        world_map.apply_live_terrain(terrain_from_cells(
            [cell("object", 30, 30, "object:rock_01")], CATALOG), PUBLISHED)
        self.assertEqual(len(world_mobs._obstacle_shapes()), len(world_map.OBSTACLES))
        self.assertEqual(len(world_map.OBSTACLES), 2)


class LiveRelocationTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(world_map, "IS_TOWER_WORLD", True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(world_map.apply_live_terrain)
        self.database = FakeDatabase({1: 7})
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))

    def test_player_inside_new_tree_is_moved_to_free_ground(self):
        # На время первого входа рельеф открыт, как в других тестах мобов
        self.service._terrain_blocked = lambda x, y: False
        self.service.sync(7, 1, {"x": 20 * 32 + 16.0, "y": 20 * 32 + 16.0})
        del self.service._terrain_blocked

        self.service.reload_terrain(terrain_from_cells(
            [cell("object", 20, 20, "object:tree1")], CATALOG), PUBLISHED)

        player = next(iter(self.service._players.values()))
        self.assertFalse(self.service._terrain_blocked(player.x, player.y))
        self.assertNotEqual((player.x, player.y), (20 * 32 + 16.0, 20 * 32 + 16.0))

    def test_snapshot_carries_terrain_version(self):
        self.service._terrain_blocked = lambda x, y: False
        self.service.sync(7, 1, {"x": 700.0, "y": 1296.0})
        del self.service._terrain_blocked
        player = next(iter(self.service._players.values()))
        snapshot = self.service._snapshot(player, 0, True)
        self.assertEqual(snapshot["terrain_version"], world_map.TERRAIN_VERSION)


class LivePublishTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(world_map, "IS_TOWER_WORLD", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(world_map.apply_live_terrain)

    def test_published_size_and_stamp_are_applied(self):
        world_map.apply_live_terrain(sample_terrain(), {"map_w": 40, "map_h": 30, "published_at": 2.0})
        self.assertEqual((world_map.MAP_TILES_W, world_map.MAP_TILES_H), (40, 30))
        self.assertEqual(world_map.PUBLISHED_AT, 2.0)
        self.assertTrue(world_map.LIVE_MAP)

    def test_procedural_size_is_restored_after_live_map(self):
        procedural = (world_map.MAP_TILES_W, world_map.MAP_TILES_H)
        world_map.apply_live_terrain(sample_terrain(), {"map_w": 40, "map_h": 30, "published_at": 2.0})
        world_map.apply_live_terrain()
        self.assertEqual((world_map.MAP_TILES_W, world_map.MAP_TILES_H), procedural)
        self.assertFalse(world_map.LIVE_MAP)

    def test_live_map_has_no_roads_structures_or_mobs(self):
        world_map.apply_live_terrain(sample_terrain(), {"map_w": 40, "map_h": 30, "published_at": 2.0})
        self.assertEqual(world_roads.roads_payload(), {"routes": [], "tiles": [], "travel_seconds": 0})
        self.assertEqual(structures.world_structures(), {"objects": []})
        service = world_mobs.WorldService(FakeDatabase({1: 7}), FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.assertEqual(service._spawn_list(), ())  # на карте без бесов мобов нет

    def test_live_map_spawn_is_passable(self):
        world_map.apply_live_terrain(sample_terrain(), {"map_w": 40, "map_h": 30, "published_at": 2.0})
        spawn_x, spawn_y = world_map.MAP_SPAWN_PX
        self.assertTrue(world_map.is_passable(spawn_x, spawn_y))

    def test_sync_picks_up_new_publication_once(self):
        database = FakeDatabase({1: 7})
        database.published_map = mock.Mock(return_value={"name": "Степь", "map_w": 40, "map_h": 30, "published_at": 5.0})
        service = WorldService(database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        published = {"map_w": 40, "map_h": 30, "published_at": 5.0}
        with mock.patch.object(world_mobs.map_editor, "load_published_map",
                               return_value=(sample_terrain(), published)) as load:
            self.assertTrue(service.sync_published_map())
            self.assertFalse(service.sync_published_map())
        load.assert_called_once()
        self.assertEqual(world_map.PUBLISHED_AT, 5.0)
        self.assertEqual((world_map.MAP_TILES_W, world_map.MAP_TILES_H), (40, 30))

    def test_sync_ignores_world_without_publication(self):
        database = FakeDatabase({1: 7})
        database.published_map = mock.Mock(return_value=None)
        service = WorldService(database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.assertFalse(service.sync_published_map())
        self.assertIsNone(world_map.PUBLISHED_AT)


if __name__ == "__main__":
    unittest.main()
