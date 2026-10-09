import math
import time
import unittest

from core.production_buildings import building_level_info
from server.city_population import CityPopulation
from server.city_upgrade import (
    UPGRADE_TICK_SECONDS,
    city_upgrade_cycle_cost,
    city_upgrade_drain_per_tick,
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

    def _set_population(self, amount):
        with self.database.connection() as connection:
            current = connection.execute(
                """SELECT COUNT(*) AS amount, COALESCE(MAX(ordinal), 0) AS max_ordinal
                   FROM city_citizens WHERE world_id=%s AND faction='light' AND alive=TRUE""",
                (self.database.world_id,),
            ).fetchone()
            for ordinal in range(int(current["max_ordinal"]) + 1,
                                 int(current["max_ordinal"]) + max(0, int(amount) - int(current["amount"])) + 1):
                connection.execute(
                    """INSERT INTO city_citizens
                       (world_id, faction, ordinal, name, satiety, satiety_updated_at, created_at)
                       VALUES (%s, 'light', %s, %s, 100, %s, %s)""",
                    (self.database.world_id, ordinal, f"Горожанин {ordinal}",
                     self.start_at - 120, self.start_at - 120),
                )

    def test_level_one_capacity_and_population_based_drain_formula(self):
        self.assertEqual(building_level_info(1, "barn")["storage"], 1000)
        self.assertEqual(building_level_info(1, "warehouse")["storage"], 1000)
        self.assertEqual(city_upgrade_drain_per_tick(10, 10), 100)
        self.assertEqual(city_upgrade_cycle_cost(10, 10), 400)
        self.assertEqual(city_upgrade_drain_per_tick(4, 10), 40)
        self.assertEqual(city_upgrade_cycle_cost(4, 10), 160)

    def test_city_visual_payload_includes_live_population(self):
        with self.database.connection() as connection:
            payload = city_upgrade_payload(
                connection, (self.database.world_id, "light"), self.start_at - 120
            )
        self.assertEqual(payload["city_level"], 1)
        self.assertEqual(payload["population"], 4)
        self.assertEqual(payload["population_capacity"], 10)
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
        self.assertEqual(self._storage("barn", "wheat"), 960)
        self.assertEqual(self._storage("warehouse", "wood"), 960)
        with self.database.connection() as connection:
            payload = city_upgrade_payload(
                connection, (self.database.world_id, "light"),
                self.start_at + UPGRADE_TICK_SECONDS,
            )
        self.assertEqual(payload["phase_index"], 1)

    def test_ap_does_not_start_without_resources_for_all_four_ticks(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 159)
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
        self.assertEqual(self._storage("warehouse", "wood"), 159)

    def test_only_required_goods_are_charged_using_population_formula(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("barn", "berries", 900)
        self._set_storage("warehouse", "wood", 1000)

        self._process_at(self.start_at)
        with self.database.connection() as connection:
            state = self.city.get_state(self.character_id, self.start_at)["city_upgrade"]
        self.assertEqual(set(state["charging_resources"]), {"wheat", "wood"})
        self.assertEqual(state["resource_cost_per_tick"]["wheat"], 40)
        self.assertEqual(state["resource_cost_per_tick"]["wood"], 40)

        self._process_at(self.start_at + 900)
        self.assertEqual(self._storage("barn", "wheat"), 960)
        self.assertEqual(self._storage("warehouse", "wood"), 960)
        self._set_storage("barn", "wheat", 1380)
        self._process_at(self.start_at + 1800)
        self.assertEqual(self._storage("barn", "wheat"), 1340)
        self.assertEqual(self._storage("barn", "berries"), 900)
        self.assertEqual(self._storage("warehouse", "wood"), 920)

    def test_city_stays_level_one_when_a_tick_cannot_be_fully_paid(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)

        for tick in range(1, 4):
            self._process_at(self.start_at + tick * 900)

        self._set_storage("barn", "wheat", 0)
        self._process_at(self.start_at + 3600)

        self.assertEqual(self._storage("barn", "wheat"), 0)
        self.assertEqual(self._storage("warehouse", "wood"), 840)
        self.assertEqual(self._city_level(), 1)
        state = self.city.get_state(self.character_id, self.start_at + 3600)["city_upgrade"]
        self.assertEqual(state["last_result"]["status"], "failed")
        self.assertEqual(state["last_result"]["unpaid_resources"], [{
            "resource": "wheat", "required": 160, "charged": 120, "shortfall": 40,
        }])

    def test_city_levels_up_after_all_fixed_population_costs_are_paid(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)
        for tick in range(1, 5):
            self._process_at(self.start_at + tick * 900)

        self.assertEqual(self._storage("barn", "wheat"), 840)
        self.assertEqual(self._storage("warehouse", "wood"), 840)
        self.assertEqual(self._city_level(), 2)
        state = self.city.get_state(self.character_id, self.start_at + 3600)["city_upgrade"]
        self.assertEqual(state["last_result"]["status"], "completed")

    def test_ten_of_ten_citizens_drain_one_hundred_of_each_resource_per_tick(self):
        self._set_population(10)
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)

        with self.database.connection() as connection:
            cycle = connection.execute(
                "SELECT city_upgrade_cycle FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["city_upgrade_cycle"]
        self.assertEqual(cycle["resources"]["wheat"]["per_tick"], 100)
        self.assertEqual(cycle["resources"]["wood"]["per_tick"], 100)

        for tick in range(1, 5):
            self._process_at(self.start_at + tick * UPGRADE_TICK_SECONDS)
            expected_stock = 1000 - tick * 100
            self.assertEqual(self._storage("barn", "wheat"), expected_stock)
            self.assertEqual(self._storage("warehouse", "wood"), expected_stock)
        self.assertEqual(self._city_level(), 2)

    def test_tick_cost_updates_when_population_changes_during_cycle(self):
        self._set_storage("barn", "wheat", 1000)
        self._set_storage("warehouse", "wood", 1000)
        self._process_at(self.start_at)
        self._process_at(self.start_at + UPGRADE_TICK_SECONDS)
        self._set_population(5)
        self._process_at(self.start_at + 2 * UPGRADE_TICK_SECONDS)

        self.assertEqual(self._storage("barn", "wheat"), 910)
        self.assertEqual(self._storage("warehouse", "wood"), 910)
        with self.database.connection() as connection:
            cycle = connection.execute(
                "SELECT city_upgrade_cycle FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["city_upgrade_cycle"]
        self.assertEqual(cycle["resources"]["wheat"]["tick_costs"], [40, 50])