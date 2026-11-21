extends RefCounted

# Порт правил карточки персонажа Deck: deck/combat/character_stats.py, mechanics.py, progression.py,
# deck/ui/character_profile.py, deck/ui/mage_card.py, deck/ui/class_identity.py и подсказки предмета
# из deck/ui/character_card.py. Числа и строки совпадают с Python-клиентом (проверено эталоном).

const STARTING_ENDURANCE_VALUE := 2
const MIN_STAT_VALUE := 2
const ENDURANCE_HP_BONUS := 10
const BASE_HP := 70
const MANA_PER_INTELLECT := 5
const DEBUG_UNLIMITED_CHARACTER_IDS := [2]
const DEBUG_UNLIMITED_STAT_POINTS := 999
const LEVEL_CAP := 10
const XP_TO_LEVEL := {1: 20, 2: 40, 3: 120, 4: 200, 5: 350, 6: 500, 7: 750, 8: 900, 9: 1100}
const BASE_CRITICAL_CHANCE := 5.0
const BASE_CRITICAL_MULTIPLIER := 1.5
const CRITICAL_DAMAGE_PER_INTUITION := 0.05
const DODGE_CHANCE_PER_AGILITY := 2.0
const DODGE_CAP := 70.0
const CHANCE_CAP := 95.0
const DEFAULT_STATS := {
	"strength": 2,
	"agility": 2,
	"intuition": 2,
	"wisdom": 2,
	"intellect": 2,
	"harmony": 2,
	"endurance": 2,
}
const STAT_ROWS := [
	["strength", "Сила", "Урон"],
	["agility", "Ловкость", "Уворот"],
	["intuition", "Интуиция", "Крит"],
	["wisdom", "Мудрость", "Маг Урон"],
	["intellect", "Интеллект", ""],
	["harmony", "Гармония", ""],
	["endurance", "Выносливость", "Блок"],
]
const STAT_SUPPORT_STATS := {
	"strength": ["agility", "intuition"],
	"agility": ["strength", "intuition"],
	"intuition": ["strength", "agility"],
	"wisdom": ["intellect", "harmony"],
	"intellect": ["wisdom", "harmony"],
	"harmony": ["wisdom", "intellect"],
}
const DERIVED_COLORS := {
	"Урон": Color8(255, 255, 255),
	"Маг Урон": Color8(190, 150, 255),
	"Уворот": Color8(150, 220, 255),
	"Крит": Color8(255, 90, 90),
	"HP": Color8(110, 235, 120),
	"Блок": Color8(150, 210, 255),
}
const LEGACY_PROFESSION_TYPES := {
	"battle_mage": "mage",
	"support_mage": "mage",
	"harmonist": "mage",
}
const PROFESSIONS := {
	"warrior": {"hp": 70, "base_dodge": 0, "base_crit": 5},
	"archer": {"hp": 25, "base_dodge": 10, "base_crit": 5},
	"assassin": {"hp": 15, "base_dodge": 0, "base_crit": 13, "base_crit_damage_bonus": 30},
	"mage": {"hp": 10, "base_mana": 65, "base_dodge": 0, "base_crit": 5},
	"necromancer": {"hp": 20, "base_mana": 25, "base_dodge": 0, "base_crit": 5},
}
const CLASS_PALETTES := {
	"warrior": {"background": Color8(68, 32, 38), "accent": Color8(220, 95, 100), "icon_background": Color8(145, 52, 60), "glyph": "В"},
	"archer": {"background": Color8(31, 58, 41), "accent": Color8(105, 190, 105), "icon_background": Color8(48, 125, 67), "glyph": "Л"},
	"assassin": {"background": Color8(52, 35, 67), "accent": Color8(170, 120, 215), "icon_background": Color8(105, 67, 150), "glyph": "А"},
	"mage": {"background": Color8(35, 57, 74), "accent": Color8(125, 195, 230), "icon_background": Color8(58, 132, 172), "glyph": "М"},
	"necromancer": {"background": Color8(37, 54, 42), "accent": Color8(120, 220, 135), "icon_background": Color8(54, 120, 69), "glyph": "Н"},
}
const SLOT_LAYOUT := [
	["ears", "Серьги", 0, 0], ["head", "Голова", 2, 0], ["neck", "Шея", 4, 0],
	["back", "Плащ", 0, 1], ["body", "Доспех", 2, 1], ["ring", "Кольцо", 4, 1],
	["hands", "Руки", 0, 2], ["shield", "П рука", 1, 2], ["belt", "Пояс", 2, 2],
	["weapon", "Л рука", 3, 2], ["ring_2", "Кольцо", 4, 2],
	["legs", "Ноги", 2, 3], ["feet", "Обувь", 2, 4],
]
const EQUIPMENT_LABELS := {
	"strength": "Сила",
	"agility": "Ловкость",
	"intuition": "Интуиция",
	"endurance": "Выносливость",
	"wisdom": "Мудрость",
	"intellect": "Интеллект",
	"harmony": "Гармония",
	"hp": "HP",
	"mp": "MP",
	"dodge": "% Уворот",
	"block": "% Блок",
}


static func normalize_profession_type(profession_type: String) -> String:
	return str(LEGACY_PROFESSION_TYPES.get(profession_type, profession_type))


static func get_profession(profession_type: String) -> Dictionary:
	return _dict(PROFESSIONS.get(normalize_profession_type(profession_type), {}))


static func class_palette(profession_type: String) -> Dictionary:
	return _dict(CLASS_PALETTES.get(normalize_profession_type(profession_type), CLASS_PALETTES["warrior"]))


static func is_debug_unlimited(character_id: Variant) -> bool:
	return DEBUG_UNLIMITED_CHARACTER_IDS.has(_int(character_id))


static func minimum_endurance(level: int) -> int:
	return STARTING_ENDURANCE_VALUE + maxi(0, level - 1)


static func calculate_max_hp(level: int, endurance: int, profession_type: String = "warrior") -> int:
	var profession := get_profession(profession_type)
	var base_hp := int(profession.get("hp", BASE_HP)) if not profession.is_empty() else BASE_HP
	return base_hp + ENDURANCE_HP_BONUS * endurance


static func calculate_max_mana(intellect: int, profession_type: String) -> int:
	var data := get_profession(profession_type) if not profession_type.is_empty() else {}
	var base_mana := int(data.get("base_mana", 0))
	return base_mana + MANA_PER_INTELLECT * intellect


static func stat_support_requirement(stat_value: int) -> int:
	return maxi(0, floori(stat_value / 2.0))


static func stat_supports_met(stats: Dictionary, stat_name: String) -> bool:
	if not STAT_SUPPORT_STATS.has(stat_name):
		return true
	var required := stat_support_requirement(_int(stats.get(stat_name, 0)))
	for support in STAT_SUPPORT_STATS[stat_name]:
		if _int(stats.get(support, MIN_STAT_VALUE)) < required:
			return false
	return true


static func adjust_stats(stats: Dictionary, stat_points: int, hp: int, max_hp: int, level: int, stat_name: String, delta: int, character_id: Variant, profession_type: String = "warrior") -> Dictionary:
	if not stats.has(stat_name) or not [-1, 1].has(delta):
		return {}
	var unlimited := is_debug_unlimited(character_id)
	if stat_name == "endurance" and delta > 0:
		return {}
	if delta > 0 and stat_points <= 0 and not unlimited:
		return {}
	var minimum_value := 0
	if not unlimited:
		minimum_value = minimum_endurance(level) if stat_name == "endurance" else MIN_STAT_VALUE
	if delta < 0 and _int(stats[stat_name]) <= minimum_value:
		return {}
	var updated_stats := stats.duplicate()
	updated_stats[stat_name] = _int(updated_stats[stat_name]) + delta
	if not unlimited:
		if delta > 0 and not stat_supports_met(updated_stats, stat_name):
			return {}
		if delta < 0:
			for dependent in _dependents(stat_name):
				if not stat_supports_met(updated_stats, dependent):
					return {}
	var updated_max_hp := calculate_max_hp(level, _int(updated_stats["endurance"]), profession_type)
	var updated_hp := hp
	if stat_name == "endurance" and delta > 0:
		updated_hp += updated_max_hp - max_hp
	return {
		"stats": updated_stats,
		"stat_points": DEBUG_UNLIMITED_STAT_POINTS if unlimited else stat_points - delta,
		"hp": mini(updated_hp, updated_max_hp),
		"max_hp": updated_max_hp,
	}


static func xp_to_next(level: int) -> int:
	if level >= LEVEL_CAP:
		return 0
	return _int(XP_TO_LEVEL.get(level, 0))


static func clamp_chance(value: float, maximum: float = CHANCE_CAP) -> float:
	return clampf(value, 0.0, maximum)


static func dodge_chance(agility: int, profession_type: String, equipment_bonuses: Dictionary) -> float:
	var from_agility := float(agility) * DODGE_CHANCE_PER_AGILITY
	var base_dodge := 0.0
	if not profession_type.is_empty():
		base_dodge = float(get_profession(profession_type).get("base_dodge", 0))
	var equipment_dodge := 0.0
	if not equipment_bonuses.is_empty():
		equipment_dodge = float(equipment_bonuses.get("dodge", 0))
	return clamp_chance(from_agility + base_dodge + equipment_dodge, DODGE_CAP)


static func critical_chance(profession_type: String) -> float:
	var profession := get_profession(profession_type)
	var base_chance := float(profession.get("base_crit", BASE_CRITICAL_CHANCE)) if not profession.is_empty() else BASE_CRITICAL_CHANCE
	return clamp_chance(base_chance)


static func critical_multiplier(profession_type: String, intuition: int) -> float:
	var profession := get_profession(profession_type)
	var class_bonus := int(profession.get("base_crit_damage_bonus", 0)) if not profession.is_empty() else 0
	return BASE_CRITICAL_MULTIPLIER + float(class_bonus) / 100.0 + float(intuition) * CRITICAL_DAMAGE_PER_INTUITION


static func weapon_damage_range(equipment: Dictionary) -> Variant:
	var damage: Variant = _dict(_dict(equipment.get("weapon")).get("effects")).get("damage")
	if not _truthy(damage) or _is_zero_range(damage):
		var shield_damage: Variant = _dict(_dict(equipment.get("shield")).get("effects")).get("damage")
		if _truthy(shield_damage) and not _is_zero_range(shield_damage):
			damage = shield_damage
	if not _truthy(damage):
		return null
	if damage is int or damage is float:
		damage = [damage, damage]
	var low := _int(damage[0])
	var high := _int(damage[-1])
	return Vector2i(mini(low, high), maxi(low, high))


static func normalize_profile(data: Dictionary, title: Variant = null, kind: String = "player") -> Dictionary:
	var profile := {
		"id": data.get("id", data.get("character_id", null)),
		"character_id": data.get("character_id", data.get("id", null)),
		"type": str(data.get("type", "warrior")),
		"profession_type": str(data.get("profession_type", data.get("type", "warrior"))),
		"name": str(data.get("name", "Персонаж")),
		"level": _int(data.get("level", 1)),
		"xp": _int(data.get("xp", 0)),
		"hp": data.get("hp", data.get("current_hp", 0)),
		"max_hp": data.get("max_hp", data.get("hp_max", 0)),
		"mp": data.get("mp", data.get("current_mp", 0)),
		"max_mp": data.get("max_mp", data.get("mp_max", 0)),
		"stats": _dict(data.get("stats", {})).duplicate(),
		"stat_points": _int(data.get("stat_points", 0)),
		"coins": _int(data.get("coins", 0)),
		"equipment": _dict(data.get("equipment", {})).duplicate(),
		"equipment_bonuses": _dict(data.get("equipment_bonuses", {})).duplicate(),
		"max_hp_includes_equipment": _truthy(data.get("max_hp_includes_equipment", false)),
		"kind": kind,
	}
	profile["max_hp"] = maxi(_int(profile["max_hp"]), 1)
	profile["type"] = normalize_profession_type(str(profile["type"]))
	profile["profession_type"] = normalize_profession_type(str(profile["profession_type"]))
	profile["max_mp"] = maxi(_int(profile["max_mp"]), 1)
	profile["hp"] = mini(_int(profile["hp"]), int(profile["max_hp"]))
	profile["mp"] = mini(_int(profile["mp"]), int(profile["max_mp"]))
	profile["title"] = title
	if profile["stats"].is_empty():
		profile["stats"] = DEFAULT_STATS.duplicate()
	if profile["type"] == "assassin":
		var old_max_hp := _int(profile["max_hp"])
		var old_hp := _int(profile["hp"])
		var endurance := _int(profile["stats"].get("endurance", minimum_endurance(int(profile["level"]))))
		var assassin_max_hp := calculate_max_hp(int(profile["level"]), endurance, "assassin")
		if profile["max_hp_includes_equipment"]:
			assassin_max_hp += _int(_dict(profile["equipment_bonuses"]).get("hp", 0))
		profile["max_hp"] = maxi(1, assassin_max_hp)
		if old_max_hp > 0 and old_hp < old_max_hp:
			profile["hp"] = int(float(old_hp) * float(profile["max_hp"]) / float(old_max_hp))
		else:
			profile["hp"] = profile["max_hp"]
		profile["hp"] = mini(maxi(0, int(profile["hp"])), int(profile["max_hp"]))
	return profile


static func effective_stats(profile: Dictionary) -> Dictionary:
	var stats: Dictionary = _dict(profile.get("stats", {})).duplicate()
	var bonuses := _dict(profile.get("equipment_bonuses", {}))
	for stat_name in bonuses:
		if stats.has(stat_name):
			stats[stat_name] = _int(stats[stat_name]) + _int(bonuses[stat_name])
	return stats


static func displayed_hp(profile: Dictionary) -> Vector2i:
	var base_max_hp := _int(profile.get("max_hp", 1))
	var bonuses := _dict(profile.get("equipment_bonuses", {}))
	var hp_bonus := 0 if _truthy(profile.get("max_hp_includes_equipment", false)) else _int(bonuses.get("hp", 0))
	var maximum := maxi(1, base_max_hp + hp_bonus)
	var current := _int(profile.get("hp", 0))
	if hp_bonus > 0 and current >= base_max_hp:
		current += hp_bonus
	return Vector2i(mini(current, maximum), maximum)


static func derived_values(profile: Dictionary, opponent: Variant = null) -> Dictionary:
	var fighter_stats := effective_stats(profile)
	for stat_name in DEFAULT_STATS:
		if not fighter_stats.has(stat_name):
			fighter_stats[stat_name] = DEFAULT_STATS[stat_name]
	var profession_type := str(profile.get("profession_type", profile.get("type", "warrior")))
	var bonuses := _dict(profile.get("equipment_bonuses", {}))
	var weapon: Variant = weapon_damage_range(_dict(profile.get("equipment", {})))
	var intuition := _int(fighter_stats.get("intuition", 2))
	var agility := _int(fighter_stats.get("agility", 2))
	var magic_damage: Variant = null
	if normalize_profession_type(profession_type) in ["mage", "necromancer"]:
		magic_damage = _damage_with_weapon(_int(fighter_stats.get("wisdom", 2)), weapon)
	var values := {}
	if opponent == null:
		values["Урон"] = _damage_with_weapon(maxi(1, _int(fighter_stats.get("strength", 2))), weapon)
		values["Уворот"] = "%d%%" % int(dodge_chance(agility, profession_type, bonuses))
		values["Крит"] = "%d%% × %d%%" % [int(critical_chance(profession_type)), int(critical_multiplier(profession_type, intuition) * 100.0)]
	else:
		var enemy_stats := effective_stats(normalize_profile(_dict(opponent)))
		var enemy_endurance := _int(enemy_stats.get("endurance", 2))
		var strength := _int(fighter_stats.get("strength", 2))
		values["Урон"] = maxi(1, int(float(strength) * 2.0 - float(enemy_endurance) * 0.5))
		values["Уворот"] = "%d%%" % int(dodge_chance(agility, profession_type, bonuses))
		values["Крит"] = "%d%% × %d%%" % [int(critical_chance(profession_type)), int(critical_multiplier(profession_type, intuition) * 100.0)]
	values["HP"] = displayed_hp(profile).y
	if magic_damage != null:
		values["Маг Урон"] = magic_damage
	return values


static func adjust_profile_stat(profile: Dictionary, stat_name: String, delta: int) -> bool:
	var result := adjust_stats(
		_dict(profile["stats"]),
		_int(profile["stat_points"]),
		_int(profile["hp"]),
		_int(profile["max_hp"]),
		_int(profile["level"]),
		stat_name,
		delta,
		profile.get("character_id", profile.get("id")),
	)
	if result.is_empty():
		return false
	var stats: Dictionary = profile["stats"]
	for key in result["stats"]:
		stats[key] = result["stats"][key]
	profile["stat_points"] = result["stat_points"]
	profile["hp"] = result["hp"]
	profile["max_hp"] = result["max_hp"]
	return true


static func mage_adjust_stat(profile: Dictionary, stat_name: String, delta: int) -> bool:
	if not DEFAULT_STATS.has(stat_name) or not [-1, 1].has(delta):
		return false
	if stat_name == "endurance" and delta > 0:
		return false
	if delta > 0 and _int(profile["stat_points"]) <= 0:
		return false
	var stats: Dictionary = profile["stats"]
	var current := _int(stats.get(stat_name, MIN_STAT_VALUE))
	if delta < 0 and current <= MIN_STAT_VALUE:
		return false
	var updated := current + delta
	stats[stat_name] = updated
	profile["stat_points"] = _int(profile["stat_points"]) - delta
	if stat_name == "intellect":
		profile["max_mp"] = calculate_max_mana(updated, "mage")
		profile["mp"] = mini(_int(profile["mp"]), int(profile["max_mp"]))
	return true


# Правка из окна сравнения: маг (is_mage_profile, как у Python _is_mage) идёт по правилам MageCard,
# остальные по правилам Deck. Пустой словарь означает, что правка отклонена.
static func comparison_adjust(raw: Dictionary, stat_name: String, delta: int) -> Dictionary:
	var profile := normalize_profile(raw, "ИГРОК", "player")
	var changed := mage_adjust_stat(profile, stat_name, delta) if is_mage_profile(raw) else adjust_profile_stat(profile, stat_name, delta)
	return profile if changed else {}


static func is_mage_profile(profile: Dictionary) -> bool:
	if profile.get("type") == "mage":
		return true
	var stats := _dict(profile.get("stats", {}))
	for key in ["wisdom", "intellect", "harmony"]:
		if stats.has(key):
			return true
	return false


static func is_warrior_profile(profile: Dictionary) -> bool:
	if profile.get("type") == "mage":
		return false
	var stats := _dict(profile.get("stats", {}))
	for key in ["wisdom", "intellect", "harmony"]:
		if stats.has(key):
			return false
	return true


static func equipment_tooltip_lines(item: Dictionary) -> Array:
	var lines: Array = [[str(item.get("name", "Предмет")), Color8(255, 224, 150)]]
	var description: Variant = item.get("description")
	if _truthy(description):
		lines.append([str(description), Color8(225, 220, 207)])
	var bonuses := _dict(item.get("bonuses"))
	for stat in bonuses:
		var value: Variant = bonuses[stat]
		var sign := "+" if _int(value) > 0 else ""
		lines.append(["Бонус: %s%s %s" % [sign, _plain_number(value), str(EQUIPMENT_LABELS.get(stat, stat))], Color8(140, 230, 150)])
	var damage: Variant = _dict(item.get("effects")).get("damage")
	if _truthy(damage) and not _is_zero_range(damage):
		lines.append(["Урон: %s" % _plain_number(damage[-1]), Color8(255, 220, 120)])
	lines.append(["Вес: %s кг" % format_g(float(item.get("weight", 0)) if item.get("weight") != null else 0.0), Color8(175, 180, 185)])
	return lines


static func format_g(value: float) -> String:
	if value == 0.0:
		return "0"
	var exponent := floori(log(absf(value)) / log(10.0))
	var decimals := clampi(5 - exponent, 0, 10)
	var text := ("%." + str(decimals) + "f") % value
	if text.contains("."):
		text = text.rstrip("0").rstrip(".")
	return text


static func _damage_with_weapon(base_damage: int, weapon: Variant) -> Variant:
	var base := maxi(1, base_damage)
	if weapon == null:
		return base
	var minimum: int = weapon.x + base
	var maximum: int = weapon.y + base
	if minimum == maximum:
		return minimum
	return "%d-%d" % [minimum, maximum]


static func _dependents(stat_name: String) -> Array:
	var result: Array = []
	for stat in STAT_SUPPORT_STATS:
		if STAT_SUPPORT_STATS[stat].has(stat_name):
			result.append(stat)
	return result


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _int(value: Variant) -> int:
	if value == null:
		return 0
	return int(value)


static func _is_zero_range(value: Variant) -> bool:
	return value is Array and value.size() == 2 and float(value[0]) == 0.0 and float(value[1]) == 0.0


# JSON отдаёт целые числа как float, а Python печатает их без дробной части.
static func _plain_number(value: Variant) -> String:
	if value is float and is_equal_approx(value, roundf(value)):
		return str(int(value))
	return str(value)


static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return value
	if value is int or value is float:
		return value != 0
	if value is String:
		return not value.is_empty()
	if value is Array or value is Dictionary:
		return not value.is_empty()
	return true
