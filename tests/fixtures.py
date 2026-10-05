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


@contextmanager
def running_server(database):
    """Start a GameRequestHandler-backed HTTP server bound to the given database.

    Yields a connected GameClient. The server is always shut down on exit.
    """
    previous_database = GameRequestHandler.database
    previous_items_database = GameRequestHandler.items_database
    GameRequestHandler.database = database
    GameRequestHandler.items_database = ItemsDatabase(database)
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
