"""Shared test fixtures and helpers for tests/test_server.py and tests/test_combat.py."""

import os
import threading
import uuid
from pathlib import Path
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

import psycopg

from client.network import GameClient
from server import config
from server.database import Database
from server.items_database import ItemsDatabase
from server.main import GameRequestHandler
from front_line.server.world_mobs import WorldService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", config.DATABASE_URL)


def create_test_database(world_id=None, central=False):
    """Fresh, isolated PostgreSQL schema with all migrations applied."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    database = Database(TEST_DATABASE_URL, schema=schema, world_id=world_id, central=central)
    if not central:
        # Колонка игрового псевдонима — миграция центрального сервера; в схеме мира её тоже нужно добавить.
        central_nickname = Path(config.__file__).resolve().parent / "migrations" / "central" / "0085_game_nickname.sql"
        with database.connection() as connection:
            connection.execute(central_nickname.read_text(encoding="utf-8"))
    return database


def drop_test_database(database):
    database.close()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA IF EXISTS "{database.schema}" CASCADE')


def seed_city_treasury(connection, world_id, copper, character_id, faction="light"):
    """Set the city treasury and credit all of it to one contributor, so they can spend it."""
    connection.execute(
        "UPDATE city_population_state SET treasury_copper=%s WHERE world_id=%s AND faction=%s",
        (int(copper), world_id, faction),
    )
    connection.execute(
        """INSERT INTO city_treasury_contributions (world_id, faction, character_id, contributed_copper)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (world_id, faction, character_id)
           DO UPDATE SET contributed_copper = EXCLUDED.contributed_copper""",
        (world_id, faction, int(character_id), int(copper)),
    )


@contextmanager
def running_server(database, mode=None):
    """Start a GameRequestHandler-backed HTTP server bound to the given database.

    Yields a connected GameClient. The server is always shut down on exit.
    """
    if mode == "economy":
        from economy.server.api import EconomyRequestHandler as request_handler
    elif mode == "front_line":
        from front_line.server.api import FrontLineRequestHandler as request_handler
    elif mode is None:
        request_handler = GameRequestHandler
    else:
        raise ValueError(f"Unknown test server mode: {mode}")

    previous_database = request_handler.database
    previous_items_database = request_handler.items_database
    previous_world = request_handler.world
    request_handler.database = database
    request_handler.items_database = ItemsDatabase(database)
    request_handler.world = (
        None if mode == "economy" else WorldService(database, request_handler.items_database)
    )
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), request_handler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    client = GameClient(f"http://127.0.0.1:{http_server.server_port}")
    try:
        yield client
    finally:
        http_server.shutdown()
        http_server.server_close()
        request_handler.database = previous_database
        request_handler.items_database = previous_items_database
        request_handler.world = previous_world
