extends RefCounted

const ADDED := "added"
const REMOVED := "removed"
const OUTSIDE_TEXT := "Клетка вне карты"
const TYPE_HERO := "hero"
const TYPE_MOB := "mob"
const TYPE_BUILDING := "building"
const MAX_DEFENSE_SLOTS := 5
const BUILDING_ATTACK_TYPES := ["arrow", "magic"]
const BUILDING_DAMAGE_MAX := 10000
const BUILDING_SPRITES := ["castle_8", "castle_5"]
const DEFAULT_BUILDING_SPRITE := "castle_8"
const TARGET_OBJECTIVE := "objective"
const TARGET_CHARACTERS := "characters"
const TARGET_BOTH := "both"
const MAX_SPAWN_LEVEL := 30
const MAX_SPAWN_COUNT := 500
const MAX_INTERVAL_SECONDS := 86399
const MAX_START_DELAY_SECONDS := 604800
const MAX_SPAWN_WAVES := 50
const MAX_SPAWN_REWARD := 1000000
const FRONT_LINE_MOB_KEYS := [
	"imp_vanilla", "imp_sword", "imp_pitchfork", "imp_sword_shield", "imp_pitchfork_shield",
	"imp_green_vanilla", "imp_green_sword", "imp_green_pitchfork",
	"imp_green_sword_shield", "imp_green_pitchfork_shield",
	"imp_blue_vanilla", "imp_blue_sword", "imp_blue_pitchfork",
	"imp_blue_sword_shield", "imp_blue_pitchfork_shield",
]
const MAX_BOSS_SPELL_SLOTS := 3
const MAX_BOSS_DROP_SLOTS := 5
const MAX_BOSS_STAT := 1000000
const MAX_BOSS_SPELL_RANGE := 100
const MAX_BOSS_SPELL_COOLDOWN_SECONDS := 86399
const DEFAULT_MOB_SETTINGS := {
	"level": 1,
	"mob_key": "",
	"count": 1,
	"interval_seconds": 30,
	"squad_min": 1,
	"squad_max": 1,
	"start_after_seconds": 0,
}


# Главное здание: здоровье, регенерация HP в минуту и до MAX_DEFENSE_SLOTS слотов обороны.
# Пределы те же, что проверяет сервер (server/map_editor.py: normalize_building_settings).
static func normalize_building_sprite(value: Variant) -> String:
	var sprite := str(value)
	return sprite if BUILDING_SPRITES.has(sprite) else DEFAULT_BUILDING_SPRITE


static func normalize_building_settings(settings: Variant) -> Dictionary:
	var source: Dictionary = settings if settings is Dictionary else {}
	var slots: Array = []
	var raw_slots: Variant = source.get("defense_slots", [])
	if raw_slots is Array:
		for raw in raw_slots:
			if slots.size() >= MAX_DEFENSE_SLOTS:
				break
			if not raw is Dictionary:
				continue
			var attack := str(raw.get("attack", "arrow"))
			if not BUILDING_ATTACK_TYPES.has(attack):
				attack = "arrow"
			var damage_min := clampi(int(raw.get("damage_min", 1)), 0, BUILDING_DAMAGE_MAX)
			var damage_max := clampi(int(raw.get("damage_max", damage_min)), damage_min, BUILDING_DAMAGE_MAX)
			slots.append({
				"attack": attack,
				"damage_min": damage_min,
				"damage_max": damage_max,
				"radius_units": clampf(float(raw.get("radius_units", 300.0)), 10.0, 2000.0),
				"interval_seconds": clampf(float(raw.get("interval_seconds", 2.0)), 0.2, 60.0),
			})
	return {
		"hp": clampi(int(source.get("hp", 500)), 1, 100000),
		"hp_regen_per_minute": clampi(int(source.get("hp_regen_per_minute", 0)), 0, 10000),
		"defense_slots": slots,
	}


static func is_front_line_mob_key(key: String) -> bool:
	if FRONT_LINE_MOB_KEYS.has(key):
		return true
	var parts := key.split("|", false)
	return parts.size() == 3 and parts[0] == "mob" \
		and not parts[1].is_empty() and not parts[2].is_empty()


static func toggle(
	spawns: Array,
	cell: Vector2i,
	map_size: Vector2i,
	spawn_type := TYPE_HERO,
	mob_settings: Dictionary = {},
	include_target := false,
	building_sprite := DEFAULT_BUILDING_SPRITE,
) -> Dictionary:
	if not inside(cell, map_size):
		return {"result": "", "error": OUTSIDE_TEXT}
	if find(spawns, cell) >= 0:
		erase(spawns, cell)
		return {"result": REMOVED, "error": ""}
	if spawn_type != TYPE_HERO and spawn_type != TYPE_MOB and spawn_type != TYPE_BUILDING:
		return {"result": "", "error": "Неизвестный тип спауна"}
	var spawn := {
		"x": cell.x,
		"y": cell.y,
		"type": spawn_type,
		"name": next_name(spawns, spawn_type),
	}
	if spawn_type == TYPE_MOB:
		spawn["settings"] = normalize_mob_settings(mob_settings, include_target)
	elif spawn_type == TYPE_BUILDING:
		spawn["settings"] = normalize_building_settings(mob_settings)
		spawn["sprite"] = normalize_building_sprite(building_sprite)
	spawns.append(spawn)
	return {"result": ADDED, "error": ""}


static func erase(spawns: Array, cell: Vector2i) -> bool:
	var index := find(spawns, cell)
	if index < 0:
		return false
	spawns.remove_at(index)
	return true


static func load_spawns(raw: Variant, map_size: Vector2i, mode := "front_line") -> Array:
	var result: Array = []
	var type_counts := {TYPE_HERO: 0, TYPE_MOB: 0, TYPE_BUILDING: 0}
	if not raw is Array:
		return result
	for value in raw:
		if not value is Dictionary:
			continue
		var cell := Vector2i(int(value.get("x", -1)), int(value.get("y", -1)))
		if not inside(cell, map_size) or find(result, cell) >= 0:
			continue
		var spawn_type := str(value.get("type", TYPE_HERO))
		if spawn_type != TYPE_HERO and spawn_type != TYPE_MOB and spawn_type != TYPE_BUILDING:
			continue
		var number_name := str(type_counts[spawn_type] + 1)
		var saved_name := str(value.get("name", "")).strip_edges()
		if saved_name.is_empty() or saved_name.is_valid_int():
			saved_name = number_name
		var spawn := {
			"x": cell.x,
			"y": cell.y,
			"type": spawn_type,
			"name": saved_name,
		}
		if spawn_type == TYPE_BUILDING:
			spawn["settings"] = normalize_building_settings(value.get("settings", {}))
			spawn["sprite"] = normalize_building_sprite(value.get("sprite", ""))
		if spawn_type == TYPE_MOB:
			var settings: Variant = value.get("settings", {})
			if not settings is Dictionary:
				continue
			var normalized := normalize_mob_settings(settings, mode == "front_line")
			var waves: Array = normalized.get("waves", [])
			if waves.is_empty() or str(waves[0].get("mob_key", "")).is_empty():
				continue
			spawn["settings"] = normalized
		result.append(spawn)
		type_counts[spawn_type] += 1
	return result


static func to_payload(
	spawns: Array,
	mode := "front_line",
	map_size := Vector2i.ZERO,
) -> Array:
	var payload: Array = []
	var type_counts := {TYPE_HERO: 0, TYPE_MOB: 0, TYPE_BUILDING: 0}
	for spawn in spawns:
		if not spawn is Dictionary or not spawn.has("x") or not spawn.has("y"):
			continue
		var x := int(spawn["x"])
		var y := int(spawn["y"])
		if x < 0 or y < 0 \
			or (map_size.x > 0 and map_size.y > 0 and (x >= map_size.x or y >= map_size.y)):
			continue
		var saved := {"x": x, "y": y}
		var spawn_type := str(spawn.get("type", TYPE_HERO))
		if spawn_type != TYPE_HERO and spawn_type != TYPE_MOB and spawn_type != TYPE_BUILDING:
			continue
		if spawn.has("name"):
			var name := _normalized_name(spawn.get("name", ""), type_counts[spawn_type] + 1)
			if name.is_valid_int():
				name = str(type_counts[spawn_type] + 1)
			saved["name"] = name
		if spawn_type == TYPE_BUILDING:
			saved["type"] = TYPE_BUILDING
			saved["settings"] = normalize_building_settings(spawn.get("settings", {}))
			saved["sprite"] = normalize_building_sprite(spawn.get("sprite", ""))
		if spawn_type == TYPE_MOB:
			saved["type"] = TYPE_MOB
			saved["settings"] = normalize_mob_settings(spawn.get("settings", {}), mode == "front_line")
		payload.append(saved)
		type_counts[spawn_type] += 1
	return payload


static func next_name(spawns: Array, spawn_type := TYPE_HERO) -> String:
	var type_count := 0
	for spawn in spawns:
		if spawn is Dictionary and str(spawn.get("type", TYPE_HERO)) == spawn_type:
			type_count += 1
	for offset in range(type_count + 1):
		var candidate := type_count + 1 + offset
		var candidate_name := str(candidate)
		var name_is_used := false
		for spawn in spawns:
			if spawn is Dictionary \
				and str(spawn.get("type", TYPE_HERO)) == spawn_type \
				and str(spawn.get("name", "")) == candidate_name:
				name_is_used = true
				break
		if not name_is_used:
			return candidate_name
	return str(spawns.size() * 2 + 1)


static func _normalized_name(value: Variant, fallback_number: int) -> String:
	var name := str(value).strip_edges()
	return name if not name.is_empty() else str(fallback_number)


static func normalize_mob_settings(settings: Dictionary, include_target := false) -> Dictionary:
	var raw_waves: Variant = settings.get("waves", [settings])
	if not raw_waves is Array or raw_waves.is_empty():
		raw_waves = [settings]
	var normalized_waves: Array[Dictionary] = []
	for wave_value in raw_waves.slice(0, MAX_SPAWN_WAVES):
		var wave_settings: Dictionary = wave_value if wave_value is Dictionary else {}
		normalized_waves.append(normalize_mob_wave(wave_settings, include_target))
	return {"waves": normalized_waves}


static func normalize_mob_wave(settings: Dictionary, include_target := false) -> Dictionary:
	var normalized := DEFAULT_MOB_SETTINGS.duplicate(true)
	normalized["level"] = clampi(int(settings.get("level", normalized["level"])), 1, MAX_SPAWN_LEVEL)
	normalized["mob_key"] = str(settings.get("mob_key", normalized["mob_key"])).strip_edges()
	normalized["count"] = clampi(
		int(settings.get("count", normalized["count"])), 1, MAX_SPAWN_COUNT
	)
	normalized["interval_seconds"] = clampi(
		int(settings.get("interval_seconds", normalized["interval_seconds"])), 1, MAX_INTERVAL_SECONDS
	)
	normalized["squad_min"] = clampi(int(settings.get("squad_min", 1)), 1, MAX_SPAWN_COUNT)
	normalized["squad_max"] = clampi(
		int(settings.get("squad_max", normalized["squad_min"])), normalized["squad_min"], MAX_SPAWN_COUNT
	)
	normalized["start_after_seconds"] = clampi(
		int(settings.get("start_after_seconds", normalized["start_after_seconds"])),
		0,
		MAX_START_DELAY_SECONDS,
	)
	if include_target:
		var target := str(settings.get("target", TARGET_OBJECTIVE))
		if not [TARGET_OBJECTIVE, TARGET_CHARACTERS, TARGET_BOTH].has(target):
			target = TARGET_OBJECTIVE
		normalized["target"] = target
		normalized["boss"] = normalize_boss_settings(settings.get("boss", {}))
	return normalized


static func normalize_boss_settings(value: Variant) -> Dictionary:
	var settings: Dictionary = value if value is Dictionary else {}
	var raw_slots: Variant = settings.get("spell_slots", [])
	if not raw_slots is Array:
		raw_slots = []
	var spell_slots: Array[Dictionary] = []
	for index in range(MAX_BOSS_SPELL_SLOTS):
		var raw_slot: Variant = raw_slots[index] if index < raw_slots.size() else {}
		var slot: Dictionary = raw_slot if raw_slot is Dictionary else {}
		spell_slots.append({
			"spell_key": str(slot.get("spell_key", "")).substr(0, 64),
			"range": clampi(int(slot.get("range", 3)), 0, MAX_BOSS_SPELL_RANGE),
			"damage": clampi(int(slot.get("damage", 10)), 0, MAX_BOSS_STAT),
			"cooldown_seconds": clampi(
				int(slot.get("cooldown_seconds", 5)), 0, MAX_BOSS_SPELL_COOLDOWN_SECONDS
			),
			"area_radius": clampi(int(slot.get("area_radius", 1)), 0, MAX_BOSS_SPELL_RANGE),
			"mana_cost": clampi(int(slot.get("mana_cost", 5)), 0, MAX_BOSS_STAT),
		})
	var raw_drop_slots: Variant = settings.get("drop_slots", [])
	if not raw_drop_slots is Array:
		raw_drop_slots = []
	var drop_slots: Array[Dictionary] = []
	for index in range(MAX_BOSS_DROP_SLOTS):
		var raw_slot: Variant = raw_drop_slots[index] if index < raw_drop_slots.size() else {}
		var slot: Dictionary = raw_slot if raw_slot is Dictionary else {}
		drop_slots.append({
			"item_id": maxi(0, int(slot.get("item_id", 0))),
			"chance_percent": clampi(int(slot.get("chance_percent", 0)), 0, 100),
		})
	return {
		"enabled": bool(settings.get("enabled", false)),
		"max_hp": clampi(int(settings.get("max_hp", 1000)), 1, MAX_BOSS_STAT),
		"max_mp": clampi(int(settings.get("max_mp", 100)), 0, MAX_BOSS_STAT),
		"reward_xp": clampi(int(settings.get("reward_xp", 100)), 0, MAX_SPAWN_REWARD),
		"spell_slots": spell_slots,
		"drop_slots": drop_slots,
	}


static func find(spawns: Array, cell: Vector2i) -> int:
	for index in range(spawns.size()):
		var spawn: Variant = spawns[index]
		if spawn is Dictionary and int(spawn.get("x", -1)) == cell.x and int(spawn.get("y", -1)) == cell.y:
			return index
	return -1


static func inside(cell: Vector2i, map_size: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < map_size.x and cell.y < map_size.y
