"""Постройки Колоды в её раскладке: редактор показывает их рамками и в карту не сохраняет.

Здания, ворота и кристалл задаёт код мира (kaloda/map_config.py). Сервер карт принимает только тайлы каталога,
поэтому постройку нельзя положить в черновик: она видна как ориентир для расстановки земли и мобов.
"""
from kaloda.map_config import (
    CARD_SHOP_BOUNDS,
    CITY_GATE_TILES,
    DUNGEON_ENTRANCE_BOUNDS,
    GUILD_BOUNDS,
    LIBRARY_BOUNDS,
    RESPAWN_CRYSTAL,
    SUPPLIES_SHOP_BOUNDS,
    TAVERN_BOUNDS,
    city_area_payload,
)


def _area(left, top, width, height):
    return [(x, y) for y in range(top, top + height) for x in range(left, left + width)]


def structures():
    """Постройки с клетками: [{"id", "name", "tiles": [(x, y), ...]}] в порядке показа."""
    crystal = (RESPAWN_CRYSTAL["tile_x"], RESPAWN_CRYSTAL["tile_y"], RESPAWN_CRYSTAL["tile_w"], RESPAWN_CRYSTAL["tile_h"])
    return [
        {"id": "city_walls", "name": "Городские стены", "tiles": [tuple(tile) for tile in city_area_payload()["wall_tiles"]]},
        {"id": "city_gate", "name": "Ворота города", "tiles": [tuple(tile) for tile in CITY_GATE_TILES]},
        {"id": "crystal_of_life", "name": "Кристалл возрождения", "tiles": _area(*crystal)},
        {"id": "guild", "name": "Гильдия", "tiles": _area(*GUILD_BOUNDS)},
        {"id": "supplies_shop", "name": "Магазин припасов", "tiles": _area(*SUPPLIES_SHOP_BOUNDS)},
        {"id": "card_shop", "name": "Магазин карт", "tiles": _area(*CARD_SHOP_BOUNDS)},
        {"id": "tavern", "name": "Таверна", "tiles": _area(*TAVERN_BOUNDS)},
        {"id": "library", "name": "Библиотека", "tiles": _area(*LIBRARY_BOUNDS)},
        {"id": "dungeon_entrance", "name": "Вход в подземелье", "tiles": _area(*DUNGEON_ENTRANCE_BOUNDS)},
    ]
