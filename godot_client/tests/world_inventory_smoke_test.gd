extends Node

# Рюкзак Башни: сетка вместо полей «ячейка назначения» и «количество», действия уходят как inventory_action,
# текст успеха появляется только после ответа, отказ по слоту запрос не отправляет, «В сундук» работает как раньше.

const WORLD_SCRIPT := preload("res://scripts/world_entry.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"
const WRONG_SLOT := "Предмет не подходит для этого слота"
const ERROR_COLOR := Color8(235, 110, 100)
const GOOD_COLOR := Color8(120, 220, 120)

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "profession_type": "warrior", "level": 7, "xp": 120,
		"stat_points": 3, "stats": {"strength": 12, "agility": 9, "intuition": 7, "wisdom": 4, "intellect": 6, "endurance": 10},
		"equipment": {}, "equipment_bonuses": {}, "copper": 5, "silver": 2, "gold": 1, "carried_weight_kg": 0}
	ApiClient._http.timeout = 0.5
	var world = WORLD_SCRIPT.new()
	add_child(world)
	await _wait_idle(world)

	world._inventory_view = "backpack"
	world._inventory_state = _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
		{"slot_index": 3, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
	], {"weapon": {"name": "Короткий меч", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}})
	world._inventory_panel.visible = true
	world._render_inventory()
	var grid = world._inventory_grid
	var colored: Array = []
	grid.message_colored.connect(func(text: String, color: Color) -> void: colored.append([text, color]))
	_check(world._inventory_grid_host.visible and not world._inventory_scroll.visible, "рюкзак показан сеткой, список сундуков скрыт")
	_check(grid.item_at(["bag", 0]).get("name") == "Зелье здоровья" and grid.item_at(["equip", "weapon"]).get("name") == "Короткий меч",
		"предметы и экипировка лежат в сетке по ячейкам и слотам")
	_check(not _has_placeholder(world, "Ячейка назначения") and not _has_placeholder(world, "Количество для удаления"),
		"полей «ячейка назначения» и «количество для удаления» нет")
	_check(_find_button(world, "Переместить") == null and _find_button(world, "Удалить кол-во") == null,
		"старых кнопок строк рюкзака нет")

	_click(grid, ["bag", 0])
	_check(world._inventory_action_button.visible and world._inventory_action_button.text == "Использовать",
		"для зелья кнопка «Использовать» на месте")
	_check(world._inventory_drop_button.visible and world._inventory_deposit_button.visible, "для предмета в рюкзаке есть «Выбросить» и «В сундук»")
	_click(grid, ["bag", 9])
	_check(not world._inventory_action_button.visible and not world._inventory_deposit_button.visible, "пустая ячейка сбрасывает кнопки действий")

	_drag(grid, ["bag", 0], ["bag", 7])
	_check(world._pending_action == "inventory_action" and world._inventory_status.text == "",
		"перенос уходит запросом inventory_action, текста до ответа нет")
	world._handle_api_result(true, _state([
		{"slot_index": 3, "name": "Простой лук", "quantity": 1, "item_type": "equipment", "equip_slot": "weapon", "effects": {}},
		{"slot_index": 7, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
	], {"weapon": {"name": "Короткий меч", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}}))
	_check(grid.selected_target() == ["bag", 7] and world._inventory_status.text == "", "после ответа на перенос выбор на цели, строка пустая")
	await _wait_api_idle()

	_drop_on_card(world, grid, ["bag", 3], "weapon")
	_check(world._pending_action == "inventory_action" and world._inventory_status.text != "Надето: Простой лук",
		"надевание ждёт ответа, текст «Надето» не показан")
	world._handle_api_result(true, _state([
		{"slot_index": 0, "name": "Зелье здоровья", "quantity": 2, "item_type": "potion", "can_use": true, "effects": {"type": "hp", "value": 40}},
	], {"weapon": {"name": "Простой лук", "item_type": "equipment", "equip_slot": "weapon", "effects": {}}}))
	_check(world._inventory_status.text == "Надето: Простой лук", "после ответа показан текст «Надето»")
	_check(colored.back() == ["Надето: Простой лук", GOOD_COLOR], "сетка отдаёт «Надето» зелёным, как в Python")
	_check(world._inventory_status.get_theme_color("font_color") == GOOD_COLOR, "в рюкзаке «Надето» показано зелёным через message_colored")
	await _wait_api_idle()

	_drop_on_card(world, grid, ["bag", 0], "weapon")
	_check(world._pending_action.is_empty() and world._inventory_status.text == WRONG_SLOT,
		"отказ по слоту показан сразу и запрос не отправляется")
	_check(world._inventory_status.get_theme_color("font_color") == ERROR_COLOR, "отказ по слоту показан красным")
	_check(colored.back() == [WRONG_SLOT, ERROR_COLOR], "сетка отдаёт отказ по слоту красным")

	_click(grid, ["bag", 0])
	world._inventory_action_button.pressed.emit()
	_check(world._pending_action == "inventory_action", "«Использовать» кнопкой уходит запросом")
	world._handle_api_result(false, "Зелье недоступно")
	_check(world._inventory_status.text == "Зелье недоступно" and world._pending_action.is_empty(),
		"ошибка сервера показана, текст «Использовано» не появился")
	_check(world._inventory_status.get_theme_color("font_color") == ERROR_COLOR, "ошибка сервера в рюкзаке красным (RED)")
	_check(grid.selected_target() == ["bag", 0], "ошибка сервера оставляет выбор у предмета")
	await _wait_api_idle()

	world._inventory_deposit_button.pressed.emit()
	_check(world._pending_action == "storage_transfer", "«В сундук» по-прежнему отправляет перенос в сундук")
	await _wait_idle(world)

	remove_child(world)
	world.free()
	GameSession.clear()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("world_inventory_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _state(items: Array, equipment: Dictionary) -> Dictionary:
	return {"inventory": items, "equipment": equipment, "bonuses": {}, "capacity": 50, "carried_weight_kg": 1.0}


func _has_placeholder(node: Node, text: String) -> bool:
	for child in node.find_children("*", "LineEdit", true, false):
		if str(child.placeholder_text).begins_with(text):
			return true
	return false


func _find_button(node: Node, text: String) -> Button:
	for child in node.find_children("*", "Button", true, false):
		if child.text == text:
			return child
	return null


func _click(grid, target: Array) -> void:
	var point := _target_point(grid, target)
	_mouse(grid, point, MOUSE_BUTTON_LEFT, true)
	_mouse(grid, point, MOUSE_BUTTON_LEFT, false)


func _drag(grid, from_target: Array, to_target: Array) -> void:
	var from_point := _target_point(grid, from_target)
	var to_point := _target_point(grid, to_target)
	_mouse(grid, from_point, MOUSE_BUTTON_LEFT, true)
	var motion := InputEventMouseMotion.new()
	motion.position = to_point
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	grid.gui_input.emit(motion)
	_mouse(grid, to_point, MOUSE_BUTTON_LEFT, false)


# Экипировка идёт перетаскиванием на ячейку карточки персонажа: отпускание вне рюкзака передаётся окну мира.
func _drop_on_card(world, grid, source: Array, slot: String) -> void:
	world._profile_overlay.visible = true
	var card = world._profile_overlay._card
	var local: Vector2 = card._slot_rects()[slot].get_center()
	world._on_inventory_drop_outside(source, card.get_global_transform_with_canvas() * local)


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


func _wait_idle(world) -> void:
	var waited := 0
	while not world._pending_action.is_empty() and waited < 240:
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
