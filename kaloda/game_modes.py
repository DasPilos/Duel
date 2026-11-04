"""Режимы Колоды: тип мира сервера. Миры карт редактора получают режим «kaloda», по нему лобби находит их.

Список свой, отдельный от core/game_modes.py (режимы Оператора 1): у Колоды свои миры и карты.
"""

GAME_MODES = (
    {"key": "kaloda", "name": "Колода"},
)
DEFAULT_MODE = GAME_MODES[0]["key"]

_BY_KEY = {mode["key"]: mode for mode in GAME_MODES}


def is_mode(key):
    return key in _BY_KEY


def mode_name(key):
    """Название режима для показа; неизвестный ключ возвращается как есть."""
    return _BY_KEY.get(key, {}).get("name", str(key))
