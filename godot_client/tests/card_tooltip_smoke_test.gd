extends Node

const RULES := preload("res://scripts/card_tooltip_rules.gd")
const TOOLTIP_SCRIPT := preload("res://scripts/card_tooltip.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SCENE_TRANSITION := preload("res://scripts/scene_transition.gd")
const SAMPLES_PATH := "res://tests/card_tooltip_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"
const BATTLE_FIXTURE := "res://tests/fixtures/deck_battle/planning_hand.json"
const SECTIONS := ["rules", "samples", "tooltip_widget", "deck_hover", "battle_hover"]

var _failures: Array[String] = []
var _checks := 0
var _finished_sections: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	var samples := _load_samples()
	_check_samples(samples)
	await _check_tooltip_widget(samples[0]["card"])
	await _check_deck_hover(samples[0]["card"], samples[1]["card"])
	for section in SECTIONS:
		_check(_finished_sections.has(section), "раздел «%s» выполнен до конца" % section)
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("card_tooltip_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_rules() -> void:
	_check(RULES.format_coins(0) == "0 монет", "ноль монет")
	_check(RULES.format_coins(1) == "1 монета", "одна монета")
	_check(RULES.format_coins(2) == "2 монеты", "две монеты")
	_check(RULES.format_coins(5) == "5 монет", "пять монет")
	_check(RULES.format_coins(11) == "11 монет", "одиннадцать монет")
	_check(RULES.format_coins(21) == "21 монета", "двадцать одна монета")
	_check(RULES.format_coins(22) == "22 монеты", "двадцать две монеты")
	_check(RULES.format_coins(700) == "700 монет", "700 монет")
	_check(RULES.rarity_label("epic") == "Эпическая", "подпись эпической редкости")
	_check(RULES.rarity_label("unknown") == "—", "неизвестная редкость без подписи")
	var screen := Vector2(1280, 720)
	var box := Vector2(420, 200)
	_check(RULES.tooltip_position(Vector2(100, 100), box, screen) == Vector2(116, 116), "подсказка у курсора")
	_check(RULES.tooltip_position(Vector2(1000, 100), box, screen) == Vector2(564, 116), "подсказка переворачивается у правого края")
	_check(RULES.tooltip_position(Vector2(100, 700), box, screen) == Vector2(116, 514), "подсказка поднимается у нижнего края")
	_check(RULES.tooltip_position(Vector2(-50, -50), box, screen) == Vector2(6, 6), "подсказка не уходит за левый верхний край")
	_finished_sections.append("rules")


func _load_samples() -> Array:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if not parsed is Array or parsed.is_empty():
		_check(false, "файл эталонных карт читается")
		return [{"card": {}, "lines": []}, {"card": {}, "lines": []}]
	return parsed


func _check_samples(samples: Array) -> void:
	_check(samples.size() == 18, "эталон содержит 18 карт Python-клиента")
	for record in samples:
		var card: Dictionary = record["card"]
		var expected: Array = record["lines"]
		var got := RULES.tooltip_lines(card)
		var same := got.size() == expected.size()
		if same:
			for index in range(expected.size()):
				if str(got[index]) != str(expected[index]):
					same = false
		_check(same, "строки подсказки совпадают с Python: %s" % str(card.get("key", "?")))
	_finished_sections.append("samples")


func _check_tooltip_widget(card: Dictionary) -> void:
	var tooltip = TOOLTIP_SCRIPT.new()
	add_child(tooltip)
	await get_tree().process_frame
	_check(not tooltip.visible, "подсказка скрыта по умолчанию")
	tooltip.show_card(card)
	_check(tooltip.visible, "подсказка показывается")
	_check(tooltip._title.text == str(card.get("name", "")), "заголовок подсказки — название карты")
	_check(tooltip._body.text.split("\n").size() == RULES.tooltip_lines(card).size(), "тело подсказки содержит все строки")
	await get_tree().process_frame
	_check(is_equal_approx(tooltip.size.x, 420.0), "ширина подсказки фиксирована 420 px")
	var screen := get_viewport().get_visible_rect().size
	var mouse := Vector2(screen.x - 40.0, 60.0)
	tooltip.reposition(mouse)
	_check(tooltip.global_position == RULES.tooltip_position(mouse, tooltip.size, screen), "подсказка смещается у правого края экрана")
	tooltip.show_card(card)
	_check(tooltip.visible, "повторный показ той же карты не скрывает подсказку")
	tooltip.hide_card()
	_check(not tooltip.visible, "hide_card скрывает подсказку")
	tooltip.free()
	_finished_sections.append("tooltip_widget")


func _check_deck_hover(first: Dictionary, second: Dictionary) -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {"id": 42, "name": "Тест"}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var tooltip = deck._card_tooltip

	deck._collection.clear()
	deck._collection.append(first)
	deck._collection.append(second)
	deck._render_collection()
	await _frames(2)
	var collection_row: Label = deck._list.get_child(0)
	deck._update_card_hover(_center(collection_row))
	_check(tooltip.visible and tooltip._title.text == str(first.get("name", "")), "коллекция: наведение показывает карту строки")
	deck._update_card_hover(Vector2(-10, -10))
	_check(not tooltip.visible, "коллекция: уход курсора скрывает подсказку")

	deck._shop.clear()
	deck._shop.append(second)
	deck._render_shop()
	await _frames(2)
	var shop_row: HBoxContainer = deck._list.get_child(0)
	var shop_label: Label = shop_row.get_child(0)
	deck._update_card_hover(_center(shop_label))
	_check(tooltip.visible and tooltip._title.text == str(second.get("name", "")), "магазин: наведение показывает карту")
	deck._update_card_hover(Vector2(-10, -10))
	_check(not tooltip.visible, "магазин: уход курсора скрывает подсказку")

	await _check_battle_hover(deck, tooltip, first)

	var owned_first := first.duplicate()
	owned_first["quantity"] = 2
	var owned_second := second.duplicate()
	owned_second["quantity"] = 2
	deck._collection.clear()
	deck._collection.append(owned_first)
	deck._collection.append(owned_second)
	deck._render_decks()
	_check(deck._card_select is ItemList and deck._card_select.item_count == 2, "колода: выбор карт — список на две карты")
	await _frames(2)
	var item_point: Vector2 = deck._card_select.get_global_position() + deck._card_select.get_item_rect(1).get_center()
	deck._update_card_hover(item_point)
	_check(tooltip.visible and tooltip._title.text == str(second.get("name", "")), "колода: наведение на строку показывает её карту")
	deck._update_card_hover(Vector2(-10, -10))
	_check(not tooltip.visible, "колода: курсор вне строк скрывает подсказку")
	deck._card_select.select(1)
	deck._add_cards_to_deck()
	var second_key := str(second.get("key", ""))
	_check(int(deck._deck_counts.get(second_key, 0)) == 1, "колода: выбранная карта добавляется в состав")
	deck._remove_card_from_deck()
	_check(not deck._deck_counts.has(second_key), "колода: копия убирается из состава")

	deck._update_card_hover(item_point)
	deck._clear_list()
	deck._update_card_hover(item_point)
	_check(not tooltip.visible, "смена экрана очищает список и скрывает подсказку")

	_finished_sections.append("deck_hover")
	remove_child(deck)
	deck.free()
	GameSession.clear()


# Бой на поле DeckBattleView: наведение находит карту опросом (_bind_card_hover), сигнал card_hovered
# показывает и прячет ту же подсказку. В конце бой закрывается кнопкой возврата, список мира снова виден.
func _check_battle_hover(deck, tooltip, first: Dictionary) -> void:
	var card_name := str(first.get("name", ""))
	var battle := _battle_snapshot(first)
	deck._view = "battle"
	deck._battle_state = battle
	deck._render_battle()
	await _frames(2)
	var view = deck._battle_view
	var hand_card = view.card_view("hand", 0)
	_check(hand_card != null and deck._card_hover_targets.size() == view.card_count(), "бой: каждая карта поля привязана к подсказке")
	if hand_card == null:
		return
	var point := _center(hand_card)
	deck._update_card_hover(point)
	_check(tooltip.visible and tooltip._title.text == card_name, "бой: наведение показывает карту руки")
	_check(tooltip._body.text == "\n".join(PackedStringArray(RULES.tooltip_lines(first))), "бой: подсказка содержит строки карты")
	deck._render_battle()
	_check(tooltip.visible, "бой: обновление боя не прячет подсказку")
	await _frames(2)
	hand_card = view.card_view("hand", 0)
	if hand_card == null:
		return
	deck._update_card_hover(_center(hand_card))
	_check(tooltip.visible and tooltip._title.text == card_name, "бой: после обновления карта под курсором снова показывает подсказку")
	deck._update_card_hover(Vector2(-10, -10))
	_check(not tooltip.visible, "бой: уход курсора скрывает подсказку")
	hand_card.mouse_entered.emit()
	_check(tooltip.visible and tooltip._title.text == card_name, "бой: сигнал card_hovered показывает карту")
	hand_card.mouse_exited.emit()
	_check(not tooltip.visible, "бой: сигнал card_hovered с пустым словарём скрывает подсказку")
	var emptied := battle.duplicate(true)
	emptied["hand"] = []
	emptied["can_select"] = []
	deck._battle_state = emptied
	deck._render_battle()
	await _frames(2)
	deck._update_card_hover(point)
	_check(not tooltip.visible, "бой: убранная карта не участвует в наведении")
	emptied["phase"] = "result"
	deck._battle_result_data = {"outcome": "win", "character": {"hp": 1, "mp": 0}}
	deck._render_battle()
	deck._return_from_battle()
	await SCENE_TRANSITION.wait_until_idle(get_tree())
	await _wait_idle(deck)
	_check(deck._view == "backyard" and not deck._battle_screen.visible, "выход из боя возвращает список мира")
	_finished_sections.append("battle_hover")


func _battle_snapshot(first: Dictionary) -> Dictionary:
	var battle := _read_json(BATTLE_FIXTURE)
	battle["hand"] = [first]
	battle["selected"] = []
	battle["can_select"] = [str(first.get("key", ""))]
	battle["table"] = []
	battle["draw_choices"] = []
	return battle


func _read_json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


func _wait_idle(deck) -> void:
	var waited := 0.0
	while not deck._pending_action.is_empty() and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05
	_check(deck._pending_action.is_empty(), "запрос колоды завершается")


func _frames(count: int) -> void:
	for index in range(count):
		await get_tree().process_frame


func _center(control: Control) -> Vector2:
	return control.get_global_rect().get_center()


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
