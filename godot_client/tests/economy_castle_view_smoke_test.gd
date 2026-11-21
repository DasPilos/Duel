extends Node

const CASTLE_SCRIPT := preload("res://scripts/economy_castle_view.gd")
const FIXTURE_PATH := "res://tests/fixtures/economy/castle_view_state.json"
const PARTIAL_FIXTURE_PATH := "res://tests/fixtures/economy/castle_population.json"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_constants_and_title()
	_check_formats()
	_check_governor()
	_check_population_list()
	_check_assign_flow()
	_check_recall_and_selection()
	_check_treasury()
	_check_upgrades()
	_check_messages_and_tasks()
	_check_partial_payload()
	await _check_layout_and_refresh()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_castle_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_constants_and_title() -> void:
	_check(CASTLE_SCRIPT.WINDOW_SIZE == Vector2(720, 507), "размер окна 720×507 (1080×760 px Python)")
	_check(CASTLE_SCRIPT.BORDER_COLOR == Color8(197, 164, 103) and CASTLE_SCRIPT.BACKGROUND_COLOR == Color8(24, 27, 25),
		"рамка и фон окна как в Python")
	var view = _new_view()
	_check(view.window_title() == "Замок Радбурка", "до данных заголовок — название замка из Python")
	view.set_state(_state())
	_check(view.window_title() == "Замок Радбурка" and _texts(view).has("Уровень 1"), "заголовок и подпись «Уровень 1»")
	var renamed := _state()
	renamed["castle_name"] = "Замок Тест"
	view.set_state(renamed)
	_check(view.window_title() == "Замок Тест", "заголовок берётся из состояния")
	var labels: Array[String] = []
	for entry in CASTLE_SCRIPT.TABS:
		labels.append(str(entry[1]))
	_check(labels == ["ГУБЕРНАТОР", "НАСЕЛЕНИЕ", "КАЗНА", "ЗАДАНИЯ", "УЛУЧШЕНИЯ"], "пять вкладок с подписями Python по порядку")
	for entry in CASTLE_SCRIPT.TABS:
		_check((view._tab_buttons[entry[0]] as Button).text == entry[1], "кнопка вкладки %s" % entry[1])
	_check(view._tab == "governor" and view._tab_buttons["governor"].button_pressed and view._tab_panels["governor"].visible,
		"по умолчанию открыт ГУБЕРНАТОР")
	_drop(view)


func _check_formats() -> void:
	_check(CASTLE_SCRIPT.format_hms(0) == "00:00:00", "ноль секунд — 00:00:00")
	_check(CASTLE_SCRIPT.format_hms(3661) == "01:01:01", "3661 с — 01:01:01")
	_check(CASTLE_SCRIPT.format_hms(-5) == "00:00:00", "отрицательное время считается нулём")
	_check(CASTLE_SCRIPT.format_hms(360000) == "100:00:00", "часы свыше 99 выводятся целиком, как в Python")


func _check_governor() -> void:
	var view = _new_view()
	view.set_state(_state())
	var texts := _texts(view)
	for expected in ["Ресурс", "Доход в час", "Расход в час", "Тенденция", "Пшеница", "120,0 в час", "90,0 в час",
			"Древесина", "42,5 в час", "12,0 в час", "Мясо", "14,0 в час", "20,0 в час", "Кожа", "6,0 в час", "0,0 в час"]:
		_check(texts.has(expected), "таблица губернатора показывает «%s»" % expected)
	_check(texts.count("Есть небольшой +") == 2 and texts.has("На ап города") and texts.has("Дефицит"),
		"тенденции подписаны как в Python")
	var deficit := _label_with_text(view, "Дефицит")
	_check(deficit != null and deficit.get_theme_color("font_color") == Color8(239, 83, 77), "дефицит окрашен красным, как в Python")
	var ready := _label_with_text(view, "На ап города")
	_check(ready != null and ready.get_theme_color("font_color") == Color8(104, 222, 133), "«На ап города» окрашен зелёным")
	_drop(view)

	var no_flow := _state()
	no_flow.erase("city_resource_income_per_hour")
	no_flow.erase("city_resource_consumption_per_hour")
	view = _new_view()
	view.set_state(no_flow)
	_check(_texts(view).has("Нет текущего движения ресурсов."), "без движения ресурсов — строка Python")
	_drop(view)

	var no_trend := _state()
	no_trend.erase("city_resource_trend")
	view = _new_view()
	view.set_state(no_trend)
	_check(_texts(view).count("—") == 4 and _texts(view).has("120,0 в час"),
		"без тенденций строки остаются, тенденция выводится прочерком")
	_drop(view)


func _check_population_list() -> void:
	var view = _new_view()
	view.set_state(_state())
	var summary := _label_with_text(view, "Население 6 / 10 (запасов на 2 дня)")
	_check(summary != null, "сводка населения как в Python")
	_check(summary != null and summary.get_theme_color("font_color") == Color8(232, 191, 67), "сводка окрашена жёлтой зоной")
	_check(_label_with_text(view, "Население сытое : 00:21:00") != null, "таймер жёлтой зоны «Население сытое : 00:21:00»")
	var rows := _rows(view)
	_check(rows.size() == 6, "шесть горожан в списке")
	var names: Array[String] = []
	for row in rows:
		names.append(_row_name(row))
	_check(names == ["Агата", "Фрида", "Дорн", "Бран", "Лира", "Эльм"],
		"свободные горожане первыми, внутри групп порядок сохраняется")
	var buttons: Array[String] = []
	for row in rows:
		buttons.append(_row_button(row).text)
	_check(buttons == ["НАЗНАЧИТЬ", "НАЗНАЧИТЬ", "НАЗНАЧИТЬ", "ДОМОЙ", "ДОМОЙ", "В ПУТИ ДОМОЙ"],
		"кнопки строк: НАЗНАЧИТЬ, ДОМОЙ, В ПУТИ ДОМОЙ")
	_check(_row_meter(rows[0]).text == "Сытность 62%" and _row_meter(rows[0]).get_theme_color("font_color") == Color8(72, 174, 95),
		"сытность выше 30 % зелёная")
	_check(_row_meter(rows[2]).text == "Сытность 9%" and _row_meter(rows[2]).get_theme_color("font_color") == Color8(226, 66, 58),
		"сытность до 10 % красная")
	_check(_row_death(rows[2]).text == "Смерть через 01:30:00", "смерть через 01:30:00 при сытности до 10 %")
	_check(_row_bar(rows[2]).value == 9.0, "шкала сытности заполнена на 9 %")
	_check(_row_meter(rows[5]).text == "Сильный голод 35%" and _row_bar(rows[5]).value == 35.0,
		"при сытности 0 показывается сильный голод и шкала по голоду")
	_check(_row_work(rows[3]).text == "Ферма · Занят", "работа: здание · статус")
	_check(_row_work(rows[4]).text == "Лесопилка · В пути 00:01:34", "путь показывает остаток времени")
	_check(_row_work(rows[5]).text == "Зверинец · Возвращается 00:00:39", "возвращение с временем в пути")
	view._received_msec -= 4500
	view._update_travel_labels()
	_check(_row_work(rows[4]).text == "Лесопилка · В пути 00:01:29", "остаток пути уменьшается между обновлениями")
	_drop(view)

	var convoy := _state()
	convoy["citizens"][0]["work_status"] = "Ведёт повозку"
	convoy["citizens"][0]["job_building"] = ""
	view = _new_view()
	view.set_state(convoy)
	var convoy_row: Node = null
	for row in _rows(view):
		if _row_name(row) == "Агата":
			convoy_row = row
	var convoy_button := _row_button(convoy_row)
	_check(convoy_button.text == "В РЕЙСЕ" and convoy_button.disabled, "возница занят рейсом и не назначается")
	_drop(view)

	var red := _state()
	red["food_zone"] = "red"
	red["departure_eta_seconds"] = 3600
	view = _new_view()
	view.set_state(red)
	var departure := _label_with_text(view, "Горожанин покинет город : 01:00:00")
	_check(departure != null and departure.get_theme_color("font_color") == Color8(218, 69, 65),
		"красная зона: горожанин покинет город, красный таймер")
	red["food_zone"] = "green"
	red["new_citizen_eta_seconds"] = null
	view.set_state(red)
	_check(_label_with_text(view, "Новый горожанин прибудет через: --:--:--") != null, "нет ETA — прочерки таймера")
	red.erase("food_zone")
	view.set_state(red)
	_check(not view._zone_timer.visible and view._summary_label.get_theme_color("font_color") == CASTLE_SCRIPT.ZONE_DEFAULT_COLOR,
		"без food_zone таймер скрыт, сводка нейтрального цвета")
	_drop(view)


func _check_assign_flow() -> void:
	var view = _new_view()
	var log := _record(view)
	view.set_state(_state())
	var rows := _rows(view)
	_press(_row_button(rows[0]))
	_check(view._selected_citizen_id == 11 and view._worksite_section.visible, "НАЗНАЧИТЬ выбирает свободного горожанина")
	_check(_texts(view).has("Куда отправить:") and _texts(view).has("Свободно: 2 · занято: 1")
		and _texts(view).has("Горный разлом"), "места работы берутся из worksites")
	_press(_button_with_caption(view, "Горный разлом"))
	_check(view._message_label.visible and view._message_label.text == "Нет свободных рабочих мест на этом объекте."
		and view._message_label.get_theme_color("font_color") == CASTLE_SCRIPT.MESSAGE_ERROR_COLOR and not view._confirm_panel.visible,
		"полный объект даёт сообщение, подтверждения нет")
	_press(_button_with_caption(view, "Крестьянское поселение"))
	_check(view._confirm_panel.visible and _label_with_text(view, "Отправить Агата на работу?") != null
		and _label_with_text(view, "Крестьянское поселение · путь в одну сторону: 00:05:00") != null,
		"подтверждение отправки с именем и временем пути")
	_press(view._confirm_ok)
	_check(log.size() == 1 and log[0][0] == "assign_citizen"
		and log[0][1] == {"citizen_id": 11, "worksite_key": "farm", "slot_index": 1},
		"ОТПРАВИТЬ шлёт assign_citizen с местом и первым свободным слотом")
	_check(not view._confirm_panel.visible, "после подтверждения окно закрыто")

	_press(_row_button(rows[1]))
	_press(_button_with_caption(view, "Крестьянское поселение"))
	_press(_button_with_text(view, "ОТМЕНА"))
	_check(not view._confirm_panel.visible and log.size() == 1, "ОТМЕНА закрывает подтверждение без запроса")

	_press(_row_button(rows[2]))
	_check(view._message_label.text == "Горожанин сейчас не свободен." and not view._confirm_panel.visible,
		"занятый горожанин не назначается")
	_drop(view)


func _check_recall_and_selection() -> void:
	var view = _new_view()
	var log := _record(view)
	view.set_state(_state())
	var rows := _rows(view)
	_press(_row_button(rows[3]))
	_check(view._confirm_panel.visible and _label_with_text(view, "Вернуть Бран в город?") != null
		and _label_with_text(view, "Путь домой: 00:05:00") != null, "ДОМОЙ открывает подтверждение возврата")
	_press(view._confirm_ok)
	_check(log.size() == 1 and log[0][0] == "recall_citizen" and log[0][1] == {"citizen_id": 14},
		"ВЕРНУТЬ шлёт recall_citizen")
	_press(_row_button(rows[5]))
	_check(view._message_label.text == "Горожанин уже возвращается в город." and not view._confirm_panel.visible,
		"возвращающийся горожанин не отзывается повторно")
	_press(_row_button(rows[0]))
	var busy := _state()
	busy["citizens"][0]["job_building"] = "farm"
	view.set_state(busy)
	_check(view._selected_citizen_id == -1 and not view._worksite_section.visible,
		"выбор сбрасывается, если горожанин уже занят")
	_drop(view)


func _check_treasury() -> void:
	var view = _new_view()
	var log := _record(view)
	view.set_state(_state())
	var coins: Array[String] = []
	for entry in view._coin_row.get_children():
		coins.append((entry.get_child(1) as Label).text)
	_check(coins == ["1250", "36", "2"], "казна: медь, серебро, золото как в Python")
	_check(_label_with_text(view, "Городская казна:") != null, "заголовок казны")
	_check(view._mayor_label.visible and _label_with_text(view, "Твой вклад: 18 серебра (можно забрать только свой вклад)") != null,
		"строка мэра и личный вклад")
	_check(_label_with_text(view, "До сбора налогов: 00:22:00 (ожидается: 12 серебра)") != null, "налоги с таймером")
	_press(_button_with_text(view, "ПОПОЛНИТЬ КАЗНУ"))
	_press(_button_with_text(view, "ВЗЯТЬ С КАЗНЫ"))
	_check(log.size() == 2 and log[0] == ["treasury_deposit", {"maximum_copper": 500}]
		and log[1] == ["treasury_withdraw", {"maximum_copper": 1800}],
		"кнопки казны передают максимум перевода: взнос из личной меди, выдача из вклада")
	var empty := _state()
	empty["personal_currency_copper"] = 0
	view.set_state(empty)
	_press(_button_with_text(view, "ПОПОЛНИТЬ КАЗНУ"))
	_check(log.size() == 2 and view._message_label.text == "Нет доступных монет для перевода.",
		"без монет перевод не открывается, как в Python")
	var commoner := _state()
	commoner["is_mayor"] = false
	view.set_state(commoner)
	_check(not view._mayor_label.visible, "строка мэра скрыта у обычного игрока")
	_drop(view)


func _check_upgrades() -> void:
	var view = _new_view()
	var log := _record(view)
	view.set_state(_state())
	_check(_label_with_text(view, "Улучшения замка") != null, "заголовок улучшений")
	_check(view._upgrade_cards.get_child_count() == 2, "карточки улучшений из состояния")
	var texts := _texts(view)
	_check(texts.has("Требование: Нет") and texts.has("Результат: Налог с горожан +10 медн.")
		and texts.has("Время улучшения: 01:20:00"), "карточка Казначейского указа")
	_check(texts.has("/ 5 серебра") and texts.has("310/30 древесины") and texts.has("18"),
		"цена, древесина склада и личный вклад в серебре")
	_check(_label_with_text(view, "Осталось: 00:40:00") != null, "идущее улучшение показывает остаток")
	_press(_button_with_text(view, "НАЧАТЬ"))
	_check(log.size() == 1 and log[0] == ["upgrade_start", {"upgrade_id": "treasury_edict"}],
		"НАЧАТЬ шлёт upgrade_start с id улучшения замка")
	var poor := _state()
	poor["upgrades"][0]["silver_cost"] = 50
	view.set_state(poor)
	var locked := _button_with_text(view, "НЕДОСТАТОЧНО")
	_check(locked != null and locked.disabled, "не хватает серебра — «НЕДОСТАТОЧНО» отключена")
	var done := _state()
	done["upgrades"][1]["is_active"] = false
	done["upgrades"][1]["is_complete"] = true
	view.set_state(done)
	_check(_label_with_text(view, "УСТАНОВЛЕНО") != null, "готовое улучшение помечено УСТАНОВЛЕНО")
	_drop(view)


func _check_messages_and_tasks() -> void:
	var view = _new_view()
	view.set_state(_state())
	_check(_texts(view).has("Заданий пока нет."), "вкладка заданий — заглушка Python")
	view.set_message("Горожанин отправлен к месту работы.", false)
	_check(view._message_label.visible and view._message_label.get_theme_color("font_color") == CASTLE_SCRIPT.MESSAGE_OK_COLOR,
		"успешное сообщение окрашено отдельно")
	view.set_message("Ошибка запроса", true)
	_check(view._message_label.get_theme_color("font_color") == CASTLE_SCRIPT.MESSAGE_ERROR_COLOR,
		"ошибка окрашена цветом Python")
	view.set_message("", false)
	_check(not view._message_label.visible, "пустой текст скрывает строку статуса")
	_drop(view)


func _check_partial_payload() -> void:
	var view = _new_view()
	view.set_state(_load(PARTIAL_FIXTURE_PATH))
	_check(_label_with_text(view, "Население 2 / 6 (в городе достаточно еды для роста)") != null,
		"частичный ответ: сводка без зоны")
	_check(not view._zone_timer.visible and view._summary_label.get_theme_color("font_color") == CASTLE_SCRIPT.ZONE_DEFAULT_COLOR,
		"частичный ответ без food_zone: таймер скрыт, цвет нейтральный")
	_check(_texts(view).has("Нет текущего движения ресурсов."), "частичный ответ без ресурсов: пустая строка")
	_check(_texts(view).has("Твой вклад: — (можно забрать только свой вклад)"), "нет personal_treasury_text — прочерк")
	_check(_texts(view).has("Требование: —") and _texts(view).has("Результат: —"), "нет полей улучшения — прочерки")
	_check(_button_with_text(view, "НЕДОСТАТОЧНО") != null, "без серебра и древесины улучшение не начинается")
	var rows := _rows(view)
	_check(rows.size() == 2 and _row_death(rows[1]).text == "Смерть через 02:00:00", "два горожанина, смерть по ETA")
	_drop(view)


func _check_layout_and_refresh() -> void:
	var view = _new_view()
	view.set_state(_state())
	var log := _record(view)
	var widest := 0.0
	var tallest := 0.0
	for entry in CASTLE_SCRIPT.TABS:
		_press(view._tab_buttons[entry[0]])
		await get_tree().process_frame
		var minimum: Vector2 = view.get_combined_minimum_size()
		widest = maxf(widest, minimum.x)
		tallest = maxf(tallest, minimum.y)
	_check(widest <= 680.0, "вид помещается в ширину окна (680 ед.), минимум %.0f" % widest)
	_check(tallest <= 433.0, "вид помещается в высоту окна (433 ед.), минимум %.0f" % tallest)
	view._process(CASTLE_SCRIPT.REFRESH_SECONDS)
	_check(log.size() == 1 and log[0][0] == "refresh", "раз в 5 с вид просит обновление состояния")
	_drop(view)


func _load(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary and parsed.get("population") is Dictionary:
		return parsed["population"]
	_check(false, "фикстура %s читается как объект с полем population" % path)
	return {}


func _state() -> Dictionary:
	return _load(FIXTURE_PATH).duplicate(true)


func _new_view():
	var view = CASTLE_SCRIPT.new()
	add_child(view)
	view.set_process(false)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _record(view) -> Array:
	var log: Array = []
	view.action_requested.connect(func(action: String, payload: Dictionary) -> void:
		log.append([action, payload]))
	return log


func _press(button: Button) -> void:
	button.pressed.emit()


func _rows(view) -> Array:
	return view._citizen_rows.get_children()


func _row_line(row: Node) -> HBoxContainer:
	return row.get_child(0) as HBoxContainer


func _row_name(row: Node) -> String:
	return (_row_line(row).get_child(1) as Label).text


func _row_meter(row: Node) -> Label:
	return _row_line(row).get_child(2).get_child(0) as Label


func _row_bar(row: Node) -> ProgressBar:
	return _row_line(row).get_child(2).get_child(1) as ProgressBar


func _row_death(row: Node) -> Label:
	return _row_line(row).get_child(3) as Label


func _row_work(row: Node) -> Label:
	return _row_line(row).get_child(4) as Label


func _row_button(row: Node) -> Button:
	return _row_line(row).get_child(5) as Button


func _nodes(root: Node) -> Array:
	var found: Array = []
	_collect(root, found)
	return found


func _collect(node: Node, found: Array) -> void:
	if node is Label or node is Button:
		found.append(node)
	for child in node.get_children():
		_collect(child, found)


func _texts(root: Node) -> Array[String]:
	var found: Array[String] = []
	for node in _nodes(root):
		found.append(node.text)
	return found


func _label_with_text(root: Node, text: String) -> Label:
	for node in _nodes(root):
		if node is Label and node.text == text:
			return node
	return null


func _button_with_text(root: Node, text: String) -> Button:
	for node in _nodes(root):
		if node is Button and node.text == text:
			return node
	return null


func _button_with_caption(root: Node, caption: String) -> Button:
	for node in _nodes(root):
		if node is Button and _texts(node).has(caption):
			return node
	return null


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
