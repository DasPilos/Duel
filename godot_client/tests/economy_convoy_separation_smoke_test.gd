extends Node

# Раздвижка повозок, летящих рядом (ui/map_travel.py:128-165) и точка отрисовки display_position (map_travel.py:177-178, 250-251).
# Ожидания сняты с _separate_nearby_convoys из pygame 2.6.1 на тех же данных; сетевых вызовов и узлов карты нет.
const RULES := preload("res://scripts/economy_travel_rules.gd")
const TOLERANCE := 0.01

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_pair_and_lanes()
	_check_order_and_anchor()
	_check_distance_limit()
	_check_destination_and_cluster_shape()
	_check_directions()
	_check_tile_size_citizens_and_empty()
	_check_display_position()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_convoy_separation_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_pair_and_lanes() -> void:
	var pair := [_wagon(7, "lumber_camp", 100.0, 200.0, "e"), _wagon(8, "lumber_camp", 120.0, 200.0, "e")]
	RULES.separate_nearby_convoys(pair)
	_check(_near(_display(pair[0]), Vector2(100.0, 185.6)), "первая повозка пары уходит на полосу -14.4 px поперёк движения «восток»")
	_check(_near(_display(pair[1]), Vector2(120.0, 214.4)), "вторая повозка пары уходит на полосу +14.4 px")
	_check(_position(pair[0]) == Vector2(100.0, 200.0) and _position(pair[1]) == Vector2(120.0, 200.0),
		"позиция сервера не меняется, раздвигается только точка отрисовки")


func _check_order_and_anchor() -> void:
	var by_text := [_wagon(9, "farm", 100.0, 200.0, "e"), _wagon(10, "farm", 110.0, 200.0, "e")]
	RULES.separate_nearby_convoys(by_text)
	_check(_near(_display(by_text[1]), Vector2(110.0, 185.6)) and _near(_display(by_text[0]), Vector2(100.0, 214.4)),
		"полосы идут по строке id: «10» раньше «9», как в Python")
	var json_ids := [_wagon(9.0, "farm", 100.0, 200.0, "e"), _wagon(10.0, "farm", 110.0, 200.0, "e")]
	RULES.separate_nearby_convoys(json_ids)
	_check(_near(_display(json_ids[1]), Vector2(110.0, 185.6)) and _near(_display(json_ids[0]), Vector2(100.0, 214.4)),
		"id из JSON приходят float (9.0, 10.0), порядок полос тот же")
	var by_list := [_wagon(2, "lumber_camp", 0.0, 0.0, "e"), _wagon(1, "lumber_camp", 10.0, 0.0, "e")]
	RULES.separate_nearby_convoys(by_list)
	_check(_near(_display(by_list[1]), Vector2(10.0, -14.4)) and _near(_display(by_list[0]), Vector2(0.0, 14.4)),
		"полоса задаёт id, а не порядок списка; якорь — первая повозка списка")
	var three := [_wagon(1, "farm", 300.0, 300.0, "n"), _wagon(2, "farm", 310.0, 300.0, "n"), _wagon(3, "farm", 320.0, 300.0, "n")]
	RULES.separate_nearby_convoys(three)
	_check(_near(_display(three[0]), Vector2(271.2, 300.0)) and _near(_display(three[1]), Vector2(310.0, 300.0))
		and _near(_display(three[2]), Vector2(348.8, 300.0)), "три повозки ложатся на полосы -28.8, 0 и +28.8 px поперёк «севера»")


func _check_distance_limit() -> void:
	var exact := [_wagon(1, "lumber_camp", 0.0, 0.0, "s"), _wagon(2, "lumber_camp", 48.0, 0.0, "s")]
	RULES.separate_nearby_convoys(exact)
	_check(_near(_display(exact[0]), Vector2(14.4, 0.0)) and _near(_display(exact[1]), Vector2(33.6, 0.0)),
		"повозки ровно в 48 px (1.5 тайла) считаются рядом: граница включительна")
	var apart := [_wagon(1, "lumber_camp", 0.0, 0.0, "s"), _wagon(2, "lumber_camp", 48.5, 0.0, "s")]
	RULES.separate_nearby_convoys(apart)
	_check(not apart[0].has("display_position_x") and not apart[1].has("display_position_x"),
		"повозки дальше 48 px друг от друга не раздвигаются")


func _check_destination_and_cluster_shape() -> void:
	var other := [_wagon(1, "lumber_camp", 0.0, 0.0, "e"), _wagon(2, "farm", 10.0, 0.0, "e")]
	RULES.separate_nearby_convoys(other)
	_check(not other[0].has("display_position_x") and not other[1].has("display_position_x"),
		"повозки к разным строениям не раздвигаются, даже стоя рядом")
	var star := [_wagon(1, "farm", 0.0, 0.0, "e"), _wagon(2, "farm", 40.0, 0.0, "e"), _wagon(3, "farm", 80.0, 0.0, "e")]
	RULES.separate_nearby_convoys(star)
	_check(_near(_display(star[0]), Vector2(0.0, -14.4)) and _near(_display(star[1]), Vector2(40.0, 14.4)),
		"кластер строится от якоря: вторая повозка в 40 px от него входит в кластер")
	_check(not star[2].has("display_position_x"), "третья повозка дальше 48 px от якоря остаётся одна, хотя рядом со второй")


func _check_directions() -> void:
	var unknown := [_wagon(1, "farm", 0.0, 0.0, "up"), _wagon(2, "farm", 10.0, 0.0, "up")]
	RULES.separate_nearby_convoys(unknown)
	_check(_near(_display(unknown[0]), Vector2(14.4, 0.0)) and _near(_display(unknown[1]), Vector2(-4.4, 0.0)),
		"неизвестное направление считается «югом», как в Python: полосы по горизонтали")
	var diagonal := [_wagon(1, "farm", 0.0, 0.0, "ne"), _wagon(2, "farm", 10.0, 0.0, "ne")]
	RULES.separate_nearby_convoys(diagonal)
	_check(_near(_display(diagonal[0]), Vector2(-10.1808, -10.1808)) and _near(_display(diagonal[1]), Vector2(20.1808, 10.1808)),
		"диагональ «северо-восток» раздвигает по диагонали с множителем 0.707, как в Python")
	var anchor_only := [_wagon(1, "farm", 0.0, 0.0, "e"), _wagon(2, "farm", 10.0, 0.0, "n")]
	RULES.separate_nearby_convoys(anchor_only)
	_check(_near(_display(anchor_only[0]), Vector2(0.0, -14.4)) and _near(_display(anchor_only[1]), Vector2(10.0, 14.4)),
		"направление для всего кластера берётся у якоря, а не у соседа")


func _check_tile_size_citizens_and_empty() -> void:
	var small := [_wagon(1, "farm", 0.0, 0.0, "e"), _wagon(2, "farm", 20.0, 0.0, "e")]
	RULES.separate_nearby_convoys(small, 16)
	_check(_near(_display(small[0]), Vector2(0.0, -7.2)) and _near(_display(small[1]), Vector2(20.0, 7.2)),
		"при тайле 16 px радиус 24 px и шаг полос 14.4 px: масштаб тайла учитывается, как в Python")
	var citizen := {"entity_kind": "citizen", "id": 5, "destination_building_id": "farm",
		"position_x": 0.0, "position_y": 0.0, "position_direction": "e"}
	var mixed := [citizen, _wagon(1, "farm", 30.0, 0.0, "s"), _wagon(2, "farm", 30.0, 20.0, "s")]
	RULES.separate_nearby_convoys(mixed)
	_check(not citizen.has("display_position_x") and not citizen.has("display_position_y"), "горожанин в раздвижку не попадает")
	_check(_near(_display(mixed[1]), Vector2(44.4, 0.0)) and _near(_display(mixed[2]), Vector2(15.6, 20.0)),
		"повозки раздвигаются между собой, горожанин рядом их не трогает")
	var single := [_wagon(1, "farm", 0.0, 0.0, "e")]
	RULES.separate_nearby_convoys(single)
	_check(not single[0].has("display_position_x"), "одна повозка остаётся на месте")
	var empty: Array = []
	RULES.separate_nearby_convoys(empty)
	_check(empty.is_empty(), "пустой список повозок не падает")


func _check_display_position() -> void:
	var plain := _wagon(1, "farm", 30.0, 40.0, "e")
	_check(RULES.display_position(plain).is_equal_approx(Vector2(30.0, 40.0)), "без раздвижки точка отрисовки совпадает с позицией сервера")
	plain["display_position_x"] = 31.5
	plain["display_position_y"] = 44.0
	_check(RULES.display_position(plain).is_equal_approx(Vector2(31.5, 44.0)), "после раздвижки точка отрисовки берётся из display_position")


func _wagon(convoy_id: Variant, destination: String, x: float, y: float, direction: String) -> Dictionary:
	return {"entity_kind": "wagon", "id": convoy_id, "destination_building_id": destination,
		"position_x": x, "position_y": y, "position_direction": direction}


func _display(entry: Dictionary) -> Vector2:
	if not entry.has("display_position_x") or not entry.has("display_position_y"):
		return Vector2(INF, INF)
	return Vector2(float(entry["display_position_x"]), float(entry["display_position_y"]))


func _position(entry: Dictionary) -> Vector2:
	return Vector2(float(entry["position_x"]), float(entry["position_y"]))


func _near(point: Vector2, expected: Vector2) -> bool:
	return point.distance_to(expected) <= TOLERANCE


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
