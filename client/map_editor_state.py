"""Клетки карты для редактора: земля, прозрачная земля поверх неё и объекты, без зависимости от Pygame."""
from collections import deque

from core.map_catalog import overlay_keys
from core.npc_catalog import NPC_CATALOG

UNDO_LIMIT = 100
NPC_KINDS = frozenset(npc["key"] for npc in NPC_CATALOG)


class MapEditorState:
    def __init__(self, catalog, cells, map_w, map_h):
        self.items = {item["item_key"]: item for item in catalog}
        self.map_w = map_w
        self.map_h = map_h
        self.ground = {}
        self.overlay = {}
        self.overlay_keys = overlay_keys()
        self.objects = {}
        self.cover = {}
        self.mobs = {}
        self.spawns = []
        self.version = 0
        self.dirty = False
        self.selection = None
        self.undo_stack = []
        self.redo_stack = []
        self._pending = None
        self.name = ""
        self._load(cells)

    def _load(self, cells):
        for cell in cells:
            key = cell["key"]
            if key not in self.items:
                continue
            if cell["layer"] == "overlay" or (cell["layer"] == "ground" and key in self.overlay_keys):
                # Прозрачные тайлы из старых черновиков лежали в слое земли и закрывали её.
                self.overlay[(cell["x"], cell["y"])] = key
            elif cell["layer"] == "ground":
                self.ground[(cell["x"], cell["y"])] = key
            else:
                self._add_object(key, cell["x"], cell["y"])

    def replace_cells(self, cells):
        """Заменяет всю карту клетками, например картой башни. Действие попадает в историю отмены."""
        self.begin_action()
        self.ground = {}
        self.overlay = {}
        self.objects = {}
        self.cover = {}
        self.mobs = {}
        self.spawns = []
        self.selection = None
        self._load(cells)
        self.dirty = True
        self.end_action()

    def inside(self, x, y):
        return 0 <= x < self.map_w and 0 <= y < self.map_h

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        self._dirty = value
        if value:
            self.version += 1

    def footprint(self, key, x, y):
        item = self.items[key]
        return [(x + dx, y + dy) for dx in range(item["footprint_w"]) for dy in range(item["footprint_h"])]

    def place(self, key, x, y):
        """Ставит элемент в клетку. Объекты заменяют пересекающиеся с ними. Возвращает текст ошибки или None."""
        item = self.items.get(key)
        if item is None:
            return "Элемента нет в каталоге"
        if not self.inside(x, y):
            return "Клетка вне карты"
        if item["kind"] == "ground":
            if key in self.overlay_keys:
                if self.overlay.get((x, y)) != key:
                    self.overlay[(x, y)] = key
                    self.dirty = True
            elif self.ground.get((x, y)) != key or (x, y) in self.overlay:
                self.ground[(x, y)] = key
                self.overlay.pop((x, y), None)
                self.dirty = True
            return None
        tiles = self.footprint(key, x, y)
        if not all(self.inside(tx, ty) for tx, ty in tiles):
            return "Элемент выходит за край карты"
        if self.objects.get((x, y)) == key:
            return None
        for tile in tiles:
            anchor = self.cover.get(tile)
            if anchor is not None:
                self._remove_object(anchor)
        self._add_object(key, x, y)
        self.dirty = True
        return None

    def paint(self, key, x, y, size=1):
        """Кисть квадратом size×size. Для объектов ставится один элемент в клетку (x, y)."""
        item = self.items.get(key)
        if item is None or item["kind"] != "ground" or size <= 1:
            return self.place(key, x, y)
        start = -(size // 2)
        for dx in range(start, start + size):
            for dy in range(start, start + size):
                if self.inside(x + dx, y + dy):
                    self.place(key, x + dx, y + dy)
        return None

    def fill(self, key, x, y):
        """Заливает связанную область клеток того же вида земли. Возвращает число закрашенных клеток."""
        item = self.items.get(key)
        if item is None or item["kind"] != "ground" or not self.inside(x, y):
            return 0
        layer = self.overlay if key in self.overlay_keys else self.ground
        target = layer.get((x, y))
        if target == key:
            return 0
        seen = {(x, y)}
        queue = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            for tile in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if tile in seen or not self.inside(*tile) or layer.get(tile) != target:
                    continue
                seen.add(tile)
                queue.append(tile)
        for tile in seen:
            layer[tile] = key
            if layer is self.ground:
                self.overlay.pop(tile, None)
        self.dirty = True
        return len(seen)

    def erase(self, x, y):
        """Удаляет объект, закрывающий клетку, затем прозрачную землю, затем землю. Возвращает True, если что-то удалено."""
        anchor = self.cover.get((x, y))
        if anchor is not None:
            self._remove_object(anchor)
            self.dirty = True
            return True
        for layer in (self.overlay, self.ground):
            if (x, y) in layer:
                del layer[(x, y)]
                self.dirty = True
                return True
        return False

    def select(self, x0, y0, x1, y1):
        self.selection = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def clear_selection(self):
        self.selection = None

    def in_selection(self, x, y):
        if self.selection is None:
            return False
        left, top, right, bottom = self.selection
        return left <= x <= right and top <= y <= bottom

    def selected_entries(self):
        ground = [(tile, key) for tile, key in self.ground.items() if self.in_selection(*tile)]
        objects = [(anchor, key) for anchor, key in self.objects.items() if self.in_selection(*anchor)]
        return ground, objects

    def selected_overlay(self):
        return [(tile, key) for tile, key in self.overlay.items() if self.in_selection(*tile)]

    def move_selection(self, dx, dy):
        """Переносит выделение на dx, dy клеток. Возвращает текст ошибки или None; при ошибке карта не меняется."""
        if self.selection is None or (dx == 0 and dy == 0):
            return None
        ground, objects = self.selected_entries()
        overlay = self.selected_overlay()
        if not ground and not objects and not overlay:
            return None
        for (x, y), _ in ground + overlay:
            if not self.inside(x + dx, y + dy):
                return "Выделение выходит за край карты"
        for (x, y), key in objects:
            if not all(self.inside(tx, ty) for tx, ty in self.footprint(key, x + dx, y + dy)):
                return "Выделение выходит за край карты"
        for anchor, _ in objects:
            self._remove_object(anchor)
        for tile, _ in ground:
            del self.ground[tile]
        for tile, _ in overlay:
            del self.overlay[tile]
        for (x, y), key in ground:
            self.ground[(x + dx, y + dy)] = key
        for (x, y), key in overlay:
            self.overlay[(x + dx, y + dy)] = key
        for (x, y), key in objects:
            anchor = (x + dx, y + dy)
            for tile in self.footprint(key, *anchor):
                cover = self.cover.get(tile)
                if cover is not None:
                    self._remove_object(cover)
            self._add_object(key, *anchor)
        left, top, right, bottom = self.selection
        self.selection = (left + dx, top + dy, right + dx, bottom + dy)
        self.dirty = True
        return None

    def delete_selection(self):
        """Удаляет всё выделенное. Возвращает число удалённых записей."""
        ground, objects = self.selected_entries()
        overlay = self.selected_overlay()
        for anchor, _ in objects:
            self._remove_object(anchor)
        for tile, _ in ground:
            del self.ground[tile]
        for tile, _ in overlay:
            del self.overlay[tile]
        if ground or objects or overlay:
            self.dirty = True
        return len(ground) + len(objects) + len(overlay)

    def copy_selection(self):
        """Копия выделенного: слои земли, поверх земли и объектов со смещением от левого верхнего угла выделения."""
        if self.selection is None:
            return None
        left, top, right, bottom = self.selection
        ground, objects = self.selected_entries()
        overlay = self.selected_overlay()
        if not ground and not objects and not overlay:
            return None

        def shifted(entries):
            return [(x - left, y - top, key) for (x, y), key in entries]

        return {
            "w": right - left + 1,
            "h": bottom - top + 1,
            "ground": shifted(ground),
            "overlay": shifted(overlay),
            "objects": shifted(objects),
        }

    def make_stamp(self, entries):
        """Кусок из списка (dx, dy, ключ), например тайлов каталога: каждый элемент попадает в свой слой."""
        stamp = {"w": 0, "h": 0, "ground": [], "overlay": [], "objects": []}
        for dx, dy, key in entries:
            item = self.items.get(key)
            if item is None:
                continue
            if item["kind"] != "ground":
                layer = "objects"
            elif key in self.overlay_keys:
                layer = "overlay"
            else:
                layer = "ground"
            stamp[layer].append((dx, dy, key))
            stamp["w"] = max(stamp["w"], dx + 1)
            stamp["h"] = max(stamp["h"], dy + 1)
        return stamp if stamp["w"] else None

    def paste(self, stamp, x, y):
        """Вставляет кусок левым верхним углом в (x, y); пустые клетки куска карту не меняют.

        Возвращает текст ошибки или None. Вставленная область становится выделением.
        """
        for dx, dy, key in stamp["ground"] + stamp["overlay"]:
            if not self.inside(x + dx, y + dy):
                return "Кусок выходит за край карты"
        for dx, dy, key in stamp["objects"]:
            if not all(self.inside(*tile) for tile in self.footprint(key, x + dx, y + dy)):
                return "Кусок выходит за край карты"
        for dx, dy, key in stamp["ground"]:
            self.ground[(x + dx, y + dy)] = key
            self.overlay.pop((x + dx, y + dy), None)
        for dx, dy, key in stamp["overlay"]:
            self.overlay[(x + dx, y + dy)] = key
        for dx, dy, key in stamp["objects"]:
            anchor = (x + dx, y + dy)
            for tile in self.footprint(key, *anchor):
                cover = self.cover.get(tile)
                if cover is not None:
                    self._remove_object(cover)
            self._add_object(key, *anchor)
        self.selection = (x, y, min(x + stamp["w"] - 1, self.map_w - 1), min(y + stamp["h"] - 1, self.map_h - 1))
        self.dirty = True
        return None

    def clear(self):
        if not self.ground and not self.overlay and not self.objects and not self.mobs:
            return
        self.ground = {}
        self.overlay = {}
        self.objects = {}
        self.cover = {}
        self.mobs = {}
        self.spawns = []
        self.selection = None
        self.dirty = True

    def begin_action(self):
        """Запоминает состояние перед действием; вызывается перед кликом или командой меню."""
        self._pending = self._snapshot()

    def end_action(self):
        """Записывает действие в историю, если карта изменилась. Возвращает True, если записано."""
        before, self._pending = self._pending, None
        if before is None or before == self._snapshot():
            return False
        self.undo_stack.append(before)
        del self.undo_stack[:-UNDO_LIMIT]
        self.redo_stack.clear()
        return True

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        return True

    def to_cells(self):
        cells = [{"layer": "ground", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.ground.items())]
        cells += [{"layer": "overlay", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.overlay.items())]
        cells += [{"layer": "object", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.objects.items())]
        return cells

    def place_mob(self, kind, x, y):
        """Ставит беса на клетку; на клетке может стоять только один бес — новый заменяет старого. Возвращает текст ошибки или None."""
        if kind not in NPC_KINDS:
            return "Такого беса нет в каталоге"
        if not self.inside(x, y):
            return "Клетка вне карты"
        if self.mobs.get((x, y)) != kind:
            self.mobs[(x, y)] = kind
            self.dirty = True
        return None

    def erase_mob(self, x, y):
        """Убирает беса с клетки. Возвращает True, если бес был."""
        if (x, y) not in self.mobs:
            return False
        del self.mobs[(x, y)]
        self.dirty = True
        return True

    def load_mobs(self, mobs):
        """Расстановка из черновика; неизвестные виды и клетки за краем карты пропускаются."""
        self.mobs = {}
        for mob in mobs or []:
            kind, x, y = mob.get("kind"), int(mob.get("x", -1)), int(mob.get("y", -1))
            if kind in NPC_KINDS and self.inside(x, y):
                self.mobs[(x, y)] = kind

    def to_mobs(self):
        return [
            {"kind": kind, "x": x, "y": y}
            for (x, y), kind in sorted(self.mobs.items(), key=lambda item: (item[0][1], item[0][0]))
        ]

    def toggle_spawn(self, x, y):
        """Точка спауна: ставит, если её нет, и убирает, если есть. Возвращает 'added', 'removed' или текст ошибки."""
        if not self.inside(x, y):
            return "Клетка вне карты"
        if (x, y) in self.spawns:
            self.spawns.remove((x, y))
            self.dirty = True
            return "removed"
        self.spawns.append((x, y))
        self.dirty = True
        return "added"

    def erase_spawn(self, x, y):
        if (x, y) not in self.spawns:
            return False
        self.spawns.remove((x, y))
        self.dirty = True
        return True

    def load_spawns(self, spawns):
        self.spawns = []
        for spawn in spawns or []:
            x, y = int(spawn.get("x", -1)), int(spawn.get("y", -1))
            if self.inside(x, y) and (x, y) not in self.spawns:
                self.spawns.append((x, y))

    def to_spawns(self):
        return [{"x": x, "y": y} for x, y in self.spawns]

    def mark_saved(self):
        self.dirty = False

    def _snapshot(self):
        return (dict(self.ground), dict(self.overlay), dict(self.objects), dict(self.mobs), list(self.spawns))

    def _restore(self, snapshot):
        ground, overlay, objects, mobs, spawns = snapshot
        self.ground = dict(ground)
        self.overlay = dict(overlay)
        self.mobs = dict(mobs)
        self.spawns = list(spawns)
        self.objects = {}
        self.cover = {}
        self.selection = None
        for (x, y), key in objects.items():
            self._add_object(key, x, y)
        self.dirty = True

    def _add_object(self, key, x, y):
        self.objects[(x, y)] = key
        for tile in self.footprint(key, x, y):
            self.cover[tile] = (x, y)

    def _remove_object(self, anchor):
        key = self.objects.pop(anchor)
        for tile in self.footprint(key, *anchor):
            if self.cover.get(tile) == anchor:
                del self.cover[tile]
