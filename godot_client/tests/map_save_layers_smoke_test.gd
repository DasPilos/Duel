extends Node


class SaveEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: SaveEditor
var failed := false


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		failed = true
	return condition


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	if not failed:
		print("Map save smoke tests passed: overlapping tile layers merge into unique server cells, every layer is kept in the draft.")
	get_tree().quit(1 if failed else 0)


func _run() -> void:
	editor = SaveEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	_prepare_layers()
	_check_overlapping_tile_layers()
	_check_status_after_save()
	_finish()


func _prepare_layers() -> void:
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "editor_layer": 1},
		"sand": {"item_key": "sand", "kind": "ground", "editor_layer": 1},
		"foam": {"item_key": "foam", "kind": "ground", "editor_layer": 2},
		"rock": {"item_key": "rock", "kind": "object"},
	}
	var lower: Dictionary = editor._new_layer("Нижний", editor.LAYER_TILE, 0)
	var upper: Dictionary = editor._new_layer("Верхний", editor.LAYER_TILE, 0)
	var things: Dictionary = editor._new_layer("Объекты", editor.LAYER_OBJECT, 0)
	lower["cells"] = {"1:1": "grass", "2:1": "grass", "4:4": "local_only_tile"}
	upper["cells"] = {"1:1": "sand", "3:3": "foam"}
	upper["visible"] = false
	things["cells"] = {"5:5": "rock"}
	editor._layers.clear()
	editor._layers.append(lower)
	editor._layers.append(upper)
	editor._layers.append(things)


func _slot_map(cells: Array) -> Dictionary:
	var result := {}
	for cell in cells:
		result["%s|%d|%d" % [cell["layer"], int(cell["x"]), int(cell["y"])]] = str(cell["key"])
	return result


func _check_overlapping_tile_layers() -> void:
	editor._mode = "front_line"
	var map_payload: Dictionary = editor._build_map_payload()
	_check(
		map_payload.get("mode", "") == "front_line",
		"Сохранение карты должно сохранять выбранный режим Front Line.",
	)
	var serialized: Dictionary = editor._serialize_editor_layers()
	var catalog_cells: Array = serialized["catalog_cells"]
	var slots := _slot_map(catalog_cells)
	_check(
		slots.size() == catalog_cells.size(),
		"В списке клеток для сервера остались дубликаты (слой хранения, x, y): сервер отклонит такое сохранение.",
	)
	_check(
		slots == {
			"ground|1|1": "sand",
			"ground|2|1": "grass",
			"overlay|3|3": "foam",
			"object|5|5": "rock",
		},
		"Клетки для сервера: верхний слой должен перекрывать нижний, локальные тайлы не отправляются. Получено: %s" % str(slots),
	)
	_check(int(serialized["merged_cells"]) == 1, "Число перекрытых клеток должно быть 1.")
	var stored_layers: Array = serialized["editor_layers"]
	if not _check(stored_layers.size() == 3, "В черновик должны попасть все три слоя."):
		return
	var lower_cells := _slot_map(stored_layers[0]["cells"])
	var upper_cells := _slot_map(stored_layers[1]["cells"])
	_check(
		lower_cells.get("ground|1|1", "") == "grass" and lower_cells.size() == 3,
		"Нижний слой потерял клетки в черновике, хотя их перекрывает верхний.",
	)
	_check(
		upper_cells.size() == 2 and not bool(stored_layers[1]["visible"]),
		"Скрытый верхний слой должен сохраняться целиком вместе с признаком видимости.",
	)


func _check_status_after_save() -> void:
	editor._last_save_merged_cells = 2
	editor._pending_action = "save_map"
	editor._on_api_completed(true, {"saved_id": 7})
	_check(
		editor._saved_id == 7 and editor._status.text.contains("ID: 7") and editor._status.text.contains("2"),
		"После сохранения статус должен показывать ID черновика и число перекрытых клеток.",
	)
	editor._on_api_completed(true, {"saved_maps": []})
	_check(
		editor._status.text.contains("ID: 7"),
		"Обновление списка черновиков не должно затирать сообщение об успешном сохранении.",
	)
	editor._pending_action = "save_map"
	editor._on_api_completed(false, "Клетка (1, 1) уже занята на слое «ground»")
	_check(
		editor._status.text.begins_with("Не удалось сохранить карту:")
		and editor._status.text.contains("уже занята"),
		"Ошибка сервера при сохранении должна быть понятно показана в статусе.",
	)
