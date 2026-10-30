import unittest

from core.currency import Currency
from tests.fixtures import create_test_database, drop_test_database


class PlayerCorpseDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.user_id = self.database.register("corpsetester", "password")["id"]
        self.character_id = self.database.create_character(self.user_id, "Погибший")["id"]

    def tearDown(self):
        drop_test_database(self.database)

    def fund(self, copper):
        self.database.add_world_currency(self.user_id, self.character_id, copper)

    def wallet_copper(self):
        return Currency(**self.database.add_world_currency(self.user_id, self.character_id, 0)).total_copper()

    def empty_wallet(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET copper=0, silver=0, gold=0 WHERE id=%s AND world_id=%s",
                (self.character_id, self.database.world_id),
            )

    def test_death_takes_percent_of_coins_into_corpse(self):
        self.fund(1000)
        total = self.wallet_copper()
        corpse, currency = self.database.create_player_corpse(
            self.user_id, self.character_id, 300.0, 400.0, 20)
        self.assertEqual(corpse["copper"], total * 20 // 100)
        self.assertEqual((corpse["x"], corpse["y"]), (300.0, 400.0))
        self.assertEqual(self.wallet_copper(), total - corpse["copper"])
        self.assertEqual(Currency(**currency).total_copper(), total - corpse["copper"])
        listed = self.database.list_player_corpses(self.character_id)
        self.assertEqual([item["id"] for item in listed], [corpse["id"]])

    def test_no_corpse_without_coins(self):
        self.empty_wallet()
        self.assertIsNone(self.database.create_player_corpse(self.user_id, self.character_id, 0.0, 0.0, 20))
        self.assertEqual(self.database.list_player_corpses(self.character_id), [])

    def test_loot_returns_coins_and_removes_corpse(self):
        self.fund(1000)
        total = self.wallet_copper()
        corpse, _ = self.database.create_player_corpse(self.user_id, self.character_id, 1.0, 2.0, 20)
        currency, looted = self.database.loot_player_corpse(self.user_id, self.character_id, corpse["id"])
        self.assertEqual(looted, corpse["copper"])
        self.assertEqual(Currency(**currency).total_copper(), total)
        self.assertEqual(self.wallet_copper(), total)
        self.assertEqual(self.database.list_player_corpses(self.character_id), [])
        with self.assertRaises(ValueError):
            self.database.loot_player_corpse(self.user_id, self.character_id, corpse["id"])

    def test_corpses_stack_and_each_is_looted_separately(self):
        self.fund(1000)
        first, _ = self.database.create_player_corpse(self.user_id, self.character_id, 1.0, 2.0, 20)
        second, _ = self.database.create_player_corpse(self.user_id, self.character_id, 5.0, 6.0, 20)
        self.assertEqual(len(self.database.list_player_corpses(self.character_id)), 2)
        self.database.loot_player_corpse(self.user_id, self.character_id, second["id"])
        remaining = self.database.list_player_corpses(self.character_id)
        self.assertEqual([item["id"] for item in remaining], [first["id"]])

    def test_other_user_cannot_loot_corpse(self):
        self.fund(1000)
        corpse, _ = self.database.create_player_corpse(self.user_id, self.character_id, 1.0, 2.0, 20)
        stranger_id = self.database.register("stranger", "password")["id"]
        stranger_character = self.database.create_character(stranger_id, "Чужой")["id"]
        with self.assertRaises(ValueError):
            self.database.loot_player_corpse(stranger_id, stranger_character, corpse["id"])
        self.assertEqual(len(self.database.list_player_corpses(self.character_id)), 1)


if __name__ == "__main__":
    unittest.main()
