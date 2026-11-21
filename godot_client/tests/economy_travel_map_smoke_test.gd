extends Node

const RULES := preload("res://scripts/economy_travel_rules.gd")
const TRAVEL_MAP_SCRIPT := preload("res://scripts/economy_travel_map.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const FIXTURE_DIR := "res://tests/fixtures/economy/"
const PORT_FIRST := 19470
const PORT_LAST := 19520
const SERVE_TIMEOUT_MS := 8000
const POSITION_TOLERANCE := 0.05

var _failures: Array[String] = []
var _checks := 0
var _server := TCPServer.new()
var _peer: StreamPeerTCP
var _requested_paths: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	_check_client_positions_match_server()
	_check_travel_map()
	await _check_request_chain_and_lists()
	_server.stop()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_travel_map_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_rules() -> void:
	var roads: Dictionary = _fixture("world_roads.json").get("terrain", {}).get("roads", {})
	var routes: Array = roads.get("routes", [])
	_check(routes.size() == 5, "фикстура маршрутов содержит пять дорог")
	var gates: Dictionary = _fixture("world_roads.json").get("city_gates", {})
	for route in routes:
		var first: Array = route["tiles"][0]
		_check(gates.get(str(route["gate_id"]), []) == first, "маршрут %s начинается у своих ворот" % str(route["building_id"]))
	_check(str(RULES.route_for_building(routes, "farm").get("building_id", "")) == "wheat_farm", "ферма из карты строений ведёт на маршрут wheat_farm")
	_check(str(RULES.route_for_building(routes, "lumber_camp").get("name", "")) == "Лагерь лесорубов", "лесопилка находит свой маршрут")
	_check(RULES.route_for_building(routes, "unknown_building").is_empty(), "неизвестное строение маршрута не имеет")

	var wheat: Dictionary = RULES.route_for_building(routes, "farm")
	var first_center := RULES.route_points(wheat["tiles"])[0]
	var last_center := RULES.route_points(wheat["tiles"])[-1]
	var at_start := RULES.route_position(wheat["tiles"], 0.0)
	_check(is_equal_approx(float(at_start["x"]), first_center.x) and is_equal_approx(float(at_start["y"]), first_center.y),
		"доля 0 — центр первого тайла маршрута")
	var at_end := RULES.route_position(wheat["tiles"], 1.0)
	_check(is_equal_approx(float(at_end["x"]), last_center.x) and is_equal_approx(float(at_end["y"]), last_center.y),
		"доля 1 — центр последнего тайла маршрута")
	_check(is_equal_approx(last_center.x, 656.0) and is_equal_approx(last_center.y, 1008.0), "конец маршрута фермы совпадает с позицией повозки в фикстуре")

	_check(str(RULES.route_position([[0, 0], [1, 0]], 0.5).get("direction", "")) == "e", "движение вправо — направление e")
	_check(str(RULES.route_position([[1, 0], [0, 0]], 0.5).get("direction", "")) == "w", "движение влево — направление w")
	_check(str(RULES.route_position([[0, 1], [0, 0]], 0.5).get("direction", "")) == "n", "движение вверх — направление n")
	_check(str(RULES.route_position([[0, 0], [1, 1]], 0.5).get("direction", "")) == "se", "диагональ вниз-вправо — направление se")
	_check(RULES.route_position([], 0.5).is_empty(), "пустой маршрут не даёт позиции")

	var convoys: Array = _fixture("traveling_convoys.json").get("convoys", [])
	_check(RULES.progress_percent(convoys[0]) == 60, "прогресс повозки берётся из progress_percent")
	_check(RULES.progress_percent({"travel_seconds": 600, "eta_seconds": 240, "direction": "outbound"}) == 60,
		"без progress_percent прогресс туда считается из ETA")
	_check(RULES.progress_percent({"travel_seconds": 300, "eta_seconds": 65, "direction": "returning"}) == 22,
		"без progress_percent прогресс обратно считается из ETA")
	_check(RULES.progress_percent({"progress_percent": 150}) == 100, "прогресс ограничивается сверху")

	var sprites := RULES.sprite_names("peasant")
	_check(str(sprites["wagon"]) == "cart_peasant" and str(sprites["harness"]) == "harness_peasant"
		and str(sprites["horse"]) == "horse" and str(sprites["driver"]) == "driver", "спрайты повозки названы как в map_travel.py")
	_check(str(RULES.sprite_names("").get("wagon", "")) == "cart_light", "пустой ключ повозки — лёгкая повозка")
	_check(RULES.cart_icon_name("peasant") == "cart_peasant" and RULES.cart_icon_name("").is_empty(),
		"иконка повозки — cart_{ключ}, без ключа иконки нет")
	_check(RULES.cart_icon_rect(Rect2(100.0, 200.0, 80.0, 16.0)).is_equal_approx(Rect2(64.0, 192.0, 32.0, 32.0)),
		"иконка 32 px левее подписи с зазором 4 px и центром по высоте подписи")
	_check(is_equal_approx(RULES.rotation_for(RULES.DIRECTION_VECTORS["e"]), PI / 2.0), "поворот «восток» — четверть оборота")
	_check(is_equal_approx(RULES.rotation_for(RULES.DIRECTION_VECTORS["n"]), 0.0), "поворот «север» — без поворота")
	var root := RULES.assets_root(ProjectSettings.globalize_path("res://"))
	for sprite_name in ["cart_light", "cart_peasant", "harness_peasant", "horse", "driver"]:
		_check(FileAccess.file_exists(RULES.transport_sprite_path(root, sprite_name)), "спрайт %s лежит в assets/ui/transport" % sprite_name)
	_check(not FileAccess.file_exists("res://assets/ui/transport/cart_light.png"), "спрайты не скопированы в проект")

	var citizens: Array = _fixture("traveling_citizens.json").get("citizens", [])
	var citizen_entries := RULES.citizen_entries(citizens)
	_check(citizen_entries.size() == 2 and str(citizen_entries[0]["entity_kind"]) == "citizen", "горожане с позицией сервера попадают на карту")
	_check(int(citizen_entries[0]["eta_seconds"]) == 125, "горожанин: ETA берётся из eta_seconds")
	var no_position: Dictionary = citizens[0].duplicate()
	no_position["position_x"] = null
	_check(RULES.citizen_entries([no_position]).is_empty(), "горожанин без позиции на карту не попадает")

	var now_entries := RULES.convoy_entries(convoys, routes, 0.0)
	_check(now_entries.size() == 2 and str(now_entries[0]["entity_kind"]) == "wagon", "обе повозки с маршрутами попадают на карту")
	var later_entries := RULES.convoy_entries(convoys, routes, 10.0)
	_check(int(later_entries[0]["eta_seconds"]) == 230, "ETA повозки уменьшается на прошедшее время")
	_check(int(now_entries[0]["eta_seconds"]) == 240, "ETA повозки без прошедшего времени равна ответу сервера")
	var unknown: Dictionary = convoys[0].duplicate()
	unknown["destination_building_id"] = "no_such_route"
	_check(RULES.convoy_entries([unknown], routes, 0.0).is_empty(), "повозка к неизвестному маршруту не выводится")

	var lines := RULES.tooltip_lines(now_entries[0])
	_check(lines.has("Экипаж: Аня") and lines.has("Лошади: Гнедка") and lines.has("Маршрут: Лагерь лесорубов"),
		"подсказка повозки собрана из полей экипажа и маршрута")
	_check(RULES.format_seconds(65) == "01:05" and RULES.format_seconds(3725) == "1 ч 02 мин", "время в подсказках форматируется как в списке")
	var bounds := RULES.content_bounds(routes, now_entries)
	_check(bounds.has_point(first_center) and bounds.has_point(last_center), "границы содержимого вмещают маршрут фермы")
	_check(RULES.content_bounds([], []).size == Vector2(512 * 32, 256 * 32), "без маршрутов видна вся карта мира")


func _check_client_positions_match_server() -> void:
	var routes: Array = _fixture("world_roads.json").get("terrain", {}).get("roads", {}).get("routes", [])
	var convoys: Array = _fixture("traveling_convoys.json").get("convoys", [])
	for convoy in convoys:
		var route: Dictionary = RULES.route_for_building(routes, str(convoy["destination_building_id"]))
		var progress := float(int(convoy["progress_percent"])) / 100.0
		var position := RULES.route_position(route["tiles"], progress)
		_check(absf(float(position["x"]) - float(convoy["position_x"])) <= POSITION_TOLERANCE
			and absf(float(position["y"]) - float(convoy["position_y"])) <= POSITION_TOLERANCE,
			"позиция повозки %s по прогрессу совпадает с сервером" % str(convoy["id"]))
		if float(convoy["progress_percent"]) < 100.0:
			_check(str(position["direction"]) == str(convoy["position_direction"]),
				"направление повозки %s совпадает с сервером" % str(convoy["id"]))


func _check_travel_map() -> void:
	var routes: Array = _fixture("world_roads.json").get("terrain", {}).get("roads", {}).get("routes", [])
	var citizens: Array = _fixture("traveling_citizens.json").get("citizens", [])
	var convoys: Array = _fixture("traveling_convoys.json").get("convoys", [])
	var map = TRAVEL_MAP_SCRIPT.new()
	map.custom_minimum_size = Vector2(900, 480)
	add_child(map)
	map.size = Vector2(900, 480)
	map.set_routes(routes)
	map.set_citizens(citizens)
	map.set_convoys(convoys)
	_check(map.entries().size() == 4, "карта путей получила двух горожан и две повозки")
	_check(not map.draw_tiles, "карта путей не рисует сетку тайлов мира")
	var view := Rect2(Vector2.ZERO, map.size)
	var all_visible := true
	for route in routes:
		for point in RULES.route_points(route["tiles"]):
			all_visible = all_visible and view.has_point(map.world_to_screen(point))
	_check(all_visible, "при первой загрузке видны все маршруты целиком")
	var citizen_screen: Vector2 = map.world_to_screen(Vector2(1632.71, 2495.29))
	var picked: Dictionary = map.entry_at_screen(citizen_screen)
	_check(str(picked.get("name", "")) == "Аня", "наведение на горожанина находит его запись")
	_check(map._get_tooltip(citizen_screen).contains("Маршрут: Лагерь лесорубов"), "подсказка горожанина называет маршрут")
	_check(map.entry_at_screen(Vector2(-1000.0, -1000.0)).is_empty(), "пустое место на карте путей не даёт записи")
	var feet: Vector2 = map.citizen_feet(picked)
	_check(str(map.entry_at_screen(feet + Vector2(0.0, -80.0)).get("name", "")) == "Аня", "голова горожанина выбирается: спрайт 90 px над ногами")
	_check(map.entry_at_screen(feet + Vector2(0.0, -110.0)).is_empty(), "выше спрайта горожанина выбора нет")
	var cart: Vector2 = map.world_to_screen(Vector2(656.0, 1008.0))
	_check(str(map.entry_at_screen(cart + Vector2(0.0, -40.0)).get("entity_kind", "")) == "wagon", "повозка выбирается по прежнему прямоугольнику 68x64")
	_check(map.entry_at_screen(cart + Vector2(0.0, -60.0)).is_empty(), "над повозкой выбора нет выше прежнего прямоугольника")
	_check(map.citizen_frames().has("e") and map.citizen_frames().has("nw"), "кадры горожан из ../assets доступны карте путей")
	_check(map._texture("cart_peasant") != null and map._texture("cart_light") != null, "спрайты повозок загружаются из ../assets")
	_check(map._texture("horse") != null and map._texture("driver") != null, "спрайты лошади и возницы загружаются")
	_check(map._texture("cart_missing") == null, "отсутствующий спрайт не ломает карту")
	_check(map._cart_icon_texture("peasant") != null and map._cart_icon_texture("light") != null, "иконки повозок берутся из ../assets/ui/transport")
	_check(map._cart_icon_texture("") == null and map._cart_icon_texture("missing") == null, "без ключа или картинки иконки повозки нет")
	var eta_before := _first_wagon_eta(map)
	map._convoys_received_msec -= 30000
	map._refresh_entries()
	var eta_drop := eta_before - _first_wagon_eta(map)
	_check(eta_drop >= 29 and eta_drop <= 31, "ETA повозки пересчитывается по времени между ответами сервера")
	var label: Rect2 = map._label_rect("Аня", Vector2(400.0, 300.0))
	_check(is_equal_approx(label.get_center().x, 400.0), "подпись центрируется по точке, как midbottom в map_travel.py:280")
	_check(is_equal_approx(label.position.y + ThemeDB.fallback_font.get_ascent(11), 270.0), "базовая линия подписи на 30 px выше точки")
	var pair: Array = [convoys[1].duplicate(true), convoys[1].duplicate(true)]
	pair[1]["id"] = 9
	var paired = TRAVEL_MAP_SCRIPT.new()
	add_child(paired)
	paired.set_routes(routes)
	paired.set_convoys(pair)
	var wagons: Array = []
	for entry in paired.entries():
		if str(entry.get("entity_kind", "")) == "wagon":
			wagons.append(entry)
	_check(wagons.size() == 2, "две повозки к одной ферме попадают на карту")
	var first := RULES.display_position(wagons[0])
	var second := RULES.display_position(wagons[1])
	_check(absf(first.distance_to(second) - 28.8) <= 0.01, "повозки в одной точке разводятся на шаг полосы 28.8 px (0.9 тайла)")
	_check(((first + second) * 0.5).distance_to(Vector2(656.0, 1008.0)) <= 0.01, "полосы стоят симметрично относительно точки повозки на пути")
	_check(str(paired.entry_at_screen(paired.world_to_screen(first) + Vector2(0.0, -40.0)).get("entity_kind", "")) == "wagon",
		"выбор повозки работает по точке отрисовки после раздвижки")
	paired.free()
	map.free()


func _first_wagon_eta(map) -> int:
	for entry in map.entries():
		if str(entry.get("entity_kind", "")) == "wagon":
			return int(entry["eta_seconds"])
	return -1


func _check_request_chain_and_lists() -> void:
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
	economy._travel_timer.stop()
	ApiClient.set_server_url("http://127.0.0.1:%d" % port)

	economy._close_window()
	var content_before: int = economy._content.get_child_count()
	var status_before: String = economy._status.text
	var details_before: String = economy._details.text
	economy._toggle_map_layer()
	_check(economy._pending_action == "travel_routes", "слой путей запрашивает маршруты карты")
	await _serve({"/api/map/terrain": _fixture("world_roads.json")})
	await _serve({"/api/world/traveling-citizens?character_id=42": _fixture("traveling_citizens.json")})
	await _serve({"/api/world/traveling-convoys?character_id=42": _fixture("traveling_convoys.json")})
	await _wait_idle(economy)
	_check(_requested_paths == ["/api/map/terrain", "/api/world/traveling-citizens?character_id=42",
		"/api/world/traveling-convoys?character_id=42"], "цепочка путей идёт: карта, горожане, повозки")
	_check(economy._travel_map.entries().size() == 4, "карта путей получила горожан и повозки из ответов")
	_check(economy._content.get_child_count() == content_before and economy._status.text == status_before
		and economy._details.text == details_before, "обновление путей не меняет списки")

	economy._set_view("city")
	economy._refresh_travel_layer()
	_check(economy._pending_action.is_empty(), "вне карты путей обновление не запрашивает сервер")

	economy._close_window()
	_check(economy._map_layer == "travel" and economy._travel_map.visible, "карта открывается в последнем слое путей")
	await _serve({"/api/world/traveling-citizens?character_id=42": {}})
	await _wait_idle(economy)
	_check(economy._map_hint.text.begins_with("Пути мира:"), "ошибка обновления путей показывается в подсказке карты")
	_check(economy._status.text == status_before, "ошибка путей не пишет в статус списка")
	_check(economy._content.get_child_count() == content_before, "ошибка путей не добавляет строк в список")

	remove_child(economy)
	economy.free()
	GameSession.clear()


func _listen() -> int:
	for port in range(PORT_FIRST, PORT_LAST):
		if _server.listen(port, "127.0.0.1") == OK:
			return port
	return -1


# Принимает один HTTP-запрос и отвечает фикстурой по пути (вместе с query-строкой); без фикстуры — 404.
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
	var raw := ""
	deadline = Time.get_ticks_msec() + SERVE_TIMEOUT_MS
	while not raw.contains("\r\n\r\n") and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		_peer.poll()
		var available := _peer.get_available_bytes()
		if available > 0:
			var chunk: Array = _peer.get_data(available)
			raw += (chunk[1] as PackedByteArray).get_string_from_utf8()
	var path := raw.get_slice("\r\n", 0).get_slice(" ", 1)
	_requested_paths.append(path)
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


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % file_name)
	return {}


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
