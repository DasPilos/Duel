"""Клиент редактора карт Колоды: вызовы редактора идут на /api/kaloda/..., а не на маршруты Оператора 1."""

from urllib.parse import quote

from kaloda.client import KalodaClient, ServerError
from kaloda.game_modes import DEFAULT_MODE

__all__ = ["EditorClient", "ServerError"]


class EditorClient(KalodaClient):
    def list_worlds(self):
        """Миры Колоды; тестовые видят только модераторы и админы."""
        return self._kaloda("GET", "/worlds")["worlds"]

    def list_saved_maps(self, mode=None):
        path = "/map/saved" + (f"?mode={quote(mode)}" if mode else "")
        return self._kaloda("GET", path)["saved_maps"]

    def save_saved_map(self, cells, map_w, map_h, name, mode, mobs=(), saved_id=None, spawns=()):
        """Сохраняет карту на сервере как заготовку (мир не создаётся). saved_id обновляет уже сохранённую карту."""
        payload = {
            "cells": cells, "name": name, "map_w": map_w, "map_h": map_h,
            "mobs": list(mobs), "spawns": list(spawns), "mode": mode or DEFAULT_MODE, "saved_id": saved_id or 0,
        }
        return self._kaloda("POST", "/map/editor/saved", payload, timeout=max(self.timeout, 30))

    def publish_map(self, cells, map_w, map_h, name, world_id, mobs=(), mode=None, spawns=(), saved_id=None):
        """Размещает карту в мире Колоды; игроки этого мира увидят её после обновления рельефа."""
        payload = {
            "cells": cells, "name": name, "map_w": map_w, "map_h": map_h, "world_id": world_id,
            "mobs": list(mobs), "mode": mode or DEFAULT_MODE, "spawns": list(spawns), "saved_id": saved_id,
        }
        return self._kaloda("POST", "/map/editor/publish", payload, timeout=max(self.timeout, 30))

    def create_test_world(self, saved_id, name, test=True):
        """Создаёт мир Колоды из сохранённой карты. Создаёт только админ."""
        payload = {"saved_id": saved_id, "name": name, "test": bool(test)}
        return self._kaloda("POST", "/map/editor/test-world", payload, timeout=max(self.timeout, 30))

    def get_equipment_items(self, slots):
        """Экипировка каталога по слотам: сервер Колоды отдаёт весь каталог, поэтому фильтр здесь."""
        wanted = set(slots)
        return [
            item for item in self.list_item_catalog()
            if item.get("item_type") == "equipment" and item.get("equip_slot") in wanted
        ]
