extends Node

# Стенка на стенку: правила заявок и окно сбора (состояние кнопок, сигналы, таймеры, пары соперников).
const WINDOW_SCRIPT := preload("res://scripts/deck_group_battle_window.gd")
const RULES := preload("res://scripts/deck_group_battle_rules.gd")

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	await _check_window()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_group_battle_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _member(character_id: int) -> Dictionary:
	return {"id": character_id, "name": "Боец %d" % character_id}


func _offer(id: String, sender_id: int, status: String, participants: Array, max_size := 6) -> Dictionary:
	return {
		"id": id,
		"sender_id": sender_id,
		"sender": "Игрок %d" % sender_id,
		"status": status,
		"max_participants": max_size,
		"ttl": 120,
		"created_at": 1000.0,
		"participants": participants,
	}


func _check_rules() -> void:
	var waiting := _offer("a", 1, "waiting", [_member(1), _member(2)])
	var full := _offer("b", 3, "waiting", [_member(3), _member(4), _member(5), _member(6), _member(7), _member(8)])
	var ready := _offer("c", 9, "ready", [_member(9), _member(10), _member(11), _member(12), _member(13), _member(14)])
	ready["teams"] = [[_member(9), _member(10), _member(11)], [_member(12), _member(13), _member(14)]]
	var offers: Array = [waiting, full]

	_check(RULES.own_offer(offers, 2)["id"] == "a", "свою заявку находим по участнику")
	_check(RULES.own_offer(offers, 99).is_empty(), "чужой персонаж своей заявки не имеет")
	_check(RULES.can_join(waiting, 5), "в заявку с местами можно вступить")
	_check(not RULES.can_join(waiting, 1), "нельзя вступить второй раз")
	_check(not RULES.can_join(full, 20), "в полную заявку вступить нельзя")
	_check(not RULES.can_join(ready, 20), "в готовую заявку вступить нельзя")
	_check(RULES.seconds_left(waiting, 1030.0) == 90, "осталось 90 секунд через 30 секунд из 120")
	_check(RULES.seconds_left(waiting, 1500.0) == 0, "таймер не уходит в минус")
	_check(RULES.format_clock(90) == "1:30", "формат времени 1:30")
	_check(RULES.format_clock(5) == "0:05", "формат времени с ведущим нулём")
	_check(RULES.format_clock(3600) == "60:00", "формат времени больше часа")
	_check(RULES.offer_title(waiting) == "Игрок 1 (2/6)", "заголовок заявки с числом участников")
	_check(RULES.max_participants_of({}) == 10, "без максимума — десять участников")
	_check(RULES.status_label(waiting) == "набор участников", "подпись набора")
	_check(RULES.status_label(ready) == "команды сформированы", "подпись готовой заявки")
	_check(RULES.status_label({"status": "in_progress"}) == "бой идёт", "подпись идущего боя")
	_check(RULES.status_label({"status": "cancelled"}) == "заявка закрыта", "подпись закрытой заявки")
	_check(RULES.team_of(ready, 11) == 0 and RULES.team_of(ready, 14) == 1, "команда персонажа")
	_check(RULES.team_of(ready, 1) == -1, "чужой персонаж без команды")
	_check(RULES.opponent_of(ready, 10)["id"] == 13, "соперник: тот же индекс в другой команде")
	_check(RULES.opponent_of(ready, 11)["id"] == 14, "соперник для последнего места")
	_check(RULES.opponent_of(ready, 14)["id"] == 11, "соперник для второй команды")
	_check(RULES.opponent_of(waiting, 1).is_empty(), "до сборки команд соперника нет")
	_check(RULES.start_available(ready, 10), "в готовом сборе свой бой можно начать")
	_check(not RULES.start_available(waiting, 1), "в наборе бой ещё не начинается")
	_check(not RULES.start_available(ready, 1), "чужой персонаж боя не начинает")
	_check(RULES.validate_choice(6, 120).is_empty() and RULES.validate_choice(8, 600).is_empty(), "допустимые размер и время")
	_check(not RULES.validate_choice(7, 120).is_empty(), "размер 7 не допускается")
	_check(not RULES.validate_choice(6, 60).is_empty(), "время 60 секунд не допускается")
	_check(RULES.is_sender(waiting, 1) and not RULES.is_sender(waiting, 2), "отправитель заявки")


func _check_window() -> void:
	var host := Node.new()
	add_child(host)
	var window = WINDOW_SCRIPT.new()
	host.add_child(window)
	window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await get_tree().process_frame

	var creates: Array = []
	window.create_requested.connect(func(size: int, ttl: int) -> void: creates.append([size, ttl]))
	var joins: Array = []
	window.join_requested.connect(func(offer_id: String) -> void: joins.append(offer_id))
	var leaves: Array = []
	window.leave_requested.connect(func(offer_id: String) -> void: leaves.append(offer_id))
	var starts: Array = []
	window.start_requested.connect(func(offer_id: String) -> void: starts.append(offer_id))

	_check(not window.is_open(), "окно сбора закрыто по умолчанию")
	window.open(7)
	_check(window.is_open(), "окно открывается")
	window.set_state([], 7)
	_check(window._offers_box.get_child_count() == 1 and window._offers_box.get_child(0).text == "Активных заявок пока нет", "пустой список заявок")
	_check(window._create_box.visible and not window._own_box.visible, "без своей заявки видны параметры сбора")
	_check(window._create_button.disabled, "без размера и времени создать нельзя")
	window._on_size_toggled(true, 8)
	_check(window._create_button.disabled, "одного размера мало")
	window._on_ttl_toggled(true, 600)
	_check(not window._create_button.disabled, "размер и время выбраны — создание доступно")
	window._on_create_pressed()
	_check(creates == [[8, 600]], "создание передаёт размер и время")

	var others := _offer("x1", 3, "waiting", [_member(3), _member(4)])
	window.set_state([others], 7)
	_check(window._join_buttons["x1"].text == "ВСТУПИТЬ" and not window._join_buttons["x1"].disabled, "чужой сбор с местами открыт для вступления")
	window._on_join_pressed("x1")
	_check(joins == ["x1"], "вступление передаёт id заявки")
	window.set_busy(true)
	_check(window._join_buttons["x1"].disabled and window._create_button.disabled, "во время запроса кнопки заблокированы")
	window._on_join_pressed("x1")
	_check(joins.size() == 1, "во время запроса повторного вступления нет")
	window.set_busy(false)

	var own := _offer("own1", 7, "waiting", [_member(7)])
	window.set_state([own], 7)
	_check(window._own_box.visible and not window._create_box.visible, "со своей заявкой видна только она")
	_check(window._leave_button.visible and not window._start_button.visible, "в наборе есть отмена, но не старт")
	_check(window._join_buttons["own1"].text == "ВЫ В СБОРЕ" and window._join_buttons["own1"].disabled, "свой сбор нельзя занять повторно")
	window._on_leave_pressed()
	_check(leaves == ["own1"], "отмена передаёт id своей заявки")
	window.refresh_clock(1030.0)
	_check(window._own_status.text.contains("осталось 1:30"), "таймер своей заявки обновляется")

	var ready := _offer("c", 9, "ready", [_member(9), _member(10), _member(11), _member(12), _member(13), _member(14)])
	ready["teams"] = [[_member(9), _member(10), _member(11)], [_member(12), _member(13), _member(14)]]
	window.set_state([ready], 10)
	_check(window._start_button.visible and not window._leave_button.visible, "в готовом сборе видна кнопка боя, отмены нет")
	_check(window._own_team.text == "Команда 1 · соперник: Боец 13", "в окне показан соперник")
	window._on_start_pressed()
	_check(starts == ["c"], "старт передаёт id готового сбора")
	window.set_state([ready], 10)
	window.refresh_clock(2000.0)
	_check(not window._own_status.text.contains("осталось"), "у готового сбора таймера нет")

	window.show_message("Сервер отказал", true)
	_check(window._message.text == "Сервер отказал", "сообщение окна показывается")
	_check(window._message.get_theme_color("font_color") == Color8(255, 100, 100), "ошибка окрашена красным")

	_check(window.is_open(), "Esc не закрывает окно группового боя: клавиша уходит в меню выхода")
	window.open(7)
	window.close()
	_check(not window.is_open(), "кнопка закрытия работает")
	host.queue_free()
	await get_tree().process_frame
