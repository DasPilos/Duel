# Duel

Duel is a multiplayer RPG with a Pygame client and a Python HTTP server. PostgreSQL is the persistent source of truth. All character classes use the same client and join the shared world selected by `WORLD_ID`; class does not create a separate map, castle, economy, or population.

## Quick Start (Windows)

Requirements: Python 3.13, PostgreSQL, and the dependencies in `requirements.txt`.

1. Create a virtual environment and install dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Configure PostgreSQL locally. The default DSN is `postgresql://game@127.0.0.1:5432/game`; put credentials in PostgreSQL's password file, never in source control. Confirm the configured world exists.

3. Start the local server in Terminal 1:

```powershell
$env:HOST = '127.0.0.1'
$env:PORT = '8765'
$env:WORLD_ID = '1'
python -m server.main
```

4. Start the online client in Terminal 2:

```powershell
python main.py --online --server http://127.0.0.1:8765
```

The client defaults to local mode when `--online` is omitted. Use an explicit server URL; `127.0.0.1` is local, while `192.168.1.230` is the Z440 host on the private network.

## Tests

```powershell
python -m unittest discover -s tests -q
```

For a focused check:

```powershell
python -m unittest tests.test_city_population tests.test_world_terrain -q
python -m unittest tests.test_combat tests.test_card_battle tests.test_physical_effects -q
```

Tests create temporary PostgreSQL schemas. Never set `TEST_DATABASE_URL` to production credentials or a production database.

## Client Package

The repository contains the client source, not a committed generated ZIP. Build the downloadable source package with:

```powershell
python scripts/build_client_package.py
```

This creates `client_package.zip`; the running server can serve it at `/download/client`. It is a Python source package, not a standalone executable. See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) and [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

## Project Guides

- [Architecture](ARCHITECTURE.md)
- [Local development](DEVELOPER_GUIDE.md)
- [Contributing, including battle math](CONTRIBUTING.md)
- [Battle math source map](BATTLE_MATH.md)
- [Deployment](DEPLOYMENT_CHECKLIST.md)
- [Documentation index](DOCUMENTATION_INDEX.md)
- [Z440 monitor](SERVER_MONITOR.md)
