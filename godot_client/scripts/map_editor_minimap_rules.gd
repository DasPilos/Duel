extends RefCounted

const MAX_SIDE := 170.0
const MARGIN := 12.0
const MINI_EMPTY := Color(18.0 / 255.0, 20.0 / 255.0, 24.0 / 255.0)
const MINI_UNKNOWN := Color(200.0 / 255.0, 200.0 / 255.0, 200.0 / 255.0)
const VIEW_COLOR := Color(255.0 / 255.0, 220.0 / 255.0, 90.0 / 255.0)
const CATEGORY_RGB := {
	"ground": [88, 132, 64],
	"floor": [104, 146, 76],
	"berry": [120, 150, 70],
	"road": [150, 118, 78],
	"water": [56, 104, 168],
	"bridge": [142, 98, 58],
	"rock": [122, 122, 128],
	"tree": [28, 76, 40],
	"old_tree": [34, 84, 46],
	"stump": [92, 70, 48],
	"log": [100, 76, 52],
}
const ATLAS_CATEGORY := {
	"Почва": "ground",
	"Вода": "water",
	"Объекты": "tree",
	"Детали": "floor",
}


static func rect_for(canvas_size: Vector2, map_size: Vector2i) -> Rect2:
	if map_size.x <= 0 or map_size.y <= 0:
		return Rect2()
	var side := minf(MAX_SIDE, minf(canvas_size.x, canvas_size.y) * 0.35)
	var size := size_for(map_size, side)
	return Rect2(canvas_size - Vector2(MARGIN, MARGIN) - size, size)


static func size_for(map_size: Vector2i, max_side: float) -> Vector2:
	var longest := maxi(map_size.x, map_size.y)
	if longest <= 0 or max_side <= 0.0:
		return Vector2.ZERO
	return Vector2(map_size) * (max_side / float(longest))


static func tile_at(point: Vector2, rect: Rect2, map_size: Vector2i) -> Vector2i:
	if map_size.x <= 0 or map_size.y <= 0 or rect.size.x <= 0.0 or rect.size.y <= 0.0:
		return Vector2i.ZERO
	var scale := rect.size / Vector2(map_size)
	var local := (point - rect.position) / scale
	return Vector2i(clampi(floori(local.x), 0, map_size.x - 1), clampi(floori(local.y), 0, map_size.y - 1))


static func view_rect(pan: Vector2, tile_size: float, canvas_size: Vector2, map_size: Vector2i, rect: Rect2) -> Rect2:
	var first := Vector2(-pan.x / tile_size, -pan.y / tile_size)
	var visible := canvas_size / tile_size
	var left := clampf(first.x, 0.0, float(map_size.x))
	var top := clampf(first.y, 0.0, float(map_size.y))
	var right := clampf(first.x + visible.x, 0.0, float(map_size.x))
	var bottom := clampf(first.y + visible.y, 0.0, float(map_size.y))
	var scale := rect.size / Vector2(map_size)
	return Rect2(rect.position + Vector2(left, top) * scale, Vector2(right - left, bottom - top) * scale)


static func pan_for_center(tile: Vector2i, canvas_size: Vector2, tile_size: float) -> Vector2:
	return canvas_size / 2.0 - (Vector2(tile) + Vector2(0.5, 0.5)) * tile_size


static func color_for_category(category: String) -> Color:
	if not CATEGORY_RGB.has(category):
		return MINI_UNKNOWN
	var rgb: Array = CATEGORY_RGB[category]
	return Color8(int(rgb[0]), int(rgb[1]), int(rgb[2]))


static func atlas_category(label: String) -> String:
	return str(ATLAS_CATEGORY.get(label, ""))


static func build_image(map_size: Vector2i, layers: Array, category_of: Callable) -> Image:
	var image := Image.create(maxi(map_size.x, 1), maxi(map_size.y, 1), false, Image.FORMAT_RGBA8)
	image.fill(MINI_EMPTY)
	for layer in layers:
		var cells: Dictionary = layer["cells"]
		for key in cells:
			var parts := str(key).split(":")
			if parts.size() != 2:
				continue
			var x := int(parts[0])
			var y := int(parts[1])
			if x < 0 or y < 0 or x >= map_size.x or y >= map_size.y:
				continue
			image.set_pixel(x, y, color_for_category(str(category_of.call(str(cells[key])))))
	return image
