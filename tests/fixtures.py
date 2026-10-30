"""Shared test fixtures and helpers for tests/test_server.py and tests/test_combat.py."""

import os
import threading
import uuid
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

import psycopg

from client.network import GameClient
from server import config
from server.database import Database
from server.items_database import ItemsDatabase
from server.main import GameRequestHandler
from server.world_mobs import WorldService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", config.DATABASE_URL)


def create_test_database(world_id=None):
    """Fresh, isolated PostgreSQL schema with all migrations applied."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    return Database(TEST_DATABASE_URL, schema=schema, world_id=world_id)


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
def running_server(database):
    """Start a GameRequestHandler-backed HTTP server bound to the given database.

    Yields a connected GameClient. The server is always shut down on exit.
    """
    previous_database = GameRequestHandler.database
    previous_items_database = GameRequestHandler.items_database
    previous_world = GameRequestHandler.world
    GameRequestHandler.database = database
    GameRequestHandler.items_database = ItemsDatabase(database)
    GameRequestHandler.world = WorldService(database, GameRequestHandler.items_database)
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    client = GameClient(f"http://127.0.0.1:{http_server.server_port}")
    try:
        yield client
    finally:
        http_server.shutdown()
        http_server.server_close()
        GameRequestHandler.database = previous_database
        GameRequestHandler.items_database = previous_items_database
        GameRequestHandler.world = previous_world
