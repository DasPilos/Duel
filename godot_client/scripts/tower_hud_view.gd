extends RefCounted

# Вид HUD башни: панель персонажа слева вверху, миникарта и координаты слева внизу. Рисует на переданном CanvasItem,
# геометрия и правила — в tower_hud_rules.gd. Хотбар не дублируется: hotbar.gd уже совпадает с ui/hotbar.py в масштабе 2/3.

const RULES := preload("res://scripts/tower_hud_rules.gd")
const CLASS_RULES := preload("res://scripts/deck_class_card_rules.gd")
const DETAILS_RULES := preload("res://scripts/create_character_details_rules.gd")

const NAME_FONT_SIZE := 13  # Python font 20
const COORDS_FONT_SIZE := 13  # Python font 20
const BADGE_FONT_SIZE := 9  # Python badge_font 13 bold
const PLAYER_MARK_RADIUS := 2.0  # Python 3
const PLAYER_DOT_RADIUS := 1.0  # Python 2
const CORPSE_MARK_SIZE := 3  # Python 5
const CORPSE_LABEL_OFFSET := Vector2(3.0, -5.0)  # Python (+5, -7)
const TOWN_IDS := ["town_radburg", "main_castle"]

const GRASS_COLOR := Color8(92, 116, 62)
const FOREST_COLOR := Color8(34, 72, 38)
const DRY_COLOR := Color8(118, 98, 62)
const WATER_COLOR := Color8(40, 112, 150)
const MOUNTAIN_COLOR := Color8(122, 114, 104)
const ROAD_COLOR := Color8(176, 146, 96)
const BRIDGE_COLOR := Color8(196, 150, 84)
const TOWER_COLOR := Color8(120, 112, 100)
const TOWN_COLOR := Color8(230, 190, 90)
const OBJECT_COLOR := Color8(200, 200, 210)
const FRAME_COLOR := Color8(220, 180, 70)
const PLAYER_MARK_COLOR := Color8(255, 255, 255)
const PLAYER_DOT_COLOR := Color8(220, 60, 60)
const CORPSE_MARK_COLOR := Color8(210, 210, 220)
const CORPSE_LABEL_COLOR := Color8(235, 235, 245)
const MOB_MARK_COLOR := Color8(255, 78, 55)
const MOB_DOT_COLOR := Color8(255, 220, 120)

const NAME_COLOR := Color8(255, 235, 150)
const HP_TEXT_COLOR := Color8(255, 110, 110)
const HP_FILL_COLOR := Color8(210, 80, 80)
const MP_TEXT_COLOR := Color8(120, 170, 255)
const MP_FILL_COLOR := Color8(60, 140, 220)
const BAR_BACKGROUND_COLOR := Color8(20, 22, 28)
const BAR_BORDER_COLOR := Color8(60, 66, 76)
const PORTRAIT_BACKGROUND_COLOR := Color8(15, 18, 24)
const PORTRAIT_BORDER_COLOR := Color8(180, 150, 60)
const COORDS_BACKGROUND_COLOR := Color8(15, 18, 24, 235)
const COORDS_TEXT_COLOR := Color8(240, 240, 240)

static var _icon_cache: Dictionary = {}

var _grid: Vector2i = RULES.DEFAULT_GRID
var _minimap_image: Image
var _minimap_texture: ImageTexture
var _portrait_box: StyleBoxFlat
var _coords_box: StyleBoxFlat
var _badge_font: Font


func layout(view_size: Vector2) -> Dictionary:
	return RULES.layout(view_size, _grid)


func minimap_image() -> Image:
	return _minimap_image


# terrain — ответ сервера на карту (ключи map, tiles, roads, bridges, objects, obstacles), как в Python _build_minimap.
func configure_minimap(terrain: Dictionary) -> void:
	var map_data := _dict(terrain.get("map"))
	_grid = Vector2i(
		maxi(1, int(map_data.get("tiles_w", _grid.x))),
		maxi(1, int(map_data.get("tiles_h", _grid.y))),
	)
	var size := RULES.minimap_size(RULES.MINIMAP_HEIGHT, _grid)
	var scale := RULES.tile_scale(size, _grid)
	var image := Image.create(size.x, size.y, false, Image.FORMAT_RGBA8)
	image.fill(GRASS_COLOR)
	for obstacle in _array(terrain.get("obstacles")):
		if obstacle is Dictionary:
			_fill_polygon(image, _scaled_points(obstacle.get("points"), scale), _obstacle_color(str(obstacle.get("type", ""))))
	var tiles := _dict(terrain.get("tiles"))
	var roads := _dict(terrain.get("roads"))
	var layers := [
		[RULES.tiles_from_rows(tiles.get("mountain")), MOUNTAIN_COLOR],
		[RULES.tiles_from_rows(tiles.get("forest")), FOREST_COLOR],
		[RULES.tiles_from_rows(tiles.get("dry")), DRY_COLOR],
		[RULES.tiles_from_rows(tiles.get("water")), WATER_COLOR],
		[RULES.tiles_from_pairs(roads.get("tiles")) + RULES.tiles_from_rows(tiles.get("paths")), ROAD_COLOR],
	]
	for layer in layers:
		for tile in layer[0]:
			_fill_rect(image, RULES.minimap_tile_rect(tile, scale), layer[1])
	for bridge in _array(terrain.get("bridges")):
		if bridge is Dictionary:
			for tile in RULES.tiles_from_pairs(bridge.get("tiles")):
				_fill_rect(image, RULES.minimap_tile_rect(tile, scale), BRIDGE_COLOR)
	for map_object in _array(terrain.get("objects")):
		if map_object is Dictionary:
			var is_town := TOWN_IDS.has(str(map_object.get("id", "")))
			_fill_rect(image, _object_rect(map_object, scale), TOWN_COLOR if is_town else OBJECT_COLOR)
	_frame(image, FRAME_COLOR)
	_minimap_image = image
	_minimap_texture = null


# rect — layout()["player_panel"]; содержимое рисуется от его левого верхнего угла.
func draw_player_panel(canvas: CanvasItem, rect: Rect2, character: Dictionary, fighter: Dictionary, portrait: Texture2D) -> void:
	var font := _font_for(canvas)
	var origin := rect.position
	var name_x := origin.x
	var icon := profession_icon(str(character.get("type", "")))
	if icon != null:
		canvas.draw_texture_rect(icon, Rect2(origin, Vector2(RULES.ICON_SIZE, RULES.ICON_SIZE)), false)
		name_x += RULES.ICON_SIZE + RULES.PANEL_GAP
	_draw_text_middle(canvas, font, NAME_FONT_SIZE, Vector2(name_x, origin.y + RULES.ICON_SIZE / 2.0), RULES.display_name(character), NAME_COLOR)

	var portrait_rect := Rect2(origin.x, origin.y + RULES.ICON_SIZE + RULES.PANEL_GAP, RULES.PORTRAIT_SIZE, RULES.PORTRAIT_SIZE)
	canvas.draw_style_box(_portrait_style(), portrait_rect)
	if portrait != null:
		var drawn := RULES.fit_size(Vector2(portrait.get_width(), portrait.get_height()), RULES.PORTRAIT_FIT)
		if drawn != Vector2.ZERO:
			canvas.draw_texture_rect(portrait, Rect2(portrait_rect.get_center() - drawn / 2.0, drawn), false)

	var hp := float(fighter.get("hp", 0.0))
	var max_hp := float(fighter.get("max_hp", 0.0))
	var mp := float(fighter.get("mp", 0.0))
	var max_mp := float(fighter.get("max_mp", 0.0))
	var bars_x := portrait_rect.end.x + RULES.PANEL_GAP + RULES.BAR_INDENT
	var next_y := _draw_resource_bar(canvas, font, Vector2(bars_x, portrait_rect.position.y), RULES.hp_label(hp, max_hp), HP_TEXT_COLOR, HP_FILL_COLOR, hp, max_hp)
	_draw_resource_bar(canvas, font, Vector2(bars_x, next_y), RULES.mp_label(mp, max_mp), MP_TEXT_COLOR, MP_FILL_COLOR, mp, max_mp)


# Миникарта рисуется в rect (layout()["minimap"]); маркеры и подписи расстояний — как в _draw_minimap.
func draw_minimap(canvas: CanvasItem, rect: Rect2, player_world: Vector2, corpses: Array, mobs: Array = []) -> void:
	var texture := _minimap_texture_or_null()
	if texture == null:
		return
	canvas.draw_texture_rect(texture, rect, false)
	var world_size := Vector2(_grid) * RULES.TILE_SIZE
	var marker := RULES.world_to_minimap(player_world, rect, world_size)
	var center := Vector2(int(marker.x), int(marker.y))
	canvas.draw_circle(center, PLAYER_MARK_RADIUS, PLAYER_MARK_COLOR)
	canvas.draw_circle(center, PLAYER_DOT_RADIUS, PLAYER_DOT_COLOR)
	var font := _badge_font_for()
	for corpse in corpses:
		if not corpse is Dictionary:
			continue
		var corpse_world := Vector2(float(corpse.get("x", 0.0)), float(corpse.get("y", 0.0)))
		var point := RULES.world_to_minimap(corpse_world, rect, world_size)
		var cx := int(point.x)
		var cy := int(point.y)
		canvas.draw_rect(Rect2(cx - 1, cy - 1, CORPSE_MARK_SIZE, CORPSE_MARK_SIZE), CORPSE_MARK_COLOR)
		var tiles := RULES.py_round(RULES.corpse_distance_tiles(corpse_world, player_world))
		_draw_text_top(canvas, font, BADGE_FONT_SIZE, Vector2(cx, cy) + CORPSE_LABEL_OFFSET, RULES.tiles_label(tiles), CORPSE_LABEL_COLOR)
	for mob in mobs:
		if not mob is Dictionary:
			continue
		var mob_world := Vector2(float(mob.get("x", 0.0)), float(mob.get("y", 0.0)))
		var mob_point := RULES.world_to_minimap(mob_world, rect, world_size)
		canvas.draw_circle(mob_point, 3.0, MOB_MARK_COLOR)
		canvas.draw_circle(mob_point, 1.0, MOB_DOT_COLOR)


# Координаты курсора и персонажа в rect (layout()["coords"]). Ширина коробки подогнана под текст, как в Python.
func draw_coords(canvas: CanvasItem, rect: Rect2, cursor_world: Vector2, player_world: Vector2) -> void:
	var font := _font_for(canvas)
	var lines := RULES.coords_lines(cursor_world, player_world)
	var widest := 0.0
	for line in lines:
		widest = maxf(widest, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, COORDS_FONT_SIZE).x)
	var box := Rect2(rect.position, Vector2(minf(rect.size.x, widest + 2.0 * RULES.COORDS_PAD_X), rect.size.y))
	canvas.draw_style_box(_coords_style(), box)
	var text_size := RULES.fit_font_size(widest, rect.size.x - 2.0 * RULES.COORDS_PAD_X, COORDS_FONT_SIZE)
	for index in lines.size():
		var top_left := box.position + Vector2(RULES.COORDS_PAD_X, RULES.COORDS_PAD_Y + index * RULES.COORDS_LINE_HEIGHT)
		_draw_text_top(canvas, font, text_size, top_left, lines[index], COORDS_TEXT_COLOR)


func _draw_resource_bar(canvas: CanvasItem, font: Font, top_left: Vector2, label: String, text_color: Color, fill_color: Color, value: float, maximum: float) -> float:
	_draw_text_top(canvas, font, NAME_FONT_SIZE, top_left, label, text_color)
	var bar := Rect2(top_left.x, top_left.y + font.get_height(NAME_FONT_SIZE) + RULES.LABEL_GAP, RULES.BAR_WIDTH, RULES.BAR_HEIGHT)
	canvas.draw_rect(bar, BAR_BACKGROUND_COLOR)
	var fill_width := RULES.bar_fill_width(RULES.BAR_WIDTH, RULES.bar_ratio(value, maximum))
	canvas.draw_rect(Rect2(bar.position, Vector2(fill_width, RULES.BAR_HEIGHT)), fill_color)
	canvas.draw_rect(bar, BAR_BORDER_COLOR, false, 1.0)
	return bar.end.y + RULES.BAR_STEP


func _draw_text_top(canvas: CanvasItem, font: Font, font_size: int, top_left: Vector2, text: String, color: Color) -> void:
	canvas.draw_string(font, top_left + Vector2(0.0, font.get_ascent(font_size)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _draw_text_middle(canvas: CanvasItem, font: Font, font_size: int, left_center: Vector2, text: String, color: Color) -> void:
	var baseline := left_center.y + (font.get_ascent(font_size) - font.get_descent(font_size)) / 2.0
	canvas.draw_string(font, Vector2(left_center.x, baseline), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _font_for(canvas: CanvasItem) -> Font:
	if canvas is Control:
		return (canvas as Control).get_theme_default_font()
	return ThemeDB.fallback_font


func _badge_font_for() -> Font:
	if _badge_font == null:
		var bold := FontVariation.new()
		bold.base_font = ThemeDB.fallback_font
		bold.variation_embolden = 0.6
		_badge_font = bold
	return _badge_font


func _portrait_style() -> StyleBoxFlat:
	if _portrait_box == null:
		_portrait_box = _box_style(PORTRAIT_BACKGROUND_COLOR, PORTRAIT_BORDER_COLOR, 3)
	return _portrait_box


func _coords_style() -> StyleBoxFlat:
	if _coords_box == null:
		_coords_box = _box_style(COORDS_BACKGROUND_COLOR, FRAME_COLOR, 4)
	return _coords_box


static func _box_style(background: Color, border: Color, radius: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(radius)
	return style


func _minimap_texture_or_null() -> Texture2D:
	if _minimap_image == null:
		return null
	if _minimap_texture == null:
		_minimap_texture = ImageTexture.create_from_image(_minimap_image)
	return _minimap_texture


func _object_rect(map_object: Dictionary, scale: Vector2) -> Rect2i:
	var x := float(map_object.get("tile_x", 0)) * scale.x
	var y := float(map_object.get("tile_y", 0)) * scale.y
	var width := maxf(2.0, float(map_object.get("tile_w", 1)) * scale.x)
	var height := maxf(2.0, float(map_object.get("tile_h", 1)) * scale.y)
	return Rect2i(int(x), int(y), int(width), int(height))


func _scaled_points(points: Variant, scale: Vector2) -> PackedVector2Array:
	var result := PackedVector2Array()
	if not points is Array:
		return result
	for point in points:
		if point is Array and point.size() >= 2:
			result.append(Vector2(float(point[0]) / RULES.TILE_SIZE * scale.x, float(point[1]) / RULES.TILE_SIZE * scale.y))
	return result


func _obstacle_color(kind: String) -> Color:
	match kind:
		"forest":
			return FOREST_COLOR
		"lake":
			return WATER_COLOR
		"tower":
			return TOWER_COLOR
	return MOUNTAIN_COLOR


func _fill_polygon(image: Image, vertices: PackedVector2Array, color: Color) -> void:
	if vertices.size() < 3:
		return
	var top := int(vertices[0].y)
	var bottom := top
	for vertex in vertices:
		top = mini(top, int(vertex.y))
		bottom = maxi(bottom, int(vertex.y))
	for row in range(maxi(top, 0), mini(bottom, image.get_height() - 1) + 1):
		for span in RULES.polygon_row_spans(vertices, row):
			var left := maxi(span.x, 0)
			var right := mini(span.y, image.get_width() - 1)
			if right >= left:
				image.fill_rect(Rect2i(left, row, right - left + 1, 1), color)


func _fill_rect(image: Image, rect: Rect2i, color: Color) -> void:
	var clipped := rect.intersection(Rect2i(Vector2i.ZERO, Vector2i(image.get_width(), image.get_height())))
	if clipped.has_area():
		image.fill_rect(clipped, color)


func _frame(image: Image, color: Color) -> void:
	var width := image.get_width()
	var height := image.get_height()
	image.fill_rect(Rect2i(0, 0, width, 1), color)
	image.fill_rect(Rect2i(0, height - 1, width, 1), color)
	image.fill_rect(Rect2i(0, 0, 1, height), color)
	image.fill_rect(Rect2i(width - 1, 0, 1, height), color)


static func profession_icon(profession: String) -> Texture2D:
	if _icon_cache.has(profession):
		return _icon_cache[profession]
	var texture: Texture2D = null
	var path := DETAILS_RULES.class_icon_path(_assets_root(), profession)
	if not path.is_empty():
		var image := Image.load_from_file(path)
		if image != null and not image.is_empty():
			image.convert(Image.FORMAT_RGBA8)
			image.resize(RULES.ICON_SIZE, RULES.ICON_SIZE, Image.INTERPOLATE_BILINEAR)
			texture = ImageTexture.create_from_image(image)
	_icon_cache[profession] = texture
	return texture


static func _assets_root() -> String:
	return CLASS_RULES.default_assets_root(ProjectSettings.globalize_path("res://").trim_suffix("/"))


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _array(value: Variant) -> Array:
	return value if value is Array else []
