extends Node

# Стенка на стенку в мире Deck: кнопка заднего двора, окно сбора, ошибки запросов и автостарт готового боя.
# Сеть не используется: адрес недоступен, ответы подаются вручную через _on_api_completed.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RULES := preload("res://scripts/deck_group_battle_rules.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_world()
	GameSession.clear()
	if _checks == 0:
		_check(false, "проверки стенки на стенку выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_group_battle_world_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _member(character_id: int) -> Dictionary:
	return {"id": character_id, "name": "Боец %d" % character_id}


func _ready_offer(offer_id: String) -> Dictionary:
	var team_a := [_member(42), _member(43), _member(44)]
	var team_b := [_member(45), _member(46), _member(47)]
	return {
		"id": offer_id,
		"sender_id": 42,
		"sender": "Тест",
		"status": "ready",
		"max_participants": 6,
		"ttl": 120,
		"created_at": 1000.0,
		"participants": team_a + team_b,
		"teams": [team_a, team_b],
	}


func _waiting_offer() -> Dictionary:
	return {
		"id": "x1",
		"sender_id": 50,
		"sender": "Другой",
		"status": "waiting",
		"max_participants": 6,
		"ttl": 120,
		"created_at": Time.get_unix_time_from_system(),
		"participants": [_member(50)],
	}


func _check_world() -> void:
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
		"mp": 20,
		"max_mp": 20,
		"coins": 500,
		"zone": "backyard",
		"position_x": float(25 * 48 + 24),
		"position_y": float(43 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	deck._pending_action = "stub"
	var window = deck._group_battle_window

	deck._view = "backyard"
	deck._social_location = "backyard"
	deck._social_data = {"group_offers": [_waiting_offer()]}
	deck._render_social()
	var has_button := false
	for child in deck._list.get_children():
		var button := child as Button
		if button != null and button.text.begins_with("Стенка на стенку"):
			has_button = true
	_check(has_button, "на заднем дворе есть кнопка «Стенка на стенку»")

	deck._open_group_battle_window()
	_check(window.is_open() and deck._window_open(), "кнопка открывает окно и блокирует ходьбу мира")
	_check(window._join_buttons.has("x1") and not window._join_buttons["x1"].disabled, "в окне показан чужой сбор с местами")

	deck._create_group_battle(7, 120)
	_check(window._message.text == RULES.CHOICE_REQUIRED, "некорректный сбор не отправляется")
	deck._create_group_battle(8, 600)
	_check(window._message.text == "Подождите завершения текущего запроса.", "параллельный запрос сбора не отправляется")

	deck._checkpoint_pending = false
	deck._pending_action = "join_group"
	deck._on_api_completed(false, "Заявка уже закрыта")
	_check(window._message.text == "Не удалось вступить в сбор: Заявка уже закрыта", "ошибка вступления видна в окне")
	_check(not window._join_buttons["x1"].disabled and deck._pending_action.is_empty(), "после ошибки кнопки снова доступны")

	deck._pending_action = ""
	deck._checkpoint_pending = false
	deck._social_data = {"group_offers": [_ready_offer("c1")]}
	var started: bool = deck._maybe_start_ready_group_battle()
	_check(started and deck._group_started_offer_id == "c1", "готовый сбор запускает свой бой")
	_check(not window.is_open(), "старт боя закрывает окно сбора")
	_check(deck._pending_action == "battle_start", "старт боя отправляет запрос боя")
	await _wait_idle(deck)
	_check(not deck._maybe_start_ready_group_battle(), "тот же сбор повторно не запускается")

	deck._pending_action = "social_snapshot"
	deck._on_api_completed(true, {
		"group_offers": [_ready_offer("c2")],
		"occupants": [],
		"messages": [],
		"offers": [],
		"my_application": null,
	})
	_check(deck._group_started_offer_id == "c2" and deck._pending_action == "battle_start", "снимок с готовым сбором запускает бой")
	await _wait_idle(deck)

	deck._pending_action = "stub"
	deck._open_group_battle_window()
	_check(window.is_open(), "окно сбора открывается повторно")
	deck._enter_location("tavern")
	_check(not window.is_open(), "смена локации закрывает окно сбора")

	GameSession.clear()
	deck.queue_free()
	await get_tree().process_frame
