extends Node

const SPAWN_RULES = preload("res://scripts/map_editor_spawn_rules.gd")
const BUILDING_DIALOG = preload("res://scripts/building_settings_dialog.gd")

var _failures := 0
var _checks := 0


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error(message)


func _ready() -> void:
	_run()


func _run() -> void:
	var raw_settings := {
		"hp": 800,
		"hp_regen_per_minute": 60,
		"defense_slots": [
			{"attack": "arrow", "damage_min": 5, "damage_max": 9, "radius_units": 400, "interval_seconds": 1.5},
			{"attack": "magic", "damage_min": 10, "damage_max": 4, "radius_units": 99999, "interval_seconds": 0.01},
			{"attack": "fire", "damage_min": 1, "damage_max": 2},
		],
	}
	var normalized := SPAWN_RULES.normalize_building_settings(raw_settings)
	_check(int(normalized["hp"]) == 800, "здоровье здания сохраняется")
	_check(int(normalized["hp_regen_per_minute"]) == 60, "регенерация в минуту сохраняется")
	var slots: Array = normalized["defense_slots"]
	_check(slots.size() == 3, "слоты обороны сохраняются")
	_check(str(slots[0]["attack"]) == "arrow" and float(slots[0]["interval_seconds"]) == 1.5, "слот стрел: тип и интервал")
	_check(int(slots[1]["damage_max"]) == 10, "урон максимум не меньше минимума")
	_check(float(slots[1]["radius_units"]) == 2000.0 and float(slots[1]["interval_seconds"]) == 0.2, "радиус и интервал ограничены")
	_check(str(slots[2]["attack"]) == "arrow", "неизвестный тип атаки заменяется стрелами")

	var many := {"defense_slots": []}
	for index in range(7):
		many["defense_slots"].append({"attack": "arrow", "damage_min": 1, "damage_max": 2})
	_check(SPAWN_RULES.normalize_building_settings(many)["defense_slots"].size() == SPAWN_RULES.MAX_DEFENSE_SLOTS, "слотов обороны не больше пяти")

	var spawns: Array = []
	var map_size := Vector2i(16, 16)
	var added := SPAWN_RULES.toggle(spawns, Vector2i(3, 4), map_size, SPAWN_RULES.TYPE_BUILDING, raw_settings)
	_check(str(added["result"]) == SPAWN_RULES.ADDED, "здание ставится на клетку")
	_check(str(spawns[0]["type"]) == SPAWN_RULES.TYPE_BUILDING, "точка получает тип здания")

	var payload := SPAWN_RULES.to_payload(spawns, "economy", map_size)
	_check(payload.size() == 1 and str(payload[0]["type"]) == SPAWN_RULES.TYPE_BUILDING, "здание попадает в публикацию")
	_check(payload[0]["settings"]["defense_slots"].size() == 3, "слоты обороны попадают в публикацию")

	spawns[0]["sprite"] = "castle_5"
	var with_sprite := SPAWN_RULES.to_payload(spawns, "economy", map_size)
	_check(str(with_sprite[0]["sprite"]) == "castle_5", "спрайт здания публикуется")
	var loaded := SPAWN_RULES.load_spawns(with_sprite, map_size, "economy")
	_check(str(loaded[0]["sprite"]) == "castle_5", "спрайт здания читается обратно")
	_check(SPAWN_RULES.normalize_building_sprite("dragon") == "castle_8", "неизвестный спрайт заменяется основным")
	_check(loaded.size() == 1 and str(loaded[0]["type"]) == SPAWN_RULES.TYPE_BUILDING, "здание загружается из карты")
	_check(int(loaded[0]["settings"]["hp"]) == 800, "настройки здания читаются обратно")

	var dialog = BUILDING_DIALOG.new()
	add_child(dialog)
	dialog.set_settings(raw_settings)
	_check(dialog.slot_count() == 3, "диалог показывает сохранённые слоты обороны")
	dialog._on_add_slot_pressed()
	dialog._on_add_slot_pressed()
	_check(dialog.slot_count() == 5, "диалог добавляет слоты до пяти")
	dialog._on_add_slot_pressed()
	_check(dialog.slot_count() == 5, "шестой слот не добавляется")
	dialog._hp_spin.value = 1200
	var from_dialog: Dictionary = dialog.get_settings()
	_check(int(from_dialog["hp"]) == 1200, "диалог возвращает здоровье")
	_check(from_dialog["defense_slots"].size() == 5, "диалог возвращает пять слотов")
	dialog.queue_free()

	print("building_spawn_rules_smoke_test: %s (%d checks)" % ["OK" if _failures == 0 else "FAILED", _checks])
	get_tree().quit(0 if _failures == 0 else 1)
