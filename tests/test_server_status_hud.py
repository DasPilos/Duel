import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pygame

from ui.server_status_hud import ServerStatusHUD
from ui.chat.widgets import MessageItem


class ServerStatusHUDTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.Surface((1920, 1080))

    def tearDown(self):
        pygame.quit()

    def test_draws_online_count_and_restart_button(self):
        hud = ServerStatusHUD()
        hud.apply_status({"online_players": 4, "restart_notice": None})
        hud.draw(self.screen)

        hud.apply_status({
            "online_players": 4,
            "restart_notice": {
                "restart_at": 1000,
                "seconds_remaining": 180,
                "message": "Сервер получил обновление.",
            },
        })
        hud.draw(self.screen)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=hud.restart_button.center
        )
        self.assertEqual(hud.handle_event(event), "restart_client")

    def test_clock_formats_server_epoch_in_kiev_timezone(self):
        hud = ServerStatusHUD()
        hud.server_time = datetime(2025, 1, 1, 22, 59, 59, tzinfo=timezone.utc).timestamp()
        hud.server_time_received_at = 100.0
        with patch("ui.server_status_hud.time.monotonic", return_value=101.0):
            self.assertEqual(hud._server_clock_text(), "01:00:00")

    def test_chat_timestamp_is_rendered_before_sender_and_text(self):
        item = MessageItem()
        font = pygame.font.Font(None, 18)
        lines = item.wrapped_lines(
            {"sender": "Игрок", "text": "Привет", "time_text": "12:34:56"},
            own=False,
            font=font,
            max_width=500,
        )
        rendered = "".join(text for line in lines for text, _color in line)

        self.assertTrue(rendered.startswith("[12:34:56] Игрок: Привет"))