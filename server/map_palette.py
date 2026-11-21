"""Validation and collision handling for global map-palette changes."""

PALETTE_LAYERS = frozenset(range(1, 9))
GENERATOR_ROLES = frozenset({"random_decor"})


def validate_overrides(overrides, catalog):
    if not isinstance(overrides, dict):
        raise ValueError("Настройки палитры должны быть объектом")
    items = {item["item_key"]: item for item in catalog}
    result = {}
    for key, raw in overrides.items():
        if key not in items or not isinstance(raw, dict):
            raise ValueError(f"Настройка тайла «{key}» некорректна")
        allowed = {
            "blocks", "editor_layer", "generator_role", "palette_group",
            "palette_order", "palette_position",
        }
        if set(raw) - allowed:
            raise ValueError(f"Неизвестное свойство тайла «{key}»")
        value = {}
        if "blocks" in raw:
            if not isinstance(raw["blocks"], bool):
                raise ValueError(f"Проходимость тайла «{key}» должна быть логическим значением")
            value["blocks"] = raw["blocks"]
        if "editor_layer" in raw:
            layer = raw["editor_layer"]
            if not isinstance(layer, int) or isinstance(layer, bool) or layer not in PALETTE_LAYERS:
                raise ValueError(f"Слой тайла «{key}» должен быть от 1 до 8")
            if items[key]["kind"] == "object" and layer < 6:
                raise ValueError(f"Объект «{key}» нельзя назначить на слой {layer}")
            if items[key]["kind"] == "ground" and layer > 6:
                raise ValueError(f"Тайл земли «{key}» нельзя назначить на слой {layer}")
            value["editor_layer"] = layer
        if "generator_role" in raw:
            role = raw["generator_role"]
            if role is not None and role not in GENERATOR_ROLES:
                raise ValueError(f"Неизвестная роль генератора у тайла «{key}»")
            value["generator_role"] = role
        if "palette_group" in raw:
            group = raw["palette_group"]
            if group is not None and (not isinstance(group, str) or len(group) > 80):
                raise ValueError(f"Группа тайла «{key}» некорректна")
            value["palette_group"] = group
        if "palette_order" in raw:
            order = raw["palette_order"]
            if not isinstance(order, int) or isinstance(order, bool):
                raise ValueError(f"Порядок тайла «{key}» должен быть целым числом")
            value["palette_order"] = order
        if "palette_position" in raw:
            position = raw["palette_position"]
            if (
                not isinstance(position, dict)
                or set(position) != {"x", "y"}
                or not all(
                    isinstance(position[axis], int)
                    and not isinstance(position[axis], bool)
                    for axis in ("x", "y")
                )
                or not 0 <= position["x"] < 10
                or not 0 <= position["y"] <= 255
            ):
                raise ValueError(f"Позиция тайла «{key}» в палитре некорректна")
            value["palette_position"] = {
                "x": position["x"],
                "y": position["y"],
            }
        result[key] = value
    return result


def editor_layer(item, overrides):
    return overrides.get(item["item_key"], {}).get(
        "editor_layer",
        item.get("editor_layer", 3 if item["kind"] == "ground" else 7),
    )


def same_cells(first, second):
    """Whether two cell lists describe the same map, regardless of ordering."""
    cell_key = lambda cell: (
        str(cell["layer"]),
        int(cell["x"]),
        int(cell["y"]),
        str(cell["key"]),
    )
    return sorted(map(cell_key, first)) == sorted(map(cell_key, second))


def _storage_layer(item, artist_layer, previous_layer):
    if item["kind"] == "object":
        return "object"
    if artist_layer in (1, 3):
        return "ground"
    if artist_layer in (2, 4):
        return "overlay"
    if artist_layer == 5:
        return previous_layer if previous_layer in ("elevation", "relief") else "elevation"
    if artist_layer == 6:
        return "infra"
    if artist_layer in (7, 8):
        return "object"
    raise ValueError(f"Тайл «{item['item_key']}» нельзя поместить на слой {artist_layer}")


def remap_cells(cells, catalog, old_overrides, new_overrides, resolutions=None, context="map"):
    """Return remapped cells, unresolved conflicts, and cells removed on collisions."""
    resolutions = resolutions or {}
    items = {item["item_key"]: item for item in catalog}
    candidates = {}
    for cell in cells:
        key = cell["key"]
        item = items.get(key)
        if item is None:
            raise ValueError(f"Элемента «{key}» нет в каталоге")
        old_layer = editor_layer(item, old_overrides)
        new_layer = editor_layer(item, new_overrides)
        target = (
            _storage_layer(item, new_layer, cell["layer"])
            if old_layer != new_layer
            else cell["layer"]
        )
        moved = {**cell, "layer": target}
        candidates.setdefault((target, cell["x"], cell["y"]), []).append({
            "cell": moved,
            "moved": target != cell["layer"],
            "source_layer": cell["layer"],
        })

    remapped = []
    conflicts = []
    removed = []
    for (layer, x, y), entries in sorted(candidates.items()):
        if len(entries) == 1:
            remapped.append(entries[0]["cell"])
            continue
        conflict_id = f"{context}:{layer}:{x}:{y}"
        chosen_key = resolutions.get(conflict_id)
        chosen_entries = [
            entry for entry in entries
            if entry["cell"]["key"] == chosen_key
        ]
        if not chosen_entries:
            chosen_entries = entries
        chosen = min(
            chosen_entries,
            key=lambda entry: (
                entry["moved"],
                entry["cell"]["key"],
                entry["source_layer"],
            ),
        )
        remapped.append(chosen["cell"])
        removed.extend(
            {
                **entry["cell"],
                "source_layer": entry["source_layer"],
            }
            for entry in entries
            if entry is not chosen
        )
    return remapped, conflicts, removed
