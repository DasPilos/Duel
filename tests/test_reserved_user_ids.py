import unittest

from tests.fixtures import create_test_database, drop_test_database


class ReservedUserIdsTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def test_new_players_start_after_the_reserved_range(self):
        player = self.database.register("reserve-check", "password")
        self.assertGreater(player["id"], 100)

    def test_reserved_range_is_not_taken_by_registration_after_gaps(self):
        ids = [self.database.register(f"reserve-{index}", "password")["id"] for index in range(3)]
        self.assertTrue(all(user_id > 100 for user_id in ids))
        self.assertEqual(len(set(ids)), 3)


if __name__ == "__main__":
    unittest.main()
