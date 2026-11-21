extends Node

# Проверки рельефа Башни: правила tower_terrain_rules.gd против Python-клиента.
# Ожидания получены вызовом функций scenes/world_map_scene.py на тех же входах: хэш клетки, round(),
# карта земли, кромки дорог из реальных PNG, выбор картинок гор по краям, размещение и порядок деревьев,
# мосты, камни берега, команды полигонов гор, леса и озера (_render_*). Контрольные суммы — Σ (i + 1) * значение.

const RULES := preload("res://scripts/tower_terrain_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/tower_terrain_view.gd")
const TICKS := [0, 139, 140, 98765]

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_hash_and_rounding()
	_check_tiles_and_ground()
	_check_roads()
	_check_mountains()
	_check_trees()
	_check_visible_trees()
	_check_bridges_and_shores()
	_check_mountain_pieces()
	_check_legacy_mountains()
	_check_legacy_forest()
	_check_legacy_lake()
	_check_asset_sizes()
	await _check_view()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_terrain_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)


static func _map_root() -> String:
	return ProjectSettings.globalize_path("res://").path_join("../assets/map").simplify_path()


static func _rgba(path: String) -> PackedByteArray:
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		return PackedByteArray()
	image.convert(Image.FORMAT_RGBA8)
	return image.get_data()


static func _weighted_sum(values: Array) -> int:
	var total := 0
	for index in values.size():
		total += (index + 1) * int(values[index])
	return total


static func _same(a: Variant, b: Variant) -> bool:
	if a is Array and b is Array:
		if a.size() != b.size():
			return false
		for index in a.size():
			if not _same(a[index], b[index]):
				return false
		return true
	if (a is float or a is int) and (b is float or b is int):
		# Vector2 хранит float32, поэтому допуск по координатам 1e-3 px
		return absf(float(a) - float(b)) < 0.001
	return a == b


func _check_hash_and_rounding() -> void:
	var cases := [[0, 0], [1, 0], [0, 1], [1, 2], [5, 7], [12, 3], [-1, 5], [-3, -2], [124, 124], [511, 255], [-1, -1], [2, -7]]
	var hashes := [0, 3044388955, 882533181, 965784961, 2328200225, 2182537451, 3780432144, 1438863210, 1450536075, 3208286729, 79354894, 539579621]
	for index in cases.size():
		_check(RULES.map_hash(cases[index][0], cases[index][1]) == hashes[index], "хэш клетки %s совпадает с Python" % str(cases[index]))
	var floats := [53.5, 76.5, 82.5, 84.0, 0.5, 1.5, 2.5, 114.0, -2.5]
	var rounded := [54, 76, 82, 84, 0, 2, 2, 114, -2]
	for index in floats.size():
		_check(RULES.py_round(floats[index]) == rounded[index], "round(%s) как в Python" % str(floats[index]))
	var dx := []
	for step in 13:
		dx.append(RULES.floor_div((step - 6) * 32, 12))
	_check(dx == [-16, -14, -11, -8, -6, -3, 0, 2, 5, 8, 10, 13, 16], "смещение дерева по x с округлением вниз")
	var dy := []
	for step in 7:
		dy.append(RULES.floor_div((step - 3) * 32, 12))
	_check(dy == [-8, -6, -3, 0, 2, 5, 8], "смещение дерева по y с округлением вниз")


func _check_tiles_and_ground() -> void:
	var mask := RULES.tile_mask(9, 7)
	RULES.fill_tile_rows(mask, [[2, 3, 5], [4, 0, 0], [4, 7, 8], [0, 1, 1], [-1, 0, 3], [6, 8, 8]], 9, 7)
	var expected := [Vector2i(0, 4), Vector2i(1, 0), Vector2i(3, 2), Vector2i(4, 2), Vector2i(5, 2), Vector2i(7, 4), Vector2i(8, 4), Vector2i(8, 6)]
	var found := 0
	for y in 7:
		for x in 9:
			if mask[y * 9 + x] != 0:
				found += 1
				_check(expected.has(Vector2i(x, y)), "лишняя клетка маски (%d, %d)" % [x, y])
	_check(found == expected.size(), "маска строк [y, x0, x1] совпадает с _tile_set в пределах сетки")

	var cover := RULES.tile_mask(24, 14)
	for y in range(5, 9):
		for x in range(6, 10):
			cover[y * 24 + x] = 1
	cover[2 * 24 + 20] = 1
	cover[2 * 24 + 21] = 1
	cover[3 * 24 + 20] = 1
	var kinds := RULES.ground_kinds(cover, 24, 14)
	var grid := [
		"BBBBBBBB.BBBB.B.BBBBBBBB", "BBBB.BBBBBBBBBBBBBBFFFF.", "BB.BBBBBBBBBBBBBBBBFFFF.", "B.BBBBB.BBBBBB.BBBB.F.FB",
		".BBB.F.F.FFBBBBB.BBF.FB.", ".BBBBFFFFFFBBBBBBBBBBBBB", ".B.BB.FFFF.BB...BBBBB.B.", ".BBBBFFFFFFBBBBBB.BBBBBB",
		"...BBFFFFFFBBBBB.B.BBBBB", ".BBBBFFF..FBB.B.........", ".BB..BBBBBBBBBB.B.......", ".BBBBB.BBBBBBBBBBB......",
		".BB..BBBBBBBBBBBBB......", ".BBBBBBBBB.BBB..B.B.....",
	]
	for y in 14:
		var line := ""
		for x in 24:
			var kind: int = kinds[y * 24 + x]
			line += "F" if kind == RULES.KIND_FLOOR else ("B" if kind == RULES.KIND_BERRY else ".")
		_check(line == grid[y], "вид земли строка %d совпадает с build_ground_kinds" % y)


func _check_roads() -> void:
	var edge_sides := ["n", "s", "e", "w"]
	var road := RULES.tile_mask(16, 14)
	for x in range(2, 13):
		road[6 * 16 + x] = 1
	for y in range(1, 13):
		road[y * 16 + 7] = 1
	for tile in [Vector2i(3, 2), Vector2i(4, 2), Vector2i(3, 3), Vector2i(4, 3), Vector2i(12, 12)]:
		road[tile.y * 16 + tile.x] = 1
	# [gx, gy, маска сторон (n=1, s=2, e=4, w=8), ядро или вариант, контрольная сумма композита]
	var expected := [
		[7, 1, 13, 1, 439721101], [3, 2, 9, 2, 644012011], [4, 2, 5, 2, 721806405], [7, 2, 12, 1, 447679141],
		[3, 3, 10, 2, 494127594], [4, 3, 6, 0, 543990796], [7, 3, 12, 1, 447679141], [7, 4, 12, 0, 507765113],
		[7, 5, 12, 2, 467351890], [2, 6, 11, 1, 422550884], [3, 6, 3, 0, 561761421], [4, 6, 3, 1, 431825530],
		[5, 6, 3, 2, 492362307], [6, 6, 3, 0, 561761421], [7, 6, 0, 0, 1053305088], [8, 6, 3, 1, 431825530],
		[9, 6, 3, 0, 561761421], [10, 6, 3, 1, 431825530], [11, 6, 3, 0, 561761421], [12, 6, 7, 2, 477638786],
		[7, 7, 12, 1, 447679141], [7, 8, 12, 1, 447679141], [7, 9, 12, 0, 507765113], [7, 10, 12, 1, 447679141],
		[7, 11, 12, 2, 467351890], [7, 12, 14, 2, 432319843], [12, 12, 15, 0, 442016984],
	]
	var edge_cache := {}
	var core_cache := {}
	var map_tiles := _map_root().path_join("tiles")
	for item in expected:
		var piece := RULES.road_piece(road, 16, 14, item[0], item[1])
		var mask: int = item[2]
		var sub: int = item[3]
		var want := sub if mask == 0 else RULES.ROAD_CORE_COUNT + (mask - 1) * RULES.ROAD_EDGE_VARIANTS + sub
		_check(piece == want, "кусок дороги (%d, %d) = %d" % [item[0], item[1], want])
		var composite: PackedByteArray
		if mask == 0:
			if not core_cache.has(sub):
				core_cache[sub] = _rgba(map_tiles.path_join("road_core_%d.png" % (sub + 1)))
			composite = core_cache[sub]
		else:
			var edges: Array = []
			for side in 4:
				if mask & (1 << side):
					var key := "%s_%d" % [edge_sides[side], sub]
					if not edge_cache.has(key):
						edge_cache[key] = _rgba(map_tiles.path_join("road_edge_%s_%d.png" % [edge_sides[side], sub + 1]))
					edges.append(edge_cache[key])
			composite = RULES.road_composite(edges)
		_check(_weighted_sum(Array(composite)) == item[4], "композит кромок (%d, %d) совпадает с _build_road_tile" % [item[0], item[1]])


func _check_mountains() -> void:
	var names := PackedStringArray()
	for number in range(1, 121):
		names.append("rock_%02d" % number)
	names.sort()
	var rocks := []
	for name in names:
		rocks.append(RULES.rock_info(32, _rgba(_map_root().path_join("mountains").path_join(name + ".png"))))
	var opacity_cases := {
		"rock_01": [0.0, 0.96875, 0.84375, 0.0], "rock_50": [1.0, 0.8125, 0.75, 0.8125],
		"rock_100": [1.0, 1.0, 1.0, 1.0], "rock_120": [0.84375, 0.6875, 0.0, 0.25],
	}
	for name in opacity_cases:
		var info: Dictionary = rocks[names.find(name)]
		var opacity: PackedFloat64Array = info["opacity"]
		for side in 4:
			_check(opacity[side] == opacity_cases[name][side], "непрозрачность %s с края %d как в _rock_info" % [name, side])
	# [грань (0 N, 1 E, 2 S, 3 W), пиксель, a, r, g, b] — пиксели краёв, как get_at() в _rock_info
	var samples := {
		"rock_01": [[0, 0, 0, 255, 255, 255], [0, 5, 0, 255, 255, 255], [3, 7, 0, 255, 255, 255], [1, 31, 255, 91, 106, 50], [2, 3, 0, 255, 255, 255]],
		"rock_100": [[0, 0, 255, 116, 90, 61], [0, 5, 255, 30, 27, 24], [3, 7, 255, 116, 90, 61], [1, 31, 255, 160, 128, 95], [2, 3, 255, 86, 69, 54]],
	}
	for name in samples:
		var info: Dictionary = rocks[names.find(name)]
		for sample in samples[name]:
			var line: PackedInt32Array = info["edges"][sample[0]]
			var at: int = sample[1] * 4
			var pixel := [line[at], line[at + 1], line[at + 2], line[at + 3]]
			_check(pixel == [sample[2], sample[3], sample[4], sample[5]], "пиксель края %s совпадает с get_at" % name)
	var cells: Array = []
	for x in 9:
		for y in 7:
			if not (x >= 3 and x <= 5 and y >= 2 and y <= 4):
				cells.append(Vector2i(x, y))
	cells.append_array([Vector2i(9, 3), Vector2i(10, 3), Vector2i(10, 2)])
	var roles := RULES.mountain_roles(cells, rocks)
	# [x, y, номер rock_NN] как в build_mountain_roles
	var expected := [
		[0, 0, 1], [1, 0, 2], [2, 0, 2], [3, 0, 2], [4, 0, 2], [5, 0, 2], [6, 0, 2], [7, 0, 2], [8, 0, 6],
		[0, 1, 13], [1, 1, 101], [2, 1, 101], [3, 1, 112], [4, 1, 112], [5, 1, 112], [6, 1, 15], [7, 1, 15], [8, 1, 18],
		[0, 2, 13], [1, 2, 101], [2, 2, 18], [6, 2, 13], [7, 2, 101], [8, 2, 18], [10, 2, 89],
		[0, 3, 13], [1, 3, 101], [2, 3, 18], [6, 3, 13], [7, 3, 101], [8, 3, 101], [9, 3, 2], [10, 3, 107],
		[0, 4, 13], [1, 4, 101], [2, 4, 18], [6, 4, 13], [7, 4, 101], [8, 4, 18],
		[0, 5, 13], [1, 5, 101], [2, 5, 101], [3, 5, 2], [4, 5, 2], [5, 5, 2], [6, 5, 109], [7, 5, 109], [8, 5, 18],
		[0, 6, 104], [1, 6, 113], [2, 6, 113], [3, 6, 113], [4, 6, 113], [5, 6, 113], [6, 6, 113], [7, 6, 113], [8, 6, 107],
	]
	_check(roles.size() == expected.size(), "число клеток венца совпадает с build_mountain_roles")
	for item in expected:
		var want := names.find("rock_%02d" % item[2])
		_check(roles.get(Vector2i(item[0], item[1]), -1) == want, "картинка горы (%d, %d) = rock_%02d" % [item[0], item[1], item[2]])


func _check_trees() -> void:
	# [gx, gy, размер пула, [[base_x, base_y, индекс в пуле, кадры при TICKS]]]
	var cases := [
		[0, 0, 3, []], [0, 0, 4, []], [3, 4, 3, []], [3, 4, 4, []],
		[-1, 5, 3, [[-14, 184, 1, [9, 9, 0, 4]], [-27, 189, 2, [3, 3, 4, 8]]]],
		[-1, 5, 4, [[-14, 184, 1, [9, 9, 0, 4]], [-27, 189, 1, [3, 3, 4, 8]]]],
		[7, -1, 3, [[224, 8, 0, [1, 1, 2, 6]]]], [7, -1, 4, [[224, 8, 2, [1, 1, 2, 6]]]],
		[10, 10, 3, []], [10, 10, 4, []],
		[20, 3, 3, [[669, 120, 1, [6, 6, 7, 1]]]], [20, 3, 4, [[669, 120, 2, [6, 6, 7, 1]]]],
		[45, 30, 3, [[1472, 1000, 2, [2, 2, 3, 7]]]], [45, 30, 4, [[1472, 1000, 1, [2, 2, 3, 7]]]],
		[-1, -1, 3, [[-6, 8, 2, [5, 5, 6, 0]]]], [-1, -1, 4, [[-6, 8, 3, [5, 5, 6, 0]]]],
		[5, 7, 3, []], [5, 7, 4, []],
		[2, 9, 3, [[88, 314, 0, [7, 7, 8, 2]]]], [2, 9, 4, [[88, 314, 2, [7, 7, 8, 2]]]],
		[1, 1, 3, [[58, 72, 2, [5, 5, 6, 0]]]], [1, 1, 4, [[58, 72, 3, [5, 5, 6, 0]]]],
		[4, 4, 3, []], [4, 4, 4, []],
	]
	for item in cases:
		var placements := RULES.tree_placements(item[0], item[1], item[2])
		var expected: Array = item[3]
		_check(placements.size() == expected.size(), "число деревьев клетки (%d, %d) пул %d" % [item[0], item[1], item[2]])
		for index in mini(placements.size(), expected.size()):
			var placement: Vector4i = placements[index]
			var want: Array = expected[index]
			_check(placement.x == want[0] and placement.y == want[1] and placement.z == want[2],
				"дерево клетки (%d, %d) позиция и пул" % [item[0], item[1]])
			for tick_index in TICKS.size():
				var frame := (RULES.floor_div(TICKS[tick_index], RULES.TREE_FRAME_MS) + placement.w) % RULES.TREE_FRAMES
				_check(frame == want[3][tick_index], "кадр дерева клетки (%d, %d) в %d мс" % [item[0], item[1], TICKS[tick_index]])

	var width := 12
	var height := 8
	var forest := RULES.tile_mask(width, height)
	for y in range(2, 6):
		for x in range(2, 8):
			forest[y * width + x] = 1
	var dry := RULES.tile_mask(width, height)
	for x in width:
		dry[x] = 1
		dry[(height - 1) * width + x] = 1
	for y in height:
		dry[y * width] = 1
		dry[y * width + width - 1] = 1
	dry[3 * width + 9] = 1
	var props := [
		{"type": "log", "tiles": [[3, 2], [4, 2]]},
		{"type": "stump", "tiles": [[6, 4]]},
		{"type": "stump", "tiles": [[1, 4]]},
		{"type": "log", "tiles": [[5, 6], [6, 6]]},
		{"type": "stump", "tiles": [[10, 2]]},
	]
	var layout := RULES.build_tree_layout(width, height, forest, dry, RULES.prop_anchors(props))
	var sprite_sizes := [
		Vector4i(160, 256, 6, 10), Vector4i(160, 288, 6, 10), Vector4i(160, 224, 6, 10),
		Vector4i(160, 256, 6, 10), Vector4i(160, 288, 6, 10), Vector4i(160, 224, 6, 10),
		Vector4i(352, 416, 5, 10), Vector4i(83, 76, 1, 1), Vector4i(82, 84, 1, 1),
		Vector4i(114, 54, 1, 1), Vector4i(114, 54, 1, 1),
	]
	# Число блитов и контрольная сумма списка [x, y, спрайт, кадр] из _draw_forest_trees при кадре 1234567 мс
	var views := [
		[Rect2(-96, -64, 1920, 1080), 103, 579867],
		[Rect2(200, 150, 1920, 1080), 67, 959675],
		[Rect2(300, 300, 1920, 1080), 23, 161001],
	]
	for item in views:
		var ranges := RULES.tree_ranges(item[0], width, height)
		var draws := RULES.tree_draws(layout, ranges, width, height, 1234567, sprite_sizes)
		_check(draws.size() == item[1] * 4, "число слотов леса в %s" % str(item[0]))
		var flat := Array(draws)
		_check(_weighted_sum(flat) == item[2], "порядок и кадры слотов леса в %s" % str(item[0]))


func _check_bridges_and_shores() -> void:
	_check(RULES.bridge_top_left([[2, 4], [3, 4], [4, 4], [5, 4]], Vector2i(176, 110)) == Vector2i(40, 89), "мост по центру пролёта (1)")
	_check(RULES.bridge_top_left([[8, 1], [8, 2], [8, 3]], Vector2i(176, 110)) == Vector2i(184, 25), "мост по центру пролёта (2)")
	var water := RULES.tile_mask(12, 8)
	for y in range(2, 5):
		for x in range(3, 6):
			water[y * 12 + x] = 1
	water[5 * 12 + 9] = 1
	water[0] = 1
	var sizes := [Vector2i(12, 32), Vector2i(12, 32), Vector2i(32, 8), Vector2i(32, 8)]
	var full := Array(RULES.shore_rim_draws(water, 12, 8, Vector4i(0, 12, 0, 8), sizes))
	var full_expected := [
		-12, 0, 0, 0, 32, 0, 1, 0, 0, -8, 2, 0, 0, 32, 3, 0,
		84, 64, 0, 1, 96, 56, 2, 1, 128, 56, 2, 1, 192, 64, 1, 1, 160, 56, 2, 1,
		84, 96, 0, 0, 192, 96, 1, 0, 84, 128, 0, 2, 96, 160, 3, 2, 128, 160, 3, 2,
		192, 128, 1, 2, 160, 160, 3, 2, 276, 160, 0, 1, 320, 160, 1, 1, 288, 152, 2, 1, 288, 192, 3, 1,
	]
	_check(full == full_expected, "камни берега по всей карте совпадают с _draw_shore_rims")
	var partial := Array(RULES.shore_rim_draws(water, 12, 8, Vector4i(2, 6, 1, 5), sizes))
	var partial_expected := [
		84, 64, 0, 1, 96, 56, 2, 1, 128, 56, 2, 1, 192, 64, 1, 1, 160, 56, 2, 1,
		84, 96, 0, 0, 192, 96, 1, 0, 84, 128, 0, 2, 96, 160, 3, 2, 128, 160, 3, 2,
		192, 128, 1, 2, 160, 160, 3, 2,
	]
	_check(partial == partial_expected, "камни берега в диапазоне видимой области совпадают с Python")


func _check_mountain_pieces() -> void:
	var roles := {Vector2i(0, 0): 1, Vector2i(1, 0): 2, Vector2i(2, 0): 3, Vector2i(0, 1): 4}
	var pieces := Array(RULES.mountain_pieces(Rect2i(0, 0, 65, 33), roles))
	_check(pieces == [0, 0, 32, 32, 1, 32, 0, 32, 32, 2, 64, 0, 1, 32, 3, 0, 32, 32, 1, 4],
		"клетки гор обрезаются по прямоугольнику поверхности как в _render_mountain_tiles")


func _normalize_op(op: Dictionary) -> Array:
	var kind: String = op["kind"]
	match kind:
		"polygon":
			return ["fill_poly", _color(op["color"]), _points(op["points"])]
		"outline":
			return ["outline_poly", _color(op["color"]), _points(op["points"]), float(op["width"])]
		"lines":
			return ["lines", _color(op["color"]), bool(op["closed"]), _points(op["points"]), float(op["width"])]
		"line":
			return ["line", _color(op["color"]), _point(op["points"][0]), _point(op["points"][1]), float(op["width"])]
		"circle":
			return ["circle", _color(op["color"]), _point(op["centre"]), float(op["radius"])]
		"arc":
			return ["arc", _color(op["color"]), _rect(op["rect"]), float(op["start"]), float(op["stop"]), float(op["width"])]
		"clear":
			return ["clear", _rect(op["rect"])]
	return []


static func _color(color: Color) -> Array:
	var values := [roundi(color.r * 255.0), roundi(color.g * 255.0), roundi(color.b * 255.0)]
	if color.a < 0.999:
		values.append(roundi(color.a * 255.0))
	return values


static func _point(point: Vector2) -> Array:
	return [point.x, point.y]


static func _points(points: PackedVector2Array) -> Array:
	var result := []
	for point in points:
		result.append([point.x, point.y])
	return result


static func _rect(rect: Rect2) -> Array:
	return [rect.position.x, rect.position.y, rect.size.x, rect.size.y]


func _check_legacy_mountains() -> void:
	var points := PackedVector2Array([Vector2(100, 100), Vector2(260, 100), Vector2(260, 220), Vector2(100, 220)])
	var peaks := [
		{"x": 140, "y": 160, "w": 60, "h": 50, "kind": "hill"},
		{"x": 200, "y": 200, "w": 90, "h": 180, "kind": "peak"},
		{"x": 232, "y": 150, "w": 70, "h": 120, "kind": "peak"},
	]
	var result := RULES.mountain_ops(points, peaks, [Rect2i(180, 150, 30, 40)])
	_check(result["origin"] == Vector2i(100, 20) and result["size"] == Vector2i(161, 201), "поверхность гор как в _render_mountains")
	var hill_low := [[10.0, 140.0], [15.0, 127.05904774487396], [20.0, 115.0], [25.0, 104.64466094067262], [30.0, 96.69872981077808],
		[35.0, 91.70370868554659], [40.0, 90.0], [45.0, 91.70370868554659], [50.0, 96.69872981077806], [55.0, 104.64466094067262],
		[60.0, 115.0], [65.0, 127.05904774487395], [70.0, 140.0]]
	var hill_high := [[40.0, 90.0], [45.0, 91.70370868554659], [50.0, 96.69872981077806], [55.0, 104.64466094067262],
		[60.0, 115.0], [65.0, 127.05904774487395], [70.0, 140.0]]
	var expected := [
		["fill_poly", [62, 64, 50], [[0, 80], [160, 80], [160, 200], [0, 200]]],
		["outline_poly", [40, 40, 32], [[0, 80], [160, 80], [160, 200], [0, 200]], 6.0],
		["fill_poly", [96, 102, 70], hill_low],
		["fill_poly", [72, 76, 54], hill_high + [[40, 140]]],
		["lines", [48, 50, 38], false, hill_high, 2.0],
		["fill_poly", [118, 110, 100], [[55.0, 180], [100, 0], [107.2, 180]]],
		["fill_poly", [72, 66, 62], [[107.2, 180], [100, 0], [145.0, 180]]],
		["fill_poly", [235, 238, 242], [[90.1, 39.6], [100, 0], [109.9, 39.6]]],
		["line", [40, 36, 34], [100, 0], [145.0, 180], 2.0],
		["fill_poly", [118, 110, 100], [[97.0, 130], [132, 10], [137.6, 130]]],
		["fill_poly", [72, 66, 62], [[137.6, 130], [132, 10], [167.0, 130]]],
		["line", [40, 36, 34], [132, 10], [167.0, 130], 2.0],
		["clear", [80, 130, 30, 40]],
		["line", [30, 27, 25], [80, 130], [80, 138], 5.0],
		["line", [30, 27, 25], [80, 138], [80, 146], 5.0],
		["line", [30, 27, 25], [80, 146], [80, 154], 5.0],
		["line", [30, 27, 25], [80, 154], [80, 162], 5.0],
		["line", [30, 27, 25], [80, 162], [80, 170], 5.0],
		["line", [30, 27, 25], [110, 130], [110, 138], 5.0],
		["line", [30, 27, 25], [110, 138], [110, 146], 5.0],
		["line", [30, 27, 25], [110, 146], [110, 154], 5.0],
		["line", [30, 27, 25], [110, 154], [110, 162], 5.0],
		["line", [30, 27, 25], [110, 162], [110, 170], 5.0],
		["line", [30, 27, 25], [80, 130], [88, 130], 5.0],
		["line", [30, 27, 25], [88, 130], [96, 130], 5.0],
		["line", [30, 27, 25], [96, 130], [104, 130], 5.0],
		["line", [30, 27, 25], [104, 130], [112, 130], 5.0],
		["line", [30, 27, 25], [80, 170], [88, 170], 5.0],
		["line", [30, 27, 25], [88, 170], [96, 170], 5.0],
		["line", [30, 27, 25], [96, 170], [104, 170], 5.0],
		["line", [30, 27, 25], [104, 170], [112, 170], 5.0],
	]
	var ops: Array = []
	for op in result["ops"]:
		ops.append(_normalize_op(op))
	_check(_same(ops, expected), "команды гор (_render_mountains) совпадают с Python")


func _check_legacy_forest() -> void:
	var points := PackedVector2Array([Vector2(200, 200), Vector2(300, 190), Vector2(320, 280), Vector2(210, 300)])
	var trees := [{"x": 220, "y": 220, "r": 18}, {"x": 260, "y": 240, "r": 24}, {"x": 300, "y": 250, "r": 16}]
	var result := RULES.forest_ops(points, trees)
	_check(result["origin"] == Vector2i(170, 160) and result["size"] == Vector2i(180, 170), "поверхность леса как в _render_forest")
	var expected := [
		["fill_poly", [16, 32, 18], [[30, 40], [130, 30], [150, 120], [40, 140]]],
		["circle", [10, 22, 12], [54, 66], 18.0],
		["circle", [34, 74, 36], [50, 60], 18.0],
		["circle", [52, 106, 46], [44, 54], 9.0],
		["circle", [10, 22, 12], [94, 86], 24.0],
		["circle", [32, 72, 35], [90, 80], 24.0],
		["circle", [50, 104, 46], [82, 72], 12.0],
		["circle", [10, 22, 12], [134, 96], 16.0],
		["circle", [36, 76, 37], [130, 90], 16.0],
		["circle", [54, 108, 46], [125, 85], 8.0],
	]
	var ops: Array = []
	for op in result["ops"]:
		ops.append(_normalize_op(op))
	_check(_same(ops, expected), "команды леса (_render_forest) совпадают с Python")


func _check_legacy_lake() -> void:
	var points := PackedVector2Array([Vector2(40, 40), Vector2(80, 34), Vector2(110, 52), Vector2(114, 84),
		Vector2(96, 104), Vector2(52, 100), Vector2(28, 76), Vector2(24, 50)])
	var water := PackedVector2Array([Vector2(48, 52), Vector2(76, 45), Vector2(100, 58), Vector2(104, 82),
		Vector2(92, 96), Vector2(56, 93), Vector2(36, 74), Vector2(32, 56)])
	var result := RULES.lake_ops(points, water, [[0.06, 0.2], [0.43, 0.57]])
	_check(result["origin"] == Vector2i(24, 34) and result["size"] == Vector2i(91, 71), "поверхность озера как в _render_lake")
	var expected := [
		["fill_poly", [74, 91, 61], [[16, 6], [56, 0], [86, 18], [90, 50], [72, 70], [28, 66], [4, 42], [0, 16]]],
		["lines", [194, 169, 112], false, [[16, 6], [56, 0]], 22.0],
		["lines", [220, 197, 143], false, [[16, 6], [56, 0]], 12.0],
		["lines", [194, 169, 112], false, [[90, 50], [72, 70]], 22.0],
		["lines", [220, 197, 143], false, [[90, 50], [72, 70]], 12.0],
		["fill_poly", [28, 100, 132], [[24, 18], [52, 11], [76, 24], [80, 48], [68, 62], [32, 59], [12, 40], [8, 22]]],
		["outline_poly", [77, 158, 174], [[24, 18], [52, 11], [76, 24], [80, 48], [68, 62], [32, 59], [12, 40], [8, 22]], 3.0],
		["lines", [112, 189, 190], true, [[25.6, 19.4], [51.36, 12.96], [73.44, 24.92], [77.12, 47.0], [66.08, 59.88],
			[32.96, 57.12], [14.56, 39.64], [10.879999999999999, 23.08]], 2.0],
	]
	var ops: Array = []
	var arcs: Array = []
	for op in result["ops"]:
		if op["kind"] == "arc":
			var rect: Rect2 = op["rect"]
			var color: Color = op["color"]
			arcs.append(int(rect.position.x))
			arcs.append(int(rect.position.y))
			arcs.append(int(rect.size.x))
			arcs.append(int(rect.size.y))
			arcs.append(roundi(color.r * 255.0))
			arcs.append(roundi(color.g * 255.0))
			arcs.append(roundi(color.b * 255.0))
			arcs.append(roundi(color.a * 255.0))
		else:
			ops.append(_normalize_op(op))
	_check(_same(ops, expected), "команды озера (_render_lake) без дуг совпадают с Python")
	var arc_count := arcs.size() >> 3
	_check(arc_count == 69 and _weighted_sum(arcs) == 13079308, "дуги озера (_render_lake) совпадают по числу и контрольной сумме")


func _check_view() -> void:
	var view = VIEW_SCRIPT.new()
	_check(not view.is_configured(), "вид до configure не готов")
	var road_image: Image = VIEW_SCRIPT.road_texture(41).get_image()
	_check(road_image != null and _weighted_sum(Array(road_image.get_data())) == 439721101,
		"композит кромки через загрузку вида совпадает с _build_road_tile")
	var canvas := Node2D.new()
	add_child(canvas)
	var visible := Rect2(0.0, 0.0, 1920.0, 1080.0)
	var state := {"calls": 0, "elements": []}
	var draw_view := func() -> void:
		var elements: Array = view.draw(canvas, visible, 1000)
		state["elements"] = elements
		for element in elements:
			element["draw"].call(canvas)
		state["calls"] += 1
	canvas.draw.connect(draw_view)
	view.configure(_tower_terrain())
	_check(view.is_configured(), "вид Башни настраивается по payload с uniform_grass")
	canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(state["calls"] >= 1, "вид Башни рисуется в callback канвы")
	_check_elements(state["elements"])
	view.configure(_legacy_terrain())
	_check(view.is_configured(), "вид без uniform_grass настраивается по тому же payload")
	canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(state["calls"] >= 2 and state["elements"].is_empty(), "вид без uniform_grass рисуется и деревьев переднего плана не имеет")
	canvas.draw.disconnect(draw_view)
	remove_child(canvas)
	canvas.free()


func _check_visible_trees() -> void:
	var sizes := [
		Vector4i(160, 256, 6, 10), Vector4i(160, 288, 6, 10), Vector4i(160, 224, 6, 10),
		Vector4i(160, 256, 6, 10), Vector4i(160, 288, 6, 10), Vector4i(160, 224, 6, 10),
		Vector4i(352, 416, 5, 10), Vector4i(83, 76, 1, 1), Vector4i(82, 84, 1, 1),
		Vector4i(114, 54, 1, 1), Vector4i(114, 54, 1, 1),
	]
	var width := 12
	var height := 8
	var forest := RULES.tile_mask(width, height)
	for x in range(2, 6):
		for y in [2, 3, 4]:
			forest[y * width + x] = 1
	var dry := RULES.tile_mask(width, height)
	for x in width:
		dry[x] = 1
		dry[(height - 1) * width + x] = 1
	var layout := RULES.build_tree_layout(width, height, forest, dry, RULES.prop_anchors([
		{"type": "log", "tiles": [[3, 2], [4, 2]]},
		{"type": "stump", "tiles": [[6, 4]]},
	]))
	# V1: экран 1920x1080 от начала координат, now 1000 мс. Python: 60 слотов деревьев и пней в диапазоне, на экране 50
	var visible := Rect2(0, 0, 1920, 1080)
	var draws := RULES.tree_draws(layout, RULES.tree_ranges(visible, width, height), width, height, 1000, sizes)
	_check(draws.size() == 60 * 4, "V1: 60 слотов деревьев и пней в диапазоне как в Python")
	var flat := []
	for index in range(0, draws.size(), 4):
		var size: Vector4i = sizes[draws[index + 2]]
		var rect := Rect2(draws[index], draws[index + 1], size.x, size.y)
		if visible.intersects(rect):
			flat.append_array([rect.position.x, rect.position.y, rect.size.x, rect.size.y, rect.end.y])
	_check(flat.size() == 50 * 5 and _weighted_sum(flat) == 4757218,
		"V1: 50 видимых слотов с контрольной суммой Python по [x, y, w, h, base_y]")


func _check_elements(elements: Array) -> void:
	_check(elements.size() == 50, "вид: 50 элементов видимых деревьев и пней как в Python")
	var flat := []
	var shape_ok := true
	var ordered := true
	var previous := -INF
	for element in elements:
		if not (element is Dictionary) or element.size() != 3:
			shape_ok = false
			continue
		if not (element.has("base_y") and element.has("rect") and element.has("draw")):
			shape_ok = false
			continue
		var base_y: Variant = element["base_y"]
		var rect: Variant = element["rect"]
		if not (base_y is float and rect is Rect2 and element["draw"] is Callable):
			shape_ok = false
			continue
		shape_ok = shape_ok and absf(base_y - rect.end.y) < 0.001
		ordered = ordered and base_y >= previous
		previous = float(base_y)
		flat.append_array([rect.position.x, rect.position.y, rect.size.x, rect.size.y, base_y])
	_check(shape_ok, "элемент переднего плана: ровно base_y (float), rect (Rect2), draw (Callable); base_y равен низу rect")
	_check(ordered, "элементы переднего плана идут по возрастанию base_y, как слоты в Python")
	_check(_weighted_sum(flat) == 4757218, "вид: кадры, позиции и base_y элементов совпадают с Python")


# Размеры спрайтов как в Python: листы и кадры деревьев, пни и брёвна масштабом 0.5, камни берега, мост и кромки дороги.
func _check_asset_sizes() -> void:
	var sheets: Array = VIEW_SCRIPT.tree_sheet_textures()
	var sheet_sizes := [[960, 512], [960, 576], [960, 448], [960, 512], [960, 576], [960, 448], [1760, 832]]
	var frame_sizes := [[160, 256], [160, 288], [160, 224], [160, 256], [160, 288], [160, 224], [352, 416]]
	var columns := [6, 6, 6, 6, 6, 6, 5]
	for index in sheets.size():
		var sheet: Texture2D = sheets[index]
		_check(sheet != null and sheet.get_width() == sheet_sizes[index][0] and sheet.get_height() == sheet_sizes[index][1],
			"лист дерева %d по размеру файла" % index)
		_check(sheet.get_width() == frame_sizes[index][0] * columns[index] and sheet.get_height() == frame_sizes[index][1] * 2,
			"кадры листа дерева %d кладутся сеткой как в Python" % index)
	var prop_sizes := [[83, 76], [82, 84], [114, 54], [114, 54]]
	var index := 0
	for type_textures in VIEW_SCRIPT.prop_textures():
		for texture in type_textures:
			_check(texture != null and texture.get_width() == prop_sizes[index][0] and texture.get_height() == prop_sizes[index][1],
				"пень или бревно %d масштабом 0.5 с round() как в Python" % index)
			index += 1
	var rims: Array = VIEW_SCRIPT.rim_textures()
	var rim_sizes := [[12, 32], [12, 32], [32, 8], [32, 8]]
	for side in 4:
		var rim: Texture2D = rims[side][0]
		_check(rim != null and rim.get_width() == rim_sizes[side][0] and rim.get_height() == rim_sizes[side][1],
			"камень берега стороны %d без растяжки" % side)
	var bridge: Texture2D = VIEW_SCRIPT.bridge_texture()
	_check(bridge != null and bridge.get_width() == 176 and bridge.get_height() == 110, "мост 176x110 без растяжки")
	var grass: Texture2D = VIEW_SCRIPT.ground_textures()[RULES.GROUND_GRASS_BASE]
	_check(grass != null and grass.get_width() == 32 and grass.get_height() == 32, "тайл земли 32x32")
	var rock_mismatch := 0
	for rock_index in VIEW_SCRIPT.rock_names().size():
		var rock: Texture2D = VIEW_SCRIPT.rock_texture(rock_index)
		if rock == null or rock.get_width() != 32 or rock.get_height() != 32:
			rock_mismatch += 1
	_check(rock_mismatch == 0, "все камни гор 32x32 без растяжки, как в Python")



static func _tower_terrain() -> Dictionary:
	return {
		"map": {"tiles_w": 12, "tiles_h": 8, "uniform_grass": true, "version": 1},
		"tiles": {
			"forest": [[2, 2, 5], [3, 2, 5], [4, 2, 5]],
			"dry": [[0, 0, 11], [7, 0, 11]],
			"water": [[5, 6, 7]],
			"paths": [[4, 0, 0]],
			"mountain": [[3, 2, 3]],
			"partial": [],
		},
		"roads": {"tiles": [[7, 1], [7, 2]]},
		"props": [{"type": "log", "tiles": [[3, 2], [4, 2]]}, {"type": "stump", "tiles": [[6, 4]]}],
		"bridges": [{"tiles": [[2, 4], [3, 4]]}],
		"obstacles": [
			{"id": "tower_1", "type": "tower", "points": [[96, 96], [192, 96], [192, 192], [96, 192]], "passages": [], "hp": 1000, "max_hp": 1000},
			{"id": "mountains_ring_0", "type": "mountains", "points": [[64, 96], [128, 96], [128, 128], [64, 128]], "peaks": [], "passages": []},
		],
		"crystals": [],
	}


static func _legacy_terrain() -> Dictionary:
	var terrain := _tower_terrain()
	terrain["map"]["uniform_grass"] = false
	terrain["obstacles"] = [
		{"id": "forest_1", "type": "forest", "points": [[200, 200], [300, 190], [320, 280], [210, 300]],
			"trees": [{"x": 220, "y": 220, "r": 18}], "passages": []},
		{"id": "lake_1", "type": "lake", "points": [[40, 40], [80, 34], [110, 52], [114, 84], [96, 104], [52, 100], [28, 76], [24, 50]],
			"water_points": [[48, 52], [76, 45], [100, 58], [104, 82], [92, 96], [56, 93], [36, 74], [32, 56]],
			"sandy_shore_sections": [[0.06, 0.2]], "passages": []},
		{"id": "mountains_1", "type": "mountains", "points": [[100, 100], [260, 100], [260, 220], [100, 220]],
			"peaks": [{"x": 200, "y": 200, "w": 90, "h": 180, "kind": "peak"}], "passages": [[180, 150, 30, 40]]},
	]
	return terrain

