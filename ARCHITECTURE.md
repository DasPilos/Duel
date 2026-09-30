# Архитектура системы 6 классов

## 📋 Обзор

После анализа и очистки кода, вся система переработана для поддержки **6 уникальных классов** с сохранением полной консистентности.

### **Единый источник истины**
Все данные классов определены **ОДИН РАЗ** в `/combat/character_stats.py`:
- `PROFESSIONS` - данные о каждом классе
- `UNIQUE_RESOURCE_RECOVERY` - восстановление ресурсов
- `UNIQUE_RESOURCE_GAIN` - получение ресурсов в бою

---

## 🎮 6 Классов персонажей

| Класс | HP | Мана | Уворот | Крит | Уникальный ресурс |
|---|---|---|---|---|---|
| **Боец** | 70 | 5 | 0% | 5% | Ярость (Rage) |
| **Лучник** | 35 | 15 | 10% | 5% | Меткость (Accuracy) |
| **Асасин** | 40 | 10 | 0% | 5% (80% урон) | Концентрация (Concentration) |
| **Боевой маг** | 50 | 20 | 0% | 5% | Мана |
| **Маг поддержки** | 30 | 45 | 0% | 5% | Мана |
| **Гармонист** | 35 | 35 | 0% | 5% | Мана |

---

## 🔋 Уникальные ресурсы

### **Ярость (Rage) - Боец**
```python
# Максимум
max_rage = 50 + (9 × (level - 1))

# Восстановление в конце хода
+4 ярости

# Получение в бою
При получении 10+ урона: +10 + (2 × level) ярости

# Трата
Карты стоят N ярости (как action points для action point карт)
```

### **Меткость (Accuracy) - Лучник**
```python
# Максимум
max_accuracy = 50 + (9 × (level - 1))

# Восстановление в конце хода
+5 меткости

# Получение в бою
При успешном уворотиь: +7 + (1 × level) меткости

# Трата
Карты стоят N меткости
```

### **Концентрация (Concentration) - Асасин**
```python
# Максимум
max_concentration = 50 + (9 × (level - 1))

# Восстановление в конце хода
+9 концентрации

# Получение в бою
При крит ударе: +15 + (1 × level) концентрации

# Трата
Карты стоят N концентрации
```

### **Мана (Mana) - Все магические классы**
```python
# Максимум
max_mana = intellect × 5

# Восстановление в конце хода
+8 + (wisdom ÷ 2) маны

# Получение в бою
Автоматически восстанавливается в конце хода

# Трата
Карты стоят N маны
```

---

## 💾 Структура Fighter класса

```python
class Fighter:
    # Основные поля
    name: str
    level: int
    character_id: int
    profession_type: str  # "warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"
    
    # Основные характеристики (7 статов для всех)
    stats: dict  # {"strength", "agility", "intuition", "wisdom", "intellect", "harmony", "endurance"}
    stat_points: int  # Для распределения
    
    # Здоровье
    hp: int
    max_hp: int  # = endurance × 10
    
    # Мана (для всех классов)
    mp: int
    max_mp: int  # = intellect × 5
    
    # Уникальный ресурс (зависит от класса)
    unique_resource_type: str  # "rage", "accuracy", "concentration", "mana"
    unique_resource_current: int  # Текущее значение
    unique_resource_max: int  # Максимум (зависит от класса и уровня)
    
    # Методы для уникального ресурса
    spend_unique_resource(amount) -> bool  # Потратить ресурс
    gain_unique_resource(amount) -> None   # Получить ресурс
    recover_unique_resource(level) -> None # Восстановить в конце хода
```

---

## 🃏 Система карт

### **Card dataclass**
```python
@dataclass(frozen=True)
class Card:
    # Идентификация
    key: str
    name: str
    group_name: str  # e.g., "Магия: Огонь" или "Боец: Кровавая жатва"
    
    # Затраты ресурсов (старая система - для warrior карт)
    strength_cost: int
    intuition_cost: int
    agility_cost: int
    endurance_cost: int
    
    # Затраты ресурсов (новая система)
    resource_type: str  # "mana", "rage", "accuracy", "concentration"
    resource_cost: int  # Затрата уникального ресурса
    
    # Эффекты
    effect_type: str
    effect_data: dict  # JSON параметры
    
    # Другое
    level: int
    image_path: str
    effect_duration: int
    drop_chance: float
```

### **Типы затрат ресурсов**
```python
CARD_RESOURCE_TYPES = {
    "mana": "Мана",           # Для магических классов
    "rage": "Ярость",         # Для бойца
    "accuracy": "Меткость",   # Для лучника
    "concentration": "Концентрация",  # Для асасина
    "action_points": "Action Points",  # Старая система (для бойца с боевыми картами)
}
```

---

## ⚔️ Боевая система (CardBattle)

### **Применение карты**
```python
def can_select(side: str, card: Card) -> bool:
    fighter = self.player if side == "player" else self.enemy
    
    # Проверить action points (для старых карт воина)
    if card.resource_type == "action_points":
        for stat, cost in card.costs.items():
            if action_points[side][stat] < cost:
                return False
    
    # Проверить уникальный ресурс
    elif card.resource_type == fighter.unique_resource_type:
        if fighter.unique_resource_current < card.resource_cost:
            return False
    
    # Проверить ман (если карта стоит ман, а это не main ресурс)
    elif card.resource_type == "mana":
        if fighter.mp < card.resource_cost:
            return False
    
    return True

def resolve_card(side: str, card: Card) -> None:
    fighter = self.player if side == "player" else self.enemy
    
    # Потратить ресурс
    if card.resource_type == "action_points":
        for stat, cost in card.costs.items():
            action_points[side][stat] -= cost
    
    elif card.resource_type == fighter.unique_resource_type:
        fighter.spend_unique_resource(card.resource_cost)
    
    elif card.resource_type == "mana":
        fighter.mp = max(0, fighter.mp - card.resource_cost)
    
    # Применить эффект карты
    _resolve_card_effect(side, card)
```

### **Восстановление ресурсов в конце хода**
```python
def end_turn(self):
    # Восстановить ман (для всех классов)
    fighter.mp = min(fighter.max_mp, fighter.mp + 8 + fighter.wisdom // 2)
    
    # Восстановить уникальный ресурс (если не мана)
    if fighter.unique_resource_type != "mana":
        fighter.recover_unique_resource(fighter.level)
    
    # Пересчитать параметры на случай если изменился интеллект
    fighter.recalculate_parameters()
```

---

## 📊 Распределение карт по классам

### **Маги (все 3 типа имеют одинаковые карты)**
- 36 магических карт (6 элементов × 6 карт каждый)
- Все карты стоят **мана** (resource_type = "mana")
- Карты одинаковы для всех магических классов (боевой маг, маг поддержки, гармонист)

### **Боец (Warrior)**
- 21 карта (3 стиля × 7 карт)
- Карты стоят **ярость** (resource_type = "rage")
- Не используют старую систему action points

### **Лучник (Archer)**
- 24 карты (3 стиля × 8 карт)
- Карты стоят **меткость** (resource_type = "accuracy")

### **Асасин (Assassin)**
- 24 карты (3 стиля × 8 карт)
- Карты стоят **концентрация** (resource_type = "concentration")

---

## 🔄 Миграция от старой системы

### **Была:**
```python
# Старая система action points
card.costs = {
    "strength": 5,
    "intuition": 3,
    "agility": 2,
    "endurance": 1,
}
# Применение: вычитаем action points каждый ход

# Мана была спрятана в effect_data
card.effect_data["mana_cost"] = 10  # ← Плохо!
```

### **Стала:**
```python
# Новая система - явное указание ресурса
card.resource_type = "mana"  # или "rage", "accuracy", "concentration"
card.resource_cost = 10

# Старые карты воина с action points все еще поддерживаются:
card.resource_type = "action_points"
card.costs = {...}  # ← Как было раньше
```

---

## ✅ Консистентность

### **Гарантии (все проверено)**
- ✅ Все данные классов в одном месте: `character_stats.py`
- ✅ Нет дублирования кода между файлами
- ✅ Нет конфликтующих систем (удалена старая `/core/character/`)
- ✅ Все формулы центра

лизованы в функциях
- ✅ Fighter использует эти функции для всех расчетов
- ✅ CardBattle использует Fighter для применения ресурсов
- ✅ Card содержит явный тип и затрату ресурса

### **Если нужно изменить что-то в системе:**
1. Найти константу в `character_stats.py`
2. Изменить ее
3. Все остальные части автоматически используют обновленное значение

---

## 📝 Примеры

### **Создать бойца уровня 5**
```python
fighter = Fighter(name="Ivan", level=5, profession_type="warrior")
# fighter.unique_resource_type = "rage"
# fighter.unique_resource_max = 50 + (9 × 4) = 86
# fighter.unique_resource_current = 86
# fighter.max_hp = 70
# fighter.max_mp = 15 (intellect × 5 = 3 × 5)
```

### **Применить карту с яростью**
```python
card = get_card("warrior_slash")  # resource_type="rage", resource_cost=11

if battle.can_select("player", card):
    fighter.spend_unique_resource(11)  # Потратить ярость
    battle._resolve_card_effect("player", card)  # Применить эффект
```

### **Восстановление в конце хода**
```python
# Боец восстанавливает +4 ярости
fighter.recover_unique_resource(level=5)  # +4 ярости

# Маг восстанавливает ман по формуле
fighter.mp = min(fighter.max_mp, fighter.mp + 8 + fighter.wisdom // 2)
```

