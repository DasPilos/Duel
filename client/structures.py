"""Перевод строений из ответа сервера (списки) в удобный для отрисовки вид (pygame.Rect, кортежи)."""

import pygame

_POINT_KEYS = ("entrance_tile", "approach_pos")


def hydrate_structure(data):
    obj = dict(data)
    for key in _POINT_KEYS:
        if obj.get(key) is not None:
            obj[key] = tuple(obj[key])
    if "solid_rects" in obj:
        obj["solid_rects"] = [pygame.Rect(rect) for rect in obj["solid_rects"]]
    if "entrances" in obj:
        obj["entrances"] = [
            {**entrance, "tiles": [tuple(tile) for tile in entrance.get("tiles", [])],
             "approach_pos": tuple(entrance["approach_pos"]) if entrance.get("approach_pos") else None}
            for entrance in obj["entrances"]
        ]
    return obj


def hydrate_structures(items):
    return [hydrate_structure(item) for item in items]
