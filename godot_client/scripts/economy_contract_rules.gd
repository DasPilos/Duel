extends RefCounted
# Контракт ответов Экономики, которые читает economy_world.gd. Имена полей взяты из серверного кода
# (пути относительно economy/server/, номера строк проверены по текущему файлу):
#
# Горожане в пути: GET /api/world/traveling-citizens?character_id=N → {"citizens": [...]} (api.py:113-119).
#   Элемент — city_population.py:512-524: id:512 faction:513 name:514 job_building:515
#   travel_direction:516 (outbound|returning) travel_total_seconds:517 travel_seconds_left:518 eta_seconds:519
#   position_x:520 position_y:521 position_direction:522 route_name:523 movement_text:524.
#   Собирает CityPopulation.get_traveling_citizens (city_population.py:469).
#
# Повозки мира: GET /api/world/traveling-convoys?character_id=N → {"convoys": [...]} (api.py:121-127).
#   Элемент — transport.py:1152-1178: id:1152 cart_id:1152 cart_grade:1153 cart_name:1154
#   destination_name:1160 route_name:1160 driver_name:1162 pinned:1167 phase:1169 status:1169
#   cargo_percent:1175 position_x:1176 position_y:1176 position_direction:1177 started_at:1178.
#   Собирает TransportService.get_world_convoys (transport.py:1025).
#
# Население: GET /api/castle/{id}/population → {"population": {...}} (api.py:111).
#   Ключи — city_population.py:1147-1186: castle_name:1147 castle_level:1148 city_level:1149
#   population:1157 population_capacity:1158 citizens:1159 city_resource_storage:1165 food_status:1167
#   treasury_text:1171 worksites:1185 upgrades:1186. Житель — city_population.py:1071-1090
#   (id, name, satiety, work_status, job_building, job_slot, travel_seconds_left, travel_direction).
#   Место работы — city_population.py:1044-1047 (building, name, free_slots, capacity, travel_seconds).
#
# Здание: GET /api/buildings/{building}/{id} → {"building": {...}} (api.py:100).
#   Ключи — production_buildings.py:1008-1059: building:1008 level:1011 max_workers:1012 workers:1034
#   next_harvest_seconds:1039 storage:1040 worker_slots:1050 upgrade:1059.
#   Слот — production_buildings.py:703-709: slot_index, resource, occupied, worker_name, is_player.
#
# Карта города: GET /api/city/structures → {"city": {"objects": [...], "walls": [...]}} (api.py:21, 64-66).
#   Данные — server/structures.py CITY_OBJECTS и CITY_WALLS. Клиент хранит копию в economy_city_layout_rules.gd.

const TRAVELER_FIELDS := ["id", "name", "job_building", "travel_direction", "travel_seconds_left", "eta_seconds"]
const TRAVELER_KINDS := {
	"id": "number", "name": "string", "job_building": "string",
	"travel_direction": "string", "travel_seconds_left": "number", "eta_seconds": "number",
}
const CONVOY_FIELDS := ["id", "cart_id", "cart_name", "destination_name", "driver_name", "status", "pinned"]
const CONVOY_KINDS := {
	"id": "number", "cart_id": "string", "cart_name": "string", "destination_name": "string",
	"driver_name": "string", "status": "string", "pinned": "bool",
}
const POPULATION_FIELDS := [
	"castle_name", "castle_level", "city_level", "population", "population_capacity", "citizens",
	"city_resource_storage", "food_status", "treasury_text", "worksites", "upgrades",
]
const POPULATION_KINDS := {
	"castle_name": "string", "castle_level": "number", "city_level": "number",
	"population": "number", "population_capacity": "number", "citizens": "array",
	"city_resource_storage": "dict", "food_status": "string", "treasury_text": "string",
	"worksites": "array", "upgrades": "array",
}
const CITIZEN_FIELDS := ["id", "name", "satiety", "work_status", "job_building", "travel_seconds_left", "travel_direction"]
const WORKSITE_FIELDS := ["building", "name", "free_slots", "capacity", "travel_seconds"]
const BUILDING_FIELDS := ["building", "level", "max_workers", "workers", "next_harvest_seconds", "storage", "worker_slots", "upgrade"]
const BUILDING_KINDS := {
	"building": "string", "level": "number", "max_workers": "number", "workers": "number",
	"storage": "dict", "worker_slots": "array", "upgrade": "dict",
}
const WORKER_SLOT_FIELDS := ["slot_index", "resource", "occupied", "worker_name", "is_player"]


# Список объектов под ключом key; при неверной форме ответа — пустой массив.
static func items(payload: Variant, key: String) -> Array:
	if not payload is Dictionary or not payload.get(key, null) is Array:
		return []
	var result: Array = []
	for item in payload[key]:
		if item is Dictionary:
			result.append(item)
	return result


static func missing_fields(item: Variant, fields: Array) -> Array:
	if not item is Dictionary:
		return fields.duplicate()
	var missing: Array = []
	for field in fields:
		if not item.has(field):
			missing.append(field)
	return missing


# Поля, у которых тип не совпадает с контрактом. JSON отдаёт все числа как float, поэтому "number" — любое число.
static func kind_mismatches(item: Dictionary, kinds: Dictionary) -> Array:
	var mismatches: Array = []
	for field in kinds:
		if not item.has(field) or not _kind_matches(item[field], str(kinds[field])):
			mismatches.append(field)
	return mismatches


static func _kind_matches(value: Variant, kind: String) -> bool:
	match kind:
		"number":
			return value is int or value is float
		"string":
			return value is String
		"bool":
			return value is bool
		"array":
			return value is Array
		"dict":
			return value is Dictionary
	return false
