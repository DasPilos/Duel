import unittest

from scenes.world_map_scene import WorldMapScene


def _scene_with_grid(grid_w, grid_h):
    scene = WorldMapScene.__new__(WorldMapScene)
    scene.grid_w = grid_w
    scene.grid_h = grid_h
    return scene


class MinimapSizeTests(unittest.TestCase):
    def test_square_tower_grid_gives_square_minimap(self):
        width, height = _scene_with_grid(125, 125)._minimap_size()

        self.assertEqual(width, height)

    def test_wide_grid_keeps_its_aspect_ratio(self):
        width, height = _scene_with_grid(512, 256)._minimap_size()

        self.assertEqual((width, height), (384, 192))


class MinimapTileRectTests(unittest.TestCase):
    def test_tile_rect_is_at_least_one_pixel_when_scaled_down(self):
        rect = WorldMapScene._minimap_tile_rect(10, 10, 0.5, 0.5)

        self.assertGreaterEqual(rect[2], 1)
        self.assertGreaterEqual(rect[3], 1)

    def test_tile_rect_covers_scaled_tile_bounds(self):
        rect = WorldMapScene._minimap_tile_rect(4, 2, 1.5, 1.5)

        self.assertEqual(rect, (6, 3, 1, 1))


if __name__ == "__main__":
    unittest.main()
