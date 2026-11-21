extends Control

signal lobby_requested
signal quit_requested
signal quit_ready

const QUIT_DURATION := 5.0
const PANEL_WIDTH := 300.0
const OPEN_SHADE_ALPHA := 0.7
const QUIT_SHADE_ALPHA := 0.94
const PANEL_COLOR := Color8(24, 29, 34)
const BORDER_COLOR := Color8(194, 161, 94)
const TITLE_COLOR := Color8(238, 220, 178)
const BUTTON_COLOR := Color8(54, 69, 78)
const QUIT_BUTTON_COLOR := Color8(105, 69, 49)
const BUTTON_TEXT_COLOR := Color8(236, 226, 203)
const ERROR_COLOR := Color8(232, 135, 120)
const STATUS_COLOR := Color8(174, 175, 172)
const COUNTDOWN_COLOR := Color8(235, 225, 205)

var _shade: ColorRect
var _panel: PanelContainer
var _title: Label
var _message: Label
var _main_box: VBoxContainer
var _settings_box: VBoxContainer
var _countdown: Label
var _page := "main"
var _quitting := false
var _quit_remaining := 0.0
var _quit_disconnected := false
var _quit_ready_sent := false


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	z_index = 200
	visible = false
	set_process(false)

	_shade = ColorRect.new()
	_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_shade)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)

	_panel = PanelContainer.new()
	_panel.custom_minimum_size = Vector2(PANEL_WIDTH, 0)
	_panel.add_theme_stylebox_override("panel", _panel_style())
	center.add_child(_panel)

	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 16)
	_panel.add_child(margin)

	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 10)
	margin.add_child(layout)

	_title = Label.new()
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.add_theme_font_size_override("font_size", 18)
	_title.add_theme_color_override("font_color", TITLE_COLOR)
	layout.add_child(_title)

	_message = Label.new()
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.custom_minimum_size = Vector2(PANEL_WIDTH - 32.0, 0)
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_message.add_theme_font_size_override("font_size", 12)
	layout.add_child(_message)

	_main_box = VBoxContainer.new()
	_main_box.add_theme_constant_override("separation", 8)
	layout.add_child(_main_box)
	_add_button(_main_box, "НАСТРОЙКИ", BUTTON_COLOR, _on_settings_pressed)
	_add_button(_main_box, "ПОКИНУТЬ ИГРУ", QUIT_BUTTON_COLOR, _on_quit_pressed)
	_add_button(_main_box, "ВЫЙТИ В ЛОББИ", BUTTON_COLOR, _on_lobby_pressed)
	_add_button(_main_box, "ПРОДОЛЖИТЬ", BUTTON_COLOR, close)

	_settings_box = VBoxContainer.new()
	_settings_box.add_theme_constant_override("separation", 8)
	layout.add_child(_settings_box)
	var stub := Label.new()
	stub.text = "Настройки появятся позже"
	stub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stub.add_theme_font_size_override("font_size", 12)
	stub.add_theme_color_override("font_color", STATUS_COLOR)
	_settings_box.add_child(stub)
	_add_button(_settings_box, "НАЗАД", BUTTON_COLOR, _on_back_pressed)

	_countdown = Label.new()
	_countdown.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_countdown.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_countdown.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_countdown.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_countdown.add_theme_font_size_override("font_size", 20)
	_countdown.add_theme_color_override("font_color", COUNTDOWN_COLOR)
	_countdown.visible = false
	add_child(_countdown)
	_show_page("main")


func open(error_text := "") -> void:
	_quitting = false
	_quit_remaining = 0.0
	_quit_disconnected = false
	_quit_ready_sent = false
	set_process(false)
	_countdown.visible = false
	_panel.visible = true
	_shade.color = Color(0, 0, 0, OPEN_SHADE_ALPHA)
	if is_inside_tree():
		get_viewport().gui_release_focus()
	_show_page("main")
	_set_buttons_disabled(false)
	_set_message(error_text, true)
	visible = true


func close() -> void:
	if _quitting:
		return
	visible = false
	set_process(false)


func is_open() -> bool:
	return visible and not _quitting


func is_quitting() -> bool:
	return _quitting


func blocks_input() -> bool:
	return visible


func set_status(text: String) -> void:
	_set_buttons_disabled(true)
	_set_message(text, false)


func begin_quit() -> void:
	_quitting = true
	_quit_remaining = QUIT_DURATION
	_quit_disconnected = false
	_quit_ready_sent = false
	_panel.visible = false
	_countdown.visible = true
	visible = true
	set_process(true)
	_update_countdown()


# Выход завершается только когда и отключение прошло, и отсчёт закончился.
func mark_disconnected() -> void:
	if not _quitting:
		return
	_quit_disconnected = true
	_emit_quit_ready_if_done()


func _process(delta: float) -> void:
	if not _quitting:
		set_process(false)
		return
	_quit_remaining = maxf(0.0, _quit_remaining - maxf(0.0, delta))
	_update_countdown()
	_emit_quit_ready_if_done()


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	get_viewport().set_input_as_handled()
	if _quitting or not event is InputEventKey or not event.pressed or event.echo or event.keycode != KEY_ESCAPE:
		return
	if _page == "settings":
		_show_page("main")
	else:
		close()


func _emit_quit_ready_if_done() -> void:
	if _quit_ready_sent or not _quitting or not _quit_disconnected or _quit_remaining > 0.0:
		return
	_quit_ready_sent = true
	quit_ready.emit()


func _update_countdown() -> void:
	var progress := 1.0 - _quit_remaining / QUIT_DURATION
	_shade.color = Color(0, 0, 0, progress * QUIT_SHADE_ALPHA)
	_countdown.text = "Выход через %d..." % int(ceil(_quit_remaining))


func _show_page(page: String) -> void:
	_page = page
	_title.text = "НАСТРОЙКИ" if page == "settings" else "МЕНЮ"
	_main_box.visible = page == "main"
	_settings_box.visible = page == "settings"


func _set_message(text: String, is_error: bool) -> void:
	_message.text = text
	_message.visible = not text.is_empty()
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else STATUS_COLOR)


func _set_buttons_disabled(value: bool) -> void:
	for box in [_main_box, _settings_box]:
		for button in box.get_children():
			if button is Button:
				button.disabled = value


func _on_settings_pressed() -> void:
	_show_page("settings")


func _on_back_pressed() -> void:
	_show_page("main")


func _on_quit_pressed() -> void:
	quit_requested.emit()


func _on_lobby_pressed() -> void:
	lobby_requested.emit()


func _add_button(parent: Container, text: String, color: Color, handler: Callable) -> void:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(220, 34)
	button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	button.add_theme_font_size_override("font_size", 13)
	button.add_theme_color_override("font_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_hover_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_pressed_color", BUTTON_TEXT_COLOR)
	button.add_theme_color_override("font_disabled_color", STATUS_COLOR)
	button.add_theme_stylebox_override("normal", _button_style(color))
	button.add_theme_stylebox_override("hover", _button_style(color.lightened(0.12)))
	button.add_theme_stylebox_override("pressed", _button_style(color.darkened(0.12)))
	button.add_theme_stylebox_override("disabled", _button_style(color.darkened(0.3)))
	button.pressed.connect(handler)
	parent.add_child(button)


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_COLOR
	style.border_color = BORDER_COLOR
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	return style


static func _button_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(4)
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	return style
