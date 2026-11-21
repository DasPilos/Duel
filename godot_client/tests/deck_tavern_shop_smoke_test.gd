extends Node

const WINDOW_SCRIPT := preload("res://scripts/deck_tavern_shop_window.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_tavern_shop_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const BARTENDER_BUTTON := "Хозяин трактира — напитки"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_texts(samples["texts"])
		await _check_window(samples)
		await _check_world(samples)
	else:
		_check(false, "файл эталона лавки читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_tavern_shop_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_texts(texts: Dictionary) -> void:
	_check(WINDOW_SCRIPT.WINDOW_TITLE == texts["bartender"], "заголовок лавки — имя хозяина из tavern_scene.py")
	_check(WINDOW_SCRIPT.TAB_DRINKS == texts["tab_drinks"], "вкладка «НАПИТКИ» как в Python")
	_check(WINDOW_SCRIPT.TAB_SELL == texts["tab_sell"], "вкладка «СКУПКА» как в Python")
	_check(WINDOW_SCRIPT.TITLE_DRINKS == texts["drinks_title"], "заголовок списка «Напитки бара» как в Python")
	_check(WINDOW_SCRIPT.TITLE_SELL == texts["sell_title"], "заголовок «Скупки» как в Python")
	_check(WINDOW_SCRIPT.SELL_HINT == texts["sell_hint"], "подсказка «Скупки» как в Python")
	_check(WINDOW_SCRIPT.PRICE_PLACEHOLDER == texts["price_placeholder"], "вместо цены «временно недоступно», как в Python")
	_check(WINDOW_SCRIPT.PURCHASE_DISABLED == texts["purchase_disabled"], "сообщение об отключённой покупке как в Python")
	_check(WINDOW_SCRIPT.CLOSE_TEXT == texts["close"], "кнопка «ЗАКРЫТЬ» как в Python")
	_check(BARTENDER_BUTTON == texts["bartender"] + " — напитки", "кнопка входа названа по хозяину трактира")


func _check_window(samples: Dictionary) -> void:
	var texts: Dictionary = samples["texts"]
	var drinks: Array = samples["drinks"]
	var shop = WINDOW_SCRIPT.new()
	shop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(shop)
	await get_tree().process_frame
	_check(not shop.is_open(), "лавка закрыта по умолчанию")

	shop.open()
	_check(shop.is_open(), "лавка открывается")
	_check(shop._message.text == WINDOW_SCRIPT.DRINKS_LOADING, "до ответа сервера показано «Загружаем напитки…»")
	_check(shop._drinks_box.visible and not shop._sell_box.visible, "по умолчанию открыта вкладка «НАПИТКИ»")
	_check(_has_label(shop._drinks_box, texts["drinks_title"]), "в списке есть заголовок «Напитки бара»")

	shop.set_drinks(drinks)
	var first: Dictionary = drinks[0]
	_check(shop._list.item_count == drinks.size(), "список показывает напитки сервера")
	_check(shop._list.get_item_text(0) == "%s — %s" % [first["name"], texts["price_placeholder"]], "у напитка вместо цены «временно недоступно»")
	_check(shop._list.get_item_tooltip(0) == first["description"], "описание напитка показано подсказкой при наведении")
	_check(shop._message.text.is_empty(), "после загрузки сообщение очищено")

	shop.set_drinks([])
	_check(shop._list.item_count == 0 and shop._message.text == WINDOW_SCRIPT.DRINKS_EMPTY, "пустой ответ: «В баре пока нет напитков.»")

	var second := {"name": "Тестовый напиток", "description": "Нужен только для проверки строк списка"}
	shop.set_drinks([first, second])
	shop._list.item_clicked.emit(1, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	_check(shop._message.text.is_empty(), "одиночный клик ничего не сообщает")
	shop._list.item_clicked.emit(0, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	_check(shop._message.text.is_empty(), "клик по другому напитку не считается двойным")
	# В headless-режиме пауза таймера не совпадает с Time.get_ticks_msec(), поэтому отметку прошлого клика сдвигаем на 400 мс.
	shop._last_click_msec = Time.get_ticks_msec() - 400
	shop._list.item_clicked.emit(0, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	_check(shop._message.text.is_empty(), "второй клик позже 300 мс не считается двойным")
	shop._list.item_clicked.emit(0, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	_check(shop._message.text == texts["purchase_disabled"], "двойной клик показывает, что покупки отключены")

	shop.show_message("")
	shop._list.item_clicked.emit(1, Vector2.ZERO, MOUSE_BUTTON_RIGHT)
	shop._list.item_clicked.emit(1, Vector2.ZERO, MOUSE_BUTTON_RIGHT)
	_check(shop._message.text.is_empty(), "правый клик не считается покупкой")

	shop.show_message("Напитки не загружены: тест", true)
	_check(shop._message.text == "Напитки не загружены: тест", "сообщение об ошибке показано в лавке")

	shop._sell_tab.button_pressed = true
	_check(shop._sell_box.visible and not shop._drinks_box.visible, "вкладка «СКУПКА» показывает заглушку")
	_check(_has_label(shop._sell_box, texts["sell_title"]) and _has_label(shop._sell_box, texts["sell_hint"]), "«Скупка» показывает заголовок и подсказку, как в Python")
	shop._drinks_tab.button_pressed = true
	_check(shop._drinks_box.visible and not shop._sell_box.visible, "вкладка «НАПИТКИ» возвращается")

	_find_button_text(shop, texts["close"]).pressed.emit()
	_check(not shop.is_open(), "«ЗАКРЫТЬ» закрывает лавку")
	shop.open()
	_find_button_text(shop, "×").pressed.emit()
	_check(not shop.is_open(), "кнопка × закрывает лавку")
	shop.open()
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	shop._on_backdrop_input(click)
	_check(not shop.is_open(), "щелчок вне окна закрывает лавку")
	shop.open()
	shop._list.grab_focus()
	await get_tree().process_frame
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	await get_tree().process_frame
	_check(shop.is_open(), "Esc не закрывает лавку даже с фокусом в списке: клавиша уходит в меню выхода")

	shop.open()
	await get_tree().process_frame
	await get_tree().process_frame
	var screen := get_viewport().get_visible_rect().size
	_check(shop._window.size.x <= screen.x and shop._window.size.y <= screen.y, "лавка помещается в экран")
	shop.queue_free()
	await get_tree().process_frame


func _check_world(samples: Dictionary) -> void:
	var texts: Dictionary = samples["texts"]
	var drinks: Array = samples["drinks"]
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {"id": 42, "name": "Тест", "coins": 100, "type": "mage", "level": 5, "position_x": 100.0, "talents": {}}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var shop = deck._tavern_shop_window

	_check(_find_button_text(deck, BARTENDER_BUTTON) == null, "на карте мира кнопки хозяина нет")
	deck._enter_location("tavern")
	await _wait_idle(deck)
	_check(_find_button_text(deck, BARTENDER_BUTTON) != null, "в таверне есть вход к хозяину трактира")
	_find_button_text(deck, BARTENDER_BUTTON).pressed.emit()
	_check(shop.is_open(), "вход к хозяину открывает лавку")
	_check(deck._pending_action == "tavern_drinks", "напитки запрошены при открытии лавки")
	_check(deck._window_open(), "открытая лавка блокирует мир")
	await _wait_idle(deck)
	_check(shop._message.text.begins_with("Напитки не загружены: "), "ошибка сети показана в лавке")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	_check(shop.is_open() and deck._exit_menu.is_open(), "Esc открывает меню выхода и не закрывает лавку, как в Python")
	deck._exit_menu.close()
	shop.close()

	_find_button_text(deck, BARTENDER_BUTTON).pressed.emit()
	await _wait_idle(deck)
	deck._pending_action = "tavern_drinks"
	deck._on_api_completed(true, {"drinks": drinks})
	_check(shop._list.item_count == drinks.size(), "ответ сервера наполняет список напитков")
	shop._list.item_clicked.emit(0, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	shop._list.item_clicked.emit(0, Vector2.ZERO, MOUSE_BUTTON_LEFT)
	_check(shop._message.text == texts["purchase_disabled"], "двойной клик в мире показывает, что покупки отключены")
	_check(deck._pending_action.is_empty() and deck._queued_requests.is_empty(), "двойной клик не отправляет запросов покупки")

	deck._pending_action = "tavern_drinks"
	deck._on_api_completed(true, {"nope": 1})
	_check(shop._message.text == "Напитки не загружены: неверный ответ сервера", "неверный ответ сервера показан в лавке")

	shop.close()
	deck._pending_action = "checkpoint"
	deck._open_tavern_shop()
	_check(deck._queued_requests.size() == 1 and deck._pending_action == "checkpoint", "открытие лавки ждёт, пока мир освободится")
	shop.close()
	deck._pending_action = ""
	deck._flush_queued_requests()
	_check(deck._pending_action.is_empty() and deck._queued_requests.is_empty(), "закрытая лавка не отправляет отложенный запрос")

	deck._enter_location("world_map")
	await _wait_idle(deck)
	_check(_find_button_text(deck, BARTENDER_BUTTON) == null, "вне таверны кнопки хозяина нет")


func _has_label(node: Node, text: String) -> bool:
	for child in node.get_children():
		if child is Label and child.text == text:
			return true
		if _has_label(child, text):
			return true
	return false


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
