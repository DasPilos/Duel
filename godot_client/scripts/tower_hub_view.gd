extends Control

# Таверна Tower: фон assets/tavern и три кнопки Python — «Комната отдыха», «Выход на улицу», «Хозяин трактира».
# Горячие зоны картинки заменены кнопками вверху по центру: подписи видны без наведения, а открытый чат (внизу слева) их не закрывает.

signal room_requested
signal street_requested
signal bartender_requested

const FALLBACK_COLOR := Color8(38, 27, 24)
const TITLE_COLOR := Color8(240, 210, 140)
const MUTED_COLOR := Color8(200, 200, 205)
const BUTTON_SIZE := Vector2(210.0, 44.0)
const BUTTON_FONT_SIZE := 17
const BUTTON_FILL := Color8(24, 29, 38, 226)
const BUTTON_HOVER_FILL := Color8(44, 52, 64, 236)
const BUTTON_PRESSED_FILL := Color8(92, 72, 40, 240)
const BUTTON_BORDER_COLOR := Color8(190, 150, 80)

static var _background: Texture2D = null
static var _background_loaded := false

var _character_label: Label
var _status: Label
var _buttons: Dictionary = {}


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(queue_redraw)

	var title := Label.new()
	title.text = "Таверна"
	title.position = Vector2(40.0, 26.0)
	title.add_theme_font_size_override("font_size", 26)
	title.add_theme_color_override("font_color", TITLE_COLOR)
	add_child(title)

	_character_label = Label.new()
	_character_label.position = Vector2(40.0, 64.0)
	_character_label.add_theme_color_override("font_color", MUTED_COLOR)
	add_child(_character_label)

	var menu := VBoxContainer.new()
	menu.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	menu.grow_horizontal = Control.GROW_DIRECTION_BOTH
	menu.grow_vertical = Control.GROW_DIRECTION_END
	menu.offset_top = 120.0
	menu.add_theme_constant_override("separation", 8)
	add_child(menu)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 12)
	menu.add_child(row)
	_buttons["room"] = _make_button(row, "Комната отдыха", _on_room_pressed)
	_buttons["street"] = _make_button(row, "Выход на улицу", _on_street_pressed)
	_buttons["bartender"] = _make_button(row, "Хозяин трактира", _on_bartender_pressed)

	_status = Label.new()
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status.add_theme_color_override("font_color", MUTED_COLOR)
	menu.add_child(_status)


func _draw() -> void:
	var texture := background_texture()
	if texture == null:
		draw_rect(Rect2(Vector2.ZERO, size), FALLBACK_COLOR)
	else:
		draw_texture_rect(texture, Rect2(Vector2.ZERO, size), false)


static func background_texture() -> Texture2D:
	if not _background_loaded:
		_background_loaded = true
		var path := ProjectSettings.globalize_path("res://").path_join("../assets/tavern/background_original.png").simplify_path()
		if FileAccess.file_exists(path):
			var image := Image.load_from_file(path)
			if image != null and not image.is_empty():
				_background = ImageTexture.create_from_image(image)
	return _background


func set_character_text(text: String) -> void:
	_character_label.text = text


func set_status(text: String) -> void:
	_status.text = text


func button(key: String) -> Button:
	return _buttons.get(key) as Button


func _make_button(parent: Container, text: String, handler: Callable) -> Button:
	var item := Button.new()
	item.text = text
	item.focus_mode = Control.FOCUS_NONE
	item.custom_minimum_size = BUTTON_SIZE
	item.add_theme_font_size_override("font_size", BUTTON_FONT_SIZE)
	item.add_theme_stylebox_override("normal", _button_style(BUTTON_FILL))
	item.add_theme_stylebox_override("hover", _button_style(BUTTON_HOVER_FILL))
	item.add_theme_stylebox_override("pressed", _button_style(BUTTON_PRESSED_FILL))
	item.add_theme_stylebox_override("focus", _button_style(BUTTON_FILL))
	item.pressed.connect(handler)
	parent.add_child(item)
	return item


func _button_style(fill: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = BUTTON_BORDER_COLOR
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(6.0)
	return style


func _on_room_pressed() -> void:
	room_requested.emit()


func _on_street_pressed() -> void:
	street_requested.emit()


func _on_bartender_pressed() -> void:
	bartender_requested.emit()
