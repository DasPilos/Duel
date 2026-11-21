extends Node

const DIALOG_SCRIPT := preload("res://scripts/material_contribution_dialog.gd")
const RULES := preload("res://scripts/character_profile_rules.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _confirmed: Array = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_dialog()
	await _check_economy()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("material_contribution_smoke_test: OK")
	get_tree().quit(code)


func _check_dialog() -> void:
	_check(DIALOG_SCRIPT.format_g(12.0) == "12" and DIALOG_SCRIPT.format_g(58.5) == "58.5", "числа веса форматируются как в Python («:g»)")
	_check(DIALOG_SCRIPT.weight_color(40.0, 109.0) == RULES.GREEN, "вес до 80 % грузоподъёмности зелёный")
	_check(DIALOG_SCRIPT.weight_color(90.0, 109.0) == RULES.YELLOW, "вес выше 80 % жёлтый")
	_check(DIALOG_SCRIPT.weight_color(109.0, 109.0) == RULES.RED, "вес на грузоподъёмности красный")
	_check(DIALOG_SCRIPT.weight_color(50.0, 0.0) == RULES.GREEN, "без грузоподъёмности цвет не красный и не жёлтый")

	var host := Control.new()
	host.size = Vector2(1280.0, 720.0)
	add_child(host)
	var dialog = DIALOG_SCRIPT.new()
	host.add_child(dialog)
	dialog.confirmed.connect(func(mode: String, item_key: String, quantity: int) -> void:
		_confirmed.append([mode, item_key, quantity]))
	await get_tree().process_frame
	_check(not dialog.is_open(), "диалог закрыт по умолчанию")

	dialog.open("withdraw", "wheat", "Пшеница", 20, 12, {"carried_weight_kg": 40.0, "carry_capacity_kg": 109.0}, 2.5)
	_check(dialog.is_open() and dialog.maximum() == 12, "забрать ограничено остатком для забора (12) при запасе 20")
	_check(dialog._title.text == "Забрать: Пшеница", "заголовок режима «Забрать»")
	_check(dialog._available_label.text == "На складе: 20 · можно взять сейчас: 12", "подписи склада и доступного количества")
	_check(dialog._chosen_label.text == "Забрать: 0 / 20", "подпись выбранного количества при заборе")
	_check(dialog._confirm_button.text == "ЗАБРАТЬ" and dialog._confirm_button.disabled, "ЗАБРАТЬ неактивна при нуле")
	_check(dialog._weight_label.visible and dialog._weight_label.text == "Вес после забора: 40 / 109 кг", "вес после забора показан")
	_check(dialog._note_label.text == "Выбранное количество будет помещено в рюкзак", "пояснение режима «Забрать»")
	_check(is_equal_approx(dialog._note_label.position.y, 170.0), "пояснение «Забрать» стоит ниже строки веса")

	dialog._set_quantity_from_x(28.0)
	_check(dialog.quantity() == 0, "левый край дорожки даёт ноль")
	dialog._set_quantity_from_x(532.0)
	_check(dialog.quantity() == 12, "правый край дорожки даёт максимум")
	dialog._set_quantity_from_x(280.0)
	_check(dialog.quantity() == 6, "середина дорожки даёт половину максимума")
	_check(dialog._weight_label.text == "Вес после забора: 55 / 109 кг", "вес растёт с количеством: 40 + 6 × 2.5 = 55")
	_check(dialog._chosen_label.text == "Забрать: 6 / 20", "подпись количества обновляется")
	_check(not dialog._confirm_button.disabled, "ЗАБРАТЬ активна при выбранном количестве")

	dialog._frame.gui_input.emit(_mouse_press(Vector2(406.0, 124.0)))
	_check(dialog._dragging and dialog.quantity() == 9, "нажатие на дорожку начинает протяжку (0.75 × 12 = 9)")
	dialog._frame.gui_input.emit(_mouse_motion(Vector2(532.0, 124.0)))
	_check(dialog.quantity() == 12, "протяжка до правого края даёт максимум")
	dialog._frame.gui_input.emit(_mouse_release(Vector2(532.0, 124.0)))
	dialog._frame.gui_input.emit(_mouse_motion(Vector2(280.0, 124.0)))
	_check(not dialog._dragging and dialog.quantity() == 12, "после отпускания кнопки протяжка остановлена")
	dialog._frame.gui_input.emit(_mouse_press(Vector2(10.0, 10.0)))
	_check(not dialog._dragging, "нажатие вне дорожки протяжку не начинает")

	dialog._set_quantity_from_x(406.0)
	dialog._confirm_button.pressed.emit()
	_check(not dialog.is_open() and _confirmed == [["withdraw", "wheat", 9]], "подтверждение отдаёт режим, ресурс и количество и закрывает диалог")
	_confirmed.clear()

	dialog.open("deposit", "wood", "Древесина", 9, 5)
	_check(dialog.maximum() == 5 and dialog._title.text == "Пополнение склада: Древесина", "внесение ограничено потребностью (5) и заголовок режима")
	_check(dialog._available_label.text == "В рюкзаке: 9", "подпись количества в рюкзаке")
	_check(dialog._chosen_label.text == "Внести: 0 / 5", "подпись внесения")
	_check(not dialog._weight_label.visible, "при внесении строка веса скрыта")
	_check(dialog._note_label.text == "Выбранное количество поступит в общий запас здания", "пояснение режима внесения")
	_check(dialog._confirm_button.text == "ВНЕСТИ", "кнопка ВНЕСТИ")
	_check(is_equal_approx(dialog._note_label.position.y, 151.0), "пояснение внесения стоит выше, без строки веса")
	dialog._set_quantity_from_x(280.0)
	_check(dialog.quantity() == 2, "половина от 5 (2.5) округляется к чётному, как в Python: 2")
	dialog.open("deposit", "wood", "Древесина", 9, 9)
	dialog._set_quantity_from_x(280.0)
	_check(dialog.quantity() == 4, "половина от 9 (4.5) округляется к чётному, как в Python: 4")

	dialog.open("deposit", "wood", "Древесина", 9, 9)
	_check(dialog._confirm_button.disabled, "при нулевом количестве кнопка ВНЕСТИ неактивна")
	dialog._on_confirm_pressed()
	_check(dialog.is_open() and _confirmed.is_empty(), "без выбранного количества подтверждение ничего не делает")
	dialog._set_quantity_from_x(280.0)
	_check(not dialog._confirm_button.disabled, "при выбранном количестве кнопка ВНЕСТИ активна")
	dialog._cancel_button.pressed.emit()
	_check(not dialog.is_open() and _confirmed.is_empty(), "ОТМЕНА закрывает диалог без подтверждения")

	dialog.open("contribute", "x", "Дерево", 5, 3)
	_check(dialog._title.text == "Взнос: Дерево" and dialog._note_label.text == "Внесённые материалы пойдут на улучшение здания", "режим взноса повторяет подписи Python-диалога")
	dialog.close()

	dialog.open("withdraw", "gold", "Золото", 0, 5)
	dialog._set_quantity_from_x(300.0)
	_check(dialog.maximum() == 0 and dialog.quantity() == 0, "при нулевом максимуме ползунок не меняет количество")
	dialog.close()

	dialog.open("deposit", "wood", "Древесина", 9, 5)
	_check(dialog.is_open(), "диалог не закрывается сам: Esc обрабатывает меню выхода")

	dialog.open("deposit", "wood", "Древесина", 9, 5)
	dialog._gui_input(_mouse_press(Vector2(640.0, 360.0)))
	_check(dialog.is_open(), "клик внутри панели не закрывает диалог")
	dialog._gui_input(_mouse_press(Vector2(5.0, 5.0)))
	_check(not dialog.is_open(), "клик вне панели закрывает диалог")

	remove_child(host)
	host.free()


func _check_economy() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "carried_weight_kg": 0.0}
	ApiClient._http.timeout = 0.5
	var economy = ECONOMY_SCRIPT.new()
	add_child(economy)
	await _wait_idle(economy)
	_check(economy._contribution_dialog != null, "экран экономики создаёт диалог взноса")

	economy._selected_building = "warehouse"
	economy._open_storage_window("warehouse")
	await _wait_idle(economy)
	economy._show_building(_warehouse_state(12))
	_check(economy._content.get_node("StorageView").visible and economy._storage_window.window_title() == "Склад",
		"окно склада показывает состояние склада")

	var dialog = economy._contribution_dialog
	economy._pending_action = "city"
	economy._open_storage_dialog("deposit", "wood")
	_check(not dialog.is_open() and economy._status.text == "Подождите завершения текущего запроса.", "пока идёт запрос, диалог склада не открывается")
	economy._pending_action = ""

	economy._on_storage_view_action("storage_withdraw", {"resource": "wheat", "quantity": 12})
	_check(dialog.is_open() and dialog._mode == "withdraw", "ВЗЯТЬ открывает диалог режима «Забрать»")
	_check(dialog.maximum() == 5, "забрать не больше ограничения рюкзака по весу: min(12, 5) = 5")
	_check(dialog._weight_label.text == "Вес после забора: 40 / 109 кг", "диалог показывает вес из серверного состояния")

	dialog.open("deposit", "wood", "Древесина", 9, 4)
	economy._unhandled_input(_key_press(KEY_ESCAPE))
	_check(economy._exit_menu.is_open() and dialog.is_open(), "Esc при открытом диалоге открывает меню выхода, диалог остаётся, как в Python")
	economy._exit_menu.close()
	dialog.close()

	economy._on_storage_view_action("storage_withdraw", {"resource": "wheat", "quantity": 12})
	dialog._set_quantity_from_x(28.0 + 504.0 * 0.6)
	_check(dialog.quantity() == 3, "выбор 3 из 5")
	dialog._confirm_button.pressed.emit()
	_check(not dialog.is_open() and economy._pending_action == "storage_action", "подтверждение отправляет storage_action")
	var withdraw_request: Dictionary = economy._storage_action_request("withdraw", "wheat", 3)
	_check(withdraw_request["path"] == "/api/buildings/warehouse/42/storage/withdraw", "забор идёт в storage/withdraw")
	_check(withdraw_request["body"] == {"resource": "wheat", "quantity": 3}, "тело запроса содержит ресурс и количество")
	var deposit_request: Dictionary = economy._storage_action_request("deposit", "wood", 2)
	_check(deposit_request["path"] == "/api/buildings/warehouse/42/storage/deposit", "внесение идёт в storage/deposit")
	await _wait_idle(economy)

	economy._pending_action = "storage_action"
	economy._on_api_completed(true, {"building": _warehouse_state(9)})
	_check(economy._building["storage"]["wheat"] == 9, "ответ сервера обновляет запасы здания")
	_check(economy._pending_action == "inventory_load", "после взноса запрашивается инвентарь")
	await _wait_idle(economy)

	economy._pending_action = "inventory_load"
	economy._on_api_completed(true, {"inventory": [], "carried_weight_kg": 12.5, "equipment": {}, "bonuses": {"strength": 1}})
	_check(is_equal_approx(float(GameSession.character["carried_weight_kg"]), 12.5), "переносимый вес персонажа берётся из инвентаря")
	_check(GameSession.character["equipment_bonuses"] == {"strength": 1}, "бонусы экипировки берутся из инвентаря")

	economy._pending_action = "storage_action"
	economy._on_api_completed(false, "В рюкзаке нет места для этого ресурса")
	_check(economy._storage_window._message_label.text == "В рюкзаке нет места для этого ресурса", "ошибка склада показывается в окне склада")

	remove_child(economy)
	economy.free()
	GameSession.clear()


func _warehouse_state(wheat_stock: int) -> Dictionary:
	return {
		"building": "warehouse",
		"level": 2,
		"workers": 0,
		"max_workers": 0,
		"next_harvest_seconds": 0,
		"upgrade": null,
		"worker_slots": [],
		"storage": {"wheat": wheat_stock, "wood": 0, "limit": 500},
		"storage_withdrawable": {
			"wheat": {"available": wheat_stock, "max_withdraw": 5, "item_weight_kg": 2.5,
				"carried_weight_kg": 40.0, "carry_capacity_kg": 109.0},
		},
		"storage_depositable": {
			"wood": {"item_id": 60, "in_backpack": 9, "max_deposit": 4},
			"wheat": {"item_id": 63, "in_backpack": 0, "max_deposit": 0},
		},
	}


func _wait_idle(economy) -> void:
	var waited := 0.0
	while not economy._pending_action.is_empty() and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05
	_check(economy._pending_action.is_empty(), "запрос экономики завершается")


func _mouse_press(position: Vector2) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = position
	return event


func _mouse_release(position: Vector2) -> InputEventMouseButton:
	var event := _mouse_press(position)
	event.pressed = false
	return event


func _mouse_motion(position: Vector2) -> InputEventMouseMotion:
	var event := InputEventMouseMotion.new()
	event.position = position
	return event


func _key_press(keycode: Key) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	return event


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
