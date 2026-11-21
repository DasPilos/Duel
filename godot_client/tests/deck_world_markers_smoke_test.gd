extends Node

# Маркеры карты мира Deck: каждый вид получает свою букву и подсказку, а клик по плитке передаётся в deck_world.gd.
# Сеть не используется: запросы мира ждут в очереди (_pending_action занят), как в deck_arena_world_smoke_test.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RULES := preload("res://scripts/deck_world_map_rules.gd")
const RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const FIXTURES := preload("res://tests/deck_world_map_fixtures.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const DUNGEON_TOOLTIP := "Вход в подземелье: стойте на нём 5 секунд"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_marker_rules()
	await _check_deck_markers()
	await _check_signals()
	GameSession.clear()
	if _checks == 0:
		_check(false, "проверки маркеров выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_world_markers_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_marker_rules() -> void:
	var player := RULES.marker_for({"player": true, "tavern": true})
	_check(player.get("symbol") == "T", "игрок не получает букву: фигурку рисует слой спрайтов, зона под ним остаётся")
	_check(RULES.marker_for({"player": true}).is_empty(), "метки игрока нет: фигурку рисует слой спрайтов")
	var zone_symbols := {"tavern": "T", "guild": "G", "supplies": "S", "library": "L", "talent": "Д"}
	for zone in zone_symbols:
		var marker := RULES.marker_for({zone: true})
		_check(marker.get("symbol") == zone_symbols[zone] and marker.get("kind") == zone, "зона %s отмечена буквой %s" % [zone, zone_symbols[zone]])
	_check(RULES.marker_for({"guild": true}).get("color").is_equal_approx(Color(235 / 255.0, 200 / 255.0, 70 / 255.0)), "гильдия окрашена цветом подписи из Python")
	var dungeon := RULES.marker_for({"dungeon": true})
	_check(dungeon.get("symbol") == "D" and dungeon.get("tooltip") == DUNGEON_TOOLTIP, "вход в подземелье отмечен D с прежней подсказкой")
	var arena_kinds := {"K": "Кобольд", "E": "Древний ент", "X": "Скелет", "N": "Некромант"}
	for symbol in arena_kinds:
		var marker := RULES.marker_for({"arena": {"marker": symbol, "name": arena_kinds[symbol]}})
		_check(marker.get("symbol") == symbol and marker.get("tooltip") == "%s — бой на арене" % arena_kinds[symbol], "арена %s отмечена с прежней подсказкой" % symbol)
	_check(RULES.marker_for({"solid": true}).is_empty(), "твёрдый тайл без зоны не получает буквы")
	_check(RULES.marker_for({"solid": true, "tavern": true}).get("symbol") == "T", "таверна важнее препятствия, как раньше")
	_check(RULES.marker_for({"dungeon": true, "arena": {"marker": "K", "name": "Кобольд"}}).get("symbol") == "D", "вход в подземелье важнее арены")
	_check(RULES.marker_for({}).is_empty(), "обычная земля без букв")


func _check_deck_markers() -> void:
	var deck = await _make_deck()

	deck._map_position = Vector2i(12, 36)
	deck._render_location()
	var renderer = _find_renderer(deck)
	_check(renderer.marker_at(Vector2i(12, 36)).is_empty(), "на плитке игрока нет маркера: его рисует слой спрайтов")
	_check(_find_button_text(deck, "@") == null, "кнопки @ больше нет")
	_check(renderer.marker_at(Vector2i(12, 34)).is_empty(), "кристалл не получает букву, он рисуется объектом")
	_check(not renderer.is_steppable(Vector2i(12, 35)), "кристалл сверху не подсвечен как шаг")
	_check(renderer.is_steppable(Vector2i(11, 36)) and renderer.is_steppable(Vector2i(13, 36)) and renderer.is_steppable(Vector2i(12, 37)), "три свободных соседа подсвечены")
	_check(not renderer.is_steppable(Vector2i(13, 37)), "диагональ не подсвечена")

	deck._map_position = Vector2i(3, 27)
	deck._render_location()
	renderer = _find_renderer(deck)
	_check(renderer.marker_at(Vector2i(5, 27)).get("symbol") == "T", "таверна отмечена T")
	_check(renderer.is_steppable(Vector2i(4, 27)), "вход в таверну подсвечен как шаг")

	deck._map_position = Vector2i(24, 43)
	deck._render_location()
	renderer = _find_renderer(deck)
	_check(renderer.marker_at(Vector2i(26, 44)).get("symbol") == "D" and renderer.marker_at(Vector2i(26, 44)).get("tooltip") == DUNGEON_TOOLTIP, "вход в подземелье отмечен D")
	_check(_find_button_text(deck, "D").tooltip_text == DUNGEON_TOOLTIP, "подсказка входа видна на кнопке")

	deck._map_position = Vector2i(53, 12)
	deck._render_location()
	_check(_find_button_text(deck, "K").tooltip_text == "Кобольд — бой на арене", "кобольд отмечен K с прежней подсказкой")

	deck._map_position = Vector2i(41, 6)
	deck._render_location()
	_check(_find_renderer(deck).marker_at(Vector2i(42, 6)).get("symbol") == "E", "древний ент отмечен E")
	deck._map_position = Vector2i(34, 53)
	deck._render_location()
	_check(_find_renderer(deck).marker_at(Vector2i(34, 55)).get("symbol") == "X", "скелет отмечен X")
	deck._map_position = Vector2i(48, 53)
	deck._render_location()
	_check(_find_renderer(deck).marker_at(Vector2i(48, 58)).get("symbol") == "N", "некромант отмечен N")

	deck.queue_free()
	await get_tree().process_frame
	GameSession.clear()


func _check_signals() -> void:
	var renderer = RENDERER_SCRIPT.new()
	add_child(renderer)
	var clicked: Array[Vector2i] = []
	var hovered: Array[Vector2i] = []
	renderer.tile_clicked.connect(func(tile: Vector2i) -> void: clicked.append(tile))
	renderer.tile_hovered.connect(func(tile: Vector2i) -> void: hovered.append(tile))
	renderer.configure({
		"terrain": FIXTURES.procedural_terrain(),
		"center": Vector2i(12, 36),
		"view_size": 11,
		"map_size": Vector2i(128, 256),
		"tile_px": 48.0,
		"markers": {Vector2i(13, 36): RULES.marker_for({"guild": true})},
		"solid": [Vector2i(12, 35)],
		"steppable": [Vector2i(11, 36), Vector2i(13, 36), Vector2i(12, 37)],
	})

	var release := _mouse_button(Vector2(6 * 48 + 24, 5 * 48 + 24), MOUSE_BUTTON_LEFT, false)
	renderer._gui_input(release)
	_check(clicked == [Vector2i(13, 36)], "клик по плитке отдаёт её координату (13, 36)")

	renderer._gui_input(_mouse_button(Vector2(6 * 48 + 24, 5 * 48 + 24), MOUSE_BUTTON_LEFT, true))
	renderer._gui_input(_mouse_button(Vector2(6 * 48 + 24, 5 * 48 + 24), MOUSE_BUTTON_RIGHT, false))
	renderer._gui_input(_mouse_button(Vector2(-10, 10), MOUSE_BUTTON_LEFT, false))
	_check(clicked.size() == 1, "нажатие, правая кнопка и клик за окном не отдают тайл")

	_find_button_text(renderer, "G").pressed.emit()
	_check(clicked.size() == 2 and clicked[1] == Vector2i(13, 36), "кнопка маркера передаёт тот же тайл")
	_check(renderer.marker_at(Vector2i(13, 36)).get("symbol") == "G", "маркер на плитке отвечает за букву G")

	var motion := InputEventMouseMotion.new()
	motion.position = Vector2(24, 24)
	renderer._gui_input(motion)
	renderer._gui_input(motion)
	_check(hovered == [Vector2i(7, 31)], "наведение отдаёт тайл один раз")
	motion.position = Vector2(6 * 48 + 24, 5 * 48 + 24)
	renderer._gui_input(motion)
	_check(renderer.mouse_default_cursor_shape == Control.CURSOR_POINTING_HAND, "над соседним тайлом курсор указывает на шаг")
	renderer.queue_free()
	await get_tree().process_frame

	var deck = await _make_deck()
	deck._map_position = Vector2i(12, 36)
	deck._render_location()
	var world_map = _find_renderer(deck)
	world_map.tile_clicked.emit(Vector2i(12, 35))
	_check(deck._map_position == Vector2i(12, 36), "клик по кристаллу не двигает игрока")
	world_map.tile_clicked.emit(Vector2i(14, 36))
	_check(deck._map_position == Vector2i(12, 36), "клик через один тайл не двигает игрока")
	world_map.tile_clicked.emit(Vector2i(13, 36))
	_check(deck._map_position == Vector2i(13, 36) and deck._map_direction == "e", "клик по соседнему тайлу делает шаг")

	deck._map_position = Vector2i(24, 43)
	deck._render_location()
	_find_button_text(deck, "D").pressed.emit()
	_check(deck._map_position == Vector2i(25, 43) and not deck._dungeon_gate_timer.is_stopped(), "кнопка входа в подземелье делает шаг и запускает таймер входа")
	deck._dungeon_gate_timer.stop()

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
		"position_x": float(12 * 48 + 24),
		"position_y": float(36 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _mouse_button(position: Vector2, button: MouseButton, pressed: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = pressed
	event.position = position
	return event


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
