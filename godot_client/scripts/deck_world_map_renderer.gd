extends Control

# Карта мира Deck: плитки и объекты рисуются здесь, маркеры — кнопками поверх плиток.
# Фигурки игрока и лесника — дочерний слой deck_world_sprites.gd поверх маркеров.
# Клик и наведение только сообщают координату тайла, перетаскивание — сдвиг в тайлах; ходьбу и камеру решает deck_world.gd.

signal tile_clicked(tile: Vector2i)
signal tile_hovered(tile: Vector2i)
signal view_drag_started()
signal view_dragged(offset: Vector2)

const RULES := preload("res://scripts/deck_world_map_rules.gd")
const SPRITES_SCRIPT := preload("res://scripts/deck_world_sprites.gd")
const INSET := 3.0
const ELLIPSE_SEGMENTS := 24
const HIGHLIGHT := Color(1.0, 0.843, 0.235)
const WAVE_COLOR := Color(110 / 255.0, 160 / 255.0, 220 / 255.0)
const PLANK_COLOR := Color(100 / 255.0, 70 / 255.0, 40 / 255.0)
const BERRY_COLOR := Color(196 / 255.0, 52 / 255.0, 72 / 255.0)
const ROCK_EDGE_COLOR := Color(60 / 255.0, 60 / 255.0, 66 / 255.0)
const BLOCK_COLOR := Color(60 / 255.0, 60 / 255.0, 66 / 255.0)

var _origin := Vector2i.ZERO
var _view_shift := Vector2.ZERO
var _data_window := Rect2i()
var _marker_buttons: Dictionary = {}
var _view_size := 11
var _map_size := Vector2i(128, 256)
var _cell := 48.0
var _published := false
var _kinds: Dictionary = {}
var _walls: Dictionary = {}
var _city := Rect2i()
var _objects: Array = []
var _solid: Dictionary = {}
var _steppable: Dictionary = {}
var _markers: Dictionary = {}
var _hover_tile := RULES.NO_TILE
var _sprites = null
var _pressing := false
var _dragging := false
var _press_point := Vector2.ZERO


func _init() -> void:
	mouse_exited.connect(_on_mouse_exited)


# state: terrain, center, view_size, map_size, tile_px, markers (тайл → маркер), solid и steppable (списки тайлов).
func configure(state: Dictionary) -> void:
	_clear_markers()
	var terrain: Variant = state.get("terrain", {})
	terrain = terrain if terrain is Dictionary else {}
	_view_size = maxi(1, int(state.get("view_size", 11)))
	_map_size = state.get("map_size", Vector2i(128, 256))
	_cell = maxf(1.0, float(state.get("tile_px", 48.0)))
	_set_view(_state_view_center(state))
	_published = RULES.is_published(terrain)
	var data: Variant = state.get("data_window", null)
	_data_window = data if data is Rect2i else Rect2i(_origin, Vector2i.ONE * _view_size)
	_kinds = RULES.tile_kinds(terrain, _data_window)
	_walls = RULES.wall_tiles(terrain)
	_city = RULES.city_bounds(terrain)
	_objects = RULES.objects_for(terrain)
	_solid = _set_of(state.get("solid", []))
	_steppable = _set_of(state.get("steppable", []))
	_markers = state.get("markers", {})
	_hover_tile = RULES.NO_TILE
	custom_minimum_size = Vector2.ONE * _cell * float(_view_size)
	size = custom_minimum_size
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_PASS
	for tile in _markers:
		_add_marker(tile, _markers[tile])
	if state.has("center"):
		_add_sprites(state)
	queue_redraw()


func tile_at(point: Vector2) -> Vector2i:
	if point.x < 0.0 or point.y < 0.0 or point.x >= _view_size * _cell or point.y >= _view_size * _cell:
		return RULES.NO_TILE
	var shifted := (point + _view_shift * _cell) / _cell
	var tile := _origin + Vector2i(floori(shifted.x), floori(shifted.y))
	return tile if RULES.in_map(tile, _map_size) else RULES.NO_TILE


func marker_at(tile: Vector2i) -> Dictionary:
	return _markers.get(tile, {})


func is_steppable(tile: Vector2i) -> bool:
	return _steppable.has(tile)


# Время и ходьба приходят из deck_world.gd каждый кадр; перерисовывается только слой фигурок.
func set_animation(anim_time: float, walking: bool) -> void:
	if is_instance_valid(_sprites):
		_sprites.set_animation(anim_time, walking)


# Окно карты в дробных тайлах: center — центр окна в координатах тайлов (tile_center(tile) для целой плитки).
# Плитки, маркеры и лагерь лесника сдвигаются плавно; на каждом изменении сдвига пересчитываются только они.
func set_view_center(center: Vector2) -> void:
	var previous_origin := _origin
	var previous_shift := _view_shift
	_set_view(center)
	if _origin == previous_origin and _view_shift.is_equal_approx(previous_shift):
		return
	for tile in _marker_buttons:
		_place_marker(tile)
	_refresh_forester()
	queue_redraw()


func _set_view(center: Vector2) -> void:
	var origin := RULES.view_origin(center, _view_size)
	_origin = Vector2i(int(floor(origin.x)), int(floor(origin.y)))
	_view_shift = origin - Vector2(_origin)


func _state_view_center(state: Dictionary) -> Vector2:
	if state.has("view_center"):
		return state["view_center"]
	return RULES.tile_center(state.get("center", Vector2i.ZERO))


func _state_figure(state: Dictionary) -> Vector2:
	if state.has("figure"):
		return state["figure"]
	return RULES.tile_center(state.get("center", Vector2i.ZERO))


# Ноги фигурки в координатах окна: окно и фигурка сдвигаются по дробным тайлам, как плитки.
func _figure_feet(figure: Vector2) -> Vector2:
	return (figure - Vector2(_origin) - _view_shift) * _cell


# Фигурка может стоять не в центре окна (камера зажата краем карты), поэтому ноги пересчитываются каждый кадр.
func set_figure(figure: Vector2) -> void:
	if is_instance_valid(_sprites):
		_sprites.set_feet(_figure_feet(figure))


func _place_marker(tile: Vector2i) -> void:
	var button: Button = _marker_buttons[tile]
	var frame := RULES.tile_rect(tile, _origin, _cell).grow(-INSET)
	button.position = frame.position - _view_shift * _cell
	button.size = frame.size
	button.visible = Rect2(Vector2.ZERO, size).intersects(Rect2(button.position, button.size))


# Наведение на лагерь лесника, как hovered_entity в Python: окна, закрывающие карту, его отключают.
func update_pointer(point: Vector2, blocked: bool) -> void:
	var forester := _forester_view()
	var hovered := false
	if not blocked and not forester.is_empty():
		var rect: Rect2 = forester["rect"]
		hovered = rect.has_point(point)
	if is_instance_valid(_sprites):
		_sprites.set_forester_hovered(hovered)


func _refresh_forester() -> void:
	if is_instance_valid(_sprites):
		_sprites.set_forester(_forester_view())


func _set_of(tiles: Variant) -> Dictionary:
	var result := {}
	if tiles is Array:
		for tile in tiles:
			if tile is Vector2i:
				result[tile] = true
	return result


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), RULES.VOID_COLOR)
	draw_set_transform(-_view_shift * _cell)
	for y in range(_view_size + 1):
		for x in range(_view_size + 1):
			var tile := _origin + Vector2i(x, y)
			if RULES.in_map(tile, _map_size):
				_draw_tile(tile)
	for map_object in _objects:
		_draw_object(map_object)
	for tile in _solid:
		_draw_solid(tile)
	for tile in _steppable:
		_draw_highlight(tile)
	draw_set_transform(Vector2.ZERO)


func _draw_tile(tile: Vector2i) -> void:
	var rect := RULES.tile_rect(tile, _origin, _cell)
	draw_rect(rect, RULES.ground_color(_published, tile, _map_size))
	if not _published and _city.has_point(tile):
		draw_rect(rect, RULES.checker(RULES.PAVING_COLORS, tile))
	elif _kinds.has(tile):
		_draw_kind(str(_kinds[tile]), tile, rect)
	if _walls.has(tile):
		var inner := rect.grow(-INSET)
		draw_rect(inner, RULES.WALL_COLOR)
		draw_rect(inner, RULES.WALL_EDGE_COLOR, false, 2.0)


func _draw_kind(kind: String, tile: Vector2i, rect: Rect2) -> void:
	match kind:
		"road":
			draw_rect(rect, RULES.checker(RULES.ROAD_COLORS, tile))
			draw_line(rect.position, Vector2(rect.end.x, rect.position.y), RULES.ROAD_EDGE_COLOR)
			draw_line(Vector2(rect.position.x, rect.end.y), rect.end, RULES.ROAD_EDGE_COLOR)
		"water":
			draw_rect(rect, RULES.tile_color("water"))
			for fraction in [0.36, 0.7]:
				var wave_y: float = rect.position.y + _cell * fraction
				draw_line(Vector2(rect.position.x + _cell * 0.2, wave_y), Vector2(rect.position.x + _cell * 0.8, wave_y), WAVE_COLOR, 2.0)
		"bridge":
			draw_rect(rect, RULES.tile_color("bridge"))
			for fraction in [0.25, 0.5, 0.75]:
				var plank_y: float = rect.position.y + _cell * fraction
				draw_line(Vector2(rect.position.x, plank_y), Vector2(rect.end.x, plank_y), PLANK_COLOR, 1.5)
		"mountain":
			_draw_mountain(rect)
		"forest", "dry":
			_draw_crown(rect, RULES.tile_color(kind))
		"berry":
			draw_rect(rect, RULES.tile_color("berry"))
			for offset in [Vector2(0.3, 0.4), Vector2(0.62, 0.55), Vector2(0.42, 0.74)]:
				draw_circle(rect.position + offset * _cell, _cell * 0.07, BERRY_COLOR)
		"floor":
			draw_rect(rect, RULES.tile_color("floor"))
		"impassable":
			draw_rect(rect, RULES.tile_color("impassable"))
			draw_rect(rect.grow(-4.0), ROCK_EDGE_COLOR, false, 2.0)
		"stump":
			_draw_stump(rect)
		"log":
			_draw_log(rect)


func _draw_mountain(rect: Rect2) -> void:
	draw_rect(rect, RULES.tile_color("mountain"))
	var left := rect.position + Vector2(0.12, 0.9) * _cell
	var apex := rect.position + Vector2(0.5, 0.18) * _cell
	var ridge := rect.position + Vector2(0.56, 0.9) * _cell
	var right := rect.position + Vector2(0.88, 0.9) * _cell
	draw_colored_polygon(PackedVector2Array([left, apex, ridge]), Color(118 / 255.0, 110 / 255.0, 100 / 255.0))
	draw_colored_polygon(PackedVector2Array([ridge, apex, right]), Color(72 / 255.0, 66 / 255.0, 62 / 255.0))


func _draw_crown(rect: Rect2, color: Color) -> void:
	var center := rect.get_center()
	var radius := _cell * 0.42
	draw_circle(center + Vector2(2, 3) * (_cell / 48.0), radius, Color(0, 0, 0, 0.35))
	draw_circle(center, radius, color)
	draw_circle(center - Vector2.ONE * radius * 0.3, radius * 0.45, color.lightened(0.25))
	draw_arc(center, radius, 0.0, TAU, ELLIPSE_SEGMENTS, color.darkened(0.45), 1.5)


func _draw_stump(rect: Rect2) -> void:
	var center := rect.get_center() + Vector2(0, _cell * 0.08)
	var color := RULES.tile_color("stump")
	draw_circle(center, _cell * 0.22, color)
	draw_arc(center, _cell * 0.16, 0.0, TAU, 16, color.lightened(0.3), 2.0)


func _draw_log(rect: Rect2) -> void:
	var log_rect := Rect2(rect.position + Vector2(0.14, 0.42) * _cell, Vector2(0.72, 0.2) * _cell)
	draw_rect(log_rect, RULES.tile_color("log"))
	draw_rect(log_rect, RULES.tile_color("log").darkened(0.4), false, 1.5)


# Твёрдый тайл без вида плитки, стены и объекта — обломок скалы. Остальные твёрдые клетки уже нарисованы выше.
func _draw_solid(tile: Vector2i) -> void:
	if _kinds.has(tile) or _walls.has(tile) or _object_covers(tile):
		return
	var rect := RULES.tile_rect(tile, _origin, _cell)
	draw_rect(rect, RULES.tile_color("obstacle"))
	draw_rect(rect.grow(-4.0), ROCK_EDGE_COLOR, false, 2.0)


func _object_covers(tile: Vector2i) -> bool:
	for map_object in _objects:
		if map_object["rect"].has_point(tile):
			return true
	return false


func _draw_object(map_object: Dictionary) -> void:
	var tiles: Rect2i = map_object["rect"]
	var rect := _view_rect(tiles)
	match str(map_object["kind"]):
		"crystal":
			_draw_crystal(rect)
		"library":
			_draw_library(rect)
		"talent":
			_draw_talent(rect)
		"forester":
			pass  # лагерь лесника рисует слой фигурок поверх маркеров
		_:
			draw_rect(rect, BLOCK_COLOR)


func _view_rect(tiles: Rect2i) -> Rect2:
	return Rect2(Vector2(tiles.position - _origin) * _cell, Vector2(tiles.size) * _cell)


# Кристалл возрождения: порт _draw_respawn_crystal из world_map_scene.py (k = tile_size / 32, pulse = 1).
func _draw_crystal(rect: Rect2) -> void:
	var k := _cell / 32.0
	var center := rect.get_center()
	draw_circle(center, 34.0 * k, Color(65 / 255.0, 205 / 255.0, 255 / 255.0, 36 / 255.0))
	draw_circle(center, 17.0 * k, Color(105 / 255.0, 230 / 255.0, 255 / 255.0, 24 / 255.0))
	var pedestal := Rect2(rect.position + Vector2(12, rect.size.y - 28) * k, Vector2(rect.size.x - 24, 20) * k)
	var pedestal_center := pedestal.get_center()
	var pedestal_radius := pedestal.size / 2.0
	draw_colored_polygon(_ellipse(pedestal_center + Vector2(0, 5), pedestal_radius), Color(14 / 255.0, 29 / 255.0, 38 / 255.0))
	draw_colored_polygon(_ellipse(pedestal_center, pedestal_radius), Color(35 / 255.0, 92 / 255.0, 112 / 255.0))
	draw_polyline(_closed(_ellipse(pedestal_center, pedestal_radius)), Color(105 / 255.0, 218 / 255.0, 238 / 255.0), 2.0)
	draw_line(
		Vector2(pedestal.position.x + 8, center.y + 16 * k),
		Vector2(pedestal.end.x - 8, center.y + 16 * k),
		Color(116 / 255.0, 225 / 255.0, 255 / 255.0),
		2.0
	)
	var top := Vector2(center.x, rect.position.y + 8 * k)
	var upper_right := Vector2(center.x + 18 * k, center.y - 8 * k)
	var lower_right := Vector2(center.x + 12 * k, center.y + 18 * k)
	var bottom := Vector2(center.x, rect.end.y - 28 * k)
	var lower_left := Vector2(center.x - 12 * k, center.y + 18 * k)
	var upper_left := Vector2(center.x - 18 * k, center.y - 8 * k)
	var mid := Vector2(center.x, center.y + 10 * k)
	var crystal := PackedVector2Array([top, upper_right, lower_right, bottom, lower_left, upper_left])
	draw_colored_polygon(crystal, Color(35 / 255.0, 152 / 255.0, 205 / 255.0))
	draw_colored_polygon(PackedVector2Array([top, upper_right, mid]), Color(151 / 255.0, 240 / 255.0, 255 / 255.0))
	draw_colored_polygon(PackedVector2Array([top, mid, upper_left]), Color(68 / 255.0, 197 / 255.0, 232 / 255.0))
	draw_colored_polygon(PackedVector2Array([upper_right, lower_right, mid]), Color(33 / 255.0, 122 / 255.0, 181 / 255.0))
	draw_colored_polygon(PackedVector2Array([lower_right, bottom, mid]), Color(23 / 255.0, 93 / 255.0, 150 / 255.0))
	draw_colored_polygon(PackedVector2Array([bottom, lower_left, mid]), Color(46 / 255.0, 166 / 255.0, 211 / 255.0))
	draw_colored_polygon(PackedVector2Array([lower_left, upper_left, mid]), Color(94 / 255.0, 220 / 255.0, 245 / 255.0))
	draw_polyline(_closed(crystal), Color(205 / 255.0, 252 / 255.0, 255 / 255.0), 2.0)


# Библиотека: порт блока из world_map_scene.py (_draw_objects, id library).
func _draw_library(rect: Rect2) -> void:
	var columns := int(round(rect.size.x / _cell))
	var rows := int(round(rect.size.y / _cell))
	var grid_color := Color(72 / 255.0, 72 / 255.0, 88 / 255.0)
	draw_rect(rect, Color(48 / 255.0, 48 / 255.0, 60 / 255.0))
	draw_rect(rect, Color(112 / 255.0, 112 / 255.0, 135 / 255.0), false, 3.0)
	for index in range(1, columns):
		var x := rect.position.x + index * _cell
		draw_line(Vector2(x, rect.position.y + 8), Vector2(x, rect.end.y - 8), grid_color, 2.0)
	for index in range(1, rows):
		var y := rect.position.y + index * _cell
		draw_line(Vector2(rect.position.x + 8, y), Vector2(rect.end.x - 8, y), grid_color, 2.0)
	var door := Rect2(rect.get_center().x - _cell / 4.0, rect.end.y - _cell, _cell / 2.0, _cell)
	draw_rect(door, Color(112 / 255.0, 82 / 255.0, 54 / 255.0))


# Древо талантов: порт из world_map_scene.py (k = tile_size / 48). Центр — угол блока 2x2, как obj["x"], obj["y"].
func _draw_talent(rect: Rect2) -> void:
	var k := _cell / 48.0
	var base := rect.get_center()
	draw_colored_polygon(_ellipse(base + Vector2(0, 21 * k), Vector2(34 * k, 8 * k)), Color(12 / 255.0, 19 / 255.0, 13 / 255.0))
	draw_rect(Rect2(base + Vector2(-9 * k, -5 * k), Vector2(18 * k, 46 * k)), Color(105 / 255.0, 75 / 255.0, 43 / 255.0))
	for crown in [Vector3(-17, -18, 19), Vector3(0, -31, 23), Vector3(17, -18, 19)]:
		var center: Vector2 = base + Vector2(crown.x, crown.y) * k
		draw_circle(center, crown.z * k, Color(78 / 255.0, 145 / 255.0, 66 / 255.0))
		draw_arc(center, crown.z * k, 0.0, TAU, ELLIPSE_SEGMENTS, Color(48 / 255.0, 105 / 255.0, 48 / 255.0), 2.0 * k)


func _draw_highlight(tile: Vector2i) -> void:
	var rect := RULES.tile_rect(tile, _origin, _cell).grow(-2.0)
	draw_rect(rect, Color(HIGHLIGHT.r, HIGHLIGHT.g, HIGHLIGHT.b, 0.12))
	draw_rect(rect, HIGHLIGHT, false, 2.0)


func _ellipse(center: Vector2, radius: Vector2) -> PackedVector2Array:
	var points := PackedVector2Array()
	for index in range(ELLIPSE_SEGMENTS):
		var angle := TAU * index / ELLIPSE_SEGMENTS
		points.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y))
	return points


func _closed(points: PackedVector2Array) -> PackedVector2Array:
	var closed := points.duplicate()
	closed.append(points[0])
	return closed


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			_pressing = true
			_dragging = false
			_press_point = event.position
			view_drag_started.emit()
		elif event.button_index == MOUSE_BUTTON_LEFT:
			var clicked := not _dragging
			_pressing = false
			_dragging = false
			var tile := tile_at(event.position)
			if clicked and tile != RULES.NO_TILE:
				accept_event()
				tile_clicked.emit(tile)
	elif event is InputEventMouseMotion:
		if _pressing and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) == 0:
			_pressing = false
			_dragging = false
		elif _pressing:
			var offset: Vector2 = event.position - _press_point
			if _dragging or RULES.drag_passed(offset):
				_dragging = true
				view_dragged.emit(offset / _cell)
		_update_hover(tile_at(event.position))


func _update_hover(tile: Vector2i) -> void:
	if tile == _hover_tile:
		return
	_hover_tile = tile
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if _steppable.has(tile) else Control.CURSOR_ARROW
	if tile != RULES.NO_TILE:
		tile_hovered.emit(tile)


func _on_mouse_exited() -> void:
	_hover_tile = RULES.NO_TILE
	mouse_default_cursor_shape = Control.CURSOR_ARROW


func _add_marker(tile: Vector2i, marker: Dictionary) -> void:
	var fill: Color = marker.get("color", Color.WHITE)
	fill.a = float(marker.get("alpha", 1.0))
	var border: Color = marker.get("border", fill.darkened(0.45))
	border.a = 1.0
	var text_color := RULES.text_color_for(fill)
	var button := Button.new()
	button.text = str(marker.get("symbol", ""))
	button.tooltip_text = str(marker.get("tooltip", ""))
	button.focus_mode = Control.FOCUS_NONE
	button.clip_text = true
	button.disabled = bool(marker.get("disabled", false))
	button.add_theme_stylebox_override("normal", _marker_style(fill, border))
	button.add_theme_stylebox_override("disabled", _marker_style(fill, border))
	button.add_theme_stylebox_override("focus", _marker_style(fill, border))
	button.add_theme_stylebox_override("hover", _marker_style(fill.lightened(0.15), border))
	button.add_theme_stylebox_override("pressed", _marker_style(fill.darkened(0.12), border))
	for key in ["font_color", "font_hover_color", "font_pressed_color", "font_disabled_color", "font_focus_color"]:
		button.add_theme_color_override(key, text_color)
	button.pressed.connect(_on_marker_pressed.bind(tile))
	button.mouse_entered.connect(_on_marker_entered.bind(tile))
	_marker_buttons[tile] = button
	_place_marker(tile)
	add_child(button)


func _marker_style(fill: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	return style


func _on_marker_pressed(tile: Vector2i) -> void:
	tile_clicked.emit(tile)


func _on_marker_entered(tile: Vector2i) -> void:
	tile_hovered.emit(tile)


func _add_sprites(state: Dictionary) -> void:
	_sprites = SPRITES_SCRIPT.new()
	_sprites.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_sprites.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_sprites)
	_sprites.configure({
		"feet": _figure_feet(_state_figure(state)),
		"tile_px": int(_cell),
		"direction": str(state.get("direction", "s")),
		"player_name": str(state.get("player_name", "Герой")),
		"forester": _forester_view(),
		"anim_time": float(state.get("anim_time", 0.0)),
		"walking": bool(state.get("walking", false)),
	})


func _forester_view() -> Dictionary:
	for map_object in _objects:
		if str(map_object["kind"]) == "forester":
			return {"rect": _forester_rect(map_object), "rotation": int(map_object.get("rotation", 0)), "name": str(map_object.get("name", ""))}
	return {}


# Лагерь лесника рисует слой фигурок, поэтому его прямоугольник учитывает дробный сдвиг окна (в отличие от плиток).
func _forester_rect(map_object: Dictionary) -> Rect2:
	var tiles: Rect2i = map_object["rect"]
	return Rect2((Vector2(tiles.position - _origin) - _view_shift) * _cell, Vector2(tiles.size) * _cell)


func _clear_markers() -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()
	_marker_buttons.clear()
	_sprites = null
