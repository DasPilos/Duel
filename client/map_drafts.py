"""Черновики карт редактора: локальные JSON-файлы в папке map_drafts (сервер не нужен)."""
import json
import time
import uuid
from pathlib import Path

from core.game_modes import DEFAULT_MODE

DRAFTS_DIR = Path(__file__).resolve().parent.parent / "map_drafts"
NAME_MAX = 64


class DraftError(Exception):
    """Ошибка черновика, которую можно показать художнику."""


def _path(draft_id, folder):
    return folder / f"{draft_id}.json"


def _read(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=1)


def _all(folder):
    if not folder.exists():
        return []
    drafts = []
    for path in folder.glob("*.json"):
        try:
            drafts.append(_read(path))
        except (OSError, ValueError):
            continue
    return drafts


def list_drafts(folder=DRAFTS_DIR):
    """Черновики: название, размер и миры, где карта опубликована. Новые сверху."""
    drafts = sorted(_all(folder), key=lambda draft: draft["updated_at"], reverse=True)
    return [
        {
            "id": draft["id"],
            "name": draft["name"],
            "map_w": draft["map_w"],
            "map_h": draft["map_h"],
            "mode": draft.get("mode", DEFAULT_MODE),
            "updated_at": draft["updated_at"],
            "active_worlds": [item["world_name"] for item in draft["published"]],
        }
        for draft in drafts
    ]


def load_draft(draft_id, folder=DRAFTS_DIR):
    try:
        return _read(_path(draft_id, folder))
    except OSError as error:
        raise DraftError("Черновик не найден, возможно он был удалён") from error


def save_draft(name, cells, map_w, map_h, draft_id=None, folder=DRAFTS_DIR, mode=None, mobs=None, spawns=None):
    """Создаёт черновик или перезаписывает draft_id. Возвращает сохранённый черновик.

    Режим игры (mode) задаётся при создании карты; без него берётся режим уже сохранённого черновика, затем режим по умолчанию.
    """
    name = str(name or "").strip()
    if not 1 <= len(name) <= NAME_MAX:
        raise DraftError(f"Название черновика: от 1 до {NAME_MAX} символов")
    published = []
    stored_mode = None
    stored_server_map = None
    for draft in _all(folder):
        if draft["name"] == name and draft["id"] != draft_id:
            raise DraftError(f"Черновик «{name}» уже есть, выберите другое название (F2)")
        if draft["id"] == draft_id:
            published = draft["published"]
            stored_mode = draft.get("mode")
            stored_server_map = draft.get("server_map")
    if draft_id is None:
        draft_id = uuid.uuid4().hex
    data = {
        "id": draft_id,
        "name": name,
        "map_w": map_w,
        "map_h": map_h,
        "mode": mode or stored_mode or DEFAULT_MODE,
        "updated_at": time.time(),
        "cells": [{"layer": cell["layer"], "x": cell["x"], "y": cell["y"], "key": cell["key"]} for cell in cells],
        "published": published,
        "mobs": [dict(mob) for mob in (mobs or [])],
        "spawns": [dict(spawn) for spawn in (spawns or [])],
        "server_map": stored_server_map,
    }
    _write(_path(draft_id, folder), data)
    return data


def delete_draft(draft_id, folder=DRAFTS_DIR):
    """Удаляет файл черновика. Сервер не трогает: опубликованную карту проверяет вызывающий код."""
    try:
        _path(draft_id, folder).unlink()
    except FileNotFoundError as error:
        raise DraftError("Черновик не найден, возможно он уже удалён") from error


def mark_server_map(draft_id, saved_id, saved_name, folder=DRAFTS_DIR):
    """Запоминает, что карта сохранена на сервере: следующее сохранение обновит её, а не создаст новую."""
    for draft in _all(folder):
        if draft["id"] == draft_id:
            draft["server_map"] = {"saved_id": saved_id, "saved_name": saved_name}
            _write(_path(draft["id"], folder), draft)


def mark_published(draft_id, world_id, world_name, folder=DRAFTS_DIR):
    """Отмечает черновик опубликованным в мире. В мире одна карта: у других черновиков эта отметка снимается."""
    for draft in _all(folder):
        others = [item for item in draft["published"] if item["world_id"] != world_id]
        if draft["id"] == draft_id:
            others.append({"world_id": world_id, "world_name": world_name})
        if others != draft["published"]:
            draft["published"] = others
            _write(_path(draft["id"], folder), draft)
