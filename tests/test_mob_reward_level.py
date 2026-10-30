import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import mob_modes
from server import world_map
from server.world_mobs import WorldService
from tests.test_world_mobs import FakeClock, FakeDatabase, FakeItems

IMP = "imp_sword"


class RewardAndLevelTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.modes = patch.object(mob_modes, "MODES_DIR", Path(self.folder.name))
        self.modes.start()
        self.addCleanup(self.modes.stop)
        self.database = FakeDatabase({1: 7})
        self.database.mobs = [{"kind": IMP, "x": 10, "y": 12}]
        live = patch.object(world_map, "LIVE_MAP", True)
        live.start()
        self.addCleanup(live.stop)
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.mob = self.service._mobs[f"mob_0_{IMP}"]

    def configure(self, **changes):
        settings = {**mob_modes.default_settings(IMP), **changes}
        mob_modes.save_mob_settings("tower", IMP, settings, self.folder.name)
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        return self.service._mobs[f"mob_0_{IMP}"]

    def test_reward_from_the_mode_file_is_the_coin_pool_of_the_mob(self):
        mob = self.configure(reward_copper=250)
        self.assertEqual(mob.reward_copper, 250)
        self.assertEqual(mob.coins_copper, 250)

    def test_default_reward_is_the_default_coin_pool(self):
        self.assertEqual(self.mob.reward_copper, mob_modes.DEFAULT_REWARD_COPPER)

    def test_xp_reward_from_the_mode_file_reaches_the_mob(self):
        mob = self.configure(reward_xp=40)
        self.assertEqual(mob.reward_xp, 40)
        self.assertEqual(self.mob.reward_xp, mob_modes.DEFAULT_REWARD_XP)

    def test_snapshot_carries_the_level_of_the_placed_mob(self):
        mob = self.configure(level=3, stats={**mob_modes.default_settings(IMP)["stats"], "endurance": 6})
        payload = self.service._mob_payload(mob)
        self.assertEqual(payload["level"], 3)

    def test_patrolling_mob_faces_its_move_direction(self):
        self.service._terrain_blocked = lambda x, y: False
        self.mob.patrol_cells = ((0, 0), (3, 0))
        self.mob.patrol_target = (self.mob.home_x + 3 * world_map.TILE, self.mob.home_y)
        self.mob.facing = 0.0
        self.service._update_mob_patrol(self.mob, 0.1)
        self.assertAlmostEqual(self.mob.facing, 0.0, places=3)
        self.mob.patrol_target = (self.mob.home_x, self.mob.home_y + 3 * world_map.TILE)
        self.mob.x, self.mob.y = self.mob.home_x, self.mob.home_y
        self.service._update_mob_patrol(self.mob, 0.1)
        self.assertGreater(self.mob.facing, 0.0)  # вниз по экрану


class RewardValidationTests(unittest.TestCase):
    def test_reward_is_a_whole_number_of_copper(self):
        settings = {**mob_modes.default_settings(IMP), "reward_copper": 120.0}
        self.assertEqual(mob_modes.validate_settings(settings)["reward_copper"], 120)
        with self.assertRaises(ValueError):
            mob_modes.validate_settings({**settings, "reward_copper": -5})

    def test_xp_reward_defaults_to_ten_and_is_a_whole_number(self):
        settings = mob_modes.default_settings(IMP)
        self.assertEqual(settings["reward_xp"], 10)
        self.assertEqual(mob_modes.validate_settings({**settings, "reward_xp": 45.0})["reward_xp"], 45)
        with self.assertRaises(ValueError):
            mob_modes.validate_settings({**settings, "reward_xp": -1})


if __name__ == "__main__":
    unittest.main()
