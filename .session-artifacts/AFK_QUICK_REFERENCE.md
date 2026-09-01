# 🚀 АФК система - Быстрая справка

## Что было сделано

Реализована полная архитектура АФК системы для боев:

### ✅ Завершено (60%)

1. **БД уровень** - таблица `active_battles` + методы
2. **АФК логика** - `AFKBattleManager` и `AFKBattleHandler`  
3. **Клиентская поддержка** - методы восстановления боя
4. **Сетевой слой** - API endpoints структура

### ⚠️ Требуется (40%)

1. Реализовать API endpoints на сервере (`/api/duel/active-battles/`, `/api/duel/restore/`)
2. Интегрировать AFK логику в боевой движок
3. Добавить восстановление боя в DuelScene
4. Реализовать таймауты и очистку старых боев

## Файлы изменены

```
✏️ server/database.py      - добавлена таблица + методы
✨ server/afk_battle.py    - новый файл с логикой
✏️ client/session.py        - методы восстановления
✏️ client/network.py        - API методы
```

## Как это работает

### Отключение клиента
```python
Игрок закрывает окно
  ↓
DuelScene.close() проверяет: phase != "result"?
  ↓ ДА
Игрок не отключается от сервера
  ↓
mark_player_afk() отмечает как AFK в БД
  ↓
save_battle_state() сохраняет состояние боя
  ↓
Сервер продолжает бой с АФК персонажем
```

### Переподключение
```python
Игрок возвращается
  ↓
check_active_battle() - есть активный бой?
  ↓ ДА
restore_battle_state() восстанавливает полное состояние
  ↓
unmark_player_afk() убирает AFK статус
  ↓
Сцена боя отображается как раньше
```

## API endpoints структура

Нужно добавить в `server/main.py`:

```python
@app.route("/api/duel/active-battles/<int:player_id>/<int:opponent_id>")
async def check_active_battle(player_id, opponent_id):
    # Возвращает: {"exists": true/false, "player_afk": 1/0}

@app.route("/api/duel/restore/<int:player_id>/<int:opponent_id>")
async def restore_battle(player_id, opponent_id):
    # Возвращает: {"battle_state": {...}, "player_afk": 1/0}
```

## Классы и методы

### `AFKBattleManager`
```python
select_afk_card(available_cards)        # Выбрать карту
select_afk_attack_zone(valid_zones)     # Выбрать зону
should_regenerate_during_afk()          # False - не регенерирует
get_afk_strategy()                      # 'random'
```

### `AFKBattleHandler`  
```python
mark_player_afk(player_id, opponent_id)           # Отметить как AFK
unmark_player_afk(player_id, opponent_id)         # Убрать AFK
save_battle_state(player_id, opponent_id, data)   # Сохранить
restore_battle_state(player_id, opponent_id)      # Восстановить
cleanup_battle(player_id, opponent_id)            # Удалить
```

## Таблица БД

```sql
active_battles:
- id              INTEGER PRIMARY KEY
- player_id       INTEGER
- opponent_id     INTEGER  
- battle_data     TEXT (JSON состояние боя)
- player_afk      INTEGER (0/1)
- opponent_afk    INTEGER (0/1)
- created_at      REAL
- updated_at      REAL
```

## Конфиг (нужно добавить)

```python
# server/config.py
AFK_BATTLE_TIMEOUT_SECONDS = 300      # Как долго хранить
AFK_ACTION_DELAY_SECONDS = 3          # Задержка между ходами
AFK_CLEANUP_INTERVAL_SECONDS = 60     # Как часто чистить БД
```

## Тестирование

```bash
# 1. Начать бой между двумя игроками
# 2. Закрыть одного (Alt+F4)
# 3. Проверить БД:
sqlite3 server_data.sqlite3
SELECT * FROM active_battles WHERE player_id = 1;
# Должно быть: player_afk=1, battle_data содержит данные

# 4. Переподключить игрока
# 5. Бой должен восстановиться
```

## Документация

Полные руководства в `.session-artifacts/`:
- `AFK_SYSTEM.md` - техническое описание
- `AFK_IMPLEMENTATION_PROGRESS.md` - детальная реализация
- `AFK_IMPLEMENTATION_SUMMARY.md` - это резюме

## Коммиты

```
9841334 Add AFK implementation summary
90c83cf Add AFK system documentation
8cf3ad8 Add AFK battle restoration methods to client
68c2053 Implement AFK battle persistence system
```

---

**Статус:** ✅ Архитектура готова, готово к доработке
**Сложность:** Средняя (основная работа впереди - интеграция)
**Время:** ~3-4 часа для полной реализации
