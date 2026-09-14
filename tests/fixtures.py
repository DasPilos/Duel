"""Shared test fixtures and helpers for tests/test_server.py and tests/test_combat.py."""

import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

from client.network import GameClient
from server.main import GameRequestHandler


@contextmanager
def running_server(database):
    """Start a GameRequestHandler-backed HTTP server bound to the given database.

    Yields a connected GameClient. The server is always shut down on exit.
    """
    GameRequestHandler.database = database
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), GameRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    client = GameClient(f"http://127.0.0.1:{http_server.server_port}")
    try:
        yield client
    finally:
        http_server.shutdown()
        http_server.server_close()
