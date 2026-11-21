import unittest

from server.items_database import ItemsDatabase
from tests.fixtures import create_test_database, drop_test_database, running_server


class TowerStorageTransferTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        self.user_id = self.database.register("storage_tower", "password")["id"]
        self.character_id = self.database.create_character(self.user_id, "Хранитель")["id"]
        self.items = ItemsDatabase(self.database)

    def test_api_moves_partial_stack_both_directions(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 63, 6))
        with running_server(self.database, mode="tower") as client:
            client.token = self.database.login("storage_tower", "password")["token"]
            state = self.items.get_inventory_state(self.character_id)
            source_slot = state["inventory"][0]["slot_index"]

            deposited = client.transfer_storage(
                self.character_id, "chest2", "deposit", 4, slot_index=source_slot
            )
            self.assertEqual(sum(row["quantity"] for row in deposited["inventory"]), 2)
            self.assertEqual(len(deposited["storage"]), 1)
            storage_row = deposited["storage"][0]
            self.assertEqual(storage_row["quantity"], 4)

            withdrawn = client.transfer_storage(
                self.character_id,
                "chest2",
                "withdraw",
                3,
                storage_item_id=storage_row["id"],
            )
            self.assertEqual(sum(row["quantity"] for row in withdrawn["inventory"]), 5)
            self.assertEqual(withdrawn["storage"][0]["quantity"], 1)

    def test_failed_transfer_preserves_both_sides(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 63, 2))
        slot = self.items.get_inventory(self.character_id)[0]["slot_index"]
        with self.assertRaisesRegex(ValueError, "недостаточно"):
            self.items.transfer_storage(self.character_id, "chest1", "deposit", 3, slot_index=slot)
        self.assertEqual(self.items.get_inventory(self.character_id)[0]["quantity"], 2)
        self.assertEqual(self.items.get_storage(self.character_id, "chest1"), [])

    def test_economy_mode_accepts_common_storage_transfer(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 63, 2))
        slot = self.items.get_inventory(self.character_id)[0]["slot_index"]
        with running_server(self.database, mode="economy") as client:
            client.token = self.database.login("storage_tower", "password")["token"]
            state = client.transfer_storage(
                self.character_id, "chest1", "deposit", 1, slot_index=slot
            )
        self.assertEqual(state["inventory"][0]["quantity"], 1)
        self.assertEqual(state["storage"][0]["quantity"], 1)


class DeckStorageTransferTests(unittest.TestCase):
    def setUp(self):
        from deck.server.items_database import ItemsDatabase as DeckItemsDatabase
        from tests.deck.server_fixtures import create_test_database, drop_test_database

        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        self.items = DeckItemsDatabase(self.database)

    def test_deck_api_moves_items_between_backpack_and_chest(self):
        from tests.deck.server_fixtures import running_server

        user = self.database.register("storage_deck", "password")
        character_id = self.database.create_character(user["id"], "Хранитель")["id"]
        self.assertTrue(self.items.add_to_inventory(character_id, 63, 5))
        slot = self.items.get_inventory(character_id)[0]["slot_index"]
        with running_server(self.database) as client:
            client.login("storage_deck", "password")
            deposited = client.transfer_storage(
                character_id, "chest1", "deposit", 3, slot_index=slot
            )
            self.assertEqual(sum(row["quantity"] for row in deposited["inventory"]), 2)
            storage_row = deposited["storage"][0]
            withdrawn = client.transfer_storage(
                character_id, "chest1", "withdraw", 2,
                storage_item_id=storage_row["id"],
            )
            self.assertEqual(sum(row["quantity"] for row in withdrawn["inventory"]), 4)
            self.assertEqual(len(withdrawn["storage"]), 1)
            self.assertEqual(withdrawn["storage"][0]["quantity"], 1)


if __name__ == "__main__":
    unittest.main()
