"""Import and export game map drafts as Tiled TMX maps."""
import base64
import gzip
import hashlib
import json
import math
import os
import re
import struct
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from core import map_catalog
from core.game_modes import DEFAULT_MODE, is_mode
from core.npc_catalog import NPC_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TILED_DIR = PROJECT_ROOT / "tiled"
TILESETS_DIR = TILED_DIR / "tilesets"
MAPS_DIR = TILED_DIR / "maps"
TILE_SIZE = 32
GID_MASK = 0x1FFFFFFF
EDITOR_LAYER_NAMES = (
    "Вода",
    "Декор воды",
    "Основа суши",
    "Декор суши",
    "Скалы, горы и водопады",
    "Постройки",
    "Декор местности",
    "Животные",
    "Мобы",
)
STORAGE_LAYERS = ("ground", "overlay", "elevation", "relief", "infra")
NPC_KINDS = frozenset(item["key"] for item in NPC_CATALOG)


@dataclass(frozen=True)
class TmxImport:
    draft: dict
    warnings: list
    # Draft fields (mode, mobs, spawns, crystals, harvest_enabled) that the TMX really describes.
    explicit: frozenset = frozenset()


def _property(parent, name, value, value_type=None):
    properties = parent.find("properties")
    if properties is None:
        properties = ET.SubElement(parent, "properties")
    prop = ET.SubElement(properties, "property", {"name": name})
    if value_type:
        prop.set("type", value_type)
    if isinstance(value, (dict, list)):
        prop.set("value", json.dumps(value, ensure_ascii=False))
    elif isinstance(value, bool):
        prop.set("value", "true" if value else "false")
    else:
        prop.set("value", str(value))


def _properties(element):
    properties = {}
    parent = element.find("properties")
    if parent is None:
        return properties
    for prop in parent.findall("property"):
        value = prop.get("value", prop.text or "")
        kind = prop.get("type")
        if kind == "bool":
            value = value.casefold() == "true"
        elif kind == "int":
            try:
                value = int(value)
            except ValueError:
                pass
        elif kind == "float":
            try:
                value = float(value)
            except ValueError:
                pass
        properties[prop.get("name", "")] = value
    return properties


def _safe_name(value):
    normalized = str(value).casefold()
    safe = re.sub(r"[^a-z0-9_-]+", "_", normalized).strip("_")
    if not safe:
        safe = "tileset"
    if safe != normalized.strip("_"):
        suffix = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe}_{suffix}"
    return safe


def _relative_path(path, base_dir):
    path = Path(path).resolve()
    try:
        return Path(os.path.relpath(path, Path(base_dir).resolve())).as_posix()
    except ValueError:
        return path.as_posix()


@lru_cache(maxsize=1)
def _item_specs():
    return {
        **map_catalog.rocky_tile_specs(),
        **map_catalog.winter_tile_specs(),
        **map_catalog.undead_tile_specs(),
        **map_catalog.desert_tile_specs(),
        **map_catalog.grassland_tile_specs(),
    }


@lru_cache(maxsize=1)
def _animation_specs():
    return {
        **map_catalog.rocky_animations(),
        **map_catalog.winter_animations(),
        **map_catalog.undead_animations(),
        **map_catalog.desert_animations(),
        **map_catalog.grassland_animations(),
    }


def _source_path(asset):
    path = (PROJECT_ROOT / "assets" / "map" / Path(*asset.split("/"))).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Map asset is missing: {path}")
    return path


def _image_frames(item, specs, animations):
    asset_path = _source_path(item["asset"])
    with Image.open(asset_path) as source:
        image = source.convert("RGBA")

    spec = specs.get(item["item_key"], {})
    animation = animations.get(item["item_key"])
    frame_ids = animation.get("tile_ids") if animation else None
    if frame_ids and spec.get("tile_id") is not None:
        columns = int(spec.get("columns") or image.width // TILE_SIZE)
        frame_size = image.width // columns
        frames = []
        for tile_id in frame_ids:
            column, row = tile_id % columns, tile_id // columns
            box = (
                column * frame_size,
                row * frame_size,
                (column + 1) * frame_size,
                (row + 1) * frame_size,
            )
            frame = image.crop(box)
            if frame.size != (TILE_SIZE, TILE_SIZE):
                raise ValueError(f"Animation tile is outside its image: {item['item_key']}")
            frames.append(frame)
        return frames

    if animation and not frame_ids:
        frame_width, frame_height = map(int, animation["frame"])
        frames = []
        for index in range(int(animation["frames"])):
            column = index % int(animation["cols"])
            row = index // int(animation["cols"])
            frame = image.crop((
                column * frame_width,
                row * frame_height,
                (column + 1) * frame_width,
                (row + 1) * frame_height,
            ))
            if frame.size != (frame_width, frame_height):
                raise ValueError(f"Animation frame is outside its image: {item['item_key']}")
            frames.append(frame)
        return frames

    if (
        spec.get("tile_id") is not None
        and (spec.get("representation") == "sprite" or item["kind"] == "object")
    ):
        columns = int(spec.get("columns") or image.width // TILE_SIZE)
        tile_size = image.width // columns
        tile_id = int(spec["tile_id"])
        return [image.crop((
            tile_id % columns * tile_size,
            tile_id // columns * tile_size,
            (tile_id % columns + 1) * tile_size,
            (tile_id // columns + 1) * tile_size,
        ))]

    if item.get("category") in {"tree", "old_tree"}:
        from scenes.world_map_scene import MAP_TREE_SHEETS

        frame_size = MAP_TREE_SHEETS.get(item["item_key"])
        if frame_size:
            return [image.crop((0, 0, frame_size[0], frame_size[1]))]

    if item.get("category") == "animal":
        from core.map_animals import ANIMAL_SHEETS

        sheet = ANIMAL_SHEETS.get(item["item_key"].removeprefix("animal_"))
        if sheet:
            frame_size = int(sheet[0])
            return [image.crop((0, 0, frame_size, frame_size))]
    return [image]


def _set_image(element, path, width=None, height=None):
    attributes = {"source": path.as_posix()}
    if width is not None:
        attributes["width"] = str(width)
    if height is not None:
        attributes["height"] = str(height)
    ET.SubElement(element, "image", attributes)


def _write_sheet_tileset(path, name, asset, items, specs, animations):
    image_path = _source_path(asset)
    with Image.open(image_path) as image:
        width, height = image.size
    if width % TILE_SIZE or height % TILE_SIZE:
        raise ValueError(f"Tilesheet dimensions must align to {TILE_SIZE}px: {image_path}")
    columns, rows = width // TILE_SIZE, height // TILE_SIZE
    tilecount = columns * rows
    root = ET.Element("tileset", {
        "version": "1.10",
        "tiledversion": "1.12.2",
        "name": name,
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "tilecount": str(tilecount),
        "columns": str(columns),
        "objectalignment": "bottom",
    })
    relative_image = _relative_path(image_path, path.parent)
    _set_image(root, Path(relative_image), width, height)
    by_id = {}
    for item in items:
        tile_id = int(specs[item["item_key"]]["tile_id"])
        if not 0 <= tile_id < tilecount:
            raise ValueError(f"Tile id is outside its sheet: {item['item_key']}")
        previous = by_id.get(tile_id)
        if previous is not None and previous["item_key"] != item["item_key"]:
            raise ValueError(f"Two catalog items use {asset} tile {tile_id}")
        by_id[tile_id] = item
    tile_gids = {}
    for tile_id, item in sorted(by_id.items()):
        tile = ET.SubElement(root, "tile", {
            "id": str(tile_id),
            "type": item.get("category", ""),
        })
        _property(tile, "item_key", item["item_key"])
        tile_gids[item["item_key"]] = tile_id
        animation = animations.get(item["item_key"])
        if animation:
            frame_ids = animation.get("tile_ids")
            if frame_ids:
                frames = frame_ids
            else:
                frames = [
                    tile_id + frame
                    for frame in range(int(animation["frames"]))
                ]
            durations = animation.get("durations", [])
            animated = ET.SubElement(tile, "animation")
            for index, frame_id in enumerate(frames):
                duration = durations[index] if index < len(durations) else 150
                ET.SubElement(animated, "frame", {
                    "tileid": str(int(frame_id)),
                    "duration": str(int(duration)),
                })
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return tilecount, tile_gids


def _write_collection_tileset(path, name, items, specs, animations, output_dir):
    root = ET.Element("tileset", {
        "version": "1.10",
        "tiledversion": "1.12.2",
        "name": name,
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "tilecount": "0",
        "columns": "0",
        "objectalignment": "bottom",
    })
    frames_dir = output_dir / "images"
    records = []
    key_tile_ids = {}
    next_id = 0
    for item in sorted(items, key=lambda value: value["item_key"]):
        tile_id = next_id
        key_tile_ids[item["item_key"]] = tile_id
        next_id += 1
        frames = _image_frames(item, specs, animations)
        frame_ids = [tile_id]
        base_frame = frames[0]
        tile = ET.SubElement(root, "tile", {
            "id": str(tile_id),
            "type": item.get("category", ""),
        })
        _property(tile, "item_key", item["item_key"])
        tile_asset = _tile_image_path(item, base_frame, frames_dir)
        _set_image(
            tile,
            Path(_relative_path(tile_asset, path.parent)),
            *base_frame.size,
        )
        animation = animations.get(item["item_key"])
        if animation and len(frames) > 1:
            for frame_index, frame in enumerate(frames[1:], 1):
                frame_id = next_id
                next_id += 1
                frame_ids.append(frame_id)
                frame_tile = ET.SubElement(root, "tile", {"id": str(frame_id)})
                _property(frame_tile, "animation_frame", True, "bool")
                frame_path = _write_frame_image(frames_dir, item["item_key"], frame_index, frame)
                _set_image(
                    frame_tile,
                    Path(_relative_path(frame_path, path.parent)),
                    *frame.size,
                )
            animated = ET.SubElement(tile, "animation")
            durations = animation.get("durations", [])
            for frame_index, frame_id in enumerate(frame_ids):
                duration_index = frame_index
                duration = (
                    durations[duration_index]
                    if duration_index < len(durations)
                    else 150
                )
                ET.SubElement(animated, "frame", {
                    "tileid": str(frame_id),
                    "duration": str(int(duration)),
                })
        records.append({
            "key": item["item_key"],
            "tile_id": tile_id,
            "width": base_frame.width,
            "height": base_frame.height,
        })
    root.set("tilecount", str(next_id))
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return next_id, key_tile_ids, records


def _tile_image_path(item, frame, frames_dir):
    animation = _animation_specs().get(item["item_key"])
    spec = _item_specs().get(item["item_key"], {})
    needs_crop = bool(
        (animation and (animation.get("tile_ids") or int(animation.get("frames", 0)) > 1))
        or (
            spec.get("representation") == "sprite"
            and spec.get("tile_id") is not None
        )
        or item["kind"] == "object" and spec.get("tile_id") is not None
        or item.get("category") in {"tree", "old_tree", "animal"}
    )
    if not needs_crop:
        return _source_path(item["asset"])
    return _write_frame_image(frames_dir, item["item_key"], 0, frame)


def _write_frame_image(directory, item_key, frame_index, image):
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_name(item_key)}_frame_{frame_index:02d}.png"
    path = directory / filename
    image.save(path)
    return path


def _build_tilesets(output_dir=TILESETS_DIR, catalog=None):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = list(map_catalog.catalog_definitions() if catalog is None else catalog)
    specs = _item_specs()
    animations = _animation_specs()
    sheet_items = defaultdict(list)
    collection_items = []
    for item in catalog:
        spec = specs.get(item["item_key"], {})
        if (
            item["kind"] == "ground"
            and spec.get("tile_id") is not None
            and spec.get("representation") != "sprite"
        ):
            sheet_items[item["asset"]].append(item)
        else:
            collection_items.append(item)

    tilesets = []
    key_locations = {}
    used_names = set()
    for asset, items in sorted(sheet_items.items()):
        base = _safe_name(Path(asset).stem)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base}_{suffix}"
            suffix += 1
        used_names.add(name)
        filename = f"{name}.tsx"
        path = output_dir / filename
        tilecount, local_ids = _write_sheet_tileset(
            path, name, asset, items, specs, animations,
        )
        tilesets.append({
            "name": name,
            "source": filename,
            "path": path,
            "tilecount": tilecount,
            "keys": local_ids,
        })

    if collection_items:
        name = "game_objects"
        filename = f"{name}.tsx"
        path = output_dir / filename
        tilecount, local_ids, records = _write_collection_tileset(
            path,
            name,
            collection_items,
            specs,
            animations,
            output_dir,
        )
        tilesets.append({
            "name": name,
            "source": filename,
            "path": path,
            "tilecount": tilecount,
            "keys": local_ids,
            "records": records,
        })

    first_gid = 1
    for tileset in tilesets:
        tileset["firstgid"] = first_gid
        for key, local_id in tileset["keys"].items():
            key_locations[key] = (tileset, local_id)
        first_gid += tileset["tilecount"]
    return tilesets, key_locations


def write_tilesets(output_dir=TILESETS_DIR, catalog=None):
    """Write external TSX tilesets and return a small summary."""
    tilesets, _locations = _build_tilesets(output_dir, catalog)
    return {
        "files": [item["source"] for item in tilesets],
        "tile_counts": {item["name"]: item["tilecount"] for item in tilesets},
    }


def _draft_layers(draft):
    layers = [list(draft.get("cells", []))]
    layers.extend(list(cells) for cells in draft.get("editor_layers", []))
    return (layers + [[] for _ in range(9 - len(layers))])[:9]


def _editor_index(item, cell):
    if item.get("category") == "animal":
        return 7
    if item.get("kind") == "object":
        return 5 if item.get("category") in {
            "building", "bridge", "house", "structure",
        } else 6
    return max(0, min(8, int(item.get("editor_layer", 3)) - 1))


def _cell_gid(cell, key_locations):
    try:
        tileset, local_id = key_locations[cell["key"]]
    except KeyError as error:
        raise ValueError(f"Map item has no Tiled tile: {cell['key']}") from error
    return tileset["firstgid"] + local_id


def _append_map_properties(root, draft):
    _property(root, "game_tmx_version", 1, "int")
    _property(root, "game_name", draft.get("name", ""))
    _property(root, "game_mode", draft.get("mode", DEFAULT_MODE))
    _property(root, "harvest_enabled", bool(draft.get("harvest_enabled", False)), "bool")
    _property(root, "crystals", draft.get("crystals") or {})


def _write_layer_data(layer, gids, width, height):
    data = ET.SubElement(layer, "data", {"encoding": "csv"})
    values = (
        str(gids.get((x, y), 0))
        for y in range(height)
        for x in range(width)
    )
    data.text = ",".join(values)


def _item_by_key(catalog):
    return {item["item_key"]: item for item in catalog}


def export_draft_to_tmx(draft, path, *, tilesets_dir=TILESETS_DIR):
    path = Path(path).resolve()
    catalog = map_catalog.catalog_definitions()
    path.parent.mkdir(parents=True, exist_ok=True)
    draft_keys = {
        cell["key"]
        for cells in _draft_layers(draft)
        for cell in cells
    }
    biome_prefixes = {key.partition("_")[0] for key in draft_keys}
    catalog = [
        item for item in catalog
        if item["item_key"] in draft_keys
        or item["item_key"].partition("_")[0] in biome_prefixes
    ]
    tilesets_dir = Path(tilesets_dir).resolve()
    output_tilesets = tilesets_dir / f"{_safe_name(path.stem)}_tilesets"
    tilesets, key_locations = _build_tilesets(output_tilesets, catalog)
    catalog_by_key = _item_by_key(catalog)
    width, height = int(draft["map_w"]), int(draft["map_h"])
    if width <= 0 or height <= 0:
        raise ValueError("Map dimensions must be positive")
    root = ET.Element("map", {
        "version": "1.10",
        "tiledversion": "1.12.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(width),
        "height": str(height),
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "infinite": "0",
    })
    _append_map_properties(root, draft)
    for tileset in tilesets:
        tsx_path = Path(tileset["path"])
        ET.SubElement(root, "tileset", {
            "firstgid": str(tileset["firstgid"]),
            "source": _relative_path(tsx_path, path.parent),
        })

    all_layers = _draft_layers(draft)
    group_cells = defaultdict(lambda: defaultdict(list))
    group_objects = defaultdict(list)
    for layer_index, cells in enumerate(all_layers):
        for cell in cells:
            item = catalog_by_key.get(cell["key"])
            if item is None:
                raise ValueError(f"Unknown map item: {cell['key']}")
            editor_index = layer_index if layer_index else _editor_index(item, cell)
            editor_index = max(0, min(8, editor_index))
            if item["kind"] == "object" or cell.get("layer") == "object":
                group_objects[editor_index].append((cell, item))
            else:
                storage = cell.get("layer")
                if storage not in STORAGE_LAYERS:
                    storage = "ground"
                group_cells[editor_index][storage].append(cell)

    ids = {"layer": 1, "object": 1}
    for editor_index in range(9):
        if not group_cells[editor_index] and not group_objects[editor_index] and (
            editor_index != 8 or not draft.get("mobs") and not draft.get("spawns")
        ):
            continue
        number = editor_index + 1
        group = ET.SubElement(root, "group", {
            "id": str(ids["layer"]),
            "name": f"{number} {EDITOR_LAYER_NAMES[editor_index]}",
        })
        ids["layer"] += 1
        _property(group, "editor_layer", number, "int")
        for storage in STORAGE_LAYERS:
            cells = group_cells[editor_index].get(storage, [])
            if not cells:
                continue
            layer = ET.SubElement(group, "layer", {
                "id": str(ids["layer"]),
                "name": storage,
                "width": str(width),
                "height": str(height),
            })
            ids["layer"] += 1
            _property(layer, "storage", storage)
            gids = {}
            for cell in cells:
                x, y = int(cell["x"]), int(cell["y"])
                if not (0 <= x < width and 0 <= y < height):
                    raise ValueError(f"Map cell is outside dimensions: {(x, y)}")
                gids[x, y] = _cell_gid(cell, key_locations)
            _write_layer_data(layer, gids, width, height)
        objects = group_objects[editor_index]
        if objects:
            object_layer = ET.SubElement(group, "objectgroup", {
                "id": str(ids["layer"]),
                "name": "objects",
                "draworder": "topdown",
            })
            ids["layer"] += 1
            for cell, item in objects:
                x, y = int(cell["x"]), int(cell["y"])
                tileset, local_id = key_locations[item["item_key"]]
                gid = tileset["firstgid"] + local_id
                record = next(
                    (entry for entry in tileset.get("records", ())
                     if entry["key"] == item["item_key"]),
                    None,
                )
                object_width = int(record["width"]) if record else TILE_SIZE
                object_height = int(record["height"]) if record else TILE_SIZE
                obj = ET.SubElement(object_layer, "object", {
                    "id": str(ids["object"]),
                    "gid": str(gid),
                    "x": str(x * TILE_SIZE + TILE_SIZE // 2),
                    "y": str((y + 1) * TILE_SIZE),
                    "width": str(object_width),
                    "height": str(object_height),
                    "name": item.get("display_name", item["item_key"]),
                    "type": item["category"],
                })
                _property(obj, "item_key", item["item_key"])
                _property(obj, "cell_x", x, "int")
                _property(obj, "cell_y", y, "int")
                ids["object"] += 1
        if editor_index == 8 and draft.get("mobs"):
            object_layer = ET.SubElement(group, "objectgroup", {
                "id": str(ids["layer"]),
                "name": "mobs",
            })
            ids["layer"] += 1
            for mob in draft["mobs"]:
                obj = ET.SubElement(object_layer, "object", {
                    "id": str(ids["object"]),
                    "name": str(mob["kind"]),
                    "type": "mob",
                    "x": str(int(mob["x"]) * TILE_SIZE + TILE_SIZE // 2),
                    "y": str(int(mob["y"]) * TILE_SIZE + TILE_SIZE // 2),
                    "width": "0",
                    "height": "0",
                })
                _property(obj, "kind", mob["kind"])
                _property(obj, "cell_x", int(mob["x"]), "int")
                _property(obj, "cell_y", int(mob["y"]), "int")
                ids["object"] += 1
        if editor_index == 8 and draft.get("spawns"):
            object_layer = ET.SubElement(group, "objectgroup", {
                "id": str(ids["layer"]),
                "name": "spawns",
            })
            ids["layer"] += 1
            for spawn in draft["spawns"]:
                obj = ET.SubElement(object_layer, "object", {
                    "id": str(ids["object"]),
                    "name": "spawn",
                    "type": "spawn",
                    "x": str(int(spawn["x"]) * TILE_SIZE + TILE_SIZE // 2),
                    "y": str(int(spawn["y"]) * TILE_SIZE + TILE_SIZE // 2),
                    "width": "0",
                    "height": "0",
                })
                _property(obj, "cell_x", int(spawn["x"]), "int")
                _property(obj, "cell_y", int(spawn["y"]), "int")
                ids["object"] += 1
    root.set("nextlayerid", str(ids["layer"]))
    root.set("nextobjectid", str(ids["object"]))
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def _tileset_tile_properties(tileset_element, base_dir):
    source = tileset_element.get("source")
    if source:
        path = (base_dir / source).resolve()
        if not path.is_file():
            return None, {}
        root = ET.parse(path).getroot()
        tileset_dir = path.parent
    else:
        root = tileset_element
        tileset_dir = base_dir
    image = root.find("image")
    image_path = (
        (tileset_dir / image.get("source")).resolve()
        if image is not None and image.get("source")
        else None
    )
    tile_props = {
        int(tile.get("id")): _properties(tile)
        for tile in root.findall("tile")
    }
    return image_path, {
        "root": root,
        "tile_props": tile_props,
        "image_path": image_path,
    }


def _gid_lookup(root, map_path, catalog):
    specs = _item_specs()
    by_asset_tile = {}
    by_asset = defaultdict(list)
    by_key = _item_by_key(catalog)
    for item in catalog:
        spec = specs.get(item["item_key"], {})
        if spec.get("tile_id") is not None:
            by_asset_tile[(item["asset"], int(spec["tile_id"]))] = item["item_key"]
        by_asset[item["asset"]].append(item["item_key"])
    entries = root.findall("tileset")
    lookup = {}
    for index, entry in enumerate(entries):
        firstgid = int(entry.get("firstgid", "0"))
        endgid = (
            int(entries[index + 1].get("firstgid", "0"))
            if index + 1 < len(entries)
            else None
        )
        _image_path, data = _tileset_tile_properties(entry, map_path.parent)
        if data is None:
            continue
        props = data["tile_props"]
        image_path = data["image_path"]
        columns = int(data["root"].get("columns", "0") or 0)
        for local_id, values in props.items():
            key = values.get("item_key")
            if key in by_key:
                lookup[firstgid + local_id] = key
        if image_path is None:
            continue
        try:
            asset = image_path.relative_to((PROJECT_ROOT / "assets" / "map").resolve()).as_posix()
        except ValueError:
            continue
        if columns:
            for tile_id in range(max(0, (endgid - firstgid) if endgid else int(data["root"].get("tilecount", "0")))):
                key = by_asset_tile.get((asset, tile_id))
                if key:
                    lookup.setdefault(firstgid + tile_id, key)
        else:
            candidates = by_asset.get(asset, ())
            for local_id, key in enumerate(sorted(candidates)):
                if endgid is None or firstgid + local_id < endgid:
                    lookup.setdefault(firstgid + local_id, key)
    return lookup


def _decode_layer(layer, width, height):
    data = layer.find("data")
    if data is None:
        return []
    encoding = data.get("encoding")
    compression = data.get("compression")
    chunks = data.findall("chunk")
    pieces = chunks or [data]
    decoded = []
    for piece in pieces:
        x, y = int(piece.get("x", "0")), int(piece.get("y", "0"))
        piece_width = int(piece.get("width", str(width)))
        piece_height = int(piece.get("height", str(height)))
        text = (piece.text or "").strip()
        if encoding == "csv":
            values = [int(value) for value in re.split(r"[\s,]+", text) if value]
        elif encoding == "base64":
            raw = base64.b64decode(text)
            if compression == "zlib":
                raw = zlib.decompress(raw)
            elif compression == "gzip":
                raw = gzip.decompress(raw)
            elif compression == "zstd":
                raise ValueError("TMX zstd compression is not supported; choose zlib or gzip in Tiled")
            elif compression:
                raise ValueError(f"Unsupported TMX compression: {compression}")
            if len(raw) % 4:
                raise ValueError("TMX tile data byte length is not divisible by four")
            values = list(struct.unpack(f"<{len(raw) // 4}I", raw))
        elif encoding is None:
            values = [int(tile.get("gid", "0")) for tile in piece.findall("tile")]
        else:
            raise ValueError(f"Unsupported TMX tile encoding: {encoding}")
        decoded.append((x, y, piece_width, piece_height, values))
    return decoded


def _all_map_layers(root):
    def visit(parent, inherited_layer=None):
        for child in parent:
            if child.tag in {"layer", "objectgroup"}:
                yield child, inherited_layer
            elif child.tag == "group":
                group_props = _properties(child)
                editor_layer = group_props.get("editor_layer", inherited_layer)
                if editor_layer is None:
                    match = re.match(r"\s*(\d+)", child.get("name", ""))
                    editor_layer = int(match.group(1)) if match else None
                yield from visit(child, editor_layer)

    yield from visit(root)


def _storage_for_key(key, item, layer, props):
    explicit = props.get("storage")
    if explicit in STORAGE_LAYERS:
        return explicit
    if layer.get("name") in STORAGE_LAYERS:
        return layer.get("name")
    if key in _infrastructure_keys():
        return "infra"
    if key in _overlay_keys():
        return "overlay"
    terrain = map_catalog.terrain_layer_for_key(key)
    if terrain:
        return terrain
    if item.get("category") == "water":
        return "ground"
    return "ground"


@lru_cache(maxsize=1)
def _infrastructure_keys():
    return frozenset(map_catalog.infrastructure_keys())


@lru_cache(maxsize=1)
def _overlay_keys():
    return frozenset(map_catalog.overlay_keys())


def _object_cell(obj, props, width, height):
    if "cell_x" in props and "cell_y" in props:
        return int(props["cell_x"]), int(props["cell_y"])
    x = float(obj.get("x", "0"))
    y = float(obj.get("y", "0"))
    return round((x - TILE_SIZE / 2) / TILE_SIZE), round(y / TILE_SIZE) - 1


def _point_cell(obj, props):
    if "cell_x" in props and "cell_y" in props:
        return int(props["cell_x"]), int(props["cell_y"])
    x = float(obj.get("x", "0"))
    y = float(obj.get("y", "0"))
    return math.floor(x / TILE_SIZE), math.floor(y / TILE_SIZE)


def _map_bounds(root):
    if root.get("infinite", "0") != "1":
        return 0, 0, int(root.get("width", "0")), int(root.get("height", "0"))
    bounds = []
    for layer, _editor_layer in _all_map_layers(root):
        if layer.tag != "layer":
            continue
        for x, y, width, height, _values in _decode_layer(layer, 0, 0):
            bounds.append((x, y, x + width, y + height))
    if not bounds:
        return 0, 0, int(root.get("width", "0")), int(root.get("height", "0"))
    return (
        min(box[0] for box in bounds),
        min(box[1] for box in bounds),
        max(box[2] for box in bounds) - min(box[0] for box in bounds),
        max(box[3] for box in bounds) - min(box[1] for box in bounds),
    )


def import_tmx(path):
    path = Path(path).resolve()
    root = ET.parse(path).getroot()
    if root.tag != "map":
        raise ValueError("TMX root element must be <map>")
    map_width_px = int(root.get("tilewidth", str(TILE_SIZE)))
    map_height_px = int(root.get("tileheight", str(TILE_SIZE)))
    if map_width_px != TILE_SIZE or map_height_px != TILE_SIZE:
        raise ValueError(f"Game maps must use {TILE_SIZE}x{TILE_SIZE}px tiles")
    catalog = map_catalog.catalog_definitions()
    catalog_by_key = _item_by_key(catalog)
    gid_to_key = _gid_lookup(root, path, catalog)
    min_x, min_y, map_w, map_h = _map_bounds(root)
    if map_w <= 0 or map_h <= 0:
        raise ValueError("TMX map has no finite tile bounds")
    warnings = Counter()
    explicit = set()
    editor_cells = [[] for _ in range(9)]
    mobs, spawns = [], []
    flipped = 0
    for layer, editor_layer in _all_map_layers(root):
        props = _properties(layer)
        name = layer.get("name", "")
        index = (
            max(0, min(8, int(editor_layer) - 1))
            if editor_layer is not None
            else 0
        )
        if layer.tag == "layer":
            for chunk_x, chunk_y, chunk_width, chunk_height, values in _decode_layer(
                layer, int(root.get("width", "0")), int(root.get("height", "0")),
            ):
                if len(values) != chunk_width * chunk_height:
                    warnings["malformed tile layer cells"] += 1
                    continue
                for offset, raw_gid in enumerate(values):
                    flags = raw_gid & ~GID_MASK
                    gid = raw_gid & GID_MASK
                    if not gid:
                        continue
                    if flags:
                        flipped += 1
                    key = gid_to_key.get(gid)
                    if key is None:
                        warnings["unknown tile ids"] += 1
                        continue
                    item = catalog_by_key.get(key)
                    if item is None:
                        warnings["unknown catalog keys"] += 1
                        continue
                    x = chunk_x + offset % chunk_width - min_x
                    y = chunk_y + offset // chunk_width - min_y
                    if not (0 <= x < map_w and 0 <= y < map_h):
                        warnings["cells outside map bounds"] += 1
                        continue
                    storage = _storage_for_key(key, item, layer, props)
                    cell = {"layer": storage, "x": x, "y": y, "key": key}
                    editor_index = index
                    if editor_layer is None:
                        editor_index = max(0, min(8, int(item.get("editor_layer", 3)) - 1))
                    editor_cells[editor_index].append(cell)
        else:
            if name.casefold() in {"mobs", "spawns"}:
                explicit.add(name.casefold())
            for obj in layer.findall("object"):
                object_props = _properties(obj)
                object_type = str(
                    object_props.get("kind")
                    or obj.get("type")
                    or obj.get("class")
                    or ""
                ).casefold()
                if name.casefold() == "mobs" or object_type == "mob":
                    explicit.add("mobs")
                    kind = object_props.get("kind") or obj.get("name")
                    if kind in NPC_KINDS:
                        x, y = _point_cell(obj, object_props)
                        x, y = x - min_x, y - min_y
                        if 0 <= x < map_w and 0 <= y < map_h:
                            mobs.append({"kind": str(kind), "x": x, "y": y})
                        else:
                            warnings["mob objects outside map bounds"] += 1
                    elif kind:
                        warnings["unknown mob kinds"] += 1
                    continue
                if name.casefold() == "spawns" or object_type == "spawn":
                    explicit.add("spawns")
                    x, y = _point_cell(obj, object_props)
                    x, y = x - min_x, y - min_y
                    if 0 <= x < map_w and 0 <= y < map_h:
                        spawns.append({"x": x, "y": y})
                    else:
                        warnings["spawn objects outside map bounds"] += 1
                    continue
                raw_gid = int(obj.get("gid", "0"))
                if not raw_gid:
                    continue
                if raw_gid & ~GID_MASK:
                    flipped += 1
                key = object_props.get("item_key") or gid_to_key.get(raw_gid & GID_MASK)
                item = catalog_by_key.get(key)
                if item is None:
                    warnings["unknown object tiles"] += 1
                    continue
                x, y = _object_cell(obj, object_props, map_w, map_h)
                x, y = x - min_x, y - min_y
                if not (0 <= x < map_w and 0 <= y < map_h):
                    warnings["objects outside map bounds"] += 1
                    continue
                storage = "object" if item["kind"] == "object" else _storage_for_key(
                    key, item, layer, props,
                )
                object_layer_index = (
                    index
                    if editor_layer is not None
                    else _editor_index(item, {"layer": storage})
                )
                editor_cells[object_layer_index].append({
                    "layer": storage, "x": x, "y": y, "key": key,
                })

    if flipped:
        warnings["flipped tiles; flip flags were ignored"] += flipped
    props = _properties(root)
    mode = DEFAULT_MODE
    if "game_mode" in props:
        if is_mode(props["game_mode"]):
            mode = props["game_mode"]
            explicit.add("mode")
        else:
            warnings["unknown game mode; default mode used"] += 1
    crystals = {}
    if "crystals" in props:
        parsed_crystals = _parse_crystals(props["crystals"])
        if parsed_crystals is None:
            warnings["invalid crystals property; defaults used"] += 1
        else:
            crystals = parsed_crystals
            explicit.add("crystals")
    harvest_enabled = False
    if "harvest_enabled" in props:
        parsed_harvest = _parse_bool(props["harvest_enabled"])
        if parsed_harvest is None:
            warnings["invalid harvest_enabled property; ignored"] += 1
        else:
            harvest_enabled = parsed_harvest
            explicit.add("harvest_enabled")
    name = str(props.get("game_name") or path.stem)
    draft = {
        "name": name,
        "cells": editor_cells[0],
        "editor_layers": editor_cells[1:],
        "map_w": map_w,
        "map_h": map_h,
        "mode": mode,
        "mobs": mobs,
        "spawns": spawns,
        "crystals": crystals,
        "harvest_enabled": harvest_enabled,
    }
    warning_list = []
    for message, count in sorted(warnings.items()):
        warning_list.append(f"{message}: {count}")
    return TmxImport(draft, warning_list, frozenset(explicit))


def _parse_crystals(value):
    """Настройки кристаллов: словарь «цвет → словарь значений» либо JSON-строка с ним; иначе None."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict) and all(isinstance(item, dict) for item in value.values()):
        return value
    return None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    return None
