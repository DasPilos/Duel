extends Control

# Окно «Библиотека мира» из deck/ui/library_window.py: поиск, категории, список записей и описание выбранной.
# Каталог предметов приходит из мира (set_items) после открытия; остальные категории готовы сразу.

const RULES := preload("res://scripts/deck_library_rules.gd")
const WINDOW_WIDTH := 880.0
const WINDOW_HEIGHT := 540.0
const LIST_WIDTH := 290.0
const DESCRIPTION_WIDTH := 440.0
const WINDOW_BACKGROUND := Color8(29, 31, 38, 250)
const WINDOW_BORDER := Color8(145, 145, 175)
const TITLE_COLOR := Color8(225, 225, 245)
const TEXT_COLOR := Color8(205, 208, 220)
const ITEMS_LOADING := "Загружаем каталог предметов…"

var _catalogue: Dictionary = {}
var _items_message := ""
var _category_index := 0
var _entries: Array = []
var _window: PanelContainer
var _search: LineEdit
var _category_group := ButtonGroup.new()
var _list: ItemList
var _scroll: ScrollContainer
var _title: Label
var _description: Label


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	for category in RULES.CATEGORIES:
		_catalogue[category] = RULES.static_entries(category)
	_catalogue["Предметы"] = []
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
	_window.add_theme_stylebox_override("panel", _box_style())
	center.add_child(_window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	_window.add_child(layout)
	layout.add_child(_build_header())
	_search = LineEdit.new()
	_search.placeholder_text = "введите название или эффект…"
	_search.custom_minimum_size.y = 30
	_search.text_changed.connect(_on_search_changed)
	layout.add_child(_search)
	layout.add_child(_build_categories())
	layout.add_child(_build_body())


func open() -> void:
	if _catalogue["Предметы"].is_empty():
		_items_message = ITEMS_LOADING
	visible = true
	_refresh()


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


func set_items(items: Array) -> void:
	_catalogue["Предметы"] = RULES.item_entries(items)
	_items_message = ""
	_refresh()


func show_items_message(text: String) -> void:
	_items_message = text
	_refresh()


func _refresh() -> void:
	var category: String = RULES.CATEGORIES[_category_index]
	_entries = RULES.filter_entries(_catalogue.get(category, []), _search.text)
	_list.clear()
	for entry in _entries:
		_list.add_item(str(entry["name"]))
	if _entries.is_empty():
		_title.text = "Нет записей"
		var message := "По запросу ничего не найдено."
		if category == "Предметы" and not _items_message.is_empty():
			message = _items_message
		_description.text = message
		_scroll.scroll_vertical = 0
		return
	_list.select(0)
	_show_entry(0)


func _show_entry(index: int) -> void:
	var entry: Dictionary = _entries[index]
	_title.text = str(entry["name"])
	_description.text = str(entry["description"])
	_scroll.scroll_vertical = 0


func _on_category_toggled(on: bool, index: int) -> void:
	if not on:
		return
	_category_index = index
	_refresh()


func _on_search_changed(_text: String) -> void:
	_refresh()


func _on_entry_selected(index: int) -> void:
	_show_entry(index)


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		close()


func _build_header() -> Control:
	var header := HBoxContainer.new()
	var title := _make_label(18, TITLE_COLOR)
	title.text = "Библиотека мира"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(32, 28)
	close_button.pressed.connect(close)
	header.add_child(close_button)
	return header


func _build_categories() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	for index in range(RULES.CATEGORIES.size()):
		var button := Button.new()
		button.text = RULES.CATEGORIES[index]
		button.toggle_mode = true
		button.button_group = _category_group
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size.y = 30
		button.button_pressed = index == _category_index
		button.toggled.connect(_on_category_toggled.bind(index))
		row.add_child(button)
	return row


func _build_body() -> Control:
	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 16)
	_list = ItemList.new()
	_list.custom_minimum_size.x = LIST_WIDTH
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.add_theme_font_size_override("font_size", 14)
	_list.item_selected.connect(_on_entry_selected)
	body.add_child(_list)
	_scroll = ScrollContainer.new()
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(_scroll)
	var details := VBoxContainer.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details.add_theme_constant_override("separation", 8)
	_scroll.add_child(details)
	_title = _make_label(17, TITLE_COLOR)
	details.add_child(_title)
	_description = _make_label(14, TEXT_COLOR)
	_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_description.custom_minimum_size.x = DESCRIPTION_WIDTH
	details.add_child(_description)
	return body


func _make_label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _box_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = WINDOW_BACKGROUND
	style.border_color = WINDOW_BORDER
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(14)
	return style
