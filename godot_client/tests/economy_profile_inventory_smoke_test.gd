extends Node

const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const RULES := preload("res://scripts/inventory_drag_rules.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	await _check_profile_keys()
	await _check_escape_order()
	await _check_chat_blocks_keys()
	await _check_inventory_window()
	GameSession.clear()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_profile_inventory_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_profile_keys() -> void:
	var economy = _start_economy()
	_check(not economy._profile_overlay.is_open(), "при входе карточка персонажа закрыта")
	_press(economy, KEY_I)
	_check(economy._profile_overlay.is_open(), "I открывает карточку персонажа")
	_press(economy, KEY_I)
	_check(not economy._profile_overlay.is_open(), "повторная I закрывает карточку")
	_press(economy, KEY_C)
	_check(economy._profile_overlay.is_open(), "C открывает карточку персонажа")
	_press(economy, KEY_C)
	_check(not economy._profile_overlay.is_open(), "повторная C закрывает карточку")
	await _finish_economy(economy)


func _check_escape_order() -> void:
	var economy = _start_economy()
	_press(economy, KEY_I)
	economy._profile_overlay.backpack_requested.emit()
	_check(economy._inventory_view.is_open(), "кнопка РЮКЗАК открывает инвентарь")
	_check(economy._pending_action == "inventory_load", "инвентарь запрашивает /api/inventory/{id}")
	_press(economy, KEY_ESCAPE)
	_check(not economy._inventory_view.is_open() and not economy._chat_panel.is_open() and not economy._exit_menu.blocks_input(),
		"первый Esc закрывает инвентарь и не открывает меню выхода")
	_check(economy._profile_overlay.is_open(), "Esc не закрывает карточку персонажа")
	_press(economy, KEY_ENTER)
	_check(economy._chat_panel.is_open(), "Enter открывает чат, когда инвентарь закрыт")
	_press(economy, KEY_ESCAPE)
	_check(not economy._chat_panel.is_open() and not economy._exit_menu.blocks_input(), "следующий Esc закрывает чат")
	_press(economy, KEY_ESCAPE)
	_check(economy._exit_menu.blocks_input(), "Esc без окон и чата открывает меню выхода")
	_check(economy._profile_overlay.is_open(), "меню выхода не закрывает карточку персонажа")
	economy._exit_menu.close()
	await _finish_economy(economy)


func _check_chat_blocks_keys() -> void:
	var economy = _start_economy()
	_press(economy, KEY_ENTER)
	_check(economy._chat_panel.is_open(), "Enter открывает чат")
	_press(economy, KEY_I)
	_check(not economy._profile_overlay.is_open(), "при открытом чате I не открывает карточку")
	_press(economy, KEY_C)
	_check(not economy._profile_overlay.is_open(), "при открытом чате C не открывает карточку")
	_press(economy, KEY_ENTER)
	_check(economy._chat_panel.is_open(), "Enter при открытом чате ничего не меняет")
	_press(economy, KEY_ESCAPE)
	_check(not economy._chat_panel.is_open() and not economy._exit_menu.blocks_input(), "Esc закрывает чат")
	_press(economy, KEY_I)
	_check(economy._profile_overlay.is_open(), "после закрытия чата I открывает карточку")
	economy._treasury_dialog.open("deposit", "copper", "", 10, 10)
	_check(economy._treasury_dialog.is_open(), "диалог казны открыт")
	_press(economy, KEY_C)
	_check(not economy._profile_overlay.is_open(), "открытый диалог казны не блокирует C")
	economy._treasury_dialog.close()
	await _finish_economy(economy)


func _check_inventory_window() -> void:
	var economy = _start_economy()
	_press(economy, KEY_I)
	economy._profile_overlay.backpack_requested.emit()
	await _wait_idle(economy)
	_check(economy._inventory_view.is_open(), "инвентарь остаётся открытым после неудачного запроса")
	_check(economy._inventory_view._status.text != "Загружаем инвентарь…", "ошибка запроса показана в окне инвентаря")

	_load_state(economy)
	_check(economy._inventory_view._weight.text.begins_with("Переносимый вес: 12.5 / "), "окно показывает переносимый вес")
	_check(_status_color(economy) == RULES.TEXT_DIM_COLOR, "сообщение загрузки приглушённое, без серого")
	var grid = economy._inventory_view._grid
	var actions: Array = _capture_actions(economy._inventory_view)
	_check(grid.item_at(["bag", 3]).get("name") == "Простой лук" and grid.item_at(["bag", 0]).get("name") == "Зелье здоровья",
		"рюкзак раскладывает предметы по ячейкам")
	_check(grid.item_at(["equip", "weapon"]).get("name") == "Простой лук", "надетый предмет сидит в слоте оружия")
	_check(is_equal_approx(float(GameSession.character["carried_weight_kg"]), 12.5), "вес персонажа берётся из инвентаря")

	_click_cell(economy, 3)
	_check(_visible_button_texts(economy._inventory_view).has("Надеть"), "выбранный предмет получает кнопку «Надеть»")
	_press_button(economy._inventory_view, "Надеть")
	_check(actions == [["equip", {"slot_index": 3}]], "кнопка «Надеть» передаёт ячейку без слота")
	_check(economy._pending_action == "inventory_action", "кнопка «Надеть» отправляет запрос инвентаря")
	_check(_status_text(economy) != "Надето: Простой лук", "текст «Надето» не появляется до ответа сервера")
	await _wait_idle(economy)
	_check(_status_text(economy) != "" and _status_text(economy) != "Надето: Простой лук", "неудачное действие показывает ошибку, а не «Надето»")
	_check(grid.selected_target() == ["bag", 3], "неудачное действие оставляет выбор у предмета в рюкзаке")
	_check(_status_color(economy) == RULES.BAD_COLOR, "ошибка сервера показана красным")

	_load_state(economy)
	_click_cell(economy, 3)
	_press_button(economy._inventory_view, "Надеть")
	economy._on_api_completed(true, _inventory_payload())
	_check(_status_text(economy) == "Надето: Простой лук", "после ответа сервера показан текст «Надето»")
	_check(_status_color(economy) == RULES.GOOD_COLOR, "«Надето» зелёным, как в Python")
	await _wait_api_idle()

	_load_state(economy)
	_click_cell(economy, 0)
	_press_button(economy._inventory_view, "Выбросить")
	_check(economy._pending_action.is_empty() and _visible_button_texts(economy._inventory_view).has("Точно?"),
		"первое «Выбросить» просит подтверждения и запрос не отправляет")
	_press_button(economy._inventory_view, "Точно?")
	_check(economy._pending_action == "inventory_action" and actions.back() == ["drop", {"slot_index": 0}], "второе нажатие отправляет действие drop")
	_check(_status_text(economy) != "Выброшено: Зелье здоровья", "текст «Выброшено» не появляется до ответа")
	economy._on_api_completed(true, _inventory_payload())
	_check(_status_text(economy) == "Выброшено: Зелье здоровья", "после ответа сервера показан текст «Выброшено»")
	_check(_status_color(economy) == RULES.TEXT_DIM_COLOR, "«Выброшено» приглушённым, как в Python")
	await _wait_api_idle()

	_load_state(economy)
	actions.clear()
	_drag(economy, ["bag", 3], ["equip", "weapon"])
	_check(actions == [["equip", {"slot_index": 3, "slot": "weapon"}]], "перетаскивание лука на слот оружия передаёт слот")
	await _wait_idle(economy)

	_load_state(economy)
	actions.clear()
	_drag(economy, ["bag", 0], ["equip", "weapon"])
	_check(actions.is_empty() and economy._pending_action.is_empty(), "зелье не уходит в слот оружия и запрос не отправляется")
	_check(_status_text(economy) == "Предмет не подходит для этого слота", "отказ при перетаскивании показан в окне сразу")
	_check(_status_color(economy) == RULES.BAD_COLOR, "отказ по слоту красным")
	_right_click_cell(economy, 7)
	_check(_status_text(economy) == "Этот предмет нельзя использовать" and _status_color(economy) == RULES.TEXT_DIM_COLOR,
		"правый клик по предмету без действия: отказ приглушённым, как в Python")
	_check(economy._pending_action.is_empty() and actions.is_empty(), "отказ правым кликом запрос не отправляет")

	_load_state(economy)
	actions.clear()
	_drag(economy, ["bag", 7], ["bag", 9])
	_check(actions == [["move", {"from_slot": 7, "to_slot": 9}]], "перенос в пустую ячейку уходит намерением move")
	_check(ECONOMY_SCRIPT.INVENTORY_ACTION_PATHS["move"] == "/api/inventory/move", "перенос уходит на /api/inventory/move")
	_check(_payload_keys(actions[0][1]) == ["from_slot", "to_slot"], "в переносе на сервер нет лишних полей")
	_check(economy._pending_action == "inventory_action" and _status_text(economy) == "Инвентарь обновлён.",
		"перенос не меняет текст сообщения до ответа сервера")
	economy._on_api_completed(true, _inventory_payload())
	_check(_status_text(economy) == "" and grid.selected_target() == ["bag", 9], "после ответа на перенос строка очищается, выбор на цели")
	await _wait_api_idle()

	_load_state(economy)
	actions.clear()
	_drag(economy, ["equip", "weapon"], ["bag", 11])
	_check(actions == [["unequip", {"slot": "weapon", "target_slot": 11}]], "перетаскивание из слота оружия в рюкзак передаёт target_slot")
	economy._on_api_completed(true, _inventory_payload())
	_check(_status_text(economy) == "Снято: Простой лук" and _status_color(economy) == RULES.TEXT_DIM_COLOR,
		"после ответа показан текст «Снято» приглушённым цветом")
	await _wait_api_idle()

	_load_state(economy)
	_click_cell(economy, 0)
	_press_button(economy._inventory_view, "Использовать")
	_check(economy._pending_action == "inventory_action" and _status_text(economy) != "Использовано: Зелье здоровья",
		"«Использовать» отправляет запрос, текст «Использовано» ждёт ответа")
	var after := _inventory_payload()
	after["character"] = {"id": 42, "name": "Тест", "type": "mage", "level": 3, "xp": 0, "stat_points": 2, "hp": 120, "max_hp": 140,
		"copper": 120, "silver": 0, "gold": 0, "stats": {"strength": 10, "endurance": 10}, "equipment": {}, "equipment_bonuses": {}}
	economy._on_api_completed(true, after)
	_check(_status_text(economy) == "Использовано: Зелье здоровья", "после «Использовать» показан текст из ответа сервера")
	_check(_status_color(economy) == RULES.GOOD_COLOR, "«Использовано» зелёным, как в Python")
	_check(int(GameSession.character["hp"]) == 120, "персонаж из ответа действия заменяет текущего")
	_check(is_equal_approx(float(GameSession.character["carried_weight_kg"]), 12.5), "переносимый вес после действия берётся из ответа")
	await _wait_api_idle()

	_check(economy._profile_overlay.is_open(), "карточка остаётся открытой, пока инвентарь открыт")
	economy._on_profile_stat_requested("strength", 1)
	_check(economy._pending_action == "profile_update", "+ к характеристике сохраняет карточку на сервере")
	await _wait_idle(economy)
	_check(economy._map_hint.text.length() > 0 and economy._pending_action.is_empty(), "неудачное сохранение карточки показывает причину")
	await _finish_economy(economy)


func _load_state(economy) -> void:
	economy._pending_action = "inventory_load"
	economy._on_api_completed(true, _inventory_payload())


func _status_text(economy) -> String:
	return economy._inventory_view._status.text


func _status_color(economy) -> Color:
	return economy._inventory_view._status.get_theme_color("font_color")


func _right_click_cell(economy, index: int) -> void:
	var grid = economy._inventory_view._grid
	var point: Vector2 = grid.cell_rect(index).get_center()
	_mouse(grid, point, MOUSE_BUTTON_RIGHT, true)
	_mouse(grid, point, MOUSE_BUTTON_RIGHT, false)


func _payload_keys(payload: Dictionary) -> Array:
	var keys := payload.keys()
	keys.sort()
	return keys


func _wait_api_idle() -> void:
	var waited := 0.0
	while ApiClient._busy and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05


func _start_economy():
	GameSession.clear()
	GameSession.character = {
		"id": 42, "name": "Тест", "type": "mage", "level": 3, "xp": 0, "hp": 80, "max_hp": 140,
		"copper": 120, "silver": 0, "gold": 0, "carried_weight_kg": 12.5, "stat_points": 2,
		"stats": {"strength": 10, "endurance": 10, "agility": 5, "intuition": 5, "wisdom": 5, "intellect": 5},
		"equipment": {"weapon": {"name": "Простой лук", "equip_slot": "weapon"}}, "equipment_bonuses": {},
	}
	GameSession.world = {}
	GameSession.world_token = "test-world-token"
	ApiClient.set_server_url(UNREACHABLE_URL)
	ApiClient.token = "test-world-token"
	ApiClient._http.timeout = 0.5
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	economy._chat_timer.stop()
	economy._travel_timer.stop()
	return economy


func _finish_economy(economy) -> void:
	await _wait_idle(economy)
	remove_child(economy)
	economy.free()
	GameSession.clear()


func _wait_idle(economy) -> void:
	var waited := 0.0
	while not economy._pending_action.is_empty() and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05
	_check(economy._pending_action.is_empty(), "запрос экономики завершается")


func _press(economy, keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	economy._unhandled_input(event)


func _press_button(view, text: String) -> void:
	for button in view.find_children("*", "Button", true, false):
		if button.text == text and button.is_visible_in_tree():
			button.pressed.emit()
			return
	_check(false, "кнопка «%s» видна в окне инвентаря" % text)


func _visible_button_texts(view) -> Array:
	var texts: Array = []
	for button in view.find_children("*", "Button", true, false):
		if button.is_visible_in_tree():
			texts.append(button.text)
	return texts


func _capture_actions(view) -> Array:
	var captured: Array = []
	view.action_requested.connect(func(action: String, payload: Dictionary) -> void: captured.append([action, payload]))
	return captured


func _click_cell(economy, index: int) -> void:
	var grid = economy._inventory_view._grid
	var point: Vector2 = grid.cell_rect(index).get_center()
	_mouse(grid, point, MOUSE_BUTTON_LEFT, true)
	_mouse(grid, point, MOUSE_BUTTON_LEFT, false)


# Цели: ["bag", индекс ячейки] или ["equip", ключ слота]. Перетаскивание проходит через ввод сетки, как у игрока.
func _drag(economy, from_target: Array, to_target: Array) -> void:
	var grid = economy._inventory_view._grid
	var from_point := _target_point(grid, from_target)
	var to_point := _target_point(grid, to_target)
	_mouse(grid, from_point, MOUSE_BUTTON_LEFT, true)
	_motion(grid, to_point)
	_mouse(grid, to_point, MOUSE_BUTTON_LEFT, false)


func _target_point(grid, target: Array) -> Vector2:
	if str(target[0]) == "bag":
		return grid.cell_rect(int(target[1])).get_center()
	return grid.slot_rect(str(target[1])).get_center()


func _mouse(control, point: Vector2, button: MouseButton, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = pressed
	event.position = point
	control.gui_input.emit(event)


func _motion(control, point: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	control.gui_input.emit(event)


func _inventory_payload() -> Dictionary:
	return {
		"inventory": [
			{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "can_use": true, "equip_slot": null, "effects": {"type": "hp", "value": 40}},
			{"slot_index": 3, "name": "Простой лук", "quantity": 1, "can_use": false, "equip_slot": "weapon"},
			{"slot_index": 7, "name": "Дубовая доска", "quantity": 5, "can_use": false, "equip_slot": null},
		],
		"equipment": {"weapon": {"name": "Простой лук", "equip_slot": "weapon"}},
		"bonuses": {"strength": 1},
		"capacity": 50,
		"carried_weight_kg": 12.5,
	}


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
