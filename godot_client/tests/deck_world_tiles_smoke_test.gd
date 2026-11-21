extends Node

# Плитки карты мира Deck: окно вокруг игрока, виды тайлов, цвета, пустой рельеф и скрытие городских зон на опубликованной карте.
# Сеть не используется: запросы мира ждут в очереди (_pending_action занят), как в deck_arena_world_smoke_test.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RULES := preload("res://scripts/deck_world_map_rules.gd")
const RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const FIXTURES := preload("res://tests/deck_world_map_fixtures.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const CITY_MARKERS := ["T", "G", "S", "L", "Д"]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_window_math()
	_check_tile_lookup()
	_check_colours()
	await _check_renderer_window()
	await _check_empty_payload()
	await _check_published_hides_city()
	GameSession.clear()
	if _checks == 0:
		_check(false, "проверки плиток выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_world_tiles_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_window_math() -> void:
	_check(RULES.window_origin(Vector2i(12, 36), 11) == Vector2i(7, 31), "окно 11x11 центрируется на игроке")
	_check(RULES.window_origin(Vector2i(0, 0), 11) == Vector2i(-5, -5), "окно у края карты выходит за её пределы")
	_check(RULES.tile_rect(Vector2i(7, 31), Vector2i(7, 31), 48.0) == Rect2(0, 0, 48, 48), "левый верхний тайл окна стоит в начале")
	_check(RULES.tile_rect(Vector2i(17, 41), Vector2i(7, 31), 48.0) == Rect2(480, 480, 48, 48), "правый нижний тайл окна стоит в конце")
	_check(RULES.in_map(Vector2i(0, 0), Vector2i(128, 256)), "первый тайл карты в пределах")
	_check(RULES.in_map(Vector2i(127, 255), Vector2i(128, 256)), "последний тайл карты в пределах")
	_check(not RULES.in_map(Vector2i(-1, 0), Vector2i(128, 256)), "тайл левее карты за пределами")
	_check(not RULES.in_map(Vector2i(128, 0), Vector2i(128, 256)), "тайл правее карты за пределами")
	_check(RULES.is_neighbour(Vector2i(13, 36), Vector2i(12, 36)), "тайл справа — соседний")
	_check(RULES.is_neighbour(Vector2i(12, 35), Vector2i(12, 36)), "тайл сверху — соседний")
	_check(not RULES.is_neighbour(Vector2i(13, 37), Vector2i(12, 36)), "диагональ не считается соседней")
	_check(not RULES.is_neighbour(Vector2i(14, 36), Vector2i(12, 36)), "тайл через один шаг не соседний")
	_check(not RULES.is_neighbour(Vector2i(12, 36), Vector2i(12, 36)), "свой тайл не соседний")
	_check(RULES.tile_from([1]) == RULES.NO_TILE and RULES.tile_from("x") == RULES.NO_TILE, "битая координата даёт пустой тайл")


func _check_tile_lookup() -> void:
	var published := FIXTURES.published_terrain()
	var window := Rect2i(0, 0, 24, 20)
	var kinds := RULES.tile_kinds(published, window)
	_check(kinds.get(Vector2i(3, 3)) == "forest", "лес из набора forest виден как лес")
	_check(not kinds.has(Vector2i(4, 3)), "просвет в лесу остаётся без вида")
	_check(kinds.get(Vector2i(8, 1)) == "dry", "сухой лес виден отдельно")
	_check(kinds.get(Vector2i(12, 2)) == "water", "вода виден как вода")
	_check(kinds.get(Vector2i(14, 2)) == "bridge", "мост поверх воды виден как мост")
	_check(kinds.get(Vector2i(3, 12)) == "mountain", "горы перекрывают непроходимость")
	_check(kinds.get(Vector2i(8, 12)) == "impassable", "непроходимый тайл без горы виден как препятствие")
	_check(kinds.get(Vector2i(10, 9)) == "road", "набор paths виден как дорога")
	_check(kinds.get(Vector2i(19, 10)) == "berry", "ягоды видны как ягоды")
	_check(kinds.get(Vector2i(21, 16)) == "floor", "пол виден как пол")
	_check(kinds.get(Vector2i(10, 15)) == "stump", "пень из props виден как пень")
	_check(kinds.get(Vector2i(11, 16)) == "log", "бревно из props виден как бревно")
	_check(not kinds.has(Vector2i(0, 0)), "тайл без набора остаётся обычной землёй")
	_check(not RULES.tile_kinds(published, Rect2i(0, 0, 5, 5)).has(Vector2i(12, 2)), "вне окна виды тайлов не собираются")
	_check(RULES.tile_kinds({"roads": {"tiles": [[2, 2]]}}, window).get(Vector2i(2, 2)) == "road", "дорога из payload видна как дорога")
	_check(RULES.tile_kinds({"tiles": "сломано", "props": 5, "roads": []}, window).is_empty(), "битый рельеф не ломает поиск видов")

	var procedural := FIXTURES.procedural_terrain()
	var walls := RULES.wall_tiles(procedural)
	_check(walls.size() == 81, "стены города: кольцо без трёх ворот")
	_check(walls.has(Vector2i(0, 25)) and walls.has(Vector2i(24, 43)), "углы города входят в стены")
	_check(not walls.has(Vector2i(24, 34)), "ворота города не являются стеной")
	_check(RULES.city_bounds(procedural) == Rect2i(0, 25, 25, 19), "границы города берутся из payload")
	var objects := RULES.objects_for(procedural)
	_check(objects.size() == 3, "неопубликованная карта даёт кристалл, библиотеку и древо")
	_check(objects[0]["kind"] == "crystal" and objects[0]["rect"] == Rect2i(11, 33, 3, 3), "кристалл занимает 3x3 тайла из payload")
	_check(objects[1]["kind"] == "library" and objects[1]["rect"] == RULES.LIBRARY_BOUNDS, "библиотека занимает границы зоны")
	_check(objects[2]["kind"] == "talent" and objects[2]["rect"] == RULES.TALENT_BOUNDS, "древо занимает границы зоны")
	_check(RULES.objects_for(published).is_empty(), "опубликованная карта без объектов города")


func _check_colours() -> void:
	_check(RULES.tile_color("water").is_equal_approx(Color(56 / 255.0, 104 / 255.0, 168 / 255.0)), "вода окрашена цветом редактора")
	_check(RULES.tile_color("unknown") == RULES.VOID_COLOR, "неизвестный вид получает фон карты")
	_check(RULES.ground_color(false, Vector2i(5, 10), Vector2i(128, 256)).is_equal_approx(RULES.GRASS_COLORS[1]), "север карты — трава в шахматном порядке")
	_check(RULES.ground_color(false, Vector2i(5, 200), Vector2i(128, 256)).is_equal_approx(RULES.ROCK_COLORS[1]), "юг карты — каменистая пустошь")
	_check(RULES.ground_color(true, Vector2i(0, 0), Vector2i(24, 20)).is_equal_approx(RULES.PUBLISHED_GROUND_COLORS[0]), "опубликованная карта — земля редактора")
	_check(RULES.checker(RULES.PAVING_COLORS, Vector2i(1, 0)) == RULES.PAVING_COLORS[1], "мостовая чередуется по клеткам")
	_check(RULES.text_color_for(Color(0, 0, 0)).r > 0.5, "на тёмном маркере текст светлый")
	_check(RULES.text_color_for(Color(1, 1, 1)).r < 0.5, "на светлом маркере текст тёмный")


func _check_renderer_window() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	renderer.configure({
		"terrain": FIXTURES.procedural_terrain(),
		"center": Vector2i(12, 36),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
	})
	_check(renderer.custom_minimum_size == Vector2(528, 528), "карта 11x11 тайлов по 48 px занимает 528 px")
	_check(renderer.tile_at(Vector2(24, 24)) == Vector2i(7, 31), "верхний левый тайл окна находится по точке")
	_check(renderer.tile_at(Vector2(519, 519)) == Vector2i(17, 41), "нижний правый тайл окна находится по точке")
	_check(renderer.tile_at(Vector2(529, 10)) == RULES.NO_TILE, "точка правее окна не попадает в тайл")
	_check(renderer.tile_at(Vector2(-1, 10)) == RULES.NO_TILE, "точка левее окна не попадает в тайл")
	await get_tree().process_frame
	renderer.queue_free()
	await get_tree().process_frame


func _check_empty_payload() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	renderer.configure({})
	_check(renderer.get_child_count() == 0, "пустое состояние не создаёт маркеров")
	_check(renderer.tile_at(Vector2(5 * 48 + 1, 5 * 48 + 1)) == Vector2i(0, 0), "пустой рельеф: окно у края стоит на карте 128x256")
	renderer.configure({
		"terrain": {},
		"center": Vector2i(64, 128),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
		"markers": {},
		"solid": [],
		"steppable": [],
	})
	renderer.configure({"terrain": {"tiles": "сломано", "city_area": [], "objects": 3, "obstacles": "нет"}, "center": Vector2i(1, 1)})
	await get_tree().process_frame
	await get_tree().process_frame
	_check(renderer.is_inside_tree(), "пустой рельеф рисуется без ошибки")
	renderer.queue_free()
	await get_tree().process_frame


func _check_published_hides_city() -> void:
	var deck = await _make_deck()
	var published := FIXTURES.published_terrain()
	published["city_area"] = FIXTURES.procedural_terrain()["city_area"]
	published["library_area"] = FIXTURES.procedural_terrain()["library_area"]
	published["objects"] = FIXTURES.procedural_terrain()["objects"]
	_check(RULES.wall_tiles(published).is_empty() and RULES.city_bounds(published) == Rect2i(), "опубликованная карта не рисует стены и границы города")
	_check(RULES.objects_for(published).size() == 1, "опубликованная карта не добавляет зон библиотеки и древа")

	deck._terrain = published
	_check(not deck._is_tavern_tile(Vector2i(6, 27)), "опубликованная карта: таверна не отмечена")
	_check(not deck._is_guild_tile(Vector2i(20, 27)), "опубликованная карта: гильдия не отмечена")
	_check(not deck._is_supplies_shop_tile(Vector2i(15, 27)), "опубликованная карта: магазин не отмечен")
	_check(not deck._is_library_tile(Vector2i(20, 41)), "опубликованная карта: библиотека не отмечена")
	_check(not deck._is_talent_tile(Vector2i(22, 37)), "опубликованная карта: древо не отмечено")
	deck._map_position = Vector2i(12, 27)
	deck._render_location()
	var renderer = _find_renderer(deck)
	var city_letters := 0
	for symbol in CITY_MARKERS:
		if _find_button_text(deck, symbol) != null:
			city_letters += 1
	_check(city_letters == 0, "опубликованная карта: в окне нет букв городских зон")
	_check(renderer != null and renderer.get_child_count() == 1 and renderer.marker_at(Vector2i(12, 27)).is_empty(), "опубликованная карта: букв нет, остаётся только слой спрайтов игрока")

	deck._terrain = FIXTURES.procedural_terrain()
	deck._render_location()
	_check(_find_button_text(deck, "T") != null and _find_button_text(deck, "S") != null, "неопубликованная карта: буквы таверны и магазина на месте")
	deck.queue_free()
	await get_tree().process_frame
	GameSession.clear()


func _make_deck() -> Node:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = _character()
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	deck._pending_action = "stub"
	return deck


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _character() -> Dictionary:
	return {
		"id": 42,
		"name": "Тест",
		"type": "warrior",
		"level": 5,
		"hp": 60,
		"max_hp": 142,
		"mp": 20,
		"max_mp": 20,
		"coins": 500,
		"zone": "world_map",
		"position_x": float(12 * 48 + 24),
		"position_y": float(36 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _find_renderer(node: Node) -> Node:
	for child in node.get_children():
		if child.get_script() == RENDERER_SCRIPT:
			return child
		var found := _find_renderer(child)
		if found != null:
			return found
	return null


func _find_button_text(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button_text(child, text)
		if found != null:
			return found
	return null
