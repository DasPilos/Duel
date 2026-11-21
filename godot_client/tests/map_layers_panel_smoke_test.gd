extends Node

const RULES = preload("res://scripts/layer_rules.gd")
const LIST_SCRIPT = preload("res://scripts/layer_list.gd")


class LayerEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "tower"
		_build_ui()


var editor: LayerEditor
var failed := false


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		failed = true
	return condition


func _frames(count: int) -> void:
	for _index in range(count):
		await get_tree().process_frame


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	if not failed:
		print("Layer panel smoke tests passed: numbering, colors, eye button, double-click rename, drag and order rules.")
	get_tree().quit(1 if failed else 0)


func _run() -> void:
	_check_rules()
	if failed:
		_finish()
		return
	editor = LayerEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await _frames(2)
	editor._version_overlay.visible = false
	editor.set_process(false)
	editor._create_default_layers()
	editor._render_layers()
	await _frames(3)
	_check_default_rows()
	if not failed:
		await _check_select_without_hiding()
	if not failed:
		await _check_eye_button()
	if not failed:
		await _check_rename()
	if not failed:
		_check_buttons_and_order_rules()
	if not failed:
		_check_drag_callbacks()
	if not failed:
		await _check_real_drag()
	if not failed:
		_check_groups()
	if not failed:
		_check_undo()
	if not failed:
		_check_load_normalizes()
	_finish()


func _layer_id(layer_name: String) -> int:
	for layer in editor._layers:
		if str(layer.get("name", "")) == layer_name:
			return int(layer["id"])
	return 0


func _row(layer_id: int) -> Dictionary:
	return editor._layer_list.get_row(layer_id)


func _titles() -> Array:
	var result: Array = []
	for layer_id in editor._layer_list.row_ids():
		result.append(str(_row(layer_id)["title"].text))
	return result


func _numbers() -> Array:
	var result: Array = []
	for layer_id in editor._layer_list.row_ids():
		result.append(str(_row(layer_id)["number"].text))
	return result


func _order_names() -> Array:
	var result: Array = []
	for layer in editor._layers:
		result.append(str(layer.get("name", "")))
	return result


func _luminance(color: Color) -> float:
	return color.r * 0.299 + color.g * 0.587 + color.b * 0.114


func _row_color(layer_id: int) -> Color:
	var style: StyleBoxFlat = _row(layer_id)["style"]
	return style.bg_color


func _check_rules() -> void:
	var layers: Array[Dictionary] = [
		{"id": 1, "type": "tile"},
		{"id": 2, "type": "group"},
		{"id": 3, "type": "object"},
		{"id": 4, "type": "tile"},
		{"id": 5, "type": "mob"},
	]
	var numbers: Dictionary = RULES.numbers(layers)
	_check(
		numbers == {1: 1, 2: 0, 3: 2, 4: 3, 5: 4},
		"Нумерация слоёв должна идти снизу вверх без учёта групп: %s" % str(numbers),
	)
	var changed: bool = RULES.normalize_order(layers)
	var ids: Array = []
	for layer in layers:
		ids.append(int(layer["id"]))
	_check(changed and ids == [1, 2, 4, 3, 5], "Слои тайлов должны уйти под объекты, группа остаться на месте: %s" % str(ids))
	_check(not RULES.normalize_order(layers), "Упорядоченный список не должен меняться повторно.")
	_check(RULES.insert_index(layers, "tile") == 3 and RULES.insert_index(layers, "object") == 5, "Неверное место вставки нового слоя.")
	var decorative_layers: Array[Dictionary] = [
		{"id": 1, "type": "tile"},
		{"id": 2, "type": "object"},
		{"id": 3, "type": "decorative"},
	]
	RULES.normalize_order(decorative_layers)
	_check(
		[int(decorative_layers[0]["id"]), int(decorative_layers[1]["id"]), int(decorative_layers[2]["id"])] == [1, 3, 2],
		"Декоративный слой должен работать как слой тайлов и оставаться под объектами.",
	)
	_check(
		RULES.insert_index(decorative_layers, "decorative") == 2,
		"Новый декоративный слой должен вставать над верхним слоем тайлов.",
	)
	_check(
		RULES.layer_color("decorative", 2) == RULES.layer_color("tile", 2),
		"Декоративный слой должен использовать цвет слоёв тайлов.",
	)
	var no_tiles: Array[Dictionary] = [{"id": 1, "type": "object"}]
	_check(RULES.insert_index(no_tiles, "tile") == 0, "Слой тайлов без тайлов должен вставать вниз.")
	var previous := _luminance(RULES.layer_color("tile", 1))
	for number in range(2, RULES.GRADIENT_LAYERS + 1):
		var current := _luminance(RULES.layer_color("tile", number))
		_check(current > previous, "Слой тайлов %d должен быть светлее предыдущего." % number)
		previous = current
	for layer_type in ["object", "animal", "mob"]:
		previous = _luminance(RULES.layer_color(layer_type, 1))
		for number in range(2, RULES.GRADIENT_LAYERS + 1):
			var current := _luminance(RULES.layer_color(layer_type, number))
			_check(current > previous, "Слой «%s» %d должен быть светлее предыдущего." % [layer_type, number])
			previous = current
	var dark: Color = RULES.layer_color("tile", 1)
	var bright: Color = RULES.layer_color("tile", 20)
	_check(
		dark.g > dark.r and dark.g > dark.b and bright.g > bright.r and bright.g > bright.b,
		"Слои тайлов должны быть зелёными.",
	)
	_check(_luminance(dark) < 0.25 and _luminance(bright) > 0.65, "Слой 1 должен быть тёмным, слой 20 — ярким.")
	_check(RULES.layer_color("tile", 20) == RULES.layer_color("tile", 40), "После слоя 20 цвет не должен меняться.")
	var object_hue: Color = RULES.layer_color("object", 3)
	_check(object_hue.b > object_hue.r and object_hue.b > object_hue.g, "Слои объектов должны быть синими.")
	var animal_hue: Color = RULES.layer_color("animal", 3)
	_check(animal_hue.r > animal_hue.b and animal_hue.g > animal_hue.b, "Слои животных должны быть жёлтыми.")
	var mob_hue: Color = RULES.layer_color("mob", 3)
	_check(mob_hue.r > mob_hue.g and mob_hue.r > mob_hue.b, "Слои мобов должны быть красными.")


func _check_default_rows() -> void:
	var list = editor._layer_list
	_check(list.get_script() == LIST_SCRIPT, "Панель слоёв должна быть списком строк, а не деревом.")
	_check(_titles() == ["Мобы", "Животные", "Объекты", "Земля"], "Верхний слой должен быть первой строкой списка: %s" % str(_titles()))
	_check(_numbers() == ["4", "3", "2", "1"], "Слои нумеруются снизу вверх: %s" % str(_numbers()))
	var ground_id := _layer_id("Земля")
	var ground_color := _row_color(ground_id)
	_check(ground_color == RULES.layer_color("tile", 1), "Слой тайлов 1 должен быть тёмно-зелёным.")
	_check(_row_color(_layer_id("Объекты")) == RULES.layer_color("object", 2), "Слой объектов должен быть синим по номеру 2.")
	_check(_row_color(_layer_id("Животные")) == RULES.layer_color("animal", 3), "Слой животных должен быть жёлтым по номеру 3.")
	_check(_row_color(_layer_id("Мобы")) == RULES.layer_color("mob", 4), "Слой мобов должен быть красным по номеру 4.")
	for layer_id in list.row_ids():
		var row := _row(layer_id)
		_check(row["eye"] is Button and row["number"] is Label, "В строке слоя нет кнопки скрытия и номера.")
		_check(not bool(row["eye"].get_meta("hidden")), "Видимый слой не должен подсвечивать кнопку скрытия.")
		var rect: Rect2 = row["panel"].get_global_rect()
		var list_rect: Rect2 = list.get_global_rect()
		_check(rect.size.x > 40.0 and list_rect.encloses(rect), "Строка слоя не помещается в панель: %s в %s" % [str(rect), str(list_rect)])
		_check(row["title"].size.x > 20.0, "Для названия слоя не осталось места.")
	var selected_style: StyleBoxFlat = _row(ground_id)["style"]
	_check(selected_style.border_width_left == 2 and selected_style.border_color.a > 0.9, "Выбранный слой должен иметь заметную рамку.")
	_check("Слой 1" in editor._layer_info.text and "тайлы" in editor._layer_info.text, "Под списком нет сведений о выбранном слое: %s" % editor._layer_info.text)
	_check(editor._layer_list.get_row(0).is_empty(), "Для неизвестного слоя не должно быть строки.")


func _row_point(layer_id: int) -> Vector2:
	var panel: Control = _row(layer_id)["panel"]
	var title: Control = _row(layer_id)["title"]
	return Vector2(title.get_global_rect().get_center().x, panel.get_global_rect().get_center().y)


func _move_mouse(point: Vector2) -> void:
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	get_viewport().push_input(motion, true)
	await _frames(2)


func _button_event(point: Vector2, pressed: bool, double_click := false) -> InputEventMouseButton:
	var button := InputEventMouseButton.new()
	button.button_index = MOUSE_BUTTON_LEFT
	button.pressed = pressed
	button.double_click = double_click
	button.position = point
	button.global_position = point
	button.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	return button


func _click(point: Vector2) -> void:
	await _move_mouse(point)
	for pressed in [true, false]:
		get_viewport().push_input(_button_event(point, pressed), true)
		await _frames(2)


func _double_click(point: Vector2) -> void:
	await _move_mouse(point)
	get_viewport().push_input(_button_event(point, true), true)
	await _frames(1)
	get_viewport().push_input(_button_event(point, false), true)
	await _frames(1)
	get_viewport().push_input(_button_event(point, true, true), true)
	await _frames(1)
	get_viewport().push_input(_button_event(point, false), true)
	await _frames(2)


func _check_select_without_hiding() -> void:
	var object_id := _layer_id("Объекты")
	var ground_id := _layer_id("Земля")
	var panel_before: Control = _row(object_id)["panel"]
	await _click(_row_point(object_id))
	_check(editor._active_layer_id == object_id, "Клик по строке не выбрал слой.")
	for layer in editor._layers:
		_check(bool(layer.get("visible", true)), "Выбор слоя не должен скрывать или показывать слой «%s»." % str(layer.get("name", "")))
	_check(_row(object_id)["panel"] == panel_before, "Строка слоя пересоздаётся при выборе, перетаскивание не сможет начаться.")
	var selected: StyleBoxFlat = _row(object_id)["style"]
	var previous: StyleBoxFlat = _row(ground_id)["style"]
	_check(selected.border_width_left == 2 and previous.border_width_left == 1, "Рамка выбранного слоя не переключилась.")
	_check(editor._undo_stack.is_empty(), "Выбор слоя не должен попадать в историю отмены.")
	_check("Слой 2" in editor._layer_info.text and "объекты" in editor._layer_info.text, "Сведения о выбранном слое не обновились: %s" % editor._layer_info.text)


func _check_eye_button() -> void:
	var object_id := _layer_id("Объекты")
	var ground_id := _layer_id("Земля")
	editor._active_layer_id = ground_id
	editor._render_layers()
	await _frames(2)
	var eye: Button = _row(object_id)["eye"]
	await _click(eye.get_global_rect().get_center())
	_check(not bool(editor._get_layer(object_id).get("visible", true)), "Кнопка не скрыла слой.")
	_check(bool(_row(object_id)["eye"].get_meta("hidden")), "Кнопка скрытого слоя не подсвечена.")
	_check(editor._active_layer_id == ground_id, "Кнопка скрытия не должна менять выбранный слой.")
	_check(_numbers() == ["4", "3", "2", "1"], "Скрытие не должно менять номера слоёв.")
	_check(not bool(_row(ground_id)["eye"].get_meta("hidden")), "Подсветилась кнопка не того слоя.")
	_check(_row_color(object_id) != RULES.layer_color("object", 2), "Скрытый слой должен выглядеть приглушённым.")
	_check("скрыт" in editor._status.text, "Статус не сообщает о скрытии слоя: %s" % editor._status.text)
	await _click(eye.get_global_rect().get_center())
	_check(bool(editor._get_layer(object_id).get("visible", false)), "Повторное нажатие не вернуло слой.")
	_check(not bool(_row(object_id)["eye"].get_meta("hidden")), "Подсветка кнопки не погасла.")
	_check(_row_color(object_id) == RULES.layer_color("object", 2), "Цвет показанного слоя не вернулся.")
	editor._undo_last_action()
	_check(not bool(editor._get_layer(object_id).get("visible", true)), "Ctrl+Z не отменил показ слоя.")
	editor._undo_last_action()
	_check(bool(editor._get_layer(object_id).get("visible", false)), "Ctrl+Z не отменил скрытие слоя.")
	_check(bool(_row(object_id)["eye"].get_meta("hidden")) == false, "После отмены кнопка показывает неверное состояние.")
	editor._active_layer_id = object_id
	editor._set_layer_visibility(object_id, false)
	_check(editor._active_layer_id != object_id and editor._is_layer_visible(editor._get_layer(editor._active_layer_id)), "Скрытый активный слой должен уступить выбор видимому.")
	editor._set_layer_visibility(object_id, true)
	editor._undo_stack.clear()
	editor._active_layer_id = ground_id
	editor._render_layers()


func _check_rename() -> void:
	var animal_id := _layer_id("Животные")
	var list = editor._layer_list
	var height_before: float = _row(animal_id)["panel"].size.y
	await _double_click(_row_point(animal_id))
	_check(editor._active_layer_id == animal_id, "Двойной клик должен выбирать слой.")
	_check(list.is_renaming(), "Двойной клик не открыл переименование.")
	var edit: LineEdit = _row(animal_id)["edit"]
	_check(edit.visible and edit.has_focus() and not _row(animal_id)["title"].visible, "Поле переименования не показано или не в фокусе.")
	_check(is_equal_approx(_row(animal_id)["panel"].size.y, height_before), "Строка меняет высоту при переименовании: %s → %s" % [str(height_before), str(_row(animal_id)["panel"].size.y)])
	_check(edit.text == "Животные", "В поле переименования должно стоять текущее название.")
	edit.text = "Звери"
	edit.text_submitted.emit("Звери")
	await _frames(1)
	_check(str(editor._get_layer(animal_id)["name"]) == "Звери", "Enter не применил новое название.")
	_check(not list.is_renaming() and not edit.visible and _row(animal_id)["title"].visible, "Поле переименования не закрылось.")
	_check(_titles()[1] == "Звери", "Список не показал новое название: %s" % str(_titles()))
	editor._undo_last_action()
	_check(str(editor._get_layer(animal_id)["name"]) == "Животные", "Ctrl+Z не вернул название слоя.")
	list.begin_rename(animal_id)
	edit = _row(animal_id)["edit"]
	edit.text = "Отмена"
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	edit.gui_input.emit(escape)
	_check(not list.is_renaming() and str(editor._get_layer(animal_id)["name"]) == "Животные", "Esc должен отменять переименование.")
	list.begin_rename(animal_id)
	edit = _row(animal_id)["edit"]
	edit.text = "   "
	edit.text_submitted.emit("   ")
	_check(str(editor._get_layer(animal_id)["name"]) == "Животные", "Пустое название не должно применяться.")
	list.begin_rename(animal_id)
	edit = _row(animal_id)["edit"]
	edit.text = "Фауна"
	edit.release_focus()
	await _frames(1)
	_check(str(editor._get_layer(animal_id)["name"]) == "Фауна", "Потеря фокуса должна применять название.")
	editor._undo_last_action()
	_check(str(editor._get_layer(animal_id)["name"]) == "Животные", "Ctrl+Z не вернул название после потери фокуса.")
	editor._undo_stack.clear()
	editor._active_layer_id = _layer_id("Земля")
	editor._render_layers()


func _check_buttons_and_order_rules() -> void:
	var ground_id := _layer_id("Земля")
	var object_id := _layer_id("Объекты")
	var animal_id := _layer_id("Животные")
	var mob_id := _layer_id("Мобы")
	editor._active_layer_id = animal_id
	editor._move_layer(1)
	_check(_order_names() == ["Земля", "Объекты", "Мобы", "Животные"], "«Вверх» должна поднимать слой: %s" % str(_order_names()))
	_check(_titles() == ["Животные", "Мобы", "Объекты", "Земля"] and _numbers() == ["4", "3", "2", "1"], "После подъёма список и номера не обновились: %s %s" % [str(_titles()), str(_numbers())])
	_check(_row_color(animal_id) == RULES.layer_color("animal", 4), "Цвет слоя не следует за номером.")
	editor._move_layer(-1)
	_check(_order_names() == ["Земля", "Объекты", "Животные", "Мобы"], "«Вниз» должна опускать слой: %s" % str(_order_names()))
	editor._active_layer_id = ground_id
	editor._move_layer(1)
	_check(_order_names() == ["Земля", "Объекты", "Животные", "Мобы"], "Слой тайлов поднялся выше слоя объектов.")
	_check("тайлов" in editor._status.text, "Нет пояснения, почему слой тайлов не поднимается: %s" % editor._status.text)
	editor._active_layer_id = object_id
	editor._move_layer(-1)
	_check(_order_names() == ["Земля", "Объекты", "Животные", "Мобы"], "Слой объектов опустился под слой тайлов.")
	editor._active_layer_id = mob_id
	editor._move_layer(1)
	_check(_order_names() == ["Земля", "Объекты", "Животные", "Мобы"], "Верхний слой не должен подниматься выше.")
	editor._layer_type.select(0)
	editor._layer_name.text = "Трава"
	editor._add_layer()
	_check(_order_names() == ["Земля", "Трава", "Объекты", "Животные", "Мобы"], "Новый слой тайлов должен встать над верхним слоем тайлов: %s" % str(_order_names()))
	var grass_id := _layer_id("Трава")
	_check(editor._active_layer_id == grass_id and _numbers() == ["5", "4", "3", "2", "1"], "Нумерация после добавления тайлов неверна: %s" % str(_numbers()))
	_check(_row_color(grass_id) == RULES.layer_color("tile", 2), "У нового слоя тайлов неверный цвет.")
	editor._layer_type.select(1)
	editor._layer_name.text = "Деревья"
	editor._add_layer()
	_check(_order_names() == ["Земля", "Трава", "Объекты", "Животные", "Мобы", "Деревья"], "Новый слой объектов должен встать наверх: %s" % str(_order_names()))
	var trees_id := _layer_id("Деревья")
	# Слой тайлов нельзя поднять выше слоя объектов, а объект — опустить под слой тайлов.
	var before := _order_names()
	var undo_size: int = editor._undo_stack.size()
	_check(not editor._move_layer_next_to(grass_id, trees_id, true), "Слой тайлов встал над слоем объектов.")
	_check(_order_names() == before, "После отказа порядок слоёв изменился.")
	_check("под слоями объектов" in editor._status.text, "Нет пояснения про порядок тайлов и объектов: %s" % editor._status.text)
	_check(not editor._move_layer_next_to(object_id, ground_id, false), "Слой объектов встал под слой тайлов.")
	_check(_order_names() == before, "После отказа порядок слоёв изменился (объект).")
	_check(editor._undo_stack.size() == undo_size, "Отказ от перемещения не должен попадать в историю: %d" % editor._undo_stack.size())
	# Частично допустимое перемещение: слой встаёт на границу тайлов и объектов.
	_check(editor._move_layer_next_to(ground_id, mob_id, true), "Слой тайлов не переместился внутри своей зоны.")
	_check(_order_names() == ["Трава", "Земля", "Объекты", "Животные", "Мобы", "Деревья"], "Слой тайлов должен встать на границу зон: %s" % str(_order_names()))
	_check("границу" in editor._status.text, "Нет пояснения про границу тайлов и объектов: %s" % editor._status.text)
	_check(_numbers() == ["6", "5", "4", "3", "2", "1"] and _titles()[5] == "Трава", "Номера после переноса неверны: %s %s" % [str(_titles()), str(_numbers())])
	_check(editor._move_layer_next_to(trees_id, grass_id, false), "Объект не встал на границу под слоями тайлов.")
	_check(_order_names() == ["Трава", "Земля", "Деревья", "Объекты", "Животные", "Мобы"], "Порядок объектов неверен: %s" % str(_order_names()))
	_check("границу" in editor._status.text, "Нет пояснения про границу для объекта: %s" % editor._status.text)
	var canvas_order: Array = []
	for layer in editor._layers:
		canvas_order.append(int(layer["id"]))
	var expected := [grass_id, ground_id, trees_id, object_id, animal_id, mob_id]
	_check(canvas_order == expected, "Холст рисует слои не в порядке номеров.")
	var serialized: Array = editor._serialize_editor_layers()["editor_layers"]
	var saved_ids: Array = []
	for layer in serialized:
		saved_ids.append(int(layer["id"]))
	_check(saved_ids == expected, "Порядок слоёв при сохранении не совпал с нумерацией.")
	editor._undo_stack.clear()


func _drag_data(layer_id: int) -> Dictionary:
	# Превью перетаскивания создаётся только в настоящем жесте, он проверяется ниже.
	return {"type": editor._layer_list.DRAG_TYPE, "layer_id": layer_id}


func _check_drag_callbacks() -> void:
	var list = editor._layer_list
	var trees_id := _layer_id("Деревья")
	var object_id := _layer_id("Объекты")
	var mob_id := _layer_id("Мобы")
	var data: Dictionary = _drag_data(trees_id)
	_check(int(data["layer_id"]) == trees_id, "Перетаскивание не вернуло данные слоя.")
	var target_panel: Control = _row(mob_id)["panel"]
	var height := target_panel.size.y
	_check(list._row_can_drop(Vector2(5, height * 0.25), data, mob_id, target_panel), "Строку слоя нельзя бросить на другую строку.")
	var style: StyleBoxFlat = _row(mob_id)["style"]
	_check(style.border_width_top == 3 and style.border_width_bottom == 0 and style.border_color == list.DROP_BORDER, "Верхняя половина строки должна показывать линию вставки сверху.")
	_check(list._row_can_drop(Vector2(5, height * 0.75), data, mob_id, target_panel), "Нижняя половина строки не принимает слой.")
	_check(style.border_width_top == 0 and style.border_width_bottom == 3, "Нижняя половина строки должна показывать линию вставки снизу.")
	_check(not list._row_can_drop(Vector2(5, 5), data, trees_id, _row(trees_id)["panel"]), "Слой нельзя бросить на самого себя.")
	_check(style.border_width_bottom != 3 and style.border_color != list.DROP_BORDER, "Линия вставки должна пропасть, когда курсор ушёл с целевой строки.")
	_check(not list._row_can_drop(Vector2(5, 5), "посторонние данные", mob_id, target_panel), "Список принял чужие данные перетаскивания.")
	_check(list._row_can_drop(Vector2(5, height * 0.25), data, mob_id, target_panel), "Строку снова нельзя бросить.")
	list.notification(Control.NOTIFICATION_DRAG_END)
	_check(style.border_width_top != 3 and style.border_color != list.DROP_BORDER, "Линия вставки осталась после конца перетаскивания.")
	var dropped: Array = []
	list.layer_dropped.connect(func(source: int, target: int, above: bool) -> void: dropped.append([source, target, above]))
	list._row_drop(Vector2(5, height * 0.75), data, object_id, _row(object_id)["panel"])
	_check(dropped == [[trees_id, object_id, false]], "Бросок строки не сообщил, куда вставить слой: %s" % str(dropped))
	_check(_order_names() == ["Трава", "Земля", "Деревья", "Объекты", "Животные", "Мобы"], "Бросок под слой, который уже ниже, не должен менять порядок.")
	list._row_drop(Vector2(5, height * 0.25), data, mob_id, target_panel)
	_check(_order_names() == ["Трава", "Земля", "Объекты", "Животные", "Мобы", "Деревья"], "Бросок на верхнюю половину верхней строки не поднял слой: %s" % str(_order_names()))
	_check(editor._active_layer_id == trees_id, "После перемещения должен быть выбран перенесённый слой.")
	_check(_numbers() == ["6", "5", "4", "3", "2", "1"] and _titles()[0] == "Деревья", "Номера после броска неверны: %s %s" % [str(_titles()), str(_numbers())])
	editor._undo_last_action()
	_check(_order_names() == ["Трава", "Земля", "Деревья", "Объекты", "Животные", "Мобы"], "Ctrl+Z не вернул порядок слоёв.")
	editor._undo_stack.clear()


func _check_real_drag() -> void:
	await _frames(3)
	var trees_id := _layer_id("Деревья")
	var mob_id := _layer_id("Мобы")
	var start := _row_point(trees_id)
	var target_rect: Rect2 = _row(mob_id)["panel"].get_global_rect()
	var finish := Vector2(start.x, target_rect.position.y + target_rect.size.y * 0.2)
	await _move_mouse(start)
	get_viewport().push_input(_button_event(start, true), true)
	await _frames(2)
	var steps := 8
	var previous := start
	for step in range(1, steps + 1):
		var point := start.lerp(finish, float(step) / steps)
		var motion := InputEventMouseMotion.new()
		motion.position = point
		motion.global_position = point
		motion.relative = point - previous
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		previous = point
		get_viewport().push_input(motion, true)
		await _frames(1)
	_check(get_viewport().gui_is_dragging(), "Движение мыши с зажатой кнопкой не начало перетаскивание слоя.")
	get_viewport().push_input(_button_event(finish, false), true)
	await _frames(3)
	_check(not get_viewport().gui_is_dragging(), "Перетаскивание не завершилось после отпускания кнопки.")
	_check(_order_names() == ["Трава", "Земля", "Объекты", "Животные", "Мобы", "Деревья"], "Перетаскивание мышью не подняло слой над мобами: %s" % str(_order_names()))
	_check(editor._active_layer_id == trees_id, "Перетащенный слой должен стать выбранным.")
	editor._undo_last_action()
	_check(_order_names() == ["Трава", "Земля", "Деревья", "Объекты", "Животные", "Мобы"], "Ctrl+Z не отменил перетаскивание.")
	editor._undo_stack.clear()


func _check_groups() -> void:
	var before := _numbers()
	editor._layer_type.select(2)
	editor._layer_name.text = "Папка"
	editor._add_layer()
	var group_id := _layer_id("Папка")
	_check(editor._active_layer_id == group_id and str(editor._get_layer(group_id)["type"]) == "group", "Группа не создана.")
	_check(_row(group_id)["number"].text == "" and _numbers().filter(func(text: String) -> bool: return text != "") == before, "Группа не должна получать номер и менять номера слоёв: %s" % str(_numbers()))
	_check(_row_color(group_id) == RULES.GROUP_COLOR, "Группа должна иметь свой цвет.")
	editor._layer_type.select(2)
	editor._layer_name.text = "Вложенная"
	editor._add_layer()
	var child_id := _layer_id("Вложенная")
	var ids: Array = editor._layer_list.row_ids()
	_check(ids.find(child_id) == ids.find(group_id) + 1, "Вложенная группа должна идти сразу под своей группой: %s" % str(_titles()))
	_check(float(_row(child_id)["indent"].custom_minimum_size.x) > float(_row(group_id)["indent"].custom_minimum_size.x), "Вложенная группа должна быть сдвинута вправо.")
	_check(not editor._layer_list._row_can_drop(Vector2(5, 3), {"type": "layer_row", "layer_id": child_id}, _layer_id("Земля"), _row(_layer_id("Земля"))["panel"]), "Слой нельзя переносить между разными группами.")
	editor._active_layer_id = group_id
	editor._delete_layer()
	_check(_layer_id("Папка") == 0 and _layer_id("Вложенная") == 0, "Удаление группы не удалило вложенные слои.")
	_check(_titles().size() == 6, "Список слоёв не обновился после удаления группы: %s" % str(_titles()))
	editor._undo_last_action()
	_check(_layer_id("Папка") != 0 and _layer_id("Вложенная") != 0, "Ctrl+Z не вернул удалённую группу.")
	editor._undo_stack.clear()
	editor._active_layer_id = _layer_id("Папка")
	editor._delete_layer()
	editor._undo_stack.clear()


func _check_undo() -> void:
	var ground_id := _layer_id("Земля")
	editor._active_layer_id = ground_id
	var before := _order_names()
	editor._toggle_layer_lock()
	_check(bool(_row(ground_id)["lock"].visible) and "заблокирован" in editor._layer_info.text, "Блокировка слоя не видна в списке.")
	editor._undo_last_action()
	_check(not bool(editor._get_layer(ground_id)["locked"]) and not bool(_row(ground_id)["lock"].visible), "Ctrl+Z не снял блокировку.")
	editor._duplicate_layer()
	_check(_order_names().size() == before.size() + 1 and editor._layers[editor._layer_index(ground_id) + 1]["name"] == "Земля — копия", "Копия слоя не создана над оригиналом: %s" % str(_order_names()))
	editor._undo_last_action()
	_check(_order_names() == before, "Ctrl+Z не убрал копию слоя.")
	editor._delete_layer()
	_check(_layer_id("Земля") == 0, "Слой не удалён.")
	editor._undo_last_action()
	_check(_order_names() == before and editor._active_layer_id == ground_id, "Ctrl+Z не вернул удалённый слой и выбор.")
	editor._layer_type.select(0)
	editor._layer_name.text = "Новый"
	editor._add_layer()
	editor._undo_last_action()
	_check(_order_names() == before, "Ctrl+Z не убрал добавленный слой.")
	_check(editor._layer_list.row_ids().size() == before.size(), "Строки списка не соответствуют слоям после отмены.")
	editor._layer_type.select(5)
	editor._layer_name.text = "Декор"
	var expected_decorative_index: int = RULES.insert_index(editor._layers, "decorative")
	editor._add_layer()
	var decorative_id := _layer_id("Декор")
	_check(
		str(editor._get_layer(decorative_id).get("type", "")) == "decorative",
		"В редакторе должен создаваться отдельный декоративный тип слоя.",
	)
	_check(
		editor._layer_index(decorative_id) == expected_decorative_index,
		"Декоративный слой должен вставляться над тайлами и под слоями объектов.",
	)


func _check_load_normalizes() -> void:
	var stored: Array = [
		{"id": 7, "name": "Камни", "type": "object", "parent_id": 0, "visible": true, "locked": false, "cells": [], "animal_settings": {}},
		{"id": 8, "name": "Песок", "type": "tile", "parent_id": 0, "visible": false, "locked": false, "cells": [], "animal_settings": {}},
		{"id": 9, "name": "Вода", "type": "tile", "parent_id": 0, "visible": true, "locked": true, "cells": [], "animal_settings": {}},
	]
	editor._load_map_payload({"id": 5, "name": "Старая карта", "map_w": 32, "map_h": 32, "editor_layers": stored})
	var names := _order_names()
	_check(names.slice(0, 3) == ["Песок", "Вода", "Камни"], "Слои тайлов после загрузки должны лежать под объектами: %s" % str(names))
	_check("под слои объектов" in editor._status.text, "Нет сообщения о перестановке слоёв: %s" % editor._status.text)
	_check(bool(_row(8)["eye"].get_meta("hidden")) and _row(9)["lock"].visible, "Скрытие и блокировка не восстановились из сохранения.")
	_check(_titles()[0] == "Мобы" and _numbers()[0] == str(names.size()), "Список после загрузки показан не сверху вниз: %s" % str(_titles()))
	var saved: Array = editor._serialize_editor_layers()["editor_layers"]
	_check(int(saved[0]["id"]) == 8 and int(saved[2]["id"]) == 7, "В сохранении слои идут не в порядке нумерации.")
