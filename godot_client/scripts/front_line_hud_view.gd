extends "res://scripts/tower_hud_view.gd"

const PANEL_SIZE := Vector2(580, 124)
# Координаты внутри панели в масштабе 1; опыт на всю ширину над ХП и МП.
const PORTRAIT_RECT := Rect2(12, 10, 80, 90)
const NAME_RECT := Rect2(12, 103, 80, 15)
const XP_RECT := Rect2(104, 10, 464, 16)
const HP_RECT := Rect2(104, 30, 228, 16)
const MP_RECT := Rect2(340, 30, 228, 16)
const SLOTS_RECT := Rect2(104, 52, 464, 48)
const CAPTION_RECT := Rect2(104, 103, 464, 15)
const SPECIAL_SLOTS := 9
const EDGE_MARGIN := 6.0
const FRAME_WIDTH := 5.0
const SECTION_GAP := 12.0
const PANEL_COLOR := Color8(18, 20, 26)
const BRONZE_COLOR := Color8(122, 103, 73)
const EDGE_LIGHT := Color8(185, 160, 113)
const SLOT_COLOR := Color8(10, 12, 18)
const INSET_EDGE := Color8(57, 61, 72)
const LABEL_COLOR := Color8(225, 216, 195)
const XP_COLOR := Color8(178, 132, 40)
const BAR_TEXT_COLOR := Color8(249, 238, 220)

var _framed_portrait: Texture2D
var _portrait_source := Rect2()


func layout(view_size: Vector2) -> Dictionary:
	var map_limit := Vector2(minf(192.0, view_size.x * 0.22), minf(128.0, view_size.y * 0.26))
	var map_scale := minf(map_limit.x / _grid.x, map_limit.y / _grid.y)
	var map_size := (Vector2(_grid) * map_scale).floor().max(Vector2.ONE)
	var minimap := Rect2(Vector2(EDGE_MARGIN + FRAME_WIDTH, view_size.y - EDGE_MARGIN - FRAME_WIDTH - map_size.y), map_size)
	var minimap_frame := minimap.grow(FRAME_WIDTH)
	var left_limit := minimap_frame.end.x + SECTION_GAP
	var panel_scale := minf(1.0, maxf(1.0, view_size.x - left_limit - EDGE_MARGIN) / PANEL_SIZE.x)
	var panel_size := (PANEL_SIZE * panel_scale).floor()
	var left := clampf(floorf((view_size.x - panel_size.x) * 0.5), left_limit, view_size.x - EDGE_MARGIN - panel_size.x)
	var panel := Rect2(Vector2(left, view_size.y - EDGE_MARGIN - panel_size.y), panel_size)
	var coords := RULES.coords_rect(minimap)
	coords.position.y = minf(minimap_frame.position.y, panel.position.y) - EDGE_MARGIN - coords.size.y
	coords.size.x = minf(coords.size.x, view_size.x - coords.position.x - EDGE_MARGIN)
	return {
		"player_panel": panel,
		"minimap": minimap,
		"minimap_frame": minimap_frame,
		"coords": coords,
		"hotbar": _panel_rect(panel, SLOTS_RECT),
		"xp": _panel_rect(panel, XP_RECT),
		"hp": _panel_rect(panel, HP_RECT),
		"mp": _panel_rect(panel, MP_RECT),
	}


func special_slot_rects(panel: Rect2) -> Array[Rect2]:
	var slots: Array[Rect2] = []
	for index in SPECIAL_SLOTS:
		slots.append(_panel_rect(panel, Rect2(SLOTS_RECT.position.x + index * 52, SLOTS_RECT.position.y, 48, SLOTS_RECT.size.y)))
	return slots


func draw_player_panel(canvas: CanvasItem, rect: Rect2, character: Dictionary, fighter: Dictionary, portrait: Texture2D) -> void:
	var scale := rect.size.x / PANEL_SIZE.x
	var font := _font_for(canvas)
	_draw_frame(canvas, rect)
	var portrait_rect := _panel_rect(rect, PORTRAIT_RECT)
	_draw_inset(canvas, portrait_rect)
	var image := portrait if portrait != null else profession_icon(str(character.get("type", "")))
	if image != null:
		if image != _framed_portrait:
			_framed_portrait = image
			_portrait_source = Rect2(Vector2.ZERO, image.get_size())
			var pixels := image.get_image()
			if pixels != null and pixels.get_used_rect().has_area():
				_portrait_source = Rect2(pixels.get_used_rect())
		var fitted := RULES.fit_size(_portrait_source.size, 66.0 * scale)
		canvas.draw_texture_rect_region(image, Rect2(portrait_rect.get_center() - fitted * 0.5, fitted), _portrait_source)
	var name_rect := _panel_rect(rect, NAME_RECT)
	_draw_centered(canvas, font, name_rect, RULES.display_name(character), maxi(9, roundi(11 * scale)), LABEL_COLOR)

	_draw_experience(canvas, font, _panel_rect(rect, XP_RECT), int(fighter.get("level", character.get("level", 1))),
		int(fighter.get("xp", character.get("xp", 0))), int(fighter.get("xp_to_next", 0)), scale)
	_draw_vital(canvas, font, _panel_rect(rect, HP_RECT), "ХП",
		float(fighter.get("hp", 0)), float(fighter.get("max_hp", 0)), Color8(163, 38, 44), scale)
	_draw_vital(canvas, font, _panel_rect(rect, MP_RECT), "МП",
		float(fighter.get("mp", 0)), float(fighter.get("max_mp", 0)), Color8(40, 87, 154), scale)

	var hovered := -1
	var slots := special_slot_rects(rect)
	for index in slots.size():
		var slot := slots[index]
		var is_hovered := slot.has_point(canvas.get_local_mouse_position())
		if is_hovered:
			hovered = index
		_draw_inset(canvas, slot, is_hovered)
		var center := slot.get_center() - Vector2(0, 3 * scale)
		var radius := 5.0 * scale
		canvas.draw_polyline(PackedVector2Array([
			center + Vector2(0, -radius), center + Vector2(radius, 0),
			center + Vector2(0, radius), center + Vector2(-radius, 0),
			center + Vector2(0, -radius),
		]), BRONZE_COLOR.darkened(0.45), 1.0)
		_draw_centered(canvas, font, Rect2(slot.end - Vector2(18, 18) * scale, Vector2(14, 14) * scale),
			str(index + 1), maxi(9, roundi(12 * scale)), LABEL_COLOR)
	var caption := "СПЕЦПРИЁМЫ" if hovered < 0 else "Спецприём %d · не назначен" % (hovered + 1)
	_draw_centered(canvas, font, _panel_rect(rect, CAPTION_RECT), caption, maxi(9, roundi(10 * scale)), EDGE_LIGHT)


func draw_minimap(canvas: CanvasItem, rect: Rect2, player_world: Vector2, corpses: Array, mobs: Array = []) -> void:
	_draw_frame(canvas, rect.grow(FRAME_WIDTH))
	super.draw_minimap(canvas, rect, player_world, corpses, mobs)
	canvas.draw_rect(rect, BRONZE_COLOR, false, 1.0)


func _coords_style() -> StyleBoxFlat:
	if _coords_box == null:
		_coords_box = _box_style(Color8(18, 20, 26, 230), BRONZE_COLOR, 1)
	return _coords_box


func _panel_rect(panel: Rect2, local_rect: Rect2) -> Rect2:
	var scale := panel.size / PANEL_SIZE
	return Rect2(panel.position + local_rect.position * scale, local_rect.size * scale)


func _draw_frame(canvas: CanvasItem, rect: Rect2) -> void:
	canvas.draw_rect(rect, Color8(6, 7, 10))
	canvas.draw_rect(rect.grow(-1), BRONZE_COLOR)
	canvas.draw_rect(rect.grow(-3), PANEL_COLOR)
	canvas.draw_rect(rect.grow(-5), INSET_EDGE, false, 1.0)
	canvas.draw_line(rect.position + Vector2(3, 2), Vector2(rect.end.x - 3, rect.position.y + 2), EDGE_LIGHT)
	canvas.draw_line(Vector2(rect.position.x + 3, rect.end.y - 2), rect.end - Vector2(3, 2), BRONZE_COLOR.darkened(0.45))
	for corner in [rect.position, Vector2(rect.end.x - 6, rect.position.y), Vector2(rect.position.x, rect.end.y - 6), rect.end - Vector2(6, 6)]:
		canvas.draw_rect(Rect2(corner + Vector2(2, 2), Vector2(2, 2)), EDGE_LIGHT)


func _draw_inset(canvas: CanvasItem, rect: Rect2, highlighted: bool = false) -> void:
	canvas.draw_rect(rect, EDGE_LIGHT if highlighted else BRONZE_COLOR.darkened(0.25))
	canvas.draw_rect(rect.grow(-1), Color8(4, 5, 8))
	canvas.draw_rect(rect.grow(-3), SLOT_COLOR.lightened(0.06) if highlighted else SLOT_COLOR)
	canvas.draw_line(rect.position + Vector2(3, 3), Vector2(rect.end.x - 3, rect.position.y + 3), INSET_EDGE)
	canvas.draw_line(Vector2(rect.position.x + 2, rect.end.y - 2), rect.end - Vector2(2, 2), INSET_EDGE)


func _draw_vital(canvas: CanvasItem, font: Font, rect: Rect2, title: String, value: float, maximum: float, color: Color, scale: float) -> void:
	_draw_bar(canvas, rect, RULES.bar_ratio(value, maximum), color)
	_draw_centered(canvas, font, rect, "%s %d / %d" % [title, int(value), int(maximum)], maxi(9, roundi(11 * scale)), BAR_TEXT_COLOR)


# Полоска опыта: уровень у левого края, полученный опыт и порог следующего уровня по центру.
func _draw_experience(canvas: CanvasItem, font: Font, rect: Rect2, level: int, xp: int, xp_to_next: int, scale: float) -> void:
	var ratio := 1.0 if xp_to_next <= 0 else RULES.bar_ratio(float(xp), float(xp_to_next))
	_draw_bar(canvas, rect, ratio, XP_COLOR)
	var font_size := maxi(9, roundi(11 * scale))
	var padding := 6.0 * scale
	var level_rect := Rect2(rect.position + Vector2(padding, 0), Vector2(rect.size.x * 0.5 - padding, rect.size.y))
	_draw_text(canvas, font, level_rect, "Уровень %d" % level, font_size, BAR_TEXT_COLOR, HORIZONTAL_ALIGNMENT_LEFT)
	_draw_centered(canvas, font, rect, experience_text(xp, xp_to_next), font_size, BAR_TEXT_COLOR)


static func experience_text(xp: int, xp_to_next: int) -> String:
	if xp_to_next <= 0:
		return "Опыт: максимальный уровень"
	return "Опыт %d \\ %d" % [xp, xp_to_next]


func _draw_bar(canvas: CanvasItem, rect: Rect2, ratio: float, color: Color) -> void:
	_draw_inset(canvas, rect)
	var inner := rect.grow(-3)
	var width := floorf(inner.size.x * clampf(ratio, 0.0, 1.0))
	if width > 0:
		canvas.draw_rect(Rect2(inner.position, Vector2(width, inner.size.y)), color)
		canvas.draw_rect(Rect2(inner.position, Vector2(width, inner.size.y * 0.5)), color.lightened(0.18))


func _draw_centered(canvas: CanvasItem, font: Font, rect: Rect2, text: String, font_size: int, color: Color) -> void:
	_draw_text(canvas, font, rect, text, font_size, color, HORIZONTAL_ALIGNMENT_CENTER)


func _draw_text(canvas: CanvasItem, font: Font, rect: Rect2, text: String, font_size: int, color: Color, alignment: HorizontalAlignment) -> void:
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var fitted_size := RULES.fit_font_size(text_width, rect.size.x - 4, font_size)
	var baseline := rect.get_center().y + (font.get_ascent(fitted_size) - font.get_descent(fitted_size)) * 0.5
	canvas.draw_string(font, Vector2(rect.position.x + 1, baseline + 1), text, alignment, rect.size.x, fitted_size, Color8(0, 0, 0))
	canvas.draw_string(font, Vector2(rect.position.x, baseline), text, alignment, rect.size.x, fitted_size, color)
