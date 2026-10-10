"""Server-authoritative stable dispatch and shared world convoy snapshots."""

import json
import math
import time

from core.cart_progress import CART_GRADES, cart_load_speed_ratio, cart_stats
from core.city_progression import city_storage_resources, unlocked_country_buildings
from core.currency import Currency
from core.production_buildings import building_level_info, building_resources
from server.city_population import DEFAULT_FACTION
from server.database import SYSTEM_USER_ID, lock_character
from server.production_buildings import ProductionBuildings, STORAGE_ITEM_IDS
from server.world_roads import PRODUCTION_BUILDING_IDS, roads_payload, route_position

ACTIVE_STATUSES = ("outbound", "blocked")
PROVISION_SECONDS = 5
RESOURCE_RETRY_SECONDS = 60


def _production_building(road_building_id):
    return PRODUCTION_BUILDING_IDS.get(str(road_building_id), str(road_building_id))


def _json_list(value):
    if isinstance(value, str):
        value = json.loads(value)
    return list(value or [])


class TransportService:
    def __init__(self, database):
        self.db = database
        self.production = ProductionBuildings(database)
        roads = roads_payload(city_level=4)["routes"]
        self.routes = {route["building_id"]: route for route in roads}

    def _world_id(self, connection, character_id):
        row = connection.execute(
            "SELECT world_id FROM characters WHERE id = %s AND world_id = %s",
            (int(character_id), int(self.db.world_id)),
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден в этом мире")
        return int(row["world_id"])

    def _ensure_building(self, connection, key, now):
        self.production._ensure(connection, key, now)
        connection.execute(
            """SELECT 1 FROM building_states
               WHERE world_id = %s AND faction = %s AND building = %s FOR UPDATE""",
            key,
        )
        self.production._advance(connection, key, now)

    @staticmethod
    def _where():
        return "world_id = %s AND faction = %s AND building = %s"

    def _load_cargo(self, connection, world_id, destination_id, resource_ids,
                    capacity_kg, exclude_convoy_id, now):
        building = _production_building(destination_id)
        destination_key = (int(world_id), DEFAULT_FACTION, building)
        warehouse_key = (int(world_id), DEFAULT_FACTION, "warehouse")
        barn_key = (int(world_id), DEFAULT_FACTION, "barn")
        city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
        available_city_resources = set(city_storage_resources(
            "barn", city_level, building_resources("barn")
        )) | set(city_storage_resources(
            "warehouse", city_level, building_resources("warehouse")
        ))
        if any(resource_id not in available_city_resources for resource_id in resource_ids):
            return [], 0.0, {}
        self._ensure_building(connection, warehouse_key, now)
        self._ensure_building(connection, destination_key, now)
        barn_resources = set(building_resources("barn"))
        source_buildings = {
            resource_id: ("barn" if resource_id in barn_resources else "warehouse")
            for resource_id in resource_ids
        }
        if "barn" in source_buildings.values():
            self._ensure_building(connection, barn_key, now)

        destination_state = self.production._state(connection, destination_key)
        destination_capacity = int(building_level_info(
            int(destination_state["level"]), building,
        )["storage"])
        destination_resources = self.production._resources(connection, destination_key)
        reserved_rows = connection.execute(
            """SELECT cargo_json FROM transport_convoys
               WHERE world_id=%s AND faction=%s AND destination_building_id=%s
                 AND status IN ('outbound','blocked') AND id<>%s""",
            (world_id, DEFAULT_FACTION, destination_id, int(exclude_convoy_id)),
        ).fetchall()
        reserved = sum(
            int(slot.get("quantity", 0))
            for row in reserved_rows for slot in _json_list(row["cargo_json"])
        )
        reserved_by_resource = {}
        for row in reserved_rows:
            for slot in _json_list(row["cargo_json"]):
                resource_id = str(slot.get("resource_id", ""))
                reserved_by_resource[resource_id] = (
                    reserved_by_resource.get(resource_id, 0) + int(slot.get("quantity", 0))
                )
        destination_free = {
            resource_id: max(
                0, destination_capacity
                - int(destination_resources.get(resource_id, {}).get("storage", 0))
                - reserved_by_resource.get(resource_id, 0),
            )
            for resource_id in set(resource_ids)
        }
        source_keys = {"warehouse": warehouse_key, "barn": barn_key}
        source_resources = {
            source_building: self.production._resources(connection, source_keys[source_building])
            for source_building in set(source_buildings.values())
        }
        slot_count = max(1, len(resource_ids))
        slot_weight_budget = int(capacity_kg) / slot_count
        cargo, cargo_weight = [], 0.0
        for resource_id in resource_ids:
            item_id = STORAGE_ITEM_IDS.get(resource_id)
            source_building = source_buildings[resource_id]
            source_stock = source_resources[source_building].get(resource_id)
            if item_id is None or source_stock is None:
                source_name = "городском амбаре" if source_building == "barn" else "общем складе"
                raise ValueError(f"Ресурс {resource_id} отсутствует в {source_name}")
            item = connection.execute(
                "SELECT weight FROM items_catalog WHERE id=%s", (int(item_id),),
            ).fetchone()
            unit_weight = 0.0 if item is None else float(item["weight"] or 0)
            if unit_weight <= 0:
                raise ValueError(f"Не задан вес ресурса {resource_id}")
            per_slot_capacity = max(0, math.floor((slot_weight_budget + 1e-9) / unit_weight))
            quantity = min(
                int(source_stock["storage"]), destination_free[resource_id], per_slot_capacity,
            )
            if quantity <= 0:
                return [], 0.0, source_buildings
            cargo.append({
                "resource_id": resource_id, "item_id": int(item_id),
                "quantity": quantity, "unit_weight_kg": unit_weight,
            })
            cargo_weight += quantity * unit_weight
            destination_free[resource_id] -= quantity
            slot_weight_budget = max(0.0, slot_weight_budget - quantity * unit_weight)
        for item in cargo:
            connection.execute(
                """UPDATE building_resources SET storage=storage-%s
                   WHERE world_id=%s AND faction=%s AND building=%s AND resource=%s""",
                (item["quantity"], world_id, DEFAULT_FACTION,
                 source_buildings[item["resource_id"]], item["resource_id"]),
            )
        return cargo, cargo_weight, source_buildings

    def _driver_can_continue(self, connection, driver_id):
        driver = connection.execute(
            """SELECT alive, satisfaction, job_building, working, travel_direction
               FROM city_citizens WHERE id=%s FOR UPDATE""",
            (int(driver_id),),
        ).fetchone()
        return bool(
            driver is not None and driver["alive"] and driver["satisfaction"] == "satisfied"
            and driver["job_building"] is None and not driver["working"]
            and driver["travel_direction"] is None
        )

    def _finish_convoy(self, connection, convoy_id, now):
        convoy = connection.execute(
            "SELECT world_id, faction, arrival_at FROM transport_convoys WHERE id=%s FOR UPDATE",
            (int(convoy_id),),
        ).fetchone()
        if convoy is not None:
            horse_ids = [row["horse_id"] for row in connection.execute(
                "SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s",
                (int(convoy_id),),
            ).fetchall()]
            stable_key = (int(convoy["world_id"]), convoy["faction"], "stable")
            self.production._sync_horse_satiety(
                connection, stable_key,
                min(float(now), float(convoy["arrival_at"])), horse_ids,
            )
        connection.execute(
            """UPDATE transport_convoys SET status='arrived', phase='complete',
               pinned=FALSE, waiting_for_resources=FALSE WHERE id=%s""",
            (int(convoy_id),),
        )
        connection.execute(
            """UPDATE stable_horses SET status='Отдыхает'
               WHERE id IN (SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s)""",
            (int(convoy_id),),
        )

    def _start_pinned_leg(self, connection, convoy, world_id, now):
        cart = connection.execute(
            """SELECT upgrades_json FROM stable_cart_progress
               WHERE world_id=%s AND faction=%s AND building='stable' AND grade=%s""",
            (int(world_id), DEFAULT_FACTION, int(convoy["cart_grade"])),
        ).fetchone()
        upgrades = {} if cart is None else cart["upgrades_json"] or {}
        if isinstance(upgrades, str):
            upgrades = json.loads(upgrades)
        stats = cart_stats(upgrades)
        distance = float(self.routes[convoy["destination_building_id"]]["distance_tiles"])
        travel_seconds = max(1, int(math.ceil(distance * float(stats["seconds_per_tile"]))))
        connection.execute(
            """UPDATE transport_convoys SET cargo_json='[]'::jsonb, cargo_weight_kg=0,
               travel_seconds=%s, started_at=%s, arrival_at=%s, status='outbound', phase='outbound',
               waiting_for_resources=FALSE, delivered_quantity=0 WHERE id=%s""",
            (travel_seconds, now, now + travel_seconds, int(convoy["id"])),
        )
        horse_ids = [row["horse_id"] for row in connection.execute(
            "SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s",
            (int(convoy["id"]),),
        ).fetchall()]
        self.production._sync_horse_satiety(
            connection, (int(world_id), DEFAULT_FACTION, "stable"), now, horse_ids,
        )
        connection.execute(
            """UPDATE stable_horses SET status='В пути'
               WHERE id IN (SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s)""",
            (int(convoy["id"]),),
        )

    def _start_pinned_loading(self, connection, convoy, world_id, now):
        resource_ids = _json_list(convoy["resource_ids_json"])
        selected_resource_ids = [resource_id for resource_id in resource_ids if resource_id is not None]
        source_building = _production_building(convoy["destination_building_id"])
        source_key = (int(world_id), DEFAULT_FACTION, source_building)
        self._ensure_building(connection, source_key, now)
        source_resources = self.production._resources(connection, source_key)
        cart = connection.execute(
            """SELECT upgrades_json FROM stable_cart_progress
               WHERE world_id=%s AND faction=%s AND building='stable' AND grade=%s""",
            (int(world_id), DEFAULT_FACTION, int(convoy["cart_grade"])),
        ).fetchone()
        upgrades = {} if cart is None else cart["upgrades_json"] or {}
        if isinstance(upgrades, str):
            upgrades = json.loads(upgrades)
        stats = cart_stats(upgrades)
        capacity_kg = int(convoy["capacity_kg"])
        slot_weight_budget = capacity_kg / max(1, len(resource_ids))
        barn_resources = set(building_resources("barn"))
        city_storage = {}
        for resource_id in selected_resource_ids:
            storage_building = "barn" if resource_id in barn_resources else "warehouse"
            if storage_building not in city_storage:
                city_key = (int(world_id), DEFAULT_FACTION, storage_building)
                self._ensure_building(connection, city_key, now)
                city_state = self.production._state(connection, city_key)
                city_resources = self.production._resources(connection, city_key)
                storage_limit = int(building_level_info(int(city_state["level"]), storage_building)["storage"])
                reserved_rows = connection.execute(
                    """SELECT cargo_json FROM transport_convoys
                       WHERE world_id=%s AND faction=%s AND status IN ('outbound','blocked')
                         AND phase IN ('returning','unloading') AND id<>%s""",
                    (int(world_id), DEFAULT_FACTION, int(convoy["id"])),
                ).fetchall()
                reserved_by_resource = {}
                for row in reserved_rows:
                    for slot in _json_list(row["cargo_json"]):
                        resource_id = str(slot.get("resource_id", ""))
                        if ("barn" if resource_id in barn_resources else "warehouse") == storage_building:
                            reserved_by_resource[resource_id] = (
                                reserved_by_resource.get(resource_id, 0)
                                + int(slot.get("quantity", 0))
                            )
                free_by_resource = {}
                for requested_resource in selected_resource_ids:
                    requested_storage = (
                        "barn" if requested_resource in barn_resources else "warehouse"
                    )
                    if requested_storage == storage_building:
                        stock = city_resources.get(requested_resource)
                        free_by_resource[requested_resource] = max(
                            0, storage_limit
                            - (0 if stock is None else int(stock["storage"]))
                            - reserved_by_resource.get(requested_resource, 0),
                        )
                city_storage[storage_building] = {
                    "key": city_key,
                    "resources": city_resources,
                    "free_by_resource": free_by_resource,
                }

        cargo = []
        cargo_weight = 0.0
        for resource_id in selected_resource_ids:
            item_id = STORAGE_ITEM_IDS.get(resource_id)
            source = source_resources.get(resource_id)
            storage_building = "barn" if resource_id in barn_resources else "warehouse"
            destination = city_storage[storage_building]
            item = None if item_id is None else connection.execute(
                "SELECT weight FROM items_catalog WHERE id=%s", (int(item_id),),
            ).fetchone()
            unit_weight = 0.0 if item is None else float(item["weight"] or 0)
            if source is None or unit_weight <= 0:
                continue
            quantity = min(
                int(source["storage"]), destination["free_by_resource"][resource_id],
                max(0, math.floor((slot_weight_budget + 1e-9) / unit_weight)),
            )
            if quantity <= 0:
                continue
            cargo.append({
                "resource_id": resource_id, "item_id": int(item_id),
                "quantity": quantity, "unit_weight_kg": unit_weight,
            })
            quantity_weight = quantity * unit_weight
            cargo_weight += quantity_weight
            destination["free_by_resource"][resource_id] -= quantity
            slot_weight_budget = max(0.0, slot_weight_budget - quantity_weight)

        if not cargo:
            connection.execute(
                """UPDATE transport_convoys SET cargo_json='[]'::jsonb, cargo_weight_kg=0,
                   delivered_quantity=0 WHERE id=%s""",
                (int(convoy["id"]),),
            )
            self._start_return_leg(connection, convoy, now)
            return True

        for item in cargo:
            connection.execute(
                """UPDATE building_resources SET storage=storage-%s
                   WHERE world_id=%s AND faction=%s AND building=%s AND resource=%s""",
                (item["quantity"], int(world_id), DEFAULT_FACTION, source_building, item["resource_id"]),
            )
        grade = CART_GRADES[str(convoy["cart_grade"])]
        load_seconds = max(1, int(math.ceil(
            cargo_weight / max(0.01, float(grade.get("load_kg_per_minute", 3))) * 60
        )))
        connection.execute(
            """UPDATE transport_convoys SET cargo_json=%s::jsonb, cargo_weight_kg=%s,
               phase='loading', status='outbound', started_at=%s, travel_seconds=%s,
               arrival_at=%s, waiting_for_resources=FALSE, delivered_quantity=0 WHERE id=%s""",
            (json.dumps(cargo, ensure_ascii=False), cargo_weight, now, load_seconds,
             now + load_seconds, int(convoy["id"])),
        )
        connection.execute(
            """UPDATE stable_horses SET status='В пути'
               WHERE id IN (SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s)""",
            (int(convoy["id"]),),
        )
        return True

    def _start_return_leg(self, connection, convoy, now):
        cart = connection.execute(
            """SELECT upgrades_json FROM stable_cart_progress
               WHERE world_id=%s AND faction=%s AND building='stable' AND grade=%s""",
            (int(convoy["world_id"]), DEFAULT_FACTION, int(convoy["cart_grade"])),
        ).fetchone()
        upgrades = {} if cart is None else cart["upgrades_json"] or {}
        if isinstance(upgrades, str):
            upgrades = json.loads(upgrades)
        stats = cart_stats(upgrades)
        distance = float(self.routes[convoy["destination_building_id"]]["distance_tiles"])
        capacity = max(1, int(convoy["capacity_kg"]))
        speed_ratio = cart_load_speed_ratio(
            convoy["cargo_weight_kg"], capacity, stats["full_load_speed_penalty_percent"],
        )
        travel_seconds = max(1, int(math.ceil(
            distance * float(stats["seconds_per_tile"]) / speed_ratio
        )))
        connection.execute(
            """UPDATE transport_convoys SET status='outbound', phase='returning',
               started_at=%s, travel_seconds=%s, arrival_at=%s, waiting_for_resources=FALSE
               WHERE id=%s""",
            (now, travel_seconds, now + travel_seconds, int(convoy["id"])),
        )

    def turn_driver_home(self, connection, world_id, driver_id, now):
        convoy = connection.execute(
            """SELECT * FROM transport_convoys WHERE world_id=%s AND faction=%s
               AND driver_citizen_id=%s AND status IN ('outbound','blocked')
               FOR UPDATE""",
            (int(world_id), DEFAULT_FACTION, int(driver_id)),
        ).fetchone()
        if convoy is None:
            return False

        phase = convoy.get("phase") or "outbound"
        now = float(now)
        if phase == "outbound" and float(convoy["arrival_at"]) > now:
            total = max(1, int(convoy["travel_seconds"]))
            progress = min(1.0, max(0.0, (now - float(convoy["started_at"])) / total))
            return_seconds = max(1, int(math.ceil(progress * total)))
            started_at = now - (1.0 - progress) * total
            connection.execute(
                """UPDATE transport_convoys SET status='outbound',phase='returning',
                   pinned=FALSE,waiting_for_resources=FALSE,started_at=%s,arrival_at=%s
                   WHERE id=%s""",
                (started_at, now + return_seconds, int(convoy["id"])),
            )
        elif phase in ("outbound", "loading", "waiting_for_resources"):
            connection.execute(
                "UPDATE transport_convoys SET pinned=FALSE,waiting_for_resources=FALSE WHERE id=%s",
                (int(convoy["id"]),),
            )
            self._start_return_leg(connection, convoy, now)
        else:
            connection.execute(
                "UPDATE transport_convoys SET pinned=FALSE,waiting_for_resources=FALSE WHERE id=%s",
                (int(convoy["id"]),),
            )
        connection.execute(
            """UPDATE stable_horses SET status='В пути'
               WHERE id IN (SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s)""",
            (int(convoy["id"]),),
        )
        return True

    def _start_unloading(self, connection, convoy, now):
        grade = CART_GRADES[str(convoy["cart_grade"])]
        unload_seconds = max(1, int(math.ceil(
            float(convoy["cargo_weight_kg"])
            / max(0.01, float(grade.get("unload_kg_per_minute", 3))) * 60
        )))
        connection.execute(
            """UPDATE transport_convoys SET status='outbound', phase='unloading',
               started_at=%s, travel_seconds=%s, arrival_at=%s WHERE id=%s""",
            (now, unload_seconds, now + unload_seconds, int(convoy["id"])),
        )

    def _estimate_pinned_cargo_weight(self, connection, convoy, world_id):
        resource_ids = _json_list(convoy["resource_ids_json"])
        if not resource_ids:
            return 0.0
        source_building = _production_building(convoy["destination_building_id"])
        source_resources = self.production._resources(
            connection, (int(world_id), DEFAULT_FACTION, source_building),
        )
        barn_resources = set(building_resources("barn"))
        storage_free = {}
        reserved_rows = connection.execute(
            """SELECT cargo_json FROM transport_convoys WHERE world_id=%s AND faction=%s
               AND status IN ('outbound','blocked') AND phase IN ('returning','unloading')
               AND id<>%s""",
            (int(world_id), DEFAULT_FACTION, int(convoy["id"])),
        ).fetchall()
        for resource_id in resource_ids:
            storage_building = "barn" if resource_id in barn_resources else "warehouse"
            if resource_id in storage_free:
                continue
            key = (int(world_id), DEFAULT_FACTION, storage_building)
            state = self.production._state(connection, key)
            rows = self.production._resources(connection, key)
            limit = int(building_level_info(int(state["level"]), storage_building)["storage"])
            reserved = sum(
                int(slot.get("quantity", 0))
                for row in reserved_rows for slot in _json_list(row["cargo_json"])
                if str(slot.get("resource_id")) == resource_id
            )
            stock = rows.get(resource_id)
            storage_free[resource_id] = max(
                0, limit - (0 if stock is None else int(stock["storage"])) - reserved,
            )

        slot_budget = max(1, int(convoy["capacity_kg"])) / len(resource_ids)
        total_weight = 0.0
        for resource_id in resource_ids:
            item_id = STORAGE_ITEM_IDS.get(str(resource_id))
            source = source_resources.get(str(resource_id))
            item = None if item_id is None else connection.execute(
                "SELECT weight FROM items_catalog WHERE id=%s", (int(item_id),),
            ).fetchone()
            unit_weight = 0.0 if item is None else float(item["weight"] or 0)
            storage_building = "barn" if str(resource_id) in barn_resources else "warehouse"
            if source is None or unit_weight <= 0 or storage_free[resource_id] <= 0:
                return 0.0
            quantity = min(
                int(source["storage"]), storage_free[resource_id],
                max(0, math.floor((slot_budget + 1e-9) / unit_weight)),
            )
            if quantity <= 0:
                return 0.0
            weight = quantity * unit_weight
            total_weight += weight
            storage_free[resource_id] -= quantity
            slot_budget = max(0.0, slot_budget - weight)
        return total_weight

    def _unload_at_city(self, connection, convoy, world_id, now):
        barn_resources = set(building_resources("barn"))
        city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
        available_city_resources = set(city_storage_resources(
            "barn", city_level, building_resources("barn")
        )) | set(city_storage_resources(
            "warehouse", city_level, building_resources("warehouse")
        ))
        cargo = _json_list(convoy["cargo_json"])
        remaining = []
        for item in cargo:
            resource_id = str(item["resource_id"])
            if resource_id not in available_city_resources:
                remaining.append(item)
                continue
            building = "barn" if resource_id in barn_resources else "warehouse"
            key = (int(world_id), DEFAULT_FACTION, building)
            self._ensure_building(connection, key, now)
            state = self.production._state(connection, key)
            limit = int(building_level_info(int(state["level"]), building)["storage"])
            rows = self.production._resources(connection, key)
            stock = rows.get(resource_id)
            free = max(0, limit - (0 if stock is None else int(stock["storage"])))
            quantity = max(0, int(item.get("quantity", 0)))
            accepted = min(quantity, free)
            if accepted:
                connection.execute(
                    f"UPDATE building_resources SET storage=storage+%s WHERE {self._where()} AND resource=%s",
                    (accepted, *key, resource_id),
                )
                free -= accepted
            if accepted < quantity:
                remaining.append({**item, "quantity": quantity - accepted})

        if remaining:
            remaining_weight = sum(
                int(item["quantity"]) * float(item.get("unit_weight_kg", 0))
                for item in remaining
            )
            connection.execute(
                """UPDATE transport_convoys SET status='blocked', phase='unloading',
                   cargo_json=%s::jsonb, cargo_weight_kg=%s, started_at=%s,
                   travel_seconds=%s, arrival_at=%s WHERE id=%s""",
                (json.dumps(remaining, ensure_ascii=False), remaining_weight, now,
                 RESOURCE_RETRY_SECONDS, now + RESOURCE_RETRY_SECONDS, int(convoy["id"])),
            )
            return False

        if convoy["pinned"] and self._driver_can_continue(
            connection, int(convoy["driver_citizen_id"]),
        ):
            connection.execute(
                """UPDATE transport_convoys SET status='outbound', phase='resting',
                   cargo_json='[]'::jsonb, cargo_weight_kg=0, delivered_quantity=0,
                   started_at=%s, travel_seconds=%s, arrival_at=%s,
                   waiting_for_resources=FALSE WHERE id=%s""",
                (now, PROVISION_SECONDS, now + PROVISION_SECONDS, int(convoy["id"])),
            )
            return True
        self._finish_convoy(connection, int(convoy["id"]), now)
        return True

    def _settle_due(self, connection, world_id, now):
        self.production._advance_cart_maintenance(
            connection, (int(world_id), DEFAULT_FACTION, "stable"), now,
        )
        rows = connection.execute(
            """SELECT * FROM transport_convoys
               WHERE world_id = %s AND faction = %s AND status IN ('outbound','blocked')
                 AND arrival_at <= %s
               ORDER BY arrival_at, id FOR UPDATE""",
            (int(world_id), DEFAULT_FACTION, float(now)),
        ).fetchall()
        for convoy in rows:
            phase = convoy.get("phase", "outbound")
            if phase == "waiting_for_resources" or convoy["waiting_for_resources"]:
                if convoy["pinned"] and self._driver_can_continue(
                    connection, int(convoy["driver_citizen_id"]),
                ):
                    self._start_pinned_loading(connection, convoy, world_id, now)
                else:
                    self._finish_convoy(connection, int(convoy["id"]), now)
                continue
            if phase == "loading":
                self._start_return_leg(connection, convoy, now)
                continue
            if phase == "returning":
                self._start_unloading(connection, convoy, now)
                continue
            if phase == "unloading":
                self._unload_at_city(connection, convoy, world_id, now)
                continue
            if phase == "resting":
                if convoy["pinned"] and self._driver_can_continue(
                    connection, int(convoy["driver_citizen_id"]),
                ):
                    self._start_pinned_leg(connection, convoy, world_id, now)
                else:
                    self._finish_convoy(connection, int(convoy["id"]), now)
                continue
            if (convoy["status"] == "blocked" and phase == "outbound"
                    and convoy["pinned"] and _json_list(convoy["cargo_json"])):
                self._start_return_leg(connection, convoy, now)
                continue

            building = _production_building(convoy["destination_building_id"])
            key = (int(world_id), DEFAULT_FACTION, building)
            self._ensure_building(connection, key, now)
            state = self.production._state(connection, key)
            capacity = int(building_level_info(int(state["level"]), building)["storage"])
            resources = self.production._resources(connection, key)
            reserved_rows = connection.execute(
                """SELECT cargo_json FROM transport_convoys WHERE world_id=%s AND faction=%s
                   AND destination_building_id=%s AND status IN ('outbound','blocked') AND id<>%s""",
                (int(world_id), DEFAULT_FACTION, convoy["destination_building_id"], int(convoy["id"])),
            ).fetchall()
            reserved_by_resource = {}
            for reserved_row in reserved_rows:
                for slot in _json_list(reserved_row["cargo_json"]):
                    resource_id = str(slot.get("resource_id", ""))
                    reserved_by_resource[resource_id] = (
                        reserved_by_resource.get(resource_id, 0) + int(slot.get("quantity", 0))
                    )
            cargo = _json_list(convoy["cargo_json"])
            free_by_resource = {
                str(slot["resource_id"]): max(
                    0, capacity
                    - int(resources.get(str(slot["resource_id"]), {}).get("storage", 0))
                    - reserved_by_resource.get(str(slot["resource_id"]), 0),
                )
                for slot in cargo
            }
            remaining = []
            delivered = int(convoy["delivered_quantity"])
            for slot in cargo:
                resource_id = str(slot["resource_id"])
                quantity = max(0, int(slot.get("quantity", 0)))
                accepted = min(quantity, free_by_resource[resource_id])
                if accepted:
                    connection.execute(
                        f"UPDATE building_resources SET storage = storage + %s WHERE {self._where()} AND resource = %s",
                        (accepted, *key, resource_id),
                    )
                    free_by_resource[resource_id] -= accepted
                    delivered += accepted
                if accepted < quantity:
                    remaining.append({**slot, "quantity": quantity - accepted})
            if remaining:
                connection.execute(
                    """UPDATE transport_convoys SET cargo_json = %s::jsonb,
                       delivered_quantity = %s, status = 'blocked', phase='outbound' WHERE id = %s""",
                    (json.dumps(remaining, ensure_ascii=False), delivered, int(convoy["id"])),
                )
                continue

            if convoy["pinned"] and self._driver_can_continue(
                connection, int(convoy["driver_citizen_id"]),
            ):
                refreshed = connection.execute(
                    "SELECT * FROM transport_convoys WHERE id=%s FOR UPDATE",
                    (int(convoy["id"]),),
                ).fetchone()
                self._start_pinned_loading(connection, refreshed, world_id, now)
                continue
            self._finish_convoy(connection, int(convoy["id"]), now)

    def set_pinned(self, character_id, convoy_id, pinned, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            world_id = self._world_id(connection, character_id)
            convoy = connection.execute(
                """SELECT id, waiting_for_resources FROM transport_convoys
                   WHERE id=%s AND world_id=%s AND faction=%s
                     AND status IN ('outbound','blocked') FOR UPDATE""",
                (int(convoy_id), world_id, DEFAULT_FACTION),
            ).fetchone()
            if convoy is None:
                raise ValueError("Активный рейс не найден")
            pinned = bool(pinned)
            if not pinned and convoy["waiting_for_resources"]:
                connection.execute(
                    """UPDATE transport_convoys SET pinned=FALSE, status='arrived', phase='complete',
                       waiting_for_resources=FALSE WHERE id=%s""",
                    (int(convoy_id),),
                )
                horse_ids = [row["horse_id"] for row in connection.execute(
                    "SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s",
                    (int(convoy_id),),
                ).fetchall()]
                self.production._sync_horse_satiety(
                    connection, (world_id, DEFAULT_FACTION, "stable"), now, horse_ids,
                )
                connection.execute(
                    """UPDATE stable_horses SET status='Отдыхает'
                       WHERE id IN (SELECT horse_id FROM transport_convoy_horses WHERE convoy_id=%s)""",
                    (int(convoy_id),),
                )
            else:
                connection.execute(
                    "UPDATE transport_convoys SET pinned=%s WHERE id=%s",
                    (pinned, int(convoy_id)),
                )
        return self.get_world_convoys(character_id, now=now)

    def dispatch(self, character_id, payload, now=None):
        now = time.time() if now is None else float(now)
        character_id = int(character_id)
        cart_id = str(payload.get("cart_id", ""))
        cart_type_id, separator, instance_value = cart_id.partition("~")
        try:
            grade = int(cart_type_id.rsplit("_", 1)[1])
            cart_instance = int(instance_value) if separator else 1
        except (IndexError, ValueError):
            raise ValueError("Выбрана неизвестная повозка")
        if cart_instance < 1:
            raise ValueError("Выбрана неизвестная повозка")
        grade_id = str(grade)
        cart_config = CART_GRADES.get(grade_id)
        if cart_config is None:
            raise ValueError("Эта повозка пока недоступна для отправки")

        horse_ids = [int(value) for value in payload.get("horse_ids", [])]
        driver_id = int(payload.get("driver_citizen_id", 0))
        destination_id = str(payload.get("destination_building_id", ""))
        resource_ids = [None if value is None else str(value)
                for value in payload.get("resource_ids", [])]
        selected_resource_ids = [value for value in resource_ids if value is not None]
        pinned = bool(payload.get("pinned", False))
        if len(horse_ids) != int(cart_config.get("horse_count", 0)) or len(set(horse_ids)) != len(horse_ids):
            raise ValueError("Выберите требуемое число разных лошадей")
        slot_count = int(cart_config.get("resource_slots", 0))
        if len(resource_ids) != slot_count or any(resource is None for resource in resource_ids):
            raise ValueError("Выберите ресурс для каждого грузового слота")
        if len(resource_ids) != slot_count or len(set(selected_resource_ids)) != len(selected_resource_ids):
            raise ValueError("Проверьте выбранный груз в слотах повозки")
        route = self.routes.get(destination_id)
        if route is None or not route.get("tiles"):
            raise ValueError("Выберите доступный загородный маршрут")
        building = _production_building(destination_id)
        allowed_resources = {str(item["id"]) for item in route.get("resources", [])}
        if any(resource not in allowed_resources for resource in selected_resource_ids):
            raise ValueError("Выбранный ресурс не подходит для пункта назначения")

        with self.db.connection() as connection:
            lock_character(connection, character_id)
            world_id = self._world_id(connection, character_id)
            city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
            if destination_id not in unlocked_country_buildings(city_level):
                raise ValueError("Этот загородный маршрут ещё не открыт для города")
            available_city_resources = set(city_storage_resources(
                "barn", city_level, building_resources("barn")
            )) | set(city_storage_resources(
                "warehouse", city_level, building_resources("warehouse")
            ))
            if any(resource_id not in available_city_resources for resource_id in selected_resource_ids):
                raise ValueError("Этот ресурс ещё не открыт для города")
            stable_key = (world_id, DEFAULT_FACTION, "stable")
            warehouse_key = (world_id, DEFAULT_FACTION, "warehouse")
            barn_key = (world_id, DEFAULT_FACTION, "barn")
            destination_key = (world_id, DEFAULT_FACTION, building)
            self._ensure_building(connection, stable_key, now)
            self._ensure_building(connection, warehouse_key, now)
            barn_resources = set(building_resources("barn"))
            source_buildings = {
                resource_id: ("barn" if resource_id in barn_resources else "warehouse")
                for resource_id in selected_resource_ids
            }
            if "barn" in source_buildings.values():
                self._ensure_building(connection, barn_key, now)
            self._ensure_building(connection, destination_key, now)
            self._settle_due(connection, world_id, now)

            cart = connection.execute(
                f"""SELECT body_owned, body_count, upgrades_json, cart_wear_json
                    FROM stable_cart_progress
                    WHERE {self._where()} AND grade = %s FOR UPDATE""",
                (*stable_key, grade),
            ).fetchone()
            body_count = (0 if cart is None else max(
                int(cart["body_count"] or 0), 1 if cart["body_owned"] else 0
            ))
            if cart is None or cart_instance > body_count:
                raise ValueError("Эта повозка ещё не куплена")
            cart_wear = cart["cart_wear_json"] or {}
            if isinstance(cart_wear, str):
                cart_wear = json.loads(cart_wear)
            durability = float(cart_wear.get(cart_id, {}).get("durability", 100))
            if durability <= 0:
                raise ValueError("Повозка сломана. Отремонтируйте её древесиной")
            active_cart = connection.execute(
                """SELECT 1 FROM transport_convoys WHERE world_id=%s AND faction=%s
                   AND cart_id=%s AND status IN ('outbound','blocked')""",
                (world_id, DEFAULT_FACTION, cart_id),
            ).fetchone()
            if active_cart:
                raise ValueError("Повозка уже занята рейсом")

            active_driver = connection.execute(
                """SELECT 1 FROM transport_convoys WHERE world_id=%s AND faction=%s
                   AND driver_citizen_id=%s AND status IN ('outbound','blocked')""",
                (world_id, DEFAULT_FACTION, driver_id),
            ).fetchone()
            if active_driver:
                raise ValueError("Этот горожанин уже ведёт повозку")

            driver = connection.execute(
                """SELECT * FROM city_citizens WHERE id=%s AND world_id=%s AND faction=%s
                   AND alive=TRUE FOR UPDATE""",
                (driver_id, world_id, DEFAULT_FACTION),
            ).fetchone()
            if driver is None:
                raise ValueError("Участник экипажа не найден")
            from server.city_population import CityPopulation

            population = CityPopulation(self.db)
            population._sync_citizen_hunger(
                connection, (world_id, DEFAULT_FACTION), dict(driver), now,
                population._food_stock(connection, world_id),
            )
            driver = connection.execute(
                "SELECT * FROM city_citizens WHERE id=%s AND alive=TRUE FOR UPDATE",
                (driver_id,),
            ).fetchone()
            if driver is None:
                raise ValueError("Участник экипажа умер от голода")
            if (driver["satisfaction"] != "satisfied" or driver["job_building"] is not None
                    or driver["working"] or driver["travel_direction"] is not None):
                raise ValueError("Участник экипажа должен быть свободным, сытым и не находиться в пути")

            horses = connection.execute(
                """SELECT id, name, breed, status FROM stable_horses
                   WHERE world_id=%s AND faction=%s AND building='stable' AND id = ANY(%s)
                     AND status='Отдыхает' FOR UPDATE""",
                (world_id, DEFAULT_FACTION, horse_ids),
            ).fetchall()
            if len(horses) != len(horse_ids):
                raise ValueError("Все лошади должны быть свободны и стоять в конюшне")

            self._ensure_building(connection, destination_key, now)
            upgrades = cart["upgrades_json"] or {}
            if isinstance(upgrades, str):
                upgrades = json.loads(upgrades)
            stats = cart_stats(upgrades)
            capacity_kg = int(stats["capacity_kg"])
            cargo, cargo_weight = [], 0.0
            if not pinned:
                destination_state = self.production._state(connection, destination_key)
                destination_capacity = int(building_level_info(
                    int(destination_state["level"]), building,
                )["storage"])
                destination_resources = self.production._resources(connection, destination_key)
                reserved_rows = connection.execute(
                    """SELECT cargo_json FROM transport_convoys
                       WHERE world_id=%s AND faction=%s AND destination_building_id=%s
                         AND status IN ('outbound','blocked')""",
                    (world_id, DEFAULT_FACTION, destination_id),
                ).fetchall()
                reserved_by_resource = {}
                for row in reserved_rows:
                    for slot in _json_list(row["cargo_json"]):
                        resource_id = str(slot.get("resource_id", ""))
                        reserved_by_resource[resource_id] = (
                            reserved_by_resource.get(resource_id, 0)
                            + int(slot.get("quantity", 0))
                        )
                destination_free = {
                    resource_id: max(
                        0, destination_capacity
                        - int(destination_resources.get(resource_id, {}).get("storage", 0))
                        - reserved_by_resource.get(resource_id, 0),
                    )
                    for resource_id in set(selected_resource_ids)
                }
                source_keys = {"warehouse": warehouse_key, "barn": barn_key}
                source_resources = {
                    source_building: self.production._resources(connection, source_keys[source_building])
                    for source_building in set(source_buildings.values())
                }
                slot_weight_budget = capacity_kg / max(1, slot_count)
                for resource_id in ([] if pinned else resource_ids):
                    if resource_id is None:
                        continue
                    item_id = STORAGE_ITEM_IDS.get(resource_id)
                    source_building = source_buildings[resource_id]
                    source_stock = source_resources[source_building].get(resource_id)
                    if item_id is None or source_stock is None:
                        continue
                    item = connection.execute(
                        "SELECT weight FROM items_catalog WHERE id=%s", (int(item_id),),
                    ).fetchone()
                    unit_weight = 0.0 if item is None else float(item["weight"] or 0)
                    if unit_weight <= 0:
                        continue
                    per_slot_capacity = max(0, math.floor((slot_weight_budget + 1e-9) / unit_weight))
                    quantity = min(
                        int(source_stock["storage"]), destination_free[resource_id], per_slot_capacity,
                    )
                    if quantity <= 0:
                        continue
                    cargo.append({
                        "resource_id": resource_id, "item_id": int(item_id),
                        "quantity": quantity, "unit_weight_kg": unit_weight,
                    })
                    cargo_weight += quantity * unit_weight
                    destination_free[resource_id] -= quantity
                    slot_weight_budget = max(0.0, slot_weight_budget - quantity * unit_weight)

            distance = float(route["distance_tiles"])
            speed_ratio = cart_load_speed_ratio(
                cargo_weight, capacity_kg, stats["full_load_speed_penalty_percent"],
            )
            travel_seconds = max(1, int(math.ceil(
                distance * float(stats["seconds_per_tile"]) / speed_ratio
            )))
            convoy = connection.execute(
                """INSERT INTO transport_convoys
                   (world_id, faction, cart_id, cart_grade, driver_citizen_id,
                    destination_building_id, cargo_json, cargo_weight_kg, capacity_kg,
                          travel_seconds, started_at, arrival_at, status, pinned, resource_ids_json,
                          started_by, created_at)
                         VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,'outbound',%s,%s::jsonb,%s,%s)
                   RETURNING id""",
                (world_id, DEFAULT_FACTION, cart_id, grade, driver_id, destination_id,
                 json.dumps(cargo, ensure_ascii=False), cargo_weight, capacity_kg,
                      travel_seconds, now, now + travel_seconds, pinned,
                      json.dumps(resource_ids, ensure_ascii=False), character_id, now),
            ).fetchone()
            convoy_id = int(convoy["id"])
            for index, horse_id in enumerate(horse_ids):
                connection.execute(
                    """INSERT INTO transport_convoy_horses (convoy_id, horse_id, slot_index)
                       VALUES (%s,%s,%s)""",
                    (convoy_id, horse_id, index),
                )
            self.production._sync_horse_satiety(
                connection, stable_key, now, horse_ids,
            )
            connection.execute(
                "UPDATE stable_horses SET status='В пути' WHERE id = ANY(%s)",
                (horse_ids,),
            )
            for item in cargo:
                if not pinned:
                    connection.execute(
                        """UPDATE building_resources SET storage=storage-%s
                           WHERE world_id=%s AND faction=%s AND building=%s AND resource=%s""",
                        (item["quantity"], world_id, DEFAULT_FACTION,
                         source_buildings[item["resource_id"]], item["resource_id"]),
                    )
        convoy = next(
            (row for row in self.get_world_convoys(character_id, now=now)
             if int(row["id"]) == convoy_id),
            None,
        )
        if convoy is None:
            raise RuntimeError("Рейс создан, но не найден в снимке мира")
        return convoy

    def get_world_convoys(self, character_id, now=None):
        now = time.time() if now is None else float(now)
        with self.db.connection() as connection:
            world_id = self._world_id(connection, character_id)
            city_level = self.production._city_level(connection, world_id, DEFAULT_FACTION)
            self._settle_due(connection, world_id, now)
            rows = connection.execute(
                """SELECT convoy.* FROM transport_convoys convoy
                   WHERE convoy.world_id=%s AND convoy.faction=%s
                     AND convoy.status IN ('outbound','blocked')
                   ORDER BY convoy.started_at, convoy.id""",
                (world_id, DEFAULT_FACTION),
            ).fetchall()
            results = []
            for row in rows:
                route = self.routes.get(row["destination_building_id"])
                if route is None:
                    continue
                horses = connection.execute(
                    """SELECT horse.id,horse.name,horse.breed,horse.status
                       FROM transport_convoy_horses link JOIN stable_horses horse ON horse.id=link.horse_id
                       WHERE link.convoy_id=%s ORDER BY link.slot_index""",
                    (int(row["id"]),),
                ).fetchall()
                driver = connection.execute(
                    "SELECT name,satiety,satisfaction FROM city_citizens WHERE id=%s",
                    (int(row["driver_citizen_id"]),),
                ).fetchone()
                phase = row["phase"] or "outbound"
                eta = max(0, int(math.ceil(float(row["arrival_at"]) - now)))
                total = max(1, int(row["travel_seconds"]))
                phase_progress = min(1.0, max(0.0, (now - float(row["started_at"])) / total))
                cart = connection.execute(
                    """SELECT upgrades_json FROM stable_cart_progress
                       WHERE world_id=%s AND faction=%s AND building='stable' AND grade=%s""",
                    (world_id, DEFAULT_FACTION, int(row["cart_grade"])),
                ).fetchone()
                upgrades = {} if cart is None else cart["upgrades_json"] or {}
                if isinstance(upgrades, str):
                    upgrades = json.loads(upgrades)
                stats = cart_stats(upgrades)
                distance = float(route["distance_tiles"])
                outbound_seconds = max(1, int(math.ceil(distance * stats["seconds_per_tile"])))
                cargo_weight = max(0.0, float(row["cargo_weight_kg"]))
                if cargo_weight <= 0 and row["pinned"] and phase in ("outbound", "loading", "waiting_for_resources"):
                    cargo_weight = self._estimate_pinned_cargo_weight(connection, row, world_id)
                cart_config = CART_GRADES[str(row["cart_grade"])]
                load_per_minute = max(0.01, float(cart_config.get("load_kg_per_minute", 3)))
                unload_per_minute = max(0.01, float(cart_config.get("unload_kg_per_minute", 3)))
                load_seconds = max(1, int(math.ceil(cargo_weight / load_per_minute * 60))) if cargo_weight > 0 else 0
                unload_seconds = max(1, int(math.ceil(cargo_weight / unload_per_minute * 60))) if cargo_weight > 0 else 0
                speed_ratio = cart_load_speed_ratio(
                    cargo_weight, row["capacity_kg"], stats["full_load_speed_penalty_percent"],
                )
                return_seconds = max(1, int(math.ceil(distance * stats["seconds_per_tile"] / speed_ratio)))
                phase_index = {
                    "outbound": 0, "loading": 1, "waiting_for_resources": 1,
                    "returning": 2, "unloading": 3,
                }.get(phase, 4)
                stage_definitions = (
                    ("outbound", f"Следует в {route['name']}", outbound_seconds),
                    ("loading", "Погрузка", load_seconds),
                    ("returning", "Следует в город", return_seconds),
                    ("unloading", "Разгрузка", unload_seconds),
                )
                route_stages = []
                for index, (stage_phase, label, duration) in enumerate(stage_definitions):
                    state = "complete" if index < phase_index else "current" if index == phase_index else "future"
                    seconds = 0 if state == "complete" else eta if state == "current" else duration
                    if not row["pinned"] and phase == "outbound":
                        if index == 1:
                            state, seconds = "complete", 0
                        elif index > 1:
                            state, seconds = "future", 0
                    route_stages.append({"phase": stage_phase, "label": label,
                                         "seconds": seconds, "state": state})
                if row["status"] == "blocked":
                    cycle_seconds_remaining = None
                elif row["pinned"] and phase == "resting":
                    cycle_seconds_remaining = eta
                elif row["pinned"]:
                    cycle_seconds_remaining = eta + sum(
                        stage["seconds"] for stage in route_stages if stage["state"] == "future"
                    ) + PROVISION_SECONDS
                else:
                    cycle_seconds_remaining = eta
                direction = "returning" if phase in ("returning", "unloading", "resting") else "outbound"
                if phase in ("loading", "waiting_for_resources"):
                    progress = 1.0
                elif phase in ("unloading", "resting"):
                    progress = 0.0
                elif phase == "returning":
                    progress = 1.0 - phase_progress
                else:
                    progress = phase_progress
                if row["status"] == "blocked" and phase == "unloading":
                    progress = 0.0
                position = route_position(row["destination_building_id"], progress, city_level)
                if row["status"] == "blocked":
                    eta = 0
                if row["status"] != "blocked" and phase in ("outbound", "returning"):
                    elapsed = max(0.0, now - float(row["started_at"]))
                    phase_progress = min(1.0, elapsed / total)
                    progress = 1.0 - phase_progress if phase == "returning" else phase_progress
                    position = route_position(row["destination_building_id"], progress, city_level)
                if position is None:
                    continue
                phase_status = {
                    "outbound": "Едет к объекту",
                    "loading": "Погрузка",
                    "returning": "Возвращается в город",
                    "unloading": "Разгрузка",
                    "resting": "Пополнение провизии",
                    "waiting_for_resources": "Ожидает ресурсы",
                }.get(phase, "В пути")
                if row["status"] == "blocked":
                    phase_status = ("Ожидает места для разгрузки" if phase == "unloading"
                                    else "Ожидает разгрузки")
                results.append({
                    "id": int(row["id"]), "cart_id": row["cart_id"],
                    "cart_grade": int(row["cart_grade"]),
                    "cart_name": CART_GRADES[str(row["cart_grade"])]["name"],
                    "cart_sprite_key": CART_GRADES[str(row["cart_grade"])].get("sprite_key", "light"),
                    "destination_building_id": row["destination_building_id"],
                    "destination_name": route["name"], "route_name": route["name"],
                    "driver_citizen_id": int(row["driver_citizen_id"]),
                    "driver_name": "Горожанин" if driver is None else driver["name"],
                    "horses": [dict(horse) for horse in horses],
                    "cargo": _json_list(row["cargo_json"]),
                    "cargo_kg": float(row["cargo_weight_kg"]),
                    "capacity_kg": int(row["capacity_kg"]),
                    "pinned": bool(row["pinned"]),
                    "waiting_for_resources": bool(row["waiting_for_resources"]),
                    "phase": phase, "status": phase_status,
                    "route_stages": route_stages,
                    "cycle_seconds_remaining": cycle_seconds_remaining,
                    "movement_text": phase_status,
                    "direction": direction, "travel_seconds": total,
                    "seconds_remaining": eta, "progress_percent": int(progress * 100),
                    "position_x": position[0], "position_y": position[1],
                    "position_direction": position[2],
                    "started_at": float(row["started_at"]),
                })
            return results
