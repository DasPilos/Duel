# Тайлы увеличены в 1.5 раза (было 32 px); все пиксельные координаты выводятся из тайлов.
TILE_SIZE = 48
MAP_WIDTH_TILES = 128
MAP_HEIGHT_TILES = 256
MAP_VERSION = 5
SHOW_OUTSIDE_CITY_LOCATIONS = False


def tile_center(tile_x, tile_y):
    return [tile_x * TILE_SIZE + TILE_SIZE // 2, tile_y * TILE_SIZE + TILE_SIZE // 2]


_CRYSTAL_TILE = (11, 33, 3, 3)
RESPAWN_CRYSTAL = {
    "id": "crystal_of_life",
    "name": "Кристалл возрождения",
    "type": "Кристалл возрождения (3x3 тайла)",
    "tile_x": _CRYSTAL_TILE[0],
    "tile_y": _CRYSTAL_TILE[1],
    "tile_w": _CRYSTAL_TILE[2],
    "tile_h": _CRYSTAL_TILE[3],
    "x": tile_center(12, 34)[0],
    "y": tile_center(12, 34)[1],
    "radius": TILE_SIZE * 3 // 2,
    "entrance_tile": [12, 36],
    "approach_pos": tile_center(12, 36),
    "desc": "Кристалл возрождения. Восстанавливает здоровье героя.",
    "icon": "💎",
    "solid_rects": [[
        _CRYSTAL_TILE[0] * TILE_SIZE,
        _CRYSTAL_TILE[1] * TILE_SIZE,
        _CRYSTAL_TILE[2] * TILE_SIZE,
        _CRYSTAL_TILE[3] * TILE_SIZE,
    ]],
}

# Кобольд в лесу; после поражения возрождается через KOBOLD_RESPAWN_SECONDS.
KOBOLD_SPAWN_TILE = (54, 12)
KOBOLD_RESPAWN_SECONDS = 60

# Лагерь кобольдов (3 врага в одном бою на арене): центр на тайле [62, 18], занимает 3x3 тайла.
KOBOLD_CAMP_TILE = (62, 18)
KOBOLD_CAMP_SIZE = 3

# Второй лагерь кобольдов в лесу: в бою на стороне игрока появляется союзник-лучник Ельпачино Фред.
KOBOLD_CAMP2_TILE = (46, 22)

ANCIENT_ENT_TILE = (42, 6)

# Гильдия искателей приключений внутри города: тайлы X 19..23, Y 26..28.
GUILD_BOUNDS = (19, 26, 5, 3)

# Магазин припасов внутри города: тайлы X 14..18, Y 26..28.
SUPPLIES_SHOP_BOUNDS = (14, 26, 5, 3)
CARD_SHOP_BOUNDS = (9, 26, 5, 3)

# Таверна внутри города: тайлы X 4..8, Y 26..28. Вход ведёт на экран таверны,
# а при выходе из неё герой появляется на улице перед дверью.
TAVERN_BOUNDS = (4, 26, 5, 3)
TAVERN_EXIT_POS = tuple(tile_center(6, 29))

# Библиотека внутри города: тайлы X 19..23, Y 40..42.
LIBRARY_BOUNDS = (19, 40, 5, 3)

# Кладбище: тайлы X 25..57, Y 43..67.
GRAVEYARD_BOUNDS = (25, 43, 33, 25)
DUNGEON_ENTRANCE_BOUNDS = (25, 43, 3, 4)
DUNGEON_ROOM_ORIGIN = (64, 34)
DUNGEON_ROOM_SIZE = (14, 10)


def is_guild_tile(tile_x, tile_y, bounds=GUILD_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_supplies_shop_tile(tile_x, tile_y, bounds=SUPPLIES_SHOP_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_card_shop_tile(tile_x, tile_y, bounds=CARD_SHOP_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_tavern_tile(tile_x, tile_y, bounds=TAVERN_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_library_tile(tile_x, tile_y, bounds=LIBRARY_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_graveyard_tile(tile_x, tile_y, bounds=GRAVEYARD_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def is_dungeon_entrance_tile(tile_x, tile_y, bounds=DUNGEON_ENTRANCE_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def library_area_payload():
    return {"id": "library", "name": "Библиотека", "bounds": list(LIBRARY_BOUNDS)}


def graveyard_area_payload():
    return {"id": "graveyard", "name": "Кладбище", "bounds": list(GRAVEYARD_BOUNDS)}


# Городские стены: угловые тайлы [0, 25], [24, 25], [24, 43], [0, 43]; центр [12, 34] занимает кристалл.
# Проход шириной 3 тайла — в восточной стене напротив кристалла, в сторону карты.
CITY_WALL_BOUNDS = (0, 25, 25, 19)
CITY_GATE_TILES = ((24, 33), (24, 34), (24, 35))

# Лес: тайлы X 38..73, Y 2..29.
FOREST_BOUNDS = (38, 2, 36, 28)


def is_forest_tile(tile_x, tile_y, bounds=FOREST_BOUNDS):
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def forest_area_payload():
    return {"id": "forest_1", "name": "Лес", "bounds": list(FOREST_BOUNDS)}


def _city_wall_tiles():
    left, top, width, height = CITY_WALL_BOUNDS
    right, bottom = left + width - 1, top + height - 1
    gates = set(CITY_GATE_TILES)
    return [
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if (x in (left, right) or y in (top, bottom)) and (x, y) not in gates
    ]


def _merge_wall_rects(tiles):
    """Соседние тайлы стены сливаются в горизонтальные/вертикальные отрезки для коллизий."""
    remaining = set(tiles)
    rects = []
    for x, y in sorted(tiles, key=lambda tile: (tile[1], tile[0])):
        length = 0
        while (x + length, y) in remaining:
            length += 1
        if length > 1:
            remaining.difference_update((x + i, y) for i in range(length))
            rects.append([x * TILE_SIZE, y * TILE_SIZE, length * TILE_SIZE, TILE_SIZE])
    for x, y in sorted(remaining):
        if (x, y) not in remaining:
            continue
        length = 0
        while (x, y + length) in remaining:
            length += 1
        remaining.difference_update((x, y + i) for i in range(length))
        rects.append([x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, length * TILE_SIZE])
    return rects


def is_city_tile(tile_x, tile_y, bounds=CITY_WALL_BOUNDS):
    """Всё, что внутри городских стен (включая стены и проход), считается городом."""
    left, top, width, height = bounds
    return left <= tile_x < left + width and top <= tile_y < top + height


def city_area_payload():
    wall_tiles = _city_wall_tiles()
    return {
        "id": "city_walls",
        "name": "Город",
        "bounds": list(CITY_WALL_BOUNDS),
        "wall_tiles": [list(tile) for tile in wall_tiles],
        "gate_tiles": [list(tile) for tile in CITY_GATE_TILES],
        "solid_rects": _merge_wall_rects(wall_tiles),
    }
