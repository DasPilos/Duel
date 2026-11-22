extends Node

const SELECTION_RULES = preload("res://scripts/map_editor_selection_rules.gd")


class SelectionEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: SelectionEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	editor = SelectionEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
		"sand": {"item_key": "sand", "kind": "ground", "category": "ground"},
		"rock": {"item_key": "rock", "kind": "object", "category": "rock"},
	}
	editor._map_width.value = 16
	editor._map_height.value = 16
	_check_rules()
	_check_tools_and_keys()
	_check_rectangle_select()
	_check_move_and_undo()
	_check_move_edge()
	_check_delete()
	_check_copy_paste()
	_check_cut()
	_check_locked_and_hidden_layers()
	_check_escape_and_deselect()
	_check_paste_errors()
	await _check_draw()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_selection_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _reset() -> void:
	editor._create_default_layers()
	editor._render_layers()
	editor._layers[0]["cells"] = {"2:2": "grass", "3:2": "grass", "2:3": "grass", "3:3": "grass", "6:6": "sand"}
	editor._layers[1]["cells"] = {"2:3": "rock"}
	editor._layers[2]["cells"] = {"2:2": "animal|wolf"}
	editor._selection = Rect2i()
	editor._stamp_buffer = {}
	editor._select_tool("brush")


func _cells(index: int) -> Dictionary:
	return editor._layers[index]["cells"]


func _cell_position(cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom


func _click(cell: Vector2i, button: MouseButton) -> void:
	editor._begin_canvas_stroke(_cell_position(cell), button)
	editor._end_canvas_stroke(button)


func _drag(from: Vector2i, to: Vector2i) -> void:
	editor._begin_canvas_stroke(_cell_position(from), MOUSE_BUTTON_LEFT)
	editor._paint_canvas_drag_at(_cell_position(to))
	editor._end_canvas_stroke(MOUSE_BUTTON_LEFT)


func _press(keycode: Key, ctrl := false) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	editor._unhandled_key_input(event)


func _check_rules() -> void:
	_check(SELECTION_RULES.rect_between(Vector2i(4, 4), Vector2i(1, 2)) == Rect2i(1, 2, 4, 3), "Рамка нормализуется в любом направлении")
	_check(SELECTION_RULES.contains(Rect2i(1, 2, 4, 3), Vector2i(4, 4)) and not SELECTION_RULES.contains(Rect2i(1, 2, 4, 3), Vector2i(5, 2)), "Рамка включает правый нижний угол и не включает клетку за ним")
	_check(not SELECTION_RULES.contains(Rect2i(), Vector2i.ZERO), "Пустое выделение никого не содержит")
	_check(SELECTION_RULES.parse_key("12:7") == Vector2i(12, 7) and SELECTION_RULES.parse_key("bad") == Vector2i(-1, -1), "Ключ клетки разбирается в координаты")
	var layer := {"id": 1, "type": "tile", "cells": {"0:0": "grass", "1:1": "sand", "9:9": "grass"}}
	var block: Dictionary = SELECTION_RULES.copy([layer], Rect2i(0, 0, 2, 2))
	_check(int(block["count"]) == 2 and int(block["w"]) == 2 and block["parts"][0]["cells"].size() == 2, "Копия хранит клетки выделения со смещением от угла")
	_check(SELECTION_RULES.copy([layer], Rect2i()).is_empty(), "Копия пустого выделения пуста")
	var moved: Dictionary = SELECTION_RULES.move([layer], Rect2i(0, 0, 2, 2), Vector2i(1, 1), Vector2i(4, 4))
	_check(int(moved["count"]) == 2 and layer["cells"] == {"1:1": "grass", "2:2": "sand", "9:9": "grass"}, "Перенос сначала убирает исходные клетки, потом ставит новые")
	var refused: Dictionary = SELECTION_RULES.move([layer], Rect2i(1, 1, 2, 2), Vector2i(3, 0), Vector2i(4, 4))
	_check(refused["error"] == "Выделение выходит за край карты" and layer["cells"] == {"1:1": "grass", "2:2": "sand", "9:9": "grass"}, "Перенос за край карты отменяется целиком")
	_check(SELECTION_RULES.delete([layer], Rect2i(1, 1, 8, 8)) == 2 and layer["cells"] == {"9:9": "grass"}, "Удаление убирает только клетки внутри выделения")


func _check_tools_and_keys() -> void:
	_reset()
	_press(KEY_V)
	_check(editor._active_tool == "select" and editor._select_button.button_pressed and not editor._brush_button.button_pressed, "Клавиша V включает выделение")
	_press(KEY_V, true)
	_check(editor._active_tool == "select" and editor._status.text.begins_with("Буфер пуст"), "Ctrl+V без буфера не включает вставку")
	_check(editor._active_tool == "select" and editor._select_button.button_pressed and not editor._stamp_button.button_pressed, "Кнопка вставки откатывается, если буфер пуст")
	editor._select_tool("brush")


func _check_rectangle_select() -> void:
	_reset()
	_press(KEY_V)
	_drag(Vector2i(1, 1), Vector2i(4, 4))
	_check(editor._selection == Rect2i(1, 1, 4, 4), "Протянутая рамка становится выделением")
	_check(editor._undo_stack.is_empty(), "Выделение не попадает в историю отмены")
	_click(Vector2i(0, 0), MOUSE_BUTTON_RIGHT)
	_check(not editor._selection.has_area(), "Правая кнопка в режиме выделения снимает выделение")
	_drag(Vector2i(4, 4), Vector2i(1, 1))
	_check(editor._selection == Rect2i(1, 1, 4, 4), "Рамка, протянутая назад, нормализуется")


func _check_move_and_undo() -> void:
	_reset()
	_press(KEY_V)
	_drag(Vector2i(1, 1), Vector2i(4, 4))
	_drag(Vector2i(2, 2), Vector2i(4, 2))
	_check(editor._selection == Rect2i(3, 1, 4, 4), "Выделение сдвинулось вместе с клетками")
	_check(_cells(0) == {"4:2": "grass", "5:2": "grass", "4:3": "grass", "5:3": "grass", "6:6": "sand"}, "Земля перенесена на две клетки вправо, песок не тронут")
	_check(_cells(1) == {"4:3": "rock"}, "Объект переехал вместе с выделением")
	_check(_cells(2) == {"2:2": "animal|wolf"}, "Животные не переносятся выделением")
	_check(editor._undo_stack.size() == 1, "Перенос записывается в историю одним действием")
	_press(KEY_Z, true)
	_check(_cells(0) == {"2:2": "grass", "3:2": "grass", "2:3": "grass", "3:3": "grass", "6:6": "sand"} and _cells(1) == {"2:3": "rock"}, "Отмена возвращает перенесённые клетки")
	_check(not editor._selection.has_area(), "Отмена сбрасывает выделение, как в Python")
	_press(KEY_Y, true)
	_check(_cells(0).has("4:2") and _cells(1) == {"4:3": "rock"}, "Повтор переносит клетки снова")


func _check_move_edge() -> void:
	_reset()
	_cells(0)["15:0"] = "grass"
	editor._selection = Rect2i(14, 0, 2, 1)
	_press(KEY_V)
	_drag(Vector2i(14, 0), Vector2i(15, 0))
	_check(editor._status.text == "Выделение выходит за край карты", "Перенос за край карты показывает ошибку")
	_check(_cells(0).has("15:0") and not _cells(0).has("16:0") and editor._selection == Rect2i(14, 0, 2, 1), "Перенос за край не меняет карту и выделение")
	_check(editor._undo_stack.is_empty(), "Отменённый перенос не попадает в историю")


func _check_delete() -> void:
	_reset()
	editor._selection = Rect2i(0, 0, 4, 4)
	_press(KEY_DELETE)
	_check(editor._status.text == "Удалено элементов: 5", "Delete сообщает число удалённых клеток")
	_check(_cells(0) == {"6:6": "sand"} and _cells(1).is_empty() and _cells(2) == {"2:2": "animal|wolf"}, "Delete убирает земля и объекты в выделении, животные остаются")
	_check(editor._undo_stack.size() == 1, "Удаление записывается в историю")
	_press(KEY_Z, true)
	_check(_cells(0).size() == 5 and _cells(1) == {"2:3": "rock"}, "Отмена возвращает удалённое")
	_press(KEY_Y, true)
	_check(_cells(0) == {"6:6": "sand"}, "Повтор снова удаляет")
	var undo_before: int = editor._undo_stack.size()
	_press(KEY_DELETE)
	_check(editor._undo_stack.size() == undo_before, "Delete без выделения ничего не делает")


func _check_copy_paste() -> void:
	_reset()
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_C, true)
	_check(editor._status.text == "Скопировано элементов: 5. Ctrl+V — вставить куском", "Копирование сообщает число клеток")
	_check(int(editor._stamp_buffer["count"]) == 5 and int(editor._stamp_buffer["w"]) == 2 and _cells(0).size() == 5, "Копия не меняет карту")
	_press(KEY_V, true)
	_check(editor._active_tool == "stamp" and editor._stamp_button.button_pressed, "Ctrl+V включает вставку куском")
	_click(Vector2i(8, 8), MOUSE_BUTTON_LEFT)
	_check(_cells(0).get("8:8") == "grass" and _cells(0).get("9:9") == "grass" and _cells(1).get("8:9") == "rock", "Кусок вставлен левым верхним углом в клетку курсора")
	_check(editor._selection == Rect2i(8, 8, 2, 2), "После вставки выделение становится вставленной областью")
	_check(editor._status.text == "Вставлено элементов: 5", "Вставка сообщает число клеток")
	_check(editor._undo_stack.size() == 1, "Вставка записывается в историю одним действием")
	_press(KEY_Z, true)
	_check(not _cells(0).has("8:8") and _cells(1) == {"2:3": "rock"}, "Отмена убирает вставленный кусок")
	_press(KEY_Y, true)
	_check(_cells(0).get("9:9") == "grass", "Повтор возвращает кусок")
	_click(Vector2i(12, 12), MOUSE_BUTTON_RIGHT)
	_check(editor._active_tool == "brush" and editor._brush_button.button_pressed, "Правая кнопка отменяет вставку и возвращает кисть")


func _check_cut() -> void:
	_reset()
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_X, true)
	_check(_cells(0) == {"6:6": "sand"} and _cells(1).is_empty() and int(editor._stamp_buffer["count"]) == 5, "Вырезание убирает клетки и кладёт их в буфер")
	_check(editor._status.text == "Вырезано. Ctrl+V — вставить куском", "Вырезание сообщает о буфере")
	_check(editor._undo_stack.size() == 1, "Вырезание записывается в историю одним действием")
	_press(KEY_Z, true)
	_check(_cells(0).size() == 5 and _cells(1) == {"2:3": "rock"}, "Отмена возвращает вырезанное")


func _check_locked_and_hidden_layers() -> void:
	_reset()
	editor._layers[0]["locked"] = true
	editor._selection = Rect2i(0, 0, 16, 16)
	_press(KEY_C, true)
	_check(int(editor._stamp_buffer["count"]) == 1 and editor._stamp_buffer["parts"][0]["layer_type"] == "object", "Заблокированный слой не попадает в копию")
	_press(KEY_DELETE)
	_check(_cells(0).size() == 5 and _cells(1).is_empty() and editor._status.text == "Удалено элементов: 1", "Удаление не трогает заблокированный слой")
	_reset()
	editor._layers[0]["visible"] = false
	editor._selection = Rect2i(0, 0, 16, 16)
	_press(KEY_DELETE)
	_check(_cells(0).size() == 5 and _cells(1).is_empty(), "Скрытый слой не меняется выделением")
	editor._layers[0]["visible"] = true


func _check_escape_and_deselect() -> void:
	_reset()
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_ESCAPE)
	_check(not editor._selection.has_area(), "Esc снимает выделение")
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_D, true)
	_check(not editor._selection.has_area(), "Ctrl+D снимает выделение")
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_C, true)
	_press(KEY_V, true)
	_press(KEY_ESCAPE)
	_check(editor._active_tool == "brush", "Esc в режиме вставки возвращает кисть")
	editor._select_tool("brush")


func _check_paste_errors() -> void:
	_reset()
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_C, true)
	_press(KEY_V, true)
	var undo_before: int = editor._undo_stack.size()
	_click(Vector2i(15, 15), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Кусок выходит за край карты" and editor._undo_stack.size() == undo_before and _cells(0).size() == 5, "Кусок, не помещающийся у края, не вставляется")
	var stamp := {"w": 1, "h": 1, "count": 1, "parts": [{"layer_id": 1, "layer_type": "tile", "cells": [[0, 0, "grass"]]}]}
	var no_tile_layer := [{"id": 5, "type": "object", "cells": {}}]
	var skipped: Dictionary = SELECTION_RULES.paste(no_tile_layer, stamp, Vector2i(0, 0), Vector2i(16, 16), 5)
	_check(int(skipped["count"]) == 0 and int(skipped["skipped"]) == 1 and no_tile_layer[0]["cells"].is_empty(), "Без подходящего слоя кусок пропускается и считается")
	var fallback := [{"id": 7, "type": "tile", "cells": {}}, {"id": 8, "type": "tile", "cells": {}}]
	var target: Dictionary = SELECTION_RULES.paste_target(fallback, {"layer_id": 99, "layer_type": "tile", "cells": []}, 8)
	_check(int(target["id"]) == 8, "Если исходного слоя нет, кусок идёт на активный слой того же типа")
	target = SELECTION_RULES.paste_target(fallback, {"layer_id": 99, "layer_type": "tile", "cells": []}, 42)
	_check(int(target["id"]) == 7, "Если активный слой другого типа, кусок идёт на первый слой нужного типа")


func _check_draw() -> void:
	_reset()
	editor._selection = Rect2i(2, 2, 2, 2)
	_press(KEY_C, true)
	_press(KEY_V, true)
	editor._update_canvas_hover(_cell_position(Vector2i(5, 5)))
	_check(editor._hover_cell == Vector2i(5, 5), "Наведение запоминает клетку для призрака вставки")
	editor._canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	editor._on_canvas_mouse_exited()
	_check(editor._hover_cell == Vector2i(-1, -1), "Уход курсора с холста убирает призрак вставки")
	editor._select_tool("brush")
