extends Node

const RULES := preload("res://scripts/economy_contract_rules.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const FIXTURE_DIR := "res://tests/fixtures/economy/"
const PORT_FIRST := 19400
const PORT_LAST := 19460
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
	_check_contract_rules()
	await _check_live_loads()
	_server.stop()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_contract_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_contract_rules() -> void:
	var citizens := RULES.items(_fixture("traveling_citizens.json"), "citizens")
	_check(citizens.size() == 2, "фикстура горожан содержит двух элементов")
	for citizen in citizens:
		_check(RULES.missing_fields(citizen, RULES.TRAVELER_FIELDS).is_empty(), "горожанин содержит поля, которые читает UI")
		_check(RULES.kind_mismatches(citizen, RULES.TRAVELER_KINDS).is_empty(), "типы полей горожанина совпадают с контрактом")

	var convoys := RULES.items(_fixture("traveling_convoys.json"), "convoys")
	_check(convoys.size() == 2, "фикстура повозок содержит два элемента")
	for convoy in convoys:
		_check(RULES.missing_fields(convoy, RULES.CONVOY_FIELDS).is_empty(), "повозка содержит поля, которые читает UI")
		_check(RULES.kind_mismatches(convoy, RULES.CONVOY_KINDS).is_empty(), "типы полей повозки совпадают с контрактом")

	var population: Dictionary = _fixture("castle_population.json").get("population", {})
	_check(RULES.missing_fields(population, RULES.POPULATION_FIELDS).is_empty(), "население содержит поля, которые читает UI")
	_check(RULES.kind_mismatches(population, RULES.POPULATION_KINDS).is_empty(), "типы полей населения совпадают с контрактом")
	var population_citizens := RULES.items(population, "citizens")
	_check(population_citizens.size() == 2, "население содержит двух жителей")
	for citizen in population_citizens:
		_check(RULES.missing_fields(citizen, RULES.CITIZEN_FIELDS).is_empty(), "житель содержит поля города")
	for worksite in RULES.items(population, "worksites"):
		_check(RULES.missing_fields(worksite, RULES.WORKSITE_FIELDS).is_empty(), "место работы содержит поля города")

	var building: Dictionary = _fixture("building_barn.json").get("building", {})
	_check(RULES.missing_fields(building, RULES.BUILDING_FIELDS).is_empty(), "здание содержит поля, которые читает UI")
	_check(RULES.kind_mismatches(building, RULES.BUILDING_KINDS).is_empty(), "типы полей здания совпадают с контрактом")
	for slot in RULES.items(building, "worker_slots"):
		_check(RULES.missing_fields(slot, RULES.WORKER_SLOT_FIELDS).is_empty(), "слот здания содержит поля UI")

	_check(RULES.items({"citizens": "не массив"}, "citizens").is_empty(), "ответ с неверным типом даёт пустой список")
	_check(RULES.items(null, "citizens").is_empty(), "пустой ответ даёт пустой список")
	_check(RULES.missing_fields({"name": "Аня"}, RULES.TRAVELER_FIELDS).size() == RULES.TRAVELER_FIELDS.size() - 1,
		"missing_fields находит отсутствующие поля")
	_check(RULES.kind_mismatches({"name": 5}, {"name": "string"}) == ["name"], "kind_mismatches находит неверный тип")


func _check_live_loads() -> void:
	GameSession.clear()
	GameSession.character = {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120,
		"silver": 0, "gold": 0, "carried_weight_kg": 0.0}
	GameSession.world = {}
	GameSession.world_token = "test-world-token"
	var port := _listen()
	_check(port > 0, "тестовый сервер слушает 127.0.0.1")
	if port <= 0:
		return
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	economy._chat_timer.stop()
	_check(economy._pending_action.is_empty(), "без адреса мира при открытии нет автозапроса")
	ApiClient.set_server_url("http://127.0.0.1:%d" % port)

	economy._load_city()
	_check(economy._view == "city" and economy._pending_action == "city", "_load_city переводит вид в город")
	await _serve({"/api/castle/42/population": _fixture("castle_population.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/castle/42/population", "_load_city запрашивает население персонажа")
	_check(economy._content.get_node("CastleView").visible, "_load_city показывает окно замка")
	_check(economy._castle_view._summary_label.text.begins_with("Население 2 / 6"), "окно замка показывает население")
	_check(economy._castle_view._citizen_rows.get_child_count() == 2, "окно замка рисует строки двух жителей")

	economy._on_castle_action("assign_citizen", {"citizen_id": 7, "worksite_key": "barn", "slot_index": 0})
	await _serve({"/api/castle/42/citizens/7/assign": _fixture("castle_population.json")})
	await _wait_idle(economy)
	var assign_sent: Variant = JSON.parse_string(_requested_bodies.back())
	_check(_requested_paths.back() == "/api/castle/42/citizens/7/assign" and assign_sent is Dictionary
		and assign_sent.get("building") == "barn" and int(assign_sent.get("slot_index", -1)) == 0,
		"назначение горожанина уходит POST с зданием и слотом из окна")
	_check(economy._castle_view._message_label.text == "Горожанин отправлен к месту работы.", "после назначения замок пишет подтверждение")

	economy._on_castle_action("treasury_deposit", {"maximum_copper": 500})
	_check(economy._treasury_dialog.is_open() and economy._treasury_dialog.maximum() == 500,
		"взнос в казну открывает диалог монет с личным максимумом")
	economy._treasury_dialog._quantity = 200
	economy._treasury_dialog._on_confirm_pressed()
	_check(not economy._treasury_dialog.is_open(), "подтверждение монет закрывает диалог")
	await _serve({"/api/castle/42/treasury": _fixture("castle_population.json")})
	await _wait_idle(economy)
	var treasury_sent: Variant = JSON.parse_string(_requested_bodies.back())
	_check(_requested_paths.back() == "/api/castle/42/treasury" and treasury_sent is Dictionary
		and treasury_sent.get("direction") == "deposit" and int(treasury_sent.get("amount_copper", 0)) == 200,
		"подтверждённый взнос уходит POST с направлением и медями")
	_check(economy._castle_view._message_label.text == "Монеты внесены в казну.", "после взноса замок пишет подтверждение")

	economy._on_castle_action("upgrade_start", {"upgrade_id": "walls"})
	await _serve({"/api/castle/42/upgrades/walls": _fixture("castle_population.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/castle/42/upgrades/walls", "улучшение замка уходит POST на свой id")

	economy._open_stable_window()
	_check(economy._view == "stable" and economy._pending_action == "building", "конюшня открывает своё окно и запрашивает состояние")
	await _serve({"/api/buildings/stable/42": _fixture("building_stable.json")})
	await _serve({"/api/map/terrain": _fixture("world_roads.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/map/terrain", "после состояния конюшни запрашиваются маршруты карты")
	_check(economy._stable_window.visible and economy._stable_window.window_title() == "Конюшня", "окно конюшни показывает название")

	economy._on_stable_view_action("dispatch", {"cart_id": "cart-7", "horse_ids": [11], "driver_citizen_id": 5,
		"destination_building_id": "lumber_camp", "resource_ids": ["wood"], "pinned": false})
	await _serve({"/api/buildings/stable/42/transport/dispatch": _fixture("building_stable.json")})
	await _wait_idle(economy)
	var dispatch_sent: Variant = JSON.parse_string(_requested_bodies.back())
	_check(_requested_paths.back() == "/api/buildings/stable/42/transport/dispatch" and dispatch_sent is Dictionary
		and dispatch_sent.get("cart_id") == "cart-7" and int(dispatch_sent.get("driver_citizen_id", 0)) == 5
		and dispatch_sent.get("destination_building_id") == "lumber_camp",
		"отправка повозки уходит POST с повозкой, возницей и маршрутом из окна")
	economy._close_window()
	_check(economy._view == "map" and not economy._stable_window.visible, "закрытие окна конюшни прячет её")

	economy._load_forge()
	_check(economy._view == "forge" and economy._pending_action == "forge", "кузница открывает своё окно и запрашивает очередь")
	await _serve({"/api/forge/42": _fixture("forge_state.json")})
	await _wait_idle(economy)
	_check(economy._content.get_node("ForgeView").visible and economy._window_title.text == "Кузница", "окно кузницы показывает заголовок после ответа")
	economy._on_forge_view_action("create_order", {"item_id": 90})
	await _serve({"/api/forge/42/orders": _fixture("forge_state.json")})
	await _wait_idle(economy)
	var forge_sent: Variant = JSON.parse_string(_requested_bodies.back())
	_check(_requested_paths.back() == "/api/forge/42/orders" and forge_sent is Dictionary and int(forge_sent.get("item_id", 0)) == 90,
		"заказ рецепта уходит POST с item_id")
	economy._close_window()

	economy._selected_building = "barn"
	economy._load_building()
	_check(economy._view == "storage" and economy._pending_action == "building", "_load_building открывает окно склада для амбара")
	await _serve({"/api/buildings/barn/42": _fixture("building_barn.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/barn/42", "_load_building берёт ключ выбранного здания")
	_check(economy._storage_window.visible and economy._storage_window.window_title() == "Амбар", "окно склада показывает название амбара")
	_check(economy._window_title.text == "Амбар", "заголовок окна склада — название амбара")

	economy._load_travelers()
	_check(economy._view == "travelers" and economy._pending_action == "travelers", "_load_travelers переводит вид в горожан")
	await _serve({"/api/world/traveling-citizens?character_id=42": _fixture("traveling_citizens.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/world/traveling-citizens?character_id=42", "_load_travelers запрашивает горожан персонажа")
	var traveler_rows: Node = economy._content.get_node_or_null("TravelerControls")
	_check(traveler_rows != null and traveler_rows.get_child_count() == 2, "_load_travelers рисует двух горожан в пути")
	if traveler_rows != null and traveler_rows.get_child_count() == 2:
		_check((traveler_rows.get_child(0) as Label).text == "Аня · Лагерь лесорубов · Едет на работу · осталось 02:05",
			"строка горожанина собрана из name, job_building, travel_direction и travel_seconds_left")
		_check((traveler_rows.get_child(1) as Label).text == "Бор · Крестьянское поселение · Возвращается · осталось 01:05",
			"возвращающийся горожанин показан как «Возвращается»")

	economy._load_convoys()
	_check(economy._view == "convoys" and economy._pending_action == "convoys", "_load_convoys переводит вид в повозки")
	await _serve({"/api/world/traveling-convoys?character_id=42": _fixture("traveling_convoys.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/world/traveling-convoys?character_id=42", "_load_convoys запрашивает повозки персонажа")
	var convoy_rows: Node = economy._content.get_node_or_null("ConvoyControls")
	_check(convoy_rows != null and convoy_rows.get_child_count() == 2, "_load_convoys рисует две повозки")
	if convoy_rows != null and convoy_rows.get_child_count() == 2:
		var first_row := convoy_rows.get_child(0) as HBoxContainer
		_check((first_row.get_child(0) as Label).text == "Крестьянский обоз · cart-7 → Лагерь лесорубов · возница: Аня · Едет к объекту · закреплён",
			"строка закреплённой повозки собрана из полей контракта")
		_check((first_row.get_child(1) as Button).text == "Открепить", "закреплённая повозка предлагает открепить")
		var second_row := convoy_rows.get_child(1) as HBoxContainer
		_check((second_row.get_child(0) as Label).text == "Лёгкая повозка · cart-8 → Крестьянское поселение · возница: Бор · Ожидает ресурсы · разовый рейс",
			"строка разового рейса использует status")
		_check((second_row.get_child(1) as Button).text == "Закрепить", "разовый рейс предлагает закрепить")

	economy._open_workshop_window()
	_check(economy._view == "workshop" and economy._pending_action == "workshop_refresh", "мастерская открывает окно и запрашивает состояние конюшни")
	await _serve({"/api/buildings/stable/42": _fixture("workshop_state.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/stable/42", "мастерская берёт конюшню персонажа")
	var workshop = economy._content.get_node_or_null("WorkshopView")
	_check(workshop != null and workshop.visible and economy._building_window_title == "Городская мастерская",
		"окно мастерской показано под своим заголовком")
	workshop._select_tab("carts")
	_check(workshop._order_buttons.has(1) and not workshop._order_buttons[1].disabled, "на вкладке повозок заказ лёгкой повозки доступен")
	workshop._on_order_pressed(1)
	_check(economy._pending_action == "workshop_order", "заказ повозки уходит запросом")
	await _serve({"/api/buildings/stable/42/cart/purchase": _fixture("workshop_state.json")})
	await _wait_idle(economy)
	_check(_requested_paths.back() == "/api/buildings/stable/42/cart/purchase", "заказ повозки отправляется POST на покупку")
	_check(workshop._message_label.text == ECONOMY_SCRIPT.WORKSHOP_ORDER_MESSAGE, "после заказа мастерская пишет подтверждение")
	economy._close_window()
	_check(economy._view == "map" and not workshop.visible, "закрытие окна прячет мастерскую")

	remove_child(economy)
	economy.free()
	GameSession.clear()


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % file_name)
	return {}


func _listen() -> int:
	for port in range(PORT_FIRST, PORT_LAST):
		if _server.listen(port, "127.0.0.1") == OK:
			return port
	return -1


# Принимает один HTTP-запрос и отвечает фикстурой по пути (вместе с query-строкой).
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
		text = JSON.stringify({"error": "нет фикстуры для " + path})
	var bytes := text.to_utf8_buffer()
	var head := "%s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % [status_line, bytes.size()]
	_peer.put_data(head.to_utf8_buffer())
	_peer.put_data(bytes)


func _wait_idle(economy) -> void:
	var deadline := Time.get_ticks_msec() + SERVE_TIMEOUT_MS
	while not economy._pending_action.is_empty() and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.02).timeout
	_check(economy._pending_action.is_empty(), "запрос экономики завершается")


# Читает запрос целиком: заголовки и тело по Content-Length (POST мастерской).
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
