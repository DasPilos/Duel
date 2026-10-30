import unittest
from types import SimpleNamespace

import pygame

from client.app_flow import leave_to_lobby
from client.network import ServerError
from core import settings
from ui.exit_menu import ExitMenu


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.logins = []

    def login(self, username, password):
        self.logins.append((username, password))
        if self.fail:
            raise ServerError("сервер недоступен")
        return {"username": username}


class FakeSession:
    def __init__(self, fail_login=False):
        self.username = "tester"
        self.password = "secret"
        self.user = {"username": "tester"}
        self.character = {"id": 7, "name": "Тест"}
        self.client = FakeClient(fail=fail_login)
        self.disconnect_calls = []

    def disconnect(self, character=None):
        self.disconnect_calls.append(character)
        self.user = None
        self.character = None


class ExitMenuLobbyButtonTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))

    def tearDown(self):
        pygame.quit()

    def test_lobby_button_is_right_below_quit_and_returns_lobby_action(self):
        menu = ExitMenu()
        menu.open()
        menu.draw(self.screen, self.font, self.small_font)
        quit_button = menu.buttons["quit"]
        lobby_button = menu.buttons["lobby"]
        self.assertEqual(lobby_button.x, quit_button.x)
        self.assertEqual(lobby_button.top, quit_button.bottom + 14)

        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=lobby_button.center)
        self.assertEqual(menu.handle_event(click), "lobby")
        self.assertFalse(menu.is_open)


class LeaveToLobbyTests(unittest.TestCase):
    def test_saves_character_and_logs_back_in_for_lobby(self):
        session = FakeSession()
        scene = SimpleNamespace(session=session)

        result, error = leave_to_lobby(scene)

        self.assertIsNone(error)
        self.assertIs(result, session)
        self.assertEqual(session.disconnect_calls, [{"id": 7, "name": "Тест"}])
        self.assertEqual(session.client.logins, [("tester", "secret")])
        self.assertEqual(session.user, {"username": "tester"})

    def test_returns_error_when_relogin_fails(self):
        session = FakeSession(fail_login=True)
        scene = SimpleNamespace(session=session)

        result, error = leave_to_lobby(scene)

        self.assertIsNone(result)
        self.assertEqual(error, "сервер недоступен")

    def test_returns_error_without_session(self):
        result, error = leave_to_lobby(SimpleNamespace())

        self.assertIsNone(result)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
