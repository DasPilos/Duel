extends Node

const SPAWN_RULES = preload("res://scripts/map_editor_spawn_rules.gd")
const DRAFTS_RULES = preload("res://scripts/map_editor_drafts_rules.gd")
const TEST_FOLDER := "user://map_spawns_test_drafts"


class SpawnEditor extends "res://scripts/map_editor.gd":
	var saved_payload: Dictionary = {}
	var save_posts := 0

	func _ready() -> void:
		_mode = "tower"
		_build_ui()

	func _post_saved_map(payload: Dictionary) -> void:
		saved_payload = payload
		save_posts += 1


class DrawProbe extends Control:
	var editor_ref: SpawnEditor
	var draws := 0

	func _draw() -> void:
		draws += 1
		editor_ref._draw_spawn_overlay(self, 16.0)
		editor_ref._draw_spawn_overlay(self, 8.0)


var editor: SpawnEditor
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	editor = SpawnEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
	}
	editor._selected_item_key = "grass"
	editor._create_default_layers()
	editor._render_layers()
	editor._map_width.value = 16
	editor._map_height.value = 16
	_check_rules()
	_check_tool_and_clicks()
	_check_undo_redo()
	_check_layer_history()
	_check_payloads()
	_check_local_draft()
	_check_server_load()
	await _check_drawing()
	_check_mob_spawns()
	_check_duration_formatting()
	_check_tavern_objective()
	_finish()


func _finish() -> void:
	_remove_folder(TEST_FOLDER)
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	print("map_editor_spawns_smoke_test: %d failures (%d checks)" % [_failures.size(), _checks])
	get_tree().quit(0 if _failures.is_empty() else 1)


func _ground_cells() -> Dictionary:
	return editor._layers[0]["cells"]


func _cell_position(cell: Vector2i) -> Vector2:
	return editor._pan + (Vector2(cell) + Vector2(0.5, 0.5)) * editor.TILE_SIZE * editor._zoom


func _click(cell: Vector2i, button: MouseButton) -> void:
	editor._begin_canvas_stroke(_cell_position(cell), button)
	editor._end_canvas_stroke(button)


func _press(keycode: Key, ctrl := true, shift := false) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	event.shift_pressed = shift
	editor._unhandled_key_input(event)


func _as_cells(items: Array) -> Array:
	var cells: Array = []
	for item in items:
		cells.append(Vector2i(int(item["x"]), int(item["y"])))
	return cells


func _editor_cells() -> Array:
	return _as_cells(editor._spawns)


func _remove_folder(folder: String) -> void:
	var directory := DirAccess.open(folder)
	if directory == null:
		return
	for file_name in directory.get_files():
		directory.remove(file_name)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(folder))


func _check_rules() -> void:
	var map_size := Vector2i(8, 8)
	var spawns: Array = []
	var added: Dictionary = SPAWN_RULES.toggle(spawns, Vector2i(2, 3), map_size)
	_check(
		added["result"] == SPAWN_RULES.ADDED
		and Vector2i(int(spawns[0]["x"]), int(spawns[0]["y"])) == Vector2i(2, 3)
		and spawns[0]["name"] == "1",
		"Правила: первый клик ставит пронумерованную точку",
	)
	var removed: Dictionary = SPAWN_RULES.toggle(spawns, Vector2i(2, 3), map_size)
	_check(removed["result"] == SPAWN_RULES.REMOVED and spawns.is_empty(), "Правила: повторный клик убирает точку")
	var outside: Dictionary = SPAWN_RULES.toggle(spawns, Vector2i(8, 0), map_size)
	_check(outside["error"] == SPAWN_RULES.OUTSIDE_TEXT and spawns.is_empty(), "Правила: клетка за краем карты не ставится")
	_check(not SPAWN_RULES.erase(spawns, Vector2i(1, 1)), "Правила: удаление несуществующей точки ничего не меняет")
	SPAWN_RULES.toggle(spawns, Vector2i(4, 4), map_size)
	_check(SPAWN_RULES.erase(spawns, Vector2i(4, 4)) and spawns.is_empty(), "Правила: удаление существующей точки")
	var mixed_spawns: Array = []
	for cell in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0)]:
		SPAWN_RULES.toggle(mixed_spawns, cell, map_size, SPAWN_RULES.TYPE_HERO)
	SPAWN_RULES.toggle(
		mixed_spawns,
		Vector2i(3, 0),
		map_size,
		SPAWN_RULES.TYPE_MOB,
		{"mob_key": "imp_vanilla"},
	)
	_check(
		mixed_spawns[0]["name"] == "1"
		and mixed_spawns[2]["name"] == "3"
		and mixed_spawns[3]["name"] == "1",
		"Нумерация точек возрождения и появления ЛПС ведётся отдельно",
	)
	var legacy_mixed := SPAWN_RULES.load_spawns([
		{"x": 0, "y": 0, "name": "1"},
		{"x": 1, "y": 0, "name": "2"},
		{"x": 2, "y": 0, "name": "3"},
		{
			"x": 3,
			"y": 0,
			"type": "mob",
			"name": "4",
			"settings": {"mob_key": "imp_vanilla"},
		},
	], map_size)
	_check(legacy_mixed[3]["name"] == "1", "Старый общий номер точки ЛПС нормализуется отдельно от возрождений")
	var loaded: Array = SPAWN_RULES.load_spawns([
		{"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 9, "y": 0}, "мусор", {"x": 0, "y": 7}, {"x": -1, "y": 2},
	], map_size)
	_check(_as_cells(loaded) == [Vector2i(1, 1), Vector2i(0, 7)], "Загрузка: дубликаты, клетки вне карты и мусор пропускаются, порядок сохраняется")
	_check(SPAWN_RULES.load_spawns("не массив", map_size).is_empty() and SPAWN_RULES.load_spawns(null, map_size).is_empty(), "Загрузка: не массив даёт пустой список")
	_check(SPAWN_RULES.to_payload(loaded) == [
		{"x": 1, "y": 1, "name": "1"}, {"x": 0, "y": 7, "name": "2"},
	], "Сериализация: точки героя сохраняют координаты и имена")
	var payload_with_hidden_points := SPAWN_RULES.to_payload([
		{"x": 1, "y": 1},
		{"name": "Невидимая"},
		{"x": -1, "y": -1},
		{"x": 8, "y": 1},
	], "tower", {}, map_size)
	_check(
		payload_with_hidden_points == [{"x": 1, "y": 1, "name": "1"}],
		"Сериализация исключает скрытые и выходящие за карту точки, не создавая координаты -1,-1",
	)
	var limited := SPAWN_RULES.normalize_mob_settings({
		"level": 999, "count": 999999, "interval_seconds": 999999,
	})
	var limited_wave: Dictionary = limited["waves"][0]
	_check(
		limited_wave["level"] == SPAWN_RULES.MAX_SPAWN_LEVEL
		and limited_wave["count"] == SPAWN_RULES.MAX_SPAWN_COUNT
		and limited_wave["interval_seconds"] == SPAWN_RULES.MAX_INTERVAL_SECONDS
		and not limited_wave.has("reward_xp") and not limited_wave.has("reward_copper"),
		"Настройки спауна ограничиваются допустимыми серверными значениями"
	)
	var boss_defaults := SPAWN_RULES.normalize_boss_settings({})
	_check(
		not boss_defaults["enabled"]
		and boss_defaults["spell_slots"].size() == SPAWN_RULES.MAX_BOSS_SPELL_SLOTS
		and boss_defaults["spell_slots"][0]["spell_key"] == ""
		and boss_defaults["drop_slots"].size() == SPAWN_RULES.MAX_BOSS_DROP_SLOTS
		and boss_defaults["drop_slots"][0]["item_id"] == 0,
		"Для каждой волны создаются отключённый босс и пустые слоты заклинаний и предметов",
	)
	var configured_boss := SPAWN_RULES.normalize_boss_settings({
		"drop_slots": [{"item_id": 12, "chance_percent": 35}],
	})
	_check(
		configured_boss["drop_slots"][0] == {"item_id": 12, "chance_percent": 35}
		and configured_boss["drop_slots"].size() == SPAWN_RULES.MAX_BOSS_DROP_SLOTS,
		"Параметры пяти слотов предметов босса нормализуются",
	)
	var front_line_target := SPAWN_RULES.normalize_mob_settings({"target": "both"}, true)
	_check(front_line_target["waves"][0]["target"] == SPAWN_RULES.TARGET_BOTH, "Front Line хранит цель моба")
	var tower_settings := SPAWN_RULES.normalize_mob_settings({"target": "characters"})
	_check(not tower_settings["waves"][0].has("target"), "настройка цели Front Line не попадает в другие режимы")
	var target_spawns: Array = []
	SPAWN_RULES.toggle(
		target_spawns,
		Vector2i(3, 3),
		map_size,
		SPAWN_RULES.TYPE_MOB,
		{"mob_key": "imp_vanilla", "target": SPAWN_RULES.TARGET_CHARACTERS},
		true,
	)
	_check(
		SPAWN_RULES.to_payload(target_spawns, "front_line")[0]["settings"]["waves"][0]["target"]
			== SPAWN_RULES.TARGET_CHARACTERS,
		"Цель сохраняется в формате Front Line",
	)
	target_spawns[0]["name"] = "Лесной вход"
	_check(
		SPAWN_RULES.to_payload(target_spawns, "front_line")[0]["name"] == "Лесной вход"
		and SPAWN_RULES.load_spawns(
			SPAWN_RULES.to_payload(target_spawns, "front_line"), map_size, "front_line"
		)[0]["name"] == "Лесной вход",
		"Имя точки сохраняется и загружается",
	)
	_check(
		not SPAWN_RULES.to_payload(target_spawns, "tower")[0]["settings"]["waves"][0].has("target"),
		"Цель исключается из формата остальных режимов",
	)


func _check_tool_and_clicks() -> void:
	editor._select_tool(editor.TOOL_SPAWN)
	_check(editor._active_tool == editor.TOOL_SPAWN and editor._hero_spawn_button.button_pressed, "Инструмент возрождения включается и подсвечивается")
	_check(editor._status.text.begins_with("Точки"), "Инструмент возрождения пишет подсказку в статус")
	_click(Vector2i(2, 3), MOUSE_BUTTON_LEFT)
	_check(_editor_cells() == [Vector2i(2, 3)] and editor._status.text == "Точка возрождения 1 на (2, 3)", "ЛКМ ставит точку возрождения с номером")
	_check(_ground_cells().is_empty() and editor._undo_stack.size() == 1, "Спаун не рисует тайлы и пишет один шаг истории")
	_click(Vector2i(5, 1), MOUSE_BUTTON_LEFT)
	_check(_editor_cells() == [Vector2i(2, 3), Vector2i(5, 1)] and editor._status.text == "Точка возрождения 2 на (5, 1)", "Вторая точка возрождения получает следующий номер")
	_click(Vector2i(2, 3), MOUSE_BUTTON_LEFT)
	_check(_editor_cells().size() == 2, "Обычный клик по существующей точке не удаляет её до распознавания двойного щелчка")
	_click(Vector2i(5, 1), MOUSE_BUTTON_RIGHT)
	_check(_editor_cells() == [Vector2i(2, 3)] and editor._status.text == "Точка спауна убрана с (5, 1)", "ПКМ удаляет точку возрождения")
	var depth := editor._undo_stack.size()
	_click(Vector2i(7, 7), MOUSE_BUTTON_RIGHT)
	_check(editor._undo_stack.size() == depth and editor._status.text == "Точка спауна убрана с (5, 1)", "ПКМ по пустой клетке не пишет историю и не меняет статус")
	_click(Vector2i(16, 3), MOUSE_BUTTON_LEFT)
	_check(_editor_cells() == [Vector2i(2, 3)] and editor._status.text == "Клетка вне карты", "Клик за краем карты не ставит точку и сообщает об этом")
	_check(editor._undo_stack.size() == depth, "Ошибка за краем карты не пишет историю")
	editor._select_tool(editor.TOOL_BRUSH)
	_check(not editor._hero_spawn_button.button_pressed and not editor._mob_spawn_button.button_pressed, "Смена инструмента снимает подсветку размещения точек")
	_click(Vector2i(1, 1), MOUSE_BUTTON_LEFT)
	_check(_ground_cells().get("1:1") == "grass" and _editor_cells().size() == 1, "Кисть рисует тайл, не меняя точки возрождения")
	editor._undo_last_action()
	editor._spawns.clear()
	editor._refresh_spawn_button()


func _check_undo_redo() -> void:
	editor._select_tool(editor.TOOL_SPAWN)
	editor._undo_stack.clear()
	editor._redo_stack.clear()
	_click(Vector2i(1, 1), MOUSE_BUTTON_LEFT)
	_click(Vector2i(4, 2), MOUSE_BUTTON_LEFT)
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(4, 2)] and editor._undo_stack.size() == 2, "Две постановки дают два шага истории")
	editor._undo_last_action()
	_check(_editor_cells() == [Vector2i(1, 1)] and editor._redo_stack.size() == 1, "Отмена убирает последнюю точку")
	editor._undo_last_action()
	_check(editor._spawns.is_empty(), "Вторая отмена возвращает пустой список")
	editor._redo_last_action()
	editor._redo_last_action()
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(4, 2)], "Повтор возвращает обе точки в исходном порядке")
	_click(Vector2i(4, 2), MOUSE_BUTTON_RIGHT)
	_check(_editor_cells() == [Vector2i(1, 1)] and editor._redo_stack.is_empty(), "Удаление ПКМ пишет шаг и очищает повтор")
	editor._undo_last_action()
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(4, 2)], "Отмена удаления возвращает точку")
	editor._redo_last_action()
	_check(_editor_cells() == [Vector2i(1, 1)], "Повтор удаления снова убирает точку")
	_press(KEY_Z)
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(4, 2)], "Ctrl+Z отменяет удаление точки")
	_press(KEY_Y)
	_check(_editor_cells() == [Vector2i(1, 1)], "Ctrl+Y повторяет удаление точки")


func _check_layer_history() -> void:
	var ground_id := int(editor._layers[0]["id"])
	editor._set_layer_visibility(ground_id, false)
	_click(Vector2i(6, 6), MOUSE_BUTTON_LEFT)
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(6, 6)], "Точка после смены видимости слоя добавляется к прежним")
	editor._undo_last_action()
	_check(_editor_cells() == [Vector2i(1, 1)] and not bool(editor._get_layer(ground_id)["visible"]), "Отмена точки не трогает видимость слоя")
	editor._undo_last_action()
	_check(bool(editor._get_layer(ground_id)["visible"]) and _editor_cells() == [Vector2i(1, 1)], "Отмена видимости слоя возвращает слой и сохраняет точки")
	editor._redo_last_action()
	editor._redo_last_action()
	_check(not bool(editor._get_layer(ground_id)["visible"]) and _editor_cells() == [Vector2i(1, 1), Vector2i(6, 6)], "Повтор восстанавливает и слой, и точку")


func _check_payloads() -> void:
	var expected := [
		{"x": 1, "y": 1, "name": "1"},
		{"x": 6, "y": 6, "name": "2"},
	]
	var publish: Dictionary = editor._build_map_payload()
	_check(publish["spawns"] == expected, "Публикация: поле spawns совпадает с точками редактора")
	editor._map_name.text = "Карта со спаунами"
	editor._save_map()
	_check(editor.save_posts == 1 and editor.saved_payload["spawns"] == expected, "Сохранение на сервер: поле spawns совпадает с точками редактора")
	editor._spawns.append({"type": SPAWN_RULES.TYPE_HERO, "name": "Невидимая"})
	editor._save_map()
	_check(
		editor.save_posts == 2
		and editor.saved_payload["spawns"] == expected
		and editor._spawns.size() == expected.size(),
		"Сохранение удаляет скрытую точку без координат, прежде чем отправить карту",
	)
	var snapshot := editor._layers_snapshot()
	snapshot["spawns"].append({"type": SPAWN_RULES.TYPE_HERO, "name": "Невидимая"})
	editor._restore_history_snapshot(snapshot)
	_check(
		editor._spawns.size() == expected.size(),
		"Восстановление истории также отбрасывает невидимые точки без координат",
	)


func _check_local_draft() -> void:
	_remove_folder(TEST_FOLDER)
	editor._local_drafts_folder = TEST_FOLDER
	editor._local_draft_id = ""
	editor._map_name.text = "Спаун-черновик"
	_check(editor._save_local_draft(), "Локальный черновик со спаунами сохраняется")
	var stored: Dictionary = DRAFTS_RULES.read_file(TEST_FOLDER, editor._local_draft_id)
	_check(_as_cells(stored.get("spawns", [])) == [Vector2i(1, 1), Vector2i(6, 6)], "Файл черновика хранит поле spawns")
	editor._spawns = []
	editor._open_local_draft(editor._local_draft_id)
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(6, 6)], "Открытие локального черновика восстанавливает точки")
	_check(editor._status.text.begins_with("Черновик «Спаун-черновик» открыт"), "Открытие черновика пишет статус")


func _check_server_load() -> void:
	editor._load_map_payload({
		"id": 7,
		"name": "С сервера",
		"map_w": 16,
		"map_h": 16,
		"cells": [],
		"editor_layers": [],
		"spawns": [{"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 17, "y": 0}, {"x": 3, "y": 4}],
	})
	_check(_editor_cells() == [Vector2i(1, 1), Vector2i(3, 4)], "Карта с сервера: дубликаты и клетки вне карты отбрасываются")
	_check(editor._saved_id == 7 and editor._undo_stack.is_empty(), "Загрузка с сервера сбрасывает историю")
	editor._load_map_payload({
		"id": 8,
		"name": "Без спаунов",
		"map_w": 16,
		"map_h": 16,
		"cells": [],
		"editor_layers": [],
	})
	_check(editor._spawns.is_empty(), "Карта без поля spawns открывается без точек")


func _check_drawing() -> void:
	editor._select_tool(editor.TOOL_SPAWN)
	editor._spawns = [
		{"x": 1, "y": 1, "type": "hero"},
		{"x": 3, "y": 4, "type": "mob", "settings": {
			"level": 2, "mob_key": "mob|test|skeleton", "count": 4, "interval_seconds": 20,
		}},
	]
	editor._hover_cell = Vector2i(2, 2)
	var probe := DrawProbe.new()
	probe.editor_ref = editor
	probe.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(probe)
	probe.queue_redraw()
	editor._canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	_check(probe.draws > 0 and editor._spawns.size() == 2, "Отрисовка точек выполняется в контексте рисования и не меняет состояние")
	editor._zoom = 0.5
	editor._canvas.queue_redraw()
	await get_tree().process_frame
	await get_tree().process_frame
	editor._zoom = 1.0
	_check(editor._spawns.size() == 2 and probe.draws > 0, "Отрисовка точек без номеров при мелком масштабе выполняется")
	probe.queue_free()


func _check_mob_spawns() -> void:
	var mob_key := "mob|test|imp"
	var mob_group := {
		"key": mob_key,
		"name": "Скелет",
		"kind": "mob",
		"profile_kind": "imp_vanilla",
	}
	editor._animal_groups = [mob_group]
	editor._animal_groups_by_key = {mob_key: mob_group}
	editor._spawns.clear()
	editor._undo_stack.clear()
	editor._redo_stack.clear()
	editor._select_spawn_type(SPAWN_RULES.TYPE_MOB)
	_check(editor._spawn_type == SPAWN_RULES.TYPE_MOB and editor._mob_spawn_button.button_pressed, "Кнопка «Появления ЛПС» включает режим размещения мобов")
	var mob_layer_id := 0
	var ground_layer_id := 0
	for layer in editor._layers:
		if str(layer.get("type", "")) == editor.LAYER_MOB:
			mob_layer_id = int(layer.get("id", 0))
		elif str(layer.get("type", "")) == editor.LAYER_TILE:
			ground_layer_id = int(layer.get("id", 0))
	_check(
		int(editor._get_layer(editor._active_layer_id).get("id", 0)) == mob_layer_id,
		"Выбор точек ЛПС переключает редактор на слой «Мобы»",
	)
	editor._on_layer_list_selected(ground_layer_id)
	_click(Vector2i(3, 3), MOUSE_BUTTON_LEFT)
	_check(
		editor._spawns.is_empty()
		and editor._status.text == "Точки появления ЛПС можно размещать только на слое «Мобы».",
		"Точка ЛПС не размещается на другом слое",
	)
	editor._on_layer_list_selected(mob_layer_id)
	_check(editor._spawn_settings_dialog == null, "До размещения точки настройки не открываются")
	_click(Vector2i(4, 3), MOUSE_BUTTON_LEFT)
	_check(editor._spawns.size() == 1 and editor._spawns[0]["type"] == "mob", "Точка ЛПС размещается отдельным типом")
	_check(
		editor._spawns[0]["settings"]["waves"][0]["mob_key"] == mob_key
		and editor._spawns[0]["name"] == "1",
		"Новая точка получает моба по умолчанию и номер",
	)
	editor._handle_canvas_double_click(_cell_position(Vector2i(4, 3)))
	_check(editor._spawn_settings_dialog.visible and editor._spawn_settings_index == 0, "Двойной щелчок по точке ЛПС открывает её индивидуальные настройки")
	_check(
		editor._spawn_settings_dialog.theme == editor._ui_root.theme
		and editor._spawn_name_edit.text == "1",
		"Диалог точки использует масштаб редактора и показывает её имя",
	)
	editor._spawn_settings_dialog.hide()
	editor._select_tool(editor.TOOL_BRUSH)
	editor._handle_canvas_double_click(_cell_position(Vector2i(4, 3)))
	_check(
		editor._spawn_settings_dialog.visible and editor._spawn_settings_index == 0,
		"Двойной щелчок по точке открывает её настройки без активного инструмента спауна",
	)
	editor._spawn_settings_dialog.hide()
	editor._erase_canvas_at(_cell_position(Vector2i(4, 3)))
	_check(
		editor._spawn_settings_dialog.visible and editor._spawns.size() == 1,
		"ПКМ по точке открывает настройки, не удаляя её",
	)
	editor._spawn_settings_dialog.hide()
	editor._erase_canvas_at(_cell_position(Vector2i(4, 3)))
	_check(editor._spawn_settings_dialog.visible, "Повторный ПКМ по точке продолжает открывать её настройки")
	var settings := {"waves": [{
		"mob_key": mob_key,
		"level": 7,
		"count": 12,
		"interval_seconds": 45,
		"start_after_seconds": 0,
		"squad_min": 1,
		"squad_max": 1,
	}]}
	_check(editor._apply_mob_spawn_settings(0, settings, "Лесной вход"), "Настройки уже размещённой точки применяются")
	_check(editor._spawns[0]["settings"] == settings, "Уровень, моб, количество и интервал сохранены на точке")
	_check(editor._spawns[0]["name"] == "Лесной вход", "Имя точки редактируется вместе с её настройками")
	editor._undo_last_action()
	_check(int(editor._spawns[0]["settings"]["waves"][0]["level"]) == 1 and editor._spawns[0]["name"] == "1", "Настройки и имя точки входят в историю отмены")
	editor._redo_last_action()
	_check(editor._spawns[0]["settings"] == settings and editor._spawns[0]["name"] == "Лесной вход", "Повтор восстанавливает настройки и имя точки")
	editor._select_spawn_type(SPAWN_RULES.TYPE_MOB)
	_click(Vector2i(6, 6), MOUSE_BUTTON_LEFT)
	_check(editor._spawns[1]["name"] == "2", "Новая точка получает следующий последовательный номер")
	var second_settings := settings.duplicate(true)
	second_settings["waves"][0]["level"] = 3
	_check(editor._apply_mob_spawn_settings(1, second_settings, "Второй вход"), "Вторая точка настраивается отдельно")
	_check(
		editor._spawns[0]["settings"]["waves"][0]["level"] == 7
		and editor._spawns[1]["settings"]["waves"][0]["level"] == 3,
		"Настройки разных точек не перезаписывают друг друга",
	)
	editor._spawn_settings_dialog.hide()
	editor._select_spawn_type(SPAWN_RULES.TYPE_HERO)
	_click(Vector2i(7, 5), MOUSE_BUTTON_LEFT)
	_check(editor._count_spawns(SPAWN_RULES.TYPE_HERO) == 1, "Точки героя считаются как сетевые места игроков")
	_check(editor._hero_spawn_button.text == "Возрождения · 1", "Число точек возрождения видно на кнопке")
	editor._handle_canvas_double_click(_cell_position(Vector2i(7, 5)))
	_check(editor._spawn_rename_dialog.visible and editor._spawn_rename_index == 2, "Двойной щелчок по точке возрождения открывает переименование")
	_check(editor._rename_spawn(2, "Площадь"), "Размещённую точку возрождения можно переименовать")
	var payload := SPAWN_RULES.to_payload(editor._spawns)
	var loaded := SPAWN_RULES.load_spawns(payload, Vector2i(16, 16))
	_check(loaded == editor._spawns, "Серверный/локальный формат сохраняет имена и настройки спаунов")
	editor._spawn_rename_dialog.hide()
	editor._spawn_settings_dialog.hide()
	editor._mode = "front_line"
	_check(
		editor._default_mob_spawn_settings()["waves"][0]["mob_key"] == "imp_vanilla",
		"Волна по умолчанию использует ключ боевого NPC, а не ключ спрайта.",
	)
	var palette_mob_key := "mob|test|rat"
	var palette_mob_group := {"key": palette_mob_key, "name": "Крыса", "kind": "mob"}
	_check(
		editor._spawn_mob_key(palette_mob_group) == palette_mob_key,
		"Ключ моба из палитры сохраняется без подмены его профилем.",
	)
	editor._animal_groups.append(palette_mob_group)
	editor._animal_groups_by_key[palette_mob_key] = palette_mob_group
	_check(
		editor._apply_mob_spawn_settings(
			0,
			{"waves": [{"mob_key": palette_mob_key}]},
			"Крыса из палитры",
		)
		and editor._spawns[0]["settings"]["waves"][0]["mob_key"] == palette_mob_key,
		"Моб из палитры можно сохранить в настройках волны.",
	)
	var front_line_wave: Dictionary = settings["waves"][0].duplicate(true)
	front_line_wave["mob_key"] = "imp_vanilla"
	front_line_wave["target"] = SPAWN_RULES.TARGET_BOTH
	var front_line_settings := {"waves": [front_line_wave]}
	_check(
		editor._apply_mob_spawn_settings(0, front_line_settings, "Лесной вход"),
		"Front Line принимает настройку цели",
	)
	_check(
		editor._apply_mob_spawn_settings(
			1,
			{"waves": [{
				"mob_key": "imp_vanilla",
				"level": second_settings["waves"][0]["level"],
				"count": second_settings["waves"][0]["count"],
				"interval_seconds": second_settings["waves"][0]["interval_seconds"],
				"target": SPAWN_RULES.TARGET_OBJECTIVE,
			}]},
			"Второй вход"
		),
		"Front Line хранит независимую цель второй точки",
	)
	_check(editor._front_line_spawns_supported(), "Сохранённые волны используют подключённые мобы палитры.")
	editor._configure_spawn_settings_dialog(editor._spawns[0]["settings"], "Проверка цели")
	_check(
		editor._spawn_target_row.visible
		and str(editor._spawn_target_select.get_item_metadata(editor._spawn_target_select.selected))
			== SPAWN_RULES.TARGET_BOTH,
		"Front Line показывает и восстанавливает индивидуальную цель",
	)
	_check(
		not _contains_text(editor._spawn_settings_dialog, "Уровень спауна"),
		"В настройках волны нет поля уровня",
	)
	editor._spawn_item_catalog = [{"id": 12, "name": "Кристалл маны"}]
	editor._configure_spawn_settings_dialog({
		"waves": [
			{
				"mob_key": "imp_vanilla", "level": 2, "count": 3, "interval_seconds": 10,
				"start_after_seconds": 0, "target": SPAWN_RULES.TARGET_OBJECTIVE,
				"boss": {
					"enabled": true, "max_hp": 4321, "max_mp": 765, "reward_xp": 987,
					"spell_slots": [{
						"spell_key": "", "range": 8, "damage": 120,
						"cooldown_seconds": 7, "area_radius": 4, "mana_cost": 25,
					}],
					"drop_slots": [{"item_id": 12, "chance_percent": 35}],
				},
			},
			{"mob_key": "imp_vanilla", "level": 9, "count": 7, "interval_seconds": 30, "start_after_seconds": 120, "target": SPAWN_RULES.TARGET_CHARACTERS},
		],
	}, "Независимые волны")
	_spawn_wave_ui_checks()
	editor._spawn_settings_dialog.hide()
	var front_line_payload := SPAWN_RULES.to_payload(editor._spawns, editor._mode)
	var front_line_loaded := SPAWN_RULES.load_spawns(front_line_payload, Vector2i(16, 16), editor._mode)
	_check(front_line_loaded == editor._spawns, "Цель сохраняется и загружается в Front Line")
	editor._mode = "tower"
	var tower_payload := SPAWN_RULES.to_payload(editor._spawns, editor._mode)
	_check(
		not tower_payload[0]["settings"]["waves"][0].has("target"),
		"Настройка цели не сохраняется для Tower",
	)


func _spawn_wave_ui_checks() -> void:
	_check(
		int(editor._spawn_wave_count_spin.value) == 2
		and editor._spawn_wave_select.item_count == 2,
		"Диалог показывает число и список отдельных волн",
	)
	editor._spawn_wave_select.select(1)
	editor._on_spawn_wave_selected(1)
	_check(
		editor._spawn_start_delay_edit.text == "00:02:00"
		and editor._spawn_interval_edit.text == "00:00:30",
		"Время старта и интервал загружаются в формате ЧЧ:ММ:СС",
	)
	editor._spawn_count_spin.value = 11
	editor._spawn_wave_select.select(0)
	editor._on_spawn_wave_selected(0)
	_check(
		int(editor._spawn_count_spin.value) == 3
		and int(editor._spawn_wave_configs[1]["count"]) == 11,
		"Редактирование и переключение сохраняют независимые параметры волн",
	)
	editor._spawn_wave_select.select(0)
	editor._on_spawn_wave_selected(0)
	_check(
		editor._spawn_boss_checkbox.button_pressed
		and int(editor._spawn_boss_hp_spin.value) == 4321
		and int(editor._spawn_boss_mp_spin.value) == 765
		and int(editor._spawn_boss_reward_xp_spin.value) == 987
		and int((editor._spawn_boss_spell_slots[0]["damage"] as SpinBox).value) == 120
		and (editor._spawn_boss_spell_slots[0]["cooldown"] as LineEdit).text == "00:00:07",
		"Настройки босса и его слота заклинания загружаются отдельно для выбранной волны",
	)
	var drop_item_select: OptionButton = editor._spawn_boss_drop_controls[0]["item_select"]
	_check(
		int(drop_item_select.get_item_metadata(drop_item_select.selected)) == 12
		and int((editor._spawn_boss_drop_controls[0]["chance"] as SpinBox).value) == 35,
		"Предмет и процент выпадения загружаются в слоты босса",
	)
	editor._store_spawn_wave_form()
	_check(
		editor._spawn_wave_configs[0]["boss"]["drop_slots"][0]
			== {"item_id": 12, "chance_percent": 35},
		"Предмет и шанс сохраняются в настройках выбранной волны",
	)
	editor._spawn_boss_hp_spin.value = 5000
	editor._store_spawn_wave_form()
	_check(
		int(editor._spawn_wave_configs[0]["boss"]["max_hp"]) == 5000
		and editor._spawn_wave_configs[0]["boss"]["spell_slots"][0]["spell_key"] == "",
		"Настройки босса и пустые слоты заклинаний сохраняются в данных волны",
	)


func _check_duration_formatting() -> void:
	_check(
		editor._format_duration(3661) == "01:01:01"
		and editor._format_duration(604800) == "168:00:00",
		"Время отображается как ЧЧ:ММ:СС, включая длительность больше суток",
	)
	var valid := editor._parse_duration("00:02:05", 604800, true, "Время старта")
	_check(
		bool(valid["valid"]) and int(valid["seconds"]) == 125,
		"Ввод ЧЧ:ММ:СС корректно преобразуется в секунды",
	)
	var invalid := editor._parse_duration("00:60:00", 604800, true, "Время старта")
	_check(not bool(invalid["valid"]), "Некорректное время отклоняется явно")


func _contains_text(node: Node, text: String) -> bool:
	if node is Label and str((node as Label).text) == text:
		return true
	for child in node.get_children():
		if _contains_text(child, text):
			return true
	return false


func _check_tavern_objective() -> void:
	editor._mode = "front_line"
	editor._catalog_by_key["city_building_tavern"] = {
		"item_key": "city_building_tavern",
		"kind": "object",
		"category": "city_building",
		"representation": "sprite",
		"footprint_w": 13,
		"footprint_h": 13,
	}
	editor._open_tavern_settings()
	_check(
		editor._tavern_settings_dialog.visible
		and int(editor._tavern_hp_spin.value) == SPAWN_RULES.DEFAULT_TAVERN_HP,
		"Настройки таверны открываются с 1000 HP по умолчанию",
	)
	editor._tavern_hp_spin.value = 2345
	editor._save_tavern_settings()
	editor._ensure_front_line_tavern()
	var object_layer := editor._layer_by_type(editor.LAYER_OBJECT)
	_check(
		str(object_layer["cells"].get("3:1", "")) == "city_building_tavern",
		"Таверна автоматически размещается цельным 13×13 объектом",
	)
	var payload := editor._spawn_payload()
	_check(
		payload.back() == {"type": SPAWN_RULES.TYPE_OBJECTIVE, "settings": {"max_hp": 2345}},
		"Максимальное здоровье таверны добавляется в настройки карты",
	)
	editor._load_map_payload({
		"id": 9,
		"name": "Front Line",
		"map_w": 16,
		"map_h": 16,
		"cells": [],
		"editor_layers": [],
		"spawns": payload,
	})
	_check(
		int(editor._tavern_settings["max_hp"]) == 2345
		and str(editor._layer_by_type(editor.LAYER_OBJECT)["cells"].get("3:1", ""))
			== "city_building_tavern",
		"Загрузка карты восстанавливает здоровье и автоматическую таверну",
	)
	editor._save_map()
	_check(
		editor.saved_payload["spawns"].back()["settings"]["max_hp"] == 2345,
		"Сохранение карты сохраняет заданное здоровье таверны",
	)
	editor._mode = "tower"
