extends Node

const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {
		"id": 42,
		"name": "Тест",
		"profession_type": "warrior",
		"level": 7,
		"xp": 120,
		"stat_points": 3,
		"stats": {"strength": 12, "agility": 9, "intuition": 7, "wisdom": 4, "intellect": 6, "endurance": 10},
		"equipment": {},
		"equipment_bonuses": {},
		"copper": 5,
		"silver": 2,
		"gold": 1,
		"carried_weight_kg": 0,
	}
	ApiClient._http.timeout = 0.5
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world._go_to_screen(WORLD_SCRIPT.SCREEN_MAP)
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	world.size = Vector2(1280, 720)
	world._world_ready = true
	GameSession.world_snapshot = {"player": {
		"x": 0, "y": 0, "hp": 80, "max_hp": 140, "mp": 10, "max_mp": 36,
		"dash_cooldown": 0.0, "dash_active": false, "windup": 0.0,
	}}

	_check(not world._profile_overlay.is_open(), "карточка закрыта при входе в мир")
	_press_key(KEY_C)
	_check(world._profile_overlay.is_open(), "клавиша C открывает карточку персонажа")
	_check(world._profile_overlay.current_profile()["hp"] == 80 and world._profile_overlay.current_profile()["max_hp"] == 140, "карточка показывает живые HP из мира")
	_press_key(KEY_C)
	_check(not world._profile_overlay.is_open(), "повторная C закрывает карточку")
	_press_key(KEY_I)
	_check(world._profile_overlay.is_open() and not world._inventory_panel.visible, "клавиша I открывает карточку персонажа, как в Python, а не инвентарь")
	_press_key(KEY_I)
	_check(not world._profile_overlay.is_open() and not world._inventory_panel.visible, "повторная I закрывает карточку")

	var search := LineEdit.new()
	world.add_child(search)
	search.grab_focus()
	_check(search.has_focus(), "тестовое поле ввода получило фокус")
	var key_i := InputEventKey.new()
	key_i.keycode = KEY_I
	key_i.physical_keycode = KEY_I
	key_i.pressed = true
	world._unhandled_input(key_i)
	_check(world._profile_overlay.is_open(), "I открывает карточку при фокусе в обычном поле ввода, как в Python: блокирует только чат")
	world._unhandled_input(key_i)
	search.release_focus()
	world.remove_child(search)
	search.free()
	world._toggle_chat()
	world._unhandled_input(key_i)
	_check(not world._profile_overlay.is_open(), "открытый чат забирает I, карточка не открывается")
	world._close_chat()

	world._toggle_character_profile()
	_check(world._profile_overlay.is_open(), "переключение карточки персонажа открывает её")
	_press_key(KEY_ESCAPE)
	_check(world._profile_overlay.is_open() and world._exit_menu.is_open(), "Esc открывает меню выхода, карточка остаётся открытой, как в Python")
	world._exit_menu.close()

	world._unhandled_input(_click(world.size * 0.5, true))
	_check(world._profile_overlay.is_open(), "двойной клик по своему персонажу открывает карточку")
	world._unhandled_input(_click(Vector2(900.0, 400.0), false))
	_check(world._profile_overlay.is_open(), "ЛКМ мимо карточки не закрывает её и не работает по миру")
	world._inventory_loaded = true
	world._profile_overlay._backpack_button.pressed.emit()
	_check(world._inventory_panel.visible, "кнопка РЮКЗАК открывает инвентарь")
	world._toggle_inventory()

	world._pending_action = "busy"
	world._on_profile_stat_requested("strength", 1)
	_check(world._status.text == "Подождите завершения текущего запроса.", "пока идёт запрос, изменение характеристики ждёт")
	world._pending_action = ""
	world._on_profile_stat_requested("endurance", 1)
	_check(world._status.text == "Эту характеристику сейчас нельзя изменить.", "выносливость вручную не повышается")
	world._on_profile_level_requested(1)
	_check(world._status.text == "Уровень сейчас нельзя изменить.", "обычный персонаж не меняет уровень")

	world._unhandled_input(_click(Vector2(900.0, 400.0), false))
	_press_key(KEY_ESCAPE)
	_check(world._profile_overlay.is_open() and world._exit_menu.is_open(), "Esc после клика мимо карточки открывает меню, карточка остаётся")
	world._exit_menu.close()
	world._profile_overlay.close()

	world._inventory_panel.visible = true
	_press_key(KEY_ESCAPE)
	_check(not world._inventory_panel.visible and not world._exit_menu.is_open(), "Esc закрывает инвентарь и не открывает меню выхода")
	_press_key(KEY_ESCAPE)
	_check(world._exit_menu.is_open(), "Esc без открытых окон открывает меню выхода")
	world._exit_menu.close()
	_check(_find_button(world, "Выйти из аккаунта") == null, "в мире нет кнопки «Выйти из аккаунта»: выход в лобби через Esc")

	remove_child(world)
	world.free()
	GameSession.clear()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_profile_smoke_test: OK")
	get_tree().quit(code)


func _press_key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	get_viewport().push_input(event)


func _click(position: Vector2, double: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = double
	event.position = position
	return event


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
