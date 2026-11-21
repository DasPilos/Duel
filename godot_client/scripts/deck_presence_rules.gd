extends RefCounted

# Другие игроки на карте мира Deck: фильтры, границы экрана, поиск под курсором и поля карточки.
# Порт deck/ui/player_presence.py: active_player_entities, фильтр draw_afk_players, player_at и состав карточки из
# draw_player_hover_card (normalize_character_profile). Здесь нет рисования: его делает deck_presence_view.gd.

const MAP_RULES := preload("res://scripts/deck_world_map_rules.gd")
# draw_active_players: -80 <= sx <= WIDTH + 80 и -100 <= sy <= HEIGHT + 20; WIDTH и HEIGHT — размер окна просмотра Godot.
const SCREEN_MARGIN_LEFT := 80.0
const SCREEN_MARGIN_RIGHT := 80.0
const SCREEN_MARGIN_TOP := 100.0
const SCREEN_MARGIN_BOTTOM := 20.0
# player_at: pygame.Rect(sx - 22, sy - 58, 44, 62), правая и нижняя границы не входят.
const HIT_LEFT := 22.0
const HIT_RIGHT := 22.0
const HIT_ABOVE := 58.0
const HIT_BELOW := 4.0
const DEFAULT_NAME := "Игрок"
const DEFAULT_TYPE := "warrior"
const DEFAULT_DIRECTION := "s"
# Поля записи игрока, которые читает карточка; алиасы current_hp и hp_max берутся так же, как в Python.
const CARD_FIELDS := [
	"name", "type", "profession_type", "level", "xp", "hp", "max_hp", "mp", "max_mp",
	"current_hp", "hp_max", "current_mp", "mp_max", "stats", "stat_points", "coins",
	"equipment", "equipment_bonuses", "max_hp_includes_equipment",
]


static func is_afk(occupant: Dictionary) -> bool:
	return _truthy(occupant.get("afk"))


static func has_position(occupant: Dictionary) -> bool:
	return occupant.get("position_x") != null and occupant.get("position_y") != null


static func is_own(occupant: Dictionary, own_id: String) -> bool:
	return id_text(occupant.get("character_id")) == own_id


# Идентификатор как строка: число 42 и 42.0 из JSON дают одно и то же «42».
static func id_text(value: Variant) -> String:
	if value is float or value is int:
		return str(int(value))
	return str(value)


# Активные игроки в точке: не AFK, та же локация, есть позиция и это не сам персонаж.
static func active_occupants(occupants: Array, location: String, own_id: String) -> Array:
	var result: Array = []
	for occupant in occupants:
		if occupant is Dictionary and not is_afk(occupant) and occupant.get("location") == location \
				and has_position(occupant) and not is_own(occupant, own_id):
			result.append(occupant)
	return result


# AFK-игроки в точке. Свой персонаж здесь не исключается, как в draw_afk_players.
static func afk_occupants(occupants: Array, location: String) -> Array:
	var result: Array = []
	for occupant in occupants:
		if occupant is Dictionary and is_afk(occupant) and occupant.get("location") == location and has_position(occupant):
			result.append(occupant)
	return result


static func on_screen(screen: Vector2, viewport: Vector2) -> bool:
	return screen.x >= -SCREEN_MARGIN_LEFT and screen.x <= viewport.x + SCREEN_MARGIN_RIGHT \
		and screen.y >= -SCREEN_MARGIN_TOP and screen.y <= viewport.y + SCREEN_MARGIN_BOTTOM


static func hit_rect(screen: Vector2) -> Rect2:
	return Rect2(screen.x - HIT_LEFT, screen.y - HIT_ABOVE, HIT_LEFT + HIT_RIGHT, HIT_ABOVE + HIT_BELOW)


static func contains(rect: Rect2, point: Vector2) -> bool:
	return point.x >= rect.position.x and point.x < rect.end.x and point.y >= rect.position.y and point.y < rect.end.y


# entries: [{"occupant": Dictionary, "screen": Vector2}] в порядке списка; побеждает первый попавший, как player_at.
static func player_at(entries: Array, point: Vector2) -> Dictionary:
	for entry in entries:
		if contains(hit_rect(entry["screen"]), point):
			return entry["occupant"]
	return {}


# Мировая точка (position_x, position_y) в координаты окна карты. Окно и тайл те же, что у renderer:
# origin = window_origin(center, view_size), cell = tile_px.
static func map_point(world: Vector2, center: Vector2i, view_size: int, tile_px: float) -> Vector2:
	var tile := maxf(1.0, tile_px)
	var origin := Vector2(MAP_RULES.window_origin(center, view_size))
	return (world / tile - origin) * tile


static func card_profile(occupant: Dictionary) -> Dictionary:
	var profile := {}
	for key in CARD_FIELDS:
		if occupant.has(key):
			profile[key] = occupant[key]
	var character_id: Variant = occupant.get("character_id", occupant.get("id"))
	profile["id"] = character_id
	profile["character_id"] = character_id
	return profile


static func display_name(occupant: Dictionary) -> String:
	return str(occupant.get("name", DEFAULT_NAME))


static func afk_label(occupant: Dictionary) -> String:
	return "%s (АФК)" % display_name(occupant)


static func class_type(occupant: Dictionary) -> String:
	return str(occupant.get("type", DEFAULT_TYPE))


# Пустое или отсутствующее направление даёт «s», как `or "s"` в Python.
static func direction_of(occupant: Dictionary) -> String:
	var direction: Variant = occupant.get("position_direction")
	return str(direction) if _truthy(direction) else DEFAULT_DIRECTION


# Истинность как в Python: None, 0, пустые строка, список и словарь — ложь.
static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return value
	if value is String:
		return not (value as String).is_empty()
	if value is int or value is float:
		return value != 0
	if value is Array:
		return not (value as Array).is_empty()
	if value is Dictionary:
		return not (value as Dictionary).is_empty()
	return true
