"""Вход в Колоду из общего лобби: единственное место, где общий цикл игры встречается с нашим миром."""

from client.network import ServerError
from deck.client import DeckSession
from deck.scenes.world_flow import DeckWorld
from scenes.character_scene import CharacterScene

GAME_KEY = "deck"


def open_world(world_session):
    """Первая сцена мира: Колода, если сервер мира объявляет себя ею, иначе обычный выбор персонажа."""
    deck_session = DeckSession.adopt(world_session)
    try:
        info = deck_session.client.get_game_info()
    except ServerError:
        info = {}
    if info.get("game") == GAME_KEY:
        return DeckWorld(deck_session)
    return CharacterScene(world_session)
