extends Node

const WINDOW_SCRIPT := preload("res://scripts/deck_supplies_shop_window.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_supplies_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		await _check_window(samples["items"])
		await _check_world(samples["items"])
	else:
		_check(false, "файл эталона припасов читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_supplies_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_window(items: Array) -> void:
	var window = WINDOW_SCRIPT.new()
	var buys: Array = []
	window.buy_requested.connect(func(item_id: int, item_name: String) -> void: buys.append([item_id, item_name]))
	add_child(window)
	await get_tree().process_frame
	_check(not window.is_open(), "окно припасов скрыто по умолчанию")
	window.open(100)
	_check(window.is_open(), "окно припасов открывается сразу")
	_check(window._balance.text == "У вас: 100 монет", "баланс показан при открытии")
	_check(window._message.text == "Загружаем ассортимент…", "пока каталог грузится, окно показывает ожидание")
	_check(window._rows.get_child_count() == 0, "до загрузки список товаров пуст")
	_find_button_text(window, "КУПИТЬ").pressed.emit()
	_check(window._message.text == "Товары не загружены", "покупка без загруженных товаров сообщает об этом")
	_check(buys.is_empty(), "без товаров покупка не отправляется")

	window.set_items(items)
	_check(window._rows.get_child_count() == 4, "каталог показывает четыре товара")
	var first_line: HBoxContainer = window._rows.get_child(0)
	var first_row: Button = first_line.get_child(0)
	var first_price: Label = first_line.get_child(1)
	_check(first_row.text == "Зелье восстановления здоровья\nВосстанавливает 20 HP в бою", "название и описание товара")
	_check(first_price.text == "15 монет", "цена товара выводится в монетах")
	_check(window._rows.get_child(2).get_child(1).text == "5 монет", "дешёвый товар выводит цену как в Python")
	_check(window._rows.get_child(3).get_child(1).text == "60 монет", "свиток выводит цену 60 монет")
	_check(window._message.text == "", "после загрузки сообщение очищено")

	window._rows.get_child(1).get_child(0).button_pressed = true
	_check(window._selected_index == 1, "выбор строки меняет товар")
	_find_button_text(window, "КУПИТЬ").pressed.emit()
	_check(buys == [[5, "Зелье восстановления маны"]], "покупка передаёт id и название выбранного товара")
	window.show_message("Куплено: Зелье восстановления маны")
	window._rows.get_child(2).get_child(0).button_pressed = true
	_check(window._message.text == "", "выбор строки сбрасывает сообщение")

	window.show_message("Не удалось купить товар: Недостаточно денег", true)
	_check(window._message.get_theme_color("font_color") == Color8(255, 150, 140), "ошибка покупки выводится красным")
	window.set_balance(85)
	_check(window._balance.text == "У вас: 85 монет", "баланс обновляется")
	window.set_items([items[0]])
	_check(window._selected_index == 0, "выбор ограничен длиной нового каталога")

	var screen := get_viewport().get_visible_rect().size
	_check(window._window.size.x <= screen.x and window._window.size.y <= screen.y, "окно припасов помещается в экран")

	_check(window.is_open(), "Esc больше не закрывает окно припасов: клавиша уходит в меню выхода")
	window.open(100)
	_find_button_text(window, "×").pressed.emit()
	_check(not window.is_open(), "кнопка × закрывает окно припасов")
	window.open(100)
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	window._on_backdrop_input(click)
	_check(not window.is_open(), "щелчок вне окна закрывает окно припасов")
	window.queue_free()
	await get_tree().process_frame


func _check_world(items: Array) -> void:
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
	var shop = deck._supplies_shop_window

	deck._terrain = {}
	deck._view = "home"
	deck._map_position = Vector2i(13, 27)
	deck._move_world(1, 0)
	_check(shop.is_open(), "вход на тайл магазина припасов открывает окно")
	_check(deck._map_position == Vector2i(14, 27), "герой стоит на тайле магазина")
	_check(shop._balance.text == "У вас: 100 монет", "окно показывает баланс персонажа")
	_check(shop._message.text == "Загружаем ассортимент…", "каталог запрашивается при входе")
	_check(deck._pending_action == "supplies_catalog", "запрос каталога отправлен")
	var key := InputEventKey.new()
	key.keycode = KEY_D
	key.pressed = true
	deck._unhandled_input(key)
	_check(deck._map_position == Vector2i(14, 27), "клавиши не двигают фигурку и при открытом окне")
	await _wait_idle(deck)
	_check(shop._message.text.begins_with("Не удалось загрузить ассортимент"), "ошибка каталога показана в окне")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	deck._unhandled_input(escape)
	_check(shop.is_open() and deck._exit_menu.is_open(), "Esc открывает меню выхода и не закрывает магазин, как в Python")
	deck._exit_menu.close()
	shop.close()
	deck._move_world(1, 0)
	_check(not shop.is_open(), "переход внутри магазина не открывает окно повторно")
	deck._move_world(-3, 0)
	_check(not shop.is_open(), "выход из магазина не открывает окно")
	deck._move_world(2, 0)
	_check(shop.is_open(), "новый вход с улицы снова открывает окно")
	await _wait_idle(deck)
	shop.close()

	deck._terrain = {"published": true}
	deck._map_position = Vector2i(13, 27)
	deck._move_world(1, 0)
	_check(not shop.is_open(), "на опубликованной карте магазина припасов нет")
	deck._terrain = {}

	await _wait_idle(deck)
	deck._pending_action = "social_snapshot"
	deck._map_position = Vector2i(13, 27)
	deck._move_world(1, 0)
	_check(shop.is_open() and deck._pending_action == "social_snapshot", "пока идёт другой запрос, каталог не отправляется")
	_check(deck._queued_requests.size() == 1 and deck._queued_requests[0]["action"] == "supplies_catalog", "каталог стоит в очереди до ответа")
	ApiClient.request_completed.emit(false, "Тестовый ответ")
	await _wait_idle(deck)
	_check(shop._message.text.begins_with("Не удалось загрузить ассортимент"), "после ответа на прежний запрос каталог запрошен")
	shop.close()

	shop.open(100)
	deck._buy_supply_item(4, "Зелье восстановления здоровья")
	_check(deck._pending_action == "supplies_buy", "покупка отправляет запрос")
	_check(shop._message.text == "Покупаем…", "во время покупки окно показывает ожидание")
	await _wait_idle(deck)
	_check(shop._message.text.begins_with("Не удалось купить товар"), "сетевая ошибка покупки показана в окне")
	_check(deck._pending_supply_name.is_empty(), "после ошибки имя товара сброшено")

	shop.open(100)
	deck._pending_action = "supplies_buy"
	deck._pending_supply_name = "Зелье восстановления маны"
	deck._on_api_completed(true, {"character": {"id": 42, "coins": 85}, "inventory": {}})
	_check(int(GameSession.character["coins"]) == 85, "покупка списывает монеты в сессии")
	_check(GameSession.character.has("equipment"), "экипировка не теряется при обновлении персонажа")
	_check(shop._balance.text == "У вас: 85 монет", "баланс в окне обновлён после покупки")
	_check(shop._message.text == "Куплено: Зелье восстановления маны", "сообщение о покупке с названием товара")

	deck._pending_action = "supplies_buy"
	deck._pending_supply_name = "Свиток разрушения магии"
	deck._on_api_completed(false, "Недостаточно денег")
	_check(shop._message.text == "Не удалось купить товар: Недостаточно денег", "ошибка сервера показана с префиксом")
	_check(deck._pending_supply_name.is_empty(), "после ошибки сервера имя товара сброшено")
	_check(int(GameSession.character["coins"]) == 85, "при ошибке монеты не меняются")

	deck._pending_action = "other"
	deck._buy_supply_item(6, "Метательный кинжал")
	_check(shop._message.text == "Подождите завершения текущего запроса.", "во время другого запроса покупка не уходит")
	_check(deck._pending_supply_name.is_empty(), "занятая покупка не запоминает товар")
	deck._pending_action = ""

	var saved_id: int = deck._character_id
	deck._character_id = 0
	deck._buy_supply_item(6, "Метательный кинжал")
	_check(shop._message.text == "Персонаж не загружен", "покупка без персонажа не уходит")
	deck._character_id = saved_id

	deck._pending_action = "supplies_catalog"
	deck._on_api_completed(true, {"wrong": 1})
	_check(shop._message.text == "Не удалось загрузить ассортимент: неверный ответ сервера", "неверный ответ каталога показан в окне")
	deck._pending_action = "supplies_catalog"
	deck._on_api_completed(true, {"items": items})
	_check(shop._rows.get_child_count() == 4, "ответ сервера наполняет список товаров")
	shop.close()

	deck._map_position = Vector2i(16, 27)
	deck._render_location()
	_check(_find_button_text(deck._list, "S") != null, "на карте отмечен магазин припасов буквой S")

	deck.queue_free()
	await get_tree().process_frame


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
