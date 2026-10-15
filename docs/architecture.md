# Архитектура

Актуальная карта проекта. Код является источником истины. История изменений — в [CHANGELOG.md](../CHANGELOG.md) и истории git.

## Слои

```
main.py (CLI, игровой цикл, маршрутизация сцен)
  └─ client/app_flow.py      хелперы цикла: сессии сцен, чекпоинты, инвентарь
  └─ scenes/*                экраны: вход, персонаж, таверна, город, карта мира
       └─ ui/*               отрисовка и окна; без правил игры
       └─ combat/*, core/*   чистые правила и справочники (без сети и Pygame-состояния)
       └─ client/network.py  GameClient → HTTP → server/main.py
server/main.py (ThreadingHTTPServer, GameRequestHandler)
  └─ server/database.py      Database (psycopg, PostgreSQL, world_id)
  └─ server/*                сервисы мира: город, производство, транспорт, казна, чат, события
```

Сервер авторитетен: состояние мира, экономика, население и результаты хранятся и считаются только на сервере. Клиент рисует данные и отправляет действия.

## Поток сцен (`main.py`)

`TitleScene` (вход) → `CharacterScene` (выбор персонажа) → `CreateCharacterScene` (новый персонаж) → `TavernScene` (хаб) → `CharacterRoom` | `CityScene` | `WorldMapScene`.
Переходы между `CityScene` и `WorldMapScene` идут через ворота города. Переходы выполняет `SceneTransition`; сцена сообщает о выходе через `finished` и `navigate`.

Чекпоинт персонажа при выходе собирает `client/app_flow.checkpoint_for_scene`. Восстановление после входа — `scene_for_saved_character`.

## Клиент (`client/`)

- `network.py` — `GameClient`: синхронные HTTP-запросы через `urllib` (таймаут 3 с; 15 с для рельефа). `ServerError` — ошибка ответа сервера.
- `session.py` — `OnlineSession`: персонаж, пассивная регенерация HP, отключение.
- `background_polling.py` — `BackgroundPoller`: фоновый опрос без блокировки игрового цикла.
- `state.py`, `structures.py`, `credentials.py` — локальное состояние, перевод строений в удобный вид, учётные данные.

## Сервер (`server/`)

- `main.py` — маршрутизация HTTP, фоновый тик города (`CITY_TICK_INTERVAL_SECONDS`), запуск сервера.
- `config.py` — все переменные окружения (`WORLD_ID`, `HOST`, `PORT`, `DATABASE_URL`, интервалы тиков).
- `database.py` — `Database`; все чтения и записи мира идут с `world_id`. Миграции лежат в `server/migrations/`.
- `world_map.py`, `world_roads.py`, `structures.py` — рельеф, дороги и строения мира.
- `city_population.py`, `city_upgrade.py` — жители, голод, работа, рост города по часам.
- `production_buildings.py`, `forge.py` — производственные здания и очередь кузницы.
- `transport.py` — диспетчеризация стабильного транспорта и общие караваны.
- `treasury_ledger.py` — вклады игроков в казну города.
- `social.py` (фасад), `chat_cache.py`, `presence.py`, `realtime.py` (опциональный WebSocket-чат).
- `world_events.py` — однократные объявления о переходах состояния мира («Летописец»).
- `maintenance.py` — уведомление о плановой перезагрузке сервера.
- `town/` — серверная логика локаций города.

## Правила и справочники (`combat/`, `core/`)

- `combat/` — характеристики, прогрессия, урон оружия, боевые формулы карты мира (`world_stats.py`). Формулы описаны в [BATTLE_MATH.md](BATTLE_MATH.md).
- `core/` — настройки (`settings.py`), валюта, вес переноски, прогресс повозок, рецепты кузницы, справочник производственных зданий (общий для сервера и клиента), движение игрока.

## UI (`ui/`, `scenes/`)

- `ui/` — окна и панели: `character_card.py` (единственная карточка персонажа), `inventory_window.py`, `castle_window.py`, `stable_window.py`, `production_building_window.py`, `city_storage_window.py`, `chat/`, `character_room/`, `map_travel.py`, `server_status_hud.py`.
- `scenes/city/` — миксины `CityScene`: здания, экстерьер, HUD, модальные окна, отрисовка.
- `scenes/world_map_scene.py` — карта мира (бой с мобами, перемещение, караваны).
- `scenes/player_sprites.py` — общий загрузчик 8-направленных спрайтов для карты мира и города.

## Инварианты

1. Каждое обращение к данным мира передаёт `world_id`.
2. Действия над персонажем проверяются через `Database.character_belongs_to_user`.
3. Изменения схемы — новой миграцией; применённые миграции не переписываются.
4. Серверные расчёты (ресурсы, голод, рост) выполняются на сервере; клиент не принимает таких решений.
5. `combat/` не импортирует Pygame; в `core/` Pygame используется только в `settings.py`.
