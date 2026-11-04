"""Редактор карт Колоды: рисование локально, черновики в папке map_drafts, сервер нужен для сохранения и публикации.

Пример: python -m kaloda.editor --server http://127.0.0.1:8766
Для сохранения и публикации на сервер нужен вход модератора. Логин и пароль можно передать через --username и --password
или переменные GAME_USERNAME и GAME_PASSWORD. Иначе вход открывается окном внутри редактора.
"""
import argparse
import os
import sys

import pygame

from kaloda.client import ServerError
from kaloda.editor.catalog import catalog_definitions
from kaloda.editor.client import EditorClient
from kaloda.editor.scene import MapEditorScene
from kaloda.editor.ui import LoginPrompt
from kaloda.settings import FONT_NAME, FPS, HEIGHT, WIDTH

DEFAULT_SERVER = "http://127.0.0.1:8766"


def parse_args():
    parser = argparse.ArgumentParser(description="Редактор карт Колоды")
    parser.add_argument("--server", default=os.getenv("GAME_SERVER", DEFAULT_SERVER))
    parser.add_argument("--username", default=os.getenv("GAME_USERNAME"))
    parser.add_argument("--password", default=os.getenv("GAME_PASSWORD"))
    return parser.parse_args()


def ask_login(screen, clock, font, small, username, message=""):
    """Окно входа внутри редактора: крутит свой цикл событий, поэтому окно не замирает. None — отмена."""
    background = screen.copy()
    prompt = LoginPrompt(font, small, username)
    prompt.message = message
    pygame.key.start_text_input()
    try:
        while True:
            clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                result = prompt.handle_event(event)
                if result == "cancel":
                    return None
                if result == "submit" and all(prompt.values()):
                    return prompt.values()
            screen.blit(background, (0, 0))
            prompt.draw(screen)
            pygame.display.flip()
    finally:
        pygame.key.stop_text_input()


def make_login(client, args, ask):
    """Вход на сервер: из аргументов или окна входа; при неверном пароле окно открывается снова с текстом ошибки."""
    def login():
        if client.token:
            return True
        username, password = args.username or "", args.password or ""
        message = ""
        while True:
            if not (username and password):
                values = ask(username, message)
                if values is None:
                    return False
                username, password = values
            try:
                client.login(username, password)
                return True
            except ServerError as error:
                message = f"Вход не выполнен: {error}\nКарта не сохранена"
                password = ""
    return login


def main():
    args = parse_args()
    client = EditorClient(args.server, timeout=10)

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Колода: редактор карт")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(FONT_NAME, 20)
    small = pygame.font.SysFont(FONT_NAME, 15)

    def ask(username, message):
        return ask_login(screen, clock, font, small, username, message)

    scene = MapEditorScene(client, catalog_definitions(), make_login(client, args, ask))

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if scene.handle_event(event):
                running = False
        scene.draw(screen)
        pygame.display.flip()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
