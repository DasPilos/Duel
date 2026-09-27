"""
Система предметов и инвентаря
"""

import json
import time
from typing import List, Dict, Optional


BACKPACK_SIZE = 50
MAX_STACK = 99

# Слоты куклы персонажа. Ключи совпадают с equip_slot в каталоге.
EQUIPMENT_SLOTS = (
    "head", "ears", "neck", "back", "body", "hands",
    "belt", "legs", "feet", "weapon", "shield", "ring",
)

# Выдаётся один раз при первом открытии рюкзака: (item_id, количество)
STARTER_KIT = (
    (20, 1),   # Железный меч
    (30, 1),   # Кожаный доспех
    (33, 1),   # Плащ странника
    (37, 1),   # Железные сапоги
    (2, 3),    # Зелье здоровья
    (1, 2),    # Зелье маны
    (10, 5),   # Железная руда
    (11, 3),   # Листья травы
)

# (id, name, item_type, rarity, weight, price, description, can_use, effects, bonuses, icon, equip_slot)
# icon — имя слоя в assets/fighters/equipment/placeholders или ключ процедурной иконки клиента.
CATALOG = (
    # Зелья
    (1, "Зелье маны", "potion", "common", 0.1, 50, "Восстанавливает 50 маны", 1, {"type": "mp", "value": 50}, None, "potion_blue", None),
    (2, "Зелье здоровья", "potion", "common", 0.1, 75, "Восстанавливает 50 здоровья", 1, {"type": "hp", "value": 50}, None, "potion_red", None),
    (3, "Зелье силы", "potion", "rare", 0.15, 200, "Сила +3 на 5 ходов. Действует только в бою", 0, {"type": "buff", "stat": "strength", "value": 3, "duration": 5}, None, "potion_orange", None),

    # Материалы
    (10, "Железная руда", "material", "common", 0.5, 20, "Используется для крафта", 0, None, None, "ore", None),
    (11, "Листья травы", "material", "common", 0.05, 15, "Используется для зелий", 0, None, None, "herb", None),
    (12, "Кость дракона", "material", "epic", 1.0, 500, "Редкий материал для крафта", 0, None, None, "bone", None),
    (13, "Кристалл маны", "material", "rare", 0.2, 300, "Источник магической энергии", 0, None, None, "crystal", None),

    # Оружие и щиты
    (20, "Железный меч", "equipment", "common", 2.0, 150, "Простой, но надёжный клинок", 0, None, {"strength": 1}, "right_hand_steel_sword", "weapon"),
    (21, "Стальной меч", "equipment", "rare", 1.8, 350, "Клинок из закалённой стали", 0, None, {"strength": 2, "intuition": 1}, "right_hand_steel_sword", "weapon"),
    (22, "Кинжал", "equipment", "common", 1.0, 100, "Лёгкое оружие для быстрых ударов", 0, None, {"agility": 1}, "right_hand_steel_sword", "weapon"),
    (38, "Круглый щит", "equipment", "common", 3.5, 180, "Деревянный щит с железной оковкой", 0, None, {"endurance": 2}, "left_hand_round_shield", "shield"),

    # Броня
    (30, "Кожаный доспех", "equipment", "common", 3.0, 200, "Не сковывает движений", 0, None, {"agility": 1}, "body_steel_breastplate", "body"),
    (31, "Боевой доспех", "equipment", "rare", 5.0, 400, "Тяжёлая стальная кираса", 0, None, {"endurance": 2}, "body_steel_breastplate", "body"),
    (32, "Железный шлем", "equipment", "rare", 1.5, 300, "Защищает голову от ударов", 0, None, {"endurance": 1, "strength": 1}, "head_iron_helmet", "head"),
    (33, "Плащ странника", "equipment", "common", 1.0, 120, "Спасает от ветра и чужих взглядов", 0, None, {"agility": 1}, "back_blue_cloak", "back"),
    (34, "Бронзовый пояс", "equipment", "common", 0.5, 90, "Широкий пояс с бронзовой пряжкой", 0, None, {"endurance": 1}, "belt_bronze_belt", "belt"),
    (35, "Стальные рукавицы", "equipment", "common", 1.2, 140, "Крепкая хватка для рукояти", 0, None, {"strength": 1}, "hands_steel_gauntlets", "hands"),
    (36, "Стальные поножи", "equipment", "common", 2.5, 160, "Защищают ноги в ближнем бою", 0, None, {"endurance": 1}, "legs_steel_greaves", "legs"),
    (37, "Железные сапоги", "equipment", "common", 1.8, 110, "Тяжёлые, зато надёжные", 0, None, {"agility": 1}, "feet_iron_boots", "feet"),

    # Аксессуары
    (40, "Кольцо силы", "equipment", "rare", 0.05, 250, "Золотое кольцо с руной силы", 0, None, {"strength": 1}, "rings_gold_rings", "ring"),
    (41, "Амулет защиты", "equipment", "common", 0.1, 150, "Сапфир на серебряной цепочке", 0, None, {"endurance": 1}, "neck_sapphire_pendant", "neck"),
    (42, "Золотые серьги", "equipment", "rare", 0.05, 220, "Обостряют чутьё владельца", 0, None, {"intuition": 1}, "ears_gold_earrings", "ears"),

    # Свитки
    (50, "Свиток огня", "scroll", "rare", 0.2, 200, "Наносит урон огнём. Действует только в бою", 0, {"type": "damage", "value": 30}, None, "scroll", None),
    (51, "Свиток защиты", "scroll", "common", 0.15, 100, "Даёт щит. Действует только в бою", 0, None, None, "scroll", None),
)

_ITEM_COLUMNS = """c.name, c.item_type, c.rarity, c.weight, c.price, c.description,
                   c.can_use, c.effects_json, c.bonuses_json, c.icon, c.equip_slot"""


def _item_payload(row) -> Dict:
    item = dict(row)
    item["effects"] = json.loads(item.pop("effects_json", None) or "{}")
    item["bonuses"] = json.loads(item.pop("bonuses_json", None) or "{}")
    return item


class ItemsDatabase:
    """Управляет предметами, инвентарём и экипировкой персонажа"""

    def __init__(self, database):
        """
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.db = database
        self._initialize_tables()
        self._initialize_items_catalog()

    def _initialize_tables(self):
        """Создаёт таблицы для системы предметов"""
        with self.db.connection() as connection:
            connection.executescript(
                """
                -- Каталог предметов (статические данные)
                CREATE TABLE IF NOT EXISTS items_catalog (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    item_type TEXT NOT NULL,  -- 'potion', 'material', 'equipment', 'scroll'
                    rarity TEXT NOT NULL,     -- 'common', 'rare', 'epic', 'legendary'
                    weight REAL NOT NULL,     -- вес в кг
                    price INTEGER NOT NULL,   -- цена в золоте
                    description TEXT,         -- описание
                    can_use INTEGER NOT NULL DEFAULT 0,  -- можно ли использовать вне боя
                    effects_json TEXT,        -- JSON с эффектами {"type": "mp", "value": 50}
                    bonuses_json TEXT,        -- JSON с бонусами для экипировки {"strength": 2}
                    icon TEXT,                -- ключ иконки
                    created_at REAL NOT NULL
                );

                -- Рюкзак персонажа. Таблица character_inventory занята старой системой напитков.
                CREATE TABLE IF NOT EXISTS character_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    slot_index INTEGER NOT NULL,  -- позиция в рюкзаке (0-49)
                    created_at REAL NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id),
                    FOREIGN KEY(item_id) REFERENCES items_catalog(id),
                    UNIQUE(character_id, slot_index)
                );

                -- Разовые выдачи (стартовый набор)
                CREATE TABLE IF NOT EXISTS character_item_grants (
                    character_id INTEGER PRIMARY KEY,
                    starter_kit_at REAL NOT NULL
                );

                -- Экипировка персонажа (надетое)
                CREATE TABLE IF NOT EXISTS character_equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    slot TEXT NOT NULL,     -- см. EQUIPMENT_SLOTS
                    item_id INTEGER NOT NULL,
                    equipped_at REAL NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id),
                    FOREIGN KEY(item_id) REFERENCES items_catalog(id),
                    UNIQUE(character_id, slot)
                );

                -- Хранилище персонажа (в сундуках)
                CREATE TABLE IF NOT EXISTS character_storage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    storage_type TEXT NOT NULL,  -- 'chest1', 'chest2', etc
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    slot_index INTEGER,          -- позиция в сундуке
                    created_at REAL NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id),
                    FOREIGN KEY(item_id) REFERENCES items_catalog(id),
                    UNIQUE(character_id, storage_type, item_id, slot_index)
                );

                -- Боевые колоды
                CREATE TABLE IF NOT EXISTS character_decks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    cards_json TEXT NOT NULL,   -- JSON список карт с количеством
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id)
                );

                -- Боевые события (добыча после боя)
                CREATE TABLE IF NOT EXISTS battle_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    battle_id INTEGER,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    claimed INTEGER NOT NULL DEFAULT 0,  -- забрана ли добыча
                    created_at REAL NOT NULL,
                    claimed_at REAL,
                    FOREIGN KEY(character_id) REFERENCES characters(id),
                    FOREIGN KEY(item_id) REFERENCES items_catalog(id)
                );

                CREATE INDEX IF NOT EXISTS idx_items_character
                    ON character_items(character_id);

                CREATE INDEX IF NOT EXISTS idx_equipment_character
                    ON character_equipment(character_id);

                CREATE INDEX IF NOT EXISTS idx_storage_character
                    ON character_storage(character_id);

                CREATE INDEX IF NOT EXISTS idx_decks_character
                    ON character_decks(character_id);

                CREATE INDEX IF NOT EXISTS idx_rewards_character
                    ON battle_rewards(character_id);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(items_catalog)").fetchall()}
            if "equip_slot" not in columns:
                connection.execute("ALTER TABLE items_catalog ADD COLUMN equip_slot TEXT")

    def _initialize_items_catalog(self):
        """Синхронизирует каталог предметов с CATALOG (добавляет новые, обновляет старые)"""
        now = time.time()
        rows = [
            (
                item_id, name, item_type, rarity, weight, price, description, can_use,
                json.dumps(effects, ensure_ascii=False) if effects else None,
                json.dumps(bonuses, ensure_ascii=False) if bonuses else None,
                icon, equip_slot, now,
            )
            for item_id, name, item_type, rarity, weight, price, description, can_use, effects, bonuses, icon, equip_slot
            in CATALOG
        ]
        with self.db.connection() as connection:
            connection.executemany(
                """
                INSERT INTO items_catalog
                (id, name, item_type, rarity, weight, price, description, can_use,
                 effects_json, bonuses_json, icon, equip_slot, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, item_type = excluded.item_type, rarity = excluded.rarity,
                    weight = excluded.weight, price = excluded.price, description = excluded.description,
                    can_use = excluded.can_use, effects_json = excluded.effects_json,
                    bonuses_json = excluded.bonuses_json, icon = excluded.icon, equip_slot = excluded.equip_slot
                """,
                rows,
            )

    # ==================== ИНВЕНТАРЬ (рюкзак) ====================

    @staticmethod
    def _check_slot(slot_index) -> int:
        slot_index = int(slot_index)
        if not 0 <= slot_index < BACKPACK_SIZE:
            raise ValueError("Неверная ячейка рюкзака")
        return slot_index

    @staticmethod
    def _catalog_item(connection, item_id):
        return connection.execute("SELECT * FROM items_catalog WHERE id = ?", (item_id,)).fetchone()

    @staticmethod
    def _slot_row(connection, character_id, slot_index):
        return connection.execute(
            "SELECT * FROM character_items WHERE character_id = ? AND slot_index = ?",
            (character_id, slot_index),
        ).fetchone()

    @staticmethod
    def _free_slots(connection, character_id) -> List[int]:
        used = {
            row["slot_index"]
            for row in connection.execute(
                "SELECT slot_index FROM character_items WHERE character_id = ?",
                (character_id,),
            ).fetchall()
        }
        return [index for index in range(BACKPACK_SIZE) if index not in used]

    def _add_items(self, connection, character_id: int, item_id: int, quantity: int) -> bool:
        """Кладёт предметы в рюкзак: сначала докладывает в стопки, затем занимает свободные ячейки.
        Ничего не меняет и возвращает False, если места не хватает."""
        item = self._catalog_item(connection, item_id)
        if item is None or quantity <= 0:
            return False
        stack_limit = 1 if item["item_type"] == "equipment" else MAX_STACK

        stacks = connection.execute(
            """SELECT id, quantity FROM character_items
               WHERE character_id = ? AND item_id = ? AND quantity < ?
               ORDER BY slot_index""",
            (character_id, item_id, stack_limit),
        ).fetchall()
        room_in_stacks = sum(stack_limit - row["quantity"] for row in stacks)
        free_slots = self._free_slots(connection, character_id)
        slots_needed = -(-max(0, quantity - room_in_stacks) // stack_limit)
        if slots_needed > len(free_slots):
            return False

        remaining = quantity
        for row in stacks:
            added = min(stack_limit - row["quantity"], remaining)
            connection.execute(
                "UPDATE character_items SET quantity = quantity + ? WHERE id = ?",
                (added, row["id"]),
            )
            remaining -= added
        now = time.time()
        for slot_index in free_slots[:slots_needed]:
            added = min(stack_limit, remaining)
            connection.execute(
                """INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (character_id, item_id, added, slot_index, now),
            )
            remaining -= added
        return True

    def add_to_inventory(self, character_id: int, item_id: int, quantity: int = 1) -> bool:
        """Добавляет предмет в рюкзак"""
        with self.db.connection() as connection:
            return self._add_items(connection, character_id, item_id, quantity)

    def remove_from_inventory(self, character_id: int, item_id: int, quantity: int = 1) -> bool:
        """Удаляет предметы из рюкзака (из любых стопок). False, если столько нет."""
        with self.db.connection() as connection:
            rows = connection.execute(
                """SELECT id, quantity FROM character_items
                   WHERE character_id = ? AND item_id = ? ORDER BY slot_index DESC""",
                (character_id, item_id),
            ).fetchall()
            if sum(row["quantity"] for row in rows) < quantity:
                return False
            remaining = quantity
            for row in rows:
                if remaining <= 0:
                    break
                taken = min(row["quantity"], remaining)
                self._take_from_row(connection, row, taken)
                remaining -= taken
            return True

    @staticmethod
    def _take_from_row(connection, row, quantity):
        if row["quantity"] <= quantity:
            connection.execute("DELETE FROM character_items WHERE id = ?", (row["id"],))
        else:
            connection.execute(
                "UPDATE character_items SET quantity = quantity - ? WHERE id = ?",
                (quantity, row["id"]),
            )

    def drop_from_slot(self, character_id: int, slot_index: int, quantity: Optional[int] = None) -> bool:
        """Выбрасывает предмет из ячейки. quantity=None — всю стопку."""
        slot_index = self._check_slot(slot_index)
        with self.db.connection() as connection:
            row = self._slot_row(connection, character_id, slot_index)
            if row is None:
                raise ValueError("Ячейка пуста")
            self._take_from_row(connection, row, row["quantity"] if quantity is None else int(quantity))
            return True

    def move_item(self, character_id: int, from_slot: int, to_slot: int) -> bool:
        """Перемещает предмет между ячейками: в пустую, в стопку того же предмета или меняет местами"""
        from_slot = self._check_slot(from_slot)
        to_slot = self._check_slot(to_slot)
        if from_slot == to_slot:
            return True
        with self.db.connection() as connection:
            source = self._slot_row(connection, character_id, from_slot)
            if source is None:
                raise ValueError("Ячейка пуста")
            target = self._slot_row(connection, character_id, to_slot)

            if target is None:
                connection.execute("UPDATE character_items SET slot_index = ? WHERE id = ?", (to_slot, source["id"]))
                return True

            item = self._catalog_item(connection, source["item_id"])
            if target["item_id"] == source["item_id"] and item["item_type"] != "equipment" and target["quantity"] < MAX_STACK:
                moved = min(MAX_STACK - target["quantity"], source["quantity"])
                connection.execute("UPDATE character_items SET quantity = quantity + ? WHERE id = ?", (moved, target["id"]))
                self._take_from_row(connection, source, moved)
                return True

            # Обмен местами: временно уводим источник с ячейки, чтобы не нарушить UNIQUE
            connection.execute("UPDATE character_items SET slot_index = -1 WHERE id = ?", (source["id"],))
            connection.execute("UPDATE character_items SET slot_index = ? WHERE id = ?", (from_slot, target["id"]))
            connection.execute("UPDATE character_items SET slot_index = ? WHERE id = ?", (to_slot, source["id"]))
            return True

    def get_inventory(self, character_id: int) -> List[Dict]:
        """Получает весь рюкзак персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT i.id, i.item_id, i.quantity, i.slot_index, {_ITEM_COLUMNS}
                FROM character_items i
                JOIN items_catalog c ON i.item_id = c.id
                WHERE i.character_id = ?
                ORDER BY i.slot_index
                """,
                (character_id,)
            ).fetchall()
            return [_item_payload(row) for row in rows]

    def ensure_starter_kit(self, character_id: int) -> bool:
        """Выдаёт стартовый набор, если персонаж его ещё не получал"""
        with self.db.connection() as connection:
            granted = connection.execute(
                "SELECT 1 FROM character_item_grants WHERE character_id = ?",
                (character_id,),
            ).fetchone()
            if granted:
                return False
            for item_id, quantity in STARTER_KIT:
                self._add_items(connection, character_id, item_id, quantity)
            connection.execute(
                "INSERT INTO character_item_grants (character_id, starter_kit_at) VALUES (?, ?)",
                (character_id, time.time()),
            )
            return True

    def get_inventory_state(self, character_id: int) -> Dict:
        """Всё, что нужно окну инвентаря: рюкзак, экипировка и суммарные бонусы"""
        return {
            "inventory": self.get_inventory(character_id),
            "equipment": self.get_equipment(character_id),
            "bonuses": self.get_stat_bonuses(character_id),
            "capacity": BACKPACK_SIZE,
        }

    def use_item(self, user_id: int, character_id: int, slot_index: int) -> Dict:
        """Использует предмет из ячейки (зелья) и возвращает обновлённого персонажа"""
        slot_index = self._check_slot(slot_index)
        with self.db.connection() as connection:
            row = connection.execute(
                f"""SELECT i.id, i.quantity, {_ITEM_COLUMNS}
                    FROM character_items i JOIN items_catalog c ON c.id = i.item_id
                    WHERE i.character_id = ? AND i.slot_index = ?""",
                (character_id, slot_index),
            ).fetchone()
        if row is None:
            raise ValueError("Ячейка пуста")
        if not row["can_use"]:
            raise ValueError("Этот предмет нельзя использовать здесь")

        effects = json.loads(row["effects_json"] or "{}")
        character = self.db.get_character(user_id, character_id)
        if character is None:
            raise ValueError("Персонаж не найден")
        stat, limit = {"hp": ("hp", "max_hp"), "mp": ("mp", "max_mp")}.get(effects.get("type"), (None, None))
        if stat is None:
            raise ValueError("Этот предмет нельзя использовать здесь")
        if character[stat] >= character[limit]:
            raise ValueError("Здоровье и так полное" if stat == "hp" else "Мана и так полная")

        character[stat] = min(character[limit], character[stat] + int(effects.get("value", 0)))
        self.db.save_character(user_id, character_id, character)
        with self.db.connection() as connection:
            self._take_from_row(connection, row, 1)
        return self.db.get_character(user_id, character_id)

    # ==================== ЭКИПИРОВКА ====================

    def equip_item(self, character_id: int, slot_index: int, slot: Optional[str] = None) -> bool:
        """Надевает предмет из ячейки рюкзака. Надетый ранее предмет занимает освободившуюся ячейку."""
        slot_index = self._check_slot(slot_index)
        with self.db.connection() as connection:
            row = self._slot_row(connection, character_id, slot_index)
            if row is None:
                raise ValueError("Ячейка пуста")
            item = self._catalog_item(connection, row["item_id"])
            if item["item_type"] != "equipment" or item["equip_slot"] not in EQUIPMENT_SLOTS:
                raise ValueError("Этот предмет нельзя надеть")
            if slot is not None and slot != item["equip_slot"]:
                raise ValueError("Предмет не подходит для этого слота")
            slot = item["equip_slot"]

            previous = connection.execute(
                "SELECT item_id FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot),
            ).fetchone()
            self._take_from_row(connection, row, 1)
            connection.execute(
                "DELETE FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot),
            )
            connection.execute(
                "INSERT INTO character_equipment (character_id, slot, item_id, equipped_at) VALUES (?, ?, ?, ?)",
                (character_id, slot, item["id"], time.time()),
            )
            if previous is not None:
                target = slot_index if self._slot_row(connection, character_id, slot_index) is None else None
                if target is None:
                    free = self._free_slots(connection, character_id)
                    if not free:
                        raise ValueError("Рюкзак полон")
                    target = free[0]
                connection.execute(
                    """INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                       VALUES (?, ?, 1, ?, ?)""",
                    (character_id, previous["item_id"], target, time.time()),
                )
            return True

    def unequip_item(self, character_id: int, slot: str, target_slot: Optional[int] = None) -> bool:
        """Снимает предмет в рюкзак: в указанную ячейку (если свободна) или в первую свободную"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT item_id FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot)
            ).fetchone()
            if row is None:
                raise ValueError("Слот пуст")

            free = self._free_slots(connection, character_id)
            if target_slot is not None and self._check_slot(target_slot) in free:
                target = int(target_slot)
            elif free:
                target = free[0]
            else:
                raise ValueError("Рюкзак полон")

            connection.execute(
                "DELETE FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot)
            )
            connection.execute(
                """INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                   VALUES (?, ?, 1, ?, ?)""",
                (character_id, row["item_id"], target, time.time()),
            )
            return True

    def get_equipment(self, character_id: int) -> Dict[str, Dict]:
        """Получает экипировку персонажа: {slot: предмет}"""
        with self.db.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT e.slot, e.item_id, {_ITEM_COLUMNS}
                FROM character_equipment e
                JOIN items_catalog c ON e.item_id = c.id
                WHERE e.character_id = ?
                """,
                (character_id,)
            ).fetchall()
            return {row["slot"]: _item_payload(row) for row in rows}

    def get_stat_bonuses(self, character_id: int) -> Dict[str, int]:
        """Получает все бонусы к статам от экипировки"""
        with self.db.connection() as connection:
            return self.db.equipment_bonuses(connection, character_id)

    # ==================== ХРАНИЛИЩЕ (сундуки) ====================

    def add_to_storage(self, character_id: int, storage_type: str, item_id: int, quantity: int = 1) -> bool:
        """Добавляет предмет в сундук"""
        with self.db.connection() as connection:
            # Проверяем, есть ли уже такой предмет в сундуке
            row = connection.execute(
                "SELECT id, quantity FROM character_storage WHERE character_id = ? AND storage_type = ? AND item_id = ?",
                (character_id, storage_type, item_id)
            ).fetchone()

            if row:
                new_quantity = row["quantity"] + quantity
                connection.execute(
                    "UPDATE character_storage SET quantity = ? WHERE id = ?",
                    (new_quantity, row["id"])
                )
            else:
                # Ищем свободную ячейку
                slot = connection.execute(
                    "SELECT COUNT(*) FROM character_storage WHERE character_id = ? AND storage_type = ?",
                    (character_id, storage_type)
                ).fetchone()[0]

                if slot >= 100:  # Максимум 100 ячеек в сундуке
                    return False

                connection.execute(
                    """
                    INSERT INTO character_storage (character_id, storage_type, item_id, quantity, slot_index, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (character_id, storage_type, item_id, quantity, slot, time.time())
                )

            return True

    def remove_from_storage(self, character_id: int, storage_type: str, item_id: int, quantity: int = 1) -> bool:
        """Удаляет предмет из сундука"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT id, quantity FROM character_storage WHERE character_id = ? AND storage_type = ? AND item_id = ?",
                (character_id, storage_type, item_id)
            ).fetchone()

            if not row:
                return False

            new_quantity = row["quantity"] - quantity
            if new_quantity <= 0:
                connection.execute("DELETE FROM character_storage WHERE id = ?", (row["id"],))
            else:
                connection.execute(
                    "UPDATE character_storage SET quantity = ? WHERE id = ?",
                    (new_quantity, row["id"])
                )

            return True

    def get_storage(self, character_id: int, storage_type: str) -> List[Dict]:
        """Получает содержимое сундука"""
        with self.db.connection() as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.character_id, s.item_id, s.quantity, s.slot_index,
                       c.name, c.item_type, c.rarity, c.weight, c.price, c.icon
                FROM character_storage s
                JOIN items_catalog c ON s.item_id = c.id
                WHERE s.character_id = ? AND s.storage_type = ?
                ORDER BY s.slot_index
                """,
                (character_id, storage_type)
            ).fetchall()

            return [dict(row) for row in rows]

    # ==================== БОЕВЫЕ КОЛОДЫ ====================

    def create_deck(self, character_id: int, name: str, cards: Dict[int, int]) -> int:
        """Создаёт новую боевую колоду"""
        with self.db.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO character_decks (character_id, name, cards_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (character_id, name, json.dumps(cards), time.time(), time.time())
            )
            return cursor.lastrowid

    def get_deck(self, deck_id: int) -> Optional[Dict]:
        """Получает информацию о колоде"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM character_decks WHERE id = ?",
                (deck_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "is_active": row["is_active"],
                "cards": json.loads(row["cards_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }

    def get_decks(self, character_id: int) -> List[Dict]:
        """Получает все колоды персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, is_active, cards_json, created_at FROM character_decks WHERE character_id = ?",
                (character_id,)
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "is_active": row["is_active"],
                    "cards": json.loads(row["cards_json"]),
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def set_active_deck(self, character_id: int, deck_id: int) -> bool:
        """Устанавливает активную колоду"""
        with self.db.connection() as connection:
            # Убираем активность со всех колод
            connection.execute(
                "UPDATE character_decks SET is_active = 0 WHERE character_id = ?",
                (character_id,)
            )

            # Устанавливаем новую активную
            connection.execute(
                "UPDATE character_decks SET is_active = 1 WHERE id = ? AND character_id = ?",
                (deck_id, character_id)
            )

            return True

    def delete_deck(self, character_id: int, deck_id: int) -> bool:
        with self.db.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM character_decks WHERE id = ? AND character_id = ?",
                (deck_id, character_id),
            )
            return cursor.rowcount > 0

    def get_active_deck(self, character_id: int) -> Optional[Dict]:
        """Получает активную колоду персонажа"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM character_decks WHERE character_id = ? AND is_active = 1",
                (character_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "cards": json.loads(row["cards_json"])
            }

    # ==================== ДОБЫЧА ====================

    def add_reward(self, character_id: int, item_id: int, quantity: int, battle_id: Optional[int] = None) -> int:
        """Добавляет награду в список для подтверждения"""
        with self.db.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO battle_rewards (character_id, battle_id, item_id, quantity, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (character_id, battle_id, item_id, quantity, time.time())
            )
            return cursor.lastrowid

    def get_rewards(self, character_id: int, claimed: bool = False) -> List[Dict]:
        """Получает добычу персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                """
                SELECT r.id, r.item_id, r.quantity, r.claimed, r.created_at,
                       c.name, c.rarity, c.icon, c.price
                FROM battle_rewards r
                JOIN items_catalog c ON r.item_id = c.id
                WHERE r.character_id = ? AND r.claimed = ?
                ORDER BY r.created_at DESC
                """,
                (character_id, 1 if claimed else 0)
            ).fetchall()

            return [dict(row) for row in rows]

    def claim_reward(self, reward_id: int, character_id: int) -> bool:
        """Забирает добычу в инвентарь. False, если добычи нет или рюкзак полон."""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT item_id, quantity FROM battle_rewards WHERE id = ? AND character_id = ? AND claimed = 0",
                (reward_id, character_id)
            ).fetchone()

            if not row or not self._add_items(connection, character_id, row["item_id"], row["quantity"]):
                return False

            connection.execute(
                "UPDATE battle_rewards SET claimed = 1, claimed_at = ? WHERE id = ?",
                (time.time(), reward_id)
            )

            return True
