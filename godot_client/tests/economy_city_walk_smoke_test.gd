extends Node

const RULES := preload("res://scripts/economy_city_layout_rules.gd")
const WALK_RULES := preload("res://scripts/economy_city_walk_rules.gd")
const SPRITE_RULES := preload("res://scripts/economy_player_sprite_rules.gd")
const CITY_MAP_SCRIPT := preload("res://scripts/economy_city_map.gd")
const PROFILE_RULES := preload("res://scripts/character_profile_rules.gd")
const TARGET_STREET := Vector2(2704.0, 1616.0)
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
# Двери из city_scene.py (update(), строки 1090–1169): тайл двери, окно и точка, куда выталкивается герой.
const DOOR_CASES := [
	{"tile": Vector2i(110, 30), "window": "tavern", "push": Vector2i(108, 30)},
	{"tile": Vector2i(32, 80), "window": "barn", "push": Vector2i(34, 80)},
	{"tile": Vector2i(32, 46), "window": "warehouse", "push": Vector2i(34, 46)},
	{"tile": Vector2i(46, 56), "window": "forge", "push": Vector2i(44, 56)},
	{"tile": Vector2i(46, 32), "window": "workshop", "push": Vector2i(44, 32)},
	{"tile": Vector2i(168, 86), "window": "barracks", "push": Vector2i(168, 88)},
	{"tile": Vector2i(88, 30), "window": "engineering", "push": Vector2i(90, 30)},
	{"tile": Vector2i(46, 168), "window": "university", "push": Vector2i(46, 166)},
	{"tile": Vector2i(38, 146), "window": "academy", "push": Vector2i(40, 146)},
	{"tile": Vector2i(88, 132), "window": "mage_school", "push": Vector2i(90, 132)},
]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_path_avoids_solids()
	_check_path_ends_at_target()
	_check_unreachable_targets()
	_check_entrances_are_walkable()
	_check_marker_follows_path()
	_check_walk_speed()
	_check_building_click_opens_without_walk()
	_check_each_door_opens_and_pushes()
	_check_walk_onto_door_opens_window()
	_check_left_click_on_ground_changes_nothing()
	_check_gate_is_hint_only()
	_check_world_reports_open_windows()
	_check_pause_and_right_click()
	_check_camera_follow()
	_check_houses_follow_population()
	_check_player_sprites()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_city_walk_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_path_avoids_solids() -> void:
	var solids: Array[Rect2i] = RULES.solid_rects(RULES.DEFAULT_HOUSE_COUNT)
	var spawn: Vector2 = RULES.PLAYER_SPAWN_PX
	var targets := [
		Vector2(1803.5, 1797.25), Vector2(1100.0, 1100.0), Vector2(500.0, 1500.0), Vector2(1600.0, 2900.0),
		Vector2(2900.0, 2000.0), Vector2(900.0, 2200.0), Vector2(2600.0, 600.0), Vector2(1200.0, 300.0),
		TARGET_STREET,
	]
	for target: Vector2 in targets:
		var path: Array = WALK_RULES.find_path(spawn, target, solids)
		_check(not path.is_empty(), "путь до %s найден" % str(target))
		if path.is_empty():
			continue
		var clear := true
		var crosses_footprint := false
		for point: Vector2 in path:
			if WALK_RULES.is_blocked(point, solids):
				clear = false
			var footprint := RULES.building_at_world(point)
			if not footprint.is_empty() and Vector2i(floori(point.x / 16.0), floori(point.y / 16.0)) != footprint["entrance"]:
				crosses_footprint = true
		_check(clear, "точки пути до %s не задевают стены, здания и дома" % str(target))
		_check(not crosses_footprint, "путь до %s не заходит в здания, кроме их входов" % str(target))
		var position := spawn
		var steps: Array = path.duplicate()
		var every_frame_clear := true
		var guard := 0
		while not steps.is_empty() and guard < 100000:
			var result: Dictionary = WALK_RULES.follow_path(position, steps, 2.0, solids)
			position = result["position"]
			if WALK_RULES.is_blocked(position, solids):
				every_frame_clear = false
			if not bool(result["moved"]):
				break
			guard += 1
		_check(every_frame_clear, "каждый кадр пути до %s свободен от препятствий" % str(target))
		_check(position.distance_to(target) < 0.001, "персонаж доходит до %s" % str(target))


func _check_path_ends_at_target() -> void:
	var solids: Array[Rect2i] = RULES.solid_rects(RULES.DEFAULT_HOUSE_COUNT)
	var target := Vector2(1803.5, 1797.25)
	var path: Array = WALK_RULES.find_path(RULES.PLAYER_SPAWN_PX, target, solids)
	_check(not path.is_empty() and path.back() == target, "последняя точка пути — выбранная цель")
	var street: Array = WALK_RULES.find_path(RULES.PLAYER_SPAWN_PX, TARGET_STREET, solids)
	_check(street.back() == TARGET_STREET, "путь по улице заканчивается в клике")


func _check_unreachable_targets() -> void:
	var solids: Array[Rect2i] = RULES.solid_rects(RULES.DEFAULT_HOUSE_COUNT)
	var spawn: Vector2 = RULES.PLAYER_SPAWN_PX
	_check(WALK_RULES.find_path(spawn, Vector2(2400.0, 2200.0), solids).is_empty(), "тело замка недостижимо")
	_check(WALK_RULES.find_path(spawn, Vector2(1600.0, 1600.0), solids).is_empty(), "кристалл жизни недостижим")
	var first_house := Vector2(RULES.house_solid_rect(RULES.HOUSE_LOTS[0]).get_center())
	_check(WALK_RULES.find_path(spawn, first_house, solids).is_empty(), "дом жителя недостижим")
	_check(WALK_RULES.find_path(spawn, Vector2(-50.0, 500.0), solids).is_empty(), "точка за картой недостижима")
	var map = _make_map()
	_check(not map.order_walk(Vector2(2400.0, 2200.0)) and map.walk_path().is_empty(), "ПКМ по замку не задаёт путь")
	map.queue_free()


func _check_entrances_are_walkable() -> void:
	var solids: Array[Rect2i] = RULES.solid_rects(0)
	for building in RULES.BUILDINGS:
		var building_id := str(building["id"])
		var entrance: Vector2i = building["entrance"]
		_check(not WALK_RULES.is_blocked(_tile_center(entrance), solids), "вход %s проходим" % building_id)


func _check_marker_follows_path() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	_check(map.order_walk(TARGET_STREET), "клик по улице задаёт путь")
	var planned: Array = map.walk_path()
	var polyline := PackedVector2Array([RULES.PLAYER_SPAWN_PX])
	for point: Vector2 in planned:
		polyline.append(point)
	var on_path := true
	var moved := false
	for index in range(40):
		map.step_walk(1.0 / 60.0)
		var position: Vector2 = map.player_position()
		if position.distance_to(RULES.PLAYER_SPAWN_PX) > 0.01:
			moved = true
		if _distance_to_polyline(position, polyline) > 0.01:
			on_path = false
	_check(moved, "маркер сдвинулся с точки спавна")
	_check(on_path, "каждая позиция маркера лежит на пути")
	_check(map.is_walking(), "во время ходьбы герой в состоянии «walk»")
	map.queue_free()


func _check_walk_speed() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	map.order_walk(TARGET_STREET)
	var planned: Array = map.walk_path()
	var start: Vector2 = map.player_position()
	map.step_walk(0.5)
	_check(map.player_position().distance_to(_point_along(start, planned, 110.0)) < 0.01, "без груза герой идёт 220 px/с")

	var character := {"id": 42, "stats": {"strength": 10, "endurance": 10}, "carried_weight_kg": 0.0}
	var capacity := PROFILE_RULES.carry_capacity(character)
	character["carried_weight_kg"] = capacity * 0.9
	GameSession.character = character
	_check(is_equal_approx(PROFILE_RULES.character_movement_multiplier(character), 0.3), "перегруз даёт множитель 0.3")
	map.order_walk(TARGET_STREET)
	planned = map.walk_path()
	start = map.player_position()
	map.step_walk(1.0)
	_check(map.player_position().distance_to(_point_along(start, planned, 66.0)) < 0.01, "перегруженный герой идёт 66 px/с")
	GameSession.character = {}
	map.queue_free()


func _check_building_click_opens_without_walk() -> void:
	var map = _make_map()
	var keys: Array[String] = []
	map.building_clicked.connect(func(key: String) -> void: keys.append(key))
	var barn := RULES.building_by_id("barn_building")
	_click(map, RULES.building_world_rect(barn).get_center())
	_check(keys == ["barn"], "клик по амбару открывает его окно")
	_check(not map.is_walking() and map.walk_path().is_empty(), "клик по зданию не ведёт героя к входу")
	map.queue_free()


# Каждая дверь из city_scene.py: таблица совпадает с окном здания, окно открывается один раз, герой выталкивается и стоит.
func _check_each_door_opens_and_pushes() -> void:
	for door: Dictionary in DOOR_CASES:
		var tile: Vector2i = door["tile"]
		var window := str(door["window"])
		var push_tile: Vector2i = door["push"]
		var table_door: Dictionary = RULES.door_at_tile(tile)
		_check(table_door.get("window", "") == window and table_door.get("push") == push_tile
			and RULES.window_key(RULES.building_at_tile(tile)) == window, "таблица дверей совпадает с city_scene.py: %s" % window)
		_check(not WALK_RULES.is_blocked(RULES.tile_center(push_tile), RULES.solid_rects(RULES.HOUSE_LOTS.size())),
			"точка выталкивания у двери %s свободна" % window)
		var map = _make_map()
		var open_windows := {}
		var opened: Array[String] = []
		map.window_is_open = func(key: String) -> bool: return open_windows.has(key)
		var on_open := func(key: String) -> void:
			opened.append(key)
			open_windows[key] = true
		map.building_clicked.connect(on_open)
		map._player = _tile_center(tile)
		map.step_walk(1.0 / 60.0)
		_check(opened == [window], "дверь %s открывает своё окно" % window)
		_check(map.player_position().is_equal_approx(_tile_center(push_tile)),
			"дверь %s выталкивает героя на тайл %s" % [window, str(push_tile)])
		_check(not map.is_walking(), "после выталкивания дверью %s герой стоит" % window)
		map._player = _tile_center(tile)
		map.step_walk(1.0 / 60.0)
		_check(opened == [window] and map.player_position().is_equal_approx(_tile_center(tile)),
			"дверь %s не открывает окно повторно, пока оно открыто" % window)
		map.queue_free()


# Настоящий путь: ПКМ по двери амбара из спавна. Дверь срабатывает при входе на тайл, окно открывается один раз.
func _check_walk_onto_door_opens_window() -> void:
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	var map = _make_map()
	var open_windows := {}
	var opened: Array[String] = []
	map.window_is_open = func(key: String) -> bool: return open_windows.has(key)
	var on_open := func(key: String) -> void:
		opened.append(key)
		open_windows[key] = true
	map.building_clicked.connect(on_open)
	_send_button(map, map.world_to_screen(_tile_center(Vector2i(32, 80))), true, MOUSE_BUTTON_RIGHT)
	_check(not map.walk_path().is_empty(), "путь от спавна до двери амбара найден")
	var steps := 0
	while opened.is_empty() and steps < 6000:
		map.step_walk(1.0 / 60.0)
		steps += 1
	_check(opened == ["barn"], "ходьба на дверь амбара открывает окно")
	_check(map.player_position().is_equal_approx(_tile_center(Vector2i(34, 80))), "после выталкивания герой стоит у двери (34, 80)")
	_check(not map.is_walking() and not map.walk_path().is_empty(), "оставшийся путь сохраняется, как move_path в city_scene.py")
	map.set_walk_paused(true)
	var pushed: Vector2 = map.player_position()
	map.step_walk(1.0 / 60.0)
	_check(map.player_position() == pushed and opened == ["barn"], "пока окно открыто, герой стоит и окно не открывается снова")
	GameSession.character = {}
	map.queue_free()


# Левый клик по пустой земле не меняет ни путь, ни позицию героя: путь строит только правая кнопка.
func _check_left_click_on_ground_changes_nothing() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	_send_button(map, map.world_to_screen(TARGET_STREET), true, MOUSE_BUTTON_RIGHT)
	for index in range(20):
		map.step_walk(1.0 / 60.0)
	var path_before: Array = map.walk_path()
	var position_before: Vector2 = map.player_position()
	_check(not path_before.is_empty() and map.is_walking(), "ПКМ запускает ходьбу")
	_click(map, Vector2(1800.0, 1800.0))
	_check(map.walk_path() == path_before, "левый клик по земле не меняет путь героя")
	_check(map.player_position() == position_before, "левый клик по земле не двигает героя")
	_walk_until_idle(map)
	var idle_position: Vector2 = map.player_position()
	_click(map, Vector2(2100.0, 1616.0))
	_check(map.walk_path().is_empty() and map.player_position() == idle_position and not map.is_walking(),
		"левый клик по земле у стоящего героя ничего не делает")
	GameSession.character = {}
	map.queue_free()


# Ворота только показывают заметку: путь не останавливается, на карту мира герой не уходит, окна не открываются.
func _check_gate_is_hint_only() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	var gates: Array[String] = []
	var buildings: Array[String] = []
	map.gate_clicked.connect(func(gate: Dictionary) -> void: gates.append(str(gate["id"])))
	map.building_clicked.connect(func(key: String) -> void: buildings.append(key))
	var east_center: Vector2 = RULES.gate_world_rect(_gate("east")).get_center()
	_click(map, east_center)
	_check(gates == ["east"] and map.walk_path().is_empty(), "клик по воротам показывает заметку и не ведёт героя")
	var beyond := Vector2(3180.0, 1600.0)
	_send_button(map, map.world_to_screen(beyond), true, MOUSE_BUTTON_RIGHT)
	_walk_until_idle(map)
	_check(gates == ["east", "east"], "при входе в проём пешком заметка показывается один раз")
	_check(map.player_position().distance_to(beyond) < 0.01, "ворота не останавливают путь: герой доходит до точки за проёмом")
	_check(buildings.is_empty(), "проход через ворота не открывает ни одного окна")
	GameSession.character = {}
	map.queue_free()


# Карта спрашивает мир, открыто ли окно здания: по этому ответу дверь не открывает окно повторно.
func _check_world_reports_open_windows() -> void:
	GameSession.clear()
	GameSession.character = {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120,
		"silver": 0, "gold": 0, "carried_weight_kg": 0.0}
	GameSession.world = {}
	GameSession.world_token = "test-world-token"
	ApiClient.set_server_url(UNREACHABLE_URL)
	ApiClient.token = "test-world-token"
	ApiClient._http.timeout = 0.5
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	economy._chat_timer.stop()
	var is_open: Callable = economy._city_map.window_is_open
	economy._set_view("tavern")
	_check(is_open.call("tavern") and not is_open.call("barn"), "открытая таверна распознаётся")
	economy._set_view("storage")
	economy._selected_building = "barn"
	_check(is_open.call("barn") and not is_open.call("warehouse"), "амбар распознаётся по выбранному зданию")
	economy._selected_building = "warehouse"
	_check(is_open.call("warehouse") and not is_open.call("barn"), "склад распознаётся отдельно от амбара")
	economy._set_view("forge")
	_check(is_open.call("forge") and not is_open.call("warehouse"), "кузница распознаётся")
	economy._set_view("workshop")
	_check(is_open.call("workshop") and not is_open.call("forge"), "мастерская распознаётся")
	economy._open_static_building("mage_school")
	_check(is_open.call("mage_school") and not is_open.call("academy"), "статическое здание распознаётся по своему ключу")
	economy._set_view("map")
	_check(not is_open.call("mage_school") and not is_open.call("tavern"), "на карте города окон нет")
	remove_child(economy)
	economy.free()
	GameSession.clear()


func _check_pause_and_right_click() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	map.set_walk_paused(true)
	_send_button(map, map.world_to_screen(TARGET_STREET), true, MOUSE_BUTTON_RIGHT)
	_check(not map.walk_path().is_empty(), "ПКМ по улице задаёт путь")
	var before: Vector2 = map.player_position()
	map.step_walk(0.5)
	_check(map.player_position() == before and not map.is_walking(), "на паузе (открыто окно) герой стоит")
	map.set_walk_paused(false)
	map.step_walk(0.5)
	_check(map.player_position() != before, "после закрытия окна путь продолжается")
	GameSession.character = {}
	map.queue_free()


func _check_camera_follow() -> void:
	var map = _make_map()
	GameSession.character = {"id": 42, "carried_weight_kg": 0.0}
	map.order_walk(TARGET_STREET)
	map._process(1.0 / 60.0)
	_check(map.camera_center.is_equal_approx(RULES.TILE_PX * Vector2(100.0, 100.0)), "вся карта видна — камера стоит по центру")
	_send_wheel(map, Vector2(450.0, 240.0), MOUSE_BUTTON_WHEEL_UP)
	_send_wheel(map, Vector2(450.0, 240.0), MOUSE_BUTTON_WHEEL_UP)
	map.center_on_player()
	_check(map.camera_center.is_equal_approx(map.player_position()), "кнопка «К герою» центрирует камеру на герое")
	map.order_walk(Vector2(2000.0, 1616.0))
	for index in range(30):
		map.step_walk(1.0 / 60.0)
		map._process(1.0 / 60.0)
	_check(map.camera_center.is_equal_approx(map.player_position()), "при зуме камера следует за героем")
	var camera_before_drag: Vector2 = map.camera_center
	_send_button(map, Vector2(300.0, 200.0), true, MOUSE_BUTTON_LEFT)
	_send_motion(map, Vector2(360.0, 200.0), Vector2(60.0, 0.0), MOUSE_BUTTON_MASK_LEFT)
	_send_button(map, Vector2(360.0, 200.0), false, MOUSE_BUTTON_LEFT)
	var camera_after_drag: Vector2 = map.camera_center
	_check(not camera_after_drag.is_equal_approx(camera_before_drag), "перетаскивание двигает камеру")
	map.step_walk(1.0 / 60.0)
	map._process(1.0 / 60.0)
	_check(map.camera_center.is_equal_approx(camera_after_drag), "после перетаскивания камера не возвращается к герою")
	GameSession.character = {}
	map.queue_free()


func _check_houses_follow_population() -> void:
	var map = _make_map()
	map.set_city_state({}, {})
	_check(map._house_count() == RULES.DEFAULT_HOUSE_COUNT, "без данных о населении — четыре дома, как в city_scene.py")
	map.set_city_state({"population": 2}, {})
	_check(map._house_count() == 2 and _count_houses(map._solid_rects()) == 2, "солидными становятся только живущие дома")
	map.set_city_state({"population": 40}, {})
	_check(map._house_count() == RULES.HOUSE_LOTS.size(), "домов не больше участков")
	_check(RULES.house_solid_rect([32, 20, 6, 6, 3]) == Rect2i(507, 280, 106, 136), "прямоугольник дома совпадает с rendering.py (участок 6x6 клеток)")
	map.queue_free()


func _check_player_sprites() -> void:
	var root := SPRITE_RULES.assets_root(ProjectSettings.globalize_path("res://"))
	var sets: Dictionary = SPRITE_RULES.frame_sets(root)
	_check(not (sets["idle"] as Dictionary).is_empty() and not (sets["run"] as Dictionary).is_empty(),
		"стойка 2Idle и бег 3run грузятся из ../assets")
	var idle_frame := SPRITE_RULES.frame_for(sets, false, "e", 0.0)
	var run_frame := SPRITE_RULES.frame_for(sets, true, "s", 0.3)
	_check(idle_frame is Texture2D and run_frame is Texture2D, "кадры стойки и бега выбираются по направлению")
	_check(idle_frame != null and idle_frame.get_height() == 90, "кадр героя масштабируется до 90 px, как в Python")
	_check(SPRITE_RULES.frame_for({}, true, "s", 0.0) == null, "без кадров возвращается null, рисуется маркер")
	_check(SPRITE_RULES.is_warrior({"type": "warrior"}) and not SPRITE_RULES.is_warrior({"type": "mage"}),
		"кадры воина выбираются по профессии warrior, остальные классы берут стойку и бег 2Idle/3run")


func _make_map():
	var map = CITY_MAP_SCRIPT.new()
	map.custom_minimum_size = Vector2(900, 480)
	add_child(map)
	map.size = Vector2(900, 480)
	map.fit_map()
	return map


func _tile_center(tile: Vector2i) -> Vector2:
	return Vector2(tile * RULES.TILE_PX) + Vector2(RULES.TILE_PX, RULES.TILE_PX) * 0.5


func _walk_until_idle(map) -> void:
	var steps := 0
	while not map.walk_path().is_empty() and steps < 6000:
		map.step_walk(1.0 / 60.0)
		steps += 1
	_check(map.walk_path().is_empty(), "путь завершается за разумное число кадров")


func _click(map, world: Vector2) -> void:
	var screen: Vector2 = map.world_to_screen(world)
	_send_button(map, screen, true, MOUSE_BUTTON_LEFT)
	_send_button(map, screen, false, MOUSE_BUTTON_LEFT)


func _send_button(map, position: Vector2, pressed: bool, button: MouseButton) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = pressed
	event.position = position
	map._gui_input(event)


func _send_wheel(map, position: Vector2, button: MouseButton) -> void:
	_send_button(map, position, true, button)


func _send_motion(map, position: Vector2, relative: Vector2, mask: MouseButtonMask) -> void:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.relative = relative
	event.button_mask = mask
	map._gui_input(event)


# Точка на расстоянии distance вдоль ломаной start → path.
func _point_along(start: Vector2, path: Array, distance: float) -> Vector2:
	var current := start
	var left := distance
	for point: Vector2 in path:
		var segment := current.distance_to(point)
		if segment >= left:
			return current.lerp(point, left / segment)
		left -= segment
		current = point
	return current


func _distance_to_polyline(point: Vector2, polyline: PackedVector2Array) -> float:
	var best := INF
	for index in range(polyline.size() - 1):
		var closest := Geometry2D.get_closest_point_to_segment(point, polyline[index], polyline[index + 1])
		best = minf(best, closest.distance_to(point))
	return best


func _count_houses(solids: Array) -> int:
	var houses := 0
	for lot in RULES.HOUSE_LOTS:
		if solids.has(RULES.house_solid_rect(lot)):
			houses += 1
	return houses


func _gate(gate_id: String) -> Dictionary:
	for gate in RULES.GATES:
		if str(gate["id"]) == gate_id:
			return gate
	_check(false, "ворота %s есть в таблице клиента" % gate_id)
	return {}


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
