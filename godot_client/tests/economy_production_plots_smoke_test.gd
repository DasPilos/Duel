extends Node

# Холст участков (economy_production_plots_view.gd) и геометрия (economy_production_plot_geometry.gd) без сети:
# участки по зданиям, клик попадает в свой полигон, текстуры и домики есть в ../assets, все виды рисуются
# без ошибок на разных уровнях и стадиях, подсказка и надпись закрытого участка как в Python.
const CANVAS_SCRIPT := preload("res://scripts/economy_production_plots_view.gd")
const GEO := preload("res://scripts/economy_production_plot_geometry.gd")
const RULES := preload("res://scripts/economy_production_rules.gd")

# Подкласс холста считает вызовы _draw: без этого отрисовку в headless-режиме нельзя было бы проверить.
class CountingCanvas extends "res://scripts/economy_production_plots_view.gd":
	var draws := 0

	func _draw() -> void:
		draws += 1
		super._draw()


const PLOT_COUNTS := {"farm": 12, "lumber_camp": 12, "mountain_rift": 4, "barnyard": 1, "black_pit": 10}
const SHAPES := {"farm": "fields", "lumber_camp": "pie", "mountain_rift": "rift", "barnyard": "pen", "black_pit": "digs"}
const CANVAS_SIZE := Vector2(900.0, 340.0)

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_geometry()
	_check_groups_and_names()
	_check_assets()
	await _check_drawing()
	_check_hints_and_captions()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_production_plots_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _area() -> Rect2:
	return Rect2(Vector2(6.0, 6.0), CANVAS_SIZE - Vector2(12.0, 12.0))


func _check_geometry() -> void:
	for building in PLOT_COUNTS:
		var plots: Array = GEO.build(SHAPES[building], _area(), RULES.plot_groups(building), 25)
		_check(plots.size() == PLOT_COUNTS[building], "%s: полигонов столько же, сколько участков" % building)
		var centered := true
		for plot in plots:
			centered = centered and plot["points"].size() >= 4 and Geometry2D.is_point_in_polygon(plot["center"], plot["points"])
		_check(centered, "%s: центр каждого участка лежит внутри полигона" % building)
	var rift := GEO.build("rift", _area(), RULES.plot_groups("mountain_rift"), 25)
	_check(rift[0].has("tent"), "палатка разлома задана")
	_check(GEO.rift_backdrop(_area().size).size() > 100, "фон разлома строится из команд рисования")
	_check(RULES.plot_slots(_state("farm", 1, 0), "farm", 5) == null, "закрытый участок без мест в состоянии")


func _check_groups_and_names() -> void:
	var rift := RULES.plot_groups("mountain_rift")
	_check(rift.size() == 4 and int(rift[0]["places"]) == 7 and int(rift[1]["places"]) == 10 and int(rift[3]["level"]) == 10,
		"разлом: четыре прииска, места складываются по видам")
	_check(RULES.plot_name("mountain_rift", rift[1]) == "Прииск железа", "название прииска железа")
	var pen := RULES.plot_groups("barnyard")
	_check(pen.size() == 1 and int(pen[0]["places"]) == 25 and pen[0]["resources"] == ["leather", "meat"],
		"загон: один участок на 25 мест")
	_check(RULES.plot_name("farm", RULES.plot_groups("farm")[0]) == "Поле (пшеница)", "название поля с ресурсом")
	_check(RULES.plot_name("lumber_camp", RULES.plot_groups("lumber_camp")[4]) == "Опушка (ягоды)", "название опушки")
	_check(RULES.plot_name("black_pit", RULES.plot_groups("black_pit")[0]) == "Копанка (уголь)", "название копанки")


func _check_assets() -> void:
	var textures := {"farm": ["wheat", "flax", "cotton"], "lumber_camp": ["wood", "berries"]}
	for building in textures:
		var asset_dir := "farm" if building == "farm" else "lumber_camp"
		for resource in textures[building]:
			for stage in range(4):
				var path: String = CANVAS_SCRIPT.asset_path(asset_dir, RULES.texture_file(resource, stage))
				_check(FileAccess.file_exists(path), "есть текстура %s" % path.get_file())
		_check(FileAccess.file_exists(CANVAS_SCRIPT.asset_path(asset_dir, "house.png")), "есть домик для %s" % building)


func _check_drawing() -> void:
	for building in PLOT_COUNTS:
		for level_stage in [[1, 0], [10, 3]]:
			var canvas = CountingCanvas.new()
			canvas.set_building(building)
			canvas.set_state(_state(building, level_stage[0], level_stage[1]), 42)
			canvas.size = CANVAS_SIZE
			add_child(canvas)
			await get_tree().process_frame
			await get_tree().process_frame
			var label := "%s, уровень %d" % [building, level_stage[0]]
			_check(canvas.draws > 0, "%s: отрисовка выполнена без ошибок" % label)
			_check(canvas.plot_count() == PLOT_COUNTS[building], "%s: холст рисует все участки" % label)
			var geometry: Array = canvas.plot_geometry()
			var hits := true
			for index in range(geometry.size()):
				hits = hits and canvas.plot_at(geometry[index]["center"]) == index
			_check(hits, "%s: клик в центре участка попадает в свой участок" % label)
			remove_child(canvas)
			canvas.free()


func _check_hints_and_captions() -> void:
	var canvas = CANVAS_SCRIPT.new()
	canvas.set_building("farm")
	canvas.set_state({"building": "farm", "level": 1, "stage": 0, "worker_slots": [
		{"slot_index": 0, "occupied": false, "resources": ["wheat"]},
		{"slot_index": 1, "occupied": false, "resources": ["wheat"]},
	]}, 42)
	canvas.size = CANVAS_SIZE
	add_child(canvas)
	var first_center: Vector2 = canvas.plot_geometry()[0]["center"]
	_check(canvas._get_tooltip(first_center) == "Поле (пшеница): работников 0 / 2. Клик — встать на добычу",
		"подсказка свободного поля как в Python")
	_check(canvas._get_tooltip(Vector2(-50.0, -50.0)) == "", "вне участков подсказки нет")
	remove_child(canvas)
	canvas.free()
	_check(RULES.plot_lock_caption("farm", 1) == "Пшеница · ур. 2", "надпись закрытого поля: ресурс и уровень")
	_check(RULES.plot_lock_caption("black_pit", 1) == "Копанка · ур. 2", "надпись закрытой копанки")
	_check(RULES.plot_lock_caption("mountain_rift", 1) == "Прииск железа · ур. 2", "надпись закрытого прииска")


# Состояние здания с местами всех открытых к уровню участков: занятые — каждое чётное место.
func _state(building: String, level: int, stage: int) -> Dictionary:
	var slots: Array = []
	for group in RULES.plot_groups(building):
		if int(group["level"]) > level:
			continue
		for slot_index in group["slots"]:
			var occupied: bool = int(slot_index) % 2 == 0
			slots.append({
				"slot_index": slot_index,
				"occupied": occupied,
				"worker_id": "citizen:%d" % int(slot_index) if occupied else null,
				"worker_name": "Горожанин",
				"is_player": false,
				"is_travelling": false,
				"resource": group["resource"],
				"resources": group["resources"],
				"timer_sec_by_resource": {},
				"resource_progress_sec": {},
				"progress_sec": 0,
			})
	return {
		"building": building,
		"level": level,
		"stage": stage,
		"worker_slots": slots,
		"storage": {"limit": 500},
		"farm_upgrades": {"ration_plots": [], "extra_places": {}},
		"lumber_camp_upgrades": {"bonus_plots": []},
	}
