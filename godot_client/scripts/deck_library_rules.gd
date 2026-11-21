extends RefCounted

# Порт справочника deck/ui/library_window.py: категории, поиск и текст записей предметов.
# Существа, карты, классы и эффекты приходят из сгенерированного deck_library_data.gd,
# предметы строятся из каталога сервера (GET /api/deck/items) тем же правилом, что _item_entry в Python.

const DATA := preload("res://scripts/deck_library_data.gd")
const CURRENCY := preload("res://scripts/deck_currency.gd")
const CATEGORIES := ["Существа", "Предметы", "Карты", "Классы", "Эффекты"]
const CARD_FIELDS := {
	"damage": "урон",
	"dice": "кубики урона",
	"heal": "лечение",
	"heal_percent": "лечение",
	"heal_flat": "базовое лечение",
	"heal_endurance": "лечение за выносливость",
	"heal_agility_multiplier": "лечение за ловкость",
	"heal_max_hp_percent": "лечение от максимального HP",
	"heal_per_turn": "лечение за ход",
	"range": "дальность",
	"duration": "длительность",
	"buff_duration": "длительность бафа",
	"stacks": "заряды",
	"poison": "яд",
	"bleed": "кровотечение",
	"entangle": "корни",
	"shield": "щит",
	"shield_flat": "прочность щита",
	"shield_hp": "прочность щита",
	"dodge_percent": "уклонение",
	"damage_percent": "урон",
	"damage_buff_percent": "усиление урона",
	"incoming_damage_percent": "снижение входящего урона",
	"crit_chance_percent": "шанс критического удара",
	"crit_damage_percent": "критический урон",
	"hits": "удары",
	"summon": "призыв",
	"summon_spirit": "призыв лесного духа",
	"spirit_hp": "здоровье духа",
	"spirit_dodge": "уклонение духа",
	"wisdom_damage": "урон за мудрость",
	"intellect_damage": "урон за интеллект",
	"wisdom_hp": "щит за мудрость",
	"intellect_shield": "щит за интеллект",
	"crit_chance_guarantee": "гарантированный крит",
	"no_miss": "без промаха",
	"element": "стихия",
}


static func static_entries(category: String) -> Array:
	match category:
		"Существа":
			return DATA.CREATURES
		"Карты":
			return DATA.CARDS
		"Классы":
			return DATA.CLASSES
		"Эффекты":
			return DATA.EFFECTS
	return []


static func item_entries(items: Array) -> Array:
	var entries: Array = []
	for item in items:
		if item is Dictionary:
			entries.append(item_entry(item))
	return entries


static func item_entry(item: Dictionary) -> Dictionary:
	var effects := _dict(item.get("effects"))
	var effect_type := str(effects.get("type", ""))
	var use_text := "Материал или экипировка; прямое использование не предусмотрено."
	if _truthy(item.get("can_use")):
		use_text = "Можно использовать вне боя."
	elif effect_type.begins_with("battle_"):
		use_text = "Используется в бою."
	var description := "Тип: %s. Редкость: %s.\nЦена: %s.\n%s\n%s" % [
		_py_value_text(item.get("item_type", "")),
		_py_value_text(item.get("rarity", "")),
		CURRENCY.format_coins(_int(item.get("price", 0))),
		_py_value_text(item.get("description", "")),
		use_text,
	]
	var parameters := PackedStringArray()
	for key in effects:
		if str(key) == "type":
			continue
		var label: String = CARD_FIELDS.get(str(key), str(key).replace("_", " "))
		parameters.append("%s: %s" % [label, _py_value_text(effects[key])])
	if not parameters.is_empty():
		description += "\nПараметры эффекта: " + ", ".join(parameters)
	return {"name": _py_value_text(item.get("name", "?")), "description": description}


# Поиск как в Python: без учёта регистра и пробелов по краям, по названию и описанию.
static func filter_entries(entries: Array, query: String) -> Array:
	var needle := query.strip_edges().to_lower()
	if needle.is_empty():
		return entries.duplicate()
	var result: Array = []
	for entry in entries:
		if str(entry["name"]).to_lower().contains(needle) or str(entry["description"]).to_lower().contains(needle):
			result.append(entry)
	return result


# str() для строк и значений f-строк Python: вложенные списки и словари печатаются как repr.
static func _py_value_text(value: Variant) -> String:
	if value is String:
		return value
	return _py_repr(value)


static func _py_repr(value: Variant) -> String:
	if value == null:
		return "None"
	if value is bool:
		return "True" if value else "False"
	if value is float and is_equal_approx(value, roundf(value)):
		return str(int(value))
	if value is int or value is float:
		return str(value)
	if value is String:
		return "'%s'" % value
	if value is Array:
		var elements := PackedStringArray()
		for element in value:
			elements.append(_py_repr(element))
		return "[%s]" % ", ".join(elements)
	if value is Dictionary:
		var pairs := PackedStringArray()
		for key in value:
			pairs.append("%s: %s" % [_py_repr(key), _py_repr(value[key])])
		return "{%s}" % ", ".join(pairs)
	return str(value)


static func _dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


static func _int(value: Variant) -> int:
	if value == null:
		return 0
	return int(value)


static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return value
	if value is int or value is float:
		return value != 0
	if value is String:
		return not value.is_empty()
	if value is Array or value is Dictionary:
		return not value.is_empty()
	return true
