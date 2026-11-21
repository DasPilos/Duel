"""Import the winter biome's used Tiled tiles and intact standalone growth sprites."""
import argparse
import json
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import pygame
from PIL import Image, ImageChops, ImageFilter

from scripts.import_rocky_biome import GID_MASK, SCALE, TILE_SIZE, _object_sprites, _tile_crop

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_ASSETS = PROJECT_ROOT / "assets" / "map"
TILESET_NAMES = {
    "ground_ice": ("ground", "floor", "ground", "Лёд и земля"),
    "snow": ("ground", "floor", "overlay", "Снег"),
    "ice": ("ground", "floor", "ground", "Лёд"),
    "water_detilazation": ("ground", "floor", "overlay", "Вода и анимация"),
    "water_detilazation_v2": ("ground", "floor", "overlay", "Водные детали"),
    "cracks": ("ground", "floor", "overlay", "Ледяные трещины"),
    "details": ("ground", "floor", "overlay", "Детали"),
    "spots": ("ground", "floor", "overlay", "Следы и пятна"),
}
EXTRA_SHEETS = {
    "Ice": ("ground", "floor", "ground", "Лёд"),
    "water_detilazation_v2": ("ground", "floor", "overlay", "Водные детали · набор 2"),
}
WATER_TILE_SHEETS = frozenset({"ice", "ground_ice"})
WATER_COVERAGE_THRESHOLD = 0.5
IMPASSABLE_WATER_COVERAGE_THRESHOLD = 0.3
REMOVED_ICE_DUPLICATE_TILE_IDS = frozenset({249, 273})
GROWTH_RE = re.compile(
    r"^(?P<base>.+?)_(?P<surface>ground|snow|wall)_shadow(?P<stage>\d+)(?:-(?P<variant>\d+))?$",
    re.IGNORECASE,
)
DISPLAY_NAMES = {
    "trees1": "Заснеженное дерево 1",
    "trees2": "Заснеженное дерево 2",
    "trees3": "Заснеженное дерево 3",
    "trees4": "Заснеженное дерево 4",
    "ice_trees": "Ледяное дерево",
    "crystal_flower": "Цветочный кристалл",
    "crystal_sharp": "Острый кристалл",
    "crystal_square": "Квадратный кристалл",
    "ice_flowers": "Ледяные цветы",
    "mushroom1": "Гриб 1",
    "mushroom2": "Гриб 2",
    "ruins1": "Руины 1",
    "ruins2": "Руины 2",
    "snowmen": "Снеговик",
    "stones": "Камни",
    "idols": "Идолы",
}


def _is_majority_open_water(tile):
    """True when dark open-water pixels occupy more than half of the full tile frame."""
    return _open_water_share(tile) > WATER_COVERAGE_THRESHOLD


def _has_impassable_open_water(tile):
    """True when dark open-water pixels occupy more than 30% of the full tile frame."""
    return _open_water_share(tile) > IMPASSABLE_WATER_COVERAGE_THRESHOLD


def _open_water_share(tile):
    rgba = tile.convert("RGBA")
    pixels = rgba.load()
    water_pixels = 0
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            if (
                alpha
                and blue > red * 1.25
                and blue > green * 1.15
                and max(red, green, blue) < 180
            ):
                water_pixels += 1
    return water_pixels / (rgba.width * rgba.height)


def _tilesets(source_root, map_path):
    root = ET.parse(map_path).getroot()
    entries = root.findall("tileset")
    tilesets = []
    png_root = source_root / "PNG"
    png_by_name = {path.name.casefold(): path for path in png_root.glob("*.png")}
    for index, entry in enumerate(entries):
        source = entry.get("source")
        definition_path = (map_path.parent / source).resolve() if source else None
        definition = ET.parse(definition_path).getroot() if definition_path else entry
        image = definition.find("image")
        if image is None:
            continue
        filename = Path(image.attrib["source"]).name
        candidate = (definition_path.parent if definition_path else map_path.parent) / filename
        image_path = candidate if candidate.is_file() else png_by_name.get(filename.casefold())
        if image_path is None:
            raise FileNotFoundError(f"Winter tilesheet is missing: {filename}")
        name = definition.get("name", Path(filename).stem)
        first_gid = int(entry.attrib["firstgid"])
        end_gid = int(entries[index + 1].attrib["firstgid"]) if index + 1 < len(entries) else first_gid + int(definition.attrib["tilecount"])
        animations = {}
        for tile in definition.findall("tile"):
            frames = tile.find("animation")
            if frames is not None:
                animations[int(tile.attrib["id"])] = [
                    {"tile_id": int(frame.attrib["tileid"]), "duration": int(frame.attrib["duration"])}
                    for frame in frames.findall("frame")
                ]
        tilesets.append({
            "first_gid": first_gid,
            "end_gid": end_gid,
            "name": name,
            "path": image_path,
            "columns": int(definition.attrib["columns"]),
            "tile_count": int(definition.attrib["tilecount"]),
            "animations": animations,
        })
    return root, tilesets


def _used_tiles(root, tilesets):
    used = {sheet["name"]: set() for sheet in tilesets}
    usage = {sheet["name"]: defaultdict(Counter) for sheet in tilesets}
    for layer in root.findall("layer"):
        data = layer.find("data")
        if data is None:
            continue
        chunks = data.findall("chunk")
        values = [value for chunk in chunks for value in (chunk.text or "").split(",")]
        if not chunks and data.text:
            values = data.text.split(",")
        for raw in values:
            if not raw.strip():
                continue
            gid = int(raw.strip()) & GID_MASK
            for sheet in tilesets:
                if sheet["first_gid"] <= gid < sheet["end_gid"]:
                    tile_id = gid - sheet["first_gid"]
                    used[sheet["name"]].add(tile_id)
                    usage[sheet["name"]][tile_id][layer.get("name", "")] += 1
                    break
    return used, usage


def _storage_layer(sheet_name, tiled_layers):
    spec = TILESET_NAMES.get(sheet_name.casefold())
    if spec is None:
        return "ground"
    if sheet_name.casefold() == "water_detilazation":
        if any(name.casefold() == "water" for name in tiled_layers):
            return "ground"
    return spec[2]


def _tile_key(sheet_name, tile_id):
    return f"winter_{re.sub(r'[^a-z0-9]+', '_', sheet_name.casefold()).strip('_')}_{tile_id:04d}"


def _animated_groups(sheet_name, image, columns, animations, used_ids):
    """Group adjacent animated water tiles into indivisible palette stamps."""
    cells = {
        (tile_id // columns, tile_id % columns): tile_id
        for tile_id, frames in animations.items()
        if tile_id in used_ids and frames and any(
            image.crop((
                frame["tile_id"] % columns * TILE_SIZE,
                frame["tile_id"] // columns * TILE_SIZE,
                (frame["tile_id"] % columns + 1) * TILE_SIZE,
                (frame["tile_id"] // columns + 1) * TILE_SIZE,
            )).getchannel("A").getbbox() is not None
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
        if len(group) < 2:
            continue
        top = min(tile_id // columns for tile_id in group)
        left = min(tile_id % columns for tile_id in group)
        ordered_ids = sorted(group)
        groups.append({
            "key": f"winter_{sheet_name.casefold()}_animation_{ordered_ids[0]:04d}",
            "sheet": sheet_name,
            "width": max(tile_id % columns for tile_id in group) - left + 1,
            "height": max(tile_id // columns for tile_id in group) - top + 1,
            "cells": [
                {
                    "key": _tile_key(sheet_name, tile_id),
                    "x": tile_id % columns - left,
                    "y": tile_id // columns - top,
                    "layer": "overlay",
                }
                for tile_id in ordered_ids
            ],
        })
    return groups


def _import_standalone(source_root, output_dir):
    root = source_root / "PNG" / "Objects_separately"
    candidates = []
    for path in sorted(root.rglob("*.png"), key=lambda item: item.as_posix().casefold()):
        match = GROWTH_RE.fullmatch(path.stem)
        if match is None:
            raise ValueError(f"Unexpected standalone winter object name: {path.name}")
        candidates.append((path, match))

    objects_dir = output_dir / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    seen = set()
    catalog = []
    for path, match in candidates:
        image = Image.open(path).convert("RGBA")
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Winter object has no visible pixels: {path}")
        signature = (image.size, image.tobytes())
        duplicate = signature in seen
        seen.add(signature)
        base = re.sub(r"[^a-z0-9]+", "_", match["base"].casefold()).strip("_")
        surface = match["surface"].casefold()
        stage = int(match["stage"])
        variant = match["variant"]
        variant_id = int(variant or 0)
        key = f"winter_growth_{base}_{surface}_{stage:02d}_{variant_id:02d}"
        asset_name = f"{key}.png"
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(objects_dir / asset_name)
        title = DISPLAY_NAMES.get(base, base.replace("_", " ").capitalize())
        surface_label = {"ground": "земля", "snow": "снег", "wall": "стена"}[surface]
        display_name = f"{title} · {surface_label} · стадия {stage}"
        if variant:
            display_name += f" · вариант {variant}"
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "bush",
            "asset": f"winter/objects/{asset_name}",
            "sheet": "Objects_separately",
            "representation": "sprite",
            "display_name": display_name,
            "growth_series": f"winter_{base}_{surface}",
            "growth_stage": stage,
            "growth_size": (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) * SCALE * SCALE,
            "layer": "objects",
            "title": "Зимний биом · Растущие объекты",
            "palette_hidden": duplicate,
            "source_name": path.name,
            "source_folder": path.parent.name,
        })
    return catalog


def _import_detail_sprites(sheet, used_ids, output_dir):
    sprites = _object_sprites(sheet, used_ids)
    objects_dir = output_dir / "details_objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    for index, (bounds, _area, tile_ids, sprite) in enumerate(sprites, start=1):
        key = f"winter_details_object_{index:03d}"
        asset_name = f"detail_object_{index:03d}.png"
        sprite.resize(
            (sprite.width * SCALE, sprite.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(objects_dir / asset_name)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "rock",
            "asset": f"winter/details_objects/{asset_name}",
            "sheet": "details",
            "representation": "sprite",
            "display_name": f"Зимняя деталь {index:03d}",
            "layer": "objects",
            "title": "Зимний биом · Цельные детали",
            "source_tile_ids": sorted(tile_ids),
            "growth_size": bounds.width * bounds.height * SCALE * SCALE,
            "palette_hidden": False,
        })
    return catalog


def _whole_sprites(sheet, used_ids, gap=1):
    """Extract intact alpha groups, joining near-touching pixels into one decal."""
    columns = sheet.width // TILE_SIZE
    alpha = sheet.getchannel("A")
    grouped_alpha = alpha.filter(ImageFilter.MaxFilter(gap * 2 + 1)) if gap else alpha
    grouped_image = Image.new("RGBA", sheet.size)
    grouped_image.putalpha(grouped_alpha)
    surface = pygame.image.fromstring(grouped_image.tobytes(), sheet.size, "RGBA")
    components = pygame.mask.from_surface(surface, 1).connected_components()
    tile_mask = pygame.mask.Mask((TILE_SIZE, TILE_SIZE), fill=True)
    sprites = []
    for component in components:
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
            unsetcolor=(0, 0, 0, 0),
        )
        component_alpha = Image.frombytes(
            "RGBA",
            mask_surface.get_size(),
            pygame.image.tostring(mask_surface, "RGBA"),
        ).getchannel("A")
        sprite = sheet.crop((bounds.left, bounds.top, bounds.right, bounds.bottom))
        sprite.putalpha(ImageChops.multiply(
            sprite.getchannel("A"),
            component_alpha.crop((bounds.left, bounds.top, bounds.right, bounds.bottom)),
        ))
        visible = sprite.getchannel("A").getbbox()
        if visible is None:
            continue
        sprite = sprite.crop(visible)
        sprites.append((
            bounds.left + visible[0],
            bounds.top + visible[1],
            tile_ids,
            sprite,
        ))
    return sorted(sprites, key=lambda entry: (entry[1], entry[0]))


def _import_decal_sprites(sheet, used_ids, output_dir, sheet_name, folder, prefix, title):
    objects_dir = output_dir / folder
    objects_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    for index, (left, top, tile_ids, sprite) in enumerate(
        _whole_sprites(sheet, used_ids),
        start=1,
    ):
        key = f"winter_{prefix}_{index:03d}"
        asset_name = f"{prefix}_{index:03d}.png"
        sprite.resize(
            (sprite.width * SCALE, sprite.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(objects_dir / asset_name)
        catalog.append({
            "key": key,
            "kind": "object",
            "category": "floor",
            "asset": f"winter/{folder}/{asset_name}",
            "sheet": sheet_name,
            "representation": "sprite",
            "display_name": f"{title} {index:03d}",
            "layer": "objects",
            "title": f"Зимний биом · {title}",
            "source_tile_ids": sorted(tile_ids),
            "source_position": [left, top],
            "growth_size": sprite.width * sprite.height * SCALE * SCALE,
            "palette_hidden": False,
        })
    return catalog


def import_biome(source_root, output_dir=None):
    source_root = Path(source_root).resolve()
    map_path = source_root / "Tiled_files" / "Winter.tmx"
    if not map_path.is_file():
        raise FileNotFoundError(f"Winter.tmx was not found at {map_path}")
    output_dir = Path(output_dir or MAP_ASSETS / "winter").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    map_root, tilesets = _tilesets(source_root, map_path)
    used, usage = _used_tiles(map_root, tilesets)

    catalog = []
    animations = {}
    animated_groups = []
    detail_sprites = []
    spot_sprites = []
    water_detail_sprites = []
    seen_tiles = defaultdict(set)
    overlay_keys = []
    for sheet in tilesets:
        name = sheet["name"]
        settings = TILESET_NAMES.get(name.casefold())
        if settings is None or name.casefold() == "objects":
            continue
        image = Image.open(sheet["path"]).convert("RGBA")
        if name.casefold() == "details":
            detail_columns = image.width // TILE_SIZE
            detail_rows = image.height // TILE_SIZE
            detail_sprites = _import_detail_sprites(
                image,
                set(range(detail_columns * detail_rows)),
                output_dir,
            )
        elif name.casefold() == "spots":
            spot_sprites = _import_decal_sprites(
                image, used[name], output_dir, name,
                "spots_objects", "spot", "Следы и пятна",
            )
        elif name.casefold() == "water_detilazation_v2":
            water_detail_sprites = _import_decal_sprites(
                image,
                set(range(sheet["columns"] * (image.height // TILE_SIZE))),
                output_dir,
                name,
                "water_details",
                "water_detail",
                "Водная деталь",
            )
        target = output_dir / f"{name}.png"
        image.resize((image.width * SCALE, image.height * SCALE), Image.Resampling.NEAREST).save(target)
        tile_ids = set(used[name])
        for tile_id in tuple(tile_ids):
            tile_ids.update(frame["tile_id"] for frame in sheet["animations"].get(tile_id, []))
        if name.casefold() == "water_detilazation":
            animated_groups.extend(_animated_groups(
                name,
                image,
                sheet["columns"],
                sheet["animations"],
                used[name],
            ))
        for tile_id in sorted(tile_ids):
            tile = image.crop((
                tile_id % sheet["columns"] * TILE_SIZE,
                tile_id // sheet["columns"] * TILE_SIZE,
                (tile_id % sheet["columns"] + 1) * TILE_SIZE,
                (tile_id // sheet["columns"] + 1) * TILE_SIZE,
            ))
            animated = sheet["animations"].get(tile_id)
            if tile.getchannel("A").getbbox() is None and not (
                animated and any(
                    image.crop((
                        frame["tile_id"] % sheet["columns"] * TILE_SIZE,
                        frame["tile_id"] // sheet["columns"] * TILE_SIZE,
                        (frame["tile_id"] % sheet["columns"] + 1) * TILE_SIZE,
                        (frame["tile_id"] // sheet["columns"] + 1) * TILE_SIZE,
                    )).getchannel("A").getbbox() is not None
                    for frame in animated
                )
            ):
                continue
            category = (
                "water"
                if name.casefold() in WATER_TILE_SHEETS and _is_majority_open_water(tile)
                else settings[1]
            )
            frame_ids = [frame["tile_id"] for frame in animated] if animated else [tile_id]
            role = _storage_layer(name, usage[name].get(tile_id, {}))
            signatures = tuple(
                _tile_crop(image, frame_id, sheet["columns"]).tobytes()
                for frame_id in frame_ids
            )
            duplicate = signatures in seen_tiles[(role, bool(animated))]
            seen_tiles[(role, bool(animated))].add(signatures)
            key = _tile_key(name, tile_id)
            if role == "overlay":
                overlay_keys.append(key)
            catalog.append({
                "key": key,
                "kind": settings[0],
                "category": category,
                "asset": f"winter/{name}.png",
                "sheet": name,
                "tile_id": tile_id,
                "columns": sheet["columns"],
                "title": f"Зимний биом · {settings[3]}",
                "used_in_example": tile_id in used[name],
                "tiled_layers": list(usage[name].get(tile_id, {})),
                "layer": role,
                "display_name": (
                    f"Вода без льда · тайл {tile_id + 1:04d}"
                    if category == "water"
                    else f"Тайл {tile_id + 1:04d}"
                ),
                "frame_tile_ids": frame_ids,
                "durations": [frame["duration"] for frame in animated] if animated else [],
                "palette_hidden": name.casefold() in ("details", "spots", "water_detilazation_v2") or duplicate or (not animated and any(
                    tile_id in [frame["tile_id"] for frame in frames]
                    for frames in sheet["animations"].values()
                )),
            })
            if animated:
                animations[key] = {
                    "frame": [TILE_SIZE * SCALE, TILE_SIZE * SCALE],
                    "frames": len(animated),
                    "cols": len(animated),
                    "durations": [frame["duration"] for frame in animated],
                    "tile_ids": frame_ids,
                }

    source_pngs = {
        path.stem.casefold(): path
        for directory in (source_root / "PNG", source_root / "Tiled_files")
        for path in directory.glob("*.png")
    }
    known_sheets = {sheet["name"].casefold() for sheet in tilesets}
    seen_open_water_tiles = set()
    for name, settings in EXTRA_SHEETS.items():
        if name.casefold() in known_sheets:
            continue
        image_path = source_pngs.get(name.casefold())
        if image_path is None:
            continue
        image = Image.open(image_path).convert("RGBA")
        columns = image.width // TILE_SIZE
        tile_count = columns * (image.height // TILE_SIZE)
        image.resize((image.width * SCALE, image.height * SCALE), Image.Resampling.NEAREST).save(
            output_dir / f"{name}.png"
        )
        for tile_id in range(tile_count):
            if name.casefold() == "ice" and tile_id in REMOVED_ICE_DUPLICATE_TILE_IDS:
                continue
            tile = image.crop((
                tile_id % columns * TILE_SIZE,
                tile_id // columns * TILE_SIZE,
                (tile_id % columns + 1) * TILE_SIZE,
                (tile_id // columns + 1) * TILE_SIZE,
            ))
            if tile.getchannel("A").getbbox() is None:
                continue
            key = _tile_key(name, tile_id)
            category = (
                "water"
                if name.casefold() in WATER_TILE_SHEETS and _is_majority_open_water(tile)
                else settings[1]
            )
            signature = (_tile_crop(image, tile_id, columns).tobytes(),)
            if category == "water":
                if signature in seen_open_water_tiles:
                    continue
                seen_open_water_tiles.add(signature)
            duplicate = signature in seen_tiles[(settings[2], False)]
            seen_tiles[(settings[2], False)].add(signature)
            if settings[2] == "overlay":
                overlay_keys.append(key)
            catalog.append({
                "key": key,
                "kind": settings[0],
                "category": category,
                "asset": f"winter/{name}.png",
                "sheet": name,
                "tile_id": tile_id,
                "columns": columns,
                "title": f"Зимний биом · {settings[3]}",
                "used_in_example": False,
                "tiled_layers": [],
                "layer": settings[2],
                "display_name": (
                    f"Вода без льда · тайл {tile_id + 1:04d}"
                    if category == "water"
                    else f"Тайл {tile_id + 1:04d}"
                ),
                "frame_tile_ids": [tile_id],
                "durations": [],
                "palette_hidden": duplicate or name.casefold() == "water_detilazation_v2",
            })
        if name.casefold() == "water_detilazation_v2":
            water_detail_sprites = _import_decal_sprites(
                image,
                set(range(tile_count)),
                output_dir,
                name,
                "water_details",
                "water_detail",
                "Водная деталь",
            )

    standalone = _import_standalone(source_root, output_dir)
    catalog.extend(detail_sprites)
    catalog.extend(spot_sprites)
    catalog.extend(water_detail_sprites)
    catalog.extend(standalone)
    (output_dir / "catalog.json").write_text(
        json.dumps(
            {"items": catalog, "overlay_keys": overlay_keys, "animated_groups": animated_groups},
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
    return len(catalog), len(animations), len(standalone)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing the winter biome")
    parser.add_argument("--output", type=Path, help="output directory (defaults to assets/map/winter)")
    args = parser.parse_args()
    tiles, animations, objects = import_biome(args.source, args.output)
    print(f"Imported {tiles} winter assets ({animations} animations, {objects} intact objects).")


if __name__ == "__main__":
    main()
