"""Worlds from saved maps: each world starts the runtime registered for its game mode.

Each world has its own process, port, and mode database schema. Processes read their published
visual map from the shared map catalog and synchronize updates without a restart.
"""
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from core.game_modes import is_mode
from core import mob_modes
from server.mode_registry import get_mode

REPO_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_DIR / "logs"
PORT_RANGE = range(8800, 8900)
HEALTH_TIMEOUT = 1.5

# Процессы миров, запущенные этим сервером: world_id -> Popen
_processes = {}


def is_healthy(url):
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=HEALTH_TIMEOUT) as response:
            return response.status == 200
    except OSError:
        return False


def free_port(used):
    """Первый свободный порт из PORT_RANGE, которого нет в used и который можно открыть."""
    for port in PORT_RANGE:
        if port in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise RuntimeError("Нет свободного порта для мира карты")


def spawn_world_server(world_id, port, mode, test_only=False):
    LOG_DIR.mkdir(exist_ok=True)
    mode_config = get_mode(mode)
    if not mode_config.get("runtime_ready", True) or not mode_config.get("entrypoint"):
        raise ValueError(f"Игровой сервер режима «{mode_config['name']}» ещё не подключён")
    env = {**os.environ, "PORT": str(port)}
    if mode_config["key"] == "deck":
        env.pop("WORLD_ID", None)
        env.pop("DECK_PUBLIC_URL", None)
        env["DECK_WORLD_ID"] = str(world_id)
        env["DECK_PORT"] = str(port)
        env["DECK_PUBLIC_URL"] = f"http://127.0.0.1:{port}"
    else:
        env.pop("DECK_WORLD_ID", None)
        env["GAME_SCHEMA"] = mode_config["schema"]
        env["WORLD_ID"] = str(world_id)
        env["WORLD_TEST"] = "1" if test_only else "0"
        env["PUBLIC_URL"] = f"http://127.0.0.1:{port}"
    with open(LOG_DIR / f"world_{world_id}.log", "ab") as log:
        return subprocess.Popen(
            [sys.executable, "-m", mode_config["entrypoint"]],
            cwd=REPO_DIR,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def _running(world_id):
    process = _processes.get(world_id)
    return process is not None and process.poll() is None


def save_map(database, moderator_id, body):
    """Сохраняет карту на сервере как заготовку. Мир не создаётся и сервер мира не запускается:
    это делает игрок с привилегиями в разделе «Миры» игрового меню."""
    saved_id = database.save_saved_map(
        int(body.get("saved_id") or 0), body.get("name", ""), str(body.get("mode", "tower")),
        int(body.get("map_w", 125)), int(body.get("map_h", 125)),
        body.get("cells", []), body.get("mobs", []), moderator_id, spawns=body.get("spawns", []),
        crystals=body.get("crystals", {}), harvest_enabled=bool(body.get("harvest_enabled", False)),
        editor_layers=body.get("editor_layers", []),
    )
    stored = database.get_saved_map(saved_id)
    world_errors = _republish_linked_worlds(database, moderator_id, stored)
    return {"saved_id": saved_id, "name": stored["name"], "mode": stored["mode"], "world_errors": world_errors}


def mode_item_database(database, mode):
    """Create an ItemsDatabase bound to the selected mode's gameplay schema."""
    mode_config = get_mode(mode)
    if mode_config["key"] == "deck":
        raise ValueError("Редактор экипировки недоступен для режима Deck")
    from server.database import Database
    from server.items_database import ItemsDatabase

    mode_database = Database(dsn=database.dsn, schema=mode_config["schema"])
    return ItemsDatabase(mode_database)


def load_mob_settings(mode, kind, folder=None):
    """Load a mob profile shared by all editors and world processes for this mode."""
    _validate_mob_settings_key(mode, kind)
    modes_module = _mob_modes_module(mode)
    return modes_module.load_mob_settings(mode, kind, folder)


def save_mob_settings(mode, kind, settings, folder=None):
    """Validate and persist a mode-wide mob profile."""
    _validate_mob_settings_key(mode, kind)
    modes_module = _mob_modes_module(mode)
    return modes_module.save_mob_settings(mode, kind, settings, folder)


def _mob_modes_module(mode):
    if mode == "deck":
        from deck.editor import mob_modes as deck_mob_modes

        return deck_mob_modes
    return mob_modes


def _validate_mob_settings_key(mode, kind):
    if not isinstance(mode, str) or not mode.strip() or mode != mode.strip():
        raise ValueError("Некорректный режим игры")
    if not isinstance(kind, str) or not kind.strip() or len(kind) > 160 \
            or kind != kind.strip() or any(ord(char) < 32 for char in kind):
        raise ValueError("Некорректный ключ моба")


def _republish_linked_worlds(database, moderator_id, saved):
    """Миры, где опубликована эта заготовка, получают новую версию. Запущенный мир подхватит её сам (см. sync_published_map)."""
    errors = []
    for world_id in database.linked_world_ids(saved["id"]):
        try:
            database.publish_map(
                saved["cells"], world_id, saved["name"], saved["map_w"], saved["map_h"], moderator_id,
                mobs=saved["mobs"], mode=saved["mode"], spawns=saved["spawns"], saved_id=saved["id"],
                crystals=saved["crystals"], harvest_enabled=saved["harvest_enabled"],
            )
        except ValueError as error:
            errors.append({"world_id": world_id, "error": str(error)})
    return errors


def create_test_world(database, moderator_id, body):
    """Мир из сохранённой карты: название, режим карты, карта и расстановка. Модератор создаёт только тестовые миры
    (их видят модераторы и админы); админ может создать и публичный мир (test=False)."""
    if not database.is_moderator(moderator_id):
        raise ValueError("Создавать миры могут только модераторы и админы")
    saved = database.get_saved_map(int(body.get("saved_id") or 0))
    name = str(body.get("name", "")).strip() or saved["name"]
    test = bool(body.get("test", True)) if database.is_admin(moderator_id) else True
    mode = "deck" if saved["mode"] == "deck" else saved["mode"]
    mode_config = get_mode(mode)
    if not mode_config.get("runtime_ready", True):
        raise ValueError(f"Игровой сервер режима «{mode_config['name']}» ещё не подключён")
    world = database.create_map_world(name, mode, moderator_id, test_only=test)
    try:
        database.publish_map(
            saved["cells"], world["id"], name, saved["map_w"], saved["map_h"], moderator_id,
            mobs=saved["mobs"], mode=mode, spawns=saved["spawns"], saved_id=saved["id"],
            crystals=saved["crystals"], harvest_enabled=saved["harvest_enabled"],
        )
    except ValueError:
        database.delete_map_world(world["id"])
        raise
    return {"world_id": world["id"], "name": name, "mode": mode, "test": test}


def start_world(database, moderator_id, world_id, spawn=None, healthy=is_healthy):
    """Запускает сервер мира, если его ещё нет. Публичный мир запускает только админ; модератор — свои тестовые миры."""
    world = database.world_info(world_id)
    if not database.is_admin(moderator_id) and not (database.is_moderator(moderator_id) and world["test_only"]):
        raise ValueError("Публичный мир запускает только админ; модераторы запускают тестовые миры")
    if world["code"] == "lobby":
        raise ValueError("Центральное лобби не запускается как игровой мир")
    mode_config = get_mode(world["mode"])
    if not mode_config.get("runtime_ready", True) or not mode_config.get("entrypoint"):
        raise ValueError(f"Игровой сервер режима «{mode_config['name']}» ещё не подключён")
    url = world["server_url"]
    if _running(world_id) or (url and healthy(url)):
        return {"world_id": world_id, "server_url": url, "started": False}
    port = free_port(database.used_ports())
    url = f"http://127.0.0.1:{port}"
    database.set_world_server(world_id, url)
    if spawn is None:
        _processes[world_id] = spawn_world_server(world_id, port, mode_config["key"], test_only=bool(world["test_only"]))
    else:
        _processes[world_id] = spawn(world_id, port)
    return {"world_id": world_id, "server_url": url, "started": True}


def ensure_front_line_world(database, healthy=is_healthy, spawn=None):
    """Create and start Front Line's persistent matchmaking world without moderator action."""
    world = database.ensure_front_line_world()
    url = world.get("server_url")
    world_id = int(world["id"])
    if _running(world_id) or (url and healthy(url)):
        return {"world_id": world_id, "server_url": url, "started": False}
    port = free_port(database.used_ports())
    url = f"http://127.0.0.1:{port}"
    database.set_world_server(world_id, url)
    if spawn is None:
        _processes[world_id] = spawn_world_server(world_id, port, "front_line")
    else:
        _processes[world_id] = spawn(world_id, port)
    return {"world_id": world_id, "server_url": url, "started": True}
