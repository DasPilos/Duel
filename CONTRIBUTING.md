# Contributing

The repository is shared by all gameplay systems. Character class is gameplay data, not a code or world boundary: warriors, archers, assassins, and mage professions use the same multiplayer world and server services.

## Workflow

1. Update `main` and create a focused branch:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/short-description
```

2. Change the module that owns the behavior and add a regression test.
3. Run the focused tests, then the full suite when practical:

```powershell
python -m unittest tests.test_combat tests.test_card_battle tests.test_physical_effects tests.test_character_stats -q
python -m unittest discover -s tests -q
```

4. Review `git diff --check`, `git status --short`, and the staged diff. Commit only files belonging to your change; push the branch and open a pull request unless the maintainer requests a direct main update.

## Battle Math Contributions

Read [BATTLE_MATH.md](BATTLE_MATH.md) before editing formulas. The implementation is in `combat/`; tests are the executable contract. For each formula change:

- Identify the function that computes the value and every caller.
- Add a deterministic test using an injected/seeded RNG where randomness is involved.
- Cover caps, minimums, class-specific modifiers, equipment, and temporary effects affected by the change.
- Update `BATTLE_MATH.md` only after the code and tests establish the new behavior.
- Do not duplicate combat formulas in UI code or documentation-only implementations.

Battle rules are shared across professions. A warrior-only change must not silently alter mage or archer behavior unless that is intended and tested.

## Server and Database Changes

- The server is authoritative for shared state and game outcomes.
- Include `world_id` in world-owned database reads and writes.
- Authenticate a character through the current user before accepting character-scoped requests.
- Add a new SQL migration for schema changes; do not rewrite an applied migration.
- Never test with production credentials or production data.

## Keep Out of Commits

Do not add credentials, PostgreSQL password files, database dumps, `bot_state.json`, `.vscode/tasks.json`, virtual environments, generated logs, or `client_package.zip`. Build the client package with `python scripts/build_client_package.py` when a downloadable archive is needed.
