"""
Система предметов и инвентаря
"""

import json
import time
from typing import List, Dict, Optional, Tuple


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
                    item_type TEXT NOT NULL,  -- 'potion', 'material', 'card', 'equipment', etc
                    rarity TEXT NOT NULL,     -- 'common', 'rare', 'epic', 'legendary'
                    weight REAL NOT NULL,     -- вес в кг
                    price INTEGER NOT NULL,   -- цена в золоте
                    description TEXT,         -- описание
                    can_use INTEGER NOT NULL DEFAULT 0,  -- можно ли использовать (зелья, свитки)
                    effects_json TEXT,        -- JSON с эффектами {"type": "mana", "value": 50}
                    bonuses_json TEXT,        -- JSON с бонусами для экипировки {"strength": 2, "hp": 5}
                    icon TEXT,                -- иконка (emoji или путь)
                    created_at REAL NOT NULL
                );

                -- Инвентарь персонажа (рюкзак - носит на себе)
                CREATE TABLE IF NOT EXISTS character_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    slot_index INTEGER,      -- позиция в рюкзаке (0-49)
                    created_at REAL NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id),
                    FOREIGN KEY(item_id) REFERENCES items_catalog(id),
                    UNIQUE(character_id, item_id, slot_index)
                );

                -- Экипировка персонажа (надетое)
                CREATE TABLE IF NOT EXISTS character_equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    slot TEXT NOT NULL,     -- 'head', 'body', 'hands', 'legs', 'feet'
                                            -- 'weapon_main', 'weapon_off', 'ring_1', 'ring_2', 'amulet'
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

                CREATE INDEX IF NOT EXISTS idx_inventory_character
                    ON character_inventory(character_id);

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

    def _initialize_items_catalog(self):
        """Загружает каталог предметов в БД"""
        with self.db.connection() as connection:
            # Проверяем, есть ли уже предметы
            count = connection.execute("SELECT COUNT(*) FROM items_catalog").fetchone()[0]
            if count > 0:
                return

            # Инициализируем базовый каталог предметов
            items = [
                # Зелья (consumables)
                (1, "Зелье маны", "potion", "common", 0.1, 50, "Восстанавливает 50 маны", 1, '{"type": "mana", "value": 50}', None, "🧪", time.time()),
                (2, "Зелье HP", "potion", "common", 0.1, 75, "Восстанавливает 100 HP", 1, '{"type": "hp", "value": 100}', None, "💊", time.time()),
                (3, "Зелье силы", "potion", "rare", 0.15, 200, "Увеличивает Силу на 3 на 5 ходов", 1, '{"type": "buff", "stat": "strength", "value": 3, "duration": 5}', None, "⚔️", time.time()),

                # Материалы (materials)
                (10, "Железная руда", "material", "common", 0.5, 20, "Используется для крафта", 0, None, None, "⛏️", time.time()),
                (11, "Листья травы", "material", "common", 0.05, 15, "Используется для зелий", 0, None, None, "🌿", time.time()),
                (12, "Кость дракона", "material", "epic", 1.0, 500, "Редкий материал для крафта", 0, None, None, "🐉", time.time()),
                (13, "Кристалл маны", "material", "rare", 0.2, 300, "Источник магической энергии", 0, None, None, "💎", time.time()),

                # Оружие (equipment - weapons)
                (20, "Меч железный", "equipment", "common", 2.0, 150, "Увеличивает урон +5", 0, None, '{"damage": 5}', "⚔️", time.time()),
                (21, "Меч стальной", "equipment", "rare", 1.8, 350, "Увеличивает урон +10", 0, None, '{"damage": 10}', "🗡️", time.time()),
                (22, "Кинжал", "equipment", "common", 1.0, 100, "Увеличивает урон +3, +1 Ловкость", 0, None, '{"damage": 3, "agility": 1}', "🔪", time.time()),

                # Броня (equipment - armor)
                (30, "Доспехи кожаные", "equipment", "common", 3.0, 200, "Увеличивает HP +5, +1 Ловкость", 0, None, '{"hp": 5, "agility": 1}', "🛡️", time.time()),
                (31, "Доспехи боевые", "equipment", "rare", 5.0, 400, "Увеличивает HP +10, +2 Выносливость", 0, None, '{"hp": 10, "endurance": 2}', "🛡️", time.time()),
                (32, "Корона железная", "equipment", "rare", 1.5, 300, "Увеличивает HP +5, +2 Сила", 0, None, '{"hp": 5, "strength": 2}', "👑", time.time()),

                # Аксессуары (equipment - accessories)
                (40, "Кольцо силы", "equipment", "rare", 0.05, 250, "Увеличивает Силу +1", 0, None, '{"strength": 1}', "💍", time.time()),
                (41, "Амулет защиты", "equipment", "common", 0.1, 150, "Увеличивает HP +2", 0, None, '{"hp": 2}', "⭐", time.time()),

                # Свитки (consumables)
                (50, "Свиток огня", "scroll", "rare", 0.2, 200, "Наносит урон огнём в боевой колоде", 1, '{"type": "damage", "value": 30}', None, "📜", time.time()),
                (51, "Свиток защиты", "scroll", "common", 0.15, 100, "Даёт щит в боевой колоде", 0, None, None, "📜", time.time()),
            ]

            connection.executemany(
                """
                INSERT INTO items_catalog
                (id, name, item_type, rarity, weight, price, description, can_use, effects_json, bonuses_json, icon, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                items
            )

    # ==================== ИНВЕНТАРЬ (рюкзак) ====================

    def add_to_inventory(self, character_id: int, item_id: int, quantity: int = 1) -> bool:
        """Добавляет предмет в рюкзак"""
        with self.db.connection() as connection:
            # Проверяем, есть ли уже такой предмет
            row = connection.execute(
                "SELECT id, quantity FROM character_inventory WHERE character_id = ? AND item_id = ?",
                (character_id, item_id)
            ).fetchone()

            if row:
                # Увеличиваем количество
                new_quantity = row["quantity"] + quantity
                connection.execute(
                    "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                    (new_quantity, row["id"])
                )
            else:
                # Ищем свободную ячейку
                slot = connection.execute(
                    "SELECT COUNT(*) FROM character_inventory WHERE character_id = ?",
                    (character_id,)
                ).fetchone()[0]

                if slot >= 50:  # Максимум 50 ячеек
                    return False

                connection.execute(
                    "INSERT INTO character_inventory (character_id, item_id, quantity, slot_index, created_at) VALUES (?, ?, ?, ?, ?)",
                    (character_id, item_id, quantity, slot, time.time())
                )

            return True

    def remove_from_inventory(self, character_id: int, item_id: int, quantity: int = 1) -> bool:
        """Удаляет предмет из рюкзака"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT id, quantity FROM character_inventory WHERE character_id = ? AND item_id = ?",
                (character_id, item_id)
            ).fetchone()

            if not row:
                return False

            new_quantity = row["quantity"] - quantity
            if new_quantity <= 0:
                connection.execute("DELETE FROM character_inventory WHERE id = ?", (row["id"],))
            else:
                connection.execute(
                    "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                    (new_quantity, row["id"])
                )

            return True

    def get_inventory(self, character_id: int) -> List[Dict]:
        """Получает весь инвентарь персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                """
                SELECT i.id, i.character_id, i.item_id, i.quantity, i.slot_index,
                       c.name, c.item_type, c.rarity, c.weight, c.price, c.description, c.icon, c.can_use
                FROM character_inventory i
                JOIN items_catalog c ON i.item_id = c.id
                WHERE i.character_id = ?
                ORDER BY i.slot_index
                """,
                (character_id,)
            ).fetchall()

            return [dict(row) for row in rows]

    # ==================== ЭКИПИРОВКА ====================

    def equip_item(self, character_id: int, slot: str, item_id: int) -> bool:
        """Надевает предмет на персонажа"""
        with self.db.connection() as connection:
            # Проверяем, есть ли такой предмет
            item = connection.execute(
                "SELECT * FROM items_catalog WHERE id = ?",
                (item_id,)
            ).fetchone()

            if not item or item["item_type"] != "equipment":
                return False

            # Удаляем старый предмет со слота
            connection.execute(
                "DELETE FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot)
            )

            # Надеваем новый
            connection.execute(
                """
                INSERT INTO character_equipment (character_id, slot, item_id, equipped_at)
                VALUES (?, ?, ?, ?)
                """,
                (character_id, slot, item_id, time.time())
            )

            # Удаляем из инвентаря
            self.remove_from_inventory(character_id, item_id, 1)

            return True

    def unequip_item(self, character_id: int, slot: str) -> bool:
        """Снимает предмет с персонажа"""
        with self.db.connection() as connection:
            # Получаем надетый предмет
            row = connection.execute(
                "SELECT item_id FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot)
            ).fetchone()

            if not row:
                return False

            item_id = row["item_id"]

            # Удаляем экипировку
            connection.execute(
                "DELETE FROM character_equipment WHERE character_id = ? AND slot = ?",
                (character_id, slot)
            )

            # Добавляем в инвентарь
            self.add_to_inventory(character_id, item_id, 1)

            return True

    def get_equipment(self, character_id: int) -> Dict[str, Dict]:
        """Получает экипировку персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                """
                SELECT e.slot, e.item_id, c.name, c.rarity, c.bonuses_json, c.icon
                FROM character_equipment e
                JOIN items_catalog c ON e.item_id = c.id
                WHERE e.character_id = ?
                """,
                (character_id,)
            ).fetchall()

            result = {}
            for row in rows:
                bonuses = json.loads(row["bonuses_json"] or "{}")
                result[row["slot"]] = {
                    "item_id": row["item_id"],
                    "name": row["name"],
                    "rarity": row["rarity"],
                    "bonuses": bonuses,
                    "icon": row["icon"]
                }

            return result

    def get_stat_bonuses(self, character_id: int) -> Dict[str, int]:
        """Получает все бонусы к статам от экипировки"""
        equipment = self.get_equipment(character_id)
        bonuses = {}

        for slot_data in equipment.values():
            for stat, value in slot_data["bonuses"].items():
                bonuses[stat] = bonuses.get(stat, 0) + value

        return bonuses

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
        """Забирает добычу в инвентарь"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT item_id, quantity FROM battle_rewards WHERE id = ? AND character_id = ? AND claimed = 0",
                (reward_id, character_id)
            ).fetchone()

            if not row:
                return False

            # Добавляем в инвентарь
            self.add_to_inventory(character_id, row["item_id"], row["quantity"])

            # Отмечаем как забранную
            connection.execute(
                "UPDATE battle_rewards SET claimed = 1, claimed_at = ? WHERE id = ?",
                (time.time(), reward_id)
            )

            return True
