import unittest
from types import SimpleNamespace

import pygame

from core import settings
from tests.test_dash import make_snapshot


class FakeLootClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def world_loot_corpse(self, character_id, corpse_id):
        self.calls.append((character_id, corpse_id))
        if self.error is not None:
            raise self.error
        return self.result


class PlayerCorpseClientTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from scenes.world_map_scene import WorldMapScene

        self.client = FakeLootClient()
        self.character = {"id": 1, "name": "Т", "copper": 100, "silver": 0, "gold": 0}
        self.scene = WorldMapScene(SimpleNamespace(character=self.character, client=self.client))
        self.scene.player_x, self.scene.player_y = 1000.0, 1000.0

    def tearDown(self):
        pygame.quit()

    def corpse(self, corpse_id=7, dx=0.0, copper=40):
        return {"id": corpse_id, "x": 1000.0 + dx, "y": 1000.0, "copper": copper}

    def test_tile_word_agrees_with_number(self):
        from scenes.world_map_scene import _tiles_word

        self.assertEqual(_tiles_word(1), "тайл")
        self.assertEqual(_tiles_word(2), "тайла")
        self.assertEqual(_tiles_word(5), "тайлов")
        self.assertEqual(_tiles_word(11), "тайлов")
        self.assertEqual(_tiles_word(21), "тайл")
        self.assertEqual(_tiles_word(22), "тайла")

    def test_distance_is_measured_in_tiles(self):
        self.assertAlmostEqual(self.scene._corpse_distance_tiles(self.corpse(dx=96.0)), 3.0)

    def test_far_corpse_only_shows_notice(self):
        self.scene._open_corpse_window(self.corpse(dx=32.0 * 5))
        self.assertIsNone(self.scene.corpse_window_id)
        self.assertEqual(self.scene.action_notice, "Подойдите ближе к трупу")

    def test_near_corpse_opens_window(self):
        self.scene._open_corpse_window(self.corpse(corpse_id=9, dx=32.0))
        self.assertEqual(self.scene.corpse_window_id, 9)

    def test_loot_all_moves_coins_to_wallet_and_closes_window(self):
        self.client.result = {
            "currency": {"copper": 140, "silver": 0, "gold": 0},
            "corpses": [],
        }
        self.scene.player_corpses = [self.corpse(corpse_id=7, dx=0.0, copper=40)]
        self.scene.corpse_window_id = 7

        self.scene._loot_corpse()

        self.assertEqual(self.client.calls, [(1, 7)])
        self.assertEqual(self.character["copper"], 140)
        self.assertEqual(self.scene.player_corpses, [])
        self.assertIsNone(self.scene.corpse_window_id)
        self.assertIn("Забрано из трупа", self.scene.action_notice)

    def test_failed_loot_keeps_window_and_shows_error(self):
        self.client.error = OSError("сеть недоступна")
        self.scene.player_corpses = [self.corpse(corpse_id=7)]
        self.scene.corpse_window_id = 7

        self.scene._loot_corpse()

        self.assertEqual(self.scene.corpse_window_id, 7)
        self.assertEqual(self.character["copper"], 100)
        self.assertEqual(self.scene.action_notice, "сеть недоступна")

    def test_window_closes_when_corpse_disappears_from_snapshot(self):
        self.scene.player_corpses = [self.corpse(corpse_id=7)]
        self.scene.corpse_window_id = 7
        snap = make_snapshot(x=1000.0, y=1000.0)
        snap["corpses"] = []

        self.scene._apply_world_snapshot(snap)

        self.assertEqual(self.scene.player_corpses, [])
        self.assertIsNone(self.scene.corpse_window_id)

    def test_click_on_corpse_marker_finds_that_corpse(self):
        corpse = self.corpse(corpse_id=3, dx=0.0)
        self.scene.player_corpses = [corpse]
        sx, sy = self.scene.world_to_screen(corpse["x"], corpse["y"])
        self.assertIs(self.scene._player_corpse_at((sx, sy - 8)), corpse)
        self.assertIsNone(self.scene._player_corpse_at((sx + 400, sy)))

    def test_corpse_and_window_draw_without_errors(self):
        surface = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        self.scene.player_corpses = [self.corpse(corpse_id=7, dx=0.0, copper=40)]
        self.scene.corpse_window_id = 7

        self.scene._draw_player_corpses(surface)
        self.scene._draw_corpse_window(surface)


if __name__ == "__main__":
    unittest.main()
