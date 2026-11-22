extends Control
# Общий холст карты Экономики: фон из тайлов, камера (масштаб колесом, перетаскивание, клик по миру)
# и нарезка атласа как в map_atlas_palette.gd (set_atlas). Наследник задаёт цвет тайла в _tile_color()
# и рисует объекты в _draw_content(); координаты мира — пиксели, тайл = tile_px.

signal world_clicked(world_position: Vector2)

const MIN_ZOOM := 0.05
const MAX_ZOOM := 1.5
const ZOOM_FACTOR := 1.15
const DRAG_THRESHOLD := 4.0
const BACKGROUND_COLOR := Color(16.0 / 255.0, 20.0 / 255.0, 26.0 / 255.0)
const GRID_COLOR := Color(58.0 / 255.0, 66.0 / 255.0, 76.0 / 255.0)

var map_tiles := Vector2i(100, 100)
var tile_px := 16
var camera_center := Vector2.ZERO
var zoom := 1.0
var show_grid := false
var background_color := BACKGROUND_COLOR
var draw_tiles := true
var atlas_texture: Texture2D
var atlas_tile_px := 16
var atlas_columns := 0
var atlas_rows := 0
var _pressed := false
var _dragged := false
var _press_position := Vector2.ZERO
var _camera_touched := false


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	resized.connect(_on_resized)


func set_map(tiles: Vector2i, tile_size: int) -> void:
	map_tiles = tiles
	tile_px = maxi(1, tile_size)
	_clamp_camera()
	queue_redraw()


func set_atlas(texture: Texture2D, atlas_tile_size := 16) -> void:
	atlas_texture = texture
	atlas_tile_px = maxi(1, atlas_tile_size)
	atlas_columns = 0
	atlas_rows = 0
	if atlas_texture != null:
		atlas_columns = int(atlas_texture.get_size().x) / atlas_tile_px
		atlas_rows = int(atlas_texture.get_size().y) / atlas_tile_px
	queue_redraw()


# Область текстуры для клетки атласа; за пределами сетки — пустой Rect2.
func atlas_region(coords: Vector2i) -> Rect2:
	if coords.x < 0 or coords.y < 0 or coords.x >= atlas_columns or coords.y >= atlas_rows:
		return Rect2()
	return Rect2(Vector2(coords * atlas_tile_px), Vector2.ONE * atlas_tile_px)


func map_size_px() -> Vector2:
	return Vector2(map_tiles * tile_px)


# Масштаб, при котором вся карта помещается в холст; камера встаёт в центр карты.
func fit_map() -> void:
	fit_world_rect(Rect2(Vector2.ZERO, map_size_px()))


# Масштаб, при котором прямоугольник мира (в пикселях) помещается в холст целиком.
func fit_world_rect(world_rect: Rect2) -> void:
	if size.x <= 0.0 or size.y <= 0.0 or world_rect.size.x <= 0.0 or world_rect.size.y <= 0.0:
		return
	zoom = clampf(minf(size.x / world_rect.size.x, size.y / world_rect.size.y), MIN_ZOOM, MAX_ZOOM)
	camera_center = world_rect.get_center()
	_camera_touched = false
	_clamp_camera()
	queue_redraw()


# Меняет масштаб так, чтобы точка под курсором осталась на месте.
func set_zoom_at(factor: float, screen_anchor: Vector2) -> void:
	var anchor_world := screen_to_world(screen_anchor)
	zoom = clampf(zoom * factor, MIN_ZOOM, MAX_ZOOM)
	camera_center = anchor_world - (screen_anchor - size * 0.5) / zoom
	_camera_touched = true
	_clamp_camera()
	queue_redraw()


func world_to_screen(world: Vector2) -> Vector2:
	return size * 0.5 + (world - camera_center) * zoom


func screen_to_world(screen: Vector2) -> Vector2:
	return camera_center + (screen - size * 0.5) / zoom


# Диапазон тайлов, попадающих в холст (с границами карты).
func visible_tile_rect() -> Rect2i:
	var top_left := screen_to_world(Vector2.ZERO) / float(tile_px)
	var bottom_right := screen_to_world(size) / float(tile_px)
	var left := clampi(floori(top_left.x), 0, map_tiles.x)
	var top := clampi(floori(top_left.y), 0, map_tiles.y)
	var right := clampi(ceili(bottom_right.x), 0, map_tiles.x)
	var bottom := clampi(ceili(bottom_right.y), 0, map_tiles.y)
	return Rect2i(left, top, maxi(0, right - left), maxi(0, bottom - top))


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), background_color)
	if draw_tiles and map_tiles.x > 0 and map_tiles.y > 0:
		_draw_tiles()
	_draw_content()


func _draw_tiles() -> void:
	var area := visible_tile_rect()
	var tile_screen := tile_px * zoom
	for gy in range(area.position.y, area.end.y):
		for gx in range(area.position.x, area.end.x):
			var tile := Vector2i(gx, gy)
			var rect := Rect2(world_to_screen(Vector2(tile * tile_px)), Vector2.ONE * tile_screen)
			var atlas_coords := _tile_atlas_coords(tile)
			if atlas_texture != null and atlas_coords.x >= 0 and atlas_region(atlas_coords).has_area():
				draw_texture_rect_region(atlas_texture, rect, atlas_region(atlas_coords))
			else:
				draw_rect(rect, _tile_color(tile))
			if show_grid:
				draw_rect(rect, GRID_COLOR, false, 1.0)



func _draw_content() -> void:
	pass


func _tile_color(_tile: Vector2i) -> Color:
	return Color(0.12, 0.14, 0.17)


# Клетка атласа для тайла или Vector2i(-1, -1), если тайл рисуется цветом.
func _tile_atlas_coords(_tile: Vector2i) -> Vector2i:
	return Vector2i(-1, -1)


func _gui_input(event: InputEvent) -> void:
	var button := event as InputEventMouseButton
	if button != null:
		_handle_button(button)
		return
	var motion := event as InputEventMouseMotion
	if motion != null and _pressed:
		if not _dragged and motion.position.distance_to(_press_position) > DRAG_THRESHOLD:
			_dragged = true
		if _dragged:
			camera_center -= motion.relative / zoom
			_camera_touched = true
			_clamp_camera()
			queue_redraw()
			accept_event()


func _handle_button(button: InputEventMouseButton) -> void:
	if button.pressed and button.button_index == MOUSE_BUTTON_WHEEL_UP:
		set_zoom_at(ZOOM_FACTOR, button.position)
		accept_event()
	elif button.pressed and button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		set_zoom_at(1.0 / ZOOM_FACTOR, button.position)
		accept_event()
	elif button.button_index == MOUSE_BUTTON_LEFT:
		if button.pressed:
			_pressed = true
			_dragged = false
			_press_position = button.position
		elif _pressed:
			_pressed = false
			if not _dragged:
				world_clicked.emit(screen_to_world(button.position))
		accept_event()


func _clamp_camera() -> void:
	camera_center = camera_center.clamp(Vector2.ZERO, map_size_px())


func _on_resized() -> void:
	if not _camera_touched:
		fit_map()
	else:
		_clamp_camera()
		queue_redraw()
