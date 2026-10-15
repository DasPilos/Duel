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
- Comment only code that needs clarification.
- Never put secrets or production DSNs in code, tests, or docs.
