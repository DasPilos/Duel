# Developer Guide

## Environment

The supported development setup is Python 3.13, Pygame 2.6, and PostgreSQL accessed through psycopg 3. The production database is not the local development database. Keep separate DSNs and never copy production credentials into local files.

Install dependencies in a virtual environment:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The current workspace may use `.venv_313`; use the interpreter selected for that workspace if it is already configured.

## Local PostgreSQL

The default configuration in `server/config.py` is:

- `DATABASE_URL=postgresql://game@127.0.0.1:5432/game`
- `WORLD_ID=1`
- `HOST=0.0.0.0`
- `PORT=8765`

For local-only development, explicitly bind to loopback so the server is not exposed to the LAN:

```powershell
$env:HOST = '127.0.0.1'
$env:PORT = '8765'
$env:WORLD_ID = '1'
python -m server.main
```

The PostgreSQL password belongs in `%APPDATA%\postgresql\pgpass.conf`, not in `server/config.py`, `.env` committed to Git, or command history. The server applies migrations at startup; `WORLD_ID` must refer to an existing world. Confirm `/health` at `http://127.0.0.1:8765/health`.

## Run the Client

In a second terminal, from the repository root:

```powershell
python main.py --online --server http://127.0.0.1:8765
```

Use `--server http://192.168.1.230:8765` only when intentionally connecting to the Z440 server. Do not use the production URL while testing data-changing features.

## Tests

Run the full suite:

```powershell
python -m unittest discover -s tests -q
```

Run the relevant slice first while iterating:

```powershell
python -m unittest tests.test_city_population tests.test_world_terrain -q
python -m unittest tests.test_combat tests.test_card_battle tests.test_physical_effects tests.test_character_stats -q
```

`tests/fixtures.py` creates and drops a temporary PostgreSQL schema. Set `TEST_DATABASE_URL` to a disposable development database. Never point it at production. Some Pygame tests emit harmless libpng profile warnings.

## Change Boundaries

- Put shared domain rules in the owning `server/`, `combat/`, or `core/` module, not in a scene renderer.
- Keep client rendering separate from server-authoritative state.
- Scope database queries by `world_id`; character class must not partition the shared world.
- Add a migration for schema changes. Do not edit already-applied migrations.
- Add or update focused tests for behavior and API contracts.
- Do not include `bot_state.json`, `.vscode/tasks.json`, virtual environments, credentials, or generated archives in a commit.

## Client Package

Build the optional source download archive with:

```powershell
python scripts/build_client_package.py
```

It includes client code and runtime assets only. It does not contain the server, PostgreSQL data, credentials, or test files. `client_package.zip` is generated and intentionally excluded from source commits.
