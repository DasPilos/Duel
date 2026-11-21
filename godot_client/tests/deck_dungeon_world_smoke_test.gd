extends Node

# Подземелье в мире Deck: вход у портала, бой в комнатах, торговец, фонтан, сокровище и выход.
# Сеть не используется: запросы мира ждут в очереди (_pending_action занят), ответы подаются вручную.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const RULES := preload("res://scripts/deck_dungeon_rules.gd")
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
	if _checks == 0:
		_check(false, "проверки подземелья выполнены")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_dungeon_world_smoke_test: OK (%d checks)" % _checks)
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


func _queued(deck, action: String) -> Dictionary:
	for item in deck._queued_requests:
		if str(item["action"]) == action:
			return item
	return {}


func _character(coins: int, hp: int) -> Dictionary:
	return {
		"id": 42,
		"name": "Тест",
		"type": "warrior",
		"level": 5,
		"hp": hp,
		"max_hp": 142,
		"mp": 20,
		"max_mp": 20,
		"coins": coins,
		"zone": "world_map",
		"position_x": float(25 * 48 + 24),
		"position_y": float(43 * 48 + 24),
		"position_direction": "s",
		"talents": {},
	}


func _finished(result: String, source: String, character: Dictionary) -> Dictionary:
	return {
		"result": result,
		"encounter_id": source,
		"defeated_npc_types": [],
		"enemy_count": 2,
		"player_hp": 40,
		"player_mp": 5,
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
	GameSession.character = _character(500, 60)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	deck._pending_action = "stub"
	var dungeon = deck._dungeon_view

	deck._map_position = Vector2i(25, 43)
	deck._update_dungeon_gate()
	_check(not deck._dungeon_gate_timer.is_stopped(), "встать на вход запускает таймер входа")
	deck._map_position = Vector2i(20, 43)
	deck._update_dungeon_gate()
	_check(deck._dungeon_gate_timer.is_stopped(), "сойти с входа останавливает таймер")
	deck._map_position = Vector2i(25, 43)
	deck._on_dungeon_gate_timeout()
	_check(deck._dungeon_entering and not _queued(deck, "dungeon_enter").is_empty(), "таймер входа запрашивает подземелье")
	deck._handle_dungeon_payload("dungeon_enter", {})
	_check(deck._in_dungeon and dungeon.is_open() and deck._window_open(), "ответ сервера открывает подземелье и блокирует мир")
	_check(deck._map_position == RULES.APPROACH and not deck._dungeon_entering, "вход сохраняет место у портала")

	deck._on_dungeon_battle_requested(1, Vector2i(71, 39))
	var start := _queued(deck, "arena_start")
	_check(deck._arena_pending_source == "dungeon_room_1" and start["body"]["source"] == "dungeon_room_1", "бой комнаты 1 запрашивается с её именем")
	_check(is_equal_approx(float(start["body"]["position_x"]), float(71 * 48 + 24)), "позиция боя — клетка комнаты, а не портал")
	deck._handle_arena_failure("arena_start", "Подойдите ближе к противнику")
	_check(not dungeon.is_busy() and deck._arena_pending_source.is_empty(), "ошибка старта боя снимает занятость комнаты")

	deck._arena_pending_source = "dungeon_room_1"
	deck._handle_arena_payload("arena_start", {"arena": states["battle"]})
	_check(deck._arena_window.is_open() and not dungeon.visible and dungeon.is_open(), "старт боя комнаты открывает бой и прячет поле")
	var win := _finished("win", "dungeon_room_1", _character(500, 40))
	deck._handle_arena_payload("arena_cmd_1", {"arena": {"notice": "", "log": [], "state": states["result"], "finished": win}})
	_check(dungeon.is_cleared(1), "победа очищает комнату 1")
	deck._on_arena_finish_confirmed({})
	_check(not deck._arena_window.is_open() and dungeon.visible and deck._in_dungeon, "после победы поле снова видно и подземелье продолжается")
	_check(deck._dungeon_battle_outcome.is_empty(), "итог боя сброшен после подтверждения")

	dungeon._open_merchant()
	_check(not _queued(deck, "dungeon_supplies").is_empty() and not _queued(deck, "dungeon_cards").is_empty(), "магазин запрашивает товары и карты")
	deck._handle_dungeon_payload("dungeon_supplies", {"items": [{"item_id": 4, "name": "Зелье", "price": 15}]})
	deck._handle_dungeon_payload("dungeon_cards", {"cards": [{"key": "card_a", "name": "Удар", "price": 100, "available": false}]})
	_check(dungeon._merchant_list.item_count == 2, "магазин показывает товары и карты сервера")
	deck._on_dungeon_merchant_buy("supply", 0)
	var buy := _queued(deck, "dungeon_buy_supply")
	_check(buy["body"]["item_id"] == 4 and buy["body"]["character_id"] == 42, "покупка товара отправляет его id")
	deck._handle_dungeon_failure("dungeon_buy_supply", "Покупка не выполнена: нет места")
	_check(not dungeon.is_busy() and dungeon._panel_message.text == "Покупка не выполнена: нет места", "ошибка покупки показана в магазине")
	deck._on_dungeon_merchant_buy("supply", 0)
	deck._handle_dungeon_payload("dungeon_buy_supply", {"character": {"coins": 485}})
	_check(dungeon._panel_message.text == "Куплено: Зелье" and int(GameSession.character["coins"]) == 485, "покупка списывает монеты персонажа")
	dungeon._on_secondary_pressed()
	_check(dungeon.is_completed(2), "«ЗАКРЫТЬ МАГАЗИН» открывает проход комнаты 2")

	deck._on_dungeon_fountain_requested()
	var fountain := _queued(deck, "dungeon_fountain")
	_check(fountain["method"] == HTTPClient.METHOD_PUT and int(fountain["body"]["hp"]) == 142, "фонтан сохраняет полное здоровье персонажа")
	deck._handle_dungeon_payload("dungeon_fountain", {"character": {"hp": 142, "mp": 20}})
	_check(dungeon.is_completed(4), "фонтан открывает проход комнаты 4")

	deck._on_dungeon_chest_requested("req-1")
	_check(str(_queued(deck, "dungeon_chest")["body"]["request_id"]) == "req-1", "сундук отправляет id запроса")
	deck._handle_dungeon_failure("dungeon_chest", "Сундук не открыт: сеть")
	_check(not dungeon.treasure_opened() and not dungeon.is_busy(), "ошибка сундука не открывает его")
	deck._finish_dungeon_chest({"character": {"coins": 1300}, "rewards": ["830 монет", "1 × Зелье"]})
	_check(dungeon.treasure_opened() and int(GameSession.character["coins"]) == 1300, "сундук выдаёт награды и монеты")

	deck._quest_log.accept("clear_dungeon")
	deck._leave_dungeon("")
	_check(not deck._in_dungeon and not dungeon.is_open(), "выход закрывает подземелье")
	_check(deck._quest_log.status("clear_dungeon") == "completed", "выход с сокровищем засчитывает «Зачистить подземелье»")
	_check(deck._status.text.contains("Зачистить подземелье"), "выполненное задание объявлено в статусе")
	_check(deck._map_position == RULES.APPROACH and not _queued(deck, "dungeon_exit").is_empty(), "выход возвращает ко входу и сообщает серверу")

	deck._handle_dungeon_payload("dungeon_enter", {})
	deck._on_dungeon_battle_requested(1, Vector2i(71, 39))
	deck._arena_pending_source = "dungeon_room_1"
	deck._handle_arena_payload("arena_start", {"arena": states["battle"]})
	var lost := _finished("loss", "dungeon_room_1", _character(500, 142))
	deck._handle_arena_payload("arena_cmd_2", {"arena": {"notice": "", "log": [], "state": states["result"], "finished": lost}})
	deck._on_arena_finish_confirmed({})
	_check(not deck._in_dungeon and not dungeon.is_open(), "поражение выводит из подземелья")
	_check(not dungeon.is_cleared(1) and deck._quest_log.status("clear_dungeon") == "completed", "поражение не очищает комнату и не даёт сокровищ")

	GameSession.clear()
	deck.queue_free()
	await get_tree().process_frame
