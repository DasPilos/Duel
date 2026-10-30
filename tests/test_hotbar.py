import unittest
from types import SimpleNamespace

import pygame

from core import settings
from ui import hotbar


class HotbarSceneTests(unittest.TestCase):
    def test_digit_key_flashes_its_slot_until_timer_runs_out(self):
        pygame.init()
        try:
            pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
            from scenes.world_map_scene import WorldMapScene

            scene = WorldMapScene(SimpleNamespace(character={"id": 1, "name": "Т"}, client=SimpleNamespace()))
            scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3, mod=0, unicode="3", scancode=0))
            self.assertEqual(scene.hotbar_flash_index, 2)
            self.assertGreater(scene.hotbar_flash_timer, 0)

            scene.hotbar_flash_timer = 0.0
            scene.hotbar_flash_index = None
            scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, mod=0, unicode="0", scancode=0))
            self.assertEqual(scene.hotbar_flash_index, 9)
        finally:
            pygame.quit()


class HotbarLayoutTests(unittest.TestCase):
    def test_ten_slots_of_64_pixels_centered_at_bottom(self):
        rects = hotbar.hotbar_slot_rects(1920, 1080)
        self.assertEqual(len(rects), 10)
        for rect in rects:
            self.assertEqual((rect.width, rect.height), (64, 64))
            self.assertEqual(rect.bottom, 1080 - hotbar.HOTBAR_BOTTOM_MARGIN)
        left = rects[0].left
        right = rects[-1].right
        self.assertEqual(left - (1920 - right), 0)

    def test_slots_do_not_overlap(self):
        rects = hotbar.hotbar_slot_rects(1920, 1080)
        for first, second in zip(rects, rects[1:]):
            self.assertFalse(first.colliderect(second))


class HotbarKeyTests(unittest.TestCase):
    def test_keys_one_to_nine_and_zero_map_to_slots_in_order(self):
        keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0]
        for index, key in enumerate(keys):
            self.assertEqual(hotbar.hotbar_index_for_key(key), index)

    def test_other_keys_have_no_slot(self):
        self.assertIsNone(hotbar.hotbar_index_for_key(pygame.K_a))
        self.assertIsNone(hotbar.hotbar_index_for_key(pygame.K_ESCAPE))


if __name__ == "__main__":
    unittest.main()
