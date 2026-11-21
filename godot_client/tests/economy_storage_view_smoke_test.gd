extends Node

const STORAGE_SCRIPT := preload("res://scripts/economy_storage_view.gd")
const METER_SCRIPT := preload("res://scripts/storage_meter.gd")
const BARN_FIXTURE := "res://tests/fixtures/economy/building_barn.json"
const WAREHOUSE_FIXTURE := "res://tests/fixtures/economy/economy_storage_view_warehouse.json"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_formats()
	_check_constants()
	_check_barn_title_tabs_and_rows()
	_check_storage_actions()
	_check_warehouse_rows_and_order()
	_check_charging_meter()
	_check_upgrade_tab()
	_check_upgrade_states()
	_check_message()
	await _check_layout_width()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_storage_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_formats() -> void:
	_check(STORAGE_SCRIPT.format_duration(18000) == "5 ч 0 мин", "длительность улучшения как format_duration: 5 ч 0 мин")
	_check(STORAGE_SCRIPT.format_duration(2700) == "45 мин", "меньше часа: только минуты")
	_check(STORAGE_SCRIPT.format_clock(3725) == "1 ч 02 м 05 с", "таймер стройки как format_clock: 1 ч 02 м 05 с")
	_check(STORAGE_SCRIPT.format_clock(-3) == "0 ч 00 м 00 с", "отрицательный таймер даёт нули")


func _check_constants() -> void:
	_check(STORAGE_SCRIPT.WINDOW_SIZE == Vector2(600, 507), "размер окна склада 600×507 (Python 900×760)")
	_check(STORAGE_SCRIPT.BORDER_COLOR == Color8(220, 185, 70), "рамка окна как в Python")
	_check(STORAGE_SCRIPT.BACKGROUND_COLOR == Color8(24, 26, 18), "фон окна как в Python")


func _check_barn_title_tabs_and_rows() -> void:
	var view = _new_view()
	view.set_state(_barn_state())
	_check(view.window_title() == "Амбар", "заголовок амбара по полю building")
	_check(_texts(view).has("Уровень 1"), "подпись уровня Python: Уровень 1")
	var labels: Array[String] = []
	for button in view._tab_buttons.values():
		labels.append(str(button.text))
	_check(labels == ["СКЛАД", "УЛУЧШЕНИЕ"], "вкладки СКЛАД и УЛУЧШЕНИЕ по порядку")
	_check(view._tab_buttons["storage"].button_pressed, "по умолчанию открыта вкладка СКЛАД")
	_check(_row_names(view) == ["Пшеница"], "фикстура амбара даёт одну строку с товаром")
	_check(_texts(view).has("120 / 400"), "количество выводится как «N / лимит»")
	_check(not _texts(view).has("Инвентарь и сундуки") and not _texts(view).has("Рабочие места"),
		"нет панели инвентаря и слотов рабочих")

	var state := _barn_state()
	state["storage"] = {"berries": 120, "wheat": 640, "meat": 35, "limit": 1500}
	view.set_state(state)
	_check(_row_names(view) == ["Ягоды", "Пшеница", "Мясо"], "амбар с тремя товарами: строки в порядке Python")
	_check(_texts(view).has("640 / 1500") and _texts(view).has("35 / 1500"), "три строки с количеством и лимитом")
	_check(_find_buttons(view, "ВЗЯТЬ").size() == 3, "ВЗЯТЬ есть у всех товаров с запасом")
	_check(_find_buttons(view, "ВНЕСТИ").is_empty(), "без storage_depositable ВНЕСТИ не показывается")
	_check(view._subtitle.text == "Уровень 1", "подпись уровня обновляется вместе с состоянием")
	_drop(view)


func _check_storage_actions() -> void:
	var view = _new_view()
	var actions: Array = []
	var record := func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload])
	view.action_requested.connect(record)
	var state := _barn_state()
	state["storage"] = {"berries": 120, "wheat": 640, "meat": 35, "limit": 1500}
	state["storage_depositable"] = {"berries": {"in_backpack": 50, "max_deposit": 50}}
	view.set_state(state)
	_check(_press(view._rows.get_child(0), "ВНЕСТИ"), "у ягод есть ВНЕСТИ при max_deposit > 0")
	_check(actions.size() == 1 and actions[0][0] == "storage_deposit" and actions[0][1] == {"resource": "berries"},
		"ВНЕСТИ шлёт storage_deposit с ключом товара")
	_check(_press(view._rows.get_child(1), "ВЗЯТЬ"), "у пшеницы есть ВЗЯТЬ")
	_check(actions.size() == 2 and actions[1][0] == "storage_withdraw" and actions[1][1] == {"resource": "wheat", "quantity": 640},
		"ВЗЯТЬ шлёт storage_withdraw с товаром и запасом здания")
	_drop(view)


func _check_warehouse_rows_and_order() -> void:
	var view = _new_view()
	view.set_state(_warehouse_state())
	var names := _row_names(view)
	_check(names.size() == 24, "склад показывает все 24 товара из состояния, служебный limit не строка")
	_check(names[0] == "Древесина" and names[1] == "Доска" and names[23] == "Алмаз",
		"товары идут в порядке Python, а не в порядке ответа сервера")
	_check(view._table_scroll.is_ancestor_of(view._rows), "строки товаров лежат внутри ScrollContainer")
	_check(view._table_scroll.custom_minimum_size.y == STORAGE_SCRIPT.TABLE_MAX_HEIGHT,
		"длинный список ограничен по высоте, остальное прокручивается")
	_check(_texts(view).has("310 / 3000") and _texts(view).has("0 / 3000"), "количество каждого товара из 3000")
	_check(_find_buttons(view, "ВЗЯТЬ").size() == 9, "ВЗЯТЬ у девяти товаров с запасом больше нуля")
	_check(_find_buttons(view, "ВНЕСТИ").size() == 6, "ВНЕСТИ у шести товаров с max_deposit > 0")
	_drop(view)


func _check_charging_meter() -> void:
	var view = _new_view()
	var state := _warehouse_state()
	state["city_upgrade"] = {"charging_resources": ["stone"]}
	view.set_state(state)
	var stone = _first_meter(view._rows.get_child(_row_names(view).find("Камень")))
	var wood = _first_meter(view._rows.get_child(_row_names(view).find("Древесина")))
	_check(stone != null and stone._charging and wood != null and not wood._charging,
		"шкала мигает только у товара, который заряжает улучшение")
	_drop(view)


func _check_upgrade_tab() -> void:
	var view = _new_view()
	view.set_state(_warehouse_state())
	_open_tab(view, "upgrade")
	var texts := _texts(view)
	_check(texts.has("Улучшение до уровня 3 — время стройки 5 ч 0 мин"), "заголовок улучшения как в Python")
	_check(texts.has("Материалы списываются с общего склада"), "подпись о списании материалов")
	_check(texts.has("Древесина: склад 310/30, ранее оплачено 10"), "материал с уже оплаченной частью")
	_check(texts.has("Доска: склад 15/15, ранее оплачено 5"), "второй материал с оплатой")
	_check(texts.has("Железо: склад 7/12"), "материал без оплаты")
	_check(_label_color(view, "Древесина: склад 310/30, ранее оплачено 10") == STORAGE_SCRIPT.MATERIAL_DONE_COLOR,
		"материал, набранный на складе, зелёный")
	_check(_label_color(view, "Железо: склад 7/12") == STORAGE_SCRIPT.MATERIAL_PENDING_COLOR,
		"недостающий материал жёлтый")
	_check(not _has_text_starting(view, "Вместимость"), "без storage_limit строки вместимости нет")
	var button := _find_button(view, "УЛУЧШИТЬ")
	_check(button != null and button.disabled and button.custom_minimum_size == STORAGE_SCRIPT.UPGRADE_SIZE,
		"кнопка УЛУЧШИТЬ 167×28 и выключена, пока материалов не хватает")
	_drop(view)


func _check_upgrade_states() -> void:
	var view = _new_view()
	var actions: Array = []
	var record := func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload])
	view.action_requested.connect(record)
	var state := _warehouse_state()
	state["upgrade"]["ready"] = true
	view.set_state(state)
	_open_tab(view, "upgrade")
	_check(_press(view, "УЛУЧШИТЬ"), "готовое улучшение показывает кнопку")
	_check(actions.size() == 1 and actions[0] == ["upgrade_building", {}], "УЛУЧШИТЬ шлёт upgrade_building без payload")
	state["upgrade"]["ready"] = false
	view.set_state(state)
	_press(view, "УЛУЧШИТЬ")
	_check(actions.size() == 1, "выключенная кнопка улучшения ничего не шлёт")

	state = _warehouse_state()
	state["upgrade"]["in_progress"] = true
	state["upgrade"]["seconds_left"] = 3725
	view.set_state(state)
	_check(_find_button(view, "УЛУЧШИТЬ") == null, "во время стройки кнопки нет")
	_check(_texts(view).has("Идёт стройка: осталось 1 ч 02 м 05 с"), "таймер стройки как в Python")
	view._process(60.0)
	_check(_texts(view).has("Идёт стройка: осталось 1 ч 01 м 05 с"), "таймер стройки идёт между обновлениями")

	state = _warehouse_state()
	state["upgrade"]["storage_limit"] = 5000
	view.set_state(state)
	_check(_texts(view).has("Вместимость каждого товара: 5000 материалов"),
		"если сервер прислал вместимость следующего уровня, она выводится с единицей склада")

	state = _warehouse_state()
	state["upgrade"] = null
	view.set_state(state)
	_check(_texts(view).has("Здание достигло максимального уровня") and _find_button(view, "УЛУЧШИТЬ") == null,
		"на максимальном уровне текст Python и без кнопки")
	_drop(view)


func _check_message() -> void:
	var view = _new_view()
	view.set_message("Недостаточно древесины")
	_check(view._message_label.visible and view._message_label.text == "Недостаточно древесины", "сообщение ошибки видно")
	_check(view._message_label.get_theme_color("font_color") == STORAGE_SCRIPT.ERROR_COLOR, "ошибка окрашена цветом Python")
	view.set_message("")
	_check(not view._message_label.visible, "пустой текст скрывает сообщение")
	_drop(view)


func _check_layout_width() -> void:
	var view = _new_view()
	view.set_state(_warehouse_state())
	await get_tree().process_frame
	var width: float = view.get_combined_minimum_size().x
	_check(width <= 560.0, "вид помещается в ширину содержимого окна (560), минимум %.0f" % width)
	_drop(view)


func _new_view():
	var view = STORAGE_SCRIPT.new()
	add_child(view)
	view.set_process(false)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _open_tab(view, key: String) -> void:
	view._tab_buttons[key].pressed.emit()


func _fixture(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % path)
	return {}


func _barn_state() -> Dictionary:
	var building: Dictionary = _fixture(BARN_FIXTURE).get("building", {})
	return building.duplicate(true)


func _warehouse_state() -> Dictionary:
	var building: Dictionary = _fixture(WAREHOUSE_FIXTURE).get("building", {})
	return building.duplicate(true)


func _row_names(view) -> Array[String]:
	var names: Array[String] = []
	for row in view._rows.get_children():
		names.append(_texts(row)[0])
	return names


func _first_meter(node: Node) -> Node:
	if node.get_script() == METER_SCRIPT:
		return node
	for child in node.get_children():
		var found := _first_meter(child)
		if found != null:
			return found
	return null


func _press(node: Node, text: String) -> bool:
	var button := _find_button(node, text)
	if button == null:
		return false
	button.pressed.emit()
	return true


func _find_button(node: Node, text: String) -> Button:
	if node is Button and (node as Button).text == text:
		return node as Button
	for child in node.get_children():
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _find_buttons(node: Node, text: String) -> Array[Button]:
	var found: Array[Button] = []
	if node is Button and (node as Button).text == text:
		found.append(node as Button)
	for child in node.get_children():
		found.append_array(_find_buttons(child, text))
	return found


func _label_color(view, text: String) -> Color:
	for label in _find_labels(view):
		if label.text == text:
			return label.get_theme_color("font_color")
	return Color.BLACK


func _has_text_starting(view, prefix: String) -> bool:
	for text in _texts(view):
		if text.begins_with(prefix):
			return true
	return false


func _find_labels(node: Node) -> Array[Label]:
	var found: Array[Label] = []
	if node is Label:
		found.append(node as Label)
	for child in node.get_children():
		found.append_array(_find_labels(child))
	return found


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
