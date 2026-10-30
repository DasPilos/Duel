"""Миры из карт редактора: карта, сохранённая на сервере, получает свой мир с режимом карты.

Мир — отдельный процесс сервера (server.main) с WORLD_ID нового мира и свободным портом. Процесс читает
опубликованную карту из общей базы и подхватывает её публикации сам (проверка раз в 5 секунд).
"""
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from core.game_modes import is_mode

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


def spawn_world_server(world_id, port):
    LOG_DIR.mkdir(exist_ok=True)
    env = {**os.environ, "WORLD_ID": str(world_id), "PORT": str(port)}
    log = open(LOG_DIR / f"world_{world_id}.log", "ab")
    return subprocess.Popen(
        [sys.executable, "-m", "server.main"],
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
    )
    stored = database.get_saved_map(saved_id)
    world_errors = _republish_linked_worlds(database, moderator_id, stored)
    return {"saved_id": saved_id, "name": stored["name"], "mode": stored["mode"], "world_errors": world_errors}


def _republish_linked_worlds(database, moderator_id, saved):
    """Миры, где опубликована эта заготовка, получают новую версию. Запущенный мир подхватит её сам (см. sync_published_map)."""
    errors = []
    for world_id in database.linked_world_ids(saved["id"]):
        try:
            database.publish_map(
                saved["cells"], world_id, saved["name"], saved["map_w"], saved["map_h"], moderator_id,
                mobs=saved["mobs"], mode=saved["mode"], spawns=saved["spawns"], saved_id=saved["id"],
            )
        except ValueError as error:
            errors.append({"world_id": world_id, "error": str(error)})
    return errors


def create_test_world(database, admin_id, body):
    """Мир из сохранённой карты: название, режим карты, карта и расстановка. test=True (по умолчанию) — тестовый:
    его видят только админ и модераторы. Создаёт только админ."""
    if not database.is_admin(admin_id):
        raise ValueError("Создавать миры может только админ")
    saved = database.get_saved_map(int(body.get("saved_id") or 0))
    name = str(body.get("name", "")).strip() or saved["name"]
    test = bool(body.get("test", True))
    world = database.create_map_world(name, saved["mode"], admin_id, test_only=test)
    try:
        database.publish_map(
            saved["cells"], world["id"], name, saved["map_w"], saved["map_h"], admin_id,
            mobs=saved["mobs"], mode=saved["mode"], spawns=saved["spawns"], saved_id=saved["id"],
        )
    except ValueError:
        database.delete_map_world(world["id"])
        raise
    return {"world_id": world["id"], "name": name, "mode": saved["mode"], "test": test}


def start_world(database, moderator_id, world_id, spawn=spawn_world_server, healthy=is_healthy):
    """Запускает сервер мира, если его ещё нет. Запускает только админ (раздел «Миры» игрового меню)."""
    if not database.is_admin(moderator_id):
        raise ValueError("Запускать миры может только админ")
    url = database.world_info(world_id)["server_url"]
    if _running(world_id) or (url and healthy(url)):
        return {"world_id": world_id, "server_url": url, "started": False}
    port = free_port(database.used_ports())
    url = f"http://127.0.0.1:{port}"
    database.set_world_server(world_id, url)
    _processes[world_id] = spawn(world_id, port)
    return {"world_id": world_id, "server_url": url, "started": True}
