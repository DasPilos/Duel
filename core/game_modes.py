"""Режимы игры. Режим — тип мира сервера: у каждого режима свои настройки мобов (core/mob_modes.py).

В одном режиме может быть много миров с разными названиями и картами, мобы в них одинаковы.
"""

GAME_MODES = (
    {"key": "tower", "name": "Башня"},
)
DEFAULT_MODE = GAME_MODES[0]["key"]

_BY_KEY = {mode["key"]: mode for mode in GAME_MODES}


def mode_keys():
    return [mode["key"] for mode in GAME_MODES]


def is_mode(key):
    return key in _BY_KEY


def mode_name(key):
    """Название режима для показа; неизвестный ключ возвращается как есть."""
    return _BY_KEY.get(key, {}).get("name", str(key))
