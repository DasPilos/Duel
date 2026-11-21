extends Control

# Окно магазина припасов из deck/ui/supplies_shop_window.py. Окно открывается сразу; каталог и баланс
# приходят из мира (set_items, set_balance). Покупку окно не выполняет: оно сообщает buy_requested,
# мир отправляет запрос и возвращает результат через show_message.

signal buy_requested(item_id: int, item_name: String)

const CURRENCY := preload("res://scripts/deck_currency.gd")
const WINDOW_WIDTH := 620.0
const WINDOW_HEIGHT := 390.0
const ROW_HEIGHT := 52.0
const PRICE_WIDTH := 100.0
const WINDOW_BACKGROUND := Color8(20, 31, 44, 250)
const WINDOW_BORDER := Color8(80, 155, 220)
const TITLE_COLOR := Color8(140, 205, 255)
const PRICE_COLOR := Color8(240, 210, 115)
const MESSAGE_COLOR := Color8(245, 220, 140)
const ERROR_COLOR := Color8(255, 150, 140)

var _items: Array = []
var _selected_index := 0
var _group := ButtonGroup.new()
var _window: PanelContainer
var _balance: Label
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
	_window.add_theme_stylebox_override("panel", _box_style())
	center.add_child(_window)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	_window.add_child(layout)
	layout.add_child(_build_header())
	_balance = _make_label(14, PRICE_COLOR)
	layout.add_child(_balance)
	_rows = VBoxContainer.new()
	_rows.add_theme_constant_override("separation", 6)
	layout.add_child(_rows)
	layout.add_child(_build_footer())
	set_balance(0)


func open(coins: int) -> void:
	set_balance(coins)
	_selected_index = 0
	set_items([])
	show_message("Загружаем ассортимент…")
	visible = true


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


func set_balance(coins: int) -> void:
	_balance.text = "У вас: %s" % CURRENCY.format_coins(coins)


func set_items(items: Array) -> void:
	_items = items.duplicate(true)
	_selected_index = clampi(_selected_index, 0, maxi(0, _items.size() - 1))
	_render_rows()
	show_message("")


func show_message(text: String, is_error := false) -> void:
	_message.text = text
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else MESSAGE_COLOR)


func _render_rows() -> void:
	for child in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()
	for index in range(_items.size()):
		_rows.add_child(_make_row(index, _items[index]))


func _make_row(index: int, item: Dictionary) -> HBoxContainer:
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	var row := Button.new()
	row.toggle_mode = true
	row.button_group = _group
	row.alignment = HORIZONTAL_ALIGNMENT_LEFT
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.custom_minimum_size = Vector2(0, ROW_HEIGHT)
	row.text = "%s\n%s" % [str(item.get("name", "")), str(item.get("description", ""))]
	row.button_pressed = index == _selected_index
	row.toggled.connect(_on_row_toggled.bind(index))
	line.add_child(row)
	var price := _make_label(14, PRICE_COLOR)
	price.text = CURRENCY.format_coins(int(item.get("price", 0)))
	price.custom_minimum_size.x = PRICE_WIDTH
	price.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	price.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	line.add_child(price)
	return line


func _on_row_toggled(on: bool, index: int) -> void:
	if not on:
		return
	_selected_index = index
	show_message("")


func _on_buy_pressed() -> void:
	if _items.is_empty():
		show_message("Товары не загружены", true)
		return
	var item: Dictionary = _items[_selected_index]
	buy_requested.emit(int(item.get("item_id", 0)), str(item.get("name", "")))


func _on_backdrop_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		close()


func _build_header() -> Control:
	var header := HBoxContainer.new()
	var title := _make_label(17, TITLE_COLOR)
	title.text = "Магазин с припасами"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.text = "×"
	close_button.custom_minimum_size = Vector2(32, 28)
	close_button.pressed.connect(close)
	header.add_child(close_button)
	return header


func _build_footer() -> Control:
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	_message = _make_label(13, MESSAGE_COLOR)
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.custom_minimum_size.x = 240.0
	_message.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(_message)
	var buy_button := Button.new()
	buy_button.text = "КУПИТЬ"
	buy_button.custom_minimum_size = Vector2(160, 36)
	buy_button.pressed.connect(_on_buy_pressed)
	footer.add_child(buy_button)
	return footer


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
	style.set_content_margin_all(12)
	return style
