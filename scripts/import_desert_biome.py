"""Import the Desert biome's used Tiled tiles, animated compositions, and intact sprites."""
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
WATER_SHEETS = frozenset({"water_detilazation", "water_detilazation2"})
SHEET_SETTINGS = {
    "ground_grass": ("ground", "grass", "Пустыня · Песок и возвышенности"),
    "water_detilazation2": ("ground", "water", "Пустыня · Водная анимация"),
    "water_detilazation": ("ground", "water", "Пустыня · Водные детали"),
    "rocks_details": ("ground", "rock", "Пустыня · Каменные детали"),
    "water_coasts": ("ground", "water", "Пустыня · Берега и вода"),
    "spots": ("ground", "floor", "Пустыня · Пятна и следы"),
    "sand": ("ground", "floor", "Пустыня · Анимированный песок"),
    "objects": ("object", "bush", "Пустыня · Объекты из атласа"),
    "details": ("object", "bush", "Пустыня · Детали из атласа"),
    "animated_objects": ("object", "bush", "Пустыня · Анимированные объекты"),
}
LAYER_ROLES = {
    "water": "ground",
    "sand": "ground",
    "grass": "ground",
}
OBJECT_TYPES = (
    ("trees", "Деревья"),
    ("plants", "Растения и кактусы"),
    ("rocks", "Камни"),
    ("structures", "Постройки"),
    ("remains", "Кости и черепа"),
    ("terrain", "Элементы ландшафта"),
    ("water", "Объекты у воды"),
    ("other", "Прочие объекты"),
)
OBJECT_TYPE_NAMES = dict(OBJECT_TYPES)
OBJECT_TYPE_ORDER = {
    object_type: index for index, (object_type, _title) in enumerate(OBJECT_TYPES)
}


def _key(sheet, tile_id):
    normalized = re.sub(r"[^a-z0-9]+", "_", sheet.casefold()).strip("_")
    return f"desert_{normalized}_{tile_id:04d}"


def _layer_role(layer_name):
    layer = layer_name.casefold().replace(" ", "_")
    if "elevated_space" in layer or layer == "lakes_upstairs":
        return "elevation"
    if layer.startswith("objects"):
        return "objects"
    if layer == "bridge":
        return "infra"
    if layer in LAYER_ROLES:
        return LAYER_ROLES[layer]
    if (
        layer.startswith(("water_details", "details", "shadow", "spots", "dots", "rock_details", "rocks_details"))
        or layer.startswith("objects_under")
    ):
        return "overlay"
    return None


def _preferred_role(sheet_name, layer_usage):
    normalized = sheet_name.casefold()
    if normalized in WATER_SHEETS:
        return "overlay"
    if normalized.startswith(("objects", "details")):
        return "objects"
    counts = Counter()
    for layer_name, count in layer_usage.items():
        role = _layer_role(layer_name)
        if role:
            counts[role] += count
    if counts:
        return max(counts, key=lambda role: (counts[role], role))
    return "ground"


def _editor_layer(sheet_name, layer_usage, fallback_role):
    normalized = sheet_name.casefold()
    if normalized in WATER_SHEETS or (
        normalized == "water_coasts"
        and any(_layer_role(layer) == "ground" and layer.casefold() == "water" for layer in layer_usage)
    ):
        return 2 if normalized in WATER_SHEETS else 1
    if normalized.startswith(("objects", "details")):
        return 7
    role_layers = {
        "ground": 3,
        "overlay": 4,
        "elevation": 5,
        "infra": 6,
        "objects": 7,
    }
    counts = Counter()
    for layer_name, count in layer_usage.items():
        role = _layer_role(layer_name)
        if role in role_layers:
            counts[role] += count
    if counts:
        return role_layers[max(counts, key=lambda role: (counts[role], role))]
    return role_layers.get(fallback_role, 3)


def _tile_category(sheet_name, layer_usage, fallback_category, role):
    if role == "elevation":
        return "rock"
    normalized = sheet_name.casefold()
    if normalized == "water_coasts":
        if any(layer.casefold() == "water" for layer in layer_usage):
            return "water"
        if any("grass" in layer.casefold() for layer in layer_usage):
            return "grass"
        if any("sand" in layer.casefold() for layer in layer_usage):
            return "floor"
    if normalized in WATER_SHEETS:
        return "water"
    if role == "overlay" and any("water" in layer.casefold() for layer in layer_usage):
        return "water"
    return fallback_category


def _animated_groups(
    sheet_name,
    image,
    columns,
    animations,
    tile_ids,
    tile_roles,
    fallback_role,
):
    animated_cells = {
        (tile_id // columns, tile_id % columns): tile_id
        for tile_id, frames in animations.items()
        if tile_id in tile_ids
        and frames
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
        groups.append({
            "key": f"desert_{sheet_name.casefold()}_animation_{min(group):04d}",
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
                for tile_id in sorted(group)
            ],
        })
    return groups


def _sprite_type(source_name):
    name = source_name.casefold()
    if "tree" in name:
        return "trees"
    if any(token in name for token in ("cactus", "bush", "flower", "grass_element", "plant")):
        return "plants"
    if "rock" in name:
        return "rocks"
    if any(token in name for token in ("ruin", "gate", "pyramid")):
        return "structures"
    if any(token in name for token in ("bone", "scull", "skull")):
        return "remains"
    if "sand_element" in name:
        return "terrain"
    if "water" in name:
        return "water"
    return "other"


def _standalone_sprites(source_root, output_dir):
    source_dir = source_root / "PNG" / "Objects_separately"
    sources = sorted(source_dir.glob("*.png"), key=lambda path: path.name.casefold())
    if not sources:
        raise FileNotFoundError(f"No separate Desert sprites were found in {source_dir}")
    output_objects = output_dir / "objects"
    output_objects.mkdir(parents=True, exist_ok=True)
    catalog = []
    for source in sources:
        with Image.open(source) as source_image:
            image = source_image.convert("RGBA")
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"Desert sprite has no visible pixels: {source}")
        normalized = re.sub(r"[^a-z0-9]+", "_", source.stem.casefold()).strip("_")
        key = f"desert_sprite_{normalized}"
        asset_name = f"{key}.png"
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_objects / asset_name)
        object_type = _sprite_type(source.name)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "bush",
            "asset": f"desert/objects/{asset_name}",
            "sheet": "Objects_separately",
            "representation": "sprite",
            "display_name": source.stem.replace("_", " "),
            "layer": "objects",
            "editor_layer": 7,
            "title": "Пустыня · Цельные объекты",
            "source_name": source.name,
            "source_size": list(image.size),
            "object_type": object_type,
            "object_type_name": OBJECT_TYPE_NAMES[object_type],
            "object_type_order": OBJECT_TYPE_ORDER[object_type],
            "palette_hidden": False,
        })
    return catalog


def _hide_duplicate_sprites(catalog, output_dir):
    duplicates = defaultdict(list)
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
            raise ValueError(f"Desert sprite has no visible pixels: {image_path}")
        cropped = image.crop(bounds)
        signature = cropped.size, hashlib.sha256(cropped.tobytes()).digest()
        duplicates[signature].append(item)
    for items in duplicates.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda item: (
            preferred_sheet_order.get(item.get("sheet", "").casefold(), 3),
            item["key"],
        ))
        for item in items[1:]:
            item["palette_hidden"] = True


def import_biome(source_root, output_dir=None):
    source_root = Path(source_root).resolve()
    if source_root.name.casefold() == "tiled_files":
        source_root = source_root.parent
    map_path = source_root / "Tiled_files" / "Desert.tmx"
    if not map_path.is_file():
        raise FileNotFoundError(f"Desert.tmx was not found at {map_path}")
    output_dir = Path(output_dir or MAP_ASSETS / "desert").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    map_root, tilesets = _tilesets(source_root, map_path)
    used_ids, layer_usage = _used_tiles(map_root, tilesets)
    catalog = []
    animations = {}
    animated_groups = []
    for tileset in tilesets:
        name = tileset["name"]
        normalized = name.casefold()
        if normalized not in SHEET_SETTINGS:
            continue
        kind, category, title = SHEET_SETTINGS[normalized]
        image = Image.open(tileset["path"]).convert("RGBA")
        columns = tileset["columns"]
        declared_width = columns * TILE_SIZE
        declared_height = (
            (tileset["tile_count"] + columns - 1) // columns * TILE_SIZE
        )
        if image.width < declared_width or image.height < declared_height:
            raise ValueError(f"{name} sheet is smaller than its declared Tiled dimensions")
        sheet_used_ids = set(used_ids[name])
        sheet_animations = tileset["animations"]
        animation_ids = set(sheet_animations)
        included_ids = sheet_used_ids | (
            animation_ids if normalized in WATER_SHEETS
            else animation_ids & sheet_used_ids
        )
        if not included_ids:
            continue
        for tile_id in tuple(included_ids):
            included_ids.update(
                frame["tile_id"] for frame in sheet_animations.get(tile_id, ())
            )
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_dir / f"{normalized}.png")
        tile_roles = {
            tile_id: _preferred_role(name, layer_usage[name].get(tile_id, {}))
            for tile_id in animation_ids
        }
        fallback_role = (
            "overlay" if normalized in WATER_SHEETS
            else "objects" if kind == "object"
            else "ground"
        )
        groups = (
            []
            if normalized in {"objects", "details", "water_coasts"}
            else _animated_groups(
                name,
                image,
                columns,
                sheet_animations,
                animation_ids & included_ids,
                tile_roles,
                fallback_role,
            )
        )
        grouped_keys = {
            cell["key"] for group in groups for cell in group["cells"]
        }
        animated_groups.extend(groups)
        frame_ids = {
            frame["tile_id"]
            for frames in sheet_animations.values()
            for frame in frames
        }

        if normalized in {"objects", "details"}:
            sprites = _object_sprites(image, sheet_used_ids)
            folder = "objects" if normalized == "objects" else "details"
            sprite_dir = output_dir / folder
            sprite_dir.mkdir(parents=True, exist_ok=True)
            for index, (bounds, _area, source_ids, sprite) in enumerate(sprites, 1):
                key = f"desert_{normalized}_sprite_{index:03d}"
                asset_name = f"{normalized}_{index:03d}.png"
                sprite.resize(
                    (sprite.width * SCALE, sprite.height * SCALE),
                    Image.Resampling.NEAREST,
                ).save(sprite_dir / asset_name)
                catalog.append({
                    "key": key,
                    "kind": "object",
                    "category": "bush",
                    "asset": f"desert/{folder}/{asset_name}",
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
            frames = sheet_animations.get(tile_id)
            source_ids = [frame["tile_id"] for frame in frames] if frames else [tile_id]
            if not any(
                _tile_crop(image, frame_id, columns).getbbox() is not None
                for frame_id in source_ids
            ):
                continue
            tile_layers = layer_usage[name].get(tile_id, {})
            role = _preferred_role(name, tile_layers)
            tile_category = _tile_category(name, tile_layers, category, role)
            key = _key(name, tile_id)
            catalog.append({
                "key": key,
                "kind": kind,
                "category": tile_category,
                "asset": f"desert/{normalized}.png",
                "sheet": name,
                "tile_id": tile_id,
                "columns": columns,
                "title": title,
                "used_in_example": tile_id in sheet_used_ids,
                "tiled_layers": list(tile_layers),
                "layer_roles": sorted({
                    mapped
                    for layer_name in tile_layers
                    if (mapped := _layer_role(layer_name)) is not None
                }),
                "layer": role,
                "editor_layer": _editor_layer(name, tile_layers, role),
                "water_decor": normalized in WATER_SHEETS,
                "requires_water": normalized in WATER_SHEETS,
                "display_name": f"{title.rsplit(' · ', 1)[-1]} · тайл {tile_id + 1:04d}",
                "frame_tile_ids": source_ids,
                "durations": [frame["duration"] for frame in frames] if frames else [],
                "palette_hidden": (
                    normalized == "details"
                    or key in grouped_keys
                    or (not frames and tile_id in frame_ids)
                ),
            })
            if frames:
                animations[key] = {
                    "frame": [TILE_SIZE * SCALE, TILE_SIZE * SCALE],
                    "frames": len(frames),
                    "cols": len(frames),
                    "durations": [frame["duration"] for frame in frames],
                    "tile_ids": source_ids,
                }

    catalog.extend(_standalone_sprites(source_root, output_dir))
    _hide_duplicate_sprites(catalog, output_dir)
    (output_dir / "catalog.json").write_text(
        json.dumps(
            {"items": catalog, "animated_groups": animated_groups},
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
    parser.add_argument("source", type=Path, help="directory containing the Desert biome")
    parser.add_argument("--output", type=Path, help="output directory (defaults to assets/map/desert)")
    args = parser.parse_args()
    tiles, animation_count, group_count = import_biome(args.source, args.output)
    print(
        f"Imported {tiles} Desert assets "
        f"({animation_count} animations, {group_count} complete animated compositions)."
    )


if __name__ == "__main__":
    main()
