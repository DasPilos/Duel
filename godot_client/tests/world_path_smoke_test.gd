extends Node

const COLLISION_SCRIPT := preload("res://scripts/world_collision.gd")
const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_collision_rules()
	await _check_first_entry_position()
	await _check_world_movement()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_path_smoke_test: OK")
	get_tree().quit(code)


func _terrain(tiles_w: int, tiles_h: int, forest: Array, partial: Array = [], obstacles: Array = []) -> Dictionary:
	return {
		"map": {"tiles_w": tiles_w, "tiles_h": tiles_h, "version": 1},
		"tiles": {"forest": forest, "water": [], "dry": [], "mountain": [], "impassable": [], "partial": partial},
		"props": [],
		"obstacles": obstacles,
	}


# Стена из леса по двум клеткам столбца x = 8..9 (старый столбец 4 при тайле 32 px) от верха до строки 13;
# при gap = true строки 14..15 (старая строка 7) свободны
func _wall(gap: bool) -> Array:
	var rows: Array = []
	for row in range(14):
		rows.append([row, 8, 9])
	if not gap:
		rows.append([14, 8, 9])
		rows.append([15, 8, 9])
	return rows


func _check_collision_rules() -> void:
	var collision = COLLISION_SCRIPT.new()
	collision.configure(_terrain(20, 16, _wall(true)))
	_check(not collision.terrain_blocked(80.0, 112.0), "открытая клетка свободна")
	_check(collision.terrain_blocked(144.0, 80.0), "лес блокирует центр клетки")
	_check(collision.terrain_blocked(126.0, 80.0), "ноги персонажа задевают соседний лесной тайл")
	_check(not collision.terrain_blocked(112.0, 80.0), "ноги у края свободной клетки проходят")
	_check(collision.terrain_blocked(5.0, 100.0), "у границы мира ноги не проходят")
	var mob := COLLISION_SCRIPT.mob_rect(240.0, 200.0)
	_check(not collision.point_blocked(Vector2(190.0, 200.0), []), "точка рядом с мобом свободна без динамических блокировок")
	_check(collision.point_blocked(Vector2(190.0, 200.0), [mob]), "тело моба блокирует ноги персонажа")
	var rat := COLLISION_SCRIPT.front_line_mob_rect(240.0, 200.0, false)
	var boss := COLLISION_SCRIPT.front_line_mob_rect(240.0, 200.0, true)
	_check(rat == [224, 184, 32, 32] and boss == [176, 136, 128, 128], "тело моба Front Line совпадает с сервером (_mob_body_rect)")
	_check(not collision.point_blocked(Vector2(210.0, 200.0), [rat]) and collision.point_blocked(Vector2(210.0, 200.0), [boss]),
		"к крысе Front Line герой подходит вплотную, босс занимает место в 4 раза больше")
	_check(not collision.segment_clear(Vector2(112.0, 80.0), Vector2(144.0, 80.0), []), "отрезок через стену не свободен")
	_check(collision.segment_clear(Vector2(80.0, 112.0), Vector2(112.0, 112.0), []), "отрезок в открытой зоне свободен")

	var path: Array = collision.find_path(Vector2(80.0, 112.0), Vector2(208.0, 112.0), [])
	_check(not path.is_empty() and path[path.size() - 1] == Vector2(208.0, 112.0), "путь в обход стены найден и заканчивается в цели")
	var went_round := false
	var clear := true
	var previous := Vector2(80.0, 112.0)
	for point in path:
		if point.y >= 224.0:
			went_round = true
		if collision.point_blocked(point, []) or not collision.segment_clear(previous, point, []):
			clear = false
		previous = point
	_check(went_round, "путь проходит через проём у нижнего края стены")
	_check(clear, "все точки и отрезки пути свободны")
	_check(collision.find_path(Vector2(80.0, 112.0), Vector2(144.0, 80.0), []).is_empty(), "путь к заблокированной цели пуст")
	_check(collision.find_path(Vector2(80.0, 112.0), Vector2(80.0, 112.0), []) == [Vector2(80.0, 112.0)], "путь до своей клетки — только цель")

	var closed = COLLISION_SCRIPT.new()
	closed.configure(_terrain(20, 16, _wall(false)))
	_check(closed.find_path(Vector2(80.0, 112.0), Vector2(208.0, 112.0), []).is_empty(), "сплошная стена делает цель недостижимой")

	var corner = COLLISION_SCRIPT.new()
	corner.configure(_terrain(8, 8, [[0, 2, 3], [1, 2, 3], [2, 0, 1], [3, 0, 1]]))
	_check(corner.find_path(Vector2(16.0, 16.0), Vector2(48.0, 48.0), []).is_empty(), "по диагонали между двумя блоками не протискиваемся")

	var masked = COLLISION_SCRIPT.new()
	masked.configure(_terrain(16, 16, [], [[4, 4, "0111011101110111"]]))
	_check(masked.terrain_blocked(72.0, 80.0), "клетка маски 4 px, которую задевают ноги, блокирует")
	_check(not masked.terrain_blocked(84.0, 80.0), "свободная часть тайла с маской проходима")
	# Маска 4×4 на тайл 16 px: клетка маски 4 px (core/tile_mask.py: tile_size // MASK_SIDE), col 0 = x 64..67.
	_check(not masked.terrain_blocked(80.0, 80.0), "маска 4×4 на тайл 16 px: ноги от x 70 не задевают первую колонку маски (клетка 4 px)")

	var walled = COLLISION_SCRIPT.new()
	walled.configure(_terrain(20, 20, [], [], [{"points": [[100, 100], [140, 100], [140, 140], [100, 140]], "passages": [[110, 110, 10, 10]]}]))
	_check(walled.terrain_blocked(105.0, 105.0), "полигон препятствия блокирует")
	_check(not walled.terrain_blocked(115.0, 115.0), "проход в препятствии открыт")

	var walker = COLLISION_SCRIPT.new()
	walker.configure(_terrain(20, 16, _wall(true)))
	var position := Vector2(80.0, 112.0)
	var waypoints: Array = walker.find_path(position, Vector2(208.0, 112.0), [])
	var frames := 0
	var stayed_free := true
	while not waypoints.is_empty() and frames < 5000:
		position = walker.follow_path(position, waypoints, 2.0, [])["position"]
		if walker.point_blocked(position, []):
			stayed_free = false
		frames += 1
	_check(waypoints.is_empty() and position.distance_to(Vector2(208.0, 112.0)) < 1.0, "персонаж доходит до цели по пути")
	_check(stayed_free, "при движении по пути персонаж не входит в препятствия")


func _check_first_entry_position() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "position_x": null, "position_y": null}
	GameSession.world_snapshot = {}
	ApiClient._http.timeout = 0.5
	ApiClient._world_http.timeout = 0.5
	var world = WORLD_SCRIPT.new()
	add_child(world)
	await _wait_until(func() -> bool: return not world._world_request_pending, 15000)
	world._go_to_screen(WORLD_SCRIPT.SCREEN_MAP)
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	await _wait_until(func() -> bool: return not world._world_request_pending, 15000)
	world._send_world_sync()
	_check(world._world_action == "world_resync", "вход без сохранённой позиции запрашивает resync, а не падает на float(null)")
	await _wait_until(func() -> bool: return not world._world_request_pending, 15000)
	GameSession.character = {"id": 42, "name": "Тест", "position_x": 80.0, "position_y": 112.0}
	world._send_world_sync()
	_check(world._world_action == "world_sync", "вход с сохранённой позицией отправляет обычный sync")
	await _wait_until(func() -> bool: return not world._world_request_pending, 15000)
	remove_child(world)
	world.free()
	GameSession.clear()


func _check_world_movement() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест"}
	ApiClient._http.timeout = 0.5
	var world = WORLD_SCRIPT.new()
	add_child(world)
	await _wait_until(func() -> bool: return not world._world_request_pending, 15000)
	world._apply_terrain(_terrain(20, 16, _wall(true)))
	world._world_ready = true
	world._desired_position = Vector2(80.0, 112.0)
	var player := {"x": 80.0, "y": 112.0, "move_speed": 120.0, "reach": 60.0, "windup": 0.0, "backswing": 0.0, "dash_active": false}
	GameSession.world_snapshot = {"player": player, "mobs": [], "animals": []}

	_check(world._set_move_path(Vector2(208.0, 112.0)), "клик по земле за стеной ставит путь")
	var frames := 0
	var stayed_free := true
	while not world._move_path.is_empty() and frames < 5000:
		world._follow_move_path(1.0 / 60.0, 120.0)
		if world._collision.point_blocked(world._desired_position, world._dynamic_rects("")):
			stayed_free = false
		frames += 1
	_check(stayed_free, "персонаж не входит в препятствия по пути")
	_check(world._desired_position.distance_to(Vector2(208.0, 112.0)) < 2.0, "персонаж доходит до точки клика")
	_check(not world._has_move_target, "после прибытия маркер цели снят")
	_check(not world._set_move_path(Vector2(144.0, 80.0)) and world._move_path.is_empty(), "клик по лесу не ставит путь")

	var mob_position := Vector2(240.0, 200.0)
	GameSession.world_snapshot = {
		"player": player,
		"mobs": [{"id": "m1", "x": mob_position.x, "y": mob_position.y, "state": "alive", "hp": 10}],
		"animals": [],
	}
	world._desired_position = Vector2(80.0, 112.0)
	world._selected_mob_id = "m1"
	world._repath_timer = 0.0
	frames = 0
	stayed_free = true
	while frames < 5000 and world._distance_to_mob_body(mob_position) > 60.0:
		world._update_chase_path(1.0 / 60.0, player)
		world._follow_move_path(1.0 / 60.0, 120.0)
		if world._collision.point_blocked(world._desired_position, world._dynamic_rects("m1")):
			stayed_free = false
		frames += 1
	_check(world._distance_to_mob_body(mob_position) <= 60.0, "погоня доводит персонажа до дистанции удара")
	_check(stayed_free, "погоня не проходит через стену и не входит в препятствия")
	_check(world._selected_mob_id == "m1", "цель остаётся выбранной во время погони")

	# Во Front Line сосед перекрывает центр цели: путь к центру пустой и герой стоял бы. Он должен подойти к телу.
	GameSession.world = {"server_url": UNREACHABLE_URL, "mode": "front_line"}
	var crowd_target := {"id": "m1", "x": 240.0, "y": 200.0, "state": "alive", "hp": 10, "front_line": true}
	GameSession.world_snapshot = {
		"player": {"reach": 32.0},
		"mobs": [crowd_target, {"id": "m2", "x": 244.0, "y": 204.0, "state": "alive", "hp": 10, "front_line": true}],
		"animals": [],
	}
	world._desired_position = Vector2(80.0, 112.0)
	world._selected_mob_id = "m1"
	world._repath_timer = 0.0
	frames = 0
	while frames < 5000 and world._distance_to_mob_body(Vector2(240.0, 200.0), crowd_target) > 32.0:
		world._update_chase_path(1.0 / 60.0, {"reach": 32.0})
		world._follow_move_path(1.0 / 60.0, 120.0)
		frames += 1
	_check(world._distance_to_mob_body(Vector2(240.0, 200.0), crowd_target) <= 32.0,
		"во Front Line герой подходит на дистанцию удара, даже если сосед перекрывает центр цели")
	GameSession.world = {"server_url": UNREACHABLE_URL}

	world._desired_position = Vector2(80.0, 112.0)
	_check(world._is_adjacent_to_crystal(Vector2i(6, 7)), "кристалл рядом с персонажем распознаётся")
	_check(world._start_harvest_path(Vector2i(6, 7)) and world._move_path.is_empty(), "рядом с кристаллом путь не нужен")

	remove_child(world)
	world.free()
	GameSession.clear()


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
