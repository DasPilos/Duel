import unittest

from server.world_events import WorldEventWatcher


class WorldEventWatcherTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"food_status": "Пищи достаточно", "storages": {}}
        self.published = []
        self.watcher = WorldEventWatcher(
            lambda: self.snapshot,
            lambda key, context, lines: self.published.append((key, context, lines)) or True,
            cooldown=60,
        )

    def test_baseline_is_silent_and_hunger_transition_is_announced_once(self):
        self.assertEqual(self.watcher.poll(now=100), 0)
        self.snapshot["food_status"] = "В городе голод"

        self.assertEqual(self.watcher.poll(now=130), 1)
        self.assertEqual(self.published[0][0], "food:hunger")
        self.assertIn("голод", " ".join(self.published[0][2]))
        self.assertEqual(self.watcher.poll(now=160), 0)
        self.assertEqual(len(self.published), 1)

    def test_food_recovery_is_announced_as_a_state_transition(self):
        self.watcher.poll(now=100)
        self.snapshot["food_status"] = "Население не доедает"
        self.assertEqual(self.watcher.poll(now=120), 1)
        self.snapshot["food_status"] = "Пищи достаточно"

        self.assertEqual(self.watcher.poll(now=140), 1)
        self.assertEqual(self.published[-1][0], "food:recovered")

    def test_full_storage_only_announces_transition_and_refill_after_cooldown(self):
        self.watcher.poll(now=100)
        self.snapshot["storages"] = {
            "farm": {"name": "Ферма", "total": 10, "limit": 10},
        }

        self.assertEqual(self.watcher.poll(now=120), 1)
        self.assertEqual(self.published[0][0], "storage-full:farm")
        self.assertEqual(self.watcher.poll(now=130), 0)

        self.snapshot["storages"]["farm"]["total"] = 9
        self.assertEqual(self.watcher.poll(now=140), 0)
        self.snapshot["storages"]["farm"]["total"] = 10
        self.assertEqual(self.watcher.poll(now=200), 1)
        self.assertEqual(len(self.published), 2)

    def test_missing_snapshot_does_not_change_baseline(self):
        self.snapshot = None
        self.assertEqual(self.watcher.poll(now=100), 0)
        self.snapshot = {"food_status": "В городе голод", "storages": {}}
        self.assertEqual(self.watcher.poll(now=110), 0)
        self.assertEqual(self.published, [])


if __name__ == "__main__":
    unittest.main()
