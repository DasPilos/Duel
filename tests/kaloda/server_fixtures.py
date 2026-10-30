"""Фикстуры серверных тестов Колоды.

Каждому тесту достаются две свежие схемы PostgreSQL: «общая» с таблицами Оператора 1 (users, sessions, worlds)
и своя игровая схема Колоды, как на настоящем сервере. Таблицы Оператора 1 поднимаются его же миграциями.
"""

import os
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

import psycopg

from kaloda.client import KalodaClient
from kaloda.server import config
from kaloda.server.database import Database
from server.database import Database as SharedDatabase

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", config.DATABASE_URL)
TEST_WORLD_ID = 9
TEST_WORLD_CODE = "kaloda_test"


def create_test_database():
    suffix = uuid.uuid4().hex[:12]
    shared_schema, game_schema = f"test_shared_{suffix}", f"test_kaloda_{suffix}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{shared_schema}"')
    shared = SharedDatabase(TEST_DATABASE_URL, schema=shared_schema)
    with shared.connection() as connection:
        connection.execute(
            "INSERT INTO worlds (id, code, name, status, created_at) VALUES (%s, %s, %s, 'open', %s)",
            (TEST_WORLD_ID, TEST_WORLD_CODE, "Колода (тест)", time.time()),
        )
    database = Database(
        TEST_DATABASE_URL, schema=game_schema, shared_schema=shared_schema, world_id=TEST_WORLD_ID
    )
    database.shared_database = shared
    return database


def drop_test_database(database):
    database.close()
    database.shared_database.close()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        for schema in (database.schema, database.shared_schema):
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def create_second_world(database, world_id=TEST_WORLD_ID + 1):
    """Второй мир Колоды в тех же схемах: для проверки, что миры не смешивают данные."""
    with database.shared_database.connection() as connection:
        connection.execute(
            "INSERT INTO worlds (id, code, name, status, created_at) VALUES (%s, %s, %s, 'open', %s)",
            (world_id, f"{TEST_WORLD_CODE}_{world_id}", "Колода 2 (тест)", time.time()),
        )
    return Database(
        database.dsn, schema=database.schema, shared_schema=database.shared_schema, world_id=world_id
    )


@contextmanager
def running_server(database):
    """Поднимает HTTP-сервер Колоды на свободном порту и отдаёт подключённого KalodaClient."""
    from kaloda.server.main import GameRequestHandler, bind_database

    previous = bind_database(database)
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    client = KalodaClient(f"http://127.0.0.1:{http_server.server_port}")
    try:
        yield client
    finally:
        http_server.shutdown()
        http_server.server_close()
        bind_database(*previous)
