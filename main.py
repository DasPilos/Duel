import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import pygame

from client.app_flow import (
    close_scene_ui,
    disconnect_scene,
    ensure_equipment_loaded,
    inventory_session,
    leave_to_lobby,
    resync_scene,
    scene_for_saved_character,
    scene_session,
    server_status_visible,
    start_disconnect,
    text_input_focused,
    toggle_player_profile,
)
from client.connection import ConnectionMonitor
from client.network import ServerError
from core.settings import FPS, HEIGHT, WIDTH
from scenes.account_menu_scene import AccountMenuScene
from scenes.character_scene import CharacterScene
from scenes.city_scene import CityScene
from scenes.create_character_scene import CreateCharacterScene
from scenes.tavern_scene import TavernScene
from scenes.title_scene import TitleScene
from scenes.town.character_room import CharacterRoom
from scenes.world_map_scene import WorldMapScene
from ui.connection_overlay import ConnectionOverlay
from ui.exit_menu import ExitMenu
from ui.inventory_window import InventoryWindow
from ui.scene_transition import SceneTransition
from ui.server_status_hud import ServerStatusHUD
from ui.sfx import stop_run_sound

def parse_args():
    parser = argparse.ArgumentParser(description="Мир Duel")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--username", default=os.getenv("GAME_USERNAME"))
    parser.add_argument("--password", default=os.getenv("GAME_PASSWORD"))
    parser.add_argument("--server", default=os.getenv("GAME_SERVER", "http://127.0.0.1:8765"))
    return parser.parse_args()


def main():
    args = parse_args()
    pygame.init()
    pygame.mixer.init()  # Инициализируем звуковую систему

    screen = pygame.display.set_mode((WIDTH, HEIGHT))

    clock = pygame.time.Clock()
    scene = TitleScene(
        args.server,
        args.username or "",
        args.password or "",
    )
    pygame.key.start_text_input()

    transition = SceneTransition()
    inventory = InventoryWindow()
    exit_menu = ExitMenu()
    server_status_hud = ServerStatusHUD()
    connection = ConnectionMonitor()
    connection_overlay = ConnectionOverlay()
    disconnect_executor = ThreadPoolExecutor(max_workers=1)
    disconnect_future = None
    disconnect_succeeded = False
    server_unreachable = False  # отключиться от сервера не вышло: клиент можно закрыть без сохранения

    try:
        running = True

        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if connection.is_blocking:
                    if event.type == pygame.QUIT:
                        running = False
                    elif connection_overlay.handle_event(connection, event) == "reload":
                        # Сохранение может не пройти, но перезагрузка всё равно нужна
                        disconnect_scene(scene)
                        pygame.quit()
                        os.execv(sys.executable, [sys.executable, *sys.argv])
                    continue
                if event.type == pygame.QUIT:
                    if exit_menu.quitting:
                        continue
                    if scene_session(scene) is not None:
                        exit_menu.open()
                    else:
                        running = False
                    continue
                elif transition.active:
                    continue
                elif exit_menu.quitting:
                    continue
                elif exit_menu.is_open:
                    action = exit_menu.handle_event(event)
                    if action == "quit":
                        if server_unreachable:
                            running = False
                            continue
                        disconnect_succeeded = False
                        disconnect_future = start_disconnect(scene, disconnect_executor)
                        if disconnect_future is not None:
                            exit_menu.begin_quit()
                        else:
                            exit_menu.open(error="Не удалось отключиться от сервера.")
                    elif action == "lobby":
                        lobby_session, error = leave_to_lobby(scene)
                        if lobby_session is None:
                            exit_menu.open(error=error)
                        else:
                            transition.start(screen, lambda: AccountMenuScene(lobby_session))
                    continue
                elif (server_status_visible(scene, transition.active, exit_menu)
                      and server_status_hud.handle_event(event) == "restart_client"):
                    error = disconnect_scene(scene)
                    if error is None:
                        pygame.quit()
                        os.execv(sys.executable, [sys.executable, *sys.argv])
                    else:
                        exit_menu.open(error=error)
                    continue
                elif inventory.handle_event(event):
                    continue
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                      and scene_session(scene) is not None and not text_input_focused(scene)):
                    exit_menu.open()
                    continue
                elif (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_i
                    and inventory_session(scene) is not None
                    and not text_input_focused(scene)
                ):
                    toggle_player_profile(scene)
                else:
                    scene.handle_event(event)

            # Кнопка «РЮКЗАК» в профиле персонажа открывает то же окно
            overlay = getattr(scene, "profile_overlay", None)
            if getattr(overlay, "inventory_requested", False):
                overlay.inventory_requested = False
                if inventory_session(scene) is not None:
                    inventory.open(inventory_session(scene))

            if disconnect_future is not None and disconnect_future.done():
                completed_disconnect = disconnect_future
                disconnect_future = None
                try:
                    completed_disconnect.result()
                except Exception as error:
                    server_unreachable = True
                    exit_menu.open(error=f"Сервер недоступен: {error}. Нажмите «Покинуть игру», чтобы закрыть клиент")
                else:
                    disconnect_succeeded = True

            if exit_menu.update_quit(dt) and disconnect_succeeded:
                running = False

            ensure_equipment_loaded(scene)

            if transition.active and inventory.is_open:
                inventory.close()

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
                        transition.start(screen, lambda: AccountMenuScene(session))

                elif args.online and isinstance(scene, AccountMenuScene) and scene.finished:
                    close_scene_ui(scene)
                    if scene.world_session is not None:
                        world_session = scene.world_session
                        transition.start(screen, lambda: CharacterScene(world_session))
                    else:
                        pygame.key.start_text_input()
                        transition.start(screen, lambda: TitleScene(args.server))

                elif args.online and isinstance(scene, CharacterScene) and scene.finished:
                    pygame.key.stop_text_input()
                    if scene.cancelled:
                        scene.session.disconnect()
                        running = False
                    elif scene.create_new_character:
                        # Transition to character creation scene
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: CreateCharacterScene(session))
                    else:
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: scene_for_saved_character(session))

                elif args.online and isinstance(scene, CreateCharacterScene) and scene.finished:
                    pygame.key.stop_text_input()
                    if scene.cancelled:
                        # Back to character selection
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: CharacterScene(session))
                    else:
                        # Character created; both professions share the same tavern hub (миры карт — сразу на карте).
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: scene_for_saved_character(session))

                elif args.online and isinstance(scene, TavernScene) and scene.finished:
                    if scene.cancelled:
                        error = disconnect_scene(scene)
                        if error is None:
                            running = False
                        else:
                            exit_menu.open(error=error)
                    else:
                        close_scene_ui(scene)
                        session = scene.session
                        if scene.navigate == "character_room":
                            transition.start(screen, lambda: CharacterRoom(session))
                        elif scene.navigate == "city":
                            # Выход на улицу города возле двери таверны
                            transition.start(screen, lambda: CityScene(session, gate="tavern"))
                        elif scene.navigate == "world_map":
                            transition.start(screen, lambda: WorldMapScene(session))
                        else:
                            transition.start(screen, lambda: TavernScene(session))

                elif args.online and isinstance(scene, WorldMapScene) and scene.finished:
                    close_scene_ui(scene)
                    session = scene.session
                    if scene.navigate == "city":
                        gate = getattr(scene, "city_gate", "east")
                        transition.start(screen, lambda g=gate: CityScene(session, gate=g))
                    else:
                        transition.start(screen, lambda: TavernScene(session))

                elif args.online and isinstance(scene, CityScene) and scene.finished:
                    close_scene_ui(scene)
                    session = scene.session
                    if scene.navigate == "tavern":
                        transition.start(screen, lambda: TavernScene(session))
                    else:
                        gate = getattr(scene, "exit_gate", "east")
                        transition.start(screen, lambda g=gate: WorldMapScene(session, spawn_gate=g))

                elif args.online and isinstance(scene, CharacterRoom) and scene.finished:
                    close_scene_ui(scene)
                    session = scene.session
                    transition.start(screen, lambda: TavernScene(session))

            status = connection.update(scene_session(scene), dt)
            if status is not None:
                server_status_hud.apply_status(status)
            if connection.take_reconnected():
                resync_scene(scene)
            if connection.expired():
                running = False

            if not transition.active:
                if not exit_menu.is_open and not exit_menu.quitting and not connection.is_blocking:
                    scene.update(dt)
                else:
                    stop_run_sound()
                scene.draw(screen)
                inventory.draw(screen)
                exit_menu.draw(screen, pygame.font.SysFont("arial", 30), pygame.font.SysFont("arial", 20))
                if server_status_visible(scene, transition.active, exit_menu):
                    server_status_hud.draw(screen)
            else:
                stop_run_sound()
                new_scene = transition.update(dt)
                if new_scene is not None:
                    scene = new_scene
                    pygame.key.start_text_input()
                transition.draw(screen)

            connection_overlay.draw(screen, connection)
            pygame.display.flip()
    finally:
        disconnect_executor.shutdown(wait=True, cancel_futures=False)
        try:
            scene.close()
        except ServerError:
            pass
        pygame.quit()


if __name__ == "__main__":
    main()
