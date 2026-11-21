extends PanelContainer

signal confirmed(image: Image)
signal cancelled

const AVATAR_SIZE := 150
const PREVIEW_SIZE := 260.0
const RESULT_SIZE := 100.0
const PANEL_COLOR := Color8(18, 20, 27)
const PANEL_BORDER := Color8(120, 96, 52)
const TITLE_COLOR := Color8(240, 209, 143)
const MUTED_COLOR := Color8(158, 173, 196)
const TEXT_COLOR := Color8(215, 220, 230)
const FRAME_COLOR := Color8(240, 200, 120)
const DIM_COLOR := Color(0.0, 0.0, 0.0, 0.55)
const CONFIRM_COLOR := Color8(70, 140, 220)

var _source: Image
var _source_texture: ImageTexture
var _scaled: Image
var _crop_origin := Vector2i.ZERO
var _scale_mode := false
var _dragging := false
var _preview: Control
var _result_view: TextureRect
var _info: Label


# Вызывать до добавления в дерево: source уже в формате RGBA8 и больше 150 px хотя бы по одной стороне.
func setup(source: Image) -> void:
	_source = source
	_source_texture = ImageTexture.create_from_image(source)
	_scaled = _fit_image(source)
	_crop_origin = Vector2i((source.get_width() - AVATAR_SIZE) / 2, (source.get_height() - AVATAR_SIZE) / 2)
	_build_ui()
	_refresh()


func _build_ui() -> void:
	add_theme_stylebox_override("panel", _panel_style())
	mouse_filter = Control.MOUSE_FILTER_STOP
	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 10)
	add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	margin.add_child(layout)

	layout.add_child(_label("Фото аккаунта · можно поставить PNG %d × %d px" % [AVATAR_SIZE, AVATAR_SIZE], 12, TITLE_COLOR))
	var hint := _label("Ваше фото %d × %d px больше нужного размера. Выберите, как привести его к %d × %d." % [
		_source.get_width(), _source.get_height(), AVATAR_SIZE, AVATAR_SIZE,
	], 10, MUTED_COLOR)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = PREVIEW_SIZE + 140.0
	layout.add_child(hint)

	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 10)
	layout.add_child(body)
	_preview = Control.new()
	_preview.custom_minimum_size = Vector2(PREVIEW_SIZE, PREVIEW_SIZE)
	_preview.mouse_filter = Control.MOUSE_FILTER_STOP
	_preview.mouse_default_cursor_shape = Control.CURSOR_MOVE
	_preview.draw.connect(_draw_preview)
	_preview.gui_input.connect(_on_preview_input)
	body.add_child(_preview)

	var side_column := VBoxContainer.new()
	side_column.custom_minimum_size = Vector2(130, 0)
	side_column.add_theme_constant_override("separation", 6)
	body.add_child(side_column)
	side_column.add_child(_label("Результат %d × %d" % [AVATAR_SIZE, AVATAR_SIZE], 10, MUTED_COLOR))
	_result_view = TextureRect.new()
	_result_view.custom_minimum_size = Vector2(RESULT_SIZE, RESULT_SIZE)
	_result_view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_result_view.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	side_column.add_child(_result_view)
	_info = _label("", 10, TEXT_COLOR)
	_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	side_column.add_child(_info)

	var mode_row := HBoxContainer.new()
	mode_row.add_theme_constant_override("separation", 6)
	layout.add_child(mode_row)
	var mode_group := ButtonGroup.new()
	var crop_button := _mode_button("Обрезать по рамке", mode_group, true)
	crop_button.toggled.connect(_on_crop_mode_toggled)
	mode_row.add_child(crop_button)
	var scale_button := _mode_button("Масштабировать", mode_group, false)
	scale_button.toggled.connect(_on_scale_mode_toggled)
	mode_row.add_child(scale_button)

	var action_row := HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 6)
	layout.add_child(action_row)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	action_row.add_child(spacer)
	var cancel_button := Button.new()
	cancel_button.text = "Отмена"
	cancel_button.custom_minimum_size = Vector2(90, 24)
	cancel_button.add_theme_font_size_override("font_size", 10)
	cancel_button.pressed.connect(_on_cancel_pressed)
	action_row.add_child(cancel_button)
	var confirm_button := Button.new()
	confirm_button.text = "Сохранить фото"
	confirm_button.custom_minimum_size = Vector2(130, 24)
	confirm_button.add_theme_font_size_override("font_size", 10)
	confirm_button.add_theme_stylebox_override("normal", _flat_style(CONFIRM_COLOR))
	confirm_button.pressed.connect(_on_confirm_pressed)
	action_row.add_child(confirm_button)


func _mode_button(text: String, group: ButtonGroup, pressed: bool) -> Button:
	var button := Button.new()
	button.text = text
	button.toggle_mode = true
	button.button_group = group
	button.button_pressed = pressed
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0, 24)
	button.add_theme_font_size_override("font_size", 10)
	button.add_theme_stylebox_override("normal", _flat_style(Color8(40, 44, 58)))
	button.add_theme_stylebox_override("hover", _flat_style(Color8(56, 62, 80)))
	button.add_theme_stylebox_override("pressed", _flat_style(CONFIRM_COLOR))
	button.add_theme_stylebox_override("hover_pressed", _flat_style(CONFIRM_COLOR.lightened(0.1)))
	return button


func _on_crop_mode_toggled(pressed: bool) -> void:
	if pressed:
		_set_scale_mode(false)


func _on_scale_mode_toggled(pressed: bool) -> void:
	if pressed:
		_set_scale_mode(true)


func _set_scale_mode(value: bool) -> void:
	_scale_mode = value
	_dragging = false
	_refresh()


func _refresh() -> void:
	if _result_view == null:
		return
	_result_view.texture = ImageTexture.create_from_image(_result_image())
	_info.text = _info_text()
	_preview.queue_redraw()


func _info_text() -> String:
	if _scale_mode:
		var empty_edges := "Пустые края будут прозрачными." if _source.get_width() != _source.get_height() else "Края совпадают с фото."
		return "Всё фото уменьшится до %d × %d px, пропорции сохранятся. %s" % [AVATAR_SIZE, AVATAR_SIZE, empty_edges]
	return "В кадре останется: x %d–%d, y %d–%d, без масштабирования. Двигайте рамку мышью." % [
		_crop_origin.x, _crop_origin.x + AVATAR_SIZE, _crop_origin.y, _crop_origin.y + AVATAR_SIZE,
	]


func _result_image() -> Image:
	if _scale_mode:
		return _scaled
	return _source.get_region(Rect2i(_crop_origin, Vector2i(AVATAR_SIZE, AVATAR_SIZE)))


func _view_scale() -> float:
	return minf(_preview.size.x / float(_source.get_width()), _preview.size.y / float(_source.get_height()))


func _view_rect() -> Rect2:
	var view_size := Vector2(_source.get_width(), _source.get_height()) * _view_scale()
	return Rect2((_preview.size - view_size) * 0.5, view_size)


func _frame_rect() -> Rect2:
	var view := _view_rect()
	var view_scale := _view_scale()
	return Rect2(view.position + Vector2(_crop_origin) * view_scale, Vector2(AVATAR_SIZE, AVATAR_SIZE) * view_scale)


func _draw_preview() -> void:
	var view := _view_rect()
	_preview.draw_texture_rect(_source_texture, view, false)
	if _scale_mode:
		_preview.draw_rect(view, FRAME_COLOR, false, 2.0)
		return
	_preview.draw_rect(view, DIM_COLOR)
	var frame := _frame_rect()
	_preview.draw_texture_rect_region(
		_source_texture, frame, Rect2(Vector2(_crop_origin), Vector2(AVATAR_SIZE, AVATAR_SIZE)),
	)
	_preview.draw_rect(frame, FRAME_COLOR, false, 2.0)


func _on_preview_input(event: InputEvent) -> void:
	if _scale_mode:
		return
	var button_event := event as InputEventMouseButton
	if button_event != null and button_event.button_index == MOUSE_BUTTON_LEFT:
		_dragging = button_event.pressed
		if _dragging:
			_center_crop_at(button_event.position)
		return
	var motion := event as InputEventMouseMotion
	if motion != null and _dragging:
		_center_crop_at(motion.position)


# Рамка центрируется под курсором и не выходит за края фото.
func _center_crop_at(local_point: Vector2) -> void:
	var view_scale := _view_scale()
	if view_scale <= 0.0:
		return
	var image_point := (local_point - _view_rect().position) / view_scale
	_crop_origin = Vector2i(
		clampi(roundi(image_point.x - AVATAR_SIZE * 0.5), 0, _source.get_width() - AVATAR_SIZE),
		clampi(roundi(image_point.y - AVATAR_SIZE * 0.5), 0, _source.get_height() - AVATAR_SIZE),
	)
	_refresh()


func _on_confirm_pressed() -> void:
	confirmed.emit(_result_image())


func _on_cancel_pressed() -> void:
	cancelled.emit()


# Фото уменьшается по большей стороне до 150 px; меньшая сторона остаётся прозрачным полем.
static func _fit_image(source: Image) -> Image:
	var width := source.get_width()
	var height := source.get_height()
	var factor := float(AVATAR_SIZE) / float(maxi(width, height))
	var fitted := Vector2i(maxi(1, roundi(width * factor)), maxi(1, roundi(height * factor)))
	var resized := Image.create_from_data(width, height, false, source.get_format(), source.get_data())
	resized.resize(fitted.x, fitted.y, Image.INTERPOLATE_LANCZOS)
	var result := Image.create(AVATAR_SIZE, AVATAR_SIZE, false, Image.FORMAT_RGBA8)
	result.fill(Color(0.0, 0.0, 0.0, 0.0))
	result.blit_rect(resized, Rect2i(Vector2i.ZERO, fitted), (Vector2i(AVATAR_SIZE, AVATAR_SIZE) - fitted) / 2)
	return result


static func _label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_COLOR
	style.border_color = PANEL_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.shadow_color = Color(0, 0, 0, 0.5)
	style.shadow_size = 10
	return style


static func _flat_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(4)
	return style
