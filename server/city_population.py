"""Shared city citizens, hourly food consumption, and work assignments."""

import json
import math
import time

from core.currency import Currency
from core.production_buildings import (
    BUILDINGS,
    LUMBER_CAMP_UPGRADES,
    building_level_info,
    building_resources,
)
from core.city_progression import (
    city_population_capacity,
    city_storage_resources,
    city_upgrade_resources,
    unlocked_country_buildings,
)
from core.production_buildings import slot_resources
from server.database import Database, lock_character
from server import config, treasury_ledger
from server.production_buildings import (
    DEFAULT_FACTION,
    STORAGE_ITEM_IDS,
    ProductionBuildings,
    _harvest_bonus_for_worker,
    _resource_timer_sec,
    farm_speed_bonus_percent,
)
from server.city_upgrade import (
    city_upgrade_cycle_cost,
    city_upgrade_payload,
    process_city_upgrade,
)

MIN_POPULATION = 4
FULL_MEAL_NUTRITION = 100
FOOD_VALUE = {"wheat": 10, "berries": 15, "meat": 20}
FOOD_EXTRACTION_RANK = {"wheat": 1, "berries": 2, "meat": 3}


def _cargo_resources(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return [resource for resource in (value or []) if resource]
TAX_COPPER = {"satisfied": 50, "irritated": 20, "starving": 0}
TREASURY_EDICT_TAX_BONUS = 10
TREASURY_EDICT_COST_WOOD = 30
TREASURY_EDICT_COST_SILVER = 5
TREASURY_EDICT_TIME_SECONDS = 4800
CASTLE_UPGRADE_CAPACITY_BONUS = {"plot_for_building": 1}
CASTLE_UPGRADES = {
    1: {
        "plot_for_building": {
            "name": "Участок под застройку",
            "effect": "+1 место горожанина",
            "result": "Вместимость горожан +1",
            "requirement": "Нет",
            "wood_cost": 30,
            "silver_cost": 10,
            "time_seconds": 6000,
        },
        "treasury_edict": {
            "name": "Казначейский указ",
            "effect": "+10 медн. налога за каждого горожанина",
            "result": "Налог с горожан +10 медн.",
            "requirement": "Нет",
            "wood_cost": TREASURY_EDICT_COST_WOOD,
            "silver_cost": TREASURY_EDICT_COST_SILVER,
            "time_seconds": TREASURY_EDICT_TIME_SECONDS,
        },
    },
}
IDLE_SATIETY_SECONDS = 150
TRAVEL_SATIETY_SECONDS = 100
WORK_SATIETY_SECONDS = 60
STRONG_HUNGER_SECONDS = 60
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


def wheat_reserve_zone(amount, capacity):
    ratio = 0 if int(capacity) <= 0 else max(0, int(amount)) / int(capacity)
    if ratio <= 0.20:
        return "red"
    if ratio <= 0.40:
        return "yellow"
    return "green"


def satisfaction_for_satiety(satiety):
    satiety = int(satiety)
    if satiety <= 10:
        return "starving"
    if satiety <= 30:
        return "irritated"
    return "satisfied"


def food_consumption_per_hour(citizens, available_foods):
    if "wheat" not in set(available_foods):
        return {}
    wheat_total = 0.0
    for citizen in citizens:
        status = citizen.get("work_status")
        if status in ("Ведёт повозку", "В пути", "Возвращается"):
            interval = TRAVEL_SATIETY_SECONDS
        elif status == "Занят":
            interval = WORK_SATIETY_SECONDS
        else:
            interval = IDLE_SATIETY_SECONDS
        wheat_total += math.ceil((FULL_MEAL_NUTRITION - 30) / FOOD_VALUE["wheat"]) * 3600 / (
            (FULL_MEAL_NUTRITION - 30) * interval
        )
    return {"wheat": wheat_total} if wheat_total > 0 else {}


class CityPopulation:
    def __init__(self, database):
        self.db = database
        self.production = ProductionBuildings(database)
        self._travel_distances = None
        self._world_dbs = {}

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
            """INSERT INTO city_population_state (world_id, faction, castle_level, city_level, last_food_tick_at)
               VALUES (%s, %s, 1, 1, %s) ON CONFLICT DO NOTHING""",
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
        self._reconcile_orphaned_worker_assignments(connection, key)

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
            """SELECT city_level, population_capacity_bonus,
                      COUNT(citizen.id) AS population,
                      COALESCE(MAX(citizen.ordinal), 0) AS max_ordinal
               FROM city_population_state state
                             LEFT JOIN city_citizens citizen
                                 ON citizen.world_id = state.world_id AND citizen.faction = state.faction
                                AND citizen.alive=TRUE
               WHERE state.world_id = %s AND state.faction = %s
               GROUP BY state.city_level, state.population_capacity_bonus""",
            key,
        ).fetchone()
        population = int(city["population"])
        max_ordinal = int(city["max_ordinal"])
        capacity = city_population_capacity(
            city["city_level"], city["population_capacity_bonus"],
        )
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

    @staticmethod
    def _reconcile_orphaned_worker_assignments(connection, key):
        citizens = connection.execute(
            """SELECT id, job_building, job_slot FROM city_citizens
               WHERE world_id=%s AND faction=%s AND alive=TRUE AND job_building IS NOT NULL
                 AND travel_direction IS DISTINCT FROM 'returning' FOR UPDATE""",
            key,
        ).fetchall()
        for citizen in citizens:
            slot_exists = connection.execute(
                """SELECT 1 FROM building_worker_slots
                   WHERE world_id=%s AND faction=%s AND building=%s AND slot_index=%s
                     AND occupied=1 AND worker_id=%s""",
                (int(key[0]), key[1], citizen["job_building"], citizen["job_slot"],
                 f"citizen:{int(citizen['id'])}"),
            ).fetchone()
            if slot_exists:
                continue
            connection.execute(
                """UPDATE city_citizens SET job_building=NULL, job_slot=NULL, working=FALSE,
                   arrival_at=NULL, travel_direction=NULL, return_progress=1,
                   return_started_at=NULL WHERE id=%s""",
                (int(citizen["id"]),),
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
        city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
        accessible_food = set(city_storage_resources(
            "barn", city_level, ("berries", "wheat", "meat")
        ))
        return {
            row["resource"]: int(row["storage"])
            for row in connection.execute(
                """SELECT resource, storage FROM building_resources
                   WHERE world_id = %s AND faction = %s AND building = 'barn'
                     AND resource IN ('wheat', 'berries', 'meat') FOR UPDATE""",
                (int(world_id), DEFAULT_FACTION),
            ).fetchall() if row["resource"] in accessible_food
        }

    def _feed(self, connection, world_id, stock, needed):
        quantity = min(max(0, int(stock.get("wheat", 0))),
                       math.ceil(max(0, int(needed)) / FOOD_VALUE["wheat"]))
        if quantity <= 0:
            return 0
        connection.execute(
            """UPDATE building_resources SET storage = storage - %s
               WHERE world_id = %s AND faction = %s AND building = 'barn' AND resource = 'wheat'""",
            (quantity, int(world_id), DEFAULT_FACTION),
        )
        stock["wheat"] = stock.get("wheat", 0) - quantity
        return quantity * FOOD_VALUE["wheat"]

    @staticmethod
    def _satiety_rate(citizen, convoy_driver=False):
        if convoy_driver or citizen.get("travel_direction"):
            return TRAVEL_SATIETY_SECONDS
        if citizen.get("working"):
            return WORK_SATIETY_SECONDS
        return IDLE_SATIETY_SECONDS

    def _sync_citizen_hunger(self, connection, key, citizen, now, stock=None, convoy_driver=False):
        if not citizen.get("alive", True):
            return None
        previous_update = float(citizen["satiety_updated_at"])
        now = max(float(now), previous_update)
        remaining = now - previous_update
        rate = self._satiety_rate(citizen, convoy_driver)
        satiety = int(citizen["satiety"])
        satiety_progress = float(citizen.get("satiety_progress", 0))
        strong_hunger = int(citizen.get("strong_hunger", 0))
        strong_hunger_progress = float(citizen.get("strong_hunger_progress", 0))
        if stock is None:
            stock = self._food_stock(connection, key[0])
        reached_zero_at = previous_update if satiety == 0 else None
        satiety_zero_since = citizen.get("satiety_zero_since")
        if satiety_zero_since is not None:
            satiety_zero_since = float(satiety_zero_since)

        while remaining > 1e-9:
            if satiety <= 30:
                nutrition = self._feed(connection, key[0], stock, 100 - satiety)
                if nutrition:
                    satiety = min(100, satiety + nutrition)
                    satiety_progress = 0
                    strong_hunger = 0
                    strong_hunger_progress = 0
                    reached_zero_at = None
                    continue

            if satiety == 0:
                hunger_units = strong_hunger_progress + remaining / STRONG_HUNGER_SECONDS
                hunger_gain = min(100 - strong_hunger, int(hunger_units))
                strong_hunger = min(100, strong_hunger + hunger_gain)
                strong_hunger_progress = (
                    0 if strong_hunger == 100 else hunger_units - hunger_gain
                )
                remaining = 0
                break

            threshold = 30 if satiety > 30 else 0
            seconds_to_threshold = max(0.0, (satiety - threshold - satiety_progress) * rate)
            if remaining >= seconds_to_threshold:
                remaining -= seconds_to_threshold
                satiety = threshold
                satiety_progress = 0
                if satiety == 0 and reached_zero_at is None:
                    reached_zero_at = now - remaining
                continue

            satiety_units = satiety_progress + remaining / rate
            satiety_loss = int(satiety_units)
            satiety -= satiety_loss
            satiety_progress = satiety_units - satiety_loss
            remaining = 0

        if satiety <= 30:
            nutrition = self._feed(connection, key[0], stock, 100 - satiety)
            if nutrition:
                satiety = min(100, satiety + nutrition)
                satiety_progress = 0
                strong_hunger = 0
                strong_hunger_progress = 0
                reached_zero_at = None

        satisfaction = satisfaction_for_satiety(satiety)
        if satiety == 0 and satiety_zero_since is None:
            satiety_zero_since = reached_zero_at or now
        elif satiety > 0:
            satiety_zero_since = None
        if (satiety == 0 and float(now) - satiety_zero_since > 2 * 60 * 60):
            if convoy_driver:
                from server.transport import TransportService

                TransportService(self.db).turn_driver_home(
                    connection, key[0], int(citizen["id"]), satiety_zero_since,
                )
            self._release_worker(connection, key, citizen, now, clear_job=True)
            connection.execute(
                """UPDATE city_citizens SET alive=FALSE, working=FALSE, job_building=NULL,
                   job_slot=NULL, arrival_at=NULL, travel_direction=NULL, satiety=0,
                   satiety_progress=0, strong_hunger=100, strong_hunger_progress=0,
                   satiety_updated_at=%s, satiety_zero_since=%s,
                   satisfaction='starving' WHERE id=%s""",
                (now, satiety_zero_since, int(citizen["id"])),
            )
            return citizen["name"]
        connection.execute(
            """UPDATE city_citizens SET satiety=%s, satiety_progress=%s,
               strong_hunger=%s, strong_hunger_progress=%s,
               satiety_updated_at=%s, satiety_zero_since=%s, satisfaction=%s WHERE id=%s""",
            (satiety, satiety_progress, strong_hunger, strong_hunger_progress,
             now, satiety_zero_since, satisfaction, int(citizen["id"])),
        )
        citizen.update(
            satiety=satiety, satiety_progress=satiety_progress,
            strong_hunger=strong_hunger, strong_hunger_progress=strong_hunger_progress,
            satiety_updated_at=now, satiety_zero_since=satiety_zero_since,
            satisfaction=satisfaction,
        )
        if satiety <= 10 and convoy_driver:
            from server.transport import TransportService

            TransportService(self.db).turn_driver_home(
                connection, key[0], int(citizen["id"]), now,
            )
        elif (satiety <= 10 and citizen.get("working")
              and citizen.get("travel_direction") != "returning"):
            self._begin_return(connection, key, citizen, now)
        return None

    def _sync_citizens(self, connection, key, now):
        stock = self._food_stock(connection, key[0])
        convoy_driver_ids = {
            int(row["driver_citizen_id"])
            for row in connection.execute(
                """SELECT driver_citizen_id FROM transport_convoys
                   WHERE world_id=%s AND faction=%s AND status IN ('outbound','blocked')""",
                key,
            ).fetchall()
        }
        citizens = connection.execute(
            """SELECT * FROM city_citizens WHERE world_id=%s AND faction=%s AND alive=TRUE
               ORDER BY ordinal FOR UPDATE""",
            key,
        ).fetchall()
        departed = []
        for citizen in citizens:
            name = self._sync_citizen_hunger(
                connection, key, dict(citizen), now, stock,
                convoy_driver=int(citizen["id"]) in convoy_driver_ids,
            )
            if name:
                departed.append(name)
        return departed

    def _travel_seconds(self, building):
        if self._travel_distances is None:
            from server.world_roads import build_country_roads

            routes = {row["building_id"]: row for row in build_country_roads()[0]}
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
            city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
            citizens = connection.execute(
                     """SELECT id, faction, name, job_building, travel_direction, arrival_at,
                                  return_progress, return_started_at
                   FROM city_citizens
                   WHERE world_id = %s AND travel_direction IS NOT NULL
                                         AND alive=TRUE
                     AND arrival_at > %s
                   ORDER BY faction, id""",
                (world_id, now),
            ).fetchall()

        road_buildings = {production: road for road, production in PRODUCTION_BUILDING_IDS.items()}
        route_names = {route["building_id"]: route["name"]
                   for route in roads_payload(city_level)["routes"]}
        travelers = []
        for citizen in citizens:
            full_route_seconds = self._travel_seconds(citizen["job_building"])
            if full_route_seconds <= 0:
                continue
            eta = max(0, math.ceil(float(citizen["arrival_at"]) - now))
            direction = citizen["travel_direction"]
            if direction == "returning":
                return_progress = min(1.0, max(0.0, float(citizen["return_progress"])))
                total = max(1, math.ceil(full_route_seconds * return_progress))
                elapsed = (max(0.0, now - float(citizen["return_started_at"]))
                           if citizen["return_started_at"] is not None
                           else max(0.0, total - eta))
                progress = return_progress * max(0.0, 1.0 - elapsed / total)
            else:
                total = full_route_seconds
                progress = 1 - eta / total
            road_building = road_buildings.get(citizen["job_building"], citizen["job_building"])
            position = route_position(road_building, progress, city_level)
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
            self.production._sync_harvest(connection, building_key, now)
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
                   working = FALSE, arrival_at = NULL, travel_direction = NULL,
                   return_progress = 1, return_started_at = NULL WHERE id = %s""",
                (int(citizen["id"]),),
            )
        else:
            connection.execute(
                "UPDATE city_citizens SET working = FALSE, arrival_at = NULL, travel_direction = NULL WHERE id = %s",
                (int(citizen["id"]),),
            )

    def _begin_return(self, connection, key, citizen, now):
        full_route_seconds = self._travel_seconds(citizen["job_building"])
        progress = 1.0
        if (citizen.get("travel_direction") == "outbound"
                and citizen.get("arrival_at") is not None and full_route_seconds > 0):
            outbound_started_at = float(citizen["arrival_at"]) - full_route_seconds
            progress = min(1.0, max(0.0, (float(now) - outbound_started_at) / full_route_seconds))
        return_seconds = max(1, int(math.ceil(full_route_seconds * progress)))
        self._release_worker(connection, key, citizen, now)
        arrival_at = now + return_seconds
        connection.execute(
            """UPDATE city_citizens SET working = TRUE, arrival_at = %s,
               travel_direction = 'returning', return_progress = %s,
               return_started_at = %s WHERE id = %s""",
            (arrival_at, progress, float(now), int(citizen["id"])),
        )

    def _settle_travel(self, connection, key, now):
        stock = self._food_stock(connection, key[0])
        while True:
            citizens = connection.execute(
                """SELECT * FROM city_citizens
               WHERE world_id = %s AND faction = %s AND travel_direction IS NOT NULL
                 AND alive=TRUE AND arrival_at <= %s FOR UPDATE""",
                (*key, float(now)),
            ).fetchall()
            if not citizens:
                return
            for citizen in citizens:
                arrival_at = float(citizen["arrival_at"])
                self._sync_citizen_hunger(connection, key, dict(citizen), arrival_at, stock)
                current = connection.execute(
                    "SELECT * FROM city_citizens WHERE id=%s AND alive=TRUE FOR UPDATE",
                    (int(citizen["id"]),),
                ).fetchone()
                if (current is None or not current["travel_direction"]
                        or float(current["arrival_at"]) > now):
                    continue
                if current["travel_direction"] == "returning":
                    connection.execute(
                        """UPDATE city_citizens SET job_building=NULL,job_slot=NULL,
                           working=FALSE,arrival_at=NULL,travel_direction=NULL,
                           return_progress=1,return_started_at=NULL WHERE id=%s""",
                        (int(citizen["id"]),),
                    )
                else:
                    connection.execute(
                        """UPDATE city_citizens SET arrival_at=NULL,travel_direction=NULL,
                           return_progress=1,return_started_at=NULL WHERE id=%s""",
                        (int(citizen["id"]),),
                    )
                settled = connection.execute(
                    "SELECT * FROM city_citizens WHERE id=%s AND alive=TRUE FOR UPDATE",
                    (int(citizen["id"]),),
                ).fetchone()
                if settled is not None:
                    self._sync_citizen_hunger(connection, key, dict(settled), now, stock)

    @staticmethod
    def _tax_copper(citizens, edict_active=False):
        total = 0
        for row in citizens:
            tax = TAX_COPPER.get(row["satisfaction"], 0)
            if tax and edict_active:
                tax += TREASURY_EDICT_TAX_BONUS
            total += tax
        return total

    def _pick_departing_citizen(self, connection, key):
        """Приоритет ухода: свободные, затем не-пищевая работа, затем пищевая по классу (мясо, ягоды, пшеница)."""
        citizens = connection.execute(
            """SELECT id, ordinal, name, job_building, job_slot, working, travel_direction
               FROM city_citizens WHERE world_id=%s AND faction=%s AND alive=TRUE
               ORDER BY ordinal""",
            key,
        ).fetchall()
        convoy_cargo = {
            int(row["driver_citizen_id"]): _cargo_resources(row["resource_ids_json"])
            for row in connection.execute(
                """SELECT driver_citizen_id, resource_ids_json FROM transport_convoys
                   WHERE world_id=%s AND faction=%s AND status IN ('outbound','blocked')""",
                key,
            ).fetchall()
        }

        def food_rank(resources):
            ranks = [FOOD_EXTRACTION_RANK[resource] for resource in resources
                     if resource in FOOD_EXTRACTION_RANK]
            return max(ranks) if ranks else 0

        candidates = []
        for citizen in citizens:
            citizen_id = int(citizen["id"])
            ordinal = int(citizen["ordinal"])
            if citizen_id in convoy_cargo:
                cargo_rank = food_rank(convoy_cargo[citizen_id])
                if cargo_rank == 0:
                    candidates.append((3, 0, -ordinal, citizen))
                else:
                    candidates.append((4, -cargo_rank, -ordinal, citizen))
                continue
            if citizen["job_building"] is None:
                candidates.append((1, 0, -ordinal, citizen))
                continue
            slot_rank = food_rank(slot_resources(citizen["job_building"], int(citizen["job_slot"])))
            if slot_rank == 0:
                candidates.append((2, 0, -ordinal, citizen))
            else:
                candidates.append((5, -slot_rank, -ordinal, citizen))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[:3])[3]

    def _depart_citizen(self, connection, key, citizen, now):
        if int(citizen["id"]) in self._convoy_driver_ids(connection, key):
            from server.transport import TransportService

            TransportService(self.db).turn_driver_home(
                connection, key[0], int(citizen["id"]), now,
            )
        self._release_worker(connection, key, dict(citizen), now, clear_job=True)
        connection.execute(
            """UPDATE city_citizens SET alive=FALSE, working=FALSE, job_building=NULL,
               job_slot=NULL, arrival_at=NULL, travel_direction=NULL, satisfaction='starving'
               WHERE id=%s""",
            (int(citizen["id"]),),
        )
        return citizen

    def _convoy_driver_ids(self, connection, key):
        return {
            int(row["driver_citizen_id"])
            for row in connection.execute(
                """SELECT driver_citizen_id FROM transport_convoys
                   WHERE world_id=%s AND faction=%s AND status IN ('outbound','blocked')""",
                key,
            ).fetchall()
        }

    def _hourly_tick(self, connection, key, tick_at):
        citizens = connection.execute(
            """SELECT satisfaction FROM city_citizens
               WHERE world_id=%s AND faction=%s AND alive=TRUE FOR UPDATE""",
            key,
        ).fetchall()
        edict = connection.execute(
            """SELECT EXISTS(
                   SELECT 1 FROM castle_upgrade_state
                   WHERE world_id = %s AND faction = %s AND upgrade_id = 'treasury_edict'
                     AND done = TRUE
                     AND castle_level = (SELECT castle_level FROM city_population_state
                                         WHERE world_id = %s AND faction = %s)
               ) AS done""",
            (*key, *key),
        ).fetchone()
        tax_copper = self._tax_copper(citizens, edict_active=bool(edict["done"]))
        if tax_copper:
            connection.execute(
                """UPDATE city_population_state SET treasury_copper = treasury_copper + %s
                   WHERE world_id = %s AND faction = %s""",
                (tax_copper, *key),
            )
            treasury_ledger.distribute_income(connection, key, tax_copper)
        state = connection.execute(
            """SELECT city_level, population_capacity_bonus
               FROM city_population_state WHERE world_id = %s AND faction = %s""",
            key,
        ).fetchone()
        current = connection.execute(
            """SELECT COUNT(*) FILTER (WHERE alive=TRUE) AS amount,
                      COALESCE(MAX(ordinal), 0) AS max_ordinal
               FROM city_citizens WHERE world_id=%s AND faction=%s""",
            key,
        ).fetchone()
        stock = self._food_stock(connection, key[0])
        barn_level_row = connection.execute(
            "SELECT level FROM building_states WHERE world_id=%s AND faction=%s AND building='barn'",
            key,
        ).fetchone()
        barn_level = 1 if barn_level_row is None else int(barn_level_row["level"])
        barn_capacity = int(building_level_info(barn_level, "barn")["storage"])
        zone = wheat_reserve_zone(stock.get("wheat", 0), barn_capacity)
        if (zone == "green" and current["amount"] < city_population_capacity(
                state["city_level"], state["population_capacity_bonus"]
        )):
            ordinal = int(current["max_ordinal"]) + 1
            connection.execute(
                """INSERT INTO city_citizens
                         (world_id, faction, ordinal, name, satiety, satiety_updated_at, created_at)
                         VALUES (%s, %s, %s, %s, 100, %s, %s)""",
                     (*key, ordinal, f"Горожанин {ordinal}", tick_at, tick_at),
            )
            return []
        if zone == "red" and current["amount"] > 0:
            citizen = self._pick_departing_citizen(connection, key)
            if citizen is not None:
                departed = self._depart_citizen(connection, key, citizen, tick_at)
                return [("departed", departed["name"])]
        return []

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
            last_tick = float(state["last_food_tick_at"])
            hours_done = 0
            while last_tick + 3600 <= now and hours_done < config.CITY_CATCHUP_HOURS_PER_PASS:
                last_tick += 3600
                hours_done += 1
                self._ensure_building(connection, key[0], "barn", last_tick)
                departures.extend(self._sync_citizens(connection, key, last_tick))
                self._settle_travel(connection, key, last_tick)
                departures.extend(self._sync_citizens(connection, key, last_tick))
                departures.extend(self._hourly_tick(connection, key, last_tick))
                connection.execute(
                    """UPDATE city_population_state SET last_food_tick_at = %s
                       WHERE world_id = %s AND faction = %s""",
                    (last_tick, *key),
                )
            # Пока часы простоя не догнаны, события текущего момента не обрабатываем:
            # иначе они опередят почасовые шаги. Остаток догоняется в следующих проходах.
            if last_tick + 3600 > now:
                self._ensure_building(connection, key[0], "barn", now)
                self._settle_travel(connection, key, now)
                departures.extend(self._sync_citizens(connection, key, now))
                process_city_upgrade(connection, key, now)
                self._complete_castle_upgrades(connection, key, now)
        for event in departures:
            if isinstance(event, tuple):
                self._announce_citizen_departure(key[0], event[1])
            else:
                self._announce_starvation_death(key[0], event)

    def _complete_castle_upgrades(self, connection, key, now):
        finished = connection.execute(
            """UPDATE castle_upgrade_state SET done = TRUE, finish_at = NULL
               WHERE world_id = %s AND faction = %s
                 AND done = FALSE AND finish_at IS NOT NULL AND finish_at <= %s
               RETURNING upgrade_id""",
            (*key, now),
        ).fetchall()
        for row in finished:
            effect = CASTLE_UPGRADE_CAPACITY_BONUS.get(row["upgrade_id"], 0)
            if effect:
                connection.execute(
                    """UPDATE city_population_state
                       SET population_capacity_bonus = population_capacity_bonus + %s
                       WHERE world_id = %s AND faction = %s""",
                    (effect, *key),
                )

    def start_castle_upgrade(self, character_id, upgrade_id, now=None):
        now = time.time() if now is None else float(now)
        self.get_state(character_id, now)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            key = self._key(connection, character_id)
            state = connection.execute(
                """SELECT castle_level FROM city_population_state
                   WHERE world_id = %s AND faction = %s FOR UPDATE""",
                key,
            ).fetchone()
            level = int(state["castle_level"])
            upgrade = CASTLE_UPGRADES.get(level, {}).get(upgrade_id)
            if upgrade is None:
                raise ValueError("Улучшение замка не найдено")
            existing = connection.execute(
                """SELECT done, finish_at FROM castle_upgrade_state
                   WHERE world_id = %s AND faction = %s AND castle_level = %s AND upgrade_id = %s
                   FOR UPDATE""",
                (*key, level, upgrade_id),
            ).fetchone()
            if existing is not None and existing["done"]:
                raise ValueError(f"{upgrade['name']} уже построено")
            if existing is not None and existing["finish_at"] is not None:
                raise ValueError(f"{upgrade['name']} уже выполняется")
            self.production._debit_treasury(
                connection, key, Currency.to_copper(silver=upgrade["silver_cost"]), character_id,
            )
            self.production._debit_warehouse_items(
                connection, key, {STORAGE_ITEM_IDS["wood"]: upgrade["wood_cost"]}, now,
            )
            connection.execute(
                """INSERT INTO castle_upgrade_state
                       (world_id, faction, castle_level, upgrade_id, finish_at, done)
                   VALUES (%s, %s, %s, %s, %s, FALSE)
                   ON CONFLICT (world_id, faction, castle_level, upgrade_id)
                   DO UPDATE SET finish_at = EXCLUDED.finish_at""",
                (*key, level, upgrade_id, now + upgrade["time_seconds"]),
            )
        return self.get_state(character_id, now)

    def start_treasury_edict(self, character_id, now=None):
        return self.start_castle_upgrade(character_id, "treasury_edict", now)

    def tick_all(self, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            keys = [(int(row["world_id"]), row["faction"])
                    for row in connection.execute("SELECT world_id, faction FROM city_population_state").fetchall()]
        for key in keys:
            self._process_due(key, now)

    def _announce_starvation_death(self, world_id, name):
        self._announce_city_chat(world_id, f"Горожанин умер от голода: {name}")

    def _announce_citizen_departure(self, world_id, name):
        self._announce_city_chat(world_id, f"Горожанин покинул город из-за голода: {name}")

    def _announce_city_chat(self, world_id, text):
        world_db = self._world_dbs.get(int(world_id))
        if world_db is None:
            world_db = Database(self.db.dsn, schema=self.db.schema, world_id=int(world_id))
            self._world_dbs[int(world_id)] = world_db
        system_character = world_db.ensure_bot_character(f"city_population_{world_id}", "Город")
        world_db.add_chat_message(system_character, "city", text)

    def _resource_income_per_hour(self, connection, key, now, resources_in_scope):
        income = {resource: 0.0 for resource in resources_in_scope}
        buildings = ("farm", "lumber_camp", "barnyard", "mountain_rift", "black_pit")
        farm_upgrades = self.production._farm_upgrades(connection, (*key, "farm"))
        lumber_upgrades = self.production._lumber_camp_upgrades(
            connection, (*key, "lumber_camp"),
        )
        slots_by_building = {}
        citizen_ids = set()
        for building in buildings:
            slots = connection.execute(
                """SELECT slot_index, worker_id FROM building_worker_slots
                         WHERE world_id=%s AND faction=%s AND building=%s AND occupied=1""",
                (*key, building),
            ).fetchall()
            slots_by_building[building] = slots
            for slot in slots:
                worker_id = str(slot["worker_id"] or "")
                if worker_id.startswith("citizen:"):
                    citizen_ids.add(int(worker_id.split(":", 1)[1]))
        travel_by_citizen = {}
        if citizen_ids:
            for row in connection.execute(
                "SELECT id, travel_direction, arrival_at FROM city_citizens WHERE id = ANY(%s)",
                (sorted(citizen_ids),),
            ).fetchall():
                travel_by_citizen[int(row["id"])] = row
        for building in buildings:
            for slot in slots_by_building[building]:
                worker_id = str(slot["worker_id"] or "")
                if worker_id.startswith("citizen:"):
                    travel = travel_by_citizen.get(int(worker_id.split(":", 1)[1]))
                    if (travel and travel["travel_direction"] == "outbound"
                            and travel["arrival_at"] is not None
                            and float(travel["arrival_at"]) > float(now)):
                        continue
                bonus = _harvest_bonus_for_worker(connection, worker_id)
                resources = slot_resources(building, int(slot["slot_index"]))
                if (building == "farm"
                        and (farm_upgrades["wooden_plough"] or farm_upgrades["whetstone"])
                        and "wheat" in resources):
                    bonus = dict(bonus)
                    bonus["wheat"] = int(bonus.get("wheat", 0)) + farm_speed_bonus_percent(farm_upgrades)
                elif (building == "lumber_camp" and lumber_upgrades["strong_handle"]
                      and "wood" in resources):
                    bonus = dict(bonus)
                    bonus["wood"] = int(bonus.get("wood", 0)) + int(
                        LUMBER_CAMP_UPGRADES["strong_handle"]["speed_bonus_percent"]
                    )
                for resource in resources:
                    if resource not in income:
                        continue
                    timer = _resource_timer_sec(resource, bonus)
                    if timer:
                        income[resource] += 3600 / timer
        return income

    def _payload(self, connection, key, now, character_id):
        state = connection.execute(
            """SELECT castle_level, city_level, population_capacity_bonus,
                      last_food_tick_at, treasury_copper
               FROM city_population_state WHERE world_id = %s AND faction = %s""",
            key,
        ).fetchone()
        castle_rows = self._castle_upgrade_rows(connection, key, int(state["castle_level"]))
        treasury_edict_done = bool(castle_rows.get("treasury_edict", {}).get("done"))
        character_currency = connection.execute(
            "SELECT copper, silver, gold FROM characters WHERE id = %s",
            (int(character_id),),
        ).fetchone()
        treasury = Currency().add_copper_amount(int(state["treasury_copper"]))
        personal_treasury = treasury_ledger.contribution_of(connection, key, character_id)
        is_mayor = treasury_ledger.is_mayor(connection, key, character_id)
        spendable_treasury = treasury_ledger.spendable_copper(connection, key, character_id)
        personal_currency = Currency.from_dict(character_currency or {})
        citizens = connection.execute(
            "SELECT * FROM city_citizens WHERE world_id = %s AND faction = %s AND alive=TRUE ORDER BY ordinal",
            key,
        ).fetchall()
        city_level = int(state["city_level"])
        accessible_barn = city_storage_resources(
            "barn", city_level, building_resources("barn"),
        )
        accessible_warehouse = city_storage_resources(
            "warehouse", city_level, building_resources("warehouse"),
        )
        barn_stock = self._food_stock(connection, key[0])
        food = {resource: int(barn_stock.get(resource, 0)) for resource in accessible_barn}
        resource_storage = {
            **food,
            **{resource: 0 for resource in accessible_warehouse},
        }
        warehouse_rows = connection.execute(
            """SELECT resource, storage FROM building_resources
               WHERE world_id=%s AND faction=%s AND building='warehouse'
                 AND resource = ANY(%s)""",
            (*key, list(accessible_warehouse)),
        ).fetchall()
        resource_storage.update({
            row["resource"]: int(row["storage"]) for row in warehouse_rows
        })
        resource_income = self._resource_income_per_hour(
            connection, key, now, resource_storage
        )
        food_income = {resource: resource_income[resource] for resource in food}
        population_capacity = city_population_capacity(
            state["city_level"], state["population_capacity_bonus"],
        )
        next_tick_at = float(state["last_food_tick_at"]) + 3600
        barn_level_row = connection.execute(
            "SELECT level FROM building_states WHERE world_id=%s AND faction=%s AND building='barn'",
            key,
        ).fetchone()
        barn_level = 1 if barn_level_row is None else int(barn_level_row["level"])
        barn_capacity = int(building_level_info(barn_level, "barn")["storage"])
        wheat_zone = wheat_reserve_zone(food.get("wheat", 0), barn_capacity)
        food_status = {
            "green": "в городе достаточно еды для роста",
            "yellow": "в городе не стабильно с поставками еды",
            "red": "в городе нечего есть, может начаться голод",
        }[wheat_zone]
        expected_tax_copper = self._tax_copper(
            citizens, edict_active=treasury_edict_done,
        )
        new_citizen_due = (
            wheat_zone == "green" and len(citizens) < population_capacity
        )
        worksites = []
        unlocked_roads = set(unlocked_country_buildings(state["city_level"]))
        for building in WORK_BUILDINGS:
            road_id = next((road for road, worksite in ROAD_BUILDINGS.items()
                            if worksite == building), None)
            if road_id not in unlocked_roads:
                continue
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
            capacity = building_level_info(level, building)["max_workers"]
            if building == "farm":
                capacity += len(self.production._farm_upgrades(connection, building_key)["ration_plots"])
                capacity += sum(
                    int(count) for count in
                    self.production._farm_upgrades(connection, building_key)["extra_places"].values()
                )
            worksites.append({"building": building, "name": BUILDINGS[building]["name"],
                              "free_slots": [int(row["slot_index"]) for row in slots if not row["occupied"]],
                              "capacity": capacity,
                              "travel_seconds": self._travel_seconds(building)})
        citizen_list = []
        convoy_driver_ids = {
            int(row["driver_citizen_id"])
            for row in connection.execute(
                """SELECT driver_citizen_id FROM transport_convoys
                   WHERE world_id=%s AND faction=%s AND status IN ('outbound','blocked')""",
                key,
            ).fetchall()
        }
        for citizen in citizens:
            row = dict(citizen)
            if int(row["id"]) in convoy_driver_ids:
                work_status = "Ведёт повозку"
            elif row["travel_direction"] == "returning":
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
                                 "satiety": int(row["satiety"]),
                                 "strong_hunger": int(row["strong_hunger"]),
                                 "satisfaction": row["satisfaction"], "work_status": work_status,
                                 "job_building": row["job_building"], "job_slot": row["job_slot"],
                                 "death_eta_seconds": (
                                     max(0, math.ceil(
                                         ((int(row["satiety"]) * self._satiety_rate(
                                             row, int(row["id"]) in convoy_driver_ids
                                         ) - float(row.get("satiety_progress", 0)))
                                          if int(row["satiety"]) > 0 else 0)
                                         + 2 * 60 * 60
                                         - (now - float(row["satiety_zero_since"])
                                            if row.get("satiety_zero_since") is not None else 0)
                                     )) if int(row["satiety"]) <= 10 else None
                                 ),
                                 "travel_seconds_left": (max(0, math.ceil(float(row["arrival_at"]) - now))
                                                          if row["travel_direction"] and row["arrival_at"] is not None
                                                          else 0),
                                 "travel_direction": row["travel_direction"]})
        horses = connection.execute(
            """SELECT status FROM stable_horses
               WHERE world_id=%s AND faction=%s AND building='stable'""",
            key,
        ).fetchall()
        food_consumers = citizen_list + [
            {"work_status": "Свободен" if horse["status"] == "Отдыхает" else "Занят",
             "is_horse": True}
            for horse in horses
        ]
        food_consumption = food_consumption_per_hour(food_consumers, food)
        new_citizen_eta = (
            max(0, math.ceil(next_tick_at - now)) if new_citizen_due else None
        )
        departure_eta = (
            max(0, math.ceil(next_tick_at - now)) if wheat_zone == "red" and citizens else None
        )
        resource_consumption = dict(food_consumption)
        city_upgrade = city_upgrade_payload(connection, key, now)
        for resource, amount in city_upgrade.get("resource_drain_per_hour", {}).items():
            resource_consumption[resource] = resource_consumption.get(resource, 0.0) + float(amount)
        if wheat_zone == "yellow":
            net_wheat_drain = max(
                0.0,
                resource_consumption.get("wheat", 0.0) - food_income.get("wheat", 0.0),
            )
            red_threshold = math.floor(barn_capacity * 0.20)
            satiated_eta = (
                math.ceil((food.get("wheat", 0) - red_threshold) * 3600 / net_wheat_drain)
                if net_wheat_drain > 0 else None
            )
        else:
            satiated_eta = None
        upgrade_foods = set(city_upgrade_resources(int(state["city_level"])))
        upgrade_cycle_cost = city_upgrade_cycle_cost(len(citizen_list), population_capacity)
        food_trend = {}
        for resource in food:
            if food_income.get(resource, 0.0) < food_consumption.get(resource, 0.0):
                food_trend[resource] = "deficit"
            elif resource in upgrade_foods and food[resource] >= upgrade_cycle_cost:
                food_trend[resource] = "upgrade_ready"
            else:
                food_trend[resource] = "surplus"
        resource_trend = dict(food_trend)
        for resource in accessible_warehouse:
            income = resource_income.get(resource, 0.0)
            consumption = resource_consumption.get(resource, 0.0)
            if income < consumption:
                trend = "deficit"
            elif resource in upgrade_foods and resource_storage[resource] >= upgrade_cycle_cost:
                trend = "upgrade_ready"
            elif income > consumption:
                trend = "surplus"
            else:
                trend = "deficit"
            resource_trend[resource] = trend
        return {"castle_name": "Замок Радбурка",
            "castle_level": int(state["castle_level"]),
            "city_level": city_level,
            "city_upgrade": city_upgrade,
                "castle_upgrade": (self._active_castle_upgrades(
                    int(state["castle_level"]), castle_rows, now) or [{
                        "id": None, "active": False, "finish_at": None, "upgrade_name": None,
                    }])[0],
                "castle_upgrades_active": self._active_castle_upgrades(
                    int(state["castle_level"]), castle_rows, now),
                "population": len(citizen_list),
                "population_capacity": population_capacity,
                "citizens": citizen_list, "food_storage": food,
                "food_income_per_hour": food_income,
                "food_consumption_per_hour": food_consumption,
                "food_trend": food_trend,
                "city_resource_income_per_hour": resource_income,
                "city_resource_consumption_per_hour": resource_consumption,
                "city_resource_storage": resource_storage,
                "city_resource_trend": resource_trend,
                "food_status": food_status,
                "food_zone": wheat_zone,
                "treasury_copper": int(state["treasury_copper"]),
                "treasury": treasury.to_dict(),
                "treasury_text": Currency.format_amount(state["treasury_copper"]),
                "personal_treasury_copper": personal_treasury,
                "personal_treasury_text": Currency.format_amount(personal_treasury),
                "is_mayor": is_mayor,
                "spendable_treasury_copper": spendable_treasury,
                "personal_currency_copper": personal_currency.total_copper(),
                "personal_currency": personal_currency.to_dict(),
                "personal_currency_text": Currency.format_amount(personal_currency.total_copper()),
                "tax_tick_seconds_left": max(0, math.ceil(next_tick_at - now)),
                "expected_tax_copper": expected_tax_copper,
                "expected_tax_text": Currency.format_amount(expected_tax_copper),
                "new_citizen_eta_seconds": new_citizen_eta,
                "departure_eta_seconds": departure_eta,
                "satiated_eta_seconds": satiated_eta,
                "worksites": worksites, "governor": None, "tasks": [],
                "upgrades": self._castle_upgrades_payload(
                    int(state["castle_level"]), castle_rows, now)}

    def _castle_upgrade_rows(self, connection, key, castle_level):
        rows = connection.execute(
            """SELECT upgrade_id, finish_at, done FROM castle_upgrade_state
               WHERE world_id = %s AND faction = %s AND castle_level = %s""",
            (*key, castle_level),
        ).fetchall()
        return {row["upgrade_id"]: row for row in rows}

    @staticmethod
    def _active_castle_upgrades(castle_level, rows, now):
        catalog = CASTLE_UPGRADES.get(castle_level, {})
        active = []
        for upgrade_id, row in rows.items():
            if row["done"] or row["finish_at"] is None or upgrade_id not in catalog:
                continue
            active.append({
                "id": upgrade_id,
                "active": True,
                "finish_at": float(row["finish_at"]),
                "upgrade_name": catalog[upgrade_id]["name"],
            })
        return active

    @staticmethod
    def _castle_upgrades_payload(castle_level, rows, now):
        payload = []
        for upgrade_id, upgrade in CASTLE_UPGRADES.get(castle_level, {}).items():
            row = rows.get(upgrade_id)
            done = bool(row["done"]) if row else False
            finish_at = row["finish_at"] if row else None
            active = finish_at is not None and not done
            seconds_left = max(0, math.ceil(float(finish_at) - now)) if active else 0
            payload.append({
                "id": upgrade_id,
                "name": upgrade["name"],
                "effect": upgrade["effect"],
                "requirement": upgrade["requirement"],
                "result": upgrade["result"],
                "silver_cost": upgrade["silver_cost"],
                "wood_cost": upgrade["wood_cost"],
                "time_seconds": upgrade["time_seconds"],
                "is_complete": done,
                "is_active": active,
                "seconds_left": seconds_left,
            })
        return payload

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
                treasury_ledger.add_contribution(connection, key, character_id, amount_copper)
                treasury_ledger.refresh_mayor(connection, key)
            else:
                contribution = treasury_ledger.contribution_of(connection, key, character_id)
                if contribution < amount_copper:
                    needed_silver = -(-amount_copper // Currency.COPPER_PER_SILVER)
                    have_silver = contribution // Currency.COPPER_PER_SILVER
                    raise ValueError(
                        f"В казне недостаточно твоих средств: {have_silver}/{needed_silver} серебра"
                    )
                treasury -= amount_copper
                treasury_ledger.remove_contribution(connection, key, character_id, amount_copper)
                treasury_ledger.refresh_mayor(connection, key)
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
            city_level = self.production._city_level(connection, key[0], key[1])
            road_id = next((road for road, worksite in ROAD_BUILDINGS.items()
                            if worksite == building), None)
            if road_id not in unlocked_country_buildings(city_level):
                raise ValueError("Это загородное здание ещё не открыто для города")
            self._settle_travel(connection, key, now)
            citizen = connection.execute(
                """SELECT * FROM city_citizens WHERE id = %s AND world_id = %s AND faction = %s
                   AND alive=TRUE FOR UPDATE""",
                (int(citizen_id), *key),
            ).fetchone()
            if citizen is None:
                raise ValueError("Горожанин не найден")
            active_convoy = connection.execute(
                """SELECT 1 FROM transport_convoys WHERE world_id=%s AND faction=%s
                   AND driver_citizen_id=%s AND status IN ('outbound','blocked')""",
                (*key, int(citizen_id)),
            ).fetchone()
            self._sync_citizen_hunger(
                connection, key, dict(citizen), now,
                self._food_stock(connection, key[0]), convoy_driver=active_convoy is not None,
            )
            citizen = connection.execute(
                "SELECT * FROM city_citizens WHERE id=%s AND alive=TRUE FOR UPDATE",
                (int(citizen_id),),
            ).fetchone()
            if citizen is None:
                raise ValueError("Горожанин умер от голода")
            if citizen["satisfaction"] != "satisfied":
                raise ValueError("Голодный горожанин не может выйти на работу")
            if citizen["job_building"] is not None:
                raise ValueError("Горожанин уже назначен на работу")
            if citizen["working"] or citizen["travel_direction"] is not None:
                raise ValueError("Горожанин сейчас не свободен")
            if connection.execute(
                """SELECT 1 FROM transport_convoys WHERE world_id=%s AND faction=%s
                   AND driver_citizen_id=%s AND status IN ('outbound','blocked')""",
                (*key, int(citizen_id)),
            ).fetchone():
                raise ValueError("Участник экипажа занят транспортным рейсом")
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
                         working = TRUE, arrival_at = %s, travel_direction = 'outbound',
                         return_progress = 1, return_started_at = NULL WHERE id = %s""",
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
                """SELECT * FROM city_citizens WHERE id = %s AND world_id = %s AND faction = %s
                   AND alive=TRUE FOR UPDATE""",
                (int(citizen_id), *key),
            ).fetchone()
            if citizen is None or not citizen["job_building"]:
                raise ValueError("Горожанин сейчас не работает")
            self._sync_citizen_hunger(
                connection, key, dict(citizen), now, self._food_stock(connection, key[0]),
            )
            citizen = connection.execute(
                "SELECT * FROM city_citizens WHERE id=%s AND alive=TRUE FOR UPDATE",
                (int(citizen_id),),
            ).fetchone()
            if citizen is None or not citizen["job_building"]:
                raise ValueError("Горожанин сейчас не работает")
            if citizen["travel_direction"] == "returning":
                raise ValueError("Горожанин уже возвращается в город")
            self._begin_return(connection, key, dict(citizen), now)
        return self.get_state(character_id, now)
