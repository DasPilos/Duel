"""Состояние кристаллов опубликованной карты: стадии растут по времени сервера, добыча — отдельный учёт игрока."""
from core import crystal_growth
from server.perf_probe import timed
from server import world_map


def is_adjacent_tile(x, y, tile):
    """Игрок в точке (x, y) стоит на соседней клетке тайла (включая диагонали)."""
    tile_x, tile_y = tile
    return max(abs(int(x) // world_map.TILE - tile_x), abs(int(y) // world_map.TILE - tile_y)) == 1


SAVE_INTERVAL = 5.0  # сек: как часто сохранять прогресс внутри стадии (смена стадии сохраняется сразу)


class CrystalField:
    def __init__(self, store=None):
        self._store = store
        self._published_at = None
        self._save_timer = SAVE_INTERVAL
        self._crystals = {}
        self.reload()

    def reload(self):
        """Берёт кристаллы текущего рельефа и их сохранённый рост; добытые кристаллы не возвращаются."""
        self._published_at = world_map.PUBLISHED_AT
        stored = self._store.load_world_crystal_states(self._published_at) if self._store is not None else {}
        self._crystals = {}
        for tile, crystal in list(world_map.MAP_CRYSTALS.items()):
            saved = stored.get(tile)
            if saved is not None and saved["harvested"]:
                world_map.remove_live_crystal(tile)
                continue
            if saved is None:
                state = {"color": crystal["color"], "stage": crystal["stage"], "elapsed": 0.0}
                self._save(tile, state)
            else:
                state = {"color": saved["color"], "stage": saved["stage"], "elapsed": saved["elapsed"]}
            self._crystals[tile] = state

    def get(self, tile):
        return self._crystals.get(tile)

    def grow(self, dt):
        """Растит стадии: через grow_seconds переходим на следующую, на последней стадии рост останавливается."""
        for tile, crystal in self._crystals.items():
            if crystal["stage"] >= crystal_growth.CRYSTAL_STAGES:
                continue
            grow_seconds = crystal_growth.settings_for(world_map.CRYSTAL_SETTINGS, crystal["color"])["grow_seconds"]
            crystal["elapsed"] += dt
            stage_before = crystal["stage"]
            while crystal["stage"] < crystal_growth.CRYSTAL_STAGES and crystal["elapsed"] >= grow_seconds:
                crystal["elapsed"] -= grow_seconds
                crystal["stage"] += 1
            if crystal["stage"] >= crystal_growth.CRYSTAL_STAGES:
                crystal["elapsed"] = 0.0
            if crystal["stage"] != stage_before:
                self._save(tile, crystal)
        self._save_timer -= dt
        if self._save_timer <= 0:
            self._save_timer = SAVE_INTERVAL
            for tile, crystal in self._crystals.items():
                if crystal["stage"] < crystal_growth.CRYSTAL_STAGES:
                    self._save(tile, crystal)

    def remove(self, tile):
        """Добыт: кристалл исчезает, тайл становится свободным для всех игроков и не возвращается после перезапуска."""
        self._crystals.pop(tile, None)
        world_map.remove_live_crystal(tile)
        if self._store is not None:
            self._store.mark_world_crystal_harvested(self._published_at, tile)

    def _save(self, tile, crystal):
        if self._store is not None:
            self._store.save_world_crystal_state(
                self._published_at, tile, crystal["color"], crystal["stage"], crystal["elapsed"],
            )


# Замеры: рост кристаллов и сохранение их состояния (см. server/perf_probe.py).
CrystalField.grow = timed("кристаллы: рост и сохранение")(CrystalField.grow)
