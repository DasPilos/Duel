extends RefCounted
# Город Радбург на карте мира: draw_city_exterior (scenes/city/exterior.py) с PNG-модулями из assets,
# обводка и подпись из _draw_objects (scenes/world_map_scene.py). Стены и постройки рисуются в мировых
# координатах Python, поэтому вызывающий код задаёт преобразование камеры до вызова.

const RULES := preload("res://scripts/world_map_town_rules.gd")
const DECK_SPRITE := preload("res://scripts/deck_player_sprite_rules.gd")
const FARM_HOUSE_ASSET := "town/farm/house.png"
const LUMBER_HOUSE_ASSET := "town/lumber_camp/house.png"
const KEEP_ASSET := "fighters/equipment/placeholders/building_town_radburg.png"
const SHADOW_COLOR := Color8(12, 17, 15)
const GROUND_COLOR := Color8(49, 57, 56)
const GROUND_BORDER_COLOR := Color8(102, 115, 110)
const TOWER_BORDER_COLOR := Color8(35, 42, 43)
const MERLON_COLOR := Color8(34, 40, 41)
const GATE_FILL_COLOR := Color8(29, 34, 34)
const GATE_BORDER_COLOR := Color8(224, 184, 95)
const WOOD_COLOR := Color8(82, 54, 34)
const RAIL_COLOR := Color8(158, 109, 61)
const WOOD_LEVEL_5_COLOR := Color8(105, 112, 111)
const RAIL_LEVEL_5_COLOR := Color8(168, 176, 174)
const STONE_COLOR := Color8(96, 104, 104)
const STONE_DARK_COLOR := Color8(60, 66, 67)
const LOG_COLOR := Color8(145, 97, 53)
const TRENCH_COLOR := Color8(137, 103, 62)
const FARM_WALL_COLOR := Color8(132, 94, 64)
const LUMBER_WALL_COLOR := Color8(145, 119, 83)
const HOUSE_BORDER_COLOR := Color8(61, 48, 38)
const FLAG_POLE_COLOR := Color8(65, 47, 34)
const FLAG_COLOR := Color8(220, 194, 106)
const ELLIPSE_SEGMENTS := 32
const WINDOW_FILL := Color8(15, 20, 28, 245)
const WINDOW_BORDER := Color8(220, 185, 60)
const WINDOW_TITLE := Color8(255, 225, 120)
const STATUS_COLOR := Color8(80, 255, 120)
const WINDOW_RULE := Color8(50, 65, 80)
const CLOSE_FILL := Color8(45, 30, 35)
const CLOSE_HOVER := Color8(180, 50, 50)
const CLOSE_BORDER := Color8(220, 100, 100)
const INFO_TEXT := Color8(210, 215, 220)
const INFO_IN_RANGE := Color8(80, 255, 120)
const INFO_OUT_RANGE := Color8(160, 160, 160)
const BUTTON_ACTIVE := Color8(45, 80, 130)
const BUTTON_ACTIVE_HOVER := Color8(70, 120, 180)
const BUTTON_IDLE := Color8(55, 55, 60)
const BUTTON_IDLE_HOVER := Color8(75, 75, 80)
const BUTTON_TEXT := Color8(255, 255, 255)
const BUTTON_IDLE_TEXT := Color8(170, 170, 175)
const NOTICE_FILL := Color8(40, 25, 25)
const NOTICE_BORDER := Color8(200, 80, 70)
const NOTICE_TEXT := Color8(255, 120, 100)

var _textures: Dictionary = {}
var _badge_font_cache: Font


# Обводка как в _draw_objects: выбранный город — жёлтая 3 px, наведение — голубое, иначе серо-синее.
func draw_town(canvas: CanvasItem, rect: Rect2, visual: Dictionary, hovered: bool, active := false) -> void:
	_draw_exterior(canvas, rect, visual)
	var style := StyleBoxFlat.new()
	style.draw_center = false
	style.set_corner_radius_all(RULES.OUTLINE_RADIUS_PX)
	if active:
		style.set_border_width_all(RULES.ACTIVE_BORDER_PX)
		style.border_color = RULES.ACTIVE_OUTLINE
		canvas.draw_style_box(style, rect)
		return
	style.set_border_width_all(RULES.OUTLINE_BORDER_PX)
	style.border_color = RULES.OUTLINE_HOVER if hovered else RULES.OUTLINE_DEFAULT
	canvas.draw_style_box(style, rect.grow(4.0) if hovered else rect)


# Плашка над объектом в экранных координатах: нижний край текста на anchor, как draw_map_badge в Python.
func draw_badge(canvas: CanvasItem, anchor: Vector2, text: String, border: Color, ui_scale: float) -> void:
	var font := _badge_font()
	var font_size := roundi(RULES.BADGE_FONT_PX * ui_scale)
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var text_height := font.get_height(font_size)
	var pad := RULES.BADGE_PAD_PX * ui_scale
	var box := Rect2(
		anchor.x - text_width * 0.5 - pad.x,
		anchor.y - text_height - pad.y,
		text_width + pad.x * 2.0,
		text_height + pad.y * 2.0,
	)
	var style := StyleBoxFlat.new()
	style.bg_color = RULES.BADGE_BACKGROUND
	style.set_border_width_all(1)
	style.border_color = border
	style.set_corner_radius_all(roundi(3.0 * ui_scale))
	canvas.draw_style_box(style, box)
	canvas.draw_string(font, box.position + Vector2(pad.x, pad.y + font.get_ascent(font_size)), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, RULES.BADGE_TEXT)


# Окно активного объекта, как _draw_active_window в Python: название, статус, радиус, описание и кнопка действия.
func draw_window(canvas: CanvasItem, layout: Dictionary, town: Dictionary, in_range: bool, notice: String, mouse: Vector2, ui_scale: float) -> void:
	var window: Rect2 = layout["window"]
	var origin := window.position
	canvas.draw_style_box(_box(WINDOW_FILL, WINDOW_BORDER, 8.0 * ui_scale), window)
	_draw_text(canvas, ThemeDB.fallback_font, origin + Vector2(14.0, 12.0) * ui_scale, RULES.title_text(town), roundi(20.0 * ui_scale), WINDOW_TITLE)
	_draw_text(canvas, _badge_font(), origin + Vector2(14.0, 40.0) * ui_scale, RULES.STATUS_TEXT, roundi(13.0 * ui_scale), STATUS_COLOR)
	_draw_close(canvas, layout["close"], mouse, ui_scale)
	canvas.draw_line(origin + Vector2(14.0, 62.0) * ui_scale, Vector2(window.end.x - 14.0 * ui_scale, origin.y + 62.0 * ui_scale), WINDOW_RULE, 1.0)
	var info_size := roundi(11.0 * ui_scale)
	_draw_text(canvas, ThemeDB.fallback_font, origin + Vector2(14.0, 72.0) * ui_scale, RULES.type_text(town), info_size, INFO_TEXT)
	_draw_text(canvas, ThemeDB.fallback_font, origin + Vector2(14.0, 86.0) * ui_scale, RULES.range_text(in_range), info_size, INFO_IN_RANGE if in_range else INFO_OUT_RANGE)
	var line_top := 102.0
	for line in RULES.description_lines(str(town.get("desc", ""))):
		_draw_text(canvas, ThemeDB.fallback_font, origin + Vector2(14.0, line_top) * ui_scale, str(line), info_size, INFO_TEXT)
		line_top += 14.0
	_draw_action(canvas, layout["action"], notice, in_range, mouse, ui_scale)


func _draw_close(canvas: CanvasItem, close: Rect2, mouse: Vector2, ui_scale: float) -> void:
	canvas.draw_style_box(_box(CLOSE_HOVER if close.has_point(mouse) else CLOSE_FILL, CLOSE_BORDER, 4.0 * ui_scale), close)
	var inset := close.size * 0.3
	canvas.draw_line(close.position + inset, close.end - inset, Color.WHITE, 1.5)
	canvas.draw_line(Vector2(close.end.x - inset.x, close.position.y + inset.y), Vector2(close.position.x + inset.x, close.end.y - inset.y), Color.WHITE, 1.5)


# Кнопка: в радиусе — синяя, вне — серая; вместо надписи во время отказа показывается фраза красным, как в Python.
func _draw_action(canvas: CanvasItem, action: Rect2, notice: String, in_range: bool, mouse: Vector2, ui_scale: float) -> void:
	var font := ThemeDB.fallback_font
	var font_size := roundi(16.0 * ui_scale)
	if not notice.is_empty():
		canvas.draw_style_box(_box(NOTICE_FILL, NOTICE_BORDER, 4.0 * ui_scale), action)
		_draw_centered(canvas, font, action, notice, font_size, NOTICE_TEXT)
		return
	var hovered := action.has_point(mouse)
	var fill := BUTTON_ACTIVE_HOVER if hovered else BUTTON_ACTIVE
	var text_color := BUTTON_TEXT
	if not in_range:
		fill = BUTTON_IDLE_HOVER if hovered else BUTTON_IDLE
		text_color = BUTTON_IDLE_TEXT
	canvas.draw_style_box(_box(fill, fill, 4.0 * ui_scale), action)
	_draw_centered(canvas, font, action, RULES.ENTER_LABEL, font_size, text_color)


func _draw_text(canvas: CanvasItem, font: Font, top_left: Vector2, text: String, font_size: int, color: Color) -> void:
	canvas.draw_string(font, Vector2(top_left.x, top_left.y + font_size * 0.9), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _draw_centered(canvas: CanvasItem, font: Font, rect: Rect2, text: String, font_size: int, color: Color) -> void:
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	canvas.draw_string(font, Vector2(rect.get_center().x - width * 0.5, rect.get_center().y + font_size * 0.35), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _box(fill: Color, border: Color, radius: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(roundi(radius))
	return style


func _draw_exterior(canvas: CanvasItem, rect: Rect2, visual: Dictionary) -> void:
	var unit := RULES.scale_for(rect)
	var inset := RULES.inset_for(unit)
	var bounds := RULES.bounds_for(rect, inset)
	var plan := RULES.wall_plan(visual)
	var level_tier := RULES.tier(RULES.city_level(visual))

	canvas.draw_colored_polygon(_ellipse_points(Rect2(
		bounds.position.x + inset, bounds.end.y - inset,
		maxf(1.0, bounds.size.x - 2.0 * inset), maxf(5.0, inset * 3.0),
	)), SHADOW_COLOR)
	canvas.draw_rect(bounds, GROUND_COLOR)
	_frame(canvas, bounds, GROUND_BORDER_COLOR, maxi(1, roundi(2.0 * unit)))

	var tint := mini(level_tier * 2, 24)
	var tower_color := Color8(86 + tint, 94 + tint, 92 + tint)
	var merlon := maxi(4, roundi(9.0 * unit))
	for tower in RULES.tower_rects(bounds, unit):
		canvas.draw_rect(tower, tower_color)
		_frame(canvas, tower, TOWER_BORDER_COLOR, maxi(1, roundi(2.0 * unit)))
		for merlon_x in range(int(tower.position.x) + 3, int(tower.end.x) - merlon, merlon * 2):
			canvas.draw_rect(Rect2(merlon_x, tower.position.y - 2.0, merlon, floori(merlon / 2.0) + 1), MERLON_COLOR)

	match str(plan["kind"]):
		"stone":
			for side in 4:
				_draw_stone_fence(canvas, bounds, side, unit)
		"upgrade":
			var stages: Array = plan["stages"]
			for side in 4:
				_draw_stone_wall_stage(canvas, bounds, side, unit, str(stages[side]))
		"completed":
			for side in 4:
				_draw_completed_fence(canvas, bounds, side, unit, int(plan["tier"]))
		_:
			for side in plan["completed"]:
				_draw_completed_fence(canvas, bounds, int(side), unit, 1)
			if bool(plan["trench"]):
				_draw_trench(canvas, bounds, unit)
			for side in plan["work_sides"]:
				_draw_work_logs(canvas, bounds, int(side), unit)

	for gate in RULES.gate_rects(bounds, unit):
		canvas.draw_rect(gate, GATE_FILL_COLOR)
		_frame(canvas, gate, GATE_BORDER_COLOR, 1)

	var houses := RULES.house_rects(bounds, level_tier, unit)
	for index in houses.size():
		_draw_residence(canvas, houses[index], level_tier, index)

	_draw_keep(canvas, RULES.keep_rect(bounds))


func _draw_residence(canvas: CanvasItem, rect: Rect2, level_tier: int, index: int) -> void:
	var is_farm := level_tier == 1
	canvas.draw_rect(rect, FARM_WALL_COLOR if is_farm else LUMBER_WALL_COLOR)
	_frame(canvas, rect, HOUSE_BORDER_COLOR, maxi(1, floori(rect.size.x / 24.0)))
	var texture := _texture(FARM_HOUSE_ASSET if is_farm else LUMBER_HOUSE_ASSET)
	if texture != null:
		canvas.draw_texture_rect(texture, rect, false)
	if level_tier == 2:
		var flag_x := rect.position.x + floorf(rect.size.x / 2.0) + float((index % 3) - 1) * maxi(2, floori(rect.size.x / 5.0))
		var flag_top := rect.position.y + maxi(2, floori(rect.size.y / 10.0))
		canvas.draw_line(Vector2(flag_x, flag_top), Vector2(flag_x, flag_top + maxi(3, floori(rect.size.y / 4.0))),
			FLAG_POLE_COLOR, 1.0)
		canvas.draw_colored_polygon(PackedVector2Array([
			Vector2(flag_x, flag_top),
			Vector2(flag_x + maxi(3, floori(rect.size.x / 5.0)), flag_top + maxi(1, floori(rect.size.y / 12.0))),
			Vector2(flag_x, flag_top + maxi(2, floori(rect.size.y / 6.0))),
		]), FLAG_COLOR)


# Донжон рисуется одним модулем: draw_city_exterior вызывает draw_keep(screen, keep, 1), башни там нет.
func _draw_keep(canvas: CanvasItem, rect: Rect2) -> void:
	var texture := _texture(KEEP_ASSET)
	if texture != null:
		canvas.draw_texture_rect(texture, rect, false)
	else:
		canvas.draw_rect(rect, STONE_COLOR)


func _draw_completed_fence(canvas: CanvasItem, bounds: Rect2, side: int, unit: float, level: int) -> void:
	var wood := WOOD_COLOR if level < 5 else WOOD_LEVEL_5_COLOR
	var rail := RAIL_COLOR if level < 5 else RAIL_LEVEL_5_COLOR
	var step := maxi(5, roundi(18.0 * unit))
	var gap := maxi(4, roundi(24.0 * unit))
	var post := roundi(7.0 * unit)
	var wood_width := float(maxi(2, roundi(5.0 * unit)))
	var thin := float(maxi(1, roundi(2.0 * unit)))
	if side <= 1:
		var y := bounds.position.y if side == 0 else bounds.end.y
		for interval in _gap_intervals(bounds.position.x, bounds.end.x, RULES.center_x(bounds), gap):
			canvas.draw_line(Vector2(interval.x, y), Vector2(interval.y, y), wood, wood_width)
			canvas.draw_line(Vector2(interval.x, y - 2.0), Vector2(interval.y, y - 2.0), rail, thin)
			for post_x in range(int(interval.x), int(interval.y) + 1, step):
				canvas.draw_line(Vector2(post_x, y - post), Vector2(post_x, y + post), wood, thin)
	else:
		var x := bounds.end.x if side == 2 else bounds.position.x
		for interval in _gap_intervals(bounds.position.y, bounds.end.y, RULES.center_y(bounds), gap):
			canvas.draw_line(Vector2(x, interval.x), Vector2(x, interval.y), wood, wood_width)
			canvas.draw_line(Vector2(x - 2.0, interval.x), Vector2(x - 2.0, interval.y), rail, thin)
			for post_y in range(int(interval.x), int(interval.y) + 1, step):
				canvas.draw_line(Vector2(x - post, post_y), Vector2(x + post, post_y), wood, thin)


func _draw_stone_fence(canvas: CanvasItem, bounds: Rect2, side: int, unit: float) -> void:
	var height := maxi(4, roundi(7.0 * unit))
	var gap := maxi(4, roundi(24.0 * unit))
	var merlon := maxi(3, roundi(6.0 * unit))
	var half_merlon := floori(merlon / 2.0)
	if side <= 1:
		var y := int(bounds.position.y if side == 0 else bounds.end.y)
		for interval in _gap_intervals(bounds.position.x, bounds.end.x, RULES.center_x(bounds), gap):
			var x1 := int(interval.x)
			var x2 := int(interval.y)
			var body := Rect2(x1, y - height, x2 - x1, height * 2)
			canvas.draw_rect(body, STONE_COLOR)
			_frame(canvas, body, STONE_DARK_COLOR, 1)
			for merlon_x in range(x1, x2 - merlon + 1, merlon * 2):
				canvas.draw_rect(Rect2(merlon_x, y - height - half_merlon, merlon, half_merlon + 1), STONE_DARK_COLOR)
	else:
		var x := int(bounds.end.x if side == 2 else bounds.position.x)
		for interval in _gap_intervals(bounds.position.y, bounds.end.y, RULES.center_y(bounds), gap):
			var y1 := int(interval.x)
			var y2 := int(interval.y)
			var body := Rect2(x - height, y1, height * 2, y2 - y1)
			canvas.draw_rect(body, STONE_COLOR)
			_frame(canvas, body, STONE_DARK_COLOR, 1)
			for merlon_y in range(y1, y2 - merlon + 1, merlon * 2):
				canvas.draw_rect(Rect2(x - height - half_merlon, merlon_y, half_merlon + 1, merlon), STONE_DARK_COLOR)


# Стадия 2→3 по стороне: stone, building (брёвна и половинная каменная стена) или wood.
func _draw_stone_wall_stage(canvas: CanvasItem, bounds: Rect2, side: int, unit: float, stage: String) -> void:
	if stage == "stone":
		_draw_stone_fence(canvas, bounds, side, unit)
	elif stage == "building":
		_draw_work_logs(canvas, bounds, side, unit)
		_draw_stone_fence(canvas, bounds, side, unit * 0.5)
	else:
		_draw_completed_fence(canvas, bounds, side, unit, 2)


func _draw_work_logs(canvas: CanvasItem, bounds: Rect2, side: int, unit: float) -> void:
	var length := maxi(4, roundi(14.0 * unit))
	var step := maxi(8, roundi(28.0 * unit))
	var width := float(maxi(2, roundi(3.0 * unit)))
	if side <= 1:
		var y := bounds.position.y + 4.0 if side == 0 else bounds.end.y - 4.0
		for x in range(int(bounds.position.x) + 4, int(bounds.end.x) - 4, step):
			canvas.draw_line(Vector2(x, y + 2.0), Vector2(x + length, y - 2.0), LOG_COLOR, width)
	else:
		var x := bounds.end.x - 4.0 if side == 2 else bounds.position.x + 4.0
		for y in range(int(bounds.position.y) + 4, int(bounds.end.y) - 4, step):
			canvas.draw_line(Vector2(x + 2.0, y), Vector2(x - 2.0, y + length), LOG_COLOR, width)


func _draw_trench(canvas: CanvasItem, bounds: Rect2, unit: float) -> void:
	var step := maxi(8, roundi(18.0 * unit))
	var trench_length := maxi(4, roundi(10.0 * unit))
	var left := int(bounds.position.x)
	var top := int(bounds.position.y)
	var right := int(bounds.end.x)
	var bottom := int(bounds.end.y)
	for x in range(left + 4, right - 4, step):
		canvas.draw_line(Vector2(x, top + 4), Vector2(mini(x + trench_length, right - 4), top + 4), TRENCH_COLOR, 3.0)
		canvas.draw_line(Vector2(x, bottom - 4), Vector2(mini(x + trench_length, right - 4), bottom - 4), TRENCH_COLOR, 3.0)
	for y in range(top + 4, bottom - 4, step):
		canvas.draw_line(Vector2(left + 4, y), Vector2(left + 4, mini(y + trench_length, bottom - 4)), TRENCH_COLOR, 3.0)
		canvas.draw_line(Vector2(right - 4, y), Vector2(right - 4, mini(y + trench_length, bottom - 4)), TRENCH_COLOR, 3.0)


# Два участка стороны с разрывом под ворота: как интервалы ((left, centerx - gap), (centerx + gap, right)).
func _gap_intervals(start: float, end: float, center: int, gap: int) -> Array:
	return [Vector2(start, center - gap), Vector2(center + gap, end)]


# Рамка внутри прямоугольника, как pygame.draw.rect с толщиной width.
func _frame(canvas: CanvasItem, rect: Rect2, color: Color, width: int) -> void:
	var thickness := float(width)
	canvas.draw_rect(Rect2(rect.position.x, rect.position.y, rect.size.x, thickness), color)
	canvas.draw_rect(Rect2(rect.position.x, rect.end.y - thickness, rect.size.x, thickness), color)
	canvas.draw_rect(Rect2(rect.position.x, rect.position.y, thickness, rect.size.y), color)
	canvas.draw_rect(Rect2(rect.end.x - thickness, rect.position.y, thickness, rect.size.y), color)


func _ellipse_points(rect: Rect2) -> PackedVector2Array:
	var points := PackedVector2Array()
	var center := rect.get_center()
	var radius := rect.size * 0.5
	for index in ELLIPSE_SEGMENTS:
		var angle := TAU * index / ELLIPSE_SEGMENTS
		points.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y))
	return points


func _texture(asset: String) -> Texture2D:
	if not _textures.has(asset):
		var path := DECK_SPRITE.assets_root(ProjectSettings.globalize_path("res://")).path_join(asset)
		var image: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
		_textures[asset] = ImageTexture.create_from_image(image) if image != null and not image.is_empty() else null
	return _textures[asset]


# Шрифт плашек — 13 px жирный, жирность задаётся как в economy_city_map.gd.
func _badge_font() -> Font:
	if _badge_font_cache == null:
		var bold := FontVariation.new()
		bold.base_font = ThemeDB.fallback_font
		bold.variation_embolden = 0.6
		_badge_font_cache = bold
	return _badge_font_cache
