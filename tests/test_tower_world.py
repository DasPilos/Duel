import unittest
from unittest import mock

from server import world_map
from server.world_map import (
    IS_TOWER_WORLD, MAP_TILES_H, MAP_TILES_W, TILE, TOWER_CENTER_TILE, build_tower_terrain_tiles, point_in_polygon,
    rect_touches_blocked_tile, tower_mountain_tiles, tower_obstacle, tower_road_tiles,
)

TOWER_TILES_SET = {(x, y) for x in range(61, 64) for y in range(61, 64)}


class TowerGeometryTests(unittest.TestCase):
    def test_tower_is_three_by_three_block_in_map_centre_with_full_hp(self):
        tower = tower_obstacle()
        xs = [x for x, _ in tower["points"]]
        ys = [y for _, y in tower["points"]]

        self.assertEqual(TOWER_CENTER_TILE, 62)
        self.assertEqual((min(xs) // TILE, max(xs) // TILE), (61, 64))
        self.assertEqual((min(ys) // TILE, max(ys) // TILE), (61, 64))
        self.assertEqual(tower["type"], "tower")
        self.assertEqual((tower["hp"], tower["max_hp"]), (1000, 1000))

    def test_tower_polygon_covers_centre_but_not_road_beside_it(self):
        tower = tower_obstacle()

        self.assertTrue(point_in_polygon((62 * TILE + 16, 62 * TILE + 16), tower["points"]))
        self.assertFalse(point_in_polygon((62 * TILE + 16, 66 * TILE + 16), tower["points"]))

    def test_roads_form_ring_around_tower_with_one_tile_gap(self):
        tiles = set(tower_road_tiles())

        self.assertTrue({(59, y) for y in range(59, 66)} <= tiles)
        self.assertTrue({(65, y) for y in range(59, 66)} <= tiles)
        self.assertTrue({(x, 59) for x in range(59, 66)} <= tiles)
        self.assertTrue({(x, 65) for x in range(59, 66)} <= tiles)
        self.assertFalse(tiles & TOWER_TILES_SET)

    def test_four_roads_run_from_ring_to_map_edges(self):
        tiles = set(tower_road_tiles())
        last = 124

        self.assertIn((62, 0), tiles)
        self.assertIn((62, last), tiles)
        self.assertIn((0, 62), tiles)
        self.assertIn((last, 62), tiles)


class TowerTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forest, cls.water = build_tower_terrain_tiles()

    def test_forest_and_lakes_exist_and_do_not_overlap(self):
        self.assertGreater(len(self.forest), 500)
        self.assertGreater(len(self.water), 100)
        self.assertFalse(self.forest & self.water)

    def test_tiles_stay_inside_map(self):
        for x, y in self.forest | self.water:
            self.assertTrue(0 <= x < world_map.TOWER_TILES and 0 <= y < world_map.TOWER_TILES)

    def test_roads_and_tower_yard_stay_free(self):
        blocked = self.forest | self.water
        half = world_map.TOWER_YARD_HALF
        yard = {(x, y) for x in range(TOWER_CENTER_TILE - half, TOWER_CENTER_TILE + half + 1)
                for y in range(TOWER_CENTER_TILE - half, TOWER_CENTER_TILE + half + 1)}

        self.assertFalse(blocked & set(tower_road_tiles()))
        self.assertFalse(blocked & yard)

    def test_road_has_two_tile_clearance_from_forest_and_water(self):
        blocked = self.forest | self.water
        for road_x, road_y in tower_road_tiles():
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    self.assertNotIn((road_x + dx, road_y + dy), blocked)

    def test_spawn_on_south_road_is_free(self):
        self.assertNotIn((TOWER_CENTER_TILE, TOWER_CENTER_TILE + 28), self.forest | self.water)


class TowerMountainRingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forest, cls.water = build_tower_terrain_tiles()
        cls.mountains = tower_mountain_tiles()
        cls.roads = set(tower_road_tiles())

    def test_ring_stays_inside_67_square_and_outside_57_yard(self):
        centre = TOWER_CENTER_TILE
        outer = world_map.TOWER_RING_HALF

        self.assertEqual((2 * outer + 1, 2 * world_map.TOWER_YARD_HALF + 1), (67, 57))
        for x, y in self.mountains:
            self.assertLessEqual(max(abs(x - centre), abs(y - centre)), outer)

    def test_ring_thickness_is_uneven_from_zero_to_five_with_gaps_up_to_ten(self):
        centre = TOWER_CENTER_TILE
        outer = world_map.TOWER_RING_HALF
        yard = world_map.TOWER_YARD_HALF
        thicknesses = []
        longest_gap = 0
        for side_cell in (lambda a, r: (centre + a, centre - r), lambda a, r: (centre + a, centre + r),
                          lambda a, r: (centre - r, centre + a), lambda a, r: (centre + r, centre + a)):
            run_gap = 0
            for along in range(-outer, outer + 1):
                if abs(along) <= world_map.TOWER_GORGE_HALF:
                    run_gap = 0
                    continue
                depth = 0
                for reach in range(outer, yard, -1):
                    if side_cell(along, reach) not in self.mountains:
                        break
                    depth += 1
                thicknesses.append(depth)
                run_gap = run_gap + 1 if depth == 0 else 0
                longest_gap = max(longest_gap, run_gap)

        self.assertEqual(min(thicknesses), 0)
        self.assertEqual(max(thicknesses), world_map.TOWER_RING_DEPTH)
        self.assertGreater(len(set(thicknesses)), 3)
        self.assertGreaterEqual(longest_gap, 4)
        self.assertLessEqual(longest_gap, 10)

    def test_four_gorges_are_open_roads_in_each_side(self):
        centre = TOWER_CENTER_TILE
        ring = world_map.TOWER_RING_HALF
        gorge_centres = [(centre, centre - ring + 2), (centre, centre + ring - 2),
                         (centre - ring + 2, centre), (centre + ring - 2, centre)]

        for tile in gorge_centres:
            self.assertNotIn(tile, self.mountains)
            self.assertIn(tile, self.roads)

    def test_mountains_do_not_overlap_forest_water_or_roads(self):
        self.assertFalse(self.mountains & (self.forest | self.water))
        self.assertFalse(self.mountains & self.roads)


@unittest.skipUnless(IS_TOWER_WORLD, "проверка для мира «Башня» (WORLD_ID=2)")
class TowerMountainServerTests(unittest.TestCase):
    def test_mountain_tiles_block_movement_and_gorges_stay_open(self):
        mountains = world_map.TOWER_MOUNTAIN_TILES
        self.assertTrue(mountains <= world_map.TOWER_BLOCKED_TILES)

        mountain_x, mountain_y = next(iter(sorted(mountains)))
        self.assertFalse(world_map.is_passable(mountain_x * TILE + 16, mountain_y * TILE + 16))
        gorge_y = TOWER_CENTER_TILE - world_map.TOWER_RING_HALF + 2
        self.assertTrue(world_map.is_passable(TOWER_CENTER_TILE * TILE + 16, gorge_y * TILE + 16))

    def test_mountain_obstacles_are_rectangles_covering_ring_tiles(self):
        obstacles = world_map.TOWER_MOUNTAIN_OBSTACLES
        covered = set()
        for obstacle in obstacles:
            xs = [x for x, _ in obstacle["points"]]
            ys = [y for _, y in obstacle["points"]]
            self.assertEqual(obstacle["type"], "mountains")
            self.assertEqual(obstacle["peaks"], [])
            left, top, right, bottom = min(xs) // TILE, min(ys) // TILE, (max(xs) - 1) // TILE, (max(ys) - 1) // TILE
            covered |= {(x, y) for x in range(left, right + 1) for y in range(top, bottom + 1)}

        self.assertTrue(obstacles)
        self.assertEqual(covered, set(world_map.TOWER_MOUNTAIN_TILES))

    def test_payload_contains_mountain_tiles(self):
        payload = world_map.terrain_payload(city_level=1)
        spans = payload["tiles"]["mountain"]
        decoded = {(x, y) for y, start, end in spans for x in range(start, end + 1)}

        self.assertEqual(decoded, set(world_map.TOWER_MOUNTAIN_TILES))

    def test_two_rivers_have_one_bridge_each(self):
        self.assertEqual(len(world_map.TOWER_BRIDGES), 2)


class TowerPropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forest, cls.water = build_tower_terrain_tiles()
        cls.props = world_map.build_tower_props(cls.forest, cls.water)
        cls.prop_tiles = [tuple(tile) for prop in cls.props for tile in prop["tiles"]]

    def test_stumps_and_logs_are_generated(self):
        self.assertEqual({prop["type"] for prop in self.props}, {"stump", "log"})

    def test_props_sit_on_dry_land_next_to_forest_and_off_roads(self):
        reserved = world_map._tower_reserved_tiles()
        for x, y in self.prop_tiles:
            self.assertNotIn((x, y), self.forest | self.water)
            self.assertNotIn((x, y), reserved)
            self.assertTrue({(x, y - 1), (x, y + 1), (x + 1, y), (x - 1, y)} & self.forest)

    def test_logs_cover_two_horizontal_tiles_and_stumps_one(self):
        for prop in self.props:
            if prop["type"] == "log":
                first, second = prop["tiles"]
                self.assertEqual(second, [first[0] + 1, first[1]])
            else:
                self.assertEqual(len(prop["tiles"]), 1)

    def test_props_do_not_overlap(self):
        self.assertEqual(len(self.prop_tiles), len(set(self.prop_tiles)))

    def test_prop_tiles_block_movement(self):
        x, y = self.prop_tiles[0]
        with mock.patch.object(world_map, "TOWER_BLOCKED_TILES", frozenset(self.prop_tiles)):
            self.assertTrue(rect_touches_blocked_tile((x * TILE + 5, y * TILE + 5, 10, 10)))


@unittest.skipUnless(IS_TOWER_WORLD, "проверка для мира «Башня» (WORLD_ID=2)")
class TowerPropPayloadTests(unittest.TestCase):
    def test_payload_props_are_blocked_on_server(self):
        payload = world_map.terrain_payload(city_level=1)

        self.assertTrue(payload["props"])
        for prop in payload["props"]:
            for tile in prop["tiles"]:
                self.assertIn(tuple(tile), world_map.TOWER_BLOCKED_TILES)
                self.assertFalse(world_map.is_passable(tile[0] * TILE + 16, tile[1] * TILE + 16))


class TowerBlockingTests(unittest.TestCase):
    def test_rect_touching_blocked_tile_is_blocked(self):
        with mock.patch.object(world_map, "TOWER_BLOCKED_TILES", frozenset({(3, 4)})):
            self.assertTrue(rect_touches_blocked_tile((3 * TILE + 30, 4 * TILE + 5, 10, 10)))
            self.assertFalse(rect_touches_blocked_tile((0, 0, TILE, TILE)))
            self.assertFalse(rect_touches_blocked_tile((2 * TILE, 4 * TILE, TILE, TILE)))

    def test_is_passable_rejects_blocked_tile(self):
        with mock.patch.object(world_map, "TOWER_BLOCKED_TILES", frozenset({(3, 4)})),                 mock.patch.object(world_map, "OBSTACLES", ()):
            self.assertFalse(world_map.is_passable(3 * TILE + 5, 4 * TILE + 5))
            self.assertTrue(world_map.is_passable(2 * TILE + 5, 4 * TILE + 5))

    def test_tile_rows_compress_runs_by_row(self):
        rows = world_map._tile_rows({(1, 2), (2, 2), (3, 2), (7, 2), (0, 5)})

        self.assertEqual(rows, [[2, 1, 3], [2, 7, 7], [5, 0, 0]])


@unittest.skipIf(IS_TOWER_WORLD, "проверка для мира по умолчанию (WORLD_ID=1)")
class DefaultWorldProfileTests(unittest.TestCase):
    def test_default_world_keeps_512_by_256_map_and_its_obstacles(self):
        self.assertEqual((MAP_TILES_W, MAP_TILES_H), (512, 256))
        self.assertNotIn("tower", {obstacle["type"] for obstacle in world_map.OBSTACLES})

    def test_default_world_terrain_payload_reports_map_size_and_no_tower(self):
        payload = world_map.terrain_payload(city_level=1)

        self.assertEqual(payload["map"]["tiles_w"], 512)
        self.assertEqual(payload["map"]["tiles_h"], 256)
        self.assertFalse(payload["map"]["uniform_grass"])
        self.assertEqual(payload["tiles"], {"forest": [], "water": [], "dry": [], "paths": [], "mountain": [], "berry": [], "floor": [],
                                            "impassable": [], "partial": []})
        self.assertEqual(payload["props"], [])
        self.assertEqual(payload["bridges"], [])


@unittest.skipUnless(IS_TOWER_WORLD, "проверка для мира «Башня» (WORLD_ID=2)")
class TowerFeatureTests(unittest.TestCase):
    def test_dense_forest_keeps_away_from_water(self):
        near_water = world_map._near_tiles(world_map.TOWER_WATER_TILES, world_map.TOWER_WATER_MARGIN)

        self.assertFalse(world_map.TOWER_FOREST_TILES & near_water)

    def test_clearings_are_free_of_forest(self):
        for centre_x, centre_y, radius in world_map.TOWER_CLEARINGS:
            clearing = world_map._clearing_tiles(centre_x, centre_y, radius)
            self.assertFalse(clearing & world_map.TOWER_FOREST_TILES)

    def test_paths_stay_off_water_forest_dry_and_props(self):
        paths = world_map.TOWER_PATH_TILES

        self.assertTrue(paths)
        self.assertFalse(paths & world_map.TOWER_WATER_TILES)
        self.assertFalse(paths & world_map.TOWER_FOREST_TILES)
        self.assertFalse(paths & world_map.TOWER_DRY_TILES)
        self.assertFalse(paths & world_map.TOWER_PROP_TILES)

    def test_paths_reach_the_road_ring(self):
        roads = set(tower_road_tiles())
        touching = {(x + dx, y + dy) for x, y in roads for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}

        self.assertTrue(world_map.TOWER_PATH_TILES & touching)

    def test_dry_band_lies_on_map_edge_and_blocks_movement(self):
        last = world_map.TOWER_TILES - 1
        for x, y in world_map.TOWER_DRY_TILES:
            self.assertLess(min(x, y, last - x, last - y), world_map.TOWER_DRY_MAX_DEPTH)
            self.assertIn((x, y), world_map.TOWER_BLOCKED_TILES)
        self.assertFalse(world_map.TOWER_DRY_TILES & world_map.TOWER_FOREST_TILES)
        self.assertFalse(world_map.TOWER_DRY_TILES & world_map.TOWER_WATER_TILES)

    def test_dry_edge_is_broken_by_glades_of_10_to_40_tiles(self):
        last = world_map.TOWER_TILES - 1
        sides = (
            lambda along, d: (along, d),
            lambda along, d: (along, last - d),
            lambda along, d: (d, along),
            lambda along, d: (last - d, along),
        )

        def inner_runs(flags, value):
            """Серии value, не касающиеся краёв среза: обрезанные краем серии не проверяем."""
            runs, start = [], None
            for index, flag in enumerate(flags + [not value]):
                if flag == value and start is None:
                    start = index
                elif flag != value and start is not None:
                    if start > 0 and index < len(flags):
                        runs.append(index - start)
                    start = None
            return runs

        for side in sides:
            flags = [side(along, 0) in world_map.TOWER_DRY_TILES for along in range(5, last - 4)]
            self.assertTrue(inner_runs(flags, False))
            for length in inner_runs(flags, True):
                self.assertLessEqual(length, world_map.TOWER_DRY_SPAN_MAX)
            for length in inner_runs(flags, False):
                self.assertTrue(world_map.TOWER_GLADE_MIN <= length <= world_map.TOWER_GLADE_MAX)

    def test_bridges_cross_river_on_road_and_are_not_water(self):
        roads = set(tower_road_tiles())

        self.assertTrue(world_map.TOWER_BRIDGES)
        for bridge in world_map.TOWER_BRIDGES:
            for x, y in bridge["tiles"]:
                self.assertIn((x, y), roads)
                self.assertNotIn((x, y), world_map.TOWER_WATER_TILES)

    def test_one_bridge_per_river_crossing_with_artist_span(self):
        self.assertEqual(len(world_map.TOWER_BRIDGES), len(world_map.TOWER_RIVER_ROUTES))
        for bridge in world_map.TOWER_BRIDGES:
            xs = [x for x, _ in bridge["tiles"]]
            ys = [y for _, y in bridge["tiles"]]
            self.assertLessEqual(max(xs) - min(xs) + 1, 2 * world_map.TOWER_BRIDGE_HALF_SPAN + 1)
            self.assertEqual(len(set(ys)), 3)

    def test_rivers_run_from_north_edge_into_water(self):
        self.assertTrue(any(y == 0 for _, y in world_map.TOWER_RIVERS))
        self.assertTrue(world_map.TOWER_RIVERS & world_map.TOWER_WATER_TILES)

    def test_payload_carries_dry_paths_and_bridges(self):
        payload = world_map.terrain_payload(city_level=1)

        self.assertTrue(payload["tiles"]["dry"])
        self.assertTrue(payload["tiles"]["paths"])
        self.assertEqual(len(payload["bridges"]), len(world_map.TOWER_BRIDGES))


if __name__ == "__main__":
    unittest.main()
