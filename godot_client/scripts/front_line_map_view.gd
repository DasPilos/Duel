extends RefCounted

const MAP_TILE_SIZE := 32.0
const ATLAS_TILE_SIZE := 16
const ATLAS_CELL_PREFIX := "atlas|"

static var _texture_cache: Dictionary = {}
static var _image_cache: Dictionary = {}
static var _animation_cache: Dictionary = {}

var _map_layers: Array[Dictionary] = []
var _map_width := 0
var _map_height := 0


func configure(map_data: Variant) -> void:
	_map_layers.clear()
	_map_width = 0
	_map_height = 0
	if not map_data is Dictionary:
		return
	var source_layers: Variant = map_data.get("layers", [])
	if not source_layers is Array:
		return
	_map_width = maxi(1, int(map_data.get("map_w", 1)))
	_map_height = maxi(1, int(map_data.get("map_h", 1)))
	for layer_value in source_layers:
		if not layer_value is Dictionary or not bool(layer_value.get("visible", true)):
			continue
		var source_cells: Variant = layer_value.get("cells", [])
		if not source_cells is Array:
			continue
		var map_image := Image.create(
			_map_width * ATLAS_TILE_SIZE,
			_map_height * ATLAS_TILE_SIZE,
			false,
			Image.FORMAT_RGBA8,
		)
		var has_tiles := false
		var animated_cells: Array[Dictionary] = []
		for cell_value in source_cells:
			if not cell_value is Dictionary:
				continue
			var x := int(cell_value.get("x", -1))
			var y := int(cell_value.get("y", -1))
			if x < 0 or y < 0 or x >= _map_width or y >= _map_height:
				continue
			var parts := _atlas_parts(str(cell_value.get("key", "")))
			if parts.is_empty():
				continue
			var source_image := _image(str(parts[0]))
			if source_image == null:
				continue
			var source := Rect2i(
				Vector2i(int(parts[1]), int(parts[2])) * ATLAS_TILE_SIZE,
				Vector2i.ONE * ATLAS_TILE_SIZE,
			)
			if source.end.x > source_image.get_width() or source.end.y > source_image.get_height():
				continue
			var source_tile_id := int(parts[2]) * (source_image.get_width() / ATLAS_TILE_SIZE) + int(parts[1])
			var frames := _sheet_animations(str(parts[0]), source_image.get_width() / ATLAS_TILE_SIZE).get(
				source_tile_id,
				[],
			) as Array
			map_image.blend_rect(
				source_image,
				source,
				Vector2i(x, y) * ATLAS_TILE_SIZE,
			)
			if frames.size() > 1:
				map_image.fill_rect(
					Rect2i(Vector2i(x, y) * ATLAS_TILE_SIZE, Vector2i.ONE * ATLAS_TILE_SIZE),
					Color.TRANSPARENT,
				)
				animated_cells.append({
					"position": Vector2i(x, y),
					"texture": _texture(str(parts[0])),
					"columns": source_image.get_width() / ATLAS_TILE_SIZE,
					"fallback_tile_id": source_tile_id,
					"frames": frames,
				})
			has_tiles = true
		if has_tiles:
			_map_layers.append({
				"texture": ImageTexture.create_from_image(map_image),
				"animated_cells": animated_cells,
			})


func draw(canvas: CanvasItem, visible_world: Rect2) -> void:
	var destination := Rect2(
		Vector2.ZERO,
		Vector2(_map_width, _map_height) * MAP_TILE_SIZE,
	)
	if not visible_world.intersects(destination):
		return
	for layer in _map_layers:
		var layer_texture: Texture2D = layer["texture"]
		canvas.draw_texture_rect(layer_texture, destination, false)
		for cell in layer["animated_cells"]:
			var cell_position: Vector2i = cell["position"]
			var tile_destination := Rect2(
				Vector2(cell_position) * MAP_TILE_SIZE,
				Vector2.ONE * MAP_TILE_SIZE,
			)
			if not visible_world.intersects(tile_destination):
				continue
			var columns := int(cell["columns"])
			var tile_id := _animation_frame_tile_id(
				cell["frames"],
				Time.get_ticks_msec(),
				int(cell["fallback_tile_id"]),
			)
			var source := Rect2(
				Vector2(tile_id % columns, tile_id / columns) * ATLAS_TILE_SIZE,
				Vector2.ONE * ATLAS_TILE_SIZE,
			)
			canvas.draw_texture_rect_region(cell["texture"], tile_destination, source)


func animated_tile_count() -> int:
	var total := 0
	for layer in _map_layers:
		total += (layer["animated_cells"] as Array).size()
	return total


static func _animation_frame_tile_id(frames: Array, elapsed_msec: int, fallback_tile_id: int) -> int:
	if frames.is_empty():
		return fallback_tile_id
	var cycle_duration := 0
	for frame in frames:
		cycle_duration += maxi(int(frame.get("duration", 100)), 1)
	if cycle_duration <= 0:
		return fallback_tile_id
	var frame_time := posmod(elapsed_msec, cycle_duration)
	for frame in frames:
		frame_time -= maxi(int(frame.get("duration", 100)), 1)
		if frame_time < 0:
			return int(frame.get("tile_id", fallback_tile_id))
	return fallback_tile_id


static func _sheet_animations(sheet_path: String, columns: int) -> Dictionary:
	var cache_key := "%s|%d" % [sheet_path, columns]
	if _animation_cache.has(cache_key):
		return _animation_cache[cache_key] as Dictionary
	var animations: Dictionary = {}
	var directory := DirAccess.open(sheet_path.get_base_dir())
	if directory == null:
		_animation_cache[cache_key] = animations
		return animations
	for file_name in directory.get_files():
		if file_name.begins_with("._") or file_name.get_extension().to_lower() not in ["tmx", "tsx"]:
			continue
		_read_animation_metadata(
			sheet_path.get_base_dir().path_join(file_name),
			sheet_path.get_file(),
			animations,
		)
	_animation_cache[cache_key] = animations
	return animations


static func _read_animation_metadata(metadata_path: String, sheet_file_name: String, animations: Dictionary) -> void:
	var parser := XMLParser.new()
	if parser.open(metadata_path) != OK:
		return
	var image_name := ""
	var tile_id := -1
	var frames: Array[Dictionary] = []
	while true:
		var error := parser.read()
		if error == ERR_FILE_EOF:
			break
		if error != OK:
			push_warning("Front Line: ошибка чтения анимаций тайлов из %s" % metadata_path)
			break
		if parser.get_node_type() == XMLParser.NODE_ELEMENT:
			match parser.get_node_name():
				"tileset":
					image_name = ""
				"image":
					image_name = parser.get_named_attribute_value("source").get_file()
				"tile":
					tile_id = int(parser.get_named_attribute_value("id"))
					frames.clear()
				"frame":
					if tile_id >= 0:
						frames.append({
							"tile_id": int(parser.get_named_attribute_value("tileid")),
							"duration": int(parser.get_named_attribute_value("duration")),
						})
		elif parser.get_node_type() == XMLParser.NODE_ELEMENT_END and parser.get_node_name() == "tile":
			if image_name.to_lower() == sheet_file_name.to_lower() and not frames.is_empty():
				animations[tile_id] = frames.duplicate()
			tile_id = -1
			frames.clear()


static func _atlas_parts(key: String) -> PackedStringArray:
	if not key.begins_with(ATLAS_CELL_PREFIX):
		return PackedStringArray()
	var parts := key.trim_prefix(ATLAS_CELL_PREFIX).split("|")
	if parts.size() not in [3, 5, 6] or parts[0].is_empty():
		return PackedStringArray()
	if not parts[1].is_valid_int() or not parts[2].is_valid_int():
		return PackedStringArray()
	return PackedStringArray([parts[0], parts[1], parts[2]])


static func _image(path: String) -> Image:
	if _image_cache.has(path):
		return _image_cache[path] as Image
	var texture := _texture(path)
	if texture == null:
		return null
	var image := texture.get_image()
	if image == null:
		push_warning("Front Line: не удалось прочитать тайловый атлас: %s" % path)
		return null
	if image.is_compressed():
		var error := image.decompress()
		if error != OK:
			push_warning("Front Line: не удалось распаковать тайловый атлас: %s" % path)
			return null
	image.convert(Image.FORMAT_RGBA8)
	_image_cache[path] = image
	return image


static func _texture(path: String) -> Texture2D:
	if _texture_cache.has(path):
		return _texture_cache[path] as Texture2D
	if not ResourceLoader.exists(path):
		push_warning("Front Line: не найден тайловый атлас карты: %s" % path)
		_texture_cache[path] = null
		return null
	var texture := ResourceLoader.load(path) as Texture2D
	if texture == null:
		push_warning("Front Line: не удалось загрузить тайловый атлас карты: %s" % path)
	_texture_cache[path] = texture
	return texture
