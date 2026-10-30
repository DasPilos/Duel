import random
import unittest
from types import SimpleNamespace

from server import world_map
from server.world_map import TILE
from server.world_mobs import WorldService
from tests.test_world_mobs import FakeClock, FakeDatabase, FakeItems

SPAWN_A = (5, 5)
SPAWN_B = (60, 40)


def pixels(tile):
    return (tile[0] * TILE + TILE // 2, tile[1] * TILE + TILE // 2)


class SpawnPointTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase({1: 7})
        self.database.spawns = [SPAWN_A, SPAWN_B]
        self.service = WorldService(self.database, FakeItems(), clock=FakeClock(), rng=random.Random(3))
        self.service._terrain_blocked = lambda x, y: False
        self.events = []
        self.service._emit_notice = lambda player, text: self.events.append(text)

    def test_entry_starts_at_the_spawn_nearest_to_the_saved_position(self):
        self.assertEqual(self.service._entry_position(pixels(SPAWN_B)[0] + 10, pixels(SPAWN_B)[1]), pixels(SPAWN_B))
        self.assertEqual(self.service._entry_position(pixels(SPAWN_A)[0] - 3, pixels(SPAWN_A)[1] + 9), pixels(SPAWN_A))

    def test_entry_without_a_saved_position_uses_one_of_the_spawns(self):
        self.assertIn(self.service._entry_position(None, None), [pixels(SPAWN_A), pixels(SPAWN_B)])

    def test_no_spawns_keeps_the_map_centre(self):
        self.database.spawns = []
        self.assertEqual(self.service._entry_position(None, None),
                         (float(world_map.MAP_SPAWN_PX[0]), float(world_map.MAP_SPAWN_PX[1])))

    def test_death_respawns_at_the_nearest_spawn_with_full_health(self):
        player = SimpleNamespace(
            x=pixels(SPAWN_B)[0] - 40, y=pixels(SPAWN_B)[1] + 20, move_path=[1, 2], attack_target=object(),
            fighter=SimpleNamespace(hp=0, max_hp=50), dirty=False,
        )
        self.service._respawn_player(player, player.x, player.y)
        self.assertEqual((player.x, player.y), pixels(SPAWN_B))
        self.assertEqual(player.fighter.hp, 50)
        self.assertEqual(player.move_path, [])
        self.assertIsNone(player.attack_target)
        self.assertTrue(player.dirty)
        self.assertEqual(len(self.events), 1)

    def test_death_near_the_first_spawn_goes_back_to_it(self):
        player = SimpleNamespace(
            x=pixels(SPAWN_A)[0] + 5, y=pixels(SPAWN_A)[1], move_path=[], attack_target=None,
            fighter=SimpleNamespace(hp=0, max_hp=30), dirty=False,
        )
        self.service._respawn_player(player, player.x, player.y)
        self.assertEqual((player.x, player.y), pixels(SPAWN_A))


if __name__ == "__main__":
    unittest.main()
