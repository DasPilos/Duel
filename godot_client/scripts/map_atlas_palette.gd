extends Control

signal tile_selected(atlas_coords: Vector2i)
signal region_selected(atlas_region: Rect2i)

const TILE_SIZE := 16
const INITIAL_ZOOM := 0.5
const MIN_ZOOM := INITIAL_ZOOM / 2.0
const MAX_ZOOM := INITIAL_ZOOM * 4.0

var atlas_texture: Texture2D
var atlas_columns := 0
var atlas_rows := 0
var tile_size := TILE_SIZE
var animations: Dictionary = {}
# Кадры анимаций (кроме первого тайла группы) скрыты в палитре: клик по кадру выбирает тайл-якорь.
var _frame_anchor: Dictionary = {}
const FRAME_HIDE_COLOR := Color(0.10, 0.11, 0.13)
var autotile_labels: Dictionary = {}
var selected_coords := Vector2i(-1, -1)
var selected_region := Rect2i()
var _zoom := INITIAL_ZOOM
var _animation_time := 0.0
var _selection_start := Vector2i(-1, -1)
var _selection_button := MOUSE_BUTTON_NONE
var _selecting := false


func set_atlas(texture: Texture2D, tile_animations: Dictionary, atlas_tile_size := TILE_SIZE) -> void:
	atlas_texture = texture
	animations = tile_animations
	_rebuild_frame_anchors()
	autotile_labels.clear()
	tile_size = maxi(1, atlas_tile_size)
	selected_coords = Vector2i(-1, -1)
	selected_region = Rect2i()
	if atlas_texture != null:
		atlas_columns = int(atlas_texture.get_size().x) / tile_size
		atlas_rows = int(atlas_texture.get_size().y) / tile_size
	_update_size()
	set_process(not animations.is_empty())
	queue_redraw()


func set_autotile_labels(labels: Dictionary) -> void:
	autotile_labels = labels.duplicate(true)
	queue_redraw()


func _process(delta: float) -> void:
	_animation_time += delta
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if atlas_texture == null:
		return
	if event is InputEventMouseButton:
		if not event.pressed and event.button_index == _selection_button and _selecting:
			_selecting = false
			_selection_button = MOUSE_BUTTON_NONE
			var end_coords := _position_to_atlas_coords(event.position)
			if _is_valid_atlas_coords(end_coords):
				var left := mini(_selection_start.x, end_coords.x)
				var top := mini(_selection_start.y, end_coords.y)
				var region := Rect2i(left, top, absi(end_coords.x - _selection_start.x) + 1, absi(end_coords.y - _selection_start.y) + 1)
				selected_region = region
				selected_coords = _selection_start
				if region.size == Vector2i.ONE:
					tile_selected.emit(selected_coords)
				else:
					region_selected.emit(region)
				queue_redraw()
				accept_event()
			return
		if not event.pressed:
			return
		if event.ctrl_pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			_zoom = minf(_zoom * 1.2, MAX_ZOOM)
			_update_size()
			accept_event()
		elif event.ctrl_pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_zoom = maxf(_zoom / 1.2, MIN_ZOOM)
			_update_size()
			accept_event()
		elif event.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT]:
			var coords := _position_to_atlas_coords(event.position)
			if _is_valid_atlas_coords(coords):
				_selection_start = coords
				_selection_button = event.button_index
				_selecting = true
				selected_coords = coords
				selected_region = Rect2i(coords, Vector2i.ONE)
				queue_redraw()
				accept_event()
	elif event is InputEventMouseMotion and _selecting:
		var selection_mask := MOUSE_BUTTON_MASK_LEFT if _selection_button == MOUSE_BUTTON_LEFT else MOUSE_BUTTON_MASK_RIGHT
		if event.button_mask & selection_mask == 0:
			return
		var coords := _position_to_atlas_coords(event.position)
		if _is_valid_atlas_coords(coords):
			var left := mini(_selection_start.x, coords.x)
			var top := mini(_selection_start.y, coords.y)
			selected_region = Rect2i(left, top, absi(coords.x - _selection_start.x) + 1, absi(coords.y - _selection_start.y) + 1)
			queue_redraw()
			accept_event()
	elif event is InputEventMouseMotion:
		var coords := _position_to_atlas_coords(event.position)
		var marker_data: Dictionary = autotile_labels.get("%d:%d" % [coords.x, coords.y], {})
		tooltip_text = "\n".join(marker_data.get("details", []))


func _position_to_atlas_coords(position: Vector2) -> Vector2i:
	var tile_pixel_size := tile_size * _zoom
	var coords := Vector2i(floori(position.x / tile_pixel_size), floori(position.y / tile_pixel_size))
	if atlas_columns > 0 and _is_valid_atlas_coords(coords):
		var tile_id := coords.y * atlas_columns + coords.x
		if _frame_anchor.has(tile_id):
			var anchor := int(_frame_anchor[tile_id])
			return Vector2i(anchor % atlas_columns, anchor / atlas_columns)
	return coords


func _rebuild_frame_anchors() -> void:
	_frame_anchor.clear()
	for tile_id_value in animations:
		var anchor := int(tile_id_value)
		for frame in animations[tile_id_value]:
			var frame_id := int(frame.get("tile_id", anchor))
			if frame_id != anchor:
				_frame_anchor[frame_id] = anchor


func _is_valid_atlas_coords(coords: Vector2i) -> bool:
	return coords.x >= 0 and coords.y >= 0 and coords.x < atlas_columns and coords.y < atlas_rows


func _draw() -> void:
	if atlas_texture == null:
		return
	var atlas_size := atlas_texture.get_size() * _zoom
	draw_texture_rect(atlas_texture, Rect2(Vector2.ZERO, atlas_size), false)
	_draw_hidden_frames()
	_draw_animated_tiles()
	var tile_pixel_size := tile_size * _zoom
	for x in range(atlas_columns + 1):
		var line_x := float(x) * tile_pixel_size
		draw_line(Vector2(line_x, 0), Vector2(line_x, atlas_size.y), Color(0.06, 0.08, 0.09, 0.34))
	for y in range(atlas_rows + 1):
		var line_y := float(y) * tile_pixel_size
		draw_line(Vector2(0, line_y), Vector2(atlas_size.x, line_y), Color(0.06, 0.08, 0.09, 0.34))
	_draw_autotile_labels(tile_pixel_size)
	if selected_coords.x >= 0:
		var selected_rect := Rect2(Vector2(selected_coords) * tile_pixel_size, Vector2.ONE * tile_pixel_size)
		draw_rect(selected_rect, Color(1.0, 0.25, 0.12), false, maxf(0.5, _zoom * 2.0 / 3.0))
	if selected_region.size != Vector2i.ZERO:
		var region_rect := Rect2(Vector2(selected_region.position) * tile_pixel_size, Vector2(selected_region.size) * tile_pixel_size)
		draw_rect(region_rect, Color(1.0, 0.78, 0.22, 0.9), false, maxf(0.75, _zoom))


func _draw_autotile_labels(tile_pixel_size: float) -> void:
	for key in autotile_labels:
		var parts := str(key).split(":")
		if parts.size() != 2:
			continue
		var coords := Vector2i(int(parts[0]), int(parts[1]))
		var marker_data: Dictionary = autotile_labels[key]
		var markers: Array = marker_data.get("markers", [])
		if markers.is_empty():
			continue
		var rect := Rect2(Vector2(coords) * tile_pixel_size, Vector2.ONE * tile_pixel_size)
		draw_rect(rect, Color(1.0, 0.76, 0.18, 0.9), false, maxf(1.0, _zoom))
		if tile_pixel_size < 14:
			continue
		var marker := str(markers[0]).substr(0, 5)
		if markers.size() > 1:
			marker += "+%d" % (markers.size() - 1)
		var badge_size := Vector2(minf(tile_pixel_size, marker.length() * 5.0 + 4.0), 9.0)
		var badge := Rect2(rect.position + Vector2(1.0, 1.0), badge_size)
		draw_rect(badge, Color(0.05, 0.08, 0.1, 0.88))
		draw_string(
			ThemeDB.fallback_font,
			badge.position + Vector2(2.0, 7.0),
			marker,
			HORIZONTAL_ALIGNMENT_LEFT,
			badge.size.x - 2.0,
			7,
			Color(1.0, 0.9, 0.56),
		)


func _draw_hidden_frames() -> void:
	if atlas_columns <= 0:
		return
	var tile_pixel_size := tile_size * _zoom
	for frame_id in _frame_anchor:
		var coords := Vector2i(int(frame_id) % atlas_columns, int(frame_id) / atlas_columns)
		draw_rect(Rect2(Vector2(coords) * tile_pixel_size, Vector2.ONE * tile_pixel_size), FRAME_HIDE_COLOR)


func _draw_animated_tiles() -> void:
	var tile_pixel_size := tile_size * _zoom
	var columns := atlas_columns
	for tile_id_value in animations:
		var tile_id := int(tile_id_value)
		var frames: Array = animations[tile_id_value]
		if frames.is_empty():
			continue
		var current_frame: Dictionary = _current_frame(frames)
		var coords := Vector2i(tile_id % columns, tile_id / columns)
		var destination := Rect2(Vector2(coords) * tile_pixel_size, Vector2.ONE * tile_pixel_size)
		var source := Rect2(
			Vector2(int(current_frame.get("tile_id", tile_id)) % columns, int(current_frame.get("tile_id", tile_id)) / columns) * tile_size,
			Vector2.ONE * tile_size
		)
		draw_texture_rect_region(atlas_texture, destination, source)


func _current_frame(frames: Array) -> Dictionary:
	var cycle_duration := 0.0
	for frame in frames:
		cycle_duration += maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
	if cycle_duration <= 0.0:
		return frames[0]
	var frame_time := fmod(_animation_time, cycle_duration)
	for frame in frames:
		frame_time -= maxf(float(frame.get("duration", 100)), 1.0) / 1000.0
		if frame_time < 0.0:
			return frame
	return frames[0]


func _update_size() -> void:
	if atlas_texture == null:
		custom_minimum_size = Vector2.ZERO
		return
	custom_minimum_size = atlas_texture.get_size() * _zoom
	size = custom_minimum_size
