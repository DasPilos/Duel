#!/usr/bin/env python3
"""Render a Tiled biome's original tile animations as a 10-second Godot OGV."""

import argparse
import base64
import math
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIOME_MAPS = {
    "grassland": Path(
        "assets/base_tails/Biome/"
        "craftpix-net-189510-grassland-top-down-tileset-pixel-art/"
        "Tiled_files/Glades.tmx"
    ),
    "winter": Path("assets/base_tails/Biome/winter/Tiled_files/Winter.tmx"),
    "desert": Path("assets/base_tails/Biome/desert/Tiled_files/Desert.tmx"),
    "swamp": Path("assets/base_tails/Biome/swamp/Tiled_files/Swamp.tmx"),
    "rocky": Path(
        "assets/base_tails/Biome/"
        "rocky-top-down-tileset-pixel-art-for-rpg/Tiled_files/Rocky_area.tmx"
    ),
    "undead": Path("assets/base_tails/Biome/undeadt/Tiled_files/Undead_land.tmx"),
    "cursed": Path("assets/base_tails/Biome/cursed/Tiled_files/Cursed_land.tmx"),
}
OUTPUT_DIR = PROJECT_ROOT / "assets/ui/title_biomes"
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_SECONDS = 10
VIDEO_FPS = 20
ANIMATION_FRAME_MS = 150
TILE_FLIP_MASK = 0xE0000000
TILE_GID_MASK = 0x1FFFFFFF


def _read_animations(map_path: Path) -> dict[int, list[tuple[int, int]]]:
    root = ElementTree.parse(map_path).getroot()
    animations: dict[int, list[tuple[int, int]]] = {}
    for tileset_node in root.findall("tileset"):
        first_gid = int(tileset_node.get("firstgid", "0"))
        source = tileset_node.get("source")
        if source:
            tileset_path = (map_path.parent / source).resolve()
            tileset = ElementTree.parse(tileset_path).getroot()
        else:
            tileset = tileset_node

        for tile in tileset.findall("tile"):
            animation = tile.find("animation")
            if animation is None:
                continue
            frames = [
                (first_gid + int(frame.get("tileid", "0")), int(frame.get("duration", "0")))
                for frame in animation.findall("frame")
            ]
            if any(duration <= 0 for _, duration in frames):
                raise ValueError(f"Animation has a non-positive frame duration in {map_path}")
            animations[first_gid + int(tile.get("id", "0"))] = frames

    if not animations:
        raise ValueError(f"No animated tiles were found in {map_path}")
    return animations


def _frame_gid(frames: list[tuple[int, int]], elapsed_ms: int) -> int:
    cycle_ms = sum(duration for _, duration in frames)
    position = elapsed_ms % cycle_ms
    for gid, duration in frames:
        if position < duration:
            return gid
        position -= duration
    raise AssertionError("Animation frame duration accounting failed")


def _visible_scene_bounds(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = alpha.size
    pixels = alpha.load()
    column_threshold = max(1, math.ceil(height * 0.01))
    row_threshold = max(1, math.ceil(width * 0.01))
    columns = [0] * width
    rows = [0] * height
    for y in range(height):
        for x in range(width):
            if pixels[x, y] > 0:
                columns[x] += 1
                rows[y] += 1

    active_columns = [x for x, count in enumerate(columns) if count >= column_threshold]
    active_rows = [y for y, count in enumerate(rows) if count >= row_threshold]
    if not active_columns or not active_rows:
        return None
    return (
        active_columns[0],
        active_rows[0],
        active_columns[-1] + 1,
        active_rows[-1] + 1,
    )


def _replace_tile_gids(payload: str, animations: dict[int, list[tuple[int, int]]], elapsed_ms: int) -> str:
    def replace(match: re.Match[str]) -> str:
        value = int(match.group(0))
        gid = value & TILE_GID_MASK
        frames = animations.get(gid)
        if frames is None:
            return match.group(0)
        return str((value & TILE_FLIP_MASK) | _frame_gid(frames, elapsed_ms))

    return re.sub(r"(?<!\d)\d+(?!\d)", replace, payload)


def _replace_binary_gids(
    payload: str,
    compression: str,
    animations: dict[int, list[tuple[int, int]]],
    elapsed_ms: int,
) -> str:
    encoded = "".join(payload.split())
    if not encoded:
        return payload
    raw = base64.b64decode(encoded)
    if compression == "zlib":
        raw = zlib.decompress(raw)
    elif compression:
        raise ValueError(f"Unsupported Tiled compression: {compression}")
    if len(raw) % 4:
        raise ValueError("Tiled tile data is not a sequence of 32-bit GIDs")
    gids = struct.unpack(f"<{len(raw) // 4}I", raw)
    updated = bytearray()
    for value in gids:
        gid = value & TILE_GID_MASK
        frames = animations.get(gid)
        if frames is not None:
            value = (value & TILE_FLIP_MASK) | _frame_gid(frames, elapsed_ms)
        updated.extend(struct.pack("<I", value))
    if compression == "zlib":
        updated = bytearray(zlib.compress(updated))
    return base64.b64encode(updated).decode("ascii")


def _replace_layer_data(map_text: str, animations: dict[int, list[tuple[int, int]]], elapsed_ms: int) -> str:
    def replace_data(match: re.Match[str]) -> str:
        opening, body, closing = match.groups()
        attributes = dict(re.findall(r'([\w:-]+)="([^"]*)"', opening))
        encoding = attributes.get("encoding")

        if encoding == "csv":
            def replace_chunk(chunk: re.Match[str]) -> str:
                chunk_open, chunk_body, chunk_close = chunk.groups()
                return chunk_open + _replace_tile_gids(chunk_body, animations, elapsed_ms) + chunk_close

            updated_body, chunk_count = re.subn(
                r"(<chunk\b[^>]*>)(.*?)(</chunk>)",
                replace_chunk,
                body,
                flags=re.DOTALL,
            )
            if chunk_count == 0:
                updated_body = _replace_tile_gids(body, animations, elapsed_ms)
            return opening + updated_body + closing

        if encoding == "base64":
            compression = attributes.get("compression", "")

            def replace_binary(chunk: re.Match[str]) -> str:
                chunk_open, chunk_body, chunk_close = chunk.groups()
                updated = _replace_binary_gids(chunk_body, compression, animations, elapsed_ms)
                return chunk_open + updated + chunk_close

            updated_body, chunk_count = re.subn(
                r"(<chunk\b[^>]*>)(.*?)(</chunk>)",
                replace_binary,
                body,
                flags=re.DOTALL,
            )
            if chunk_count == 0:
                updated_body = _replace_binary_gids(body, compression, animations, elapsed_ms)
            return opening + updated_body + closing

        return match.group(0)

    def replace_layer(layer: re.Match[str]) -> str:
        return re.sub(
            r"(<data\b[^>]*>)(.*?)(</data>)",
            replace_data,
            layer.group(0),
            flags=re.DOTALL,
        )

    return re.sub(r"<layer\b[^>]*>.*?</layer>", replace_layer, map_text, flags=re.DOTALL)


def _resolve_ffmpeg(explicit_path: Path | None) -> str:
    if explicit_path is not None:
        if not explicit_path.is_file():
            raise FileNotFoundError(f"FFmpeg executable not found: {explicit_path}")
        return str(explicit_path)
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise FileNotFoundError(
            "FFmpeg is required. Install it and add it to PATH, or pass --ffmpeg."
        ) from error
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_biome(biome: str, rasterizer: Path, ffmpeg: Path | None) -> Path:
    map_path = PROJECT_ROOT / BIOME_MAPS[biome]
    if not map_path.is_file():
        raise FileNotFoundError(f"Tiled map not found: {map_path}")
    if not rasterizer.is_file():
        raise FileNotFoundError(f"Tiled rasterizer not found: {rasterizer}")

    ffmpeg_exe = _resolve_ffmpeg(ffmpeg)
    animations = _read_animations(map_path)
    output_path = OUTPUT_DIR / f"{biome}.ogv"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_map = map_path.read_text(encoding="utf-8-sig")
    total_frames = VIDEO_SECONDS * VIDEO_FPS
    frames_per_animation_step = VIDEO_FPS * ANIMATION_FRAME_MS // 1000
    unique_phases = math.ceil(total_frames / frames_per_animation_step)

    with tempfile.TemporaryDirectory(prefix="title-biome-") as work_dir:
        work = Path(work_dir)
        render_dir = work / "rendered"
        encode_dir = work / "encoded"
        render_dir.mkdir()
        encode_dir.mkdir()
        reference_bounds = None

        for frame_index in range(unique_phases):
            elapsed_ms = frame_index * ANIMATION_FRAME_MS
            frame_map = map_path.parent / f".{biome}_title_{frame_index}.tmx"
            frame_render = render_dir / f"source_{frame_index:03d}.png"
            try:
                frame_map.write_text(
                    _replace_layer_data(raw_map, animations, elapsed_ms),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [str(rasterizer), str(frame_map), str(frame_render)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Tiled rendering failed for {biome} at {elapsed_ms} ms: "
                        f"{result.stderr.strip() or result.stdout.strip()}"
                    )
                with Image.open(frame_render) as source:
                    image = source.convert("RGBA")
                if reference_bounds is None:
                    reference_bounds = _visible_scene_bounds(image.getchannel("A"))
                    if reference_bounds is None:
                        raise ValueError(f"The Tiled map rendered no visible pixels: {map_path}")
                image = image.crop(reference_bounds)
                image = ImageOps.fit(
                    image,
                    (VIDEO_WIDTH, VIDEO_HEIGHT),
                    method=Image.Resampling.NEAREST,
                    centering=(0.5, 0.5),
                )
                image.save(render_dir / f"phase_{frame_index:03d}.png")
                if frame_index % 10 == 0:
                    print(
                        f"{biome}: rendered authored animation phase "
                        f"{frame_index + 1}/{unique_phases}"
                    )
            finally:
                frame_map.unlink(missing_ok=True)

        for frame_index in range(total_frames):
            phase_index = frame_index // frames_per_animation_step
            source = render_dir / f"phase_{phase_index:03d}.png"
            shutil.copyfile(source, encode_dir / f"frame_{frame_index:04d}.png")

        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(VIDEO_FPS),
                "-i",
                str(encode_dir / "frame_%04d.png"),
                "-t",
                str(VIDEO_SECONDS),
                "-an",
                "-c:v",
                "libtheora",
                "-q:v",
                "7",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg encoding failed: {result.stderr.strip()}")

    print(f"Created {output_path} ({output_path.stat().st_size:,} bytes)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--biome",
        choices=["all", *sorted(BIOME_MAPS)],
        default="grassland",
    )
    parser.add_argument(
        "--rasterizer",
        type=Path,
        default=Path("tmxrasterizer.exe"),
        help="Path to Tiled's tmxrasterizer.exe",
    )
    parser.add_argument("--ffmpeg", type=Path, help="Path to FFmpeg; can also be found on PATH")
    args = parser.parse_args()
    ffmpeg = args.ffmpeg.resolve() if args.ffmpeg else None
    biomes = BIOME_MAPS if args.biome == "all" else {args.biome: BIOME_MAPS[args.biome]}
    for biome in biomes:
        render_biome(biome, args.rasterizer.resolve(), ffmpeg)


if __name__ == "__main__":
    main()
