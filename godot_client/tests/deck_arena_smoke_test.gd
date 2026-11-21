extends Node

const WINDOW_SCRIPT := preload("res://scripts/deck_arena_window.gd")
const RULES := preload("res://scripts/deck_arena_rules.gd")
const SAMPLES_PATH := "res://tests/deck_arena_samples.json"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_geometry(samples)
		_check_hex(samples)
		_check_rules(samples)
		await _check_window(samples)
	else:
		_check(false, "файл эталона арены читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_arena_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)


func _center(state: Dictionary) -> Vector2i:
	var center: Array = state["center"] if state.has("center") else state["arena"]["center"]
	return Vector2i(int(center[0]), int(center[1]))


func _check_geometry(samples: Dictionary) -> void:
	var center := _center(samples)
	var size := float(samples["tile_size"])
	var centers_match := true
	var polygons_match := true
	for row in samples["geometry"]:
		var tile := RULES.tile_from_array(row["tile"])
		var center_pos := RULES.tile_center(tile, center, size, Vector2.ZERO)
		var expected := Vector2(float(row["center"][0]), float(row["center"][1]))
		if center_pos.distance_to(expected) > 0.001:
			centers_match = false
		var polygon := RULES.hex_polygon(expected, size)
		for index in 6:
			var point := Vector2(float(row["polygon"][index][0]), float(row["polygon"][index][1]))
			if polygon[index].distance_to(point) > 0.001:
				polygons_match = false
	_check(centers_match, "центры клеток совпадают с ArenaController.tile_center")
	_check(polygons_match, "шестиугольники совпадают с ArenaController.tile_polygon")


func _check_hex(samples: Dictionary) -> void:
	var distances_match := true
	for pair in samples["hex_pairs"]:
		var distance := RULES.hex_distance(RULES.tile_from_array(pair["a"]), RULES.tile_from_array(pair["b"]))
		if distance != int(pair["distance"]):
			distances_match = false
	_check(distances_match, "расстояния между клетками совпадают с arena_battle.hex_distance")
	var neighbors_match := true
	for row in samples["neighbors"]:
		var got := RULES.hex_neighbors(RULES.tile_from_array(row["tile"]))
		for index in 6:
			if got[index] != RULES.tile_from_array(row["neighbors"][index]):
				neighbors_match = false
	_check(neighbors_match, "соседи клетки совпадают с arena_battle.hex_neighbors")


func _check_rules(samples: Dictionary) -> void:
	var battle: Dictionary = samples["states"]["battle"]
	var attack: Dictionary = samples["states"]["attack"]
	var center := _center(battle)
	var tiles: Array = battle["tiles"]
	var size := 40.0
	var origin := Vector2(300.0, 200.0)
	var picks_own_tile := true
	for value in tiles:
		var tile := RULES.tile_from_array(value)
		var pos := RULES.tile_center(tile, center, size, origin)
		if RULES.tile_at(pos, tiles, center, size, origin) != tile:
			picks_own_tile = false
	_check(picks_own_tile, "клик в центр клетки попадает в эту клетку")
	_check(RULES.tile_at(origin + Vector2(5000.0, 5000.0), tiles, center, size, origin) == RULES.NO_TILE, "клик за пределами поля не выбирает клетку")

	var fit := RULES.fit_board(tiles, center, Vector2(1200.0, 700.0))
	var area := Rect2(Vector2.ZERO, Vector2(1200.0, 700.0))
	var fits := float(fit["size"]) > 4.0
	for value in tiles:
		var polygon := RULES.hex_polygon(RULES.tile_center(RULES.tile_from_array(value), center, float(fit["size"]), fit["origin"]), float(fit["size"]))
		for point in polygon:
			if not area.has_point(point):
				fits = false
	_check(fits, "поле целиком помещается в область доски")

	_check(RULES.card_mode(battle["hand"][0]) == "unit", "карта «себе» выбирает цель-существо")
	_check(RULES.card_mode(attack["hand"][4]) == "attack", "карта врага выбирает гекс для атаки")
	_check(RULES.card_mode({"role": "summon"}) == "tile", "призыв выбирает свободный гекс")
	_check(RULES.card_mode({"role": "ally", "effect": "necromancer_transfer"}) == "transfer", "перенос существа идёт в два шага")

	var summon_hint := RULES.targeting_hint({"role": "summon"}, "", 2)
	_check(summon_hint == "Выберите клетку для призыва (радиус 2) — S отменяет розыгрыш", "подсказка призыва как в оверлее")
	_check(RULES.targeting_hint({"role": "enemy"}, "", 2).ends_with(" — S отменяет розыгрыш"), "подсказка с отменой S")

	var banner := RULES.banner_title(battle)
	_check(banner.begins_with("БОЙ: Тест против Кобольд"), "баннер назван по игроку и противнику")
	_check(RULES.details_text(battle).contains("Карты: 0/2"), "баннер показывает карты за ход")
	_check(RULES.status_text(battle) == "Ваш ход", "статус хода игрока")
	_check(RULES.status_text(samples["states"]["result"]) == "Бой окончен", "статус окончен боя")
	_check(RULES.result_of(samples["states"]["result"]) == "teleport", "итог телепорта из эталона")
	_check(RULES.unit_info_text(RULES.unit_by_id(battle["units"], "enemy")).contains("Здоровье: 20/20"), "карточка существа показывает здоровье")

	var player_tile := RULES.tile_from_array(RULES.unit_by_id(attack["units"], "player")["position"])
	var enemy_unit := RULES.unit_by_id(attack["units"], "enemy")
	var enemy_card: Dictionary = attack["hand"][4]
	var aim_tile := RULES.tile_from_array(enemy_card["preview"]["aim_tiles"][0])
	var aim_plan := RULES.plan_targeting_click(enemy_card, enemy_card["preview"], aim_tile, {}, "", 4)
	_check(aim_plan["kind"] == "play" and aim_plan["command"]["aim_tile"] == RULES.tile_to_array(aim_tile), "клик по гексу прицела отправляет aim_tile")
	var far_tile := RULES.tile_from_array(tiles[0])
	var unit_plan := RULES.plan_targeting_click(enemy_card, {"aim_tiles": [], "targets": []}, far_tile, enemy_unit, "", 4)
	_check(unit_plan["kind"] == "play" and unit_plan["command"]["target"] == "enemy", "удар по врагу без гекса идёт по его id")
	var ally_plan := RULES.plan_targeting_click(enemy_card, enemy_card["preview"], far_tile, RULES.unit_by_id(attack["units"], "player"), "", 4)
	_check(ally_plan["kind"] == "hint", "клик по себе при атаке — подсказка без команды")
	_check(player_tile != RULES.NO_TILE, "игрок стоит на клетке")

	var summon_tile := RULES.tile_from_array(tiles[1])
	var summon_card := {"name": "Призыв", "role": "summon", "effect": "mage_golem", "preview": {"tiles": [RULES.tile_to_array(summon_tile)]}}
	var summon_plan := RULES.plan_targeting_click(summon_card, summon_card["preview"], summon_tile, {}, "", 1)
	_check(summon_plan["kind"] == "play" and summon_plan["command"]["tile"] == RULES.tile_to_array(summon_tile), "призыв отправляет клетку как tile")

	var transfer_card := {"name": "Перенос", "role": "ally", "effect": "necromancer_transfer", "preview": {"targets": ["player"], "transfer_tiles": {"player": [RULES.tile_to_array(summon_tile)]}}}
	var first := RULES.plan_targeting_click(transfer_card, transfer_card["preview"], player_tile, RULES.unit_by_id(attack["units"], "player"), "", 2)
	_check(first["kind"] == "transfer_target" and first["target"] == "player", "перенос: сначала выбирается существо")
	var second := RULES.plan_targeting_click(transfer_card, transfer_card["preview"], summon_tile, {}, "player", 2)
	_check(second["kind"] == "play" and second["command"]["destination"] == RULES.tile_to_array(summon_tile), "перенос: затем клетка назначения")


func _tile_pixel(state: Dictionary, tile: Vector2i, window) -> Vector2:
	return RULES.tile_center(tile, _center(state), window._tile_size, window._origin)


# Кнопки режима переключаются, поэтому повторное нажатие выключает режим: включаем только при необходимости.
func _ensure_mode(window, mode: String) -> void:
	if window._mode != mode:
		window._on_button_pressed(mode)


func _check_window(samples: Dictionary) -> void:
	var states: Dictionary = samples["states"]
	var battle: Dictionary = states["battle"]
	var attack: Dictionary = states["attack"]
	var host := Control.new()
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(host)
	var window = WINDOW_SCRIPT.new()
	host.add_child(window)
	await get_tree().process_frame
	await get_tree().process_frame
	var commands: Array[Dictionary] = []
	window.command_requested.connect(func(command: Dictionary) -> void: commands.append(command))
	var confirmed: Array[Dictionary] = []
	window.finished_confirmed.connect(func(finished: Dictionary) -> void: confirmed.append(finished))

	_check(not window.is_open(), "окно закрыто по умолчанию")
	window.open(states["draft"], samples["inventory"])
	await get_tree().process_frame
	_check(window.is_open() and window._draft_root.visible, "при наборе колоды открывается выбор стартовых карт")
	_check(window._draft_grid.get_child_count() == states["draft"]["draft_cards"].size(), "в выборе столько карт, сколько в таблице")
	window._draft_grid.get_child(0).pressed.emit()
	_check(commands.size() == 1 and commands[0]["type"] == "draft", "нажатие на карту отправляет draft")
	_check(window.is_busy(), "во время запроса окно занято")
	window._on_choice_pressed("draft", "other")
	_check(commands.size() == 1, "пока запрос в пути, второй клик не отправляет команду")
	window.receive_response({"state": battle, "notice": "", "log": []})
	_check(not window.is_busy() and not window._draft_root.visible, "после ответа выбор стартовых карт закрыт")
	_check(window._banner_title.text.begins_with("БОЙ: Тест против Кобольд"), "баннер заполнен из ответа сервера")
	_check(window._board.size.x > 0.0 and window._tile_size > 4.0, "доска получила размер и клетки видны")

	_check(window._hand_row.get_child_count() == 0, "рука скрыта, пока не выбран режим карт")
	window._on_button_pressed("cards")
	_check(window._hand_row.get_child_count() == battle["hand"].size(), "в режиме карт видна вся рука")
	window._on_hand_pressed(0)
	_check(window._selected_index == 0, "первый клик выбирает карту")
	window._on_hand_pressed(0)
	_check(window._targeting, "второй клик по той же карте начинает выбор цели")
	window._on_board_click(_tile_pixel(battle, RULES.tile_from_array(RULES.unit_by_id(battle["units"], "player")["position"]), window))
	_check(commands.size() == 2 and commands[1] == {"type": "play", "card_index": 0, "target": "player"}, "карта «себе» отправляет play с целью player")
	window.receive_response({"state": battle, "notice": "Карта разыграна", "log": ["Тест разыгрывает карту"]})
	_check(window._notice_label.text == "Карта разыграна", "заметка сервера показана в окне")

	window.apply_state(attack)
	_ensure_mode(window, "cards")
	window._on_hand_pressed(4)
	window._on_hand_pressed(4)
	var enemy_card: Dictionary = attack["hand"][4]
	var aim_tile := RULES.tile_from_array(enemy_card["preview"]["aim_tiles"][0])
	var highlights: Dictionary = window._highlights(RULES.tile_set(attack["tiles"]))
	_check(highlights["aim"].size() == enemy_card["preview"]["aim_tiles"].size(), "атака подсвечивает все гексы прицела")
	window._on_board_click(_tile_pixel(attack, aim_tile, window))
	_check(commands.size() == 3 and commands[2] == {"type": "play", "card_index": 4, "aim_tile": RULES.tile_to_array(aim_tile)}, "клик по гексу прицела отправляет aim_tile")
	window.receive_response({"state": attack, "notice": "", "log": []})

	window.apply_state(attack)
	_ensure_mode(window, "cards")
	window._on_hand_pressed(4)
	window._on_hand_pressed(4)
	var far_tile := RULES.tile_from_array(attack["tiles"][0])
	window._click_target(far_tile, RULES.unit_by_id(attack["units"], "enemy"))
	_check(commands.size() == 4 and commands[3]["target"] == "enemy" and not commands[3].has("aim_tile"), "удар по врагу вне прицела уходит по его id")
	window.receive_response({"state": attack, "notice": "", "log": []})

	window.apply_state(battle)
	_ensure_mode(window, "move")
	_check(window._mode == "move" and window._buttons["move"].modulate == Color(1.0, 0.85, 0.45), "кнопка хода подсвечена в режиме хода")
	var reach_tile := RULES.tile_from_array(battle["reachable"][0])
	window._on_board_click(_tile_pixel(battle, reach_tile, window))
	_check(commands.size() == 5 and commands[4] == {"type": "move", "tile": RULES.tile_to_array(reach_tile)}, "клик по досягаемой клетке отправляет move")
	var far_move := RULES.tile_from_array(battle["tiles"][0])
	window.receive_response({"state": battle, "notice": "", "log": []})
	_ensure_mode(window, "move")
	window._on_board_click(_tile_pixel(battle, far_move, window))
	_check(commands.size() == 5 and window._notice_label.text.begins_with("Сюда не дойти"), "недосягаемая клетка не отправляет команду и объясняет почему")
	window.receive_response({"state": battle, "notice": "", "log": []})

	var moved_state := battle.duplicate(true)
	moved_state["can_move"] = false
	moved_state["moved"] = true
	moved_state["reachable"] = []
	window.apply_state(moved_state)
	_check(window._mode == "" and window._buttons["move"].disabled, "после хода кнопка «ПОХОДИТЬ» недоступна")

	window._on_button_pressed("end")
	_check(commands[-1] == {"type": "end_turn"}, "кнопка завершения хода отправляет end_turn")
	window.receive_response({"state": battle, "notice": "", "log": []})

	window._on_button_pressed("teleport")
	_check(window._teleport_root.visible, "телепорт открывает подтверждение")
	window._on_teleport_cancel()
	_check(not window._teleport_root.visible and commands.size() == 6, "отмена телепорта ничего не отправляет")
	window._on_button_pressed("teleport")
	window._on_teleport_confirm()
	_check(commands[-1] == {"type": "teleport"}, "подтверждение телепорта отправляет teleport")
	window.receive_response({"state": battle, "notice": "", "log": []})

	window._on_button_pressed("inventory")
	_check(window._items_root.visible and window._items_list.item_count == 3, "инвентарь показывает три предмета для боя")
	window._items_list.select(0)
	window._on_items_use()
	_check(commands[-1] == {"type": "item", "item_id": 4}, "предмет 4 отправляет item с его id")
	window.receive_response({"state": battle, "notice": "Восстановлено 20 здоровья", "log": []})
	_check(window._inventory[0]["quantity"] == 1, "после успешного предмета количество уменьшается")

	window._on_button_pressed("inventory")
	window._items_list.select(2)
	window._on_items_use()
	_check(window._pending_item == 6 and commands.size() == 8, "кинжал ждёт выбора врага и не уходит сразу")
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	window._input(escape)
	_check(window._pending_item == 6, "Esc не отменяет выбор цели кинжала: клавиша уходит в меню выхода")
	var cancel := InputEventKey.new()
	cancel.keycode = KEY_S
	cancel.pressed = true
	window._input(cancel)
	_check(window._pending_item == 0 and window._notice_label.text == "Выбор цели для предмета отменён", "S отменяет выбор цели кинжала")
	window._on_button_pressed("inventory")
	window._items_list.select(2)
	window._on_items_use()
	window._on_board_click(_tile_pixel(battle, RULES.tile_from_array(RULES.unit_by_id(battle["units"], "enemy")["position"]), window))
	_check(commands[-1] == {"type": "item", "item_id": 6, "target": "enemy"}, "кинжал по врагу отправляет item с целью")
	window.receive_response({"state": battle, "notice": "", "log": []})

	window._on_button_pressed("burn")
	_check(window._burn_mode and window._hand_row.get_child_count() == battle["hand"].size(), "сжигание показывает руку")
	window._on_hand_pressed(0)
	window._on_burn_pressed()
	_check(commands[-1] == {"type": "burn", "card_index": 0}, "сжигание отправляет burn с индексом карты")
	window.receive_response({"state": battle, "notice": "Карта сожжена", "log": []})
	_check(not window._burn_mode, "после сжигания режим сбрасывается")

	var before := commands.size()
	window._on_button_pressed("end")
	_check(commands.size() == before + 1 or window.is_busy(), "кнопка конца хода работает после ответа")
	window.receive_error("Сейчас ход противника")
	_check(not window.is_busy() and window._notice_label.text == "Сейчас ход противника", "ошибка сервера показана и разблокирует окно")
	window.receive_response({"state": battle, "notice": "", "log": []})

	var finished: Dictionary = samples["finished"].duplicate(true)
	finished["xp_awarded"] = 5
	window.receive_response({"state": states["result"], "notice": "", "log": [], "finished": finished})
	_check(window._result_root.visible and window._result_title.text == "ТЕЛЕПОРТ", "итог боя показывает заголовок результата")
	_check(window._result_rewards.text.contains("+5"), "итог показывает опыт за противников")
	window._on_result_continue()
	_check(confirmed.size() == 1 and confirmed[0]["result"] == "teleport", "кнопка «ПРОДОЛЖИТЬ» передаёт итог миру")
	window.close()
	_check(not window.is_open(), "окно закрывается")
	host.queue_free()
