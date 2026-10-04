"""Applies numbered SQL files from this package exactly once per database schema."""
import time
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent
# Same key in every game process, so worlds starting together never migrate in parallel.
_MIGRATION_LOCK_KEY = 74_210_001


def pending_migrations(applied):
    return [path for path in sorted(MIGRATIONS_DIR.glob("*.sql")) if path.stem not in applied]


def apply_migrations(connection):
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
    done = []
    for path in pending_migrations(applied):
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
            (path.stem, time.time()),
        )
        done.append(path.stem)
    return done
