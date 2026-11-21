extends RefCounted

# Геометрия героя на карте города, порт _draw_player_character из scenes/city/rendering.py (1560-1592):
#   тень — эллипс 32x14 с левым верхним углом на (-16, -5) от ног, как shadow_surf в Python;
#   кадр — midbottom на 2 px ниже ног (psy + 2), его рисует economy_city_player_sprite.gd;
#   плашка ника — низ текста на 42 px выше ног, затем расширение 4 px по бокам и 2 px сверху и снизу (inflate(8, 4));
#   иконка профессии 32 px слева от плашки с зазором 4 px и центром по её высоте (ui/profession_icons.py).
# Тень, кадр и подъём плашки умножаются на масштаб карты; шрифт и иконка остаются в пикселях экрана.

const SHAPE_RULES := preload("res://scripts/economy_citizen_sprite_rules.gd")
const HUD_RULES := preload("res://scripts/tower_hud_rules.gd")
const SHADOW_OFFSET := Vector2(-16.0, -5.0)
const SHADOW_SIZE := Vector2(32.0, 14.0)
const SHADOW_COLOR := Color(10.0 / 255.0, 12.0 / 255.0, 16.0 / 255.0, 170.0 / 255.0)
const FRAME_FEET_OFFSET := 2.0
const NAME_BOTTOM_OFFSET := 42.0
const NAME_FONT_SIZE := 11
const NAME_PADDING := Vector2(4.0, 2.0)
const NAME_TEXT_COLOR := Color8(240, 240, 240)
const NAME_FILL_COLOR := Color8(15, 18, 24)
const NAME_BORDER_COLOR := Color8(220, 180, 60)
const NAME_CORNER_RADIUS := 3
const ICON_SIZE := 32.0
const ICON_GAP := 4.0


static func name_text(character: Dictionary) -> String:
	return HUD_RULES.display_name(character)


static func shadow_points(feet: Vector2, zoom: float) -> PackedVector2Array:
	return SHAPE_RULES.ellipse_points(Rect2(feet + SHADOW_OFFSET * zoom, SHADOW_SIZE * zoom))


static func name_plate(text_size: Vector2, feet: Vector2, zoom: float) -> Rect2:
	var text_top := feet.y - NAME_BOTTOM_OFFSET * zoom - text_size.y
	var text_rect := Rect2(feet.x - text_size.x * 0.5, text_top, text_size.x, text_size.y)
	return text_rect.grow_individual(NAME_PADDING.x, NAME_PADDING.y, NAME_PADDING.x, NAME_PADDING.y)


static func icon_rect(plate: Rect2) -> Rect2:
	return Rect2(plate.position.x - ICON_GAP - ICON_SIZE, plate.get_center().y - ICON_SIZE * 0.5, ICON_SIZE, ICON_SIZE)
