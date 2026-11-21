extends SceneTree

const GRASS_PROFILE = preload("res://scripts/glades_grass_artist_profile.gd")


func _initialize() -> void:
	var artist_data: Dictionary = GRASS_PROFILE.load_rules()
	var rules: Dictionary = artist_data.get("rules", {})
	var full_mask_tiles: Array = rules.get(255, [])
	if int(artist_data.get("sample_cells", 0)) != 674 \
		or rules.size() != 67 \
		or not full_mask_tiles.has(Vector2i(2, 1)) \
		or full_mask_tiles.size() != 4:
		push_error("Glades grass rules do not match the artist's main space layer.")
		quit(1)
		return
	for candidates in rules.values():
		for coords in candidates:
			if coords.x < 1 or coords.x > 6 or coords.y < 0 or coords.y > 2:
				push_error("The Glades grass profile contains a tile outside the grass field.")
				quit(1)
				return
	print("Glades grass artist profile smoke test passed: 674 cells, 67 masks.")
	quit(0)
