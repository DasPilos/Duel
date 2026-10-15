# Contributing

Character profession is gameplay data, not a code or world boundary. Warrior, Archer, Assassin, and Mage use the same server, world, economy, and population.

## Workflow

1. Create a focused branch from the current `main`:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/short-description
```

2. Change the module that owns the behavior and add a regression test.
3. Run the focused tests, then the full suite before committing:

```powershell
python -m unittest tests.test_world_stats -q
python -m unittest discover -s tests -q
```

4. Check `git diff --check`, `git status --short`, and the staged diff. Commit only files for your change. Do not commit credentials, database dumps, virtual environments, logs, or `client_package.zip`.

## Rules

- The server is authoritative for shared state: economy, population, production, and combat results.
- Every world-owned database read or write includes `world_id`.
- Check character ownership through the authenticated user before accepting a character-scoped request.
- Schema changes go in a new file under `server/migrations/`. Never edit an applied migration.
- Combat formulas live in `combat/`. Read [docs/BATTLE_MATH.md](docs/BATTLE_MATH.md) before changing them, and add a deterministic test for each change (inject or seed the RNG).
- A warrior-only change must not change other professions unless that is intended and tested.
- Never test against production data or credentials.
