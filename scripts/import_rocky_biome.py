"""Import used Rocky_area tiles, complete water compositions, and named growth stages."""
import argparse
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import pygame
from PIL import Image, ImageChops

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_ASSETS = PROJECT_ROOT / "assets" / "map"
TILE_SIZE = 16
SCALE = 2
GID_MASK = 0x1FFFFFFF
WATER_OBJECTS = (
    ("boat", "Лодка", ((25, "Boat.png", "Лодка"),)),
    ("sail", "Парус", ((21, "Sail.png", "Парус"),)),
    ("house", "Домик на сваях", ((28, "House.png", "Домик на сваях"),)),
    ("ruins_1", "Руины 1", ((1, "Ruins1.png", "Руины 1"),)),
    ("ruins_2", "Руины 2", ((6, "Ruins2.png", "Руины 2"),)),
    ("ruins_3", "Руины 3", ((8, "Ruins3.png", "Руины 3"),)),
    ("ruins_4", "Руины 4", ((10, "Ruins4.png", "Руины 4"),)),
    (
        "nessy",
        "Несси",
        (
            (17, "Nessy_head.png", "Несси · голова"),
            (19, "Nessy_tail.png", "Несси · хвост"),
        ),
    ),
)
GROWTH_NAME = re.compile(
    r"^(?P<base>.+)_(?P<stage>\d+)(?:-(?P<variant>\d+))?$",
    re.IGNORECASE,
)
GROWTH_SHADOW_NAME = re.compile(
    r"^(?P<base>.+?)_(?P<surface>grass|ground|wall)_shadow(?P<stage>\d+)?$",
    re.IGNORECASE,
)

SHEET_SETTINGS = {
    "Ground_moss": {"kind": "ground", "category": "grass", "layer": "ground", "title": "Скалистый биом · Земля (основа)"},
    "Water_coasts": {"kind": "ground", "category": "water", "layer": "ground", "title": "Скалистый биом · Береговая вода (основа)"},
    "Water_detilazation2": {"kind": "ground", "category": "water", "layer": "overlay", "title": "Скалистый биом · Анимированная вода"},
    "Waterfalls": {"kind": "ground", "category": "water", "layer": "overlay", "title": "Скалистый биом · Водопады"},
    "Objects": {"kind": "object", "category": "bush", "layer": "objects", "title": "Скалистый биом · Цельные объекты"},
    "Water_detilazation": {"kind": "ground", "category": "water", "layer": "overlay", "title": "Скалистый биом · Водные детали"},
    "details": {"kind": "object", "category": "bush", "layer": "objects", "title": "Скалистый биом · Мелкий декор (поверх земли)"},
    "Water_under_objects": {"kind": "ground", "category": "water", "layer": "overlay", "title": "Скалистый биом · Вода под объектами"},
}


def _read_tilesets(map_path):
    map_root = ET.parse(map_path).getroot()
    tilesets = []
    for index, entry in enumerate(map_root.findall("tileset")):
        first_gid = int(entry.attrib["firstgid"])
        source = entry.get("source")
        source_path = (map_path.parent / source).resolve() if source else None
        tileset = ET.parse(source_path).getroot() if source_path else entry
        image = tileset.find("image")
        if image is None:
            raise ValueError(f"Tileset {source or tileset.get('name')} has no image")
        image_path = ((source_path.parent if source_path else map_path.parent) / image.attrib["source"]).resolve()
        raw_name = Path(source).stem if source else Path(image.attrib["source"]).stem
        name = next(
            (known_name for known_name in SHEET_SETTINGS if known_name.casefold() == raw_name.casefold()),
            raw_name,
        )
        columns = int(tileset.attrib["columns"])
        tile_count = int(tileset.attrib["tilecount"])
        end_gid = (
            int(map_root.findall("tileset")[index + 1].attrib["firstgid"])
            if index + 1 < len(map_root.findall("tileset"))
            else first_gid + tile_count
        )
        animations = {}
        for tile in tileset.findall("tile"):
            frames = tile.find("animation")
            if frames is None:
                continue
            animation_frames = [
                {"tile_id": int(frame.attrib["tileid"]), "duration": int(frame.attrib["duration"])}
                for frame in frames.findall("frame")
            ]
            if not animation_frames:
                continue
            animations[int(tile.attrib["id"])] = animation_frames
        tilesets.append({
            "first_gid": first_gid,
            "end_gid": end_gid,
            "name": name,
            "path": image_path,
            "columns": columns,
            "tile_count": tile_count,
            "animations": animations,
        })
    return map_root, tilesets


def _used_tile_ids(map_root, tilesets):
    used = {tileset["name"]: set() for tileset in tilesets}
    layer_usage = {tileset["name"]: defaultdict(Counter) for tileset in tilesets}
    for layer in map_root.findall("layer"):
        data = layer.find("data")
        if data is None:
            continue
        chunks = data.findall("chunk")
        values = [value for chunk in chunks for value in (chunk.text or "").split(",")]
        if not chunks and data.text:
            values = data.text.split(",")
        for value in values:
            if not value.strip():
                continue
            gid = int(value.strip()) & GID_MASK
            if not gid:
                continue
            for tileset in tilesets:
                if tileset["first_gid"] <= gid < tileset["end_gid"]:
                    tile_id = gid - tileset["first_gid"]
                    name = tileset["name"]
                    used[name].add(tile_id)
                    layer_usage[name][tile_id][layer.get("name", "")] += 1
                    break
    return used, layer_usage


def _map_layer_tiles(map_root, tilesets):
    """Return non-empty Tiled cells as (layer, x, y, sheet, tile_id) records."""
    ordered = sorted(tilesets, key=lambda tileset: tileset["first_gid"])
    result = []
    for layer in map_root.findall("layer"):
        data = layer.find("data")
        if data is None:
            continue
        chunks = data.findall("chunk")
        sources = chunks or [data]
        for source in sources:
            if source.tag == "chunk":
                x, y = int(source.get("x", 0)), int(source.get("y", 0))
                width, height = int(source.attrib["width"]), int(source.attrib["height"])
            else:
                x, y = int(layer.get("x", 0)), int(layer.get("y", 0))
                width, height = int(layer.attrib["width"]), int(layer.attrib["height"])
            if data.get("encoding") == "csv":
                values = [value.strip() for value in (source.text or "").split(",") if value.strip()]
                if len(values) != width * height:
                    raise ValueError(f"Invalid CSV tile data in Tiled layer {layer.get('name')}")
                gids = [int(value) for value in values]
            else:
                gids = [int(tile.get("gid", "0")) for tile in source.findall("tile")]
                if len(gids) != width * height:
                    raise ValueError(f"Invalid tile data in Tiled layer {layer.get('name')}")
            for index, value in enumerate(gids):
                gid = value & GID_MASK
                if not gid:
                    continue
                tileset = next(
                    (entry for entry in ordered if entry["first_gid"] <= gid < entry["end_gid"]),
                    None,
                )
                if tileset is not None:
                    result.append((
                        layer.get("name", ""),
                        x + index % width,
                        y + index // width,
                        tileset["name"],
                        gid - tileset["first_gid"],
                    ))
    return result


def _position_groups(cells):
    """Split occupied (x, y) positions into groups connected by an edge."""
    remaining = set(cells)
    groups = []
    while remaining:
        start = min(remaining, key=lambda point: (point[1], point[0]))
        remaining.remove(start)
        stack, group = [start], []
        while stack:
            x, y = stack.pop()
            group.append((x, y))
            for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    return groups


def _visible_sprite_mask_signature(image):
    image = image.convert("RGBA")
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        return None
    visible_mask = image.getchannel("A").crop(bounds)
    return visible_mask.size, visible_mask.tobytes()


def _growth_sources(source_root):
    """Find explicit author-named tree, mushroom, and rock growth stages."""
    separate_dir = source_root / "PNG" / "Objects_separately"
    if not separate_dir.is_dir():
        return []
    candidates = defaultdict(list)
    for path in sorted(separate_dir.glob("*.png"), key=lambda item: item.name.casefold()):
        shadow = GROWTH_SHADOW_NAME.fullmatch(path.stem)
        if shadow:
            base = f"{shadow['base']}_{shadow['surface']}".casefold().replace("с", "c")
            is_rock = re.fullmatch(r"rock[123]_(?:grass|ground)", base) is not None
            is_mushroom = base.startswith(("big_mushrooms_", "blue-green_mushrooms_"))
            if not (is_rock or is_mushroom):
                continue
            if shadow["stage"] is None and not is_rock:
                continue
            stage = int(shadow["stage"] or 1)
            group = f"rocky_{re.sub(r'[^a-z0-9]+', '_', base).strip('_')}"
            candidates[group].append((stage, path, None))
            continue
        match = GROWTH_NAME.fullmatch(path.stem)
        if not match:
            continue
        base = match["base"].casefold().replace("с", "c")
        if not base.startswith("conifer_tree"):
            continue
        stage = int(match["stage"])
        variant = match["variant"]
        group = f"rocky_{re.sub(r'[^a-z0-9]+', '_', base).strip('_')}"
        candidates[group].append((stage, path, variant))

    sources = []
    for group, entries in sorted(candidates.items()):
        stages = {stage for stage, _path, variant in entries if variant is None}
        if len(stages) < 3:
            continue
        for stage, path, variant in entries:
            if variant is not None:
                continue
            sources.append((group, stage, path))
    return sources


def _water_object_groups(map_root, tilesets, sprites, output_dir, separate_dir):
    """Build object-and-wave stamps from the author's actual Tiled placements."""
    if not separate_dir.is_dir():
        return [], set(), []
    layer_tiles = _map_layer_tiles(map_root, tilesets)
    object_tiles = {index: tile_ids for index, (_bounds, _area, tile_ids, _sprite) in enumerate(sprites, start=1)}
    sprite_bounds = {index: bounds for index, (bounds, _area, _tile_ids, _sprite) in enumerate(sprites, start=1)}
    by_layer = defaultdict(list)
    water_effects = []
    animated_owners = {}
    for tileset in tilesets:
        if tileset["name"] not in ("Water_under_objects", "Water_detilazation2"):
            continue
        image = Image.open(tileset["path"]).convert("RGBA")
        animated_owners[tileset["name"]] = {
            tile_id
            for tile_id, frames in tileset["animations"].items()
            if any(
                _tile_crop(image, frame["tile_id"], tileset["columns"]).getbbox() is not None
                for frame in frames
            )
        }
    for layer, x, y, sheet, tile_id in layer_tiles:
        if sheet == "Objects" and layer.startswith("Objects"):
            by_layer[layer].append((x, y, tile_id))
        elif layer == "water_details" and sheet == "Water_under_objects" and tile_id in animated_owners.get(sheet, set()):
            water_effects.append((x, y, sheet, tile_id))

    placements = defaultdict(list)
    for layer, cells in by_layer.items():
        positions_by_component = defaultdict(set)
        for x, y, tile_id in cells:
            for component, tile_ids in object_tiles.items():
                if tile_id in tile_ids:
                    positions_by_component[component].add((x, y))
        for component, positions in positions_by_component.items():
            placements[component].extend(
                (layer, group) for group in _position_groups(positions)
            )

    def best_placement(component):
        candidates = placements.get(component, ())
        scored = []
        for layer, cells in candidates:
            effects = [
                (x, y, sheet, tile_id)
                for x, y, sheet, tile_id in water_effects
                if min(max(abs(x - cell_x), abs(y - cell_y)) for cell_x, cell_y in cells) <= 2
            ]
            scored.append((len(effects), layer, cells, effects))
        if not scored:
            return None
        score, layer, cells, effects = max(
            scored,
            key=lambda entry: (entry[0], -min(y for _x, y in entry[2]), entry[1]),
        )
        return (layer, cells, effects) if score else None

    object_groups = []
    consumed_component_ids = set()
    catalog_entries = []
    selected_groups = []
    for slug, title, components in WATER_OBJECTS:
        selected = []
        for component, filename, display_name in components:
            placement = best_placement(component)
            if placement is None:
                continue
            layer, cells, effects = placement
            selected.append((component, filename, display_name, layer, cells, effects))
        if not selected or (slug == "nessy" and len(selected) != len(components)):
            continue
        selected_groups.append((slug, title, selected))
    cells_by_group = {
        slug: {
            cell
            for _component, _filename, _name, _layer, placement, _effects in selected
            for cell in placement
        }
        for slug, _title, selected in selected_groups
    }
    effect_owners = defaultdict(set)
    for x, y, sheet, tile_id in water_effects:
        distances = []
        for slug, cells in cells_by_group.items():
            distance = min(
                (max(abs(x - cell_x), abs(y - cell_y)) for cell_x, cell_y in cells),
                default=float("inf"),
            )
            distances.append((distance, slug))
        if distances:
            distance, owner = min(distances)
            if distance <= 2:
                effect_owners[owner].add((x, y, sheet, tile_id))

    for slug, title, selected in selected_groups:
        all_effects = effect_owners[slug]
        object_positions = []
        for _component, _filename, _name, _layer, cells, _effects in selected:
            min_x = min(x for x, _y in cells)
            min_y = min(y for _x, y in cells)
            component = _component
            bounds = sprite_bounds[component]
            width_tiles = bounds.width / TILE_SIZE
            height_tiles = bounds.height / TILE_SIZE
            sprite_left = min_x + (bounds.left % TILE_SIZE) / TILE_SIZE
            sprite_top = min_y + (bounds.top % TILE_SIZE) / TILE_SIZE
            anchor_x = round(sprite_left + width_tiles / 2 - 0.5)
            anchor_y = round(sprite_top + height_tiles - 1)
            offset_x = sprite_left - (anchor_x + 0.5 - width_tiles / 2)
            offset_y = sprite_top - (anchor_y + 1 - height_tiles)
            object_positions.append((
                anchor_x,
                anchor_y,
                offset_x,
                offset_y,
                sprite_left,
                sprite_top,
                width_tiles,
                height_tiles,
            ))

        raw_cells = []
        for x, y, sheet, tile_id in sorted(all_effects, key=lambda cell: (cell[1], cell[0], cell[2], cell[3])):
            sheet_key = sheet.lower()
            raw_cells.append({
                "key": f"rocky_{sheet_key}_{tile_id:04d}",
                "x": x,
                "y": y,
                "layer": "overlay",
            })
        object_keys = []
        for index, (_component, filename, display_name, _layer, _cells, _effects) in enumerate(selected):
            key = f"rocky_water_object_{slug}_{index + 1}"
            object_keys.append(key)

        (output_dir / "water_objects").mkdir(parents=True, exist_ok=True)
        for index, (_component, filename, display_name, _layer, _cells, _effects) in enumerate(selected):
            source_path = separate_dir / filename
            if not source_path.is_file():
                raise FileNotFoundError(f"Missing Rocky standalone sprite: {source_path}")
            key = object_keys[index]
            relative_asset = f"rocky/water_objects/{key.rsplit('_', 1)[-1]}_{slug}.png"
            image = sprites[_component - 1][3].copy()
            if filename == "Nessy_tail.png":
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            image.resize(
                (image.width * SCALE, image.height * SCALE),
                Image.Resampling.NEAREST,
            ).save(output_dir / "water_objects" / Path(relative_asset).name)
            catalog_entries.append({
                "key": key,
                "kind": "object",
                "category": "bush",
                "asset": relative_asset,
                "sheet": "Objects_separately",
                "representation": "sprite",
                "display_name": display_name,
                "layer": "objects",
                "title": "Скалистый биом · Объекты в воде",
                "palette_hidden": False,
                "render_offset_tiles": {
                    "x": object_positions[index][2],
                    "y": object_positions[index][3],
                },
            })
        consumed_component_ids.update(component for component, *_rest in selected)

        object_bounds = []
        normalized_objects = []
        for index, _entry in enumerate(selected):
            anchor_x, anchor_y, _offset_x, _offset_y, left, top, width_tiles, height_tiles = object_positions[index]
            object_bounds.append((left, top, left + width_tiles, top + height_tiles))
            normalized_objects.append({
                "key": object_keys[index],
                "x": anchor_x,
                "y": anchor_y,
            })

        if not object_bounds:
            continue
        min_x = min([cell["x"] for cell in raw_cells] + [math.floor(bound[0]) for bound in object_bounds])
        min_y = min([cell["y"] for cell in raw_cells] + [math.floor(bound[1]) for bound in object_bounds])
        max_x = max([cell["x"] + 1 for cell in raw_cells] + [math.ceil(bound[2]) for bound in object_bounds])
        max_y = max([cell["y"] + 1 for cell in raw_cells] + [math.ceil(bound[3]) for bound in object_bounds])
        group_cells = [
            {key: value for key, value in cell.items() if key != "display_name"}
            for cell in raw_cells
        ]
        group_cells.extend(
            {
                "key": item["key"],
                "x": item["x"],
                "y": item["y"],
                "layer": "objects",
            }
            for item in normalized_objects
        )
        object_groups.append({
            "key": f"rocky_water_object_{slug}",
            "primary_key": object_keys[0],
            "title": title,
            "width": max_x - min_x,
            "height": max_y - min_y,
            "cells": [
                {**cell, "x": cell["x"] - min_x, "y": cell["y"] - min_y}
                for cell in group_cells
            ],
        })
    return object_groups, consumed_component_ids, catalog_entries


def _import_growth_objects(source_root, output_dir):
    """Import the author's explicitly numbered Rocky growth stages."""
    catalog = []
    sources = _growth_sources(source_root)
    if not sources:
        return catalog
    growth_dir = output_dir / "growth"
    growth_dir.mkdir(parents=True, exist_ok=True)
    for group, stage, source_path in sources:
        key = f"bush_{group}_{stage}"
        asset = f"rocky/growth/{key}.png"
        image = Image.open(source_path).convert("RGBA")
        visible_bounds = image.getchannel("A").getbbox()
        if visible_bounds is None:
            raise ValueError(f"Growth sprite has no visible pixels: {source_path}")
        growth_size = (
            (visible_bounds[2] - visible_bounds[0])
            * (visible_bounds[3] - visible_bounds[1])
            * SCALE
            * SCALE
        )
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_dir / "growth" / f"{key}.png")
        parts = group.removeprefix("rocky_").replace("_", " ").split()
        family = parts[0]
        if family == "conifer":
            variant = " ".join(parts[1:])
            if variant.startswith("tree small"):
                label = f"Небольшое хвойное дерево №{variant.removeprefix('tree small')}"
            else:
                label = f"Хвойное дерево №{variant.removeprefix('tree')}"
            variant = ""
        elif family in {"rock1", "rock2", "rock3"}:
            label = f"Камни Rocky {family[-1]}"
            variant = " ".join(parts[1:])
        elif family == "big":
            label = "Большие грибы"
            variant = " ".join(parts[2:])
        else:
            label = "Сине-зелёные грибы"
            variant = " ".join(parts[3:])
        surface_names = {"grass": "на траве", "ground": "на земле", "wall": "на стене"}
        label = " ".join(part for part in (label, surface_names.get(variant, variant)) if part)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "bush",
            "asset": asset,
            "sheet": "Objects_separately",
            "representation": "sprite",
            "display_name": f"{label} · стадия {stage}",
            "layer": "objects",
            "title": "Скалистый биом · Растущие объекты",
            "growth_series": group,
            "growth_stage": stage,
            "growth_size": growth_size,
            "palette_hidden": False,
        })
    return catalog


def _tiled_layer_role(sheet, layer_name):
    """Map the author's Tiled layer names onto the map editor's supported storage layers."""
    layer = layer_name.casefold()
    if sheet == "Objects":
        return "objects"
    if "elevated_space" in layer:
        return "elevation"
    if "bridge" in layer:
        return "infra"
    if sheet == "details":
        return "overlay"
    if layer == "water":
        return "ground"
    if layer.startswith(("water_details", "small_river_elements", "river_elements")):
        return "overlay"
    if "ground" in layer or "moss" in layer:
        return "ground"
    if layer.startswith("objects"):
        return "ground"
    return None


def _preferred_layer(sheet, usage, fallback):
    role_counts = Counter()
    for layer_name, count in usage.items():
        role = _tiled_layer_role(sheet, layer_name)
        if role and role != "objects":
            role_counts[role] += count
    if not role_counts:
        return fallback
    priority = {"ground": 3, "overlay": 2, "elevation": 1, "infra": 0}
    return max(role_counts, key=lambda role: (role_counts[role], priority[role]))


def _tile_crop(sheet, tile_id, columns):
    x = tile_id % columns * TILE_SIZE
    y = tile_id // columns * TILE_SIZE
    frame = sheet.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
    if frame.size != (TILE_SIZE, TILE_SIZE):
        raise ValueError(f"Tile {tile_id} is outside the source sheet")
    return frame.resize((TILE_SIZE * SCALE, TILE_SIZE * SCALE), Image.Resampling.NEAREST)


def _tile_fingerprint(sheet, tile_id, columns):
    x = tile_id % columns * TILE_SIZE
    y = tile_id // columns * TILE_SIZE
    pixels = bytearray(
        sheet.crop(
            (x, y, x + TILE_SIZE, y + TILE_SIZE)
        ).convert("RGBA").tobytes()
    )
    for offset in range(0, len(pixels), 4):
        if pixels[offset + 3] == 0:
            pixels[offset:offset + 3] = b"\0\0\0"
    return bytes(pixels)


def _artist_sheet_layout(tiled_image, artist_image, items):
    if artist_image.width % TILE_SIZE or artist_image.height % TILE_SIZE:
        raise ValueError("Ground_moss artist sheet dimensions must align to 16px tiles")
    columns = artist_image.width // TILE_SIZE
    rows = artist_image.height // TILE_SIZE
    items_by_fingerprint = defaultdict(list)
    for item in items:
        items_by_fingerprint[
            _tile_fingerprint(tiled_image, item["tile_id"], item["columns"])
        ].append(item)

    positions_by_fingerprint = defaultdict(list)
    for row in range(rows):
        for column in range(columns):
            fingerprint = _tile_fingerprint(
                artist_image,
                row * columns + column,
                columns,
            )
            if fingerprint in items_by_fingerprint:
                positions_by_fingerprint[fingerprint].append((column, row))

    positions_by_key = defaultdict(list)
    layer_order = {"ground": 0, "elevation": 1, "infra": 2, "overlay": 3}
    for fingerprint, positions in positions_by_fingerprint.items():
        matching_items = sorted(
            items_by_fingerprint[fingerprint],
            key=lambda item: (
                layer_order.get(item["layer"], 4),
                item["tile_id"],
            ),
        )
        for index, position in enumerate(positions):
            item = (
                matching_items[index]
                if index < len(matching_items)
                else matching_items[0]
            )
            positions_by_key[item["key"]].append(list(position))

    return positions_by_key, [columns, rows]


def _object_sprites(sheet, used_ids):
    """Return substantial, used connected sprites from the Objects sheet in stable visual order."""
    surface = pygame.image.fromstring(sheet.tobytes(), sheet.size, "RGBA")
    components = pygame.mask.from_surface(surface, 1).connected_components()
    sprites = []
    columns = sheet.width // TILE_SIZE
    tile_mask = pygame.mask.Mask((TILE_SIZE, TILE_SIZE), fill=True)
    for component in components:
        if component.count() < 100:
            continue
        bounds = component.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(0, 0, 0, 0),
        ).get_bounding_rect()
        tile_ids = set()
        for row in range(bounds.top // TILE_SIZE, (bounds.bottom - 1) // TILE_SIZE + 1):
            for column in range(bounds.left // TILE_SIZE, (bounds.right - 1) // TILE_SIZE + 1):
                if component.overlap(tile_mask, (column * TILE_SIZE, row * TILE_SIZE)) is not None:
                    tile_ids.add(row * columns + column)
        if not tile_ids.intersection(used_ids):
            continue
        mask_surface = component.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(255, 255, 255, 0),
        )
        mask = Image.frombytes("RGBA", mask_surface.get_size(), pygame.image.tostring(mask_surface, "RGBA"))
        sprite = sheet.crop((bounds.left, bounds.top, bounds.right, bounds.bottom))
        mask = mask.crop((bounds.left, bounds.top, bounds.right, bounds.bottom))
        sprite.putalpha(ImageChops.multiply(sprite.getchannel("A"), mask.getchannel("A")))
        sprite = Image.alpha_composite(Image.new("RGBA", sprite.size), sprite)
        sprites.append((bounds, component.count(), tile_ids, sprite))
    return sorted(sprites, key=lambda sprite: (sprite[0].top, sprite[0].left))


def _animated_groups(sheet, animations, used_ids, columns):
    """Group adjacent animated water tiles into indivisible palette stamps."""
    cells = {
        (tile_id // columns, tile_id % columns): tile_id
        for tile_id, frames in animations.items()
        if any(
            _tile_crop(sheet, frame["tile_id"], columns).getbbox() is not None
            for frame in frames
        )
    }
    seen = set()
    groups = []
    for start in sorted(cells):
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], []
        while stack:
            row, column = stack.pop()
            group.append(cells[row, column])
            for neighbour in (
                (row + 1, column), (row - 1, column),
                (row, column + 1), (row, column - 1),
            ):
                if neighbour in cells and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        if len(group) < 2 or not used_ids.intersection(group):
            continue
        top = min(tile_id // columns for tile_id in group)
        left = min(tile_id % columns for tile_id in group)
        groups.append({
            "cells": [
                {
                    "key": f"rocky_water_detilazation2_{tile_id:04d}",
                    "x": tile_id % columns - left,
                    "y": tile_id // columns - top,
                }
                for tile_id in sorted(group)
            ],
        })
    return groups


def import_biome(source_root, output_dir=None):
    source_root = Path(source_root).resolve()
    map_path = source_root / "Tiled_files" / "Rocky_area.tmx"
    if not map_path.is_file():
        raise FileNotFoundError(f"Rocky_area.tmx was not found at {map_path}")
    output_dir = Path(output_dir or MAP_ASSETS / "rocky").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    map_root, tilesets = _read_tilesets(map_path)
    used_ids, layer_usage = _used_tile_ids(map_root, tilesets)
    separate_dir = source_root / "PNG" / "Objects_separately"
    object_sheet_info = next(
        (tileset for tileset in tilesets if tileset["name"] == "Objects"),
        None,
    )
    object_sprites = []
    if object_sheet_info is not None:
        object_image = Image.open(object_sheet_info["path"]).convert("RGBA")
        object_sprites = _object_sprites(
            object_image,
            used_ids.get("Objects", set()),
        )
    detail_sheet_info = next(
        (tileset for tileset in tilesets if tileset["name"] == "details"),
        None,
    )
    detail_sprites = []
    if detail_sheet_info is not None:
        detail_image = Image.open(detail_sheet_info["path"]).convert("RGBA")
        detail_sprites = _object_sprites(
            detail_image,
            used_ids.get("details", set()),
        )
    water_object_groups, water_component_ids, water_object_catalog = _water_object_groups(
        map_root,
        tilesets,
        object_sprites,
        output_dir,
        separate_dir,
    )
    growth_catalog = _import_growth_objects(source_root, output_dir)
    growth_sprite_signatures = {
        signature
        for item in growth_catalog
        if (
            signature := _visible_sprite_mask_signature(
                Image.open(output_dir / "growth" / Path(item["asset"]).name)
            )
        ) is not None
    }
    water_group_tile_ids = defaultdict(set)
    for group in water_object_groups:
        for cell in group["cells"]:
            for sheet_name in ("Water_under_objects", "Water_detilazation2"):
                prefix = f"rocky_{sheet_name.lower()}_"
                if cell["key"].startswith(prefix):
                    water_group_tile_ids[sheet_name].add(int(cell["key"][len(prefix):]))
                    break
    sheets_by_name = {}
    for tileset in tilesets:
        settings = SHEET_SETTINGS.get(tileset["name"])
        if settings is None:
            continue
        entry = sheets_by_name.setdefault(tileset["name"], {
            **settings,
            "columns": tileset["columns"],
            "tile_count": tileset["tile_count"],
            "used_ids": set(),
            "layer_usage": defaultdict(Counter),
            "animations": {},
            "image_path": tileset["path"],
        })
        if entry["image_path"] != tileset["path"] or entry["columns"] != tileset["columns"]:
            raise ValueError(f"Inconsistent duplicate tileset definition for {tileset['name']}")
        entry["used_ids"].update(used_ids[tileset["name"]])
        for tile_id, counts in layer_usage[tileset["name"]].items():
            entry["layer_usage"][tile_id].update(counts)
        entry["animations"].update(tileset["animations"])

    catalog = []
    animations = {}
    animated_groups = []
    detail_catalog = []
    for name, sheet_info in sheets_by_name.items():
        source_image = Image.open(sheet_info["image_path"]).convert("RGBA")
        groups = (
            _animated_groups(
                source_image,
                sheet_info["animations"],
                sheet_info["used_ids"],
                sheet_info["columns"],
            )
            if name == "Water_detilazation2"
            else []
        )
        grouped_tile_ids = {
            int(cell["key"].rsplit("_", 1)[1])
            for group in groups
            for cell in group["cells"]
        }
        animated_groups.extend(groups)
        animation_frame_ids = {
            frame["tile_id"]
            for frames in sheet_info["animations"].values()
            for frame in frames
        }
        animation_signatures = set()
        static_signatures = set()
        expected_size = (sheet_info["columns"] * TILE_SIZE, ((sheet_info["tile_count"] + sheet_info["columns"] - 1) // sheet_info["columns"]) * TILE_SIZE)
        if source_image.size[0] < expected_size[0] or source_image.size[1] < expected_size[1]:
            raise ValueError(f"{name} sheet is smaller than its declared Tiled dimensions")
        sheet_asset = f"rocky/{name}.png"
        sheet_path = output_dir / f"{name}.png"
        source_image.resize(
            (source_image.width * SCALE, source_image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(sheet_path)

        if name == "Objects":
            seen_sprites = set()
            for index, (bounds, _area, tile_ids, sprite) in enumerate(
                object_sprites,
                start=1,
            ):
                key = f"rocky_objects_{index:03d}"
                relative_asset = f"rocky/objects/object_{index:03d}.png"
                object_dir = output_dir / "objects"
                object_dir.mkdir(parents=True, exist_ok=True)
                if index == 19:
                    sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                scaled_sprite = sprite.resize(
                    (bounds.width * SCALE, bounds.height * SCALE),
                    Image.Resampling.NEAREST,
                )
                scaled_sprite.save(output_dir / "objects" / f"object_{index:03d}.png")
                sprite_signature = (sprite.size, sprite.tobytes())
                duplicate_sprite = sprite_signature in seen_sprites
                seen_sprites.add(sprite_signature)
                duplicate_growth_sprite = (
                    _visible_sprite_mask_signature(scaled_sprite) in growth_sprite_signatures
                )
                source_layers = list(dict.fromkeys(
                    layer_name
                    for tile_id in sorted(tile_ids & sheet_info["used_ids"])
                    for layer_name in sheet_info["layer_usage"].get(tile_id, {})
                ))
                source_layer_counts = Counter()
                for tile_id in tile_ids & sheet_info["used_ids"]:
                    source_layer_counts.update(sheet_info["layer_usage"].get(tile_id, {}))
                under_elevation_count = sum(
                    count for layer_name, count in source_layer_counts.items()
                    if layer_name.startswith("Objects_under_elevated_space")
                )
                foreground_count = sum(
                    count for layer_name, count in source_layer_counts.items()
                    if layer_name.startswith("Objects")
                    and not layer_name.startswith("Objects_under_elevated_space")
                )
                catalog.append({
                    "key": key,
                    "kind": sheet_info["kind"],
                    "category": sheet_info["category"],
                    "asset": relative_asset,
                    "sheet": name,
                    "representation": "sprite",
                    "display_name": f"Объект Rocky {index:03d}",
                    "layer": sheet_info["layer"],
                    "title": sheet_info["title"],
                    "tiled_layers": source_layers,
                    "render_order": (
                        "under_elevation"
                        if under_elevation_count > foreground_count
                        else "foreground"
                    ),
                    "palette_hidden": (
                        duplicate_sprite
                        or duplicate_growth_sprite
                        or index in water_component_ids
                    ),
                })
            continue

        if name == "details":
            detail_dir = output_dir / "details_objects"
            detail_dir.mkdir(parents=True, exist_ok=True)
            seen_detail_sprites = set()
            for index, (bounds, _area, tile_ids, sprite) in enumerate(
                detail_sprites,
                start=1,
            ):
                key = f"rocky_details_object_{index:03d}"
                relative_asset = f"rocky/details_objects/detail_object_{index:03d}.png"
                scaled_sprite = sprite.resize(
                    (bounds.width * SCALE, bounds.height * SCALE),
                    Image.Resampling.NEAREST,
                )
                scaled_sprite.save(detail_dir / f"detail_object_{index:03d}.png")
                source_tile_ids = sorted(tile_ids)
                signature = (scaled_sprite.size, scaled_sprite.tobytes())
                duplicate_sprite = signature in seen_detail_sprites
                seen_detail_sprites.add(signature)
                detail_catalog.append({
                    "key": key,
                    "kind": "object",
                    "category": "bush",
                    "asset": relative_asset,
                    "sheet": "details",
                    "representation": "sprite",
                    "display_name": f"Цельный объект Rocky {index:03d}",
                    "layer": "objects",
                    "title": "Скалистый биом · Цельные детали и растения",
                    "source_tile_ids": source_tile_ids,
                    "growth_size": bounds.width * bounds.height * SCALE * SCALE,
                    "palette_hidden": duplicate_sprite,
                })

        included_ids = (
            set(sheet_info["used_ids"])
            | grouped_tile_ids
            | water_group_tile_ids.get(name, set())
        )
        for tile_id in sorted(included_ids):
            animation_frames = sheet_info["animations"].get(tile_id)
            source_ids = [frame["tile_id"] for frame in animation_frames] if animation_frames else [tile_id]
            representative = _tile_crop(source_image, source_ids[0], sheet_info["columns"])
            if animation_frames:
                has_visible_frame = any(
                    _tile_crop(source_image, frame_id, sheet_info["columns"]).getbbox() is not None
                    for frame_id in source_ids
                )
                if not has_visible_frame:
                    continue
            elif representative.getbbox() is None:
                continue
            animation_durations = [frame["duration"] for frame in animation_frames] if animation_frames else []
            signature = (
                tuple(_tile_crop(source_image, frame_id, sheet_info["columns"]).tobytes() for frame_id in source_ids),
                tuple(animation_durations),
            )
            tile_layer = _preferred_layer(
                name,
                sheet_info["layer_usage"].get(tile_id, {}),
                sheet_info["layer"],
            )
            if animation_frames:
                duplicate_animation = signature in animation_signatures
                animation_signatures.add(signature)
            else:
                signature_key = (tile_layer, signature)
                duplicate_animation = signature_key in static_signatures
                static_signatures.add(signature_key)
            key = f"rocky_{name.lower()}_{tile_id:04d}"
            catalog.append({
                "key": key,
                "kind": sheet_info["kind"],
                "category": sheet_info["category"],
                "asset": sheet_asset,
                "sheet": name,
                "tile_id": tile_id,
                "columns": sheet_info["columns"],
                "title": sheet_info["title"],
                "used_in_example": tile_id in sheet_info["used_ids"],
                "tiled_layers": list(sheet_info["layer_usage"].get(tile_id, {})),
                "layer_roles": sorted({
                    role
                    for layer_name in sheet_info["layer_usage"].get(tile_id, {})
                    if (role := _tiled_layer_role(name, layer_name)) is not None
                }),
                "layer": tile_layer,
                "display_name": f"Тайл {tile_id + 1:04d}",
                "frame_tile_ids": source_ids,
                "durations": animation_durations,
                **(
                    {"flip_x": True}
                    if name == "Water_detilazation2" and tile_id == 378
                    else {}
                ),
                "palette_hidden": (
                    tile_id in grouped_tile_ids
                    or duplicate_animation
                    or name == "details"
                    or (not animation_frames and tile_id in animation_frame_ids)
                ),
            })
            if animation_frames:
                animations[key] = {
                    "frame": [TILE_SIZE * SCALE, TILE_SIZE * SCALE],
                    "frames": len(animation_frames),
                    "cols": len(animation_frames),
                    "durations": [frame["duration"] for frame in animation_frames],
                    "tile_ids": source_ids,
                }

    ground_moss_info = sheets_by_name.get("Ground_moss")
    if ground_moss_info is not None:
        artist_sheet_path = next(
            (
                path
                for path in (source_root / "PNG").glob("*.png")
                if path.stem.casefold() == "ground_moss"
            ),
            None,
        )
        if artist_sheet_path is None:
            raise FileNotFoundError(
                f"PNG/Ground_moss.png was not found in {source_root}"
            )
        ground_moss_items = [
            item
            for item in catalog
            if item.get("sheet") == "Ground_moss"
            and not item.get("palette_hidden", False)
        ]
        artist_positions, artist_size = _artist_sheet_layout(
            Image.open(ground_moss_info["image_path"]).convert("RGBA"),
            Image.open(artist_sheet_path).convert("RGBA"),
            ground_moss_items,
        )
        for item in ground_moss_items:
            item["artist_sheet_positions"] = artist_positions.get(item["key"], [])
            item["artist_sheet_size"] = artist_size

    catalog.extend(detail_catalog)
    catalog.extend(water_object_catalog)
    catalog.extend(growth_catalog)
    catalog_path = output_dir / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "items": catalog,
                "animated_groups": animated_groups,
                "water_object_groups": water_object_groups,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    animations_path = output_dir / "animations.json"
    animations_path.write_text(
        json.dumps(animations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    license_path = source_root / "License.txt"
    if license_path.is_file():
        shutil.copyfile(license_path, output_dir / "License.txt")
    return len(catalog), len(animations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing the Rocky tileset")
    parser.add_argument("--output", type=Path, help="output directory (defaults to assets/map/rocky)")
    args = parser.parse_args()
    item_count, animation_count = import_biome(args.source, args.output)
    print(f"Imported {item_count} tiles and {animation_count} Tiled animations.")


if __name__ == "__main__":
    main()
