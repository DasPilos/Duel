extends Node

# Клавиша I в мире Колоды на сцене deck_world.gd: карточка на карте и в таверне, своя карточка в комнате, рюкзак
# скрывает карточку мира, фокус чата и бой её не открывают. Сеть не используется: адрес недоступен, ответы не нужны.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const FIXTURE := "res://tests/fixtures/deck_backyard/social.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_world()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_profile_key_world_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


# ApiClient отклоняет запрос, пока идёт другой, поэтому ждём ответа на каждом шаге.
func _api_idle() -> void:
	var started := Time.get_ticks_msec()
	while ApiClient._busy and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _key(deck, keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	deck._unhandled_input(event)


func _load_fixture() -> Dictionary:
	var file := FileAccess.open(FIXTURE, FileAccess.READ)
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary


func _check_world() -> void:
	var social: Dictionary = _load_fixture()
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = (social["character"] as Dictionary).duplicate(true)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _api_idle()

	deck._enter_location("world_map")
	await _api_idle()
	_key(deck, KEY_I)
	_check(deck._profile_overlay.is_open() and deck._profile_host.visible, "на карте I открывает карточку мира")
	_key(deck, KEY_I)
	_check(not deck._profile_overlay.is_open(), "повторная I закрывает карточку на карте")
	_key(deck, KEY_I)
	_check(deck._profile_overlay.is_open(), "I снова открывает карточку на карте")
	deck._enter_location("tavern")
	await _api_idle()
	_check(not deck._profile_overlay.is_open(), "новый визит в таверну закрывает карточку мира")
	_key(deck, KEY_I)
	_check(deck._profile_overlay.is_open(), "в таверне I открывает карточку")

	deck._show_inventory()
	await _api_idle()
	await get_tree().process_frame
	_check(deck._profile_overlay.is_open() and not deck._profile_host.visible, "рюкзак скрывает карточку мира, но не закрывает её")
	_key(deck, KEY_I)
	_check(deck._view == "tavern" and deck._profile_overlay.is_open() and deck._profile_host.visible, "I закрывает рюкзак и возвращает открытую карточку")
	await _api_idle()

	if deck._chat_input != null:
		deck._chat_input.grab_focus()
		await get_tree().process_frame
		_key(deck, KEY_I)
		_check(deck._profile_overlay.is_open(), "фокус в поле чата: I не закрывает карточку")
		deck._chat_input.release_focus()
		await get_tree().process_frame
	else:
		_check(false, "в таверне есть поле чата для проверки фокуса")

	deck._view = "battle"
	_key(deck, KEY_I)
	_check(deck._profile_overlay.is_open(), "в бою I не переключает карточку")
	await get_tree().process_frame
	_check(not deck._profile_overlay.is_open(), "бой закрывает карточку мира")
	_key(deck, KEY_I)
	_check(not deck._profile_overlay.is_open(), "в бою I не открывает карточку")
	deck._view = "tavern"

	var saved_character: Dictionary = GameSession.character
	GameSession.character = {}
	_key(deck, KEY_I)
	_check(not deck._profile_overlay.is_open(), "без персонажа I ничего не открывает")
	GameSession.character = saved_character

	deck._enter_location("character_room")
	await _api_idle()
	_key(deck, KEY_I)
	_check(deck._room_view.is_profile_open() and not deck._profile_overlay.is_open(), "в комнате I открывает карточку комнаты")
	_key(deck, KEY_I)
	_check(not deck._room_view.is_profile_open(), "в комнате повторная I закрывает карточку")

	GameSession.character.erase("equipment")
	_key(deck, KEY_I)
	for step in 4:
		await _api_idle()
	_check(GameSession.character.has("equipment"), "открытие карточки без экипировки запрашивает её и при ошибке ставит пустые слоты")

	deck.queue_free()
	await get_tree().process_frame
