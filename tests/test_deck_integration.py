import unittest
import threading
from http.server import ThreadingHTTPServer

from client.network import GameClient, ServerError
from server import main as shared_server
from tests.fixtures import create_test_database, drop_test_database


class ModeServerIsolationTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()

    def tearDown(self):
        drop_test_database(self.database)

    def test_deck_routes_are_not_mounted_on_the_tower_world_server(self):
        previous_database = shared_server.GameRequestHandler.database
        previous_items_database = shared_server.GameRequestHandler.items_database
        shared_server.GameRequestHandler.database = self.database
        shared_server.GameRequestHandler.items_database = None
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), shared_server.GameRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        client = GameClient(f"http://127.0.0.1:{http_server.server_port}")
        try:
            with self.assertRaises(ServerError):
                client._request("GET", "/api/deck/info")
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)
            shared_server.GameRequestHandler.database = previous_database
            shared_server.GameRequestHandler.items_database = previous_items_database


if __name__ == "__main__":
    unittest.main()
