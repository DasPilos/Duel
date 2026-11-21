extends Node

const HISTORY_RULES = preload("res://scripts/map_editor_history_rules.gd")


class RedoEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "tower"
		_build_ui()


var editor: RedoEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	editor = RedoEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
		"rock": {"item_key": "rock", "kind": "object", "category": "rock"},
	}
	editor._selected_item_key = "grass"
	editor._create_default_layers()
	editor._render_layers()
	_check_rules()
	_check_stroke_undo_redo()
	_check_shortcuts()
	_check_layer_history()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_redo_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _ground_cells() -> Dictionary:
	return editor._layers[0]["cells"]


func _cell_position(cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom


func _paint(cell: Vector2i) -> void:
	editor._begin_canvas_stroke(_cell_position(cell), MOUSE_BUTTON_LEFT)
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)


func _press(keycode: Key, ctrl := true, shift := false) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	event.shift_pressed = shift
	editor._unhandled_key_input(event)


func _check_rules() -> void:
	var undo: Array = []
	var redo: Array = [{"n": -1}]
	for index in range(105):
		HISTORY_RULES.record(undo, redo, {"n": index}, 100)
	_check(undo.size() == 100 and int(undo[0]["n"]) == 5, "Лимит истории: остаются последние 100 снимков")
	_check(redo.is_empty(), "Новое действие очищает стек повтора")
	var undone: Dictionary = HISTORY_RULES.undo(undo, redo, {"n": 999})
	_check(int(undone["n"]) == 104 and redo.size() == 1 and int(redo[0]["n"]) == 999, "Отмена переносит текущее состояние в повтор")
	var redone: Dictionary = HISTORY_RULES.redo(undo, redo, {"n": 104}, 100)
	_check(int(redone["n"]) == 999 and redo.is_empty() and int(undo[-1]["n"]) == 104, "Повтор возвращает отменённое состояние в историю")
	_check(HISTORY_RULES.undo([], [], {"n": 1}).is_empty() and HISTORY_RULES.redo([], [], {"n": 1}, 100).is_empty(), "Пустые стеки ничего не возвращают")


func _check_stroke_undo_redo() -> void:
	_paint(Vector2i(1, 1))
	_paint(Vector2i(2, 1))
	_check(_ground_cells().size() == 2 and _ground_cells().get("2:1") == "grass", "Два мазка кистью ставят две клетки земли")
	_check(editor._undo_stack.size() == 2 and editor._redo_stack.is_empty(), "Каждый мазок попадает в историю отмены")
	_check(not editor._undo_button.disabled and editor._redo_button.disabled, "Кнопки: отмена доступна, повтор пока нет")
	editor._undo_last_action()
	_check(_ground_cells().size() == 1 and not _ground_cells().has("2:1"), "Отмена убирает последний мазок")
	_check(editor._redo_stack.size() == 1 and not editor._redo_button.disabled, "После отмены мазок доступен для повтора")
	editor._redo_last_action()
	_check(_ground_cells().size() == 2 and _ground_cells().get("2:1") == "grass", "Повтор возвращает мазок")
	_check(editor._redo_stack.is_empty() and editor._redo_button.disabled, "После повтора стек повтора пуст")
	editor._undo_last_action()
	editor._undo_last_action()
	_check(_ground_cells().is_empty() and editor._redo_stack.size() == 2, "Две отмены очищают карту и откладывают два шага")
	_paint(Vector2i(5, 5))
	_check(editor._redo_stack.is_empty(), "Новый мазок очищает стек повтора")
	editor._redo_last_action()
	_check(_ground_cells().size() == 1 and _ground_cells().has("5:5"), "После нового мазка повтора старых шагов нет")
	editor._undo_last_action()
	editor._begin_canvas_stroke(_cell_position(Vector2i(9, 9)), MOUSE_BUTTON_RIGHT)
	editor._end_canvas_stroke(MOUSE_BUTTON_RIGHT)
	_check(editor._redo_stack.size() == 1 and editor._undo_stack.is_empty(), "Мазок без изменений не пишет историю и не очищает повтор")
	editor._redo_last_action()
	_check(_ground_cells().has("5:5"), "Повтор после мазка без изменений возвращает клетку")


func _check_shortcuts() -> void:
	var before := _ground_cells().size()
	_press(KEY_Y)
	_check(_ground_cells().size() == before and editor._status.text == "Нет действий для повтора.", "Ctrl+Y без повтора ничего не меняет")
	_press(KEY_Z)
	_check(_ground_cells().is_empty() and editor._status.text == "Последнее действие отменено.", "Ctrl+Z отменяет мазок")
	_press(KEY_Y)
	_check(_ground_cells().size() == 1 and editor._status.text == "Действие повторено.", "Ctrl+Y повторяет мазок")
	_press(KEY_Z)
	_check(_ground_cells().is_empty(), "Ctrl+Z снова убирает мазок")
	_press(KEY_Z, true, true)
	_check(_ground_cells().size() == 1 and _ground_cells().has("5:5"), "Ctrl+Shift+Z повторяет мазок")
	var key_no_ctrl := InputEventKey.new()
	key_no_ctrl.keycode = KEY_Z
	key_no_ctrl.pressed = true
	editor._unhandled_key_input(key_no_ctrl)
	_check(_ground_cells().size() == 1, "Z без Ctrl не отменяет действие")
	var key_held := InputEventKey.new()
	key_held.keycode = KEY_Z
	key_held.pressed = true
	key_held.echo = true
	key_held.ctrl_pressed = true
	editor._unhandled_key_input(key_held)
	_check(_ground_cells().size() == 1, "Повтор клавиши (echo) не отменяет действие второй раз")
	var key_russian := InputEventKey.new()
	key_russian.keycode = KEY_NONE
	key_russian.physical_keycode = KEY_Z
	key_russian.pressed = true
	key_russian.ctrl_pressed = true
	editor._unhandled_key_input(key_russian)
	_check(_ground_cells().is_empty(), "Ctrl+Z работает на русской раскладке по физической клавише")


func _check_layer_history() -> void:
	var ground_id := int(editor._layers[0]["id"])
	editor._set_layer_visibility(ground_id, false)
	_check(not bool(editor._get_layer(ground_id)["visible"]), "Скрытие слоя записывается в историю")
	editor._undo_last_action()
	_check(bool(editor._get_layer(ground_id)["visible"]) and not editor._redo_stack.is_empty(), "Отмена возвращает видимость слоя и откладывает её для повтора")
	var object_id := int(editor._layers[1]["id"])
	var redo_depth := editor._redo_stack.size()
	var placed := editor._move_layer_next_to(ground_id, object_id, true)
	_check(not placed and editor._redo_stack.size() == redo_depth, "Перестановка без изменения порядка не трогает стек повтора")
	editor._redo_last_action()
	_check(not bool(editor._get_layer(ground_id)["visible"]), "Повтор возвращает скрытие слоя")
	_check(editor._redo_button.disabled, "После повтора кнопка повтора отключена")
