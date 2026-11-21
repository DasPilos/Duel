extends PanelContainer

signal message_submitted(text: String, recipient_user_id: int)
signal player_menu_requested(player: Dictionary, global_point: Vector2)

const LOBBY_FORMAT := preload("res://scripts/lobby_format.gd")
const TABS := ["Общий", "Личный"]
# Базовые единицы 1280×720. При окне 1920×1080 (масштаб 1.5) чат 870×390 px, отступ снизу около 10 px.
const PANEL_SIZE := Vector2(580, 260)
const COLLAPSED_SIZE := Vector2(64, 34)
const BOTTOM_MARGIN := 7.0
const PEOPLE_WIDTH := 116
const FONT_SMALL := 10
const FONT_TEXT := 11
const ONLINE_COLOR := Color8(140, 224, 156)
const ROW_HOVER_COLOR := Color8(60, 66, 88, 200)
const PANEL_BACKGROUND := Color8(22, 24, 34, 166)
const PANEL_BORDER := Color8(90, 100, 130)
const TAB_ACTIVE := Color8(90, 145, 220)
const TAB_IDLE := Color8(55, 58, 72)
const INPUT_BACKGROUND := Color8(28, 30, 43)
const INPUT_BORDER := Color8(70, 75, 90)
const INPUT_FOCUS_BORDER := Color8(100, 150, 220)
const SEND_COLOR := Color8(70, 140, 220)
const OWN_NAME_COLOR := Color8(150, 210, 255)
const OTHER_TEXT_COLOR := Color8(215, 215, 225)
const WHISPER_COLOR := Color8(235, 190, 255)
const TIME_COLOR := Color8(160, 165, 170)
const ERROR_COLOR := Color8(255, 120, 100)
const TARGET_COLOR := Color8(255, 220, 120)

var _tab := "Общий"
var _own_user_id := 0
var _players: Array = []
var _messages: Array = []
var _whisper_target: Dictionary = {}
var _status_text := ""
var _status_is_error := true
var _collapsed := false
var _tab_buttons: Dictionary = {}
var _collapse_button: Button
var _body: HBoxContainer
var _log: RichTextLabel
var _status: Label
var _input: LineEdit
var _players_box: VBoxContainer
var _players_title: Label
var _players_signature := ""


func _init() -> void:
	custom_minimum_size = PANEL_SIZE
	anchor_left = 0.5
	anchor_right = 0.5
	anchor_top = 1.0
	anchor_bottom = 1.0
	offset_left = -PANEL_SIZE.x * 0.5
	offset_right = PANEL_SIZE.x * 0.5
	offset_bottom = -BOTTOM_MARGIN
	offset_top = offset_bottom - PANEL_SIZE.y
	add_theme_stylebox_override("panel", _panel_style())
	mouse_filter = Control.MOUSE_FILTER_STOP
	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 6)
	add_child(margin)

	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 4)
	margin.add_child(layout)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 4)
	layout.add_child(header)
	for tab_name in TABS:
		var tab_button := Button.new()
		tab_button.text = tab_name
		tab_button.custom_minimum_size = Vector2(70, 22)
		tab_button.add_theme_font_size_override("font_size", FONT_SMALL)
		tab_button.pressed.connect(_on_tab_pressed.bind(tab_name))
		header.add_child(tab_button)
		_tab_buttons[tab_name] = tab_button
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	_collapse_button = Button.new()
	_collapse_button.text = "X"
	_collapse_button.tooltip_text = "Свернуть чат"
	_collapse_button.custom_minimum_size = Vector2(24, 22)
	_collapse_button.add_theme_font_size_override("font_size", FONT_SMALL)
	_collapse_button.add_theme_stylebox_override("normal", _flat_style(Color8(120, 60, 60)))
	_collapse_button.pressed.connect(_toggle_collapsed)
	header.add_child(_collapse_button)

	_body = HBoxContainer.new()
	_body.add_theme_constant_override("separation", 6)
	_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(_body)

	var messages_column := VBoxContainer.new()
	messages_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	messages_column.size_flags_vertical = Control.SIZE_EXPAND_FILL
	messages_column.add_theme_constant_override("separation", 3)
	_body.add_child(messages_column)

	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_active = true
	_log.scroll_following = true
	_log.selection_enabled = true
	_log.custom_minimum_size = Vector2(0, 60)
	_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log.add_theme_font_size_override("normal_font_size", FONT_TEXT)
	messages_column.add_child(_log)

	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.add_theme_font_size_override("font_size", FONT_SMALL)
	messages_column.add_child(_status)

	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 4)
	messages_column.add_child(input_row)
	_input = LineEdit.new()
	_input.placeholder_text = "Сообщение или /w <имя> текст"
	_input.max_length = 300
	_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_input.custom_minimum_size.y = 24
	_input.add_theme_font_size_override("font_size", FONT_TEXT)
	_input.add_theme_stylebox_override("normal", _input_style(INPUT_BORDER))
	_input.add_theme_stylebox_override("focus", _input_style(INPUT_FOCUS_BORDER))
	_input.text_submitted.connect(_on_text_submitted)
	input_row.add_child(_input)
	var send_button := Button.new()
	send_button.text = "ОТПРАВИТЬ"
	send_button.custom_minimum_size = Vector2(76, 24)
	send_button.add_theme_font_size_override("font_size", FONT_SMALL)
	send_button.add_theme_stylebox_override("normal", _flat_style(SEND_COLOR))
	send_button.pressed.connect(_submit)
	input_row.add_child(send_button)

	var divider := ColorRect.new()
	divider.color = PANEL_BORDER
	divider.custom_minimum_size = Vector2(2, 0)
	_body.add_child(divider)

	var people_column := VBoxContainer.new()
	people_column.custom_minimum_size = Vector2(PEOPLE_WIDTH, 0)
	people_column.add_theme_constant_override("separation", 3)
	_body.add_child(people_column)
	_players_title = Label.new()
	_players_title.add_theme_font_size_override("font_size", FONT_SMALL)
	_players_title.add_theme_color_override("font_color", TARGET_COLOR)
	people_column.add_child(_players_title)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	people_column.add_child(scroll)
	_players_box = VBoxContainer.new()
	_players_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_players_box.add_theme_constant_override("separation", 2)
	scroll.add_child(_players_box)

	_update_tabs()
	_refresh_status()
	_render_players()


func set_identity(user_id: int) -> void:
	_own_user_id = user_id


func set_players(players: Array) -> void:
	var signature := str(players)
	if signature == _players_signature:
		return
	_players_signature = signature
	_players = players.duplicate()
	_render_players()


# Пункт меню «Отправить личное сообщение»: переключает на «Личный» и готовит команду /w.
func start_private_message(username: String) -> void:
	if _collapsed:
		_toggle_collapsed()
	_tab = "Личный"
	_status_text = ""
	_update_tabs()
	_render()
	_input.text = "/w %s " % username
	_input.caret_column = _input.text.length()
	_input.grab_focus()
	_refresh_status()


func _render_players() -> void:
	if _players_box == null:
		return
	for child in _players_box.get_children():
		_players_box.remove_child(child)
		child.queue_free()
	for player in _players:
		if not (player is Dictionary):
			continue
		var row := Button.new()
		row.text = "● " + str(player.get("username", "Игрок"))
		row.flat = true
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.clip_text = true
		row.focus_mode = Control.FOCUS_NONE
		row.tooltip_text = "ПКМ — действия"
		row.add_theme_font_size_override("font_size", FONT_TEXT)
		row.add_theme_color_override("font_color", ONLINE_COLOR)
		row.add_theme_color_override("font_hover_color", ONLINE_COLOR)
		row.add_theme_color_override("font_pressed_color", ONLINE_COLOR)
		row.add_theme_stylebox_override("hover", _flat_style(ROW_HOVER_COLOR))
		row.add_theme_stylebox_override("pressed", _flat_style(ROW_HOVER_COLOR))
		row.gui_input.connect(_on_player_row_input.bind(player))
		_players_box.add_child(row)
	_players_title.text = "Лобби · онлайн %d" % _players.size()


func _on_player_row_input(event: InputEvent, player: Dictionary) -> void:
	var mouse_event := event as InputEventMouseButton
	if mouse_event != null and mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_RIGHT:
		player_menu_requested.emit(player, get_global_mouse_position())


func set_messages(messages: Array) -> void:
	_messages = messages.duplicate()
	_render()


func set_status(text: String, is_error := true) -> void:
	_status_text = text
	_status_is_error = is_error
	_refresh_status()


func clear_input() -> void:
	_input.clear()


func _on_text_submitted(_text: String) -> void:
	_submit()


func _submit() -> void:
	var text := _input.text.strip_edges()
	if text.is_empty():
		set_status("Сообщение не может быть пустым")
		return
	var recipient := 0
	if text == "/w" or text.begins_with("/w "):
		var parsed: Dictionary = LOBBY_FORMAT.parse_whisper(text, _players, _own_user_id)
		if not str(parsed["error"]).is_empty():
			set_status(str(parsed["error"]))
			return
		_whisper_target = {"user_id": int(parsed["user_id"]), "username": str(parsed["username"])}
		recipient = int(parsed["user_id"])
		text = str(parsed["message"])
		_tab = "Личный"
		_update_tabs()
		_render()
	elif _tab == "Личный":
		if _whisper_target.is_empty():
			set_status("Напишите /w <имя> текст, чтобы начать личный диалог")
			return
		recipient = int(_whisper_target["user_id"])
	message_submitted.emit(text, recipient)


func _on_tab_pressed(tab_name: String) -> void:
	_tab = tab_name
	_status_text = ""
	_update_tabs()
	_render()
	_refresh_status()


func _toggle_collapsed() -> void:
	_collapsed = not _collapsed
	_body.visible = not _collapsed
	for tab_name in TABS:
		(_tab_buttons[tab_name] as Button).visible = not _collapsed
	_collapse_button.text = "Чат" if _collapsed else "X"
	_collapse_button.custom_minimum_size.x = 40.0 if _collapsed else 24.0
	_collapse_button.add_theme_stylebox_override("normal", _flat_style(TAB_ACTIVE if _collapsed else Color8(120, 60, 60)))
	_collapse_button.tooltip_text = "Открыть чат" if _collapsed else "Свернуть чат"
	_apply_size(COLLAPSED_SIZE if _collapsed else PANEL_SIZE)


# Чат привязан к низу экрана по центру, поэтому меняются только верхний край и ширина.
func _apply_size(panel_size: Vector2) -> void:
	custom_minimum_size = panel_size
	offset_left = -panel_size.x * 0.5
	offset_right = panel_size.x * 0.5
	offset_top = offset_bottom - panel_size.y


func _update_tabs() -> void:
	for tab_name in TABS:
		var button: Button = _tab_buttons[tab_name]
		var color := TAB_ACTIVE if tab_name == _tab else TAB_IDLE
		button.add_theme_stylebox_override("normal", _flat_style(color))
		button.add_theme_stylebox_override("hover", _flat_style(color.lightened(0.12)))


func _refresh_status() -> void:
	if not _status_text.is_empty():
		_status.text = _status_text
		_status.add_theme_color_override("font_color", ERROR_COLOR if _status_is_error else TARGET_COLOR)
	elif _tab == "Личный" and not _whisper_target.is_empty():
		_status.text = "Собеседник: %s" % str(_whisper_target["username"])
		_status.add_theme_color_override("font_color", TARGET_COLOR)
	else:
		_status.text = ""


func _render() -> void:
	if _log == null:
		return
	var lines := PackedStringArray()
	for message in _messages:
		if message is Dictionary:
			var line := _message_line(message)
			if not line.is_empty():
				lines.append(line)
	_log.text = "\n".join(lines)


func _message_line(message: Dictionary) -> String:
	var is_whisper: bool = message.get("recipient_user_id") != null
	if (_tab == "Личный") != is_whisper:
		return ""
	var own := int(message.get("sender_user_id", 0)) == _own_user_id
	var sender := "Вы" if own else _escape(str(message.get("username", "Игрок")))
	var color := WHISPER_COLOR if is_whisper else (OWN_NAME_COLOR if own else OTHER_TEXT_COLOR)
	var time_text := LOBBY_FORMAT.local_time_text(float(message.get("created_at", 0.0)))
	return "[color=#%s][%s][/color] [color=#%s]%s:[/color] %s" % [
		TIME_COLOR.to_html(false),
		time_text,
		color.to_html(false),
		sender,
		_escape(str(message.get("text", ""))),
	]


static func _escape(text: String) -> String:
	return text.replace("[", "[lb]")


static func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_BACKGROUND
	style.border_color = PANEL_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	return style


static func _input_style(border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = INPUT_BACKGROUND
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.content_margin_left = 8
	style.content_margin_right = 8
	return style


static func _flat_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(5)
	return style
