extends Control

# Бой на арене из deck/ui/arena_overlay.py. Клиент рисует поле и отправляет команды,
# а бой считает сервер (deck/server/arena.py). Анимации шагов и всплывающие числа не переносятся:
# урон, ходы и призывы видны в журнале боя.

signal command_requested(command: Dictionary)
signal finished_confirmed(finished: Dictionary)

const RULES := preload("res://scripts/deck_arena_rules.gd")
const LEFT_WIDTH := 430.0
const RIGHT_WIDTH := 230.0
const BUTTON_SIZE := Vector2(RIGHT_WIDTH, 46.0)
const HAND_CARD_SIZE := Vector2(150.0, 200.0)
const HAND_GAP := 12
const DRAFT_CARD_SIZE := Vector2(170.0, 120.0)
const DRAFT_COLUMNS := 5
const DRAW_CARD_SIZE := Vector2(230.0, 150.0)
const NOTICE_SECONDS := 2.5
const MARGIN := 16
const CARD_FONT_SIZE := 13
const MISS_HINT := "Здесь нельзя — выберите подсвеченную цель"
const BUTTONS := [
	["teleport", "ТЕЛЕПОРТ"],
	["inventory", "ИНВЕНТАРЬ"],
	["move", "ПОХОДИТЬ"],
	["cards", "РАЗЫГРАТЬ КАРТЫ"],
	["burn", "СЖЕЧЬ КАРТУ"],
	["end", "ЗАВЕРШИТЬ ХОД"],
]
const DRAFT_TITLE := "Выберите 2 карты; ещё 3 будут выданы случайно"
const DRAW_TITLE := "Выберите 1 из 2 карт"
const TELEPORT_TITLE := "Подтвердите телепорт"
const TELEPORT_TEXT := "Персонаж покинет арену и вернётся в зал. Продолжить?"
const ITEMS_TITLE := "Инвентарь"
const ITEMS_EMPTY := "В рюкзаке нет предметов для боя."
const LOG_TITLE := "Журнал боя"
const UNIT_TITLE := "Существо"
const UNIT_EMPTY := "Наведите курсор на существо"
const SELECT_HAND_HINT := "Выберите карту для розыгрыша"
const SELECTED_HINT := "Нажмите на выбранную карту ещё раз, чтобы выбрать цель"
const BURN_HINT := "Выберите карту и нажмите B, чтобы сжечь её"
const BURN_ONCE := "За ход можно сжечь только одну карту"
const DAGGER_HINT := "Выберите врага для метательного кинжала (S — отмена)"
const DAGGER_NEED_ENEMY := "Выберите врага для метательного кинжала"
const ITEM_CANCELLED := "Выбор цели для предмета отменён"
const CANCELLED := "Розыгрыш отменён"
const NO_ITEM_SELECTED := "Выберите предмет в рюкзаке"
const COLOR_TILE_EVEN := Color8(53, 70, 40)
const COLOR_TILE_ODD := Color8(48, 65, 37)
const COLOR_GRAVE := Color8(108, 108, 114)
const COLOR_REACH := Color8(48, 105, 60)
const COLOR_REACH_HOVER := Color8(70, 155, 85)
const COLOR_SUMMON := Color8(45, 105, 135)
const COLOR_SUMMON_HOVER := Color8(80, 165, 210)
const COLOR_BARRIER := Color8(105, 105, 115)
const COLOR_TRAP := Color8(118, 118, 122)
const COLOR_OBSTACLE := Color8(72, 66, 60)
const COLOR_AIM := Color8(96, 58, 50)
const COLOR_SPLASH := Color(1.0, 0.14, 0.14, 0.36)
const COLOR_TARGET_ENEMY := Color8(135, 60, 50)
const COLOR_TARGET_ALLY := Color8(50, 135, 65)
const COLOR_EDGE := Color8(150, 150, 80)
const COLOR_BOUNDARY := Color8(235, 200, 90)
const COLOR_HOVER := Color8(255, 255, 255)
const COLOR_PLAYER := Color8(90, 170, 255)
const COLOR_ALLY := Color8(90, 225, 120)
const COLOR_ENEMY := Color8(240, 90, 80)
const COLOR_SUMMON_UNIT := Color8(110, 200, 255)
const COLOR_TARGET_RING := Color8(255, 215, 60)
const PANEL_BG := Color8(14, 16, 22, 230)
const PANEL_BORDER := Color8(190, 160, 80)
const TITLE_COLOR := Color8(255, 225, 140)
const TEXT_COLOR := Color8(225, 230, 240)
const HINT_COLOR := Color8(235, 230, 200)
const NOTICE_COLOR := Color8(255, 225, 140)
const ERROR_COLOR := Color8(255, 150, 140)
const ACTIVE_COLOR := Color(1.0, 0.85, 0.45)

var _state: Dictionary = {}
var _inventory: Array[Dictionary] = []
var _busy := false
var _last_command: Dictionary = {}
var _finished: Dictionary = {}
var _mode := ""
var _burn_mode := false
var _selected_index := -1
var _targeting := false
var _transfer_target := ""
var _pending_item := 0
var _hover_tile := RULES.NO_TILE
var _hover_unit: Dictionary = {}
var _tile_size := 1.0
var _origin := Vector2.ZERO
var _buttons: Dictionary = {}
var _banner_title: Label
var _banner_details: Label
var _log_label: Label
var _unit_label: Label
var _board: Control
var _hint_label: Label
var _notice_label: Label
var _notice_timer: Timer
var _hand_row: HBoxContainer
var _draft_root: Control
var _draft_grid: GridContainer
var _draw_root: Control
var _draw_row: HBoxContainer
var _teleport_root: Control
var _teleport_cancel: Button
var _teleport_confirm: Button
var _items_root: Control
var _items_list: ItemList
var _items_empty: Label
var _items_use: Button
var _result_root: Control
var _result_title: Label
var _result_text: Label
var _result_rewards: Label


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var backdrop := ColorRect.new()
	backdrop.color = Color(0.03, 0.04, 0.06, 0.94)
	backdrop.mouse_filter = Control.MOUSE_FILTER_STOP
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, MARGIN)
	add_child(margin)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	margin.add_child(layout)
	layout.add_child(_build_banner())
	var middle := HBoxContainer.new()
	middle.size_flags_vertical = Control.SIZE_EXPAND_FILL
	middle.add_theme_constant_override("separation", 12)
	layout.add_child(middle)
	middle.add_child(_build_left_column())
	middle.add_child(_build_board())
	middle.add_child(_build_right_column())
	layout.add_child(_build_bottom())
	_notice_timer = Timer.new()
	_notice_timer.one_shot = true
	_notice_timer.timeout.connect(_clear_notice)
	add_child(_notice_timer)
	_build_overlays()


func open(state: Dictionary, inventory: Array) -> void:
	_busy = false
	_last_command = {}
	_finished = {}
	_mode = ""
	_burn_mode = false
	_pending_item = 0
	_clear_selection()
	_inventory = _battle_items(inventory)
	visible = true
	if is_inside_tree():
		get_viewport().gui_release_focus()
	apply_state(state)


func close() -> void:
	visible = false
	_busy = false
	_last_command = {}
	_finished = {}
	_state = {}
	for root in [_draft_root, _draw_root, _teleport_root, _items_root, _result_root]:
		root.visible = false


func is_open() -> bool:
	return visible


# Режим карт: здесь S отменяет выбор, поэтому по S карта под окном не скроллится (arena.mode == "cards" в Python).
func is_cards_mode() -> bool:
	return visible and _mode == "cards" and not _result_root.visible


func is_busy() -> bool:
	return _busy


func set_inventory(inventory: Array) -> void:
	_inventory = _battle_items(inventory)
	_refresh_all()


# Состояние боя из ответа сервера: поле, рука, цели и журнал.
func apply_state(state: Dictionary) -> void:
	_state = state.duplicate(true)
	if str(_state.get("phase", "")) != "battle" or not RULES.result_of(_state).is_empty():
		_pending_item = 0
	var card := _selected_card()
	if not card.is_empty() and not bool(card.get("playable", false)):
		_clear_selection()
	_hover_unit = RULES.unit_at_tile(_tiles_units(), _hover_tile)
	_refresh_all()


# Ответ сервера на команду: новое состояние, заметка, журнал и итог боя.
func receive_response(response: Dictionary) -> void:
	var command := _last_command
	_busy = false
	_last_command = {}
	var state: Variant = response.get("state")
	if state is Dictionary and not (state as Dictionary).is_empty():
		apply_state(state)
	var command_type := str(command.get("type", ""))
	if command_type == "item":
		_spend_item(int(command.get("item_id", 0)))
	elif command_type == "burn":
		_mode = "cards"
		_burn_mode = false
		_clear_selection()
	var notice := RULES.text_of(response.get("notice"))
	if not notice.is_empty():
		_show_notice(notice)
	var finished: Variant = response.get("finished")
	if finished is Dictionary and not (finished as Dictionary).is_empty():
		show_result(finished)
	_refresh_all()


func receive_error(message: String) -> void:
	_busy = false
	_last_command = {}
	_show_notice(message, true)
	_refresh_all()


func show_result(finished: Dictionary) -> void:
	_finished = finished.duplicate(true)
	var info: Array = RULES.RESULT_TEXT.get(str(finished.get("result", "")), ["Бой окончен", "", TEXT_COLOR])
	_result_title.text = str(info[0])
	_result_title.add_theme_color_override("font_color", info[2])
	_result_text.text = str(info[1])
	var lines := PackedStringArray()
	var xp := int(finished.get("xp_awarded", 0))
	if xp > 0:
		lines.append("Опыт за противников: +%d" % xp)
	for key in ["xp_error", "save_error"]:
		var problem := RULES.text_of(finished.get(key))
		if not problem.is_empty():
			lines.append(problem)
	_result_rewards.text = "\n".join(lines)
	_result_root.visible = true


func _input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return
	if key_event.keycode == KEY_S:
		_cancel_interaction()
	elif key_event.keycode == KEY_B:
		_on_burn_pressed()
	else:
		return
	get_viewport().set_input_as_handled()


func _build_banner() -> Control:
	var panel := _panel()
	panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	_banner_title = _label(20, TITLE_COLOR)
	_banner_details = _label(14, TEXT_COLOR)
	box.add_child(_banner_title)
	box.add_child(_banner_details)
	panel.add_child(box)
	return panel


func _build_left_column() -> Control:
	var column := VBoxContainer.new()
	column.custom_minimum_size.x = LEFT_WIDTH
	column.add_theme_constant_override("separation", 10)
	var log_panel := _panel()
	log_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var log_box := VBoxContainer.new()
	log_box.add_child(_title_label(LOG_TITLE))
	_log_label = _wrapping_label(14, TEXT_COLOR)
	log_box.add_child(_log_label)
	log_panel.add_child(log_box)
	column.add_child(log_panel)
	var unit_panel := _panel()
	var unit_box := VBoxContainer.new()
	unit_box.add_child(_title_label(UNIT_TITLE))
	_unit_label = _wrapping_label(14, TEXT_COLOR)
	unit_box.add_child(_unit_label)
	unit_panel.add_child(unit_box)
	column.add_child(unit_panel)
	return column


func _build_board() -> Control:
	_board = Control.new()
	_board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_board.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_board.mouse_filter = Control.MOUSE_FILTER_STOP
	_board.draw.connect(_draw_board)
	_board.gui_input.connect(_on_board_input)
	_board.mouse_exited.connect(_on_board_mouse_exited)
	_board.resized.connect(_on_board_resized)
	return _board


func _build_right_column() -> Control:
	var column := VBoxContainer.new()
	column.custom_minimum_size.x = RIGHT_WIDTH
	column.add_theme_constant_override("separation", 8)
	for entry in BUTTONS:
		var button := Button.new()
		button.custom_minimum_size = BUTTON_SIZE
		button.text = str(entry[1])
		button.pressed.connect(_on_button_pressed.bind(str(entry[0])))
		column.add_child(button)
		_buttons[str(entry[0])] = button
	return column


func _build_bottom() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	_hint_label = _label(15, HINT_COLOR)
	_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_label.custom_minimum_size.y = 22.0
	_notice_label = _label(16, NOTICE_COLOR)
	_notice_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_notice_label.custom_minimum_size.y = 24.0
	_hand_row = HBoxContainer.new()
	_hand_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_hand_row.add_theme_constant_override("separation", HAND_GAP)
	_hand_row.custom_minimum_size.y = HAND_CARD_SIZE.y
	box.add_child(_hint_label)
	box.add_child(_notice_label)
	box.add_child(_hand_row)
	return box


func _build_overlays() -> void:
	var draft := _make_overlay(620.0)
	_draft_root = draft.root
	draft.box.add_child(_title_label(DRAFT_TITLE))
	_draft_grid = GridContainer.new()
	_draft_grid.add_theme_constant_override("h_separation", 10)
	_draft_grid.add_theme_constant_override("v_separation", 10)
	draft.box.add_child(_draft_grid)

	var draw_choice := _make_overlay(620.0)
	_draw_root = draw_choice.root
	draw_choice.box.add_child(_title_label(DRAW_TITLE))
	_draw_row = HBoxContainer.new()
	_draw_row.add_theme_constant_override("separation", 16)
	draw_choice.box.add_child(_draw_row)

	var teleport := _make_overlay(560.0)
	_teleport_root = teleport.root
	teleport.box.add_child(_title_label(TELEPORT_TITLE))
	var teleport_text := _wrapping_label(15, TEXT_COLOR)
	teleport_text.text = TELEPORT_TEXT
	teleport.box.add_child(teleport_text)
	var teleport_row := HBoxContainer.new()
	teleport_row.alignment = BoxContainer.ALIGNMENT_CENTER
	teleport_row.add_theme_constant_override("separation", 20)
	_teleport_cancel = _button("ОСТАТЬСЯ", Vector2(200.0, 40.0))
	_teleport_cancel.pressed.connect(_on_teleport_cancel)
	_teleport_confirm = _button("ДА, ТЕЛЕПОРТИРОВАТЬ", Vector2(260.0, 40.0))
	_teleport_confirm.pressed.connect(_on_teleport_confirm)
	teleport_row.add_child(_teleport_cancel)
	teleport_row.add_child(_teleport_confirm)
	teleport.box.add_child(teleport_row)

	var items := _make_overlay(520.0)
	_items_root = items.root
	items.box.add_child(_title_label(ITEMS_TITLE))
	_items_list = ItemList.new()
	_items_list.custom_minimum_size = Vector2(480.0, 220.0)
	items.box.add_child(_items_list)
	_items_empty = _wrapping_label(14, TEXT_COLOR)
	_items_empty.text = ITEMS_EMPTY
	items.box.add_child(_items_empty)
	var items_row := HBoxContainer.new()
	items_row.alignment = BoxContainer.ALIGNMENT_CENTER
	items_row.add_theme_constant_override("separation", 20)
	_items_use = _button("ИСПОЛЬЗОВАТЬ", Vector2(200.0, 40.0))
	_items_use.pressed.connect(_on_items_use)
	var items_close := _button("ЗАКРЫТЬ", Vector2(160.0, 40.0))
	items_close.pressed.connect(_on_items_close)
	items_row.add_child(_items_use)
	items_row.add_child(items_close)
	items.box.add_child(items_row)

	var result := _make_overlay(560.0)
	_result_root = result.root
	_result_title = _label(26, TITLE_COLOR)
	result.box.add_child(_result_title)
	_result_text = _wrapping_label(15, TEXT_COLOR)
	result.box.add_child(_result_text)
	_result_rewards = _wrapping_label(14, TEXT_COLOR)
	result.box.add_child(_result_rewards)
	var continue_button := _button("ПРОДОЛЖИТЬ", Vector2(240.0, 44.0))
	continue_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	continue_button.pressed.connect(_on_result_continue)
	result.box.add_child(continue_button)


func _make_overlay(min_width: float) -> Dictionary:
	var root := Control.new()
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	root.visible = false
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0.0, 0.0, 0.0, 0.62)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	var panel := _panel()
	panel.custom_minimum_size.x = min_width
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	panel.add_child(box)
	add_child(root)
	return {"root": root, "box": box}


func _panel() -> PanelContainer:
	var panel := PanelContainer.new()
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_BG
	style.border_color = PANEL_BORDER
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	style.set_content_margin_all(10)
	panel.add_theme_stylebox_override("panel", style)
	return panel


func _label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _wrapping_label(font_size: int, color: Color) -> Label:
	var label := _label(font_size, color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = LEFT_WIDTH - 40.0
	return label


func _title_label(text: String) -> Label:
	var label := _label(18, TITLE_COLOR)
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return label


func _button(text: String, min_size: Vector2) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = min_size
	return button


func _battle_items(inventory: Array) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for entry in inventory:
		if entry is Dictionary and int(entry.get("item_id", 0)) in RULES.BATTLE_ITEM_IDS:
			result.append({
				"item_id": int(entry["item_id"]),
				"name": RULES.item_name(entry),
				"quantity": int(entry.get("quantity", 1)),
			})
	return result


func _spend_item(item_id: int) -> void:
	for index in _inventory.size():
		if int(_inventory[index]["item_id"]) == item_id:
			_inventory[index]["quantity"] = int(_inventory[index]["quantity"]) - 1
			if int(_inventory[index]["quantity"]) <= 0:
				_inventory.remove_at(index)
			return


func _send(command: Dictionary) -> void:
	if _busy:
		return
	_busy = true
	_last_command = command
	_refresh_all()
	command_requested.emit(command)


func _turn_ready() -> bool:
	return (
		not _busy
		and not _state.is_empty()
		and str(_state.get("phase", "")) == "battle"
		and RULES.result_of(_state).is_empty()
		and str(_state.get("active_side", "")) == "player"
	)


func _overlay_open() -> bool:
	return _draft_root.visible or _draw_root.visible or _teleport_root.visible or _items_root.visible or _result_root.visible


func _can_use(key: String) -> bool:
	if _busy or _state.is_empty() or _overlay_open():
		return false
	match key:
		"inventory":
			return str(_state.get("phase", "")) == "battle" and RULES.result_of(_state).is_empty()
		"move":
			return _turn_ready() and bool(_state.get("can_move", false))
		"cards":
			return _turn_ready() and int(_state.get("cards_played", 0)) < int(_state.get("max_cards", 2))
		"burn":
			return _turn_ready() and not bool(_state.get("burned_this_turn", false))
	return _turn_ready()


func _is_active(key: String) -> bool:
	match key:
		"move":
			return _mode == "move"
		"cards":
			return _mode == "cards" and not _burn_mode
		"burn":
			return _burn_mode
	return false


func _on_button_pressed(key: String) -> void:
	if not _can_use(key):
		return
	if key == "burn":
		_on_burn_pressed()
		return
	if key == "end":
		_mode = ""
		_burn_mode = false
		_clear_selection()
		_send({"type": "end_turn"})
		return
	_cancel_targeting()
	match key:
		"cards":
			_mode = "" if _mode == "cards" else "cards"
			_burn_mode = false
		"move":
			_mode = "" if _mode == "move" else "move"
			_burn_mode = false
		"inventory":
			_mode = ""
			_burn_mode = false
			_open_items()
		"teleport":
			_mode = ""
			_burn_mode = false
			_teleport_root.visible = true
	_clear_selection()
	_refresh_all()


func _on_burn_pressed() -> void:
	if not _turn_ready() or _overlay_open():
		return
	if bool(_state.get("burned_this_turn", false)):
		_show_notice(BURN_ONCE, true)
		_refresh_all()
		return
	if _burn_mode and _selected_index >= 0:
		_send({"type": "burn", "card_index": _selected_index})
		return
	_burn_mode = not _burn_mode
	_mode = "cards" if _burn_mode else ""
	_clear_selection()
	if _burn_mode:
		_show_notice(BURN_HINT)
	_refresh_all()


func _on_hand_pressed(index: int) -> void:
	if not _turn_ready() or _overlay_open():
		return
	var hand: Array = _state.get("hand", [])
	if index < 0 or index >= hand.size():
		return
	var card: Dictionary = hand[index]
	if _burn_mode:
		_selected_index = index
		_transfer_target = ""
		_targeting = false
		_show_notice("Выбрана карта «%s». Нажмите B, чтобы сжечь её" % str(card.get("name", "")))
	elif index == _selected_index:
		if not _targeting:
			_targeting = true
			_transfer_target = ""
	else:
		_targeting = false
		_transfer_target = ""
		if bool(card.get("playable", false)):
			_selected_index = index
		else:
			_selected_index = -1
			_show_notice(str(card.get("reason", "Не хватает ресурса для этой карты")), true)
	_refresh_all()


func _on_choice_pressed(command_type: String, card_key: String) -> void:
	if _busy or card_key.is_empty():
		return
	_send({"type": command_type, "card_key": card_key})


func _open_items() -> void:
	_items_list.clear()
	for item in _inventory:
		_items_list.add_item("%s × %d" % [str(item["name"]), int(item["quantity"])])
	var empty := _inventory.is_empty()
	_items_empty.visible = empty
	_items_list.visible = not empty
	_items_use.disabled = empty
	if not empty:
		_items_list.select(0)
	_items_root.visible = true


func _on_items_use() -> void:
	var selected := _items_list.get_selected_items()
	if selected.is_empty():
		_show_notice(NO_ITEM_SELECTED, true)
		return
	var item: Dictionary = _inventory[selected[0]]
	_items_root.visible = false
	var item_id := int(item["item_id"])
	if item_id == RULES.DAGGER_ITEM_ID:
		_pending_item = item_id
		_show_notice(DAGGER_HINT)
		_refresh_all()
		return
	_send({"type": "item", "item_id": item_id})


func _on_items_close() -> void:
	_items_root.visible = false
	_refresh_all()


func _on_teleport_confirm() -> void:
	_teleport_root.visible = false
	_send({"type": "teleport"})


func _on_teleport_cancel() -> void:
	_teleport_root.visible = false
	_refresh_all()


func _on_result_continue() -> void:
	_result_root.visible = false
	var finished := _finished
	_finished = {}
	finished_confirmed.emit(finished)


func _on_board_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_set_hover((event as InputEventMouseMotion).position)
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		var button_event := event as InputEventMouseButton
		if button_event.button_index == MOUSE_BUTTON_LEFT:
			_on_board_click(button_event.position)
		elif button_event.button_index == MOUSE_BUTTON_RIGHT:
			_cancel_interaction()


func _on_board_mouse_exited() -> void:
	_hover_tile = RULES.NO_TILE
	_hover_unit = {}
	_refresh_unit_info()
	_board.queue_redraw()


func _on_board_resized() -> void:
	_refit_board()
	_board.queue_redraw()


func _set_hover(pos: Vector2) -> void:
	_hover_tile = RULES.tile_at(pos, _tiles(), _center_qr(), _tile_size, _origin)
	_hover_unit = RULES.unit_at_tile(_tiles_units(), _hover_tile)
	_refresh_unit_info()
	_board.queue_redraw()


func _on_board_click(pos: Vector2) -> void:
	if _busy or _state.is_empty() or _overlay_open():
		return
	var tile := RULES.tile_at(pos, _tiles(), _center_qr(), _tile_size, _origin)
	if tile == RULES.NO_TILE:
		return
	var unit := RULES.unit_at_tile(_tiles_units(), tile)
	if _pending_item != 0:
		_use_dagger(unit)
		return
	if _mode == "cards" and _turn_ready() and _targeting:
		_click_target(tile, unit)
		return
	if str(unit.get("side", "")) == "enemy" and _mode != "move":
		_select_enemy(unit)
		return
	if _mode == "move" and _turn_ready():
		_move_to(tile)


func _use_dagger(unit: Dictionary) -> void:
	if str(unit.get("side", "")) != "enemy":
		_show_notice(DAGGER_NEED_ENEMY, true)
		_refresh_all()
		return
	_pending_item = 0
	_send({"type": "item", "item_id": RULES.DAGGER_ITEM_ID, "target": str(unit.get("id", ""))})


func _select_enemy(unit: Dictionary) -> void:
	var unit_id := str(unit.get("id", ""))
	if not _turn_ready() or unit_id == RULES.text_of(_state.get("target")):
		return
	_show_notice("Цель: %s" % str(unit.get("name", "")), false, 1.5)
	_send({"type": "select_target", "target": unit_id})


func _move_to(tile: Vector2i) -> void:
	var reach := RULES.tile_set(_state.get("reachable", []))
	if reach.has(tile):
		_send({"type": "move", "tile": RULES.tile_to_array(tile)})
		return
	var player := RULES.unit_by_id(_tiles_units(), "player")
	if tile != RULES.tile_from_array(player.get("position", [])):
		_show_notice(RULES.move_failed_text(int(_state.get("move_range", 3))), true)
		_refresh_all()


# Клик по полю при выбранной карте: логика та же, что _click_target в оверлее.
func _click_target(tile: Vector2i, unit: Dictionary) -> void:
	var card := _selected_card()
	if card.is_empty():
		_cancel_targeting("Выбор карты сброшен — выберите карту снова")
		_refresh_all()
		return
	var plan := RULES.plan_targeting_click(card, card.get("preview", {}), tile, unit, _transfer_target, _selected_index)
	match str(plan.get("kind", "")):
		"transfer_target":
			_transfer_target = str(plan.get("target", ""))
			_show_notice("Выберите свободный гекс для перемещения существа")
			_refresh_all()
		"play":
			_clear_selection()
			_send(plan.get("command", {}))
		_:
			_show_notice(MISS_HINT)
			_refresh_all()


func _cancel_interaction() -> void:
	if _overlay_open():
		return
	if _pending_item != 0:
		_pending_item = 0
		_show_notice(ITEM_CANCELLED)
	elif _targeting:
		_cancel_targeting(CANCELLED)
	elif _mode != "" or _burn_mode or _selected_index >= 0:
		_mode = ""
		_burn_mode = false
		_clear_selection()
	_refresh_all()


func _cancel_targeting(text: String = "") -> void:
	_clear_selection()
	if not text.is_empty():
		_show_notice(text, false, 1.5)


func _clear_selection() -> void:
	_selected_index = -1
	_targeting = false
	_transfer_target = ""


func _selected_card() -> Dictionary:
	var hand: Array = _state.get("hand", [])
	if _selected_index < 0 or _selected_index >= hand.size():
		return {}
	return hand[_selected_index]


func _show_notice(text: String, is_error := false, seconds := NOTICE_SECONDS) -> void:
	_notice_label.text = text
	_notice_label.add_theme_color_override("font_color", ERROR_COLOR if is_error else NOTICE_COLOR)
	if is_inside_tree():
		_notice_timer.start(seconds)


func _clear_notice() -> void:
	_notice_label.text = ""


func _summon_range() -> int:
	return int(_state.get("summon_range", 2))


func _tiles() -> Array:
	return _state.get("tiles", [])


func _tiles_units() -> Array:
	return _state.get("units", [])


func _center_qr() -> Vector2i:
	var center: Array = _state.get("arena", {}).get("center", [0, 0])
	return Vector2i(int(center[0]), int(center[1]))


func _refit_board() -> void:
	var fit := RULES.fit_board(_tiles(), _center_qr(), _board.size)
	_tile_size = float(fit["size"])
	_origin = fit["origin"]


func _refresh_all() -> void:
	if _state.is_empty():
		return
	if _mode == "move" and not bool(_state.get("can_move", false)):
		_mode = ""
	if _burn_mode and bool(_state.get("burned_this_turn", false)):
		_burn_mode = false
	_banner_title.text = RULES.banner_title(_state)
	_banner_details.text = RULES.details_text(_state)
	_refresh_log()
	_refresh_unit_info()
	_refresh_hand()
	_refresh_hint()
	_refresh_buttons()
	_refresh_overlays()
	_refit_board()
	_board.queue_redraw()


func _refresh_log() -> void:
	var lines := PackedStringArray()
	var log_lines: Array = _state.get("log", [])
	for index in range(maxi(0, log_lines.size() - RULES.MAX_LOG_LINES), log_lines.size()):
		lines.append(str(log_lines[index]))
	_log_label.text = "\n".join(lines)


func _refresh_unit_info() -> void:
	var unit: Dictionary = _hover_unit
	if unit.is_empty():
		unit = RULES.unit_by_id(_tiles_units(), RULES.text_of(_state.get("target")))
	_unit_label.text = RULES.unit_info_text(unit) if not unit.is_empty() else UNIT_EMPTY


func _refresh_hand() -> void:
	_clear_children(_hand_row)
	if _state.is_empty() or not (_mode == "cards" or _burn_mode) or not RULES.result_of(_state).is_empty():
		return
	var hand: Array = _state.get("hand", [])
	for index in hand.size():
		var card: Dictionary = hand[index]
		var button := Button.new()
		button.custom_minimum_size = HAND_CARD_SIZE
		button.text = RULES.hand_card_text(card)
		button.tooltip_text = RULES.card_tooltip(card)
		button.add_theme_font_size_override("font_size", CARD_FONT_SIZE)
		button.modulate = _hand_color(card, index)
		button.pressed.connect(_on_hand_pressed.bind(index))
		_hand_row.add_child(button)


func _hand_color(card: Dictionary, index: int) -> Color:
	if index == _selected_index:
		return Color(1.0, 0.92, 0.45)
	if not bool(card.get("playable", false)) or not _turn_ready():
		return Color(0.6, 0.6, 0.65)
	return Color.WHITE


func _refresh_hint() -> void:
	var hint := ""
	var card := _selected_card()
	if not RULES.result_of(_state).is_empty():
		hint = ""
	elif _pending_item != 0:
		hint = DAGGER_HINT
	elif _burn_mode:
		hint = BURN_HINT
	elif not card.is_empty() and _targeting:
		hint = RULES.targeting_hint(card, _transfer_target, _summon_range())
	elif not card.is_empty():
		hint = SELECTED_HINT
	elif _mode == "cards":
		hint = SELECT_HAND_HINT
	_hint_label.text = hint


func _refresh_buttons() -> void:
	for key in _buttons:
		var button: Button = _buttons[key]
		button.disabled = not _can_use(str(key))
		button.modulate = ACTIVE_COLOR if _is_active(str(key)) else Color.WHITE


func _refresh_overlays() -> void:
	var phase := str(_state.get("phase", ""))
	_draft_root.visible = phase == "draft"
	_draw_root.visible = phase == "draw_choice"
	if _draft_root.visible:
		_fill_choices(_draft_grid, _state.get("draft_cards", []), "draft", DRAFT_CARD_SIZE, DRAFT_COLUMNS)
	if _draw_root.visible:
		_fill_choices(_draw_row, _state.get("draw_choices", []), "draw_choice", DRAW_CARD_SIZE, 2)
	if not _turn_ready():
		_teleport_root.visible = false
	if phase != "battle" or not RULES.result_of(_state).is_empty():
		_items_root.visible = false


func _fill_choices(container: Container, cards: Array, command_type: String, button_size: Vector2, columns: int) -> void:
	_clear_children(container)
	if container is GridContainer:
		(container as GridContainer).columns = columns
	for card in cards:
		if not (card is Dictionary):
			continue
		var button := Button.new()
		button.custom_minimum_size = button_size
		button.text = RULES.hand_card_text(card)
		button.tooltip_text = RULES.card_tooltip(card)
		button.add_theme_font_size_override("font_size", CARD_FONT_SIZE)
		button.pressed.connect(_on_choice_pressed.bind(command_type, str(card.get("key", ""))))
		container.add_child(button)


func _clear_children(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _draw_board() -> void:
	if _state.is_empty() or _tile_size <= 0.0:
		return
	var center := _center_qr()
	var tiles := _tiles()
	var board := RULES.tile_set(tiles)
	var reach := RULES.tile_set(_state.get("reachable", [])) if _mode == "move" else {}
	var obstacles := RULES.tile_set(_state.get("obstacles", []))
	var barriers := RULES.tile_set(_state.get("barriers", []))
	var traps := RULES.tile_set(_state.get("traps", []))
	var grave := RULES.tile_set(_state.get("grave_soil", []))
	var highlights := _highlights(board)
	for value in tiles:
		var tile := RULES.tile_from_array(value)
		var polygon := RULES.hex_polygon(RULES.tile_center(tile, center, _tile_size, _origin), _tile_size)
		var hovered := tile == _hover_tile
		var fill := COLOR_TILE_ODD if (tile.x + tile.y) % 2 == 1 else COLOR_TILE_EVEN
		if grave.has(tile):
			fill = COLOR_GRAVE
		if reach.has(tile):
			fill = COLOR_REACH_HOVER if hovered else COLOR_REACH
		if highlights.tiles.has(tile):
			fill = COLOR_SUMMON_HOVER if hovered else COLOR_SUMMON
		if barriers.has(tile):
			fill = COLOR_BARRIER
		if traps.has(tile):
			fill = COLOR_TRAP
		if obstacles.has(tile):
			fill = COLOR_OBSTACLE
		if highlights.aim.has(tile):
			fill = COLOR_AIM
		if highlights.targets.has(tile):
			fill = highlights.targets[tile]
		_board.draw_colored_polygon(polygon, fill)
		if highlights.splash.has(tile):
			_board.draw_colored_polygon(polygon, COLOR_SPLASH)
		_draw_outline(polygon, COLOR_EDGE, 1.0)
		var neighbors := RULES.hex_neighbors(tile)
		for edge in range(6):
			if not board.has(neighbors[edge]):
				_board.draw_line(polygon[edge], polygon[(edge + 1) % 6], COLOR_BOUNDARY, 3.0)
		if hovered:
			_draw_outline(polygon, COLOR_HOVER, 2.5)
	_draw_units(center)


func _draw_units(center: Vector2i) -> void:
	var font := ThemeDB.fallback_font
	var target_id := RULES.text_of(_state.get("target"))
	for unit in _tiles_units():
		if not (unit is Dictionary):
			continue
		var pos := RULES.tile_center(RULES.tile_from_array(unit.get("position", [])), center, _tile_size, _origin)
		var radius := _tile_size * 0.36
		_board.draw_circle(pos, radius, _unit_color(str(unit.get("side", ""))))
		_board.draw_arc(pos, radius, 0.0, TAU, 24, Color(0.0, 0.0, 0.0, 0.7), 1.5)
		if str(unit.get("id", "")) == target_id:
			_board.draw_arc(pos, radius + 4.0, 0.0, TAU, 28, COLOR_TARGET_RING, 3.0)
		var letter := str(unit.get("name", "?")).substr(0, 1).to_upper()
		var font_size := maxi(10, int(radius * 1.1))
		_board.draw_string(font, pos + Vector2(-radius, font_size * 0.35), letter, HORIZONTAL_ALIGNMENT_CENTER, radius * 2.0, font_size, Color.WHITE)
		var max_hp := maxf(1.0, float(unit.get("max_hp", 1)))
		var ratio := clampf(float(unit.get("hp", 0)) / max_hp, 0.0, 1.0)
		var bar := Rect2(pos.x - radius, pos.y + radius + 3.0, radius * 2.0, 4.0)
		_board.draw_rect(bar, Color(0.12, 0.12, 0.14))
		_board.draw_rect(Rect2(bar.position, Vector2(bar.size.x * ratio, bar.size.y)), Color(0.35, 0.9, 0.45))


# Подсветка целей выбранной карты: для атаки — допустимые гексы и область взрыва под курсором.
func _highlights(board: Dictionary) -> Dictionary:
	var result := {"tiles": {}, "aim": {}, "splash": {}, "targets": {}}
	var card := _selected_card()
	if not _targeting or card.is_empty():
		return result
	var preview: Dictionary = card.get("preview", {})
	match RULES.card_mode(card):
		"transfer":
			if _transfer_target.is_empty():
				result["targets"] = _unit_tiles(preview.get("targets", []))
			else:
				result["tiles"] = RULES.tile_set(preview.get("transfer_tiles", {}).get(_transfer_target, []))
		"attack":
			result["aim"] = RULES.tile_set(preview.get("aim_tiles", []))
			result["splash"] = _splash_tiles(card, board, result["aim"])
		"tile":
			result["tiles"] = RULES.tile_set(preview.get("tiles", []))
		_:
			result["targets"] = _unit_tiles(preview.get("targets", []))
	return result


func _splash_tiles(card: Dictionary, board: Dictionary, aim: Dictionary) -> Dictionary:
	var result := {}
	var center_tile := _hover_tile
	if not aim.has(center_tile) and str(_hover_unit.get("side", "")) == "enemy":
		center_tile = RULES.tile_from_array(_hover_unit.get("position", []))
	if not aim.has(center_tile):
		return result
	var radius := int(card.get("aoe_radius", 0))
	for tile in board.keys():
		if RULES.hex_distance(tile, center_tile) <= radius:
			result[tile] = true
	return result


func _unit_tiles(ids: Array) -> Dictionary:
	var result := {}
	for unit in _tiles_units():
		if unit is Dictionary and str(unit.get("id", "")) in ids:
			var color := COLOR_TARGET_ENEMY if str(unit.get("side", "")) == "enemy" else COLOR_TARGET_ALLY
			result[RULES.tile_from_array(unit.get("position", []))] = color
	return result


func _draw_outline(polygon: PackedVector2Array, color: Color, width: float) -> void:
	var loop := polygon.duplicate()
	loop.append(polygon[0])
	_board.draw_polyline(loop, color, width)


func _unit_color(side: String) -> Color:
	match side:
		"player":
			return COLOR_PLAYER
		"ally":
			return COLOR_ALLY
		"enemy":
			return COLOR_ENEMY
	return COLOR_SUMMON_UNIT
