extends Control

# Лавка хозяина трактира из deck/ui/tavern_shop.py: вкладки «НАПИТКИ» и «СКУПКА», список напитков с сервера.
# Покупка отключена, как в Python: двойной клик по напитку показывает PURCHASE_DISABLED. «СКУПКА» — заглушка, как в Python.

const TAB_DRINKS := "НАПИТКИ"
const TAB_SELL := "СКУПКА"
const TITLE_DRINKS := "Напитки бара"
const TITLE_SELL := "Скупка"
const SELL_HINT := "Кликните на предмет в рюкзаке"
const PRICE_PLACEHOLDER := "временно недоступно"
const PURCHASE_DISABLED := "Покупки временно отключены до назначения цен в монетах"
const CLOSE_TEXT := "ЗАКРЫТЬ"
const WINDOW_TITLE := "Хозяин трактира"
const DRINKS_LOADING := "Загружаем напитки…"
const DRINKS_EMPTY := "В баре пока нет напитков."
const UNKNOWN_DRINK := "Неизвестный напиток"
# Два клика по одному напитку быстрее этого порога считаются двойным, как в Python.
const DOUBLE_CLICK_MSEC := 300
const WINDOW_WIDTH := 560.0
const WINDOW_HEIGHT := 420.0
const WINDOW_BACKGROUND := Color8(40, 50, 70, 250)
const WINDOW_BORDER := Color8(150, 150, 170)
const HEADER_COLOR := Color8(100, 200, 255)
const SELL_TITLE_COLOR := Color8(255, 150, 100)
const TEXT_COLOR := Color8(200, 200, 200)
const ERROR_COLOR := Color8(255, 100, 100)

var _drinks: Array[Dictionary] = []
var _loaded := false
var _last_click_index := -1
var _last_click_msec := 0
var _window: PanelContainer
var _tabs := ButtonGroup.new()
var _drinks_tab: Button
var _sell_tab: Button
var _drinks_box: VBoxContainer
var _sell_box: VBoxContainer
var _list: ItemList
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
	_window.add_theme_stylebox_override("panel", _box_style())
	center.add_child(_window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	_window.add_child(layout)
	layout.add_child(_build_header())
	layout.add_child(_build_tabs())
	layout.add_child(_build_body())
	_message = _make_label("", 13, TEXT_COLOR)
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.custom_minimum_size.x = WINDOW_WIDTH - 40.0
	layout.add_child(_message)
	layout.add_child(_build_footer())


func open() -> void:
	visible = true
	show_message(DRINKS_LOADING if not _loaded else "", false)


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


# Цена пока не показывается: в Python вместо неё стоит «временно недоступно».
func set_drinks(drinks: Array) -> void:
	_loaded = true
	_drinks.clear()
	for drink in drinks:
		if drink is Dictionary:
			_drinks.append({
				"name": str(drink.get("name", UNKNOWN_DRINK)),
				"description": str(drink.get("description", "")),
			})
	_last_click_index = -1
	_list.clear()
	for drink in _drinks:
		var index := _list.add_item("%s — %s" % [drink["name"], PRICE_PLACEHOLDER])
		_list.set_item_tooltip(index, str(drink["description"]))
	show_message(DRINKS_EMPTY if _drinks.is_empty() else "", false)


func show_message(text: String, is_error := false) -> void:
	_message.text = text
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else TEXT_COLOR)


func _on_drink_clicked(index: int, _at_position: Vector2, mouse_button_index: int) -> void:
	if mouse_button_index != MOUSE_BUTTON_LEFT:
		return
	var now := Time.get_ticks_msec()
	if index == _last_click_index and now - _last_click_msec < DOUBLE_CLICK_MSEC:
		_last_click_index = -1
		_last_click_msec = 0
		show_message(PURCHASE_DISABLED, true)
		return
	_last_click_index = index
	_last_click_msec = now


func _on_tab_toggled(pressed: bool, is_sell: bool) -> void:
	if not pressed:
		return
	_drinks_box.visible = not is_sell
	_sell_box.visible = is_sell


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		close()


func _build_header() -> Control:
	var row := HBoxContainer.new()
	var title := _make_label(WINDOW_TITLE, 18, HEADER_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(32, 28)
	close_button.pressed.connect(close)
	row.add_child(close_button)
	return row


func _build_tabs() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	_drinks_tab = _make_tab(TAB_DRINKS, false)
	_sell_tab = _make_tab(TAB_SELL, true)
	row.add_child(_drinks_tab)
	row.add_child(_sell_tab)
	return row


func _make_tab(text: String, is_sell: bool) -> Button:
	var button := Button.new()
	button.text = text
	button.toggle_mode = true
	button.button_group = _tabs
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size.y = 30
	button.button_pressed = not is_sell
	button.toggled.connect(_on_tab_toggled.bind(is_sell))
	return button


func _build_body() -> Control:
	var body := VBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_drinks_box = VBoxContainer.new()
	_drinks_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_drinks_box.add_theme_constant_override("separation", 8)
	_drinks_box.add_child(_make_label(TITLE_DRINKS, 17, HEADER_COLOR))
	_list = ItemList.new()
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.add_theme_font_size_override("font_size", 14)
	_list.item_clicked.connect(_on_drink_clicked)
	_drinks_box.add_child(_list)
	body.add_child(_drinks_box)
	_sell_box = VBoxContainer.new()
	_sell_box.add_theme_constant_override("separation", 8)
	_sell_box.visible = false
	_sell_box.add_child(_make_label(TITLE_SELL, 17, SELL_TITLE_COLOR))
	_sell_box.add_child(_make_label(SELL_HINT, 14, TEXT_COLOR))
	body.add_child(_sell_box)
	return body


func _build_footer() -> Control:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	var close_button := Button.new()
	close_button.text = CLOSE_TEXT
	close_button.custom_minimum_size = Vector2(120, 30)
	close_button.pressed.connect(close)
	row.add_child(close_button)
	return row


func _make_label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
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
