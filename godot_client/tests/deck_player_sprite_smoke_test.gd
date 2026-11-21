extends Node

# Спрайты персонажа и лесника карты мира Deck: пути, направления, кадры, размеры и привязка как в
# deck/scenes/world_map_scene.py. Эталон — pygame 2.6.1 (.venv_313): get_bounding_rect первого кадра,
# ширина после масштаба до 56 px, сумма байтов и число непрозрачных пикселей срезов лесника.
const RULES := preload("res://scripts/deck_player_sprite_rules.gd")
const LAYER_SCRIPT := preload("res://scripts/deck_world_sprites.gd")
const RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const MAP_RULES := preload("res://scripts/deck_world_map_rules.gd")
const FIXTURES := preload("res://tests/deck_world_map_fixtures.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const IDLE_CROP := {
	"n": [237, 121, 551, 827], "ne": [303, 98, 435, 849], "e": [358, 78, 310, 849], "se": [275, 113, 457, 833],
	"s": [260, 99, 515, 847], "sw": [293, 89, 450, 857], "w": [318, 110, 345, 812], "nw": [295, 140, 441, 804],
}
const IDLE_WIDTHS := {"n": 37, "ne": 28, "e": 20, "se": 30, "s": 34, "sw": 29, "w": 23, "nw": 30}
const RUN_CROP := {
	"n": [179, 83, 311, 545], "ne": [183, 66, 335, 556], "e": [124, 93, 435, 529], "se": [175, 85, 383, 544],
	"s": [183, 58, 330, 571], "sw": [146, 53, 380, 571], "w": [162, 104, 393, 515], "nw": [170, 75, 336, 551],
}
const RUN_WIDTHS := {"n": 31, "ne": 33, "e": 46, "se": 39, "s": 32, "sw": 37, "w": 42, "nw": 34}
# Срезы листа лесника при сдвигах -240, 0, 239: сумма байтов RGBA, число пикселей с alpha > 0 и границы содержимого.
const FORESTER_SUMS := [27339194, 27113296, 27845639]
const FORESTER_ALPHA := [45942, 45677, 46628]
const FORESTER_BOUNDS := [[3, 15, 223, 313], [15, 6, 221, 322], [19, 15, 219, 313]]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_paths()
	_check_directions()
	_check_frame_timing()
	_check_player_frames()
	_check_forester_slices()
	_check_rotation_and_badge()
	_check_missing_assets()
	await _check_renderer_layer()
	await _check_deck_walk()
	GameSession.clear()
	if _checks == 0:
		_check(false, "проверки спрайтов выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_player_sprite_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_paths() -> void:
	_check(RULES.assets_root("C:/game/godot_client/") == "C:/game/assets", "корень ассетов — ../assets от godot_client")
	_check(RULES.assets_root("C:/game/godot_client") == "C:/game/assets", "корень без завершающей косой черты тот же")
	var root := RULES.assets_root(ProjectSettings.globalize_path("res://"))
	_check(root.ends_with("/assets") and DirAccess.dir_exists_absolute(root.path_join("2Idle/n")), "реальный корень ассетов содержит 2Idle/n")
	_check(FileAccess.file_exists(root.path_join(RULES.FORESTER_FILE)), "лист лесника лежит в ../assets, не в проекте")
	var names := RULES.frame_names(root.path_join("2Idle/n"))
	_check(names.size() == 4 and names[0].ends_with("-01.png") and names[3].ends_with("-04.png"), "стойка: четыре кадра по имени, без apng и spritesheet")
	_check(RULES.frame_names(root.path_join("3run/e")).size() == 6, "бег: шесть кадров направления e")
	_check(RULES.frame_names("C:/нет/такой/папки").is_empty(), "несуществующая папка даёт пустой список")


func _check_directions() -> void:
	var cases := {
		Vector2(1, 0): "e", Vector2(0, 1): "s", Vector2(-1, 0): "w", Vector2(0, -1): "n",
		Vector2(1, 1): "se", Vector2(-1, 1): "sw", Vector2(-1, -1): "nw", Vector2(1, -1): "ne",
	}
	for vector in cases:
		_check(RULES.direction_for(vector) == cases[vector], "вектор %s даёт направление %s" % [vector, cases[vector]])
	var angles := {10.0: "e", 30.0: "se", 80.0: "s", 120.0: "sw", 170.0: "w", -170.0: "w", -140.0: "nw", -100.0: "n", -50.0: "ne", -10.0: "e"}
	for angle in angles:
		_check(RULES.direction_for(Vector2.from_angle(deg_to_rad(angle))) == angles[angle], "угол %.0f° даёт %s" % [angle, angles[angle]])
	_check(RULES.direction_for(Vector2(cos(deg_to_rad(22.4)), sin(deg_to_rad(22.4)))) == "e", "граница 22.5°: 22.4° остаётся e")
	_check(RULES.direction_for(Vector2(cos(deg_to_rad(22.6)), sin(deg_to_rad(22.6)))) == "se", "граница 22.5°: 22.6° уже se")
	_check(RULES.direction_for(Vector2(cos(deg_to_rad(-22.6)), sin(deg_to_rad(-22.6)))) == "ne", "угол −22.6° даёт ne, как в Python")


func _check_frame_timing() -> void:
	_check(RULES.frame_index(0.0, RULES.IDLE_FPS, 4) == 0, "стойка начинается с первого кадра")
	_check(RULES.frame_index(0.26, RULES.IDLE_FPS, 4) == 1, "стойка 4 кадра/с: через 0.26 с второй кадр")
	_check(RULES.frame_index(1.0, RULES.IDLE_FPS, 4) == 0, "стойка зацикливается через секунду")
	_check(RULES.frame_index(0.35, RULES.RUN_FPS, 6) == 3 and RULES.frame_index(0.6, RULES.RUN_FPS, 6) == 0, "бег 10 кадров/с по шести кадрам")
	_check(RULES.forester_frame_index(0.34, 3) == 0 and RULES.forester_frame_index(0.35, 3) == 1 and RULES.forester_frame_index(0.7, 3) == 2, "лесник меняет кадр каждые 0.35 с")
	_check(RULES.forester_frame_index(1.1, 3) == 0, "смена кадров лесника зацикливается")
	_check(is_equal_approx(RULES.WALK_STEP_SECONDS, 48.0 / (220.0 * 48.0 / 32.0)), "шаг тайла 48 px занимает 48 / (220 * 48 / 32) с, как у игрока Python")
	_check(RULES.frames_for_direction({"e": ["a"]}, "w") == ["a"], "нет своего направления — первый набор, как в Python")
	_check(RULES.frames_for_direction({}, "n").is_empty(), "без кадров пустой набор")


func _check_player_frames() -> void:
	var root := RULES.assets_root(ProjectSettings.globalize_path("res://"))
	var idle := RULES.directional_frames(root.path_join(RULES.IDLE_FOLDER), RULES.PLAYER_TARGET_HEIGHT)
	var run := RULES.directional_frames(root.path_join(RULES.RUN_FOLDER), RULES.PLAYER_TARGET_HEIGHT)
	_check(idle.keys() == RULES.DIRECTIONS and run.keys() == RULES.DIRECTIONS, "все восемь направлений загружены в порядке n, ne, e, ...")
	for direction in RULES.DIRECTIONS:
		var idle_frames: Array = idle[direction]
		var run_frames: Array = run[direction]
		_check(idle_frames.size() == 4 and run_frames.size() == 6, "%s: четыре кадра стойки и шесть кадров бега" % direction)
		var idle_first := RULES.frame_names(root.path_join("2Idle").path_join(direction))[0]
		var run_first := RULES.frame_names(root.path_join("3run").path_join(direction))[0]
		_check(_rect(IDLE_CROP[direction]) == RULES.used_rect(root.path_join("2Idle").path_join(direction).path_join(idle_first)), "стойка %s: обрезка первого кадра как get_bounding_rect в pygame" % direction)
		_check(_rect(RUN_CROP[direction]) == RULES.used_rect(root.path_join("3run").path_join(direction).path_join(run_first)), "бег %s: обрезка первого кадра как get_bounding_rect в pygame" % direction)
		_check(_is_scaled_to(idle_frames, IDLE_WIDTHS[direction]), "стойка %s: высота 56 px, ширина %d как в Python" % [direction, IDLE_WIDTHS[direction]])
		_check(_is_scaled_to(run_frames, RUN_WIDTHS[direction]), "бег %s: высота 56 px, ширина %d как в Python" % [direction, RUN_WIDTHS[direction]])


func _check_forester_slices() -> void:
	var root := RULES.assets_root(ProjectSettings.globalize_path("res://"))
	var sheet := Image.load_from_file(root.path_join(RULES.FORESTER_FILE))
	if sheet == null or sheet.is_empty():
		_check(false, "лист лесника читается")
		return
	_check(sheet.get_size() == Vector2i(725, 582), "лист лесника 725x582, как в pygame")
	sheet.convert(Image.FORMAT_RGBA8)
	for index in range(RULES.FORESTER_SHIFTS.size()):
		var shift: int = RULES.FORESTER_SHIFTS[index]
		var frame := RULES.forester_slice(sheet, shift)
		_check(_byte_sum(frame) == FORESTER_SUMS[index], "срез лесника при сдвиге %d совпадает с pygame по сумме байтов" % shift)
		_check(_alpha_count(frame) == FORESTER_ALPHA[index], "срез лесника при сдвиге %d: непрозрачных пикселей как в pygame" % shift)
		_check(frame.get_used_rect() == _rect(FORESTER_BOUNDS[index]), "срез лесника при сдвиге %d: границы содержимого как в pygame" % shift)
	var frames := RULES.forester_frames(root.path_join(RULES.FORESTER_FILE), 48)
	_check(frames.size() == 3 and frames[0].get_size() == Vector2(480, 480), "три кадра лесника по 480 px (10 тайлов по 48 px)")
	_check(frames.size() == 3 and frames[0].get_image().get_data() != frames[1].get_image().get_data(), "кадры дыма лесника различаются")
	_check(RULES.forester_frames(root.path_join(RULES.FORESTER_FILE), 48) == frames, "повторный вызов берёт кадры из кэша")


func _check_rotation_and_badge() -> void:
	_check(RULES.rotated_bounds(Vector2(480, 480), 180).is_equal_approx(Vector2(480, 480)), "поворот на 180° не меняет холст лесника")
	_check(RULES.rotated_bounds(Vector2(480, 480), 90).is_equal_approx(Vector2(480, 480)), "поворот на 90° не меняет квадрат")
	_check(RULES.rotated_bounds(Vector2(100, 50), 90).is_equal_approx(Vector2(50, 100)), "поворот на 90° меняет стороны прямоугольника")
	_check(RULES.forester_badge_text("Лагерь лесорубов") == "🌲 Лагерь лесорубов [10x10]", "подпись лесника как в Python")
	var objects := MAP_RULES.objects_for({"objects": [{"id": "lumber_camp", "name": "Лагерь лесорубов", "tile_x": 41, "tile_y": 83, "tile_w": 10, "tile_h": 10, "rotation": -90}]})
	_check(objects[0]["kind"] == "forester" and objects[0]["rotation"] == 270, "лесник в объектах карты, поворот -90 приводится к 270 как в Python")


func _check_missing_assets() -> void:
	_check(RULES.directional_frames("C:/нет/2Idle", 56).is_empty(), "нет папки стойки: кадров нет, ошибки нет")
	_check(RULES.forester_frames("C:/нет/forester's1.png", 48).is_empty(), "нет листа лесника: кадров нет, ошибки нет")
	_check(RULES.used_rect("C:/нет/файл.png") == Rect2i(), "нет файла: пустая обрезка")


func _check_renderer_layer() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	renderer.configure({
		"terrain": _forester_terrain(),
		"center": Vector2i(46, 88),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
		"direction": "e",
		"player_name": "Тест",
		"anim_time": 0.0,
		"walking": false,
	})
	var layer = _find_layer(renderer)
	_check(layer != null and renderer.get_child_count() == 1, "слой фигурок — единственный дочерний узел карты, маркеров в окне нет")
	await get_tree().process_frame
	var state: Dictionary = layer.animation_state()
	_check(state["feet"] == Vector2(264, 264), "ноги персонажа в середине его плитки: (5.5, 5.5) тайла по 48 px")
	_check(state["frame_count"] == 4 and is_equal_approx(state["fps"], 4.0) and state["player_rect"] == Rect2(254, 208, 20, 56), "стойка на e: 4 кадра по 4 кадра/с, кадр 20x56, ноги в точке (264, 264)")
	_check(state["forester_rect"] == Rect2(0, 0, 480, 480), "лагерь лесника 10x10 от (41, 83) — в окне это (0, 0), 480 px")
	_check(state["player_name"] == "Тест" and state["direction"] == "e", "подпись и направление переданы в слой")
	_check(layer.draw_count() > 0, "слой нарисован без ошибок")
	renderer.set_animation(0.35, true)
	state = layer.animation_state()
	_check(state["frame_count"] == 6 and is_equal_approx(state["fps"], 10.0), "при ходьбе бег: шесть кадров, 10 кадров/с")
	_check(state["frame_index"] == 3 and state["player_rect"] == Rect2(241, 208, 46, 56), "бег на e: кадр 3, ширина 46, ноги в той же точке")
	renderer.set_animation(0.35, false)
	_check(layer.animation_state()["frame_count"] == 4, "после шага снова стойка")
	renderer.queue_free()
	await get_tree().process_frame


func _check_deck_walk() -> void:
	var deck = await _make_deck()
	deck._terrain = _forester_terrain()
	deck._map_position = Vector2i(46, 95)
	deck._render_location()
	var renderer = _find_renderer(deck)
	_check(renderer.marker_at(Vector2i(46, 95)).is_empty(), "на плитке игрока маркера нет: его рисует слой")
	_check(_find_button_text(deck, "@") == null, "кнопки «@» на карте нет")
	_check(_legend_text(deck).contains("фигурка персонажа") and not _legend_text(deck).contains("@"), "легенда описывает фигурку персонажа, а не «@»")

	deck._advance_map_animation(0.5)
	var time_before: float = deck._map_anim_time
	deck._move_world(0, -1)
	var layer = _find_layer(_find_renderer(deck))
	_check(deck._map_direction == "n" and deck._map_walk_seconds > 0.0, "шаг на север переводит персонажа в ходьбу")
	_check(layer.animation_state()["walking"] and layer.animation_state()["direction"] == "n", "слой получил ходьбу и направление шага")
	_check(is_equal_approx(layer.animation_state()["anim_time"], time_before), "после перестройки карты время кадров не сбрасывается")
	deck._advance_map_animation(0.05)
	_check(layer.animation_state()["walking"], "через 0.05 с шаг ещё идёт")
	deck._advance_map_animation(0.2)
	_check(not layer.animation_state()["walking"], "после шага (32 / 220 с) персонаж стоит")
	_check(is_equal_approx(layer.animation_state()["anim_time"], deck._map_anim_time), "слой показывает время карты деки")

	deck.queue_free()
	await get_tree().process_frame
	GameSession.clear()


func _forester_terrain() -> Dictionary:
	var terrain := FIXTURES.procedural_terrain()
	terrain["objects"].append({
		"id": "lumber_camp",
		"name": "Лагерь лесорубов",
		"tile_x": 41,
		"tile_y": 83,
		"tile_w": 10,
		"tile_h": 10,
		"rotation": 180,
	})
	return terrain


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
	deck._terrain = FIXTURES.procedural_terrain()
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
		"position_x": float(46 * 48 + 24),
		"position_y": float(95 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _is_scaled_to(frames: Array, width: int) -> bool:
	for frame in frames:
		if frame.get_height() != RULES.PLAYER_TARGET_HEIGHT or frame.get_width() != width:
			return false
	return true


func _byte_sum(image: Image) -> int:
	var total := 0
	for value in image.get_data():
		total += value
	return total


func _alpha_count(image: Image) -> int:
	var data := image.get_data()
	var count := 0
	for index in range(3, data.size(), 4):
		if data[index] != 0:
			count += 1
	return count


func _rect(values: Array) -> Rect2i:
	return Rect2i(int(values[0]), int(values[1]), int(values[2]), int(values[3]))


func _legend_text(node: Node) -> String:
	var text := ""
	for child in node.get_children():
		if child is Label:
			text += child.text + "\n"
		text += _legend_text(child)
	return text


func _find_layer(node: Node) -> Node:
	for child in node.get_children():
		if child.get_script() == LAYER_SCRIPT:
			return child
		var found := _find_layer(child)
		if found != null:
			return found
	return null


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
