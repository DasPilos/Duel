extends Node

# Таблица решений по правилам ui/inventory_window.py: порог перетаскивания, _drop_onto, _quick_action, подсветка и
# раскладка «куклы». Координаты слотов сверены с equipment_slots.slot_rects(pygame.Rect(0, 0, 440, 440)).

const RULES := preload("res://scripts/inventory_drag_rules.gd")

const BOW := {"name": "Простой лук", "rarity": "rare", "item_type": "equipment", "equip_slot": "weapon",
	"effects": {"damage": [3, 5]}, "bonuses": {"strength": 2}, "weight": 2, "price": 500}
const LONG_BOW := {"name": "Длинный лук", "item_type": "equipment", "equip_slot": "weapon",
	"effects": {"two_handed": true, "damage": [4, 6]}, "weight": 3, "price": 800}
const DAGGER := {"name": "Кинжал", "item_type": "equipment", "equip_slot": "weapon", "effects": {"either_hand": true}}
const SHIELD := {"name": "Щит", "item_type": "equipment", "equip_slot": "shield", "effects": {}}
const HELMET := {"name": "Шлем", "item_type": "equipment", "equip_slot": "head", "effects": {}}
const POTION := {"name": "Зелье здоровья", "item_type": "potion", "can_use": true,
	"effects": {"type": "hp", "value": 40}, "weight": 0.5, "price": 150}
const BOARD := {"name": "Дубовая доска", "item_type": "material", "equip_slot": null, "effects": {}, "weight": 1, "price": 10}
const WRONG_SLOT := "Предмет не подходит для этого слота"

const PYTHON_SLOT_RECTS := {
	"ears": Rect2(15, 25, 66, 62), "head": Rect2(187, 25, 66, 62), "neck": Rect2(356, 25, 66, 62),
	"back": Rect2(15, 111, 66, 62), "body": Rect2(187, 111, 66, 62), "ring": Rect2(356, 111, 66, 62),
	"hands": Rect2(15, 197, 66, 62), "shield": Rect2(110, 197, 66, 62), "belt": Rect2(187, 197, 66, 62),
	"weapon": Rect2(275, 197, 66, 62), "ring_2": Rect2(356, 197, 66, 62),
	"legs": Rect2(187, 283, 66, 62), "feet": Rect2(187, 369, 66, 62),
}

var _failures: Array[String] = []
var _checks := 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_drag_threshold()
	_check_slot_accepts()
	_check_drop_decisions()
	_check_quick_decisions()
	_check_success_colors()
	_check_highlight()
	_check_paperdoll_rects()
	_check_item_lines()
	_check_labels_and_bodies()
	var code := 0 if _failures.is_empty() else 1
	for failure in _failures:
		push_error(failure)
	if code == 0:
		print("inventory_drag_rules_smoke_test: OK (%d checks)" % _checks)
	get_tree().quit(code)


func _check_drag_threshold() -> void:
	var origin := Vector2(100.0, 100.0)
	_check(not RULES.is_drag_started(origin, Vector2(104.0, 104.0)), "квадрат 32 ≤ 36: перетаскивания нет")
	_check(not RULES.is_drag_started(origin, Vector2(105.0, 103.0)), "квадрат 34 ≤ 36: перетаскивания нет")
	_check(not RULES.is_drag_started(origin, Vector2(106.0, 100.0)), "ровно 6 px не начинает перетаскивание (строго больше 36)")
	_check(RULES.is_drag_started(origin, Vector2(106.0, 101.0)), "квадрат 37 > 36: перетаскивание начинается")
	_check(RULES.is_drag_started(origin, Vector2(105.0, 105.0)), "диагональ 50 > 36: перетаскивание начинается")


func _check_slot_accepts() -> void:
	_check(RULES.slot_accepts(BOW, "weapon"), "лук принимается в слот оружия")
	_check(not RULES.slot_accepts(BOW, "shield"), "обычный лук не идёт в щит")
	_check(RULES.slot_accepts(LONG_BOW, "shield"), "двуручный лук идёт в слот щита")
	_check(RULES.slot_accepts(DAGGER, "shield"), "предмет «любая рука» идёт в слот щита")
	_check(not RULES.slot_accepts(SHIELD, "weapon"), "щит не идёт в слот оружия")
	_check(RULES.slot_accepts(HELMET, "head") and not RULES.slot_accepts(HELMET, "weapon"), "шлем только в слот головы")
	_check(not RULES.slot_accepts(LONG_BOW, "body"), "двуручность не открывает другие слоты")
	_check(not RULES.slot_accepts(POTION, "weapon") and not RULES.slot_accepts(POTION, "head"), "зелье без слота не надевается")


func _check_drop_decisions() -> void:
	_expect("перенос в пустую ячейку", RULES.drop_decision(["bag", 0], ["bag", 7], POTION),
		"move", {"from_slot": 0, "to_slot": 7}, "", false, ["bag", 7])
	_expect("перенос на ту же ячейку", RULES.drop_decision(["bag", 0], ["bag", 0], POTION), "none", {}, "", false)
	_expect("лук в слот оружия", RULES.drop_decision(["bag", 3], ["equip", "weapon"], BOW),
		"equip", {"slot_index": 3, "slot": "weapon"}, "Надето: Простой лук", false, ["equip", "weapon"])
	_expect("зелье в слот оружия", RULES.drop_decision(["bag", 0], ["equip", "weapon"], POTION),
		"none", {}, WRONG_SLOT, true)
	_expect("шлем в слот головы", RULES.drop_decision(["bag", 5], ["equip", "head"], HELMET),
		"equip", {"slot_index": 5, "slot": "head"}, "Надето: Шлем", false, ["equip", "head"])
	_expect("шлем в слот кольца", RULES.drop_decision(["bag", 5], ["equip", "ring"], HELMET), "none", {}, WRONG_SLOT, true)
	_expect("двуручный лук в слот щита", RULES.drop_decision(["bag", 4], ["equip", "shield"], LONG_BOW),
		"equip", {"slot_index": 4, "slot": "shield"}, "Надето: Длинный лук", false, ["equip", "shield"])
	_expect("кинжал «любая рука» в слот щита", RULES.drop_decision(["bag", 6], ["equip", "shield"], DAGGER),
		"equip", {"slot_index": 6, "slot": "shield"}, "Надето: Кинжал", false, ["equip", "shield"])
	_expect("щит в слот оружия", RULES.drop_decision(["bag", 2], ["equip", "weapon"], SHIELD), "none", {}, WRONG_SLOT, true)
	_expect("снятие лука в ячейку рюкзака", RULES.drop_decision(["equip", "weapon"], ["bag", 6], BOW),
		"unequip", {"slot": "weapon", "target_slot": 6}, "Снято: Простой лук", false, [])
	_expect("экипировка в экипировку ничего не делает", RULES.drop_decision(["equip", "weapon"], ["equip", "shield"], BOW),
		"none", {}, "", false)
	_expect("отпускание вне сетки", RULES.drop_decision(["bag", 0], [], POTION), "none", {}, "", false)
	_expect("пустой предмет под источником", RULES.drop_decision(["bag", 0], ["bag", 1], {}), "none", {}, "", false)


func _check_quick_decisions() -> void:
	_expect("правый клик по надетому луку снимает без слота", RULES.quick_decision(["equip", "weapon"], BOW),
		"unequip", {"slot": "weapon", "target_slot": -1}, "Снято: Простой лук", false)
	_expect("правый клик по луку в рюкзаке надевает", RULES.quick_decision(["bag", 3], BOW),
		"equip", {"slot_index": 3, "slot": ""}, "Надето: Простой лук", false)
	_expect("правый клик по зелью использует", RULES.quick_decision(["bag", 0], POTION),
		"use", {"slot_index": 0}, "Использовано: Зелье здоровья", false)
	_expect("правый клик по доске ничего не делает", RULES.quick_decision(["bag", 7], BOARD),
		"none", {}, "Этот предмет нельзя использовать", false)
	_expect("правый клик мимо ячейки", RULES.quick_decision([], {}), "none", {}, "", false)


func _check_success_colors() -> void:
	_check(RULES.success_color(RULES.ACTION_EQUIP) == Color8(120, 220, 120), "«Надето» зелёным, как GREEN в Python")
	_check(RULES.success_color(RULES.ACTION_USE) == Color8(120, 220, 120), "«Использовано» зелёным, как GREEN в Python")
	_check(RULES.success_color(RULES.ACTION_UNEQUIP) == Color8(150, 142, 130), "«Снято» приглушённым, как TEXT_DIM в Python")
	_check(RULES.success_color(RULES.ACTION_DROP) == Color8(150, 142, 130), "«Выброшено» приглушённым, как TEXT_DIM в Python")


func _check_highlight() -> void:
	_check(RULES.highlight_slot(true, ["bag", 5], HELMET) == "head", "при перетаскивании шлема подсвечен слот головы")
	_check(RULES.highlight_slot(false, ["bag", 5], HELMET) == "", "без перетаскивания подсветки нет")
	_check(RULES.highlight_slot(true, ["bag", 0], POTION) == "", "зелье без слота не подсвечивает экипировку")
	_check(RULES.highlight_slot(true, ["equip", "weapon"], BOW) == "", "предмет, снимаемый из слота, не подсвечивает")
	_check(RULES.highlight_slot(true, [], {}) == "", "без нажатой ячейки подсветки нет")
	_check(RULES.highlight_slot(true, ["bag", 4], LONG_BOW) == "weapon", "двуручный лук подсвечивает только слот оружия, как Python")


func _check_paperdoll_rects() -> void:
	var rects := RULES.paperdoll_slot_rects(Rect2(0, 0, 440, 440))
	_check(rects.size() == PYTHON_SLOT_RECTS.size(), "в «кукле» тринадцать слотов")
	for slot in PYTHON_SLOT_RECTS:
		_check(rects.get(slot) == PYTHON_SLOT_RECTS[slot], "слот %s совпадает с equipment_slots.py" % slot)
	_check(RULES.slot_label("weapon") == "Л рука" and RULES.slot_label("shield") == "П рука", "подписи слотов как в SLOT_LABELS")


func _check_item_lines() -> void:
	var bow_lines := RULES.item_lines(BOW)
	_check(bow_lines[0][0] == "Простой лук" and bow_lines[0][1] == Color8(80, 150, 255), "название окрашено цветом редкости")
	var bow_texts := _texts(bow_lines)
	_check(bow_texts[1] == "Редкий · Экипировка · Л рука", "строка редкости, типа и слота")
	_check(bow_texts.has("+2 Сила") and bow_texts.has("Урон: 3-5"), "бонус и урон оружия")
	_check(bow_texts.back() == "Вес: 2 кг   ·   Цена: 5 серебра", "вес и цена как в Python")
	var potion_texts := _texts(RULES.item_lines(POTION))
	_check(potion_texts.has("Восстанавливает 40 здоровья"), "зелье описывает восстановление")
	_check(potion_texts.back() == "Вес: 0.5 кг   ·   Цена: 1 серебро 50 меди", "150 меди выводятся как 1 серебро 50 меди")
	var helmet_texts := _texts(RULES.item_lines(HELMET))
	_check(helmet_texts[1] == "Обычный · Экипировка · Голова", "предмет без редкости считается обычным")
	_check(_texts(RULES.item_lines(BOARD)).back() == "Вес: 1 кг   ·   Цена: 10 меди", "предмет без бонусов и урона")


func _texts(lines: Array) -> Array:
	var texts: Array = []
	for line in lines:
		texts.append(line[0])
	return texts


# Подпись кнопки панели и тела запросов: пустой slot и target_slot -1 не уходят на сервер, как None в Python.
func _check_labels_and_bodies() -> void:
	_check(RULES.action_label(["equip", "weapon"], BOW) == "Снять", "надетый предмет: кнопка «Снять»")
	_check(RULES.action_label(["bag", 3], BOW) == "Надеть", "предмет экипировки в рюкзаке: кнопка «Надеть»")
	_check(RULES.action_label(["bag", 0], POTION) == "Использовать", "зелье: кнопка «Использовать»")
	_check(RULES.action_label(["bag", 7], BOARD) == "", "предмет без действия: кнопки нет")
	_check(RULES.action_label([], {}) == "", "пустая цель: кнопки нет")
	_check(RULES.equip_body(3, "") == {"slot_index": 3}, "надевание без слота: только ячейка")
	_check(RULES.equip_body(3, "weapon") == {"slot_index": 3, "slot": "weapon"}, "надевание в слот: ячейка и слот")
	_check(RULES.unequip_body("weapon", -1) == {"slot": "weapon"}, "снятие без ячейки: только слот")
	_check(RULES.unequip_body("weapon", 11) == {"slot": "weapon", "target_slot": 11}, "снятие в ячейку: слот и target_slot")
	_check(RULES.ACTION_DROP == "drop" and RULES.BUSY_MESSAGE == "Подождите завершения текущего запроса.", "константы выброса и ожидания")


func _expect(label: String, decision: Dictionary, action: String, params: Dictionary, message: String, is_error: bool, select = null) -> void:
	_check(str(decision.get("action")) == action, "%s: действие %s" % [label, action])
	_check(decision.get("params") == params, "%s: параметры %s" % [label, str(params)])
	_check(str(decision.get("message")) == message and bool(decision.get("is_error")) == is_error,
		"%s: сообщение «%s»" % [label, message])
	_check(decision.has("select") == (select != null) and (select == null or decision.get("select") == select),
		"%s: выбор ячейки" % label)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
