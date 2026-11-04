"""Вход в Колоду из общего лобби: единственное место, где общий цикл игры встречается с нашим миром."""

from client.network import ServerError
from kaloda.client import KalodaSession
from kaloda.scenes.world_flow import KalodaWorld
from scenes.character_scene import CharacterScene

GAME_KEY = "kaloda"


def open_world(world_session):
    """Первая сцена мира: Колода, если сервер мира объявляет себя ею, иначе обычный выбор персонажа."""
    kaloda_session = KalodaSession.adopt(world_session)
    try:
        info = kaloda_session.client.get_game_info()
    except ServerError:
        info = {}
    if info.get("game") == GAME_KEY:
        return KalodaWorld(kaloda_session)
    return CharacterScene(world_session)
