extends RefCounted

const LIMITS := {
	"move_speed": [0.0, 400.0],
	"windup": [0.05, 5.0],
	"backswing": [0.05, 5.0],
	"aggro_tiles": [0.0, 30.0],
	"respawn_seconds": [0.0, 86399.0],
	"reward_copper": [0.0, 1000000.0],
	"reward_xp": [0.0, 1000000.0],
}
const INT_FIELDS := ["respawn_seconds", "reward_copper", "reward_xp"]
const FRONT_LINE_RESOURCE_FIELDS := [
	{"key": "max_hp", "label": "ХП", "unit": "", "step": 10},
	{"key": "max_mp", "label": "МП", "unit": "", "step": 5},
	{"key": "attack_range", "label": "Дальность атаки", "unit": "ед.", "step": 10},
	{"key": "area_radius", "label": "Радиус урона", "unit": "ед.", "step": 10},
]
# Дальность атаки моба Front Line, единиц; 50 ед. = 1 тайл (16 px). Совпадает с переводом сервера (front_line/server/combat.py).
const ATTACK_RANGE_MAX := 1500
const OPTIONAL_RESOURCE_KEYS := ["attack_range", "area_radius"]
# Характер боя моба: воин (ближний бой), лучник (стрела), маг (сфера с уроном по области).
const ATTACK_STYLES := [["warrior", "Воин"], ["archer", "Лучник"], ["mage", "Маг"]]
const ATTACK_STYLE_IDS := ["warrior", "archer", "mage"]
const AREA_RADIUS_MAX := 500
const PATROL_SIZE := 18
const PATROL_ANCHOR := 9
const STATES := ["aggressive", "neutral", "friendly"]
const STATE_LABELS := {
	"aggressive": "Агрессивный",
	"neutral": "Нейтральный",
	"friendly": "Дружественный",
}
const STATE_HINTS := {
	"aggressive": "Нападает на игрока, подошедшего на расстояние агрессии.",
	"neutral": "Не трогает игрока, пока тот не нападёт на него или на охраняемый им объект.",
	"friendly": "Не нападает. Помогает в бою, если бой с игроком начался в зоне патруля.",
}
const EQUIPMENT_SLOTS := [
	"head", "ears", "neck", "back", "body", "hands",
	"belt", "legs", "feet", "weapon", "shield", "ring", "ring_2",
]

# Правила Tower и Economy: core/mob_modes.py
const DEFAULT_RULES := {
	"stat_min": 3,
	"level_min": 1,
	"level_cap": 30,
	"endurance_first": 4,
	"free_points_first": 3,
	"free_points_per_level": 3,
	"stats": [
		["strength", "Сила"],
		["agility", "Ловкость"],
		["intuition", "Интуиция"],
		["wisdom", "Мудрость"],
		["intellect", "Интеллект"],
		["endurance", "Выносливость"],
	],
}
# Правила Deck: deck/editor/mob_modes.py
const DECK_RULES := {
	"stat_min": 2,
	"level_min": 1,
	"level_cap": 10,
	"endurance_first": 2,
	"free_points_first": 6,
	"free_points_per_level": 4,
	"stats": [
		["strength", "Сила"],
		["agility", "Ловкость"],
		["intuition", "Интуиция"],
		["wisdom", "Мудрость"],
		["intellect", "Интеллект"],
		["harmony", "Гармония"],
		["endurance", "Выносливость"],
	],
}
const FRONT_LINE_RULES := {
	"unlimited": true,
	"stat_min": 0,
	"level_min": 1,
	"level_cap": 9223372036854775807,
	"endurance_first": 0,
	"free_points_first": 0,
	"free_points_per_level": 0,
	"stats": [
		["strength", "Сила"],
		["agility", "Ловкость"],
		["intuition", "Интуиция"],
		["wisdom", "Мудрость"],
		["intellect", "Интеллект"],
		["endurance", "Выносливость"],
	],
}


static func rules_for_mode(mode: String) -> Dictionary:
	if mode == "deck":
		return DECK_RULES
	if mode == "front_line":
		return FRONT_LINE_RULES
	return DEFAULT_RULES


static func allocatable_stats(rules: Dictionary) -> Array:
	var result: Array = []
	for entry in rules["stats"]:
		if str(entry[0]) != "endurance":
			result.append(str(entry[0]))
	return result


static func stat_label(rules: Dictionary, stat: String) -> String:
	for entry in rules["stats"]:
		if str(entry[0]) == stat:
			return str(entry[1])
	return stat


static func endurance_for_level(rules: Dictionary, level: int) -> int:
	if bool(rules.get("unlimited", false)):
		return 0
	return int(rules["endurance_first"]) + level - 1


static func total_free_points(rules: Dictionary, level: int) -> int:
	if bool(rules.get("unlimited", false)):
		return 0
	return int(rules["free_points_first"]) + int(rules["free_points_per_level"]) * (level - 1)


static func spent_points(rules: Dictionary, stats: Dictionary) -> int:
	var spent := 0
	for stat in allocatable_stats(rules):
		spent += int(stats.get(stat, rules["stat_min"])) - int(rules["stat_min"])
	return spent


static func free_points(rules: Dictionary, level: int, stats: Dictionary) -> int:
	if bool(rules.get("unlimited", false)):
		return 0
	return total_free_points(rules, level) - spent_points(rules, stats)


static func item_slot(slot: String) -> String:
	return "ring" if slot == "ring_2" else slot


static func item_requirements(item: Dictionary) -> Dictionary:
	var effects: Variant = item.get("effects")
	if not effects is Dictionary:
		return {}
	var requirements: Variant = effects.get("requirements")
	return (requirements as Dictionary).duplicate() if requirements is Dictionary else {}


static func item_fits(item: Dictionary, stats: Dictionary, level: int) -> bool:
	var requirements := item_requirements(item)
	var required_level := int(requirements.get("level", 1))
	requirements.erase("level")
	if required_level > level:
		return false
	for stat in requirements:
		if int(stats.get(str(stat), 0)) < int(requirements[stat]):
			return false
	return true


static func requirement_text(item: Dictionary, rules: Dictionary) -> String:
	var requirements := item_requirements(item)
	var required_level := int(requirements.get("level", 1))
	requirements.erase("level")
	var parts: Array[String] = []
	for stat in requirements:
		parts.append("%s %d" % [stat_label(rules, str(stat)), int(requirements[stat])])
	parts.append("ур. %d" % required_level)
	return ", ".join(parts)


# Снимает известные предметы, которые не подходят виду; предметы вне списка остаются для проверки сервером.
static func drop_unfit_equipment(
	equipment: Dictionary,
	items: Array,
	stats: Dictionary,
	level: int,
) -> Dictionary:
	var known := {}
	for item in items:
		if item is Dictionary and item.has("id"):
			known[int(item["id"])] = item
	var result := {}
	for slot in equipment:
		var item_id: Variant = equipment[slot]
		var item: Variant = known.get(int(item_id)) if item_id != null else null
		result[slot] = null if item != null and not item_fits(item, stats, level) else item_id
	return result


static func format_hms(seconds: float) -> String:
	var total := maxi(0, roundi(seconds))
	return "%02d:%02d:%02d" % [floori(total / 3600.0), floori(total / 60.0) % 60, total % 60]


# Секунды из «ЧЧ:ММ:СС», «ММ:СС» или обычного числа; null, если текст не разобран.
static func parse_seconds(text: String) -> Variant:
	var parts := text.strip_edges().split(":")
	if parts.size() > 3 or parts.is_empty():
		return null
	var total := 0.0
	for part in parts:
		if not part.strip_edges().is_valid_float():
			return null
		total = total * 60.0 + part.strip_edges().to_float()
	return total


static func format_field(key: String, value: float) -> String:
	match key:
		"respawn_seconds":
			return format_hms(value)
		"windup", "backswing":
			return "%.2f" % value
		"aggro_tiles":
			return "%.1f" % value
	return "%d" % roundi(value)


static func parse_field(key: String, text: String) -> Variant:
	var cleaned := text.strip_edges().replace(",", ".")
	if key == "respawn_seconds":
		return parse_seconds(cleaned)
	return cleaned.to_float() if cleaned.is_valid_float() else null


static func clamp_field(key: String, value: float) -> float:
	var limits: Array = LIMITS[key]
	var clamped := clampf(value, float(limits[0]), float(limits[1]))
	return roundf(clamped) if key in INT_FIELDS else snappedf(clamped, 0.01)


static func field_output(key: String, value: float) -> Variant:
	return roundi(value) if key in INT_FIELDS else snappedf(value, 0.01)


# Проверка перед отправкой: те же правила, что на сервере (core/mob_modes.py::validate_settings).
static func validate_settings(rules: Dictionary, settings: Dictionary) -> String:
	var level := int(settings.get("level", 0))
	if level < int(rules["level_min"]) or (
		not bool(rules.get("unlimited", false)) and level > int(rules["level_cap"])
	):
		return "Уровень: от %d до %d" % [int(rules["level_min"]), int(rules["level_cap"])]
	if not str(settings.get("state", "")) in STATES:
		return "Выберите состояние моба."
	var stats: Variant = settings.get("stats")
	if not stats is Dictionary:
		return "Характеристики моба не заданы."
	for entry in rules["stats"]:
		var stat := str(entry[0])
		if not stats.has(stat):
			return "Характеристика «%s» не задана." % str(entry[1])
		var value := int(stats[stat])
		if bool(rules.get("unlimited", false)):
			if value < int(rules["stat_min"]):
				return "Характеристика «%s» не ниже %d" % [
					str(entry[1]), int(rules["stat_min"]),
				]
		elif stat == "endurance":
			if value != endurance_for_level(rules, level):
				return "Выносливость на уровне %d равна %d" % [level, endurance_for_level(rules, level)]
		elif value < int(rules["stat_min"]):
			return "Характеристика «%s» не ниже %d" % [str(entry[1]), int(rules["stat_min"])]
	var spent := spent_points(rules, stats)
	var total := total_free_points(rules, level)
	if not bool(rules.get("unlimited", false)) and spent > total:
		return "Вложено %d очков характеристик, на уровне %d доступно %d" % [spent, level, total]
	if bool(rules.get("unlimited", false)):
		for entry in FRONT_LINE_RESOURCE_FIELDS:
			var resource_key := str(entry["key"])
			if not settings.has(resource_key):
				if resource_key in OPTIONAL_RESOURCE_KEYS:
					continue  # сервер подставит значение по умолчанию
				return "Параметр «%s» не задан." % str(entry["label"])
			var resource_value: Variant = settings[resource_key]
			var minimum := 1 if resource_key == "max_hp" else 0
			if not resource_value is int and not resource_value is float:
				return "Параметр «%s» должен быть целым числом не меньше %d." % [
					str(entry["label"]), minimum,
				]
			var numeric_resource := float(resource_value)
			if not is_finite(numeric_resource) or numeric_resource != float(int(numeric_resource)) \
				or int(numeric_resource) < minimum:
				return "Параметр «%s» должен быть целым числом не меньше %d." % [
					str(entry["label"]), minimum,
				]
	if int(settings.get("attack_range", 0)) > ATTACK_RANGE_MAX:
		return "Дальность атаки: не больше %d ед. (50 ед. = 1 тайл)." % ATTACK_RANGE_MAX
	if not str(settings.get("attack_style", "warrior")) in ATTACK_STYLE_IDS:
		return "Характер боя: воин, лучник или маг."
	if int(settings.get("area_radius", 0)) > AREA_RADIUS_MAX:
		return "Радиус урона: не больше %d ед. (50 ед. = 1 тайл)." % AREA_RADIUS_MAX
	if int(settings.get("damage_min", 0)) > int(settings.get("damage_max", 0)):
		return "Урон: минимум не больше максимума."
	var patrol: Variant = settings.get("patrol")
	if not patrol is Array:
		return "Патруль должен быть списком клеток."
	for cell in patrol:
		var dx := int(cell[0])
		var dy := int(cell[1])
		if dx < -PATROL_ANCHOR or dy < -PATROL_ANCHOR \
			or dx >= PATROL_SIZE - PATROL_ANCHOR or dy >= PATROL_SIZE - PATROL_ANCHOR:
			return "Клетка патруля (%d, %d) вне поля %d×%d" % [dx, dy, PATROL_SIZE, PATROL_SIZE]
	return ""
