# Architecture

## Runtime

- `main.py` is the Pygame game client and scene loop.
- `client/` implements HTTP requests, online sessions, presence polling, and client state.
- `server/main.py` routes authenticated HTTP requests.
- `server/` owns game rules and persistence services.
- `server/migrations/` applies PostgreSQL schema migrations at startup.
- `combat/` contains character stats, battle rules, effects, progression, decks, and battle state.
- `scenes/` coordinates gameplay and interaction; `ui/` renders and handles UI input.
- `core/` contains shared settings and domain utilities.

## Authority and Shared World

The server and PostgreSQL are authoritative for persistent state and multiplayer actions. The client may animate or render server snapshots, but must not decide outcomes or write authoritative state directly.

`WORLD_ID` selects the world served by a process. Within that world, all players and character professions (warrior, archer, assassin, and mage professions) share the same map and world systems. There is no player-owned castle or private citizen population. City population is shared by the world's `light` faction. Authorization checks that the requesting account owns its selected character; data such as traveling citizens is then queried for the whole world, not filtered by character class or owner.

World-scoped state must always include `world_id` in database queries. Do not return data from a different `WORLD_ID`.

## Traveling Entities

Citizen travel state is persisted in `city_citizens` (`travel_direction`, `arrival_at`, `job_building`). The server combines that state with the authoritative road polyline from `server/world_roads.py` and returns position, direction, and ETA from `GET /api/world/traveling-citizens`. Every authenticated character in the same world receives the same snapshot. The Pygame client draws those coordinates; it does not independently simulate citizen movement. Snapshot polling uses `client/background_polling.py`.

Player presence is separate: social snapshots refresh live player positions in the in-memory presence service. Presence has a TTL and is not a persistent character-position write on every frame.

## Persistence

PostgreSQL is configured by `DATABASE_URL`; `WORLD_ID` defaults to 1. On Windows, libpq reads passwords from `%APPDATA%\postgresql\pgpass.conf`. Passwords, database dumps, `bot_state.json`, and virtual environments do not belong in commits. `cards.sqlite3` is a static client catalog; it is not the authoritative game database.

Schema changes belong in ordered SQL files under `server/migrations/`. Keep queries parameterized and world-scoped. Use the existing `Database` pool and service classes rather than opening ad-hoc connections in request handlers.

## Battle Rules

Battle calculations are implemented in `combat/` and verified by `tests/test_combat.py`, `tests/test_card_battle.py`, `tests/test_physical_effects.py`, and `tests/test_character_stats.py`. `BATTLE_MATH.md` maps current rules to their source and tests. Update a focused test whenever a balance formula changes.

## Distribution

The source repository is canonical. `scripts/build_client_package.py` generates the optional client ZIP from source and assets. Do not commit generated `client_package.zip`; rebuild it when publishing a download. The server's `/download/client` route serves the generated file if it exists.

## Host Monitoring

`ops/monitor.py` is a separate, read-only console dashboard for Ubuntu Server. It reads host counters from `/proc`, service state through `systemctl`, game errors from the journal, API health from loopback, and online count from PostgreSQL. Its optional systemd unit is documented in [SERVER_MONITOR.md](SERVER_MONITOR.md); it does not participate in the game-server request path.
