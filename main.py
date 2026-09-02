import argparse
import os

import pygame

from core.settings import FPS, HEIGHT, WIDTH
from scenes.duel_scene import DuelScene
from scenes.character_scene import CharacterScene
from scenes.profession_select_scene import ProfessionSelectScene
from scenes.tavern_scene import TavernScene
from scenes.backyard_scene import BackyardScene
from scenes.town.character_room import CharacterRoom
from scenes.title_scene import TitleScene
from ui.scene_transition import SceneTransition


def close_scene_ui(scene):
    chat = getattr(scene, "chat", None)
    if chat is not None:
        chat.close()


def apply_passive_regen(scene, dt):
    # Во время боя не применяем пассивную регенерацию, кроме как при просмотре результатов
    if isinstance(scene, DuelScene):
        if scene.phase != "result":
            return
        session = scene.online_session
        if session is None:
            return
        session.passive_regenerate(dt, in_tavern=False)
        amount = getattr(session, "last_regen_amount", 0)
        if amount > 0 and hasattr(scene, "profile_overlay"):
            scene.profile_overlay.player_card.sync(
                session.character,
                title="ТЕКУЩИЙ ИГРОК",
                kind="player",
            )
            scene.profile_overlay.player_card.show_regen(amount)
        return
    
    session = getattr(scene, "session", None)
    if session is not None:
        session.passive_regenerate(dt, in_tavern=isinstance(scene, TavernScene))
        amount = getattr(session, "last_regen_amount", 0)
        if amount > 0 and hasattr(scene, "profile_overlay"):
            scene.profile_overlay.player_card.sync(
                session.character,
                title="ТЕКУЩИЙ ИГРОК",
                kind="player",
            )
            scene.profile_overlay.player_card.show_regen(amount)


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

    transition = SceneTransition()

    try:
        running = True

        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif not transition.active:
                    scene.handle_event(event)

            if not transition.active:
                if args.online and isinstance(scene, TitleScene) and scene.finished:
                    pygame.key.stop_text_input()
                    if scene.online_session is None:
                        running = False
                    elif scene.cancelled:
                        running = False
                    else:
                        close_scene_ui(scene)
                        session = scene.online_session
                        transition.start(screen, lambda: CharacterScene(session))

                elif args.online and isinstance(scene, CharacterScene) and scene.finished:
                    pygame.key.stop_text_input()
                    if scene.cancelled:
                        scene.session.disconnect()
                        running = False
                    else:
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: ProfessionSelectScene(session))

                elif args.online and isinstance(scene, ProfessionSelectScene) and scene.finished:
                    pygame.key.stop_text_input()
                    if scene.cancelled:
                        scene.session.disconnect()
                        running = False
                    else:
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: TavernScene(session))

                elif args.online and isinstance(scene, TavernScene) and scene.finished:
                    if scene.cancelled:
                        scene.session.disconnect()
                        running = False
                    else:
                        close_scene_ui(scene)
                        session = scene.session
                        if scene.navigate == "character_room":
                            transition.start(screen, lambda: CharacterRoom(session))
                        else:
                            transition.start(screen, lambda: BackyardScene(session))

                elif args.online and isinstance(scene, CharacterRoom) and scene.finished:
                    close_scene_ui(scene)
                    session = scene.session
                    transition.start(screen, lambda: TavernScene(session))

                elif args.online and isinstance(scene, BackyardScene) and scene.finished:
                    session = scene.session
                    if scene.navigate == "tavern" or scene.cancelled:
                        close_scene_ui(scene)
                        transition.start(screen, lambda: TavernScene(session))
                    else:
                        opponent = scene.opponent
                        close_scene_ui(scene)
                        transition.start(screen, lambda: DuelScene(session, opponent))

                elif args.online and isinstance(scene, DuelScene) and scene.return_to_tavern:
                    scene.return_to_tavern = False
                    close_scene_ui(scene)
                    session = scene.online_session
                    transition.start(screen, lambda: TavernScene(session))

            if not transition.active:
                if args.online:
                    apply_passive_regen(scene, dt)
                scene.update(dt)
                scene.draw(screen)
            else:
                new_scene = transition.update(dt)
                if new_scene is not None:
                    scene = new_scene
                    pygame.key.start_text_input()
                transition.draw(screen)

            pygame.display.flip()
    finally:
        scene.close()
        pygame.quit()


if __name__ == "__main__":
    main()
