extends Node

# Комната персонажа Колоды в мире: вход открывает вид и грузит экипировку, список мира переезжает в чат комнаты,
# вкладки грузят свои разделы, ошибки сети помечают раздел, дверь ведёт в таверну, инвентарь скрывает комнату.
# Сеть не используется: адрес недоступен, а успешные ответы подаются через _on_api_completed. ApiClient держит один
# запрос, поэтому перед каждым шагом ждём его завершения.
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const FIXTURE := "res://tests/fixtures/deck_backyard/social.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const OLD_ROOM_NOTE := "Комната персонажа. Коллекцию карт и состав колод можно открыть в верхней панели."

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
		print("deck_room_world_smoke_test: OK (%d checks)" % _checks)
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
	var room = deck._room_view
	var chat_box: Control = room.get("_chat_box")

	# Вход: вид показан, чат переехал в него, экипировка запрошена. Запрос уходит после чекпоинта локации,
	# поэтому сначала он в очереди, а после ответа чекпоинта в сети падает: раздел помечается неудачным.
	deck._enter_location("character_room")
	_check(deck._view == "character_room" and room.visible, "вход в комнату показывает вид комнаты")
	_check(deck._list.get_parent() == chat_box, "чат мира переносится в область чата комнаты")
	_check(not _list_texts(deck).has(OLD_ROOM_NOTE), "старая заметка комнаты убрана")
	_check(room.section_state("equipment") == "loading", "вход запрашивает экипировку")
	await _api_idle()
	_check(room.section_state("equipment") == "failed", "ошибка сети помечает экипировку неудачной")
	_check(deck._status.text.begins_with("Экипировка не загружена: "), "ошибка экипировки подписана как в мире")
	_check(_texts(room).has("Не удалось загрузить данные."), "комната показывает ошибку вместо пустой экипировки")

	# Сундуки: первый ответ приходит напрямую, второй запрос ждёт в очереди и падает, когда сеть отвечает.
	_find_button(room, "Сундуки").pressed.emit()
	_check(room.current_tab() == "chests" and room.section_state("chest1") == "loading" and room.section_state("chest2") == "loading", "вкладка сундуков запрашивает оба сундука")
	deck._on_api_completed(true, {"storage": [{"name": "Карта", "quantity": 2}]})
	_check(room.section_state("chest1") == "ready" and _texts(room).has("Карта ×2"), "ответ сундука 1 выводит предметы")
	_check(room.section_state("chest2") == "loading", "сундук 2 ждёт своей очереди")
	await _api_idle()
	_check(room.section_state("chest2") == "failed" and deck._status.text.begins_with("Сундук 2 не загружен: "), "сундук 2 после ошибки сети помечен неудачным")

	# Колоды: ответ сервера выводит колоду в вид.
	_find_button(room, "Колоды").pressed.emit()
	_check(room.section_state("decks") == "loading", "вкладка колод запрашивает колоды")
	deck._on_api_completed(true, {"decks": [{"name": "Огонь", "cards": {"fire": 2}, "created_at": 1700000000.0}]})
	_check(room.section_state("decks") == "ready" and _texts(room).has("Огонь"), "ответ колод выводит колоду")
	await _api_idle()

	# Дверь ведёт в таверну: вид скрыт, список мира возвращается в оболочку.
	_find_button(room, "Вернуться в таверну").pressed.emit()
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	await _api_idle()
	_check(deck._social_location == "tavern" and deck._view == "tavern", "«Вернуться в таверну» ведёт в таверну")
	_check(not room.visible and deck._list.get_parent() == deck._room_list_home, "в таверне вид комнаты скрыт, список вернулся в оболочку")

	# Новый визит: вкладка снова «Экипировка», разделы запрашиваются заново, карточка закрыта, как в Python.
	deck._enter_location("character_room")
	_check(room.current_tab() == "equipment" and room.section_state("equipment") == "loading", "новый визит снова открывает Экипировку и запрашивает её")
	await _api_idle()
	_check(room.section_state("equipment") == "failed", "повторный визит: ошибка экипировки снова помечается")

	# Колоды загружаются, чтобы проверить: возврат из рюкзака не сбрасывает вкладку и данные.
	_find_button(room, "Колоды").pressed.emit()
	deck._on_api_completed(true, {"decks": [{"name": "Огонь", "cards": {"fire": 2}, "created_at": 1700000000.0}]})
	_check(room.section_state("decks") == "ready", "колоды загружены перед открытием рюкзака")
	await _api_idle()

	# «РЮКЗАК» в карточке открывает рюкзак: комната скрыта, карточка остаётся открытой, как в Python.
	_find_button_by_tooltip(room, "Карточка персонажа").pressed.emit()
	_find_button(room, "РЮКЗАК").pressed.emit()
	await get_tree().process_frame
	_check(deck._view == "inventory" and not room.visible, "«РЮКЗАК» в карточке открывает рюкзак и скрывает комнату")
	_check(deck._list.get_parent() == deck._room_list_home, "список рюкзака возвращается в оболочку")
	_check(room.is_profile_open() and room.current_tab() == "decks", "карточка остаётся открытой, вкладка комнаты сохраняется")
	_check(deck._owner_is_open("inventory"), "запрос рюкзака отправляется, пока рюкзак открыт")

	# Ответ рюкзака подаём напрямую, как в других тестах: сеть в этом тесте недоступна.
	deck._on_api_completed(true, {"inventory": [], "carried_weight_kg": 0.0, "capacity": 50})
	_check(_find_button(deck._list, "Назад в игру") != null, "рюкзак показывает «Назад в игру»")
	await _api_idle()

	# «Назад в игру» возвращает в ту же комнату: вкладка, данные и карточка не сбрасываются.
	_find_button(deck._list, "Назад в игру").pressed.emit()
	await _api_idle()
	_check(deck._view == "character_room" and room.visible, "«Назад в игру» возвращает в комнату")
	_check(room.is_profile_open() and room.current_tab() == "decks" and room.section_state("decks") == "ready", "возврат из рюкзака сохраняет карточку, вкладку и данные")
	_check(not deck._owner_is_open("inventory"), "вне рюкзака его запрос в очереди не выполняется")

	# Дверь ведёт в таверну; новый визит закрывает карточку и открывает Экипировку.
	_find_button(room, "Вернуться в таверну").pressed.emit()
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	await _api_idle()
	deck._enter_location("character_room")
	_check(not room.is_profile_open() and room.current_tab() == "equipment", "новый визит закрывает карточку и открывает Экипировку")
	await _api_idle()

	GameSession.clear()
	deck.queue_free()
	await get_tree().process_frame


func _load_fixture() -> Dictionary:
	var file := FileAccess.open(FIXTURE, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}


func _texts(node: Node) -> Array[String]:
	var result: Array[String] = []
	_collect_texts(node, result)
	return result


func _list_texts(deck) -> Array[String]:
	return _texts(deck._list)


func _find_button_by_tooltip(node: Node, tooltip: String) -> Button:
	for child in node.get_children():
		if child is Button and (child as Button).tooltip_text == tooltip:
			return child as Button
		var found := _find_button_by_tooltip(child, tooltip)
		if found != null:
			return found
	return null


func _collect_texts(node: Node, result: Array[String]) -> void:
	if node is Label:
		result.append((node as Label).text)
	elif node is Button:
		result.append((node as Button).text)
	for child in node.get_children():
		_collect_texts(child, result)


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and (child as Button).text == text:
			return child as Button
		var found := _find_button(child, text)
		if found != null:
			return found
	return null
