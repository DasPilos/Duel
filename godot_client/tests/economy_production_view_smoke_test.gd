extends Node

# Производственное окно (economy_production_view.gd) без сети: строки мест и кнопки, подтверждение полосой,
# отказ при полном складе, карточки улучшений фермы и лесопилки, прежний блок УЛУЧШИТЬ у других зданий,
# холст участков с кликами, таймеры ресурсов в строках и описание следующего уровня.
const VIEW_SCRIPT := preload("res://scripts/economy_production_view.gd")
const RULES := preload("res://scripts/economy_production_rules.gd")
const RIFT_NEXT_DESC := "Горожанин: камень 1 ед. за 200 с, железная руда 1 ед. за 300 с, мифриловая руда 1 ед. за 900 с, обсидиановая порода 1 ед. за 1400 с. Вместимость каждого товара: 800. Горожан: 3."
const PIT_NEXT_DESC := "Горожанин: уголь 1 ед. за 600 с. Бонусный самоцвет: шанс 0.69% на каждую добытую единицу угля (гагат 65%, малахит 35%; каждый 1 кг). Вместимость каждого товара: 1400. Горожан: 5."

var _failures: Array[String] = []
var _checks := 0
var _actions: Array = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var view = VIEW_SCRIPT.new()
	view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(view)
	view.set_character_id(42)
	view.action_requested.connect(_on_action)
	_check_production_rows(view)
	_check_confirm_strip(view)
	_check_storage_full_click(view)
	_check_plot_canvas(view)
	_check_timer_values(view)
	_check_upgrade_cards(view)
	_check_mountain_rift(view)
	remove_child(view)
	view.free()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("economy_production_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _on_action(action: String, payload: Dictionary) -> void:
	_actions.append([action, payload])


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_production_rows(view) -> void:
	view.select_tab(RULES.TAB_PRODUCTION)
	view.set_state(_state("farm", {}, null))
	_check(_button_texts(view._body) == ["Поставить горожанина", "Встать на добычу", "Снять горожанина", "Закончить работу"],
		"места показывают кнопки: свободное, горожанин, своё место и чужой игрок")
	_check(view._status_label.text == "Работает", "статус «Работает» при занятых местах")
	_check(view._rate_label.text.begins_with("Производство в час:"), "строка производства в час есть")
	_check(_actions.is_empty(), "вкладка производства не шлёт запросов")


func _check_confirm_strip(view) -> void:
	view.set_state(_state("farm", {}, null))
	_find_button(view._body, "Поставить горожанина").pressed.emit()
	_check(view._confirm_strip.visible and view._confirm_label.text == "Поставить горожанина на работу?",
		"найм спрашивает подтверждение полосой")
	_check(_actions.is_empty(), "до подтверждения действие не уходит")
	_find_button(view._confirm_strip, "ОТМЕНА").pressed.emit()
	_check(not view._confirm_strip.visible and _actions.is_empty(), "отмена прячет полосу и не шлёт действие")

	_find_button(view._body, "Снять горожанина").pressed.emit()
	_check(view._confirm_label.text == "Снять горожанина с работы?", "снятие спрашивает подтверждение")
	_find_button(view._confirm_strip, "ПОДТВЕРДИТЬ").pressed.emit()
	_check(_actions.back() == ["fire", {"slot_index": 1}], "подтверждённое снятие шлёт fire с номером места")
	_check(not view._confirm_strip.visible, "после подтверждения полоса скрыта")


func _check_storage_full_click(view) -> void:
	var full := _state("farm", {}, null)
	full["storage"] = {"limit": 100, "wheat": 100}
	view.set_state(full)
	_find_button(view._body, "Встать на добычу").pressed.emit()
	_check(view._message_label.text == RULES.MSG_STORAGE_FULL, "встать на добычу при полном складе даёт сообщение")
	_check(not view._confirm_strip.visible, "при полном складе подтверждение не открывается")


func _check_upgrade_cards(view) -> void:
	_actions.clear()
	view.select_tab(RULES.TAB_UPGRADE)
	_check(_actions.size() == 1 and _actions[0][0] == "refresh", "вкладка УЛУЧШЕНИЕ запрашивает свежее здание")

	view.set_state(_state("farm", {}, null))
	_check(_button_texts(view._body) == ["НАЧАТЬ", "НАЧАТЬ", "СНАЧАЛА ПРЕДЫДУЩИЕ"],
		"на 1 уровне фермы три карточки: две можно начать, одна закрыта")
	_check(_find_buttons(view._body)[2].disabled, "закрытая карточка отключена")
	_find_buttons(view._body)[0].pressed.emit()
	_check(_actions.back() == ["production_upgrade", {"upgrade_id": "ration"}], "кнопка НАЧАТЬ шлёт production_upgrade с id")

	view.set_state(_state("farm", {"ration": true, "wooden_plough": true}, null))
	_check(_button_texts(view._body) == ["НАЧАТЬ"], "после двух улучшений открыто третье, и на нём кнопка НАЧАТЬ")
	_check(_label_texts(view._body).count("УСТАНОВЛЕНО") == 2, "установленные карточки помечены УСТАНОВЛЕНО")

	view.set_state(_state("farm", {}, "ration", 100))
	_check(_label_texts(view._body).has("Осталось: 0 ч 01 м 40 с"), "активное улучшение показывает таймер")
	_check(_button_texts(view._body) == ["ИДЁТ УЛУЧШЕНИЕ", "СНАЧАЛА ПРЕДЫДУЩИЕ"], "пока идёт улучшение, остальные ждут")

	view.set_state(_state("lumber_camp", {"logging_expansion": true}, null, 0, 2))
	_check(_button_texts(view._body).is_empty() and _label_texts(view._body).has("УСТАНОВЛЕНО"),
		"лесопилка 2 уровня: завершённое улучшение без кнопки")
	view.set_state(_state("lumber_camp", {}, null))
	_check(_button_texts(view._body) == ["НАЧАТЬ", "НАЧАТЬ", "СНАЧАЛА ПРЕДЫДУЩИЕ"], "лесопилка 1 уровня: три карточки")


func _check_mountain_rift(view) -> void:
	view.set_state({
		"building": "mountain_rift", "level": 1, "workers": 0, "max_workers": 0,
		"storage": {"limit": 100}, "worker_slots": [],
		"upgrade": {"next_level": 2, "time_seconds": 3600, "ready": true, "in_progress": false,
			"materials": [], "storage_limit": 200},
	})
	_check(_button_texts(view._body) == ["УЛУЧШИТЬ"], "горный разлом по-прежнему показывает УЛУЧШИТЬ")
	_check(_label_texts(view._body).has(RIFT_NEXT_DESC), "улучшение разлома показывает описание следующего уровня")
	view.set_state({
		"building": "black_pit", "level": 3, "workers": 0, "max_workers": 0,
		"storage": {"limit": 100}, "worker_slots": [],
		"upgrade": {"next_level": 4, "time_seconds": 3600, "ready": true, "in_progress": false, "materials": []},
	})
	_check(_label_texts(view._body).has(PIT_NEXT_DESC), "копь показывает бонусный самоцвет следующего уровня")


func _check_plot_canvas(view) -> void:
	view.select_tab(RULES.TAB_PRODUCTION)
	view.set_state(_state("farm", {}, null))
	var canvas = view._plots_view
	_check(canvas != null and canvas.plot_count() == 12, "производство показывает холст из 12 участков фермы")
	_check(_label_texts(view._body).count("Пшеница 2:20") == 3, "в каждом занятом месте таймер ресурса: 2:20 на полном цикле")
	_actions.clear()
	canvas.plot_clicked.emit(0)
	_check(view._confirm_strip.visible and view._confirm_label.text == "Поставить горожанина на работу?",
		"клик по свободному участку открывает найм")
	_find_button(view._confirm_strip, "ПОДТВЕРДИТЬ").pressed.emit()
	_check(_actions.back() == ["hire", {"slot_index": 0}], "подтверждённый найм с клика шлёт hire с местом")
	canvas.plot_removed.emit(0)
	_check(view._confirm_label.text == "Снять горожанина с работы?", "правый клик по участку спрашивает снятие")
	_find_button(view._confirm_strip, "ПОДТВЕРДИТЬ").pressed.emit()
	_check(_actions.back() == ["fire", {"slot_index": 1}], "подтверждённое снятие с участка шлёт fire горожанина")
	canvas.plot_clicked.emit(1)
	_check(view._message_label.text == RULES.MSG_PLOT_FULL, "полный участок: сообщение о свободном месте")
	canvas.plot_removed.emit(1)
	_check(view._message_label.text == RULES.MSG_PLOT_EMPTY, "участок без горожан: сообщение")
	canvas.plot_clicked.emit(2)
	_check(view._message_label.text == "Поле (лён) откроется на 3 уровне", "закрытый участок называет уровень открытия")


func _check_timer_values(view) -> void:
	var state := _state("farm", {}, null)
	state["worker_slots"][1]["timer_sec_by_resource"] = {"wheat": 120}
	state["worker_slots"][1]["resource_progress_sec"] = {"wheat": 30}
	view.set_state(state)
	_check(_label_texts(view._body).has("Пшеница 1:30"), "таймер берёт цикл из места и прогресс сервера: 120 - 30 = 1:30")


func _state(building: String, completed: Dictionary, active: Variant, seconds_left: int = 0, level: int = 1) -> Dictionary:
	var key := "lumber_camp_upgrades" if building == "lumber_camp" else "farm_upgrades"
	var state := {
		"building": building,
		"level": level,
		"workers": 2,
		"max_workers": 4,
		"storage": {"limit": 100, "wheat": 10},
		"storage_full": false,
		"worker_slots": [
			{"slot_index": 0, "occupied": false, "worker_id": null, "resource": "wheat", "resources": ["wheat"], "is_player": false},
			{"slot_index": 1, "occupied": true, "worker_id": "citizen:5", "worker_name": "Анна", "resource": "wheat", "resources": ["wheat"], "is_player": false},
			{"slot_index": 2, "occupied": true, "worker_id": "player:42", "worker_name": "Тест", "resource": "wheat", "resources": ["wheat"], "is_player": true, "harvest_bonus": {"wheat": 5}},
			{"slot_index": 3, "occupied": true, "worker_id": "player:7", "worker_name": "Чужой", "resource": "wheat", "resources": ["wheat"], "is_player": true},
		],
		"player_work": {"slot_index": 2},
		"upgrade": null,
		"warehouse_storage": {"wood": 500},
		"spendable_treasury_copper": 100000,
	}
	state[key] = {"completed": completed, "active_upgrade_id": active, "seconds_left": seconds_left}
	return state


func _find_button(node: Node, text: String) -> Button:
	for button in _find_buttons(node):
		if button.text == text:
			return button
	return null


func _find_buttons(node: Node) -> Array:
	var buttons: Array = []
	for child in node.get_children():
		if child is Button:
			buttons.append(child)
		buttons.append_array(_find_buttons(child))
	return buttons


func _button_texts(node: Node) -> Array:
	var texts: Array = []
	for button in _find_buttons(node):
		texts.append(button.text)
	return texts


func _label_texts(node: Node) -> Array:
	var texts: Array = []
	for child in node.get_children():
		if child is Label:
			texts.append(child.text)
		texts.append_array(_label_texts(child))
	return texts
