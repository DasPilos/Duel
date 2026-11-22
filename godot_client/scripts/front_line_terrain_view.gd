extends RefCounted

# Рельеф Башни: порт отрисовки WorldMapScene.draw() из scenes/world_map_scene.py. Порядок тот же: заливка экрана,
# земля, камни берега, мосты, все деревья и пни, затем препятствия (горы, озёра, леса). Спрайты читаются из
# ../assets/map один раз и кэшируются статически. Башня (_render_tower) не рисуется: это процедурное здание главной карты.
# draw() возвращает элементы {"base_y", "rect", "draw"} для видимых деревьев и пней. Python рисует их повторно поверх
# актёров с меньшей глубиной и пересекающимся прямоугольником (_draw_mobs, 2622–2629); проверку делает вызывающий код,
# рисунок выполняет element["draw"].call(canvas). Координаты мировые; draw_set_transform здесь не вызывается.

const RULES := preload("res://scripts/front_line_terrain_rules.gd")
const TILE := 16
const DEFAULT_TILES_W := 512
const DEFAULT_TILES_H := 256
const BACKGROUND_COLOR := Color8(20, 24, 28)
const LEGACY_ROAD_LINE := Color8(95, 74, 44)
const FALLBACK_GROUND := Color8(40, 60, 40)
const PROP_SCALE := 0.5
const ROCK_SIZE := 32
const ARC_STEPS := 16
# Число файлов земли: трава grass_1..5, подстилка floor_dark_1..4, ягоды berry_1..3 (варианты отражений внутри)
const GRASS_TILE_NAMES := 5
const FLOOR_TILE_NAMES := 4
const BERRY_TILE_NAMES := 3
# [файл листа, размер кадра, колонок в листе]; порядок совпадает с RULES.GREEN_TREE_IDS и DEAD_TREE_IDS
const TREE_SHEETS := [
	["tree1.png", Vector2i(160, 256), 6], ["tree2.png", Vector2i(160, 288), 6], ["tree3.png", Vector2i(160, 224), 6],
	["old_tree1.png", Vector2i(160, 256), 6], ["old_tree2.png", Vector2i(160, 288), 6], ["old_tree3.png", Vector2i(160, 224), 6],
	["big_tree.png", Vector2i(352, 416), 5],
]
# Файлы пней и брёвен по типам RULES.PROP_TYPES; два варианта на тип
const PROP_FILES := [["stump_1.png", "stump_2.png"], ["log_1.png", "log_2.png"]]

static var _textures: Dictionary = {}
static var _edge_bytes: Dictionary = {}
static var _rock_names := PackedStringArray()
static var _rock_infos: Array = []
static var _rock_textures: Array = []

var _configured := false
var _uniform := false
var _width := DEFAULT_TILES_W
var _height := DEFAULT_TILES_H
var _water := PackedByteArray()
var _road := PackedByteArray()
var _ground_index := PackedInt32Array()
var _road_index := PackedInt32Array()
var _cell_color := PackedColorArray()
var _ground_textures: Array = []
var _road_textures: Array = []
var _rim_textures: Array = []
var _rim_sizes: Array = []
var _sprite_textures: Array = []
var _sprite_sizes: Array = []
var _tree_layout: Dictionary = {}
var _bridges: Array = []
var _obstacles: Array = []


# Рельеф из /api/map/terrain: строки тайлов, дороги, пни, мосты и препятствия. Для карт без uniform_grass
# отрисовка идёт плоскими клетками и контурами, как в Python без спрайтов.
func configure(terrain: Dictionary) -> void:
	_configured = false
	_bridges.clear()
	_obstacles.clear()
	_tree_layout = {}
	var map_info := _dictionary(terrain.get("map", {}))
	_width = maxi(1, int(map_info.get("tiles_w", DEFAULT_TILES_W)))
	_height = maxi(1, int(map_info.get("tiles_h", DEFAULT_TILES_H)))
	_uniform = bool(map_info.get("uniform_grass", false))
	var tiles := _dictionary(terrain.get("tiles", {}))
	var forest := RULES.tile_mask(_width, _height)
	RULES.fill_tile_rows(forest, _array(tiles.get("forest", [])), _width, _height)
	var dry := RULES.tile_mask(_width, _height)
	RULES.fill_tile_rows(dry, _array(tiles.get("dry", [])), _width, _height)
	var mountain := RULES.tile_mask(_width, _height)
	RULES.fill_tile_rows(mountain, _array(tiles.get("mountain", [])), _width, _height)
	_water = RULES.tile_mask(_width, _height)
	RULES.fill_tile_rows(_water, _array(tiles.get("water", [])), _width, _height)
	_road = RULES.tile_mask(_width, _height)
	RULES.fill_tile_rows(_road, _array(tiles.get("paths", [])), _width, _height)
	RULES.fill_tile_points(_road, _array(_dictionary(terrain.get("roads", {})).get("tiles", [])), _width, _height)
	var anchors := RULES.prop_anchors(_array(terrain.get("props", [])))
	var obstacles := _array(terrain.get("obstacles", []))
	if _uniform:
		_configure_uniform(forest, dry, anchors, _array(terrain.get("bridges", [])), obstacles)
	else:
		_configure_flat()
	var roles := {}
	if _uniform and _has_mountains(obstacles):
		roles = RULES.mountain_roles(_mountain_cells(mountain), rock_infos())
	for obstacle in obstacles:
		if obstacle is Dictionary:
			_add_obstacle(obstacle, roles)
	_configured = true


func is_configured() -> bool:
	return _configured


# Фон до актёров, как WorldMapScene.draw() до _draw_mobs: заливка экрана, земля, камни берега, мосты, все деревья и пни,
# препятствия. Возвращает элементы видимых деревьев и пней: {"base_y": float, "rect": Rect2, "draw": Callable(canvas)}.
# rect — спрайт, поставленный низом по центру в (base_x, base_y), как tree.get_rect(midbottom=...) при масштабе 1;
# base_y — нижняя граница rect. Элементы идут по возрастанию base_y, как слоты в Python.
func draw(canvas: CanvasItem, visible_world: Rect2, now_msec: int) -> Array:
	if not _configured:
		return []
	canvas.draw_rect(visible_world, BACKGROUND_COLOR)
	var ranges := RULES.ground_ranges(visible_world, _width, _height)
	_draw_ground(canvas, ranges)
	var trees: Array = []
	if _uniform:
		_draw_shore_rims(canvas, ranges)
		_draw_bridges(canvas, visible_world)
		trees = _draw_trees(canvas, visible_world, now_msec)
	for obstacle in _obstacles:
		if not visible_world.intersects(obstacle["rect"]):
			continue
		if obstacle["kind"] == "tiles":
			_draw_tiles(canvas, obstacle["pieces"], visible_world)
		else:
			for op in obstacle["ops"]:
				_draw_op(canvas, op)
	return trees


func _configure_uniform(forest: PackedByteArray, dry: PackedByteArray, anchors: Array, bridges: Array, obstacles: Array) -> void:
	var count := _width * _height
	var cover := PackedByteArray()
	cover.resize(count)
	for index in count:
		cover[index] = 1 if forest[index] != 0 or dry[index] != 0 else 0
	var kinds := RULES.ground_kinds(cover, _width, _height)
	_ground_textures = ground_textures()
	_ground_index.resize(count)
	_road_index.resize(count)
	_road_textures = []
	_road_textures.resize(RULES.ROAD_PIECE_COUNT)
	for gy in _height:
		for gx in _width:
			var index := gy * _width + gx
			if _water[index] != 0:
				_ground_index[index] = RULES.water_texture_index(gx, gy)
				_road_index[index] = -1
				continue
			_ground_index[index] = RULES.ground_texture_index(kinds[index], RULES.map_hash(gx, gy))
			var piece := RULES.road_piece(_road, _width, _height, gx, gy)
			_road_index[index] = piece
			if piece >= 0 and _road_textures[piece] == null:
				_road_textures[piece] = road_texture(piece)
	_rim_textures = rim_textures()
	_rim_sizes = []
	for side in 4:
		var rim: Texture2D = _rim_textures[side][0]
		_rim_sizes.append(Vector2i(rim.get_width(), rim.get_height()) if rim != null else Vector2i.ZERO)
	_sprite_textures = []
	_sprite_sizes = []
	var sheets := tree_sheet_textures()
	for index in TREE_SHEETS.size():
		var sheet: Array = TREE_SHEETS[index]
		var frame_size: Vector2i = sheet[1]
		_sprite_textures.append(sheets[index])
		_sprite_sizes.append(Vector4i(frame_size.x, frame_size.y, int(sheet[2]), RULES.TREE_FRAMES))
	var props := prop_textures()
	for type_index in PROP_FILES.size():
		for variant in 2:
			var prop: Texture2D = props[type_index][variant]
			_sprite_textures.append(prop)
			var prop_size := Vector2i(prop.get_width(), prop.get_height()) if prop != null else Vector2i.ZERO
			_sprite_sizes.append(Vector4i(prop_size.x, prop_size.y, 1, 1))
	_tree_layout = RULES.build_tree_layout(_width, _height, forest, dry, anchors)
	var bridge_tex := bridge_texture()
	if bridge_tex != null:
		var bridge_size := Vector2i(bridge_tex.get_width(), bridge_tex.get_height())
		for bridge in bridges:
			if not bridge is Dictionary:
				continue
			var tiles := _array(bridge.get("tiles", []))
			if tiles.is_empty():
				continue
			var top_left := RULES.bridge_top_left(tiles, bridge_size)
			_bridges.append({"rect": Rect2(Vector2(top_left), Vector2(bridge_size)), "texture": bridge_tex})


func _configure_flat() -> void:
	var count := _width * _height
	var half := RULES.floor_div(_height, 2)
	_cell_color.resize(count)
	for gy in _height:
		for gx in _width:
			var index := gy * _width + gx
			_cell_color[index] = RULES.flat_cell_color(gx, gy, half, _road[index] != 0)


func _has_mountains(obstacles: Array) -> bool:
	for obstacle in obstacles:
		if obstacle is Dictionary and str(obstacle.get("type", "")) == "mountains":
			return true
	return false


func _mountain_cells(mountain: PackedByteArray) -> Array:
	var cells: Array = []
	for index in mountain.size():
		if mountain[index] != 0:
			cells.append(Vector2i(index % _width, RULES.floor_div(index, _width)))
	return cells


func _add_obstacle(obstacle: Dictionary, roles: Dictionary) -> void:
	var kind := str(obstacle.get("type", ""))
	if kind == "tower":
		return
	var points := _points(obstacle.get("points", []))
	if points.is_empty():
		return
	if kind == "mountains" and _uniform:
		_add_tile_mountain(points, roles)
		return
	var result: Dictionary
	if kind == "forest":
		result = RULES.forest_ops(points, _array(obstacle.get("trees", [])))
	elif kind == "lake":
		var water := _points(obstacle.get("water_points", []))
		if water.is_empty():
			return
		result = RULES.lake_ops(points, water, _array(obstacle.get("sandy_shore_sections", [])))
	else:
		result = RULES.mountain_ops(points, _array(obstacle.get("peaks", [])), _passages(obstacle.get("passages", [])))
	var origin := Vector2(result["origin"])
	_obstacles.append({
		"kind": "ops",
		"rect": Rect2(origin, Vector2(result["size"])),
		"ops": _world_ops(result["ops"], origin),
	})


# Горный венец целыми клетками: клетка обрезается по прямоугольнику препятствия, как поверхность в Python.
func _add_tile_mountain(points: PackedVector2Array, roles: Dictionary) -> void:
	var bounds := RULES.points_bounds(points)
	var raw := RULES.mountain_pieces(bounds, roles)
	var pieces: Array = []
	for index in range(0, raw.size(), 5):
		var texture := rock_texture(raw[index + 4])
		if texture == null:
			continue
		var dest := Rect2(raw[index], raw[index + 1], raw[index + 2], raw[index + 3])
		pieces.append([dest, Rect2(Vector2.ZERO, dest.size), texture])
	_obstacles.append({"kind": "tiles", "rect": Rect2(bounds), "pieces": pieces})


func _draw_ground(canvas: CanvasItem, ranges: Vector4i) -> void:
	for gy in range(ranges.z, ranges.w):
		for gx in range(ranges.x, ranges.y):
			var index := gy * _width + gx
			var position := Vector2(gx * TILE, gy * TILE)
			if _uniform:
				_blit(canvas, _ground_textures[_ground_index[index]], position)
				var piece := _road_index[index]
				if piece >= 0 and _road_textures[piece] != null:
					canvas.draw_texture(_road_textures[piece], position)
			else:
				canvas.draw_rect(Rect2(position, Vector2(TILE + 1, TILE + 1)), _cell_color[index])
				if _road[index] != 0:
					canvas.draw_rect(Rect2(position, Vector2(TILE + 1, 1)), LEGACY_ROAD_LINE)
					canvas.draw_rect(Rect2(position + Vector2(0, TILE), Vector2(TILE + 1, 1)), LEGACY_ROAD_LINE)


func _draw_shore_rims(canvas: CanvasItem, ranges: Vector4i) -> void:
	var draws := RULES.shore_rim_draws(_water, _width, _height, ranges, _rim_sizes)
	for index in range(0, draws.size(), 4):
		var texture: Texture2D = _rim_textures[draws[index + 2]][draws[index + 3]]
		if texture != null:
			canvas.draw_texture(texture, Vector2(draws[index], draws[index + 1]))


func _draw_bridges(canvas: CanvasItem, visible: Rect2) -> void:
	for bridge in _bridges:
		if visible.intersects(bridge["rect"]):
			canvas.draw_texture(bridge["texture"], bridge["rect"].position)


func _draw_trees(canvas: CanvasItem, visible: Rect2, now_msec: int) -> Array:
	var elements: Array = []
	var ranges := RULES.tree_ranges(visible, _width, _height)
	var draws := RULES.tree_draws(_tree_layout, ranges, _width, _height, now_msec, _sprite_sizes)
	for index in range(0, draws.size(), 4):
		var sprite := draws[index + 2]
		var size: Vector4i = _sprite_sizes[sprite]
		var texture: Texture2D = _sprite_textures[sprite]
		var rect := Rect2(draws[index], draws[index + 1], size.x, size.y)
		if texture == null or not visible.intersects(rect):
			continue
		var source := _frame_source(size, draws[index + 3])
		canvas.draw_texture_rect_region(texture, rect, source)
		elements.append({"base_y": rect.end.y, "rect": rect, "draw": _sprite_drawer(texture, rect, source)})
	return elements


static func _frame_source(size: Vector4i, frame: int) -> Rect2:
	return Rect2((frame % size.z) * size.x, RULES.floor_div(frame, size.z) * size.y, size.x, size.y)


static func _sprite_drawer(texture: Texture2D, dest: Rect2, source: Rect2) -> Callable:
	return func(canvas: CanvasItem) -> void:
		canvas.draw_texture_rect_region(texture, dest, source)


func _draw_tiles(canvas: CanvasItem, pieces: Array, visible: Rect2) -> void:
	for piece in pieces:
		var dest: Rect2 = piece[0]
		if visible.intersects(dest):
			canvas.draw_texture_rect_region(piece[2], dest, piece[1])


func _draw_op(canvas: CanvasItem, op: Dictionary) -> void:
	match op["kind"]:
		"polygon":
			canvas.draw_colored_polygon(op["points"], op["color"])
		"polyline":
			canvas.draw_polyline(op["points"], op["color"], op["width"])
		"line":
			canvas.draw_line(op["from"], op["to"], op["color"], op["width"])
		"circle":
			canvas.draw_circle(op["centre"], op["radius"], op["color"])
		"clear":
			_repaint_ground(canvas, op["rect"])


# Очистка прямоугольника поверхности в Python открывает землю под горой: здесь землю перерисовывают поверх.
func _repaint_ground(canvas: CanvasItem, rect: Rect2) -> void:
	if not rect.has_area():
		return
	var first_x := floori(rect.position.x / TILE)
	var last_x := floori((rect.end.x - 1.0) / TILE)
	var first_y := floori(rect.position.y / TILE)
	var last_y := floori((rect.end.y - 1.0) / TILE)
	for gy in range(first_y, last_y + 1):
		for gx in range(first_x, last_x + 1):
			var tile := Rect2(gx * TILE, gy * TILE, TILE + 1, TILE + 1)
			if gx < 0 or gy < 0 or gx >= _width or gy >= _height:
				canvas.draw_rect(tile.intersection(rect), BACKGROUND_COLOR)
				continue
			var index := gy * _width + gx
			canvas.draw_rect(tile.intersection(rect), _cell_color[index])
			if _road[index] != 0:
				var top_line := Rect2(tile.position.x, tile.position.y, TILE + 1, 1).intersection(rect)
				var bottom_line := Rect2(tile.position.x, tile.position.y + TILE, TILE + 1, 1).intersection(rect)
				if top_line.has_area():
					canvas.draw_rect(top_line, LEGACY_ROAD_LINE)
				if bottom_line.has_area():
					canvas.draw_rect(bottom_line, LEGACY_ROAD_LINE)


static func ground_textures() -> Array:
	if not _textures.has("ground"):
		var list: Array = []
		for index in RULES.GROUND_WATER_COUNT:
			list.append(_texture_from(_load_rgba(map_root().path_join("tiles/water_%d.png" % (index + 1)))))
		for index in GRASS_TILE_NAMES:
			list.append_array(_flip_textures(map_root().path_join("tiles/grass_%d.png" % (index + 1))))
		for index in FLOOR_TILE_NAMES:
			list.append_array(_flip_textures(map_root().path_join("tiles/floor_dark_%d.png" % (index + 1))))
		for index in BERRY_TILE_NAMES:
			list.append_array(_flip_textures(map_root().path_join("tiles/berry_%d.png" % (index + 1))))
		_textures["ground"] = list
	return _textures["ground"]


static func rim_textures() -> Array:
	if not _textures.has("rims"):
		var left: Array = []
		var right: Array = []
		var top: Array = []
		var bottom: Array = []
		for index in RULES.SHORE_VARIANTS:
			var from_left := _flip_textures(map_root().path_join("rims/shore_left_%d.png" % index))
			left.append(from_left[0])
			right.append(from_left[1])
			var from_bottom := _flip_textures(map_root().path_join("rims/shore_bottom_%d.png" % index))
			bottom.append(from_bottom[0])
			top.append(from_bottom[2])
		_textures["rims"] = [left, right, top, bottom]
	return _textures["rims"]


static func tree_sheet_textures() -> Array:
	if not _textures.has("trees"):
		var list: Array = []
		for sheet in TREE_SHEETS:
			list.append(_texture_from(_load_rgba(map_root().path_join("trees/" + sheet[0]))))
		_textures["trees"] = list
	return _textures["trees"]


static func prop_textures() -> Array:
	if not _textures.has("props"):
		var types: Array = []
		for names in PROP_FILES:
			var variants: Array = []
			for file_name in names:
				variants.append(_scaled_prop(map_root().path_join("props/" + file_name)))
			types.append(variants)
		_textures["props"] = types
	return _textures["props"]


static func bridge_texture() -> Texture2D:
	if not _textures.has("bridge"):
		_textures["bridge"] = _texture_from(_load_rgba(map_root().path_join("props/bridge_horizontal.png")))
	return _textures["bridge"]


# Кусок дороги: ядро (0–3) или композит кромок (min по каналам), собирается один раз на вид.
static func road_texture(piece: int) -> Texture2D:
	var key := "road|%d" % piece
	if not _textures.has(key):
		var image: Image = null
		if piece < RULES.ROAD_CORE_COUNT:
			image = _load_rgba(map_root().path_join("tiles/road_core_%d.png" % (piece + 1)))
		else:
			var local := piece - RULES.ROAD_CORE_COUNT
			var sides := RULES.floor_div(local, RULES.ROAD_EDGE_VARIANTS) + 1
			var variant := local % RULES.ROAD_EDGE_VARIANTS
			var edges: Array = []
			for side in RULES.ROAD_SIDE_NAMES.size():
				if sides & (1 << side):
					edges.append(_road_edge_bytes(RULES.ROAD_SIDE_NAMES[side], variant))
			var complete := true
			for edge in edges:
				if edge.is_empty():
					complete = false
			if complete and not edges.is_empty():
				image = Image.create_from_data(TILE, TILE, false, Image.FORMAT_RGBA8, RULES.road_composite(edges))
		_textures[key] = _texture_from(image)
	return _textures[key]


static func rock_names() -> PackedStringArray:
	if _rock_names.is_empty():
		var names := PackedStringArray()
		for file_name in DirAccess.get_files_at(map_root().path_join("mountains")):
			if file_name.begins_with("rock_") and file_name.ends_with(".png"):
				names.append(file_name.get_basename())
		names.sort()
		_rock_names = names
	return _rock_names


static func rock_infos() -> Array:
	if _rock_infos.is_empty() and not rock_names().is_empty():
		var infos: Array = []
		for name in rock_names():
			var image := _load_rgba(map_root().path_join("mountains/%s.png" % name))
			var rgba := image.get_data() if image != null else PackedByteArray()
			if rgba.size() != ROCK_SIZE * ROCK_SIZE * 4:
				rgba = PackedByteArray()
				rgba.resize(ROCK_SIZE * ROCK_SIZE * 4)
			infos.append(RULES.rock_info(ROCK_SIZE, rgba))
		_rock_infos = infos
	return _rock_infos


static func rock_texture(index: int) -> Texture2D:
	var names := rock_names()
	if _rock_textures.size() != names.size():
		_rock_textures.resize(names.size())
	if index < 0 or index >= names.size():
		return null
	if _rock_textures[index] == null:
		_rock_textures[index] = _texture_from(_load_rgba(map_root().path_join("mountains/%s.png" % names[index])))
	return _rock_textures[index]


static func map_root() -> String:
	return ProjectSettings.globalize_path("res://").path_join("../assets/map").simplify_path()


static func _load_rgba(path: String) -> Image:
	if not FileAccess.file_exists(path):
		return null
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		return null
	image.convert(Image.FORMAT_RGBA8)
	return image


static func _texture_from(image: Image) -> Texture2D:
	return ImageTexture.create_from_image(image) if image != null else null


# Четыре варианта по порядку pygame: как есть, по горизонтали, по вертикали, по обеим осям.
static func _flip_textures(path: String) -> Array:
	var key := "flip|" + path
	if not _textures.has(key):
		var base := _load_rgba(path)
		if base == null:
			_textures[key] = [null, null, null, null]
		else:
			var flip_x := base.duplicate() as Image
			flip_x.flip_x()
			var flip_y := base.duplicate() as Image
			flip_y.flip_y()
			var flip_xy := flip_x.duplicate() as Image
			flip_xy.flip_y()
			_textures[key] = [_texture_from(base), _texture_from(flip_x), _texture_from(flip_y), _texture_from(flip_xy)]
	return _textures[key]


static func _scaled_prop(path: String) -> Texture2D:
	var image := _load_rgba(path)
	if image == null:
		return null
	var size := Vector2i(
		RULES.py_round(image.get_width() * PROP_SCALE),
		RULES.py_round(image.get_height() * PROP_SCALE),
	)
	image.resize(size.x, size.y, Image.INTERPOLATE_BILINEAR)
	return _texture_from(image)


static func _road_edge_bytes(side: String, variant: int) -> PackedByteArray:
	var key := "%s|%d" % [side, variant]
	if not _edge_bytes.has(key):
		var image := _load_rgba(map_root().path_join("tiles/road_edge_%s_%d.png" % [side, variant + 1]))
		_edge_bytes[key] = image.get_data() if image != null else PackedByteArray()
	return _edge_bytes[key]


static func _blit(canvas: CanvasItem, texture: Texture2D, position: Vector2) -> void:
	if texture != null:
		canvas.draw_texture(texture, position)
	else:
		canvas.draw_rect(Rect2(position, Vector2(TILE, TILE)), FALLBACK_GROUND)


# Координаты препятствий в локальной системе поверхности Python переводятся в мировые один раз.
static func _world_ops(ops: Array, origin: Vector2) -> Array:
	var result: Array = []
	for op in ops:
		var color: Color = op.get("color", Color.WHITE)
		match op["kind"]:
			"polygon":
				var polygon := _shifted(op["points"], origin, false)
				if polygon.size() >= 3:
					result.append({"kind": "polygon", "color": color, "points": polygon})
			"outline", "lines":
				var closed: bool = op["kind"] == "outline" or bool(op["closed"])
				var outline := _shifted(op["points"], origin, closed)
				if outline.size() >= 2:
					result.append({"kind": "polyline", "color": color, "points": outline, "width": op["width"]})
			"line":
				var line_points: PackedVector2Array = op["points"]
				result.append({"kind": "line", "color": color, "from": line_points[0] + origin, "to": line_points[1] + origin, "width": op["width"]})
			"circle":
				result.append({"kind": "circle", "color": color, "centre": op["centre"] + origin, "radius": op["radius"]})
			"arc":
				var rect: Rect2 = op["rect"]
				var arc := _arc_points(Rect2(rect.position + origin, rect.size), op["start"], op["stop"])
				result.append({"kind": "polyline", "color": color, "points": arc, "width": op["width"]})
			"clear":
				var cleared: Rect2 = op["rect"]
				result.append({"kind": "clear", "rect": Rect2(cleared.position + origin, cleared.size)})
	return result


static func _shifted(points: PackedVector2Array, origin: Vector2, closed: bool) -> PackedVector2Array:
	var result := PackedVector2Array()
	for point in points:
		result.append(point + origin)
	if closed and not points.is_empty():
		result.append(points[0] + origin)
	return result


# Дуга pygame.draw.arc: эллипс внутри прямоугольника, угол против часовой стрелки, экранный y вниз.
static func _arc_points(rect: Rect2, start: float, stop: float) -> PackedVector2Array:
	var centre := rect.get_center()
	var radius := rect.size * 0.5
	var points := PackedVector2Array()
	for step in ARC_STEPS + 1:
		var angle := start + (stop - start) * step / ARC_STEPS
		points.append(Vector2(centre.x + radius.x * cos(angle), centre.y - radius.y * sin(angle)))
	return points


static func _points(source: Variant) -> PackedVector2Array:
	var points := PackedVector2Array()
	if source is Array:
		for point in source:
			if point is Array and point.size() >= 2:
				points.append(Vector2(float(point[0]), float(point[1])))
	return points


static func _passages(source: Variant) -> Array:
	var passages: Array = []
	if source is Array:
		for passage in source:
			if passage is Array and passage.size() >= 4:
				passages.append(Rect2i(int(passage[0]), int(passage[1]), int(passage[2]), int(passage[3])))
	return passages


static func _array(value: Variant) -> Array:
	return value if value is Array else []


static func _dictionary(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}
