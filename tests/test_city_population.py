import json
import math
import time
import unittest

from server.city_population import CityPopulation, wheat_reserve_zone
from server.database import SYSTEM_USER_ID
from server.items_database import ItemsDatabase
from server.production_buildings import ProductionBuildings
from tests.fixtures import create_test_database, drop_test_database, running_server, seed_city_treasury


def _upgrade_by_id(state, upgrade_id):
    return next(row for row in state["upgrades"] if row["id"] == upgrade_id)


class CityPopulationTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.items = ItemsDatabase(self.database)
        user = self.database.register("city-overseer", "password")
        self.character_id = self.database.create_character(user["id"], "Overseer")["id"]
        self.city = CityPopulation(self.database)

    def tearDown(self):
        drop_test_database(self.database)

    def _set_city_level(self, level):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET city_level=%s WHERE world_id=%s AND faction='light'",
                (int(level), self.database.world_id),
            )

    def test_wheat_reserve_zones_match_storage_fill_boundaries(self):
        self.assertEqual(wheat_reserve_zone(200, 1000), "red")
        self.assertEqual(wheat_reserve_zone(201, 1000), "yellow")
        self.assertEqual(wheat_reserve_zone(400, 1000), "yellow")
        self.assertEqual(wheat_reserve_zone(401, 1000), "green")
        self.assertEqual(wheat_reserve_zone(1000, 1000), "green")

    def test_red_satiety_exposes_two_hour_death_countdown(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        citizen_id = state["citizens"][0]["id"]
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_citizens SET satiety=10,satiety_progress=0,
                   satiety_updated_at=%s,satiety_zero_since=NULL WHERE id=%s""",
                (now, citizen_id),
            )

        state = self.city.get_state(self.character_id, now)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)

        self.assertEqual(citizen["death_eta_seconds"], 8700)

    def test_castle_starts_with_four_citizens_and_level_one_capacity_ten(self):
        state = self.city.get_state(self.character_id)
        self.assertEqual(state["castle_name"], "Замок Радбурка")
        self.assertEqual(state["castle_level"], 1)
        self.assertEqual((state["population"], state["population_capacity"]), (4, 10))
        self.assertTrue(all(citizen["satiety"] == 100 for citizen in state["citizens"]))
        self.assertEqual(state["worksites"][0]["building"], "farm")

    def test_city_level_two_keeps_castle_level_one(self):
        self._set_city_level(2)
        state = self.city.get_state(self.character_id)
        self.assertEqual(state["castle_level"], 1)
        self.assertEqual(state["city_upgrade"]["city_level"], 2)
        self.assertEqual(state["population_capacity"], 14)

    def test_governor_lists_newly_unlocked_stone_before_it_is_stocked(self):
        self._set_city_level(2)
        state = self.city.get_state(self.character_id)

        self.assertIn("stone", state["city_resource_storage"])
        self.assertEqual(state["city_resource_storage"]["stone"], 0)
        self.assertIn("stone", state["city_resource_income_per_hour"])
        self.assertIn("stone", state["city_resource_trend"])

    def test_governor_counts_stone_from_mountain_rift_workers(self):
        self._set_city_level(2)
        now = 10000
        self.city.get_state(self.character_id, now)
        self.city.production.hire_worker(
            self.character_id, "mountain_rift", 0, f"player:{self.character_id}", now,
        )
        state = self.city.get_state(self.character_id, now + 1)

        self.assertAlmostEqual(state["city_resource_income_per_hour"]["stone"], 3600 / 200)
        self.assertEqual(state["city_resource_trend"]["stone"], "surplus")

    def test_governor_hourly_consumption_includes_horses_and_unlocked_foods(self):
        now = time.time()
        self.city.get_state(self.character_id, now=now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 1000, self.character_id)
        horse_state = ProductionBuildings(self.database).purchase_horse(
            self.character_id, 0, now=now + 1,
        )
        self.assertEqual(horse_state["stall_slots"][0]["horse"]["status"], "Отдыхает")
        resting = self.city.get_state(self.character_id, now=now + 1)
        self.assertEqual(resting["food_consumption_per_hour"], {"wheat": 12.0})

        with self.database.connection() as connection:
            connection.execute(
                "UPDATE stable_horses SET status='В пути' WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        travelling = self.city.get_state(self.character_id, now=now + 2)
        self.assertEqual(travelling["food_consumption_per_hour"], {"wheat": 15.6})

        self._set_city_level(2)
        leveled = self.city.get_state(self.character_id, now=now + 3)
        self.assertIn("wheat", leveled["food_consumption_per_hour"])
        self.assertNotIn("berries", leveled["food_consumption_per_hour"])
        self.assertNotIn("meat", leveled["food_consumption_per_hour"])

    def test_governor_reports_food_income_and_weighted_trend(self):
        now = 10000
        state = self.city.get_state(self.character_id, now)
        self.assertEqual(state["food_income_per_hour"]["wheat"], 0)
        self.assertEqual(state["food_trend"]["wheat"], "deficit")

        self.city.production.hire_worker(
            self.character_id, "farm", 0, f"player:{self.character_id}", now,
        )
        state = self.city.get_state(self.character_id, now + 1)
        self.assertAlmostEqual(state["food_income_per_hour"]["wheat"], 3600 / 140)
        self.assertEqual(state["food_trend"]["wheat"], "surplus")

        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=160
                   WHERE world_id=%s AND faction='light' AND building='barn' AND resource='wheat'""",
                (self.database.world_id,),
            )
        state = self.city.get_state(self.character_id, now + 2)
        self.assertEqual(state["food_trend"]["wheat"], "upgrade_ready")

    def test_governor_reports_wood_income_and_city_upgrade_drain(self):
        now = 10000
        self.city.get_state(self.character_id, now)
        self.city.production.hire_worker(
            self.character_id, "lumber_camp", 0, f"player:{self.character_id}", now,
        )
        state = self.city.get_state(self.character_id, now + 1)
        self.assertAlmostEqual(state["city_resource_income_per_hour"]["wood"], 15)
        self.assertEqual(state["city_resource_consumption_per_hour"].get("wood", 0), 0)
        self.assertEqual(state["city_resource_trend"]["wood"], "surplus")

        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=710
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
        state = self.city.get_state(self.character_id, now + 2)
        self.assertEqual(state["city_resource_trend"]["wood"], "upgrade_ready")

        cycle = {
            "active": True,
            "drain_formula": "population_capacity",
            "started_at": now + 10,
            "finish_at": now + 3610,
            "tick_index": 0,
            "population": 4,
            "population_capacity": 10,
            "resources": {"wood": {"per_tick": 40}},
        }
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_population_state SET city_upgrade_cycle=%s::jsonb
                   WHERE world_id=%s AND faction='light'""",
                (json.dumps(cycle), self.database.world_id),
            )
        state = self.city.get_state(self.character_id, now + 3)
        self.assertEqual(state["city_resource_consumption_per_hour"]["wood"], 160)
        self.assertEqual(state["city_resource_trend"]["wood"], "deficit")

    def test_citizens_eat_only_wheat(self):
        from server.city_population import food_consumption_per_hour

        citizens = [{"work_status": "Свободен"}, {"work_status": "Занят"}]
        consumption = food_consumption_per_hour(citizens, ["wheat", "berries", "meat"])
        self.assertEqual(set(consumption), {"wheat"})
        self.assertEqual(food_consumption_per_hour(citizens, ["berries", "meat"]), {})
    def test_idle_satiety_decreases_by_one_percent_every_150_seconds(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (now, self.database.world_id),
            )
        state = self.city.get_state(self.character_id, now + 149)
        self.assertEqual(state["citizens"][0]["satiety"], 100)

        state = self.city.get_state(self.character_id, now + 150)

        self.assertEqual(state["citizens"][0]["satiety"], 99)

    def test_work_and_travel_use_their_own_satiety_rates(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        working_id, traveling_id = [row["id"] for row in state["citizens"][:2]]
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=0""",
                (f"citizen:{working_id}", self.database.world_id),
            )
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=1""",
                (f"citizen:{traveling_id}", self.database.world_id),
            )
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=0""",
                (f"citizen:{working_id}", self.database.world_id),
            )
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=1""",
                (f"citizen:{traveling_id}", self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=100,satiety_progress=0,
                   satiety_updated_at=%s,working=TRUE,job_building='farm',job_slot=0,
                   travel_direction=NULL,arrival_at=NULL WHERE id=%s""",
                (now, working_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=100,satiety_progress=0,
                   satiety_updated_at=%s,working=TRUE,job_building='farm',job_slot=1,
                   travel_direction='outbound',arrival_at=%s WHERE id=%s""",
                (now, now + 500, traveling_id),
            )

        state = self.city.get_state(self.character_id, now + 100)
        citizens = {row["id"]: row for row in state["citizens"]}
        self.assertEqual(citizens[working_id]["satiety"], 99)
        self.assertEqual(citizens[traveling_id]["satiety"], 99)

    def test_one_citizen_eats_when_reaching_thirty_percent(self):
        now = time.time()
        self._set_city_level(3)
        state = self.city.get_state(self.character_id, now)
        citizen_id = state["citizens"][0]["id"]
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_citizens SET satiety=100,satiety_progress=0,satiety_updated_at=%s WHERE world_id=%s AND faction='light'",
                (now, self.database.world_id),
            )
            connection.execute(
                "UPDATE city_citizens SET satiety=31 WHERE id=%s", (citizen_id,),
            )
            connection.execute(
                "UPDATE building_resources SET storage=CASE resource WHEN 'wheat' THEN 7 ELSE 5 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now + 150)

        citizens = {row["id"]: row for row in state["citizens"]}
        self.assertEqual(citizens[citizen_id]["satiety"], 100)
        self.assertEqual(sum(row["satiety"] for row in state["citizens"] if row["id"] != citizen_id), 3 * 99)
        self.assertEqual(state["food_storage"], {"wheat": 0, "berries": 5, "meat": 5})

    def test_level_one_city_does_not_consume_locked_barn_food(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_resources SET storage=10 WHERE world_id=%s AND faction='light'
                   AND building='barn' AND resource IN ('berries','meat')""",
                (self.database.world_id,),
            )
        with self.database.connection() as connection:
            self.assertEqual(
                self.city._food_stock(connection, self.database.world_id), {"wheat": 0}
            )

    def test_food_replaces_strong_hunger_with_partial_satiety(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        citizen_id = state["citizens"][0]["id"]
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_citizens SET satiety=0,satiety_progress=0,
                         strong_hunger=99,strong_hunger_progress=0,satiety_updated_at=%s WHERE id=%s""",
                (now, citizen_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 1 ELSE 0 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)

        self.assertEqual(citizen["satiety"], 10)
        self.assertEqual(citizen["strong_hunger"], 0)

    def test_zero_satiety_returns_worker_and_dies_after_two_hours(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        citizen_id = state["citizens"][0]["id"]
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_citizens SET satiety=1,satiety_progress=0,
                   satiety_updated_at=%s,working=TRUE,job_building='farm',job_slot=0,
                   travel_direction=NULL,arrival_at=NULL WHERE id=%s""",
                (now, citizen_id),
            )
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s,hire_time=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=0""",
                (f"citizen:{citizen_id}", now, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s WHERE world_id=%s AND faction='light'",
                (now + 10000, self.database.world_id),
            )

        state = self.city.get_state(self.character_id, now + 60)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
        self.assertEqual(citizen["satiety"], 0)
        self.assertEqual(citizen["travel_direction"], "returning")
        self.assertEqual(citizen["strong_hunger"], 0)
        state = self.city.get_state(self.character_id, now + 60 + 2 * 60 * 60 + 1)

        self.assertEqual(state["population"], 3)
        with self.database.connection() as connection:
            alive = connection.execute(
                "SELECT alive FROM city_citizens WHERE id=%s", (citizen_id,),
            ).fetchone()["alive"]
        self.assertFalse(alive)

    def test_hourly_tick_grows_city_when_wheat_is_in_green_zone(self):
        now = time.time()
        state = self.city.get_state(self.character_id, now)
        self._set_city_level(3)
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
                     """UPDATE building_resources SET storage = CASE WHEN resource='wheat' THEN 410 ELSE 100 END
                   WHERE world_id = %s AND faction = 'light' AND building = 'barn' AND resource IN ('wheat','berries','meat')""",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 5)
        self.assertEqual(state["food_zone"], "green")
        self.assertEqual(state["food_status"], "в городе достаточно еды для роста")
        self.assertIsNotNone(state["new_citizen_eta_seconds"])
        elapsed_percent = int((now - tick_at) // 150)
        self.assertTrue(all(citizen["satiety"] == 76 - elapsed_percent
                    for citizen in state["citizens"][:4]))
        self.assertEqual(state["citizens"][4]["satiety"], 100 - elapsed_percent)
        self.assertEqual(state["food_storage"], {"wheat": 410, "berries": 100, "meat": 100})

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
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 410 ELSE 100 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
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

    def test_green_wheat_zone_adds_one_citizen_per_hour(self):
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
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 500 ELSE 0 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["food_zone"], "green")
        self.assertEqual(state["population"], 5)

    def test_red_wheat_zone_removes_free_citizen_before_workers(self):
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
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 10 ELSE 0 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["food_zone"], "red")
        self.assertEqual(state["population"], 3)
        self.assertEqual(state["citizens"][0]["work_status"], "Свободен")

    def test_yellow_wheat_zone_does_not_grow_or_depart_population(self):
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
                "UPDATE building_resources SET storage=CASE WHEN resource='wheat' THEN 300 ELSE 0 END WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertEqual(state["population"], 4)
        self.assertEqual(state["food_zone"], "yellow")
        self.assertGreater(state["satiated_eta_seconds"], 0)
        self.assertEqual(state["food_storage"], {"wheat": 300})
        elapsed_percent = int((now - tick_at) // 150)
        self.assertTrue(all(citizen["satiety"] == 76 - elapsed_percent
                    for citizen in state["citizens"][:4]))

    def test_zero_satiety_for_two_hours_kills_citizens_and_announces_each_death(self):
        state = self.city.get_state(self.character_id)
        key = (self.database.world_id, "light")
        now = time.time()
        with self.database.connection() as connection:
            connection.execute(
                     """INSERT INTO city_citizens
                         (world_id, faction, ordinal, name, satiety, strong_hunger,
                          satisfaction, satiety_updated_at, satiety_zero_since, created_at)
                         VALUES (%s, 'light', 5, 'Пятый', 0, 99, 'starving', %s, %s, %s)""",
                     (self.database.world_id, now - 7200, now - 7200, now),
            )
            connection.execute(
                     """UPDATE city_citizens SET satiety=0,strong_hunger=99,
                         satiety_updated_at=%s,satiety_zero_since=%s,satisfaction='starving'
                         WHERE world_id=%s AND faction='light'""",
                     (now - 7200, now - 7200, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE city_population_state SET last_food_tick_at=%s WHERE world_id=%s AND faction='light'",
                (now + 3600, self.database.world_id),
            )

        state = self.city.get_state(self.character_id, now + 1)

        self.assertEqual(state["population"], 0)
        with self.database.connection() as connection:
            announcement = connection.execute(
                "SELECT COUNT(*) AS amount FROM chat_messages WHERE world_id=%s AND location='city' AND text LIKE %s",
                (self.database.world_id, "Горожанин умер от голода:%"),
            ).fetchone()["amount"]
        self.assertEqual(announcement, 5)
        self.assertEqual(len(state["citizens"]), 0)

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

        self.assertEqual(state["treasury_copper"], 100)

    def test_threshold_meal_refills_then_individual_decay_resumes(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self._set_city_level(3)
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
                     WHEN 'wheat' THEN 500 WHEN 'berries' THEN 8 WHEN 'meat' THEN 8 END
                   WHERE world_id=%s AND faction='light' AND building='barn'
                     AND resource IN ('wheat','berries','meat')""",
                (self.database.world_id,),
            )

        state = self.city.get_state(self.character_id, now)

        self.assertTrue(all(citizen["satiety"] == 76 for citizen in state["citizens"][:4]))
        self.assertEqual(state["citizens"][4]["satiety"], 100)
        self.assertTrue(all(citizen["satisfaction"] == "satisfied" for citizen in state["citizens"]))
        self.assertEqual(state["treasury_copper"], 200)
        self.assertEqual(
            state["food_storage"], {"wheat": 472, "berries": 8, "meat": 8}
        )

    def test_treasury_edict_debits_wood_and_silver_then_raises_tax_when_done(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self.city.production.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 1000, self.character_id)
            connection.execute(
                """UPDATE building_resources SET storage=100
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        started = self.city.start_treasury_edict(self.character_id, now)

        self.assertEqual(started["treasury_copper"], 1000 - 500)
        upgrade = _upgrade_by_id(started, "treasury_edict")
        self.assertTrue(upgrade["is_active"])
        self.assertFalse(upgrade["is_complete"])
        self.assertEqual(upgrade["seconds_left"], 4800)
        with self.database.connection() as connection:
            row = connection.execute(
                """SELECT storage FROM building_resources
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            ).fetchone()
        self.assertEqual(int(row["storage"]), 70)
        with self.assertRaises(ValueError):
            self.city.start_treasury_edict(self.character_id, now)

        finished = self.city.get_state(self.character_id, now + 4800)

        self.assertTrue(_upgrade_by_id(finished, "treasury_edict")["is_complete"])
        self.assertFalse(_upgrade_by_id(finished, "treasury_edict")["is_active"])
        self.assertEqual(
            finished["expected_tax_copper"],
            CityPopulation._tax_copper(finished["citizens"], edict_active=True),
        )
        self.assertGreater(
            finished["expected_tax_copper"],
            CityPopulation._tax_copper(finished["citizens"], edict_active=False),
        )
        with self.assertRaises(ValueError):
            self.city.start_treasury_edict(self.character_id, now + 4800)

    def test_plot_for_building_adds_capacity_once_per_castle_level(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self.city.production.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 10000, self.character_id)
            connection.execute(
                """UPDATE building_resources SET storage=100
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        started = self.city.start_castle_upgrade(self.character_id, "plot_for_building", now)

        plot = _upgrade_by_id(started, "plot_for_building")
        self.assertTrue(plot["is_active"])
        self.assertEqual(plot["seconds_left"], 6000)
        self.assertEqual(started["treasury_copper"], 10000 - 1000)
        self.assertEqual(len(started["castle_upgrades_active"]), 1)
        with self.database.connection() as connection:
            wood = connection.execute(
                """SELECT storage FROM building_resources
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            ).fetchone()
        self.assertEqual(int(wood["storage"]), 70)
        with self.assertRaises(ValueError):
            self.city.start_castle_upgrade(self.character_id, "plot_for_building", now)

        finished = self.city.get_state(self.character_id, now + 6000)

        self.assertTrue(_upgrade_by_id(finished, "plot_for_building")["is_complete"])
        self.assertEqual(finished["castle_upgrades_active"], [])
        self.assertEqual(finished["population_capacity"], 11)
        with self.assertRaises(ValueError):
            self.city.start_castle_upgrade(self.character_id, "plot_for_building", now + 6000)
        self.assertEqual(self.city.get_state(self.character_id, now + 6001)["population_capacity"], 11)

    def test_castle_upgrades_can_run_in_parallel(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self.city.production.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 10000, self.character_id)
            connection.execute(
                """UPDATE building_resources SET storage=100
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        self.city.start_castle_upgrade(self.character_id, "plot_for_building", now)
        started = self.city.start_treasury_edict(self.character_id, now)

        self.assertEqual({row["id"] for row in started["castle_upgrades_active"]},
                         {"plot_for_building", "treasury_edict"})

    def test_castle_upgrade_rejects_unknown_id(self):
        with self.assertRaises(ValueError):
            self.city.start_castle_upgrade(self.character_id, "no_such_upgrade")

    def test_castle_upgrade_list_contains_every_catalog_entry_for_level(self):
        state = self.city.get_state(self.character_id)
        ids = [row["id"] for row in state["upgrades"]]
        self.assertIn("plot_for_building", ids)
        self.assertIn("treasury_edict", ids)

    def test_treasury_edict_rejects_missing_wood_without_debiting_silver(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self.city.production.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 1000, self.character_id)
            connection.execute(
                """UPDATE building_resources SET storage=0
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )

        with self.assertRaises(ValueError):
            self.city.start_treasury_edict(self.character_id, now)

        state = self.city.get_state(self.character_id, now)
        self.assertEqual(state["treasury_copper"], 1000)
        self.assertFalse(state["upgrades"][0]["is_active"])

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

    def test_withdraw_is_limited_to_own_treasury_contribution(self):
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET silver=5,copper=0,gold=0 WHERE id=%s",
                (self.character_id,),
            )
        self.city.transfer_treasury(self.character_id, "deposit", 300)
        other = self.database.create_character(
            self.database.register("other-depositor", "password")["id"], "Other"
        )["id"]
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET silver=2,copper=0,gold=0 WHERE id=%s",
                (other,),
            )
        self.city.transfer_treasury(other, "deposit", 200)

        with self.assertRaisesRegex(ValueError, "твоих средств"):
            self.city.transfer_treasury(other, "withdraw", 201)

        state = self.city.transfer_treasury(other, "withdraw", 200)
        self.assertEqual(state["treasury_copper"], 300)
        self.assertEqual(state["personal_treasury_copper"], 0)

    def test_pre_migration_treasury_is_unassigned_and_not_withdrawable(self):
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 500, self.character_id)
            connection.execute(
                "DELETE FROM city_treasury_contributions WHERE world_id=%s",
                (self.database.world_id,),
            )
            connection.execute(
                "UPDATE characters SET silver=0,copper=0,gold=0 WHERE id=%s",
                (self.character_id,),
            )

        with self.assertRaisesRegex(ValueError, "твоих средств"):
            self.city.transfer_treasury(self.character_id, "withdraw", 1)

        state = self.city.get_state(self.character_id, time.time())
        self.assertEqual(state["treasury_copper"], 500)
        self.assertEqual(state["personal_treasury_copper"], 0)

    def _new_depositor(self, name, silver):
        user = self.database.register(name, "password")
        character_id = self.database.create_character(user["id"], name)["id"]
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE characters SET silver=%s,copper=0,gold=0 WHERE id=%s",
                (int(silver), character_id),
            )
        return character_id

    def test_mayor_is_largest_contributor_and_changes_on_deposit(self):
        rival = self._new_depositor("mayor-rival", 5)
        self.city.transfer_treasury(self.character_id, "deposit", 300)
        self.assertTrue(self.city.get_state(self.character_id, time.time())["is_mayor"])

        self.city.transfer_treasury(rival, "deposit", 400)

        self.assertTrue(self.city.get_state(rival, time.time())["is_mayor"])
        self.assertFalse(self.city.get_state(self.character_id, time.time())["is_mayor"])

    def test_mayor_keeps_role_on_tie(self):
        rival = self._new_depositor("tie-rival", 5)
        self.city.transfer_treasury(self.character_id, "deposit", 300)

        self.city.transfer_treasury(rival, "deposit", 300)

        self.assertTrue(self.city.get_state(self.character_id, time.time())["is_mayor"])
        self.assertFalse(self.city.get_state(rival, time.time())["is_mayor"])

    def test_mayor_spends_whole_treasury_and_others_only_their_contribution(self):
        rival = self._new_depositor("spend-rival", 5)
        self.city.transfer_treasury(self.character_id, "deposit", 300)
        self.city.transfer_treasury(rival, "deposit", 200)
        key = (self.database.world_id, "light")

        rival_state = self.city.get_state(rival, time.time())
        self.assertFalse(rival_state["is_mayor"])
        self.assertEqual(rival_state["spendable_treasury_copper"], 200)
        with self.database.connection() as connection:
            with self.assertRaisesRegex(ValueError, "твоих средств"):
                ProductionBuildings._debit_treasury(connection, key, 250, rival)

        mayor_state = self.city.get_state(self.character_id, time.time())
        self.assertTrue(mayor_state["is_mayor"])
        self.assertEqual(mayor_state["spendable_treasury_copper"], 500)
        with self.database.connection() as connection:
            ProductionBuildings._debit_treasury(connection, key, 400, self.character_id)

        state = self.city.get_state(rival, time.time())
        self.assertEqual(state["treasury_copper"], 100)
        self.assertEqual(state["personal_treasury_copper"], 40)
        self.assertFalse(state["is_mayor"])
        self.assertTrue(self.city.get_state(self.character_id, time.time())["is_mayor"])
        self.assertEqual(self._glory(self.character_id), 240)
        self.assertEqual(self._glory(rival), 160)

    def test_mayor_expense_is_drawn_pro_rata_with_largest_remainder_rounding(self):
        rival = self._new_depositor("rounding-rival", 5)
        third = self._new_depositor("rounding-third", 5)
        self.city.transfer_treasury(self.character_id, "deposit", 100)
        self.city.transfer_treasury(rival, "deposit", 100)
        self.city.transfer_treasury(third, "deposit", 50)
        key = (self.database.world_id, "light")

        with self.database.connection() as connection:
            ProductionBuildings._debit_treasury(connection, key, 7, self.character_id)

        # Exact shares of 7 over 100:100:50 are 2.8 / 2.8 / 1.4. Floors are 2 / 2 / 1,
        # and the 2 leftover copper goes to the largest remainders, so the totals still match 7.
        spent = {
            self.character_id: 100 - self.city.get_state(self.character_id, time.time())["personal_treasury_copper"],
            rival: 100 - self.city.get_state(rival, time.time())["personal_treasury_copper"],
            third: 50 - self.city.get_state(third, time.time())["personal_treasury_copper"],
        }
        self.assertEqual(sum(spent.values()), 7)
        self.assertIn(spent[self.character_id], (2, 3))
        self.assertIn(spent[rival], (2, 3))
        self.assertIn(spent[third], (1, 2))
        self.assertEqual(self._glory(self.character_id), spent[self.character_id])
        self.assertEqual(self._glory(rival), spent[rival])
        self.assertEqual(self._glory(third), spent[third])
        self.assertEqual(self.city.get_state(self.character_id, time.time())["treasury_copper"], 243)

    def test_mayor_spend_beyond_contributions_goes_to_faction_glory(self):
        self.city.transfer_treasury(self.character_id, "deposit", 100)
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE city_population_state SET treasury_copper=500 WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            )
        key = (self.database.world_id, "light")

        with self.database.connection() as connection:
            ProductionBuildings._debit_treasury(connection, key, 300, self.character_id)

        state = self.city.get_state(self.character_id, time.time())
        self.assertEqual(state["treasury_copper"], 200)
        self.assertEqual(state["personal_treasury_copper"], 0)
        self.assertEqual(self._glory(self.character_id), 100)
        self.assertEqual(self._faction_glory("light"), 200)

    def test_non_mayor_spend_from_own_contribution_awards_glory(self):
        rival = self._new_depositor("glory-rival", 5)
        self.city.transfer_treasury(self.character_id, "deposit", 300)
        self.city.transfer_treasury(rival, "deposit", 50)
        key = (self.database.world_id, "light")

        with self.database.connection() as connection:
            ProductionBuildings._debit_treasury(connection, key, 30, rival)

        self.assertEqual(self.city.get_state(rival, time.time())["personal_treasury_copper"], 20)
        self.assertEqual(self._glory(rival), 30)
        self.assertEqual(self._glory(self.character_id), 0)
        self.assertEqual(self._faction_glory("light"), 0)

    def _faction_glory(self, faction):
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT points FROM faction_glory WHERE world_id=%s AND faction=%s",
                (self.database.world_id, faction),
            ).fetchone()
        return 0 if row is None else int(row["points"])

    def _glory(self, character_id):
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT points FROM character_glory WHERE world_id=%s AND character_id=%s",
                (self.database.world_id, character_id),
            ).fetchone()
        return 0 if row is None else int(row["points"])

    def test_hourly_tax_is_split_pro_rata_between_contributors(self):
        now = time.time()
        self.city.get_state(self.character_id, now)
        other = self.database.create_character(
            self.database.register("tax-partner", "password")["id"], "Partner"
        )["id"]
        tick_at = int(now // 3600) * 3600
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE city_population_state SET last_food_tick_at=%s,treasury_copper=100
                   WHERE world_id=%s AND faction='light'""",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "DELETE FROM city_treasury_contributions WHERE world_id=%s",
                (self.database.world_id,),
            )
            connection.execute(
                """INSERT INTO city_treasury_contributions
                   (world_id, faction, character_id, contributed_copper)
                   VALUES (%s,'light',%s,60),(%s,'light',%s,40)""",
                (self.database.world_id, self.character_id, self.database.world_id, other),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=100,satiety_updated_at=%s,hunger_streak=0
                   WHERE world_id=%s AND faction='light'""",
                (tick_at, self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET satiety=0,satiety_updated_at=%s,hunger_streak=0
                   WHERE world_id=%s AND faction='light' AND ordinal=2""",
                (tick_at - 3600, self.database.world_id),
            )
            connection.execute(
                "UPDATE building_resources SET storage=0 WHERE world_id=%s AND faction='light' AND building='barn' AND resource IN ('wheat','berries','meat')",
                (self.database.world_id,),
            )

        self.city.get_state(self.character_id, now)

        with self.database.connection() as connection:
            rows = connection.execute(
                """SELECT character_id, contributed_copper FROM city_treasury_contributions
                   WHERE world_id=%s""",
                (self.database.world_id,),
            ).fetchall()
            treasury = connection.execute(
                "SELECT treasury_copper FROM city_population_state WHERE world_id=%s AND faction='light'",
                (self.database.world_id,),
            ).fetchone()["treasury_copper"]
        contributed = {int(r["character_id"]): int(r["contributed_copper"]) for r in rows}
        tax = int(treasury) - 100
        self.assertGreater(tax, 0)
        mine_tax = contributed[self.character_id] - 60
        theirs_tax = contributed[other] - 40
        self.assertEqual(mine_tax + theirs_tax, tax)
        self.assertAlmostEqual(mine_tax, tax * 0.6, delta=1)
        self.assertAlmostEqual(theirs_tax, tax * 0.4, delta=1)

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

    def test_population_clears_replaced_citizen_assignment(self):
        now = 10000
        state = self.city.get_state(self.character_id, now)
        citizen_id = state["citizens"][0]["id"]
        with self.database.connection() as connection:
            connection.execute(
                """UPDATE building_worker_slots SET occupied=1,worker_id=%s
                   WHERE world_id=%s AND faction='light' AND building='farm' AND slot_index=0""",
                (f"player:{self.character_id}", self.database.world_id),
            )
            connection.execute(
                """UPDATE city_citizens SET job_building='farm',job_slot=0,working=TRUE,
                   arrival_at=%s,travel_direction='outbound' WHERE id=%s""",
                (now + 3600, citizen_id),
            )

        state = self.city.get_state(self.character_id, now + 1)
        citizen = next(row for row in state["citizens"] if row["id"] == citizen_id)
        farm = next(site for site in state["worksites"] if site["building"] == "farm")
        self.assertIsNone(citizen["job_building"])
        self.assertEqual(citizen["work_status"], "Свободен")
        self.assertEqual(farm["free_slots"], [1])

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
        for profession, character_name in (("archer", "Archer"), ("mage", "Mage")):
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
        with self.database.connection() as connection:
            owner_row = connection.execute(
                "SELECT user_id FROM characters WHERE id = %s",
                (self.character_id,),
            ).fetchone()
        self.assertGreater(owner_row["user_id"], SYSTEM_USER_ID)

    def test_get_state_exposes_active_castle_upgrade_until_edict_finishes(self):
        now = float(int(time.time() // 3600) * 3600 + 30)
        self.city.get_state(self.character_id, now)
        self.city.production.get_state(self.character_id, "warehouse", now)
        with self.database.connection() as connection:
            seed_city_treasury(connection, self.database.world_id, 1000, self.character_id)
            connection.execute(
                """UPDATE building_resources SET storage=100
                   WHERE world_id=%s AND faction='light' AND building='warehouse' AND resource='wood'""",
                (self.database.world_id,),
            )
        self.assertFalse(self.city.get_state(self.character_id, now)["castle_upgrade"]["active"])

        self.city.start_treasury_edict(self.character_id, now)
        running = self.city.get_state(self.character_id, now + 1)["castle_upgrade"]
        self.assertTrue(running["active"])
        self.assertEqual(running["upgrade_name"], "Казначейский указ")
        self.assertEqual(running["finish_at"], now + 4800)

        finished = self.city.get_state(self.character_id, now + 4801)["castle_upgrade"]
        self.assertFalse(finished["active"])


if __name__ == "__main__":
    unittest.main()
