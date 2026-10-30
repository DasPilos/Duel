import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from scenes.map_editor_scene import _scale_rgba


class ScaleRgbaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_transparent_pixels_do_not_darken_opaque_edge(self):
        source = pygame.Surface((2, 1), pygame.SRCALPHA)
        source.fill((0, 0, 0, 0))
        source.set_at((0, 0), (255, 0, 0, 255))

        scaled = _scale_rgba(source, (1, 1))
        r, g, b, a = scaled.get_at((0, 0))

        self.assertGreaterEqual(r, 250)
        self.assertEqual((g, b), (0, 0))
        self.assertAlmostEqual(a, 127, delta=2)

    def test_fully_opaque_surface_keeps_colors(self):
        source = pygame.Surface((4, 4), pygame.SRCALPHA)
        source.fill((10, 200, 30, 255))

        scaled = _scale_rgba(source, (2, 2))

        self.assertEqual(scaled.get_at((1, 1))[:3], (10, 200, 30))
        self.assertEqual(scaled.get_at((1, 1))[3], 255)


if __name__ == "__main__":
    unittest.main()
