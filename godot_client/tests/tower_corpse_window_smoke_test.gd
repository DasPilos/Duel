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
	GameSession.character = {"id": 42, "name": "Тест", "type": "warrior", "copper": 5, "silver": 2, "gold": 1}
	GameSession.world_snapshot = {
		"player": {"x": 1040.0, "y": 1040.0, "hp": 48.0, "max_hp": 48.0, "mp": 18.0, "max_mp": 18.0, "move_speed": 120.0},
		"mobs": [],
		"animals": [],
		"trails": [],
		"corpses": [
			{"id": 7, "x": 1040.0, "y": 1040.0, "copper": 250},
			{"id": 8, "x": 1360.0, "y": 1040.0, "copper": 9999},
		],
	}
	var world = WORLD_SCRIPT.new()
	add_child(world)
	world._go_to_screen(WORLD_SCRIPT.SCREEN_MAP)
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	world.size = Vector2(1280, 720)
	world._world_ready = true
	world._desired_position = Vector2(1040.0, 1040.0)

	_check(world._corpse_at(Vector2(1040.0, 1030.0)) == 7, "клик внутри метки трупа выбирает труп")
	_check(world._corpse_at(Vector2(1040.0, 1040.0)) == 0, "нижняя граница метки трупа не попадает в клик")
	_check(world._corpse_at(Vector2(1054.0, 1030.0)) == 0, "правая граница метки трупа не попадает в клик")
	_check(world._corpse_at(Vector2(1040.0, 1000.0)) == 0, "клик над меткой трупа мимо")
	_check(is_equal_approx(world._corpse_distance_tiles(world._corpse_by_id(8)), 10.0), "расстояние до трупа считается в тайлах")

	world._open_corpse_window(8)
	_check(world._corpse_window_id == 0, "труп дальше 2 тайлов окно не открывает")
	_check(world._status.text == "Подойдите ближе к трупу", "дальний труп просит подойти ближе")
	world._open_corpse_window(7)
	_check(world._corpse_window_id == 7, "труп в радиусе 2 тайлов открывает окно")
	_check(world._corpse_window_contains(world.size * 0.5), "окно трупа перехватывает клик по центру экрана")
	_check(not world._corpse_window_contains(Vector2(5.0, 5.0)), "клик вне окна трупа не перехватывается")

	var rects: Dictionary = world._corpse_window_rects()
	var window: Rect2 = rects["window"]
	var close: Rect2 = rects["close"]
	var loot: Rect2 = rects["loot"]
	_check(window.get_center().is_equal_approx(world.size * 0.5), "окно трупа стоит по центру экрана")
	_check(window.encloses(close) and window.encloses(loot), "кнопки окна трупа лежат внутри окна")
	world._handle_corpse_window_click(close.get_center())
	_check(world._corpse_window_id == 0, "кнопка ✕ закрывает окно трупа")

	world._open_corpse_window(7)
	world._update_corpse_window([{"id": 8, "x": 1360.0, "y": 1040.0, "copper": 9999}])
	_check(world._corpse_window_id == 0, "окно закрывается, когда труп пропал из мира")
	world._open_corpse_window(7)
	world._update_corpse_window([{"id": 7, "x": 1040.0, "y": 1040.0, "copper": 250}])
	_check(world._corpse_window_id == 7, "окно остаётся открытым, пока труп на месте")

	_check(world._tiles_word(1) == "тайл" and world._tiles_word(2) == "тайла" and world._tiles_word(4) == "тайла", "склонение: 1 тайл, 2–4 тайла")
	_check(world._tiles_word(5) == "тайлов" and world._tiles_word(11) == "тайлов" and world._tiles_word(14) == "тайлов", "склонение: 5 и 11–14 тайлов")
	_check(world._tiles_word(21) == "тайл" and world._tiles_word(22) == "тайла" and world._tiles_word(111) == "тайлов", "склонение: 21 тайл, 22 тайла, 111 тайлов")

	world.free()
	GameSession.clear()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_corpse_window_smoke_test: OK")
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
