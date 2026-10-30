import unittest
from types import SimpleNamespace

from client.app_flow import opens_map_first


class MapWorldEntryTests(unittest.TestCase):
    def test_map_worlds_open_on_the_map_not_in_the_tavern(self):
        self.assertTrue(opens_map_first(SimpleNamespace(map_world=True)))

    def test_ordinary_worlds_keep_the_tavern(self):
        self.assertFalse(opens_map_first(SimpleNamespace(map_world=False)))
        self.assertFalse(opens_map_first(SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
