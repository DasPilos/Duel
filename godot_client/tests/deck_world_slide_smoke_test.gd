extends Node

# Скольжение фигурки и камера карты Колоды в сцене: окно и плитки идут по дробным тайлам, камера догоняет фигурку,
# зажата краями мира и отпускается перетаскиванием или клавишами; телепорт, Space и «К герою» центрируют сразу.
# Окна, закрывающие карту, отключают наведение на лагерь (как hovered_entity).
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const MAP_RULES := preload("res://scripts/deck_world_map_rules.gd")
const PLAYER_RULES := preload("res://scripts/deck_player_sprite_rules.gd")
const FIXTURES := preload("res://tests/deck_world_map_fixtures.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_renderer_window()
	await _check_forester()
	await _check_world_slide()
	await _check_camera_follow()
	await _check_edge_clamp()
	await _check_drag_refresh()
	await _check_published_blocking()
	await _check_key_scroll()
	await _check_space_center()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_world_slide_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


# Окно 11x11 с дробным сдвигом: плитки, маркер и поиск плитки под курсором используют один и тот же сдвиг.
func _check_renderer_window() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	renderer.configure({
		"terrain": FIXTURES.procedural_terrain(),
		"center": Vector2i(12, 36),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
		"markers": {Vector2i(7, 31): {"symbol": "T", "color": Color.WHITE, "alpha": 1.0}},
		"data_window": Rect2i(6, 30, 13, 13),
	})
	var button: Button = renderer.get("_marker_buttons")[Vector2i(7, 31)]
	_check(button.position == Vector2(3.0, 3.0), "в покое маркер стоит на своей плитке")
	renderer.set_view_center(Vector2(12.7, 36.5))
	_check(renderer.get("_origin") == Vector2i(7, 31) and is_equal_approx(renderer.get("_view_shift").x, 0.2), "окно сдвигается на дробную часть тайла")
	_check(renderer.tile_at(Vector2(24.0, 24.0)) == Vector2i(7, 31), "под курсором первая плитка окна при сдвиге")
	_check(renderer.tile_at(Vector2(40.0, 24.0)) == Vector2i(8, 31), "сдвиг учитывается при поиске плитки под курсором")
	_check(renderer.tile_at(Vector2(529.0, 10.0)) == MAP_RULES.NO_TILE, "точка правее окна не попадает в плитку и при сдвиге")
	_check(is_equal_approx(button.position.x, 3.0 - 0.2 * 48.0), "маркер едет вместе с плитками")
	renderer.set_view_center(Vector2(12.5, 36.5))
	_check(button.position == Vector2(3.0, 3.0), "маркер возвращается на место, когда окно встало на плитку")
	renderer.set_figure(Vector2(12.2, 36.5))
	var feet: Vector2 = renderer.get("_sprites").animation_state()["feet"]
	_check(feet.is_equal_approx(Vector2(249.6, 264.0)), "ноги фигурки считаются от окна: сдвиг по x берётся из окна, а не из центра")
	renderer.queue_free()
	await get_tree().process_frame


# Лагерь лесника едет с окном, отбрасывает тень и подсвечивается при наведении, пока окна не закрывают карту.
func _check_forester() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	renderer.configure({
		"terrain": {"objects": [{"id": "lumber_camp", "name": "Лагерь", "tile_x": 41, "tile_y": 83, "tile_w": 10, "tile_h": 10, "rotation": 0}]},
		"center": Vector2i(46, 88),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
	})
	var layer = renderer.get("_sprites")
	_check(layer.animation_state()["forester_rect"] == Rect2(0.0, 0.0, 480.0, 480.0), "в покое лагерь лесника 10x10 плиток стоит в углу окна")
	renderer.set_view_center(Vector2(46.7, 88.5))
	var state: Dictionary = layer.animation_state()
	var rect: Rect2 = state["forester_rect"]
	_check(is_equal_approx(rect.position.x, -9.6) and rect.position.y == 0.0, "при сдвиге окна лагерь лесника едет вместе с плитками")
	_check(state["forester_shadow_rect"] == PLAYER_RULES.forester_shadow_ellipse(rect, 48.0), "тень лагеря считается по его прямоугольнику")
	_check(not state["forester_hovered"], "без указателя лагерь не подсвечен")
	renderer.update_pointer(Vector2(100.0, 100.0), false)
	_check(layer.animation_state()["forester_hovered"], "указатель над лагерем подсвечивает его")
	renderer.update_pointer(Vector2(100.0, 100.0), true)
	_check(not layer.animation_state()["forester_hovered"], "окно поверх карты отключает подсветку лагеря")
	renderer.update_pointer(Vector2(-200.0, -200.0), false)
	_check(not layer.animation_state()["forester_hovered"], "указатель мимо лагеря его не подсвечивает")
	renderer.queue_free()
	await get_tree().process_frame


# Шаг на соседнюю плитку: фигурка скользит за 32 / 220 с, камера догоняет её на min(1, 8·dt); телепорт ставит всё сразу.
func _check_world_slide() -> void:
	var deck = await _make_deck()
	deck._map_position = Vector2i(12, 36)
	deck._render_location()
	_check(deck._world_map.get("_origin") == Vector2i(7, 31) and deck._world_map.get("_view_shift") == Vector2.ZERO, "в покое окно стоит на целых плитках")
	deck._move_world(1, 0)
	_check(deck._map_position == Vector2i(13, 36), "шаг сразу меняет логическую плитку")
	_check(deck._map_slide == Vector2(12.5, 36.5) and deck._map_camera == Vector2(12.5, 36.5), "до движения фигурка и камера ещё на старой плитке")
	var step: float = PLAYER_RULES.WALK_STEP_SECONDS
	deck._advance_map_animation(step / 2.0)
	_check(deck._map_slide.is_equal_approx(Vector2(13.0, 36.5)), "через половину шага фигурка на полпути")
	var camera_x := 12.5 + 0.5 * minf(1.0, 8.0 * step / 2.0)
	_check(deck._map_camera.is_equal_approx(Vector2(camera_x, 36.5)), "камера отстаёт от фигурки на min(1, 8·dt) разницы")
	var renderer = deck._world_map
	_check(renderer.get("_origin") == Vector2i(7, 31) and is_equal_approx(renderer.get("_view_shift").x, camera_x - 12.5), "окно сдвинуто дробно по камере")
	_check(is_equal_approx(deck._map_world_to_local(Vector2(12.5 * 48.0, 36.5 * 48.0)).x, (12.5 - camera_x + 5.5) * 48.0), "точка старой плитки в координатах окна смещена камерой")
	_check(renderer.get("_sprites").animation_state()["walking"], "во время шага фигурка идёт")
	deck._advance_map_animation(step)
	renderer = deck._world_map
	_check(deck._map_slide == Vector2(13.5, 36.5), "за один шаг фигурка встаёт на плитку без перелёта")
	_check(deck._map_camera.is_equal_approx(Vector2(13.5, 36.5)), "за полный шаг камера догоняет фигурку")
	_check(renderer.get("_origin") == Vector2i(8, 31) and is_equal_approx(renderer.get("_view_shift").x, 0.0), "в конце окно на целых плитках")
	_check(not renderer.get("_sprites").animation_state()["walking"], "ходьба кончается вместе со скольжением")
	deck._map_position = Vector2i(40, 60)
	deck._advance_map_animation(0.0)
	renderer = deck._world_map
	_check(deck._map_slide == Vector2(40.5, 60.5) and deck._map_camera == Vector2(40.5, 60.5), "телепорт ставит фигурку и камеру на плитку сразу")
	_check(renderer.get("_origin") == Vector2i(35, 55), "после телепорта окно перестроено на новую плитку")
	deck.queue_free()
	await get_tree().process_frame


# Догон только в пути: за кадр при 60 fps камера проходит 8/60 разницы до фигурки; после прибытия камера стоит на месте.
# Перетаскивание его выключает, щелчок и шаг включают, «К герою» центрирует сразу.
func _check_camera_follow() -> void:
	var deck = await _make_deck()
	deck._map_position = Vector2i(12, 36)
	deck._render_location()
	deck._move_world(1, 0)
	var before := Vector2(12.5, 36.5)
	deck._advance_map_animation(1.0 / 60.0)
	var expected: Vector2 = before + (deck._map_slide - before) * (8.0 / 60.0)
	_check(deck._map_camera.is_equal_approx(expected), "в пути за кадр при 60 fps камера проходит 8/60 разницы до фигурки")
	_check(deck._map_camera.x > before.x and deck._map_camera.x < deck._map_slide.x, "камера отстаёт от фигурки, а не встаёт на неё сразу")
	for _frame in 30:
		deck._advance_map_animation(1.0 / 60.0)
	var arrived: Vector2 = deck._map_camera
	_check(deck._map_slide == Vector2(13.5, 36.5) and arrived.x > 12.5 and arrived.x < 13.5, "на прибытии фигурка на плитке, камера ещё отстаёт")
	for _frame in 60:
		deck._advance_map_animation(1.0 / 60.0)
	_check(deck._map_camera == arrived, "после прибытия камера стоит на месте: догон только в пути")
	deck._center_map_camera()
	_check(deck._map_camera_follow and deck._map_camera.is_equal_approx(Vector2(13.5, 36.5)), "«К герою» центрирует камеру сразу, без догона")
	var renderer = deck._world_map
	var clicks: Array = []
	renderer.tile_clicked.connect(func(tile: Vector2i) -> void: clicks.append(tile))
	_press(renderer, Vector2(100.0, 100.0))
	_drag(renderer, Vector2(148.0, 100.0))
	_check(not deck._map_camera_follow, "перетаскивание мышью выключает догон камеры")
	_check(deck._map_camera.is_equal_approx(Vector2(12.5, 36.5)), "камера сдвинута на смещение мыши в тайлах")
	deck._advance_map_animation(0.5)
	_check(deck._map_camera.is_equal_approx(Vector2(12.5, 36.5)), "пока карту тянут, камера не возвращается к фигурке")
	_release(renderer, Vector2(148.0, 100.0))
	_check(clicks.is_empty(), "отпускание после перетаскивания не ходит по плитке")
	_press(renderer, Vector2(100.0, 100.0))
	_drag(renderer, Vector2(103.0, 102.0))
	_release(renderer, Vector2(103.0, 102.0))
	_check(clicks == [Vector2i(9, 33)], "движение до 4 px — это щелчок по плитке, а не перетаскивание")
	deck._center_map_camera()
	_check(deck._map_camera_follow and deck._map_camera.is_equal_approx(Vector2(13.5, 36.5)), "кнопка «К герою» центрирует камеру и включает догон")
	_press(renderer, Vector2(100.0, 100.0))
	_drag(renderer, Vector2(148.0, 100.0))
	_release(renderer, Vector2(148.0, 100.0))
	_check(not deck._map_camera_follow, "перетаскивание снова выключает догон")
	deck._move_world(-1, 0)
	_check(deck._map_camera_follow, "шаг фигурки снова включает догон, как ПКМ в Python")
	deck.queue_free()
	await get_tree().process_frame


# Зажим краями: у углов карты камера прижата к границе окна, а фигурка стоит у края окна, не в центре.
func _check_edge_clamp() -> void:
	var deck = await _make_deck()
	deck._map_position = Vector2i(0, 0)
	deck._advance_map_animation(0.0)
	var renderer = deck._world_map
	_check(deck._map_camera == Vector2(5.5, 5.5) and renderer.get("_origin") == Vector2i(0, 0), "у левого верхнего угла камера прижата к (5.5, 5.5), окно не уходит за карту")
	var feet: Vector2 = renderer.get("_sprites").animation_state()["feet"]
	_check(feet == Vector2(24.0, 24.0), "фигурка у угла стоит у края окна: ноги в (0.5, 0.5) тайла")
	deck._map_position = Vector2i(127, 255)
	deck._advance_map_animation(0.0)
	renderer = deck._world_map
	_check(deck._map_camera == Vector2(122.5, 250.5) and renderer.get("_origin") == Vector2i(117, 245), "у правого нижнего угла камера прижата к (122.5, 250.5)")
	feet = renderer.get("_sprites").animation_state()["feet"]
	_check(feet == Vector2(504.0, 504.0), "в правом нижнем углу ноги фигурки в (10.5, 10.5) тайла окна")
	deck.queue_free()
	await get_tree().process_frame


# Перетаскивание дальше окна данных перестраивает плитки, но карта и жест остаются теми же.
func _check_drag_refresh() -> void:
	var deck = await _make_deck()
	deck._map_position = Vector2i(60, 60)
	deck._advance_map_animation(0.0)
	var renderer = deck._world_map
	var clicks: Array = []
	renderer.tile_clicked.connect(func(tile: Vector2i) -> void: clicks.append(tile))
	_press(renderer, Vector2(300.0, 200.0))
	_drag(renderer, Vector2(300.0 - 20.0 * 48.0, 200.0))
	_check(deck._map_camera.is_equal_approx(Vector2(80.5, 60.5)), "перетаскивание на 20 тайлов влево сдвигает камеру на 20 тайлов вправо")
	deck._advance_map_animation(0.0)
	_check(deck._world_map == renderer, "перестройка данных не пересоздаёт карту, и жест продолжается")
	_check(MAP_RULES.covers_view(renderer.get("_data_window"), deck._map_camera, 11), "окно данных переехало за камерой")
	_check(deck._presence_view.is_inside_tree(), "слой игроков перестроен под новое окно")
	_drag(renderer, Vector2(300.0 - 22.0 * 48.0, 200.0))
	_check(deck._map_camera.is_equal_approx(Vector2(82.5, 60.5)), "после перестройки перетаскивание тянет дальше")
	_release(renderer, Vector2(300.0 - 22.0 * 48.0, 200.0))
	_check(clicks.is_empty(), "длинный жест не превращается в щелчок")
	deck.queue_free()
	await get_tree().process_frame


# Непроходимые плитки опубликованной карты: набор берётся из текущего рельефа, старый не остаётся в силе.
func _check_published_blocking() -> void:
	var deck = await _make_deck()
	deck._terrain = {"tiles": {"impassable": [[13, 36]], "water": [[14, 36]]}, "objects": [], "obstacles": []}
	_check(deck._is_world_tile_solid(Vector2i(13, 36)) and deck._is_world_tile_solid(Vector2i(14, 36)), "непроходимая и водная плитки опубликованной карты блокируют ходьбу")
	_check(not deck._is_world_tile_solid(Vector2i(15, 36)), "плитка вне наборов проходима")
	deck._terrain = {"tiles": {"mountain": [[15, 36]]}, "objects": [], "obstacles": []}
	_check(not deck._is_world_tile_solid(Vector2i(13, 36)) and deck._is_world_tile_solid(Vector2i(15, 36)), "новый рельеф заменяет набор блокировок")
	deck.queue_free()
	await get_tree().process_frame


# Клавиши WASD и стрелки скроллят камеру, фигурку не двигают (блок «Скролл карты стрелками / WASD» в Python).
# Shift ускоряет, углы карты зажимают камеру, чат с фокусом, меню выхода и подземелье скролл останавливают,
# S в режиме карт арены не скроллит, даже когда бой сбрасывает режим.
func _check_key_scroll() -> void:
	var deck = await _make_deck()
	deck.set_process(false)
	deck._map_position = Vector2i(40, 60)
	deck._advance_map_animation(0.0)
	var step := 850.0 * 0.1 / 48.0
	var start: Vector2 = deck._map_camera
	_key(KEY_D, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera.is_equal_approx(start + Vector2(step, 0.0)), "D сдвигает камеру вправо на 850 px/с")
	_check(deck._map_position == Vector2i(40, 60) and deck._map_slide == Vector2(40.5, 60.5), "клавиши не двигают фигурку")
	_check(not deck._map_camera_follow, "скролл клавишами выключает догон")
	_key(KEY_D, false)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera.is_equal_approx(start + Vector2(step, 0.0)), "отпущенная клавиша камеру не двигает")

	var before_shift: Vector2 = deck._map_camera
	_key(KEY_SHIFT, true)
	_key(KEY_W, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera.is_equal_approx(before_shift + Vector2(0.0, -step * 2.2)), "Shift + W скроллит в 2.2 раза быстрее")
	_key(KEY_W, false)
	_key(KEY_SHIFT, false)
	await get_tree().process_frame

	deck._map_position = Vector2i(0, 0)
	deck._advance_map_animation(0.0)
	_key(KEY_A, true)
	_key(KEY_W, true)
	await get_tree().process_frame
	deck._advance_map_animation(1.0)
	_check(deck._map_camera == Vector2(5.5, 5.5) and deck._map_position == Vector2i(0, 0), "скролл к углу карты зажат краями, фигурка на месте")
	_key(KEY_A, false)
	_key(KEY_W, false)
	await get_tree().process_frame

	var field := LineEdit.new()
	field.size = Vector2(200.0, 30.0)
	add_child(field)
	field.grab_focus()
	var before_focus: Vector2 = deck._map_camera
	_key(KEY_D, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera == before_focus, "чат с фокусом забирает клавиши: карта не скроллится")
	_key(KEY_D, false)
	field.release_focus()
	field.queue_free()
	await get_tree().process_frame

	deck._exit_menu.open()
	_key(KEY_D, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera == before_focus, "меню выхода останавливает скролл")
	_key(KEY_D, false)
	deck._exit_menu.close()
	await get_tree().process_frame

	deck._in_dungeon = true
	_key(KEY_S, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera == before_focus, "в подземелье клавиши карту не скроллят")
	_key(KEY_S, false)
	deck._in_dungeon = false
	await get_tree().process_frame

	var arena = deck._arena_window
	arena.visible = true
	arena.set("_mode", "cards")
	deck._advance_map_animation(0.0)
	_key(KEY_S, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(arena.get("_mode") == "", "S в бою отменил режим карт")
	_check(deck._map_camera == before_focus, "S, нажатый в режиме карт, не скроллит, даже когда бой сбросил режим")
	_key(KEY_S, false)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	arena.set("_mode", "cards")
	deck._advance_map_animation(0.0)
	_key(KEY_DOWN, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.1)
	_check(deck._map_camera.is_equal_approx(before_focus + Vector2(0.0, step)), "↓ скроллит и в режиме карт арены")
	_key(KEY_DOWN, false)
	arena.visible = false
	arena.set("_mode", "")
	await get_tree().process_frame
	deck.queue_free()
	await get_tree().process_frame


# Space ставит камеру на фигурку и включает догон, как в Python; фигурка стоит, зажим краями действует.
# Меню выхода, модальное окно, подземелье и чат с фокусом Space не забирают; бой на арене пропускает.
func _check_space_center() -> void:
	var deck = await _make_deck()
	deck.set_process(false)
	deck._map_position = Vector2i(0, 0)
	deck._advance_map_animation(0.0)
	_key(KEY_D, true)
	await get_tree().process_frame
	deck._advance_map_animation(1.0)
	_key(KEY_D, false)
	await get_tree().process_frame
	_check(deck._map_camera.x > 15.0 and not deck._map_camera_follow, "клавиши отвели камеру от фигурки и выключили догон")
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera == Vector2(5.5, 5.5) and deck._map_camera_follow, "Space ставит камеру на фигурку и зажимает её краями карты")
	_check(deck._map_position == Vector2i(0, 0) and deck._map_slide == Vector2(0.5, 0.5), "Space не двигает фигурку")

	deck._map_position = Vector2i(40, 60)
	deck._advance_map_animation(0.0)
	_key(KEY_A, true)
	await get_tree().process_frame
	deck._advance_map_animation(0.5)
	_key(KEY_A, false)
	await get_tree().process_frame
	var away: Vector2 = deck._map_camera
	_check(away.x < 38.0, "камера уехала от фигурки")

	deck._exit_menu.open()
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera == away, "меню выхода забирает Space")
	deck._exit_menu.close()

	deck._supplies_shop_window.open(0)
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera == away, "открытое окно магазина забирает Space")
	deck._supplies_shop_window.close()

	deck._in_dungeon = true
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera == away, "в подземелье Space карту не трогает")
	deck._in_dungeon = false

	var field := LineEdit.new()
	field.size = Vector2(200.0, 30.0)
	add_child(field)
	field.grab_focus()
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera == away, "чат с фокусом не даёт центрировать карту")
	field.release_focus()
	field.queue_free()
	await get_tree().process_frame

	deck._arena_window.visible = true
	deck._unhandled_input(_key_event(KEY_SPACE))
	_check(deck._map_camera.is_equal_approx(Vector2(40.5, 60.5)), "бой на арене Space пропускает, как в Python")
	deck._arena_window.visible = false
	deck.queue_free()
	await get_tree().process_frame


func _key_event(keycode: Key) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	return event


func _key(keycode: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = pressed
	Input.parse_input_event(event)


func _press(renderer, point: Vector2) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = point
	renderer._gui_input(event)


func _drag(renderer, point: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	event.position = point
	renderer._gui_input(event)


func _release(renderer, point: Vector2) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = false
	event.position = point
	renderer._gui_input(event)


func _make_deck() -> Node:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {
		"id": 42,
		"name": "Тест",
		"type": "warrior",
		"level": 5,
		"hp": 60,
		"max_hp": 142,
		"mp": 0,
		"max_mp": 0,
		"zone": "world_map",
		"position_x": 600.0,
		"position_y": 1752.0,
		"position_direction": "s",
	}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	deck._pending_action = "stub"
	deck._terrain = {"objects": [], "obstacles": []}
	return deck


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame
