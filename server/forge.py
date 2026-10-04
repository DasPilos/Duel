"""Shared Radburg forge queue and owner-only finished-order storage."""

import time

from core.currency import Currency
from core.forge_recipes import FORGE_QUEUE_LIMIT, RECIPE_BY_ITEM
from server.database import lock_character
from server.production_buildings import DEFAULT_FACTION


class Forge:
    def __init__(self, database, items_database):
        self.db = database
        self.items = items_database

    @staticmethod
    def _lock_queue(connection, world_id, faction):
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"forge:{int(world_id)}:{faction}",),
        )

    @staticmethod
    def _world_id(connection, character_id):
        row = connection.execute(
            "SELECT world_id FROM characters WHERE id = %s", (int(character_id),)
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        return int(row["world_id"])

    @staticmethod
    def _advance_queue(connection, world_id, faction, now):
        orders = connection.execute(
            """SELECT id, status, queued_at, started_at, duration_seconds
               FROM forge_orders
               WHERE world_id = %s AND faction = %s AND status IN ('queued', 'working')
               ORDER BY id FOR UPDATE""",
            (world_id, faction),
        ).fetchall()
        previous_finish = None
        for order in orders:
            if order["status"] == "working" and order["started_at"] is not None:
                started_at = float(order["started_at"])
            else:
                started_at = previous_finish if previous_finish is not None else float(order["queued_at"])
            finish_at = started_at + int(order["duration_seconds"])
            if finish_at <= now:
                connection.execute(
                    """UPDATE forge_orders
                       SET status = 'ready', started_at = %s, completed_at = %s
                       WHERE id = %s AND status IN ('queued', 'working')""",
                    (started_at, finish_at, order["id"]),
                )
                previous_finish = finish_at
                continue
            connection.execute(
                """UPDATE forge_orders SET status = 'working', started_at = %s
                   WHERE id = %s AND status = 'queued'""",
                (started_at, order["id"]),
            )
            previous_finish = finish_at
            break

    def get_state(self, character_id, now=None):
        now = time.time() if now is None else float(now)
        faction = DEFAULT_FACTION
        with self.db.connection() as connection:
            world_id = self._world_id(connection, character_id)
            self._lock_queue(connection, world_id, faction)
            self._advance_queue(connection, world_id, faction, now)
            rows = connection.execute(
                """SELECT o.id, o.owner_character_id, o.item_id, o.status, o.queued_at,
                          o.started_at, o.completed_at, o.duration_seconds,
                          c.name AS owner_name, i.name AS item_name, i.icon AS item_icon
                   FROM forge_orders o
                   JOIN characters c ON c.id = o.owner_character_id
                   JOIN items_catalog i ON i.id = o.item_id
                   WHERE o.world_id = %s AND o.faction = %s
                     AND o.status IN ('queued', 'working')
                   ORDER BY o.id""",
                (world_id, faction),
            ).fetchall()
            queue = []
            queue_total_seconds = 0
            active = True
            for position, row in enumerate(rows, 1):
                if row["status"] == "working" and active:
                    seconds_left = max(0, int(row["started_at"] + row["duration_seconds"] - now))
                    active = False
                else:
                    seconds_left = int(row["duration_seconds"])
                queue_total_seconds += seconds_left
                queue.append({
                    "order_id": int(row["id"]),
                    "owner_character_id": int(row["owner_character_id"]),
                    "owner_name": row["owner_name"],
                    "item_id": int(row["item_id"]),
                    "item_name": row["item_name"],
                    "icon": row["item_icon"],
                    "status": row["status"],
                    "position": position,
                    "duration_seconds": int(row["duration_seconds"]),
                    "seconds_left": seconds_left,
                })
            warehouse_rows = connection.execute(
                """SELECT o.id AS order_id, o.item_id, o.completed_at,
                          i.name AS item_name, i.icon AS item_icon,
                          i.description, i.weight, i.price, i.equip_slot
                   FROM forge_orders o
                   JOIN items_catalog i ON i.id = o.item_id
                   WHERE o.world_id = %s AND o.faction = %s
                     AND o.owner_character_id = %s AND o.status = 'ready'
                   ORDER BY o.completed_at, o.id""",
                (world_id, faction, int(character_id)),
            ).fetchall()
            warehouse = [
                {
                    "order_id": int(row["order_id"]),
                    "item_id": int(row["item_id"]),
                    "item_name": row["item_name"],
                    "icon": row["item_icon"],
                    "description": row.get("description", ""),
                    "weight": row.get("weight", 0),
                    "price": row.get("price", 0),
                    "equip_slot": row.get("equip_slot"),
                    "completed_at": row["completed_at"],
                }
                for row in warehouse_rows
            ]
        return {
            "queue": queue,
            "queue_count": len(queue),
            "queue_limit": FORGE_QUEUE_LIMIT,
            "queue_total_seconds": queue_total_seconds,
            "warehouse": warehouse,
        }

    def create_order(self, character_id, item_id, now=None):
        now = time.time() if now is None else float(now)
        item_id = int(item_id)
        recipe = RECIPE_BY_ITEM.get(item_id)
        if recipe is None:
            raise ValueError("Для этого предмета рецепт ещё не задан")
        faction = DEFAULT_FACTION
        with self.db.connection() as connection:
            world_id = self._world_id(connection, character_id)
            self._lock_queue(connection, world_id, faction)
            lock_character(connection, character_id)
            self._advance_queue(connection, world_id, faction, now)
            queued = connection.execute(
                """SELECT COUNT(*) AS amount FROM forge_orders
                   WHERE world_id = %s AND faction = %s AND status IN ('queued', 'working')""",
                (world_id, faction),
            ).fetchone()["amount"]
            if int(queued) >= FORGE_QUEUE_LIMIT:
                raise ValueError("Очередь кузницы заполнена (5 из 5)")

            cost_copper = int(recipe.get("cost_copper", 0))
            if cost_copper > 0:
                char_row = connection.execute(
                    "SELECT copper, silver, gold FROM characters WHERE id = %s",
                    (int(character_id),),
                ).fetchone()
                if char_row is None:
                    raise ValueError("Персонаж не найден")
                curr = Currency(char_row["copper"], char_row["silver"], char_row["gold"])
                if not curr.has_enough_copper(cost_copper):
                    raise ValueError(f"Недостаточно денег: требуется {Currency.format_amount(cost_copper)}")

            for material_id, amount in recipe["materials"].items():
                rows = connection.execute(
                    """SELECT id, quantity FROM character_items
                       WHERE character_id = %s AND item_id = %s
                       ORDER BY slot_index FOR UPDATE""",
                    (int(character_id), int(material_id)),
                ).fetchall()
                if sum(int(row["quantity"]) for row in rows) < int(amount):
                    material = self.items._catalog_item(connection, int(material_id))
                    material_name = material["name"] if material else "материал"
                    raise ValueError(f"Недостаточно материала: {material_name} ×{amount}")

            if cost_copper > 0:
                curr.subtract_copper_amount(cost_copper)
                connection.execute(
                    "UPDATE characters SET copper = %s, silver = %s, gold = %s WHERE id = %s",
                    (curr.copper, curr.silver, curr.gold, int(character_id)),
                )

            for material_id, amount in recipe["materials"].items():
                remaining = int(amount)
                rows = connection.execute(
                    """SELECT id, quantity FROM character_items
                       WHERE character_id = %s AND item_id = %s
                       ORDER BY slot_index FOR UPDATE""",
                    (int(character_id), int(material_id)),
                ).fetchall()
                for row in rows:
                    if remaining <= 0:
                        break
                    taken = min(remaining, int(row["quantity"]))
                    self.items._take_from_row(connection, row, taken)
                    remaining -= taken

            order_id = connection.execute(
                """INSERT INTO forge_orders
                   (world_id, faction, owner_character_id, item_id, recipe_json,
                    duration_seconds, status, queued_at)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s, 'queued', %s)
                   RETURNING id""",
                (
                    world_id, faction, int(character_id), item_id,
                    __import__("json").dumps(recipe["materials"]),
                    int(recipe["duration_sec"]), now,
                ),
            ).fetchone()["id"]
            self._advance_queue(connection, world_id, faction, now)
        return int(order_id)

    def collect_order(self, character_id, order_id, now=None):
        now = time.time() if now is None else float(now)
        faction = DEFAULT_FACTION
        with self.db.connection() as connection:
            world_id = self._world_id(connection, character_id)
            self._lock_queue(connection, world_id, faction)
            lock_character(connection, character_id)
            self._advance_queue(connection, world_id, faction, now)
            order = connection.execute(
                """SELECT id, item_id FROM forge_orders
                   WHERE id = %s AND world_id = %s AND faction = %s
                     AND owner_character_id = %s AND status = 'ready'
                   FOR UPDATE""",
                (int(order_id), world_id, faction, int(character_id)),
            ).fetchone()
            if order is None:
                raise ValueError("Готовый заказ не найден на вашем складе кузницы")
            if not self.items._add_items(connection, character_id, int(order["item_id"]), 1):
                raise ValueError("В рюкзаке нет места для готового предмета")
            connection.execute(
                "UPDATE forge_orders SET status = 'claimed', claimed_at = %s WHERE id = %s",
                (now, int(order_id)),
            )
        return True
