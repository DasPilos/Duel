extends Node

const DRAFTS_RULES = preload("res://scripts/map_editor_drafts_rules.gd")


class DraftEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var editor: DraftEditor
var folder := ""
var first_id := ""
var second_id := ""
var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _run() -> void:
	folder = OS.get_environment("TEMP").path_join("map_editor_drafts_test_%d" % Time.get_ticks_usec())
	editor = DraftEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._local_drafts_folder = folder
	editor._catalog_by_key = {
		"grass": {"item_key": "grass", "kind": "ground", "category": "grass"},
		"sand": {"item_key": "sand", "kind": "ground", "category": "ground"},
		"rock": {"item_key": "rock", "kind": "object", "category": "rock"},
	}
	editor._map_width.value = 16
	editor._map_height.value = 16
	_check_name_and_ids()
	await _check_files_and_format()
	await _check_list_and_load()
	_check_duplicates_and_overwrite()
	_check_publish_and_server_marks()
	_check_editor_roundtrip()
	_check_editor_refusals()
	_check_shortcuts()
	_cleanup()
	_finish()


func _finish() -> void:
	if is_instance_valid(editor):
		editor.free()
	for failure in _failures:
		push_error(failure)
	if _failures.is_empty():
		print("map_editor_drafts_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(0 if _failures.is_empty() else 1)


func _press(keycode: Key, ctrl := false) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	editor._unhandled_key_input(event)


func _layer_named(layer_name: String) -> Dictionary:
	for layer in editor._layers:
		if str(layer.get("name", "")) == layer_name:
			return layer
	return {}


func _draft_file_count() -> int:
	return DRAFTS_RULES.read_all(folder).size()


func _check_name_and_ids() -> void:
	_check(DRAFTS_RULES.name_error("   ") != "", "Пустое название не принимается")
	_check(DRAFTS_RULES.name_error("".lpad(64, "я")) == "", "Название из 64 символов допустимо")
	_check(DRAFTS_RULES.name_error("".lpad(65, "я")) == "Название черновика: от 1 до 64 символов", "Название длиннее 64 символов отклоняется")
	var id := DRAFTS_RULES.new_id()
	var hex := true
	for index in range(id.length()):
		hex = hex and "0123456789abcdef".contains(id.substr(index, 1))
	_check(id.length() == 32 and hex and DRAFTS_RULES.is_safe_id(id), "Идентификатор черновика — 32 шестнадцатеричных символа, как uuid4 в Python")
	_check(not DRAFTS_RULES.is_safe_id("../escape") and not DRAFTS_RULES.is_safe_id(""), "Идентификатор с путём отклоняется")


func _check_files_and_format() -> void:
	var cells := [{"layer": "ground", "x": 1, "y": 2, "key": "grass"}]
	var layers := [{
		"id": 1, "name": "Земля", "type": "tile", "parent_id": 0, "visible": true, "locked": false,
		"animal_settings": {}, "cells": [{"layer": "ground", "x": 1, "y": 2, "key": "grass"}],
	}]
	var result: Dictionary = DRAFTS_RULES.save_draft(folder, "  Карта  ", cells, 16, 16, "", "economy", [], [], layers)
	_check(str(result["error"]).is_empty(), "Черновик сохраняется без ошибок")
	var draft: Dictionary = result["draft"]
	first_id = str(draft["id"])
	_check(str(draft["name"]) == "Карта", "Название обрезается по краям")
	var path := folder.path_join(first_id + ".json")
	_check(FileAccess.file_exists(path), "Файл называется идентификатором черновика и имеет расширение .json")
	var text := FileAccess.get_file_as_string(path)
	_check(text.contains("\"map_w\": 16,") and not text.contains("16.0"), "Размеры пишутся целыми числами, как в Python")
	_check(text.contains("\"x\": 1,") and not text.contains("\"x\": 1.0"), "Координаты клеток пишутся целыми числами")
	_check(text.contains("\"name\": \"Карта\"") and text.contains("\"server_map\": null"), "Название пишется без экранирования, связь с сервером пустая")
	var parsed: Dictionary = JSON.parse_string(text)
	var all_keys := true
	for key in ["id", "name", "map_w", "map_h", "mode", "updated_at", "cells", "published", "mobs", "spawns", "server_map"]:
		all_keys = all_keys and parsed.has(key)
	_check(all_keys, "В файле есть все ключи формата Python")
	_check(parsed["published"].is_empty() and str(parsed["mode"]) == "economy", "Новый черновик без публикаций, режим сохранён")
	_check(parsed["editor_layers"] is Array and parsed["editor_layers"].size() == 1, "Слои редактора сохраняются отдельным ключом")
	var rewritten: Dictionary = DRAFTS_RULES.save_draft(folder, "Карта", cells, 16, 16, first_id, "", [], [], layers)
	_check(str(rewritten["error"]).is_empty() and str(rewritten["draft"]["id"]) == first_id, "Сохранение с тем же идентификатором перезаписывает черновик")


func _check_list_and_load() -> void:
	await get_tree().create_timer(0.02).timeout
	var second: Dictionary = DRAFTS_RULES.save_draft(folder, "Вторая", [], 16, 16, "", "economy", [], [], [])
	second_id = str(second["draft"]["id"])
	var listed: Array[Dictionary] = DRAFTS_RULES.list_drafts(folder)
	_check(listed.size() == 2 and str(listed[0]["name"]) == "Вторая", "Список черновиков: самые свежие сверху")
	_check(int(listed[0]["map_w"]) == 16 and listed[0]["active_worlds"].is_empty(), "В списке есть размеры и нет публикаций")
	var loaded: Dictionary = DRAFTS_RULES.load_draft(folder, first_id)
	_check(str(loaded["error"]).is_empty() and str(loaded["draft"]["name"]) == "Карта", "Черновик загружается по идентификатору")
	_check(str(DRAFTS_RULES.load_draft(folder, "0123abcd")["error"]) == "Черновик не найден, возможно он был удалён", "Загрузка несуществующего черновика сообщает об этом")
	var empty_name: Dictionary = DRAFTS_RULES.save_draft(folder, "   ", cells_for_test(), 16, 16, "", "economy", [], [], [])
	_check(str(empty_name["error"]) == "Название черновика: от 1 до 64 символов" and _draft_file_count() == 2, "Черновик без названия не записывается")


func cells_for_test() -> Array:
	return [{"layer": "ground", "x": 0, "y": 0, "key": "grass"}]


func _check_duplicates_and_overwrite() -> void:
	var clash: Dictionary = DRAFTS_RULES.save_draft(folder, "Вторая", [], 16, 16, first_id, "", [], [], [])
	_check(str(clash["error"]) == "Черновик «Вторая» уже есть, выберите другое название" and clash["draft"].is_empty(), "Название занятого черновика не принимается")
	var overwrite: Dictionary = DRAFTS_RULES.save_draft(folder, "Вторая", [], 16, 16, second_id, "", [], [], [])
	_check(str(overwrite["error"]).is_empty(), "Черновик может сохраниться под своим же названием")
	var renamed: Dictionary = DRAFTS_RULES.save_draft(folder, "Первая", [], 16, 16, first_id, "", [], [], [])
	_check(str(renamed["error"]).is_empty() and str(DRAFTS_RULES.load_draft(folder, first_id)["draft"]["name"]) == "Первая", "Переименование сохраняет идентификатор")


func _check_publish_and_server_marks() -> void:
	DRAFTS_RULES.mark_published(folder, first_id, 7, "Мир Альфа")
	var first: Dictionary = DRAFTS_RULES.load_draft(folder, first_id)["draft"]
	_check(first["published"].size() == 1 and str(first["published"][0]["world_name"]) == "Мир Альфа", "Публикация записывает мир в черновик")
	DRAFTS_RULES.mark_published(folder, second_id, 7, "Мир Альфа")
	first = DRAFTS_RULES.load_draft(folder, first_id)["draft"]
	var second: Dictionary = DRAFTS_RULES.load_draft(folder, second_id)["draft"]
	_check(first["published"].is_empty() and second["published"].size() == 1, "В мире одна карта: отметка переходит к новому черновику")
	DRAFTS_RULES.mark_server_map(folder, second_id, 42, "Карта на сервере")
	var text := FileAccess.get_file_as_string(folder.path_join(second_id + ".json"))
	_check(text.contains("\"saved_id\": 42,") and text.contains("\"map_w\": 16,") and not text.contains("42.0"), "Перезапись отметок не превращает числа в дробные")
	second = DRAFTS_RULES.load_draft(folder, second_id)["draft"]
	_check(str(second["server_map"]["saved_name"]) == "Карта на сервере", "Связь с серверной картой сохраняется в черновике")
	_check(DRAFTS_RULES.delete_draft(folder, first_id).is_empty(), "Черновик удаляется с диска")
	_check(DRAFTS_RULES.delete_draft(folder, first_id) == "Черновик не найден, возможно он уже удалён", "Повторное удаление сообщает, что черновика уже нет")
	_check(_draft_file_count() == 1, "После удаления остаётся один файл")


func _check_editor_roundtrip() -> void:
	editor._create_default_layers()
	editor._render_layers()
	editor._mode = "front_line"
	editor._map_name.text = "Редактор"
	editor._layers[0]["cells"] = {"1:1": "grass", "2:1": "sand"}
	editor._layers[1]["cells"] = {"3:3": "rock"}
	var extra: Dictionary = editor._new_layer("Доп", editor.LAYER_TILE, 0)
	extra["visible"] = false
	extra["cells"] = {"5:5": "grass"}
	editor._layers.append(extra)
	_check(editor._save_local_draft(), "Сохранение локального черновика из редактора проходит")
	var saved_id: String = editor._local_draft_id
	_check(not saved_id.is_empty() and editor._status.text == "Черновик «Редактор» сохранён на этом компьютере.", "Редактор запоминает черновик и пишет статус")
	editor._create_default_layers()
	editor._render_layers()
	editor._map_name.text = ""
	editor._open_local_draft(saved_id)
	_check(
		editor._map_name.text == "Редактор" and editor._mode == "front_line",
		"Открытие черновика Front Line возвращает название и игровой режим",
	)
	_check(_layer_named("Земля")["cells"] == {"1:1": "grass", "2:1": "sand"}, "Открытие возвращает клетки земли")
	_check(_layer_named("Объекты")["cells"] == {"3:3": "rock"}, "Открытие возвращает объекты")
	var restored := _layer_named("Доп")
	_check(not restored.is_empty() and not bool(restored["visible"]) and restored["cells"] == {"5:5": "grass"}, "Скрытый слой восстанавливается со своими клетками")
	_check(editor._saved_id == 0, "Черновик без связи с сервером не подставляет серверный ID")
	_check(editor._selected_local_draft_id() == saved_id, "Список локальных черновиков показывает открытый")


func _check_editor_refusals() -> void:
	var foreign: Dictionary = DRAFTS_RULES.save_draft(folder, "Чужой режим", [], 16, 16, "", "deck", [], [], [])
	var foreign_id := str(foreign["draft"]["id"])
	editor._open_local_draft(foreign_id)
	_check(editor._status.text.begins_with("Черновик создан для режима") and editor._map_name.text == "Редактор", "Черновик другого режима не открывается")
	var saved_id: String = editor._local_draft_id
	DRAFTS_RULES.mark_published(folder, saved_id, 9, "Мир Бета")
	editor._refresh_local_drafts(saved_id)
	editor._request_delete_local_draft()
	_check(editor._status.text == "Нельзя удалить: карта играет в мире «Мир Бета»" and str(DRAFTS_RULES.load_draft(folder, saved_id)["error"]).is_empty(), "Опубликованный черновик нельзя удалить")
	editor._delete_local_draft(foreign_id, ConfirmationDialog.new())
	_check(str(DRAFTS_RULES.load_draft(folder, foreign_id)["error"]) != "" and editor._status.text == "Черновик «Чужой режим» удалён с этого компьютера.", "Черновик удаляется с диска и статус называет его")


func _check_shortcuts() -> void:
	editor._map_name.text = ""
	_press(KEY_S, true)
	_check(editor._status.text == "Черновик не сохранён: Название черновика: от 1 до 64 символов", "Ctrl+S без названия сообщает об ошибке")
	editor._map_name.text = "Горячая"
	var open_id: String = editor._local_draft_id
	_press(KEY_S, true)
	_check(editor._local_draft_id == open_id and str(DRAFTS_RULES.load_draft(folder, open_id)["draft"]["name"]) == "Горячая", "Ctrl+S сохраняет открытый черновик под новым названием")
	editor._local_draft_id = ""
	editor._map_name.text = "Новая карта"
	_press(KEY_S, true)
	var created_id: String = editor._local_draft_id
	_check(not created_id.is_empty() and created_id != open_id and str(DRAFTS_RULES.load_draft(folder, created_id)["draft"]["name"]) == "Новая карта", "Ctrl+S без открытого черновика создаёт новый")
	editor._refresh_local_drafts(created_id)
	editor._map_name.text = ""
	_press(KEY_L, true)
	_check(editor._map_name.text == "Новая карта" and editor._local_draft_id == created_id, "Ctrl+L открывает выбранный черновик")
	editor._local_draft_select.clear()
	_press(KEY_L, true)
	_check(editor._status.text == "Сначала выберите черновик на этом компьютере.", "Ctrl+L без выбранного черновика подсказывает, что делать")


func _cleanup() -> void:
	var directory := DirAccess.open(folder)
	if directory != null:
		for file_name in directory.get_files():
			directory.remove(file_name)
	DirAccess.remove_absolute(folder)
	_check(not DirAccess.dir_exists_absolute(folder), "Временная папка черновиков удалена")
