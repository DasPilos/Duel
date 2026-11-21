extends RefCounted

# Правила входа в мир Tower и чекпоинтов: порт client/app_flow.py (scene_for_saved_character, checkpoint_for_scene,
# opens_map_first) и выходов из таверны (main.py). Сервер принимает zone как строку, поэтому PUT /api/characters/{id}
# работает без изменений сервера. Локация чата и присутствия совпадает с зоной. Городских ворот в Tower нет: город
# относится к Economy, поэтому «Выход на улицу» открывает карту мира напрямую.

const ZONE_TAVERN := "tavern"
const ZONE_ROOM := "character_room"
const ZONE_MAP := "world_map"
const BARTENDER_UNAVAILABLE := "Напитки пока недоступны"


static func is_map_world(world: Dictionary) -> bool:
	var code := str(world.get("code", ""))
	return str(world.get("mode", "")) == "front_line" \
		or code.begins_with("map") or code.begins_with("deck_map")


static func is_coordinate(value: Variant) -> bool:
	return typeof(value) == TYPE_FLOAT or typeof(value) == TYPE_INT


static func has_position(character: Dictionary) -> bool:
	return is_coordinate(character.get("position_x")) and is_coordinate(character.get("position_y"))


# Мир Front Line и карта из редактора открываются сразу: сервер размещает игрока у точки возрождения.
# Обычный мир: комната и карта — по зоне. Карта без позиции и любая другая зона начинают в таверне.
static func entry_zone(world: Dictionary, character: Dictionary) -> String:
	if is_map_world(world):
		return ZONE_MAP
	var zone := str(character.get("zone", ""))
	if zone == ZONE_ROOM:
		return ZONE_ROOM
	if zone == ZONE_MAP and has_position(character):
		return ZONE_MAP
	return ZONE_TAVERN


# Позиция уходит только для карты и только когда клиент её знает. Для таверны и комнаты сохранённая позиция не меняется.
static func checkpoint_body(zone: String, position: Vector2, direction: String, position_known: bool) -> Dictionary:
	var body := {"zone": zone}
	if zone == ZONE_MAP and position_known:
		body["position_x"] = position.x
		body["position_y"] = position.y
		body["position_direction"] = direction
	return body
