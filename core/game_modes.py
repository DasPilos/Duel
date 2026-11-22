"""Режимы игры. Режим — тип мира сервера: у каждого режима свои настройки мобов (core/mob_modes.py).

В одном режиме может быть много миров с разными названиями и картами, мобы в них одинаковы.
"""

GAME_MODES = (
    {
        "key": "economy",
        "name": "Economy",
        "description": "Отдельные экономические миры",
        "runtime_ready": True,
    },
    {
        "key": "deck",
        "name": "Deck",
        "description": "Отдельные карточные миры",
        "runtime_ready": True,
    },
    {
        "key": "front_line",
        "name": "Front Line",
        "description": "Совместная оборона карты от волн мобов.",
        "runtime_ready": False,
    },
)
DEFAULT_MODE = "front_line"

_BY_KEY = {mode["key"]: mode for mode in GAME_MODES}


def mode_keys():
    return [mode["key"] for mode in GAME_MODES]


def is_mode(key):
    return key in _BY_KEY


def mode_name(key):
    """Название режима для показа; неизвестный ключ возвращается как есть."""
    return _BY_KEY.get(key, {}).get("name", str(key))
