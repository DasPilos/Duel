extends Control

# Комнаты подземелья из deck/ui/dungeon_window.py и world_map_scene.py: поле по клеткам, проём, торговец, фонтан и сундук.
# Сеть ведёт мир (deck_world.gd): вид сообщает о действиях сигналами и принимает ответы методами.

signal battle_requested(room: int, tile: Vector2i)
signal merchant_requested()
signal merchant_buy_requested(kind: String, index: int)
signal fountain_requested()
signal chest_open_requested(request_id: String)
signal exit_requested()

const RULES := preload("res://scripts/deck_dungeon_rules.gd")
const TILE_PIXELS := 48.0
const COLOR_BACKGROUND := Color8(18, 19, 23)
const COLOR_WALL := Color8(61, 58, 60)
const COLOR_FLOOR_A := Color8(53, 50, 53)
const COLOR_FLOOR_B := Color8(47, 45, 48)
const COLOR_GRID := Color8(32, 30, 33)
const COLOR_DOOR := Color8(155, 55, 48)
const COLOR_PLAYER := Color8(90, 170, 255)
const COLOR_SKELETON := Color8(196, 194, 180)
const COLOR_MERCHANT := Color8(166, 122, 77)
const COLOR_FOUNTAIN := Color8(76, 157, 193)
const COLOR_CHEST := Color8(184, 138, 54)
const COLOR_LABEL := Color8(235, 190, 155)
const COLOR_TEXT := Color8(220, 218, 207)
const COLOR_HINT := Color8(235, 220, 185)
const COLOR_MESSAGE := Color8(255, 220, 150)
const COLOR_ERROR := Color8(255, 150, 140)
const PANEL_BG := Color8(27, 29, 35, 245)
const PANEL_BORDER := Color8(115, 112, 101)
const MERCHANT_TITLE := "Подземный торговец"
const MERCHANT_LOADING := "Загружаем ассортимент…"
const MERCHANT_EMPTY := "Ассортимент пока пуст."
const MERCHANT_SELECT := "Выберите товар в списке."
const MERCHANT_UNAVAILABLE := "Эта карта пока недоступна для покупки"
const MERCHANT_BUY := "КУПИТЬ"
const MERCHANT_CLOSE := "ЗАКРЫТЬ МАГАЗИН"
const CHEST_TITLE := "Сундук павшего короля"
const CHEST_TEXT := "Откройте сундук, чтобы получить все выпавшие награды."
const CHEST_OPEN := "ОТКРЫТЬ СУНДУК"
const CHEST_LEAVE := "ВЫЙТИ"
const CHEST_DONE := "Награды добавлены в инвентарь"
const FOUNTAIN_DONE := "Фонтан восстановил здоровье и ману"
const FOUNTAIN_ALREADY := "Фонтан уже восстановил здоровье и ману"
const CLEARED := "Комната очищена: проход открыт"
const BATTLE_STARTING := "Бой начинается…"
const TOO_FAR := "Подойдите ближе к объекту"
const EXIT_HINT := "Подойдите к сундуку и нажмите E, чтобы выйти"

var _open := false
var _room := 1
var _player := Vector2i.ZERO
var _cleared: Dictionary = {}
var _completed: Dictionary = {}
var _treasure_opened := false
var _busy := false
var _message := ""
var _message_error := false
var _panel := ""
var _merchant_items: Array = []
var _merchant_cards: Array = []
var _chest_request_id := ""
var _chest_rewards: Array = []
var _title: Label
var _hint: Label
var _message_label: Label
var _panel_root: Control
var _panel_title: Label
var _panel_close: Button
var _panel_balance: Label
var _merchant_list: ItemList
var _panel_text: Label
var _panel_message: Label
var _panel_primary: Button
var _panel_secondary: Button


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var top := VBoxContainer.new()
	top.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	top.offset_top = 24.0
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(top)
	_title = _label(26, COLOR_TEXT)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	top.add_child(_title)
	var bottom := VBoxContainer.new()
	bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_top = -84.0
	bottom.offset_bottom = -28.0
	bottom.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bottom)
	_message_label = _label(15, COLOR_MESSAGE)
	_message_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	bottom.add_child(_message_label)
	_hint = _label(15, COLOR_HINT)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	bottom.add_child(_hint)
	_build_panel()


func open_dungeon() -> void:
	_open = true
	_busy = false
	_room = 1
	_player = RULES.start_tile()
	_cleared.clear()
	_completed.clear()
	_treasure_opened = false
	_panel = ""
	_panel_root.visible = false
	visible = true
	_set_message("", false)
	_refresh()


func close_dungeon() -> void:
	_open = false
	_busy = false
	_panel = ""
	_panel_root.visible = false
	visible = false


# Пока открыт бой, поле скрыто: клавиши обрабатывает окно арены.
func set_suspended(value: bool) -> void:
	visible = _open and not value


func is_open() -> bool:
	return _open


func is_busy() -> bool:
	return _busy


func room() -> int:
	return _room


func player_tile() -> Vector2i:
	return _player


func panel_name() -> String:
	return _panel


func is_cleared(room_number: int) -> bool:
	return _cleared.has(room_number)


func is_completed(room_number: int) -> bool:
	return _completed.has(room_number)


func treasure_opened() -> bool:
	return _treasure_opened


func battle_started(_room_number: int) -> void:
	_busy = true
	_set_message(BATTLE_STARTING, false)
	_refresh()


func battle_start_failed(message: String) -> void:
	_busy = false
	_set_message(message, true)
	_refresh()


# Итог боя комнаты: победа открывает проход, поражение и телепорт закрывает подземелье миром.
func battle_won(room_number: int) -> void:
	_cleared[room_number] = true
	_busy = false
	_set_message(CLEARED, false)
	_refresh()


func battle_lost() -> void:
	_busy = false
	_refresh()


func show_merchant(items: Array, cards: Array, balance_text: String) -> void:
	_merchant_items = items
	_merchant_cards = cards
	_merchant_list.clear()
	for item in items:
		_merchant_list.add_item("%s — %s" % [str(item.get("name", "")), str(item.get("price_text", ""))])
	for card in cards:
		_merchant_list.add_item("%s — %s" % [str(card.get("name", "")), str(card.get("price_text", ""))])
	_panel_balance.text = balance_text
	_panel_text.text = MERCHANT_EMPTY if items.is_empty() and cards.is_empty() else ""
	_panel_message.text = ""


func merchant_result(message: String, is_error: bool, balance_text: String) -> void:
	_busy = false
	_panel_message.text = message
	_panel_message.add_theme_color_override("font_color", COLOR_ERROR if is_error else COLOR_MESSAGE)
	if not balance_text.is_empty():
		_panel_balance.text = balance_text


func fountain_result(ok: bool, message: String) -> void:
	_busy = false
	if ok:
		_completed[RULES.FOUNTAIN_ROOM] = true
	_set_message(FOUNTAIN_DONE if ok else message, not ok)
	_refresh()


func chest_result(ok: bool, rewards: Array, message: String) -> void:
	_busy = false
	if ok:
		_treasure_opened = true
		_chest_rewards = rewards
		var lines := PackedStringArray()
		for reward in rewards:
			lines.append(str(reward))
		_panel_text.text = "\n".join(lines)
		_panel_message.text = CHEST_DONE
		_panel_message.add_theme_color_override("font_color", COLOR_MESSAGE)
		_panel_primary.text = CHEST_LEAVE
	else:
		_panel_message.text = message
		_panel_message.add_theme_color_override("font_color", COLOR_ERROR)
	_refresh()


func _input(event: InputEvent) -> void:
	if not visible or not _open or not (event is InputEventKey):
		return
	var key := event as InputEventKey
	if not key.pressed or key.keycode == KEY_ESCAPE:
		return
	if _panel != "":
		get_viewport().set_input_as_handled()
		return
	var step := _step_for(key.keycode)
	if step != Vector2i.ZERO:
		_try_move(step)
	elif key.keycode == KEY_E and not key.echo:
		_interact()
	else:
		return
	get_viewport().set_input_as_handled()


func _gui_input(event: InputEvent) -> void:
	if not _open or _panel != "" or _busy:
		return
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if not button.pressed or button.button_index != MOUSE_BUTTON_LEFT:
			return
		var tile := _tile_at(button.position)
		if tile == RULES.actor_tile():
			_interact()
		elif tile != RULES.NO_TILE and maxi(absi(tile.x - _player.x), absi(tile.y - _player.y)) == 1:
			_try_move(tile - _player)
		accept_event()


func _step_for(keycode: int) -> Vector2i:
	match keycode:
		KEY_UP, KEY_W:
			return Vector2i(0, -1)
		KEY_DOWN, KEY_S:
			return Vector2i(0, 1)
		KEY_LEFT, KEY_A:
			return Vector2i(-1, 0)
		KEY_RIGHT, KEY_D:
			return Vector2i(1, 0)
	return Vector2i.ZERO


func _gate() -> bool:
	return RULES.gate_open(_room, _cleared, _completed)


func _try_move(step: Vector2i) -> void:
	if _busy or _panel != "":
		return
	var gate := _gate()
	if RULES.leaves_east(_room, _player, step, gate):
		_enter_room(_room + 1)
		return
	var target := _player + step
	if not RULES.is_passable(target, gate):
		return
	_player = target
	_set_message("", false)
	_refresh()
	_after_move()


func _enter_room(room_number: int) -> void:
	_room = room_number
	_player = RULES.start_tile()
	_set_message("", false)
	_refresh()


# Бой начинается сам, когда игрок подходит к противнику комнаты, как _update_dungeon_encounter в Python.
func _after_move() -> void:
	if RULES.battle_pending(_room, _cleared) and RULES.actor_reachable(_player) and not _busy:
		_busy = true
		_set_message(BATTLE_STARTING, false)
		_refresh()
		battle_requested.emit(_room, _player)


func _interact() -> void:
	if _busy or _panel != "":
		return
	if not RULES.actor_reachable(_player):
		_set_message(TOO_FAR, true)
		_refresh()
		return
	match _room:
		2:
			_open_merchant()
		4:
			if _completed.has(RULES.FOUNTAIN_ROOM):
				_set_message(FOUNTAIN_ALREADY, false)
			else:
				_busy = true
				fountain_requested.emit()
		6:
			if _treasure_opened:
				exit_requested.emit()
			else:
				_open_chest()
	_refresh()


func _open_merchant() -> void:
	_panel = "merchant"
	_panel_title.text = MERCHANT_TITLE
	_panel_text.text = MERCHANT_LOADING
	_panel_message.text = ""
	_panel_primary.text = MERCHANT_BUY
	_panel_primary.visible = true
	_panel_secondary.text = MERCHANT_CLOSE
	_merchant_list.visible = true
	_panel_balance.visible = true
	_merchant_list.clear()
	_panel_root.visible = true
	merchant_requested.emit()


func _open_chest() -> void:
	_panel = "chest"
	_chest_request_id = RULES.new_request_id()
	_panel_title.text = CHEST_TITLE
	_panel_text.text = CHEST_TEXT
	_panel_message.text = ""
	_panel_primary.text = CHEST_OPEN
	_panel_primary.visible = true
	_panel_secondary.visible = false
	_merchant_list.visible = false
	_panel_balance.visible = false
	_panel_root.visible = true


func _close_panel() -> void:
	if _panel == "merchant":
		_panel_root.visible = false
		_panel = ""
	elif _panel == "chest" and not _busy:
		_panel_root.visible = false
		_panel = ""
	_panel_secondary.visible = true
	_refresh()


func _on_primary_pressed() -> void:
	if _panel == "merchant":
		_buy_selected()
	elif _panel == "chest":
		if _treasure_opened:
			_panel_root.visible = false
			_panel = ""
			exit_requested.emit()
		elif not _busy:
			_busy = true
			chest_open_requested.emit(_chest_request_id)


func _on_secondary_pressed() -> void:
	if _panel == "merchant":
		_completed[RULES.MERCHANT_ROOM] = true
		_panel_root.visible = false
		_panel = ""
		_refresh()


func _buy_selected() -> void:
	if _busy:
		return
	var selected := _merchant_list.get_selected_items()
	if selected.is_empty():
		_panel_message.text = MERCHANT_SELECT
		_panel_message.add_theme_color_override("font_color", COLOR_ERROR)
		return
	var index: int = selected[0]
	if index < _merchant_items.size():
		_busy = true
		merchant_buy_requested.emit("supply", index)
		return
	var card_index := index - _merchant_items.size()
	if not bool(_merchant_cards[card_index].get("available", false)):
		_panel_message.text = MERCHANT_UNAVAILABLE
		_panel_message.add_theme_color_override("font_color", COLOR_ERROR)
		return
	_busy = true
	merchant_buy_requested.emit("card", card_index)


func _tile_at(pos: Vector2) -> Vector2i:
	var local := (pos - _room_origin()) / TILE_PIXELS
	var tile := RULES.ORIGIN + Vector2i(floori(local.x), floori(local.y))
	return tile if RULES.is_inside(tile) else RULES.NO_TILE


func _room_origin() -> Vector2:
	var board := Vector2(RULES.SIZE) * TILE_PIXELS
	return Vector2((size.x - board.x) / 2.0, (size.y - board.y) / 2.0)


func _set_message(text: String, is_error: bool) -> void:
	_message = text
	_message_error = is_error


func _refresh() -> void:
	_title.text = RULES.room_name(_room)
	var text := _message
	if text.is_empty():
		text = RULES.hint(_room, _gate(), _treasure_opened)
		if _room == RULES.CHEST_ROOM and _treasure_opened:
			text = EXIT_HINT
	_hint.text = "" if _message != "" else text
	_message_label.text = _message
	_message_label.add_theme_color_override("font_color", COLOR_ERROR if _message_error else COLOR_MESSAGE)
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), COLOR_BACKGROUND)
	var gate := _gate()
	var tile_size := Vector2(TILE_PIXELS, TILE_PIXELS)
	for y in range(RULES.ORIGIN.y, RULES.ORIGIN.y + RULES.SIZE.y):
		for x in range(RULES.ORIGIN.x, RULES.ORIGIN.x + RULES.SIZE.x):
			var tile := Vector2i(x, y)
			var rect := Rect2(_cell_origin(tile), tile_size)
			var color := COLOR_WALL if RULES.is_wall(tile, gate) else (COLOR_FLOOR_B if (x + y) % 2 == 1 else COLOR_FLOOR_A)
			draw_rect(rect, color)
			draw_rect(rect, COLOR_GRID, false, 1.0)
	if _room < RULES.ROOM_COUNT and not gate:
		var door_center := _cell_origin(RULES.door_tile()) + tile_size / 2.0
		draw_line(door_center + Vector2(-8.0, -18.0), door_center + Vector2(-8.0, 18.0), COLOR_DOOR, 5.0)
		draw_line(door_center + Vector2(8.0, -18.0), door_center + Vector2(8.0, 18.0), COLOR_DOOR, 5.0)
	_draw_actor(_cell_origin(RULES.actor_tile()) + tile_size / 2.0)
	var player_center := _cell_origin(_player) + tile_size / 2.0
	draw_circle(player_center, TILE_PIXELS * 0.36, COLOR_PLAYER)
	draw_arc(player_center, TILE_PIXELS * 0.36, 0.0, TAU, 24, Color(0.0, 0.0, 0.0, 0.7), 1.5)


func _cell_origin(tile: Vector2i) -> Vector2:
	return _room_origin() + Vector2(tile - RULES.ORIGIN) * TILE_PIXELS


func _draw_actor(center: Vector2) -> void:
	var font := ThemeDB.fallback_font
	var label_text := ""
	match _room:
		1, 3, 5:
			if _cleared.has(_room):
				return
			for offset in [-12.0, 12.0]:
				draw_circle(center + Vector2(offset, -10.0), 7.0, COLOR_SKELETON)
				draw_line(center + Vector2(offset, -3.0), center + Vector2(offset, 12.0), COLOR_SKELETON, 3.0)
		2:
			draw_rect(Rect2(center - Vector2(16.0, 18.0), Vector2(32.0, 30.0)), COLOR_MERCHANT)
		4:
			draw_circle(center, 16.0, COLOR_FOUNTAIN)
			draw_arc(center, 10.0, 0.0, TAU, 20, Color8(147, 217, 230), 3.0)
		6:
			draw_rect(Rect2(center - Vector2(16.0, 14.0), Vector2(32.0, 26.0)), COLOR_CHEST)
	label_text = str(RULES.ACTOR_LABELS.get(_room, ""))
	if not label_text.is_empty():
		draw_string(font, center + Vector2(-70.0, 34.0), label_text, HORIZONTAL_ALIGNMENT_CENTER, 140.0, 12, COLOR_LABEL)


func _build_panel() -> void:
	_panel_root = Control.new()
	_panel_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_panel_root.visible = false
	_panel_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_panel_root)
	var dim := ColorRect.new()
	dim.color = Color(0.0, 0.0, 0.0, 0.62)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	_panel_root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel_root.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size.x = 640.0
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_BG
	style.border_color = PANEL_BORDER
	style.set_border_width_all(3)
	style.set_corner_radius_all(12)
	style.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", style)
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	panel.add_child(box)
	var title_row := HBoxContainer.new()
	box.add_child(title_row)
	_panel_title = _label(22, COLOR_TEXT)
	_panel_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(_panel_title)
	_panel_close = Button.new()
	_panel_close.text = "×"
	_panel_close.custom_minimum_size = Vector2(36.0, 36.0)
	_panel_close.pressed.connect(_close_panel)
	title_row.add_child(_panel_close)
	_panel_balance = _label(14, Color8(238, 208, 118))
	box.add_child(_panel_balance)
	_merchant_list = ItemList.new()
	_merchant_list.custom_minimum_size = Vector2(600.0, 240.0)
	box.add_child(_merchant_list)
	_panel_text = _label(15, COLOR_TEXT)
	_panel_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_panel_text.custom_minimum_size.x = 600.0
	box.add_child(_panel_text)
	_panel_message = _label(14, COLOR_MESSAGE)
	_panel_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_panel_message.custom_minimum_size.x = 600.0
	box.add_child(_panel_message)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 20)
	box.add_child(row)
	_panel_primary = Button.new()
	_panel_primary.custom_minimum_size = Vector2(240.0, 44.0)
	_panel_primary.pressed.connect(_on_primary_pressed)
	row.add_child(_panel_primary)
	_panel_secondary = Button.new()
	_panel_secondary.custom_minimum_size = Vector2(240.0, 44.0)
	_panel_secondary.pressed.connect(_on_secondary_pressed)
	row.add_child(_panel_secondary)


func _label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label
