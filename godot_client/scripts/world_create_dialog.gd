extends PanelContainer

signal mode_selected(mode: String)
signal launch_requested(saved_id: int, world_name: String, test: bool)
signal close_requested

const MODE_ORDER := ["front_line", "economy", "deck"]
const TITLE_COLOR := Color8(240, 209, 143)
const MUTED_COLOR := Color8(158, 173, 196)
const ERROR_COLOR := Color8(255, 120, 100)
const INFO_COLOR := Color8(200, 205, 215)

var _mode := "front_line"
var _is_admin := false
var _selected_saved_id := 0
var _mode_group := ButtonGroup.new()
var _map_group := ButtonGroup.new()
var _mode_buttons: Dictionary = {}
var _map_list: VBoxContainer
var _name_input: LineEdit
var _test_check: CheckBox
var _status: Label
var _launch_button: Button
var _cancel_button: Button


func setup(is_admin: bool, mode_names: Dictionary) -> void:
	_is_admin = is_admin
	for child in get_children():
		child.queue_free()
	_mode_buttons.clear()
	add_theme_stylebox_override("panel", _panel_style())
	custom_minimum_size = Vector2(400, 0)
	mouse_filter = Control.MOUSE_FILTER_STOP

	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 10)
	add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	margin.add_child(layout)

	layout.add_child(_label("Новый мир", 13, TITLE_COLOR))
	layout.add_child(_label("Сначала выберите режим, затем карту этого режима.", 10, MUTED_COLOR))

	layout.add_child(_label("Название", 10, MUTED_COLOR))
	_name_input = LineEdit.new()
	_name_input.placeholder_text = "По умолчанию — название карты"
	_name_input.max_length = 64
	_name_input.custom_minimum_size.y = 24
	_name_input.add_theme_font_size_override("font_size", 11)
	layout.add_child(_name_input)

	layout.add_child(_label("Режим", 10, MUTED_COLOR))
	var mode_row := HBoxContainer.new()
	mode_row.add_theme_constant_override("separation", 4)
	layout.add_child(mode_row)
	for mode_key in MODE_ORDER:
		var button := Button.new()
		button.text = str(mode_names.get(mode_key, mode_key))
		button.toggle_mode = true
		button.button_group = _mode_group
		button.custom_minimum_size = Vector2(0, 24)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.add_theme_font_size_override("font_size", 11)
		button.pressed.connect(_on_mode_pressed.bind(mode_key))
		mode_row.add_child(button)
		_mode_buttons[mode_key] = button
	(_mode_buttons[_mode] as Button).button_pressed = true

	layout.add_child(_label("Карта этого режима", 10, MUTED_COLOR))
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(0, 120)
	layout.add_child(scroll)
	_map_list = VBoxContainer.new()
	_map_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_map_list.add_theme_constant_override("separation", 3)
	scroll.add_child(_map_list)

	if _is_admin:
		_test_check = CheckBox.new()
		_test_check.text = "Тестовый мир (виден только модераторам и админам)"
		_test_check.button_pressed = true
		_test_check.add_theme_font_size_override("font_size", 11)
		layout.add_child(_test_check)
	else:
		layout.add_child(_label("Модераторы создают тестовые миры: их видят модераторы и админы.", 10, MUTED_COLOR))

	_status = _label("", 10, ERROR_COLOR)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(_status)

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 6)
	buttons.alignment = BoxContainer.ALIGNMENT_END
	layout.add_child(buttons)
	_cancel_button = Button.new()
	_cancel_button.text = "Отмена"
	_cancel_button.custom_minimum_size = Vector2(80, 24)
	_cancel_button.add_theme_font_size_override("font_size", 11)
	_cancel_button.pressed.connect(func() -> void: close_requested.emit())
	buttons.add_child(_cancel_button)
	_launch_button = Button.new()
	_launch_button.text = "Запустить мир"
	_launch_button.custom_minimum_size = Vector2(110, 24)
	_launch_button.add_theme_font_size_override("font_size", 11)
	_launch_button.disabled = true
	_launch_button.pressed.connect(_on_launch_pressed)
	buttons.add_child(_launch_button)

	show_loading()


func current_mode() -> String:
	return _mode


func show_loading() -> void:
	_selected_saved_id = 0
	_map_group = ButtonGroup.new()
	_update_launch_button()
	_clear_map_list()
	_map_list.add_child(_label("Загружаем карты…", 10, MUTED_COLOR))


func show_maps(maps: Array) -> void:
	_selected_saved_id = 0
	_map_group = ButtonGroup.new()
	_update_launch_button()
	_clear_map_list()
	if maps.is_empty():
		var empty_label := _label("В этом режиме пока нет сохранённых карт. Сохраните карту в редакторе карт.", 10, MUTED_COLOR)
		empty_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_map_list.add_child(empty_label)
		return
	for saved_map in maps:
		if not saved_map is Dictionary:
			continue
		var button := Button.new()
		button.text = "%s · %d×%d" % [
			str(saved_map.get("name", "Карта")),
			int(saved_map.get("map_w", 0)),
			int(saved_map.get("map_h", 0)),
		]
		button.toggle_mode = true
		button.button_group = _map_group
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.custom_minimum_size = Vector2(0, 24)
		button.add_theme_font_size_override("font_size", 11)
		button.pressed.connect(_on_map_pressed.bind(int(saved_map.get("id", 0))))
		_map_list.add_child(button)


func set_status(text: String, is_error := true) -> void:
	_status.text = text
	_status.add_theme_color_override("font_color", ERROR_COLOR if is_error else INFO_COLOR)


func set_busy(busy: bool) -> void:
	_name_input.editable = not busy
	_cancel_button.disabled = busy
	_launch_button.disabled = busy or _selected_saved_id <= 0
	if _test_check != null:
		_test_check.disabled = busy


func _on_mode_pressed(mode_key: String) -> void:
	if mode_key == _mode:
		return
	_mode = mode_key
	show_loading()
	mode_selected.emit(mode_key)


func _on_map_pressed(saved_id: int) -> void:
	_selected_saved_id = saved_id
	_update_launch_button()


func _on_launch_pressed() -> void:
	if _selected_saved_id <= 0:
		set_status("Выберите карту этого режима")
		return
	var test := _test_check.button_pressed if _is_admin else true
	launch_requested.emit(_selected_saved_id, _name_input.text.strip_edges(), test)


func _update_launch_button() -> void:
	_launch_button.disabled = _selected_saved_id <= 0


func _clear_map_list() -> void:
	for child in _map_list.get_children():
		_map_list.remove_child(child)
		child.queue_free()


func _label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color8(20, 21, 27, 252)
	style.border_color = Color8(122, 92, 48)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.shadow_color = Color(0, 0, 0, 0.5)
	style.shadow_size = 14
	return style
