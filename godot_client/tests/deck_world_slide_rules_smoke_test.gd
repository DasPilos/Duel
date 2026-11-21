extends Node

# Скольжение фигурки между плитками, камера карты (догон, зажим краями, порог перетаскивания, скролл клавишами) и тень
# лагеря лесника (deck/scenes/world_map_scene.py): скорость шага, дробное окно, окно данных с запасом, геометрия тени. Чистые правила, сцены нет.
const MAP_RULES := preload("res://scripts/deck_world_map_rules.gd")
const PLAYER_RULES := preload("res://scripts/deck_player_sprite_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_speed_and_centers()
	_check_slide()
	_check_window()
	_check_data_window_covers_slide()
	_check_camera_rules()
	_check_key_scroll_rules()
	_check_forester_look()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_world_slide_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_speed_and_centers() -> void:
	var step: float = PLAYER_RULES.WALK_STEP_SECONDS
	_check(is_equal_approx(step, 32.0 / 220.0), "тайл проходится за 32 / 220 с")
	_check(is_equal_approx(1.0 / step, 220.0 / 32.0), "фигурка идёт 6.875 тайла в секунду, как player_speed = 220 * tile / 32")
	_check(is_equal_approx(48.0 / (220.0 * 48.0 / 32.0), step), "при 48 px на тайл скорость 330 px/с, как в Python")
	_check(MAP_RULES.tile_center(Vector2i(12, 36)) == Vector2(12.5, 36.5), "центр плитки лежит в середине тайла")
	_check(MAP_RULES.view_origin(Vector2(12.5, 36.5), 11) == Vector2(7.0, 31.0), "окно 11x11 центрировано на фигурке")


func _check_slide() -> void:
	var from := Vector2(12.5, 36.5)
	var to := Vector2(13.5, 36.5)
	_check(MAP_RULES.slide_toward(from, to, 0.5) == Vector2(13.0, 36.5), "за полшага фигурка проходит половину тайла")
	_check(MAP_RULES.slide_toward(from, to, 1.0) == to, "на целый шаг фигурка встаёт в цель точно")
	_check(MAP_RULES.slide_toward(from, to, 3.0) == to, "большой шаг не перелетает цель")
	_check(MAP_RULES.slide_toward(to, to, 0.5) == to, "у цели фигурка стоит")
	_check(MAP_RULES.slide_toward(from, to, -1.0) == from, "отрицательный шаг не двигает фигурку")
	var diagonal := MAP_RULES.slide_toward(Vector2(0.0, 0.0), Vector2(3.0, 4.0), 2.5)
	_check(diagonal.is_equal_approx(Vector2(1.5, 2.0)), "по диагонали фигурка идёт по прямой")
	var position := from
	for frame in 50:
		position = MAP_RULES.slide_toward(position, to, 1.0 / 50.0)
	_check(position.is_equal_approx(to), "за время шага фигурка приходит в цель")


func _check_window() -> void:
	var origin := Vector2(7.0, 31.0)
	_check(MAP_RULES.world_to_view(Vector2(12.5 * 48.0, 36.5 * 48.0), origin, 48.0) == Vector2(264.0, 264.0), "фигурка на плитке окна стоит по центру")
	_check(MAP_RULES.world_to_view(Vector2(13.5 * 48.0, 36.5 * 48.0), origin, 48.0) == Vector2(312.0, 264.0), "соседняя плитка правее центра окна на 48 px")


func _check_data_window_covers_slide() -> void:
	_check(MAP_RULES.data_window(Vector2i(12, 36), Vector2(12.5, 36.5), 11) == Rect2i(6, 30, 13, 13), "в покое окно данных — окно 11x11 с запасом в плитку")
	_check(MAP_RULES.data_window(Vector2i(13, 36), Vector2(13.0, 36.5), 11) == Rect2i(6, 30, 14, 13), "на полпути вправо окно данных охватывает старое и новое окно")
	var east := _covered_on_slide(Vector2i(13, 36), Vector2(12.5, 36.5), Vector2(13.5, 36.5))
	_check(east, "при шаге вправо каждый кадр скольжения виден внутри окна данных")
	var west := _covered_on_slide(Vector2i(11, 36), Vector2(12.5, 36.5), Vector2(11.5, 36.5))
	_check(west, "при шаге влево каждый кадр скольжения виден внутри окна данных")
	var south := _covered_on_slide(Vector2i(12, 37), Vector2(12.5, 36.5), Vector2(12.5, 37.5))
	_check(south, "при шаге вниз каждый кадр скольжения виден внутри окна данных")


# Окно данных строится в начале шага; все кадры от старой точки скольжения до цели должны попадать в него.
func _covered_on_slide(logical: Vector2i, from: Vector2, to: Vector2) -> bool:
	var window := MAP_RULES.data_window(logical, from, 11)
	for index in range(51):
		var center := from.lerp(to, index / 50.0)
		var origin := MAP_RULES.view_origin(center, 11)
		var first := Vector2i(int(floor(origin.x)), int(floor(origin.y)))
		var last := first + Vector2i.ONE * 11
		if first.x < window.position.x or first.y < window.position.y or last.x >= window.end.x or last.y >= window.end.y:
			return false
	return true


# Догон камеры min(1, 8·dt), зажим краями карты, порог перетаскивания и покрытие окна данных окном камеры.
func _check_camera_rules() -> void:
	var origin := Vector2.ZERO
	var target := Vector2(10.0, 0.0)
	_check(MAP_RULES.follow_camera(origin, target, 0.1).is_equal_approx(Vector2(8.0, 0.0)), "за 0.1 с камера проходит 8·dt = 0.8 разницы")
	_check(MAP_RULES.follow_camera(origin, target, 0.2) == target, "при dt от 1/8 с камера встаёт на фигурку сразу")
	_check(MAP_RULES.follow_camera(target, target, 0.1) == target, "стоящая на фигурке камера не двигается")
	_check(MAP_RULES.follow_camera(origin, target, -1.0) == origin, "отрицательный шаг не двигает камеру")
	_check(MAP_RULES.follow_camera(origin, target, 1.0 / 60.0).is_equal_approx(Vector2(10.0 * 8.0 / 60.0, 0.0)), "при 60 fps за кадр камера проходит 8/60 разницы")
	var map_size := Vector2(128.0, 256.0)
	_check(MAP_RULES.clamp_camera(Vector2.ZERO, Vector2.ZERO, map_size, 11) == Vector2(5.5, 5.5), "угол карты прижимает окно к (5.5, 5.5): половина окна 5.5 тайла")
	_check(MAP_RULES.clamp_camera(Vector2(200.0, 300.0), Vector2.ZERO, map_size, 11) == Vector2(122.5, 250.5), "дальний угол прижимает к (128 - 5.5, 256 - 5.5)")
	_check(MAP_RULES.clamp_camera(Vector2(-3.0, 128.0), Vector2.ZERO, map_size, 11) == Vector2(5.5, 128.0), "зажимается только тот край, за который вышли")
	_check(MAP_RULES.clamp_camera(Vector2(60.0, 100.0), Vector2.ZERO, map_size, 11) == Vector2(60.0, 100.0), "внутри карты камера не меняется")
	_check(not MAP_RULES.drag_passed(Vector2(4.0, -4.0)) and MAP_RULES.drag_passed(Vector2(5.0, 0.0)), "перетаскивание начинается дальше 4 px, как в Python")
	_check(MAP_RULES.covers_view(MAP_RULES.data_window(Vector2i(13, 36), Vector2(13.5, 36.5), 11), Vector2(13.5, 36.5), 11), "окно данных покрывает окно камеры")
	_check(MAP_RULES.covers_view(Rect2i(6, 30, 13, 13), Vector2(12.5, 36.5), 11), "в покое окно 13x13 покрывает окно камеры")
	_check(not MAP_RULES.covers_view(Rect2i(6, 30, 13, 13), Vector2(13.5, 36.5), 11), "камера правее окна данных требует перестройки")
	_check(MAP_RULES.data_window(Vector2i(12, 36), Vector2(60.5, 36.5), 11) == Rect2i(54, 30, 13, 13), "далеко ушедшая камера не тянет окно фигурки: данные только вокруг камеры")


# Скролл клавишами как блок «Скролл карты стрелками / WASD» в Python: 850 px/с на тайл 48 px, Shift в 2.2 раза быстрее.
# S не скроллит в режиме карт, стрелка вниз скроллит всегда, противоположные клавиши дают moved без смещения.
func _check_key_scroll_rules() -> void:
	var step := 850.0 * 0.1 / 48.0
	var up := _scroll({"up": true})
	_check(_offset(up).is_equal_approx(Vector2(0.0, -step)) and up["moved"], "W сдвигает камеру вверх на 850 px/с")
	_check(_offset(_scroll({"left": true})).is_equal_approx(Vector2(-step, 0.0)), "A и ← сдвигают камеру влево")
	_check(_offset(_scroll({"right": true})).is_equal_approx(Vector2(step, 0.0)), "D и → сдвигают камеру вправо")
	_check(_offset(_scroll({"down": true})).is_equal_approx(Vector2(0.0, step)), "↓ сдвигает камеру вниз")
	_check(_offset(_scroll({"s": true})).is_equal_approx(Vector2(0.0, step)), "S сдвигает камеру вниз вне режима карт")
	var cards := _scroll({"s": true}, true)
	_check(_offset(cards) == Vector2.ZERO and not cards["moved"], "S не скроллит в режиме карт")
	var cards_down := _scroll({"s": true, "down": true}, true)
	_check(_offset(cards_down).is_equal_approx(Vector2(0.0, step)) and cards_down["moved"], "↓ скроллит и в режиме карт, как в Python")
	_check(_offset(_scroll({"up": true, "shift": true})).is_equal_approx(Vector2(0.0, -step * 2.2)), "Shift ускоряет скролл в 2.2 раза")
	var opposite := _scroll({"left": true, "right": true})
	_check(_offset(opposite) == Vector2.ZERO, "противоположные клавиши не смещают камеру")
	_check(opposite["moved"], "противоположные клавиши всё равно отключают догон")
	var none := _scroll({})
	_check(_offset(none) == Vector2.ZERO and not none["moved"], "без клавиш камера не двигается")
	_check(_offset(MAP_RULES.key_scroll({"up": true}, 0.0, 48.0, false)) == Vector2.ZERO, "при нулевом кадре скролла нет")


func _scroll(held: Dictionary, s_cancels := false) -> Dictionary:
	return MAP_RULES.key_scroll(held, 0.1, 48.0, s_cancels)


func _offset(scroll: Dictionary) -> Vector2:
	return scroll["offset"]


func _check_forester_look() -> void:
	var rect := Rect2(0.0, 0.0, 480.0, 480.0)
	_check(PLAYER_RULES.forester_shadow_ellipse(rect, 48.0) == Rect2(20.0, 180.0, 440.0, 120.0), "тень как pygame.draw.ellipse(sx + 20, sy + 180, obj_w - 40, 120)")
	_check(PLAYER_RULES.forester_shadow_ellipse(Rect2(0.0, 0.0, 960.0, 960.0), 96.0) == Rect2(40.0, 360.0, 880.0, 240.0), "тень масштабируется вместе с плиткой")
	var shadow: Color = PLAYER_RULES.FORESTER_SHADOW_COLOR
	_check(is_equal_approx(shadow.a, 1.0) and shadow.is_equal_approx(Color(16 / 255.0, 24 / 255.0, 16 / 255.0, 1.0)), "тень непрозрачная, цвет (16, 24, 16), как у pygame без альфа-канала")
	_check(PLAYER_RULES.FORESTER_HOVER_COLOR.is_equal_approx(Color(80 / 255.0, 200 / 255.0, 255 / 255.0)), "рамка наведения (80, 200, 255), как в world_map_scene.py")
	_check(PLAYER_RULES.FORESTER_HOVER_BADGE_COLOR.is_equal_approx(Color(100 / 255.0, 200 / 255.0, 255 / 255.0)), "подпись наведения (100, 200, 255)")
