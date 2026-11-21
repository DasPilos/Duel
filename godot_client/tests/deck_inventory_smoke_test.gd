extends Node

# Рюкзак Колоды: перенос и надевание уходят как inventory_action, текст успеха появляется только после ответа,
# отказ по слоту запрос не отправляет, «В сундук» остаётся для переноса в сундук.

const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const WRONG_SLOT := "Предмет не подходит для этого слота"
const GOOD_COLOR := Color8(120, 220, 120)
const BAD_COLOR := Color8(235, 110, 100)
const TEXT_DIM_COLOR := Color8(150, 142, 130)

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {"id": 42, "name": "Тест", "type": "warrior", "level": 5, "hp": 60, "max_hp": 60,
		"mp": 20, "max_mp": 20, "zone": "character_room", "talents": {}}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)

	deck._view = "inventory"
	deck._inventory_view = "backpack"
	deck._inventory_state = _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
		{"slot_index": 3, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
	], {"weapon": {"name": "Короткий меч", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}})
	deck._render_inventory()
	var grid = deck._inventory_grid
	var colored: Array = []
	grid.message_colored.connect(func(text: String, color: Color) -> void: colored.append([text, color]))
	_check(grid.item_at(["bag", 0]).get("name") == "Зелье здоровья", "рюкзак Колоды показан сеткой")
	_click(grid, ["bag", 3])
	_check(deck._inventory_deposit_button.visible and deck._inventory_drop_button.visible,
		"для предмета в рюкзаке доступны «В сундук» и «Выбросить»")
	_click(grid, ["equip", "weapon"])
	_check(not deck._inventory_deposit_button.visible and not deck._inventory_drop_button.visible,
		"для экипировки «В сундук» и «Выбросить» скрыты")

	_drag(grid, ["bag", 0], ["bag", 7])
	_check(deck._pending_action == "inventory_action" and deck._inventory_message_label.text == "",
		"перенос уходит запросом inventory_action, текста до ответа нет")
	deck._on_api_completed(true, _state([
		{"slot_index": 3, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
		{"slot_index": 7, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
	], {"weapon": {"name": "Короткий меч", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}}))
	_check(grid.selected_target() == ["bag", 7] and deck._inventory_message_label.text == "",
		"после ответа на перенос выбор на цели, строка сообщения пустая")
	await _wait_api_idle()

	_drag(grid, ["bag", 3], ["equip", "weapon"])
	_check(deck._pending_action == "inventory_action" and deck._inventory_message_label.text != "Надето: Простой лук",
		"надевание ждёт ответа, текст «Надето» не показан")
	deck._on_api_completed(true, _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
	], {"weapon": {"name": "Простой лук", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}}))
	_check(deck._inventory_message_label.text == "Надето: Простой лук", "после ответа показан текст «Надето»")
	_check(colored.back() == ["Надето: Простой лук", GOOD_COLOR], "сетка отдаёт «Надето» зелёным, как в Python")
	_check(deck._inventory_message_label.get_theme_color("font_color") == GOOD_COLOR, "окно Колоды показывает «Надето» зелёным")
	await _wait_api_idle()

	_drag(grid, ["bag", 0], ["equip", "weapon"])
	_check(deck._pending_action.is_empty() and deck._inventory_message_label.text == WRONG_SLOT,
		"отказ по слоту показан сразу и запрос не отправляется")
	_check(deck._inventory_message_label.get_theme_color("font_color") == Color8(235, 110, 100),
		"отказ по слоту показан красным")
	_check(colored.back() == [WRONG_SLOT, BAD_COLOR], "сетка отдаёт отказ по слоту красным")

	_right_click(grid, ["bag", 0])
	_check(deck._pending_action == "inventory_action", "«Использовать» из правого клика уходит запросом")
	deck._on_api_completed(false, "Зелье недоступно")
	_check(deck._inventory_message_label.text == "Зелье недоступно" and deck._pending_action.is_empty(),
		"ошибка сервера показана в рюкзаке, текст «Использовано» не появился")
	_check(deck._inventory_message_label.get_theme_color("font_color") == BAD_COLOR, "ошибка сервера в рюкзаке красным (RED)")
	_check(grid.selected_target() == ["bag", 0], "ошибка сервера оставляет выбор у предмета")
	await _wait_api_idle()

	_drag(grid, ["equip", "weapon"], ["bag", 5])
	_check(deck._pending_action == "inventory_action" and deck._inventory_message_label.text != "Снято: Простой лук",
		"снятие перетаскиванием ждёт ответа, текст «Снято» не показан")
	deck._on_api_completed(true, _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
		{"slot_index": 2, "name": "Дубовая доска", "quantity": 1, "item_type": "material", "effects": {}},
		{"slot_index": 5, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
	], {}))
	_check(deck._inventory_message_label.text == "Снято: Простой лук" and deck._inventory_message_label.get_theme_color("font_color") == TEXT_DIM_COLOR,
		"после ответа «Снято» приглушённым, как в Python")
	await _wait_api_idle()

	_right_click(grid, ["bag", 2])
	_check(deck._pending_action.is_empty() and deck._inventory_message_label.text == "Этот предмет нельзя использовать"
		and deck._inventory_message_label.get_theme_color("font_color") == TEXT_DIM_COLOR,
		"предмет без действия: отказ приглушённым и без запроса")

	grid.request_drop(["bag", 2])
	_check(deck._pending_action.is_empty(), "первое подтверждение выброса запрос не отправляет")
	grid.request_drop(["bag", 2])
	_check(deck._pending_action == "inventory_action", "второе подтверждение отправляет выброс")
	deck._on_api_completed(true, _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
		{"slot_index": 5, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
	], {}))
	_check(deck._inventory_message_label.text == "Выброшено: Дубовая доска" and deck._inventory_message_label.get_theme_color("font_color") == TEXT_DIM_COLOR,
		"после ответа «Выброшено» приглушённым, как в Python")
	await _wait_api_idle()

	remove_child(deck)
	deck.free()
	GameSession.clear()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_inventory_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _state(items: Array, equipment: Dictionary) -> Dictionary:
	return {"inventory": items, "equipment": equipment, "bonuses": {}, "capacity": 50, "carried_weight_kg": 1.0}


func _click(grid, target: Array) -> void:
	var point := _target_point(grid, target)
	_mouse(grid, point, MOUSE_BUTTON_LEFT, true)
	_mouse(grid, point, MOUSE_BUTTON_LEFT, false)


func _right_click(grid, target: Array) -> void:
	var point := _target_point(grid, target)
	_mouse(grid, point, MOUSE_BUTTON_RIGHT, true)
	_mouse(grid, point, MOUSE_BUTTON_RIGHT, false)


func _drag(grid, from_target: Array, to_target: Array) -> void:
	var from_point := _target_point(grid, from_target)
	var to_point := _target_point(grid, to_target)
	_mouse(grid, from_point, MOUSE_BUTTON_LEFT, true)
	var motion := InputEventMouseMotion.new()
	motion.position = to_point
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	grid.gui_input.emit(motion)
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


func _wait_idle(deck) -> void:
	var waited := 0
	while not deck._pending_action.is_empty() and waited < 240:
		await get_tree().process_frame
		waited += 1
	await get_tree().process_frame


func _wait_api_idle() -> void:
	var waited := 0
	while ApiClient._busy and waited < 240:
		await get_tree().process_frame
		waited += 1


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
