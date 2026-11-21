extends Node

# Вид сетки: перетаскивание, правый клик и Delete эмитят нужные сигналы; подсветка и выбор — как в Python.
# Ввод подаётся в gui_input, по которому вид получает и мышь, и клавиатуру.

const VIEW_SCRIPT := preload("res://scripts/inventory_drag_view.gd")
const RULES := preload("res://scripts/inventory_drag_rules.gd")

const POTION := {"name": "Зелье здоровья", "item_type": "potion", "can_use": true, "icon": "bone",
	"effects": {"type": "hp", "value": 40}, "quantity": 2}
const BOW := {"name": "Простой лук", "rarity": "rare", "item_type": "equipment", "equip_slot": "weapon",
	"effects": {"damage": [3, 5]}, "weight": 2, "price": 500}
const HELMET := {"name": "Шлем", "item_type": "equipment", "equip_slot": "head", "effects": {}}
const BOARD := {"name": "Дубовая доска", "item_type": "material", "quantity": 5, "effects": {}}
const SWORD := {"name": "Короткий меч", "item_type": "equipment", "equip_slot": "weapon", "effects": {"damage": [4, 6]}}
const WRONG_SLOT := "Предмет не подходит для этого слота"

var _failures: Array[String] = []
var _checks := 0
var _view
var _events: Array = []
var _messages: Array = []
var _colored: Array = []
var _selection_changes := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_view = VIEW_SCRIPT.new()
	_connect_signals()
	add_child(_view)
	await get_tree().process_frame
	_view.set_items([_item(0, POTION), _item(3, BOW), _item(5, HELMET), _item(7, BOARD)], {"weapon": SWORD}, 50)
	_check_layout()
	_check_drag_to_equip_slot()
	_check_wrong_slot_refused()
	_check_move_to_empty_cell()
	_check_unequip_by_drag()
	_check_click_and_threshold()
	_check_right_click_actions()
	_check_delete_confirm()
	_check_highlight_while_dragging()
	_check_state_update()
	_check_pending_protocol()
	await _check_draw_pass()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("inventory_drag_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_layout() -> void:
	_check(_view.size == Vector2(1120.0, 440.0), "вид занимает 1120×440 (сетка и кукла Python)")
	_check(_view.cell_rect(0).position == Vector2(464.0, 56.0), "первая ячейка сетки в (464, 56)")
	_check(_view.cell_rect(49).end == Vector2(1120.0, 382.0), "последняя ячейка 10×5 заканчивается в (1120, 382)")
	_check(_view.slot_rect("weapon") == Rect2(275, 197, 66, 62), "слот оружия на месте Python (275, 197)")


func _check_drag_to_equip_slot() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_drag(_cell(3), _slot("weapon"))
	_check(_events == [["equip", 3, "weapon"]], "лук из ячейки 3 на слот оружия: equip_requested(3, weapon)")
	_check(_view.selected_target() == ["bag", 3] and _messages.is_empty(), "до ответа выбор у источника и текста успеха нет")
	_view.resolve_action(true)
	_check(_view.selected_target() == ["equip", "weapon"], "после успешного ответа выбран слот оружия")
	_check(_messages == [["Надето: Простой лук", false]], "после ответа показан текст «Надето»")
	_check(_colored == [["Надето: Простой лук", RULES.GOOD_COLOR]], "«Надето» зелёным, как в Python")
	_check(not _view.is_dragging() and _view.highlight_slot() == "", "после отпускания перетаскивание и подсветка сняты")


func _check_wrong_slot_refused() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_drag(_cell(0), _slot("weapon"))
	_check(_events.is_empty(), "зелье не уходит в слот оружия")
	_check(_messages == [[WRONG_SLOT, true]], "отказ показан красным сообщением сразу, без ожидания ответа")
	_check(_colored == [[WRONG_SLOT, RULES.BAD_COLOR]], "отказ по слоту красным (RED)")


func _check_move_to_empty_cell() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_drag(_cell(7), _cell(9))
	_check(_events == [["move", 7, 9]], "перенос в пустую ячейку: move_requested(7, 9)")
	_check(_messages.is_empty() and _view.selected_target() == ["bag", 7], "перенос: до ответа ни текста, ни смены выбора")
	_view.resolve_action(true)
	_check(_view.selected_target() == ["bag", 9], "после переноса выбрана целевая ячейка")
	_check(_messages == [["", false]], "после переноса строка сообщения очищается")
	_check(_colored == [["", RULES.TEXT_DIM_COLOR]], "после переноса строка пустая, цвет не важен")


func _check_unequip_by_drag() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_drag(_slot("weapon"), _cell(11))
	_check(_events == [["unequip", "weapon", 11]], "снятие перетаскиванием: unequip_requested(weapon, 11)")
	_view.resolve_action(true)
	_check(_view.selected_target().is_empty(), "после снятия выбор сбрасывается")
	_check(_messages == [["Снято: Короткий меч", false]], "после снятия показан текст «Снято»")
	_check(_colored == [["Снято: Короткий меч", RULES.TEXT_DIM_COLOR]], "«Снято» приглушённым, как в Python")


func _check_click_and_threshold() -> void:
	_events.clear()
	_click(_cell(5))
	_check(_events.is_empty() and _view.selected_target() == ["bag", 5], "клик выбирает ячейку и ничего не отправляет")
	var moved := _cell(5) + Vector2(6.0, 0.0)
	_button(_cell(5), MOUSE_BUTTON_LEFT, true)
	_move(moved)
	_button(moved, MOUSE_BUTTON_LEFT, false)
	_check(_events.is_empty() and not _view.is_dragging(), "смещение на 6 px не начинает перетаскивание")
	_click(_cell(12))
	_check(_view.selected_target().is_empty(), "клик по пустой ячейке снимает выбор")


func _check_right_click_actions() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_right_click(_cell(3))
	_view.resolve_action(true)
	_right_click(_cell(0))
	_view.resolve_action(true)
	_right_click(_slot("weapon"))
	_view.resolve_action(true)
	_right_click(_cell(7))
	_check(_events == [["equip", 3, ""], ["use", 0], ["unequip", "weapon", -1]],
		"правый клик: надеть без слота, использовать, снять без цели")
	_check(_messages.back() == ["Этот предмет нельзя использовать", false], "предмет без действия объясняет почему серым, без красного")
	_check(_colored == [["Надето: Простой лук", RULES.GOOD_COLOR], ["Использовано: Зелье здоровья", RULES.GOOD_COLOR],
		["Снято: Короткий меч", RULES.TEXT_DIM_COLOR], ["Этот предмет нельзя использовать", RULES.TEXT_DIM_COLOR]],
		"правый клик: надето и использовано зелёным, снято и отказ «нельзя использовать» приглушённым")


func _check_delete_confirm() -> void:
	_events.clear()
	_messages.clear()
	_colored.clear()
	_click(_cell(7))
	_key(KEY_DELETE)
	_check(_events.is_empty() and _view.drop_confirm_active(), "первый Delete просит подтверждения и не выбрасывает")
	_check(_messages.back() == ["Нажмите «Точно?», чтобы выбросить: Дубовая доска", true], "подтверждение показано красным")
	_check(_colored.back() == ["Нажмите «Точно?», чтобы выбросить: Дубовая доска", RULES.BAD_COLOR], "подтверждение окрашено как отказ")
	_key(KEY_DELETE)
	_check(_events == [["drop", 7]] and not _view.drop_confirm_active(), "второй Delete выбрасывает ячейку")
	_check(_messages.back() == ["Нажмите «Точно?», чтобы выбросить: Дубовая доска", true], "до ответа текста «Выброшено» нет")
	_view.resolve_action(true)
	_check(_messages.back() == ["Выброшено: Дубовая доска", false], "после ответа показан текст «Выброшено»")
	_check(_colored.back() == ["Выброшено: Дубовая доска", RULES.TEXT_DIM_COLOR], "«Выброшено» приглушённым, как в Python")
	_key(KEY_DELETE)
	_view._on_drop_confirm_timeout()
	_check(not _view.drop_confirm_active(), "по истечении 3 секунд подтверждение сбрасывается")
	_key(KEY_DELETE)
	_check(_events.size() == 1 and _view.drop_confirm_active(), "после сброса следующий Delete снова просит подтверждения")
	_click(_cell(5))
	_check(not _view.drop_confirm_active(), "выбор другой ячейки сбрасывает подтверждение, как в Python")
	_click(_slot("weapon"))
	_key(KEY_DELETE)
	_check(not _view.drop_confirm_active() and _events.size() == 1, "Delete по экипировке ничего не делает")


func _check_highlight_while_dragging() -> void:
	_events.clear()
	_button(_cell(5), MOUSE_BUTTON_LEFT, true)
	_move(_cell(5) + Vector2(20.0, 0.0))
	_check(_view.is_dragging() and _view.highlight_slot() == "head", "при перетаскивании шлема подсвечен слот головы")
	_move(_slot("head"))
	_button(_slot("head"), MOUSE_BUTTON_LEFT, false)
	_check(_events == [["equip", 5, "head"]], "отпускание над слотом головы: equip_requested(5, head)")
	_check(_view.highlight_slot() == "", "подсветка гаснет после отпускания")
	_view.resolve_action(true)


func _check_state_update() -> void:
	_click(_cell(7))
	_selection_changes = 0
	_view.set_items([_item(0, POTION), _item(3, BOW)], {"weapon": SWORD}, 50)
	_check(_view.selected_target().is_empty() and _selection_changes > 0, "обновление состояния сбрасывает выбор опустевшей ячейки")
	_check(_view.item_at(["equip", "weapon"]).get("name") == "Короткий меч" and _view.item_at(["bag", 7]).is_empty(),
		"предметы читаются по ячейкам и слотам")
	_check(str(_view.tooltip_lines_at(_cell(3))[0][0]) == "Простой лук", "подсказка по наведению начинается с названия предмета")


func _check_pending_protocol() -> void:
	_events.clear()
	_messages.clear()
	_drag(_cell(0), _cell(9))
	_check(_events == [["move", 0, 9]] and _messages.is_empty(), "перенос уходит владельцу, текста до ответа нет")
	_view.resolve_action(false)
	_check(_view.selected_target() == ["bag", 0] and _messages.is_empty(), "ошибка сервера: выбор остаётся у источника, текста нет")
	_drag(_cell(0), _cell(9))
	_check(_events.size() == 2 and _events[1] == ["move", 0, 9], "после ошибки перенос снова уходит")
	_drag(_cell(3), _slot("weapon"))
	_check(_events.size() == 2 and _messages.back() == ["Подождите завершения текущего запроса.", true],
		"пока перенос ждёт ответа, новое действие не уходит и объясняет почему")
	_check(_colored.back() == ["Подождите завершения текущего запроса.", RULES.BAD_COLOR], "«Подождите» окрашено как отказ")
	_view.resolve_action(true)
	_check(_view.selected_target() == ["bag", 9] and _messages.back() == ["", false], "успешный перенос: выбор на цели, строка очищается")
	_drag(_cell(3), _slot("weapon"))
	_check(_events.size() == 3 and _events[2] == ["equip", 3, "weapon"], "после ответа следующее действие уходит")
	_view.resolve_action(true)


func _check_draw_pass() -> void:
	_button(_cell(0), MOUSE_BUTTON_LEFT, true)
	_move(_cell(0) + Vector2(30.0, 0.0))
	await get_tree().process_frame
	await get_tree().process_frame
	_check(_view.is_dragging(), "перерисовка с призраком перетаскиваемого предмета проходит")
	_button(_cell(0) + Vector2(30.0, 0.0), MOUSE_BUTTON_LEFT, false)
	await get_tree().process_frame
	_check(not _view.is_dragging(), "перерисовка после отпускания проходит")


func _connect_signals() -> void:
	_view.move_requested.connect(func(from_slot: int, to_slot: int) -> void: _events.append(["move", from_slot, to_slot]))
	_view.equip_requested.connect(func(slot_index: int, slot: String) -> void: _events.append(["equip", slot_index, slot]))
	_view.unequip_requested.connect(func(slot: String, target_slot: int) -> void: _events.append(["unequip", slot, target_slot]))
	_view.use_requested.connect(func(slot_index: int) -> void: _events.append(["use", slot_index]))
	_view.drop_requested.connect(func(slot_index: int) -> void: _events.append(["drop", slot_index]))
	_view.message_requested.connect(func(text: String, is_error: bool) -> void: _messages.append([text, is_error]))
	_view.selection_changed.connect(func(_target: Array) -> void: _selection_changes += 1)
	_view.message_colored.connect(func(text: String, color: Color) -> void: _colored.append([text, color]))


func _item(slot_index: int, data: Dictionary) -> Dictionary:
	var item := data.duplicate()
	item["slot_index"] = slot_index
	return item


func _cell(index: int) -> Vector2:
	return _view.cell_rect(index).get_center()


func _slot(slot: String) -> Vector2:
	return _view.slot_rect(slot).get_center()


func _button(point: Vector2, button: MouseButton, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = pressed
	event.position = point
	_view.gui_input.emit(event)


func _move(point: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	_view.gui_input.emit(event)


func _click(point: Vector2) -> void:
	_button(point, MOUSE_BUTTON_LEFT, true)
	_button(point, MOUSE_BUTTON_LEFT, false)


func _right_click(point: Vector2) -> void:
	_button(point, MOUSE_BUTTON_RIGHT, true)
	_button(point, MOUSE_BUTTON_RIGHT, false)


func _drag(from_point: Vector2, to_point: Vector2) -> void:
	_button(from_point, MOUSE_BUTTON_LEFT, true)
	_move(to_point)
	_button(to_point, MOUSE_BUTTON_LEFT, false)


func _key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	_view.gui_input.emit(event)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
