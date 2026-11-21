extends PanelContainer

# Порт ui/chat/dialog.py: вкладки «Общий» и «Личный», шёпот «/w <имя> текст», ошибки в статусе.
# Сетевых запросов здесь нет: сцена отправляет сообщения и передаёт сюда снимок локации.

signal message_submitted(text: String, recipient_id: int)

const TABS := ["Общий", "Личный"]
const WHISPER_COMMAND := "/w"
const PANEL_SIZE := Vector2(460, 300)
const MARGIN := 10.0
const PANEL_BACKGROUND := Color8(22, 24, 34, 250)
const PANEL_BORDER := Color8(90, 100, 130)
const TEXT_COLOR := Color8(215, 215, 225)
const WHISPER_COLOR := Color8(235, 190, 255)
const ERROR_COLOR := Color8(255, 120, 100)
const TARGET_COLOR := Color8(255, 220, 120)
const MUTED_COLOR := Color8(160, 165, 170)

var _tab := "Общий"
var _messages: Array = []
var _occupants: Array = []
var _own_id := 0
var _whisper_target: Dictionary = {}
var _status_text := ""
var _status_is_error := true
var _tab_buttons: Dictionary = {}
var _scroll: ScrollContainer
var _log: VBoxContainer
var _status: Label
var _input: LineEdit


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	offset_left = -PANEL_SIZE.x - MARGIN
	offset_top = -PANEL_SIZE.y - MARGIN
	offset_right = -MARGIN
	offset_bottom = -MARGIN
	custom_minimum_size = PANEL_SIZE
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL_BACKGROUND
	style.border_color = PANEL_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(8)
	add_theme_stylebox_override("panel", style)
	var layout := VBoxContainer.new()
	add_child(layout)
	var header := HBoxContainer.new()
	layout.add_child(header)
	for tab_name in TABS:
		var tab_button := Button.new()
		tab_button.text = tab_name
		tab_button.pressed.connect(_select_tab.bind(tab_name))
		header.add_child(tab_button)
		_tab_buttons[tab_name] = tab_button
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	var close_button := Button.new()
	close_button.text = "X"
	close_button.pressed.connect(close_panel)
	header.add_child(close_button)
	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(_scroll)
	_log = VBoxContainer.new()
	_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(_log)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(_status)
	var input_row := HBoxContainer.new()
	layout.add_child(input_row)
	_input = LineEdit.new()
	_input.placeholder_text = "Сообщение (/w <имя> текст)"
	_input.max_length = 300
	_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_input.text_submitted.connect(_on_text_submitted)
	input_row.add_child(_input)
	var send_button := Button.new()
	send_button.text = "Отправить"
	send_button.pressed.connect(_submit)
	input_row.add_child(send_button)
	visible = false
	_render()


# Разбирает «/w <имя> текст». Имя ищется среди игроков локации, самое длинное совпадение побеждает.
static func parse_whisper(text: String, occupants: Array) -> Dictionary:
	var body := text.substr(WHISPER_COMMAND.length()).strip_edges()
	if body.is_empty():
		return {"target": {}, "body": "", "error": "Формат: /w <имя> текст"}
	var candidates: Array = []
	for occupant in occupants:
		if occupant is Dictionary and not str(occupant.get("name", "")).is_empty():
			candidates.append(occupant)
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a["name"]).length() > str(b["name"]).length())
	for occupant in candidates:
		var name := str(occupant["name"])
		if body.substr(0, name.length()).nocasecmp_to(name) != 0:
			continue
		var rest := body.substr(name.length())
		if not rest.is_empty() and not rest.left(1).strip_edges().is_empty():
			continue
		var message := rest.strip_edges()
		if message.is_empty():
			return {"target": occupant, "body": "", "error": "Введите текст сообщения после имени"}
		return {"target": occupant, "body": message, "error": ""}
	return {"target": {}, "body": "", "error": "Игрок не найден в локации: %s" % body.split(" ", false)[0]}


func is_open() -> bool:
	return visible


func open_panel() -> void:
	visible = true
	_input.grab_focus()


func close_panel() -> void:
	if not visible:
		return
	visible = false
	_input.release_focus()


func set_status(text: String, is_error := true) -> void:
	_status_text = text
	_status_is_error = is_error
	_refresh_status()


func apply_snapshot(messages: Array, occupants: Array, own_id: int) -> void:
	_messages = messages
	_occupants = occupants
	_own_id = own_id
	_render()


func clear_messages() -> void:
	apply_snapshot([], [], _own_id)


# Вызывается после успешной отправки: как в Python, личный ответ переключает вкладку на «Личный».
func mark_sent(recipient_id: int) -> void:
	_input.clear()
	set_status("")
	if recipient_id > 0:
		_tab = "Личный"
	_render()


func _select_tab(tab_name: String) -> void:
	_tab = tab_name
	_status_text = ""
	_render()


func _on_text_submitted(_text: String) -> void:
	if _input.text.strip_edges().is_empty():
		close_panel()
	else:
		_submit()


func _submit() -> void:
	var text := _input.text.strip_edges()
	if text.is_empty():
		set_status("Сообщение не может быть пустым")
		return
	var recipient_id := 0
	if text == WHISPER_COMMAND or text.begins_with(WHISPER_COMMAND + " "):
		var parsed := parse_whisper(text, _occupants)
		if not str(parsed["error"]).is_empty():
			set_status(str(parsed["error"]))
			return
		_whisper_target = parsed["target"]
		recipient_id = int(_whisper_target["character_id"])
		text = str(parsed["body"])
	elif _tab == "Личный":
		if _whisper_target.is_empty():
			set_status("Напишите /w <имя> текст, чтобы начать личный диалог")
			return
		recipient_id = int(_whisper_target["character_id"])
	message_submitted.emit(text, recipient_id)


func _visible_messages() -> Array:
	var result: Array = []
	for message in _messages:
		if not message is Dictionary:
			continue
		var recipient_id := _id_of(message.get("recipient_id"))
		if _tab == "Общий":
			if recipient_id == 0:
				result.append(message)
		elif recipient_id > 0 and _own_id in [_id_of(message.get("sender_id")), recipient_id]:
			result.append(message)
	return result


func _id_of(value: Variant) -> int:
	return 0 if value == null else int(value)


func _render() -> void:
	for child in _log.get_children():
		_log.remove_child(child)
		child.queue_free()
	for message in _visible_messages():
		var line := Label.new()
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.text = "[%s] %s: %s" % [
			str(message.get("time_text", "")),
			str(message.get("sender", "Игрок")),
			str(message.get("text", "")),
		]
		var is_private := _id_of(message.get("recipient_id")) > 0
		line.add_theme_color_override("font_color", WHISPER_COLOR if is_private else TEXT_COLOR)
		_log.add_child(line)
	for tab_name in _tab_buttons:
		_tab_buttons[tab_name].disabled = tab_name == _tab
	_refresh_status()
	call_deferred("_scroll_to_end")


func _refresh_status() -> void:
	if not _status_text.is_empty():
		_status.text = _status_text
		_status.add_theme_color_override("font_color", ERROR_COLOR if _status_is_error else MUTED_COLOR)
	elif _tab == "Личный" and not _whisper_target.is_empty():
		_status.text = "Собеседник: %s" % str(_whisper_target.get("name", ""))
		_status.add_theme_color_override("font_color", TARGET_COLOR)
	else:
		_status.text = ""


func _scroll_to_end() -> void:
	_scroll.scroll_vertical = int(_scroll.get_v_scroll_bar().max_value)
