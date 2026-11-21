extends Node

# Интеграция арены с миром Deck: метки на карте, запуск боя у противника, ошибки сети и итог боя.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const QUEST_LOG := preload("res://scripts/deck_quest_log.gd")
const SAMPLES_PATH := "res://tests/deck_arena_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		await _check_world(samples)
	else:
		_check(false, "файл эталона арены читается")
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_arena_world_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _find_button_text(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button_text(child, text)
		if found != null:
			return found
	return null


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _encounters(alive: Dictionary) -> Dictionary:
	var list: Array = []
	for source in ["kobold", "kobold_camp", "kobold_camp_2", "ancient_ent", "skeleton", "necromancer"]:
		list.append({"source": source, "alive": bool(alive.get(source, true)), "respawn_in": null})
	return {"encounters": list}


func _character(x_tile: int, y_tile: int, hp: int) -> Dictionary:
	return {
		"id": 42,
		"name": "Тест",
		"type": "warrior",
		"level": 5,
		"hp": hp,
		"max_hp": 142,
		"mp": 20,
		"max_mp": 20,
		"zone": "world_map",
		"position_x": float(x_tile * 48 + 24),
		"position_y": float(y_tile * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _finished(result: String, source: String, enemy_count: int, character: Dictionary) -> Dictionary:
	return {
		"result": result,
		"encounter_id": source,
		"defeated_npc_types": [],
		"enemy_count": enemy_count,
		"player_hp": 50,
		"player_mp": 10,
		"xp_awarded": 0,
		"xp_error": null,
		"save_error": null,
		"character": character,
	}


func _check_world(samples: Dictionary) -> void:
	var states: Dictionary = samples["states"]
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = _character(53, 12, 60)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var arena_window = deck._arena_window

	_check(not arena_window.is_open() and not deck._window_open(), "без боя окно арены закрыто и мир свободен")

	deck._map_position = Vector2i(53, 12)
	deck._render_location()
	var marker := _find_button_text(deck, "K")
	_check(marker != null and marker.tooltip_text == "Кобольд — бой на арене", "кобольд отмечен буквой K рядом с игроком")

	deck._apply_arena_status({"encounters": [
		{"source": "kobold", "alive": false, "respawn_in": 45},
		{"source": "kobold_camp", "alive": true, "respawn_in": null},
		{"source": "kobold_camp_2", "alive": true, "respawn_in": null},
		{"source": "ancient_ent", "alive": true, "respawn_in": null},
		{"source": "skeleton", "alive": true, "respawn_in": null},
		{"source": "necromancer", "alive": true, "respawn_in": null},
	]})
	_check(deck._arena_source_at(Vector2i(54, 12)).is_empty(), "погибший кобольд не отмечен на карте")
	_check(_find_button_text(deck, "K") == null, "погибший кобольд не виден на карте")

	deck._apply_arena_status(_encounters({}))
	deck._map_position = Vector2i(52, 12)
	_check(not deck._check_arena_encounter(), "на расстоянии два шага от кобольда бой не начинается")
	deck._map_position = Vector2i(53, 12)
	_check(deck._check_arena_encounter(), "подход вплотную к кобольду начинает бой")
	_check(deck._arena_pending_source == "kobold", "ожидание боя помнит противника")
	_check(not deck._check_arena_encounter(), "пока бой ждёт ответа, второй запуск не делается")
	await _wait_idle(deck)
	_check(deck._arena_pending_source.is_empty(), "сбой запуска снимает ожидание боя")
	_check(deck._status.text.begins_with("Не удалось начать бой на арене: "), "сбой запуска объяснён в статусе")

	deck._arena_pending_source = "kobold"
	deck._handle_arena_payload("arena_start", {"arena": states["battle"]})
	_check(arena_window.is_open() and deck._arena_session_id == str(states["battle"]["session_id"]), "ответ на старт открывает окно боя")
	_check(deck._window_open() and deck._arena_pending_source.is_empty(), "открытый бой блокирует мир")
	_check(not deck._check_arena_encounter(), "во время боя новая встреча не запускается")
	await _wait_idle(deck)
	_check(arena_window.is_open(), "запрос инвентаря не закрывает бой")

	arena_window._send({"type": "end_turn"})
	_check(arena_window.is_busy(), "команда из окна занимает окно до ответа")
	await _wait_idle(deck)
	_check(not arena_window.is_busy() and arena_window.is_open(), "сбой сети разблокирует окно боя")
	_check(arena_window._notice_label.text.length() > 0, "сбой сети показан в окне боя")

	deck._handle_arena_payload("arena_cmd_99", {"arena": {"notice": "Ход завершён", "log": ["Тест"], "state": states["battle"], "finished": null}})
	_check(arena_window._notice_label.text == "Ход завершён" and not arena_window.is_busy(), "успешный ответ сервера показан в окне")

	deck._quest_log.accept("kill_kobold")
	var win := _finished("win", "kobold", 1, _character(53, 12, 50))
	deck._handle_arena_payload("arena_cmd_100", {"arena": {"notice": "", "log": [], "state": states["result"], "finished": win}})
	_check(deck._quest_log.status("kill_kobold") == "completed", "победа засчитывает задание на кобольда")
	_check(int(GameSession.character["hp"]) == 50, "здоровье после боя берётся с сервера")
	_check(arena_window._result_root.visible and arena_window._result_title.text == "ПОБЕДА!", "итог победы показан в окне")
	_check(deck._map_position == Vector2i(53, 12), "победа оставляет игрока на месте")

	deck._on_arena_finish_confirmed({})
	await _wait_idle(deck)
	_check(not arena_window.is_open() and deck._arena_session_id.is_empty(), "«ПРОДОЛЖИТЬ» закрывает бой")

	deck._quest_log.accept("kill_skeleton")
	var skeleton := _finished("win", "skeleton", 1, _character(53, 12, 50))
	var skeleton_result: Dictionary = deck._apply_arena_finish(skeleton)
	_check(deck._quest_log.status("kill_skeleton") == "completed", "победа над скелетом засчитывает задание")
	_check(skeleton_result["notes"] == ["Задание «Убить скелета» выполнено — сдайте в гильдии"], "выполненное задание объявлено подсказкой")

	deck._quest_log.accept("kill_3_kobolds")
	var camp := _finished("win", "kobold_camp", 3, _character(53, 12, 50))
	var camp_result: Dictionary = deck._apply_arena_finish(camp)
	_check(deck._quest_log.status("kill_3_kobolds") == "completed", "лагерь из трёх кобольдов засчитывает три убийства")
	_check(camp_result["notes"] == ["Задание «Убить 3 кобольдов» выполнено — сдайте в гильдии"], "задание на лагерь объявлено подсказкой")

	var lost := _finished("loss", "kobold", 1, _character(12, 36, 142))
	var lost_result: Dictionary = deck._apply_arena_finish(lost)
	_check(deck._map_position == Vector2i(12, 36), "поражение переносит игрока к кристаллу")
	_check(lost_result["notes"].is_empty(), "поражение не даёт заданий")

	var teleport := _finished("teleport", "skeleton", 1, _character(12, 36, 50))
	var teleport_result: Dictionary = deck._apply_arena_finish(teleport)
	_check(teleport_result["notes"].is_empty() and deck._map_position == Vector2i(12, 36), "телепорт тоже переносит к кристаллу без заданий")

	deck._arena_window.close()
	deck._arena_session_id = ""
	deck._apply_arena_status(_encounters({}))
	_check(deck._arena_source_at(Vector2i(54, 12)) == "kobold", "после сервера со свежим статусом живой кобольд снова на карте")

	GameSession.clear()
	deck.queue_free()
	await get_tree().process_frame
