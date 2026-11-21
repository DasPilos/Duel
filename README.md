# Multiverse of Games

Multimode game: a Pygame client connects to a central lobby and to independent Tower, Economy, Deck, or Front Line world servers. PostgreSQL is the source of truth; each mode stores its gameplay data separately.

> **Режимы:** world-server entrypoints and APIs are isolated by mode. Shared services are the account/lobby control plane and visual assets.

The Godot client and its source art library are in [`godot_client/`](./godot_client/). Install Git LFS and run `git lfs pull` after cloning to download binary art assets.

## Quick Start (Windows)

Requirements: Python 3.13, PostgreSQL, and `requirements.txt`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `DATABASE_URL` if the default `postgresql://game@127.0.0.1:5432/game` does not fit. Keep the password in the PostgreSQL password file, never in source control.

Terminal 1, central lobby:

```powershell
$env:HOST = '127.0.0.1'
$env:PORT = '8765'
python -m server.central_main
```

Start a world from the central lobby, or run one mode manually:

```powershell
$env:WORLD_ID = '1'
$env:GAME_SCHEMA = 'tower'
python -m tower.server.main
```

For Economy, use its own schema and entrypoint:

```powershell
$env:WORLD_ID = '1'
$env:GAME_SCHEMA = 'economy'
python -m economy.server.main
```

For Deck, start its separate world server with the central-server-issued mode world ID:

```powershell
$env:DECK_WORLD_ID = '5'
$env:DECK_PORT = '8802'
python -m deck.server.main
```

Online client:

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
