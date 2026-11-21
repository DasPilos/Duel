extends Node

const CHAT_SCRIPT := preload("res://scripts/location_chat_panel.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_whisper_parsing()
	_check_panel()
	await _check_economy()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_chat_smoke_test: OK")
	await get_tree().create_timer(0.2).timeout
	get_tree().quit(code)


func _check_whisper_parsing() -> void:
	var anna := {"name": "Аня", "character_id": 5}
	var parsed: Dictionary = CHAT_SCRIPT.parse_whisper("/w Аня привет", [anna])
	_check(int(parsed["target"]["character_id"]) == 5 and parsed["body"] == "привет" and parsed["error"] == "", "шёпот находит игрока и текст")
	_check(int(CHAT_SCRIPT.parse_whisper("/w аня привет", [anna])["target"]["character_id"]) == 5, "имя ищется без учёта регистра")
	_check(CHAT_SCRIPT.parse_whisper("/w", [anna])["error"] == "Формат: /w <имя> текст", "/w без имени — ошибка формата")
	_check(CHAT_SCRIPT.parse_whisper("/w Аня", [anna])["error"] == "Введите текст сообщения после имени", "нет текста после имени")
	_check(CHAT_SCRIPT.parse_whisper("/w Бор текст", [anna])["error"] == "Игрок не найден в локации: Бор", "неизвестный игрок")
	_check(CHAT_SCRIPT.parse_whisper("/w Аняк привет", [anna])["error"] == "Игрок не найден в локации: Аняк", "имя должно заканчиваться пробелом")
	var petrova := {"name": "Аня Петрова", "character_id": 6}
	var long_match: Dictionary = CHAT_SCRIPT.parse_whisper("/w Аня Петрова привет", [anna, petrova])
	_check(int(long_match["target"]["character_id"]) == 6 and long_match["body"] == "привет", "побеждает самое длинное совпадение имени")


func _check_panel() -> void:
	var panel = CHAT_SCRIPT.new()
	add_child(panel)
	var sent: Array = []
	panel.message_submitted.connect(func(text: String, recipient_id: int) -> void: sent.append([text, recipient_id]))
	panel.apply_snapshot([
		{"sender_id": 1, "sender": "Я", "recipient_id": null, "text": "общий", "time_text": "10:00:00"},
		{"sender_id": 2, "sender": "Аня", "recipient_id": 1, "text": "тебе", "time_text": "10:00:01"},
		{"sender_id": 3, "sender": "Бор", "recipient_id": 4, "text": "чужой шёпот", "time_text": "10:00:02"},
	], [{"name": "Аня", "character_id": 2}], 1)
	_check(panel._visible_messages().size() == 1 and panel._visible_messages()[0]["text"] == "общий", "вкладка «Общий» показывает только публичные сообщения")
	panel._select_tab("Личный")
	_check(panel._visible_messages().size() == 1 and panel._visible_messages()[0]["text"] == "тебе", "вкладка «Личный» показывает только шёпоты с участием игрока")
	panel._input.text = "привет"
	panel._submit()
	_check(panel._status.text == "Напишите /w <имя> текст, чтобы начать личный диалог" and sent.is_empty(), "личная вкладка без собеседника не отправляет сообщение")
	panel._input.text = "/w Аня привет"
	panel._submit()
	_check(sent == [["привет", 2]], "/w отправляет текст выбранному игроку")
	panel.mark_sent(2)
	_check(panel._tab == "Личный" and panel._input.text.is_empty() and panel._status.text == "Собеседник: Аня", "после шёпота открывается «Личный» с именем собеседника")
	panel._select_tab("Общий")
	panel._input.text = "всем привет"
	panel._on_text_submitted("всем привет")
	_check(sent[-1] == ["всем привет", 0], "публичное сообщение уходит без получателя")
	panel._input.text = "/w Бор текст"
	panel._submit()
	_check(panel._status.text == "Игрок не найден в локации: Бор" and sent.size() == 2, "шёпот неизвестному игроку показывает ошибку")
	panel.open_panel()
	_check(panel.is_open(), "панель открывается")
	panel._input.text = "  "
	panel._on_text_submitted("  ")
	_check(not panel.is_open(), "Enter на пустом вводе закрывает чат, как в Python")
	panel.open_panel()
	panel.close_panel()
	_check(not panel.is_open(), "close_panel закрывает чат")
	panel.clear_messages()
	_check(panel._visible_messages().is_empty(), "clear_messages очищает историю")
	panel.queue_free()


func _check_economy() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120,
		"silver": 0, "gold": 0, "carried_weight_kg": 0.0}
	ApiClient._http.timeout = 0.5
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	economy._chat_timer.stop()
	await _wait_idle(economy)
	_check(economy._chat_location() == "city", "в городе чат работает с локацией city")

	economy._status.text = "маркер"
	economy._poll_chat()
	_check(economy._pending_action == "chat_snapshot", "опрос чата запрашивает снимок локации")
	await _wait_idle(economy)
	_check(economy._status.text == "маркер", "ошибка опроса чата не перезаписывает общий статус")

	economy._pending_action = "chat_snapshot"
	economy._chat_request_location = "city"
	economy._on_api_completed(true, {"messages": [
		{"sender_id": 42, "sender": "Тест", "recipient_id": null, "text": "первое", "time_text": "10:00:00"},
		{"sender_id": 7, "sender": "Аня", "recipient_id": null, "text": "второе", "time_text": "10:00:01"},
	], "occupants": [{"name": "Аня", "character_id": 7}]})
	_check(economy._chat_panel._visible_messages().size() == 2, "снимок города попадает в общий список чата")
	_check(economy._status.text == "маркер", "успешный опрос не трогает общий статус")

	economy._pending_action = "chat_snapshot"
	economy._chat_request_location = "tavern"
	economy._on_api_completed(true, {"messages": [], "occupants": []})
	_check(economy._chat_panel._visible_messages().size() == 2, "ответ о другой локации игнорируется")

	economy._set_view("tavern")
	_check(economy._chat_location() == "tavern" and economy._chat_panel._messages.is_empty(), "переход в таверну переключает чат и очищает прежние сообщения")
	economy._set_view("city")

	economy._chat_panel.message_submitted.emit("привет", 0)
	_check(economy._pending_action == "chat_send", "сообщение уходит запросом chat_send")
	await _wait_idle(economy)
	_check(not economy._chat_panel._status.text.is_empty(), "ошибка отправки показывается в чате")
	_check(economy._status.text == "маркер", "ошибка отправки не перезаписывает общий статус")

	var enter := InputEventKey.new()
	enter.keycode = KEY_ENTER
	enter.pressed = true
	economy._unhandled_input(enter)
	_check(economy._chat_panel.is_open(), "Enter открывает чат, если поле ввода не занято")
	var esc := InputEventKey.new()
	esc.keycode = KEY_ESCAPE
	esc.pressed = true
	economy._unhandled_input(esc)
	_check(not economy._chat_panel.is_open() and not economy._exit_menu.blocks_input(), "первый Esc закрывает чат и не открывает меню выхода")
	economy._close_window()
	economy._unhandled_input(esc)
	_check(economy._exit_menu.blocks_input(), "Esc без открытого чата открывает меню выхода")

	remove_child(economy)
	economy.free()
	GameSession.clear()


func _wait_idle(economy) -> void:
	var waited := 0.0
	while not economy._pending_action.is_empty() and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05
	_check(economy._pending_action.is_empty(), "запрос экономики завершается")


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
