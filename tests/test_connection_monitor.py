import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from client.connection import ConnectionMonitor
from client.network import GameClient, ServerError, ServerUnavailableError
from server.build_info import compute_build_id


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class _Client:
    def __init__(self, status):
        self.status = status
        self.error = None
        self.calls = 0

    def get_server_status(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.status)


class ConnectionMonitorTests(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.monitor = ConnectionMonitor(clock=self.clock)
        self.client = _Client({"build_id": "build-1", "online_players": 1})
        self.session = SimpleNamespace(client=self.client, character={"id": 1})

    def tick(self, seconds=1.0):
        self.clock.now += seconds
        return self.monitor.update(self.session, seconds)

    def go_offline(self):
        self.client.error = ServerUnavailableError("refused")
        self.tick()
        self.tick()
        self.assertEqual(self.monitor.state, ConnectionMonitor.OFFLINE)
        self.client.error = None

    def test_online_server_returns_status_and_records_build(self):
        status = self.tick(0)

        self.assertEqual(status["build_id"], "build-1")
        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)
        self.assertFalse(self.monitor.is_blocking)

    def test_single_failed_poll_does_not_pause_game(self):
        self.client.error = ServerUnavailableError("timeout")

        self.assertIsNone(self.tick())

        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)

    def test_two_failed_polls_show_countdown_for_ten_seconds(self):
        self.go_offline()
        self.client.error = ServerUnavailableError("refused")

        self.tick(4)
        self.assertEqual(self.monitor.remaining_seconds(), 6.0)
        self.assertFalse(self.monitor.expired())

        self.tick(6)
        self.assertEqual(self.monitor.remaining_seconds(), 0.0)
        self.assertTrue(self.monitor.expired())

    def test_reconnect_within_grace_restores_game_and_requests_resync_once(self):
        self.go_offline()
        self.tick(3)

        self.tick()

        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)
        self.assertIsNone(self.monitor.remaining_seconds())
        self.assertTrue(self.monitor.take_reconnected())
        self.assertFalse(self.monitor.take_reconnected())

    def test_restart_with_new_build_marks_client_outdated_without_countdown(self):
        self.tick(0)
        self.client.status = {"build_id": "build-2"}

        self.tick()
        self.tick(60)

        self.assertEqual(self.monitor.state, ConnectionMonitor.OUTDATED)
        self.assertTrue(self.monitor.is_blocking)
        self.assertFalse(self.monitor.expired())
        self.assertFalse(self.monitor.take_reconnected())

    def test_new_build_after_outage_is_outdated_not_resumed(self):
        self.tick(0)
        self.go_offline()
        self.client.status = {"build_id": "build-2"}

        self.tick()

        self.assertEqual(self.monitor.state, ConnectionMonitor.OUTDATED)
        self.assertFalse(self.monitor.take_reconnected())

    def test_outdated_state_stays_while_server_is_down(self):
        self.tick(0)
        self.client.status = {"build_id": "build-2"}
        self.tick()
        self.client.error = ServerUnavailableError("refused")

        self.tick()
        self.tick()

        self.assertEqual(self.monitor.state, ConnectionMonitor.OUTDATED)

    def test_old_server_without_build_id_still_resyncs_after_outage(self):
        self.client.status = {"online_players": 1}
        self.tick(0)
        self.go_offline()

        self.tick()

        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)
        self.assertTrue(self.monitor.take_reconnected())

    def test_session_without_character_resets_pause(self):
        self.go_offline()
        self.session.character = None

        self.monitor.update(self.session, 1.0)

        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)
        self.assertIsNone(self.monitor.remaining_seconds())

    def test_polls_only_once_per_interval(self):
        self.tick(0)
        self.monitor.update(self.session, 0.4)
        self.monitor.update(self.session, 0.4)

        self.assertEqual(self.client.calls, 1)

    def test_server_error_response_does_not_pause_game(self):
        self.client.error = ServerError("Токен недействителен")

        self.tick()

        self.assertEqual(self.monitor.state, ConnectionMonitor.ONLINE)


class BuildIdTests(unittest.TestCase):
    def test_build_id_is_stable_and_changes_with_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("server", "core", "combat"):
                (root / name).mkdir()
            (root / "server" / "main.py").write_text("print(1)\n", encoding="utf-8")

            first = compute_build_id(root)
            self.assertEqual(first, compute_build_id(root))

            (root / "server" / "main.py").write_text("print(2)\n", encoding="utf-8")
            self.assertNotEqual(first, compute_build_id(root))


class NetworkErrorTests(unittest.TestCase):
    def test_unreachable_server_raises_unavailable_error(self):
        client = GameClient("http://127.0.0.1:1", timeout=1)

        with self.assertRaises(ServerUnavailableError):
            client.health()


if __name__ == "__main__":
    unittest.main()
