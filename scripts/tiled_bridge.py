"""Command-line tools for preparing and converting Tiled maps."""
import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client import map_drafts
from core import map_catalog
from core.tiled_bridge import (
    MAPS_DIR,
    TILESETS_DIR,
    export_draft_to_tmx,
    import_tmx,
    write_tilesets,
)


DEFAULT_RASTERIZER = Path(r"E:\Tiled Map Editor\tmxrasterizer.exe")


def _catalog_for_biome(biome):
    catalog = map_catalog.catalog_definitions()
    if biome == "all":
        return catalog
    prefix = f"{biome}_"
    selected = [item for item in catalog if item["item_key"].startswith(prefix)]
    if not selected:
        raise ValueError(f"No map catalog items found for biome: {biome}")
    return selected


def create_project(directory, biome="desert", *, include_sample=True):
    directory = Path(directory).resolve()
    tilesets_dir = directory / "tilesets"
    maps_dir = directory / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    summary = write_tilesets(
        tilesets_dir,
        catalog=_catalog_for_biome(biome),
    )
    project = {
        "automappingRulesFile": "",
        "commands": [],
        "extensionsPath": "extensions",
        "version": "1.4",
        "propertyTypes": [],
        "folders": ["maps", "tilesets"],
    }
    project_path = directory / "game.tiled-project"
    project_path.write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sample_path = None
    if include_sample and biome == "desert":
        sample_path = create_desert_sample(maps_dir, tilesets_dir)
    return project_path, sample_path, summary


def create_desert_sample(maps_dir=MAPS_DIR, tilesets_dir=TILESETS_DIR):
    items = {
        item["item_key"]: item
        for item in _catalog_for_biome("desert")
    }
    specs = map_catalog.desert_tile_specs()
    ground_key = next(
        key for key, spec in specs.items()
        if key in items
        and items[key]["kind"] == "ground"
        and spec.get("layer") == "ground"
        and spec.get("tile_id") is not None
        and key.startswith("desert_ground_grass_")
        and not spec.get("palette_hidden")
    )
    grass_key = next(
        key for key, spec in specs.items()
        if key in items
        and items[key]["kind"] == "ground"
        and items[key]["category"] == "grass"
        and spec.get("layer") == "ground"
        and spec.get("tile_id") is not None
        and key.startswith("desert_ground_grass_")
        and key != ground_key
    )
    decorations = [
        key for key, item in items.items()
        if item["kind"] == "object"
        and item.get("category") == "bush"
        and specs.get(key, {}).get("representation") == "sprite"
    ]

    def decoration_size_score(key):
        image_path = ROOT / "assets" / "map" / Path(*items[key]["asset"].split("/"))
        with Image.open(image_path) as image:
            return abs(image.width - 32) + abs(image.height - 32)

    object_key = next(
        (
            key for key in decorations
            if items[key]["asset"].endswith("objects_015.png")
        ),
        min(decorations, key=decoration_size_score),
    )
    width, height = 24, 16
    cells = [
        {"layer": "ground", "x": x, "y": y, "key": ground_key}
        for y in range(height)
        for x in range(width)
    ]
    editor_layers = [[] for _ in range(8)]
    for x, y in ((5, 5), (6, 5), (5, 6), (17, 9), (18, 9), (18, 10)):
        editor_layers[1].append({
            "layer": "ground",
            "x": x,
            "y": y,
            "key": grass_key,
        })
    for x, y in ((4, 8), (12, 8), (19, 6)):
        editor_layers[5].append({
            "layer": "object",
            "x": x,
            "y": y,
            "key": object_key,
        })
    draft = {
        "name": "Desert Tiled test",
        "map_w": width,
        "map_h": height,
        "mode": "tower",
        "cells": cells,
        "editor_layers": editor_layers,
        "mobs": [],
        "spawns": [],
        "crystals": {},
        "harvest_enabled": False,
    }
    output = Path(maps_dir) / "desert_test.tmx"
    return export_draft_to_tmx(draft, output, tilesets_dir=tilesets_dir)


@dataclass(frozen=True)
class DraftImport:
    draft: dict
    created: bool
    warnings: list
    kept: tuple


def import_to_drafts(tmx, folder=map_drafts.DRAFTS_DIR, name=None):
    """Saves a TMX map as a game draft; a draft with the same name is updated in place.

    Mobs, spawns, crystals, the harvest flag and the mode come from the TMX only when it describes them,
    so importing a map redrawn in Tiled keeps what was added to the draft in the game editor.
    """
    folder = Path(folder)
    imported = import_tmx(tmx)
    draft = imported.draft
    name = str(name or draft["name"]).strip()
    existing = next(
        (item for item in map_drafts.list_drafts(folder) if item["name"] == name),
        None,
    )
    previous = map_drafts.load_draft(existing["id"], folder) if existing else {}

    def pick(field, default):
        if field in imported.explicit or not previous:
            return draft[field]
        return previous.get(field, default)

    saved = map_drafts.save_draft(
        name,
        draft["cells"],
        draft["map_w"],
        draft["map_h"],
        existing["id"] if existing else None,
        folder=folder,
        mode=pick("mode", None),
        mobs=pick("mobs", []),
        spawns=pick("spawns", []),
        crystals=pick("crystals", {}),
        harvest_enabled=pick("harvest_enabled", False),
        editor_layers=draft["editor_layers"],
    )
    kept = tuple(
        field for field in ("mobs", "spawns", "crystals")
        if previous.get(field) and field not in imported.explicit
    )
    return DraftImport(saved, existing is None, imported.warnings, kept)


def load_draft_for_export(reference, folder=map_drafts.DRAFTS_DIR):
    """A draft JSON file by path, or a draft of the drafts folder by id or name."""
    path = Path(reference)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    for item in map_drafts.list_drafts(Path(folder)):
        if reference in (item["id"], item["name"]):
            return map_drafts.load_draft(item["id"], Path(folder))
    raise ValueError(f"Draft not found: {reference}")


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    project = commands.add_parser("init", help="Create a Tiled project and a test map")
    project.add_argument("--directory", type=Path, default=ROOT / "tiled")
    project.add_argument(
        "--biome",
        choices=("desert", "grassland", "rocky", "winter", "undead", "all"),
        default="desert",
    )
    project.add_argument("--no-sample", action="store_true")

    export = commands.add_parser("export", help="Export a game draft to TMX")
    export.add_argument("draft", help="Draft name or id from the drafts folder, or a draft JSON file")
    export.add_argument("tmx", type=Path)
    export.add_argument("--folder", type=Path, default=map_drafts.DRAFTS_DIR)

    importer = commands.add_parser(
        "import",
        help="Import a TMX map into the map editor drafts (Ctrl+L in the editor)",
    )
    importer.add_argument("tmx", type=Path)
    importer.add_argument("--name", help="Draft name; defaults to the game_name map property or the file name")
    importer.add_argument("--folder", type=Path, default=map_drafts.DRAFTS_DIR)

    render = commands.add_parser("render", help="Render TMX to PNG using Tiled's rasterizer")
    render.add_argument("tmx", type=Path)
    render.add_argument("png", type=Path)
    render.add_argument("--rasterizer", type=Path, default=DEFAULT_RASTERIZER)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            project_path, sample_path, summary = create_project(
                args.directory,
                args.biome,
                include_sample=not args.no_sample,
            )
            print(f"Tiled project: {project_path}")
            if sample_path:
                print(f"Test map: {sample_path}")
            print(f"Tilesets: {len(summary['files'])}")
        elif args.command == "export":
            draft = load_draft_for_export(args.draft, args.folder)
            output = export_draft_to_tmx(draft, args.tmx)
            print(f"Exported: {output}")
        elif args.command == "import":
            result = import_to_drafts(args.tmx, args.folder, args.name)
            draft = result.draft
            action = "Created" if result.created else "Updated"
            print(f"{action} draft: {draft['name']} (id {draft['id']})")
            print(
                f"Map {draft['map_w']}x{draft['map_h']}, mode {draft['mode']}, "
                f"mobs: {len(draft['mobs'])}, spawns: {len(draft['spawns'])}"
            )
            if result.kept:
                print(f"Kept from the existing draft: {', '.join(result.kept)}")
            print(f"Folder: {args.folder}")
            print("Open it in the map editor: Ctrl+L")
            for warning in result.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
        else:
            args.png.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [str(args.rasterizer), str(args.tmx), str(args.png)],
                check=True,
            )
            print(f"Rendered: {args.png}")
        return 0
    except (
        OSError, ValueError, ElementTree.ParseError, map_drafts.DraftError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"tiled_bridge: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
