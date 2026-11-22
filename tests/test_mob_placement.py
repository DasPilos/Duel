import random
import unittest
from unittest.mock import patch

from core import mob_modes
from server import world_map
from server.world_map import TILE
from front_line.server.world_mobs import WorldService
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
        defaults = mob_modes.load_mob_settings("front_line", IMP)  # значения из файла режима
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

    def test_patrol_route_stays_inside_the_zone_cells(self):
        self.mob.patrol_cells = ((1, 0), (0, 2))
        route = self.service._plan_patrol_route(self.mob)
        allowed = {(self.mob.home_x + TILE, self.mob.home_y), (self.mob.home_x, self.mob.home_y + 2 * TILE)}
        self.assertTrue(route)
        self.assertTrue(set(route) <= allowed, route)

    def test_respawn_delay_comes_from_the_mode_file(self):
        self.assertEqual(self.mob.respawn_delay, mob_modes.load_mob_settings("front_line", IMP)["respawn_seconds"])


def _wall_terrain(lo, hi, gap=None):
    """Тонкая стена по X в полосе [lo, hi); если задан gap по Y, в этом промежутке стена открыта."""
    def blocked(x, y):
        if not (lo <= x < hi):
            return False
        return gap is None or not (gap[0] <= y < gap[1])
    return blocked


class PatrolRouteTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase({1: 7})
        self.database.mobs = [{"kind": IMP, "x": 10, "y": 12}]
        self.live = patch.object(world_map, "LIVE_MAP", True)
        self.live.start()
        self.addCleanup(self.live.stop)
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.mob = self.service._mobs[f"mob_0_{IMP}"]

    def _patrol(self, dt, ticks, on_tick):
        max_x = self.mob.x
        for _ in range(ticks):
            self.service._update_mob_patrol(self.mob, dt)
            on_tick()
            max_x = max(max_x, self.mob.x)
        return max_x

    def test_thin_wall_is_never_crossed_on_a_patrol(self):
        lo = self.mob.home_x + TILE + 8
        for dt in (0.1, 0.25):
            with self.subTest(dt=dt):
                self.mob.x, self.mob.y = self.mob.home_x, self.mob.home_y
                self.mob.patrol_route = []
                self.mob.patrol_pause = 0.0
                self.service._terrain_blocked = _wall_terrain(lo, lo + 2)
                max_x = self._patrol(dt, 3000, lambda: self.assertLess(self.mob.x, lo))
                self.assertGreater(max_x, self.mob.home_x + TILE // 2)

    def test_patrol_goes_around_a_wall_only_through_the_gap(self):
        lo = self.mob.home_x + 2 * TILE - 24
        gap = (self.mob.home_y + 2 * TILE - 8, self.mob.home_y + 2 * TILE + 8)
        self.service._terrain_blocked = _wall_terrain(lo, lo + 2, gap)

        def check():
            if lo <= self.mob.x < lo + 2:
                self.assertTrue(gap[0] <= self.mob.y < gap[1], (self.mob.x, self.mob.y))

        max_x = self._patrol(0.25, 3000, check)
        self.assertGreater(max_x, lo + 2)


class ChaseRouteTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase({1: 7})
        self.database.mobs = [{"kind": IMP, "x": 10, "y": 12}]
        self.live = patch.object(world_map, "LIVE_MAP", True)
        self.live.start()
        self.addCleanup(self.live.stop)
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.service._players = {}
        self.mob = self.service._mobs[f"mob_0_{IMP}"]
        self.player = type("P", (), {"x": self.mob.home_x + 4 * TILE, "y": self.mob.home_y, "character_id": 1})()

    def _chase(self, ticks, dt, on_tick):
        for _ in range(ticks):
            self.service._move_mob_toward(self.mob, self.player, dt)
            on_tick()

    def test_chase_goes_around_a_wall_only_through_the_gap(self):
        lo = self.mob.home_x + 2 * TILE - 24
        gap = (self.mob.home_y + 2 * TILE - 8, self.mob.home_y + 2 * TILE + 8)
        self.service._terrain_blocked = _wall_terrain(lo, lo + 2, gap)

        def check():
            if lo <= self.mob.x < lo + 2:
                self.assertTrue(gap[0] <= self.mob.y < gap[1], (self.mob.x, self.mob.y))

        self._chase(3000, 0.1, check)
        self.assertGreater(self.mob.x, lo + 2)

    def test_chase_never_crosses_a_full_wall(self):
        lo = self.mob.home_x + 2 * TILE - 24
        self.service._terrain_blocked = _wall_terrain(lo, lo + 2)
        self._chase(1000, 0.1, lambda: self.assertLess(self.mob.x, lo))


if __name__ == "__main__":
    unittest.main()
