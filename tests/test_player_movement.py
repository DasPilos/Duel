import unittest

from core.player_movement import find_tile_path, follow_path


def _wall_blocker(blocked_tiles, tile_size=32):
    def is_blocked(x, y):
        return (int(x // tile_size), int(y // tile_size)) in blocked_tiles
    return is_blocked


class FindTilePathTests(unittest.TestCase):
    def test_open_field_returns_path_ending_at_goal(self):
        path = find_tile_path((16, 16), (16 + 32 * 5, 16), _wall_blocker(set()))
        self.assertIsNotNone(path)
        self.assertEqual(path[-1], (16 + 32 * 5, 16))

    def test_same_tile_returns_goal_only(self):
        path = find_tile_path((10, 10), (20, 20), _wall_blocker(set()))
        self.assertEqual(path, [(20, 20)])

    def test_blocked_goal_returns_none(self):
        goal = (16 + 32 * 3, 16)
        path = find_tile_path((16, 16), goal, _wall_blocker({(3, 0)}))
        self.assertIsNone(path)

    def test_path_goes_around_wall(self):
        # Вертикальная стена на x=2 от y=0 до y=3, обход через y=4
        wall = {(2, y) for y in range(4)}
        start = (16, 16)
        goal = (16 + 32 * 4, 16)
        path = find_tile_path(start, goal, _wall_blocker(wall))
        self.assertIsNotNone(path)
        self.assertEqual(path[-1], goal)
        for px, py in path:
            self.assertNotIn((int(px // 32), int(py // 32)), wall)

    def test_no_route_returns_none(self):
        # Замкнутая коробка вокруг старта: выхода нет, поиск должен завершиться отказом
        box = {(x, y) for x in range(-1, 4) for y in range(-1, 4)} - {(x, y) for x in range(0, 3) for y in range(0, 3)}
        path = find_tile_path((16 + 32, 16 + 32), (16 + 32 * 10, 16), _wall_blocker(box), max_nodes=400)
        self.assertIsNone(path)


class FollowPathTests(unittest.TestCase):
    def test_consumes_waypoints_within_budget(self):
        path = [(10.0, 0.0), (20.0, 0.0)]
        x, y, moved = follow_path(0.0, 0.0, path, 15.0, _wall_blocker(set()))
        self.assertTrue(moved)
        self.assertAlmostEqual(x, 15.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertEqual(path, [(20.0, 0.0)])

    def test_partial_step_toward_next_waypoint(self):
        path = [(100.0, 0.0)]
        x, y, moved = follow_path(0.0, 0.0, path, 4.0, _wall_blocker(set()))
        self.assertTrue(moved)
        self.assertAlmostEqual(x, 4.0)
        self.assertEqual(path, [(100.0, 0.0)])

    def test_stops_at_blocked_waypoint(self):
        path = [(10.0, 0.0), (80.0, 0.0)]
        blocked = _wall_blocker({(2, 0)})  # тайл x 64..96
        x, y, moved = follow_path(0.0, 0.0, path, 200.0, blocked)
        self.assertAlmostEqual(x, 10.0)
        self.assertEqual(path, [(80.0, 0.0)])

    def test_empty_path_does_nothing(self):
        x, y, moved = follow_path(5.0, 6.0, [], 10.0, _wall_blocker(set()))
        self.assertEqual((x, y, moved), (5.0, 6.0, False))


if __name__ == "__main__":
    unittest.main()
