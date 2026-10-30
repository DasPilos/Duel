import unittest
from collections import Counter, deque
from core.map_catalog import catalog_definitions
from scripts import generate_crossroads_map as generator
from server.map_editor import terrain_from_cells


class CrossroadsMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells, cls.stats = generator.generate(seed=5)
        cls.catalog = {item["item_key"]: item for item in catalog_definitions()}

    def test_three_roads_reach_three_different_edges_over_bridges(self):
        self.assertEqual(self.stats["road_exits_reachable_from_centre"], {"north": True, "west": True, "east": True})
        self.assertEqual(self.stats["bridges"], 3)
        self.assertEqual(self.stats["objects_on_road"], 0)

    def test_three_hills_and_mountains_beside_the_roads(self):
        self.assertEqual(self.stats["hills"], 3)
        self.assertGreaterEqual(self.stats["massifs"], 6)

    def test_forest_is_dense_with_giants_and_old_trees(self):
        categories = self.stats["objects"]
        self.assertGreater(categories["tree"], 800)
        self.assertGreater(categories["old_tree"], 400)

    def test_road_is_at_most_three_tiles_wide_away_from_the_junction(self):
        self.assertTrue(2 <= self.stats["max_road_thickness"] <= 3, self.stats["max_road_thickness"])

    def test_bridges_replace_water_with_walkable_tiles(self):
        terrain = terrain_from_cells(self.cells, list(self.catalog.values()))
        bridge_floor = {
            (c["x"], c["y"]) for c in self.cells
            if c["layer"] == "overlay" and self.catalog[c["key"]]["category"] == "floor"
        }
        self.assertTrue(bridge_floor)
        self.assertFalse(bridge_floor & set(terrain["water"]))

    def test_river_is_one_tile_wide_and_connected_by_sides(self):
        self.assertEqual(generator.RIVER_WIDTH, 1)
        offsets = [0] * 8 + [1] * 8 + [0] * 8 + [-1] * 8
        cells = generator._river_line(32, 10, offsets, 0, True)
        self.assertTrue(all(count <= 2 for count in Counter(x for x, _ in cells).values()))
        seen, queue = {min(cells)}, deque([min(cells)])
        while queue:
            x, y = queue.popleft()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        self.assertEqual(seen, cells)

    def test_small_map_is_refused(self):
        with self.assertRaises(SystemExit):
            generator.generate(size=40)


if __name__ == "__main__":
    unittest.main()
