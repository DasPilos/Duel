extends RefCounted

# Отрисовка героя города: тень, кадр и плашка ника с иконкой профессии, в порядке _draw_player_character
# (scenes/city/rendering.py). Запасной маркер без кадров рисует economy_city_map.gd. Геометрия — в economy_city_player_sprite_rules.gd.

const RULES := preload("res://scripts/economy_city_player_sprite_rules.gd")
const PROFESSION_ICON := preload("res://scripts/tower_hud_view.gd")

static var _plate_style: StyleBoxFlat


static func draw_shadow(canvas: CanvasItem, feet: Vector2, zoom: float) -> void:
	canvas.draw_colored_polygon(RULES.shadow_points(feet, zoom), RULES.SHADOW_COLOR)


static func draw_frame(canvas: CanvasItem, feet: Vector2, zoom: float, frame: Texture2D) -> void:
	var frame_size := frame.get_size() * zoom
	var bottom := feet + Vector2(0.0, RULES.FRAME_FEET_OFFSET * zoom)
	canvas.draw_texture_rect(frame, Rect2(bottom - Vector2(frame_size.x * 0.5, frame_size.y), frame_size), false)


static func draw_name(canvas: CanvasItem, feet: Vector2, zoom: float, character: Dictionary) -> void:
	var font := ThemeDB.fallback_font
	var text := RULES.name_text(character)
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, RULES.NAME_FONT_SIZE)
	var plate := RULES.name_plate(text_size, feet, zoom)
	canvas.draw_style_box(_plate(), plate)
	var baseline := plate.position + Vector2(RULES.NAME_PADDING.x, RULES.NAME_PADDING.y + font.get_ascent(RULES.NAME_FONT_SIZE))
	canvas.draw_string(font, baseline, text, HORIZONTAL_ALIGNMENT_LEFT, -1, RULES.NAME_FONT_SIZE, RULES.NAME_TEXT_COLOR)
	var icon: Texture2D = PROFESSION_ICON.profession_icon(str(character.get("type", "")))
	if icon != null:
		canvas.draw_texture_rect(icon, RULES.icon_rect(plate), false)


static func _plate() -> StyleBoxFlat:
	if _plate_style == null:
		_plate_style = StyleBoxFlat.new()
		_plate_style.bg_color = RULES.NAME_FILL_COLOR
		_plate_style.border_color = RULES.NAME_BORDER_COLOR
		_plate_style.set_border_width_all(1)
		_plate_style.set_corner_radius_all(RULES.NAME_CORNER_RADIUS)
	return _plate_style
