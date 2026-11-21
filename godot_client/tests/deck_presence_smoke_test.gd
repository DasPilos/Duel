extends Node

# Другие игроки на карте мира Deck: фильтры, границы экрана, наведение и карточка как в deck/ui/player_presence.py.
# Эталон — tests/fixtures/deck_presence/presence_cases.json, сгенерированная настоящими функциями Python
# (pygame 2.6.1, .venv_313): активные и AFK-игроки, кто рисуется, player_at и поля карточки.

const RULES := preload("res://scripts/deck_presence_rules.gd")
const VIEW_SCRIPT := preload("res://scripts/deck_presence_view.gd")
const CHARACTER_RULES := preload("res://scripts/deck_character_rules.gd")
const RENDERER_SCRIPT := preload("res://scripts/deck_world_map_renderer.gd")
const SPRITES_SCRIPT := preload("res://scripts/deck_world_sprites.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const FIXTURES := preload("res://tests/deck_world_map_fixtures.gd")
const FIXTURE_PATH := "res://tests/fixtures/deck_presence/presence_cases.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const OWN_TILE := Vector2i(46, 95)

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	var fixture: Dictionary = parsed if parsed is Dictionary else {}
	_check(not fixture.is_empty(), "фикстура presence_cases.json читается")
	if not fixture.is_empty():
		_check_filters(fixture)
		_check_bounds(fixture)
		_check_hits(fixture)
		_check_card_fields(fixture)
	_check_helpers()
	await _check_scene()
	GameSession.clear()
	if _checks == 0:
		_check(false, "проверки игроков выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_presence_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_filters(fixture: Dictionary) -> void:
	var occupants: Array = fixture["occupants"]
	var own_id := str(fixture["own_id"])
	var active := RULES.active_occupants(occupants, "world_map", own_id)
	_check(_ids(active) == _ids_at(occupants, _ints(fixture["active"])), "активные игроки как active_player_entities: порядок списка, свой и чужая локация отсеяны")
	var afk := RULES.afk_occupants(occupants, "world_map")
	_check(_ids(afk) == _ids_at(occupants, _ints(fixture["afk"])), "AFK-игроки в локации как draw_afk_players")
	_check(RULES.active_occupants(occupants, "tavern", own_id).size() == 1, "локация «tavern» даёт только своего игрока таверны")


func _check_bounds(fixture: Dictionary) -> void:
	var viewport := Vector2(float(fixture["viewport"]["width"]), float(fixture["viewport"]["height"]))
	var drawn := _ints(fixture["drawn_active"]) + _ints(fixture["drawn_afk"])
	var candidates := _ints(fixture["active"]) + _ints(fixture["afk"])
	for index in candidates:
		_check(RULES.on_screen(_screen(fixture, index), viewport) == drawn.has(index), "игрок %d рисуется по границам экрана, как в Python" % index)
	_check(RULES.on_screen(Vector2(-80, 0), viewport) and not RULES.on_screen(Vector2(-81, 0), viewport), "левая граница -80 входит, -81 нет")
	_check(RULES.on_screen(Vector2(viewport.x + 80, 0), viewport) and not RULES.on_screen(Vector2(viewport.x + 81, 0), viewport), "правая граница WIDTH + 80")
	_check(RULES.on_screen(Vector2(0, -100), viewport) and not RULES.on_screen(Vector2(0, -101), viewport), "верхняя граница -100")
	_check(RULES.on_screen(Vector2(0, viewport.y + 20), viewport) and not RULES.on_screen(Vector2(0, viewport.y + 21), viewport), "нижняя граница HEIGHT + 20")


func _check_hits(fixture: Dictionary) -> void:
	var occupants: Array = fixture["occupants"]
	var entries: Array = []
	for index in _ints(fixture["active"]):
		entries.append({"occupant": occupants[index], "screen": _screen(fixture, index)})
	for hit in fixture["hits"]:
		var point := Vector2(float(hit["point"][0]), float(hit["point"][1]))
		var found: Dictionary = RULES.player_at(entries, point)
		var found_index := -1 if found.is_empty() else _index_of(occupants, found["character_id"])
		_check(found_index == int(hit["index"]), "player_at в точке (%d, %d) как в Python" % [point.x, point.y])


func _check_card_fields(fixture: Dictionary) -> void:
	var occupants: Array = fixture["occupants"]
	for expected in fixture["cards"]:
		var index := int(expected["index"])
		var profile := CHARACTER_RULES.normalize_profile(RULES.card_profile(occupants[index]), "", "player")
		var label := "карточка игрока %d" % index
		_check(profile["name"] == expected["name"] and profile["type"] == expected["type"] and profile["profession_type"] == expected["profession_type"], "%s: имя и класс" % label)
		_check(RULES.id_text(profile["character_id"]) == expected["character_id"] and RULES.id_text(profile["id"]) == expected["character_id"], "%s: id" % label)
		var level := int(profile["level"])
		_check(level == int(expected["level"]) and int(profile["xp"]) == int(expected["xp"]) and CHARACTER_RULES.xp_to_next(level) == int(expected["xp_to_next"]), "%s: уровень и XP" % label)
		var hp: Vector2i = CHARACTER_RULES.displayed_hp(profile)
		_check(hp.x == int(expected["hp"]) and hp.y == int(expected["max_hp"]), "%s: HP" % label)
		_check(int(profile["mp"]) == int(expected["mp"]) and int(profile["max_mp"]) == int(expected["max_mp"]), "%s: MP" % label)
		_check(int(profile["stat_points"]) == int(expected["stat_points"]) and int(profile["coins"]) == int(expected["coins"]), "%s: очки характеристик и монеты" % label)
		var effective: Dictionary = CHARACTER_RULES.effective_stats(profile)
		var stats_match := true
		for key in expected["effective_stats"]:
			stats_match = stats_match and int(effective.get(key, -1)) == int(expected["effective_stats"][key])
		_check(stats_match, "%s: характеристики" % label)
		var derived: Dictionary = CHARACTER_RULES.derived_values(profile, null)
		var derived_match := true
		for key in expected["derived"]:
			derived_match = derived_match and str(derived.get(key, "")) == str(expected["derived"][key])
		_check(derived_match, "%s: производные значения" % label)


func _check_helpers() -> void:
	_check(RULES.direction_of({}) == "s" and RULES.direction_of({"position_direction": ""}) == "s" and RULES.direction_of({"position_direction": "ne"}) == "ne", "пустое направление даёт s, как `or \"s\"`")
	_check(RULES.display_name({}) == "Игрок" and RULES.afk_label({"name": "Ник"}) == "Ник (АФК)", "имя по умолчанию «Игрок» и подпись «(АФК)»")
	_check(RULES.has_position({"position_x": 0.0, "position_y": 0.0}) and not RULES.has_position({"position_x": 0.0}), "позиция 0 считается заданной, отсутствие — нет")
	_check(RULES.is_own({"character_id": 42}, "42") and RULES.is_own({"character_id": 42.0}, "42") and not RULES.is_own({"character_id": 7}, "42"), "свой персонаж по character_id, 42.0 из JSON тоже свой")
	_check(RULES.hit_rect(Vector2(100, 100)) == Rect2(78, 42, 44, 62), "область наведения 44x62: от -22 до +22 по x, от -58 до +4 по y")
	_check(not RULES.contains(RULES.hit_rect(Vector2(100, 100)), Vector2(122, 50)) and RULES.contains(RULES.hit_rect(Vector2(100, 100)), Vector2(78, 42)), "правая граница не входит, левая и верхняя входят")
	var feet := RULES.map_point(_world(OWN_TILE), OWN_TILE, 11, 48.0)
	_check(feet == Vector2(264, 264), "точка персонажа в центре окна 11x11: (264, 264)")
	_check(RULES.map_point(_world(Vector2i(48, 95)), OWN_TILE, 11, 48.0) == Vector2(360, 264), "плитка справа от персонажа на 96 px дальше")
	var card := RULES.card_profile({"name": "Ник", "character_id": 5, "afk": true, "talents": {}, "location": "world_map"})
	_check(card.has("name") and card["id"] == 5 and not card.has("afk") and not card.has("talents"), "в карточку идут только её поля")
	_check(RULES.card_profile({"id": 7})["character_id"] == 7, "без character_id берётся id, как в Python")


func _check_scene() -> void:
	var deck = await _make_deck()
	deck._terrain = FIXTURES.procedural_terrain()
	deck._map_position = OWN_TILE
	deck._social_data = {"occupants": _scene_occupants()}
	deck._render_location()
	await get_tree().process_frame
	await get_tree().process_frame
	var renderer = _find_node(deck, RENDERER_SCRIPT)
	var sprites = _find_node(deck, SPRITES_SCRIPT)
	var view = _find_node(deck, VIEW_SCRIPT)
	_check(renderer != null and view != null and deck._presence_view == view, "слой игроков создан в карте мира и доступен деке")
	if view == null or renderer == null or sprites == null:
		deck.queue_free()
		await get_tree().process_frame
		return
	_check(view.get_parent() == sprites and sprites.get_parent() == renderer, "слой игроков лежит в слое фигурок: рисуется поверх фигурки персонажа")
	_check(view.mouse_filter == Control.MOUSE_FILTER_IGNORE and view.card_node().mouse_filter == Control.MOUSE_FILTER_IGNORE and _all_ignore(view.card_node()), "слой и карточка не принимают мышь: клики идут на плитки")
	_check(view.active_names() == ["Соперник", "Далеко"], "активные игроки: своего и таверны нет, дальний остаётся в списке")
	_check(view.afk_names() == ["Сонный"], "AFK-игрок локации в списке AFK")
	_check(view.draw_count() > 0, "слой нарисован")
	var feet: Vector2 = sprites.animation_state()["feet"]
	_check(RULES.map_point(_world(OWN_TILE), OWN_TILE, 11, 48.0) == feet, "точка персонажа совпадает с ногами фигурки")
	var rival: Vector2 = view.screen_of(7)
	_check(rival - view.global_position == Vector2(360, 264), "маркер соперника стоит в своей плитке окна карты")
	var hit: Vector2 = rival + Vector2(0, -20)
	view.forward_mouse_motion(hit, false)
	var card = view.card_node()
	_check(view.hovered_name() == "Соперник" and view.card_visible() and card.visible, "наведение на соперника показывает карточку")
	_check(card.get("_name_label").text == "Соперник" and card.get("_level_label").text == "Уровень 3", "карточка: имя и уровень соперника")
	_check(card.get("_xp_label").text == "XP: 21/120" and card.get("_hp_label").text == "HP: 12/30", "карточка: XP и HP из записи")
	_check(card.get("_mp_label").text == "MP: 4/9" and card.get("_stat_points_label").text == "Свободные очки: 2", "карточка: MP и очки характеристик")
	_check(Rect2(Vector2.ZERO, get_viewport().get_visible_rect().size).encloses(card.get_global_rect()), "карточка целиком в окне просмотра, не обрезана")
	view.forward_mouse_motion(rival + Vector2(40, -20), false)
	_check(view.hovered_name() == "" and not view.card_visible(), "вне области маркера карточки нет")
	view.forward_mouse_motion(view.screen_of(11) + Vector2(0, -20), false)
	_check(view.hovered_name() == "" and not view.card_visible(), "AFK-игрок не наводится, как player_at")
	view.forward_mouse_motion(hit, true)
	_check(view.hovered_name() == "" and not card.visible, "открытое окно поверх карты гасит наведение")
	_check(deck._presence_blocked() == false, "без открытых окон наведение разрешено")
	deck._comparison.visible = true
	_check(deck._presence_blocked(), "сравнение персонажей закрывает карту для наведения")
	deck._comparison.visible = false

	var motions_before: int = view.motion_count()
	var motion := InputEventMouseMotion.new()
	motion.position = hit
	motion.global_position = hit
	deck._input(motion)
	_check(view.motion_count() == motions_before + 1, "движение мыши из deck_world.gd передаётся слою игроков")

	var clicked: Array = []
	renderer.tile_clicked.connect(func(tile: Vector2i) -> void: clicked.append(tile))
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = hit - renderer.global_position
	renderer._gui_input(release)
	_check(clicked == [Vector2i(48, 95)], "клик по маркеру игрока отдаёт плитку под ним карте, как раньше")

	deck._render_location()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_count_nodes(deck, VIEW_SCRIPT) == 1, "после перестройки карты остался один слой игроков")

	deck.queue_free()
	await get_tree().process_frame


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
		"position_x": float(OWN_TILE.x * 48 + 24),
		"position_y": float(OWN_TILE.y * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _scene_occupants() -> Array:
	return [
		_occupant("Соперник", 7, Vector2i(48, 95), "e", "archer", 3, false, "world_map"),
		_occupant("Сонный", 11, Vector2i(44, 96), "s", "necromancer", 2, true, "world_map"),
		_occupant("Тест", 42, OWN_TILE, "s", "warrior", 5, false, "world_map"),
		_occupant("Таверна", 13, Vector2i(46, 93), "s", "warrior", 2, false, "tavern"),
		_occupant("Далеко", 15, Vector2i(66, 95), "s", "mage", 4, false, "world_map"),
	]


func _occupant(name: String, character_id: int, tile: Vector2i, direction: String, profession: String, level: int, afk: bool, location: String) -> Dictionary:
	return {
		"name": name,
		"character_id": character_id,
		"type": profession,
		"level": level,
		"xp": 7 * level,
		"hp": 12,
		"max_hp": 30,
		"mp": 4,
		"max_mp": 9,
		"stats": CHARACTER_RULES.DEFAULT_STATS.duplicate(),
		"stat_points": level - 1,
		"location": location,
		"afk": afk,
		"position_x": _world(tile).x,
		"position_y": _world(tile).y,
		"position_direction": direction,
	}


func _world(tile: Vector2i) -> Vector2:
	return Vector2(float(tile.x * 48 + 24), float(tile.y * 48 + 24))


func _screen(fixture: Dictionary, index: int) -> Vector2:
	var values: Array = fixture["screen"][str(index)]
	return Vector2(float(values[0]), float(values[1]))


func _ints(values: Array) -> Array:
	var result: Array = []
	for value in values:
		result.append(int(value))
	return result


func _ids(occupants: Array) -> Array:
	var result: Array = []
	for occupant in occupants:
		result.append(RULES.id_text(occupant["character_id"]))
	return result


func _ids_at(occupants: Array, indices: Array) -> Array:
	var result: Array = []
	for index in indices:
		result.append(RULES.id_text(occupants[index]["character_id"]))
	return result


func _index_of(occupants: Array, character_id: Variant) -> int:
	for index in range(occupants.size()):
		if RULES.id_text(occupants[index]["character_id"]) == RULES.id_text(character_id):
			return index
	return -1


func _all_ignore(node: Node) -> bool:
	for child in node.get_children():
		if child is Control and child.mouse_filter != Control.MOUSE_FILTER_IGNORE:
			return false
		if not _all_ignore(child):
			return false
	return true


func _count_nodes(node: Node, script: Script) -> int:
	var count := 1 if node.get_script() == script else 0
	for child in node.get_children():
		count += _count_nodes(child, script)
	return count


func _find_node(node: Node, script: Script) -> Node:
	for child in node.get_children():
		if child.get_script() == script:
			return child
		var found := _find_node(child, script)
		if found != null:
			return found
	return null
