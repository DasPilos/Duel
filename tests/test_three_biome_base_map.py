import unittest

from scripts.generate_three_biome_base_map import SIZE, generate


class ThreeBiomeBaseMapTests(unittest.TestCase):
    def test_map_has_three_biomes_city_and_reachable_roads(self):
        cells, stats = generate()
        self.assertEqual(len(stats["biome_cells"]), 3)
        self.assertTrue(all(count > 1000 for count in stats["biome_cells"].values()))
        self.assertGreater(stats["transition_cells"], 10000)
        self.assertEqual(stats["city_buildings"], 8)
        self.assertTrue(all(stats["road_exits_reachable_from_city"].values()))
        self.assertEqual(
            sum(cell["layer"] == "ground" for cell in cells),
            SIZE * SIZE,
        )


if __name__ == "__main__":
    unittest.main()
