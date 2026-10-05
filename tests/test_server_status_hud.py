import unittest
from types import SimpleNamespace

import pygame

from ui.server_status_hud import ServerStatusHUD


class _Client:
    def __init__(self, status):
        self.status = status
        self.calls = 0

    def get_server_status(self):
        self.calls += 1
        return self.status


class ServerStatusHUDTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.Surface((1920, 1080))

    def tearDown(self):
        pygame.quit()

    def test_draws_online_count_and_restart_button(self):
        client = _Client({"online_players": 4, "restart_notice": None})
        session = SimpleNamespace(client=client, character={"id": 1})
        hud = ServerStatusHUD()
        hud.update(session, 0, visible=True)
        self.assertEqual(client.calls, 1)
        hud.draw(self.screen)

        client.status = {
            "online_players": 4,
            "restart_notice": {
                "restart_at": 1000,
                "seconds_remaining": 180,
                "message": "Сервер получил обновление.",
            },
        }
        hud.poll_elapsed = hud.POLL_SECONDS
        hud.update(session, 0, visible=True)
        hud.draw(self.screen)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=hud.restart_button.center
        )
        self.assertEqual(hud.handle_event(event), "restart_client")

    def test_does_not_poll_when_hidden(self):
        client = _Client({"online_players": 0, "restart_notice": None})
        session = SimpleNamespace(client=client, character={"id": 1})
        hud = ServerStatusHUD()

        hud.update(session, 10, visible=False)

        self.assertEqual(client.calls, 0)