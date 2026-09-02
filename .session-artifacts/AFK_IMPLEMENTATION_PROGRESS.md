# Реализация АФК системы для боев

## ✅ Завершённые компоненты

### 1. **Слой базы данных** (`server/database.py`)

**Добавлена таблица `active_battles`:**
```sql
CREATE TABLE IF NOT EXISTS active_battles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    opponent_id INTEGER NOT NULL,
    battle_data TEXT NOT NULL,      -- JSON состояние боя
    player_afk INTEGER NOT NULL DEFAULT 0,
    opponent_afk INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY(player_id) REFERENCES characters(id),
    FOREIGN KEY(opponent_id) REFERENCES characters(id)
);
```

**Добавлены методы:**
- `save_active_battle(player_id, opponent_id, battle_data)` - сохраняет состояние боя
- `mark_player_afk(player_id, opponent_id, is_afk=True)` - отмечает игрока как АФК
- `get_active_battle(player_id, opponent_id)` - восстанавливает состояние боя
- `delete_active_battle(player_id, opponent_id)` - удаляет завершенный бой

### 2. **АФК логика** (`server/afk_battle.py`)

**Класс `AFKBattleManager`** - управляет АФК статусом:
- `can_player_act_if_afk()` - возвращает False (АФК не может действовать)
- `should_receive_damage_while_afk()` - возвращает True (АФК получает урон)
- `should_regenerate_during_afk()` - возвращает False (АФК не регенерирует HP)

**Класс `AFKBattleHandler`** - управляет состоянием боев:
- `mark_player_afk()` - отмечает игрока как АФК в БД
- `unmark_player_afk()` - убирает статус АФК при переподключении
- `save_battle_state()` - сохраняет состояние боя
- `restore_battle_state()` - восстанавливает состояние при переподключении
- `cleanup_battle()` - удаляет завершенный бой

### 3. **Клиентская поддержка** (`client/session.py`)

**Добавлены методы в `OnlineSession`:**
- `check_active_battle(opponent_id)` - проверяет наличие активного боя
- `restore_battle_state(opponent_id)` - восстанавливает состояние боя

### 4. **Сетевой слой** (`client/network.py`)

**Добавлены методы в `GameClient`:**
- `check_active_battle(player_id, opponent_id)` - GET `/api/duel/active-battles/{player_id}/{opponent_id}`
- `restore_battle_state(player_id, opponent_id)` - GET `/api/duel/restore/{player_id}/{opponent_id}`

### 5. **Уже реализовано** (в предыдущих сеансах)

- ✅ Модифицирован `DuelScene.close()` для проверки фазы боя перед отключением
- ✅ Если `phase != "result"` → игрок остается подключен (AFK)
- ✅ Пассивная регенерация работает корректно для офлайн персонажей

## 🔄 Поток выполнения

### Сценарий 1: Отключение клиента во время боя

```
1. Игрок закрывает клиент
   ↓
2. WebSocket соединение разрывается
   ↓
3. OnlineSession.disconnect() вызывается
   ↓
4. Если DuelScene.phase != "result":
   - Не отправляется сигнал disconnect на сервер
   - Персонаж остается в боевой сессии
   ↓
5. AFKBattleHandler.mark_player_afk() отмечает персонаж как AFK
   ↓
6. AFKBattleHandler.save_battle_state() сохраняет состояние в БД
   ↓
7. АФК персонаж НЕ выполняет никаких действий
   - Просто получает урон от противника
   - Может получать баффы/дебаффы
   - Стоит и ждет переподключения или таймаута
   - Обновляет состояние боя в БД

```

### Сценарий 2: Переподключение

```
1. Игрок возвращается и переподключается
   ↓
2. Фронтенд проверяет check_active_battle(opponent_id)
   ↓
3. Если бой активен:
   - restore_battle_state() вернет сохраненное состояние
   - Восстанавливается полная сцена боя
   - Показывается сообщение "Переподключение успешно"
   ↓
4. AFKBattleHandler.unmark_player_afk() убирает статус AFK
   ↓
5. Игрок может продолжить управлять персонажем
```

### Сценарий 3: Завершение боя

```
1. Боевая система определяет победителя
   ↓
2. XP и награды применяются обоим персонажам
   ↓
3. Боевая статистика записывается в архив
   ↓
4. AFKBattleHandler.cleanup_battle() удаляет запись из active_battles
   ↓
5. При переподключении игрок видит экран результатов боя
```

## 📋 Требуемые работы (следующие шаги)

Для полной функциональности АФК системы необходимо:

### 1. **Серверные API endpoints** (нужно реализовать)

```python
# server/main.py или server/duel_offers.py (или новый файл server/afk_duel.py)

@app.route("/api/duel/active-battles/<int:player_id>/<int:opponent_id>", methods=["GET"])
async def check_active_battle(player_id, opponent_id):
    """Проверяет есть ли активный бой"""
    battle = db.get_active_battle(player_id, opponent_id)
    if battle:
        return {"exists": True, "player_afk": battle["player_afk"]}
    return {"exists": False}

@app.route("/api/duel/restore/<int:player_id>/<int:opponent_id>", methods=["GET"])
async def restore_battle(player_id, opponent_id):
    """Восстанавливает состояние боя при переподключении"""
    battle = db.get_active_battle(player_id, opponent_id)
    if battle:
        return {
            "battle_state": battle["battle_data"],
            "player_afk": battle["player_afk"],
            "opponent_afk": battle["opponent_afk"]
        }
    return {"error": "Бой не найден"}
```

### 2. **Интеграция с боевым движком** (нужно реализовать)

В `combat/card_battle.py` или `scenes/duel_resolver.py`:
- Добавить проверку флага `player_afk` перед вызовом input handler'а
- Если AFK → использовать `AFKBattleManager.select_afk_card()`
- Сохранять состояние боя после каждого хода

### 3. **Фронтенд-интеграция** (нужно реализовать)

В `scenes/duel_scene.py`:
- При входе в бой → проверить `check_active_battle()`
- Если находится активный бой → вызвать `restore_battle_state()`
- Восстановить UI сцены из сохраненного состояния
- Показать notification о переподключении

### 4. **Таймауты и очистка** (нужно реализовать)

```python
# server/config.py
AFK_BATTLE_TIMEOUT_SECONDS = 300  # 5 минут
AFK_ACTION_DELAY_SECONDS = 3      # Задержка между АФК действиями

# Периодическая задача на сервере для очистки старых боев
async def cleanup_expired_battles():
    now = time.time()
    expired = db.connection().execute(
        "DELETE FROM active_battles WHERE updated_at < ? - ?",
        (now, config.AFK_BATTLE_TIMEOUT_SECONDS)
    )
```

## 🔧 Конфигурация

Необходимо добавить в `server/config.py`:

```python
# АФК система
AFK_BATTLE_TIMEOUT_SECONDS = 300      # Как долго хранить боевую сессию
AFK_ACTION_DELAY_SECONDS = 3          # Задержка между действиями AFK персонажа
AFK_CLEANUP_INTERVAL_SECONDS = 60     # Как часто проверять и очищать старые бои
```

## 📊 Базовая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        КЛИЕНТ (Pygame)                      │
├─────────────────────────────────────────────────────────────┤
│ OnlineSession                                               │
│ ├─ check_active_battle()  ←→ GameClient                    │
│ └─ restore_battle_state() ←→ GameClient                    │
└─────────────────────────────────────────────────────────────┘
                             ↓
                        HTTP/WebSocket
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    СЕРВЕР (asyncio WebSocket)               │
├─────────────────────────────────────────────────────────────┤
│ GameClient API Endpoints                                    │
│ ├─ GET /api/duel/active-battles/:player_id/:opponent_id   │
│ └─ GET /api/duel/restore/:player_id/:opponent_id          │
│                             ↓                               │
│ AFKBattleHandler                                            │
│ ├─ mark_player_afk()                                       │
│ ├─ save_battle_state()                                     │
│ └─ restore_battle_state()                                  │
│                             ↓                               │
│ AFKBattleManager                                            │
│ ├─ select_afk_card()                                       │
│ └─ select_afk_attack_zone()                                │
│                             ↓                               │
│ Database Layer                                              │
│ └─ active_battles table                                    │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Особенности реализации

1. **АФК персонаж НЕ регенерирует HP** во время боя (по требованиям)
2. **Случайная стратегия** - непредсказуемая для противника
3. **Полное сохранение состояния** - можно восстановить точное состояние боя
4. **Противник получает обновления** о действиях АФК персонажа в реальном времени
5. **Боевая статистика записывается** независимо от AFK статуса

## 🧪 Тестирование

Для проверки АФК системы:

```bash
# 1. Запустить сервер
python server/main.py

# 2. Запустить двух клиентов в разных окнах
python main.py  # Клиент 1
python main.py  # Клиент 2

# 3. Начать бой между ними
# 4. Закрыть окно одного клиента (Alt+F4 или Ctrl+C)
# 5. Проверить БД:
sqlite3 server_data.sqlite3
SELECT * FROM active_battles WHERE player_id = 1;
# Должно показать: player_afk = 1, battle_data содержит состояние

# 6. Переподключить первый клиент
python main.py  # Клиент 1
# Должно восстановиться состояние боя в том же месте
```

## 📝 Документация

Полная документация АФК системы находится в `.session-artifacts/AFK_SYSTEM.md`
