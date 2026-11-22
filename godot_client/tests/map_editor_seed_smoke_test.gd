extends Node

const SEED_RULES = preload("res://scripts/map_editor_seed_rules.gd")
const FIXTURE_PATH := "res://tests/map_editor_seed_fixture.json"
const APPLIED_STATUS := "Карта мира в черновике, клеток: %d. Сохраните черновик (Ctrl+S)"
const NO_WORLD_STATUS := "Мир сервера играет процедурным рельефом: опубликованной карты нет"


class SeedEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: SeedEditor
var _failures: Array[String] = []
var _checks := 0
var _fixture: Dictionary = {}
var _catalog_by_key: Dictionary = {}
var _expected: Array = []


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	_check(parsed is Dictionary, "Фикстура читается как JSON-объект")
	if parsed is Dictionary:
		_fixture = parsed
		for item in _fixture["catalog"]:
			_catalog_by_key[str(item["item_key"])] = item
		_expected = _normalized(_fixture["expected_cells"])
		editor = SeedEditor.new()
		editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		add_child(editor)
		await get_tree().process_frame
		editor._catalog_by_key = _catalog_by_key
		editor._create_default_layers()
		editor._render_layers()
		_check_rules()
		_check_fixture_output()
		_check_editor_apply()
		_check_editor_undo()
		_check_response_paths()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_seed_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _normalized(raw_cells: Array) -> Array:
	var result: Array = []
	for cell in raw_cells:
		result.append({"layer": str(cell["layer"]), "x": int(cell["x"]), "y": int(cell["y"]), "key": str(cell["key"])})
	return result


func _terrain() -> Dictionary:
	return _fixture["terrain"]


func _check_rules() -> void:
	_check(SEED_RULES.decode_tiles([[1, 2], [1, 2], [3, 4]]).size() == 2, "Тайлы сервера [x, y]: повтор одной клетки даёт одну запись")
	_check(SEED_RULES.decode_tiles([[1, 2, 3]]).is_empty(), "Строки другой длины (старый формат [y, x, x]) не читаются")
	_check(SEED_RULES.build_cells({"tiles": {}}, {}, 2, 2).is_empty(), "Пустой каталог не даёт клеток")


func _check_fixture_output() -> void:
	var map_w := int(_fixture["map_w"])
	var map_h := int(_fixture["map_h"])
	var cells: Array = SEED_RULES.build_cells(_terrain(), _catalog_by_key, map_w, map_h)
	_check(cells.size() == _expected.size(), "Число клеток совпадает с фикстурой Python: %d" % _expected.size())
	_check(cells == _expected, "Клетки и порядок совпадают с build_world_seed_cells из фикстуры")
	var ground_count := 0
	for cell in cells:
		if cell["layer"] == "ground":
			ground_count += 1
	_check(ground_count == map_w * map_h, "Каждая клетка карты получает землю")
	_check(SEED_RULES.build_cells(_terrain(), _catalog_by_key, map_w, map_h) == cells, "Одинаковый рельеф даёт одинаковую карту")
	var changed := _terrain().duplicate(true)
	changed["tiles"]["water"] = []
	var changed_cells: Array = SEED_RULES.build_cells(changed, _catalog_by_key, map_w, map_h)
	_check(changed_cells != cells and changed_cells.size() == cells.size(), "Другой рельеф меняет землю, размер карты тот же")


func _check_editor_apply() -> void:
	editor._map_width.value = 64
	editor._map_height.value = 64
	editor._spawns = [Vector2i(1, 1)]
	editor._saved_id = 5
	editor._undo_stack.clear()
	editor._redo_stack.clear()
	editor._apply_world_terrain(_terrain())
	_check(editor._map_size() == Vector2i(int(_fixture["map_w"]), int(_fixture["map_h"])), "Размер карты берётся из мира: 40×30")
	var placed := 0
	var missing := 0
	for cell in _expected:
		var target: Dictionary = editor._layers[0] if cell["layer"] == "ground" else editor._layer_by_type(editor.LAYER_OBJECT)
		var stored := str(target["cells"].get("%d:%d" % [cell["x"], cell["y"]], ""))
		if stored == str(cell["key"]):
			placed += 1
		else:
			missing += 1
	_check(missing == 0 and placed == _expected.size(), "Все клетки попадают в слои «Земля» и «Объекты»: %d" % placed)
	_check(editor._spawns.is_empty(), "Генерация очищает точки спауна, как replace_cells в Python")
	_check(editor._saved_id == 0 and editor._local_draft_id.is_empty(), "Генерация отвязывает карту от сохранённого черновика")
	_check(editor._status.text == APPLIED_STATUS % _expected.size(), "Статус: число клеток и подсказка про сохранение")
	_check(editor._undo_stack.size() == 1 and editor._redo_stack.is_empty(), "Генерация — одно действие в истории")


func _check_editor_undo() -> void:
	editor._undo_last_action()
	_check(editor._map_size() == Vector2i(64, 64) and editor._layers[0]["cells"].is_empty(), "Отмена возвращает прежний размер и пустую землю")
	_check(editor._spawns == [Vector2i(1, 1)], "Отмена возвращает точки спауна")
	editor._redo_last_action()
	_check(editor._map_size() == Vector2i(40, 30) and editor._layers[0]["cells"].size() == 1200, "Повтор возвращает карту мира целиком")
	_check(editor._spawns.is_empty(), "Повтор снова очищает точки спауна")


func _check_response_paths() -> void:
	editor._undo_stack.clear()
	editor._redo_stack.clear()
	editor._generate_from_world()
	_check(editor._status.text == "Сгенерировать можно только на карте мира Колоды: откройте редактор из мира.", "Вне мира Колоды кнопка не отправляет запрос")
	_check(editor._pending_action.is_empty(), "Вне мира Колоды ожидание ответа не начинается")
	editor._apply_world_terrain({"width_tiles": 20, "height_tiles": 20, "props": []})
	_check(editor._status.text == NO_WORLD_STATUS and editor._undo_stack.is_empty(), "Без наборов тайлов карта не меняется")
	editor._pending_action = "world_terrain"
	editor._on_api_completed(false, "Нет связи")
	_check(editor._status.text == "Не загружено: Нет связи", "Ошибка загрузки рельефа показывается в статусе")
	editor._pending_action = "world_terrain"
	editor._on_api_completed(true, {"terrain": _terrain()})
	_check(editor._map_size() == Vector2i(40, 30) and editor._undo_stack.size() == 1, "Ответ сервера с рельефом применяется через список действий")
	editor._pending_action = "world_terrain"
	editor._on_api_completed(true, {"terrain": {"width_tiles": 20, "height_tiles": 20}})
	_check(editor._status.text == NO_WORLD_STATUS and editor._undo_stack.size() == 1, "Ответ без наборов тайлов сообщает о процедурном рельефе")
