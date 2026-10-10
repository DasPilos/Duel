"""Hourly, server-owned city growth through resource supply."""

import json
import math

from core.city_progression import (
    city_population_capacity,
    city_storage_resources,
    city_upgrade_resources,
)
from core.production_buildings import building_level_info, building_resources

UPGRADE_TICK_SECONDS = 15 * 60
UPGRADE_TICK_COUNT = 4
UPGRADE_CYCLE_SECONDS = UPGRADE_TICK_SECONDS * UPGRADE_TICK_COUNT
UPGRADE_START_GRACE_SECONDS = 15
LEGACY_SURPLUS_PERCENT = 71


def city_upgrade_drain_per_tick(population, population_capacity):
    return max(0, int(population)) * max(0, int(population_capacity))


def city_upgrade_cycle_cost(population, population_capacity):
    return city_upgrade_drain_per_tick(population, population_capacity) * UPGRADE_TICK_COUNT


def _population_state(connection, key, city_level):
    row = connection.execute(
        """SELECT state.population_capacity_bonus,
                  COUNT(citizen.id) AS amount
           FROM city_population_state state
           LEFT JOIN city_citizens citizen
             ON citizen.world_id=state.world_id AND citizen.faction=state.faction
            AND citizen.alive=TRUE
           WHERE state.world_id=%s AND state.faction=%s
           GROUP BY state.population_capacity_bonus""",
        key,
    ).fetchone()
    population = 0 if row is None else int(row["amount"])
    capacity_bonus = 0 if row is None else int(row["population_capacity_bonus"])
    capacity = city_population_capacity(city_level, capacity_bonus)
    return population, capacity


def _json_object(value):
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _city_storage(connection, key, city_level):
    required_resources = set(city_upgrade_resources(city_level))
    levels = {
        row["building"]: int(row["level"])
        for row in connection.execute(
            """SELECT building, level FROM building_states
               WHERE world_id=%s AND faction=%s AND building IN ('barn','warehouse')""",
            key,
        ).fetchall()
    }
    stocks = {
        (row["building"], row["resource"]): int(row["storage"])
        for row in connection.execute(
            """SELECT building, resource, storage FROM building_resources
               WHERE world_id=%s AND faction=%s AND building IN ('barn','warehouse')""",
            key,
        ).fetchall()
    }
    result = {}
    for building in ("barn", "warehouse"):
        level = levels.get(building, 1)
        capacity = int(building_level_info(level, building)["storage"])
        for resource in city_storage_resources(building, city_level, building_resources(building)):
            if resource not in required_resources:
                continue
            result[resource] = {
                "building": building,
                "stock": stocks.get((building, resource), 0),
                "capacity": capacity,
            }
    return result


def _write_upgrade_state(connection, key, last_hour, cycle, last_result):
    connection.execute(
        """UPDATE city_population_state
           SET city_upgrade_last_hour=%s, city_upgrade_cycle=%s::jsonb,
               city_upgrade_last_result=%s::jsonb
           WHERE world_id=%s AND faction=%s""",
        (float(last_hour), json.dumps(cycle, ensure_ascii=False),
         json.dumps(last_result, ensure_ascii=False), *key),
    )


def _finish_city_upgrade(connection, key, city_level, cycle, finished_at):
    resources = _city_storage(connection, key, city_level)
    if cycle.get("drain_formula") == "population_capacity":
        unpaid_resources = [
            {
                "resource": resource,
                "required": int(item.get("required", 0)),
                "charged": int(item.get("charged", 0)),
                "shortfall": max(0, int(item.get("required", 0)) - int(item.get("charged", 0))),
            }
            for resource, item in cycle["resources"].items()
            if int(item.get("charged", 0)) < int(item.get("required", 0))
        ]
        completion_failed = bool(unpaid_resources)
    else:
        below_threshold = [
            {
                "resource": resource,
                "storage": item["stock"],
                "capacity": item["capacity"],
                "required": math.ceil(item["capacity"] * LEGACY_SURPLUS_PERCENT / 100),
            }
            for resource, item in resources.items()
            if item["stock"] < math.ceil(item["capacity"] * LEGACY_SURPLUS_PERCENT / 100)
        ]
        unpaid_resources = []
        completion_failed = bool(below_threshold)
    if not completion_failed and resources:
        next_level = city_level + 1
        connection.execute(
            """UPDATE city_population_state SET castle_level=%s
               WHERE world_id=%s AND faction=%s""",
            (next_level, *key),
        )
        return {
            "status": "completed",
            "from_level": city_level,
            "to_level": next_level,
            "finished_at": float(finished_at),
            "resources": list(cycle["resources"]),
        }
    result = {
        "status": "failed",
        "level": city_level,
        "finished_at": float(finished_at),
    }
    if cycle.get("drain_formula") == "population_capacity":
        result["unpaid_resources"] = unpaid_resources
    else:
        result["below_threshold"] = below_threshold
    return result


def process_city_upgrade(connection, key, now):
    """Advance due quarter-hour deductions and start only on an exact hour boundary."""
    state = connection.execute(
        """SELECT castle_level, population_capacity_bonus,
              city_upgrade_last_hour, city_upgrade_cycle,
                  city_upgrade_last_result
           FROM city_population_state WHERE world_id=%s AND faction=%s FOR UPDATE""",
        key,
    ).fetchone()
    if state is None:
        return None

    city_level = int(state["castle_level"])
    last_hour = float(state["city_upgrade_last_hour"])
    cycle = _json_object(state["city_upgrade_cycle"])
    last_result = _json_object(state["city_upgrade_last_result"])
    now = float(now)

    if cycle.get("active"):
        started_at = float(cycle["started_at"])
        tick_index = int(cycle.get("tick_index", 0))
        while tick_index < UPGRADE_TICK_COUNT:
            tick_at = started_at + (tick_index + 1) * UPGRADE_TICK_SECONDS
            if now + 1e-6 < tick_at:
                break
            if cycle.get("drain_formula") == "population_capacity":
                population, population_capacity = _population_state(connection, key, city_level)
                per_tick = city_upgrade_drain_per_tick(population, population_capacity)
                cycle["population"] = population
                cycle["population_capacity"] = population_capacity
            else:
                per_tick = None
            for resource, item in cycle["resources"].items():
                tick_cost = per_tick if per_tick is not None else int(item["per_tick"])
                if per_tick is not None:
                    item["per_tick"] = tick_cost
                    item["required"] = int(item.get("required", 0)) + tick_cost
                    item.setdefault("tick_costs", []).append(tick_cost)
                building = item["building"]
                stock_row = connection.execute(
                    """SELECT storage FROM building_resources
                       WHERE world_id=%s AND faction=%s AND building=%s AND resource=%s
                       FOR UPDATE""",
                    (*key, building, resource),
                ).fetchone()
                stock = 0 if stock_row is None else int(stock_row["storage"])
                charged = min(stock, tick_cost)
                if charged:
                    connection.execute(
                        """UPDATE building_resources SET storage=storage-%s
                           WHERE world_id=%s AND faction=%s AND building=%s AND resource=%s""",
                        (charged, *key, building, resource),
                    )
                item["charged"] = int(item.get("charged", 0)) + charged
            tick_index += 1
            cycle["tick_index"] = tick_index

        finished_at = started_at + UPGRADE_CYCLE_SECONDS
        if now + 1e-6 >= finished_at and tick_index == UPGRADE_TICK_COUNT:
            last_result = _finish_city_upgrade(connection, key, city_level, cycle, finished_at)
            next_hour = float(finished_at)
            _write_upgrade_state(connection, key, next_hour, {}, last_result)
            return last_result

        _write_upgrade_state(connection, key, last_hour, cycle, last_result)
        return last_result

    hour = math.floor(now / 3600) * 3600
    if hour <= last_hour:
        return last_result
    if now - hour > UPGRADE_START_GRACE_SECONDS:
        _write_upgrade_state(connection, key, hour, {}, last_result)
        return last_result

    resources = _city_storage(connection, key, city_level)
    population, population_capacity = _population_state(connection, key, city_level)
    per_tick = city_upgrade_drain_per_tick(population, population_capacity)
    cycle_cost = city_upgrade_cycle_cost(population, population_capacity)
    funded = {
        resource: item for resource, item in resources.items()
        if item["stock"] >= cycle_cost
    }
    if not resources or len(funded) != len(resources):
        _write_upgrade_state(connection, key, hour, {}, last_result)
        return last_result

    cycle = {
        "active": True,
        "drain_formula": "population_capacity",
        "started_at": float(hour),
        "finish_at": float(hour + UPGRADE_CYCLE_SECONDS),
        "tick_index": 0,
        "population": population,
        "population_capacity": population_capacity,
        "resources": {
            resource: {
                "building": item["building"],
                "snapshot": item["stock"],
                "capacity": item["capacity"],
                "per_tick": per_tick,
                "required": 0,
                "charged": 0,
                "tick_costs": [],
            }
            for resource, item in funded.items()
        },
    }
    _write_upgrade_state(connection, key, hour, cycle, last_result)
    return last_result


def city_upgrade_payload(connection, key, now):
    row = connection.execute(
        """SELECT castle_level, population_capacity_bonus,
              city_upgrade_last_hour, city_upgrade_cycle,
              city_upgrade_last_result
           FROM city_population_state WHERE world_id=%s AND faction=%s""",
        key,
    ).fetchone()
    if row is None:
        return {
            "city_level": 1, "population": 4, "active": False,
            "charging_resources": [], "last_result": {},
        }

    population_row = connection.execute(
        """SELECT COUNT(*) AS amount FROM city_citizens
           WHERE world_id=%s AND faction=%s AND alive=TRUE""",
        key,
    ).fetchone()
    population = 0 if population_row is None else int(population_row["amount"])

    cycle = _json_object(row["city_upgrade_cycle"])
    active = bool(cycle.get("active"))
    started_at = float(cycle.get("started_at", 0)) if active else None
    finish_at = float(cycle.get("finish_at", 0)) if active else None
    tick_index = int(cycle.get("tick_index", 0)) if active else 0
    elapsed = max(0.0, float(now) - started_at) if active else 0.0
    phase_index = min(3, int(elapsed // UPGRADE_TICK_SECONDS)) if active else 0
    next_tick_at = (
        started_at + (tick_index + 1) * UPGRADE_TICK_SECONDS
        if active and tick_index < UPGRADE_TICK_COUNT else finish_at
    )
    last_hour = float(row["city_upgrade_last_hour"])
    next_start_at = max(0.0, last_hour + 3600)
    return {
        "city_level": int(row["castle_level"]),
        "population": population,
        "population_capacity": city_population_capacity(
            row["castle_level"], row["population_capacity_bonus"],
        ),
        "active": active,
        "started_at": started_at,
        "finish_at": finish_at,
        "seconds_left": max(0, math.ceil(finish_at - float(now))) if active else 0,
        "tick_index": tick_index,
        "tick_count": UPGRADE_TICK_COUNT,
        "phase_index": phase_index,
        "drain_formula": cycle.get("drain_formula") if active else None,
        "resource_drain_per_hour": {
            resource: (
                city_upgrade_drain_per_tick(
                    population,
                    int(cycle.get("population_capacity", city_population_capacity(
                        row["castle_level"], row["population_capacity_bonus"],
                    ))),
                ) * UPGRADE_TICK_COUNT
                if cycle.get("drain_formula") == "population_capacity"
                else int(item.get("per_tick", 0)) * UPGRADE_TICK_COUNT
            )
            for resource, item in cycle.get("resources", {}).items()
        } if active else {},
        "resource_cost_per_tick": {
            resource: (
                city_upgrade_drain_per_tick(
                    population,
                    int(cycle.get("population_capacity", city_population_capacity(
                        row["castle_level"], row["population_capacity_bonus"],
                    ))),
                )
                if cycle.get("drain_formula") == "population_capacity"
                else int(item.get("per_tick", 0))
            )
            for resource, item in cycle.get("resources", {}).items()
        } if active else {},
        "next_tick_at": next_tick_at,
        "seconds_to_next_tick": max(0, math.ceil(next_tick_at - float(now))) if active else 0,
        "charging_resources": list(cycle.get("resources", {})) if active else [],
        "last_result": _json_object(row["city_upgrade_last_result"]),
        "next_start_at": next_start_at,
    }