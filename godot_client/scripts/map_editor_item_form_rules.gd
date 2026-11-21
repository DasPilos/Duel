extends RefCounted

# Правила формы «Новый предмет»: порт core/item_form.py (default_form, validate_form, MAX_*) и таблицы полей
# из scenes/item_form_dialog.py. Файлы не читаются: список иконок передаётся снаружи.

const MAX_NAME := 64
const MAX_STAT := 50
const MAX_LEVEL := 50
const MAX_PERCENT := 100
const MAX_HP := 10000
const MAX_DAMAGE := 999
const MAX_ATTACK_DISTANCE := 100
const MAX_AURA_RADIUS := 3000
const MAX_PRICE := 1000000000
const CUSTOM_ITEM_FIRST_ID := 1000
const DEFAULT_CRIT_POWER := 50
const AURA_TYPE_OPTIONS := {"none": "Нет", "vampirism": "Вампиризм"}
const AURA_TARGET_OPTIONS := {"allies": "Союзники", "enemies": "Враги"}
# Число с более чем 15 цифрами заменяется этим значением: оно заведомо выходит за любой предел формы
# и не переполняет int64.
const OVERFLOW_VALUE := 1000000000000000
const ICON_KEY_PATTERN := "^[a-z0-9][a-z0-9_]{0,63}$"
const INT_TEXT_PATTERN := "^[+-]?[0-9]+(_[0-9]+)*$"

# Порядок соответствует слотам предметов; два слота куклы для колец объединены в один.
const EQUIPMENT_SLOTS := [
	"head", "ears", "neck", "back", "body", "hands",
	"belt", "legs", "feet", "weapon", "shield", "ring",
]
const SLOT_LABELS := {
	"head": "Голова", "ears": "Серьги", "neck": "Шея", "back": "Плащ", "body": "Доспех",
	"hands": "Руки", "weapon": "Правая рука", "shield": "Левая рука", "belt": "Пояс",
	"ring": "Кольца", "legs": "Ноги", "feet": "Обувь",
}
const ITEM_SUBCATEGORIES := [
	"Мечи", "Топоры", "Кинжалы", "Молоты", "Луки", "Посохи", "Щиты",
	"Шлемы", "Доспехи", "Перчатки", "Пояса", "Кольца", "Плащи", "Обувь", "Прочее",
]
const FORM_STATS := ["strength", "agility", "intuition", "wisdom", "intellect", "endurance"]
const STAT_LABELS := {
	"strength": "Сила", "agility": "Ловкость", "intuition": "Интуиция",
	"wisdom": "Мудрость", "intellect": "Интеллект", "endurance": "Выносливость",
}
const SLOT_ICON_PREFIXES := {
	"head": ["head_"], "ears": ["ears_"], "neck": ["neck_"], "back": ["back_"], "body": ["body_"],
	"hands": ["hands_"], "weapon": ["weapon_", "right_hand_"], "shield": ["shield_", "left_hand_"],
	"belt": ["belt_"], "ring": ["ring_", "rings_"], "ring_2": ["ring_", "rings_"], "legs": ["legs_"],
	"feet": ["feet_"],
}
# (ключ, наименьшее, наибольшее, подпись в ошибке) — порядок совпадает с validate_form в Python.
const CLEAN_INT_CHECKS := [
	["windup_percent", -90, 200, "Скорость замаха, %"],
	["recovery_percent", -90, 200, "Восстановление, %"],
	["move_speed_percent", -90, 200, "Скорость передвижения, %"],
	["price", 0, MAX_PRICE, "Цена"],
	["damage_min", 0, MAX_DAMAGE, "Урон от"],
	["damage_max", 0, MAX_DAMAGE, "Урон до"],
	["attack_range", 0, MAX_ATTACK_DISTANCE, "Дальность атаки, клеток"],
	["attack_area", 0, MAX_ATTACK_DISTANCE, "Площадь атаки, клеток"],
	["lifesteal_percent", 0, MAX_PERCENT, "Вампиризм, %"],
	["aura_radius_px", 0, MAX_AURA_RADIUS, "Радиус ауры, пикселей"],
	["aura_lifesteal_percent", 0, MAX_PERCENT, "Вампиризм ауры, %"],
	["level", 1, MAX_LEVEL, "Уровень"],
	["crit_power", 0, 500, "Сила крита, %"],
	["hp", 0, MAX_HP, "ХП"],
	["mp", 0, MAX_HP, "МП"],
	["magic_damage", 0, MAX_DAMAGE, "Маг урон"],
]
const PERCENT_CHECKS := [
	["dodge", "Уворот, %"],
	["anti_dodge", "Анти уворот, %"],
	["crit", "Крит, %"],
	["anti_crit", "Крит антикрит, %"],
	["block", "Блок, %"],
]

static var _icon_regex: RegEx
static var _int_text_regex: RegEx


static func default_form() -> Dictionary:
	var requirements := {}
	var bonuses := {}
	for stat in FORM_STATS:
		requirements[stat] = 0
		bonuses[stat] = 0
	return {
		"name": "",
		"slot": "weapon",
		"two_handed": false,
		"windup_percent": 0,
		"recovery_percent": 0,
		"move_speed_percent": 0,
		"price": 0,
		"damage_min": 0,
		"damage_max": 0,
		"attack_range": 0,
		"attack_area": 0,
		"lifesteal_percent": 0,
		"aura_type": "none",
		"aura_target": "allies",
		"aura_radius_px": 0,
		"aura_lifesteal_percent": 0,
		"level": 1,
		"requirements": requirements,
		"bonuses": bonuses,
		"dodge": 0,
		"anti_dodge": 0,
		"crit": 0,
		"anti_crit": 0,
		"crit_power": DEFAULT_CRIT_POWER,
		"block": 0,
		"hp": 0,
		"mp": 0,
		"magic_damage": 0,
		"icon": null,
	}


# Строки таблицы: три колонки формы; заголовок — строка с key "header" и kind "".
static func field_columns() -> Array:
	var first := [
		_field("name", "Название", "text"),
		_field("slot", "Слот", "slot"),
		_field("icon", "Иконка", "icon"),
		_field("two_handed", "Обе руки (двуручный)", "flag"),
		_field("windup_percent", "Скорость замаха, %", "int", 5, -90, 200),
		_field("recovery_percent", "Восстановление, %", "int", 5, -90, 200),
		_field("move_speed_percent", "Скорость передвижения, %", "int", 5, -90, 200),
		_field("damage_min", "Урон от", "int", 1, 0, MAX_DAMAGE),
		_field("damage_max", "Урон до", "int", 1, 0, MAX_DAMAGE),
		_field("attack_range", "Дальность атаки, клеток", "int", 1, 0, MAX_ATTACK_DISTANCE),
		_field("attack_area", "Площадь атаки, клеток", "int", 1, 0, MAX_ATTACK_DISTANCE),
		_field("price", "Цена, мед.", "int", 100, 0, MAX_PRICE),
	]
	var second := [_header("Требование"), _field("level", "Уровень", "int", 1, 1, MAX_LEVEL)]
	second.append_array(_stat_fields("req:", 1))
	second.append(_header("Характеристики предмета"))
	second.append_array(_stat_fields("bon:", 1))
	var third := [
		_header("Бой"),
		_field("dodge", "Уворот, %", "int", 1, 0, 100),
		_field("anti_dodge", "Анти уворот, %", "int", 1, 0, 100),
		_field("crit", "Крит, %", "int", 1, 0, 100),
		_field("anti_crit", "Крит антикрит, %", "int", 1, 0, 100),
		_field("crit_power", "Мощь критического удара, %", "int", 5, 0, 500),
		_field("block", "Шанс блока, %", "int", 1, 0, 100),
		_field("lifesteal_percent", "Вампиризм, %", "int", 1, 0, MAX_PERCENT),
		_header("Аура"),
		_field("aura_type", "Тип ауры", "choice"),
		_field("aura_target", "Цель ауры", "choice"),
		_field("aura_radius_px", "Радиус, пикселей", "int", 10, 0, MAX_AURA_RADIUS),
		_field("aura_lifesteal_percent", "Вампиризм ауры, %", "int", 1, 0, MAX_PERCENT),
		_field("hp", "ХП", "int", 10, 0, MAX_HP),
		_field("mp", "МП", "int", 10, 0, MAX_HP),
		_field("magic_damage", "Маг урон", "int", 1, 0, MAX_DAMAGE),
	]
	return [first, second, third]


static func get_value(form: Dictionary, key: String) -> Variant:
	if key.begins_with("req:"):
		return form["requirements"][key.substr(4)]
	if key.begins_with("bon:"):
		return form["bonuses"][key.substr(4)]
	return form[key]


static func set_value(form: Dictionary, key: String, value: Variant) -> void:
	if key.begins_with("req:"):
		form["requirements"][key.substr(4)] = value
	elif key.begins_with("bon:"):
		form["bonuses"][key.substr(4)] = value
	else:
		form[key] = value


# Шаг кнопок «−» и «+»: значение из текста тоже учитывается, нечисловое считается нулём.
static func step_value(form: Dictionary, spec: Dictionary, direction: int) -> int:
	var base: Variant = parse_int(get_value(form, str(spec["key"])))
	if base == null:
		base = 0
	return clampi(int(base) + direction * int(spec["step"]), int(spec["low"]), int(spec["high"]))


static func step_slot(slot: String, direction: int) -> String:
	var index := EQUIPMENT_SLOTS.find(slot)
	if index < 0:
		index = 0
	return str(EQUIPMENT_SLOTS[posmod(index + direction, EQUIPMENT_SLOTS.size())])


static func slot_label(slot: String) -> String:
	return str(SLOT_LABELS.get(slot, slot))


static func item_subcategory(item: Dictionary) -> String:
	var icon := str(item.get("icon", "")).to_lower()
	var searchable := ("%s %s" % [str(item.get("name", "")), icon]).to_lower()
	if icon.begins_with("tool_"):
		return "Прочее"
	if _contains_any(searchable, ["sword", "blade", "меч"]):
		return "Мечи"
	if _contains_any(searchable, ["axe", "топор"]):
		return "Топоры"
	if _contains_any(searchable, ["dagger", "knife", "кинжал"]):
		return "Кинжалы"
	if _contains_any(searchable, ["hammer", "mace", "молот", "булава", "дубин"]):
		return "Молоты"
	if _contains_any(searchable, ["bow", "лук"]):
		return "Луки"
	if _contains_any(searchable, ["staff", "wand", "посох"]):
		return "Посохи"
	if _contains_any(searchable, ["shield", "щит"]):
		return "Щиты"
	if _contains_any(searchable, ["helmet", "helm", "шлем", "шапк", "корон"]):
		return "Шлемы"
	if _contains_any(searchable, ["armor", "armour", "breastplate", "доспех", "брон"]):
		return "Доспехи"
	if _contains_any(searchable, ["glove", "gauntlet", "перчат"]):
		return "Перчатки"
	if _contains_any(searchable, ["belt", "пояс"]):
		return "Пояса"
	if _contains_any(searchable, ["ring", "кольц"]):
		return "Кольца"
	if _contains_any(searchable, ["cloak", "cape", "плащ"]):
		return "Плащи"
	if _contains_any(searchable, ["boot", "shoe", "сапог", "обув"]):
		return "Обувь"
	return "Прочее"


static func item_categories(items: Array, slot: String) -> Array:
	var categories: Array = []
	for item in items:
		if not item is Dictionary or _item_slot(item) != slot:
			continue
		var category := item_subcategory(item)
		if not categories.has(category):
			categories.append(category)
	categories.sort_custom(func(left: String, right: String) -> bool:
		return ITEM_SUBCATEGORIES.find(left) < ITEM_SUBCATEGORIES.find(right)
	)
	return categories


static func _item_slot(item: Dictionary) -> String:
	var slot := str(item.get("equip_slot", ""))
	return "ring" if slot == "ring_2" else slot


static func form_from_item(item: Dictionary) -> Dictionary:
	var form := default_form()
	form["name"] = str(item.get("name", ""))
	form["slot"] = str(item.get("equip_slot", "weapon"))
	if form["slot"] == "ring_2":
		form["slot"] = "ring"
	form["icon"] = item.get("icon")
	form["price"] = item.get("price", 0)
	var bonuses: Variant = item.get("bonuses", {})
	var effects: Variant = item.get("effects", {})
	if not bonuses is Dictionary:
		bonuses = {}
	if not effects is Dictionary:
		effects = {}
	for stat in FORM_STATS:
		form["bonuses"][stat] = bonuses.get(stat, 0)
	var requirements: Variant = effects.get("requirements", {})
	if requirements is Dictionary:
		for stat in FORM_STATS:
			form["requirements"][stat] = requirements.get(stat, 0)
	form["level"] = requirements.get("level", 1) if requirements is Dictionary else 1
	var damage: Variant = effects.get("damage", [])
	if damage is Array and damage.size() >= 2:
		form["damage_min"] = damage[0]
		form["damage_max"] = damage[1]
	for key in [
		"two_handed", "windup_percent", "recovery_percent", "move_speed_percent",
		"attack_range", "attack_area", "lifesteal_percent", "dodge", "anti_dodge",
		"crit", "anti_crit", "crit_power", "block", "magic_damage",
	]:
		form[key] = effects.get(key, bonuses.get(key, form[key]))
	form["hp"] = bonuses.get("hp", 0)
	form["mp"] = bonuses.get("mp", 0)
	var aura: Variant = effects.get("aura", {})
	if aura is Dictionary:
		form["aura_type"] = aura.get("type", "none")
		form["aura_target"] = aura.get("target", "allies")
		form["aura_radius_px"] = aura.get("radius_px", 0)
		form["aura_lifesteal_percent"] = aura.get("lifesteal_percent", 0)
	return form


static func _contains_any(text: String, needles: Array) -> bool:
	for needle in needles:
		if text.contains(str(needle)):
			return true
	return false


# Как int() в Python: пробелы по краям, знак и подчёркивания между цифрами. Нечисловой текст даёт null.
static func parse_int(raw: Variant) -> Variant:
	if raw is bool:
		return 1 if raw else 0
	if raw is int:
		return raw
	if raw is float:
		if is_nan(raw) or is_inf(raw):
			return null
		return int(clampf(raw, -float(OVERFLOW_VALUE), float(OVERFLOW_VALUE)))
	if raw is String:
		return _parse_int_text(raw)
	return null


static func is_valid_icon_key(key: String) -> bool:
	if _icon_regex == null:
		_icon_regex = RegEx.create_from_string(ICON_KEY_PATTERN)
	return _icon_regex.search(key) != null


static func is_known_icon(key: Variant, known_icons: Array) -> bool:
	return key is String and is_valid_icon_key(key) and known_icons.has(key)


# Ключи иконок из имён файлов папки: как icon_keys() в core/item_icons.py (только *.png, по алфавиту).
static func icon_keys_from_files(file_names: PackedStringArray) -> Array:
	var keys: Array = []
	for file_name in file_names:
		if not file_name.ends_with(".png"):
			continue
		var key := file_name.trim_suffix(".png")
		if is_valid_icon_key(key) and not keys.has(key):
			keys.append(key)
	keys.sort()
	return keys


static func icons_for_slot(slot: String, known_icons: Array) -> Array:
	var keys := known_icons.duplicate()
	keys.sort()
	var prefixes: Array = SLOT_ICON_PREFIXES.get(slot, [slot + "_"])
	var matching: Array = []
	for key in keys:
		for prefix in prefixes:
			if str(key).begins_with(str(prefix)):
				matching.append(key)
				break
	return matching if not matching.is_empty() else keys


# Первый пункт выбора иконки — «нет» (null), затем иконки слота.
static func icon_options_for_slot(slot: String, known_icons: Array) -> Array:
	var options: Array = [null]
	options.append_array(icons_for_slot(slot, known_icons))
	return options


# Проверка как validate_form в core/item_form.py. Возвращает {"clean": Dictionary, "error": String};
# пустая error — форма принята. Порядок проверок и тексты совпадают с Python.
static func validate_form(form: Dictionary, known_icons: Array) -> Dictionary:
	var merged := _merged_form(form)
	var name := str(merged["name"]).strip_edges()
	if name.is_empty():
		return _rejected("Укажите название предмета")
	if name.length() > MAX_NAME:
		return _rejected("Название длиннее %d символов" % MAX_NAME)
	if merged["slot"] == "ring_2":
		merged["slot"] = "ring"
	if not EQUIPMENT_SLOTS.has(merged["slot"]):
		return _rejected("Выберите слот экипировки")
	if not AURA_TYPE_OPTIONS.has(merged["aura_type"]):
		return _rejected("Выберите тип ауры")
	if not AURA_TARGET_OPTIONS.has(merged["aura_target"]):
		return _rejected("Выберите цель ауры")
	var icon: Variant = merged["icon"] if _truthy(merged["icon"]) else null
	if icon != null and not is_known_icon(icon, known_icons):
		return _rejected("Иконка не найдена в базе иконок")
	var clean := {
		"name": name,
		"slot": merged["slot"],
		"icon": icon,
		"aura_type": merged["aura_type"],
		"aura_target": merged["aura_target"],
		"two_handed": _truthy(merged["two_handed"]),
	}
	for check in CLEAN_INT_CHECKS:
		var key := str(check[0])
		var result := _int_in(merged, key, int(check[1]), int(check[2]), str(check[3]))
		if not str(result["error"]).is_empty():
			return _rejected(str(result["error"]))
		clean[key] = result["value"]
	if int(clean["damage_min"]) > int(clean["damage_max"]):
		return _rejected("Урон «от» не может быть больше «до»")
	for check in PERCENT_CHECKS:
		var key := str(check[0])
		var result := _int_in(merged, key, 0, MAX_PERCENT, str(check[1]))
		if not str(result["error"]).is_empty():
			return _rejected(str(result["error"]))
		clean[key] = result["value"]
	for group in ["requirements", "bonuses"]:
		var values: Dictionary = merged[group]
		var clean_group := {}
		for stat in FORM_STATS:
			var result := _int_in(values, stat, 0, MAX_STAT, str(STAT_LABELS[stat]))
			if not str(result["error"]).is_empty():
				return _rejected(str(result["error"]))
			clean_group[stat] = result["value"]
		clean[group] = clean_group
	return {"clean": clean, "error": ""}


static func _field(key: String, label: String, kind: String, step := 0, low := 0, high := 0) -> Dictionary:
	return {"key": key, "label": label, "kind": kind, "step": step, "low": low, "high": high}


static func _header(label: String) -> Dictionary:
	return _field("header", label, "")


static func _stat_fields(prefix: String, step: int) -> Array:
	var rows: Array = []
	for stat in FORM_STATS:
		rows.append(_field(prefix + stat, str(STAT_LABELS[stat]), "int", step, 0, MAX_STAT))
	return rows


# Значения по умолчанию поверх переданной формы, как {**defaults, **form} в Python; группы сливаются по стату
# (пустая группа — null или нет ключа — даёт значения по умолчанию).
static func _merged_form(form: Dictionary) -> Dictionary:
	var merged := default_form()
	for key in form:
		if not key in ["requirements", "bonuses"]:
			merged[key] = form[key]
	for group in ["requirements", "bonuses"]:
		var values: Dictionary = merged[group]
		var given: Variant = form.get(group)
		if given is Dictionary:
			for stat in given:
				values[stat] = given[stat]
	return merged


static func _int_in(values: Dictionary, key: String, low: int, high: int, label: String) -> Dictionary:
	var parsed: Variant = parse_int(values.get(key))
	if parsed == null:
		return {"value": 0, "error": "%s: нужно целое число" % label}
	var value := int(parsed)
	if value < low or value > high:
		return {"value": 0, "error": "%s: от %d до %d" % [label, low, high]}
	return {"value": value, "error": ""}


static func _rejected(message: String) -> Dictionary:
	return {"clean": {}, "error": message}


static func _parse_int_text(raw: String) -> Variant:
	var text := raw.strip_edges()
	if _int_text_regex == null:
		_int_text_regex = RegEx.create_from_string(INT_TEXT_PATTERN)
	if _int_text_regex.search(text) == null:
		return null
	var digits := text.trim_prefix("+").trim_prefix("-").replace("_", "").lstrip("0")
	if digits.length() > 15:
		return -OVERFLOW_VALUE if text.begins_with("-") else OVERFLOW_VALUE
	return text.replace("_", "").to_int()


static func _truthy(value: Variant) -> bool:
	if value == null:
		return false
	if value is bool:
		return bool(value)
	if value is int or value is float:
		return value != 0
	if value is String or value is StringName:
		return not str(value).is_empty()
	if value is Array or value is Dictionary:
		return not value.is_empty()
	return true
