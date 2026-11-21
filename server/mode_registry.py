"""Control-plane metadata for independent game-mode runtimes."""

MODES = (
    {
        "key": "tower",
        "name": "Tower",
        "description": "Боевые миры Башни с отдельным сервером и API.",
        "schema": "tower",
        "entrypoint": "tower.server.main",
        "runtime_ready": True,
    },
    {
        "key": "economy",
        "name": "Economy",
        "description": "Производство и развитие города в Economy.",
        "schema": "economy",
        "entrypoint": "economy.server.main",
        "runtime_ready": True,
    },
    {
        "key": "deck",
        "name": "Deck",
        "description": "Карточные миры с отдельным сервером и правилами Deck.",
        "schema": "deck",
        "entrypoint": "deck.server.main",
        "runtime_ready": True,
    },
    {
        "key": "front_line",
        "name": "Front Line",
        "description": "Автоматический режим обороны с отдельным сервером и картами редактора.",
        "schema": "tower",
        "entrypoint": "front_line.server.main",
        "runtime_ready": True,
    },
)

_BY_KEY = {mode["key"]: mode for mode in MODES}


def list_modes():
    return [dict(mode) for mode in MODES]


def get_mode(key):
    try:
        return dict(_BY_KEY[key])
    except KeyError as error:
        raise ValueError(f"Неизвестный режим: {key}") from error
