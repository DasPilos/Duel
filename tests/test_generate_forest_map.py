import random
import unittest

from scripts import generate_forest_map as generator

SIZE = 64


class EarthPatchTests(unittest.TestCase):
    def setUp(self):
        self.zones = {(x, y): ("giant" if 28 <= x <= 36 else "grove") for x in range(SIZE) for y in range(SIZE)}
        self.road = {(x, 10) for x in range(SIZE)}

    def _patches(self, seed=1):
        return generator._earth_patches(random.Random(seed), SIZE, self.zones, set(self.road))

    def test_patches_are_made_and_stay_away_from_roads_giant_forest_and_edges(self):
        patches = self._patches()
        self.assertGreaterEqual(len(patches), generator.EARTH_PATCH_MIN * 4)
        margin = generator.EARTH_PATCH_MARGIN
        for x, y in patches:
            self.assertTrue(2 <= x < SIZE - 2 and 2 <= y < SIZE - 2)
            near = [(x + dx, y + dy) for dx in range(-margin, margin + 1) for dy in range(-margin, margin + 1)]
            self.assertFalse(any(cell in self.road or self.zones.get(cell) == "giant" for cell in near), (x, y))

    def test_patches_are_deterministic_for_a_seed_and_differ_between_seeds(self):
        self.assertEqual(self._patches(4), self._patches(4))
        self.assertNotEqual(self._patches(4), self._patches(5))

    def test_no_room_means_no_patches(self):
        zones = {cell: "giant" for cell in self.zones}
        self.assertEqual(generator._earth_patches(random.Random(1), SIZE, zones, set()), set())


class DryAndLiveForestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells, cls.stats = generator.generate(seed=7)

    def test_dry_template_covers_the_outer_zone_and_brings_big_and_small_stumps(self):
        self.assertGreater(self.stats["dry_forest_cells"], 0)
        keys = {cell["key"] for cell in self.cells if cell["layer"] == "object"}
        self.assertTrue(keys & set(generator.BIG_STUMPS))
        self.assertTrue(keys & set(generator.SMALL_STUMPS))

    def test_mountain_landscape_with_empty_blocks_still_generates(self):
        cells, stats = generator.generate(seed=7, landscape="Горный ландшафт")
        self.assertEqual(stats["dry_forest_cells"], 0)
        self.assertTrue(cells)


if __name__ == "__main__":
    unittest.main()
