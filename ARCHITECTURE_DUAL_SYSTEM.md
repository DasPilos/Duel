# DUEL - Архитектура двойной системы (Воины + Маги)

**Статус:** 🔴 КРИТИЧНО: Разработчик 2 должен понимать эту архитектуру ПЕРЕД началом работы  
**Дата:** 2026-09-02  
**Авторы:** ДА (Оп1) и ОП2 (Система магии)

---

## 🎯 ЗОЛОТОЕ ПРАВИЛО

```
⚠️ ЕДИНАЯ БД НА ВСЕХ! ⚠️

Воин может заработать 100 медяков → видны в БД
Маг может потратить те же 100 медяков → исчезают из БД
Воин видит остаток 0 медяков

ВСЕ ДО КОПЕЙКИ СИНХРОНИЗИРОВАНО НА СЕРВЕРЕ!
Клиент - это только ВИЗУАЛИЗАЦИЯ (отображение того что на сервере)
```

---

## 📊 Структура БД (ЕДИНАЯ)

### Таблица `characters` (ОБЩАЯ для всех типов персонажей)

```sql
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'warrior' или 'mage' или в будущем другие
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    
    -- Здоровье и Мана (ОБЩИЕ ДЛЯ ВСЕХ)
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    mp INTEGER NOT NULL DEFAULT 50,
    max_mp INTEGER NOT NULL DEFAULT 50,
    
    -- ВАЛЮТА - ОБЩАЯ ДЛЯ ВСЕХ (Воин и Маг видят одно и то же!)
    copper INTEGER NOT NULL DEFAULT 0,      -- медяки (0-99)
    silver INTEGER NOT NULL DEFAULT 0,      -- серебро (0-99)
    gold INTEGER NOT NULL DEFAULT 0,        -- золото (можно >100)
    
    -- Характеристики (JSON - разные для воина и мага)
    stats_json TEXT NOT NULL,  
    stat_points INTEGER NOT NULL DEFAULT 6,
    
    -- Инвентарь (ОБЩИЙ для всех типов)
    inventory_json TEXT NOT NULL,  -- JSON с предметами
    equipped_json TEXT NOT NULL,   -- JSON с экипировкой
    
    -- Профессиональные данные
    profession_data_json TEXT,     -- Специфичные для типа персонажа данные
    
    zone TEXT NOT NULL DEFAULT 'town',
    updated_at REAL NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

**Пример строки для ВОИНА:**
```json
{
  "id": 1,
  "user_id": 1,
  "name": "Артур",
  "type": "warrior",
  "copper": 50,
  "silver": 20,
  "gold": 5,
  "stats_json": {
    "strength": 5,
    "agility": 3,
    "intuition": 2,
    "endurance": 4
  },
  "profession_data_json": {
    "warrior_specific": "данные только для воина"
  }
}
```

**Пример строки для МАГА:**
```json
{
  "id": 2,
  "user_id": 2,
  "name": "Волшебник",
  "type": "mage",
  "copper": 50,     -- ТА ЖЕ ВАЛЮТА! Может потратить эти 50 медяков
  "silver": 20,     -- ТА ЖЕ ВАЛЮТА!
  "gold": 5,        -- ТА ЖЕ ВАЛЮТА!
  "stats_json": {
    "wisdom": 5,
    "spirituality": 4,
    "endurance": 4
  },
  "profession_data_json": {
    "primary_element": "fire",
    "spellbook": ["spell1", "spell2", ...]
  }
}
```

### Таблица `inventory` (ОБЩАЯ - нужна или JSON в characters)

```sql
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,       -- ID предмета (например 'drink_ale', 'sword_iron')
    quantity INTEGER NOT NULL,
    slot INTEGER,                -- Номер слота в рюкзаке (или NULL если в банке)
    equipped BOOLEAN DEFAULT 0,  -- Экипирован ли?
    created_at REAL NOT NULL,
    FOREIGN KEY(character_id) REFERENCES characters(id)
);
```

**Пример:** И воины И маги видят эту таблицу!
- Если Воин купил зелье → `inventory` получает +1 для character_id=1
- Если Маг видит своё окно инвентаря → видит это же зелье

### Таблица `battle_stats` (ОБЩАЯ - для всех типов боя)

```sql
CREATE TABLE battle_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    opponent_id INTEGER,
    battle_type TEXT NOT NULL,  -- 'warrior_duel' или 'mage_duel' или смешанный
    victory BOOLEAN NOT NULL,
    
    -- Общие метрики
    damage_dealt INTEGER NOT NULL,
    damage_taken INTEGER NOT NULL,
    healing_done INTEGER NOT NULL,
    
    -- Награда (единая валюта!)
    copper_earned INTEGER DEFAULT 0,
    silver_earned INTEGER DEFAULT 0,
    gold_earned INTEGER DEFAULT 0,
    xp_earned INTEGER NOT NULL,
    
    -- Специфичные данные
    stats_json TEXT,  -- Специфичные метрики для типа боя
    
    battle_log TEXT,  -- JSON с ходами боя
    created_at REAL NOT NULL,
    FOREIGN KEY(character_id) REFERENCES characters(id)
);
```

---

## 💰 Финансовая система (ЕДИНАЯ)

### Правило конвертации

```
100 медяков (copper) → 1 серебро (silver)
100 серебра (silver) → 1 золото (gold)

Золото не конвертируется (может быть ∞)
```

### API для валюты (ЕДИНЫЙ для всех)

```python
# server/main.py или database.py

def add_currency(character_id: int, copper: int = 0, silver: int = 0, gold: int = 0):
    """Добавить валюту персонажу (работает для воина и мага одинаково)"""
    with db.connection() as conn:
        char = conn.execute(
            "SELECT copper, silver, gold FROM characters WHERE id = ?", 
            (character_id,)
        ).fetchone()
        
        total_copper = char['copper'] + copper
        total_silver = char['silver'] + silver
        total_gold = char['gold'] + gold
        
        # Автоматическая конвертация
        while total_copper >= 100:
            total_copper -= 100
            total_silver += 1
        
        while total_silver >= 100:
            total_silver -= 100
            total_gold += 1
        
        conn.execute(
            "UPDATE characters SET copper = ?, silver = ?, gold = ? WHERE id = ?",
            (total_copper, total_silver, total_gold, character_id)
        )

def subtract_currency(character_id: int, copper: int = 0, silver: int = 0, gold: int = 0) -> bool:
    """Вычесть валюту (возвращает True если успешно)"""
    with db.connection() as conn:
        char = conn.execute(
            "SELECT copper, silver, gold FROM characters WHERE id = ?",
            (character_id,)
        ).fetchone()
        
        # Проверка хватает ли денег
        total_available = (char['gold'] * 10000) + (char['silver'] * 100) + char['copper']
        total_needed = (gold * 10000) + (silver * 100) + copper
        
        if total_available < total_needed:
            return False  # Недостаточно средств
        
        # Вычитаем
        new_gold = char['gold'] - gold
        new_silver = char['silver'] - silver
        new_copper = char['copper'] - copper
        
        # Если недостаточно одного уровня - берем из верхнего
        if new_copper < 0:
            if new_silver > 0:
                new_silver -= 1
                new_copper += 100
        
        if new_silver < 0:
            if new_gold > 0:
                new_gold -= 1
                new_silver += 100
        
        conn.execute(
            "UPDATE characters SET copper = ?, silver = ?, gold = ? WHERE id = ?",
            (new_copper, new_silver, new_gold, character_id)
        )
        return True
```

### Пример покупки напитка (РАБОТАЕТ ОДИНАКОВО для Воина и Мага)

```python
# Оба персонажа видят один и тот же магазин
# Один персонаж (неважно какой) делает покупку

POST /api/shop/buy_drink
{
    "character_id": 1,  # Может быть воин (type='warrior')
    "drink_id": "ale",  # или маг (type='mage')
    "quantity": 1
}

# На сервере:
1. Получить персонажа
2. Проверить character.type (воин или маг - не важно!)
3. Проверить хватает ли медяков (character.copper >= 20)
4. Вычесть медяки: subtract_currency(1, copper=20)
5. Добавить в инвентарь
6. Вернуть обновленные данные персонажа

# Ответ клиенту:
{
    "success": true,
    "character": {
        "copper": 30,  -- было 50, вычли 20
        "silver": 20,
        "gold": 5,
        "inventory": [...]
    }
}
```

---

## 🗂️ Разделение кода (КОД ДА И ОП2)

### ЧТО ОБЩЕЕ (трогают оба):
```
✅ server/database.py     - методы для валюты, инвентаря, боя
✅ server/main.py         - новые API endpoints для магов
✅ core/currency.py       - класс Currency (используется обоими)
✅ ui/shop_ui.py          - один магазин для всех (адаптируется для типа)
✅ ui/inventory_ui.py     - один инвентарь для всех
```

### ЧТО ОТДЕЛЬНОЕ (ДА - Воины):
```
scenes/duel_scene.py      - боевая система ТОЛЬКО для воинов
core/character/warrior.py - класс Warrior
core/stats/warrior_stats.py - статистика воинов
ui/warrior_card.py        - карточка воина
ui/battle_ui.py           - UI боя воинов
```

### ЧТО ОТДЕЛЬНОЕ (ОП2 - Маги):
```
scenes/mage_duel_scene.py  - боевая система ТОЛЬКО для магов
core/character/mage.py     - класс Mage
core/magic/spell.py        - заклинания
core/magic/spellbook.py    - гримуар
ui/mage_card.py            - карточка мага
ui/mage_battle_ui.py       - UI боя магов
```

---

## 📈 Пример: Воин работает, Маг работает

### Сценарий 1: Оба персонажа одного игрока

```
Пользователь (user_id=1):
- Создает Воина (character_id=1, type='warrior')
- Создает Мага  (character_id=2, type='mage')

БД:
characters {
    { id: 1, user_id: 1, type: 'warrior', copper: 0, silver: 0, gold: 0 },
    { id: 2, user_id: 1, type: 'mage',    copper: 0, silver: 0, gold: 0 }
}

Воин побеждает в бою → получает 10 медяков:
UPDATE characters SET copper = 10 WHERE id = 1

БД:
characters {
    { id: 1, user_id: 1, type: 'warrior', copper: 10, ... },  -- ← 10 медяков
    { id: 2, user_id: 1, type: 'mage',    copper: 0,  ... }
}

Игрок переключается на Мага (выбирает character_id=2):
- Видит в таверне магазин
- Видит только свои 0 медяков (id=2)

Маг побеждает → получает 10 медяков:
UPDATE characters SET copper = 10 WHERE id = 2

БД:
characters {
    { id: 1, user_id: 1, type: 'warrior', copper: 10, ... },  -- Воин: 10 медяков
    { id: 2, user_id: 1, type: 'mage',    copper: 10, ... }   -- Маг: 10 медяков
}

Маг идет в магазин и покупает напиток за 20 медяков:
subtract_currency(character_id=2, copper=20)  -- ОШИБКА! Не хватает денег

Маг и Воин вместе зарабатывают еще 20 медяков:
- Когда-то один из них выигрывает еще 20 медяков

БД:
characters {
    { id: 1, user_id: 1, type: 'warrior', copper: 10, silver: 1, gold: 0 },
    { id: 2, user_id: 1, type: 'mage',    copper: 10, silver: 1, gold: 0 }
}

Теперь каждый может купить напиток!
```

---

## 🔗 API Design (Общие для всех)

### Получить персонажа (неважно какого типа)

```
GET /api/character/<id>

Response:
{
    "id": 1,
    "name": "Артур",
    "type": "warrior",
    "level": 3,
    "hp": 30,
    "max_hp": 40,
    "mp": 50,
    "max_mp": 50,
    "copper": 10,
    "silver": 2,
    "gold": 1,
    "stats": {...},
    "inventory": [...],
    "profession_data": {...}  -- специфичные данные для типа
}
```

### Купить предмет в магазине (ЕДИНЫЙ ENDPOINT)

```
POST /api/shop/buy
{
    "character_id": 1,  -- может быть воин или маг
    "item_id": "drink_ale",
    "quantity": 1
}

Response:
{
    "success": true,
    "copper": 0,   -- обновленная валюта
    "silver": 1,
    "gold": 0,
    "inventory": [...]  -- обновленный инвентарь
}
```

### Начать бой (РАЗНЫЕ для типа)

```
POST /api/battle/start
{
    "character_id": 1
}

Сервер проверяет character.type:
- Если 'warrior'  → запускает DuelScene (ДА)
- Если 'mage'     → запускает MageDuelScene (ОП2)

Response:
{
    "battle_id": "b123",
    "scene_type": "duel" или "mage_duel",
    "opponent": {...},
    "initial_state": {...}
}
```

### Завершить бой (ЕДИНЫЙ - обновляет валюту в characters)

```
POST /api/battle/<battle_id>/finish
{
    "character_id": 1,
    "victory": true
}

На сервере:
1. Проверить результат
2. Если victory=true:
   - add_currency(1, copper=10)  или copper=20, silver=1, etc.
3. Сохранить в battle_stats
4. Обновить character (level, xp, stats)

Response:
{
    "victory": true,
    "rewards": {
        "xp": 50,
        "copper": 10,
        "silver": 0,
        "gold": 0
    },
    "character": {
        "level": 4,
        "xp": 150,
        "copper": 20,  -- обновлено!
        "silver": 2,
        "gold": 1
    }
}
```

---

## 📝 Инструкция для ОП2 (Разработчик 2)

### ✅ ЧТО НУЖНО ДЕЛАТЬ:

1. **Создавать свои файлы** для логики магии:
   - `core/character/mage.py` - класс Mage
   - `core/magic/spell.py` - класс Spell
   - `scenes/mage_duel_scene.py` - боевая система магов

2. **Использовать ОБЩИЕ API**:
   ```python
   # Для получения персонажа
   character = db.get_character(character_id)  # ВСЕ типы!
   
   # Для работы с валютой
   db.add_currency(character_id, copper=10)
   db.subtract_currency(character_id, copper=20)
   
   # Для инвентаря
   db.add_to_inventory(character_id, "item_id", quantity=1)
   ```

3. **Отправлять данные на сервер**:
   - Никогда не считай деньги на клиенте!
   - Сервер это источник истины (источник правды)
   - Клиент только отображает

### ❌ ЧТО НЕ ДЕЛАТЬ:

1. **НЕ менять таблицу `characters`**:
   - Не добавляй новые колонки для магов (используй `profession_data_json`)
   - Не меняй валюту для магов отдельно

2. **НЕ считать деньги на клиенте**:
   ```python
   # ❌ НЕПРАВИЛЬНО:
   local_copper = 50
   if local_copper >= 20:
       local_copper -= 20
   
   # ✅ ПРАВИЛЬНО:
   response = api.subtract_currency(character_id, copper=20)
   if response.success:
       show_message("Куплено!")
   else:
       show_message("Недостаточно средств!")
   ```

3. **НЕ дублировать валюту**:
   ```python
   # ❌ НЕПРАВИЛЬНО:
   mage_copper = 50  # отдельная переменная для магов
   
   # ✅ ПРАВИЛЬНО:
   character = db.get_character(character_id)
   mage_copper = character['copper']  # из БД, одна для всех
   ```

### 🎯 Логика разделения на примере

**Когда ОП2 создает систему магии:**

```python
# ✅ ПРАВИЛЬНО: Использует общую валюту
class Mage(BaseCharacter):
    def buy_spell_tome(self, tome_id: str, cost_copper: int):
        # Вычитаем из ОБЩЕЙ валюты (не создаем отдельную)
        if db.subtract_currency(self.id, copper=cost_copper):
            self.learn_spell(tome_id)
            return True
        return False

# ❌ НЕПРАВИЛЬНО: Создает отдельную валюту
class Mage(BaseCharacter):
    def __init__(self):
        self.mage_copper = 50  # отдельная! ПЛОХО!
        self.mage_silver = 0
    
    def buy_spell_tome(self, tome_id: str):
        if self.mage_copper >= 20:
            self.mage_copper -= 20  # изменяем локальную копию! ПЛОХО!
```

---

## 🎮 Финальная архитектура

### Таверна (ОБЩАЯ для всех)

```
┌─────────────────────────────────────────┐
│          ТАВЕРНА (одна для всех)         │
├─────────────────────────────────────────┤
│                                         │
│  💰 Валюта (из БД, одна для всех):     │
│     Медяки: 50  Серебро: 2  Золото: 1  │
│                                         │
│  🏪 Магазин (адаптируется для типа):   │
│     - Зелья (купит кто угодно)         │
│     - Тома заклинаний (только маги)     │
│     - Мечи (только воины)               │
│                                         │
│  ⚔️ Боевой тренер:                     │
│     - Нажал воин  → DuelScene          │
│     - Нажал маг   → MageDuelScene      │
│                                         │
│  💬 Чат (общий для всех)               │
│     Все видят сообщения друг друга     │
│                                         │
└─────────────────────────────────────────┘
```

### База данных (ОДНА на всех)

```
users (одна таблица)
  ├─ user_id=1
  │   ├─ character_id=1 (warrior) → медяки из БД
  │   └─ character_id=2 (mage)    → медяки из БД (могут быть разные!)
  │
  └─ user_id=2
      └─ character_id=3 (warrior) → медяки из БД

inventory (одна таблица для всех)
  ├─ character_id=1 (warrior) → зелья, мечи
  └─ character_id=2 (mage)    → зелья, тома

battle_stats (одна таблица для всех типов боев)
  ├─ battle_type='warrior_duel'
  └─ battle_type='mage_duel'

characters (ОДНА ТАБЛИЦА, поле type различает тип!)
  ├─ id=1, type='warrior', copper=50, silver=2, gold=1
  ├─ id=2, type='mage',    copper=50, silver=2, gold=1
  └─ id=3, type='warrior', copper=100 → 101 copper в итоге
```

---

## 🚀 Инструкция при запуске

### Для ОП1 (текущий разработчик):
✅ Продолжать работать как обычно
✅ Пакет `core/character/warrior.py` - ваше
✅ Пакет `scenes/duel_scene.py` - ваше
✅ Валюта и инвентарь - ОБЩИЕ

### Для ОП2 (новый разработчик):
1. Прочитать ЭТУ архитектуру (ARCHITECTURE_DUAL_SYSTEM.md)
2. Прочитать MAGE_DEVELOPER_GUIDE.md для деталей
3. Создать `core/character/mage.py` (используя `BaseCharacter`)
4. Использовать ОБЩИЕ методы БД для валюты
5. Создать `scenes/mage_duel_scene.py` (своя боевая система)
6. НЕ менять warrior код и НЕ дублировать валюту

---

**Вопросы ОП2?** Спросите до начала работы! Лучше уточнить сейчас, чем переделывать потом.

**Документ готов к передаче:** 2026-09-02  
**Статус:** 🟢 Готов, архитектура зафиксирована
