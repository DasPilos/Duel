extends Node

const CURRENCY := preload("res://scripts/currency_format.gd")
const ECONOMY_SCRIPT := preload("res://scripts/economy_world.gd")
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_currency()
	await _check_tavern()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tavern_drinks_smoke_test: OK")
	await get_tree().create_timer(0.2).timeout
	get_tree().quit(code)


func _check_currency() -> void:
	_check(CURRENCY.format_amount(0) == "0 меди", "ноль выводится как «0 меди»")
	_check(CURRENCY.format_amount(1) == "1 медь", "одна медь в единственном числе")
	_check(CURRENCY.format_amount(20) == "20 меди", "20 меди")
	_check(CURRENCY.format_amount(100) == "1 серебро", "100 меди — одно серебро")
	_check(CURRENCY.format_amount(10203) == "1 золото 2 серебра 3 меди", "золото, серебро и медь выводятся по порядку")
	_check(CURRENCY.format_amount(20500) == "2 золота 5 серебра", "несколько золота и серебра без нулевой меди")
	_check(CURRENCY.total_copper({"copper": 5, "silver": 2, "gold": 1}) == 10205, "общая сумма кошелька в меди")
	_check(not CURRENCY.has_enough_copper({"copper": 5, "silver": 0, "gold": 0}, 20), "меди не хватает на цену")
	_check(CURRENCY.has_enough_copper({"copper": 5, "silver": 1, "gold": 0}, 105), "серебро учитывается при проверке цены")


func _check_tavern() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL}
	GameSession.character = {"id": 42, "name": "Тест", "hp": 80, "max_hp": 140, "copper": 120,
		"silver": 0, "gold": 0, "carried_weight_kg": 0.0}
	ApiClient._http.timeout = 0.5
	var economy = ECONOMY_SCRIPT.new()
	economy.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(economy)
	await _wait_idle(economy)

	economy._load_tavern()
	_check(economy._view == "tavern" and economy._pending_action == "drinks", "«Таверна» запрашивает напитки сервера")
	await _wait_idle(economy)
	_check(economy._details.text == "Таверна · напитки не загружены.", "при ошибке загрузки экран говорит, что напитки не получены")

	economy._pending_action = "drinks"
	economy._on_api_completed(true, {"drinks": _drinks_payload()})
	var box = _tavern_box(economy)
	_check(box != null, "экран таверны строится")
	_check(_drink_texts(box) == ["Эль — 20 меди", "Крепкое — 1 серебро"], "напитки выводятся с ценой в денежном формате")
	_check(_drink_tooltip(box, 0) == "мгновенно восстанавливает 50 HP", "описание напитка выводится подсказкой")
	_check(economy._details.text.contains("Ваши средства: 1 серебро 20 меди") and economy._details.text.contains("Здоровье: 80 / 140"), "шапка показывает деньги и здоровье персонажа")

	var first: Button = _drink_buttons(box)[0]
	first.gui_input.emit(_click(false))
	_check(economy._pending_action == "", "одиночный клик по напитку только выбирает его, покупки нет")
	first.gui_input.emit(_click(true))
	_check(economy._pending_action == "buy_drink", "двойной клик отправляет покупку")
	await _wait_idle(economy)
	_check(economy._status.text.begins_with("Ошибка покупки:"), "сетевая ошибка покупки показывается в статусе")

	economy._status.text = "маркер"
	economy._pending_action = "buy_drink"
	economy._on_api_completed(false, "БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ")
	_check(economy._status.text == "маркер", "полное здоровье: ошибка не показывается, как в Python")
	economy._pending_action = "buy_drink"
	economy._on_api_completed(false, "Напиток не найден")
	_check(economy._status.text == "Ошибка покупки: Напиток не найден", "прочие ошибки покупки показываются с префиксом")

	GameSession.character["copper"] = 5
	economy._buy_drink(1, 20)
	_check(economy._status.text == ECONOMY_SCRIPT.TAVERN_BROKE_LINE and economy._pending_action == "", "без денег покупка не отправляется")
	GameSession.character["copper"] = 120

	economy._pending_action = "buy_drink"
	economy._on_api_completed(true, {"character": {"id": 42, "name": "Тест", "hp": 140, "max_hp": 140,
		"copper": 100, "silver": 0, "gold": 0, "carried_weight_kg": 0.0}})
	_check(int(GameSession.character["hp"]) == 140 and economy._details.text.contains("Здоровье: 140 / 140"), "ответ покупки обновляет здоровье и шапку таверны")
	_check(economy._details.text.contains("Ваши средства: 1 серебро"), "после покупки деньги в шапке обновлены")

	economy._select_tavern_tab("sell")
	box = _tavern_box(economy)
	_check(_label_texts(box).has("Кликните на предмет в рюкзаке") and _drink_buttons(box).is_empty(), "вкладка «Скупка» повторяет подсказку Python без списка напитков")
	economy._select_tavern_tab("drinks")

	economy._pending_action = "drinks"
	economy._on_api_completed(true, {"drinks": []})
	box = _tavern_box(economy)
	_check(_label_texts(box).has("В баре нет напитков."), "пустой список напитков объясняется")

	economy._pending_action = ""
	economy._load_city()
	_check(_tavern_box(economy) == null, "переход к городу убирает панель таверны")
	await _wait_idle(economy)

	remove_child(economy)
	economy.free()
	GameSession.clear()


func _drinks_payload() -> Array:
	return [
		{"id": 1, "name": "Эль", "price_copper": 20, "effect": "heal", "effect_value": 50,
			"description": "мгновенно восстанавливает 50 HP"},
		{"id": 2, "name": "Крепкое", "price_copper": 100, "effect": "heal", "effect_value": 80,
			"description": "восстанавливает 80 HP"},
	]


func _tavern_box(economy):
	return economy._content.find_child("TavernControls", false, false)


func _drink_buttons(box) -> Array:
	var buttons: Array = []
	for child in box.get_children():
		if child is Button:
			buttons.append(child)
	return buttons


func _drink_texts(box) -> Array:
	var texts: Array = []
	for button in _drink_buttons(box):
		texts.append(button.text)
	return texts


func _drink_tooltip(box, index: int) -> String:
	return _drink_buttons(box)[index].tooltip_text


func _label_texts(box) -> Array:
	var texts: Array = []
	for child in box.get_children():
		if child is Label:
			texts.append(child.text)
	return texts


func _wait_idle(economy) -> void:
	var waited := 0.0
	while not economy._pending_action.is_empty() and waited < 5.0:
		await get_tree().create_timer(0.05).timeout
		waited += 0.05
	_check(economy._pending_action.is_empty(), "запрос экономики завершается")


func _click(double: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = double
	return event


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
