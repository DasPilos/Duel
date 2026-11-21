extends Node

const STABLE_SCRIPT := preload("res://scripts/economy_stable_view.gd")
const FIXTURE_PATH := "res://tests/fixtures/economy/building_stable.json"
const ROADS_PATH := "res://tests/fixtures/economy/world_roads.json"
const CITY_RESOURCES := {"wheat": 120, "flax": 10, "wood": 50}

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_formats()
	_check_tabs_and_title()
	_check_transport_figures_and_rows()
	_check_dispatch_payload()
	_check_dispatch_validation()
	_check_routes_list()
	_check_cart_actions()
	_check_stall_rows_and_purchase()
	_check_upgrade_actions()
	_check_cart_purchase()
	_check_messages()
	_check_refresh()
	await _check_layout_width()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_stable_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_formats() -> void:
	_check(STABLE_SCRIPT.format_hms(3725) == "01:02:05", "format_hms: 3725 с — 01:02:05")
	_check(STABLE_SCRIPT.format_hms(59) == "00:00:59", "format_hms: меньше минуты — 00:00:59")
	_check(STABLE_SCRIPT.format_hms(-5) == "00:00:00", "format_hms: отрицательное время даёт 00:00:00")


func _check_tabs_and_title() -> void:
	var view = _new_view()
	_check(view.window_title() == "Конюшня", "заголовок окна «Конюшня»")
	var labels: Array[String] = []
	for button in view._tab_buttons.values():
		labels.append(button.text)
	_check(labels == ["ТРАНСПОРТ", "МАРШРУТЫ", "ПОВОЗКИ", "СТОЙЛО", "УЛУЧШЕНИЯ"], "пять вкладок в порядке Python")
	var sub_labels: Array[String] = []
	for button in view._upgrade_buttons.values():
		sub_labels.append(button.text)
	_check(sub_labels == ["ТРАНСПОРТ", "СТОЙЛО", "КОНЮШНЯ"], "подвкладки улучшений: ТРАНСПОРТ, СТОЙЛО, КОНЮШНЯ")
	_check(view._tab_buttons["transport"].button_pressed and view._tab_panels["transport"].visible,
		"по умолчанию открыта вкладка ТРАНСПОРТ")
	_check(not view._tab_panels["routes"].visible, "остальные вкладки скрыты")
	view.set_state(_base_state())
	_check(_texts(view).has("Уровень 2"), "подзаголовок «Уровень 2» из состояния")
	_check(not _texts(view).has("Рабочие места"), "блока «Рабочие места» нет, как в Python")
	_drop(view)


func _check_transport_figures_and_rows() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	var summary: Array[String] = []
	for label in view._summary_labels:
		summary.append(label.text)
	_check(summary == ["Повозок в городе: 2", "Готово к рейсу: 1", "В пути: 1"],
		"сводка рейсов: в городе 2, готово 1, в пути 1")
	_check(view._trip_rows.get_child_count() == 2, "таблица рейсов: строка на каждую повозку")
	var texts := _texts(view)
	for expected in ["Экипаж — / лошадей: 0/1", "Тимофей / Ветер", "Едет к объекту", "Закреплён",
			"00:52:00", "Маршрут: Крестьянское поселение", "До завершения", "Следует в Крестьянское поселение"]:
		_check(texts.has(expected), "строка рейса показывает «%s»" % expected)
	_drop(view)


func _check_dispatch_payload() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_routes(_roads(), CITY_RESOURCES)
	view.set_state(_base_state())
	view._cart_select.select(1)
	view._cart_select.item_selected.emit(1)
	view._driver_select.select(1)
	view._route_select.select(1)
	view._route_select.item_selected.emit(1)
	view._horse_selects[0].select(1)
	view._resource_selects[0].select(2)
	view._pin_check.button_pressed = true
	_press(view, "Собрать экипаж")
	_check(view._dispatch_panel.visible, "кнопка «Собрать экипаж» открывает форму рейса")
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check(actions.size() == 1 and actions[0][0] == "dispatch", "«ОТПРАВИТЬ В РЕЙС» шлёт dispatch")
	if actions.size() == 1:
		var payload: Dictionary = actions[0][1]
		_check(payload == {
			"cart_id": "cart_grade_1", "horse_ids": [1], "driver_citizen_id": 5,
			"destination_building_id": "wheat_farm", "resource_ids": ["flax"], "pinned": true,
		}, "тело dispatch: cart_id, horse_ids, driver_citizen_id, destination_building_id, resource_ids, pinned")
		_check(typeof(payload["driver_citizen_id"]) == TYPE_INT and typeof(payload["cart_id"]) == TYPE_STRING
			and typeof(payload["pinned"]) == TYPE_BOOL, "типы dispatch: int, String, bool")
		_check(payload["horse_ids"] is Array and typeof(payload["horse_ids"][0]) == TYPE_INT
			and payload["resource_ids"] is Array and typeof(payload["resource_ids"][0]) == TYPE_STRING,
			"horse_ids — массив int, resource_ids — массив String")
	_drop(view)


func _check_dispatch_validation() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_routes(_roads(), CITY_RESOURCES)
	view.set_state(_base_state())
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Выберите повозку.", "без выбранной повозки рейс не шлётся")
	view._cart_select.select(2)
	view._cart_select.item_selected.emit(2)
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Повозка сейчас: В пути.", "занятая повозка не отправляется")
	view._cart_select.select(1)
	view._cart_select.item_selected.emit(1)
	view._driver_select.select(0)
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Выберите свободного горожанина-кучера.", "без кучера рейс не шлётся")
	view._driver_select.select(1)
	view._route_select.select(0)
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Выберите пункт назначения.", "без маршрута рейс не шлётся")
	view._route_select.select(1)
	view._route_select.item_selected.emit(1)
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Выберите свободную отдыхающую лошадь 1.", "без лошади рейс не шлётся")
	view._horse_selects[0].select(1)
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Выберите груз для слота 1.", "без груза рейс не шлётся")
	view.set_routes(_roads(), {})
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Для этой повозки нет полного набора доступных грузовых ресурсов.",
		"ресурсы, которых нет в городе, не предлагаются")
	view.set_routes([], {})
	_press(view, "ОТПРАВИТЬ В РЕЙС")
	_check_message(view, "Нет доступных серверных маршрутов.", "без маршрутов рейс не шлётся")
	_check(actions.is_empty(), "при проверках dispatch не уходит")
	_drop(view)


func _check_routes_list() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_routes(_roads(), CITY_RESOURCES)
	_check(view._route_list.get_child_count() == 5, "маршруты: пять карточек из world_roads.json")
	_check(view._route_detail.get_child(0).text == "Крестьянское поселение", "детали: первый маршрут выбран по умолчанию")
	view._select_route(2)
	_check(view._route_detail.get_child(0).text == "Горный разлом", "выбор маршрута меняет детали")
	_check(view._route_detail.get_child(1).text == "Расстояние: 1.74 км", "расстояние маршрута в км")
	_check(_texts(view).has("Горный разлом · 1.74 км"), "карточка маршрута показывает название и расстояние")
	_check(actions.is_empty(), "выбор маршрута не шлёт запрос")
	view.set_routes([], {})
	_check(_texts(view).has("Нет данных о загородных маршрутах"), "пустой список маршрутов")
	_drop(view)


func _check_cart_actions() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_state(_base_state())
	_check(_buttons(view, "РЕМОНТ · 20 древесины").size() == 1, "ремонт только у повозки ниже 100%")
	_press(view, "РЕМОНТ · 20 древесины")
	_check(actions.back() == ["repair_cart", {"cart_id": "cart_grade_1"}], "ремонт шлёт repair_cart {cart_id}")
	var always := _buttons(view, "Всегда хорошо")
	_press_button(always[0])
	_check(actions.back() == ["set_auto_repair", {"cart_id": "cart_grade_1", "mode": null}],
		"активный режим выключается: mode = null")
	_press_button(always[1])
	_check(actions.back() == ["set_auto_repair", {"cart_id": "cart_grade_1~2", "mode": "always"}],
		"неактивный режим включается: mode = \"always\"")
	_press(view, "Экономный ремонт")
	_check(actions.back() == ["set_auto_repair", {"cart_id": "cart_grade_1", "mode": "economy"}],
		"экономный ремонт шлёт mode = \"economy\"")
	view._rename_select.select(2)
	view._rename_input.text = "Почта"
	_press(view, "ПЕРЕИМЕНОВАТЬ")
	_check(actions.back() == ["rename_cart", {"cart_id": "cart_grade_1~2", "name": "Почта"}],
		"переименование шлёт rename_cart {cart_id, name}")
	_press(view, "Закреплён")
	_check(actions.back() == ["toggle_convoy_pin", {"convoy_id": 12, "pinned": true}],
		"закрепление рейса шлёт toggle_convoy_pin {convoy_id, pinned: текущее состояние}")
	_check(actions.size() == 6, "на вкладке ПОВОЗКИ шесть запросов, без лишних")
	_drop(view)


func _check_stall_rows_and_purchase() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_state(_base_state())
	_open_tab(view, "stalls")
	_check(view._stall_summary.text == "Стойла: занято 3 / 6 мест", "сводка стойл: занято 3 / 6 мест")
	_check(view._feed_label.text == "Расход корма: -6 кг Пшеница / час", "расход корма с названием зерна")
	_check(view._stall_rows.get_child_count() == 9, "таблица стойл: девять строк (как в состоянии)")
	_check(_texts(view).has("Пустое стойло") and _count_texts(view, "Пустое стойло") == 3, "три пустых стойла")
	_check(_count_texts(view, "Доступно на 3 уровне Конюшни") == 2 and _count_texts(view, "Доступно на 4 уровне Конюшни") == 1,
		"закрытые стойла с уровнем открытия из состояния")
	var sell := _buttons(view, "ПРОДАТЬ ЛОШАДЬ")
	_check(sell.size() == 3 and sell[0].disabled and sell[0].tooltip_text == STABLE_SCRIPT.SELL_UNAVAILABLE_TEXT,
		"ПРОДАТЬ отключена с подсказкой: продажи на сервере нет")
	var satiety := _find_label(view, "Сытность 15%")
	_check(satiety != null and satiety.get_theme_color("font_color") == STABLE_SCRIPT.SATIETY_MID_COLOR,
		"сытность 15% окрашена жёлтым, как в Python")
	_check(_texts(view).has("Сытность 86%") and _find_label(view, "Сытность 86%").get_theme_color("font_color") == STABLE_SCRIPT.SATIETY_OK_COLOR,
		"сытность 86% окрашена зелёным")
	var buy := _buttons(view, "КУПИТЬ")
	_check(buy.size() == 3 and not buy[0].disabled and _texts(view).has("10 серебра"),
		"КУПИТЬ по цене horse_price_next_silver (10 серебра)")
	_press_button(buy[0])
	_check(actions.back() == ["purchase_horse", {"slot_index": 3}], "покупка лошади шлёт purchase_horse {slot_index: int}")
	_check(typeof(actions.back()[1]["slot_index"]) == TYPE_INT, "slot_index — int")
	var no_price := _base_state()
	no_price.erase("horse_price_next_silver")
	view.set_state(no_price)
	_check(_texts(view).has("50 серебра"), "без цены в состоянии остаётся цена Python: 50 серебра")
	var poor := _base_state()
	poor["treasury_silver_available"] = 5
	view.set_state(poor)
	_check(_buttons(view, "КУПИТЬ")[0].disabled, "КУПИТЬ отключена, если серебра не хватает")
	_drop(view)


func _check_upgrade_actions() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_state(_base_state())
	_open_tab(view, "upgrades")
	_check(_texts(view).has("Древесина · На складе: 300"), "улучшения повозки: материалы узла и склад")
	view._select_cart_node("sides")
	_check(_texts(view).has("Доска · На складе: 0"), "выбор узла меняет материалы")
	_check(actions.is_empty(), "выбор узла улучшения не шлёт запрос")
	view._select_upgrade_tab("stalls")
	_check(_texts(view).has("Вместимость: 6 мест (+0 от улучшений)"), "вместимость стойл на вкладке СТОЙЛО")
	_check(_texts(view).has("Идёт улучшение: осталось 02:00:00"), "улучшение в процессе: таймер")
	var install := _buttons(view, "КУПИТЬ И УСТАНОВИТЬ")
	_check(install.size() == 1 and not install[0].disabled, "улучшение стойла можно купить")
	_press_button(install[0])
	_check(actions.back() == ["purchase_upgrade", {"upgrade_id": "wooden_stalls"}],
		"покупка улучшения шлёт purchase_upgrade {upgrade_id: String}")
	var short := _base_state()
	short["stall_upgrades"]["wooden_stalls"]["can_purchase"] = false
	view.set_state(short)
	_check(_buttons(view, "НЕДОСТАТОЧНО")[0].disabled, "без ресурсов улучшение недоступно")
	view._select_upgrade_tab("building")
	_check(_texts(view).has("Улучшение до уровня 3") and _texts(view).has("Древесина: склад 300/5"),
		"КОНЮШНЯ: уровень здания и материалы")
	_check(_texts(view).has("Железная руда: склад 0/5"), "материал без запаса в складе")
	_check(_texts(view).has("недостаточно"), "нехватка материала отмечена")
	var start := _buttons(view, "НЕДОСТАТОЧНО РЕСУРСОВ")
	_check(start.size() == 1 and start[0].disabled, "улучшение здания недоступно без материалов")
	var ready := _base_state()
	ready["upgrade"]["ready"] = true
	view.set_state(ready)
	_press(view, "ОПЛАТИТЬ И УЛУЧШИТЬ")
	_check(actions.back() == ["start_upgrade", {}], "улучшение здания шлёт start_upgrade")
	var maximum := _base_state()
	maximum["upgrade"] = null
	view.set_state(maximum)
	_check(_texts(view).has("Максимальный уровень здания"), "на максимуме уровня здания улучшения нет")
	_drop(view)


func _check_cart_purchase() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_state(_base_state())
	_open_tab(view, "carts")
	var order_text := "ИЗГОТОВИТЬ · 100 дерева · 10 серебра · 40 мин"
	_check(_buttons(view, order_text).size() == 1 and not _buttons(view, order_text)[0].disabled,
		"кнопка заказа повозки с ценой и доступна при ресурсах")
	_check(_texts(view).has("Лёгкая повозка изготавливается: 40 мин."), "строка производства из body_finish_at")
	_press(view, order_text)
	_check(actions.back() == ["purchase_cart", {}], "заказ повозки шлёт purchase_cart {}")
	var poor := _base_state()
	poor["warehouse_storage"]["wood"] = 99
	view.set_state(poor)
	_check(_buttons(view, order_text)[0].disabled, "99 древесины — заказ недоступен")
	var full := _base_state()
	var orders: Array = full["cart_progress"]["grades"]["1"]["production_orders"]
	for index in range(4):
		orders.append({"order_id": 20 + index, "grade": 1, "created_at": 1767225600.0, "finish_at": 1767228000.0})
	view.set_state(full)
	_check(_buttons(view, order_text)[0].disabled, "очередь 5 / 5 закрывает заказ")
	_drop(view)


func _check_messages() -> void:
	var view = _new_view()
	view.set_message("Заказ принят. Повозка появится в транспорте через 40 минут.", false)
	_check(view._message_label.visible and view._message_label.text.begins_with("Заказ принят"),
		"строка статуса показывает сообщение")
	_check(view._message_label.get_theme_color("font_color") == STABLE_SCRIPT.MESSAGE_OK_COLOR,
		"успешное сообщение окрашено отдельно")
	view.set_message("Очередь производства повозок заполнена (5/5)", true)
	_check(view._message_label.get_theme_color("font_color") == STABLE_SCRIPT.MESSAGE_ERROR_COLOR,
		"ошибка окрашена цветом Python")
	view.set_message("", false)
	_check(not view._message_label.visible, "пустой текст скрывает строку статуса")
	_drop(view)


func _check_refresh() -> void:
	var view = _new_view()
	var actions := _record(view)
	view.set_state(_base_state())
	view._process(4.0)
	_check(actions.is_empty(), "обновление состояния не раньше чем через 5 с")
	view._process(1.5)
	_check(actions.size() == 1 and actions[0] == ["refresh", {}], "через 5 с вид просит актуальное состояние")
	_drop(view)


func _check_layout_width() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	view.set_routes(_roads(), CITY_RESOURCES)
	await get_tree().process_frame
	for key in ["transport", "routes", "carts", "stalls", "upgrades"]:
		view._tab_buttons[key].pressed.emit()
		await get_tree().process_frame
		var content: Control = view._tab_panels[key].get_child(0)
		var width: float = content.get_combined_minimum_size().x
		_check(width <= STABLE_SCRIPT.WINDOW_SIZE.x,
			"вкладка %s помещается в ширину окна %.0f (минимум %.0f)" % [key, STABLE_SCRIPT.WINDOW_SIZE.x, width])
	_drop(view)


func _new_view():
	var view = STABLE_SCRIPT.new()
	add_child(view)
	view.set_process(false)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _record(view) -> Array:
	var actions: Array = []
	view.action_requested.connect(func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload]))
	return actions


func _open_tab(view, key: String) -> void:
	view._tab_buttons[key].pressed.emit()


func _press(view, text: String) -> void:
	var found := _buttons(view, text)
	_check(not found.is_empty(), "кнопка «%s» есть" % text)
	if not found.is_empty():
		_press_button(found[0])


func _press_button(button: Button) -> void:
	button.pressed.emit()


func _check_message(view, expected: String, message: String) -> void:
	_check(view._message_label.visible and view._message_label.text == expected and
		view._message_label.get_theme_color("font_color") == STABLE_SCRIPT.MESSAGE_ERROR_COLOR,
		"%s: «%s»" % [message, expected])


func _fixture_building() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	if parsed is Dictionary and parsed.get("building") is Dictionary:
		return parsed["building"]
	_check(false, "фикстура %s читается как JSON с полем building" % FIXTURE_PATH)
	return {}


func _base_state() -> Dictionary:
	return _fixture_building().duplicate(true)


func _roads() -> Array:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(ROADS_PATH))
	if parsed is Dictionary and parsed.get("terrain") is Dictionary:
		return parsed["terrain"]["roads"]["routes"]
	_check(false, "фикстура %s читается как JSON с маршрутами" % ROADS_PATH)
	return []


func _texts(root: Node) -> Array[String]:
	var found: Array[String] = []
	_collect_texts(root, found)
	return found


func _count_texts(root: Node, text: String) -> int:
	var count := 0
	for found in _texts(root):
		if found == text:
			count += 1
	return count


func _collect_texts(node: Node, found: Array[String]) -> void:
	if node is Label:
		found.append((node as Label).text)
	elif node is Button:
		found.append((node as Button).text)
	for child in node.get_children():
		_collect_texts(child, found)


func _buttons(root: Node, text: String) -> Array:
	var found: Array = []
	_collect_buttons(root, text, found)
	return found


func _collect_buttons(node: Node, text: String, found: Array) -> void:
	if node is Button and (node as Button).text == text:
		found.append(node)
	for child in node.get_children():
		_collect_buttons(child, text, found)


func _find_label(root: Node, text: String) -> Label:
	for label in _labels(root):
		if label.text == text:
			return label
	return null


func _labels(node: Node) -> Array:
	var found: Array = []
	if node is Label:
		found.append(node)
	for child in node.get_children():
		found.append_array(_labels(child))
	return found


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
