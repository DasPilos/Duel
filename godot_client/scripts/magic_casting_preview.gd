extends RefCounted

const ASSET_ROOT := "res://assets/base_tails/spells/PNG/Character_casting_magic"
const FRAME_SIZE := Vector2i(64, 64)
const FRAME_COLUMNS := 5
const FRAME_ROWS := 4

var _frames_by_animation: Dictionary = {}


func frame_texture(profession: String, level: int, direction: String, frame_index: int) -> Texture2D:
	if level < 1 or level > 9:
		push_error("Magic casting preview level is out of range: %d" % level)
		return null
	var asset_class := _asset_class_name(profession)
	if asset_class.is_empty():
		push_error("Magic casting preview does not support profession: %s" % profession)
		return null
	var animation_key := "%s:%d" % [asset_class, level]
	if not _frames_by_animation.has(animation_key):
		var frames := _load_animation_frames(asset_class, level)
		if frames.is_empty():
			return null
		_frames_by_animation[animation_key] = frames
	var frames: Array = _frames_by_animation[animation_key]
	var row := _direction_row(direction)
	var column := posmod(frame_index, FRAME_COLUMNS)
	return frames[row * FRAME_COLUMNS + column] as Texture2D


func _asset_class_name(profession: String) -> String:
	match profession.to_lower():
		"warrior", "swordsman":
			return "Swordsman"
		"archer":
			return "Archer"
		"mage":
			return "Mage"
		_:
			return ""


func _direction_row(direction: String) -> int:
	match direction.to_lower():
		"w", "west", "left":
			return 1
		"e", "east", "right":
			return 2
		"n", "north", "up":
			return 3
		_:
			return 0


func _load_animation_frames(asset_class: String, level: int) -> Array:
	var filename_level := "lv7" if asset_class == "Archer" and level == 7 else "lvl%d" % level
	var path := "%s/%s/Lvl%d/%s_%s_Magic.png" % [ASSET_ROOT, asset_class, level, asset_class, filename_level]
	var sheet := load(path) as Texture2D
	if sheet == null:
		push_error("Magic casting preview sheet could not be loaded: %s" % path)
		return []
	var image := sheet.get_image()
	if image == null or image.is_empty() or image.get_width() != FRAME_SIZE.x * FRAME_COLUMNS or image.get_height() != FRAME_SIZE.y * FRAME_ROWS:
		push_error("Magic casting preview sheet has an unexpected size: %s" % path)
		return []
	var frames: Array[Texture2D] = []
	for row in FRAME_ROWS:
		for column in FRAME_COLUMNS:
			var frame_image := image.get_region(Rect2i(Vector2i(column, row) * FRAME_SIZE, FRAME_SIZE))
			frames.append(ImageTexture.create_from_image(frame_image))
	return frames
