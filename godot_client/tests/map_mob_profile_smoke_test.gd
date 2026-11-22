extends Node

const Dialog := preload("res://scripts/mob_profile_dialog.gd")
const Rules := preload("res://scripts/mob_profile_rules.gd")
const NOTE := "Экипировка не загружена: сервер недоступен"
const SAVED_TEXT := "Настройки моба сохранены для режима Economy."


class ProfileEditor extends "res://scripts/map_editor.gd":
	func _ready() -> void:
		_mode = "economy"
		_build_ui()


var failed := false
var saved: Array = []
var cancelled := 0


func _ready() -> void:
	call_deferred("_run")


func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		failed = true
	return condition


func _run() -> void:
	_check_rules()
	await _check_values_and_steppers()
	await _check_stats_and_level()
	await _check_deck_rules()
	await _check_front_line_rules_and_resources()
	await _check_states_and_patrol()
	await _check_layout_with_notes()
	await _check_collected_settings()
	await _check_equipment_without_list()
	await _check_equipment_with_list()
	await _check_keyboard_and_wheel()
	await _check_editor_integration()
	if not failed:
		print("Mob profile smoke tests passed: values, steppers, stats, patrol, equipment, keyboard and editor integration work.")
	get_tree().quit(1 if failed else 0)


func _sample_settings() -> Dictionary:
	return {
		"move_speed": 210.0,
		"windup": 0.44,
		"backswing": 0.42,
		"aggro_tiles": 3.5,
		"respawn_seconds": 30.0,
		"reward_copper": 30.0,
		"reward_xp": 10.0,
		"state": "aggressive",
		"level": 3.0,
		"stats": {
			"strength": 4.0,
			"agility": 4.0,
			"intuition": 10.0,
			"wisdom": 3.0,
			"intellect": 3.0,
			"endurance": 6.0,
		},
		"equipment": {},
		"patrol": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
	}


func _sample_items() -> Array:
	return [
		{"id": 11, "name": "Шлем новичка", "equip_slot": "head", "effects": {"requirements": {"level": 1}}},
		{"id": 12, "name": "Шлем ветерана", "equip_slot": "head", "effects": {"requirements": {"level": 5}}},
		{"id": 13, "name": "Шлем силача", "equip_slot": "head", "effects": {"requirements": {"strength": 8}}},
		{"id": 21, "name": "Медное кольцо", "equip_slot": "ring", "effects": {}},
		{"id": 22, "name": "Серебряное кольцо", "equip_slot": "ring"},
		{"id": 31, "name": "Короткий меч", "equip_slot": "weapon", "effects": {"requirements": {"level": 2, "strength": 4}}},
	]


func _open_dialog(mode: String, settings: Dictionary, options: Dictionary = {}) -> Control:
	var dialog: Control = Dialog.new()
	dialog.setup("Синий бес с вилами", mode, settings, options)
	dialog.save_requested.connect(func(result: Dictionary) -> void: saved.append(result))
	dialog.cancel_requested.connect(func() -> void: cancelled += 1)
	add_child(dialog)
	await get_tree().process_frame
	await get_tree().process_frame
	return dialog


func _dispose(dialog: Control) -> void:
	remove_child(dialog)
	dialog.free()


func _input_texts(inputs: Dictionary) -> Dictionary:
	var result := {}
	for key in inputs:
		result[key] = (inputs[key] as LineEdit).text
	return result


func _labels_text(node: Node) -> String:
	var parts: Array[String] = []
	for label in node.find_children("*", "Label", true, false):
		parts.append((label as Label).text)
	return "\n".join(parts)


func _find_button(node: Node, caption: String) -> Button:
	for button in node.find_children("*", "Button", true, false):
		if (button as Button).text == caption:
			return button
	return null


func _type(input: LineEdit, text: String) -> void:
	input.text = text
	input.text_submitted.emit(text)


func _mouse_button(position: Vector2, button: MouseButton, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.position = position
	event.global_position = position
	event.button_index = button
	event.pressed = pressed
	event.button_mask = (1 << (button - 1)) if pressed else 0
	get_viewport().push_input(event, true)


func _mouse_move(position: Vector2, mask: int) -> void:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	event.button_mask = mask
	get_viewport().push_input(event, true)


func _press_escape() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ESCAPE
	event.pressed = true
	get_viewport().push_input(event)


func _cell_center(grid: Control, cell: Vector2i) -> Vector2:
	return grid.get_global_rect().position + (Vector2(cell) + Vector2(0.5, 0.5)) * float(grid.cell_size)


func _good_settings() -> Dictionary:
	return {
		"level": 3,
		"state": "aggressive",
		"stats": {"strength": 4, "agility": 4, "intuition": 10, "wisdom": 3, "intellect": 3, "endurance": 6},
		"patrol": [[-9, -9], [8, 8], [0, 0]],
	}


func _check_rules() -> void:
	_check(Rules.format_hms(30.0) == "00:00:30", "format_hms(30) должно давать 00:00:30.")
	_check(Rules.format_hms(3661.0) == "01:01:01", "format_hms(3661) должно давать 01:01:01.")
	_check(Rules.format_hms(86399.0) == "23:59:59", "format_hms(86399) должно давать 23:59:59.")
	_check(Rules.parse_seconds("1:02:03") == 3723.0, "«1:02:03» должно разбираться как 3723 секунды.")
	_check(Rules.parse_seconds("1:30") == 90.0, "«1:30» должно разбираться как 90 секунд.")
	_check(Rules.parse_seconds(" 45 ") == 45.0, "Обычное число секунд должно разбираться как есть.")
	_check(Rules.parse_seconds("abc") == null, "Мусор вместо времени не должен разбираться.")
	_check(Rules.parse_seconds("1:2:3:4") == null, "Четыре части времени не должны разбираться.")
	_check(Rules.parse_seconds("") == null, "Пустая строка не должна разбираться как время.")
	_check(Rules.format_field("windup", 0.44) == "0.44", "Замах показывается с двумя знаками.")
	_check(Rules.format_field("aggro_tiles", 3.5) == "3.5", "Радиус агрессии показывается с одним знаком.")
	_check(Rules.format_field("move_speed", 210.0) == "210", "Скорость показывается целым числом.")
	_check(Rules.parse_field("windup", "0,5") == 0.5, "Запятая в дробном числе должна приниматься.")
	_check(Rules.parse_field("windup", "x") == null, "Не число не должно разбираться.")
	_check(Rules.clamp_field("move_speed", 999.0) == 400.0, "Скорость зажимается верхним пределом.")
	_check(Rules.clamp_field("windup", 0.0) == 0.05, "Замах зажимается нижним пределом.")
	_check(Rules.clamp_field("respawn_seconds", 86400.0) == 86399.0, "Респаун зажимается 23:59:59.")
	_check(Rules.clamp_field("reward_xp", 12.6) == 13.0, "Целые поля округляются.")
	_check(typeof(Rules.field_output("reward_xp", 13.0)) == TYPE_INT, "Награда уходит на сервер целым числом.")
	_check(typeof(Rules.field_output("windup", 0.45)) == TYPE_FLOAT, "Замах уходит на сервер дробным числом.")
	_check(Rules.item_slot("ring_2") == "ring", "Второе кольцо берёт предметы слота ring.")

	var economy := Rules.rules_for_mode("economy")
	_check(Rules.validate_settings(economy, _good_settings()) == "", "Корректные настройки должны проходить проверку.")
	var bad := _good_settings()
	bad["level"] = 31
	_check(Rules.validate_settings(economy, bad).begins_with("Уровень"), "Уровень выше 30 должен отклоняться.")
	bad = _good_settings()
	bad["state"] = "bogus"
	_check(Rules.validate_settings(economy, bad) == "Выберите состояние моба.", "Неизвестное состояние отклоняется.")
	bad = _good_settings()
	bad["stats"].erase("wisdom")
	_check(Rules.validate_settings(economy, bad).contains("не задана"), "Пропущенная характеристика отклоняется.")
	bad = _good_settings()
	bad["stats"]["endurance"] = 7
	_check(Rules.validate_settings(economy, bad).begins_with("Выносливость"), "Выносливость должна совпадать с уровнем.")
	bad = _good_settings()
	bad["stats"]["agility"] = 2
	_check(Rules.validate_settings(economy, bad).contains("не ниже 3"), "Характеристика ниже минимума отклоняется.")
	bad = _good_settings()
	bad["stats"]["strength"] = 12
	_check(Rules.validate_settings(economy, bad).begins_with("Вложено"), "Лишние очки характеристик отклоняются.")
	bad = _good_settings()
	bad["patrol"] = [[9, 0]]
	_check(Rules.validate_settings(economy, bad).contains("вне поля"), "Клетка патруля вне поля отклоняется.")
	bad = _good_settings()
	bad["patrol"] = []
	_check(Rules.validate_settings(economy, bad) == "", "Пустой патруль допустим.")
	_check(Rules.rules_for_mode("economy") == Rules.DEFAULT_RULES, "Economy использует общие правила.")
	_check(Rules.rules_for_mode("deck") != economy, "Deck использует свои правила.")
	var front_line := Rules.rules_for_mode("front_line")
	var unlimited_settings := _good_settings()
	unlimited_settings["level"] = 100
	unlimited_settings["stats"] = {
		"strength": 1000000,
		"agility": 2000000,
		"intuition": 3000000,
		"wisdom": 4000000,
		"intellect": 5000000,
		"endurance": 6000000,
	}
	unlimited_settings["max_hp"] = 7000000
	unlimited_settings["max_mp"] = 8000000
	_check(
		Rules.validate_settings(front_line, unlimited_settings) == "",
		"Front Line принимает характеристики, уровень и ресурсы без игровых верхних ограничений.",
	)
	unlimited_settings["stats"]["endurance"] = 0
	_check(
		Rules.validate_settings(front_line, unlimited_settings) == "",
		"Выносливость Front Line задаётся независимо от уровня и может быть нулевой.",
	)
	unlimited_settings["stats"]["strength"] = -1
	_check(
		Rules.validate_settings(front_line, unlimited_settings).contains("не ниже 0"),
		"Отрицательные характеристики отклоняются.",
	)


func _check_front_line_rules_and_resources() -> void:
	var dialog := await _open_dialog("front_line", _sample_settings(), {"mode_name": "Front Line"})
	dialog._damage_inputs["damage_min"].text = "2"
	dialog._commit_damage("damage_min")
	dialog._damage_inputs["damage_max"].text = "5"
	dialog._commit_damage("damage_max")
	dialog.set_stat_value("strength", 3)
	_check(
		dialog._damage_actual["damage_min"].text == "8" and dialog._damage_actual["damage_max"].text == "11"
		and int(dialog.collect_settings()["damage_min"]) == 2 and int(dialog.collect_settings()["damage_max"]) == 5,
		"Фактический урон = база + 2 за очко силы; базовые минимум и максимум сохраняются",
	)
	_check(
		not (dialog.field_inputs["max_mp"] as LineEdit).editable
		and not (dialog.field_inputs["aggro_tiles"] as LineEdit).editable
		and not (dialog.stat_inputs["wisdom"] as LineEdit).editable
		and not dialog.level_input.editable
		and dialog.field_rows["max_mp"].modulate.a < 1.0
		and (dialog.field_inputs["max_hp"] as LineEdit).editable
		and dialog.field_rows["max_hp"].modulate.a == 1.0,
		"Во Front Line неиспользуемые параметры неактивны и затемнены, используемые — нет",
	)
	_check(
		dialog.field_inputs.has("max_hp") and dialog.field_inputs.has("max_mp")
		and (dialog.stat_inputs["endurance"] as LineEdit).editable
		and not (dialog.stat_plus["strength"] as Button).disabled,
		"В настройках Front Line доступны ХП, МП и свободные характеристики, включая выносливость.",
	)
	_check(
		_labels_text(dialog).contains("Без ограничений")
		and _labels_text(dialog).contains("Выносливость задаётся вручную"),
		"Front Line не привязывает характеристики и выносливость к уровню.",
	)
	dialog.set_level(100)
	dialog.set_stat_value("endurance", 5000000)
	dialog.set_stat_value("strength", 4000000)
	dialog.set_integer_field_value("max_hp", 123456789)
	dialog.step_field("max_hp", 1)
	dialog.set_integer_field_value("max_mp", 987654321)
	_check(
		dialog.level == 100 and int(dialog.stats["endurance"]) == 5000000
		and int(dialog.stats["strength"]) == 4000000
		and int(dialog.values["max_hp"]) == 123456799
		and int(dialog.values["max_mp"]) == 987654321,
		"Значения характеристик, ХП и МП сохраняются без прежних лимитов.",
	)
	dialog.set_integer_field_value("attack_range", 1600)
	var result: Dictionary = dialog.collect_settings()
	_check(
		int(dialog.values["attack_range"]) == 1500 and int(result["attack_range"]) == 1500
		and typeof(result["attack_range"]) == TYPE_INT,
		"Дальность атаки во Front Line ограничена 1500 ед. и уходит на сервер целым числом.",
	)
	_check(
		result["max_hp"] == 123456799 and result["max_mp"] == 987654321
		and typeof(result["max_hp"]) == TYPE_INT and typeof(result["max_mp"]) == TYPE_INT,
		"ХП и МП отправляются на сервер целыми числами.",
	)
	_dispose(dialog)


func _check_values_and_steppers() -> void:
	var dialog := await _open_dialog("economy", _sample_settings(), {"mode_name": "Economy", "note": NOTE})
	var texts := _input_texts(dialog.field_inputs)
	_check(
		texts == {
			"move_speed": "210",
			"windup": "0.44",
			"backswing": "0.42",
			"aggro_tiles": "3.5",
			"respawn_seconds": "00:00:30",
			"reward_copper": "30",
			"reward_xp": "10",
		},
		"Поля основных параметров показывают значения как на образце. Получено: %s" % str(texts),
	)
	_check(dialog.level == 3 and dialog.level_input.text == "3", "Уровень моба должен быть 3.")
	_check(dialog.free_points() == 0 and dialog.total_points() == 9, "Свободных очков должно быть 0 из 9.")
	var stat_texts := _input_texts(dialog.stat_inputs)
	_check(
		stat_texts == {
			"strength": "4", "agility": "4", "intuition": "10",
			"wisdom": "3", "intellect": "3", "endurance": "6",
		},
		"Характеристики показываются как на образце. Получено: %s" % str(stat_texts),
	)
	_check(not (dialog.stat_inputs["endurance"] as LineEdit).editable, "Выносливость нельзя править вручную.")
	var text_all := _labels_text(dialog)
	for expected in [
		"Параметры: Синий бес с вилами  ·  режим «Economy»",
		"Параметры относятся к виду моба",
		"Свободных очков: 0 из 9",
		"Выносливость задаётся уровнем: 6",
		"клеток: 3 · ЛКМ — закрасить, ПКМ — стереть",
		"надето: 0 из 13",
		"Жёлтый крест — точка появления моба",
	]:
		_check(text_all.contains(expected), "В окне не найдена надпись «%s»." % expected)
	_check(String(dialog.field_inputs["reward_xp"].tooltip_text).contains("делится между героями по доле урона"), "Пояснение об опыте в подсказке поля")
	_check(dialog.message_text() == NOTE, "Заметка об экипировке показывается в футере.")
	_check(dialog.save_button.text == "Сохранить изменения" and dialog.cancel_button.text == "Отмена", "Кнопки футера.")
	_check(
		(dialog.state_buttons["aggressive"] as Button).has_theme_stylebox_override("normal")
		and not (dialog.state_buttons["neutral"] as Button).has_theme_stylebox_override("normal"),
		"Выбранное состояние подсвечивается рамкой.",
	)
	_check((dialog.stat_plus["strength"] as Button).disabled, "«+» неактивен, когда нет свободных очков.")
	_check((dialog.stat_minus["wisdom"] as Button).disabled, "«−» неактивен на минимуме характеристики.")
	_check(not (dialog.stat_minus["strength"] as Button).disabled, "«−» активен выше минимума.")

	var screen := _screen_size()
	_check(
		dialog.size.is_equal_approx(get_viewport().get_visible_rect().size),
		"Окно должно занимать весь экран: %s." % str(dialog.size),
	)
	_check(
		dialog.panel.size.y <= screen.y - 24.0 and dialog.panel.size.x <= screen.x - 24.0,
		"Панель параметров %s не помещается на экран %s с запасом." % [str(dialog.panel.size), str(screen)],
	)

	(dialog.field_plus["move_speed"] as Button).pressed.emit()
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "215", "«+» добавляет 5 к скорости.")
	(dialog.field_minus["move_speed"] as Button).pressed.emit()
	(dialog.field_minus["move_speed"] as Button).pressed.emit()
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "205", "«−» убавляет 5 от скорости.")
	(dialog.field_plus["windup"] as Button).pressed.emit()
	_check((dialog.field_inputs["windup"] as LineEdit).text == "0.49", "Замах меняется шагом 0.05.")
	(dialog.field_minus["backswing"] as Button).pressed.emit()
	_check((dialog.field_inputs["backswing"] as LineEdit).text == "0.37", "Откат меняется шагом 0.05.")
	(dialog.field_plus["aggro_tiles"] as Button).pressed.emit()
	_check((dialog.field_inputs["aggro_tiles"] as LineEdit).text == "4.0", "Радиус агрессии меняется шагом 0.5.")
	(dialog.field_plus["respawn_seconds"] as Button).pressed.emit()
	_check((dialog.field_inputs["respawn_seconds"] as LineEdit).text == "00:00:35", "Респаун меняется шагом 5 секунд.")
	(dialog.field_plus["reward_copper"] as Button).pressed.emit()
	_check((dialog.field_inputs["reward_copper"] as LineEdit).text == "35", "Монеты меняются шагом 5.")
	(dialog.field_minus["reward_xp"] as Button).pressed.emit()
	_check((dialog.field_inputs["reward_xp"] as LineEdit).text == "5", "Опыт меняется шагом 5.")

	dialog.set_field_value("move_speed", 9999.0)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "400", "Скорость не выше 400.")
	_check((dialog.field_plus["move_speed"] as Button).disabled, "«+» неактивен на максимуме.")
	_check(not (dialog.field_minus["move_speed"] as Button).disabled, "«−» активен ниже максимума.")
	dialog.set_field_value("move_speed", -5.0)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "0", "Скорость не ниже 0.")
	_check((dialog.field_minus["move_speed"] as Button).disabled, "«−» неактивен на минимуме.")
	dialog.set_field_value("windup", 0.0)
	_check((dialog.field_inputs["windup"] as LineEdit).text == "0.05", "Замах не ниже 0.05.")
	dialog.set_field_value("aggro_tiles", 99.0)
	_check((dialog.field_inputs["aggro_tiles"] as LineEdit).text == "30.0", "Радиус агрессии не выше 30.")
	dialog.set_field_value("respawn_seconds", 999999.0)
	_check((dialog.field_inputs["respawn_seconds"] as LineEdit).text == "23:59:59", "Респаун не выше 23:59:59.")
	dialog.set_field_value("reward_copper", 2000000.0)
	_check((dialog.field_inputs["reward_copper"] as LineEdit).text == "1000000", "Монеты не выше миллиона.")

	_type(dialog.field_inputs["respawn_seconds"], "01:02:03")
	_check(
		(dialog.field_inputs["respawn_seconds"] as LineEdit).text == "01:02:03" and float(dialog.values["respawn_seconds"]) == 3723.0,
		"Респаун вводится как ЧЧ:ММ:СС.",
	)
	_type(dialog.field_inputs["respawn_seconds"], "1:30")
	_check((dialog.field_inputs["respawn_seconds"] as LineEdit).text == "00:01:30", "Респаун вводится как ММ:СС.")
	_type(dialog.field_inputs["respawn_seconds"], "abc")
	_check(
		(dialog.field_inputs["respawn_seconds"] as LineEdit).text == "00:01:30" and float(dialog.values["respawn_seconds"]) == 90.0,
		"Неверный ввод времени возвращает прежнее значение.",
	)
	_type(dialog.field_inputs["windup"], "0,5")
	_check((dialog.field_inputs["windup"] as LineEdit).text == "0.50", "Дробное число с запятой принимается.")
	_type(dialog.field_inputs["move_speed"], "1000")
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "400", "Введённое значение зажимается лимитом.")

	(dialog.field_inputs["move_speed"] as LineEdit).text = "100"
	(dialog.field_plus["move_speed"] as Button).pressed.emit()
	_check(
		(dialog.field_inputs["move_speed"] as LineEdit).text == "105",
		"Несохранённый текст в поле должен учитываться при нажатии «+».",
	)
	_dispose(dialog)


func _check_stats_and_level() -> void:
	var dialog := await _open_dialog("economy", _sample_settings())
	dialog.step_stat("strength", 1)
	(dialog.stat_plus["strength"] as Button).pressed.emit()
	_check(int(dialog.stats["strength"]) == 4, "Без свободных очков силу повысить нельзя.")
	dialog.step_stat("intuition", -1)
	_check(int(dialog.stats["intuition"]) == 9 and dialog.free_points() == 1, "Снятое очко становится свободным.")
	_check(
		_labels_text(dialog).contains("Свободных очков: 1 из 9") and not (dialog.stat_plus["strength"] as Button).disabled,
		"Появившееся свободное очко включает «+».",
	)
	(dialog.stat_plus["agility"] as Button).pressed.emit()
	_check(int(dialog.stats["agility"]) == 5 and dialog.free_points() == 0, "«+» тратит свободное очко.")
	(dialog.stat_minus["strength"] as Button).pressed.emit()
	_check(int(dialog.stats["strength"]) == 3 and (dialog.stat_minus["strength"] as Button).disabled, "«−» останавливается на минимуме 3.")
	dialog.step_stat("strength", -1)
	_check(int(dialog.stats["strength"]) == 3, "Ниже минимума характеристика не опускается.")
	dialog.step_stat("endurance", 1)
	dialog.set_stat_value("endurance", 99)
	_check(
		int(dialog.stats["endurance"]) == 6
		and (dialog.stat_plus["endurance"] as Button).disabled
		and (dialog.stat_minus["endurance"] as Button).disabled,
		"Выносливость задаётся только уровнем.",
	)
	_type(dialog.stat_inputs["intellect"], "50")
	_check(int(dialog.stats["intellect"]) == 4 and dialog.free_points() == 0, "Введённое значение ограничено свободными очками.")
	_type(dialog.stat_inputs["wisdom"], "abc")
	_check(int(dialog.stats["wisdom"]) == 3 and (dialog.stat_inputs["wisdom"] as LineEdit).text == "3", "Неверный ввод возвращает значение.")
	_dispose(dialog)

	dialog = await _open_dialog("economy", _sample_settings())
	(dialog.level_plus as Button).pressed.emit()
	_check(
		dialog.level == 4 and int(dialog.stats["endurance"]) == 7
		and _labels_text(dialog).contains("Свободных очков: 3 из 12")
		and _labels_text(dialog).contains("Выносливость задаётся уровнем: 7"),
		"Повышение уровня добавляет очки и выносливость.",
	)
	(dialog.level_minus as Button).pressed.emit()
	(dialog.level_minus as Button).pressed.emit()
	_check(
		dialog.level == 2 and int(dialog.stats["endurance"]) == 5
		and int(dialog.stats["intuition"]) == 7 and dialog.free_points() == 0
		and _labels_text(dialog).contains("Свободных очков: 0 из 6"),
		"Понижение уровня снимает лишние очки с последних характеристик. Получено: %s" % str(dialog.stats),
	)
	_type(dialog.level_input, "30")
	_check(
		dialog.level == 30 and int(dialog.stats["endurance"]) == 33 and dialog.total_points() == 90
		and (dialog.level_plus as Button).disabled,
		"Предельный уровень Economy — 30.",
	)
	_type(dialog.level_input, "99")
	_check(dialog.level == 30, "Уровень выше предела зажимается.")
	_type(dialog.level_input, "0")
	_check(
		dialog.level == 1 and int(dialog.stats["endurance"]) == 4 and (dialog.level_minus as Button).disabled
		and int(dialog.stats["intuition"]) == 4 and dialog.free_points() == 0,
		"Уровень не ниже 1, очки подрезаются. Получено: %s" % str(dialog.stats),
	)
	_type(dialog.level_input, "x")
	_check(dialog.level == 1 and dialog.level_input.text == "1", "Неверный уровень возвращает прежний.")
	_dispose(dialog)


func _check_deck_rules() -> void:
	var dialog := await _open_dialog(
		"deck",
		{"level": 1.0, "state": "neutral", "stats": {"strength": 4.0}},
		{"mode_name": "Deck"},
	)
	_check(dialog.stat_inputs.size() == 7 and dialog.stat_inputs.has("harmony"), "В Deck семь характеристик, включая гармонию.")
	_check(
		int(dialog.stats["strength"]) == 4 and int(dialog.stats["agility"]) == 2 and int(dialog.stats["endurance"]) == 2,
		"Минимум характеристики в Deck — 2. Получено: %s" % str(dialog.stats),
	)
	_check(dialog.total_points() == 6 and dialog.free_points() == 4, "На первом уровне Deck шесть очков.")
	_check(_labels_text(dialog).contains("режим «Deck»") and _labels_text(dialog).contains("Гармония"), "Подписи режима Deck.")
	dialog.set_level(99)
	_check(
		dialog.level == 10 and int(dialog.stats["endurance"]) == 11 and dialog.total_points() == 42
		and (dialog.level_plus as Button).disabled,
		"Предельный уровень Deck — 10, очков 6 + 4 за каждый уровень.",
	)
	_check(dialog.state == "neutral", "Состояние из настроек сохраняется.")
	_check(
		Rules.validate_settings(dialog.rules, dialog.collect_settings()) == "",
		"Настройки Deck должны проходить клиентскую проверку.",
	)
	_dispose(dialog)


func _check_states_and_patrol() -> void:
	var dialog := await _open_dialog("economy", _sample_settings())
	(dialog.state_buttons["neutral"] as Button).pressed.emit()
	_check(
		dialog.state == "neutral" and _labels_text(dialog).contains(str(Rules.STATE_HINTS["neutral"]))
		and (dialog.state_buttons["neutral"] as Button).has_theme_stylebox_override("normal")
		and not (dialog.state_buttons["aggressive"] as Button).has_theme_stylebox_override("normal"),
		"Выбор состояния меняет подсветку и подсказку.",
	)
	dialog.set_state("bogus")
	_check(dialog.state == "neutral", "Неизвестное состояние игнорируется.")

	var grid = dialog.patrol_grid
	_find_button(dialog, "Круг 3").pressed.emit()
	_check(grid.cell_count() == 29, "Круг 3 содержит 29 клеток, получено %d." % grid.cell_count())
	_check(_labels_text(dialog).contains("клеток: 29 ·"), "Счётчик патруля обновляется после пресета.")
	_find_button(dialog, "Круг 6").pressed.emit()
	_check(grid.cell_count() == 113, "Круг 6 содержит 113 клеток, получено %d." % grid.cell_count())
	_find_button(dialog, "Очистить").pressed.emit()
	_check(grid.cell_count() == 0 and _labels_text(dialog).contains("клеток: 0 ·"), "Кнопка «Очистить» стирает патруль.")

	_mouse_button(_cell_center(grid, Vector2i(9, 9)), MOUSE_BUTTON_LEFT, true)
	_mouse_button(_cell_center(grid, Vector2i(9, 9)), MOUSE_BUTTON_LEFT, false)
	_check(grid.cells.has(Vector2i(9, 9)) and grid.cell_count() == 1, "ЛКМ закрашивает клетку.")
	_check(_labels_text(dialog).contains("клеток: 1 ·"), "Счётчик патруля обновляется после рисования.")
	_mouse_button(_cell_center(grid, Vector2i(9, 9)), MOUSE_BUTTON_RIGHT, true)
	_mouse_button(_cell_center(grid, Vector2i(9, 9)), MOUSE_BUTTON_RIGHT, false)
	_check(grid.cell_count() == 0, "ПКМ стирает клетку.")

	_mouse_button(_cell_center(grid, Vector2i(2, 2)), MOUSE_BUTTON_LEFT, true)
	_mouse_move(_cell_center(grid, Vector2i(6, 2)), MOUSE_BUTTON_MASK_LEFT)
	_mouse_button(_cell_center(grid, Vector2i(6, 2)), MOUSE_BUTTON_LEFT, false)
	_check(
		grid.offsets() == [[-7, -7], [-6, -7], [-5, -7], [-4, -7], [-3, -7]],
		"Протягивание ЛКМ закрашивает ряд клеток. Получено: %s" % str(grid.offsets()),
	)
	_mouse_button(_cell_center(grid, Vector2i(0, 17)), MOUSE_BUTTON_LEFT, true)
	_mouse_move(_cell_center(grid, Vector2i(5, 12)), MOUSE_BUTTON_MASK_LEFT)
	_mouse_button(_cell_center(grid, Vector2i(5, 12)), MOUSE_BUTTON_LEFT, false)
	_check(grid.cell_count() == 5 + 6, "Быстрое движение мыши не оставляет пропусков в линии.")
	_mouse_button(_cell_center(grid, Vector2i(4, 2)), MOUSE_BUTTON_RIGHT, true)
	_mouse_move(_cell_center(grid, Vector2i(5, 2)), MOUSE_BUTTON_MASK_RIGHT)
	_mouse_button(_cell_center(grid, Vector2i(5, 2)), MOUSE_BUTTON_RIGHT, false)
	_check(
		not grid.cells.has(Vector2i(4, 2)) and not grid.cells.has(Vector2i(5, 2)) and grid.cells.has(Vector2i(3, 2)),
		"Протягивание ПКМ стирает клетки.",
	)
	_dispose(dialog)


func _screen_size() -> Vector2:
	return Vector2(
		float(ProjectSettings.get_setting("display/window/size/viewport_width")),
		float(ProjectSettings.get_setting("display/window/size/viewport_height")),
	)


func _check_layout_with_notes() -> void:
	var screen := _screen_size()
	for mode in ["economy", "deck", "front_line"]:
		var dialog := await _open_dialog(mode, _sample_settings(), {
			"mode_name": mode,
			"note": NOTE + ". " + NOTE + ". " + NOTE,
			"integration_note": "Профиль сохранится на сервере, но этот LPC-набор пока не подключён к игровому NPC-каталогу.",
			"equipment_items": [],
		})
		_check(
			dialog.panel.size.y <= screen.y - 24.0 and dialog.panel.size.x <= screen.x - 24.0,
			"Режим %s: панель с заметками %s не помещается на экран %s с запасом." % [mode, str(dialog.panel.size), str(screen)],
		)
		var panel_rect: Rect2 = dialog.panel.get_global_rect()
		_check(
			dialog.patrol_grid.get_global_rect().end.y <= panel_rect.end.y
			and dialog.save_button.get_global_rect().end.y <= panel_rect.end.y,
			"Режим %s: сетка патруля и кнопка сохранения должны лежать внутри панели." % mode,
		)
		_dispose(dialog)


func _check_collected_settings() -> void:
	var settings := _sample_settings()
	settings["patrol"] = [[1.0, 2.0], [-9.0, -9.0], [0.0, 0.0], [8.0, 8.0], [-3.0, 2.0]]
	var dialog := await _open_dialog("economy", settings, {"equipment_items": _sample_items()})
	var result: Dictionary = dialog.collect_settings()
	_check(
		typeof(result["respawn_seconds"]) == TYPE_INT and typeof(result["reward_copper"]) == TYPE_INT
		and typeof(result["reward_xp"]) == TYPE_INT and typeof(result["level"]) == TYPE_INT,
		"Респаун, награды и уровень уходят на сервер целыми числами.",
	)
	_check(
		float(result["move_speed"]) == 210.0 and float(result["windup"]) == 0.44 and float(result["aggro_tiles"]) == 3.5,
		"Дробные параметры сохраняются без искажений.",
	)
	var stats: Dictionary = result["stats"]
	var all_int := true
	for stat in stats:
		all_int = all_int and typeof(stats[stat]) == TYPE_INT
	_check(
		all_int and stats.size() == 6 and int(stats["intuition"]) == 10,
		"Характеристики уходят целыми числами. Получено: %s" % str(stats),
	)
	_check(
		(result["equipment"] as Dictionary).keys() == Rules.EQUIPMENT_SLOTS,
		"Экипировка содержит все 13 слотов в порядке сервера.",
	)
	_check(
		result["patrol"] == [[-9, -9], [0, 0], [-3, 2], [1, 2], [8, 8]],
		"Патруль отсортирован по (y, x) и содержит целые числа. Получено: %s" % str(result["patrol"]),
	)
	_check(Rules.validate_settings(dialog.rules, result) == "", "Собранные настройки проходят клиентскую проверку.")
	var encoded := JSON.stringify(result)
	_check(
		encoded.contains("\"respawn_seconds\":30,") and encoded.contains("\"level\":3"),
		"В JSON целые поля не превращаются в дробные: %s" % encoded,
	)

	saved.clear()
	dialog.save_button.pressed.emit()
	_check(saved.size() == 1 and saved[0] == result, "Кнопка сохранения отправляет собранные настройки.")
	dialog.set_busy(true)
	_check(
		dialog.save_button.disabled and dialog.message_text().contains("Сохраняем"),
		"Во время сохранения кнопка блокируется и показывается сообщение.",
	)
	dialog.set_busy(false)
	_check(not dialog.save_button.disabled, "После ответа сервера кнопка снова доступна.")

	cancelled = 0
	dialog.cancel_button.pressed.emit()
	_check(cancelled == 1, "Кнопка «Отмена» просит закрыть окно.")
	_dispose(dialog)


func _check_equipment_without_list() -> void:
	var settings := _sample_settings()
	settings["equipment"] = {"body": 999.0}
	var dialog := await _open_dialog("economy", settings, {"note": NOTE})
	var panel = dialog.equipment_panel
	_check(not panel.visible, "Окно экипировки закрыто, пока его не открыли.")
	_check(panel.equipped_count() == 1, "В настройках надет один предмет.")
	_find_button(dialog, "Открыть экипировку").pressed.emit()
	_check(panel.visible and panel.slot_buttons.size() == 13, "Кнопка открывает куклу из 13 слотов.")
	_check(panel._slot_values["body"].text == "предмет #999", "Предмет вне списка показывается как «предмет #N».")
	panel.open_slot("head")
	_check(
		panel.picker_slot == "head" and panel._picker_layer.visible and panel._manual_row.visible
		and not panel._picker_scroll.visible,
		"Без списка предметов вместо выбора показывается ввод ID.",
	)
	panel._manual_input.text = "abc"
	panel.apply_manual_id()
	_check(panel.equipment["head"] == null and panel.picker_slot == "head", "Нечисловой ID не применяется.")
	panel._manual_input.text = "0"
	panel.apply_manual_id()
	_check(panel.equipment["head"] == null and panel.picker_slot == "head", "Нулевой ID не применяется.")
	panel._manual_input.text = "123"
	panel.apply_manual_id()
	_check(
		int(panel.equipment["head"]) == 123 and panel.picker_slot == "" and not panel._picker_layer.visible,
		"Корректный ID надевается и закрывает выбор.",
	)
	_check(panel._slot_values["head"].text == "предмет #123", "Ячейка показывает надетый ID.")
	panel.open_slot("head")
	_check(panel._manual_input.text == "123", "Поле ID заполнено текущим значением.")
	_find_button(panel, "Снять").pressed.emit()
	_check(panel.equipment["head"] == null and panel.picker_slot == "", "Кнопка «Снять» очищает слот.")
	panel.open_slot("weapon")
	_mouse_button(Vector2(5, 5), MOUSE_BUTTON_LEFT, true)
	_mouse_button(Vector2(5, 5), MOUSE_BUTTON_LEFT, false)
	_check(panel.picker_slot == "", "Клик вне списка закрывает выбор.")
	panel.open_slot("weapon")
	_mouse_button(Vector2(600, 300), MOUSE_BUTTON_RIGHT, true)
	_mouse_button(Vector2(600, 300), MOUSE_BUTTON_RIGHT, false)
	_check(panel.picker_slot == "" and panel.visible, "ПКМ закрывает только список, а не окно.")
	_find_button(panel, "Готово").pressed.emit()
	_check(not panel.visible and _labels_text(dialog).contains("надето: 1 из 13"), "«Готово» закрывает окно и обновляет счётчик.")

	saved.clear()
	dialog.request_save()
	_check(
		saved.size() == 1 and int(saved[0]["equipment"]["body"]) == 999 and dialog.dropped_equipment_count == 0,
		"Предмет вне списка сохраняется для проверки сервером.",
	)
	_dispose(dialog)


func _check_equipment_with_list() -> void:
	var settings := _sample_settings()
	settings["equipment"] = {"body": 999.0}
	var dialog := await _open_dialog("economy", settings, {"equipment_items": _sample_items()})
	var panel = dialog.equipment_panel
	dialog.open_equipment()
	_check(panel.slot_items("head").size() == 3, "В слоте головы три предмета.")
	_check(
		panel.option_ids("head") == [null, 11] and panel.hidden_count("head") == 2,
		"Список головы: только Шлем новичка, два предмета скрыты. Получено: %s" % str(panel.option_ids("head")),
	)
	panel.open_slot("head")
	_check(
		panel.option_buttons.size() == 2 and not panel._manual_row.visible and panel._picker_scroll.visible
		and panel._picker_info.text.contains("скрыто по требованиям: 2"),
		"Список показывает пустой вариант и подходящий предмет.",
	)
	panel.option_buttons[1].pressed.emit()
	_check(int(panel.equipment["head"]) == 11 and panel.picker_slot == "", "Клик по предмету надевает его.")
	_check(panel._slot_values["head"].text == "Шлем новичка", "Ячейка показывает имя предмета.")

	_check(panel.option_ids("ring") == [null, 21, 22] and panel.slot_items("ring_2").size() == 2, "Кольца берутся из слота ring.")
	panel.pick("ring", 21)
	_check(panel.option_ids("ring_2") == [null, 22], "Одно кольцо нельзя надеть дважды.")
	_check(panel.option_ids("ring") == [null, 21, 22], "Свой предмет остаётся в списке слота.")
	panel.open_slot("ring_2")
	_check(panel.option_buttons.size() == 2, "Во втором кольце на одно предложение меньше.")
	panel.close_picker()

	panel.pick("head", 12)
	panel.pick("weapon", 31)
	saved.clear()
	dialog.request_save()
	_check(
		saved.size() == 1 and saved[0]["equipment"]["head"] == null and int(saved[0]["equipment"]["weapon"]) == 31
		and int(saved[0]["equipment"]["body"]) == 999 and dialog.dropped_equipment_count == 1,
		"Неподходящий шлем снимается при сохранении, остальное остаётся. Получено: %s" % str(saved),
	)
	_check(_labels_text(dialog).contains("надето: 3 из 13"), "Счётчик экипировки после снятия: 3 из 13.")
	dialog.set_level(1)
	saved.clear()
	dialog.request_save()
	_check(
		saved.size() == 1 and saved[0]["equipment"]["weapon"] == null and dialog.dropped_equipment_count == 1,
		"После понижения уровня меч снимается при сохранении.",
	)
	_dispose(dialog)


func _check_keyboard_and_wheel() -> void:
	var dialog := await _open_dialog("economy", _sample_settings(), {"equipment_items": _sample_items()})
	var panel = dialog.equipment_panel
	var row: Control = dialog.field_rows["move_speed"]
	_mouse_button(row.get_global_rect().get_center(), MOUSE_BUTTON_WHEEL_UP, true)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "215", "Колесо вверх над строкой увеличивает значение.")
	_mouse_button(row.get_global_rect().get_center(), MOUSE_BUTTON_WHEEL_DOWN, true)
	_mouse_button(row.get_global_rect().get_center(), MOUSE_BUTTON_WHEEL_DOWN, true)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "205", "Колесо вниз уменьшает значение.")
	_mouse_button(Vector2(2, 2), MOUSE_BUTTON_WHEEL_UP, true)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "205", "Колесо вне строк ничего не меняет.")
	(dialog.field_inputs["windup"] as LineEdit).text = "1.00"
	_mouse_button((dialog.field_rows["move_speed"] as Control).get_global_rect().get_center(), MOUSE_BUTTON_WHEEL_UP, true)
	_check((dialog.field_inputs["windup"] as LineEdit).text == "1.00" and dialog.values["windup"] == 1.0, "Колесо сохраняет набранный текст соседних полей.")
	dialog.open_equipment()
	_mouse_button(row.get_global_rect().get_center(), MOUSE_BUTTON_WHEEL_UP, true)
	_check((dialog.field_inputs["move_speed"] as LineEdit).text == "210", "Колесо не работает под окном экипировки.")

	panel.open_slot("head")
	cancelled = 0
	_press_escape()
	_check(panel.picker_slot == "" and panel.visible and cancelled == 0, "Первый Esc закрывает список предметов.")
	_press_escape()
	_check(not panel.visible and cancelled == 0, "Второй Esc закрывает окно экипировки.")
	_press_escape()
	_check(cancelled == 1, "Третий Esc отменяет изменения.")
	_dispose(dialog)


func _check_editor_integration() -> void:
	var editor := ProfileEditor.new()
	editor.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(editor)
	await get_tree().process_frame
	editor._animal_groups_by_key = {
		"goblin": {"name": "Гоблин", "kind": "mob", "profile_kind": "goblin"},
		"imp": {"name": "Бес", "kind": "mob", "profile_kind": "npc_imp"},
	}
	_check(
		editor._mob_equipment_path() == "/api/items/equipment?slots=head,ears,neck,back,body,hands,belt,legs,feet,weapon,shield,ring",
		"Запрос экипировки содержит 12 уникальных слотов. Получено: %s" % editor._mob_equipment_path(),
	)

	editor._load_mob_profile("goblin")
	_check(
		editor._pending_mob_profile_key == "goblin" and editor._pending_action == "mob_profile_load",
		"Открытие настроек начинает загрузку профиля.",
	)
	editor._on_api_completed(true, {"settings": _sample_settings()})
	_check(
		editor._pending_action == "mob_equipment_items" and not is_instance_valid(editor._mob_profile_dialog),
		"После профиля запрашивается список экипировки, окно ещё не открыто.",
	)
	editor._on_api_completed(false, "Маршрут не найден")
	var dialog: Control = editor._mob_profile_dialog
	if not _check(is_instance_valid(dialog), "Без списка экипировки окно всё равно открывается."):
		editor.free()
		return
	_check(
		dialog.mode == "economy" and dialog.message_text().contains("Экипировка не загружена")
		and not dialog.equipment_panel._items_loaded,
		"Без списка окно показывает заметку и ручной ввод ID.",
	)
	_check(
		_labels_text(dialog).contains("не подключён к игровому NPC-каталогу") and editor.get_child(editor.get_child_count() - 1) == dialog,
		"Для LPC-набора показана заметка об интеграции, окно поверх редактора.",
	)

	editor._pending_mob_profile_key = "goblin"
	editor._pending_mob_profile_kind = "goblin"
	editor._pending_mob_profile_settings = _sample_settings()
	editor._pending_action = "mob_equipment_items"
	editor._on_api_completed(true, {"items": _sample_items()})
	var reopened: Control = editor._mob_profile_dialog
	_check(
		is_instance_valid(reopened) and reopened != dialog and dialog.is_queued_for_deletion()
		and reopened.equipment_panel._items_loaded and reopened.message_text() == "",
		"Со списком предметов окно открывается без заметки и заменяет прежнее.",
	)
	await get_tree().process_frame

	reopened.request_save()
	_check(
		editor._pending_action == "mob_profile_save" and reopened.save_button.disabled
		and editor._status.text.contains("Сохраняем профиль моба"),
		"Сохранение блокирует кнопку и ставит запрос на сервер.",
	)
	editor._on_api_completed(false, "Уровень вне допустимого диапазона")
	_check(
		is_instance_valid(editor._mob_profile_dialog) and not reopened.save_button.disabled
		and reopened.message_text() == "Уровень вне допустимого диапазона"
		and editor._status.text.begins_with("Не удалось сохранить настройки моба:")
		and editor._pending_mob_profile_key == "goblin",
		"Ошибка сервера показывается в окне, окно не закрывается.",
	)
	reopened.request_save()
	editor._on_api_completed(true, {"settings": {}})
	_check(
		editor._mob_profile_dialog == null and reopened.is_queued_for_deletion()
		and editor._pending_mob_profile_key == "" and editor._status.text == SAVED_TEXT,
		"Успешное сохранение закрывает окно. Статус: %s" % editor._status.text,
	)
	await get_tree().process_frame

	editor._pending_mob_profile_key = "imp"
	editor._pending_mob_profile_kind = "npc_imp"
	var imp_settings := _sample_settings()
	imp_settings["equipment"] = {"head": 12.0}
	editor._pending_mob_profile_settings = imp_settings
	editor._pending_action = "mob_equipment_items"
	editor._on_api_completed(true, {"items": _sample_items()})
	var imp_dialog: Control = editor._mob_profile_dialog
	_check(
		is_instance_valid(imp_dialog) and not _labels_text(imp_dialog).contains("не подключён к игровому NPC-каталогу"),
		"Для обычного моба заметки об интеграции нет.",
	)
	imp_dialog.request_save()
	editor._on_api_completed(true, {"settings": {}})
	_check(
		editor._status.text == SAVED_TEXT + " Снято предметов, не подходящих по требованиям: 1.",
		"В статусе сообщается о снятых предметах. Статус: %s" % editor._status.text,
	)
	await get_tree().process_frame

	editor._pending_mob_profile_key = "goblin"
	editor._pending_mob_profile_kind = "goblin"
	editor._pending_mob_profile_settings = _sample_settings()
	editor._show_pending_mob_profile(null)
	var cancel_dialog: Control = editor._mob_profile_dialog
	_check(is_instance_valid(cancel_dialog), "Окно открывается повторно.")
	cancel_dialog.cancel_button.pressed.emit()
	_check(
		editor._mob_profile_dialog == null and cancel_dialog.is_queued_for_deletion()
		and editor._pending_mob_profile_key == "" and editor._status.text == "Изменения профиля моба отменены.",
		"Отмена закрывает окно и сбрасывает ожидание.",
	)
	await get_tree().process_frame

	editor._pending_mob_profile_key = "ghost"
	editor._show_mob_profile("ghost", {}, [])
	_check(
		editor._mob_profile_dialog == null and editor._status.text == "Моб больше не найден в палитре."
		and editor._pending_mob_profile_key == "",
		"Если моб пропал из палитры, окно не открывается.",
	)

	editor._pending_mob_profile_key = "goblin"
	editor._pending_action = "mob_profile_load"
	editor._on_api_completed(true, {"settings": "не словарь"})
	_check(
		editor._mob_profile_dialog == null and editor._pending_mob_profile_key == "",
		"Неверный формат профиля сбрасывает ожидание.",
	)
	editor._pending_mob_profile_key = "goblin"
	editor._pending_action = "mob_profile_load"
	editor._on_api_completed(false, "Нет доступа")
	_check(editor._pending_mob_profile_key == "" and editor._status.text == "Нет доступа", "Ошибка загрузки профиля сбрасывает ожидание.")
	editor.free()
