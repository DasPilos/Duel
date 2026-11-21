extends Node

const HOTBAR_SCRIPT := preload("res://scripts/hotbar.gd")
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var host := Control.new()
	host.size = Vector2(1280, 720)
	add_child(host)
	var hotbar = HOTBAR_SCRIPT.new()
	host.add_child(hotbar)

	var first := hotbar.slot_rect(0)
	var last := hotbar.slot_rect(9)
	_check(is_equal_approx(first.position.x, 407.0) and is_equal_approx(first.size.x, 43.0), "первый слот по центру: %s" % first)
	_check(is_equal_approx(last.end.x, 873.0), "последний слот заканчивается на правом краю панели 1–0: %s" % last)
	_check(is_equal_approx(first.end.y, 713.0), "панель стоит у нижнего края с отступом 7 единиц")
	_check(hotbar.slot_at(hotbar.slot_rect(3).get_center()) == 3, "клик по центру слота 4 попадает в слот 4")
	_check(hotbar.slot_at(Vector2(452.0, 690.0)) == -1, "клик между слотами не относится к панели")
	_check(not hotbar._has_point(Vector2(452.0, 690.0)), "клик между слотами проходит в мир")
	_check(hotbar._has_point(first.get_center()), "клик по слоту перехватывается панелью")

	_check(hotbar.key_slot(KEY_1) == 0 and hotbar.key_slot(KEY_0) == 9, "клавиши 1 и 0 соответствуют слотам 1 и 10")
	_check(hotbar.key_slot(KEY_R) == -1, "R не относится к панели 1–0")

	hotbar.flash(4)
	_check(hotbar._flash_index == 4, "нажатие подсвечивает слот")
	hotbar._process(0.2)
	_check(hotbar._flash_index == -1, "подсветка гаснет через 0,15 с")

	host.free()
	await _check_world_keys()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("hotbar_smoke_test: OK")
	get_tree().quit(code)


func _check_world_keys() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест"}
	ApiClient._http.timeout = 0.5
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world._go_to_screen(WORLD_SCRIPT.SCREEN_MAP)
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	world._world_ready = true
	GameSession.world_snapshot = {"player": {"dash_cooldown": 0.0, "dash_active": false, "windup": 0.0}}

	_press_key(KEY_R)
	_check(world._dash_aiming, "R включает прицеливание рывка")
	_press_key(KEY_R)
	_check(not world._dash_aiming, "повторный R отменяет прицеливание")

	_press_key(KEY_1)
	_check(world._dash_aiming and world._hotbar._flash_index == 0, "слот 1 подсвечивается и запускает прицел рывка")
	_press_key(KEY_1)
	_check(not world._dash_aiming, "повторная 1 отменяет прицел")

	_press_key(KEY_5)
	_check(world._hotbar._flash_index == 4 and not world._dash_aiming, "слот 5 подсвечивается без действия")

	GameSession.world_snapshot = {"player": {"dash_cooldown": 12.0, "dash_active": false, "windup": 0.0}}
	_press_key(KEY_R)
	_check(not world._dash_aiming, "во время перезарядки прицел не включается")

	remove_child(world)
	world.free()
	GameSession.clear()


func _press_key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	get_viewport().push_input(event)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
