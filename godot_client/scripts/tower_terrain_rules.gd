extends RefCounted

# Правила рельефа Башни без текстур и без рисования, порт scenes/world_map_scene.py:
#   _map_hash (286), build_ground_kinds (293), _edge_gap (334), _rock_info (341), build_mountain_roles (364),
#   ключ и смешение кромок дороги (_road_surface 1628, _build_road_tile 412), _add_tree_slots (1687),
#   _draw_forest_trees (1641), _draw_bridges (1703), _draw_shore_rims (1715), _render_mountain_tiles (1900),
#   _render_mountains (1850), _render_forest (1913), _render_lake (1931), point_in_polygon (server/world_map.py).
# Клетки лежат плоским массивом с индексом gy * width + gx. Пиксель кромки — четвёрка (a, r, g, b).
# Команды отрисовки (ops) идут в локальных координатах поверхности Python, без смещения origin.

const TILE := 32
const TREE_FRAME_MS := 140
const TREE_FRAMES := 10
const TREE_INDEX_BITS := 22
const TREE_INDEX_MASK := (1 << TREE_INDEX_BITS) - 1
const KIND_GRASS := 0
const KIND_FLOOR := 1
const KIND_BERRY := 2
const FLOOR_RING := 1
const BERRY_RING := 5
# Текстуры земли идут одним списком: вода, трава, подстилка, ягоды; внутри вида — варианты по хэшу клетки.
const GROUND_WATER_BASE := 0
const GROUND_WATER_COUNT := 3
const GROUND_GRASS_BASE := 3
const GROUND_GRASS_COUNT := 20
const GROUND_FLOOR_BASE := 23
const GROUND_FLOOR_COUNT := 16
const GROUND_BERRY_BASE := 39
const GROUND_BERRY_COUNT := 12
const ROAD_CORE_COUNT := 4
const ROAD_EDGE_VARIANTS := 3
const ROAD_PIECE_COUNT := 49
# Порядок сторон дороги как в MAP_ROAD_NEIGHBOURS: n, s, e, w; бит стороны = 1 << индекс
const ROAD_SIDE_OFFSETS := [Vector2i(0, -1), Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0)]
const ROAD_SIDE_NAMES := ["n", "s", "e", "w"]
# Порядок граней горной клетки как в Python: N, E, S, W; бит грани = 1 << индекс
const ROCK_SIDE_OFFSETS := [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
const SHORE_LEFT := 0
const SHORE_RIGHT := 1
const SHORE_TOP := 2
const SHORE_BOTTOM := 3
const SHORE_VARIANTS := 3
# Листы деревьев: 0–2 зелёные (tree1–3), 3–6 мёртвые (old_tree1–3, big_tree), как порядок MAP_TREE_SHEETS
const GREEN_TREE_IDS := [0, 1, 2]
const DEAD_TREE_IDS := [3, 4, 5, 6]
const PROP_TYPES := ["stump", "log"]
const PROP_VARIANTS := 2
const PROP_SPRITE_BASE := 7
const FOREST_MARGIN := 30
const LAKE_ARC_COUNT := 72


static func map_hash(gx: int, gy: int) -> int:
	var h := ((gx * 73856093) ^ (gy * 19349663)) & 0xFFFFFFFF
	h = ((h ^ (h >> 13)) * 0x5BD1E995) & 0xFFFFFFFF
	return h ^ (h >> 15)


# Деление как у Python //: округление вниз, в том числе для отрицательных чисел.
static func floor_div(numerator: int, denominator: int) -> int:
	return floori(float(numerator) / float(denominator))


# round() из Python: половина округляется к чётному (76.5 → 76, 53.5 → 54).
static func py_round(value: float) -> int:
	var base := floorf(value)
	var fraction := value - base
	if fraction > 0.5 or (fraction == 0.5 and fmod(base, 2.0) != 0.0):
		return int(base) + 1
	return int(base)


static func tile_mask(width: int, height: int) -> PackedByteArray:
	var mask := PackedByteArray()
	mask.resize(maxi(0, width) * maxi(0, height))
	return mask


# Строки [y, x_начало, x_конец] → клетки маски; клетки за пределами сетки пропускаются.
static func fill_tile_rows(mask: PackedByteArray, rows: Array, width: int, height: int) -> void:
	for row in rows:
		if not (row is Array) or row.size() < 3:
			continue
		var tile_y := int(row[0])
		for tile_x in range(int(row[1]), int(row[2]) + 1):
			_set_cell(mask, width, height, tile_x, tile_y)


static func fill_tile_points(mask: PackedByteArray, points: Array, width: int, height: int) -> void:
	for point in points:
		if point is Array and point.size() >= 2:
			_set_cell(mask, width, height, int(point[0]), int(point[1]))


static func cell_on(mask: PackedByteArray, width: int, height: int, gx: int, gy: int) -> bool:
	return gx >= 0 and gy >= 0 and gx < width and gy < height and mask[gy * width + gx] != 0


static func _set_cell(mask: PackedByteArray, width: int, height: int, gx: int, gy: int) -> void:
	if gx >= 0 and gy >= 0 and gx < width and gy < height:
		mask[gy * width + gx] = 1


# Вид земли по клеткам леса и сухого края: 0 трава, 1 подстилка, 2 ягоды.
# Клетки дальше BERRY_RING от покрытия — пятнами по блокам 5x5.
static func ground_kinds(cover: PackedByteArray, width: int, height: int) -> PackedByteArray:
	var count := width * height
	var distance := PackedInt32Array()
	distance.resize(count)
	distance.fill(-1)
	var frontier := PackedInt32Array()
	for index in count:
		if cover[index] != 0:
			distance[index] = 0
			frontier.append(index)
	for depth in range(1, BERRY_RING + 1):
		var next := PackedInt32Array()
		for index in frontier:
			var gx: int = index % width
			var gy: int = floor_div(index, width)
			for dy in [-1, 0, 1]:
				for dx in [-1, 0, 1]:
					var nx: int = gx + dx
					var ny: int = gy + dy
					if nx < 0 or ny < 0 or nx >= width or ny >= height:
						continue
					var neighbour: int = ny * width + nx
					if distance[neighbour] == -1:
						distance[neighbour] = depth
						next.append(neighbour)
		frontier = next
	var kinds := PackedByteArray()
	kinds.resize(count)
	for gy in height:
		for gx in width:
			var index := gy * width + gx
			var h := map_hash(gx, gy)
			var depth := distance[index]
			var kind := KIND_GRASS
			if depth == 0:
				kind = KIND_FLOOR
			elif depth > 0 and depth <= FLOOR_RING:
				if h % 5 < 3:
					kind = KIND_FLOOR
			elif depth > 0:
				if h % 7 != 0:
					kind = KIND_BERRY
			elif map_hash(floor_div(gx, 5), floor_div(gy, 5)) % 4 == 0 and h % 5 < 3:
				kind = KIND_BERRY
			kinds[index] = kind
	return kinds


static func ground_texture_index(kind: int, h: int) -> int:
	match kind:
		KIND_FLOOR:
			return GROUND_FLOOR_BASE + h % GROUND_FLOOR_COUNT
		KIND_BERRY:
			return GROUND_BERRY_BASE + h % GROUND_BERRY_COUNT
	return GROUND_GRASS_BASE + h % GROUND_GRASS_COUNT


static func water_texture_index(gx: int, gy: int) -> int:
	return GROUND_WATER_BASE + map_hash(gx, gy) % GROUND_WATER_COUNT


# Кусок дороги: -1 — не дорога; 0–3 — ядро; 4+ — кромка по маске сторон (1–15) и варианту.
static func road_piece(road: PackedByteArray, width: int, height: int, gx: int, gy: int) -> int:
	if not cell_on(road, width, height, gx, gy):
		return -1
	var sides := 0
	for side in ROAD_SIDE_OFFSETS.size():
		var offset: Vector2i = ROAD_SIDE_OFFSETS[side]
		if not cell_on(road, width, height, gx + offset.x, gy + offset.y):
			sides |= 1 << side
	var h := map_hash(gx, gy)
	if sides == 0:
		return h % ROAD_CORE_COUNT
	return ROAD_CORE_COUNT + (sides - 1) * ROAD_EDGE_VARIANTS + (h >> 8) % ROAD_EDGE_VARIANTS


# Кромки дороги на углу пересекаются по каналам: минимум каждого байта RGBA (BLEND_RGBA_MIN).
static func road_composite(edges: Array) -> PackedByteArray:
	var result: PackedByteArray = edges[0].duplicate()
	for index in range(1, edges.size()):
		var other: PackedByteArray = edges[index]
		for byte_index in result.size():
			result[byte_index] = mini(result[byte_index], other[byte_index])
	return result


# Кромки и непрозрачность картинки клетки горы: edges — N, E, S, W; opacity — доля альфы на грани.
static func rock_info(size: int, rgba: PackedByteArray) -> Dictionary:
	var last := size - 1
	var edges: Array = [
		_pixel_line(size, rgba, 0, 0, 1, 0),
		_pixel_line(size, rgba, last, 0, 0, 1),
		_pixel_line(size, rgba, 0, last, 1, 0),
		_pixel_line(size, rgba, 0, 0, 0, 1),
	]
	var opacity := PackedFloat64Array()
	for index in edges.size():
		var line: PackedInt32Array = edges[index]
		var alpha := 0
		for pixel in size:
			alpha += line[pixel * 4]
		opacity.append(float(alpha) / (255.0 * size))
	return {"edges": edges, "opacity": opacity}


static func _pixel_line(size: int, rgba: PackedByteArray, x0: int, y0: int, step_x: int, step_y: int) -> PackedInt32Array:
	var line := PackedInt32Array()
	line.resize(size * 4)
	for pixel in size:
		var source := ((y0 + step_y * pixel) * size + x0 + step_x * pixel) * 4
		var target := pixel * 4
		line[target] = rgba[source + 3]
		line[target + 1] = rgba[source]
		line[target + 2] = rgba[source + 1]
		line[target + 3] = rgba[source + 2]
	return line


# Средняя разница двух граней (_edge_gap по всем пикселям, деленная на длину).
static func line_gap(first: PackedInt32Array, second: PackedInt32Array) -> float:
	var count := first.size() >> 2
	var total := 0.0
	for pixel in count:
		var p := pixel * 4
		var gap := float(absi(first[p] - second[p])) / 255.0
		if first[p] != 0 and second[p] != 0:
			gap += float(absi(first[p + 1] - second[p + 1]) + absi(first[p + 2] - second[p + 2])
				+ absi(first[p + 3] - second[p + 3])) / 765.0
		total += gap
	return total / float(count)


# Выбор картинки горы для каждой клетки венца: rocks — массив rock_info в порядке имён, результат — индекс картинки.
static func mountain_roles(cells: Array, rocks: Array) -> Dictionary:
	var roles := {}
	if cells.is_empty() or rocks.is_empty():
		return roles
	var cell_set := {}
	for cell in cells:
		cell_set[cell] = true
	var rock_count := rocks.size()
	var openness: Array = []
	var candidates: Array = []
	for pattern in 16:
		var values := PackedFloat64Array()
		var best := INF
		for rock in rock_count:
			var opacity: PackedFloat64Array = rocks[rock]["opacity"]
			var total := 0.0
			for side in 4:
				var closed := ((pattern >> side) & 1) == 1
				total += (1.0 - opacity[side]) if closed else opacity[side]
			values.append(total)
			best = minf(best, total)
		var chosen := PackedInt32Array()
		for rock in rock_count:
			if values[rock] <= best + 0.5:
				chosen.append(rock)
		openness.append(values)
		candidates.append(chosen)
	var ordered := cells.duplicate()
	ordered.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.y < b.y or (a.y == b.y and a.x < b.x))
	var left_cache := {}
	var top_cache := {}
	for cell in ordered:
		var pattern := 0
		for side in 4:
			var offset: Vector2i = ROCK_SIDE_OFFSETS[side]
			if cell_set.has(cell + offset):
				pattern |= 1 << side
		var left: int = roles.get(cell + Vector2i(-1, 0), -1)
		var top: int = roles.get(cell + Vector2i(0, -1), -1)
		var values: PackedFloat64Array = openness[pattern]
		var best_rock := -1
		var best_score := INF
		for rock in candidates[pattern]:
			var seam := 0.0
			if left >= 0:
				seam += _pair_gap(left_cache, rock, left, rock_count, rocks[rock]["edges"][3], rocks[left]["edges"][1])
			if top >= 0:
				seam += _pair_gap(top_cache, rock, top, rock_count, rocks[rock]["edges"][0], rocks[top]["edges"][2])
			var score: float = values[rock] + seam
			if score < best_score:
				best_score = score
				best_rock = rock
		roles[cell] = best_rock
	return roles


static func _pair_gap(cache: Dictionary, rock: int, other: int, count: int, first: PackedInt32Array, second: PackedInt32Array) -> float:
	var key := rock * count + other
	if not cache.has(key):
		cache[key] = line_gap(first, second)
	return cache[key]


# Клетки горного препятствия [x, y, w, h, картинка]: как Python, картинка 32x32 отрисована целиком,
# но обрезана по прямоугольнику поверхности (правый и нижний край Rect включает последний пиксель).
static func mountain_pieces(bounds: Rect2i, roles: Dictionary) -> PackedInt32Array:
	var pieces := PackedInt32Array()
	var left_tile := floor_div(bounds.position.x, TILE)
	var top_tile := floor_div(bounds.position.y, TILE)
	var right_tile := floor_div(bounds.end.x - 1, TILE)
	var bottom_tile := floor_div(bounds.end.y - 1, TILE)
	for tile_y in range(top_tile, bottom_tile + 1):
		for tile_x in range(left_tile, right_tile + 1):
			var rock: int = roles.get(Vector2i(tile_x, tile_y), -1)
			if rock < 0:
				continue
			var x := bounds.position.x + (tile_x - left_tile) * TILE
			var y := bounds.position.y + (tile_y - top_tile) * TILE
			var piece_w := mini(x + TILE, bounds.end.x) - x
			var piece_h := mini(y + TILE, bounds.end.y) - y
			if piece_w > 0 and piece_h > 0:
				pieces.append(x)
				pieces.append(y)
				pieces.append(piece_w)
				pieces.append(piece_h)
				pieces.append(rock)
	return pieces


static func points_bounds(points: PackedVector2Array) -> Rect2i:
	if points.is_empty():
		return Rect2i()
	var min_x := int(points[0].x)
	var max_x := min_x
	var min_y := int(points[0].y)
	var max_y := min_y
	for point in points:
		min_x = mini(min_x, int(point.x))
		max_x = maxi(max_x, int(point.x))
		min_y = mini(min_y, int(point.y))
		max_y = maxi(max_y, int(point.y))
	return Rect2i(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


# Размещение деревьев клетки: Vector4i(base_x, base_y, индекс в пуле, фаза кадра). Пустая клетка — пустой массив.
static func tree_placements(gx: int, gy: int, pool_size: int) -> Array:
	var placements: Array = []
	var h := map_hash(gx, gy)
	if h % 5 == 0:
		return placements
	var layers := 2 if (h >> 3) % 3 == 0 else 1
	for layer in layers:
		var lh := map_hash(gx * 3 + layer * 101, gy * 7 + layer * 53)
		var dx := floor_div((((lh >> 4) % 13) - 6) * TILE, 12)
		var dy := floor_div((((lh >> 12) % 7) - 3) * TILE, 12)
		placements.append(Vector4i(gx * TILE + (TILE >> 1) + dx, (gy + 1) * TILE + dy, lh % pool_size, lh >> 8))
	return placements


# Пни и брёвна: Vector4i(gx, gy, индекс типа, ширина в клетках); якорь — минимальная клетка footprint, последний побеждает.
static func prop_anchors(props: Array) -> Array:
	var by_cell := {}
	for prop in props:
		if not (prop is Dictionary):
			continue
		var type_index := PROP_TYPES.find(str(prop.get("type", "")))
		if type_index < 0:
			continue
		var footprint: Array = []
		for tile in prop.get("tiles", []):
			if tile is Array and tile.size() >= 2:
				footprint.append(Vector2i(int(tile[0]), int(tile[1])))
		if footprint.is_empty():
			continue
		var anchor: Vector2i = footprint[0]
		for tile in footprint:
			if tile.x < anchor.x or (tile.x == anchor.x and tile.y < anchor.y):
				anchor = tile
		by_cell[anchor] = Vector4i(anchor.x, anchor.y, type_index, footprint.size())
	return by_cell.values()


# Все слоты леса и пней по клеткам, включая кольцо за краем карты. Порядок — ключи сортировки,
# которые повторяют stable sort по base_y из Python: сначала клетки карты, потом кольцо, затем по строкам и столбцам.
static func build_tree_layout(width: int, height: int, forest: PackedByteArray, dry: PackedByteArray, anchors: Array) -> Dictionary:
	var prop_by_cell := {}
	for anchor in anchors:
		prop_by_cell[Vector2i(anchor.x, anchor.y)] = anchor
	var sprite := PackedInt32Array()
	var base_x := PackedInt32Array()
	var base_y := PackedInt32Array()
	var phase := PackedInt32Array()
	var cells := {}
	for gy in range(-1, height + 1):
		for gx in range(-1, width + 1):
			var inside := gx >= 0 and gy >= 0 and gx < width and gy < height
			var outer := 0 if inside else 1
			var keys := PackedInt64Array()
			var pool: Array = []
			if inside:
				var index := gy * width + gx
				if prop_by_cell.has(Vector2i(gx, gy)):
					var anchor: Vector4i = prop_by_cell[Vector2i(gx, gy)]
					var entry := sprite.size()
					var prop_y := (gy + 1) * TILE
					sprite.append(PROP_SPRITE_BASE + anchor.z * PROP_VARIANTS + map_hash(gx, gy) % PROP_VARIANTS)
					base_x.append(gx * TILE + anchor.w * (TILE >> 1))
					base_y.append(prop_y)
					phase.append(0)
					keys.append(_sort_key(prop_y, outer, gy, gx, 0, entry))
				if dry[index] != 0:
					pool = DEAD_TREE_IDS
				elif forest[index] != 0:
					pool = GREEN_TREE_IDS
			elif dry[clampi(gy, 0, height - 1) * width + clampi(gx, 0, width - 1)] != 0:
				pool = DEAD_TREE_IDS
			if not pool.is_empty():
				var placements := tree_placements(gx, gy, pool.size())
				for layer in placements.size():
					var placement: Vector4i = placements[layer]
					var entry := sprite.size()
					sprite.append(pool[placement.z])
					base_x.append(placement.x)
					base_y.append(placement.y)
					phase.append(placement.w)
					keys.append(_sort_key(placement.y, outer, gy, gx, 1 + layer, entry))
			if not keys.is_empty():
				cells[Vector2i(gx, gy)] = keys
	return {"sprite": sprite, "base_x": base_x, "base_y": base_y, "phase": phase, "cells": cells}


static func _sort_key(base_y: int, outer: int, gy: int, gx: int, sub: int, index: int) -> int:
	var key := (base_y + 4096) & 0xFFFF
	key = (key << 1) | outer
	key = (key << 10) | (gy + 1)
	key = (key << 10) | (gx + 1)
	key = (key << 2) | sub
	return (key << TREE_INDEX_BITS) | index


# Диапазоны клеток деревьев как в _draw_forest_trees: внутри карты и кольцо за её краем.
static func tree_ranges(visible: Rect2, width: int, height: int) -> Dictionary:
	var left := floori(visible.position.x / TILE)
	var top := floori(visible.position.y / TILE)
	var right := floori(visible.end.x / TILE)
	var bottom := floori(visible.end.y / TILE)
	return {
		"start_gx": maxi(0, left - 2), "end_gx": mini(width, right + 3),
		"start_gy": maxi(0, top - 6), "end_gy": mini(height, bottom + 2),
		"outer_gx0": maxi(-1, left - 2), "outer_gx1": mini(width + 1, right + 3),
		"outer_gy0": maxi(-1, top - 6), "outer_gy1": mini(height + 1, bottom + 2),
	}


# Диапазоны клеток земли и кромок: на один тайл шире видимой области с каждой стороны.
static func ground_ranges(visible: Rect2, width: int, height: int) -> Vector4i:
	return Vector4i(
		maxi(0, floori(visible.position.x / TILE) - 1),
		mini(width, floori(visible.end.x / TILE) + 2),
		maxi(0, floori(visible.position.y / TILE) - 1),
		mini(height, floori(visible.end.y / TILE) + 2),
	)


# Плоский список [x, y, спрайт, кадр] в порядке отрисовки Python. sprite_sizes[спрайт] = Vector4i(ширина, высота, колонки, кадров).
static func tree_draws(layout: Dictionary, ranges: Dictionary, width: int, height: int, now_msec: int, sprite_sizes: Array) -> PackedInt32Array:
	var keys := _range_keys(layout, ranges, width, height)
	var sprites: PackedInt32Array = layout["sprite"]
	var base_x: PackedInt32Array = layout["base_x"]
	var base_y: PackedInt32Array = layout["base_y"]
	var phase: PackedInt32Array = layout["phase"]
	var draws := PackedInt32Array()
	var tick := floor_div(now_msec, TREE_FRAME_MS)
	for key in keys:
		var index: int = key & TREE_INDEX_MASK
		var sprite := sprites[index]
		var size: Vector4i = sprite_sizes[sprite]
		var frame := 0
		if size.w > 1:
			frame = (tick + phase[index]) % size.w
		draws.append(base_x[index] - (size.x >> 1))
		draws.append(base_y[index] - size.y)
		draws.append(sprite)
		draws.append(frame)
	return draws


static func _range_keys(layout: Dictionary, ranges: Dictionary, width: int, height: int) -> PackedInt64Array:
	var keys := PackedInt64Array()
	var cells: Dictionary = layout["cells"]
	for gy in range(ranges["outer_gy0"], ranges["outer_gy1"]):
		for gx in range(ranges["outer_gx0"], ranges["outer_gx1"]):
			if not _in_tree_ranges(gx, gy, ranges, width, height):
				continue
			var cell := Vector2i(gx, gy)
			if cells.has(cell):
				keys.append_array(cells[cell])
	keys.sort()
	return keys


# Внутри карты клетка берётся из диапазона видимой области, за краем — из кольца outer_*.
static func _in_tree_ranges(gx: int, gy: int, ranges: Dictionary, width: int, height: int) -> bool:
	if gx >= 0 and gy >= 0 and gx < width and gy < height:
		return gx >= ranges["start_gx"] and gx < ranges["end_gx"] and gy >= ranges["start_gy"] and gy < ranges["end_gy"]
	return gx >= ranges["outer_gx0"] and gx < ranges["outer_gx1"] and gy >= ranges["outer_gy0"] and gy < ranges["outer_gy1"]


# Мост по центру пролёта: (min + max + 1) * tile // 2 по каждой оси; верхний левый угол спрайта.
static func bridge_top_left(tiles: Array, sprite_size: Vector2i) -> Vector2i:
	var min_x := 2147483647
	var max_x := -2147483648
	var min_y := 2147483647
	var max_y := -2147483648
	for tile in tiles:
		min_x = mini(min_x, int(tile[0]))
		max_x = maxi(max_x, int(tile[0]))
		min_y = mini(min_y, int(tile[1]))
		max_y = maxi(max_y, int(tile[1]))
	var centre := Vector2i(floor_div((min_x + max_x + 1) * TILE, 2), floor_div((min_y + max_y + 1) * TILE, 2))
	return centre - Vector2i(sprite_size.x >> 1, sprite_size.y >> 1)


# Камни берега: плоский список [x, y, сторона, вариант] по клеткам диапазона, сторона — SHORE_*.
# sizes — размеры спрайтов сторон: left, right, top, bottom.
static func shore_rim_draws(water: PackedByteArray, width: int, height: int, ranges: Vector4i, sizes: Array) -> PackedInt32Array:
	var draws := PackedInt32Array()
	for gy in range(ranges.z, ranges.w):
		for gx in range(ranges.x, ranges.y):
			if not cell_on(water, width, height, gx, gy):
				continue
			var left := gx * TILE
			var top := gy * TILE
			var right := (gx + 1) * TILE
			var bottom := (gy + 1) * TILE
			var variant := (gx * 3 + gy * 5) % SHORE_VARIANTS
			if not cell_on(water, width, height, gx - 1, gy):
				var rim_left: Vector2i = sizes[SHORE_LEFT]
				_append_rim(draws, left - rim_left.x, top, SHORE_LEFT, variant)
			if not cell_on(water, width, height, gx + 1, gy):
				_append_rim(draws, right, top, SHORE_RIGHT, variant)
			if not cell_on(water, width, height, gx, gy - 1):
				var rim_top: Vector2i = sizes[SHORE_TOP]
				_append_rim(draws, left, top - rim_top.y, SHORE_TOP, variant)
			if not cell_on(water, width, height, gx, gy + 1):
				_append_rim(draws, left, bottom, SHORE_BOTTOM, variant)
	return draws


static func _append_rim(draws: PackedInt32Array, x: int, y: int, side: int, variant: int) -> void:
	draws.append(x)
	draws.append(y)
	draws.append(side)
	draws.append(variant)


# Цвет клетки без текстур: север и юг карты разного тона; дорога — своя заливка.
static func flat_cell_color(gx: int, gy: int, half_gy: int, is_road: bool) -> Color:
	var even := (gx + gy) % 2 == 0
	var color := Color8(28, 42, 32) if even else Color8(31, 46, 35)
	if gy >= half_gy:
		color = Color8(36, 32, 34) if even else Color8(40, 35, 38)
	if is_road:
		color = Color8(120, 96, 60) if even else Color8(128, 103, 65)
	return color


static func point_in_polygon(point: Vector2, polygon: PackedVector2Array) -> bool:
	var inside := false
	var count := polygon.size()
	for index in count:
		var a: Vector2 = polygon[index]
		var b: Vector2 = polygon[(index + 1) % count]
		if (a.y > point.y) != (b.y > point.y) and point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x:
			inside = not inside
	return inside


# Команды отрисовки: kind — polygon (заливка), outline (контур), lines, line, circle, arc, clear (очистка прямоугольника).
static func forest_ops(points: PackedVector2Array, trees: Array) -> Dictionary:
	var bounds := points_bounds(points)
	var left := bounds.position.x - FOREST_MARGIN
	var top := bounds.position.y - FOREST_MARGIN
	var size := Vector2i(bounds.end.x - 1 - left + FOREST_MARGIN, bounds.end.y - 1 - top + FOREST_MARGIN)
	var local := PackedVector2Array()
	for point in points:
		local.append(Vector2(point.x - left, point.y - top))
	var ops: Array = [{"kind": "polygon", "color": Color8(16, 32, 18), "points": local}]
	for tree in trees:
		var x := int(tree["x"]) - left
		var y := int(tree["y"]) - top
		var r := int(tree["r"])
		var shade := (x * 7 + y * 3) % 18
		ops.append({"kind": "circle", "color": Color8(10, 22, 12), "centre": Vector2(x + 4, y + 6), "radius": float(r)})
		ops.append({"kind": "circle", "color": Color8(26 + shade, 66 + shade, 32 + (shade >> 1)), "centre": Vector2(x, y), "radius": float(r)})
		var small := floor_div(r, 3)
		ops.append({"kind": "circle", "color": Color8(44 + shade, 98 + shade, 46), "centre": Vector2(x - small, y - small), "radius": float(floor_div(r, 2))})
	return {"origin": Vector2i(left, top), "size": size, "ops": ops}


static func lake_ops(points: PackedVector2Array, water_points: PackedVector2Array, sandy_sections: Array) -> Dictionary:
	var bounds := points_bounds(points)
	var left := bounds.position.x
	var top := bounds.position.y
	var size := bounds.size
	var shore := PackedVector2Array()
	for point in points:
		shore.append(Vector2(point.x - left, point.y - top))
	var water := PackedVector2Array()
	for point in water_points:
		water.append(Vector2(point.x - left, point.y - top))
	var ops: Array = [{"kind": "polygon", "color": Color8(74, 91, 61), "points": shore}]
	var count := shore.size()
	for section in sandy_sections:
		var first := floori(float(section[0]) * count)
		var last := floori(float(section[1]) * count)
		var part := shore.slice(first, mini(last + 1, count))
		if part.size() > 1:
			ops.append({"kind": "lines", "color": Color8(194, 169, 112), "closed": false, "points": part, "width": 22.0})
			ops.append({"kind": "lines", "color": Color8(220, 197, 143), "closed": false, "points": part, "width": 12.0})
	ops.append({"kind": "polygon", "color": Color8(28, 100, 132), "points": water})
	ops.append({"kind": "outline", "color": Color8(77, 158, 174), "points": water, "width": 3.0})
	var sum_x := 0.0
	var sum_y := 0.0
	for point in water:
		sum_x += point.x
		sum_y += point.y
	var centre_x := sum_x / water.size()
	var centre_y := sum_y / water.size()
	var inner := PackedVector2Array()
	for point in water:
		inner.append(Vector2(point.x + (centre_x - point.x) * 0.08, point.y + (centre_y - point.y) * 0.08))
	ops.append({"kind": "lines", "color": Color8(112, 189, 190), "closed": true, "points": inner, "width": 2.0})
	for index in LAKE_ARC_COUNT:
		var x := 22 + (index * 97) % maxi(24, size.x - 44)
		var y := 18 + (index * 61) % maxi(24, size.y - 36)
		if point_in_polygon(Vector2(x, y), water):
			var length := 5 + index % 13
			var color := Color8(119, 192, 194, 170) if index % 3 != 0 else Color8(18, 73, 104, 180)
			ops.append({"kind": "arc", "color": color, "rect": Rect2(x, y, length * 2, 7), "start": 0.2, "stop": 2.7, "width": 2.0})
	return {"origin": Vector2i(left, top), "size": size, "ops": ops}


# Горный массив с вершинами (_render_mountains): подножие, холмы и пики, снег, прорубленные проходы.
static func mountain_ops(points: PackedVector2Array, peaks: Array, passages: Array) -> Dictionary:
	var bounds := points_bounds(points)
	var left := bounds.position.x
	var right := bounds.end.x - 1
	var bottom := bounds.end.y - 1
	var top := bounds.position.y
	for peak in peaks:
		top = mini(top, int(peak["y"]) - int(peak["h"]))
	var size := Vector2i(right - left + 1, bottom - top + 1)
	var local := PackedVector2Array()
	for point in points:
		local.append(Vector2(point.x - left, point.y - top))
	var ops: Array = [
		{"kind": "polygon", "color": Color8(62, 64, 50), "points": local},
		{"kind": "outline", "color": Color8(40, 40, 32), "points": local, "width": 6.0},
	]
	for peak in peaks:
		var x := int(peak["x"]) - left
		var y := int(peak["y"]) - top
		var w := int(peak["w"])
		var h := int(peak["h"])
		if str(peak.get("kind", "")) == "hill":
			_hill_ops(ops, x, y, w, h)
			continue
		var apex := Vector2(x, y - h)
		var ridge := Vector2(x + w * 0.08, y)
		ops.append({"kind": "polygon", "color": Color8(118, 110, 100), "points": PackedVector2Array([Vector2(x - w / 2.0, y), apex, ridge])})
		ops.append({"kind": "polygon", "color": Color8(72, 66, 62), "points": PackedVector2Array([ridge, apex, Vector2(x + w / 2.0, y)])})
		if h >= 160:
			var snow := 0.22 if h < 300 else 0.32
			ops.append({"kind": "polygon", "color": Color8(235, 238, 242), "points": PackedVector2Array([
				Vector2(apex.x - w / 2.0 * snow, apex.y + h * snow), apex, Vector2(apex.x + w / 2.0 * snow, apex.y + h * snow),
			])})
		ops.append({"kind": "line", "color": Color8(40, 36, 34), "points": PackedVector2Array([apex, Vector2(x + w / 2.0, y)]), "width": 2.0})
	var local_passages: Array[Rect2i] = []
	for passage in passages:
		var rect: Rect2i = passage
		local_passages.append(Rect2i(rect.position.x - left, rect.position.y - top, rect.size.x, rect.size.y))
	for local_passage in local_passages:
		ops.append({"kind": "clear", "rect": Rect2(local_passage)})
	for local_passage in local_passages:
		for edge_pair in [[local_passage.position.x, -3], [local_passage.end.x, 3]]:
			var edge_x: int = edge_pair[0]
			var out: int = edge_pair[1]
			for y in range(local_passage.position.y, local_passage.end.y, 8):
				if _rock_side(Vector2(edge_x + out, y + 4), local, local_passages):
					ops.append(_line_op(Vector2(edge_x, y), Vector2(edge_x, y + 8)))
		for edge_pair in [[local_passage.position.y, -3], [local_passage.end.y, 3]]:
			var edge_y: int = edge_pair[0]
			var out: int = edge_pair[1]
			for x in range(local_passage.position.x, local_passage.end.x, 8):
				if _rock_side(Vector2(x + 4, edge_y + out), local, local_passages):
					ops.append(_line_op(Vector2(x, edge_y), Vector2(x + 8, edge_y)))
	return {"origin": Vector2i(left, top), "size": size, "ops": ops}


static func _hill_ops(ops: Array, x: int, y: int, w: int, h: int) -> void:
	var arc := PackedVector2Array()
	for step in 13:
		arc.append(Vector2(x - w / 2.0 + w * step / 12.0, y - h * sin(PI * step / 12.0)))
	var lower := arc.slice(6)
	ops.append({"kind": "polygon", "color": Color8(96, 102, 70), "points": arc})
	var shadow := lower.duplicate()
	shadow.append(Vector2(x, y))
	ops.append({"kind": "polygon", "color": Color8(72, 76, 54), "points": shadow})
	ops.append({"kind": "lines", "color": Color8(48, 50, 38), "closed": false, "points": lower, "width": 2.0})


static func _line_op(from: Vector2, to: Vector2) -> Dictionary:
	return {"kind": "line", "color": Color8(30, 27, 25), "points": PackedVector2Array([from, to]), "width": 5.0}


static func _rock_side(point: Vector2, local: PackedVector2Array, passages: Array[Rect2i]) -> bool:
	if not point_in_polygon(point, local):
		return false
	for passage in passages:
		if point.x >= passage.position.x and point.x < passage.end.x and point.y >= passage.position.y and point.y < passage.end.y:
			return false
	return true
