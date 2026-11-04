"""Рельеф карты первого мира Колоды: сервер отдаёт его клиенту, клиент только рисует."""

from kaloda.map_config import (
    MAP_HEIGHT_TILES,
    MAP_VERSION,
    MAP_WIDTH_TILES,
    RESPAWN_CRYSTAL,
    SHOW_OUTSIDE_CITY_LOCATIONS,
    TILE_SIZE,
    city_area_payload,
    forest_area_payload,
    graveyard_area_payload,
    library_area_payload,
)


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for i in range(len(polygon)):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def terrain_payload():
    payload = {
        "map_version": MAP_VERSION,
        "tile_size": TILE_SIZE,
        "width_tiles": MAP_WIDTH_TILES,
        "height_tiles": MAP_HEIGHT_TILES,
        "obstacles": [],
        "objects": [dict(RESPAWN_CRYSTAL)],
        "city_area": city_area_payload(),
        "library_area": library_area_payload(),
        "roads": {"routes": [], "tiles": [], "travel_seconds": 0},
    }
    if SHOW_OUTSIDE_CITY_LOCATIONS:
        payload["forest_area"] = forest_area_payload()
        payload["graveyard_area"] = graveyard_area_payload()
    return payload
