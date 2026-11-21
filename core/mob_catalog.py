"""Mobs available to Front Line waves from the Godot editor's LPC palette."""
import re
from pathlib import Path
from xml.etree import ElementTree

from core.npc_catalog import NPC_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LPC_ASSETS = PROJECT_ROOT / "godot_client" / "assets" / "base_tails" / "LPC"

_ACTION_SUFFIX = re.compile(
    r"(?i)(walk_attack|run_attack|idle|walk|run|attack|hurt|death|jump|flight|fly|move|swim)\d*$"
)
_DIRECTION_SUFFIX = re.compile(r"(?i)_?(front|back|left|right)$")
_GOBLIN_VARIANT = re.compile(r"(?i)^goblin([1-3])$")
_GOBLIN_ACTION = re.compile(
    r"(?i)^(idle|walk|run|attack|hurt|death|walk_attack|run_attack)\d?$"
)
_DISPLAY_PREFIXES = (
    ("slime_boss", "Босс-слайм"),
    ("vampires", "Вампир"),
    ("plant", "Растение"),
    ("golem", "Голем"),
    ("skeleton", "Скелет"),
    ("gnoll", "Гнолл"),
    ("beholder", "Бехолдер"),
    ("rat", "Крыса"),
    ("demon", "Демон"),
    ("imp", "Имп"),
    ("slime", "Слайм"),
    ("lich", "Лич"),
    ("zombie", "Зомби"),
    ("ent", "Энт"),
    ("mushroom", "Гриб"),
    ("ghost", "Призрак"),
    ("lizardman", "Ящеролюд"),
    ("orc", "Орк"),
    ("g", "Гоблин"),
)
_SPECIAL_PACKS = {"LPC imp", "LPC Imp 2"}
_EXCLUDED_PACKS = {"wolfs"}


def _sheet_info(path):
    if path.name.startswith("._"):
        return "", "", ""
    stem = path.stem
    if not stem.lower().endswith("_with_shadow"):
        return "", "", ""
    stem = stem[: -len("_with_shadow")].strip()
    if stem.lower().endswith("_animation"):
        stem = stem[: -len("_animation")]
    direction = ""
    direction_match = _DIRECTION_SUFFIX.search(stem)
    if direction_match is not None:
        direction = direction_match.group(1).lower()
        stem = stem[: direction_match.start()].strip()
    state = "animation"
    action = _ACTION_SUFFIX.search(stem)
    if action is not None:
        state = action.group(1).lower()
        stem = stem[: action.start()].rstrip("_- ").strip()
    return stem.lower(), state, direction


def _display_name(species_key):
    for prefix, label in _DISPLAY_PREFIXES:
        if not species_key.startswith(prefix):
            continue
        suffix = species_key[len(prefix) :].lstrip("_").strip()
        return f"{label} {suffix}".strip()
    return species_key.replace("_", " ").capitalize()


def _tiled_sheet_animations(image_path):
    """Read Tiled frame rectangles for one sheet using the pack's own metadata."""
    for metadata_path in sorted(
        list(image_path.parent.glob("*.tmx")) + list(image_path.parent.glob("*.tsx"))
    ):
        try:
            root = ElementTree.parse(metadata_path).getroot()
        except ElementTree.ParseError:
            continue
        for tileset in root.iter("tileset"):
            image = tileset.find("image")
            if image is None or Path(image.get("source", "")).name.casefold() != image_path.name.casefold():
                continue
            columns = int(tileset.get("columns", 0))
            tile_width = int(tileset.get("tilewidth", 0))
            tile_height = int(tileset.get("tileheight", 0))
            if columns <= 0 or tile_width <= 0 or tile_height <= 0:
                continue
            image_width = int(image.get("width", 0))
            image_height = int(image.get("height", 0))
            rows = image_height // tile_height
            animations = {}
            for tile in tileset.findall("tile"):
                frames = [
                    {
                        "tile_id": int(frame.get("tileid", -1)),
                        "duration": int(frame.get("duration", 0)),
                    }
                    for frame in tile.findall("./animation/frame")
                ]
                if frames:
                    animations[int(tile.get("id", -1))] = frames
            return columns, rows, tile_width, tile_height, image_width, animations
    return 0, 0, 0, 0, 0, {}


def _animation_matches(animations, candidate_id, base_id, offset):
    candidate_frames = animations.get(candidate_id, [])
    base_frames = animations.get(base_id, [])
    return bool(candidate_frames) and len(candidate_frames) == len(base_frames) and all(
        candidate["tile_id"] + offset == base["tile_id"]
        and candidate["duration"] == base["duration"]
        for candidate, base in zip(candidate_frames, base_frames)
    )


def _tiled_clips(image_path):
    columns, rows, tile_width, tile_height, image_width, animations = _tiled_sheet_animations(image_path)
    if not animations or columns <= 0:
        return []
    image_height = rows * tile_height
    tile_ids = sorted(animations)
    clips = []
    for tile_id in tile_ids:
        frames = animations[tile_id]
        stride = 1
        for previous, frame in zip(frames, frames[1:]):
            step = frame["tile_id"] - previous["tile_id"]
            if 0 < step < columns:
                stride = min(step, 8)
                break
        frame_width = stride
        for frame in frames:
            frame_id = frame["tile_id"]
            frame_width = min(frame_width, columns - frame_id % columns)
        frame_height = stride
        origin_x, origin_y = tile_id % columns, tile_id // columns
        if origin_x + frame_width > columns or origin_y + frame_height > rows:
            continue
        if origin_x > 0 and _animation_matches(animations, tile_id - 1, tile_id, 1):
            continue
        first_row = min(
            (animation_id // columns for animation_id in animations if animation_id % columns == origin_x),
            default=0,
        )
        if (origin_y - first_row) % frame_height:
            continue
        rects = []
        valid = True
        for frame in frames:
            frame_id = frame["tile_id"]
            frame_x, frame_y = frame_id % columns, frame_id // columns
            rect = (
                frame_x * tile_width,
                frame_y * tile_height,
                frame_width * tile_width,
                frame_height * tile_height,
            )
            if rect[0] + rect[2] > image_width or rect[1] + rect[3] > image_height:
                valid = False
                break
            rects.append(rect)
        if valid and rects:
            clips.append({
                "row": origin_y // frame_height,
                "origin": tile_id,
                "frame_size": (frame_width * tile_width, frame_height * tile_height),
                "rects": rects,
            })
    return clips


def _palette_sheet_records(pack):
    records = {}
    preferred = {}
    for path in sorted(pack.rglob("*.png")):
        species, state, direction = _sheet_info(path)
        if not species:
            continue
        key = (species, state, path.name.casefold())
        has_metadata = any(path.parent.glob("*.tmx")) or any(path.parent.glob("*.tsx"))
        priority = (int(has_metadata), int("tiled" in str(path.parent).casefold()))
        if key not in preferred or priority > preferred[key][0]:
            preferred[key] = (priority, path, direction)
    for (species, state, _filename), (_priority, path, direction) in preferred.items():
        records.setdefault(species, {}).setdefault(state, []).append({
            "path": path,
            "direction": direction,
        })
    for states in records.values():
        for entries in states.values():
            entries.sort(key=lambda entry: (entry["direction"], str(entry["path"]).casefold()))
    return records


def _palette_mobs():
    if not LPC_ASSETS.is_dir():
        return ()
    result = []
    pack_folders = sorted(
        (path for path in LPC_ASSETS.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    )
    for pack in pack_folders:
        if pack.name.startswith(".") or pack.name in _EXCLUDED_PACKS | _SPECIAL_PACKS | {"__MACOSX"}:
            continue
        if pack.name == "goblin sprite-pack":
            sheets_by_species = {}
            for path in sorted(pack.rglob("*.png")):
                if path.name.startswith("._") or not path.name.lower().endswith("_with_shadow.png"):
                    continue
                variant_match = _GOBLIN_VARIANT.search(path.parent.parent.name)
                action = path.stem[: -len("_with_shadow")]
                action_match = _GOBLIN_ACTION.fullmatch(action)
                if variant_match is None or action_match is None:
                    continue
                species = f"g{variant_match.group(1)}"
                state = action_match.group(1).lower()
                sheets_by_species.setdefault(species, {}).setdefault(state, []).append({
                    "path": path,
                    "direction": "",
                })
        else:
            sheets_by_species = _palette_sheet_records(pack)
        for species_key in sorted(sheets_by_species):
            sheet_paths = sheets_by_species[species_key]
            for entries in sheet_paths.values():
                entries.sort(key=lambda entry: (entry["direction"], str(entry["path"]).casefold()))
            result.append({
                "key": f"mob|{pack.name}|{species_key}",
                "name": _display_name(species_key),
                "pack_folder": pack.name,
                "species_key": species_key,
                "pack_path": pack,
                "sheet_paths": sheet_paths,
            })
    return tuple(result)


PALETTE_MOB_CATALOG = _palette_mobs()
MOB_CATALOG = tuple(dict(mob) for mob in NPC_CATALOG) + PALETTE_MOB_CATALOG
MOB_KEYS = frozenset(mob["key"] for mob in MOB_CATALOG)
PALETTE_MOB_BY_KEY = {mob["key"]: mob for mob in PALETTE_MOB_CATALOG}
_ANIMATION_CACHE = {}


def mob_catalog():
    """Return copyable metadata for every wave mob shown in the editor palette."""
    return [dict(mob) for mob in MOB_CATALOG]


def palette_mob(key):
    """Return the source-pack record for a palette mob, or None for a non-palette key."""
    return PALETTE_MOB_BY_KEY.get(key)


def palette_mob_animations(key, action):
    """Return parsed Tiled animation clips for a palette mob action."""
    cache_key = (key, action)
    if cache_key in _ANIMATION_CACHE:
        return _ANIMATION_CACHE[cache_key]
    mob = palette_mob(key)
    if mob is None:
        _ANIMATION_CACHE[cache_key] = []
        return []
    candidates = {
        "walk": ("walk", "run", "animation", "idle", "death"),
        "run": ("run", "walk", "animation", "idle", "death"),
        "idle": ("idle", "animation", "walk", "run", "death"),
        "attack": ("attack", "walk_attack", "run_attack", "animation", "walk", "run", "death"),
        "death": ("death",),
    }.get(action, (action, "animation", "idle"))
    result = []
    for state in candidates:
        for entry in mob["sheet_paths"].get(state, []):
            clips = _tiled_clips(entry["path"])
            if clips:
                result.append({
                    "path": entry["path"],
                    "direction": entry["direction"],
                    "clips": clips,
                })
        if result:
            break
    _ANIMATION_CACHE[cache_key] = result
    return result
