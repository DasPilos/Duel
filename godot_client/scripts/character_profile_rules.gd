extends RefCounted

# Правила карточки персонажа из клиента Python: ui/character_profile.py, combat/character_stats.py,
# combat/world_stats.py, combat/weapon_damage.py, core/carry_weight.py и combat/progression.py.
# Сервер отдаёт класс персонажа как profession_type, поэтому он же используется как тип карточки.

const STAT_ROWS := [
	["strength", "Сила", "Урон"],
	["agility", "Ловкость", "Уворот"],
	["intuition", "Интуиция", "Крит"],
	["wisdom", "Мудрость", "Маг Урон"],
	["intellect", "Интеллект", ""],
	["endurance", "Выносливость", "Блок"],
]
const DEFAULT_STATS := {"strength": 5, "agility": 5, "intuition": 5, "wisdom": 5, "intellect": 5, "endurance": 5}
const DERIVED_COLORS := {
	"Урон": Color8(255, 255, 255),
	"Уворот": Color8(150, 220, 255),
	"Крит": Color8(255, 90, 90),
	"Маг Урон": Color8(180, 100, 240),
	"HP": Color8(110, 235, 120),
	"Блок": Color8(150, 210, 255),
}
const STAT_LABELS := {
	"strength": "Сила", "agility": "Ловкость", "intuition": "Интуиция", "endurance": "Выносливость",
	"wisdom": "Мудрость", "intellect": "Интеллект", "hp": "HP", "mp": "MP", "dodge": "% Уворот", "block": "% Блок",
}
const MIN_STAT_VALUE := 3
const STARTING_ENDURANCE_VALUE := 3
const MAX_LEVEL := 1000
const LEVEL_CAP := 30
const DEBUG_UNLIMITED_CHARACTER_IDS := [2]
const DEBUG_UNLIMITED_STAT_POINTS := 999
const HP_PER_ENDURANCE := 12
const MANA_PER_INTELLECT := 6
const BASE_MOVE_SPEED := 160.0
const MOVE_SPEED_PER_AGILITY := 5.0
const BASE_ATTACK_WINDUP := 0.5
const WINDUP_REDUCTION_PER_INTUITION := 0.02
const BASE_ATTACK_BACKSWING := 0.5
const BACKSWING_REDUCTION_PER_AGILITY := 0.02
const DODGE_PER_AGILITY := 5.0
const MAX_DODGE_CHANCE := 70.0
const CRIT_PER_INTUITION := 5.0
const MAX_CRIT_CHANCE := 95.0
const CRIT_DAMAGE_PERCENT := 150
const CARRY_PER_STRENGTH := 5
const CARRY_PER_ENDURANCE := 3
const GREEN := Color8(115, 215, 125)
const NEUTRAL := Color8(220, 210, 190)
const YELLOW := Color8(245, 205, 80)
const RED := Color8(235, 95, 85)


# Приводит профиль из сети, сохранения или боя к одному формату карточки.
static func normalize_profile(profile: Dictionary) -> Dictionary:
	var raw_stats := _dict(profile.get("stats", {}))
	var stats := {}
	for key in raw_stats:
		stats[str(key)] = _int(raw_stats[key])
	if stats.is_empty():
		stats = DEFAULT_STATS.duplicate()
	var level := _int(profile.get("level", 1), 1)
	var includes_equipment := bool(profile.get("max_hp_includes_equipment", false))
	var max_hp := maxi(_int(profile.get("max_hp", 0)), 1)
	var max_mp := maxi(_int(profile.get("max_mp", 0)), 1)
	if stats.has("endurance") and stats.has("intellect") and not includes_equipment:
		max_hp = maxi(calculate_max_hp(_int(stats["endurance"])), 1)
		max_mp = maxi(calculate_max_mana(_int(stats["intellect"])), 1)
	var character_id: Variant = profile.get("character_id", profile.get("id"))
	return {
		"id": profile.get("id", character_id),
		"character_id": character_id,
		"type": str(profile.get("type", profile.get("profession_type", "warrior"))),
		"name": str(profile.get("name", "Персонаж")),
		"level": level,
		"xp": _int(profile.get("xp", 0)),
		"hp": mini(_int(profile.get("hp", 0)), max_hp),
		"max_hp": max_hp,
		"mp": mini(_int(profile.get("mp", 0)), max_mp),
		"max_mp": max_mp,
		"stats": stats,
		"stat_points": _int(profile.get("stat_points", 0)),
		"copper": _int(profile.get("copper", 0)),
		"silver": _int(profile.get("silver", 0)),
		"gold": _int(profile.get("gold", 0)),
		"equipment": _dict(profile.get("equipment", {})).duplicate(true),
		"equipment_bonuses": _dict(profile.get("equipment_bonuses", {})).duplicate(true),
		"max_hp_includes_equipment": includes_equipment,
		"carried_weight_kg": _float(profile.get("carried_weight_kg", 0.0)),
	}


static func effective_stats(profile: Dictionary) -> Dictionary:
	var result := {}
	var raw_stats := _dict(profile.get("stats", {}))
	for key in raw_stats:
		result[str(key)] = _int(raw_stats[key])
	var bonuses := _dict(profile.get("equipment_bonuses", {}))
	for key in bonuses:
		if result.has(str(key)):
			result[str(key)] = int(result[str(key)]) + _int(bonuses[key])
	return result


# Текущие и максимальные HP: бонус экипировки добавляется, если сервер не включил его в максимум.
static func displayed_hp(profile: Dictionary) -> Vector2i:
	var base_max := _int(profile.get("max_hp", 1), 1)
	var hp_bonus := 0
	if not bool(profile.get("max_hp_includes_equipment", false)):
		hp_bonus = _int(_dict(profile.get("equipment_bonuses", {})).get("hp", 0))
	var maximum := maxi(1, base_max + hp_bonus)
	var current := _int(profile.get("hp", 0))
	if hp_bonus > 0 and current >= base_max:
		current += hp_bonus
	return Vector2i(mini(current, maximum), maximum)


static func derived_values(profile: Dictionary) -> Dictionary:
	var stats := effective_stats(profile)
	var weapon: Variant = weapon_damage_range(profile.get("equipment", {}))
	var agility := _int(stats.get("agility", 0))
	var intuition := _int(stats.get("intuition", 0))
	var values := {
		"Урон": _damage_text(_int(stats.get("strength", 0)), weapon),
		"Уворот": "%d%%" % int(clampf(DODGE_PER_AGILITY * agility, 0.0, MAX_DODGE_CHANCE)),
		"Крит": "%d%% × %d%%" % [int(clampf(CRIT_PER_INTUITION * intuition, 0.0, MAX_CRIT_CHANCE)), CRIT_DAMAGE_PERCENT],
		"Маг Урон": _damage_text(_int(stats.get("wisdom", 0)), weapon),
		"HP": displayed_hp(profile).y,
	}
	var block := _int(_dict(profile.get("equipment_bonuses", {})).get("block", 0))
	if block != 0:
		values["Блок"] = "%d%%" % block
	return values


static func derived_color(key: String) -> Color:
	return DERIVED_COLORS.get(key, Color.WHITE)


# Урон оружия (мин, макс) или null. Щит даёт урон, только если оружие его не даёт.
static func weapon_damage_range(equipment: Variant) -> Variant:
	var slots := _dict(equipment)
	var damage: Variant = _effect_damage(slots.get("weapon"))
	if not _has_damage(damage):
		var shield_damage: Variant = _effect_damage(slots.get("shield"))
		if _has_damage(shield_damage):
			damage = shield_damage
	if not _has_damage(damage):
		return null
	var low_high: Array = damage if damage is Array else [damage, damage]
	var low := _int(low_high[0])
	var high := _int(low_high[low_high.size() - 1])
	return Vector2i(mini(low, high), maxi(low, high))


static func combat_speed_values(profile: Dictionary) -> Dictionary:
	var multiplier := movement_speed_multiplier(_float(profile.get("carried_weight_kg", 0.0)), carry_capacity(profile))
	var effective := effective_stats(profile)
	var base_stats := _dict(profile.get("stats", {}))
	var attack_seconds := attack_windup(effective) + attack_backswing(effective)
	var move_speed := python_round(move_speed_for(effective, multiplier))
	var base_move_speed := python_round(move_speed_for(base_stats, multiplier))
	return {
		"attack_seconds": snappedf(attack_seconds, 0.01),
		"move_speed": move_speed,
		"move_speed_bonus": move_speed - base_move_speed,
	}


static func attack_windup(stats: Dictionary) -> float:
	return maxf(0.0, BASE_ATTACK_WINDUP - WINDUP_REDUCTION_PER_INTUITION * _int(stats.get("intuition", 0)))


static func attack_backswing(stats: Dictionary) -> float:
	return maxf(0.0, BASE_ATTACK_BACKSWING - BACKSWING_REDUCTION_PER_AGILITY * _int(stats.get("agility", 0)))


static func move_speed_for(stats: Dictionary, multiplier: float) -> float:
	var speed := BASE_MOVE_SPEED + MOVE_SPEED_PER_AGILITY * _int(stats.get("agility", 0))
	return speed * multiplier


static func carry_capacity(profile: Dictionary) -> int:
	var stats := _dict(profile.get("stats", {}))
	var bonuses := _dict(profile.get("equipment_bonuses", {}))
	var strength := _int(stats.get("strength", 0)) + _int(bonuses.get("strength", 0))
	var endurance := _int(stats.get("endurance", 0)) + _int(bonuses.get("endurance", 0))
	return maxi(0, strength) * CARRY_PER_STRENGTH + maxi(0, endurance) * CARRY_PER_ENDURANCE


static func load_ratio(carried_kg: float, capacity_kg: float) -> float:
	var capacity := maxf(0.0, capacity_kg)
	if capacity == 0.0:
		return 0.0
	return maxf(0.0, carried_kg) / capacity


static func load_color(carried_kg: float, capacity_kg: float) -> Color:
	var ratio := load_ratio(carried_kg, capacity_kg)
	if ratio <= 0.30:
		return GREEN
	if ratio > 0.80:
		return RED
	if ratio > 0.60:
		return YELLOW
	return NEUTRAL


static func movement_speed_multiplier(carried_kg: float, capacity_kg: float) -> float:
	var ratio := load_ratio(carried_kg, capacity_kg)
	if ratio > 0.80:
		return 0.30
	if ratio > 0.60:
		return 0.50
	if ratio > 0.30:
		return 0.70
	return 1.0


static func character_movement_multiplier(profile: Dictionary) -> float:
	return movement_speed_multiplier(_float(profile.get("carried_weight_kg", 0.0)), carry_capacity(profile))


static func xp_to_next(level: int) -> int:
	if level >= LEVEL_CAP:
		return 0
	if level <= 20:
		return floori(140 + 45 * level + 5 * level * (level - 1))
	return xp_to_next(20) + 90 * (level - 20)


static func is_debug_unlimited(profile: Dictionary) -> bool:
	var character_id: Variant = profile.get("character_id", profile.get("id"))
	if character_id == null:
		return false
	return DEBUG_UNLIMITED_CHARACTER_IDS.has(int(character_id))


static func calculate_max_hp(endurance: int) -> int:
	return HP_PER_ENDURANCE * endurance


static func calculate_max_mana(intellect: int) -> int:
	return MANA_PER_INTELLECT * intellect


static func minimum_endurance(level: int) -> int:
	return STARTING_ENDURANCE_VALUE + maxi(0, level - 1)


# Новое состояние после +1/−1 к характеристике или пустой словарь, если изменение запрещено.
static func adjust_stat(profile: Dictionary, stat_name: String, delta: int) -> Dictionary:
	var stats := _dict(profile.get("stats", {}))
	if not stats.has(stat_name) or (delta != 1 and delta != -1):
		return {}
	if stat_name == "endurance" and delta > 0:
		return {}
	var unlimited := is_debug_unlimited(profile)
	var level := _int(profile.get("level", 1), 1)
	var stat_points := _int(profile.get("stat_points", 0))
	if delta > 0 and stat_points <= 0 and not unlimited:
		return {}
	var minimum_value := 0
	if not unlimited:
		minimum_value = minimum_endurance(level) if stat_name == "endurance" else MIN_STAT_VALUE
	if delta < 0 and _int(stats[stat_name]) <= minimum_value:
		return {}
	var updated_stats: Dictionary = stats.duplicate(true)
	updated_stats[stat_name] = _int(updated_stats[stat_name]) + delta
	var updated_max_hp := calculate_max_hp(_int(updated_stats.get("endurance", 0)))
	return {
		"stats": updated_stats,
		"stat_points": DEBUG_UNLIMITED_STAT_POINTS if unlimited else stat_points - delta,
		"hp": mini(_int(profile.get("hp", 0)), updated_max_hp),
		"max_hp": updated_max_hp,
	}


# Отладочное изменение уровня доступно только тестовым персонажам.
static func adjust_level(profile: Dictionary, delta: int) -> Dictionary:
	if not is_debug_unlimited(profile):
		return {}
	var level := _int(profile.get("level", 1), 1)
	var new_level := clampi(level + delta, 1, MAX_LEVEL)
	if new_level == level:
		return {}
	var stats: Dictionary = _dict(profile.get("stats", {})).duplicate(true)
	stats["endurance"] = maxi(_int(stats.get("endurance", 0)), minimum_endurance(new_level))
	var max_hp := calculate_max_hp(_int(stats["endurance"]))
	return {"level": new_level, "stats": stats, "max_hp": max_hp, "hp": max_hp}


# Строки подсказки предмета: [[текст, цвет], ...].
static func equipment_tooltip_lines(item: Dictionary) -> Array:
	var lines: Array = [[str(item.get("name", "Предмет")), Color8(255, 224, 150)]]
	var description := str(item.get("description", ""))
	if not description.is_empty():
		lines.append([description, Color8(225, 220, 207)])
	for stat in _dict(item.get("bonuses", {})):
		var value := _int(_dict(item.get("bonuses", {}))[stat])
		var sign_text := "+" if value > 0 else ""
		lines.append(["Бонус: %s%d %s" % [sign_text, value, STAT_LABELS.get(stat, stat)], Color8(140, 230, 150)])
	var damage: Variant = _dict(item.get("effects", {})).get("damage")
	if _has_damage(damage):
		var damage_list: Array = damage if damage is Array else [damage, damage]
		lines.append(["Урон: %d–%d" % [_int(damage_list[0]), _int(damage_list[damage_list.size() - 1])], Color8(255, 220, 120)])
	lines.append(["Вес: %s кг" % str(_float(item.get("weight", 0.0))), Color8(175, 180, 185)])
	return lines


static func _damage_text(base: int, weapon: Variant) -> String:
	var value := maxi(1, base)
	if weapon == null:
		return str(value)
	var weapon_range: Vector2i = weapon
	if weapon_range.x == weapon_range.y:
		return str(value + weapon_range.x)
	return "%d-%d" % [value + weapon_range.x, value + weapon_range.y]


static func _effect_damage(item: Variant) -> Variant:
	if not item is Dictionary:
		return null
	return _dict(item.get("effects", {})).get("damage")


static func _has_damage(damage: Variant) -> bool:
	if damage == null:
		return false
	if damage is Array:
		return not damage.is_empty() and not (_int(damage[0]) == 0 and _int(damage[damage.size() - 1]) == 0)
	if damage is int or damage is float:
		return damage != 0
	return false


# Банковское округление Python: 150.5 → 150, 143.5 → 144.
static func python_round(value: float) -> int:
	var floored := floorf(value)
	var fraction := value - floored
	if fraction > 0.5 or (fraction == 0.5 and fmod(floored, 2.0) != 0.0):
		return int(floored) + 1
	return int(floored)


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _int(value: Variant, fallback: int = 0) -> int:
	if value == null:
		return fallback
	return int(value)


static func _float(value: Variant) -> float:
	if value == null:
		return 0.0
	return float(value)
