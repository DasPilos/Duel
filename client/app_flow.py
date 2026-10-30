"""Хелперы игрового цикла: сессии сцен, чекпоинты, инвентарь и отключение от сервера."""

from client.network import ServerError
from scenes.city_scene import CityScene
from scenes.town.character_room import CharacterRoom
from scenes.tavern_scene import TavernScene
from scenes.world_map_scene import WorldMapScene

# Сцены, где инвентарь открывается клавишей I (не в бою и не в меню входа)
INVENTORY_SCENES = (TavernScene, CharacterRoom, WorldMapScene, CityScene)


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
    """Открытый чат или полный лог боя забирают клавиши (I, ESC) себе, а не меню."""
    combat_log = getattr(scene, "combat_log", None)
    if combat_log is not None and combat_log.captures_keyboard():
        return True
    chat = getattr(scene, "chat", None)
    return chat is not None and chat.captures_keyboard()


def close_scene_ui(scene):
    presence = getattr(scene, "presence", None)
    if presence is not None:
        presence.close()
    chat = getattr(scene, "chat", None)
    if chat is not None:
        chat.hide()


def scene_session(scene):
    return getattr(scene, "session", None) or getattr(scene, "online_session", None)


def resync_scene(scene):
    """После возврата связи перечитывает персонажа и обновляет состояние мира с сервера."""
    session = scene_session(scene)
    if session is not None and getattr(session, "character", None):
        try:
            session.refresh_character()
        except ServerError:
            pass
    resync = getattr(scene, "resync_with_server", None)
    if resync is not None:
        resync()


def server_status_visible(scene, transition, exit_menu):
    if transition or exit_menu.is_open or exit_menu.quitting:
        return False
    session = scene_session(scene)
    if session is None or not getattr(session, "character", None):
        return False
    if isinstance(scene, CityScene):
        menu_flags = (
            "castle_menu_open", "barn_menu_open", "warehouse_menu_open", "stable_menu_open",
            "forge_menu_open", "workshop_menu_open", "barracks_menu_open",
            "engineering_menu_open", "university_menu_open", "academy_menu_open",
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
        fighter = getattr(scene, "combat_fighter", None)
        if fighter is not None:
            checkpoint.update({"hp": fighter.hp, "mp": fighter.mp})
    elif isinstance(scene, CityScene):
        checkpoint.update({
            "zone": "city",
            "position_x": scene.player_x,
            "position_y": scene.player_y,
            "position_direction": scene.player_direction,
        })
    elif isinstance(scene, CharacterRoom):
        checkpoint["zone"] = "character_room"
    elif isinstance(scene, TavernScene):
        checkpoint["zone"] = "tavern"
    return checkpoint


def opens_map_first(session):
    """Мир создан из карты редактора: в нём нет таверны, персонаж появляется на карте."""
    return bool(getattr(session, "map_world", False))


def scene_for_saved_character(session):
    if opens_map_first(session):
        return WorldMapScene(session)
    character = session.character or {}
    position = (character.get("position_x"), character.get("position_y"))
    direction = character.get("position_direction") or "s"
    if character.get("zone") == "world_map" and all(value is not None for value in position):
        return WorldMapScene(session, spawn_pos=(*position, direction))
    if character.get("zone") == "city" and all(value is not None for value in position):
        return CityScene(session, spawn_pos=(*position, direction))
    if character.get("zone") == "character_room":
        return CharacterRoom(session)
    return TavernScene(session)


def disconnect_scene(scene):
    session = scene_session(scene)
    checkpoint = checkpoint_for_scene(scene)
    if session is None:
        return None
    close_scene_ui(scene)
    try:
        session.disconnect(character=checkpoint)
    except ServerError as error:
        return str(error)
    return None


def start_disconnect(scene, executor):
    session = scene_session(scene)
    if session is None:
        return None
    checkpoint = checkpoint_for_scene(scene)
    close_scene_ui(scene)
    return executor.submit(session.disconnect, character=checkpoint)


def leave_to_lobby(scene):
    """Сохраняет персонажа, выходит с сервера мира и заново входит в аккаунт для лобби.

    Возвращает (сессия аккаунта, None) или (None, текст ошибки).
    """
    session = scene_session(scene)
    if session is None:
        return None, "Нет активной сессии."
    checkpoint = checkpoint_for_scene(scene)
    close_scene_ui(scene)
    try:
        session.disconnect(character=checkpoint)
        # disconnect сбрасывает токен, для лобби нужен новый
        session.user = session.client.login(session.username, session.password)
    except ServerError as error:
        return None, str(error)
    return session, None
