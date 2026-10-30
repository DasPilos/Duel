"""Применяет нумерованные SQL-файлы схемы Колоды ровно один раз."""
import time
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent
# Свой ключ: миграции Колоды не блокируются миграциями Оператора 1, а запущенные вместе миры Колоды не мигрируют параллельно.
_MIGRATION_LOCK_KEY = 74_220_001


def pending_migrations(applied):
    return [path for path in sorted(MIGRATIONS_DIR.glob("*.sql")) if path.stem not in applied]


def apply_migrations(connection, schema):
    """Выполняется в одной транзакции: применяются либо все новые миграции, либо ни одной.

    Соединение ищет таблицы в `schema`, а затем в общей схеме, поэтому CREATE TABLE без имени схемы
    попадает в схему Колоды.
    """
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_KEY,))
    connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{schema}".schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at DOUBLE PRECISION NOT NULL
        )
        """
    )
    applied = {row["version"] for row in connection.execute(f'SELECT version FROM "{schema}".schema_migrations')}
    done = []
    for path in pending_migrations(applied):
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            f'INSERT INTO "{schema}".schema_migrations (version, applied_at) VALUES (%s, %s)',
            (path.stem, time.time()),
        )
        done.append(path.stem)
    return done
