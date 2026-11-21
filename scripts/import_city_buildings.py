"""Import complete city buildings by composing visible layers from Craftpix Tiled demos."""
import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = PROJECT_ROOT / "godot_client" / "assets" / "base_tails" / "pack"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "map" / "city_buildings"
DEFAULT_RASTERIZER = Path(r"E:\Tiled Map Editor\tmxrasterizer.exe")
SOURCE_TILE_SIZE = 16
SCALE = 2
BUILDINGS = {
    "market": {
        "pack": "craftpix-net-587497-pixel-art-market-square-rpg-shop-and-npc-assets-pack",
        "map": Path("Tiled_files") / "Market_square.tmx",
        "layers": (
            "street", "walls_grass", "details", "Boxes_tables_hat", "Tent",
            "Stall1", "Stall", "Boxes", "Shadow", "boxes_carpet", "Table_corpet",
            "candle1", "candle2", "Ball", "Armor_top", "Rack", "Flag", "Barrel",
            "Walls_top", "NPC_street",
        ),
        "title": "Городской рынок",
    },
    "tavern": {
        "pack": "craftpix-net-666104-tavern-top-down-pixel-rpg-asset-pack",
        "map": Path("Tiled_files") / "Tavern_exterior.tmx",
        "layers": (
            "Walls", "cornice", "balcony", "balcony_border", "Roof", "attic",
            "sign_big", "ivy", "Boxes_small_sign", "tables1", "tables2",
        ),
        "title": "Таверна",
    },
    "smithy": {
        "pack": "craftpix-net-741016-pixel-blacksmith-house-interior-and-exterior-assets",
        "map": Path("Tiled_files") / "Blacksmith_house_exterior.tmx",
        "layers": (
            "House_walls", "roof", "Canopy_sign", "Boxes_carts", "Flags",
            "Table", "smoke",
        ),
        "title": "Кузница",
    },
    "glassblower": {
        "pack": "craftpix-net-692491-free-glassblowers-workshop-top-down-pixel-art-asset",
        "map": Path("Tiled_files") / "Exterior.tmx",
        "layers": (
            "Walls", "Windows_top", "Roof", "Roof_detail", "stovepipe",
            "Sign", "Tent", "Supplies", "Barrel", "cart",
        ),
        "title": "Мастерская стеклодува",
    },
    "herbalist": {
        "pack": "craftpix-net-742958-pixel-art-herbalists-hut-top-down-asset-pack",
        "map": Path("Tiled_files") / "Exterior.tmx",
        "layers": ("House",),
        "title": "Лавка травника",
    },
    "library": {
        "pack": "craftpix-net-845649-library-inventory-top-down-pixel-art-asset-pack",
        "map": Path("Tiled_files") / "Exterior.tmx",
        "layers": ("House",),
        "title": "Библиотека",
    },
    "mage_tower": {
        "pack": "craftpix-net-289481-mage-tower-top-down-pixel-art-asset-pack",
        "map": Path("Tiled_files") / "Exterior.tmx",
        "layers": ("Platform", "Tower"),
        "title": "Башня мага",
    },
    "guild": {
        "pack": "craftpix-net-189780-free-top-down-pixel-art-guild-hall-asset-pack",
        "map": Path("Tiled_files") / "Exterior.tmx",
        "layers": ("House", "Roof", "Sign", "Flags"),
        "title": "Гильдия",
    },
}


def _render_layers(map_path, output_path, layers, rasterizer):
    command = [str(rasterizer), "--no-smoothing"]
    for layer in layers:
        command.extend(("--show-layer", layer))
    command.extend((str(map_path), str(output_path)))
    subprocess.run(command, check=True, capture_output=True, text=True)
    return Image.open(output_path).convert("RGBA")


def _compose_building(map_path, layers, output_path, rasterizer):
    with tempfile.TemporaryDirectory(prefix="city-building-") as temp_dir:
        canvas = None
        for index, layer in enumerate(layers):
            image = _render_layers(
                map_path,
                Path(temp_dir) / f"layer_{index:02d}.png",
                (layer,),
                rasterizer,
            )
            if canvas is None:
                canvas = Image.new("RGBA", image.size)
            elif image.size != canvas.size:
                raise ValueError(f"Tiled layer size changed while rendering {map_path}")
            canvas.alpha_composite(image)

    if canvas is None:
        raise ValueError(f"No layers were selected for {map_path}")
    bounds = canvas.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"Selected layers contain no visible pixels: {map_path}")
    left = bounds[0] // SOURCE_TILE_SIZE * SOURCE_TILE_SIZE
    top = bounds[1] // SOURCE_TILE_SIZE * SOURCE_TILE_SIZE
    right = math.ceil(bounds[2] / SOURCE_TILE_SIZE) * SOURCE_TILE_SIZE
    bottom = math.ceil(bounds[3] / SOURCE_TILE_SIZE) * SOURCE_TILE_SIZE
    right = min(right, canvas.width)
    bottom = min(bottom, canvas.height)
    cropped = canvas.crop((left, top, right, bottom))
    scaled = cropped.resize(
        (cropped.width * SCALE, cropped.height * SCALE),
        Image.Resampling.NEAREST,
    )
    scaled.save(output_path)
    return {
        "footprint_w": cropped.width // SOURCE_TILE_SIZE,
        "footprint_h": cropped.height // SOURCE_TILE_SIZE,
    }


def import_buildings(packs_dir=PACKS_DIR, output_dir=OUTPUT_DIR, rasterizer=DEFAULT_RASTERIZER):
    packs_dir = Path(packs_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    items = []
    licenses_dir = output_dir / "licenses"
    licenses_dir.mkdir(exist_ok=True)

    for slug, details in BUILDINGS.items():
        pack_root = packs_dir / details["pack"]
        map_path = pack_root / details["map"]
        if not map_path.is_file():
            raise FileNotFoundError(f"City demo map is missing: {map_path}")
        asset_name = f"{slug}.png"
        dimensions = _compose_building(
            map_path,
            details["layers"],
            output_dir / asset_name,
            Path(rasterizer).resolve(),
        )
        items.append({
            "key": f"city_building_{slug}",
            "kind": "object",
            "category": "building",
            "asset": f"city_buildings/{asset_name}",
            "display_name": details["title"],
            "title": details["title"],
            "representation": "sprite",
            "footprint_w": dimensions["footprint_w"],
            "footprint_h": dimensions["footprint_h"],
            "blocks": True,
            "editor_layer": 6,
        })

        license_path = next(
            (path for path in (pack_root / "license.txt", pack_root / "License.txt") if path.is_file()),
            None,
        )
        if license_path is not None:
            shutil.copyfile(license_path, licenses_dir / f"{slug}.txt")

    (output_dir / "catalog.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs", type=Path, default=PACKS_DIR, help="directory containing Craftpix packs")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="output directory for imported sprites")
    parser.add_argument("--rasterizer", type=Path, default=DEFAULT_RASTERIZER)
    args = parser.parse_args()
    items = import_buildings(args.packs, args.output, args.rasterizer)
    for item in items:
        print(
            f"{item['display_name']}: {item['footprint_w']}x{item['footprint_h']} cells "
            f"({item['asset']})"
        )


if __name__ == "__main__":
    main()
