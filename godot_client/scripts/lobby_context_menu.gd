extends PanelContainer

signal entry_chosen(entry_id: String, payload: Dictionary)

const MENU_WIDTH := 180.0
const FONT_SIZE := 11
const BACKGROUND := Color8(24, 26, 36)
const BORDER := Color8(110, 120, 150)
const HOVER_COLOR := Color8(62, 84, 120)
const TEXT_COLOR := Color8(225, 230, 240)
const DISABLED_COLOR := Color8(104, 110, 124)
const INFO_COLOR := Color8(158, 173, 196)

var _entries_box: VBoxContainer
var _payload: Dictionary = {}


func _init() -> void:
	top_level = true
	visible = false
	z_index = 200
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(MENU_WIDTH, 0)
	add_theme_stylebox_override("panel", _panel_style())
	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 4)
	add_child(margin)
	_entries_box = VBoxContainer.new()
	_entries_box.add_theme_constant_override("separation", 2)
	margin.add_child(_entries_box)


# Пункты с disabled серые и не реагируют. Строки с label — пояснения без нажатия.
func open_at(point: Vector2, entries: Array, payload: Dictionary = {}) -> void:
	_payload = payload.duplicate(true)
	for child in _entries_box.get_children():
		_entries_box.remove_child(child)
		child.queue_free()
	for entry in entries:
		if entry is Dictionary:
			_add_entry(entry)
	visible = true
	var menu_size := get_combined_minimum_size()
	size = menu_size
	var viewport := get_viewport_rect().size
	global_position = Vector2(
		clampf(point.x, 0.0, maxf(0.0, viewport.x - menu_size.x)),
		clampf(point.y, 0.0, maxf(0.0, viewport.y - menu_size.y)),
	)


func close() -> void:
	visible = false
	_payload.clear()


func _input(event: InputEvent) -> void:
	if not visible:
		return
	var mouse_event := event as InputEventMouseButton
	if mouse_event != null and mouse_event.pressed and not get_global_rect().has_point(mouse_event.position):
		close()
		return
	var key_event := event as InputEventKey
	if key_event != null and key_event.pressed and key_event.keycode == KEY_ESCAPE:
		close()
		get_viewport().set_input_as_handled()


func _add_entry(entry: Dictionary) -> void:
	var text := str(entry.get("text", ""))
	if bool(entry.get("label", false)):
		var label := Label.new()
		label.text = text
		label.add_theme_font_size_override("font_size", FONT_SIZE - 1)
		label.add_theme_color_override("font_color", INFO_COLOR)
		_entries_box.add_child(label)
		return
	var button := Button.new()
	button.text = text
	button.flat = true
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.focus_mode = Control.FOCUS_NONE
	button.disabled = bool(entry.get("disabled", false))
	button.add_theme_font_size_override("font_size", FONT_SIZE)
	button.add_theme_color_override("font_color", TEXT_COLOR)
	button.add_theme_color_override("font_hover_color", TEXT_COLOR)
	button.add_theme_color_override("font_disabled_color", DISABLED_COLOR)
	button.add_theme_stylebox_override("hover", _hover_style())
	button.add_theme_stylebox_override("pressed", _hover_style())
	button.pressed.connect(_on_entry_pressed.bind(str(entry.get("id", ""))))
	_entries_box.add_child(button)


func _on_entry_pressed(entry_id: String) -> void:
	var payload := _payload.duplicate(true)
	close()
	entry_chosen.emit(entry_id, payload)


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = BACKGROUND
	style.border_color = BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.shadow_color = Color(0, 0, 0, 0.45)
	style.shadow_size = 4
	return style


static func _hover_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = HOVER_COLOR
	style.set_corner_radius_all(3)
	style.content_margin_left = 6
	style.content_margin_right = 6
	return style
