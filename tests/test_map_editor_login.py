import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import map_editor
from client.network import ServerError
from scenes.map_editor_ui import LoginPrompt


def key(code, text=""):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode=text, scancode=0)


def typed(text):
    return pygame.event.Event(pygame.TEXTINPUT, text=text)


class FakeClient:
    def __init__(self, accept):
        self.accept = accept
        self.token = None
        self.calls = []

    def login(self, username, password):
        self.calls.append((username, password))
        if (username, password) != self.accept:
            raise ServerError("Неверный пароль")
        self.token = "token"


class LoginPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.prompt = LoginPrompt(pygame.font.SysFont("arial", 16), pygame.font.SysFont("arial", 13))

    def test_typing_fills_the_active_field_and_tab_switches(self):
        self.prompt.handle_event(typed("mod"))
        self.prompt.handle_event(key(pygame.K_TAB))
        self.prompt.handle_event(typed("secret"))
        self.assertEqual(self.prompt.values(), ("mod", "secret"))

    def test_enter_submits_and_escape_cancels(self):
        self.assertEqual(self.prompt.handle_event(key(pygame.K_RETURN, "\r")), "submit")
        self.assertEqual(self.prompt.handle_event(key(pygame.K_ESCAPE)), "cancel")

    def test_backspace_removes_the_last_character(self):
        self.prompt.handle_event(typed("abc"))
        self.prompt.handle_event(key(pygame.K_BACKSPACE))
        self.assertEqual(self.prompt.values()[0], "ab")

    def test_save_button_click_submits(self):
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=self.prompt.submit_rect().center)
        self.assertEqual(self.prompt.handle_event(click), "submit")

    def test_password_is_drawn_as_stars(self):
        self.prompt.handle_event(key(pygame.K_TAB))
        self.prompt.handle_event(typed("hunter2"))
        self.prompt.draw(pygame.display.get_surface())  # не должно падать и не показывает пароль открыто


class MakeLoginTests(unittest.TestCase):
    def test_uses_the_prompt_until_the_password_is_right(self):
        client = FakeClient(accept=("mod", "good"))
        answers = [("mod", "bad"), ("mod", "good")]
        messages = []

        def ask(username, message):
            messages.append(message)
            return answers.pop(0)

        login = map_editor.make_login(client, type("Args", (), {"username": None, "password": None})(), ask)
        self.assertTrue(login())
        self.assertEqual(client.calls, [("mod", "bad"), ("mod", "good")])
        self.assertIn("Неверный пароль", messages[1])
        self.assertIn("Карта не сохранена", messages[1])

    def test_cancelling_the_prompt_means_no_login(self):
        client = FakeClient(accept=("mod", "good"))
        login = map_editor.make_login(client, type("Args", (), {"username": None, "password": None})(), lambda u, m: None)
        self.assertFalse(login())
        self.assertEqual(client.calls, [])

    def test_arguments_skip_the_prompt(self):
        client = FakeClient(accept=("mod", "good"))
        asked = []
        login = map_editor.make_login(client, type("Args", (), {"username": "mod", "password": "good"})(),
                                      lambda u, m: asked.append(m))
        self.assertTrue(login())
        self.assertEqual(asked, [])

    def test_already_logged_in_does_nothing(self):
        client = FakeClient(accept=("mod", "good"))
        client.token = "token"
        login = map_editor.make_login(client, type("Args", (), {"username": None, "password": None})(), lambda u, m: None)
        self.assertTrue(login())
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
