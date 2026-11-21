extends Node

const BASE_RESOLUTION := Vector2i(1280, 720)
const DEFAULT_RESOLUTION := Vector2i(1920, 1080)
const PREVIOUS_DEFAULT_RESOLUTION := Vector2i(1280, 720)
const SETTINGS_PATH := "user://display_settings.cfg"
const CONFIRM_SECONDS := 10
const DISPLAY_MODES := [
	{"id": "windowed", "name": "Оконный"},
	{"id": "borderless", "name": "Безрамочный"},
	{"id": "fullscreen", "name": "Полноэкранный"},
]
const UI_SCALES := [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]
const COMMON_RESOLUTIONS := [
	Vector2i(960, 540),
	Vector2i(1024, 576),
	Vector2i(1280, 800),
	Vector2i(1280, 720),
	Vector2i(1440, 900),
	Vector2i(1600, 900),
	Vector2i(1680, 1050),
	Vector2i(1920, 1080),
	Vector2i(1920, 1200),
	Vector2i(2560, 1080),
	Vector2i(2560, 1440),
	Vector2i(2560, 1600),
	Vector2i(3440, 1440),
	Vector2i(3840, 1600),
	Vector2i(3840, 2160),
	Vector2i(5120, 1440),
]

var _settings: Dictionary = {
	"resolution": DEFAULT_RESOLUTION,
	"mode": "windowed",
	"ui_scale": 1.0,
}
var _pending_settings: Dictionary = {}
var _previous_settings: Dictionary = {}
var _canvas_layer: CanvasLayer
var _overlay: Control
var _settings_panel: PanelContainer
var _settings_center: CenterContainer
var _confirm_center: CenterContainer
var _confirm_panel: PanelContainer
var _resolution_select: OptionButton
var _mode_select: OptionButton
var _scale_select: OptionButton
var _settings_message: Label
var _confirm_message: Label
var _confirm_button: Button
var _confirm_timer: Timer
var _open_button: Button
var _seconds_remaining := CONFIRM_SECONDS


func _ready() -> void:
	_load_settings()
	_configure_logical_viewport()
	_build_settings_ui()
	_apply_settings(_settings)


func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo or event.keycode != KEY_ESCAPE:
		return
	if not _overlay.visible:
		return
	if _confirm_panel.visible:
		_revert_pending_settings()
	else:
		_close_settings()
	get_viewport().set_input_as_handled()


func _configure_logical_viewport() -> void:
	var window := get_window()
	window.content_scale_size = BASE_RESOLUTION
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND


func _load_settings(path: String = SETTINGS_PATH) -> void:
	var config := ConfigFile.new()
	var error := config.load(path)
	if error == ERR_FILE_NOT_FOUND:
		return
	if error != OK:
		push_error("Не удалось загрузить настройки экрана: %s" % error_string(error))
		return

	var resolution: Variant = config.get_value(
		"display",
		"resolution",
		[DEFAULT_RESOLUTION.x, DEFAULT_RESOLUTION.y]
	)
	if resolution is Array and resolution.size() == 2:
		var parsed_resolution := Vector2i(int(resolution[0]), int(resolution[1]))
		if parsed_resolution.x >= 960 and parsed_resolution.y >= 540:
			_settings["resolution"] = (
				DEFAULT_RESOLUTION if parsed_resolution == PREVIOUS_DEFAULT_RESOLUTION
				else parsed_resolution
			)

	var mode := str(config.get_value("display", "mode", "windowed"))
	if _is_valid_mode(mode):
		_settings["mode"] = mode

	var ui_scale := float(config.get_value("display", "ui_scale", 1.0))
	if UI_SCALES.has(ui_scale):
		_settings["ui_scale"] = ui_scale


func _save_settings() -> Error:
	var config := ConfigFile.new()
	var resolution: Vector2i = _settings["resolution"]
	config.set_value("display", "resolution", [resolution.x, resolution.y])
	config.set_value("display", "mode", _settings["mode"])
	config.set_value("display", "ui_scale", _settings["ui_scale"])
	var error := config.save(SETTINGS_PATH)
	if error != OK:
		push_error("Не удалось сохранить настройки экрана: %s" % error_string(error))
	return error


func _build_settings_ui() -> void:
	_canvas_layer = CanvasLayer.new()
	_canvas_layer.layer = 100
	add_child(_canvas_layer)

	_overlay = Control.new()
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	_canvas_layer.add_child(_overlay)

	var backdrop := ColorRect.new()
	backdrop.color = Color(0.012, 0.016, 0.025, 0.78)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.add_child(backdrop)

	_settings_center = CenterContainer.new()
	_settings_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_settings_center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(_settings_center)
	_settings_panel = PanelContainer.new()
	_settings_panel.custom_minimum_size = Vector2(560, 0)
	_settings_panel.add_theme_stylebox_override("panel", _dialog_panel_style())
	_settings_center.add_child(_settings_panel)

	var settings_margin := MarginContainer.new()
	for side in ["left", "top", "right", "bottom"]:
		settings_margin.add_theme_constant_override("margin_" + side, 28)
	_settings_panel.add_child(settings_margin)

	var settings_content := VBoxContainer.new()
	settings_content.add_theme_constant_override("separation", 14)
	settings_margin.add_child(settings_content)

	var title := Label.new()
	title.text = "Экран и графика"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(0.94, 0.82, 0.56))
	settings_content.add_child(title)

	_settings_message = Label.new()
	_settings_message.text = "Базовая область игры — 1280×720. На широких окнах сцена расширяется без растягивания. Масштаб применяется ко всему 2D-содержимому."
	_settings_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_settings_message.add_theme_color_override("font_color", Color(0.70, 0.73, 0.79))
	settings_content.add_child(_settings_message)

	_resolution_select = _add_option_row(settings_content, "Разрешение окна")
	_mode_select = _add_option_row(settings_content, "Режим экрана")
	_scale_select = _add_option_row(settings_content, "Масштаб интерфейса и сцены")

	var settings_buttons := HBoxContainer.new()
	settings_buttons.add_theme_constant_override("separation", 12)
	settings_content.add_child(settings_buttons)
	var apply_button := Button.new()
	apply_button.text = "Применить"
	apply_button.custom_minimum_size.y = 42
	apply_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	apply_button.pressed.connect(_apply_selected_settings)
	settings_buttons.add_child(apply_button)
	var close_button := Button.new()
	close_button.text = "Закрыть"
	close_button.custom_minimum_size.y = 42
	close_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	close_button.pressed.connect(_close_settings)
	settings_buttons.add_child(close_button)

	_confirm_center = CenterContainer.new()
	_confirm_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_confirm_center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_confirm_center.visible = false
	_overlay.add_child(_confirm_center)
	_confirm_panel = PanelContainer.new()
	_confirm_panel.custom_minimum_size = Vector2(500, 220)
	_confirm_panel.add_theme_stylebox_override("panel", _dialog_panel_style())
	_confirm_panel.visible = false
	_confirm_center.add_child(_confirm_panel)

	var confirm_content := VBoxContainer.new()
	confirm_content.add_theme_constant_override("separation", 16)
	_confirm_panel.add_child(confirm_content)
	_confirm_message = Label.new()
	_confirm_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_confirm_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_confirm_message.add_theme_font_size_override("font_size", 20)
	confirm_content.add_child(_confirm_message)
	_confirm_button = Button.new()
	_confirm_button.text = "Оставить настройки"
	_confirm_button.custom_minimum_size.y = 44
	_confirm_button.pressed.connect(_confirm_pending_settings)
	confirm_content.add_child(_confirm_button)
	_confirm_timer = Timer.new()
	_confirm_timer.wait_time = 1.0
	_confirm_timer.timeout.connect(_on_confirm_timer_timeout)
	add_child(_confirm_timer)

	_open_button = Button.new()
	_open_button.text = "Настройки"
	_open_button.tooltip_text = "Разрешение и масштаб интерфейса"
	_open_button.custom_minimum_size = Vector2(132, 42)
	_open_button.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	_open_button.offset_left = -150
	_open_button.offset_top = 18
	_open_button.offset_right = -18
	_open_button.offset_bottom = 60
	_open_button.visible = false
	_open_button.pressed.connect(_open_settings)
	_canvas_layer.add_child(_open_button)


func set_settings_button_visible(is_visible: bool) -> void:
	if _open_button != null:
		_open_button.visible = is_visible


func _dialog_panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.055, 0.06, 0.07, 1.0)
	style.border_color = Color(0.48, 0.36, 0.19)
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.55)
	style.shadow_size = 16
	style.shadow_offset = Vector2(0, 6)
	return style


func _add_option_row(parent: VBoxContainer, title: String) -> OptionButton:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	parent.add_child(row)

	var label := Label.new()
	label.text = title
	label.custom_minimum_size.x = 190
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(label)

	var option := OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	option.custom_minimum_size.y = 40
	row.add_child(option)
	return option


func _open_settings() -> void:
	if _confirm_panel.visible:
		return
	_populate_options()
	if Engine.is_embedded_in_editor():
		_settings_message.text = "Игра запущена во встроенном окне редактора Godot: изменить размер и режим окна здесь нельзя. Для проверки запустите игру отдельным окном. Масштаб интерфейса доступен."
	else:
		_settings_message.text = "Базовая область игры — 1280×720. На широких окнах сцена расширяется без растягивания. Масштаб применяется ко всему 2D-содержимому."
	_settings_panel.visible = true
	_overlay.visible = true


func _close_settings() -> void:
	if _confirm_panel.visible:
		_revert_pending_settings()
		return
	_overlay.visible = false


func _populate_options() -> void:
	_resolution_select.clear()
	var available_resolutions := _get_available_resolutions()
	var current_resolution: Vector2i = _settings["resolution"]
	if not available_resolutions.has(current_resolution):
		available_resolutions.append(current_resolution)
	available_resolutions.sort_custom(
		func(a: Vector2i, b: Vector2i) -> bool:
			return a.x * a.y < b.x * b.y
	)
	for resolution in available_resolutions:
		_resolution_select.add_item("%d × %d" % [resolution.x, resolution.y])
		_resolution_select.set_item_metadata(_resolution_select.item_count - 1, resolution)
		if resolution == current_resolution:
			_resolution_select.select(_resolution_select.item_count - 1)

	_mode_select.clear()
	for mode in DISPLAY_MODES:
		_mode_select.add_item(str(mode["name"]))
		_mode_select.set_item_metadata(_mode_select.item_count - 1, mode["id"])
		if mode["id"] == _settings["mode"]:
			_mode_select.select(_mode_select.item_count - 1)
	if not _mode_select.item_selected.is_connected(_on_mode_selected):
		_mode_select.item_selected.connect(_on_mode_selected)

	_scale_select.clear()
	for scale in UI_SCALES:
		_scale_select.add_item("%d%%" % roundi(scale * 100.0))
		_scale_select.set_item_metadata(_scale_select.item_count - 1, scale)
		if is_equal_approx(scale, float(_settings["ui_scale"])):
			_scale_select.select(_scale_select.item_count - 1)

	_mode_select.disabled = Engine.is_embedded_in_editor()
	_resolution_select.disabled = Engine.is_embedded_in_editor() or str(_settings["mode"]) != "windowed"


func _on_mode_selected(index: int) -> void:
	_resolution_select.disabled = Engine.is_embedded_in_editor() or str(_mode_select.get_item_metadata(index)) != "windowed"


func _get_available_resolutions() -> Array[Vector2i]:
	var screen_size := DisplayServer.screen_get_size()
	if screen_size.x < 960 or screen_size.y < 540:
		screen_size = Vector2i(1920, 1080)

	var resolutions: Array[Vector2i] = []
	for resolution in COMMON_RESOLUTIONS:
		if resolution.x <= screen_size.x and resolution.y <= screen_size.y:
			resolutions.append(resolution)
	if not resolutions.has(DEFAULT_RESOLUTION):
		resolutions.append(DEFAULT_RESOLUTION)
	return resolutions


func _apply_selected_settings() -> void:
	if _resolution_select.selected < 0 or _mode_select.selected < 0 or _scale_select.selected < 0:
		_settings_message.text = "Выберите разрешение, режим экрана и масштаб интерфейса."
		return

	_previous_settings = _settings.duplicate(true)
	if Engine.is_embedded_in_editor():
		var selected_scale: float = _scale_select.get_item_metadata(_scale_select.selected)
		if is_equal_approx(selected_scale, float(_settings["ui_scale"])):
			_settings_message.text = "Разрешение и режим окна нельзя изменить во встроенном запуске. Отключите «Встроить игру при следующем запуске» в настройках редактора Godot."
			return
		_pending_settings = _settings.duplicate(true)
		_pending_settings["ui_scale"] = selected_scale
	else:
		_pending_settings = {
			"resolution": _resolution_select.get_item_metadata(_resolution_select.selected),
			"mode": _mode_select.get_item_metadata(_mode_select.selected),
			"ui_scale": _scale_select.get_item_metadata(_scale_select.selected),
		}
	_apply_settings(_pending_settings)
	_seconds_remaining = CONFIRM_SECONDS
	_settings_panel.visible = false
	_confirm_center.visible = true
	_confirm_panel.visible = true
	_confirm_message.text = "Оставить эти настройки экрана?\nАвтоматический возврат через %d сек." % _seconds_remaining
	_overlay.visible = true
	_confirm_timer.start()


func _on_confirm_timer_timeout() -> void:
	_seconds_remaining -= 1
	if _seconds_remaining <= 0:
		_revert_pending_settings()
		return
	_confirm_message.text = "Оставить эти настройки экрана?\nАвтоматический возврат через %d сек." % _seconds_remaining


func _confirm_pending_settings() -> void:
	_confirm_timer.stop()
	_settings = _pending_settings.duplicate(true)
	var error := _save_settings()
	if error != OK:
		_settings = _previous_settings.duplicate(true)
		_apply_settings(_settings)
		_confirm_panel.visible = false
		_confirm_center.visible = false
		_settings_panel.visible = true
		_populate_options()
		_settings_message.text = "Настройки применены, но не сохранены. Проверьте права доступа к папке данных."
		_pending_settings.clear()
		_overlay.visible = true
		return
	_pending_settings.clear()
	_confirm_panel.visible = false
	_confirm_center.visible = false
	_overlay.visible = false


func _revert_pending_settings() -> void:
	_confirm_timer.stop()
	_apply_settings(_previous_settings)
	_settings = _previous_settings.duplicate(true)
	_pending_settings.clear()
	_confirm_panel.visible = false
	_confirm_center.visible = false
	_settings_panel.visible = true
	_populate_options()
	_settings_message.text = "Настройки отменены. Выберите другие параметры или закройте окно."
	_overlay.visible = true


func _apply_settings(settings: Dictionary) -> void:
	var window := get_window()
	window.content_scale_factor = float(settings["ui_scale"])
	if DisplayServer.get_name() == "headless" or Engine.is_embedded_in_editor():
		return

	var mode := str(settings["mode"])
	if mode == "fullscreen":
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
		return

	var screen_position := DisplayServer.screen_get_position()
	var screen_size := DisplayServer.screen_get_size()
	if mode == "borderless":
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
		DisplayServer.window_set_position(screen_position)
		DisplayServer.window_set_size(screen_size)
		return

	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
	var resolution: Vector2i = settings["resolution"]
	DisplayServer.window_set_size(resolution)
	DisplayServer.window_set_position(screen_position + (screen_size - resolution) / 2)


func _is_valid_mode(mode: String) -> bool:
	for available_mode in DISPLAY_MODES:
		if available_mode["id"] == mode:
			return true
	return false
