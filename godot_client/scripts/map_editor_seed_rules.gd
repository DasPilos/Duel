extends RefCounted

const GROUND_TILE_SETS := [["water", "water"], ["paths", "road"], ["floor", "floor"], ["mountain", "rock"]]
const TILE_SET_NAMES := ["water", "paths", "floor", "mountain", "forest", "dry"]
const GRASS_CATEGORY := "grass"
const TREE_CATEGORY := "tree"
const DRY_CATEGORY := "old_tree"
const PROP_CATEGORIES := ["stump", "log"]


static func decode_tiles(rows: Array) -> Dictionary:
	var tiles := {}
	for row in rows:
		if row is Array and row.size() == 2:
			tiles[Vector2i(int(row[0]), int(row[1]))] = true
	return tiles


static func build_cells(terrain: Dictionary, catalog_by_key: Dictionary, map_w: int, map_h: int) -> Array:
	var tiles: Dictionary = terrain.get("tiles", {})
	var tile_sets := {}
	for name in TILE_SET_NAMES:
		tile_sets[name] = decode_tiles(tiles.get(name, []))
	var pools := _pools(catalog_by_key)
	var cells: Array = []
	for y in range(map_h):
		for x in range(map_w):
			var category := GRASS_CATEGORY
			for pair in GROUND_TILE_SETS:
				if tile_sets[pair[0]].has(Vector2i(x, y)):
					category = pair[1]
					break
			var key := _pick(pools["ground"].get(category, []), x, y)
			if not key.is_empty():
				cells.append({"layer": "ground", "x": x, "y": y, "key": key})
	var covered := {}
	var objects: Array = []
	for prop in terrain.get("props", []):
		if not prop is Dictionary or not str(prop.get("type", "")) in PROP_CATEGORIES:
			continue
		var lowest: Variant = _lowest_tile(prop.get("tiles", []))
		if lowest != null:
			_put_object(pools, catalog_by_key, str(prop["type"]), lowest.x, lowest.y, map_w, map_h, covered, objects)
	for tile in _sorted_tiles(tile_sets["forest"]):
		_put_object(pools, catalog_by_key, TREE_CATEGORY, tile.x, tile.y, map_w, map_h, covered, objects)
	for tile in _sorted_tiles(tile_sets["dry"]):
		_put_object(pools, catalog_by_key, DRY_CATEGORY, tile.x, tile.y, map_w, map_h, covered, objects)
	return cells + objects


static func _pick(keys: Array, x: int, y: int) -> String:
	if keys.is_empty():
		return ""
	return str(keys[((x * 73856093) ^ (y * 19349663)) % keys.size()])


static func _pools(catalog_by_key: Dictionary) -> Dictionary:
	var pools := {"ground": {}, "object": {}}
	var keys := catalog_by_key.keys()
	keys.sort()
	for key in keys:
		var item: Dictionary = catalog_by_key[key]
		var kind := str(item.get("kind", ""))
		if not pools.has(kind):
			continue
		var category := str(item.get("category", ""))
		if kind == "ground" and category == GRASS_CATEGORY and bool(item.get("blocks", false)):
			continue
		if not pools[kind].has(category):
			pools[kind][category] = []
		pools[kind][category].append(str(item.get("item_key", key)))
	return pools


static func _put_object(
	pools: Dictionary, catalog_by_key: Dictionary, category: String, x: int, y: int,
	map_w: int, map_h: int, covered: Dictionary, objects: Array
) -> void:
	var keys: Array = pools["object"].get(category, [])
	if keys.is_empty():
		return
	var item: Dictionary = catalog_by_key[_pick(keys, x, y)]
	var footprint: Array[Vector2i] = []
	for dx in range(int(item["footprint_w"])):
		for dy in range(int(item["footprint_h"])):
			footprint.append(Vector2i(x + dx, y + dy))
	for tile in footprint:
		if tile.x < 0 or tile.y < 0 or tile.x >= map_w or tile.y >= map_h or covered.has(tile):
			return
	for tile in footprint:
		covered[tile] = true
	objects.append({"layer": "object", "x": x, "y": y, "key": str(item["item_key"])})


static func _lowest_tile(tiles: Array) -> Variant:
	var lowest: Variant = null
	for tile in tiles:
		if not tile is Array or tile.size() != 2:
			continue
		var cell := Vector2i(int(tile[0]), int(tile[1]))
		if lowest == null or cell.x < lowest.x or (cell.x == lowest.x and cell.y < lowest.y):
			lowest = cell
	return lowest


static func _sorted_tiles(tile_set: Dictionary) -> Array:
	var tiles: Array = tile_set.keys()
	tiles.sort_custom(func(first: Vector2i, second: Vector2i) -> bool:
		return first.x < second.x or (first.x == second.x and first.y < second.y)
	)
	return tiles
