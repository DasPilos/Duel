import time
import unittest

from server.city_population import CityPopulation, food_tick_forecast, meal_plan
from server.database import SYSTEM_USER_ID
from server.items_database import ItemsDatabase
from server.production_buildings import ProductionBuildings
from tests.fixtures import create_test_database, drop_test_database, running_server


class CityPopulationTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.items = ItemsDatabase(self.database)
        user = self.database.register("city-overseer", "password")
        self.character_id = self.database.create_character(user["id"], "Overseer")["id"]
        self.city = CityPopulation(self.database)

    def tearDown(self):
        drop_test_database(self.database)

    def test_castle_starts_with_four_citizens_and_level_one_capacity_ten(self):
        state = self.city.get_state(self.character_id)
        self.assertEqual(state["castle_name"], "Замок Радбурка")
        self.assertEqual(state["castle_level"], 1)
        self.assertEqual((state["population"], state["population_capacity"]), (4, 10))
        self.assertTrue(all(citizen["satiety"] == 100 for citizen in state["citizens"]))
        self.assertEqual(state["worksites"][0]["building"], "farm")

    def test_full_meal_matches_requested_food_values(self):
        self.assertEqual(
            meal_plan(100, {"wheat": 3, "berries": 2, "meat": 2}),
            {"wheat": 3, "berries": 2, "meat": 2},
        )

    def test_full_meal_uses_only_wheat_when_other_food_is_unavailable(self):
        self.assertEqual(
            meal_plan(100, {"wheat": 10, "berries": 0, "meat": 0}),
            {"wheat": 10, "berries": 0, "meat": 0},
        )

    def test_food_tick_forecast_covers_sufficient_partial_and_hunger_states(self):
        citizens = [
            {"satiety": 100, "satiety_updated_at": 0, "hunger_streak": 0}
            for _ in range(4)
        ]
        enough = food_tick_forecast(
            citizens, {"wheat": 100, "berries": 100, "meat": 100}, 0, 10
        )
        partial = food_tick_forecast(
            citizens, {"wheat": 32, "berries": 0, "meat": 0}, 1800, 10
        )
        hungry = food_tick_forecast(
            citizens, {"wheat": 0, "berries": 0, "meat": 0}, 3600, 10
        )

        self.assertEqual(enough, ("Пищи достаточно", True, 400))
        self.assertEqual(partial, ("Население не доедает", False, 320))
        self.assertEqual(hungry[0], "В городе голод")
        self.assertEqual(hungry[2], 80)

    def test_satiety_decreases_by_one_per_minute(self):
        now = float(int(time.time() // 3600) * 3600 + 300)
        self.city.get_state(self.character_id, now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (now, self.database.world_id),
            )
        state = self.city.get_state(self.character_id, now)
        self.assertEqual(state["citizens"][0]["satiety"], 100)

        state = self.city.get_state(self.character_id, now + 60)

        self.assertEqual(state["citizens"][0]["satiety"], 99)

    def test_hourly_tick_feeds_citizens_and_grows_city_with_food_reserve(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        tick_at = int(now // 3600) * 3600
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at = %s WHERE world_id = %s AND faction = 'light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                """UPDATE building_resources SET storage = 100
                   WHERE world_id = %s AND faction = 'light' AND building = 'barn' AND resource IN ('wheat','berries','meat')""",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 5)
        self.assertEqual(state["food_status"], "Пищи достаточно")
        self.assertIsNotNone(state["new_citizen_eta_seconds"])
        expected_satiety = max(0, 100 - int((now - tick_at) // 60))
        self.assertTrue(all(citizen["satiety"] == expected_satiety for citizen in state["citizens"]))
        self.assertEqual(state["food_storage"], {"wheat": 88, "berries": 92, "meat": 92})

    def test_population_growth_does_not_reset_existing_workers_or_travel(self):
        tick_at = float(int(time.time() // 3600 + 1) * 3600)
        assign_at = tick_at - 300
        self.city._travel_distances = {"farm": 50, "lumber_camp": 50}
        state = self.city.get_state(self.character_id, assign_at)
        citizen_ids = [state["citizens"][0]["id"], state["citizens"][1]["id"]]
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (tick_at, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=100 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )
        self.city.assign_citizen(self.character_id, citizen_ids[0], "farm", 0, assign_at)
        self.city.assign_citizen(self.character_id, citizen_ids[1], "lumber_camp", 0, assign_at)

        state = self.city.get_state(self.character_id, tick_at + 1)

        self.assertEqual(state["population"], 5)
        for citizen_id, building in zip(citizen_ids, ("farm", "lumber_camp")):
            citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
            self.assertEqual(citizen["job_building"], building)
            self.assertEqual(citizen["work_status"], "В пути")
            self.assertEqual(citizen["travel_seconds_left"], 299)
        farm_state = self.city.production.get_state(self.character_id, "farm", tick_at + 1)
        farm_worker = farm_state["worker_slots"][0]
        self.assertTrue(farm_worker["is_travelling"])
        self.assertEqual(farm_worker["travel_seconds_left"], 299)
        self.assertEqual(farm_worker["resource_progress_sec"]["wheat"], 0)
        new_citizen = next(row for row in state["citizens"] if row["id"] not in citizen_ids
                           and row["job_building"] is None)
        self.assertEqual(new_citizen["work_status"], "Свободен")

    def test_hourly_tick_substitutes_available_wheat_for_a_full_meal(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        tick_at = int(now // 3600) * 3600
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 40 ELSE 0 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 4)
        self.assertEqual(state["food_storage"], {"wheat": 0, "berries": 0, "meat": 0})
        expected_satiety = max(0, 100 - int((now - tick_at) // 60))
        self.assertTrue(all(citizen["satiety"] == expected_satiety for citizen in state["citizens"]))

    def test_population_never_falls_below_four_and_departure_is_announced_above_minimum(self):
        state = self.city.get_state(self.character_id)
        key = (self.database.world_id, "light")
        now = time.time()
        with self.database.connection() as connection:
            connection.execute(
                """INSERT INTO city_citizens
                   (world_id, faction, ordinal, name, satiety, hunger_streak, satisfaction, created_at)
                   VALUES (%s, 'light', 5, 'Пятый', 0, 1, 'irritated', %s)""",
                (self.database.world_id, now),
            )
            connection.execute(
                "UPDATE city_citizens SET satiety=0,hunger_streak=1,satisfaction='irritated' WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s WHERE world_id=%s AND faction='light'",
                (now - 3600, self.database.world_id),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 4)
        with self.database.connection() as connection:
            announcement = connection.execute(
                "SELECT COUNT(*) AS amount FROM chat_messages WHERE world_id=%s AND location='city' AND text LIKE %s",
                (self.database.world_id, "Горожанин покинул город (-1):%"),
            ).fetchone()["amount"]
        self.assertEqual(announcement, 1)
        self.assertEqual(len(state["citizens"]), 4)

    def test_hourly_taxes_follow_citizen_satisfaction_status(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        tick_at = int(now // 3600) * 3600
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s,treasury_copper=0 WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=100,satiety_updated_at=%s,hunger_streak=0
                   WHERE world_id=%s AND faction='light' AND ordinal IN (1,4)""",
                (tick_at, self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=0,satiety_updated_at=%s,hunger_streak=0
                   WHERE world_id=%s AND faction='light' AND ordinal=2""",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=0,satiety_updated_at=%s,hunger_streak=1
                   WHERE world_id=%s AND faction='light' AND ordinal=3""",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["treasury_copper"], 220)

    def test_fully_fed_citizens_recover_mood_and_green_tax_rate(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        tick_at = int(now // 3600) * 3600
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s,treasury_copper=0 WHERE world_id=%s AND faction='light'",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=30,satiety_updated_at=%s,
                   hunger_streak=2,satisfaction='starving' WHERE world_id=%s AND faction='light'""",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                """UPDATE building_resources SET storage=CASE resource
                     WHEN 'wheat' THEN 12 WHEN 'berries' THEN 8 WHEN 'meat' THEN 8 END
                   WHERE world_id=%s AND faction='light' AND building='barn'
                     AND resource IN ('wheat','berries','meat')""",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertTrue(all(citizen["satiety"] == 100 for citizen in state["citizens"]))
        self.assertTrue(all(citizen["satisfaction"] == "satisfied" for citizen in state["citizens"]))
        self.assertEqual(state["treasury_copper"], 400)

    def test_player_can_deposit_and_withdraw_city_treasury(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET silver=2,copper=10,gold=0 WHERE id=%s",
                (self.character_id,),
            )

        deposited = self.city.transfer_treasury(self.character_id, "deposit", 110)

        self.assertEqual(deposited["treasury_copper"], 110)
        self.assertEqual(deposited["personal_currency_copper"], 100)
        withdrawn = self.city.transfer_treasury(self.character_id, "withdraw", 25)

        self.assertEqual(withdrawn["treasury_copper"], 85)
        self.assertEqual(withdrawn["personal_currency_copper"], 125)

    def test_assigned_citizen_uses_worker_slot_and_can_return(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        self.city._travel_distances = {"farm": 1}
        citizen_id = state["citizens"][0]["id"]
        state = self.city.assign_citizen(self.character_id, citizen_id, "farm", 0, now)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
        self.assertEqual(citizen["work_status"], "В пути")
        self.assertEqual(citizen["travel_seconds_left"], 12)

        farm = ProductionBuildings(self.database).get_state(self.character_id, "farm", now)
        self.assertEqual(farm["worker_slots"][0]["worker_id"], f"citizen:{citizen_id}")
        self.assertEqual(farm["worker_slots"][0]["worker_name"], citizen["name"])

        state = self.city.recall_citizen(self.character_id, citizen_id, now)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
        self.assertEqual(citizen["work_status"], "Возвращается")
        self.assertEqual(citizen["travel_seconds_left"], 1)

        state = self.city.get_state(self.character_id, now + 24)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
        self.assertEqual(citizen["work_status"], "Свободен")

    def test_legacy_production_workers_are_counted_as_castle_citizens(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        production = ProductionBuildings(self.database)
        production.hire_worker(self.character_id, "farm", 0, "citizen-1", now)
        production.hire_worker(self.character_id, "farm", 1, "citizen-2", now)

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 4)
        assigned = [citizen for citizen in state["citizens"] if citizen["job_building"] == "farm"]
        self.assertEqual(len(assigned), 2)
        farm = production.get_state(self.character_id, "farm", now)
        self.assertEqual(
            [slot["worker_id"] for slot in farm["worker_slots"]],
            [f"citizen:{citizen['id']}" for citizen in assigned],
        )

    def test_authenticated_api_loads_assigns_and_recalls_citizen(self):
        with running_server(self.database) as client:
            client.timeout = 15
            client.login("city-overseer", "password")
            state = client.get_city_population(self.character_id)
            self.assertEqual(state["population"], 4)

            citizen_id = state["citizens"][0]["id"]
            state = client.assign_city_citizen(self.character_id, citizen_id, "farm", 0)
            citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
            self.assertEqual(citizen["work_status"], "В пути")

            state = client.recall_city_citizen(self.character_id, citizen_id)
            citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
            self.assertEqual(citizen["work_status"], "Возвращается")

            with self.database.connection() as connection:
                connection.execute(
                    "UPDATE characters SET copper=0,silver=1,gold=0 WHERE id=%s",
                    (self.character_id,),
                )
            state = client.transfer_city_treasury(self.character_id, "deposit", 50)
            self.assertEqual(state["treasury_copper"], 50)
            self.assertEqual(state["personal_currency_copper"], 50)

    def test_world_traveling_citizens_are_shared_between_players(self):
        observers = []
        for profession, character_name in (("archer", "Archer"), ("battle_mage", "Mage")):
            observer = self.database.register(f"city-map-{profession}", "password")
            observer_character = self.database.create_character(
                observer["id"], character_name, profession
            )
            observers.append((f"city-map-{profession}", observer_character["id"]))

        with running_server(self.database) as owner_client:
            owner_client.timeout = 15
            owner_client.login("city-overseer", "password")
            state = owner_client.get_city_population(self.character_id)
            citizen_id = state["citizens"][0]["id"]
            owner_client.assign_city_citizen(self.character_id, citizen_id, "farm", 0)

            owner_travelers = owner_client.get_world_traveling_citizens(self.character_id)
            snapshots = [owner_travelers]
            for username, observer_id in observers:
                observer_client = type(owner_client)(owner_client.base_url)
                observer_client.login(username, "password")
                snapshots.append(
                    observer_client.get_world_traveling_citizens(observer_id)
                )

        owner_citizen = next(row for row in owner_travelers if row["id"] == citizen_id)
        for snapshot in snapshots:
            traveler = next(row for row in snapshot if row["id"] == citizen_id)
            self.assertEqual(traveler["travel_direction"], "outbound")
            self.assertGreater(traveler["travel_total_seconds"], 0)
            self.assertGreaterEqual(traveler["eta_seconds"], 0)
            self.assertIsInstance(traveler["position_x"], float)
            self.assertIsInstance(traveler["position_y"], float)
            self.assertIn(traveler["position_direction"], {"n", "ne", "e", "se", "s", "sw", "w", "nw"})
            self.assertEqual(traveler["position_x"], owner_citizen["position_x"])
            self.assertEqual(traveler["position_y"], owner_citizen["position_y"])

    def test_system_user_is_not_counted_as_a_city_citizen(self):
        state = self.city.get_state(self.character_id)
        self.assertEqual(state["population"], 4)
        self.assertGreater(self.database.get_character_for_battle(self.character_id)["user_id"], SYSTEM_USER_ID)


if __name__ == "__main__":
    unittest.main()
