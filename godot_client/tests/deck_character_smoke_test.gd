extends Node

const RULES := preload("res://scripts/deck_character_rules.gd")
const CARD_SCRIPT := preload("res://scripts/deck_character_card.gd")
const COMPARISON_SCRIPT := preload("res://scripts/deck_character_comparison.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_character_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_rules(samples)
		await _check_card(samples["profiles"]["warrior"]["input"])
		await _check_comparison(samples["profiles"]["warrior"]["input"], samples["profiles"]["archer"]["input"])
		await _check_deck_wiring(samples["profiles"]["warrior"]["input"])
	else:
		_check(false, "файл эталона читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_character_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_rules(samples: Dictionary) -> void:
	var profiles: Dictionary = samples["profiles"]
	for name in profiles:
		var entry: Dictionary = profiles[name]
		var input: Dictionary = entry["input"]
		var normalized := RULES.normalize_profile(input)
		var snapshot: Dictionary = entry["normalized"]
		for key in ["type", "profession_type", "level", "hp", "max_hp", "mp", "max_mp", "stat_points", "max_hp_includes_equipment"]:
			_check(_same(normalized.get(key), snapshot.get(key)), "нормализация %s: %s" % [name, key])
		_check(_same(normalized["stats"], snapshot["stats"]), "нормализация %s: характеристики" % name)
		_check(_same(RULES.effective_stats(normalized), entry["effective"]), "эффективные характеристики %s" % name)
		var hp := RULES.displayed_hp(normalized)
		_check(_same([hp.x, hp.y], entry["hp_display"]), "HP для отображения %s" % name)
		_check(_same(RULES.derived_values(normalized), entry["derived"]), "производные значения %s" % name)
		for opponent in entry["derived_with"]:
			var expected: Dictionary = entry["derived_with"][opponent]
			_check(_same(RULES.derived_values(normalized, profiles[opponent]["input"]), expected), "производные %s против %s" % [name, opponent])
		_check(RULES.is_mage_profile(input) == bool(entry["is_mage"]), "is_mage %s" % name)
		_check(RULES.is_warrior_profile(input) == bool(entry["is_warrior"]), "is_warrior %s" % name)
	for case in samples["adjust_warrior"]:
		var label := "правка по правилам Deck: %s %s %+d" % [case["profile"], case["stat"], int(case["delta"])]
		var profile := RULES.normalize_profile(profiles[case["profile"]]["input"])
		var ok := RULES.adjust_profile_stat(profile, str(case["stat"]), int(case["delta"]))
		_check(ok == bool(case["ok"]), label + ": результат")
		_check(_same(profile["stats"], case["stats"]), label + ": характеристики")
		_check(int(profile["stat_points"]) == int(case["stat_points"]), label + ": очки")
		_check(int(profile["hp"]) == int(case["hp"]) and int(profile["max_hp"]) == int(case["max_hp"]), label + ": HP")
	for case in samples["adjust_mage"]:
		var label := "правка по правилам мага: %s %s %+d" % [case["profile"], case["stat"], int(case["delta"])]
		var result := RULES.comparison_adjust(profiles[case["profile"]]["input"], str(case["stat"]), int(case["delta"]))
		_check(result.is_empty() != bool(case["ok"]), label + ": результат")
		if not result.is_empty():
			_check(_same(result["stats"], case["stats"]), label + ": характеристики")
			_check(int(result["stat_points"]) == int(case["stat_points"]), label + ": очки")
			_check(int(result["mp"]) == int(case["mp"]) and int(result["max_mp"]) == int(case["max_mp"]), label + ": мана")
	for level in samples["xp"]:
		_check(RULES.xp_to_next(int(level)) == int(samples["xp"][level]), "опыт до следующего уровня: %s" % level)
	for record in samples["tooltips"]:
		var item: Dictionary = record["item"]
		_check(_same(_plain_lines(RULES.equipment_tooltip_lines(item)), record["lines"]), "подсказка предмета: %s" % str(item.get("name", "?")))
	var plain_warrior := RULES.comparison_adjust({"type": "warrior", "level": 5, "stats": {"strength": 5, "agility": 4, "intuition": 3, "endurance": 6}, "stat_points": 3, "hp": 100, "max_hp": 120}, "strength", 1)
	_check(not plain_warrior.is_empty() and int(plain_warrior["stats"]["strength"]) == 6, "воин без магических статов правится по правилам Deck")
	_check(RULES.comparison_adjust({"type": "warrior", "level": 5, "stats": {"strength": 2}, "stat_points": 3}, "strength", -1).is_empty(), "характеристика не ниже минимума")


func _check_card(warrior: Dictionary) -> void:
	var card = CARD_SCRIPT.new()
	var clicks: Array = []
	card.stat_requested.connect(func(stat_name: String, delta: int) -> void: clicks.append([stat_name, delta]))
	add_child(card)
	await get_tree().process_frame
	var profile := RULES.normalize_profile(warrior, "ИГРОК", "player")
	card.set_profile(profile, "ИГРОК", Color8(80, 180, 120), true, null)
	_check(card._xp_label.text == "XP: 120/350", "карточка: XP до следующего уровня")
	_check(card._hp_label.text == "HP: 100/135", "карточка: HP с бонусом экипировки")
	_check(card._mp_label.text == "MP: 10/10", "карточка: мана")
	_check(card._coins_label.text == "Монеты: 1234", "карточка: монеты")
	_check(card._stat_labels["strength"].text == "Сила: 7", "карточка: сила с бонусом экипировки")
	_check(card._derived_labels["strength"].text == "Урон: 10-14", "карточка: урон от силы и оружия")
	_check(card._derived_labels["agility"].text == "Уворот: 12%", "карточка: уворот")
	_check(card._derived_labels["intuition"].text == "Крит: 5% × 165%", "карточка: крит")
	_check(card._stat_points_label.text == "Свободные очки: 3", "карточка: свободные очки")
	_check(card._slot_cells["weapon"]["item"].text == "Меч", "карточка: оружие в слоте")
	_check(card._slot_cells["head"]["item"].text == "—", "карточка: пустой слот")
	_check(card._stat_controls["strength"].visible, "карточка: свой персонаж правится")
	card._stat_plus["strength"].pressed.emit()
	_check(clicks == [["strength", 1]], "карточка: плюс отправляет правку характеристики")
	await get_tree().process_frame
	var weapon_panel: Control = card._slot_cells["weapon"]["panel"]
	var hovered: Dictionary = card.slot_item_at(weapon_panel.get_global_rect().get_center())
	_check(str(hovered.get("name", "")) == "Меч", "карточка: наведение на оружие находит предмет")
	_check(card.slot_item_at(Vector2(-100, -100)).is_empty(), "карточка: вне слотов предмета нет")
	card.set_profile(profile, "ПРОТИВНИК", Color8(210, 100, 90), false, null)
	_check(not card._stat_controls["strength"].visible, "карточка: соперника не правят")
	card.queue_free()
	await get_tree().process_frame


func _check_comparison(player: Dictionary, opponent: Dictionary) -> void:
	var modal = COMPARISON_SCRIPT.new()
	var challenges := [0]
	var stat_requests: Array = []
	modal.challenge_requested.connect(func() -> void: challenges[0] += 1)
	modal.stat_requested.connect(func(stat_name: String, delta: int) -> void: stat_requests.append([stat_name, delta]))
	add_child(modal)
	await get_tree().process_frame
	_check(not modal.visible, "окно сравнения скрыто по умолчанию")
	modal.open(player, opponent)
	_check(modal.visible, "окно сравнения открывается")
	_check(modal._player_card._name_label.text == str(player["name"]), "окно сравнения: слева персонаж игрока")
	_check(modal._opponent_card._name_label.text == str(opponent["name"]), "окно сравнения: справа соперник")
	modal._player_card._stat_plus["strength"].pressed.emit()
	_check(stat_requests == [["strength", 1]], "окно сравнения: правка персонажа игрока передаётся наверх")
	_check(not modal._opponent_card._stat_controls["strength"].visible, "окно сравнения: у соперника правки нет")
	modal._challenge_button.pressed.emit()
	_check(challenges[0] == 1, "окно сравнения: БРОСИТЬ ВЫЗОВ отправляет сигнал")
	modal.set_status("Ошибка", true)
	_check(modal._status.text == "Ошибка", "окно сравнения: строка статуса")
	modal._close_button.pressed.emit()
	_check(not modal.visible, "окно сравнения: ЗАКРЫТЬ скрывает окно")
	modal.open(player, opponent)
	_check(modal.visible, "окно сравнения открывается повторно для проверок")
	modal.free()
	await get_tree().process_frame


func _check_deck_wiring(player: Dictionary) -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = player.duplicate(true)
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)

	deck._view = "backyard"
	deck._social_data = {
		"occupants": [{"character_id": 7, "name": "Соперник", "level": 3, "hp": 40, "max_hp": 60, "stats": {"strength": 4}}],
		"offers": [
			{"id": "offer-7", "sender_id": "7", "sender": "Соперник"},
			{"id": "offer-9", "sender_id": "9", "sender": "Неизвестный"},
		],
		"my_application": null,
	}
	deck._render_social()
	var compare_button := _find_button(deck._list, "Сравнить")
	_check(compare_button != null, "заявки на бой: есть кнопка «Сравнить»")
	compare_button.pressed.emit()
	_check(deck._comparison.visible, "кнопка «Сравнить» открывает окно сравнения")
	_check(str(deck._comparison_offer.get("id", "")) == "offer-7", "окно сравнения запомнило заявку")
	_check(deck._comparison._opponent_card._name_label.text == "Соперник", "соперник взят из списка игроков рядом")
	_check(deck._comparison._status.text == "Загружаем снаряжение…", "окно сравнения: загрузка снаряжения")
	await _wait_idle(deck)
	_check(deck._comparison._status.text != "Загружаем снаряжение…", "окно сравнения: ошибка загрузки показана в окне")

	deck._social_data["my_application"] = {"id": "mine", "status": "waiting"}
	deck._comparison._challenge_button.pressed.emit()
	_check(deck._comparison._status.text == "Пока активна ваша заявка, бросить вызов нельзя", "вызов запрещён при своей активной заявке")
	_check(deck._pending_action.is_empty(), "запрещённый вызов не отправляет запрос")
	deck._social_data["my_application"] = null

	deck._on_comparison_stat_requested("strength", 1)
	_check(deck._pending_action == "comparison_save", "правка характеристики сохраняется на сервере")
	await _wait_idle(deck)

	deck._pending_action = "comparison_inventory"
	deck._on_api_completed(true, {
		"equipment": {"head": {"name": "Шлем", "bonuses": {"endurance": 1}, "weight": 1.0}},
		"bonuses": {"endurance": 1},
	})
	_check(deck._comparison._player_card._slot_cells["head"]["item"].text == "Шлем", "снаряжение из инвентаря показано в окне")

	deck._pending_action = "comparison_save"
	deck._on_api_completed(true, {"character": {
		"id": 1, "name": "Боец", "type": "warrior", "level": 5, "xp": 120, "hp": 100, "max_hp": 120,
		"mp": 10, "max_mp": 10, "stat_points": 2, "coins": 1234,
		"stats": {"strength": 6, "agility": 4, "intuition": 3, "wisdom": 2, "intellect": 2, "harmony": 2, "endurance": 6},
	}})
	_check(int(GameSession.character["stats"]["strength"]) == 6, "сохранение: новые характеристики записаны в сессию")
	_check(GameSession.character.get("equipment", {}).has("head"), "сохранение: экипировка из инвентаря не теряется в ответе сервера")
	_check(deck._comparison._player_card._stat_points_label.text == "Свободные очки: 2", "сохранение: окно обновлено")
	_check(deck._comparison._status.text == "Характеристики сохранены.", "сохранение: статус в окне")

	deck._pending_action = "comparison_challenge"
	deck._on_api_completed(true, {"offer": {"id": "offer-7", "status": "pending"}})
	_check(deck._comparison.visible, "ответ «не принято» оставляет окно открытым")
	_check(deck._comparison._status.text == "Ответ на заявку отправлен.", "ответ на вызов показан в окне")
	deck.queue_free()
	await get_tree().process_frame


func _wait_idle(deck) -> void:
	var waited := 0
	while not deck._pending_action.is_empty() and waited < 240:
		await get_tree().process_frame
		waited += 1
	await get_tree().process_frame


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _plain_lines(lines: Array) -> Array:
	var result := []
	for line in lines:
		var color: Color = line[1]
		result.append([str(line[0]), [roundi(color.r * 255.0), roundi(color.g * 255.0), roundi(color.b * 255.0)]])
	return result


func _same(a: Variant, b: Variant) -> bool:
	if typeof(a) == TYPE_DICTIONARY and typeof(b) == TYPE_DICTIONARY:
		if a.size() != b.size():
			return false
		for key in a:
			if not b.has(key) or not _same(a[key], b[key]):
				return false
		return true
	if typeof(a) == TYPE_ARRAY and typeof(b) == TYPE_ARRAY:
		if a.size() != b.size():
			return false
		for index in range(a.size()):
			if not _same(a[index], b[index]):
				return false
		return true
	var a_number := typeof(a) == TYPE_INT or typeof(a) == TYPE_FLOAT
	var b_number := typeof(b) == TYPE_INT or typeof(b) == TYPE_FLOAT
	if a_number and b_number:
		return is_equal_approx(float(a), float(b))
	return a == b


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
