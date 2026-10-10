import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from core import settings
from core.cart_progress import CART_GRADES, DEFAULT_CART_PROGRESS
from core.production_buildings import building_resources, upgrade_requirements
from server.items_database import ItemsDatabase
from server.production_buildings import ProductionBuildings, STORAGE_RESOURCES_BY_ITEM_ID
from server.structures import city_structures
from tests.fixtures import create_test_database, drop_test_database

BARN_GOODS = ("berries", "wheat", "meat")
WAREHOUSE_GOODS = (
    "wood", "board", "flax", "cotton", "leather", "coal", "stone", "iron", "mithril", "obsidian",
    "iron_ingot", "steel", "hard_leather", "thick_leather", "cloth", "stone_block",
    "jet", "malachite", "topaz", "garnet", "emerald", "ruby", "sapphire", "diamond",
)


class CityStorageServerTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.buildings = ProductionBuildings(self.database)
        user = self.database.register("keeper", "password")
        self.character_id = self.database.create_character(user["id"], "Keeper")["id"]
        with self.database.connection() as connection:
            connection.execute(
                """INSERT INTO city_population_state (world_id, faction, castle_level, last_food_tick_at)
                   VALUES (%s, 'light', 4, 0) ON CONFLICT (world_id, faction)
                   DO UPDATE SET castle_level = 4""",
                (self.database.world_id,),
            )
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET stats_json = %s WHERE id = %s",
                ('{"strength":1000,"agility":3,"intuition":3,"wisdom":3,"intellect":3,"harmony":3,"endurance":3}',
                 self.character_id),
            )

    def tearDown(self):
        drop_test_database(self.database)

    def _deposit_warehouse(self, character_id, item_id, quantity, now=10000):
        items = ItemsDatabase(self.database)
        resource = STORAGE_RESOURCES_BY_ITEM_ID[item_id]
        items.add_to_inventory(character_id, item_id, quantity)
        return self.buildings.deposit_to_storage(character_id, "warehouse", resource, quantity, now)

    def _set_city_level(self, level):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET castle_level=%s WHERE world_id=%s AND faction='light'",
                (int(level), self.database.world_id),
            )

    def test_goods_lists_and_capacity(self):
        barn = self.buildings.get_state(self.character_id, "barn", 10000)
        self.assertEqual(barn["storage"], {**{good: 0 for good in BARN_GOODS}, "limit": 1000})
        self.assertEqual(barn["worker_slots"], [])
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10000)
        self.assertEqual(warehouse["storage"], {**{good: 0 for good in WAREHOUSE_GOODS}, "limit": 1000})
        self.assertEqual(building_resources("barn"), BARN_GOODS)

    def test_level_one_storage_only_exposes_and_accepts_initial_resources(self):
        self._set_city_level(1)
        barn = self.buildings.get_state(self.character_id, "barn", 10000)
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10000)
        self.assertEqual(barn["storage"], {"wheat": 0, "limit": 1000})
        self.assertEqual(warehouse["storage"], {"wood": 0, "limit": 1000})

        items = ItemsDatabase(self.database)
        items.add_to_inventory(self.character_id, 62, 5)
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            self.buildings.deposit_to_storage(self.character_id, "barn", "berries", 5, 10001)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=5 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='iron'""",
                (self.database.world_id,),
            )
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            self.buildings.withdraw_from_storage(self.character_id, "warehouse", "iron", 1, 10002)
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10003)
        self.assertEqual(warehouse["storage"], {"wood": 0, "limit": 1000})
        self.assertEqual(warehouse["storage_total"], 0)
        self._set_city_level(3)
        self.assertNotIn(
            "diamond", self.buildings.get_state(self.character_id, "warehouse", 10004)["storage"]
        )
        self._set_city_level(4)
        self.assertIn(
            "diamond", self.buildings.get_state(self.character_id, "warehouse", 10005)["storage"]
        )

    def test_level_two_storage_exposes_only_wheat_wood_and_stone(self):
        self._set_city_level(2)
        barn = self.buildings.get_state(self.character_id, "barn", 10000)
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10000)
        self.assertEqual(barn["storage"], {"wheat": 0, "limit": 1000})
        self.assertEqual(
            warehouse["storage"], {"wood": 0, "stone": 0, "limit": 1000},
        )

    def test_each_city_storage_resource_has_its_own_capacity(self):
        items = ItemsDatabase(self.database)
        items.add_to_inventory(self.character_id, 63, 1000)
        self.buildings.deposit_to_storage(self.character_id, "barn", "wheat", 1000, 10000)
        items.add_to_inventory(self.character_id, 62, 1000)
        barn = self.buildings.deposit_to_storage(
            self.character_id, "barn", "berries", 1000, 10001
        )
        self.assertEqual((barn["storage"]["wheat"], barn["storage"]["berries"]), (1000, 1000))
        self.assertEqual(barn["storage_total"], 2000)

        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=1000 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
        warehouse = self._deposit_warehouse(self.character_id, 10, 1, 10003)
        self.assertEqual((warehouse["storage"]["wood"], warehouse["storage"]["iron"]), (1000, 1))
        self.assertEqual(warehouse["storage_total"], 1001)

    def test_upgrade_levels_and_max_level(self):
        items = ItemsDatabase(self.database)
        expected = {"barn": (1000, 1500, 2000, 2700, 4000), "warehouse": (1000, 3000, 5000, 7000, 10000)}
        for building, capacities in expected.items():
            now = 10000
            for level in range(1, 5):
                for item_id, required in upgrade_requirements(level, building)["materials"].items():
                    self._deposit_warehouse(self.character_id, item_id, required, now)
                self.buildings.start_upgrade(self.character_id, building, now)
                now += upgrade_requirements(level, building)["time_seconds"]
                state = self.buildings.get_state(self.character_id, building, now)
                self.assertEqual(state["level"], level + 1)
                self.assertEqual(state["storage"]["limit"], capacities[level])
            self.assertIsNone(state["upgrade"])
            with self.assertRaisesRegex(ValueError, "максимального уровня"):
                self.buildings.start_upgrade(self.character_id, building, now)

    def test_stable_building_upgrade_takes_five_hours(self):
        self.assertEqual(upgrade_requirements(1, "stable")["time_seconds"], 5 * 3600)
        self.assertEqual(upgrade_requirements(1, "farm")["time_seconds"], 2 * 3600)

    def test_player_cannot_replace_a_citizen_in_an_occupied_work_slot(self):
        self.buildings.get_state(self.character_id, "farm", 10000)
        self.buildings.hire_worker(self.character_id, "farm", 0, "citizen-1", 10001)

        with self.assertRaisesRegex(ValueError, "занято горожанином"):
            self.buildings.toggle_player_worker(self.character_id, "farm", 0, 10002)

        state = self.buildings.get_state(self.character_id, "farm", 10003)
        self.assertEqual(state["worker_slots"][0]["worker_id"], "citizen-1")
        self.assertFalse(state["worker_slots"][1]["occupied"])
        state = self.buildings.toggle_player_worker(self.character_id, "farm", 1, 10004)
        self.assertEqual(state["worker_slots"][0]["worker_id"], "citizen-1")
        self.assertEqual(state["worker_slots"][1]["worker_id"], f"player:{self.character_id}")

    def test_shared_stable_capacity_increases_by_two_per_level(self):
        user = self.database.register("stablemate", "password")
        teammate = self.database.create_character(user["id"], "Stablemate")["id"]
        state = self.buildings.get_state(self.character_id, "stable", 10000)
        self.assertEqual(state["stall_capacity"], 4)
        self.assertEqual(state["occupied_stalls"], 0)
        self.assertEqual(state["feed_consumption_kg_per_hour"], 0)
        self.assertEqual(sum(1 for slot in state["stall_slots"] if slot["unlocked"]), 4)
        self.assertEqual(state["stall_slots"][4]["unlock_level"], 2)
        with self.database.connection() as connection:
            connection.execute("UPDATE building_states SET level = 2 WHERE building = 'stable'")
        shared_state = self.buildings.get_state(teammate, "stable", 10001)
        self.assertEqual(shared_state["stall_capacity"], 6)
        self.assertEqual(shared_state["level"], 2)
        self.assertEqual(sum(1 for slot in shared_state["stall_slots"] if slot["unlocked"]), 6)

    def test_horse_price_stays_ten_silver_and_horses_are_shared(self):
        from core.production_buildings import horse_purchase_price_silver

        self.assertEqual([horse_purchase_price_silver(count) for count in range(5)],
                 [10, 10, 10, 10, 10])
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET copper=0,silver=0,gold=0 WHERE id=%s",
                (self.character_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=4000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        state = self.buildings.get_state(self.character_id, "stable", 10000)
        self.assertEqual(state["horse_price_next_silver"], 10)
        for slot_index, price in enumerate((10, 10, 10, 10)):
            state = self.buildings.purchase_horse(self.character_id, slot_index, 10001 + slot_index)
            horse = state["stall_slots"][slot_index]["horse"]
            self.assertEqual(horse["purchase_price_silver"], price)
            self.assertEqual(horse["status"], "Отдыхает")
        self.assertEqual(state["occupied_stalls"], 4)
        self.assertEqual(state["horse_price_next_silver"], 10)
        self.assertEqual(state["treasury_silver_available"], 0)
        with self.database.connection() as connection:
            wallet = connection.execute(
                "SELECT copper,silver,gold FROM characters WHERE id=%s",
                (self.character_id,),
            ).fetchone()
        self.assertEqual((wallet["copper"], wallet["silver"], wallet["gold"]), (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "Стойло ещё не открыто"):
            self.buildings.purchase_horse(self.character_id, 4, 10005)

        teammate_user = self.database.register("horse-mate", "password")
        teammate_id = self.database.create_character(teammate_user["id"], "HorseMate")["id"]
        shared = self.buildings.get_state(teammate_id, "stable", 10006)
        self.assertEqual(shared["occupied_stalls"], 4)
        self.assertEqual(shared["stall_slots"][3]["horse"]["purchase_price_silver"], 10)

    def test_horse_satiety_uses_wheat_and_idle_or_work_rate(self):
        self.buildings.get_state(self.character_id, "barn", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=1000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        self.buildings.purchase_horse(self.character_id, 0, now=10000)
        with self.database.connection() as connection:
            horse_id = connection.execute(
                "SELECT id FROM stable_horses WHERE world_id=%s AND faction='light' AND slot_index=0",
                (self.database.world_id,),
            ).fetchone()["id"]
            connection.execute(
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 0 ELSE 5 END "
                "WHERE world_id=%s AND faction='light' AND building='barn' "
                "AND resource IN ('wheat', 'berries', 'meat')",
                (self.database.world_id,),
            )

        idle = self.buildings.get_state(self.character_id, "stable", 20500)
        horse = idle["stall_slots"][0]["horse"]
        self.assertEqual(horse["satiety"], 30)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=3 WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            )
        fed_at_rest = self.buildings.get_state(self.character_id, "stable", 20500)
        self.assertEqual(fed_at_rest["stall_slots"][0]["horse"]["satiety"], 60)

        with self.database.connection() as connection:
            connection.execute("UPDATE stable_horses SET status='В пути' WHERE id=%s", (horse_id,))
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            )
        working = self.buildings.get_state(self.character_id, "stable", 22300)
        self.assertEqual(working["stall_slots"][0]["horse"]["satiety"], 30)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=3 WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            )
        fed_on_route = self.buildings.get_state(self.character_id, "stable", 22300)
        self.assertEqual(fed_on_route["stall_slots"][0]["horse"]["satiety"], 60)
        with self.database.connection() as connection:
            wheat = connection.execute(
                "SELECT storage FROM building_resources WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertEqual(wheat, 0)
        with self.database.connection() as connection:
            other_food = connection.execute(
                "SELECT resource, storage FROM building_resources WHERE world_id=%s "
                "AND faction='light' AND building='barn' AND resource IN ('berries', 'meat')",
                (self.database.world_id,),
            ).fetchall()
        self.assertEqual({row["resource"]: row["storage"] for row in other_food},
                         {"berries": 5, "meat": 5})

    def test_shared_stall_upgrade_checks_and_debits_common_balances(self):
        stable = self.buildings.get_state(self.character_id, "stable", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET copper=0,silver=25,gold=0 WHERE id=%s",
                (self.character_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=5000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        self._deposit_warehouse(self.character_id, 60, 300)
        before = self.buildings.get_state(self.character_id, "stable", 10001)
        self.assertTrue(before["stall_upgrades"]["wooden_stalls"]["can_purchase"])
        first = self.buildings.purchase_stall_upgrade(self.character_id, "wooden_stalls", 10002)
        self.assertEqual(first["warehouse_storage"]["wood"], 0)
        self.assertEqual(first["treasury_silver_available"], 0)
        self.assertEqual(first["silver_available"], 25)
        self.assertEqual(first["stall_capacity"], stable["stall_capacity"])
        self.assertTrue(first["stall_upgrades"]["wooden_stalls"]["purchased"])
        self.assertTrue(first["stall_upgrades"]["wooden_stalls"]["in_progress"])
        self.assertEqual(first["stall_upgrades"]["wooden_stalls"]["seconds_left"], 10800)
        self.assertFalse(first["stall_slots"][4]["unlocked"])
        with self.assertRaisesRegex(ValueError, "уже куплено"):
            self.buildings.purchase_stall_upgrade(self.character_id, "wooden_stalls", 10003)
        teammate_user = self.database.register("stallmate", "password")
        teammate_id = self.database.create_character(teammate_user["id"], "Stallmate")["id"]
        before_finish = self.buildings.get_state(teammate_id, "stable", 20801)
        self.assertEqual(before_finish["stall_capacity"], stable["stall_capacity"])
        self.assertEqual(before_finish["stall_upgrades"]["wooden_stalls"]["seconds_left"], 1)
        shared = self.buildings.get_state(teammate_id, "stable", 20802)
        self.assertEqual(shared["stall_capacity"], stable["stall_capacity"] + 1)
        self.assertTrue(shared["stall_upgrades"]["wooden_stalls"]["completed"])
        self.assertTrue(shared["stall_slots"][4]["unlocked"])

    def test_farm_upgrade_chain_adds_first_field_worker_plough_and_level_two(self):
        farm = self.buildings.get_state(self.character_id, "farm", 10000)
        self.assertEqual(farm["max_workers"], 2)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=10000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )

        ration = self.buildings.purchase_farm_upgrade(self.character_id, "ration", now=10001)
        self.assertEqual(ration["farm_upgrades"]["active_upgrade_id"], "ration")
        self.assertEqual(ration["farm_upgrades"]["seconds_left"], 1800)
        self.assertEqual(len(ration["worker_slots"]), 2)
        ration_done = self.buildings.get_state(self.character_id, "farm", 11801)
        self.assertTrue(ration_done["farm_upgrades"]["completed"]["ration"])
        self.assertEqual(ration_done["max_workers"], 3)
        ration_slot = next(slot for slot in ration_done["worker_slots"] if slot["slot_index"] == 1000)
        self.assertEqual(ration_slot["resources"], ["wheat"])
        from server.city_population import CityPopulation

        governor = CityPopulation(self.database).get_state(self.character_id, now=11801)
        farm_worksite = next(site for site in governor["worksites"] if site["building"] == "farm")
        self.assertEqual(farm_worksite["capacity"], 3)
        self.buildings.hire_worker(self.character_id, "farm", 1000, "citizen:1", now=11802)
        assigned = self.buildings.get_state(self.character_id, "farm", 11802)
        self.assertEqual(assigned["workers"], 1)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                "AND building='warehouse' AND resource='wood'",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=2000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        plough = self.buildings.purchase_farm_upgrade(self.character_id, "wooden_plough", now=11803)
        self.assertEqual(plough["farm_upgrades"]["seconds_left"], 3600)
        plough_done = self.buildings.get_state(self.character_id, "farm", 15403)
        self.assertTrue(plough_done["farm_upgrades"]["wooden_plough"])
        self.assertEqual(plough_done["worker_slots"][0]["timer_sec_by_resource"]["wheat"], 133)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=200 WHERE world_id=%s AND faction='light' "
                "AND building='warehouse' AND resource='wood'",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=5000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        level_two = self.buildings.purchase_farm_upgrade(self.character_id, "farm_level_2", now=15404)
        self.assertEqual(level_two["farm_upgrades"]["seconds_left"], 7200)
        completed = self.buildings.get_state(self.character_id, "farm", 22604)
        self.assertEqual(completed["level"], 2)
        self.assertTrue(completed["farm_upgrades"]["completed"]["farm_level_2"])
        self.assertEqual(completed["storage"]["limit"], 800)
        self.assertEqual(completed["max_workers"], 5)
        self.assertEqual(
            [slot["slot_index"] for slot in completed["worker_slots"]],
            [0, 1, 2, 3, 1000],
        )
        self.assertEqual(completed["worker_slots"][2]["resources"], ["wheat"])
        governor = CityPopulation(self.database).get_state(self.character_id, now=22604)
        farm_worksite = next(site for site in governor["worksites"] if site["building"] == "farm")
        self.assertEqual(farm_worksite["capacity"], 5)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=3000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        ration_level_two = self.buildings.purchase_farm_upgrade(
            self.character_id, "ration_level_2", now=22605,
        )
        self.assertEqual(ration_level_two["farm_upgrades"]["seconds_left"], 1800)
        ration_level_two_done = self.buildings.get_state(self.character_id, "farm", 24405)
        self.assertTrue(ration_level_two_done["farm_upgrades"]["completed"]["ration_level_2"])
        second_field_slot = next(
            slot for slot in ration_level_two_done["worker_slots"] if slot["slot_index"] == 1001
        )
        self.assertEqual(second_field_slot["resources"], ["wheat"])
        self.assertEqual(ration_level_two_done["max_workers"], 6)
        governor = CityPopulation(self.database).get_state(self.character_id, now=24405)
        farm_worksite = next(site for site in governor["worksites"] if site["building"] == "farm")
        self.assertEqual(farm_worksite["capacity"], 6)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                "AND building='warehouse' AND resource='wood'",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=2000 "
                "WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        handle = self.buildings.purchase_farm_upgrade(
            self.character_id, "wooden_handle", now=24406,
        )
        self.assertEqual(handle["farm_upgrades"]["seconds_left"], 3600)
        handle_done = self.buildings.get_state(self.character_id, "farm", 28006)
        self.assertTrue(handle_done["farm_upgrades"]["completed"]["wooden_handle"])
        self.assertEqual(handle_done["worker_slots"][0]["timer_sec_by_resource"]["wheat"], 122)
        governor = CityPopulation(self.database).get_state(self.character_id, now=28006)
        self.assertAlmostEqual(governor["city_resource_income_per_hour"]["wheat"], 3600 / 122)

    def test_stall_purchase_never_debits_backpack_directly(self):
        items = ItemsDatabase(self.database)
        items.add_to_inventory(self.character_id, 60, 300)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=5000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        with self.assertRaisesRegex(ValueError, "общем складе"):
            self.buildings.purchase_stall_upgrade(self.character_id, "wooden_stalls", 10000)
        self.assertEqual(sum(row["quantity"] for row in items.get_inventory(self.character_id)
                             if row["item_id"] == 60), 300)
        self._deposit_warehouse(self.character_id, 60, 300, 10001)
        purchased = self.buildings.purchase_stall_upgrade(
            self.character_id, "wooden_stalls", 10002
        )
        self.assertTrue(purchased["stall_upgrades"]["wooden_stalls"]["purchased"])
        self.assertEqual(purchased["warehouse_storage"]["wood"], 0)
        self.assertEqual(purchased["treasury_silver_available"], 0)
        self.assertEqual(sum(row["quantity"] for row in items.get_inventory(self.character_id)
                             if row["item_id"] == 60), 0)

    def test_lumber_camp_upgrade_chain_expands_first_plot_and_unlocks_level_two(self):
        now = 10000
        initial = self.buildings.get_state(self.character_id, "lumber_camp", now)
        self.assertEqual(initial["storage"]["limit"], 500)
        self.assertEqual(initial["max_workers"], 2)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_population_state SET treasury_copper=0
                   WHERE world_id=%s AND faction='light'""",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE characters SET copper=0, silver=500, gold=0 WHERE id=%s",
                (self.character_id,),
            )
            connection.execute(
                """UPDATE building_resources SET storage=300
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        with self.assertRaisesRegex(ValueError, "казне недостаточно средств"):
            self.buildings.purchase_lumber_camp_upgrade(
                self.character_id, "logging_expansion", now + 0.25,
            )
        with self.database.connection() as connection:
            treasury = connection.execute(
                "SELECT treasury_copper FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["treasury_copper"]
            wallet_silver = connection.execute(
                "SELECT silver FROM characters WHERE id=%s", (self.character_id,),
            ).fetchone()["silver"]
            self.assertEqual(treasury, 0)
            self.assertEqual(wallet_silver, 500)
            connection.execute(
                """UPDATE city_population_state SET treasury_copper=50000
                   WHERE world_id=%s AND faction='light'""",
                (self.database.world_id,),
            )

        initial = self.buildings.get_state(self.character_id, "lumber_camp", now + 0.5)
        self.assertEqual(initial["treasury_silver_available"], 500)

        expansion = self.buildings.purchase_lumber_camp_upgrade(
            self.character_id, "logging_expansion", now + 1,
        )
        self.assertEqual(expansion["lumber_camp_upgrades"]["seconds_left"], 2400)
        self.assertEqual(expansion["treasury_silver_available"], 450)
        expansion_done = self.buildings.get_state(
            self.character_id, "lumber_camp", now + 2402,
        )
        self.assertTrue(expansion_done["lumber_camp_upgrades"]["completed"]["logging_expansion"])
        self.assertEqual(expansion_done["max_workers"], 3)
        bonus_slot = next(slot for slot in expansion_done["worker_slots"]
                          if slot["slot_index"] == 1000)
        self.assertEqual(bonus_slot["resources"], ["wood"])

        with self.assertRaisesRegex(ValueError, "усиленную рукоять"):
            self.buildings.purchase_lumber_camp_upgrade(
                self.character_id, "lumber_camp_level_2", now + 2403,
            )

        handle = self.buildings.purchase_lumber_camp_upgrade(
            self.character_id, "strong_handle", now + 2403,
        )
        self.assertEqual(handle["treasury_silver_available"], 380)
        self.assertEqual(handle["warehouse_storage"]["wood"], 300)
        handle_done = self.buildings.get_state(
            self.character_id, "lumber_camp", now + 6004,
        )
        self.assertTrue(handle_done["lumber_camp_upgrades"]["completed"]["strong_handle"])
        self.assertEqual(handle_done["worker_slots"][0]["timer_sec_by_resource"]["wood"], 221)

        level_two = self.buildings.purchase_lumber_camp_upgrade(
            self.character_id, "lumber_camp_level_2", now + 6005,
        )
        self.assertEqual(level_two["lumber_camp_upgrades"]["seconds_left"], 8400)
        self.assertEqual(level_two["treasury_silver_available"], 330)
        self.assertEqual(level_two["warehouse_storage"]["wood"], 0)
        completed = self.buildings.get_state(
            self.character_id, "lumber_camp", now + 14405,
        )
        self.assertEqual(completed["level"], 2)
        self.assertEqual(completed["storage"]["limit"], 800)
        self.assertEqual(completed["max_workers"], 4)
        self.assertEqual(
            [slot["slot_index"] for slot in completed["worker_slots"]],
            [0, 1, 2, 1000],
        )

    def test_building_upgrade_spends_shared_warehouse_not_backpack(self):
        items = ItemsDatabase(self.database)
        requirements = upgrade_requirements(1, "stable")["materials"]
        first_item_id, first_required = next(iter(requirements.items()))
        items.add_to_inventory(self.character_id, first_item_id, first_required)

        with self.assertRaisesRegex(ValueError, "общем складе"):
            self.buildings.start_upgrade(self.character_id, "stable", 10000)
        self.assertEqual(sum(item["quantity"] for item in items.get_inventory(self.character_id)
                             if item["item_id"] == first_item_id), first_required)

        for item_id, required in requirements.items():
            resource = STORAGE_RESOURCES_BY_ITEM_ID[item_id]
            self._deposit_warehouse(self.character_id, item_id, required, 10001)
        state = self.buildings.start_upgrade(self.character_id, "stable", 10002)
        self.assertTrue(state["upgrade"]["in_progress"])
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10003)
        for item_id in requirements:
            resource = STORAGE_RESOURCES_BY_ITEM_ID[item_id]
            self.assertEqual(warehouse["storage"].get(resource, 0), 0)
            self.assertEqual(sum(item["quantity"] for item in items.get_inventory(self.character_id)
                                 if item["item_id"] == item_id), first_required if item_id == first_item_id else 0)

    def test_cart_purchase_debits_shared_warehouse_and_treasury_atomically(self):
        items = ItemsDatabase(self.database)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET copper = 0, silver = 50, gold = 0 WHERE id = %s",
                (self.character_id,),
            )
        items.add_to_inventory(self.character_id, 60, 100)
        deposited = self.buildings.deposit_to_storage(
            self.character_id, "warehouse", "wood", 100, 10000
        )
        self.assertEqual(deposited["storage"]["wood"], 100)
        self.assertEqual(sum(item["quantity"] for item in items.get_inventory(self.character_id)
                             if item["item_id"] == 60), 0)

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=1000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        purchased = self.buildings.purchase_cart(self.character_id, now=10004)
        grade = purchased["cart_progress"]["grades"]["1"]
        self.assertFalse(grade["body_owned"])
        self.assertEqual(grade["body_finish_at"], 12404)
        self.assertEqual(purchased["warehouse_storage"]["wood"], 0)
        self.assertEqual(purchased["treasury_silver_available"], 0)
        self.assertEqual(purchased["silver_available"], 50)
        self.assertEqual(purchased["available_carts"], [])

        for order_time in range(10005, 10009):
            with self.database.connection() as connection:
                connection.execute(
                    "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                    "AND building='warehouse' AND resource='wood'",
                    (self.database.world_id,),
                )
                connection.execute(
                    "UPDATE city_population_state SET treasury_copper=1000 "
                    "WHERE world_id=%s AND faction='light'",
                    (self.database.world_id,),
                )
            self.buildings.purchase_cart(self.character_id, now=order_time)

        queue_full = self.buildings.get_state(self.character_id, "stable", 10008)
        self.assertEqual(
            len(queue_full["cart_progress"]["grades"]["1"]["production_orders"]), 5
        )
        with self.assertRaisesRegex(ValueError, r"заполнена \(5/5\)"):
            self.buildings.purchase_cart(self.character_id, now=10009)
        persisted = ProductionBuildings(self.database).get_state(self.character_id, "stable", 12403)
        self.assertFalse(persisted["cart_progress"]["grades"]["1"]["body_owned"])
        self.assertEqual(persisted["available_carts"], [])
        persisted = ProductionBuildings(self.database).get_state(self.character_id, "stable", 12404)
        self.assertTrue(persisted["cart_progress"]["grades"]["1"]["body_owned"])
        self.assertEqual(len(persisted["available_carts"]), 1)
        self.assertEqual(persisted["cart_progress"]["grades"]["1"]["body_count"], 1)
        completed_all = self.buildings.get_state(self.character_id, "stable", 12408)
        self.assertEqual(completed_all["cart_progress"]["grades"]["1"]["body_count"], 5)
        self.assertEqual(
            [cart["id"] for cart in completed_all["available_carts"]],
            ["cart_grade_1", "cart_grade_1~2", "cart_grade_1~3", "cart_grade_1~4", "cart_grade_1~5"],
        )

    def test_cart_maintenance_charges_active_time_and_repairs_with_wood(self):
        now = 10000
        self.buildings.get_state(self.character_id, "stable", now)
        self.buildings.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE stable_cart_progress SET body_owned=TRUE, body_count=1
                   WHERE world_id=%s AND faction='light' AND building='stable' AND grade=1""",
                (self.database.world_id,),
            )
            connection.execute(
                """UPDATE building_resources SET storage=3 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
            stable_key = (self.database.world_id, "light", "stable")
            self.buildings._advance_cart_maintenance(connection, stable_key, now, [])
            self.buildings._advance_cart_maintenance(connection, stable_key, now + 3600, [])
            idle_stock = connection.execute(
                """SELECT storage FROM building_resources WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertEqual(idle_stock, 3)

        active_convoy = [{
            "cart_id": "cart_grade_1", "status": "outbound", "phase": "outbound",
            "started_at": now + 3600, "arrival_at": now + 7200,
        }]
        with self.database.connection() as connection:
            self.buildings._advance_cart_maintenance(
                connection, stable_key, now + 7200, active_convoy,
            )
            stock_after_paid_hour = connection.execute(
                """SELECT storage FROM building_resources WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertEqual(stock_after_paid_hour, 1)

        active_convoy[0].update(started_at=now + 7200, arrival_at=now + 10800)
        with self.database.connection() as connection:
            self.buildings._advance_cart_maintenance(
                connection, stable_key, now + 10800, active_convoy,
            )
            row = connection.execute(
                """SELECT cart_wear_json FROM stable_cart_progress
                   WHERE world_id=%s AND faction='light' AND building='stable' AND grade=1""",
                (self.database.world_id,),
            ).fetchone()
            self.assertEqual(row["cart_wear_json"]["cart_grade_1"]["durability"], 99.0)
            connection.execute(
                """UPDATE building_resources SET storage=1 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        repaired = self.buildings.repair_cart(
            self.character_id, "cart_grade_1", now=now + 10801,
        )
        cart = repaired["available_carts"][0]
        self.assertEqual(cart["durability"], 100)
        self.assertFalse(cart["broken"])
        self.assertEqual(repaired["warehouse_storage"]["wood"], 0)

        with self.database.connection() as connection:
            connection.execute(
                """UPDATE stable_cart_progress SET cart_wear_json=%s::jsonb
                   WHERE world_id=%s AND faction='light' AND building='stable' AND grade=1""",
                (json.dumps({"cart_grade_1": {"durability": 0, "updated_at": now + 10802}}),
                 self.database.world_id),
            )
            connection.execute(
                """UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
        broken = self.buildings.get_state(self.character_id, "stable", now + 10802)
        self.assertEqual(broken["available_carts"][0]["status"], "Сломана")
        self.assertFalse(broken["available_carts"][0]["dispatch_available"])
        self.assertEqual(broken["available_carts"][0]["repair_wood_cost"], 100)
        repaired = self.buildings.repair_cart(
            self.character_id, "cart_grade_1", now=now + 10803,
        )
        self.assertEqual(repaired["available_carts"][0]["durability"], 100)
        self.assertEqual(repaired["warehouse_storage"]["wood"], 0)

    def test_cart_purchase_rejects_shortage_without_partial_debit(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=500 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        with self.assertRaisesRegex(ValueError, "Недостаточно ресурсов на общем складе"):
            self.buildings.purchase_cart(self.character_id, now=10004)
        state = self.buildings.get_state(self.character_id, "stable", 10004)
        self.assertFalse(state["cart_progress"]["grades"]["1"]["body_owned"])
        self.assertEqual(state["treasury_silver_available"], 5)

    def test_cart_purchase_does_not_debit_backpack_or_wallet(self):
        items = ItemsDatabase(self.database)
        items.add_to_inventory(self.character_id, 60, 100)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=2000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )

        with self.assertRaisesRegex(ValueError, "Отдельные взносы за повозку отключены"):
            self.buildings.contribute_cart(self.character_id, "wood", 100, 10001, source="backpack")
        self.assertEqual(sum(item["quantity"] for item in items.get_inventory(self.character_id)
                             if item["item_id"] == 60), 100)
        with self.database.connection() as connection:
            treasury = connection.execute(
                "SELECT treasury_copper FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["treasury_copper"]
        self.assertEqual(treasury, 2000)


class FakeStorageClient:
    get_city_structures = staticmethod(city_structures)

    def get_inventory(self, _character_id):
        return {"inventory": [
            {"item_id": 60, "quantity": 12}, {"item_id": 73, "quantity": 7},
            {"item_id": 61, "quantity": 4}, {"item_id": 64, "quantity": 9},
            {"item_id": 74, "quantity": 2}, {"item_id": 66, "quantity": 6},
        ]}

    def get_map_terrain(self):
        return {"roads": {"routes": [
            {"building_id": "wheat_farm", "name": "Крестьянское поселение", "distance_tiles": 50.11,
             "distance_pixels": 1604, "resources": [{"id": "wheat", "label": "Пшеница"}]},
            {"building_id": "lumber_camp", "name": "Лагерь лесорубов", "distance_tiles": 94.61,
             "distance_pixels": 3028, "resources": [{"id": "wood", "label": "Древесина"}]},
            {"building_id": "mountain_rift", "name": "Горный разлом", "distance_tiles": 86.88,
             "distance_pixels": 2780, "resources": [{"id": "iron", "label": "Железная руда"}]},
            {"building_id": "barnyard", "name": "Скотный двор", "distance_tiles": 60.53,
             "distance_pixels": 1937, "resources": [{"id": "leather", "label": "Кожа"}]},
            {"building_id": "black_pit", "name": "Чёрная копь", "distance_tiles": 81.41,
             "distance_pixels": 2605, "resources": [{"id": "coal", "label": "Уголь"}]},
        ]}}
    def __init__(self):
        self.calls = []
        self.last_payload = None
        self.cart_progress = deepcopy(DEFAULT_CART_PROGRESS)
        self.warehouse_storage = {"wood": 12, "board": 4, "flax": 9}
        self.treasury_silver_available = 100
        self.action_error = None
        self.dispatch_payload = None

    def get_building(self, building, _character_id):
        if building == "stable":
            return {
                "building": "stable", "level": 1, "stall_capacity": 4, "max_workers": 0,
                "server_time": 0,
                "occupied_stalls": 0, "feed_consumption_kg_per_hour": 0,
                "feed_resource_label": "Пшеница",
                "stall_slots": [
                    {"slot_index": slot, "unlocked": slot < 4,
                     "unlock_level": 1 if slot < 4 else 2, "horse": None}
                    for slot in range(22)
                ],
                "stall_capacity_bonus": 0,
                "silver_available": 100,
                "treasury_silver_available": self.treasury_silver_available,
                "backpack_resource_amounts": {"wood": 12},
                "warehouse_storage": dict(self.warehouse_storage),
                "cart_progress": deepcopy(self.cart_progress),
                "available_carts": ([{
                    "id": "cart_grade_1", "grade": 1, "name": "Лёгкая повозка",
                    "status": "Свободна", "can_travel": False,
                    "dispatch_available": False, "horse_slots": 1, "resource_slots": 1,
                    "capacity_kg": 300, "seconds_per_tile": 23.9473,
                    "status_message": "Отправка транспортных рейсов ещё не подключена.",
                }] if self.cart_progress["grades"]["1"].get("body_owned") else []),
                "horse_price_next_silver": 50,
                "stall_upgrades": {
                                        "wooden_stalls": {"wood_cost": 300, "silver_cost": 50,
                                                                            "purchased": False, "ready": True, "can_purchase": True,
                                                                            "wood_remaining": 300, "silver_remaining": 50,
                                      "wood_deposited": 0, "silver_deposited": 0,
                                      "wood_in_warehouse": 300, "wood_in_backpack": 12,
                                      "silver_available": 50, "treasury_silver_available": self.treasury_silver_available},
                    "hayloft": {"wood_cost": 300, "silver_cost": 50,
                                                                "purchased": False, "ready": True, "can_purchase": True,
                                                                "wood_remaining": 300, "silver_remaining": 50,
                                "wood_deposited": 0, "silver_deposited": 0,
                                                                "wood_in_warehouse": 300, "wood_in_backpack": 12,
                                                                "silver_available": 50, "treasury_silver_available": self.treasury_silver_available},
                },
                "storage": {"limit": 0}, "storage_total": 0, "worker_slots": [],
                "upgrade": {"next_level": 2, "time_seconds": 7200, "ready": False,
                            "in_progress": False, "finish_at": None, "seconds_left": None,
                            "materials": [{"item_id": 60, "name": "Древесина", "required": 5,
                                           "deposited": 0, "in_warehouse": 5}]},
            }
        goods = BARN_GOODS if building == "barn" else WAREHOUSE_GOODS
        limit = 1000
        state = {
            "building": building, "level": 1, "max_workers": 0, "cycle_start_time": 0, "cycle_duration_sec": 7200,
            "storage": {**{good: 0 for good in goods}, "limit": limit}, "buffer": {}, "forecast": {},
            "worker_slots": [],
            "upgrade": {
                "next_level": 2, "time_seconds": 7200, "ready": False, "in_progress": False,
                "finish_at": None, "seconds_left": None,
                "materials": [{"item_id": 60, "name": "Древесина", "icon": None, "required": 5,
                               "deposited": 0, "in_warehouse": 5}],
            },
        }
        if building == "warehouse":
            state["storage"].update({"wood": 12, "iron_ingot": 7, "board": 4, "flax": 9,
                                     "steel": 2, "leather": 6})
        route_stock = {
            "farm": {"wheat": 1250}, "lumber_camp": {"wood": 271},
            "mountain_rift": {"iron": 84}, "barnyard": {"leather": 39},
            "black_pit": {"coal": 16},
        }
        state["storage"].update(route_stock.get(building, {}))
        resource_item_ids = {"wood": 60, "board": 61, "flax": 64, "leather": 66,
                             "iron_ingot": 73, "steel": 74}
        backpack = {60: 12, 73: 7, 61: 4, 64: 9, 74: 2, 66: 6}
        state["storage_depositable"] = {
            resource: {"item_id": item_id, "in_backpack": backpack.get(item_id, 0),
                       "max_deposit": min(
                           backpack.get(item_id, 0),
                           max(0, limit - state["storage"].get(resource, 0)),
                       )}
            for resource, item_id in resource_item_ids.items() if resource in goods
        }
        item_weights = {60: 4.0, 61: 6.0, 62: 2.0, 63: 2.0, 64: 3.0, 65: 4.0,
                        66: 3.0, 67: 3.0, 68: 3.0, 69: 3.0, 73: 6.0, 74: 7.0}
        item_id_by_resource = {resource: item_id for item_id, resource in
                               ((item_id, resource) for resource, item_id in {
                                   "wood": 60, "board": 61, "berries": 62, "wheat": 63,
                                   "flax": 64, "cotton": 65, "leather": 66, "meat": 67,
                                   "coal": 68, "stone": 69, "iron_ingot": 73, "steel": 74,
                               }.items())}
        state["storage_withdrawable"] = {
            resource: {"available": amount, "max_withdraw": min(amount, 12),
                       "item_weight_kg": item_weights[item_id_by_resource[resource]],
                       "carried_weight_kg": 18.0, "carry_capacity_kg": 42.0}
            for resource, amount in state["storage"].items()
            if resource != "limit" and resource in item_id_by_resource
        }
        return state

    def building_action(self, building, _character_id, action, payload=None):
        self.calls.append((building, action))
        self.last_payload = payload or {}
        if self.action_error is not None:
            raise self.action_error
        if building == "stable" and action == "cart/purchase":
            grade = self.cart_progress["grades"]["1"]
            wood_due = max(0, 100 - grade.get("wood_deposited", 0))
            silver_due = max(0, 10 - grade.get("silver_deposited", 0))
            if self.warehouse_storage["wood"] >= wood_due and self.treasury_silver_available >= silver_due:
                self.warehouse_storage["wood"] -= wood_due
                self.treasury_silver_available -= silver_due
                grade["wood_deposited"] = 100
                grade["silver_deposited"] = 10
                grade["body_finish_at"] = 2400
        return self.get_building(building, _character_id)

    def dispatch_transport(self, _character_id, payload):
        self.dispatch_payload = payload
        return {"building": self.get_building("stable", _character_id), "convoy": {"id": 1}}


class CityStorageWindowTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from scenes.city_scene import CityScene

        self.client = FakeStorageClient()
        self.scene = CityScene(SimpleNamespace(character={"id": 1, "name": "Тест"}, client=self.client))

    def tearDown(self):
        pygame.quit()

    def test_storage_meter_uses_requested_fill_bands(self):
        from ui.storage_meter import storage_fill_color

        self.assertEqual(storage_fill_color(200, 1000), (218, 69, 65))
        self.assertEqual(storage_fill_color(210, 1000), (232, 191, 67))
        self.assertEqual(storage_fill_color(400, 1000), (232, 191, 67))
        self.assertEqual(storage_fill_color(410, 1000), (75, 190, 100))
        self.assertEqual(storage_fill_color(700, 1000), (75, 190, 100))
        self.assertEqual(storage_fill_color(710, 1000), (116, 218, 245))
        self.assertEqual(storage_fill_color(1000, 1000), (116, 218, 245))

    def test_storage_meter_marks_fill_stage_boundaries(self):
        from ui.storage_meter import draw_storage_meter

        surface = pygame.Surface((60, 10))
        rect = pygame.Rect(0, 0, 60, 10)
        draw_storage_meter(surface, rect, 0, 1000)
        inner = rect.inflate(-2, -2)
        for boundary in (0.20, 0.40, 0.70):
            marker_x = inner.x + round(inner.width * boundary)
            self.assertEqual(surface.get_at((marker_x, inner.centery))[:3], (150, 163, 164))

    def test_charging_storage_meter_flashes_green_and_white(self):
        from ui.storage_meter import draw_storage_meter

        surface = pygame.Surface((60, 10))
        rect = pygame.Rect(0, 0, 60, 10)
        with patch("ui.storage_meter.pygame.time.get_ticks", return_value=0):
            draw_storage_meter(surface, rect, 800, 1000, charging=True)
        self.assertEqual(surface.get_at((20, 5))[:3], (48, 225, 105))
        with patch("ui.storage_meter.pygame.time.get_ticks", return_value=350):
            draw_storage_meter(surface, rect, 800, 1000, charging=True)
        self.assertEqual(surface.get_at((20, 5))[:3], (246, 255, 250))

    def test_cart_purchase_debits_shared_balances_without_contribution_dialog(self):
        window = self.scene.stable_window
        self.client.warehouse_storage["wood"] = 100
        self.client.treasury_silver_available = 10
        window.state = self.client.get_building("stable", 1)
        window._sync_cart_progress()
        window.tab = "carts"
        window._draw_carts(self.screen)
        self.assertEqual(window.cart_contribution_areas, {})
        button = window.cart_purchase_buttons[1]

        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=button.center,
        ))

        self.assertIn(("stable", "cart/purchase"), self.client.calls)
        self.assertEqual(self.client.warehouse_storage["wood"], 0)
        self.assertEqual(self.client.treasury_silver_available, 0)
        self.assertFalse(self.client.cart_progress["grades"]["1"]["body_owned"])
        self.assertEqual(self.client.cart_progress["grades"]["1"]["body_finish_at"], 2400)
        window._draw_carts(self.screen)
        self.assertNotIn(1, window.cart_purchase_buttons)

    def test_cart_shortage_does_not_offer_backpack_contribution(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.tab = "carts"
        window._draw_carts(self.screen)

        self.assertEqual(window.cart_contribution_areas, {})
        self.assertNotIn(1, window.cart_purchase_buttons)
        self.assertIsNone(window.source_picker)
        self.assertFalse(any(action == "cart/purchase" for _, action in self.client.calls))

    def test_transport_picker_hides_cart_already_on_route(self):
        window = self.scene.stable_window
        self.client.cart_progress["grades"]["1"]["body_owned"] = True
        window.state = self.client.get_building("stable", 1)
        window.state["transport_convoys"] = [{"cart_id": "cart_grade_1"}]
        window.transport_popup = ("cart", None)

        self.assertEqual(window._transport_popup_items(), [])
        window._select_transport_option(("cart", None, "cart_grade_1"))

        self.assertIsNone(window.transport_draft["cart_id"])
        self.assertEqual(window.message, "Повозка уже занята рейсом.")
        self.assertFalse(window._transport_can_start())

    def test_transport_resource_picker_hides_city_locked_resources(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["city_upgrade"] = {"city_level": 1}
        window.routes = [{
            "building_id": "lumber_camp", "name": "Лесопилка",
            "resources": [
                {"id": "wood", "label": "Древесина"},
                {"id": "berries", "label": "Ягоды"},
                {"id": "flax", "label": "Лён"},
            ],
        }]
        window.destination_state = {
            "storage": {"wood": 20, "berries": 10, "flax": 5, "limit": 1000},
        }
        window.transport_draft["destination_id"] = "lumber_camp"
        window.transport_popup = ("resource", 0)

        self.assertEqual(window._transport_popup_items(), [("wood", "Древесина")])

        window.state["city_upgrade"]["city_level"] = 2
        self.assertEqual(
            window._transport_popup_items(),
            [("wood", "Древесина"), ("berries", "Ягоды"), ("flax", "Лён")],
        )

    def test_transport_farm_destination_loads_production_storage_for_resource_picker(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["city_upgrade"] = {"city_level": 1}
        window.routes = [{
            "building_id": "wheat_farm", "name": "Крестьянское поселение",
            "resources": [{"id": "wheat", "label": "Пшеница"}],
        }]
        window.transport_draft["cart_id"] = "cart_grade_1"
        with patch.object(self.client, "get_building", return_value={
            "storage": {"wheat": 0, "limit": 500},
        }) as get_building:
            window._select_transport_option(("destination", None, "wheat_farm"))

        get_building.assert_called_once_with("farm", 1)
        window.transport_popup = ("resource", 0)
        self.assertEqual(window._transport_popup_items(), [("wheat", "Пшеница")])

    def test_barn_and_warehouse_windows(self):
        for building, opener, window in (
            ("barn", self.scene._open_barn, self.scene.barn_window),
            ("warehouse", self.scene._open_warehouse, self.scene.warehouse_window),
        ):
            with self.subTest(building=building):
                opener()
                self.scene.draw(self.screen)
                self.assertEqual(window.tab, "storage")
                window.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1, pos=window.upgrade_tab.center,
                ))
                self.assertEqual(window.tab, "upgrade")
                window.deposit_buttons = {}
                window.state["upgrade"]["ready"] = True
                window.draw(self.screen)
                self.assertEqual(window.deposit_buttons, {})
                window.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1, pos=window.upgrade_button.center,
                ))
                self.assertIn((building, "upgrade/start"), self.client.calls)
                window.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
                self.assertFalse(window.is_open)

    def test_warehouse_storage_deposit_uses_available_backpack_resource(self):
        window = self.scene.warehouse_window
        window.open()
        window._draw_storage_tab(self.screen, window.rect.top + 136)
        self.assertIn("wood", window.storage_deposit_buttons)
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=window.storage_deposit_buttons["wood"].center,
        ))
        self.assertTrue(window.contribution_dialog.is_open)
        self.assertEqual(window.contribution_dialog.maximum, 12)

        with patch.object(window.contribution_dialog, "handle_event",
                          return_value=(("storage", "wood"), 5)):
            window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))
        self.assertIn(("warehouse", "storage/deposit"), self.client.calls)

    def test_city_storage_window_can_open_withdraw_dialog(self):
        window = self.scene.warehouse_window
        window.open()
        window._draw_storage_tab(self.screen, window.rect.top + 136)
        self.assertIn("wood", window.storage_withdraw_buttons)

        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=window.storage_withdraw_buttons["wood"].center,
        ))

        self.assertTrue(window.contribution_dialog.is_open)
        self.assertEqual(window.contribution_dialog.mode, "withdraw")
        self.assertEqual(window.contribution_dialog.maximum, 12)

        with patch.object(window.contribution_dialog, "handle_event",
                          return_value=(("storage_withdraw", "wood"), 4)):
            window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))
        self.assertIn(("warehouse", "storage/withdraw"), self.client.calls)

    def test_withdraw_slider_caps_by_weight_and_updates_weight_readout(self):
        dialog = self.scene.warehouse_window.contribution_dialog
        dialog.open(
            ("storage_withdraw", "wheat"), "Пшеница", 500, 12,
            mode="withdraw",
            weight_state={"carried_weight_kg": 18, "carry_capacity_kg": 42},
            item_weight_kg=2,
        )
        rendered = []
        rendered_colors = {}
        original_font = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                if len(args) > 1:
                    rendered_colors[text] = args[1]
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        self.scene.small_font = Recorder()
        try:
            dialog.draw(self.screen)
            dialog.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=(dialog.track_rect.right, dialog.track_rect.centery),
            ))
            dialog.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONUP, button=1, pos=dialog.track_rect.midright,
            ))
            dialog.draw(self.screen)
        finally:
            self.scene.small_font = original_font

        self.assertEqual(dialog.quantity, 12)
        self.assertIn("Забрать: 12 / 500", rendered)
        self.assertIn("Вес после забора: 42 / 42 кг", rendered)
        self.assertEqual(rendered_colors["Вес после забора: 42 / 42 кг"], (235, 95, 85))

    def test_storage_tab_shows_only_goods_and_capacity(self):
        window = self.scene.barn_window
        self.scene._open_barn()
        window.state["storage"] = {"wheat": 0, "limit": 1000}
        rendered = []
        original = self.scene.font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.font = original
        for text in ("Уровень 1", "Товары:", "Пшеница", "0 / 1000"):
            self.assertIn(text, rendered)
        self.assertNotIn("Ягоды", rendered)
        self.assertNotIn("Мясо", rendered)
        self.assertEqual(window.production_desc(2), "Вместимость каждого товара: 1500 продукции")

    def test_storage_meter_replaces_backpack_label_and_matches_row_height(self):
        from ui.city_storage_window import draw_storage_meter as _draw_meter
        from unittest.mock import patch

        window = self.scene.barn_window
        window.state = self.client.get_building("barn", 1)
        window.state["storage"] = {"wheat": 900, "limit": 1000}
        rendered = []
        original = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.small_font = Recorder()
        try:
            with patch("ui.city_storage_window.draw_storage_meter", wraps=_draw_meter) as meter:
                window._draw_storage_tab(self.screen, 100)
        finally:
            self.scene.small_font = original

        meter_rect = meter.call_args.args[1]
        self.assertEqual(meter_rect.height, 18)
        self.assertGreater(meter_rect.width, 200)
        self.assertFalse(any(text.startswith("Рюкзак:") for text in rendered))

    def test_stable_is_server_placed_rendered_and_reachable(self):
        stable = next(obj for obj in self.scene.objects if obj["id"] == "stable_building")
        self.assertEqual((stable["tile_x"], stable["tile_y"], stable["tile_w"], stable["tile_h"]), (77, 6, 17, 6))
        self.scene.player_x, self.scene.player_y = stable["approach_pos"]
        self.assertTrue(self.scene._is_within_one_tile(stable))
        self.assertFalse(self.scene._check_collision(*stable["approach_pos"]))
        self.scene.draw(self.screen)

    def test_resident_houses_block_movement_as_population_grows(self):
        first_house = self.scene._citizen_house_solid_rects()[0]
        self.assertTrue(self.scene._check_collision(*first_house.center))
        self.assertFalse(self.scene._check_collision(first_house.left - 16, first_house.centery))
        first_lot = self.scene.citizen_house_lots[0]
        roof_center = (
            (first_lot[0] + first_lot[2] / 2) * self.scene.tile_size,
            first_lot[1] * self.scene.tile_size - self.scene.tile_size // 4,
        )
        self.assertTrue(self.scene._check_collision(*roof_center))

        fifth_house = self.scene.citizen_house_lots[4]
        fifth_house_center = (
            (fifth_house[0] + fifth_house[2] / 2) * self.scene.tile_size,
            (fifth_house[1] + fifth_house[3] / 2) * self.scene.tile_size,
        )
        self.assertFalse(self.scene._check_collision(*fifth_house_center))
        self.scene.city_population_count = 5
        self.assertTrue(self.scene._check_collision(*fifth_house_center))

    def test_resident_house_lots_avoid_buildings_and_roads_across_city(self):
        lots = self.scene.citizen_house_lots
        centers = []
        for tile_x, tile_y, width, depth, _floors in lots:
            centers.append((tile_x + width / 2, tile_y + depth / 2))
            roof_bounds = pygame.Rect(tile_x - 1, tile_y - 1, width + 2, depth + 1)
            for object_data in self.scene.objects:
                building = pygame.Rect(
                    object_data["tile_x"], object_data["tile_y"],
                    object_data["tile_w"], object_data["tile_h"],
                ).inflate(2, 2)
                self.assertFalse(roof_bounds.colliderect(building))
            for x in range(roof_bounds.left, roof_bounds.right):
                for y in range(roof_bounds.top, roof_bounds.bottom):
                    on_road = (
                        (40 <= x <= 59 and 40 <= y <= 59)
                        or 47 <= x <= 52 or 47 <= y <= 52
                        or (x >= 80 and 44 <= y <= 55)
                    )
                    self.assertFalse(on_road)
        quadrant_counts = (
            sum(x < 50 and y < 50 for x, y in centers),
            sum(x >= 50 and y < 50 for x, y in centers),
            sum(x < 50 and y >= 50 for x, y in centers),
            sum(x >= 50 and y >= 50 for x, y in centers),
        )
        self.assertTrue(all(count >= 2 for count in quadrant_counts))

    def test_resident_house_wall_is_opaque_beneath_roof(self):
        tile_x, tile_y, width, depth, _floors = self.scene.citizen_house_lots[0]
        self.scene.camera_x = (tile_x + width / 2) * self.scene.tile_size
        self.scene.camera_y = (tile_y + depth / 2) * self.scene.tile_size
        self.screen.fill((0, 0, 0))
        self.scene._draw_citizen_houses(self.screen)
        sx, sy = self.scene.world_to_screen(
            tile_x * self.scene.tile_size, tile_y * self.scene.tile_size,
        )
        wall_pixel = (sx + 8, sy + depth * self.scene.tile_size * 3 // 4)
        self.assertNotEqual(self.screen.get_at(wall_pixel)[:3], (0, 0, 0))

    def test_city_palisade_visual_advances_through_ap_phases(self):
        import time

        phases = (
            (100, []),
            (1000, [False, False, False, False]),
            (1900, [True, False, False, False]),
            (2800, [True, True, True, False]),
        )
        for elapsed, expected_sections in phases:
            with self.subTest(elapsed=elapsed):
                self.scene.city_upgrade_state = {
                    "city_level": 1,
                    "active": True,
                    "started_at": time.time() - elapsed,
                }
                with patch.object(
                    self.scene, "_draw_palisade_section",
                    wraps=self.scene._draw_palisade_section,
                ) as draw_section:
                    self.scene._draw_city_upgrade_construction(self.screen)
                actual_sections = [call.args[-1] for call in draw_section.call_args_list]
                self.assertEqual(actual_sections, expected_sections)

        self.scene.city_upgrade_state = {"city_level": 2, "active": False}
        with patch.object(
            self.scene, "_draw_palisade_section",
            wraps=self.scene._draw_palisade_section,
        ) as draw_section:
            self.scene._draw_city_upgrade_construction(self.screen)
        self.assertEqual(
            [call.kwargs.get("complete", call.args[-1] if call.args else None)
             for call in draw_section.call_args_list],
            [True] * 4,
        )

    def test_global_city_home_count_follows_l1_and_l2_only(self):
        from scenes.city.exterior import draw_city_exterior
        from scenes.city.sprite_modules import draw_residence

        rect = pygame.Rect(80, 80, 480, 480)
        with patch("scenes.city.exterior.draw_residence", wraps=draw_residence) as draw_house:
            draw_city_exterior(self.screen, rect, {"city_level": 1, "population": 10})
            self.assertEqual(draw_house.call_count, 4)
            draw_house.reset_mock()
            draw_city_exterior(self.screen, rect, {"city_level": 2, "population": 4})
            self.assertEqual(draw_house.call_count, 7)
            draw_house.reset_mock()
            draw_city_exterior(self.screen, rect, {"city_level": 10, "population": 10})
            self.assertEqual(draw_house.call_count, 7)

    def test_global_ap_starts_with_trenches_before_log_staging(self):
        from scenes import city

        rect = pygame.Rect(80, 80, 480, 480)
        with patch("scenes.city.exterior._draw_trench") as trench, \
                patch("scenes.city.exterior._draw_work_logs") as logs:
            city.exterior.draw_city_exterior(
                self.screen, rect,
                {"city_level": 1, "active": True, "phase_index": 0},
            )
        trench.assert_called_once()
        logs.assert_not_called()

        with patch("scenes.city.exterior._draw_trench") as trench, \
                patch("scenes.city.exterior._draw_work_logs") as logs:
            city.exterior.draw_city_exterior(
                self.screen, rect,
                {"city_level": 1, "active": True, "phase_index": 1},
            )
        trench.assert_not_called()
        logs.assert_called_once()

    def test_city_visuals_are_limited_to_l1_and_l2(self):
        from scenes.city.sprite_modules import city_visual_tier

        self.assertEqual([city_visual_tier(level) for level in (1, 2, 3, 10)],
                         [1, 2, 2, 2])

    def test_city_level_two_keeps_central_castle_at_building_level_one(self):
        from scenes.city.exterior import draw_city_exterior

        rect = pygame.Rect(80, 80, 480, 480)
        with patch("scenes.city.exterior.draw_keep") as draw_keep:
            draw_city_exterior(self.screen, rect, {"city_level": 2, "active": False})
        draw_keep.assert_called_once()
        self.assertEqual(draw_keep.call_args.args[2], 1)

    def test_purchased_cart_is_hidden_from_buy_tab_and_available_in_transport(self):
        window = self.scene.stable_window
        self.client.cart_progress["grades"]["1"]["body_owned"] = True
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "status": "Свободна", "can_travel": True,
            "dispatch_available": True, "horse_slots": 1, "resource_slots": 1,
            "capacity_kg": 300, "seconds_per_tile": 7.2,
        }]
        window._sync_cart_progress()
        rendered = []
        original = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.small_font = Recorder()
        try:
            window._draw_carts(self.screen)
        finally:
            self.scene.small_font = original
        self.assertTrue(any(text.startswith("Новых повозок нет") for text in rendered))
        self.assertNotIn("Лёгкая повозка", rendered)
        self.assertNotIn("КУПЛЕНО", rendered)
        self.assertFalse(any("на складе:" in text or "в казне:" in text for text in rendered))
        self.assertEqual(
            [cart["id"] for cart in window._available_transport_carts()],
            ["cart_grade_1"],
        )

    def test_cart_fleet_shows_wear_in_one_row_and_repair_action(self):
        window = self.scene.stable_window
        window.is_open = True
        window.tab = "carts"
        self.client.cart_progress["grades"]["1"].update(body_owned=True, body_count=2)
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [
            {
                "id": "cart_grade_1", "grade": 1, "instance": 1,
                "name": "Лёгкая повозка", "sprite_key": "light", "status": "Сломана",
                "durability": 0, "max_durability": 100, "broken": True,
                "repair_wood_cost": 100, "maintenance_wood_per_hour": 0,
            },
            {
                "id": "cart_grade_1~2", "grade": 1, "instance": 2,
                "name": "Лёгкая повозка", "sprite_key": "light", "status": "В пути",
                "durability": 65, "max_durability": 100, "broken": False,
                "repair_wood_cost": 35, "maintenance_wood_per_hour": 2,
            },
        ]
        window._sync_cart_progress()
        window._draw_carts(self.screen)

        cards = window.cart_card_rects
        self.assertEqual(set(cards), {"cart_grade_1", "cart_grade_1~2"})
        self.assertEqual(cards["cart_grade_1"].top, cards["cart_grade_1~2"].top)
        self.assertIn("cart_grade_1", window.cart_repair_buttons)
        self.assertNotIn("cart_grade_1~2", window.cart_repair_buttons)
        with patch.object(window, "_building_action") as building_action:
            window.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=window.cart_repair_buttons["cart_grade_1"].center,
            ))
        building_action.assert_called_once_with(
            "cart/repair", {"cart_id": "cart_grade_1"},
        )

    def test_resident_houses_follow_population_without_opening_castle(self):
        self.client.population = 10
        self.client.get_city_population = lambda _character_id: {
            "population": self.client.population,
        }
        from scenes.city_scene import CityScene

        scene = CityScene(SimpleNamespace(
            character={"id": 1, "name": "Тест"}, client=self.client,
        ))
        self.assertFalse(scene.castle_menu_open)
        self.assertEqual(scene.city_population_count, 10)
        self.assertEqual(len(scene._citizen_house_solid_rects()), 10)

        self.client.population = 7
        scene.city_population_refresh_at = 0
        scene.update(0)
        self.assertEqual(scene.city_population_count, 7)
        self.assertEqual(len(scene._citizen_house_solid_rects()), 7)

    def test_stable_menu_has_name_and_level_header(self):
        self.scene.stable_window.open()
        self.scene.stable_menu_open = True
        rendered = []
        original = self.scene.large_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.large_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.large_font = original
        self.assertIn("Конюшня", rendered)
        self.assertTrue(self.scene._any_modal_open())
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(self.scene.stable_menu_open)

    def test_city_player_information_menu_and_chat_room(self):
        session = SimpleNamespace(
            character={"id": 1, "name": "Тест", "level": 1, "type": "warrior"},
            client=self.client,
            social_snapshot=lambda location: {
                "occupants": [], "messages": [], "offers": [],
                "my_application": None, "group_offers": [],
            },
        )
        from scenes.city_scene import CityScene

        scene = CityScene(session)
        try:
            self.assertEqual(scene.chat.location, "city")
            scene.active_entity = {"id": "player"}
            scene._trigger_active_action()
            self.assertTrue(scene.profile_overlay.is_open)
            scene.draw(self.screen)
        finally:
            scene.chat.close()

    def test_forge_and_workshop_modals_draw_independently(self):
        rendered = []
        original = self.scene.badge_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.badge_font = Recorder()
        try:
            self.assertEqual(self.scene.forge_modal_rect.size, self.scene.stable_window.rect.size)
            self.assertTrue(self.scene.forge_modal_rect.contains(self.scene.forge_back_button))
            self.assertEqual(
                set(self.scene.forge_tabs),
                {"weapons", "shields", "helmets", "armor", "gloves", "plates", "shoes", "smelting", "upgrades", "storage"},
            )
            forge_tab_rects = list(self.scene.forge_tabs.values())
            self.assertEqual(forge_tab_rects[0].left, self.scene.forge_modal_rect.left + 24)
            self.assertEqual(forge_tab_rects[-1].right, self.scene.forge_modal_rect.right - 24)
            self.assertTrue(all(
                current.right + 8 == following.left
                for current, following in zip(forge_tab_rects, forge_tab_rects[1:])
            ))
            self.scene.forge_menu_open = True
            self.scene.draw(self.screen)
            self.assertTrue(any("ОРУЖЕЙНАЯ КУЗНИЦА" in text for text in rendered))
            self.assertFalse(any("БРОННАЯ МАСТЕРСКАЯ" in text for text in rendered))

            for tab, button in self.scene.forge_tabs.items():
                self.scene.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1, pos=button.center))
                self.assertEqual(self.scene.forge_tab, tab)
                self.scene.draw(self.screen)

            rendered.clear()
            self.scene.forge_menu_open = False
            self.scene.workshop_menu_open = True
            self.scene.draw(self.screen)
            self.assertTrue(any("БРОННАЯ МАСТЕРСКАЯ" in text for text in rendered))
            self.assertFalse(any("ОРУЖЕЙНАЯ КУЗНИЦА" in text for text in rendered))
        finally:
            self.scene.badge_font = original

    def test_workshop_tabs_show_cart_specs_and_start_production(self):
        self.assertEqual(self.scene.workshop_modal_rect.size, self.scene.stable_window.rect.size)
        expected_tabs = {
            "helmets", "armor", "gloves", "plates", "shoes",
            "leatherworker", "carts", "upgrades", "storage",
        }
        self.assertEqual(set(self.scene.workshop_tabs), expected_tabs)
        tab_rects = list(self.scene.workshop_tabs.values())
        self.assertEqual(tab_rects[0].left, self.scene.workshop_modal_rect.left + 24)
        self.assertEqual(tab_rects[-1].right, self.scene.workshop_modal_rect.right - 24)
        self.assertTrue(all(first.right + 8 == second.left
                            for first, second in zip(tab_rects, tab_rects[1:])))

        rendered = []
        original_small = self.scene.small_font
        original_font = self.scene.font

        class Recorder:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def render(self, text, *args):
                rendered.append(str(text))
                return self.wrapped.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.wrapped, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.workshop_menu_open = True
            self.scene.workshop_tab = "storage"
            self.scene.draw(self.screen)
            self.assertTrue(any("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ" in text for text in rendered))
            self.assertTrue(any("ПРОЦЕСС РАБОТЫ МАСТЕРСКОЙ" in text for text in rendered))

            self.scene.workshop_tab = "carts"
            self.client.warehouse_storage["wood"] = 100
            self.client.treasury_silver_available = 10
            self.client.cart_progress["grades"]["1"].update(body_owned=True, body_count=1)
            self.scene._refresh_workshop_state()
            self.scene.draw(self.screen)
            self.assertIsNotNone(self.scene.workshop_cart_button)
            self.assertTrue(any("Лёгкая повозка" in text for text in rendered))
            self.assertTrue(any("Цена:" == text for text in rendered))
            self.assertTrue(any("100/100" == text for text in rendered))
            self.assertTrue(any("10/10" == text for text in rendered))
            self.assertFalse(any("(склад)" in text or "(казна)" in text for text in rendered))
            self.assertTrue(any("Производство: 40 минут" in text for text in rendered))
            self.assertTrue(any("Грузоподъёмность" in text for text in rendered))
            self.assertTrue(any("Кучер" in text for text in rendered))
            self.assertTrue(any("Упряжка" in text for text in rendered))
            self.assertTrue(any("Погрузка: 60 кг/мин" in text for text in rendered))
            self.assertTrue(any("Разгрузка: 40 кг/мин" in text for text in rendered))
            self.assertFalse(any("ОТКРЫТЬ ТРАНСПОРТ" in text or "ГОТОВА К ОТПРАВКЕ" in text
                                 for text in rendered))
            cart_catalog = dict(CART_GRADES)
            cart_catalog["3"] = {**CART_GRADES["1"], "name": "Тестовая повозка"}
            with patch("scenes.city.modals.CART_GRADES", cart_catalog):
                self.scene.draw(self.screen)
            first_lot = self.scene.workshop_cart_lot_rects[1]
            second_lot = self.scene.workshop_cart_lot_rects[3]
            self.assertEqual(first_lot.top, second_lot.top)
            self.assertEqual(first_lot.right + 10, second_lot.left)
            self.scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=self.scene.workshop_cart_button.center,
            ))
            self.assertTrue(self.scene.workshop_menu_open)
            self.assertFalse(self.scene.stable_menu_open)
            self.assertTrue(self.client.cart_progress["grades"]["1"]["body_owned"])
            self.assertIsNotNone(self.client.cart_progress["grades"]["1"]["body_finish_at"])
            self.assertEqual(self.client.warehouse_storage["wood"], 0)
            self.assertEqual(self.client.treasury_silver_available, 0)
            self.assertEqual(self.scene.workshop_state["queue"][0]["item_name"], "Лёгкая повозка")
            rendered.clear()
            self.scene.draw(self.screen)
            self.assertTrue(any("ОЧЕРЕДЬ: 1 / 5" in text for text in rendered))
            self.assertTrue(any("ОБЩЕЕ ВРЕМЯ: 40:00" in text for text in rendered))
            self.assertTrue(any("В ПРОИЗВОДСТВЕ: Лёгкая повозка" in text for text in rendered))
            self.assertTrue(any("До готовности: 40:00" in text for text in rendered))
            self.client.warehouse_storage["wood"] = 100
            self.client.treasury_silver_available = 10
            self.scene.draw(self.screen)
            self.assertIsNotNone(self.scene.workshop_cart_button)
            self.scene.workshop_state["queue"] = [{"item_name": "Заказ"}] * 5
            self.scene.draw(self.screen)
            self.assertIsNotNone(self.scene.workshop_cart_button)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font

    def test_workshop_cart_icons_use_one_tile_size(self):
        from ui.map_travel import draw_transport_cart_icon

        self.scene.workshop_menu_open = True
        self.scene.workshop_tab = "carts"
        self.scene.workshop_state.update({
            "queue": [{
                "grade": 1,
                "item_name": "Лёгкая повозка",
                "seconds_left": 1200,
                "duration_seconds": 2400,
            }],
            "queue_limit": 5,
        })
        with patch("scenes.city.modals.draw_transport_cart_icon",
                   wraps=draw_transport_cart_icon) as draw_cart:
            self.scene.draw(self.screen)

        icon_sizes = [call.args[3] for call in draw_cart.call_args_list]
        self.assertGreaterEqual(icon_sizes.count(32), 3)

    def test_stable_tabs_and_route_selection(self):
        window = self.scene.stable_window
        window.open()
        self.scene.stable_menu_open = True
        self.assertEqual(window.tab, "transport")
        ordered_tabs = sorted(window.tabs, key=lambda key: window.tabs[key].left)
        self.assertEqual(ordered_tabs, ["transport", "routes", "carts", "stalls", "upgrades"])
        self.assertEqual(list(window._upgrade_subtabs()), ["transport", "stalls", "building"])
        self.scene.draw(self.screen)

        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.tabs["routes"].center))
        self.assertEqual(window.tab, "routes")
        self.assertEqual(len(window.routes), 5)
        self.scene.draw(self.screen)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window._route_row_rects()[1].center))
        self.assertEqual(window.selected_route, 1)
        self.assertEqual(window.route_state["storage"]["wood"], 271)
        rendered = []
        original_font = self.scene.font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        self.scene.font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.font = original_font
        self.assertIn("271", rendered)

        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.tabs["carts"].center))
        self.assertEqual(window.tab, "carts")
        self.scene.draw(self.screen)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.tabs["upgrades"].center))
        self.assertEqual(window.tab, "upgrades")
        self.scene.draw(self.screen)
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window._upgrade_subtabs()["transport"].center))
        self.assertEqual(window.upgrade_tab, "transport")
        rendered = []
        original_small_font = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original_small_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_small_font, name)

        self.scene.small_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small_font
        self.assertIn("Древесина", rendered)
        self.assertIn("На складе: 12", rendered)
        sides_button = window.cart_node_buttons["sides"]
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=sides_button.center))
        self.assertEqual(window.selected_cart_node, "sides")

        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window._upgrade_subtabs()["stalls"].center))
        self.assertEqual(window.upgrade_tab, "stalls")
        rendered.clear()
        self.scene.small_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small_font
        self.assertTrue(any("Приставные деревянные денники" in text for text in rendered))
        self.assertTrue(any("Внешний сеновал" in text for text in rendered))
        self.assertTrue(any("Древесина: склад 300/300" in text for text in rendered))
        self.assertTrue(any("Серебро: казна 100/50" in text for text in rendered))
        self.assertEqual(sum(text.startswith("Оплата при покупке") for text in rendered), 2)
        self.assertEqual(window.stall_contribution_buttons, {})
        self.assertIn("wooden_stalls", window.stall_upgrade_buttons)
        upgrade_button = window.stall_upgrade_buttons["wooden_stalls"]
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=upgrade_button.center))
        self.assertIn(("stable", "stall-upgrade/purchase"), self.client.calls)

        window.state = self.client.get_building("stable", 1)
        window.state["upgrade"]["ready"] = True
        window.upgrade_tab = "building"
        rendered.clear()
        self.scene.small_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small_font
        self.assertEqual(window.deposit_buttons, {})
        self.assertTrue(any("склад 5/5" in text for text in rendered))
        self.assertTrue(any("ОПЛАТИТЬ И УЛУЧШИТЬ" in text for text in rendered))
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.upgrade_button.center))
        self.assertIn(("stable", "upgrade/start"), self.client.calls)

    def test_stalls_tab_uses_server_capacity(self):
        window = self.scene.stable_window
        window.open()
        self.scene.stable_menu_open = True
        self.assertEqual(window.state["stall_capacity"], 4)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.tabs["stalls"].center))
        self.scene.draw(self.screen)
        self.assertEqual(window.tab, "stalls")
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.stall_buy_buttons[0].center))
        self.assertIn(("stable", "horse/purchase"), self.client.calls)

    def test_stable_stall_shows_each_horses_satiety_meter(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["stall_slots"][0]["horse"] = {
            "id": 7, "name": "Лошадь 1", "breed": "Рабочая",
            "status": "Отдыхает", "satiety": 25,
        }
        rendered = []
        original_font = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append((str(text), args[1] if len(args) > 1 else None))
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        self.scene.small_font = Recorder()
        try:
            window._draw_stalls(self.screen)
        finally:
            self.scene.small_font = original_font

        satiety = next(color for text, color in rendered if text == "Сытность 25%")
        self.assertEqual(satiety, (232, 184, 48))

    def test_transport_empty_popups_for_carts_and_horses(self):
        window = self.scene.stable_window
        window.open()
        self.scene.stable_menu_open = True
        self.scene.draw(self.screen)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.transport_buttons[("cart", None)].center))
        self.scene.draw(self.screen)
        rendered = []
        original = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.small_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original
        self.assertIn("У вас нет свободного транспорта", rendered)

        window.state["available_carts"] = [
            {"id": 42, "name": "Лесная арба", "horse_slots": 1, "resource_slots": 1}
        ]
        window.transport_popup = ("cart", None)
        self.scene.draw(self.screen)
        cart_option = next(iter(window.transport_popup_options.values()))
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=cart_option.center))
        self.scene.draw(self.screen)
        horse_button = window.transport_buttons[("horse", 0)]
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=horse_button.center))
        self.scene.draw(self.screen)
        rendered.clear()
        self.scene.small_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original
        self.assertIn("У вас нет свободных лошадей", rendered)

    def test_resting_horse_without_availability_flag_is_selectable(self):
        window = self.scene.stable_window
        window.state = {"stall_slots": [{
            "unlocked": True,
            "horse": {"id": 7, "name": "Лошадь 7", "status": "Отдыхает"},
        }]}

        self.assertEqual([horse["id"] for horse in window._available_transport_horses()], [7])

    def test_crew_picker_uses_population_free_status(self):
        window = self.scene.stable_window
        window.state = {"transport_convoys": [{"driver_citizen_id": 14}]}
        self.client.get_city_population = lambda _character_id: {"citizens": [
            {"id": 11, "name": "Горожанин 11", "work_status": "Свободен",
             "satisfaction": "satisfied", "satiety": 94},
            {"id": 12, "name": "Горожанин 12", "work_status": "Свободен",
             "satisfaction": "starving", "satiety": 8},
            {"id": 13, "name": "Горожанин 13", "work_status": "Занят",
             "satisfaction": "satisfied", "satiety": 94},
            {"id": 14, "name": "Горожанин 14", "work_status": "Свободен",
             "satisfaction": "satisfied", "satiety": 94},
        ]}

        window._sync_transport_drivers()

        self.assertEqual(
            [driver["id"] for driver in window.state["available_cart_drivers"]], [11],
        )

    def test_wheat_slot_renders_icon_and_allows_dispatch_with_stale_cart_flag(self):
        window = self.scene.stable_window
        window.state = {
            "available_carts": [{
                "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "Свободна",
                "can_travel": False, "dispatch_available": False,
                "horse_slots": 1, "resource_slots": 1, "capacity_kg": 300,
                "seconds_per_tile": 24,
            }],
            "stall_slots": [{"unlocked": True, "horse": {
                "id": 7, "name": "Лошадь 7", "status": "Отдыхает", "can_travel": True,
            }}],
            "available_cart_drivers": [{"id": 11, "name": "Горожанин 11"}],
            "transport_convoys": [],
        }
        window.routes = [{
            "building_id": "wheat_farm", "name": "Пшеничная ферма",
            "distance_tiles": 50.11,
            "resources": [{"id": "wheat", "label": "Пшеница"}],
        }]
        window.transport_draft = {
            "cart_id": "cart_grade_1", "horse_ids": [7],
            "driver_citizen_id": 11, "destination_id": "wheat_farm",
            "resource_ids": ["wheat"],
        }
        rendered = []
        original_font = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(str(text))
                return original_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_font, name)

        self.scene.small_font = Recorder()
        try:
            with patch("ui.stable_window.draw_item_icon") as draw_item_icon:
                window._draw_transport(self.screen)
        finally:
            self.scene.small_font = original_font

        self.assertTrue(window._transport_can_start())
        self.assertTrue(any(call.args[1] == 63 for call in draw_item_icon.call_args_list))
        self.assertIn("Пшеница", rendered)

    def test_transport_tab_lists_owned_idle_cart_as_free(self):
        self.client.cart_progress["grades"]["1"]["body_owned"] = True
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        rendered = []
        original_small = self.scene.small_font
        original_font = self.scene.font

        class Recorder:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def render(self, text, *args):
                rendered.append(str(text))
                return self.wrapped.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.wrapped, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            window._draw_transport(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font

        self.assertTrue(any("Повозок в городе: 1" in text for text in rendered))
        self.assertIn("Свободна", rendered)
        self.assertIn("Вид сверху", rendered)
        self.assertIn("Информация о рейсе", rendered)
        self.assertNotIn("Пока нет купленных повозок", rendered)

    def test_transport_dispatch_submits_selected_crew_and_cargo(self):
        window = self.scene.stable_window
        window.is_open = True
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "Свободна",
            "can_travel": False, "dispatch_available": False,
            "dispatch_available": True, "horse_slots": 1, "resource_slots": 1,
        }]
        window.state["stall_slots"][0]["horse"] = {
            "id": 12, "name": "Лошадь 1", "can_travel": True,
        }
        window.state["available_cart_drivers"] = [{"id": 42, "name": "Участник экипажа"}]
        window.routes = [{
            "building_id": "lumber_camp", "name": "Лесопилка",
            "distance_tiles": 12.5,
            "resources": [{"id": "wood", "label": "Древесина"}],
        }]
        window.transport_draft = {
            "cart_id": "cart_grade_1", "horse_ids": [12],
            "driver_citizen_id": 42, "destination_id": "lumber_camp",
            "resource_ids": ["wood"], "pinned": True,
        }
        window.transport_start_button = pygame.Rect(20, 20, 240, 38)

        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.transport_start_button.center,
        ))

        self.assertEqual(self.client.dispatch_payload, {
            "cart_id": "cart_grade_1", "horse_ids": [12],
            "driver_citizen_id": 42, "destination_building_id": "lumber_camp",
            "resource_ids": ["wood"], "pinned": True,
        })
        self.assertIsNone(window.transport_draft["cart_id"])

    def test_dispatch_button_waits_until_cargo_slot_is_selected(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "Свободна",
            "can_travel": True, "dispatch_available": True,
            "horse_slots": 1, "resource_slots": 1,
        }]
        window.state["stall_slots"][0]["horse"] = {
            "id": 12, "name": "Лошадь 1", "can_travel": True,
        }
        window.state["available_cart_drivers"] = [{"id": 42, "name": "Горожанин 12"}]
        window.routes = [{
            "building_id": "lumber_camp", "name": "Лесопилка",
            "distance_tiles": 12.5, "resources": [{"id": "wood", "label": "Древесина"}],
        }]
        window.transport_draft = {
            "cart_id": "cart_grade_1", "horse_ids": [12],
            "driver_citizen_id": 42, "destination_id": "lumber_camp",
            "resource_ids": [None], "pinned": False,
        }

        reasons = window._transport_block_reasons()
        self.assertEqual(reasons, ["Выберите груз для слота 1."])
        self.assertFalse(window._transport_can_start())

    def test_repeat_route_checkbox_toggles_draft(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "Свободна",
            "can_travel": True, "dispatch_available": True,
            "horse_slots": 1, "resource_slots": 1,
        }]
        window.routes = [{
            "building_id": "lumber_camp", "name": "Лесопилка",
            "distance_tiles": 12.5,
            "resources": [{"id": "wood", "label": "Древесина"}],
        }]
        window.transport_draft.update({
            "cart_id": "cart_grade_1", "destination_id": "lumber_camp",
            "resource_ids": ["wood"],
        })

        window._draw_transport(self.screen)
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.transport_pin_draft_button.center,
        ))

        self.assertTrue(window.transport_draft["pinned"])

    def test_active_pinned_route_can_be_unpinned(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "В пути",
            "can_travel": False, "dispatch_available": False,
            "horse_slots": 1, "resource_slots": 1,
        }]
        window.state["transport_convoys"] = [{
            "id": 55, "cart_id": "cart_grade_1", "status": "В пути", "pinned": True,
            "horses": [], "seconds_remaining": 60,
        }]

        window._draw_transport(self.screen)
        button = window.transport_pin_buttons[55]
        window.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=button.center,
        ))

        self.assertEqual(self.client.calls[-1], ("stable", "transport/pin"))
        self.assertEqual(self.client.last_payload, {"convoy_id": 55, "pinned": False})

    def test_carts_tab_renders_fleet_row_and_compact_purchase(self):
        window = self.scene.stable_window
        window.open()
        self.scene.stable_menu_open = True
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=window.tabs["carts"].center))
        self.scene.draw(self.screen)
        rendered = []
        original = self.scene.small_font
        original_font = self.scene.font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.small_font = Recorder()
        self.scene.font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original
            self.scene.font = original_font
        self.assertIn("Состояние повозок", rendered)
        self.assertIn("Пока нет изготовленных повозок.", rendered)
        self.assertTrue(any("Лёгкая повозка" in text for text in rendered))
        self.assertFalse(any("Крестьянский обоз" in text for text in rendered))
        self.assertTrue(any("100 древесины + 10 серебра" in text for text in rendered))
        self.assertIn("ИЗГОТОВИТЬ", rendered)
        self.assertFalse(any("Слотов для товаров" in text for text in rendered))
        self.assertFalse(any("500 тайлов/час" in text for text in rendered))

    def test_cart_stays_unavailable_until_production_completes(self):
        window = self.scene.stable_window
        grade = self.client.cart_progress["grades"]["1"]
        grade.update(wood_deposited=100, silver_deposited=10)
        window.state = self.client.get_building("stable", 1)
        window._sync_cart_progress()

        window._building_action("cart/purchase", {"grade": 1})

        self.assertFalse(window.cart_progress["grades"]["1"]["body_owned"])
        self.assertEqual(window.cart_progress["grades"]["1"]["body_finish_at"], 2400)
        carts = window._available_transport_carts()
        self.assertEqual(carts, [])
        self.assertEqual(window.message, "Заказ принят. Повозка появится в транспорте через 40 минут.")

        window.tab = "carts"
        window._draw_carts(self.screen)
        self.assertNotIn(1, window.cart_purchase_buttons)
        grade["body_owned"] = True
        grade["body_finish_at"] = None
        window.state = self.client.get_building("stable", 1)
        window._sync_cart_progress()
        carts = window._available_transport_carts()
        self.assertEqual([cart["id"] for cart in carts], ["cart_grade_1"])
        self.assertFalse(carts[0]["dispatch_available"])
        window._select_transport_option(("cart", None, carts[0]["id"]))
        self.assertEqual(window.message, "Для рейса нужна свободная отдыхающая лошадь.")

    def test_transport_table_lists_all_owned_carts_and_their_details(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [
            {"id": "cart_grade_1", "name": "Лёгкая повозка", "status": "В пути",
             "can_travel": False, "horse_slots": 1, "resource_slots": 1, "capacity_kg": 300},
            {"id": "cart_grade_2", "name": "Крестьянский обоз", "status": "Свободна",
             "can_travel": True, "horse_slots": 2, "resource_slots": 2, "capacity_kg": 450},
        ]
        window.state["transport_convoys"] = [{
            "id": 17, "cart_id": "cart_grade_1", "cart_name": "Лёгкая повозка",
            "destination_name": "Крестьянское поселение", "cargo_kg": 150,
            "capacity_kg": 300, "driver_name": "Горожанин 1", "horses": [{"name": "Лошадь 1"}],
            "status": "Едет к объекту", "seconds_remaining": 900, "pinned": True,
        }]
        rendered = []
        original_font, original_small, original_tiny = (
            self.scene.font, self.scene.small_font, window.tiny_font,
        )

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.font = Recorder(original_font)
        self.scene.small_font = Recorder(original_small)
        window.tiny_font = Recorder(original_small)
        try:
            window._draw_transport(self.screen)
        finally:
            self.scene.font = original_font
            self.scene.small_font = original_small
            window.tiny_font = original_tiny

        self.assertIn("Повозок в городе: 2", rendered)
        self.assertIn("Лёгкая повозка", rendered)
        self.assertIn("Крестьянский обоз", rendered)
        self.assertIn("Маршрут: Крестьянское поселение", rendered)
        self.assertIn("150 / 300 кг", rendered)
        self.assertIn("0 / 450 кг", rendered)
        self.assertEqual(len(window.transport_timeline_rects), 5)
        self.assertEqual(len({rect.width for rect in window.transport_timeline_rects}), 1)

    def test_transport_table_scrolls_to_third_cart(self):
        window = self.scene.stable_window
        window.is_open = True
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [
            {"id": f"cart_grade_{grade}", "name": f"Повозка {grade}",
             "status": "Свободна", "can_travel": True, "horse_slots": 1,
             "resource_slots": 1, "capacity_kg": 300}
            for grade in range(1, 4)
        ]
        window.state["transport_convoys"] = []
        window.transport_scroll = 0
        rendered = []
        original_font, original_small = self.scene.font, self.scene.small_font

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.font = Recorder(original_font)
        self.scene.small_font = Recorder(original_small)
        try:
            window._draw_transport(self.screen)
            self.assertIn("Повозка 1", rendered)
            self.assertIn("Повозка 2", rendered)
            self.assertNotIn("Повозка 3", rendered)

            rendered.clear()
            window.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-1))
            window._draw_transport(self.screen)
        finally:
            self.scene.font = original_font
            self.scene.small_font = original_small

        self.assertEqual(window.transport_scroll, 1)
        self.assertNotIn("Повозка 1", rendered)
        self.assertIn("Повозка 2", rendered)
        self.assertIn("Повозка 3", rendered)
        self.assertEqual(len({rect.height for rect in window.transport_timeline_rects}), 1)

    def test_transport_route_timeline_colors_completed_current_and_future_stages(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.state["available_carts"] = [{
            "id": "cart_grade_1", "name": "Лёгкая повозка", "status": "В пути",
            "can_travel": False, "horse_slots": 1, "resource_slots": 1, "capacity_kg": 300,
        }]
        window.state["transport_convoys"] = [{
            "id": 21, "cart_id": "cart_grade_1", "cart_name": "Лёгкая повозка",
            "destination_name": "Крестьянское поселение", "cargo_kg": 100,
            "capacity_kg": 300, "driver_name": "Горожанин 1", "horses": [],
            "status": "Погрузка", "phase": "loading", "seconds_remaining": 125,
            "cycle_seconds_remaining": 900, "pinned": True,
            "route_stages": [
                {"phase": "outbound", "label": "В поселение", "seconds": 0, "state": "complete"},
                {"phase": "loading", "label": "Погрузка", "seconds": 125, "state": "current"},
                {"phase": "returning", "label": "В город", "seconds": 600, "state": "future"},
                {"phase": "unloading", "label": "Разгрузка", "seconds": 170, "state": "future"},
            ],
        }]
        rendered_colors = {}
        original_font, original_small, original_tiny = (
            self.scene.font, self.scene.small_font, window.tiny_font,
        )

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered_colors[str(text)] = args[1] if len(args) > 1 else None
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.font = Recorder(original_font)
        self.scene.small_font = Recorder(original_small)
        window.tiny_font = Recorder(original_tiny)
        try:
            window._draw_transport(self.screen)
        finally:
            self.scene.font = original_font
            self.scene.small_font = original_small
            window.tiny_font = original_tiny

        self.assertEqual(rendered_colors["В поселение"], (143, 148, 143))
        self.assertEqual(rendered_colors["Погрузка"], (139, 224, 145))
        self.assertEqual(rendered_colors["В город"], (139, 190, 231))
        self.assertEqual(rendered_colors["Разгрузка"], (139, 190, 231))
        self.assertIn("00:02:05", rendered_colors)
        self.assertIn("00:15:00", rendered_colors)

    def test_cart_grade_one_formulas_and_grade_two_gate(self):
        from core.cart_progress import cart_stats, grade_two_unlocked

        levels = {"wheels": 3, "sides": 3, "axles": 3}
        stats = cart_stats(levels)
        self.assertEqual(stats["capacity_kg"], 450)
        self.assertAlmostEqual(stats["seconds_per_tile"], 1.2)
        self.assertEqual(stats["empty_tiles_per_hour"], 3000)
        self.assertEqual(stats["full_load_speed_penalty_percent"], 40)
        progress = {"grades": {"1": {"upgrades": {"wheels": 3, "sides": 3, "axles": 2}}}}
        self.assertFalse(grade_two_unlocked(progress))
        progress["grades"]["1"]["upgrades"]["axles"] = 3
        self.assertTrue(grade_two_unlocked(progress))

    def test_light_cart_revised_base_spec(self):
        from core.cart_progress import CART_GRADES, cart_load_speed_ratio, cart_stats

        grade = CART_GRADES["1"]
        stats = cart_stats({"wheels": 0, "sides": 0, "axles": 0})
        self.assertEqual(stats["empty_tiles_per_hour"], 500)
        self.assertEqual(stats["seconds_per_tile"], 7.2)
        self.assertEqual(stats["capacity_kg"], 300)
        self.assertEqual(stats["full_load_speed_penalty_percent"], 70)
        self.assertEqual(grade["resource_slots"], 1)
        self.assertEqual(grade["horse_count"], 1)
        self.assertEqual(grade["villagers_required"], 1)
        self.assertEqual(grade["load_kg_per_minute"], 60)
        self.assertEqual(grade["load_kg_per_20_seconds"], 20)
        self.assertEqual(cart_load_speed_ratio(0, 300, 70), 1.0)
        self.assertAlmostEqual(cart_load_speed_ratio(150, 300, 70), 0.65)
        self.assertAlmostEqual(cart_load_speed_ratio(300, 300, 70), 0.3)


if __name__ == "__main__":
    unittest.main()
