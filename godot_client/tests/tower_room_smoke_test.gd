extends Node

const ROOM_VIEW_SCRIPT := preload("res://scripts/tower_room_view.gd")
const ROOM_RULES := preload("res://scripts/tower_room_rules.gd")

var _failures: Array[String] = []
var _tab_changes: Array[String] = []
var _withdraws: Array[Dictionary] = []
var _doors := 0
var _backpacks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_rules()
	var host := Control.new()
	host.size = Vector2(1280.0, 720.0)
	add_child(host)
	var room = ROOM_VIEW_SCRIPT.new()
	host.add_child(room)
	room.tab_selected.connect(_on_tab_selected)
	room.withdraw_requested.connect(_on_withdraw_requested)
	room.door_requested.connect(_on_door_requested)
	room.inventory_requested.connect(_on_backpack_requested)
	room.set_character({"name": "Тест", "level": 3, "copper": 5, "silver": 2, "gold": 1})
	room.set_equipment({
		"body": {"name": "Кожаный доспех", "rarity": "common", "bonuses": {"agility": 1}},
		"weapon": {"name": "Стальной меч", "rarity": "rare", "bonuses": {"strength": 2, "intuition": 1}},
	})
	room.set_chests({"chest1": [{"id": 5, "name": "Карта", "quantity": 2, "slot_index": 0}], "chest2": []})
	await get_tree().process_frame
	_check(ROOM_VIEW_SCRIPT.background_texture() != null, "фон комнаты найден в общих assets")

	_check(room.current_tab() == "equipment", "комната открывается на вкладке Экипировка")
	var texts := _texts(room)
	_check(texts.has("Персонаж: Тест (уровень 3) · Кошелёк: 1 золото 2 серебра 5 меди"), "комната показывает персонажа и кошелёк")
	_check(texts.has("Тело: Кожаный доспех (common) · +1 Ловкость"), "экипировка показывает надетую броню и бонусы")
	_check(texts.has("Оружие: Стальной меч (rare) · +2 Сила, +1 Интуиция"), "экипировка показывает бонусы оружия")
	_check(texts.has("Голова: [Пусто]"), "пустой слот выводится как [Пусто]")
	_check(not texts.has("Сундук 1 (карты) · 1 / 80 ячеек"), "на вкладке Экипировка сундуки не показываются")

	_find_button(room, "Сундуки").pressed.emit()
	_check(room.current_tab() == "chests" and _tab_changes == ["chests"], "«Сундуки» переключает вкладку и сообщает о ней")
	texts = _texts(room)
	_check(texts.has("Сундук 1 (карты) · 1 / 80 ячеек"), "вкладка Сундуки показывает первый сундук с вместимостью")
	_check(texts.has("Карта ×2 · ячейка 1"), "в сундуке 1 видна карта с количеством и ячейкой")
	_check(texts.has("Сундук 2 (материалы) · 0 / 100 ячеек") and texts.has("Сундук пуст."), "второй сундук пуст и помечен как пустой")
	_check(not texts.has("Голова: [Пусто]"), "на вкладке Сундуки экипировка скрыта")

	_find_button(room, "В рюкзак").pressed.emit()
	_check(_withdraws.size() == 1 and _withdraws[0]["storage_type"] == "chest1" and int(_withdraws[0]["item"]["id"]) == 5, "«В рюкзак» передаёт сундук и предмет")

	_find_button(room, "Вернуться в таверну").pressed.emit()
	_find_button(room, "Рюкзак").pressed.emit()
	_check(_doors == 1 and _backpacks == 1, "дверь и кнопка Рюкзак отправляют свои сигналы")

	_find_button(room, "Экипировка").pressed.emit()
	_check(room.current_tab() == "equipment" and _tab_changes == ["chests", "equipment"], "возврат на Экипировку переключает вкладку")
	_check(_texts(room).has("Тело: Кожаный доспех (common) · +1 Ловкость"), "после возврата экипировка снова видна")

	room.set_status("Перемещаем предметы…")
	_check(_texts(room).has("Перемещаем предметы…"), "статус комнаты выводится под вкладками")
	remove_child(host)
	host.free()

	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("tower_room_smoke_test: OK")
	get_tree().quit(code)


func _check_rules() -> void:
	_check(ROOM_RULES.bonus_text({"strength": 2, "hp": 20}) == "+2 Сила, +20 HP", "бонусы выводятся подписями Python")
	_check(ROOM_RULES.bonus_text({}) == "" and ROOM_RULES.bonus_text(null) == "", "без бонусов строка пустая")
	_check(ROOM_RULES.equipment_rows({}).size() == 13, "строк экипировки столько же, сколько слотов Python")
	var shadow_rows: Array = ROOM_RULES.equipment_rows({"shield": {"_two_handed_shadow": true, "name": "Меч"}})
	_check(_row_text(shadow_rows, "Щит") == "Щит: занято двуручным оружием", "второй слот двуручного оружия показан занятым")
	_check(ROOM_RULES.chest_title("chest2", 3) == "Сундук 2 (материалы) · 3 / 100 ячеек", "заголовок сундука показывает вместимость")
	_check(ROOM_RULES.storage_item_text({"name": "Руда", "quantity": 4, "slot_index": 2}) == "Руда ×4 · ячейка 3", "предмет сундука показывает ячейку с единицы")
	_check(ROOM_RULES.is_tab("equipment") and ROOM_RULES.is_tab("chests") and not ROOM_RULES.is_tab("backpack"), "у комнаты две вкладки")


func _row_text(rows: Array, slot_name: String) -> String:
	for row in rows:
		if str(row["text"]).begins_with(slot_name + ":"):
			return str(row["text"])
	return ""


func _texts(node: Node) -> PackedStringArray:
	var result := PackedStringArray()
	for label in node.find_children("*", "Label", true, false):
		result.append(label.text)
	return result


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _on_tab_selected(tab: String) -> void:
	_tab_changes.append(tab)


func _on_withdraw_requested(storage_type: String, item: Dictionary) -> void:
	_withdraws.append({"storage_type": storage_type, "item": item})


func _on_door_requested() -> void:
	_doors += 1


func _on_backpack_requested() -> void:
	_backpacks += 1


func _check(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
