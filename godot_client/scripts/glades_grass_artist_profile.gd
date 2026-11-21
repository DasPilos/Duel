extends RefCounted

const REFERENCE_PATH := "res://assets/base_tails/Biome/craftpix-net-189510-grassland-top-down-tileset-pixel-art/Tiled_files/Glades.tmx"
const GRASS_FIRST_GID := 1
const WATER_FIRST_GID := 743
const GRASS_COLUMNS := 53
const GRASS_MIN_X := 1
const GRASS_MAX_X := 6
const GRASS_MIN_Y := 0
const GRASS_MAX_Y := 2
const NEIGHBOR_OFFSETS := [
	Vector2i.UP,
	Vector2i(1, -1),
	Vector2i.RIGHT,
	Vector2i(1, 1),
	Vector2i.DOWN,
	Vector2i(-1, 1),
	Vector2i.LEFT,
	Vector2i(-1, -1),
]


static func load_rules() -> Dictionary:
	var parser := XMLParser.new()
	var open_error := parser.open(REFERENCE_PATH)
	if open_error != OK:
		push_error(
			"Не удалось открыть образец луга %s: %s"
			% [REFERENCE_PATH, error_string(open_error)],
		)
		return {}
	var sample_cells: Dictionary = {}
	var in_main_space := false
	var in_chunk := false
	var chunk_origin := Vector2i.ZERO
	var chunk_width := 0
	var chunk_height := 0
	var chunk_index := 0
	var found_main_space := false
	while true:
		var read_error := parser.read()
		if read_error == ERR_FILE_EOF:
			break
		if read_error != OK:
			push_error("Ошибка XML при чтении образца луга %s." % REFERENCE_PATH)
			return {}
		var node_type := parser.get_node_type()
		var node_name := ""
		if node_type in [XMLParser.NODE_ELEMENT, XMLParser.NODE_ELEMENT_END]:
			node_name = parser.get_node_name()
		if node_type == XMLParser.NODE_ELEMENT:
			if node_name == "layer":
				in_main_space = parser.get_named_attribute_value("name") == "main space"
				found_main_space = found_main_space or in_main_space
			elif node_name == "chunk" and in_main_space:
				in_chunk = true
				chunk_origin = Vector2i(
					parser.get_named_attribute_value("x").to_int(),
					parser.get_named_attribute_value("y").to_int(),
				)
				chunk_width = parser.get_named_attribute_value("width").to_int()
				chunk_height = parser.get_named_attribute_value("height").to_int()
				chunk_index = 0
		elif node_type == XMLParser.NODE_TEXT and in_main_space and in_chunk:
			var gid_tokens := parser.get_node_data().split(",", true)
			for token_index in range(gid_tokens.size()):
				var gid_text := str(gid_tokens[token_index]).strip_edges()
				if gid_text.is_empty() and token_index == gid_tokens.size() - 1:
					continue
				if chunk_width <= 0 or chunk_height <= 0 \
					or chunk_index >= chunk_width * chunk_height:
					push_error("Повреждены размеры блока тайлов в образце луга.")
					return {}
				var gid := gid_text.to_int() & 0x1fffffff if not gid_text.is_empty() else 0
				if gid >= GRASS_FIRST_GID and gid < WATER_FIRST_GID:
					var tile_id := gid - GRASS_FIRST_GID
					var tile_coords := Vector2i(tile_id % GRASS_COLUMNS, tile_id / GRASS_COLUMNS)
					if tile_coords.x >= GRASS_MIN_X and tile_coords.x <= GRASS_MAX_X \
						and tile_coords.y >= GRASS_MIN_Y and tile_coords.y <= GRASS_MAX_Y:
						var sample_cell := chunk_origin + Vector2i(
							chunk_index % chunk_width,
							chunk_index / chunk_width,
						)
						sample_cells[sample_cell] = tile_coords
				chunk_index += 1
		elif node_type == XMLParser.NODE_ELEMENT_END:
			if node_name == "chunk" and in_chunk:
				if chunk_index != chunk_width * chunk_height:
					push_error("Неполный блок тайлов в образце луга.")
					return {}
				in_chunk = false
			elif node_name == "layer":
				in_main_space = false
	if not found_main_space or sample_cells.is_empty():
		push_error("В образце луга не найден слой main space для автотайлинга.")
		return {}
	var rules: Dictionary = {}
	for sample_cell_variant in sample_cells:
		var sample_cell: Vector2i = sample_cell_variant
		var mask := 0
		for index in range(NEIGHBOR_OFFSETS.size()):
			if sample_cells.has(sample_cell + NEIGHBOR_OFFSETS[index]):
				mask |= 1 << index
		var candidates: Array = rules.get(mask, [])
		var tile_coords: Vector2i = sample_cells[sample_cell]
		if not candidates.has(tile_coords):
			candidates.append(tile_coords)
		rules[mask] = candidates
	for mask in rules:
		var candidates: Array = rules[mask]
		candidates.sort_custom(func(first: Vector2i, second: Vector2i) -> bool:
			if first.y == second.y:
				return first.x < second.x
			return first.y < second.y
		)
	return {"rules": rules, "sample_cells": sample_cells.size()}
