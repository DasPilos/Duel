import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from client.network import ServerError
from combat.fighter import Fighter
from server.main import GameRequestHandler
from tests.fixtures import running_server
from server.database import Database
from server.items_database import BACKPACK_SIZE, MAX_STACK, STARTER_KIT, ItemsDatabase


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        self.items = ItemsDatabase(self.database)
        user = self.database.register("tester", "password")
        self.user_id = user["id"]
        self.character_id = self.database.create_character(self.user_id, "Воин")["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def bag(self):
        return {item["slot_index"]: item for item in self.items.get_inventory(self.character_id)}

    def test_starter_kit_is_granted_once(self):
        self.assertTrue(self.items.ensure_starter_kit(self.character_id))
        self.assertFalse(self.items.ensure_starter_kit(self.character_id))
        self.assertEqual(len(self.bag()), len(STARTER_KIT))

    def test_potions_stack_and_equipment_does_not(self):
        self.items.add_to_inventory(self.character_id, 2, MAX_STACK + 5)
        self.items.add_to_inventory(self.character_id, 20, 2)
        quantities = sorted((item["item_id"], item["quantity"]) for item in self.bag().values())
        self.assertEqual(quantities, [(2, 5), (2, MAX_STACK), (20, 1), (20, 1)])

    def test_full_backpack_rejects_new_items_without_partial_add(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE))
        self.assertFalse(self.items.add_to_inventory(self.character_id, 2, 1))
        self.assertEqual(len(self.bag()), BACKPACK_SIZE)

    def test_move_to_empty_cell_and_swap(self):
        self.items.add_to_inventory(self.character_id, 20, 1)  # ячейка 0
        self.items.add_to_inventory(self.character_id, 2, 1)   # ячейка 1
        self.items.move_item(self.character_id, 0, 7)
        self.assertEqual(self.bag()[7]["item_id"], 20)
        self.items.move_item(self.character_id, 7, 1)
        bag = self.bag()
        self.assertEqual((bag[1]["item_id"], bag[7]["item_id"]), (20, 2))

    def test_move_merges_same_potions(self):
        self.items.add_to_inventory(self.character_id, 2, 3)  # ячейка 0
        # Вторая стопка тех же зелий (add_to_inventory сам бы их объединил)
        with self.database.connection() as connection:
            connection.execute(
                "INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at) VALUES (?, 2, 4, 9, 0)",
                (self.character_id,),
            )
        self.items.move_item(self.character_id, 9, 0)
        bag = self.bag()
        self.assertEqual(bag[0]["quantity"], 7)
        self.assertNotIn(9, bag)

    def test_equip_swaps_previous_item_into_same_cell(self):
        self.items.add_to_inventory(self.character_id, 20, 1)  # железный меч, ячейка 0
        self.items.add_to_inventory(self.character_id, 21, 1)  # стальной меч, ячейка 1
        self.items.equip_item(self.character_id, 0)
        self.items.equip_item(self.character_id, 1, "weapon")
        self.assertEqual(self.items.get_equipment(self.character_id)["weapon"]["item_id"], 21)
        self.assertEqual(self.bag()[1]["item_id"], 20)
        self.assertEqual(self.items.get_stat_bonuses(self.character_id), {"strength": 2, "intuition": 1})

    def test_equip_rejects_wrong_slot_and_non_equipment(self):
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.add_to_inventory(self.character_id, 2, 1)
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 0, "head")
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 1)
        self.assertEqual(self.items.get_equipment(self.character_id), {})

    def test_unequip_to_chosen_cell_and_full_backpack(self):
        self.items.add_to_inventory(self.character_id, 32, 1)
        self.items.equip_item(self.character_id, 0)
        self.items.unequip_item(self.character_id, "head", target_slot=12)
        self.assertEqual(self.bag()[12]["item_id"], 32)

        self.items.equip_item(self.character_id, 12)
        self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE)
        with self.assertRaises(ValueError):
            self.items.unequip_item(self.character_id, "head")
        self.assertIn("head", self.items.get_equipment(self.character_id))

    def test_health_potion_heals_and_is_consumed(self):
        character = self.database.get_character(self.user_id, self.character_id)
        self.database.save_character(self.user_id, self.character_id, {**character, "hp": 10})
        self.items.add_to_inventory(self.character_id, 2, 2)
        updated = self.items.use_item(self.user_id, self.character_id, 0)
        self.assertEqual(updated["hp"], min(60, updated["max_hp"]))
        self.assertEqual(self.bag()[0]["quantity"], 1)

    def test_potion_is_not_wasted_at_full_health(self):
        self.items.add_to_inventory(self.character_id, 2, 1)
        with self.assertRaises(ValueError):
            self.items.use_item(self.user_id, self.character_id, 0)
        self.assertEqual(self.bag()[0]["quantity"], 1)

    def test_character_payload_carries_equipment_bonuses(self):
        self.items.add_to_inventory(self.character_id, 31, 1)  # боевой доспех: выносливость +2
        self.items.equip_item(self.character_id, 0)
        character = self.database.get_character(self.user_id, self.character_id)
        self.assertEqual(character["equipment_bonuses"], {"endurance": 2})
        battle = self.database.get_character_for_battle(self.character_id)["character"]
        self.assertEqual(battle["equipment_bonuses"], {"endurance": 2})

    def test_fighter_uses_equipment_bonus_without_changing_base_stats(self):
        fighter = Fighter("Воин")
        base_strength = fighter.stats["strength"]
        base_hp = fighter.max_hp
        fighter.equipment_stat_modifiers = {"strength": 2, "endurance": 1}
        fighter.recalculate_parameters()
        self.assertEqual(fighter.strength, base_strength + 2)
        self.assertEqual(fighter.stats["strength"], base_strength)
        self.assertGreater(fighter.max_hp, base_hp)


class InventoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        # running_server подменяет только database; предметы тоже уводим во временную базу
        self.items_patch = patch.object(GameRequestHandler, "items_database", ItemsDatabase(self.database))
        self.items_patch.start()

    def tearDown(self):
        self.items_patch.stop()
        self.temp_dir.cleanup()

    def test_client_round_trip(self):
        with running_server(self.database) as client:
            client.register("bagowner", "password")
            client.login("bagowner", "password")
            character = client.create_character("Носильщик")
            state = client.get_inventory(character["id"])
            bag = {item["slot_index"]: item for item in state["inventory"]}
            self.assertEqual(len(bag), len(STARTER_KIT))
            self.assertEqual(state["capacity"], BACKPACK_SIZE)

            sword_slot = next(index for index, item in bag.items() if item["item_id"] == 20)
            state = client.equip_item(character["id"], sword_slot, "weapon")
            self.assertEqual(state["equipment"]["weapon"]["name"], "Железный меч")
            self.assertEqual(state["bonuses"], {"strength": 1})

            state = client.unequip_item(character["id"], "weapon", 40)
            self.assertEqual({item["slot_index"]: item["item_id"] for item in state["inventory"]}[40], 20)

            state = client.move_item(character["id"], 40, 41)
            state = client.drop_item(character["id"], 41)
            self.assertNotIn(20, [item["item_id"] for item in state["inventory"]])

            with self.assertRaises(ServerError):
                client.equip_item(character["id"], 49)


if __name__ == "__main__":
    unittest.main()
