import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from core import settings
from core.cart_progress import DEFAULT_CART_PROGRESS
from core.production_buildings import building_resources, upgrade_requirements
from server.items_database import ItemsDatabase
from server.production_buildings import ProductionBuildings, STORAGE_RESOURCES_BY_ITEM_ID
from server.structures import city_structures
from tests.fixtures import create_test_database, drop_test_database

BARN_GOODS = ("berries", "wheat", "meat")
WAREHOUSE_GOODS = (
    "wood", "board", "flax", "cotton", "leather", "coal", "stone", "iron", "mithril", "obsidian",
    "iron_ingot", "steel", "hard_leather", "thick_leather", "cloth", "stone_block",
)


class CityStorageServerTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.buildings = ProductionBuildings(self.database)
        user = self.database.register("keeper", "password")
        self.character_id = self.database.create_character(user["id"], "Keeper")["id"]
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

    def test_goods_lists_and_capacity(self):
        barn = self.buildings.get_state(self.character_id, "barn", 10000)
        self.assertEqual(barn["storage"], {**{good: 0 for good in BARN_GOODS}, "limit": 1000})
        self.assertEqual(barn["worker_slots"], [])
        warehouse = self.buildings.get_state(self.character_id, "warehouse", 10000)
        self.assertEqual(warehouse["storage"], {**{good: 0 for good in WAREHOUSE_GOODS}, "limit": 2000})
        self.assertEqual(building_resources("barn"), BARN_GOODS)

    def test_upgrade_levels_and_max_level(self):
        items = ItemsDatabase(self.database)
        expected = {"barn": (1000, 1500, 2000, 2700, 4000), "warehouse": (2000, 3000, 5000, 7000, 10000)}
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
        purchased = self.buildings.purchase_cart(self.character_id, now=10003)
        self.assertTrue(purchased["cart_progress"]["grades"]["1"]["body_owned"])
        self.assertEqual(purchased["warehouse_storage"]["wood"], 0)
        self.assertEqual(purchased["treasury_silver_available"], 0)
        self.assertEqual(purchased["silver_available"], 50)
        self.assertEqual(len(purchased["available_carts"]), 1)
        self.assertEqual(purchased["available_carts"][0]["id"], "cart_grade_1")
        self.assertFalse(purchased["available_carts"][0]["dispatch_available"])
        persisted = ProductionBuildings(self.database).get_state(self.character_id, "stable", 10004)
        self.assertTrue(persisted["cart_progress"]["grades"]["1"]["body_owned"])
        self.assertEqual(len(persisted["available_carts"]), 1)

    def test_cart_purchase_rejects_shortage_without_partial_debit(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=500 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        with self.assertRaisesRegex(ValueError, "Недостаточно ресурсов на общем складе"):
            self.buildings.purchase_cart(self.character_id, now=10003)
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
        limit = 1000 if building == "barn" else 2000
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
        free = max(0, limit - sum(state["storage"].get(good, 0) for good in goods))
        state["storage_depositable"] = {
            resource: {"item_id": item_id, "in_backpack": backpack.get(item_id, 0),
                       "max_deposit": min(backpack.get(item_id, 0), free)}
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
                grade["body_owned"] = True
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
        self.assertTrue(self.client.cart_progress["grades"]["1"]["body_owned"])

    def test_cart_shortage_does_not_offer_backpack_contribution(self):
        window = self.scene.stable_window
        window.state = self.client.get_building("stable", 1)
        window.tab = "carts"
        window._draw_carts(self.screen)

        self.assertEqual(window.cart_contribution_areas, {})
        self.assertNotIn(1, window.cart_purchase_buttons)
        self.assertIsNone(window.source_picker)
        self.assertFalse(any(action == "cart/purchase" for _, action in self.client.calls))

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
        for text in ("Уровень 1", "Товары:", "Заполнен: 0 / 1000", "Ягоды", "Пшеница", "Мясо"):
            self.assertIn(text, rendered)
        self.assertEqual(rendered.count("0"), 3)
        self.assertEqual(window.production_desc(2), "Вместимость: 1500 продукции")

    def test_stable_is_server_placed_rendered_and_reachable(self):
        stable = next(obj for obj in self.scene.objects if obj["id"] == "stable_building")
        self.assertEqual((stable["tile_x"], stable["tile_y"], stable["tile_w"], stable["tile_h"]), (77, 6, 17, 6))
        self.scene.player_x, self.scene.player_y = stable["approach_pos"]
        self.assertTrue(self.scene._is_within_one_tile(stable))
        self.assertFalse(self.scene._check_collision(*stable["approach_pos"]))
        self.scene.draw(self.screen)

    def test_resident_houses_block_movement_as_population_grows(self):
        from scenes.city.rendering import CITIZEN_HOUSE_LOTS

        first_house = self.scene._citizen_house_solid_rects()[0]
        self.assertTrue(self.scene._check_collision(*first_house.center))
        self.assertFalse(self.scene._check_collision(first_house.left - 16, first_house.centery))

        tile_x, tile_y, width_tiles, depth_tiles, _floors = CITIZEN_HOUSE_LOTS[4]
        fifth_house_center = (tile_x * self.scene.tile_size + width_tiles * self.scene.tile_size // 2,
                              tile_y * self.scene.tile_size + depth_tiles * self.scene.tile_size // 2)
        self.assertFalse(self.scene._check_collision(*fifth_house_center))
        self.scene.city_population_count = 5
        self.assertTrue(self.scene._check_collision(*fifth_house_center))

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

        self.assertTrue(any("Куплено повозок: 1" in text for text in rendered))
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

    def test_carts_tab_renders_grades_stock_and_selectable_nodes(self):
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
        self.assertTrue(any("Лёгкая повозка" in text for text in rendered))
        self.assertTrue(any("Крестьянский обоз" in text for text in rendered))
        self.assertTrue(any("Слотов для товаров" in text for text in rendered))
        self.assertIn("НЕДОСТАТОЧНО", rendered)
        self.assertFalse(any(text == "20" for text in rendered))
        self.assertTrue(any("требование: уровень конюшни 1" in text for text in rendered))
        self.assertTrue(any("Древесина на складе:" in text for text in rendered))
        self.assertTrue(any("Серебро в казне:" in text for text in rendered))
        self.assertFalse(any("Грейд 1" in text for text in rendered))
        self.assertTrue(any("150 тайлов/час" in text for text in rendered))
        self.assertTrue(any("1 кг/20 сек (3 кг/мин)" in text for text in rendered))
        self.assertFalse(any(text.startswith("не задано") for text in rendered))

    def test_purchased_cart_moves_to_transport_and_is_not_purchasable_again(self):
        window = self.scene.stable_window
        grade = self.client.cart_progress["grades"]["1"]
        grade.update(wood_deposited=100, silver_deposited=10)
        window.state = self.client.get_building("stable", 1)
        window._sync_cart_progress()

        window._building_action("cart/purchase", {"grade": 1})

        self.assertTrue(window.cart_progress["grades"]["1"]["body_owned"])
        carts = window._available_transport_carts()
        self.assertEqual([cart["id"] for cart in carts], ["cart_grade_1"])
        self.assertFalse(carts[0]["dispatch_available"])
        self.assertEqual(window.message, "Лёгкая повозка куплена и добавлена в транспорт.")

        window.tab = "carts"
        window._draw_carts(self.screen)
        self.assertNotIn(1, window.cart_purchase_buttons)
        window._select_transport_option(("cart", None, carts[0]["id"]))
        self.assertEqual(window.message, "Для рейса нужна свободная отдыхающая лошадь.")

    def test_cart_grade_one_formulas_and_grade_two_gate(self):
        from core.cart_progress import cart_stats, grade_two_unlocked

        levels = {"wheels": 3, "sides": 3, "axles": 3}
        stats = cart_stats(levels)
        self.assertEqual(stats["capacity_kg"], 450)
        self.assertAlmostEqual(stats["seconds_per_tile"], 17.9473)
        self.assertEqual(stats["full_load_speed_penalty_percent"], 40)
        progress = {"grades": {"1": {"upgrades": {"wheels": 3, "sides": 3, "axles": 2}}}}
        self.assertFalse(grade_two_unlocked(progress))
        progress["grades"]["1"]["upgrades"]["axles"] = 3
        self.assertTrue(grade_two_unlocked(progress))


if __name__ == "__main__":
    unittest.main()
