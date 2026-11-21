extends Node

const RULES := preload("res://scripts/character_profile_rules.gd")
const CARD_SCRIPT := preload("res://scripts/character_card.gd")
const OVERLAY_SCRIPT := preload("res://scripts/character_profile_overlay.gd")

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	_check_card()
	_check_overlay()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("character_profile_smoke_test: OK")
	get_tree().quit(code)


func _sample(points: int = 3) -> Dictionary:
	return {
		"id": 5,
		"name": "Тест",
		"profession_type": "warrior",
		"level": 7,
		"xp": 120,
		"hp": 80,
		"max_hp": 0,
		"mp": 10,
		"max_mp": 0,
		"stats": {"strength": 12, "agility": 9, "intuition": 7, "wisdom": 4, "intellect": 6, "endurance": 10},
		"stat_points": points,
		"copper": 5,
		"silver": 2,
		"gold": 1,
		"equipment": {
			"weapon": {"name": "Меч", "effects": {"damage": [3, 7]}, "weight": 2.5},
			"body": {"name": "Доспех", "weight": 4.0},
		},
		"equipment_bonuses": {"strength": 2, "agility": 2, "endurance": 3, "hp": 20, "block": 5},
		"max_hp_includes_equipment": false,
		"carried_weight_kg": 40,
	}


func _check_rules() -> void:
	var profile := RULES.normalize_profile(_sample())
	_check(profile["max_hp"] == 120 and profile["max_mp"] == 36, "максимум HP и MP считается по выносливости и интеллекту")
	_check(profile["hp"] == 80 and profile["mp"] == 10, "текущие HP и MP сохраняются")
	_check(RULES.displayed_hp(profile) == Vector2i(80, 140), "бонус экипировки +20 HP добавляется к максимуму")

	var effective := RULES.effective_stats(profile)
	_check(effective["strength"] == 14 and effective["agility"] == 11 and effective["endurance"] == 13, "характеристики считаются с учётом экипировки")
	var derived := RULES.derived_values(profile)
	_check(derived["Урон"] == "17-21", "урон силы и оружия 17-21 (как в Python)")
	_check(derived["Уворот"] == "55%", "уворот 55% (как в Python)")
	_check(derived["Крит"] == "35% × 150%", "крит 35% × 150% (как в Python)")
	_check(derived["Маг Урон"] == "7-11", "магический урон 7-11 (как в Python)")
	_check(derived["HP"] == 140 and derived["Блок"] == "5%", "HP 140 и блок 5% (как в Python)")

	var speeds := RULES.combat_speed_values(profile)
	_check(is_equal_approx(speeds["attack_seconds"], 0.64), "скорость атаки 0.64 с (как в Python)")
	_check(speeds["move_speed"] == 150 and speeds["move_speed_bonus"] == 6, "скорость 150 px/с с бонусом +6: банковское округление 150.5 → 150")
	_check(RULES.carry_capacity(profile) == 109, "грузоподъёмность 109 кг")
	_check(is_equal_approx(RULES.character_movement_multiplier(profile), 0.7), "при 40 кг (37% грузоподъёмности) множитель 0.7")
	_check(RULES.load_color(40, 109) == Color8(220, 210, 190), "при 40 кг цвет веса нейтральный")
	var heavy_source := _sample()
	heavy_source["carried_weight_kg"] = 70
	var heavy := RULES.normalize_profile(heavy_source)
	_check(is_equal_approx(RULES.character_movement_multiplier(heavy), 0.5), "при 70 кг множитель 0.5 (как в Python)")
	_check(RULES.load_color(70, 109) == Color8(245, 205, 80), "при 70 кг вес жёлтый (как в Python)")
	_check(RULES.xp_to_next(7) == 665 and RULES.xp_to_next(20) == 2940 and RULES.xp_to_next(25) == 3390 and RULES.xp_to_next(30) == 0, "опыт до следующего уровня совпадает с Python")

	var raised := RULES.adjust_stat(profile, "strength", 1)
	_check(raised["stats"]["strength"] == 13 and raised["stat_points"] == 2 and raised["max_hp"] == 120 and raised["hp"] == 80, "+1 к силе тратит очко (как в Python)")
	_check(RULES.adjust_stat(profile, "endurance", 1).is_empty(), "выносливость вручную не растёт")
	_check(RULES.adjust_stat(RULES.normalize_profile(_sample(0)), "strength", 1).is_empty(), "без свободных очков +1 запрещён")
	var min_strength_source := _sample()
	min_strength_source["stats"]["strength"] = 3
	_check(RULES.adjust_stat(RULES.normalize_profile(min_strength_source), "strength", -1).is_empty(), "сила не опускается ниже 3")
	var low_endurance_source := _sample()
	low_endurance_source["level"] = 5
	low_endurance_source["stats"]["endurance"] = 7
	_check(RULES.adjust_stat(RULES.normalize_profile(low_endurance_source), "endurance", -1).is_empty(), "выносливость не ниже минимума уровня (7 на 5 уровне)")
	var lowered := RULES.adjust_stat(profile, "agility", -1)
	_check(lowered["stats"]["agility"] == 8 and lowered["stat_points"] == 4, "-1 к ловкости возвращает очко (как в Python)")

	var debug_source := _sample()
	debug_source["id"] = 2
	var debug_level := RULES.adjust_level(RULES.normalize_profile(debug_source), 1)
	_check(debug_level["level"] == 8 and debug_level["max_hp"] == 120 and debug_level["stats"]["endurance"] == 10, "отладочный уровень тестового персонажа (как в Python)")
	_check(RULES.adjust_level(profile, 1).is_empty(), "уровень обычного персонажа не меняется")

	var lines := RULES.equipment_tooltip_lines({"name": "Меч", "bonuses": {"strength": 2}, "effects": {"damage": [3, 7]}, "weight": 2.5})
	_check(lines[0][0] == "Меч" and lines[1][0] == "Бонус: +2 Сила" and lines[2][0] == "Урон: 3–7" and lines[3][0] == "Вес: 2.5 кг", "подсказка предмета совпадает с Python")


func _check_card() -> void:
	var host := Control.new()
	host.size = Vector2(1920, 1080)
	add_child(host)
	var card = CARD_SCRIPT.new()
	host.add_child(card)
	card.set_profile(_sample())
	var stat_events: Array = []
	card.stat_requested.connect(func(stat_name: String, delta: int) -> void: stat_events.append([stat_name, delta]))
	var closes := [0]
	card.close_requested.connect(func() -> void: closes[0] += 1)
	var level_events: Array = []
	card.level_requested.connect(func(delta: int) -> void: level_events.append(delta))

	card.handle_click(card.stat_button_rect("strength", 1).get_center())
	card.handle_click(card.stat_button_rect("agility", -1).get_center())
	card.handle_click(card.close_button_rect().get_center())
	card.handle_click(Vector2(200.0, 300.0))
	_check(not card.handle_click(Vector2(-10.0, -10.0)), "клик вне карточки не обрабатывается карточкой")
	_check(stat_events == [["strength", 1], ["agility", -1]], "кнопки +/- отправляют изменение характеристики")
	_check(closes[0] == 1, "крестик отправляет закрытие карточки")
	_check(level_events.is_empty(), "у обычного персонажа кнопок уровня нет")
	_check(card.current_profile()["stats"]["strength"] == 12, "карточка не меняет характеристики сама: их меняет сервер")

	var debug_source := _sample()
	debug_source["id"] = 2
	card.set_profile(debug_source)
	card.handle_click(card.level_button_rect(1).get_center())
	_check(level_events == [1], "у тестового персонажа кнопка + уровня отправляет изменение")


func _check_overlay() -> void:
	var host := Control.new()
	host.size = Vector2(1920, 1080)
	add_child(host)
	var overlay = OVERLAY_SCRIPT.new()
	host.add_child(overlay)
	_check(not overlay.is_open(), "оверлей закрыт по умолчанию")
	overlay.open(_sample())
	_check(overlay.is_open() and overlay.current_profile()["stats"]["strength"] == 12, "открытие показывает профиль персонажа")

	var backpack_events := [0]
	overlay.backpack_requested.connect(func() -> void: backpack_events[0] += 1)
	overlay._backpack_button.pressed.emit()
	_check(backpack_events[0] == 1, "кнопка РЮКЗАК просит открыть инвентарь")

	var stat_events: Array = []
	overlay.stat_requested.connect(func(stat_name: String, delta: int) -> void: stat_events.append([stat_name, delta]))
	overlay._card.handle_click(overlay._card.stat_button_rect("strength", 1).get_center())
	_check(stat_events == [["strength", 1]], "оверлей передаёт изменение характеристики наверх")

	overlay.update_profile(_sample(9))
	_check(overlay.current_profile()["stat_points"] == 9, "обновление профиля выводит свежие данные")
	overlay.open(_sample())
	overlay._card.handle_click(overlay._card.close_button_rect().get_center())
	_check(not overlay.is_open(), "крестик на карточке закрывает оверлей")


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
