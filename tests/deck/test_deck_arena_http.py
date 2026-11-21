"""Маршруты арены на настоящем HTTP-сервере с подменённой базой (без PostgreSQL)."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from deck.map_config import RESPAWN_CRYSTAL
from deck.server import main
from tests.deck.test_deck_arena_service import CHARACTER_ID, USER_ID, FakeDatabase, FakeItems

TOKEN = "arena-test-token"


class HttpDatabase(FakeDatabase):
    world_id = 1

    def user_id_by_token(self, token):
        return USER_ID if token == TOKEN else None

    def load_deck_battle_sessions(self, *args, **kwargs):
        return []

    def get_character(self, user_id, character_id):
        if user_id != USER_ID or int(character_id) != CHARACTER_ID:
            return None
        return dict(self.character)


def call(port, method, path, body=None, token=TOKEN):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


class ArenaHttpTests(unittest.TestCase):
    def setUp(self):
        from tests.deck.test_deck_arena_service import character_payload

        self.database = HttpDatabase(character_payload())
        self.items = FakeItems()
        patcher = mock.patch.object(main.GameRequestHandler, "log_message", lambda *args: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        main.bind_database(self.database, self.items)
        self.server = main.GameHTTPServer(("127.0.0.1", 0), main.GameRequestHandler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        main.bind_database(None)

    def test_start_requires_authorization_and_owned_character(self):
        status, _ = call(self.port, "POST", "/api/deck/arena/start",
                         {"character_id": CHARACTER_ID, "source": "kobold"}, token=None)
        self.assertEqual(status, 401)
        status, payload = call(self.port, "POST", "/api/deck/arena/start",
                               {"character_id": CHARACTER_ID + 1, "source": "kobold"})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_battle_runs_over_http_and_releases_character(self):
        status, payload = call(self.port, "POST", "/api/deck/arena/start",
                               {"character_id": CHARACTER_ID, "source": "kobold"})
        self.assertEqual(status, 200)
        state = payload["arena"]
        self.assertEqual(state["phase"], "draft")
        status, active = call(self.port, "GET", f"/api/deck/arena/active?character_id={CHARACTER_ID}")
        self.assertEqual(active["arena"]["session_id"], state["session_id"])
        status, status_payload = call(self.port, "GET", f"/api/deck/arena/status?character_id={CHARACTER_ID}")
        self.assertEqual(len(status_payload["encounters"]), 6)

        finished = None
        for _ in range(300):
            if state["phase"] == "draft":
                command = {"type": "draft", "card_key": state["draft_cards"][0]["key"]}
            elif state["phase"] == "draw_choice":
                command = {"type": "draw_choice", "card_key": state["draw_choices"][0]["key"]}
            else:
                command = {"type": "end_turn"}
            status, payload = call(self.port, "POST", "/api/deck/arena/action", {
                "character_id": CHARACTER_ID, "session_id": state["session_id"], "command": command,
            })
            self.assertEqual(status, 200, payload)
            state = payload["arena"]["state"]
            if payload["arena"]["finished"] is not None:
                finished = payload["arena"]["finished"]
                break
        self.assertIsNotNone(finished, "бой должен завершиться")
        self.assertIn(finished["result"], ("win", "loss", "teleport"))
        self.assertIsNone(finished["save_error"])
        self.assertIn("character", finished)
        self.assertNotIn("reward_request_id", finished)
        self.assertTrue(self.database.saved)
        if finished["result"] == "loss":
            self.assertEqual(self.database.saved[-1]["position_x"], float(RESPAWN_CRYSTAL["approach_pos"][0]))
        status, active = call(self.port, "GET", f"/api/deck/arena/active?character_id={CHARACTER_ID}")
        self.assertIsNone(active["arena"])

    def test_action_rejects_non_object_command(self):
        status, payload = call(self.port, "POST", "/api/deck/arena/action", {
            "character_id": CHARACTER_ID, "session_id": "x", "command": "end_turn",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
