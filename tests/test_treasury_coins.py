import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ui.catalog_icons import draw_treasury_coins


class TreasuryCoinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.font = pygame.font.Font(None, 20)

    def setUp(self):
        self.screen = pygame.Surface((800, 100))
        self.rendered = []
        original_render = self.font.render

        def recording_render(text, *args):
            self.rendered.append(str(text))
            return original_render(text, *args)

        self.font_proxy = _RenderProxy(self.font, recording_render)

    def test_splits_copper_into_gold_silver_and_copper(self):
        # 4 gold + 66 silver + 79 copper = 46679 copper
        end_x = draw_treasury_coins(self.screen, self.font_proxy, 46679, (0, 0))
        self.assertEqual(self.rendered, ["4", "66", "79"])
        self.assertGreater(end_x, 0)

    def test_zero_gold_still_shows_all_three_denominations(self):
        draw_treasury_coins(self.screen, self.font_proxy, 4679, (0, 0))
        self.assertEqual(self.rendered, ["0", "46", "79"])

    def test_zero_treasury_shows_three_zeros(self):
        draw_treasury_coins(self.screen, self.font_proxy, 0, (0, 0))
        self.assertEqual(self.rendered, ["0", "0", "0"])


class _RenderProxy:
    def __init__(self, font, render):
        self._font = font
        self.render = render

    def __getattr__(self, name):
        return getattr(self._font, name)


if __name__ == "__main__":
    unittest.main()
