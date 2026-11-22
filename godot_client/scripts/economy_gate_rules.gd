extends RefCounted
# Ворота Радбурга: проёмы между стенами, зоны наведения и точки перехода на карту мира.
# Сервер Экономики не отдаёт ворота отдельным полем: city_structures() (server/structures.py:365-366) возвращает
# только objects и walls, а CITY_WALLS (server/structures.py:239-251) содержит стены и башни. Проёмы — промежутки
# между коллинеарными стенами одной толщины; gaps_from_walls() находит их по стенам, тест сверяет с GATES из
# economy_city_layout_rules.gd. Размеры совпадают с scenes/city/rendering.py _draw_walls_and_gates (1335-1427).
# Выход в Python: scenes/city_scene.py update(), зоны проёмов задают exit_gate и finished (1067-1087).
# Переход: economy_world.gd (клик по проёму или шаг в зону) открывает карту; world_entry.gd входит у точки MAP_SPAWNS.
# Обратно город открывает у точки CITY_SPAWNS по входу town_radburg (server/structures.py:282).

const TILE_PX := 16
const EXIT_SOURCE := "scenes/city_scene.py:1067-1087"
# Точки появления на карте мира у ворот (scenes/world_map_scene.py:501-518); main — алиас главных ворот.
const MAP_SPAWNS := {
	"east": {"position": Vector2(150 * TILE_PX + 16, 106 * TILE_PX + 16), "direction": "e"},
	"north": {"position": Vector2(134 * TILE_PX + 16, 90 * TILE_PX + 16), "direction": "n"},
	"south": {"position": Vector2(134 * TILE_PX + 16, 122 * TILE_PX + 16), "direction": "s"},
	"west": {"position": Vector2(118 * TILE_PX + 16, 106 * TILE_PX + 16), "direction": "w"},
}
# Точки появления в городе при возврате с карты (scenes/city_scene.py, spawn_map).
const CITY_SPAWNS := {
	"east": {"position": Vector2(190 * TILE_PX + 16, 100 * TILE_PX), "direction": "w"},
	"north": {"position": Vector2(100 * TILE_PX, 8 * TILE_PX + 16), "direction": "s"},
	"south": {"position": Vector2(100 * TILE_PX, 190 * TILE_PX + 16), "direction": "n"},
	"west": {"position": Vector2(8 * TILE_PX + 16, 100 * TILE_PX), "direction": "e"},
}
const GATE_ALIASES := {"main": "east"}
const TOWN_IDS := ["town_radburg", "main_castle"]
const NAMES := {
	"east": "Главные ворота",
	"north": "Северные ворота",
	"south": "Южные ворота",
	"west": "Западные ворота",
}


# walls — прямоугольники [x, y, w, h] или Rect2i в пикселях мира; возвращает ворота с полями id, name, rect (в тайлах).
static func gaps_from_walls(walls: Array) -> Array:
	var rects: Array[Rect2i] = []
	for wall in walls:
		rects.append(_rect_of(wall))
	var extent := Vector2i.ZERO
	for rect in rects:
		extent = Vector2i(maxi(extent.x, rect.end.x), maxi(extent.y, rect.end.y))
	var gates: Array = []
	for first in rects:
		for second in rects:
			var gap := _gap_between(first, second)
			if gap.has_area() and not _blocked(gap, rects):
				gates.append(_gate_for(gap, extent))
	return gates


# Ворота, в зону которых попала точка мира; пустой словарь, если точка вне проёмов.
static func gate_at_world(gates: Array, world: Vector2) -> Dictionary:
	for gate in gates:
		var rect: Rect2i = gate["rect"]
		if Rect2(Vector2(rect.position * TILE_PX), Vector2(rect.size * TILE_PX)).has_point(world):
			return gate
	return {}


static func tooltip(gate: Dictionary) -> String:
	return "%s · выход на карту мира" % str(gate.get("name", ""))


# Точка появления на карте мира у ворот города; неизвестные ворота — главные.
static func map_spawn(gate_id: String) -> Dictionary:
	return _spawn(MAP_SPAWNS, gate_id)


# Точка появления в городе при возврате с карты у выбранного входа; неизвестный вход — главные ворота.
static func city_spawn(gate_id: String) -> Dictionary:
	return _spawn(CITY_SPAWNS, gate_id)


# Id входа в город, на клетке которого стоит герой на карте мира; пусто, если клетка не вход.
static func entrance_at_tile(objects: Array, tile: Vector2i) -> String:
	for map_object in objects:
		if not map_object is Dictionary or not TOWN_IDS.has(str(map_object.get("id", ""))):
			continue
		for entrance in map_object.get("entrances", []):
			if not entrance is Dictionary:
				continue
			for entrance_tile in entrance.get("tiles", []):
				if entrance_tile is Array and entrance_tile.size() >= 2 and int(entrance_tile[0]) == tile.x and int(entrance_tile[1]) == tile.y:
					return str(entrance.get("id", "east"))
	return ""


static func _spawn(table: Dictionary, gate_id: String) -> Dictionary:
	var key := str(GATE_ALIASES.get(gate_id, gate_id))
	var spawn: Dictionary = table.get(key, table["east"])
	return spawn.duplicate()


static func _rect_of(value: Variant) -> Rect2i:
	if value is Rect2i:
		return value
	var values: Array = value
	return Rect2i(int(values[0]), int(values[1]), int(values[2]), int(values[3]))


static func _gap_between(first: Rect2i, second: Rect2i) -> Rect2i:
	if first.position.y == second.position.y and first.size.y == second.size.y and second.position.x > first.end.x:
		return Rect2i(first.end.x, first.position.y, second.position.x - first.end.x, first.size.y)
	if first.position.x == second.position.x and first.size.x == second.size.x and second.position.y > first.end.y:
		return Rect2i(first.position.x, first.end.y, first.size.x, second.position.y - first.end.y)
	return Rect2i()


# Промежуток, занятый башней или стеной, не проём: между башнями по верхнему краю лежит стена.
static func _blocked(gap: Rect2i, rects: Array[Rect2i]) -> bool:
	for rect in rects:
		if rect.intersects(gap):
			return true
	return false


static func _gate_for(gap: Rect2i, extent: Vector2i) -> Dictionary:
	var side := ""
	if gap.position.y == 0:
		side = "north"
	elif gap.end.y == extent.y:
		side = "south"
	elif gap.position.x == 0:
		side = "west"
	elif gap.end.x == extent.x:
		side = "east"
	var tiles := Rect2i(
		floori(float(gap.position.x) / TILE_PX), floori(float(gap.position.y) / TILE_PX),
		ceili(float(gap.size.x) / TILE_PX), ceili(float(gap.size.y) / TILE_PX),
	)
	return {"id": side, "name": str(NAMES.get(side, "Ворота")), "rect": tiles}
