extends Node

const VIEW_SCRIPT := preload("res://scripts/deck_battle_view.gd")
const CARD_VIEW_SCRIPT := preload("res://scripts/deck_battle_card_view.gd")
const RULES := preload("res://scripts/deck_battle_layout_rules.gd")
const FIXTURE_DIR := "res://tests/fixtures/deck_battle/"

var _failures: Array[String] = []
var _checks := 0
var _pressed: Array = []
var _hovered: Array = []
var _view


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_view = VIEW_SCRIPT.new()
	_view.size = RULES.DESIGN_SIZE
	_view.card_pressed.connect(_on_card_pressed)
	_view.card_hovered.connect(_on_card_hovered)
	add_child(_view)
	await get_tree().process_frame
	_check_empty_and_partial()
	_check_planning()
	_check_draft()
	_check_draw()
	_check_result()
	_check_signals()
	_check_art_and_back()
	_check_piles()
	await _check_scaling()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_battle_view_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_empty_and_partial() -> void:
	_view.set_snapshot({})
	_check(_view.card_count() == 0, "пустой снимок: карт нет")
	_check(_view.panel_visible("board") and not _view.timer_state()["visible"], "пустой снимок: доска без таймера")
	_view.set_snapshot({"phase": "planning"})
	_check(_view.card_count() == 0 and _view.timer_state()["visible"], "частичный снимок: таймер без карт")
	_check(_view.timer_state()["text"] == "ВАШ ХОД", "частичный снимок: подпись хода")
	_view.set_snapshot({"phase": "result", "outcome": "win"})
	_check(_view.panel_visible("result") and not _view.panel_visible("board"), "результат без состава боя: панель результата, доска скрыта")
	_check(_view.result_texts()["title"] == "ПОБЕДА", "результат без состава боя: заголовок")
	_view.set_snapshot({"phase": "draft", "table": "junk", "hand": null})
	_check(_view.card_count() == 0 and _view.draft_texts()["visible"], "драфт с мусором в списках: карт нет, подписи видны")


func _check_planning() -> void:
	var data := _fixture("planning_hand.json")
	var hand: Array = data["hand"]
	_view.set_snapshot(data)
	_check(_view.card_count() == 7, "планирование: 5 карт руки и 2 выбранные")
	_check(_view.card_view("hand", 0) == null and _view.card_view("hand", 2) != null, "планирование: выбранные карты не дублируются в руке")
	_check(_view.card_view("selected", 0).name_text() == hand[0]["name"], "выбранная карта: название из снимка руки")
	_check(_view.card_view("hand", 6).is_highlighted() and not _view.card_view("hand", 6).is_pressable(), "недоступная карта руки затемнена и не нажимается")
	_check(_view.card_view("hand", 2).is_available() and _view.card_view("hand", 2).is_pressable(), "доступная карта руки нажимается")
	_check(_view.card_view("selected", 0).fill_color() == RULES.COLOR_CARD_SELECTED, "выбранная карта: цвет выбора")
	var hp: Dictionary = _view.bar_state("player", "hp")
	_check(hp["value"] == 106.0 and hp["max_value"] == 120.0 and hp["text"] == "HP: 106/120", "полоса HP игрока 106 из 120")
	_check(_view.bar_state("player", "mp")["max_value"] == 10.0, "полоса MP игрока 10 из 10")
	var rage: Dictionary = _view.bar_state("player", "resource")
	_check(rage["value"] == 68.0 and rage["text"] == "Ярость: 68/68", "полоса ярости воина 68 из 68")
	_check(not _view.bar_state("enemy", "resource")["visible"], "маг: третья полоса скрыта")
	_check(_view.bar_state("enemy", "hp")["value"] == 35.0, "маг: HP 35")
	var timer: Dictionary = _view.timer_state()
	_check(timer["visible"] and timer["value"] == 42.0 and timer["max_value"] == 60.0, "таймер хода: 42 из 60")
	_check(timer["text"] == "ВАШ ХОД" and _view.timer_fill_color() == RULES.COLOR_TIMER_GREEN, "таймер хода: подпись и зелёный цвет")
	var fighter: Dictionary = _view.fighter_texts("player")
	_check(fighter["name"] == "Тестовый Боец" and fighter["level"] == "Уровень 3", "игрок: имя и уровень")
	_check(fighter["stats"].size() == 7 and fighter["stats"][0] == "Сила: 6", "игрок: семь характеристик")
	_check(fighter["derived"] == ["Урон: 6", "Уворот: 6%", "Крит: 5% × 170%"], "игрок: производные значения как в Python (derived_values)")
	_check(not _view.draft_texts()["visible"] and _view.panel_visible("table") and _view.panel_visible("board"), "планирование: доска и стол видны, драфта нет")
	_check(_view.has_background_texture() and _view.has_table_texture(), "фон и стол загружены из ../assets")
	var leftover := data.duplicate(true)
	leftover["table"] = [hand[0]]
	_view.set_snapshot(leftover)
	_check(_view.card_count() == 7, "вне драфта стол не рисуется")
	_view.set_snapshot(data)


func _check_draft() -> void:
	var data := _fixture("draft_starting.json")
	_view.set_snapshot(data)
	_check(_view.card_count() == 22, "стартовый драфт: 20 карт на столе и 2 взятые")
	var draft: Dictionary = _view.draft_texts()
	_check(draft["visible"] and draft["title"] == "СТАРТОВЫЙ ДРАФТ", "стартовый драфт: заголовок")
	_check(draft["message"] == "Выберите две стартовые карты" and draft["timer"] == "ОСТАЛОСЬ 75 СЕК", "стартовый драфт: подсказка и таймер")
	_check(not _view.timer_state()["visible"], "в драфте полоски хода нет")
	var first_table = _view.card_view("table", 0)
	_check(first_table.position == RULES.draft_slot_rect("starting", 0).position, "первая карта стола стоит в слоте 0")
	_check(first_table.is_pressable() and not _view.card_view("hand", 0).is_pressable(), "карта стола нажимается, взятая карта руки нет")
	var before := _positions_by_key("table")
	var reduced := data.duplicate(true)
	var removed_key := str(data["table"][5]["key"])
	reduced["table"].remove_at(5)
	_view.set_snapshot(reduced)
	_check(_view.card_count() == 21, "после выбора карты: 19 на столе и 2 в руке")
	var after := _positions_by_key("table")
	var kept := true
	for key in after.keys():
		if before.has(key) and before[key] != after[key]:
			kept = false
	_check(kept and not after.has(removed_key) and after.size() == 19, "карты стола сохраняют слоты, убранная карта пропадает")
	reduced["battle_id"] = "another-battle"
	_view.set_snapshot(reduced)
	_check(_view.card_view("table", 0).position == RULES.draft_slot_rect("starting", 0).position, "новый бой: слоты начинаются заново")
	_view.set_snapshot(_fixture("draft_redraft.json"))
	_check(_view.card_count() == 13 and _view.draft_texts()["title"] == "ПОВТОРНЫЙ ДРАФТ", "повторный драфт: 6 карт стола и 7 в руке")


func _check_draw() -> void:
	_view.set_snapshot(_fixture("draw_choice.json"))
	_check(_view.card_count() == 10, "выбор карты: 7 карт руки и 3 варианта")
	var choice = _view.card_view("draw_choices", 0)
	_check(choice != null and choice.is_pressable() and choice.size.y == 176.0, "варианты добора нажимаются и высотой 176")
	var timer: Dictionary = _view.timer_state()
	_check(timer["visible"] and timer["value"] == 9.0 and timer["max_value"] == 15.0, "таймер выбора: 9 из 15")
	_check(timer["text"] == "ВЫБОР КАРТЫ: 9 СЕК" and _view.timer_fill_color() == RULES.COLOR_TIMER_RED, "таймер выбора: подпись и красный цвет на 9 с")
	var hand_visible := true
	for row in range(7):
		if _view.card_view("hand", row) == null:
			hand_visible = false
	_check(hand_visible and _view.card_view("hand", 0).is_highlighted() and not _view.card_view("hand", 0).is_pressable(), "рука в выборе карты видна, но не нажимается")


func _check_result() -> void:
	var data := _fixture("outcome_win.json")
	_view.set_snapshot(data)
	var result: Dictionary = _view.result_texts()
	_check(result["visible"] and result["title"] == "ПОБЕДА", "результат: заголовок победы")
	_check(result["winner"] == "Победитель: Тестовый Некромант", "результат: победитель — боец игрока")
	_check(_view.card_count() == 0 and not _view.panel_visible("board") and not _view.panel_visible("timer"), "результат: карты, доска и таймер скрыты")
	data["outcome"] = "loss"
	_view.set_snapshot(data)
	_check(_view.result_texts()["title"] == "ПОРАЖЕНИЕ" and _view.result_texts()["winner"] == "Победитель: Тестовый Боец", "поражение: заголовок и соперник-победитель")
	data["outcome"] = "draw"
	_view.set_snapshot(data)
	_check(_view.result_texts()["title"] == "НИЧЬЯ" and _view.result_texts()["winner"] == "Победитель: Ничья", "ничья: заголовок и Ничья")
	_view.set_snapshot(_fixture("planning_hand.json"))
	_check(not _view.result_texts()["visible"], "после результата панель скрывается")


func _check_signals() -> void:
	var data := _fixture("planning_hand.json")
	_view.set_snapshot(data)
	_pressed.clear()
	_hovered.clear()
	_view.card_view("hand", 2).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_view.card_view("hand", 6).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_view.card_view("selected", 1).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_view.card_view("hand", 2).gui_input.emit(_click(MOUSE_BUTTON_RIGHT))
	_check(_pressed == [["hand", 2], ["selected", 1]], "нажатие уходит card_pressed(zone, index); недоступная карта и правая кнопка молчат")
	_view.card_view("hand", 3).mouse_entered.emit()
	_check(_hovered.size() == 1 and _hovered[0]["key"] == data["hand"][3]["key"], "наведение: card_hovered с картой")
	_view.card_view("hand", 3).mouse_exited.emit()
	_check(_hovered.size() == 2 and _hovered[1].is_empty(), "уход курсора: card_hovered({})")
	_view.set_snapshot(_fixture("draw_choice.json"))
	_pressed.clear()
	_view.card_view("draw_choices", 1).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_check(_pressed == [["draw_choices", 1]], "выбор добора: card_pressed(draw_choices, 1)")
	_view.set_snapshot(_fixture("draft_starting.json"))
	_pressed.clear()
	_view.card_view("table", 3).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_view.card_view("hand", 0).gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_check(_pressed == [["table", 3]], "драфт: карта стола нажимается, взятая карта руки нет")


func _check_art_and_back() -> void:
	var data := _fixture("planning_hand.json")
	data["hand"][2]["image_path"] = "assets/cards/faces/deaf_defense.png"
	data["hand"][3]["image_path"] = "assets/cards/faces/no_such_face.png"
	_view.set_snapshot(data)
	_check(_view.card_view("hand", 2).has_art(), "картинка карты: файл существует, лицо с артом")
	_check(not _view.card_view("hand", 3).has_art(), "картинки карты нет: текстовое лицо")
	_check(not _view.card_view("hand", 4).has_art(), "карта без image_path: текстовое лицо")
	_check(_view.card_view("hand", 2).name_text() == data["hand"][2]["name"], "карта с арт-лицом показывает название")
	_view.set_snapshot(_fixture("planning_hand.json"))
	var back = CARD_VIEW_SCRIPT.new()
	add_child(back)
	back.configure(RULES.hidden_card_entry(Rect2(0, 0, 150, 200)))
	_check(back.is_showing_back() and not back.has_art() and not back.is_pressable(), "рубашка: без лица и без нажатий")
	back.queue_free()
	_check(CARD_VIEW_SCRIPT.load_texture(RULES.asset_path(CARD_VIEW_SCRIPT.project_dir(), RULES.CARD_BACK_ASSET)) != null, "рубашка карты читается из ../assets")


func _check_piles() -> void:
	_view.set_snapshot(_fixture("planning_hand.json"))
	_check(_view.pile_title("deck") == "ВАША КОЛОДА" and _view.pile_title("discard") == "ВАШ СБРОС", "подписи колоды и сброса")
	_check(not _view.pile_count_visible("deck"), "без счётчиков бейдж скрыт")
	_view.set_pile_counts(20, 2)
	_check(_view.pile_count_visible("deck") and _view.pile_count_text("deck") == "20", "счётчик колоды")
	_check(_view.pile_count_text("discard") == "2", "счётчик сброса")
	_view.set_pile_counts(-1, -1)
	_check(not _view.pile_count_visible("discard"), "отрицательный счётчик скрывает бейдж")
	_view.set_hit_overlay_visible(true)
	_check(not _view.hit_overlay_visible() and not _view.panel_visible("hit"), "заглушка удара: файла нет, оверлей не показывается")


func _check_scaling() -> void:
	_view.set_snapshot(_fixture("planning_hand.json"))
	_view.size = Vector2(960, 540)
	await get_tree().process_frame
	_check(is_equal_approx(_view.canvas_factor(), 0.5), "вид 960x540: макет уменьшен вдвое")
	var card = _view.card_view("selected", 0)
	_check(card.get_global_rect().size == Vector2(75, 100), "карта на экране занимает половину размера")
	_view.size = RULES.DESIGN_SIZE
	await get_tree().process_frame
	_check(is_equal_approx(_view.canvas_factor(), 1.0), "вид 1920x1080: масштаб 1")


func _positions_by_key(zone: String) -> Dictionary:
	var result := {}
	for view in _view.card_views():
		if view.zone == zone:
			result[str(view.card["key"])] = view.position
	return result


func _fixture(file_name: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIR + file_name))
	return parsed if parsed is Dictionary else {}


func _click(button: int) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = true
	return event


func _on_card_pressed(zone: String, index: int) -> void:
	_pressed.append([zone, index])


func _on_card_hovered(card: Dictionary) -> void:
	_hovered.append(card)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
