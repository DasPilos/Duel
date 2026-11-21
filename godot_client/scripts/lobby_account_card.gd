extends PanelContainer

signal menu_requested(global_point: Vector2)

# В базовых единицах 1280×720: при окне 1920×1080 (масштаб 1.5) это 150 px, как у фото.
const AVATAR_SIZE := 100
const FRAME_COLOR := Color8(201, 160, 84)
const FRAME_BACKGROUND := Color8(14, 15, 18)
const HINT_COLOR := Color8(158, 173, 196)

var _texture_rect: TextureRect
var _hint: Label


func _init() -> void:
	add_theme_stylebox_override("panel", _frame_style())
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	tooltip_text = "ПКМ — меню фото аккаунта"
	gui_input.connect(_on_gui_input)

	var area := Control.new()
	area.custom_minimum_size = Vector2(AVATAR_SIZE, AVATAR_SIZE)
	add_child(area)

	_texture_rect = TextureRect.new()
	_texture_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_texture_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	area.add_child(_texture_rect)

	_hint = Label.new()
	_hint.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_hint.text = "ПКМ —\nфото аккаунта"
	_hint.add_theme_font_size_override("font_size", 10)
	_hint.add_theme_color_override("font_color", HINT_COLOR)
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	area.add_child(_hint)


func set_avatar(texture: Texture2D) -> void:
	_texture_rect.texture = texture
	_hint.visible = texture == null


func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		menu_requested.emit(get_global_mouse_position())


static func _frame_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = FRAME_BACKGROUND
	style.border_color = FRAME_COLOR
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	style.shadow_color = Color(0, 0, 0, 0.45)
	style.shadow_size = 4
	return style
