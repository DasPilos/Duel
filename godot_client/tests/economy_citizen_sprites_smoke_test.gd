extends Node

# Спрайты горожан на карте путей: кадры из ../assets, направления, номер кадра, запасная фигурка, иконка у подписи,
# прямоугольник выбора и перерисовка. Эталон — pygame 2.6.1 и scenes/player_sprites.py при высоте 90 px:
# ширина кадра по направлениям (после обрезки первого кадра по get_bounding_rect), как в player_frame.
const RULES := preload("res://scripts/economy_citizen_sprite_rules.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const TRAVEL_MAP_SCRIPT := preload("res://scripts/economy_travel_map.gd")
const FIXTURE_DIR := "res://tests/fixtures/economy/"
const RUN_WIDTHS := {"n": 51, "ne": 54, "e": 74, "se": 63, "s": 52, "sw": 59, "w": 68, "nw": 54}
const IDLE_WIDTHS := {"n": 59, "ne": 46, "e": 32, "se": 49, "s": 54, "sw": 47, "w": 38, "nw": 49}

var _failures: Array[String] = []
var _checks := 0
var _draws := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_constants()
	_check_frame_sets()
	_check_frame_choice()
	_check_fallbacks()
	_check_figure()
	_check_icon()
	_check_pick_box()
	await _check_map_draws()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_citizen_sprites_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_constants() -> void:
	_check(RULES.SPRITE_HEIGHT == 90, "высота кадра горожанина 90 px, как PLAYER_SPRITE_HEIGHT")
	_check(is_equal_approx(RULES.RUN_FPS, 8.0), "бег горожанина 8 кадров/с, как run_fps=8.0 в map_travel.py")
	_check(RULES.RUN_FOLDER == "3run" and RULES.IDLE_FOLDER == "2Idle", "папки бега и стойки названы как в scenes/player_sprites.py")


func _check_frame_sets() -> void:
	var root := DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://"))
	var run := RULES.frames_by_direction(root)
	_check(run.keys() == DECK_SPRITE.DIRECTIONS, "кадры горожан есть для восьми направлений в порядке n, ne, ...")
	var run_sizes := true
	var run_counts := true
	for direction in DECK_SPRITE.DIRECTIONS:
		var frames: Array = run.get(direction, [])
		run_counts = run_counts and frames.size() == 6
		run_sizes = run_sizes and not frames.is_empty() and _same_size(frames[0], Vector2(int(RUN_WIDTHS[direction]), 90.0))
	_check(run_counts, "бег: по шесть кадров в каждом направлении из 3run")
	_check(run_sizes, "бег: кадры 90 px в высоту, ширина как в pygame для каждого направления")

	var idle := RULES.frames_from_folders("C:/нет/3run", root.path_join("2Idle"))
	var idle_sizes := idle.keys() == DECK_SPRITE.DIRECTIONS
	for direction in DECK_SPRITE.DIRECTIONS:
		var frames: Array = idle.get(direction, [])
		idle_sizes = idle_sizes and frames.size() == 4 and _same_size(frames[0], Vector2(int(IDLE_WIDTHS[direction]), 90.0))
	_check(idle_sizes, "без папки бега берётся стойка 2Idle: четыре кадра 90 px, ширина как в pygame")
	_check(RULES.frames_from_folders("C:/нет/3run", "C:/нет/2Idle").is_empty(), "нет ни бега, ни стойки: кадров нет, ошибки нет")


func _check_frame_choice() -> void:
	var frames := RULES.frames_by_direction(DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://")))
	var east: Array = frames["e"]
	_check(RULES.frame_for(frames, "e", 0.0) == east[0], "в момент 0 с горожанин на первом кадре бега")
	_check(RULES.frame_for(frames, "e", 0.13) == east[1], "8 кадров/с: через 0.13 с второй кадр")
	_check(RULES.frame_for(frames, "e", 0.75) == east[0], "шесть кадров зацикливаются через 0.75 с")
	_check(RULES.frame_for(frames, "e", 1.0) == east[2], "через 1 с номер кадра 8 % 6 = 2, как в player_frame")
	_check(_same_size(RULES.frame_for(frames, "w", 0.0), Vector2(68.0, 90.0)), "направление w берёт свои кадры")
	_check(RULES.frame_for(frames, "", 0.0) == frames["n"][0], "неизвестное направление — первый набор, как next(iter(...)) в Python")


func _check_fallbacks() -> void:
	_check(RULES.frames_by_direction("C:/нет/assets").is_empty(), "нет папок ассетов: кадров нет, ошибки нет")
	_check(RULES.frame_for({}, "n", 0.0) == null, "без кадров возвращается null, и рисуется фигурка")


func _check_figure() -> void:
	var figure := RULES.figure_geometry(Vector2(100.0, 200.0))
	_check(_rect_close(figure["shadow"], Rect2(90.0, 197.0, 20.0, 7.0)), "тень фигурки (sx-10, sy-3, 20, 7), как map_travel.py:274")
	_check(figure["head"] == Vector2(100.0, 180.0) and is_equal_approx(float(figure["head_radius"]), 6.0),
		"голова фигурки: круг r=6 в (sx, sy-20), как map_travel.py:275")
	_check(_rect_close(figure["body"], Rect2(95.0, 186.0, 10.0, 14.0)) and is_equal_approx(float(figure["body_radius"]), 2.0),
		"тело фигурки (sx-5, sy-14, 10, 14) со скруглением 2, как map_travel.py:276")
	var ellipse := RULES.ellipse_points(figure["shadow"])
	_check(ellipse.size() == RULES.ELLIPSE_SEGMENTS, "эллипс тени задан %d точками" % RULES.ELLIPSE_SEGMENTS)
	_check(_rect_close(_bounds(ellipse), figure["shadow"]), "эллипс тени касается сторон своего прямоугольника")
	_check(not Geometry2D.is_point_in_polygon(Vector2(90.5, 197.5), ellipse), "угол прямоугольника тени лежит вне эллипса")
	_check(Geometry2D.is_point_in_polygon(Vector2(100.0, 200.5), ellipse), "центр тени лежит внутри эллипса")
	var rounded := RULES.rounded_rect_points(figure["body"], 2.0)
	_check(rounded.size() == 4 * (RULES.CORNER_SEGMENTS + 1), "тело: по четыре точки дуги на каждый угол")
	_check(_rect_close(_bounds(rounded), figure["body"]), "скруглённое тело занимает свой прямоугольник")
	_check(not Geometry2D.is_point_in_polygon(Vector2(95.2, 186.2), rounded), "угол тела срезан скруглением")
	_check(Geometry2D.is_point_in_polygon(Vector2(97.5, 186.2), rounded), "верхний край тела между дугами остаётся")


func _check_icon() -> void:
	var label := Rect2(100.0, 150.0, 40.0, 16.0)
	_check(RULES.icon_origin(label) == Vector2(64.0, 142.0),
		"иконка слева от подписи с зазором 4 px (32 + 4) и центром по высоте подписи, как map_travel.py:281-282")
	_check(RULES.icon_origin(Rect2(100.4, 150.0, 39.6, 16.0)) == Vector2(64.0, 142.0), "положение иконки округляется до целого пикселя")
	var geometry := RULES.icon_geometry(Vector2(64.0, 142.0))
	_check(geometry["head"] == Vector2(80.0, 151.0) and is_equal_approx(float(geometry["head_outline_radius"]), 5.0)
		and is_equal_approx(float(geometry["head_radius"]), 4.0), "голова иконки: круг r=5 с обводкой и r=4 в (16, 9), как IconCache._draw_procedural")
	_check(_rect_close(geometry["body_outline"], Rect2(71.0, 157.0, 17.0, 13.0)) and is_equal_approx(float(geometry["body_outline_radius"]), 4.0),
		"обводка тела (7, 15, 17, 13) со скруглением 4")
	_check(_rect_close(geometry["body"], Rect2(73.0, 158.0, 14.0, 12.0)) and is_equal_approx(float(geometry["body_radius"]), 3.0),
		"заливка тела (9, 16, 14, 12) со скруглением 3")
	_check(RULES.ICON_OUTLINE == Color8(40, 30, 25) and RULES.ICON_BODY == Color8(157, 177, 143), "цвета иконки как в IconCache._draw_procedural")


func _check_pick_box() -> void:
	var root := DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://"))
	var box: Rect2 = RULES.CITIZEN_PICK_BOX
	_check(box.has_point(Vector2.ZERO), "ноги горожанина попадают в прямоугольник выбора")
	var run := RULES.frames_by_direction(root)
	var idle := RULES.frames_from_folders("C:/нет/3run", root.path_join("2Idle"))
	var run_covered := true
	var idle_covered := true
	for direction in DECK_SPRITE.DIRECTIONS:
		run_covered = run_covered and box.encloses(_sprite_rect(run[direction][0]))
		idle_covered = idle_covered and box.encloses(_sprite_rect(idle[direction][0]))
	_check(run_covered, "прямоугольник выбора вмещает кадр бега каждого направления (до 74x90)")
	_check(idle_covered, "прямоугольник выбора вмещает кадр стойки каждого направления")
	var figure := RULES.figure_geometry(Vector2.ZERO)
	var head: Vector2 = figure["head"]
	var head_radius := float(figure["head_radius"])
	_check(box.encloses(Rect2(head - Vector2.ONE * head_radius, Vector2.ONE * head_radius * 2.0))
		and box.encloses(figure["shadow"]), "запасная фигурка тоже попадает в прямоугольник выбора")


func _check_map_draws() -> void:
	var routes: Array = _fixture("world_roads.json").get("terrain", {}).get("roads", {}).get("routes", [])
	var citizens: Array = _fixture("traveling_citizens.json").get("citizens", [])
	var map = TRAVEL_MAP_SCRIPT.new()
	map.custom_minimum_size = Vector2(900, 480)
	add_child(map)
	map.size = Vector2(900, 480)
	map.set_routes(routes)
	map.set_citizens(citizens)
	map.draw.connect(_count_draw)
	await get_tree().process_frame
	_check(map.citizen_frames().keys() == DECK_SPRITE.DIRECTIONS, "карта загружает кадры горожан из ../assets")

	var anya := _entry_named(map, "Аня")
	_check(not anya.is_empty(), "горожанин Аня попадает в записи карты")
	var feet: Vector2 = map.citizen_feet(anya)
	_check(str(map.entry_at_screen(feet + Vector2(0.0, -80.0)).get("name", "")) == "Аня",
		"выбор горожанина работает по голове спрайта, 80 px над ногами")
	_check(map.entry_at_screen(feet + Vector2(0.0, -110.0)).is_empty(), "выше спрайта горожанина выбора нет")
	_check(map.entry_at_screen(feet + Vector2(45.0, -40.0)).is_empty(), "правее спрайта горожанина выбора нет")

	var before := _draws
	for _frame in range(3):
		await get_tree().process_frame
	_check(_draws - before >= 3, "горожане на карте: перерисовка каждый кадр")

	map.visible = false
	await get_tree().process_frame
	before = _draws
	for _frame in range(3):
		await get_tree().process_frame
	_check(_draws == before, "скрытая карта не перерисовывается")

	map.visible = true
	map._assets_root = "C:/нет/assets"
	map._citizen_frames_loaded = false
	before = _draws
	for _frame in range(2):
		await get_tree().process_frame
	_check(map.citizen_frames().is_empty() and _draws > before, "без файлов карта рисует фигурку горожан и не падает")
	map.free()


func _count_draw() -> void:
	_draws += 1


func _entry_named(map, entry_name: String) -> Dictionary:
	for entry in map.entries():
		if str(entry.get("name", "")) == entry_name:
			return entry
	return {}


func _sprite_rect(frame: Texture2D) -> Rect2:
	return DECK_SPRITE.player_frame_rect(Vector2.ZERO, Vector2i(frame.get_size()))


func _same_size(frame: Texture2D, expected: Vector2) -> bool:
	return frame != null and frame.get_size() == expected


func _rect_close(a: Rect2, b: Rect2) -> bool:
	return a.position.is_equal_approx(b.position) and a.size.is_equal_approx(b.size)


func _bounds(points: PackedVector2Array) -> Rect2:
	var low := points[0]
	var high := points[0]
	for point in points:
		low = low.min(point)
		high = high.max(point)
	return Rect2(low, high - low)


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % file_name)
	return {}


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
