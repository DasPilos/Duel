extends RefCounted

const DEFAULT_FOLDER := "user://map_drafts"
const DEFAULT_MODE := "front_line"
const NAME_MAX := 64
const NOT_FOUND_TEXT := "Черновик не найден, возможно он был удалён"
const ALREADY_DELETED_TEXT := "Черновик не найден, возможно он уже удалён"
const INT_KEYS := ["map_w", "map_h", "x", "y", "world_id", "saved_id", "id", "parent_id", "patrol_radius"]


static func name_error(raw_name: String) -> String:
	var length := raw_name.strip_edges().length()
	if length < 1 or length > NAME_MAX:
		return "Название черновика: от 1 до %d символов" % NAME_MAX
	return ""


static func new_id() -> String:
	var id := ""
	for _index in range(4):
		id += "%08x" % (randi() & 0xFFFFFFFF)
	return id


static func build_draft(
	draft_id: String, name: String, map_w: int, map_h: int, mode: String,
	cells: Array, published: Array, mobs: Array, spawns: Array, server_map: Variant, editor_layers: Array,
) -> Dictionary:
	var stored_cells: Array = []
	for cell in cells:
		stored_cells.append({"layer": str(cell["layer"]), "x": int(cell["x"]), "y": int(cell["y"]), "key": str(cell["key"])})
	return {
		"id": draft_id,
		"name": name,
		"map_w": map_w,
		"map_h": map_h,
		"mode": mode,
		"updated_at": Time.get_unix_time_from_system(),
		"cells": stored_cells,
		"published": published,
		"mobs": mobs,
		"spawns": spawns,
		"server_map": server_map,
		"editor_layers": editor_layers,
	}


static func list_drafts(folder: String) -> Array[Dictionary]:
	var summaries: Array[Dictionary] = []
	for draft in read_all(folder):
		var worlds: Array[String] = []
		for item in draft.get("published", []):
			worlds.append(str(item.get("world_name", "")))
		summaries.append({
			"id": str(draft["id"]),
			"name": str(draft.get("name", "")),
			"map_w": int(draft.get("map_w", 0)),
			"map_h": int(draft.get("map_h", 0)),
			"mode": str(draft.get("mode", DEFAULT_MODE)),
			"updated_at": float(draft.get("updated_at", 0.0)),
			"active_worlds": worlds,
		})
	summaries.sort_custom(func(first: Dictionary, second: Dictionary) -> bool:
		return first["updated_at"] > second["updated_at"]
	)
	return summaries


# Возвращает {"draft": Dictionary, "error": текст или ""}.
static func load_draft(folder: String, draft_id: String) -> Dictionary:
	var draft := read_file(folder, draft_id)
	if draft.is_empty():
		return {"draft": {}, "error": NOT_FOUND_TEXT}
	return {"draft": draft, "error": ""}


# Создаёт черновик или перезаписывает draft_id; публикации и связь с сервером сохраняются. Возвращает {"draft", "error"}.
static func save_draft(
	folder: String, raw_name: String, cells: Array, map_w: int, map_h: int, draft_id: String,
	mode: String, mobs: Array, spawns: Array, editor_layers: Array,
) -> Dictionary:
	var name := raw_name.strip_edges()
	var error := name_error(name)
	if not error.is_empty():
		return {"draft": {}, "error": error}
	var published: Array = []
	var stored_mode := ""
	var stored_server_map: Variant = null
	for draft in read_all(folder):
		if str(draft.get("name", "")) == name and str(draft["id"]) != draft_id:
			return {"draft": {}, "error": "Черновик «%s» уже есть, выберите другое название" % name}
		if str(draft["id"]) == draft_id:
			published = draft.get("published", [])
			stored_mode = str(draft.get("mode", ""))
			stored_server_map = draft.get("server_map")
	var id := draft_id if not draft_id.is_empty() else new_id()
	if not is_safe_id(id):
		return {"draft": {}, "error": "Некорректный идентификатор черновика"}
	var chosen_mode := mode if not mode.is_empty() else (stored_mode if not stored_mode.is_empty() else DEFAULT_MODE)
	var data := build_draft(id, name, map_w, map_h, chosen_mode, cells, published, mobs, spawns, stored_server_map, editor_layers)
	var write_error := write_draft(folder, data)
	if not write_error.is_empty():
		return {"draft": {}, "error": write_error}
	return {"draft": data, "error": ""}


static func delete_draft(folder: String, draft_id: String) -> String:
	if not is_safe_id(draft_id):
		return ALREADY_DELETED_TEXT
	var directory := DirAccess.open(folder)
	if directory == null or not directory.file_exists(draft_id + ".json"):
		return ALREADY_DELETED_TEXT
	var error := directory.remove(draft_id + ".json")
	if error != OK:
		return "Не удалось удалить черновик: " + error_string(error)
	return ""


static func mark_server_map(folder: String, draft_id: String, saved_id: int, saved_name: String) -> void:
	for draft in read_all(folder):
		if str(draft["id"]) == draft_id:
			draft["server_map"] = {"saved_id": saved_id, "saved_name": saved_name}
			write_draft(folder, draft)


# В мире одна карта: у других черновиков отметка о мире снимается.
static func mark_published(folder: String, draft_id: String, world_id: int, world_name: String) -> void:
	for draft in read_all(folder):
		var published: Array = draft.get("published", [])
		var others: Array = []
		for item in published:
			if int(item.get("world_id", 0)) != world_id:
				others.append(item)
		if str(draft["id"]) == draft_id:
			others.append({"world_id": world_id, "world_name": world_name})
		if others != published:
			draft["published"] = others
			write_draft(folder, draft)


static func read_all(folder: String) -> Array[Dictionary]:
	var drafts: Array[Dictionary] = []
	var directory := DirAccess.open(folder)
	if directory == null:
		return drafts
	for file_name in directory.get_files():
		if not file_name.ends_with(".json"):
			continue
		var draft := read_file(folder, file_name.get_basename())
		if not draft.is_empty() and draft.has("id") and draft.has("name"):
			drafts.append(draft)
	return drafts


static func read_file(folder: String, draft_id: String) -> Dictionary:
	if not is_safe_id(draft_id):
		return {}
	var path := folder.path_join(draft_id + ".json")
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


static func write_draft(folder: String, data: Dictionary) -> String:
	var global_folder := ProjectSettings.globalize_path(folder)
	if not DirAccess.dir_exists_absolute(global_folder):
		var folder_error := DirAccess.make_dir_recursive_absolute(global_folder)
		if folder_error != OK:
			return "Не удалось создать папку черновиков: " + error_string(folder_error)
	var file := FileAccess.open(folder.path_join(str(data["id"]) + ".json"), FileAccess.WRITE)
	if file == null:
		return "Не удалось записать черновик: " + error_string(FileAccess.get_open_error())
	file.store_string(JSON.stringify(normalize_ints(data), " ", false))
	file.close()
	return ""


static func normalize_ints(value: Variant, key := "") -> Variant:
	if value is Dictionary:
		var result := {}
		for item_key in value:
			result[item_key] = normalize_ints(value[item_key], str(item_key))
		return result
	if value is Array:
		var items: Array = []
		for item in value:
			items.append(normalize_ints(item, key))
		return items
	if key in INT_KEYS and (value is float or value is int):
		return int(value)
	return value


static func is_safe_id(draft_id: String) -> bool:
	if draft_id.is_empty():
		return false
	for index in range(draft_id.length()):
		var code := draft_id.unicode_at(index)
		var allowed := (code >= 48 and code <= 57) or (code >= 65 and code <= 90) or (code >= 97 and code <= 122) or code == 45 or code == 95
		if not allowed:
			return false
	return true
