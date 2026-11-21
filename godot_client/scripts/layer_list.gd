extends ScrollContainer

const RULES = preload("res://scripts/layer_rules.gd")

signal layer_selected(layer_id: int)
signal visibility_toggled(layer_id: int)
signal layer_renamed(layer_id: int, new_name: String)
signal layer_dropped(layer_id: int, target_id: int, above: bool)

const DRAG_TYPE := "layer_row"
const ROW_HEIGHT := 13.0
const INDENT_WIDTH := 7.0
const EYE_SIZE := Vector2(16.0, 11.0)
const NUMBER_WIDTH := 11.0
const LOCK_WIDTH := 9.0
const NAME_MAX_LENGTH := 40
const HIDDEN_FILL := Color8(30, 32, 36)
const SELECTED_BORDER := Color(1.0, 1.0, 1.0, 0.95)
const DROP_BORDER := Color8(255, 214, 72)
const EYE_SHOWN := Color8(52, 58, 66)
const EYE_SHOWN_HOVER := Color8(76, 84, 96)
const EYE_HIDDEN := Color8(226, 96, 48)
const EYE_HIDDEN_HOVER := Color8(246, 128, 76)
const ICON_COLOR := Color8(232, 238, 244)
const EDIT_FILL := Color8(14, 16, 20)

var _rows_box: VBoxContainer
var _rows: Dictionary = {}
var _active_id := 0
var _renaming_id := 0
var _drop_id := 0
var _drop_above := false
var _eye_styles: Dictionary = {}


func _init() -> void:
	horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	custom_minimum_size = Vector2(0.0, 40.0)
	_rows_box = VBoxContainer.new()
	_rows_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows_box.add_theme_constant_override("separation", 1)
	add_child(_rows_box)
	_eye_styles = {
		"shown": _flat_style(EYE_SHOWN),
		"shown_hover": _flat_style(EYE_SHOWN_HOVER),
		"hidden": _flat_style(EYE_HIDDEN),
		"hidden_hover": _flat_style(EYE_HIDDEN_HOVER),
	}


func _notification(what: int) -> void:
	if what == NOTIFICATION_DRAG_END:
		_clear_drop_target()


# Строки переиспользуются по id слоя: выбор и перетаскивание не пересоздают нажатую строку.
func refresh(entries: Array, active_id: int) -> void:
	var previous_active := _active_id
	_active_id = active_id
	var seen := {}
	for index in range(entries.size()):
		var entry: Dictionary = entries[index]
		var layer_id := int(entry.get("id", 0))
		seen[layer_id] = true
		if not _rows.has(layer_id):
			var created := _build_row(layer_id)
			_rows[layer_id] = created
			_rows_box.add_child(created["panel"])
		var row: Dictionary = _rows[layer_id]
		row["entry"] = entry
		_rows_box.move_child(row["panel"], index)
	for layer_id in _rows.keys():
		if not seen.has(layer_id):
			_remove_row(int(layer_id))
	for layer_id in _rows:
		_apply_row(int(layer_id))
	if active_id != previous_active:
		call_deferred("_ensure_row_visible", active_id)


func set_active(layer_id: int) -> void:
	var previous_active := _active_id
	_active_id = layer_id
	for row_id in _rows:
		_apply_row(int(row_id))
	if layer_id != previous_active:
		call_deferred("_ensure_row_visible", layer_id)


func get_row(layer_id: int) -> Dictionary:
	return _rows.get(layer_id, {})


func row_ids() -> Array[int]:
	var ids: Array[int] = []
	for child in _rows_box.get_children():
		ids.append(int(child.get_meta("layer_id", 0)))
	return ids


func is_renaming() -> bool:
	return _renaming_id != 0


func begin_rename(layer_id: int) -> void:
	if not _rows.has(layer_id):
		return
	_finish_rename(true)
	var row: Dictionary = _rows[layer_id]
	var edit: LineEdit = row["edit"]
	var title: Label = row["title"]
	_renaming_id = layer_id
	edit.text = str(row["entry"].get("name", ""))
	title.visible = false
	edit.visible = true
	edit.grab_focus()
	edit.select_all()


func _build_row(layer_id: int) -> Dictionary:
	var panel := PanelContainer.new()
	panel.set_meta("layer_id", layer_id)
	panel.custom_minimum_size.y = ROW_HEIGHT
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var style := _flat_style(Color.BLACK)
	style.content_margin_left = 2.0
	style.content_margin_right = 2.0
	style.content_margin_top = 1.0
	style.content_margin_bottom = 1.0
	panel.add_theme_stylebox_override("panel", style)
	panel.gui_input.connect(_on_row_gui_input.bind(layer_id))
	panel.set_drag_forwarding(
		_row_drag_data.bind(layer_id, panel),
		_row_can_drop.bind(layer_id, panel),
		_row_drop.bind(layer_id, panel),
	)
	var box := HBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 2)
	panel.add_child(box)
	var indent := Control.new()
	indent.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(indent)
	var eye := Button.new()
	eye.focus_mode = Control.FOCUS_NONE
	eye.custom_minimum_size = EYE_SIZE
	eye.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	eye.pressed.connect(_on_eye_pressed.bind(layer_id))
	eye.draw.connect(_draw_eye.bind(eye))
	box.add_child(eye)
	var number := Label.new()
	number.custom_minimum_size.x = NUMBER_WIDTH
	number.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	box.add_child(number)
	var title := Label.new()
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.clip_text = true
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	box.add_child(title)
	var edit := LineEdit.new()
	edit.visible = false
	edit.max_length = NAME_MAX_LENGTH
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var edit_style := _flat_style(EDIT_FILL, DROP_BORDER)
	edit_style.set_border_width_all(1)
	edit_style.content_margin_left = 2.0
	edit_style.content_margin_right = 2.0
	edit_style.content_margin_top = 0.0
	edit_style.content_margin_bottom = 0.0
	edit.add_theme_stylebox_override("normal", edit_style)
	edit.add_theme_stylebox_override("focus", edit_style)
	edit.add_theme_stylebox_override("read_only", edit_style)
	edit.text_submitted.connect(_on_edit_submitted)
	edit.focus_exited.connect(_finish_rename.bind(true))
	edit.gui_input.connect(_on_edit_gui_input)
	box.add_child(edit)
	var lock := Label.new()
	lock.text = "🔒"
	lock.custom_minimum_size.x = LOCK_WIDTH
	lock.visible = false
	box.add_child(lock)
	return {
		"panel": panel,
		"style": style,
		"indent": indent,
		"eye": eye,
		"number": number,
		"title": title,
		"edit": edit,
		"lock": lock,
		"entry": {},
	}


func _apply_row(layer_id: int) -> void:
	var row: Dictionary = _rows[layer_id]
	var entry: Dictionary = row["entry"]
	var number_value := int(entry.get("number", 0))
	var hidden := not bool(entry.get("visible", true))
	var effectively_hidden := not bool(entry.get("effective_visible", true))
	var fill: Color = RULES.layer_color(str(entry.get("type", "")), number_value)
	if effectively_hidden:
		fill = fill.lerp(HIDDEN_FILL, 0.7)
	var text_color: Color = RULES.text_color(fill)
	var style: StyleBoxFlat = row["style"]
	style.bg_color = fill
	if layer_id == _drop_id:
		style.border_color = DROP_BORDER
		style.border_width_left = 0
		style.border_width_right = 0
		style.border_width_top = 3 if _drop_above else 0
		style.border_width_bottom = 0 if _drop_above else 3
	elif layer_id == _active_id:
		style.border_color = SELECTED_BORDER
		style.set_border_width_all(2)
	else:
		style.border_color = fill.darkened(0.45)
		style.set_border_width_all(1)
	var indent: Control = row["indent"]
	indent.custom_minimum_size.x = float(entry.get("depth", 0)) * INDENT_WIDTH
	var eye: Button = row["eye"]
	var eye_key := "hidden" if hidden else "shown"
	eye.add_theme_stylebox_override("normal", _eye_styles[eye_key])
	eye.add_theme_stylebox_override("hover", _eye_styles[eye_key + "_hover"])
	eye.add_theme_stylebox_override("pressed", _eye_styles[eye_key + "_hover"])
	eye.set_meta("hidden", hidden)
	eye.tooltip_text = "Показать слой" if hidden else "Скрыть слой"
	eye.queue_redraw()
	var number: Label = row["number"]
	number.text = str(number_value) if number_value > 0 else ""
	number.add_theme_color_override("font_color", text_color)
	var title: Label = row["title"]
	title.text = str(entry.get("name", ""))
	title.add_theme_color_override("font_color", text_color)
	var lock: Label = row["lock"]
	lock.visible = bool(entry.get("locked", false))
	var panel: Control = row["panel"]
	panel.tooltip_text = str(entry.get("tooltip", ""))


func _flat_style(background: Color, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_corner_radius_all(2)
	style.content_margin_left = 0.0
	style.content_margin_right = 0.0
	style.content_margin_top = 0.0
	style.content_margin_bottom = 0.0
	return style


func _remove_row(layer_id: int) -> void:
	if _renaming_id == layer_id:
		_renaming_id = 0
	if _drop_id == layer_id:
		_drop_id = 0
	var row: Dictionary = _rows[layer_id]
	_rows.erase(layer_id)
	var panel: Control = row["panel"]
	_rows_box.remove_child(panel)
	panel.queue_free()


func _ensure_row_visible(layer_id: int) -> void:
	if is_inside_tree() and _rows.has(layer_id):
		ensure_control_visible(_rows[layer_id]["panel"])


func _draw_eye(button: Button) -> void:
	var hidden := bool(button.get_meta("hidden", false))
	var center := button.size * 0.5
	var half_width := minf(button.size.x * 0.34, 6.0)
	var half_height := minf(button.size.y * 0.30, 3.5)
	var outline := PackedVector2Array()
	for step in range(13):
		var t := -1.0 + float(step) / 6.0
		outline.append(center + Vector2(t * half_width, -half_height * (1.0 - t * t)))
	for step in range(12, -1, -1):
		var t := -1.0 + float(step) / 6.0
		outline.append(center + Vector2(t * half_width, half_height * (1.0 - t * t)))
	button.draw_polyline(outline, ICON_COLOR, 1.0, true)
	if hidden:
		var reach := half_height * 1.6
		button.draw_line(
			center + Vector2(-half_width, reach), center + Vector2(half_width, -reach),
			ICON_COLOR, 1.4, true,
		)
	else:
		button.draw_circle(center, half_height * 0.55, ICON_COLOR)


func _on_row_gui_input(event: InputEvent, layer_id: int) -> void:
	if not event is InputEventMouseButton:
		return
	var click: InputEventMouseButton = event
	if click.button_index != MOUSE_BUTTON_LEFT or not click.pressed:
		return
	if _renaming_id != 0 and _renaming_id != layer_id:
		_finish_rename(true)
	layer_selected.emit(layer_id)
	if click.double_click:
		begin_rename(layer_id)


func _on_eye_pressed(layer_id: int) -> void:
	visibility_toggled.emit(layer_id)


func _on_edit_submitted(_text: String) -> void:
	_finish_rename(true)


func _on_edit_gui_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		_finish_rename(false)
		accept_event()


func _finish_rename(commit: bool) -> void:
	if _renaming_id == 0:
		return
	var layer_id := _renaming_id
	_renaming_id = 0
	if not _rows.has(layer_id):
		return
	var row: Dictionary = _rows[layer_id]
	var edit: LineEdit = row["edit"]
	var title: Label = row["title"]
	var new_name := edit.text.strip_edges()
	edit.visible = false
	title.visible = true
	if commit and not new_name.is_empty() and new_name != str(row["entry"].get("name", "")):
		layer_renamed.emit(layer_id, new_name)


func _dragged_layer_id(data: Variant) -> int:
	if data is Dictionary and str(data.get("type", "")) == DRAG_TYPE:
		return int(data.get("layer_id", 0))
	return 0


func _row_drag_data(_at_position: Vector2, layer_id: int, panel: Control) -> Variant:
	if not _rows.has(layer_id):
		return null
	var entry: Dictionary = _rows[layer_id]["entry"]
	var number_value := int(entry.get("number", 0))
	var fill: Color = RULES.layer_color(str(entry.get("type", "")), number_value)
	var preview := PanelContainer.new()
	var preview_style := _flat_style(fill, SELECTED_BORDER)
	preview_style.set_border_width_all(1)
	preview_style.content_margin_left = 4.0
	preview_style.content_margin_right = 4.0
	preview_style.content_margin_top = 1.0
	preview_style.content_margin_bottom = 1.0
	preview.add_theme_stylebox_override("panel", preview_style)
	var caption := Label.new()
	caption.text = ("%d · %s" % [number_value, str(entry.get("name", ""))]) if number_value > 0 \
		else str(entry.get("name", ""))
	caption.add_theme_font_size_override("font_size", 10)
	caption.add_theme_color_override("font_color", RULES.text_color(fill))
	preview.add_child(caption)
	panel.set_drag_preview(preview)
	return {"type": DRAG_TYPE, "layer_id": layer_id}


func _row_can_drop(at_position: Vector2, data: Variant, layer_id: int, panel: Control) -> bool:
	var source_id := _dragged_layer_id(data)
	if source_id == 0 or source_id == layer_id or not _rows.has(source_id) or not _rows.has(layer_id):
		_clear_drop_target()
		return false
	var source_entry: Dictionary = _rows[source_id]["entry"]
	var target_entry: Dictionary = _rows[layer_id]["entry"]
	if int(source_entry.get("parent_id", 0)) != int(target_entry.get("parent_id", 0)):
		_clear_drop_target()
		return false
	_set_drop_target(layer_id, at_position.y < panel.size.y * 0.5)
	return true


func _row_drop(at_position: Vector2, data: Variant, layer_id: int, panel: Control) -> void:
	var source_id := _dragged_layer_id(data)
	var above := at_position.y < panel.size.y * 0.5
	_clear_drop_target()
	if source_id == 0 or source_id == layer_id:
		return
	layer_dropped.emit(source_id, layer_id, above)


func _set_drop_target(layer_id: int, above: bool) -> void:
	if _drop_id == layer_id and _drop_above == above:
		return
	var previous := _drop_id
	_drop_id = layer_id
	_drop_above = above
	if previous != 0 and previous != layer_id and _rows.has(previous):
		_apply_row(previous)
	_apply_row(layer_id)


func _clear_drop_target() -> void:
	var previous := _drop_id
	_drop_id = 0
	if previous != 0 and _rows.has(previous):
		_apply_row(previous)
