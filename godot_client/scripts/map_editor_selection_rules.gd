extends RefCounted


static func rect_between(first: Vector2i, second: Vector2i) -> Rect2i:
	var left := mini(first.x, second.x)
	var top := mini(first.y, second.y)
	var right := maxi(first.x, second.x)
	var bottom := maxi(first.y, second.y)
	return Rect2i(left, top, right - left + 1, bottom - top + 1)


static func contains(selection: Rect2i, cell: Vector2i) -> bool:
	return selection.has_area() and selection.has_point(cell)


# targets: слои, которые редактируются (тайлы и объекты, видимые и не заблокированные).
static func copy(targets: Array, selection: Rect2i) -> Dictionary:
	if not selection.has_area():
		return {}
	var parts: Array = []
	var count := 0
	for layer in targets:
		var cells: Dictionary = layer["cells"]
		var entries: Array = []
		for key in cells:
			var cell := parse_key(str(key))
			if contains(selection, cell):
				entries.append([cell.x - selection.position.x, cell.y - selection.position.y, str(cells[key])])
		if entries.is_empty():
			continue
		count += entries.size()
		parts.append({"layer_id": int(layer["id"]), "layer_type": str(layer["type"]), "cells": entries})
	if count == 0:
		return {}
	return {"w": selection.size.x, "h": selection.size.y, "parts": parts, "count": count}


# Возвращает {"error": текст или "", "count": число перенесённых клеток}. При ошибке карта не меняется.
static func move(targets: Array, selection: Rect2i, delta: Vector2i, map_size: Vector2i) -> Dictionary:
	var moving: Array = []
	if not selection.has_area() or delta == Vector2i.ZERO:
		return {"error": "", "count": 0}
	for layer in targets:
		var cells: Dictionary = layer["cells"]
		var found: Array = []
		for key in cells:
			var cell := parse_key(str(key))
			if contains(selection, cell):
				found.append([cell, str(cells[key])])
		if not found.is_empty():
			moving.append({"cells": cells, "found": found})
	var count := 0
	for entry in moving:
		for item in entry["found"]:
			if not _inside(item[0] + delta, map_size):
				return {"error": "Выделение выходит за край карты", "count": 0}
			count += 1
	for entry in moving:
		var cells: Dictionary = entry["cells"]
		for item in entry["found"]:
			cells.erase(cell_key(item[0]))
	for entry in moving:
		var cells: Dictionary = entry["cells"]
		for item in entry["found"]:
			cells[cell_key(item[0] + delta)] = item[1]
	return {"error": "", "count": count}


static func delete(targets: Array, selection: Rect2i) -> int:
	if not selection.has_area():
		return 0
	var count := 0
	for layer in targets:
		var cells: Dictionary = layer["cells"]
		var doomed: Array = []
		for key in cells:
			if contains(selection, parse_key(str(key))):
				doomed.append(key)
		for key in doomed:
			cells.erase(key)
		count += doomed.size()
	return count


# Возвращает {"error", "count", "skipped", "rect"}: skipped — клетки куска, для которых не нашлось подходящего слоя.
static func paste(targets: Array, stamp: Dictionary, origin: Vector2i, map_size: Vector2i, active_layer_id: int) -> Dictionary:
	for part in stamp["parts"]:
		for item in part["cells"]:
			if not _inside(origin + Vector2i(item[0], item[1]), map_size):
				return {"error": "Кусок выходит за край карты", "count": 0, "skipped": 0, "rect": Rect2i()}
	var count := 0
	var skipped := 0
	for part in stamp["parts"]:
		var layer := paste_target(targets, part, active_layer_id)
		if layer.is_empty():
			skipped += part["cells"].size()
			continue
		var cells: Dictionary = layer["cells"]
		for item in part["cells"]:
			cells[cell_key(origin + Vector2i(item[0], item[1]))] = str(item[2])
			count += 1
	var width := mini(int(stamp["w"]), map_size.x - origin.x)
	var height := mini(int(stamp["h"]), map_size.y - origin.y)
	return {"error": "", "count": count, "skipped": skipped, "rect": Rect2i(origin, Vector2i(width, height))}


# Слой для куска: тот же слой, если он редактируется; иначе активный слой того же типа; иначе первый такой слой.
static func paste_target(targets: Array, part: Dictionary, active_layer_id: int) -> Dictionary:
	var layer_type := str(part["layer_type"])
	var wanted_id := int(part["layer_id"])
	var active := {}
	var first := {}
	for layer in targets:
		if str(layer["type"]) != layer_type:
			continue
		if int(layer["id"]) == wanted_id:
			return layer
		if int(layer["id"]) == active_layer_id:
			active = layer
		if first.is_empty():
			first = layer
	return active if not active.is_empty() else first


static func cell_key(cell: Vector2i) -> String:
	return "%d:%d" % [cell.x, cell.y]


static func parse_key(key: String) -> Vector2i:
	var parts := key.split(":")
	if parts.size() != 2:
		return Vector2i(-1, -1)
	return Vector2i(int(parts[0]), int(parts[1]))


static func _inside(cell: Vector2i, map_size: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < map_size.x and cell.y < map_size.y
