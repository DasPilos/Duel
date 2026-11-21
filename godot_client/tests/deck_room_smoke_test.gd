extends Node

# Комната персонажа Колоды: правила сверены с deck/scenes/character_room.py (подписи, порядок слотов, строки),
# вид проверяется в хосте. Сеть не используется: данные подаются напрямую.
const ROOM_VIEW_SCRIPT := preload("res://scripts/deck_room_view.gd")
const RULES := preload("res://scripts/deck_room_rules.gd")
const LOBBY_FORMAT := preload("res://scripts/lobby_format.gd")
const FIXTURE := "res://tests/fixtures/deck_backyard/social.json"

var _failures: Array[String] = []
var _checks := 0
var _tab_changes: Array[String] = []
var _doors := 0
var _backpacks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	await _check_view()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("deck_room_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(label)


func _check_rules() -> void:
	_check(RULES.character_line({"name": "Тест", "level": 3, "coins": 150}) == "Персонаж: Тест (Уровень 3) | Монеты: 150", "строка персонажа как в Python")
	_check(RULES.character_line({"name": "Тест", "level": 3.0, "coins": 150.0}) == "Персонаж: Тест (Уровень 3) | Монеты: 150", "числа из JSON (float) выводятся целыми")
	_check(RULES.is_tab("chests") and not RULES.is_tab("unknown"), "вкладки: только три известные")
	_check(RULES.sections_for_tab("chests") == ["chest1", "chest2"], "вкладка сундуков даёт оба раздела")
	_check(RULES.section_path("equipment", 7) == "/api/equipment/7", "путь экипировки")
	_check(RULES.section_path("chest2", 7) == "/api/storage/7/chest2", "путь второго сундука")
	_check(RULES.section_path("decks", 7) == "/api/deck/decks/7", "путь колод")
	_check(RULES.section_from_action(RULES.section_action("chest1")) == "chest1", "действие и раздел согласованы")
	_check(RULES.needs_load("") and RULES.needs_load("failed"), "раздел грузится, если его не было или он не загрузился")
	_check(not RULES.needs_load("loading") and not RULES.needs_load("ready"), "раздел не грузится повторно во время загрузки и после неё")
	_check(RULES.section_payload("equipment", {"equipment": {}}) is Dictionary, "пустая экипировка — валидный ответ")
	_check(RULES.section_payload("decks", {"decks": "нет"}) == null, "неверный формат колод отклоняется")
	_check(RULES.section_payload("chest1", {"storage": []}) is Array, "сундук берёт поле storage")
	_check(RULES.section_payload("chest1", null) == null, "пустой ответ отклоняется")

	var rows := RULES.equipment_rows({
		"body": {"name": "Кожаный доспех", "rarity": "common", "bonuses": {"agility": 1}},
		"weapon": {"name": "Стальной меч", "rarity": "rare", "bonuses": {"strength": 2, "harmony": 1}},
	})
	_check(rows.size() == 13, "экипировка: 13 слотов как в Python")
	_check(str(rows[0]["label"]) == "Серьги" and str(rows[12]["label"]) == "Обувь", "экипировка: порядок слотов Python")
	_check(str(rows[1]["name"]) == "[Пусто]" and bool(rows[1]["empty"]), "пустой слот выводится как [Пусто]")
	_check(str(rows[4]["name"]) == "Кожаный доспех (common)" and str(rows[4]["bonuses"]) == "+1 Ловкость", "доспех: название, редкость и бонус")
	_check(str(rows[9]["label"]) == "Л рука" and str(rows[9]["bonuses"]) == "+2 Сила, +1 Гармония", "оружие: подпись слота и бонусы с Гармонией")
	_check(RULES.bonus_text({}) == "" and RULES.bonus_text(null) == "", "без бонусов строка пустая")
	_check(RULES.bonus_text({"strength": 2.0, "agility": 1.5}) == "+2 Сила, +1.5 Ловкость", "бонусы из JSON: целые без дроби, дробные как есть")

	var items: Array = []
	for index in 12:
		items.append({"name": "Карта %d" % index, "quantity": index + 1})
	var lines := RULES.storage_lines(items)
	_check(lines.size() == 12 and lines[0] == "Карта 0 ×1" and lines[11] == "Карта 11 ×12", "сундук: все предметы, без ограничения числа строк")
	_check(RULES.storage_lines([{"name": "Карта", "quantity": 2}]) == ["Карта ×2"], "сундук: название и количество")
	_check(RULES.chest_title("chest2") == "СУНДУК 2 (МАТЕРИАЛЫ)", "заголовок второго сундука")

	var deck := {"name": "Огонь", "cards": {"fire": 2, "water": 1, "earth": 1}, "created_at": 1600000000.0, "updated_at": 1700000000.0}
	_check(RULES.deck_title(deck, 0) == "Огонь" and RULES.deck_title({}, 1) == "Колода 2", "название колоды и запасное имя")
	_check(RULES.deck_info_text(deck) == "Карт: 3 | Последнее обновление: " + LOBBY_FORMAT.local_datetime_text(1700000000.0), "колода: число карт и дата последнего изменения (updated_at)")
	_check(RULES.deck_info_text({"cards": [], "updated_at": null}) == "Карт: 0 | Последнее обновление: N/A", "колода без даты и карт")


func _check_view() -> void:
	var character: Dictionary = (_load_fixture()["character"] as Dictionary).duplicate(true)
	var host := Control.new()
	host.size = Vector2(1280.0, 720.0)
	add_child(host)
	var room = ROOM_VIEW_SCRIPT.new()
	host.add_child(room)
	room.tab_selected.connect(_on_tab_selected)
	room.door_requested.connect(_on_door_requested)
	room.backpack_requested.connect(_on_backpack_requested)
	room.set_character(character)
	room.set_active(true)
	await get_tree().process_frame
	_check(room.visible and room.current_tab() == "equipment", "комната открывается на вкладке Экипировка")
	_check(_texts(room).has(RULES.character_line(character)), "комната показывает персонажа, уровень и монеты")
	_check(_texts(room).has("ЭКИПИРОВКА") and _texts(room).has("Загрузка…"), "до ответа экипировка показывает загрузку")

	room.set_section_data("equipment", {
		"body": {"name": "Кожаный доспех", "rarity": "common", "bonuses": {"agility": 1}},
	})
	var texts := _texts(room)
	_check(texts.has("Серьги") and texts.has("[Пусто]") and texts.has("Кожаный доспех (common)") and texts.has("+1 Ловкость"), "экипировка выводится по слотам")
	_check(not texts.has("Загрузка…"), "после ответа загрузка скрыта")
	room.set_section_data("equipment", {})
	_check(_texts(room).has("Экипировка пуста"), "пустая экипировка выводит «Экипировка пуста»")

	_find_button(room, "Сундуки").pressed.emit()
	_check(room.current_tab() == "chests" and _tab_changes == ["chests"], "«Сундуки» переключает вкладку и сообщает о ней")
	_check(_texts(room).has("СУНДУК 1 (КАРТЫ)") and _texts(room).has("СУНДУК 2 (МАТЕРИАЛЫ)"), "вкладка сундуков показывает оба сундука")
	room.set_section_data("chest1", [{"name": "Карта", "quantity": 2}])
	room.set_section_state("chest2", "failed")
	_check(_texts(room).has("Карта ×2"), "предмет сундука 1 выводится")
	_check(_texts(room).has("Не удалось загрузить данные."), "неудачный сундук 2 показывает ошибку")
	room.set_section_data("chest2", [])
	_check(_texts(room).has("Сундук пуст."), "пустой сундук 2 показывает «Сундук пуст.»")
	_check(not _texts(room).has("[Пусто]"), "на вкладке сундуков экипировка скрыта")
	var many: Array = []
	for index in 40:
		many.append({"name": "Карта %d" % index, "quantity": 1})
	room.set_section_data("chest1", many)
	await get_tree().process_frame
	await get_tree().process_frame
	var bar := (room.get("_scroll") as ScrollContainer).get_v_scroll_bar()
	_check(_texts(room).has("Карта 39 ×1"), "все предметы сундука выводятся, а не первые 10")
	_check(bar.max_value > bar.page, "длинный сундук прокручивается, полоса показывает длину списка")

	_find_button(room, "Колоды").pressed.emit()
	_check(room.current_tab() == "decks" and _tab_changes == ["chests", "decks"], "«Колоды» переключает вкладку")
	_check(_texts(room).has("Загрузка…"), "колоды до ответа показывают загрузку")
	room.set_section_data("decks", [{"name": "Огонь", "cards": {"fire": 2}, "created_at": 1700000000.0}])
	_check(_texts(room).has("Огонь") and _has_prefix(_texts(room), "Карт: 1 | Последнее обновление: "), "колода выводится с числом карт и датой")
	room.set_section_data("decks", [])
	_check(_texts(room).has("Колоды не найдены"), "без колод выводится «Колоды не найдены»")
	room.set_section_state("decks", "failed")
	_check(_texts(room).has("Не удалось загрузить данные."), "ошибка колод выводится")

	_find_button(room, "Вернуться в таверну").pressed.emit()
	_check(_doors == 1, "«Вернуться в таверну» сообщает о выходе")
	_find_button_by_tooltip(room, "Карточка персонажа").pressed.emit()
	_check(room.is_profile_open(), "кнопка карточки открывает карточку персонажа")
	_find_button(room, "РЮКЗАК").pressed.emit()
	_check(_backpacks == 1 and room.is_profile_open(), "«РЮКЗАК» в карточке сообщает о рюкзаке, карточка остаётся открытой")
	room.set_character(character)

	room.reset()
	_check(not room.is_profile_open(), "новый визит закрывает карточку")
	_check(room.current_tab() == "equipment" and room.section_state("equipment") == "", "новый визит открывает Экипировку и сбрасывает разделы")
	_check(_texts(room).has("Загрузка…"), "после сброса экипировка снова ждёт ответа")
	room.set_message("Статус комнаты")
	_check(_texts(room).has("Статус комнаты"), "статус мира выводится в комнате")

	var list := VBoxContainer.new()
	host.add_child(list)
	room.dock_list(list)
	_check(list.get_parent() != host and list.get_parent() != null, "список мира переносится в область чата")
	room.undock_list(list, host, 8)
	_check(list.get_parent() == host, "список возвращается в оболочку")

	room.set_active(false)
	_check(not room.visible, "неактивная комната скрыта")
	remove_child(host)
	host.free()


func _on_tab_selected(tab: String) -> void:
	_tab_changes.append(tab)


func _on_door_requested() -> void:
	_doors += 1


func _on_backpack_requested() -> void:
	_backpacks += 1


func _load_fixture() -> Dictionary:
	var file := FileAccess.open(FIXTURE, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}


func _texts(node: Node) -> Array[String]:
	var result: Array[String] = []
	_collect_texts(node, result)
	return result


func _collect_texts(node: Node, result: Array[String]) -> void:
	if node is Label:
		result.append((node as Label).text)
	elif node is Button:
		result.append((node as Button).text)
	for child in node.get_children():
		_collect_texts(child, result)


func _has_prefix(texts: Array[String], prefix: String) -> bool:
	for text in texts:
		if text.begins_with(prefix):
			return true
	return false


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and (child as Button).text == text:
			return child as Button
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _find_button_by_tooltip(node: Node, tooltip: String) -> Button:
	for child in node.get_children():
		if child is Button and (child as Button).tooltip_text == tooltip:
			return child as Button
		var found := _find_button_by_tooltip(child, tooltip)
		if found != null:
			return found
	return null
