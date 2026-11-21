extends RefCounted

# Правила комнаты персонажа Tower: порт scenes/town/character_room.py. Две вкладки — «Экипировка» и «Сундуки»
# (chest1 — карты, chest2 — материалы). Надевать и снимать предметы можно в рюкзаке, как в Python: комната только
# показывает надетое и содержимое сундуков.

const CURRENCY_FORMAT := preload("res://scripts/currency_format.gd")
const TAB_EQUIPMENT := "equipment"
const TAB_CHESTS := "chests"
const TAB_TITLES := {"equipment": "Экипировка", "chests": "Сундуки"}
const CHEST_TYPES := ["chest1", "chest2"]
const CHEST_TITLES := {"chest1": "Сундук 1 (карты)", "chest2": "Сундук 2 (материалы)"}
const CHEST_CAPACITY := {"chest1": 80, "chest2": 100}
const EMPTY_CHEST_TEXT := "Сундук пуст."
const EQUIPMENT_EMPTY_TEXT := "[Пусто]"
const EQUIPMENT_TWO_HANDED_TEXT := "занято двуручным оружием"
const EQUIPMENT_HINT := "Надевать и снимать предметы можно в рюкзаке."
const EQUIPMENT_SLOT_NAMES := {
	"head": "Голова",
	"ears": "Уши",
	"neck": "Шея",
	"back": "Спина",
	"body": "Тело",
	"hands": "Руки",
	"belt": "Пояс",
	"legs": "Ноги",
	"feet": "Обувь",
	"weapon": "Оружие",
	"shield": "Щит",
	"ring": "Кольцо",
	"ring_2": "Кольцо 2",
}
const STAT_LABELS := {
	"strength": "Сила",
	"agility": "Ловкость",
	"intuition": "Интуиция",
	"endurance": "Выносливость",
	"wisdom": "Мудрость",
	"intellect": "Интеллект",
	"hp": "HP",
	"mp": "MP",
	"dodge": "% Уворот",
	"block": "% Блок",
}


static func is_tab(tab: String) -> bool:
	return TAB_TITLES.has(tab)


static func character_line(character: Dictionary) -> String:
	return "Персонаж: %s (уровень %s) · Кошелёк: %s" % [
		str(character.get("name", "Персонаж")),
		str(character.get("level", 1)),
		CURRENCY_FORMAT.format_amount(CURRENCY_FORMAT.total_copper(character)),
	]


# Строки экипировки в порядке слотов Python. Второй слот двуручного оружия показывается занятым.
static func equipment_rows(equipment: Dictionary) -> Array:
	var rows: Array = []
	for slot in EQUIPMENT_SLOT_NAMES:
		var slot_name := str(EQUIPMENT_SLOT_NAMES[slot])
		var item: Variant = equipment.get(slot)
		if not item is Dictionary:
			rows.append({"text": "%s: %s" % [slot_name, EQUIPMENT_EMPTY_TEXT], "filled": false})
		elif bool(item.get("_two_handed_shadow", false)):
			rows.append({"text": "%s: %s" % [slot_name, EQUIPMENT_TWO_HANDED_TEXT], "filled": false})
		else:
			rows.append({"text": "%s: %s" % [slot_name, item_text(item)], "filled": true})
	return rows


static func item_text(item: Dictionary) -> String:
	var text := "%s (%s)" % [str(item.get("name", "Предмет")), str(item.get("rarity", "common"))]
	var bonuses := bonus_text(item.get("bonuses"))
	return text if bonuses.is_empty() else "%s · %s" % [text, bonuses]


static func bonus_text(bonuses: Variant) -> String:
	if not bonuses is Dictionary:
		return ""
	var parts := PackedStringArray()
	for key in bonuses:
		parts.append("+%s %s" % [str(bonuses[key]), str(STAT_LABELS.get(str(key), str(key)))])
	return ", ".join(parts)


static func chest_title(storage_type: String, count: int) -> String:
	return "%s · %d / %d ячеек" % [
		str(CHEST_TITLES.get(storage_type, storage_type)),
		count,
		int(CHEST_CAPACITY.get(storage_type, 0)),
	]


static func storage_item_text(item: Dictionary) -> String:
	return "%s ×%d · ячейка %d" % [
		str(item.get("name", "Предмет")),
		int(item.get("quantity", 1)),
		int(item.get("slot_index", 0)) + 1,
	]
