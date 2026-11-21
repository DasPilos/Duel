"""Клетки карты редактора по слоям, без зависимости от Pygame."""
from collections import deque

from core.crystal_growth import crystal_colors, validate_settings
from core.map_catalog import (
    WATER_ANIMAL_KEYS, infrastructure_keys, overlay_keys, palette_storage_layer_keys, road_keys,
    terrain_layer_for_key, water_decor_requires_water_keys,
)
from core.npc_catalog import NPC_CATALOG

UNDO_LIMIT = 100
NPC_KINDS = frozenset(npc["key"] for npc in NPC_CATALOG)


class MapEditorState:
    def __init__(self, catalog, cells, map_w, map_h):
        self.items = {item["item_key"]: item for item in catalog}
        self.allow_cross_layer_placements = False
        self.replace_other_layers = False
        self.water_decor_requires_water_keys = water_decor_requires_water_keys()
        self.map_w = map_w
        self.map_h = map_h
        self.ground = {}
        self.overlay = {}
        self.elevation = {}
        self.relief = {}
        self.infra = {}
        self.overlay_keys = overlay_keys()
        self.road_set = frozenset(road_keys())
        self.infra_keys = infrastructure_keys()
        self.objects = {}
        self.cover = {}
        self.mobs = {}
        self.spawns = []
        self.crystal_settings = {}
        self.harvest_enabled = False
        self.version = 0
        self.dirty = False
        self.selection = None
        self.undo_stack = []
        self.redo_stack = []
        self._pending = None
        self.name = ""
        self._load(cells)

    def _load(self, cells):
        migrated = []
        base_keys = palette_storage_layer_keys("ground")
        for cell in cells:
            key = cell["key"]
            if key not in self.items:
                continue
            pos = (cell["x"], cell["y"])
            terrain_layer = terrain_layer_for_key(key)
            if cell["layer"] in ("elevation", "relief"):
                getattr(self, cell["layer"])[pos] = key
            elif cell["layer"] == "infra" or (cell["layer"] == "ground" and key in self.infra_keys):
                # Инфраструктура из старых черновиков лежала в слое земли и стирала её под собой.
                self.infra[pos] = key
            elif cell["layer"] == "ground" and key in base_keys:
                self.ground[pos] = key
            elif cell["layer"] == "overlay":
                self.overlay[pos] = key
            elif cell["layer"] == "ground" and key in self.overlay_keys:
                # Дороги и прозрачные тайлы из старых черновиков лежали в слое земли. Переносятся после слоя 2.
                migrated.append((pos, key))
            elif cell["layer"] == "ground" and terrain_layer:
                getattr(self, terrain_layer)[pos] = key
            elif cell["layer"] == "ground":
                self.ground[pos] = key
            else:
                self._add_object(key, cell["x"], cell["y"])
        for pos, key in migrated:
            under = self.overlay.get(pos)
            if under is not None and under not in self.road_set:
                # Трава или переход поверх дороги в старых черновиках генератора: уходит в слой земли, дорога остаётся в слое 2.
                self.ground[pos] = under
            self.overlay[pos] = key

    def replace_cells(self, cells):
        """Заменяет всю карту клетками, например картой башни. Действие попадает в историю отмены."""
        self.begin_action()
        self.ground = {}
        self.overlay = {}
        self.elevation = {}
        self.relief = {}
        self.infra = {}
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

    def _water_at(self, tile, updates=None, infra_updates=None):
        updates = updates or {}
        infra_updates = infra_updates or {}
        key = updates.get("ground", {}).get(tile, self.ground.get(tile))
        infra_key = infra_updates.get(tile, self.infra.get(tile))
        return key is not None and self.items.get(key, {}).get("category") == "water" and infra_key is None

    def _water_overlay_error(self, updates=None, infra_updates=None):
        if self.allow_cross_layer_placements:
            return None
        updates = updates or {}
        overlay_updates = updates.get("overlay", {})
        infra_updates = infra_updates or {}
        affected = (
            overlay_updates.keys()
            | updates.get("ground", {}).keys()
            | infra_updates.keys()
        )
        for tile in affected:
            key = overlay_updates.get(tile, self.overlay.get(tile))
            if (
                key is not None
                and (
                    self.items.get(key, {}).get("category") == "water"
                    or key in self.water_decor_requires_water_keys
                )
                and not self._water_at(tile, updates, infra_updates)
            ):
                return "Водные эффекты можно размещать только на тайлах воды"
        return None

    def _water_object_error(self, objects, updates=None, infra_updates=None):
        if self.allow_cross_layer_placements:
            return None
        for (x, y), key in objects:
            if key in WATER_ANIMAL_KEYS and not all(
                self._water_at(tile, updates, infra_updates) for tile in self.footprint(key, x, y)
            ):
                return "Водных животных можно размещать только на тайлах воды"
        return None

    def _water_objects_touching(self, tiles):
        return [
            (anchor, key)
            for anchor, key in self.objects.items()
            if key in WATER_ANIMAL_KEYS
            and any(tile in tiles for tile in self.footprint(key, *anchor))
        ]

    def _clear_other_layers(self, tile, keep_layer):
        changed = False
        for layer_name in ("ground", "overlay", "elevation", "relief", "infra"):
            if layer_name == keep_layer:
                continue
            layer = getattr(self, layer_name)
            if tile in layer:
                del layer[tile]
                changed = True
        anchor = self.cover.get(tile)
        if anchor is not None:
            self._remove_object(anchor)
            changed = True
        if changed:
            self.dirty = True

    def place(self, key, x, y, layer=None):
        """Ставит элемент в клетку. Объекты заменяют пересекающиеся с ними. Возвращает текст ошибки или None."""
        item = self.items.get(key)
        if item is None:
            return "Элемента нет в каталоге"
        if not self.inside(x, y):
            return "Клетка вне карты"
        if item["kind"] == "ground":
            if layer in ("ground", "overlay", "elevation", "relief", "infra"):
                target_layer = getattr(self, layer)
            elif key in self.infra_keys:
                target_layer = self.infra
            elif key in self.overlay_keys:
                target_layer = self.overlay
            elif terrain_layer := terrain_layer_for_key(key):
                target_layer = getattr(self, terrain_layer)
            else:
                target_layer = self.ground
            layer_name = next(
                name for name in ("ground", "overlay", "elevation", "relief", "infra")
                if target_layer is getattr(self, name)
            )
            error = self._water_object_error(
                self._water_objects_touching({(x, y)}),
                {layer_name: {(x, y): key}},
                {(x, y): key} if layer_name == "infra" else None,
            )
            if error:
                return error
            error = self._water_overlay_error(
                {layer_name: {(x, y): key}},
                {(x, y): key} if layer_name == "infra" else None,
            )
            if error:
                return error
            if self.replace_other_layers:
                self._clear_other_layers((x, y), layer_name)
            if target_layer is self.infra:
                if self.infra.get((x, y)) != key:
                    self.infra[(x, y)] = key
                    self.dirty = True
            elif target_layer is self.overlay:
                if self.overlay.get((x, y)) != key:
                    self.overlay[(x, y)] = key
                    self.dirty = True
            elif target_layer is self.elevation:
                if self.elevation.get((x, y)) != key:
                    self.elevation[(x, y)] = key
                    self.dirty = True
            elif target_layer is self.relief:
                if self.relief.get((x, y)) != key:
                    self.relief[(x, y)] = key
                    self.dirty = True
            elif self.ground.get((x, y)) != key:
                self.ground[(x, y)] = key
                self.dirty = True
            return None
        tiles = self.footprint(key, x, y)
        if not all(self.inside(tx, ty) for tx, ty in tiles):
            return "Элемент выходит за край карты"
        error = self._water_object_error([((x, y), key)])
        if error:
            return error
        if self.replace_other_layers:
            for tile in tiles:
                self._clear_other_layers(tile, "objects")
        if self.objects.get((x, y)) == key:
            return None
        for tile in tiles:
            anchor = self.cover.get(tile)
            if anchor is not None:
                self._remove_object(anchor)
        self._add_object(key, x, y)
        self.dirty = True
        return None

    def paint(self, key, x, y, size=1, layer=None):
        """Кисть квадратом size×size. Для объектов ставится один элемент в клетку (x, y)."""
        item = self.items.get(key)
        if item is None or item["kind"] != "ground" or size <= 1:
            return self.place(key, x, y, layer=layer)
        start = -(size // 2)
        tiles = {
            (x + dx, y + dy)
            for dx in range(start, start + size)
            for dy in range(start, start + size)
            if self.inside(x + dx, y + dy)
        }
        target_layer = getattr(self, layer) if layer in (
            "ground", "overlay", "elevation", "relief", "infra"
        ) else self._ground_layer_for(key)
        layer_name = next(
            name for name in ("ground", "overlay", "elevation", "relief", "infra")
            if target_layer is getattr(self, name)
        )
        updates = {layer_name: {tile: key for tile in tiles}}
        infra_updates = updates.get("infra")
        error = self._water_object_error(
            self._water_objects_touching(tiles),
            updates,
            infra_updates,
        ) or self._water_overlay_error(updates, infra_updates)
        if error:
            return error
        for tile_x, tile_y in sorted(tiles):
            error = self.place(key, tile_x, tile_y, layer=layer)
            if error:
                return error
        return None

    def fill(self, key, x, y, layer=None):
        """Заливает связанную область клеток того же вида земли. Возвращает число закрашенных клеток."""
        item = self.items.get(key)
        if item is None or item["kind"] != "ground" or not self.inside(x, y):
            return 0
        target_layer = (
            getattr(self, layer)
            if layer in ("ground", "overlay", "elevation", "relief", "infra")
            else self._ground_layer_for(key)
        )
        target = target_layer.get((x, y))
        if target == key:
            return 0
        seen = {(x, y)}
        queue = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            for tile in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if tile in seen or not self.inside(*tile) or target_layer.get(tile) != target:
                    continue
                seen.add(tile)
                queue.append(tile)
        layer_name = next(
            name for name in ("ground", "overlay", "elevation", "relief", "infra")
            if target_layer is getattr(self, name)
        )
        updates = {layer_name: {tile: key for tile in seen}}
        infra_updates = updates.get("infra")
        error = self._water_object_error(
            self._water_objects_touching(seen),
            updates,
            infra_updates,
        )
        if error:
            return error
        error = self._water_overlay_error(updates, infra_updates)
        if error:
            return error
        for tile in seen:
            if self.replace_other_layers:
                self._clear_other_layers(tile, layer_name)
            target_layer[tile] = key
        self.dirty = True
        return len(seen)

    def _ground_layer_for(self, key):
        if key in self.infra_keys:
            return self.infra
        if key in self.overlay_keys:
            return self.overlay
        terrain_layer = terrain_layer_for_key(key)
        if terrain_layer:
            return getattr(self, terrain_layer)
        return self.ground

    def erase(self, x, y, layer=None):
        """Удаляет верхний элемент клетки. Возвращает True, если что-то удалено."""
        if layer in (None, "object"):
            anchor = self.cover.get((x, y))
        else:
            anchor = None
        if anchor is not None:
            self._remove_object(anchor)
            self.dirty = True
            return True
        layers = (
            (getattr(self, layer),)
            if layer in ("ground", "overlay", "elevation", "relief", "infra")
            else (self.infra, self.relief, self.elevation, self.overlay, self.ground)
            if layer is None
            else ()
        )
        for tiles in layers:
            if (x, y) in tiles:
                del tiles[(x, y)]
                self.dirty = True
                return True
        if layer == "object":
            anchor = self.cover.get((x, y))
            if anchor is not None:
                self._remove_object(anchor)
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

    def selected_elevation(self):
        return [(tile, key) for tile, key in self.elevation.items() if self.in_selection(*tile)]

    def selected_relief(self):
        return [(tile, key) for tile, key in self.relief.items() if self.in_selection(*tile)]

    def selected_infra(self):
        return [(tile, key) for tile, key in self.infra.items() if self.in_selection(*tile)]

    def move_selection(self, dx, dy):
        """Переносит выделение на dx, dy клеток. Возвращает текст ошибки или None; при ошибке карта не меняется."""
        if self.selection is None or (dx == 0 and dy == 0):
            return None
        ground, objects = self.selected_entries()
        overlay = self.selected_overlay()
        elevation = self.selected_elevation()
        relief = self.selected_relief()
        infra = self.selected_infra()
        if not ground and not objects and not overlay and not elevation and not relief and not infra:
            return None
        for (x, y), _ in ground + overlay + elevation + relief + infra:
            if not self.inside(x + dx, y + dy):
                return "Выделение выходит за край карты"
        for (x, y), key in objects:
            if not all(self.inside(tx, ty) for tx, ty in self.footprint(key, x + dx, y + dy)):
                return "Выделение выходит за край карты"
        terrain_updates = {}
        for layer_name, entries in (
            ("ground", ground), ("overlay", overlay), ("elevation", elevation), ("relief", relief),
        ):
            layer_updates = terrain_updates.setdefault(layer_name, {})
            for tile, _ in entries:
                layer_updates[tile] = None
            for (x, y), key in entries:
                layer_updates[(x + dx, y + dy)] = key
        infra_updates = {tile: None for tile, _ in infra}
        infra_updates.update({(x + dx, y + dy): key for (x, y), key in infra})
        moved_anchors = {anchor for anchor, _ in objects}
        resulting_objects = [
            (anchor, key) for anchor, key in self.objects.items() if anchor not in moved_anchors
        ] + [((x + dx, y + dy), key) for (x, y), key in objects]
        error = self._water_object_error(resulting_objects, terrain_updates, infra_updates)
        if error:
            return error
        error = self._water_overlay_error(terrain_updates, infra_updates)
        if error:
            return error
        for anchor, _ in objects:
            self._remove_object(anchor)
        for tile, _ in ground:
            del self.ground[tile]
        for tile, _ in overlay:
            del self.overlay[tile]
        for tile, _ in elevation:
            del self.elevation[tile]
        for tile, _ in relief:
            del self.relief[tile]
        for tile, _ in infra:
            del self.infra[tile]
        for layer_name, entries in (
            ("ground", ground), ("overlay", overlay), ("elevation", elevation),
            ("relief", relief), ("infra", infra),
        ):
            target_layer = getattr(self, layer_name)
            for (x, y), key in entries:
                target = (x + dx, y + dy)
                if self.replace_other_layers:
                    self._clear_other_layers(target, layer_name)
                target_layer[target] = key
        for (x, y), key in objects:
            anchor = (x + dx, y + dy)
            for tile in self.footprint(key, *anchor):
                if self.replace_other_layers:
                    self._clear_other_layers(tile, "objects")
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
        elevation = self.selected_elevation()
        relief = self.selected_relief()
        infra = self.selected_infra()
        for anchor, _ in objects:
            self._remove_object(anchor)
        for tile, _ in ground:
            del self.ground[tile]
        for tile, _ in overlay:
            del self.overlay[tile]
        for tile, _ in elevation:
            del self.elevation[tile]
        for tile, _ in relief:
            del self.relief[tile]
        for tile, _ in infra:
            del self.infra[tile]
        if ground or objects or overlay or elevation or relief or infra:
            self.dirty = True
        return len(ground) + len(objects) + len(overlay) + len(elevation) + len(relief) + len(infra)

    def copy_selection(self):
        """Копирует выделенные слои со смещением от левого верхнего угла выделения."""
        if self.selection is None:
            return None
        left, top, right, bottom = self.selection
        ground, objects = self.selected_entries()
        overlay = self.selected_overlay()
        elevation = self.selected_elevation()
        relief = self.selected_relief()
        infra = self.selected_infra()
        if not ground and not objects and not overlay and not elevation and not relief and not infra:
            return None

        def shifted(entries):
            return [(x - left, y - top, key) for (x, y), key in entries]

        return {
            "w": right - left + 1,
            "h": bottom - top + 1,
            "ground": shifted(ground),
            "overlay": shifted(overlay),
            "elevation": shifted(elevation),
            "relief": shifted(relief),
            "infra": shifted(infra),
            "objects": shifted(objects),
        }

    def make_stamp(self, entries):
        """Кусок из списка (dx, dy, ключ), например тайлов каталога: каждый элемент попадает в свой слой."""
        stamp = {"w": 0, "h": 0, "ground": [], "overlay": [], "elevation": [], "relief": [], "infra": [], "objects": []}
        for entry in entries:
            dx, dy, key = entry[:3]
            palette_layer = entry[3] if len(entry) > 3 else None
            item = self.items.get(key)
            if item is None:
                continue
            if item["kind"] != "ground":
                layer = "objects"
            elif palette_layer in ("ground", "overlay", "elevation", "relief", "infra"):
                layer = palette_layer
            elif key in self.infra_keys:
                layer = "infra"
            elif key in self.overlay_keys:
                layer = "overlay"
            elif terrain_layer_for_key(key):
                layer = terrain_layer_for_key(key)
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
        elevation = stamp.get("elevation", [])
        relief = stamp.get("relief", [])
        infra = stamp.get("infra", [])
        for dx, dy, key in stamp["ground"] + stamp["overlay"] + elevation + relief + infra:
            if not self.inside(x + dx, y + dy):
                return "Кусок выходит за край карты"
        for dx, dy, key in stamp["objects"]:
            if not all(self.inside(*tile) for tile in self.footprint(key, x + dx, y + dy)):
                return "Кусок выходит за край карты"
        terrain_updates = {}
        for layer_name, entries in (
            ("ground", stamp["ground"]), ("overlay", stamp["overlay"]),
            ("elevation", elevation), ("relief", relief),
        ):
            terrain_updates[layer_name] = {(x + dx, y + dy): key for dx, dy, key in entries}
        infra_updates = {(x + dx, y + dy): key for dx, dy, key in infra}
        pasted_anchors = set()
        for dx, dy, key in stamp["objects"]:
            pasted_anchors.update(self.footprint(key, x + dx, y + dy))
        resulting_objects = [
            (anchor, key) for anchor, key in self.objects.items()
            if not any(tile in pasted_anchors for tile in self.footprint(key, *anchor))
        ] + [((x + dx, y + dy), key) for dx, dy, key in stamp["objects"]]
        error = self._water_object_error(resulting_objects, terrain_updates, infra_updates)
        if error:
            return error
        error = self._water_overlay_error(terrain_updates, infra_updates)
        if error:
            return error
        for dx, dy, key in stamp["ground"]:
            tile = (x + dx, y + dy)
            if self.replace_other_layers:
                self._clear_other_layers(tile, "ground")
            self.ground[tile] = key
        for dx, dy, key in stamp["overlay"]:
            tile = (x + dx, y + dy)
            if self.replace_other_layers:
                self._clear_other_layers(tile, "overlay")
            self.overlay[tile] = key
        for dx, dy, key in elevation:
            tile = (x + dx, y + dy)
            if self.replace_other_layers:
                self._clear_other_layers(tile, "elevation")
            self.elevation[tile] = key
        for dx, dy, key in relief:
            tile = (x + dx, y + dy)
            if self.replace_other_layers:
                self._clear_other_layers(tile, "relief")
            self.relief[tile] = key
        for dx, dy, key in infra:
            tile = (x + dx, y + dy)
            if self.replace_other_layers:
                self._clear_other_layers(tile, "infra")
            self.infra[tile] = key
        for dx, dy, key in stamp["objects"]:
            anchor = (x + dx, y + dy)
            for tile in self.footprint(key, *anchor):
                if self.replace_other_layers:
                    self._clear_other_layers(tile, "objects")
                cover = self.cover.get(tile)
                if cover is not None:
                    self._remove_object(cover)
            self._add_object(key, *anchor)
        self.selection = (x, y, min(x + stamp["w"] - 1, self.map_w - 1), min(y + stamp["h"] - 1, self.map_h - 1))
        self.dirty = True
        return None

    def clear(self):
        if not self.ground and not self.overlay and not self.elevation and not self.relief and not self.infra and not self.objects and not self.mobs:
            return
        self.ground = {}
        self.overlay = {}
        self.elevation = {}
        self.relief = {}
        self.infra = {}
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
        cells += [{"layer": "elevation", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.elevation.items())]
        cells += [{"layer": "relief", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.relief.items())]
        cells += [{"layer": "infra", "x": x, "y": y, "key": key} for (x, y), key in sorted(self.infra.items())]
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

    def set_crystal_settings(self, color, values):
        """Настройки роста и добычи цвета; values уже проверены validate_settings."""
        self.crystal_settings[color] = dict(values)
        self.dirty = True

    def toggle_harvest(self):
        self.harvest_enabled = not self.harvest_enabled
        self.dirty = True
        return self.harvest_enabled

    def load_crystals(self, crystals, harvest_enabled=False):
        """Настройки кристаллов из черновика; некорректные данные сбрасываются к значениям по умолчанию."""
        try:
            self.crystal_settings = validate_settings(crystals, crystal_colors(self.items))
        except ValueError:
            self.crystal_settings = {}
        self.harvest_enabled = bool(harvest_enabled)

    def to_crystals(self):
        return {color: dict(values) for color, values in self.crystal_settings.items()}

    def mark_saved(self):
        self.dirty = False

    def _snapshot(self):
        return (
            dict(self.ground), dict(self.overlay), dict(self.elevation), dict(self.relief), dict(self.infra),
            dict(self.objects), dict(self.mobs), list(self.spawns),
        )

    def _restore(self, snapshot):
        ground, overlay, elevation, relief, infra, objects, mobs, spawns = snapshot
        self.ground = dict(ground)
        self.overlay = dict(overlay)
        self.elevation = dict(elevation)
        self.relief = dict(relief)
        self.infra = dict(infra)
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
