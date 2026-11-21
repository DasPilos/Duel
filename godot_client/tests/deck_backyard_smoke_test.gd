extends Node

# Задний двор Калоды: раскладка и правила сверены с фикстурой Python (tests/fixtures/deck_backyard/python_layout.json),
# вид проверяется отдельно, связка с миром — через существующие действия (заявки, сбор, сравнение, чат).
# Сеть не используется: адрес недоступен, ответы подаются вручную.
const RULES := preload("res://scripts/deck_backyard_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/deck_backyard_view.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_backyard/"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const OWN_ID := 42

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var python := _load_json("python_layout.json")
	var social := _load_json("social.json")
	_check(not python.is_empty() and not social.is_empty(), "фикстуры заднего двора загружены")
	_check_python_layout(python)
	_check_rules(social)
	await _check_view(social)
	await _check_world(social)
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_backyard_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _load_json(file_name: String) -> Dictionary:
	var file := FileAccess.open(FIXTURE_DIR + file_name, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}


func _same_rect(rect: Rect2, values: Variant) -> bool:
	if not values is Array or values.size() < 4:
		return false
	return is_equal_approx(rect.position.x, float(values[0])) and is_equal_approx(rect.position.y, float(values[1])) \
		and is_equal_approx(rect.size.x, float(values[2])) and is_equal_approx(rect.size.y, float(values[3]))


func _vec(values: Array) -> Vector2:
	return Vector2(float(values[0]), float(values[1]))


func _check_python_layout(python: Dictionary) -> void:
	_check(_same_rect(RULES.TAVERN_BUTTON, python["tavern_button"]), "кнопка «В ТАВЕРНУ» на месте Python")
	_check(_same_rect(RULES.INVENTORY_BUTTON, python["inventory_button"]), "кнопка инвентаря на месте Python")
	_check(_same_rect(RULES.APPLICATION_FRAME, python["application_frame"]), "рамка «ОДИН НА ОДИН» на месте Python")
	_check(_same_rect(RULES.DUEL_LIST, python["duel_list"]), "список заявок на месте Python")
	_check(_same_rect(RULES.GROUP_LIST, python["group_list"]), "список стенки на месте Python")
	_check(_same_rect(RULES.DUEL_BUTTON, python["duel_button"]), "кнопка «ОДИН НА ОДИН» на месте Python")
	_check(_same_rect(RULES.GROUP_BUTTON, python["group_button"]), "кнопка «СТЕНКА НА СТЕНКУ» на месте Python")
	_check(_same_rect(RULES.ACCEPT_BUTTON, python["accept_button"]), "кнопка «ПРИНЯТЬ ЗАЯВКУ» на месте Python")
	_check(RULES.TITLE_POS == _vec(python["title_pos"]), "заголовок рамки на месте Python")
	_check(RULES.GROUP_LABEL_POS == _vec(python["group_label_pos"]), "подпись стенки на месте Python")
	_check(RULES.ERROR_POS == _vec(python["error_pos"]), "строка ошибки на месте Python")
	_check(is_equal_approx(RULES.TIMER_TOP, float(python["timer_top"])), "таймеры под кнопками, как в Python")
	_check(int(RULES.ROW_STEP) == int(python["row_step"]) and int(RULES.ROW_HEIGHT) == int(python["row_height"]), "шаг и высота строк как в Python")
	_check(_same_rect(RULES.CHAT_PANEL, python["chat_panel"]), "панель чата на месте Python")
	_check(_same_rect(RULES.collapsed_toggle_rect(), python["chat_collapsed_toggle"]), "кнопка «ЧАТ» свёрнутого чата на месте Python")
	var layout: Dictionary = RULES.chat_layout(RULES.default_divider_x())
	_check(_same_rect(layout["divider"], python["chat_divider"]), "разделитель чата на месте Python")
	_check(_same_rect(layout["people"], python["chat_people"]), "список людей чата на месте Python")
	_check(_same_rect(layout["messages"], python["chat_messages"]), "список сообщений чата на месте Python")
	_check(_same_rect(layout["send"], python["chat_send"]), "кнопка «ОТПРАВИТЬ» на месте Python")
	_check(_same_rect(layout["toggle"], python["chat_toggle"]), "кнопка «СВЕРНУТЬ» на месте Python")
	_check(layout["room_pos"] == _vec(python["chat_room_name_pos"]), "название комнаты чата на месте Python")
	var channels: Array = layout["channels"]
	var python_channels: Array = python["chat_channels"]
	var channels_match := channels.size() == python_channels.size()
	for index in channels.size():
		channels_match = channels_match and _same_rect(channels[index], python_channels[index]["rect"])
	_check(channels_match, "вкладки «Общий» и «Личные» на месте Python")
	_check(is_equal_approx(RULES.clamp_divider(-100000.0), float(python["chat_divider_x_min"])), "нижний предел разделителя как в Python")
	_check(is_equal_approx(RULES.clamp_divider(100000.0), float(python["chat_divider_x_max"])), "верхний предел разделителя как в Python")
	var field: Rect2 = layout["field"]
	var send: Rect2 = layout["send"]
	_check(is_equal_approx(field.end.x, send.position.x - RULES.CHAT_FIELD_GAP), "поле ввода не заходит под кнопку «ОТПРАВИТЬ»")


func _check_rules(social: Dictionary) -> void:
	var now := float(social["now"])
	var own := str(OWN_ID)
	var offers: Array = social["offers"]
	var duel := RULES.duel_offers(offers, {}, own, "Тестовый Боец")
	_check(duel.size() == 2 and str(duel[0]["id"]) == "offer-7", "заявки сортируются от новых к старым")
	var fresh := RULES.duel_label(duel[0], own, now)
	_check(fresh["text"] == "Соперник (новая)" and bool(fresh["highlight"]), "свежая заявка помечена «новая» и подсвечена")
	var old := RULES.duel_label(duel[1], own, now)
	_check(old["text"] == "Бродяга" and not bool(old["highlight"]), "старая заявка без пометки")
	var mine := {"id": "mine", "sender_id": OWN_ID, "sender": "Тестовый Боец", "status": "pending", "created_at": now - 60.0, "ttl": 300}
	var with_mine := RULES.duel_offers(offers, mine, own, "Тестовый Боец")
	_check(with_mine.size() == 3 and str(with_mine[1]["id"]) == "mine", "своя заявка добавляется и попадает на своё место по времени")
	_check(RULES.duel_offers(offers + [mine], mine, own, "Тестовый Боец").size() == 3, "своя заявка не дублируется, если она уже в списке")
	_check(RULES.duel_label(with_mine[1], own, now)["text"] == "Тестовый Боец (ваша заявка)", "своя заявка подписана «(ваша заявка)»")
	_check(RULES.application_timer_text(mine, now) == "Заявка активна: 4:00", "таймер своей заявки M:SS")
	_check(not RULES.active_application(mine, now).is_empty(), "не просроченная заявка активна")
	var expired := mine.duplicate()
	expired["created_at"] = now - 400.0
	_check(RULES.active_application(expired, now).is_empty(), "просроченная заявка неактивна")
	_check(RULES.active_application({"id": "x", "status": "accepted", "created_at": now, "ttl": 300}, now).is_empty(), "принятая заявка неактивна")
	var group: Dictionary = social["group_offers"][0]
	_check(RULES.group_timer_text(group, now) == "Сбор активен: 6:40", "таймер сбора M:SS")
	_check(RULES.group_label(group) == "Лучник (3/10)", "строка сбора с «/10», как в Python")
	_check(RULES.group_button_title({}) == "Стенка на стенку" and RULES.group_button_title(group) == "Отменить сбор", "подпись кнопки стенки меняется со сбором")
	_check(RULES.duel_button_title({}) == "ОДИН НА ОДИН" and RULES.duel_button_title(mine) == "ОТОЗВАТЬ ЗАЯВКУ", "подпись кнопки заявки меняется со своей заявкой")
	var people := RULES.people_rows(social["occupants"], own)
	_check(people.size() == 4 and bool(people[0]["self"]) and str(people[2]["label"]) == "Бродяга (АФК)", "люди рядом: свой отмечен, АФК с подписью")
	var messages: Array = social["messages"].duplicate(true)
	messages.append({"id": 9, "sender_id": 7, "sender": "Соперник", "recipient_id": 42, "text": "личное", "time_text": "12:02:00"})
	_check(RULES.visible_messages(messages).size() == 3, "в «Общем» нет личных сообщений")
	var own_parts := RULES.message_parts(social["messages"][1], own)
	_check(own_parts["body"] == "Вы: Я в деле, жду заявок" and bool(own_parts["own"]) and own_parts["time"] == "[12:00:50] ", "своё сообщение: «Вы» и время")
	_check(bool(RULES.message_parts(social["messages"][2], own)["gold"]), "[ИГРОК] подсвечивается золотом")
	_check(RULES.countdown_text(65) == "1:05" and RULES.countdown_text(0) == "0:00", "формат таймера M:SS")
	var font := ThemeDB.fallback_font
	var wrapped := RULES.wrap_text(font, "Длинная строка сообщения, которая точно не влезет в одну короткую строку", 15, 120.0, 120.0)
	var all_fit := true
	for line in wrapped:
		all_fit = all_fit and RULES.text_width(font, str(line), 15) <= 120.5
	_check(wrapped.size() >= 3 and all_fit, "сообщения переносятся по ширине")
	var cut := RULES.fit_text(font, "Очень длинное имя участника", 18, 80.0)
	_check(cut.ends_with("…") and RULES.text_width(font, cut, 18) <= 80.0, "длинное имя обрезается с многоточием")
	_check(RULES.fit_text(font, "Имя", 18, 300.0) == "Имя", "короткое имя не меняется")
	_check(RULES.clamp_scroll(5, 3, 3) == 0 and RULES.clamp_scroll(-2, 10, 3) == 0 and RULES.clamp_scroll(9, 10, 3) == 7, "прокрутка ограничена")
	_check(RULES.visible_count(145.0, 42.0) == 3 and RULES.visible_count(200.0, 42.0) == 4, "видимые строки как в Python")
	_check(RULES.row_index_at(10.0, 0, 42.0, 34.0) == 0 and RULES.row_index_at(40.0, 0, 42.0, 34.0) == -1 and RULES.row_index_at(50.0, 1, 42.0, 34.0) == 2, "попадание кликом в строку")
	var thumb := RULES.scrollbar_thumb(Rect2(0.0, 0.0, 4.0, 145.0), 6, 3, 3)
	_check(is_equal_approx(thumb.position.y, 73.0) and is_equal_approx(thumb.size.y, 72.0), "ползунок прокрутки в конце списка")
	var incoming := {"id": "in-1", "sender_id": "7", "sender": "Соперник", "target_id": str(OWN_ID), "created_at": now - 10.0}
	_check(not RULES.incoming_offer("in-1", [incoming], mine, own).is_empty(), "входящая заявка принимается, пока своя активна")
	_check(RULES.incoming_offer("in-1", [incoming], {}, own).is_empty(), "без своей заявки входящую принять нельзя")
	_check(RULES.incoming_offer("", [incoming], mine, own).is_empty(), "без выбранной строки принимать нечего")


func _model_from(social: Dictionary, own_application: Dictionary) -> Dictionary:
	var own := str(OWN_ID)
	return {
		"now": float(social["now"]),
		"own_id": own,
		"my_application": own_application,
		"duel_offers": RULES.duel_offers(social["offers"], own_application, own, "Тестовый Боец"),
		"selected_offer_id": "",
		"group_offers": social["group_offers"],
		"own_group": {},
		"occupants": social["occupants"],
		"messages": social["messages"],
	}


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and (child as Button).text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _find_all_buttons(node: Node, text: String) -> Array:
	var found: Array = []
	for child in node.get_children():
		if child is Button and (child as Button).text == text:
			found.append(child)
		found.append_array(_find_all_buttons(child, text))
	return found


func _click(position: Vector2) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = position
	return event


func _release(position: Vector2) -> InputEventMouseButton:
	var event := _click(position)
	event.pressed = false
	return event


func _motion(position: Vector2) -> InputEventMouseMotion:
	var event := InputEventMouseMotion.new()
	event.position = position
	return event


func _wheel(up: bool, position: Vector2) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_WHEEL_UP if up else MOUSE_BUTTON_WHEEL_DOWN
	event.pressed = true
	event.position = position
	return event


func _check_view(social: Dictionary) -> void:
	var host := Control.new()
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(host)
	var view = VIEW_SCRIPT.new()
	host.add_child(view)
	view.set_active(true)
	var model := _model_from(social, {})
	var layer: Control = view.build_layer(model)
	host.add_child(layer)
	var stage: Control = view.get("_stage")

	var tavern := _find_button(host, "В ТАВЕРНУ")
	_check(tavern != null and tavern.position == Vector2(1640.0, 35.0) and tavern.size == Vector2(220.0, 45.0), "кнопка «В ТАВЕРНУ» стоит на месте Python")
	var duel := _find_button(host, "ОДИН НА ОДИН")
	_check(duel != null and duel.position == Vector2(560.0, 620.0) and duel.size == Vector2(220.0, 40.0), "кнопка «ОДИН НА ОДИН» стоит на месте Python")
	var accept := _find_button(host, "ПРИНЯТЬ ЗАЯВКУ")
	_check(accept != null and not accept.visible, "«ПРИНЯТЬ ЗАЯВКУ» скрыта без входящей заявки")
	var common := _find_button(host, "Общий")
	var personal := _find_button(host, "Личные")
	_check(common != null and personal != null and personal.disabled and not common.disabled, "вкладка «Личные» пока недоступна, «Общий» активна")
	_check(_find_button(host, "СВЕРНУТЬ") != null and _find_button(host, "ОТПРАВИТЬ") != null, "кнопки чата на месте")
	var input: LineEdit = view.chat_input()
	_check(input.position == Vector2(456.0, 1040.0) and input.size.y >= 25.0 and input.position.y + input.size.y <= 1075.0 and input.max_length == 300, "поле ввода на месте Python, внутри панели, до 300 символов")
	_check(input.size.x > 600.0 and input.position.x + input.size.x < 1217.0, "поле ввода не заходит на кнопку «ОТПРАВИТЬ»")

	var compare_buttons := _find_all_buttons(host, "Сравнить")
	_check(compare_buttons.size() == 2, "у двух чужих заявок есть «Сравнить»")
	_check(_find_all_buttons(host, "ДУЭЛЬ").size() == 1 and _find_all_buttons(host, "Вызвать").size() == 2, "АФК получает «ДУЭЛЬ», остальные «Вызвать»")
	var hidden := true
	for child in layer.get_children():
		hidden = hidden and not (child as Control).visible
	_check(hidden, "кнопки строк скрыты, пока строка не наведена")
	view.set("_hovered_duel", 0)
	view.call("_refresh_row_buttons")
	_check(compare_buttons[0].visible and not compare_buttons[1].visible, "наведение на строку показывает её кнопки")
	view.set("_hovered_duel", -1)
	view.call("_refresh_row_buttons")
	_check(not compare_buttons[0].visible, "уход с строки прячет её кнопки")

	var received: Array = []
	view.compare_requested.connect(func(offer: Dictionary) -> void: received.append("compare:" + str(offer.get("id", ""))))
	view.accept_offer_requested.connect(func(offer_id: String) -> void: received.append("accept:" + offer_id))
	view.decline_offer_requested.connect(func(offer_id: String) -> void: received.append("decline:" + offer_id))
	view.challenge_requested.connect(func(character_id: String) -> void: received.append("challenge:" + character_id))
	view.duel_row_pressed.connect(func(offer: Dictionary) -> void: received.append("row:" + str(offer.get("id", ""))))
	view.group_row_pressed.connect(func(offer_id: String) -> void: received.append("group:" + offer_id))
	view.chat_send_requested.connect(func(text: String) -> void: received.append("chat:" + text))
	view.tavern_requested.connect(func() -> void: received.append("tavern"))
	view.duel_requested.connect(func() -> void: received.append("duel"))
	compare_buttons[0].pressed.emit()
	_find_all_buttons(host, "Принять")[0].pressed.emit()
	_find_all_buttons(host, "Отклонить")[0].pressed.emit()
	_find_button(host, "ДУЭЛЬ").pressed.emit()
	_find_all_buttons(host, "Вызвать")[0].pressed.emit()
	tavern.pressed.emit()
	duel.pressed.emit()
	view.get("_duel_area").gui_input.emit(_click(Vector2(100.0, 10.0)))
	view.get("_group_area").gui_input.emit(_click(Vector2(100.0, 10.0)))
	input.text = "Привет"
	input.text_submitted.emit("Привет")
	var expected := ["compare:offer-7", "accept:offer-7", "decline:offer-7", "challenge:9", "challenge:7", "tavern", "duel", "row:offer-7", "group:group-11", "chat:Привет"]
	_check(received == expected, "кнопки и строки отдают те же действия, что раньше")

	view.get("_toggle_button").pressed.emit()
	_check(view.get("_collapsed") and view.get("_collapsed_button").visible and not input.visible, "свёрнутый чат остаётся кнопкой «ЧАТ»")
	view.get("_collapsed_button").pressed.emit()
	_check(not view.get("_collapsed") and input.visible, "чат разворачивается обратно")

	stage.gui_input.emit(_click(Vector2(1296.0, 900.0)))
	stage.gui_input.emit(_motion(Vector2(1100.0, 900.0)))
	_check(is_equal_approx(float(view.get("_divider_x")), 1096.0), "разделитель двигается мышью")
	stage.gui_input.emit(_motion(Vector2(0.0, 900.0)))
	_check(is_equal_approx(float(view.get("_divider_x")), 771.0), "разделитель не выходит за пределы")
	stage.gui_input.emit(_release(Vector2(0.0, 900.0)))
	stage.gui_input.emit(_motion(Vector2(1200.0, 900.0)))
	_check(is_equal_approx(float(view.get("_divider_x")), 771.0), "после отпускания разделитель стоит на месте")
	view.set("_divider_x", RULES.default_divider_x())
	view.call("_apply_chat_layout")

	var extra_offers: Array = social["offers"].duplicate(true)
	for index in 3:
		extra_offers.append({"id": "extra-%d" % index, "sender_id": str(100 + index), "sender": "Игрок %d" % index, "created_at": float(social["now"]) - 1000.0 - index})
	var social_many := social.duplicate(true)
	social_many["offers"] = extra_offers
	var layer_many: Control = view.build_layer(_model_from(social_many, {}))
	host.add_child(layer_many)
	view.get("_duel_area").gui_input.emit(_wheel(false, Vector2(100.0, 50.0)))
	_check(view.get("_duel_scroll") == 1, "колесо прокручивает заявки")
	view.get("_duel_area").gui_input.emit(_wheel(true, Vector2(100.0, 50.0)))
	_check(view.get("_duel_scroll") == 0, "колесо возвращает заявки назад")
	view.get("_messages_area").gui_input.emit(_wheel(true, Vector2(100.0, 50.0)))
	_check(not view.get("_message_follow"), "колесо в чате отключает слежение за последним сообщением")

	view.set_message("Ошибка тест")
	_check(view.get("_message") == "Ошибка тест", "строка ошибки видна на заднем дворе")
	view.open_profile(social["character"])
	_check(view.is_profile_open(), "кнопка профиля открывает карточку игрока")

	var home := Control.new()
	var shell_list := VBoxContainer.new()
	home.add_child(shell_list)
	host.add_child(home)
	view.dock_list(shell_list)
	_check(shell_list.get_parent() == stage and shell_list.position == Vector2(800.0, 620.0), "список переносится в вид на место кнопки стенки")
	view.undock_list(shell_list, home, 8)
	_check(shell_list.get_parent() == home and shell_list.get_theme_constant("separation") == 8, "список возвращается в оболочку с прежним отступом")

	var hover_style: StyleBoxFlat = tavern.get_theme_stylebox("hover")
	_check(hover_style.bg_color == Color8(110, 190, 255), "наведение на кнопку как в Python: (110, 190, 255)")
	var group := Button.new()
	group.text = "Стенка на стенку"
	view.style_group_button(group, false)
	var caption := group.get_child(0) as Label
	_check(caption != null and caption.uppercase and caption.text == "Стенка на стенку" and group.get_theme_color("font_color").a == 0.0, "подпись стенки выводится заглавными, как в Python")
	group.free()
	host.queue_free()
	await get_tree().process_frame


func _waiting_group() -> Dictionary:
	return {
		"id": "group-11", "sender_id": 11, "sender": "Лучник", "status": "waiting", "max_participants": 8,
		"ttl": 600, "created_at": Time.get_unix_time_from_system() - 100.0,
		"participants": [{"id": 11, "name": "Лучник"}, {"id": 12, "name": "Маг"}],
	}


func _shift_social(social: Dictionary, now: float) -> Dictionary:
	var data: Dictionary = JSON.parse_string(JSON.stringify(social))
	var delta := now - float(data["now"])
	for offer in data["offers"]:
		offer["created_at"] = float(offer["created_at"]) + delta
	for group in data["group_offers"]:
		group["created_at"] = float(group["created_at"]) + delta
	for message in data["messages"]:
		message["created_at"] = float(message["created_at"]) + delta
	return data


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


# ApiClient держит один запрос: пока он идёт, следующий отклоняется сразу, поэтому ждём ответа на каждом шаге.
func _api_idle() -> void:
	var started := Time.get_ticks_msec()
	while ApiClient._busy and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _check_world(social: Dictionary) -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = (social["character"] as Dictionary).duplicate(true)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var now := Time.get_unix_time_from_system()
	var view = deck._backyard_view
	var stage: Control = view.get("_stage")
	deck._view = "backyard"
	deck._social_location = "backyard"
	deck._social_data = _shift_social(social, now)
	deck._render_social()
	_check(deck._list.get_parent() == stage and view.visible, "задний двор показывает вид и переносит список мира в него")
	_check(_find_button(deck._list, "Стенка на стенку") != null, "кнопка «Стенка на стенку» стоит в списке мира")
	_check(_find_button(deck._list, "Сравнить") != null, "кнопка «Сравнить» есть в списке мира")
	_check(deck._chat_input == view.chat_input(), "чат заднего двора использует поле вида")
	deck._status.text = "тест статуса"
	deck._sync_backyard_view()
	_check(view.get("_message") == "тест статуса", "статус мира показывается на заднем дворе")

	var group_button := _find_button(deck._list, "Стенка на стенку")
	await _api_idle()
	group_button.pressed.emit()
	_check(deck._group_battle_window.is_open(), "кнопка стенки открывает окно сбора")
	deck._group_battle_window.close()

	await _api_idle()
	deck._social_data["group_offers"] = [{
		"id": "group-mine", "sender_id": OWN_ID, "sender": "Тестовый Боец", "status": "waiting",
		"max_participants": 6, "ttl": 600, "created_at": now - 200.0,
		"participants": [{"id": OWN_ID, "name": "Тестовый Боец"}, {"id": 12, "name": "Маг"}],
	}]
	deck._render_social()
	deck._on_backyard_duel_pressed()
	_check(deck._status.text == RULES.DUEL_GUARD and deck._pending_action.is_empty(), "заявка один на один не подаётся, пока стоит своя стенка")
	deck._on_backyard_group_pressed()
	_check(deck._pending_action == "leave_group", "«Отменить сбор» отменяет свой сбор, как раньше")
	await _api_idle()

	deck._social_data["group_offers"] = []
	deck._social_data["my_application"] = {"id": "mine", "sender_id": OWN_ID, "sender": "Тестовый Боец", "status": "pending", "created_at": now - 60.0, "ttl": 300}
	deck._render_social()
	deck._on_backyard_group_pressed()
	_check(deck._status.text == RULES.GROUP_GUARD and not deck._group_battle_window.is_open(), "стенка не открывается, пока своя заявка активна")
	deck._on_backyard_duel_pressed()
	_check(deck._pending_action == "cancel_application", "«ОТОЗВАТЬ ЗАЯВКУ» отменяет заявку, как раньше")
	await _api_idle()

	deck._social_data["my_application"] = null
	deck._render_social()
	deck._on_backyard_duel_pressed()
	_check(deck._pending_action == "create_application", "«ОДИН НА ОДИН» подаёт заявку, как раньше")
	await _api_idle()

	deck._render_social()
	_find_button(deck._list, "Сравнить").pressed.emit()
	_check(deck._comparison.visible and str(deck._comparison_offer.get("id", "")) == "offer-7", "«Сравнить» открывает сравнение заявки, как раньше")
	deck._close_comparison()

	await _api_idle()
	deck._social_data["group_offers"] = [_waiting_group()]
	deck._render_social()
	view.get("_group_area").gui_input.emit(_click(Vector2(100.0, 10.0)))
	_check(deck._pending_action == "join_group", "клик по строке стенки вступает в сбор, как раньше")
	await _api_idle()

	view.chat_input().text = "Привет"
	view.chat_input().text_submitted.emit("Привет")
	_check(deck._pending_action == "send_chat", "сообщение чата уходит прежним запросом")
	await _api_idle()

	view.get("_inventory_button").pressed.emit()
	_check(view.is_profile_open(), "📦 открывает профиль игрока")
	GameSession.character["level"] = 9
	deck._sync_backyard_view()
	_check(deck._backyard_profile_snapshot.get("level") == 9, "профиль обновляется при смене персонажа")
	deck._on_backyard_level_requested(1)
	_check(deck._status.text == RULES.LEVEL_LOCKED_TEXT, "уровень в профиле заднего двора не меняется")

	await _api_idle()
	view.get("_tavern_button").pressed.emit()
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	_check(deck._social_location == "tavern" and deck._view == "tavern", "«В ТАВЕРНУ» ведёт в таверну")
	_check(deck._list.get_parent() == deck._backyard_list_home and not view.visible, "в таверне список возвращается в оболочку, вид скрыт")
	await _api_idle()
	deck._enter_location("backyard")
	_check(deck._list.get_parent() == stage and view.visible, "возврат на задний двор снова показывает вид")

	deck._view = "battle"
	deck._sync_backyard_view()
	_check(not view.visible and deck._list.get_parent() == stage, "во время боя вид скрыт, список не теряется")
	deck._view = "backyard"
	deck._social_data = {}
	deck._render_social()
	_check(_find_button(deck._list, "Стенка на стенку") != null and view.visible, "пустой снимок не ломает задний двор")

	GameSession.clear()
	deck.queue_free()
	await get_tree().process_frame
