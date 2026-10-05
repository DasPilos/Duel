import argparse
import os
import sys

import pygame

from combat.card_database import is_mage_profession
from core.settings import FPS, HEIGHT, WIDTH
from scenes.duel_scene import DuelScene
from scenes.mage_battle_scene import MageBattleScene
from scenes.character_scene import CharacterScene
from scenes.create_character_scene import CreateCharacterScene
from scenes.tavern_scene import TavernScene
from scenes.backyard_scene import BackyardScene
from scenes.town.character_room import CharacterRoom
from scenes.world_map_scene import WorldMapScene
from scenes.city_scene import CityScene
from scenes.title_scene import TitleScene
from ui.scene_transition import SceneTransition
from client.network import ServerError
from ui.inventory_window import InventoryWindow
from ui.exit_menu import ExitMenu
from ui.server_status_hud import ServerStatusHUD


# Сцены, где инвентарь открывается клавишей I (не в бою и не в меню входа)
INVENTORY_SCENES = (TavernScene, CharacterRoom, WorldMapScene, CityScene, BackyardScene)


def inventory_session(scene):
    """Сессия, для которой можно открыть инвентарь в этой сцене, или None"""
    if not isinstance(scene, INVENTORY_SCENES):
        return None
    session = getattr(scene, "session", None)
    if session is None or not getattr(session, "character", None):
        return None
    return session


def ensure_equipment_loaded(scene):
    """Один раз подгружает надетые предметы, чтобы слоты на карточке профиля не были пустыми"""
    overlay = getattr(scene, "profile_overlay", None)
    session = inventory_session(scene)
    if session is None or not getattr(overlay, "is_open", False) or "equipment" in session.character:
        return
    try:
        state = session.client.get_inventory(session.character["id"])
    except ServerError:
        state = {}
    session.character["equipment"] = dict(state.get("equipment", {}))


def text_input_focused(scene):
    """Игрок печатает в чате или вводит имя колоды — клавиша I должна остаться буквой"""
    message_input = getattr(getattr(scene, "chat", None), "message_input", None)
    if getattr(message_input, "focused", False):
        return True
    deck_panel = getattr(getattr(scene, "profile_overlay", None), "deck_panel", None)
    return bool(getattr(deck_panel, "creating", False))


def close_scene_ui(scene):
    chat = getattr(scene, "chat", None)
    if chat is not None:
        chat.close()


def scene_session(scene):
    return getattr(scene, "session", None) or getattr(scene, "online_session", None)


def server_status_visible(scene, transition, exit_menu):
    if transition or exit_menu.is_open or exit_menu.quitting or isinstance(scene, DuelScene):
        return False
    session = scene_session(scene)
    if session is None or not getattr(session, "character", None):
        return False
    if isinstance(scene, CityScene):
        menu_flags = (
            "castle_menu_open", "barn_menu_open", "warehouse_menu_open", "stable_menu_open",
            "forge_menu_open", "workshop_menu_open", "barracks_menu_open",
            "engineering_menu_open", "university_menu_open", "academy_menu_open",
            "mage_school_menu_open",
        )
        if any(getattr(scene, name, False) for name in menu_flags):
            return False
        if any(getattr(scene, name, None) is not None and getattr(scene, name).is_open
               for name in ("barn_window", "warehouse_window", "stable_window")):
            return False
    return True


def toggle_player_profile(scene):
    session = scene_session(scene)
    overlay = getattr(scene, "profile_overlay", None)
    if session is None or not getattr(session, "character", None) or overlay is None:
        return False
    if overlay.is_open:
        overlay.close()
    else:
        overlay.open(session.character, None)
    return True


def checkpoint_for_scene(scene):
    session = scene_session(scene)
    if session is None or not session.character:
        return None
    checkpoint = dict(session.character)
    if isinstance(scene, WorldMapScene):
        checkpoint.update({
            "zone": "world_map",
            "position_x": scene.player_x,
            "position_y": scene.player_y,
            "position_direction": scene.player_direction,
        })
    elif isinstance(scene, CityScene):
        checkpoint.update({
            "zone": "city",
            "position_x": scene.player_x,
            "position_y": scene.player_y,
            "position_direction": scene.player_direction,
        })
    elif isinstance(scene, BackyardScene):
        checkpoint["zone"] = "backyard"
    elif isinstance(scene, CharacterRoom):
        checkpoint["zone"] = "character_room"
    elif isinstance(scene, TavernScene):
        checkpoint["zone"] = "tavern"
    elif isinstance(scene, DuelScene):
        checkpoint["zone"] = "backyard"
    return checkpoint


def scene_for_saved_character(session):
    character = session.character or {}
    position = (character.get("position_x"), character.get("position_y"))
    direction = character.get("position_direction") or "s"
    if character.get("zone") == "world_map" and all(value is not None for value in position):
        return WorldMapScene(session, spawn_pos=(*position, direction))
    if character.get("zone") == "city" and all(value is not None for value in position):
        return CityScene(session, spawn_pos=(*position, direction))
    if character.get("zone") == "backyard":
        return BackyardScene(session)
    if character.get("zone") == "character_room":
        return CharacterRoom(session)
    return TavernScene(session)


def disconnect_scene(scene):
    session = scene_session(scene)
    checkpoint = checkpoint_for_scene(scene)
    if session is None:
        return None
    close_scene_ui(scene)
    fighter = scene.player if isinstance(scene, DuelScene) else None
    try:
        session.disconnect(fighter=fighter, character=checkpoint)
    except ServerError as error:
        return str(error)
    return None


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
    pygame.mixer.init()  # Инициализируем звуковую систему

    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)

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
    inventory = InventoryWindow()
    exit_menu = ExitMenu()
    server_status_hud = ServerStatusHUD()

    try:
        running = True

        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
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
                        error = disconnect_scene(scene)
                        if error is None:
                            exit_menu.begin_quit()
                        else:
                            exit_menu.open(error=error)
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

            if exit_menu.update_quit(dt):
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
                        transition.start(screen, lambda: CharacterScene(session))

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
                        # Character created; both professions share the same tavern hub.
                        close_scene_ui(scene)
                        session = scene.session
                        transition.start(screen, lambda: TavernScene(session))

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
                            transition.start(screen, lambda: BackyardScene(session))

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

                elif args.online and isinstance(scene, BackyardScene) and scene.finished:
                    session = scene.session
                    if scene.navigate == "tavern" or scene.cancelled:
                        close_scene_ui(scene)
                        transition.start(screen, lambda: TavernScene(session))
                    else:
                        opponent = scene.opponent
                        close_scene_ui(scene)
                        if is_mage_profession(session.character.get("type")):
                            transition.start(screen, lambda: MageBattleScene(session, opponent))
                        else:
                            transition.start(screen, lambda: DuelScene(session, opponent))

                elif args.online and isinstance(scene, DuelScene) and scene.return_to_tavern:
                    scene.return_to_tavern = False
                    close_scene_ui(scene)
                    session = scene.online_session
                    # Если персонаж погиб (hp <= 0), возрождаем у Кристалла Жизни в городе (а не в таверне)
                    if getattr(scene, "player", None) and scene.player.hp <= 0:
                        if session and getattr(session, "character", None):
                            session.character["hp"] = session.character.get("max_hp", 100)
                            try:
                                session.client.save_character(session.character)
                            except Exception:
                                pass
                        transition.start(screen, lambda: CityScene(session, gate="crystal"))
                    else:
                        transition.start(screen, lambda: TavernScene(session))

            if not transition.active:
                server_status_hud.update(
                    scene_session(scene), dt,
                    visible=server_status_visible(scene, transition.active, exit_menu),
                )
                if not exit_menu.is_open and not exit_menu.quitting:
                    if args.online:
                        apply_passive_regen(scene, dt)
                    scene.update(dt)
                scene.draw(screen)
                inventory.draw(screen)
                exit_menu.draw(screen, pygame.font.SysFont("arial", 30), pygame.font.SysFont("arial", 20))
                if server_status_visible(scene, transition.active, exit_menu):
                    server_status_hud.draw(screen)
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
