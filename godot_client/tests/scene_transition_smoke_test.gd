extends Node

const TRANSITION_SCRIPT := preload("res://scripts/scene_transition.gd")
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


# Считает события, дошедшие до сцены: во время затемнения счётчики должны стоять на месте.
class InputProbe extends Node:
	var input_count := 0
	var unhandled_count := 0

	func _ready() -> void:
		set_process_input(true)
		set_process_unhandled_input(true)

	func _input(_event: InputEvent) -> void:
		input_count += 1

	func _unhandled_input(_event: InputEvent) -> void:
		unhandled_count += 1


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var probe := InputProbe.new()
	add_child(probe)
	var first := {"calls": 0}
	var second := {"calls": 0}
	var layer: CanvasLayer = TRANSITION_SCRIPT.run(get_tree(), func() -> void: first["calls"] += 1)
	_check(layer != null and layer.is_inside_tree(), "переход добавляет слой поверх сцены")
	_check(TRANSITION_SCRIPT.is_running(get_tree()), "пока слой на месте, переход считается идущим")
	var shade := _find_shade(layer)
	_check(shade != null and shade.mouse_filter == Control.MOUSE_FILTER_STOP, "во время перехода клики блокируются")
	_check(first["calls"] == 0, "сцена не меняется до окончания затемнения")

	get_viewport().push_input(_key_event())
	get_viewport().push_input(_click_event())
	_check(probe.input_count == 0 and probe.unhandled_count == 0, "во время затемнения клавиатура и мышь не доходят до сцены")

	var repeated: CanvasLayer = TRANSITION_SCRIPT.run(get_tree(), func() -> void: second["calls"] += 1)
	_check(repeated == null, "повторный запрос во время затемнения игнорируется")

	await get_tree().create_timer(TRANSITION_SCRIPT.DURATION + 0.05).timeout
	_check(first["calls"] == 1, "после затемнения смена сцены вызывается")
	await get_tree().create_timer(0.3).timeout
	_check(first["calls"] == 1 and second["calls"] == 0, "смена сцены вызывается ровно один раз, отброшенный запрос не вызывается")
	_check(not is_instance_valid(layer) or layer.is_queued_for_deletion(), "слой перехода удаляется после смены сцены")
	_check(not TRANSITION_SCRIPT.is_running(get_tree()), "после освобождения слоя переход больше не идёт")

	get_viewport().push_input(_key_event())
	_check(probe.input_count == 1, "после освобождения слоя клавиатура снова работает")

	var again: CanvasLayer = TRANSITION_SCRIPT.run(get_tree(), func() -> void: pass)
	_check(again != null, "после освобождения можно запустить новый переход")
	await TRANSITION_SCRIPT.wait_until_idle(get_tree())
	_check(not is_instance_valid(again) or again.is_queued_for_deletion(), "wait_until_idle дожидается освобождения слоя")
	await _check_world_wiring()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("scene_transition_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_world_wiring() -> void:
	await _check_tower_wiring()
	await _check_deck_wiring()
	await _check_economy_wiring()


func _check_tower_wiring() -> void:
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "zone": "tavern"}
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world._enter_screen(WORLD_SCRIPT.SCREEN_HUB)
	_check(not TRANSITION_SCRIPT.is_running(get_tree()), "Башня: первая загрузка таверны без затемнения")
	world._go_to_screen(WORLD_SCRIPT.SCREEN_MAP)
	world._go_to_screen(WORLD_SCRIPT.SCREEN_ROOM)
	_check(world._screen == "tavern" and TRANSITION_SCRIPT.is_running(get_tree()), "Башня: выход на карту идёт через затемнение, экран меняется позже")
	await TRANSITION_SCRIPT.wait_until_idle(get_tree())
	_check(world._screen == "world_map", "Башня: после затемнения открыта карта, повторный запрос игнорируется")
	remove_child(world)
	world.free()
	GameSession.clear()


func _check_deck_wiring() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "type": "warrior", "level": 5, "hp": 60, "max_hp": 60, "mp": 20, "max_mp": 20, "zone": "world_map", "talents": {}}
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	deck._enter_location("world_map")
	_check(not TRANSITION_SCRIPT.is_running(get_tree()), "Колода: первая загрузка карты без затемнения")
	deck._show_inventory()
	_check(deck._view == "inventory" and not TRANSITION_SCRIPT.is_running(get_tree()), "Колода: рюкзак открывается окном без затемнения")
	deck._go_to_location("tavern")
	_check(deck._social_location == "world_map" and TRANSITION_SCRIPT.is_running(get_tree()), "Колода: переход в таверну идёт через затемнение")
	await TRANSITION_SCRIPT.wait_until_idle(get_tree())
	_check(deck._social_location == "tavern" and deck._view == "tavern", "Колода: после затемнения открыта таверна")
	remove_child(deck)
	deck.free()
	GameSession.clear()


func _check_economy_wiring() -> void:
	GameSession.clear()
	GameSession.world = {"server_url": UNREACHABLE_URL}
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	economy._load_forge()
	_check(economy._view == "forge" and not TRANSITION_SCRIPT.is_running(get_tree()), "Экономика: кузница открывается окном без затемнения")
	economy._set_view("map")
	economy._enter_tavern()
	_check(economy._view == "map" and TRANSITION_SCRIPT.is_running(get_tree()), "Экономика: вход в таверну идёт через затемнение")
	await TRANSITION_SCRIPT.wait_until_idle(get_tree())
	_check(economy._view == "tavern", "Экономика: после затемнения открыта таверна")
	economy._close_window()
	_check(economy._view == "tavern" and TRANSITION_SCRIPT.is_running(get_tree()), "Экономика: выход из таверны идёт через затемнение")
	await TRANSITION_SCRIPT.wait_until_idle(get_tree())
	_check(economy._view == "map", "Экономика: после затемнения снова город")
	remove_child(economy)
	economy.free()
	GameSession.clear()


func _find_shade(layer: CanvasLayer) -> ColorRect:
	for child in layer.get_children():
		if child is ColorRect:
			return child
	return null


func _key_event() -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = KEY_A
	event.physical_keycode = KEY_A
	event.pressed = true
	return event


func _click_event() -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = Vector2(20, 20)
	event.global_position = Vector2(20, 20)
	return event


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
