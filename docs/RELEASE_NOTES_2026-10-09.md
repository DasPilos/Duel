# Release Notes: 2026-10-09

## Baseline

Compared with `c9f33e4` (`Add individual citizen ration and starvation system`), which was the same revision on local `main`, `origin/main`, and Z440 before this release. This release contains the current local source changes and PostgreSQL migrations. Runtime state (`bot_state.json`), local VS Code tasks, credentials, virtual environments, and database files are excluded.

## City and Production

- Added shared city population state, citizen satiety/hunger, food consumption, work assignments, return travel, starvation handling, taxes, and population growth.
- Added Governor rates and trends for food and wood. Free citizens are listed first; work assignment only uses free citizens and unoccupied slots.
- Added level-gated production resources, shared production storage, and backpack-capacity-limited withdrawal. Player production is deposited to shared storage; there are no personal harvest shares.
- Added farm progression: level 1 has 500 storage and two workers; Samozakhvat adds a first-field slot and the wooden plough adds +5% wheat speed. Both are required to upgrade the farm to level 2, which has 800 storage and opens a second wheat field with two worker slots. At level 2, “Раздать пай” adds one more slot to field two and the wooden handle adds +8% wheat speed. The two speed upgrades stack to +13%.
- Added timed upgrades, shared treasury/warehouse costs, farm upgrade prerequisites, and migration-backed upgrade state.

## Stable and Transport

- Added shared cart production inventory, multiple cart instances, transport phases, pinned routes, stable/cart upgrades, and cart durability.
- Active carts consume 2 wood per hour; idle carts consume none. Insufficient wood wears the cart, broken carts cannot be dispatched, and repair consumes one wood per restored durability point.
- Added cart fleet status and wear indicators in a horizontal stable view.

## City and Battles

- Refactored city scene rendering/building modules and added city upgrade supply tracking.
- Added persisted battle archive records and a Hall of Fame replay viewer.
- Added world-scoped transport, city, and battle migrations; database migrations apply at server startup.

## Validation and Deployment

- Relevant city, production, transport, farm progression, and UI unittest modules pass.
- Full release validation: `python -m unittest discover -s tests -q`.
- `git diff --check` passes.
- Z440 preserves its existing `bot_state.json` and `venv/`; deployment pulls the committed source and restarts `game-server.service`.
