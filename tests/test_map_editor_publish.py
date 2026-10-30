import unittest

from tests.fixtures import create_test_database, drop_test_database

MAP_W = 16
MAP_H = 16


class MapPublishTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.user = self.database.register("publish-user", "password")
        self.moderator = self.database.register("publish-mod", "password")
        with self.database.connection() as connection:
            connection.execute("UPDATE users SET role = 'moderator' WHERE id = %s", (self.moderator["id"],))
        self.grass = [{"layer": "ground", "x": 0, "y": 0, "key": "grass_1"}]
        self.rock = [{"layer": "object", "x": 2, "y": 2, "key": "rock_01"}]

    def tearDown(self):
        drop_test_database(self.database)

    def _publish(self, cells, name="Степь", map_w=MAP_W, map_h=MAP_H, user=None):
        user = user or self.moderator
        return self.database.publish_map(cells, self.database.world_id, name, map_w, map_h, user["id"])

    def _live(self):
        return {(c["layer"], c["x"], c["y"], c["key"]) for c in self.database.map_live_cells()}

    def test_catalog_is_seeded_from_assets(self):
        keys = {item["item_key"] for item in self.database.map_catalog()}

        self.assertIn("grass_1", keys)
        self.assertIn("rock_01", keys)

    def test_moderator_publishes_cells_to_world(self):
        cells = self.grass + self.rock

        result = self._publish(cells, name="  Степь  ")

        self.assertEqual(result["applied"], 2)
        self.assertEqual(result["name"], "Степь")
        self.assertEqual(result["world_id"], self.database.world_id)
        self.assertEqual(self._live(), {("ground", 0, 0, "grass_1"), ("object", 2, 2, "rock_01")})

    def test_publish_replaces_previous_map_of_same_world(self):
        self._publish(self.grass)

        self._publish(self.rock, name="Лес")

        self.assertEqual(self._live(), {("object", 2, 2, "rock_01")})
        self.assertEqual(self.database.published_map()["name"], "Лес")

    def test_published_map_reports_name_and_size(self):
        result = self._publish(self.grass, name="Степь", map_w=20, map_h=30)

        published = self.database.published_map()

        self.assertEqual(published["name"], "Степь")
        self.assertEqual((published["map_w"], published["map_h"]), (20, 30))
        self.assertEqual(published["published_at"], result["published_at"])

    def test_regular_user_cannot_publish(self):
        with self.assertRaises(ValueError):
            self._publish(self.grass, user=self.user)

        self.assertEqual(self._live(), set())

    def test_invalid_cells_keep_previous_map(self):
        self._publish(self.grass)

        with self.assertRaises(ValueError):
            self._publish([{"layer": "ground", "x": 1, "y": 1, "key": "missing"}], name="Битая")

        self.assertEqual(self._live(), {("ground", 0, 0, "grass_1")})
        self.assertEqual(self.database.published_map()["name"], "Степь")

    def test_empty_map_is_rejected(self):
        with self.assertRaises(ValueError):
            self._publish([])

        self.assertIsNone(self.database.published_map())

    def test_name_is_checked(self):
        with self.assertRaises(ValueError):
            self._publish(self.grass, name="   ")
        with self.assertRaises(ValueError):
            self._publish(self.grass, name="x" * 65)

    def test_size_outside_limits_is_rejected(self):
        with self.assertRaises(ValueError):
            self._publish(self.grass, map_w=8)
        with self.assertRaises(ValueError):
            self._publish(self.grass, map_h=1000)

    def test_publish_to_unknown_world_is_rejected(self):
        with self.assertRaises(ValueError):
            self.database.publish_map(self.grass, 999999, "Степь", MAP_W, MAP_H, self.moderator["id"])


if __name__ == "__main__":
    unittest.main()
