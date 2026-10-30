"""Карты, подготовленные для сервера: файлы JSON в папке maps_for_server (формат черновика редактора).

Окно «Создать мир» загружает их на сервер кнопкой «Загрузить карту».
"""
import json
from pathlib import Path

SERVER_MAPS_DIR = Path(__file__).resolve().parent.parent / "maps_for_server"


def list_server_maps(folder=SERVER_MAPS_DIR):
    """Карты из папки: {path, name, mode, map_w, map_h, data}. Файлы с ошибкой пропускаются."""
    maps = []
    if not folder.is_dir():
        return maps
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or "cells" not in data or "map_w" not in data or "map_h" not in data:
            continue
        maps.append({
            "path": path,
            "name": str(data.get("name") or path.stem),
            "mode": str(data.get("mode", "tower")),
            "map_w": data["map_w"],
            "map_h": data["map_h"],
            "data": data,
        })
    return maps


def upload_server_map(client, entry):
    """Загружает карту на сервер как сохранённую; возвращает ответ сервера с saved_id."""
    data = entry["data"]
    return client.save_saved_map(
        data["cells"], data["map_w"], data["map_h"], entry["name"], entry["mode"],
        mobs=data.get("mobs", []), spawns=data.get("spawns", []),
    )
