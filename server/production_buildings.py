"""Производственные и городские здания на сервере: общие для всех игроков фракции в мире.

Всё состояние и все расчёты (производство, выгрузка, стадии, улучшение) — здесь; клиент только отображает ответ.
Личное у игрока только инвентарь: материалы улучшения берутся из рюкзака того, кто их сдаёт.
"""

import json
import math
import random
import time
from copy import deepcopy
from contextlib import contextmanager

from core.cart_progress import CART_GRADES, DEFAULT_CART_PROGRESS, RESOURCE_ITEM_IDS, cart_stats
from core.currency import Currency
from core.production_buildings import (
    BUILDINGS,
    RESOURCES,
    building_config,
    building_level_info,
    building_resources,
    horse_purchase_price_silver,
    PRODUCTION_ITEM_IDS,
    slot_resources,
    upgrade_requirements,
)
from server.database import lock_character
from server.items_database import ItemsDatabase

# Пока в игре одна фракция; когда появится выбор фракции, её нужно хранить у персонажа
DEFAULT_FACTION = "light"
STORAGE_ITEM_IDS = {
    "berries": 62,
    "wheat": 63,
    "meat": 67,
    "wood": 60,
    "board": 61,
    "flax": 64,
    "cotton": 65,
    "leather": 66,
    "coal": 68,
    "stone": 69,
    "iron": 10,
    "mithril": 71,
    "obsidian": 72,
    "jet": 80,
    "malachite": 81,
    "topaz": 82,
    "garnet": 83,
    "emerald": 84,
    "ruby": 85,
    "sapphire": 86,
    "diamond": 87,
    "iron_ingot": 73,
    "steel": 74,
    "hard_leather": 75,
    "thick_leather": 76,
    "cloth": 77,
    "stone_block": 78,
}
STORAGE_RESOURCES_BY_ITEM_ID = {item_id: resource for resource, item_id in STORAGE_ITEM_IDS.items()}
HARVEST_BONUS_RESOURCE_ALIASES = {"iron_ore": "iron"}


def _harvest_bonus_for_worker(connection, worker_id):
    if not worker_id or not str(worker_id).startswith("player:"):
        return {}
    character_id = int(str(worker_id).split(":", 1)[1])
    rows = connection.execute(
        """SELECT c.effects_json FROM character_equipment equipment
           JOIN items_catalog c ON c.id = equipment.item_id
           WHERE equipment.character_id = %s""",
        (character_id,),
    ).fetchall()
    bonuses = {}
    for row in rows:
        effects = json.loads(row["effects_json"] or "{}")
        for resource, percent in effects.get("harvest_bonus", {}).items():
            resource = HARVEST_BONUS_RESOURCE_ALIASES.get(resource, resource)
            bonuses[resource] = bonuses.get(resource, 0) + int(percent)
    return bonuses


def _resource_timer_sec(resource, harvest_bonus=None):
    base_timer = RESOURCES.get(resource, {}).get("timer_sec")
    if base_timer is None:
        return None
    percent = max(0, min(90, int((harvest_bonus or {}).get(resource, 0))))
    return max(1, math.ceil(base_timer * (100 - percent) / 100))


def _timestamp(now):
    return time.time() if now is None else float(now)


def _completed_units(hire_time, now, timer_sec):
    if hire_time is None:
        return 0
    return max(0, math.floor((float(now) - float(hire_time)) / timer_sec))


def _new_units(building, slot, now, harvest_bonus=None):
    """Единицы, готовые с прошлого учёта, и новые счётчики credited (горожанин может давать несколько ресурсов)."""
    credited = dict(slot["credited"] or {})
    added = {}
    for resource in slot_resources(building, slot["slot_index"]):
        timer_sec = _resource_timer_sec(resource, harvest_bonus)
        if timer_sec is None:
            continue
        total = _completed_units(slot["hire_time"], now, timer_sec)
        fresh = total - credited.get(resource, 0)
        if fresh > 0:
            added[resource] = fresh
            credited[resource] = total
    return added, credited


def distribute_to_storage(storage, incoming, limit):
    """Accept each produced resource immediately, proportionally when shared storage is nearly full."""
    free = max(0, limit - sum(storage.values()))
    total = sum(incoming.values())
    if total <= free:
        return dict(incoming)
    accepted = {resource: incoming[resource] * free // total for resource in incoming}
    leftover = free - sum(accepted.values())
    for resource in incoming:
        if leftover <= 0:
            break
        if accepted[resource] < incoming[resource]:
            accepted[resource] += 1
            leftover -= 1
    return accepted


def reconcile_player_harvest_claims(connection, key, resource, storage_amount):
    """Keep personal claim quotas as allocations within, never additions to, shared stock."""
    claims = connection.execute(
        f"""SELECT character_id, claimable FROM building_player_resources
            WHERE {_WHERE} AND resource = %s AND claimable > 0
            ORDER BY character_id FOR UPDATE""",
        (*key, resource),
    ).fetchall()
    total_claimable = sum(int(row["claimable"]) for row in claims)
    available = max(0, int(storage_amount))
    if total_claimable <= available:
        return
    allocated = [int(row["claimable"]) * available // total_claimable for row in claims]
    remainder = available - sum(allocated)
    for index, row in enumerate(claims):
        if remainder <= 0:
            break
        if allocated[index] < int(row["claimable"]):
            allocated[index] += 1
            remainder -= 1
    for row, amount in zip(claims, allocated):
        if amount != int(row["claimable"]):
            connection.execute(
                f"""UPDATE building_player_resources SET claimable = %s
                    WHERE {_WHERE} AND character_id = %s AND resource = %s""",
                (amount, *key, int(row["character_id"]), resource),
            )


# Условие для ключа здания: (world_id, faction, building)
_WHERE = "world_id = %s AND faction = %s AND building = %s"


class ProductionBuildings:
    """Общие здания фракции. Методы принимают персонажа, от имени которого действует игрок."""

    def __init__(self, database, rng=None):
        self.db = database
        self.rng = rng or random.Random()

    def _bonus_resource(self, building, level):
        """Optional resource bonus for one newly mined coal unit."""
        bonus = building_config(building).get("bonus")
        chance = bonus["unit_bonus_chance"].get(int(level), 0) if bonus else 0
        if not chance or self.rng.random() >= chance:
            return None
        weights = bonus["weights"][int(level)]
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    @staticmethod
    def _building_key(connection, character_id, building):
        row = connection.execute("SELECT world_id FROM characters WHERE id = %s", (int(character_id),)).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        return row["world_id"], DEFAULT_FACTION, building

    @staticmethod
    def _state(connection, key):
        return connection.execute(f"SELECT * FROM building_states WHERE {_WHERE}", key).fetchone()

    @staticmethod
    def _resources(connection, key):
        rows = connection.execute(
            f"SELECT resource, storage, buffer FROM building_resources WHERE {_WHERE}", key
        ).fetchall()
        return {row["resource"]: row for row in rows}

    @staticmethod
    def _slots(connection, key):
        return connection.execute(
            f"""SELECT slot_index, occupied, worker_id, hire_time, credited
                FROM building_worker_slots WHERE {_WHERE} ORDER BY slot_index""",
            key,
        ).fetchall()

    def active_player_work(self, character_id):
        player_worker_id = f"player:{int(character_id)}"
        with self.db.connection() as connection:
            world_id = self._building_key(connection, character_id, "farm")[0]
            row = connection.execute(
                """SELECT building, slot_index FROM building_worker_slots
                   WHERE world_id = %s AND faction = %s AND occupied = 1 AND worker_id = %s
                   LIMIT 1""",
                (world_id, DEFAULT_FACTION, player_worker_id),
            ).fetchone()
        if row is None:
            return None
        return {"building": row["building"], "slot_index": int(row["slot_index"])}

    @contextmanager
    def _transaction(self, character_id, building, now):
        """Блокировка персонажа (его рюкзак) и здания (общее для фракции), догон времени здания до now."""
        building_config(building)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            key = self._building_key(connection, character_id, building)
            self._ensure(connection, key, now)
            connection.execute(f"SELECT 1 FROM building_states WHERE {_WHERE} FOR UPDATE", key)
            self._advance(connection, key, now)
            yield connection, key

    def _ensure(self, connection, key, now):
        building = key[2]
        connection.execute(
            """INSERT INTO building_states (world_id, faction, building, level, cycle_start_time)
               VALUES (%s, %s, %s, 1, %s) ON CONFLICT (world_id, faction, building) DO NOTHING""",
            (*key, now),
        )
        for resource in building_resources(building):
            connection.execute(
                """INSERT INTO building_resources (world_id, faction, building, resource)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (world_id, faction, building, resource) DO NOTHING""",
                (*key, resource),
            )
        level = self._state(connection, key)["level"]
        for slot_index in range(building_level_info(level, building)["max_workers"]):
            connection.execute(
                """INSERT INTO building_worker_slots (world_id, faction, building, slot_index)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (world_id, faction, building, slot_index) DO NOTHING""",
                (*key, slot_index),
            )
        if building == "stable":
            for grade, progress in DEFAULT_CART_PROGRESS["grades"].items():
                connection.execute(
                    """INSERT INTO stable_cart_progress
                       (world_id, faction, building, grade, blueprint_owned, body_owned,
                        wood_deposited, silver_deposited, upgrades_json)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                       ON CONFLICT (world_id, faction, building, grade) DO NOTHING""",
                    (*key, int(grade), progress["blueprint_owned"], progress["body_owned"],
                     progress["wood_deposited"], progress["silver_deposited"],
                     json.dumps(progress["upgrades"])),
                )

    def _advance(self, connection, key, now):
        """Accrue completed worker units directly to storage up to the current time."""
        finish_at = self._state(connection, key)["upgrade_finish_at"]
        if finish_at is not None and finish_at <= now:
            self._sync_harvest(connection, key, finish_at)
            connection.execute(
                f"UPDATE building_states SET level = level + 1, upgrade_finish_at = NULL WHERE {_WHERE}", key
            )
            self._ensure(connection, key, finish_at)
        self._sync_harvest(connection, key, now)

    def _sync_harvest(self, connection, key, now):
        """Credit each completed unit directly to shared storage; never queue new buffer."""
        building = key[2]
        rows = self._resources(connection, key)
        storage = {resource: int(row["storage"]) for resource, row in rows.items()}
        incoming = {resource: int(row["buffer"]) for resource, row in rows.items()}
        added = {}
        player_added = {}
        level = int(self._state(connection, key)["level"])
        storage_limit = int(building_level_info(level, building)["storage"])
        for slot in self._slots(connection, key):
            if not slot["occupied"] or slot["hire_time"] is None:
                continue
            harvest_bonus = _harvest_bonus_for_worker(connection, slot["worker_id"])
            fresh, credited = _new_units(building, slot, now, harvest_bonus)
            for resource, amount in fresh.items():
                added[resource] = added.get(resource, 0) + amount
                incoming[resource] = incoming.get(resource, 0) + amount
                worker_id = slot["worker_id"] or ""
                if worker_id.startswith("player:"):
                    character_id = int(worker_id.split(":", 1)[1])
                    resource_players = player_added.setdefault(resource, {})
                    resource_players[character_id] = resource_players.get(character_id, 0) + amount
                    connection.execute(
                        """
                        INSERT INTO building_player_resources
                            (world_id, faction, building, character_id, resource, buffered, total_produced)
                        VALUES (%s, %s, %s, %s, %s, 0, %s)
                        ON CONFLICT (world_id, faction, building, character_id, resource)
                        DO UPDATE SET total_produced = building_player_resources.total_produced + EXCLUDED.total_produced
                        """,
                        (*key, character_id, resource, amount),
                    )
            connection.execute(
                f"UPDATE building_worker_slots SET credited = %s::jsonb WHERE {_WHERE} AND slot_index = %s",
                (json.dumps(credited), *key, slot["slot_index"]),
            )
        if building == "black_pit":
            for _ in range(added.get("coal", 0)):
                bonus = self._bonus_resource(building, level)
                if bonus:
                    incoming[bonus] = incoming.get(bonus, 0) + 1

        accepted = distribute_to_storage(storage, incoming, storage_limit)
        for resource, amount in accepted.items():
            player_rows = connection.execute(
                f"""SELECT character_id, buffered FROM building_player_resources
                    WHERE {_WHERE} AND resource=%s AND (buffered > 0 OR character_id = ANY(%s))
                    ORDER BY character_id FOR UPDATE""",
                (*key, resource, list(player_added.get(resource, {}))),
            ).fetchall()
            player_buffered = {
                int(row["character_id"]): int(row["buffered"])
                for row in player_rows
            }
            for character_id, fresh in player_added.get(resource, {}).items():
                player_buffered[character_id] = player_buffered.get(character_id, 0) + fresh
            player_total = sum(player_buffered.values())
            incoming_total = int(incoming.get(resource, 0))
            player_accepted = (player_total if amount >= incoming_total else
                               player_total * amount // incoming_total if incoming_total else 0)
            claims = {
                character_id: (buffered * player_accepted // player_total if player_total else 0)
                for character_id, buffered in player_buffered.items()
            }
            leftover = player_accepted - sum(claims.values())
            for character_id, buffered in sorted(player_buffered.items()):
                if leftover <= 0:
                    break
                if claims[character_id] < buffered:
                    claims[character_id] += 1
                    leftover -= 1
            for character_id in player_buffered:
                claim = claims[character_id]
                connection.execute(
                    f"""UPDATE building_player_resources
                        SET claimable=claimable+%s, buffered=0
                        WHERE {_WHERE} AND character_id=%s AND resource=%s""",
                    (claim, *key, character_id, resource),
                )
            connection.execute(
                f"""UPDATE building_player_resources SET buffered=0
                    WHERE {_WHERE} AND resource=%s""",
                (*key, resource),
            )
            connection.execute(
                f"""UPDATE building_resources SET storage=storage+%s, buffer=0
                    WHERE {_WHERE} AND resource=%s""",
                (amount, *key, resource),
            )
        connection.execute(
            f"UPDATE building_resources SET buffer=0 WHERE {_WHERE}", key
        )
        connection.execute(
            f"UPDATE building_player_resources SET buffered=0 WHERE {_WHERE}", key
        )

    def _payload(self, connection, key, character_id, now):
        building = key[2]
        self._sync_harvest(connection, key, now)
        state = self._state(connection, key)
        rows = self._resources(connection, key)
        for resource, row in rows.items():
            reconcile_player_harvest_claims(connection, key, resource, row["storage"])
        info = building_level_info(state["level"], building)
        slots = []
        for slot in self._slots(connection, key):
            resources = slot_resources(building, slot["slot_index"])
            harvest_bonus = _harvest_bonus_for_worker(connection, slot["worker_id"])
            worker_name = slot["worker_id"]
            travel_direction = None
            arrival_at = None
            if worker_name and worker_name.startswith("player:"):
                worker_row = connection.execute(
                    "SELECT name FROM characters WHERE id = %s",
                    (int(worker_name.split(":", 1)[1]),),
                ).fetchone()
                worker_name = worker_row["name"] if worker_row else "Игрок"
            elif worker_name and worker_name.startswith("citizen:"):
                citizen_id = int(worker_name.split(":", 1)[1])
                citizen_row = connection.execute(
                    """SELECT name, travel_direction, arrival_at FROM city_citizens
                       WHERE id = %s""",
                    (citizen_id,),
                ).fetchone()
                worker_name = citizen_row["name"] if citizen_row else "Горожанин"
                if citizen_row:
                    travel_direction = citizen_row["travel_direction"]
                    arrival_at = citizen_row["arrival_at"]
            elif worker_name and worker_name.startswith("citizen-"):
                worker_name = f"Горожанин {worker_name.split('-', 1)[1]}"
            travel_seconds_left = (
                max(0, math.ceil(float(arrival_at) - now))
                if travel_direction == "outbound" and arrival_at is not None and float(arrival_at) > now
                else 0
            )
            is_travelling = travel_seconds_left > 0
            timer_sec_by_resource = {
                resource: _resource_timer_sec(resource, harvest_bonus)
                for resource in resources if _resource_timer_sec(resource, harvest_bonus) is not None
            }
            timer_sec = timer_sec_by_resource.get(resources[0], RESOURCES[resources[0]].get("timer_sec", 0))
            resource_progress = {
                resource: (0 if not slot["occupied"] or is_travelling else
                           int((now - slot["hire_time"]) % timer_sec_by_resource[resource]))
                for resource in resources if resource in timer_sec_by_resource
            }
            slots.append({
                "slot_index": slot["slot_index"],
                "resource": resources[0],
                "resources": list(resources),
                "occupied": bool(slot["occupied"]),
                "worker_id": slot["worker_id"],
                "worker_name": worker_name,
                "is_player": bool(slot["worker_id"] and slot["worker_id"].startswith("player:")),
                "travel_direction": travel_direction,
                "is_travelling": is_travelling,
                "travel_seconds_left": travel_seconds_left,
                "player_id": (int(slot["worker_id"].split(":", 1)[1])
                              if slot["worker_id"] and slot["worker_id"].startswith("player:") else None),
                "hire_time": slot["hire_time"],
                "progress_sec": (0 if not slot["occupied"] or is_travelling else
                                 int((now - slot["hire_time"]) % timer_sec)),
                "resource_progress_sec": resource_progress,
                "timer_sec_by_resource": timer_sec_by_resource,
                "harvest_bonus": {resource: percent for resource, percent in harvest_bonus.items()
                                   if resource in resources},
            })
        next_harvest_seconds = min((
            max(0, timer - slot["resource_progress_sec"].get(resource, 0))
            for slot in slots if slot["occupied"] and not slot["is_travelling"]
            for resource, timer in slot["timer_sec_by_resource"].items()
        ), default=None)
        player_claim_rows = connection.execute(
            f"""SELECT resource, claimable FROM building_player_resources
                WHERE {_WHERE} AND character_id = %s AND claimable > 0""",
            (*key, int(character_id)),
        ).fetchall()
        player_harvest_claims = {row["resource"]: row["claimable"] for row in player_claim_rows}
        player_total_rows = connection.execute(
            f"""SELECT resource, total_produced FROM building_player_resources
                WHERE {_WHERE} AND character_id = %s AND total_produced > 0""",
            (*key, int(character_id)),
        ).fetchall()
        player_harvest_totals = {row["resource"]: row["total_produced"] for row in player_total_rows}
        player_worker_id = f"player:{int(character_id)}"
        player_work_slot = next(
            (slot for slot in slots if slot["occupied"] and slot["worker_id"] == player_worker_id), None
        )
        player_work = None
        if player_work_slot is not None:
            work_resources = slot_resources(building, player_work_slot["slot_index"])
            work_resource = work_resources[0]
            work_harvest_bonus = player_work_slot.get("harvest_bonus", {})
            work_timer = _resource_timer_sec(work_resource, work_harvest_bonus)
            work_progress = int((now - player_work_slot["hire_time"]) % work_timer)
            player_work = {
                "slot_index": player_work_slot["slot_index"],
                "resource": work_resource,
                "resources": list(work_resources),
                "timer_sec": work_timer,
                "progress_sec": work_progress,
                "seconds_to_next": work_timer - work_progress,
                "harvest_bonus": work_harvest_bonus,
                "total_produced": {resource: player_harvest_totals.get(resource, 0)
                                   for resource in work_resources},
            }
        storage = {resource: row["storage"] for resource, row in rows.items()}
        storage_depositable = {}
        storage_withdrawable = {}
        carry_state = ItemsDatabase.carry_weight_state(connection, character_id)
        free_storage = max(0, info["storage"] - sum(storage.values()))
        for resource in building_resources(building):
            item_id = STORAGE_ITEM_IDS.get(resource)
            if item_id is not None:
                in_backpack = self._backpack_amount(connection, character_id, item_id)
                storage_depositable[resource] = {
                    "item_id": item_id,
                    "in_backpack": in_backpack,
                    "max_deposit": min(in_backpack, free_storage),
                }
                item = ItemsDatabase._catalog_item(connection, item_id)
                storage_withdrawable[resource] = {
                    "available": int(storage.get(resource, 0)),
                    "max_withdraw": ItemsDatabase.max_addable_quantity(
                        connection, character_id, item_id, storage.get(resource, 0), carry_state
                    ),
                    "item_weight_kg": 0.0 if item is None else float(item["weight"] or 0),
                    **carry_state,
                }
        stall_slots = None
        occupied_stalls = 0
        feed_consumption = 0
        stall_upgrades = None
        cart_progress = None
        available_carts = []
        available_cart_drivers = []
        treasury_silver_available = 0
        backpack_resource_amounts = {}
        if building == "stable":
            active_convoys = connection.execute(
                """SELECT id, cart_id, driver_citizen_id, status FROM transport_convoys
                   WHERE world_id = %s AND faction = %s AND status IN ('outbound','blocked')""",
                key[:2],
            ).fetchall()
            convoy_by_cart = {row["cart_id"]: row for row in active_convoys}
            busy_driver_ids = {int(row["driver_citizen_id"]) for row in active_convoys}
            available_cart_drivers = [
                {"id": int(row["id"]), "name": row["name"], "satiety": int(row["satiety"]),
                 "satisfaction": row["satisfaction"]}
                for row in connection.execute(
                    """SELECT id,name,satiety,satisfaction FROM city_citizens
                              WHERE world_id=%s AND faction=%s AND alive=TRUE AND satisfaction='satisfied'
                                                 AND job_building IS NULL AND working=FALSE AND travel_direction IS NULL
                       ORDER BY ordinal""",
                    key[:2],
                ).fetchall()
                if int(row["id"]) not in busy_driver_ids
            ]
            resting_horse_count = connection.execute(
                """SELECT COUNT(*) AS count FROM stable_horses
                   WHERE world_id=%s AND faction=%s AND building='stable' AND status='Отдыхает'""",
                key[:2],
            ).fetchone()["count"]
            cart_progress = self._cart_progress(connection, key)
            for grade, progress in cart_progress["grades"].items():
                if not progress.get("body_owned"):
                    continue
                cart_grade = CART_GRADES[grade]
                stats = cart_stats(progress.get("upgrades", {}))
                active_convoy = convoy_by_cart.get(f"cart_grade_{grade}")
                can_travel = (
                    active_convoy is None
                    and resting_horse_count >= int(cart_grade.get("horse_count", 0))
                    and bool(available_cart_drivers)
                )
                available_carts.append({
                    "id": f"cart_grade_{grade}",
                    "grade": int(grade),
                    "name": cart_grade["name"],
                    "status": ("Ожидает разгрузки" if active_convoy and active_convoy["status"] == "blocked"
                               else "В пути" if active_convoy else "Свободна"),
                    "can_travel": can_travel,
                    "dispatch_available": can_travel,
                    "sprite_key": cart_grade.get("sprite_key", "light"),
                    "horse_slots": int(cart_grade.get("horse_count", 0)),
                    "resource_slots": int(cart_grade.get("resource_slots", 0)),
                    "capacity_kg": stats["capacity_kg"],
                    "seconds_per_tile": stats["seconds_per_tile"],
                    "empty_tiles_per_hour": stats["empty_tiles_per_hour"],
                    "full_load_speed_penalty_percent": stats["full_load_speed_penalty_percent"],
                })
            level_tables = building_config(building)["levels"]
            upgrade_config = building_config(building)["stall_upgrades"]
            purchased_rows = connection.execute(
                f"SELECT upgrade_id, finish_at FROM stable_stall_upgrades WHERE {_WHERE}", key
            ).fetchall()
            purchased_by_id = {row["upgrade_id"]: row for row in purchased_rows}
            purchased_upgrades = set(purchased_by_id)
            completed_upgrades = {
                upgrade_id for upgrade_id, row in purchased_by_id.items()
                if row["finish_at"] is not None and row["finish_at"] <= now
            }
            contribution_rows = connection.execute(
                f"SELECT upgrade_id, wood_deposited, silver_deposited "
                f"FROM stable_stall_upgrade_contributions WHERE {_WHERE}", key
            ).fetchall()
            contributions = {row["upgrade_id"]: row for row in contribution_rows}
            currency_row = connection.execute(
                "SELECT copper, silver, gold FROM characters WHERE id = %s",
                (int(character_id),),
            ).fetchone()
            silver_available = Currency(**currency_row).total_silver
            treasury_row = connection.execute(
                """SELECT treasury_copper FROM city_population_state
                   WHERE world_id = %s AND faction = %s""",
                key[:2],
            ).fetchone()
            treasury_silver_available = (0 if treasury_row is None else
                                         int(treasury_row["treasury_copper"]) // Currency.COPPER_PER_SILVER)
            backpack_resource_amounts = {
                resource: int(self._backpack_amount(connection, character_id, item_id))
                for resource, item_id in RESOURCE_ITEM_IDS.items()
            }
            stall_capacity_bonus = sum(
                upgrade_config[upgrade_id]["horse_capacity"] for upgrade_id in completed_upgrades
            )
            stall_capacity = info["stall_capacity"] + stall_capacity_bonus
            horse_rows = connection.execute(
                f"""SELECT id, slot_index, name, breed, status, purchase_price_silver
                    FROM stable_horses WHERE {_WHERE} ORDER BY id""",
                key,
            ).fetchall()
            horses_by_slot = {horse["slot_index"]: horse for horse in horse_rows}
            occupied_stalls = len(horse_rows)
            base_max_stalls = max(level_info["stall_capacity"] for level_info in level_tables.values())
            max_stalls = base_max_stalls + sum(
                upgrade["horse_capacity"] for upgrade in upgrade_config.values()
            )
            stall_upgrades = {
                upgrade_id: {
                    **upgrade,
                    "wood_deposited": contributions.get(upgrade_id, {}).get("wood_deposited", 0),
                    "silver_deposited": contributions.get(upgrade_id, {}).get("silver_deposited", 0),
                    "wood_in_warehouse": self._warehouse_amount(
                        connection, key, upgrade["wood_item_id"]
                    ),
                    "treasury_silver_available": treasury_silver_available,
                    "purchased": upgrade_id in purchased_upgrades,
                    "wood_remaining": max(
                        0, int(upgrade["wood_cost"])
                        - int(contributions.get(upgrade_id, {}).get("wood_deposited", 0))
                    ),
                    "silver_remaining": max(
                        0, int(upgrade["silver_cost"])
                        - int(contributions.get(upgrade_id, {}).get("silver_deposited", 0))
                    ),
                    "completed": upgrade_id in completed_upgrades,
                    "in_progress": (
                        upgrade_id in purchased_by_id and upgrade_id not in completed_upgrades
                    ),
                    "finish_at": purchased_by_id.get(upgrade_id, {}).get("finish_at"),
                    "seconds_left": (
                        max(0, int(math.ceil(purchased_by_id[upgrade_id]["finish_at"] - now)))
                        if upgrade_id in purchased_by_id
                        and purchased_by_id[upgrade_id]["finish_at"] is not None
                        and upgrade_id not in completed_upgrades else 0
                    ),
                    "can_purchase": (
                        contributions.get(upgrade_id, {}).get("wood_deposited", 0)
                        + self._warehouse_amount(connection, key, upgrade["wood_item_id"])
                        >= upgrade["wood_cost"]
                        and contributions.get(upgrade_id, {}).get("silver_deposited", 0)
                        + treasury_silver_available >= upgrade["silver_cost"]
                    ),
                }
                for upgrade_id, upgrade in upgrade_config.items()
            }
            for upgrade in stall_upgrades.values():
                upgrade["ready"] = upgrade["purchased"] or upgrade["can_purchase"]
            for upgrade_id, upgrade in stall_upgrades.items():
                upgrade["can_purchase"] = upgrade["purchased"] or (
                    upgrade["wood_in_warehouse"] >= upgrade["wood_remaining"]
                    and treasury_silver_available >= upgrade["silver_remaining"]
                )
            stall_slots = []
            for slot_index in range(max_stalls):
                unlock_level = next(
                    (level for level, level_info in level_tables.items()
                     if level_info["stall_capacity"] > slot_index),
                    max(level_tables),
                )
                stall_slots.append({
                    "slot_index": slot_index,
                    "unlocked": slot_index < stall_capacity,
                    "unlock_level": 1 if slot_index < stall_capacity else unlock_level,
                    "horse": None if slot_index not in horses_by_slot else {
                        "id": horses_by_slot[slot_index]["id"],
                        "name": horses_by_slot[slot_index]["name"],
                        "breed": horses_by_slot[slot_index]["breed"],
                        "status": horses_by_slot[slot_index]["status"],
                        "can_travel": horses_by_slot[slot_index]["status"] == "Отдыхает",
                        "purchase_price_silver": horses_by_slot[slot_index]["purchase_price_silver"],
                    },
                })
            feed_consumption = occupied_stalls * building_config(building)["feed_kg_per_horse_hour"]
        return {
            "building": building,
            "faction": key[1],
            "server_time": now,
            "level": state["level"],
            "max_workers": info["max_workers"],
            "stall_capacity": stall_capacity if building == "stable" else info.get("stall_capacity"),
            "stall_capacity_bonus": stall_capacity_bonus if building == "stable" else 0,
            "stall_slots": stall_slots,
            "stall_upgrades": stall_upgrades,
            "cart_progress": cart_progress,
            "available_carts": available_carts,
            "available_cart_drivers": available_cart_drivers,
            "backpack_resource_amounts": backpack_resource_amounts,
            "treasury_silver_available": treasury_silver_available,
            "silver_available": silver_available if building == "stable" else None,
            "horse_price_next_silver": (
                horse_purchase_price_silver(occupied_stalls) if building == "stable" else None
            ),
            "occupied_stalls": occupied_stalls,
            "feed_resource": building_config(building).get("feed_resource"),
            "feed_resource_label": RESOURCES.get(building_config(building).get("feed_resource"), {}).get("label"),
            "feed_consumption_kg_per_hour": feed_consumption,
            "workers": sum(1 for slot in slots if slot["occupied"]),
            "stage": min(
                3, sum(int(row["storage"]) for row in rows.values()) * 4 // max(1, info["storage"]),
            ),
            "next_harvest_seconds": next_harvest_seconds,
            "storage": {**storage, "limit": info["storage"]},
            "storage_total": sum(storage.values()),
            "storage_depositable": storage_depositable,
            "storage_withdrawable": storage_withdrawable,
            **carry_state,
            "warehouse_storage": self._warehouse_storage(connection, key) if building == "stable" else None,
            "worker_slots": slots,
            "player_work": player_work,
            "player_harvest_claims": player_harvest_claims,
            "player_harvest_totals": player_harvest_totals,
            "resource_timer_sec": {
                resource: (_resource_timer_sec(resource, player_work_slot.get("harvest_bonus", {}))
                           if player_work_slot and resource in slot_resources(building, player_work_slot["slot_index"])
                           else RESOURCES[resource]["timer_sec"])
                for resource in rows if "timer_sec" in RESOURCES[resource]
            },
            "upgrade": self._upgrade_payload(connection, key, character_id, state, now),
        }

    @staticmethod
    def _deposited(connection, key):
        rows = connection.execute(
            f"SELECT item_id, quantity FROM building_upgrade_materials WHERE {_WHERE}", key
        ).fetchall()
        return {row["item_id"]: row["quantity"] for row in rows}

    @staticmethod
    def _backpack_amount(connection, character_id, item_id):
        return connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS amount FROM character_items WHERE character_id = %s AND item_id = %s",
            (int(character_id), int(item_id)),
        ).fetchone()["amount"]

    @staticmethod
    def _warehouse_storage(connection, key):
        rows = connection.execute(
            """SELECT resource, storage FROM building_resources
               WHERE world_id = %s AND faction = %s AND building = 'warehouse'""",
            (key[0], key[1]),
        ).fetchall()
        return {row["resource"]: row["storage"] for row in rows}

    def _debit_warehouse_items(self, connection, key, item_costs, now):
        costs = {}
        for item_id, amount in item_costs.items():
            amount = max(0, int(amount))
            resource = STORAGE_RESOURCES_BY_ITEM_ID.get(int(item_id))
            if amount and resource is None:
                raise ValueError(f"Предмет {item_id} нельзя купить со склада")
            if amount:
                costs[resource] = costs.get(resource, 0) + amount
        if not costs:
            return

        warehouse_key = (int(key[0]), key[1], "warehouse")
        self._ensure(connection, warehouse_key, now)
        connection.execute(
            f"SELECT 1 FROM building_states WHERE {_WHERE} FOR UPDATE", warehouse_key
        )
        rows = connection.execute(
            """SELECT resource, storage FROM building_resources
               WHERE world_id = %s AND faction = %s AND building = 'warehouse'
                 AND resource = ANY(%s) FOR UPDATE""",
            (warehouse_key[0], warehouse_key[1], list(costs)),
        ).fetchall()
        available = {row["resource"]: int(row["storage"]) for row in rows}
        shortages = [
            f"{RESOURCES[resource]['label']}: {available.get(resource, 0)}/{amount}"
            for resource, amount in costs.items()
            if available.get(resource, 0) < amount
        ]
        if shortages:
            raise ValueError("Недостаточно ресурсов на общем складе: " + ", ".join(shortages))
        for resource, amount in costs.items():
            connection.execute(
                """UPDATE building_resources SET storage = storage - %s
                   WHERE world_id = %s AND faction = %s AND building = 'warehouse'
                     AND resource = %s""",
                (amount, warehouse_key[0], warehouse_key[1], resource),
            )

    @staticmethod
    def _debit_treasury(connection, key, amount_copper):
        amount_copper = max(0, int(amount_copper))
        if not amount_copper:
            return
        treasury = connection.execute(
            """SELECT treasury_copper FROM city_population_state
               WHERE world_id = %s AND faction = %s FOR UPDATE""",
            (int(key[0]), key[1]),
        ).fetchone()
        available = 0 if treasury is None else int(treasury["treasury_copper"])
        if available < amount_copper:
            needed_silver = (amount_copper + Currency.COPPER_PER_SILVER - 1) // Currency.COPPER_PER_SILVER
            have_silver = available // Currency.COPPER_PER_SILVER
            raise ValueError(f"В казне недостаточно средств: {have_silver}/{needed_silver} серебра")
        connection.execute(
            """UPDATE city_population_state SET treasury_copper = treasury_copper - %s
               WHERE world_id = %s AND faction = %s""",
            (amount_copper, int(key[0]), key[1]),
        )

    @staticmethod
    def _cart_progress(connection, key):
        progress = deepcopy(DEFAULT_CART_PROGRESS)
        rows = connection.execute(
            f"""SELECT grade, blueprint_owned, body_owned, wood_deposited,
                       silver_deposited, upgrades_json
                FROM stable_cart_progress WHERE {_WHERE}""",
            key,
        ).fetchall()
        for row in rows:
            grade = str(row["grade"])
            upgrades = row["upgrades_json"] or {}
            if isinstance(upgrades, str):
                upgrades = json.loads(upgrades)
            progress["grades"][grade].update({
                "blueprint_owned": row["blueprint_owned"],
                "body_owned": row["body_owned"],
                "wood_deposited": row["wood_deposited"],
                "silver_deposited": row["silver_deposited"],
                "upgrades": dict(upgrades),
            })
        return progress

    def contribute_cart(self, character_id, resource, quantity, now=None, source=None):
        raise ValueError(
            "Отдельные взносы за повозку отключены. Пополните общий склад и казну, затем купите повозку."
        )

    def purchase_cart(self, character_id, grade_id=1, now=None):
        now = _timestamp(now)
        grade_id = int(grade_id)
        if grade_id != 1:
            raise ValueError("Эта повозка пока недоступна для покупки")
        with self._transaction(character_id, "stable", now) as (connection, key):
            config = CART_GRADES[str(grade_id)]
            progress = connection.execute(
                f"""SELECT wood_deposited, silver_deposited, body_owned
                    FROM stable_cart_progress WHERE {_WHERE} AND grade = %s FOR UPDATE""",
                (*key, grade_id),
            ).fetchone()
            if progress["body_owned"]:
                raise ValueError("Лёгкая повозка уже куплена")
            stable_level = int(self._state(connection, key)["level"])
            if stable_level < int(config.get("required_stable_level", 1)):
                raise ValueError("Недостаточный уровень конюшни для покупки повозки")

            wood_due = max(0, int(config["wood_cost"]) - int(progress["wood_deposited"]))
            silver_due = max(0, int(config["silver_cost"]) - int(progress["silver_deposited"]))
            self._debit_warehouse_items(
                connection, key, {STORAGE_ITEM_IDS["wood"]: wood_due}, now,
            )
            self._debit_treasury(
                connection, key, Currency.to_copper(silver=silver_due),
            )
            connection.execute(
                f"""UPDATE stable_cart_progress
                    SET body_owned = TRUE, wood_deposited = %s, silver_deposited = %s
                    WHERE {_WHERE} AND grade = %s""",
                (int(config["wood_cost"]), int(config["silver_cost"]), *key, grade_id),
            )
            return self._payload(connection, key, character_id, now)

    @classmethod
    def _warehouse_amount(cls, connection, key, item_id):
        resource = STORAGE_RESOURCES_BY_ITEM_ID.get(int(item_id))
        if resource is None:
            return 0
        row = connection.execute(
            """SELECT storage FROM building_resources
               WHERE world_id = %s AND faction = %s AND building = 'warehouse' AND resource = %s""",
            (key[0], key[1], resource),
        ).fetchone()
        return 0 if row is None else int(row["storage"])

    @classmethod
    def _take_inventory_items(cls, connection, character_id, item_id, quantity):
        rows = connection.execute(
            """SELECT id, quantity FROM character_items
               WHERE character_id = %s AND item_id = %s ORDER BY slot_index DESC FOR UPDATE""",
            (int(character_id), int(item_id)),
        ).fetchall()
        if sum(row["quantity"] for row in rows) < quantity:
            return False
        remaining = quantity
        for row in rows:
            if remaining <= 0:
                break
            taken = min(row["quantity"], remaining)
            ItemsDatabase._take_from_row(connection, row, taken)
            remaining -= taken
        return True

    def deposit_to_storage(self, character_id, building, resource, quantity, now=None):
        """Move matching resources from a player's backpack into a shared building store."""
        now = _timestamp(now)
        building = str(building)
        resource = str(resource)
        quantity = int(quantity)
        if building not in BUILDINGS or resource not in building_resources(building):
            raise ValueError("Этот ресурс нельзя выгрузить в выбранное хранилище")
        item_id = STORAGE_ITEM_IDS.get(resource)
        if item_id is None or quantity <= 0:
            raise ValueError("Некорректный ресурс или количество")

        with self._transaction(character_id, building, now) as (connection, key):
            state = self._state(connection, key)
            storage_rows = self._resources(connection, key)
            stock = storage_rows.get(resource)
            if stock is None:
                raise ValueError("Ресурс отсутствует в хранилище")
            limit = building_level_info(state["level"], building)["storage"]
            free_capacity = max(0, limit - sum(row["storage"] for row in storage_rows.values()))
            backpack_quantity = self._backpack_amount(connection, character_id, item_id)
            amount = min(quantity, backpack_quantity, free_capacity)
            if amount <= 0:
                raise ValueError("Нет ресурса в рюкзаке или хранилище заполнено")
            if not self._take_inventory_items(connection, character_id, item_id, amount):
                raise ValueError("В рюкзаке недостаточно ресурса")
            connection.execute(
                f"UPDATE building_resources SET storage = storage + %s WHERE {_WHERE} AND resource = %s",
                (amount, *key, resource),
            )
            return self._payload(connection, key, character_id, now)

    def withdraw_from_storage(self, character_id, building, resource, quantity, now=None):
        """Move shared building resources into a player's backpack, respecting its capacity."""
        now = _timestamp(now)
        building = str(building)
        resource = str(resource)
        quantity = int(quantity)
        if building not in BUILDINGS or resource not in building_resources(building):
            raise ValueError("Этот ресурс нельзя забрать из выбранного хранилища")
        item_id = STORAGE_ITEM_IDS.get(resource)
        if item_id is None or quantity <= 0:
            raise ValueError("Некорректный ресурс или количество")

        with self._transaction(character_id, building, now) as (connection, key):
            stock = self._resources(connection, key).get(resource)
            if stock is None or int(stock["storage"]) <= 0:
                raise ValueError("На складе нет этого ресурса")
            requested = min(quantity, int(stock["storage"]))
            amount = ItemsDatabase.add_to_inventory_up_to(
                connection, int(character_id), item_id, requested
            )
            if amount <= 0:
                raise ValueError("В рюкзаке нет места для этого ресурса")
            connection.execute(
                f"UPDATE building_resources SET storage = storage - %s WHERE {_WHERE} AND resource = %s",
                (amount, *key, resource),
            )
            return self._payload(connection, key, character_id, now)

    def _upgrade_payload(self, connection, key, character_id, state, now):
        requirements = upgrade_requirements(state["level"], key[2])
        if requirements is None:
            return None
        deposited = self._deposited(connection, key)
        warehouse_key = (key[0], key[1], "warehouse")
        self._ensure(connection, warehouse_key, now)
        warehouse_rows = self._resources(connection, warehouse_key)
        materials = []
        for item_id, required in requirements["materials"].items():
            catalog = connection.execute("SELECT name, icon FROM items_catalog WHERE id = %s", (item_id,)).fetchone()
            materials.append({
                "item_id": item_id,
                "name": catalog["name"] if catalog else f"Предмет {item_id}",
                "icon": catalog["icon"] if catalog else None,
                "required": required,
                "deposited": min(required, deposited.get(item_id, 0)),
                "in_warehouse": int(warehouse_rows.get(
                    STORAGE_RESOURCES_BY_ITEM_ID.get(int(item_id)), {}
                ).get("storage", 0)),
                "remaining": max(0, required - min(required, deposited.get(item_id, 0))),
            })
        finish_at = state["upgrade_finish_at"]
        can_start = all(
            item["deposited"] + item["in_warehouse"] >= item["required"]
            for item in materials
        )
        return {
            "next_level": state["level"] + 1,
            "time_seconds": requirements["time_seconds"],
            "materials": materials,
            "ready": can_start,
            "in_progress": finish_at is not None,
            "finish_at": finish_at,
            "seconds_left": None if finish_at is None else max(0, int(finish_at - now)),
        }

    @staticmethod
    def _slot(connection, key, slot_index):
        slot = connection.execute(
            f"SELECT slot_index, occupied, worker_id, hire_time, credited FROM building_worker_slots WHERE {_WHERE} AND slot_index = %s",
            (*key, int(slot_index)),
        ).fetchone()
        if slot is None:
            raise ValueError("Участок ещё не открыт")
        return slot

    # ---------- действия (любой игрок фракции) ----------

    def get_state(self, character_id, building, now=None):
        now = _timestamp(now)
        with self._transaction(character_id, building, now) as (connection, key):
            state = self._payload(connection, key, character_id, now)
        if building == "stable":
            from server.transport import TransportService

            state["transport_convoys"] = TransportService(self.db).get_world_convoys(
                character_id, now=now,
            )
        return state

    def hire_worker(self, character_id, building, slot_index, worker_id, now=None):
        now = _timestamp(now)
        slot_index = int(slot_index)
        worker_id = "" if worker_id is None else str(worker_id).strip()
        if not worker_id:
            raise ValueError("Не указан worker_id")
        with self._transaction(character_id, building, now) as (connection, key):
            if self._slot(connection, key, slot_index)["occupied"]:
                raise ValueError("Место на участке уже занято")
            connection.execute(
                f"""
                UPDATE building_worker_slots SET occupied = 1, worker_id = %s, hire_time = %s, credited = '{{}}'::jsonb
                WHERE {_WHERE} AND slot_index = %s
                """,
                (worker_id, now, *key, slot_index),
            )
            return self._payload(connection, key, character_id, now)

    def fire_worker(self, character_id, building, slot_index, now=None):
        now = _timestamp(now)
        slot_index = int(slot_index)
        with self._transaction(character_id, building, now) as (connection, key):
            slot = self._slot(connection, key, slot_index)
            if not slot["occupied"]:
                raise ValueError("Место на участке пустое")
            if (slot["worker_id"] or "").startswith("player:"):
                raise ValueError("Игрок должен сам завершить работу")
            self._sync_harvest(connection, key, now)
            connection.execute(
                f"""
                UPDATE building_worker_slots SET occupied = 0, worker_id = NULL, hire_time = NULL, credited = '{{}}'::jsonb
                WHERE {_WHERE} AND slot_index = %s
                """,
                (*key, slot_index),
            )
            return self._payload(connection, key, character_id, now)

    def toggle_player_worker(self, character_id, building, slot_index, now=None):
        now = _timestamp(now)
        slot_index = int(slot_index)
        player_worker_id = f"player:{int(character_id)}"
        with self._transaction(character_id, building, now) as (connection, key):
            assigned = connection.execute(
                """SELECT building, slot_index FROM building_worker_slots
                   WHERE world_id = %s AND faction = %s AND occupied = 1 AND worker_id = %s
                   LIMIT 1""",
                (key[0], key[1], player_worker_id),
            ).fetchone()
            if assigned:
                if assigned["building"] != building or assigned["slot_index"] != slot_index:
                    raise ValueError("Вы уже работаете на другом объекте")
                self._sync_harvest(connection, key, now)
                connection.execute(
                    f"""UPDATE building_worker_slots
                        SET occupied = 0, worker_id = NULL, hire_time = NULL, credited = '{{}}'::jsonb
                        WHERE {_WHERE} AND slot_index = %s""",
                    (*key, slot_index),
                )
                return self._payload(connection, key, character_id, now)

            slot = self._slot(connection, key, slot_index)
            if slot["occupied"] and (slot["worker_id"] or "").startswith("player:"):
                raise ValueError("Это место занято другим игроком")
            info = building_level_info(self._state(connection, key)["level"], building)
            if sum(resource["storage"] for resource in self._resources(connection, key).values()) >= info["storage"]:
                raise ValueError("Склад переполнен, нельзя начать добычу")
            self._sync_harvest(connection, key, now)
            connection.execute(
                f"""UPDATE building_worker_slots
                    SET occupied = 1, worker_id = %s, hire_time = %s, credited = '{{}}'::jsonb
                    WHERE {_WHERE} AND slot_index = %s""",
                (player_worker_id, now, *key, slot_index),
            )
            return self._payload(connection, key, character_id, now)

    def claim_player_harvest(self, character_id, building, resource, quantity, now=None):
        now = _timestamp(now)
        resource = str(resource)
        quantity = int(quantity)
        item_id = PRODUCTION_ITEM_IDS.get(resource)
        if item_id is None or quantity <= 0:
            raise ValueError("Некорректный ресурс или количество")
        with self._transaction(character_id, building, now) as (connection, key):
            if resource not in building_resources(building):
                raise ValueError("Этот ресурс не производится в здании")
            claim = connection.execute(
                f"""SELECT claimable FROM building_player_resources
                    WHERE {_WHERE} AND character_id = %s AND resource = %s FOR UPDATE""",
                (*key, int(character_id), resource),
            ).fetchone()
            if claim is None or claim["claimable"] <= 0:
                raise ValueError("Нет выгруженной личной добычи для забора")
            stock = connection.execute(
                f"SELECT storage FROM building_resources WHERE {_WHERE} AND resource = %s FOR UPDATE",
                (*key, resource),
            ).fetchone()
            if stock is None or stock["storage"] <= 0:
                raise ValueError("Ресурс больше не находится на складе")
            requested = min(quantity, claim["claimable"], stock["storage"])
            added = ItemsDatabase.add_to_inventory_up_to(connection, character_id, item_id, requested)
            if added <= 0:
                raise ValueError("В рюкзаке нет места для этого ресурса")
            connection.execute(
                f"""UPDATE building_resources SET storage = storage - %s
                    WHERE {_WHERE} AND resource = %s""",
                (added, *key, resource),
            )
            connection.execute(
                f"""UPDATE building_player_resources SET claimable = claimable - %s
                    WHERE {_WHERE} AND character_id = %s AND resource = %s""",
                (added, *key, int(character_id), resource),
            )
            return self._payload(connection, key, character_id, now)

    def deposit_material(self, character_id, building, item_id, quantity, now=None, source="warehouse"):
        raise ValueError(
            "Отдельные взносы отключены. Пополните общий склад; ресурсы спишутся при запуске улучшения."
        )

    def start_upgrade(self, character_id, building, now=None):
        """Запускает стройку (любой игрок фракции): сданные материалы расходуются, уровень вырастет по времени."""
        now = _timestamp(now)
        with self._transaction(character_id, building, now) as (connection, key):
            state = self._state(connection, key)
            requirements = upgrade_requirements(state["level"], building)
            if requirements is None:
                raise ValueError("Здание уже максимального уровня")
            if state["upgrade_finish_at"] is not None:
                raise ValueError("Стройка уже идёт")
            deposited = self._deposited(connection, key)
            remaining = {
                item_id: max(0, int(required) - int(deposited.get(item_id, 0)))
                for item_id, required in requirements["materials"].items()
            }
            self._debit_warehouse_items(connection, key, remaining, now)
            connection.execute(f"DELETE FROM building_upgrade_materials WHERE {_WHERE}", key)
            connection.execute(
                f"UPDATE building_states SET upgrade_finish_at = %s WHERE {_WHERE}",
                (now + requirements["time_seconds"], *key),
            )
            return self._payload(connection, key, character_id, now)

    def contribute_stall_upgrade(self, character_id, upgrade_id, resource, quantity,
                                 now=None, source=None):
        raise ValueError(
            "Отдельные взносы отключены. Пополните общий склад и казну, затем купите улучшение."
        )

    def purchase_stall_upgrade(self, character_id, upgrade_id, now=None):
        now = _timestamp(now)
        upgrade_id = str(upgrade_id)
        with self._transaction(character_id, "stable", now) as (connection, key):
            upgrade = building_config("stable")["stall_upgrades"].get(upgrade_id)
            if upgrade is None:
                raise ValueError("Неизвестное улучшение стойла")
            purchased = connection.execute(
                f"SELECT 1 FROM stable_stall_upgrades WHERE {_WHERE} AND upgrade_id = %s",
                (*key, upgrade_id),
            ).fetchone()
            if purchased:
                raise ValueError("Это улучшение стойла уже куплено")
            progress = connection.execute(
                f"""SELECT wood_deposited, silver_deposited FROM stable_stall_upgrade_contributions
                    WHERE {_WHERE} AND upgrade_id = %s FOR UPDATE""",
                (*key, upgrade_id),
            ).fetchone()
            legacy_wood = 0 if progress is None else int(progress["wood_deposited"])
            legacy_silver = 0 if progress is None else int(progress["silver_deposited"])
            wood_due = max(0, int(upgrade["wood_cost"]) - legacy_wood)
            silver_due = max(0, int(upgrade["silver_cost"]) - legacy_silver)
            self._debit_warehouse_items(
                connection, key, {int(upgrade["wood_item_id"]): wood_due}, now,
            )
            self._debit_treasury(
                connection, key, Currency.to_copper(silver=silver_due),
            )
            connection.execute(
                """
                INSERT INTO stable_stall_upgrades
                    (world_id, faction, building, upgrade_id, purchased_by, purchased_at, finish_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (*key, upgrade_id, int(character_id), now, now + upgrade["time_seconds"]),
            )
            return self._payload(connection, key, character_id, now)

    def purchase_horse(self, character_id, slot_index, now=None):
        now = _timestamp(now)
        slot_index = int(slot_index)
        with self._transaction(character_id, "stable", now) as (connection, key):
            state = self._state(connection, key)
            purchased_upgrades = {
                row["upgrade_id"] for row in connection.execute(
                    f"SELECT upgrade_id FROM stable_stall_upgrades WHERE {_WHERE}", key
                ).fetchall()
            }
            upgrade_config = building_config("stable")["stall_upgrades"]
            capacity = building_level_info(state["level"], "stable")["stall_capacity"] + sum(
                upgrade_config[upgrade_id]["horse_capacity"] for upgrade_id in purchased_upgrades
            )
            if slot_index < 0 or slot_index >= capacity:
                raise ValueError("Стойло ещё не открыто")
            if connection.execute(
                f"SELECT 1 FROM stable_horses WHERE {_WHERE} AND slot_index = %s",
                (*key, slot_index),
            ).fetchone():
                raise ValueError("Это стойло уже занято")

            horse_count = connection.execute(
                f"SELECT COUNT(*) AS count FROM stable_horses WHERE {_WHERE}", key
            ).fetchone()["count"]
            price = horse_purchase_price_silver(horse_count)
            self._debit_treasury(connection, key, Currency.to_copper(silver=price))
            connection.execute(
                """
                INSERT INTO stable_horses
                    (world_id, faction, building, slot_index, name, breed,
                     status, purchase_price_silver, purchased_by, purchased_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (*key, slot_index, f"Лошадь {horse_count + 1}", "Рабочая", "Отдыхает",
                 price, int(character_id), now),
            )
            return self._payload(connection, key, character_id, now)
