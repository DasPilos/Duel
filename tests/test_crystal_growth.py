import unittest
from unittest import mock

from core import crystal_growth
from server import world_map
from server.items_database import ItemsDatabase
from server.world_crystals import CrystalField
from tests.fixtures import create_test_database, drop_test_database
from tests.test_world_mobs import FakeDatabase

TILE = (3, 4)


def _settings(start, end, grow=10):
    return {"grow_seconds": grow, "loot_start": start, "loot_next": end, "harvest_seconds": 5, "loot_item_id": 14}


class CrystalRulesTests(unittest.TestCase):
    def test_loot_interpolates_linearly_between_first_and_last_stage(self):
        settings = _settings(1, 4)
        self.assertEqual([crystal_growth.loot_amount(settings, stage) for stage in range(1, 5)], [1, 2, 3, 4])

    def test_duration_is_parsed_as_hours_minutes_seconds(self):
        self.assertEqual(crystal_growth.parse_duration("0:10:00"), 600)
        with self.assertRaises(ValueError):
            crystal_growth.parse_duration("0:75:00")

    def test_loot_item_must_be_a_material_when_checked(self):
        with self.assertRaises(ValueError):
            crystal_growth.validate_settings({"black": {**_settings(1, 3), "loot_item_id": 999}}, ["black"], {14, 10})
        valid = crystal_growth.validate_settings({"black": _settings(1, 3)}, ["black"], {14})
        self.assertEqual(valid["black"]["loot_item_id"], 14)

    def test_loot_does_not_decrease_along_color_order(self):
        colors = ["black", "blue", "red"]
        with self.assertRaises(ValueError):
            crystal_growth.validate_settings({"black": _settings(2, 4), "blue": _settings(1, 5)}, colors)
        ordered = {"black": _settings(2, 4), "blue": _settings(2, 5), "red": _settings(3, 6)}
        crystal_growth.validate_settings(ordered, colors)

    def test_order_is_checked_against_nearest_configured_colors(self):
        colors = ["black", "blue", "red"]
        settings = {"black": _settings(2, 4), "red": _settings(3, 6)}
        crystal_growth.check_loot_order(settings, colors, "blue", _settings(2, 5))
        with self.assertRaises(ValueError):
            crystal_growth.check_loot_order(settings, colors, "blue", _settings(2, 7))

    def test_color_unlocks_after_previous_color_is_configured(self):
        colors = ["black", "blue"]
        self.assertTrue(crystal_growth.crystal_unlocked({}, colors, "black"))
        self.assertFalse(crystal_growth.crystal_unlocked({}, colors, "blue"))
        self.assertTrue(crystal_growth.crystal_unlocked({"black": _settings(1, 3)}, colors, "blue"))


class CrystalFieldTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.multiple(
            world_map,
            TOWER_CRYSTALS={TILE: {"color": "black", "stage": 1}},
            TOWER_IMPASSABLE_TILES={TILE},
            TOWER_BLOCKED_TILES={TILE},
            TERRAIN_VERSION=0,
            CRYSTAL_SETTINGS={"black": _settings(1, 3, grow=10)},
            PUBLISHED_AT=5.0,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stages_grow_by_time_and_stop_on_the_last_one(self):
        field = CrystalField(FakeDatabase({}))
        field.grow(10)
        self.assertEqual(field.get(TILE)["stage"], 2)
        field.grow(25)
        self.assertEqual((field.get(TILE)["stage"], field.get(TILE)["elapsed"]), (4, 0.0))
        field.grow(100)
        self.assertEqual(field.get(TILE)["stage"], 4)

    def test_growth_progress_survives_restart(self):
        store = FakeDatabase({})
        CrystalField(store).grow(12)
        restored = CrystalField(store).get(TILE)
        self.assertEqual((restored["stage"], restored["elapsed"]), (2, 2.0))

    def test_harvested_crystal_is_not_restored_after_restart(self):
        store = FakeDatabase({})
        field = CrystalField(store)
        field.remove(TILE)
        self.assertIsNone(field.get(TILE))
        self.assertNotIn(TILE, world_map.TOWER_CRYSTALS)
        world_map.TOWER_CRYSTALS = {TILE: {"color": "black", "stage": 1}}
        restarted = CrystalField(store)
        self.assertIsNone(restarted.get(TILE))
        self.assertNotIn(TILE, world_map.TOWER_CRYSTALS)

    def test_new_publication_starts_growth_from_map_stage(self):
        store = FakeDatabase({})
        CrystalField(store).grow(12)
        world_map.PUBLISHED_AT = 6.0
        self.assertEqual(CrystalField(store).get(TILE)["stage"], 1)


class CrystalStateDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        ItemsDatabase(self.database)

    def test_stage_and_harvest_are_stored(self):
        self.database.save_world_crystal_state(5.0, TILE, "black", 2, 3.5)
        self.database.save_world_crystal_state(5.0, (9, 9), "red", 1, 0.0)
        self.database.mark_world_crystal_harvested(5.0, (9, 9))
        states = self.database.load_world_crystal_states(5.0)
        self.assertEqual(states[TILE], {"color": "black", "stage": 2, "elapsed": 3.5, "harvested": False})
        self.assertTrue(states[(9, 9)]["harvested"])

    def test_states_of_older_publications_are_dropped(self):
        self.database.save_world_crystal_state(5.0, TILE, "black", 2, 3.5)
        self.assertEqual(self.database.load_world_crystal_states(6.0), {})
        self.assertEqual(self.database.load_world_crystal_states(5.0), {})

    def test_loot_materials_come_from_items_catalog(self):
        self.assertIn(crystal_growth.CRYSTAL_ITEM_ID, self.database.material_item_ids())


if __name__ == "__main__":
    unittest.main()
