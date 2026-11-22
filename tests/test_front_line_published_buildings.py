import threading
import unittest
from unittest.mock import MagicMock, patch

from front_line.server.world import FrontLineWorldService
from front_line.server.world_mobs import WorldService


def _service(database):
    service = FrontLineWorldService.__new__(FrontLineWorldService)
    service._database = database
    service._building_states = []
    service._lock = threading.RLock()
    return service


def _saved(building_x=10, building_y=12):
    return {
        "id": 7,
        "spawns": [{
            "type": "building", "x": building_x, "y": building_y, "sprite": "castle_5",
            "settings": {"hp": 500, "hp_regen_per_minute": 0, "defense_slots": []},
        }],
    }


class PublishedBuildingsTests(unittest.TestCase):
    def test_uses_published_saved_map_not_first(self):
        database = MagicMock()
        database.published_map.return_value = {"saved_id": 7}
        database.get_saved_map.return_value = _saved()
        service = _service(database)
        self.assertEqual(service._published_saved_map()["id"], 7)
        database.first_saved_map.assert_not_called()
        database.get_saved_map.assert_called_once_with(7)

    def test_falls_back_to_first_map_without_publication(self):
        database = MagicMock()
        database.published_map.return_value = None
        database.first_saved_map.return_value = _saved()
        service = _service(database)
        self.assertEqual(service._published_saved_map()["id"], 7)
        database.first_saved_map.assert_called_once_with("front_line")

    def test_falls_back_when_saved_map_is_missing(self):
        database = MagicMock()
        database.published_map.return_value = {"saved_id": 9}
        database.get_saved_map.side_effect = ValueError("Карта на сервере не найдена")
        database.first_saved_map.return_value = None
        service = _service(database)
        self.assertIsNone(service._published_saved_map())
        database.first_saved_map.assert_called_once_with("front_line")

    def test_reload_terrain_takes_buildings_from_published_map(self):
        database = MagicMock()
        database.published_map.return_value = {"saved_id": 7}
        database.get_saved_map.return_value = _saved(10, 12)
        service = _service(database)
        terrain = {"impassable": frozenset()}
        published = {"map_w": 64, "map_h": 64, "saved_id": 7}
        with patch.object(WorldService, "reload_terrain") as base_reload:
            service.reload_terrain(terrain, published)
        base_reload.assert_called_once_with(terrain, published)
        self.assertEqual(len(service._building_states), 1)
        self.assertEqual(service._building_states[0]["sprite"], "castle_5")
        self.assertIn((10, 12), terrain["impassable"])
        self.assertIn((14, 16), terrain["impassable"])
        self.assertNotIn((15, 16), terrain["impassable"])

    def test_reload_terrain_without_terrain_keeps_base_behaviour(self):
        database = MagicMock()
        database.published_map.return_value = None
        service = _service(database)
        with patch.object(WorldService, "reload_terrain") as base_reload:
            service.reload_terrain(None, None)
        base_reload.assert_called_once_with(None, None)
        self.assertEqual(service._building_states, [])


if __name__ == "__main__":
    unittest.main()
