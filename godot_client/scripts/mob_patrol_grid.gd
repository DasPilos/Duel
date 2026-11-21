extends Control

signal changed

const GRID_SIZE := 18
const ANCHOR := 9
const BACKGROUND_COLOR := Color8(16, 18, 22)
const LINE_COLOR := Color8(44, 48, 56)
const FILL_COLOR := Color8(86, 160, 220)
const ANCHOR_COLOR := Color8(255, 220, 90)

var cell_size := 24
var cells: Dictionary = {}
var _paint_button := MOUSE_BUTTON_NONE
var _last_cell := Vector2i(-1, -1)


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_cell_size(cell_size)


func set_cell_size(value: int) -> void:
	cell_size = maxi(4, value)
	custom_minimum_size = Vector2(GRID_SIZE, GRID_SIZE) * cell_size
	queue_redraw()


func cell_count() -> int:
	return cells.size()


func set_offsets(offsets: Array) -> void:
	cells.clear()
	for offset in offsets:
		if offset is Array and offset.size() >= 2:
			var cell := Vector2i(int(offset[0]) + ANCHOR, int(offset[1]) + ANCHOR)
			if _inside(cell):
				cells[cell] = true
	queue_redraw()
	changed.emit()


func offsets() -> Array:
	var sorted_cells: Array = cells.keys()
	sorted_cells.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return a.y < b.y or (a.y == b.y and a.x < b.x)
	)
	var result: Array = []
	for cell: Vector2i in sorted_cells:
		result.append([cell.x - ANCHOR, cell.y - ANCHOR])
	return result


func apply_preset(preset: String) -> void:
	cells.clear()
	if preset != "clear":
		var radius := 3 if preset == "circle3" else 6
		for y in range(GRID_SIZE):
			for x in range(GRID_SIZE):
				var dx := x - ANCHOR
				var dy := y - ANCHOR
				if dx * dx + dy * dy <= radius * radius:
					cells[Vector2i(x, y)] = true
	queue_redraw()
	changed.emit()


func cell_at(position: Vector2) -> Vector2i:
	var cell := Vector2i(floori(position.x / cell_size), floori(position.y / cell_size))
	return cell if _inside(cell) else Vector2i(-1, -1)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button_event: InputEventMouseButton = event
		if button_event.button_index != MOUSE_BUTTON_LEFT \
			and button_event.button_index != MOUSE_BUTTON_RIGHT:
			return
		if button_event.pressed:
			_paint_button = button_event.button_index
			_last_cell = Vector2i(-1, -1)
			_paint_at(button_event.position)
		elif button_event.button_index == _paint_button:
			_paint_button = MOUSE_BUTTON_NONE
			_last_cell = Vector2i(-1, -1)
		accept_event()
	elif event is InputEventMouseMotion and _paint_button != MOUSE_BUTTON_NONE:
		var motion_event: InputEventMouseMotion = event
		_paint_at(motion_event.position)
		accept_event()


func _paint_at(position: Vector2) -> void:
	var cell := cell_at(position)
	if not _inside(cell):
		return
	var from_cell := _last_cell if _inside(_last_cell) else cell
	_last_cell = cell
	var painted := _paint_button == MOUSE_BUTTON_LEFT
	var modified := false
	for step_cell in _line_cells(from_cell, cell):
		if painted and not cells.has(step_cell):
			cells[step_cell] = true
			modified = true
		elif not painted and cells.has(step_cell):
			cells.erase(step_cell)
			modified = true
	if modified:
		queue_redraw()
		changed.emit()


func _line_cells(from_cell: Vector2i, to_cell: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var delta := to_cell - from_cell
	var steps := maxi(absi(delta.x), absi(delta.y))
	if steps == 0:
		result.append(to_cell)
		return result
	for index in range(steps + 1):
		var point := Vector2(from_cell) + Vector2(delta) * (float(index) / float(steps))
		result.append(Vector2i(roundi(point.x), roundi(point.y)))
	return result


func _inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < GRID_SIZE and cell.y < GRID_SIZE


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, Vector2(GRID_SIZE, GRID_SIZE) * cell_size), BACKGROUND_COLOR)
	for y in range(GRID_SIZE):
		for x in range(GRID_SIZE):
			var rect := Rect2(Vector2(x, y) * cell_size, Vector2.ONE * cell_size)
			if cells.has(Vector2i(x, y)):
				draw_rect(rect.grow(-1.0), FILL_COLOR)
			draw_rect(rect, LINE_COLOR, false, 1.0)
	var mark := Rect2(Vector2(ANCHOR, ANCHOR) * cell_size, Vector2.ONE * cell_size)
	draw_rect(mark, ANCHOR_COLOR, false, 2.0)
	draw_line(mark.position, mark.end, ANCHOR_COLOR, 1.0)
	draw_line(
		Vector2(mark.end.x, mark.position.y),
		Vector2(mark.position.x, mark.end.y),
		ANCHOR_COLOR,
		1.0,
	)
