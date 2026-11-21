extends Node

const WORKSHOP_SCRIPT := preload("res://scripts/economy_workshop_view.gd")
const FIXTURE_PATH := "res://tests/fixtures/economy/workshop_state.json"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_formats()
	_check_tabs_and_title()
	_check_cart_card_specs()
	_check_queue_and_timers()
	_check_queue_limits()
	_check_order_button_availability()
	_check_order_actions_and_refresh()
	_check_storage_and_placeholders()
	_check_messages()
	await _check_layout_fit()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_workshop_smoke_test: OK")
	get_tree().quit(code)


func _check_formats() -> void:
	_check(WORKSHOP_SCRIPT.format_time(2400) == "40:00", "40 минут форматируются как 40:00")
	_check(WORKSHOP_SCRIPT.format_time(3900) == "1 ч 05 мин", "больше часа: 1 ч 05 мин")
	_check(WORKSHOP_SCRIPT.format_time(59) == "00:59", "меньше минуты: 00:59")
	_check(WORKSHOP_SCRIPT.format_time(-5) == "00:00", "отрицательное время даёт 00:00")
	_check(WORKSHOP_SCRIPT._round_half_even(22.5) == 22 and WORKSHOP_SCRIPT._round_half_even(23.5) == 24
		and WORKSHOP_SCRIPT._round_half_even(22.7) == 23, "округление как round() в Python")
	_check(WORKSHOP_SCRIPT.cart_stats({})["empty_tiles_per_hour"] == 500, "без улучшений повозка идёт 500 тайлов/ч")
	_check(WORKSHOP_SCRIPT.cart_stats({"wheels": 2})["empty_tiles_per_hour"] == 1125, "два уровня колёс дают 1125 тайлов/ч")


func _check_tabs_and_title() -> void:
	var view = _new_view()
	_check(view.window_title() == "Городская мастерская", "заголовок окна как в Python")
	var labels: Array[String] = []
	for button in view._tab_buttons.values():
		labels.append(button.text)
	_check(labels == ["ШЛЕМЫ", "ДОСПЕХИ", "ПЕРЧАТКИ", "ЛАТЫ", "ОБУВЬ", "КОЖЕВНИК", "ПОВОЗКИ", "УЛУЧШЕНИЯ", "СКЛАД"],
		"девять вкладок с подписями Python по порядку")
	_check(view._tab == "helmets" and view._tab_buttons["helmets"].button_pressed, "по умолчанию открыта вкладка шлемов")
	_check(_texts(view).has("Раздел шлемов мастерской."), "заглушка шлемов с текстом Python")
	_drop(view)

	var detached = WORKSHOP_SCRIPT.new()
	detached.set_state(_base_state())
	_check(detached._queue.size() == 1, "состояние принимается до добавления вида в дерево")
	detached.free()


func _check_cart_card_specs() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_open_tab(view, "carts")
	var texts := _texts(view)
	for expected in [
		"Лёгкая повозка", "В очереди: 1", "Цена:", "100/100", "10/10", "Производство: 40 минут",
		"Грузоподъёмность: 300 кг", "Кучер: 1", "Слот для товаров: 1", "Упряжка: 1",
		"Погрузка: 60 кг/мин", "Разгрузка: 40 кг/мин", "Скорость без груза: 10 км/ч", "Полная загрузка: штраф -70%",
	]:
		_check(texts.has(expected), "карточка повозки показывает «%s»" % expected)
	_check(texts.count("Заказать") == 1 and texts.count("Крестьянский обоз") == 0,
		"в каталоге только лёгкая повозка, как в Python")
	var upgraded := _base_state()
	upgraded["cart_progress"]["grades"]["1"]["upgrades"] = {"wheels": 2, "sides": 1, "axles": 3}
	view.set_state(upgraded)
	texts = _texts(view)
	_check(texts.has("Грузоподъёмность: 350 кг") and texts.has("Скорость без груза: 22 км/ч")
		and texts.has("Полная загрузка: штраф -40%"), "улучшения меняют характеристики, 22.5 км/ч округляется к чётному")
	_drop(view)


func _check_queue_and_timers() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_check(view._queue_title.text.contains("ОЧЕРЕДЬ: 1 / 5"), "заголовок очереди: 1 / 5")
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ: 40:00", "общее время очереди 40:00")
	_check(view._work_title.text == "В ПРОИЗВОДСТВЕ: Лёгкая повозка", "текущий заказ — лёгкая повозка")
	_check(view._work_time.text == "До готовности: 40:00", "до готовности 40:00 сразу после получения состояния")
	_check(view._progress_box.visible and view._progress_percent.text == "0%", "прогресс 0% в начале заказа")
	_check(view._slot_badges[0].text == "[1] В ПРОИЗВОДСТВЕ" and view._slot_timers[0].text == "40:00",
		"первый слот занят таймером")
	_check(view._slot_badges[1].text == "[2] СВОБОДНЫЙ СЛОТ" and not view._slot_bodies[1].visible
		and view._slot_hints[1].visible, "второй слот свободен")
	view._apply_elapsed(600.0)
	_check(view._work_time.text == "До готовности: 30:00" and view._slot_timers[0].text == "30:00",
		"через 600 с осталось 30:00")
	_check(view._progress_percent.text == "25%" and is_equal_approx(view._progress_bar.value, 25.0),
		"через 600 с прогресс 25%")
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ: 30:00", "общее время идёт вместе с заказом")
	view._apply_elapsed(2400.0)
	_check(view._work_time.text == "До готовности: 00:00" and view._progress_percent.text == "100%",
		"по окончании 00:00 и 100%")
	_drop(view)


func _check_queue_limits() -> void:
	var view = _new_view()
	view.set_state(_state_with_queue(5))
	_check(view._queue_title.text.contains("ОЧЕРЕДЬ: 5 / 5"), "очередь заполнена 5 / 5")
	_check(view._slot_badges[0].text == "[1] В ПРОИЗВОДСТВЕ" and view._slot_badges[4].text == "[5] В ОЧЕРЕДИ",
		"первый заказ в производстве, остальные в очереди")
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ: 10 ч 00 мин", "сумма 2400+4800+...+12000 с = 10 ч 00 мин")
	_check(view._slot_timers[1].text == "1 ч 20 мин", "второй заказ ждёт 1 ч 20 мин")
	var unsorted := _base_state()
	var unsorted_orders: Array = unsorted["cart_progress"]["grades"]["1"]["production_orders"]
	unsorted_orders.push_front({"order_id": 9, "grade": 1, "created_at": 1767225600.0, "finish_at": 1767225600.0 + 600.0})
	view.set_state(unsorted)
	_check(view._queue[0]["order_id"] == 9 and view._slot_timers[0].text == "10:00", "очередь сортируется по времени финиша")
	view.set_state(_state_with_queue(0))
	_check(view._queue_title.text.contains("ОЧЕРЕДЬ: 0 / 5"), "пустая очередь 0 / 5")
	_check(view._work_title.text == "Мастерская свободна" and view._work_time.text == "Ожидает заказа на производство.",
		"пустая мастерская показывает заглушку Python")
	_check(not view._progress_box.visible and view._queue_total.text == "ОБЩЕЕ ВРЕМЯ: 00:00",
		"без заказов прогресс скрыт, общее время 00:00")
	_check(view._slot_badges[4].text == "[5] СВОБОДНЫЙ СЛОТ" and view._slot_hints[4].visible, "все пять слотов свободны")
	var fallback := _base_state()
	fallback["cart_progress"]["grades"]["1"]["production_orders"] = []
	view.set_state(fallback)
	_check(view._queue_title.text.contains("ОЧЕРЕДЬ: 1 / 5") and view._work_title.text == "В ПРОИЗВОДСТВЕ: Лёгкая повозка",
		"без списка заказов берётся body_finish_at, как в Python")
	_drop(view)


func _check_order_button_availability() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_open_tab(view, "carts")
	_check(not view._order_buttons[1].disabled, "100 древесины, 10 серебра и очередь 1 / 5 — заказ доступен")
	var no_wood := _base_state()
	no_wood["warehouse_storage"]["wood"] = 99
	view.set_state(no_wood)
	_check(view._order_buttons[1].disabled, "99 древесины не хватает на заказ")
	var no_silver := _base_state()
	no_silver["treasury_silver_available"] = 9
	view.set_state(no_silver)
	_check(view._order_buttons[1].disabled, "9 серебра не хватает на заказ")
	view.set_state(_state_with_queue(5))
	_check(view._order_buttons[1].disabled, "очередь 5 / 5 закрывает заказ даже при достатке")
	view.set_state(_state_with_queue(0))
	_check(not view._order_buttons[1].disabled, "пустая очередь с достатком — заказ доступен")
	_drop(view)


func _check_order_actions_and_refresh() -> void:
	var view = _new_view()
	var actions: Array = []
	var record := func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload])
	view.action_requested.connect(record)
	view.set_state(_base_state())
	_open_tab(view, "carts")
	view._order_buttons[1].pressed.emit()
	_check(actions.size() == 1 and actions[0][0] == "order_cart" and actions[0][1] == {"grade": 1},
		"«Заказать» шлёт order_cart с грейдом 1")
	view.set_state(_state_with_queue(5))
	view._order_buttons[1].pressed.emit()
	_check(actions.size() == 1, "недоступная кнопка запрос не шлёт")
	_open_tab(view, "armor")
	_check(actions.size() == 1, "переключение вкладки запрос не шлёт")
	view._process(4.0)
	_check(actions.size() == 1, "обновление состояния не раньше чем через 5 с")
	view._process(1.5)
	_check(actions.size() == 2 and actions[1][0] == "refresh", "через 5 с вид просит актуальное состояние")
	_drop(view)


func _check_storage_and_placeholders() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_open_tab(view, "storage")
	var texts := _texts(view)
	_check(texts.has("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ") and texts.has("Готовые изделия мастерской будут храниться здесь."),
		"пустой склад готовой продукции как в Python")
	var stocked := _base_state()
	stocked["warehouse"] = [{"item_name": "Лёгкая повозка"}, {"item_name": "Кираса"}]
	view.set_state(stocked)
	texts = _texts(view)
	_check(not texts.has("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ"), "с готовыми изделиями пустая надпись уходит")
	_check(texts.count("ГОТОВО К ВЫДАЧЕ") == 2 and texts.has("Кираса"),
		"каждое готовое изделие — карточка «ГОТОВО К ВЫДАЧЕ»")
	_open_tab(view, "armor")
	texts = _texts(view)
	_check(texts.has("ДОСПЕХИ") and texts.has("Раздел доспехов и брони."), "вкладка доспехов — заглушка как в Python")
	_check(view._order_buttons.is_empty(), "на заглушке нет кнопок заказа")
	_open_tab(view, "upgrades")
	_check(_texts(view).has("Улучшения мастерской будут доступны после настройки требований."),
		"улучшения — заглушка с текстом Python")
	_drop(view)


func _check_messages() -> void:
	var view = _new_view()
	view.set_message("Заказ принят. Повозка появится в транспорте через 40 минут.", false)
	_check(view._message_label.visible and view._message_label.text.begins_with("Заказ принят"),
		"строка статуса показывает сообщение")
	_check(view._message_label.get_theme_color("font_color") == WORKSHOP_SCRIPT.MESSAGE_OK_COLOR,
		"успешное сообщение окрашено отдельно")
	view.set_message("Очередь производства повозок заполнена (5/5)", true)
	_check(view._message_label.get_theme_color("font_color") == WORKSHOP_SCRIPT.MESSAGE_ERROR_COLOR,
		"ошибка окрашена цветом Python")
	view.set_message("", false)
	_check(not view._message_label.visible, "пустой текст скрывает строку статуса")
	_drop(view)


func _check_layout_fit() -> void:
	var view = _new_view()
	view.set_state(_state_with_queue(5))
	_open_tab(view, "carts")
	var window: Vector2 = WORKSHOP_SCRIPT.WINDOW_SIZE
	var content := Vector2(window.x - 40.0, window.y - 64.0)
	view.custom_minimum_size = Vector2.ZERO
	await get_tree().process_frame
	var natural: Vector2 = view.get_combined_minimum_size()
	_check(natural.x <= content.x and natural.y <= content.y - 200.0,
		"без растяжения вид не шире %.0f и не выше %.0f: минимум %.0f × %.0f" % [content.x, content.y - 200.0, natural.x, natural.y])
	view.custom_minimum_size = content
	await get_tree().process_frame
	await get_tree().process_frame
	_check(is_equal_approx(view.size.x, content.x) and is_equal_approx(view.size.y, content.y),
		"вид получает ширину контента окна и всю высоту: %.0f × %.0f" % [view.size.x, view.size.y])
	var process: PanelContainer = view._process_panel
	_check(is_equal_approx(process.size.y, WORKSHOP_SCRIPT.PROCESS_HEIGHT), "панель процесса 163 единицы, как 244 px Python")
	_check(process.get_combined_minimum_size().y <= WORKSHOP_SCRIPT.PROCESS_HEIGHT,
		"содержимое панели процесса помещается в 163 единицы")
	_check(is_equal_approx(process.get_global_rect().end.y, view.get_global_rect().end.y), "панель процесса стоит у нижнего края вида")
	_check(view._tab_scroll.size.y >= 200.0, "вкладки получили оставшуюся высоту")
	_check(WORKSHOP_SCRIPT.SLOT_MIN_HEIGHT <= 100.0, "минимальная высота слота не больше 100 единиц")
	_drop(view)


func _new_view():
	var view = WORKSHOP_SCRIPT.new()
	add_child(view)
	view.set_process(false)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _open_tab(view, key: String) -> void:
	view._tab_buttons[key].pressed.emit()


func _fixture() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % FIXTURE_PATH)
	return {}


func _base_state() -> Dictionary:
	var building: Dictionary = _fixture().get("building", {})
	return building.duplicate(true)


func _state_with_queue(count: int) -> Dictionary:
	var state := _base_state()
	var orders: Array = state["cart_progress"]["grades"]["1"]["production_orders"]
	orders.clear()
	for index in range(count):
		orders.append({"order_id": index + 1, "grade": 1, "created_at": 1767225600.0,
			"finish_at": 1767225600.0 + 2400.0 * (index + 1)})
	state["cart_progress"]["grades"]["1"]["body_finish_at"] = 1767228000.0 if count > 0 else null
	return state


func _texts(root: Node) -> Array[String]:
	var found: Array[String] = []
	_collect_texts(root, found)
	return found


func _collect_texts(node: Node, found: Array[String]) -> void:
	if node is Label:
		found.append((node as Label).text)
	elif node is Button:
		found.append((node as Button).text)
	for child in node.get_children():
		_collect_texts(child, found)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
