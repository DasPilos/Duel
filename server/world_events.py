"""Observe authoritative world-state transitions and announce them once."""

import logging
import time

from core.production_buildings import BUILDINGS
from server.city_population import CityPopulation
from server.database import SYSTEM_USER_ID
from server.production_buildings import DEFAULT_FACTION, ProductionBuildings

LOGGER = logging.getLogger(__name__)
POLL_SECONDS = 30
EVENT_COOLDOWN_SECONDS = 15 * 60
STORAGE_BUILDINGS = ("farm", "lumber_camp", "mountain_rift", "barnyard", "black_pit", "barn", "stable")


class WorldEventWatcher:
    def __init__(self, snapshot_provider, publish, *, cooldown=EVENT_COOLDOWN_SECONDS):
        self.snapshot_provider = snapshot_provider
        self.publish = publish
        self.cooldown = float(cooldown)
        self.previous_food_status = None
        self.full_storage_buildings = None
        self.last_published = {}

    @staticmethod
    def _food_announcement(previous, current):
        if current == previous or current is None:
            return None
        if current == "В городе голод":
            return "food:hunger", {"event": "hunger"}, [
                "Летописец сообщает: в городе начался голод.",
                "В городе не хватает еды — жители голодают.",
                "Запасы пищи истощены: город охватил голод.",
            ]
        if current == "Население не доедает":
            return "food:shortage", {"event": "food_shortage"}, [
                "Жителям города не хватает пищи.",
                "Запасы еды сократились: население недоедает.",
                "Летописец предупреждает: в городе нехватка продовольствия.",
            ]
        if current == "Пищи достаточно" and previous in {
            "В городе голод", "Население не доедает",
        }:
            return "food:recovered", {"event": "food_recovered"}, [
                "Запасы пищи восстановлены — город снова обеспечен.",
                "В городе достаточно еды, голод отступил.",
                "Продовольственное положение в городе стабилизировалось.",
            ]
        return None

    @staticmethod
    def _storage_announcement(building, record):
        name = str(record["name"])
        total, limit = int(record["total"]), int(record["limit"])
        context = {"event": "storage_full", "building": name, "total": total, "limit": limit}
        lines = [
            f"Склад предприятия {name} заполнен ({total}/{limit}).",
            f"Производственный склад {name} достиг вместимости ({total}/{limit}).",
            f"Летописец: склад {name} заполнен; свободного места нет ({total}/{limit}).",
        ]
        return f"storage-full:{building}", context, lines

    def _announce(self, event_key, context, lines, now):
        previous = self.last_published.get(event_key)
        if previous is not None and now - previous < self.cooldown:
            return False
        if not self.publish(event_key, context, lines):
            return False
        self.last_published[event_key] = now
        return True

    def poll(self, now=None):
        now = time.monotonic() if now is None else float(now)
        snapshot = self.snapshot_provider()
        if snapshot is None:
            return 0

        announced = 0
        food_status = snapshot.get("food_status")
        if self.previous_food_status is None:
            self.previous_food_status = food_status
        else:
            event = self._food_announcement(self.previous_food_status, food_status)
            if event is None or self._announce(*event, now):
                self.previous_food_status = food_status
                if event is not None:
                    announced += 1

        storages = snapshot.get("storages", {})
        current_full = {
            building for building, record in storages.items()
            if int(record.get("limit", 0)) > 0
            and int(record.get("total", 0)) >= int(record["limit"])
        }
        if self.full_storage_buildings is None:
            self.full_storage_buildings = current_full
        else:
            newly_full = current_full - self.full_storage_buildings
            for building in sorted(newly_full):
                event = self._storage_announcement(building, storages[building])
                if self._announce(*event, now):
                    announced += 1
            self.full_storage_buildings = current_full
        return announced


def world_event_snapshot(database, now=None):
    """Read/update lazy authoritative world state using the existing services."""
    now = time.time() if now is None else float(now)
    world_id = int(database.world_id)
    with database.connection() as connection:
        character = connection.execute(
            """SELECT id FROM characters WHERE world_id = %s AND user_id <> %s
               ORDER BY id LIMIT 1""",
            (world_id, SYSTEM_USER_ID),
        ).fetchone()
        buildings = {
            row["building"] for row in connection.execute(
                """SELECT building FROM building_states
                   WHERE world_id = %s AND faction = %s""",
                (world_id, DEFAULT_FACTION),
            ).fetchall()
        }
    if character is None:
        return None

    character_id = int(character["id"])
    population = CityPopulation(database).get_state(character_id, now)
    production = ProductionBuildings(database)
    storages = {}
    for building in STORAGE_BUILDINGS:
        if building not in buildings or building not in BUILDINGS:
            continue
        try:
            state = production.get_state(character_id, building, now)
        except ValueError:
            LOGGER.exception("Cannot read world storage state for %s", building)
            continue
        storage = state.get("storage") or {}
        limit = int(storage.get("limit", 0))
        if limit <= 0:
            continue
        storages[building] = {
            "name": BUILDINGS[building]["name"],
            "total": int(state.get("storage_total", 0)),
            "limit": limit,
        }
    return {"food_status": population.get("food_status"), "storages": storages}


def run_world_event_watcher(database, stop_event, *, interval=POLL_SECONDS, watcher=None):
    from server.ai_commentator import enqueue_world_comment

    watcher = watcher or WorldEventWatcher(
        lambda: world_event_snapshot(database),
        lambda event_key, context, lines: enqueue_world_comment(
            database, event_key, context, lines,
        ),
    )
    while not stop_event.is_set():
        try:
            watcher.poll()
        except Exception:
            LOGGER.exception("World event watcher failed")
        if stop_event.wait(interval):
            break
