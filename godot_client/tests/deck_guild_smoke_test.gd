extends Node

const QUEST_LOG := preload("res://scripts/deck_quest_log.gd")
const GUILD_WINDOW_SCRIPT := preload("res://scripts/deck_guild_window.gd")
const CURRENCY := preload("res://scripts/deck_currency.gd")
const CARD_RULES := preload("res://scripts/card_tooltip_rules.gd")
const DECK_SCRIPT := preload("res://scripts/deck_world.gd")
const SAMPLES_PATH := "res://tests/deck_guild_samples.json"
const UNREACHABLE_URL := "http://127.0.0.1:9"

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var samples: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAMPLES_PATH))
	if samples is Dictionary:
		_check_quests(samples["quests"])
		_check_coins()
		_check_quest_log()
		await _check_window()
		await _check_world()
	else:
		_check(false, "файл эталона заданий читается")
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_guild_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_quests(expected: Array) -> void:
	_check(QUEST_LOG.QUESTS.size() == expected.size(), "список заданий совпадает с Python по размеру")
	for index in range(mini(expected.size(), QUEST_LOG.QUESTS.size())):
		var mine: Dictionary = QUEST_LOG.QUESTS[index]
		var theirs: Dictionary = expected[index]
		var quest_id := str(theirs["id"])
		_check(str(mine["id"]) == quest_id, "порядок заданий: %s" % quest_id)
		_check(str(mine["title"]) == str(theirs["title"]), "название задания %s" % quest_id)
		_check(str(mine["description"]) == str(theirs["description"]), "описание задания %s" % quest_id)
		_check(str(mine["target"]) == str(theirs["target"]), "цель задания %s" % quest_id)
		_check(int(mine["count"]) == int(theirs["count"]), "количество задания %s" % quest_id)
		_check(int(mine["reward_coins"]) == int(theirs["reward_coins"]), "награда задания %s" % quest_id)


func _check_coins() -> void:
	_check(CURRENCY.format_coins(1) == "1 монета", "одна монета")
	_check(CURRENCY.format_coins(2) == "2 монеты", "две монеты")
	_check(CURRENCY.format_coins(5) == "5 монет", "пять монет")
	_check(CURRENCY.format_coins(21) == "21 монета", "двадцать одна монета")
	_check(CURRENCY.format_coins(22) == "22 монеты", "двадцать две монеты")
	_check(CURRENCY.format_coins(111) == "111 монет", "111 монет (исключение 11..14)")
	_check(CURRENCY.format_coins(780) == "780 монет", "780 монет")
	_check(CARD_RULES.format_coins(22) == "22 монеты", "подсказка карты использует то же склонение")


func _check_quest_log() -> void:
	var log = QUEST_LOG.new()
	_check(log.status("kill_kobold") == "available", "новое задание доступно")
	_check(log.accept("kill_kobold"), "задание принимается")
	_check(not log.accept("kill_kobold"), "повторно принять нельзя")
	_check(not log.accept("unknown"), "неизвестное задание не принимается")
	_check(log.status("kill_kobold") == "active", "принятое задание активно")
	_check(log.record_progress("ancient_ent").is_empty(), "чужая цель не выполняет задание")
	_check(log.progress_of("kill_kobold") == 0, "чужая цель не меняет прогресс")
	_check(log.accept("kill_3_kobolds"), "второе задание принимается")
	_check(log.record_progress("kobold") == ["kill_kobold"], "выполненное задание возвращается из обновления")
	_check(log.status("kill_kobold") == "completed", "задание выполнено")
	_check(log.status("kill_3_kobolds") == "active" and log.progress_of("kill_3_kobolds") == 1, "общая цель считается по всем принятым заданиям")
	_check(log.record_progress("kobold", 5) == ["kill_3_kobolds"], "прогресс выполняет задание сверх нужного")
	_check(log.progress_of("kill_3_kobolds") == 3, "прогресс ограничивается числом целей")
	_check(log.claim("kill_kobold") == 10, "сдача возвращает награду задания")
	_check(log.status("kill_kobold") == "available", "после сдачи задание снова доступно")
	_check(log.claim("kill_kobold") == 0, "сдача невыполненного задания ничего не даёт")
	_check(log.claim("kill_3_kobolds") == 40, "вторая сдача возвращает свою награду")


func _check_window() -> void:
	var window = GUILD_WINDOW_SCRIPT.new()
	var log = QUEST_LOG.new()
	var claims: Array = []
	window.claim_requested.connect(func(quest_id: String) -> void: claims.append(quest_id))
	add_child(window)
	await get_tree().process_frame
	_check(not window.is_open(), "окно гильдии скрыто по умолчанию")
	window.open(log)
	_check(window.is_open(), "окно гильдии открывается")
	_check(window._welcome.visible and not window._quests_view.visible, "при открытии показано приветствие")
	_check(not window._footer.visible, "в приветствии нижняя панель скрыта, как в Python")
	_find_button_text(window, "ЗАДАНИЯ").pressed.emit()
	_check(window._quests_view.visible and not window._welcome.visible, "кнопка ЗАДАНИЯ показывает список")
	_check(window._footer.visible, "в списке видна нижняя панель с кнопкой")
	_check(window._rows.size() == 6, "в списке шесть заданий")
	_check(window._rows["kill_kobold"].text == "Убить кобольда\nдоступно", "строка доступного задания")
	_check(window._action_button.text == "ПРИНЯТЬ ЗАДАНИЕ" and not window._action_button.disabled, "доступное задание: кнопка принять")
	window._action_button.pressed.emit()
	_check(log.status("kill_kobold") == "active", "кнопка принять берёт задание")
	_check(window._message.text == "Задание «Убить кобольда» принято", "сообщение о принятии")
	_check(window._action_button.text == "ЗАДАНИЕ ВЗЯТО" and window._action_button.disabled, "взятое задание нельзя принять снова")
	_check(window._detail_progress.visible and window._detail_progress.text == "Прогресс: 0/1", "прогресс взятого задания")
	_check(window._rows["kill_kobold"].text == "Убить кобольда\nвзято", "строка взятого задания")
	log.record_progress("kobold")
	window.refresh()
	_check(window._rows["kill_kobold"].text == "Убить кобольда\nвыполнено!", "строка выполненного задания")
	_check(window._action_button.text == "СДАТЬ ЗАДАНИЕ" and not window._action_button.disabled, "выполненное задание сдаётся")
	window._action_button.pressed.emit()
	_check(claims == ["kill_kobold"], "сдача просит мир о награде задания")
	_check(log.status("kill_kobold") == "completed", "окно само не снимает выполненное задание")
	window._rows["kill_3_kobolds"].button_pressed = true
	_check(window._selected_id == "kill_3_kobolds", "выбор строки меняет задание справа")
	_check(window._detail_title.text == "Убить 3 кобольдов", "справа название выбранного задания")
	_check(window._detail_reward.text == "Награда: 40 монет", "справа награда выбранного задания")
	_check(not window._detail_progress.visible, "у доступного задания прогресс скрыт")
	_check(window._message.text == "", "выбор строки сбрасывает сообщение")
	var window_size: Vector2 = window._window.size
	var screen := get_viewport().get_visible_rect().size
	_check(window_size.x <= screen.x and window_size.y <= screen.y, "окно гильдии помещается в экран")
	window.open(log)
	_find_button_text(window, "×").pressed.emit()
	_check(not window.is_open(), "кнопка × закрывает окно")
	window.open(log)
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	window._on_backdrop_input(click)
	_check(not window.is_open(), "щелчок вне окна закрывает его")
	window.show_message("Ошибка", true)
	_check(window._message.get_theme_color("font_color") == Color8(255, 150, 140), "ошибка выводится красным")
	window.queue_free()
	await get_tree().process_frame


func _check_world() -> void:
	GameSession.clear()
	GameSession.hub_url = UNREACHABLE_URL
	GameSession.token = "test-token"
	GameSession.world_token = "test-world-token"
	GameSession.world = {"server_url": UNREACHABLE_URL, "name": "Тест"}
	GameSession.character = {"id": 42, "name": "Тест", "coins": 100, "equipment": {"weapon": {"name": "Меч"}}}
	ApiClient._http.timeout = 0.5
	var deck = DECK_SCRIPT.new()
	deck.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(deck)
	deck._social_timer.stop()
	deck._battle_timer.stop()
	await _wait_idle(deck)
	var guild = deck._guild_window

	deck._terrain = {}
	deck._view = "home"
	deck._map_position = Vector2i(18, 27)
	deck._move_world(1, 0)
	_check(guild.is_open(), "вход на тайл гильдии открывает окно")
	_check(deck._map_position == Vector2i(19, 27), "герой стоит на тайле гильдии")
	var key := InputEventKey.new()
	key.keycode = KEY_D
	key.pressed = true
	deck._unhandled_input(key)
	_check(deck._map_position == Vector2i(19, 27), "клавиши не двигают фигурку и при открытом окне")
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	deck._unhandled_input(escape)
	_check(guild.is_open() and deck._exit_menu.is_open(), "Esc открывает меню выхода и не закрывает гильдию, как в Python")
	deck._exit_menu.close()
	guild.close()
	deck._move_world(1, 0)
	_check(not guild.is_open(), "переход внутри гильдии не открывает окно повторно")
	deck._move_world(0, -2)
	_check(not guild.is_open(), "выход из гильдии не открывает окно")
	deck._move_world(-1, 2)
	_check(guild.is_open(), "новый вход с улицы снова открывает окно")
	guild.close()

	deck._terrain = {"published": true}
	deck._map_position = Vector2i(18, 27)
	deck._move_world(1, 0)
	_check(not guild.is_open(), "на опубликованной карте зоны гильдии нет")
	deck._terrain = {}

	deck._map_position = Vector2i(21, 27)
	deck._render_location()
	_check(_find_button_text(deck._list, "G") != null, "на карте отмечена гильдия буквой G")

	guild.open(deck._quest_log)
	deck._quest_log.accept("kill_kobold")
	deck._quest_log.record_progress("kobold")
	guild.refresh()
	deck._claim_guild_quest("kill_kobold")
	_check(deck._pending_action == "guild_claim", "сдача отправляет запрос на сервер")
	_check(guild._message.text == "Сдаём задание…", "во время запроса окно показывает ожидание")
	await _wait_idle(deck)
	_check(guild._message.text.begins_with("Не удалось сдать задание"), "ошибка сети показана в окне гильдии")
	_check(deck._quest_log.status("kill_kobold") == "completed", "при ошибке задание остаётся выполненным")
	_check(deck._pending_guild_quest.is_empty(), "после ошибки ожидание сдачи сброшено")

	deck._pending_action = "other"
	deck._claim_guild_quest("kill_3_kobolds")
	_check(guild._message.text == "Подождите завершения текущего запроса.", "во время другого запроса сдача не уходит")
	_check(deck._pending_guild_quest.is_empty(), "занятый запрос не запоминает задание")
	deck._pending_action = ""

	deck._pending_action = "guild_claim"
	deck._pending_guild_quest = "kill_kobold"
	deck._on_api_completed(true, {"character": {"id": 42, "coins": 110}, "reward_coins": 10, "already_claimed": false})
	_check(int(GameSession.character["coins"]) == 110, "награда зачислена в монеты персонажа")
	_check(GameSession.character.has("equipment"), "экипировка не теряется при обновлении персонажа")
	_check(deck._quest_log.status("kill_kobold") == "available", "после сдачи задание снова доступно")
	_check(guild._message.text == "Получено: 10 монет", "сообщение о награде")

	deck._quest_log.accept("kill_kobold")
	deck._quest_log.record_progress("kobold")
	deck._pending_action = "guild_claim"
	deck._pending_guild_quest = "kill_kobold"
	deck._on_api_completed(true, {"character": {"id": 42, "coins": 110}, "reward_coins": 0, "already_claimed": true})
	_check(guild._message.text == "Это задание уже было сдано", "повторная сдача сообщает об этом")
	_check(int(GameSession.character["coins"]) == 110, "повторная сдача не начисляет монеты")
	_check(deck._quest_log.status("kill_kobold") == "available", "повторная сдача тоже снимает выполненное задание")

	deck._on_api_completed(false, "Персонаж не найден")
	_check(deck._pending_action.is_empty(), "неудачный запрос снимает ожидание")

	deck.queue_free()
	await get_tree().process_frame


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
