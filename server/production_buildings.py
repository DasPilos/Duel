"""Производственные и городские здания на сервере: общие для всех игроков фракции в мире.

Всё состояние и все расчёты (производство, выгрузка, стадии, улучшение) — здесь; клиент только отображает ответ.
Личное у игрока только инвентарь: материалы улучшения берутся из рюкзака того, кто их сдаёт.
"""

import json
import math
import random
import time
from contextlib import contextmanager

from core.currency import Currency
from core.production_buildings import (
    CYCLE_DURATION_SEC,
    RESOURCES,
    building_config,
    building_level_info,
    building_resources,
    horse_purchase_price_silver,
    PRODUCTION_ITEM_IDS,
    plot_stage,
    slot_resources,
    upgrade_requirements,
)
from server.database import lock_character
from server.items_database import ItemsDatabase

# Пока в игре одна фракция; когда появится выбор фракции, её нужно хранить у персонажа
DEFAULT_FACTION = "light"


def _timestamp(now):
    return time.time() if now is None else float(now)


def _completed_units(hire_time, now, timer_sec):
    if hire_time is None:
        return 0
    return max(0, math.floor((float(now) - float(hire_time)) / timer_sec))


def _new_units(building, slot, now):
    """Единицы, готовые с прошлого учёта, и новые счётчики credited (горожанин может давать несколько ресурсов)."""
    credited = dict(slot["credited"] or {})
    added = {}
    for resource in slot_resources(building, slot["slot_index"]):
        total = _completed_units(slot["hire_time"], now, RESOURCES[resource]["timer_sec"])
        fresh = total - credited.get(resource, 0)
        if fresh > 0:
            added[resource] = fresh
            credited[resource] = total
    return added, credited


def distribute_to_storage(storage, buffers, limit):
    """Сколько каждого ресурса попадёт на склад: при нехватке места — пропорционально буферам."""
    free = max(0, limit - sum(storage.values()))
    total = sum(buffers.values())
    if total <= free:
        return dict(buffers)
    accepted = {resource: buffers[resource] * free // total for resource in buffers}
    leftover = free - sum(accepted.values())
    for resource in buffers:
        if leftover <= 0:
            break
        if accepted[resource] < buffers[resource]:
            accepted[resource] += 1
            leftover -= 1
    return accepted


# Условие для ключа здания: (world_id, faction, building)
_WHERE = "world_id = %s AND faction = %s AND building = %s"


class ProductionBuildings:
    """Общие здания фракции. Методы принимают персонажа, от имени которого действует игрок."""

    def __init__(self, database, rng=None):
        self.db = database
        self.rng = rng or random.Random()

    def _cycle_bonus(self, building, level):
        """Случайная добыча за цикл отгрузки: один бросок на всё здание, вид — по весам уровня; None, если не выпало."""
        bonus = building_config(building).get("bonus")
        chance = bonus["cycle_chance"].get(int(level), 0) if bonus else 0
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
            """
            INSERT INTO building_states (world_id, faction, building, level, cycle_start_time)
            VALUES (%s, %s, %s, 1, %s)
            ON CONFLICT (world_id, faction, building) DO NOTHING
            """,
            (*key, now),
        )
        for resource in building_resources(building):
            connection.execute(
                """
                INSERT INTO building_resources (world_id, faction, building, resource)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (world_id, faction, building, resource) DO NOTHING
                """,
                (*key, resource),
            )
        level = self._state(connection, key)["level"]
        for slot_index in range(building_level_info(level, building)["max_workers"]):
            connection.execute(
                """
                INSERT INTO building_worker_slots (world_id, faction, building, slot_index)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (world_id, faction, building, slot_index) DO NOTHING
                """,
                (*key, slot_index),
            )

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
            f"""
            SELECT slot_index, occupied, worker_id, hire_time, credited FROM building_worker_slots
            WHERE {_WHERE} ORDER BY slot_index
            """,
            key,
        ).fetchall()

    @staticmethod
    def _add_to_buffers(connection, key, amounts):
        for resource, amount in amounts.items():
            if amount:
                connection.execute(
                    f"UPDATE building_resources SET buffer = buffer + %s WHERE {_WHERE} AND resource = %s",
                    (amount, *key, resource),
                )

    def _advance(self, connection, key, now):
        """Доводит состояние до now; циклы до окончания стройки считаются по старому уровню."""
        finish_at = self._state(connection, key)["upgrade_finish_at"]
        if finish_at is not None and finish_at <= now:
            self._process_due_cycles(connection, key, finish_at)
            connection.execute(
                f"UPDATE building_states SET level = level + 1, upgrade_finish_at = NULL WHERE {_WHERE}", key
            )
            self._ensure(connection, key, finish_at)
        self._process_due_cycles(connection, key, now)

    def _sync_buffer(self, connection, key, now):
        """Переносит готовые единицы работающих горожан в буфер и запоминает, сколько уже учтено."""
        building = key[2]
        added = {}
        for slot in self._slots(connection, key):
            if not slot["occupied"]:
                continue
            fresh, credited = _new_units(building, slot, now)
            if not fresh:
                continue
            for resource, amount in fresh.items():
                added[resource] = added.get(resource, 0) + amount
                worker_id = slot["worker_id"] or ""
                if worker_id.startswith("player:"):
                    character_id = int(worker_id.split(":", 1)[1])
                    connection.execute(
                        """
                        INSERT INTO building_player_resources
                            (world_id, faction, building, character_id, resource, buffered, total_produced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (world_id, faction, building, character_id, resource)
                        DO UPDATE SET buffered = building_player_resources.buffered + EXCLUDED.buffered,
                                      total_produced = building_player_resources.total_produced + EXCLUDED.total_produced
                        """,
                        (*key, character_id, resource, amount, amount),
                    )
            connection.execute(
                f"UPDATE building_worker_slots SET credited = %s::jsonb WHERE {_WHERE} AND slot_index = %s",
                (json.dumps(credited), *key, slot["slot_index"]),
            )
        self._add_to_buffers(connection, key, added)

    def _unload(self, connection, key, now):
        building = key[2]
        self._sync_buffer(connection, key, now)
        rows = self._resources(connection, key)
        storage = {resource: row["storage"] for resource, row in rows.items()}
        buffers = {resource: row["buffer"] for resource, row in rows.items()}
        level = self._state(connection, key)["level"]
        limit = building_level_info(level, building)["storage"]
        # Излишек сверх общего лимита склада сгорает
        accepted = distribute_to_storage(storage, buffers, limit)
        # Один бросок на цикл: нужен хотя бы один работавший горожанин и место на складе
        worked = sum(buffers.values()) > 0 or any(slot["occupied"] for slot in self._slots(connection, key))
        if worked and sum(storage.values()) + sum(accepted.values()) < limit:
            found = self._cycle_bonus(building, level)
            if found:
                accepted[found] += 1
        for resource in rows:
            player_rows = connection.execute(
                f"""SELECT character_id, buffered FROM building_player_resources
                    WHERE {_WHERE} AND resource = %s AND buffered > 0 ORDER BY character_id""",
                (*key, resource),
            ).fetchall()
            player_total = sum(row["buffered"] for row in player_rows)
            buffer_total = buffers[resource]
            player_accepted = (player_total if accepted[resource] >= buffer_total else
                               player_total * accepted[resource] // buffer_total if buffer_total else 0)
            remaining_player_accepted = player_accepted
            for index, player_row in enumerate(player_rows):
                if index == len(player_rows) - 1:
                    amount = min(player_row["buffered"], remaining_player_accepted)
                else:
                    amount = min(
                        player_row["buffered"],
                        player_accepted * player_row["buffered"] // max(1, player_total),
                    )
                if amount > 0:
                    connection.execute(
                        """
                        UPDATE building_player_resources
                        SET claimable = claimable + %s
                        WHERE world_id = %s AND faction = %s AND building = %s
                          AND character_id = %s AND resource = %s
                        """,
                        (amount, *key, player_row["character_id"], resource),
                    )
                    remaining_player_accepted -= amount
            connection.execute(
                f"""UPDATE building_player_resources SET buffered = 0
                    WHERE {_WHERE} AND resource = %s""",
                (*key, resource),
            )
            connection.execute(
                f"UPDATE building_resources SET storage = storage + %s, buffer = 0 WHERE {_WHERE} AND resource = %s",
                (accepted[resource], *key, resource),
            )
        connection.execute(f"UPDATE building_states SET cycle_start_time = %s WHERE {_WHERE}", (now, *key))

    def _process_due_cycles(self, connection, key, now):
        """Выгружает каждый завершённый цикл на его точной границе — как выгрузка по расписанию."""
        boundary = float(self._state(connection, key)["cycle_start_time"]) + CYCLE_DURATION_SEC
        while boundary <= now:
            self._unload(connection, key, boundary)
            boundary += CYCLE_DURATION_SEC

    def _payload(self, connection, key, character_id, now):
        building = key[2]
        self._sync_buffer(connection, key, now)
        state = self._state(connection, key)
        rows = self._resources(connection, key)
        info = building_level_info(state["level"], building)
        time_left = max(0, CYCLE_DURATION_SEC - (now - state["cycle_start_time"]))
        forecast = {resource: row["buffer"] for resource, row in rows.items()}
        slots = []
        for slot in self._slots(connection, key):
            resources = slot_resources(building, slot["slot_index"])
            timer_sec = RESOURCES[resources[0]]["timer_sec"]
            resource_progress = {
                resource: (0 if not slot["occupied"] else
                           int((now - slot["hire_time"]) % RESOURCES[resource]["timer_sec"]))
                for resource in resources
            }
            if slot["occupied"]:
                for resource in resources:
                    forecast[resource] += math.floor(time_left / RESOURCES[resource]["timer_sec"])
            worker_name = slot["worker_id"]
            if worker_name and worker_name.startswith("player:"):
                worker_row = connection.execute(
                    "SELECT name FROM characters WHERE id = %s",
                    (int(worker_name.split(":", 1)[1]),),
                ).fetchone()
                worker_name = worker_row["name"] if worker_row else "Игрок"
            elif worker_name and worker_name.startswith("citizen-"):
                worker_name = f"Горожанин {worker_name.split('-', 1)[1]}"
            slots.append({
                "slot_index": slot["slot_index"],
                "resource": resources[0],
                "resources": list(resources),
                "occupied": bool(slot["occupied"]),
                "worker_id": slot["worker_id"],
                "worker_name": worker_name,
                "is_player": bool(slot["worker_id"] and slot["worker_id"].startswith("player:")),
                "player_id": (int(slot["worker_id"].split(":", 1)[1])
                              if slot["worker_id"] and slot["worker_id"].startswith("player:") else None),
                "hire_time": slot["hire_time"],
                "progress_sec": 0 if not slot["occupied"] else int((now - slot["hire_time"]) % timer_sec),
                "resource_progress_sec": resource_progress,
            })
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
            work_timer = RESOURCES[work_resource]["timer_sec"]
            work_progress = int((now - player_work_slot["hire_time"]) % work_timer)
            player_work = {
                "slot_index": player_work_slot["slot_index"],
                "resource": work_resource,
                "resources": list(work_resources),
                "timer_sec": work_timer,
                "progress_sec": work_progress,
                "seconds_to_next": work_timer - work_progress,
                "total_produced": {resource: player_harvest_totals.get(resource, 0)
                                   for resource in work_resources},
            }
        storage = {resource: row["storage"] for resource, row in rows.items()}
        stall_slots = None
        occupied_stalls = 0
        feed_consumption = 0
        stall_upgrades = None
        if building == "stable":
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
                    "wood_in_backpack": self._backpack_amount(
                        connection, character_id, upgrade["wood_item_id"]
                    ),
                    "silver_available": silver_available,
                    "purchased": upgrade_id in purchased_upgrades,
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
                    "ready": (
                        contributions.get(upgrade_id, {}).get("wood_deposited", 0) >= upgrade["wood_cost"]
                        and contributions.get(upgrade_id, {}).get("silver_deposited", 0) >= upgrade["silver_cost"]
                    ),
                }
                for upgrade_id, upgrade in upgrade_config.items()
            }
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
            "silver_available": silver_available if building == "stable" else None,
            "horse_price_next_silver": (
                horse_purchase_price_silver(occupied_stalls) if building == "stable" else None
            ),
            "occupied_stalls": occupied_stalls,
            "feed_resource": building_config(building).get("feed_resource"),
            "feed_resource_label": RESOURCES.get(building_config(building).get("feed_resource"), {}).get("label"),
            "feed_consumption_kg_per_hour": feed_consumption,
            "workers": sum(1 for slot in slots if slot["occupied"]),
            "cycle_start_time": state["cycle_start_time"],
            "cycle_duration_sec": CYCLE_DURATION_SEC,
            "cycle_seconds_left": int(time_left),
            "stage": plot_stage(state["cycle_start_time"], now),
            "storage": {**storage, "limit": info["storage"]},
            "storage_total": sum(storage.values()),
            "buffer": {resource: row["buffer"] for resource, row in rows.items()},
            "forecast": forecast,
            "worker_slots": slots,
            "player_work": player_work,
            "player_harvest_claims": player_harvest_claims,
            "player_harvest_totals": player_harvest_totals,
            "resource_timer_sec": {
                resource: RESOURCES[resource]["timer_sec"] for resource in rows if "timer_sec" in RESOURCES[resource]
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

    def _upgrade_payload(self, connection, key, character_id, state, now):
        requirements = upgrade_requirements(state["level"], key[2])
        if requirements is None:
            return None
        deposited = self._deposited(connection, key)
        materials = []
        for item_id, required in requirements["materials"].items():
            catalog = connection.execute("SELECT name, icon FROM items_catalog WHERE id = %s", (item_id,)).fetchone()
            materials.append({
                "item_id": item_id,
                "name": catalog["name"] if catalog else f"Предмет {item_id}",
                "icon": catalog["icon"] if catalog else None,
                "required": required,
                "deposited": min(required, deposited.get(item_id, 0)),
                # Рюкзак — личный: показываем, сколько есть у того, кто смотрит окно
                "in_backpack": self._backpack_amount(connection, character_id, item_id),
            })
        finish_at = state["upgrade_finish_at"]
        return {
            "next_level": state["level"] + 1,
            "time_seconds": requirements["time_seconds"],
            "materials": materials,
            "ready": all(item["deposited"] >= item["required"] for item in materials),
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
            return self._payload(connection, key, character_id, now)

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
            # Целые единицы — в буфер, незавершённый остаток сгорает
            fresh, _credited = _new_units(building, slot, now)
            self._add_to_buffers(connection, key, fresh)
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
                self._sync_buffer(connection, key, now)
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
            self._sync_buffer(connection, key, now)
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

    def deposit_material(self, character_id, building, item_id, quantity, now=None):
        """Игрок сдаёт материал из своего рюкзака в общий склад улучшения здания (не больше недостающего)."""
        now = _timestamp(now)
        item_id, quantity = int(item_id), int(quantity)
        if quantity <= 0:
            raise ValueError("Некорректное количество")
        with self._transaction(character_id, building, now) as (connection, key):
            state = self._state(connection, key)
            requirements = upgrade_requirements(state["level"], building)
            if requirements is None:
                raise ValueError("Здание уже максимального уровня")
            if state["upgrade_finish_at"] is not None:
                raise ValueError("Идёт стройка — дождитесь окончания")
            if item_id not in requirements["materials"]:
                raise ValueError("Этот материал не нужен для улучшения")
            missing = requirements["materials"][item_id] - self._deposited(connection, key).get(item_id, 0)
            amount = min(quantity, missing, self._backpack_amount(connection, character_id, item_id))
            if amount <= 0:
                raise ValueError("Нечего сдать: материала нет в рюкзаке или уже сдано достаточно")
            rows = connection.execute(
                """SELECT id, quantity FROM character_items
                   WHERE character_id = %s AND item_id = %s ORDER BY slot_index DESC""",
                (int(character_id), item_id),
            ).fetchall()
            remaining = amount
            for row in rows:
                if remaining <= 0:
                    break
                taken = min(row["quantity"], remaining)
                ItemsDatabase._take_from_row(connection, row, taken)
                remaining -= taken
            connection.execute(
                """
                INSERT INTO building_upgrade_materials (world_id, faction, building, item_id, quantity)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (world_id, faction, building, item_id)
                DO UPDATE SET quantity = building_upgrade_materials.quantity + EXCLUDED.quantity
                """,
                (*key, item_id, amount),
            )
            return self._payload(connection, key, character_id, now)

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
            if any(deposited.get(item_id, 0) < required for item_id, required in requirements["materials"].items()):
                raise ValueError("Сданы не все материалы")
            connection.execute(f"DELETE FROM building_upgrade_materials WHERE {_WHERE}", key)
            connection.execute(
                f"UPDATE building_states SET upgrade_finish_at = %s WHERE {_WHERE}",
                (now + requirements["time_seconds"], *key),
            )
            return self._payload(connection, key, character_id, now)

    def contribute_stall_upgrade(self, character_id, upgrade_id, resource, quantity, now=None):
        now = _timestamp(now)
        upgrade_id = str(upgrade_id)
        resource = str(resource)
        quantity = int(quantity)
        if resource not in ("wood", "silver") or quantity <= 0:
            raise ValueError("Некорректный взнос в улучшение стойла")
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

            connection.execute(
                """
                INSERT INTO stable_stall_upgrade_contributions (world_id, faction, building, upgrade_id)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                (*key, upgrade_id),
            )
            progress = connection.execute(
                f"""SELECT * FROM stable_stall_upgrade_contributions
                    WHERE {_WHERE} AND upgrade_id = %s FOR UPDATE""",
                (*key, upgrade_id),
            ).fetchone()
            if resource == "wood":
                missing = upgrade["wood_cost"] - progress["wood_deposited"]
                available = self._backpack_amount(connection, character_id, upgrade["wood_item_id"])
                amount = min(quantity, missing, available)
                if amount <= 0:
                    raise ValueError("В рюкзаке нет древесины или взнос уже заполнен")
                rows = connection.execute(
                    """SELECT id, quantity FROM character_items
                       WHERE character_id = %s AND item_id = %s ORDER BY slot_index DESC""",
                    (int(character_id), upgrade["wood_item_id"]),
                ).fetchall()
                remaining = amount
                for row in rows:
                    if remaining <= 0:
                        break
                    taken = min(row["quantity"], remaining)
                    ItemsDatabase._take_from_row(connection, row, taken)
                    remaining -= taken
                connection.execute(
                    f"""UPDATE stable_stall_upgrade_contributions
                        SET wood_deposited = wood_deposited + %s WHERE {_WHERE} AND upgrade_id = %s""",
                    (amount, *key, upgrade_id),
                )
            else:
                missing = upgrade["silver_cost"] - progress["silver_deposited"]
                character = connection.execute(
                    "SELECT copper, silver, gold FROM characters WHERE id = %s FOR UPDATE",
                    (int(character_id),),
                ).fetchone()
                currency = Currency(**character)
                available = currency.total_silver
                amount = min(quantity, missing, available)
                cost_copper = Currency.to_copper(silver=amount)
                if amount <= 0 or not currency.subtract_copper_amount(cost_copper):
                    raise ValueError("Недостаточно серебра для взноса")
                connection.execute(
                    """UPDATE characters SET copper = %s, silver = %s, gold = %s, updated_at = %s
                       WHERE id = %s""",
                    (currency.copper, currency.silver, currency.gold, now, int(character_id)),
                )
                connection.execute(
                    f"""UPDATE stable_stall_upgrade_contributions
                        SET silver_deposited = silver_deposited + %s WHERE {_WHERE} AND upgrade_id = %s""",
                    (amount, *key, upgrade_id),
                )
            return self._payload(connection, key, character_id, now)

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
            if (progress is None or progress["wood_deposited"] < upgrade["wood_cost"]
                    or progress["silver_deposited"] < upgrade["silver_cost"]):
                raise ValueError("Сначала внесите все материалы и серебро")
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
            character = connection.execute(
                "SELECT copper, silver, gold FROM characters WHERE id = %s FOR UPDATE",
                (int(character_id),),
            ).fetchone()
            currency = Currency(**character)
            if not currency.subtract_copper_amount(Currency.to_copper(silver=price)):
                raise ValueError(f"Для покупки нужно {price} серебра")
            connection.execute(
                """UPDATE characters SET copper = %s, silver = %s, gold = %s, updated_at = %s
                   WHERE id = %s""",
                (currency.copper, currency.silver, currency.gold, now, int(character_id)),
            )
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
