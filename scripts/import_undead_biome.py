"""Import the Undead biome's Tiled sheets, intact sprites, and complete animated compositions."""
import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from scripts.import_rocky_biome import SCALE, TILE_SIZE, _object_sprites, _tile_crop
from scripts.import_winter_biome import _tilesets, _used_tiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_ASSETS = PROJECT_ROOT / "assets" / "map"
WATER_SHEETS = frozenset({
    "water_detilazation",
    "water_detilazation2",
    "water_coasts",
})
SHEET_SETTINGS = {
    "ground_rocks": ("ground", "floor", "Биом нежити · Земля и скалы"),
    "water_detilazation": ("ground", "floor", "Биом нежити · Водная анимация"),
    "water_detilazation2": ("ground", "floor", "Биом нежити · Водная анимация 2"),
    "water_coasts": ("ground", "water", "Биом нежити · Берега и вода"),
    "objects": ("object", "bush", "Биом нежити · Объекты"),
    "objects_animated": ("object", "bush", "Биом нежити · Анимированные объекты"),
    "objects_animated2": ("object", "bush", "Биом нежити · Анимированные объекты 2"),
    "objects_animated3": ("object", "bush", "Биом нежити · Анимированные объекты 3"),
    "details": ("object", "bush", "Биом нежити · Детали"),
}
LAYER_ROLES = {
    "ground": "ground",
    "water": "ground",
    "water_detailization": "overlay",
    "darker_surface1": "overlay",
    "darker_surface2": "overlay",
    "bridge": "infra",
}
ARTIST_LAYERS = {
    "ground": 3,
    "overlay": 4,
    "elevation": 5,
    "infra": 6,
    "objects": 7,
}
ANIMATION_SPRITES = {
    "Animation1": (96, 128),
    "Animation2": (80, 96),
    "Animation3": (64, 64),
    "Animation4": (80, 112),
    "Animation5": (96, 112),
    "Animation6": (48, 80),
}
ANIMATION_SPRITE_MS = 120
MOUNTAIN_STONE_PIXEL_THRESHOLD = 8
MOUNTAIN_TYPE_NAMES = {
    "dark": "Биом нежити · Горы — тёмные скалы",
    "stone": "Биом нежити · Горы — скалы с каменной вершиной",
}
OBJECT_TYPE_NAMES = {
    "bones": "Кости",
    "broken_tree": "Сломанные деревья",
    "crystal": "Кристаллы",
    "dead_arm": "Рука нежити",
    "dead_tree": "Мёртвые деревья",
    "grave": "Могилы",
    "lich": "Личи",
    "pile_skulls": "Черепа",
    "plant": "Растения",
    "rock": "Камни",
    "ruin": "Руины",
    "skull_door": "Двери с черепами",
    "thorn_plant": "Колючие растения",
    "tree": "Деревья",
}
OBJECT_TYPE_ORDER = (
    "tree",
    "dead_tree",
    "broken_tree",
    "ruin",
    "grave",
    "skull_door",
    "bones",
    "pile_skulls",
    "dead_arm",
    "lich",
    "rock",
    "crystal",
    "thorn_plant",
    "plant",
)
OBJECT_TYPE_ORDER_INDEX = {
    object_type: index for index, object_type in enumerate(OBJECT_TYPE_ORDER)
}


def _object_type(source_name):
    family = Path(source_name).stem.casefold().split("_shadow", 1)[0]
    family = re.sub(r"[^a-z]+", "_", family).strip("_")
    family = {
        "thorn_palnt": "thorn_plant",
        "pile_sculls": "pile_skulls",
        "scull_door": "skull_door",
    }.get(family, family)
    if family not in OBJECT_TYPE_NAMES:
        raise ValueError(f"Unknown undead object type in source filename: {source_name}")
    return family


def _mountain_type(image, tile_ids, columns):
    """Classify a Ground_rocks tile by its visible stone-colored pixels."""
    for tile_id in tile_ids:
        x, y = tile_id % columns * TILE_SIZE, tile_id // columns * TILE_SIZE
        tile = image.crop((x, y, x + TILE_SIZE, y + TILE_SIZE)).convert("RGBA")
        stone_pixels = sum(
            1
            for red, green, blue, alpha in tile.get_flattened_data()
            if alpha
            and red > 100
            and green > 100
            and blue > 75
            and red >= green >= blue
            and red - blue > 15
        )
        if stone_pixels >= MOUNTAIN_STONE_PIXEL_THRESHOLD:
            return "stone"
    return "dark"


def _tile_fingerprint(image, tile_id, columns):
    x = tile_id % columns * TILE_SIZE
    y = tile_id // columns * TILE_SIZE
    pixels = bytearray(image.crop(
        (x, y, x + TILE_SIZE, y + TILE_SIZE)
    ).convert("RGBA").tobytes())
    for offset in range(0, len(pixels), 4):
        if pixels[offset + 3] == 0:
            pixels[offset:offset + 3] = b"\0\0\0"
    return bytes(pixels)


def _artist_tile_locations(image):
    if image.width % TILE_SIZE or image.height % TILE_SIZE:
        raise ValueError("Ground_rocks artist sheet dimensions must align to 16px tiles")
    columns = image.width // TILE_SIZE
    locations = defaultdict(list)
    for row in range(image.height // TILE_SIZE):
        for column in range(columns):
            tile_id = row * columns + column
            locations[_tile_fingerprint(image, tile_id, columns)].append(
                (row, column)
            )
    return locations, columns, image.height // TILE_SIZE


def _tightest_artist_bounds(tile_candidates, columns, rows, group_key):
    best = None
    for top in range(rows):
        active_columns = {tile_id: set() for tile_id in tile_candidates}
        for bottom in range(top, rows):
            for tile_id, candidates in tile_candidates.items():
                active_columns[tile_id].update(
                    column for row, column in candidates if row == bottom
                )
            counts = Counter()
            covered = 0
            left = 0
            for right in range(columns):
                for tile_id, candidates in active_columns.items():
                    if right in candidates:
                        if counts[tile_id] == 0:
                            covered += 1
                        counts[tile_id] += 1
                while covered == len(tile_candidates) and left <= right:
                    height = bottom - top + 1
                    width = right - left + 1
                    score = (
                        height * width,
                        max(height, width),
                        height,
                        width,
                        top,
                        left,
                    )
                    if best is None or score < best[0]:
                        best = (score, (top, left, bottom, right))
                    for tile_id, candidates in active_columns.items():
                        if left in candidates:
                            counts[tile_id] -= 1
                            if counts[tile_id] == 0:
                                covered -= 1
                    left += 1
    if best is None:
        raise ValueError(
            f"Could not map every tile in mountain group {group_key} "
            "to the artist Ground_rocks sheet"
        )
    return best[1]


def _artist_group_positions(
    group_items,
    tiled_image,
    locations,
    columns,
    rows,
    group_key,
):
    tile_candidates = {
        item["tile_id"]: locations.get(
            _tile_fingerprint(tiled_image, item["tile_id"], item["columns"]),
            (),
        )
        for item in group_items
    }
    if any(not candidates for candidates in tile_candidates.values()):
        raise ValueError(
            f"A tile in mountain group {group_key} does not match "
            "the artist Ground_rocks sheet"
        )
    top, left, bottom, right = _tightest_artist_bounds(
        tile_candidates,
        columns,
        rows,
        group_key,
    )
    choices = {
        tile_id: sorted(
            (
                (row, column)
                for row, column in candidates
                if top <= row <= bottom and left <= column <= right
            ),
            key=lambda position: (
                abs(position[0] - (top + bottom) / 2)
                + abs(position[1] - (left + right) / 2),
                position,
            ),
        )
        for tile_id, candidates in tile_candidates.items()
    }
    owners = {}

    def assign(tile_id, visited):
        for position in choices[tile_id]:
            if position in visited:
                continue
            visited.add(position)
            previous = owners.get(position)
            if previous is None or assign(previous, visited):
                owners[position] = tile_id
                return True
        return False

    for tile_id in sorted(
        tile_candidates,
        key=lambda value: (len(choices[value]), value),
    ):
        if not assign(tile_id, set()):
            raise ValueError(
                f"Could not assign unique artist-sheet cells for mountain group {group_key}"
            )
    return {tile_id: position for position, tile_id in owners.items()}


def _artist_connected_groups(group_items, positions):
    items_by_position = {
        positions[item["tile_id"]]: item
        for item in group_items
    }
    groups = []
    seen = set()
    for start in sorted(items_by_position):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        group = []
        while stack:
            position = stack.pop()
            group.append(items_by_position[position])
            row, column = position
            for neighbour in (
                (row + 1, column),
                (row - 1, column),
                (row, column + 1),
                (row, column - 1),
            ):
                if neighbour in items_by_position and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        groups.append((group, {item["tile_id"]: positions[item["tile_id"]] for item in group}))
    return groups


def _artist_layout_cells(
    tiled_image,
    artist_image,
    group_items,
    columns,
    rows,
):
    items_by_fingerprint = {}
    for item in group_items:
        fingerprint = _tile_fingerprint(
            tiled_image,
            item["tile_id"],
            item["columns"],
        )
        items_by_fingerprint[fingerprint] = min(
            item["tile_id"],
            items_by_fingerprint.get(fingerprint, item["tile_id"]),
        )

    positions_by_tile = defaultdict(list)
    layout_rows = rows
    has_layout_content = False
    for row in range(rows):
        row_has_content = False
        for column in range(columns):
            tile_id = items_by_fingerprint.get(
                _tile_fingerprint(
                    artist_image,
                    row * columns + column,
                    columns,
                )
            )
            if tile_id is not None:
                positions_by_tile[tile_id].append((row, column))
                row_has_content = True
        if row_has_content:
            has_layout_content = True
        elif has_layout_content:
            layout_rows = row
            break
    return positions_by_tile, layout_rows


def _key(sheet, tile_id):
    normalized = re.sub(r"[^a-z0-9]+", "_", sheet.casefold()).strip("_")
    return f"undead_{normalized}_{tile_id:04d}"


def _layer_role(layer_name):
    layer = layer_name.casefold()
    if "elevated_space" in layer or layer.startswith(("bricks", "stairs")):
        return "elevation"
    if layer.startswith("objects"):
        return "objects"
    if layer == "bridge":
        return "infra"
    if layer in LAYER_ROLES:
        return LAYER_ROLES[layer]
    if layer.startswith("details"):
        return "overlay"
    return None


def _artist_layer(sheet_name, layer_usage, fallback_role):
    if sheet_name.casefold() in WATER_SHEETS:
        if sheet_name.casefold() in {"water_detilazation", "water_detilazation2"}:
            return 2
        role_to_artist = {
            "ground": 1,
            "overlay": 2,
            "elevation": 5,
            "infra": 6,
        }
    elif sheet_name.casefold().startswith("objects"):
        return 7
    elif sheet_name.casefold() == "details":
        return 4
    else:
        role_to_artist = ARTIST_LAYERS

    counts = Counter()
    for layer_name, count in layer_usage.items():
        role = _layer_role(layer_name)
        if role in role_to_artist:
            counts[role] += count
    if not counts:
        return role_to_artist.get(fallback_role, 3)
    return role_to_artist[max(counts, key=lambda role: (counts[role], role))]


def _preferred_role(sheet_name, layer_usage):
    normalized = sheet_name.casefold()
    if normalized in {"water_detilazation", "water_detilazation2"}:
        return "overlay"
    if normalized.startswith("objects"):
        return "objects"
    counts = Counter()
    for layer_name, count in layer_usage.items():
        role = _layer_role(layer_name)
        if role:
            counts[role] += count
    if not counts:
        return "ground"
    return max(counts, key=lambda role: (counts[role], role))


def _animated_groups(
    sheet_name,
    image,
    columns,
    animations,
    tile_ids,
    tile_roles,
    fallback_role,
    additional_tile_ids=(),
):
    animated_cells = {
        (tile_id // columns, tile_id % columns): tile_id
        for tile_id, frames in animations.items()
        if tile_id in tile_ids
        and any(
            _tile_crop(image, frame["tile_id"], columns).getbbox() is not None
            for frame in frames
        )
    }
    seen = set()
    groups = []
    for start in sorted(animated_cells):
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], []
        while stack:
            row, column = stack.pop()
            group.append(animated_cells[row, column])
            for neighbour in (
                (row + 1, column), (row - 1, column),
                (row, column + 1), (row, column - 1),
            ):
                if neighbour in animated_cells and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        if len(group) < 2:
            continue
        top = min(tile_id // columns for tile_id in group)
        left = min(tile_id % columns for tile_id in group)
        bottom = max(tile_id // columns for tile_id in group)
        right = max(tile_id % columns for tile_id in group)
        grouped_ids = set(group)
        frame_ids = {
            frame["tile_id"]
            for frames in animations.values()
            for frame in frames
        }
        for tile_id in additional_tile_ids:
            row, column = divmod(tile_id, columns)
            if (
                top <= row <= bottom
                and left <= column <= right
                and tile_id not in grouped_ids
                and tile_id not in frame_ids
                and _tile_crop(image, tile_id, columns).getbbox() is not None
            ):
                group.append(tile_id)
                grouped_ids.add(tile_id)
        ordered_ids = sorted(group)
        groups.append({
            "key": f"undead_{sheet_name.casefold()}_animation_{ordered_ids[0]:04d}",
            "sheet": sheet_name,
            "width": right - left + 1,
            "height": bottom - top + 1,
            "cells": [
                {
                    "key": _key(sheet_name, tile_id),
                    "x": tile_id % columns - left,
                    "y": tile_id // columns - top,
                    "layer": tile_roles.get(tile_id, fallback_role),
                }
                for tile_id in ordered_ids
            ],
        })
    return groups


def _standalone_sprites(source_root, output_dir):
    source_dir = source_root / "PNG" / "Objects_separately"
    output_objects = output_dir / "objects"
    output_objects.mkdir(parents=True, exist_ok=True)
    catalog = []
    for source in sorted(source_dir.glob("*.png"), key=lambda path: path.name.casefold()):
        image = Image.open(source).convert("RGBA")
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"Undead sprite has no visible pixels: {source}")
        normalized = re.sub(r"[^a-z0-9]+", "_", source.stem.casefold()).strip("_")
        key = f"undead_sprite_{normalized}"
        object_type = _object_type(source.name)
        asset_name = f"{key}.png"
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_objects / asset_name)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "bush",
            "asset": f"undead/objects/{asset_name}",
            "sheet": "Objects_separately",
            "representation": "sprite",
            "display_name": source.stem.replace("_", " "),
            "layer": "objects",
            "editor_layer": 7,
            "title": "Биом нежити · Цельные объекты",
            "source_name": source.name,
            "source_size": list(image.size),
            "object_type": object_type,
            "object_type_name": OBJECT_TYPE_NAMES[object_type],
            "object_type_order": OBJECT_TYPE_ORDER_INDEX[object_type],
            "palette_hidden": False,
        })
    return catalog


def _animated_sprites(source_root, output_dir):
    source_dir = source_root / "PNG"
    output_dir = output_dir / "animated_objects"
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog, animations = [], {}
    for sheet_name, (frame_width, frame_height) in ANIMATION_SPRITES.items():
        source = source_dir / f"{sheet_name}.png"
        if not source.is_file():
            raise FileNotFoundError(f"Undead animation sheet is missing: {source}")
        with Image.open(source) as source_image:
            image = source_image.convert("RGBA")
        if image.height != frame_height * 3:
            raise ValueError(f"{sheet_name} must contain three rows of {frame_height}px frames")
        horizontal_padding = image.width - frame_width * 6
        if horizontal_padding not in (0, 16):
            raise ValueError(f"{sheet_name} has unexpected frame-sheet width {image.width}")
        x_offset = horizontal_padding // 2
        key = f"undead_{sheet_name.casefold()}"
        asset_name = f"{key}.png"
        frames = Image.new("RGBA", (frame_width * 6, frame_height))
        for frame in range(6):
            source_box = (
                x_offset + frame * frame_width,
                frame_height,
                x_offset + (frame + 1) * frame_width,
                frame_height * 2,
            )
            frame_image = image.crop(source_box)
            if frame_image.getchannel("A").getbbox() is None:
                raise ValueError(f"{sheet_name} contains an empty animation frame {frame + 1}")
            frames.alpha_composite(frame_image, (frame * frame_width, 0))
        frames.resize(
            (frames.width * SCALE, frames.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_dir / asset_name)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "bush",
            "asset": f"undead/animated_objects/{asset_name}",
            "sheet": sheet_name,
            "representation": "sprite",
            "display_name": f"Анимированный спрайт {sheet_name.removeprefix('Animation')}",
            "layer": "objects",
            "editor_layer": 7,
            "title": "Биом нежити · Анимированные цельные объекты",
            "source_name": source.name,
            "source_size": [frame_width, frame_height],
            "palette_hidden": False,
        })
        animations[key] = {
            "frame": [frame_width * SCALE, frame_height * SCALE],
            "frames": 6,
            "cols": 6,
            "durations": [ANIMATION_SPRITE_MS] * 6,
        }
    return catalog, animations


def _hide_duplicate_sprites(catalog, output_dir):
    duplicate_groups = defaultdict(list)
    preferred_sheet_order = {
        "objects_separately": 0,
        "objects": 1,
        "details": 2,
    }
    for item in catalog:
        if item.get("representation") != "sprite":
            continue
        image_path = output_dir / Path(*item["asset"].split("/")[1:])
        with Image.open(image_path) as source:
            image = source.convert("RGBA")
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Undead sprite has no visible pixels: {image_path}")
        cropped = image.crop(bounds)
        signature = (
            cropped.size,
            hashlib.sha256(cropped.tobytes()).digest(),
        )
        duplicate_groups[signature].append(item)

    for duplicates in duplicate_groups.values():
        if len(duplicates) < 2:
            continue
        duplicates.sort(key=lambda item: (
            preferred_sheet_order.get(item.get("sheet", "").casefold(), 3),
            item["key"],
        ))
        for duplicate in duplicates[1:]:
            duplicate["palette_hidden"] = True


def import_biome(source_root, output_dir=None):
    source_root = Path(source_root).resolve()
    if source_root.name.casefold() == "tiled_files":
        source_root = source_root.parent
    map_path = source_root / "Tiled_files" / "Undead_land.tmx"
    if not map_path.is_file():
        raise FileNotFoundError(f"Undead_land.tmx was not found at {map_path}")
    output_dir = Path(output_dir or MAP_ASSETS / "undead").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    map_root, tilesets = _tilesets(source_root, map_path)
    used_ids, layer_usage = _used_tiles(map_root, tilesets)
    sheets = {}
    for tileset in tilesets:
        name = tileset["name"]
        normalized = name.casefold()
        if normalized not in SHEET_SETTINGS:
            continue
        sheet = sheets.setdefault(normalized, {
            "name": name,
            "columns": tileset["columns"],
            "tile_count": tileset["tile_count"],
            "image_path": tileset["path"],
            "used_ids": set(),
            "layer_usage": defaultdict(Counter),
            "animations": {},
        })
        if (
            sheet["columns"] != tileset["columns"]
            or sheet["image_path"] != tileset["path"]
        ):
            raise ValueError(f"Inconsistent duplicate tileset definition for {name}")
        sheet["used_ids"].update(used_ids[name])
        for tile_id, layers in layer_usage[name].items():
            sheet["layer_usage"][tile_id].update(layers)
        sheet["animations"].update(tileset["animations"])

    catalog = []
    animations = {}
    animated_groups = []
    hidden_keys = set()
    for normalized, sheet in sheets.items():
        name = sheet["name"]
        kind, category, title = SHEET_SETTINGS[normalized]
        image = Image.open(sheet["image_path"]).convert("RGBA")
        columns = sheet["columns"]
        declared_width = columns * TILE_SIZE
        declared_height = (
            (sheet["tile_count"] + columns - 1) // columns * TILE_SIZE
        )
        if image.width < declared_width or image.height < declared_height:
            raise ValueError(f"{name} sheet is smaller than its declared Tiled dimensions")
        water_sheet = normalized in WATER_SHEETS
        animation_ids = set(sheet["animations"])
        if water_sheet:
            included_ids = set(sheet["used_ids"]) | animation_ids
        else:
            included_ids = set(sheet["used_ids"]) | (
                animation_ids & set(sheet["used_ids"])
            )
        if not included_ids:
            continue
        for tile_id in tuple(included_ids):
            included_ids.update(
                frame["tile_id"]
                for frame in sheet["animations"].get(tile_id, ())
            )
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_dir / f"{normalized}.png")
        group_ids = animation_ids if water_sheet else animation_ids & set(sheet["used_ids"])
        tile_roles = {
            tile_id: _preferred_role(name, sheet["layer_usage"].get(tile_id, {}))
            for tile_id in group_ids
        }
        fallback_role = (
            "overlay"
            if normalized in {"water_detilazation", "water_detilazation2"}
            else "objects" if kind == "object"
            else "ground"
        )
        groups = (
            []
            if normalized.startswith("objects_animated") or normalized == "water_coasts"
            else _animated_groups(
                name, image, columns, sheet["animations"], group_ids,
                tile_roles, fallback_role,
                sheet["used_ids"] if normalized == "objects" else (),
            )
        )
        grouped_ids = {
            cell["key"]
            for group in groups
            for cell in group["cells"]
        }
        animated_groups.extend(groups)
        frame_ids = {
            frame["tile_id"]
            for frames in sheet["animations"].values()
            for frame in frames
        }

        if normalized in {"objects", "details"}:
            sprites = _object_sprites(image, sheet["used_ids"])
            folder = "objects" if normalized == "objects" else "details"
            sprite_dir = output_dir / folder
            sprite_dir.mkdir(parents=True, exist_ok=True)
            for index, (bounds, _area, source_ids, sprite) in enumerate(sprites, 1):
                key = f"undead_{normalized}_sprite_{index:03d}"
                asset_name = f"{normalized}_{index:03d}.png"
                sprite.resize(
                    (sprite.width * SCALE, sprite.height * SCALE),
                    Image.Resampling.NEAREST,
                ).save(sprite_dir / asset_name)
                catalog.append({
                    "key": key,
                    "kind": "object",
                    "category": "bush",
                    "asset": f"undead/{folder}/{asset_name}",
                    "sheet": name,
                    "representation": "sprite",
                    "display_name": f"{title.rsplit(' · ', 1)[-1]} {index:03d}",
                    "layer": "objects",
                    "editor_layer": 7,
                    "title": title,
                    "source_tile_ids": sorted(source_ids),
                    "source_size": [bounds.width, bounds.height],
                    "growth_size": bounds.width * bounds.height * SCALE * SCALE,
                    "palette_hidden": False,
                })
            if normalized == "objects":
                continue

        for tile_id in sorted(included_ids):
            frames = sheet["animations"].get(tile_id)
            source_ids = [frame["tile_id"] for frame in frames] if frames else [tile_id]
            if not any(
                _tile_crop(image, frame_id, columns).getbbox() is not None
                for frame_id in source_ids
            ):
                continue
            tiled_layers = sheet["layer_usage"].get(tile_id, {})
            tile_role = _preferred_role(name, tiled_layers)
            tile_category = category
            if normalized == "water_coasts" and "water" not in tiled_layers:
                tile_category = "floor"
            key = _key(name, tile_id)
            if key in grouped_ids:
                hidden_keys.add(key)
            catalog.append({
                "key": key,
                "kind": kind,
                "category": tile_category,
                "asset": f"undead/{normalized}.png",
                "sheet": name,
                "tile_id": tile_id,
                "columns": columns,
                "title": title,
                "used_in_example": tile_id in sheet["used_ids"],
                "tiled_layers": list(tiled_layers),
                "layer_roles": sorted({
                    mapped
                    for layer_name in tiled_layers
                    if (mapped := _layer_role(layer_name)) is not None
                }),
                "layer": tile_role,
                "editor_layer": _artist_layer(name, tiled_layers, tile_role),
                "water_decor": normalized in {"water_detilazation", "water_detilazation2"},
                "requires_water": normalized in {"water_detilazation", "water_detilazation2"},
                "display_name": f"{title.rsplit(' · ', 1)[-1]} · тайл {tile_id + 1:04d}",
                "frame_tile_ids": source_ids,
                "durations": [frame["duration"] for frame in frames] if frames else [],
                "palette_hidden": (
                    normalized.startswith("objects_animated")
                    or key in grouped_ids
                    or (not frames and tile_id in frame_ids)
                    or normalized == "details"
                ),
            })
            if normalized == "ground_rocks" and tile_role == "elevation":
                mountain_type = _mountain_type(
                    image,
                    source_ids,
                    columns,
                )
                catalog[-1]["mountain_type"] = mountain_type
                catalog[-1]["mountain_type_title"] = MOUNTAIN_TYPE_NAMES[mountain_type]
            if frames:
                animations[key] = {
                    "frame": [TILE_SIZE * SCALE, TILE_SIZE * SCALE],
                    "frames": len(frames),
                    "cols": len(frames),
                    "durations": [frame["duration"] for frame in frames],
                    "tile_ids": source_ids,
                }

        if normalized == "ground_rocks":
            artist_sheet = next(
                (
                    path
                    for path in (source_root / "PNG").glob("*.png")
                    if path.stem.casefold() == "ground_rocks"
                ),
                None,
            )
            if artist_sheet is None:
                raise FileNotFoundError(
                    f"PNG/Ground_rocks.png was not found in {source_root}"
                )
            artist_image = Image.open(artist_sheet).convert("RGBA")
            artist_locations, artist_columns, artist_rows = _artist_tile_locations(
                artist_image
            )
            mountain_items = {
                item["tile_id"]: item
                for item in catalog
                if item.get("sheet") == name
                and item.get("layer") == "elevation"
                and not item["palette_hidden"]
            }
            original_types = {
                tile_id: item.get("mountain_type", "dark")
                for tile_id, item in mountain_items.items()
            }
            artist_sheet_items = [
                item
                for item in catalog
                if item.get("sheet") == name
                and not item.get("palette_hidden", False)
            ]
            artist_cells_by_tile, artist_layout_rows = _artist_layout_cells(
                image,
                artist_image,
                artist_sheet_items,
                artist_columns,
                artist_rows,
            )
            for item in artist_sheet_items:
                tile_id = item["tile_id"]
                item["artist_sheet_positions"] = [
                    [column, row]
                    for row, column in artist_cells_by_tile.get(tile_id, ())
                ]
                item["artist_sheet_size"] = [
                    artist_columns,
                    artist_layout_rows,
                ]
            pending_groups = []
            assigned_tile_ids = set()
            for _bounds, _area, source_ids, _sprite in _object_sprites(
                image,
                included_ids,
            ):
                group_items = [
                    mountain_items[tile_id]
                    for tile_id in source_ids
                    if tile_id in mountain_items
                    and tile_id not in assigned_tile_ids
                ]
                if not group_items:
                    continue
                group_key = f"undead_ground_rocks_mountain_{len(pending_groups) + 1:03d}"
                positions = _artist_group_positions(
                    group_items,
                    image,
                    artist_locations,
                    artist_columns,
                    artist_rows,
                    group_key,
                )
                pending_groups.extend(
                    _artist_connected_groups(group_items, positions)
                )
                assigned_tile_ids.update(item["tile_id"] for item in group_items)

            for tile_id, item in mountain_items.items():
                if tile_id in assigned_tile_ids:
                    continue
                pending_groups.extend(
                    _artist_connected_groups(
                        [item],
                        _artist_group_positions(
                            [item],
                            image,
                            artist_locations,
                            artist_columns,
                            artist_rows,
                            f"undead_ground_rocks_mountain_{tile_id}",
                        ),
                    )
                )

            pending_groups.sort(
                key=lambda entry: (
                    min(row for row, _column in entry[1].values()),
                    min(column for _row, column in entry[1].values()),
                    -len(entry[0]),
                    min(item["tile_id"] for item in entry[0]),
                )
            )
            for group_index, (group_items, positions) in enumerate(
                pending_groups,
                1,
            ):
                mountain_types = Counter(
                    original_types[item["tile_id"]]
                    for item in group_items
                )
                mountain_type = max(
                    ("dark", "stone"),
                    key=lambda value: (mountain_types[value], value == "stone"),
                )
                group_key = f"undead_ground_rocks_mountain_{group_index:03d}"
                left = min(column for _row, column in positions.values())
                top = min(row for row, _column in positions.values())
                for item in group_items:
                    tile_id = item["tile_id"]
                    row, column = positions[tile_id]
                    item["mountain_type"] = mountain_type
                    item["mountain_type_title"] = MOUNTAIN_TYPE_NAMES[mountain_type]
                    item["mountain_group"] = group_key
                    item["mountain_position"] = [
                        column - left,
                        row - top,
                    ]

    catalog.extend(_standalone_sprites(source_root, output_dir))
    animated_sprites, sprite_animations = _animated_sprites(source_root, output_dir)
    catalog.extend(animated_sprites)
    animations.update(sprite_animations)
    _hide_duplicate_sprites(catalog, output_dir)
    (output_dir / "catalog.json").write_text(
        json.dumps(
            {
                "items": catalog,
                "animated_groups": animated_groups,
                "palette_hidden_keys": sorted(hidden_keys),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (output_dir / "animations.json").write_text(
        json.dumps(animations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    license_path = source_root / "License.txt"
    if license_path.is_file():
        shutil.copyfile(license_path, output_dir / "License.txt")
    return len(catalog), len(animations), len(animated_groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing the Undead biome")
    parser.add_argument("--output", type=Path, help="output directory (defaults to assets/map/undead)")
    args = parser.parse_args()
    tiles, animation_count, group_count = import_biome(args.source, args.output)
    print(
        f"Imported {tiles} Undead assets "
        f"({animation_count} animations, {group_count} complete animated compositions)."
    )


if __name__ == "__main__":
    main()
