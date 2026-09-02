# 🖥️ Сервер - Интеграция Инвентаря

## 📋 Статус
✅ **ИНТЕГРИРОВАНА** - ItemsDatabase подключена к основному серверу (PID: 33872)

---

## 🌐 API Endpoints

### GET запросы (получение данных)

#### Получить инвентарь персонажа
```http
GET /api/inventory/{character_id}
Authorization: Bearer {token}
```
**Ответ:**
```json
{
  "inventory": [
    {
      "id": 1,
      "character_id": 123,
      "item_id": 5,
      "quantity": 3,
      "slot_index": 0,
      "created_at": 1234567890
    }
  ]
}
```

#### Получить экипировку персонажа
```http
GET /api/equipment/{character_id}
Authorization: Bearer {token}
```
**Ответ:**
```json
{
  "equipment": {
    "head": {"item_id": 10, "name": "Железный шлем", ...},
    "chest": null,
    "legs": null,
    ...
  }
}
```

#### Получить сундук
```http
GET /api/storage/{character_id}/{storage_type}
Authorization: Bearer {token}
```
Параметры:
- `storage_type`: `"chest1"` или `"chest2"`

**Ответ:**
```json
{
  "storage": [
    {"item_id": 15, "quantity": 50, ...}
  ]
}
```

#### Получить боевые колоды
```http
GET /api/decks/{character_id}
Authorization: Bearer {token}
```
**Ответ:**
```json
{
  "decks": [
    {
      "id": 1,
      "character_id": 123,
      "name": "Основная колода",
      "is_active": true,
      "cards_json": "[...]",
      "created_at": 1234567890
    }
  ]
}
```

---

### POST запросы (действия)

#### Получить инвентарь (альтернатива GET)
```http
POST /api/inventory
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123
}
```

#### Использовать предмет
```http
POST /api/inventory/use
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123,
  "item_id": 5
}
```
**Ответ:**
```json
{
  "used": true
}
```

#### Выбросить предмет
```http
POST /api/inventory/drop
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123,
  "item_id": 5
}
```

#### Надеть экипировку
```http
POST /api/equipment/equip
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123,
  "item_id": 10,
  "slot": "head"
}
```
**Параметры slot:**
- `"head"`, `"chest"`, `"legs"`, `"feet"`, `"hands"`, `"back"`
- `"main_hand"`, `"off_hand"`
- `"ring1"`, `"ring2"`
- `"amulet"`

#### Снять экипировку
```http
POST /api/equipment/unequip
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123,
  "slot": "head"
}
```

#### Получить экипировку (POST альтернатива)
```http
POST /api/equipment
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123
}
```

#### Получить сундук (POST альтернатива)
```http
POST /api/storage
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123,
  "storage_type": "chest1"
}
```

#### Получить колоды (POST альтернатива)
```http
POST /api/decks
Authorization: Bearer {token}
Content-Type: application/json

{
  "character_id": 123
}
```

---

## 🔐 Проверка Безопасности

**На всех эндпоинтах сервер проверяет:**
1. ✅ Валидность токена
2. ✅ Принадлежность персонажа к пользователю
3. ✅ Существование персонажа в БД

**Если персонаж не существует:**
```json
{
  "error": "Персонаж не найден"
}
```

---

## 🎯 Интеграция на Клиенте

Клиент должен:
1. Отправлять токен в заголовке `Authorization: Bearer {token}`
2. Включать `character_id` в body (POST) или URL (GET)
3. Обрабатывать ошибки `400` и `401`

### Пример клиентского запроса (Python):

```python
import requests

# Получить инвентарь
response = requests.get(
    "http://localhost:8765/api/inventory/123",
    headers={"Authorization": f"Bearer {token}"}
)
inventory = response.json()["inventory"]

# Надеть экипировку
response = requests.post(
    "http://localhost:8765/api/equipment/equip",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "character_id": 123,
        "item_id": 10,
        "slot": "head"
    }
)
```

---

## 📊 Архитектура

```
┌─────────────────┐
│   Сервер (8765) │
├─────────────────┤
│   main.py       │
│  (GameRequestHandler)
│                 │
├─ GET endpoints  │
├─ POST endpoints │
└────────┬────────┘
         │
         │ использует
         ▼
┌─────────────────────────┐
│  ItemsDatabase()        │
│  (server/database.py)   │
├─────────────────────────┤
│  • Управление инвентарём│
│  • Управление броней    │
│  • Управление сундуками │
│  • Управление колодами  │
│  • Система добычи       │
└────────┬────────────────┘
         │
         │ хранит/читает
         ▼
┌─────────────────────────┐
│  SQLite Database        │
│  (server_data.sqlite3)  │
├─────────────────────────┤
│  • items_catalog        │
│  • character_inventory  │
│  • character_equipment  │
│  • character_storage    │
│  • character_decks      │
│  • battle_rewards       │
└─────────────────────────┘
```

---

## ⚙️ Конфигурация

Все параметры в `server/config.py`:

```python
HOST = "0.0.0.0"          # Адрес сервера
PORT = 8765               # Порт
TOKEN_TTL_SECONDS = 604800 # Время жизни токена (7 дней)
DATABASE_PATH = "server_data.sqlite3"
```

---

## ✅ Проверка

Сервер **работает и слушает** на `localhost:8765`:

```bash
# Проверить здоровье сервера
curl http://localhost:8765/health

# Ответ:
# {"status": "ok"}
```

---

## 📝 Следующие шаги

1. **Создать HTTP клиент методы** (client/network.py)
   - GET /api/inventory/{id}
   - GET /api/equipment/{id}
   - GET /api/storage/{id}/{type}
   - GET /api/decks/{id}
   - POST /api/inventory/use
   - POST /api/inventory/drop
   - POST /api/equipment/equip
   - POST /api/equipment/unequip

2. **Подстановить в CharacterRoom._load_*()** методы
   - Заменить TODO на настоящие HTTP вызовы

3. **Интеграция с боевой системой**
   - Применить бонусы от экипировки

4. **Обработка добычи после боя**
   - POST /api/rewards/claim

---

Generated: 2026-09-01 18:32 UTC
