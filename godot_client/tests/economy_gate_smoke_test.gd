extends Node

const RULES := preload("res://scripts/economy_city_layout_rules.gd")
const GATE_RULES := preload("res://scripts/economy_gate_rules.gd")
const CITY_MAP_SCRIPT := preload("res://scripts/economy_city_map.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const TOWN_RULES := preload("res://scripts/world_map_town_rules.gd")
const FIXTURE_DIR := "res://tests/fixtures/economy/"
const PORT_FIRST := 19530
const PORT_LAST := 19580
const REQUEST_TIMEOUT_MS := 8000
const UNREACHABLE_URL := "http://127.0.0.1:9"
const SYNC_ERROR := "Маршрут не найден в API этого режима"
# Вход Радбурга из economy/server (server/structures.py:282) с клетками входов на карте мира.
const TOWN_OBJECTS := [{
	"id": "town_radburg", "tile_x": 60, "tile_y": 46, "tile_w": 15, "tile_h": 15,
	"name": "Город Радбург", "type": "Город Света (15х15)",
	"desc": "Радбург — священный Город Света. Размер 15х15 тайлов (X: 60..74, Y: 46..60). 4 ворот: Главные (восток), Южные, Северные, Западные.",
	"solid_rects": [[1984, 1536, 352, 352]],
	"entrances": [
		{"id": "east", "tiles": [[74, 52], [74, 53], [74, 54]], "approach_pos": [2416, 1712]},
		{"id": "south", "tiles": [[67, 60]], "approach_pos": [2160, 1968]},
		{"id": "north", "tiles": [[67, 46]], "approach_pos": [2160, 1456]},
		{"id": "west", "tiles": [[60, 53]], "approach_pos": [1904, 1712]},
	],
}]
const MINIMAL_TERRAIN := {
	"map": {"tiles_w": 100, "tiles_h": 100, "version": 1},
	"tiles": {}, "objects": TOWN_OBJECTS, "obstacles": [], "props": [], "bridges": [], "crystals": [], "animals": [], "roads": {},
}

var _failures: Array[String] = []
var _checks := 0
var _server := TCPServer.new()
var _base_url := ""
var _responses: Dictionary = {}
var _requests: Array[Dictionary] = []
var _connections: Array[Dictionary] = []
var _answered: Array = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_gates_from_server_walls()
	_check_gate_zones()
	_check_map_hover_and_click()
	_check_spawns()
	_check_gate_click_opens_map()
	_check_city_starts_at_gate()
	await _check_city_return_entrance()
	await _check_town_window()
	var port := _listen()
	_check(port > 0, "тестовый сервер слушает 127.0.0.1")
	if port > 0:
		_base_url = "http://127.0.0.1:%d" % port
		await _check_map_entry_and_sync_notice()
	_server.stop()
	_cancel_transitions()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_gate_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_gates_from_server_walls() -> void:
	var walls: Array = _fixture("city_structures.json").get("city", {}).get("walls", [])
	var derived: Array = GATE_RULES.gaps_from_walls(walls)
	_check(derived.size() == 4, "из стен сервера выводятся четыре проёма")
	var by_id := {}
	for gate in derived:
		by_id[str(gate["id"])] = gate
	for layout_gate in RULES.GATES:
		var gate_id := str(layout_gate["id"])
		_check(by_id.has(gate_id), "проём %s найден между стенами сервера" % gate_id)
		if by_id.has(gate_id):
			_check(by_id[gate_id]["rect"] == layout_gate["rect"], "проём %s совпадает с таблицей клиента" % gate_id)
			_check(str(by_id[gate_id]["name"]) == str(layout_gate["name"]), "название проёма %s совпадает с rendering.py" % gate_id)
	var broken: Array = walls.duplicate()
	broken.remove_at(7)
	_check(GATE_RULES.gaps_from_walls(broken).size() == 3, "без восточной стены проёма нет")


func _check_gate_zones() -> void:
	var east := _gate("east")
	var east_center := RULES.gate_world_rect(east).get_center()
	_check(str(GATE_RULES.gate_at_world(RULES.GATES, east_center).get("id", "")) == "east", "центр восточного проёма попадает в зону")
	_check(str(GATE_RULES.gate_at_world(RULES.GATES, Vector2(1504.0, 10.0)).get("id", "")) == "north", "левый край северного проёма входит в зону")
	_check(GATE_RULES.gate_at_world(RULES.GATES, Vector2(1503.0, 10.0)).is_empty(), "точка левее северного проёма в зону не входит")
	_check(GATE_RULES.gate_at_world(RULES.GATES, Vector2(1600.0, 1600.0)).is_empty(), "центр площади — не ворота")
	_check(GATE_RULES.gate_at_world(RULES.GATES, Vector2(-10.0, -10.0)).is_empty(), "точка за стенами — не ворота")
	var tooltip := GATE_RULES.tooltip(east)
	_check(tooltip == "Главные ворота · выход на карту мира", "подсказка ворот называет проём и выход на карту мира")


func _check_map_hover_and_click() -> void:
	var map = CITY_MAP_SCRIPT.new()
	map.custom_minimum_size = Vector2(900, 480)
	add_child(map)
	map.size = Vector2(900, 480)
	map.fit_map()
	var gate_ids: Array[String] = []
	var building_keys: Array[String] = []
	map.gate_clicked.connect(func(gate: Dictionary) -> void: gate_ids.append(str(gate["id"])))
	map.building_clicked.connect(func(key: String) -> void: building_keys.append(key))

	var east_center: Vector2 = RULES.gate_world_rect(_gate("east")).get_center()
	var east_screen: Vector2 = map.world_to_screen(east_center)
	_send_motion(map, east_screen)
	_check(map._hover_gate_id == "east", "наведение на восточные ворота подсвечивает их")
	_check(map._get_tooltip(east_screen).contains("Главные ворота"), "подсказка на воротах называет проём")
	_click(map, east_center)
	_check(gate_ids == ["east"], "клик по воротам отдаёт проём восток")
	_check(building_keys.is_empty(), "клик по воротам не открывает здание")
	_send_motion(map, map.world_to_screen(Vector2(1600.0, 1600.0)))
	_check(map._hover_gate_id == "", "наведение на площадь снимает подсветку ворот")
	_send_motion(map, east_screen)
	map._on_mouse_exited()
	_check(map._hover_gate_id == "", "уход курсора с карты снимает подсветку")
	map.free()


func _check_spawns() -> void:
	_check(GATE_RULES.map_spawn("east")["position"] == Vector2(2416.0, 1712.0), "восточные ворота ведут на карту в точку 75×53 тайла")
	_check(str(GATE_RULES.map_spawn("east")["direction"]) == "e", "у восточного входа карта смотрит на восток")
	_check(GATE_RULES.map_spawn("main") == GATE_RULES.map_spawn("east"), "главные ворота main ведут к восточной точке")
	_check(GATE_RULES.map_spawn("north")["position"] == Vector2(2160.0, 1456.0), "северные ворота ведут в точку 67×45 тайлов")
	_check(GATE_RULES.map_spawn("south")["position"] == Vector2(2160.0, 1968.0), "южные ворота ведут в точку 67×61 тайла")
	_check(GATE_RULES.map_spawn("west")["position"] == Vector2(1904.0, 1712.0), "западные ворота ведут в точку 59×53 тайла")
	_check(GATE_RULES.map_spawn("unknown") == GATE_RULES.map_spawn("east"), "неизвестные ворота ведут к восточной точке")
	_check(GATE_RULES.city_spawn("east")["position"] == Vector2(3056.0, 1600.0), "возврат через восточный вход ставит героя у восточных ворот города")
	_check(GATE_RULES.city_spawn("north")["position"] == Vector2(1600.0, 144.0), "возврат через северный вход ставит героя у северных ворот")
	_check(str(GATE_RULES.city_spawn("north")["direction"]) == "s", "у северного входа города герой смотрит на юг")
	_check(GATE_RULES.city_spawn("south")["position"] == Vector2(1600.0, 3056.0), "возврат через южный вход ставит героя у южных ворот")
	_check(GATE_RULES.city_spawn("west")["position"] == Vector2(144.0, 1600.0), "возврат через западный вход ставит героя у западных ворот")
	_check(GATE_RULES.city_spawn("main") == GATE_RULES.city_spawn("east"), "вход main в город — восточный")
	_check(GATE_RULES.entrance_at_tile(TOWN_OBJECTS, Vector2i(74, 53)) == "east", "клетка 74×53 — восточный вход Радбурга")
	_check(GATE_RULES.entrance_at_tile(TOWN_OBJECTS, Vector2i(67, 46)) == "north", "клетка 67×46 — северный вход")
	_check(GATE_RULES.entrance_at_tile(TOWN_OBJECTS, Vector2i(67, 60)) == "south", "клетка 67×60 — южный вход")
	_check(GATE_RULES.entrance_at_tile(TOWN_OBJECTS, Vector2i(60, 53)) == "west", "клетка 60×53 — западный вход")
	_check(GATE_RULES.entrance_at_tile(TOWN_OBJECTS, Vector2i(75, 53)) == "", "точка появления у восточного входа сама входом не является")
	_check(GATE_RULES.entrance_at_tile([], Vector2i(74, 53)) == "", "без объектов карты входа в город нет")


func _check_gate_click_opens_map() -> void:
	GameSession.clear()
	GameSession.character = _character()
	GameSession.world = {}
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	economy._chat_timer.stop()
	economy._travel_timer.stop()
	economy._close_window()
	economy._pending_action = "busy"
	economy._city_map.gate_clicked.emit(_gate("north"))
	_check(not SCENE_TRANSITION.is_running(get_tree()) and GameSession.pending_map_gate.is_empty(), "клик по воротам во время запроса города ждёт, пока запрос закроется")
	economy._pending_action = ""
	economy._start_map_transition_if_idle()
	_check(GameSession.pending_map_gate == "north", "клик по северным воротам запоминает вход для карты мира")
	_check(SCENE_TRANSITION.is_running(get_tree()), "переход на карту идёт через общий затемняющий переход")
	_check(economy._view == "map" and economy._pending_action.is_empty(), "переход не меняет вид города и не делает запросов")
	_check(economy._city_map_panel.visible and not economy._list_panel.visible, "город остаётся на экране до смены сцены")
	economy._city_map.gate_clicked.emit(_gate("west"))
	_check(GameSession.pending_map_gate == "north", "второй клик во время перехода ничего не меняет")
	_cancel_transitions()
	remove_child(economy)
	economy.free()
	GameSession.clear()


func _check_city_starts_at_gate() -> void:
	GameSession.clear()
	GameSession.character = _character()
	GameSession.world = {}
	GameSession.pending_city_gate = "north"
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	economy._chat_timer.stop()
	economy._travel_timer.stop()
	_check(economy._city_map.player_position() == GATE_RULES.city_spawn("north")["position"], "возврат через северный вход ставит героя у северных ворот города")
	_check(GameSession.pending_city_gate.is_empty(), "вход в город читается один раз")
	remove_child(economy)
	economy.free()
	var plain = ECONOMY_SCRIPT.new()
	add_child(plain)
	plain._chat_timer.stop()
	plain._travel_timer.stop()
	_check(plain._city_map.player_position() == RULES.PLAYER_SPAWN_PX, "без входа город стартует у восточных ворот, как раньше")
	remove_child(plain)
	plain.free()
	GameSession.clear()


func _check_city_return_entrance() -> void:
	GameSession.clear()
	GameSession.character = {}
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.world_token = "test-world-token"
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world._world_sync_timer.stop()
	await _wait_until(func() -> bool: return world._pending_action.is_empty(), REQUEST_TIMEOUT_MS)
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	world._economy_map = true
	world._map_objects = TOWN_OBJECTS
	world._desired_position = _tile_center(Vector2i(59, 53))
	world._check_city_entrance()
	_check(not SCENE_TRANSITION.is_running(get_tree()) and GameSession.pending_city_gate.is_empty(), "клетка рядом со входом не открывает город")
	world._desired_position = _tile_center(Vector2i(60, 53))
	world._pending_action = "busy"
	world._check_city_entrance()
	_check(not SCENE_TRANSITION.is_running(get_tree()) and GameSession.pending_city_gate.is_empty(), "шаг на вход во время запроса карты ждёт, пока запрос закроется")
	world._pending_action = ""
	await get_tree().process_frame
	await get_tree().process_frame
	_check(GameSession.pending_city_gate == "west", "шаг на западный вход Радбурга ведёт в город через западные ворота")
	_check(SCENE_TRANSITION.is_running(get_tree()) and world._leaving_to_city, "переход в город идёт через общий затемняющий переход")
	world._check_city_entrance()
	_check(GameSession.pending_city_gate == "west", "повторный шаг во время перехода ничего не меняет")
	_cancel_transitions()
	remove_child(world)
	world.free()
	GameSession.clear()


func _check_town_window() -> void:
	GameSession.clear()
	GameSession.character = {}
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.world_token = "test-world-token"
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world.size = Vector2(1280.0, 720.0)
	world._world_sync_timer.stop()
	world._set_screen(WORLD_SCRIPT.SCREEN_MAP)
	world._economy_map = true
	world._apply_terrain(MINIMAL_TERRAIN)
	world._world_ready = true
	world._desired_position = Vector2(2000.0, 1600.0)
	var city := Vector2(2160.0, 1712.0)
	var ground := Vector2(1700.0, 1500.0)
	_check(world._town_objects.size() == 1 and world._town_active_id.is_empty(), "город попадает на карту Экономики, окно закрыто")
	_check(not world._is_ui_point(_screen_point(world, city)) and not world._is_ui_point(_screen_point(world, ground)), "точки проверки лежат на карте, а не на панелях")
	_mouse_press(world, _screen_point(world, city))
	_check(world._town_active_id == "town_radburg", "клик по городу выбирает его и открывает окно")
	await get_tree().process_frame
	await get_tree().process_frame
	var action: Rect2 = world._town_window_layout()["action"]
	_mouse_press(world, action.get_center())
	_check(TOWN_RULES.TOO_FAR_PHRASES.has(world._town_notice), "вдали от ворот кнопка показывает фразу отказа")
	_check(not SCENE_TRANSITION.is_running(get_tree()) and GameSession.pending_city_gate.is_empty(), "вдали от ворот переход в город не начинается")
	_check(world._town_active_id == "town_radburg", "после отказа окно остаётся открытым")
	_mouse_press(world, _screen_point(world, city), true)
	_check(not SCENE_TRANSITION.is_running(get_tree()), "двойной клик вдали от ворот тоже не переводит в город")
	_press_escape(world)
	_check(world._town_active_id.is_empty() and not world._exit_menu.is_open(), "Esc сначала закрывает окно объекта, меню выхода не открывается")
	_mouse_press(world, _screen_point(world, city))
	var close: Rect2 = world._town_window_layout()["close"]
	_mouse_press(world, close.get_center())
	_check(world._town_active_id.is_empty(), "крестик закрывает окно")
	_mouse_press(world, _screen_point(world, city))
	_mouse_press(world, _screen_point(world, ground))
	_check(world._town_active_id.is_empty(), "клик по земле закрывает окно")
	world._desired_position = _tile_center(Vector2i(75, 53))
	_mouse_press(world, _screen_point(world, city))
	var enter: Rect2 = world._town_window_layout()["action"]
	_mouse_press(world, enter.get_center())
	_check(SCENE_TRANSITION.is_running(get_tree()) and world._leaving_to_city, "кнопка рядом с восточными воротами открывает переход в город")
	_check(GameSession.pending_city_gate == "east", "переход в город идёт через ближайшие восточные ворота")
	_cancel_transitions()
	remove_child(world)
	world.free()
	var tower = WORLD_SCRIPT.new()
	add_child(tower)
	tower._world_sync_timer.stop()
	tower._apply_terrain(MINIMAL_TERRAIN)
	_check(tower._town_objects.is_empty() and tower._town_at(city).is_empty(), "на карте Башни объект города не выбирается")
	remove_child(tower)
	tower.free()
	GameSession.clear()


func _screen_point(world, world_point: Vector2) -> Vector2:
	return (world_point - world._camera_position()) * world._world_scale() + world.size * 0.5


func _mouse_press(world, point: Vector2, double_click := false) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = double_click
	event.position = point
	world._unhandled_input(event)


func _press_escape(world) -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ESCAPE
	event.pressed = true
	world._unhandled_input(event)


func _check_map_entry_and_sync_notice() -> void:
	_responses = {
		"GET /api/characters/42": {"status": 200, "body": {"character": _character()}},
		"GET /api/map/terrain": {"status": 200, "body": {"terrain": MINIMAL_TERRAIN}},
		"POST /api/world/sync": {"status": 404, "body": {"error": SYNC_ERROR}},
		"POST /api/world/leave": {"status": 404, "body": {"error": SYNC_ERROR}},
		"PUT /api/characters/42": {"status": 200, "body": {"character": _character()}},
		"POST /api/sessions/disconnect": {"status": 200, "body": {"ok": true}},
		"GET /api/social/snapshot": {"status": 200, "body": {"occupants": [], "messages": []}},
		"GET /api/castle/42/population": {"status": 200, "body": {"population": {"castle_level": 1, "city_upgrade": {"city_level": 1, "active": true, "phase_index": 2}}}},
	}
	GameSession.clear()
	GameSession.character = _character()
	GameSession.world = {"server_url": _base_url}
	GameSession.world_token = "test-world-token"
	GameSession.hub_url = _base_url
	GameSession.pending_map_gate = "north"
	var world = WORLD_SCRIPT.new()
	add_child(world)
	var entered := await _wait_until(
		func() -> bool: return world._world_ready and world._pending_action.is_empty() and _sent_count("POST /api/world/sync") >= 1 and world._status.text == SYNC_ERROR,
		REQUEST_TIMEOUT_MS,
	)
	_check(entered, "карта Экономики получает терейн и первый ответ синхронизации")
	_check(world._town_objects.size() == 1 and world._collision.terrain_blocked(2160.0, 1712.0), "Радбург из terrain.objects блокирует донжон на карте Экономики")
	_check(not world._collision.terrain_blocked(2416.0, 1712.0), "точка восточных ворот свободна")
	_check(world._economy_map and world._screen == WORLD_SCRIPT.SCREEN_MAP, "вход из города сразу открывает карту, без таверны и комнаты")
	_check(GameSession.pending_map_gate.is_empty(), "карта забирает вход из города один раз")
	_check(world._player_direction == "n", "вход через северные ворота смотрит на север")
	_check(not world._leaving_to_city, "точка у северных ворот не открывает город сразу")
	var sync_body := _body_of("POST /api/world/sync")
	_check(float(sync_body.get("x", 0.0)) == 2160.0 and float(sync_body.get("y", 0.0)) == 1456.0, "синхронизация начинается с точки северных ворот")
	_check(world._status.text == SYNC_ERROR, "отказ /api/world/sync показан текстом сервера")
	await _wait_until(func() -> bool: return world._pending_action.is_empty(), REQUEST_TIMEOUT_MS)
	var sent_before := _sent_count("POST /api/world/sync")
	world._status.text = "другое сообщение"
	world._send_world_sync()
	var retried := await _wait_until(
		func() -> bool: return world._pending_action.is_empty() and _sent_count("POST /api/world/sync") > sent_before,
		REQUEST_TIMEOUT_MS,
	)
	_check(retried and world._status.text == "другое сообщение", "повторный отказ синхронизации молчит, пока не сменилась ошибка")
	world._show_status_notice("проверка таймера")
	world._tick_status_notice(1.5)
	_check(world._status.text == "проверка таймера", "уведомление держится меньше двух секунд")
	world._tick_status_notice(0.6)
	_check(world._status.text.is_empty(), "уведомление очищается через две секунды")
	var city_state := await _wait_until(
		func() -> bool: return int(world._city_visual_state.get("phase_index", -1)) == 2 and world._pending_action.is_empty(),
		REQUEST_TIMEOUT_MS,
	)
	_check(city_state and _sent_count("GET /api/castle/42/population") >= 1, "состояние города берётся у /api/castle/42/population и применяется")
	await _wait_until(func() -> bool: return world._pending_action.is_empty(), REQUEST_TIMEOUT_MS)
	var status_before: String = world._status.text
	world._pending_action = "city_population"
	world._handle_api_result(false, "Сервер недоступен")
	_check(world._status.text == status_before and world._pending_action.is_empty(), "отказ обновления города молчит и не трогает строку состояния")
	world._apply_city_population({"castle_level": 2, "city_upgrade": {"city_level": 2, "active": false}})
	var reloaded := await _wait_until(
		func() -> bool: return _sent_count("GET /api/map/terrain") >= 2 and world._pending_action.is_empty(),
		REQUEST_TIMEOUT_MS,
	)
	_check(reloaded and world._layout_city_level == 1, "смена уровня города перечитывает терейн, уровень берётся из ответа терейна")
	world._start_exit("lobby")
	var left := await _wait_until(
		func() -> bool: return _sent_count("POST /api/sessions/disconnect") >= 1 and world._pending_action.is_empty(),
		REQUEST_TIMEOUT_MS,
	)
	_check(left, "выход с карты Экономики доходит до отключения")
	_check(_sent_count("POST /api/world/leave") == 1, "выход сначала пробует /api/world/leave")
	_check(not world._exit_menu.is_open(), "ошибка /api/world/leave не возвращает меню выхода")
	_check(int(_body_of("POST /api/sessions/disconnect").get("character_id", 0)) == 42, "отключение передаёт персонажа")
	_cancel_transitions()
	remove_child(world)
	world.free()


func _character() -> Dictionary:
	return {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120, "silver": 0, "gold": 0, "carried_weight_kg": 0.0}


func _tile_center(tile: Vector2i) -> Vector2:
	return Vector2(tile * 32) + Vector2(16.0, 16.0)


func _cancel_transitions() -> void:
	for layer in get_tree().get_nodes_in_group(SCENE_TRANSITION.GROUP):
		var parent: Node = layer.get_parent()
		if parent != null:
			parent.remove_child(layer)
		layer.free()


func _listen() -> int:
	for port in range(PORT_FIRST, PORT_LAST):
		if _server.listen(port, "127.0.0.1") == OK:
			return port
	return -1


# Сервер работает без блокировки: _wait_until на каждом кадре принимает и отвечает на запросы.
func _pump_server() -> void:
	while _server.is_connection_available():
		_connections.append({"peer": _server.take_connection(), "buffer": PackedByteArray()})
	var index := _connections.size() - 1
	while index >= 0:
		var connection := _connections[index]
		var peer: StreamPeerTCP = connection["peer"]
		peer.poll()
		var buffer: PackedByteArray = connection["buffer"]
		var available := peer.get_available_bytes()
		if available > 0:
			buffer.append_array(peer.get_data(available)[1])
			connection["buffer"] = buffer
		if _request_ready(buffer):
			_connections.remove_at(index)
			_answer(peer, buffer)
		index -= 1


func _request_ready(buffer: PackedByteArray) -> bool:
	var text := buffer.get_string_from_utf8()
	var split := text.find("\r\n\r\n")
	if split < 0:
		return false
	var length := 0
	for line in text.substr(0, split).split("\r\n"):
		if line.to_lower().begins_with("content-length:"):
			length = int(line.get_slice(":", 1).strip_edges())
	return buffer.size() - (split + 4) >= length


func _answer(peer: StreamPeerTCP, buffer: PackedByteArray) -> void:
	var text := buffer.get_string_from_utf8()
	var split := text.find("\r\n\r\n")
	var request_line := text.get_slice("\r\n", 0)
	var key := "%s %s" % [request_line.get_slice(" ", 0), request_line.get_slice(" ", 1).get_slice("?", 0)]
	_requests.append({"key": key, "body": buffer.slice(split + 4).get_string_from_utf8()})
	var reply: Dictionary = _responses.get(key, {"status": 404, "body": {"error": "нет ответа для " + key}})
	var status := int(reply["status"])
	var bytes := JSON.stringify(reply["body"]).to_utf8_buffer()
	var head := "HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % [
		status, "OK" if status == 200 else "Not Found", bytes.size(),
	]
	peer.put_data(head.to_utf8_buffer())
	peer.put_data(bytes)
	_answered.append(peer)


func _sent_count(key: String) -> int:
	var count := 0
	for request in _requests:
		if str(request["key"]) == key:
			count += 1
	return count


func _body_of(key: String) -> Dictionary:
	for request in _requests:
		if str(request["key"]) == key:
			var parsed: Variant = JSON.parse_string(str(request["body"]))
			return parsed if parsed is Dictionary else {}
	return {}


func _wait_until(condition: Callable, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		_pump_server()
		await get_tree().process_frame
	return true


func _gate(gate_id: String) -> Dictionary:
	for gate in RULES.GATES:
		if str(gate["id"]) == gate_id:
			return gate
	_check(false, "ворота %s есть в таблице клиента" % gate_id)
	return {}


func _click(map, world: Vector2) -> void:
	var screen: Vector2 = map.world_to_screen(world)
	_send_button(map, screen, true)
	_send_button(map, screen, false)


func _send_button(map, position: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = position
	map._gui_input(event)


func _send_motion(map, position: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = position
	map._gui_input(event)


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
