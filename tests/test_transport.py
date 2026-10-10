import unittest
import time
import math

from server.city_population import CityPopulation
from server.items_database import ItemsDatabase
from server.production_buildings import ProductionBuildings
from server.transport import TransportService
from tests.fixtures import create_test_database, drop_test_database, running_server


class TransportServiceTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.now = time.time()
        user = self.database.register("hauler", "password")
        self.character_id = self.database.create_character(user["id"], "Hauler")["id"]
        ItemsDatabase(self.database)
        self.production = ProductionBuildings(self.database)
        CityPopulation(self.database).get_state(self.character_id, now=self.now)
        self.production.get_state(self.character_id, "stable", now=self.now)
        self.production.get_state(self.character_id, "warehouse", now=self.now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=10000 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE stable_cart_progress SET body_owned=TRUE WHERE world_id=%s AND faction='light' AND grade=1",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                "AND building='warehouse' AND resource='wood'",
                (self.database.world_id,),
            )
        self.production.purchase_horse(self.character_id, 0, now=self.now + 1)
        with self.database.connection() as connection:
            self.driver_id = connection.execute(
                "SELECT id FROM city_citizens WHERE world_id=%s AND faction='light' "
                "AND satisfaction='satisfied' ORDER BY ordinal LIMIT 1",
                (self.database.world_id,),
            ).fetchone()["id"]

    def tearDown(self):
        drop_test_database(self.database)

    def _payload(self):
        return {
            "cart_id": "cart_grade_1",
            "horse_ids": [self._horse_id()],
            "driver_citizen_id": self.driver_id,
            "destination_building_id": "lumber_camp",
            "resource_ids": ["wood"],
        }

    def _horse_id(self):
        with self.database.connection() as connection:
            return connection.execute(
                "SELECT id FROM stable_horses WHERE world_id=%s AND faction='light' AND slot_index=0",
                (self.database.world_id,),
            ).fetchone()["id"]

    def test_cart_in_production_cannot_be_dispatched(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE stable_cart_progress SET body_owned=FALSE, body_count=0 "
                "WHERE world_id=%s AND faction='light' AND grade=1",
                (self.database.world_id,),
            )
            connection.execute(
                "INSERT INTO stable_cart_production_orders "
                "(world_id, faction, building, grade, created_at, finish_at) "
                "VALUES (%s, 'light', 'stable', 1, %s, %s)",
                (self.database.world_id, self.now, self.now + 2400),
            )

        with self.assertRaisesRegex(ValueError, "ещё не куплена"):
            TransportService(self.database).dispatch(
                self.character_id, self._payload(), now=self.now + 2
            )

    def test_second_owned_cart_instance_can_be_dispatched(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE stable_cart_progress SET body_count=2 WHERE world_id=%s "
                "AND faction='light' AND grade=1",
                (self.database.world_id,),
            )
        payload = self._payload()
        payload["cart_id"] = "cart_grade_1~2"

        convoy = TransportService(self.database).dispatch(
            self.character_id, payload, now=self.now + 2
        )

        self.assertEqual(convoy["cart_id"], "cart_grade_1~2")

    def test_second_cart_dispatches_empty_when_selected_resource_is_unavailable(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE stable_cart_progress SET body_count=2 WHERE world_id=%s AND faction='light' AND grade=1",
                (self.database.world_id,),
            )
            connection.execute(
                """UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        payload = self._payload()
        payload["cart_id"] = "cart_grade_1~2"
        convoy = TransportService(self.database).dispatch(
            self.character_id, payload, now=self.now + 2,
        )

        self.assertEqual(convoy["cart_id"], "cart_grade_1~2")
        self.assertEqual(convoy["cargo"], [])
        self.assertEqual(convoy["cargo_kg"], 0)
        self.assertEqual(convoy["status"], "Едет к объекту")

    def test_dispatch_rejects_unselected_cargo_slot(self):
        payload = self._payload()
        payload["resource_ids"] = [None]
        with self.assertRaisesRegex(ValueError, "ресурс для каждого грузового слота"):
            TransportService(self.database).dispatch(
                self.character_id, payload, now=self.now + 2,
            )

    def test_empty_pinned_route_returns_instead_of_waiting_for_resources(self):
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light'
                   AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
        payload = self._payload()
        payload["pinned"] = True
        service = TransportService(self.database)
        convoy = service.dispatch(self.character_id, payload, now=self.now + 2)

        returned = service.get_world_convoys(
            self.character_id, now=self.now + convoy["travel_seconds"] + 3,
        )

        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0]["phase"], "returning")
        self.assertEqual(returned[0]["cargo"], [])
        self.assertNotEqual(returned[0]["status"], "Ожидает ресурсы")

    def test_dispatched_horse_uses_work_satiety_rate(self):
        TransportService(self.database).dispatch(
            self.character_id, self._payload(), now=self.now + 2
        )

        state = self.production.get_state(
            self.character_id, "stable", now=self.now + 62
        )

        self.assertEqual(state["stall_slots"][0]["horse"]["status"], "В пути")
        self.assertEqual(state["stall_slots"][0]["horse"]["satiety"], 99)

    def test_dispatch_http_and_world_convoy_snapshot(self):
        observer_user = self.database.register("hauler-observer", "password")
        observer_id = self.database.create_character(observer_user["id"], "Observer")["id"]
        with running_server(self.database) as owner_client:
            owner_client.timeout = 15
            owner_client.login("hauler", "password")
            observer_client = type(owner_client)(owner_client.base_url)
            observer_client.login("hauler-observer", "password")

            stable = owner_client.get_building("stable", self.character_id)
            self.assertEqual(len(stable["available_cart_drivers"]), 4)
            self.assertTrue(stable["available_carts"][0]["can_travel"])
            response = owner_client.dispatch_transport(self.character_id, self._payload())
            pinned_state = owner_client.building_action(
                "stable", self.character_id, "transport/pin",
                {"convoy_id": response["convoy"]["id"], "pinned": True},
            )
            self.assertTrue(pinned_state["transport_convoys"][0]["pinned"])
            unpinned_state = owner_client.building_action(
                "stable", self.character_id, "transport/pin",
                {"convoy_id": response["convoy"]["id"], "pinned": False},
            )
            self.assertFalse(unpinned_state["transport_convoys"][0]["pinned"])
            owner_convoys = owner_client.get_traveling_convoys(self.character_id)
            observer_convoys = observer_client.get_traveling_convoys(observer_id)

        self.assertEqual(len(owner_convoys), 1)
        self.assertEqual(len(observer_convoys), 1)
        convoy = owner_convoys[0]
        observer_convoy = observer_convoys[0]
        self.assertEqual(observer_convoy["id"], convoy["id"])
        self.assertEqual(observer_convoy["cargo"], convoy["cargo"])
        self.assertAlmostEqual(observer_convoy["position_x"], convoy["position_x"], places=1)
        self.assertAlmostEqual(observer_convoy["position_y"], convoy["position_y"], places=1)
        self.assertEqual(convoy["cart_id"], "cart_grade_1")
        self.assertEqual(convoy["destination_building_id"], "lumber_camp")
        self.assertEqual(convoy["cargo"][0]["resource_id"], "wood")
        self.assertEqual(response["convoy"]["id"], convoy["id"])
        self.assertFalse(response["building"]["available_carts"][0]["can_travel"])
        self.assertNotIn(
            self.driver_id,
            [driver["id"] for driver in response["building"]["available_cart_drivers"]],
        )
        population = CityPopulation(self.database)
        city_state = population.get_state(self.character_id)
        driver = next(row for row in city_state["citizens"] if row["id"] == self.driver_id)
        self.assertEqual(driver["work_status"], "Ведёт повозку")
        with self.assertRaisesRegex(ValueError, "Участник экипажа занят транспортным рейсом"):
            population.assign_citizen(self.character_id, self.driver_id, "farm", 0)

    def test_free_driver_with_stale_job_slot_is_still_available(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_citizens SET job_slot=0 WHERE id=%s", (self.driver_id,),
            )

        stable = self.production.get_state(self.character_id, "stable", now=self.now + 2)

        self.assertIn(
            self.driver_id,
            [driver["id"] for driver in stable["available_cart_drivers"]],
        )
        convoy = TransportService(self.database).dispatch(
            self.character_id, self._payload(), now=self.now + 3,
        )
        self.assertEqual(convoy["driver_citizen_id"], self.driver_id)

    def test_dispatch_rejects_locked_city_routes_and_resources(self):
        service = TransportService(self.database)
        payload = self._payload()
        payload["destination_building_id"] = "mountain_rift"
        payload["resource_ids"] = ["iron"]
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            service.dispatch(self.character_id, payload, now=self.now + 2)

        payload["destination_building_id"] = "lumber_camp"
        payload["resource_ids"] = ["berries"]
        with self.assertRaisesRegex(ValueError, "ещё не открыт"):
            service.dispatch(self.character_id, payload, now=self.now + 3)

    def test_dispatch_uses_destination_capacity_per_resource(self):
        service = TransportService(self.database)
        self.production.get_state(self.character_id, "barn", now=self.now)
        self.production.get_state(self.character_id, "lumber_camp", now=self.now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET castle_level=2 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
            connection.execute(
                """UPDATE building_resources SET storage=500 WHERE world_id=%s AND faction='light'
                   AND building='lumber_camp' AND resource='wood'""",
                (self.database.world_id,),
            )
            connection.execute(
                """UPDATE building_resources SET storage=1 WHERE world_id=%s AND faction='light'
                   AND building='barn' AND resource='berries'""",
                (self.database.world_id,),
            )

        payload = self._payload()
        payload["resource_ids"] = ["berries"]
        convoy = service.dispatch(self.character_id, payload, now=self.now + 2)
        self.assertEqual(convoy["cargo"][0]["resource_id"], "berries")

    def test_wheat_convoy_loads_from_barn(self):
        self.production.get_state(self.character_id, "barn", now=self.now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            )

        payload = self._payload()
        payload["destination_building_id"] = "wheat_farm"
        payload["resource_ids"] = ["wheat"]
        convoy = TransportService(self.database).dispatch(
            self.character_id, payload, now=self.now + 2,
        )

        self.assertEqual(convoy["cargo"][0]["resource_id"], "wheat")
        with self.database.connection() as connection:
            remaining_wheat = connection.execute(
                "SELECT storage FROM building_resources WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertLess(remaining_wheat, 100)

    def test_wheat_dispatch_http_action_is_registered(self):
        self.production.get_state(self.character_id, "barn", now=self.now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            )
        payload = self._payload()
        payload["destination_building_id"] = "wheat_farm"
        payload["resource_ids"] = ["wheat"]

        with running_server(self.database) as client:
            client.timeout = 15
            client.login("hauler", "password")
            response = client.dispatch_transport(self.character_id, payload)

        self.assertEqual(response["convoy"]["cargo"][0]["resource_id"], "wheat")

    def test_pinned_route_loads_returns_unloads_reprovisions_and_repeats(self):
        from core.cart_progress import cart_stats

        self.production.get_state(self.character_id, "farm", now=self.now)
        self.production.get_state(self.character_id, "barn", now=self.now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE building_resources SET storage=1000 WHERE world_id=%s AND faction='light' "
                "AND building='farm' AND resource='wheat'",
                (self.database.world_id,),
            )
        payload = self._payload()
        payload.update(
            destination_building_id="wheat_farm", resource_ids=["wheat"], pinned=True,
        )
        service = TransportService(self.database)
        convoy = service.dispatch(self.character_id, payload, now=self.now + 2)
        convoy_id = convoy["id"]
        self.assertTrue(convoy["pinned"])
        self.assertEqual(convoy["cargo"], [])

        cart_stats_value = cart_stats({"wheels": 0, "sides": 0, "axles": 0})
        one_way_empty = math.ceil(50.11 * cart_stats_value["seconds_per_tile"])
        loading = service.get_world_convoys(self.character_id, now=self.now + 3 + one_way_empty)[0]
        self.assertEqual(loading["id"], convoy_id)
        self.assertEqual(loading["phase"], "loading")
        self.assertEqual(loading["cargo"][0]["resource_id"], "wheat")
        self.assertGreater(loading["cargo_kg"], 0)
        self.assertEqual([stage["state"] for stage in loading["route_stages"]],
                 ["complete", "current", "future", "future"])
        expected_load = math.ceil(loading["cargo_kg"] / 60 * 60)
        expected_unload = math.ceil(loading["cargo_kg"] / 40 * 60)
        self.assertEqual(loading["seconds_remaining"], expected_load)
        self.assertEqual(loading["route_stages"][3]["seconds"], expected_unload)
        self.assertGreater(expected_unload, expected_load)
        with self.database.connection() as connection:
            farm_wheat = connection.execute(
                "SELECT storage FROM building_resources WHERE world_id=%s AND faction='light' "
                "AND building='farm' AND resource='wheat'",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertLess(farm_wheat, 1000)

        load_end = self.now + 3 + one_way_empty + loading["seconds_remaining"] + 1
        returning = service.get_world_convoys(self.character_id, now=load_end)[0]
        self.assertEqual(returning["phase"], "returning")
        self.assertGreater(returning["travel_seconds"], one_way_empty)

        return_end = load_end + returning["seconds_remaining"] + 1
        unloading = service.get_world_convoys(self.character_id, now=return_end)[0]
        self.assertEqual(unloading["phase"], "unloading")
        self.assertEqual(unloading["seconds_remaining"], expected_unload)

        unload_end = return_end + unloading["seconds_remaining"] + 1
        resting = service.get_world_convoys(self.character_id, now=unload_end)[0]
        self.assertEqual(resting["phase"], "resting")
        self.assertEqual(resting["direction"], "returning")
        self.assertEqual(resting["status"], "Пополнение провизии")
        self.assertEqual(resting["seconds_remaining"], 5)
        self.assertEqual(resting["cycle_seconds_remaining"], 5)
        self.assertEqual([stage["state"] for stage in resting["route_stages"]],
                 ["complete", "complete", "complete", "complete"])
        self.assertEqual(resting["cargo"], [])
        with self.database.connection() as connection:
            city_wheat = connection.execute(
                "SELECT storage FROM building_resources WHERE world_id=%s AND faction='light' "
                "AND building='barn' AND resource='wheat'",
                (self.database.world_id,),
            ).fetchone()["storage"]
        self.assertGreater(city_wheat, 0)

        next_departure = service.get_world_convoys(
            self.character_id, now=unload_end + 6,
        )[0]
        self.assertEqual(next_departure["phase"], "outbound")
        self.assertTrue(next_departure["pinned"])
        self.assertEqual(next_departure["cargo"], [])
        service.set_pinned(self.character_id, convoy_id, False, now=unload_end + 7)
        finished = service.get_world_convoys(
            self.character_id,
            now=unload_end + 8 + next_departure["seconds_remaining"],
        )
        self.assertFalse(any(int(row["id"]) == convoy_id for row in finished))

    def test_pinning_blocked_inbound_convoy_returns_existing_cargo(self):
        service = TransportService(self.database)
        convoy = service.dispatch(self.character_id, self._payload(), now=self.now + 1)
        blocked_at = self.now + 2
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE transport_convoys SET status='blocked', phase='outbound', arrival_at=%s
                   WHERE id=%s""",
                (blocked_at - 1, convoy["id"]),
            )

        snapshot = service.set_pinned(
            self.character_id, convoy["id"], True, now=blocked_at,
        )
        returning = next(row for row in snapshot if row["id"] == convoy["id"])

        self.assertTrue(returning["pinned"])
        self.assertEqual(returning["phase"], "returning")
        self.assertEqual(returning["direction"], "returning")
        self.assertEqual(returning["cargo"][0]["resource_id"], "wood")

    def test_starving_convoy_driver_turns_the_wagon_toward_city(self):
        service = TransportService(self.database)
        convoy = service.dispatch(self.character_id, self._payload(), now=self.now + 1)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_citizens SET satiety=1,satiety_progress=0,
                   satiety_updated_at=%s WHERE id=%s""",
                (self.now + 1, self.driver_id),
            )

        CityPopulation(self.database).tick_all(now=self.now + 102)

        returning = next(
            row for row in service.get_world_convoys(self.character_id, now=self.now + 102)
            if row["id"] == convoy["id"]
        )
        self.assertFalse(returning["pinned"])
        self.assertEqual(returning["phase"], "returning")
        self.assertEqual(returning["direction"], "returning")

    def test_starving_driver_is_not_offered_or_dispatchable(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_citizens SET satiety=10,satisfaction='starving' WHERE id=%s",
                (self.driver_id,),
            )
        stable = self.production.get_state(self.character_id, "stable", now=self.now + 2)
        self.assertNotIn(self.driver_id, [row["id"] for row in stable["available_cart_drivers"]])
        with self.assertRaisesRegex(ValueError, "свободным, сытым"):
            TransportService(self.database).dispatch(
                self.character_id, self._payload(), now=self.now + 3,
            )


if __name__ == "__main__":
    unittest.main()
