"""Applies numbered SQL files from this package exactly once per database schema."""
import time
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent
# Same key in every game process, so worlds starting together never migrate in parallel.
_MIGRATION_LOCK_KEY = 74_210_001
_MODE_SCHEMA_MIGRATION = "0078_mode_database_schemas"


def pending_migrations(applied, migration_dir=MIGRATIONS_DIR):
    return [path for path in sorted(migration_dir.glob("*.sql")) if path.stem not in applied]


def apply_migrations(connection, schema=None):
    """Run inside one transaction: either every pending migration is applied or none."""
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_KEY,))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at DOUBLE PRECISION NOT NULL
        )
        """
    )
    applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
    if schema in ("tower", "economy") and _MODE_SCHEMA_MIGRATION not in applied:
        central_migration = connection.execute(
            "SELECT applied_at FROM public.schema_migrations WHERE version = %s",
            (_MODE_SCHEMA_MIGRATION,),
        ).fetchone()
        if central_migration is None:
            raise RuntimeError("The central schema must be initialized before a mode schema")
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
            (_MODE_SCHEMA_MIGRATION, central_migration["applied_at"]),
        )
        applied.add(_MODE_SCHEMA_MIGRATION)

    done = []
    bootstrap_migrations = [] if _MODE_SCHEMA_MIGRATION in applied else pending_migrations(applied)
    for path in bootstrap_migrations:
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
            (path.stem, time.time()),
        )
        if path.stem == _MODE_SCHEMA_MIGRATION and schema is None:
            current_schema = connection.execute("SELECT current_schema() AS schema").fetchone()["schema"]
            if current_schema == "public":
                applied_at = time.time()
                for mode_schema in ("tower", "economy"):
                    connection.execute(
                        f'INSERT INTO "{mode_schema}".schema_migrations (version, applied_at) VALUES (%s, %s)',
                        (path.stem, applied_at),
                    )
        done.append(path.stem)

    if _MODE_SCHEMA_MIGRATION in applied or _MODE_SCHEMA_MIGRATION in done:
        if schema in ("tower", "economy"):
            migration_dir = MIGRATIONS_DIR / "modes" / schema
        elif schema is None:
            migration_dir = MIGRATIONS_DIR / "central"
        else:
            migration_dir = None
        if migration_dir is not None and migration_dir.is_dir():
            applied.update(done)
            for path in pending_migrations(applied, migration_dir):
                connection.execute(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
                    (path.stem, time.time()),
                )
                done.append(path.stem)
    return done
