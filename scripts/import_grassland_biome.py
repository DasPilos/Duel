"""Import the used tiles from Craftpix's Glades Tiled map."""
import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_ASSETS = PROJECT_ROOT / "assets" / "map"
TILE_SIZE = 16
SCALE = 2
GID_MASK = 0x1FFFFFFF
SHEET_SETTINGS = {
    "Ground_grass": ("ground", "grass", "ground", "Земля и трава"),
    "Water_coasts": ("ground", "water", "ground", "Береговая вода"),
    "Water_detilazation": ("ground", "water", "overlay", "Водные детали"),
    "Trees_rocks": ("ground", "grass", "overlay", "Деревья и камни"),
    "Details": ("ground", "grass", "overlay", "Детали"),
    "Water_detilazation2": ("ground", "water", "overlay", "Водные детали · набор 2"),
}
WATER_COAST_GRASS_TILE_IDS = frozenset({81})
WATER_COAST_BRIDGE_TILE_IDS = frozenset({72, 73, 111, 112, 150, 151, 189, 190})


def _read_map(map_path):
    root = ET.parse(map_path).getroot()
    tilesets = []
    entries = root.findall("tileset")
    for index, entry in enumerate(entries):
        source = entry.get("source")
        definition_path = (map_path.parent / source).resolve() if source else None
        definition = ET.parse(definition_path).getroot() if definition_path else entry
        name = definition.get("name")
        if name not in SHEET_SETTINGS:
            continue
        image = definition.find("image")
        if image is None:
            continue
        image_path = (
            (definition_path.parent if definition_path else map_path.parent)
            / image.attrib["source"]
        ).resolve()
        if not image_path.is_file():
            image_path = (map_path.parent.parent / "PNG" / Path(image.attrib["source"]).name).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Grassland tilesheet is missing: {image_path}")
        first_gid = int(entry.attrib["firstgid"])
        end_gid = (
            int(entries[index + 1].attrib["firstgid"])
            if index + 1 < len(entries)
            else first_gid + int(definition.attrib["tilecount"])
        )
        tilesets.append({
            "name": name,
            "path": image_path,
            "first_gid": first_gid,
            "end_gid": end_gid,
            "columns": int(definition.attrib["columns"]),
            "tile_count": int(definition.attrib["tilecount"]),
            "animations": {
                int(tile.attrib["id"]): [
                    {
                        "tile_id": int(frame.attrib["tileid"]),
                        "duration": int(frame.attrib["duration"]),
                    }
                    for frame in tile.findall("./animation/frame")
                ]
                for tile in definition.findall("tile")
                if tile.find("animation") is not None
            },
        })
    return root, tilesets


def _used_tiles(root, tilesets):
    used = {sheet["name"]: set() for sheet in tilesets}
    for layer in root.iter("layer"):
        data = layer.find("data")
        if data is None:
            continue
        chunks = data.findall("chunk")
        sources = chunks or [data]
        for source in sources:
            if data.get("encoding") == "csv":
                gids = (int(value.strip()) for value in (source.text or "").split(",") if value.strip())
            else:
                gids = (int(tile.get("gid", "0")) for tile in source.findall("tile"))
            for value in gids:
                gid = value & GID_MASK
                if not gid:
                    continue
                for sheet in tilesets:
                    if sheet["first_gid"] <= gid < sheet["end_gid"]:
                        used[sheet["name"]].add(gid - sheet["first_gid"])
                        break
    for sheet in tilesets:
        for tile_id in tuple(used[sheet["name"]]):
            for frame in sheet["animations"].get(tile_id, []):
                used[sheet["name"]].add(frame["tile_id"])
    return used


def import_biome(source_root, output_dir=None):
    source_root = Path(source_root).resolve()
    map_path = source_root / "Tiled_files" / "Glades.tmx"
    if not map_path.is_file():
        raise FileNotFoundError(f"Glades.tmx was not found at {map_path}")
    output_dir = Path(output_dir or MAP_ASSETS / "grassland").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    root, tilesets = _read_map(map_path)
    used = _used_tiles(root, tilesets)
    catalog = []
    animations = {}
    overlay_keys = []
    for sheet in tilesets:
        name = sheet["name"]
        kind, category, layer, title = SHEET_SETTINGS[name]
        tile_categories = {}
        if name == "Water_coasts":
            tile_categories.update(dict.fromkeys(WATER_COAST_GRASS_TILE_IDS, "grass"))
            tile_categories.update(dict.fromkeys(WATER_COAST_BRIDGE_TILE_IDS, "bridge"))
            for tile_id, tile_category in tuple(tile_categories.items()):
                for frame in sheet["animations"].get(tile_id, []):
                    tile_categories[frame["tile_id"]] = tile_category
        image = Image.open(sheet["path"]).convert("RGBA")
        expected_width = sheet["columns"] * TILE_SIZE
        expected_height = (
            (sheet["tile_count"] + sheet["columns"] - 1) // sheet["columns"] * TILE_SIZE
        )
        if image.width < expected_width or image.height < expected_height:
            raise ValueError(f"{name} sheet is smaller than its declared Tiled dimensions")
        image.resize(
            (image.width * SCALE, image.height * SCALE),
            Image.Resampling.NEAREST,
        ).save(output_dir / f"{name}.png")
        for tile_id in sorted(used[name] | tile_categories.keys()):
            left = tile_id % sheet["columns"] * TILE_SIZE
            top = tile_id // sheet["columns"] * TILE_SIZE
            tile = image.crop((left, top, left + TILE_SIZE, top + TILE_SIZE))
            if tile.getchannel("A").getbbox() is None:
                continue
            key = f"grassland_{name.casefold()}_{tile_id:04d}"
            if layer == "overlay":
                overlay_keys.append(key)
            frames = sheet["animations"].get(tile_id, [])
            frame_ids = [frame["tile_id"] for frame in frames] if frames else [tile_id]
            catalog.append({
                "key": key,
                "kind": kind,
                "category": tile_categories.get(tile_id, category),
                "asset": f"grassland/{name}.png",
                "sheet": name,
                "tile_id": tile_id,
                "columns": sheet["columns"],
                "title": f"Равнины Craftpix · {title}",
                "display_name": f"Тайл {tile_id + 1:04d}",
                "layer": layer,
                "frame_tile_ids": frame_ids,
                "durations": [frame["duration"] for frame in frames],
                "used_in_example": tile_id in used[name],
                "palette_hidden": name in {"Trees_rocks", "Details", "Water_detilazation2"},
            })
            if frames:
                animations[key] = {
                    "frame": [TILE_SIZE * SCALE, TILE_SIZE * SCALE],
                    "frames": len(frames),
                    "cols": len(frames),
                    "durations": [frame["duration"] for frame in frames],
                    "tile_ids": frame_ids,
                }

    (output_dir / "catalog.json").write_text(
        json.dumps(
            {"items": catalog, "overlay_keys": overlay_keys},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (output_dir / "animations.json").write_text(
        json.dumps(animations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for license_name in ("license.txt", "License.txt"):
        license_path = source_root / license_name
        if license_path.is_file():
            shutil.copyfile(license_path, output_dir / "License.txt")
            break
    return len(catalog), len(animations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing the grassland biome")
    parser.add_argument("--output", type=Path, help="output directory (defaults to assets/map/grassland)")
    args = parser.parse_args()
    items, animations = import_biome(args.source, args.output)
    print(f"Imported {items} grassland tiles and {animations} animations.")


if __name__ == "__main__":
    main()
