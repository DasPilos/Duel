extends Control

# Окно «Новый предмет» редактора карт. Как в Python: сам диалог форму не проверяет, OK отдаёт копию формы
# редактору (save_requested), а ошибку редактор возвращает через set_message. Сети здесь нет.

signal save_requested(form: Dictionary)
signal cancel_requested

const Rules := preload("res://scripts/map_editor_item_form_rules.gd")
const Style := preload("res://scripts/mob_profile_style.gd")

const PANEL_SIZE := Vector2(1140, 720)
const COLUMN_WIDTH := 340.0
const COLUMN_GAP := 16
const ROW_GAP := 6
const LABEL_WIDTH := 170.0
const LABEL_FONT_SIZE := 12
const CONTROL_HEIGHT := 28
const STEP_SIZE := Vector2(28, 28)
const TEXT_INPUT_WIDTH := 160.0
const INT_INPUT_WIDTH := 72.0
const SLOT_VALUE_WIDTH := 120.0
const ICON_BUTTON_WIDTH := 160.0
const ICON_CELL := Vector2(84, 84)
const ICON_THUMB := 52
const ICON_COLUMNS := 6
const ICON_VISIBLE_ROWS := 5
const GRID_GAP := 4
const ICON_FOLDER_RELATIVE := "../assets/item_icons"
const EMPTY_ICON_TEXT := "нет"
const TITLE_TEXT := "Новый предмет"
const HINT_TEXT := "Экипировка сохранится в каталог режима. Вампиризм и аура действуют в бою Front Line; часть остальных параметров пока сохраняется для последующей настройки"
const SAVE_TEXT := "Сохранить в базу"
const CANCEL_TEXT := "Отмена"
const NO_ICONS_TEXT := "В базе иконок пока нет файлов для этого слота. Положите PNG в assets/item_icons"

var form: Dictionary = {}

var _icon_folder := ""
var _icon_keys: Array = []
var _editing_item_id := 0
var _title_label: Label
var _name_input: LineEdit
var _int_inputs: Dictionary = {}
var _int_steps: Dictionary = {}
var _flag_inputs: Dictionary = {}
var _choice_inputs: Dictionary = {}
var _slot_prev: Button
var _slot_next: Button
var _slot_label: Label
var _icon_button: Button
var _picker: ColorRect
var _picker_title: Label
var _picker_back_button: Button
var _picker_warning: Label
var _picker_scroll: ScrollContainer
var _picker_grid: GridContainer
var _picker_options: Array = []
var _icon_options_by_category: Dictionary = {}
var _picker_stage := "categories"
var _thumbs: Dictionary = {}
var _message_label: Label


func _init() -> void:
	theme = Style.make_theme()


static func default_icon_folder() -> String:
	return ProjectSettings.globalize_path("res://").path_join(ICON_FOLDER_RELATIVE).simplify_path()


static func scan_icon_keys(folder: String) -> Array:
	if folder.is_empty() or not DirAccess.dir_exists_absolute(folder):
		return []
	return Rules.icon_keys_from_files(DirAccess.get_files_at(folder))


# icon_folder нужен только для миниатюр в выборе иконки; icon_keys — допустимые ключи (как файлы в папке).
func setup(icon_folder: String, icon_keys: Array, initial_form: Dictionary = {}, item_id := 0) -> void:
	_icon_folder = icon_folder
	_icon_keys = icon_keys.duplicate()
	_icon_keys.sort()
	_thumbs.clear()
	form = Rules.default_form()
	for key in initial_form:
		form[key] = initial_form[key]
	_editing_item_id = item_id
	var current_icon: Variant = form.get("icon")
	if current_icon is String and Rules.is_valid_icon_key(current_icon) and not _icon_keys.has(current_icon):
		_icon_keys.append(current_icon)
		_icon_keys.sort()
	if _name_input == null:
		_build_ui()
	_title_label.text = "Настройки предмета" if _editing_item_id >= Rules.CUSTOM_ITEM_FIRST_ID else TITLE_TEXT
	_refresh_all()


func icon_keys() -> Array:
	return _icon_keys.duplicate()


func message_text() -> String:
	return _message_label.text


func set_message(text: String, color: Color = Style.WARN_COLOR) -> void:
	_message_label.text = text
	_message_label.add_theme_color_override("font_color", color)


func request_save() -> void:
	_commit_all_inputs()
	save_requested.emit(form.duplicate(true))


func request_cancel() -> void:
	cancel_requested.emit()


func _input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo or key_event.keycode != KEY_ESCAPE:
		return
	if _picker == null or not is_visible_in_tree():
		return
	get_viewport().set_input_as_handled()
	if _picker.visible:
		_close_icon_picker()
	else:
		request_cancel()


func _build_ui() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var shade := ColorRect.new()
	shade.color = Style.SHADE_COLOR
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = PANEL_SIZE
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	center.add_child(panel)
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_top", 16)
	margin.add_theme_constant_override("margin_bottom", 14)
	panel.add_child(margin)
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 10)
	margin.add_child(outer)
	_title_label = Style.make_label(TITLE_TEXT, Style.TEXT_COLOR, Style.TITLE_FONT_SIZE)
	outer.add_child(_title_label)
	outer.add_child(_wrapped_label(HINT_TEXT, Style.DIM_COLOR, Style.SMALL_FONT_SIZE))
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", COLUMN_GAP)
	outer.add_child(columns)
	for column_specs in Rules.field_columns():
		var column := VBoxContainer.new()
		column.custom_minimum_size.x = COLUMN_WIDTH
		column.add_theme_constant_override("separation", ROW_GAP)
		columns.add_child(column)
		for spec in column_specs:
			_add_row(column, spec)
	_build_footer(outer)
	_build_picker()


func _add_row(column: VBoxContainer, spec: Dictionary) -> void:
	var key := str(spec["key"])
	if key == "header":
		column.add_child(Style.make_label(str(spec["label"]), Style.ACTIVE_COLOR, Style.HEADER_FONT_SIZE))
		return
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", ROW_GAP)
	column.add_child(row)
	var label := Style.make_label(str(spec["label"]), Style.TEXT_COLOR, LABEL_FONT_SIZE)
	label.custom_minimum_size.x = LABEL_WIDTH
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(label)
	match str(spec["kind"]):
		"text":
			_add_name_input(row)
		"slot":
			_add_slot_control(row)
		"icon":
			_add_icon_control(row)
		"flag":
			_add_flag_control(row, key)
		"choice":
			_add_choice_control(row, key)
		"int":
			_add_int_control(row, spec)


func _add_name_input(row: HBoxContainer) -> void:
	_name_input = LineEdit.new()
	_name_input.custom_minimum_size = Vector2(TEXT_INPUT_WIDTH, CONTROL_HEIGHT)
	_name_input.max_length = Rules.MAX_NAME
	_name_input.select_all_on_focus = true
	_name_input.text_changed.connect(_on_name_changed)
	_name_input.text_submitted.connect(_release_after_submit.bind(_name_input))
	row.add_child(_name_input)


func _add_slot_control(row: HBoxContainer) -> void:
	_slot_prev = Style.make_button("<", STEP_SIZE)
	_slot_prev.pressed.connect(_on_slot_step.bind(-1))
	var value := PanelContainer.new()
	value.custom_minimum_size = Vector2(SLOT_VALUE_WIDTH, CONTROL_HEIGHT)
	value.add_theme_stylebox_override("panel", Style.flat(Style.MENU_COLOR, Style.MENU_COLOR, 0, 4))
	_slot_label = Style.make_label("", Style.TEXT_COLOR)
	_slot_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_slot_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_slot_label.clip_text = true
	_slot_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_slot_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	value.add_child(_slot_label)
	_slot_next = Style.make_button(">", STEP_SIZE)
	_slot_next.pressed.connect(_on_slot_step.bind(1))
	row.add_child(_slot_prev)
	row.add_child(value)
	row.add_child(_slot_next)


func _add_icon_control(row: HBoxContainer) -> void:
	_icon_button = Style.make_button("", Vector2(ICON_BUTTON_WIDTH, CONTROL_HEIGHT))
	_icon_button.clip_text = true
	_icon_button.pressed.connect(_open_icon_picker)
	_icon_button.gui_input.connect(_on_icon_button_gui_input)
	row.add_child(_icon_button)


func _add_flag_control(row: HBoxContainer, key: String) -> void:
	var box := CheckBox.new()
	box.focus_mode = Control.FOCUS_NONE
	box.toggled.connect(_on_flag_toggled.bind(key))
	row.add_child(box)
	_flag_inputs[key] = box


func _add_choice_control(row: HBoxContainer, key: String) -> void:
	var select := OptionButton.new()
	select.custom_minimum_size = Vector2(ICON_BUTTON_WIDTH, CONTROL_HEIGHT)
	select.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	var choices: Dictionary = Rules.AURA_TYPE_OPTIONS if key == "aura_type" else Rules.AURA_TARGET_OPTIONS
	for value in choices:
		select.add_item(str(choices[value]))
		select.set_item_metadata(select.item_count - 1, value)
	select.item_selected.connect(_on_choice_selected.bind(key))
	row.add_child(select)
	_choice_inputs[key] = select


func _add_int_control(row: HBoxContainer, spec: Dictionary) -> void:
	var key := str(spec["key"])
	var minus := Style.make_button("−", STEP_SIZE)
	var input := LineEdit.new()
	input.custom_minimum_size = Vector2(INT_INPUT_WIDTH, CONTROL_HEIGHT)
	input.alignment = HORIZONTAL_ALIGNMENT_CENTER
	input.select_all_on_focus = true
	var plus := Style.make_button("+", STEP_SIZE)
	minus.pressed.connect(_on_step.bind(spec, -1))
	plus.pressed.connect(_on_step.bind(spec, 1))
	input.text_submitted.connect(_on_int_submitted.bind(key))
	input.focus_exited.connect(_commit_int.bind(key))
	row.add_child(minus)
	row.add_child(input)
	row.add_child(plus)
	_int_inputs[key] = input
	_int_steps[key] = [minus, plus]


func _build_footer(outer: VBoxContainer) -> void:
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 14)
	outer.add_child(footer)
	var save := Style.make_button(SAVE_TEXT, Vector2(240, 40))
	var save_border := Style.SAVE_COLOR.lightened(0.25)
	save.add_theme_stylebox_override("normal", Style.flat(Style.SAVE_COLOR, save_border))
	save.add_theme_stylebox_override("hover", Style.flat(Style.SAVE_HOVER_COLOR, save_border))
	save.add_theme_stylebox_override("pressed", Style.flat(Style.SAVE_COLOR.darkened(0.15), save_border))
	save.pressed.connect(request_save)
	footer.add_child(save)
	var cancel := Style.make_button(CANCEL_TEXT, Vector2(140, 40))
	cancel.pressed.connect(request_cancel)
	footer.add_child(cancel)
	_message_label = Style.make_label("", Style.WARN_COLOR, Style.SMALL_FONT_SIZE)
	_message_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_message_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	footer.add_child(_message_label)


func _build_picker() -> void:
	_picker = ColorRect.new()
	_picker.color = Color(0.0, 0.0, 0.0, 0.0)
	_picker.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_picker.mouse_filter = Control.MOUSE_FILTER_STOP
	_picker.visible = false
	_picker.gui_input.connect(_on_picker_backdrop_input)
	add_child(_picker)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_picker.add_child(center)
	var window := PanelContainer.new()
	window.mouse_filter = Control.MOUSE_FILTER_STOP
	window.add_theme_stylebox_override("panel", Style.flat(Style.MENU_COLOR, Style.ACTIVE_COLOR, 2, 6))
	center.add_child(window)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	window.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	margin.add_child(column)
	var heading := HBoxContainer.new()
	heading.add_theme_constant_override("separation", 8)
	column.add_child(heading)
	_picker_title = Style.make_label("", Style.ACTIVE_COLOR, Style.HEADER_FONT_SIZE)
	_picker_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.add_child(_picker_title)
	_picker_back_button = Style.make_button("← Назад", Vector2(100, CONTROL_HEIGHT))
	_picker_back_button.pressed.connect(_show_icon_categories)
	_picker_back_button.visible = false
	heading.add_child(_picker_back_button)
	_picker_warning = Style.make_label(NO_ICONS_TEXT, Style.WARN_COLOR, Style.SMALL_FONT_SIZE)
	column.add_child(_picker_warning)
	_picker_scroll = ScrollContainer.new()
	_picker_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_picker_scroll.custom_minimum_size = Vector2(0, ICON_VISIBLE_ROWS * (ICON_CELL.y + GRID_GAP))
	column.add_child(_picker_scroll)
	_picker_grid = GridContainer.new()
	_picker_grid.columns = ICON_COLUMNS
	_picker_grid.add_theme_constant_override("h_separation", GRID_GAP)
	_picker_grid.add_theme_constant_override("v_separation", GRID_GAP)
	_picker_scroll.add_child(_picker_grid)


func _open_icon_picker() -> void:
	var slot := str(form["slot"])
	_picker_options = Rules.icon_options_for_slot(slot, _icon_keys)
	_icon_options_by_category.clear()
	for option in _picker_options:
		if option == null:
			continue
		var category := Rules.item_subcategory({"icon": str(option)})
		var options: Array = _icon_options_by_category.get(category, [])
		options.append(option)
		_icon_options_by_category[category] = options
	_picker_warning.visible = _picker_options.size() == 1
	_show_icon_categories()
	_picker.visible = true


func _show_icon_categories() -> void:
	_picker_stage = "categories"
	_picker_title.text = "Выберите направление: %s" % Rules.slot_label(str(form["slot"]))
	_picker_back_button.visible = false
	for child in _picker_grid.get_children():
		_picker_grid.remove_child(child)
		child.queue_free()
	for category in Rules.ITEM_SUBCATEGORIES:
		var options: Array = _icon_options_by_category.get(category, [])
		if options.is_empty():
			continue
		var button := Style.make_button("%s · %d" % [str(category), options.size()], Vector2(ICON_CELL.x * 2 + GRID_GAP, ICON_CELL.y))
		button.pressed.connect(_show_category_icons.bind(str(category)))
		_picker_grid.add_child(button)
	if _picker_options.has(null):
		var empty_button := Style.make_button("Без иконки", Vector2(ICON_CELL.x * 2 + GRID_GAP, ICON_CELL.y))
		empty_button.pressed.connect(_on_icon_picked.bind(null))
		_picker_grid.add_child(empty_button)
	_picker_scroll.scroll_vertical = 0


func _show_category_icons(category: String) -> void:
	_picker_stage = "icons"
	_picker_title.text = "Иконки: %s" % category
	_picker_back_button.visible = true
	for child in _picker_grid.get_children():
		_picker_grid.remove_child(child)
		child.queue_free()
	for option in _icon_options_by_category.get(category, []):
		_picker_grid.add_child(_make_icon_cell(option))
	_picker_scroll.scroll_vertical = 0


func _close_icon_picker() -> void:
	_picker.visible = false
	_picker_options = []
	_icon_options_by_category.clear()


func _make_icon_cell(key: Variant) -> Button:
	var cell := Style.make_button("", ICON_CELL)
	if key == form["icon"]:
		cell.add_theme_stylebox_override("normal", Style.flat(Style.BUTTON_ON_COLOR, Style.ACTIVE_COLOR, 2))
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 2)
	cell.add_child(box)
	if key == null:
		box.add_child(_cell_label(EMPTY_ICON_TEXT, Style.TEXT_COLOR))
	else:
		var thumb := _thumb(str(key))
		if thumb != null:
			var rect := TextureRect.new()
			rect.texture = thumb
			rect.custom_minimum_size = Vector2(ICON_THUMB, ICON_THUMB)
			rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			rect.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
			rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
			box.add_child(rect)
		box.add_child(_cell_label(str(key), Style.DIM_COLOR))
	cell.pressed.connect(_on_icon_picked.bind(key))
	return cell


func _on_icon_button_gui_input(event: InputEvent) -> void:
	var button := event as InputEventMouseButton
	if button != null and button.pressed and button.button_index == MOUSE_BUTTON_RIGHT:
		_open_icon_picker()


func _cell_label(text: String, color: Color) -> Label:
	var label := Style.make_label(text, color, Style.SMALL_FONT_SIZE)
	label.custom_minimum_size.x = ICON_CELL.x - 8
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _thumb(key: String) -> Texture2D:
	if not _thumbs.has(key):
		_thumbs[key] = _load_thumb(_icon_folder.path_join(key + ".png"))
	return _thumbs[key]


func _load_thumb(path: String) -> Texture2D:
	if _icon_folder.is_empty() or not FileAccess.file_exists(path):
		return null
	var image := Image.load_from_file(path)
	if image == null or image.is_empty():
		return null
	image.convert(Image.FORMAT_RGBA8)
	image.resize(ICON_THUMB, ICON_THUMB, Image.INTERPOLATE_LANCZOS)
	return ImageTexture.create_from_image(image)


func _on_icon_picked(key: Variant) -> void:
	form["icon"] = key
	_refresh_icon()
	_close_icon_picker()


func _on_picker_backdrop_input(event: InputEvent) -> void:
	var button := event as InputEventMouseButton
	if button != null and button.pressed and button.button_index == MOUSE_BUTTON_LEFT:
		_close_icon_picker()


func _on_name_changed(text: String) -> void:
	form["name"] = text


func _on_flag_toggled(pressed: bool, key: String) -> void:
	Rules.set_value(form, key, pressed)


func _on_choice_selected(index: int, key: String) -> void:
	var select := _choice_inputs[key] as OptionButton
	Rules.set_value(form, key, select.get_item_metadata(index))


func _on_slot_step(direction: int) -> void:
	form["slot"] = Rules.step_slot(str(form["slot"]), direction)
	_refresh_slot()


func _on_step(spec: Dictionary, direction: int) -> void:
	_commit_all_inputs()
	var key := str(spec["key"])
	Rules.set_value(form, key, Rules.step_value(form, spec, direction))
	_refresh_int(key)


func _on_int_submitted(_text: String, key: String) -> void:
	_commit_int(key)
	(_int_inputs[key] as LineEdit).release_focus()


# Число, которое не читается как целое, остаётся в форме текстом: тогда проверка при OK назовёт поле.
func _commit_int(key: String) -> void:
	var input := _int_inputs[key] as LineEdit
	var parsed: Variant = Rules.parse_int(input.text)
	Rules.set_value(form, key, input.text if parsed == null else parsed)
	_refresh_int(key)


func _commit_all_inputs() -> void:
	for key in _int_inputs:
		_commit_int(str(key))


func _release_after_submit(_text: String, input: LineEdit) -> void:
	input.release_focus()


func _refresh_all() -> void:
	_name_input.text = str(form["name"])
	for key in _int_inputs:
		_refresh_int(str(key))
	for key in _flag_inputs:
		(_flag_inputs[key] as CheckBox).set_pressed_no_signal(bool(form[key]))
	for key in _choice_inputs:
		var select := _choice_inputs[key] as OptionButton
		for index in range(select.item_count):
			if select.get_item_metadata(index) == form[key]:
				select.select(index)
				break
	_refresh_slot()
	_refresh_icon()


func _refresh_int(key: String) -> void:
	var value: Variant = Rules.get_value(form, key)
	(_int_inputs[key] as LineEdit).text = "" if value == null else str(value)


func _refresh_slot() -> void:
	_slot_label.text = Rules.slot_label(str(form["slot"]))


func _refresh_icon() -> void:
	var icon: Variant = form["icon"]
	_icon_button.text = EMPTY_ICON_TEXT if icon == null or str(icon).is_empty() else str(icon)


func _wrapped_label(text: String, color: Color, font_size: int) -> Label:
	var label := Style.make_label(text, color, font_size)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label
