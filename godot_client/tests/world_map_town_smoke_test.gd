extends Node

# Город Радбург на карте Экономики: объект и стены из terrain.objects, подпись, наведение, ворота и коллизия.
# Проверяются правила, коллизия и отрисовка вида без world_entry.gd; карта Башни здесь не участвует.

const RULES := preload("res://scripts/world_map_town_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/world_map_town_view.gd")
const COLLISION_SCRIPT := preload("res://scripts/world_collision.gd")
const GATE_RULES := preload("res://scripts/economy_gate_rules.gd")
const KEEP_ASSET := "fighters/equipment/placeholders/building_town_radburg.png"
const FARM_HOUSE_ASSET := "town/farm/house.png"
const LUMBER_HOUSE_ASSET := "town/lumber_camp/house.png"
# town_radburg из server/structures.py: solid_rects в мировых пикселях.
const TOWN := {
	"id": "town_radburg", "tile_x": 120, "tile_y": 92, "tile_w": 30, "tile_h": 30,
	"name": "Город Радбург", "type": "Город Света (15х15)",
	"desc": "Радбург — священный Город Света. Размер 15х15 тайлов (X: 60..74, Y: 46..60). 4 ворот: Главные (восток), Южные, Северные, Западные.",
	"entrances": [
		{"id": "east", "tiles": [[148, 104], [148, 106], [148, 108]], "approach_pos": [2416, 1712]},
		{"id": "south", "tiles": [[134, 120]], "approach_pos": [2160, 1968]},
		{"id": "north", "tiles": [[134, 92]], "approach_pos": [2160, 1456]},
		{"id": "west", "tiles": [[120, 106]], "approach_pos": [1904, 1712]},
	],
	"solid_rects": [
		[1984, 1536, 352, 352], [1920, 1472, 224, 32], [2176, 1472, 224, 32], [1920, 1920, 224, 32], [2176, 1920, 224, 32],
		[1920, 1472, 32, 224], [1920, 1728, 32, 224], [2368, 1472, 32, 192], [2368, 1760, 32, 192],
	],
}
const LUMBER_CAMP := {"id": "lumber_camp", "tile_x": 20, "tile_y": 20, "tile_w": 20, "tile_h": 20, "solid_rects": [[320, 320, 320, 320]]}
const TERRAIN := {"map": {"tiles_w": 1024, "tiles_h": 512}, "tiles": {}, "props": [], "obstacles": []}
const DRAW_STATES := [
	{"city_level": 1, "active": false},
	{"city_level": 1, "active": true, "phase_index": 0},
	{"city_level": 1, "active": true, "phase_index": 3},
	{"city_level": 2},
	{"city_level": 2, "active": true, "phase_index": 1},
	{"city_level": 3},
]

var _failures: Array[String] = []
var _checks := 0
var _view
var _canvas: Control
var _drawn := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_objects_and_hover()
	_check_wall_plan()
	_check_exterior_geometry()
	_check_collision()
	_check_window_rules()
	await _check_draw()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_map_town_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_objects_and_hover() -> void:
	_check(RULES.town_objects([LUMBER_CAMP, TOWN]).size() == 1, "из terrain.objects берётся только town_radburg")
	_check(RULES.town_objects([LUMBER_CAMP]).is_empty(), "без города ничего не рисуется")
	_check(RULES.object_rect(TOWN) == Rect2(1920, 1472, 480, 480), "город занимает 30×30 тайлов от (120, 92)")
	var hover := RULES.hover_rect(TOWN)
	_check(hover == Rect2(1920, 1450, 480, 502), "наведение поднимается на 22 px, как _find_entity_at")
	_check(hover.has_point(Vector2(2100, 1460)) and not hover.has_point(Vector2(2100, 1440)), "над верхним краем наведение только в пределах 22 px")
	_check(RULES.badge_text(1) == "Город Радбург · ур. 1", "подпись города как в Python")
	_check(RULES.badge_text(4) == "Город Радбург · ур. 4", "подпись берёт уровень города")
	_check(RULES.solid_rects([LUMBER_CAMP]).is_empty(), "нерисуемые здания не получают коллизию")
	var solid := RULES.solid_rects([TOWN])
	_check(solid.size() == 9 and solid[0] == [1984, 1536, 352, 352], "коллизия города — девять прямоугольников из terrain.objects")


func _check_wall_plan() -> void:
	_check(RULES.tier(1) == 1 and RULES.tier(2) == 2 and RULES.tier(4) == 2, "ярус стен 1 или 2, как city_visual_tier")
	_check(RULES.city_level({}) == 1 and RULES.city_level({"city_level": 3}) == 3, "уровень города по умолчанию 1")
	var trench: Dictionary = RULES.wall_plan({"city_level": 1, "active": true, "phase_index": 0})
	_check(trench["kind"] == "level1" and bool(trench["trench"]) and (trench["work_sides"] as Array).is_empty(), "первая фаза работ: траншея без брёвен")
	var phase_two: Dictionary = RULES.wall_plan({"city_level": 1, "active": true, "phase_index": 2})
	_check(phase_two["completed"] == [1, 2] and phase_two["work_sides"] == [0, 3] and not bool(phase_two["trench"]), "вторая фаза: готовы стороны 1 и 2, брёвна на 0 и 3")
	var phase_three: Dictionary = RULES.wall_plan({"city_level": 1, "active": true, "phase_index": 3})
	_check(phase_three["completed"] == [1, 2, 3] and phase_three["work_sides"] == [0], "третья фаза: готовы стороны 1–3, брёвна на 0")
	_check(RULES.wall_plan({"city_level": 2})["kind"] == "completed", "второй уровень без работ: деревянный забор")
	var upgrade: Dictionary = RULES.wall_plan({"city_level": 2, "active": true, "phase_index": 1})
	_check(upgrade["kind"] == "upgrade" and upgrade["stages"] == ["stone", "building", "wood", "wood"], "улучшение 2→3: камень, строящаяся сторона, дерево")
	_check(RULES.wall_plan({"city_level": 3})["kind"] == "stone", "третий уровень и выше: каменная стена")


func _check_exterior_geometry() -> void:
	var rect := RULES.object_rect(TOWN)
	var unit := RULES.scale_for(rect)
	var inset := RULES.inset_for(unit)
	var bounds := RULES.bounds_for(rect, inset)
	_check(is_equal_approx(unit, 1.0) and inset == 12 and bounds == Rect2(1932, 1484, 456, 456), "внутренняя область отступает на 12 px, как в draw_city_exterior")
	_check(RULES.gate_rects(bounds, unit) == [Rect2(2136, 1483, 48, 24), Rect2(2136, 1917, 48, 24), Rect2(1931, 1688, 24, 48), Rect2(2365, 1688, 24, 48)], "ворота на север, юг, запад и восток")
	_check(RULES.tower_rects(bounds, unit) == [Rect2(1932, 1484, 72, 72), Rect2(2316, 1484, 72, 72), Rect2(1932, 1868, 72, 72), Rect2(2316, 1868, 72, 72)], "четыре угловые башни")
	var farm := RULES.house_rects(bounds, 1, unit)
	_check(farm.size() == 4 and farm[0] == Rect2(1989, 1541, 42, 42), "первый ярус: четыре дома, первый в (1989, 1541)")
	_check(RULES.house_rects(bounds, 2, unit).size() == 7, "второй ярус: семь домов")
	_check(RULES.keep_rect(bounds) == Rect2(2074, 1626, 173, 173), "донжон по центру, 38% от стороны")


func _check_collision() -> void:
	var collision = COLLISION_SCRIPT.new()
	collision.configure(TERRAIN)
	_check(not collision.terrain_blocked(2160.0, 1712.0), "без solid_rects центр свободен (как на карте Башни)")
	collision.set_solid_rects(RULES.solid_rects([TOWN]))
	_check(collision.terrain_blocked(2160.0, 1712.0), "донжон в центре блокирует ход")
	_check(not collision.terrain_blocked(2380.0, 1712.0), "восточные ворота проходимы между стенами")
	_check(not collision.terrain_blocked(2160.0, 1500.0), "северные ворота проходимы между стенами")
	for gate_id in ["main", "north", "south", "west"]:
		var spawn: Vector2 = GATE_RULES.map_spawn(gate_id)["position"]
		_check(not collision.terrain_blocked(spawn.x, spawn.y), "точка входа %s свободна" % gate_id)
	collision.set_solid_rects([])
	_check(not collision.terrain_blocked(2160.0, 1712.0), "сброс solid_rects возвращает свободный ход")


func _check_window_rules() -> void:
	var window := RULES.window_rect(Vector2(1280.0, 720.0), 2.0 / 3.0)
	_check(is_equal_approx(window.end.x, 1280.0 - 25.0 * 2.0 / 3.0) and is_equal_approx(window.end.y, 720.0 - 40.0 * 2.0 / 3.0), "окно прижато к правому нижнему углу с отступами Python")
	_check(is_equal_approx(window.size.x, 365.0 * 2.0 / 3.0) and is_equal_approx(window.size.y, 215.0 * 2.0 / 3.0), "размер окна 365×215 px Python")
	var layout := RULES.window_layout(window, 2.0 / 3.0)
	_check(window.encloses(layout["close"]) and window.encloses(layout["action"]), "крестик и кнопка лежат внутри окна")
	_check(RULES.within_one_tile(TOWN, Vector2i(150, 106)) and RULES.within_one_tile(TOWN, Vector2i(146, 106)), "рядом с восточными воротами кнопка активна")
	_check(not RULES.within_one_tile(TOWN, Vector2i(144, 106)) and not RULES.within_one_tile(TOWN, Vector2i(130, 90)), "дальше двух клеток от ворот кнопка неактивна")
	_check(RULES.within_one_tile(TOWN, Vector2i(132, 90)), "диагональ к северным воротам засчитывается, как в Python")
	_check(RULES.nearest_gate(TOWN, Vector2(2416.0, 1712.0)) == "east" and RULES.nearest_gate(TOWN, Vector2(2160.0, 1456.0)) == "north", "ближайшие ворота выбираются по точке входа")
	_check(RULES.nearest_gate(TOWN, Vector2(2160.0, 1968.0)) == "south" and RULES.nearest_gate(TOWN, Vector2(1904.0, 1712.0)) == "west", "юг и запад выбираются по точке входа")
	_check(RULES.nearest_gate({}, Vector2.ZERO) == "east", "без входов по умолчанию восток")
	_check(RULES.description_lines(str(TOWN["desc"])).size() == 2 and RULES.description_lines("Коротко").size() == 1, "описание: две строки по 42 символа, короткое — одна строка")
	var choices: Array = RULES.too_far_choices("Слишком далеко")
	_check(choices.size() == 9 and not choices.has("Слишком далеко") and RULES.too_far_choices("").size() == 10, "фраза отказа не повторяет предыдущую")
	_check(RULES.range_text(true) != RULES.range_text(false) and RULES.type_text(TOWN) == "Тип: Город Света (15х15)", "текст радиуса и типа как в окне Python")


func _check_draw() -> void:
	_view = VIEW_SCRIPT.new()
	_check(_view._texture(KEEP_ASSET) != null, "донжон Радбурга читается из assets")
	_check(_view._texture(FARM_HOUSE_ASSET) != null and _view._texture(LUMBER_HOUSE_ASSET) != null, "дома первого и второго яруса читаются из assets")
	_canvas = Control.new()
	_canvas.size = Vector2(1280.0, 720.0)
	add_child(_canvas)
	_canvas.draw.connect(_on_canvas_draw)
	_canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_drawn > 0, "город со всеми ветками стен, подписью и окном рисуется без ошибок")
	remove_child(_canvas)
	_canvas.free()


func _on_canvas_draw() -> void:
	var rect := Rect2(40.0, 40.0, 480.0, 480.0)
	for state in DRAW_STATES:
		_view.draw_town(_canvas, rect, state, true)
	_view.draw_town(_canvas, rect, DRAW_STATES[1], false, true)
	_view.draw_badge(_canvas, Vector2(280.0, 30.0), RULES.badge_text(2), RULES.BADGE_ACTIVE, 2.0 / 3.0)
	var layout := RULES.window_layout(RULES.window_rect(_canvas.size, 2.0 / 3.0), 2.0 / 3.0)
	_view.draw_window(_canvas, layout, TOWN, true, "", Vector2.ZERO, 2.0 / 3.0)
	_view.draw_window(_canvas, layout, TOWN, false, "Слишком далеко", (layout["close"] as Rect2).get_center(), 2.0 / 3.0)
	_drawn += 1


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
