# DUEL - Раздел Магии для второго разработчика

**Статус:** 🟡 Готовый к передаче разработчику 2  
**Разработчик:** Оператор 2 (Система магии)  
**Дата создания:** 2026-09-02

⚠️ **ВАЖНО:** Перед тем как начать, прочитайте [ARCHITECTURE_DUAL_SYSTEM.md](./ARCHITECTURE_DUAL_SYSTEM.md) - там описана ЕДИНАЯ БД и ЕДИНАЯ валюта для воинов и магов!

## 📋 Обзор

Второй разработчик будет отвечать за **полную систему магии** в рамках проекта DUEL. Это **отдельная подсистема**, которая не пересекается с основной системой боя воинов (Warrior System).

### Принцип разделения

```
┌─────────────────────────────────────────────────────────────┐
│                      ОСНОВНАЯ ИГРА (ДА)                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │ Система Воинов (ДА)  │      │ Система Магии (ОП2)  │    │
│  │  (Warrior System)    │      │   (Mage System)      │    │
│  ├──────────────────────┤      ├──────────────────────┤    │
│  │ • Характеристики     │      │ • Характеристики     │    │
│  │   (Сила, Ловкость)   │      │   (Мудрость, Духовн) │    │
│  │ • Карты атак         │      │ • Магические способн │    │
│  │ • Боевые действия    │      │ • Система магии      │    │
│  │ • Сценa duel_scene   │      │ • Система элементов  │    │
│  │   для воинов         │      │ • Новая сцена боя    │    │
│  │                      │      │   для магов          │    │
│  └──────────────────────┘      └──────────────────────┘    │
│          ↓                               ↓                  │
│  Таверна (общая)  ←─────────────────────────────────────→  │
│  Магазин (общий)  ←─────────────────────────────────────→  │
│  Чат (общий)      ←─────────────────────────────────────→  │
│  БД (общая)       ←─────────────────────────────────────→  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Что ДА (Оператор 1) делает:
- ✅ Основная боевая система (Warrior)
- ✅ Система валюты
- ✅ Магазин напитков
- ✅ Таверна и чат
- ✅ Аутентификация
- ✅ Инвентарь (общее)

### Что ОП2 (Второй разработчик) делает:
- 🧙 Система персонажей-магов (Mage class)
- 🧙 Система магии и заклинаний
- 🧙 Система элементов (Земля, Вода, Огонь, Воздух)
- 🧙 Боевая система для магов (отдельная сцена)
- 🧙 Таблица статистики магических боев
- 🧙 AI для магических ботов

## 🗂️ Архитектура проекта для магии

### Структура папок (что создать)

```
core/
├── character/
│   ├── base.py           # ✅ Уже есть - BaseCharacter (абстрактный)
│   ├── warrior.py        # ✅ Уже есть - Warrior (воины)
│   └── mage.py           # 🔴 СОЗДАТЬ - Mage (маги)
│
├── stats/
│   ├── warrior_stats.py   # ✅ Уже есть
│   └── mage_stats.py      # 🔴 СОЗДАТЬ - Статистика магов
│
├── magic/                 # 🔴 НОВАЯ ПАПКА
│   ├── __init__.py
│   ├── spell.py          # Класс заклинания
│   ├── element.py        # Система элементов
│   ├── spellbook.py      # Гримуар заклинаний
│   └── school.py         # Школы магии
│
└── effects/               # 🔴 НОВАЯ ПАПКА
    ├── __init__.py
    ├── effect.py         # Базовый класс эффекта
    └── magic_effects.py  # Магические эффекты

scenes/
├── duel_scene.py         # ✅ Боевая система для воинов
└── mage_duel_scene.py    # 🔴 СОЗДАТЬ - Боевая система для магов

ui/
├── character_card.py     # ✅ Карточка персонажа (адаптировать)
├── mage_card.py          # 🔴 СОЗДАТЬ - Карточка мага
├── spellbook_ui.py       # 🔴 СОЗДАТЬ - UI гримуара
└── magic_effects_ui.py   # 🔴 СОЗДАТЬ - UI эффектов магии

server/
├── database.py           # ✅ Адаптировать для магов
└── magic_routes.py       # 🔴 СОЗДАТЬ - API для магии

client/
├── session.py            # ✅ Адаптировать для магов
└── magic_client.py       # 🔴 СОЗДАТЬ - Клиент для магии
```

## 📊 Система характеристик магов

### Основные характеристики (3)

```python
{
    "wisdom": 3,          # Мудрость - урон магии (базовое значение)
    "spirituality": 3,    # Духовность - манапул и регенерация маны
    "endurance": 4,       # Выносливость - здоровье (как у воинов)
}
```

### Расчёты

```python
# HP = endurance * 10
max_hp = 4 * 10  # = 40 HP

# Мана = spirituality * 5
max_mana = 3 * 5  # = 15 MP

# Урон магии = wisdom * коэффициент элемента
magic_damage = wisdom * element_coefficient

# Регенерация маны = spirituality * 0.1 в секунду
mana_regen = spirituality * 0.1
```

### Правила прокачки

- ✅ **Можно прокачивать:** Мудрость, Духовность
- ❌ **Нельзя прокачивать:** Выносливость (только +1 за уровень)
- ✅ **Минимум:** 3 для Мудрости и Духовности
- ✅ **Выносливость:** 4 + (уровень - 1)
- ✅ **Очки за уровень:** +3 очка на прокачку при повышении уровня

## 🧙 Система магии

### Четыре элемента

```python
ELEMENTS = {
    "earth": {
        "name": "Земля",
        "color": (139, 69, 19),
        "type": "physical",
        "traits": ["мощь", "стабильность"],
        "spells": ["Земляной удар", "Каменное покрытие", ...]
    },
    "water": {
        "name": "Вода",
        "color": (0, 100, 200),
        "type": "healing",
        "traits": ["исцеление", "контроль"],
        "spells": ["Исцеляющая волна", "Морозный луч", ...]
    },
    "fire": {
        "name": "Огонь",
        "color": (255, 100, 0),
        "type": "offensive",
        "traits": ["урон", "взрывы"],
        "spells": ["Огненный шар", "Пылающий вихрь", ...]
    },
    "wind": {
        "name": "Воздух",
        "color": (100, 200, 255),
        "type": "mobility",
        "traits": ["скорость", "мобильность"],
        "spells": ["Воздушный удар", "Порыв ветра", ...]
    }
}
```

### Структура заклинания

```python
class Spell:
    def __init__(
        self,
        id: str,
        name: str,
        element: str,           # "earth", "water", "fire", "wind"
        cost: int,              # стоимость маны
        damage: int,            # урон (базовый)
        description: str,
        effect: str,            # "damage", "heal", "control", "buff"
        cast_time: float,       # время каста в секундах
        cooldown: float,        # перезарядка
        school: str,            # "combat", "healing", "utility"
    ):
        self.id = id
        self.name = name
        self.element = element
        self.cost = cost
        self.damage = damage
        self.description = description
        self.effect = effect
        self.cast_time = cast_time
        self.cooldown = cooldown
        self.school = school
    
    def calculate_damage(self, wisdom: int, target_defense: int) -> int:
        # Расчет урона с учетом мудрости и защиты
        base_damage = self.damage + (wisdom * 0.5)
        reduction = max(0, target_defense * 0.3)
        return int(base_damage - reduction)
```

### Примеры заклинаний

**Огонь (Damage):**
```python
{
    "id": "fire_fireball",
    "name": "Огненный шар",
    "element": "fire",
    "cost": 20,
    "damage": 15,
    "effect": "damage",
    "cast_time": 1.5,
    "cooldown": 2.0,
    "school": "combat",
    "description": "Запускает огненный шар в противника"
}
```

**Вода (Healing):**
```python
{
    "id": "water_heal",
    "name": "Исцеляющая волна",
    "element": "water",
    "cost": 15,
    "damage": 0,
    "effect": "heal",
    "cast_time": 1.0,
    "cooldown": 1.5,
    "school": "healing",
    "heal_amount": 20,
    "description": "Восстанавливает 20 HP вам или союзнику"
}
```

**Земля (Control):**
```python
{
    "id": "earth_stun",
    "name": "Паралич земли",
    "element": "earth",
    "cost": 25,
    "damage": 5,
    "effect": "control",
    "cast_time": 2.0,
    "cooldown": 3.0,
    "school": "combat",
    "duration": 2.0,  # длительность стана
    "description": "Замораживает противника на 2 секунды"
}
```

## 🎮 Боевая система магов

### Фазы боя (аналогично воинам, но адаптировано)

1. **Подготовка** - выбор заклинания вместо карты
2. **Кастование** - анимация каста (cast_time)
3. **Эффект** - применение эффекта (урон, исцеление, контроль)
4. **Регенерация маны** - восстановление маны между ходами
5. **Результаты** - таблица статистики боя

### Отличия от воинов

| Воины | Маги |
|-------|------|
| Карты (физические) | Заклинания (магия) |
| HP и Stamina | HP и Mana |
| Прямая атака | Каст + эффект |
| Нет времени каста | Время каста (cast_time) |
| Стандартный урон | Зависит от элемента и мудрости |

### Мана и её восстановление

```python
# В начале хода маг получает регенерацию маны
mana_regen_per_turn = spirituality * 0.5

# При касте заклинания
if current_mana >= spell.cost:
    current_mana -= spell.cost
    apply_spell_effect(spell)
else:
    # Не хватает маны - действие отменяется
    show_error("Недостаточно маны!")
```

## 🗄️ Структура БД для магов

### Таблица mage_characters

```sql
CREATE TABLE mage_characters (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    
    -- Статистика
    wisdom INTEGER DEFAULT 3,
    spirituality INTEGER DEFAULT 3,
    endurance INTEGER DEFAULT 4,
    
    -- Состояние в бою
    hp INTEGER,
    max_hp INTEGER,
    mana INTEGER,
    max_mana INTEGER,
    
    -- Валюта (общая с воинами)
    copper INTEGER DEFAULT 0,
    silver INTEGER DEFAULT 0,
    gold INTEGER DEFAULT 0,
    
    -- Специфично для магов
    primary_element TEXT DEFAULT 'fire',  -- основной элемент
    spellbook TEXT,  -- JSON с изученными заклинаниями
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
```

### Таблица mage_spells

```sql
CREATE TABLE mage_spells (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    element TEXT NOT NULL,
    cost INTEGER,
    damage INTEGER,
    description TEXT,
    effect TEXT,
    cast_time REAL,
    cooldown REAL,
    school TEXT,
    created_at TIMESTAMP
)
```

### Таблица mage_battle_stats

```sql
CREATE TABLE mage_battle_stats (
    id INTEGER PRIMARY KEY,
    mage_id INTEGER NOT NULL,
    opponent_id INTEGER,
    opponent_type TEXT,  -- "mage" или "bot"
    
    -- Результат
    victory BOOLEAN,
    
    -- Статистика
    spells_cast INTEGER,
    mana_used INTEGER,
    damage_dealt INTEGER,
    damage_taken INTEGER,
    healing_done INTEGER,
    
    battle_log TEXT,  -- JSON с ходами
    
    created_at TIMESTAMP,
    FOREIGN KEY (mage_id) REFERENCES mage_characters(id)
)
```

## 🔗 API для магии

### Аутентификация магов

```
POST /api/mage/create
Body: { "name": "Маг-новичок" }
Response: { "mage": mage_data }
```

### Получить данные мага

```
GET /api/mage/<id>
Response: { "mage": mage_data_with_stats }
```

### Сохранить мага

```
POST /api/mage/<id>/save
Body: { "wisdom": 5, "spirituality": 4, ... }
Response: { "mage": updated_mage }
```

### Список заклинаний

```
GET /api/mage/spells
Response: { "spells": [spell1, spell2, ...] }
```

### Начать магический бой

```
POST /api/mage/duel/start
Body: { "mage_id": 1 }
Response: { "duel": duel_state }
```

### Произнести заклинание

```
POST /api/mage/duel/cast
Body: { 
    "duel_id": 1, 
    "spell_id": "fire_fireball",
    "target": "opponent"
}
Response: { "result": effect_result }
```

### Завершить бой

```
POST /api/mage/duel/finish
Body: { "duel_id": 1 }
Response: { "winner": "mage_id", "stats": battle_stats }
```

## 🚀 План разработки для ОП2

### Фаза 1: Основы (неделя 1)
- [ ] Создать класс `Mage` в `core/character/mage.py`
- [ ] Создать систему статистики магов в `core/stats/mage_stats.py`
- [ ] Адаптировать БД для поддержки магов в `server/database.py`
- [ ] Создать базовые API endpoints

### Фаза 2: Система магии (неделя 2)
- [ ] Создать класс `Spell` в `core/magic/spell.py`
- [ ] Создать систему элементов в `core/magic/element.py`
- [ ] Создать гримуар в `core/magic/spellbook.py`
- [ ] Создать 12+ заклинаний (3 на элемент)

### Фаза 3: Боевая система (неделя 3)
- [ ] Создать `MageDuelScene` в `scenes/mage_duel_scene.py`
- [ ] Реализовать логику каста и маны
- [ ] Создать таблицу статистики для магов
- [ ] Реализовать ИИ для магических ботов

### Фаза 4: UI (неделя 4)
- [ ] Создать карточку мага в `ui/mage_card.py`
- [ ] Создать интерфейс гримуара в `ui/spellbook_ui.py`
- [ ] Создать визуализацию заклинаний
- [ ] Интеграция с таверной и магазином

### Фаза 5: Тестирование и полировка (неделя 5)
- [ ] Тестирование балансировки урона
- [ ] Тестирование маны и регенерации
- [ ] Тестирование ИИ магических ботов
- [ ] Оптимизация производительности

## ⚠️ Правила для избежания конфликтов кода

### ✅ ЧТО ОП2 МОЖЕТ МЕНЯТЬ:

1. **Создавать новые файлы:**
   - `core/character/mage.py`
   - `core/magic/*`
   - `core/effects/*`
   - `scenes/mage_duel_scene.py`
   - `ui/mage_*.py`
   - `server/magic_routes.py`
   - `client/magic_client.py`

2. **Менять в существующих файлах:**
   - `core/character/base.py` - добавлять абстрактные методы для магов
   - `server/database.py` - добавлять методы для магов (не трогать warrior методы)
   - `client/session.py` - добавлять методы для магов
   - `main.py` - добавлять экран выбора профессии (Воин/Маг)

### ❌ ЧТО ОП2 НЕ МОЖЕТ МЕНЯТЬ:

1. **НЕ трогать warrior код:**
   - `core/character/warrior.py` (только если критическая ошибка)
   - `core/stats/warrior_stats.py` (только если критическая ошибка)
   - `scenes/duel_scene.py` (только если критическая ошибка)
   - `ui/character_card.py` (только адаптация для магов, не удаление)

2. **НЕ менять логику боя воинов:**
   - Система карт
   - Расчёт урона для воинов
   - Фазы боя для воинов

3. **НЕ менять другие системы:**
   - Система валюты (только использовать)
   - Магазин (только адаптировать для магов)
   - Чат (только использовать)
   - Таверна (адаптировать для магов)

## 🔄 Интеграция с основной игрой

### Экран выбора профессии (в main.py)

```python
class ProfessionSelectScene:
    """Выбор между Воином и Магом"""
    
    def __init__(self):
        self.warrior_button = pygame.Rect(...)
        self.mage_button = pygame.Rect(...)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.warrior_button.collidepoint(event.pos):
                return "warrior"
            elif self.mage_button.collidepoint(event.pos):
                return "mage"
```

### Выбор противника в таверне

```python
class TavernScene:
    def handle_npc_click(self, npc_name):
        if npc_name == "Боевой тренер":
            if self.character.type == "warrior":
                return DuelScene(self.session)
            elif self.character.type == "mage":
                return MageDuelScene(self.session)
```

## 🎯 Коммуникация между разработчиками

### ДА (Оператор 1) и ОП2 будут:

1. **Встречаться каждый день** - обсуждать прогресс (15 минут)
2. **Делать code review** - перед merge в main
3. **Использовать разные ветки:**
   - ДА: `feature/warrior-*`
   - ОП2: `feature/mage-*`
4. **Коммитить часто** - чтобы видеть прогресс
5. **Документировать изменения** - добавлять комментарии в код

### Git workflow для ОП2

```bash
# Создать ветку для фичи
git checkout -b feature/mage-spellbook

# Делать коммиты
git commit -m "Add Spell class and spellbook system"
git commit -m "Add 12 spells for 4 elements"

# Перед merge убедиться что нет конфликтов
git pull origin main
# Если есть конфликты - разрешить их

# Создать Pull Request
git push origin feature/mage-spellbook
# На GitHub - нажать "Create Pull Request"
# ДА сделает code review и merge
```

## 📞 Контакты для ОП2

- **Основная ветка:** `main` (стабильная, для production)
- **Ветка разработки:** `develop` (не используется, каждый на своей feature branch)
- **Структура коммитов:** `Добавить систему магии - [описание]`

## 🎉 Готово к работе!

Теперь ОП2 может начать разработку без риска конфликтов кода! 

**Первые шаги для ОП2:**

1. Клонировать репозиторий
2. Прочитать этот документ
3. Прочитать `MAGE_SYSTEM_DOCS.md` для деталей
4. Создать ветку: `git checkout -b feature/mage-foundation`
5. Начать с создания класса `Mage` в `core/character/mage.py`

---

**Документ создан:** 2026-09-02  
**Версия:** 1.0  
**Статус:** 🟢 Готов к передаче второму разработчику
