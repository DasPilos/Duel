extends Node2D

const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const TILESET_BUILDER = preload("res://scripts/terrain_tileset_builder.gd")
const ATLAS_PATH := "res://assets/base_tails/Biome/craftpix-net-477432-flying-islands-pixel-art-top-down-tileset/Tiled_files/Ground_grass.png"
const MAP_OFFSET := Vector2(280, 56)

var _tile_map: TileMapLayer
var _status: Label
var _painted_cells: Dictionary = {}
var _stroke_cells: Dictionary = {}
var _source_id := 0
var _base_tile := Vector2i.ZERO
var _painting := false
var _erasing := false
var _zoom := 1.0


func _ready() -> void:
	_build_background()
	_tile_map = TileMapLayer.new()
	_tile_map.position = MAP_OFFSET
	add_child(_tile_map)
	_build_toolbar()
	var atlas_texture := load(ATLAS_PATH) as Texture2D
	if atlas_texture == null:
		_status.text = "Не удалось загрузить 16×16 атлас: " + ATLAS_PATH
		return
	var source_image := atlas_texture.get_image()
	if source_image.is_empty():
		_status.text = "Не удалось прочитать изображение атласа: " + ATLAS_PATH
		return
	var result: Dictionary = TILESET_BUILDER.build(source_image)
	if result.has("error"):
		_status.text = str(result["error"])
		return
	if int(result.get("terrain_tile_count", 0)) == 0:
		_status.text = "В атласе не найдены непрозрачные центры тайлов для Terrain."
		return
	_tile_map.tile_set = result["tile_set"]
	_source_id = int(result["source_id"])
	_base_tile = result["base_tile"]
	_status.text = "Основа: Ground_grass (%d,%d), набор острова. ЛКМ рисует, ПКМ стирает. Ctrl+колесо — масштаб." % [
		_base_tile.x,
		_base_tile.y,
	]
	print("Terrain prototype: Ground_grass base %s, %d base/edge candidates." % [
		str(_base_tile),
		int(result["terrain_tile_count"]),
	])
	if DisplayServer.get_name() == "headless":
		_run_headless_smoke_test()


func _build_toolbar() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(14, 14)
	panel.custom_minimum_size = Vector2(250, 0)
	layer.add_child(panel)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 10)
	panel.add_child(content)
	var back_button := Button.new()
	back_button.text = "Назад в редактор карт"
	back_button.pressed.connect(_return_to_editor)
	content.add_child(back_button)
	var heading := Label.new()
	heading.text = "Godot Terrain · 16×16"
	heading.add_theme_font_size_override("font_size", 20)
	content.add_child(heading)
	var help := Label.new()
	help.text = "Основа: Ground_grass (2, 2)\nЛКМ — рисовать основу; после отпускания появляются края\nПКМ — стирать · Ctrl + колесо — масштаб"
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(help)
	var clear_button := Button.new()
	clear_button.text = "Очистить карту"
	clear_button.pressed.connect(_clear_map)
	content.add_child(clear_button)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.custom_minimum_size.y = 90
	content.add_child(_status)


func _build_background() -> void:
	var background := ColorRect.new()
	background.color = Color(0.16, 0.29, 0.43)
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)


func _return_to_editor() -> void:
	SCENE_TRANSITION.run(get_tree(), _change_to_editor)


func _change_to_editor() -> void:
	var error := get_tree().change_scene_to_file("res://scenes/map_editor.tscn")
	if error != OK:
		_status.text = "Не удалось открыть редактор карт: " + error_string(error)


func _run_headless_smoke_test() -> void:
	var test_shapes: Array[Array] = [
		[Vector2i(1, 1)],
		[Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0), Vector2i(3, 0)],
		[Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0), Vector2i(0, 1), Vector2i(0, 2)],
		[
			Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0),
			Vector2i(0, 1), Vector2i(1, 1), Vector2i(2, 1),
			Vector2i(0, 2), Vector2i(1, 2), Vector2i(2, 2),
		],
	]
	var expected_shape_tiles: Array[Array] = [
		[Vector2i(1, 1)],
		[Vector2i(1, 1), Vector2i(2, 1), Vector2i(2, 1), Vector2i(3, 1)],
		[Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 1), Vector2i(1, 2), Vector2i(1, 3)],
		[
			Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 1),
			Vector2i(1, 2), Vector2i(2, 2), Vector2i(3, 2),
			Vector2i(1, 3), Vector2i(2, 3), Vector2i(3, 3),
		],
	]
	for shape_index in range(test_shapes.size()):
		var test_cells: Array[Vector2i] = []
		for cell in test_shapes[shape_index]:
			test_cells.append(cell)
			_paint_cell(cell)
			if _tile_map.get_cell_atlas_coords(cell) != _base_tile:
				push_error("Во время рисования должна оставаться бирюзовая основа в %s." % str(cell))
				_tile_map.clear()
				_painted_cells.clear()
				_stroke_cells.clear()
				return
		_finish_paint_stroke()
		var resolved_count := 0
		for cell in test_cells:
			if _tile_map.get_cell_source_id(cell) == _source_id:
				resolved_count += 1
		if resolved_count != test_cells.size():
			push_error("Terrain не подобрал тайлы для формы %d (%d/%d)." % [shape_index + 1, resolved_count, test_cells.size()])
			_tile_map.clear()
			return
		for cell_index in range(test_cells.size()):
			var cell := test_cells[cell_index]
			var expected_tile: Vector2i = expected_shape_tiles[shape_index][cell_index]
			if _tile_map.get_cell_atlas_coords(cell) != expected_tile:
				push_error("Для %s ожидался тайл %s по направлению края, получен %s." % [
					str(cell),
					str(expected_tile),
					str(_tile_map.get_cell_atlas_coords(cell)),
				])
				_tile_map.clear()
				return
		if shape_index == 3 and _tile_map.get_cell_atlas_coords(Vector2i(1, 1)) != _base_tile:
			push_error("Внутренняя клетка не выбрала базовый тайл %s." % str(_base_tile))
			_tile_map.clear()
			return
		_tile_map.clear()
		_painted_cells.clear()
		_stroke_cells.clear()
	_painted_cells.clear()
	_stroke_cells.clear()
	var filled_cells: Array[Vector2i] = []
	for cell in test_shapes[3]:
		_paint_cell(cell)
	_finish_paint_stroke()
	var erased_cell := Vector2i(1, 1)
	_painted_cells.erase(erased_cell)
	_tile_map.erase_cell(erased_cell)
	_update_terrain_neighbors(erased_cell)
	if _tile_map.get_cell_source_id(erased_cell) != -1:
		push_error("Стирание Terrain не удалило выбранную клетку.")
		_tile_map.clear()
		_painted_cells.clear()
		return
	for cell in _painted_cells:
		if _tile_map.get_cell_source_id(cell) != _source_id:
			push_error("После стирания Terrain не обновил соседние клетки.")
			_tile_map.clear()
			_painted_cells.clear()
			return
	_tile_map.clear()
	_painted_cells.clear()
	print("Terrain smoke tests passed: fixed base, edge variants, isolated, straight, corner and erase/update.")


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.ctrl_pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and event.pressed:
			_change_zoom(1 if event.button_index == MOUSE_BUTTON_WHEEL_UP else -1, event.position)
			get_viewport().set_input_as_handled()
			return
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_painting = true
				_paint_at(event.position, false)
			else:
				_painting = false
				_finish_paint_stroke()
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			_erasing = event.pressed
			if event.pressed:
				_paint_at(event.position, true)
	elif event is InputEventMouseMotion:
		if _painting:
			_paint_at(event.position, false)
		elif _erasing:
			_paint_at(event.position, true)


func _change_zoom(direction: int, mouse_position: Vector2) -> void:
	var old_zoom := _zoom
	_zoom = clampf(_zoom * (1.15 if direction > 0 else 1.0 / 1.15), 0.5, 5.0)
	if is_equal_approx(old_zoom, _zoom):
		return
	var zoom_ratio := _zoom / old_zoom
	_tile_map.position = mouse_position + (_tile_map.position - mouse_position) * zoom_ratio
	_tile_map.scale = Vector2.ONE * _zoom


func _paint_at(screen_position: Vector2, erase: bool) -> void:
	if _tile_map == null or _tile_map.tile_set == null:
		return
	var cell := _tile_map.local_to_map(_tile_map.to_local(screen_position))
	if erase:
		_painted_cells.erase(cell)
		_tile_map.erase_cell(cell)
		_update_terrain_neighbors(cell)
		return
	_paint_cell(cell)


func _paint_cell(cell: Vector2i) -> void:
	_painted_cells[cell] = true
	_stroke_cells[cell] = true
	_tile_map.set_cell(cell, _source_id, _base_tile)


func _finish_paint_stroke() -> void:
	if _stroke_cells.is_empty() or _tile_map == null or _tile_map.tile_set == null:
		return
	var affected_cells: Dictionary = {}
	for stroke_cell in _stroke_cells:
		for y in range(-1, 2):
			for x in range(-1, 2):
				var cell: Vector2i = stroke_cell + Vector2i(x, y)
				if _painted_cells.has(cell):
					affected_cells[cell] = true
	var cells: Array[Vector2i] = []
	for cell in affected_cells:
		cells.append(cell)
	_refresh_terrain(cells)
	_stroke_cells.clear()


func _update_terrain_neighbors(cell: Vector2i) -> void:
	var cells: Array[Vector2i] = []
	for y in range(-1, 2):
		for x in range(-1, 2):
			var neighbor := cell + Vector2i(x, y)
			if _painted_cells.has(neighbor):
				cells.append(neighbor)
	_refresh_terrain(cells)


func _refresh_terrain(cells: Array[Vector2i]) -> void:
	for cell in cells:
		_tile_map.set_cell(cell, _source_id, _get_expected_tile(cell))


func _get_expected_tile(cell: Vector2i) -> Vector2i:
	var atlas_tile := _base_tile
	if not _painted_cells.has(cell + Vector2i.LEFT):
		atlas_tile.x -= 1
	elif not _painted_cells.has(cell + Vector2i.RIGHT):
		atlas_tile.x += 1
	if not _painted_cells.has(cell + Vector2i.UP):
		atlas_tile.y -= 1
	elif not _painted_cells.has(cell + Vector2i.DOWN):
		atlas_tile.y += 1
	return atlas_tile


func _clear_map() -> void:
	_painted_cells.clear()
	if _tile_map != null:
		_tile_map.clear()
