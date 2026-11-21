extends Node

const RULES := preload("res://scripts/deck_talent_rules.gd")
const DATA := preload("res://scripts/deck_talent_data.gd")
const WINDOW_SCRIPT := preload("res://scripts/deck_talent_window.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_talent_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_static_data(samples)
		_check_rules()
		await _check_window()
		await _check_world()
	else:
		_check(false, "файл эталона талантов читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_talent_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_static_data(samples: Dictionary) -> void:
	# JSON отдаёт числа как float, а const-данные хранят int; сравниваем после одного и того же преобразования.
	var generated_trees: Variant = JSON.parse_string(JSON.stringify(DATA.TREES))
	_check(generated_trees == samples["trees"], "деревья талантов совпадают с эталоном Python")
	_check(DATA.LEGACY_PROFESSION_TYPES == samples["legacy_profession_types"], "устаревшие типы магов совпадают с эталоном")
	_check(DATA.TREES.size() == 5, "пять деревьев классов")
	var levels_in_order := true
	var passive_on_three := true
	var choices_have_two := true
	for profession in DATA.TREES:
		var tree: Array = DATA.TREES[profession]
		_check(tree.size() == 10, "%s: десять уровней" % profession)
		for index in range(tree.size()):
			var entry: Dictionary = tree[index]
			levels_in_order = levels_in_order and int(entry["level"]) == index + 1
			if entry["passive"]:
				passive_on_three = passive_on_three and int(entry["level"]) == 3
			else:
				choices_have_two = choices_have_two and entry["options"].size() == 2
	_check(levels_in_order, "уровни идут от 1 до 10")
	_check(passive_on_three, "пассивное улучшение только на 3-м уровне")
	_check(choices_have_two, "на каждом выборе ровно два варианта")


func _check_rules() -> void:
	_check(RULES.normalize_type("battle_mage") == "mage", "устаревший боевой маг сводится к mage")
	_check(RULES.normalize_type("harmonist") == "mage", "гармонист сводится к mage")
	_check(RULES.normalize_type("") == "warrior" and RULES.normalize_type(null) == "warrior", "пустой тип — воин, как в Python")
	_check(RULES.tree_for("unknown_class") == DATA.TREES["warrior"], "неизвестный класс получает дерево воина")
	_check(RULES.tree_for("mage") == DATA.TREES["mage"], "маг получает своё дерево")
	_check(RULES.type_label("mage") == "Mage", "подпись типа как capitalize в Python")
	_check(RULES.type_label("battle_mage") == "Battle_mage", "подпись устаревшего типа как в Python")
	_check(RULES.is_unlocked(5, 5) and not RULES.is_unlocked(4, 5), "ряд открыт при уровне персонажа не ниже")
	var character := {"level": 5, "talents": {"1": "hp"}}
	_check(RULES.choose_error(character, DATA.TREES["mage"][0]) == "На этом уровне улучшение уже выбрано", "повторный выбор отклоняется")
	_check(RULES.choose_error(character, DATA.TREES["mage"][5]) == "Это улучшение доступно с 6-го уровня", "закрытый уровень отклоняется")
	_check(RULES.choose_error(character, DATA.TREES["mage"][1]) == "", "свободный открытый уровень разрешён")
	_check(RULES.choose_error({"level": 5}, DATA.TREES["mage"][1]) == "", "персонаж без талантов может выбрать")


func _check_window() -> void:
	var window = WINDOW_SCRIPT.new()
	window.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(window)
	var chosen: Array = []
	window.choose_requested.connect(func(level: int, choice_id: String, option_name: String) -> void:
		chosen.append([level, choice_id, option_name]))
	var mage: Array = DATA.TREES["mage"]
	var burn: Dictionary = mage[1]["options"][1]

	window.open({"id": 7, "type": "mage", "level": 5, "talents": {"1": "hp"}})
	_check(window.is_open(), "окно открывается")
	_check(window._subtitle.text == "Mage — уровень 5", "подпись: класс и уровень")
	_check(window._rows.get_child_count() == 10, "окно показывает десять уровней")
	_check(_button_label(_row_buttons(window, 1)[0]).text == mage[0]["options"][0]["name"], "выбранный вариант показан названием")
	_check(_button_label(_row_buttons(window, 1)[1]).text == mage[0]["options"][1]["description"], "невыбранный вариант показан описанием")
	_check(_row_buttons(window, 3).is_empty() and _has_label(window._rows, "ПАССИВНОЕ УЛУЧШЕНИЕ"), "третий уровень пассивный и без кнопок")
	_row_buttons(window, 2)[1].pressed.emit()
	_check(chosen.size() == 1 and chosen[0] == [2, burn["id"], burn["name"]], "открытый свободный вариант отправляет выбор миру")
	_row_buttons(window, 6)[0].pressed.emit()
	_check(chosen.size() == 1 and window._message.text == "Это улучшение доступно с 6-го уровня", "закрытый уровень не отправляется")
	_row_buttons(window, 1)[1].pressed.emit()
	_check(chosen.size() == 1 and window._message.text == "На этом уровне улучшение уже выбрано", "занятый уровень не отправляется")

	window.set_character({"id": 7, "type": "mage", "level": 5, "talents": {"1": "hp", "2": "burn_20"}})
	_check(_button_label(_row_buttons(window, 2)[1]).text == burn["name"], "после ответа сервера выбранный вариант показан названием")
	window.show_message("Выбрано: тест")
	_check(window._message.text == "Выбрано: тест", "сообщение окна обновляется")
	window.set_character({"id": 7, "type": "battle_mage", "level": 5, "talents": {}})
	_check(window._subtitle.text == "Battle_mage — уровень 5", "устаревший тип показан как в Python")
	_check(_button_label(_row_buttons(window, 1)[0]).text == mage[0]["options"][0]["description"], "устаревший маг получает дерево мага")
	window.open({"level": 5})
	_check(window._message.text == "Персонаж не загружен", "без id персонаж не загружен")
	window.open({"id": 7, "type": "mage", "level": 5, "talents": {"1": "hp"}})

	await get_tree().process_frame
	await get_tree().process_frame
	var screen := get_viewport().get_visible_rect().size
	_check(window._window.size.x <= screen.x and window._window.size.y <= screen.y, "окно помещается в экран")
	var bar: VScrollBar = window._scroll.get_v_scroll_bar()
	_check(bar.max_value > bar.page, "десять уровней прокручиваются")
	var down := InputEventKey.new()
	down.keycode = KEY_DOWN
	down.pressed = true
	get_viewport().push_input(down)
	_check(window._scroll.scroll_vertical > 0, "стрелка вниз прокручивает древо")
	var up := InputEventKey.new()
	up.keycode = KEY_UP
	up.pressed = true
	get_viewport().push_input(up)
	_check(window._scroll.scroll_vertical == 0, "стрелка вверх возвращает наверх")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	_check(window.is_open(), "Esc не закрывает древо: клавиша уходит в меню выхода")
	window.open({"id": 7, "type": "mage", "level": 5, "talents": {}})
	_find_button_text(window, "×").pressed.emit()
	_check(not window.is_open(), "кнопка × закрывает древо")
	window.open({"id": 7, "type": "mage", "level": 5, "talents": {}})
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	window._on_backdrop_input(click)
	_check(not window.is_open(), "щелчок вне окна закрывает древо")
	window.queue_free()
	await get_tree().process_frame


func _check_world() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {
		"id": 42, "name": "Тест", "coins": 100, "type": "mage", "level": 5,
		"position_x": 100.0, "talents": {"1": "hp"},
	}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var talents = deck._talent_window
	var burn: Dictionary = DATA.TREES["mage"][1]["options"][1]

	deck._terrain = {}
	deck._view = "home"
	deck._map_position = Vector2i(21, 37)
	deck._move_world(1, 0)
	_check(talents.is_open(), "вход на тайл древа открывает окно талантов")
	_check(deck._map_position == Vector2i(22, 37), "герой стоит на тайле древа")
	_check(deck._pending_action == "talent_character", "состояние персонажа запрошено при входе")
	await _wait_idle(deck)
	_check(talents._message.text.begins_with("Не удалось обновить данные персонажа"), "ошибка сети показана в древе")

	var key := InputEventKey.new()
	key.keycode = KEY_D
	key.pressed = true
	deck._unhandled_input(key)
	_check(deck._map_position == Vector2i(22, 37), "клавиши не двигают фигурку и при открытом древе")
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	get_viewport().push_input(escape)
	_check(talents.is_open() and deck._exit_menu.is_open(), "Esc открывает меню выхода и не закрывает древо, как в Python")
	deck._exit_menu.close()
	talents.close()

	deck._move_world(1, 0)
	_check(not talents.is_open(), "переход внутри зоны древа не открывает окно повторно")
	deck._move_world(0, 2)
	_check(not talents.is_open(), "выход из зоны древа не открывает окно")
	deck._move_world(-1, 0)
	deck._move_world(0, -2)
	_check(talents.is_open(), "повторный вход на тайл открывает древо снова")
	talents.close()
	deck._move_world(-1, 0)
	_check(_find_button_text(deck, "Д") != null, "соседний тайл древа отмечен буквой Д")
	deck._move_world(1, 0)
	_check(talents.is_open(), "вход с запада снова открывает древо")
	await _wait_idle(deck)

	_row_buttons(talents, 2)[1].pressed.emit()
	_check(deck._pending_action == "talent_choose" and deck._pending_talent_name == burn["name"], "выбор улучшения отправляется в мир")
	await _wait_idle(deck)
	_check(talents._message.text.begins_with("Не удалось выбрать улучшение"), "ошибка выбора показана в древе")
	_check(deck._pending_talent_name.is_empty(), "после ошибки имя выбора сброшено")

	deck._pending_action = "talent_choose"
	deck._pending_talent_name = burn["name"]
	var position_before := float(GameSession.character["position_x"])
	deck._on_api_completed(true, {"character": {"id": 42, "level": 6, "talents": {"1": "hp", "2": "burn_20"}, "position_x": 1.0}})
	_check(GameSession.character["talents"].get("2") == "burn_20" and int(GameSession.character["level"]) == 6, "ответ сервера обновляет уровень и таланты")
	_check(float(GameSession.character["position_x"]) == position_before, "позиция из ответа сервера не перезаписывает мир")
	_check(talents._message.text == "Выбрано: " + burn["name"], "после выбора показано сообщение")
	_check(_button_label(_row_buttons(talents, 2)[1]).text == burn["name"], "выбранный вариант отмечен в древе")

	deck._pending_action = "talent_character"
	deck._on_api_completed(true, {"nope": 1})
	_check(talents._message.text == "Не удалось обновить данные персонажа: неверный ответ сервера", "неверный ответ сервера показан в древе")

	talents.close()
	deck._pending_action = "checkpoint"
	deck._request_when_idle("talent_character", HTTPClient.METHOD_GET, "/api/characters/42", {}, "talents")
	deck._pending_action = ""
	deck._flush_queued_requests()
	_check(deck._pending_action.is_empty() and deck._queued_requests.is_empty(), "закрытое древо не отправляет отложенный запрос")

	deck._terrain = {"published": true}
	deck._map_position = Vector2i(21, 37)
	deck._move_world(1, 0)
	_check(not talents.is_open(), "на опубликованной карте древа нет")
	deck._terrain = {}


func _row_buttons(window, talent_level: int) -> Array:
	var panel: Node = window._rows.get_child(talent_level - 1)
	var row: Node = panel.get_child(0)
	var buttons: Array = []
	for child in row.get_children():
		if child is Button:
			buttons.append(child)
	return buttons


func _button_label(button: Button) -> Label:
	return button.get_child(0) as Label


func _has_label(node: Node, text: String) -> bool:
	for child in node.get_children():
		if child is Label and child.text == text:
			return true
		if _has_label(child, text):
			return true
	return false


func _wait_idle(deck) -> void:
	var started := Time.get_ticks_msec()
	while not deck._pending_action.is_empty() and Time.get_ticks_msec() - started < 5000:
		await get_tree().create_timer(0.01).timeout
	await get_tree().process_frame


func _find_button_text(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button_text(child, text)
		if found != null:
			return found
	return null


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)
