extends Node

# Бой Калоды в мире Deck: снимок уходит в DeckBattleView, нажатие карты или кнопки шлёт тот же запрос, что старая
# текстовая кнопка, текст карт убран, подсказка и ошибки работают на экране боя. Запросы перехватывает локальный
# TCP-стаб на 127.0.0.1: ответы задаёт тест, настоящий сервер не нужен.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"
const STUB_PORT := 18773
const STUB_URL := "http://127.0.0.1:18773"
const BATTLE_PATH := "/api/deck/battle/action"
const CHARACTER_ID := 42
const WAIT_LIMIT_MS := 5000

var _failures: Array[String] = []
var _checks := 0
var _deck
var _server := TCPServer.new()
var _sockets: Array = []
var _requests: Array = []
var _reply_status := 400
var _reply_body: Dictionary = {"error": "stub"}


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check(_server.listen(STUB_PORT, "127.0.0.1") == OK, "локальный стаб слушает 127.0.0.1")
	_setup_session()
	await _check_snapshot_reaches_view()
	await _check_text_is_gone()
	await _check_hover()
	await _check_card_presses()
	await _check_draft_draw_and_result()
	await _check_response_updates_view()
	await _check_duplicate_copies()
	await _check_phase_transition()
	await _check_busy_and_errors()
	await _teardown()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_integration_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _setup_session() -> void:
	GameSession.clear()
	GameSession.hub_url = STUB_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": STUB_URL, "name": "Тест"}
	GameSession.character = {"id": 0, "name": "Тест", "zone": "backyard"}
	ApiClient.set_server_url(STUB_URL)
	ApiClient._http.timeout = 3.0
	_deck = DECK_SCRIPT.new()
	_deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_deck)
	# Id 0 не даёт миру стартовых запросов; нужный id задаётся после сборки экрана.
	_deck._character_id = CHARACTER_ID
	_deck._social_timer.stop()
	_deck._battle_timer.stop()


func _check_snapshot_reaches_view() -> void:
	var data := _fixture("planning_hand.json")
	_show_battle(data)
	var view = _deck._battle_view
	_check(_deck._battle_screen.visible and not (_deck._list.get_parent() as Control).visible, "бой: экран боя открыт, список мира скрыт")
	_check(view.card_count() == 7, "вид получил снимок: 5 карт руки и 2 выбранные")
	_check(view.timer_state()["visible"] and view.timer_state()["value"] == 42.0, "вид получил таймер: 42 секунды")
	_check(view.fighter_texts("player")["name"] == "Тестовый Боец", "вид получил имя бойца")
	_check(view.bar_state("player", "hp")["value"] == 106.0, "вид получил HP 106")
	_check(not view.pile_count_visible("deck") and not view.pile_count_visible("discard"), "колода и сброс без счётчиков: снимка их не содержит")
	_check(not view.hit_overlay_visible(), "заглушка удара не показана")


func _check_text_is_gone() -> void:
	var data := _fixture("planning_hand.json")
	_show_battle(data)
	var log_texts := _label_texts(_deck._battle_log)
	var group_in_log := false
	for card in data["hand"]:
		for text in log_texts:
			group_in_log = group_in_log or text.contains(str(card["group_name"]))
	var stats_in_log := false
	for text in log_texts:
		stats_in_log = stats_in_log or text.contains("HP") or text.contains("MP") or text.contains("Сила")
	_check(not group_in_log and not stats_in_log, "текст боя: строк карт (группа, стоимость) и HP, MP, характеристик в журнале нет")
	var only_lines := true
	for node in _deck._battle_log.get_children():
		only_lines = only_lines and (node is Label or node is RichTextLabel)
	_check(only_lines, "журнал боя: только строки (подписи и строки комментатора), без рядов карт")
	var commentary := _rich_texts(_deck._battle_log)
	_check(commentary.size() == 2 and commentary[0].contains("Бой начался.") and commentary[1].contains("Тестовый Боец применил Целительный выпад. ") and commentary[1].contains("(-6 хп)"), "комментатор: старт боя и обмен из снимка попадают в журнал")
	_check(_button_texts(_deck._battle_buttons) == ["Подтвердить ход", "Сжечь карту"], "кнопки боя: подтверждение и сжигание")
	var all_buttons := _all_button_texts(_deck)
	_check(not (all_buttons.has("Выбрать") or all_buttons.has("Снять выбор") or all_buttons.has("Сжечь")), "в мире нет старых кнопок «Выбрать», «Снять выбор», «Сжечь»")
	_check(_deck._list.get_child_count() == 0, "бой не рисуется в список мира")


func _check_hover() -> void:
	_show_battle(_fixture("planning_hand.json"))
	var card = _deck._battle_view.card_view("hand", 2)
	_check(_deck._card_hover_targets.size() == _deck._battle_view.card_count(), "каждая карта боя привязана к подсказке (_bind_card_hover)")
	var hovered: Dictionary = _deck._hovered_card(card.get_global_rect().get_center())
	_check(str(hovered.get("key", "")) == "warrior_valen_cleave", "опрос наведения находит карту боя под курсором")
	card.mouse_entered.emit()
	_check(_deck._card_tooltip.visible and _deck._card_tooltip._card_key == "warrior_valen_cleave", "card_hovered показывает подсказку карты")
	card.mouse_exited.emit()
	_check(not _deck._card_tooltip.visible, "уход курсора прячет подсказку")


func _check_card_presses() -> void:
	var data := _fixture("planning_hand.json")
	var battle_id := str(data["battle_id"])
	_show_battle(data)
	await _expect_request("выбор карты руки шлёт select с её ключом", "POST", BATTLE_PATH,
		_body(battle_id, "select", "warrior_valen_cleave"), func(): _click_card("hand", 2))
	await _expect_request("снятие выбранной карты шлёт deselect с её ключом", "POST", BATTLE_PATH,
		_body(battle_id, "deselect", "warrior_valen_strike_copy"), func(): _click_card("selected", 1))
	await _expect_no_request("недоступная карта руки не шлёт запроса", func(): _click_card("hand", 6))
	await _expect_request("кнопка «Подтвердить ход» шлёт confirm", "POST", BATTLE_PATH,
		_body(battle_id, "confirm", ""), func(): _press_button("Подтвердить ход"))
	_show_battle(data)
	_press_button("Сжечь карту")
	_check(_deck._battle_burn_mode and _deck._battle_view.card_view("hand", 6).is_pressable(), "режим сжигания: карта руки нажимается и без права выбора")
	_check(_button_texts(_deck._battle_buttons).has("Отменить сжигание"), "режим сжигания: кнопка показывает отмену")
	await _expect_request("сжигание карты руки шлёт burn с её ключом", "POST", BATTLE_PATH,
		_body(battle_id, "burn", "warrior_weakness_strength_copy"), func(): _click_card("hand", 6))
	_check(not _deck._battle_burn_mode, "после сжигания режим выключается")
	_press_button("Сжечь карту")
	await _expect_request("сжигание выбранной карты шлёт burn с её ключом", "POST", BATTLE_PATH,
		_body(battle_id, "burn", "warrior_valen_strike"), func(): _click_card("selected", 0))
	_press_button("Сжечь карту")
	_press_button("Отменить сжигание")
	_check(not _deck._battle_burn_mode and _button_texts(_deck._battle_buttons).has("Сжечь карту"), "отмена сжигания возвращает кнопку")


func _check_draft_draw_and_result() -> void:
	var draft := _fixture("draft_starting.json")
	var battle_id := str(draft["battle_id"])
	_show_battle(draft)
	await _expect_request("драфт: карта стола шлёт pick_starting", "POST", BATTLE_PATH,
		_body(battle_id, "pick_starting", str(draft["table"][3]["key"])), func(): _click_card("table", 3))
	await _expect_no_request("драфт: взятая карта руки не нажимается", func(): _click_card("hand", 0))
	var redraft := _fixture("draft_redraft.json")
	_show_battle(redraft)
	await _expect_request("повторный драфт шлёт pick_redraft", "POST", BATTLE_PATH,
		_body(battle_id, "pick_redraft", str(redraft["table"][1]["key"])), func(): _click_card("table", 1))
	var draw := _fixture("draw_choice.json")
	_show_battle(draw)
	await _expect_request("выбор добора шлёт choose_draw", "POST", BATTLE_PATH,
		_body(battle_id, "choose_draw", str(draw["draw_choices"][1]["key"])), func(): _click_card("draw_choices", 1))
	var won := _fixture("outcome_win.json")
	_show_battle(won)
	_check(_button_texts(_deck._battle_buttons) == ["Получить итог боя"], "итог боя: кнопка «Получить итог боя»")
	await _expect_request("кнопка «Получить итог боя» шлёт finish", "POST", "/api/deck/battle/finish",
		{"character_id": CHARACTER_ID, "battle_id": battle_id}, func(): _press_button("Получить итог боя"))
	_check(_deck._battle_notice.text == "stub", "ошибка итога боя видна на экране боя")
	_check(_deck._battle_view.result_texts()["title"] == "ПОБЕДА", "результат: заголовок победы на поле")
	_deck._battle_result_data = {"outcome": "win", "character": {"hp": 90, "mp": 10}, "reward": {"name": "Тестовая карта"}}
	_deck._render_battle()
	var log_texts := _label_texts(_deck._battle_log)
	_check(log_texts.has("HP после боя: 90 · MP: 10") and log_texts.has("Награда: Тестовая карта"), "после боя: HP, MP и награда в журнале")
	_check(_button_texts(_deck._battle_buttons) == ["Вернуться на задний двор"], "после боя: кнопка возврата на задний двор")
	await _expect_request("возврат на задний двор сохраняет зону и уводит с экрана боя", "PUT",
		"/api/characters/%d" % CHARACTER_ID, {"zone": "backyard"}, func(): _press_button("Вернуться на задний двор"))
	_check(_deck._view == "backyard" and not _deck._battle_screen.visible, "возврат: вид мира, экран боя скрыт")
	_check((_deck._list.get_parent() as Control).visible and _deck._battle_state.is_empty(), "возврат: список мира снова виден, состояние боя сброшено")


func _check_response_updates_view() -> void:
	var data := _fixture("planning_hand.json")
	var after := data.duplicate(true)
	after["selected"].append("warrior_valen_cleave")
	_reply_status = 200
	_reply_body = {"battle": after}
	_show_battle(data)
	await _expect_request("ответ на выбор обновляет поле", "POST", BATTLE_PATH,
		_body(str(data["battle_id"]), "select", "warrior_valen_cleave"), func(): _click_card("hand", 2))
	_reply_status = 400
	_reply_body = {"error": "stub"}
	_check(_deck._battle_view.card_count() == 7 and _deck._battle_view.card_view("selected", 2) != null, "ответ боя: выбранная карта появляется в выборе")
	_check(_deck._battle_view.card_view("selected", 2).name_text() == "Целительный выпад", "ответ боя: карта названа по снимку")


func _check_duplicate_copies() -> void:
	var data := _fixture("planning_hand.json")
	data["selected"] = ["warrior_valen_cleave"]
	data["hand"][3]["key"] = "warrior_valen_cleave"
	_show_battle(data)
	var view = _deck._battle_view
	_check(view.card_count() == 7, "две копии одной карты: на поле 6 карт руки и выбранная")
	_check(view.card_view("hand", 2) == null, "первая копия выбранной карты занята")
	_check(view.card_view("hand", 3) != null and not view.card_view("hand", 3).is_pressable(), "вторая копия видна и не нажимается, пока выбрана первая")


func _check_phase_transition() -> void:
	_show_battle(_fixture("draft_starting.json"))
	_deck._pending_action = "battle_action"
	_deck._on_api_completed(true, {"battle": _fixture("planning_hand.json")})
	_check(_deck._phase_transition.is_active(), "переход драфт → планирование запущен")
	var started := Time.get_ticks_msec()
	while _deck._phase_transition.is_active() and Time.get_ticks_msec() - started < WAIT_LIMIT_MS:
		await get_tree().process_frame
		_pump_stub()
	_deck._battle_timer.stop()
	_check(_deck._battle_view.card_count() == 7 and _deck._battle_state["phase"] == "planning", "после перехода поле показывает планирование")


func _check_busy_and_errors() -> void:
	_show_battle(_fixture("planning_hand.json"))
	_deck._pending_action = "stub"
	var before := _requests.size()
	_press_button("Подтвердить ход")
	_check(_requests.size() == before and _deck._battle_notice.text == "Подождите завершения текущего запроса.", "занятое соединение: кнопка не шлёт запрос и пишет об этом на экране боя")
	_deck._pending_action = ""
	var no_id := _fixture("planning_hand.json")
	no_id["battle_id"] = ""
	_show_battle(no_id)
	before = _requests.size()
	_press_button("Подтвердить ход")
	_check(_requests.size() == before and _deck._battle_notice.text == "Сервер не вернул идентификатор боя.", "без идентификатора боя запрос не уходит")


# Нажатие должно отправить ровно один запрос с нужными методом, путём и телом; затем ждём ответа стаба.
func _expect_request(label: String, method: String, path: String, expected: Dictionary, press: Callable) -> void:
	var before := _requests.size()
	press.call()
	await _wait_requests(before + 1)
	var ok := _requests.size() == before + 1
	if ok:
		var request: Dictionary = _requests[before]
		var body: Dictionary = request["body"]
		ok = request["method"] == method and request["path"] == path and body.size() == expected.size()
		for key in expected.keys():
			ok = ok and body.has(key) and body[key] == expected[key]
	_check(ok, label)
	await _wait_idle()


func _expect_no_request(label: String, press: Callable) -> void:
	var before := _requests.size()
	press.call()
	await _wait_frames(10)
	_check(_requests.size() == before and _deck._pending_action.is_empty(), label)


func _body(battle_id: String, action: String, card_key: String) -> Dictionary:
	return {"character_id": CHARACTER_ID, "battle_id": battle_id, "action": action, "card_key": card_key}


func _show_battle(data: Dictionary) -> void:
	_deck._view = "battle"
	_deck._battle_result_data.clear()
	_deck._battle_state = data
	_deck._show_battle_state()
	_deck._battle_timer.stop()


func _click_card(zone: String, index: int) -> bool:
	var card = _deck._battle_view.card_view(zone, index)
	if card == null:
		_check(false, "карта %s:%d есть на поле" % [zone, index])
		return false
	card.gui_input.emit(_left_click())
	return true


func _press_button(text: String) -> bool:
	for child in _deck._battle_buttons.get_children():
		if child is Button and (child as Button).text == text:
			(child as Button).pressed.emit()
			return true
	_check(false, "кнопка «%s» есть на экране боя" % text)
	return false


func _left_click() -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	return event


func _button_texts(container: Node) -> Array:
	var texts: Array = []
	for child in container.get_children():
		if child is Button:
			texts.append((child as Button).text)
	return texts


func _all_button_texts(node: Node) -> Array:
	var texts: Array = []
	if node is Button:
		texts.append((node as Button).text)
	for child in node.get_children():
		texts.append_array(_all_button_texts(child))
	return texts


func _label_texts(container: Node) -> Array:
	var texts: Array = []
	for child in container.get_children():
		if child is Label:
			texts.append((child as Label).text)
	return texts


func _rich_texts(container: Node) -> Array:
	var texts: Array = []
	for child in container.get_children():
		if child is RichTextLabel:
			texts.append((child as RichTextLabel).text)
	return texts


func _wait_frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame
		_pump_stub()


func _wait_requests(count: int) -> void:
	var started := Time.get_ticks_msec()
	while _requests.size() < count and Time.get_ticks_msec() - started < WAIT_LIMIT_MS:
		await get_tree().process_frame
		_pump_stub()


func _wait_idle() -> void:
	var started := Time.get_ticks_msec()
	while not _deck._pending_action.is_empty() and Time.get_ticks_msec() - started < WAIT_LIMIT_MS:
		await get_tree().process_frame
		_pump_stub()
	await get_tree().process_frame


# Стаб: принимает соединения, читает запрос целиком (заголовки и Content-Length), записывает его и отвечает.
func _pump_stub() -> void:
	while _server.is_connection_available():
		_sockets.append({"peer": _server.take_connection(), "buffer": PackedByteArray()})
	for socket in _sockets.duplicate():
		var peer: StreamPeerTCP = socket["peer"]
		var available := peer.get_available_bytes()
		if available > 0:
			var chunk: Array = peer.get_data(available)
			if chunk[0] == OK:
				var buffer: PackedByteArray = socket["buffer"]
				buffer.append_array(chunk[1])
				socket["buffer"] = buffer
		if _answer_if_complete(socket):
			_sockets.erase(socket)


func _answer_if_complete(socket: Dictionary) -> bool:
	var buffer: PackedByteArray = socket["buffer"]
	var text := buffer.get_string_from_utf8()
	var header_end := text.find("\r\n\r\n")
	if header_end < 0:
		return false
	var lines := text.substr(0, header_end).split("\r\n")
	var request_line := lines[0].split(" ")
	var length := 0
	for line in lines:
		if line.to_lower().begins_with("content-length:"):
			length = int(line.substr(15).strip_edges())
	# Заголовки ASCII, поэтому позиция в символах совпадает с байтовой.
	var body_start := header_end + 4
	if buffer.size() < body_start + length:
		return false
	var body_text := buffer.slice(body_start, body_start + length).get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(body_text) if not body_text.is_empty() else {}
	_requests.append({
		"method": request_line[0],
		"path": request_line[1],
		"body": parsed if parsed is Dictionary else {},
	})
	_send_reply(socket["peer"])
	return true


func _send_reply(peer: StreamPeerTCP) -> void:
	var payload := JSON.stringify(_reply_body).to_utf8_buffer()
	var status_text := "OK" if _reply_status == 200 else "Error"
	var head := "HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % [
		_reply_status,
		status_text,
		payload.size(),
	]
	peer.put_data(head.to_utf8_buffer())
	peer.put_data(payload)
	peer.disconnect_from_host()


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


func _teardown() -> void:
	for socket in _sockets:
		(socket["peer"] as StreamPeerTCP).disconnect_from_host()
	_sockets.clear()
	_server.stop()
	_deck.queue_free()
	await get_tree().process_frame
	GameSession.clear()
	ApiClient.base_url = "http://127.0.0.1:8765"
	ApiClient.token = ""


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
