extends Node

const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const WAIT_TIMEOUT_MS := 8000

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест"}
	ApiClient._http.timeout = 0.5
	await _check_deck_battle_exit()
	for script in [WORLD_SCRIPT, ECONOMY_SCRIPT, DECK_SCRIPT]:
		await _check_scene(script)
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_exit_smoke_test: OK")
	get_tree().quit(code)


func _check_scene(script: GDScript) -> void:
	var label := script.resource_path.get_file()
	var scene = script.new()
	add_child(scene)
	await _wait_until(func() -> bool: return scene._pending_action.is_empty(), WAIT_TIMEOUT_MS)

	_press_escape()
	_check(scene._exit_menu.is_open(), label + ": Esc открывает меню выхода")
	_press_escape()
	_check(not scene._exit_menu.is_open(), label + ": повторный Esc закрывает меню")

	scene._exit_menu.open()
	_check(_press(scene._exit_menu._main_box, "ВЫЙТИ В ЛОББИ"), label + ": есть пункт ВЫЙТИ В ЛОББИ")
	var lobby_failed := await _wait_until(
		func() -> bool: return scene._exit_menu.is_open() and scene._exit_intent.is_empty(),
		WAIT_TIMEOUT_MS,
	)
	_check(lobby_failed, label + ": ошибка выхода в лобби возвращает меню")
	_check(scene._exit_menu._message.visible and not scene._exit_menu._message.text.is_empty(), label + ": ошибка лобби показана в меню")
	_check(not scene._server_unreachable, label + ": ошибка лобби не помечает сервер недоступным")

	scene._exit_menu.open()
	_check(_press(scene._exit_menu._main_box, "ПОКИНУТЬ ИГРУ"), label + ": есть пункт ПОКИНУТЬ ИГРУ")
	_check(scene._exit_menu.is_quitting() and not scene._exit_menu.is_open(), label + ": ПОКИНУТЬ ИГРУ запускает отсчёт и блокирует меню")
	_check(scene._exit_menu.is_quitting() and not scene._exit_menu.is_open(), label + ": ПОКИНУТЬ ИГРУ запускает отсчёт и блокирует меню")
	_press_escape()
	_check(scene._exit_menu.is_quitting(), label + ": Esc не прерывает выход")
	var quit_failed := await _wait_until(
		func() -> bool: return scene._exit_menu.is_open() and scene._exit_intent.is_empty(),
		WAIT_TIMEOUT_MS,
	)
	_check(quit_failed, label + ": ошибка выхода отменяет отсчёт и возвращает меню")
	_check(scene._server_unreachable, label + ": ошибка выхода помечает сервер недоступным")
	_check(scene._exit_menu._message.text.begins_with("Сервер недоступен:"), label + ": текст ошибки выхода как в клиенте Python")

	scene._exit_menu.close()
	get_tree().root.close_requested.emit()
	_check(scene._exit_menu.is_open(), label + ": закрытие окна открывает меню выхода")
	_check(not get_tree().is_auto_accept_quit(), label + ": пока сцена активна, окно не закрывается автоматически")

	remove_child(scene)
	scene.free()
	_check(get_tree().is_auto_accept_quit(), label + ": сцена возвращает авто-закрытие окна")


func _check_deck_battle_exit() -> void:
	var scene = DECK_SCRIPT.new()
	add_child(scene)
	await _wait_until(func() -> bool: return scene._pending_action.is_empty(), WAIT_TIMEOUT_MS)
	scene._social_location = "tavern"
	scene._view = "battle"
	scene._battle_state = {"phase": "turn", "battle_id": "exit-test"}
	scene._exit_menu.open()
	_check(_press(scene._exit_menu._main_box, "ВЫЙТИ В ЛОББИ"), "в бою Deck есть пункт ВЫЙТИ В ЛОББИ")
	var failed := await _wait_until(
		func() -> bool: return scene._exit_menu.is_open() and scene._exit_intent.is_empty(),
		WAIT_TIMEOUT_MS,
	)
	_check(failed, "в бою Deck выход в лобби запускается и возвращает меню после ошибки сети")
	_check(scene._exit_menu._message.text != "Сначала завершите текущий бой.", "в бою Deck выход не блокируется")
	_check(GameSession.character.get("zone", "") == "tavern", "в бою Deck выход сохраняет локацию боя, а не служебное имя battle")
	remove_child(scene)
	scene.free()


func _wait_until(condition: Callable, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await get_tree().process_frame
	return true


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)


func _button(box: Node, text: String) -> Button:
	for child in box.get_children():
		if child is Button and child.text == text:
			return child
	return null


func _press(box: Node, text: String) -> bool:
	var button := _button(box, text)
	if button == null or button.disabled:
		return false
	button.pressed.emit()
	return true


func _press_escape() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ESCAPE
	event.physical_keycode = KEY_ESCAPE
	event.pressed = true
	get_viewport().push_input(event)
