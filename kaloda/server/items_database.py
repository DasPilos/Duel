"""
Система предметов и инвентаря
"""

import json
import time
import uuid
from typing import List, Dict, Optional

from kaloda.currency import format_coins, spend_coins
from kaloda.rewards import roll_dungeon_treasure
from kaloda.server.database import lock_character
from kaloda.combat.card_database import DUNGEON_CARD_KEYS, UNIVERSAL_CARDS, card_to_dict


BACKPACK_SIZE = 50
MAX_STACK = 99
ITEM_STACK_LIMITS = {60: 10}
# Цена товара магазина припасов — это price предмета в каталоге (в монетах)
SUPPLIES_SHOP_ITEM_IDS = (4, 5, 6, 52)
COLLECTION_SLOTS = 60

# Ограничение предметов по классам: архер может брать только эти предметы
ARCHER_ALLOWED_ITEMS = {
    1, 2, 3,          # Зелья
    10, 11, 12, 13,    # Материалы
    20, 21, 22, 24,    # Оружие (мечи, кинжалы, простой лук)
    33, 37,            # Броня (легкая)
    40, 41, 42,        # Аксессуары
    50, 51,            # Свитки
    90, 91, 92, 93,    # Инструменты добычи
}

# Слоты куклы персонажа. Ключи совпадают с equip_slot в каталоге.
EQUIPMENT_SLOTS = (
    "head", "ears", "neck", "back", "body", "hands",
    "belt", "legs", "feet", "weapon", "shield", "ring", "ring_2",
)

# (id, name, item_type, rarity, weight, price, description, can_use, effects, bonuses, icon, equip_slot)
# price — полная стоимость в монетах.
# icon — имя слоя в assets/fighters/equipment/placeholders или ключ процедурной иконки клиента.
CATALOG = (
    # Зелья
    (1, "Зелье маны", "potion", "common", 0.1, 500000, "Восстанавливает 50 маны", 1, {"type": "mp", "value": 50}, None, "potion_blue", None),
    (2, "Зелье здоровья", "potion", "common", 0.1, 750000, "Восстанавливает 50 здоровья", 1, {"type": "hp", "value": 50}, None, "potion_red", None),
    (3, "Зелье силы", "potion", "rare", 0.15, 2000000, "Сила +3 на 5 ходов. Действует только в бою", 0, {"type": "buff", "stat": "strength", "value": 3, "duration": 5}, None, "potion_orange", None),
    (4, "Зелье восстановления здоровья", "potion", "common", 0.1, 15, "Восстанавливает 20 HP в бою", 0, {"type": "battle_hp", "value": 20}, None, "potion_red", None),
    (5, "Зелье восстановления маны", "potion", "common", 0.1, 15, "Восстанавливает 12 маны в бою", 0, {"type": "battle_mp", "value": 12}, None, "potion_blue", None),
    (6, "Метательный кинжал", "potion", "common", 0.1, 5, "Наносит выбранному врагу 9 урона в бою", 0, {"type": "battle_damage", "value": 9}, None, "right_hand_steel_sword", None),

    # Материалы
    (10, "Железная руда", "material", "common", 5.0, 50, "Добывается в карьере и горной местности", 0, None, None, "material_iron_ore", None),
    (11, "Листья травы", "material", "common", 0.05, 15, "Используется для зелий", 0, None, None, "herb", None),
    (12, "Кость дракона", "material", "epic", 1.0, 5000000, "Редкий материал для крафта", 0, None, None, "bone", None),
    (13, "Кристалл маны", "material", "rare", 0.2, 3000000, "Источник магической энергии", 0, None, None, "crystal", None),

    # Базовые материалы мира
    (60, "Древесина", "material", "common", 4.0, 20, "Добывается в поселении лесовиков и в лесу", 0, None, None, "material_wood", None),
    (61, "Доска", "material", "common", 6.0, 80, "Добывается в поселении лесовиков и в лесу", 0, None, None, "material_board", None),
    (62, "Ягода", "material", "common", 2.0, 15, "Добывается в поселении лесовиков и в лесу", 0, None, None, "material_berry", None),
    (63, "Пшеница", "material", "common", 2.0, 10, "Добывается в крестьянском поселении", 0, None, None, "material_wheat", None),
    (64, "Лен", "material", "common", 3.0, 60, "Добывается в крестьянском поселении", 0, None, None, "material_flax", None),
    (65, "Хлопок", "material", "common", 4.0, 200, "Добывается в крестьянском поселении", 0, None, None, "material_cotton", None),
    (66, "Кожа", "material", "common", 3.0, 30, "Добывается на животноводческой ферме", 0, None, None, "material_leather", None),
    (67, "Мясо", "material", "common", 3.0, 20, "Добывается на животноводческой ферме", 0, None, None, "material_meat", None),
    (68, "Уголь", "material", "common", 3.0, 30, "Добывается в шахте и горной местности", 0, None, None, "material_coal", None),
    (69, "Камень", "material", "common", 3.0, 30, "Добывается в карьере и горной местности", 0, None, None, "material_stone", None),
    (71, "Мифриловая руда", "material", "rare", 7.0, 2000, "Добывается в карьере и горной местности", 0, None, None, "material_mithril_ore", None),
    (72, "Обсидиановая порода", "material", "epic", 9.0, 50000, "Добывается в карьере и горной местности", 0, None, None, "material_obsidian_ore", None),
    (80, "Гагат", "material", "common", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_jet", None),
    (81, "Малахит", "material", "common", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_malachite", None),
    (82, "Топаз", "material", "common", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_topaz", None),
    (83, "Гранат", "material", "common", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_garnet", None),
    (84, "Изумруд", "material", "rare", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_emerald", None),
    (85, "Рубин", "material", "rare", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_ruby", None),
    (86, "Сапфир", "material", "rare", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_sapphire", None),
    (87, "Алмаз", "material", "epic", 1.0, 0, "Редкая находка в угольной шахте", 0, None, None, "material_diamond", None),
    (901, "Карта скелета-стража", "material", "rare", 0.0, 0, "Коллекционная карта подземелья", 0, None, None, "card", None),
    (902, "Статуя короля скелетов", "material", "epic", 0.0, 0, "Реликвия. В будущем её можно будет продать или обменять", 0, None, None, "bone", None),
    (903, "Копьё скелета-стража", "material", "rare", 0.0, 0, "Оружие без характеристик; свойства будут добавлены позже", 0, None, None, "right_hand_steel_sword", None),
    (904, "Карта короля скелетов", "material", "epic", 0.0, 0, "Коллекционная карта подземелья", 0, None, None, "card", None),
    (905, "Корона короля скелетов", "material", "epic", 0.0, 0, "Реликвия без характеристик; свойства будут добавлены позже", 0, None, None, "head_iron_helmet", None),
    (906, "Наследие павшего короля", "material", "legendary", 0.0, 0, "Реликвия без характеристик; свойства будут добавлены позже", 0, None, None, "bone", None),

    # Крафтовые материалы
    (73, "Железо", "material", "common", 6.0, 100, "Получается при переплавке железной руды в кузнице", 0, None, None, "material_iron", None),
    (74, "Сталь", "material", "rare", 7.0, 5000, "Получается при переплавке железа в кузнице", 0, None, None, "material_steel", None),
    (75, "Крепкая кожа", "material", "common", 3.0, 5000, "Получается при обработке кожи в мастерской", 0, None, None, "material_tough_leather", None),
    (76, "Толстая кожа", "material", "rare", 5.0, 10000, "Получается из крепкой кожи и ткани в мастерской", 0, None, None, "material_thick_leather", None),
    (77, "Ткань", "material", "common", 2.0, 80, "Получается при обработке льна в мастерской", 0, None, None, "material_cloth", None),
    (78, "Каменный блок", "material", "common", 7.0, 80, "Получается при обработке камня в инженерной палате", 0, None, None, "material_stone_block", None),

    # Оружие и щиты
    (20, "Железный меч", "equipment", "common", 2.0, 1500000, "Простой, но надёжный клинок", 0, {"damage": [5, 7]}, {"strength": 1}, "right_hand_steel_sword", "weapon"),
    (21, "Стальной меч", "equipment", "rare", 1.8, 3500000, "Клинок из закалённой стали", 0, {"damage": [7, 10]}, {"strength": 2, "intuition": 1}, "right_hand_steel_sword", "weapon"),
    (22, "Кинжал", "equipment", "common", 1.0, 1000000, "Лёгкое оружие для быстрых ударов", 0, {"damage": [3, 5]}, {"agility": 1}, "right_hand_steel_sword", "weapon"),
    (23, "Дубина", "equipment", "common", 5.0, 500, "Требование: Сила: 6. HP +20", 0, {"requirements": {"strength": 6}, "damage": [3, 10]}, {"hp": 20}, "weapon_club", "weapon"),
    (24, "Простой лук", "equipment", "common", 1.0, 400, "Требование: Ловкость: 6. Сила +2. Уворот: +5%", 0, {"requirements": {"agility": 6}, "damage": [4, 8], "dodge": 5}, {"strength": 2, "dodge": 5}, "weapon_bow", "weapon"),
    (25, "Деревянный посох", "equipment", "common", 2.0, 500, "Требование: Мудрость: 6, Интеллект: 4. MP +30", 0, {"requirements": {"wisdom": 6, "intellect": 4}, "damage": [1, 4]}, {"mp": 30}, "weapon_staff", "weapon"),
    (38, "Круглый щит", "equipment", "common", 3.5, 1800000, "Деревянный щит с железной оковкой", 0, None, {"endurance": 2}, "left_hand_round_shield", "shield"),
    (39, "Деревянный щит", "equipment", "common", 3.0, 300, "Требование: Сила: 4. HP +20. Блок: +5%", 0, {"requirements": {"strength": 4}, "damage": [0, 0], "block": 5}, {"hp": 20, "block": 5}, "shield_wooden", "shield"),

    # Броня
    (30, "Кожаный доспех", "equipment", "common", 3.0, 2000000, "Не сковывает движений", 0, None, {"agility": 1}, "body_steel_breastplate", "body"),
    (31, "Боевой доспех", "equipment", "rare", 5.0, 4000000, "Тяжёлая стальная кираса", 0, None, {"endurance": 2}, "body_steel_breastplate", "body"),
    (32, "Железный шлем", "equipment", "rare", 1.5, 3000000, "Защищает голову от ударов", 0, None, {"endurance": 1, "strength": 1}, "head_iron_helmet", "head"),
    (33, "Плащ странника", "equipment", "common", 1.0, 1200000, "Спасает от ветра и чужих взглядов", 0, None, {"agility": 1}, "back_blue_cloak", "back"),
    (34, "Бронзовый пояс", "equipment", "common", 0.5, 900000, "Широкий пояс с бронзовой пряжкой", 0, None, {"endurance": 1}, "belt_bronze_belt", "belt"),
    (35, "Стальные рукавицы", "equipment", "common", 1.2, 1400000, "Крепкая хватка для рукояти", 0, None, {"strength": 1}, "hands_steel_gauntlets", "hands"),
    (36, "Стальные поножи", "equipment", "common", 2.5, 1600000, "Защищают ноги в ближнем бою", 0, None, {"endurance": 1}, "legs_steel_greaves", "legs"),
    (37, "Железные сапоги", "equipment", "common", 1.8, 1100000, "Тяжёлые, зато надёжные", 0, None, {"agility": 1}, "feet_iron_boots", "feet"),

    # Аксессуары
    (40, "Кольцо силы", "equipment", "rare", 0.05, 2500000, "Золотое кольцо с руной силы", 0, None, {"strength": 1}, "rings_gold_rings", "ring"),
    (41, "Амулет защиты", "equipment", "common", 0.1, 1500000, "Сапфир на серебряной цепочке", 0, None, {"endurance": 1}, "neck_sapphire_pendant", "neck"),
    (42, "Золотые серьги", "equipment", "rare", 0.05, 2200000, "Обостряют чутьё владельца", 0, None, {"intuition": 1}, "ears_gold_earrings", "ears"),

    # Свитки
    (50, "Свиток огня", "scroll", "rare", 0.2, 2000000, "Наносит урон огнём. Действует только в бою", 0, {"type": "damage", "value": 30}, None, "scroll", None),
    (51, "Свиток защиты", "scroll", "common", 0.15, 1000000, "Даёт щит. Действует только в бою", 0, None, None, "scroll", None),
    (52, "Свиток разрушения магии", "scroll", "rare", 0.2, 60, "Требует 20 маны. Снимает один отрицательный эффект в бою", 0, {"type": "battle_cleanse", "mana_cost": 20}, None, "scroll", None),

    # Базовые инструменты для добычи
    (90, "Старый серп", "equipment", "common", 1.0, 100, "Требование: Сила: 4. Сокращает время добычи пшеницы на 20%", 0, {"requirements": {"strength": 4}, "damage": [1, 1], "harvest_bonus": {"wheat": 20}, "two_handed": True}, None, "tool_sickle", "weapon"),
    (91, "Топор лесоруба", "equipment", "common", 1.0, 100, "Требование: Сила: 4. Сокращает время добычи древесины на 20%", 0, {"requirements": {"strength": 4}, "damage": [1, 1], "harvest_bonus": {"wood": 20}, "two_handed": True}, None, "tool_axe", "weapon"),
    (92, "Кирка", "equipment", "common", 1.0, 100, "Требование: Сила: 4. Сокращает время добычи железа, угля и камня на 20%", 0, {"requirements": {"strength": 4}, "damage": [1, 1], "harvest_bonus": {"iron_ore": 20, "coal": 20, "stone": 20}, "two_handed": True}, None, "tool_pickaxe", "weapon"),
    (93, "Разделочный нож", "equipment", "common", 1.0, 100, "Требование: Сила: 4. Сокращает время добычи кожи и мяса на 20%", 0, {"requirements": {"strength": 4}, "damage": [1, 1], "harvest_bonus": {"leather": 20, "meat": 20}, "two_handed": True}, None, "tool_butcher_knife", "weapon"),
)

BASE_STARTER_EQUIPMENT = (90, 91, 92, 93)

_ITEM_COLUMNS = """c.name, c.item_type, c.rarity, c.weight, c.price, c.description,
                   c.can_use, c.effects_json, c.bonuses_json, c.icon, c.equip_slot"""


def _item_payload(row) -> Dict:
    item = dict(row)
    item["effects"] = json.loads(item.pop("effects_json", None) or "{}")
    item["bonuses"] = json.loads(item.pop("bonuses_json", None) or "{}")
    if "can_use" in item:
        item["can_use"] = bool(item["can_use"])
    return item


def card_price_coins(card) -> int:
    """Полная цена карты в монетах."""
    return int(card.price_coins)


def is_two_handed(item):
    return bool((item or {}).get("effects", {}).get("two_handed"))


def display_equipment_hands(equipment):
    """Add a display-only entry in the other hand for a single stored two-handed item."""
    result = dict(equipment)
    for slot, item in list(equipment.items()):
        if slot not in ("weapon", "shield") or not is_two_handed(item):
            continue
        other_slot = "shield" if slot == "weapon" else "weapon"
        result[other_slot] = {**item, "_two_handed_shadow": True, "_two_handed_source_slot": slot}
    return result


class ItemsDatabase:
    """Управляет предметами, инвентарём и экипировкой персонажа"""

    def __init__(self, database):
        """
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.db = database
        self._initialize_items_catalog()

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
            connection.cursor().executemany(
                """
                INSERT INTO items_catalog
                (id, name, item_type, rarity, weight, price, description, can_use,
                 effects_json, bonuses_json, icon, equip_slot, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, item_type = excluded.item_type, rarity = excluded.rarity,
                    weight = excluded.weight, price = excluded.price, description = excluded.description,
                    can_use = excluded.can_use, effects_json = excluded.effects_json,
                    bonuses_json = excluded.bonuses_json, icon = excluded.icon, equip_slot = excluded.equip_slot
                """,
                rows,
            )

    def list_catalog_items(self) -> List[Dict]:
        """Весь каталог предметов для справочника клиента, по возрастанию id."""
        with self.db.connection() as connection:
            rows = connection.execute(
                f"SELECT c.id, {_ITEM_COLUMNS} FROM items_catalog c ORDER BY c.id"
            ).fetchall()
        return [_item_payload(row) for row in rows]

    def get_catalog_items(self, item_ids) -> Dict[str, Dict]:
        """Предметы каталога по id: {"23": предмет}. Неизвестные id в ответ не попадают."""
        ids = sorted({int(item_id) for item_id in item_ids})
        if not ids:
            return {}
        with self.db.connection() as connection:
            rows = connection.execute(
                f"SELECT c.id, {_ITEM_COLUMNS} FROM items_catalog c WHERE c.id = ANY(%s)",
                (ids,),
            ).fetchall()
        return {str(row["id"]): _item_payload(row) for row in rows}

    def _lock_coins(self, connection, user_id: int, character_id: int) -> int:
        """Блокирует персонажа до конца транзакции и отдаёт его баланс монет."""
        lock_character(connection, character_id)
        row = connection.execute(
            """SELECT coins FROM characters
               WHERE id = %s AND user_id = %s AND world_id = %s
               FOR UPDATE""",
            (character_id, user_id, self.db.world_id),
        ).fetchone()
        if row is None:
            raise ValueError("Персонаж не найден")
        return int(row["coins"])

    def _store_coins(self, connection, user_id: int, character_id: int, coins: int, now: float):
        connection.execute(
            """UPDATE characters SET coins = %s, updated_at = %s
               WHERE id = %s AND user_id = %s AND world_id = %s""",
            (coins, now, character_id, user_id, self.db.world_id),
        )

    def grant_base_equipment(self, character_id: int) -> bool:
        """Give a character the four basic gathering tools once."""
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            granted = connection.execute(
                "SELECT 1 FROM character_item_grants WHERE character_id = %s",
                (character_id,),
            ).fetchone()
            if granted:
                return False
            if len(self._free_slots(connection, character_id)) < len(BASE_STARTER_EQUIPMENT):
                raise ValueError("В рюкзаке недостаточно места для базовых инструментов")
            for item_id in BASE_STARTER_EQUIPMENT:
                if not self._add_items(connection, character_id, item_id, 1):
                    raise ValueError("Не удалось выдать базовые инструменты")
            connection.execute(
                "INSERT INTO character_item_grants (character_id, starter_kit_at) VALUES (%s, %s)",
                (character_id, time.time()),
            )
        return True

    # ==================== ИНВЕНТАРЬ (рюкзак) ====================

    @staticmethod
    def _check_slot(slot_index) -> int:
        slot_index = int(slot_index)
        if not 0 <= slot_index < BACKPACK_SIZE:
            raise ValueError("Неверная ячейка рюкзака")
        return slot_index

    @staticmethod
    def _catalog_item(connection, item_id):
        return connection.execute("SELECT * FROM items_catalog WHERE id = %s", (item_id,)).fetchone()

    @staticmethod
    def _stack_limit(item):
        if item["item_type"] == "equipment":
            return 1
        return ITEM_STACK_LIMITS.get(int(item["id"]), MAX_STACK)

    @staticmethod
    def _slot_row(connection, character_id, slot_index):
        return connection.execute(
            "SELECT * FROM character_items WHERE character_id = %s AND slot_index = %s",
            (character_id, slot_index),
        ).fetchone()

    @staticmethod
    def _free_slots(connection, character_id) -> List[int]:
        used = {
            row["slot_index"]
            for row in connection.execute(
                "SELECT slot_index FROM character_items WHERE character_id = %s",
                (character_id,),
            ).fetchall()
        }
        return [index for index in range(BACKPACK_SIZE) if index not in used]

    @classmethod
    def _add_items(cls, connection, character_id: int, item_id: int, quantity: int) -> bool:
        """Кладёт предметы в рюкзак: сначала докладывает в стопки, затем занимает свободные ячейки.
        Ничего не меняет и возвращает False, если места не хватает."""
        lock_character(connection, character_id)
        item = cls._catalog_item(connection, item_id)
        if item is None or quantity <= 0:
            return False
        stack_limit = cls._stack_limit(item)

        stacks = connection.execute(
            """SELECT id, quantity FROM character_items
               WHERE character_id = %s AND item_id = %s AND quantity < %s
               ORDER BY slot_index""",
            (character_id, item_id, stack_limit),
        ).fetchall()
        room_in_stacks = sum(stack_limit - row["quantity"] for row in stacks)
        free_slots = cls._free_slots(connection, character_id)
        slots_needed = -(-max(0, quantity - room_in_stacks) // stack_limit)
        if slots_needed > len(free_slots):
            return False

        remaining = quantity
        for row in stacks:
            added = min(stack_limit - row["quantity"], remaining)
            connection.execute(
                "UPDATE character_items SET quantity = quantity + %s WHERE id = %s",
                (added, row["id"]),
            )
            remaining -= added
        now = time.time()
        for slot_index in free_slots[:slots_needed]:
            added = min(stack_limit, remaining)
            connection.execute(
                """INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                   VALUES (%s, %s, %s, %s, %s)""",
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
        quantity = int(quantity)
        if quantity <= 0:
            return False
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            rows = connection.execute(
                """SELECT id, quantity FROM character_items
                   WHERE character_id = %s AND item_id = %s ORDER BY slot_index DESC""",
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
            connection.execute("DELETE FROM character_items WHERE id = %s", (row["id"],))
        else:
            connection.execute(
                "UPDATE character_items SET quantity = quantity - %s WHERE id = %s",
                (quantity, row["id"]),
            )

    def drop_from_slot(self, character_id: int, slot_index: int, quantity: Optional[int] = None) -> bool:
        """Выбрасывает предмет из ячейки. quantity=None — всю стопку."""
        slot_index = self._check_slot(slot_index)
        if quantity is not None and int(quantity) <= 0:
            raise ValueError("Некорректное количество")
        with self.db.connection() as connection:
            lock_character(connection, character_id)
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
            lock_character(connection, character_id)
            source = self._slot_row(connection, character_id, from_slot)
            if source is None:
                raise ValueError("Ячейка пуста")
            target = self._slot_row(connection, character_id, to_slot)

            if target is None:
                connection.execute("UPDATE character_items SET slot_index = %s WHERE id = %s", (to_slot, source["id"]))
                return True

            item = self._catalog_item(connection, source["item_id"])
            stack_limit = self._stack_limit(item)
            if target["item_id"] == source["item_id"] and item["item_type"] != "equipment" and target["quantity"] < stack_limit:
                moved = min(stack_limit - target["quantity"], source["quantity"])
                connection.execute("UPDATE character_items SET quantity = quantity + %s WHERE id = %s", (moved, target["id"]))
                self._take_from_row(connection, source, moved)
                return True

            # Обмен местами: временно уводим источник с ячейки, чтобы не нарушить UNIQUE
            connection.execute("UPDATE character_items SET slot_index = -1 WHERE id = %s", (source["id"],))
            connection.execute("UPDATE character_items SET slot_index = %s WHERE id = %s", (from_slot, target["id"]))
            connection.execute("UPDATE character_items SET slot_index = %s WHERE id = %s", (to_slot, source["id"]))
            return True

    def get_inventory(self, character_id: int) -> List[Dict]:
        """Получает весь рюкзак персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT i.id, i.item_id, i.quantity, i.slot_index, {_ITEM_COLUMNS}
                FROM character_items i
                JOIN items_catalog c ON i.item_id = c.id
                WHERE i.character_id = %s
                ORDER BY i.slot_index
                """,
                (character_id,)
            ).fetchall()
            return [_item_payload(row) for row in rows]

    def get_inventory_state(self, character_id: int) -> Dict:
        """Всё, что нужно окну инвентаря: рюкзак, экипировка и суммарные бонусы"""
        inventory = self.get_inventory(character_id)
        equipment = self.get_equipment(character_id)
        return {
            "inventory": inventory,
            "equipment": equipment,
            "bonuses": self.get_stat_bonuses(character_id),
            "capacity": BACKPACK_SIZE,
        }

    def get_supplies_shop_catalog(self) -> List[Dict]:
        """Товары магазина припасов; price — полная цена в монетах."""
        with self.db.connection() as connection:
            rows = connection.execute(
                """SELECT id, name, item_type, rarity, weight, price, description,
                          effects_json, icon
                   FROM items_catalog WHERE id = ANY(%s) ORDER BY id""",
                (list(SUPPLIES_SHOP_ITEM_IDS),),
            ).fetchall()
        return [
            {
                "item_id": row["id"],
                "name": row["name"],
                "item_type": row["item_type"],
                "rarity": row["rarity"],
                "weight": row["weight"],
                "price": int(row["price"]),
                "description": row["description"],
                "effects": json.loads(row["effects_json"] or "{}"),
                "icon": row["icon"],
            }
            for row in rows
        ]

    def buy_supplies_item(self, user_id: int, character_id: int, item_id: int) -> Dict:
        item_id = int(item_id)
        if item_id not in SUPPLIES_SHOP_ITEM_IDS:
            raise ValueError("Этого товара нет в магазине припасов")

        with self.db.connection() as connection:
            coins = self._lock_coins(connection, user_id, character_id)
            item = self._catalog_item(connection, item_id)
            if item is None:
                raise ValueError("Этого товара нет в магазине припасов")
            coins = spend_coins(coins, item["price"])
            if not self._add_items(connection, character_id, item_id, 1):
                raise ValueError("В рюкзаке нет свободного места")
            self._store_coins(connection, user_id, character_id, coins, time.time())

        return {
            "character": self.db.get_character(user_id, character_id),
            "inventory": self.get_inventory_state(character_id),
        }

    @staticmethod
    def _card_shop_entries(cards) -> List[Dict]:
        entries = []
        for card in cards:
            price = card_price_coins(card)
            entries.append({
                **card_to_dict(card),
                "price": price,
                "available": price > 0 and card.rarity != "unassigned",
            })
        return entries

    def get_card_shop_catalog(self) -> List[Dict]:
        return self._card_shop_entries(
            card for card in UNIVERSAL_CARDS if card.key not in DUNGEON_CARD_KEYS
        )

    def get_dungeon_card_shop_catalog(self) -> List[Dict]:
        return self._card_shop_entries(
            card for card in UNIVERSAL_CARDS if card.key in DUNGEON_CARD_KEYS
        )

    def buy_card(self, user_id: int, character_id: int, card_key: str, *, dungeon_shop=False) -> Dict:
        card = next(
            (
                item for item in UNIVERSAL_CARDS
                if item.key == str(card_key)
                and (item.key in DUNGEON_CARD_KEYS) == dungeon_shop
            ),
            None,
        )
        if card is None:
            if str(card_key) in DUNGEON_CARD_KEYS and not dungeon_shop:
                raise ValueError("Эта карта продаётся только в подземелье")
            if dungeon_shop:
                raise ValueError("Этой карты нет у подземного торговца")
            raise ValueError("Этой карты нет в карточной лавке")
        price = card_price_coins(card)
        if price <= 0 or card.rarity == "unassigned":
            raise ValueError("Покупка этой карты временно отключена до назначения цены")
        with self.db.connection() as connection:
            coins = self._lock_coins(connection, user_id, character_id)
            owned = connection.execute(
                """SELECT id, quantity, slot_index FROM character_card_collection
                   WHERE character_id = %s AND card_key = %s""",
                (character_id, card.key),
            ).fetchone()
            coins = spend_coins(coins, price)
            now = time.time()
            if owned is not None:
                connection.execute(
                    """UPDATE character_card_collection
                       SET quantity = quantity + 1, acquired_at = %s WHERE id = %s""",
                    (now, owned["id"]),
                )
            else:
                used_slots = {
                    row["slot_index"]
                    for row in connection.execute(
                        """SELECT slot_index FROM character_card_collection
                           WHERE character_id = %s""",
                        (character_id,),
                    ).fetchall()
                }
                slot_index = next((slot for slot in range(COLLECTION_SLOTS) if slot not in used_slots), None)
                if slot_index is None:
                    raise ValueError("В коллекции нет свободных ячеек")
                connection.execute(
                    """INSERT INTO character_card_collection
                       (character_id, card_key, quantity, slot_index, acquired_at)
                       VALUES (%s, %s, 1, %s, %s)""",
                    (character_id, card.key, slot_index, now),
                )
            self._store_coins(connection, user_id, character_id, coins, now)
        return {
            "character": self.db.get_character(user_id, character_id),
            "card": card_to_dict(card),
        }

    def buy_dungeon_card(self, user_id: int, character_id: int, card_key: str) -> Dict:
        return self.buy_card(user_id, character_id, card_key, dungeon_shop=True)

    def claim_dungeon_treasure(self, user_id: int, character_id: int, request_id: str) -> Dict:
        try:
            request_id = str(uuid.UUID(str(request_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("Неверный идентификатор открытия сундука") from error

        with self.db.connection() as connection:
            coins = self._lock_coins(connection, user_id, character_id)

            claim = connection.execute(
                """SELECT rewards_json FROM character_dungeon_treasure_claims
                   WHERE character_id = %s AND request_id = %s""",
                (character_id, request_id),
            ).fetchone()
            if claim is None:
                rewards = roll_dungeon_treasure()
                for item in rewards["items"]:
                    if not self._add_items(
                        connection,
                        character_id,
                        int(item["item_id"]),
                        int(item["quantity"]),
                    ):
                        raise ValueError("В рюкзаке недостаточно места для наград")
                now = time.time()
                if rewards["coins"]:
                    coins += int(rewards["coins"])
                    self._store_coins(connection, user_id, character_id, coins, now)
                connection.execute(
                    """INSERT INTO character_dungeon_treasure_claims
                       (character_id, request_id, rewards_json, created_at)
                       VALUES (%s, %s, %s, %s)""",
                    (character_id, request_id, json.dumps(rewards, ensure_ascii=False), now),
                )
            else:
                rewards = json.loads(claim["rewards_json"])

        return {
            "character": self.db.get_character(user_id, character_id),
            "inventory": self.get_inventory_state(character_id),
            "rewards": [
                *([format_coins(rewards["coins"])] if rewards["coins"] else []),
                *(
                    f"{item['quantity']} × {item['name']}"
                    for item in rewards["items"]
                ),
            ],
        }

    def use_item(self, user_id: int, character_id: int, slot_index: int) -> Dict:
        """Использует предмет из ячейки (зелья) и возвращает обновлённого персонажа"""
        slot_index = self._check_slot(slot_index)
        # The lock stays held until the potion is taken, so one potion cannot be used twice in parallel.
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                f"""SELECT i.id, i.quantity, {_ITEM_COLUMNS}
                    FROM character_items i JOIN items_catalog c ON c.id = i.item_id
                    WHERE i.character_id = %s AND i.slot_index = %s""",
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
            self._take_from_row(connection, row, 1)
        return self.db.get_character(user_id, character_id)

    # ==================== ЭКИПИРОВКА ====================

    def equip_item(self, character_id: int, slot_index: int, slot: Optional[str] = None) -> bool:
        """Надевает предмет из ячейки рюкзака. Надетый ранее предмет занимает освободившуюся ячейку."""
        slot_index = self._check_slot(slot_index)
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            row = self._slot_row(connection, character_id, slot_index)
            if row is None:
                raise ValueError("Ячейка пуста")
            item = self._catalog_item(connection, row["item_id"])
            if item["item_type"] != "equipment" or item["equip_slot"] not in EQUIPMENT_SLOTS:
                raise ValueError("Этот предмет нельзя надеть")
            effects = json.loads(item["effects_json"] or "{}")
            two_handed = bool(effects.get("two_handed"))
            either_hand = bool(effects.get("either_hand"))
            valid_target = (
                slot is None
                or slot == item["equip_slot"]
                or (item["equip_slot"] == "ring" and slot == "ring_2")
                or (two_handed and slot in ("weapon", "shield"))
                or (either_hand and slot in ("weapon", "shield"))
            )
            if not valid_target:
                raise ValueError("Предмет не подходит для этого слота")
            if slot is None:
                if either_hand:
                    weapon_occ = connection.execute(
                        "SELECT 1 FROM character_equipment WHERE character_id = %s AND slot = 'weapon'",
                        (character_id,),
                    ).fetchone()
                    shield_occ = connection.execute(
                        "SELECT 1 FROM character_equipment WHERE character_id = %s AND slot = 'shield'",
                        (character_id,),
                    ).fetchone()
                    if weapon_occ and not shield_occ:
                        slot = "shield"
                    else:
                        slot = "weapon"
                else:
                    slot = item["equip_slot"]
            if two_handed:
                occupied_hand = connection.execute(
                    """SELECT slot FROM character_equipment
                       WHERE character_id = %s AND slot IN ('weapon', 'shield') LIMIT 1""",
                    (character_id,),
                ).fetchone()
                if occupied_hand:
                    raise ValueError("Чтобы надеть двуручный предмет, освободите обе руки")
                slot = "weapon"
            elif slot in ("weapon", "shield"):
                other_hand = "shield" if slot == "weapon" else "weapon"
                other_item = connection.execute(
                    """SELECT c.effects_json FROM character_equipment e
                       JOIN items_catalog c ON c.id = e.item_id
                       WHERE e.character_id = %s AND e.slot = %s""",
                    (character_id, other_hand),
                ).fetchone()
                if other_item and json.loads(other_item["effects_json"] or "{}").get("two_handed"):
                    raise ValueError("Другая рука занята двуручным предметом")

            # Проверка класса: лучник может брать только разрешённые предметы
            char_row = connection.execute(
                "SELECT type FROM characters WHERE id = %s",
                (character_id,),
            ).fetchone()
            if char_row and char_row["type"] == "archer" and item["id"] not in ARCHER_ALLOWED_ITEMS:
                raise ValueError("Этот предмет недоступен для лучника")

            previous = connection.execute(
                "SELECT item_id FROM character_equipment WHERE character_id = %s AND slot = %s",
                (character_id, slot),
            ).fetchone()
            self._take_from_row(connection, row, 1)
            connection.execute(
                "DELETE FROM character_equipment WHERE character_id = %s AND slot = %s",
                (character_id, slot),
            )
            connection.execute(
                "INSERT INTO character_equipment (character_id, slot, item_id, equipped_at) VALUES (%s, %s, %s, %s)",
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
                       VALUES (%s, %s, 1, %s, %s)""",
                    (character_id, previous["item_id"], target, time.time()),
                )
            return True

    def unequip_item(self, character_id: int, slot: str, target_slot: Optional[int] = None) -> bool:
        """Снимает предмет в рюкзак: в указанную ячейку (если свободна) или в первую свободную"""
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                """SELECT e.item_id, e.slot, c.effects_json FROM character_equipment e
                   JOIN items_catalog c ON c.id = e.item_id
                   WHERE e.character_id = %s AND e.slot = %s""",
                (character_id, slot)
            ).fetchone()
            actual_slot = slot
            if row is None and slot in ("weapon", "shield"):
                other_hand = "shield" if slot == "weapon" else "weapon"
                other_item = connection.execute(
                    """SELECT e.item_id, e.slot, c.effects_json FROM character_equipment e
                       JOIN items_catalog c ON c.id = e.item_id
                       WHERE e.character_id = %s AND e.slot = %s""",
                    (character_id, other_hand),
                ).fetchone()
                if other_item and json.loads(other_item["effects_json"] or "{}").get("two_handed"):
                    row = other_item
                    actual_slot = other_hand
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
                "DELETE FROM character_equipment WHERE character_id = %s AND slot = %s",
                (character_id, actual_slot)
            )
            connection.execute(
                """INSERT INTO character_items (character_id, item_id, quantity, slot_index, created_at)
                   VALUES (%s, %s, 1, %s, %s)""",
                (character_id, row["item_id"], target, time.time()),
            )
            return True

    def get_equipment(self, character_id: int) -> Dict[str, Dict]:
        """Получает экипировку персонажа: {slot: предмет}"""
        with self.db.connection() as connection:
            return self.db.equipped_items(connection, character_id)

    def get_stat_bonuses(self, character_id: int) -> Dict[str, int]:
        """Получает все бонусы к статам от экипировки"""
        with self.db.connection() as connection:
            return self.db.equipment_bonuses(connection, character_id)

    # ==================== ХРАНИЛИЩЕ (сундуки) ====================

    def add_to_storage(self, character_id: int, storage_type: str, item_id: int, quantity: int = 1) -> bool:
        """Добавляет предмет в сундук"""
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            # Проверяем, есть ли уже такой предмет в сундуке
            row = connection.execute(
                "SELECT id, quantity FROM character_storage WHERE character_id = %s AND storage_type = %s AND item_id = %s",
                (character_id, storage_type, item_id)
            ).fetchone()

            if row:
                new_quantity = row["quantity"] + quantity
                connection.execute(
                    "UPDATE character_storage SET quantity = %s WHERE id = %s",
                    (new_quantity, row["id"])
                )
            else:
                # Ищем свободную ячейку
                slot = connection.execute(
                    "SELECT COUNT(*) AS amount FROM character_storage WHERE character_id = %s AND storage_type = %s",
                    (character_id, storage_type)
                ).fetchone()["amount"]

                if slot >= 100:  # Максимум 100 ячеек в сундуке
                    return False

                connection.execute(
                    """
                    INSERT INTO character_storage (character_id, storage_type, item_id, quantity, slot_index, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (character_id, storage_type, item_id, quantity, slot, time.time())
                )

            return True

    def remove_from_storage(self, character_id: int, storage_type: str, item_id: int, quantity: int = 1) -> bool:
        """Удаляет предмет из сундука"""
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            row = connection.execute(
                "SELECT id, quantity FROM character_storage WHERE character_id = %s AND storage_type = %s AND item_id = %s",
                (character_id, storage_type, item_id)
            ).fetchone()

            if not row:
                return False

            new_quantity = row["quantity"] - quantity
            if new_quantity <= 0:
                connection.execute("DELETE FROM character_storage WHERE id = %s", (row["id"],))
            else:
                connection.execute(
                    "UPDATE character_storage SET quantity = %s WHERE id = %s",
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
                WHERE s.character_id = %s AND s.storage_type = %s
                ORDER BY s.slot_index
                """,
                (character_id, storage_type)
            ).fetchall()

            return [dict(row) for row in rows]

    # ==================== БОЕВЫЕ КОЛОДЫ ====================

    @staticmethod
    def _deck_payload(row) -> Dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "is_active": bool(row["is_active"]),
            "cards": json.loads(row["cards_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_deck(self, character_id: int, name: str, cards: Dict[str, int]) -> int:
        """Создаёт новую боевую колоду: {card_key: количество}. Правила колоды проверяет вызывающий."""
        now = time.time()
        with self.db.connection() as connection:
            return connection.execute(
                """
                INSERT INTO character_decks (character_id, name, cards_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (character_id, name, json.dumps(cards), now, now)
            ).fetchone()["id"]

    def get_deck(self, deck_id: int) -> Optional[Dict]:
        """Получает информацию о колоде"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM character_decks WHERE id = %s",
                (deck_id,)
            ).fetchone()
        return self._deck_payload(row) if row else None

    def get_decks(self, character_id: int) -> List[Dict]:
        """Получает все колоды персонажа"""
        with self.db.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM character_decks WHERE character_id = %s ORDER BY id",
                (character_id,)
            ).fetchall()
        return [self._deck_payload(row) for row in rows]

    def set_active_deck(self, character_id: int, deck_id: int) -> bool:
        """Делает колоду активной (единственной). False, если у персонажа нет такой колоды."""
        with self.db.connection() as connection:
            lock_character(connection, character_id)
            deck = connection.execute(
                "SELECT 1 FROM character_decks WHERE id = %s AND character_id = %s",
                (deck_id, character_id),
            ).fetchone()
            if deck is None:
                return False
            connection.execute(
                "UPDATE character_decks SET is_active = CASE WHEN id = %s THEN 1 ELSE 0 END WHERE character_id = %s",
                (deck_id, character_id),
            )
            return True

    def delete_deck(self, character_id: int, deck_id: int) -> bool:
        with self.db.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM character_decks WHERE id = %s AND character_id = %s",
                (deck_id, character_id),
            )
            return cursor.rowcount > 0

    def get_active_deck(self, character_id: int) -> Optional[Dict]:
        """Получает активную колоду персонажа"""
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM character_decks WHERE character_id = %s AND is_active = 1",
                (character_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "cards": json.loads(row["cards_json"])
            }
