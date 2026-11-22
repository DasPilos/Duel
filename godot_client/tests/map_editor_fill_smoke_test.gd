extends Node

const FILL_RULES = preload("res://scripts/map_editor_fill_rules.gd")


class FillEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: FillEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	editor = FillEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
		"sand": {"item_key": "sand", "kind": "ground", "category": "ground"},
		"rock": {"item_key": "rock", "kind": "object", "category": "rock"},
	}
	editor._create_default_layers()
	editor._render_layers()
	editor._map_width.value = 16
	editor._map_height.value = 16
	_check_rules()
	_check_tool_switching()
	_check_fill_region()
	_check_fill_undo()
	_check_refusals()
	_check_single_atlas_tile()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_fill_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _ground_cells() -> Dictionary:
	return editor._layers[0]["cells"]


func _cell_position(cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom


func _click(cell: Vector2i, button: MouseButton) -> void:
	editor._begin_canvas_stroke(_cell_position(cell), button)
	editor._end_canvas_stroke(button)


func _press(keycode: Key, ctrl := false) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	editor._unhandled_key_input(event)


func _count_value(cells: Dictionary, key: String) -> int:
	var count := 0
	for value in cells.values():
		if str(value) == key:
			count += 1
	return count


func _check_rules() -> void:
	var wall := {"2:0": "sand", "2:1": "sand", "2:2": "sand", "2:3": "sand"}
	var filled: Array[Vector2i] = FILL_RULES.fill(wall, Vector2i(5, 4), Vector2i(0, 0), "grass")
	_check(filled.size() == 8 and wall.get("1:3") == "grass" and not wall.has("3:0"), "Заливка по правилам останавливается у песчаной стены и не выходит за неё")
	_check(FILL_RULES.fill(wall, Vector2i(5, 4), Vector2i(0, 0), "grass").is_empty(), "Заливка того же вида ничего не меняет")
	_check(FILL_RULES.fill(wall, Vector2i(5, 4), Vector2i(5, 0), "grass").is_empty(), "Клетка за краем карты не заливается")
	var sand_fill := FILL_RULES.fill(wall, Vector2i(5, 4), Vector2i(2, 0), "rock")
	_check(sand_fill.size() == 4 and wall.get("2:3") == "rock" and wall.get("1:0") == "grass", "Заливается только связанная область того же вида")
	var diagonal := {"1:0": "sand", "0:1": "sand"}
	_check(FILL_RULES.fill(diagonal, Vector2i(2, 2), Vector2i(0, 0), "grass").size() == 1 and not diagonal.has("1:1"), "Заливка идёт только по сторонам клетки, не по диагонали")


func _check_tool_switching() -> void:
	_check(editor._active_tool == "brush" and editor._brush_button.button_pressed, "По умолчанию активна кисть")
	_press(KEY_F, true)
	_check(editor._active_tool == "brush", "Ctrl+F не переключает инструмент")
	_press(KEY_F)
	_check(editor._active_tool == "fill" and editor._fill_button.button_pressed, "Клавиша F включает заливку")
	_check(not editor._brush_button.button_pressed and not editor._auto_brush_button.button_pressed, "Заливка снимает кисть и автокисть в группе")
	_press(KEY_B)
	_check(editor._active_tool == "brush" and editor._brush_button.button_pressed and not editor._fill_button.button_pressed, "Клавиша B возвращает кисть")
	editor._fill_button.pressed.emit()
	_check(editor._active_tool == "fill", "Кнопка «Заливка» включает инструмент заливки")
	editor._select_tool("brush")


func _check_fill_region() -> void:
	editor._selected_item_key = "sand"
	for y in range(16):
		_click(Vector2i(2, y), MOUSE_BUTTON_LEFT)
	_check(_ground_cells().size() == 16, "Песчаная стена из шестнадцати клеток поставлена кистью")
	editor._select_tool("fill")
	editor._selected_item_key = "grass"
	_click(Vector2i(0, 0), MOUSE_BUTTON_LEFT)
	_check(_count_value(_ground_cells(), "grass") == 32 and _ground_cells().get("1:15") == "grass", "Заливка стартует слева и покрывает тридцать две клетки левой области")
	_check(editor._status.text == "Залито клеток: 32", "После заливки статус показывает число клеток")
	_check(_count_value(_ground_cells(), "sand") == 16 and not _ground_cells().has("3:0"), "Песчаная стена и правая область не тронуты")
	_check(editor._undo_stack.size() == 17, "Заливка записывается в историю одним действием")


func _check_fill_undo() -> void:
	_press(KEY_Z, true)
	_check(_ground_cells().size() == 16 and _count_value(_ground_cells(), "grass") == 0, "Ctrl+Z отменяет заливку целиком")
	_press(KEY_Y, true)
	_check(_ground_cells().size() == 48 and _count_value(_ground_cells(), "grass") == 32, "Ctrl+Y повторяет заливку")


func _check_refusals() -> void:
	var before := _ground_cells().size()
	var undo_before: int = editor._undo_stack.size()
	_click(Vector2i(0, 0), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Область уже этого вида" and editor._undo_stack.size() == undo_before, "Заливка того же вида сообщает об этом и не пишет историю")
	editor._selected_item_key = "rock"
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Заливка работает только с землёй" and _ground_cells().size() == before, "Объект нельзя залить, статус говорит об этом")
	editor._selected_item_key = "grass"
	editor._active_layer_id = int(editor._layers[1]["id"])
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Заливка работает только на слое тайлов." and editor._layers[1]["cells"].is_empty(), "На слое объектов заливка не работает")
	editor._active_layer_id = int(editor._layers[0]["id"])
	editor._layers[0]["locked"] = true
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(_ground_cells().size() == before, "Заблокированный слой не заливается")
	editor._layers[0]["locked"] = false
	editor._active_custom_group_id = "server_group"
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text.begins_with("Серверную группу тайлов") and _ground_cells().size() == before, "Серверная группа тайлов не заливается")
	editor._active_custom_group_id = ""
	editor._animal_groups_by_key = {"animal_wolf": {"kind": "animal"}}
	editor._selected_item_key = "animal_wolf"
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Заливка работает только с землёй" and _ground_cells().size() == before, "Животное нельзя залить")
	editor._animal_groups_by_key = {}
	var atlas_key: String = editor._encode_atlas_cell("res://assets/base_tails/tile.png", Vector2i(0, 0))
	editor._selected_item_key = atlas_key
	editor._selected_atlas_region = Rect2i(0, 0, 2, 1)
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text.begins_with("Заливка работает одним тайлом") and _ground_cells().size() == before, "Блок тайлов листа не заливается, нужен один тайл")
	editor._selected_item_key = "grass"
	editor._selected_atlas_region = Rect2i()
	_click(Vector2i(0, 0), MOUSE_BUTTON_RIGHT)
	_check(not _ground_cells().has("0:0") and _ground_cells().size() == before - 1, "Правая кнопка в режиме заливки стирает клетку")


func _check_single_atlas_tile() -> void:
	var atlas_key: String = editor._encode_atlas_cell("res://assets/base_tails/tile.png", Vector2i(3, 4))
	editor._selected_item_key = atlas_key
	editor._selected_atlas_region = Rect2i(Vector2i(3, 4), Vector2i.ONE)
	_click(Vector2i(5, 5), MOUSE_BUTTON_LEFT)
	_check(editor._status.text == "Залито клеток: 208" and _ground_cells().get("5:5") == atlas_key and _ground_cells().get("15:15") == atlas_key, "Один тайл листа заливает всю пустую область справа")
	_check(_ground_cells().get("2:0") == "sand" and _ground_cells().get("2:15") == "sand", "Заливка атласом не выходит за песчаную стену")
