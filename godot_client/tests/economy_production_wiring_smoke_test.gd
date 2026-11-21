extends Node

# Связка производственного окна с миром (economy_world.gd): запросы карточек улучшения, возврат горожанина,
# таймер обновления, блоки при полном складе и незавершённой работе, сброс ожидания при ошибке.
# Запросы уходят на локальный тестовый сервер, поэтому видно и путь, и тело запроса.
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const RULES := preload("res://scripts/economy_production_rules.gd")
const FIXTURE_FILE := "res://tests/fixtures/economy/castle_population.json"
const PORT_FIRST := 19470
const PORT_LAST := 19520
const SERVE_TIMEOUT_MS := 8000

var _failures: Array[String] = []
var _checks := 0
var _server := TCPServer.new()
var _peer: StreamPeerTCP
var _requested_paths: Array[String] = []
var _requested_bodies: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	GameSession.clear()
	GameSession.character = {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120,
		"silver": 0, "gold": 0, "carried_weight_kg": 0.0}
	GameSession.world = {}
	GameSession.world_token = "test-world-token"
	var port := _listen()
	_check(port > 0, "тестовый сервер слушает 127.0.0.1")
	if port > 0:
		await _check_world(port)
	_server.stop()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_production_wiring_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_world(port: int) -> void:
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	economy._chat_timer.stop()
	ApiClient.set_server_url("http://127.0.0.1:%d" % port)
	economy._character_id = 42
	await _check_upgrade_requests(economy)
	await _check_recall_and_timer(economy)
	_check_guards(economy)
	remove_child(economy)
	economy.free()


func _check_upgrade_requests(economy) -> void:
	economy._selected_building = "farm"
	economy._view = "building"
	economy._building = _state("farm", {}, null)
	economy._on_production_view_action("production_upgrade", {"upgrade_id": "ration"})
	_check(economy._pending_action == "building_action", "кнопка карточки ставит запрос действия здания")
	await _serve({"/api/buildings/farm/42/farm/upgrade": {"building": _state("farm", {"ration": true}, null)}})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/farm/42/farm/upgrade", "улучшение фермы уходит POST на farm/upgrade")
	var sent: Variant = JSON.parse_string(_requested_bodies.back())
	_check(sent is Dictionary and str(sent.get("upgrade_id", "")) == "ration", "тело запроса содержит upgrade_id")
	_check(economy._production_window._message_label.text.is_empty(), "успешное улучшение очищает сообщение окна")

	economy._selected_building = "lumber_camp"
	economy._building = _state("lumber_camp", {}, null)
	economy._on_production_view_action("production_upgrade", {"upgrade_id": "strong_handle"})
	await _serve({"/api/buildings/lumber_camp/42/lumber-camp/upgrade":
		{"building": _state("lumber_camp", {"strong_handle": true}, null)}})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/lumber_camp/42/lumber-camp/upgrade",
		"улучшение лесопилки уходит POST на lumber-camp/upgrade")
	sent = JSON.parse_string(_requested_bodies.back())
	_check(sent is Dictionary and str(sent.get("upgrade_id", "")) == "strong_handle", "тело лесопилки содержит upgrade_id")


func _check_recall_and_timer(economy) -> void:
	economy._selected_building = "farm"
	economy._view = "building"
	economy._building = _state("farm", {}, null)
	economy._on_production_view_action("fire", {"slot_index": 1})
	_check(economy._pending_action == "building_citizen_recall", "снятие горожанина идёт через возврат в город")
	await _serve({"/api/castle/42/citizens/5/recall": _fixture()})
	_check(_requested_paths.back() == "/api/castle/42/citizens/5/recall", "возврат горожанина уходит POST на его id")
	await _serve({"/api/buildings/farm/42": {"building": _state("farm", {}, null)}})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/farm/42", "после возврата окно перечитывает здание, как load() в Python")
	_check(economy._production_window._message_label.text == RULES.MSG_RECALLED, "после возврата пишем сообщение")

	economy._view = "map"
	economy._on_building_timer()
	_check(economy._pending_action.is_empty(), "таймер не обновляет чужое окно")
	economy._view = "building"
	economy._on_building_timer()
	_check(economy._pending_action == "building", "таймер обновляет открытое окно здания")
	await _serve({"/api/buildings/farm/42": {"building": _state("farm", {}, null)}})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/farm/42", "обновление здания идёт GET на открытый тип здания")
	economy._view = "storage"
	economy._on_building_timer()
	_check(economy._pending_action == "building", "таймер обновляет открытый склад, как _refresh_if_due в Python")
	await _serve({"/api/buildings/farm/42": {"building": _state("farm", {}, null)}})
	await _wait_idle(economy)


func _check_guards(economy) -> void:
	economy._view = "building"
	economy._selected_building = "farm"
	economy._building = _state("farm", {}, null)
	economy._pending_action = "building_action"
	economy._on_production_view_action("production_upgrade", {"upgrade_id": "ration"})
	_check(economy._production_window._message_label.text == RULES.MSG_BUSY, "второе действие при ожидании сервера отклоняется")
	economy._pending_action = ""

	economy._pending_action = "building_action"
	economy._on_api_completed(false, "Недостаточно серебра")
	_check(economy._pending_action.is_empty(), "ошибка действия снимает ожидание")
	_check(economy._production_window._message_label.text == "Недостаточно серебра", "ошибка карточки выводится в окне производства")

	var full := _state("farm", {}, null)
	full["storage"] = {"limit": 100, "wheat": 100}
	economy._building = full
	economy._toggle_player_slot(0)
	_check(economy._production_window._message_label.text == RULES.MSG_STORAGE_FULL, "встать на добычу при полном складе нельзя")
	_check(economy._pending_action.is_empty(), "при полном складе запрос не уходит")

	var working := _state("farm", {}, null)
	working["worker_slots"] = [{"slot_index": 0, "occupied": true, "worker_id": "player:42", "is_player": true,
		"resource": "wheat", "resources": ["wheat"]}]
	working["player_work"] = {"slot_index": 0}
	economy._building = working
	economy._close_window()
	_check(economy._view == "building", "с места добычи окно не закрывается")
	_check(economy._production_window._message_label.text == RULES.MSG_LEAVE_BLOCKED, "с места добычи пишем, что нужно завершить работу")
	economy._building = _state("farm", {}, null)
	economy._close_window()
	_check(economy._view == "map", "без работы окно закрывается")


func _state(building: String, completed: Dictionary, active: Variant) -> Dictionary:
	var key := "lumber_camp_upgrades" if building == "lumber_camp" else "farm_upgrades"
	var state := {
		"building": building,
		"level": 1,
		"workers": 1,
		"max_workers": 2,
		"storage": {"limit": 100, "wheat": 10},
		"storage_full": false,
		"worker_slots": [
			{"slot_index": 0, "occupied": false, "worker_id": null, "resource": "wheat", "resources": ["wheat"], "is_player": false},
			{"slot_index": 1, "occupied": true, "worker_id": "citizen:5", "worker_name": "Анна", "resource": "wheat", "resources": ["wheat"], "is_player": false},
		],
		"player_work": null,
		"upgrade": null,
		"warehouse_storage": {"wood": 500},
		"spendable_treasury_copper": 100000,
	}
	state[key] = {"completed": completed, "active_upgrade_id": active, "seconds_left": 0}
	return state


func _fixture() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_FILE))
	return parsed if parsed is Dictionary else {}


func _listen() -> int:
	for port in range(PORT_FIRST, PORT_LAST):
		if _server.listen(port, "127.0.0.1") == OK:
			return port
	return -1


# Принимает один HTTP-запрос и отвечает данными по пути (вместе с query-строкой).
func _serve(responses: Dictionary) -> void:
	var deadline := Time.get_ticks_msec() + SERVE_TIMEOUT_MS
	_peer = null
	while _peer == null and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		if _server.is_connection_available():
			_peer = _server.take_connection()
	if _peer == null:
		_check(false, "запрос не дошёл до тестового сервера")
		return
	var raw := await _read_request()
	var path := raw.get_slice("\r\n", 0).get_slice(" ", 1)
	_requested_paths.append(path)
	var parts := raw.split("\r\n\r\n", true, 1)
	_requested_bodies.append(parts[1] if parts.size() == 2 else "")
	var status_line := "HTTP/1.1 200 OK"
	var text := ""
	if responses.has(path):
		text = JSON.stringify(responses[path])
	else:
		status_line = "HTTP/1.1 404 Not Found"
		text = JSON.stringify({"error": "нет ответа для " + path})
	var bytes := text.to_utf8_buffer()
	var head := "%s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % [status_line, bytes.size()]
	_peer.put_data(head.to_utf8_buffer())
	_peer.put_data(bytes)


func _wait_idle(economy) -> void:
	var deadline := Time.get_ticks_msec() + SERVE_TIMEOUT_MS
	while not economy._pending_action.is_empty() and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.02).timeout
	_check(economy._pending_action.is_empty(), "запрос окна производства завершается")


# Читает запрос целиком: заголовки и тело по Content-Length (POST действий).
func _read_request() -> String:
	var buffer := PackedByteArray()
	var deadline := Time.get_ticks_msec() + SERVE_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		_peer.poll()
		var available := _peer.get_available_bytes()
		if available > 0:
			var chunk: Array = _peer.get_data(available)
			buffer.append_array(chunk[1] as PackedByteArray)
		var text := buffer.get_string_from_utf8()
		var header_end := text.find("\r\n\r\n")
		if header_end >= 0 and buffer.size() >= header_end + 4 + _content_length(text.substr(0, header_end)):
			break
	return buffer.get_string_from_utf8()


func _content_length(headers: String) -> int:
	for line in headers.split("\r\n"):
		if line.to_lower().begins_with("content-length:"):
			return int(line.get_slice(":", 1).strip_edges())
	return 0


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
