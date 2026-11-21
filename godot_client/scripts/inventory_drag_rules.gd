extends RefCounted

# Правила перетаскивания рюкзака из ui/inventory_window.py без UI: порог начала, решение при отпускании кнопки над
# целью, быстрые действия, подходящий слот (двуручное оружие и «любая рука»), подсветка и раскладка «куклы» экипировки.
# Ячейка — Array: ["bag", индекс ячейки рюкзака] или ["equip", ключ слота]; пустой Array значит «ячейки нет».
# В решениях slot "" и target_slot -1 означают, что слот выберет сервер, как в Python.

const CARD := preload("res://scripts/character_card.gd")
const CHARACTER_RULES := preload("res://scripts/character_profile_rules.gd")
const CURRENCY_FORMAT := preload("res://scripts/currency_format.gd")

const KIND_BAG := "bag"
const KIND_EQUIP := "equip"
const ACTION_NONE := "none"
const ACTION_MOVE := "move"
const ACTION_EQUIP := "equip"
const ACTION_UNEQUIP := "unequip"
const ACTION_USE := "use"
const ACTION_DROP := "drop"
const DRAG_THRESHOLD_SQUARED := 36.0
const TWO_HAND_SLOTS := ["weapon", "shield"]
const WRONG_SLOT_MESSAGE := "Предмет не подходит для этого слота"
const CANNOT_USE_MESSAGE := "Этот предмет нельзя использовать"
const BUSY_MESSAGE := "Подождите завершения текущего запроса."
const REFERENCE_CENTER_X := 220.0
const MIDDLE_ROW_SHIFT := 8.0
const ROW_OFFSETS := [-172.0, -86.0, 0.0, 86.0, 172.0]
const RARITY_LABELS := {"common": "Обычный", "rare": "Редкий", "epic": "Эпический", "legendary": "Легендарный"}
const TYPE_LABELS := {"potion": "Зелье", "material": "Материал", "equipment": "Экипировка", "scroll": "Свиток"}
const TEXT_COLOR := Color8(230, 222, 205)
const TEXT_DIM_COLOR := Color8(150, 142, 130)
const GOOD_COLOR := Color8(120, 220, 120)
const BAD_COLOR := Color8(235, 110, 100)
const DAMAGE_COLOR := Color8(255, 215, 120)


# Порог начала перетаскивания: квадрат расстояния строго больше 36 (6 px), как в Python.
static func is_drag_started(press_position: Vector2, position: Vector2) -> bool:
	return press_position.distance_squared_to(position) > DRAG_THRESHOLD_SQUARED


static func text_of(item: Dictionary, key: String, fallback: String) -> String:
	var value: Variant = item.get(key)
	return fallback if value == null else str(value)


static func equip_slot_of(item: Dictionary) -> String:
	return text_of(item, "equip_slot", "")


static func slot_label(slot: String) -> String:
	for entry in CARD.SLOT_LAYOUT:
		if str(entry[0]) == slot:
			return str(entry[1])
	return slot


static func rarity_color(item: Dictionary, fallback: Color) -> Color:
	return CARD.RARITY_COLORS.get(text_of(item, "rarity", ""), fallback)


# Двуручное оружие и предмет «любая рука» (effects.two_handed / either_hand) можно положить в слот оружия или щита.
static func slot_accepts(item: Dictionary, slot: String) -> bool:
	if equip_slot_of(item) == slot:
		return true
	var effects := _dict(item.get("effects"))
	var hand_free := bool(effects.get("two_handed", false)) or bool(effects.get("either_hand", false))
	return hand_free and TWO_HAND_SLOTS.has(slot)


# Подсветка только по equip_slot предмета из рюкзака, как _highlight_slot в Python.
static func highlight_slot(dragging: bool, pressed: Array, pressed_item: Dictionary) -> String:
	if not dragging or pressed.is_empty() or str(pressed[0]) != KIND_BAG:
		return ""
	return equip_slot_of(pressed_item)


# Отпускание кнопки над целью (_drop_onto). item — предмет под источником (для слота — надетый).
static func drop_decision(source: Array, target: Array, item: Dictionary) -> Dictionary:
	if source.is_empty() or target.is_empty() or source == target or item.is_empty():
		return _none()
	var source_kind := str(source[0])
	var target_kind := str(target[0])
	var item_name := text_of(item, "name", "Предмет")
	if source_kind == KIND_BAG and target_kind == KIND_BAG:
		return _action(ACTION_MOVE, {"from_slot": int(source[1]), "to_slot": int(target[1])}, "", target)
	if source_kind == KIND_BAG and target_kind == KIND_EQUIP:
		var slot := str(target[1])
		if not slot_accepts(item, slot):
			return _none(WRONG_SLOT_MESSAGE, true)
		return _action(ACTION_EQUIP, {"slot_index": int(source[1]), "slot": slot}, "Надето: %s" % item_name, target)
	if source_kind == KIND_EQUIP and target_kind == KIND_BAG:
		return _action(ACTION_UNEQUIP, {"slot": str(source[1]), "target_slot": int(target[1])}, "Снято: %s" % item_name, [])
	return _none()


# Правый клик (_quick_action): снять экипировку, надеть или использовать предмет.
static func quick_decision(target: Array, item: Dictionary) -> Dictionary:
	if target.is_empty() or item.is_empty():
		return _none()
	var item_name := text_of(item, "name", "Предмет")
	if str(target[0]) == KIND_EQUIP:
		return _action(ACTION_UNEQUIP, {"slot": str(target[1]), "target_slot": -1}, "Снято: %s" % item_name)
	if not equip_slot_of(item).is_empty():
		return _action(ACTION_EQUIP, {"slot_index": int(target[1]), "slot": ""}, "Надето: %s" % item_name)
	if bool(item.get("can_use", false)):
		return _action(ACTION_USE, {"slot_index": int(target[1])}, "Использовано: %s" % item_name)
	return _none(CANNOT_USE_MESSAGE)


# Подпись основной кнопки панели предмета, как _action_label в экономике.
static func action_label(target: Array, item: Dictionary) -> String:
	if target.is_empty() or item.is_empty():
		return ""
	if str(target[0]) == KIND_EQUIP:
		return "Снять"
	if not equip_slot_of(item).is_empty():
		return "Надеть"
	if bool(item.get("can_use", false)):
		return "Использовать"
	return ""


# Тела запросов как в client/network.py: пустой slot и target_slot -1 не отправляются, сервер выберет слот сам.
static func equip_body(slot_index: int, slot: String) -> Dictionary:
	var body := {"slot_index": slot_index}
	if not slot.is_empty():
		body["slot"] = slot
	return body


static func unequip_body(slot: String, target_slot: int) -> Dictionary:
	var body := {"slot": slot}
	if target_slot >= 0:
		body["target_slot"] = target_slot
	return body


# Цвет успешного сообщения как в ui/inventory_window.py: «Надето» и «Использовано» — GOOD_COLOR (GREEN),
# «Снято» и «Выброшено» — TEXT_DIM_COLOR.
static func success_color(action: String) -> Color:
	if action == ACTION_EQUIP or action == ACTION_USE:
		return GOOD_COLOR
	return TEXT_DIM_COLOR


# Слоты «куклы» в рамке frame: equipment_slots.slot_rects, ширина рамки масштабирует колонки относительно 440 px.
static func paperdoll_slot_rects(frame: Rect2) -> Dictionary:
	var scale := frame.size.x / CARD.CARD_WIDTH
	var area_center_y := (frame.position.y + CARD.AREA_TOP_OFFSET + frame.end.y - CARD.AREA_BOTTOM_OFFSET) / 2.0
	var middle_row_top := floorf(area_center_y - MIDDLE_ROW_SHIFT)
	var rects := {}
	for entry in CARD.SLOT_LAYOUT:
		var column_center := float(CARD.COLUMN_CENTERS[int(entry[2])])
		var left := roundf(frame.get_center().x + (column_center - REFERENCE_CENTER_X) * scale - CARD.SLOT_WIDTH / 2.0)
		var top: float = middle_row_top + ROW_OFFSETS[int(entry[3])]
		rects[str(entry[0])] = Rect2(left, top, CARD.SLOT_WIDTH, CARD.SLOT_HEIGHT)
	return rects


# Строки описания как _item_lines в Python: [текст, цвет]. Первая строка — название.
static func item_lines(item: Dictionary) -> Array:
	var rarity := text_of(item, "rarity", "common")
	var kind := text_of(item, "item_type", "")
	kind = str(TYPE_LABELS.get(kind, kind))
	var slot := equip_slot_of(item)
	if not slot.is_empty():
		kind = "%s · %s" % [kind, slot_label(slot)]
	var lines: Array = [
		[text_of(item, "name", "?"), CARD.RARITY_COLORS.get(rarity, TEXT_COLOR)],
		["%s · %s" % [RARITY_LABELS.get(rarity, rarity), kind], TEXT_DIM_COLOR],
	]
	var description := text_of(item, "description", "")
	if not description.is_empty():
		lines.append([description, TEXT_COLOR])
	var bonuses := _dict(item.get("bonuses"))
	for stat in bonuses:
		var value := int(bonuses[stat])
		var sign_text := "+" if value > 0 else ""
		lines.append(["%s%d %s" % [sign_text, value, CHARACTER_RULES.STAT_LABELS.get(str(stat), str(stat))], GOOD_COLOR if value > 0 else BAD_COLOR])
	if slot == "weapon":
		var damage: Variant = CHARACTER_RULES.weapon_damage_range({"weapon": item})
		if damage != null:
			var low: int = damage.x
			var high: int = damage.y
			lines.append(["Урон: %s" % (str(low) if low == high else "%d-%d" % [low, high]), DAMAGE_COLOR])
	var effects := _dict(item.get("effects"))
	var effect_type := text_of(effects, "type", "")
	if bool(item.get("can_use", false)) and (effect_type == "hp" or effect_type == "mp"):
		var resource := "здоровья" if effect_type == "hp" else "маны"
		lines.append(["Восстанавливает %s %s" % [text_of(effects, "value", "0"), resource], GOOD_COLOR])
	var weight := weight_text(float(item.get("weight", 0.0)))
	var price := CURRENCY_FORMAT.format_amount(int(item.get("price", 0)))
	lines.append(["Вес: %s кг   ·   Цена: %s" % [weight, price], TEXT_DIM_COLOR])
	return lines


# Формат Python «{:g}»: 2.0 → «2», 0.5 → «0.5».
static func weight_text(value: float) -> String:
	return ("%.3f" % value).rstrip("0").rstrip(".")


static func _none(message: String = "", is_error: bool = false) -> Dictionary:
	return {"action": ACTION_NONE, "params": {}, "message": message, "is_error": is_error}


static func _action(action: String, params: Dictionary, message: String = "", select: Variant = null) -> Dictionary:
	var decision := {"action": action, "params": params, "message": message, "is_error": false}
	if select != null:
		decision["select"] = select
	return decision


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}
