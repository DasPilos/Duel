"""Shared city citizens, hourly food consumption, and work assignments."""

import itertools
import math
import time

from core.currency import Currency
from core.production_buildings import BUILDINGS, building_level_info
from server.database import Database, lock_character
from server.production_buildings import DEFAULT_FACTION, ProductionBuildings

MIN_POPULATION = 4
BASE_POPULATION_CAPACITY = 10
FULL_MEAL_NUTRITION = 100
FOOD_VALUE = {"wheat": 10, "berries": 15, "meat": 20}
FOOD_SHARE = {"wheat": 3, "berries": 3, "meat": 4}
WORK_BUILDINGS = ("farm", "lumber_camp", "mountain_rift", "barnyard", "black_pit")
ROAD_BUILDINGS = {
    "wheat_farm": "farm",
    "lumber_camp": "lumber_camp",
    "mountain_rift": "mountain_rift",
    "barnyard": "barnyard",
    "black_pit": "black_pit",
}


def hour_boundary(timestamp):
    return math.floor(float(timestamp) / 3600) * 3600


def meal_plan(needed, available):
    """Choose a balanced ration, preferring exact satiety without wasting food."""
    needed = max(0, int(needed))
    if not needed:
        return {food: 0 for food in FOOD_VALUE}
    foods = tuple(FOOD_VALUE)
    limits = [min(max(0, int(available.get(food, 0))), math.ceil(needed / FOOD_VALUE[food]))
              for food in foods]
    best_score = None
    best = {food: 0 for food in foods}
    for amounts in itertools.product(*(range(limit + 1) for limit in limits)):
        nutrition = [amount * FOOD_VALUE[food] for food, amount in zip(foods, amounts)]
        total = sum(nutrition)
        if total > needed:
            continue
        balance_error = sum(
            abs(value * sum(FOOD_SHARE.values()) - total * FOOD_SHARE[food])
            for food, value in zip(foods, nutrition)
        )
        score = (total, -balance_error, -sum(amounts), *(-amount for amount in amounts))
        if best_score is None or score > best_score:
            best_score = score
            best = dict(zip(foods, amounts))
    return best


def post_meal_state(satiety, hunger_streak, nutrition):
    satiety = min(FULL_MEAL_NUTRITION, max(0, int(satiety)) + max(0, int(nutrition)))
    incomplete_meals = int(hunger_streak) + 1 if satiety < FULL_MEAL_NUTRITION else 0
    if satiety >= FULL_MEAL_NUTRITION:
        satisfaction = "satisfied"
    elif incomplete_meals >= 2 and satiety < 50:
        satisfaction = "starving"
    else:
        satisfaction = "irritated"
    return satiety, incomplete_meals, satisfaction


def food_tick_forecast(citizens, stock, tick_at, capacity):
    remaining_stock = {food: max(0, int(stock.get(food, 0))) for food in FOOD_VALUE}
    projected_satiety = []
    unhappy = False
    expected_tax_copper = 0
    remaining_population = len(citizens)
    for citizen in citizens:
        elapsed_minutes = max(
            0, int((float(tick_at) - float(citizen["satiety_updated_at"])) // 60)
        )
        satiety = max(0, int(citizen["satiety"]) - elapsed_minutes)
        plan = meal_plan(FULL_MEAL_NUTRITION, remaining_stock)
        nutrition = 0
        for food, amount in plan.items():
            remaining_stock[food] -= amount
            nutrition += amount * FOOD_VALUE[food]
        post_satiety, streak, mood = post_meal_state(
            satiety, citizen["hunger_streak"], nutrition
        )
        expected_tax_copper += {"satisfied": 100, "irritated": 20, "starving": 0}[mood]
        if mood == "starving" and nutrition == 0 and remaining_population > MIN_POPULATION:
            remaining_population -= 1
            continue
        projected_satiety.append(post_satiety)
        unhappy = unhappy or mood != "satisfied"

    if any(value < 50 for value in projected_satiety):
        food_status = "В городе голод"
    elif any(value < FULL_MEAL_NUTRITION for value in projected_satiety):
        food_status = "Население не доедает"
    else:
        food_status = "Пищи достаточно"

    reserve = sum(remaining_stock[food] * value for food, value in FOOD_VALUE.items())
    citizen_due = remaining_population < int(capacity) and not unhappy and reserve >= FULL_MEAL_NUTRITION
    return food_status, citizen_due, expected_tax_copper


class CityPopulation:
    def __init__(self, database):
        self.db = database
        self.production = ProductionBuildings(database)
        self._travel_distances = None

    @staticmethod
    def _key(connection, character_id):
        row = connection.execute(
            "SELECT world_id FROM characters WHERE id = %s", (int(character_id),)
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        return int(row["world_id"]), DEFAULT_FACTION

    def _ensure_state(self, connection, key, now):
        connection.execute(
            """INSERT INTO city_population_state (world_id, faction, castle_level, last_food_tick_at)
               VALUES (%s, %s, 1, %s) ON CONFLICT DO NOTHING""",
            (*key, hour_boundary(now)),
        )
        count = connection.execute(
            "SELECT COUNT(*) AS amount FROM city_citizens WHERE world_id = %s AND faction = %s",
            key,
        ).fetchone()["amount"]
        if count == 0:
            self._seed_citizens(connection, key, now)
        self._ensure_building(connection, key[0], "barn", now)
        for building in WORK_BUILDINGS:
            self._ensure_building(connection, key[0], building, now)
        self._reconcile_legacy_workers(connection, key, now)

    @staticmethod
    def _reconcile_legacy_workers(connection, key, now):
        legacy_slots = connection.execute(
            """SELECT building, slot_index, worker_id FROM building_worker_slots
               WHERE world_id = %s AND faction = %s AND occupied = 1
                                 AND worker_id LIKE %s
               ORDER BY hire_time, building, slot_index FOR UPDATE""",
                        (*key, "citizen-%"),
        ).fetchall()
        if not legacy_slots:
            return
        city = connection.execute(
            """SELECT castle_level, COUNT(citizen.id) AS population,
                      COALESCE(MAX(citizen.ordinal), 0) AS max_ordinal
               FROM city_population_state state
               LEFT JOIN city_citizens citizen
                 ON citizen.world_id = state.world_id AND citizen.faction = state.faction
               WHERE state.world_id = %s AND state.faction = %s
               GROUP BY state.castle_level""",
            key,
        ).fetchone()
        population = int(city["population"])
        max_ordinal = int(city["max_ordinal"])
        capacity = int(city["castle_level"]) * BASE_POPULATION_CAPACITY
        for slot in legacy_slots:
            try:
                preferred_ordinal = int(str(slot["worker_id"]).rsplit("-", 1)[1])
            except (IndexError, ValueError):
                preferred_ordinal = -1
            citizen = connection.execute(
                """SELECT id, ordinal FROM city_citizens
                   WHERE world_id = %s AND faction = %s AND job_building IS NULL
                   ORDER BY CASE WHEN ordinal = %s THEN 0 ELSE 1 END, ordinal
                   LIMIT 1 FOR UPDATE""",
                (*key, preferred_ordinal),
            ).fetchone()
            if citizen is None and population < capacity:
                max_ordinal += 1
                connection.execute(
                    """INSERT INTO city_citizens
                       (world_id, faction, ordinal, name, satiety, satiety_updated_at, created_at)
                       VALUES (%s, %s, %s, %s, 100, %s, %s)""",
                    (*key, max_ordinal, f"Горожанин {max_ordinal}", now, now),
                )
                citizen = connection.execute(
                    """SELECT id, ordinal FROM city_citizens
                       WHERE world_id = %s AND faction = %s AND ordinal = %s FOR UPDATE""",
                    (*key, max_ordinal),
                ).fetchone()
                population += 1
            if citizen is None:
                continue
            citizen_id = int(citizen["id"])
            connection.execute(
                """UPDATE building_worker_slots SET worker_id = %s
                   WHERE world_id = %s AND faction = %s AND building = %s
                     AND slot_index = %s AND worker_id = %s""",
                (f"citizen:{citizen_id}", *key, slot["building"],
                 int(slot["slot_index"]), slot["worker_id"]),
            )
            connection.execute(
                """UPDATE city_citizens SET job_building = %s, job_slot = %s,
                   working = TRUE, arrival_at = NULL, travel_direction = NULL
                   WHERE id = %s""",
                (slot["building"], int(slot["slot_index"]), citizen_id),
            )

    @staticmethod
    def _seed_citizens(connection, key, now):
        for ordinal in range(1, MIN_POPULATION + 1):
            connection.execute(
                """INSERT INTO city_citizens
                         (world_id, faction, ordinal, name, satiety, satiety_updated_at, created_at)
                         VALUES (%s, %s, %s, %s, 100, %s, %s) ON CONFLICT DO NOTHING""",
                     (*key, ordinal, f"Горожанин {ordinal}", now, now),
            )

    def _ensure_building(self, connection, world_id, building, now):
        key = (int(world_id), DEFAULT_FACTION, building)
        self.production._ensure(connection, key, now)
        connection.execute(
            """SELECT 1 FROM building_states
               WHERE world_id = %s AND faction = %s AND building = %s FOR UPDATE""",
            key,
        )
        self.production._advance(connection, key, now)
        return key

    def _food_stock(self, connection, world_id):
        return {
            row["resource"]: int(row["storage"])
            for row in connection.execute(
                """SELECT resource, storage FROM building_resources
                   WHERE world_id = %s AND faction = %s AND building = 'barn'
                     AND resource IN ('wheat', 'berries', 'meat')""",
                (int(world_id), DEFAULT_FACTION),
            ).fetchall()
        }

    def _feed(self, connection, world_id, stock):
        plan = meal_plan(FULL_MEAL_NUTRITION, stock)
        nutrition = 0
        for food, quantity in plan.items():
            if quantity <= 0:
                continue
            connection.execute(
                """UPDATE building_resources SET storage = storage - %s
                   WHERE world_id = %s AND faction = %s AND building = 'barn' AND resource = %s""",
                (quantity, int(world_id), DEFAULT_FACTION, food),
            )
            stock[food] = stock.get(food, 0) - quantity
            nutrition += quantity * FOOD_VALUE[food]
        return nutrition

    def _travel_seconds(self, building):
        if self._travel_distances is None:
            from server.world_roads import roads_payload

            routes = {row["building_id"]: row for row in roads_payload()["routes"]}
            self._travel_distances = {
                target: float(routes[source]["distance_tiles"])
                for source, target in ROAD_BUILDINGS.items() if source in routes
            }
        return int(math.ceil(self._travel_distances.get(building, 0) * 3600 / 300))

    def get_traveling_citizens(self, character_id, now=None):
        from server.world_roads import PRODUCTION_BUILDING_IDS, roads_payload, route_position

        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            world_id, _faction = self._key(connection, character_id)
            citizens = connection.execute(
                """SELECT id, faction, name, job_building, travel_direction, arrival_at
                   FROM city_citizens
                   WHERE world_id = %s AND travel_direction IS NOT NULL
                     AND arrival_at > %s
                   ORDER BY faction, id""",
                (world_id, now),
            ).fetchall()

        road_buildings = {production: road for road, production in PRODUCTION_BUILDING_IDS.items()}
        route_names = {route["building_id"]: route["name"]
                       for route in roads_payload()["routes"]}
        travelers = []
        for citizen in citizens:
            total = self._travel_seconds(citizen["job_building"])
            if total <= 0:
                continue
            eta = max(0, math.ceil(float(citizen["arrival_at"]) - now))
            direction = citizen["travel_direction"]
            progress = eta / total if direction == "returning" else 1 - eta / total
            road_building = road_buildings.get(citizen["job_building"], citizen["job_building"])
            position = route_position(road_building, progress)
            if position is None:
                continue
            travelers.append({
                "id": int(citizen["id"]),
                "faction": citizen["faction"],
                "name": citizen["name"],
                "job_building": citizen["job_building"],
                "travel_direction": direction,
                "travel_total_seconds": total,
                "travel_seconds_left": eta,
                "eta_seconds": eta,
                "position_x": position[0],
                "position_y": position[1],
                "position_direction": position[2],
                "route_name": route_names.get(road_building, road_building),
                "movement_text": "Идёт на работу" if direction == "outbound" else "Возвращается в город",
            })
        return travelers

    def _release_worker(self, connection, key, citizen, now, *, clear_job=False):
        building, slot_index = citizen.get("job_building"), citizen.get("job_slot")
        if building and slot_index is not None:
            building_key = self._ensure_building(connection, key[0], building, now)
            self.production._sync_buffer(connection, building_key, now)
            connection.execute(
                """UPDATE building_worker_slots
                   SET occupied = 0, worker_id = NULL, hire_time = NULL, credited = '{}'::jsonb
                   WHERE world_id = %s AND faction = %s AND building = %s AND slot_index = %s
                     AND worker_id = %s""",
                (*building_key, int(slot_index), f"citizen:{citizen['id']}"),
            )
        if clear_job:
            connection.execute(
                """UPDATE city_citizens SET job_building = NULL, job_slot = NULL,
                   working = FALSE, arrival_at = NULL, travel_direction = NULL WHERE id = %s""",
                (int(citizen["id"]),),
            )
        else:
            connection.execute(
                "UPDATE city_citizens SET working = FALSE, arrival_at = NULL, travel_direction = NULL WHERE id = %s",
                (int(citizen["id"]),),
            )

    def _begin_return(self, connection, key, citizen, now):
        self._release_worker(connection, key, citizen, now)
        arrival_at = now + self._travel_seconds(citizen["job_building"])
        connection.execute(
            """UPDATE city_citizens SET working = TRUE, arrival_at = %s,
               travel_direction = 'returning' WHERE id = %s""",
            (arrival_at, int(citizen["id"])),
        )

    @staticmethod
    def _settle_travel(connection, key, now):
        citizens = connection.execute(
            """SELECT id, travel_direction FROM city_citizens
               WHERE world_id = %s AND faction = %s AND travel_direction IS NOT NULL
                 AND arrival_at <= %s FOR UPDATE""",
            (*key, float(now)),
        ).fetchall()
        for citizen in citizens:
            if citizen["travel_direction"] == "returning":
                connection.execute(
                    """UPDATE city_citizens SET job_building = NULL, job_slot = NULL,
                       working = FALSE, arrival_at = NULL, travel_direction = NULL WHERE id = %s""",
                    (int(citizen["id"]),),
                )
            else:
                connection.execute(
                    """UPDATE city_citizens SET arrival_at = NULL, travel_direction = NULL
                       WHERE id = %s""",
                    (int(citizen["id"]),),
                )

    def _resume_worker(self, connection, key, citizen, now):
        building, slot_index = citizen.get("job_building"), citizen.get("job_slot")
        if not building or slot_index is None or citizen.get("working"):
            return
        building_key = self._ensure_building(connection, key[0], building, now)
        slot = connection.execute(
            """SELECT occupied FROM building_worker_slots
               WHERE world_id = %s AND faction = %s AND building = %s AND slot_index = %s FOR UPDATE""",
            (*building_key, int(slot_index)),
        ).fetchone()
        if slot is None or slot["occupied"]:
            connection.execute(
                "UPDATE city_citizens SET job_building = NULL, job_slot = NULL WHERE id = %s",
                (int(citizen["id"]),),
            )
            return
        arrival_at = now + self._travel_seconds(building)
        connection.execute(
            """UPDATE building_worker_slots SET occupied = 1, worker_id = %s,
               hire_time = %s, credited = '{}'::jsonb
               WHERE world_id = %s AND faction = %s AND building = %s AND slot_index = %s""",
            (f"citizen:{citizen['id']}", arrival_at, *building_key, int(slot_index)),
        )
        connection.execute(
            """UPDATE city_citizens SET working = TRUE, arrival_at = %s,
               travel_direction = 'outbound' WHERE id = %s""",
            (arrival_at, int(citizen["id"])),
        )

    def _hourly_tick(self, connection, key, tick_at):
        self._ensure_building(connection, key[0], "barn", tick_at)
        stock = self._food_stock(connection, key[0])
        citizens = connection.execute(
            """SELECT * FROM city_citizens WHERE world_id = %s AND faction = %s
               ORDER BY ordinal FOR UPDATE""",
            key,
        ).fetchall()
        departed = []
        tax_copper = 0
        remaining_population = len(citizens)
        for citizen in citizens:
            elapsed_minutes = max(
                0, int((float(tick_at) - float(citizen["satiety_updated_at"])) // 60)
            )
            satiety = max(0, int(citizen["satiety"]) - elapsed_minutes)
            fed = self._feed(connection, key[0], stock)
            post_satiety, streak, mood = post_meal_state(
                satiety, citizen["hunger_streak"], fed
            )
            tax_copper += {"satisfied": 100, "irritated": 20, "starving": 0}[mood]
            citizen_data = dict(citizen)
            citizen_data.update(satiety=post_satiety, hunger_streak=streak,
                                satisfaction=mood)
            if mood == "starving" and citizen["working"]:
                self._begin_return(connection, key, citizen_data, tick_at)
            if mood == "starving" and fed == 0 and remaining_population > MIN_POPULATION:
                self._release_worker(connection, key, citizen_data, tick_at)
                connection.execute("DELETE FROM city_citizens WHERE id = %s", (int(citizen["id"]),))
                remaining_population -= 1
                departed.append(citizen["name"])
                continue
            connection.execute(
                     """UPDATE city_citizens SET satiety = %s, satiety_updated_at = %s,
                         hunger_streak = %s, satisfaction = %s WHERE id = %s""",
                     (citizen_data["satiety"], tick_at, streak, mood, int(citizen["id"])),
            )
            citizen_data["working"] = bool(citizen["working"])
            if mood == "satisfied" and not citizen_data["working"]:
                self._resume_worker(connection, key, citizen_data, tick_at)

        if tax_copper:
            connection.execute(
                """UPDATE city_population_state SET treasury_copper = treasury_copper + %s
                   WHERE world_id = %s AND faction = %s""",
                (tax_copper, *key),
            )
        state = connection.execute(
            "SELECT castle_level FROM city_population_state WHERE world_id = %s AND faction = %s",
            key,
        ).fetchone()
        current = connection.execute(
            "SELECT COUNT(*) AS amount, COALESCE(MAX(ordinal), 0) AS max_ordinal FROM city_citizens WHERE world_id = %s AND faction = %s",
            key,
        ).fetchone()
        unhappy = connection.execute(
            "SELECT COUNT(*) AS amount FROM city_citizens WHERE world_id = %s AND faction = %s AND satisfaction <> 'satisfied'",
            key,
        ).fetchone()["amount"]
        food_reserve = sum(stock.get(food, 0) * value for food, value in FOOD_VALUE.items())
        if (current["amount"] < int(state["castle_level"]) * BASE_POPULATION_CAPACITY
                and not unhappy and food_reserve >= FULL_MEAL_NUTRITION):
            ordinal = int(current["max_ordinal"]) + 1
            connection.execute(
                """INSERT INTO city_citizens
                         (world_id, faction, ordinal, name, satiety, satiety_updated_at, created_at)
                         VALUES (%s, %s, %s, %s, 100, %s, %s)""",
                     (*key, ordinal, f"Горожанин {ordinal}", tick_at, tick_at),
            )
        return departed

    def _process_due(self, key, now):
        departures = []
        with self.db.connection() as connection:
            state = connection.execute(
                """SELECT last_food_tick_at FROM city_population_state
                   WHERE world_id = %s AND faction = %s FOR UPDATE""",
                key,
            ).fetchone()
            if state is None:
                return
            self._settle_travel(connection, key, now)
            last_tick = float(state["last_food_tick_at"])
            while last_tick + 3600 <= now:
                last_tick += 3600
                departures.extend(self._hourly_tick(connection, key, last_tick))
                connection.execute(
                    """UPDATE city_population_state SET last_food_tick_at = %s
                       WHERE world_id = %s AND faction = %s""",
                    (last_tick, *key),
                )
        for name in departures:
            self._announce_departure(key[0], name)

    def tick_all(self, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            keys = [(int(row["world_id"]), row["faction"])
                    for row in connection.execute("SELECT world_id, faction FROM city_population_state").fetchall()]
        for key in keys:
            self._process_due(key, now)

    def _announce_departure(self, world_id, name):
        world_db = Database(self.db.dsn, schema=self.db.schema, world_id=int(world_id))
        system_character = world_db.ensure_bot_character(f"city_population_{world_id}", "Город")
        world_db.add_chat_message(system_character, "city", f"Горожанин покинул город (-1): {name}")

    def _payload(self, connection, key, now, character_id):
        state = connection.execute(
            """SELECT castle_level, last_food_tick_at, treasury_copper
               FROM city_population_state WHERE world_id = %s AND faction = %s""",
            key,
        ).fetchone()
        character_currency = connection.execute(
            "SELECT copper, silver, gold FROM characters WHERE id = %s",
            (int(character_id),),
        ).fetchone()
        treasury = Currency().add_copper_amount(int(state["treasury_copper"]))
        personal_currency = Currency.from_dict(character_currency or {})
        citizens = connection.execute(
            "SELECT * FROM city_citizens WHERE world_id = %s AND faction = %s ORDER BY ordinal",
            key,
        ).fetchall()
        food = self._food_stock(connection, key[0])
        population_capacity = int(state["castle_level"]) * BASE_POPULATION_CAPACITY
        next_tick_at = float(state["last_food_tick_at"]) + 3600
        food_status, new_citizen_due, expected_tax_copper = food_tick_forecast(
            citizens, food, next_tick_at, population_capacity
        )
        worksites = []
        for building in WORK_BUILDINGS:
            building_key = (key[0], key[1], building)
            level_row = connection.execute(
                "SELECT level FROM building_states WHERE world_id = %s AND faction = %s AND building = %s",
                building_key,
            ).fetchone()
            level = 1 if level_row is None else int(level_row["level"])
            slots = connection.execute(
                """SELECT slot_index, occupied FROM building_worker_slots
                   WHERE world_id = %s AND faction = %s AND building = %s ORDER BY slot_index""",
                building_key,
            ).fetchall()
            worksites.append({"building": building, "name": BUILDINGS[building]["name"],
                              "free_slots": [int(row["slot_index"]) for row in slots if not row["occupied"]],
                              "capacity": building_level_info(level, building)["max_workers"],
                              "travel_seconds": self._travel_seconds(building)})
        citizen_list = []
        for citizen in citizens:
            row = dict(citizen)
            elapsed_minutes = max(
                0, int((float(now) - float(row["satiety_updated_at"])) // 60)
            )
            if row["travel_direction"] == "returning":
                work_status = "Возвращается"
            elif row["travel_direction"] == "outbound":
                work_status = "В пути"
            elif row["working"]:
                work_status = "Занят"
            elif row["job_building"]:
                work_status = "В городе"
            else:
                work_status = "Свободен"
            citizen_list.append({"id": int(row["id"]), "name": row["name"],
                                 "satiety": max(0, int(row["satiety"]) - elapsed_minutes),
                                 "satisfaction": row["satisfaction"], "work_status": work_status,
                                 "job_building": row["job_building"], "job_slot": row["job_slot"],
                                 "travel_seconds_left": (max(0, math.ceil(float(row["arrival_at"]) - now))
                                                          if row["travel_direction"] and row["arrival_at"] is not None
                                                          else 0),
                                 "travel_direction": row["travel_direction"]})
        return {"castle_name": "Замок Радбурка", "castle_level": int(state["castle_level"]),
                "population": len(citizen_list),
                "population_capacity": population_capacity,
                "citizens": citizen_list, "food_storage": food,
                "food_tick_seconds_left": max(0, math.ceil(float(state["last_food_tick_at"]) + 3600 - now)),
                "food_status": food_status,
                "treasury_copper": int(state["treasury_copper"]),
                "treasury": treasury.to_dict(),
                "treasury_text": Currency.format_amount(state["treasury_copper"]),
                "personal_currency_copper": personal_currency.total_copper(),
                "personal_currency": personal_currency.to_dict(),
                "personal_currency_text": Currency.format_amount(personal_currency.total_copper()),
                "tax_tick_seconds_left": max(0, math.ceil(next_tick_at - now)),
                "expected_tax_copper": expected_tax_copper,
                "expected_tax_text": Currency.format_amount(expected_tax_copper),
                "new_citizen_eta_seconds": (
                    max(0, math.ceil(next_tick_at - now)) if new_citizen_due else None
                ),
                "worksites": worksites, "governor": None, "tasks": [], "upgrades": []}

    def get_state(self, character_id, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            key = self._key(connection, character_id)
            self._ensure_state(connection, key, now)
        self._process_due(key, now)
        with self.db.connection() as connection:
            return self._payload(connection, key, now, character_id)

    def transfer_treasury(self, character_id, direction, amount_copper, now=None):
        now = time.time() if now is None else float(now)
        direction = str(direction)
        amount_copper = int(amount_copper)
        if direction not in ("deposit", "withdraw") or amount_copper <= 0:
            raise ValueError("Некорректная операция с казной")
        self.get_state(character_id, now)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            key = self._key(connection, character_id)
            state = connection.execute(
                """SELECT treasury_copper FROM city_population_state
                   WHERE world_id = %s AND faction = %s FOR UPDATE""",
                key,
            ).fetchone()
            character = connection.execute(
                """SELECT copper, silver, gold FROM characters
                   WHERE id = %s FOR UPDATE""",
                (int(character_id),),
            ).fetchone()
            if character is None:
                raise ValueError("Персонаж не найден")
            wallet = Currency.from_dict(character)
            treasury = int(state["treasury_copper"])
            if direction == "deposit":
                if not wallet.subtract_copper_amount(amount_copper):
                    raise ValueError("У персонажа недостаточно монет")
                treasury += amount_copper
            else:
                if treasury < amount_copper:
                    raise ValueError("В казне недостаточно монет")
                treasury -= amount_copper
                wallet.add_copper_amount(amount_copper)
            connection.execute(
                """UPDATE city_population_state SET treasury_copper = %s
                   WHERE world_id = %s AND faction = %s""",
                (treasury, *key),
            )
            connection.execute(
                """UPDATE characters SET copper = %s, silver = %s, gold = %s
                   WHERE id = %s""",
                (wallet.copper, wallet.silver, wallet.gold, int(character_id)),
            )
        return self.get_state(character_id, now)

    def assign_citizen(self, character_id, citizen_id, building, slot_index, now=None):
        now = time.time() if now is None else float(now)
        building, slot_index = str(building), int(slot_index)
        if building not in WORK_BUILDINGS:
            raise ValueError("На это здание нельзя назначить горожанина")
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            key = self._key(connection, character_id)
            self._ensure_state(connection, key, now)
            self._settle_travel(connection, key, now)
            citizen = connection.execute(
                """SELECT * FROM city_citizens WHERE id = %s AND world_id = %s AND faction = %s FOR UPDATE""",
                (int(citizen_id), *key),
            ).fetchone()
            if citizen is None:
                raise ValueError("Горожанин не найден")
            if citizen["satisfaction"] != "satisfied":
                raise ValueError("Голодный горожанин не может выйти на работу")
            if citizen["job_building"] is not None:
                raise ValueError("Горожанин уже назначен на работу")
            building_key = self._ensure_building(connection, key[0], building, now)
            slot = connection.execute(
                """SELECT occupied FROM building_worker_slots
                   WHERE world_id = %s AND faction = %s AND building = %s AND slot_index = %s FOR UPDATE""",
                (*building_key, slot_index),
            ).fetchone()
            if slot is None:
                raise ValueError("Рабочее место не открыто")
            if slot["occupied"]:
                raise ValueError("Рабочее место уже занято")
            arrival_at = now + self._travel_seconds(building)
            connection.execute(
                """UPDATE building_worker_slots SET occupied = 1, worker_id = %s,
                   hire_time = %s, credited = '{}'::jsonb
                   WHERE world_id = %s AND faction = %s AND building = %s AND slot_index = %s""",
                (f"citizen:{citizen_id}", arrival_at, *building_key, slot_index),
            )
            connection.execute(
                """UPDATE city_citizens SET job_building = %s, job_slot = %s,
                         working = TRUE, arrival_at = %s, travel_direction = 'outbound' WHERE id = %s""",
                (building, slot_index, arrival_at, int(citizen_id)),
            )
        return self.get_state(character_id, now)

    def recall_citizen(self, character_id, citizen_id, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            key = self._key(connection, character_id)
            self._settle_travel(connection, key, now)
            citizen = connection.execute(
                """SELECT * FROM city_citizens WHERE id = %s AND world_id = %s AND faction = %s FOR UPDATE""",
                (int(citizen_id), *key),
            ).fetchone()
            if citizen is None or not citizen["job_building"]:
                raise ValueError("Горожанин сейчас не работает")
            if citizen["travel_direction"] == "returning":
                raise ValueError("Горожанин уже возвращается в город")
            self._begin_return(connection, key, dict(citizen), now)
        return self.get_state(character_id, now)
