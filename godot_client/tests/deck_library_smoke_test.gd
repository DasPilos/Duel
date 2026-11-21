extends Node

const RULES := preload("res://scripts/deck_library_rules.gd")
const WINDOW_SCRIPT := preload("res://scripts/deck_library_window.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_library_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_static_data(samples["categories"])
		_check_items(samples["items"])
		_check_filter()
		await _check_window(samples)
		await _check_world(samples)
	else:
		_check(false, "файл эталона справочника читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_library_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_static_data(categories: Dictionary) -> void:
	for category in ["Существа", "Карты", "Классы", "Эффекты"]:
		var expected: Array = categories[category]
		var actual: Array = RULES.static_entries(category)
		_check(actual.size() == expected.size(), "%s: число записей совпадает с Python (%d)" % [category, expected.size()])
		_check(actual == expected, "%s: тексты совпадают с Python" % category)
	_check(RULES.static_entries("Предметы").is_empty(), "предметы не встроены: их отдаёт сервер")
	_check(RULES.static_entries("Неизвестно").is_empty(), "неизвестная категория пуста")


func _check_items(items: Array) -> void:
	for record in items:
		var item: Dictionary = record["item"]
		var expected: Dictionary = record["entry"]
		var entry := RULES.item_entry(item)
		var label := str(item["name"])
		_check(str(entry["name"]) == str(expected["name"]), "название предмета %s" % label)
		_check(str(entry["description"]) == str(expected["description"]), "описание предмета %s совпадает с Python" % label)


func _check_filter() -> void:
	var creatures: Array = RULES.static_entries("Существа")
	var found := RULES.filter_entries(creatures, "  КОБОЛЬД ")
	_check(not found.is_empty() and str(found[0]["name"]) == "Кобольд", "поиск без учёта регистра и пробелов по краям")
	_check(RULES.filter_entries(creatures, "").size() == creatures.size(), "пустой запрос показывает все записи")
	_check(RULES.filter_entries(creatures, "zzz-нет").is_empty(), "неизвестный запрос ничего не находит")
	_check(RULES.filter_entries(creatures, "призывает волка").size() >= 1, "поиск идёт и по описанию")


func _check_window(samples: Dictionary) -> void:
	var creatures: Array = samples["categories"]["Существа"]
	var cards: Array = samples["categories"]["Карты"]
	var window = WINDOW_SCRIPT.new()
	add_child(window)
	await get_tree().process_frame
	_check(not window.is_open(), "справочник скрыт по умолчанию")
	window.open()
	_check(window.is_open(), "справочник открывается")
	_check(window._items_message == "Загружаем каталог предметов…", "пока каталог предметов грузится, окно это показывает")
	_check(window._list.item_count == creatures.size(), "по умолчанию открыта категория «Существа»")
	_check(window._title.text == creatures[0]["name"], "первая запись выбрана и показана")
	_check(window._description.text == creatures[0]["description"], "описание первой записи совпадает с Python")

	_find_button_text(window, "Карты").button_pressed = true
	_check(window._list.item_count == cards.size(), "категория «Карты» показывает все карты")
	window._list.select(2)
	window._list.item_selected.emit(2)
	_check(window._title.text == cards[2]["name"], "выбор записи в списке показывает её название")
	_check(window._description.text == cards[2]["description"], "выбор записи показывает её описание")

	window._search.text = "огонь"
	window._search.text_changed.emit("огонь")
	var fire_matches: int = RULES.filter_entries(cards, "огонь").size()
	_check(fire_matches > 0 and window._list.item_count == fire_matches, "поиск сужает список карт")
	window._search.text = "zzzz-нет"
	window._search.text_changed.emit("zzzz-нет")
	_check(window._title.text == "Нет записей", "пустой результат поиска называется «Нет записей»")
	_check(window._description.text == "По запросу ничего не найдено.", "пустой результат поиска объясняется")
	window._search.text = ""
	window._search.text_changed.emit("")

	_find_button_text(window, "Предметы").button_pressed = true
	_check(window._description.text == "Загружаем каталог предметов…", "пустой каталог предметов показывает ожидание")
	window.show_items_message("Каталог предметов недоступен: Нет ответа от сервера.")
	_check(window._description.text == "Каталог предметов недоступен: Нет ответа от сервера.", "ошибка каталога показана вместо пустого списка")
	window.set_items(_items_of(samples["items"]))
	_check(window._list.item_count == samples["items"].size(), "каталог предметов показывает записи сервера")
	_check(window._title.text == samples["items"][0]["entry"]["name"], "первый предмет выбран и показан")
	_check(window._items_message.is_empty(), "после загрузки сообщение о каталоге очищено")

	_find_button_text(window, "Эффекты").button_pressed = true
	_check(window._list.item_count == samples["categories"]["Эффекты"].size(), "категория «Эффекты» показывает все эффекты")
	_find_button_text(window, "Существа").button_pressed = true
	_check(window._list.item_count == creatures.size(), "возврат к «Существам» восстанавливает список")

	var screen := get_viewport().get_visible_rect().size
	_check(window._window.size.x <= screen.x and window._window.size.y <= screen.y, "справочник помещается в экран")

	window._search.grab_focus()
	await get_tree().process_frame
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	await get_tree().process_frame
	_check(window.is_open(), "Esc не закрывает справочник даже при фокусе в поле поиска: клавиша уходит в меню выхода")

	window.open()
	_find_button_text(window, "×").pressed.emit()
	_check(not window.is_open(), "кнопка × закрывает справочник")
	window.open()
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	window._on_backdrop_input(click)
	_check(not window.is_open(), "щелчок вне окна закрывает справочник")
	window.queue_free()
	await get_tree().process_frame


func _check_world(samples: Dictionary) -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {"id": 42, "name": "Тест", "coins": 100, "equipment": {"weapon": {"name": "Меч"}}}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var library = deck._library_window

	deck._terrain = {}
	deck._view = "home"
	deck._map_position = Vector2i(18, 41)
	deck._move_world(1, 0)
	_check(library.is_open(), "вход на тайл библиотеки открывает справочник")
	_check(deck._map_position == Vector2i(19, 41), "герой стоит на тайле библиотеки")
	_find_button_text(library, "Предметы").button_pressed = true
	_check(deck._pending_action == "library_items", "каталог предметов запрошен при входе")
	var key := InputEventKey.new()
	key.keycode = KEY_D
	key.pressed = true
	deck._unhandled_input(key)
	_check(deck._map_position == Vector2i(19, 41), "клавиши не двигают фигурку и при открытом справочнике")
	await _wait_idle(deck)
	_check(library._description.text.begins_with("Каталог предметов недоступен"), "ошибка сети показана в справочнике")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	_check(library.is_open() and deck._exit_menu.is_open(), "Esc открывает меню выхода и не закрывает справочник, как в Python")
	deck._exit_menu.close()
	library.close()
	deck._move_world(1, 0)
	_check(not library.is_open(), "переход внутри библиотеки не открывает окно повторно")
	deck._move_world(0, -2)
	_check(not library.is_open(), "выход из библиотеки не открывает окно")
	deck._move_world(-1, 2)
	_check(library.is_open(), "новый вход с улицы снова открывает справочник")
	library.close()

	deck._terrain = {"published": true}
	deck._map_position = Vector2i(18, 41)
	deck._move_world(1, 0)
	_check(not library.is_open(), "на опубликованной карте библиотеки нет")
	deck._terrain = {}

	await _wait_idle(deck)
	deck._pending_action = "social_snapshot"
	deck._map_position = Vector2i(18, 41)
	deck._move_world(1, 0)
	_check(library.is_open() and deck._pending_action == "social_snapshot", "пока идёт другой запрос, каталог не отправляется")
	_check(deck._queued_requests.size() == 1 and deck._queued_requests[0]["action"] == "library_items", "каталог стоит в очереди")
	ApiClient.request_completed.emit(false, "Тестовый ответ")
	await _wait_idle(deck)
	_check(deck._queued_requests.is_empty(), "после ответа очередь пуста")
	_check(library._description.text.begins_with("Каталог предметов недоступен"), "после ответа на прежний запрос каталог запрошен")
	library.close()

	deck._pending_action = "library_items"
	deck._on_api_completed(true, {"wrong": 1})
	library.open()
	deck._pending_action = "library_items"
	deck._on_api_completed(true, {"wrong": 1})
	_check(library._description.text == "Каталог предметов недоступен: неверный ответ сервера", "неверный ответ каталога показан в справочнике")
	deck._pending_action = "library_items"
	deck._on_api_completed(true, {"items": _items_of(samples["items"])})
	_find_button_text(library, "Предметы").button_pressed = true
	_check(library._list.item_count == samples["items"].size(), "ответ сервера наполняет категорию «Предметы»")
	library.close()

	deck._map_position = Vector2i(21, 41)
	deck._render_location()
	_check(_find_button_text(deck._list, "L") != null, "на карте отмечена библиотека буквой L")

	deck.queue_free()
	await get_tree().process_frame


func _items_of(records: Array) -> Array:
	var items: Array = []
	for record in records:
		items.append(record["item"])
	return items


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _find_button_text(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button_text(child, text)
		if found != null:
			return found
	return null


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
