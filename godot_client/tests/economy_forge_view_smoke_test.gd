extends Node

const FORGE_SCRIPT := preload("res://scripts/economy_forge_view.gd")
const FIXTURE_PATH := "res://tests/fixtures/economy/forge_state.json"
# Рецепты как в Python (core/forge_recipes.py и format_forge_time): id, название, материалы, время.
const EXPECTED_RECIPES := [
	[90, "Старый серп", "Древесина ×5", "12 м"],
	[91, "Топор лесоруба", "Древесина ×5", "12 м"],
	[92, "Кирка", "Древесина ×5", "12 м"],
	[93, "Разделочный нож", "Древесина ×5", "12 м"],
	[23, "Дубина", "Древесина ×5", "18 м"],
	[24, "Простой лук", "Древесина ×4", "16 м"],
	[25, "Деревянный посох", "Древесина ×5", "16 м"],
	[20, "Железный меч", "Железо ×3", "30 м"],
	[22, "Кинжал", "Железо ×2", "20 м"],
	[21, "Стальной меч", "Сталь ×3", "60 м"],
	[39, "Деревянный щит", "Древесина ×4", "21 м"],
	[38, "Круглый щит", "Древесина ×4", "25 м"],
	[73, "Железо", "Железная руда ×1, Древесина ×1", "30 м"],
	[74, "Сталь", "Железо ×1, Уголь ×1", "40 м"],
]

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_constants()
	_check_tabs_and_title()
	_check_closed_and_upgrade_tabs()
	_check_recipe_grid()
	_check_queue_slots_and_total()
	_check_craft_states()
	_check_create_order_action()
	_check_collect_order_action()
	_check_info_popup()
	_check_popup_leaves_with_view()
	_check_recipe_data()
	_check_messages()
	await _check_layout_fit()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_forge_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_constants() -> void:
	_check(FORGE_SCRIPT.WINDOW_SIZE == Vector2(1066, 600), "размер окна 1600×900 px Python, переведённый в единицы Godot")
	_check(FORGE_SCRIPT.BORDER_COLOR == Color8(255, 140, 50) and FORGE_SCRIPT.BACKGROUND_COLOR == Color8(24, 20, 20),
		"рамка и фон окна как в Python")


func _check_tabs_and_title() -> void:
	var view = _new_view()
	_check(view.window_title() == "Кузница", "заголовок окна как в Python")
	view.set_state(_base_state())
	var labels: Array[String] = []
	for button in view._tab_buttons.values():
		labels.append(button.text)
	_check(labels == ["ОРУЖИЕ", "ЩИТЫ", "ШЛЕМЫ", "ДОСПЕХИ", "ПЕРЧАТКИ", "ЛАТЫ", "ОБУВЬ", "ПЛАВИЛЬНЯ", "УЛУЧШЕНИЯ", "СКЛАД (2)"],
		"десять вкладок в порядке Python, у склада счётчик готовых заказов")
	_check(view._tab == "weapons" and view._tab_buttons["weapons"].button_pressed, "по умолчанию открыта вкладка оружия")
	_check(_texts(view).has("ОРУЖЕЙНАЯ КУЗНИЦА • УРОВЕНЬ 1"), "подзаголовок с уровнем 1 по умолчанию")
	view.set_state(_with(_base_state(), {"level": 3}))
	_check(_texts(view).has("ОРУЖЕЙНАЯ КУЗНИЦА • УРОВЕНЬ 3"), "уровень берётся из состояния")
	view.set_state(_with(_base_state(), {"warehouse": []}))
	_check(view._tab_buttons["storage"].text == "СКЛАД", "без готовых заказов счётчика нет")
	_drop(view)

	var detached = FORGE_SCRIPT.new()
	detached.set_state(_base_state())
	_check(detached._queue.size() == 3, "состояние принимается до добавления вида в дерево")
	detached.free()


func _check_closed_and_upgrade_tabs() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	for entry in [["helmets", "ШЛЕМЫ"], ["armor", "ДОСПЕХИ"], ["gloves", "ПЕРЧАТКИ"], ["plates", "ЛАТЫ"], ["shoes", "ОБУВЬ"]]:
		_open_tab(view, entry[0])
		_check(_texts(view).has("РАЗДЕЛ «%s» ЗАКРЫТ" % entry[1]) and view._craft_buttons.is_empty(),
			"вкладка «%s» закрыта без рецептов, как в Python" % entry[1])
	_check(_texts(view).has("Ковка элементов брони и защитной экипировки открывается на 2-м уровне кузницы.")
		and _texts(view).has("Развивайте город и улучшайте здания во вкладке «УЛУЧШЕНИЯ»."),
		"закрытая вкладка показывает два пояснения Python")
	_open_tab(view, "upgrades")
	_check(_texts(view).has("УЛУЧШЕНИЕ КУЗНИЦЫ: УРОВЕНЬ 1 -> 2") and view._craft_buttons.is_empty(),
		"улучшения — заглушка с текстом Python")
	_drop(view)


func _check_recipe_grid() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	var grid := _grid_of(view)
	_check(grid != null and grid.columns == 4, "рецепты раскладываются в 4 колонки")
	_check(view._craft_buttons.keys() == [90, 91, 92, 93, 23, 24, 25, 20, 22, 21], "оружие: десять рецептов в порядке Python")
	_check(FORGE_SCRIPT.GRID_HEIGHT == 2 * FORGE_SCRIPT.CARD_HEIGHT + FORGE_SCRIPT.CARD_GAP_Y and view._tab_scroll.custom_minimum_size.y == FORGE_SCRIPT.GRID_HEIGHT,
		"видимая область рассчитана на две строки карточек, остальные прокручиваются")
	_check(_texts(view).count("Требование: —") == 10 and _texts(view).count("Бафы: —") == 10,
		"в каждой карточке строки Требование и Бафы с прочерком, данных о них нет")
	_check(view._info_buttons.size() == 10 and _texts(view).count("ИНФО") == 10, "у каждой карточки кнопка ИНФО")
	_open_tab(view, "shields")
	_check(view._craft_buttons.keys() == [39, 38], "щиты: два рецепта")
	_open_tab(view, "smelting")
	_check(view._craft_buttons.keys() == [73, 74], "плавильня: два рецепта")
	_drop(view)


func _check_queue_slots_and_total() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_check(view._queue_title.text == "ПРОЦЕСС РАБОТЫ КУЗНИЦЫ • ОЧЕРЕДЬ: 3 / 5 (МАКС. 5 ЗАКАЗОВ)", "заголовок очереди как в Python")
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: 46:00", "общее время: 420 + 1080 + 1260 с = 46:00")
	_check(view._work_title.text == "В РАБОТЕ: Старый серп" and view._work_owner.text == "Заказчик: Тестовый герой",
		"в работе первый заказ и его заказчик")
	_check(view._work_time.text == "До готовности: 07:00" and view._progress_percent.text == "41% (07:00)",
		"остаток 07:00 и прогресс 41%, как в Python")
	_check(view._slots.size() == 5, "пять слотов очереди")
	_check(_slot_text(view, 0, "badge") == "[1] В РАБОТЕ" and _slot_text(view, 1, "badge") == "[2] В ОЧЕРЕДИ"
		and _slot_text(view, 2, "badge") == "[3] В ОЧЕРЕДИ", "первые три слота заняты, первый в работе")
	_check(_slot_text(view, 3, "badge") == "[4] СВОБОДНЫЙ СЛОТ" and _slot_text(view, 4, "badge") == "[5] СВОБОДНЫЙ СЛОТ",
		"слоты 4 и 5 свободны")
	_check(not view._slots[3]["busy"].visible and view._slots[3]["free"].visible, "свободный слот показывает подсказку")
	_check(_slot_text(view, 0, "timer") == "07:00" and _slot_text(view, 1, "timer") == "18:00" and _slot_text(view, 2, "timer") == "21:00",
		"таймеры слотов как в Python")
	_check(_slot_text(view, 2, "name") == "Деревянный щи" and _slot_text(view, 2, "owner") == "Игрок: Тестовый ге",
		"название и заказчик в слоте обрезаются, как [:13] и [:11] в Python")
	view._process(60.0)
	_check(view._work_time.text == "До готовности: 06:00" and view._progress_percent.text == "50% (06:00)",
		"через 60 с осталось 06:00 и прогресс 50%")
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: 45:00" and _slot_text(view, 0, "timer") == "06:00",
		"общее время и таймер первого слота идут вместе")
	view.set_state(_state_with_queue(0))
	_check(view._work_title.text == "Горн свободен. Кузнец ждет заказов" and not view._progress_box.visible
		and view._work_hint.visible, "пустая мастерская показывает заглушку Python")
	_check(view._queue_title.text == "ПРОЦЕСС РАБОТЫ КУЗНИЦЫ • ОЧЕРЕДЬ: 0 / 5 (МАКС. 5 ЗАКАЗОВ)"
		and view._queue_total.text == "ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: 00:00", "пустая очередь: 0 / 5 и 00:00")
	view.set_state(_state_with_queue(5))
	_check(view._queue_total.text == "ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: 3 ч 20 мин" and _slot_text(view, 4, "badge") == "[5] В ОЧЕРЕДИ",
		"полная очередь: 5 заказов по 40 мин, итог 3 ч 20 мин")
	_drop(view)


func _check_craft_states() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_check(view._craft_buttons[90].text == "ВЫКОВАТЬ" and not view._craft_buttons[90].disabled,
		"без проверки материалов кнопка доступна: ВЫКОВАТЬ")
	view.set_state(_state_with_queue(5))
	_check(view._craft_buttons[90].text == "ОЧЕРЕДЬ (5/5)" and view._craft_buttons[90].disabled, "полная очередь: ОЧЕРЕДЬ (5/5), кнопка выключена")
	view.set_state(_with(_state_with_queue(5), {"inventory": []}))
	_check(view._craft_buttons[20].text == "ОЧЕРЕДЬ (5/5)", "полная очередь важнее нехватки материалов, как в Python")
	view.set_state(_with(_base_state(), {"inventory": []}))
	_check(view._craft_buttons[90].text == "НЕТ МАТЕРИАЛОВ" and view._craft_buttons[90].disabled, "без древесины: НЕТ МАТЕРИАЛОВ")
	_check(view._craft_buttons[20].text == "НЕТ МАТЕРИАЛОВ", "без железа: НЕТ МАТЕРИАЛОВ")
	view.set_state(_with(_base_state(), {"inventory": [{"item_id": 60, "quantity": 4}]}))
	_check(view._craft_buttons[24].text == "ВЫКОВАТЬ" and view._craft_buttons[90].text == "НЕТ МАТЕРИАЛОВ",
		"четыре древесины хватает на лук (4), но не на серп (5)")
	view.set_state(_with(_base_state(), {"inventory": [{"item_id": 60, "quantity": 3}, {"item_id": 60, "quantity": 2}]}))
	_check(view._craft_buttons[90].text == "ВЫКОВАТЬ", "древесина из нескольких стеков складывается")
	view.set_state(_with(_base_state(), {"inventory": [{"item_id": 73, "quantity": 2}]}))
	_check(view._craft_buttons[20].text == "НЕТ МАТЕРИАЛОВ" and view._craft_buttons[22].text == "ВЫКОВАТЬ",
		"два железа хватает на кинжал (2), но не на меч (3)")
	view.set_state(_with(_base_state(), {"character": {"copper": 39, "silver": 0, "gold": 0}}))
	_check(view._craft_buttons[90].text == "НЕТ МАТЕРИАЛОВ" and view._craft_buttons[20].text == "ВЫКОВАТЬ",
		"39 меди не хватает на рецепт за 40 меди; бесплатный рецепт доступен")
	view.set_state(_with(_base_state(), {"character": {"copper": 0, "silver": 1, "gold": 0}}))
	_check(view._craft_buttons[90].text == "ВЫКОВАТЬ" and view._craft_buttons[23].text == "НЕТ МАТЕРИАЛОВ",
		"одного серебра (100 меди) хватает на серп, но не на дубину (300 меди)")
	view.set_state(_with(_base_state(), {"inventory": [{"item_id": 60, "quantity": 5}]}))
	_check(view._craft_buttons[23].text == "ВЫКОВАТЬ", "без поля character деньги не проверяются")
	view.set_state(_base_state())
	_drop(view)


func _check_create_order_action() -> void:
	var view = _new_view()
	var actions: Array = []
	var record := func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload])
	view.action_requested.connect(record)
	view.set_state(_base_state())
	view._craft_buttons[90].pressed.emit()
	_check(actions.size() == 1 and actions[0][0] == "create_order" and actions[0][1] == {"item_id": 90},
		"«ВЫКОВАТЬ» шлёт create_order с item_id рецепта")
	_check(typeof(actions[0][1]["item_id"]) == TYPE_INT, "item_id уходит целым числом")
	view.set_state(_with(_base_state(), {"inventory": []}))
	view._craft_buttons[90].pressed.emit()
	_check(actions.size() == 1, "кнопка «НЕТ МАТЕРИАЛОВ» запрос не шлёт")
	view.set_state(_state_with_queue(5))
	view._craft_buttons[90].pressed.emit()
	_check(actions.size() == 1, "при полной очереди запрос не шлётся")
	view.set_state(_base_state())
	view._info_buttons[90].pressed.emit()
	_find_button(view._overlay, "ВЫКОВАТЬ").pressed.emit()
	_check(actions.size() == 2 and actions[1][0] == "create_order" and actions[1][1] == {"item_id": 90},
		"«ВЫКОВАТЬ» в окне рецепта шлёт create_order")
	_check(view._overlay == null, "окно рецепта закрывается после заказа")
	_drop(view)


func _check_collect_order_action() -> void:
	var view = _new_view()
	var actions: Array = []
	var record := func(action: String, payload: Dictionary) -> void:
		actions.append([action, payload])
	view.action_requested.connect(record)
	view.set_state(_base_state())
	_open_tab(view, "storage")
	_check(view._collect_buttons.size() == 2 and _texts(view).count("ГОТОВО К ВЫДАЧЕ") == 2, "склад: карточка и кнопка на каждый готовый заказ")
	_check(_texts(view).has("Вес: 1.5 кг") and _texts(view).has("Лук из ясеня, готов к выдаче"),
		"вес и описание берутся из состояния")
	view._collect_buttons[301].pressed.emit()
	_check(actions.size() == 1 and actions[0][0] == "collect_order" and actions[0][1] == {"order_id": 301},
		"«ЗАБРАТЬ В РЮКЗАК» шлёт collect_order с order_id")
	_check(typeof(actions[0][1]["order_id"]) == TYPE_INT, "order_id уходит целым числом")
	view.set_state(_with(_base_state(), {"warehouse": []}))
	_check(_texts(view).has("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ") and view._collect_buttons.is_empty(), "пустой склад как в Python")
	_drop(view)


func _check_info_popup() -> void:
	var view = _new_view()
	var children_before: int = view.get_child_count()
	view.set_state(_base_state())
	_check(view._overlay == null, "окно рецепта закрыто по умолчанию")
	view._info_buttons[90].pressed.emit()
	_check(view._overlay != null and view._overlay.get_parent() == get_tree().root and view._popup_title.text == "Старый серп",
		"ИНФО открывает окно рецепта с названием поверх экрана, на корне окна")
	_check(view.get_child_count() == children_before, "окно рецепта не добавляет детей виду, раскладка прокрутки не меняется")
	_check(not _texts(view).has("Информация о предмете кузницы") and _texts(view._overlay).has("Информация о предмете кузницы"),
		"текст окна рецепта находится в окне, а не в виде")
	_check(_find_button(view._overlay, "ВЫКОВАТЬ") != null and _find_button(view._overlay, "ОТМЕНА") != null,
		"в окне рецепта есть ВЫКОВАТЬ и ОТМЕНА")
	_check(view._popup_values.size() == 9, "девять строк параметров, как в Python")
	_check(view._popup_values["Слот"].text == "—" and view._popup_values["Урон:"].text == "—" and view._popup_values["Бафы"].text == "—",
		"строки без данных показывают прочерк")
	_check(view._popup_values["Цена:"].text == "40 меди", "цена за изготовление в меди")
	_find_button(view._overlay, "ОТМЕНА").pressed.emit()
	_check(view._overlay == null, "ОТМЕНА закрывает окно")
	view._info_buttons[23].pressed.emit()
	_check(view._popup_values["Цена:"].text == "3 серебра", "300 меди показываются как 3 серебра")
	view._info_buttons[20].pressed.emit()
	_check(view._popup_values["Цена:"].text == "без дополнительной платы", "бесплатный рецепт без приписки о цене")
	_find_button(view._overlay, "ОТМЕНА").pressed.emit()
	_check(view._overlay == null, "ОТМЕНА закрывает окно рецепта")
	view._info_buttons[90].pressed.emit()
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	view._overlay.get_child(0).gui_input.emit(click)
	_check(view._overlay == null, "щелчок по затемнению закрывает окно рецепта")
	view.set_state(_with(_base_state(), {"inventory": []}))
	view._info_buttons[90].pressed.emit()
	_check(_find_button(view._overlay, "НЕТ МАТЕРИАЛОВ").disabled, "в окне рецепта та же проверка материалов")
	view.set_state(_base_state())
	_check(not _find_button(view._overlay, "ВЫКОВАТЬ").disabled, "после получения состояния с материалами окно обновляется")
	view._close_info()
	_drop(view)


func _check_popup_leaves_with_view() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	view._info_buttons[90].pressed.emit()
	var overlay: Control = view._overlay
	_drop(view)
	_check(overlay.is_queued_for_deletion(), "вид, закрытый при открытом окне рецепта, убирает окно с экрана")



func _check_recipe_data() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	for expected in EXPECTED_RECIPES:
		var recipe_id: int = expected[0]
		var tab := "weapons"
		if [39, 38].has(recipe_id):
			tab = "shields"
		elif [73, 74].has(recipe_id):
			tab = "smelting"
		_open_tab(view, tab)
		view._info_buttons[recipe_id].pressed.emit()
		_check(view._popup_title.text == expected[1] and view._popup_values["Рецепт:"].text == expected[2]
			and view._popup_values["Изготовления:"].text == expected[3],
			"рецепт %s: название, материалы и время как в Python" % expected[1])
		view._close_info()
	_drop(view)


func _check_messages() -> void:
	var view = _new_view()
	view.set_message("Заказ принят в кузницу! Кузнец приступил к работе.", false)
	_check(view._message_label.visible and view._message_label.text.begins_with("Заказ принят"), "сообщение показывается")
	_check(view._message_label.get_theme_color("font_color") == FORGE_SCRIPT.MESSAGE_OK_COLOR, "успех окрашен цветом Python")
	view.set_message("Очередь кузницы заполнена (5 из 5)", true)
	_check(view._message_label.get_theme_color("font_color") == FORGE_SCRIPT.MESSAGE_ERROR_COLOR, "ошибка окрашена цветом Python")
	view._process(3.5)
	_check(view._message_label.visible, "сообщение держится 4 с, как в Python")
	view._process(0.6)
	_check(not view._message_label.visible, "через 4 с сообщение скрывается")
	view.set_message("Тест", false)
	view.set_message("", false)
	_check(not view._message_label.visible, "пустой текст скрывает строку статуса")
	_drop(view)


func _check_layout_fit() -> void:
	var view = _new_view()
	view.set_state(_base_state())
	_open_tab(view, "weapons")
	await get_tree().process_frame
	var minimum: Vector2 = view.get_combined_minimum_size()
	_check(minimum.x <= FORGE_SCRIPT.WINDOW_SIZE.x - 24.0 and minimum.y <= FORGE_SCRIPT.WINDOW_SIZE.y - 64.0,
		"вид помещается в окно родителя: %.0f × %.0f" % [minimum.x, minimum.y])
	_drop(view)


func _new_view():
	var view = FORGE_SCRIPT.new()
	add_child(view)
	view.set_process(false)
	return view


func _drop(view) -> void:
	remove_child(view)
	view.free()


func _open_tab(view, key: String) -> void:
	view._tab_buttons[key].pressed.emit()


func _grid_of(view) -> GridContainer:
	if view._tab_body.get_child_count() == 0:
		return null
	return view._tab_body.get_child(0) as GridContainer


func _slot_text(view, index: int, key: String) -> String:
	return (view._slots[index][key] as Label).text


func _fixture() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_PATH))
	if parsed is Dictionary:
		return parsed
	_check(false, "фикстура %s читается как JSON-объект" % FIXTURE_PATH)
	return {}


func _base_state() -> Dictionary:
	return _fixture().duplicate(true)


func _with(state: Dictionary, changes: Dictionary) -> Dictionary:
	var result := state.duplicate(true)
	result.merge(changes, true)
	return result


func _state_with_queue(count: int) -> Dictionary:
	var state := _base_state()
	var queue: Array = []
	for index in range(count):
		queue.append({"order_id": 500 + index, "owner_character_id": 1, "owner_name": "Тестовый герой",
			"item_id": 90, "item_name": "Старый серп", "status": "working" if index == 0 else "queued",
			"position": index + 1, "duration_seconds": 2400, "seconds_left": 2400})
	state["queue"] = queue
	state["queue_count"] = count
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


func _find_button(root: Node, text: String) -> Button:
	if root is Button and (root as Button).text == text:
		return root as Button
	for child in root.get_children():
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
