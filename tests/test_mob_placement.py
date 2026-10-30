import random
import unittest
from unittest.mock import patch

from core import mob_modes
from server import world_map
from server.world_map import TILE
from server.world_mobs import WorldService
from tests.test_world_mobs import FakeClock, FakeDatabase, FakeItems

IMP = "imp_sword"


class PlacedMobTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase({1: 7})
        self.database.mobs = [{"kind": IMP, "x": 10, "y": 12}]
        self.live = patch.object(world_map, "LIVE_MAP", True)
        self.live.start()
        self.addCleanup(self.live.stop)
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.service._terrain_blocked = lambda x, y: False
        self.mob = self.service._mobs[f"mob_0_{IMP}"]

    def test_a_placed_mob_appears_on_its_tile_with_the_mode_settings(self):
        self.assertEqual(self.mob.kind, IMP)
        self.assertEqual((self.mob.home_x, self.mob.home_y), (10 * TILE + TILE // 2, 12 * TILE + TILE // 2))
        defaults = mob_modes.load_mob_settings("tower", IMP)  # значения из файла режима
        self.assertEqual(self.mob.move_speed, defaults["move_speed"])
        self.assertEqual(self.mob.respawn_delay, defaults["respawn_seconds"])
        self.assertEqual(self.mob.attitude, defaults["state"])
        self.assertEqual(self.mob.fighter.stats["strength"], defaults["stats"]["strength"])

    def test_no_placed_mobs_means_no_mobs(self):
        self.database.mobs = []
        service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.assertEqual(service._mobs, {})

    def test_aggressive_mob_attacks_a_player_in_its_zone(self):
        self.mob.attitude = "aggressive"
        player = type("P", (), {"x": self.mob.home_x + 10, "y": self.mob.home_y, "character_id": 1})()
        self.service._players = {1: player}
        self.assertIs(self.service._aggro_target(self.mob), player)

    def test_neutral_mob_ignores_players_until_provoked(self):
        self.mob.attitude = "neutral"
        player = type("P", (), {"x": self.mob.home_x + 10, "y": self.mob.home_y, "character_id": 1})()
        self.service._players = {1: player}
        self.assertIsNone(self.service._aggro_target(self.mob))
        self.mob.provoker = player
        self.assertIs(self.service._aggro_target(self.mob), player)

    def test_friendly_mob_never_attacks_players(self):
        self.mob.attitude = "friendly"
        player = type("P", (), {"x": self.mob.home_x, "y": self.mob.home_y, "character_id": 1})()
        self.service._players = {1: player}
        self.mob.provoker = player
        self.assertIsNone(self.service._aggro_target(self.mob))

    def test_patrol_points_stay_inside_the_zone_cells(self):
        self.mob.patrol_cells = ((1, 0), (0, 2))
        points = {self.service._pick_patrol_point(self.mob) for _ in range(30)}
        allowed = {(self.mob.home_x + TILE, self.mob.home_y), (self.mob.home_x, self.mob.home_y + 2 * TILE)}
        self.assertTrue(points <= allowed, points)

    def test_respawn_delay_comes_from_the_mode_file(self):
        self.assertEqual(self.mob.respawn_delay, mob_modes.load_mob_settings("tower", IMP)["respawn_seconds"])


if __name__ == "__main__":
    unittest.main()
