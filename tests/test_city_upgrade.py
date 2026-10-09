import math
import time
import unittest

from core.production_buildings import building_level_info
from server.city_population import CityPopulation
from server.city_upgrade import (
    UPGRADE_TICK_SECONDS,
    city_upgrade_drain_percent,
    city_upgrade_payload,
    process_city_upgrade,
)
from server.production_buildings import ProductionBuildings
from tests.fixtures import create_test_database, drop_test_database


class CityUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        user = self.database.register("city-upgrade", "password")
        self.character_id = self.database.create_character(user["id"], "UpgradeTester")["id"]
        self.city = CityPopulation(self.database)
        self.production = ProductionBuildings(self.database)
        now = time.time()
        self.start_at = (math.floor(now / 3600) + 1) * 3600
        self.city.get_state(self.character_id, self.start_at - 120)
        self.production.get_state(self.character_id, "warehouse", self.start_at - 120)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_population_state
                   SET city_upgrade_last_hour=%s, last_food_tick_at=%s
                   WHERE world_id=%s AND faction='light'""",
                (self.start_at - 3600, self.start_at + 3600, self.database.world_id),
            )

    def tearDown(self):
        drop_test_database(self.database)

    def _set_storage(self, building, resource, amount):
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=%s WHERE world_id=%s AND faction='light'
                   AND building=%s AND resource=%s""",
                (int(amount), self.database.world_id, building, resource),
            )

    def _storage(self, building, resource):
        with self.database.connection() as connection:
            row = connection.execute(
                """SELECT storage FROM building_resources WHERE world_id=%s AND faction='light'
                   AND building=%s AND resource=%s""",
                (self.database.world_id, building, resource),
            ).fetchone()
        return 0 if row is None else int(row["storage"])

    def _process_at(self, timestamp):
        with self.database.connection() as connection:
            return process_city_upgrade(
                connection, (self.database.world_id, "light"), float(timestamp)
            )

    def _city_level(self):
        with self.database.connection() as connection:
            return int(connection.execute(
                "SELECT castle_level FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["castle_level"])

    def test_level_one_storage_capacity_and_drain_schedule(self):
        self.assertEqual(building_level_info(1, "barn")["storage"], 1000)
        self.assertEqual(building_level_info(1, "warehouse")["storage"], 1000)
        self.assertEqual(
            [city_upgrade_drain_percent(level) for level in (1, 2, 3, 4, 5)],
            [12, 13, 14, 15, 15],
        )

    def test_city_visual_payload_includes_live_population(self):
        with self.database.connection() as connection:
            payload = city_upgrade_payload(
                connection, (self.database.world_id, "light"), self.start_at - 120
            )
        self.assertEqual(payload["city_level"], 1)
        self.assertEqual(payload["population"], 4)
        self.assertFalse(payload["active"])

    def test_population_ticker_advances_cycle_without_ui_requests(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self.city.tick_all(now=self.start_at)
        with self.database.connection() as connection:
            state = connection.execute(
                """SELECT city_upgrade_cycle FROM city_population_state
                   WHERE world_id=%s AND faction='light'""",
                (self.database.world_id,),
            ).fetchone()["city_upgrade_cycle"]
        self.assertTrue(state["active"])

        self.city.tick_all(now=self.start_at + UPGRADE_TICK_SECONDS)
        self.assertEqual(self._storage("barn", "wheat"), 880)
        self.assertEqual(self._storage("warehouse", "wood"), 880)
        with self.database.connection() as connection:
            payload = city_upgrade_payload(
                connection, (self.database.world_id, "light"),
                self.start_at + UPGRADE_TICK_SECONDS,
            )
        self.assertEqual(payload["phase_index"], 1)

    def test_ap_does_not_start_until_all_required_goods_are_in_surplus(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 700)
        self._set_storage("barn", "berries", 900)

        self._process_at(self.start_at)
        with self.database.connection() as connection:
            row = connection.execute(
                """SELECT city_upgrade_cycle FROM city_population_state
                   WHERE world_id=%s AND faction='light'""",
                (self.database.world_id,),
            ).fetchone()
        self.assertFalse(row["city_upgrade_cycle"].get("active", False))
        self.assertEqual(self._storage("barn", "wheat"), 1000)
        self.assertEqual(self._storage("warehouse", "wood"), 700)

    def test_only_required_goods_in_surplus_are_charged(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("barn", "berries", 900)
        self._set_storage("warehouse", "wood", 1000)

        self._process_at(self.start_at)
        with self.database.connection() as connection:
            state = self.city.get_state(self.character_id, self.start_at)["city_upgrade"]
        self.assertEqual(set(state["charging_resources"]), {"wheat", "wood"})
        self.assertEqual(state["rate_percent"], 12)

        self._process_at(self.start_at + 900)
        self.assertEqual(self._storage("barn", "wheat"), 880)
        self.assertEqual(self._storage("warehouse", "wood"), 880)
        self._set_storage("barn", "wheat", 1380)
        self._process_at(self.start_at + 1800)
        self.assertEqual(self._storage("barn", "wheat"), 1260)
        self.assertEqual(self._storage("barn", "berries"), 900)
        self.assertEqual(self._storage("warehouse", "wood"), 760)

    def test_city_stays_level_one_when_stock_falls_below_surplus(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)

        for tick in range(1, 5):
            self._process_at(self.start_at + tick * 900)

        self.assertEqual(self._storage("barn", "wheat"), 520)
        self.assertEqual(self._storage("warehouse", "wood"), 520)
        self.assertEqual(self._city_level(), 1)
        state = self.city.get_state(self.character_id, self.start_at + 3600)["city_upgrade"]
        self.assertEqual(state["last_result"]["status"], "failed")
        self.assertEqual({row["resource"] for row in state["last_result"]["below_threshold"]},
                         {"wheat", "wood"})

    def test_city_levels_up_if_every_required_good_stays_in_surplus(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)
        for tick in range(1, 4):
            self._process_at(self.start_at + tick * 900)

        self._set_storage("barn", "wheat", self._storage("barn", "wheat") + 310)
        self._set_storage("warehouse", "wood", self._storage("warehouse", "wood") + 310)
        self._process_at(self.start_at + 3600)

        self.assertEqual(self._storage("barn", "wheat"), 830)
        self.assertEqual(self._storage("warehouse", "wood"), 830)
        self.assertEqual(self._city_level(), 2)
        state = self.city.get_state(self.character_id, self.start_at + 3600)["city_upgrade"]
        self.assertEqual(state["last_result"]["status"], "completed")