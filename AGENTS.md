# AGENTS.md

Short map for AI assistants. Read this first; open other files only when the task needs them.

## Entry points

- `main.py` — Pygame client CLI and main loop (`--online`, `--server`, `--username`, `--password`).
- `client/app_flow.py` — scene session, checkpoint, inventory, and disconnect helpers used by `main.py`.
- `server/main.py` — HTTP server (`python -m server.main`), request routing, city tick thread.
- `server/config.py` — every environment variable and default.

## Where things live

- `server/` — authoritative game state, PostgreSQL access (`database.py`), migrations (`migrations/`), world services.
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
python -m server.main                           # run server (needs PostgreSQL)
python main.py --online --server http://127.0.0.1:8765
```

## Rules

- Work only in the local copy at `E:\python\game`.
- Do not commit, push, or delete tracked user data without explicit permission.
- Files use CRLF on disk (`core.autocrlf=true`). Preserve line endings when editing with scripts.
- Every world-owned DB read/write passes `world_id`. Character actions go through `Database.character_belongs_to_user`.
- Schema changes need a new migration; never rewrite an applied one.
- The server owns economy, population, and battle outcomes. Do not move those calculations into the client.
- The server must always know what happens on the world map: mob gear, mob HP and damage, kills, rewards, respawn, and special strikes go through the server, not only the client.
- After any change under `server/` (or `combat/`, `core/`, which the server imports), restart the server so it runs the current code. Stop the old `server.main` processes by PID, then start `python -m server.main` again and confirm port 8765 responds.
- Weapons and shields are never stubs. Every weapon or shield (player, NPC, or mob) comes from the server item catalog (`server/items_database.py` CATALOG) and is placed into slots by id. The client must not create item copies.
- Forest landscape has two palette samples: the first (`dry`) is dry forest with big and small stumps, the second (`live`) is live forest; get them with `palette_landscape("Лесной ландшафт")` and use dry for outskirts and dry patches, live elsewhere.
- Map generation (generators and AI): follow the palette sample rules in `docs/architecture.md` ("Образцы палитры"). Base road and grass tiles come from the sample's `base` list in random order (`palette_group_decor`), decor from its `decor` list in at most 10% of cells and never closer than 3 tiles to other decor of the same layer; trees and bushes only on grass; layers 3 (elevation, impassable) and 4 (rivers) never take trees or bushes. Use `core/map_catalog.py` helpers (`palette_group_decor`, `pick_decor`, `tile_allows_objects`), not ad-hoc rules. Pick border tiles between terrains by shape with `core/terrain_autotile.py` from all fitting tiles of the sample, not from fixed block positions, and use every available tile and block of the database that fits the picture. Mountains and elevations are built with `core/relief_tiling.py` (plateau plus rock wall, tiles matched by shape and edge pixels), never by placing single mountain tiles at random. Main river rule: a river is always 1 tile wide (`RIVER_WIDTH = 1` in `scripts/generate_crossroads_map.py`); it is wider only where the mountain peak tile `ml_r33_c35` is used.
- Comment only code that needs clarification.
- Never put secrets or production DSNs in code, tests, or docs.
