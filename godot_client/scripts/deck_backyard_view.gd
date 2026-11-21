extends Control

# Задний двор Калоды: экран из deck/ui/renderers/backyard.py и панель чата из deck/ui/chat/panel.py.
# Вид рисует раскладку Python (1920×1080, масштаб 2/3 внутри окна) и сообщает о нажатиях сигналами;
# запросы и действия ведёт мир (deck_world.gd), поэтому сетевого кода здесь нет.

signal tavern_requested
signal profile_requested
signal duel_requested
signal accept_requested
signal duel_row_pressed(offer: Dictionary)
signal group_row_pressed(offer_id: String)
signal compare_requested(offer: Dictionary)
signal accept_offer_requested(offer_id: String)
signal decline_offer_requested(offer_id: String)
signal challenge_requested(character_id: String)
signal chat_send_requested(text: String)
signal profile_stat_requested(stat_name: String, delta: int)
signal profile_level_requested(delta: int)

const RULES := preload("res://scripts/deck_backyard_rules.gd")
const PROFILE_OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")
const STAGE_SCALE := 2.0 / 3.0
const LIST_ORIGIN := Vector2(800.0, 620.0)
const ACTION_WIDTHS := [80.0, 70.0, 88.0]
const ACTION_OFFSETS := [0.0, 86.0, 162.0]
const ACTIONS_TOTAL := 250.0
const ACTION_HINT_GAP := 10.0
const ACTION_TOP := 5.0
const PEOPLE_BUTTON_TOP := 1.0
const MESSAGE_TOP_PAD := 4.0
const MESSAGE_SCROLL_STEP := 52.0
const LABEL_GAP := 8.0

const COLOR_BACKGROUND := Color8(22, 29, 25)
const COLOR_FRAME_FILL := Color8(45, 56, 48, 190)
const COLOR_FRAME_BORDER := Color8(100, 125, 95)
const COLOR_TITLE := Color8(255, 220, 120)
const COLOR_ROW := Color8(35, 42, 38)
const COLOR_GROUP_ROW := Color8(40, 45, 55)
const COLOR_OWN_TEXT := Color8(255, 235, 150)
const COLOR_TEXT := Color8(230, 235, 225)
const COLOR_HINT := Color8(175, 190, 170)
const COLOR_EMPTY := Color8(190, 195, 185)
const COLOR_ERROR := Color8(255, 100, 100)
const COLOR_HOVER := Color8(110, 190, 255)
const COLOR_TAVERN := Color8(110, 75, 50)
const COLOR_INVENTORY := Color8(100, 100, 120)
const COLOR_INVENTORY_BORDER := Color8(150, 150, 170)
const COLOR_DUEL := Color8(150, 95, 55)
const COLOR_GROUP := Color8(75, 95, 135)
const COLOR_OWN_ACTION := Color8(130, 70, 65)
const COLOR_ACCEPT := Color8(70, 145, 95)
const COLOR_COMPARE := Color8(75, 105, 145)
const COLOR_DECLINE := Color8(130, 70, 65)
const COLOR_SCROLL_TRACK := Color8(50, 55, 66)
const COLOR_SCROLL_THUMB := Color8(170, 180, 210)
const COLOR_CHAT_PANEL := Color8(25, 27, 38)
const COLOR_CHAT_BORDER := Color8(60, 65, 80)
const COLOR_DIVIDER := Color8(60, 65, 80)
const COLOR_DIVIDER_ACTIVE := Color8(120, 170, 230)
const COLOR_CHANNEL_SELECTED := Color8(90, 145, 220)
const COLOR_CHANNEL := Color8(55, 58, 72)
const COLOR_INPUT_FILL := Color8(28, 30, 43)
const COLOR_INPUT_BORDER := Color8(70, 75, 90)
const COLOR_INPUT_FOCUS := Color8(100, 150, 220)
const COLOR_INPUT_TEXT := Color8(240, 240, 245)
const COLOR_SEND := Color8(70, 140, 220)
const COLOR_TOGGLE := Color8(75, 105, 155)
const COLOR_PEOPLE := Color8(215, 215, 225)
const COLOR_PEOPLE_AFK := Color8(135, 139, 145)
const COLOR_AFK_CHALLENGE := Color8(91, 63, 50)
const COLOR_AFK_CHALLENGE_TEXT := Color8(228, 207, 174)
const COLOR_ROOM := Color8(255, 220, 120)
const COLOR_MESSAGE := Color8(215, 215, 225)
const COLOR_OWN_MESSAGE := Color8(150, 210, 255)
const COLOR_GOLD_MESSAGE := Color8(220, 195, 130)
const COLOR_TIME := Color8(160, 165, 170)
const COLOR_WHITE := Color8(255, 255, 255)
const COLOR_DISABLED_TEXT := Color8(150, 150, 150)

const FONT_TITLE := 22
const FONT_ROW := 18
const FONT_BUTTON := 18
const FONT_SMALL := 12
const FONT_CHANNEL := 14
const FONT_SEND := 14
const FONT_ROOM := 17
const FONT_PEOPLE := 16
const FONT_MESSAGE := 15
const FONT_ERROR := 18

var _stage: Control
var _duel_area: Control
var _group_area: Control
var _people_area: Control
var _messages_area: Control
var _chat_input: LineEdit
var _tavern_button: Button
var _inventory_button: Button
var _duel_button: Button
var _accept_button: Button
var _channel_buttons: Array[Button] = []
var _toggle_button: Button
var _send_button: Button
var _collapsed_button: Button
var _profile
var _layer: Control
var _row_buttons: Array = []
var _model: Dictionary = {}
var _model_version := 0
var _message := ""
var _active := false
var _collapsed := false
var _divider_x := 0.0
var _dragging_divider := false
var _duel_scroll := 0
var _group_scroll := 0
var _people_scroll := 0
var _message_scroll := 0.0
var _message_follow := true
var _message_lines: Array = []
var _message_total := 0.0
var _message_key := ""
var _hovered_duel := -1
var _hovered_people := -1


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_divider_x = RULES.default_divider_x()
	_stage = Control.new()
	_stage.size = RULES.DESIGN_SIZE
	_stage.scale = Vector2(STAGE_SCALE, STAGE_SCALE)
	_stage.mouse_filter = Control.MOUSE_FILTER_STOP
	_stage.draw.connect(_draw_stage.bind(_stage))
	_stage.gui_input.connect(_on_stage_input)
	add_child(_stage)
	_duel_area = _make_area(RULES.DUEL_LIST, _draw_duel_area, _on_duel_area_input)
	_group_area = _make_area(RULES.GROUP_LIST, _draw_group_area, _on_group_area_input)
	_people_area = _make_area(Rect2(), _draw_people_area, _on_people_area_input)
	_messages_area = _make_area(Rect2(), _draw_messages_area, _on_messages_area_input)
	_build_buttons()
	_build_chat_input()
	_profile = PROFILE_OVERLAY_SCRIPT.new()
	_profile.stat_requested.connect(profile_stat_requested.emit)
	_profile.level_requested.connect(profile_level_requested.emit)
	add_child(_profile)


func _ready() -> void:
	_apply_chat_layout()


func _process(_delta: float) -> void:
	if not _active:
		return
	_hovered_duel = _hovered_row(_duel_area, _duel_scroll, RULES.ROW_STEP, RULES.ROW_STEP)
	_hovered_people = _hovered_row(_people_area, _people_scroll, RULES.CHAT_PEOPLE_ROW_HEIGHT, RULES.CHAT_PEOPLE_ROW_HEIGHT)
	_refresh_row_buttons()
	_stage.queue_redraw()
	_duel_area.queue_redraw()
	_group_area.queue_redraw()
	_people_area.queue_redraw()
	_messages_area.queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), COLOR_BACKGROUND)


func set_active(active: bool) -> void:
	_active = active
	visible = active
	if active:
		_stage.queue_redraw()


func set_message(text: String) -> void:
	if text == _message:
		return
	_message = text
	_stage.queue_redraw()


func chat_input() -> LineEdit:
	return _chat_input


func is_profile_open() -> bool:
	return _profile.is_open()


func open_profile(profile: Dictionary) -> void:
	_profile.open(profile)


func update_profile(profile: Dictionary) -> void:
	_profile.update_profile(profile)


func dock_list(list: Control) -> void:
	if list.get_parent() == _stage:
		return
	list.reparent(_stage, false)
	list.position = LIST_ORIGIN
	list.size = RULES.GROUP_BUTTON.size
	list.add_theme_constant_override("separation", 0)


func undock_list(list: Control, home: Control, separation: int) -> void:
	if list.get_parent() != _stage:
		return
	if is_instance_valid(_layer):
		_layer.queue_free()
	_layer = null
	_row_buttons.clear()
	list.reparent(home, false)
	list.add_theme_constant_override("separation", separation)


func build_layer(model: Dictionary) -> Control:
	if is_instance_valid(_layer):
		_layer.queue_free()
	_layer = Control.new()
	_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_row_buttons.clear()
	var own_id := str(model.get("own_id", ""))
	var duel_list: Array = model.get("duel_offers", [])
	for index in duel_list.size():
		var offer: Dictionary = duel_list[index]
		if RULES.is_own_offer(offer, own_id):
			continue
		_add_row_button("duel", index, 0, RULES.ROW_ACTION_COMPARE, COLOR_COMPARE, offer, "", false)
		_add_row_button("duel", index, 1, RULES.ROW_ACTION_ACCEPT, COLOR_ACCEPT, offer, "", false)
		_add_row_button("duel", index, 2, RULES.ROW_ACTION_DECLINE, COLOR_DECLINE, offer, "", false)
	var people: Array = RULES.people_rows(model.get("occupants", []), own_id)
	for index in people.size():
		var person: Dictionary = people[index]
		if bool(person["self"]):
			continue
		var afk := bool(person["afk"])
		var text: String = RULES.AFK_CHALLENGE_TEXT if afk else RULES.CHALLENGE_TEXT
		_add_row_button("people", index, 0, text, COLOR_AFK_CHALLENGE if afk else COLOR_TOGGLE, {}, str(person["character_id"]), afk)
	set_model(model)
	return _layer


func style_group_button(button: Button, own_group: bool) -> void:
	_style_button(button, COLOR_OWN_ACTION if own_group else COLOR_GROUP, FONT_BUTTON)
	for color_name in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(color_name, Color(1.0, 1.0, 1.0, 0.0))
	var caption := Label.new()
	caption.text = button.text
	caption.uppercase = true
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caption.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	caption.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	caption.add_theme_font_size_override("font_size", FONT_BUTTON)
	caption.add_theme_color_override("font_color", COLOR_WHITE)
	button.add_child(caption)


func set_model(model: Dictionary) -> void:
	_model = model
	_model_version += 1
	_message_key = ""
	_clamp_scrolls()
	_apply_model_buttons()
	_layout_row_buttons()
	_stage.queue_redraw()


func _make_area(rect: Rect2, painter: Callable, input: Callable) -> Control:
	var area := Control.new()
	area.position = rect.position
	area.size = rect.size
	area.clip_contents = true
	area.mouse_filter = Control.MOUSE_FILTER_STOP
	area.draw.connect(painter.bind(area))
	area.gui_input.connect(input.bind(area))
	_stage.add_child(area)
	return area


func _build_buttons() -> void:
	_tavern_button = _make_button(RULES.TAVERN_TEXT, RULES.TAVERN_BUTTON, COLOR_TAVERN, FONT_BUTTON)
	_tavern_button.pressed.connect(tavern_requested.emit)
	_inventory_button = _make_button("", RULES.INVENTORY_BUTTON, COLOR_INVENTORY, FONT_BUTTON)
	_inventory_button.add_theme_stylebox_override("normal", _box_style(COLOR_INVENTORY, 0.0, COLOR_INVENTORY_BORDER, 2))
	_inventory_button.add_theme_stylebox_override("hover", _box_style(COLOR_INVENTORY, 0.0, COLOR_INVENTORY_BORDER, 2))
	_inventory_button.pressed.connect(profile_requested.emit)
	var icon := Control.new()
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	icon.draw.connect(_draw_inventory_icon.bind(icon))
	_inventory_button.add_child(icon)
	_duel_button = _make_button(RULES.DUEL_TEXT, RULES.DUEL_BUTTON, COLOR_DUEL, FONT_BUTTON)
	_duel_button.pressed.connect(duel_requested.emit)
	_accept_button = _make_button(RULES.ACCEPT_TEXT, RULES.ACCEPT_BUTTON, COLOR_ACCEPT, FONT_BUTTON)
	_accept_button.pressed.connect(accept_requested.emit)
	_accept_button.visible = false
	for index in RULES.CHAT_CHANNELS.size():
		var channel_button := _make_button(str(RULES.CHAT_CHANNELS[index]), Rect2(), COLOR_CHANNEL_SELECTED if index == 0 else COLOR_CHANNEL, FONT_CHANNEL)
		channel_button.disabled = index == 1
		_channel_buttons.append(channel_button)
	_toggle_button = _make_button(RULES.CHAT_TOGGLE_TEXT, Rect2(), COLOR_TOGGLE, FONT_SMALL)
	_toggle_button.pressed.connect(_toggle_chat)
	_send_button = _make_button(RULES.CHAT_SEND_TEXT, Rect2(), COLOR_SEND, FONT_SEND)
	_send_button.pressed.connect(_submit_chat)
	_collapsed_button = _make_button(RULES.CHAT_COLLAPSED_TEXT, RULES.collapsed_toggle_rect(), COLOR_TOGGLE, FONT_SMALL)
	_collapsed_button.pressed.connect(_toggle_chat)


func _build_chat_input() -> void:
	_chat_input = LineEdit.new()
	_chat_input.max_length = 300
	_chat_input.caret_blink = true
	_chat_input.add_theme_stylebox_override("normal", _field_style(COLOR_INPUT_BORDER))
	_chat_input.add_theme_stylebox_override("focus", _field_style(COLOR_INPUT_FOCUS))
	_chat_input.add_theme_color_override("font_color", COLOR_INPUT_TEXT)
	_chat_input.add_theme_font_size_override("font_size", FONT_MESSAGE)
	_chat_input.text_submitted.connect(_on_chat_text_submitted)
	_stage.add_child(_chat_input)


func _field_style(border: Color) -> StyleBoxFlat:
	var style := _box_style(COLOR_INPUT_FILL, 5.0, border, 1)
	style.content_margin_left = 8.0
	style.content_margin_right = 8.0
	style.content_margin_top = 0.0
	style.content_margin_bottom = 0.0
	return style


func _make_button(text: String, rect: Rect2, color: Color, font_size: int) -> Button:
	var button := Button.new()
	button.text = text
	button.position = rect.position
	button.size = rect.size
	button.focus_mode = Control.FOCUS_NONE
	button.clip_text = true
	_style_button(button, color, font_size)
	_stage.add_child(button)
	return button


func _style_button(button: Button, color: Color, font_size: int) -> void:
	button.add_theme_stylebox_override("normal", _box_style(color, 10.0))
	button.add_theme_stylebox_override("hover", _box_style(COLOR_HOVER, 10.0))
	button.add_theme_stylebox_override("pressed", _box_style(COLOR_HOVER, 10.0))
	button.add_theme_stylebox_override("focus", _box_style(Color(0.0, 0.0, 0.0, 0.0), 10.0))
	button.add_theme_stylebox_override("disabled", _box_style(color.darkened(0.45), 10.0))
	for color_name in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		button.add_theme_color_override(color_name, COLOR_WHITE)
	button.add_theme_color_override("font_disabled_color", COLOR_DISABLED_TEXT)
	button.add_theme_font_size_override("font_size", font_size)


func _box_style(color: Color, radius: float, border := Color(0.0, 0.0, 0.0, 0.0), border_width := 0) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(int(radius))
	style.set_border_width_all(border_width)
	style.border_color = border
	return style


func _apply_model_buttons() -> void:
	var own_application: Dictionary = _model.get("my_application", {})
	_duel_button.text = RULES.duel_button_title(own_application)
	_style_button(_duel_button, COLOR_OWN_ACTION if not own_application.is_empty() else COLOR_DUEL, FONT_BUTTON)
	var incoming := RULES.incoming_offer(str(_model.get("selected_offer_id", "")), _model.get("duel_offers", []), own_application, str(_model.get("own_id", "")))
	_accept_button.visible = not incoming.is_empty()


func _send_width() -> float:
	return maxf(RULES.CHAT_SEND_WIDTH, RULES.text_width(get_theme_default_font(), RULES.CHAT_SEND_TEXT, FONT_SEND) + 16.0)


func _apply_chat_layout() -> void:
	var layout: Dictionary = RULES.chat_layout(_divider_x, _send_width())
	var divider: Rect2 = layout["divider"]
	_divider_x = divider.position.x
	var messages: Rect2 = layout["messages"]
	_messages_area.position = messages.position
	_messages_area.size = messages.size
	var people: Rect2 = layout["people"]
	_people_area.position = people.position
	_people_area.size = people.size
	var field: Rect2 = layout["field"]
	var field_height := maxf(field.size.y, _chat_input.get_combined_minimum_size().y)
	_chat_input.position = field.position
	_chat_input.size = Vector2(field.size.x, field_height)
	var send: Rect2 = layout["send"]
	_send_button.position = send.position
	_send_button.size = Vector2(send.size.x, field_height)
	var toggle: Rect2 = layout["toggle"]
	_toggle_button.position = toggle.position
	_toggle_button.size = toggle.size
	var channels: Array = layout["channels"]
	for index in _channel_buttons.size():
		var channel_rect: Rect2 = channels[index]
		_channel_buttons[index].position = channel_rect.position
		_channel_buttons[index].size = channel_rect.size
	_message_key = ""
	_set_chat_visible(not _collapsed)
	_layout_row_buttons()
	_stage.queue_redraw()


func _set_chat_visible(shown: bool) -> void:
	_messages_area.visible = shown
	_people_area.visible = shown
	_chat_input.visible = shown
	_send_button.visible = shown
	_toggle_button.visible = shown
	for channel_button in _channel_buttons:
		channel_button.visible = shown
	_collapsed_button.visible = not shown


func _toggle_chat() -> void:
	_collapsed = not _collapsed
	_apply_chat_layout()


func _submit_chat() -> void:
	chat_send_requested.emit(_chat_input.text)


func _on_chat_text_submitted(text: String) -> void:
	chat_send_requested.emit(text)


func _add_row_button(kind: String, row: int, slot: int, text: String, color: Color, offer: Dictionary, character_id: String, always: bool) -> void:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.clip_text = true
	button.visible = false
	_style_button(button, color, FONT_SMALL)
	if always:
		button.add_theme_color_override("font_color", COLOR_AFK_CHALLENGE_TEXT)
	if kind == "people":
		button.pressed.connect(challenge_requested.emit.bind(character_id))
	elif slot == 0:
		button.pressed.connect(compare_requested.emit.bind(offer))
	elif slot == 1:
		button.pressed.connect(accept_offer_requested.emit.bind(str(offer.get("id", ""))))
	else:
		button.pressed.connect(decline_offer_requested.emit.bind(str(offer.get("id", ""))))
	_layer.add_child(button)
	_row_buttons.append({"button": button, "kind": kind, "row": row, "slot": slot, "always": always, "in_view": false})


func _duel_actions_left(font: Font) -> float:
	var hint_width := RULES.text_width(font, RULES.DUEL_HINT, FONT_ROW)
	return RULES.DUEL_LIST.end.x - RULES.ROW_PADDING - hint_width - ACTION_HINT_GAP - ACTIONS_TOTAL


func _layout_row_buttons() -> void:
	var font := get_theme_default_font()
	var duel_left := _duel_actions_left(font)
	var duel_visible := RULES.visible_count(RULES.DUEL_LIST.size.y, RULES.ROW_STEP)
	var people: Rect2 = RULES.chat_layout(_divider_x, _send_width())["people"]
	var people_visible := RULES.visible_count(people.size.y, RULES.CHAT_PEOPLE_ROW_HEIGHT)
	for entry in _row_buttons:
		var button: Button = entry["button"]
		if not is_instance_valid(button):
			continue
		var row: int = entry["row"]
		var target := Vector2.ZERO
		if entry["kind"] == "duel":
			var slot: int = entry["slot"]
			entry["in_view"] = row >= _duel_scroll and row < _duel_scroll + duel_visible
			button.size = Vector2(ACTION_WIDTHS[slot], RULES.ROW_HEIGHT - ACTION_TOP * 2.0)
			target = Vector2(duel_left + ACTION_OFFSETS[slot], RULES.DUEL_LIST.position.y + (row - _duel_scroll) * RULES.ROW_STEP + ACTION_TOP)
		else:
			entry["in_view"] = row >= _people_scroll and row < _people_scroll + people_visible
			button.size = RULES.CHAT_PEOPLE_BUTTON_SIZE
			target = Vector2(people.end.x - RULES.CHAT_PEOPLE_BUTTON_RIGHT, people.position.y + (row - _people_scroll) * RULES.CHAT_PEOPLE_ROW_HEIGHT + PEOPLE_BUTTON_TOP)
		button.position = target - LIST_ORIGIN
		button.visible = false


func _refresh_row_buttons() -> void:
	for entry in _row_buttons:
		var button: Button = entry["button"]
		if not is_instance_valid(button):
			continue
		var hovered: bool
		if entry["kind"] == "duel":
			hovered = _hovered_duel == int(entry["row"])
		else:
			hovered = _hovered_people == int(entry["row"])
		button.visible = bool(entry["in_view"]) and (bool(entry["always"]) or hovered)


func _hovered_row(area: Control, scroll: int, step: float, row_height: float) -> int:
	if area == null or not area.is_visible_in_tree():
		return -1
	var local := area.get_local_mouse_position()
	if not Rect2(Vector2.ZERO, area.size).has_point(local):
		return -1
	return RULES.row_index_at(local.y, scroll, step, row_height)


func _clamp_scrolls() -> void:
	var duel_count: int = _model.get("duel_offers", []).size()
	var group_count: int = _model.get("group_offers", []).size()
	var people_count := RULES.people_rows(_model.get("occupants", []), str(_model.get("own_id", ""))).size()
	_duel_scroll = RULES.clamp_scroll(_duel_scroll, duel_count, RULES.visible_count(RULES.DUEL_LIST.size.y, RULES.ROW_STEP))
	_group_scroll = RULES.clamp_scroll(_group_scroll, group_count, RULES.visible_count(RULES.GROUP_LIST.size.y, RULES.ROW_STEP))
	var people: Rect2 = RULES.chat_layout(_divider_x, _send_width())["people"]
	_people_scroll = RULES.clamp_scroll(_people_scroll, people_count, RULES.visible_count(people.size.y, RULES.CHAT_PEOPLE_ROW_HEIGHT))


func _wheel_direction(event: InputEvent) -> int:
	if not event is InputEventMouseButton or not event.pressed:
		return 0
	if event.button_index == MOUSE_BUTTON_WHEEL_UP:
		return 1
	if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		return -1
	return 0


func _on_stage_input(event: InputEvent) -> void:
	if not event is InputEventMouse:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			var divider: Rect2 = RULES.chat_layout(_divider_x, _send_width())["divider"]
			if not _collapsed and divider.grow_individual(3.0, 0.0, 3.0, 0.0).has_point(event.position):
				_dragging_divider = true
				_stage.accept_event()
		else:
			_dragging_divider = false
	elif event is InputEventMouseMotion and _dragging_divider:
		_divider_x = event.position.x - RULES.CHAT_DIVIDER_WIDTH / 2.0
		_apply_chat_layout()


func _on_duel_area_input(event: InputEvent, area: Control) -> void:
	var direction := _wheel_direction(event)
	var offers: Array = _model.get("duel_offers", [])
	if direction != 0:
		_duel_scroll = RULES.clamp_scroll(_duel_scroll - direction, offers.size(), RULES.visible_count(area.size.y, RULES.ROW_STEP))
		_layout_row_buttons()
		area.queue_redraw()
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		var index := RULES.row_index_at(event.position.y, _duel_scroll, RULES.ROW_STEP, RULES.ROW_HEIGHT)
		if index >= 0 and index < offers.size():
			duel_row_pressed.emit(offers[index])


func _on_group_area_input(event: InputEvent, area: Control) -> void:
	var direction := _wheel_direction(event)
	var groups: Array = _model.get("group_offers", [])
	if direction != 0:
		_group_scroll = RULES.clamp_scroll(_group_scroll - direction, groups.size(), RULES.visible_count(area.size.y, RULES.ROW_STEP))
		area.queue_redraw()
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		var index := RULES.row_index_at(event.position.y, _group_scroll, RULES.ROW_STEP, RULES.ROW_HEIGHT)
		if index >= 0 and index < groups.size():
			group_row_pressed.emit(str(groups[index].get("id", "")))


func _on_people_area_input(event: InputEvent, area: Control) -> void:
	var direction := _wheel_direction(event)
	if direction == 0:
		return
	var count := RULES.people_rows(_model.get("occupants", []), str(_model.get("own_id", ""))).size()
	_people_scroll = RULES.clamp_scroll(_people_scroll - direction, count, RULES.visible_count(area.size.y, RULES.CHAT_PEOPLE_ROW_HEIGHT))
	_layout_row_buttons()
	area.queue_redraw()


func _on_messages_area_input(event: InputEvent, area: Control) -> void:
	var direction := _wheel_direction(event)
	if direction == 0:
		return
	_message_scroll = clampf(_message_scroll - direction * MESSAGE_SCROLL_STEP, 0.0, RULES.message_max_scroll(_message_total, area.size.y))
	_message_follow = false
	area.queue_redraw()


func _draw_stage(canvas: Control) -> void:
	canvas.draw_style_box(_box_style(COLOR_FRAME_FILL, 8.0, COLOR_FRAME_BORDER, 2), RULES.APPLICATION_FRAME)
	_put_text(canvas, RULES.TITLE_POS, RULES.DUEL_TITLE, FONT_TITLE, COLOR_TITLE)
	_put_text(canvas, RULES.GROUP_LABEL_POS, RULES.GROUP_TITLE, FONT_ROW, COLOR_TITLE)
	var now := _now()
	var duel_timer := RULES.application_timer_text(_model.get("my_application", {}), now)
	_put_centered(canvas, RULES.DUEL_BUTTON.get_center().x, RULES.TIMER_TOP, duel_timer, FONT_ROW, COLOR_ERROR)
	var group_timer := RULES.group_timer_text(_model.get("own_group", {}), now)
	_put_centered(canvas, RULES.GROUP_BUTTON.get_center().x, RULES.TIMER_TOP, group_timer, FONT_ROW, COLOR_ERROR)
	_put_text(canvas, RULES.ERROR_POS, _message, FONT_ERROR, COLOR_ERROR)
	if not _collapsed:
		_draw_chat_frame(canvas)


func _draw_chat_frame(canvas: Control) -> void:
	var layout: Dictionary = RULES.chat_layout(_divider_x, _send_width())
	var panel: Rect2 = layout["panel"]
	canvas.draw_style_box(_box_style(COLOR_CHAT_PANEL, 8.0, COLOR_CHAT_BORDER, 2), panel)
	var divider: Rect2 = layout["divider"]
	var hovered := _stage.get_local_mouse_position()
	var active := _dragging_divider or divider.grow_individual(3.0, 0.0, 3.0, 0.0).has_point(hovered)
	canvas.draw_style_box(_box_style(COLOR_DIVIDER_ACTIVE if active else COLOR_DIVIDER, 3.0), divider)
	_put_text(canvas, layout["room_pos"], RULES.CHAT_ROOM_TITLE, FONT_ROOM, COLOR_ROOM)


func _draw_inventory_icon(icon: Control) -> void:
	icon.draw_rect(Rect2(14.0, 20.0, 22.0, 18.0), Color8(176, 132, 78))
	icon.draw_rect(Rect2(14.0, 20.0, 22.0, 18.0), Color8(110, 80, 45), false, 1.5)
	icon.draw_rect(Rect2(14.0, 14.0, 22.0, 7.0), Color8(200, 160, 100))
	icon.draw_rect(Rect2(24.0, 14.0, 2.0, 24.0), Color8(230, 205, 150))


func _draw_duel_area(area: Control) -> void:
	var font := get_theme_default_font()
	var offers: Array = _model.get("duel_offers", [])
	if offers.is_empty():
		_put_text(area, Vector2(0.0, RULES.ROW_TEXT_TOP), RULES.EMPTY_TEXT, FONT_ROW, COLOR_EMPTY)
		return
	var now := _now()
	var own_id := str(_model.get("own_id", ""))
	var hint_width := RULES.text_width(font, RULES.DUEL_HINT, FONT_ROW)
	var hint_left := area.size.x - RULES.ROW_PADDING - hint_width - LABEL_GAP
	var actions_left := _duel_actions_left(font) - RULES.DUEL_LIST.position.x - LABEL_GAP
	for index in offers.size():
		var top := (index - _duel_scroll) * RULES.ROW_STEP
		if top + RULES.ROW_HEIGHT < 0.0 or top >= area.size.y:
			continue
		var offer: Dictionary = offers[index]
		var label := RULES.duel_label(offer, own_id, now)
		var reserve_actions := not RULES.is_own_offer(offer, own_id) and index == _hovered_duel
		var label_right := actions_left if reserve_actions else hint_left
		area.draw_style_box(_box_style(COLOR_ROW, 5.0), Rect2(0.0, top, area.size.x, RULES.ROW_HEIGHT))
		var text := RULES.fit_text(font, str(label["text"]), FONT_ROW, label_right - RULES.ROW_PADDING)
		_put_text(area, Vector2(RULES.ROW_PADDING, top + RULES.ROW_TEXT_TOP), text, FONT_ROW, COLOR_OWN_TEXT if bool(label["highlight"]) else COLOR_TEXT)
		_put_text(area, Vector2(area.size.x - RULES.ROW_PADDING - hint_width, top + RULES.ROW_TEXT_TOP), RULES.DUEL_HINT, FONT_ROW, COLOR_HINT)
	_draw_scrollbar(area, offers.size(), RULES.visible_count(area.size.y, RULES.ROW_STEP), _duel_scroll)


func _draw_group_area(area: Control) -> void:
	var font := get_theme_default_font()
	var groups: Array = _model.get("group_offers", [])
	if groups.is_empty():
		_put_text(area, Vector2(0.0, RULES.ROW_TEXT_TOP), RULES.EMPTY_TEXT, FONT_ROW, COLOR_EMPTY)
		return
	var hint_width := RULES.text_width(font, RULES.GROUP_HINT, FONT_ROW)
	var label_width := area.size.x - RULES.ROW_PADDING * 2.0 - hint_width - LABEL_GAP
	for index in groups.size():
		var top := (index - _group_scroll) * RULES.ROW_STEP
		if top + RULES.ROW_HEIGHT < 0.0 or top >= area.size.y:
			continue
		area.draw_style_box(_box_style(COLOR_GROUP_ROW, 5.0), Rect2(0.0, top, area.size.x, RULES.ROW_HEIGHT))
		var text := RULES.fit_text(font, RULES.group_label(groups[index]), FONT_ROW, label_width)
		_put_text(area, Vector2(RULES.ROW_PADDING, top + RULES.ROW_TEXT_TOP), text, FONT_ROW, COLOR_TEXT)
		_put_text(area, Vector2(area.size.x - RULES.ROW_PADDING - hint_width, top + RULES.ROW_TEXT_TOP), RULES.GROUP_HINT, FONT_ROW, COLOR_HINT)
	_draw_scrollbar(area, groups.size(), RULES.visible_count(area.size.y, RULES.ROW_STEP), _group_scroll)


func _draw_people_area(area: Control) -> void:
	var font := get_theme_default_font()
	var people: Array = RULES.people_rows(_model.get("occupants", []), str(_model.get("own_id", "")))
	var width := area.size.x
	var height := area.size.y
	area.draw_style_box(_box_style(COLOR_SCROLL_TRACK, 3.0), Rect2(width - 8.0, 4.0, 4.0, height - 8.0))
	var visible_rows := RULES.visible_count(height, RULES.CHAT_PEOPLE_ROW_HEIGHT)
	for index in people.size():
		var top := (index - _people_scroll) * RULES.CHAT_PEOPLE_ROW_HEIGHT
		if top + RULES.CHAT_PEOPLE_ROW_HEIGHT <= 0.0 or top >= height:
			continue
		var person: Dictionary = people[index]
		var afk := bool(person["afk"])
		var has_button := not bool(person["self"]) and (afk or index == _hovered_people)
		var right_limit := width - RULES.CHAT_PEOPLE_BUTTON_RIGHT - 6.0 if has_button else width - 8.0
		var text := RULES.fit_text(font, str(person["label"]), FONT_PEOPLE, right_limit - RULES.CHAT_PEOPLE_TEXT_LEFT)
		_put_text(area, Vector2(RULES.CHAT_PEOPLE_TEXT_LEFT, top + 4.0), text, FONT_PEOPLE, COLOR_PEOPLE_AFK if afk else COLOR_PEOPLE)
	var max_scroll := people.size() - visible_rows
	if max_scroll > 0:
		var thumb_height := maxf(18.0, floorf(float(visible_rows) / people.size() * (height - 14.0)))
		var thumb_y := 7.0 + floorf(float(_people_scroll) / max_scroll * (height - 14.0 - thumb_height))
		area.draw_style_box(_box_style(COLOR_SCROLL_THUMB, 3.0), Rect2(width - 8.0, thumb_y, 4.0, thumb_height))


func _draw_messages_area(area: Control) -> void:
	var font := get_theme_default_font()
	var width := area.size.x
	var height := area.size.y
	var own_id := str(_model.get("own_id", ""))
	var key := "%d:%d" % [int(width), _model_version]
	if key != _message_key:
		_layout_messages(font, RULES.visible_messages(_model.get("messages", [])), own_id, width - 4.0)
		_message_key = key
	var max_scroll := RULES.message_max_scroll(_message_total, height)
	if _message_follow:
		_message_scroll = max_scroll
	_message_scroll = clampf(_message_scroll, 0.0, max_scroll)
	for entry in _message_lines:
		var top: float = MESSAGE_TOP_PAD + float(entry["top"]) - _message_scroll
		if top + float(entry["height"]) < 0.0 or top > height:
			continue
		var lines: Array = entry["lines"]
		for line_index in lines.size():
			var line_top := top + line_index * RULES.CHAT_LINE_HEIGHT
			if line_index == 0:
				_put_text(area, Vector2(0.0, line_top), str(entry["time"]), FONT_MESSAGE, COLOR_TIME)
				_put_text(area, Vector2(float(entry["time_width"]), line_top), str(lines[line_index]), FONT_MESSAGE, entry["color"])
			else:
				_put_text(area, Vector2(0.0, line_top), str(lines[line_index]), FONT_MESSAGE, entry["color"])
	if max_scroll > 0.0:
		area.draw_style_box(_box_style(COLOR_SCROLL_TRACK, 3.0), Rect2(width - 8.0, 4.0, 4.0, height - 8.0))
		var thumb_height := maxf(18.0, floorf(height / maxf(1.0, height + max_scroll) * (height - 10.0)))
		var thumb_y := 7.0 + floorf(_message_scroll / max_scroll * (height - 14.0 - thumb_height))
		area.draw_style_box(_box_style(COLOR_SCROLL_THUMB, 3.0), Rect2(width - 8.0, thumb_y, 4.0, thumb_height))


func _layout_messages(font: Font, messages: Array, own_id: String, max_width: float) -> void:
	_message_lines.clear()
	var y := 0.0
	for message in messages:
		var parts: Dictionary = RULES.message_parts(message, own_id)
		var time_text := str(parts["time"])
		var time_width := RULES.text_width(font, time_text, FONT_MESSAGE)
		var lines := RULES.wrap_text(font, str(parts["body"]), FONT_MESSAGE, max_width - time_width, max_width)
		var height := float(lines.size()) * RULES.CHAT_LINE_HEIGHT
		var color := COLOR_GOLD_MESSAGE if bool(parts["gold"]) else (COLOR_OWN_MESSAGE if bool(parts["own"]) else COLOR_MESSAGE)
		_message_lines.append({"lines": lines, "top": y, "height": height, "time": time_text, "time_width": time_width, "color": color})
		y += height + RULES.CHAT_LINE_GAP
	_message_total = maxf(0.0, y - RULES.CHAT_LINE_GAP)


func _draw_scrollbar(area: Control, item_count: int, visible_rows: int, scroll: int) -> void:
	if item_count <= visible_rows:
		return
	var track := Rect2(area.size.x - 6.0, 0.0, 4.0, area.size.y)
	area.draw_style_box(_box_style(COLOR_SCROLL_TRACK, 3.0), track)
	area.draw_style_box(_box_style(COLOR_SCROLL_THUMB, 3.0), RULES.scrollbar_thumb(track, item_count, visible_rows, scroll))


func _now() -> float:
	return float(_model.get("now", Time.get_unix_time_from_system()))


func _put_centered(canvas: Control, center_x: float, top: float, text: String, font_size: int, color: Color) -> void:
	if text.is_empty():
		return
	var width := RULES.text_width(get_theme_default_font(), text, font_size)
	_put_text(canvas, Vector2(center_x - width / 2.0, top), text, font_size, color)


func _put_text(canvas: Control, pos: Vector2, text: String, font_size: int, color: Color) -> void:
	if text.is_empty():
		return
	var font := get_theme_default_font()
	canvas.draw_string(font, Vector2(pos.x, pos.y + font.get_ascent(font_size)), text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size, color)
