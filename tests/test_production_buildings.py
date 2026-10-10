import random
import json
import threading
import unittest

from core.production_buildings import (
    building_resources_for_level,
    slot_resources,
    upgrade_requirements,
)
from server.items_database import ItemsDatabase
from server.production_buildings import (
    STORAGE_RESOURCES_BY_ITEM_ID,
    ProductionBuildings,
    distribute_to_storage,
    _harvest_bonus_for_worker,
    _resource_timer_sec,
)
from tests.fixtures import create_test_database, drop_test_database, running_server


class _Sequence(random.Random):
    """Подставляет заданные значения random() по кругу."""

    def __init__(self, values):
        super().__init__(0)
        self.values, self.index = values, 0

    def random(self):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value


class ProductionBuildingsTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.buildings = ProductionBuildings(self.database)
        with self.database.connection() as connection:
            connection.execute(
                """INSERT INTO city_population_state (world_id, faction, castle_level, last_food_tick_at)
                   VALUES (%s, 'light', 4, 0) ON CONFLICT (world_id, faction)
                   DO UPDATE SET castle_level = 4""",
                (self.database.world_id,),
            )

    def tearDown(self):
        drop_test_database(self.database)

    def _character(self, login="farmer"):
        user = self.database.register(login, "password")
        character_id = self.database.create_character(user["id"], login.title())["id"]
        self._set_strength(character_id, 1000)
        return character_id

    def _set_strength(self, character_id, strength):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET stats_json = %s WHERE id = %s",
                (json.dumps({"strength": strength, "agility": 3, "intuition": 3,
                             "wisdom": 3, "intellect": 3, "harmony": 3, "endurance": 3}),
                 character_id),
            )

    def _equip_gathering_tool(self, character_id, item_id):
        items = ItemsDatabase(self.database)
        items.grant_base_equipment(character_id)
        tool = next(row for row in items.get_inventory(character_id) if row["item_id"] == item_id)
        items.equip_item(character_id, tool["slot_index"])

    def test_storage_resources_follow_building_level_unlocks(self):
        self.assertEqual(building_resources_for_level("farm", 1), ("wheat",))
        self.assertEqual(building_resources_for_level("farm", 3), ("wheat", "flax"))
        self.assertEqual(building_resources_for_level("lumber_camp", 1), ("wood",))
        self.assertEqual(building_resources_for_level("lumber_camp", 3), ("wood", "berries"))
        self.assertEqual(building_resources_for_level("barnyard", 1), ("leather", "meat"))

    def test_farm_storage_payload_hides_future_crop_resources(self):
        character_id = self._character("crop-level")
        farm = self.buildings.get_state(character_id, "farm", 10000)
        self.assertEqual(set(farm["storage"]) - {"limit"}, {"wheat"})

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_states SET level=3 WHERE world_id=%s AND faction='light' AND building='farm'",
                (self.database.world_id,),
            )
        farm = self.buildings.get_state(character_id, "farm", 10001)
        self.assertEqual(set(farm["storage"]) - {"limit"}, {"wheat", "flax"})

    def test_locked_crop_cannot_be_deposited_or_withdrawn(self):
        character_id = self._character("locked-crop")
        items = ItemsDatabase(self.database)
        self.buildings.get_state(character_id, "farm", 10000)
        items.add_to_inventory(character_id, 64, 1)
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            self.buildings.deposit_to_storage(character_id, "farm", "flax", 1, 10001)

        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=1 WHERE world_id=%s AND faction='light'
                   AND building='farm' AND resource='flax'""",
                (self.database.world_id,),
            )
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            self.buildings.withdraw_from_storage(character_id, "farm", "flax", 1, 10002)

    def test_all_gathering_tools_reduce_only_matching_resource_timers(self):
        cases = (
            (90, {"wheat": (140, 112)}),
            (91, {"wood": (240, 192)}),
            (92, {"iron": (300, 240), "coal": (600, 480), "stone": (200, 160)}),
            (93, {"leather": (460, 368), "meat": (680, 544)}),
        )
        for item_id, expected in cases:
            with self.subTest(item_id=item_id):
                character_id = self._character(f"tool-{item_id}")
                self._equip_gathering_tool(character_id, item_id)
                with self.database.connection() as connection:
                    bonuses = _harvest_bonus_for_worker(connection, f"player:{character_id}")
                    self.assertEqual(set(bonuses), set(expected))
                    for resource, (base_timer, reduced_timer) in expected.items():
                        self.assertEqual(bonuses[resource], 20)
                        self.assertEqual(_resource_timer_sec(resource, bonuses), reduced_timer)
                        locations = {
                            "wheat": (("farm", 0),),
                            "wood": (("lumber_camp", 0),),
                            "iron": (("mountain_rift", 2),),
                            "coal": (("black_pit", 0),),
                            "stone": (("mountain_rift", 0),),
                            "leather": (("barnyard", 0),),
                            "meat": (("barnyard", 0),),
                        }
                        self.assertTrue(any(
                            resource in slot_resources(building, slot_index)
                            for building, slot_index in locations[resource]
                        ))

    def test_butcher_knife_shortens_live_leather_and_meat_production(self):
        character_id = self._character("butcher-knife")
        self._equip_gathering_tool(character_id, 93)

        self.buildings.get_state(character_id, "barnyard", 10000)
        state = self.buildings.toggle_player_worker(character_id, "barnyard", 0, 10000)
        slot = state["worker_slots"][0]
        self.assertEqual(slot["harvest_bonus"], {"leather": 20, "meat": 20})
        self.assertEqual(slot["timer_sec_by_resource"], {"leather": 368, "meat": 544})

        state = self.buildings.get_state(character_id, "barnyard", 10368)

        self.assertEqual(state["player_harvest_totals"].get("leather"), 1)
        self.assertIsNone(state["player_harvest_totals"].get("meat"))

    def test_player_harvest_payload_has_no_personal_claims(self):
        character_id = self._character("shared-output")
        state = self.buildings.get_state(character_id, "barnyard", 10000)
        self.assertNotIn("player_harvest_claims", state)

    def test_shared_building_storage_transfers_to_and_from_backpack(self):
        character_id = self._character("storemove")
        items = ItemsDatabase(self.database)
        items.add_to_inventory(character_id, 66, 10)

        state = self.buildings.deposit_to_storage(character_id, "barnyard", "leather", 5, 10000)
        self.assertEqual(state["storage"]["leather"], 5)
        self.assertEqual(sum(row["quantity"] for row in items.get_inventory(character_id)
                             if row["item_id"] == 66), 5)

        state = self.buildings.withdraw_from_storage(character_id, "barnyard", "leather", 3, 10000)
        self.assertEqual(state["storage"]["leather"], 2)
        self.assertEqual(sum(row["quantity"] for row in items.get_inventory(character_id)
                             if row["item_id"] == 66), 8)

    def test_city_barn_and_warehouse_allow_reciprocal_storage_transfers(self):
        character_id = self._character("city-stores")
        items = ItemsDatabase(self.database)
        for building, resource, item_id in (("barn", "wheat", 63), ("warehouse", "wood", 60)):
            with self.subTest(building=building):
                self.buildings.get_state(character_id, building, 10000)
                items.add_to_inventory(character_id, item_id, 6)
                deposited = self.buildings.deposit_to_storage(
                    character_id, building, resource, 4, 10000
                )
                self.assertEqual(deposited["storage"][resource], 4)

                withdrawn = self.buildings.withdraw_from_storage(
                    character_id, building, resource, 3, 10000
                )
                self.assertEqual(withdrawn["storage"][resource], 1)
                carried = sum(row["quantity"] for row in items.get_inventory(character_id)
                              if row["item_id"] == item_id)
                self.assertEqual(carried, 5)

    def test_black_pit_gems_can_move_to_and_from_shared_storage(self):
        character_id = self._character("gem-store")
        self._set_level(character_id, "black_pit", 3)
        items = ItemsDatabase(self.database)
        items.add_to_inventory(character_id, 80, 2)

        deposited = self.buildings.deposit_to_storage(character_id, "black_pit", "jet", 1, 10000)
        self.assertEqual(deposited["storage"]["jet"], 1)
        withdrawn = self.buildings.withdraw_from_storage(character_id, "black_pit", "jet", 1, 10000)
        self.assertEqual(withdrawn["storage"]["jet"], 0)
        self.assertEqual(sum(row["quantity"] for row in items.get_inventory(character_id)
                             if row["item_id"] == 80), 2)

    def test_authenticated_api_supports_shared_storage_deposit_and_withdraw(self):
        user = self.database.register("storage-api", "password")
        character_id = self.database.create_character(user["id"], "StorageApi")["id"]
        ItemsDatabase(self.database).add_to_inventory(character_id, 67, 5)

        with running_server(self.database) as client:
            client.login("storage-api", "password")
            deposited = client.building_action(
                "barnyard", character_id, "storage/deposit",
                {"resource": "meat", "quantity": 4},
            )
            self.assertEqual(deposited["storage"]["meat"], 4)

            withdrawn = client.building_action(
                "barnyard", character_id, "storage/withdraw",
                {"resource": "meat", "quantity": 3},
            )

        self.assertEqual(withdrawn["storage"]["meat"], 1)
        carried = sum(row["quantity"] for row in ItemsDatabase(self.database).get_inventory(character_id)
                      if row["item_id"] == 67)
        self.assertEqual(carried, 4)

    def test_storage_payload_caps_withdraw_quantity_by_remaining_carry_weight(self):
        user = self.database.register("carry-limit", "password")
        character_id = self.database.create_character(user["id"], "CarryLimit")["id"]
        items = ItemsDatabase(self.database)
        initial = items.carry_weight_state
        with self.database.connection() as connection:
            initial_weight = items.carry_weight_state(connection, character_id)
        fill_quantity = max(0, int((initial_weight["carry_capacity_kg"] - 1) // 2))
        if fill_quantity:
            self.assertTrue(items.add_to_inventory(character_id, 63, fill_quantity))

        self.buildings.get_state(character_id, "farm", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=500 WHERE world_id=%s AND faction='light' AND building='farm' AND resource='wheat'",
                (self.database.world_id,),
            )
        state = self.buildings.get_state(character_id, "farm", 10000)
        carry = items.carry_weight_state
        with self.database.connection() as connection:
            actual_weight = carry(connection, character_id)

        expected = min(500, max(0, int((actual_weight["carry_capacity_kg"]
                                        - actual_weight["carried_weight_kg"] + 1e-9) // 2)))
        self.assertEqual(state["storage_withdrawable"]["wheat"]["available"], 500)
        self.assertEqual(state["storage_withdrawable"]["wheat"]["max_withdraw"], expected)
        self.assertLess(expected, 500)

    def _set_level(self, character_id, building, level):
        self.buildings.get_state(character_id, building, 10000)
        with self.database.connection() as connection:
            connection.execute("UPDATE building_states SET level = %s WHERE building = %s", (level, building))

    def _reset(self, building):
        """Здание общее для фракции: для независимого сценария начинаем его заново."""
        with self.database.connection() as connection:
            connection.execute("DELETE FROM building_states WHERE building = %s", (building,))

    def test_disconnect_checkpoint_position_round_trips(self):
        user = self.database.register("position-saver", "password")
        character = self.database.create_character(user["id"], "PositionSaver")
        checkpoint = {
            **character,
            "zone": "world_map",
            "position_x": 4321.5,
            "position_y": 2789.25,
            "position_direction": "nw",
        }
        self.database.save_character(user["id"], character["id"], checkpoint)
        loaded = self.database.get_character(user["id"], character["id"])
        self.assertEqual(loaded["zone"], "world_map")
        self.assertEqual(loaded["position_x"], 4321.5)
        self.assertEqual(loaded["position_y"], 2789.25)
        self.assertEqual(loaded["position_direction"], "nw")

    def test_disconnect_cancels_pending_duel_application_and_marks_afk(self):
        from server import social

        with running_server(self.database) as client:
            client.register("afk-user", "secret1")
            client.login("afk-user", "secret1")
            character = client.create_character("AfkUser")
            offer = social.add_public_duel_offer(
                {"character_id": character["id"], "name": character["name"]}, "backyard"
            )
            client.disconnect({
                **character,
                "zone": "backyard",
                "position_x": 1200,
                "position_y": 900,
                "position_direction": "e",
            })

        saved_offer = next(item for item in social.DUEL_OFFERS if item["id"] == offer["id"])
        afk_presence = social.get_character_presence(character["id"])
        self.assertEqual(saved_offer["status"], "cancelled")
        self.assertTrue(afk_presence["afk"])
        self.assertEqual((afk_presence["position_x"], afk_presence["position_y"]), (1200, 900))
        social.DUEL_OFFERS.remove(saved_offer)
        social.presence.PRESENCE.pop(afk_presence["token"], None)

    def test_join_and_leave_announcements_are_posted_once_to_each_chat_location(self):
        from server import presence

        with running_server(self.database) as client:
            client.register("chat-status-user", "secret1")
            client.login("chat-status-user", "secret1")
            character = client.create_character("ChatStatusUser")
            first_snapshot = client.social_snapshot("tavern", character["id"])
            second_snapshot = client.social_snapshot("tavern", character["id"])
            self.assertEqual(
                sum(message["text"].startswith("[ИГРОК] ") for message in first_snapshot["messages"]),
                1,
            )
            self.assertEqual(
                sum(message["text"].startswith("[ИГРОК] ") for message in second_snapshot["messages"]),
                1,
            )
            client.disconnect({**character, "zone": "tavern"})

        for location in ("tavern", "backyard", "city", "world_map", "character_room", "world"):
            messages = self.database.get_chat_history(character["id"], location)
            status_texts = [message["text"] for message in messages if message["text"].startswith("[ИГРОК] ")]
            self.assertEqual(status_texts, [
                "[ИГРОК] ChatStatusUser присоединился к игре",
                "[ИГРОК] ChatStatusUser покинул сервер",
            ])

        afk_presence = presence.get_character_presence(character["id"])
        self.assertTrue(afk_presence["afk"])
        presence.PRESENCE.pop(afk_presence["token"], None)

    def test_attacking_afk_player_resolves_and_respawns_at_crystal(self):
        from server import presence

        with running_server(self.database) as client:
            client.register("offline-target", "secret1")
            target_user = client.login("offline-target", "secret1")
            target = client.create_character("OfflineTarget")
            client.update_presence(target["id"], "backyard")
            client.disconnect({
                **target,
                "zone": "backyard",
                "position_x": 1200,
                "position_y": 900,
                "position_direction": "e",
            })

            client.register("active-attacker", "secret1")
            client.login("active-attacker", "secret1")
            attacker = client.create_character("ActiveAttacker")
            accepted = client.offer_duel(attacker["id"], "backyard", target["id"])
            self.assertTrue(accepted["accepted"])
            result = client.report_battle_result(
                attacker["id"], "win", target["level"], 80, 20,
                opponent_id=target["id"], opponent_hp=0, opponent_mp=0,
            )

        saved_target = self.database.get_character(target_user["id"], target["id"])
        self.assertEqual((saved_target["hp"], saved_target["mp"]), (1, 1))
        self.assertEqual(saved_target["zone"], "city")
        self.assertEqual((saved_target["position_x"], saved_target["position_y"]),
                         (50 * 32 + 16, 53 * 32 + 16))
        self.assertTrue(result["afk_opponent"]["defeated"])
        afk_presence = presence.get_character_presence(target["id"])
        self.assertTrue(afk_presence["afk"])
        self.assertEqual(afk_presence["location"], "city")
        presence.PRESENCE.pop(afk_presence["token"], None)

    def test_active_player_work_lookup_clears_only_after_finishing_work(self):
        with running_server(self.database) as client:
            client.register("working-user", "secret1")
            client.login("working-user", "secret1")
            character = client.create_character("WorkingUser")
            character_id = character["id"]

            self.assertIsNone(client.get_player_work(character_id))
            client.building_action("farm", character_id, "workers/player/toggle", {"slot_index": 0})
            self.assertEqual(
                client.get_player_work(character_id),
                {"building": "farm", "slot_index": 0},
            )
            client.building_action("farm", character_id, "workers/player/toggle", {"slot_index": 0})
            self.assertIsNone(client.get_player_work(character_id))

    # ---------- поселение ----------

    def test_control_example_direct_harvest_and_fire(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)
        self.buildings.hire_worker(character_id, "farm", 1, "worker-1", 13600)

        state = self.buildings.get_state(character_id, "farm", 15400)
        self.assertEqual(state["storage"]["wheat"], 50)
        self.assertNotIn("buffer", state)
        self.assertEqual(state["worker_slots"][0]["progress_sec"], 80)
        self.assertEqual(state["worker_slots"][1]["progress_sec"], 120)

        state = self.buildings.fire_worker(character_id, "farm", 1, 15400)
        self.assertEqual(state["storage"]["wheat"], 50)
        self.assertNotIn("buffer", state)
        self.assertFalse(state["worker_slots"][1]["occupied"])

    def test_state_survives_new_database_wrapper(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)

        state = ProductionBuildings(self.database).get_state(character_id, "farm", 10140)
        self.assertEqual(state["storage"]["wheat"], 1)
        self.assertNotIn("buffer", state)
        self.assertEqual(state["worker_slots"][0]["worker_id"], "worker-0")

    def test_harvested_unit_goes_directly_to_storage_without_buffer(self):
        character_id = self._character("direct-harvest")
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)

        state = self.buildings.get_state(character_id, "farm", 10140)

        self.assertEqual(state["storage"]["wheat"], 1)
        self.assertNotIn("buffer", state)

    def test_direct_harvest_keeps_worker_timer_running(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)

        state = self.buildings.get_state(character_id, "farm", 17200)
        self.assertEqual(state["storage"]["wheat"], 51)
        self.assertNotIn("buffer", state)
        self.assertEqual(state["worker_slots"][0]["progress_sec"], 60)
        self.assertTrue(state["worker_slots"][0]["occupied"])

    def test_worker_payload_reports_next_unit_timer(self):
        character_id = self._character("cycle-yield")
        self.buildings.hire_worker(character_id, "farm", 0, "citizen-1", 10000)

        state = self.buildings.get_state(character_id, "farm", 10730)

        worker = state["worker_slots"][0]
        self.assertEqual(state["storage"]["wheat"], 5)
        self.assertEqual(worker["progress_sec"], 30)
        self.assertEqual(state["next_harvest_seconds"], 110)

    def test_direct_harvest_does_not_exceed_shared_storage_capacity(self):
        character_id = self._character("cycle-capacity")
        self.buildings.get_state(character_id, "farm", 10000)
        self.buildings.hire_worker(character_id, "farm", 0, "citizen-1", 10000)
        self.buildings.hire_worker(character_id, "farm", 1, "citizen-2", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=498, buffer=4 WHERE world_id=%s AND faction='light' AND building='farm' AND resource='wheat'",
                (self.database.world_id,),
            )

        state = self.buildings.get_state(character_id, "farm", 11000)

        self.assertEqual(state["storage"]["wheat"], 500)
        self.assertNotIn("buffer", state)
        with self.database.connection() as connection:
            buffer = connection.execute(
                "SELECT buffer FROM building_resources WHERE world_id=%s AND faction='light' AND building='farm' AND resource='wheat'",
                (self.database.world_id,),
            ).fetchone()["buffer"]
        self.assertEqual(buffer, 0)

    def test_player_harvest_is_shared_and_taken_from_common_storage(self):
        character_id = self._character("player-worker")
        self._set_strength(character_id, 100)
        items = ItemsDatabase(self.database)
        working = self.buildings.toggle_player_worker(character_id, "farm", 0, 10000)
        self.assertEqual(working["worker_slots"][0]["worker_id"], f"player:{character_id}")
        with self.assertRaisesRegex(ValueError, "сам завершить работу"):
            self.buildings.fire_worker(character_id, "farm", 0, 10001)

        produced = self.buildings.get_state(character_id, "farm", 17200)
        self.assertEqual(produced["storage"]["wheat"], 51)
        self.assertEqual(produced["player_harvest_totals"]["wheat"], 51)
        self.assertNotIn("player_harvest_claims", produced)

        withdrawn = self.buildings.withdraw_from_storage(
            character_id, "farm", "wheat", 50, 17200,
        )
        self.assertEqual(withdrawn["storage"]["wheat"], 1)
        self.assertEqual(sum(item["quantity"] for item in items.get_inventory(character_id)
                             if item["item_id"] == 63), 50)
        stopped = self.buildings.toggle_player_worker(character_id, "farm", 0, 17202)
        self.assertFalse(stopped["worker_slots"][0]["occupied"])

    def test_shared_harvest_is_unlimited_by_player_carry_until_withdrawal(self):
        character_id = self._character("weight-farmer")
        self._set_strength(character_id, 3)
        items = ItemsDatabase(self.database)
        self.buildings.toggle_player_worker(character_id, "farm", 0, 10140)
        produced = self.buildings.get_state(character_id, "farm", 17200)
        self.assertEqual(produced["storage"]["wheat"], 50)
        self.assertEqual(
            sum(item["quantity"] for item in items.get_inventory(character_id)
                if item["item_id"] == 63),
            0,
        )

        state = self.buildings.withdraw_from_storage(character_id, "farm", "wheat", 50, 17200)

        self.assertEqual(state["storage"]["wheat"], 38)
        self.assertEqual(
            sum(item["weight"] * item["quantity"] for item in items.get_inventory(character_id)),
            24,
        )

    def test_player_cannot_start_work_when_storage_is_full(self):
        character_id = self._character("full-worker")
        self.buildings.get_state(character_id, "farm", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage = 500 WHERE building = 'farm' AND resource = 'wheat'"
            )
        with self.assertRaisesRegex(ValueError, "Склад переполнен"):
            self.buildings.toggle_player_worker(character_id, "farm", 0, 10001)

    def test_offline_harvest_accrues_directly_on_next_access(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)
        self.buildings.hire_worker(character_id, "farm", 1, "worker-1", 10000)

        state = self.buildings.get_state(character_id, "farm", 10000 + 6 * 7200 + 100)
        self.assertEqual(state["storage"]["wheat"], 500)
        self.assertNotIn("buffer", state)

    def test_flax_and_cotton_use_their_own_timers(self):
        character_id = self._character()
        self._set_level(character_id, "farm", 7)
        state = self.buildings.hire_worker(character_id, "farm", 4, "flax-worker", 10000)
        self.assertEqual(state["worker_slots"][4]["resource"], "flax")
        state = self.buildings.hire_worker(character_id, "farm", 13, "cotton-worker", 10000)
        self.assertEqual(state["worker_slots"][13]["resource"], "cotton")

        state = self.buildings.get_state(character_id, "farm", 10000 + 980)
        self.assertEqual(state["storage"]["wheat"], 0)
        self.assertEqual(state["storage"]["flax"], 2)
        self.assertEqual(state["storage"]["cotton"], 1)
        self.assertNotIn("buffer", state)
        self.assertEqual(state["max_workers"], 14)
        self.assertEqual(state["storage"]["limit"], 4500)

    def test_locked_plot_slot_is_rejected(self):
        character_id = self._character()
        with self.assertRaisesRegex(ValueError, "не открыт"):
            self.buildings.hire_worker(character_id, "farm", 2, "worker", 10000)

    def test_unknown_building_is_rejected(self):
        character_id = self._character()
        with self.assertRaisesRegex(ValueError, "Неизвестное здание"):
            self.buildings.get_state(character_id, "castle", 10000)

    def test_storage_capacity_is_independent_per_resource(self):
        storage = {"wheat": 400, "flax": 50, "cotton": 0}
        accepted = distribute_to_storage(storage, {"wheat": 60, "flax": 30, "cotton": 10}, 500)
        self.assertEqual(accepted, {"wheat": 60, "flax": 30, "cotton": 10})
        accepted = distribute_to_storage(
            {"wheat": 500, "flax": 0, "cotton": 0},
            {"wheat": 10, "flax": 500, "cotton": 250},
            500,
        )
        self.assertEqual(accepted, {"wheat": 0, "flax": 500, "cotton": 250})

    def test_external_storage_resource_limit_is_independent(self):
        character_id = self._character("ext-cap")
        self._set_level(character_id, "farm", 3)
        self.buildings.get_state(character_id, "farm", 10000)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=500 WHERE world_id=%s AND faction='light'
                   AND building='farm' AND resource='wheat'""",
                (self.database.world_id,),
            )
        ItemsDatabase(self.database).add_to_inventory(character_id, 64, 1)
        state = self.buildings.deposit_to_storage(character_id, "farm", "flax", 1, 10001)
        self.assertEqual((state["storage"]["wheat"], state["storage"]["flax"]), (500, 1))
        self.assertEqual(state["storage_total"], 501)

    def test_upgrade_purchases_materials_from_shared_warehouse_and_finishes_on_time(self):
        character_id = self._character()
        items = ItemsDatabase(self.database)
        materials = upgrade_requirements(1)["materials"]

        with self.assertRaisesRegex(ValueError, "Недостаточно ресурсов на общем складе"):
            self.buildings.start_upgrade(character_id, "farm", 10000)
        with self.assertRaisesRegex(ValueError, "Отдельные взносы отключены"):
            self.buildings.deposit_material(character_id, "farm", 60, 5, 10000)

        for item_id, required in materials.items():
            items.add_to_inventory(character_id, item_id, required + 2)
            self.buildings.deposit_to_storage(
                character_id, "warehouse", STORAGE_RESOURCES_BY_ITEM_ID[item_id],
                required + 2, 10000,
            )
        state = self.buildings.get_state(character_id, "farm", 10000)
        self.assertTrue(state["upgrade"]["ready"])
        self.assertTrue(all(row["in_warehouse"] == 7 for row in state["upgrade"]["materials"]))

        state = self.buildings.start_upgrade(character_id, "farm", 10000)
        self.assertTrue(state["upgrade"]["in_progress"])
        self.assertEqual(state["level"], 1)
        with self.assertRaisesRegex(ValueError, "уже идёт"):
            self.buildings.start_upgrade(character_id, "farm", 10001)

        state = self.buildings.get_state(character_id, "farm", 10000 + upgrade_requirements(1)["time_seconds"])
        self.assertEqual(state["level"], 2)
        self.assertEqual(len(state["worker_slots"]), 4)
        self.assertFalse(state["upgrade"]["in_progress"])
        self.assertTrue(all(row["deposited"] == 0 for row in state["upgrade"]["materials"]))

    def test_overflow_does_not_create_a_buffer(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage = 480 WHERE building = 'farm' AND resource = 'wheat'"
            )

        state = self.buildings.get_state(character_id, "farm", 17200)
        self.assertEqual(state["storage"]["wheat"], 500)
        self.assertNotIn("buffer", state)

    def test_parallel_requests_count_harvest_once(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "worker-0", 10000)
        errors = []

        def read_state():
            try:
                self.buildings.get_state(character_id, "farm", 10000 + 10 * 140)
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=read_state) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        state = self.buildings.get_state(character_id, "farm", 10000 + 10 * 140)
        self.assertEqual(state["storage"]["wheat"], 10)
        self.assertNotIn("buffer", state)

    def test_buildings_are_shared_by_all_players_of_faction(self):
        items = ItemsDatabase(self.database)
        user = self.database.register("leaver", "password")
        first = self.database.create_character(user["id"], "Leaver")["id"]
        self._set_strength(first, 1000)
        second = self._character("helper")

        # Один игрок отправил горожанина — другой видит его на том же поле
        self.buildings.hire_worker(first, "farm", 0, "worker-0", 10000)
        state = self.buildings.get_state(second, "farm", 10000)
        self.assertTrue(state["worker_slots"][0]["occupied"])
        with self.assertRaisesRegex(ValueError, "уже занято"):
            self.buildings.hire_worker(second, "farm", 0, "worker-x", 10000)

        # Different players stock the shared warehouse; any player can buy the upgrade.
        materials = list(upgrade_requirements(1)["materials"].items())
        for index, (item_id, required) in enumerate(materials):
            giver = first if index % 2 == 0 else second
            items.add_to_inventory(giver, item_id, required)
            self.buildings.deposit_to_storage(
                giver, "warehouse", STORAGE_RESOURCES_BY_ITEM_ID[item_id], required, 10000
            )
        state = self.buildings.get_state(second, "farm", 10000)
        self.assertTrue(state["upgrade"]["ready"])
        state = self.buildings.start_upgrade(second, "farm", 10000)
        self.assertTrue(state["upgrade"]["in_progress"])

        # Здание остаётся у фракции и после удаления персонажа
        self.database.delete_character(user["id"], first)
        state = self.buildings.get_state(second, "farm", 10000 + upgrade_requirements(1)["time_seconds"])
        self.assertEqual(state["level"], 2)
        self.assertTrue(state["worker_slots"][0]["occupied"])

    # ---------- лагерь лесорубов ----------

    def test_lumber_camp_is_independent_from_farm(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "farm", 0, "farmer", 10000)
        state = self.buildings.get_state(character_id, "lumber_camp", 10000)

        self.assertEqual(state["level"], 1)
        self.assertEqual(state["storage"], {"wood": 0, "limit": 500})
        self.assertEqual(len(state["worker_slots"]), 2)
        self.assertFalse(any(slot["occupied"] for slot in state["worker_slots"]))

    def test_lumber_camp_wood_and_berries_timers(self):
        character_id = self._character()
        self._set_level(character_id, "lumber_camp", 4)
        # Слоты: 0-1 край (дерево), 2 край, 3 опушка (ягоды), 4 дерево, 5 ягоды
        state = self.buildings.hire_worker(character_id, "lumber_camp", 0, "wood-worker", 10000)
        self.assertEqual(state["worker_slots"][0]["resource"], "wood")
        state = self.buildings.hire_worker(character_id, "lumber_camp", 3, "berry-worker", 10000)
        self.assertEqual(state["worker_slots"][3]["resource"], "berries")
        self.assertEqual(state["max_workers"], 6)

        state = self.buildings.get_state(character_id, "lumber_camp", 10000 + 720)
        self.assertEqual(state["storage"]["wood"], 3)
        self.assertEqual(state["storage"]["berries"], 2)
        self.assertNotIn("buffer", state)

        # Через полный цикл: 7200/240 = 30 древесины, 7200/360 = 20 ягод
        state = self.buildings.get_state(character_id, "lumber_camp", 17200)
        self.assertEqual(state["storage"]["wood"], 30)
        self.assertEqual(state["storage"]["berries"], 20)

    def test_lumber_camp_slots_match_level_table(self):
        character_id = self._character()
        expected = {1: 2, 2: 3, 3: 4, 4: 6, 5: 8, 6: 10, 7: 13, 8: 16, 9: 19, 10: 25}
        for level, workers in expected.items():
            with self.subTest(level=level):
                self._set_level(character_id, "lumber_camp", level)
                state = self.buildings.get_state(character_id, "lumber_camp", 10000)
                self.assertEqual(len(state["worker_slots"]), workers)

    # ---------- горный разлом ----------

    def test_rift_mines_grow_with_levels(self):
        character_id = self._character()
        # Уровень 1 открывает камень; железо добавляется на уровне 2.
        expected = {
            1: (0, 2, 0, 0), 2: (1, 2, 0, 0), 3: (2, 2, 0, 0), 4: (3, 3, 0, 0), 5: (5, 3, 0, 0),
            6: (6, 4, 0, 0), 7: (6, 5, 2, 0), 8: (8, 5, 3, 0), 9: (10, 6, 3, 0), 10: (10, 7, 5, 3),
        }
        for level, places in expected.items():
            with self.subTest(level=level):
                self._set_level(character_id, "mountain_rift", level)
                slots = self.buildings.get_state(character_id, "mountain_rift", 10000)["worker_slots"]
                counts = tuple(sum(1 for slot in slots if slot["resource"] == ore) for ore in ("iron", "stone", "mithril", "obsidian"))
                self.assertEqual(counts, places)

    def test_rift_ore_timers(self):
        character_id = self._character()
        self._set_level(character_id, "mountain_rift", 10)
        for slot_index in (0, 2, 11, 20):
            self.buildings.hire_worker(character_id, "mountain_rift", slot_index, f"w{slot_index}", 10000)

        state = self.buildings.get_state(character_id, "mountain_rift", 17200)
        self.assertEqual(state["storage"]["iron"], 24)
        self.assertEqual(state["storage"]["stone"], 36)
        self.assertEqual(state["storage"]["mithril"], 8)
        self.assertEqual(state["storage"]["obsidian"], 5)
        self.assertEqual(state["storage"]["limit"], 12000)

    # ---------- скотный двор ----------

    def test_barnyard_worker_gives_leather_and_meat(self):
        character_id = self._character()
        state = self.buildings.hire_worker(character_id, "barnyard", 0, "herder", 10000)
        self.assertEqual(state["worker_slots"][0]["resources"], ["leather", "meat"])
        self.assertEqual(state["storage"], {"leather": 0, "meat": 0, "limit": 500})

        # Промежуточный запрос не должен считать единицы дважды
        self.buildings.get_state(character_id, "barnyard", 10500)
        state = self.buildings.get_state(character_id, "barnyard", 10000 + 1380)
        self.assertEqual(state["storage"]["leather"], 3)
        self.assertEqual(state["storage"]["meat"], 2)
        self.assertNotIn("buffer", state)

        state = self.buildings.fire_worker(character_id, "barnyard", 0, 10000 + 1400)
        self.assertEqual(state["storage"]["leather"], 3)
        self.assertEqual(state["storage"]["meat"], 2)
        self.assertNotIn("buffer", state)

    def test_barnyard_full_cycle(self):
        character_id = self._character()
        self.buildings.hire_worker(character_id, "barnyard", 0, "a", 10000)
        self.buildings.hire_worker(character_id, "barnyard", 1, "b", 10000)
        state = self.buildings.get_state(character_id, "barnyard", 17200)
        self.assertEqual(state["storage"]["leather"], 30)
        self.assertEqual(state["storage"]["meat"], 20)

    def test_barnyard_pen_grows_with_level_table(self):
        character_id = self._character()
        for level, workers in {1: 2, 4: 6, 7: 13, 10: 25}.items():
            with self.subTest(level=level):
                self._set_level(character_id, "barnyard", level)
                state = self.buildings.get_state(character_id, "barnyard", 10000)
                self.assertEqual(len(state["worker_slots"]), workers)

    # ---------- чёрная копь ----------

    def test_black_pit_gem_bonus_rolls_for_each_mined_coal_unit(self):
        gems = ("jet", "malachite", "topaz", "garnet", "emerald", "ruby", "sapphire", "diamond")
        lucky = ProductionBuildings(self.database, rng=_Sequence([0.0]))
        first, second = self._character("miner"), self._character("digger")

        # 1 уровень: камней нет даже при любом везении; уголь 600 с
        state = lucky.hire_worker(first, "black_pit", 0, "m", 10000)
        self.assertEqual(state["storage"], {"coal": 0, "limit": 500})
        state = lucky.get_state(first, "black_pit", 17200)
        self.assertEqual(state["storage"]["coal"], 12)
        self.assertEqual(set(state["storage"]) - {"limit"}, {"coal"})
        self.assertNotIn("buffer", state)

        # Per-unit direct accrual: deterministic success grants a gem for each coal unit.
        self._reset("black_pit")
        self._set_level(second, "black_pit", 3)
        lucky.hire_worker(second, "black_pit", 0, "a", 10000)
        lucky.hire_worker(second, "black_pit", 1, "b", 10000)
        state = lucky.get_state(second, "black_pit", 10000 + 3600)
        self.assertNotIn("buffer", state)
        state = lucky.get_state(second, "black_pit", 17200)
        self.assertEqual(state["storage"]["coal"], 24)
        self.assertEqual(state["storage"]["jet"], 24)
        state = lucky.get_state(second, "black_pit", 10000 + 2 * 7200)
        self.assertEqual(state["storage"]["jet"], 48)

    def test_black_pit_gem_kind_by_level_weights(self):
        diamonds = ProductionBuildings(self.database, rng=_Sequence([0.0, 0.99]))
        character_id = self._character()
        self._set_level(character_id, "black_pit", 10)
        diamonds.hire_worker(character_id, "black_pit", 0, "m", 10000)
        state = diamonds.get_state(character_id, "black_pit", 17200)
        self.assertEqual(state["storage"]["diamond"], 12)
        self.assertEqual(state["storage"]["limit"], 12000)

    def test_black_pit_no_gem_without_workers_full_storage_or_luck(self):
        lucky = ProductionBuildings(self.database, rng=_Sequence([0.0]))
        character_id = self._character("miner")

        self._set_level(character_id, "black_pit", 3)
        state = lucky.get_state(character_id, "black_pit", 17200)
        self.assertEqual(state["storage"]["jet"], 0)

        self._reset("black_pit")
        self._set_level(character_id, "black_pit", 3)
        lucky.hire_worker(character_id, "black_pit", 0, "m", 10000)
        with self.database.connection() as connection:
            connection.execute("UPDATE building_resources SET storage = 1000 WHERE resource = 'coal'")
        state = lucky.get_state(character_id, "black_pit", 17200)
        self.assertEqual(state["storage"]["jet"], 0)

        self._reset("black_pit")
        self._set_level(character_id, "black_pit", 3)
        unlucky = ProductionBuildings(self.database, rng=_Sequence([0.99]))
        unlucky_id = character_id
        unlucky.hire_worker(unlucky_id, "black_pit", 0, "m", 10000)
        state = unlucky.get_state(unlucky_id, "black_pit", 17200)
        self.assertEqual(state["storage"]["coal"], 12)
        self.assertEqual(state["storage"]["jet"], 0)

    def test_black_pit_own_level_table(self):
        character_id = self._character()
        expected = {1: 2, 2: 3, 3: 4, 4: 5, 5: 7, 6: 10, 7: 13, 8: 16, 9: 19, 10: 25}
        for level, workers in expected.items():
            with self.subTest(level=level):
                self._set_level(character_id, "black_pit", level)
                state = self.buildings.get_state(character_id, "black_pit", 10000)
                self.assertEqual(len(state["worker_slots"]), workers)
                self.assertEqual(state["max_workers"], workers)

    def test_http_contract_for_both_buildings(self):
        with running_server(self.database) as client:
            client.register("farmuser", "secret1")
            client.login("farmuser", "secret1")
            character = client.create_character("Farmer")

            farm = client.get_building("farm", character["id"])
            hired = client.building_action("lumber_camp", character["id"], "workers/hire", {"slot_index": 0, "worker_id": "w"})
            fired = client.building_action("lumber_camp", character["id"], "workers/fire", {"slot_index": 0})

        self.assertEqual(farm["storage"], {"wheat": 0, "limit": 500})
        self.assertEqual(hired["building"], "lumber_camp")
        self.assertTrue(hired["worker_slots"][0]["occupied"])
        self.assertFalse(fired["worker_slots"][0]["occupied"])


if __name__ == "__main__":
    unittest.main()
