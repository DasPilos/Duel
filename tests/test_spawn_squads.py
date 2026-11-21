import unittest

from core import spawn_squads


class SpawnSquadPreviewTests(unittest.TestCase):
    def test_preview_reports_ticks_and_mobs_per_tick(self):
        result = spawn_squads.preview({"count": 100, "squad_min": 2, "squad_max": 8}, 500)
        self.assertEqual(result["ticks"], len(result["sizes"]))
        self.assertEqual(sum(result["sizes"]), 100)
        self.assertEqual(result["sizes"][0], 2)
        self.assertEqual(result["sizes"][-1], 9)

    def test_fixed_squad_preview(self):
        result = spawn_squads.preview({"count": 100, "squad_min": 6, "squad_max": 6}, 500)
        self.assertEqual(result["ticks"], 16)
        self.assertEqual(result["sizes"][-1], 10)

    def test_max_defaults_to_min_and_bounds_are_checked(self):
        self.assertEqual(spawn_squads.preview({"count": 5, "squad_min": 3}, 500)["sizes"], [5])
        with self.assertRaises(ValueError):
            spawn_squads.preview({"count": 5, "squad_min": 4, "squad_max": 3}, 500)
        with self.assertRaises(ValueError):
            spawn_squads.preview({"count": 501}, 500)
        with self.assertRaises(ValueError):
            spawn_squads.preview({"count": True}, 500)
        with self.assertRaises(ValueError):
            spawn_squads.preview(["not", "a", "dict"], 500)


if __name__ == "__main__":
    unittest.main()
