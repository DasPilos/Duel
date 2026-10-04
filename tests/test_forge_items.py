import unittest
from core.forge_recipes import FORGE_RECIPES, RECIPE_BY_ITEM
from server.database import Database
from server.items_database import ItemsDatabase, CATALOG
from tests.fixtures import create_test_database, drop_test_database


class ForgeItemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = create_test_database()
        cls.items_db = ItemsDatabase(cls.db)

    @classmethod
    def tearDownClass(cls):
        drop_test_database(cls.db)

    def test_catalog_has_all_requested_items(self):
        catalog_map = {item[0]: item for item in CATALOG}
        for item_id in (90, 91, 92, 93, 23, 24, 25, 39):
            self.assertIn(item_id, catalog_map, f"Item {item_id} missing from CATALOG")

    def test_item_recipes_and_durations(self):
        # 12 minutes = 720 sec
        self.assertEqual(RECIPE_BY_ITEM[90]["duration_sec"], 720)
        self.assertEqual(RECIPE_BY_ITEM[90]["materials"], {60: 5})

        self.assertEqual(RECIPE_BY_ITEM[91]["duration_sec"], 720)
        self.assertEqual(RECIPE_BY_ITEM[91]["materials"], {60: 5})

        self.assertEqual(RECIPE_BY_ITEM[92]["duration_sec"], 720)
        self.assertEqual(RECIPE_BY_ITEM[92]["materials"], {60: 5})

        self.assertEqual(RECIPE_BY_ITEM[93]["duration_sec"], 720)
        self.assertEqual(RECIPE_BY_ITEM[93]["materials"], {60: 5})

        # 18 minutes = 1080 sec
        self.assertEqual(RECIPE_BY_ITEM[23]["duration_sec"], 1080)
        self.assertEqual(RECIPE_BY_ITEM[23]["materials"], {60: 5})

        # 16 minutes = 960 sec
        self.assertEqual(RECIPE_BY_ITEM[24]["duration_sec"], 960)
        self.assertEqual(RECIPE_BY_ITEM[24]["materials"], {60: 4})

        # 16 minutes = 960 sec
        self.assertEqual(RECIPE_BY_ITEM[25]["duration_sec"], 960)
        self.assertEqual(RECIPE_BY_ITEM[25]["materials"], {60: 5})

        # 21 minutes = 1260 sec
        self.assertEqual(RECIPE_BY_ITEM[39]["duration_sec"], 1260)
        self.assertEqual(RECIPE_BY_ITEM[39]["materials"], {60: 4})

    def test_item_stats_and_equipment(self):
        user = self.db.register("forge_tester", "password123")
        char = self.db.create_character(user["id"], "ForgeHero")
        char_id = char["id"]

        # Add club (23) and wooden shield (39)
        self.items_db.add_to_inventory(char_id, 23, 1)
        self.items_db.add_to_inventory(char_id, 39, 1)

        # Equip club
        self.items_db.equip_item(char_id, 0, "weapon")
        # Equip shield
        self.items_db.equip_item(char_id, 1, "shield")

        eq = self.items_db.get_equipment(char_id)
        self.assertEqual(eq["weapon"]["item_id"], 23)
        self.assertEqual(eq["shield"]["item_id"], 39)

        bonuses = self.items_db.get_stat_bonuses(char_id)
        # Club +20 HP, Shield +20 HP, +5 block -> HP 40, block 5
        self.assertEqual(bonuses.get("hp"), 40)
        self.assertEqual(bonuses.get("block"), 5)

        # Unequip both
        self.items_db.unequip_item(char_id, "weapon")
        self.items_db.unequip_item(char_id, "shield")

        # Equip bow (24)
        self.items_db.add_to_inventory(char_id, 24, 1)
        # Find bow index
        inv = self.items_db.get_inventory(char_id)
        bow_slot = [it["slot_index"] for it in inv if it["item_id"] == 24][0]
        self.items_db.equip_item(char_id, bow_slot, "weapon")

        eq = self.items_db.get_equipment(char_id)
        self.assertEqual(eq["weapon"]["item_id"], 24)
        self.assertNotIn("shield", eq)

        bonuses = self.items_db.get_stat_bonuses(char_id)
        self.assertEqual(bonuses.get("strength"), 2)
        self.assertEqual(bonuses.get("dodge"), 5)

        # Unequip bow
        self.items_db.unequip_item(char_id, "weapon")

        # Equip staff (25) in weapon slot
        self.items_db.add_to_inventory(char_id, 25, 1)
        inv = self.items_db.get_inventory(char_id)
        staff_slot = [it["slot_index"] for it in inv if it["item_id"] == 25][0]
        self.items_db.equip_item(char_id, staff_slot, "weapon")
        eq = self.items_db.get_equipment(char_id)
        self.assertEqual(eq["weapon"]["item_id"], 25)
        self.assertNotIn("shield", eq)
        bonuses = self.items_db.get_stat_bonuses(char_id)
        self.assertEqual(bonuses.get("mp"), 30)

        # Equip shield (39) in shield slot alongside staff
        self.items_db.add_to_inventory(char_id, 39, 1)
        inv = self.items_db.get_inventory(char_id)
        shield_slot = [it["slot_index"] for it in inv if it["item_id"] == 39][0]
        self.items_db.equip_item(char_id, shield_slot, "shield")
        eq = self.items_db.get_equipment(char_id)
        self.assertEqual(eq["weapon"]["item_id"], 25)
        self.assertEqual(eq["shield"]["item_id"], 39)
        bonuses = self.items_db.get_stat_bonuses(char_id)
        self.assertEqual(bonuses.get("mp"), 30)
        self.assertEqual(bonuses.get("hp"), 20)
        self.assertEqual(bonuses.get("block"), 5)

    def test_forge_order_creation_queue_limit_and_storage(self):
        from server.forge import Forge
        forge = Forge(self.db, self.items_db)

        user1 = self.db.register("blacksmith_fan1", "pass123")
        char1 = self.db.create_character(user1["id"], "SmithHero1")
        c1_id = char1["id"]
        self.db.save_character(user1["id"], c1_id, {**char1, "silver": 50, "copper": 50})

        user2 = self.db.register("blacksmith_fan2", "pass123")
        char2 = self.db.create_character(user2["id"], "SmithHero2")
        c2_id = char2["id"]
        self.db.save_character(user2["id"], c2_id, {**char2, "silver": 50, "copper": 50})

        # Give 30 wood to char1 (item 60)
        self.items_db.add_to_inventory(c1_id, 60, 30)
        # Give 10 wood to char2
        self.items_db.add_to_inventory(c2_id, 60, 10)

        # Order 1: Sickle (90) - takes 5 wood, 720 s
        t0 = 1000.0
        o1 = forge.create_order(c1_id, 90, now=t0)
        state = forge.get_state(c1_id, now=t0)
        self.assertEqual(state["queue_count"], 1)
        self.assertEqual(state["queue"][0]["item_id"], 90)
        self.assertEqual(state["queue"][0]["status"], "working")
        self.assertEqual(state["queue"][0]["seconds_left"], 720)
        self.assertEqual(state["queue_total_seconds"], 720)

        # Order 2: Axe (91) by player 2 - takes 5 wood, 720 s
        o2 = forge.create_order(c2_id, 91, now=t0)
        state = forge.get_state(c1_id, now=t0)
        self.assertEqual(state["queue_count"], 2)
        self.assertEqual(state["queue_total_seconds"], 1440)

        # Order 3, 4, 5 by player 1: Pickaxe (92), Knife (93), Club (23)
        o3 = forge.create_order(c1_id, 92, now=t0)
        o4 = forge.create_order(c1_id, 93, now=t0)
        o5 = forge.create_order(c1_id, 23, now=t0)
        state = forge.get_state(c1_id, now=t0)
        self.assertEqual(state["queue_count"], 5)
        self.assertEqual(state["queue_limit"], 5)

        # Order 6 should be rejected because queue limit is 5
        with self.assertRaisesRegex(ValueError, "Очередь кузницы заполнена"):
            forge.create_order(c1_id, 24, now=t0)

        # Advance time by 720 seconds -> order 1 finishes!
        t1 = t0 + 721.0
        state1 = forge.get_state(c1_id, now=t1)
        # Order 1 should now be in warehouse for char1!
        self.assertEqual(len(state1["warehouse"]), 1)
        self.assertEqual(state1["warehouse"][0]["item_id"], 90)
        self.assertEqual(state1["queue_count"], 4)
        # Order 2 (player 2) should now be working!
        self.assertEqual(state1["queue"][0]["order_id"], o2)
        self.assertEqual(state1["queue"][0]["status"], "working")

        # Player 2 should see 0 warehouse items for themselves (since order 1 belongs to player 1)
        state2 = forge.get_state(c2_id, now=t1)
        self.assertEqual(len(state2["warehouse"]), 0)

        # Player 2 cannot collect player 1's order
        with self.assertRaisesRegex(ValueError, "не найден на вашем складе"):
            forge.collect_order(c2_id, o1, now=t1)

        # Player 1 collects their finished order 1
        forge.collect_order(c1_id, o1, now=t1)
        # Check that player 1 now has sickle in inventory!
        inv1 = self.items_db.get_inventory(c1_id)
        self.assertTrue(any(it["item_id"] == 90 for it in inv1))
        # Warehouse for player 1 is now empty
        state1_after = forge.get_state(c1_id, now=t1)
        self.assertEqual(len(state1_after["warehouse"]), 0)

    def test_forge_ui_modal_rendering_and_popup(self):
        import pygame
        from types import SimpleNamespace
        from core import settings
        from scenes.city_scene import CityScene

        pygame.init()
        screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        fake_session = SimpleNamespace(
            character={"id": 1, "name": "Hero"},
            client=SimpleNamespace(
                get_inventory=lambda cid: {"inventory": [{"item_id": 60, "quantity": 10}]},
                get_forge_state=lambda cid: {"queue": [], "queue_count": 0, "queue_limit": 5, "queue_total_seconds": 0, "warehouse": []},
            ),
            get_forge_state=lambda: {"queue": [], "queue_count": 0, "queue_limit": 5, "queue_total_seconds": 0, "warehouse": []},
        )
        scene = CityScene(fake_session)
        scene._open_forge()

        # Draw forge modal
        scene._draw_forge_modal(screen)

        # Check action buttons registered for recipes (including "card", "info_btn", "craft")
        craft_buttons = [b for b in scene.forge_action_buttons if b[0] == "craft"]
        self.assertTrue(len(craft_buttons) >= 7)

        info_buttons = [b for b in scene.forge_action_buttons if b[0] == "info_btn"]
        self.assertTrue(len(info_buttons) >= 7)

        # Click INFO button for Sickle (90)
        sickle_info_btn = [b for b in info_buttons if b[1] == 90][0]
        scene._handle_forge_click(sickle_info_btn[2].center)
        self.assertEqual(scene.forge_info_popup_item, 90)

        # Draw with popup open
        scene._draw_forge_modal(screen)
        self.assertIsNotNone(scene.forge_popup_rect)
        self.assertIsNotNone(scene.forge_popup_close_btn)

        # Click close on popup
        scene._handle_forge_popup_click(scene.forge_popup_close_btn.center)
        self.assertIsNone(scene.forge_info_popup_item)


if __name__ == "__main__":
    unittest.main()
