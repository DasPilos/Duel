"""Режим Deck: тип мира сервера. Миры карт редактора получают ключ `deck`, по нему лобби находит их.

Список Deck отдельный от core/game_modes.py: правила и состояние режима изолированы от других режимов.
"""

GAME_MODES = (
    {"key": "deck", "name": "Deck"},
)
DEFAULT_MODE = GAME_MODES[0]["key"]

_BY_KEY = {mode["key"]: mode for mode in GAME_MODES}


def is_mode(key):
    return key in _BY_KEY


def mode_name(key):
    """Название режима для показа; неизвестный ключ возвращается как есть."""
    return _BY_KEY.get(key, {}).get("name", str(key))
