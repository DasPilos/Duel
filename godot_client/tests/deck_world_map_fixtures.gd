extends RefCounted

# Рельеф для проверок карты мира. Форма совпадает с ответом GET /api/deck/map/terrain:
# неопубликованная карта — deck/world_map.py terrain_payload(), опубликованная — deck/server/map_editor.py published_terrain_payload().


static func procedural_terrain() -> Dictionary:
	var walls: Array = []
	for y in range(25, 44):
		for x in range(0, 25):
			var edge := x == 0 or x == 24 or y == 25 or y == 43
			var gate := x == 24 and y >= 33 and y <= 35
			if edge and not gate:
				walls.append([x, y])
	return {
		"map_version": 5,
		"tile_size": 48,
		"width_tiles": 128,
		"height_tiles": 256,
		"obstacles": [],
		"objects": [{
			"id": "crystal_of_life",
			"name": "Кристалл возрождения",
			"tile_x": 11,
			"tile_y": 33,
			"tile_w": 3,
			"tile_h": 3,
		}],
		"city_area": {
			"id": "city_walls",
			"name": "Город",
			"bounds": [0, 25, 25, 19],
			"wall_tiles": walls,
			"gate_tiles": [[24, 33], [24, 34], [24, 35]],
			"solid_rects": [],
		},
		"library_area": {"id": "library", "name": "Библиотека", "bounds": [19, 40, 5, 3]},
		"roads": {"routes": [], "tiles": [], "travel_seconds": 0},
	}


# Маленькая карта 24x20: лес и сухой лес, озеро с мостом, горы и непроходимые тайлы, дорога, ягоды, пол, пни и брёвна.
static func published_terrain() -> Dictionary:
	var water := _block(12, 2, 5, 5, [Vector2i(14, 2), Vector2i(14, 3), Vector2i(14, 4), Vector2i(14, 5), Vector2i(14, 6)])
	var mountain := _block(2, 11, 4, 4)
	var forest := _block(1, 1, 7, 6, [Vector2i(4, 3)])
	var dry := _block(8, 1, 2, 2)
	# Деревья и сухой лес блокируют ход, поэтому сервер кладёт их и в impassable.
	var impassable := mountain.duplicate()
	impassable.append_array(_block(8, 12, 1, 3))
	impassable.append_array(forest)
	impassable.append_array(dry)
	return {
		"map_version": 5,
		"tile_size": 48,
		"width_tiles": 24,
		"height_tiles": 20,
		"obstacles": [],
		"objects": [],
		"city_area": null,
		"library_area": null,
		"roads": {"routes": [], "tiles": [], "travel_seconds": 0},
		"published": {"name": "Тест", "mode": "deck", "published_at": 1.0},
		"tiles": {
			"forest": forest,
			"water": water,
			"dry": dry,
			"paths": _block(0, 9, 24, 1),
			"mountain": mountain,
			"impassable": impassable,
			"berry": _block(18, 10, 3, 2),
			"floor": _block(20, 15, 3, 3),
		},
		"partial": [],
		"props": [
			{"type": "stump", "tiles": [[10, 15]]},
			{"type": "log", "tiles": [[11, 16], [12, 16]]},
		],
		"bridges": [{"tiles": [[14, 2], [14, 3], [14, 4], [14, 5], [14, 6]]}],
	}


static func _block(left: int, top: int, width: int, height: int, skip: Array = []) -> Array:
	var tiles: Array = []
	for y in range(top, top + height):
		for x in range(left, left + width):
			if not skip.has(Vector2i(x, y)):
				tiles.append([x, y])
	return tiles
