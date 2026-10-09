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
## Production Buildings

Workers produce resources independently on per-unit timers. Each completed unit is written directly to the building's shared faction storage; there is no harvest-cycle buffer. Storage capacity is shared across the building's resources. Units that do not fit are discarded, not queued for later. Black-pit gem bonuses roll once per completed coal unit.

Player output is shared exactly like citizen output; there are no personal harvest
shares. Resources can be taken from the common building store through the normal
withdraw action, subject to the building/city unlocks and backpack capacity.

Farm progression: level 1 has 500 storage and two wheat-field slots. “Самозахват”
adds a slot to field one; the separate wooden plough adds 5% wheat speed. Both are
required for farm level 2, which has 800 storage and opens field two with two slots.
At level 2, “Раздать пай” adds a slot to field two and the wooden handle adds 8%
wheat speed. The speed bonuses stack. Farm state is stored in
`building_states.farm_upgrades_json`; the active timer lives on
`farm_upgrade_id`/`farm_upgrade_finish_at`.

Farm slots use regular plot indices plus `FARM_RATION_SLOT_BASE` bonus indices.
Keep the second-field bonus index tied to plot index 1 in
`core/production_buildings.py`, `server/production_buildings.py`, and the
production window's `plot_slots()` mapping.

## Stable and Transport

Every cart instance stores durability in `stable_cart_progress.cart_wear_json`.
Active routes consume 2 wood per hour from the shared warehouse; idle/resting carts
consume none. If the wood balance is insufficient, the unpaid amount reduces
durability. Broken carts cannot dispatch; repair costs one wood per durability
point restored. The cart-tab UI shows all instances in a horizontal row.

## Citizen Rations

Satiety is tracked independently per citizen from 0 to 100%. Idle citizens lose 1% every 150 seconds, citizens traveling to work or driving a convoy lose 1% every 100 seconds, and working citizens lose 1% every 60 seconds. At 30% or below a citizen automatically consumes available barn food toward 100%; partial food restores only its nutrition value (wheat 10%, berries 15%, meat 20%). At 0%, a worker returns to the city and a convoy driver turns the wagon home. Strong hunger then rises by 1% per 60 seconds; food at any point resets strong hunger and restores satiety, while reaching 100% strong hunger marks the citizen dead. Dead citizen rows are retained for convoy history but excluded from active population and work offers. The hourly city tick handles taxes and population growth only; hunger is advanced independently by the 10-second city scheduler and at work/travel state transitions.

## Battle Archive

Online completed duels send one replay record with the battle result. The server stores it idempotently in the world-scoped `battle_archive` table; authenticated clients browse summaries through `GET /api/battles/archive` and retrieve full turn history through `GET /api/battles/archive/{id}`. The character-selection Hall of Fame pages through those records and allows stepping through saved turns. The local `battle_archive/` JSON files remain available for balance analysis.

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
