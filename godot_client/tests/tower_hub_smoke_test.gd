extends Node

const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const HUB_RULES := preload("res://scripts/tower_hub_rules.gd")
const HUB_VIEW_SCRIPT := preload("res://scripts/tower_hub_view.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await get_tree().process_frame
	_check(HUB_VIEW_SCRIPT.background_texture() != null, "фон таверны найден в общих assets")
	_check_entry_zones()
	_check_checkpoint_bodies()
	_check_entry_screens()
	await _check_navigation()
	_check_hub_keys()
	await _check_exit_saves_zone()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_hub_smoke_test: OK")
	get_tree().quit(code)


func _check_entry_zones() -> void:
	_check(HUB_RULES.entry_zone({}, {}) == "tavern", "новый персонаж без зоны открывает таверну")
	_check(HUB_RULES.entry_zone({}, {"zone": "tavern", "position_x": 80.0, "position_y": 112.0}) == "tavern", "таверна открывается даже с сохранённой позицией")
	_check(HUB_RULES.entry_zone({}, {"zone": "city", "position_x": 80.0, "position_y": 112.0}) == "tavern", "зона city в Tower открывает таверну")
	_check(HUB_RULES.entry_zone({}, {"zone": "town"}) == "tavern", "неизвестная зона открывает таверну")
	_check(HUB_RULES.entry_zone({}, {"zone": "world_map", "position_x": null, "position_y": null}) == "tavern", "карта без позиции не открывается")
	_check(HUB_RULES.entry_zone({}, {"zone": "world_map", "position_x": 80.0, "position_y": 112.0}) == "world_map", "карта с позицией открывается на ней")
	_check(HUB_RULES.entry_zone({}, {"zone": "character_room"}) == "character_room", "комната открывается по зоне")
	_check(HUB_RULES.entry_zone({"code": "map7"}, {"zone": "tavern"}) == "world_map", "мир карты открывает карту сразу, как в Python")
	_check(HUB_RULES.entry_zone({"code": "deck_map4"}, {}) == "world_map", "deck_map тоже открывает карту сразу")
	_check(HUB_RULES.entry_zone({"code": "front_line_matchmaking", "mode": "front_line"}, {"zone": "tavern"}) == "world_map", "Front Line открывает карту сразу, чтобы сервер поставил героя на точку возрождения")
	_check(HUB_RULES.entry_zone({"code": "tower"}, {"zone": "character_room"}) == "character_room", "обычный мир Tower не принимается за карту")


func _check_checkpoint_bodies() -> void:
	_check(HUB_RULES.checkpoint_body("tavern", Vector2(80.0, 112.0), "e", true) == {"zone": "tavern"}, "в таверне сохраняется только зона")
	_check(HUB_RULES.checkpoint_body("character_room", Vector2(80.0, 112.0), "e", true) == {"zone": "character_room"}, "в комнате сохраняется только зона")
	_check(HUB_RULES.checkpoint_body("world_map", Vector2(80.0, 112.0), "e", true) == {"zone": "world_map", "position_x": 80.0, "position_y": 112.0, "position_direction": "e"}, "на карте сохраняются зона, позиция и направление")
	_check(HUB_RULES.checkpoint_body("world_map", Vector2.ZERO, "s", false) == {"zone": "world_map"}, "карта без известной позиции не записывает нули")


func _check_entry_screens() -> void:
	var fresh = _open_world({"id": 1, "name": "Новый", "zone": ""})
	_check(fresh._screen == "tavern" and fresh._hub_view.visible and not fresh._room_view.visible, "новый персонаж открывает таверну")
	_check(not fresh._hotbar.visible and not fresh._combat_log.visible, "в таверне скрыты панели карты")
	_close_world(fresh)

	var on_map = _open_world({"id": 2, "name": "Карта", "zone": "world_map", "position_x": 80.0, "position_y": 112.0})
	_check(on_map._screen == "world_map" and not on_map._hub_view.visible and on_map._hotbar.visible, "зона world_map с позицией открывает карту")
	_close_world(on_map)

	var room = _open_world({"id": 3, "name": "Комната", "zone": "character_room"})
	_check(room._screen == "character_room" and room._room_view.visible and not room._hub_view.visible, "зона character_room открывает комнату")
	_close_world(room)

	var map_world = _open_world({"id": 4, "name": "Мир карты", "zone": "tavern"}, {"server_url": UNREACHABLE_URL, "code": "map9"})
	_check(map_world._screen == "world_map", "мир карты открывает карту напрямую")
	_close_world(map_world)

	var front_line_world = _open_world(
		{"id": 6, "name": "Front Line", "zone": "tavern"},
		{"server_url": UNREACHABLE_URL, "code": "front_line_matchmaking", "mode": "front_line"},
	)
	_check(front_line_world._screen == "world_map", "Front Line открывает карту напрямую, игнорируя таверный чекпоинт")
	_close_world(front_line_world)

	var no_position = _open_world({"id": 5, "name": "Без позиции", "zone": "world_map"})
	_check(no_position._screen == "tavern", "карта без позиции начинает в таверне")
	_close_world(no_position)


func _check_navigation() -> void:
	var hub = _open_world({"id": 1, "name": "Новый", "zone": "tavern", "copper": 5})
	_check(hub._chat_location() == "tavern" and hub._chat_title.text == "Чат таверны", "в таверне чат и присутствие используют локацию tavern")

	# Пока канал запросов занят, переход ставит чекпоинт в очередь: так видно его тело.
	hub._pending_action = "busy"
	await _press(hub, "Комната отдыха")
	_check(hub._screen == "character_room" and hub._room_view.visible and not hub._hub_view.visible, "«Комната отдыха» открывает комнату")
	_check(hub._chat_location() == "character_room" and hub._chat_title.text == "Чат комнаты", "в комнате чат использует локацию character_room")
	var leave_tavern: Dictionary = hub._request_queue[0]
	_check(leave_tavern["action"] == "checkpoint" and leave_tavern["body"] == {"zone": "tavern"}, "уход из таверны сохраняет зону tavern")
	_check(leave_tavern["method"] == HTTPClient.METHOD_PUT and leave_tavern["path"] == "/api/characters/1", "чекпоинт уходит через PUT /api/characters/{id}")
	hub._pending_action = ""
	hub._flush_request_queue()

	hub._pending_action = "busy"
	hub._room_view._on_tab_pressed("chests")
	_check(hub._request_queue.size() == 2 and hub._request_queue[0]["storage_type"] == "chest1" and hub._request_queue[1]["storage_type"] == "chest2", "вкладка Сундуки запрашивает оба сундука")
	hub._pending_action = ""
	hub._flush_request_queue()

	hub._pending_action = "busy"
	hub._room_view._on_withdraw_pressed("chest1", {"id": 5, "name": "Карта", "quantity": 2})
	_check(hub._inventory_status.text == "Подождите завершения текущего запроса.", "«В рюкзак» в комнате переводит предмет из сундука")
	hub._pending_action = ""

	hub._pending_action = "busy"
	await _press(hub, "Вернуться в таверну")
	_check(hub._screen == "tavern" and hub._hub_view.visible and not hub._room_view.visible, "дверь комнаты возвращает в таверну")
	var leave_room: Dictionary = hub._request_queue[0]
	_check(leave_room["body"] == {"zone": "character_room"}, "уход из комнаты сохраняет зону character_room")
	hub._pending_action = ""
	hub._flush_request_queue()

	hub._pending_action = "busy"
	await _press(hub, "Выход на улицу")
	_check(hub._screen == "world_map" and hub._hotbar.visible and not hub._hub_view.visible, "«Выход на улицу» открывает карту мира")
	var leave_street: Dictionary = hub._request_queue[0]
	_check(leave_street["body"] == {"zone": "tavern"}, "уход на улицу сохраняет зону таверны")
	_check(hub._request_queue[1]["action"] == "terrain", "карта запрашивает терейн сразу после чекпоинта")
	hub._pending_action = ""
	hub._flush_request_queue()

	hub._world_ready = true
	hub._desired_position = Vector2(80.0, 112.0)
	hub._player_direction = "e"
	_check(hub._checkpoint_body() == {"zone": "world_map", "position_x": 80.0, "position_y": 112.0, "position_direction": "e"}, "выход из игры на карте сохраняет зону, позицию и направление")
	hub._pending_action = "busy"
	hub._go_to_screen("tavern")
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	var leave_map: Dictionary = hub._request_queue[0]
	_check(leave_map["body"] == {"zone": "world_map", "position_x": 80.0, "position_y": 112.0, "position_direction": "e"}, "уход с карты ставит в очередь чекпоинт с позицией")
	hub._pending_action = ""
	hub._flush_request_queue()
	hub._world_ready = false
	_close_world(hub)

	var bartender = _open_world({"id": 2, "name": "Бар", "zone": "tavern"})
	await _press(bartender, "Хозяин трактира")
	_check(bartender._screen == "tavern" and bartender._hub_view.button("bartender") != null, "хозяин трактира не уводит из таверны")
	_check(bartender._hub_view._status.text == "Напитки пока недоступны", "напитки в Tower недоступны: показано сообщение")
	_close_world(bartender)


func _check_hub_keys() -> void:
	var hub = _open_world({"id": 1, "name": "Новый", "zone": "tavern"})
	_press_key(KEY_C)
	_check(hub._profile_overlay.is_open(), "в таверне клавиша C открывает карточку")
	_press_key(KEY_C)
	_press_key(KEY_ENTER)
	_check(hub._chat_panel.visible, "в таверне Enter открывает чат")
	_press_key(KEY_ESCAPE)
	_check(not hub._chat_panel.visible and not hub._exit_menu.is_open(), "Esc сначала закрывает чат")
	_press_key(KEY_ESCAPE)
	_check(hub._exit_menu.is_open(), "в таверне Esc открывает меню выхода")
	hub._exit_menu.close()
	_press_key(KEY_R)
	_check(not hub._dash_aiming, "в таверне клавиша R не включает прицел рывка")
	_close_world(hub)


# Настоящие запросы к недоступному серверу: первым при выходе уходит чекпоинт комнаты, и при ошибке выход отменяется.
func _check_exit_saves_zone() -> void:
	GameSession.clear()
	ApiClient._http.timeout = 0.5
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.world_token = "test-world-token"
	GameSession.character = {"id": 7, "name": "Выход", "zone": "character_room"}
	var room = WORLD_SCRIPT.new()
	add_child(room)
	await _wait_until(func() -> bool: return room._pending_action.is_empty(), 8000)
	room._pending_action = "character"
	room._on_api_completed(true, {"character": GameSession.character})
	await _wait_until(func() -> bool: return room._pending_action.is_empty(), 8000)
	_check(room._screen == "character_room", "вход с зоной комнаты держит экран комнаты")
	room._start_exit("lobby")
	_check(room._pending_action == "exit_checkpoint", "первым запросом выхода уходит сохранение зоны комнаты")
	var cancelled := await _wait_until(func() -> bool: return room._exit_intent.is_empty(), 8000)
	_check(cancelled and room._exit_menu.is_open(), "ошибка сохранения отменяет выход и возвращает меню")
	remove_child(room)
	room.free()
	GameSession.clear()


func _wait_until(condition: Callable, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await get_tree().process_frame
	return true


func _open_world(character: Dictionary, world: Dictionary = {"server_url": UNREACHABLE_URL}) -> Node:
	GameSession.clear()
	GameSession.world = world.duplicate(true)
	GameSession.character = character.duplicate(true)
	var node = WORLD_SCRIPT.new()
	add_child(node)
	node._pending_action = "character"
	node._on_api_completed(true, {"character": character})
	return node


func _close_world(node: Node) -> void:
	remove_child(node)
	node.free()
	GameSession.clear()


func _press(root: Node, text: String) -> void:
	var button := _find_button(root, text)
	if button == null:
		_check(false, "есть кнопка «%s»" % text)
		return
	button.pressed.emit()
	await SCENE_TRANSITION.wait_until_idle(get_tree())


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _press_key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	get_viewport().push_input(event)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
