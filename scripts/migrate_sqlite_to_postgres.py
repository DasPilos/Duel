"""One-time transfer of player data from the legacy SQLite file into PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_postgres.py --characters 1=1,2=2 --dry-run
    python scripts/migrate_sqlite_to_postgres.py --characters 1=1,2=2

--characters lists CHARACTER_ID=WORLD_ID pairs to transfer. Their owners, NPC characters
(user_id 0) and every row belonging to them are copied; everything else is skipped.
The SQLite file is opened read-only. All writes happen in one PostgreSQL transaction and are
compared row by row with the source before commit; any mismatch rolls everything back.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import config  # noqa: E402
from server.database import SYSTEM_USER_ID, Database  # noqa: E402
from server.items_database import ItemsDatabase  # noqa: E402

NPC_WORLD_ID = 1

# Tables whose rows belong to one character through character_id.
CHARACTER_TABLES = (
    "character_items",
    "character_equipment",
    "character_storage",
    "character_decks",
    "battle_rewards",
    "character_card_collection",
    "character_item_grants",
    "character_inventory",
    "chat_reads",
)

IDENTITY_TABLES = (
    "users", "characters", "chat_messages", "chat_reports", "active_battles", "battle_logs",
    "drinks", "character_inventory", "character_card_collection", "character_items",
    "character_equipment", "character_storage", "character_decks", "battle_rewards",
)


class VerificationError(RuntimeError):
    pass


def parse_mapping(raw):
    mapping = {}
    for pair in raw.split(","):
        character_id, world_id = pair.split("=")
        mapping[int(character_id)] = int(world_id)
    return mapping


def sqlite_tables(source):
    return {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def select_rows(source, query, params=()):
    cursor = source.execute(query, params)
    columns = [item[0] for item in cursor.description]
    return columns, [dict(zip(columns, row)) for row in cursor.fetchall()]


def placeholders(ids):
    return ",".join("?" for _ in ids)


def insert_rows(connection, table, rows, extra=None):
    for row in rows:
        values = dict(row)
        if extra:
            values.update(extra(row))
        columns = list(values)
        connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
            [values[column] for column in columns],
        )


def verify_rows(connection, table, key_columns, expected_rows, extra=None):
    """Every expected row must exist in PostgreSQL with identical values."""
    for row in expected_rows:
        expected = dict(row)
        if extra:
            expected.update(extra(row))
        key = [row[column] for column in key_columns]
        where = " AND ".join(f"{column} = %s" for column in key_columns)
        actual = connection.execute(
            f"SELECT {', '.join(expected)} FROM {table} WHERE {where}",
            key,
        ).fetchone()
        if actual is None:
            raise VerificationError(f"{table}: строка {key} не перенесена")
        for column, value in expected.items():
            if actual[column] != value:
                raise VerificationError(
                    f"{table}.{column} для {key}: SQLite={value!r} PostgreSQL={actual[column]!r}"
                )
    return len(expected_rows)


def ensure_empty_target(connection):
    users = connection.execute("SELECT COUNT(*) AS amount FROM users WHERE id <> %s", (SYSTEM_USER_ID,)).fetchone()
    characters = connection.execute("SELECT COUNT(*) AS amount FROM characters").fetchone()
    if users["amount"] or characters["amount"]:
        raise SystemExit(
            "В PostgreSQL уже есть игроки или персонажи. Перенос выполняется только в пустую базу."
        )


def migrate(source, connection, mapping):
    report = []
    tables = sqlite_tables(source)
    requested = sorted(mapping)

    _, chosen = select_rows(source, f"SELECT * FROM characters WHERE id IN ({placeholders(requested)})", requested)
    missing = set(requested) - {row["id"] for row in chosen}
    if missing:
        raise SystemExit(f"В SQLite нет персонажей: {sorted(missing)}")
    _, npcs = select_rows(source, "SELECT * FROM characters WHERE user_id = ?", (SYSTEM_USER_ID,))
    characters = chosen + npcs
    character_ids = [row["id"] for row in characters]
    world_of = {row["id"]: mapping.get(row["id"], NPC_WORLD_ID) for row in characters}

    owner_ids = sorted({row["user_id"] for row in chosen})
    _, users = select_rows(source, f"SELECT * FROM users WHERE id IN ({placeholders(owner_ids)})", owner_ids)
    insert_rows(connection, "users", users)
    report.append(("users", verify_rows(connection, "users", ["id"], users)))

    with_world = lambda row: {"world_id": world_of[row["id"]]}  # noqa: E731
    insert_rows(connection, "characters", characters, with_world)
    report.append(("characters", verify_rows(connection, "characters", ["id"], characters, with_world)))

    _, drinks = select_rows(source, "SELECT * FROM drinks")
    for drink in drinks:
        existing = connection.execute("SELECT name FROM drinks WHERE id = %s", (drink["id"],)).fetchone()
        if existing is None:
            insert_rows(connection, "drinks", [drink])
        elif existing["name"] != drink["name"]:
            raise VerificationError(f"drinks.id={drink['id']}: SQLite «{drink['name']}», PostgreSQL «{existing['name']}»")
    report.append(("drinks", len(drinks)))

    keys = {
        "character_item_grants": ["character_id"],
        "chat_reads": ["character_id", "location"],
    }
    for table in CHARACTER_TABLES:
        if table not in tables:
            continue
        _, rows = select_rows(
            source, f"SELECT * FROM {table} WHERE character_id IN ({placeholders(character_ids)})", character_ids
        )
        insert_rows(connection, table, rows)
        report.append((table, verify_rows(connection, table, keys.get(table, ["id"]), rows)))

    if "farm_states" in tables:
        report.extend(migrate_farm(source, connection, tables, character_ids))

    _, messages = select_rows(
        source,
        f"SELECT * FROM chat_messages WHERE sender_character_id IN ({placeholders(character_ids)})",
        character_ids,
    )
    sender_world = lambda row: {"world_id": world_of[row["sender_character_id"]]}  # noqa: E731
    insert_rows(connection, "chat_messages", messages, sender_world)
    report.append(("chat_messages", verify_rows(connection, "chat_messages", ["id"], messages, sender_world)))

    for table, column, key in (
        ("chat_reports", "reporter_character_id", ["id"]),
        ("chat_mutes", "muted_character_id", ["character_id", "muted_character_id"]),
        ("active_battles", "player_id", ["id"]),
        ("battle_logs", "player_id", ["id"]),
    ):
        _, rows = select_rows(source, f"SELECT * FROM {table} WHERE {column} IN ({placeholders(character_ids)})", character_ids)
        insert_rows(connection, table, rows)
        report.append((table, verify_rows(connection, table, key, rows)))

    # Next generated id must follow the copied ones; empty tables start from 1.
    for table in IDENTITY_TABLES:
        connection.execute(
            f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                              GREATEST(COALESCE(MAX(id), 0), 1), MAX(id) IS NOT NULL)
                FROM {table}"""
        )
    return report, characters, world_of


def migrate_farm(source, connection, tables, character_ids):
    """Старые farm_* из SQLite -> таблицы зданий (building = 'farm')."""
    ids = placeholders(character_ids)
    _, farms = select_rows(source, f"SELECT * FROM farm_states WHERE character_id IN ({ids})", character_ids)
    states = [
        {"character_id": row["character_id"], "building": "farm", "level": row["level"],
         "cycle_start_time": row["cycle_start_time"]}
        for row in farms
    ]
    resources = [
        {"character_id": row["character_id"], "building": "farm", "resource": crop,
         "storage": row[f"storage_{crop}"], "buffer": row.get(f"buffer_{crop}", 0)}
        for row in farms
        for crop in ("wheat", "flax", "cotton")
        if f"storage_{crop}" in row
    ]
    slots = []
    if "farm_worker_slots" in tables:
        _, rows = select_rows(source, f"SELECT * FROM farm_worker_slots WHERE character_id IN ({ids})", character_ids)
        slots = [{**row, "building": "farm"} for row in rows]

    insert_rows(connection, "building_states", states)
    insert_rows(connection, "building_resources", resources)
    insert_rows(connection, "building_worker_slots", slots)
    return [
        ("building_states", verify_rows(connection, "building_states", ["character_id", "building"], states)),
        ("building_resources", verify_rows(connection, "building_resources", ["character_id", "building", "resource"], resources)),
        ("building_worker_slots", verify_rows(connection, "building_worker_slots", ["character_id", "building", "slot_index"], slots)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--characters", required=True, help="CHARACTER_ID=WORLD_ID через запятую, например 1=1,2=2")
    parser.add_argument("--sqlite", default=str(config.LEGACY_SQLITE_PATH))
    parser.add_argument("--dsn", default=config.DATABASE_URL)
    parser.add_argument("--dry-run", action="store_true", help="проверить перенос и откатить его")
    args = parser.parse_args()

    mapping = parse_mapping(args.characters)
    source = sqlite3.connect(f"file:{Path(args.sqlite).resolve().as_posix()}?mode=ro", uri=True)
    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("SQLite-файл повреждён, перенос остановлен")

    database = Database(args.dsn)
    ItemsDatabase(database)
    with database.connection() as connection:
        ensure_empty_target(connection)
        report, characters, world_of = migrate(source, connection, mapping)
        if args.dry_run:
            connection.rollback()
    source.close()

    print("Режим: ПРОВЕРКА (изменения отменены)" if args.dry_run else "Режим: ПЕРЕНОС (изменения сохранены)")
    for row in characters:
        print(f"  персонаж {row['id']:>11} «{row['name']}» -> мир {world_of[row['id']]}")
    for table, count in report:
        print(f"  {table:<28} перенесено и сверено строк: {count}")


if __name__ == "__main__":
    main()
