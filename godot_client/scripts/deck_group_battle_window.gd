extends Control

# Окно «Стенка на стенку»: заявки на групповой бой, своя заявка и параметры нового сбора.
# Запросы делает deck_world.gd; окно показывает состояние и сообщает о действиях игрока.
signal create_requested(participants_value: int, ttl: int)
signal join_requested(offer_id: String)
signal leave_requested(offer_id: String)
signal start_requested(offer_id: String)

const RULES := preload("res://scripts/deck_group_battle_rules.gd")
const TITLE := "СТЕНКА НА СТЕНКУ"
const CLOSE_TEXT := "ЗАКРЫТЬ"
const SIZE_TITLE := "Количество участников"
const TTL_TITLE := "Время сбора"
const CREATE_TEXT := "СОЗДАТЬ СБОР"
const LEAVE_TEXT := "ОТМЕНИТЬ СБОР"
const START_TEXT := "НАЧАТЬ КОМАНДНЫЙ БОЙ"
const JOIN_TEXT := "ВСТУПИТЬ"
const OWN_TEXT := "ВЫ В СБОРЕ"
const CLOSED_TEXT := "НЕДОСТУПНО"
const LIST_TITLE := "Заявки на сбор"
const EMPTY_TEXT := "Активных заявок пока нет"
const OWN_PREFIX := "Ваш сбор: "
const WINDOW_WIDTH := 600.0
const WINDOW_HEIGHT := 600.0
const LIST_HEIGHT := 200.0
const WINDOW_BACKGROUND := Color8(40, 50, 70, 250)
const WINDOW_BORDER := Color8(150, 150, 170)
const HEADER_COLOR := Color8(255, 220, 120)
const TEXT_COLOR := Color8(200, 200, 200)
const ERROR_COLOR := Color8(255, 100, 100)
const OK_COLOR := Color8(150, 230, 170)
const SELECTED_COLOR := Color8(70, 170, 100)

var _window: PanelContainer
var _message: Label
var _own_box: VBoxContainer
var _own_status: Label
var _own_team: Label
var _start_button: Button
var _leave_button: Button
var _create_box: VBoxContainer
var _size_group := ButtonGroup.new()
var _ttl_group := ButtonGroup.new()
var _create_button: Button
var _offers_box: VBoxContainer
var _offers: Array = []
var _own: Dictionary = {}
var _character_id := 0
var _selected_size := 0
var _selected_ttl := 0
var _busy := false
var _join_buttons: Dictionary = {}
var _countdowns: Array = []
var _tick := 0.0


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
	_message = _make_label("", 13, TEXT_COLOR)
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_message.custom_minimum_size.x = WINDOW_WIDTH - 40.0
	layout.add_child(_message)
	layout.add_child(_build_own_block())
	layout.add_child(_build_create_block())
	layout.add_child(_make_label(LIST_TITLE, 15, HEADER_COLOR))
	layout.add_child(_build_list())


func open(character_id: int) -> void:
	_character_id = character_id
	_busy = false
	visible = true
	_refresh_all()


func close() -> void:
	visible = false


func is_open() -> bool:
	return visible


func set_state(offers: Array, character_id: int) -> void:
	_character_id = character_id
	_offers = offers
	_own = RULES.own_offer(offers, character_id)
	_refresh_all()


func show_message(text: String, is_error := false) -> void:
	_message.text = text
	_message.add_theme_color_override("font_color", ERROR_COLOR if is_error else OK_COLOR)


func set_busy(value: bool) -> void:
	_busy = value
	_refresh_buttons()


func refresh_clock(now: float) -> void:
	if not _own.is_empty():
		_own_status.text = OWN_PREFIX + _row_text(_own, now)
	for entry in _countdowns:
		entry["label"].text = _row_text(entry["offer"], now)


func _process(delta: float) -> void:
	if not visible:
		return
	_tick += delta
	if _tick < 1.0:
		return
	_tick = 0.0
	refresh_clock(Time.get_unix_time_from_system())


func _on_backdrop_input(event: InputEvent) -> void:
	var click := event as InputEventMouseButton
	if click != null and click.pressed and click.button_index == MOUSE_BUTTON_LEFT:
		close()


func _refresh_all() -> void:
	_refresh_own_block()
	_refresh_offer_rows()
	_refresh_buttons()
	refresh_clock(Time.get_unix_time_from_system())


func _refresh_own_block() -> void:
	var has_own := not _own.is_empty()
	_own_box.visible = has_own
	_create_box.visible = not has_own
	if not has_own:
		return
	var status := str(_own.get("status", ""))
	_own_team.text = ""
	if status == "ready" and RULES.team_of(_own, _character_id) >= 0:
		var opponent := RULES.opponent_of(_own, _character_id)
		_own_team.text = "Команда %d · соперник: %s" % [
			RULES.team_of(_own, _character_id) + 1,
			str(opponent.get("name", "—")),
		]
	_start_button.visible = RULES.start_available(_own, _character_id)
	_leave_button.visible = status == "waiting"


func _refresh_offer_rows() -> void:
	for child in _offers_box.get_children():
		_offers_box.remove_child(child)
		child.queue_free()
	_join_buttons.clear()
	_countdowns.clear()
	if _offers.is_empty():
		_offers_box.add_child(_make_label(EMPTY_TEXT, 13, TEXT_COLOR))
		return
	for offer_variant in _offers:
		if not offer_variant is Dictionary:
			continue
		var offer: Dictionary = offer_variant
		var offer_id := str(offer.get("id", ""))
		var row := HBoxContainer.new()
		var label := _make_label("", 13, TEXT_COLOR)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		_countdowns.append({"label": label, "offer": offer})
		var button := Button.new()
		var joinable := _own.is_empty() and RULES.can_join(offer, _character_id)
		if not _own.is_empty() and str(_own.get("id", "")) == offer_id:
			button.text = OWN_TEXT
		elif joinable:
			button.text = JOIN_TEXT
			button.pressed.connect(_on_join_pressed.bind(offer_id))
		else:
			button.text = CLOSED_TEXT
		button.set_meta("joinable", joinable)
		_join_buttons[offer_id] = button
		row.add_child(button)
		_offers_box.add_child(row)


func _refresh_buttons() -> void:
	for offer_id in _join_buttons:
		var button: Button = _join_buttons[offer_id]
		button.disabled = _busy or not bool(button.get_meta("joinable", false))
	_leave_button.disabled = _busy
	_start_button.disabled = _busy
	_refresh_create_button()


func _refresh_create_button() -> void:
	_create_button.disabled = _busy or not RULES.validate_choice(_selected_size, _selected_ttl).is_empty()


func _row_text(offer: Dictionary, now: float) -> String:
	var text := "%s · %s" % [RULES.offer_title(offer), RULES.status_label(offer)]
	if str(offer.get("status", "")) == "waiting":
		text += " · осталось %s" % RULES.format_clock(RULES.seconds_left(offer, now))
	return text


func _on_join_pressed(offer_id: String) -> void:
	if not _busy:
		join_requested.emit(offer_id)


func _on_leave_pressed() -> void:
	if not _busy and not _own.is_empty():
		leave_requested.emit(str(_own.get("id", "")))


func _on_start_pressed() -> void:
	if not _busy and RULES.start_available(_own, _character_id):
		start_requested.emit(str(_own.get("id", "")))


func _on_create_pressed() -> void:
	if not _busy and RULES.validate_choice(_selected_size, _selected_ttl).is_empty():
		create_requested.emit(_selected_size, _selected_ttl)


func _on_size_toggled(pressed: bool, value: int) -> void:
	if pressed:
		_selected_size = value
	_refresh_create_button()


func _on_ttl_toggled(pressed: bool, value: int) -> void:
	if pressed:
		_selected_ttl = value
	_refresh_create_button()


func _build_header() -> Control:
	var row := HBoxContainer.new()
	var title := _make_label(TITLE, 20, HEADER_COLOR)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title)
	var close_button := Button.new()
	close_button.text = CLOSE_TEXT
	close_button.pressed.connect(close)
	row.add_child(close_button)
	return row


func _build_own_block() -> Control:
	_own_box = VBoxContainer.new()
	_own_box.add_theme_constant_override("separation", 6)
	_own_status = _make_label("", 14, TEXT_COLOR)
	_own_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_own_box.add_child(_own_status)
	_own_team = _make_label("", 13, TEXT_COLOR)
	_own_box.add_child(_own_team)
	var row := HBoxContainer.new()
	_start_button = Button.new()
	_start_button.text = START_TEXT
	_start_button.pressed.connect(_on_start_pressed)
	row.add_child(_start_button)
	_leave_button = Button.new()
	_leave_button.text = LEAVE_TEXT
	_leave_button.pressed.connect(_on_leave_pressed)
	row.add_child(_leave_button)
	_own_box.add_child(row)
	return _own_box


func _build_create_block() -> Control:
	_create_box = VBoxContainer.new()
	_create_box.add_theme_constant_override("separation", 6)
	_create_box.add_child(_make_label(SIZE_TITLE, 14, TEXT_COLOR))
	var sizes := HBoxContainer.new()
	for index in range(RULES.SIZE_OPTIONS.size()):
		var value: int = RULES.SIZE_OPTIONS[index]
		var button := _make_choice_button(RULES.SIZE_LABELS[index], _size_group)
		button.toggled.connect(_on_size_toggled.bind(value))
		sizes.add_child(button)
	_create_box.add_child(sizes)
	_create_box.add_child(_make_label(TTL_TITLE, 14, TEXT_COLOR))
	var times := HBoxContainer.new()
	for index in range(RULES.TTL_OPTIONS.size()):
		var value: int = RULES.TTL_OPTIONS[index]
		var button := _make_choice_button(RULES.TTL_LABELS[index], _ttl_group)
		button.toggled.connect(_on_ttl_toggled.bind(value))
		times.add_child(button)
	_create_box.add_child(times)
	_create_button = Button.new()
	_create_button.text = CREATE_TEXT
	_create_button.pressed.connect(_on_create_pressed)
	_create_box.add_child(_create_button)
	return _create_box


func _build_list() -> Control:
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.y = LIST_HEIGHT
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_offers_box = VBoxContainer.new()
	_offers_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_offers_box)
	return scroll


func _make_choice_button(text: String, group: ButtonGroup) -> Button:
	var button := Button.new()
	button.text = text
	button.toggle_mode = true
	button.button_group = group
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var selected := StyleBoxFlat.new()
	selected.bg_color = SELECTED_COLOR
	selected.set_corner_radius_all(4)
	button.add_theme_stylebox_override("pressed", selected)
	button.add_theme_stylebox_override("hover_pressed", selected)
	return button


func _make_label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _box_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = WINDOW_BACKGROUND
	style.border_color = WINDOW_BORDER
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(16)
	return style
