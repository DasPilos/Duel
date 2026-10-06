# Documentation Index

## Start Here

- [README](README.md): project overview and quick start.
- [Architecture](ARCHITECTURE.md): server authority, shared-world boundaries, persistence, and module map.
- [Developer Guide](DEVELOPER_GUIDE.md): local PostgreSQL, server/client launch, and tests.
- [Contributing](CONTRIBUTING.md): branches, review, battle math, and server changes.
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md): GitHub, Z440, and downloadable client release.

## Systems

- [Battle Math](BATTLE_MATH.md): current implementation sources and executable tests.
- [City Population](ARCHITECTURE.md#persistence): PostgreSQL-backed shared city state; implementation in `server/city_population.py`.
- [World Roads](ARCHITECTURE.md#traveling-entities): server road routes and shared travel snapshots.
- `BATTLE_MATH.md`, `tests/test_card_battle.py`, and `tests/test_physical_effects.py`: battle implementation and tests.
- `server/migrations/`: ordered PostgreSQL schema history.

## Historical and Feature References

Feature-specific reports such as `CHANGELOG*.md`, `*_COMPLETED.md`, `*_REPORT.md`, and `*_STATUS.md` record prior work; they are not setup or deployment instructions. Check the current implementation and tests before treating a historical status or proposed design as implemented behavior.

The following old handoff guides describe a retired split between separate warrior and mage developers and are retained only as historical context:

- [ARCHITECTURE_DUAL_SYSTEM.md](ARCHITECTURE_DUAL_SYSTEM.md)
- [HANDOFF_GUIDE.md](HANDOFF_GUIDE.md)
- [OPERATOR2_GUIDE.md](OPERATOR2_GUIDE.md)
- [MAGE_DEVELOPER_GUIDE.md](MAGE_DEVELOPER_GUIDE.md)
