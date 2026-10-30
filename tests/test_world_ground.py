import unittest

from scenes.world_map_scene import build_ground_kinds


def _forest_block(x0, y0, size):
    return {(x, y) for x in range(x0, x0 + size) for y in range(y0, y0 + size)}


def _ring_distance(x, y, cover):
    """Минимальное число шагов по 8 соседям от клетки до леса (та же метрика, что в игре)."""
    for depth in range(1, 10):
        for dx in range(-depth, depth + 1):
            for dy in range(-depth, depth + 1):
                if (x + dx, y + dy) in cover:
                    return depth
    return 99


class GroundKindsTests(unittest.TestCase):
    def setUp(self):
        self.cover = _forest_block(40, 40, 10)
        self.kinds = build_ground_kinds(self.cover, 125, 125)

    def test_forest_tiles_are_dark_floor(self):
        for tile in self.cover:
            self.assertEqual(self.kinds[tile], "floor")

    def test_band_just_outside_forest_mixes_floor_and_grass(self):
        ring = [(x, 39) for x in range(40, 50)]
        kinds = [self.kinds.get(tile) for tile in ring]

        self.assertIn("floor", kinds)
        self.assertNotIn("berry", kinds)

    def test_two_to_five_tiles_from_forest_is_mostly_berry(self):
        # Лес занимает 40..49, значит расстояние 2..5 от него — это 42..45 и 54..47 по краям
        band = [
            (x, y)
            for x in range(34, 56)
            for y in range(34, 56)
            if (x, y) not in self.cover and 2 <= _ring_distance(x, y, self.cover) <= 5
        ]
        berry = sum(1 for tile in band if self.kinds.get(tile) == "berry")

        self.assertGreater(berry, len(band) * 0.6)

    def test_far_from_forest_there_is_no_dark_floor(self):
        far = [(x, y) for x in range(100, 125) for y in range(100, 125)]

        self.assertFalse(any(self.kinds.get(tile) == "floor" for tile in far))

    def test_no_cover_gives_only_clearing_patches(self):
        kinds = build_ground_kinds(set(), 125, 125)

        self.assertNotIn("floor", kinds.values())


if __name__ == "__main__":
    unittest.main()
