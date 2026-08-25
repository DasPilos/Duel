import argparse
import os

import pygame

from core.settings import FPS, HEIGHT, WIDTH
from scenes.duel_scene import DuelScene
from scenes.character_scene import CharacterScene
from scenes.tavern_scene import TavernScene
from scenes.backyard_scene import BackyardScene
from scenes.title_scene import TitleScene


def apply_passive_regen(scene, dt):
    if isinstance(scene, DuelScene):
        return
    session = getattr(scene, "session", None)
    if session is not None:
        session.passive_regenerate(dt)


def parse_args():
    parser = argparse.ArgumentParser(description="Мини-дуэль")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--username", default=os.getenv("GAME_USERNAME"))
    parser.add_argument("--password", default=os.getenv("GAME_PASSWORD"))
    parser.add_argument("--server", default=os.getenv("GAME_SERVER", "http://127.0.0.1:8765"))
    return parser.parse_args()


def main():
    args = parse_args()
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Мини-дуэль")

    clock = pygame.time.Clock()
    if args.online:
        scene = TitleScene(
            args.server,
            args.username or "",
            args.password or "",
        )
        pygame.key.start_text_input()
    else:
        scene = DuelScene()

    try:
        running = True

        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    scene.handle_event(event)

            if args.online and isinstance(scene, TitleScene) and scene.finished:
                pygame.key.stop_text_input()
                if scene.online_session is None:
                    running = False
                elif scene.cancelled:
                    running = False
                else:
                    scene = CharacterScene(scene.online_session)
                    pygame.key.start_text_input()

            elif args.online and isinstance(scene, CharacterScene) and scene.finished:
                pygame.key.stop_text_input()
                if scene.cancelled:
                    scene.session.disconnect()
                    running = False
                else:
                    scene = TavernScene(scene.session)
                    pygame.key.start_text_input()

            elif args.online and isinstance(scene, TavernScene) and scene.finished:
                if scene.cancelled:
                    scene.session.disconnect()
                    running = False
                else:
                    scene = BackyardScene(scene.session)
                    pygame.key.start_text_input()

            elif args.online and isinstance(scene, BackyardScene) and scene.finished:
                if scene.navigate == "tavern" or scene.cancelled:
                    scene = TavernScene(scene.session)
                    pygame.key.start_text_input()
                else:
                    scene = DuelScene(scene.session, scene.opponent)

            elif args.online and isinstance(scene, DuelScene) and scene.return_to_tavern:
                scene.return_to_tavern = False
                scene = TavernScene(scene.online_session)
                pygame.key.start_text_input()

            if args.online:
                apply_passive_regen(scene, dt)
            scene.update(dt)
            scene.draw(screen)

            pygame.display.flip()
    finally:
        scene.close()
        pygame.quit()


if __name__ == "__main__":
    main()
