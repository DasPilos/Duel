"""Sprite-sheet frame layouts for animals used by the map editor and live world."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AnimalSheet:
    asset: str
    frame_size: int
    columns: int
    frames: int
    walking_rows: tuple[int, int, int, int]
    idle_rows: tuple[int, int, int, int]


ANIMAL_SHEETS = {
    "buffalo": (64, 6, 6),
    "buffalo_cub": (64, 6, 6),
    "cat": (32, 8, 6),
    "colt": (32, 6, 6),
    "dog": (32, 6, 6),
    "donkey": (64, 6, 6),
    "drake": (32, 6, 6),
    "duck": (32, 6, 6),
    "duckling": (32, 6, 6),
}

WATERFOWL_SHEETS = {
    f"{name}_water": (32, 6, 6)
    for name in ("duck", "drake", "duckling")
}


def animal_sheet(key: str) -> AnimalSheet | None:
    """Return the source sheet and direction rows for an animal catalog key."""
    name = key.removeprefix("animal_")
    if name in WATERFOWL_SHEETS:
        species = name.removesuffix("_water")
        frame_size, columns, frames = WATERFOWL_SHEETS[name]
        return AnimalSheet(
            species, frame_size, columns, frames,
            (8, 9, 10, 11), (12, 13, 14, 15),
        )
    layout = ANIMAL_SHEETS.get(name)
    if layout is None:
        return None
    frame_size, columns, frames = layout
    return AnimalSheet(name, frame_size, columns, frames, (0, 1, 2, 3), (4, 5, 6, 7))


def animal_facing_index(angle: float) -> int:
    """Map atan2(dy, dx) to sheet rows ordered down, up, left, right."""
    dx, dy = math.cos(angle), math.sin(angle)
    if abs(dx) >= abs(dy):
        return 3 if dx >= 0 else 2
    return 0 if dy >= 0 else 1
