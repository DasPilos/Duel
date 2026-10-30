# Сервер и клиент

## Настройки (`server/config.py`)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql://game@127.0.0.1:5432/game` | PostgreSQL DSN. Пароль — в pgpass, не в коде |
| `DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE` | `1` / `20` | Размер пула соединений |
| `WORLD_ID` | `1` | Мир, который обслуживает сервер; должен существовать в БД. `2` включает карту «Башня» (125×125, см. `docs/WORLD_MAP_SYSTEM.md`) |
| `HOST` / `PORT` | `0.0.0.0` / `8765` | Адрес прослушивания |
| `SERVER_TIMEZONE` | `Europe/Kyiv` | Часовой пояс игрового времени |
| `CITY_TICK_INTERVAL_SECONDS` | `1` | Период фонового тика города |
| `CITY_CATCHUP_HOURS_PER_PASS` | `168` | Сколько часов города догоняется за один проход |

Для локальной разработки привязывайте сервер к `127.0.0.1`, чтобы он не был доступен из сети.

## Запуск

```powershell
$env:HOST = '127.0.0.1'; $env:PORT = '8765'; $env:WORLD_ID = '1'
python -m server.main
```

Миграции применяются при запуске из `server/migrations/`. Проверка: `http://127.0.0.1:8765/health`.

Опциональный WebSocket-чат запускается отдельно: `python -m server.realtime` (нужен пакет `websockets`). Без него клиент использует HTTP.

## Клиент

```powershell
python main.py --online --server http://127.0.0.1:8765
```

Адрес сервера задаётся флагом `--server`. Не используйте рабочий сервер при тестировании функций, которые меняют данные.

## API (`server/main.py`)

- Сервис: `/health`, `/api/server/status`, `/api/server/restart-notice`, `/download/client`.
- `/api/server/status` отдаёт `build_id` — хэш `.py`-файлов `server/`, `core/` и `combat/` (`server/build_info.py`). Клиент сравнивает его при переподключении: если сборка сменилась, показывается «Клиент устарел».
- Вход: `/api/login`, `/api/register`, `/api/sessions/disconnect`.
- Персонажи: `/api/characters` (`POST` принимает `name`, `profession_type` и необязательное `stats`: абсолютные значения характеристик, каждая не ниже 3, сумма потраченных очков не больше 3; выносливость фиксирована в 4), `/api/character/buy_drink`, `/api/character/use_drink`.
- Меню аккаунта: `/api/worlds` (список миров из общей БД с `opens_at`, `closes_at`, `server_url`, `is_open`) и `/api/lobby` (игроки с активной сессией на всех мирах, по `last_seen_at` за последние 15 секунд).
- Мир: `/api/map/terrain`, `/api/world/traveling-citizens`, `/api/world/traveling-convoys`.
- Редактор карт (только модераторы): черновики хранятся локально в `map_drafts/` у художника, сервер их не знает. `POST /api/map/editor/publish` с телом `{"cells": [{"layer","x","y","key"}], "world_id", "name", "map_w", "map_h"}` заменяет опубликованную карту мира в `map_live_cells` и `map_world_publish` и возвращает `{"applied": N, "world_id", "name", "published_at", ...}`. Одна и та же карта может быть опубликована на нескольких мирах. После публикации сервер заменяет terrain мира «Башня» на опубликованную карту без перезапуска: apply_published_map в server/main.py переводит клетки через terrain_from_cells (server/map_editor.py) и вызывает world_map.apply_live_terrain, номер версии растёт (map.version в /api/map/terrain, terrain_version в снимке мира). Клиент видит новую версию в снимке и перечитывает terrain. Игроки и мобы внутри новых препятствий сдвигаются к ближайшей свободной точке. Трава и декор не передаются клиенту, пустая карта возвращает процедурный мир.
- Город: `/api/city/structures`, `/api/buildings/...`, `/api/castle/...`, `/api/forge/...`.
- Инвентарь: `/api/inventory/...`, `/api/equipment/...`, `/api/storage/...`.
- Социальное и чат: `/api/social/...`, `/api/chat/...`.

Полный список и параметры смотрите в `server/main.py`.

## Хранение

- PostgreSQL хранит всё состояние мира: персонажей, население, здания, склады, казну, миры.
- Изменения схемы — новым файлом миграции в `server/migrations/` (сейчас до `0056`). `0056_world_schedule.sql` добавляет в `worlds` nullable-колонки `opens_at`, `closes_at` (Unix-время), `server_url`.
- Состояние боя на карте мира в БД не хранится.

## Публикация клиента

Клиентский пакет — архив с исходниками и ресурсами, не исполняемый файл:

```powershell
python scripts/build_client_package.py
Get-FileHash client_package.zip -Algorithm SHA256
```

Архив создаётся в корне проекта и отдаётся сервером по `/download/client`. Он не версионируется в git. Пересоберите его после изменений клиента или ассетов.

## Развёртывание

1. Проверьте локально: `python -m unittest discover -s tests -q` и `git diff --check`.
2. Опубликуйте проверенный коммит на GitHub.
3. На сервере обновите код только fast-forward (`git pull --ff-only`), не трогая файлы окружения и локальные runtime-файлы.
4. Проверьте синтаксис изменённых модулей (`python -m py_compile ...`).
5. Перезапустите сервис сервера и проверьте `/health`.

Клиентские изменения требуют нового `client_package.zip`. Серверные изменения требуют перезапуска сервера. Не копируйте локальные данные PostgreSQL на сервер, а продуктивные учётные данные не храните в репозитории.

## Монитор сервера (`ops/monitor.py`)

`ops/monitor.py` — локальная терминальная панель только для чтения. Она не открывает HTTP-порт и не отображает учётные данные. Показывает доступность API, состояние сервиса и PostgreSQL, онлайн-игроков, загрузку CPU, память, диск, сеть, время и ошибки журнала.

Ручная проверка на Linux-хосте:

```bash
cd <путь-к-проекту>
<venv>/bin/python -m ops.monitor --once
```

Установка на отдельную консоль (`tty2`): `sudo bash deploy/monitor/install.sh`. Пользователю нужна группа `adm` для чтения журнала. Установка не трогает сервис игры. Возврат к обычной консоли: `sudo systemctl disable --now game-monitor.service` и `sudo systemctl enable --now getty@tty2.service`.

Тесты разбора данных: `python -m unittest tests.test_server_monitor -q`.
