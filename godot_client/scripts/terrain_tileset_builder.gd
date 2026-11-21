extends RefCounted

const TILE_SIZE := 16
const BASE_TILE := Vector2i(2, 2)
const ATLAS_REGION := Rect2i(1, 1, 3, 3)


static func build(image: Image) -> Dictionary:
	if image == null or image.is_empty():
		return {"error": "Не удалось загрузить изображение тайлсета."}
	if image.get_width() % TILE_SIZE != 0 or image.get_height() % TILE_SIZE != 0:
		return {"error": "Размер изображения должен делиться на размер тайла %d×%d." % [TILE_SIZE, TILE_SIZE]}

	var texture := ImageTexture.create_from_image(image)
	var atlas := TileSetAtlasSource.new()
	atlas.texture = texture
	atlas.texture_region_size = Vector2i(TILE_SIZE, TILE_SIZE)
	var atlas_columns := image.get_width() / TILE_SIZE
	var atlas_rows := image.get_height() / TILE_SIZE
	for y in range(ATLAS_REGION.position.y, ATLAS_REGION.end.y):
		for x in range(ATLAS_REGION.position.x, ATLAS_REGION.end.x):
			var coords := Vector2i(x, y)
			atlas.create_tile(coords)

	var tile_set := TileSet.new()
	tile_set.tile_size = Vector2i(TILE_SIZE, TILE_SIZE)
	var source_id := tile_set.add_source(atlas)
	return {
		"tile_set": tile_set,
		"source_id": source_id,
		"columns": atlas_columns,
		"rows": atlas_rows,
		"terrain_tile_count": ATLAS_REGION.size.x * ATLAS_REGION.size.y,
		"base_tile": BASE_TILE,
	}
