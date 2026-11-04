"""Серверные предметы Колоды: каталог, рюкзак, экипировка, сундуки, магазины, награды и колоды.

ItemsDatabase вызывается напрямую (без HTTP): каждому тесту достаются свои схемы PostgreSQL.
Деньги — единый баланс монет.
"""

import json
import unittest
import uuid
from dataclasses import replace
from unittest.mock import patch

from kaloda.combat.card_database import DUNGEON_CARD_KEYS, UNIVERSAL_CARDS
from kaloda.currency import format_coins
from kaloda.rewards import DUNGEON_TREASURE_COINS, roll_dungeon_treasure
from kaloda.server.database import STARTING_COINS
from kaloda.server.items_database import (
    BACKPACK_SIZE,
    CATALOG,
    COLLECTION_SLOTS,
    MAX_STACK,
    SUPPLIES_SHOP_ITEM_IDS,
    ItemsDatabase,
    card_price_coins,
)
from tests.kaloda.server_fixtures import create_test_database, drop_test_database

SUPPLIES_PRICES = {4: 15, 5: 15, 6: 5, 52: 60}
CARDS_MODULE = "kaloda.server.items_database.UNIVERSAL_CARDS"
TREASURE_ROLL = "kaloda.server.items_database.roll_dungeon_treasure"


def priced_cards(**changes):
    """UNIVERSAL_CARDS с подменёнными полями цены/редкости: тесты механики не зависят от текущих цен карт."""
    return tuple(
        replace(card, **changes[card.key]) if card.key in changes else card
        for card in UNIVERSAL_CARDS
    )


class ItemsTestCase(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.addCleanup(drop_test_database, self.database)
        self.items = ItemsDatabase(self.database)
        self.user_id = self.database.register("tester", "password")["id"]
        self.character_id = self.database.create_character(self.user_id, "Воин")["id"]

    def another_character(self, username="other", name="Чужак", profession="warrior"):
        user_id = self.database.register(username, "password")["id"]
        return user_id, self.database.create_character(user_id, name, profession)["id"]

    def set_wallet(self, coins=0, character_id=None):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET coins = %s WHERE id = %s",
                (coins, character_id or self.character_id),
            )

    def wallet(self, character_id=None):
        with self.database.connection() as connection:
            return connection.execute(
                "SELECT coins FROM characters WHERE id = %s",
                (character_id or self.character_id,),
            ).fetchone()

    def balance(self, character_id=None):
        return int(self.wallet(character_id)["coins"])

    def bag(self):
        return {item["slot_index"]: item for item in self.items.get_inventory(self.character_id)}

    def item_quantity(self, item_id):
        return sum(
            item["quantity"] for item in self.items.get_inventory(self.character_id)
            if item["item_id"] == item_id
        )

    def fill_backpack(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE))
        self.assertEqual(len(self.bag()), BACKPACK_SIZE)

    def count_rows(self, table):
        with self.database.connection() as connection:
            return connection.execute(f"SELECT COUNT(*) AS amount FROM {table}").fetchone()["amount"]


class CatalogTests(ItemsTestCase):
    def test_catalog_is_seeded_and_reseeding_restores_code_values(self):
        with self.database.connection() as connection:
            ids = {row["id"] for row in connection.execute("SELECT id FROM items_catalog").fetchall()}
            connection.execute("UPDATE items_catalog SET price = 1, name = 'Испорчено' WHERE id = 4")
        self.assertEqual(ids, {entry[0] for entry in CATALOG})

        ItemsDatabase(self.database)

        with self.database.connection() as connection:
            row = connection.execute("SELECT name, price FROM items_catalog WHERE id = 4").fetchone()
        self.assertEqual((row["name"], row["price"]), ("Зелье восстановления здоровья", 15))

    def test_supplies_and_dungeon_loot_items_are_kept(self):
        ids = {entry[0] for entry in CATALOG}
        self.assertTrue({4, 5, 6, 52, 901, 902, 903, 904, 905, 906} <= ids)
        self.assertEqual(set(SUPPLIES_SHOP_ITEM_IDS), {4, 5, 6, 52})

    def test_catalog_prices_are_integer_coins(self):
        for entry in CATALOG:
            self.assertIsInstance(entry[5], int, entry[1])
        prices = {entry[0]: entry[5] for entry in CATALOG}
        self.assertEqual(
            {item_id: prices[item_id] for item_id in (60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 10, 71, 72)},
            {60: 20, 61: 80, 62: 15, 63: 10, 64: 60, 65: 200, 66: 30, 67: 20, 68: 30, 69: 30, 10: 50, 71: 2000, 72: 50000},
        )
        self.assertEqual(format_coins(prices[71]), "2000 монет")

    def test_wooden_staff_requirements_reach_the_database(self):
        staff = next(entry for entry in CATALOG if entry[0] == 25)
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT description, effects_json FROM items_catalog WHERE id = 25"
            ).fetchone()
        self.assertEqual(row["description"], staff[6])
        self.assertEqual(json.loads(row["effects_json"])["requirements"], {"wisdom": 6, "intellect": 4})

    def test_list_catalog_items_returns_every_item_as_client_payload(self):
        with self.database.connection() as connection:
            connection.execute(
                """INSERT INTO items_catalog (id, name, item_type, rarity, weight, price, created_at)
                   VALUES (500, 'Редкая находка', 'material', 'common', 1, 7, 0)"""
            )

        items = self.items.list_catalog_items()

        ids = [item["id"] for item in items]
        self.assertEqual(ids, sorted({entry[0] for entry in CATALOG} | {500}))
        for item in items:
            for key in ("id", "name", "item_type", "rarity", "weight", "price", "description",
                        "can_use", "effects", "bonuses", "icon", "equip_slot"):
                self.assertIn(key, item)
            self.assertIsInstance(item["can_use"], bool)
            self.assertIsInstance(item["effects"], dict)
            self.assertIsInstance(item["bonuses"], dict)
            self.assertIsInstance(item["price"], int)
        by_id = {item["id"]: item for item in items}
        self.assertEqual(by_id[2]["can_use"], True)
        self.assertEqual(by_id[2]["effects"], {"type": "hp", "value": 50})
        self.assertEqual(by_id[4]["can_use"], False)
        self.assertEqual(by_id[4]["price"], 15)
        sword = by_id[20]
        self.assertEqual((sword["item_type"], sword["equip_slot"], sword["price"]), ("equipment", "weapon", 1500000))
        self.assertEqual((sword["effects"], sword["bonuses"]), ({"damage": [5, 7]}, {"strength": 1}))
        self.assertEqual(by_id[500]["effects"], {})
        json.dumps(items)

    def test_get_catalog_items_returns_requested_items_by_string_id(self):
        result = self.items.get_catalog_items([23, "90", 23, 999999])

        self.assertEqual(set(result), {"23", "90"})
        self.assertEqual(result["23"]["id"], 23)
        self.assertEqual(result["23"]["name"], "Дубина")
        self.assertEqual(result["23"]["bonuses"], {"hp": 20})
        self.assertTrue(result["90"]["effects"]["two_handed"])
        self.assertIs(result["90"]["can_use"], False)
        self.assertEqual(self.items.get_catalog_items([]), {})


class InventoryTests(ItemsTestCase):
    def test_base_equipment_grant_is_idempotent(self):
        self.assertTrue(self.items.grant_base_equipment(self.character_id))
        self.assertFalse(self.items.grant_base_equipment(self.character_id))
        self.assertEqual({item["item_id"] for item in self.items.get_inventory(self.character_id)}, {90, 91, 92, 93})

    def test_base_equipment_grant_needs_free_slots_and_is_not_marked_when_it_fails(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE - 3))
        with self.assertRaisesRegex(ValueError, "недостаточно места"):
            self.items.grant_base_equipment(self.character_id)
        self.assertEqual(self.count_rows("character_item_grants"), 0)
        self.items.drop_from_slot(self.character_id, 0)
        self.assertTrue(self.items.grant_base_equipment(self.character_id))

    def test_potions_stack_and_equipment_does_not(self):
        self.items.add_to_inventory(self.character_id, 2, MAX_STACK + 5)
        self.items.add_to_inventory(self.character_id, 20, 2)
        quantities = sorted((item["item_id"], item["quantity"]) for item in self.bag().values())
        self.assertEqual(quantities, [(2, 5), (2, MAX_STACK), (20, 1), (20, 1)])

    def test_wood_stacks_are_limited_to_ten(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 60, 90))
        self.assertEqual(sorted(item["quantity"] for item in self.bag().values()), [10] * 9)

    def test_full_backpack_rejects_new_items_without_partial_add(self):
        self.fill_backpack()
        self.assertFalse(self.items.add_to_inventory(self.character_id, 2, 1))
        self.assertEqual(len(self.bag()), BACKPACK_SIZE)

    def test_add_rejects_unknown_item_and_non_positive_quantity(self):
        self.assertFalse(self.items.add_to_inventory(self.character_id, 999999, 1))
        self.assertFalse(self.items.add_to_inventory(self.character_id, 2, 0))
        self.assertEqual(self.bag(), {})

    def test_remove_from_inventory_takes_requested_quantity_and_rejects_missing(self):
        self.items.add_to_inventory(self.character_id, 60, 10)
        self.assertTrue(self.items.remove_from_inventory(self.character_id, 60, 3))
        self.assertEqual(self.item_quantity(60), 7)
        self.assertFalse(self.items.remove_from_inventory(self.character_id, 60, 8))
        self.assertFalse(self.items.remove_from_inventory(self.character_id, 60, 0))
        self.assertEqual(self.item_quantity(60), 7)

    def test_drop_from_slot_validates_cell_and_quantity(self):
        self.items.add_to_inventory(self.character_id, 2, 5)
        self.assertTrue(self.items.drop_from_slot(self.character_id, 0, 2))
        self.assertEqual(self.bag()[0]["quantity"], 3)
        for quantity in (0, -1):
            with self.assertRaises(ValueError):
                self.items.drop_from_slot(self.character_id, 0, quantity)
        with self.assertRaises(ValueError):
            self.items.drop_from_slot(self.character_id, 5)
        with self.assertRaises(ValueError):
            self.items.drop_from_slot(self.character_id, BACKPACK_SIZE)
        self.assertEqual(self.bag()[0]["quantity"], 3)
        self.assertTrue(self.items.drop_from_slot(self.character_id, 0))
        self.assertEqual(self.bag(), {})

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
                "INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at) VALUES (%s, 2, 4, 9, 0)",
                (self.character_id,),
            )
        self.items.move_item(self.character_id, 9, 0)
        bag = self.bag()
        self.assertEqual(bag[0]["quantity"], 7)
        self.assertNotIn(9, bag)

    def test_inventory_state_keeps_equipment_and_inventory_separate(self):
        self.assertTrue(self.items.grant_base_equipment(self.character_id))
        inventory = self.items.get_inventory(self.character_id)
        self.assertEqual(len(inventory), 4)

        self.items.equip_item(self.character_id, inventory[0]["slot_index"])
        state = self.items.get_inventory_state(self.character_id)

        self.assertEqual(set(state), {"inventory", "equipment", "bonuses", "capacity"})
        self.assertEqual(state["capacity"], BACKPACK_SIZE)
        self.assertEqual(state["bonuses"], {})
        self.assertEqual(len(state["inventory"]), 3)
        self.assertEqual(set(state["equipment"]), {"weapon", "shield"})
        self.assertTrue(state["equipment"]["shield"].get("_two_handed_shadow"))
        for item in state["inventory"]:
            for key in ("slot_index", "item_id", "quantity", "name", "rarity", "icon", "effects", "bonuses"):
                self.assertIn(key, item)
        json.dumps(state)

    def test_health_potion_heals_and_is_consumed(self):
        character = self.database.get_character(self.user_id, self.character_id)
        self.database.save_character(self.user_id, self.character_id, {**character, "hp": 10})
        self.items.add_to_inventory(self.character_id, 2, 2)
        updated = self.items.use_item(self.user_id, self.character_id, 0)
        self.assertEqual(updated["hp"], min(60, updated["max_hp"]))
        self.assertEqual(self.bag()[0]["quantity"], 1)

    def test_mana_potion_restores_mana(self):
        character = self.database.get_character(self.user_id, self.character_id)
        self.database.save_character(self.user_id, self.character_id, {**character, "mp": 0})
        self.items.add_to_inventory(self.character_id, 1, 1)
        updated = self.items.use_item(self.user_id, self.character_id, 0)
        self.assertEqual(updated["mp"], min(50, updated["max_mp"]))
        self.assertEqual(self.bag(), {})

    def test_potion_is_not_wasted_at_full_health_and_battle_items_are_not_usable(self):
        self.items.add_to_inventory(self.character_id, 2, 1)
        self.items.add_to_inventory(self.character_id, 4, 1)
        with self.assertRaises(ValueError):
            self.items.use_item(self.user_id, self.character_id, 0)
        with self.assertRaisesRegex(ValueError, "нельзя использовать"):
            self.items.use_item(self.user_id, self.character_id, 1)
        with self.assertRaisesRegex(ValueError, "пуста"):
            self.items.use_item(self.user_id, self.character_id, 2)
        self.assertEqual({slot: item["quantity"] for slot, item in self.bag().items()}, {0: 1, 1: 1})


class EquipmentTests(ItemsTestCase):
    def test_equip_swaps_previous_item_into_same_cell(self):
        self.items.add_to_inventory(self.character_id, 20, 1)  # железный меч, ячейка 0
        self.items.add_to_inventory(self.character_id, 21, 1)  # стальной меч, ячейка 1
        self.items.equip_item(self.character_id, 0)
        self.items.equip_item(self.character_id, 1, "weapon")
        self.assertEqual(self.items.get_equipment(self.character_id)["weapon"]["item_id"], 21)
        self.assertEqual(self.bag()[1]["item_id"], 20)
        self.assertEqual(self.items.get_stat_bonuses(self.character_id), {"strength": 2, "intuition": 1})

    def test_two_handed_item_fills_and_locks_both_hands(self):
        self.items.add_to_inventory(self.character_id, 90, 1)
        self.items.add_to_inventory(self.character_id, 38, 1)

        self.items.equip_item(self.character_id, 0, "shield")
        equipment = self.items.get_equipment(self.character_id)
        self.assertEqual(equipment["weapon"]["item_id"], 90)
        self.assertEqual(equipment["shield"]["item_id"], 90)
        self.assertTrue(equipment["shield"]["_two_handed_shadow"])
        with self.assertRaisesRegex(ValueError, "двуручным предметом"):
            self.items.equip_item(self.character_id, 1, "shield")
        self.assertEqual(self.bag()[1]["item_id"], 38)

        self.items.unequip_item(self.character_id, "shield")
        self.assertEqual(self.items.get_equipment(self.character_id), {})
        self.assertEqual(sorted(item["item_id"] for item in self.bag().values()), [38, 90])

    def test_ring_can_be_equipped_in_both_ring_slots(self):
        self.items.add_to_inventory(self.character_id, 40, 1)
        self.items.add_to_inventory(self.character_id, 40, 1)
        slots = sorted(self.bag())
        self.items.equip_item(self.character_id, slots[0], "ring")
        self.items.equip_item(self.character_id, slots[1], "ring_2")
        self.assertEqual(set(self.items.get_equipment(self.character_id)), {"ring", "ring_2"})

    def test_equip_rejects_wrong_slot_and_non_equipment(self):
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.add_to_inventory(self.character_id, 2, 1)
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 0, "head")
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 1)
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 49)
        self.assertEqual(self.items.get_equipment(self.character_id), {})

    def test_archer_can_only_equip_allowed_items(self):
        _, archer_id = self.another_character("archer-user", "Лучник", "archer")
        self.items.add_to_inventory(archer_id, 23, 1)  # дубина
        self.items.add_to_inventory(archer_id, 24, 1)  # простой лук
        with self.assertRaisesRegex(ValueError, "недоступен для лучника"):
            self.items.equip_item(archer_id, 0)
        self.assertTrue(self.items.equip_item(archer_id, 1))
        self.assertEqual(self.items.get_equipment(archer_id)["weapon"]["item_id"], 24)

    def test_unequip_to_chosen_cell_and_full_backpack(self):
        self.items.add_to_inventory(self.character_id, 32, 1)
        self.items.equip_item(self.character_id, 0)
        self.items.unequip_item(self.character_id, "head", target_slot=12)
        self.assertEqual(self.bag()[12]["item_id"], 32)

        self.items.equip_item(self.character_id, 12)
        self.fill_backpack()
        with self.assertRaises(ValueError):
            self.items.unequip_item(self.character_id, "head")
        self.assertIn("head", self.items.get_equipment(self.character_id))
        with self.assertRaisesRegex(ValueError, "Слот пуст"):
            self.items.unequip_item(self.character_id, "feet")

    def test_character_payload_carries_equipment_bonuses(self):
        self.items.add_to_inventory(self.character_id, 31, 1)  # боевой доспех: выносливость +2
        self.items.equip_item(self.character_id, 0)
        character = self.database.get_character(self.user_id, self.character_id)
        self.assertEqual(character["equipment_bonuses"], {"endurance": 2})
        self.assertEqual(character["equipment"]["body"]["item_id"], 31)
        battle = self.database.get_character_for_battle(self.character_id)["character"]
        self.assertEqual(battle["equipment_bonuses"], {"endurance": 2})


class StorageTests(ItemsTestCase):
    def test_storage_stacks_items_per_chest_and_removes_them(self):
        self.assertTrue(self.items.add_to_storage(self.character_id, "chest1", 60, 5))
        self.assertTrue(self.items.add_to_storage(self.character_id, "chest1", 60, 3))
        self.assertTrue(self.items.add_to_storage(self.character_id, "chest1", 10, 1))
        self.assertTrue(self.items.add_to_storage(self.character_id, "chest2", 60, 2))

        chest = self.items.get_storage(self.character_id, "chest1")
        self.assertEqual({row["item_id"]: row["quantity"] for row in chest}, {60: 8, 10: 1})
        self.assertEqual([row["slot_index"] for row in chest], [0, 1])
        self.assertEqual(chest[0]["name"], "Древесина")
        self.assertEqual(self.items.get_storage(self.character_id, "chest2")[0]["quantity"], 2)

        self.assertTrue(self.items.remove_from_storage(self.character_id, "chest1", 60, 3))
        self.assertEqual(self.items.get_storage(self.character_id, "chest1")[0]["quantity"], 5)
        self.assertTrue(self.items.remove_from_storage(self.character_id, "chest1", 60, 5))
        self.assertEqual([row["item_id"] for row in self.items.get_storage(self.character_id, "chest1")], [10])
        self.assertFalse(self.items.remove_from_storage(self.character_id, "chest1", 60, 1))


class SuppliesShopTests(ItemsTestCase):
    def test_catalog_lists_supplies_with_prices_in_coins(self):
        catalog = self.items.get_supplies_shop_catalog()

        self.assertEqual({item["item_id"]: item["price"] for item in catalog}, SUPPLIES_PRICES)
        for item in catalog:
            for key in ("name", "description", "item_type", "rarity", "weight", "effects", "icon"):
                self.assertIn(key, item)
            self.assertNotIn("price_coins", item)
        json.dumps(catalog)

    def test_purchase_debits_coins_and_adds_item(self):
        self.assertEqual(self.balance(), STARTING_COINS)

        result = self.items.buy_supplies_item(self.user_id, self.character_id, 4)
        self.assertEqual(result["character"]["coins"], STARTING_COINS - 15)
        self.assertEqual(
            next(item["quantity"] for item in result["inventory"]["inventory"] if item["item_id"] == 4), 1
        )
        result = self.items.buy_supplies_item(self.user_id, self.character_id, 6)
        self.assertEqual(result["character"]["coins"], STARTING_COINS - 20)
        result = self.items.buy_supplies_item(self.user_id, self.character_id, 4)
        self.assertEqual(result["character"]["coins"], STARTING_COINS - 35)
        self.assertEqual(self.item_quantity(4), 2)

        self.items.buy_supplies_item(self.user_id, self.character_id, 52)
        self.assertEqual(self.balance(), STARTING_COINS - 95)
        with self.assertRaisesRegex(ValueError, "Недостаточно денег"):
            self.items.buy_supplies_item(self.user_id, self.character_id, 52)
        self.assertEqual(self.balance(), STARTING_COINS - 95)
        self.assertEqual(self.item_quantity(52), 1)

    def test_failed_purchase_changes_nothing(self):
        for item_id in (2, 999999):
            with self.assertRaisesRegex(ValueError, "нет в магазине припасов"):
                self.items.buy_supplies_item(self.user_id, self.character_id, item_id)

        self.fill_backpack()
        with self.assertRaisesRegex(ValueError, "нет свободного места"):
            self.items.buy_supplies_item(self.user_id, self.character_id, 4)

        other_user_id, other_character_id = self.another_character()
        with self.assertRaisesRegex(ValueError, "Персонаж не найден"):
            self.items.buy_supplies_item(other_user_id, self.character_id, 4)
        self.assertEqual(self.balance(), STARTING_COINS)
        self.assertEqual(self.balance(other_character_id), STARTING_COINS)
        self.assertEqual(self.item_quantity(4), 0)


class CardShopCatalogTests(ItemsTestCase):
    def test_catalogs_split_universal_cards_between_city_and_dungeon(self):
        city = {card["key"] for card in self.items.get_card_shop_catalog()}
        dungeon = {card["key"] for card in self.items.get_dungeon_card_shop_catalog()}

        self.assertEqual(dungeon, set(DUNGEON_CARD_KEYS))
        self.assertFalse(city & dungeon)
        self.assertEqual(city | dungeon, {card.key for card in UNIVERSAL_CARDS})

    def test_price_is_price_coins(self):
        cards = {card.key: card for card in UNIVERSAL_CARDS}
        entries = self.items.get_card_shop_catalog() + self.items.get_dungeon_card_shop_catalog()

        for entry in entries:
            card = cards[entry["key"]]
            self.assertEqual(entry["price"], card.price_coins, card.key)
            self.assertEqual(entry["available"], entry["price"] > 0 and card.rarity != "unassigned", card.key)
            for key in ("name", "effect_data", "resource_cost", "rarity", "price_coins", "sale_price_coins"):
                self.assertIn(key, entry)
        json.dumps(entries)

    def test_prices_come_from_price_coins(self):
        cards = priced_cards(
            universal_trap=dict(price_coins=300, rarity="common"),
            universal_wolf=dict(price_coins=150, rarity="rare"),
            universal_dash=dict(price_coins=0, rarity="common"),
        )
        with patch(CARDS_MODULE, cards):
            catalog = {card["key"]: card for card in self.items.get_card_shop_catalog()}

        self.assertEqual(catalog["universal_trap"]["price"], 300)
        self.assertTrue(catalog["universal_trap"]["available"])
        self.assertEqual(catalog["universal_wolf"]["price"], 150)
        self.assertEqual(catalog["universal_dash"]["price"], 0)
        self.assertFalse(catalog["universal_dash"]["available"])
        self.assertEqual(card_price_coins(next(card for card in cards if card.key == "universal_trap")), 300)

    def test_real_catalog_purchase_spends_the_catalog_price(self):
        available = [card for card in self.items.get_card_shop_catalog() if card["available"]]
        self.assertTrue(available, "в лавке нет ни одной карты с ценой")
        card = available[0]
        self.set_wallet(coins=1000000)

        result = self.items.buy_card(self.user_id, self.character_id, card["key"])

        self.assertEqual(result["card"]["key"], card["key"])
        self.assertEqual(self.balance(), 1000000 - card["price"])
        self.assertEqual(self.database.get_card_collection(self.character_id)[0]["card_key"], card["key"])


class CardPurchaseTests(ItemsTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch(CARDS_MODULE, priced_cards(
            universal_trap=dict(price_coins=300, rarity="common"),
            universal_dash=dict(price_coins=0, rarity="common"),
            universal_bonebreaker=dict(price_coins=400, rarity="rare"),
        )))

    def collection(self, character_id=None):
        return {
            entry["card_key"]: entry
            for entry in self.database.get_card_collection(character_id or self.character_id)
        }

    def test_purchase_deducts_coins_and_merges_copies_into_one_collection_slot(self):
        self.set_wallet(coins=1000)

        result = self.items.buy_card(self.user_id, self.character_id, "universal_trap")

        self.assertEqual(result["card"]["key"], "universal_trap")
        self.assertEqual(result["character"]["coins"], 700)
        entry = self.collection()["universal_trap"]
        self.assertEqual(entry["quantity"], 1)

        again = self.items.buy_card(self.user_id, self.character_id, "universal_trap")

        self.assertEqual(again["character"]["coins"], 400)
        merged = self.collection()
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged["universal_trap"]["quantity"], 2)
        self.assertEqual(merged["universal_trap"]["slot_index"], entry["slot_index"])

    def test_purchase_uses_the_coins_balance_and_never_goes_negative(self):
        self.set_wallet(coins=250)
        with self.assertRaisesRegex(ValueError, "Недостаточно денег"):
            self.items.buy_card(self.user_id, self.character_id, "universal_trap")
        self.assertEqual(self.balance(), 250)
        self.assertEqual(self.collection(), {})

        self.set_wallet(coins=10000)
        result = self.items.buy_card(self.user_id, self.character_id, "universal_trap")

        self.assertEqual(result["character"]["coins"], 9700)

    def test_starting_wallet_is_not_enough_for_a_card(self):
        self.assertEqual(self.balance(), STARTING_COINS)
        with self.assertRaisesRegex(ValueError, "Недостаточно денег"):
            self.items.buy_card(self.user_id, self.character_id, "universal_trap")

    def test_dungeon_cards_are_sold_only_by_the_dungeon_merchant(self):
        self.set_wallet(coins=2000)
        with self.assertRaisesRegex(ValueError, "только в подземелье"):
            self.items.buy_card(self.user_id, self.character_id, "universal_bonebreaker")
        with self.assertRaisesRegex(ValueError, "нет у подземного торговца"):
            self.items.buy_dungeon_card(self.user_id, self.character_id, "universal_trap")
        self.assertEqual(self.balance(), 2000)

        result = self.items.buy_dungeon_card(self.user_id, self.character_id, "universal_bonebreaker")

        self.assertEqual(result["character"]["coins"], 1600)
        self.assertEqual(self.collection()["universal_bonebreaker"]["quantity"], 1)

    def test_unknown_unpriced_and_foreign_purchases_are_rejected_without_charge(self):
        self.set_wallet(coins=2000)
        with self.assertRaisesRegex(ValueError, "нет в карточной лавке"):
            self.items.buy_card(self.user_id, self.character_id, "no_such_card")
        with self.assertRaisesRegex(ValueError, "временно отключена"):
            self.items.buy_card(self.user_id, self.character_id, "universal_dash")
        other_user_id, _ = self.another_character()
        with self.assertRaisesRegex(ValueError, "Персонаж не найден"):
            self.items.buy_card(other_user_id, self.character_id, "universal_trap")
        self.assertEqual(self.balance(), 2000)
        self.assertEqual(self.collection(), {})

    def test_full_collection_rejects_a_new_card_without_charge(self):
        self.set_wallet(coins=2000)
        with self.database.connection() as connection:
            for slot in range(COLLECTION_SLOTS):
                connection.execute(
                    """INSERT INTO character_card_collection
                       (character_id, card_key, quantity, slot_index, acquired_at)
                       VALUES (%s, %s, 1, %s, 0)""",
                    (self.character_id, f"filler_{slot}", slot),
                )

        with self.assertRaisesRegex(ValueError, "нет свободных ячеек"):
            self.items.buy_card(self.user_id, self.character_id, "universal_trap")

        self.assertEqual(self.balance(), 2000)
        self.assertNotIn("universal_trap", self.collection())


class DungeonTreasureTests(ItemsTestCase):
    REQUEST_ID = "bc2fdcb1-5ac5-4630-a1e8-26e3906a57e1"
    REWARDS = {
        "coins": 830,
        "items": [
            {"item_id": 901, "name": "Карта скелета-стража", "quantity": 1},
            {"item_id": 902, "name": "Статуя короля скелетов", "quantity": 1},
            {"item_id": 901, "name": "Карта скелета-стража", "quantity": 2},
            {"item_id": 903, "name": "Копьё скелета-стража", "quantity": 1},
            {"item_id": 904, "name": "Карта короля скелетов", "quantity": 1},
            {"item_id": 905, "name": "Корона короля скелетов", "quantity": 1},
            {"item_id": 906, "name": "Наследие павшего короля", "quantity": 1},
        ],
    }

    def test_reward_rolls_are_independent_and_can_all_drop_together(self):
        class FixedRolls:
            def __init__(self, value):
                self.value = value

            def random(self):
                return self.value

        rewards = roll_dungeon_treasure(FixedRolls(0.0))
        self.assertEqual(rewards["coins"], 830)
        self.assertEqual(
            [(item["item_id"], item["quantity"]) for item in rewards["items"]],
            [(901, 1), (902, 1), (901, 2), (903, 1), (904, 1), (905, 1), (906, 1)],
        )
        self.assertEqual(roll_dungeon_treasure(FixedRolls(0.999)), {"coins": 830, "items": []})

    def test_treasure_is_server_owned_and_idempotent(self):
        with patch(TREASURE_ROLL, return_value=self.REWARDS):
            first = self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)
            retry = self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)

        for result in (first, retry):
            self.assertEqual(result["character"]["coins"], STARTING_COINS + 830)
        self.assertEqual(self.balance(), STARTING_COINS + 830)
        self.assertEqual(first["rewards"], retry["rewards"])
        self.assertEqual(first["rewards"][0], format_coins(830))
        self.assertEqual(first["rewards"][0], "830 монет")
        self.assertEqual(first["rewards"][1], "1 × Карта скелета-стража")
        self.assertEqual(len(first["rewards"]), 1 + len(self.REWARDS["items"]))
        quantities = {item["item_id"]: item["quantity"] for item in first["inventory"]["inventory"]}
        self.assertEqual(quantities[901], 3)
        self.assertEqual(quantities[902], 1)
        self.assertEqual(quantities[906], 1)
        self.assertEqual(self.item_quantity(901), 3)
        self.assertEqual(self.count_rows("character_dungeon_treasure_claims"), 1)

    def test_every_new_request_opens_a_new_chest(self):
        with patch(TREASURE_ROLL, return_value=self.REWARDS):
            self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)
            self.items.claim_dungeon_treasure(self.user_id, self.character_id, str(uuid.uuid4()))

        self.assertEqual(self.balance(), STARTING_COINS + 2 * 830)
        self.assertEqual(self.item_quantity(901), 6)

    def test_real_roll_pays_the_dungeon_coins(self):
        result = self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)

        self.assertEqual(self.balance(), STARTING_COINS + DUNGEON_TREASURE_COINS)
        self.assertEqual(result["rewards"][0], format_coins(DUNGEON_TREASURE_COINS))

    def test_invalid_request_and_foreign_character_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Неверный идентификатор"):
            self.items.claim_dungeon_treasure(self.user_id, self.character_id, "not-a-uuid")
        with self.assertRaisesRegex(ValueError, "Неверный идентификатор"):
            self.items.claim_dungeon_treasure(self.user_id, self.character_id, None)
        other_user_id, _ = self.another_character()
        with patch(TREASURE_ROLL, return_value=self.REWARDS):
            with self.assertRaisesRegex(ValueError, "Персонаж не найден"):
                self.items.claim_dungeon_treasure(other_user_id, self.character_id, self.REQUEST_ID)
        self.assertEqual(self.balance(), STARTING_COINS)
        self.assertEqual(self.count_rows("character_dungeon_treasure_claims"), 0)

    def test_full_backpack_grants_nothing_and_the_same_request_can_be_retried(self):
        self.fill_backpack()
        with patch(TREASURE_ROLL, return_value=self.REWARDS):
            with self.assertRaisesRegex(ValueError, "недостаточно места"):
                self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)
            self.assertEqual(self.balance(), STARTING_COINS)
            self.assertEqual(self.count_rows("character_dungeon_treasure_claims"), 0)

            for slot in range(BACKPACK_SIZE):
                self.items.drop_from_slot(self.character_id, slot)
            self.items.claim_dungeon_treasure(self.user_id, self.character_id, self.REQUEST_ID)

        self.assertEqual(self.balance(), STARTING_COINS + 830)
        self.assertEqual(self.item_quantity(906), 1)


class DeckTests(ItemsTestCase):
    def test_decks_round_trip_and_only_one_is_active(self):
        first_id = self.items.create_deck(self.character_id, "Первая", {"card_a": 2, "card_b": 1})
        second_id = self.items.create_deck(self.character_id, "Вторая", {"card_c": 1})

        first = self.items.get_deck(first_id)
        self.assertEqual((first["name"], first["cards"], first["is_active"]), ("Первая", {"card_a": 2, "card_b": 1}, False))
        self.assertIn("created_at", first)
        self.assertEqual([deck["id"] for deck in self.items.get_decks(self.character_id)], [first_id, second_id])
        self.assertIsNone(self.items.get_active_deck(self.character_id))

        self.assertTrue(self.items.set_active_deck(self.character_id, second_id))
        self.assertEqual(self.items.get_active_deck(self.character_id)["cards"], {"card_c": 1})
        self.assertTrue(self.items.set_active_deck(self.character_id, first_id))
        self.assertEqual(
            {deck["id"]: deck["is_active"] for deck in self.items.get_decks(self.character_id)},
            {first_id: True, second_id: False},
        )
        self.assertEqual(self.items.get_active_deck(self.character_id)["id"], first_id)

        self.assertFalse(self.items.set_active_deck(self.character_id, 10 ** 9))
        self.assertEqual(self.items.get_active_deck(self.character_id)["id"], first_id)
        self.assertIsNone(self.items.get_deck(10 ** 9))

    def test_decks_are_private_to_their_character(self):
        deck_id = self.items.create_deck(self.character_id, "Моя", {"card_a": 1})
        _, other_character_id = self.another_character()

        self.assertEqual(self.items.get_decks(other_character_id), [])
        self.assertFalse(self.items.set_active_deck(other_character_id, deck_id))
        self.assertFalse(self.items.delete_deck(other_character_id, deck_id))
        self.assertEqual(len(self.items.get_decks(self.character_id)), 1)

        self.assertTrue(self.items.delete_deck(self.character_id, deck_id))
        self.assertFalse(self.items.delete_deck(self.character_id, deck_id))
        self.assertEqual(self.items.get_decks(self.character_id), [])


class RewardWalletTests(ItemsTestCase):
    """Награды самой базы (гильдия, бой, опыт) идут в единый кошелёк монет."""

    def test_guild_quest_reward_is_claimed_once_and_idempotent(self):
        user_id, character_id = self.user_id, self.character_id

        _, first_reward, first_claimed = self.database.claim_guild_quest_reward(
            user_id, character_id, "kill_kobold", "quest-completion-1"
        )
        retry, retry_reward, retry_claimed = self.database.claim_guild_quest_reward(
            user_id, character_id, "kill_kobold", "quest-completion-1"
        )
        _, duplicate_reward, duplicate_claimed = self.database.claim_guild_quest_reward(
            user_id, character_id, "kill_kobold", "quest-completion-2"
        )

        self.assertEqual((first_reward, first_claimed), (10, False))
        self.assertEqual((retry_reward, retry_claimed), (10, False))
        self.assertEqual(retry["coins"], STARTING_COINS + 10)
        self.assertEqual((duplicate_reward, duplicate_claimed), (0, True))
        self.assertEqual(self.balance(), STARTING_COINS + 10)

    def test_wallet_is_a_single_coins_value(self):
        _, reward, _ = self.database.claim_guild_quest_reward(
            self.user_id, self.character_id, "kill_kobold", "wallet-quest-completion"
        )

        character = self.database.get_character(self.user_id, self.character_id)
        self.assertEqual(reward, 10)
        self.assertEqual(character["coins"], STARTING_COINS + 10)
        self.assertIsInstance(character["coins"], int)

    def test_guild_ent_and_dungeon_rewards_are_paid_in_coins(self):
        for quest_id, request_id, expected in (
            ("kill_ancient_ent", "ent-quest-completion", 160),
            ("clear_dungeon", "dungeon-quest-completion", 780),
        ):
            _, reward, _ = self.database.claim_guild_quest_reward(
                self.user_id, self.character_id, quest_id, request_id
            )
            self.assertEqual(reward, expected)
        self.assertEqual(self.balance(), STARTING_COINS + 160 + 780)

    def test_battle_result_pays_xp_but_no_currency(self):
        result = self.database.report_battle_result(
            self.user_id, self.character_id, "win", 1, 5, 0, str(uuid.uuid4())
        )

        self.assertGreater(result["xp"], 0)
        self.assertEqual(result["currency"], {"coins": 0})
        self.assertEqual(self.balance(), STARTING_COINS)

    def test_npc_kill_xp_uses_server_rewards_and_is_idempotent(self):
        request_id = "dbe82a31-8408-4500-a8a7-7100248da512"
        first = self.database.report_npc_kill_xp(
            self.user_id, self.character_id, "dungeon_room_3", ["skeleton", "necromancer"], request_id
        )
        with self.assertRaisesRegex(ValueError, "уже начислен"):
            self.database.report_npc_kill_xp(
                self.user_id, self.character_id, "dungeon_room_3", ["skeleton", "necromancer"], request_id
            )

        self.assertEqual(first["xp"], 55)
        self.assertEqual(first["levels_gained"], 1)
        self.assertEqual(first["character"]["level"], 2)
        self.assertEqual(first["character"]["xp"], 35)
        self.assertEqual(self.balance(), STARTING_COINS)


if __name__ == "__main__":
    unittest.main()
