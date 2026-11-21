extends Control

# Окно «Древо талантов» из deck/ui/talent_tree_window.py: ряд на каждый уровень, два варианта выбора, на 3-м уровне пассивное улучшение.
# Выбор уходит миру сигналом choose_requested; ответ сервера приходит через set_character и show_message.

signal choose_requested(level: int, choice_id: String, option_name: String)

const RULES := preload("res://scripts/deck_talent_rules.gd")
const WINDOW_WIDTH := 900.0
const WINDOW_HEIGHT := 600.0
const LEVEL_WIDTH := 64.0
const OPTION_HEIGHT := 56.0
const SCROLL_STEP := 60
const WINDOW_BACKGROUND := Color8(24, 35, 29, 250)
const WINDOW_BORDER := Color8(125, 185, 110)
const TITLE_COLOR := Color8(205, 235, 170)
const TEXT_COLOR := Color8(220, 225, 210)
const PASSIVE_COLOR := Color8(174, 218, 147)
const MESSAGE_COLOR := Color8(238, 220, 155)
const ERROR_COLOR := Color8(240, 150, 140)
const ROW_UNLOCKED := Color8(43, 61, 46)
const ROW_LOCKED := Color8(35, 42, 37)
const ROW_BORDER := Color8(91, 126, 85)
const OPTION_CHOSEN := Color8(73, 112, 67)
const OPTION_AVAILABLE := Color8(54, 72, 56)
const OPTION_AVAILABLE_HOVER := Color8(83, 132, 76)
const OPTION_LOCKED := Color8(43, 47, 43)
const OPTION_TEXT := Color8(235, 240, 225)
const OPTION_TEXT_LOCKED := Color8(130, 137, 128)

var _character: Dictionary = {}
var _window: PanelContainer
var _subtitle: Label
var _scroll: ScrollContainer
var _rows: VBoxContainer
var _message: Label


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var backdrop := ColorRect.new()
	backdrop.color = Color(0, 0, 0, 0.6)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.gui_input.connect(_on_backdrop_input)
	add_child(backdrop)
	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	_window = PanelContainer.new()
	_window.custom_minimum_size = Vector2(WINDOW_WIDTH, WINDOW_HEIGHT)
	_window.add_theme_stylebox_override("panel", _style(WINDOW_BACKGROUND, WINDOW_BORDER, 2, 8, 14))
	center.add_child(_window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	_window.add_child(layout)
	layout.add_child(_build_header())
	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	layout.add_child(_scroll)
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows.add_theme_constant_override("separation", 6)
	_scroll.add_child(_rows)
	_message = _make_label("", 13, MESSAGE_COLOR)
	layout.add_child(_message)


func open(character: Dictionary) -> void:
	visible = true
	_message.text = ""
	set_character(character)
	if int(character.get("id", 0)) <= 0:
		show_message("Персонаж не загружен", true)


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


func set_character(character: Dictionary) -> void:
	_character = character
	_rebuild()


func show_message(text: String, is_error := false) -> void:
	_message.text = text
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else MESSAGE_COLOR)


func _rebuild() -> void:
	var character_level := int(_character.get("level", 1))
	_subtitle.text = "%s — уровень %d" % [RULES.type_label(_character.get("type", "")), character_level]
	for child in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()
	for entry in RULES.tree_for(_character.get("type", RULES.DEFAULT_TYPE)):
		_rows.add_child(_build_row(entry, character_level))


func _build_row(entry: Dictionary, character_level: int) -> Control:
	var talent_level := int(entry["level"])
	var unlocked := RULES.is_unlocked(character_level, talent_level)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _style(ROW_UNLOCKED if unlocked else ROW_LOCKED, ROW_BORDER, 1, 6, 8))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	panel.add_child(row)
	var level_label := _make_label("Ур. %d" % talent_level, 15, TEXT_COLOR)
	level_label.custom_minimum_size.x = LEVEL_WIDTH
	row.add_child(level_label)
	if entry.get("passive", false):
		row.add_child(_passive_block(entry))
		return panel
	var chosen := RULES.chosen_id(_character.get("talents", {}), talent_level)
	for option in entry["options"]:
		row.add_child(_option_button(entry, option, unlocked, chosen))
	return panel


func _passive_block(entry: Dictionary) -> Control:
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 2)
	box.add_child(_make_label("ПАССИВНОЕ УЛУЧШЕНИЕ", 11, PASSIVE_COLOR))
	var description := _make_label(str(entry["description"]), 12, TEXT_COLOR)
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	description.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(description)
	return box


# Выбранный вариант показывает название, остальные — описание, как в Python.
func _option_button(entry: Dictionary, option: Dictionary, unlocked: bool, chosen_id: String) -> Button:
	var is_chosen := chosen_id == str(option["id"])
	var available := unlocked and chosen_id.is_empty()
	var background := OPTION_CHOSEN if is_chosen else (OPTION_AVAILABLE if available else OPTION_LOCKED)
	var hover := OPTION_AVAILABLE_HOVER if available else background
	var button := Button.new()
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0, OPTION_HEIGHT)
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_stylebox_override("normal", _style(background, ROW_BORDER, 1, 6, 6))
	button.add_theme_stylebox_override("hover", _style(hover, ROW_BORDER, 1, 6, 6))
	button.add_theme_stylebox_override("pressed", _style(hover, ROW_BORDER, 1, 6, 6))
	var text := str(option["name"]) if is_chosen else str(option["description"])
	var label := _make_label(text, 13 if is_chosen else 12, OPTION_TEXT if unlocked else OPTION_TEXT_LOCKED)
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	button.add_child(label)
	button.pressed.connect(_on_option_pressed.bind(entry, option))
	return button


func _on_option_pressed(entry: Dictionary, option: Dictionary) -> void:
	if int(_character.get("id", 0)) <= 0:
		show_message("Персонаж не загружен", true)
		return
	var error := RULES.choose_error(_character, entry)
	if not error.is_empty():
		show_message(error, true)
		return
	choose_requested.emit(int(entry["level"]), str(option["id"]), str(option["name"]))


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		close()


# _input: стрелки обрабатываются раньше навигации фокуса GUI и ходьбы мира.
func _input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.keycode == KEY_UP or event.keycode == KEY_DOWN:
		_scroll.scroll_vertical += SCROLL_STEP if event.keycode == KEY_DOWN else -SCROLL_STEP
		get_viewport().set_input_as_handled()


func _build_header() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	var top := HBoxContainer.new()
	var title := _make_label("Древо талантов", 18, TITLE_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(title)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.focus_mode = Control.FOCUS_NONE
	close_button.custom_minimum_size = Vector2(32, 28)
	close_button.pressed.connect(close)
	top.add_child(close_button)
	box.add_child(top)
	_subtitle = _make_label("", 13, TEXT_COLOR)
	box.add_child(_subtitle)
	return box


func _make_label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _style(background: Color, border: Color, border_width: int, radius: int, margin: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(margin)
	return style
