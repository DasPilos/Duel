extends RefCounted

# Правила древа талантов из deck/ui/talent_tree_window.py и deck/combat/talents.py.
# Деревья и устаревшие типы берутся из deck_talent_data.gd (генерирует scripts/export_deck_talent_data.py).

const DATA := preload("res://scripts/deck_talent_data.gd")
const DEFAULT_TYPE := "warrior"


static func normalize_type(profession_type: Variant) -> String:
	var kind := "" if profession_type == null else str(profession_type)
	if kind.is_empty():
		kind = DEFAULT_TYPE
	return str(DATA.LEGACY_PROFESSION_TYPES.get(kind, kind))


static func tree_for(profession_type: Variant) -> Array:
	return DATA.TREES.get(normalize_type(profession_type), DATA.TREES[DEFAULT_TYPE])


# Как str(type).capitalize() в Python: первая буква заглавная, остальные строчные.
static func type_label(profession_type: Variant) -> String:
	var text := "" if profession_type == null else str(profession_type)
	return text.substr(0, 1).to_upper() + text.substr(1).to_lower()


static func is_unlocked(character_level: int, talent_level: int) -> bool:
	return character_level >= talent_level


static func chosen_id(talents: Variant, talent_level: int) -> String:
	if talents is Dictionary and talents.has(str(talent_level)):
		return str(talents[str(talent_level)])
	return ""


# Пустая строка — выбор разрешён; иначе текст ошибки, как в окне Python.
static func choose_error(character: Dictionary, entry: Dictionary) -> String:
	var talent_level := int(entry["level"])
	if int(character.get("level", 1)) < talent_level:
		return "Это улучшение доступно с %d-го уровня" % talent_level
	if not chosen_id(character.get("talents", {}), talent_level).is_empty():
		return "На этом уровне улучшение уже выбрано"
	return ""
