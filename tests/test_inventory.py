import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pygame

from client.network import ServerError
from combat.fighter import Fighter
from core.currency import Currency
from server.main import GameRequestHandler
from tests.fixtures import create_test_database, drop_test_database, running_server
from server.items_database import BACKPACK_SIZE, CATALOG, MAX_STACK, ItemsDatabase
from ui.catalog_icons import BUILDING_ICON_KEYS
from ui.inventory_window import format_item_price
from ui.equipment_slots import SLOT_LABELS, SLOT_OPACITY, slot_rects


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.items = ItemsDatabase(self.database)
        user = self.database.register("tester", "password")
        self.user_id = user["id"]
        self.character_id = self.database.create_character(self.user_id, "Воин")["id"]

    def tearDown(self):
        drop_test_database(self.database)

    def bag(self):
        return {item["slot_index"]: item for item in self.items.get_inventory(self.character_id)}

    def set_strength(self, strength):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET stats_json = %s WHERE id = %s",
                (json.dumps({"strength": strength, "agility": 3, "intuition": 3,
                             "wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 3}),
                 self.character_id),
            )

    def test_base_equipment_grant_is_idempotent(self):
        self.assertFalse(self.items.grant_base_equipment(self.character_id))
        self.assertFalse(self.items.grant_base_equipment(self.character_id))
        self.assertEqual(self.items.get_inventory(self.character_id), [])

    def test_supplies_shop_purchase_debits_currency_and_adds_item(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET coins = 300 WHERE id = %s",
                (self.character_id,),
            )

        catalog = self.items.get_supplies_shop_catalog()
        self.assertEqual({item["item_id"] for item in catalog}, {4, 5, 6, 7, 52})
        result = self.items.buy_supplies_item(self.user_id, self.character_id, 4)
        self.assertEqual(result["character"]["coins"], 285)
        self.assertEqual(
            next(item["quantity"] for item in result["inventory"]["inventory"] if item["item_id"] == 4),
            1,
        )

        result = self.items.buy_supplies_item(self.user_id, self.character_id, 6)
        self.assertEqual(result["character"]["coins"], 280)
        result = self.items.buy_supplies_item(self.user_id, self.character_id, 7)
        self.assertEqual(result["character"]["coins"], 235)
        self.assertEqual(
            next(item["quantity"] for item in result["inventory"]["inventory"] if item["item_id"] == 7),
            1,
        )

    def test_regeneration_potion_is_available_for_45_coins(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET coins = 45 WHERE id = %s",
                (self.character_id,),
            )

        result = self.items.buy_supplies_item(self.user_id, self.character_id, 7)

        self.assertEqual(result["character"]["coins"], 0)
        potion = next(
            item for item in result["inventory"]["inventory"]
            if item["item_id"] == 7
        )
        self.assertEqual(potion["quantity"], 1)
        self.assertEqual(potion["effects"]["heal_per_turn"], 6)
        self.assertEqual(potion["effects"]["duration"], 5)

    def test_supplies_shop_client_api_round_trip(self):
        character = self.database.get_character(self.user_id, self.character_id)
        self.database.save_character(self.user_id, self.character_id, {
            **character, "copper": 0, "silver": 2, "gold": 0,
        })
        with patch.object(GameRequestHandler, "items_database", self.items):
            with running_server(self.database) as client:
                client.login("tester", "password")
                catalog = client.get_supplies_shop_catalog()
                self.assertEqual({item["item_id"] for item in catalog}, {4, 5, 6, 7, 52})
                result = client.buy_supplies_item(self.character_id, 52)

        self.assertEqual(result["character"]["silver"], 0)
        self.assertEqual(result["character"]["copper"], 0)
        self.assertIn(
            52,
            {item["item_id"] for item in result["inventory"]["inventory"]},
        )

    def test_equipment_migration_replaces_old_gear_and_keeps_materials(self):
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.equip_item(self.character_id, 0)
        self.items.add_to_inventory(self.character_id, 30, 1)
        self.items.add_to_inventory(self.character_id, 60, 3)

        migration = Path(__file__).resolve().parents[1] / "server" / "migrations" / "0016_reset_character_equipment_to_gathering_kit.sql"
        with self.database.connection() as connection:
            connection.execute(migration.read_text(encoding="utf-8"))

        self.assertEqual(self.items.get_equipment(self.character_id), {})
        items = self.items.get_inventory(self.character_id)
        self.assertEqual({item["item_id"] for item in items}, {60, 90, 91, 92, 93})
        self.assertEqual(next(item["quantity"] for item in items if item["item_id"] == 60), 3)

    def test_simplified_equipment_migration_keeps_hands_and_returns_removed_slots(self):
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.add_to_inventory(self.character_id, 40, 1)
        self.items.add_to_inventory(self.character_id, 90, 1)
        with self.database.connection() as connection:
            connection.execute(
                "DELETE FROM character_items WHERE character_id = %s",
                (self.character_id,),
            )
            connection.execute(
                """INSERT INTO character_equipment (character_id, slot, item_id, equipped_at)
                   VALUES (%s, 'weapon', 20, 1), (%s, 'ring', 40, 2), (%s, 'shield', 90, 3)""",
                (self.character_id, self.character_id, self.character_id),
            )

        migration = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "migrations"
            / "0055_simplify_equipment_slots.sql"
        )
        with self.database.connection() as connection:
            connection.execute(migration.read_text(encoding="utf-8"))

        equipment = self.items.get_equipment(self.character_id)
        inventory = self.items.get_inventory(self.character_id)
        self.assertEqual(equipment["hands"]["item_id"], 20)
        self.assertEqual([item["item_id"] for item in inventory], [40])

    def test_paperdoll_matches_reference_positions_and_labels(self):
        rects = slot_rects((5, 10, 440, 1065))
        self.assertEqual(rects["head"].topleft, (192, 348))
        self.assertEqual(rects["body"].topleft, (192, 434))
        self.assertEqual(rects["hands"].topleft, (20, 520))
        self.assertEqual(rects["legs"].y - rects["body"].y, 172)
        self.assertEqual(rects["feet"].y - rects["legs"].y, 86)
        self.assertEqual(rects["artifact"].topleft, (25, 807))
        self.assertEqual(set(rects), {"hands", "head", "body", "legs", "feet", "artifact"})
        self.assertEqual(SLOT_LABELS["hands"], "Руки")
        self.assertEqual(SLOT_LABELS["artifact"], "Артефакт")
        self.assertEqual(SLOT_OPACITY, 65)

        wide_rects = slot_rects((550, 100, 700, 800))
        self.assertFalse(wide_rects["hands"].colliderect(wide_rects["body"]))
        self.assertFalse(wide_rects["artifact"].colliderect(wide_rects["feet"]))

    def test_every_catalog_icon_has_a_valid_png_placeholder(self):
        placeholders = Path(__file__).resolve().parents[1] / "assets" / "fighters" / "equipment" / "placeholders"
        icon_keys = {entry[10] for entry in CATALOG if entry[10]}
        icon_keys.update(BUILDING_ICON_KEYS.values())
        for key in icon_keys:
            with self.subTest(icon=key):
                path = placeholders / f"{key}.png"
                self.assertTrue(path.is_file())
                self.assertTrue(pygame.image.load(str(path)).get_bounding_rect().size != (0, 0))

    def test_material_catalog_prices_and_currency_format(self):
        catalog_prices = {entry[0]: entry[5] for entry in CATALOG}
        prices = {entry[0]: entry[5] for entry in CATALOG if entry[2] == "material"}
        self.assertEqual(catalog_prices[1], 500000)
        self.assertEqual(catalog_prices[20], 1500000)
        self.assertEqual(catalog_prices[50], 2000000)
        self.assertEqual(
            {item_id: prices[item_id] for item_id in (60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 10, 71, 72, 73, 74, 75, 76, 77, 78)},
            {
                60: 20, 61: 80, 62: 15, 63: 10, 64: 60, 65: 200,
                66: 30, 67: 20, 68: 30, 69: 30, 10: 50, 71: 2000,
                72: 50000, 73: 100, 74: 5000, 75: 5000, 76: 10000,
                77: 80, 78: 80,
            },
        )
        self.assertEqual(format_item_price({"item_type": "material", "price": 20}), "20 меди")
        self.assertEqual(format_item_price({"item_type": "material", "price": 2000}), "20 серебра")
        self.assertEqual(format_item_price({"item_type": "material", "price": 50000}), "5 золота")
        self.assertEqual(format_item_price({"item_type": "equipment", "price": 1500000}), "150 золота")
        self.assertEqual(format_item_price({"item_type": "potion", "price": 10001}), "1 золото 1 медь")
        for entry in CATALOG:
            self.assertIsInstance(entry[5], int, entry[1])

    def test_currency_denominations_share_one_copper_balance(self):
        wallet = Currency(copper=10, silver=2, gold=1)
        self.assertEqual(wallet.total_copper(), 10210)
        self.assertEqual(Currency.format_amount(wallet.total_copper()), "1 золото 2 серебра 10 меди")
        self.assertTrue(wallet.subtract_copper_amount(2010))
        self.assertEqual(wallet.to_dict(), {"copper": 0, "silver": 82, "gold": 0})
        self.assertFalse(wallet.subtract_copper_amount(8201))

    def test_potions_stack_and_equipment_does_not(self):
        self.items.add_to_inventory(self.character_id, 2, MAX_STACK + 5)
        self.items.add_to_inventory(self.character_id, 20, 2)
        quantities = sorted((item["item_id"], item["quantity"]) for item in self.bag().values())
        self.assertEqual(quantities, [(2, 5), (2, MAX_STACK), (20, 1), (20, 1)])

    def test_wood_stacks_are_limited_to_ten(self):
        self.set_strength(100)
        self.assertTrue(self.items.add_to_inventory(self.character_id, 60, 90))
        quantities = sorted(item["quantity"] for item in self.bag().values())
        self.assertEqual(quantities, [10] * 9)

    def test_wood_stack_migration_splits_existing_large_stack(self):
        migration = Path(__file__).resolve().parents[1] / "server" / "migrations" / "0021_wood_inventory_stack_limit.sql"
        with self.database.connection() as connection:
            connection.execute(
                """INSERT INTO character_items
                   (character_id, item_id, quantity, slot_index, created_at)
                   VALUES (%s, 60, 90, 0, 0)""",
                (self.character_id,),
            )
            connection.execute(migration.read_text(encoding="utf-8"))

        wood = [item["quantity"] for item in self.items.get_inventory(self.character_id)
                if item["item_id"] == 60]
        self.assertEqual(sum(wood), 90)
        self.assertTrue(all(quantity <= 10 for quantity in wood))

    def test_full_backpack_rejects_new_items_without_partial_add(self):
        self.set_strength(100)
        self.assertTrue(self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE))
        self.assertFalse(self.items.add_to_inventory(self.character_id, 2, 1))
        self.assertEqual(len(self.bag()), BACKPACK_SIZE)

    def test_inventory_allows_items_beyond_old_carry_capacity(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 60, 50))
        inventory = self.items.get_inventory(self.character_id)
        self.assertEqual(sum(row["quantity"] for row in inventory if row["item_id"] == 60), 50)

    def test_inventory_snapshot_refreshes_card_profile_with_full_item_weights(self):
        from types import SimpleNamespace
        from ui.inventory_window import InventoryWindow

        window = InventoryWindow.__new__(InventoryWindow)
        window.session = SimpleNamespace(character={"id": self.character_id, "inventory": {}})
        window.inventory = {}
        window.equipment = {}
        window.bonuses = {}
        window.capacity = BACKPACK_SIZE
        window.selected = None
        window._apply_state({
            "inventory": [{"slot_index": 0, "item_id": 60, "name": "Древесина",
                            "weight": 4.0, "quantity": 2}],
            "equipment": {"weapon": {"item_id": 90, "weight": 1.0}},
            "bonuses": {},
            "capacity": BACKPACK_SIZE,
            "carried_weight_kg": 9.0,
        })

        self.assertEqual(window.session.character["inventory"]["0"]["weight"], 4.0)
        self.assertNotIn("carried_weight_kg", window.session.character)

    def test_inventory_state_keeps_equipment_and_inventory_separate(self):
        self.set_strength(100)
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.add_to_inventory(self.character_id, 31, 1)
        self.items.equip_item(self.character_id, 0)
        state = self.items.get_inventory_state(self.character_id)

        self.assertEqual(len(state["inventory"]), 1)
        self.assertEqual(set(state["equipment"]), {"hands"})

    def test_battle_reward_can_be_claimed_beyond_old_carry_capacity(self):
        self.assertTrue(self.items.add_to_inventory(self.character_id, 60, 50))
        reward_id = self.items.add_reward(self.character_id, 60, 1)

        self.assertTrue(self.items.claim_reward(reward_id, self.character_id))
        self.assertEqual(len(self.items.get_rewards(self.character_id)), 0)
        inventory = self.items.get_inventory(self.character_id)
        self.assertEqual(sum(row["quantity"] for row in inventory if row["item_id"] == 60), 51)

    def test_remove_inventory_item_endpoint_decrements_requested_quantity(self):
        self.set_strength(100)
        self.items.add_to_inventory(self.character_id, 60, 10)
        with patch.object(GameRequestHandler, "items_database", self.items):
            with running_server(self.database) as client:
                client.login("tester", "password")
                client.remove_inventory_item(self.character_id, 60, 3)

        wood = [item for item in self.items.get_inventory(self.character_id) if item["item_id"] == 60]
        self.assertEqual(sum(item["quantity"] for item in wood), 7)

    def test_remove_inventory_item_endpoint_rejects_missing_quantity(self):
        self.items.add_to_inventory(self.character_id, 60, 2)
        with patch.object(GameRequestHandler, "items_database", self.items):
            with running_server(self.database) as client:
                client.login("tester", "password")
                with self.assertRaisesRegex(ServerError, "недостаточно предметов"):
                    client.remove_inventory_item(self.character_id, 60, 3)

        wood = [item for item in self.items.get_inventory(self.character_id) if item["item_id"] == 60]
        self.assertEqual(sum(item["quantity"] for item in wood), 2)

    def test_partial_inventory_add_fills_only_available_stack_capacity(self):
        self.set_strength(100)
        self.items.add_to_inventory(self.character_id, 60, 8)
        self.items.add_to_inventory(self.character_id, 20, BACKPACK_SIZE - 1)
        with self.database.connection() as connection:
            added = ItemsDatabase.add_to_inventory_up_to(connection, self.character_id, 60, 20)
        self.assertEqual(added, 2)
        wood = [item for item in self.bag().values() if item["item_id"] == 60]
        self.assertEqual(len(wood), 1)
        self.assertEqual(wood[0]["quantity"], 10)
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
                "INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at) VALUES (%s, 2, 4, 9, 0)",
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
        self.items.equip_item(self.character_id, 1, "hands")
        self.assertEqual(self.items.get_equipment(self.character_id)["hands"]["item_id"], 21)
        self.assertEqual(self.bag()[1]["item_id"], 20)
        self.assertEqual(self.items.get_stat_bonuses(self.character_id), {"strength": 2, "intuition": 1})

    def test_old_weapon_and_shield_slot_names_map_to_hands(self):
        self.items.add_to_inventory(self.character_id, 20, 1)
        self.items.equip_item(self.character_id, 0, "weapon")
        self.assertEqual(set(self.items.get_equipment(self.character_id)), {"hands"})
        self.items.unequip_item(self.character_id, "shield")
        self.assertEqual(self.items.get_equipment(self.character_id), {})

    def test_ring_cannot_be_equipped_in_removed_slots(self):
        self.items.add_to_inventory(self.character_id, 40, 1)
        with self.assertRaises(ValueError):
            self.items.equip_item(self.character_id, 0, "ring")
        self.assertEqual(self.bag()[0]["item_id"], 40)

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
        self.set_strength(100)
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
        self.assertNotIn("carry_capacity_kg", character)
        battle = self.database.get_character_for_battle(self.character_id)["character"]
        self.assertEqual(battle["equipment_bonuses"], {"endurance": 2})
        self.assertNotIn("carry_capacity_kg", battle)

    def test_shield_bonuses_reach_battle_fighter(self):
        from scenes.duel_scene import DuelScene

        self.items.add_to_inventory(self.character_id, 39, 1)
        self.items.equip_item(self.character_id, 0, "shield")
        character = self.database.get_character_for_battle(self.character_id)["character"]
        fighter = Fighter("Щитоносец")

        DuelScene._apply_fighter_profile(fighter, character)

        self.assertEqual(fighter.equipment_stat_modifiers["hp"], 20)
        self.assertEqual(fighter.equipment_stat_modifiers["block"], 5)
        character_without_equipment_bonuses = {
            **character,
            "equipment_bonuses": {},
        }
        base_fighter = Fighter("Щитоносец")
        DuelScene._apply_fighter_profile(base_fighter, character_without_equipment_bonuses)
        self.assertEqual(fighter.max_hp, base_fighter.max_hp + 20)

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
        self.database = create_test_database()
        # running_server подменяет только database; предметы тоже уводим во временную базу
        self.items_patch = patch.object(GameRequestHandler, "items_database", ItemsDatabase(self.database))
        self.items_patch.start()

    def tearDown(self):
        self.items_patch.stop()
        drop_test_database(self.database)

    def test_client_round_trip(self):
        with running_server(self.database) as client:
            client.register("bagowner", "password")
            client.login("bagowner", "password")
            character = client.create_character("Носильщик")
            state = client.get_inventory(character["id"])
            self.assertEqual(state["inventory"], [])
            self.assertEqual(client.get_inventory(character["id"])["inventory"], [])
            self.assertEqual(state["capacity"], BACKPACK_SIZE)

            with self.assertRaises(ServerError):
                client.equip_item(character["id"], 49)

    def test_copper_priced_drink_can_be_paid_from_gold_balance(self):
        with running_server(self.database) as client:
            client.register("drinkbuyer", "password")
            user = client.login("drinkbuyer", "password")
            character = client.create_character("Покупатель")
            saved = self.database.get_character(user["id"], character["id"])
            self.database.save_character(user["id"], character["id"], {
                **saved, "hp": 1, "copper": 0, "silver": 0, "gold": 1,
            })
            drinks = client._request("GET", "/api/drinks", authenticated=True)["drinks"]
            self.assertEqual(drinks[0]["price_copper"], 20)
            result = client._request(
                "POST", "/api/character/buy_drink",
                {"character_id": character["id"], "drink_id": drinks[0]["id"]},
                authenticated=True,
            )
            self.assertEqual(
                (result["character"]["gold"], result["character"]["silver"], result["character"]["copper"]),
                (0, 99, 80),
            )


if __name__ == "__main__":
    unittest.main()
