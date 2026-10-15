# Duel

Multiplayer RPG: a Pygame client and a Python HTTP server. PostgreSQL is the source of truth. All character professions share one world (`WORLD_ID`).

## Quick Start (Windows)

Requirements: Python 3.13, PostgreSQL, and `requirements.txt`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `DATABASE_URL` if the default `postgresql://game@127.0.0.1:5432/game` does not fit. Keep the password in the PostgreSQL password file, never in source control.

Terminal 1, server:

```powershell
$env:HOST = '127.0.0.1'
$env:PORT = '8765'
$env:WORLD_ID = '1'
python -m server.main
```

Terminal 2, online client:

```powershell
python main.py --online --server http://127.0.0.1:8765
```

Without `--online` the client runs in local mode.

## Tests

```powershell
python -m unittest discover -s tests -q
```

Tests create temporary PostgreSQL schemas. Point `TEST_DATABASE_URL` at a disposable database, never at production.

## Documentation

- [AGENTS.md](AGENTS.md): short map and rules for AI assistants and contributors.
- [CONTRIBUTING.md](CONTRIBUTING.md): workflow and change rules.
- [docs/README.md](docs/README.md): index of all project documents.
- [CHANGELOG.md](CHANGELOG.md): history of changes.
