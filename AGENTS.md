# AGENTS.md

Short map for AI assistants. Read this first; open other files only when the task needs them.

## Entry points

- `main.py` — Pygame client CLI and main loop (`--online`, `--server`, `--username`, `--password`).
- `client/app_flow.py` — scene session, checkpoint, inventory, and disconnect helpers used by `main.py`.
- `server/central_main.py` — always-on account, lobby, mode and world registry (`python -m server.central_main`).
- `front_line/server/main.py` — one Front Line world process (the Tower mode was removed on 2026-11-21).
- `economy/server/main.py` — one Economy world process with production and city APIs.
- `deck/server/main.py` — separate server process for one Deck world.
- `server/config.py` — every environment variable and default.

## Where things live

- `server/` — central services, shared HTTP/database infrastructure, migrations, and shared world-service primitives.
- `front_line/server/`, `economy/server/`, `deck/server/` — separate mode entrypoints and API surfaces. Keep mode rules and route ownership inside their mode package; only account/lobby control-plane services and visual assets are shared.
- `client/` — `GameClient` (HTTP), `OnlineSession`, local state. No game rules.
- `scenes/` — Pygame screens. `scenes/city/` holds `CityScene` mixins; `world_map_scene.py` is the world map.
- `ui/` — windows and panels. Render server state, send actions; no rule decisions.
- `combat/`, `core/` — stats, formulas, and shared reference data. `combat/` has no Pygame imports.
- `tests/` — `unittest` suites; `tests/fixtures.py` creates temporary PostgreSQL schemas.
- `docs/architecture.md` — module map and invariants. History is in `CHANGELOG.md` and git.

## Commands

```powershell
python -m unittest discover -s tests -q        # full suite, about 6 min
python -m unittest tests.<module> -q            # focused run
python -m pyflakes <files>                      # lint changed files
python -m server.central_main                   # central lobby (needs PostgreSQL)
python -m front_line.server.main               # Front Line world (schema tower)
python -m economy.server.main                  # Economy world (needs GAME_SCHEMA=economy)
python -m deck.server.main                     # Deck world (needs DECK_WORLD_ID)
python main.py --online --server http://127.0.0.1:8765
```

## Rules

- Work only in the local copy at `E:\python\game`.
- Do not commit, push, or delete tracked user data without explicit permission.
- Files use CRLF on disk (`core.autocrlf=true`). Preserve line endings when editing with scripts.
- Every world-owned DB read/write passes `world_id`. Character actions go through `Database.character_belongs_to_user`.
- Schema changes need a new migration; never rewrite an applied one.
- Central tables live in `public`; gameplay state is isolated by PostgreSQL schema (`tower`, `economy`, or `deck`). Apply central migrations before starting world processes; put later migrations in `server/migrations/central/` or `server/migrations/modes/<mode>/`.
- Display the modes in the fixed order **Economy, Deck, Front Line**; Deck uses the `deck` key and its own package, API, server process, and PostgreSQL schema.
- Treat every game mode as a separate game with its own rules. During map creation or editing, the selected mode determines which mob and character settings, stats, controls, layouts, and other mode-specific features are available. Never infer that a setting, stat, UI branch, placement rule, or feature in one mode also exists in another; share behavior only when it is intentionally mode-agnostic and explicitly designed that way.
- Palette sprites are visual assets, not shared gameplay rules. Artists may use the same palette sprite differently in different modes; keep each mode's sprite interpretation, role, animation, and gameplay configuration independent.
- The server owns economy, population, and battle outcomes. Do not move those calculations into the client.
- The server must always know what happens on the world map: mob gear, mob HP and damage, kills, rewards, respawn, and special strikes go through the server, not only the client.
- Local server topology: start the central server (`python -m server.central_main`) first on port 8765. It owns account login, the lobby, and the mode/world registry and must work when no gameplay worlds exist. Confirm `http://127.0.0.1:8765/health` responds before starting or restarting world servers. Each world is an independent process owned by exactly one mode; use `tower.server.main`, `economy.server.main`, or `deck.server.main` and the matching database schema. Verify the central server and every started world `/health` endpoint. Never mount one mode's gameplay API or mechanics on another mode's server.
- After any change under `server/`, `front_line/server/`, `economy/server/`, `deck/server/`, `combat/`, `core/`, or to server configuration/migrations, restart the central server first and then each affected Front Line world server (see the scope rule above: Economy and Deck are excluded) so all processes run the same code and schema. Stop only the exact old process IDs; do not use broad process-name termination. Verify health on port 8765 and every affected world port before saying the restart succeeded or changes are active. Tell the user which services/ports were restarted and whether verification passed. If a required service cannot safely be started, restarted, or verified, report that explicitly and do not claim the game is fully running or the changes are in effect.
- Версия 1.0.1 (с 2026-11-22, переход на тайл 16 px) — текущая для сервера (`server/build_info.py`), клиента и редактора Godot (`godot_client/scripts/api_client.gd`). Клиенты и редакторы ниже 1.0.1 сервер отклоняет. Старый код, каталоги `assets/map` и данные под 32 px в новую версию не переносить.
- Scope of server work (mandatory): the Tower mode was removed on 2026-11-21 (its code is gone; the `tower` PostgreSQL schema stays, because Front Line uses it). The Economy server is PAUSED. Development of Economy is fully suspended: do not start, restart, or test its server (`economy.server.main`) and do not change their behaviour unless the user explicitly asks for it. They must not be running: if their processes are found running, stop them by exact PID and report it (the lobby would otherwise show their test worlds as working). The Deck server (`deck.server.main`, `deck/`) is owned exclusively by operator 2 and has card combat that is completely separate from Front Line. Do not start, restart, stop, or edit the Deck server, its worlds, its API, or its schema, and do not break its code. Work on the Front Line mode and the central server only.
- Server restart order (mandatory for every agent): (1) first list the server processes that are ours to restart: the central server (port 8765) and the Front Line world servers (`front_line.server.main`). Do NOT list, stop, or touch Economy or Deck processes, even if they hold ports in 8765 or 8800-8900; the Deck server belongs to operator 2. (2) Stop those exact PIDs and wait until their ports are free. (3) Only then start the central server and check `/health` on 8765. (4) Do NOT start Front Line world servers by hand. The central server maintains exactly one Front Line world (the `front_line_matchmaking` row in `worlds`, mode `front_line`) and starts it itself, then stores its address in the database. A manually started world is a second process for the same world; clients then reach one of them at random. After the central server is up, wait a few seconds and check that exactly one `front_line.server.main` process exists, that its parent is the central server, that the `worlds` address matches its port, and that `/health` and `/api/version` (`build_id` must match the current code) are OK. (5) Confirm that no old Front Line or central PID is still listening. Never start a new process while an old server still holds its port: the client connects through the central registry, so an old world can keep answering and the new code looks like it does nothing. Report the old and new PIDs and the `build_id` to the user.
- Never reset, truncate, or replace PostgreSQL game data as part of a restart. Apply schema changes only through the project's migrations and preserve the existing server environment and database credentials.
- Weapons and shields are never stubs. Every weapon or shield (player, NPC, or mob) comes from the server item catalog (`server/items_database.py` CATALOG) and is placed into slots by id. The client must not create item copies.
- Forest landscape has two palette samples: the first (`dry`) is dry forest with big and small stumps, the second (`live`) is live forest; get them with `palette_landscape("Лесной ландшафт")` and use dry for outskirts and dry patches, live elsewhere.
- Map generation (generators and AI): follow the palette sample rules in `docs/architecture.md` ("Образцы палитры"). Base road and grass tiles come from the sample's `base` list in random order (`palette_group_decor`), decor from its `decor` list in at most 10% of cells and never closer than 3 tiles to other decor of the same layer; trees and bushes only on grass; layers 3 (elevation, impassable) and 4 (rivers) never take trees or bushes. Use `core/map_catalog.py` helpers (`palette_group_decor`, `pick_decor`, `tile_allows_objects`), not ad-hoc rules. Pick border tiles between terrains by shape with `core/terrain_autotile.py` from all fitting tiles of the sample, not from fixed block positions, and use every available tile and block of the database that fits the picture. Mountains and elevations are built with `core/relief_tiling.py` (plateau plus rock wall, tiles matched by shape and edge pixels), never by placing single mountain tiles at random. Main river rule: a river is always 1 tile wide (`RIVER_WIDTH = 1` in `scripts/generate_crossroads_map.py`); it is wider only where the mountain peak tile `ml_r33_c35` is used.
- Comment only code that needs clarification.
- Every screen or scene change in every mode (Economy, Deck, Front Line, and any later mode or world) goes through the shared fade in `godot_client/scripts/scene_transition.gd`: the frame darkens to black, input is blocked, then the next screen appears, as `ui/scene_transition.py` does. Windows, popups, and dialogs inside the current screen do not fade.
- Never put secrets or production DSNs in code, tests, or docs.
