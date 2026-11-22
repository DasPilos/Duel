extends Control

# Плавающий блок редактора карты: перетаскивается за заголовок, меняет размер за правый нижний угол.
# «Закрепить» запрещает двигать и менять размер; «Свернуть» оставляет только заголовок, «Развернуть» возвращает блок.

const TITLE_HEIGHT := 26.0
const GRIP_SIZE := 14.0
const MIN_SIZE := Vector2(140.0, 60.0)
const KEEP_VISIBLE := 60.0
const BODY_COLOR := Color(0.09, 0.11, 0.13)
const HEADER_COLOR := Color(0.16, 0.19, 0.23)
const BORDER_COLOR := Color(0.32, 0.37, 0.43)
const GRIP_COLOR := Color(0.55, 0.6, 0.66)

signal layout_changed

var pinned := false
var collapsed := false
var panel_key := ""

var _title_label: Label
var _pin_button: Button
var _collapse_button: Button
var _header: HBoxContainer
var _body: Control
var _grip: Control
var _expanded_height := 300.0
var _dragging := false
var _resizing := false
var _resize_origin := Vector2.ZERO
var _resize_start_size := Vector2.ZERO


func _init() -> void:
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_header = HBoxContainer.new()
	_header.mouse_filter = Control.MOUSE_FILTER_STOP
	_header.gui_input.connect(_on_header_input)
	add_child(_header)
	_title_label = Label.new()
	_title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_title_label.clip_text = true
	_title_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_header.add_child(_title_label)
	_pin_button = Button.new()
	_pin_button.text = "Закрепить"
	_pin_button.tooltip_text = "Закрепить блок: его нельзя будет двигать и менять размер"
	_pin_button.pressed.connect(_toggle_pinned)
	_header.add_child(_pin_button)
	_collapse_button = Button.new()
	_collapse_button.text = "Свернуть"
	_collapse_button.tooltip_text = "Свернуть блок до заголовка"
	_collapse_button.pressed.connect(_toggle_collapsed)
	_header.add_child(_collapse_button)
	_body = Control.new()
	_body.clip_contents = true
	add_child(_body)
	_grip = Control.new()
	_grip.mouse_default_cursor_shape = Control.CURSOR_FDIAGSIZE
	_grip.gui_input.connect(_on_grip_input)
	add_child(_grip)
	resized.connect(_update_layout)
	_update_layout()


func set_title(value: String) -> void:
	_title_label.text = value


# Переносит готовый узел редактора внутрь блока; узел растягивается на всю область содержимого.
func set_content(node: Control) -> void:
	var old_parent := node.get_parent()
	if old_parent != null:
		old_parent.remove_child(node)
	_body.add_child(node)
	node.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


# Состояние для сохранения раскладки: положение, размер, закрепление и свёрнутость.
func get_state() -> Dictionary:
	return {
		"key": panel_key,
		"x": position.x,
		"y": position.y,
		"w": size.x,
		"h": size.y,
		"pinned": pinned,
		"collapsed": collapsed,
		"expanded_height": _expanded_height,
	}


# Восстанавливает состояние из файла; значения с ошибками заменяются разумными по умолчанию.
func apply_state(state: Dictionary) -> void:
	position = Vector2(float(state.get("x", position.x)), float(state.get("y", position.y)))
	size = Vector2(float(state.get("w", size.x)), float(state.get("h", size.y))).max(MIN_SIZE)
	_expanded_height = maxf(MIN_SIZE.y, float(state.get("expanded_height", size.y)))
	pinned = bool(state.get("pinned", false))
	collapsed = bool(state.get("collapsed", false))
	_pin_button.text = "Открепить" if pinned else "Закрепить"
	_collapse_button.text = "Развернуть" if collapsed else "Свернуть"
	if collapsed:
		size.y = TITLE_HEIGHT
	_update_layout()
	_move_by(Vector2.ZERO)


# Выносит блок наверх (порядок наложения) и сообщает о новом состоянии.
func _raise() -> void:
	move_to_front()
	layout_changed.emit()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), BODY_COLOR)
	draw_rect(Rect2(Vector2.ZERO, Vector2(size.x, TITLE_HEIGHT)), HEADER_COLOR)
	draw_rect(Rect2(Vector2.ZERO, size), BORDER_COLOR, false, 1.0)
	if not pinned and not collapsed:
		for offset in [4.0, 8.0]:
			draw_line(
				Vector2(size.x - offset, size.y - 2.0),
				Vector2(size.x - 2.0, size.y - offset),
				GRIP_COLOR,
				1.0,
			)


func _update_layout() -> void:
	_header.position = Vector2.ZERO
	_header.size = Vector2(size.x, TITLE_HEIGHT)
	_body.visible = not collapsed
	_body.position = Vector2(0.0, TITLE_HEIGHT)
	_body.size = Vector2(size.x, maxf(0.0, size.y - TITLE_HEIGHT))
	_grip.visible = not pinned and not collapsed
	_grip.position = size - Vector2(GRIP_SIZE, GRIP_SIZE)
	_grip.size = Vector2(GRIP_SIZE, GRIP_SIZE)
	queue_redraw()


func _toggle_pinned() -> void:
	pinned = not pinned
	_pin_button.text = "Открепить" if pinned else "Закрепить"
	_dragging = false
	_resizing = false
	_update_layout()
	layout_changed.emit()


func _toggle_collapsed() -> void:
	if collapsed:
		collapsed = false
		size.y = _expanded_height
	else:
		_expanded_height = size.y
		collapsed = true
		size.y = TITLE_HEIGHT
	_collapse_button.text = "Развернуть" if collapsed else "Свернуть"
	_update_layout()
	layout_changed.emit()


func _on_header_input(event: InputEvent) -> void:
	if pinned:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_dragging = event.pressed
		if _dragging:
			_raise()
		else:
			layout_changed.emit()
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		_move_by(event.relative)
		accept_event()


func _move_by(delta: Vector2) -> void:
	var parent_control := get_parent() as Control
	var target := position + delta
	if parent_control != null:
		var area := parent_control.size
		target.x = clampf(target.x, KEEP_VISIBLE - size.x, area.x - KEEP_VISIBLE)
		target.y = clampf(target.y, 0.0, maxf(0.0, area.y - TITLE_HEIGHT))
	position = target


func _on_grip_input(event: InputEvent) -> void:
	if pinned or collapsed:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_resizing = event.pressed
		if _resizing:
			_raise()
			_resize_origin = get_global_mouse_position()
			_resize_start_size = size
		else:
			layout_changed.emit()
		accept_event()
	elif event is InputEventMouseMotion and _resizing:
		var delta := get_global_mouse_position() - _resize_origin
		size = (_resize_start_size + delta).max(MIN_SIZE)
		_expanded_height = size.y
		accept_event()
